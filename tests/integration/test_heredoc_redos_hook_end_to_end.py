"""End-to-end tests for Issue #1620 — the heredoc ReDoS through the real hook.

The unit-level differential in
``tests/unit/lib/test_heredoc_utils_scanner_equivalence.py`` proves the linear
scanner reproduces the old regex byte-for-byte. This module proves the two
things that file structurally cannot:

1. the blow-up is gone *through the real hook subprocess*, driven with a real
   PreToolUse payload on stdin — the path that actually consumed the 5-second
   budget; and
2. all 7 call sites that consume the strip return the SAME verdicts they
   returned with the old regex — 0 disagreements — so the ReDoS fix did not
   quietly change what the security gates block.

Why the budget matters. ``.claude/settings.json`` gives ``unified_pre_tool.py``
``"timeout": 5``. Measured in a sandbox, both arms, two runs each: an
instant-deny PreToolUse hook BLOCKED, and the identical deny behind ``sleep 8``
PROCEEDED. Exceeding the budget therefore skips EVERY gate in the hook at once,
including the #1435 protected-infrastructure hard floor. The production timing
corpus holds 16 historical over-budget events for this hook across five days
(max 12.719 s), predating any probing. Pre-fix measurement through this same
harness: 147 characters at N=21 body lines cost 6.65 s; controls from the same
run were 0.086 s (terminated heredoc) and 0.083 s (``echo hello``).

Instrument verification (a probe that cannot fail cannot inform):

* POSITIVE control on the timing probe — the harness reports > 1 s for a
  deliberately slow subprocess, so a slow hook WOULD be caught.
* POSITIVE control on the input — the ORIGINAL regex on the very same N=21
  command exceeds the hook ceiling on its own, so the command really is
  adversarial rather than merely long.
* NEGATIVE controls — a same-size TERMINATED heredoc and ``echo hello`` stay
  fast AND keep normal verdicts, so "fast" is not an artifact of the hook
  short-circuiting the whole payload.

Issue: #1620
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

#: The SOURCE copies under ``plugins/`` — what this module imports and drives.
SOURCE_HOOK = HOOK_DIR / "unified_pre_tool.py"
#: The copies that EXECUTE in a live session, refreshed by
#: ``bash scripts/deploy-all.sh``. Committed is not deployed.
DEPLOYED_HOOK = REPO_ROOT / ".claude" / "hooks" / "unified_pre_tool.py"
DEPLOYED_LIB = REPO_ROOT / ".claude" / "lib" / "heredoc_utils.py"

for _path in (str(HOOK_DIR), str(LIB_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import edit_tier_classifier  # noqa: E402
import unified_pre_tool as hook  # noqa: E402
from heredoc_utils import strip_heredoc_content  # noqa: E402

#: The exponential pattern this issue removed, kept here as the "before"
#: implementation for the verdict-preservation comparison.
_OLD_PATTERN = re.compile(
    r"<<-?\s*['\"]?(\w+)['\"]?.*?\n(.*?\n)*?[ \t]*\1\b",
    re.DOTALL,
)

#: PreToolUse budget for this hook in ``.claude/settings.json``.
HOOK_TIMEOUT_BUDGET_S = 5.0
#: AC3 (end-to-end half): N=21 through the real hook must finish under 1 s.
HOOK_CEILING_S = 1.0
#: Body-line count first measured OVER the budget pre-fix (6.65 s).
ADVERSARIAL_BODY_LINES = 21


@pytest.fixture(autouse=True)
def isolated_gate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep every global gate marker this module can reach out of ``/tmp``.

    Two pieces of shared filesystem state make in-process gate calls
    order-dependent across runs (Issue #1184 consecutive-run isolation):

    * ``/tmp/.claude_deny_cache.jsonl`` — the Issue #558 escalation cache read by
      ``_check_bash_infra_writes``; a leftover entry silently rewrites the block
      message on the FIRST call of a later run.
    * ``/tmp/autonomous_dev_cmd_context.json`` — the sanctioning marker whose mere
      presence makes the gh-issue-create gate PERMIT what it would refuse
      (Issues #1609, #1618).

    Both are redirected per test to paths that do not exist.
    """
    monkeypatch.setattr(hook, "DENY_CACHE_PATH", str(tmp_path / "deny_cache.jsonl"))
    isolated_marker = tmp_path / "no_such_context.json"
    monkeypatch.setenv("GH_ISSUE_CMD_CONTEXT_PATH", str(isolated_marker))
    monkeypatch.setattr(hook, "GH_ISSUE_COMMAND_CONTEXT_PATH", str(isolated_marker), raising=False)
    yield


def _adversarial_command(body_lines: int = ADVERSARIAL_BODY_LINES) -> str:
    """Return the unterminated-heredoc command that used to blow the budget."""
    body = "".join(f"line{i}\n" for i in range(body_lines))
    return "cat <<EOF > f.txt\n" + body


def _terminated_command(body_lines: int = ADVERSARIAL_BODY_LINES) -> str:
    """Return the same command WITH its closing delimiter — negative control."""
    return _adversarial_command(body_lines) + "EOF\n"


def _drive_hook(hook_path: Path, command: str, ctx_path: Path) -> tuple[str, float]:
    """Run ``hook_path`` as a subprocess the way Claude Code does.

    Env scrubbing mirrors
    ``tests/regression/test_issue_1619_gh_issue_create_wrapper_bypass.py``:
    the sanctioning marker is redirected to a path that does not exist (the
    real global ``/tmp`` marker is never read or written) and the agent-name /
    bypass variables are removed so an inherited session cannot permit what the
    gate would otherwise refuse.

    Args:
        hook_path: The hook script to execute.
        command: The Bash command string to submit as ``tool_input``.
        ctx_path: Scratch path for the sanctioning marker (must not exist).

    Returns:
        ``(permission_decision, wall_seconds)``.
    """
    env = dict(os.environ)
    env["GH_ISSUE_CMD_CONTEXT_PATH"] = str(ctx_path)
    env.pop("CLAUDE_AGENT_NAME", None)
    env.pop("AUTONOMOUS_DEV_BYPASS", None)
    payload = {
        "session_id": "test-1620",
        "cwd": str(REPO_ROOT),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=120,
    )
    elapsed = time.perf_counter() - started
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:  # pragma: no cover - diagnostic path
        pytest.fail(f"hook produced non-JSON: {proc.stdout!r} / {proc.stderr!r}")
    return parsed.get("hookSpecificOutput", {}).get("permissionDecision", ""), elapsed


# ---------------------------------------------------------------------------
# Timing, with its controls
# ---------------------------------------------------------------------------
def test_timing_probe_can_observe_a_slow_hook(tmp_path: Path) -> None:
    """POSITIVE control on the instrument: the harness catches a slow subprocess.

    ``test_adversarial_heredoc_stays_under_hook_budget`` reports a small number.
    A small number is only evidence if a large one were reportable. This drives
    a stand-in hook that sleeps past the ceiling and checks the harness says so.
    """
    slow_hook = tmp_path / "slow_hook.py"
    slow_hook.write_text(
        "import sys, time, json\n"
        "sys.stdin.read()\n"
        f"time.sleep({HOOK_CEILING_S + 0.5})\n"
        'print(json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}))\n',
        encoding="utf-8",
    )
    verdict, elapsed = _drive_hook(slow_hook, "echo hello", tmp_path / "no_ctx.json")
    assert verdict == "allow", "control hook must still speak the decision protocol"
    assert elapsed > HOOK_CEILING_S, (
        f"the timing harness reported {elapsed:.3f}s for a subprocess that sleeps "
        f"{HOOK_CEILING_S + 0.5}s. The probe cannot observe a slow hook, so every "
        "other timing assertion in this module is measuring nothing."
    )


def test_original_regex_is_orders_of_magnitude_slower_on_the_same_command() -> None:
    """POSITIVE control on the INPUT: the N=21 command really is adversarial.

    Without this, "the hook is fast" could mean nothing more than "N=21 was
    never expensive". In-process, with no subprocess overhead at all, the
    ORIGINAL regex and the shipped scanner are run on the SAME command and the
    ratio is asserted — scale-free, so it does not become a knife-edge on slower
    or busier hardware the way an absolute second-count does. Measured here:
    ~1.0 s versus ~9 microseconds.
    """
    command = _adversarial_command()
    # The on-record hook measurement was 147 characters at N=21 with marginally
    # shorter body lines; this harness's N=21 command is 155. Both are "a command
    # a human could type by accident", which is the load-bearing property — so the
    # assertion is on that property, not on a length transcribed from elsewhere.
    assert len(command) < 200, f"the adversarial command grew to {len(command)} chars"

    started = time.perf_counter()
    _OLD_PATTERN.sub("", command)
    old_s = time.perf_counter() - started

    started = time.perf_counter()
    for _ in range(100):
        strip_heredoc_content(command)
    new_s = (time.perf_counter() - started) / 100

    ratio = old_s / new_s if new_s else float("inf")
    print(
        f"[#1620] N={ADVERSARIAL_BODY_LINES} in-process: OLD {old_s:.3f}s vs "
        f"NEW {new_s:.6f}s ({ratio:.0f}x)"
    )
    assert old_s > 0.25, (
        f"the ORIGINAL regex handled the N={ADVERSARIAL_BODY_LINES} command in "
        f"{old_s:.3f}s. The input stopped being adversarial, so the end-to-end "
        "assertion no longer demonstrates the fix."
    )
    assert ratio > 1000, (
        f"the linear scanner is only {ratio:.0f}x faster than the exponential regex "
        f"on the very command that blew the {HOOK_TIMEOUT_BUDGET_S}s budget "
        f"(OLD {old_s:.3f}s, NEW {new_s:.6f}s). The exponential class is back."
    )


def test_adversarial_heredoc_stays_under_hook_budget(tmp_path: Path) -> None:
    """AC3 (end-to-end half): N=21 through the real hook, under 1 s.

    Pre-fix this exact 147-character command cost 6.65 s against a 5 s budget,
    which skipped every PreToolUse gate rather than merely delaying one.

    The two in-run NEGATIVE controls are what make the number attributable: a
    same-size TERMINATED heredoc and ``echo hello`` must be fast too AND must
    return normal verdicts. If they were slow the number would be hook startup
    rather than the strip; if their verdicts were empty or anomalous, "fast"
    would mean the hook bailed out instead of running the gates.
    """
    ctx = tmp_path / "no_ctx.json"

    terminated_verdict, terminated_s = _drive_hook(SOURCE_HOOK, _terminated_command(), ctx)
    echo_verdict, echo_s = _drive_hook(SOURCE_HOOK, "echo hello", ctx)
    adversarial_verdict, adversarial_s = _drive_hook(SOURCE_HOOK, _adversarial_command(), ctx)

    print(
        f"[#1620] hook e2e: unterminated N={ADVERSARIAL_BODY_LINES} {adversarial_s:.3f}s "
        f"({adversarial_verdict}) | terminated {terminated_s:.3f}s ({terminated_verdict}) "
        f"| echo hello {echo_s:.3f}s ({echo_verdict})"
    )

    # Negative controls: fast AND normal verdicts.
    assert terminated_verdict == "allow"
    assert echo_verdict == "allow"
    assert terminated_s < HOOK_CEILING_S, (
        f"the TERMINATED-heredoc control took {terminated_s:.3f}s. Baseline hook "
        "cost has moved; the adversarial number below is no longer attributable "
        "to the heredoc strip."
    )
    assert echo_s < HOOK_CEILING_S, (
        f"the ``echo hello`` control took {echo_s:.3f}s — baseline hook cost has "
        "moved, see above."
    )

    # The measurement.
    assert adversarial_verdict in {"allow", "ask", "deny"}, (
        f"hook returned {adversarial_verdict!r} for the adversarial command; a "
        "fast run that produced no verdict would mean the hook bailed out rather "
        "than ran the gates."
    )
    assert adversarial_s < HOOK_CEILING_S, (
        f"the N={ADVERSARIAL_BODY_LINES} unterminated heredoc took {adversarial_s:.3f}s "
        f"end-to-end (ceiling {HOOK_CEILING_S}s, hook budget {HOOK_TIMEOUT_BUDGET_S}s). "
        "Claude Code PROCEEDS past a timed-out hook — measured, both arms — so this "
        "is a bypass of every PreToolUse gate at once, not latency."
    )
    assert adversarial_s < HOOK_TIMEOUT_BUDGET_S


# ---------------------------------------------------------------------------
# Verdict preservation across all 7 call sites
# ---------------------------------------------------------------------------
#: Commands chosen to reach each of the 7 consumers of the strip, in both the
#: heredoc-body arm (content that must be treated as DATA) and the real-command
#: arm (content that must still be treated as EXECUTABLE), plus the
#: proper-prefix delimiter shapes that exercise the emulated ``(\w+)``
#: backtracking the scanner has to reproduce.
_VERDICT_CORPUS = (
    # --- plain / no heredoc at all ---
    "echo hello",
    "gh issue create --title x --body y",
    "env CLAUDE_AGENT_NAME=implementer gh issue create --title x",
    "rm -f .claude/state/pipeline_state.json",
    "rm -rf $UNSET_VAR/",
    "cat > plugins/autonomous-dev/lib/evil.py",
    # --- heredoc body arm: the keyword is DATA ---
    "cat <<EOF > notes.md\ngh issue create --title x\nEOF\n",
    "cat <<'EOF' > notes.md\nrm -rf $HOME/\nEOF\n",
    "cat <<EOF > notes.md\nrm -f .claude/state/pipeline_state.json\nEOF\n",
    "cat <<-EOF > notes.md\n\tenv CLAUDE_AGENT_NAME=implementer bash\n\tEOF\n",
    "cat <<EOF > notes.md\ncat > plugins/autonomous-dev/lib/evil.py\nEOF\n",
    # --- real-command arm: opener + a real command after the closer ---
    "cat <<EOF > notes.md\nharmless\nEOF\ngh issue create --title x",
    "cat <<EOF > notes.md\nharmless\nEOF\nrm -rf $UNSET_VAR/",
    # --- code-file writes (edit_tier_classifier) ---
    "cat > module.py <<'EOF'\nprint(1)\nEOF\n",
    "cat > plugins/autonomous-dev/lib/module.py <<EOF\nprint(1)\nEOF\n",
    # --- proper-prefix delimiter shapes (the emulated class) ---
    "cat <<EOF > notes.md\ngh issue create --title x\nEO\n",
    "cat <<EOF2 > notes.md\ngh issue create --title x\nEOF\n",
    "cat <<EOF > notes.md\nrm -rf $UNSET_VAR/\nE\n",
    "print(1)\ncat <<EOF\ncat <<EOF2\ncat <<'EOF'\nEO\ngh issue create --title x\nEOF2\n",
    # --- unterminated: nothing may be stripped ---
    "cat <<EOF > notes.md\ngh issue create --title x\nno closer here\n",
    "cat <<EOF > notes.md\nrm -rf $UNSET_VAR/\nEOFX\n",
    # --- overlapping opener ---
    "cat <<<EOF\ngh issue create --title x\nEOF\n",
)


def _old_strip(command: str) -> str:
    """The pre-#1620 strip, for the before/after verdict comparison."""
    if not command:
        return command
    try:
        return _OLD_PATTERN.sub("", command)
    except re.error:  # pragma: no cover - matches the old fail-open contract
        return command


def _seven_call_sites() -> tuple[tuple[str, Callable[[str], object]], ...]:
    """Return ``(label, callable)`` for each of the 7 consumers of the strip.

    Verified by Grep rather than ``find_referencing_symbols``: the hook loads
    ``heredoc_utils`` through ``importlib.util``, which is invisible to the LSP
    (it reports only the ``edit_tier_classifier`` import and ``__all__``). This
    is a case where the symbol tool under-reports and Grep is the correct
    instrument.
    """
    return (
        ("unified_pre_tool:3142 _detect_env_spoofing", hook._detect_env_spoofing),
        (
            "unified_pre_tool:4283 _gh_issue_create_at_command_position",
            hook._gh_issue_create_at_command_position,
        ),
        ("unified_pre_tool:5004 _detect_gh_issue_create", hook._detect_gh_issue_create),
        ("unified_pre_tool:6630 _check_bash_state_deletion", hook._check_bash_state_deletion),
        (
            "unified_pre_tool:6725 _check_rm_rf_unresolved_vars",
            hook._check_rm_rf_unresolved_vars,
        ),
        ("unified_pre_tool:7160 _check_bash_infra_writes", hook._check_bash_infra_writes),
        (
            "edit_tier_classifier:623 detect_bash_code_file_write",
            edit_tier_classifier.detect_bash_code_file_write,
        ),
    )


def _run_corpus(arm_state_file: Path) -> dict[tuple[str, str], object]:
    """Drive every call site over the corpus from a FRESH gate-state baseline.

    ``_check_bash_infra_writes`` is stateful: it escalates its message to
    "BLOCKED (repeated attempt)" via the Issue #558 deny cache at
    ``/tmp/.claude_deny_cache.jsonl``. Running two arms back to back in one
    process therefore makes the SECOND arm disagree with the first for reasons
    that have nothing to do with heredocs — this harness produced exactly two
    such phantom disagreements before the state was isolated, on two commands
    whose strip output was byte-identical under both implementations. Each arm
    gets its own cache file, so both see the same state evolution, and the real
    global cache is never touched.

    Args:
        arm_state_file: Per-arm deny-cache path (must not be shared).

    Returns:
        Mapping of ``(call_site_label, command)`` to that gate's verdict.
    """
    original = hook.DENY_CACHE_PATH
    hook.DENY_CACHE_PATH = str(arm_state_file)
    try:
        return {
            (label, command): fn(command)
            for label, fn in _seven_call_sites()
            for command in _VERDICT_CORPUS
        }
    finally:
        hook.DENY_CACHE_PATH = original


def _diff(left: dict[tuple[str, str], object], right: dict[tuple[str, str], object]) -> list[str]:
    """Return human-readable descriptions of every verdict that moved."""
    return [
        f"{label} on {command!r}: left={left[(label, command)]!r} "
        f"right={right[(label, command)]!r}"
        for (label, command) in left
        if left[(label, command)] != right[(label, command)]
    ]


def test_verdict_harness_is_deterministic(tmp_path: Path) -> None:
    """NEGATIVE control on the comparison harness: identical arms must agree.

    Two runs of the SAME implementation must produce identical verdicts. Without
    this control the stateful deny cache made the harness report 2 disagreements
    for a scanner that was in fact byte-identical to the regex on those very
    commands — i.e. it would have been read as an emulation defect and "fixed"
    by weakening something real.
    """
    first = _run_corpus(tmp_path / "arm_a.jsonl")
    second = _run_corpus(tmp_path / "arm_b.jsonl")
    moved = _diff(first, second)
    assert not moved, (
        "running the SAME implementation twice moved "
        f"{len(moved)} verdict(s), so a gate still carries state across arms and "
        "the before/after comparison below cannot attribute anything:\n" + "\n".join(moved[:10])
    )


def test_all_seven_call_sites_keep_their_verdicts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC6: 0 verdict disagreements between the old regex and the new scanner.

    A ReDoS fix that changes what the gates block is a security regression
    wearing a performance fix's clothes. Each call site is driven twice over the
    same corpus from an identical fresh state — once with the shipped linear
    scanner, once with the original regex injected at the module boundary the
    hook actually reads (``_strip_heredoc_fn`` /
    ``edit_tier_classifier._strip_heredoc_content``) — and every pair must agree.
    """
    sites = _seven_call_sites()
    assert len(sites) == 7, "the audited call-boundary count is 7, not 8 (:4225 is a docstring)"

    new_verdicts = _run_corpus(tmp_path / "new_arm.jsonl")

    monkeypatch.setattr(hook, "_strip_heredoc_fn", _old_strip)
    monkeypatch.setattr(edit_tier_classifier, "_strip_heredoc_content", _old_strip)
    old_verdicts = _run_corpus(tmp_path / "old_arm.jsonl")

    disagreements = _diff(new_verdicts, old_verdicts)
    print(
        f"[#1620] verdict disagreements: {len(disagreements)} across "
        f"{len(sites)} call sites x {len(_VERDICT_CORPUS)} commands"
    )
    assert not disagreements, (
        "the linear scanner changed what the security gates decide — "
        + f"{len(disagreements)} disagreement(s):\n"
        + "\n".join(disagreements[:10])
    )


def test_verdict_comparison_can_observe_a_disagreement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """POSITIVE control on the comparison: it CAN report more than 0.

    A harness that reports 0 disagreements is only evidence if a non-zero result
    is reachable. Injecting a strip that removes nothing at all must move at
    least one verdict on this corpus — otherwise the corpus never reaches the
    heredoc carve-out and the AC6 assertion above is vacuous. State is isolated
    per arm exactly as above, so the movement is attributable to the strip and
    not to gate state.
    """
    baseline = _run_corpus(tmp_path / "baseline.jsonl")

    monkeypatch.setattr(hook, "_strip_heredoc_fn", lambda command: command)
    monkeypatch.setattr(edit_tier_classifier, "_strip_heredoc_content", lambda command: command)
    no_strip = _run_corpus(tmp_path / "no_strip.jsonl")

    moved = _diff(baseline, no_strip)
    print(f"[#1620] no-strip control moved {len(moved)} verdict(s)")
    assert moved, (
        "disabling the heredoc strip entirely changed NO verdict on this corpus, "
        "so the corpus does not reach the heredoc carve-out and "
        "test_all_seven_call_sites_keep_their_verdicts proves nothing."
    )


# ---------------------------------------------------------------------------
# The copy that EXECUTES
# ---------------------------------------------------------------------------
def test_deployed_copy_state_is_explicit(tmp_path: Path) -> None:
    """Committed is not deployed; deployed is not loaded.

    The live session runs ``.claude/hooks/unified_pre_tool.py``, which resolves
    its heredoc helper as ``parent.parent / "lib" / "heredoc_utils.py"`` — i.e.
    ``.claude/lib/heredoc_utils.py``, NOT the source tree this module drives
    above. Editing the source alone leaves the fix a runtime no-op.

    Both arms assert something true, so this never cries wolf:

    * deploy has run  -> re-run the N=21 measurement against the DEPLOYED hook.
    * deploy pending  -> assert the deployed copy is still the PRE-fix artifact,
      i.e. the fix is genuinely not live yet. ``bash scripts/deploy-all.sh`` is
      the coordinator's step and AC8 is its gate.

    No byte-equality assertion is made: it would be permanently red in every dev
    checkout with a staged change, and a check that cries wolf trains everyone
    to ignore the class.
    """
    assert DEPLOYED_HOOK.exists(), f"missing deploy artifact: {DEPLOYED_HOOK}"
    assert DEPLOYED_LIB.exists(), f"missing deploy artifact: {DEPLOYED_LIB}"

    deployed_source = DEPLOYED_LIB.read_text(encoding="utf-8")
    if "_build_line_index" not in deployed_source:
        assert "_HEREDOC_PATTERN" in deployed_source, (
            f"{DEPLOYED_LIB} carries neither the pre-#1620 regex nor the linear "
            "scanner. The deployed artifact is a third thing; re-run "
            "`bash scripts/deploy-all.sh`."
        )
        print("[#1620] deploy PENDING — deployed lib is still the pre-fix regex")
        return

    _, elapsed = _drive_hook(DEPLOYED_HOOK, _adversarial_command(), tmp_path / "no_ctx.json")
    print(f"[#1620] DEPLOYED hook e2e N={ADVERSARIAL_BODY_LINES}: {elapsed:.3f}s")
    assert elapsed < HOOK_CEILING_S, (
        f"the DEPLOYED hook took {elapsed:.3f}s on the N={ADVERSARIAL_BODY_LINES} "
        f"command (ceiling {HOOK_CEILING_S}s). The source copy is fixed but the copy "
        "that EXECUTES is not."
    )

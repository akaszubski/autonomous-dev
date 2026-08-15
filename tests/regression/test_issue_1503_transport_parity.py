"""Regression tests for Issue #1503 — transport-independent write enforcement.

Every enforcement site used to decide "is this a write?" with a hard-coded
literal tuple like ``("Write", "Edit")``. Any file-mutating tool whose name
was not in the specific tuple at a specific site walked straight through.
Measured against the protected target ``hooks/plan_gate.py`` before the fix::

    Write -> deny | Edit -> deny | NotebookEdit -> ALLOW | MultiEdit -> ALLOW
    mcp__serena__replace_symbol_body -> ALLOW | insert_after_symbol -> ALLOW
    mcp__serena__replace_content -> ALLOW

``NotebookEdit`` ships with Claude Code, so the Issue #1435
protected-infrastructure hard floor (invariant INV-4 in ``.claude/PROJECT.md``)
was bypassable with zero MCP servers installed.

These tests drive the REAL hooks with REAL PreToolUse payloads via subprocess —
no mocking. A passing test that never observed a block is not evidence.

Groups:
  A. Protected infra denies all 7 write transports.
  B. Same 7 still deny under the universal bypass (INV-4 survives).
  C. Negative controls — reads must never be blocked.
  D. plan_gate denies a >100-line change with no plan across all 7 transports.
  E. plan_gate ALLOWS a <100-line change across all 7 transports.
  F. Doc-file exemption survives the transport change.
  G. Non-protected target — the hard floor does NOT fire (no over-blocking).
  H. Denial-reason ordering change after the hard-floor relocation.
  I. Stale-install fallback — MultiEdit/NotebookEdit still deny without
     tool_intent.
  J. Forged content key must not buy back the simple-edit exemption.
  K. Bash semantics are UNCHANGED by the widening — Bash keeps its own
     dedicated path with its own (looser) pipeline-active rule.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# tests/regression/test_x.py -> regression -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
UPT_HOOK = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
PLAN_GATE_HOOK = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "plan_gate.py"

# Real protected-infrastructure targets. _is_protected_infrastructure() is
# anchored to the CANONICAL repo path and returns False for a synthetic temp
# tree, so a fake protected file proves nothing — we must use real paths.
PROTECTED_HOOK = str(PLAN_GATE_HOOK)
PROTECTED_LIB = str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "pipeline_state.py")

BLOCKED_DECISIONS = {"deny", "block", "ask"}

BIG_CHANGE = "\n".join(f"def generated_fn_{i}():\n    return {i}" for i in range(120))
SMALL_CHANGE = "def tiny():\n    return 1\n"


def _payload_builders():
    """Every transport that can mutate a file, with its realistic payload shape."""
    return [
        ("Write", lambda p, c: {"file_path": p, "content": c}),
        ("Edit", lambda p, c: {"file_path": p, "old_string": "x", "new_string": c}),
        ("MultiEdit", lambda p, c: {
            "file_path": p, "edits": [{"old_string": "x", "new_string": c}]}),
        ("NotebookEdit", lambda p, c: {
            "notebook_path": p, "cell_id": "c1", "new_source": c}),
        ("mcp__serena__replace_symbol_body", lambda p, c: {
            "relative_path": p, "name_path": "main", "body": c}),
        ("mcp__serena__insert_after_symbol", lambda p, c: {
            "relative_path": p, "name_path": "main", "body": c}),
        ("mcp__serena__replace_content", lambda p, c: {
            "relative_path": p, "needle": "x", "repl": c}),
    ]


WRITE_TRANSPORTS = _payload_builders()
WRITE_TRANSPORT_IDS = [name for name, _ in WRITE_TRANSPORTS]

# Issue #1503 follow-up (reviewer FINDING-1 / security-auditor F3). These four
# write transports carry NO content argument at all, so changed_content()
# returns "" and the line count is 0 however many lines the call removes. The
# line-count exemption is therefore not a size proxy for them and they must
# fall through to the plan requirement instead of being auto-exempt.
#
# ``replace_in_files`` deliberately carries a small NON-EMPTY ``repl`` so this
# proves the unbounded-impact rule (it rewrites an unbounded set of files from
# one tiny replacement string) rather than the empty-content path.
CONTENTLESS_WRITE_TRANSPORTS = [
    ("mcp__serena__rename_symbol", lambda p: {
        "relative_path": p, "name_path": "main", "new_name": "renamed_main"}),
    ("mcp__serena__safe_delete_symbol", lambda p: {
        "relative_path": p, "name_path_pattern": "main"}),
    ("mcp__serena__delete_lines", lambda p: {
        "relative_path": p, "start_line": 1, "end_line": 400}),
    ("mcp__serena__replace_in_files", lambda p: {
        "relative_path": p, "needle": "x", "repl": "y"}),
]
CONTENTLESS_WRITE_IDS = [name for name, _ in CONTENTLESS_WRITE_TRANSPORTS]

# Must NEVER be blocked. Several carry a path argument on purpose — a naive
# "has a path -> block" rule would break these, which is the explicit
# over-correction failure mode called out in the issue.
READONLY_CONTROLS = [
    ("Read", {"file_path": PROTECTED_HOOK}),
    ("Grep", {"pattern": "def", "path": str(REPO_ROOT)}),
    ("mcp__serena__find_symbol",
     {"name_path_pattern": "main", "relative_path": PROTECTED_HOOK}),
    ("mcp__serena__get_symbols_overview", {"relative_path": PROTECTED_HOOK}),
    ("mcp__serena__find_referencing_symbols",
     {"name_path": "main", "relative_path": PROTECTED_HOOK}),
    ("mcp__searxng__search", {"query": "python"}),
    ("WebFetch", {"url": "https://example.com", "prompt": "summarise"}),
    ("mcp__ms365__send-mail", {"subject": "hi", "body": "text body no path"}),
]
READONLY_IDS = [name for name, _ in READONLY_CONTROLS]


def _run_hook(
    hook_path: Path,
    tool_name: str,
    tool_input: dict,
    *,
    cwd: Path | None = None,
    env_extra: dict | None = None,
) -> tuple[str, str]:
    """Run a hook with a PreToolUse payload; return (decision, reason)."""
    workdir = cwd or REPO_ROOT
    payload = {
        "session_id": "regression-1503",
        "transcript_path": "/dev/null",
        "cwd": str(workdir),
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    env = os.environ.copy()
    for key in (
        "SKIP_PLAN_CHECK",
        "AUTONOMOUS_DEV_BYPASS",
        "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW",
        "ENFORCEMENT_LEVEL",
    ):
        env.pop(key, None)
    env["CLAUDE_PROJECT_DIR"] = str(workdir)
    env.update(env_extra or {})

    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(workdir),
        env=env,
    )

    decision = ""
    reason = ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        hso = parsed.get("hookSpecificOutput", {})
        decision = hso.get("permissionDecision") or parsed.get("decision") or decision
        reason = hso.get("permissionDecisionReason") or parsed.get("reason") or reason
    if not decision:
        decision = f"<no-json exit={result.returncode}>"
    return decision, reason


# unified_pre_tool records every protected-path deny in a SHARED /tmp cache
# (Issue #803 cross-tool workaround detection). /tmp is NOT cleared between
# pytest invocations, so these tests would otherwise leak entries into
# subsequent test modules and fail them on a second consecutive run
# (Issue #1184 class). Snapshot-and-restore keeps this module hermetic without
# destroying entries another concurrently-running module may depend on.
DENY_CACHE_PATH = Path("/tmp/.claude_deny_cache.jsonl")


@pytest.fixture(autouse=True)
def _isolate_deny_cache():
    """Restore the shared deny cache to its pre-test contents."""
    before = DENY_CACHE_PATH.read_text() if DENY_CACHE_PATH.exists() else None
    try:
        yield
    finally:
        try:
            if before is None:
                DENY_CACHE_PATH.unlink(missing_ok=True)
            else:
                DENY_CACHE_PATH.write_text(before)
        except OSError:
            pass


@pytest.fixture
def plan_gate_workspace():
    """A throwaway repo-shaped dir with an empty .claude/plans/."""
    with tempfile.TemporaryDirectory(prefix="issue1503-plangate-") as tmp:
        root = Path(tmp)
        (root / ".claude" / "plans").mkdir(parents=True)
        (root / "src").mkdir()
        yield root


# ---------------------------------------------------------------------------
# Group A — protected infrastructure denies every write transport
# ---------------------------------------------------------------------------


class TestGroupAProtectedInfraDeniesEveryTransport:
    """INV-4: the protected-infrastructure hard floor is transport-independent."""

    @pytest.mark.parametrize(
        "tool_name,build", WRITE_TRANSPORTS, ids=WRITE_TRANSPORT_IDS
    )
    def test_protected_hook_file_is_denied(self, tool_name, build):
        decision, reason = _run_hook(
            UPT_HOOK, tool_name, build(PROTECTED_HOOK, BIG_CHANGE)
        )
        assert decision in BLOCKED_DECISIONS, (
            f"{tool_name} was ALLOWED against protected {PROTECTED_HOOK} "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )

    @pytest.mark.parametrize(
        "tool_name,build", WRITE_TRANSPORTS, ids=WRITE_TRANSPORT_IDS
    )
    def test_protected_lib_file_is_denied(self, tool_name, build):
        decision, reason = _run_hook(
            UPT_HOOK, tool_name, build(PROTECTED_LIB, BIG_CHANGE)
        )
        assert decision in BLOCKED_DECISIONS, (
            f"{tool_name} was ALLOWED against protected {PROTECTED_LIB} "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )


# ---------------------------------------------------------------------------
# Group B — INV-4 survives the universal bypass
# ---------------------------------------------------------------------------


class TestGroupBHardFloorSurvivesUniversalBypass:
    """AUTONOMOUS_DEV_BYPASS=1 must NOT unlock protected infrastructure.

    The bypass is activated via the env var rather than by creating a fake
    protected tree: _is_protected_infrastructure() is anchored to the canonical
    repo path, so a synthetic tree would prove nothing. hook_bypass treats the
    env var as equivalent to .claude/.bypass, and this touches no files on disk.
    """

    @pytest.mark.parametrize(
        "tool_name,build", WRITE_TRANSPORTS, ids=WRITE_TRANSPORT_IDS
    )
    def test_bypass_does_not_unlock_protected_infra(self, tool_name, build):
        decision, reason = _run_hook(
            UPT_HOOK,
            tool_name,
            build(PROTECTED_HOOK, BIG_CHANGE),
            env_extra={"AUTONOMOUS_DEV_BYPASS": "1"},
        )
        assert decision in BLOCKED_DECISIONS, (
            f"{tool_name} escaped INV-4 under the universal bypass "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )


# ---------------------------------------------------------------------------
# Group C — negative controls (over-blocking is an explicit failure condition)
# ---------------------------------------------------------------------------


class TestGroupCReadsAreNeverBlocked:
    """Reads must stay unblocked — several of these carry a path argument."""

    @pytest.mark.parametrize(
        "tool_name,tool_input", READONLY_CONTROLS, ids=READONLY_IDS
    )
    def test_readonly_tool_is_not_blocked(self, tool_name, tool_input):
        decision, reason = _run_hook(UPT_HOOK, tool_name, tool_input)
        assert decision not in BLOCKED_DECISIONS, (
            f"{tool_name} was BLOCKED — over-correcting into a gate that blocks "
            f"reads is an explicit failure condition of Issue #1503 "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )


# ---------------------------------------------------------------------------
# Group D — plan_gate denies a large change with no plan, on every transport
# ---------------------------------------------------------------------------


class TestGroupDPlanGateDeniesLargeChange:

    @pytest.mark.parametrize(
        "tool_name,build", WRITE_TRANSPORTS, ids=WRITE_TRANSPORT_IDS
    )
    def test_large_change_without_plan_is_blocked(
        self, tool_name, build, plan_gate_workspace
    ):
        target = str(plan_gate_workspace / "src" / "feature.py")
        decision, reason = _run_hook(
            PLAN_GATE_HOOK, tool_name, build(target, BIG_CHANGE),
            cwd=plan_gate_workspace,
        )
        assert decision in BLOCKED_DECISIONS, (
            f"{tool_name} bypassed the plan gate "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )

    @pytest.mark.parametrize(
        "tool_name,build", CONTENTLESS_WRITE_TRANSPORTS, ids=CONTENTLESS_WRITE_IDS
    )
    def test_contentless_writer_without_plan_is_blocked(
        self, tool_name, build, plan_gate_workspace
    ):
        """A writer with no content argument has no size proxy, so it is gated.

        ``delete_lines(1, 400)`` removes 400 lines while changed_content()
        reports 0 — the line-count exemption cannot see the blast radius, so
        these transports must require a plan.
        """
        target = str(plan_gate_workspace / "src" / "feature.py")
        decision, reason = _run_hook(
            PLAN_GATE_HOOK, tool_name, build(target),
            cwd=plan_gate_workspace,
        )
        assert decision in BLOCKED_DECISIONS, (
            f"{tool_name} carries no content argument yet was auto-exempted by "
            f"the line-count rule — 0 lines of content is not evidence of a "
            f"small change (decision={decision!r}, reason={reason[:200]!r})"
        )


# ---------------------------------------------------------------------------
# Group E — the simple-edit exemption is about the CHANGE, not the TRANSPORT
# ---------------------------------------------------------------------------


class TestGroupEPlanGateSimpleEditExemption:
    """Issue scenario 5. Fails if changed_content() is skipped."""

    @pytest.mark.parametrize(
        "tool_name,build", WRITE_TRANSPORTS, ids=WRITE_TRANSPORT_IDS
    )
    def test_small_change_is_allowed(self, tool_name, build, plan_gate_workspace):
        target = str(plan_gate_workspace / "src" / "feature.py")
        decision, reason = _run_hook(
            PLAN_GATE_HOOK, tool_name, build(target, SMALL_CHANGE),
            cwd=plan_gate_workspace,
        )
        assert decision == "allow", (
            f"{tool_name} was blocked for a <100-line change — the exemption "
            f"must be about the change, not the transport "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )
        assert "simple edit" in reason.lower(), (
            f"{tool_name} was allowed for the wrong reason: {reason[:200]!r}"
        )

    @pytest.mark.parametrize(
        "tool_name,build", CONTENTLESS_WRITE_TRANSPORTS, ids=CONTENTLESS_WRITE_IDS
    )
    def test_contentless_writer_is_not_a_simple_edit(
        self, tool_name, build, plan_gate_workspace
    ):
        """The exemption needs a size proxy; these transports do not have one.

        The three content-bearing MCP writers above keep the exemption. These
        four must NOT be allowed with a "simple edit" reason — that reason
        would be a claim the hook has no evidence for.
        """
        target = str(plan_gate_workspace / "src" / "feature.py")
        decision, reason = _run_hook(
            PLAN_GATE_HOOK, tool_name, build(target),
            cwd=plan_gate_workspace,
        )
        assert "simple edit" not in reason.lower(), (
            f"{tool_name} was granted the simple-edit exemption with no "
            f"content argument to size the change "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )
        assert decision in BLOCKED_DECISIONS, (
            f"{tool_name} must fall through to the plan requirement "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )


# ---------------------------------------------------------------------------
# Group F — doc-file exemption survives the transport change
# ---------------------------------------------------------------------------


class TestGroupFDocFileExemption:

    @pytest.mark.parametrize(
        "tool_name,build", WRITE_TRANSPORTS, ids=WRITE_TRANSPORT_IDS
    )
    def test_doc_file_is_allowed(self, tool_name, build, plan_gate_workspace):
        doc = str(plan_gate_workspace / "README.md")
        decision, reason = _run_hook(
            PLAN_GATE_HOOK, tool_name, build(doc, BIG_CHANGE),
            cwd=plan_gate_workspace,
        )
        assert decision == "allow", (
            f"{tool_name} lost the doc-file exemption "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )
        assert "doc file" in reason.lower(), (
            f"{tool_name} was allowed for the wrong reason: {reason[:200]!r}"
        )


# ---------------------------------------------------------------------------
# Group G — no over-blocking on non-protected targets
# ---------------------------------------------------------------------------


class TestGroupGNonProtectedTargetIsNotBlocked:

    @pytest.mark.parametrize(
        "tool_name,build", WRITE_TRANSPORTS, ids=WRITE_TRANSPORT_IDS
    )
    def test_ordinary_file_is_allowed(self, tool_name, build, plan_gate_workspace):
        ordinary = str(plan_gate_workspace / "src" / "ordinary.py")
        decision, reason = _run_hook(
            UPT_HOOK, tool_name, build(ordinary, SMALL_CHANGE),
            cwd=plan_gate_workspace,
        )
        assert decision not in BLOCKED_DECISIONS, (
            f"{tool_name} was blocked against a NON-protected target — the "
            f"hard floor must not fire here "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )


# ---------------------------------------------------------------------------
# Group H — the documented denial-reason ordering change
# ---------------------------------------------------------------------------


class TestGroupHDenialReasonOrdering:
    """The hard-floor relocation changed which message wins.

    Before Issue #1503, _check_plan_exit_native ran BEFORE the infrastructure
    block, so when both would fire the plan-exit message won. After relocating
    the hard floor above the native-tool fast path, the infrastructure message
    wins. deny stays deny — only the visible reason changes. This test locks
    the new reason so the ordering cannot regress silently.
    """

    @pytest.fixture
    def plan_exited_marker(self):
        marker = REPO_ROOT / ".claude" / "plan_mode_exit.json"
        pre_existing = marker.exists()
        backup = marker.read_text() if pre_existing else None
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"stage": "plan_exited", "timestamp": 0}))
        try:
            yield marker
        finally:
            if backup is not None:
                marker.write_text(backup)
            else:
                marker.unlink(missing_ok=True)

    @pytest.mark.parametrize(
        "tool_name,build", WRITE_TRANSPORTS, ids=WRITE_TRANSPORT_IDS
    )
    def test_infrastructure_reason_wins_over_plan_exit(
        self, tool_name, build, plan_exited_marker
    ):
        decision, reason = _run_hook(
            UPT_HOOK, tool_name, build(PROTECTED_HOOK, BIG_CHANGE)
        )
        assert decision in BLOCKED_DECISIONS, (
            f"{tool_name} was allowed with a plan_exited marker present "
            f"(decision={decision!r})"
        )
        lowered = reason.lower()
        assert "infrastructure" in lowered or "protected path" in lowered, (
            f"{tool_name}: expected the infrastructure-protection reason to win "
            f"over the plan-exit message after the #1503 relocation, got "
            f"{reason[:300]!r}"
        )


# ---------------------------------------------------------------------------
# Group I — stale-install fallback
# ---------------------------------------------------------------------------


class TestGroupIStaleInstallFallback:
    """Without tool_intent, the fallback is the literal FOUR-tuple.

    The fallback must be strictly stronger than the legacy ("Write", "Edit")
    two-tuple at every site and never weaker. It must NOT fail closed to
    "deny" — denying on a missing library would block Read, which is
    catastrophic.
    """

    @staticmethod
    def _run_with_tool_intent_unimportable(tool_name: str, tool_input: dict):
        """Run unified_pre_tool with tool_intent forced to raise ImportError."""
        shim_dir = Path(tempfile.mkdtemp(prefix="issue1503-shim-"))
        # A sitecustomize that installs a meta-path finder rejecting
        # "tool_intent". The hook loads tool_intent via
        # spec_from_file_location, so we make exec_module raise instead.
        (shim_dir / "sitecustomize.py").write_text(
            "import importlib.util as _ilu\n"
            "_orig = _ilu.spec_from_file_location\n"
            "def _patched(name, location=None, *a, **kw):\n"
            "    if name == 'tool_intent':\n"
            "        raise ImportError('simulated stale install (#1503)')\n"
            "    return _orig(name, location, *a, **kw)\n"
            "_ilu.spec_from_file_location = _patched\n"
        )
        env_extra = {
            "PYTHONPATH": str(shim_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")
        }
        return _run_hook(UPT_HOOK, tool_name, tool_input, env_extra=env_extra)

    @pytest.mark.parametrize("tool_name", ["MultiEdit", "NotebookEdit"])
    def test_four_tuple_fallback_still_denies(self, tool_name):
        build = dict(WRITE_TRANSPORTS)[tool_name]
        decision, reason = self._run_with_tool_intent_unimportable(
            tool_name, build(PROTECTED_HOOK, BIG_CHANGE)
        )
        assert decision in BLOCKED_DECISIONS, (
            f"{tool_name} escaped the hard floor under the stale-install "
            f"fallback (decision={decision!r}, reason={reason[:200]!r})"
        )

    @pytest.mark.parametrize("tool_name", ["Write", "Edit"])
    def test_native_pair_still_denies_under_fallback(self, tool_name):
        build = dict(WRITE_TRANSPORTS)[tool_name]
        decision, _reason = self._run_with_tool_intent_unimportable(
            tool_name, build(PROTECTED_HOOK, BIG_CHANGE)
        )
        assert decision in BLOCKED_DECISIONS

    def test_fallback_does_not_block_reads(self):
        """Fail-open on reads: a missing library must never deny a Read."""
        decision, reason = self._run_with_tool_intent_unimportable(
            "Read", {"file_path": PROTECTED_HOOK}
        )
        assert decision not in BLOCKED_DECISIONS, (
            f"Read was BLOCKED under the stale-install fallback — the fallback "
            f"must not fail closed to deny (decision={decision!r}, "
            f"reason={reason[:200]!r})"
        )


# ---------------------------------------------------------------------------
# Group J — forged content key cannot restore the simple-edit exemption (F5)
# ---------------------------------------------------------------------------

# Security finding F5 (#1503 re-audit). ``_has_size_proxy`` originally decided
# purely on key PRESENCE, and the PreToolUse hook sees ``tool_input`` straight
# from the model's tool-call arguments — BEFORE the MCP server validates them
# against its own schema. So appending a throwaway ``content: ""`` to a
# ``safe_delete_symbol`` call forged the simple-edit exemption and walked a
# whole-symbol deletion past the plan gate. Rejecting these tools by NAME,
# before any key inspection, is what makes the forgery impossible — the same
# reason ``replace_in_files`` was already immune.
FORGED_CONTENT_PAYLOADS = [
    (
        "mcp__serena__rename_symbol",
        "content",
        lambda p: {
            "relative_path": p,
            "name_path_pattern": "main",
            "new_name": "renamed_main",
            "content": "",
        },
    ),
    (
        "mcp__serena__rename_symbol",
        "body",
        lambda p: {
            "relative_path": p,
            "name_path_pattern": "main",
            "new_name": "renamed_main",
            "body": "x",
        },
    ),
    (
        "mcp__serena__safe_delete_symbol",
        "content",
        lambda p: {
            "relative_path": p,
            "name_path_pattern": "main",
            "content": "",
        },
    ),
    (
        "mcp__serena__safe_delete_symbol",
        "body",
        lambda p: {
            "relative_path": p,
            "name_path_pattern": "main",
            "body": "x",
        },
    ),
    (
        "mcp__serena__delete_lines",
        "content",
        lambda p: {
            "relative_path": p,
            "start_line": 1,
            "end_line": 400,
            "content": "",
        },
    ),
    (
        "mcp__serena__delete_lines",
        "body",
        lambda p: {
            "relative_path": p,
            "start_line": 1,
            "end_line": 400,
            "body": "x",
        },
    ),
]
FORGED_CONTENT_IDS = [f"{name}-forged-{key}" for name, key, _ in FORGED_CONTENT_PAYLOADS]


class TestGroupJForgedContentKey:
    """F5: a throwaway content key must not buy back the exemption."""

    @pytest.mark.parametrize(
        "tool_name,forged_key,build",
        FORGED_CONTENT_PAYLOADS,
        ids=FORGED_CONTENT_IDS,
    )
    def test_forged_content_key_does_not_restore_exemption(
        self, tool_name, forged_key, build, plan_gate_workspace
    ):
        """A content key the real schema never declares proves nothing.

        ``delete_lines(1, 400)`` still removes 400 lines when a bogus
        ``content: ""`` rides along; the hook has no evidence the change is
        small, so it must fall through to the plan requirement.
        """
        target = str(plan_gate_workspace / "src" / "feature.py")
        decision, reason = _run_hook(
            PLAN_GATE_HOOK,
            tool_name,
            build(target),
            cwd=plan_gate_workspace,
        )
        assert "simple edit" not in reason.lower(), (
            f"{tool_name} forged the simple-edit exemption with a throwaway "
            f"{forged_key!r} key its real schema never declares (F5) "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )
        assert decision in BLOCKED_DECISIONS, (
            f"{tool_name} with a forged {forged_key!r} key bypassed the plan "
            f"gate — the rejection must be by tool NAME, before any key "
            f"inspection (decision={decision!r}, reason={reason[:200]!r})"
        )

    def test_genuine_content_bearing_writer_keeps_exemption(self, plan_gate_workspace):
        """Negative control: the fix must not gate honest content-bearing writers.

        ``replace_symbol_body`` DOES declare ``body`` in its real schema, so a
        genuinely small body is genuine evidence of a small change and keeps
        the exemption. Over-correcting into "gate every MCP writer" is an
        explicit failure condition.
        """
        target = str(plan_gate_workspace / "src" / "feature.py")
        decision, reason = _run_hook(
            PLAN_GATE_HOOK,
            "mcp__serena__replace_symbol_body",
            {"relative_path": target, "name_path": "main", "body": SMALL_CHANGE},
            cwd=plan_gate_workspace,
        )
        assert decision == "allow", (
            f"replace_symbol_body lost the simple-edit exemption for a genuine "
            f"<100-line body — the F5 fix must reject by NAME only, not gate "
            f"every MCP writer (decision={decision!r}, reason={reason[:200]!r})"
        )
        assert "simple edit" in reason.lower(), (
            f"replace_symbol_body was allowed for the wrong reason: {reason[:200]!r}"
        )


# ---------------------------------------------------------------------------
# Group K — Bash semantics are UNCHANGED by the transport widening
# ---------------------------------------------------------------------------


class TestGroupKBashSemanticsUnchanged:
    """Issue #1503 widened the hard floor for MultiEdit / NotebookEdit / MCP
    editors — transports that previously escaped it. It must NOT have changed
    Bash.

    Before #1503 the relocated hard floor guarded on
    ``tool_name in ("Write", "Edit")``, which is False for Bash, so the block
    never evaluated a Bash command. Bash is covered separately by
    ``_check_bash_infra_writes``, whose semantics are deliberately looser: an
    active-pipeline implementer MAY use ``sed -i`` / ``tee`` on a protected
    path. Widening the guard to ``is_write()`` silently routed Bash through the
    stricter #1296 sentinel check and broke
    ``test_bash_write_to_protected_path_allowed_when_pipeline_active``.

    These two cases pin BOTH ends of the Bash behaviour so a future widening
    cannot tighten one end without tripping the other.
    """

    def test_bash_semantics_unchanged_by_transport_widening(self):
        """Active-pipeline implementer ``sed -i`` on protected infra: ALLOWED.

        Mirrors the scenario in
        ``tests/unit/hooks/test_infrastructure_protection.py::
        TestBashInfrastructureProtection::
        test_bash_write_to_protected_path_allowed_when_pipeline_active``,
        driven through the real hook via subprocess.
        """
        decision, reason = _run_hook(
            UPT_HOOK,
            "Bash",
            {"command": f"sed -i 's/old/new/g' {PROTECTED_HOOK}"},
            env_extra={"CLAUDE_AGENT_NAME": "implementer"},
        )
        assert decision not in BLOCKED_DECISIONS, (
            f"Bash write to protected infra was BLOCKED for an active-pipeline "
            f"implementer. Issue #1503 widened the hard floor for MultiEdit / "
            f"NotebookEdit / MCP editors ONLY — Bash keeps its own dedicated "
            f"path in _check_bash_infra_writes with looser semantics "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )

    def test_bash_write_to_protected_infra_still_denied_without_pipeline(self):
        """Negative control: Bash's own gate must still fire when inactive.

        Restoring Bash to its pre-#1503 path must not degrade into "Bash is
        exempt". ``_check_bash_infra_writes`` still denies when no pipeline is
        active.
        """
        decision, reason = _run_hook(
            UPT_HOOK,
            "Bash",
            {"command": f"sed -i 's/old/new/g' {PROTECTED_HOOK}"},
            env_extra={
                "CLAUDE_AGENT_NAME": "",
                "PIPELINE_STATE_FILE": "/tmp/nonexistent_issue1503_state.json",
            },
        )
        assert decision in BLOCKED_DECISIONS, (
            f"Bash write to protected infra was ALLOWED with no active "
            f"pipeline — _check_bash_infra_writes must still deny "
            f"(decision={decision!r}, reason={reason[:200]!r})"
        )
        assert "BLOCKED" in reason, (
            f"Bash denial came from the wrong gate: {reason[:200]!r}"
        )

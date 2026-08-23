"""Enforcement tests for the context-file guard (``validate_claude_md_size.py``).

Issue #1639. The hook existed, was correct, and did nothing: its own docstring
declared it "NON-BLOCKING warning-only ... always exits 0", it was registered
in no settings file, and it never looked at ``~/.claude/CLAUDE.md`` — the one
context file that loads in *every* repo.

A guard is unproven until watched REFUSING and PERMITTING. These are the six
arms, plus the negative controls that show the refusal is scoped to a class
rather than to the one instance that prompted it:

1. Refuses a file over the hard ceiling, naming file, count, limit and action.
2. Warns but PERMITS a file over target and under ceiling.
3. Permits all four files at the sizes measured the day this landed
   (70 / 151 / 127 / 159) — the arm that proves it lands green.
4. Refuses a local section that restates a global one.
5. Permits a genuinely repo-specific local section — the correct residue
   after deduplication — which must NOT be flagged.
6. Permits when the global file is absent (a consumer repo may have none).

Arms 3 and 5 carry the most weight: a checker that flags everything is as
useless as one that flags nothing, and this one is seen on every turn.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# tests/unit/hooks/test_*.py -> hooks -> unit -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
HOOK_PATH = HOOK_DIR / "validate_claude_md_size.py"
TEMPLATES_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "templates"

sys.path.insert(0, str(HOOK_DIR))

import validate_claude_md_size as hook  # noqa: E402  (path set up above)


# ---------------------------------------------------------------------------
# Fixture text — verbatim copies, so these tests are deterministic on any
# machine including CI, where ~/.claude/CLAUDE.md does not exist.
# ---------------------------------------------------------------------------

#: The real global rule, copied from ``~/.claude/CLAUDE.md`` on 2026-08-23.
GLOBAL_SERENA_SECTION = """\
# Serena for dependencies, grep for strings

**"Who depends on this?" is a symbol question — use Serena** (`find_referencing_symbols`, `find_symbol`, call hierarchy). Zero references means dead code; grep cannot tell you that.

**"Where does this string appear?" is a text question — use grep** (markdown commands, JSON settings, config, prose). Those aren't symbols.

Using grep for the first question gives confidently wrong answers: it can't see past name shape (a kebab-case pattern misses single-word names), and it can't tell a symbol reference from a string literal (a role label counted as 21 dependencies). Both happened in one session, against a rule that was already written down.
"""

#: The 9-line duplicate as it stood in this repo's CLAUDE.md before commit
#: 120cbb04 cut it by hand. This is the real instance the detector exists for.
LOCAL_CODE_NAV_DUPLICATE = """\
## Code Navigation (LSP > grep when available)

**When the Serena LSP MCP is configured (`.mcp.json` has a `serena` server; Issue #1451), prefer its symbol tools over `grep` for anything about code STRUCTURE:**
- `find_symbol` / go-to-definition — where a function/class is defined
- `find_referencing_symbols` / find-references — **who calls this** (a symbol with **zero references is a stale, unconnected/dead function** — grep cannot tell you this reliably, it matches text not symbol bindings)
- call hierarchy (incoming/outgoing calls) — real **dependency** chains, not text guesses
- `get_symbols_overview` / document-symbol — a file's structure

Use `grep`/`Glob` only for text patterns, file names, comments, strings, and single-file reads. LSP answers are always-fresh (live-queried, no index to go stale). This directly improves dependency understanding and dead-code detection (feeds `/refactor --code`, `/sweep`). If no Serena server is configured, fall back to grep.
"""

#: The correct residue after deduplication — the section that is in the repo
#: CLAUDE.md today. It defers to the global rule and adds only what is
#: repo-specific. This MUST NOT be flagged.
LOCAL_CODE_NAV_RESIDUE = """\
## Code Navigation

Serena LSP is configured here (`.mcp.json`, #1451) — the global "Serena for dependencies, grep for strings" rule applies. Repo-specific: dead-code detection feeds `/refactor --code` and `/sweep`. The hook loads `lib/` via `importlib`, which LSP cannot follow, so hook call sites need grep and the disagreement must be named, not silently resolved.
"""

#: A SECOND global rule, used to build a plant of a DIFFERENT SHAPE from the
#: reproducer above — so the guard is shown to cover a class, not an instance.
GLOBAL_DURABLE_SECTION = """\
# Durable by default

Everything we build defaults to durable — solve the class, not the instance. Never fix a symptom by narrowing scope (allowlist entry, skip-here, repo-only guard); that moves the failure, it doesn't fix it. Enforce it by construction where you can: one sanctioned path + a guard that fails the build when the raw primitive returns. Every fix ships a regression test that fails before it and passes after — fix once, fix properly.
"""

#: A restatement of GLOBAL_DURABLE_SECTION: same heading words, reworded body.
LOCAL_DURABLE_DUPLICATE = """\
## Durable by default

Solve the class, never the instance. Do not fix a symptom by narrowing scope — an allowlist entry or a repo-only guard moves the failure, it does not fix it. Enforce by construction: one sanctioned path plus a guard that fails the build when the raw primitive returns. Every fix ships a regression test that fails before and passes after.
"""

#: Heading overlap WITHOUT body overlap. The conjunction must refuse to flag.
LOCAL_SAME_HEADING_DIFFERENT_TOPIC = """\
## Durable by default

Nightly backups run at 0300 UTC to the offsite bucket; retention is 30 days. Restore drills happen quarterly and the runbook lives beside the terraform module.
"""

#: Body overlap WITHOUT heading overlap. The conjunction must refuse to flag.
LOCAL_SAME_TOPIC_DIFFERENT_HEADING = """\
## Release checklist

Solve the class, never the instance. Do not fix a symptom by narrowing scope — an allowlist entry or a repo-only guard moves the failure, it does not fix it. Enforce by construction: one sanctioned path plus a guard that fails the build.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_lines(path: Path, line_count: int) -> Path:
    """Create ``path`` with exactly ``line_count`` lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"line {i}" for i in range(line_count)))
    return path


def _isolated_repo(tmp_path: Path) -> Path:
    """Build a tmp dir that ``get_repo_root`` will resolve to."""
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _run_hook(cwd: Path, home: Path, payload: dict | None) -> subprocess.CompletedProcess:
    """Invoke the hook as a real subprocess, the way Claude Code does.

    Args:
        cwd: Working directory for the subprocess.
        home: Value for ``$HOME`` — controls ``~/.claude/CLAUDE.md``.
        payload: Hook payload for stdin, or None for a bare CLI invocation.

    Returns:
        The completed process.
    """
    env = dict(os.environ)
    env["HOME"] = str(home)
    env.pop("AUTONOMOUS_DEV_BYPASS", None)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        cwd=str(cwd),
        env=env,
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True,
        text=True,
        timeout=30,
    )


def _decision(result: subprocess.CompletedProcess) -> dict | None:
    """Parse the hook's stdout JSON decision, if it emitted one."""
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------------------
# ARM 1 — refuses a file over the hard ceiling
# ---------------------------------------------------------------------------


class TestArm1RefusesOverCeiling:
    """The guard watched REFUSING."""

    def test_claude_md_over_ceiling_blocks(self, tmp_path: Path) -> None:
        """CLAUDE.md at 400 lines (ceiling 300) must produce a block finding."""
        repo = _isolated_repo(tmp_path)
        _write_lines(repo / "CLAUDE.md", 400)
        findings = hook.collect_size_findings(repo)
        blocking = [f for f in findings if f.severity == hook.BLOCK]
        assert len(blocking) == 1, f"expected one block finding, got {findings}"

    def test_block_message_names_file_count_limit_and_action(self, tmp_path: Path) -> None:
        """Stick+carrot: the refusal names WHAT and WHAT NEXT, not just the fact."""
        repo = _isolated_repo(tmp_path)
        _write_lines(repo / "CLAUDE.md", 400)
        message = [
            f.message for f in hook.collect_size_findings(repo) if f.severity == hook.BLOCK
        ][0]
        assert "CLAUDE.md" in message
        assert "400" in message, "message must name the measured count"
        assert str(hook.BLOCK_LINES) in message, "message must name the ceiling"
        assert str(hook.MAX_LINES) in message, "message must name the target"
        assert "REQUIRED NEXT ACTION" in message

    @pytest.mark.parametrize(
        "relative_path,line_count,ceiling",
        [
            ("CLAUDE.md", 301, 300),
            (".claude/PROJECT.md", 226, 225),
        ],
    )
    def test_one_line_past_ceiling_blocks(
        self, tmp_path: Path, relative_path: str, line_count: int, ceiling: int
    ) -> None:
        """Boundary: ceiling+1 refuses. Tests the boundary, not a round number."""
        repo = _isolated_repo(tmp_path)
        _write_lines(repo / relative_path, line_count)
        severities = {f.severity for f in hook.collect_size_findings(repo)}
        assert hook.BLOCK in severities, f"{relative_path} at {ceiling + 1} must block"

    def test_exactly_at_ceiling_does_not_block(self, tmp_path: Path) -> None:
        """Boundary, other side: exactly at the ceiling warns, does not refuse."""
        repo = _isolated_repo(tmp_path)
        _write_lines(repo / "CLAUDE.md", hook.BLOCK_LINES)
        severities = {f.severity for f in hook.collect_size_findings(repo)}
        assert severities == {hook.WARN}

    def test_subprocess_emits_block_decision_json(self, tmp_path: Path) -> None:
        """Verify the EXECUTING copy: run it, read the envelope off stdout."""
        repo = _isolated_repo(tmp_path / "repo")
        home = tmp_path / "home"
        home.mkdir()
        _write_lines(repo / "CLAUDE.md", 400)
        result = _run_hook(
            repo,
            home,
            {"tool_name": "Edit", "tool_input": {"file_path": str(repo / "CLAUDE.md")}},
        )
        assert result.returncode == 0, result.stderr
        decision = _decision(result)
        assert decision is not None, f"no decision emitted; stderr={result.stderr}"
        assert decision["decision"] == "block"
        assert "REQUIRED NEXT ACTION" in decision["reason"]


# ---------------------------------------------------------------------------
# ARM 2 — warns but permits between target and ceiling
# ---------------------------------------------------------------------------


class TestArm2WarnsButPermits:
    """The band that advises. An ordinary edit past target must not refuse."""

    @pytest.mark.parametrize("line_count", [201, 250, 300])
    def test_over_target_under_ceiling_warns_only(
        self, tmp_path: Path, line_count: int
    ) -> None:
        repo = _isolated_repo(tmp_path)
        _write_lines(repo / "CLAUDE.md", line_count)
        findings = hook.collect_size_findings(repo)
        assert [f.severity for f in findings] == [hook.WARN]

    def test_subprocess_warns_on_stderr_and_emits_no_decision(self, tmp_path: Path) -> None:
        """Executing copy, permitting arm: stderr carries the warning, stdout is silent."""
        repo = _isolated_repo(tmp_path / "repo")
        home = tmp_path / "home"
        home.mkdir()
        _write_lines(repo / "CLAUDE.md", 250)
        result = _run_hook(
            repo,
            home,
            {"tool_name": "Edit", "tool_input": {"file_path": str(repo / "CLAUDE.md")}},
        )
        assert result.returncode == 0
        assert "WARNING" in result.stderr
        assert _decision(result) is None, f"warn band must not refuse: {result.stdout}"

    def test_warn_band_is_not_empty(self) -> None:
        """The bands must be distinct — a ceiling equal to the target would make
        every warning fatal, which is the design this explicitly rejects."""
        assert hook.BLOCK_LINES > hook.MAX_LINES
        assert hook.BLOCK_PROJECT_LINES > hook.MAX_PROJECT_LINES
        assert hook.BLOCK_MEMORY_LINES > hook.MAX_MEMORY_LINES
        assert hook.BLOCK_GLOBAL_CLAUDE_LINES > hook.MAX_GLOBAL_CLAUDE_LINES


# ---------------------------------------------------------------------------
# ARM 3 — permits today's real sizes (proves it lands green)
# ---------------------------------------------------------------------------

#: Sizes on 2026-08-23. TWO INSTRUMENTS DISAGREE and the disagreement is
#: recorded rather than resolved silently: ``wc -l`` reports 70 / 150 / 127 /
#: 159 (it counts newline characters) while the hook's own ``splitlines()``
#: reports 71 / 151 / 127 / 159 (a final line with no trailing newline is
#: still a line). The two files that differ simply lack a trailing newline.
#: The LARGER figure is used throughout because it is the stronger claim, and
#: both figures are covered by the parametrized band arm below.
TODAYS_SIZES = {
    "CLAUDE.md": 71,
    "global CLAUDE.md": 151,
    "PROJECT.md": 127,
    "MEMORY.md": 159,
}

#: The ``wc -l`` figures, asserted alongside so neither instrument's reading
#: can drift into the block band unnoticed.
TODAYS_SIZES_WC = {
    "CLAUDE.md": 70,
    "global CLAUDE.md": 150,
    "PROJECT.md": 127,
    "MEMORY.md": 159,
}


class TestArm3TodaysSizesPermitted:
    """Lands green and ratchets from a true baseline."""

    def test_all_four_files_at_todays_sizes_produce_no_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _isolated_repo(tmp_path / "repo")
        home = tmp_path / "home"
        _write_lines(repo / "CLAUDE.md", TODAYS_SIZES["CLAUDE.md"])
        _write_lines(repo / ".claude" / "PROJECT.md", TODAYS_SIZES["PROJECT.md"])
        global_md = _write_lines(
            home / ".claude" / "CLAUDE.md", TODAYS_SIZES["global CLAUDE.md"]
        )
        memory_md = _write_lines(home / "memory" / "MEMORY.md", TODAYS_SIZES["MEMORY.md"])

        monkeypatch.setattr(hook, "global_claude_md_path", lambda: global_md)
        monkeypatch.setattr(hook, "derive_memory_path", lambda: memory_md)

        assert hook.collect_size_findings(repo) == []

    @pytest.mark.parametrize(
        "label,line_count",
        sorted(TODAYS_SIZES.items()) + sorted(TODAYS_SIZES_WC.items()),
    )
    def test_each_of_todays_sizes_is_ok_band(self, label: str, line_count: int) -> None:
        limits = {
            "CLAUDE.md": (hook.MAX_LINES, hook.BLOCK_LINES),
            "global CLAUDE.md": (
                hook.MAX_GLOBAL_CLAUDE_LINES,
                hook.BLOCK_GLOBAL_CLAUDE_LINES,
            ),
            "PROJECT.md": (hook.MAX_PROJECT_LINES, hook.BLOCK_PROJECT_LINES),
            "MEMORY.md": (hook.MAX_MEMORY_LINES, hook.BLOCK_MEMORY_LINES),
        }[label]
        assert hook.classify_size(line_count, *limits) == hook.OK, (
            f"{label} at its measured size {line_count} must be in the OK band — "
            "this guard is required to land green, not instantly red."
        )

    def test_live_repo_files_are_permitted(self) -> None:
        """Live data, not a fixture: the real files on this machine must pass.

        Reads whatever ``~/.claude/`` holds here. On CI those files are absent
        and contribute nothing, which is the correct behaviour for a consumer
        repo — the repo files still assert.
        """
        findings = hook.collect_size_findings(REPO_ROOT)
        blocking = [f.message for f in findings if f.severity == hook.BLOCK]
        assert blocking == [], f"live context files must not be over ceiling: {blocking}"


# ---------------------------------------------------------------------------
# ARM 4 — refuses a local section that restates a global one
# ---------------------------------------------------------------------------


class TestArm4RefusesRestatement:
    """The part size cannot see."""

    def test_historical_duplicate_is_flagged(self) -> None:
        """Regression for the real instance: the pre-#1639 Code Navigation
        section restating the global Serena rule."""
        overlaps = hook.find_overlaps(LOCAL_CODE_NAV_DUPLICATE, GLOBAL_SERENA_SECTION)
        assert len(overlaps) == 1, f"expected the duplicate to be flagged, got {overlaps}"
        assert overlaps[0].global_heading.startswith("Serena for dependencies")

    def test_plant_of_a_different_shape_is_flagged(self) -> None:
        """Negative control of a DIFFERENT shape from the reproducer.

        The class covered is "a local section restates a global one", not
        "the Code Navigation section". This plant restates a different global
        rule, with a different heading, in a different vocabulary.
        """
        overlaps = hook.find_overlaps(LOCAL_DURABLE_DUPLICATE, GLOBAL_DURABLE_SECTION)
        assert len(overlaps) == 1, f"expected the plant to be flagged, got {overlaps}"

    def test_restatement_produces_a_blocking_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End to end: a planted duplicate refuses, and names the next action."""
        repo = _isolated_repo(tmp_path / "repo")
        home = tmp_path / "home"
        (repo / "CLAUDE.md").write_text(LOCAL_DURABLE_DUPLICATE)
        global_md = home / ".claude" / "CLAUDE.md"
        global_md.parent.mkdir(parents=True)
        global_md.write_text(GLOBAL_DURABLE_SECTION)

        monkeypatch.setattr(hook, "global_claude_md_path", lambda: global_md)
        findings = hook.collect_overlap_findings(repo)

        assert len(findings) == 1
        assert findings[0].severity == hook.BLOCK
        assert "REQUIRED NEXT ACTION" in findings[0].message
        assert "Durable by default" in findings[0].message

    def test_subprocess_refuses_a_restatement(self, tmp_path: Path) -> None:
        """Executing copy: plant a duplicate, run the hook, read the refusal."""
        repo = _isolated_repo(tmp_path / "repo")
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".claude" / "CLAUDE.md").write_text(GLOBAL_DURABLE_SECTION)
        (repo / "CLAUDE.md").write_text(LOCAL_DURABLE_DUPLICATE)

        result = _run_hook(
            repo,
            home,
            {"tool_name": "Edit", "tool_input": {"file_path": str(repo / "CLAUDE.md")}},
        )
        decision = _decision(result)
        assert decision is not None, f"expected a refusal; stderr={result.stderr}"
        assert decision["decision"] == "block"
        assert "restates the global rule" in decision["reason"]


# ---------------------------------------------------------------------------
# ARM 5 — permits genuinely repo-specific content
# ---------------------------------------------------------------------------


class TestArm5PermitsRepoSpecific:
    """The arm that keeps this from crying wolf on every turn."""

    def test_deduplicated_residue_is_not_flagged(self) -> None:
        """The current ``## Code Navigation`` — the correct residue — must pass.

        It even QUOTES the global heading, which is exactly the shape a naive
        substring or body-overlap rule would flag.
        """
        overlaps = hook.find_overlaps(LOCAL_CODE_NAV_RESIDUE, GLOBAL_SERENA_SECTION)
        assert overlaps == [], f"the deduplicated residue must not be flagged: {overlaps}"

    def test_shared_heading_without_shared_body_is_not_flagged(self) -> None:
        """Half the conjunction is not enough — heading arm alone."""
        overlaps = hook.find_overlaps(
            LOCAL_SAME_HEADING_DIFFERENT_TOPIC, GLOBAL_DURABLE_SECTION
        )
        assert overlaps == []

    def test_shared_body_without_shared_heading_is_not_flagged(self) -> None:
        """Half the conjunction is not enough — body arm alone.

        This is the case that makes the conjunction load-bearing: body overlap
        ALONE ranked four benign pairs of this repo's real CLAUDE.md above the
        one real duplicate.
        """
        overlaps = hook.find_overlaps(
            LOCAL_SAME_TOPIC_DIFFERENT_HEADING, GLOBAL_DURABLE_SECTION
        )
        assert overlaps == []

    def test_live_repo_claude_md_has_no_overlap_findings(self) -> None:
        """Live data: today's real repo CLAUDE.md against today's real global."""
        findings = hook.collect_overlap_findings(REPO_ROOT)
        assert findings == [], f"today's CLAUDE.md must land green: {findings}"

    def test_headings_inside_code_fences_are_not_sections(self) -> None:
        """``# Recent sessions`` inside a ```bash fence is a comment, not a
        heading. The global CLAUDE.md has two such lines and both produced
        spurious sections before fences were stripped."""
        markdown = "# Real\n\nbody text here\n\n```bash\n# Not a heading\necho hi\n```\n"
        headings = [s.heading for s in hook.extract_sections(markdown)]
        assert headings == ["Real"]


# ---------------------------------------------------------------------------
# ARM 6 — permits when the global file is absent
# ---------------------------------------------------------------------------


class TestArm6GlobalFileAbsent:
    """A consumer repo may have no ``~/.claude/CLAUDE.md``. That is not an error."""

    def test_missing_global_produces_no_size_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _isolated_repo(tmp_path / "repo")
        _write_lines(repo / "CLAUDE.md", 50)
        monkeypatch.setattr(
            hook, "global_claude_md_path", lambda: tmp_path / "home" / ".claude" / "CLAUDE.md"
        )
        monkeypatch.setattr(hook, "derive_memory_path", lambda: tmp_path / "nope" / "MEMORY.md")
        assert hook.collect_size_findings(repo) == []

    def test_missing_global_produces_no_overlap_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _isolated_repo(tmp_path / "repo")
        (repo / "CLAUDE.md").write_text(LOCAL_DURABLE_DUPLICATE)
        monkeypatch.setattr(
            hook, "global_claude_md_path", lambda: tmp_path / "home" / ".claude" / "CLAUDE.md"
        )
        assert hook.collect_overlap_findings(repo) == []

    def test_subprocess_with_no_global_file_permits(self, tmp_path: Path) -> None:
        """Executing copy, in a home with no global CLAUDE.md at all."""
        repo = _isolated_repo(tmp_path / "repo")
        home = tmp_path / "home"
        home.mkdir()
        _write_lines(repo / "CLAUDE.md", 60)
        result = _run_hook(
            repo,
            home,
            {"tool_name": "Edit", "tool_input": {"file_path": str(repo / "CLAUDE.md")}},
        )
        assert result.returncode == 0
        assert _decision(result) is None
        assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# Global-file coverage (the file that had no limit)
# ---------------------------------------------------------------------------


class TestGlobalClaudeMdIsChecked:
    """``~/.claude/CLAUDE.md`` loads in EVERY repo and was unchecked."""

    def test_global_over_ceiling_blocks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _isolated_repo(tmp_path / "repo")
        global_md = _write_lines(tmp_path / "home" / ".claude" / "CLAUDE.md", 400)
        monkeypatch.setattr(hook, "global_claude_md_path", lambda: global_md)
        monkeypatch.setattr(hook, "derive_memory_path", lambda: tmp_path / "nope" / "MEMORY.md")
        blocking = [f for f in hook.collect_size_findings(repo) if f.severity == hook.BLOCK]
        assert len(blocking) == 1
        assert "global" in blocking[0].message

    def test_global_over_target_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        global_md = _write_lines(tmp_path / "home" / ".claude" / "CLAUDE.md", 240)
        monkeypatch.setattr(hook, "global_claude_md_path", lambda: global_md)
        count, message = hook.check_global_claude_md_size()
        assert count == 240
        assert "WARNING" in message

    def test_global_warning_does_not_masquerade_as_the_repo_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The two CLAUDE.md files must be distinguishable in the output."""
        global_md = _write_lines(tmp_path / "home" / ".claude" / "CLAUDE.md", 240)
        monkeypatch.setattr(hook, "global_claude_md_path", lambda: global_md)
        _count, message = hook.check_global_claude_md_size()
        assert "CLAUDE.md is" not in message, (
            "the global warning must not read like the repo file's warning"
        )
        assert "~/.claude/CLAUDE.md" in message


# ---------------------------------------------------------------------------
# Trigger scoping — the hook must not fire on unrelated writes
# ---------------------------------------------------------------------------


class TestTriggerScoping:
    """No signal may cry wolf: an unrelated write must pass through silently."""

    def test_unrelated_write_is_ignored_even_when_a_file_is_over_ceiling(
        self, tmp_path: Path
    ) -> None:
        repo = _isolated_repo(tmp_path / "repo")
        home = tmp_path / "home"
        home.mkdir()
        _write_lines(repo / "CLAUDE.md", 400)
        (repo / "somewhere.py").write_text("x = 1\n")

        # Negative control: the unrelated write.
        unrelated = _run_hook(
            repo,
            home,
            {"tool_name": "Edit", "tool_input": {"file_path": str(repo / "somewhere.py")}},
        )
        # Positive control: SAME repo state, SAME over-ceiling file, only the
        # target path differs. Without this arm, "no decision" above is
        # indistinguishable from a hook that cannot refuse at all.
        tracked = _run_hook(
            repo,
            home,
            {"tool_name": "Edit", "tool_input": {"file_path": str(repo / "CLAUDE.md")}},
        )

        assert unrelated.returncode == 0
        assert _decision(unrelated) is None, "an unrelated edit must not be refused"
        assert _decision(tracked) is not None, (
            "positive control failed: the instrument cannot refuse, so the "
            "negative control above proves nothing"
        )

    def test_write_to_a_tracked_file_is_recognised(self, tmp_path: Path) -> None:
        repo = _isolated_repo(tmp_path)
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(repo / "CLAUDE.md")}}
        assert hook.payload_touches_context_file(payload, repo) is True

    def test_write_to_an_untracked_file_is_not_recognised(self, tmp_path: Path) -> None:
        repo = _isolated_repo(tmp_path)
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(repo / "README.md")}}
        assert hook.payload_touches_context_file(payload, repo) is False

    def test_project_md_is_tracked(self, tmp_path: Path) -> None:
        repo = _isolated_repo(tmp_path)
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(repo / ".claude" / "PROJECT.md")},
        }
        assert hook.payload_touches_context_file(payload, repo) is True

    @pytest.mark.parametrize(
        "stdin_text",
        [
            "not json at all {{{",
            '{"tool_name": "Edit", "tool_input": "a string, not a dict"}',
            '["a", "list"]',
        ],
    )
    def test_unparsable_payload_does_nothing(self, tmp_path: Path, stdin_text: str) -> None:
        """Stdin present but unreadable = a write we cannot attribute.

        Doing nothing is the honest response. Falling back to "check
        everything" would run the full gate on an unattributable write, which
        is how a signal starts crying wolf. Note the repo here IS over ceiling,
        so a fallback would be visible.
        """
        repo = _isolated_repo(tmp_path / "repo")
        home = tmp_path / "home"
        home.mkdir()
        _write_lines(repo / "CLAUDE.md", 400)

        env = dict(os.environ)
        env["HOME"] = str(home)
        env.pop("AUTONOMOUS_DEV_BYPASS", None)
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            cwd=str(repo),
            env=env,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert _decision(result) is None, f"unattributable write must not refuse: {result.stdout}"
        assert "Traceback" not in result.stderr

    def test_bare_cli_invocation_checks_everything(self, tmp_path: Path) -> None:
        """No payload on stdin -> run every check (git pre-commit style use)."""
        repo = _isolated_repo(tmp_path / "repo")
        home = tmp_path / "home"
        home.mkdir()
        _write_lines(repo / "CLAUDE.md", 400)
        result = _run_hook(repo, home, None)
        decision = _decision(result)
        assert decision is not None and decision["decision"] == "block"


# ---------------------------------------------------------------------------
# Registration — parsed from the settings files, not read off a diff
# ---------------------------------------------------------------------------

#: Templates that carry a ``hooks`` block. ``settings.local.json`` is excluded
#: BY DESIGN — its own ``_comment`` records that hooks there double-fire
#: (Issue #1183), so registering in it would be a defect, not coverage.
HOOK_CARRYING_TEMPLATES = (
    "settings.default.json",
    "settings.granular-bash.json",
    "settings.permission-batching.json",
    "settings.strict-mode.json",
    "settings.autonomous-dev.json",
)

LIFECYCLE_EVENTS = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "UserPromptSubmit",
        "SessionStart",
        "Stop",
        "SubagentStop",
        "PreCompact",
        "PostCompact",
        "Notification",
        "TaskCompleted",
    }
)


def _registrations(settings: dict, hook_filename: str) -> list:
    """Every (event, matcher, timeout) this hook is registered under."""
    found = []
    for event, entries in (settings.get("hooks") or {}).items():
        if event not in LIFECYCLE_EVENTS or not isinstance(entries, list):
            continue
        for entry in entries:
            for command_spec in entry.get("hooks", []):
                if hook_filename in command_spec.get("command", ""):
                    found.append(
                        (event, entry.get("matcher"), command_spec.get("timeout"))
                    )
    return found


class TestRegistration:
    """An unregistered hook is the defect being fixed (#1637, #1612)."""

    @pytest.mark.parametrize("template_name", HOOK_CARRYING_TEMPLATES)
    def test_registered_in_every_shipped_template(self, template_name: str) -> None:
        settings = json.loads((TEMPLATES_DIR / template_name).read_text())
        registrations = _registrations(settings, "validate_claude_md_size.py")
        assert registrations, (
            f"{template_name} does not register validate_claude_md_size.py under any "
            "lifecycle event. Consumer repos need this (#1636); an unregistered hook "
            "is the defect being fixed."
        )

    @pytest.mark.parametrize("template_name", HOOK_CARRYING_TEMPLATES)
    def test_registered_on_a_write_event_with_a_sane_timeout(
        self, template_name: str
    ) -> None:
        settings = json.loads((TEMPLATES_DIR / template_name).read_text())
        for event, matcher, timeout in _registrations(settings, "validate_claude_md_size.py"):
            assert event == "PostToolUse", f"{template_name}: unexpected event {event}"
            assert "Write" in (matcher or ""), f"{template_name}: matcher {matcher!r}"
            assert isinstance(timeout, int) and 3 <= timeout <= 5, (
                f"{template_name}: timeout {timeout} is out of step with its siblings (3-5s)"
            )

    def test_not_registered_in_settings_local_template(self) -> None:
        """Hooks in settings.local.json double-fire (#1183). Lock the exclusion."""
        settings = json.loads((TEMPLATES_DIR / "settings.local.json").read_text())
        assert _registrations(settings, "validate_claude_md_size.py") == []

    def test_sidecar_declares_the_same_registration(self) -> None:
        """The ``.hook.json`` sidecar must not say ``orphan`` any more."""
        sidecar = json.loads((HOOK_DIR / "validate_claude_md_size.hook.json").read_text())
        assert sidecar["type"] == "lifecycle"
        assert sidecar["active"] is True
        events = {r["event"] for r in sidecar["registrations"]}
        assert events == {"PostToolUse"}

    def test_repo_settings_registers_it_when_present(self) -> None:
        """``.claude/`` is gitignored, so this file exists locally and not in CI.

        Absent, this arm is vacuous and says so; present, it must be registered
        — a template-only registration would leave THIS repo unguarded.
        """
        repo_settings = REPO_ROOT / ".claude" / "settings.json"
        if not repo_settings.exists():
            return
        settings = json.loads(repo_settings.read_text())
        assert _registrations(settings, "validate_claude_md_size.py"), (
            ".claude/settings.json exists but does not register the guard"
        )


# ---------------------------------------------------------------------------
# Refusal recording — INV-1: a refusal that is not recorded is not evidence
# ---------------------------------------------------------------------------


class TestRefusalIsRecorded:
    """The block travels through the repo's canonical refusal sink."""

    def test_sole_emitter_is_wrapped_by_the_sanctioned_sink(self) -> None:
        source = HOOK_PATH.read_text()
        assert "from hook_telemetry import block_event_decorator" in source
        assert "@block_event_decorator(" in source

    def test_emitter_prints_the_postooluse_block_shape(self, capsys) -> None:
        hook._output_decision("block", "because reasons")
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["decision"] == "block"
        assert payload["reason"] == "because reasons"

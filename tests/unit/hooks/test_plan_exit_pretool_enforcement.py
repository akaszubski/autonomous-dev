"""Unit tests for plan-exit PreToolUse enforcement (Issue #926).

Covers the 21 acceptance criteria from issue-926-plan-exit-pretool.md.
These tests exercise `_check_plan_exit_native` and `_check_plan_exit_mcp`
directly at the unit level (no subprocess). They supersede
test_plan_mode_enforcement.py, which tested the old UserPromptSubmit gate.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path for direct import
HOOKS_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import unified_pre_tool  # noqa: E402
from unified_pre_tool import (  # noqa: E402
    _PLAN_EXIT_MARKER_PATH,
    _PLAN_EXIT_STALE_MINUTES,
    _PLAN_EXIT_DENY_REASON,
    _bash_command_on_allowlist,
    _check_plan_exit_mcp,
    _check_plan_exit_native,
    _read_plan_exit_marker,
    _ti_mcp_read_tools,
)


@pytest.fixture(autouse=True)
def _force_in_adev_project(monkeypatch):
    """Issue #938: existing tests assume in-project context.

    The scope guard added in #938 short-circuits the gate when cwd is not
    an autonomous-dev repo (tmp_path is not). Patch the detector wrapper
    to True so legacy enforcement tests keep exercising in-project
    behavior. Scope/escape variants are covered separately in the
    TestScopeCheckIntegration class below.
    """
    monkeypatch.setattr(
        unified_pre_tool, "_is_adev_project_fn", lambda: True
    )
    for var in (
        "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW",
        "AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT",
    ):
        monkeypatch.delenv(var, raising=False)


def _write_marker(
    tmp_path: Path,
    *,
    age_minutes: float = 0,
    stage: str = "plan_exited",
    include_stage: bool = True,
) -> Path:
    """Write a plan mode exit marker file for testing.

    Args:
        tmp_path: Temp directory acting as cwd.
        age_minutes: How many minutes old the marker should be.
        stage: The stage field value.
        include_stage: Whether to include the stage field at all.

    Returns:
        Path to the created marker file.
    """
    marker_path = tmp_path / _PLAN_EXIT_MARKER_PATH
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
    marker_data: dict = {
        "timestamp": ts.isoformat(),
        "session_id": "test-session",
    }
    if include_stage:
        marker_data["stage"] = stage
    marker_path.write_text(json.dumps(marker_data))
    return marker_path


# ============================================================================
# No-marker: no enforcement
# ============================================================================


class TestPlanExitNoMarker:
    """No marker → no enforcement (pass through)."""

    def test_no_marker_allows_any_tool(self, tmp_path: Path):
        """With no marker file, all tools should pass through."""
        with patch("os.getcwd", return_value=str(tmp_path)):
            assert _check_plan_exit_native("Write", {"file_path": "foo.py"}) is None
            assert _check_plan_exit_native("Bash", {"command": "rm -rf /"}) is None
            assert _check_plan_exit_native("Task", {"subagent_type": "implementer"}) is None
            assert _check_plan_exit_mcp("mcp__ms365__send-mail") is None


# ============================================================================
# plan_exited: native tools
# ============================================================================


class TestPlanExitedNativeTools:
    """stage=plan_exited state matrix for native tools (ACs #1-8)."""

    def test_plan_exited_blocks_write(self, tmp_path: Path):
        """AC #1: Write denied at plan_exited."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Write", {"file_path": "foo.py", "content": "x"})
        assert result is not None
        assert result[0] == "deny"
        assert result[1] == _PLAN_EXIT_DENY_REASON

    def test_plan_exited_blocks_edit(self, tmp_path: Path):
        """AC #1: Edit denied at plan_exited."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Edit", {"file_path": "foo.py"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_blocks_notebook_edit(self, tmp_path: Path):
        """AC #1: NotebookEdit denied at plan_exited."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("NotebookEdit", {"notebook_path": "x.ipynb"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_allows_read(self, tmp_path: Path):
        """Read falls through at plan_exited (inspection allowed)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Read", {"file_path": "foo.py"})
        assert result is None

    def test_plan_exited_allows_glob(self, tmp_path: Path):
        """Glob falls through at plan_exited."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Glob", {"pattern": "**/*.py"})
        assert result is None

    def test_plan_exited_allows_grep(self, tmp_path: Path):
        """Grep falls through at plan_exited."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Grep", {"pattern": "foo"})
        assert result is None

    def test_plan_exited_allows_task_plan_critic(self, tmp_path: Path):
        """AC #2: Task(plan-critic) falls through at plan_exited."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Task", {"subagent_type": "plan-critic"})
        assert result is None

    def test_plan_exited_blocks_task_implementer(self, tmp_path: Path):
        """AC #3: Task(implementer) denied at plan_exited."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Task", {"subagent_type": "implementer"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_blocks_agent_implementer(self, tmp_path: Path):
        """Agent(implementer) denied at plan_exited (Agent == Task)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Agent", {"subagent_type": "implementer"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_allows_bash_git_status(self, tmp_path: Path):
        """AC #4: Bash(git status) falls through at plan_exited."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "git status"})
        assert result is None

    def test_plan_exited_allows_bash_gh_issue_view(self, tmp_path: Path):
        """Bash(gh issue view) falls through (3-token allowlist)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "gh issue view 123"})
        assert result is None

    def test_plan_exited_allows_bash_ls(self, tmp_path: Path):
        """Bash(ls) falls through (1-token allowlist)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "ls -la"})
        assert result is None

    def test_plan_exited_blocks_bash_gh_issue_create(self, tmp_path: Path):
        """AC #5: Bash(gh issue create ...) denied at plan_exited with canonical reason."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native(
                "Bash",
                {"command": "gh issue create --title foo --body bar"},
            )
        assert result is not None
        assert result[0] == "deny"
        # Issue #938: deny reason advertises env-var escape hatch.
        assert result[1] == _PLAN_EXIT_DENY_REASON
        assert "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW" in _PLAN_EXIT_DENY_REASON

    def test_plan_exited_blocks_bash_mkdir(self, tmp_path: Path):
        """AC #6: Bash(mkdir foo) denied at plan_exited (mkdir not on allowlist)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "mkdir foo"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_blocks_bash_find_with_delete(self, tmp_path: Path):
        """AC #7: Bash(find . -delete) denied at plan_exited (find not on allowlist)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "find . -delete"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_blocks_bash_semicolon_injection(self, tmp_path: Path):
        """AC #8: Bash(ls; rm -rf /tmp/x) denied at plan_exited (injection)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "ls; rm -rf /tmp/x"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_blocks_bash_pipe_injection(self, tmp_path: Path):
        """AC #8: Bash(ls | grep x) denied at plan_exited (injection via pipe)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "ls | grep foo"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_blocks_bash_cmdsub_injection(self, tmp_path: Path):
        """AC #8: Bash(ls `pwd`) denied at plan_exited (command substitution)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "ls `pwd`"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_blocks_bash_dollarsub_injection(self, tmp_path: Path):
        """Bash(ls $(pwd)) denied at plan_exited (dollar-command substitution)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "ls $(pwd)"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_blocks_bash_logical_and(self, tmp_path: Path):
        """Bash(ls && rm -rf /) denied (&& injection)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "ls && whoami"})
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_deny_has_system_message(self, tmp_path: Path):
        """Deny decisions include a systemMessage with user-visible guidance."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert result is not None
        _, _, system_msg = result
        assert "plan-critic" in system_msg.lower()
        assert "--skip-review" in system_msg


# ============================================================================
# plan_exited: MCP tools
# ============================================================================


class TestPlanExitedMCP:
    """stage=plan_exited state matrix for MCP tools (ACs #9-11, #19)."""

    def test_plan_exited_blocks_mcp_send_mail(self, tmp_path: Path):
        """AC #9: MCP send-mail denied at plan_exited."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_mcp("mcp__ms365__send-mail")
        assert result is not None
        assert result[0] == "deny"
        assert result[1] == _PLAN_EXIT_DENY_REASON

    def test_plan_exited_allows_mcp_gmail_list_drafts(self, tmp_path: Path):
        """AC #10: mcp__claude_ai_Gmail__list_drafts falls through (explicit allowlist)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_mcp("mcp__claude_ai_Gmail__list_drafts")
        assert result is None

    def test_plan_exited_blocks_mcp_find_and_replace_heuristic_false_positive(self, tmp_path: Path):
        """AC #11: an UNREGISTERED, write-sounding MCP tool is denied at plan_exited.

        The payload is required, and that is the point. When this test was
        written the gate matched tool NAMES against a structural regex, so a
        bare name was enough to trigger a deny. Issue #1503 deliberately
        removed that regex (see unified_pre_tool.py:1339-1341, which records
        ``find_and_replace`` as the canonical example of why name heuristics
        are forbidden: it contains "find" but is a write). The AC is now
        enforced by the ARGUMENT-SHAPE half of tool_intent's classifier — a
        PATH key plus a CONTENT key means the tool writes, whatever it is
        called and whichever server it comes from.

        A shape rule can only see a shape, so the input must carry one. The
        no-payload form this test used to send is unreachable in production:
        ``_check_plan_exit_mcp`` has exactly one production call site
        (unified_pre_tool.py:9160) and it always forwards ``tool_input``.
        The payload below is what that call site would actually deliver.

        Controls for this assertion live in the three tests immediately
        below: a registered writer that must still deny, a reader that must
        still allow, and the mcp__searxng__search false positive.
        """
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_mcp(
                "mcp__foo__find_and_replace",
                {"relative_path": "src/app.py", "repl": "new_value"},
            )
        assert result is not None, (
            "AC #11: an unregistered MCP tool carrying both a path and content "
            "must be denied at plan_exited — it writes"
        )
        assert result[0] == "deny"

    def test_plan_exited_registered_writer_denies_positive_control(self, tmp_path: Path):
        """POSITIVE CONTROL for AC #11: a REGISTERED writer still denies.

        Guards against the gate degrading to "denies nothing". Distinct shape
        from the AC #11 case: this tool is caught by NAME via the canonical
        MCP_WRITE_TOOLS registry, not by the path+content shape rule.
        """
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_mcp(
                "mcp__serena__replace_symbol_body",
                {"name_path": "MyClass/my_method", "body": "return 1"},
            )
        assert result is not None, "registered MCP writer must deny at plan_exited"
        assert result[0] == "deny"

    def test_plan_exited_reader_allows_negative_control(self, tmp_path: Path):
        """NEGATIVE CONTROL for AC #11: a reader with a path but no content allows.

        Guards against the gate degrading to "denies everything", which would
        make the positive control above meaningless. ``find_symbol`` carries
        ``relative_path`` — a PATH key — so it isolates the conjunction: path
        alone must not be enough to deny.
        """
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_mcp(
                "mcp__serena__find_symbol",
                {"name_path_pattern": "my_method", "relative_path": "src/app.py"},
            )
        assert result is None, "read-only MCP query must fall through at plan_exited"

    def test_plan_exited_allows_searxng_search(self, tmp_path: Path):
        """Regression: mcp__searxng__search must NOT be denied at plan_exited.

        This false positive is WHY the gate flipped from an enumerated read
        allowlist to a deny-what-acts rule (Issue #1503 residual, recorded at
        unified_pre_tool.py:7721-7726). Under the old allowlist the mandated
        search path was blocked purely for being un-enumerated. Nothing else
        in the suite guards it, so a revert to allowlist semantics would go
        unnoticed.
        """
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_mcp(
                "mcp__searxng__search", {"query": "python pathlib resolve"}
            )
        assert result is None, (
            "mcp__searxng__search is read-only and un-enumerated — it must fall "
            "through, not be denied for being unlisted"
        )

    def test_plan_exited_blocks_mcp_browser_evaluate(self, tmp_path: Path):
        """AC #19: mcp__playwright__browser_evaluate NOT on allowlist (arbitrary JS)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_mcp("mcp__playwright__browser_evaluate")
        assert result is not None
        assert result[0] == "deny"

    def test_plan_exited_allows_mcp_browser_snapshot(self, tmp_path: Path):
        """mcp__playwright__browser_snapshot on allowlist (read-only inspection)."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_mcp("mcp__playwright__browser_snapshot")
        assert result is None

    def test_mcp_readonly_does_not_contain_browser_evaluate(self):
        """AC #19: Regression — browser_evaluate must not be added to allowlist.

        Issue #1503 replaced the module-local _PLAN_EXIT_MCP_READONLY frozenset
        with the canonical tool_intent.MCP_READ_TOOLS registry, read via
        _ti_mcp_read_tools(). The AC is unchanged; only the source moved.
        """
        assert "mcp__playwright__browser_evaluate" not in _ti_mcp_read_tools()

    def test_plan_exited_allows_serena_read_tools(self, tmp_path: Path):
        """Issue #1503: the old allowlist OVER-BLOCKED serena reads.

        find_symbol / get_symbols_overview / find_referencing_symbols are
        read-only LSP queries. They were denied at the plan_exited stage purely
        because the module-local allowlist predated the serena integration.
        """
        _write_marker(tmp_path, stage="plan_exited")
        for tool in (
            "mcp__serena__find_symbol",
            "mcp__serena__get_symbols_overview",
            "mcp__serena__find_referencing_symbols",
        ):
            with patch("os.getcwd", return_value=str(tmp_path)):
                result = _check_plan_exit_mcp(tool)
            assert result is None, f"{tool} was blocked at plan_exited stage"

    def test_plan_exited_denies_serena_write_tools(self, tmp_path: Path):
        """Issue #1503: serena editors must NOT gain plan-exit passage."""
        _write_marker(tmp_path, stage="plan_exited")
        for tool in (
            "mcp__serena__replace_symbol_body",
            "mcp__serena__insert_after_symbol",
            "mcp__serena__replace_content",
        ):
            with patch("os.getcwd", return_value=str(tmp_path)):
                result = _check_plan_exit_mcp(tool)
            assert result is not None and result[0] == "deny", (
                f"{tool} was allowed at plan_exited stage"
            )


# ============================================================================
# critique_done: consume marker
# ============================================================================


class TestCritiqueDoneConsumesMarker:
    """stage=critique_done: terminal actions consume marker (ACs #12, #13)."""

    def test_critique_done_gh_issue_create_allows_and_deletes_marker(self, tmp_path: Path):
        """AC #12: Bash(gh issue create) allowed at critique_done AND marker deleted."""
        marker = _write_marker(tmp_path, stage="critique_done")
        assert marker.exists()
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native(
                "Bash",
                {"command": "gh issue create --title foo --body bar"},
            )
        assert result is None  # fall through (allow)
        assert not marker.exists(), "Marker must be consumed on gh issue create"

    def test_critique_done_task_implementer_allows_and_deletes_marker(self, tmp_path: Path):
        """AC #13: Task(implementer) allowed at critique_done AND marker deleted."""
        marker = _write_marker(tmp_path, stage="critique_done")
        assert marker.exists()
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native(
                "Task",
                {"subagent_type": "implementer", "prompt": "go"},
            )
        assert result is None
        assert not marker.exists()

    def test_critique_done_task_issue_creator_allows_and_deletes_marker(self, tmp_path: Path):
        """Task(issue-creator) allowed at critique_done AND marker deleted."""
        marker = _write_marker(tmp_path, stage="critique_done")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native(
                "Task",
                {"subagent_type": "issue-creator"},
            )
        assert result is None
        assert not marker.exists()

    def test_critique_done_task_cia_allows_and_deletes_marker(self, tmp_path: Path):
        """Task(continuous-improvement-analyst) allowed at critique_done AND marker deleted."""
        marker = _write_marker(tmp_path, stage="critique_done")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native(
                "Task",
                {"subagent_type": "continuous-improvement-analyst"},
            )
        assert result is None
        assert not marker.exists()

    def test_critique_done_other_bash_does_not_consume_marker(self, tmp_path: Path):
        """Non-consuming Bash at critique_done falls through without deleting marker."""
        marker = _write_marker(tmp_path, stage="critique_done")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Bash", {"command": "ls"})
        assert result is None
        # Marker preserved — this was not a consume event
        assert marker.exists()

    def test_critique_done_other_task_does_not_consume_marker(self, tmp_path: Path):
        """Task(plan-critic) at critique_done does not consume marker."""
        marker = _write_marker(tmp_path, stage="critique_done")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native(
                "Task",
                {"subagent_type": "plan-critic"},
            )
        assert result is None
        assert marker.exists()

    def test_critique_done_write_allowed_fall_through(self, tmp_path: Path):
        """Write at critique_done falls through (other gates may still block)."""
        _write_marker(tmp_path, stage="critique_done")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert result is None


# ============================================================================
# Marker edge cases
# ============================================================================


class TestMarkerEdgeCases:
    """Marker staleness, corruption, and back-compat (ACs #14, #15)."""

    def test_marker_missing_stage_treated_as_critique_done(self, tmp_path: Path):
        """AC #14: Marker without 'stage' field treated as critique_done."""
        _write_marker(tmp_path, include_stage=False)
        with patch("os.getcwd", return_value=str(tmp_path)):
            marker_data = _read_plan_exit_marker()
        assert marker_data is not None
        assert marker_data["stage"] == "critique_done"

    def test_marker_missing_stage_write_falls_through(self, tmp_path: Path):
        """Back-compat: Write at stageless marker falls through (old behavior was allow)."""
        _write_marker(tmp_path, include_stage=False)
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        # At critique_done, Write falls through
        assert result is None

    def test_marker_stale_auto_deleted(self, tmp_path: Path):
        """AC #15: Marker >30 min old auto-deleted; tool allowed."""
        marker = _write_marker(
            tmp_path,
            age_minutes=_PLAN_EXIT_STALE_MINUTES + 1,
            stage="plan_exited",
        )
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert result is None
        assert not marker.exists()

    def test_fresh_marker_not_deleted(self, tmp_path: Path):
        """Marker at 5 min not deleted; enforcement still fires."""
        marker = _write_marker(tmp_path, age_minutes=5, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert result is not None
        assert result[0] == "deny"
        assert marker.exists()

    def test_corrupted_marker_fails_closed(self, tmp_path: Path):
        """Issue #1684: a fresh corrupted marker fails CLOSED, not open.

        Adjusted from the pre-#1684 expectation (delete + allow). An
        unreadable marker means "cannot verify the stage", which INV-7
        requires be treated as "not passed" — the same disposition the
        unknown-stage branch already used.
        """
        marker_path = tmp_path / _PLAN_EXIT_MARKER_PATH
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("not valid json {{{")
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert result is not None
        assert result[0] == "deny"
        assert marker_path.exists(), "corrupt evidence must survive"

    def test_marker_unknown_stage_treated_as_plan_exited(self, tmp_path: Path):
        """Unknown stage value fails safe to plan_exited."""
        _write_marker(tmp_path, stage="some_future_stage")
        with patch("os.getcwd", return_value=str(tmp_path)):
            # Write should block (unknown stage = plan_exited for safety)
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert result is not None
        assert result[0] == "deny"

    def test_marker_missing_timestamp_fails_closed(self, tmp_path: Path):
        """Issue #1684: an unreadable timestamp is corruption → fail closed.

        Adjusted from the pre-#1684 expectation (delete + allow). Same
        reasoning as test_corrupted_marker_fails_closed: the staleness
        clock falls back to the file's mtime, which here is fresh.
        """
        marker_path = tmp_path / _PLAN_EXIT_MARKER_PATH
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps({"session_id": "test", "stage": "plan_exited"}))
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert result is not None
        assert result[0] == "deny"
        assert marker_path.exists()


# ============================================================================
# Issue #1684: corrupt marker must fail CLOSED, bounded by mtime staleness
# ============================================================================


def _write_corrupt_marker(tmp_path: Path, *, age_minutes: float = 0) -> Path:
    """Write an unparseable marker whose mtime is `age_minutes` old.

    Args:
        tmp_path: Temp directory acting as cwd.
        age_minutes: How old the file's mtime should be. The mtime is the
            ONLY clock available once the JSON body is unreadable.

    Returns:
        Path to the corrupt marker.
    """
    marker_path = tmp_path / _PLAN_EXIT_MARKER_PATH
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text("{invalid json")
    if age_minutes:
        stamp = time.time() - (age_minutes * 60.0)
        os.utime(marker_path, (stamp, stamp))
    return marker_path


class TestIssue1684CorruptMarkerFailsClosed:
    """Regression for #1684: corruption was the last silent fail-open.

    `_read_plan_exit_marker` deleted a corrupt marker and returned None —
    "cannot verify the stage" read as "no marker", i.e. no enforcement.
    That contradicted the unknown-stage branch twelve lines below, which
    already failed closed for the same class of unverifiable input.

    Both arms are exercised: the gate must REFUSE on a fresh corrupt
    marker and must still PERMIT once that corrupt marker ages past the
    staleness window, so no session is restricted permanently.
    """

    def test_regression_issue_1684_fresh_corrupt_marker_restricts(
        self, tmp_path: Path
    ):
        """Arm 1 (REFUSES): corrupt marker, mtime now → enforcement fires."""
        marker = _write_corrupt_marker(tmp_path, age_minutes=0)
        with patch("os.getcwd", return_value=str(tmp_path)):
            marker_data = _read_plan_exit_marker()
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert marker_data is not None, "corruption must not read as absence"
        assert marker_data["stage"] == "plan_exited"
        assert result is not None and result[0] == "deny"
        assert marker.exists(), (
            "the corrupt file is the only evidence corruption occurred; "
            "unlinking it guarantees silence"
        )

    def test_regression_issue_1684_fresh_corrupt_marker_restricts_mcp_writer(
        self, tmp_path: Path
    ):
        """Arm 1, different shape: the MCP surface must restrict too.

        A guard proven only on the Write tool is scoped to that instance.
        The plan-exit gate covers native writers AND MCP writers.
        """
        _write_corrupt_marker(tmp_path, age_minutes=0)
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = _check_plan_exit_mcp("mcp__ms365__send-mail")
        assert result is not None and result[0] == "deny"

    def test_regression_issue_1684_stale_corrupt_marker_permits(
        self, tmp_path: Path
    ):
        """Arm 2 (PERMITS): corrupt marker 31 min old → deleted, no enforcement.

        This is the anti-livelock arm. Without an mtime fallback clock a
        corrupt marker would restrict the session forever, which is
        strictly worse than the fail-open it replaced.
        """
        marker = _write_corrupt_marker(
            tmp_path, age_minutes=_PLAN_EXIT_STALE_MINUTES + 1
        )
        with patch("os.getcwd", return_value=str(tmp_path)):
            marker_data = _read_plan_exit_marker()
        assert marker_data is None
        assert not marker.exists(), "abandoned corrupt marker must self-clear"

        # And with the marker gone, the gate permits.
        with patch("os.getcwd", return_value=str(tmp_path)):
            assert _check_plan_exit_native("Write", {"file_path": "foo.py"}) is None

    def test_regression_issue_1684_valid_plan_exited_still_restricts(
        self, tmp_path: Path
    ):
        """Arm 3: valid marker at plan_exited — unchanged regression control."""
        _write_marker(tmp_path, stage="plan_exited")
        with patch("os.getcwd", return_value=str(tmp_path)):
            marker_data = _read_plan_exit_marker()
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert marker_data is not None and marker_data["stage"] == "plan_exited"
        assert result is not None and result[0] == "deny"

    def test_regression_issue_1684_valid_critique_done_still_permits(
        self, tmp_path: Path
    ):
        """Arm 4: valid marker at critique_done — unchanged regression control."""
        _write_marker(tmp_path, stage="critique_done")
        with patch("os.getcwd", return_value=str(tmp_path)):
            marker_data = _read_plan_exit_marker()
            result = _check_plan_exit_native("Write", {"file_path": "foo.py"})
        assert marker_data is not None and marker_data["stage"] == "critique_done"
        assert result is None

    def test_regression_issue_1684_absent_marker_still_permits(
        self, tmp_path: Path
    ):
        """Arm 5: no marker at all — absence must stay distinguishable.

        Negative control of a DIFFERENT shape than the reproducer: the fix
        must not turn "no plan session" into enforcement.
        """
        assert not (tmp_path / _PLAN_EXIT_MARKER_PATH).exists()
        with patch("os.getcwd", return_value=str(tmp_path)):
            assert _read_plan_exit_marker() is None
            assert _check_plan_exit_native("Write", {"file_path": "foo.py"}) is None

    def test_regression_issue_1684_missing_stage_still_critique_done(
        self, tmp_path: Path
    ):
        """Arm 6: valid timestamp + missing stage — back-compat path untouched.

        A stageless marker is READABLE, so it never reaches the corruption
        branch. It must still normalize to critique_done.
        """
        _write_marker(tmp_path, include_stage=False)
        with patch("os.getcwd", return_value=str(tmp_path)):
            marker_data = _read_plan_exit_marker()
        assert marker_data is not None
        assert marker_data["stage"] == "critique_done"

    def test_regression_issue_1684_corruption_lands_in_refusal_sink(
        self, tmp_path: Path, monkeypatch
    ):
        """Arm 7: the corruption event is observable, not silent.

        Routed through the canonical sink (`log_block_event`, #1588) so the
        row is attributable to this gate.
        """
        monkeypatch.delenv("HOOK_TELEMETRY_DISABLED", raising=False)
        monkeypatch.delenv("HOOK_RECOVERY_DISABLED", raising=False)
        _write_corrupt_marker(tmp_path, age_minutes=0)
        log_path = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"

        with patch("os.getcwd", return_value=str(tmp_path)):
            _read_plan_exit_marker()

        assert log_path.exists(), f"no sink file at {log_path}"
        rows = [
            json.loads(line)
            for line in log_path.read_text().splitlines()
            if line.strip()
        ]
        matches = [
            r for r in rows
            if r.get("reason", "").startswith("plan_exit_marker_corrupt:")
        ]
        assert matches, f"corruption not recorded; rows={rows}"
        row = matches[-1]
        assert row["hook_name"] == "unified_pre_tool.py"
        assert row["metadata"]["gate"] == "plan-exit-gate"
        assert row["metadata"]["disposition"] == "fail_closed"
        assert row["metadata"]["issue"] == "1684"
        assert row["refused"] is True, "fail_closed genuinely refused"

    def test_regression_issue_1684_stale_corruption_row_is_not_a_refusal(
        self, tmp_path: Path, monkeypatch
    ):
        """The permitting disposition must not be counted as a block.

        `stale_by_mtime` deletes and passes through — logging it with a
        refusal shape would inflate every downstream refusal count.
        """
        monkeypatch.delenv("HOOK_TELEMETRY_DISABLED", raising=False)
        monkeypatch.delenv("HOOK_RECOVERY_DISABLED", raising=False)
        _write_corrupt_marker(tmp_path, age_minutes=_PLAN_EXIT_STALE_MINUTES + 1)
        log_path = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"

        with patch("os.getcwd", return_value=str(tmp_path)):
            assert _read_plan_exit_marker() is None

        rows = [
            json.loads(line)
            for line in log_path.read_text().splitlines()
            if line.strip()
        ]
        matches = [
            r for r in rows
            if r.get("reason", "").startswith("plan_exit_marker_corrupt:")
        ]
        assert matches, f"stale corruption not recorded; rows={rows}"
        assert matches[-1]["metadata"]["disposition"] == "stale_by_mtime"
        assert matches[-1]["refused"] is False, (
            "a disposition that PERMITS must not be logged as a refusal"
        )

    def test_regression_issue_1684_stat_failure_keeps_the_old_escape(
        self, tmp_path: Path, monkeypatch
    ):
        """No clock at all → pre-#1684 behaviour, but logged not silent.

        If `stat()` itself raises there is no fallback clock, so failing
        closed would have no bound. That case keeps delete-and-pass-through
        — the branch exists, so it is exercised rather than assumed.
        """
        monkeypatch.delenv("HOOK_TELEMETRY_DISABLED", raising=False)
        monkeypatch.delenv("HOOK_RECOVERY_DISABLED", raising=False)
        marker = _write_corrupt_marker(tmp_path, age_minutes=0)

        real_stat = Path.stat

        def _boom(self, *args, **kwargs):
            if self.name == "plan_mode_exit.json":
                raise OSError(5, "simulated stat failure")
            return real_stat(self, *args, **kwargs)

        with patch("os.getcwd", return_value=str(tmp_path)), \
                patch.object(Path, "stat", _boom):
            assert _read_plan_exit_marker() is None
        assert not marker.exists()

        rows = [
            json.loads(line)
            for line in (tmp_path / ".claude" / "logs" / "hook-blocks.jsonl")
            .read_text().splitlines()
            if line.strip()
        ]
        matches = [
            r for r in rows
            if r.get("reason", "").startswith("plan_exit_marker_corrupt:")
        ]
        assert matches, "the no-clock escape must still be observable"
        assert matches[-1]["metadata"]["disposition"] == "stat_failed"
        assert matches[-1]["refused"] is False

    def test_regression_issue_1684_sink_negative_control_no_row_when_valid(
        self, tmp_path: Path, monkeypatch
    ):
        """Instrument control for arm 7: a VALID marker writes no corruption row.

        Without this, arm 7's assertion could be satisfied by a sink that
        logs unconditionally — an instrument that cannot stay silent cannot
        attribute anything.
        """
        monkeypatch.delenv("HOOK_TELEMETRY_DISABLED", raising=False)
        monkeypatch.delenv("HOOK_RECOVERY_DISABLED", raising=False)
        _write_marker(tmp_path, stage="plan_exited")
        log_path = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"

        with patch("os.getcwd", return_value=str(tmp_path)):
            _read_plan_exit_marker()

        rows = []
        if log_path.exists():
            rows = [
                json.loads(line)
                for line in log_path.read_text().splitlines()
                if line.strip()
            ]
        assert not [
            r for r in rows
            if r.get("reason", "").startswith("plan_exit_marker_corrupt:")
        ], f"sink fired on a readable marker; rows={rows}"


# ============================================================================
# Race mitigation
# ============================================================================


class TestRaceMitigation:
    """10ms retry-on-deny catches writer-hook advance during call."""

    def test_race_marker_advances_during_window_flips_to_allow(self, tmp_path: Path):
        """If marker advances from plan_exited to critique_done during 10ms retry, allow."""
        _write_marker(tmp_path, stage="plan_exited")

        # Wrap _read_plan_exit_marker: first call returns plan_exited, second returns critique_done
        import unified_pre_tool as upt
        real_read = upt._read_plan_exit_marker
        call_count = {"n": 0}

        def fake_read():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return real_read()  # plan_exited
            # Simulate stage advance after first read
            marker_path = Path(os.getcwd()) / _PLAN_EXIT_MARKER_PATH
            data = json.loads(marker_path.read_text())
            data["stage"] = "critique_done"
            marker_path.write_text(json.dumps(data))
            return real_read()  # critique_done

        with patch("os.getcwd", return_value=str(tmp_path)):
            with patch.object(upt, "_read_plan_exit_marker", side_effect=fake_read):
                result = _check_plan_exit_native("Write", {"file_path": "foo.py"})

        # Race mitigation saw the advance — should allow
        assert result is None


# ============================================================================
# Bash allowlist helper
# ============================================================================


class TestBashAllowlistHelper:
    """_bash_command_on_allowlist in isolation."""

    def test_single_token_allowlisted(self):
        assert _bash_command_on_allowlist("ls") is True
        assert _bash_command_on_allowlist("pwd") is True
        assert _bash_command_on_allowlist("echo hello") is True

    def test_two_token_git_allowlisted(self):
        assert _bash_command_on_allowlist("git status") is True
        assert _bash_command_on_allowlist("git log --oneline") is True

    def test_three_token_gh_allowlisted(self):
        assert _bash_command_on_allowlist("gh issue view 123") is True
        assert _bash_command_on_allowlist("gh pr list") is True

    def test_gh_issue_create_not_on_allowlist(self):
        assert _bash_command_on_allowlist("gh issue create --title x") is False

    def test_mkdir_not_on_allowlist(self):
        assert _bash_command_on_allowlist("mkdir foo") is False

    def test_injection_rejected_semicolon(self):
        assert _bash_command_on_allowlist("ls; rm -rf /") is False

    def test_injection_rejected_backtick(self):
        assert _bash_command_on_allowlist("ls `pwd`") is False

    def test_injection_rejected_newline(self):
        """A03 BLOCKING regression: '\\n' is a bash command separator.

        Without rejection, str.split() treats '\\n' as whitespace and
        splits 'ls\\nrm -rf /' into ['ls', 'rm', '-rf', '/'], where the
        first token 'ls' matches the 1-token allowlist.
        """
        assert _bash_command_on_allowlist("ls\nrm -rf /") is False

    def test_injection_rejected_crlf(self):
        """A03 BLOCKING regression: CRLF (Windows-style) injection."""
        assert _bash_command_on_allowlist("ls\r\nrm -rf /") is False

    def test_injection_rejected_cr(self):
        """A03 BLOCKING regression: bare CR injection."""
        assert _bash_command_on_allowlist("ls\rrm -rf /") is False

    def test_security_a03_newline_bypass_closed(self):
        """A03 BLOCKING regression: newline-separated multi-command injection
        must be rejected. Was previously bypassed because str.split() treats
        \\n as whitespace. Fix: \\n added to _PLAN_EXIT_INJECTION_TOKENS."""
        payload = "ls\nrm -rf .claude/plan_mode_exit.json"
        assert _bash_command_on_allowlist(payload) is False

    def test_security_a03_additional_bypass_payloads(self):
        """A03 BLOCKING regression: additional newline-injection payloads.

        Each payload starts with an allowlisted command, then uses '\\n'
        to chain a malicious command. All must be rejected.
        """
        payloads = [
            "echo hello\ngit remote set-url origin http://attacker.com",
            "cat README.md\npython3 malicious_payload.py",
            "whoami\nchmod 777 /tmp/sentinel",
        ]
        for payload in payloads:
            assert _bash_command_on_allowlist(payload) is False, (
                f"Payload should be rejected but was allowed: {payload!r}"
            )

    def test_empty_command(self):
        assert _bash_command_on_allowlist("") is False
        assert _bash_command_on_allowlist("   ") is False


# ============================================================================
# Issue #938 + #1361: Scope check / escape hatch integration
# ============================================================================


class TestScopeCheckIntegration:
    """Issue #938 (scope) + Issue #1361 (polarity flip): escape-hatch integration.

    Post-#1361 the scope check is deleted — enforcement is default-ON in every
    repo. The escape hatches (AUTONOMOUS_DEV_SKIP_PLAN_REVIEW, .claude/SKIP_PLAN_REVIEW)
    remain unchanged and still short-circuit the gate. The universal bypass
    (Issue #969: AUTONOMOUS_DEV_BYPASS or .claude/.bypass) short-circuits
    hooks BEFORE this function is reached and is exercised at hook-preamble level.
    """

    def test_foreign_project_with_marker_blocks_after_polarity_flip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """AC-1: Foreign project + marker → gate FIRES (deny) after #1361 flip.

        Before #1361 the gate silently no-op'd in foreign repos. After the
        polarity flip, enforcement is default-ON everywhere.
        """
        _write_marker(tmp_path, stage="plan_exited")
        monkeypatch.chdir(tmp_path)
        # Simulate a foreign project — no longer a bypass condition.
        monkeypatch.setattr(
            unified_pre_tool, "_is_adev_project_fn", lambda: False
        )
        for var in (
            "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW",
            "AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT",
            "AUTONOMOUS_DEV_BYPASS",
        ):
            monkeypatch.delenv(var, raising=False)

        result = _check_plan_exit_native("Write", {"file_path": "x.py"})
        assert result is not None, (
            "AC-1: post-#1361, foreign project must enforce plan-exit gate"
        )
        assert result[0] == "deny"
        assert result[1] == _PLAN_EXIT_DENY_REASON

        mcp_result = _check_plan_exit_mcp("mcp__ms365__send-mail")
        assert mcp_result is not None
        assert mcp_result[0] == "deny"

    def test_foreign_project_with_skip_env_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """AC-4: Foreign project + SKIP env var → escape hatch still works."""
        _write_marker(tmp_path, stage="plan_exited")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            unified_pre_tool, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.setenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "1")

        assert _check_plan_exit_native("Write", {"file_path": "x.py"}) is None
        assert _check_plan_exit_mcp("mcp__ms365__send-mail") is None

    def test_foreign_project_with_sentinel_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """AC-5: Foreign project + .claude/SKIP_PLAN_REVIEW → escape hatch still works."""
        _write_marker(tmp_path, stage="plan_exited")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            unified_pre_tool, "_is_adev_project_fn", lambda: False
        )
        (tmp_path / ".claude" / "SKIP_PLAN_REVIEW").write_text("")
        monkeypatch.delenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", raising=False)

        assert _check_plan_exit_native("Write", {"file_path": "x.py"}) is None
        assert _check_plan_exit_mcp("mcp__ms365__send-mail") is None

    def test_global_enforcement_emits_deprecation_notice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-6: AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT=1 → stderr deprecation notice, gate still fires.

        The env var is deprecated post-#1361 — enforcement is now the default
        regardless. Setting the var emits a stderr notice AND enforcement fires
        just as it would without the var.
        """
        _write_marker(tmp_path, stage="plan_exited")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            unified_pre_tool, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.setenv("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "1")
        monkeypatch.delenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", raising=False)

        result = _check_plan_exit_native("Write", {"file_path": "x.py"})
        assert result is not None, "Enforcement must still fire when GE=1"
        assert result[0] == "deny"

        captured = capsys.readouterr()
        assert "DEPRECATION" in captured.err, (
            f"AC-6: expected deprecation notice on stderr, got: {captured.err!r}"
        )
        assert "AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT" in captured.err

    def test_mcp_gate_also_emits_deprecation_notice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-6 + AC-7: MCP gate mirrors native gate — deprecation notice + enforcement."""
        _write_marker(tmp_path, stage="plan_exited")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            unified_pre_tool, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.setenv("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "1")
        monkeypatch.delenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", raising=False)

        result = _check_plan_exit_mcp("mcp__ms365__send-mail")
        assert result is not None, "MCP gate must fire when GE=1 (post-#1361)"
        assert result[0] == "deny"

        captured = capsys.readouterr()
        assert "DEPRECATION" in captured.err

    def test_in_project_with_skip_env_with_marker_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """In-project + SKIP env var + marker → gate returns None (escape wins)."""
        _write_marker(tmp_path, stage="plan_exited")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "1")

        assert _check_plan_exit_native("Write", {"file_path": "x.py"}) is None
        assert _check_plan_exit_mcp("mcp__ms365__send-mail") is None

    def test_in_project_with_sentinel_with_marker_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """In-project + sentinel + marker → gate returns None (escape wins)."""
        _write_marker(tmp_path, stage="plan_exited")  # Creates .claude/
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude" / "SKIP_PLAN_REVIEW").write_text("")

        assert _check_plan_exit_native("Write", {"file_path": "x.py"}) is None
        assert _check_plan_exit_mcp("mcp__ms365__send-mail") is None

    def test_global_enforcement_in_foreign_project_with_marker_blocks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Foreign project + GLOBAL_ENFORCEMENT=1 + marker → gate fires (deny)."""
        _write_marker(tmp_path, stage="plan_exited")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            unified_pre_tool, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.setenv("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "1")
        monkeypatch.delenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", raising=False)

        result = _check_plan_exit_native("Write", {"file_path": "x.py"})
        assert result is not None
        assert result[0] == "deny"

    def test_deny_reason_advertises_env_var(self):
        """AC #7: deny reason includes AUTONOMOUS_DEV_SKIP_PLAN_REVIEW."""
        assert "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW" in _PLAN_EXIT_DENY_REASON
        assert "/implement --skip-review" in _PLAN_EXIT_DENY_REASON
        assert "plan-critic" in _PLAN_EXIT_DENY_REASON

    def test_deny_system_message_advertises_three_escape_hatches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """AC #7: deny systemMessage advertises all three escape hatches."""
        _write_marker(tmp_path, stage="plan_exited")
        monkeypatch.chdir(tmp_path)

        result = _check_plan_exit_native("Write", {"file_path": "x.py"})
        assert result is not None
        _, _, system_msg = result
        assert "/implement --skip-review" in system_msg
        assert "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW" in system_msg
        assert "SKIP_PLAN_REVIEW" in system_msg  # sentinel filename appears

    @pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy_skip_env_variants_short_circuit(
        self,
        truthy: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """All truthy values for SKIP_PLAN_REVIEW short-circuit the gate."""
        _write_marker(tmp_path, stage="plan_exited")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", truthy)

        assert _check_plan_exit_native("Write", {"file_path": "x.py"}) is None
        assert _check_plan_exit_mcp("mcp__ms365__send-mail") is None

"""
Tests for gh issue create blocking in unified_pre_tool.py (Issue #599).

Validates:
1. _detect_gh_issue_create blocks direct gh issue create usage
2. Allow-through for pipeline active, authorized agents, marker file
3. Non-matching commands pass through

Date: 2026-03-29
"""

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hook and lib directories to path
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOK_DIR))

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove pipeline/agent env vars to ensure clean state."""
    env_keys = [
        "SANDBOX_ENABLED", "PRE_TOOL_MCP_SECURITY", "PRE_TOOL_AGENT_AUTH",
        "PRE_TOOL_BATCH_PERMISSION", "MCP_AUTO_APPROVE", "ENFORCEMENT_LEVEL",
        "CLAUDE_AGENT_NAME", "PIPELINE_STATE_FILE", "CLAUDE_SESSION_ID",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def no_pipeline():
    """Patch _is_pipeline_active to return False."""
    with patch.object(hook, "_is_pipeline_active", return_value=False):
        yield


@pytest.fixture
def no_agent():
    """Patch _get_active_agent_name to return empty string."""
    with patch.object(hook, "_get_active_agent_name", return_value=""):
        yield


@pytest.fixture
def no_marker(tmp_path):
    """Patch GH_ISSUE_MARKER_PATH to a non-existent file."""
    fake_path = str(tmp_path / "nonexistent_marker")
    with patch.object(hook, "GH_ISSUE_MARKER_PATH", fake_path):
        yield fake_path


# ---------------------------------------------------------------------------
# TestGhIssueCreateBlocking — commands that SHOULD be blocked
# ---------------------------------------------------------------------------

class TestGhIssueCreateBlocking:
    """Tests for commands that should be blocked."""

    def test_bare_gh_issue_create(self, no_pipeline, no_agent, no_marker):
        """Basic 'gh issue create --title ...' should be blocked."""
        cmd = 'gh issue create --title "bug report" --body "details"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result
        assert "/create-issue" in result

    def test_gh_issue_create_with_flags(self, no_pipeline, no_agent, no_marker):
        """gh issue create with various flags should be blocked."""
        cmd = 'gh issue create -R owner/repo --title "test" --label "bug"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_case_insensitive_blocking(self, no_pipeline, no_agent, no_marker):
        """Case variations like 'GH Issue Create' should be blocked."""
        cmd = 'GH Issue Create --title "test"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_gh_issue_create_with_body_file(self, no_pipeline, no_agent, no_marker):
        """gh issue create --body-file should be blocked."""
        cmd = 'gh issue create --title "test" --body-file /tmp/body.md'
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_stale_marker_blocks(self, no_pipeline, no_agent, tmp_path):
        """Marker file older than 1 hour should NOT allow through."""
        marker = tmp_path / "stale_marker"
        marker.touch()
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        os.utime(str(marker), (old_time, old_time))

        with patch.object(hook, "GH_ISSUE_MARKER_PATH", str(marker)):
            cmd = 'gh issue create --title "test"'
            result = hook._detect_gh_issue_create(cmd)
            assert result is not None
            assert "BLOCKED" in result


# ---------------------------------------------------------------------------
# TestGhIssueCreateAllowThrough — commands that should be allowed
# ---------------------------------------------------------------------------

class TestGhIssueCreateAllowThrough:
    """Tests for commands that should be allowed through."""

    def test_non_matching_gh_issue_list(self, no_pipeline, no_agent, no_marker):
        """'gh issue list' should not be blocked."""
        result = hook._detect_gh_issue_create("gh issue list --state open")
        assert result is None

    def test_non_matching_gh_pr_create(self, no_pipeline, no_agent, no_marker):
        """'gh pr create' should not be blocked."""
        result = hook._detect_gh_issue_create("gh pr create --title 'test'")
        assert result is None

    def test_non_matching_gh_issue_close(self, no_pipeline, no_agent, no_marker):
        """'gh issue close' should not be blocked."""
        result = hook._detect_gh_issue_create("gh issue close 123")
        assert result is None

    def test_non_matching_gh_issue_view(self, no_pipeline, no_agent, no_marker):
        """'gh issue view' should not be blocked."""
        result = hook._detect_gh_issue_create("gh issue view 456")
        assert result is None

    def test_no_gh_at_all(self, no_pipeline, no_agent, no_marker):
        """Commands without gh should pass through."""
        result = hook._detect_gh_issue_create('echo "hello world"')
        assert result is None

    def test_pipeline_active_allows(self, no_agent, no_marker):
        """When pipeline is active, gh issue create should be allowed."""
        with patch.object(hook, "_is_pipeline_active", return_value=True):
            cmd = 'gh issue create --title "test"'
            result = hook._detect_gh_issue_create(cmd)
            assert result is None

    def test_continuous_improvement_analyst_allowed(self, no_pipeline, no_marker):
        """continuous-improvement-analyst agent should be allowed."""
        with patch.object(hook, "_get_active_agent_name",
                          return_value="continuous-improvement-analyst"):
            cmd = 'gh issue create --title "test"'
            result = hook._detect_gh_issue_create(cmd)
            assert result is None

    def test_issue_creator_agent_allowed(self, no_pipeline, no_marker):
        """issue-creator agent should be allowed."""
        with patch.object(hook, "_get_active_agent_name",
                          return_value="issue-creator"):
            cmd = 'gh issue create --title "test"'
            result = hook._detect_gh_issue_create(cmd)
            assert result is None

    def test_fresh_marker_has_no_effect(self, no_pipeline, no_agent, tmp_path):
        """Marker file presence MUST NOT grant allow (Issue #1203 dead-code removal).

        Pre-#1203, a fresh marker file at GH_ISSUE_MARKER_PATH granted a 1-hour
        bypass via a READ allow-through. That allow-through was dead code:
        nothing has written the marker since #627 (the WRITE was blocked by
        _detect_gh_issue_marker_creation). #1203 removed the READ. The WRITE
        blocker remains as defense-in-depth.
        """
        marker = tmp_path / "fresh_marker"
        marker.touch()  # Creates with current time

        with patch.object(hook, "GH_ISSUE_MARKER_PATH", str(marker)), \
             patch.object(hook, "_is_issue_command_active", return_value=False):
            cmd = 'gh issue create --title "test"'
            result = hook._detect_gh_issue_create(cmd)
            # Marker presence MUST no longer grant allow; expect BLOCKED.
            assert result is not None, "Marker presence must NOT grant allow (#1203)"
            assert "BLOCKED" in result


# ---------------------------------------------------------------------------
# TestGhIssueCreateEdgeCases
# ---------------------------------------------------------------------------

class TestGhIssueCreateEdgeCases:
    """Edge case tests for robustness."""

    def test_empty_command(self, no_pipeline, no_agent, no_marker):
        """Empty command should pass through."""
        result = hook._detect_gh_issue_create("")
        assert result is None

    def test_gh_issue_agents_constant_exists(self):
        """GH_ISSUE_AGENTS constant should be defined."""
        assert hasattr(hook, "GH_ISSUE_AGENTS")
        assert "continuous-improvement-analyst" in hook.GH_ISSUE_AGENTS
        assert "issue-creator" in hook.GH_ISSUE_AGENTS

    def test_gh_issue_marker_path_constant_exists(self):
        """GH_ISSUE_MARKER_PATH constant should be defined."""
        assert hasattr(hook, "GH_ISSUE_MARKER_PATH")
        assert "autonomous_dev_gh_issue" in hook.GH_ISSUE_MARKER_PATH

    def test_block_message_content(self, no_pipeline, no_agent, no_marker):
        """Block message should include actionable guidance and anti-bypass language."""
        cmd = 'gh issue create --title "test"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "/create-issue" in result
        assert "/create-issue --quick" in result
        assert "duplicate detection" in result
        assert "FORBIDDEN" in result
        assert "! gh issue create" in result


# ---------------------------------------------------------------------------
# TestGhIssueCreateFalsePositives — regression tests for Issue #601
# ---------------------------------------------------------------------------

class TestGhIssueCreateFalsePositives:
    """Regression tests: text mentioning 'gh issue create' inside strings/heredocs
    should NOT trigger blocking. Only actual command invocations should be blocked."""

    def test_commit_message_with_gh_issue_create_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """git commit -m with 'gh issue create' in the message should NOT be blocked."""
        cmd = 'git commit -m "fix: write gh-issue-create marker file"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "Commit message mentioning 'gh issue create' should not be blocked"
        )

    def test_heredoc_commit_message_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """Heredoc commit message mentioning 'gh issue create' should NOT be blocked."""
        cmd = (
            "git commit -m \"$(cat <<'EOF'\n"
            "fix gh issue create bug\n"
            "EOF\n"
            ")\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "Heredoc body mentioning 'gh issue create' should not be blocked"
        )

    def test_echo_mentioning_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """echo statement mentioning 'gh issue create' should NOT be blocked."""
        cmd = 'echo "use gh issue create to file bugs"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "echo with quoted 'gh issue create' should not be blocked"
        )

    def test_actual_gh_issue_create_still_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """Actual 'gh issue create' command must STILL be blocked."""
        cmd = 'gh issue create --title "test" --body "details"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_gh_issue_create_after_heredoc_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """Heredoc followed by actual gh issue create should still be blocked."""
        cmd = (
            "cat <<'EOF'\nsome docs\nEOF\n"
            "gh issue create --title \"real command\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "Actual gh issue create after a heredoc should still be blocked"
        )
        assert "BLOCKED" in result

    def test_single_quoted_mention_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """Single-quoted string mentioning 'gh issue create' should NOT be blocked."""
        cmd = "echo 'run gh issue create for issues'"
        result = hook._detect_gh_issue_create(cmd)
        assert result is None

    def test_commit_message_double_quoted_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """Double-quoted commit message with 'gh issue create' should NOT be blocked."""
        cmd = 'git commit -m "docs: document gh issue create workflow"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is None


# ---------------------------------------------------------------------------
# TestGhIssueCreateSubprocessBypass — Issue #618 regression tests
# ---------------------------------------------------------------------------

class TestGhIssueCreateSubprocessBypass:
    """Tests for subprocess bypass patterns that wrap 'gh issue create' inside
    python3 -c, sh -c, bash -c, backticks, etc. (Issue #618)."""

    def test_python3_subprocess_run_blocked(self, no_pipeline, no_agent, no_marker):
        """python3 -c with subprocess.run(['gh', 'issue', 'create']) should be blocked."""
        cmd = (
            "python3 -c \"import subprocess; "
            "subprocess.run(['gh', 'issue', 'create', '--title', 'test'])\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "subprocess.run(['gh', 'issue', 'create']) bypass must be blocked"
        )
        assert "BLOCKED" in result

    def test_python3_subprocess_call_blocked(self, no_pipeline, no_agent, no_marker):
        """python3 -c with subprocess.call(['gh', 'issue', 'create']) should be blocked."""
        cmd = (
            "python3 -c \"import subprocess; "
            "subprocess.call(['gh', 'issue', 'create', '--title', 'bug'])\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "subprocess.call(['gh', 'issue', 'create']) bypass must be blocked"
        )
        assert "BLOCKED" in result

    def test_python3_subprocess_popen_blocked(self, no_pipeline, no_agent, no_marker):
        """python3 -c with subprocess.Popen(['gh', 'issue', 'create']) should be blocked."""
        cmd = (
            "python3 -c \"import subprocess; "
            "subprocess.Popen(['gh', 'issue', 'create', '--title', 'test'])\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "subprocess.Popen(['gh', 'issue', 'create']) bypass must be blocked"
        )
        assert "BLOCKED" in result

    def test_python_os_system_blocked(self, no_pipeline, no_agent, no_marker):
        """python3 -c with os.system('gh issue create') should be blocked."""
        cmd = (
            "python3 -c \"import os; "
            "os.system('gh issue create --title test --body details')\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "os.system('gh issue create') bypass must be blocked"
        )
        assert "BLOCKED" in result

    def test_sh_c_gh_issue_create_blocked(self, no_pipeline, no_agent, no_marker):
        """sh -c 'gh issue create ...' should be blocked."""
        cmd = "sh -c 'gh issue create --title \"bypass\" --body \"test\"'"
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "sh -c 'gh issue create' bypass must be blocked"
        )
        assert "BLOCKED" in result

    def test_bash_c_gh_issue_create_blocked(self, no_pipeline, no_agent, no_marker):
        """bash -c 'gh issue create ...' should be blocked."""
        cmd = "bash -c 'gh issue create --title \"bypass\" --body \"test\"'"
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "bash -c 'gh issue create' bypass must be blocked"
        )
        assert "BLOCKED" in result

    def test_backtick_gh_issue_create_blocked(self, no_pipeline, no_agent, no_marker):
        """Backtick command substitution `gh issue create ...` should be blocked."""
        cmd = "RESULT=`gh issue create --title 'test' --body 'details'`"
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "Backtick `gh issue create` bypass must be blocked"
        )
        assert "BLOCKED" in result

    def test_dollar_subst_gh_issue_create_blocked(self, no_pipeline, no_agent, no_marker):
        """$(gh issue create ...) command substitution should be blocked."""
        cmd = "RESULT=$(gh issue create --title 'test' --body 'details')"
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "$(gh issue create) bypass must be blocked"
        )
        assert "BLOCKED" in result

    def test_python_subprocess_check_output_blocked(self, no_pipeline, no_agent, no_marker):
        """subprocess.check_output(['gh', 'issue', 'create']) should be blocked."""
        cmd = (
            "python3 -c \"import subprocess; "
            "subprocess.check_output(['gh', 'issue', 'create', '--title', 'x'])\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "subprocess.check_output(['gh', 'issue', 'create']) bypass must be blocked"
        )
        assert "BLOCKED" in result

    def test_bypass_blocked_pipeline_inactive_no_marker(
        self, no_pipeline, no_agent, no_marker
    ):
        """Bypass detection respects the same allow-throughs as direct detection."""
        cmd = (
            "python3 -c \"import subprocess; "
            "subprocess.run(['gh', 'issue', 'create', '--title', 'test'])\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result
        assert "/create-issue" in result

    def test_bypass_allowed_when_pipeline_active(self, no_agent, no_marker):
        """Subprocess bypass is allowed when pipeline is active."""
        with patch.object(hook, "_is_pipeline_active", return_value=True):
            cmd = (
                "python3 -c \"import subprocess; "
                "subprocess.run(['gh', 'issue', 'create', '--title', 'x'])\""
            )
            result = hook._detect_gh_issue_create(cmd)
            assert result is None

    def test_bypass_allowed_when_authorized_agent(self, no_pipeline, no_marker):
        """Subprocess bypass is allowed for authorized agents."""
        with patch.object(hook, "_get_active_agent_name",
                          return_value="continuous-improvement-analyst"):
            cmd = (
                "python3 -c \"import subprocess; "
                "subprocess.run(['gh', 'issue', 'create', '--title', 'x'])\""
            )
            result = hook._detect_gh_issue_create(cmd)
            assert result is None

    def test_subprocess_no_gh_issue_create_allowed(self, no_pipeline, no_agent, no_marker):
        """subprocess.run without gh issue create should NOT be blocked."""
        cmd = (
            "python3 -c \"import subprocess; "
            "subprocess.run(['gh', 'issue', 'list'])\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "subprocess.run without gh issue create must not be blocked"
        )

    def test_subprocess_gh_pr_create_allowed(self, no_pipeline, no_agent, no_marker):
        """subprocess.run(['gh', 'pr', 'create']) should NOT be blocked."""
        cmd = (
            "python3 -c \"import subprocess; "
            "subprocess.run(['gh', 'pr', 'create', '--title', 'x'])\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "subprocess.run with gh pr create must not be blocked"
        )


# ---------------------------------------------------------------------------
# TestContainsGhIssueCreateBypass — unit tests for the helper function
# ---------------------------------------------------------------------------

class TestContainsGhIssueCreateBypass:
    """Unit tests for the _contains_gh_issue_create_bypass helper (Issue #618)."""

    def test_subprocess_run_detected(self):
        """subprocess.run with gh issue create is detected."""
        cmd = "python3 -c \"subprocess.run(['gh', 'issue', 'create'])\""
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_subprocess_call_detected(self):
        """subprocess.call with gh issue create is detected."""
        cmd = "python3 -c \"subprocess.call(['gh', 'issue', 'create'])\""
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_subprocess_popen_detected(self):
        """subprocess.Popen with gh issue create is detected."""
        cmd = "python3 -c \"subprocess.Popen(['gh', 'issue', 'create'])\""
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_os_system_detected(self):
        """os.system('gh issue create') is detected."""
        cmd = "python3 -c \"os.system('gh issue create --title x')\""
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_sh_c_detected(self):
        """sh -c 'gh issue create' is detected."""
        cmd = "sh -c 'gh issue create --title test'"
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_bash_c_detected(self):
        """bash -c 'gh issue create' is detected."""
        cmd = "bash -c 'gh issue create --title test'"
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_backtick_detected(self):
        """Backtick gh issue create is detected."""
        cmd = "X=`gh issue create --title test`"
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_dollar_subst_detected(self):
        """$(gh issue create) is detected."""
        cmd = "X=$(gh issue create --title test)"
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_gh_issue_list_not_detected(self):
        """subprocess.run with gh issue list is NOT detected."""
        cmd = "python3 -c \"subprocess.run(['gh', 'issue', 'list'])\""
        assert hook._contains_gh_issue_create_bypass(cmd) is False

    def test_gh_pr_create_not_detected(self):
        """subprocess.run with gh pr create is NOT detected."""
        cmd = "python3 -c \"subprocess.run(['gh', 'pr', 'create'])\""
        assert hook._contains_gh_issue_create_bypass(cmd) is False

    def test_empty_command_not_detected(self):
        """Empty command is not detected as a bypass."""
        assert hook._contains_gh_issue_create_bypass("") is False

    def test_direct_gh_issue_create_not_detected_by_bypass(self):
        """Direct 'gh issue create' (no subprocess wrapper) is not a bypass pattern."""
        # The bypass detector is specifically for subprocess wrapping.
        # Direct calls are caught by the primary detector.
        cmd = "gh issue create --title test"
        assert hook._contains_gh_issue_create_bypass(cmd) is False


# ---------------------------------------------------------------------------
# TestGhIssueMarkerCreationBlocking — Issue #627 regression tests
# ---------------------------------------------------------------------------

class TestGhIssueMarkerCreationBlocking:
    """Tests for blocking direct creation of the gh issue marker file (Issue #627).

    The marker file autonomous_dev_gh_issue_allowed.marker is written by the
    /create-issue pipeline. Allowing direct creation would bypass the entire
    gh-issue enforcement mechanism.
    """

    # ------------------------------------------------------------------
    # Blocked scenarios (no pipeline, no authorized agent)
    # ------------------------------------------------------------------

    def test_touch_marker_direct_blocked(self, no_pipeline, no_agent):
        """touch targeting the marker file should be blocked."""
        cmd = "touch /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result
        assert "/create-issue" in result

    def test_touch_marker_extra_spaces_blocked(self, no_pipeline, no_agent):
        """touch with extra spaces before path should be blocked."""
        cmd = "touch  /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_redirect_write_echo_blocked(self, no_pipeline, no_agent):
        """echo with redirect > to marker file should be blocked."""
        cmd = 'echo "" > /tmp/autonomous_dev_gh_issue_allowed.marker'
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_redirect_write_printf_blocked(self, no_pipeline, no_agent):
        """printf with redirect > to marker file should be blocked."""
        cmd = 'printf "" > /tmp/autonomous_dev_gh_issue_allowed.marker'
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_cp_to_marker_blocked(self, no_pipeline, no_agent):
        """cp targeting the marker filename should be blocked."""
        cmd = "cp /tmp/somefile /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_mv_to_marker_blocked(self, no_pipeline, no_agent):
        """mv targeting the marker filename should be blocked."""
        cmd = "mv /tmp/somefile /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_tee_to_marker_blocked(self, no_pipeline, no_agent):
        """tee targeting the marker filename should be blocked."""
        cmd = "tee /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_python_path_touch_blocked(self, no_pipeline, no_agent):
        """Python Path(...).touch() on the marker file should be blocked."""
        cmd = "python3 -c \"Path('/tmp/autonomous_dev_gh_issue_allowed.marker').touch()\""
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_python_open_write_blocked(self, no_pipeline, no_agent):
        """Python open(..., 'w') on the marker file should be blocked."""
        cmd = "python3 -c \"open('/tmp/autonomous_dev_gh_issue_allowed.marker', 'w').close()\""
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result

    # ------------------------------------------------------------------
    # Allow-through scenarios
    # ------------------------------------------------------------------

    def test_pipeline_active_allows_touch(self, no_agent):
        """When pipeline is active, touching the marker should be allowed."""
        with patch.object(hook, "_is_pipeline_active", return_value=True):
            cmd = "touch /tmp/autonomous_dev_gh_issue_allowed.marker"
            result = hook._detect_gh_issue_marker_creation(cmd)
            assert result is None

    def test_authorized_agent_allows_touch(self, no_pipeline):
        """Authorized agent (continuous-improvement-analyst) should be allowed."""
        with patch.object(hook, "_get_active_agent_name",
                          return_value="continuous-improvement-analyst"):
            cmd = "touch /tmp/autonomous_dev_gh_issue_allowed.marker"
            result = hook._detect_gh_issue_marker_creation(cmd)
            assert result is None

    def test_issue_creator_agent_allows_touch(self, no_pipeline):
        """issue-creator agent should be allowed to create the marker."""
        with patch.object(hook, "_get_active_agent_name",
                          return_value="issue-creator"):
            cmd = "touch /tmp/autonomous_dev_gh_issue_allowed.marker"
            result = hook._detect_gh_issue_marker_creation(cmd)
            assert result is None

    # ------------------------------------------------------------------
    # False positive avoidance
    # ------------------------------------------------------------------

    def test_echo_no_redirect_not_blocked(self, no_pipeline, no_agent):
        """echo mentioning the marker name without redirect should NOT be blocked."""
        cmd = 'echo "autonomous_dev_gh_issue_allowed"'
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None

    def test_cat_read_not_blocked(self, no_pipeline, no_agent):
        """cat (reading) the marker file should NOT be blocked."""
        cmd = "cat /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None

    def test_rm_delete_not_blocked(self, no_pipeline, no_agent):
        """rm (deleting) the marker file should NOT be blocked."""
        cmd = "rm -f /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None

    def test_ls_listing_not_blocked(self, no_pipeline, no_agent):
        """ls (listing) the marker file should NOT be blocked."""
        cmd = "ls -la /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None

    def test_touch_different_file_not_blocked(self, no_pipeline, no_agent):
        """touch targeting a different file should NOT be blocked."""
        cmd = "touch /tmp/some_other_file.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None

    def test_empty_command_not_blocked(self, no_pipeline, no_agent):
        """Empty command should NOT be blocked."""
        result = hook._detect_gh_issue_marker_creation("")
        assert result is None

    # ------------------------------------------------------------------
    # Block message content validation
    # ------------------------------------------------------------------

    def test_block_message_contains_blocked(self, no_pipeline, no_agent):
        """Block message must contain 'BLOCKED'."""
        cmd = "touch /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_block_message_contains_create_issue(self, no_pipeline, no_agent):
        """Block message must reference /create-issue command."""
        cmd = "touch /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None
        assert "/create-issue" in result

    # ------------------------------------------------------------------
    # Deny-by-default bypass regression tests (Issue #627 fix)
    # ------------------------------------------------------------------

    def test_python_json_dump_blocked(self, no_pipeline, no_agent):
        """python3 -c json.dump to marker file should be blocked."""
        cmd = (
            'python3 -c "import json; '
            "json.dump({}, open('/tmp/autonomous_dev_gh_issue_allowed.marker', 'w'))\""
        )
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "json.dump bypass must be blocked"
        assert "BLOCKED" in result

    def test_python_open_wb_blocked(self, no_pipeline, no_agent):
        """python3 -c open('wb') + write to marker file should be blocked."""
        cmd = (
            'python3 -c "f = open(\'/tmp/autonomous_dev_gh_issue_allowed.marker\', \'wb\'); '
            "f.write(b'x')\""
        )
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "open('wb') bypass must be blocked"
        assert "BLOCKED" in result

    def test_python_pickle_dump_blocked(self, no_pipeline, no_agent):
        """python3 -c pickle.dump to marker file should be blocked."""
        cmd = (
            'python3 -c "import pickle; '
            "pickle.dump('x', open('/tmp/autonomous_dev_gh_issue_allowed.marker', 'wb'))\""
        )
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "pickle.dump bypass must be blocked"
        assert "BLOCKED" in result

    def test_python_yaml_dump_blocked(self, no_pipeline, no_agent):
        """python3 -c yaml.dump to marker file should be blocked."""
        cmd = (
            'python3 -c "import yaml; '
            "yaml.dump({'a':1}, open('/tmp/autonomous_dev_gh_issue_allowed.marker', 'w'))\""
        )
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "yaml.dump bypass must be blocked"
        assert "BLOCKED" in result

    def test_python_write_bytes_blocked(self, no_pipeline, no_agent):
        """python3 -c Path.write_bytes to marker file should be blocked."""
        cmd = (
            'python3 -c "Path(\'/tmp/autonomous_dev_gh_issue_allowed.marker\').write_bytes(b\'x\')"'
        )
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "write_bytes bypass must be blocked"
        assert "BLOCKED" in result

    def test_python_shutil_copy_blocked(self, no_pipeline, no_agent):
        """python3 -c shutil.copy to marker file should be blocked."""
        cmd = (
            'python3 -c "import shutil; '
            "shutil.copy('/tmp/src', '/tmp/autonomous_dev_gh_issue_allowed.marker')\""
        )
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "shutil.copy bypass must be blocked"
        assert "BLOCKED" in result

    def test_dd_to_marker_blocked(self, no_pipeline, no_agent):
        """dd of=<marker> should be blocked."""
        cmd = "dd of=/tmp/autonomous_dev_gh_issue_allowed.marker < /dev/zero bs=1 count=1"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "dd bypass must be blocked"
        assert "BLOCKED" in result

    def test_install_to_marker_blocked(self, no_pipeline, no_agent):
        """install /dev/null <marker> should be blocked."""
        cmd = "install /dev/null /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "install bypass must be blocked"
        assert "BLOCKED" in result

    def test_python_os_open_blocked(self, no_pipeline, no_agent):
        """python3 -c os.open + os.write to marker file should be blocked."""
        cmd = (
            'python3 -c "import os; '
            "fd=os.open('/tmp/autonomous_dev_gh_issue_allowed.marker', os.O_CREAT|os.O_WRONLY); "
            "os.write(fd, b'x')\""
        )
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "os.open bypass must be blocked"
        assert "BLOCKED" in result

    def test_echo_with_redirect_to_marker_blocked(self, no_pipeline, no_agent):
        """echo x > <marker> (echo WITH redirect) should be blocked."""
        cmd = "echo x > /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is not None, "echo with redirect to marker must be blocked"
        assert "BLOCKED" in result

    # ------------------------------------------------------------------
    # False positive avoidance (deny-by-default must NOT block these)
    # ------------------------------------------------------------------

    def test_grep_marker_not_blocked(self, no_pipeline, no_agent):
        """grep referencing marker name should NOT be blocked."""
        cmd = "grep autonomous_dev_gh_issue_allowed /var/log/something"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "grep referencing marker must not be blocked"

    def test_echo_mention_no_redirect_not_blocked(self, no_pipeline, no_agent):
        """echo mentioning marker without redirect to marker should NOT be blocked."""
        cmd = 'echo "checking for autonomous_dev_gh_issue_allowed.marker"'
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "echo without redirect to marker must not be blocked"

    def test_test_f_marker_not_blocked(self, no_pipeline, no_agent):
        """test -f <marker> should NOT be blocked."""
        cmd = "test -f /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "test -f must not be blocked"

    def test_bracket_f_marker_not_blocked(self, no_pipeline, no_agent):
        """[ -f <marker> ] should NOT be blocked."""
        cmd = "[ -f /tmp/autonomous_dev_gh_issue_allowed.marker ]"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "[ -f ] must not be blocked"

    def test_stat_marker_not_blocked(self, no_pipeline, no_agent):
        """stat <marker> should NOT be blocked."""
        cmd = "stat /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "stat must not be blocked"

    def test_head_marker_not_blocked(self, no_pipeline, no_agent):
        """head -1 <marker> should NOT be blocked."""
        cmd = "head -1 /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "head must not be blocked"

    def test_cat_marker_not_blocked(self, no_pipeline, no_agent):
        """cat <marker> should NOT be blocked (duplicate of existing for completeness)."""
        cmd = "cat /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "cat must not be blocked"

    def test_rm_marker_not_blocked(self, no_pipeline, no_agent):
        """rm <marker> should NOT be blocked (duplicate of existing for completeness)."""
        cmd = "rm /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "rm must not be blocked"

    def test_ls_marker_not_blocked(self, no_pipeline, no_agent):
        """ls -la <marker> should NOT be blocked (duplicate of existing for completeness)."""
        cmd = "ls -la /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "ls must not be blocked"

    def test_wc_marker_not_blocked(self, no_pipeline, no_agent):
        """wc -l <marker> should NOT be blocked."""
        cmd = "wc -l /tmp/autonomous_dev_gh_issue_allowed.marker"
        result = hook._detect_gh_issue_marker_creation(cmd)
        assert result is None, "wc must not be blocked"


# ---------------------------------------------------------------------------
# TestPlanCommandAllowed — Issue #1203 (plan added to GH_ISSUE_COMMANDS)
# ---------------------------------------------------------------------------

import json as _json


class TestPlanCommandAllowed:
    """Issue #1203 Change A: 'plan' added to GH_ISSUE_COMMANDS.

    plan.md STEP 6 files issues by design when there are >=2 independent work
    items. Whitelisting 'plan' as a recognized command is the minimal fix to
    let the gh issue create calls in plan.md pass through the hook.
    """

    def test_plan_command_in_context_allows(
        self, no_pipeline, no_agent, no_marker, tmp_path
    ):
        """Context file with command='plan' must allow gh issue create."""
        ctx = tmp_path / "ctx.json"
        ctx.write_text(_json.dumps({"command": "plan", "timestamp": "now"}))
        with patch.object(hook, "GH_ISSUE_COMMAND_CONTEXT_PATH", str(ctx)):
            cmd = 'gh issue create --title "feat: split"'
            result = hook._detect_gh_issue_create(cmd)
            assert result is None, "plan command context must allow"

    def test_unknown_command_blocked(
        self, no_pipeline, no_agent, no_marker, tmp_path
    ):
        """Context file with an unknown command must NOT allow (fail-closed)."""
        ctx = tmp_path / "ctx.json"
        ctx.write_text(_json.dumps({"command": "evil-cmd", "timestamp": "now"}))
        with patch.object(hook, "GH_ISSUE_COMMAND_CONTEXT_PATH", str(ctx)):
            cmd = 'gh issue create --title "test"'
            result = hook._detect_gh_issue_create(cmd)
            assert result is not None, "unknown command must NOT allow"
            assert "BLOCKED" in result


# ---------------------------------------------------------------------------
# TestBypassFalsePositive — Issue #1203 Change C (argv-aware backtick/$())
# ---------------------------------------------------------------------------


class TestBypassFalsePositive:
    """Issue #1203 Change C: backtick/$() detection is argv-aware.

    The original bypass detector scanned the RAW command, matching backtick or
    $() substrings that lived INSIDE a --body/--title/--body-file argument
    value — false-positive blocking legitimate gh issue comment calls (and
    other gh subcommands) whose body contained backtick-quoted prose.
    The fix tokenizes via shlex.split, strips body/title/message argument
    values, then runs the regex on the reconstructed command.
    """

    def test_gh_issue_comment_backticked_body_not_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """gh issue comment with prose backticks (NO create pattern) must NOT trip bypass.

        The live-confirmed false positive: backtick-quoted prose in a body that
        does NOT reference 'gh issue create'. Stripping body values + the
        Tier-B value scan (which requires the create pattern to fire) keeps
        this allowed.
        """
        cmd = (
            'gh issue comment 1203 -R akaszubski/autonomous-dev '
            '--body "Diagnosis includes `some helper` mention in prose"'
        )
        assert hook._contains_gh_issue_create_bypass(cmd) is False, (
            "prose backticks WITHOUT the create pattern must not trip bypass"
        )

    def test_gh_issue_comment_dollar_subst_in_body_not_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """gh issue comment with $(echo ...) inside --body must NOT trip bypass.

        The Tier-B value scan only fires when the substitution content matches
        'gh issue create'. Benign $(echo ...) prose stays allowed.
        """
        cmd = (
            'gh issue comment 1203 -R r '
            '--body "see $(echo something) here"'
        )
        assert hook._contains_gh_issue_create_bypass(cmd) is False

    def test_gh_issue_comment_attached_body_arg_not_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """--body=VALUE attached-form strips the value AND scans it for embedded bypass.

        Prose backticks WITHOUT the create pattern stay allowed.
        """
        cmd = (
            'gh issue comment 1203 -R r '
            '--body="prose with `some thing` backticks"'
        )
        assert hook._contains_gh_issue_create_bypass(cmd) is False

    def test_actual_backtick_bypass_still_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """True backtick bypass (at command position) must STILL be blocked."""
        cmd = "RESULT=`gh issue create --title 'x' --body 'y'`"
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_actual_dollar_subst_bypass_still_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """True $() bypass (at command position) must STILL be blocked."""
        cmd = "RESULT=$(gh issue create --title 'x')"
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_malformed_shell_falls_back_to_raw_regex(
        self, no_pipeline, no_agent, no_marker
    ):
        """shlex ValueError on malformed shell must fall back to raw-regex (preserve blocking)."""
        # Unclosed quote => shlex raises ValueError
        cmd = "RESULT=`gh issue create --title 'unterminated"
        # Fallback raw regex should still match the backtick form.
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    # ------------------------------------------------------------------
    # FINDING-2 (Issue #1203 remediation cycle 1): adversarial cases for
    # substitution INSIDE body-flag values that DO contain the create
    # pattern. These execute at shell runtime when the body is double-
    # quoted (and even single-quoted is blocked, fail-closed, because
    # shlex.split(posix=True) discards quote-type info).
    # ------------------------------------------------------------------

    def test_dollar_subst_create_inside_body_value_is_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """FINDING-2: --body "$(gh issue create ...)" MUST be blocked.

        In bash, $() inside double quotes executes — this WOULD create the
        issue at shell runtime. Pre-#1203-cycle-1 this was missed because the
        argv-aware stripper removed the value before the regex scan.
        """
        cmd = 'gh issue comment 1203 --body "$(gh issue create -t x)"'
        assert hook._contains_gh_issue_create_bypass(cmd) is True, (
            "$(gh issue create) inside a body value executes at runtime — must block"
        )

    def test_backtick_create_inside_body_value_is_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """FINDING-2: --body "`gh issue create ...`" MUST be blocked.

        Backticks inside double quotes ALSO execute in bash — equally dangerous
        as the $() form.
        """
        cmd = 'gh issue comment 1203 --body "see `gh issue create -t x`"'
        assert hook._contains_gh_issue_create_bypass(cmd) is True, (
            "backticks inside a body value execute at runtime — must block"
        )

    def test_attached_body_with_dollar_subst_create_is_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """FINDING-2: --body="$(gh issue create ...)" attached form MUST be blocked."""
        cmd = 'gh issue comment 1203 --body="$(gh issue create -t x)"'
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_title_with_dollar_subst_create_is_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """FINDING-2: substitution inside --title value is equally dangerous."""
        cmd = 'gh issue comment 1203 --title "$(gh issue create -t x)" --body ok'
        assert hook._contains_gh_issue_create_bypass(cmd) is True

    def test_single_quoted_create_pattern_in_body_blocked_failclosed(
        self, no_pipeline, no_agent, no_marker
    ):
        """FINDING-2: single-quoted prose containing `gh issue create` in
        backticks — fail-closed (documented tradeoff).

        Single quotes in bash never execute substitutions, so this is technically
        safe prose. But shlex.split(posix=True) discards quote-type information,
        so the implementation cannot distinguish single vs double quotes. We
        fail closed to guarantee no real bypass possible. The cost is one
        flavor of prose false positive (markdown code-formatting of the
        create command in a single-quoted body). Live-confirmed FP (prose
        backticks WITHOUT the create pattern) is preserved as allowed.
        """
        cmd = "gh issue comment 1203 --body 'see `gh issue create` mention'"
        assert hook._contains_gh_issue_create_bypass(cmd) is True, (
            "fail-closed: single-quoted backticks-with-create-pattern still blocks"
        )


# ---------------------------------------------------------------------------
# TestProseFalsePositive — Issue #1215 (argv-position check in direct match)
# ---------------------------------------------------------------------------


class TestProseFalsePositive:
    """Issue #1215: ``_detect_gh_issue_create`` is argv-position-aware.

    Pre-#1215, the direct-match path scanned the quote-stripped command for
    the literal substring ``gh issue create``. When prose containing the
    substring escaped the simple quote stripper (shell-escaped quotes,
    ANSI-C ``$'...'`` quoting, or substrings between unquoted argv tokens),
    the gate falsely blocked the ``git commit`` itself. The #1203 and #1204
    commits were blocked by this — both required ``git commit -F /tmp/file``
    workarounds plus body-rewriting with neutral phrasing.

    The fix uses ``shlex.split`` to tokenize the command into statements and
    argv tokens, then requires that ``gh`` is the leading verb (argv[0] after
    leading env-var assignments) AND the next two tokens are ``issue`` /
    ``create`` (case-insensitive) before declaring a direct match. Body-flag
    VALUES (``-m`` / ``--message`` / ``-F`` / ``--file`` for git;
    ``--body`` / ``--title`` / ``--body-file`` for gh) are stripped before
    tokenization so substring matches inside argument values cannot fire.

    The four required cells (per Issue #1215 spec):
        1. ``-m`` short flag with the substring in the body
        2. ``-m`` short flag with a multi-line body containing the substring
        3. ``-F`` short flag (file-from-disk form)
        4. ``--message`` long flag with the substring inline
    """

    def test_git_commit_m_short_flag_with_substring_in_body_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """Cell 1: ``git commit -m "...gh issue create..."`` MUST NOT be blocked.

        The substring appears as PROSE inside the message body; the leading
        verb is ``git``, not ``gh``. Pre-#1215 this could fire when the
        message body bypassed the quote stripper (e.g., unquoted prose
        between ``-m`` and the next argument).
        """
        cmd = (
            'git commit -m "Reference the gh issue create command in prose, '
            'as the #1203 and #1204 commit bodies did."'
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "git commit -m with substring in prose MUST NOT be blocked "
            f"(Issue #1215); got: {result!r}"
        )

    def test_git_commit_m_multi_line_body_with_substring_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """Cell 2: multi-line ``-m`` body with substring in prose MUST NOT block.

        The verb is ``git``; the entire body is one argv value; no real
        ``gh issue create`` invocation exists. Note: the substring is bare
        prose, NOT wrapped in backticks — backticks-with-create-pattern
        inside a body value remains fail-closed by the bypass detector
        (documented FINDING-2 tradeoff because shlex.split(posix=True)
        discards quote-type info and a double-quoted backtick form would
        execute at shell runtime). The realistic prose case (no backticks)
        is what the #1203 and #1204 commit bodies looked like.
        """
        cmd = (
            'git commit -m "fix(security): #1203 gh-filing allowance four-defect fix\n\n'
            "(3) bypass-detector false-positive — the regex matched prose inside\n"
            "--body argument VALUES, blocking legitimate gh-issue-comment calls\n"
            '(the literal gh issue create substring lived only in prose, not at argv[0])."'
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "git commit -m with multi-line body containing the substring in prose "
            f"MUST NOT be blocked (Issue #1215); got: {result!r}"
        )

    def test_git_commit_F_file_from_disk_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """Cell 3: ``git commit -F /tmp/file_with_prose.txt`` MUST NOT be blocked.

        The hook only sees the file PATH, not the file contents. Even if the
        file on disk contains the substring, the path itself is a normal
        argv value. The verb is ``git``.
        """
        cmd = "git commit -F /tmp/some_body_with_gh_issue_create_in_filename.txt"
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "git commit -F with path argument MUST NOT be blocked "
            f"(Issue #1215); got: {result!r}"
        )

    def test_git_commit_long_message_flag_with_substring_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """Cell 4: ``git commit --message "...gh issue create..."`` MUST NOT block.

        The long-flag form ``--message`` is git's equivalent of ``-m``. The
        substring is prose inside the body; argv[0] is ``git``.
        """
        cmd = (
            'git commit --message "long-flag form of -m with the gh issue create '
            'substring inline in prose body"'
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "git commit --message with substring in body MUST NOT be blocked "
            f"(Issue #1215); got: {result!r}"
        )

    # ------------------------------------------------------------------
    # Adversarial: true bypass forms MUST still be blocked post-#1215
    # ------------------------------------------------------------------

    def test_sh_c_bypass_still_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """sh -c "gh issue create ..." stays blocked (bypass detector)."""
        cmd = 'sh -c "gh issue create --title X --body Y"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_backtick_at_command_position_still_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """RESULT=`gh issue create ...` stays blocked (bypass detector)."""
        cmd = "RESULT=`gh issue create --title test --body details`"
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_subprocess_wrapper_still_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """python3 -c with subprocess.run(['gh','issue','create',...]) stays blocked."""
        cmd = (
            'python3 -c "import subprocess; '
            "subprocess.run(['gh', 'issue', 'create', '--title', 'x'])\""
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_heredoc_piped_to_gh_issue_create_still_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """cat <<EOF ... EOF | gh issue create ... stays blocked.

        Pipe-position verb is ``gh issue create`` — the argv-position check
        sees ``gh`` as the leading verb of the second pipeline segment.
        """
        cmd = (
            "cat <<'EOF' | gh issue create --title test --body details\n"
            "body content\n"
            "EOF"
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "heredoc piped to gh issue create is a real invocation — must block"
        )
        assert "BLOCKED" in result

    def test_unterminated_quote_falls_back_to_raw_regex(
        self, no_pipeline, no_agent, no_marker
    ):
        """Malformed shell (unterminated quote) with the substring → fail-closed.

        shlex.split raises ValueError on unterminated quotes. The
        ``_detect_gh_issue_create`` direct-match path then falls back to the
        raw-regex scan on the quote-stripped command. For a true bypass form
        with garbled syntax this preserves blocking.
        """
        # Unterminated single-quote AROUND the create pattern → shlex fails →
        # raw-regex fallback on the stripped command catches the substring.
        cmd = "RESULT=`gh issue create --title 'unterminated"
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None, (
            "unterminated-quote forms with the literal command at argv "
            "position must fail closed"
        )
        assert "BLOCKED" in result

    def test_git_commit_unterminated_quote_with_substring_blocked_failclosed(
        self, no_pipeline, no_agent, no_marker
    ):
        """Documented tradeoff: unterminated-quote git commit with the substring blocks.

        Per the Issue #1215 spec scenario 9: ``git commit -m "unterminated``
        with the substring in prose hits the raw-regex fallback (shlex
        cannot parse). The substring matches the raw regex; the call is
        blocked. The user fix is to terminate the quote — this is a
        deliberately fail-closed posture, not a regression.
        """
        cmd = 'git commit -m "fix gh issue create '  # unterminated quote
        result = hook._detect_gh_issue_create(cmd)
        # Fail-closed: blocked. The user can fix the unterminated quote.
        assert result is not None, (
            "unterminated quote with the substring is fail-closed (#1215 spec)"
        )
        assert "BLOCKED" in result

    def test_attached_message_flag_with_substring_allowed(
        self, no_pipeline, no_agent, no_marker
    ):
        """``--message=VALUE`` attached form strips the value before substring scan."""
        cmd = (
            'git commit --message="long-form attached, gh issue create in prose"'
        )
        result = hook._detect_gh_issue_create(cmd)
        assert result is None, (
            "--message=VALUE attached form must strip the body value "
            f"(Issue #1215); got: {result!r}"
        )

    def test_pipeline_segment_gh_issue_create_real_command_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """``cat /tmp/body.md | gh issue create ...`` MUST be blocked.

        Two pipeline segments. argv[0] of segment 2 is ``gh issue create``.
        """
        cmd = 'cat /tmp/body.md | gh issue create --title "real"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result

    def test_env_var_assignment_before_real_command_blocked(
        self, no_pipeline, no_agent, no_marker
    ):
        """``FOO=bar gh issue create ...`` MUST be blocked.

        The argv-position helper skips leading env-var assignments and lands
        on ``gh`` as the verb. Without this, FOO=bar would mask the bypass.
        """
        cmd = 'FOO=bar gh issue create --title "test"'
        result = hook._detect_gh_issue_create(cmd)
        assert result is not None
        assert "BLOCKED" in result


# ---------------------------------------------------------------------------
# TestGhIssueCreateAtCommandPosition — unit tests for the argv helper
# ---------------------------------------------------------------------------


class TestGhIssueCreateAtCommandPosition:
    """Unit tests for ``_gh_issue_create_at_command_position`` (Issue #1215)."""

    def test_bare_gh_issue_create_detected(self):
        assert hook._gh_issue_create_at_command_position(
            "gh issue create --title x"
        ) is True

    def test_gh_issue_list_not_detected(self):
        assert hook._gh_issue_create_at_command_position(
            "gh issue list --state open"
        ) is False

    def test_gh_pr_create_not_detected(self):
        assert hook._gh_issue_create_at_command_position(
            "gh pr create --title x"
        ) is False

    def test_git_commit_with_substring_not_detected(self):
        assert hook._gh_issue_create_at_command_position(
            'git commit -m "fix gh issue create gate"'
        ) is False

    def test_env_var_prefix_gh_issue_create_detected(self):
        assert hook._gh_issue_create_at_command_position(
            "FOO=bar gh issue create --title x"
        ) is True

    def test_pipeline_segment_gh_issue_create_detected(self):
        assert hook._gh_issue_create_at_command_position(
            "cat body.md | gh issue create --title x"
        ) is True

    def test_semicolon_then_gh_issue_create_detected(self):
        assert hook._gh_issue_create_at_command_position(
            "export FOO=bar; gh issue create --title x"
        ) is True

    def test_sh_wrapper_not_detected_at_this_layer(self):
        """sh -c "gh issue create ..." is bypass-detector territory, not direct."""
        assert hook._gh_issue_create_at_command_position(
            'sh -c "gh issue create --title x"'
        ) is False

    def test_empty_command(self):
        assert hook._gh_issue_create_at_command_position("") is False

    def test_case_insensitive_match(self):
        assert hook._gh_issue_create_at_command_position(
            "GH Issue Create --title x"
        ) is True


# ---------------------------------------------------------------------------
# TestStripBodyArgValues — unit tests for the hoisted body-stripping helper
# ---------------------------------------------------------------------------


class TestStripBodyArgValues:
    """Unit tests for ``_strip_body_arg_values`` (hoisted in Issue #1215)."""

    def test_strip_dash_m_short_flag(self):
        stripped, dropped = hook._strip_body_arg_values(
            'git commit -m "prose body"'
        )
        assert "prose body" not in stripped
        assert "prose body" in dropped

    def test_strip_long_message_flag(self):
        stripped, dropped = hook._strip_body_arg_values(
            'git commit --message "long form body"'
        )
        assert "long form body" not in stripped
        assert "long form body" in dropped

    def test_strip_dash_F_file_flag(self):
        stripped, dropped = hook._strip_body_arg_values(
            "git commit -F /tmp/body.txt"
        )
        assert "/tmp/body.txt" not in stripped
        assert "/tmp/body.txt" in dropped

    def test_strip_long_file_flag(self):
        stripped, dropped = hook._strip_body_arg_values(
            "git commit --file /tmp/body.txt"
        )
        assert "/tmp/body.txt" not in stripped
        assert "/tmp/body.txt" in dropped

    def test_strip_attached_message_form(self):
        stripped, dropped = hook._strip_body_arg_values(
            'git commit --message="attached form body"'
        )
        assert "attached form body" not in stripped
        assert "attached form body" in dropped

    def test_strip_gh_body_flag(self):
        stripped, dropped = hook._strip_body_arg_values(
            'gh issue comment 123 --body "comment text"'
        )
        assert "comment text" not in stripped
        assert "comment text" in dropped

    def test_strip_gh_title_flag(self):
        stripped, dropped = hook._strip_body_arg_values(
            'gh issue create --title "title prose"'
        )
        assert "title prose" not in stripped
        assert "title prose" in dropped

    def test_malformed_shell_raises(self):
        """Unterminated quote raises ValueError for caller fallback."""
        with pytest.raises(ValueError):
            hook._strip_body_arg_values('git commit -m "unterminated')

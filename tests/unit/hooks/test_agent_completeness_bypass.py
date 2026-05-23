"""
Regression tests for agent completeness gate bypass mechanisms in unified_pre_tool.py.

Issue #802 fix: The agent completeness gate had two bypass mechanisms that did not
work when the model tried to use them:

1. Inline env var (SKIP_AGENT_COMPLETENESS_GATE=1 git commit ...) -- The hook reads
   os.environ (its own process env), but inline vars only affect the child process.
   Fix: Parse the command string for the inline env var.

2. File-based bypass (touch /tmp/skip_agent_completeness_gate && git commit ...) --
   The hook intercepts the entire Bash tool call before any part executes, so `touch`
   in a compound command never runs.
   Fix: Updated block messages to say "run as a SEPARATE command first".

Date: 2026-04-19
"""

import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add hook's parent to path so we can import the module
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOK_DIR))

# Also add lib dir for any transitive imports
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Reset relevant env vars for each test.

    Also chdir to a temp directory so the hook's ``cwd`` check at
    unified_pre_tool.py:4832 does not see ``.worktrees/batch-`` in the
    path. When tests run from a worktree whose path contains that
    substring (e.g. ``.worktrees/batch-20260523-223202``), the hook
    routes through the batch-mode agent-completeness branch instead of
    the non-batch branch that ``_check_pipeline_agent_completions`` (the
    function these tests patch) lives on. The batch branch reads real
    on-disk state and returns ``allow`` when no state exists, causing
    the gate-blocks-without-bypass tests to receive ``allow`` instead of
    the expected ``deny``. Issue #956.
    """
    env_keys = [
        "SKIP_AGENT_COMPLETENESS_GATE", "CLAUDE_SESSION_ID",
        "PIPELINE_MODE", "PIPELINE_ISSUE_NUMBER", "PIPELINE_STATE_FILE",
        "SANDBOX_ENABLED", "PRE_TOOL_MCP_SECURITY", "PRE_TOOL_AGENT_AUTH",
        "PRE_TOOL_BATCH_PERMISSION", "MCP_AUTO_APPROVE", "ENFORCEMENT_LEVEL",
        "CLAUDE_AGENT_NAME", "PRE_TOOL_PIPELINE_ORDERING",
        "SKIP_BATCH_CIA_GATE", "SKIP_BATCH_DOC_MASTER_GATE",
        "PIPELINE_CLEANUP_PHASE",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    # Defaults: MCP security on, agent auth on
    monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "true")
    monkeypatch.setenv("PRE_TOOL_AGENT_AUTH", "true")
    # Isolate from worktree cwd that triggers batch-mode hook branch (Issue #956)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def skip_gate_file():
    """Manage the /tmp/skip_agent_completeness_gate file for tests."""
    path = Path("/tmp/skip_agent_completeness_gate")
    yield path
    # Cleanup after test
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _make_hook_input(command: str) -> str:
    """Create JSON input for the hook simulating a Bash tool call with a git commit."""
    return json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "session_id": "test-session-bypass",
    })


def _run_hook_and_capture(hook_input_json: str) -> dict:
    """Run the hook main() with mocked stdin/stdout and return parsed output.

    Returns the parsed JSON output dict, or an empty dict if the hook allowed
    (reached the end without printing a deny decision for the completeness gate).
    """
    captured_output = io.StringIO()

    with patch("sys.stdin", io.StringIO(hook_input_json)), \
         patch("sys.stdout", captured_output), \
         patch.object(hook, "load_env", return_value=None):
        try:
            hook.main()
        except SystemExit:
            pass

    output_str = captured_output.getvalue().strip()
    if not output_str:
        return {}

    # The hook may print multiple JSON lines (unlikely but possible)
    # Take the last one as the final decision
    lines = output_str.strip().split("\n")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInlineEnvVarBypass:
    """Test that SKIP_AGENT_COMPLETENESS_GATE=1 in the command string triggers bypass."""

    def test_inline_env_var_bypasses_gate(self, monkeypatch):
        """When command contains 'SKIP_AGENT_COMPLETENESS_GATE=1 git commit ...',
        the gate must NOT block."""
        command = 'SKIP_AGENT_COMPLETENESS_GATE=1 git commit -m "test bypass"'
        hook_input = _make_hook_input(command)

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value="BLOCKED: missing implementer"), \
             patch.object(hook, "_log_pretool_activity", return_value=None), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            result = _run_hook_and_capture(hook_input)

        # If the gate blocked, the output would contain "Agent completeness gate"
        reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "Agent completeness gate" not in reason, (
            f"Gate should NOT have blocked with inline env var bypass, but got: {reason}"
        )

    def test_inline_env_var_true_bypasses_gate(self, monkeypatch):
        """When command contains 'SKIP_AGENT_COMPLETENESS_GATE=true git commit ...',
        the gate must NOT block (case-insensitive)."""
        command = 'SKIP_AGENT_COMPLETENESS_GATE=true git commit -m "test bypass"'
        hook_input = _make_hook_input(command)

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value="BLOCKED: missing implementer"), \
             patch.object(hook, "_log_pretool_activity", return_value=None), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            result = _run_hook_and_capture(hook_input)

        reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "Agent completeness gate" not in reason, (
            f"Gate should NOT have blocked with inline env var bypass (true), but got: {reason}"
        )


class TestFileBasedBypass:
    """Test that pre-existing /tmp/skip_agent_completeness_gate file triggers bypass."""

    def test_file_based_bypass_works(self, monkeypatch, skip_gate_file):
        """When /tmp/skip_agent_completeness_gate exists before the check,
        the gate must NOT block, and the file should be cleaned up."""
        # Create the bypass file
        skip_gate_file.touch()
        assert skip_gate_file.exists(), "Bypass file should exist before test"

        command = 'git commit -m "test file bypass"'
        hook_input = _make_hook_input(command)

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value="BLOCKED: missing implementer"), \
             patch.object(hook, "_log_pretool_activity", return_value=None), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            result = _run_hook_and_capture(hook_input)

        reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "Agent completeness gate" not in reason, (
            f"Gate should NOT have blocked with file-based bypass, but got: {reason}"
        )

        # File should be cleaned up
        assert not skip_gate_file.exists(), "Bypass file should be cleaned up after use"


class TestGateBlocksWithoutBypass:
    """Test that the gate blocks when no bypass mechanism is present."""

    def test_gate_blocks_without_bypass(self, monkeypatch):
        """Without any bypass, the gate must block when agents are missing."""
        command = 'git commit -m "test no bypass"'
        hook_input = _make_hook_input(command)

        # Ensure no file-based bypass exists
        skip_file = Path("/tmp/skip_agent_completeness_gate")
        if skip_file.exists():
            skip_file.unlink()

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value=(
                 "BLOCKED: Agent completeness gate -- missing required agents: "
                 "implementer. Completed: (none). "
                 "All required pipeline agents MUST complete before git commit."
             )), \
             patch.object(hook, "_log_pretool_activity", return_value=None), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            result = _run_hook_and_capture(hook_input)

        decision = result.get("hookSpecificOutput", {}).get("permissionDecision", "")
        reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert decision == "deny", (
            f"Gate should block with deny when no bypass is present, got: {decision}"
        )
        assert "Agent completeness gate" in reason or "agent completeness" in reason.lower(), (
            f"Block reason should mention agent completeness gate, got: {reason}"
        )


class TestProcessEnvVarBypass:
    """Test that setting SKIP_AGENT_COMPLETENESS_GATE in os.environ triggers bypass."""

    def test_process_env_var_bypasses_gate(self, monkeypatch):
        """When SKIP_AGENT_COMPLETENESS_GATE=1 is in the process environment,
        the gate must NOT block."""
        monkeypatch.setenv("SKIP_AGENT_COMPLETENESS_GATE", "1")

        command = 'git commit -m "test env bypass"'
        hook_input = _make_hook_input(command)

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value="BLOCKED: missing implementer"), \
             patch.object(hook, "_log_pretool_activity", return_value=None), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            result = _run_hook_and_capture(hook_input)

        reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "Agent completeness gate" not in reason, (
            f"Gate should NOT have blocked with process env var bypass, but got: {reason}"
        )


class TestBlockMessageClarification:
    """Test that block messages clarify file-based bypass must be a SEPARATE command."""

    def test_non_batch_block_message_says_separate_command(self, monkeypatch):
        """The block message from _check_pipeline_agent_completions should say
        'as a SEPARATE command first'."""
        # We test the actual function output here, not via main()
        # Mock the pipeline_completion_state module import
        mock_mod = MagicMock()
        mock_mod.verify_pipeline_agent_completions.return_value = (
            False,  # passed
            {"researcher"},  # completed
            {"implementer"},  # missing
        )

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch("importlib.util.spec_from_file_location") as mock_spec_fn, \
             patch("importlib.util.module_from_spec", return_value=mock_mod), \
             patch.object(hook, "_get_pipeline_mode_from_state", return_value="full"):

            mock_spec = MagicMock()
            mock_spec.loader = MagicMock()
            mock_spec_fn.return_value = mock_spec

            # Mock one of the lib_candidates to exist
            with patch.object(Path, "exists", return_value=True):
                result = hook._check_pipeline_agent_completions("test-session")

        assert result is not None, "Should return a block message when agents are missing"
        assert "SEPARATE command first" in result, (
            f"Block message should say 'SEPARATE command first', got: {result}"
        )
        assert "then retry the commit" in result, (
            f"Block message should say 'then retry the commit', got: {result}"
        )


class TestCommandStringBypassSecurity:
    """Security: bypass string in commit messages must NOT trigger bypass."""

    def test_commit_message_containing_bypass_string_does_not_bypass(self, monkeypatch):
        """A git commit message that mentions SKIP_AGENT_COMPLETENESS_GATE=1
        must NOT trigger the command-string bypass. The bypass must only match
        when the env var appears at the START of the command (shell prefix position)."""
        command = 'git commit -m "fix: handle SKIP_AGENT_COMPLETENESS_GATE=1 edge case"'
        hook_input = _make_hook_input(command)

        # Ensure no file-based bypass exists
        skip_file = Path("/tmp/skip_agent_completeness_gate")
        if skip_file.exists():
            skip_file.unlink()

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value=(
                 "BLOCKED: Agent completeness gate -- missing required agents: "
                 "implementer. Completed: (none). "
                 "All required pipeline agents MUST complete before git commit."
             )), \
             patch.object(hook, "_log_pretool_activity", return_value=None), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            result = _run_hook_and_capture(hook_input)

        decision = result.get("hookSpecificOutput", {}).get("permissionDecision", "")
        reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert decision == "deny", (
            f"Gate should BLOCK when bypass string is in commit message, got decision: {decision}"
        )
        assert "Agent completeness gate" in reason or "agent completeness" in reason.lower(), (
            f"Block reason should mention agent completeness gate, got: {reason}"
        )

    def test_bypass_string_after_semicolon_does_not_bypass(self, monkeypatch):
        """A command like 'echo SKIP_AGENT_COMPLETENESS_GATE=1; git commit ...'
        must NOT bypass the gate -- the env var is not at the command start."""
        command = 'echo SKIP_AGENT_COMPLETENESS_GATE=1; git commit -m "test"'
        hook_input = _make_hook_input(command)

        skip_file = Path("/tmp/skip_agent_completeness_gate")
        if skip_file.exists():
            skip_file.unlink()

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value=(
                 "BLOCKED: Agent completeness gate -- missing required agents: "
                 "implementer. Completed: (none). "
                 "All required pipeline agents MUST complete before git commit."
             )), \
             patch.object(hook, "_log_pretool_activity", return_value=None), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            result = _run_hook_and_capture(hook_input)

        decision = result.get("hookSpecificOutput", {}).get("permissionDecision", "")
        assert decision == "deny", (
            f"Gate should BLOCK when bypass string is after semicolon, got decision: {decision}"
        )


class TestBypassLogging:
    """Test that bypass activations are logged via _log_pretool_activity."""

    def test_file_bypass_logs_activity(self, monkeypatch, skip_gate_file):
        """When file-based bypass activates, _log_pretool_activity must be called
        with a reason starting with 'bypass:'."""
        skip_gate_file.touch()

        command = 'git commit -m "test file bypass logging"'
        hook_input = _make_hook_input(command)

        log_mock = MagicMock(return_value=None)

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value="BLOCKED: missing implementer"), \
             patch.object(hook, "_log_pretool_activity", log_mock), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            _run_hook_and_capture(hook_input)

        # Find calls with "bypass:" in the reason
        bypass_calls = [
            call for call in log_mock.call_args_list
            if len(call.args) >= 4 and "bypass:" in str(call.args[3])
        ]
        assert len(bypass_calls) >= 1, (
            f"Expected at least one _log_pretool_activity call with 'bypass:' reason, "
            f"got calls: {log_mock.call_args_list}"
        )
        assert "file-based" in str(bypass_calls[0].args[3]), (
            f"Expected file-based bypass log, got: {bypass_calls[0].args[3]}"
        )

    def test_command_bypass_logs_activity(self, monkeypatch):
        """When inline env var bypass activates, _log_pretool_activity must be called
        with a reason starting with 'bypass:'."""
        command = 'SKIP_AGENT_COMPLETENESS_GATE=1 git commit -m "test cmd bypass logging"'
        hook_input = _make_hook_input(command)

        log_mock = MagicMock(return_value=None)

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value="BLOCKED: missing implementer"), \
             patch.object(hook, "_log_pretool_activity", log_mock), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            _run_hook_and_capture(hook_input)

        bypass_calls = [
            call for call in log_mock.call_args_list
            if len(call.args) >= 4 and "bypass:" in str(call.args[3])
        ]
        assert len(bypass_calls) >= 1, (
            f"Expected at least one _log_pretool_activity call with 'bypass:' reason, "
            f"got calls: {log_mock.call_args_list}"
        )
        assert "inline env var" in str(bypass_calls[0].args[3]), (
            f"Expected inline env var bypass log, got: {bypass_calls[0].args[3]}"
        )

    def test_env_var_bypass_logs_activity(self, monkeypatch):
        """When SKIP_AGENT_COMPLETENESS_GATE is set in process environment,
        _log_pretool_activity must be called with a reason starting with 'bypass:'."""
        monkeypatch.setenv("SKIP_AGENT_COMPLETENESS_GATE", "1")

        command = 'git commit -m "test env bypass logging"'
        hook_input = _make_hook_input(command)

        log_mock = MagicMock(return_value=None)

        with patch.object(hook, "_is_pipeline_active", return_value=True), \
             patch.object(hook, "_check_pipeline_agent_completions", return_value="BLOCKED: missing implementer"), \
             patch.object(hook, "_log_pretool_activity", log_mock), \
             patch.object(hook, "_log_deviation", return_value=None), \
             patch.object(hook, "_check_bash_infra_writes", return_value=None), \
             patch.object(hook, "_detect_env_spoofing", return_value=None), \
             patch.object(hook, "_detect_gh_issue_marker_creation", return_value=None), \
             patch.object(hook, "_detect_gh_issue_create", return_value=None), \
             patch.object(hook, "_detect_settings_json_write", return_value=None), \
             patch.object(hook, "_check_bash_state_deletion", return_value=None), \
             patch.object(hook, "_extract_bash_spec_test_targets", return_value=[]), \
             patch.object(hook, "_extract_bash_file_writes", return_value=[]):
            _run_hook_and_capture(hook_input)

        bypass_calls = [
            call for call in log_mock.call_args_list
            if len(call.args) >= 4 and "bypass:" in str(call.args[3])
        ]
        assert len(bypass_calls) >= 1, (
            f"Expected at least one _log_pretool_activity call with 'bypass:' reason, "
            f"got calls: {log_mock.call_args_list}"
        )
        assert "process environment" in str(bypass_calls[0].args[3]), (
            f"Expected process environment bypass log, got: {bypass_calls[0].args[3]}"
        )

#!/usr/bin/env python3
"""
Unit tests for unified_pre_tool.py hook.

Tests layer dispatch logic, error handling, JSON output format,
and environment variable controls (DISABLE_* flags).

Date: 2026-02-21
Agent: test-master
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO

# Add hooks directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

import unified_pre_tool as upt


class TestCombineDecisions:
    """Test the combine_decisions logic."""

    def test_all_allow(self):
        results = [
            ("Sandbox", "allow", "ok"),
            ("MCP", "allow", "ok"),
            ("Agent", "allow", "ok"),
        ]
        decision, reason = upt.combine_decisions(results)
        assert decision == "allow"

    def test_any_deny(self):
        results = [
            ("Sandbox", "allow", "ok"),
            ("MCP", "deny", "blocked"),
            ("Agent", "allow", "ok"),
        ]
        decision, reason = upt.combine_decisions(results)
        assert decision == "deny"
        assert "blocked" in reason

    def test_multiple_deny(self):
        results = [
            ("Sandbox", "deny", "bad sandbox"),
            ("MCP", "deny", "bad mcp"),
        ]
        decision, reason = upt.combine_decisions(results)
        assert decision == "deny"
        assert "bad sandbox" in reason
        assert "bad mcp" in reason

    def test_ask_when_mixed(self):
        results = [
            ("Sandbox", "allow", "ok"),
            ("MCP", "ask", "needs approval"),
        ]
        decision, reason = upt.combine_decisions(results)
        assert decision == "ask"
        assert "needs approval" in reason

    def test_empty_results(self):
        decision, reason = upt.combine_decisions([])
        assert decision == "allow"

    def test_deny_trumps_ask(self):
        results = [
            ("A", "ask", "maybe"),
            ("B", "deny", "no"),
        ]
        decision, reason = upt.combine_decisions(results)
        assert decision == "deny"


class TestValidateSandboxLayer:
    """Test sandbox layer validation."""

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SANDBOX_ENABLED", None)
            decision, reason = upt.validate_sandbox_layer("Bash", {"command": "ls"})
            assert decision == "allow"
            assert "disabled" in reason.lower()

    def test_non_bash_tool(self):
        with patch.dict(os.environ, {"SANDBOX_ENABLED": "true"}):
            decision, reason = upt.validate_sandbox_layer("Read", {"file_path": "/tmp/x"})
            assert decision == "allow"

    def test_empty_command(self):
        with patch.dict(os.environ, {"SANDBOX_ENABLED": "true"}):
            decision, reason = upt.validate_sandbox_layer("Bash", {"command": ""})
            assert decision == "allow"

    def test_import_error_fallback(self):
        with patch.dict(os.environ, {"SANDBOX_ENABLED": "true"}):
            with patch.dict("sys.modules", {"sandbox_enforcer": None}):
                decision, reason = upt.validate_sandbox_layer("Bash", {"command": "rm -rf /"})
                # When sandbox_enforcer can't be imported, returns ask
                assert decision in ("ask", "deny")  # deny if enforcer is available, ask if not


class TestValidateMcpSecurity:
    """Test MCP security layer."""

    def test_native_tool_bypass(self):
        for tool in ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]:
            decision, reason = upt.validate_mcp_security(tool, {})
            assert decision == "allow"
            assert "Native tool" in reason

    def test_disabled_via_env(self):
        with patch.dict(os.environ, {"PRE_TOOL_MCP_SECURITY": "false"}):
            decision, reason = upt.validate_mcp_security("mcp_custom_tool", {})
            assert decision == "allow"
            assert "disabled" in reason.lower()

    def test_unknown_mcp_tool_no_auto_approve(self):
        with patch.dict(os.environ, {"PRE_TOOL_MCP_SECURITY": "true", "MCP_AUTO_APPROVE": "false"}):
            decision, reason = upt.validate_mcp_security("mcp_custom_tool", {})
            assert decision == "ask"

    def test_unknown_mcp_tool_auto_approve_no_engine(self):
        with patch.dict(os.environ, {"PRE_TOOL_MCP_SECURITY": "true", "MCP_AUTO_APPROVE": "true"}):
            # auto_approval_engine may or may not be importable
            decision, reason = upt.validate_mcp_security("mcp_custom_tool", {})
            # If engine available: allow/ask depending on policy; if not: allow pass through
            assert decision in ("allow", "ask")

    def test_all_native_tools_listed(self):
        """Verify known native tools are in the set."""
        expected = {"Read", "Write", "Edit", "Glob", "Grep", "Bash", "Task", "TaskOutput"}
        assert expected.issubset(upt.NATIVE_TOOLS)


class TestValidateAgentAuthorization:
    """Test agent authorization layer."""

    def test_disabled_via_env(self):
        with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "false"}):
            decision, reason = upt.validate_agent_authorization("Edit", {"file_path": "app.py"})
            assert decision == "allow"

    def test_pipeline_agent_allowed(self):
        with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "true", "CLAUDE_AGENT_NAME": "implementer"}):
            decision, reason = upt.validate_agent_authorization("Edit", {"file_path": "app.py"})
            assert decision == "allow"
            assert "Pipeline agent" in reason

    def test_non_code_tool_allowed(self):
        with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "true", "CLAUDE_AGENT_NAME": ""}, clear=False):
            os.environ.pop("PIPELINE_STATE_FILE", None)
            decision, reason = upt.validate_agent_authorization("Read", {"file_path": "app.py"})
            assert decision == "allow"

    def test_exempt_path_allowed(self):
        with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "true", "CLAUDE_AGENT_NAME": "", "ENFORCEMENT_LEVEL": "block"}, clear=False):
            os.environ.pop("PIPELINE_STATE_FILE", None)
            decision, reason = upt.validate_agent_authorization(
                "Edit", {"file_path": "tests/test_foo.py", "old_string": "a", "new_string": "b"}
            )
            assert decision == "allow"

    def test_enforcement_off(self):
        with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "true", "CLAUDE_AGENT_NAME": "", "ENFORCEMENT_LEVEL": "off"}, clear=False):
            os.environ.pop("PIPELINE_STATE_FILE", None)
            decision, reason = upt.validate_agent_authorization("Edit", {"file_path": "app.py"})
            assert decision == "allow"

    def test_non_code_extension_allowed(self):
        with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "true", "CLAUDE_AGENT_NAME": "", "ENFORCEMENT_LEVEL": "block"}, clear=False):
            os.environ.pop("PIPELINE_STATE_FILE", None)
            decision, reason = upt.validate_agent_authorization(
                "Edit", {"file_path": "config.json", "old_string": "a", "new_string": "b"}
            )
            assert decision == "allow"

    def test_block_significant_edit(self):
        with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "true", "CLAUDE_AGENT_NAME": "", "ENFORCEMENT_LEVEL": "block"}, clear=False):
            os.environ.pop("PIPELINE_STATE_FILE", None)
            new_code = "def foo():\n    pass\ndef bar():\n    pass\ndef baz():\n    x=1\n    y=2\n    z=3\n"
            decision, reason = upt.validate_agent_authorization(
                "Edit", {"file_path": "app.py", "old_string": "", "new_string": new_code}
            )
            assert decision == "deny"

    def test_suggest_level(self):
        with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "true", "CLAUDE_AGENT_NAME": "", "ENFORCEMENT_LEVEL": "suggest"}, clear=False):
            os.environ.pop("PIPELINE_STATE_FILE", None)
            new_code = "def foo():\n    pass\ndef bar():\n    pass\ndef baz():\n    x=1\n    y=2\n    z=3\n"
            decision, reason = upt.validate_agent_authorization(
                "Edit", {"file_path": "app.py", "old_string": "", "new_string": new_code}
            )
            assert decision == "allow"
            assert "Tip" in reason

    def test_minor_edit_allowed(self):
        with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "true", "CLAUDE_AGENT_NAME": "", "ENFORCEMENT_LEVEL": "block"}, clear=False):
            os.environ.pop("PIPELINE_STATE_FILE", None)
            decision, reason = upt.validate_agent_authorization(
                "Edit", {"file_path": "app.py", "old_string": "x = 1", "new_string": "x = 2"}
            )
            assert decision == "allow"


class TestValidateBatchPermission:
    """Test batch permission layer."""

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PRE_TOOL_BATCH_PERMISSION", None)
            decision, reason = upt.validate_batch_permission("Edit", {})
            assert decision == "allow"
            assert "disabled" in reason.lower()

    def test_enabled_no_classifier(self):
        with patch.dict(os.environ, {"PRE_TOOL_BATCH_PERMISSION": "true"}):
            decision, reason = upt.validate_batch_permission("Edit", {})
            # If classifier available: returns based on classification; if not: allow
            assert decision in ("allow", "ask")


class TestOutputDecision:
    """Test JSON output format."""

    def test_output_format(self, capsys):
        upt.output_decision("allow", "test reason")
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert output["hookSpecificOutput"]["permissionDecisionReason"] == "test reason"

    def test_deny_format(self, capsys):
        upt.output_decision("deny", "blocked")
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_ask_format(self, capsys):
        upt.output_decision("ask", "needs input")
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "ask"


class TestHelperFunctions:
    """Test internal helper functions."""

    def test_is_exempt_path_test_file(self):
        assert upt._is_exempt_path("tests/test_foo.py") is True
        assert upt._is_exempt_path("test_foo.py") is True

    def test_is_exempt_path_docs(self):
        assert upt._is_exempt_path("README.md") is True
        assert upt._is_exempt_path("config.json") is True

    def test_is_exempt_path_code_file(self):
        assert upt._is_exempt_path("src/app.py") is False

    def test_is_exempt_path_empty(self):
        assert upt._is_exempt_path("") is False

    def test_is_exempt_path_hooks(self):
        assert upt._is_exempt_path(".claude/hooks/my_hook.py") is True

    def test_has_significant_additions_function(self):
        is_sig, reason, details = upt._has_significant_additions(
            "", "def new_func():\n    pass\n", "app.py"
        )
        assert is_sig is True
        assert "function" in reason.lower()

    def test_has_significant_additions_minor(self):
        is_sig, reason, details = upt._has_significant_additions(
            "x = 1", "x = 2", "app.py"
        )
        assert is_sig is False

    def test_has_significant_additions_lines(self):
        old = "line1\n"
        new = "line1\nline2\nline3\nline4\nline5\nline6\n"
        is_sig, reason, details = upt._has_significant_additions(old, new, "app.py")
        assert is_sig is True
        assert "lines" in details

    def test_extract_bash_file_writes_redirect(self):
        files = upt._extract_bash_file_writes("echo hello > output.py")
        assert "output.py" in files

    def test_extract_bash_file_writes_tee(self):
        files = upt._extract_bash_file_writes("echo hello | tee output.py")
        assert "output.py" in files

    def test_extract_bash_file_writes_dev_null(self):
        files = upt._extract_bash_file_writes("cmd > /dev/null")
        assert len(files) == 0

    def test_extract_bash_file_writes_no_writes(self):
        files = upt._extract_bash_file_writes("ls -la")
        assert len(files) == 0


class TestLoadEnv:
    """Test .env loading."""

    def test_load_env_no_file(self, tmp_path):
        with patch("os.getcwd", return_value=str(tmp_path)):
            upt.load_env()  # Should not raise

    def test_load_env_with_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR_UNIQUE_12345=hello\n")
        with patch("os.getcwd", return_value=str(tmp_path)):
            os.environ.pop("TEST_VAR_UNIQUE_12345", None)
            upt.load_env()
            assert os.environ.get("TEST_VAR_UNIQUE_12345") == "hello"
            del os.environ["TEST_VAR_UNIQUE_12345"]

    def test_load_env_skips_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\nKEY_UNIQUE_99=val\n")
        with patch("os.getcwd", return_value=str(tmp_path)):
            os.environ.pop("KEY_UNIQUE_99", None)
            upt.load_env()
            assert os.environ.get("KEY_UNIQUE_99") == "val"
            del os.environ["KEY_UNIQUE_99"]

    def test_load_env_does_not_override(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("PATH=/bad\n")
        with patch("os.getcwd", return_value=str(tmp_path)):
            original_path = os.environ["PATH"]
            upt.load_env()
            assert os.environ["PATH"] == original_path


class TestMain:
    """Test main entry point."""

    def test_invalid_json_input(self, capsys):
        with patch("sys.stdin", StringIO("not json")):
            with pytest.raises(SystemExit) as exc_info:
                upt.main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "ask"
        assert "Invalid input JSON" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_empty_tool_name(self, capsys):
        with patch("sys.stdin", StringIO(json.dumps({"tool_name": "", "tool_input": {}}))):
            with pytest.raises(SystemExit) as exc_info:
                upt.main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_valid_native_tool(self, capsys):
        inp = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}})
        with patch("sys.stdin", StringIO(inp)):
            with patch.dict(os.environ, {"PRE_TOOL_AGENT_AUTH": "true", "CLAUDE_AGENT_NAME": ""}, clear=False):
                with pytest.raises(SystemExit) as exc_info:
                    upt.main()
                assert exc_info.value.code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

#!/usr/bin/env python3
"""
Unit tests for enforce_implementation_workflow.py hook (Issue #139).

Tests autonomous implementation detection and workflow enforcement.
These tests should FAIL initially (TDD red phase) until implementation is complete.

Hook Purpose:
- Catches Claude's autonomous decisions to implement features without /auto-implement
- Complements detect_feature_request.py (which catches explicit user requests)
- Blocks significant code changes (new functions, classes, >10 lines) outside proper workflow

Test Coverage Target: 95%+

Author: test-master agent
Date: 2025-12-14
Issue: #139
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

from enforce_implementation_workflow import (
    count_new_lines,
    has_significant_additions,
    is_code_file,
    load_env,
    main,
    output_decision,
)


class TestSignificantChangeDetection:
    """Test detection of significant code additions."""

    def test_detects_python_function_addition(self):
        """Test detection of new Python function definition."""
        old_string = "# Empty file\n"
        new_string = """# Empty file
def authenticate_user(username, password):
    return True
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "Python function" in reason
        assert "def" in details

    def test_detects_python_async_function_addition(self):
        """Test detection of new Python async function."""
        old_string = "pass\n"
        new_string = """async def fetch_data(url):
    return await client.get(url)
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "async function" in reason.lower()

    def test_detects_python_class_addition(self):
        """Test detection of new Python class."""
        old_string = "# Module\n"
        new_string = """class UserManager:
    def __init__(self):
        self.users = []
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "class" in reason.lower()

    def test_detects_javascript_function_addition(self):
        """Test detection of new JavaScript function."""
        old_string = "// Empty\n"
        new_string = """function handleLogin(user) {
    return validateCredentials(user);
}
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "JavaScript function" in reason

    def test_detects_javascript_async_function_addition(self):
        """Test detection of new JavaScript async function."""
        old_string = "// Module\n"
        new_string = """async function fetchUserData(id) {
    const response = await fetch(`/api/users/${id}`);
    return response.json();
}
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "async function" in reason.lower()

    def test_detects_arrow_function_addition(self):
        """Test detection of new arrow function."""
        old_string = "const exports = {};\n"
        new_string = """const handleClick = (event) => {
    event.preventDefault();
    submitForm();
};
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "arrow function" in reason.lower()

    def test_detects_export_addition(self):
        """Test detection of new export."""
        old_string = "// Module\n"
        new_string = """export function validateEmail(email) {
    return /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email);
}
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "export" in reason.lower()

    def test_detects_go_function_addition(self):
        """Test detection of new Go function."""
        old_string = "package main\n"
        new_string = """package main

func HandleRequest(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte("Hello"))
}
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "Go function" in reason

    def test_detects_rust_function_addition(self):
        """Test detection of new Rust function."""
        old_string = "// Module\n"
        new_string = """fn calculate_sum(a: i32, b: i32) -> i32 {
    a + b
}
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "Rust function" in reason

    def test_detects_rust_impl_addition(self):
        """Test detection of new Rust impl block."""
        old_string = "struct Point { x: i32, y: i32 }\n"
        new_string = """struct Point { x: i32, y: i32 }

impl Point {
    fn new(x: i32, y: i32) -> Self {
        Point { x, y }
    }
}
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "impl" in reason.lower()

    def test_detects_java_method_addition(self):
        """Test detection of new Java method."""
        old_string = "class User {}\n"
        new_string = """class User {
    public String getName() {
        return this.name;
    }
}
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "Java method" in reason

    def test_detects_significant_line_additions(self):
        """Test detection of >10 line additions."""
        old_string = "# Small file\npass\n"
        new_string = """# Small file
# Line 1
# Line 2
# Line 3
# Line 4
# Line 5
# Line 6
# Line 7
# Line 8
# Line 9
# Line 10
# Line 11
pass
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True
        assert "11 new lines" in reason
        assert "+11 lines" in details

    def test_allows_minor_edits(self):
        """Test that minor edits (typo fixes, <10 lines) are allowed."""
        old_string = "# This is a typo in the comment\n"
        new_string = "# This is a fix to the comment\n"

        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is False
        assert reason == ""
        assert details == ""

    def test_allows_small_additions(self):
        """Test that small additions (<10 lines) without new functions are allowed."""
        old_string = "# Module\npass\n"
        new_string = """# Module
# Comment 1
# Comment 2
# Comment 3
pass
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is False

    def test_handles_empty_old_string(self):
        """Test detection with empty old_string (new file)."""
        old_string = ""
        new_string = """def new_function():
    return 42
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True

    def test_handles_none_old_string(self):
        """Test detection with None old_string."""
        old_string = None
        new_string = """class NewClass:
    pass
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True

    def test_detects_multiple_function_additions(self):
        """Test detection when multiple functions are added."""
        old_string = "# Module\n"
        new_string = """# Module
def function1():
    pass

def function2():
    pass
"""
        is_sig, reason, details = has_significant_additions(old_string, new_string)
        assert is_sig is True


class TestCodeFileDetection:
    """Test code file extension filtering."""

    def test_detects_python_files(self):
        """Test detection of Python files."""
        assert is_code_file("module.py") is True
        assert is_code_file("/path/to/script.py") is True

    def test_detects_javascript_files(self):
        """Test detection of JavaScript files."""
        assert is_code_file("app.js") is True
        assert is_code_file("component.jsx") is True
        assert is_code_file("module.ts") is True
        assert is_code_file("component.tsx") is True

    def test_detects_other_language_files(self):
        """Test detection of other language files."""
        assert is_code_file("main.go") is True
        assert is_code_file("lib.rs") is True
        assert is_code_file("Main.java") is True
        assert is_code_file("app.c") is True
        assert is_code_file("app.cpp") is True
        assert is_code_file("header.h") is True
        assert is_code_file("Program.cs") is True
        assert is_code_file("script.rb") is True
        assert is_code_file("index.php") is True
        assert is_code_file("App.swift") is True
        assert is_code_file("Main.kt") is True
        assert is_code_file("App.scala") is True
        assert is_code_file("script.sh") is True
        assert is_code_file("script.bash") is True
        assert is_code_file("script.zsh") is True
        assert is_code_file("Component.vue") is True
        assert is_code_file("Component.svelte") is True

    def test_rejects_config_files(self):
        """Test rejection of config files."""
        assert is_code_file("config.json") is False
        assert is_code_file("package.json") is False
        assert is_code_file("settings.yaml") is False
        assert is_code_file(".env") is False

    def test_rejects_documentation_files(self):
        """Test rejection of documentation files."""
        assert is_code_file("README.md") is False
        assert is_code_file("CLAUDE.md") is False
        assert is_code_file("docs.txt") is False

    def test_rejects_empty_path(self):
        """Test rejection of empty path."""
        assert is_code_file("") is False

    def test_case_insensitive_extension(self):
        """Test case-insensitive extension matching."""
        assert is_code_file("Module.PY") is True
        assert is_code_file("App.JS") is True


class TestLineCountCalculation:
    """Test new line counting logic."""

    def test_counts_added_lines(self):
        """Test counting of added lines."""
        old_string = "line1\nline2\n"
        new_string = "line1\nline2\nline3\nline4\n"
        assert count_new_lines(old_string, new_string) == 2

    def test_counts_zero_for_no_change(self):
        """Test zero count for no change."""
        old_string = "line1\nline2\n"
        new_string = "line1\nline2\n"
        assert count_new_lines(old_string, new_string) == 0

    def test_counts_zero_for_deletions(self):
        """Test zero count for deletions (negative)."""
        old_string = "line1\nline2\nline3\n"
        new_string = "line1\n"
        # Should return max(0, new_lines - old_lines) = 0
        assert count_new_lines(old_string, new_string) == 0

    def test_handles_empty_old_string(self):
        """Test counting with empty old string."""
        old_string = ""
        new_string = "line1\nline2\nline3\n"
        assert count_new_lines(old_string, new_string) == 3

    def test_handles_empty_new_string(self):
        """Test counting with empty new string."""
        old_string = "line1\nline2\n"
        new_string = ""
        assert count_new_lines(old_string, new_string) == 0

    def test_handles_whitespace_only_strings(self):
        """Test counting with whitespace-only strings."""
        old_string = "   \n  \n"
        new_string = "   \n  \n  \n"
        # Should strip and count actual lines
        assert count_new_lines(old_string, new_string) >= 0


class TestAgentWhitelist:
    """Test ALLOWED_AGENTS whitelist enforcement."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "implementer"})
    def test_allows_implementer_agent(self, mock_stdout, mock_stdin):
        """Test that implementer agent is allowed."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "pass",
                "new_string": "def new_func(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "implementer" in output["hookSpecificOutput"]["permissionDecisionReason"]

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "test-master"})
    def test_allows_test_master_agent(self, mock_stdout, mock_stdin):
        """Test that test-master agent is allowed."""
        mock_stdin.write(json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "test_module.py",
                "content": "def test_feature(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "brownfield-analyzer"})
    def test_allows_brownfield_analyzer_agent(self, mock_stdout, mock_stdin):
        """Test that brownfield-analyzer agent is allowed."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "legacy.py",
                "old_string": "",
                "new_string": "class Analyzer: pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "setup-wizard"})
    def test_allows_setup_wizard_agent(self, mock_stdout, mock_stdin):
        """Test that setup-wizard agent is allowed."""
        mock_stdin.write(json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "setup.py",
                "content": "def setup(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "project-bootstrapper"})
    def test_allows_project_bootstrapper_agent(self, mock_stdout, mock_stdin):
        """Test that project-bootstrapper agent is allowed."""
        mock_stdin.write(json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "bootstrap.py",
                "content": "def bootstrap(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "researcher"})
    def test_blocks_unauthorized_agent(self, mock_stdout, mock_stdin):
        """Test that unauthorized agents are blocked."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "pass",
                "new_string": "def unauthorized_function(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "AUTONOMOUS IMPLEMENTATION DETECTED" in output["hookSpecificOutput"]["permissionDecisionReason"]


class TestEnvironmentControl:
    """Test ENFORCE_IMPLEMENTATION_WORKFLOW environment variable toggle."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_IMPLEMENTATION_WORKFLOW": "false"})
    def test_disabled_enforcement_allows_all(self, mock_stdout, mock_stdin):
        """Test that enforcement can be disabled via environment variable."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def significant_change(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "disabled" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_IMPLEMENTATION_WORKFLOW": "FALSE"})
    def test_disabled_enforcement_case_insensitive(self, mock_stdout, mock_stdin):
        """Test that enforcement toggle is case-insensitive."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def another_change(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"ENFORCE_IMPLEMENTATION_WORKFLOW": "true"}, clear=True)
    def test_enabled_enforcement_blocks_significant_changes(self, mock_stdout, mock_stdin):
        """Test that enforcement is enabled by default."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def significant_function(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestOutputFormatting:
    """Test JSON output structure."""

    @patch("sys.stdout", new_callable=StringIO)
    def test_output_decision_format(self, mock_stdout):
        """Test that output_decision produces valid JSON."""
        output_decision("allow", "Test reason")

        output = json.loads(mock_stdout.getvalue())
        assert "hookSpecificOutput" in output
        assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert output["hookSpecificOutput"]["permissionDecisionReason"] == "Test reason"

    @patch("sys.stdout", new_callable=StringIO)
    def test_output_decision_deny(self, mock_stdout):
        """Test deny decision output."""
        output_decision("deny", "Blocked for testing")

        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "Blocked for testing" in output["hookSpecificOutput"]["permissionDecisionReason"]


class TestGracefulDegradation:
    """Test error handling and graceful degradation."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_malformed_json_allows(self, mock_stdout, mock_stdin):
        """Test that malformed JSON input allows by default (no blocking)."""
        mock_stdin.write("not valid json{")
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "parse error" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_missing_tool_name_allows(self, mock_stdout, mock_stdin):
        """Test that missing tool_name allows non-Edit/Write tools."""
        mock_stdin.write(json.dumps({
            "tool_input": {
                "file_path": "module.py"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_missing_tool_input_allows(self, mock_stdout, mock_stdin):
        """Test that missing tool_input allows."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit"
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_non_edit_write_tool_allows(self, mock_stdout, mock_stdin):
        """Test that non-Edit/Write tools are allowed through."""
        mock_stdin.write(json.dumps({
            "tool_name": "Read",
            "tool_input": {
                "file_path": "module.py"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "Read" in output["hookSpecificOutput"]["permissionDecisionReason"]

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_non_code_file_allows(self, mock_stdout, mock_stdin):
        """Test that non-code files are allowed."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "README.md",
                "old_string": "# Old",
                "new_string": "# New"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "non-code" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_exception_during_processing_allows(self, mock_stdout, mock_stdin):
        """Test that exceptions during processing allow (don't block)."""
        # Provide valid JSON but trigger exception in processing
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "pass",
                "new_string": "def test(): pass"
            }
        }))
        mock_stdin.seek(0)

        # Mock has_significant_additions to raise exception
        with patch("enforce_implementation_workflow.has_significant_additions", side_effect=Exception("Test error")):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0
            output = json.loads(mock_stdout.getvalue())
            assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
            assert "error" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()


class TestWriteToolHandling:
    """Test handling of Write tool (new file creation)."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_write_tool_with_significant_content_blocked(self, mock_stdout, mock_stdin):
        """Test that Write tool with significant content is blocked."""
        mock_stdin.write(json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "new_module.py",
                "content": """def authenticate_user(username, password):
    # Validate credentials
    return True
"""
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_write_tool_with_minor_content_allowed(self, mock_stdout, mock_stdin):
        """Test that Write tool with minor content is allowed."""
        mock_stdin.write(json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "config.py",
                "content": "# Configuration\nDEBUG = True\n"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestEnvironmentLoading:
    """Test .env file loading."""

    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="ENFORCE_IMPLEMENTATION_WORKFLOW=false\n")
    def test_load_env_reads_file(self, mock_file, mock_exists):
        """Test that load_env reads .env file."""
        import os
        mock_exists.return_value = True

        # Clear the env var first
        if "ENFORCE_IMPLEMENTATION_WORKFLOW" in os.environ:
            del os.environ["ENFORCE_IMPLEMENTATION_WORKFLOW"]

        load_env()

        # Should have loaded env var
        assert "ENFORCE_IMPLEMENTATION_WORKFLOW" in os.environ
        assert os.environ["ENFORCE_IMPLEMENTATION_WORKFLOW"] == "false"

    @patch("pathlib.Path.exists")
    def test_load_env_handles_missing_file(self, mock_exists):
        """Test that load_env handles missing .env file gracefully."""
        mock_exists.return_value = False

        # Should not raise exception
        load_env()

    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="# Comment\n\nKEY=value\n")
    def test_load_env_skips_comments(self, mock_file, mock_exists):
        """Test that load_env skips comment lines."""
        import os
        mock_exists.return_value = True

        # Clear the env var first
        if "KEY" in os.environ:
            del os.environ["KEY"]

        load_env()

        assert "KEY" in os.environ
        assert os.environ["KEY"] == "value"

    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='KEY="quoted value"\n')
    def test_load_env_strips_quotes(self, mock_file, mock_exists):
        """Test that load_env strips quotes from values."""
        import os
        mock_exists.return_value = True

        # Clear the env var first
        if "KEY" in os.environ:
            del os.environ["KEY"]

        load_env()

        assert os.environ["KEY"] == "quoted value"

    @patch("pathlib.Path.exists")
    @patch("builtins.open", side_effect=IOError("Permission denied"))
    def test_load_env_handles_read_errors(self, mock_file, mock_exists):
        """Test that load_env handles file read errors gracefully."""
        mock_exists.return_value = True

        # Should not raise exception
        load_env()


class TestBlockingMessages:
    """Test that blocking messages provide helpful guidance."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_blocking_message_includes_workflow_guidance(self, mock_stdout, mock_stdin):
        """Test that blocking message includes /create-issue and /auto-implement guidance."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "auth.py",
                "old_string": "",
                "new_string": "def authenticate(user): return True"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        assert "/create-issue" in reason
        assert "/auto-implement" in reason
        assert "AUTONOMOUS IMPLEMENTATION DETECTED" in reason

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_blocking_message_includes_file_name(self, mock_stdout, mock_stdin):
        """Test that blocking message includes the file being edited."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/path/to/important_module.py",
                "old_string": "",
                "new_string": "class ImportantClass: pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        assert "important_module.py" in reason

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_blocking_message_includes_reason(self, mock_stdout, mock_stdin):
        """Test that blocking message includes detection reason."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "",
                "new_string": "def new_function(): pass"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]

        # Should mention what was detected
        assert ("Python function" in reason or "function" in reason.lower())


# Integration Tests
class TestIntegrationScenarios:
    """Test complete workflow scenarios."""

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_scenario_typo_fix_allowed(self, mock_stdout, mock_stdin):
        """Test scenario: Developer fixes typo in comment."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "utils.py",
                "old_string": "# Calcualte sum",
                "new_string": "# Calculate sum"
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    def test_scenario_feature_implementation_blocked(self, mock_stdout, mock_stdin):
        """Test scenario: Claude autonomously implements feature."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "api.py",
                "old_string": "# TODO: Add authentication",
                "new_string": """# Authentication implemented
def authenticate_user(token):
    decoded = jwt.decode(token, SECRET_KEY)
    return User.query.get(decoded['user_id'])
"""
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch.dict("os.environ", {"CLAUDE_AGENT_NAME": "implementer"})
    def test_scenario_auto_implement_workflow_allowed(self, mock_stdout, mock_stdin):
        """Test scenario: Implementation via /auto-implement workflow."""
        mock_stdin.write(json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "feature.py",
                "old_string": "pass",
                "new_string": """def process_payment(amount, user):
    # Process payment logic
    return charge_card(amount, user.card)
"""
            }
        }))
        mock_stdin.seek(0)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


if __name__ == "__main__":
    # Run tests with minimal verbosity (Issue #90 - prevent subprocess deadlock)
    pytest.main([__file__, "--tb=line", "-q"])

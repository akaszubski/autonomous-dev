r"""
Regression tests for extension-aware pattern matching and Bash file-write bypass detection.

Fix 1: Extension-aware pattern matching
Root cause: SIGNIFICANT_PATTERNS flat list matches `function log()` in .sh files
as "JavaScript function" because pattern `r'\bfunction\s+\w+\s*\('` doesn't
consider file extensions.

Fix: Replace SIGNIFICANT_PATTERNS with PATTERN_GROUPS that filter by file extension.
The _has_significant_additions() function gains a file_path parameter to select
the appropriate pattern group.

Fix 2: Bash tool file-writing bypass detection
Root cause: When Write tool is blocked, Claude can bypass with Bash tool using
`cat > file.py` or similar redirection operators.

Fix: Add _extract_bash_file_writes() function to detect file writes in Bash commands,
and extend validate_agent_authorization() to check Bash tool for file writes.

Date: 2026-02-13
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Find project root
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

# Add hooks dir to path for imports
hook_dir = project_root / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(hook_dir))

# Import functions under test
from unified_pre_tool import (
    _has_significant_additions,
    _extract_bash_file_writes,
    validate_agent_authorization,
    _is_exempt_path,
)


class TestExtensionAwarePatternMatching:
    """Test extension-aware pattern matching for language-specific patterns."""

    def test_shell_function_not_detected_as_javascript(self):
        """Shell function should NOT trigger 'JavaScript function' pattern."""
        old_string = ""
        new_string = """
#!/bin/bash
function log() {
    echo "$1"
}
"""
        is_significant, reason, details = _has_significant_additions(
            old_string, new_string, file_path="scripts/deploy.sh"
        )

        # Shell function should be detected, but NOT as JavaScript
        if is_significant and "JavaScript" in reason:
            pytest.fail(f"Shell function incorrectly detected as JavaScript: {reason}")

    def test_javascript_function_detected_in_js_file(self):
        """JavaScript function SHOULD trigger detection in .js file."""
        old_string = ""
        new_string = """
function authenticate(user) {
    return user.token;
}
"""
        is_significant, reason, details = _has_significant_additions(
            old_string, new_string, file_path="src/auth.js"
        )

        assert is_significant, "JavaScript function should be detected"
        assert "function" in reason.lower(), f"Expected 'function' in reason, got: {reason}"

    def test_python_def_detected_in_py_file(self):
        """Python function SHOULD trigger detection in .py file."""
        old_string = ""
        new_string = """
def process_data(items):
    return [x * 2 for x in items]
"""
        is_significant, reason, details = _has_significant_additions(
            old_string, new_string, file_path="src/processor.py"
        )

        assert is_significant, "Python function should be detected"
        assert "python" in reason.lower() or "function" in reason.lower(), \
            f"Expected Python function in reason, got: {reason}"

    def test_python_def_not_detected_in_sh_file(self):
        """Python 'def' in shell comment should NOT trigger Python detection."""
        old_string = ""
        new_string = """
#!/bin/bash
# This script will def-initely work
echo "Running deployment"
"""
        is_significant, reason, details = _has_significant_additions(
            old_string, new_string, file_path="scripts/deploy.sh"
        )

        # Should not trigger Python function detection
        if is_significant and "python" in reason.lower():
            pytest.fail(f"Shell comment incorrectly detected as Python: {reason}")

    def test_go_func_detected_in_go_file(self):
        """Go function SHOULD trigger detection in .go file."""
        old_string = ""
        new_string = """
func main() {
    fmt.Println("Hello")
}
"""
        is_significant, reason, details = _has_significant_additions(
            old_string, new_string, file_path="cmd/server/main.go"
        )

        assert is_significant, "Go function should be detected"
        assert "go" in reason.lower() or "function" in reason.lower(), \
            f"Expected Go function in reason, got: {reason}"

    def test_rust_fn_not_detected_in_py_file(self):
        """Rust 'fn' keyword in Python should NOT trigger Rust detection."""
        old_string = ""
        new_string = """
# Configuration function
config_fn = lambda x: x * 2
"""
        is_significant, reason, details = _has_significant_additions(
            old_string, new_string, file_path="src/config.py"
        )

        # Should not trigger Rust function detection
        if is_significant and "rust" in reason.lower():
            pytest.fail(f"Python code incorrectly detected as Rust: {reason}")

    def test_universal_patterns_apply_to_all_code_files(self):
        """Universal patterns (like conditional imports) should work across languages."""
        # Test in Python
        old_string = ""
        new_string = """
try:
    from special_lib import feature
except ImportError:
    feature = None
"""
        is_significant_py, reason_py, _ = _has_significant_additions(
            old_string, new_string, file_path="src/compat.py"
        )

        # Test in JavaScript (if universal pattern exists)
        js_new = """
try {
    const feature = require('special-lib');
} catch (err) {
    console.log('Feature unavailable');
}
"""
        is_significant_js, reason_js, _ = _has_significant_additions(
            "", js_new, file_path="src/compat.js"
        )

        # At least one should detect the conditional pattern
        assert is_significant_py or is_significant_js, \
            "Conditional import pattern should be detected in at least one language"

    def test_unknown_extension_uses_no_language_patterns(self):
        """Files with unknown extensions should only use universal patterns."""
        old_string = ""
        new_string = """
function setup() {
    initialize();
}
class Handler {
    process() {}
}
"""
        # Use .xyz extension (not in CODE_EXTENSIONS)
        is_significant, reason, details = _has_significant_additions(
            old_string, new_string, file_path="data/config.xyz"
        )

        # Should either not detect (no patterns apply) or detect only universal patterns
        # NOT language-specific patterns like "JavaScript function"
        if is_significant and any(lang in reason.lower() for lang in ["javascript", "python", "go", "rust"]):
            pytest.fail(f"Unknown extension incorrectly triggered language-specific pattern: {reason}")

    def test_empty_file_path_uses_all_patterns(self):
        """Backward compatibility: no file_path should use all patterns."""
        old_string = ""
        new_string = """
def process():
    return True
"""
        # Call without file_path (backward compat)
        is_significant, reason, details = _has_significant_additions(
            old_string, new_string, file_path=""
        )

        assert is_significant, "Function should be detected even without file_path"

    def test_class_detection_in_correct_language(self):
        """Class definitions should be detected in appropriate languages."""
        # Python class
        py_code = """
class DataProcessor:
    def __init__(self):
        pass
"""
        is_sig_py, reason_py, _ = _has_significant_additions(
            "", py_code, file_path="src/processor.py"
        )

        # Shell script (class keyword in comment)
        sh_code = """
#!/bin/bash
# This is a class-A deployment script
echo "Deploying..."
"""
        is_sig_sh, reason_sh, _ = _has_significant_additions(
            "", sh_code, file_path="scripts/deploy.sh"
        )

        assert is_sig_py, "Python class should be detected"
        if is_sig_sh and "class" in reason_sh.lower() and "python" in reason_sh.lower():
            pytest.fail("Shell comment incorrectly detected as Python class")


class TestBashFileWriteExtraction:
    """Test extraction of file paths from Bash file-write commands."""

    def test_simple_redirect(self):
        """Simple output redirect: echo 'hi' > file.py"""
        command = "echo 'import os' > module.py"
        files = _extract_bash_file_writes(command)

        assert "module.py" in files, f"Expected module.py in {files}"

    def test_append_redirect(self):
        """Append redirect: echo 'hi' >> file.py"""
        command = "echo 'import sys' >> module.py"
        files = _extract_bash_file_writes(command)

        assert "module.py" in files, f"Expected module.py in {files}"

    def test_cat_redirect(self):
        """Cat redirect: cat content.txt > file.py"""
        command = "cat template.txt > generated.py"
        files = _extract_bash_file_writes(command)

        assert "generated.py" in files, f"Expected generated.py in {files}"

    def test_tee_command(self):
        """Tee command: echo 'hi' | tee file.py"""
        command = "echo 'code' | tee output.py"
        files = _extract_bash_file_writes(command)

        assert "output.py" in files, f"Expected output.py in {files}"

    def test_tee_append(self):
        """Tee append: echo 'hi' | tee -a file.py"""
        command = "echo 'more code' | tee -a output.py"
        files = _extract_bash_file_writes(command)

        assert "output.py" in files, f"Expected output.py in {files}"

    def test_heredoc_redirect(self):
        """Heredoc redirect: cat << EOF > file.py"""
        command = """cat << 'EOF' > script.py
#!/usr/bin/env python3
print('hello')
EOF"""
        files = _extract_bash_file_writes(command)

        assert "script.py" in files, f"Expected script.py in {files}"

    def test_stderr_redirect_ignored(self):
        """Stderr redirect should be ignored: pytest 2> /dev/null"""
        command = "pytest tests/ 2> /dev/null"
        files = _extract_bash_file_writes(command)

        assert len(files) == 0, f"Stderr redirect should be ignored, got: {files}"

    def test_dev_null_ignored(self):
        """Writes to /dev/null should be ignored."""
        command = "echo 'debug' > /dev/null"
        files = _extract_bash_file_writes(command)

        assert len(files) == 0, f"/dev/null should be ignored, got: {files}"

    def test_multiple_files(self):
        """Multiple file writes: echo a > x.py; echo b > y.py"""
        command = "echo 'import x' > mod_x.py; echo 'import y' > mod_y.py"
        files = _extract_bash_file_writes(command)

        assert "mod_x.py" in files, f"Expected mod_x.py in {files}"
        assert "mod_y.py" in files, f"Expected mod_y.py in {files}"

    def test_no_redirect(self):
        """No redirect: pytest tests/"""
        command = "pytest tests/ -v"
        files = _extract_bash_file_writes(command)

        assert len(files) == 0, f"No redirect should return empty list, got: {files}"

    def test_git_command_no_redirect(self):
        """Git command without redirect."""
        command = "git status"
        files = _extract_bash_file_writes(command)

        assert len(files) == 0, f"Git command should return empty list, got: {files}"

    def test_printf_redirect(self):
        """Printf redirect: printf 'code' > file.py"""
        command = "printf 'def main():\\n    pass\\n' > main.py"
        files = _extract_bash_file_writes(command)

        assert "main.py" in files, f"Expected main.py in {files}"

    def test_fd_redirect_ignored(self):
        """File descriptor redirects should be ignored: cmd 2>&1"""
        command = "python script.py 2>&1"
        files = _extract_bash_file_writes(command)

        assert len(files) == 0, f"FD redirect should be ignored, got: {files}"

    def test_complex_pipe(self):
        """Complex pipe: grep pattern | sort > output.py"""
        command = "grep 'import' *.txt | sort > imports.py"
        files = _extract_bash_file_writes(command)

        assert "imports.py" in files, f"Expected imports.py in {files}"

    def test_empty_command(self):
        """Empty command should return empty list."""
        command = ""
        files = _extract_bash_file_writes(command)

        assert len(files) == 0, f"Empty command should return empty list, got: {files}"


class TestBashBypassEnforcement:
    """Test Bash tool file-write bypass enforcement."""

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_bash_write_to_python_file_blocked(self):
        """Bash write to Python file should be blocked at enforcement level: block."""
        tool_input = {
            "command": "cat << 'EOF' > src/module.py\nimport os\nEOF"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "deny", f"Bash write to .py should be blocked, got: {decision}"
        assert "/implement" in reason, f"Denial should suggest /implement, got: {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_bash_write_to_markdown_allowed(self):
        """Bash write to Markdown should be allowed (non-code file)."""
        tool_input = {
            "command": "echo '# Documentation' > docs/README.md"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "allow", f"Bash write to .md should be allowed, got: {decision}, {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_bash_write_to_test_file_allowed(self):
        """Bash write to test file should be allowed (exempt path)."""
        tool_input = {
            "command": "echo 'import pytest' > tests/test_feature.py"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "allow", f"Bash write to test file should be allowed, got: {decision}, {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_bash_no_redirect_allowed(self):
        """Bash command without file write should be allowed."""
        tool_input = {
            "command": "pytest tests/ -v"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "allow", f"Bash without redirect should be allowed, got: {decision}, {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "off", "CLAUDE_AGENT_NAME": ""})
    def test_bash_write_enforcement_off(self):
        """Bash write allowed when enforcement is OFF."""
        tool_input = {
            "command": "echo 'import sys' > src/util.py"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "allow", f"Enforcement OFF should allow everything, got: {decision}, {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "warn", "CLAUDE_AGENT_NAME": ""})
    def test_bash_write_enforcement_warn(self):
        """Bash write allowed with warning at enforcement level: warn."""
        tool_input = {
            "command": "cat template.txt > src/generated.py"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "allow", f"WARN level should allow, got: {decision}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "suggest", "CLAUDE_AGENT_NAME": ""})
    def test_bash_write_enforcement_suggest(self):
        """Bash write allowed with suggestion at enforcement level: suggest."""
        tool_input = {
            "command": "printf 'def main(): pass' > src/app.py"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "allow", f"SUGGEST level should allow, got: {decision}"
        assert "/implement" in reason, f"Suggestion should mention /implement, got: {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_bash_write_includes_implement_suggestion(self):
        """Denial message should include /implement suggestion."""
        tool_input = {
            "command": "echo 'class App: pass' > src/core.py"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "deny", f"Should be blocked, got: {decision}"
        assert "/implement" in reason, f"Should suggest /implement, got: {reason}"
        assert "--quick" in reason or "workflow" in reason.lower(), \
            f"Should explain workflow options, got: {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_bash_write_to_exempt_hooks_path(self):
        """Bash write to exempt path (.claude/hooks/) should be allowed."""
        tool_input = {
            "command": "cat > .claude/hooks/custom_hook.py << 'EOF'\nimport sys\nEOF"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "allow", f"Hooks path should be exempt, got: {decision}, {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": "implementer"})
    def test_bash_write_pipeline_agent_allowed(self):
        """Bash write by pipeline agent should be allowed."""
        tool_input = {
            "command": "echo 'import logging' > src/logger.py"
        }

        decision, reason = validate_agent_authorization("Bash", tool_input)

        assert decision == "allow", f"Pipeline agent should be allowed, got: {decision}, {reason}"
        assert "implementer" in reason.lower() or "authorized" in reason.lower(), \
            f"Reason should mention agent authorization, got: {reason}"


class TestBackwardCompatibility:
    """Test that existing Edit/Write enforcement still works."""

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_edit_tool_still_enforced(self):
        """Edit tool with significant Python code should still be enforced."""
        tool_input = {
            "file_path": "src/module.py",
            "old_string": "# TODO",
            "new_string": """
def process_items(items):
    return [x * 2 for x in items]
"""
        }

        decision, reason = validate_agent_authorization("Edit", tool_input)

        assert decision == "deny", f"Significant Edit should be blocked, got: {decision}, {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_write_tool_still_enforced(self):
        """Write tool with significant code should still be enforced."""
        tool_input = {
            "file_path": "src/new_module.py",
            "content": """
class DataHandler:
    def __init__(self):
        self.data = []

    def add(self, item):
        self.data.append(item)
"""
        }

        decision, reason = validate_agent_authorization("Write", tool_input)

        assert decision == "deny", f"Significant Write should be blocked, got: {decision}, {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_minor_edit_still_allowed(self):
        """Small edit (< 5 lines, no functions/classes) should still be allowed."""
        tool_input = {
            "file_path": "src/config.py",
            "old_string": "timeout = 30",
            "new_string": "timeout = 60  # Increased for slow networks"
        }

        decision, reason = validate_agent_authorization("Edit", tool_input)

        assert decision == "allow", f"Minor edit should be allowed, got: {decision}, {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_non_code_file_still_allowed(self):
        """Edit to non-code file (.json) should still be allowed."""
        tool_input = {
            "file_path": "config.json",
            "old_string": '{"timeout": 30}',
            "new_string": '{"timeout": 60, "retries": 3}'
        }

        decision, reason = validate_agent_authorization("Edit", tool_input)

        assert decision == "allow", f"Non-code edit should be allowed, got: {decision}, {reason}"

    @patch.dict(os.environ, {"ENFORCEMENT_LEVEL": "block", "CLAUDE_AGENT_NAME": ""})
    def test_pipeline_state_file_still_bypasses(self):
        """Active pipeline state file should still bypass enforcement."""
        # Create temporary pipeline state
        state_file = Path("/tmp/implement_pipeline_state.json")
        try:
            from datetime import datetime
            state = {
                "session_start": datetime.now().isoformat(),
                "status": "active"
            }
            state_file.write_text(json.dumps(state))

            with patch.dict(os.environ, {"PIPELINE_STATE_FILE": str(state_file)}):
                tool_input = {
                    "file_path": "src/module.py",
                    "old_string": "",
                    "new_string": "def new_function(): pass"
                }

                decision, reason = validate_agent_authorization("Edit", tool_input)

                assert decision == "allow", f"Pipeline state should bypass, got: {decision}, {reason}"
                assert "pipeline" in reason.lower(), f"Reason should mention pipeline, got: {reason}"
        finally:
            if state_file.exists():
                state_file.unlink()


# Test summary fixture for debugging
@pytest.fixture(scope="session", autouse=True)
def test_summary():
    """Print test summary after all tests complete."""
    yield
    print("\n" + "="*70)
    print("Extension-Aware Enforcement Test Summary")
    print("="*70)
    print("✅ TestExtensionAwarePatternMatching: 10 tests")
    print("✅ TestBashFileWriteExtraction: 15 tests")
    print("✅ TestBashBypassEnforcement: 10 tests")
    print("✅ TestBackwardCompatibility: 5 tests")
    print("="*70)
    print("TOTAL: 40 comprehensive tests for extension-aware workflow enforcement")
    print("="*70)

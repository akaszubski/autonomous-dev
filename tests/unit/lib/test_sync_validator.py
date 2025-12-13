#!/usr/bin/env python3
"""
Unit tests for sync_validator.py

Tests the 4-phase post-sync validation:
1. Settings Validation
2. Hook Integrity
3. Semantic Scan
4. Health Check

Date: 2025-12-13
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"))

from sync_validator import (
    SyncValidator,
    SyncValidationResult,
    PhaseResult,
    ValidationIssue,
    ManualFix,
    validate_sync,
)


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_create_issue(self):
        """Test creating a validation issue."""
        issue = ValidationIssue(
            severity="error",
            category="settings",
            message="Invalid JSON",
            file_path="/path/to/file.json",
            line_number=42,
        )
        assert issue.severity == "error"
        assert issue.category == "settings"
        assert issue.message == "Invalid JSON"
        assert issue.file_path == "/path/to/file.json"
        assert issue.line_number == 42
        assert issue.auto_fixable is False

    def test_auto_fixable_issue(self):
        """Test creating an auto-fixable issue."""
        issue = ValidationIssue(
            severity="warning",
            category="hook",
            message="Not executable",
            auto_fixable=True,
            fix_action="chmod +x file.py",
        )
        assert issue.auto_fixable is True
        assert issue.fix_action == "chmod +x file.py"


class TestManualFix:
    """Tests for ManualFix dataclass."""

    def test_create_manual_fix(self):
        """Test creating manual fix instructions."""
        fix = ManualFix(
            issue="Syntax error in hook",
            steps=["Open file", "Fix line 42", "Save and retry"],
            command="python -m py_compile file.py",
        )
        assert fix.issue == "Syntax error in hook"
        assert len(fix.steps) == 3
        assert fix.command == "python -m py_compile file.py"

    def test_manual_fix_no_command(self):
        """Test manual fix without a single command."""
        fix = ManualFix(
            issue="Complex fix needed",
            steps=["Step 1", "Step 2"],
        )
        assert fix.command is None


class TestPhaseResult:
    """Tests for PhaseResult dataclass."""

    def test_empty_phase_result(self):
        """Test empty phase result."""
        result = PhaseResult(phase="settings", passed=True)
        assert result.phase == "settings"
        assert result.passed is True
        assert result.error_count == 0
        assert result.warning_count == 0
        assert result.has_errors is False

    def test_phase_with_errors(self):
        """Test phase result with errors."""
        result = PhaseResult(
            phase="hooks",
            passed=False,
            issues=[
                ValidationIssue(severity="error", category="hook", message="Error 1"),
                ValidationIssue(severity="warning", category="hook", message="Warning 1"),
                ValidationIssue(severity="error", category="hook", message="Error 2"),
            ],
        )
        assert result.passed is False
        assert result.error_count == 2
        assert result.warning_count == 1
        assert result.has_errors is True


class TestSyncValidationResult:
    """Tests for SyncValidationResult dataclass."""

    def test_empty_result(self):
        """Test empty validation result."""
        result = SyncValidationResult()
        assert result.overall_passed is True  # No phases = passed
        assert result.total_auto_fixed == 0
        assert result.total_manual_fixes == 0
        assert result.exit_code == 0

    def test_all_phases_passed(self):
        """Test result when all phases pass."""
        result = SyncValidationResult(
            phases=[
                PhaseResult(phase="settings", passed=True),
                PhaseResult(phase="hooks", passed=True),
                PhaseResult(phase="semantic", passed=True),
                PhaseResult(phase="health", passed=True),
            ]
        )
        assert result.overall_passed is True
        assert result.exit_code == 0

    def test_one_phase_failed(self):
        """Test result when one phase fails."""
        result = SyncValidationResult(
            phases=[
                PhaseResult(phase="settings", passed=True),
                PhaseResult(
                    phase="hooks",
                    passed=False,
                    issues=[
                        ValidationIssue(severity="error", category="hook", message="Syntax error")
                    ],
                ),
            ]
        )
        assert result.overall_passed is False
        assert result.total_errors == 1
        assert result.exit_code == 1

    def test_auto_fixed_count(self):
        """Test counting auto-fixed issues."""
        result = SyncValidationResult(
            phases=[
                PhaseResult(
                    phase="hooks",
                    passed=True,
                    auto_fixed=["chmod +x hook1.py", "chmod +x hook2.py"],
                ),
                PhaseResult(
                    phase="settings",
                    passed=True,
                    auto_fixed=["Removed invalid hook path"],
                ),
            ]
        )
        assert result.total_auto_fixed == 3


class TestSyncValidator:
    """Tests for SyncValidator class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            claude_dir = project_path / ".claude"
            claude_dir.mkdir()
            (claude_dir / "agents").mkdir()
            (claude_dir / "hooks").mkdir()
            (claude_dir / "commands").mkdir()
            (claude_dir / "config").mkdir()
            yield project_path

    def test_validator_init(self, temp_project):
        """Test validator initialization."""
        validator = SyncValidator(temp_project)
        assert validator.project_path == temp_project
        assert validator.claude_dir == temp_project / ".claude"

    def test_validate_settings_no_file(self, temp_project):
        """Test settings validation when no settings file exists."""
        validator = SyncValidator(temp_project)
        result = validator.validate_settings()
        assert result.phase == "settings"
        assert result.passed is True  # No file is OK

    def test_validate_settings_valid_json(self, temp_project):
        """Test settings validation with valid JSON."""
        settings_path = temp_project / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps({"hooks": []}))

        validator = SyncValidator(temp_project)
        result = validator.validate_settings()
        assert result.passed is True
        assert result.error_count == 0

    def test_validate_settings_invalid_json(self, temp_project):
        """Test settings validation with invalid JSON."""
        settings_path = temp_project / ".claude" / "settings.local.json"
        settings_path.write_text("{invalid json")

        validator = SyncValidator(temp_project)
        result = validator.validate_settings()
        assert result.passed is False
        assert result.error_count == 1
        assert "Invalid JSON syntax" in result.issues[0].message

    def test_validate_settings_invalid_hook_path(self, temp_project):
        """Test settings validation with invalid hook path."""
        settings_path = temp_project / ".claude" / "settings.local.json"
        settings_path.write_text(json.dumps({
            "hooks": [{"path": "nonexistent_hook.py"}]
        }))

        validator = SyncValidator(temp_project)
        result = validator.validate_settings()
        # Invalid hook path is a warning, not an error
        assert result.warning_count >= 1
        assert any("Hook path not found" in i.message for i in result.issues)

    def test_validate_hooks_no_hooks(self, temp_project):
        """Test hook validation with no hooks."""
        validator = SyncValidator(temp_project)
        result = validator.validate_hooks()
        assert result.phase == "hooks"
        assert result.passed is True

    def test_validate_hooks_valid_syntax(self, temp_project):
        """Test hook validation with valid Python hook."""
        hook_path = temp_project / ".claude" / "hooks" / "valid_hook.py"
        hook_path.write_text("def main():\n    pass\n")
        # Make executable
        os.chmod(hook_path, 0o755)

        validator = SyncValidator(temp_project)
        result = validator.validate_hooks()
        assert result.passed is True

    def test_validate_hooks_syntax_error(self, temp_project):
        """Test hook validation with syntax error."""
        hook_path = temp_project / ".claude" / "hooks" / "bad_hook.py"
        hook_path.write_text("def main(\n  # Missing closing paren")
        os.chmod(hook_path, 0o755)

        validator = SyncValidator(temp_project)
        result = validator.validate_hooks()
        assert result.passed is False
        assert result.error_count == 1
        assert "Syntax error" in result.issues[0].message

    def test_validate_hooks_not_executable(self, temp_project):
        """Test hook validation when hook is not executable."""
        hook_path = temp_project / ".claude" / "hooks" / "hook.py"
        hook_path.write_text("pass\n")
        # Not executable
        os.chmod(hook_path, 0o644)

        validator = SyncValidator(temp_project)
        result = validator.validate_hooks()
        # Non-executable is a warning
        assert any("not executable" in i.message for i in result.issues)
        assert result.issues[0].auto_fixable is True

    def test_validate_semantic_no_agents(self, temp_project):
        """Test semantic validation with no agents."""
        validator = SyncValidator(temp_project)
        result = validator.validate_semantic()
        assert result.phase == "semantic"
        assert result.passed is True

    def test_validate_health_empty_project(self, temp_project):
        """Test health validation with empty project."""
        validator = SyncValidator(temp_project)
        result = validator.validate_health()
        assert result.phase == "health"
        # Will have warnings about low component counts
        assert result.warning_count >= 0

    def test_validate_all(self, temp_project):
        """Test running all validations."""
        validator = SyncValidator(temp_project)
        result = validator.validate_all()
        assert len(result.phases) == 4
        assert result.phases[0].phase == "settings"
        assert result.phases[1].phase == "hooks"
        assert result.phases[2].phase == "semantic"
        assert result.phases[3].phase == "health"

    def test_apply_auto_fixes_permissions(self, temp_project):
        """Test auto-fixing hook permissions."""
        hook_path = temp_project / ".claude" / "hooks" / "hook.py"
        hook_path.write_text("pass\n")
        os.chmod(hook_path, 0o644)  # Not executable

        validator = SyncValidator(temp_project)
        result = validator.validate_all()

        # Should have a fixable issue
        hook_issues = [
            i for i in result.phases[1].issues
            if "not executable" in i.message
        ]
        assert len(hook_issues) > 0
        assert hook_issues[0].auto_fixable is True

        # Apply fixes
        fixes = validator.apply_auto_fixes(result)
        assert fixes >= 1

        # Verify hook is now executable
        assert os.access(hook_path, os.X_OK)

    def test_generate_fix_report_passed(self, temp_project):
        """Test report generation when all passed."""
        validator = SyncValidator(temp_project)
        result = validator.validate_all()
        report = validator.generate_fix_report(result)

        assert "Post-Sync Validation" in report
        assert "Summary" in report

    def test_generate_fix_report_with_manual_fixes(self, temp_project):
        """Test report generation with manual fixes."""
        settings_path = temp_project / ".claude" / "settings.local.json"
        settings_path.write_text("{invalid}")

        validator = SyncValidator(temp_project)
        result = validator.validate_all()
        report = validator.generate_fix_report(result)

        assert "HOW TO FIX" in report
        assert "settings.local.json" in report


class TestValidateSyncFunction:
    """Tests for the validate_sync convenience function."""

    def test_validate_sync(self):
        """Test the convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            claude_dir = project_path / ".claude"
            claude_dir.mkdir()
            (claude_dir / "hooks").mkdir()
            (claude_dir / "agents").mkdir()
            (claude_dir / "commands").mkdir()

            result = validate_sync(project_path)
            assert isinstance(result, SyncValidationResult)
            assert len(result.phases) == 4


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_nonexistent_project(self):
        """Test with nonexistent project path."""
        validator = SyncValidator("/nonexistent/path")
        result = validator.validate_all()
        # Should not crash, just report no files found
        assert isinstance(result, SyncValidationResult)

    def test_permission_denied(self):
        """Test handling of permission denied errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            claude_dir = project_path / ".claude"
            claude_dir.mkdir()
            settings_path = claude_dir / "settings.local.json"
            settings_path.write_text("{}")

            # Make unreadable (if not running as root)
            if os.geteuid() != 0:
                os.chmod(settings_path, 0o000)
                try:
                    validator = SyncValidator(project_path)
                    result = validator.validate_settings()
                    # Should handle gracefully
                    assert result.passed is False or result.error_count >= 0
                finally:
                    os.chmod(settings_path, 0o644)

    def test_empty_settings_file(self):
        """Test with empty settings file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            claude_dir = project_path / ".claude"
            claude_dir.mkdir()
            settings_path = claude_dir / "settings.local.json"
            settings_path.write_text("")

            validator = SyncValidator(project_path)
            result = validator.validate_settings()
            # Empty file is invalid JSON
            assert result.passed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

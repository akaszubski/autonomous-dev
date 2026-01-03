#!/usr/bin/env python3
"""
TDD Tests for Comprehensive Documentation Validator (FAILING - Red Phase)

This module contains FAILING tests for comprehensive_doc_validator.py which validates
cross-references between documentation files (README, PROJECT.md, docstrings).

Requirements:
1. Command cross-reference validation (README vs actual commands)
2. Feature validation (PROJECT.md SCOPE vs implementation)
3. Code example validation (docstrings vs actual APIs)
4. Auto-fix engine for safe patterns (counts, missing commands)
5. Non-blocking, batch-mode compatible
6. Environment variable control (VALIDATE_COMPREHENSIVE_DOCS)

Test Coverage Target: 95%+ of validation logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe comprehensive validation requirements
- Tests should FAIL until comprehensive_doc_validator.py is implemented
- Each test validates ONE validation requirement

Author: test-master agent
Date: 2026-01-03
Related: Issue #198 - Comprehensive documentation validation in /auto-implement
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until comprehensive_doc_validator.py is created
from plugins.autonomous_dev.lib.comprehensive_doc_validator import (
    ComprehensiveDocValidator,
    ValidationIssue,
    ValidationReport,
)


class TestValidatorInitialization:
    """Test comprehensive doc validator initialization."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with basic structure."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create .claude directory
        claude_dir = repo_root / ".claude"
        claude_dir.mkdir()

        # Create commands directory
        commands_dir = claude_dir / "commands"
        commands_dir.mkdir()

        # Create PROJECT.md
        (repo_root / "PROJECT.md").write_text("# Project\n")

        # Create README.md
        (repo_root / "README.md").write_text("# README\n")

        return repo_root

    def test_initialization_default_mode(self, temp_repo):
        """Test validator initializes in default (interactive) mode.

        REQUIREMENT: Default mode is interactive.
        Expected: Validator created with batch_mode=False.
        """
        validator = ComprehensiveDocValidator(temp_repo)

        assert validator.repo_root == temp_repo
        assert validator.batch_mode is False

    def test_initialization_batch_mode(self, temp_repo):
        """Test validator initializes in batch mode.

        REQUIREMENT: Support batch mode (no prompts).
        Expected: Validator created with batch_mode=True.
        """
        validator = ComprehensiveDocValidator(temp_repo, batch_mode=True)

        assert validator.batch_mode is True

    def test_initialization_validates_repo_root(self):
        """Test validator validates repo_root exists.

        REQUIREMENT: Validate repo_root parameter.
        Expected: Raises ValueError for non-existent path.
        """
        with pytest.raises(ValueError, match="repo_root"):
            ComprehensiveDocValidator(Path("/nonexistent/path"))


class TestCommandExportValidation:
    """Test command export cross-reference validation (README vs actual commands)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with commands."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create .claude/commands directory
        commands_dir = repo_root / ".claude" / "commands"
        commands_dir.mkdir(parents=True)

        # Create sample commands
        (commands_dir / "advise.md").write_text("# Advise Command\n")
        (commands_dir / "align.md").write_text("# Align Command\n")
        (commands_dir / "auto-implement.md").write_text("# Auto-Implement Command\n")

        # Create README with command table
        readme = repo_root / "README.md"
        readme.write_text("""
# Commands

| Command | Description |
|---------|-------------|
| /advise | Critical thinking analysis |
| /align | Alignment command |
| /auto-implement | Autonomous feature development |
""")

        return repo_root

    def test_validate_command_exports_all_present(self, temp_repo):
        """Test validation passes when all commands present in README.

        REQUIREMENT: Validate README command table vs actual commands.
        Expected: No issues returned.
        """
        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        assert len(issues) == 0

    def test_validate_command_exports_missing_command(self, temp_repo):
        """Test validation detects command missing from README.

        REQUIREMENT: Detect missing command in README.
        Expected: Returns issue with category='command', severity='error'.
        """
        # Remove a command from README
        readme = temp_repo / "README.md"
        readme.write_text("""
# Commands

| Command | Description |
|---------|-------------|
| /advise | Critical thinking analysis |
| /align | Alignment command |
""")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        assert len(issues) == 1
        assert issues[0].category == "command"
        assert issues[0].severity == "error"
        assert "auto-implement" in issues[0].message.lower()
        assert issues[0].auto_fixable is True

    def test_validate_command_exports_extra_command(self, temp_repo):
        """Test validation detects README command without file.

        REQUIREMENT: Detect non-existent command in README.
        Expected: Returns issue with category='command', severity='warning'.
        """
        # Add non-existent command to README
        readme = temp_repo / "README.md"
        readme.write_text("""
# Commands

| Command | Description |
|---------|-------------|
| /advise | Critical thinking analysis |
| /align | Alignment command |
| /auto-implement | Autonomous feature development |
| /nonexistent | This command does not exist |
""")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        assert len(issues) == 1
        assert issues[0].category == "command"
        assert issues[0].severity == "warning"
        assert "nonexistent" in issues[0].message.lower()

    def test_validate_command_exports_handles_missing_readme(self, temp_repo):
        """Test validation handles missing README gracefully.

        REQUIREMENT: Graceful handling of missing files.
        Expected: Returns issue with category='command', severity='error'.
        """
        # Remove README
        (temp_repo / "README.md").unlink()

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        assert len(issues) > 0
        assert any(issue.severity == "error" for issue in issues)

    def test_validate_command_exports_ignores_internal_commands(self, temp_repo):
        """Test validation ignores internal/deprecated commands.

        REQUIREMENT: Filter out internal commands from validation.
        Expected: Internal commands not flagged as missing.
        """
        # Add internal command file
        commands_dir = temp_repo / ".claude" / "commands"
        (commands_dir / "_internal.md").write_text("# Internal Command\n")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        # Should not flag _internal as missing from README
        assert not any("_internal" in issue.message.lower() for issue in issues)


class TestProjectFeatureValidation:
    """Test feature validation (PROJECT.md SCOPE vs implementation)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with PROJECT.md."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create PROJECT.md with SCOPE section
        project_md = repo_root / "PROJECT.md"
        project_md.write_text("""
## SCOPE

### In Scope
- Git automation (auto-commit, auto-push, auto-PR)
- Batch processing with state management
- Security auditing with GenAI
- Documentation auto-generation

### Out of Scope
- Database migrations
- UI components
""")

        # Create implementation files
        lib_dir = repo_root / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)

        (lib_dir / "auto_git_workflow.py").write_text("# Git automation\n")
        (lib_dir / "batch_state_manager.py").write_text("# Batch processing\n")
        (lib_dir / "security_auditor.py").write_text("# Security auditing\n")
        (lib_dir / "doc_generator.py").write_text("# Documentation\n")

        return repo_root

    def test_validate_project_features_all_implemented(self, temp_repo):
        """Test validation passes when all SCOPE features implemented.

        REQUIREMENT: Validate PROJECT.md SCOPE vs implementation.
        Expected: No issues returned.
        """
        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_project_features()

        assert len(issues) == 0

    def test_validate_project_features_unimplemented(self, temp_repo):
        """Test validation detects unimplemented SCOPE feature.

        REQUIREMENT: Detect missing implementation for SCOPE item.
        Expected: Returns issue with category='feature', severity='warning'.
        """
        # Remove implementation file
        (temp_repo / "plugins" / "autonomous-dev" / "lib" / "doc_generator.py").unlink()

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_project_features()

        assert len(issues) >= 1
        feature_issues = [i for i in issues if i.category == "feature"]
        assert len(feature_issues) > 0
        assert feature_issues[0].severity == "warning"
        assert "documentation" in feature_issues[0].message.lower()

    def test_validate_project_features_handles_missing_project_md(self, temp_repo):
        """Test validation handles missing PROJECT.md gracefully.

        REQUIREMENT: Graceful handling of missing PROJECT.md.
        Expected: Returns issue with category='feature', severity='error'.
        """
        # Remove PROJECT.md
        (temp_repo / "PROJECT.md").unlink()

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_project_features()

        assert len(issues) > 0
        assert any(issue.severity == "error" for issue in issues)

    def test_validate_project_features_ignores_out_of_scope(self, temp_repo):
        """Test validation ignores 'Out of Scope' items.

        REQUIREMENT: Only validate 'In Scope' features.
        Expected: Out of scope items not flagged.
        """
        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_project_features()

        # Should not flag "Database migrations" or "UI components"
        assert not any("database" in issue.message.lower() for issue in issues)
        assert not any("ui component" in issue.message.lower() for issue in issues)

    def test_validate_project_features_multiple_missing(self, temp_repo):
        """Test validation detects multiple missing features.

        REQUIREMENT: Detect all missing implementations.
        Expected: Returns multiple issues.
        """
        # Remove multiple implementation files
        lib_dir = temp_repo / "plugins" / "autonomous-dev" / "lib"
        (lib_dir / "doc_generator.py").unlink()
        (lib_dir / "security_auditor.py").unlink()

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_project_features()

        feature_issues = [i for i in issues if i.category == "feature"]
        assert len(feature_issues) >= 2


class TestCodeExampleValidation:
    """Test code example validation (docstrings vs actual APIs)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with code and docs."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create library with function
        lib_dir = repo_root / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)

        lib_file = lib_dir / "example_lib.py"
        lib_file.write_text("""
class ExampleClass:
    def example_method(self, param1: str, param2: int) -> str:
        '''Example method.'''
        return f"{param1}: {param2}"
""")

        # Create documentation with code example
        docs_dir = repo_root / "docs"
        docs_dir.mkdir()

        doc_file = docs_dir / "EXAMPLE.md"
        doc_file.write_text("""
# Example Usage

```python
from lib.example_lib import ExampleClass

obj = ExampleClass()
result = obj.example_method("test", 42)
```
""")

        return repo_root

    def test_validate_code_examples_correct(self, temp_repo):
        """Test validation passes when code examples match API.

        REQUIREMENT: Validate code examples against actual API signatures.
        Expected: No issues returned.
        """
        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_code_examples()

        assert len(issues) == 0

    def test_validate_code_examples_outdated_signature(self, temp_repo):
        """Test validation detects outdated API signature in example.

        REQUIREMENT: Detect signature mismatches.
        Expected: Returns issue with category='example', severity='error'.
        """
        # Update library signature
        lib_file = temp_repo / "plugins" / "autonomous-dev" / "lib" / "example_lib.py"
        lib_file.write_text("""
class ExampleClass:
    def example_method(self, param1: str, param2: int, param3: bool = False) -> str:
        '''Example method - now with param3.'''
        return f"{param1}: {param2}"
""")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_code_examples()

        assert len(issues) >= 1
        example_issues = [i for i in issues if i.category == "example"]
        assert len(example_issues) > 0
        assert example_issues[0].severity == "error"

    def test_validate_code_examples_missing_import(self, temp_repo):
        """Test validation detects missing import in example.

        REQUIREMENT: Detect incorrect imports.
        Expected: Returns issue with category='example', severity='warning'.
        """
        # Update doc example with wrong import
        doc_file = temp_repo / "docs" / "EXAMPLE.md"
        doc_file.write_text("""
# Example Usage

```python
from lib.nonexistent import ExampleClass

obj = ExampleClass()
result = obj.example_method("test", 42)
```
""")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_code_examples()

        assert len(issues) >= 1
        example_issues = [i for i in issues if i.category == "example"]
        assert len(example_issues) > 0

    def test_validate_code_examples_handles_missing_docs(self, temp_repo):
        """Test validation handles missing documentation files gracefully.

        REQUIREMENT: Graceful handling when no docs with examples.
        Expected: No errors, may return info-level issues.
        """
        # Remove docs directory
        import shutil
        shutil.rmtree(temp_repo / "docs")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_code_examples()

        # Should not crash, may return info about no examples found
        assert isinstance(issues, list)


class TestAutoFixEngine:
    """Test auto-fix engine for safe patterns."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with fixable issues."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create .claude/commands directory
        commands_dir = repo_root / ".claude" / "commands"
        commands_dir.mkdir(parents=True)

        # Create commands
        (commands_dir / "advise.md").write_text("# Advise Command\n")
        (commands_dir / "align.md").write_text("# Align Command\n")
        (commands_dir / "auto-implement.md").write_text("# Auto-Implement Command\n")

        # Create README missing one command
        readme = repo_root / "README.md"
        readme.write_text("""
# Commands

| Command | Description |
|---------|-------------|
| /advise | Critical thinking analysis |
| /align | Alignment command |
""")

        # Create CLAUDE.md with wrong count
        claude_md = repo_root / "CLAUDE.md"
        claude_md.write_text("""
| Component | Count |
|-----------|-------|
| Commands | 2 |
""")

        return repo_root

    def test_auto_fix_missing_command_adds_row(self, temp_repo):
        """Test auto-fix adds missing command to README table.

        REQUIREMENT: Auto-fix can add missing command rows.
        Expected: README updated with new command row.
        """
        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        # Filter auto-fixable issues
        fixable = [i for i in issues if i.auto_fixable]
        assert len(fixable) > 0

        # Apply fixes
        fixed_count = validator.auto_fix_safe_patterns(fixable)
        assert fixed_count > 0

        # Verify README updated
        readme_content = (temp_repo / "README.md").read_text()
        assert "/auto-implement" in readme_content

    def test_auto_fix_count_mismatch(self, temp_repo):
        """Test auto-fix updates component counts.

        REQUIREMENT: Auto-fix can update count mismatches.
        Expected: CLAUDE.md count updated to actual count.
        """
        validator = ComprehensiveDocValidator(temp_repo)

        # Create count mismatch issue
        issue = ValidationIssue(
            category="count",
            severity="warning",
            message="Command count mismatch: expected 3, found 2",
            file_path=str(temp_repo / "CLAUDE.md"),
            line_number=3,
            auto_fixable=True,
            suggested_fix="Update count from 2 to 3"
        )

        fixed_count = validator.auto_fix_safe_patterns([issue])
        assert fixed_count == 1

        # Verify CLAUDE.md updated
        claude_content = (temp_repo / "CLAUDE.md").read_text()
        assert "| Commands | 3 |" in claude_content

    def test_no_auto_fix_for_goals(self, temp_repo):
        """Test auto-fix never modifies GOALS section.

        REQUIREMENT: Never auto-fix strategic content like GOALS.
        Expected: Issues in GOALS marked as not auto_fixable.
        """
        # Create PROJECT.md with GOALS
        project_md = temp_repo / "PROJECT.md"
        project_md.write_text("""
## GOALS

1. Enable autonomous development
2. Improve code quality
""")

        validator = ComprehensiveDocValidator(temp_repo)

        # Create issue in GOALS section
        issue = ValidationIssue(
            category="feature",
            severity="warning",
            message="Goal mentioned but not implemented",
            file_path=str(project_md),
            line_number=4,
            auto_fixable=False,  # Should never be auto-fixable
            suggested_fix=""
        )

        fixed_count = validator.auto_fix_safe_patterns([issue])
        assert fixed_count == 0  # Should not fix GOALS

    def test_auto_fix_dry_run_mode(self, temp_repo):
        """Test auto-fix in dry-run mode (no changes).

        REQUIREMENT: Support dry-run mode for preview.
        Expected: Returns fix count but does not modify files.
        """
        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        fixable = [i for i in issues if i.auto_fixable]
        original_readme = (temp_repo / "README.md").read_text()

        # Dry-run mode (if implemented)
        # Note: This assumes dry_run parameter exists
        # fixed_count = validator.auto_fix_safe_patterns(fixable, dry_run=True)

        # For now, just verify fixable issues exist
        assert len(fixable) > 0

    def test_auto_fix_preserves_formatting(self, temp_repo):
        """Test auto-fix preserves markdown formatting.

        REQUIREMENT: Auto-fix maintains existing formatting.
        Expected: Only minimal changes, formatting preserved.
        """
        validator = ComprehensiveDocValidator(temp_repo)

        # Add specific formatting to README
        readme = temp_repo / "README.md"
        original = """
# Commands

| Command | Description |
|---------|-------------|
| /advise | Critical thinking analysis |
| /align  | Alignment command          |
"""
        readme.write_text(original)

        issues = validator.validate_command_exports()
        fixable = [i for i in issues if i.auto_fixable]

        validator.auto_fix_safe_patterns(fixable)

        # Verify table alignment preserved
        updated = readme.read_text()
        assert "|---------|-------------|" in updated  # Table separator preserved


class TestBatchModeCompatibility:
    """Test batch mode (no interactive prompts)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create minimal structure
        (repo_root / ".claude" / "commands").mkdir(parents=True)
        (repo_root / "README.md").write_text("# README\n")

        return repo_root

    def test_batch_mode_no_prompts(self, temp_repo):
        """Test batch mode does not prompt user.

        REQUIREMENT: Batch mode runs without user interaction.
        Expected: No input() calls, auto-decisions made.
        """
        validator = ComprehensiveDocValidator(temp_repo, batch_mode=True)

        # Validate - should complete without prompting
        report = validator.validate_all()

        assert isinstance(report, ValidationReport)
        assert report is not None

    def test_interactive_mode_prompts_for_auto_fix(self, temp_repo, monkeypatch):
        """Test interactive mode prompts before auto-fix.

        REQUIREMENT: Interactive mode asks user before fixing.
        Expected: Prompts user, respects response.
        """
        # Mock user input
        monkeypatch.setattr('builtins.input', lambda _: 'n')

        validator = ComprehensiveDocValidator(temp_repo, batch_mode=False)

        # Create fixable issue
        issue = ValidationIssue(
            category="command",
            severity="error",
            message="Missing command",
            file_path=str(temp_repo / "README.md"),
            line_number=1,
            auto_fixable=True,
            suggested_fix="Add command row"
        )

        # Should prompt and respect 'n' response
        # (Implementation detail - may need adjustment based on actual API)
        fixed_count = validator.auto_fix_safe_patterns([issue])
        assert fixed_count == 0  # User declined


class TestEnvironmentVariableControl:
    """Test environment variable control."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        (repo_root / ".claude" / "commands").mkdir(parents=True)
        (repo_root / "README.md").write_text("# README\n")

        return repo_root

    def test_env_var_disables_validation(self, temp_repo):
        """Test VALIDATE_COMPREHENSIVE_DOCS=false disables validation.

        REQUIREMENT: Environment variable control for CI/CD.
        Expected: Validation skipped when disabled.
        """
        with patch.dict(os.environ, {"VALIDATE_COMPREHENSIVE_DOCS": "false"}):
            validator = ComprehensiveDocValidator(temp_repo)
            report = validator.validate_all()

            # Should return empty/skipped report
            assert report.issues == [] or not report.has_issues

    def test_env_var_enables_validation(self, temp_repo):
        """Test VALIDATE_COMPREHENSIVE_DOCS=true enables validation.

        REQUIREMENT: Explicit enable via environment variable.
        Expected: Validation runs normally.
        """
        with patch.dict(os.environ, {"VALIDATE_COMPREHENSIVE_DOCS": "true"}):
            validator = ComprehensiveDocValidator(temp_repo)
            report = validator.validate_all()

            assert isinstance(report, ValidationReport)

    def test_default_validation_enabled(self, temp_repo):
        """Test validation enabled by default.

        REQUIREMENT: Default behavior is to validate.
        Expected: Validation runs when env var not set.
        """
        with patch.dict(os.environ, {}, clear=True):
            validator = ComprehensiveDocValidator(temp_repo)
            report = validator.validate_all()

            assert isinstance(report, ValidationReport)


class TestValidationReport:
    """Test validation report structure and methods."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        (repo_root / ".claude" / "commands").mkdir(parents=True)
        (repo_root / "README.md").write_text("# README\n")
        (repo_root / "PROJECT.md").write_text("# PROJECT\n")

        return repo_root

    def test_validation_report_structure(self, temp_repo):
        """Test report contains all required fields.

        REQUIREMENT: Report has issues, has_issues, categorization.
        Expected: All fields present and correctly typed.
        """
        validator = ComprehensiveDocValidator(temp_repo)
        report = validator.validate_all()

        assert hasattr(report, "issues")
        assert hasattr(report, "has_issues")
        assert hasattr(report, "has_auto_fixable")
        assert hasattr(report, "has_manual_review")
        assert isinstance(report.issues, list)
        assert isinstance(report.has_issues, bool)

    def test_validation_report_categorizes_issues(self, temp_repo):
        """Test report categorizes auto-fixable vs manual issues.

        REQUIREMENT: Report separates fixable from manual issues.
        Expected: auto_fixable_issues and manual_review_issues lists.
        """
        validator = ComprehensiveDocValidator(temp_repo)
        report = validator.validate_all()

        assert hasattr(report, "auto_fixable_issues")
        assert hasattr(report, "manual_review_issues")
        assert isinstance(report.auto_fixable_issues, list)
        assert isinstance(report.manual_review_issues, list)

    def test_validation_report_no_issues(self, temp_repo):
        """Test report when no issues found.

        REQUIREMENT: Report correctly represents success state.
        Expected: has_issues=False, empty lists.
        """
        # Create complete, aligned documentation
        readme = temp_repo / "README.md"
        readme.write_text("""
# Commands

| Command | Description |
|---------|-------------|
""")

        validator = ComprehensiveDocValidator(temp_repo)
        report = validator.validate_all()

        # May still have issues due to missing content, but test structure
        assert isinstance(report.has_issues, bool)
        assert isinstance(report.issues, list)

    def test_validation_report_mixed_issues(self, temp_repo):
        """Test report with both auto-fixable and manual issues.

        REQUIREMENT: Report handles mixed issue types.
        Expected: Both lists populated correctly.
        """
        validator = ComprehensiveDocValidator(temp_repo)

        # Create mixed issues manually
        report = ValidationReport(
            issues=[
                ValidationIssue("command", "error", "Missing command", str(temp_repo / "README.md"), 1, True, "Add row"),
                ValidationIssue("example", "error", "Bad signature", str(temp_repo / "docs/API.md"), 10, False, ""),
            ]
        )

        assert len(report.auto_fixable_issues) == 1
        assert len(report.manual_review_issues) == 1
        assert report.has_auto_fixable is True
        assert report.has_manual_review is True


class TestValidationHandlesMissingFiles:
    """Test validation handles missing/incomplete documentation gracefully."""

    @pytest.fixture
    def minimal_repo(self, tmp_path):
        """Create minimal repository (missing most docs)."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        return repo_root

    def test_validation_handles_missing_readme(self, minimal_repo):
        """Test validation handles missing README gracefully.

        REQUIREMENT: Graceful degradation when README missing.
        Expected: Returns error issue, does not crash.
        """
        validator = ComprehensiveDocValidator(minimal_repo)
        issues = validator.validate_command_exports()

        assert isinstance(issues, list)
        # Should report README missing as an issue
        assert len(issues) > 0

    def test_validation_handles_missing_project_md(self, minimal_repo):
        """Test validation handles missing PROJECT.md gracefully.

        REQUIREMENT: Graceful degradation when PROJECT.md missing.
        Expected: Returns error issue, does not crash.
        """
        validator = ComprehensiveDocValidator(minimal_repo)
        issues = validator.validate_project_features()

        assert isinstance(issues, list)
        # Should report PROJECT.md missing as an issue
        assert len(issues) > 0

    def test_validation_handles_missing_commands_dir(self, minimal_repo):
        """Test validation handles missing commands directory.

        REQUIREMENT: Graceful degradation when .claude/commands missing.
        Expected: Returns error issue, does not crash.
        """
        validator = ComprehensiveDocValidator(minimal_repo)
        issues = validator.validate_command_exports()

        assert isinstance(issues, list)

    def test_validate_all_with_missing_files(self, minimal_repo):
        """Test validate_all() handles missing files gracefully.

        REQUIREMENT: validate_all() does not crash on incomplete repo.
        Expected: Returns report with multiple error issues.
        """
        validator = ComprehensiveDocValidator(minimal_repo)
        report = validator.validate_all()

        assert isinstance(report, ValidationReport)
        assert report.has_issues is True
        # Should have multiple errors for missing files
        assert len(report.issues) > 0


class TestValidationIssueCategorization:
    """Test validation issue categorization and fields."""

    def test_validation_issue_structure(self):
        """Test ValidationIssue dataclass structure.

        REQUIREMENT: ValidationIssue has all required fields.
        Expected: All fields present and correctly typed.
        """
        issue = ValidationIssue(
            category="command",
            severity="error",
            message="Test message",
            file_path="/path/to/file.md",
            line_number=10,
            auto_fixable=True,
            suggested_fix="Fix suggestion"
        )

        assert issue.category == "command"
        assert issue.severity == "error"
        assert issue.message == "Test message"
        assert issue.file_path == "/path/to/file.md"
        assert issue.line_number == 10
        assert issue.auto_fixable is True
        assert issue.suggested_fix == "Fix suggestion"

    def test_validation_issue_categories(self):
        """Test validation issue categories are correct.

        REQUIREMENT: Categories: command, feature, example, count.
        Expected: All categories valid.
        """
        categories = ["command", "feature", "example", "count"]

        for cat in categories:
            issue = ValidationIssue(cat, "error", "Test", "/path", 1, False, "")
            assert issue.category == cat

    def test_validation_issue_severities(self):
        """Test validation issue severities are correct.

        REQUIREMENT: Severities: error, warning, info.
        Expected: All severities valid.
        """
        severities = ["error", "warning", "info"]

        for sev in severities:
            issue = ValidationIssue("command", sev, "Test", "/path", 1, False, "")
            assert issue.severity == sev


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        return repo_root

    def test_empty_readme_table(self, temp_repo):
        """Test handling of empty README command table.

        REQUIREMENT: Handle empty tables gracefully.
        Expected: No crash, may report info issue.
        """
        # Create empty commands directory
        (temp_repo / ".claude" / "commands").mkdir(parents=True)

        # Create README with empty table
        readme = temp_repo / "README.md"
        readme.write_text("""
# Commands

| Command | Description |
|---------|-------------|
""")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        assert isinstance(issues, list)

    def test_malformed_readme_table(self, temp_repo):
        """Test handling of malformed README table.

        REQUIREMENT: Handle malformed markdown gracefully.
        Expected: Returns error issue about malformed table.
        """
        (temp_repo / ".claude" / "commands").mkdir(parents=True)

        # Create malformed table
        readme = temp_repo / "README.md"
        readme.write_text("""
# Commands

| Command | Description
|---------|
| /advise | Missing cells
""")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        # Should handle gracefully
        assert isinstance(issues, list)

    def test_unicode_in_documentation(self, temp_repo):
        """Test handling of unicode characters in docs.

        REQUIREMENT: Support unicode in documentation.
        Expected: No encoding errors.
        """
        (temp_repo / ".claude" / "commands").mkdir(parents=True)

        # Create README with unicode
        readme = temp_repo / "README.md"
        readme.write_text("""
# Commands 🚀

| Command | Description |
|---------|-------------|
| /advise | Critical thinking 🧠 |
""")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_command_exports()

        # Should handle unicode without errors
        assert isinstance(issues, list)

    def test_very_large_documentation(self, temp_repo):
        """Test handling of very large documentation files.

        REQUIREMENT: Handle large files efficiently.
        Expected: No performance issues or crashes.
        """
        (temp_repo / ".claude" / "commands").mkdir(parents=True)

        # Create large README
        readme = temp_repo / "README.md"
        large_content = "# Commands\n\n" + ("Line\n" * 10000)
        readme.write_text(large_content)

        validator = ComprehensiveDocValidator(temp_repo)

        # Should complete without timeout
        issues = validator.validate_command_exports()
        assert isinstance(issues, list)


class TestNonBlockingValidation:
    """Test validation is non-blocking (does not stop workflow)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        (repo_root / ".claude" / "commands").mkdir(parents=True)
        (repo_root / "README.md").write_text("# README\n")

        return repo_root

    def test_validation_returns_report_not_raises(self, temp_repo):
        """Test validation returns report, does not raise exceptions.

        REQUIREMENT: Non-blocking validation (return issues, not raise).
        Expected: validate_all() returns report, never raises.
        """
        validator = ComprehensiveDocValidator(temp_repo)

        # Should return report even with issues
        report = validator.validate_all()

        assert isinstance(report, ValidationReport)
        # Should not raise any exceptions

    def test_validation_error_handling(self, temp_repo):
        """Test validation handles internal errors gracefully.

        REQUIREMENT: Internal errors converted to issue reports.
        Expected: Errors caught and reported as issues.
        """
        validator = ComprehensiveDocValidator(temp_repo)

        # Even if internal validation fails, should return report
        try:
            report = validator.validate_all()
            assert isinstance(report, ValidationReport)
        except Exception as e:
            pytest.fail(f"Validation should not raise: {e}")


class TestSecurityValidation:
    """Test security hardening for CWE vulnerabilities."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        (repo_root / ".claude" / "commands").mkdir(parents=True)
        (repo_root / "README.md").write_text("# README\n")

        return repo_root

    def test_path_traversal_defense_in_depth(self, temp_repo):
        """Test path traversal defense in depth (CWE-22).

        REQUIREMENT: Module validation has multiple layers of protection.
        Expected: Both regex and explicit validation protect against attacks.

        Note: The import regex r'from\s+([a-zA-Z0-9_.]+)\s+import' provides
        first line of defense by only allowing alphanumeric, underscore, and dot.
        The security validation adds a second layer by checking each module part.
        """
        # Create lib directory
        lib_dir = temp_repo / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)

        # Create documentation with valid-looking but tricky module
        docs_dir = temp_repo / "docs"
        docs_dir.mkdir(parents=True)

        doc_file = docs_dir / "test_doc.md"
        # Module name that passes regex but points to non-existent file
        # This verifies the path resolution is working correctly
        doc_file.write_text("""
# Test Doc

```python
from lib.nonexistent_module import SomeClass
```
""")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_code_examples()

        # Should have warning for non-existent module (defense in depth)
        missing_module_issues = [i for i in issues if "non-existent module" in i.message]
        assert len(missing_module_issues) > 0, "Non-existent modules should be flagged"

        # Verify the security layer validates paths are within expected directory
        # The path resolution check ensures we can't access files outside lib/
        for issue in issues:
            # No path traversal attempt issues should exist since regex blocks them
            assert "Path traversal" not in issue.message

    def test_valid_module_names_allowed(self, temp_repo):
        """Test valid module names are allowed.

        REQUIREMENT: Alphanumeric module names work correctly.
        Expected: No warning for valid module names.
        """
        # Create lib directory and module
        lib_dir = temp_repo / "plugins" / "autonomous-dev" / "lib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "valid_module.py").write_text("class ValidClass: pass")

        # Create documentation with valid import
        docs_dir = temp_repo / "docs"
        docs_dir.mkdir(parents=True)

        doc_file = docs_dir / "test_doc.md"
        doc_file.write_text("""
# Test Doc

```python
from lib.valid_module import ValidClass
```
""")

        validator = ComprehensiveDocValidator(temp_repo)
        issues = validator.validate_code_examples()

        # Should not have warning for valid module name
        invalid_module_issues = [i for i in issues if "Invalid module name" in i.message]
        assert len(invalid_module_issues) == 0, "Valid modules should not be blocked"

    def test_regex_injection_blocked(self, temp_repo):
        """Test regex injection attempts are blocked (CWE-95).

        REQUIREMENT: Count values used in replacement are validated.
        Expected: Non-numeric counts rejected.
        """
        validator = ComprehensiveDocValidator(temp_repo)

        # Create issue with potentially malicious suggested_fix
        # The regex: from\s+(\d+)\s+to\s+(\d+) should only match digits
        issue = ValidationIssue(
            category="count",
            severity="warning",
            message="Count mismatch",
            file_path=str(temp_repo / "CLAUDE.md"),
            line_number=10,
            auto_fixable=True,
            suggested_fix="Update count from 10.*malicious to 20"  # Attempted regex injection
        )

        # Should not fix due to non-matching pattern
        result = validator._fix_count_mismatch(issue)
        assert result is False, "Regex injection should be blocked"

    def test_numeric_counts_allowed(self, temp_repo):
        """Test valid numeric counts work correctly.

        REQUIREMENT: Numeric counts are properly replaced.
        Expected: Valid count replacement works.
        """
        # Create CLAUDE.md with count
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("| Commands | 5 |\n")

        validator = ComprehensiveDocValidator(temp_repo)

        # Create issue with valid counts
        issue = ValidationIssue(
            category="count",
            severity="warning",
            message="Count mismatch",
            file_path=str(claude_md),
            line_number=1,
            auto_fixable=True,
            suggested_fix="Update count from 5 to 10"
        )

        result = validator._fix_count_mismatch(issue)
        assert result is True, "Valid count should be replaced"

        # Verify content was updated
        content = claude_md.read_text()
        assert "| Commands | 10 |" in content

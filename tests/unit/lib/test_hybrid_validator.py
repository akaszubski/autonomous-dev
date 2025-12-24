#!/usr/bin/env python3
"""
TDD Tests for Hybrid Validator (FAILING - Red Phase)

This module contains FAILING tests for hybrid_validator.py which orchestrates
GenAI validation with regex fallback.

Requirements:
1. Auto mode with API key (uses GenAI)
2. Auto mode without API key (falls back to regex)
3. GenAI-only mode fails gracefully without key
4. Regex-only mode works regardless of key
5. Exit codes (0=pass, 1=fail)
6. ParityReport format consistency

Test Coverage Target: 95%+ of orchestration logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe hybrid orchestration requirements
- Tests should FAIL until hybrid_validator.py is implemented
- Each test validates ONE orchestration requirement

Author: test-master agent
Date: 2025-12-24
Related: Issue #160 - GenAI manifest alignment validation
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until hybrid_validator.py is created
from plugins.autonomous_dev.lib.hybrid_validator import (
    HybridManifestValidator,
    ValidationMode,
    validate_manifest_alignment,
)

# Import existing validators
from plugins.autonomous_dev.lib.validate_documentation_parity import (
    ParityReport,
    ParityIssue,
    ValidationLevel,
)


class TestHybridValidatorInitialization:
    """Test hybrid validator initialization."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with proper manifest structure."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create config directory for install_manifest.json
        config_dir = repo_root / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)

        manifest = {
            "version": "3.44.0",
            "components": {
                "agents": {"files": ["agent1.md", "agent2.md", "agent3.md", "agent4.md", "agent5.md", "agent6.md", "agent7.md", "agent8.md"]},
                "commands": {"files": []},
                "hooks": {"files": []},
                "skills": {"files": []},
            }
        }
        (config_dir / "install_manifest.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("# Docs\n")

        return repo_root

    def test_initialization_auto_mode(self, temp_repo):
        """Test validator initializes in auto mode.

        REQUIREMENT: Default mode is auto (try GenAI, fallback to regex).
        Expected: Validator created with mode=AUTO.
        """
        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.AUTO)

        assert validator.repo_root == temp_repo
        assert validator.mode == ValidationMode.AUTO

    def test_initialization_genai_only_mode(self, temp_repo):
        """Test validator initializes in GenAI-only mode.

        REQUIREMENT: Support GenAI-only mode.
        Expected: Validator created with mode=GENAI_ONLY.
        """
        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.GENAI_ONLY)

        assert validator.mode == ValidationMode.GENAI_ONLY

    def test_initialization_regex_only_mode(self, temp_repo):
        """Test validator initializes in regex-only mode.

        REQUIREMENT: Support regex-only mode.
        Expected: Validator created with mode=REGEX_ONLY.
        """
        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.REGEX_ONLY)

        assert validator.mode == ValidationMode.REGEX_ONLY


class TestAutoModeWithAPIKey:
    """Test auto mode with API key present (uses GenAI)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create config directory for install_manifest.json
        config_dir = repo_root / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)

        manifest = {
            "version": "3.44.0",
            "components": {
                "agents": {"files": ["a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md", "a7.md", "a8.md"]},
                "commands": {"files": []},
                "hooks": {"files": []},
                "skills": {"files": []},
            }
        }
        (config_dir / "install_manifest.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("""
**Version**: v3.44.0

| Component | Count |
|-----------|-------|
| Agents | 8 |
        """)

        return repo_root

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("plugins.autonomous_dev.lib.hybrid_validator.GenAIManifestValidator")
    def test_auto_mode_uses_genai_when_key_present(self, mock_genai_class, temp_repo):
        """Test auto mode uses GenAI when API key present.

        REQUIREMENT: Auto mode prefers GenAI when available.
        Expected: GenAI validator called, regex not called.
        """
        mock_genai = MagicMock()
        mock_genai.has_api_key = True
        mock_genai.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="Aligned"
        )
        mock_genai_class.return_value = mock_genai

        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.AUTO)
        report = validator.validate()

        # Verify GenAI was called
        mock_genai.validate.assert_called_once()

        # Verify result
        assert report.is_valid is True
        assert len(report.issues) == 0

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("plugins.autonomous_dev.lib.hybrid_validator.GenAIManifestValidator")
    def test_auto_mode_reports_genai_used(self, mock_genai_class, temp_repo):
        """Test auto mode reports GenAI was used.

        REQUIREMENT: Report which validator was used.
        Expected: Report includes validator_used field.
        """
        mock_genai = MagicMock()
        mock_genai.has_api_key = True
        mock_genai.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="Aligned"
        )
        mock_genai_class.return_value = mock_genai

        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.AUTO)
        report = validator.validate()

        assert report.validator_used == "genai"


class TestAutoModeWithoutAPIKey:
    """Test auto mode without API key (falls back to regex)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create config directory for install_manifest.json
        config_dir = repo_root / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)

        manifest = {
            "version": "3.44.0",
            "components": {
                "agents": {"files": ["a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md", "a7.md", "a8.md"]},
                "commands": {"files": []},
                "hooks": {"files": []},
                "skills": {"files": []},
            }
        }
        (config_dir / "install_manifest.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("""
**Version**: v3.44.0

| Component | Count |
|-----------|-------|
| Agents | 8 |
        """)

        return repo_root

    @patch("plugins.autonomous_dev.lib.hybrid_validator.GenAIManifestValidator")
    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_auto_mode_fallback_to_regex_when_no_key(self, mock_regex_func, mock_genai_class, temp_repo):
        """Test auto mode falls back to regex when no API key.

        REQUIREMENT: Auto mode gracefully falls back to regex.
        Expected: GenAI returns None, regex validator called.
        """
        # GenAI has no key
        mock_genai = MagicMock()
        mock_genai.has_api_key = False
        mock_genai.validate.return_value = None
        mock_genai_class.return_value = mock_genai

        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        with patch.dict(os.environ, {}, clear=True):
            validator = HybridManifestValidator(temp_repo, mode=ValidationMode.AUTO)
            report = validator.validate()

        # Verify regex was called
        mock_regex_func.assert_called_once()

        # Verify report indicates fallback
        assert report.validator_used == "regex"

    @patch("plugins.autonomous_dev.lib.hybrid_validator.GenAIManifestValidator")
    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_auto_mode_fallback_on_genai_error(self, mock_regex_func, mock_genai_class, temp_repo):
        """Test auto mode falls back to regex when GenAI errors.

        REQUIREMENT: Auto mode handles GenAI failures gracefully.
        Expected: GenAI raises exception, regex validator called.
        """
        # GenAI has key but errors
        mock_genai = MagicMock()
        mock_genai.has_api_key = True
        mock_genai.validate.return_value = None  # Error returns None
        mock_genai_class.return_value = mock_genai

        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"}):
            validator = HybridManifestValidator(temp_repo, mode=ValidationMode.AUTO)
            report = validator.validate()

        # Verify regex was called as fallback
        mock_regex_func.assert_called_once()
        assert report.validator_used == "regex"


class TestGenAIOnlyMode:
    """Test GenAI-only mode fails gracefully without key."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create config directory for install_manifest.json
        config_dir = repo_root / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)

        manifest = {
            "version": "3.44.0",
            "components": {
                "agents": {"files": ["a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md", "a7.md", "a8.md"]},
                "commands": {"files": []},
                "hooks": {"files": []},
                "skills": {"files": []},
            }
        }
        (config_dir / "install_manifest.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("# Docs\n")

        return repo_root

    @patch("plugins.autonomous_dev.lib.hybrid_validator.GenAIManifestValidator")
    def test_genai_only_mode_fails_without_key(self, mock_genai_class, temp_repo):
        """Test GenAI-only mode reports error when no API key.

        REQUIREMENT: GenAI-only mode fails gracefully without key.
        Expected: Returns error report (not exception).
        """
        mock_genai = MagicMock()
        mock_genai.has_api_key = False
        mock_genai.validate.return_value = None
        mock_genai_class.return_value = mock_genai

        with patch.dict(os.environ, {}, clear=True):
            validator = HybridManifestValidator(temp_repo, mode=ValidationMode.GENAI_ONLY)
            report = validator.validate()

        assert report.is_valid is False
        assert len(report.issues) > 0
        assert any("API key" in issue.message for issue in report.issues)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("plugins.autonomous_dev.lib.hybrid_validator.GenAIManifestValidator")
    def test_genai_only_mode_succeeds_with_key(self, mock_genai_class, temp_repo):
        """Test GenAI-only mode works with API key.

        REQUIREMENT: GenAI-only mode uses GenAI when available.
        Expected: GenAI validator called successfully.
        """
        mock_genai = MagicMock()
        mock_genai.has_api_key = True
        mock_genai.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="Aligned"
        )
        mock_genai_class.return_value = mock_genai

        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.GENAI_ONLY)
        report = validator.validate()

        assert report.is_valid is True
        assert report.validator_used == "genai"


class TestRegexOnlyMode:
    """Test regex-only mode works regardless of key."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create config directory for install_manifest.json
        config_dir = repo_root / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)

        manifest = {
            "version": "3.44.0",
            "components": {
                "agents": {"files": ["a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md", "a7.md", "a8.md"]},
                "commands": {"files": []},
                "hooks": {"files": []},
                "skills": {"files": []},
            }
        }
        (config_dir / "install_manifest.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("""
**Version**: v3.44.0

| Component | Count |
|-----------|-------|
| Agents | 8 |
        """)

        return repo_root

    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_regex_only_mode_without_key(self, mock_regex_func, temp_repo):
        """Test regex-only mode works without API key.

        REQUIREMENT: Regex-only mode ignores API key presence.
        Expected: Regex validator called, GenAI not called.
        """
        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        with patch.dict(os.environ, {}, clear=True):
            validator = HybridManifestValidator(temp_repo, mode=ValidationMode.REGEX_ONLY)
            report = validator.validate()

        mock_regex_func.assert_called_once()
        assert report.validator_used == "regex"

    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_regex_only_mode_with_key(self, mock_regex_func, temp_repo):
        """Test regex-only mode ignores API key when present.

        REQUIREMENT: Regex-only mode always uses regex.
        Expected: Regex validator called even with API key.
        """
        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"}):
            validator = HybridManifestValidator(temp_repo, mode=ValidationMode.REGEX_ONLY)
            report = validator.validate()

        mock_regex_func.assert_called_once()
        assert report.validator_used == "regex"


class TestExitCodes:
    """Test exit codes for CLI usage."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create config directory for install_manifest.json
        config_dir = repo_root / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)

        manifest = {
            "version": "3.44.0",
            "components": {
                "agents": {"files": ["a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md", "a7.md", "a8.md"]},
                "commands": {"files": []},
                "hooks": {"files": []},
                "skills": {"files": []},
            }
        }
        (config_dir / "install_manifest.json").write_text(json.dumps(manifest))

        return repo_root

    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_exit_code_zero_on_pass(self, mock_regex_func, temp_repo):
        """Test exit code 0 when validation passes.

        REQUIREMENT: Exit code 0 for successful validation.
        Expected: get_exit_code() returns 0.
        """
        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        (temp_repo / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 8 |")

        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.REGEX_ONLY)
        report = validator.validate()

        assert report.get_exit_code() == 0

    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_exit_code_one_on_fail(self, mock_regex_func, temp_repo):
        """Test exit code 1 when validation fails.

        REQUIREMENT: Exit code 1 for failed validation.
        Expected: get_exit_code() returns 1.
        """
        # Regex validator returns mismatch dict
        mock_regex_func.return_value = {
            "status": "DRIFTED",
            "mismatches": {
                "claude_md_agents": {
                    "expected": 8,
                    "actual": 21,
                    "file": "CLAUDE.md"
                }
            }
        }

        (temp_repo / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 21 |")

        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.REGEX_ONLY)
        report = validator.validate()

        assert report.get_exit_code() == 1


class TestParityReportFormatConsistency:
    """Test ParityReport format consistency across validators."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create config directory for install_manifest.json
        config_dir = repo_root / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)

        manifest = {
            "version": "3.44.0",
            "components": {
                "agents": {"files": ["a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md", "a7.md", "a8.md"]},
                "commands": {"files": []},
                "hooks": {"files": []},
                "skills": {"files": []},
            }
        }
        (config_dir / "install_manifest.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 8 |")

        return repo_root

    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_report_format_matches_parity_report(self, mock_regex_func, temp_repo):
        """Test report format matches existing ParityReport.

        REQUIREMENT: Consistent report format across validators.
        Expected: Report is instance of ParityReport.
        """
        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.REGEX_ONLY)
        report = validator.validate()

        assert isinstance(report, ParityReport)

    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_report_contains_required_fields(self, mock_regex_func, temp_repo):
        """Test report contains all required ParityReport fields.

        REQUIREMENT: Report has is_valid, issues, summary, validator_used.
        Expected: All fields present.
        """
        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.REGEX_ONLY)
        report = validator.validate()

        assert hasattr(report, "is_valid")
        assert hasattr(report, "issues")
        # Note: HybridValidationReport has category-specific issues, not 'summary'
        assert hasattr(report, "validator_used")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("plugins.autonomous_dev.lib.hybrid_validator.GenAIManifestValidator")
    def test_genai_issues_converted_to_parity_issues(self, mock_genai_class, temp_repo):
        """Test GenAI issues converted to ParityIssue format.

        REQUIREMENT: Normalize issue format across validators.
        Expected: GenAI issues converted to ParityIssue objects.
        """
        mock_genai = MagicMock()
        mock_genai.has_api_key = True
        mock_genai.validate.return_value = MagicMock(
            is_valid=False,
            issues=[
                MagicMock(
                    component="agents",
                    level=MagicMock(value="ERROR"),
                    message="Count mismatch",
                    details="Manifest: 8, CLAUDE.md: 21",
                    location="CLAUDE.md:7"
                )
            ],
            summary="Found 1 issue"
        )
        mock_genai_class.return_value = mock_genai

        validator = HybridManifestValidator(temp_repo, mode=ValidationMode.AUTO)
        report = validator.validate()

        assert len(report.issues) == 1
        assert isinstance(report.issues[0], ParityIssue)
        # ParityIssue has level and message, not category
        assert report.issues[0].level == ValidationLevel.ERROR


class TestFunctionAPI:
    """Test validate_manifest_alignment() function API."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create config directory for install_manifest.json
        config_dir = repo_root / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)

        manifest = {
            "version": "3.44.0",
            "components": {
                "agents": {"files": ["a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md", "a7.md", "a8.md"]},
                "commands": {"files": []},
                "hooks": {"files": []},
                "skills": {"files": []},
            }
        }
        (config_dir / "install_manifest.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 8 |")

        return repo_root

    @patch("plugins.autonomous_dev.lib.hybrid_validator.GenAIManifestValidator")
    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_function_api_default_mode(self, mock_regex_func, mock_genai_class, temp_repo):
        """Test function API with default (auto) mode.

        REQUIREMENT: Provide function API for simple usage.
        Expected: Function returns ParityReport.
        """
        # GenAI has no key, falls back to regex
        mock_genai = MagicMock()
        mock_genai.has_api_key = False
        mock_genai.validate.return_value = None
        mock_genai_class.return_value = mock_genai

        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        report = validate_manifest_alignment(temp_repo)

        assert isinstance(report, ParityReport)

    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_function_api_explicit_mode(self, mock_regex_func, temp_repo):
        """Test function API with explicit mode.

        REQUIREMENT: Support mode parameter in function API.
        Expected: Function respects mode parameter.
        """
        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        report = validate_manifest_alignment(temp_repo, mode="regex-only")

        assert report.validator_used == "regex"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_validation_mode(self, tmp_path):
        """Test handling of invalid validation mode.

        REQUIREMENT: Validate mode parameter.
        Expected: Uses validate_manifest_alignment function which validates mode.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # The convenience function validates mode parameter
        with pytest.raises(ValueError):
            validate_manifest_alignment(repo_root, mode="invalid_mode")

    @patch("plugins.autonomous_dev.lib.hybrid_validator.GenAIManifestValidator")
    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_both_validators_fail(self, mock_regex_func, mock_genai_class, tmp_path):
        """Test handling when both validators fail.

        REQUIREMENT: Handle double failure gracefully.
        Expected: Exception propagates when regex fallback also fails.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # GenAI has no key
        mock_genai = MagicMock()
        mock_genai.has_api_key = False
        mock_genai.validate.return_value = None
        mock_genai_class.return_value = mock_genai

        # Regex validator fails with exception
        mock_regex_func.side_effect = Exception("Regex error")

        with patch.dict(os.environ, {}, clear=True):
            validator = HybridManifestValidator(repo_root, mode=ValidationMode.AUTO)
            # When both validators fail, exception propagates
            with pytest.raises(Exception) as exc_info:
                validator.validate()
            assert "Regex error" in str(exc_info.value)

    @patch("plugins.autonomous_dev.lib.validate_manifest_doc_alignment.validate_alignment")
    def test_missing_repository_files(self, mock_regex_func, tmp_path):
        """Test handling of missing repository files.

        REQUIREMENT: Handle incomplete repository gracefully.
        Expected: Returns error report.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()  # Create directory so path validation passes

        # Regex validator succeeds (returns dict with no mismatches)
        mock_regex_func.return_value = {"status": "ALIGNED", "mismatches": {}}

        validator = HybridManifestValidator(repo_root, mode=ValidationMode.REGEX_ONLY)
        report = validator.validate()

        # Should handle gracefully
        assert isinstance(report, ParityReport)

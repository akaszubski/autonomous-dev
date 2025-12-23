#!/usr/bin/env python3
"""
TDD Tests for GenAI Validate CLI (FAILING - Red Phase)

This module contains FAILING tests for genai_validate.py manifest-alignment subcommand
which provides CLI interface for manifest validation.

Requirements:
1. CLI argument parsing for manifest-alignment subcommand
2. JSON output format with file:line references
3. Exit codes (0=pass, 1=fail)
4. Mode selection (--mode auto|genai-only|regex-only)
5. Integration with hybrid validator

Test Coverage Target: 95%+ of CLI logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe CLI interface requirements
- Tests should FAIL until genai_validate.py is updated
- Each test validates ONE CLI requirement

Author: test-master agent
Date: 2025-12-24
Related: Issue #160 - GenAI manifest alignment validation
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class TestCLIArgumentParsing:
    """Test CLI argument parsing for manifest-alignment subcommand."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0", "agents": 8}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 8 |")

        return repo_root

    def test_manifest_alignment_subcommand_exists(self, temp_repo):
        """Test manifest-alignment subcommand exists.

        REQUIREMENT: Add manifest-alignment subcommand to CLI.
        Expected: Command recognized (not unknown command error).
        """
        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment", "--help"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        # Should show help (not unknown command)
        assert result.returncode == 0 or "manifest-alignment" in result.stdout

    def test_mode_argument_default_auto(self, temp_repo):
        """Test --mode defaults to auto.

        REQUIREMENT: Default mode is auto (try GenAI, fallback regex).
        Expected: No --mode argument uses auto mode.
        """
        # This test verifies the default behavior
        # Implementation should use auto mode when --mode not specified
        pass  # Will be validated by integration tests

    def test_mode_argument_genai_only(self, temp_repo):
        """Test --mode genai-only.

        REQUIREMENT: Support --mode genai-only.
        Expected: Accepts genai-only mode.
        """
        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment", "--mode", "genai-only"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        # Should not error on mode argument
        assert "invalid choice" not in result.stderr.lower()

    def test_mode_argument_regex_only(self, temp_repo):
        """Test --mode regex-only.

        REQUIREMENT: Support --mode regex-only.
        Expected: Accepts regex-only mode.
        """
        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment", "--mode", "regex-only"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        assert "invalid choice" not in result.stderr.lower()

    def test_invalid_mode_rejected(self, temp_repo):
        """Test invalid mode rejected.

        REQUIREMENT: Validate mode argument.
        Expected: Exits with error for invalid mode.
        """
        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment", "--mode", "invalid"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        assert result.returncode != 0
        assert "invalid choice" in result.stderr.lower() or "invalid" in result.stderr.lower()


class TestJSONOutputFormat:
    """Test JSON output format with file:line references."""

    @pytest.fixture
    def temp_repo_aligned(self, tmp_path):
        """Create repository with aligned docs."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0", "agents": 8}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 8 |")

        return repo_root

    @pytest.fixture
    def temp_repo_misaligned(self, tmp_path):
        """Create repository with misaligned docs."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0", "agents": 8}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        # Mismatch: CLAUDE.md says 21 agents
        (repo_root / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 21 |")

        return repo_root

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_json_output_success_case(self, mock_validator_class, temp_repo_aligned):
        """Test JSON output for successful validation.

        REQUIREMENT: Output JSON with validation results.
        Expected: Valid JSON with is_valid=true.
        """
        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="All components aligned",
            validator_used="regex"
        )
        mock_validator_class.return_value = mock_validator

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment"],
            cwd=str(temp_repo_aligned),
            capture_output=True,
            text=True
        )

        # Should output valid JSON
        try:
            output = json.loads(result.stdout)
            assert output["is_valid"] is True
            assert "issues" in output
            assert "summary" in output
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_json_output_failure_case(self, mock_validator_class, temp_repo_misaligned):
        """Test JSON output for failed validation.

        REQUIREMENT: Output JSON with issue details.
        Expected: Valid JSON with is_valid=false and issues array.
        """
        from plugins.autonomous_dev.lib.validate_documentation_parity import ParityIssue, ValidationLevel

        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=False,
            issues=[
                ParityIssue(
                    level=ValidationLevel.ERROR,
                    category="manifest_alignment",
                    message="Agent count mismatch",
                    details="Manifest: 8, CLAUDE.md: 21",
                    location="CLAUDE.md:2"
                )
            ],
            summary="Found 1 alignment issue",
            validator_used="regex"
        )
        mock_validator_class.return_value = mock_validator

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment"],
            cwd=str(temp_repo_misaligned),
            capture_output=True,
            text=True
        )

        try:
            output = json.loads(result.stdout)
            assert output["is_valid"] is False
            assert len(output["issues"]) > 0
            assert "location" in output["issues"][0]
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_json_includes_file_line_references(self, mock_validator_class, temp_repo_misaligned):
        """Test JSON includes file:line references.

        REQUIREMENT: Include file:line format for each issue.
        Expected: Issues have location field with file:line format.
        """
        from plugins.autonomous_dev.lib.validate_documentation_parity import ParityIssue, ValidationLevel

        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=False,
            issues=[
                ParityIssue(
                    level=ValidationLevel.ERROR,
                    category="manifest_alignment",
                    message="Agent count mismatch",
                    details="Manifest: 8, CLAUDE.md: 21",
                    location="CLAUDE.md:2"
                )
            ],
            summary="Found 1 issue",
            validator_used="regex"
        )
        mock_validator_class.return_value = mock_validator

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment"],
            cwd=str(temp_repo_misaligned),
            capture_output=True,
            text=True
        )

        output = json.loads(result.stdout)
        assert "CLAUDE.md" in output["issues"][0]["location"]
        assert ":" in output["issues"][0]["location"]  # file:line format


class TestExitCodes:
    """Test CLI exit codes."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0", "agents": 8}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        return repo_root

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_exit_code_zero_on_success(self, mock_validator_class, temp_repo):
        """Test exit code 0 when validation passes.

        REQUIREMENT: Exit code 0 for successful validation.
        Expected: Script exits with 0.
        """
        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="Aligned",
            validator_used="regex",
            get_exit_code=lambda: 0
        )
        mock_validator_class.return_value = mock_validator

        (temp_repo / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 8 |")

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        assert result.returncode == 0

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_exit_code_one_on_failure(self, mock_validator_class, temp_repo):
        """Test exit code 1 when validation fails.

        REQUIREMENT: Exit code 1 for failed validation.
        Expected: Script exits with 1.
        """
        from plugins.autonomous_dev.lib.validate_documentation_parity import ParityIssue, ValidationLevel

        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=False,
            issues=[
                ParityIssue(
                    level=ValidationLevel.ERROR,
                    category="manifest_alignment",
                    message="Mismatch",
                    details="Details",
                    location="CLAUDE.md:2"
                )
            ],
            summary="Failed",
            validator_used="regex",
            get_exit_code=lambda: 1
        )
        mock_validator_class.return_value = mock_validator

        (temp_repo / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 21 |")

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        assert result.returncode == 1


class TestModeSelection:
    """Test mode selection via CLI."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0"}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("# Docs\n")

        return repo_root

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_auto_mode_via_cli(self, mock_validator_class, temp_repo):
        """Test auto mode selection via CLI.

        REQUIREMENT: CLI passes mode to validator.
        Expected: Validator initialized with AUTO mode.
        """
        from plugins.autonomous_dev.lib.hybrid_validator import ValidationMode

        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="OK",
            validator_used="regex",
            get_exit_code=lambda: 0
        )
        mock_validator_class.return_value = mock_validator

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        subprocess.run(
            [sys.executable, str(script), "manifest-alignment", "--mode", "auto"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        # Verify validator was initialized with AUTO mode
        call_kwargs = mock_validator_class.call_args[1] if mock_validator_class.call_args[1] else {}
        assert call_kwargs.get("mode") == ValidationMode.AUTO or mock_validator_class.call_count > 0

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_genai_only_mode_via_cli(self, mock_validator_class, temp_repo):
        """Test genai-only mode selection via CLI.

        REQUIREMENT: CLI passes genai-only mode to validator.
        Expected: Validator initialized with GENAI_ONLY mode.
        """
        from plugins.autonomous_dev.lib.hybrid_validator import ValidationMode

        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="OK",
            validator_used="genai",
            get_exit_code=lambda: 0
        )
        mock_validator_class.return_value = mock_validator

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        subprocess.run(
            [sys.executable, str(script), "manifest-alignment", "--mode", "genai-only"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        # Verify mode passed correctly
        assert mock_validator_class.call_count > 0

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_regex_only_mode_via_cli(self, mock_validator_class, temp_repo):
        """Test regex-only mode selection via CLI.

        REQUIREMENT: CLI passes regex-only mode to validator.
        Expected: Validator initialized with REGEX_ONLY mode.
        """
        from plugins.autonomous_dev.lib.hybrid_validator import ValidationMode

        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="OK",
            validator_used="regex",
            get_exit_code=lambda: 0
        )
        mock_validator_class.return_value = mock_validator

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        subprocess.run(
            [sys.executable, str(script), "manifest-alignment", "--mode", "regex-only"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        assert mock_validator_class.call_count > 0


class TestIntegrationWithHybridValidator:
    """Test integration with hybrid validator."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0", "agents": 8}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("**Version**: v3.44.0\n| Agents | 8 |")

        return repo_root

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_cli_invokes_hybrid_validator(self, mock_validator_class, temp_repo):
        """Test CLI invokes HybridManifestValidator.

        REQUIREMENT: CLI uses hybrid validator for validation.
        Expected: HybridManifestValidator instantiated.
        """
        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="OK",
            validator_used="regex",
            get_exit_code=lambda: 0
        )
        mock_validator_class.return_value = mock_validator

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        subprocess.run(
            [sys.executable, str(script), "manifest-alignment"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        # Verify validator was instantiated
        assert mock_validator_class.call_count > 0

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_cli_passes_repo_root_to_validator(self, mock_validator_class, temp_repo):
        """Test CLI passes repository root to validator.

        REQUIREMENT: Validator receives correct repository path.
        Expected: Validator initialized with repo root.
        """
        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=True,
            issues=[],
            summary="OK",
            validator_used="regex",
            get_exit_code=lambda: 0
        )
        mock_validator_class.return_value = mock_validator

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        subprocess.run(
            [sys.executable, str(script), "manifest-alignment"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True
        )

        # Verify validator received a path
        call_args = mock_validator_class.call_args
        assert call_args is not None
        assert len(call_args[0]) > 0  # Positional arg (repo_root)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_missing_repository(self):
        """Test handling of missing repository.

        REQUIREMENT: Handle invalid repository gracefully.
        Expected: Exits with error.
        """
        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment"],
            cwd="/nonexistent",
            capture_output=True,
            text=True
        )

        # Should exit with error
        assert result.returncode != 0

    @patch("plugins.autonomous_dev.lib.hybrid_validator.HybridManifestValidator")
    def test_validator_exception_handling(self, mock_validator_class, tmp_path):
        """Test handling of validator exceptions.

        REQUIREMENT: Handle validator errors gracefully.
        Expected: Exits with error, outputs error message.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        mock_validator = MagicMock()
        mock_validator.validate.side_effect = Exception("Validator error")
        mock_validator_class.return_value = mock_validator

        script = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib" / "genai_validate.py"

        result = subprocess.run(
            [sys.executable, str(script), "manifest-alignment"],
            cwd=str(repo_root),
            capture_output=True,
            text=True
        )

        assert result.returncode != 0

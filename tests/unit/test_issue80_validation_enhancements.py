"""
TDD Tests for Issue #80 - Enhanced Installation Validation (Phase 3)

Tests the enhanced InstallationValidator that ensures >=99.5% coverage
and detects specific missing files.

Current State (RED PHASE):
- Enhanced validation methods don't exist yet
- 99.5% coverage target check doesn't exist
- All tests should FAIL

Test Coverage:
- 99.5% coverage validation
- Detailed missing file categorization
- Installation manifest validation
- Health check integration
- Status code generation

GitHub Issue: #80
Agent: test-master
Date: 2025-11-19
"""

import pytest
from pathlib import Path
import json


class TestEnhancedValidation:
    """Test enhanced validation for 99.5% coverage target."""

    def test_validates_99_5_percent_coverage_threshold(self, tmp_path):
        """Test that validation enforces 99.5% coverage threshold.

        99.5% = 200 of 201 files (allows 1 missing file).

        Current: FAILS - Enhanced threshold validation doesn't exist
        """
        # Arrange: Create 201 files in source
        source = tmp_path / "source"
        source.mkdir()

        for i in range(201):
            (source / f"file{i}.txt").touch()

        # Destination: 200 files (99.5%)
        dest = tmp_path / "dest"
        dest.mkdir()

        for i in range(200):
            (dest / f"file{i}.txt").touch()

        # Act: Validate with threshold
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate(threshold=99.5)

        # Assert: Passes threshold
        assert result.status == "complete"  # 99.5% counts as complete
        assert result.coverage >= 99.5

    def test_fails_validation_below_99_5_percent(self, tmp_path):
        """Test that validation fails below 99.5% coverage.

        Current: FAILS - Enhanced threshold validation doesn't exist
        """
        # Arrange: Create 201 files in source
        source = tmp_path / "source"
        source.mkdir()

        for i in range(201):
            (source / f"file{i}.txt").touch()

        # Destination: 198 files (98.5%)
        dest = tmp_path / "dest"
        dest.mkdir()

        for i in range(198):
            (dest / f"file{i}.txt").touch()

        # Act: Validate with threshold
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate(threshold=99.5)

        # Assert: Fails threshold
        assert result.status == "incomplete"
        assert result.coverage < 99.5
        assert result.missing_files == 3

    def test_categorizes_missing_files_by_directory(self, tmp_path):
        """Test that validation categorizes missing files by directory.

        Report should show:
        - scripts/: 2 missing
        - lib/: 5 missing
        - agents/: 1 missing

        Current: FAILS - Enhanced categorization doesn't exist
        """
        # Arrange: Create structured files
        source = tmp_path / "source"
        source.mkdir()

        # Scripts: 10 total
        (source / "scripts").mkdir()
        for i in range(10):
            (source / "scripts" / f"script{i}.py").touch()

        # Lib: 20 total
        (source / "lib").mkdir()
        for i in range(20):
            (source / "lib" / f"lib{i}.py").touch()

        # Agents: 15 total
        (source / "agents").mkdir()
        for i in range(15):
            (source / "agents" / f"agent{i}.md").touch()

        # Destination: Missing files from each category
        dest = tmp_path / "dest"
        dest.mkdir()

        # Scripts: 8 of 10 (2 missing)
        (dest / "scripts").mkdir()
        for i in range(8):
            (dest / "scripts" / f"script{i}.py").touch()

        # Lib: 15 of 20 (5 missing)
        (dest / "lib").mkdir()
        for i in range(15):
            (dest / "lib" / f"lib{i}.py").touch()

        # Agents: 14 of 15 (1 missing)
        (dest / "agents").mkdir()
        for i in range(14):
            (dest / "agents" / f"agent{i}.md").touch()

        # Act: Validate and get categorization
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate()

        # Assert: Categorized missing files
        assert hasattr(result, "missing_by_category")
        assert result.missing_by_category["scripts"] == 2
        assert result.missing_by_category["lib"] == 5
        assert result.missing_by_category["agents"] == 1

    def test_identifies_critical_missing_files(self, tmp_path):
        """Test that validation identifies critical missing files.

        Critical files:
        - scripts/setup.py
        - lib/security_utils.py
        - lib/install_orchestrator.py

        Current: FAILS - Critical file detection doesn't exist
        """
        # Arrange: Create files
        source = tmp_path / "source"
        source.mkdir()

        # Critical files
        (source / "scripts").mkdir()
        (source / "scripts" / "setup.py").touch()

        (source / "lib").mkdir()
        (source / "lib" / "security_utils.py").touch()
        (source / "lib" / "install_orchestrator.py").touch()

        # Non-critical files
        (source / "commands").mkdir()
        (source / "commands" / "test.md").touch()

        # Destination: Missing critical files
        dest = tmp_path / "dest"
        dest.mkdir()

        # Only non-critical files copied
        (dest / "commands").mkdir()
        (dest / "commands" / "test.md").touch()

        # Act: Validate
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate()

        # Assert: Critical files flagged
        assert hasattr(result, "critical_missing")
        assert len(result.critical_missing) == 3
        assert "scripts/setup.py" in result.critical_missing
        assert "lib/security_utils.py" in result.critical_missing
        assert "lib/install_orchestrator.py" in result.critical_missing

    def test_validates_against_manifest_201_files(self, tmp_path):
        """Test that validation uses manifest to verify 201+ files.

        Current: FAILS - Manifest validation doesn't exist
        """
        # Arrange: Create manifest with 201 files
        manifest = {
            "version": "1.0",
            "total_files": 201,
            "files": []
        }

        for i in range(201):
            manifest["files"].append({
                "path": f"file{i}.txt",
                "size": 100
            })

        manifest_path = tmp_path / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        # Destination: Only 152 files (current state)
        dest = tmp_path / "dest"
        dest.mkdir()

        for i in range(152):
            (dest / f"file{i}.txt").write_text("x" * 100)

        # Act: Validate against manifest
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator.from_manifest(manifest_path, dest)
        result = validator.validate()

        # Assert: Detects 49 missing files
        assert result.missing_files == 49
        assert result.total_expected == 201
        assert result.total_found == 152
        assert result.coverage == pytest.approx(75.62, abs=0.01)

    def test_generates_actionable_report(self, tmp_path, capsys):
        """Test that validation generates actionable report.

        Report format:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        📊 Installation Validation Report
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Status: ❌ Incomplete (75.62%)
        Target: 99.5% coverage

        Missing Files (49):
        ├─ scripts/ (9 files)
        │  ├─ setup.py
        │  ├─ validate.py
        │  └─ ...
        ├─ lib/ (23 files)
        └─ agents/ (3 files)

        Action Required:
        Run: ./install.sh --fix

        Current: FAILS - Enhanced report generation doesn't exist
        """
        # Arrange: Create incomplete installation
        source = tmp_path / "source"
        source.mkdir()

        (source / "scripts").mkdir()
        (source / "scripts" / "setup.py").touch()
        (source / "scripts" / "validate.py").touch()

        (source / "lib").mkdir()
        (source / "lib" / "utils.py").touch()

        dest = tmp_path / "dest"
        dest.mkdir()

        # Only lib/ copied
        (dest / "lib").mkdir()
        (dest / "lib" / "utils.py").touch()

        # Act: Generate report
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate()
        report = validator.generate_report(result)

        print(report)

        # Assert: Report is actionable
        captured = capsys.readouterr()
        output = captured.out

        assert "Installation Validation Report" in output
        assert "Incomplete" in output or "incomplete" in output.lower()
        assert "Missing Files" in output or "missing" in output.lower()
        assert "scripts/" in output
        assert result.coverage < 100.0


class TestValidationStatusCodes:
    """Test validation status code generation for scripts."""

    def test_returns_status_0_for_complete_installation(self, tmp_path):
        """Test that validation returns status code 0 for 100% coverage.

        Current: FAILS - Status code method doesn't exist
        """
        # Arrange: Perfect installation
        source = tmp_path / "source"
        source.mkdir()

        for i in range(10):
            (source / f"file{i}.txt").touch()

        dest = tmp_path / "dest"
        dest.mkdir()

        for i in range(10):
            (dest / f"file{i}.txt").touch()

        # Act: Get status code
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        status = validator.get_status_code()

        # Assert: Success status
        assert status == 0

    def test_returns_status_0_for_99_5_percent(self, tmp_path):
        """Test that validation returns status code 0 for >=99.5% coverage.

        Current: FAILS - Status code method doesn't exist
        """
        # Arrange: 99.5% installation (200 of 201)
        source = tmp_path / "source"
        source.mkdir()

        for i in range(201):
            (source / f"file{i}.txt").touch()

        dest = tmp_path / "dest"
        dest.mkdir()

        for i in range(200):
            (dest / f"file{i}.txt").touch()

        # Act: Get status code with threshold
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        status = validator.get_status_code(threshold=99.5)

        # Assert: Success status (meets threshold)
        assert status == 0

    def test_returns_status_1_for_incomplete_installation(self, tmp_path):
        """Test that validation returns status code 1 for <99.5% coverage.

        Current: FAILS - Status code method doesn't exist
        """
        # Arrange: Incomplete installation (76%)
        source = tmp_path / "source"
        source.mkdir()

        for i in range(100):
            (source / f"file{i}.txt").touch()

        dest = tmp_path / "dest"
        dest.mkdir()

        for i in range(76):
            (dest / f"file{i}.txt").touch()

        # Act: Get status code
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        status = validator.get_status_code()

        # Assert: Failure status
        assert status == 1

    def test_returns_status_2_for_validation_error(self, tmp_path):
        """Test that validation returns status code 2 for validation errors.

        Current: FAILS - Status code method doesn't exist
        """
        # Arrange: Missing source directory
        source = tmp_path / "nonexistent"
        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Get status code (should handle error)
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator, ValidationError

        try:
            validator = InstallationValidator(source, dest)
            status = validator.get_status_code()

            # Assert: Error status
            assert status == 2
        except ValidationError:
            # Expected error - status code 2 scenario
            pass


class TestHealthCheckIntegration:
    """Test /health-check integration with enhanced validation."""

    def test_health_check_uses_enhanced_validation(self, tmp_path):
        """Test that /health-check uses enhanced validation (99.5% threshold).

        Current: FAILS - Health check integration doesn't exist
        """
        # Arrange: Installation at 99.6% (passes threshold)
        source = tmp_path / "source"
        source.mkdir()

        for i in range(1000):
            (source / f"file{i}.txt").touch()

        dest = tmp_path / "dest"
        dest.mkdir()

        for i in range(996):  # 99.6%
            (dest / f"file{i}.txt").touch()

        # Act: Run health check
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate(threshold=99.5)

        # Assert: Passes health check
        assert result.status == "complete"
        assert result.coverage >= 99.5

    def test_health_check_reports_missing_file_categories(self, tmp_path):
        """Test that health check reports missing files by category.

        Current: FAILS - Category reporting doesn't exist
        """
        # Arrange: Missing files from multiple categories
        source = tmp_path / "source"
        source.mkdir()

        (source / "scripts").mkdir()
        for i in range(5):
            (source / "scripts" / f"script{i}.py").touch()

        (source / "lib").mkdir()
        for i in range(10):
            (source / "lib" / f"lib{i}.py").touch()

        dest = tmp_path / "dest"
        dest.mkdir()

        # Scripts: 3 of 5
        (dest / "scripts").mkdir()
        for i in range(3):
            (dest / "scripts" / f"script{i}.py").touch()

        # Lib: 7 of 10
        (dest / "lib").mkdir()
        for i in range(7):
            (dest / "lib" / f"lib{i}.py").touch()

        # Act: Validate
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate()

        # Assert: Categories reported
        assert hasattr(result, "missing_by_category")
        assert result.missing_by_category["scripts"] == 2
        assert result.missing_by_category["lib"] == 3


class TestValidationEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_zero_files_in_source(self, tmp_path):
        """Test that validation handles empty source gracefully.

        Current: FAILS - Enhanced validation doesn't exist
        """
        # Arrange: Empty source
        source = tmp_path / "source"
        source.mkdir()

        dest = tmp_path / "dest"
        dest.mkdir()

        # Act: Validate
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate()

        # Assert: Reports complete (0/0 = 100%)
        assert result.status == "complete"
        assert result.coverage == 100.0
        assert result.total_expected == 0

    def test_handles_extra_files_in_destination(self, tmp_path):
        """Test that validation handles extra files in destination.

        Extra files should be reported but not fail validation.

        Current: FAILS - Enhanced validation doesn't exist
        """
        # Arrange: Destination has extra files
        source = tmp_path / "source"
        source.mkdir()

        (source / "expected.txt").touch()

        dest = tmp_path / "dest"
        dest.mkdir()

        (dest / "expected.txt").touch()
        (dest / "extra1.txt").touch()
        (dest / "extra2.txt").touch()

        # Act: Validate
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate()

        # Assert: Reports extra files
        assert result.status == "complete"  # All expected files present
        assert result.coverage == 100.0
        assert result.extra_files == 2

        assert "extra1.txt" in result.extra_file_list
        assert "extra2.txt" in result.extra_file_list

    def test_validates_across_multiple_file_types(self, tmp_path):
        """Test that validation works across multiple file types.

        Current: FAILS - Enhanced validation doesn't exist
        """
        # Arrange: Mixed file types
        source = tmp_path / "source"
        source.mkdir()

        (source / "doc.md").write_text("# Doc")
        (source / "script.py").write_text("#!/usr/bin/env python3")
        (source / "data.json").write_text('{"key": "value"}')
        (source / "config.yaml").write_text("key: value")
        (source / "README").write_text("Readme")

        dest = tmp_path / "dest"
        dest.mkdir()

        # Copy all files
        for file in source.iterdir():
            (dest / file.name).write_bytes(file.read_bytes())

        # Act: Validate
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate()

        # Assert: All types validated
        assert result.status == "complete"
        assert result.coverage == 100.0
        assert result.total_expected == 5

    def test_validates_file_sizes_match(self, tmp_path):
        """Test that validation checks file sizes match.

        Current: FAILS - Size validation doesn't exist
        """
        # Arrange: Files with different sizes
        source = tmp_path / "source"
        source.mkdir()

        (source / "correct.txt").write_text("x" * 100)
        (source / "wrong.txt").write_text("x" * 200)

        dest = tmp_path / "dest"
        dest.mkdir()

        (dest / "correct.txt").write_text("x" * 100)
        (dest / "wrong.txt").write_text("x" * 150)  # Wrong size

        # Act: Validate with size checking
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate(check_sizes=True)

        # Assert: Size mismatch detected
        assert hasattr(result, "sizes_match")
        assert result.sizes_match is False
        assert "wrong.txt" in result.size_errors

    def test_validates_symlink_exclusion(self, tmp_path):
        """Test that validation doesn't count symlinks in destination.

        Current: FAILS - Enhanced validation doesn't exist
        """
        # Arrange: Source with regular file
        source = tmp_path / "source"
        source.mkdir()

        (source / "file.txt").write_text("content")

        # Destination with file + symlink
        dest = tmp_path / "dest"
        dest.mkdir()

        (dest / "file.txt").write_text("content")

        symlink = dest / "link.txt"
        try:
            symlink.symlink_to(dest / "file.txt")
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        # Act: Validate
        from plugins.autonomous_dev.lib.installation_validator import InstallationValidator

        validator = InstallationValidator(source, dest)
        result = validator.validate()

        # Assert: Only real file counted
        assert result.total_found == 1
        assert result.extra_files == 0  # Symlink excluded

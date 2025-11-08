#!/usr/bin/env python3
"""
TDD Tests for Version Detector (FAILING - Red Phase)

This module contains FAILING tests for version_detector.py which will detect
version differences between marketplace plugin and local project.

Requirements:
1. Parse version strings from plugin.json files (marketplace and project)
2. Compare versions to detect upgrades, downgrades, or equal versions
3. Handle missing/corrupted plugin.json gracefully
4. Security: Block path traversal attempts
5. Return detailed comparison results for user messaging

Test Coverage Target: 100% of version detection logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe version detection requirements
- Tests should FAIL until version_detector.py is implemented
- Each test validates ONE version detection requirement

Author: test-master agent
Date: 2025-11-08
Issue: GitHub #50 - Fix Marketplace Update UX
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until version_detector.py is created
from plugins.autonomous_dev.lib.version_detector import (
    VersionDetector,
    VersionComparison,
    VersionParseError,
    detect_version_mismatch,
)


class TestVersionParsingValid:
    """Test parsing valid version strings from plugin.json files."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with plugin.json."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()
        return project_root

    def test_parse_valid_semantic_version(self, temp_project):
        """Test parsing valid semantic version (MAJOR.MINOR.PATCH).

        REQUIREMENT: Version detector must parse standard semver format.
        Expected: "3.7.0" parsed correctly, components accessible.
        """
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"
        }))

        detector = VersionDetector(project_root=temp_project)
        version = detector.parse_project_version()

        assert version is not None
        assert version.major == 3
        assert version.minor == 7
        assert version.patch == 0
        assert str(version) == "3.7.0"

    def test_parse_version_with_prerelease_tag(self, temp_project):
        """Test parsing version with pre-release tag (e.g., 3.7.0-beta.1).

        REQUIREMENT: Support pre-release versions for early testing.
        Expected: "3.7.0-beta.1" parsed with prerelease metadata.
        """
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0-beta.1"
        }))

        detector = VersionDetector(project_root=temp_project)
        version = detector.parse_project_version()

        assert version.major == 3
        assert version.minor == 7
        assert version.patch == 0
        assert version.prerelease == "beta.1"

    def test_parse_marketplace_version(self, temp_project):
        """Test parsing marketplace plugin version from installed_plugins.json.

        REQUIREMENT: Detect marketplace version for comparison.
        Expected: Marketplace version parsed from ~/.claude/plugins/installed_plugins.json.
        """
        # Mock home directory for marketplace plugins
        marketplace_dir = temp_project / "mock_home" / ".claude" / "plugins"
        marketplace_dir.mkdir(parents=True)
        installed_plugins = marketplace_dir / "installed_plugins.json"
        installed_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace"
            }
        }))

        detector = VersionDetector(
            project_root=temp_project,
            marketplace_plugins_file=installed_plugins
        )
        version = detector.parse_marketplace_version("autonomous-dev")

        assert version is not None
        assert version.major == 3
        assert version.minor == 8
        assert version.patch == 0

    @pytest.mark.parametrize("version_string,expected_major,expected_minor,expected_patch", [
        ("1.0.0", 1, 0, 0),
        ("2.5.3", 2, 5, 3),
        ("10.20.30", 10, 20, 30),
        ("0.0.1", 0, 0, 1),
    ])
    def test_parse_various_valid_versions(self, temp_project, version_string, expected_major, expected_minor, expected_patch):
        """Test parsing various valid semantic versions.

        REQUIREMENT: Support all valid semver formats.
        Expected: All versions parsed correctly with correct components.
        """
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": version_string
        }))

        detector = VersionDetector(project_root=temp_project)
        version = detector.parse_project_version()

        assert version.major == expected_major
        assert version.minor == expected_minor
        assert version.patch == expected_patch


class TestVersionParsingInvalid:
    """Test handling invalid version strings gracefully."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()
        return project_root

    @pytest.mark.parametrize("invalid_version", [
        "invalid",
        "v3.7.0",  # Prefix not allowed
        "3.7",     # Missing patch
        "3",       # Missing minor and patch
        "abc.def.ghi",  # Non-numeric
        "3.7.0.1",      # Too many components
        "",             # Empty string
    ])
    def test_parse_invalid_version_raises_error(self, temp_project, invalid_version):
        """Test that invalid version strings raise VersionParseError.

        REQUIREMENT: Fail fast on invalid versions with clear error.
        Expected: VersionParseError with descriptive message.
        """
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": invalid_version
        }))

        detector = VersionDetector(project_root=temp_project)

        with pytest.raises(VersionParseError) as exc_info:
            detector.parse_project_version()

        # Error message should include the invalid version
        assert invalid_version in str(exc_info.value) or "version" in str(exc_info.value).lower()

    def test_missing_plugin_json_returns_none(self, temp_project):
        """Test that missing plugin.json returns None instead of error.

        REQUIREMENT: Handle marketplace not installed gracefully.
        Expected: parse_project_version() returns None, no exception.
        """
        # No plugin.json file created

        detector = VersionDetector(project_root=temp_project)
        version = detector.parse_project_version()

        assert version is None

    def test_corrupted_plugin_json_raises_error(self, temp_project):
        """Test that corrupted JSON raises clear error.

        REQUIREMENT: Detect corrupted plugin.json and fail safely.
        Expected: VersionParseError indicating JSON corruption.
        """
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text("{ corrupted json content")

        detector = VersionDetector(project_root=temp_project)

        with pytest.raises(VersionParseError) as exc_info:
            detector.parse_project_version()

        error_msg = str(exc_info.value).lower()
        assert "json" in error_msg or "parse" in error_msg or "corrupt" in error_msg

    def test_missing_version_field_raises_error(self, temp_project):
        """Test that plugin.json without 'version' field raises error.

        REQUIREMENT: Validate plugin.json structure.
        Expected: VersionParseError indicating missing version field.
        """
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev"
            # Missing "version" field
        }))

        detector = VersionDetector(project_root=temp_project)

        with pytest.raises(VersionParseError) as exc_info:
            detector.parse_project_version()

        assert "version" in str(exc_info.value).lower()


class TestVersionComparison:
    """Test comparing versions to detect upgrades/downgrades."""

    @pytest.fixture
    def detector(self, tmp_path):
        """Create version detector for testing."""
        return VersionDetector(project_root=tmp_path)

    def test_compare_newer_marketplace_version(self, detector):
        """Test detecting marketplace version is newer (upgrade available).

        REQUIREMENT: Detect when marketplace has newer version.
        Expected: Comparison indicates UPGRADE_AVAILABLE.
        """
        project_version = detector._parse_version_string("3.7.0")
        marketplace_version = detector._parse_version_string("3.8.0")

        comparison = detector.compare_versions(project_version, marketplace_version)

        assert comparison.status == VersionComparison.UPGRADE_AVAILABLE
        assert comparison.project_version == "3.7.0"
        assert comparison.marketplace_version == "3.8.0"
        assert comparison.is_upgrade is True

    def test_compare_older_marketplace_version(self, detector):
        """Test detecting project version is newer (downgrade would occur).

        REQUIREMENT: Detect when project is ahead of marketplace.
        Expected: Comparison indicates DOWNGRADE_RISK.
        """
        project_version = detector._parse_version_string("3.9.0")
        marketplace_version = detector._parse_version_string("3.8.0")

        comparison = detector.compare_versions(project_version, marketplace_version)

        assert comparison.status == VersionComparison.DOWNGRADE_RISK
        assert comparison.is_downgrade is True

    def test_compare_equal_versions(self, detector):
        """Test detecting equal versions (up to date).

        REQUIREMENT: Detect when versions match.
        Expected: Comparison indicates UP_TO_DATE.
        """
        project_version = detector._parse_version_string("3.7.0")
        marketplace_version = detector._parse_version_string("3.7.0")

        comparison = detector.compare_versions(project_version, marketplace_version)

        assert comparison.status == VersionComparison.UP_TO_DATE
        assert comparison.is_upgrade is False
        assert comparison.is_downgrade is False

    @pytest.mark.parametrize("project_ver,marketplace_ver,expected_status", [
        ("3.7.0", "4.0.0", VersionComparison.UPGRADE_AVAILABLE),  # Major upgrade
        ("3.7.0", "3.8.0", VersionComparison.UPGRADE_AVAILABLE),  # Minor upgrade
        ("3.7.0", "3.7.1", VersionComparison.UPGRADE_AVAILABLE),  # Patch upgrade
        ("4.0.0", "3.7.0", VersionComparison.DOWNGRADE_RISK),     # Major downgrade
        ("3.8.0", "3.7.0", VersionComparison.DOWNGRADE_RISK),     # Minor downgrade
        ("3.7.1", "3.7.0", VersionComparison.DOWNGRADE_RISK),     # Patch downgrade
    ])
    def test_compare_various_version_combinations(self, detector, project_ver, marketplace_ver, expected_status):
        """Test various version comparison scenarios.

        REQUIREMENT: Correctly identify all upgrade/downgrade cases.
        Expected: Status matches expected for all semver component changes.
        """
        project_version = detector._parse_version_string(project_ver)
        marketplace_version = detector._parse_version_string(marketplace_ver)

        comparison = detector.compare_versions(project_version, marketplace_version)

        assert comparison.status == expected_status


class TestVersionDetectionIntegration:
    """Test end-to-end version detection workflow."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create full test environment with project and marketplace."""
        # Project setup
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

        # Marketplace setup
        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        return {
            "project_root": project_root,
            "marketplace_dir": marketplace_dir
        }

    def test_detect_version_mismatch_upgrade_available(self, temp_environment):
        """Test detect_version_mismatch() function for upgrade scenario.

        REQUIREMENT: High-level function to detect version differences.
        Expected: Returns VersionComparison indicating upgrade available.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup project version
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"
        }))

        # Setup marketplace version
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace"
            }
        }))

        result = detect_version_mismatch(
            project_root=project_root,
            marketplace_plugins_file=marketplace_plugins
        )

        assert result.status == VersionComparison.UPGRADE_AVAILABLE
        assert result.project_version == "3.7.0"
        assert result.marketplace_version == "3.8.0"

    def test_detect_marketplace_not_installed(self, temp_environment):
        """Test detection when marketplace plugin not installed.

        REQUIREMENT: Handle marketplace not installed gracefully.
        Expected: Returns comparison with MARKETPLACE_NOT_INSTALLED status.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup project version
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"
        }))

        # No marketplace plugins file

        result = detect_version_mismatch(
            project_root=project_root,
            marketplace_plugins_file=marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        )

        assert result.status == VersionComparison.MARKETPLACE_NOT_INSTALLED

    def test_detect_project_not_synced(self, temp_environment):
        """Test detection when project has no plugin.json.

        REQUIREMENT: Handle project not synced gracefully.
        Expected: Returns comparison with PROJECT_NOT_SYNCED status.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # No project plugin.json

        # Setup marketplace version
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace"
            }
        }))

        result = detect_version_mismatch(
            project_root=project_root,
            marketplace_plugins_file=marketplace_plugins
        )

        assert result.status == VersionComparison.PROJECT_NOT_SYNCED


class TestSecurityValidation:
    """Test security controls prevent path traversal attacks."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_path_traversal_via_project_root_blocked(self, temp_project):
        """Test that path traversal in project_root parameter is blocked.

        SECURITY: Prevent attackers from reading /etc/passwd via project_root.
        Expected: ValueError or SecurityError raised.
        """
        malicious_root = temp_project / ".." / ".." / "etc"

        with pytest.raises((ValueError, PermissionError)) as exc_info:
            detector = VersionDetector(project_root=malicious_root)
            detector.parse_project_version()

        error_msg = str(exc_info.value).lower()
        assert "path" in error_msg or "security" in error_msg or "invalid" in error_msg

    def test_symlink_attack_via_plugin_json_blocked(self, temp_project):
        """Test that symlink to outside project is rejected.

        SECURITY: Prevent symlink-based path traversal.
        Expected: ValueError or SecurityError before following symlink.
        """
        # Create target outside project
        outside_target = temp_project.parent / "evil.json"
        outside_target.write_text(json.dumps({
            "name": "malware",
            "version": "999.0.0"
        }))

        # Create symlink inside project pointing outside
        plugin_dir = temp_project / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        symlink_path = plugin_dir / "plugin.json"

        if hasattr(os, 'symlink'):
            try:
                symlink_path.symlink_to(outside_target)

                detector = VersionDetector(project_root=temp_project)

                with pytest.raises((ValueError, PermissionError)) as exc_info:
                    detector.parse_project_version()

                error_msg = str(exc_info.value).lower()
                assert "symlink" in error_msg or "security" in error_msg or "path" in error_msg
            except OSError:
                pytest.skip("Symlinks not supported on this system")
        else:
            pytest.skip("Symlinks not available on Windows")

    def test_absolute_path_outside_whitelist_blocked(self, temp_project):
        """Test that absolute paths outside allowed directories are blocked.

        SECURITY: Only allow paths within project root.
        Expected: ValueError for /etc/passwd, /tmp/evil, etc.
        """
        malicious_paths = [
            Path("/etc/passwd"),
            Path("/tmp/evil/plugin.json"),
            Path("/var/log/malicious.json"),
        ]

        for malicious_path in malicious_paths:
            with pytest.raises((ValueError, PermissionError, FileNotFoundError)):
                detector = VersionDetector(project_root=temp_project)
                # Attempt to use malicious path
                detector._read_json_file(malicious_path)


class TestVersionComparisonDataClass:
    """Test VersionComparison result object."""

    def test_version_comparison_attributes(self):
        """Test VersionComparison has expected attributes.

        REQUIREMENT: Result object must capture comparison details.
        Expected: Has status, project_version, marketplace_version, etc.
        """
        comparison = VersionComparison(
            status=VersionComparison.UPGRADE_AVAILABLE,
            project_version="3.7.0",
            marketplace_version="3.8.0"
        )

        assert comparison.status == VersionComparison.UPGRADE_AVAILABLE
        assert comparison.project_version == "3.7.0"
        assert comparison.marketplace_version == "3.8.0"
        assert comparison.is_upgrade is True
        assert comparison.is_downgrade is False

    def test_version_comparison_message_generation(self):
        """Test VersionComparison can generate user-friendly message.

        REQUIREMENT: Provide clear messaging for UX improvements.
        Expected: message property returns descriptive text.
        """
        comparison = VersionComparison(
            status=VersionComparison.UPGRADE_AVAILABLE,
            project_version="3.7.0",
            marketplace_version="3.8.0"
        )

        message = comparison.message

        assert "upgrade" in message.lower() or "update" in message.lower()
        assert "3.7.0" in message
        assert "3.8.0" in message

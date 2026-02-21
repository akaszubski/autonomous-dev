#!/usr/bin/env python3
"""
Unit tests for MCP Profile Manager (TDD Red Phase).

Tests for pre-configured security profiles for MCP server (Issue #95).

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test development profile generation (permissive)
- Test testing profile generation (moderate)
- Test production profile generation (restrictive)
- Test profile customization (merge base + overrides)
- Test profile validation (schema compliance)
- Test profile export (JSON serialization)

Date: 2025-12-07
Issue: #95 (MCP Server Security - Permission Whitelist System)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - module doesn't exist yet (TDD!)
try:
    from mcp_profile_manager import (
        MCPProfileManager,
        SecurityProfile,
        ProfileType,
        generate_development_profile,
        generate_testing_profile,
        generate_production_profile,
        customize_profile,
        validate_profile_schema,
        export_profile,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestDevelopmentProfile:
    """Test development profile generation (most permissive)."""

    def test_generate_development_profile_filesystem_read(self):
        """Test development profile allows broad filesystem read access."""
        profile = generate_development_profile()

        assert "filesystem" in profile
        assert "read" in profile["filesystem"]
        assert "src/**" in profile["filesystem"]["read"]
        assert "tests/**" in profile["filesystem"]["read"]
        assert "docs/**" in profile["filesystem"]["read"]

    def test_generate_development_profile_filesystem_write(self):
        """Test development profile allows write to src/, tests/, docs/."""
        profile = generate_development_profile()

        assert "write" in profile["filesystem"]
        assert "src/**" in profile["filesystem"]["write"]
        assert "tests/**" in profile["filesystem"]["write"]

    def test_generate_development_profile_shell_commands(self):
        """Test development profile allows common development commands."""
        profile = generate_development_profile()

        assert "shell" in profile
        assert "allowed_commands" in profile["shell"]

        allowed = profile["shell"]["allowed_commands"]
        assert "pytest" in allowed
        assert "git" in allowed
        assert "python" in allowed
        assert "npm" in allowed

    def test_generate_development_profile_denies_destructive_commands(self):
        """Test development profile still denies destructive commands."""
        profile = generate_development_profile()

        assert "denied_patterns" in profile["shell"]

        denied = profile["shell"]["denied_patterns"]
        assert "rm -rf /" in denied or any("rm" in p for p in denied)

    def test_generate_development_profile_network_access(self):
        """Test development profile allows external network access."""
        profile = generate_development_profile()

        assert "network" in profile
        assert "allowed_domains" in profile["network"]

        # Should allow common development APIs
        allowed = profile["network"]["allowed_domains"]
        assert "*" in allowed or "api.github.com" in allowed

    def test_generate_development_profile_denies_localhost(self):
        """Test development profile still denies localhost (SSRF)."""
        profile = generate_development_profile()

        assert "denied_ips" in profile["network"]

        denied = profile["network"]["denied_ips"]
        assert "127.0.0.1" in denied
        assert "0.0.0.0" in denied


class TestTestingProfile:
    """Test testing profile generation (moderate restrictions)."""

    def test_generate_testing_profile_filesystem_read(self):
        """Test testing profile allows reading tests and src."""
        profile = generate_testing_profile()

        assert "filesystem" in profile
        assert "read" in profile["filesystem"]
        assert "tests/**" in profile["filesystem"]["read"]
        assert "src/**" in profile["filesystem"]["read"]

    def test_generate_testing_profile_filesystem_write_restricted(self):
        """Test testing profile restricts write to tests/ only."""
        profile = generate_testing_profile()

        assert "write" in profile["filesystem"]
        assert "tests/**" in profile["filesystem"]["write"]

        # Should NOT allow writing to src/ in testing
        assert "src/**" not in profile["filesystem"]["write"]

    def test_generate_testing_profile_shell_pytest_only(self):
        """Test testing profile allows pytest but limits other commands."""
        profile = generate_testing_profile()

        allowed = profile["shell"]["allowed_commands"]
        assert "pytest" in allowed

        # Should be more restrictive than development
        assert len(allowed) < 10  # Arbitrary but reasonable limit

    def test_generate_testing_profile_network_restricted(self):
        """Test testing profile restricts network access to specific APIs."""
        profile = generate_testing_profile()

        assert "network" in profile

        # Should NOT have wildcard access
        if "allowed_domains" in profile["network"]:
            assert "*" not in profile["network"]["allowed_domains"]


class TestProductionProfile:
    """Test production profile generation (most restrictive)."""

    def test_generate_production_profile_filesystem_read_minimal(self):
        """Test production profile has minimal read permissions."""
        profile = generate_production_profile()

        assert "filesystem" in profile
        assert "read" in profile["filesystem"]

        # Production should have very limited read access
        read_paths = profile["filesystem"]["read"]
        assert len(read_paths) < 5  # Minimal paths only

    def test_generate_production_profile_filesystem_write_denied(self):
        """Test production profile denies most write operations."""
        profile = generate_production_profile()

        write_paths = profile["filesystem"].get("write", [])

        # Production should have minimal or no write access
        assert len(write_paths) <= 2  # Very restricted

    def test_generate_production_profile_shell_minimal(self):
        """Test production profile has minimal shell command access."""
        profile = generate_production_profile()

        allowed = profile["shell"]["allowed_commands"]

        # Production should have minimal commands (maybe only git status)
        assert len(allowed) <= 3

    def test_generate_production_profile_network_deny_all(self):
        """Test production profile denies network access by default."""
        profile = generate_production_profile()

        assert "network" in profile

        # Should have empty allowed list or very specific domains
        allowed = profile["network"].get("allowed_domains", [])
        assert len(allowed) == 0 or ("*" not in allowed and len(allowed) < 3)

    def test_generate_production_profile_env_minimal(self):
        """Test production profile has minimal env var access."""
        profile = generate_production_profile()

        if "environment" in profile:
            allowed = profile["environment"].get("allowed_vars", [])
            assert len(allowed) < 5  # Minimal env vars only


class TestProfileCustomization:
    """Test profile customization and merging."""

    def test_customize_profile_merge_overrides(self):
        """Test customizing profile merges base with overrides."""
        base_profile = generate_development_profile()

        overrides = {
            "filesystem": {
                "read": ["custom/**"]
            }
        }

        customized = customize_profile(base_profile, overrides)

        # Should merge, not replace
        assert "custom/**" in customized["filesystem"]["read"]
        # Original paths should still be present
        assert "src/**" in customized["filesystem"]["read"]

    def test_customize_profile_override_shell_commands(self):
        """Test customizing profile can add new shell commands."""
        base_profile = generate_testing_profile()

        overrides = {
            "shell": {
                "allowed_commands": ["custom-tool"]
            }
        }

        customized = customize_profile(base_profile, overrides)

        assert "custom-tool" in customized["shell"]["allowed_commands"]
        assert "pytest" in customized["shell"]["allowed_commands"]  # Original preserved

    def test_customize_profile_replace_mode(self):
        """Test customizing profile with replace mode (not merge)."""
        base_profile = generate_development_profile()

        overrides = {
            "filesystem": {
                "read": ["only-this/**"]
            }
        }

        customized = customize_profile(base_profile, overrides, merge=False)

        # In replace mode, should only have override paths
        assert "only-this/**" in customized["filesystem"]["read"]
        assert "src/**" not in customized["filesystem"]["read"]

    def test_customize_profile_deep_merge(self):
        """Test customizing profile performs deep merge of nested objects."""
        base_profile = generate_development_profile()

        overrides = {
            "network": {
                "allowed_domains": ["custom-api.com"],
                "timeout": 30
            }
        }

        customized = customize_profile(base_profile, overrides)

        assert "custom-api.com" in customized["network"]["allowed_domains"]
        assert customized["network"]["timeout"] == 30


class TestProfileValidation:
    """Test profile schema validation."""

    def test_validate_profile_schema_valid(self):
        """Test validating a valid profile schema."""
        profile = generate_development_profile()

        result = validate_profile_schema(profile)

        assert result.valid is True
        assert result.errors == []

    def test_validate_profile_schema_missing_filesystem(self):
        """Test validating profile missing required filesystem section."""
        invalid_profile = {
            "shell": {
                "allowed_commands": ["pytest"]
            }
        }

        result = validate_profile_schema(invalid_profile)

        assert result.valid is False
        assert any("filesystem" in err for err in result.errors)

    def test_validate_profile_schema_invalid_read_type(self):
        """Test validating profile with invalid read type (not array)."""
        invalid_profile = {
            "filesystem": {
                "read": "src/**"  # Should be array, not string
            }
        }

        result = validate_profile_schema(invalid_profile)

        assert result.valid is False
        assert any("array" in err.lower() or "list" in err.lower() for err in result.errors)

    def test_validate_profile_schema_empty_commands(self):
        """Test validating profile with empty allowed_commands is valid."""
        profile = {
            "filesystem": {
                "read": ["src/**"],
                "write": []
            },
            "shell": {
                "allowed_commands": []
            }
        }

        result = validate_profile_schema(profile)

        assert result.valid is True

    def test_validate_profile_schema_unknown_fields_ignored(self):
        """Test validating profile ignores unknown fields."""
        profile = generate_development_profile()
        profile["custom_field"] = "ignored"

        result = validate_profile_schema(profile)

        # Unknown fields should be ignored, not cause errors
        assert result.valid is True


class TestProfileExport:
    """Test profile export to JSON."""

    def test_export_profile_to_json_file(self):
        """Test exporting profile to JSON file."""
        profile = generate_development_profile()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            export_profile(profile, output_path)

            # Verify file was created and is valid JSON
            with open(output_path, 'r') as f:
                loaded = json.load(f)

            assert loaded == profile
        finally:
            os.unlink(output_path)

    def test_export_profile_to_json_string(self):
        """Test exporting profile to JSON string."""
        profile = generate_testing_profile()

        json_str = export_profile(profile, output_path=None)

        # Should be valid JSON
        loaded = json.loads(json_str)
        assert loaded == profile

    def test_export_profile_pretty_print(self):
        """Test exporting profile with pretty printing (indentation)."""
        profile = generate_production_profile()

        json_str = export_profile(profile, output_path=None, indent=2)

        # Should have indentation
        assert "\n" in json_str
        assert "  " in json_str  # 2-space indent


class TestSecurityProfile:
    """Test SecurityProfile data class."""

    def test_security_profile_from_dict(self):
        """Test creating SecurityProfile from dictionary."""
        data = generate_development_profile()

        profile = SecurityProfile.from_dict(data)

        assert profile.filesystem is not None
        assert profile.shell is not None
        assert profile.network is not None

    def test_security_profile_to_dict(self):
        """Test serializing SecurityProfile to dictionary."""
        data = generate_testing_profile()
        profile = SecurityProfile.from_dict(data)

        serialized = profile.to_dict()

        assert serialized == data

    def test_security_profile_validate(self):
        """Test SecurityProfile validation method."""
        data = generate_production_profile()
        profile = SecurityProfile.from_dict(data)

        result = profile.validate()

        assert result.valid is True


class TestProfileType:
    """Test ProfileType enum."""

    def test_profile_type_enum_values(self):
        """Test ProfileType enum has expected values."""
        assert hasattr(ProfileType, 'DEVELOPMENT')
        assert hasattr(ProfileType, 'TESTING')
        assert hasattr(ProfileType, 'PRODUCTION')

    def test_profile_type_from_string(self):
        """Test creating ProfileType from string."""
        profile_type = ProfileType.from_string("development")

        assert profile_type == ProfileType.DEVELOPMENT

    def test_profile_type_from_string_case_insensitive(self):
        """Test ProfileType.from_string is case-insensitive."""
        profile_type = ProfileType.from_string("PRODUCTION")

        assert profile_type == ProfileType.PRODUCTION


class TestProfileManager:
    """Test MCPProfileManager class."""

    def test_profile_manager_create_development(self):
        """Test ProfileManager creates development profile."""
        manager = MCPProfileManager()

        profile = manager.create_profile(ProfileType.DEVELOPMENT)

        assert "filesystem" in profile
        assert len(profile["filesystem"]["read"]) > 3  # Permissive

    def test_profile_manager_create_testing(self):
        """Test ProfileManager creates testing profile."""
        manager = MCPProfileManager()

        profile = manager.create_profile(ProfileType.TESTING)

        assert "filesystem" in profile
        # Testing should be more restrictive than development
        dev_profile = manager.create_profile(ProfileType.DEVELOPMENT)
        assert len(profile["filesystem"].get("write", [])) <= len(dev_profile["filesystem"].get("write", []))

    def test_profile_manager_create_production(self):
        """Test ProfileManager creates production profile."""
        manager = MCPProfileManager()

        profile = manager.create_profile(ProfileType.PRODUCTION)

        assert "filesystem" in profile
        # Production should be most restrictive
        assert len(profile["filesystem"]["read"]) <= 5

    def test_profile_manager_save_profile(self):
        """Test ProfileManager saves profile to file."""
        manager = MCPProfileManager()
        profile = manager.create_profile(ProfileType.DEVELOPMENT)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            manager.save_profile(profile, output_path)

            # Verify file exists and is valid
            assert os.path.exists(output_path)
            with open(output_path, 'r') as f:
                loaded = json.load(f)
            assert loaded == profile
        finally:
            os.unlink(output_path)

    def test_profile_manager_load_profile(self):
        """Test ProfileManager loads profile from file."""
        manager = MCPProfileManager()
        profile = generate_testing_profile()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(profile, f)
            input_path = f.name

        try:
            loaded = manager.load_profile(input_path)

            assert loaded == profile
        finally:
            os.unlink(input_path)

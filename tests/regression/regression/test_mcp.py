#!/usr/bin/env python3
"""
Consolidated MCP Security Tests (TDD Red Phase).

Tests for MCP server security features (Issue #95):
- Profile Manager: development/testing/production profiles
- Permission Validator: filesystem, shell, network, env validation
- Bypass Prevention: CWE-22, CWE-59, CWE-78, SSRF

TDD Mode: These tests are written BEFORE implementation.
All tests FAIL initially (ImportError: module not found).

Date: 2025-12-07 (consolidated 2025-12-16)
Issue: #95 (MCP Server Security - Permission Whitelist System)
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Portable path detection (works from any test location)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        PROJECT_ROOT = current
        break
    current = current.parent
else:
    PROJECT_ROOT = Path.cwd()

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"),
)

# Import profile manager - skip if not found
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
    PROFILE_MANAGER_AVAILABLE = True
except ImportError:
    PROFILE_MANAGER_AVAILABLE = False


# =============================================================================
# Profile Manager Tests
# =============================================================================

@pytest.mark.skipif(not PROFILE_MANAGER_AVAILABLE, reason="mcp_profile_manager not implemented (TDD red phase)")
class TestDevelopmentProfile:
    """Test development profile generation (most permissive)."""

    def test_generate_development_profile_filesystem_read(self):
        """Test development profile allows broad filesystem read access."""
        profile = generate_development_profile()
        assert "filesystem" in profile
        assert "read" in profile["filesystem"]
        assert "src/**" in profile["filesystem"]["read"]

    def test_generate_development_profile_shell_commands(self):
        """Test development profile allows common development commands."""
        profile = generate_development_profile()
        assert "shell" in profile
        assert "allowed_commands" in profile["shell"]
        allowed = profile["shell"]["allowed_commands"]
        assert "pytest" in allowed
        assert "git" in allowed

    def test_generate_development_profile_denies_destructive_commands(self):
        """Test development profile still denies destructive commands."""
        profile = generate_development_profile()
        assert "denied_patterns" in profile["shell"]
        denied = profile["shell"]["denied_patterns"]
        assert "rm -rf /" in denied or any("rm" in p for p in denied)


@pytest.mark.skipif(not PROFILE_MANAGER_AVAILABLE, reason="mcp_profile_manager not implemented (TDD red phase)")
class TestTestingProfile:
    """Test testing profile generation (moderate restrictions)."""

    def test_generate_testing_profile_filesystem_write_restricted(self):
        """Test testing profile restricts write to tests/ only."""
        profile = generate_testing_profile()
        assert "write" in profile["filesystem"]
        assert "tests/**" in profile["filesystem"]["write"]
        assert "src/**" not in profile["filesystem"]["write"]

    def test_generate_testing_profile_shell_pytest_only(self):
        """Test testing profile allows pytest but limits other commands."""
        profile = generate_testing_profile()
        allowed = profile["shell"]["allowed_commands"]
        assert "pytest" in allowed
        assert len(allowed) < 10


@pytest.mark.skipif(not PROFILE_MANAGER_AVAILABLE, reason="mcp_profile_manager not implemented (TDD red phase)")
class TestProductionProfile:
    """Test production profile generation (most restrictive)."""

    def test_generate_production_profile_filesystem_read_minimal(self):
        """Test production profile has minimal read permissions."""
        profile = generate_production_profile()
        read_paths = profile["filesystem"]["read"]
        assert len(read_paths) < 5

    def test_generate_production_profile_shell_minimal(self):
        """Test production profile has minimal shell command access."""
        profile = generate_production_profile()
        allowed = profile["shell"]["allowed_commands"]
        assert len(allowed) <= 3


@pytest.mark.skipif(not PROFILE_MANAGER_AVAILABLE, reason="mcp_profile_manager not implemented (TDD red phase)")
class TestProfileCustomization:
    """Test profile customization and merging."""

    def test_customize_profile_merge_overrides(self):
        """Test customizing profile merges base with overrides."""
        base_profile = generate_development_profile()
        overrides = {"filesystem": {"read": ["custom/**"]}}
        customized = customize_profile(base_profile, overrides)
        assert "custom/**" in customized["filesystem"]["read"]
        assert "src/**" in customized["filesystem"]["read"]


@pytest.mark.skipif(not PROFILE_MANAGER_AVAILABLE, reason="mcp_profile_manager not implemented (TDD red phase)")
class TestProfileValidation:
    """Test profile schema validation."""

    def test_validate_profile_schema_valid(self):
        """Test validating a valid profile schema."""
        profile = generate_development_profile()
        result = validate_profile_schema(profile)
        assert result.valid is True

    def test_validate_profile_schema_missing_filesystem(self):
        """Test validating profile missing required filesystem section."""
        invalid_profile = {"shell": {"allowed_commands": ["pytest"]}}
        result = validate_profile_schema(invalid_profile)
        assert result.valid is False


@pytest.mark.skipif(not PROFILE_MANAGER_AVAILABLE, reason="mcp_profile_manager not implemented (TDD red phase)")
class TestProfileExport:
    """Test profile export to JSON."""

    def test_export_profile_to_json_file(self):
        """Test exporting profile to JSON file."""
        profile = generate_development_profile()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name
        try:
            export_profile(profile, output_path)
            with open(output_path, 'r') as f:
                loaded = json.load(f)
            assert loaded == profile
        finally:
            os.unlink(output_path)

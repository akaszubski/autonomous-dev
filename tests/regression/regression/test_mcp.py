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

# Import permission validator - skip if not found
try:
    from mcp_permission_validator import (
        MCPPermissionValidator,
        ValidationResult,
        PermissionDeniedError,
        validate_fs_read,
        validate_fs_write,
        validate_shell_execute,
        validate_network_access,
        validate_env_access,
        matches_glob_pattern,
    )
    PERMISSION_VALIDATOR_AVAILABLE = True
except ImportError:
    PERMISSION_VALIDATOR_AVAILABLE = False


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


# =============================================================================
# Permission Validator Tests
# =============================================================================

@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestFilesystemReadValidation:
    """Test filesystem read permission validation."""

    def test_validate_fs_read_allowed_src_path(self):
        """Test fs:read allows reading from src/** directory."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_fs_read("/project/src/main.py")
        assert result.approved is True

    def test_validate_fs_read_denied_env_file(self):
        """Test fs:read denies reading .env file (secrets)."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_fs_read("/project/.env")
        assert result.approved is False
        assert ".env" in result.reason.lower()

    def test_validate_fs_read_denied_ssh_keys(self):
        """Test fs:read denies reading SSH private keys."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_fs_read("/home/user/.ssh/id_rsa")
        assert result.approved is False

    def test_validate_fs_read_denied_path_traversal(self):
        """Test fs:read denies path traversal attempts (CWE-22)."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_fs_read("/project/src/../../etc/passwd")
        assert result.approved is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestFilesystemWriteValidation:
    """Test filesystem write permission validation."""

    def test_validate_fs_write_allowed_src_path(self):
        """Test fs:write allows writing to src/** directory."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_fs_write("/project/src/new_file.py")
        assert result.approved is True

    def test_validate_fs_write_denied_outside_project(self):
        """Test fs:write denies writing outside project directory."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_fs_write("/etc/passwd")
        assert result.approved is False

    def test_validate_fs_write_denied_env_file(self):
        """Test fs:write denies overwriting .env file."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_fs_write("/project/.env")
        assert result.approved is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestShellCommandValidation:
    """Test shell command execution validation."""

    def test_validate_shell_execute_allowed_pytest(self):
        """Test shell:execute allows running pytest."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_shell_execute("pytest tests/")
        assert result.approved is True

    def test_validate_shell_execute_denied_rm_rf(self):
        """Test shell:execute denies destructive rm -rf command."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_shell_execute("rm -rf /")
        assert result.approved is False

    def test_validate_shell_execute_command_injection_semicolon(self):
        """Test shell:execute prevents command injection with semicolon (CWE-78)."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_shell_execute("git status; rm -rf /")
        assert result.approved is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestNetworkAccessValidation:
    """Test network access validation (SSRF prevention)."""

    def test_validate_network_access_allowed_external_api(self):
        """Test network:access allows external API calls."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_network_access("https://api.github.com/repos")
        assert result.approved is True

    def test_validate_network_access_denied_localhost(self):
        """Test network:access denies localhost connections (SSRF)."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_network_access("http://127.0.0.1:8080/admin")
        assert result.approved is False

    def test_validate_network_access_denied_aws_metadata(self):
        """Test network:access denies AWS metadata service (169.254.169.254)."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_network_access("http://169.254.169.254/latest/meta-data/")
        assert result.approved is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestEnvironmentVariableValidation:
    """Test environment variable access validation."""

    def test_validate_env_access_allowed_path(self):
        """Test env:access allows reading PATH variable."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_env_access("PATH")
        assert result.approved is True

    def test_validate_env_access_denied_api_key(self):
        """Test env:access denies reading API_KEY (secret)."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_env_access("API_KEY")
        assert result.approved is False


# =============================================================================
# Bypass Prevention Tests (CWE-specific)
# =============================================================================

@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestPathTraversalPrevention:
    """Test CWE-22: Path Traversal Prevention."""

    def test_path_traversal_basic_dotdot(self):
        """Test basic path traversal with ../ is blocked."""
        validator = MCPPermissionValidator(policy_path=None)
        validator.project_root = "/project"
        result = validator.validate_fs_read("/project/src/../../etc/passwd")
        assert result.approved is False

    def test_path_traversal_url_encoded_dots(self):
        """Test URL-encoded path traversal (%2e%2e%2f) is blocked."""
        validator = MCPPermissionValidator(policy_path=None)
        validator.project_root = "/project"
        result = validator.validate_fs_read("/project/src/%2e%2e/%2e%2e/etc/passwd")
        assert result.approved is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestSymlinkAttackPrevention:
    """Test CWE-59: Symlink Attack Prevention."""

    def test_symlink_attack_link_to_etc_passwd(self):
        """Test symlink from project/evil -> /etc/passwd is blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            evil_link = project_dir / "evil"
            target = Path("/etc/passwd")
            if target.exists():
                evil_link.symlink_to(target)
                validator = MCPPermissionValidator(policy_path=None)
                validator.project_root = str(project_dir)
                result = validator.validate_fs_read(str(evil_link))
                assert result.approved is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestCommandInjectionPrevention:
    """Test CWE-78: Command Injection Prevention."""

    def test_command_injection_semicolon_separator(self):
        """Test command injection with semicolon separator is blocked."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_shell_execute("git status; rm -rf /")
        assert result.approved is False

    def test_command_injection_backticks(self):
        """Test command injection with backticks is blocked."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_shell_execute("echo `whoami`")
        assert result.approved is False

    def test_command_injection_dollar_parentheses(self):
        """Test command injection with $(...) is blocked."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_shell_execute("echo $(whoami)")
        assert result.approved is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestSSRFPrevention:
    """Test Server-Side Request Forgery (SSRF) Prevention."""

    def test_ssrf_localhost_127_0_0_1(self):
        """Test SSRF to localhost (127.0.0.1) is blocked."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_network_access("http://127.0.0.1:8080/admin")
        assert result.approved is False

    def test_ssrf_private_ip_10(self):
        """Test SSRF to private IP range 10.0.0.0/8 is blocked."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_network_access("http://10.0.0.5:8080/")
        assert result.approved is False

    def test_ssrf_private_ip_192(self):
        """Test SSRF to private IP range 192.168.0.0/16 is blocked."""
        validator = MCPPermissionValidator(policy_path=None)
        result = validator.validate_network_access("http://192.168.1.1/admin")
        assert result.approved is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestNullByteInjection:
    """Test null byte injection prevention."""

    def test_null_byte_injection_path(self):
        """Test null byte injection in file path is blocked."""
        validator = MCPPermissionValidator(policy_path=None)
        validator.project_root = "/project"
        result = validator.validate_fs_read("/project/src/main.py\x00/etc/passwd")
        assert result.approved is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestGlobPatternMatching:
    """Test glob pattern matching for path validation."""

    def test_matches_glob_pattern_double_star(self):
        """Test glob pattern matching with ** (recursive)."""
        validator = MCPPermissionValidator(policy_path=None)
        assert validator.matches_glob_pattern("/project/src/main.py", "src/**") is True
        assert validator.matches_glob_pattern("/project/tests/test.py", "src/**") is False


@pytest.mark.skipif(not PERMISSION_VALIDATOR_AVAILABLE, reason="mcp_permission_validator not implemented (TDD red phase)")
class TestPolicyLoading:
    """Test security policy loading and parsing."""

    def test_load_policy_from_file(self):
        """Test loading security policy from JSON file."""
        policy = {
            "filesystem": {"read": ["src/**", "tests/**"], "write": ["src/**"]},
            "shell": {"allowed_commands": ["pytest", "git"], "denied_patterns": ["rm -rf"]}
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(policy, f)
            policy_path = f.name
        try:
            validator = MCPPermissionValidator(policy_path=policy_path)
            assert validator.policy is not None
            assert "filesystem" in validator.policy
        finally:
            os.unlink(policy_path)

    def test_load_policy_default_profile(self):
        """Test loading default development policy when no file specified."""
        validator = MCPPermissionValidator(policy_path=None)
        assert validator.policy is not None

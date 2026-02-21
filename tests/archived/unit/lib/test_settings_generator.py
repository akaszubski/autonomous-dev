#!/usr/bin/env python3
"""
Unit tests for settings_generator.py - TDD Red Phase

Tests the SettingsGenerator class for creating .claude/settings.local.json
with specific command patterns (no wildcards) and comprehensive deny list.

Expected to FAIL until implementation is complete.

Security Requirements (GitHub Issue #115):
1. No wildcards: Must use specific patterns like Bash(git:*), NOT Bash(*)
2. Comprehensive deny list: Block dangerous commands (rm -rf, sudo, eval, etc.)
3. Safe command auto-approval: All autonomous-dev commands pre-approved
4. Merge capability: Preserve user customizations during upgrades
5. Path traversal prevention: Validate all file operations
6. Command injection prevention: Validate pattern generation

Test Strategy:
- Test SettingsGenerator class initialization and configuration
- Test command discovery from plugins/autonomous-dev/commands/*.md
- Test specific pattern generation (git:*, pytest:*, python:*, etc.)
- Test deny list includes all dangerous operations
- Test NO wildcards like Bash(*) are generated
- Test JSON structure validation
- Test security: path traversal and injection prevention
- Test edge cases: empty commands/, missing directories, corrupted data

Coverage Target: 95%+ for settings_generator.py

Author: test-master agent
Date: 2025-12-12
Issue: #115
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected to fail - no implementation yet)
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from dataclasses import asdict

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.lib.settings_generator import (
        SettingsGenerator,
        GeneratorResult,
        SettingsGeneratorError,
        DEFAULT_DENY_LIST,
        SAFE_COMMAND_PATTERNS,
    )
except ImportError:
    pytest.skip("settings_generator.py not implemented yet", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_plugin_dir(tmp_path):
    """Create temporary plugin directory with command files"""
    plugin_dir = tmp_path / "plugins" / "autonomous-dev"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)

    # Create sample command files
    command_files = [
        "auto-implement.md",
        "batch-implement.md",
        "align-project.md",
        "research.md",
        "test-feature.md",
        "setup.md",
        "sync.md",
    ]

    for cmd_file in command_files:
        (commands_dir / cmd_file).write_text(f"# {cmd_file}\n\nCommand description")

    return plugin_dir


@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root directory"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()
    return project_root


@pytest.fixture
def existing_settings_with_customizations(temp_project_root):
    """Create existing settings.local.json with user customizations"""
    settings_path = temp_project_root / ".claude" / "settings.local.json"

    user_settings = {
        "hooks": {
            "PreCommit": [
                {"type": "command", "command": "python3 custom_hook.py"}
            ]
        },
        "permissions": {
            "allow": [
                "Read(**/*.py)",
                "Write(**/*.py)",
                "Bash(custom-command:*)"
            ]
        },
        "custom_key": "user_value"
    }

    settings_path.write_text(json.dumps(user_settings, indent=2))
    return settings_path


# =============================================================================
# Initialization Tests (3 tests)
# =============================================================================

def test_generator_initialization(temp_plugin_dir):
    """Test SettingsGenerator initializes with plugin directory"""
    generator = SettingsGenerator(temp_plugin_dir)

    assert generator.plugin_dir == temp_plugin_dir
    assert generator.commands_dir == temp_plugin_dir / "commands"
    assert isinstance(generator.discovered_commands, list)


def test_generator_initialization_invalid_plugin_dir():
    """Test SettingsGenerator raises error for non-existent plugin directory"""
    invalid_dir = Path("/nonexistent/plugin/dir")

    with pytest.raises(SettingsGeneratorError) as exc_info:
        SettingsGenerator(invalid_dir)

    assert "plugin directory" in str(exc_info.value).lower()
    assert "not found" in str(exc_info.value).lower()


def test_generator_initialization_missing_commands_dir(tmp_path):
    """Test SettingsGenerator raises error when commands/ directory missing"""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    # Don't create commands/ subdirectory

    with pytest.raises(SettingsGeneratorError) as exc_info:
        SettingsGenerator(plugin_dir)

    assert "commands" in str(exc_info.value).lower()
    assert "not found" in str(exc_info.value).lower()


# =============================================================================
# Command Discovery Tests (5 tests)
# =============================================================================

def test_discover_commands_finds_all_md_files(temp_plugin_dir):
    """Test discover_commands() finds all .md files in commands/"""
    generator = SettingsGenerator(temp_plugin_dir)

    commands = generator.discover_commands()

    assert len(commands) == 7  # From fixture
    assert "auto-implement" in commands
    assert "batch-implement" in commands
    assert "research" in commands
    assert "setup" in commands


def test_discover_commands_ignores_non_md_files(tmp_path):
    """Test discover_commands() ignores non-.md files"""
    plugin_dir = tmp_path / "plugins" / "autonomous-dev"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)

    # Create mix of .md and other files
    (commands_dir / "valid.md").write_text("# Valid")
    (commands_dir / "ignore.txt").write_text("Ignore")
    (commands_dir / "ignore.py").write_text("Ignore")
    (commands_dir / ".hidden.md").write_text("Ignore hidden")

    generator = SettingsGenerator(plugin_dir)
    commands = generator.discover_commands()

    assert len(commands) == 1
    assert "valid" in commands


def test_discover_commands_handles_empty_directory(tmp_path):
    """Test discover_commands() handles empty commands/ directory"""
    plugin_dir = tmp_path / "plugins" / "autonomous-dev"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)

    generator = SettingsGenerator(plugin_dir)
    commands = generator.discover_commands()

    assert len(commands) == 0
    assert isinstance(commands, list)


def test_discover_commands_handles_archived_subdirectory(tmp_path):
    """Test discover_commands() ignores archived/ subdirectory"""
    plugin_dir = tmp_path / "plugins" / "autonomous-dev"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)

    # Create valid command
    (commands_dir / "active.md").write_text("# Active")

    # Create archived subdirectory with old commands
    archived_dir = commands_dir / "archived"
    archived_dir.mkdir()
    (archived_dir / "old.md").write_text("# Old")

    generator = SettingsGenerator(plugin_dir)
    commands = generator.discover_commands()

    assert len(commands) == 1
    assert "active" in commands
    assert "old" not in commands


def test_discover_commands_handles_permission_error(tmp_path, monkeypatch):
    """Test discover_commands() handles permission errors gracefully"""
    plugin_dir = tmp_path / "plugins" / "autonomous-dev"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)

    generator = SettingsGenerator(plugin_dir)

    # Mock Path.iterdir() to raise PermissionError
    def mock_iterdir():
        raise PermissionError("Access denied")

    with patch.object(Path, 'iterdir', mock_iterdir):
        with pytest.raises(SettingsGeneratorError) as exc_info:
            generator.discover_commands()

        assert "permission" in str(exc_info.value).lower()


# =============================================================================
# Command Pattern Generation Tests (10 tests - CRITICAL)
# =============================================================================

def test_build_command_patterns_creates_specific_patterns(temp_plugin_dir):
    """Test build_command_patterns() creates specific patterns, NOT wildcards

    CRITICAL: Must generate Bash(git:*), Bash(pytest:*), etc.
             Must NEVER generate Bash(*) wildcard
    """
    generator = SettingsGenerator(temp_plugin_dir)

    patterns = generator.build_command_patterns()

    # Should have specific patterns
    assert "Bash(git:*)" in patterns
    assert "Bash(pytest:*)" in patterns
    assert "Bash(python:*)" in patterns
    assert "Bash(python3:*)" in patterns
    assert "Bash(gh:*)" in patterns
    assert "Bash(npm:*)" in patterns
    assert "Bash(pip:*)" in patterns

    # Should NEVER have wildcard
    assert "Bash(*)" not in patterns


def test_build_command_patterns_includes_read_write_permissions(temp_plugin_dir):
    """Test build_command_patterns() includes Read/Write patterns"""
    generator = SettingsGenerator(temp_plugin_dir)

    patterns = generator.build_command_patterns()

    # File operation patterns
    assert "Read(**)" in patterns
    assert "Write(**)" in patterns
    assert "Edit(**)" in patterns
    assert "Glob(**)" in patterns
    assert "Grep(**)" in patterns


def test_build_command_patterns_no_wildcards_at_all(temp_plugin_dir):
    """Test build_command_patterns() contains NO wildcard patterns

    SECURITY: Wildcards like Bash(*) defeat the entire security model
    """
    generator = SettingsGenerator(temp_plugin_dir)

    patterns = generator.build_command_patterns()

    # Check for any wildcard patterns that would match everything
    dangerous_wildcards = [
        "Bash(*)",
        "Bash(**)",
        "Shell(*)",
        "Shell(**)",
        "Exec(*)",
        "Exec(**)",
    ]

    for wildcard in dangerous_wildcards:
        assert wildcard not in patterns, f"Found dangerous wildcard: {wildcard}"


def test_build_command_patterns_includes_autonomous_dev_commands(temp_plugin_dir):
    """Test build_command_patterns() includes autonomous-dev specific commands"""
    generator = SettingsGenerator(temp_plugin_dir)

    patterns = generator.build_command_patterns()

    # Plugin-specific patterns based on discovered commands
    # These should be derived from the command discovery
    expected_patterns = [
        "Bash(git:*)",
        "Bash(pytest:*)",
        "Bash(python:*)",
        "Read(**/*.py)",
        "Write(**/*.py)",
        "Read(**/*.md)",
        "Write(**/*.md)",
    ]

    for pattern in expected_patterns:
        assert pattern in patterns


def test_build_command_patterns_format_validation(temp_plugin_dir):
    """Test build_command_patterns() produces valid pattern format"""
    generator = SettingsGenerator(temp_plugin_dir)

    patterns = generator.build_command_patterns()

    for pattern in patterns:
        # All patterns should be strings
        assert isinstance(pattern, str)

        # Should contain proper syntax
        if pattern.startswith("Bash("):
            assert pattern.endswith(")")
            assert ":" in pattern or pattern == "Bash(**)"  # Either command:* or catch-all

        # No empty patterns
        assert len(pattern) > 0


def test_build_command_patterns_deduplication(tmp_path):
    """Test build_command_patterns() removes duplicate patterns"""
    plugin_dir = tmp_path / "plugins" / "autonomous-dev"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)

    # Create multiple commands that would generate same patterns
    (commands_dir / "cmd1.md").write_text("# Command 1")
    (commands_dir / "cmd2.md").write_text("# Command 2")

    generator = SettingsGenerator(plugin_dir)
    patterns = generator.build_command_patterns()

    # Should not have duplicates
    assert len(patterns) == len(set(patterns))


def test_build_command_patterns_includes_safe_readonly_operations(temp_plugin_dir):
    """Test build_command_patterns() includes safe read-only operations"""
    generator = SettingsGenerator(temp_plugin_dir)

    patterns = generator.build_command_patterns()

    # Safe read-only commands
    safe_readonly = [
        "Bash(ls:*)",
        "Bash(cat:*)",
        "Bash(head:*)",
        "Bash(tail:*)",
        "Bash(grep:*)",
        "Bash(find:*)",
    ]

    for pattern in safe_readonly:
        assert pattern in patterns


def test_build_command_patterns_excludes_dangerous_commands(temp_plugin_dir):
    """Test build_command_patterns() excludes dangerous command patterns"""
    generator = SettingsGenerator(temp_plugin_dir)

    patterns = generator.build_command_patterns()

    # Dangerous commands that should NOT be auto-approved
    dangerous = [
        "Bash(rm:*)",
        "Bash(sudo:*)",
        "Bash(eval:*)",
        "Bash(chmod:*)",
        "Bash(chown:*)",
        "Bash(dd:*)",
        "Bash(mkfs:*)",
    ]

    for pattern in dangerous:
        assert pattern not in patterns


def test_build_command_patterns_security_prevents_injection(temp_plugin_dir):
    """Test build_command_patterns() prevents command injection in patterns

    SECURITY: Malicious command names shouldn't allow injection
    """
    # Create command with malicious name
    commands_dir = temp_plugin_dir / "commands"
    malicious_file = commands_dir / "evil;rm -rf.md"
    malicious_file.write_text("# Evil command")

    generator = SettingsGenerator(temp_plugin_dir)

    # Should either sanitize or reject the malicious pattern
    with pytest.raises(SettingsGeneratorError):
        generator.build_command_patterns()


def test_build_command_patterns_validates_pattern_syntax(temp_plugin_dir):
    """Test build_command_patterns() validates all patterns have correct syntax"""
    generator = SettingsGenerator(temp_plugin_dir)

    patterns = generator.build_command_patterns()

    # All patterns should match expected format
    valid_prefixes = ["Bash(", "Read(", "Write(", "Edit(", "Glob(", "Grep("]

    for pattern in patterns:
        # Check it has a valid prefix
        has_valid_prefix = any(pattern.startswith(prefix) for prefix in valid_prefixes)
        assert has_valid_prefix, f"Invalid pattern format: {pattern}"

        # Check it ends with )
        assert pattern.endswith(")"), f"Pattern doesn't end with ): {pattern}"


# =============================================================================
# Deny List Generation Tests (8 tests - CRITICAL)
# =============================================================================

def test_build_deny_list_includes_destructive_file_operations():
    """Test build_deny_list() blocks destructive file operations"""
    generator = SettingsGenerator(Path("/tmp"))  # Minimal init

    deny_list = generator.build_deny_list()

    # Destructive file operations
    destructive = [
        "Bash(rm:-rf*)",
        "Bash(rm:-f*)",
        "Bash(shred:*)",
        "Bash(dd:*)",
        "Bash(mkfs:*)",
    ]

    for pattern in destructive:
        assert pattern in deny_list


def test_build_deny_list_includes_privilege_escalation():
    """Test build_deny_list() blocks privilege escalation commands"""
    generator = SettingsGenerator(Path("/tmp"))

    deny_list = generator.build_deny_list()

    # Privilege escalation
    escalation = [
        "Bash(sudo:*)",
        "Bash(su:*)",
        "Bash(doas:*)",
    ]

    for pattern in escalation:
        assert pattern in deny_list


def test_build_deny_list_includes_code_execution():
    """Test build_deny_list() blocks code execution commands"""
    generator = SettingsGenerator(Path("/tmp"))

    deny_list = generator.build_deny_list()

    # Code execution
    execution = [
        "Bash(eval:*)",
        "Bash(exec:*)",
        "Bash(source:*)",
        "Bash(.:*)",  # . is alias for source
    ]

    for pattern in execution:
        assert pattern in deny_list


def test_build_deny_list_includes_permission_changes():
    """Test build_deny_list() blocks permission modification commands"""
    generator = SettingsGenerator(Path("/tmp"))

    deny_list = generator.build_deny_list()

    # Permission changes
    permissions = [
        "Bash(chmod:*)",
        "Bash(chown:*)",
        "Bash(chgrp:*)",
    ]

    for pattern in permissions:
        assert pattern in deny_list


def test_build_deny_list_includes_network_commands():
    """Test build_deny_list() blocks dangerous network operations"""
    generator = SettingsGenerator(Path("/tmp"))

    deny_list = generator.build_deny_list()

    # Network operations that could be abused
    network = [
        "Bash(nc:*)",  # netcat
        "Bash(ncat:*)",
        "Bash(wget:*--post-file*)",  # Data exfiltration
        "Bash(curl:*--data*)",  # Data exfiltration
    ]

    for pattern in network:
        assert pattern in deny_list


def test_build_deny_list_includes_git_force_operations():
    """Test build_deny_list() blocks dangerous git operations"""
    generator = SettingsGenerator(Path("/tmp"))

    deny_list = generator.build_deny_list()

    # Dangerous git operations
    git_dangerous = [
        "Bash(git:*--force*)",
        "Bash(git:*push*-f*)",
        "Bash(git:*reset*--hard*)",
        "Bash(git:*clean*-fd*)",
    ]

    for pattern in git_dangerous:
        assert pattern in deny_list


def test_build_deny_list_includes_package_operations():
    """Test build_deny_list() blocks package installation/removal"""
    generator = SettingsGenerator(Path("/tmp"))

    deny_list = generator.build_deny_list()

    # Package operations (can modify system)
    packages = [
        "Bash(apt:*install*)",
        "Bash(apt:*remove*)",
        "Bash(yum:*install*)",
        "Bash(brew:*install*)",
        "Bash(npm:*install*-g*)",  # Global install
    ]

    for pattern in packages:
        assert pattern in deny_list


def test_build_deny_list_no_overlap_with_safe_patterns(temp_plugin_dir):
    """Test deny list doesn't block safe command patterns

    CRITICAL: Deny list should not conflict with safe allow patterns
    """
    generator = SettingsGenerator(temp_plugin_dir)

    allow_patterns = generator.build_command_patterns()
    deny_patterns = generator.build_deny_list()

    # Safe patterns should not be in deny list
    safe_patterns = [
        "Bash(git:status)",
        "Bash(git:diff)",
        "Bash(git:log)",
        "Bash(pytest:*)",
        "Bash(python:*)",
        "Read(**)",
        "Write(**)",
    ]

    for safe in safe_patterns:
        assert safe not in deny_patterns


# =============================================================================
# Settings Generation Tests (10 tests)
# =============================================================================

def test_generate_settings_produces_valid_json_structure(temp_plugin_dir):
    """Test generate_settings() produces valid JSON structure"""
    generator = SettingsGenerator(temp_plugin_dir)

    settings = generator.generate_settings()

    # Should have required keys
    assert "permissions" in settings
    assert "allow" in settings["permissions"]
    assert "deny" in settings["permissions"]

    # Should be valid JSON-serializable
    json_str = json.dumps(settings, indent=2)
    assert len(json_str) > 0


def test_generate_settings_includes_all_safe_patterns(temp_plugin_dir):
    """Test generate_settings() includes all safe command patterns"""
    generator = SettingsGenerator(temp_plugin_dir)

    settings = generator.generate_settings()
    allow_list = settings["permissions"]["allow"]

    # Should include key safe patterns
    expected_patterns = [
        "Bash(git:*)",
        "Bash(pytest:*)",
        "Read(**)",
        "Write(**)",
    ]

    for pattern in expected_patterns:
        assert pattern in allow_list


def test_generate_settings_includes_all_deny_patterns(temp_plugin_dir):
    """Test generate_settings() includes comprehensive deny list"""
    generator = SettingsGenerator(temp_plugin_dir)

    settings = generator.generate_settings()
    deny_list = settings["permissions"]["deny"]

    # Should include critical deny patterns
    expected_denies = [
        "Bash(rm:-rf*)",
        "Bash(sudo:*)",
        "Bash(eval:*)",
    ]

    for pattern in expected_denies:
        assert pattern in deny_list


def test_generate_settings_no_wildcards_in_output(temp_plugin_dir):
    """Test generate_settings() does NOT include wildcard patterns

    CRITICAL: Final output should have specific patterns only
    """
    generator = SettingsGenerator(temp_plugin_dir)

    settings = generator.generate_settings()
    allow_list = settings["permissions"]["allow"]

    # Should NOT have wildcard
    assert "Bash(*)" not in allow_list


def test_generate_settings_includes_metadata(temp_plugin_dir):
    """Test generate_settings() includes metadata for tracking"""
    generator = SettingsGenerator(temp_plugin_dir)

    settings = generator.generate_settings()

    # Should include metadata
    assert "generated_by" in settings
    assert "autonomous-dev" in settings["generated_by"]
    assert "version" in settings
    assert "timestamp" in settings


def test_generate_settings_preserves_custom_hooks(temp_plugin_dir, existing_settings_with_customizations):
    """Test generate_settings() preserves user's custom hooks section"""
    generator = SettingsGenerator(temp_plugin_dir)

    # Load existing settings
    existing = json.loads(existing_settings_with_customizations.read_text())

    # Generate new settings
    settings = generator.generate_settings(merge_with=existing)

    # Should preserve user hooks
    assert "hooks" in settings
    assert "PreCommit" in settings["hooks"]
    assert settings["hooks"]["PreCommit"] == existing["hooks"]["PreCommit"]


def test_generate_settings_preserves_custom_permissions(temp_plugin_dir, existing_settings_with_customizations):
    """Test generate_settings() preserves user's custom permissions"""
    generator = SettingsGenerator(temp_plugin_dir)

    # Load existing settings
    existing = json.loads(existing_settings_with_customizations.read_text())

    # Generate new settings with merge
    settings = generator.generate_settings(merge_with=existing)

    # Should preserve user's custom Bash pattern
    assert "Bash(custom-command:*)" in settings["permissions"]["allow"]


def test_generate_settings_validates_output_structure(temp_plugin_dir):
    """Test generate_settings() validates output has correct structure"""
    generator = SettingsGenerator(temp_plugin_dir)

    settings = generator.generate_settings()

    # Validate structure
    assert isinstance(settings, dict)
    assert isinstance(settings["permissions"], dict)
    assert isinstance(settings["permissions"]["allow"], list)
    assert isinstance(settings["permissions"]["deny"], list)

    # All patterns should be strings
    for pattern in settings["permissions"]["allow"]:
        assert isinstance(pattern, str)

    for pattern in settings["permissions"]["deny"]:
        assert isinstance(pattern, str)


def test_generate_settings_handles_empty_merge_dict(temp_plugin_dir):
    """Test generate_settings() handles empty merge_with parameter"""
    generator = SettingsGenerator(temp_plugin_dir)

    # Should work with empty dict
    settings = generator.generate_settings(merge_with={})

    assert "permissions" in settings
    assert len(settings["permissions"]["allow"]) > 0


def test_generate_settings_handles_none_merge(temp_plugin_dir):
    """Test generate_settings() handles None merge_with parameter"""
    generator = SettingsGenerator(temp_plugin_dir)

    # Should work with None
    settings = generator.generate_settings(merge_with=None)

    assert "permissions" in settings
    assert len(settings["permissions"]["allow"]) > 0


# =============================================================================
# File Writing Tests (7 tests)
# =============================================================================

def test_write_settings_creates_file(temp_plugin_dir, temp_project_root):
    """Test write_settings() creates .claude/settings.local.json"""
    generator = SettingsGenerator(temp_plugin_dir)

    output_path = temp_project_root / ".claude" / "settings.local.json"

    result = generator.write_settings(output_path)

    assert result.success is True
    assert output_path.exists()
    assert "created" in result.message.lower()


def test_write_settings_creates_claude_directory_if_missing(temp_plugin_dir, tmp_path):
    """Test write_settings() creates .claude/ directory if it doesn't exist"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    # Don't create .claude/ directory

    generator = SettingsGenerator(temp_plugin_dir)
    output_path = project_root / ".claude" / "settings.local.json"

    result = generator.write_settings(output_path)

    assert result.success is True
    assert output_path.parent.exists()
    assert output_path.exists()


def test_write_settings_validates_json_output(temp_plugin_dir, temp_project_root):
    """Test write_settings() produces valid JSON file"""
    generator = SettingsGenerator(temp_plugin_dir)

    output_path = temp_project_root / ".claude" / "settings.local.json"
    generator.write_settings(output_path)

    # Should be valid JSON
    content = json.loads(output_path.read_text())
    assert "permissions" in content
    assert "allow" in content["permissions"]


def test_write_settings_handles_permission_error(temp_plugin_dir, tmp_path, monkeypatch):
    """Test write_settings() handles permission errors gracefully"""
    project_root = tmp_path / "project"
    project_root.mkdir()

    generator = SettingsGenerator(temp_plugin_dir)
    output_path = project_root / ".claude" / "settings.local.json"

    # Mock write to raise PermissionError
    def mock_write_text(*args, **kwargs):
        raise PermissionError("Access denied")

    with patch.object(Path, 'write_text', mock_write_text):
        with pytest.raises(SettingsGeneratorError) as exc_info:
            generator.write_settings(output_path)

        assert "permission" in str(exc_info.value).lower()


def test_write_settings_validates_path_security(temp_plugin_dir):
    """Test write_settings() prevents path traversal attacks

    SECURITY: Prevent writing to ../../etc/passwd
    """
    generator = SettingsGenerator(temp_plugin_dir)

    # Try to write outside project
    malicious_path = Path("/etc/passwd")

    with pytest.raises(SettingsGeneratorError) as exc_info:
        generator.write_settings(malicious_path)

    assert "path" in str(exc_info.value).lower()


def test_write_settings_backs_up_existing_file(temp_plugin_dir, existing_settings_with_customizations):
    """Test write_settings() backs up existing settings before overwriting"""
    generator = SettingsGenerator(temp_plugin_dir)

    settings_path = existing_settings_with_customizations
    backup_path = settings_path.parent / "settings.local.json.backup"

    result = generator.write_settings(settings_path, backup=True)

    assert result.success is True
    assert backup_path.exists()
    assert "backed up" in result.message.lower()


def test_write_settings_result_includes_statistics(temp_plugin_dir, temp_project_root):
    """Test write_settings() result includes statistics"""
    generator = SettingsGenerator(temp_plugin_dir)

    output_path = temp_project_root / ".claude" / "settings.local.json"

    result = generator.write_settings(output_path)

    assert hasattr(result, 'patterns_added')
    assert hasattr(result, 'denies_added')
    assert result.patterns_added > 0
    assert result.denies_added > 0


# =============================================================================
# Edge Cases and Error Handling (8 tests)
# =============================================================================

def test_handles_corrupted_existing_settings(temp_plugin_dir, temp_project_root):
    """Test generator handles corrupted existing settings.local.json"""
    settings_path = temp_project_root / ".claude" / "settings.local.json"

    # Write invalid JSON
    settings_path.write_text("{ invalid json content }")

    generator = SettingsGenerator(temp_plugin_dir)

    # Should handle gracefully by backing up and creating fresh
    result = generator.write_settings(settings_path, merge_existing=True)

    assert result.success is True
    assert "corrupted" in result.message.lower() or "invalid" in result.message.lower()


def test_handles_symlink_in_path(temp_plugin_dir, tmp_path):
    """Test generator handles symlinks in output path

    SECURITY: Should resolve symlinks and validate final path
    """
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Create symlink
    symlink_dir = tmp_path / "symlink"
    if hasattr(symlink_dir, 'symlink_to'):
        symlink_dir.symlink_to(project_root)

        generator = SettingsGenerator(temp_plugin_dir)
        output_path = symlink_dir / ".claude" / "settings.local.json"

        # Should either resolve and accept, or reject symlinks
        # Implementation detail - test that it doesn't crash
        try:
            result = generator.write_settings(output_path)
            assert result.success is True or result.success is False
        except SettingsGeneratorError:
            # Also acceptable to reject symlinks
            pass


def test_handles_disk_full_error(temp_plugin_dir, temp_project_root, monkeypatch):
    """Test generator handles disk full errors gracefully"""
    generator = SettingsGenerator(temp_plugin_dir)
    output_path = temp_project_root / ".claude" / "settings.local.json"

    # Mock write to raise OSError (disk full)
    def mock_write_text(*args, **kwargs):
        raise OSError(28, "No space left on device")

    with patch.object(Path, 'write_text', mock_write_text):
        with pytest.raises(SettingsGeneratorError) as exc_info:
            generator.write_settings(output_path)

        assert "space" in str(exc_info.value).lower() or "disk" in str(exc_info.value).lower()


def test_handles_readonly_filesystem(temp_plugin_dir, temp_project_root, monkeypatch):
    """Test generator handles read-only filesystem gracefully"""
    generator = SettingsGenerator(temp_plugin_dir)
    output_path = temp_project_root / ".claude" / "settings.local.json"

    # Mock write to raise OSError (read-only)
    def mock_write_text(*args, **kwargs):
        raise OSError(30, "Read-only file system")

    with patch.object(Path, 'write_text', mock_write_text):
        with pytest.raises(SettingsGeneratorError) as exc_info:
            generator.write_settings(output_path)

        assert "read-only" in str(exc_info.value).lower() or "permission" in str(exc_info.value).lower()


def test_handles_unicode_in_command_names(tmp_path):
    """Test generator handles unicode characters in command files"""
    plugin_dir = tmp_path / "plugins" / "autonomous-dev"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)

    # Create command with unicode name
    unicode_file = commands_dir / "命令.md"
    unicode_file.write_text("# Unicode command", encoding='utf-8')

    generator = SettingsGenerator(plugin_dir)

    # Should handle unicode gracefully
    commands = generator.discover_commands()
    assert len(commands) >= 0  # Might include or skip unicode


def test_handles_very_long_command_names(tmp_path):
    """Test generator handles very long command file names"""
    plugin_dir = tmp_path / "plugins" / "autonomous-dev"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)

    # Create command with very long name
    long_name = "a" * 200 + ".md"
    long_file = commands_dir / long_name
    long_file.write_text("# Long name command")

    generator = SettingsGenerator(plugin_dir)

    # Should handle gracefully (might truncate or skip)
    try:
        commands = generator.discover_commands()
        assert isinstance(commands, list)
    except SettingsGeneratorError:
        # Also acceptable to reject overly long names
        pass


def test_handles_special_characters_in_patterns(temp_plugin_dir):
    """Test generator sanitizes special characters in patterns

    SECURITY: Prevent regex injection or pattern escaping
    """
    # Create command with special chars that could break patterns
    commands_dir = temp_plugin_dir / "commands"
    special_file = commands_dir / "cmd[special].md"
    special_file.write_text("# Special chars")

    generator = SettingsGenerator(temp_plugin_dir)

    # Should sanitize or reject special characters
    try:
        patterns = generator.build_command_patterns()
        # Patterns should not contain unescaped special chars
        for pattern in patterns:
            # Should not have dangling brackets
            assert pattern.count('[') == pattern.count(']')
    except SettingsGeneratorError:
        # Also acceptable to reject special chars
        pass


def test_concurrent_write_safety(temp_plugin_dir, temp_project_root):
    """Test generator handles concurrent writes safely

    NOTE: This is a basic test - full concurrency testing would need threading
    """
    generator = SettingsGenerator(temp_plugin_dir)
    output_path = temp_project_root / ".claude" / "settings.local.json"

    # Write twice in succession
    result1 = generator.write_settings(output_path)
    result2 = generator.write_settings(output_path)

    # Both should succeed
    assert result1.success is True
    assert result2.success is True

    # File should be valid JSON
    content = json.loads(output_path.read_text())
    assert "permissions" in content


# =============================================================================
# Integration with Security Utils (3 tests)
# =============================================================================

def test_uses_security_utils_for_path_validation(temp_plugin_dir, temp_project_root):
    """Test generator uses security_utils.validate_path() for all paths

    SECURITY: All file operations should go through security validation
    """
    generator = SettingsGenerator(temp_plugin_dir)
    output_path = temp_project_root / ".claude" / "settings.local.json"

    # Mock security validation
    with patch('autonomous_dev.lib.settings_generator.validate_path') as mock_validate:
        mock_validate.return_value = output_path  # Allow the path

        generator.write_settings(output_path)

        # Should have called validation
        assert mock_validate.called


def test_rejects_path_traversal_via_security_utils(temp_plugin_dir):
    """Test generator rejects path traversal via security_utils

    SECURITY: validate_path should catch ../../ attacks
    """
    generator = SettingsGenerator(temp_plugin_dir)
    malicious_path = Path("../../etc/passwd")

    with pytest.raises(SettingsGeneratorError) as exc_info:
        generator.write_settings(malicious_path)

    assert "path" in str(exc_info.value).lower()


def test_audit_logs_all_file_operations(temp_plugin_dir, temp_project_root):
    """Test generator audit logs all file write operations

    SECURITY: All writes should be logged for audit trail
    """
    generator = SettingsGenerator(temp_plugin_dir)
    output_path = temp_project_root / ".claude" / "settings.local.json"

    # Mock audit logging
    with patch('autonomous_dev.lib.settings_generator.audit_log') as mock_audit:
        generator.write_settings(output_path)

        # Should have logged the operation
        assert mock_audit.called
        # Should include path in log
        log_args = mock_audit.call_args[0]
        assert str(output_path) in str(log_args)


# =============================================================================
# Default Constants Tests (2 tests)
# =============================================================================

def test_default_deny_list_is_comprehensive():
    """Test DEFAULT_DENY_LIST constant includes all dangerous commands"""
    # This tests the module-level constant
    assert len(DEFAULT_DENY_LIST) > 20  # Should have many deny patterns

    # Check for critical denies
    critical_denies = [
        "Bash(rm:-rf*)",
        "Bash(sudo:*)",
        "Bash(eval:*)",
        "Bash(chmod:*)",
    ]

    for deny in critical_denies:
        assert deny in DEFAULT_DENY_LIST


def test_safe_command_patterns_are_specific():
    """Test SAFE_COMMAND_PATTERNS constant has specific patterns only"""
    # This tests the module-level constant
    assert len(SAFE_COMMAND_PATTERNS) > 10  # Should have many safe patterns

    # Should NOT have wildcards
    assert "Bash(*)" not in SAFE_COMMAND_PATTERNS

    # Should have specific patterns
    assert "Bash(git:*)" in SAFE_COMMAND_PATTERNS or \
           "Bash(pytest:*)" in SAFE_COMMAND_PATTERNS

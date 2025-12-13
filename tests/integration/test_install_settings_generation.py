#!/usr/bin/env python3
"""
Integration tests for settings.local.json generation during install/update

Tests the end-to-end workflow of generating .claude/settings.local.json
with proper permissions during plugin installation and updates.

Expected to FAIL until implementation is complete.

Test Coverage:
1. Fresh install: Create new settings.local.json from scratch
2. Upgrade install: Merge with existing user settings
3. User customization preservation: Hooks, permissions, custom keys
4. Missing directory creation: Auto-create .claude/ if needed
5. Permission error handling: Graceful degradation
6. Invalid JSON recovery: Backup corrupted file and regenerate
7. Symlink handling: Resolve and validate paths
8. Concurrent operations: Safe concurrent writes

Integration Points:
- SettingsGenerator library
- security_utils for path validation
- File system operations
- JSON serialization/deserialization
- Backup mechanisms

Author: test-master agent
Date: 2025-12-12
Issue: #115
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected to fail - no implementation yet)
"""

import json
import sys
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.lib.settings_generator import (
        SettingsGenerator,
        GeneratorResult,
        SettingsGeneratorError,
    )
except ImportError:
    pytest.skip("settings_generator.py not implemented yet", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def plugin_dir(tmp_path):
    """Create realistic plugin directory structure"""
    plugin_root = tmp_path / "plugins" / "autonomous-dev"
    commands_dir = plugin_root / "commands"
    commands_dir.mkdir(parents=True)

    # Create realistic command files matching actual plugin
    commands = [
        ("auto-implement.md", "# Auto Implement\n\nAutonomous feature development"),
        ("batch-implement.md", "# Batch Implement\n\nProcess multiple features"),
        ("align-project.md", "# Align Project\n\nFix PROJECT.md conflicts"),
        ("align-claude.md", "# Align Claude\n\nFix documentation drift"),
        ("research.md", "# Research\n\nResearch patterns"),
        ("plan.md", "# Plan\n\nArchitecture planning"),
        ("test-feature.md", "# Test Feature\n\nTDD test generation"),
        ("implement.md", "# Implement\n\nCode implementation"),
        ("review.md", "# Review\n\nCode quality review"),
        ("security-scan.md", "# Security Scan\n\nVulnerability scan"),
        ("update-docs.md", "# Update Docs\n\nDocumentation sync"),
        ("setup.md", "# Setup\n\nInteractive setup"),
        ("sync.md", "# Sync\n\nUnified sync"),
        ("status.md", "# Status\n\nProject progress"),
        ("health-check.md", "# Health Check\n\nPlugin validation"),
        ("pipeline-status.md", "# Pipeline Status\n\nWorkflow tracking"),
        ("update-plugin.md", "# Update Plugin\n\nPlugin update"),
        ("create-issue.md", "# Create Issue\n\nGitHub issue creation"),
        ("align-project-retrofit.md", "# Retrofit\n\nBrownfield adoption"),
    ]

    for filename, content in commands:
        (commands_dir / filename).write_text(content)

    return plugin_root


@pytest.fixture
def project_root(tmp_path):
    """Create realistic project root directory"""
    project = tmp_path / "test_project"
    project.mkdir()

    # Create typical project structure
    (project / "src").mkdir()
    (project / "tests").mkdir()
    (project / "docs").mkdir()
    (project / ".git").mkdir()

    return project


@pytest.fixture
def existing_user_settings(project_root):
    """Create existing settings.local.json with user customizations"""
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"

    user_settings = {
        "hooks": {
            "PreCommit": [
                {"type": "command", "command": "black .", "timeout": 10}
            ],
            "PrePush": [
                {"type": "command", "command": "pytest", "timeout": 300}
            ]
        },
        "permissions": {
            "allow": [
                "Read(**/*.py)",
                "Write(**/*.py)",
                "Bash(custom-linter:*)",
                "Bash(mypy:*)"
            ]
        },
        "user_metadata": {
            "project_type": "python",
            "custom_field": "user_value"
        }
    }

    settings_path.write_text(json.dumps(user_settings, indent=2))
    return settings_path


# =============================================================================
# Fresh Installation Tests (5 tests)
# =============================================================================

def test_fresh_install_creates_settings_file(plugin_dir, project_root):
    """Test fresh install creates .claude/settings.local.json from scratch

    Scenario: User installs autonomous-dev plugin for first time
    Expected: New settings.local.json created with all safe patterns
    """
    generator = SettingsGenerator(plugin_dir)

    settings_path = project_root / ".claude" / "settings.local.json"

    # Settings file should not exist yet
    assert not settings_path.exists()

    # Generate settings
    result = generator.write_settings(settings_path)

    # Should succeed
    assert result.success is True
    assert "created" in result.message.lower() or "generated" in result.message.lower()

    # File should exist now
    assert settings_path.exists()

    # Should be valid JSON
    content = json.loads(settings_path.read_text())
    assert "permissions" in content
    assert "allow" in content["permissions"]
    assert "deny" in content["permissions"]


def test_fresh_install_includes_all_safe_commands(plugin_dir, project_root):
    """Test fresh install includes patterns for all discovered commands

    Scenario: User installs plugin
    Expected: All 19 commands result in safe patterns being generated
    """
    generator = SettingsGenerator(plugin_dir)

    settings_path = project_root / ".claude" / "settings.local.json"
    generator.write_settings(settings_path)

    content = json.loads(settings_path.read_text())
    allow_patterns = content["permissions"]["allow"]

    # Should have git patterns (used by most commands)
    assert "Bash(git:*)" in allow_patterns

    # Should have pytest patterns (used by test commands)
    assert "Bash(pytest:*)" in allow_patterns

    # Should have python patterns
    assert "Bash(python:*)" in allow_patterns or "Bash(python3:*)" in allow_patterns

    # Should have file operation patterns
    assert "Read(**)" in allow_patterns
    assert "Write(**)" in allow_patterns


def test_fresh_install_no_wildcards(plugin_dir, project_root):
    """Test fresh install does NOT include Bash(*) wildcard

    CRITICAL: Fresh install should use specific patterns only
    Expected: No Bash(*), Shell(*), or other catch-all wildcards
    """
    generator = SettingsGenerator(plugin_dir)

    settings_path = project_root / ".claude" / "settings.local.json"
    generator.write_settings(settings_path)

    content = json.loads(settings_path.read_text())
    allow_patterns = content["permissions"]["allow"]

    # Should NOT have any wildcards
    dangerous_wildcards = ["Bash(*)", "Bash(**)", "Shell(*)", "Exec(*)"]

    for wildcard in dangerous_wildcards:
        assert wildcard not in allow_patterns, f"Found dangerous wildcard: {wildcard}"


def test_fresh_install_includes_comprehensive_deny_list(plugin_dir, project_root):
    """Test fresh install includes comprehensive deny list

    Expected: All dangerous operations blocked by default
    """
    generator = SettingsGenerator(plugin_dir)

    settings_path = project_root / ".claude" / "settings.local.json"
    generator.write_settings(settings_path)

    content = json.loads(settings_path.read_text())
    deny_patterns = content["permissions"]["deny"]

    # Should block destructive operations
    critical_denies = [
        "Bash(rm:-rf*)",
        "Bash(sudo:*)",
        "Bash(eval:*)",
        "Bash(chmod:*)",
    ]

    for deny in critical_denies:
        assert deny in deny_patterns, f"Missing critical deny: {deny}"


def test_fresh_install_creates_claude_directory(plugin_dir, tmp_path):
    """Test fresh install creates .claude/ directory if missing

    Scenario: New project without .claude/ directory
    Expected: Directory created automatically
    """
    project = tmp_path / "new_project"
    project.mkdir()

    # No .claude/ directory yet
    claude_dir = project / ".claude"
    assert not claude_dir.exists()

    generator = SettingsGenerator(plugin_dir)
    settings_path = claude_dir / "settings.local.json"

    generator.write_settings(settings_path)

    # Directory should be created
    assert claude_dir.exists()
    assert claude_dir.is_dir()
    assert settings_path.exists()


# =============================================================================
# Upgrade Installation Tests (7 tests)
# =============================================================================

def test_upgrade_preserves_user_hooks(plugin_dir, existing_user_settings):
    """Test upgrade installation preserves user's custom hooks

    Scenario: User has custom PreCommit/PrePush hooks
    Expected: Hooks preserved after upgrade
    """
    # Load original user settings
    original = json.loads(existing_user_settings.read_text())
    original_hooks = original["hooks"]

    generator = SettingsGenerator(plugin_dir)

    # Simulate upgrade by writing with merge
    result = generator.write_settings(existing_user_settings, merge_existing=True)

    assert result.success is True

    # Load upgraded settings
    upgraded = json.loads(existing_user_settings.read_text())

    # User hooks should still be there
    assert "hooks" in upgraded
    assert "PreCommit" in upgraded["hooks"]
    assert "PrePush" in upgraded["hooks"]
    assert upgraded["hooks"]["PreCommit"] == original_hooks["PreCommit"]
    assert upgraded["hooks"]["PrePush"] == original_hooks["PrePush"]


def test_upgrade_preserves_user_permissions(plugin_dir, existing_user_settings):
    """Test upgrade preserves user's custom permission patterns

    Scenario: User has added custom Bash patterns for their tools
    Expected: Custom patterns preserved alongside generated ones
    """
    # Load original user settings
    original = json.loads(existing_user_settings.read_text())

    generator = SettingsGenerator(plugin_dir)
    result = generator.write_settings(existing_user_settings, merge_existing=True)

    assert result.success is True

    # Load upgraded settings
    upgraded = json.loads(existing_user_settings.read_text())
    allow_patterns = upgraded["permissions"]["allow"]

    # User's custom patterns should be preserved
    assert "Bash(custom-linter:*)" in allow_patterns
    assert "Bash(mypy:*)" in allow_patterns

    # Generated patterns should also be present
    assert "Bash(git:*)" in allow_patterns
    assert "Bash(pytest:*)" in allow_patterns


def test_upgrade_preserves_custom_metadata(plugin_dir, existing_user_settings):
    """Test upgrade preserves user's custom metadata fields

    Scenario: User has added custom keys to settings.local.json
    Expected: Custom keys preserved after upgrade
    """
    # Load original user settings
    original = json.loads(existing_user_settings.read_text())

    generator = SettingsGenerator(plugin_dir)
    generator.write_settings(existing_user_settings, merge_existing=True)

    # Load upgraded settings
    upgraded = json.loads(existing_user_settings.read_text())

    # Custom metadata should be preserved
    assert "user_metadata" in upgraded
    assert upgraded["user_metadata"] == original["user_metadata"]


def test_upgrade_adds_new_patterns(plugin_dir, existing_user_settings):
    """Test upgrade adds new safe patterns from plugin

    Scenario: Plugin adds new commands in update
    Expected: New patterns added without removing user patterns
    """
    generator = SettingsGenerator(plugin_dir)

    # Get initial pattern count
    original = json.loads(existing_user_settings.read_text())
    original_allow_count = len(original["permissions"]["allow"])

    # Perform upgrade
    generator.write_settings(existing_user_settings, merge_existing=True)

    # Load upgraded settings
    upgraded = json.loads(existing_user_settings.read_text())
    upgraded_allow_count = len(upgraded["permissions"]["allow"])

    # Should have more patterns after upgrade
    assert upgraded_allow_count > original_allow_count


def test_upgrade_deduplicates_patterns(plugin_dir, existing_user_settings):
    """Test upgrade removes duplicate patterns

    Scenario: User already has some patterns that plugin would generate
    Expected: No duplicates in final output
    """
    generator = SettingsGenerator(plugin_dir)

    generator.write_settings(existing_user_settings, merge_existing=True)

    # Load upgraded settings
    upgraded = json.loads(existing_user_settings.read_text())
    allow_patterns = upgraded["permissions"]["allow"]
    deny_patterns = upgraded["permissions"]["deny"]

    # Should have no duplicates
    assert len(allow_patterns) == len(set(allow_patterns))
    assert len(deny_patterns) == len(set(deny_patterns))


def test_upgrade_backs_up_existing_file(plugin_dir, existing_user_settings):
    """Test upgrade creates backup of existing settings

    Scenario: User upgrades plugin
    Expected: Original settings backed up before modification
    """
    backup_path = existing_user_settings.parent / "settings.local.json.backup"

    # Backup should not exist yet
    assert not backup_path.exists()

    generator = SettingsGenerator(plugin_dir)
    result = generator.write_settings(existing_user_settings, merge_existing=True, backup=True)

    # Backup should be created
    assert backup_path.exists()

    # Backup should match original content
    original = json.loads(existing_user_settings.read_text())
    backup = json.loads(backup_path.read_text())

    # Note: backup has original, file now has merged content
    # So we check backup has the original hooks
    assert "hooks" in backup


def test_upgrade_reports_statistics(plugin_dir, existing_user_settings):
    """Test upgrade reports how many patterns were added/preserved

    Expected: Result includes counts of new vs preserved patterns
    """
    generator = SettingsGenerator(plugin_dir)

    result = generator.write_settings(existing_user_settings, merge_existing=True)

    assert result.success is True
    assert hasattr(result, 'patterns_added')
    assert hasattr(result, 'patterns_preserved')
    assert result.patterns_added > 0  # Should add new patterns
    assert result.patterns_preserved > 0  # Should preserve user patterns


# =============================================================================
# Error Handling Tests (8 tests)
# =============================================================================

def test_handles_corrupted_json_gracefully(plugin_dir, project_root):
    """Test handling of corrupted existing settings.local.json

    Scenario: settings.local.json exists but has invalid JSON
    Expected: Backup corrupted file and create fresh settings
    """
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"
    backup_path = claude_dir / "settings.local.json.corrupted"

    # Write invalid JSON
    settings_path.write_text("{ invalid json content [[[")

    generator = SettingsGenerator(plugin_dir)

    # Should handle gracefully
    result = generator.write_settings(settings_path, merge_existing=True)

    assert result.success is True
    assert "corrupted" in result.message.lower() or "invalid" in result.message.lower()

    # Should create backup of corrupted file
    assert backup_path.exists()

    # New file should be valid JSON
    content = json.loads(settings_path.read_text())
    assert "permissions" in content


def test_handles_permission_denied_on_directory(plugin_dir, tmp_path, monkeypatch):
    """Test handling of permission errors when creating .claude/ directory

    Scenario: User doesn't have write permission to project root
    Expected: Clear error message
    """
    project = tmp_path / "readonly_project"
    project.mkdir()

    generator = SettingsGenerator(plugin_dir)
    settings_path = project / ".claude" / "settings.local.json"

    # Mock mkdir to raise PermissionError
    original_mkdir = Path.mkdir

    def mock_mkdir(self, *args, **kwargs):
        if ".claude" in str(self):
            raise PermissionError("Access denied")
        return original_mkdir(self, *args, **kwargs)

    with patch.object(Path, 'mkdir', mock_mkdir):
        with pytest.raises(SettingsGeneratorError) as exc_info:
            generator.write_settings(settings_path)

        assert "permission" in str(exc_info.value).lower()


def test_handles_permission_denied_on_file(plugin_dir, project_root):
    """Test handling of permission errors when writing file

    Scenario: .claude/ directory exists but file is read-only
    Expected: Clear error message
    """
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"
    settings_path.write_text("{}")
    settings_path.chmod(0o444)  # Read-only

    generator = SettingsGenerator(plugin_dir)

    try:
        with pytest.raises(SettingsGeneratorError) as exc_info:
            generator.write_settings(settings_path)

        assert "permission" in str(exc_info.value).lower()
    finally:
        # Cleanup: restore write permission
        settings_path.chmod(0o644)


def test_handles_disk_full_error(plugin_dir, project_root):
    """Test handling of disk full errors

    Scenario: Disk runs out of space during write
    Expected: Clear error message
    """
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"

    generator = SettingsGenerator(plugin_dir)

    # Mock write to raise OSError (disk full)
    def mock_write_text(*args, **kwargs):
        raise OSError(28, "No space left on device")

    with patch.object(Path, 'write_text', mock_write_text):
        with pytest.raises(SettingsGeneratorError) as exc_info:
            generator.write_settings(settings_path)

        error_msg = str(exc_info.value).lower()
        assert "space" in error_msg or "disk" in error_msg or "device" in error_msg


def test_handles_symlink_in_path(plugin_dir, tmp_path):
    """Test handling of symlinks in output path

    Scenario: .claude/ or parent is a symlink
    Expected: Resolve symlink and validate final path
    """
    project = tmp_path / "real_project"
    project.mkdir()

    # Create symlink to project
    symlink_project = tmp_path / "symlink_project"

    if hasattr(symlink_project, 'symlink_to'):
        symlink_project.symlink_to(project)

        generator = SettingsGenerator(plugin_dir)
        settings_path = symlink_project / ".claude" / "settings.local.json"

        # Should either resolve and work, or reject symlinks
        try:
            result = generator.write_settings(settings_path)
            # If it succeeds, file should exist at real location
            real_path = project / ".claude" / "settings.local.json"
            assert real_path.exists() or settings_path.exists()
        except SettingsGeneratorError:
            # Also acceptable to reject symlinks for security
            pass
    else:
        pytest.skip("Symlinks not supported")


def test_handles_path_traversal_attempt(plugin_dir, tmp_path):
    """Test handling of path traversal attack

    SECURITY: Prevent writing to ../../etc/passwd
    Expected: Reject path and raise security error
    """
    generator = SettingsGenerator(plugin_dir)

    # Try to write outside project
    malicious_path = tmp_path / ".." / ".." / "etc" / "passwd"

    with pytest.raises(SettingsGeneratorError) as exc_info:
        generator.write_settings(malicious_path)

    error_msg = str(exc_info.value).lower()
    assert "path" in error_msg or "security" in error_msg


def test_handles_missing_parent_directories(plugin_dir, tmp_path):
    """Test handling of missing parent directories

    Scenario: .claude/ directory doesn't exist
    Expected: Create parent directories automatically
    """
    project = tmp_path / "new_project"
    project.mkdir()

    # Don't create .claude/ directory
    settings_path = project / ".claude" / "settings.local.json"

    generator = SettingsGenerator(plugin_dir)
    result = generator.write_settings(settings_path)

    # Should create parent and file
    assert result.success is True
    assert settings_path.exists()
    assert settings_path.parent.exists()


def test_handles_concurrent_writes(plugin_dir, project_root):
    """Test handling of concurrent writes to same file

    Scenario: Multiple processes try to write settings simultaneously
    Expected: Both succeed, last write wins
    """
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"

    generator = SettingsGenerator(plugin_dir)

    # Simulate concurrent writes
    result1 = generator.write_settings(settings_path)
    result2 = generator.write_settings(settings_path)

    # Both should succeed
    assert result1.success is True
    assert result2.success is True

    # Final file should be valid
    content = json.loads(settings_path.read_text())
    assert "permissions" in content


# =============================================================================
# Security Validation Tests (5 tests)
# =============================================================================

def test_validates_all_paths_through_security_utils(plugin_dir, project_root):
    """Test all path operations go through security validation

    SECURITY: All file operations should use validate_path()
    """
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"

    generator = SettingsGenerator(plugin_dir)

    # Mock security validation
    with patch('autonomous_dev.lib.settings_generator.validate_path') as mock_validate:
        mock_validate.return_value = settings_path  # Allow the path

        generator.write_settings(settings_path)

        # Should have validated the path
        assert mock_validate.called
        assert settings_path in [call[0][0] for call in mock_validate.call_args_list]


def test_rejects_absolute_paths_outside_project(plugin_dir):
    """Test rejection of absolute paths outside project

    SECURITY: Should only write within project boundaries
    """
    generator = SettingsGenerator(plugin_dir)

    dangerous_paths = [
        Path("/etc/passwd"),
        Path("/tmp/malicious.json"),
        Path("/var/log/evil.json"),
    ]

    for dangerous_path in dangerous_paths:
        with pytest.raises(SettingsGeneratorError) as exc_info:
            generator.write_settings(dangerous_path)

        error_msg = str(exc_info.value).lower()
        assert "path" in error_msg or "security" in error_msg


def test_prevents_command_injection_in_patterns(plugin_dir):
    """Test prevention of command injection via malicious command names

    SECURITY: Malicious .md filenames shouldn't inject commands
    """
    # Create command with injection attempt
    commands_dir = plugin_dir / "commands"
    malicious_file = commands_dir / "evil;rm -rf.md"

    try:
        malicious_file.write_text("# Evil command")

        generator = SettingsGenerator(plugin_dir)

        # Should either sanitize or reject
        with pytest.raises(SettingsGeneratorError):
            generator.build_command_patterns()
    finally:
        # Cleanup
        if malicious_file.exists():
            malicious_file.unlink()


def test_audit_logs_all_operations(plugin_dir, project_root):
    """Test all file operations are audit logged

    SECURITY: Create audit trail for security review
    """
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"

    generator = SettingsGenerator(plugin_dir)

    # Mock audit logging
    with patch('autonomous_dev.lib.settings_generator.audit_log') as mock_audit:
        generator.write_settings(settings_path)

        # Should have logged the operation
        assert mock_audit.called


def test_validates_generated_json_structure(plugin_dir, project_root):
    """Test generated JSON is validated before writing

    SECURITY: Prevent malformed JSON from being written
    """
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"

    generator = SettingsGenerator(plugin_dir)
    generator.write_settings(settings_path)

    # Should be valid JSON
    content = json.loads(settings_path.read_text())

    # Should have required structure
    assert "permissions" in content
    assert isinstance(content["permissions"], dict)
    assert "allow" in content["permissions"]
    assert "deny" in content["permissions"]
    assert isinstance(content["permissions"]["allow"], list)
    assert isinstance(content["permissions"]["deny"], list)


# =============================================================================
# Real-World Scenario Tests (4 tests)
# =============================================================================

def test_realistic_fresh_install_workflow(plugin_dir, tmp_path):
    """Test complete fresh install workflow

    Scenario: New user installs autonomous-dev plugin
    Expected: Complete settings.local.json with all patterns
    """
    # Create realistic project
    project = tmp_path / "my_project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "tests").mkdir()
    (project / ".git").mkdir()

    # Run installation
    generator = SettingsGenerator(plugin_dir)
    settings_path = project / ".claude" / "settings.local.json"

    result = generator.write_settings(settings_path)

    # Verify success
    assert result.success is True
    assert settings_path.exists()

    # Verify content
    content = json.loads(settings_path.read_text())

    # Should have safe patterns
    assert "Bash(git:*)" in content["permissions"]["allow"]
    assert "Bash(pytest:*)" in content["permissions"]["allow"]

    # Should have deny list
    assert "Bash(rm:-rf*)" in content["permissions"]["deny"]
    assert "Bash(sudo:*)" in content["permissions"]["deny"]

    # Should NOT have wildcards
    assert "Bash(*)" not in content["permissions"]["allow"]


def test_realistic_upgrade_workflow(plugin_dir, tmp_path):
    """Test complete upgrade workflow preserving user settings

    Scenario: User upgrades plugin after customizing settings
    Expected: Customizations preserved, new patterns added
    """
    # Create project with existing settings
    project = tmp_path / "existing_project"
    project.mkdir()
    claude_dir = project / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"

    # User's customized settings
    user_settings = {
        "hooks": {
            "PreCommit": [{"type": "command", "command": "mypy ."}]
        },
        "permissions": {
            "allow": [
                "Bash(mypy:*)",
                "Bash(black:*)"
            ]
        }
    }

    settings_path.write_text(json.dumps(user_settings, indent=2))

    # Run upgrade
    generator = SettingsGenerator(plugin_dir)
    result = generator.write_settings(settings_path, merge_existing=True, backup=True)

    # Verify success
    assert result.success is True

    # Verify backup created
    backup_path = claude_dir / "settings.local.json.backup"
    assert backup_path.exists()

    # Verify merge
    content = json.loads(settings_path.read_text())

    # User hooks preserved
    assert "hooks" in content
    assert "PreCommit" in content["hooks"]

    # User permissions preserved
    assert "Bash(mypy:*)" in content["permissions"]["allow"]
    assert "Bash(black:*)" in content["permissions"]["allow"]

    # Plugin patterns added
    assert "Bash(git:*)" in content["permissions"]["allow"]
    assert "Bash(pytest:*)" in content["permissions"]["allow"]


def test_realistic_corrupted_settings_recovery(plugin_dir, tmp_path):
    """Test recovery from corrupted settings.local.json

    Scenario: User's settings got corrupted (manual edit error)
    Expected: Backup corrupted file and regenerate
    """
    project = tmp_path / "corrupted_project"
    project.mkdir()
    claude_dir = project / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"

    # Write corrupted JSON
    settings_path.write_text('{ "permissions": { "allow": [ incomplete')

    # Run recovery
    generator = SettingsGenerator(plugin_dir)
    result = generator.write_settings(settings_path, merge_existing=True)

    # Should succeed with warning
    assert result.success is True
    assert "corrupted" in result.message.lower() or "invalid" in result.message.lower()

    # Should backup corrupted file
    backup_path = claude_dir / "settings.local.json.corrupted"
    assert backup_path.exists()

    # New file should be valid
    content = json.loads(settings_path.read_text())
    assert "permissions" in content


def test_realistic_multiple_upgrades(plugin_dir, tmp_path):
    """Test multiple sequential upgrades preserve settings correctly

    Scenario: User upgrades plugin multiple times
    Expected: Settings stay consistent, no degradation
    """
    project = tmp_path / "multi_upgrade_project"
    project.mkdir()
    claude_dir = project / ".claude"
    claude_dir.mkdir()

    settings_path = claude_dir / "settings.local.json"

    generator = SettingsGenerator(plugin_dir)

    # First install
    result1 = generator.write_settings(settings_path)
    assert result1.success is True

    content1 = json.loads(settings_path.read_text())
    allow_count1 = len(content1["permissions"]["allow"])

    # First upgrade
    result2 = generator.write_settings(settings_path, merge_existing=True)
    assert result2.success is True

    content2 = json.loads(settings_path.read_text())
    allow_count2 = len(content2["permissions"]["allow"])

    # Second upgrade
    result3 = generator.write_settings(settings_path, merge_existing=True)
    assert result3.success is True

    content3 = json.loads(settings_path.read_text())
    allow_count3 = len(content3["permissions"]["allow"])

    # Pattern count should stabilize (no duplicates accumulating)
    assert allow_count2 == allow_count1  # Same patterns
    assert allow_count3 == allow_count2  # Still same patterns

    # Should still be valid
    assert "Bash(git:*)" in content3["permissions"]["allow"]
    assert "Bash(*)" not in content3["permissions"]["allow"]

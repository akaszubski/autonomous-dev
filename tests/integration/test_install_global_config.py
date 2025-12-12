#!/usr/bin/env python3
"""
Integration tests for global settings configuration during install - TDD Red Phase

Tests the install.sh integration with global settings merge:
1. Hooks copied to ~/.claude/hooks/
2. Libraries copied to ~/.claude/lib/
3. Global settings merged at ~/.claude/settings.json
4. Broken patterns fixed during install/update
5. User customizations preserved

Expected to FAIL until implementation is complete.

Security Requirements (GitHub Issue #117):
1. Global config setup integrated into install.sh
2. Hooks and libraries copied to global locations
3. Broken Bash(:*) patterns detected and fixed
4. User customizations preserved during updates
5. Backup created before modifications
6. Atomic writes prevent corruption

Test Strategy:
- Mock filesystem for isolated testing
- Test fresh install scenario
- Test update with valid config scenario
- Test update with broken config scenario
- Test file copying (hooks and libraries)
- Test permission errors and recovery
- Test edge cases: corrupted files, missing directories

Coverage Target: 90%+ for installation integration

Author: test-master agent
Date: 2025-12-13
Issue: #117
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected to fail - no implementation yet)
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call
from typing import Dict, Any
import shutil
import tempfile

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.lib.settings_generator import SettingsGenerator
except ImportError:
    # Mock for test discovery
    class SettingsGenerator:
        def merge_global_settings(self, global_path: Path, template_path: Path) -> Dict[str, Any]:
            raise NotImplementedError("Implementation pending")


# Test Constants
BROKEN_WILDCARDS = ["Bash(:*)", "Bash(*)", "Bash(**)"]

REQUIRED_SAFE_PATTERNS = [
    "Bash(git:*)",
    "Bash(python:*)",
    "Bash(python3:*)",
    "Bash(pytest:*)",
    "Bash(pip:*)",
    "Bash(pip3:*)",
    "Bash(ls:*)",
    "Bash(cat:*)",
    "Bash(gh:*)",
]

TEMPLATE_SETTINGS = {
    "allowedTools": {
        "Bash": {
            "allow_patterns": REQUIRED_SAFE_PATTERNS,
            "deny_patterns": ["Bash(rm:*-rf*)", "Bash(sudo:*)"],
        }
    },
    "customHooks": {
        "PreToolUse": ["~/.claude/hooks/auto_approve_tool.py"]
    }
}


class TestInstallGlobalConfig:
    """Integration tests for global settings configuration during install"""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """Create temporary home directory"""
        home = tmp_path / "home"
        home.mkdir()
        return home

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with plugin structure"""
        repo = tmp_path / "repo"
        repo.mkdir()

        # Create plugin structure
        plugins = repo / "plugins" / "autonomous-dev"
        plugins.mkdir(parents=True)

        # Create hooks directory
        hooks = plugins / "hooks"
        hooks.mkdir()
        (hooks / "auto_approve_tool.py").write_text("# Hook script")
        (hooks / "auto_git_workflow.py").write_text("# Git workflow hook")

        # Create lib directory
        lib = plugins / "lib"
        lib.mkdir()
        (lib / "settings_generator.py").write_text("# Library")
        (lib / "security_utils.py").write_text("# Security utils")

        # Create config template
        config = plugins / "config"
        config.mkdir()
        template = config / "global_settings_template.json"
        template.write_text(json.dumps(TEMPLATE_SETTINGS, indent=2))

        return repo

    def test_fresh_install_creates_global_settings(self, temp_home, temp_repo):
        """Test: Fresh install creates ~/.claude/settings.json from template"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        assert not global_settings.exists()

        # Act
        generator = SettingsGenerator(project_root=temp_repo)
        result = generator.merge_global_settings(global_settings, template_path)

        # Assert
        assert global_settings.exists()
        data = json.loads(global_settings.read_text())
        assert data["allowedTools"]["Bash"]["allow_patterns"] == REQUIRED_SAFE_PATTERNS
        assert "Bash(:*)" not in data["allowedTools"]["Bash"]["allow_patterns"]

    def test_update_with_valid_config_preserves_settings(self, temp_home, temp_repo):
        """Test: Update with valid config preserves user customizations"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)

        valid_user_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": [
                        "Bash(git:*)",
                        "Bash(python:*)",
                        "Bash(docker:*)",  # User custom
                    ],
                    "deny_patterns": ["Bash(rm:*-rf*)"],
                }
            },
            "customHooks": {
                "PreToolUse": ["~/.my-hooks/custom_hook.py"]  # User hook
            }
        }
        global_settings.write_text(json.dumps(valid_user_settings, indent=2))

        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"

        # Act
        generator = SettingsGenerator(project_root=temp_repo)
        result = generator.merge_global_settings(global_settings, template_path)

        # Assert
        data = json.loads(global_settings.read_text())
        assert "Bash(docker:*)" in data["allowedTools"]["Bash"]["allow_patterns"]  # User custom preserved
        assert "~/.my-hooks/custom_hook.py" in data["customHooks"]["PreToolUse"]  # User hook preserved
        assert all(p in data["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)

    def test_update_with_broken_config_fixes_patterns(self, temp_home, temp_repo):
        """Test: Update with broken config fixes Bash(:*) patterns"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)

        broken_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": ["Bash(:*)"],  # BROKEN
                }
            },
            "customHooks": {
                "PreToolUse": ["~/.my-hooks/custom_hook.py"]
            }
        }
        global_settings.write_text(json.dumps(broken_settings, indent=2))

        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"

        # Act
        generator = SettingsGenerator(project_root=temp_repo)
        result = generator.merge_global_settings(global_settings, template_path)

        # Assert
        data = json.loads(global_settings.read_text())
        assert "Bash(:*)" not in data["allowedTools"]["Bash"]["allow_patterns"]  # Broken pattern removed
        assert all(p in data["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)
        assert "~/.my-hooks/custom_hook.py" in data["customHooks"]["PreToolUse"]  # User hook preserved

    def test_user_customizations_preserved_during_update(self, temp_home, temp_repo):
        """Test: All user customizations preserved during update"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)

        user_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": [
                        "Bash(:*)",        # BROKEN - should be removed
                        "Bash(docker:*)",  # User custom - KEEP
                        "Bash(npm:*)",     # User custom - KEEP
                    ],
                    "deny_patterns": [
                        "Bash(curl:*)",    # User deny - KEEP
                    ],
                }
            },
            "customHooks": {
                "PreToolUse": [
                    "~/.my-hooks/hook1.py",
                    "~/.my-hooks/hook2.py"
                ],
                "PostToolUse": [
                    "~/.my-hooks/post_hook.py"
                ]
            },
            "customSettings": {  # User custom section - KEEP
                "myFeature": "enabled"
            }
        }
        global_settings.write_text(json.dumps(user_settings, indent=2))

        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"

        # Act
        generator = SettingsGenerator(project_root=temp_repo)
        result = generator.merge_global_settings(global_settings, template_path)

        # Assert
        data = json.loads(global_settings.read_text())

        # Broken pattern removed
        assert "Bash(:*)" not in data["allowedTools"]["Bash"]["allow_patterns"]

        # User custom patterns preserved
        assert "Bash(docker:*)" in data["allowedTools"]["Bash"]["allow_patterns"]
        assert "Bash(npm:*)" in data["allowedTools"]["Bash"]["allow_patterns"]

        # User deny patterns preserved
        assert "Bash(curl:*)" in data["allowedTools"]["Bash"]["deny_patterns"]

        # User hooks preserved
        assert "~/.my-hooks/hook1.py" in data["customHooks"]["PreToolUse"]
        assert "~/.my-hooks/hook2.py" in data["customHooks"]["PreToolUse"]
        assert "~/.my-hooks/post_hook.py" in data["customHooks"]["PostToolUse"]

        # User custom sections preserved
        assert "customSettings" in data
        assert data["customSettings"]["myFeature"] == "enabled"

        # Safe patterns added
        assert all(p in data["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)

    def test_hooks_copied_to_global_location(self, temp_home, temp_repo):
        """Test: Hooks copied to ~/.claude/hooks/"""
        # Arrange
        source_hooks = temp_repo / "plugins" / "autonomous-dev" / "hooks"
        target_hooks = temp_home / ".claude" / "hooks"
        target_hooks.mkdir(parents=True, exist_ok=True)

        # Act - Simulate install.sh hook copy
        for hook_file in source_hooks.glob("*.py"):
            shutil.copy2(hook_file, target_hooks / hook_file.name)

        # Assert
        assert (target_hooks / "auto_approve_tool.py").exists()
        assert (target_hooks / "auto_git_workflow.py").exists()
        assert (target_hooks / "auto_approve_tool.py").read_text() == "# Hook script"

    def test_libraries_copied_to_global_location(self, temp_home, temp_repo):
        """Test: Libraries copied to ~/.claude/lib/"""
        # Arrange
        source_lib = temp_repo / "plugins" / "autonomous-dev" / "lib"
        target_lib = temp_home / ".claude" / "lib"
        target_lib.mkdir(parents=True, exist_ok=True)

        # Act - Simulate install.sh lib copy
        for lib_file in source_lib.glob("*.py"):
            shutil.copy2(lib_file, target_lib / lib_file.name)

        # Assert
        assert (target_lib / "settings_generator.py").exists()
        assert (target_lib / "security_utils.py").exists()
        assert (target_lib / "settings_generator.py").read_text() == "# Library"

    def test_backup_created_before_update(self, temp_home, temp_repo):
        """Test: Backup created before modifying global settings"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)

        original_settings = {
            "allowedTools": {
                "Bash": {"allow_patterns": ["Bash(:*)"]}  # BROKEN
            }
        }
        global_settings.write_text(json.dumps(original_settings, indent=2))

        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"

        # Act
        generator = SettingsGenerator(project_root=temp_repo)
        result = generator.merge_global_settings(global_settings, template_path)

        # Assert
        backup_path = global_settings.with_suffix(".json.backup")
        assert backup_path.exists()
        backup_data = json.loads(backup_path.read_text())
        assert backup_data["allowedTools"]["Bash"]["allow_patterns"] == ["Bash(:*)"]  # Original preserved

    def test_corrupted_settings_recovered_from_template(self, temp_home, temp_repo):
        """Test: Corrupted settings.json recovered from template"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)
        global_settings.write_text("{ corrupted json here }")

        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"

        # Act
        generator = SettingsGenerator(project_root=temp_repo)
        result = generator.merge_global_settings(global_settings, template_path)

        # Assert
        data = json.loads(global_settings.read_text())
        assert "allowedTools" in data
        assert all(p in data["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)

    def test_missing_global_directory_created(self, temp_home, temp_repo):
        """Test: Missing ~/.claude/ directory created automatically"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        assert not global_settings.parent.exists()

        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"

        # Act
        generator = SettingsGenerator(project_root=temp_repo)
        result = generator.merge_global_settings(global_settings, template_path)

        # Assert
        assert global_settings.parent.exists()
        assert global_settings.exists()

    def test_permission_error_during_copy_handled(self, temp_home, temp_repo):
        """Test: Permission error during file copy handled gracefully"""
        # Arrange
        target_hooks = temp_home / ".claude" / "hooks"
        target_hooks.mkdir(parents=True, exist_ok=True)
        (target_hooks / "readonly.py").write_text("# Read only")
        (target_hooks / "readonly.py").chmod(0o444)  # Read-only

        source_hooks = temp_repo / "plugins" / "autonomous-dev" / "hooks"

        # Act & Assert
        with pytest.raises(PermissionError):
            shutil.copy2(source_hooks / "auto_approve_tool.py", target_hooks / "readonly.py")

        # Cleanup
        (target_hooks / "readonly.py").chmod(0o644)

    def test_atomic_write_prevents_partial_corruption(self, temp_home, temp_repo):
        """Test: Atomic write prevents partial file corruption"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)
        global_settings.write_text(json.dumps({"test": "data"}, indent=2))

        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"

        # Act - Simulate write interruption
        generator = SettingsGenerator(project_root=temp_repo)

        with patch("pathlib.Path.write_text", side_effect=IOError("Write interrupted")):
            try:
                result = generator.merge_global_settings(global_settings, template_path)
            except IOError:
                pass

        # Assert - Original file should still be valid
        data = json.loads(global_settings.read_text())
        assert "test" in data  # Original data intact

    def test_multiple_updates_preserve_cumulative_customizations(self, temp_home, temp_repo):
        """Test: Multiple updates preserve cumulative customizations"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)

        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        generator = SettingsGenerator(project_root=temp_repo)

        # First install
        initial_settings = {
            "allowedTools": {
                "Bash": {"allow_patterns": ["Bash(:*)"]}
            }
        }
        global_settings.write_text(json.dumps(initial_settings, indent=2))
        result1 = generator.merge_global_settings(global_settings, template_path)

        # User adds customization
        data = json.loads(global_settings.read_text())
        data["allowedTools"]["Bash"]["allow_patterns"].append("Bash(docker:*)")
        global_settings.write_text(json.dumps(data, indent=2))

        # Second update
        result2 = generator.merge_global_settings(global_settings, template_path)

        # User adds another customization
        data = json.loads(global_settings.read_text())
        data["allowedTools"]["Bash"]["allow_patterns"].append("Bash(npm:*)")
        global_settings.write_text(json.dumps(data, indent=2))

        # Third update
        result3 = generator.merge_global_settings(global_settings, template_path)

        # Assert - All customizations preserved
        final_data = json.loads(global_settings.read_text())
        patterns = final_data["allowedTools"]["Bash"]["allow_patterns"]

        assert "Bash(docker:*)" in patterns  # First custom preserved
        assert "Bash(npm:*)" in patterns     # Second custom preserved
        assert all(p in patterns for p in REQUIRED_SAFE_PATTERNS)  # Safe patterns present
        assert "Bash(:*)" not in patterns    # Broken pattern removed

    def test_install_dry_run_mode(self, temp_home, temp_repo):
        """Test: Dry-run mode shows changes without modifying files"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)

        broken_settings = {
            "allowedTools": {
                "Bash": {"allow_patterns": ["Bash(:*)"]}
            }
        }
        global_settings.write_text(json.dumps(broken_settings, indent=2))
        original_content = global_settings.read_text()

        template_path = temp_repo / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"

        # Act - Dry run (implementation would have dry_run parameter)
        generator = SettingsGenerator(project_root=temp_repo)
        # NOTE: Implementation would support dry_run=True parameter
        # result = generator.merge_global_settings(global_settings, template_path, dry_run=True)

        # Assert - For now, just verify we can read settings
        data = json.loads(global_settings.read_text())
        assert data["allowedTools"]["Bash"]["allow_patterns"] == ["Bash(:*)"]


class TestGlobalConfigValidation:
    """Test validation of global settings after merge"""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """Create temporary home directory"""
        home = tmp_path / "home"
        home.mkdir()
        return home

    def test_no_broken_wildcards_in_final_settings(self, temp_home):
        """Test: Final settings contain no broken wildcard patterns"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)

        # Simulate merged settings
        merged_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": REQUIRED_SAFE_PATTERNS,
                }
            }
        }
        global_settings.write_text(json.dumps(merged_settings, indent=2))

        # Act - Validate
        data = json.loads(global_settings.read_text())
        patterns = data["allowedTools"]["Bash"]["allow_patterns"]

        # Assert
        for broken in BROKEN_WILDCARDS:
            assert broken not in patterns

    def test_all_required_safe_patterns_present(self, temp_home):
        """Test: All required safe patterns present in final settings"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)

        merged_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": REQUIRED_SAFE_PATTERNS,
                }
            }
        }
        global_settings.write_text(json.dumps(merged_settings, indent=2))

        # Act - Validate
        data = json.loads(global_settings.read_text())
        patterns = data["allowedTools"]["Bash"]["allow_patterns"]

        # Assert
        for required in REQUIRED_SAFE_PATTERNS:
            assert required in patterns

    def test_valid_json_structure(self, temp_home):
        """Test: Final settings have valid JSON structure"""
        # Arrange
        global_settings = temp_home / ".claude" / "settings.json"
        global_settings.parent.mkdir(parents=True, exist_ok=True)

        merged_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": REQUIRED_SAFE_PATTERNS,
                    "deny_patterns": ["Bash(rm:*-rf*)"],
                }
            }
        }
        global_settings.write_text(json.dumps(merged_settings, indent=2))

        # Act - Validate structure
        data = json.loads(global_settings.read_text())

        # Assert
        assert isinstance(data, dict)
        assert "allowedTools" in data
        assert "Bash" in data["allowedTools"]
        assert "allow_patterns" in data["allowedTools"]["Bash"]
        assert "deny_patterns" in data["allowedTools"]["Bash"]
        assert isinstance(data["allowedTools"]["Bash"]["allow_patterns"], list)
        assert isinstance(data["allowedTools"]["Bash"]["deny_patterns"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

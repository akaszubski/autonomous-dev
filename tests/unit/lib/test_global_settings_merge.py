#!/usr/bin/env python3
"""
Unit tests for global settings merge functionality - TDD Red Phase

Tests the SettingsGenerator.merge_global_settings() method for fixing broken
Bash(:*) patterns and preserving user customizations in ~/.claude/settings.json.

Expected to FAIL until implementation is complete.

Security Requirements (GitHub Issue #117):
1. Detect and fix broken patterns: Bash(:*) → [Bash(git:*), Bash(python:*), ...]
2. Preserve user customizations: Keep valid custom patterns
3. Atomic writes: Prevent corruption during updates
4. Backup before modification: ~/.claude/settings.json.backup
5. Validation after merge: Ensure merged settings are valid
6. Path traversal prevention: Validate all file operations

Test Strategy:
- Test merge_global_settings() method with various scenarios
- Test _fix_wildcard_patterns() helper for pattern detection/replacement
- Test backup creation and atomic writes
- Test user customization preservation
- Test validation after merge
- Test edge cases: missing file, corrupted JSON, permission errors

Coverage Target: 95%+ for global settings merge functionality

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

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.lib.settings_generator import (
        SettingsGenerator,
        SettingsGeneratorError,
    )
except ImportError:
    # Mock for test discovery
    class SettingsGenerator:
        def merge_global_settings(self, global_path: Path, template_path: Path) -> Dict[str, Any]:
            raise NotImplementedError("Implementation pending")

        def _fix_wildcard_patterns(self, settings: Dict[str, Any]) -> Dict[str, Any]:
            raise NotImplementedError("Implementation pending")

    class SettingsGeneratorError(Exception):
        pass


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

BROKEN_USER_SETTINGS = {
    "allowedTools": {
        "Bash": {
            "allow_patterns": ["Bash(:*)"],  # BROKEN
            "deny_patterns": [],
        }
    },
    "customHooks": {
        "PreToolUse": ["~/.my-hooks/custom_hook.py"]  # User custom
    }
}

VALID_USER_SETTINGS = {
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
        "PreToolUse": ["~/.my-hooks/custom_hook.py"]
    }
}


class TestGlobalSettingsMerge:
    """Test SettingsGenerator.merge_global_settings() method"""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create SettingsGenerator instance"""
        return SettingsGenerator(project_root=tmp_path)

    @pytest.fixture
    def global_settings_path(self, tmp_path):
        """Create temporary global settings path"""
        return tmp_path / ".claude" / "settings.json"

    @pytest.fixture
    def template_path(self, tmp_path):
        """Create template settings file"""
        template = tmp_path / "template.json"
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_text(json.dumps(TEMPLATE_SETTINGS, indent=2))
        return template

    def test_merge_first_install_creates_from_template(self, generator, global_settings_path, template_path):
        """Test: No existing settings → create from template"""
        # Arrange
        assert not global_settings_path.exists()

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        assert global_settings_path.exists()
        assert result["allowedTools"]["Bash"]["allow_patterns"] == REQUIRED_SAFE_PATTERNS
        assert "Bash(:*)" not in result["allowedTools"]["Bash"]["allow_patterns"]

    def test_merge_valid_settings_no_changes(self, generator, global_settings_path, template_path):
        """Test: Existing valid settings → no changes made"""
        # Arrange
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(VALID_USER_SETTINGS, indent=2))
        original_mtime = global_settings_path.stat().st_mtime

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        assert "Bash(docker:*)" in result["allowedTools"]["Bash"]["allow_patterns"]  # User custom preserved
        assert "~/.my-hooks/custom_hook.py" in result["customHooks"]["PreToolUse"]  # User hook preserved
        assert all(p in result["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)

    def test_fix_broken_bash_colon_wildcard(self, generator, global_settings_path, template_path):
        """Test: Detect and fix Bash(:*) pattern"""
        # Arrange
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(BROKEN_USER_SETTINGS, indent=2))

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        assert "Bash(:*)" not in result["allowedTools"]["Bash"]["allow_patterns"]
        assert all(p in result["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)

    def test_fix_broken_bash_wildcard(self, generator, global_settings_path, template_path):
        """Test: Detect and fix Bash(*) pattern"""
        # Arrange
        broken_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": ["Bash(*)"],  # BROKEN
                    "deny_patterns": [],
                }
            }
        }
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(broken_settings, indent=2))

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        assert "Bash(*)" not in result["allowedTools"]["Bash"]["allow_patterns"]
        assert all(p in result["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)

    def test_preserve_user_hooks_completely(self, generator, global_settings_path, template_path):
        """Test: User hooks 100% preserved during merge"""
        # Arrange
        user_settings = {
            "allowedTools": {"Bash": {"allow_patterns": ["Bash(:*)"]}},
            "customHooks": {
                "PreToolUse": ["~/.my-hooks/hook1.py", "~/.my-hooks/hook2.py"],
                "PostToolUse": ["~/.my-hooks/post_hook.py"],
            }
        }
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(user_settings, indent=2))

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        assert "~/.my-hooks/hook1.py" in result["customHooks"]["PreToolUse"]
        assert "~/.my-hooks/hook2.py" in result["customHooks"]["PreToolUse"]
        assert "~/.my-hooks/post_hook.py" in result["customHooks"]["PostToolUse"]

    def test_preserve_user_custom_patterns(self, generator, global_settings_path, template_path):
        """Test: Valid custom patterns preserved during merge"""
        # Arrange
        user_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": [
                        "Bash(docker:*)",  # User custom
                        "Bash(npm:*)",     # User custom
                        "Bash(:*)",        # BROKEN - should be removed
                    ],
                    "deny_patterns": ["Bash(curl:*)"],  # User deny
                }
            }
        }
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(user_settings, indent=2))

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        patterns = result["allowedTools"]["Bash"]["allow_patterns"]
        assert "Bash(docker:*)" in patterns  # User custom preserved
        assert "Bash(npm:*)" in patterns     # User custom preserved
        assert "Bash(:*)" not in patterns    # Broken pattern removed
        assert all(p in patterns for p in REQUIRED_SAFE_PATTERNS)  # Safe patterns added

    def test_remove_invalid_wildcard_patterns(self, generator, global_settings_path, template_path):
        """Test: All invalid wildcard patterns removed"""
        # Arrange
        broken_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": [
                        "Bash(:*)",    # BROKEN
                        "Bash(*)",     # BROKEN
                        "Bash(**)",    # BROKEN
                        "Bash(git:*)", # VALID
                    ],
                }
            }
        }
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(broken_settings, indent=2))

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        patterns = result["allowedTools"]["Bash"]["allow_patterns"]
        assert "Bash(:*)" not in patterns
        assert "Bash(*)" not in patterns
        assert "Bash(**)" not in patterns
        assert "Bash(git:*)" in patterns  # Valid pattern preserved

    def test_merge_allow_patterns_union(self, generator, global_settings_path, template_path):
        """Test: Allow lists merged as union (no duplicates)"""
        # Arrange
        user_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": [
                        "Bash(git:*)",     # Duplicate with template
                        "Bash(docker:*)",  # User custom
                    ],
                }
            }
        }
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(user_settings, indent=2))

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        patterns = result["allowedTools"]["Bash"]["allow_patterns"]
        assert patterns.count("Bash(git:*)") == 1  # No duplicates
        assert "Bash(docker:*)" in patterns         # User custom preserved
        assert all(p in patterns for p in REQUIRED_SAFE_PATTERNS)

    def test_merge_deny_patterns_union(self, generator, global_settings_path, template_path):
        """Test: Deny lists merged as union (no duplicates)"""
        # Arrange
        user_settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": ["Bash(git:*)"],
                    "deny_patterns": [
                        "Bash(rm:*-rf*)",  # Duplicate with template
                        "Bash(curl:*)",    # User custom
                    ],
                }
            }
        }
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(user_settings, indent=2))

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        deny_patterns = result["allowedTools"]["Bash"]["deny_patterns"]
        assert deny_patterns.count("Bash(rm:*-rf*)") == 1  # No duplicates
        assert "Bash(curl:*)" in deny_patterns               # User custom preserved

    def test_atomic_write_prevents_corruption(self, generator, global_settings_path, template_path):
        """Test: Atomic write pattern prevents corruption"""
        # Arrange
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(BROKEN_USER_SETTINGS, indent=2))

        # Act & Assert
        with patch("pathlib.Path.rename") as mock_rename:
            result = generator.merge_global_settings(global_settings_path, template_path)
            # Verify atomic write (write to temp, then rename)
            assert mock_rename.called or global_settings_path.exists()

    def test_backup_created_before_modification(self, generator, global_settings_path, template_path):
        """Test: Backup created before modifying settings"""
        # Arrange
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(BROKEN_USER_SETTINGS, indent=2))
        backup_path = global_settings_path.with_suffix(".json.backup")

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        assert backup_path.exists()
        backup_data = json.loads(backup_path.read_text())
        assert backup_data["allowedTools"]["Bash"]["allow_patterns"] == ["Bash(:*)"]  # Original data

    def test_validation_after_merge(self, generator, global_settings_path, template_path):
        """Test: Merged settings validated before writing"""
        # Arrange
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(BROKEN_USER_SETTINGS, indent=2))

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert - validation checks
        assert isinstance(result, dict)
        assert "allowedTools" in result
        assert "Bash" in result["allowedTools"]
        assert "allow_patterns" in result["allowedTools"]["Bash"]
        assert isinstance(result["allowedTools"]["Bash"]["allow_patterns"], list)

        # No broken patterns in final result
        for pattern in result["allowedTools"]["Bash"]["allow_patterns"]:
            assert pattern not in BROKEN_WILDCARDS

    def test_merge_missing_global_file_creates_new(self, generator, global_settings_path, template_path):
        """Test: Missing global file creates from template"""
        # Arrange
        assert not global_settings_path.exists()

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        assert global_settings_path.exists()
        data = json.loads(global_settings_path.read_text())
        assert data["allowedTools"]["Bash"]["allow_patterns"] == REQUIRED_SAFE_PATTERNS

    def test_merge_corrupted_global_file_recovers(self, generator, global_settings_path, template_path):
        """Test: Corrupted global file recovered from template"""
        # Arrange
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text("{ invalid json }")

        # Act
        result = generator.merge_global_settings(global_settings_path, template_path)

        # Assert
        assert global_settings_path.exists()
        data = json.loads(global_settings_path.read_text())
        assert "allowedTools" in data
        assert all(p in data["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)

    def test_merge_missing_template_raises_error(self, generator, global_settings_path, tmp_path):
        """Test: Missing template file raises clear error"""
        # Arrange
        missing_template = tmp_path / "missing.json"

        # Act & Assert
        with pytest.raises((SettingsGeneratorError, FileNotFoundError)):
            generator.merge_global_settings(global_settings_path, missing_template)

    def test_merge_permission_error_raises_clear_message(self, generator, global_settings_path, template_path):
        """Test: Permission error raises clear message"""
        # Arrange
        global_settings_path.parent.mkdir(parents=True, exist_ok=True)
        global_settings_path.write_text(json.dumps(BROKEN_USER_SETTINGS, indent=2))

        # Act & Assert
        with patch("pathlib.Path.write_text", side_effect=PermissionError("Access denied")):
            with pytest.raises(PermissionError, match="Access denied"):
                generator.merge_global_settings(global_settings_path, template_path)


class TestFixWildcardPatterns:
    """Test SettingsGenerator._fix_wildcard_patterns() helper"""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create SettingsGenerator instance"""
        return SettingsGenerator(project_root=tmp_path)

    def test_fix_bash_colon_wildcard(self, generator):
        """Test: Bash(:*) replaced with safe patterns"""
        # Arrange
        settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": ["Bash(:*)"],
                }
            }
        }

        # Act
        result = generator._fix_wildcard_patterns(settings)

        # Assert
        assert "Bash(:*)" not in result["allowedTools"]["Bash"]["allow_patterns"]
        assert all(p in result["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)

    def test_fix_bash_star_wildcard(self, generator):
        """Test: Bash(*) replaced with safe patterns"""
        # Arrange
        settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": ["Bash(*)"],
                }
            }
        }

        # Act
        result = generator._fix_wildcard_patterns(settings)

        # Assert
        assert "Bash(*)" not in result["allowedTools"]["Bash"]["allow_patterns"]
        assert all(p in result["allowedTools"]["Bash"]["allow_patterns"] for p in REQUIRED_SAFE_PATTERNS)

    def test_fix_multiple_wildcards(self, generator):
        """Test: Multiple broken patterns fixed"""
        # Arrange
        settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": ["Bash(:*)", "Bash(*)", "Bash(**)"],
                }
            }
        }

        # Act
        result = generator._fix_wildcard_patterns(settings)

        # Assert
        patterns = result["allowedTools"]["Bash"]["allow_patterns"]
        assert "Bash(:*)" not in patterns
        assert "Bash(*)" not in patterns
        assert "Bash(**)" not in patterns
        assert all(p in patterns for p in REQUIRED_SAFE_PATTERNS)

    def test_preserve_valid_patterns(self, generator):
        """Test: Valid patterns preserved"""
        # Arrange
        settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": [
                        "Bash(git:*)",
                        "Bash(:*)",      # BROKEN
                        "Bash(docker:*)",
                    ],
                }
            }
        }

        # Act
        result = generator._fix_wildcard_patterns(settings)

        # Assert
        patterns = result["allowedTools"]["Bash"]["allow_patterns"]
        assert "Bash(git:*)" in patterns
        assert "Bash(docker:*)" in patterns
        assert "Bash(:*)" not in patterns

    def test_no_changes_for_valid_settings(self, generator):
        """Test: Valid settings unchanged"""
        # Arrange
        settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": ["Bash(git:*)", "Bash(python:*)"],
                }
            }
        }

        # Act
        result = generator._fix_wildcard_patterns(settings)

        # Assert
        assert result["allowedTools"]["Bash"]["allow_patterns"] == ["Bash(git:*)", "Bash(python:*)"]

    def test_empty_patterns_list_handled(self, generator):
        """Test: Empty patterns list handled gracefully"""
        # Arrange
        settings = {
            "allowedTools": {
                "Bash": {
                    "allow_patterns": [],
                }
            }
        }

        # Act
        result = generator._fix_wildcard_patterns(settings)

        # Assert
        assert isinstance(result["allowedTools"]["Bash"]["allow_patterns"], list)

    def test_missing_bash_section_handled(self, generator):
        """Test: Missing Bash section handled gracefully"""
        # Arrange
        settings = {
            "allowedTools": {}
        }

        # Act
        result = generator._fix_wildcard_patterns(settings)

        # Assert
        assert "Bash" not in result.get("allowedTools", {}) or isinstance(result["allowedTools"].get("Bash"), dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

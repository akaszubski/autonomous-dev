"""
Tests for strict documentation update enforcement.

Tests the detect_doc_changes.py hook that blocks commits when required
documentation updates are missing.
"""

import json
import pytest
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from detect_doc_changes import (
    match_pattern,
    find_required_docs,
    check_doc_updates,
    is_excluded
)


class TestPatternMatching:
    """Test pattern matching for code changes."""

    def test_command_pattern_match(self):
        """Test matching command files."""
        assert match_pattern("commands/test.md", "commands/*.md")
        assert match_pattern("commands/foo-bar.md", "commands/*.md")
        assert not match_pattern("commands/subdir/test.md", "commands/*.md")

    def test_skill_directory_pattern(self):
        """Test matching skill directories."""
        assert match_pattern("skills/my-skill/", "skills/*/")
        assert match_pattern("skills/my-skill/SKILL.md", "skills/*/")
        assert not match_pattern("skills/README.md", "skills/*/")

    def test_agent_pattern_match(self):
        """Test matching agent files."""
        assert match_pattern("agents/researcher.md", "agents/*.md")
        assert match_pattern("agents/test-master.md", "agents/*.md")
        assert not match_pattern("agents/README.md", "agents/*.md") is False  # This should match

    def test_hook_pattern_match(self):
        """Test matching hook files."""
        assert match_pattern("hooks/auto_test.py", "hooks/*.py")
        assert match_pattern("hooks/detect_doc_changes.py", "hooks/*.py")
        assert not match_pattern("hooks/README.md", "hooks/*.py")

    def test_wildcard_patterns(self):
        """Test various wildcard patterns."""
        assert match_pattern("templates/settings.json", "templates/*.json")
        assert match_pattern(".claude-plugin/plugin.json", ".claude-plugin/plugin.json")


class TestExclusions:
    """Test exclusion patterns."""

    def test_test_files_excluded(self):
        """Test files are excluded."""
        assert is_excluded("tests/test_foo.py", ["tests/**/*"])
        assert is_excluded("tests/unit/test_bar.py", ["tests/**/*"])

    def test_cache_files_excluded(self):
        """Cache files are excluded."""
        assert is_excluded(".claude/cache/foo.json", [".claude/cache/**/*"])
        assert is_excluded("__pycache__/foo.pyc", ["__pycache__/**/*"])

    def test_session_files_excluded(self):
        """Session files are excluded."""
        assert is_excluded("docs/sessions/session.log", ["docs/sessions/**/*"])

    def test_non_excluded_files(self):
        """Regular files are not excluded."""
        assert not is_excluded("commands/test.md", ["tests/**/*"])
        assert not is_excluded("README.md", ["tests/**/*"])


class TestRequiredDocsFinding:
    """Test finding required docs based on code changes."""

    def setup_method(self):
        """Setup test registry."""
        self.registry = {
            "mappings": [
                {
                    "code_pattern": "commands/*.md",
                    "required_docs": ["README.md", "QUICKSTART.md"],
                    "description": "Command changes require README update",
                    "suggestion": "Add command to README"
                },
                {
                    "code_pattern": "skills/*/",
                    "required_docs": ["README.md", ".claude-plugin/marketplace.json"],
                    "description": "Skill changes require count update",
                    "suggestion": "Update skill count"
                },
                {
                    "code_pattern": "agents/*.md",
                    "required_docs": ["README.md", ".claude-plugin/marketplace.json"],
                    "description": "Agent changes require count update",
                    "suggestion": "Update agent count"
                }
            ],
            "exclusions": ["tests/**/*", "docs/sessions/**/*"]
        }

    def test_command_addition_requires_docs(self):
        """Adding a command requires README and QUICKSTART updates."""
        staged_files = ["commands/new-feature.md"]
        required = find_required_docs(staged_files, self.registry)

        assert "commands/new-feature.md" in required
        assert "README.md" in required["commands/new-feature.md"]["docs"]
        assert "QUICKSTART.md" in required["commands/new-feature.md"]["docs"]

    def test_skill_addition_requires_docs(self):
        """Adding a skill requires README and marketplace.json updates."""
        staged_files = ["skills/my-new-skill/SKILL.md"]
        required = find_required_docs(staged_files, self.registry)

        assert "skills/my-new-skill/SKILL.md" in required
        assert "README.md" in required["skills/my-new-skill/SKILL.md"]["docs"]
        assert ".claude-plugin/marketplace.json" in required["skills/my-new-skill/SKILL.md"]["docs"]

    def test_agent_addition_requires_docs(self):
        """Adding an agent requires README and marketplace.json updates."""
        staged_files = ["agents/new-agent.md"]
        required = find_required_docs(staged_files, self.registry)

        assert "agents/new-agent.md" in required
        assert "README.md" in required["agents/new-agent.md"]["docs"]

    def test_excluded_files_not_checked(self):
        """Excluded files don't trigger doc requirements."""
        staged_files = ["tests/test_new_feature.py"]
        required = find_required_docs(staged_files, self.registry)

        assert len(required) == 0

    def test_unrelated_files_no_requirements(self):
        """Files not matching any pattern have no requirements."""
        staged_files = ["src/utils.py", "scripts/helper.sh"]
        required = find_required_docs(staged_files, self.registry)

        assert len(required) == 0


class TestDocUpdateChecking:
    """Test checking if required docs are updated."""

    def test_all_docs_updated_passes(self):
        """Commit allowed when all required docs are updated."""
        required_docs_map = {
            "commands/new-feature.md": {
                "docs": {"README.md", "QUICKSTART.md"},
                "description": "Test",
                "suggestion": "Test"
            }
        }
        staged_files = {"commands/new-feature.md", "README.md", "QUICKSTART.md"}

        all_updated, violations = check_doc_updates(required_docs_map, staged_files)

        assert all_updated is True
        assert len(violations) == 0

    def test_missing_docs_fails(self):
        """Commit blocked when required docs are missing."""
        required_docs_map = {
            "commands/new-feature.md": {
                "docs": {"README.md", "QUICKSTART.md"},
                "description": "Command requires docs",
                "suggestion": "Update README"
            }
        }
        staged_files = {"commands/new-feature.md", "README.md"}  # Missing QUICKSTART.md

        all_updated, violations = check_doc_updates(required_docs_map, staged_files)

        assert all_updated is False
        assert len(violations) == 1
        assert violations[0]["code_file"] == "commands/new-feature.md"
        assert "QUICKSTART.md" in violations[0]["missing_docs"]

    def test_multiple_files_multiple_requirements(self):
        """Multiple code changes with different doc requirements."""
        required_docs_map = {
            "commands/feature-a.md": {
                "docs": {"README.md", "QUICKSTART.md"},
                "description": "Test",
                "suggestion": "Test"
            },
            "skills/new-skill/SKILL.md": {
                "docs": {"README.md", ".claude-plugin/marketplace.json"},
                "description": "Test",
                "suggestion": "Test"
            }
        }
        staged_files = {
            "commands/feature-a.md",
            "skills/new-skill/SKILL.md",
            "README.md",
            "QUICKSTART.md"
            # Missing .claude-plugin/marketplace.json
        }

        all_updated, violations = check_doc_updates(required_docs_map, staged_files)

        assert all_updated is False
        assert len(violations) == 1
        assert violations[0]["code_file"] == "skills/new-skill/SKILL.md"
        assert ".claude-plugin/marketplace.json" in violations[0]["missing_docs"]

    def test_partial_doc_updates_fail(self):
        """Partial doc updates should fail (all or nothing)."""
        required_docs_map = {
            "commands/new-feature.md": {
                "docs": {"README.md", "QUICKSTART.md", "COMMANDS.md"},
                "description": "Test",
                "suggestion": "Test"
            }
        }
        staged_files = {"commands/new-feature.md", "README.md"}  # Only 1 of 3 docs

        all_updated, violations = check_doc_updates(required_docs_map, staged_files)

        assert all_updated is False
        assert len(violations) == 1
        assert set(violations[0]["missing_docs"]) == {"QUICKSTART.md", "COMMANDS.md"}


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def setup_method(self):
        """Setup realistic registry."""
        self.registry = {
            "mappings": [
                {
                    "code_pattern": "commands/*.md",
                    "required_docs": ["README.md", "QUICKSTART.md"],
                    "description": "Commands require README",
                    "suggestion": "Add to command list"
                },
                {
                    "code_pattern": "skills/*/",
                    "required_docs": ["README.md", ".claude-plugin/marketplace.json"],
                    "description": "Skills require count update",
                    "suggestion": "Update skill count"
                },
                {
                    "code_pattern": ".claude-plugin/plugin.json",
                    "required_docs": ["README.md", "plugins/autonomous-dev/docs/UPDATES.md"],
                    "description": "Version bump requires release notes",
                    "suggestion": "Add to UPDATES.md"
                }
            ],
            "exclusions": ["tests/**/*"]
        }

    def test_new_command_workflow(self):
        """Simul developer adds new command."""
        # Step 1: Developer adds command but forgets docs
        staged_files = {"commands/new-feature.md"}
        required = find_required_docs(list(staged_files), self.registry)
        all_updated, violations = check_doc_updates(required, staged_files)

        assert all_updated is False
        assert len(violations) == 1

        # Step 2: Developer adds all required docs
        staged_files.update(["README.md", "QUICKSTART.md"])
        all_updated, violations = check_doc_updates(required, staged_files)

        assert all_updated is True
        assert len(violations) == 0

    def test_version_bump_workflow(self):
        """Simulate version bump requiring release notes."""
        staged_files = {".claude-plugin/plugin.json"}
        required = find_required_docs(list(staged_files), self.registry)
        all_updated, violations = check_doc_updates(required, staged_files)

        assert all_updated is False
        assert "plugins/autonomous-dev/docs/UPDATES.md" in violations[0]["missing_docs"]

        # Add release notes
        staged_files.update(["README.md", "plugins/autonomous-dev/docs/UPDATES.md"])
        all_updated, violations = check_doc_updates(required, staged_files)

        assert all_updated is True

    def test_unrelated_code_changes_pass(self):
        """Unrelated code changes don't require doc updates."""
        staged_files = ["src/utils.py", "scripts/helper.sh"]
        required = find_required_docs(staged_files, self.registry)

        assert len(required) == 0

    def test_test_file_changes_ignored(self):
        """Test file changes are ignored (excluded)."""
        staged_files = ["tests/test_new_feature.py"]
        required = find_required_docs(staged_files, self.registry)

        assert len(required) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

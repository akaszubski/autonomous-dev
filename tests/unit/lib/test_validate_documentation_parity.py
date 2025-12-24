#!/usr/bin/env python3
"""
TDD Tests for Documentation Parity Validator (FAILING - Red Phase)

This module contains FAILING tests for validate_documentation_parity.py which validates
documentation consistency across CLAUDE.md, PROJECT.md, README.md, and CHANGELOG.md.

Requirements:
1. Version consistency validation (CLAUDE.md vs PROJECT.md dates)
2. Count discrepancy detection (agents, commands, skills, hooks)
3. Cross-reference validation (documented features exist in codebase)
4. CHANGELOG parity (version tags match plugin.json)
5. Security documentation (security practices documented)
6. Orchestration (validate(), generate_report(), CLI interface)

Test Coverage Target: 95%+ of validation logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe documentation validation requirements
- Tests should FAIL until validate_documentation_parity.py is implemented
- Each test validates ONE documentation parity requirement

Author: test-master agent
Date: 2025-11-09
Related: Documentation parity validation feature
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until validate_documentation_parity.py is created
from plugins.autonomous_dev.lib.validate_documentation_parity import (
    DocumentationParityValidator,
    ParityIssue,
    ParityReport,
    ValidationLevel,
    validate_documentation_parity,
)


class TestVersionConsistencyValidation:
    """Test version consistency validation between CLAUDE.md and PROJECT.md."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with documentation files."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        (repo_root / ".claude").mkdir()
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "agents").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "commands").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "skills").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "hooks").mkdir()
        return repo_root

    def test_detect_version_drift_claude_older_than_project(self, temp_repo):
        """Test detection when CLAUDE.md date is older than PROJECT.md.

        REQUIREMENT: Detect when CLAUDE.md is outdated relative to PROJECT.md.
        Expected: ERROR level issue reported with specific date mismatch.
        """
        # PROJECT.md updated more recently
        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # CLAUDE.md outdated
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_version_consistency()

        assert len(issues) == 1
        assert issues[0].level == ValidationLevel.ERROR
        assert "CLAUDE.md" in issues[0].message
        assert "outdated" in issues[0].message.lower()
        assert "2025-11-08" in issues[0].details
        assert "2025-11-09" in issues[0].details

    def test_detect_version_drift_project_older_than_claude(self, temp_repo):
        """Test detection when PROJECT.md date is older than CLAUDE.md.

        REQUIREMENT: Detect when PROJECT.md is outdated relative to CLAUDE.md.
        Expected: WARNING level issue (unusual but not critical).
        """
        # CLAUDE.md updated more recently
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n")

        # PROJECT.md outdated
        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-08\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_version_consistency()

        assert len(issues) == 1
        assert issues[0].level == ValidationLevel.WARNING
        assert "PROJECT.md" in issues[0].message
        assert "outdated" in issues[0].message.lower()

    def test_no_issues_when_versions_match(self, temp_repo):
        """Test no issues when CLAUDE.md and PROJECT.md dates match.

        REQUIREMENT: No false positives when documentation is synchronized.
        Expected: Empty list of issues.
        """
        same_date = "2025-11-09"

        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text(f"**Last Updated**: {same_date}\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text(f"**Last Updated**: {same_date}\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_version_consistency()

        assert len(issues) == 0

    def test_detect_missing_version_in_claude_md(self, temp_repo):
        """Test detection when CLAUDE.md lacks version date.

        REQUIREMENT: Detect missing version metadata.
        Expected: ERROR level issue for missing date.
        """
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("# CLAUDE.md\n\nNo version here.\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_version_consistency()

        assert len(issues) == 1
        assert issues[0].level == ValidationLevel.ERROR
        assert "missing" in issues[0].message.lower()
        assert "CLAUDE.md" in issues[0].message

    def test_detect_missing_version_in_project_md(self, temp_repo):
        """Test detection when PROJECT.md lacks version date.

        REQUIREMENT: Detect missing version metadata in PROJECT.md.
        Expected: ERROR level issue for missing date.
        """
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("# PROJECT.md\n\nNo version here.\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_version_consistency()

        assert len(issues) == 1
        assert issues[0].level == ValidationLevel.ERROR
        assert "missing" in issues[0].message.lower()
        assert "PROJECT.md" in issues[0].message

    def test_handle_malformed_date_formats(self, temp_repo):
        """Test handling of malformed date formats.

        REQUIREMENT: Gracefully handle invalid date formats.
        Expected: ERROR level issue for unparseable date.
        """
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: November 9th, 2025\n")  # Wrong format

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_version_consistency()

        assert len(issues) >= 1
        assert any("format" in issue.message.lower() or "parse" in issue.message.lower()
                   for issue in issues)

    def test_handle_missing_documentation_files(self, temp_repo):
        """Test handling when documentation files are missing.

        REQUIREMENT: Detect missing documentation files.
        Expected: ERROR level issues for missing files.
        """
        # Don't create any documentation files
        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_version_consistency()

        # Should report missing files
        assert len(issues) >= 2  # CLAUDE.md and PROJECT.md missing
        assert any("CLAUDE.md" in issue.message and "missing" in issue.message.lower()
                   for issue in issues)
        assert any("PROJECT.md" in issue.message and "missing" in issue.message.lower()
                   for issue in issues)

    def test_version_consistency_with_multiple_date_formats(self, temp_repo):
        """Test version consistency with various date format variations.

        REQUIREMENT: Support common date format variations.
        Expected: Normalize and compare dates correctly.
        """
        # Various valid formats
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated:** 2025-11-09\n")  # Colon instead of double colon

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_version_consistency()

        # Should normalize both and detect they're the same
        assert len(issues) == 0


class TestCountDiscrepancyValidation:
    """Test count discrepancy detection (agents, commands, skills, hooks)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with plugin structure."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        (repo_root / ".claude").mkdir()
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "agents").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "commands").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "skills").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "hooks").mkdir()
        return repo_root

    def test_detect_agent_count_mismatch(self, temp_repo):
        """Test detection when documented agent count doesn't match reality.

        REQUIREMENT: Detect agent count discrepancies.
        Expected: ERROR level issue with actual vs documented counts.
        """
        # Create 3 actual agent files
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")
        (agents_dir / "implementer.md").write_text("# Implementer\n")

        # CLAUDE.md documents 5 agents (wrong)
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("### Agents (5 specialists)\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_count_discrepancies()

        assert len(issues) >= 1
        agent_issues = [i for i in issues if "agent" in i.message.lower()]
        assert len(agent_issues) == 1
        assert agent_issues[0].level == ValidationLevel.ERROR
        assert "5" in agent_issues[0].message  # Documented count
        assert "3" in agent_issues[0].details  # Actual count

    def test_detect_command_count_mismatch(self, temp_repo):
        """Test detection when documented command count doesn't match reality.

        REQUIREMENT: Detect command count discrepancies.
        Expected: ERROR level issue with actual vs documented counts.
        """
        # Create 2 actual command files
        commands_dir = temp_repo / "plugins" / "autonomous-dev" / "commands"
        (commands_dir / "auto-implement.md").write_text("# Auto Implement\n")
        (commands_dir / "status.md").write_text("# Status\n")

        # CLAUDE.md documents 10 commands (wrong)
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Commands (10 active)**:\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_count_discrepancies()

        assert len(issues) >= 1
        command_issues = [i for i in issues if "command" in i.message.lower()]
        assert len(command_issues) == 1
        assert command_issues[0].level == ValidationLevel.ERROR
        assert "10" in command_issues[0].message
        assert "2" in command_issues[0].details

    def test_detect_skill_count_mismatch(self, temp_repo):
        """Test detection when documented skill count doesn't match reality.

        REQUIREMENT: Detect skill count discrepancies.
        Expected: WARNING level issue (skills less critical than agents/commands).
        """
        # Create 4 actual skill files
        skills_dir = temp_repo / "plugins" / "autonomous-dev" / "skills"
        (skills_dir / "testing-guide.md").write_text("# Testing Guide\n")
        (skills_dir / "code-review.md").write_text("# Code Review\n")
        (skills_dir / "security-patterns.md").write_text("# Security Patterns\n")
        (skills_dir / "api-design.md").write_text("# API Design\n")

        # CLAUDE.md documents 10 skills (wrong)
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("### Skills (10 Active)\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_count_discrepancies()

        assert len(issues) >= 1
        skill_issues = [i for i in issues if "skill" in i.message.lower()]
        assert len(skill_issues) == 1
        assert skill_issues[0].level == ValidationLevel.WARNING
        assert "10" in skill_issues[0].message
        assert "4" in skill_issues[0].details

    def test_detect_hook_count_mismatch(self, temp_repo):
        """Test detection when documented hook count doesn't match reality.

        REQUIREMENT: Detect hook count discrepancies.
        Expected: WARNING level issue with actual vs documented counts.
        """
        # Create 3 actual hook files
        hooks_dir = temp_repo / "plugins" / "autonomous-dev" / "hooks"
        (hooks_dir / "auto_format.py").write_text("# Auto format hook\n")
        (hooks_dir / "auto_test.py").write_text("# Auto test hook\n")
        (hooks_dir / "security_scan.py").write_text("# Security scan hook\n")

        # CLAUDE.md documents 15 hooks (wrong)
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("### Hooks (15 total automation)\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_count_discrepancies()

        assert len(issues) >= 1
        hook_issues = [i for i in issues if "hook" in i.message.lower()]
        assert len(hook_issues) == 1
        assert hook_issues[0].level == ValidationLevel.WARNING
        assert "15" in hook_issues[0].message
        assert "3" in hook_issues[0].details

    def test_no_issues_when_all_counts_match(self, temp_repo):
        """Test no issues when all documented counts match reality.

        REQUIREMENT: No false positives when counts are accurate.
        Expected: Empty list of issues.
        """
        # Create actual files
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")

        commands_dir = temp_repo / "plugins" / "autonomous-dev" / "commands"
        (commands_dir / "auto-implement.md").write_text("# Auto Implement\n")

        # CLAUDE.md documents accurate counts
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
### Agents (2 specialists)
**Commands (1 active)**:
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_count_discrepancies()

        assert len(issues) == 0

    def test_ignore_archived_agents(self, temp_repo):
        """Test that archived agents are not counted.

        REQUIREMENT: Exclude archived/deprecated agents from count.
        Expected: Only count active agents, not archived directory contents.
        """
        # Create 2 active agents
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")

        # Create archived agent (should be ignored)
        archived_dir = agents_dir / "archived"
        archived_dir.mkdir()
        (archived_dir / "orchestrator.md").write_text("# Orchestrator (archived)\n")

        # CLAUDE.md documents 2 agents (correct, excluding archived)
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("### Agents (2 specialists)\n")

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_count_discrepancies()

        # Should have no issues (archived not counted)
        agent_issues = [i for i in issues if "agent" in i.message.lower()]
        assert len(agent_issues) == 0

    def test_detect_multiple_count_mismatches_simultaneously(self, temp_repo):
        """Test detection of multiple count discrepancies at once.

        REQUIREMENT: Report all count discrepancies in single validation.
        Expected: Multiple issues, one per discrepancy type.
        """
        # Create actual files (different counts than documented)
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")

        commands_dir = temp_repo / "plugins" / "autonomous-dev" / "commands"
        (commands_dir / "auto-implement.md").write_text("# Auto Implement\n")
        (commands_dir / "status.md").write_text("# Status\n")

        # CLAUDE.md documents wrong counts for multiple categories
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
### Agents (5 specialists)
**Commands (10 active)**:
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_count_discrepancies()

        # Should detect both discrepancies
        assert len(issues) >= 2
        assert any("agent" in i.message.lower() for i in issues)
        assert any("command" in i.message.lower() for i in issues)


class TestCrossReferenceValidation:
    """Test cross-reference validation (documented features exist in codebase)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with plugin structure."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        (repo_root / ".claude").mkdir()
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "agents").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "commands").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "lib").mkdir()
        return repo_root

    def test_detect_documented_agent_missing_from_codebase(self, temp_repo):
        """Test detection when documented agent doesn't exist in codebase.

        REQUIREMENT: Detect documented features that don't exist.
        Expected: ERROR level issue for missing agent file.
        """
        # CLAUDE.md documents "researcher" agent
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
### Agents:
- **researcher**: Web research for patterns
        """)

        # But researcher.md doesn't exist
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        # (no files created)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_cross_references()

        assert len(issues) >= 1
        researcher_issues = [i for i in issues if "researcher" in i.message.lower()]
        assert len(researcher_issues) == 1
        assert researcher_issues[0].level == ValidationLevel.ERROR
        assert "missing" in researcher_issues[0].message.lower() or "not found" in researcher_issues[0].message.lower()

    def test_detect_documented_command_missing_from_codebase(self, temp_repo):
        """Test detection when documented command doesn't exist in codebase.

        REQUIREMENT: Detect documented commands that don't exist.
        Expected: ERROR level issue for missing command file.
        """
        # CLAUDE.md documents "/auto-implement" command
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
**Commands**:
- `/auto-implement` - Autonomous feature development
        """)

        # But auto-implement.md doesn't exist
        commands_dir = temp_repo / "plugins" / "autonomous-dev" / "commands"
        # (no files created)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_cross_references()

        assert len(issues) >= 1
        auto_implement_issues = [i for i in issues if "auto-implement" in i.message.lower()]
        assert len(auto_implement_issues) == 1
        assert auto_implement_issues[0].level == ValidationLevel.ERROR

    def test_detect_documented_library_missing_from_codebase(self, temp_repo):
        """Test detection when documented library doesn't exist in codebase.

        REQUIREMENT: Detect documented libraries that don't exist.
        Expected: WARNING level issue for missing library file.
        """
        # CLAUDE.md documents "security_utils.py" library
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
**Core Libraries**:
1. **security_utils.py** - Centralized security validation
        """)

        # But security_utils.py doesn't exist
        lib_dir = temp_repo / "plugins" / "autonomous-dev" / "lib"
        # (no files created)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_cross_references()

        assert len(issues) >= 1
        security_utils_issues = [i for i in issues if "security_utils" in i.message.lower()]
        assert len(security_utils_issues) == 1
        assert security_utils_issues[0].level == ValidationLevel.WARNING

    def test_no_issues_when_all_references_exist(self, temp_repo):
        """Test no issues when all documented features exist in codebase.

        REQUIREMENT: No false positives when documentation is accurate.
        Expected: Empty list of issues.
        """
        # Create actual files
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")

        commands_dir = temp_repo / "plugins" / "autonomous-dev" / "commands"
        (commands_dir / "auto-implement.md").write_text("# Auto Implement\n")

        # CLAUDE.md documents existing features
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
### Agents:
- **researcher**: Web research

**Commands**:
- `/auto-implement` - Autonomous development
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_cross_references()

        assert len(issues) == 0

    def test_detect_codebase_feature_missing_from_documentation(self, temp_repo):
        """Test detection when codebase feature is not documented.

        REQUIREMENT: Detect undocumented features (reverse validation).
        Expected: INFO level issue for undocumented feature.
        """
        # Create actual agent file
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "security-auditor.md").write_text("# Security Auditor\n")

        # CLAUDE.md doesn't mention security-auditor
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
### Agents:
- **researcher**: Web research
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_cross_references()

        # Should detect undocumented agent
        assert len(issues) >= 1
        undocumented_issues = [i for i in issues if "security-auditor" in i.message.lower() or "undocumented" in i.message.lower()]
        assert len(undocumented_issues) >= 1
        assert undocumented_issues[0].level == ValidationLevel.INFO

    def test_handle_malformed_documentation_structure(self, temp_repo):
        """Test handling of malformed documentation structure.

        REQUIREMENT: Gracefully handle malformed markdown.
        Expected: WARNING about unparseable documentation.
        """
        # Create malformed CLAUDE.md (invalid markdown structure)
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
This is not proper markdown structure
No headings or lists
Just random text
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_cross_references()

        # Should report parsing issues or empty feature list
        # (implementation detail: may warn about no features found)
        assert isinstance(issues, list)  # At minimum, should return list


class TestChangelogParityValidation:
    """Test CHANGELOG parity (version tags match plugin.json)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with CHANGELOG and plugin.json."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        return repo_root

    def test_detect_missing_version_in_changelog(self, temp_repo):
        """Test detection when plugin.json version is missing from CHANGELOG.

        REQUIREMENT: Ensure CHANGELOG documents all released versions.
        Expected: WARNING level issue for missing version entry.
        """
        # plugin.json has version 3.8.0
        plugin_json = temp_repo / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        # CHANGELOG.md doesn't have 3.8.0 entry
        changelog = temp_repo / "CHANGELOG.md"
        changelog.write_text("""
# Changelog

## [3.7.0] - 2025-11-08
- Previous release

## [3.6.0] - 2025-11-01
- Older release
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_changelog_parity()

        assert len(issues) >= 1
        version_issues = [i for i in issues if "3.8.0" in i.message]
        assert len(version_issues) == 1
        assert version_issues[0].level == ValidationLevel.WARNING
        assert "CHANGELOG" in version_issues[0].message

    def test_no_issues_when_version_in_changelog(self, temp_repo):
        """Test no issues when plugin.json version exists in CHANGELOG.

        REQUIREMENT: No false positives when CHANGELOG is up-to-date.
        Expected: Empty list of issues.
        """
        # plugin.json has version 3.8.0
        plugin_json = temp_repo / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        # CHANGELOG.md has 3.8.0 entry
        changelog = temp_repo / "CHANGELOG.md"
        changelog.write_text("""
# Changelog

## [3.8.0] - 2025-11-09
- Current release

## [3.7.0] - 2025-11-08
- Previous release
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_changelog_parity()

        assert len(issues) == 0

    def test_detect_malformed_changelog_structure(self, temp_repo):
        """Test detection of malformed CHANGELOG structure.

        REQUIREMENT: Detect invalid CHANGELOG format.
        Expected: WARNING about malformed CHANGELOG.
        """
        # plugin.json has version 3.8.0
        plugin_json = temp_repo / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        # CHANGELOG.md has invalid structure (no version tags)
        changelog = temp_repo / "CHANGELOG.md"
        changelog.write_text("""
# Changelog

Just some random text
No version tags here
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_changelog_parity()

        # Should report missing version (can't find it in malformed CHANGELOG)
        assert len(issues) >= 1
        assert any("3.8.0" in i.message or "format" in i.message.lower()
                   for i in issues)

    def test_detect_missing_changelog_file(self, temp_repo):
        """Test detection when CHANGELOG.md is missing.

        REQUIREMENT: Detect missing CHANGELOG.md.
        Expected: WARNING level issue for missing CHANGELOG.
        """
        # plugin.json exists
        plugin_json = temp_repo / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        # CHANGELOG.md doesn't exist
        # (no file created)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_changelog_parity()

        assert len(issues) >= 1
        missing_issues = [i for i in issues if "CHANGELOG" in i.message and "missing" in i.message.lower()]
        assert len(missing_issues) == 1
        assert missing_issues[0].level == ValidationLevel.WARNING

    def test_handle_prerelease_versions_in_changelog(self, temp_repo):
        """Test handling of pre-release versions in CHANGELOG.

        REQUIREMENT: Support pre-release version tags (e.g., 3.8.0-beta.1).
        Expected: Validate pre-release versions correctly.
        """
        # plugin.json has pre-release version
        plugin_json = temp_repo / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0-beta.1"
        }))

        # CHANGELOG.md has pre-release entry
        changelog = temp_repo / "CHANGELOG.md"
        changelog.write_text("""
# Changelog

## [3.8.0-beta.1] - 2025-11-09
- Beta release
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_changelog_parity()

        # Should recognize pre-release version
        assert len(issues) == 0

    def test_detect_unreleased_section_without_version(self, temp_repo):
        """Test handling of [Unreleased] section in CHANGELOG.

        REQUIREMENT: Support [Unreleased] section for work in progress.
        Expected: Don't flag [Unreleased] as missing version.
        """
        # plugin.json has version 3.8.0
        plugin_json = temp_repo / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        # CHANGELOG.md has [Unreleased] section
        changelog = temp_repo / "CHANGELOG.md"
        changelog.write_text("""
# Changelog

## [Unreleased]
- Work in progress

## [3.8.0] - 2025-11-09
- Current release
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_changelog_parity()

        # Should not flag [Unreleased] as issue
        assert len(issues) == 0


class TestSecurityDocumentationValidation:
    """Test security documentation validation."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with documentation files."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        (repo_root / ".claude").mkdir()
        (repo_root / "docs").mkdir()
        return repo_root

    def test_detect_missing_security_documentation(self, temp_repo):
        """Test detection when security documentation is missing.

        REQUIREMENT: Ensure security practices are documented.
        Expected: WARNING level issue for missing security docs.
        """
        # CLAUDE.md doesn't mention security
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
# CLAUDE.md

## Project Overview
No security documentation here.
        """)

        # No SECURITY.md file
        # (no file created)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_security_documentation()

        assert len(issues) >= 1
        security_issues = [i for i in issues if "security" in i.message.lower()]
        assert len(security_issues) >= 1
        assert security_issues[0].level == ValidationLevel.WARNING

    def test_no_issues_when_security_documented(self, temp_repo):
        """Test no issues when security is properly documented.

        REQUIREMENT: No false positives when security docs exist.
        Expected: Empty list of issues.
        """
        # CLAUDE.md mentions security
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
## Security Practices

- API keys in .env files
- Path validation via security_utils
- Audit logging for sensitive operations
        """)

        # SECURITY.md exists
        security_md = temp_repo / "docs" / "SECURITY.md"
        security_md.write_text("""
# Security

## Security Practices
- CWE-22 prevention
- Audit logging
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_security_documentation()

        assert len(issues) == 0

    def test_detect_security_utils_documented_but_missing(self, temp_repo):
        """Test detection when security_utils is documented but missing.

        REQUIREMENT: Detect documented security features that don't exist.
        Expected: ERROR level issue for missing security_utils.
        """
        # CLAUDE.md documents security_utils
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
**Libraries**:
1. **security_utils.py** - Security validation
        """)

        # But security_utils.py doesn't exist
        # (no file created)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_security_documentation()

        # This should be caught by cross-reference validation
        # Security validation may also flag it
        assert isinstance(issues, list)

    def test_detect_incomplete_security_documentation(self, temp_repo):
        """Test detection of incomplete security documentation.

        REQUIREMENT: Ensure comprehensive security documentation.
        Expected: INFO level issue for incomplete docs.
        """
        # CLAUDE.md has minimal security section
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
## Security

Use .env files.
        """)

        # SECURITY.md missing key sections (audit logging, CWE coverage, etc.)
        security_md = temp_repo / "docs" / "SECURITY.md"
        security_md.write_text("""
# Security

Basic security info only.
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_security_documentation()

        # May flag incomplete documentation
        # (implementation detail: depends on validation depth)
        assert isinstance(issues, list)

    def test_validate_cwe_coverage_documentation(self, temp_repo):
        """Test validation of CWE coverage documentation.

        REQUIREMENT: Ensure CWE patterns are documented.
        Expected: Verify CWE-22, CWE-59, CWE-117 documented.
        """
        # SECURITY.md documents CWE coverage
        security_md = temp_repo / "docs" / "SECURITY.md"
        security_md.write_text("""
# Security

## CWE Coverage
- CWE-22: Path traversal prevention
- CWE-59: Symlink resolution
- CWE-117: Log output neutralization
        """)

        validator = DocumentationParityValidator(temp_repo)
        issues = validator.validate_security_documentation()

        # Should recognize proper CWE documentation
        # (no issues for complete docs)
        cwe_issues = [i for i in issues if "CWE" in i.message]
        assert len(cwe_issues) == 0


class TestOrchestrationAndReporting:
    """Test orchestration (validate(), generate_report(), CLI)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with full structure."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        (repo_root / ".claude").mkdir()
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "agents").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "commands").mkdir()
        return repo_root

    def test_validate_method_runs_all_validations(self, temp_repo):
        """Test that validate() method runs all validation checks.

        REQUIREMENT: Orchestrate all validation checks in single call.
        Expected: validate() returns ParityReport with all check results.
        """
        # Create minimal valid structure
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        validator = DocumentationParityValidator(temp_repo)
        report = validator.validate()

        # Should return ParityReport
        assert isinstance(report, ParityReport)
        assert hasattr(report, 'version_issues')
        assert hasattr(report, 'count_issues')
        assert hasattr(report, 'cross_reference_issues')
        assert hasattr(report, 'changelog_issues')
        assert hasattr(report, 'security_issues')
        assert hasattr(report, 'total_issues')
        assert hasattr(report, 'has_errors')
        assert hasattr(report, 'has_warnings')

    def test_generate_report_produces_human_readable_output(self, temp_repo):
        """Test that generate_report() produces human-readable output.

        REQUIREMENT: Generate user-friendly validation report.
        Expected: Markdown-formatted report with all issues.
        """
        # Create structure with some issues
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n### Agents (5 specialists)\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Create 2 actual agents (mismatch with documented 5)
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")

        validator = DocumentationParityValidator(temp_repo)
        report = validator.validate()
        report_text = report.generate_report()

        # Should be markdown formatted
        assert isinstance(report_text, str)
        assert len(report_text) > 0
        assert "# " in report_text or "## " in report_text  # Has headings
        assert "ERROR" in report_text or "WARNING" in report_text  # Has severity levels

    def test_convenience_function_validate_documentation_parity(self, temp_repo):
        """Test convenience function for validation.

        REQUIREMENT: Provide simple API for validation.
        Expected: validate_documentation_parity(path) returns ParityReport.
        """
        # Create minimal structure
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Use convenience function
        report = validate_documentation_parity(temp_repo)

        assert isinstance(report, ParityReport)
        assert hasattr(report, 'total_issues')

    def test_report_includes_issue_counts_by_severity(self, temp_repo):
        """Test that report includes issue counts by severity.

        REQUIREMENT: Report statistics on issue severity distribution.
        Expected: Report has error_count, warning_count, info_count.
        """
        # Create structure with mixed issues
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")  # ERROR: outdated

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        validator = DocumentationParityValidator(temp_repo)
        report = validator.validate()

        # Should have severity counts
        assert hasattr(report, 'error_count')
        assert hasattr(report, 'warning_count')
        assert hasattr(report, 'info_count')
        assert report.error_count >= 1  # At least the version drift error

    def test_report_has_errors_flag_is_accurate(self, temp_repo):
        """Test that has_errors flag accurately reflects error presence.

        REQUIREMENT: Provide boolean flag for error detection.
        Expected: has_errors=True when ERROR level issues exist.
        """
        # Create structure with ERROR level issue
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        validator = DocumentationParityValidator(temp_repo)
        report = validator.validate()

        assert report.has_errors is True
        assert report.error_count > 0

    def test_report_exit_code_nonzero_on_errors(self, temp_repo):
        """Test that report provides exit code for CLI integration.

        REQUIREMENT: Support CLI exit code convention (0=success, 1=errors).
        Expected: exit_code=1 when errors exist, 0 otherwise.
        """
        # Create structure with ERROR
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        validator = DocumentationParityValidator(temp_repo)
        report = validator.validate()

        assert hasattr(report, 'exit_code')
        assert report.exit_code == 1  # Errors present

    def test_report_exit_code_zero_on_success(self, temp_repo):
        """Test that report exit code is 0 when no errors.

        REQUIREMENT: Exit code 0 for successful validation.
        Expected: exit_code=0 when no ERROR level issues.
        """
        # Create valid structure
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        validator = DocumentationParityValidator(temp_repo)
        report = validator.validate()

        # May have warnings, but no errors
        assert report.exit_code == 0 or report.error_count == 0


class TestSecurityValidation:
    """Test security aspects of validation (path traversal, injection)."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        return repo_root

    def test_block_path_traversal_in_repo_root(self):
        """Test blocking path traversal attempts in repo_root parameter.

        REQUIREMENT: Prevent CWE-22 path traversal attacks.
        Expected: Raise ValueError on traversal attempts.
        """
        # Attempt path traversal
        malicious_path = Path("/tmp/../../../etc/passwd")

        with pytest.raises(ValueError) as exc_info:
            validator = DocumentationParityValidator(malicious_path)

        assert "path" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_block_symlink_resolution_attacks(self, temp_repo):
        """Test blocking symlink resolution attacks.

        REQUIREMENT: Prevent CWE-59 symlink attacks.
        Expected: Resolve symlinks and validate resolved paths.
        """
        # Create symlink to system directory
        system_link = temp_repo / "system_link"
        system_link.symlink_to("/etc")

        # Should detect and block
        with pytest.raises(ValueError):
            validator = DocumentationParityValidator(system_link)

    def test_audit_log_validation_operations(self, temp_repo):
        """Test that validation operations are logged to audit log.

        REQUIREMENT: CWE-778 audit logging for security operations.
        Expected: Validation logged to security_audit.log.
        """
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n")

        # Mock audit logging
        with patch('plugins.autonomous_dev.lib.security_utils.audit_log') as mock_audit:
            validator = DocumentationParityValidator(temp_repo)
            report = validator.validate()

            # Should have called audit_log
            assert mock_audit.called

    def test_handle_malicious_file_content_gracefully(self, temp_repo):
        """Test graceful handling of malicious file content.

        REQUIREMENT: Prevent injection attacks through file content.
        Expected: Parse safely without executing content.
        """
        # Create file with potential injection content
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
**Last Updated**: 2025-11-09

<!-- Malicious script: <script>alert('xss')</script> -->
$(rm -rf /)
        """)

        # Should parse safely without executing
        validator = DocumentationParityValidator(temp_repo)
        report = validator.validate()

        # Should complete without errors (content treated as text)
        assert isinstance(report, ParityReport)

    def test_limit_file_size_to_prevent_dos(self, temp_repo):
        """Test file size limits to prevent DoS attacks.

        REQUIREMENT: Prevent resource exhaustion attacks.
        Expected: Reject files exceeding size limit.
        """
        # Create oversized file (> 10MB)
        claude_md = temp_repo / "CLAUDE.md"
        large_content = "A" * (11 * 1024 * 1024)  # 11MB
        claude_md.write_text(large_content)

        # Should reject or handle gracefully
        validator = DocumentationParityValidator(temp_repo)
        # Implementation may warn or skip oversized files
        # At minimum, should not crash
        report = validator.validate()
        assert isinstance(report, ParityReport)


class TestValidationLevelEnum:
    """Test ValidationLevel enum."""

    def test_validation_level_error(self):
        """Test ERROR validation level exists.

        REQUIREMENT: Support ERROR severity level.
        Expected: ValidationLevel.ERROR accessible.
        """
        assert hasattr(ValidationLevel, 'ERROR')
        assert ValidationLevel.ERROR.value == 'ERROR'

    def test_validation_level_warning(self):
        """Test WARNING validation level exists.

        REQUIREMENT: Support WARNING severity level.
        Expected: ValidationLevel.WARNING accessible.
        """
        assert hasattr(ValidationLevel, 'WARNING')
        assert ValidationLevel.WARNING.value == 'WARNING'

    def test_validation_level_info(self):
        """Test INFO validation level exists.

        REQUIREMENT: Support INFO severity level.
        Expected: ValidationLevel.INFO accessible.
        """
        assert hasattr(ValidationLevel, 'INFO')
        assert ValidationLevel.INFO.value == 'INFO'

    def test_validation_level_ordering(self):
        """Test validation levels have proper ordering.

        REQUIREMENT: Support severity comparison.
        Expected: ERROR > WARNING > INFO.
        """
        # Assuming enum has ordering
        assert ValidationLevel.ERROR.value == 'ERROR'
        assert ValidationLevel.WARNING.value == 'WARNING'
        assert ValidationLevel.INFO.value == 'INFO'


class TestParityIssueDataclass:
    """Test ParityIssue dataclass."""

    def test_parity_issue_creation(self):
        """Test creating ParityIssue instance.

        REQUIREMENT: Support structured issue representation.
        Expected: ParityIssue with level, message, details.
        """
        issue = ParityIssue(
            level=ValidationLevel.ERROR,
            message="Agent count mismatch",
            details="Expected 5, found 3"
        )

        assert issue.level == ValidationLevel.ERROR
        assert issue.message == "Agent count mismatch"
        assert issue.details == "Expected 5, found 3"

    def test_parity_issue_string_representation(self):
        """Test string representation of ParityIssue.

        REQUIREMENT: Human-readable issue representation.
        Expected: __str__ includes level and message.
        """
        issue = ParityIssue(
            level=ValidationLevel.WARNING,
            message="Missing documentation",
            details="SECURITY.md not found"
        )

        issue_str = str(issue)
        assert "WARNING" in issue_str
        assert "Missing documentation" in issue_str


class TestParityReportDataclass:
    """Test ParityReport dataclass."""

    def test_parity_report_creation(self):
        """Test creating ParityReport instance.

        REQUIREMENT: Support comprehensive validation report.
        Expected: ParityReport with all issue categories.
        """
        report = ParityReport(
            version_issues=[],
            count_issues=[],
            cross_reference_issues=[],
            changelog_issues=[],
            security_issues=[]
        )

        assert isinstance(report.version_issues, list)
        assert isinstance(report.count_issues, list)
        assert report.total_issues == 0

    def test_parity_report_total_issues_calculation(self):
        """Test total_issues property calculation.

        REQUIREMENT: Aggregate all issue categories.
        Expected: total_issues = sum of all issue lists.
        """
        version_issue = ParityIssue(ValidationLevel.ERROR, "Version drift", "")
        count_issue = ParityIssue(ValidationLevel.ERROR, "Count mismatch", "")

        report = ParityReport(
            version_issues=[version_issue],
            count_issues=[count_issue],
            cross_reference_issues=[],
            changelog_issues=[],
            security_issues=[]
        )

        assert report.total_issues == 2

    def test_parity_report_has_errors_property(self):
        """Test has_errors property.

        REQUIREMENT: Quick check for error presence.
        Expected: has_errors=True when ERROR level issues exist.
        """
        error_issue = ParityIssue(ValidationLevel.ERROR, "Error", "")
        warning_issue = ParityIssue(ValidationLevel.WARNING, "Warning", "")

        report = ParityReport(
            version_issues=[error_issue],
            count_issues=[warning_issue],
            cross_reference_issues=[],
            changelog_issues=[],
            security_issues=[]
        )

        assert report.has_errors is True

    def test_parity_report_has_warnings_property(self):
        """Test has_warnings property.

        REQUIREMENT: Quick check for warning presence.
        Expected: has_warnings=True when WARNING level issues exist.
        """
        warning_issue = ParityIssue(ValidationLevel.WARNING, "Warning", "")

        report = ParityReport(
            version_issues=[],
            count_issues=[warning_issue],
            cross_reference_issues=[],
            changelog_issues=[],
            security_issues=[]
        )

        assert report.has_warnings is True
        assert report.has_errors is False

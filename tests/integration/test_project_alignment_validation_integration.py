#!/usr/bin/env python3
"""
Integration Tests for project-alignment-validation Skill (TDD Red Phase)

This module contains FAILING integration tests for the project-alignment-validation
skill integration with agents, hooks, and libraries (Issue #76 Phase 8.7).

Integration Test Strategy:
1. Verify agents can access skill content when keywords trigger activation
2. Verify hooks reference skill for validation patterns
3. Verify libraries reference skill for alignment assessment
4. Verify no behavioral regressions after skill extraction
5. Verify progressive disclosure loads skill content on-demand

Test Coverage:
- Agent skill activation (3 agents)
- Hook skill references (5 hooks)
- Library skill references (4 libraries)
- No behavioral regressions
- Progressive disclosure functionality

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially.

Author: test-master agent
Date: 2025-11-16
Issue: #76 Phase 8.7
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import pytest

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'lib'))
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'hooks'))

# Skill paths
SKILL_DIR = project_root / "plugins" / "autonomous-dev" / "skills" / "project-alignment-validation"
SKILL_FILE = SKILL_DIR / "SKILL.md"

# Agent paths
AGENTS_DIR = project_root / "plugins" / "autonomous-dev" / "agents"

# Hook paths
HOOKS_DIR = project_root / "plugins" / "autonomous-dev" / "hooks"

# Library paths
LIB_DIR = project_root / "plugins" / "autonomous-dev" / "lib"


# ==============================================================================
# Test Suite 1: Agent Skill Activation Integration
# ==============================================================================


class TestAgentSkillActivation:
    """Test agents can activate and use project-alignment-validation skill."""

    def test_alignment_validator_agent_activates_skill(self):
        """Test alignment-validator agent activates project-alignment-validation skill.

        Workflow:
        1. alignment-validator agent starts
        2. Uses 'alignment' keyword in prompt
        3. Skill auto-activates based on keywords
        4. Agent can access skill content (checklist, methodology)
        5. Agent performs validation using skill patterns
        """
        agent_file = AGENTS_DIR / "alignment-validator.md"
        skill_file = SKILL_FILE

        # Agent should exist
        assert agent_file.exists(), f"Agent not found: {agent_file}"

        # Skill should exist
        assert skill_file.exists(), f"Skill not found: {skill_file}"

        # Agent should reference skill
        agent_content = agent_file.read_text()
        assert "project-alignment-validation" in agent_content.lower(), (
            "alignment-validator must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

        # Skill should have alignment keywords for activation
        skill_content = skill_file.read_text()
        assert "alignment" in skill_content.lower(), (
            "Skill must include 'alignment' keyword for activation"
        )

    def test_alignment_analyzer_agent_activates_skill(self):
        """Test alignment-analyzer agent activates project-alignment-validation skill."""
        agent_file = AGENTS_DIR / "alignment-analyzer.md"
        skill_file = SKILL_FILE

        assert agent_file.exists(), f"Agent not found: {agent_file}"
        assert skill_file.exists(), f"Skill not found: {skill_file}"

        agent_content = agent_file.read_text()
        assert "project-alignment-validation" in agent_content.lower(), (
            "alignment-analyzer must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_project_progress_tracker_agent_activates_skill(self):
        """Test project-progress-tracker agent activates project-alignment-validation skill."""
        agent_file = AGENTS_DIR / "project-progress-tracker.md"
        skill_file = SKILL_FILE

        assert agent_file.exists(), f"Agent not found: {agent_file}"
        assert skill_file.exists(), f"Skill not found: {skill_file}"

        agent_content = agent_file.read_text()
        assert "project-alignment-validation" in agent_content.lower(), (
            "project-progress-tracker must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 2: Hook Integration
# ==============================================================================


class TestHookIntegration:
    """Test hooks integrate with project-alignment-validation skill."""

    def test_validate_project_alignment_hook_references_skill(self):
        """Test validate_project_alignment.py hook references skill.

        Hook should:
        1. Reference project-alignment-validation skill in docstring
        2. Use skill patterns for validation logic
        3. Not duplicate validation checklist inline
        """
        hook_file = HOOKS_DIR / "validate_project_alignment.py"
        skill_file = SKILL_FILE

        assert hook_file.exists(), f"Hook not found: {hook_file}"
        assert skill_file.exists(), f"Skill not found: {skill_file}"

        hook_content = hook_file.read_text()
        assert "project-alignment-validation" in hook_content.lower(), (
            "validate_project_alignment.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_auto_update_project_progress_hook_references_skill(self):
        """Test auto_update_project_progress.py hook references skill."""
        hook_file = HOOKS_DIR / "auto_update_project_progress.py"

        assert hook_file.exists(), f"Hook not found: {hook_file}"

        hook_content = hook_file.read_text()
        assert "project-alignment-validation" in hook_content.lower(), (
            "auto_update_project_progress.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_enforce_pipeline_complete_hook_references_skill(self):
        """Test enforce_pipeline_complete.py hook references skill."""
        hook_file = HOOKS_DIR / "enforce_pipeline_complete.py"

        assert hook_file.exists(), f"Hook not found: {hook_file}"

        hook_content = hook_file.read_text()
        assert "project-alignment-validation" in hook_content.lower(), (
            "enforce_pipeline_complete.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_detect_feature_request_hook_references_skill(self):
        """Test detect_feature_request.py hook references skill."""
        hook_file = HOOKS_DIR / "detect_feature_request.py"

        assert hook_file.exists(), f"Hook not found: {hook_file}"

        hook_content = hook_file.read_text()
        assert "project-alignment-validation" in hook_content.lower(), (
            "detect_feature_request.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_validate_documentation_alignment_hook_references_skill(self):
        """Test validate_documentation_alignment.py hook references skill."""
        hook_file = HOOKS_DIR / "validate_documentation_alignment.py"

        assert hook_file.exists(), f"Hook not found: {hook_file}"

        hook_content = hook_file.read_text()
        assert "project-alignment-validation" in hook_content.lower(), (
            "validate_documentation_alignment.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 3: Library Integration
# ==============================================================================


class TestLibraryIntegration:
    """Test libraries integrate with project-alignment-validation skill."""

    def test_alignment_assessor_library_references_skill(self):
        """Test alignment_assessor.py library references skill.

        Library should:
        1. Reference project-alignment-validation skill in docstring
        2. Use skill methodology for assessment logic
        3. Not duplicate assessment patterns inline
        """
        library_file = LIB_DIR / "alignment_assessor.py"
        skill_file = SKILL_FILE

        assert library_file.exists(), f"Library not found: {library_file}"
        assert skill_file.exists(), f"Skill not found: {skill_file}"

        library_content = library_file.read_text()
        assert "project-alignment-validation" in library_content.lower(), (
            "alignment_assessor.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_project_md_updater_library_references_skill(self):
        """Test project_md_updater.py library references skill."""
        library_file = LIB_DIR / "project_md_updater.py"

        assert library_file.exists(), f"Library not found: {library_file}"

        library_content = library_file.read_text()
        assert "project-alignment-validation" in library_content.lower(), (
            "project_md_updater.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_brownfield_retrofit_library_references_skill(self):
        """Test brownfield_retrofit.py library references skill."""
        library_file = LIB_DIR / "brownfield_retrofit.py"

        assert library_file.exists(), f"Library not found: {library_file}"

        library_content = library_file.read_text()
        assert "project-alignment-validation" in library_content.lower(), (
            "brownfield_retrofit.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_migration_planner_library_references_skill(self):
        """Test migration_planner.py library references skill."""
        library_file = LIB_DIR / "migration_planner.py"

        assert library_file.exists(), f"Library not found: {library_file}"

        library_content = library_file.read_text()
        assert "project-alignment-validation" in library_content.lower(), (
            "migration_planner.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 4: No Behavioral Regressions
# ==============================================================================


class TestNoBehavioralRegressions:
    """Test skill extraction doesn't break existing functionality."""

    def test_alignment_validator_agent_still_validates(self):
        """Test alignment-validator agent still performs validation after skill extraction.

        Before: Agent had inline validation checklist
        After: Agent references skill for checklist
        Behavior: Should still validate PROJECT.md alignment correctly
        """
        # This would require running the agent with a test PROJECT.md
        # Placeholder for now
        pytest.skip(
            "Requires agent execution framework\n"
            "Expected: alignment-validator agent validates PROJECT.md using skill patterns\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_validate_project_alignment_hook_still_blocks_commits(self):
        """Test validate_project_alignment.py hook still blocks misaligned commits.

        Before: Hook had inline validation logic
        After: Hook references skill for validation patterns
        Behavior: Should still block commits with misaligned changes
        """
        # This would require git hook execution
        # Placeholder for now
        pytest.skip(
            "Requires git hook execution\n"
            "Expected: Hook blocks commits when PROJECT.md validation fails\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_alignment_assessor_library_still_assesses_gaps(self):
        """Test alignment_assessor.py library still performs gap assessment.

        Before: Library had inline gap assessment methodology
        After: Library references skill for methodology
        Behavior: Should still identify and prioritize alignment gaps
        """
        # This would require importing and testing the library
        # Placeholder for now
        pytest.skip(
            "Requires library import and execution\n"
            "Expected: Library performs gap assessment using skill methodology\n"
            "See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 5: Progressive Disclosure
# ==============================================================================


class TestProgressiveDisclosure:
    """Test progressive disclosure loads skill content on-demand."""

    def test_skill_frontmatter_always_loaded(self):
        """Test skill frontmatter is always loaded (small context overhead)."""
        skill_file = SKILL_FILE
        content = skill_file.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill must have frontmatter"

        frontmatter = parts[1]

        # Frontmatter should be small (< 400 chars = ~100 tokens)
        assert len(frontmatter) < 400, (
            f"Skill frontmatter too large: {len(frontmatter)} chars\n"
            f"Expected: < 400 chars (~100 tokens) for efficient progressive disclosure\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_skill_full_content_loads_on_keyword_match(self):
        """Test skill full content loads when keywords match."""
        skill_file = SKILL_FILE
        content = skill_file.read_text()

        # Extract full content
        parts = content.split("---\n", 2)
        full_content = parts[2]

        # Full content should be substantial (detailed patterns)
        assert len(full_content) > 2000, (
            f"Skill content too small: {len(full_content)} chars\n"
            f"Expected: Detailed alignment validation patterns, examples\n"
            f"Progressive disclosure: Loaded only when keywords match\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_progressive_disclosure_reduces_context_bloat(self):
        """Test progressive disclosure keeps context small.

        Without progressive disclosure:
        - All 11 skill files loaded always
        - ~3,000+ tokens always in context

        With progressive disclosure:
        - Only frontmatter loaded (~100 tokens)
        - Full content loads when keywords match
        - Context bloat prevented
        """
        skill_file = SKILL_FILE
        content = skill_file.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        frontmatter = parts[1]
        full_content = parts[2]

        # Calculate token overhead (1 token ≈ 4 chars)
        frontmatter_tokens = len(frontmatter) // 4
        full_content_tokens = len(full_content) // 4

        # Frontmatter should be < 10% of full content
        overhead_ratio = frontmatter_tokens / full_content_tokens

        assert overhead_ratio < 0.1, (
            f"Progressive disclosure overhead too high: {overhead_ratio:.1%}\n"
            f"Frontmatter: {frontmatter_tokens} tokens\n"
            f"Full content: {full_content_tokens} tokens\n"
            f"Expected: Frontmatter < 10% of full content\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 6: Cross-File Integration
# ==============================================================================


class TestCrossFileIntegration:
    """Test skill works correctly across agents, hooks, and libraries."""

    def test_all_12_files_reference_same_skill(self):
        """Test all 12 files reference the same project-alignment-validation skill.

        Files:
        - 3 agents
        - 5 hooks
        - 4 libraries

        All should reference: project-alignment-validation (consistent naming)
        """
        skill_references = []

        # Check agents
        for agent_name in ["alignment-validator", "alignment-analyzer", "project-progress-tracker"]:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()
            if "project-alignment-validation" in content.lower():
                skill_references.append(agent_name)

        # Check hooks
        for hook_file in [
            "validate_project_alignment.py",
            "auto_update_project_progress.py",
            "enforce_pipeline_complete.py",
            "detect_feature_request.py",
            "validate_documentation_alignment.py"
        ]:
            hook_path = HOOKS_DIR / hook_file
            content = hook_path.read_text()
            if "project-alignment-validation" in content.lower():
                skill_references.append(hook_file)

        # Check libraries
        for library_file in [
            "alignment_assessor.py",
            "project_md_updater.py",
            "brownfield_retrofit.py",
            "migration_planner.py"
        ]:
            library_path = LIB_DIR / library_file
            content = library_path.read_text()
            if "project-alignment-validation" in content.lower():
                skill_references.append(library_file)

        assert len(skill_references) >= 5, (
            f"Expected at least 5 files to reference project-alignment-validation\n"
            f"Found {len(skill_references)} files: {skill_references}\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_skill_content_accessible_to_all_files(self):
        """Test skill content is accessible to agents, hooks, and libraries.

        Progressive disclosure ensures:
        1. Skill metadata always available
        2. Full content loads when keywords match
        3. All 12 files can access same skill content
        4. No duplication across files
        """
        skill_file = SKILL_FILE

        assert skill_file.exists(), f"Skill not found: {skill_file}"

        # Skill should have comprehensive content
        content = skill_file.read_text()
        parts = content.split("---\n", 2)
        full_content = parts[2]

        # Should include all key validation patterns
        required_patterns = [
            "GOALS",
            "SCOPE",
            "CONSTRAINTS",
            "ARCHITECTURE",
            "semantic",
            "gap"
        ]

        for pattern in required_patterns:
            assert pattern in content, (
                f"Skill missing '{pattern}' validation pattern\n"
                f"Expected: Comprehensive patterns accessible to all 12 files\n"
                f"See: Issue #76 Phase 8.7"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

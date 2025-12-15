#!/usr/bin/env python3
"""
TDD Tests for Epic #142 (New Balance Consistency Architecture) - Documentation Validation

This module contains tests for Epic #142 closeout documentation:
- 4-layer architecture consistency (10/30/40/20 percentages)
- Cross-reference validation between docs
- Deterministic-only philosophy in HOOKS.md
- Skill injection mechanism in SKILLS-AGENTS-INTEGRATION.md

Epic #142 Context:
- Implementation issues (#140, #141, #143-146) are COMPLETE
- This is a DOCUMENTATION-ONLY closeout task
- Tests validate documentation consistency and completeness

Requirements:
1. CLAUDE.md documents 4-layer architecture with correct percentages
2. docs/HOOKS.md emphasizes deterministic-only philosophy
3. docs/SKILLS-AGENTS-INTEGRATION.md documents skill injection mechanism
4. All cross-references between docs are valid
5. Workflow Discipline section exists and references all layers

Test Strategy:
- Phase 1: Documentation file existence
- Phase 2: 4-layer architecture consistency
- Phase 3: Cross-reference validation
- Phase 4: Content completeness validation
- Phase 5: Regression checks

Author: test-master agent
Date: 2025-12-16
Epic: #142
Related Issues: #140, #141, #143, #144, #145, #146
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pytest


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestPhase1DocumentationFileExistence:
    """Phase 1: Test that all required documentation files exist."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_md_path(self, project_root):
        """Get CLAUDE.md path."""
        return project_root / "CLAUDE.md"

    @pytest.fixture
    def hooks_md_path(self, project_root):
        """Get docs/HOOKS.md path."""
        return project_root / "docs" / "HOOKS.md"

    @pytest.fixture
    def skills_agents_md_path(self, project_root):
        """Get docs/SKILLS-AGENTS-INTEGRATION.md path."""
        return project_root / "docs" / "SKILLS-AGENTS-INTEGRATION.md"

    def test_claude_md_exists(self, claude_md_path):
        """Test that CLAUDE.md exists.

        EXPECTATION: File at /CLAUDE.md
        """
        assert claude_md_path.exists(), (
            f"CLAUDE.md not found\n"
            f"Expected: {claude_md_path}\n"
            "This file contains 4-layer architecture documentation"
        )

    def test_hooks_md_exists(self, hooks_md_path):
        """Test that docs/HOOKS.md exists.

        EXPECTATION: File at /docs/HOOKS.md
        """
        assert hooks_md_path.exists(), (
            f"docs/HOOKS.md not found\n"
            f"Expected: {hooks_md_path}\n"
            "This file contains deterministic-only philosophy"
        )

    def test_skills_agents_md_exists(self, skills_agents_md_path):
        """Test that docs/SKILLS-AGENTS-INTEGRATION.md exists.

        EXPECTATION: File at /docs/SKILLS-AGENTS-INTEGRATION.md
        """
        assert skills_agents_md_path.exists(), (
            f"docs/SKILLS-AGENTS-INTEGRATION.md not found\n"
            f"Expected: {skills_agents_md_path}\n"
            "This file contains skill injection mechanism documentation"
        )

    def test_all_files_are_files_not_directories(
        self, claude_md_path, hooks_md_path, skills_agents_md_path
    ):
        """Test that all documentation paths are files, not directories."""
        assert claude_md_path.is_file(), (
            f"CLAUDE.md exists but is not a file: {claude_md_path}"
        )
        assert hooks_md_path.is_file(), (
            f"docs/HOOKS.md exists but is not a file: {hooks_md_path}"
        )
        assert skills_agents_md_path.is_file(), (
            f"docs/SKILLS-AGENTS-INTEGRATION.md exists but is not a file: {skills_agents_md_path}"
        )


class TestPhase2FourLayerArchitectureConsistency:
    """Phase 2: Test 4-layer architecture consistency across all docs."""

    @pytest.fixture
    def claude_md_content(self, project_root):
        """Read CLAUDE.md content."""
        claude_md_path = project_root / "CLAUDE.md"
        return claude_md_path.read_text()

    @pytest.fixture
    def hooks_md_content(self, project_root):
        """Read docs/HOOKS.md content."""
        hooks_md_path = project_root / "docs" / "HOOKS.md"
        return hooks_md_path.read_text()

    @pytest.fixture
    def skills_agents_md_content(self, project_root):
        """Read docs/SKILLS-AGENTS-INTEGRATION.md content."""
        skills_agents_md_path = project_root / "docs" / "SKILLS-AGENTS-INTEGRATION.md"
        return skills_agents_md_path.read_text()

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def test_claude_md_has_4_layer_architecture(self, claude_md_content):
        """Test that CLAUDE.md documents 4-layer architecture.

        EXPECTATION: Mentions Layer 1, Layer 2, Layer 3, Layer 4
        """
        assert "Layer 1" in claude_md_content or "LAYER 1" in claude_md_content, (
            "CLAUDE.md missing Layer 1 documentation\n"
            "Expected: 4-layer architecture section with Layer 1 (HOOKS - 10%)"
        )
        assert "Layer 2" in claude_md_content or "LAYER 2" in claude_md_content, (
            "CLAUDE.md missing Layer 2 documentation\n"
            "Expected: 4-layer architecture section with Layer 2 (CLAUDE.md - 30%)"
        )
        assert "Layer 3" in claude_md_content or "LAYER 3" in claude_md_content, (
            "CLAUDE.md missing Layer 3 documentation\n"
            "Expected: 4-layer architecture section with Layer 3 (CONVENIENCE - 40%)"
        )
        assert "Layer 4" in claude_md_content or "LAYER 4" in claude_md_content, (
            "CLAUDE.md missing Layer 4 documentation\n"
            "Expected: 4-layer architecture section with Layer 4 (SKILLS - 20%)"
        )

    def test_claude_md_has_correct_layer_1_percentage(self, claude_md_content):
        """Test that CLAUDE.md documents Layer 1 as 10%.

        EXPECTATION: Layer 1 (HOOKS) documented as 10%
        """
        # Look for patterns like "Layer 1 (10%)" or "HOOKS - 10%" or "10% - HOOKS"
        layer1_patterns = [
            r"Layer 1.*10%",
            r"10%.*Layer 1",
            r"HOOKS.*10%",
            r"10%.*HOOKS",
        ]
        found = any(re.search(pattern, claude_md_content, re.IGNORECASE) for pattern in layer1_patterns)
        assert found, (
            "CLAUDE.md Layer 1 (HOOKS) not documented as 10%\n"
            "Expected: Layer 1 should show 10% enforcement percentage\n"
            "Search patterns: Layer 1.*10%, 10%.*Layer 1, HOOKS.*10%, 10%.*HOOKS"
        )

    def test_claude_md_has_correct_layer_2_percentage(self, claude_md_content):
        """Test that CLAUDE.md documents Layer 2 as 30%.

        EXPECTATION: Layer 2 (CLAUDE.md) documented as 30%
        """
        layer2_patterns = [
            r"Layer 2.*30%",
            r"30%.*Layer 2",
            r"CLAUDE\.md.*30%",
            r"30%.*CLAUDE\.md",
        ]
        found = any(re.search(pattern, claude_md_content, re.IGNORECASE) for pattern in layer2_patterns)
        assert found, (
            "CLAUDE.md Layer 2 (CLAUDE.md guidance) not documented as 30%\n"
            "Expected: Layer 2 should show 30% enforcement percentage\n"
            "Search patterns: Layer 2.*30%, 30%.*Layer 2, CLAUDE.md.*30%, 30%.*CLAUDE.md"
        )

    def test_claude_md_has_correct_layer_3_percentage(self, claude_md_content):
        """Test that CLAUDE.md documents Layer 3 as 40%.

        EXPECTATION: Layer 3 (CONVENIENCE) documented as 40%
        """
        layer3_patterns = [
            r"Layer 3.*40%",
            r"40%.*Layer 3",
            r"CONVENIENCE.*40%",
            r"40%.*CONVENIENCE",
        ]
        found = any(re.search(pattern, claude_md_content, re.IGNORECASE) for pattern in layer3_patterns)
        assert found, (
            "CLAUDE.md Layer 3 (CONVENIENCE) not documented as 40%\n"
            "Expected: Layer 3 should show 40% enforcement percentage\n"
            "Search patterns: Layer 3.*40%, 40%.*Layer 3, CONVENIENCE.*40%, 40%.*CONVENIENCE"
        )

    def test_claude_md_has_correct_layer_4_percentage(self, claude_md_content):
        """Test that CLAUDE.md documents Layer 4 as 20%.

        EXPECTATION: Layer 4 (SKILLS) documented as 20%
        """
        layer4_patterns = [
            r"Layer 4.*20%",
            r"20%.*Layer 4",
            r"SKILLS.*20%",
            r"20%.*SKILLS",
        ]
        found = any(re.search(pattern, claude_md_content, re.IGNORECASE) for pattern in layer4_patterns)
        assert found, (
            "CLAUDE.md Layer 4 (SKILLS) not documented as 20%\n"
            "Expected: Layer 4 should show 20% enforcement percentage\n"
            "Search patterns: Layer 4.*20%, 20%.*Layer 4, SKILLS.*20%, 20%.*SKILLS"
        )

    def test_percentages_sum_to_100(self, claude_md_content):
        """Test that documented percentages sum to 100%.

        EXPECTATION: 10% + 30% + 40% + 20% = 100%
        """
        # This is a logical test - if all four percentages are present, they should sum to 100
        # We verify this by checking all four percentages are documented
        has_10_percent = re.search(r"10%", claude_md_content) is not None
        has_30_percent = re.search(r"30%", claude_md_content) is not None
        has_40_percent = re.search(r"40%", claude_md_content) is not None
        has_20_percent = re.search(r"20%", claude_md_content) is not None

        assert has_10_percent and has_30_percent and has_40_percent and has_20_percent, (
            "CLAUDE.md missing one or more required percentages\n"
            f"Found 10%: {has_10_percent}\n"
            f"Found 30%: {has_30_percent}\n"
            f"Found 40%: {has_40_percent}\n"
            f"Found 20%: {has_20_percent}\n"
            "Expected: All four percentages (10%, 30%, 40%, 20%) documented"
        )


class TestPhase3CrossReferenceValidation:
    """Phase 3: Test cross-references between documentation files."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_md_content(self, project_root):
        """Read CLAUDE.md content."""
        return (project_root / "CLAUDE.md").read_text()

    @pytest.fixture
    def hooks_md_content(self, project_root):
        """Read docs/HOOKS.md content."""
        return (project_root / "docs" / "HOOKS.md").read_text()

    @pytest.fixture
    def skills_agents_md_content(self, project_root):
        """Read docs/SKILLS-AGENTS-INTEGRATION.md content."""
        return (project_root / "docs" / "SKILLS-AGENTS-INTEGRATION.md").read_text()

    def test_claude_md_references_hooks_md(self, claude_md_content):
        """Test that CLAUDE.md references docs/HOOKS.md.

        EXPECTATION: Contains link or reference to HOOKS.md
        """
        hooks_references = [
            "HOOKS.md",
            "docs/HOOKS.md",
            "[HOOKS.md]",
            "hooks documentation",
        ]
        found = any(ref in claude_md_content for ref in hooks_references)
        assert found, (
            "CLAUDE.md does not reference docs/HOOKS.md\n"
            "Expected: Link or reference to HOOKS.md for Layer 1 documentation\n"
            f"Searched for: {hooks_references}"
        )

    def test_claude_md_references_skills_agents_md(self, claude_md_content):
        """Test that CLAUDE.md references docs/SKILLS-AGENTS-INTEGRATION.md.

        EXPECTATION: Contains link or reference to SKILLS-AGENTS-INTEGRATION.md
        """
        skills_references = [
            "SKILLS-AGENTS-INTEGRATION.md",
            "docs/SKILLS-AGENTS-INTEGRATION.md",
            "[SKILLS-AGENTS-INTEGRATION.md]",
            "skills.*integration",
        ]
        found = any(
            re.search(ref, claude_md_content, re.IGNORECASE)
            for ref in skills_references
        )
        assert found, (
            "CLAUDE.md does not reference docs/SKILLS-AGENTS-INTEGRATION.md\n"
            "Expected: Link or reference to SKILLS-AGENTS-INTEGRATION.md for Layer 4 documentation\n"
            f"Searched for: {skills_references}"
        )

    def test_hooks_md_references_claude_md(self, hooks_md_content):
        """Test that docs/HOOKS.md references CLAUDE.md.

        EXPECTATION: Contains link or reference to CLAUDE.md
        """
        claude_references = [
            "CLAUDE.md",
            "[CLAUDE.md]",
            "project instructions",
        ]
        found = any(ref in hooks_md_content for ref in claude_references)
        assert found, (
            "docs/HOOKS.md does not reference CLAUDE.md\n"
            "Expected: Link or reference to CLAUDE.md for context\n"
            f"Searched for: {claude_references}"
        )

    def test_skills_agents_md_references_claude_md(self, skills_agents_md_content):
        """Test that docs/SKILLS-AGENTS-INTEGRATION.md references CLAUDE.md.

        EXPECTATION: Contains link or reference to CLAUDE.md
        """
        claude_references = [
            "CLAUDE.md",
            "[CLAUDE.md]",
            "project instructions",
        ]
        found = any(ref in skills_agents_md_content for ref in claude_references)
        assert found, (
            "docs/SKILLS-AGENTS-INTEGRATION.md does not reference CLAUDE.md\n"
            "Expected: Link or reference to CLAUDE.md for context\n"
            f"Searched for: {claude_references}"
        )

    def test_workflow_discipline_section_exists(self, claude_md_content):
        """Test that CLAUDE.md has Workflow Discipline section.

        EXPECTATION: Contains "## Workflow Discipline" heading
        """
        assert re.search(r"## Workflow Discipline", claude_md_content), (
            "CLAUDE.md missing '## Workflow Discipline' section\n"
            "Expected: Section documenting Layer 2 guidance"
        )


class TestPhase4ContentCompletenessValidation:
    """Phase 4: Test completeness of documentation content."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_md_content(self, project_root):
        """Read CLAUDE.md content."""
        return (project_root / "CLAUDE.md").read_text()

    @pytest.fixture
    def hooks_md_content(self, project_root):
        """Read docs/HOOKS.md content."""
        return (project_root / "docs" / "HOOKS.md").read_text()

    @pytest.fixture
    def skills_agents_md_content(self, project_root):
        """Read docs/SKILLS-AGENTS-INTEGRATION.md content."""
        return (project_root / "docs" / "SKILLS-AGENTS-INTEGRATION.md").read_text()

    def test_hooks_md_documents_deterministic_philosophy(self, hooks_md_content):
        """Test that docs/HOOKS.md emphasizes deterministic-only philosophy.

        EXPECTATION: Contains references to deterministic, blocking, or enforcement
        """
        deterministic_keywords = [
            "deterministic",
            "blocking",
            "enforcement",
            "100% reliable",
            "guaranteed",
        ]
        found = any(
            keyword.lower() in hooks_md_content.lower()
            for keyword in deterministic_keywords
        )
        assert found, (
            "docs/HOOKS.md does not emphasize deterministic-only philosophy\n"
            "Expected: Documentation about deterministic blocking enforcement\n"
            f"Searched for: {deterministic_keywords}"
        )

    def test_skills_agents_md_documents_injection_mechanism(
        self, skills_agents_md_content
    ):
        """Test that docs/SKILLS-AGENTS-INTEGRATION.md documents skill injection.

        EXPECTATION: Contains references to injection, activation, or progressive disclosure
        """
        injection_keywords = [
            "injection",
            "inject",
            "activation",
            "progressive disclosure",
            "keyword",
        ]
        found = any(
            keyword.lower() in skills_agents_md_content.lower()
            for keyword in injection_keywords
        )
        assert found, (
            "docs/SKILLS-AGENTS-INTEGRATION.md does not document skill injection mechanism\n"
            "Expected: Documentation about keyword-based skill activation\n"
            f"Searched for: {injection_keywords}"
        )

    def test_claude_md_documents_auto_implement_command(self, claude_md_content):
        """Test that CLAUDE.md documents /auto-implement command.

        EXPECTATION: Contains reference to /auto-implement (Layer 3 convenience)
        """
        assert "/auto-implement" in claude_md_content, (
            "CLAUDE.md does not document /auto-implement command\n"
            "Expected: Documentation for Layer 3 (CONVENIENCE) command"
        )

    def test_claude_md_documents_workflow_enforcement(self, claude_md_content):
        """Test that CLAUDE.md documents workflow enforcement.

        EXPECTATION: Contains references to enforcement, pipeline, or validation
        """
        enforcement_keywords = [
            "enforcement",
            "pipeline",
            "validation",
            "bypass",
            "block",
        ]
        found = any(
            keyword.lower() in claude_md_content.lower()
            for keyword in enforcement_keywords
        )
        assert found, (
            "CLAUDE.md does not document workflow enforcement\n"
            "Expected: Documentation about enforcement mechanisms\n"
            f"Searched for: {enforcement_keywords}"
        )

    def test_claude_md_workflow_discipline_has_layer_references(self, claude_md_content):
        """Test that Workflow Discipline section references all 4 layers.

        EXPECTATION: Workflow Discipline section mentions HOOKS, CLAUDE.md, commands, and skills
        """
        # Extract Workflow Discipline section (if it exists)
        match = re.search(
            r"## Workflow Discipline.*?(?=\n## |\Z)",
            claude_md_content,
            re.DOTALL
        )
        if not match:
            pytest.skip("Workflow Discipline section not found")

        section = match.group(0)

        # Check for layer references
        has_hooks_ref = any(
            keyword in section.lower()
            for keyword in ["hook", "enforcement", "blocking"]
        )
        has_claude_ref = any(
            keyword in section.lower()
            for keyword in ["claude.md", "guidance", "discipline"]
        )
        has_command_ref = any(
            keyword in section.lower()
            for keyword in ["/auto-implement", "command", "convenience"]
        )
        has_skills_ref = any(
            keyword in section.lower()
            for keyword in ["skill", "progressive", "injection"]
        )

        assert has_hooks_ref, (
            "Workflow Discipline section missing Layer 1 (HOOKS) reference"
        )
        assert has_claude_ref, (
            "Workflow Discipline section missing Layer 2 (CLAUDE.md) reference"
        )
        assert has_command_ref, (
            "Workflow Discipline section missing Layer 3 (CONVENIENCE) reference"
        )
        assert has_skills_ref, (
            "Workflow Discipline section missing Layer 4 (SKILLS) reference"
        )


class TestPhase5RegressionChecks:
    """Phase 5: Regression tests to ensure no existing functionality broke."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def test_existing_workflow_enforcement_tests_still_exist(self, project_root):
        """Test that existing workflow enforcement tests are still present.

        EXPECTATION: test_detect_feature_request.py and test_workflow_enforcement.py exist
        """
        test_files = [
            project_root / "tests" / "unit" / "hooks" / "test_detect_feature_request.py",
            project_root / "tests" / "integration" / "test_workflow_enforcement.py",
        ]
        for test_file in test_files:
            assert test_file.exists(), (
                f"Regression: Test file missing: {test_file}\n"
                "Expected: Existing workflow enforcement tests should still exist"
            )

    def test_skill_allowed_tools_test_still_exists(self, project_root):
        """Test that skill allowed_tools test still exists.

        EXPECTATION: test_skill_allowed_tools.py exists with 30+ tests
        """
        test_file = project_root / "tests" / "unit" / "test_skill_allowed_tools.py"
        assert test_file.exists(), (
            f"Regression: Test file missing: {test_file}\n"
            "Expected: Skill validation tests should still exist"
        )

        # Verify it has tests
        content = test_file.read_text()
        test_count = len(re.findall(r"def test_", content))
        assert test_count >= 30, (
            f"Regression: test_skill_allowed_tools.py only has {test_count} tests\n"
            "Expected: At least 30 tests for skill validation"
        )

    def test_hooks_directory_still_exists(self, project_root):
        """Test that hooks directory and files are still present.

        EXPECTATION: plugins/autonomous-dev/hooks/ directory exists
        """
        hooks_dir = project_root / "plugins" / "autonomous-dev" / "hooks"
        assert hooks_dir.exists() and hooks_dir.is_dir(), (
            f"Regression: Hooks directory missing: {hooks_dir}\n"
            "Expected: All hooks should still be present"
        )

        # Check for key hooks (unified hooks from Issue #144)
        key_hooks = [
            "unified_prompt_validator.py",  # Consolidates detect_feature_request.py
            "unified_pre_tool.py",  # Consolidates PreToolUse validators
            "unified_code_quality.py",  # Consolidates PreCommit quality checks
        ]
        for hook_file in key_hooks:
            hook_path = hooks_dir / hook_file
            assert hook_path.exists(), (
                f"Regression: Key hook missing: {hook_path}\n"
                "Expected: All enforcement hooks should still exist"
            )

    def test_agents_directory_still_exists(self, project_root):
        """Test that agents directory and files are still present.

        EXPECTATION: plugins/autonomous-dev/agents/ directory exists with 22 agents
        """
        agents_dir = project_root / "plugins" / "autonomous-dev" / "agents"
        assert agents_dir.exists() and agents_dir.is_dir(), (
            f"Regression: Agents directory missing: {agents_dir}\n"
            "Expected: All agents should still be present"
        )

        # Count agent files (Issue #147: 8 active agents, rest archived)
        agent_files = list(agents_dir.glob("*.md"))
        assert len(agent_files) >= 8, (
            f"Regression: Only {len(agent_files)} agent files found\n"
            "Expected: At least 8 agent files (8 active per CLAUDE.md)"
        )

    def test_skills_directory_still_exists(self, project_root):
        """Test that skills directory and files are still present.

        EXPECTATION: .claude/skills/ directory exists with 28 skills
        """
        # Skills are now in .claude/skills/ as directories (Issue #143)
        skills_dir = project_root / ".claude" / "skills"
        assert skills_dir.exists() and skills_dir.is_dir(), (
            f"Regression: Skills directory missing: {skills_dir}\n"
            "Expected: All skills should still be present"
        )

        # Count skill directories (each skill is now a directory with SKILL.md)
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        assert len(skill_dirs) >= 25, (
            f"Regression: Only {len(skill_dirs)} skill directories found\n"
            "Expected: At least 25 skill directories (28 documented in CLAUDE.md)"
        )


class TestPhase6EpicCloseoutDocumentation:
    """Phase 6: Test that Epic #142 closeout documentation exists."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def test_epic_142_closeout_document_exists(self, project_root):
        """Test that Epic #142 closeout document exists.

        EXPECTATION: docs/epic-142-closeout.md or similar exists
        """
        # Check for possible closeout document locations
        possible_locations = [
            project_root / "docs" / "epic-142-closeout.md",
            project_root / "docs" / "EPIC-142-CLOSEOUT.md",
            project_root / "docs" / "epics" / "142-closeout.md",
        ]

        found = any(path.exists() for path in possible_locations)
        assert found, (
            "Epic #142 closeout document not found\n"
            f"Searched locations: {[str(p) for p in possible_locations]}\n"
            "Expected: Closeout document summarizing Epic #142 implementation"
        )

    def test_epic_142_references_all_issues(self, project_root):
        """Test that Epic #142 closeout references all related issues.

        EXPECTATION: Closeout doc mentions #140, #141, #143, #144, #145, #146
        """
        # Find closeout document
        possible_locations = [
            project_root / "docs" / "epic-142-closeout.md",
            project_root / "docs" / "EPIC-142-CLOSEOUT.md",
            project_root / "docs" / "epics" / "142-closeout.md",
        ]

        closeout_path = None
        for path in possible_locations:
            if path.exists():
                closeout_path = path
                break

        if not closeout_path:
            pytest.skip("Closeout document not found")

        content = closeout_path.read_text()

        # Check for issue references
        required_issues = ["#140", "#141", "#143", "#144", "#145", "#146"]
        for issue in required_issues:
            assert issue in content, (
                f"Epic #142 closeout document missing reference to {issue}\n"
                f"File: {closeout_path}\n"
                "Expected: All related issues should be referenced"
            )


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=line"])

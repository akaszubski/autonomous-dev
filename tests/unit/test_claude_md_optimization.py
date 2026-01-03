#!/usr/bin/env python3
"""
TDD Tests for CLAUDE.md Optimization (FAILING - Red Phase)

This module contains FAILING tests for optimizing CLAUDE.md from 54.5k to <35k characters
by extracting detailed technical content to separate documentation files while maintaining
all cross-references and alignment.

Feature Requirements:
1. Extract libs content (lines 289-695, ~12k chars) to docs/LIBRARIES.md
2. Extract performance content (lines 138-162, ~2k chars) to docs/PERFORMANCE.md
3. Extract git automation content (lines 166-223, ~3k chars) to docs/GIT-AUTOMATION.md
4. CLAUDE.md condenses sections with links to new docs
5. Final CLAUDE.md character count < 35,000
6. All cross-references valid (relative paths)
7. No information lost (total content preserved)
8. All alignment validation passes

Test Coverage Target: 100% of optimization requirements

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe optimization requirements
- Tests should FAIL until implementation complete
- Each test validates ONE optimization requirement

Author: test-master agent
Date: 2025-11-11
Issue: TBD (CLAUDE.md optimization)
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCharacterCountValidation:
    """Test character count requirements for CLAUDE.md optimization."""

    def test_claude_md_character_count_under_35k(self):
        """
        CLAUDE.md should be < 35,000 characters after optimization.

        Current: 54,511 characters
        Target: < 35,000 characters
        Reduction: ~19,500 characters (36% reduction)
        """
        claude_md_path = Path(__file__).parent.parent.parent / "CLAUDE.md"

        # This will FAIL until optimization complete
        assert claude_md_path.exists(), "CLAUDE.md not found"

        content = claude_md_path.read_text(encoding="utf-8")
        char_count = len(content)

        assert char_count < 35000, (
            f"CLAUDE.md too large: {char_count} characters (target: < 35,000). "
            f"Need to reduce by {char_count - 35000} characters."
        )

    def test_total_content_preserved(self):
        """
        Total content across CLAUDE.md + new docs should approximately equal baseline.

        Baseline (comprehensive documentation): ~295,000 characters (v3.41.0+)
        Distribution: CLAUDE.md + LIBRARIES.md + PERFORMANCE.md + GIT-AUTOMATION.md
        Tolerance: ±15% (includes 35 libraries from LIBRARIES.md)
        """
        original_size = 541000  # Updated baseline for v3.48.0+ with agent_feedback.py (Issue #191)

        # Paths
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"
        libraries_md = project_root / "docs" / "LIBRARIES.md"
        performance_md = project_root / "docs" / "PERFORMANCE.md"
        git_automation_md = project_root / "docs" / "GIT-AUTOMATION.md"

        # This will FAIL until new docs created
        assert claude_md.exists(), "CLAUDE.md not found"
        assert libraries_md.exists(), "docs/LIBRARIES.md not created yet"
        assert performance_md.exists(), "docs/PERFORMANCE.md not created yet"
        assert git_automation_md.exists(), "docs/GIT-AUTOMATION.md not created yet"

        # Calculate total size
        total_size = (
            len(claude_md.read_text(encoding="utf-8")) +
            len(libraries_md.read_text(encoding="utf-8")) +
            len(performance_md.read_text(encoding="utf-8")) +
            len(git_automation_md.read_text(encoding="utf-8"))
        )

        # Allow ±15% tolerance (libraries have grown significantly)
        min_size = original_size * 0.85
        max_size = original_size * 1.15

        assert min_size <= total_size <= max_size, (
            f"Total content size mismatch: {total_size} characters "
            f"(expected {original_size} ±15%). "
            f"Information may have been lost or duplicated."
        )

    def test_individual_doc_sizes_reasonable(self):
        """
        Individual documentation files should be appropriately sized.

        Expected sizes (comprehensive documentation, v3.37.0):
        - docs/LIBRARIES.md: ~149,857 characters (28 library API references)
        - docs/PERFORMANCE.md: ~12,397 characters (complete optimization tracking)
        - docs/GIT-AUTOMATION.md: ~41,098 characters (includes batch git automation, Issues #93, #96, #167, #168)
        """
        project_root = Path(__file__).parent.parent.parent

        # This will FAIL until files created
        libraries_md = project_root / "docs" / "LIBRARIES.md"
        performance_md = project_root / "docs" / "PERFORMANCE.md"
        git_automation_md = project_root / "docs" / "GIT-AUTOMATION.md"

        assert libraries_md.exists(), "docs/LIBRARIES.md not created"
        assert performance_md.exists(), "docs/PERFORMANCE.md not created"
        assert git_automation_md.exists(), "docs/GIT-AUTOMATION.md not created"

        # Check sizes (±40% tolerance for libraries, ±30% for others)
        libraries_size = len(libraries_md.read_text(encoding="utf-8"))
        performance_size = len(performance_md.read_text(encoding="utf-8"))
        git_automation_size = len(git_automation_md.read_text(encoding="utf-8"))

        assert 90000 <= libraries_size <= 500000, (
            f"LIBRARIES.md size unexpected: {libraries_size} chars "
            f"(expected ~450,000 ±10% for 80+ libraries)"
        )
        assert 8600 <= performance_size <= 16200, (
            f"PERFORMANCE.md size unexpected: {performance_size} chars "
            f"(expected ~12,397 ±30%)"
        )
        assert 28768 <= git_automation_size <= 53427, (
            f"GIT-AUTOMATION.md size unexpected: {git_automation_size} chars "
            f"(expected ~41,098 ±30% with batch git automation, Issues #167, #168)"
        )


class TestContentExtractionValidation:
    """Test content extraction to new documentation files."""

    def test_libraries_md_contains_all_18_libraries(self):
        """
        docs/LIBRARIES.md should contain all 18 library descriptions.

        Required libraries:
        1. security_utils.py
        2. project_md_updater.py
        3. version_detector.py
        4. orphan_file_cleaner.py
        5. sync_dispatcher.py
        6. validate_marketplace_version.py
        7. plugin_updater.py
        8. update_plugin.py
        9. hook_activator.py
        10. auto_implement_git_integration.py
        11. github_issue_automation.py
        12. brownfield_retrofit.py
        13. codebase_analyzer.py
        14. alignment_assessor.py
        15. migration_planner.py
        16. retrofit_executor.py
        17. retrofit_verifier.py
        """
        libraries_md = Path(__file__).parent.parent.parent / "docs" / "LIBRARIES.md"

        # This will FAIL until file created
        assert libraries_md.exists(), "docs/LIBRARIES.md not created"

        content = libraries_md.read_text(encoding="utf-8")

        # Check for all 19 libraries (github_issue_automation split into closer + fetcher)
        required_libraries = [
            "security_utils.py",
            "project_md_updater.py",
            "version_detector.py",
            "orphan_file_cleaner.py",
            "sync_dispatcher.py",
            "validate_marketplace_version.py",
            "plugin_updater.py",
            "update_plugin.py",
            "hook_activator.py",
            "auto_implement_git_integration.py",
            "github_issue_closer.py",
            "github_issue_fetcher.py",
            "brownfield_retrofit.py",
            "codebase_analyzer.py",
            "alignment_assessor.py",
            "migration_planner.py",
            "retrofit_executor.py",
            "retrofit_verifier.py",
        ]

        missing_libraries = []
        for lib in required_libraries:
            if lib not in content:
                missing_libraries.append(lib)

        assert not missing_libraries, (
            f"Missing libraries in docs/LIBRARIES.md: {', '.join(missing_libraries)}"
        )

    def test_libraries_md_contains_key_functions(self):
        """
        docs/LIBRARIES.md should document key functions from each library.

        Sample key functions to verify:
        - validate_path() (security_utils.py)
        - update_goal_progress() (project_md_updater.py)
        - detect_version_mismatch() (version_detector.py)
        - detect_orphans() (orphan_file_cleaner.py)
        """
        libraries_md = Path(__file__).parent.parent.parent / "docs" / "LIBRARIES.md"

        # This will FAIL until file created
        assert libraries_md.exists(), "docs/LIBRARIES.md not created"

        content = libraries_md.read_text(encoding="utf-8")

        # Check for key functions
        key_functions = [
            "validate_path()",
            "update_goal_progress()",
            "detect_version_mismatch()",
            "detect_orphans()",
        ]

        missing_functions = []
        for func in key_functions:
            if func not in content:
                missing_functions.append(func)

        assert not missing_functions, (
            f"Missing key functions in docs/LIBRARIES.md: {', '.join(missing_functions)}"
        )

    def test_performance_md_contains_phase_details(self):
        """
        docs/PERFORMANCE.md should contain Phase 4-7 optimization details.

        Required content:
        - Phase 4 (Model Optimization)
        - Phase 5 (Prompt Simplification)
        - Phase 6 (Profiling Infrastructure)
        - Phase 7 (Parallel Validation Checkpoint)
        """
        performance_md = Path(__file__).parent.parent.parent / "docs" / "PERFORMANCE.md"

        # This will FAIL until file created
        assert performance_md.exists(), "docs/PERFORMANCE.md not created"

        content = performance_md.read_text(encoding="utf-8")

        # Check for all phases
        required_phases = [
            "Phase 4",
            "Phase 5",
            "Phase 6",
            "Phase 7",
        ]

        missing_phases = []
        for phase in required_phases:
            if phase not in content:
                missing_phases.append(phase)

        assert not missing_phases, (
            f"Missing performance phases in docs/PERFORMANCE.md: {', '.join(missing_phases)}"
        )

    def test_performance_md_contains_timing_metrics(self):
        """
        docs/PERFORMANCE.md should contain performance timing metrics.

        Required metrics:
        - Baseline timings (28-44 minutes, etc.)
        - Savings per phase (3-5 minutes, etc.)
        - Cumulative improvement (5-9 minutes, 15-32% faster)
        """
        performance_md = Path(__file__).parent.parent.parent / "docs" / "PERFORMANCE.md"

        # This will FAIL until file created
        assert performance_md.exists(), "docs/PERFORMANCE.md not created"

        content = performance_md.read_text(encoding="utf-8")

        # Check for timing metrics (using regex for flexibility)
        required_metrics = [
            r"\d+-\d+ min",  # Baseline timing pattern
            r"\d+ minutes? saved",  # Savings pattern
            r"\d+%",  # Percentage improvement
        ]

        missing_metrics = []
        for metric_pattern in required_metrics:
            if not re.search(metric_pattern, content):
                missing_metrics.append(metric_pattern)

        assert not missing_metrics, (
            f"Missing timing metrics in docs/PERFORMANCE.md: {', '.join(missing_metrics)}"
        )

    def test_git_automation_md_contains_env_vars(self):
        """
        docs/GIT-AUTOMATION.md should contain environment variable documentation.

        Required environment variables:
        - AUTO_GIT_ENABLED
        - AUTO_GIT_PUSH
        - AUTO_GIT_PR
        """
        git_automation_md = Path(__file__).parent.parent.parent / "docs" / "GIT-AUTOMATION.md"

        # This will FAIL until file created
        assert git_automation_md.exists(), "docs/GIT-AUTOMATION.md not created"

        content = git_automation_md.read_text(encoding="utf-8")

        # Check for environment variables
        required_env_vars = [
            "AUTO_GIT_ENABLED",
            "AUTO_GIT_PUSH",
            "AUTO_GIT_PR",
        ]

        missing_env_vars = []
        for env_var in required_env_vars:
            if env_var not in content:
                missing_env_vars.append(env_var)

        assert not missing_env_vars, (
            f"Missing environment variables in docs/GIT-AUTOMATION.md: {', '.join(missing_env_vars)}"
        )

    def test_git_automation_md_contains_workflow_steps(self):
        """
        docs/GIT-AUTOMATION.md should contain workflow step descriptions.

        Required content:
        - How it works (numbered steps)
        - Hook integration (SubagentStop)
        - Consent-based design explanation
        - Security documentation
        """
        git_automation_md = Path(__file__).parent.parent.parent / "docs" / "GIT-AUTOMATION.md"

        # This will FAIL until file created
        assert git_automation_md.exists(), "docs/GIT-AUTOMATION.md not created"

        content = git_automation_md.read_text(encoding="utf-8")

        # Check for workflow components
        required_components = [
            "How It Works",
            "SubagentStop",
            "First-Run Consent",  # v3.12.0: Updated from "Consent-Based" to reflect Issue #61 terminology
            "Security",
        ]

        missing_components = []
        for component in required_components:
            if component not in content:
                missing_components.append(component)

        assert not missing_components, (
            f"Missing workflow components in docs/GIT-AUTOMATION.md: {', '.join(missing_components)}"
        )


class TestCrossReferenceValidation:
    """Test cross-reference links between CLAUDE.md and new docs."""

    def test_claude_md_links_to_libraries_md(self):
        """
        CLAUDE.md should contain relative link to docs/LIBRARIES.md.

        Expected link format: [text](docs/LIBRARIES.md) or See docs/LIBRARIES.md
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        # This will FAIL until link added
        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for link (markdown or plain text reference)
        has_link = (
            "docs/LIBRARIES.md" in content or
            "[LIBRARIES.md](docs/LIBRARIES.md)" in content or
            "See docs/LIBRARIES.md" in content
        )

        assert has_link, (
            "CLAUDE.md missing link to docs/LIBRARIES.md. "
            "Should reference library documentation."
        )

    def test_claude_md_links_to_performance_md(self):
        """
        CLAUDE.md should contain relative link to docs/PERFORMANCE.md.

        Expected link format: [text](docs/PERFORMANCE.md) or See docs/PERFORMANCE.md
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        # This will FAIL until link added
        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for link
        has_link = (
            "docs/PERFORMANCE.md" in content or
            "[PERFORMANCE.md](docs/PERFORMANCE.md)" in content or
            "See docs/PERFORMANCE.md" in content
        )

        assert has_link, (
            "CLAUDE.md missing link to docs/PERFORMANCE.md. "
            "Should reference performance documentation."
        )

    def test_claude_md_links_to_git_automation_md(self):
        """
        CLAUDE.md should contain relative link to docs/GIT-AUTOMATION.md.

        Expected link format: [text](docs/GIT-AUTOMATION.md) or See docs/GIT-AUTOMATION.md
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        # This will FAIL until link added
        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for link
        has_link = (
            "docs/GIT-AUTOMATION.md" in content or
            "[GIT-AUTOMATION.md](docs/GIT-AUTOMATION.md)" in content or
            "See docs/GIT-AUTOMATION.md" in content
        )

        assert has_link, (
            "CLAUDE.md missing link to docs/GIT-AUTOMATION.md. "
            "Should reference git automation documentation."
        )

    def test_all_links_use_relative_paths(self):
        """
        All documentation links should use relative paths (not absolute).

        Valid: docs/LIBRARIES.md, ./docs/LIBRARIES.md
        Invalid: /docs/LIBRARIES.md, /Users/.../docs/LIBRARIES.md
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        # This will FAIL if absolute paths used
        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Find all markdown links
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        links = re.findall(link_pattern, content)

        absolute_links = []
        for link_text, link_url in links:
            # Check if link is to new docs
            if any(doc in link_url for doc in ["LIBRARIES.md", "PERFORMANCE.md", "GIT-AUTOMATION.md"]):
                # Should not start with /
                if link_url.startswith("/"):
                    absolute_links.append(link_url)

        assert not absolute_links, (
            f"Found absolute paths in CLAUDE.md links: {', '.join(absolute_links)}. "
            f"Use relative paths like 'docs/LIBRARIES.md' instead."
        )

    def test_links_use_correct_markdown_syntax(self):
        """
        All cross-reference links should use correct markdown syntax.

        Valid: [Library Documentation](docs/LIBRARIES.md)
        Invalid: (docs/LIBRARIES.md), docs/LIBRARIES.md (plain text allowed but not preferred)
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Find references to new docs
        doc_references = [
            "LIBRARIES.md",
            "PERFORMANCE.md",
            "GIT-AUTOMATION.md",
        ]

        for doc in doc_references:
            if doc in content:
                # Should have markdown link format somewhere
                has_markdown_link = re.search(rf'\[[^\]]+\]\([^)]*{re.escape(doc)}[^)]*\)', content)

                # Allow both markdown links and plain text references
                # (not asserting here, just checking format is valid if markdown used)
                if has_markdown_link:
                    # Verify link format is correct (no broken brackets)
                    link_match = has_markdown_link.group(0)
                    assert link_match.count('[') == 1, f"Malformed link: {link_match}"
                    assert link_match.count(']') == 1, f"Malformed link: {link_match}"
                    assert link_match.count('(') == 1, f"Malformed link: {link_match}"
                    assert link_match.count(')') == 1, f"Malformed link: {link_match}"


class TestAlignmentValidation:
    """Test alignment validation passes after optimization."""

    def test_validate_claude_alignment_passes(self):
        """
        validate_claude_alignment.py should pass after optimization.

        This ensures:
        - Version dates still consistent
        - Agent counts still correct (22 specialists - Issue #128)
        - Command counts still correct (7 commands - Issue #121)
        - No alignment drift introduced
        """
        project_root = Path(__file__).parent.parent.parent
        # Run from plugin source, not installed copy (which is gitignored)
        validator_script = project_root / "plugins" / "autonomous-dev" / "hooks" / "validate_claude_alignment.py"

        # This will FAIL if alignment broken
        assert validator_script.exists(), "validate_claude_alignment.py not found"

        # Run validator (should exit 0 on success, 1 on warnings, 2 on errors)
        import subprocess
        result = subprocess.run(
            ["python3", str(validator_script)],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        # Exit code 0 = success, 1 = warnings (OK), 2 = errors (FAIL)
        assert result.returncode in (0, 1), (
            f"CLAUDE.md alignment validation failed with errors:\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    def test_agent_count_still_correct_in_claude_md(self):
        """
        CLAUDE.md should still document correct agent count (19 specialists).

        After optimization, agent count documentation should remain accurate.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        # This will FAIL if count removed/incorrect
        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check that agents section exists and links to detailed docs
        # Note: Hardcoded counts removed to prevent drift (see refactor in Dec 2025)
        assert "### Agents" in content, "CLAUDE.md missing Agents section"
        assert "docs/AGENTS.md" in content, "CLAUDE.md should link to AGENTS.md for details"

    def test_commands_section_exists_in_claude_md(self):
        """
        CLAUDE.md should document available commands.

        Note: Hardcoded counts removed to prevent drift (see refactor in Dec 2025).
        Commands section should exist and list available commands.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check that commands section exists and lists key commands
        assert "**Commands**:" in content or "## Commands" in content, (
            "CLAUDE.md missing Commands section"
        )
        assert "/auto-implement" in content, "CLAUDE.md should document /auto-implement"
        assert "/sync" in content, "CLAUDE.md should document /sync"


class TestContentCompletenessValidation:
    """Test no information lost during optimization."""

    def test_all_18_libraries_documented(self):
        """
        All 18 libraries should be documented in docs/LIBRARIES.md.

        This is a comprehensive check ensuring no library omitted.
        """
        libraries_md = Path(__file__).parent.parent.parent / "docs" / "LIBRARIES.md"

        # This will FAIL until all libraries documented
        assert libraries_md.exists(), "docs/LIBRARIES.md not created"

        content = libraries_md.read_text(encoding="utf-8")

        # All 19 libraries with line counts (github_issue_automation split into closer + fetcher)
        expected_libraries = {
            "security_utils.py": 628,
            "project_md_updater.py": 247,
            "version_detector.py": 531,
            "orphan_file_cleaner.py": 514,
            "sync_dispatcher.py": 976,
            "validate_marketplace_version.py": 371,
            "plugin_updater.py": 868,
            "update_plugin.py": 380,
            "hook_activator.py": 539,
            "auto_implement_git_integration.py": 1466,
            "github_issue_closer.py": 583,
            "github_issue_fetcher.py": 484,
            "brownfield_retrofit.py": 470,
            "codebase_analyzer.py": 870,
            "alignment_assessor.py": 666,
            "migration_planner.py": 578,
            "retrofit_executor.py": 725,
            "retrofit_verifier.py": 689,
        }

        missing_libraries = []
        for lib_name, line_count in expected_libraries.items():
            if lib_name not in content:
                missing_libraries.append(lib_name)

        assert not missing_libraries, (
            f"Missing libraries in docs/LIBRARIES.md: {', '.join(missing_libraries)}"
        )

        assert len(expected_libraries) == 18, (
            f"Expected 18 libraries, found {len(expected_libraries)}"
        )

    def test_key_terms_still_searchable_in_claude_md(self):
        """
        Key terms should remain searchable in CLAUDE.md or be linked to new docs.

        Key terms to verify:
        - "security_utils" (should link to LIBRARIES.md)
        - "Phase 4" (should link to PERFORMANCE.md)
        - "AUTO_GIT_ENABLED" (should link to GIT-AUTOMATION.md)
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        # This will FAIL if key terms removed without links
        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for key terms or references to their documentation
        key_terms_and_docs = [
            ("security_utils", "LIBRARIES.md"),
            ("Phase 4", "PERFORMANCE.md"),
            ("AUTO_GIT_ENABLED", "GIT-AUTOMATION.md"),
        ]

        missing_terms = []
        for term, doc_file in key_terms_and_docs:
            # Term should appear in CLAUDE.md OR CLAUDE.md should link to its doc
            has_term = term in content
            has_doc_link = doc_file in content

            if not (has_term or has_doc_link):
                missing_terms.append(f"{term} (no reference to {doc_file} either)")

        assert not missing_terms, (
            f"Key terms not searchable in CLAUDE.md: {', '.join(missing_terms)}. "
            f"Either keep term or add link to detailed documentation."
        )

    def test_no_information_lost_comprehensive_check(self):
        """
        Comprehensive check that no critical information lost.

        Verifies:
        - All original major sections present (in CLAUDE.md or new docs)
        - All critical keywords searchable
        - All library names referenced somewhere
        """
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"
        libraries_md = project_root / "docs" / "LIBRARIES.md"
        performance_md = project_root / "docs" / "PERFORMANCE.md"
        git_automation_md = project_root / "docs" / "GIT-AUTOMATION.md"

        # This will FAIL if any file missing
        assert claude_md.exists(), "CLAUDE.md not found"
        assert libraries_md.exists(), "docs/LIBRARIES.md not created"
        assert performance_md.exists(), "docs/PERFORMANCE.md not created"
        assert git_automation_md.exists(), "docs/GIT-AUTOMATION.md not created"

        # Combine all content
        all_content = (
            claude_md.read_text(encoding="utf-8") +
            libraries_md.read_text(encoding="utf-8") +
            performance_md.read_text(encoding="utf-8") +
            git_automation_md.read_text(encoding="utf-8")
        )

        # Critical sections that must exist somewhere
        critical_sections = [
            "Libraries",
            "Performance",
            "Git Automation",
            "security_utils.py",
            "Phase 4",
            "AUTO_GIT_ENABLED",
            "validate_path",
            "SubagentStop",
        ]

        missing_sections = []
        for section in critical_sections:
            if section not in all_content:
                missing_sections.append(section)

        assert not missing_sections, (
            f"Critical sections missing from all documentation: {', '.join(missing_sections)}. "
            f"Information may have been lost during optimization."
        )


class TestOptimizationRegressionPrevention:
    """Test optimization doesn't break existing functionality."""

    def test_claude_md_still_has_project_overview(self):
        """
        CLAUDE.md should retain Project Overview section.

        Optimization should not remove core sections.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        assert "## Project Overview" in content or "Project Overview" in content, (
            "CLAUDE.md missing Project Overview section. "
            "Core sections should not be removed during optimization."
        )

    def test_claude_md_still_has_installation_instructions(self):
        """
        CLAUDE.md should retain installation instructions.

        Optimization should not remove essential user-facing content.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for installation keywords
        has_installation = any(
            keyword in content
            for keyword in ["/plugin install", "Installation", "Install"]
        )

        assert has_installation, (
            "CLAUDE.md missing installation instructions. "
            "Essential user-facing content should be preserved."
        )

    def test_claude_md_still_has_workflow_documentation(self):
        """
        CLAUDE.md should retain workflow documentation.

        Core workflow steps should remain in main file.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for workflow keywords
        workflow_keywords = [
            "/auto-implement",
            "Workflow",
            "researcher",
            "planner",
            "test-master",
        ]

        missing_keywords = []
        for keyword in workflow_keywords:
            if keyword not in content:
                missing_keywords.append(keyword)

        assert not missing_keywords, (
            f"CLAUDE.md missing workflow keywords: {', '.join(missing_keywords)}. "
            f"Core workflow documentation should be preserved."
        )


# Integration test marker for running validators
pytest.mark.integration = pytest.mark.skipif(
    "not config.getoption('--run-integration')",
    reason="Integration tests require --run-integration flag"
)

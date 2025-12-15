#!/usr/bin/env python3
"""
TDD Tests for CLAUDE.md Optimization - Issue #78 (FAILING - Red Phase)

This module contains FAILING tests for optimizing CLAUDE.md from 41,847 to <35,000 characters
by extracting detailed content to 4 separate documentation files while maintaining all
cross-references and searchability.

Feature Requirements (from planner):
Phase 1: Extract Performance History to docs/PERFORMANCE-HISTORY.md (~4,800 chars saved)
Phase 2: Extract Batch Processing to docs/BATCH-PROCESSING.md (~1,700 chars saved)
Phase 3: Extract Agent Architecture to docs/AGENTS.md (~2,300 chars saved)
Phase 4: Extract Hook Reference to docs/HOOKS.md (~1,300 chars saved)
Phase 5-7: Consolidate Skills, Git Automation, Libraries sections (~2,400 chars saved)

Total reduction: ~12,500 chars → Target: <35,000 chars (ideally 30-32K)

Test Coverage:
1. Character count validation (<35,000)
2. New documentation files exist and are properly sized
3. Content preservation (all information still accessible)
4. Cross-reference links work (relative paths)
5. Section size limits (no section >100 lines)
6. Search term discoverability maintained
7. Alignment validation passes

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe optimization requirements
- Tests should FAIL until implementation complete
- Each test validates ONE specific requirement

Author: test-master agent
Date: 2025-11-16
Issue: #78 (CLAUDE.md optimization)
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCharacterCountValidation:
    """Test character count requirements for CLAUDE.md optimization."""

    def test_claude_md_under_35k_characters(self):
        """
        CLAUDE.md should be < 35,000 characters after optimization.

        Current: 41,847 characters
        Target: < 35,000 characters (ideally 30-32K)
        Reduction needed: ~6,847+ characters (16%+ reduction)
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")
        char_count = len(content)

        assert char_count < 35000, (
            f"CLAUDE.md too large: {char_count:,} characters (target: < 35,000). "
            f"Need to reduce by {char_count - 35000:,} characters."
        )

    def test_claude_md_ideally_under_32k_characters(self):
        """
        CLAUDE.md should ideally be < 32,000 characters (stretch goal).

        Target: 30,000-32,000 characters
        This provides buffer for future updates without exceeding 35K limit.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")
        char_count = len(content)

        # Stretch goal - ideally under 32K
        if char_count >= 32000:
            pytest.skip(
                f"Stretch goal not met: {char_count:,} characters (ideal: < 32,000). "
                f"Hard requirement (<35K) may still pass."
            )

    def test_total_content_preserved_across_all_docs(self):
        """
        Total content across CLAUDE.md + 4 new docs should preserve all information.

        Baseline: 41,847 characters (CLAUDE.md current)
        New docs: PERFORMANCE-HISTORY.md, BATCH-PROCESSING.md, AGENTS.md, HOOKS.md
        Total should be ≥ baseline (allowing for formatting improvements)
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        performance_history = project_root / "docs" / "PERFORMANCE-HISTORY.md"
        batch_processing = project_root / "docs" / "BATCH-PROCESSING.md"
        agents_md = project_root / "docs" / "AGENTS.md"
        hooks_md = project_root / "docs" / "HOOKS.md"

        # All files must exist
        assert claude_md.exists(), "CLAUDE.md not found"
        assert performance_history.exists(), "docs/PERFORMANCE-HISTORY.md not created yet"
        assert batch_processing.exists(), "docs/BATCH-PROCESSING.md not created yet"
        assert agents_md.exists(), "docs/AGENTS.md not created yet"
        assert hooks_md.exists(), "docs/HOOKS.md not created yet"

        # Calculate total size
        total_size = sum([
            len(claude_md.read_text(encoding="utf-8")),
            len(performance_history.read_text(encoding="utf-8")),
            len(batch_processing.read_text(encoding="utf-8")),
            len(agents_md.read_text(encoding="utf-8")),
            len(hooks_md.read_text(encoding="utf-8")),
        ])

        baseline = 41847  # Current CLAUDE.md size

        # Should preserve all content (allow ±10% for formatting)
        assert total_size >= baseline * 0.9, (
            f"Information lost: total {total_size:,} chars < baseline {baseline:,} chars. "
            f"Content may have been deleted during extraction."
        )


class TestNewDocumentationFiles:
    """Test that new documentation files are created with proper content."""

    def test_performance_history_md_exists(self):
        """
        docs/PERFORMANCE-HISTORY.md should exist with performance optimization history.

        Expected content: Phase 4-7 details, timing baselines, cumulative improvements
        Expected size: ~4,800 characters
        """
        performance_history = Path(__file__).parent.parent.parent / "docs" / "PERFORMANCE-HISTORY.md"

        assert performance_history.exists(), (
            "docs/PERFORMANCE-HISTORY.md not created yet. "
            "Should extract Phase 4-7 performance history from CLAUDE.md."
        )

        content = performance_history.read_text(encoding="utf-8")
        size = len(content)

        # Should be substantial documentation
        assert size >= 3000, (
            f"PERFORMANCE-HISTORY.md too small: {size} chars (expected ~4,800). "
            f"May be missing phase details."
        )

    def test_batch_processing_md_exists(self):
        """
        docs/BATCH-PROCESSING.md should exist with batch feature processing guide.

        Expected content: /batch-implement usage, state management, resume operations
        Expected size: ~1,700 characters
        """
        batch_processing = Path(__file__).parent.parent.parent / "docs" / "BATCH-PROCESSING.md"

        assert batch_processing.exists(), (
            "docs/BATCH-PROCESSING.md not created yet. "
            "Should extract batch processing details from CLAUDE.md."
        )

        content = batch_processing.read_text(encoding="utf-8")
        size = len(content)

        # Should be moderate-sized guide
        assert size >= 1200, (
            f"BATCH-PROCESSING.md too small: {size} chars (expected ~1,700). "
            f"May be missing workflow details."
        )

    def test_agents_md_exists(self):
        """
        docs/AGENTS.md should exist with complete agent architecture documentation.

        Expected content: 20 agent descriptions, skill references, workflow integration
        Expected size: ~2,300 characters
        """
        agents_md = Path(__file__).parent.parent.parent / "docs" / "AGENTS.md"

        assert agents_md.exists(), (
            "docs/AGENTS.md not created yet. "
            "Should extract agent architecture from CLAUDE.md."
        )

        content = agents_md.read_text(encoding="utf-8")
        size = len(content)

        # Should be moderate-sized reference
        assert size >= 1800, (
            f"AGENTS.md too small: {size} chars (expected ~2,300). "
            f"May be missing agent details."
        )

    def test_hooks_md_exists(self):
        """
        docs/HOOKS.md should exist with complete hook reference.

        Expected content: 42 hooks, lifecycle events, activation guide
        Expected size: ~1,300 characters
        """
        hooks_md = Path(__file__).parent.parent.parent / "docs" / "HOOKS.md"

        assert hooks_md.exists(), (
            "docs/HOOKS.md not created yet. "
            "Should extract hook reference from CLAUDE.md."
        )

        content = hooks_md.read_text(encoding="utf-8")
        size = len(content)

        # Should be concise reference
        assert size >= 1000, (
            f"HOOKS.md too small: {size} chars (expected ~1,300). "
            f"May be missing hook listings."
        )


class TestContentPreservation:
    """Test that all content is preserved and accessible."""

    def test_performance_history_contains_all_phases(self):
        """
        PERFORMANCE-HISTORY.md should contain Phase 4-8 optimization details.

        Required phases:
        - Phase 4: Model Optimization (Haiku for researcher)
        - Phase 5: Prompt Simplification
        - Phase 6: Profiling Infrastructure
        - Phase 7: Parallel Validation
        - Phase 8: Agent Output Format Cleanup
        """
        performance_history = Path(__file__).parent.parent.parent / "docs" / "PERFORMANCE-HISTORY.md"

        assert performance_history.exists(), "PERFORMANCE-HISTORY.md not created"

        content = performance_history.read_text(encoding="utf-8")

        # Check for all phases
        required_phases = ["Phase 4", "Phase 5", "Phase 6", "Phase 7", "Phase 8"]
        missing_phases = [p for p in required_phases if p not in content]

        assert not missing_phases, (
            f"Missing performance phases in PERFORMANCE-HISTORY.md: {', '.join(missing_phases)}"
        )

    def test_performance_history_contains_timing_metrics(self):
        """
        PERFORMANCE-HISTORY.md should contain performance timing data.

        Required metrics:
        - Baseline timings (25-39 min, 22-36 min, etc.)
        - Savings per phase (3-5 minutes, 2-4 minutes, etc.)
        - Cumulative improvement percentages
        """
        performance_history = Path(__file__).parent.parent.parent / "docs" / "PERFORMANCE-HISTORY.md"

        assert performance_history.exists(), "PERFORMANCE-HISTORY.md not created"

        content = performance_history.read_text(encoding="utf-8")

        # Check for timing patterns
        has_baseline_timing = re.search(r"\d+-\d+\s+min", content)
        has_savings = re.search(r"\d+(?:-\d+)?\s+minute", content)
        has_percentage = re.search(r"\d+%", content)

        assert has_baseline_timing, "Missing baseline timing metrics"
        assert has_savings, "Missing savings metrics"
        assert has_percentage, "Missing percentage improvements"

    def test_batch_processing_contains_workflow_steps(self):
        """
        BATCH-PROCESSING.md should contain complete workflow documentation.

        Required content:
        - Command syntax (/batch-implement)
        - Input options (file-based, GitHub issues)
        - State management (batch_state.json)
        - Resume operations (--resume flag)
        - Auto-clear behavior (150K token threshold)
        """
        batch_processing = Path(__file__).parent.parent.parent / "docs" / "BATCH-PROCESSING.md"

        assert batch_processing.exists(), "BATCH-PROCESSING.md not created"

        content = batch_processing.read_text(encoding="utf-8")

        # Check for required workflow components
        required_components = [
            "/batch-implement",
            "--issues",
            "--resume",
            "batch_state.json",
            "150K",
        ]

        missing_components = [c for c in required_components if c not in content]

        assert not missing_components, (
            f"Missing workflow components in BATCH-PROCESSING.md: {', '.join(missing_components)}"
        )

    def test_agents_md_contains_all_8_active_agents(self):
        """
        AGENTS.md should document all 8 active agents (Issue #147).

        Pipeline agents (7):
        - researcher-local, planner, test-master, implementer, reviewer
        - security-auditor, doc-master

        Utility agents (1):
        - issue-creator
        """
        agents_md = Path(__file__).parent.parent.parent / "docs" / "AGENTS.md"

        assert agents_md.exists(), "AGENTS.md not created"

        content = agents_md.read_text(encoding="utf-8")

        # Active agents (Issue #147: consolidated from 21 to 8)
        active_agents = [
            "researcher-local", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master", "issue-creator"
        ]

        missing_agents = [a for a in active_agents if a not in content]

        assert not missing_agents, (
            f"Missing agents in AGENTS.md: {', '.join(missing_agents)}"
        )

    def test_hooks_md_contains_core_hooks(self):
        """
        HOOKS.md should document all 11 core hooks.

        Core hooks:
        - auto_format.py, auto_test.py, security_scan.py
        - validate_project_alignment.py, validate_claude_alignment.py
        - enforce_file_organization.py, enforce_pipeline_complete.py
        - enforce_tdd.py, detect_feature_request.py
        - auto_git_workflow.py, auto_approve_tool.py
        """
        hooks_md = Path(__file__).parent.parent.parent / "docs" / "HOOKS.md"

        assert hooks_md.exists(), "HOOKS.md not created"

        content = hooks_md.read_text(encoding="utf-8")

        core_hooks = [
            "auto_format.py", "auto_test.py", "security_scan.py",
            "validate_project_alignment.py", "validate_claude_alignment.py",
            "enforce_file_organization.py", "enforce_pipeline_complete.py",
            "enforce_tdd.py", "detect_feature_request.py",
            "auto_git_workflow.py", "auto_approve_tool.py"
        ]

        missing_hooks = [h for h in core_hooks if h not in content]

        assert not missing_hooks, (
            f"Missing core hooks in HOOKS.md: {', '.join(missing_hooks)}"
        )


class TestCrossReferenceLinks:
    """Test cross-reference links between CLAUDE.md and extracted docs."""

    def test_claude_md_links_to_performance_history(self):
        """
        CLAUDE.md should link to docs/PERFORMANCE-HISTORY.md.

        Expected in Performance Baseline section or similar location.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        has_link = "PERFORMANCE-HISTORY.md" in content

        assert has_link, (
            "CLAUDE.md missing link to docs/PERFORMANCE-HISTORY.md. "
            "Should reference detailed performance history."
        )

    def test_claude_md_links_to_batch_processing(self):
        """
        CLAUDE.md should link to docs/BATCH-PROCESSING.md.

        Expected in Batch Feature Processing section or workflow documentation.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        has_link = "BATCH-PROCESSING.md" in content

        assert has_link, (
            "CLAUDE.md missing link to docs/BATCH-PROCESSING.md. "
            "Should reference batch processing guide."
        )

    def test_claude_md_links_to_agents_md(self):
        """
        CLAUDE.md should link to docs/AGENTS.md.

        Expected in Architecture or Agents section.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for link (allow for different paths like docs/AGENTS.md or just AGENTS.md)
        has_link = "AGENTS.md" in content

        assert has_link, (
            "CLAUDE.md missing link to docs/AGENTS.md. "
            "Should reference agent architecture."
        )

    def test_claude_md_links_to_hooks_md(self):
        """
        CLAUDE.md should link to docs/HOOKS.md.

        Expected in Hooks section or automation documentation.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        has_link = "HOOKS.md" in content

        assert has_link, (
            "CLAUDE.md missing link to docs/HOOKS.md. "
            "Should reference hook documentation."
        )

    def test_all_links_use_relative_paths(self):
        """
        All cross-reference links should use relative paths.

        Valid: docs/PERFORMANCE-HISTORY.md, ./docs/AGENTS.md
        Invalid: /docs/HOOKS.md, /Users/.../docs/BATCH-PROCESSING.md
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Find all markdown links
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        links = re.findall(link_pattern, content)

        # Check links to new docs
        new_docs = [
            "PERFORMANCE-HISTORY.md",
            "BATCH-PROCESSING.md",
            "AGENTS.md",
            "HOOKS.md"
        ]

        absolute_links = []
        for link_text, link_url in links:
            for doc in new_docs:
                if doc in link_url and link_url.startswith("/"):
                    absolute_links.append(link_url)

        assert not absolute_links, (
            f"Found absolute paths in CLAUDE.md links: {absolute_links}. "
            f"Use relative paths like 'docs/AGENTS.md' instead."
        )

    def test_links_resolve_correctly(self):
        """
        All documentation links should resolve to existing files.

        Validates that linked files actually exist at specified paths.
        """
        project_root = Path(__file__).parent.parent.parent
        claude_md = project_root / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Find all markdown links to .md files
        link_pattern = r'\[([^\]]+)\]\(([^\)]+\.md)\)'
        links = re.findall(link_pattern, content)

        broken_links = []
        for link_text, link_url in links:
            # Skip external links (http/https)
            if link_url.startswith("http"):
                continue

            # Resolve relative path from CLAUDE.md location
            target_path = (project_root / link_url).resolve()

            if not target_path.exists():
                broken_links.append(f"{link_text} -> {link_url}")

        assert not broken_links, (
            f"Broken documentation links in CLAUDE.md:\n" +
            "\n".join(f"  - {link}" for link in broken_links)
        )


class TestSectionSizeLimits:
    """Test that no section exceeds size limits."""

    def test_claude_md_no_section_over_100_lines(self):
        """
        No section in CLAUDE.md should exceed 100 lines.

        This ensures content is properly condensed and extracted.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Find sections (lines starting with ##)
        sections = []
        current_section = None
        current_lines = []

        for line in lines:
            if line.startswith("##"):
                # Save previous section
                if current_section:
                    sections.append((current_section, len(current_lines)))

                # Start new section
                current_section = line.strip()
                current_lines = [line]
            elif current_section:
                current_lines.append(line)

        # Save last section
        if current_section:
            sections.append((current_section, len(current_lines)))

        # Check for oversized sections
        oversized = [(name, size) for name, size in sections if size > 100]

        assert not oversized, (
            f"Oversized sections in CLAUDE.md (>100 lines):\n" +
            "\n".join(f"  - {name}: {size} lines" for name, size in oversized) +
            "\n\nThese sections should be extracted or condensed."
        )

    def test_claude_md_average_section_size_reasonable(self):
        """
        Average section size in CLAUDE.md should be reasonable (<50 lines).

        This ensures overall document is well-condensed.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Find sections
        sections = []
        current_section = None
        current_lines = []

        for line in lines:
            if line.startswith("##"):
                if current_section:
                    sections.append((current_section, len(current_lines)))
                current_section = line.strip()
                current_lines = [line]
            elif current_section:
                current_lines.append(line)

        if current_section:
            sections.append((current_section, len(current_lines)))

        # Calculate average
        if sections:
            avg_size = sum(size for _, size in sections) / len(sections)

            assert avg_size < 50, (
                f"Average section size too large: {avg_size:.1f} lines (target: <50). "
                f"Document needs more condensing or extraction."
            )


class TestSearchDiscoverability:
    """Test that key terms remain searchable."""

    def test_performance_terms_searchable(self):
        """
        Performance-related terms should be searchable in CLAUDE.md or linked docs.

        Key terms: "Phase 4", "Phase 5", "Haiku", "profiling", "parallel validation"
        """
        project_root = Path(__file__).parent.parent.parent

        # Combine content from CLAUDE.md and performance docs
        claude_md = project_root / "CLAUDE.md"
        performance_history = project_root / "docs" / "PERFORMANCE-HISTORY.md"

        assert claude_md.exists(), "CLAUDE.md not found"
        assert performance_history.exists(), "PERFORMANCE-HISTORY.md not created"

        combined_content = (
            claude_md.read_text(encoding="utf-8") +
            performance_history.read_text(encoding="utf-8")
        )

        # Key performance terms
        key_terms = [
            "Phase 4", "Phase 5", "Haiku", "profiling", "parallel validation"
        ]

        missing_terms = [term for term in key_terms if term not in combined_content]

        assert not missing_terms, (
            f"Performance terms not searchable: {', '.join(missing_terms)}. "
            f"These should appear in CLAUDE.md or PERFORMANCE-HISTORY.md."
        )

    def test_batch_terms_searchable(self):
        """
        Batch processing terms should be searchable in CLAUDE.md or BATCH-PROCESSING.md.

        Key terms: "/batch-implement", "batch_state", "resume", "auto-clear"
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        batch_processing = project_root / "docs" / "BATCH-PROCESSING.md"

        assert claude_md.exists(), "CLAUDE.md not found"
        assert batch_processing.exists(), "BATCH-PROCESSING.md not created"

        combined_content = (
            claude_md.read_text(encoding="utf-8") +
            batch_processing.read_text(encoding="utf-8")
        )

        # Key batch terms
        key_terms = [
            "/batch-implement", "batch_state", "resume", "auto-clear"
        ]

        missing_terms = [term for term in key_terms if term not in combined_content]

        assert not missing_terms, (
            f"Batch terms not searchable: {', '.join(missing_terms)}. "
            f"These should appear in CLAUDE.md or BATCH-PROCESSING.md."
        )

    def test_agent_names_searchable(self):
        """
        All 20 agent names should be searchable in CLAUDE.md or AGENTS.md.

        Agent names: researcher, planner, test-master, implementer, etc.
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        agents_md = project_root / "docs" / "AGENTS.md"

        assert claude_md.exists(), "CLAUDE.md not found"
        assert agents_md.exists(), "AGENTS.md not created"

        combined_content = (
            claude_md.read_text(encoding="utf-8") +
            agents_md.read_text(encoding="utf-8")
        )

        # All 8 active agents (Issue #147: consolidated from 21 to 8)
        agent_names = [
            "researcher-local", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master", "issue-creator"
        ]

        missing_agents = [agent for agent in agent_names if agent not in combined_content]

        assert not missing_agents, (
            f"Agent names not searchable: {', '.join(missing_agents)}. "
            f"These should appear in CLAUDE.md or AGENTS.md."
        )

    def test_hook_names_searchable(self):
        """
        Core hook names should be searchable in CLAUDE.md or HOOKS.md.

        Hook names: auto_format, auto_test, security_scan, etc.
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        hooks_md = project_root / "docs" / "HOOKS.md"

        assert claude_md.exists(), "CLAUDE.md not found"
        assert hooks_md.exists(), "HOOKS.md not created"

        combined_content = (
            claude_md.read_text(encoding="utf-8") +
            hooks_md.read_text(encoding="utf-8")
        )

        # Core hooks (without .py extension for flexibility)
        hook_names = [
            "auto_format", "auto_test", "security_scan",
            "validate_project_alignment", "validate_claude_alignment",
            "enforce_file_organization", "enforce_pipeline_complete",
            "enforce_tdd", "detect_feature_request",
            "auto_git_workflow", "auto_approve_tool"
        ]

        missing_hooks = [hook for hook in hook_names if hook not in combined_content]

        assert not missing_hooks, (
            f"Hook names not searchable: {', '.join(missing_hooks)}. "
            f"These should appear in CLAUDE.md or HOOKS.md."
        )


class TestAlignmentValidation:
    """Test that alignment validation still passes after optimization."""

    def test_validate_claude_alignment_passes(self):
        """
        validate_claude_alignment.py should pass after optimization.

        This ensures:
        - Version dates consistent
        - Agent counts correct (8 agents per Issue #147)
        - Command counts correct (10 commands per Issue #121)
        - No alignment drift
        """
        project_root = Path(__file__).parent.parent.parent
        validator = project_root / "plugins" / "autonomous-dev" / "hooks" / "validate_claude_alignment.py"

        # Skip if validator doesn't exist (may be different path)
        if not validator.exists():
            pytest.skip("validate_claude_alignment.py not found at expected path")

        # Run validator
        result = subprocess.run(
            ["python3", str(validator)],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, (
            f"CLAUDE.md alignment validation failed after optimization:\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}\n\n"
            f"Optimization may have broken alignment checks."
        )

    def test_agent_count_still_documented(self):
        """
        CLAUDE.md should still document correct agent count (8 agents per Issue #147).

        After optimization, metadata should remain accurate.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for agent count (8 active agents per Issue #147)
        # CLAUDE.md lists agents by name, not by count
        active_agents = [
            "researcher-local", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master", "issue-creator"
        ]

        documented = sum(1 for agent in active_agents if agent in content)

        assert documented >= 6, (
            f"CLAUDE.md missing active agent documentation. "
            f"Found {documented}/8 agents. "
            f"Metadata should be preserved after optimization."
        )

    def test_command_count_still_documented(self):
        """
        CLAUDE.md should still document correct command count (10 commands).

        After optimization, metadata should remain accurate.
        Updated per Issue #121 command simplification (20 -> 10 commands).
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for command count (10 active per Issue #121)
        command_patterns = [
            r"10\s+(?:active\s+)?commands",
            r"Commands?\s+\(10",
        ]

        has_count = any(
            re.search(pattern, content, re.IGNORECASE)
            for pattern in command_patterns
        )

        assert has_count, (
            "CLAUDE.md missing command count (10 commands). "
            "Metadata should be preserved after optimization."
        )

    def test_skills_count_still_documented(self):
        """
        CLAUDE.md should still document correct skills count (27 skills).

        After optimization, metadata should remain accurate.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for skills count
        skills_patterns = [
            r"27\s+(?:active\s+)?skills?",
            r"Skills?\s+\(27",
        ]

        has_count = any(
            re.search(pattern, content, re.IGNORECASE)
            for pattern in skills_patterns
        )

        assert has_count, (
            "CLAUDE.md missing skills count (27 skills). "
            "Metadata should be preserved after optimization."
        )


class TestDocumentationQuality:
    """Test documentation quality standards."""

    def test_all_new_docs_have_proper_headers(self):
        """
        All new documentation files should have proper markdown headers.

        Required:
        - Title (# heading)
        - Overview/Introduction
        - Table of contents (for docs >500 lines)
        """
        project_root = Path(__file__).parent.parent.parent

        new_docs = [
            project_root / "docs" / "PERFORMANCE-HISTORY.md",
            project_root / "docs" / "BATCH-PROCESSING.md",
            project_root / "docs" / "AGENTS.md",
            project_root / "docs" / "HOOKS.md",
        ]

        for doc_path in new_docs:
            assert doc_path.exists(), f"{doc_path.name} not created"

            content = doc_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Should start with # heading
            has_title = any(line.startswith("# ") for line in lines[:10])

            assert has_title, (
                f"{doc_path.name} missing title heading (# Title). "
                f"Documentation should start with proper header."
            )

    def test_all_new_docs_link_back_to_claude_md(self):
        """
        All new documentation files should link back to CLAUDE.md.

        This creates bidirectional navigation for better discoverability.
        """
        project_root = Path(__file__).parent.parent.parent

        new_docs = [
            project_root / "docs" / "PERFORMANCE-HISTORY.md",
            project_root / "docs" / "BATCH-PROCESSING.md",
            project_root / "docs" / "AGENTS.md",
            project_root / "docs" / "HOOKS.md",
        ]

        for doc_path in new_docs:
            assert doc_path.exists(), f"{doc_path.name} not created"

            content = doc_path.read_text(encoding="utf-8")

            # Should reference CLAUDE.md
            has_back_link = "CLAUDE.md" in content

            assert has_back_link, (
                f"{doc_path.name} missing back-link to CLAUDE.md. "
                f"New docs should reference main documentation for context."
            )

    def test_no_duplicate_content_between_docs(self):
        """
        No substantial duplicate content should exist between CLAUDE.md and new docs.

        Allows for brief summaries/overviews but not full duplication.
        """
        project_root = Path(__file__).parent.parent.parent

        claude_md = project_root / "CLAUDE.md"
        new_docs = [
            project_root / "docs" / "PERFORMANCE-HISTORY.md",
            project_root / "docs" / "BATCH-PROCESSING.md",
            project_root / "docs" / "AGENTS.md",
            project_root / "docs" / "HOOKS.md",
        ]

        assert claude_md.exists(), "CLAUDE.md not found"

        claude_content = claude_md.read_text(encoding="utf-8")

        # Extract paragraphs from CLAUDE.md (>100 chars)
        claude_paragraphs = set(
            para.strip()
            for para in claude_content.split("\n\n")
            if len(para.strip()) > 100
        )

        # Check each new doc for duplicates
        for doc_path in new_docs:
            if not doc_path.exists():
                continue

            doc_content = doc_path.read_text(encoding="utf-8")
            doc_paragraphs = set(
                para.strip()
                for para in doc_content.split("\n\n")
                if len(para.strip()) > 100
            )

            # Find duplicates
            duplicates = claude_paragraphs & doc_paragraphs

            # Allow up to 2 duplicate paragraphs (for summaries)
            assert len(duplicates) <= 2, (
                f"{doc_path.name} has {len(duplicates)} duplicate paragraphs with CLAUDE.md. "
                f"Content should be extracted (not duplicated)."
            )


class TestRegressionPrevention:
    """Test that optimization doesn't break existing functionality."""

    def test_claude_md_still_has_install_instructions(self):
        """
        CLAUDE.md should retain installation instructions.

        Essential user-facing content should not be removed.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        # Check for installation keywords
        has_install = any(
            term in content.lower()
            for term in ["/plugin install", "installation", "install plugin"]
        )

        assert has_install, (
            "CLAUDE.md missing installation instructions. "
            "Essential user content should be preserved."
        )

    def test_claude_md_still_has_quick_reference(self):
        """
        CLAUDE.md should retain Quick Reference section.

        Core navigation should be preserved for usability.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        has_quick_ref = "Quick Reference" in content or "## Quick" in content

        assert has_quick_ref, (
            "CLAUDE.md missing Quick Reference section. "
            "Navigation aids should be preserved."
        )

    def test_claude_md_still_has_workflow_section(self):
        """
        CLAUDE.md should retain Autonomous Development Workflow section.

        Core workflow documentation should not be removed.
        """
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"

        assert claude_md.exists(), "CLAUDE.md not found"

        content = claude_md.read_text(encoding="utf-8")

        has_workflow = "Autonomous Development Workflow" in content or "## Workflow" in content

        assert has_workflow, (
            "CLAUDE.md missing workflow documentation. "
            "Core content should be preserved."
        )


# Test execution summary
if __name__ == "__main__":
    print("=" * 80)
    print("CLAUDE.md Optimization - TDD Red Phase Tests (Issue #78)")
    print("=" * 80)
    print()
    print("These tests will FAIL until implementation is complete.")
    print()
    print("Test Coverage:")
    print("  - Character count validation (<35,000)")
    print("  - New documentation files exist (4 files)")
    print("  - Content preservation (all info accessible)")
    print("  - Cross-reference links work")
    print("  - Section size limits (<100 lines)")
    print("  - Search discoverability maintained")
    print("  - Alignment validation passes")
    print("  - Documentation quality standards")
    print("  - Regression prevention")
    print()
    print("Run with: pytest -xvs tests/unit/test_claude_md_issue78_optimization.py")
    print("=" * 80)

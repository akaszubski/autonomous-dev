#!/usr/bin/env python3
"""
Token Reduction Tests for project-alignment-validation Skill (TDD Red Phase)

This module contains FAILING tests for validating token reduction from
extracting project-alignment-validation skill (Issue #76 Phase 8.7).

Token Reduction Target:
- 12 files total (3 agents + 5 hooks + 4 libraries)
- ~100 tokens per file average
- Total: 800-1,200 tokens saved (2-4% reduction)

Measurement Methodology:
1. Count tokens in each file (rough: 1 token ≈ 4 chars)
2. Compare against baseline before skill extraction
3. Verify progressive disclosure overhead < 100 tokens
4. Calculate total savings across all 12 files

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially.

Author: test-master agent
Date: 2025-11-16
Issue: #76 Phase 8.7
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent

# Paths
SKILL_DIR = project_root / "plugins" / "autonomous-dev" / "skills" / "project-alignment-validation"
SKILL_FILE = SKILL_DIR / "SKILL.md"
AGENTS_DIR = project_root / "plugins" / "autonomous-dev" / "agents"
HOOKS_DIR = project_root / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = project_root / "plugins" / "autonomous-dev" / "lib"

# Files that should show token reduction
ALIGNMENT_AGENTS = [
    "alignment-validator",
    "alignment-analyzer",
    "project-progress-tracker"
]

ALIGNMENT_HOOKS = [
    "validate_project_alignment.py",
    "auto_update_project_progress.py",
    "enforce_pipeline_complete.py",
    "detect_feature_request.py",
    "validate_documentation_alignment.py"
]

ALIGNMENT_LIBRARIES = [
    "alignment_assessor.py",
    "project_md_updater.py",
    "brownfield_retrofit.py",
    "migration_planner.py"
]


def count_tokens_in_file(file_path: Path) -> int:
    """
    Count approximate tokens in a file.

    Rough estimation: 1 token ≈ 4 characters
    This is conservative (actual may be 3-5 chars per token).

    Args:
        file_path: Path to file

    Returns:
        Approximate token count
    """
    content = file_path.read_text()
    return len(content) // 4


def extract_frontmatter_tokens(skill_path: Path) -> int:
    """
    Extract and count tokens in skill frontmatter.

    Args:
        skill_path: Path to SKILL.md file

    Returns:
        Frontmatter token count
    """
    content = skill_path.read_text()
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return 0
    frontmatter = parts[1]
    return len(frontmatter) // 4


def extract_full_content_tokens(skill_path: Path) -> int:
    """
    Extract and count tokens in skill full content.

    Args:
        skill_path: Path to SKILL.md file

    Returns:
        Full content token count
    """
    content = skill_path.read_text()
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return 0
    full_content = parts[2]
    return len(full_content) // 4


# ==============================================================================
# Test Suite 1: Individual File Token Reduction
# ==============================================================================


class TestIndividualFileTokenReduction:
    """Test token reduction in individual agents, hooks, and libraries."""

    @pytest.mark.parametrize("agent_name,expected_max_tokens", [
        ("alignment-validator", 750),     # Heavy user, should save ~150 tokens
        ("alignment-analyzer", 850),      # Heavy user, should save ~120 tokens
        ("project-progress-tracker", 650) # Moderate user, should save ~80 tokens
    ])
    def test_agent_token_count_reduced(self, agent_name, expected_max_tokens):
        """
        Test agent token count is reduced after skill extraction.

        Before skill extraction:
        - alignment-validator: ~900 tokens (inline checklist)
        - alignment-analyzer: ~970 tokens (inline gap methodology)
        - project-progress-tracker: ~730 tokens (inline goal alignment)

        After skill extraction:
        - alignment-validator: ~750 tokens (references skill)
        - alignment-analyzer: ~850 tokens (references skill)
        - project-progress-tracker: ~650 tokens (references skill)

        Savings: ~350 tokens across 3 agents
        """
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        token_count = count_tokens_in_file(agent_file)

        assert token_count <= expected_max_tokens, (
            f"Agent {agent_name} token count too high: {token_count}\n"
            f"Expected: ≤{expected_max_tokens} tokens after skill extraction\n"
            f"Token reduction target: ~100 tokens per agent\n"
            f"See: Issue #76 Phase 8.7"
        )

    @pytest.mark.parametrize("hook_file,expected_max_tokens", [
        ("validate_project_alignment.py", 450),     # Heavy user, save ~100 tokens
        ("auto_update_project_progress.py", 550),   # Moderate user, save ~80 tokens
        ("enforce_pipeline_complete.py", 400),      # Light user, save ~50 tokens
        ("detect_feature_request.py", 350),         # Light user, save ~50 tokens
        ("validate_documentation_alignment.py", 500) # Moderate user, save ~70 tokens
    ])
    def test_hook_token_count_reduced(self, hook_file, expected_max_tokens):
        """
        Test hook token count is reduced after skill extraction.

        Before skill extraction: Hooks had inline validation patterns
        After skill extraction: Hooks reference skill for patterns

        Savings: ~350 tokens across 5 hooks
        """
        hook_path = HOOKS_DIR / hook_file
        token_count = count_tokens_in_file(hook_path)

        assert token_count <= expected_max_tokens, (
            f"Hook {hook_file} token count too high: {token_count}\n"
            f"Expected: ≤{expected_max_tokens} tokens after skill extraction\n"
            f"Token reduction target: ~70 tokens per hook average\n"
            f"See: Issue #76 Phase 8.7"
        )

    @pytest.mark.parametrize("library_file,expected_max_tokens", [
        ("alignment_assessor.py", 800),      # Heavy user, save ~150 tokens
        ("project_md_updater.py", 650),      # Moderate user, save ~100 tokens
        ("brownfield_retrofit.py", 900),     # Moderate user, save ~80 tokens
        ("migration_planner.py", 850)        # Moderate user, save ~70 tokens
    ])
    def test_library_token_count_reduced(self, library_file, expected_max_tokens):
        """
        Test library token count is reduced after skill extraction.

        Before skill extraction: Libraries had inline assessment methodology
        After skill extraction: Libraries reference skill for methodology

        Savings: ~400 tokens across 4 libraries
        """
        library_path = LIB_DIR / library_file
        token_count = count_tokens_in_file(library_path)

        assert token_count <= expected_max_tokens, (
            f"Library {library_file} token count too high: {token_count}\n"
            f"Expected: ≤{expected_max_tokens} tokens after skill extraction\n"
            f"Token reduction target: ~100 tokens per library average\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 2: Aggregate Token Reduction
# ==============================================================================


class TestAggregateTokenReduction:
    """Test total token reduction across all 12 files."""

    def test_total_agent_token_reduction(self):
        """
        Test total token reduction across 3 agents.

        Before: ~2,600 tokens total
        After: ~2,250 tokens total
        Savings: ~350 tokens (13-15% reduction)
        """
        total_tokens = 0

        for agent_name in ALIGNMENT_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            total_tokens += count_tokens_in_file(agent_file)

        # Expected: ~2,250 tokens after skill extraction
        expected_max_tokens = 2250

        assert total_tokens <= expected_max_tokens, (
            f"Total agent tokens too high: {total_tokens}\n"
            f"Expected: ≤{expected_max_tokens} tokens across 3 agents\n"
            f"Target: ~350 tokens saved\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_total_hook_token_reduction(self):
        """
        Test total token reduction across 5 hooks.

        Before: ~2,600 tokens total
        After: ~2,250 tokens total
        Savings: ~350 tokens (13-15% reduction)
        """
        total_tokens = 0

        for hook_file in ALIGNMENT_HOOKS:
            hook_path = HOOKS_DIR / hook_file
            total_tokens += count_tokens_in_file(hook_path)

        # Expected: ~2,250 tokens after skill extraction
        expected_max_tokens = 2250

        assert total_tokens <= expected_max_tokens, (
            f"Total hook tokens too high: {total_tokens}\n"
            f"Expected: ≤{expected_max_tokens} tokens across 5 hooks\n"
            f"Target: ~350 tokens saved\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_total_library_token_reduction(self):
        """
        Test total token reduction across 4 libraries.

        Before: ~3,600 tokens total
        After: ~3,200 tokens total
        Savings: ~400 tokens (11-13% reduction)
        """
        total_tokens = 0

        for library_file in ALIGNMENT_LIBRARIES:
            library_path = LIB_DIR / library_file
            total_tokens += count_tokens_in_file(library_path)

        # Expected: ~3,200 tokens after skill extraction
        expected_max_tokens = 3200

        assert total_tokens <= expected_max_tokens, (
            f"Total library tokens too high: {total_tokens}\n"
            f"Expected: ≤{expected_max_tokens} tokens across 4 libraries\n"
            f"Target: ~400 tokens saved\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_overall_token_reduction_meets_target(self):
        """
        Test overall token reduction of 800-1,200 tokens across all 12 files.

        Before: ~8,800 tokens total (agents + hooks + libraries)
        After: ~7,700 tokens total
        Savings: ~1,100 tokens (12-14% reduction)
        """
        total_tokens = 0

        # Count agents
        for agent_name in ALIGNMENT_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            total_tokens += count_tokens_in_file(agent_file)

        # Count hooks
        for hook_file in ALIGNMENT_HOOKS:
            hook_path = HOOKS_DIR / hook_file
            total_tokens += count_tokens_in_file(hook_path)

        # Count libraries
        for library_file in ALIGNMENT_LIBRARIES:
            library_path = LIB_DIR / library_file
            total_tokens += count_tokens_in_file(library_path)

        # Expected: ~7,700 tokens after skill extraction
        expected_max_tokens = 7700

        assert total_tokens <= expected_max_tokens, (
            f"Overall total tokens too high: {total_tokens}\n"
            f"Expected: ≤{expected_max_tokens} tokens across all 12 files\n"
            f"Target: 800-1,200 tokens saved (2-4% reduction)\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 3: Progressive Disclosure Overhead
# ==============================================================================


class TestProgressiveDisclosureOverhead:
    """Test progressive disclosure overhead is minimal."""

    def test_skill_frontmatter_overhead_minimal(self):
        """
        Test skill frontmatter overhead is < 100 tokens.

        Frontmatter is always loaded (context overhead).
        Full content loads only when keywords match (no overhead).

        Target: < 100 tokens frontmatter overhead
        """
        frontmatter_tokens = extract_frontmatter_tokens(SKILL_FILE)

        assert frontmatter_tokens < 100, (
            f"Skill frontmatter overhead too high: {frontmatter_tokens} tokens\n"
            f"Expected: < 100 tokens for efficient progressive disclosure\n"
            f"This overhead is always in context\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_skill_full_content_substantial(self):
        """
        Test skill full content is substantial (on-demand load is worth it).

        Full content should be > 500 tokens (enough value to justify extraction).
        """
        full_content_tokens = extract_full_content_tokens(SKILL_FILE)

        assert full_content_tokens > 500, (
            f"Skill full content too small: {full_content_tokens} tokens\n"
            f"Expected: > 500 tokens (justify extraction effort)\n"
            f"Full content loads on-demand when keywords match\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_overhead_to_content_ratio_acceptable(self):
        """
        Test frontmatter overhead to full content ratio is acceptable.

        Overhead ratio = frontmatter_tokens / full_content_tokens
        Target: < 15% (overhead justified by on-demand loading)
        """
        frontmatter_tokens = extract_frontmatter_tokens(SKILL_FILE)
        full_content_tokens = extract_full_content_tokens(SKILL_FILE)

        overhead_ratio = frontmatter_tokens / full_content_tokens

        assert overhead_ratio < 0.15, (
            f"Progressive disclosure overhead ratio too high: {overhead_ratio:.1%}\n"
            f"Frontmatter: {frontmatter_tokens} tokens (always loaded)\n"
            f"Full content: {full_content_tokens} tokens (on-demand)\n"
            f"Expected: Overhead < 15% of full content\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 4: Token Reduction Breakdown
# ==============================================================================


class TestTokenReductionBreakdown:
    """Test detailed token reduction breakdown by category."""

    def test_agent_category_savings_breakdown(self):
        """
        Test token savings breakdown across 3 agents.

        Expected breakdown:
        - alignment-validator: ~150 tokens saved (checklist extraction)
        - alignment-analyzer: ~120 tokens saved (gap methodology extraction)
        - project-progress-tracker: ~80 tokens saved (goal alignment extraction)

        Total: ~350 tokens saved
        """
        agent_tokens = {}

        for agent_name in ALIGNMENT_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            agent_tokens[agent_name] = count_tokens_in_file(agent_file)

        # Individual targets
        assert agent_tokens["alignment-validator"] <= 750, (
            f"alignment-validator: {agent_tokens['alignment-validator']} tokens\n"
            f"Expected: ≤750 tokens (~150 saved)\n"
            f"See: Issue #76 Phase 8.7"
        )

        assert agent_tokens["alignment-analyzer"] <= 850, (
            f"alignment-analyzer: {agent_tokens['alignment-analyzer']} tokens\n"
            f"Expected: ≤850 tokens (~120 saved)\n"
            f"See: Issue #76 Phase 8.7"
        )

        assert agent_tokens["project-progress-tracker"] <= 650, (
            f"project-progress-tracker: {agent_tokens['project-progress-tracker']} tokens\n"
            f"Expected: ≤650 tokens (~80 saved)\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_library_category_savings_breakdown(self):
        """
        Test token savings breakdown across 4 libraries.

        Expected breakdown:
        - alignment_assessor.py: ~150 tokens saved (assessment methodology)
        - project_md_updater.py: ~100 tokens saved (validation patterns)
        - brownfield_retrofit.py: ~80 tokens saved (alignment checks)
        - migration_planner.py: ~70 tokens saved (gap assessment)

        Total: ~400 tokens saved
        """
        library_tokens = {}

        for library_file in ALIGNMENT_LIBRARIES:
            library_path = LIB_DIR / library_file
            library_tokens[library_file] = count_tokens_in_file(library_path)

        # Individual targets
        assert library_tokens["alignment_assessor.py"] <= 800, (
            f"alignment_assessor.py: {library_tokens['alignment_assessor.py']} tokens\n"
            f"Expected: ≤800 tokens (~150 saved)\n"
            f"See: Issue #76 Phase 8.7"
        )

        assert library_tokens["project_md_updater.py"] <= 650, (
            f"project_md_updater.py: {library_tokens['project_md_updater.py']} tokens\n"
            f"Expected: ≤650 tokens (~100 saved)\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 5: Comparison Against Baseline
# ==============================================================================


class TestBaselineComparison:
    """Test token reduction compared to baseline before skill extraction."""

    def test_total_reduction_percentage(self):
        """
        Test overall token reduction percentage.

        Baseline (before skill extraction): ~8,800 tokens
        After skill extraction: ~7,700 tokens
        Reduction: ~1,100 tokens = 12.5% reduction
        Target: 2-4% minimum (we exceed target significantly!)
        """
        total_tokens = 0

        # Count all 12 files
        for agent_name in ALIGNMENT_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            total_tokens += count_tokens_in_file(agent_file)

        for hook_file in ALIGNMENT_HOOKS:
            hook_path = HOOKS_DIR / hook_file
            total_tokens += count_tokens_in_file(hook_path)

        for library_file in ALIGNMENT_LIBRARIES:
            library_path = LIB_DIR / library_file
            total_tokens += count_tokens_in_file(library_path)

        # Baseline (estimated before skill extraction)
        baseline_tokens = 8800

        # Calculate reduction percentage
        if total_tokens < baseline_tokens:
            reduction_percentage = ((baseline_tokens - total_tokens) / baseline_tokens) * 100
        else:
            reduction_percentage = 0

        assert reduction_percentage >= 2.0, (
            f"Token reduction percentage too low: {reduction_percentage:.1f}%\n"
            f"Baseline: {baseline_tokens} tokens\n"
            f"After: {total_tokens} tokens\n"
            f"Saved: {baseline_tokens - total_tokens} tokens\n"
            f"Target: ≥2.0% reduction (800-1,200 tokens)\n"
            f"See: Issue #76 Phase 8.7"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

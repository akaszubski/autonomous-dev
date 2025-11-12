#!/usr/bin/env python3
"""
Token Measurement Tests for Issue #66 Phase 8.4 (FAILING - Red Phase)

Tests token counting and reduction measurement for documentation-guide skill
enhancement (Issue #66 - Phase 8.4).

Token Reduction Strategy:
1. Extract ~58 lines from doc-master.md (parity validation checklist)
2. Extract documentation guidance from 8 other agents
3. Move content to documentation-guide skill (progressive disclosure)
4. Agents reference skill instead of inline content

Expected Savings:
- doc-master.md: ~70-80 tokens (primary extraction)
- Other 8 agents: ~25-30 tokens each (~200 tokens total)
- Total: ~280 tokens (4-6% reduction)

Test Coverage:
1. Baseline token measurement (before extraction)
2. Post-extraction token measurement
3. Token reduction calculation
4. Per-agent token analysis
5. Skill content size verification

Following TDD principles:
- Write tests FIRST (red phase)
- Tests should FAIL until implementation is complete
- Tests measure actual token counts (not estimates)
- Tests validate expected reduction is achieved

Author: test-master agent
Date: 2025-11-12
Issue: #66 (Phase 8.4)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pytest


# Constants
AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"
SKILL_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "documentation-guide"
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"

# Agents affected by Phase 8.4 extraction
PHASE_84_AGENTS = [
    "doc-master",          # Primary extraction (~70-80 tokens)
    "setup-wizard",        # References docs standards (~25 tokens)
    "reviewer",            # References docstring standards (~25 tokens)
    "issue-creator",       # References documentation format (~25 tokens)
    "pr-description-generator",  # References PR description format (~25 tokens)
    "alignment-analyzer",  # References parity validation (~30 tokens)
    "project-bootstrapper",  # References readme structure (~25 tokens)
    "project-status-analyzer",  # References documentation parity (~25 tokens)
    "implementer"          # References docstring templates (~30 tokens)
]

# Expected token savings (conservative estimates)
EXPECTED_SAVINGS_PER_AGENT = {
    "doc-master": 75,           # Primary extraction (parity checklist ~58 lines)
    "setup-wizard": 25,
    "reviewer": 25,
    "issue-creator": 25,
    "pr-description-generator": 25,
    "alignment-analyzer": 30,
    "project-bootstrapper": 25,
    "project-status-analyzer": 25,
    "implementer": 30
}

EXPECTED_TOTAL_SAVINGS = sum(EXPECTED_SAVINGS_PER_AGENT.values())  # ~280 tokens


# ============================================================================
# Test 1: Token Measurement Script Exists
# ============================================================================


class TestTokenMeasurementInfrastructure:
    """Test token measurement infrastructure exists and works."""

    def test_measure_agent_tokens_script_exists(self):
        """Test measure_agent_tokens.py script exists for token counting."""
        script_file = SCRIPTS_DIR / "measure_agent_tokens.py"

        assert script_file.exists(), (
            f"Token measurement script not found: {script_file}\n"
            f"Expected: scripts/measure_agent_tokens.py for token counting\n"
            f"This script is used to measure token reduction in Phase 8.4"
        )

    def test_token_measurement_script_has_required_functions(self):
        """Test measure_agent_tokens.py has functions for baseline and post-extraction measurement."""
        script_file = SCRIPTS_DIR / "measure_agent_tokens.py"

        if script_file.exists():
            content = script_file.read_text()

            required_functions = [
                "measure_baseline_tokens",
                "measure_agent_tokens",
                "calculate_token_reduction"
            ]

            missing_functions = [func for func in required_functions if f"def {func}" not in content]

            assert len(missing_functions) == 0, (
                f"Token measurement script missing required functions:\n"
                f"Missing: {missing_functions}\n"
                f"Expected functions: {required_functions}\n"
                f"These functions are needed to measure Phase 8.4 token reduction"
            )


# ============================================================================
# Test 2: Baseline Token Measurement
# ============================================================================


class TestBaselineTokenMeasurement:
    """Test baseline token measurement before Phase 8.4 extraction."""

    def test_measure_baseline_tokens_for_phase84_agents(self):
        """Test baseline token measurement for all 9 Phase 8.4 agents."""
        # This will fail until measure_agent_tokens.py has Phase 8.4 support
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import measure_baseline_tokens
        except ImportError:
            pytest.fail(
                "Cannot import measure_baseline_tokens function\n"
                "Expected: scripts/measure_agent_tokens.py exists with this function"
            )

        baseline = measure_baseline_tokens()

        # Should include all Phase 8.4 agents
        for agent_name in PHASE_84_AGENTS:
            assert agent_name in baseline, (
                f"Missing baseline for Phase 8.4 agent: {agent_name}\n"
                f"Expected: Baseline token count for {agent_name}.md"
            )
            assert baseline[agent_name] > 0, (
                f"Invalid token count for {agent_name}: {baseline[agent_name]}\n"
                f"Expected: Positive token count"
            )

    def test_doc_master_baseline_includes_parity_checklist(self):
        """Test doc-master baseline includes parity validation checklist tokens."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import measure_agent_tokens
        except ImportError:
            pytest.skip("measure_agent_tokens not available yet")

        doc_master_file = AGENTS_DIR / "doc-master.md"
        if not doc_master_file.exists():
            pytest.skip("doc-master.md not found")

        content = doc_master_file.read_text()

        # Check if parity checklist is present (should be in baseline)
        checklist_indicators = [
            "## Documentation Parity Validation Checklist",
            "1. **Run Parity Validator**",
            "2. **Check Version Consistency**"
        ]

        has_checklist = any(indicator in content for indicator in checklist_indicators)

        assert has_checklist, (
            "doc-master.md baseline should include parity validation checklist\n"
            "This checklist will be extracted to skill in implementation phase\n"
            "Expected: ~58 lines in doc-master.md (lines 44-103)"
        )

    def test_baseline_total_tokens_substantial(self):
        """Test baseline total for Phase 8.4 agents is substantial."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import measure_baseline_tokens
        except ImportError:
            pytest.skip("measure_baseline_tokens not available yet")

        baseline = measure_baseline_tokens()

        # Calculate total baseline for Phase 8.4 agents
        phase84_total = sum(baseline.get(agent, 0) for agent in PHASE_84_AGENTS)

        assert phase84_total > 5000, (
            f"Phase 8.4 baseline too low: {phase84_total} tokens\n"
            f"Expected: > 5,000 tokens (9 agents with documentation guidance)\n"
            f"This validates we have content to extract"
        )


# ============================================================================
# Test 3: Post-Extraction Token Measurement
# ============================================================================


class TestPostExtractionTokenMeasurement:
    """Test token measurement after Phase 8.4 extraction."""

    def test_measure_post_extraction_tokens_for_phase84_agents(self):
        """Test post-extraction token measurement for Phase 8.4 agents."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import measure_agent_tokens
        except ImportError:
            pytest.fail(
                "Cannot import measure_agent_tokens function\n"
                "Expected: scripts/measure_agent_tokens.py with this function"
            )

        # Measure tokens for each Phase 8.4 agent
        post_extraction = {}
        for agent_name in PHASE_84_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            if agent_file.exists():
                post_extraction[agent_name] = measure_agent_tokens(agent_file)

        # Should have measurements for all agents
        assert len(post_extraction) == len(PHASE_84_AGENTS), (
            f"Missing post-extraction measurements\n"
            f"Expected: Measurements for all {len(PHASE_84_AGENTS)} Phase 8.4 agents\n"
            f"Got: {len(post_extraction)} measurements"
        )

    def test_doc_master_post_extraction_removed_parity_checklist(self):
        """Test doc-master.md removed parity validation checklist after extraction."""
        doc_master_file = AGENTS_DIR / "doc-master.md"

        if not doc_master_file.exists():
            pytest.skip("doc-master.md not found")

        content = doc_master_file.read_text()

        # Parity checklist should be removed after extraction
        checklist_indicators = [
            "## Documentation Parity Validation Checklist",
            "1. **Run Parity Validator**",
            "2. **Check Version Consistency**"
        ]

        has_checklist = any(indicator in content for indicator in checklist_indicators)

        assert not has_checklist, (
            "doc-master.md should have removed parity validation checklist\n"
            "Expected: Checklist extracted to skills/documentation-guide/docs/parity-validation.md\n"
            "Post-extraction: Agent should reference skill instead"
        )

    def test_agents_reference_skill_instead_of_inline_content(self):
        """Test Phase 8.4 agents reference documentation-guide skill instead of inline content."""
        for agent_name in PHASE_84_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"

            if not agent_file.exists():
                continue

            content = agent_file.read_text()

            assert "documentation-guide" in content, (
                f"{agent_name}.md should reference documentation-guide skill\n"
                f"Expected: Agent references skill instead of inline content\n"
                f"Post-extraction: Agents use skill via progressive disclosure"
            )


# ============================================================================
# Test 4: Token Reduction Calculation
# ============================================================================


class TestTokenReductionCalculation:
    """Test token reduction calculation for Phase 8.4."""

    def test_calculate_token_reduction_for_phase84(self):
        """Test token reduction calculation matches expected savings."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import calculate_token_reduction
        except ImportError:
            pytest.fail(
                "Cannot import calculate_token_reduction function\n"
                "Expected: scripts/measure_agent_tokens.py with this function"
            )

        # Calculate reduction for Phase 8.4
        reduction = calculate_token_reduction(agents=PHASE_84_AGENTS)

        assert "total_reduction" in reduction, (
            "Token reduction calculation should include total_reduction field"
        )

        total_reduction = reduction["total_reduction"]

        assert total_reduction >= EXPECTED_TOTAL_SAVINGS * 0.9, (
            f"Token reduction below expected savings\n"
            f"Actual reduction: {total_reduction} tokens\n"
            f"Expected: >= {EXPECTED_TOTAL_SAVINGS * 0.9} tokens (90% of {EXPECTED_TOTAL_SAVINGS})\n"
            f"Phase 8.4: Extract documentation guidance to skill"
        )

    def test_doc_master_token_reduction_significant(self):
        """Test doc-master.md has significant token reduction (primary extraction)."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import calculate_token_reduction
        except ImportError:
            pytest.skip("calculate_token_reduction not available yet")

        reduction = calculate_token_reduction(agents=["doc-master"])

        if "per_agent" in reduction and "doc-master" in reduction["per_agent"]:
            doc_master_reduction = reduction["per_agent"]["doc-master"]

            expected_doc_master_savings = EXPECTED_SAVINGS_PER_AGENT["doc-master"]

            assert doc_master_reduction >= expected_doc_master_savings * 0.9, (
                f"doc-master token reduction below expected\n"
                f"Actual: {doc_master_reduction} tokens\n"
                f"Expected: >= {expected_doc_master_savings * 0.9} tokens\n"
                f"doc-master: Primary extraction of parity validation checklist (~58 lines)"
            )

    def test_phase84_percentage_reduction_measurable(self):
        """Test Phase 8.4 token reduction is 4-6% of documentation guidance."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import calculate_token_reduction, measure_baseline_tokens
        except ImportError:
            pytest.skip("Token measurement functions not available yet")

        baseline = measure_baseline_tokens()
        reduction = calculate_token_reduction(agents=PHASE_84_AGENTS)

        baseline_total = sum(baseline.get(agent, 0) for agent in PHASE_84_AGENTS)
        reduction_total = reduction.get("total_reduction", 0)

        percentage_reduction = (reduction_total / baseline_total) * 100 if baseline_total > 0 else 0

        assert percentage_reduction >= 4.0, (
            f"Token reduction percentage below expected\n"
            f"Actual: {percentage_reduction:.1f}%\n"
            f"Expected: >= 4.0% (4-6% target)\n"
            f"Baseline: {baseline_total} tokens\n"
            f"Reduction: {reduction_total} tokens"
        )


# ============================================================================
# Test 5: Per-Agent Token Analysis
# ============================================================================


class TestPerAgentTokenAnalysis:
    """Test per-agent token analysis for Phase 8.4."""

    @pytest.mark.parametrize("agent_name", PHASE_84_AGENTS)
    def test_agent_token_reduction_measurable(self, agent_name):
        """Test each Phase 8.4 agent has measurable token reduction."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import calculate_token_reduction
        except ImportError:
            pytest.skip("calculate_token_reduction not available yet")

        reduction = calculate_token_reduction(agents=[agent_name])

        if "per_agent" in reduction and agent_name in reduction["per_agent"]:
            agent_reduction = reduction["per_agent"][agent_name]

            expected_reduction = EXPECTED_SAVINGS_PER_AGENT.get(agent_name, 20)

            assert agent_reduction >= expected_reduction * 0.8, (
                f"{agent_name}.md token reduction below expected\n"
                f"Actual: {agent_reduction} tokens\n"
                f"Expected: >= {expected_reduction * 0.8} tokens (80% of {expected_reduction})\n"
                f"Phase 8.4: Extract documentation guidance to skill"
            )

    def test_all_agents_have_positive_reduction(self):
        """Test all Phase 8.4 agents have positive token reduction."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import calculate_token_reduction
        except ImportError:
            pytest.skip("calculate_token_reduction not available yet")

        reduction = calculate_token_reduction(agents=PHASE_84_AGENTS)

        if "per_agent" not in reduction:
            pytest.fail("Token reduction should include per_agent breakdown")

        negative_reductions = []
        for agent_name in PHASE_84_AGENTS:
            if agent_name in reduction["per_agent"]:
                agent_reduction = reduction["per_agent"][agent_name]
                if agent_reduction <= 0:
                    negative_reductions.append(f"{agent_name}: {agent_reduction}")

        assert len(negative_reductions) == 0, (
            f"Some agents have non-positive token reduction:\n"
            f"{chr(10).join(negative_reductions)}\n"
            f"Expected: All agents have positive reduction (content extracted to skill)"
        )


# ============================================================================
# Test 6: Skill Content Size Verification
# ============================================================================


class TestSkillContentSizeVerification:
    """Test skill content size is reasonable for progressive disclosure."""

    def test_skill_docs_directory_has_content(self):
        """Test skills/documentation-guide/docs/ contains documentation files."""
        docs_dir = SKILL_DIR / "docs"

        assert docs_dir.exists(), "docs/ directory not found in documentation-guide skill"

        doc_files = list(docs_dir.glob("*.md"))

        assert len(doc_files) >= 4, (
            f"docs/ directory should contain 4 documentation files\n"
            f"Found: {len(doc_files)} files\n"
            f"Expected files: parity-validation.md, changelog-format.md, "
            f"readme-structure.md, docstring-standards.md"
        )

    def test_skill_templates_directory_has_content(self):
        """Test skills/documentation-guide/templates/ contains template files."""
        templates_dir = SKILL_DIR / "templates"

        assert templates_dir.exists(), "templates/ directory not found in documentation-guide skill"

        template_files = list(templates_dir.glob("*"))

        assert len(template_files) >= 3, (
            f"templates/ directory should contain 3 template files\n"
            f"Found: {len(template_files)} files\n"
            f"Expected files: docstring-template.py, readme-template.md, changelog-template.md"
        )

    def test_skill_content_size_appropriate_for_progressive_disclosure(self):
        """Test skill content size appropriate for progressive disclosure."""
        docs_dir = SKILL_DIR / "docs"
        templates_dir = SKILL_DIR / "templates"

        # Calculate total skill content size
        total_size = 0

        if docs_dir.exists():
            for doc_file in docs_dir.glob("*.md"):
                total_size += len(doc_file.read_text())

        if templates_dir.exists():
            for template_file in templates_dir.glob("*"):
                if template_file.is_file():
                    total_size += len(template_file.read_text())

        # Skill content should be substantial (extracted content)
        assert total_size > 2000, (
            f"Skill content too small: {total_size} bytes\n"
            f"Expected: > 2,000 bytes (extracted documentation guidance)\n"
            f"Phase 8.4: ~280 tokens ≈ 1,120 bytes (4 bytes/token average)"
        )

        # But not too large (should be focused on documentation)
        assert total_size < 50000, (
            f"Skill content too large: {total_size} bytes\n"
            f"Expected: < 50,000 bytes (focused documentation guidance)\n"
            f"Progressive disclosure: Keep content focused and scannable"
        )


# ============================================================================
# Test 7: Token Reduction Report Generation
# ============================================================================


class TestTokenReductionReportGeneration:
    """Test token reduction report generation for Phase 8.4."""

    def test_generate_phase84_token_reduction_report(self):
        """Test generation of Phase 8.4 token reduction report."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import generate_token_report
        except ImportError:
            pytest.skip("generate_token_report not available yet")

        # Generate report for Phase 8.4
        report = generate_token_report(
            agents=PHASE_84_AGENTS,
            phase="Phase 8.4",
            issue="#66"
        )

        # Report should include key metrics
        required_fields = ["phase", "issue", "total_baseline", "total_post_extraction", "total_reduction"]
        missing_fields = [field for field in required_fields if field not in report]

        assert len(missing_fields) == 0, (
            f"Token reduction report missing required fields:\n"
            f"Missing: {missing_fields}\n"
            f"Expected: {required_fields}"
        )

    def test_token_reduction_report_includes_per_agent_breakdown(self):
        """Test token reduction report includes per-agent breakdown."""
        sys.path.insert(0, str(SCRIPTS_DIR))

        try:
            from measure_agent_tokens import generate_token_report
        except ImportError:
            pytest.skip("generate_token_report not available yet")

        report = generate_token_report(
            agents=PHASE_84_AGENTS,
            phase="Phase 8.4",
            issue="#66"
        )

        assert "per_agent" in report, (
            "Token reduction report should include per-agent breakdown\n"
            "Expected: per_agent field with breakdown for each agent"
        )

        # Should have breakdown for all Phase 8.4 agents
        per_agent = report.get("per_agent", {})
        assert len(per_agent) == len(PHASE_84_AGENTS), (
            f"Per-agent breakdown incomplete\n"
            f"Expected: Breakdown for {len(PHASE_84_AGENTS)} agents\n"
            f"Got: {len(per_agent)} agents"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

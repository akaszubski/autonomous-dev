#!/usr/bin/env python3
"""Regression test ensuring plan-critic agent maintains proper output structure.

This test locks the structural enforcement added to prevent verdict-only outputs
(Issue #1272). The plan-critic agent MUST require substantive critique paragraphs
before any verdict, with verdict templates appearing at the END of the prompt.
"""

from pathlib import Path

import pytest

# Resolve project root: tests/regression/test_*.py -> parents[2] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

PLAN_CRITIC_AGENT = (
    PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "plan-critic.md"
)


class TestPlanCriticStructuralEnforcement:
    """Regression: plan-critic.md MUST maintain structural enforcement against verdict-only output (#1272)."""

    def test_plan_critic_agent_file_exists(self) -> None:
        """plan-critic.md must exist at the expected path."""
        assert PLAN_CRITIC_AGENT.exists(), f"plan-critic.md not found at {PLAN_CRITIC_AGENT}"

    def test_structural_enforcement_section_exists(self) -> None:
        """plan-critic.md must contain STRUCTURAL ENFORCEMENT section with anti-ghost language.
        
        Locks Issue #1272: plan-critic agent must explicitly forbid verdict-only outputs.
        """
        content = PLAN_CRITIC_AGENT.read_text()
        
        # Check for the STRUCTURAL ENFORCEMENT section
        assert "## STRUCTURAL ENFORCEMENT: Critique Before Verdict" in content, (
            "plan-critic.md missing '## STRUCTURAL ENFORCEMENT: Critique Before Verdict' section"
        )
        
        # Check for explicit anti-ghost language
        assert "You MUST output substantive critique paragraphs BEFORE any verdict" in content, (
            "plan-critic.md missing explicit requirement for critique before verdict"
        )
        
        # Check for FORBIDDEN rules about verdict-only output
        assert "You MUST NOT emit a verdict line without preceding critique paragraphs" in content, (
            "plan-critic.md missing FORBIDDEN rule against verdict without critique"
        )
        
        assert "verdict-only output is invalid" in content.lower(), (
            "plan-critic.md missing explicit statement that verdict-only output is INVALID"
        )

    def test_output_format_contract_requires_ordering(self) -> None:
        """Output Format Contract must specify exact ordering with verdict LAST.
        
        Locks Issue #1272: verdict must come after critique paragraphs, not before.
        """
        content = PLAN_CRITIC_AGENT.read_text()
        
        # Check Output Format Contract section exists
        assert "## Output Format Contract (REQUIRED)" in content, (
            "plan-critic.md missing '## Output Format Contract (REQUIRED)' section"
        )
        
        # Check that ordering is explicit
        assert "IN THIS EXACT ORDER" in content, (
            "Output Format Contract must specify 'IN THIS EXACT ORDER'"
        )
        
        assert "The verdict line MUST appear LAST" in content, (
            "Output Format Contract must explicitly state verdict appears LAST"
        )

    def test_verdict_templates_appear_after_critique_instructions(self) -> None:
        """Verdict format templates must appear AFTER all critique instructions.
        
        Locks Issue #1272: verdict templates appearing too early in the prompt
        creates ambiguity that allows agents to skip critique and emit verdict-only.
        """
        content = PLAN_CRITIC_AGENT.read_text()
        lines = content.split('\n')
        
        # Find key section positions
        structural_enforcement_line = -1
        output_format_line = -1
        critique_axes_line = -1
        verdict_templates_line = -1
        forbidden_behaviors_line = -1
        
        for i, line in enumerate(lines):
            if "## STRUCTURAL ENFORCEMENT" in line:
                structural_enforcement_line = i
            elif "## Output Format Contract" in line:
                output_format_line = i
            elif "## Critique Axes" in line:
                critique_axes_line = i
            elif "## Verdict Format Templates" in line:
                verdict_templates_line = i
            elif "## FORBIDDEN Behaviors" in line:
                forbidden_behaviors_line = i
        
        # All sections must exist
        assert structural_enforcement_line > 0, "STRUCTURAL ENFORCEMENT section not found"
        assert output_format_line > 0, "Output Format Contract section not found"
        assert critique_axes_line > 0, "Critique Axes section not found"
        assert verdict_templates_line > 0, "Verdict Format Templates section not found"
        assert forbidden_behaviors_line > 0, "FORBIDDEN Behaviors section not found"
        
        # Verdict templates must come AFTER all critique instruction sections
        assert verdict_templates_line > structural_enforcement_line, (
            f"Verdict Format Templates (line {verdict_templates_line}) must appear "
            f"AFTER STRUCTURAL ENFORCEMENT (line {structural_enforcement_line})"
        )
        
        assert verdict_templates_line > output_format_line, (
            f"Verdict Format Templates (line {verdict_templates_line}) must appear "
            f"AFTER Output Format Contract (line {output_format_line})"
        )
        
        assert verdict_templates_line > critique_axes_line, (
            f"Verdict Format Templates (line {verdict_templates_line}) must appear "
            f"AFTER Critique Axes (line {critique_axes_line})"
        )
        
        assert verdict_templates_line > forbidden_behaviors_line, (
            f"Verdict Format Templates (line {verdict_templates_line}) must appear "
            f"AFTER FORBIDDEN Behaviors (line {forbidden_behaviors_line})"
        )
        
        # Verdict templates should be in the last 45% of the file
        # (prevents them from appearing too early and creating ambiguity)
        template_position_ratio = verdict_templates_line / len(lines)
        assert template_position_ratio > 0.55, (
            f"Verdict Format Templates appear too early in file "
            f"(line {verdict_templates_line} of {len(lines)}, ratio {template_position_ratio:.2f}). "
            f"Should be in last 45% of file (ratio > 0.55) to avoid ambiguity."
        )

    def test_forbidden_behaviors_includes_verdict_only_prohibition(self) -> None:
        """FORBIDDEN Behaviors section must explicitly prohibit verdict-only output.
        
        Locks Issue #1272: the prohibition must be in the FORBIDDEN list, not just
        mentioned elsewhere.
        """
        content = PLAN_CRITIC_AGENT.read_text()
        
        # Extract just the FORBIDDEN Behaviors section
        lines = content.split('\n')
        forbidden_start = -1
        forbidden_end = -1
        
        for i, line in enumerate(lines):
            if "## FORBIDDEN Behaviors" in line:
                forbidden_start = i
            elif forbidden_start > 0 and line.startswith("##") and i > forbidden_start:
                forbidden_end = i
                break
        
        if forbidden_end == -1:
            forbidden_end = len(lines)
        
        forbidden_section = '\n'.join(lines[forbidden_start:forbidden_end])
        
        # Check for explicit prohibition in the FORBIDDEN list
        assert "You MUST NOT emit a verdict without substantive critique paragraphs" in forbidden_section, (
            "FORBIDDEN Behaviors section missing explicit prohibition of verdict without critique"
        )

    def test_minimum_critique_paragraphs_specified(self) -> None:
        """Output contract must specify minimum number of critique paragraphs.
        
        Locks Issue #1272: vague requirements like "some critique" are insufficient.
        Must specify concrete minimum (three paragraphs).
        """
        content = PLAN_CRITIC_AGENT.read_text()
        
        # Check for "three" or "3" paragraphs requirement
        assert (
            "Three or more paragraphs of substantive critique" in content
            or "three paragraphs of detailed critique" in content.lower()
            or "at least three paragraphs" in content.lower()
        ), "plan-critic.md must specify minimum of three critique paragraphs"

    def test_composite_score_comes_after_critique(self) -> None:
        """Output Format Contract must specify composite score comes AFTER critique.
        
        Locks Issue #1272: score must follow critique, not precede it.
        """
        content = PLAN_CRITIC_AGENT.read_text()
        
        # Look for ordering specification in Output Format Contract
        output_section_start = content.find("## Output Format Contract")
        output_section_end = content.find("## ", output_section_start + 20)
        if output_section_end == -1:
            output_section_end = len(content)
        
        output_section = content[output_section_start:output_section_end]
        
        # Check that composite score is specified to come AFTER paragraphs
        assert "comes AFTER the critique paragraphs" in output_section or "this comes AFTER" in output_section, (
            "Output Format Contract must explicitly state composite score comes AFTER critique paragraphs"
        )
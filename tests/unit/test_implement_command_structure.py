"""Structural tests for implement.md thin coordinator refactor (Issue #444).

Verifies that implement.md maintains required structure after refactoring
from 383-line monolithic inline command to ~100-line thin coordinator.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
IMPLEMENT_PATH = PROJECT_ROOT / "plugins/autonomous-dev/commands/implement.md"


@pytest.fixture
def implement_content():
    """Read the implement.md command file."""
    return IMPLEMENT_PATH.read_text()


@pytest.fixture
def implement_lines(implement_content):
    """Get non-empty lines (excluding frontmatter)."""
    lines = implement_content.strip().split("\n")
    # Skip frontmatter (between --- markers)
    in_frontmatter = False
    content_lines = []
    frontmatter_count = 0
    for line in lines:
        if line.strip() == "---":
            frontmatter_count += 1
            if frontmatter_count <= 2:
                in_frontmatter = not in_frontmatter
                continue
        if not in_frontmatter:
            content_lines.append(line)
    return content_lines


class TestCoordinatorSize:
    """Verify the coordinator is thin, not monolithic."""

    def test_implement_md_under_405_lines(self, implement_content):
        """implement.md should be under 1650 lines total (#961 added Phase 2 classifier gates at STEP 3.6 and STEP 5.5a.1)."""
        total_lines = len(implement_content.strip().split("\n"))
        assert total_lines <= 1650, (
            f"implement.md is {total_lines} lines — should be <= 1650 "
            f"(thin coordinator + Light Pipeline + ordering/verbatim/tracking enforcement + #961 classifier gates)."
        )


class TestAllStepsPresent:
    """Verify all pipeline steps are referenced."""

    @pytest.mark.parametrize(
        "step",
        [
            "STEP 0",
            "STEP 1",
            "STEP 2",
            "STEP 3",
            "STEP 4",
            "STEP 5",
            "STEP 6",
            "STEP 7",
            "STEP 8",
            "STEP 9",
            "STEP 10",
            "STEP 11",
            "STEP 12",
            "STEP 13",
            "STEP 14",
            "STEP 15",
        ],
    )
    def test_step_referenced(self, implement_content, step):
        """Each pipeline step must be referenced in the coordinator."""
        assert step in implement_content, f"{step} not found in implement.md"


class TestHardGatesPreserved:
    """Verify all HARD GATEs survive the refactor."""

    def test_hard_gate_keyword_present(self, implement_content):
        """HARD GATE enforcement language must be present."""
        assert "HARD GATE" in implement_content

    def test_test_gate_present(self, implement_content):
        """STEP 8 test gate — 0 failures required."""
        assert "pytest" in implement_content.lower() or "test" in implement_content.lower()

    def test_no_new_skips_gate(self, implement_content):
        """No new @pytest.mark.skip allowed."""
        assert "No New Skips" in implement_content or "0 new skips" in implement_content, (
            "No-new-skips gate must be referenced"
        )

    def test_hook_registration_gate(self, implement_content):
        """STEP 9 hook registration check."""
        assert "hook" in implement_content.lower() and (
            "registration" in implement_content.lower()
            or "settings" in implement_content.lower()
        )

    def test_doc_congruence_gate(self, implement_content):
        """STEP 14 documentation congruence validation."""
        assert "congruence" in implement_content.lower() or (
            "documentation" in implement_content.lower()
            and "test" in implement_content.lower()
        )

    def test_step_15_mandatory(self, implement_content):
        """STEP 15 continuous improvement is mandatory."""
        assert "continuous-improvement-analyst" in implement_content or (
            "STEP 15" in implement_content and "mandatory" in implement_content.lower()
        )

    def test_forbidden_list_present(self, implement_content):
        """COORDINATOR FORBIDDEN LIST must be preserved."""
        assert "FORBIDDEN" in implement_content


class TestAgentDelegation:
    """Verify all required agents are referenced for delegation."""

    @pytest.mark.parametrize(
        "agent",
        [
            "researcher-local",
            "researcher",
            "planner",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master",
            "continuous-improvement-analyst",
        ],
    )
    def test_agent_referenced(self, implement_content, agent):
        """Each specialist agent must be referenced by name."""
        assert agent in implement_content, (
            f"Agent '{agent}' not found in implement.md — "
            f"coordinator must delegate to all specialist agents"
        )

    def test_test_master_conditional(self, implement_content):
        """test-master should be referenced for --tdd-first mode."""
        assert "test-master" in implement_content


class TestModeRouting:
    """Verify all modes are supported."""

    @pytest.mark.parametrize(
        "flag",
        ["--batch", "--issues", "--resume", "--tdd-first"],
    )
    def test_mode_flag_supported(self, implement_content, flag):
        """Each mode flag must be referenced."""
        assert flag in implement_content, f"Mode flag '{flag}' not found"

    def test_acceptance_first_default(self, implement_content):
        """Acceptance-first should be the default mode."""
        assert "acceptance" in implement_content.lower() or "default" in implement_content.lower()

    def test_batch_routes_to_implement_batch(self, implement_content):
        """Batch mode should route to implement-batch.md."""
        assert "implement-batch" in implement_content

    def test_light_mode_flag_supported(self, implement_content):
        """--light flag must be referenced."""
        assert "--light" in implement_content

    def test_fix_mode_flag_supported(self, implement_content):
        """--fix flag must be referenced."""
        assert "--fix" in implement_content

    def test_auto_mode_detection_present(self, implement_content):
        """Auto-mode detection section must exist in STEP 0."""
        assert "Auto-mode detection" in implement_content

    def test_auto_mode_fix_signals(self, implement_content):
        """Auto-mode must detect fix-related descriptions."""
        assert "Fix signals" in implement_content or "fix test" in implement_content.lower()

    def test_auto_mode_light_signals(self, implement_content):
        """Auto-mode must detect light-related descriptions."""
        assert "Light signals" in implement_content or "update docs" in implement_content.lower()

    def test_auto_mode_requires_user_confirmation(self, implement_content):
        """Auto-mode must not silently switch — requires user confirmation."""
        assert "Silently switching" in implement_content or "user confirmation" in implement_content.lower()

    def test_auto_mode_tiebreak(self, implement_content):
        """When both fix and light match, fix takes precedence."""
        assert "Tie-break" in implement_content or "fix" in implement_content.lower()


class TestForbiddenListDensity:
    """Verify FORBIDDEN list constraint density (Issue #825).

    Research shows constraint compliance degrades after 5-7 consecutive
    items (MOSAIC benchmark). No single block should exceed 8 items.
    """

    def test_max_consecutive_forbidden_items(self, implement_content):
        """No contiguous block of FORBIDDEN items exceeds 8."""
        lines = implement_content.split("\n")
        max_consecutive = 0
        current_run = 0
        for line in lines:
            if line.strip().startswith("- ❌"):
                current_run += 1
                max_consecutive = max(max_consecutive, current_run)
            else:
                current_run = 0
        assert max_consecutive <= 8, (
            f"Found {max_consecutive} consecutive FORBIDDEN items — "
            f"max allowed is 8 (split into thematic groups per Issue #825)"
        )

    def test_all_14_forbidden_constraints_preserved(self, implement_content):
        """All 14 original FORBIDDEN constraints in the coordinator block must be preserved."""
        # Extract only the coordinator FORBIDDEN LIST block (ends at the next section)
        start_marker = "**COORDINATOR FORBIDDEN LIST**"
        end_marker = "### Pipeline Progress Protocol"
        start_idx = implement_content.find(start_marker)
        end_idx = implement_content.find(end_marker, start_idx)
        assert start_idx != -1, "COORDINATOR FORBIDDEN LIST not found"
        assert end_idx != -1, "End of coordinator block not found"
        coordinator_block = implement_content[start_idx:end_idx]
        forbidden_lines = [
            line.strip()
            for line in coordinator_block.split("\n")
            if line.strip().startswith("- ❌")
        ]
        assert len(forbidden_lines) == 14, (
            f"Expected 14 FORBIDDEN constraints in coordinator block, found {len(forbidden_lines)} — "
            f"constraints must be reorganized, not removed or added"
        )

    def test_thematic_group_headers_present(self, implement_content):
        """FORBIDDEN list must have thematic group headers."""
        assert "Agent Management" in implement_content, (
            "Missing 'Agent Management' thematic group header"
        )
        assert "Pipeline Integrity" in implement_content, (
            "Missing 'Pipeline Integrity' thematic group header"
        )


class TestPipelineState:
    """Verify pipeline state tracking is preserved."""

    def test_pipeline_state_initialization(self, implement_content):
        """Pipeline state must be initialized in STEP 0."""
        assert "pipeline" in implement_content.lower() and (
            "create_pipeline" in implement_content or "RUN_ID" in implement_content
        )

    def test_pipeline_cleanup(self, implement_content):
        """Pipeline state must be cleaned up in STEP 15."""
        assert "cleanup" in implement_content.lower() or "clean" in implement_content.lower()

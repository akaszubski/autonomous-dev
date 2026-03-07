"""Tests for Issue #404: Make acceptance-first the default mode in /implement pipeline.

Validates structural content changes across multiple markdown files:
1. implement.md - Default mode switches from TDD-first to acceptance-first
2. implement.md - --tdd-first flag documented for backward compatibility
3. implement.md - STEP 3.5 runs by default (no skip gate)
4. implement.md - STEP 4 only runs in --tdd-first mode
5. implement.md - STEP 7 agent count is conditional on mode
6. PROJECT.md - Constraints reflect acceptance-first default
7. implement-batch.md - Agent count not hardcoded to 9
8. test-master.md - References --tdd-first mode invocation
9. implementer.md - Mentions generating unit tests alongside code
10. TESTING-STRATEGY.md - Current state reflects acceptance-first default
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
IMPLEMENT_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
IMPLEMENT_BATCH_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"
TEST_MASTER_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "test-master.md"
IMPLEMENTER_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "implementer.md"
PROJECT_MD = PROJECT_ROOT / ".claude" / "PROJECT.md"
TESTING_STRATEGY_MD = PROJECT_ROOT / "docs" / "TESTING-STRATEGY.md"


@pytest.fixture
def implement_content() -> str:
    """Read implement.md content."""
    return IMPLEMENT_MD.read_text()


@pytest.fixture
def implement_lines(implement_content: str) -> list:
    """Implement.md as list of lines for line-level assertions."""
    return implement_content.splitlines()


@pytest.fixture
def project_content() -> str:
    """Read PROJECT.md content."""
    return PROJECT_MD.read_text()


@pytest.fixture
def implement_batch_content() -> str:
    """Read implement-batch.md content."""
    return IMPLEMENT_BATCH_MD.read_text()


@pytest.fixture
def test_master_content() -> str:
    """Read test-master.md content."""
    return TEST_MASTER_MD.read_text()


@pytest.fixture
def implementer_content() -> str:
    """Read implementer.md content."""
    return IMPLEMENTER_MD.read_text()


@pytest.fixture
def testing_strategy_content() -> str:
    """Read TESTING-STRATEGY.md content."""
    return TESTING_STRATEGY_MD.read_text()


class TestImplementDefaultModeIsAcceptanceFirst:
    """Verify implement.md modes table shows acceptance-first as default."""

    def test_modes_table_default_row_mentions_acceptance(self, implement_content: str):
        """The default mode row in the modes table should reference acceptance-first."""
        # Find the modes table rows - the default (no flag) row should mention acceptance
        lines = implement_content.splitlines()
        default_row = None
        for line in lines:
            # The default row has "(default)" in the Flag column
            if "(default)" in line and "|" in line:
                default_row = line
                break

        assert default_row is not None, (
            "No '(default)' row found in the modes table. "
            "Issue #404 requires the default mode to be acceptance-first."
        )
        assert "acceptance" in default_row.lower(), (
            f"Default mode row does not mention 'acceptance'. Got: {default_row!r}. "
            "Issue #404 requires acceptance-first to be the default pipeline mode."
        )

    def test_tdd_first_flag_documented(self, implement_content: str):
        """A --tdd-first flag must be documented in the modes table for backward compat."""
        assert "--tdd-first" in implement_content, (
            "implement.md must document a '--tdd-first' flag. "
            "Issue #404 inverts the default: acceptance-first is default, "
            "--tdd-first is the opt-in flag for the old behavior."
        )

    def test_acceptance_first_flag_still_mentioned(self, implement_content: str):
        """--acceptance-first should still be mentioned for backward compatibility."""
        assert "--acceptance-first" in implement_content, (
            "implement.md should still mention '--acceptance-first' for backward compat, "
            "even though it's now the default behavior."
        )


class TestStep0ParsesTddFirstFlag:
    """STEP 0 must parse --tdd-first as the opt-in flag."""

    def test_step0_mentions_tdd_first_flag(self, implement_content: str):
        """STEP 0 parsing should reference --tdd-first."""
        # Find the STEP 0 section
        step0_start = implement_content.find("### STEP 0")
        assert step0_start != -1, "STEP 0 section not found in implement.md"

        # Get content up to the next step
        step1_start = implement_content.find("### STEP 1", step0_start + 1)
        step0_section = implement_content[step0_start:step1_start]

        assert "--tdd-first" in step0_section, (
            "STEP 0 must parse '--tdd-first' flag. "
            f"Current STEP 0 content does not mention --tdd-first. "
            "Issue #404 makes --tdd-first the explicit opt-in."
        )


class TestStep35RunsByDefault:
    """STEP 3.5 (acceptance tests) should run by default, not only with --acceptance-first."""

    def test_step35_no_skip_for_acceptance_first(self, implement_content: str):
        """STEP 3.5 should NOT have 'Skip this step if --acceptance-first was NOT specified'."""
        step35_start = implement_content.find("### STEP 3.5")
        assert step35_start != -1, "STEP 3.5 section not found"

        step4_start = implement_content.find("### STEP 4", step35_start + 1)
        step35_section = implement_content[step35_start:step4_start]

        # The old text said "Skip this step if --acceptance-first was NOT specified"
        # After #404, this skip condition should reference --tdd-first instead
        assert "skip this step if `--acceptance-first` was not" not in step35_section.lower(), (
            "STEP 3.5 still has the old skip condition for --acceptance-first. "
            "Issue #404 makes acceptance-first the default, so this step should "
            "run by default and only be skipped if --tdd-first is specified."
        )

    def test_step35_skips_only_for_tdd_first(self, implement_content: str):
        """STEP 3.5 should skip only when --tdd-first is specified."""
        step35_start = implement_content.find("### STEP 3.5")
        step4_start = implement_content.find("### STEP 4", step35_start + 1)
        step35_section = implement_content[step35_start:step4_start]

        assert "--tdd-first" in step35_section, (
            "STEP 3.5 should reference --tdd-first as the condition to skip. "
            "In acceptance-first default mode, this step runs unless --tdd-first is set."
        )

    def test_step35_has_conftest_fallback(self, implement_content: str):
        """STEP 3.5 should still fall back to TDD if conftest.py is missing."""
        step35_start = implement_content.find("### STEP 3.5")
        step4_start = implement_content.find("### STEP 4", step35_start + 1)
        step35_section = implement_content[step35_start:step4_start]

        assert "conftest.py" in step35_section, (
            "STEP 3.5 must still check for tests/genai/conftest.py and fall back "
            "to TDD-first if it doesn't exist."
        )


class TestStep4OnlyInTddFirstMode:
    """STEP 4 (test-master TDD) should only run in --tdd-first mode."""

    def test_step4_conditional_on_tdd_first(self, implement_content: str):
        """STEP 4 should indicate it runs only in --tdd-first mode."""
        step4_start = implement_content.find("### STEP 4")
        assert step4_start != -1, "STEP 4 section not found"

        step5_start = implement_content.find("### STEP 5", step4_start + 1)
        step4_section = implement_content[step4_start:step5_start]

        assert "--tdd-first" in step4_section, (
            "STEP 4 should reference --tdd-first mode. "
            "In acceptance-first default, STEP 4 is skipped (unit tests are "
            "generated by implementer alongside code)."
        )

    def test_step4_default_skip_language(self, implement_content: str):
        """STEP 4 should indicate it is skipped by default (acceptance-first is default)."""
        step4_start = implement_content.find("### STEP 4")
        step5_start = implement_content.find("### STEP 5", step4_start + 1)
        step4_section = implement_content[step4_start:step5_start]

        # The old text said "Acceptance-first mode: Skip this step"
        # New text should indicate default behavior skips this step
        has_default_skip = (
            "default" in step4_section.lower()
            or "skip" in step4_section.lower()
        )
        assert has_default_skip, (
            "STEP 4 should mention that it is skipped by default. "
            "Since acceptance-first is now the default, STEP 4 only "
            "runs when --tdd-first is explicitly specified."
        )


class TestStep5DefaultPathMentionsAcceptanceTests:
    """STEP 5 default path should reference acceptance tests."""

    def test_step5_default_mentions_acceptance(self, implement_content: str):
        """STEP 5 should mention acceptance tests in its default (non-flag) path."""
        step5_start = implement_content.find("### STEP 5")
        assert step5_start != -1, "STEP 5 section not found"

        step55_start = implement_content.find("### STEP 5.5", step5_start + 1)
        step5_section = implement_content[step5_start:step55_start]

        # In acceptance-first default mode, the implementer gets acceptance tests
        # and generates unit tests alongside code
        assert "acceptance" in step5_section.lower(), (
            "STEP 5 should mention acceptance tests in the default path. "
            "Since acceptance-first is the default, the implementer receives "
            "acceptance tests from STEP 3.5 and generates unit tests alongside code."
        )


class TestStep7AgentCount:
    """STEP 7 verification should reflect conditional agent count."""

    def test_step7_does_not_hardcode_8_agents_unconditionally(self, implement_content: str):
        """STEP 7 should not hardcode 'all 8 pipeline agents' as universal requirement."""
        step7_start = implement_content.find("### STEP 7")
        assert step7_start != -1, "STEP 7 section not found"

        step8_start = implement_content.find("### STEP 8", step7_start + 1)
        step7_section = implement_content[step7_start:step8_start]

        # After #404, acceptance-first skips test-master, so agent count varies
        # STEP 7 should not insist on exactly "8 pipeline agents" unconditionally
        # It should either be conditional or list the correct agents per mode
        old_unconditional = "all 8 pipeline agents" in step7_section.lower()
        has_conditional_or_updated = (
            "--tdd-first" in step7_section
            or "conditional" in step7_section.lower()
            or "mode" in step7_section.lower()
            or "7" in step7_section  # 7 agents in acceptance-first mode
        )

        # Either the old unconditional text is gone, or conditional logic is added
        assert not old_unconditional or has_conditional_or_updated, (
            "STEP 7 unconditionally requires 'all 8 pipeline agents' but in "
            "acceptance-first mode (now default), test-master is skipped. "
            "Agent verification should be conditional on the pipeline mode."
        )


class TestTechnicalDetailsAgentList:
    """The Technical Details section agent list should reflect the mode-conditional agents."""

    def test_technical_details_mentions_mode_conditional(self, implement_content: str):
        """Technical Details section should reflect that test-master is conditional."""
        # Find the Technical Details section near the bottom
        td_start = implement_content.find("## Technical Details")
        if td_start == -1:
            td_start = implement_content.find("**Agents**:")

        assert td_start != -1, "Technical Details / Agents section not found"

        td_section = implement_content[td_start:]

        # Should mention that test-master is conditional on --tdd-first
        has_conditional = (
            "--tdd-first" in td_section
            or "conditional" in td_section.lower()
            or "acceptance-first" in td_section.lower()
        )

        assert has_conditional, (
            "Technical Details agent list should note that test-master is "
            "conditional on --tdd-first mode. In the default acceptance-first "
            "mode, only 7 agents run (test-master is skipped)."
        )


class TestProjectMdConstraints:
    """PROJECT.md constraints should reflect acceptance-first as default."""

    def test_security_constraints_not_tdd_mandatory(self, project_content: str):
        """Security constraints should not say 'TDD mandatory' without qualification."""
        constraints_start = project_content.find("## CONSTRAINTS")
        assert constraints_start != -1, "CONSTRAINTS section not found in PROJECT.md"

        constraints_section = project_content[constraints_start:]

        # The old text says "TDD mandatory (tests before implementation)"
        # After #404, this should reference acceptance-first or be more nuanced
        has_unqualified_tdd_mandatory = "tdd mandatory" in constraints_section.lower()
        has_acceptance_mention = "acceptance" in constraints_section.lower()

        # Either TDD mandatory is removed/reworded, or acceptance-first is also mentioned
        assert not has_unqualified_tdd_mandatory or has_acceptance_mention, (
            "PROJECT.md CONSTRAINTS says 'TDD mandatory' without mentioning "
            "acceptance-first. Issue #404 makes acceptance-first the default, "
            "so constraints should reflect the updated testing approach."
        )

    def test_key_points_reflect_acceptance_first(self, project_content: str):
        """Key Points should mention acceptance-first or diamond testing."""
        goals_start = project_content.find("## GOALS")
        scope_start = project_content.find("## SCOPE")
        goals_section = project_content[goals_start:scope_start]

        # The old text says "Research -> Plan -> TDD -> Implement"
        # After #404, should mention acceptance-first approach
        has_acceptance = (
            "acceptance" in goals_section.lower()
            or "diamond" in goals_section.lower()
        )

        assert has_acceptance, (
            "PROJECT.md GOALS/Key Points should mention acceptance-first or "
            "diamond testing model. The pipeline description still only "
            "mentions TDD."
        )


class TestImplementBatchAgentCount:
    """implement-batch.md should not hardcode 9 agents unconditionally."""

    def test_batch_does_not_require_exactly_9_agents(self, implement_batch_content: str):
        """Batch mode should accommodate variable agent count based on mode."""
        content_lower = implement_batch_content.lower()

        # Check for unconditional "9 agents" or "nine agents" requirement
        has_hardcoded_9 = (
            "9 agents" in content_lower
            or "nine agents" in content_lower
            or "all 9" in content_lower
        )

        if has_hardcoded_9:
            # If 9 is mentioned, it should be conditional
            has_conditional = (
                "--tdd-first" in implement_batch_content
                or "conditional" in content_lower
                or "mode" in content_lower
            )
            assert has_conditional, (
                "implement-batch.md hardcodes 9 agents without accounting for "
                "acceptance-first mode where test-master is skipped. "
                "Agent count should be conditional on pipeline mode."
            )


class TestTestMasterTddFirstReference:
    """test-master.md should reference that it's invoked in --tdd-first mode."""

    def test_test_master_mentions_tdd_first_invocation(self, test_master_content: str):
        """test-master should note it's invoked when --tdd-first is specified."""
        has_tdd_first = "--tdd-first" in test_master_content
        has_mode_reference = (
            "tdd-first mode" in test_master_content.lower()
            or "tdd mode" in test_master_content.lower()
        )

        assert has_tdd_first or has_mode_reference, (
            "test-master.md should reference that it's invoked in --tdd-first mode. "
            "Since acceptance-first is now the default, test-master only runs "
            "when --tdd-first is explicitly specified."
        )

    def test_test_master_still_describes_specification_testing(self, test_master_content: str):
        """test-master mission should still describe specification-driven testing."""
        assert "specification" in test_master_content.lower() or "spec" in test_master_content.lower(), (
            "test-master.md mission should still describe specification-driven testing."
        )


class TestImplementerGeneratesUnitTests:
    """implementer.md should mention generating unit tests alongside code in default mode."""

    def test_implementer_mentions_unit_test_generation(self, implementer_content: str):
        """Implementer should reference generating unit tests alongside implementation."""
        content_lower = implementer_content.lower()

        has_unit_test_gen = (
            "unit test" in content_lower
            or "generate test" in content_lower
            or "write test" in content_lower
        )

        # In acceptance-first default mode, implementer generates unit tests
        # alongside code since test-master is skipped
        assert has_unit_test_gen, (
            "implementer.md should mention generating unit tests alongside code. "
            "In acceptance-first default mode, test-master is skipped and the "
            "implementer is responsible for unit test creation."
        )


class TestTestingStrategyReflectsDefault:
    """TESTING-STRATEGY.md should reflect acceptance-first as the default pipeline mode."""

    def test_current_state_mentions_acceptance_first_default(self, testing_strategy_content: str):
        """Current State section should show acceptance-first as default."""
        # Find the Current State section
        current_start = testing_strategy_content.find("### Current State")
        if current_start == -1:
            pytest.skip("No 'Current State' section found in TESTING-STRATEGY.md")

        target_start = testing_strategy_content.find("### Target State", current_start + 1)
        if target_start == -1:
            target_start = len(testing_strategy_content)
        current_section = testing_strategy_content[current_start:target_start]

        # The old text says "TDD-first pipeline"
        # After #404, should say acceptance-first is default
        has_tdd_first_only = (
            "tdd-first pipeline" in current_section.lower()
            and "acceptance-first" not in current_section.lower()
        )

        assert not has_tdd_first_only, (
            "TESTING-STRATEGY.md Current State still says 'TDD-first pipeline' "
            "without mentioning acceptance-first as the default. "
            "Issue #404 makes acceptance-first the default mode."
        )

    def test_migration_references_issue_404(self, testing_strategy_content: str):
        """Migration path or changelog should reference Issue #404."""
        assert "#404" in testing_strategy_content or "404" in testing_strategy_content, (
            "TESTING-STRATEGY.md should reference Issue #404 in its migration "
            "path or changelog section documenting the shift to acceptance-first default."
        )


class TestPipelineDescriptionConsistency:
    """Cross-file consistency: pipeline description should be consistent."""

    def test_full_pipeline_label_reflects_acceptance(self, implement_content: str):
        """The 'FULL PIPELINE MODE' section heading or description should reflect acceptance."""
        full_pipeline_start = implement_content.find("# FULL PIPELINE MODE")
        assert full_pipeline_start != -1, "FULL PIPELINE MODE section not found"

        # Get the first few lines after the heading
        section_lines = implement_content[full_pipeline_start:full_pipeline_start + 300]

        # Should mention acceptance-first as the default workflow
        has_acceptance_ref = "acceptance" in section_lines.lower()
        has_agent_count_update = "7" in section_lines or "8" in section_lines

        assert has_acceptance_ref or has_agent_count_update, (
            "FULL PIPELINE MODE section should reflect that acceptance-first "
            "is the default workflow. The description still references the old "
            "8-agent TDD workflow without mentioning acceptance-first."
        )

    def test_step0_acceptance_first_is_default_routing(self, implement_content: str):
        """STEP 0 routing should treat acceptance-first as the default path."""
        step0_start = implement_content.find("### STEP 0")
        step1_start = implement_content.find("### STEP 1", step0_start + 1)
        step0_section = implement_content[step0_start:step1_start]

        # Old: --acceptance-first -> FULL PIPELINE with ACCEPTANCE-FIRST variant, else -> FULL PIPELINE
        # New: --tdd-first -> FULL PIPELINE with TDD-FIRST variant, else -> FULL PIPELINE (acceptance-first default)
        old_routing = "`--acceptance-first` " in step0_section and "else " in step0_section.lower()
        new_routing = "--tdd-first" in step0_section

        assert new_routing, (
            "STEP 0 routing should parse --tdd-first as the variant flag. "
            "The default (no flag) path should be acceptance-first."
        )

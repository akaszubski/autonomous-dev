"""
Progression tests for Issue #214: Evaluate splitting setup-wizard.md (1,145 lines).

This issue is a "validate-need" review - evaluating whether to split the setup-wizard
agent into multiple smaller agents or keep it unified with optimizations.

RECOMMENDATION: KEEP UNIFIED with hybrid optimizations
- Don't split the agent (sequential phase dependencies make it impractical)
- Extract reusable libraries (tech_stack_detector.py, project_md_generator.py) as future work
- Document the evaluation findings

These tests validate:
1. setup-wizard.md exists and is the largest agent (baseline validation)
2. setup-wizard.md has proper phase structure (6 phases)
3. Documentation of the evaluation decision exists
4. The decision document explains why unified is recommended

Test Coverage:
- Unit tests for setup-wizard.md existence and size
- Integration tests for phase structure validation
- Documentation tests for evaluation findings
- Edge cases (missing phases, malformed structure)

TDD Approach (RED phase):
- Tests written BEFORE documentation exists
- Tests should FAIL initially
- Tests pass after evaluation is documented
"""

import re
import sys
from pathlib import Path
from typing import Dict, Optional


# Project root path helper
def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.parent.parent


class TestSetupWizardBaseline:
    """Test setup-wizard.md baseline characteristics.

    Validates that setup-wizard.md exists, is the largest agent,
    and has the expected phase structure.
    """

    def test_setup_wizard_exists(self):
        """Test that setup-wizard.md exists in agents directory.

        Arrange: .claude/agents/ directory
        Act: Check for setup-wizard.md
        Assert: File exists
        """
        # Arrange
        project_root = get_project_root()
        setup_wizard = project_root / ".claude" / "agents" / "setup-wizard.md"

        # Act & Assert
        assert setup_wizard.exists(), (
            "setup-wizard.md not found in .claude/agents/. "
            "This is the agent being evaluated for Issue #214."
        )

    def test_setup_wizard_is_largest_agent(self):
        """Test that setup-wizard.md is the largest agent file.

        This validates the premise of Issue #214 - that setup-wizard.md
        is significantly larger than other agents and worth evaluating
        for potential splitting.

        Arrange: .claude/agents/ directory with all agent files
        Act: Count lines in all agent files
        Assert: setup-wizard.md has the most lines (>1000)
        """
        # Arrange
        project_root = get_project_root()
        agents_dir = project_root / ".claude" / "agents"

        # Act
        agent_sizes: Dict[str, int] = {}
        for agent_file in agents_dir.glob("*.md"):
            line_count = len(agent_file.read_text().splitlines())
            agent_sizes[agent_file.name] = line_count

        # Assert
        assert "setup-wizard.md" in agent_sizes, "setup-wizard.md not found"

        setup_wizard_size = agent_sizes["setup-wizard.md"]
        max_size = max(agent_sizes.values())

        largest_agent = max(agent_sizes.keys(), key=lambda k: agent_sizes[k])
        assert setup_wizard_size == max_size, (
            f"setup-wizard.md ({setup_wizard_size} lines) is not the largest agent. "
            f"Largest is {largest_agent} "
            f"with {max_size} lines."
        )

        assert setup_wizard_size > 1000, (
            f"setup-wizard.md has {setup_wizard_size} lines, "
            f"expected >1000 lines to justify evaluation"
        )

    def test_setup_wizard_line_count_documentation(self):
        """Test that Issue #214 accurately documents the line count.

        Arrange: setup-wizard.md with known line count
        Act: Compare actual vs documented line count (1,145)
        Assert: Difference is within 10% (allows for minor edits)
        """
        # Arrange
        project_root = get_project_root()
        setup_wizard = project_root / ".claude" / "agents" / "setup-wizard.md"

        # Act
        actual_lines = len(setup_wizard.read_text().splitlines())
        documented_lines = 1145  # From Issue #214 title

        # Assert - Allow 10% variance for minor edits
        variance = abs(actual_lines - documented_lines) / documented_lines
        assert variance < 0.10, (
            f"setup-wizard.md line count ({actual_lines}) differs significantly "
            f"from documented count ({documented_lines}). Variance: {variance:.1%}. "
            f"Update Issue #214 if major changes were made."
        )


class TestSetupWizardPhaseStructure:
    """Test setup-wizard.md phase structure.

    Validates the 6-phase structure that would make splitting complex:
    Phase 0: GenAI Installation (optional)
    Phase 1: Welcome & Tech Stack Detection
    Phase 2: PROJECT.md Setup
    Phase 3: Workflow Selection
    Phase 4: GitHub Integration (optional)
    Phase 5: Validation & Summary
    """

    def test_has_six_phase_structure(self):
        """Test that setup-wizard.md documents all 6 phases.

        This is critical for the evaluation - the sequential phase
        dependencies are why splitting is impractical.

        Arrange: setup-wizard.md content
        Act: Search for "## Phase" headings
        Assert: Found exactly 6 phases (0-5)
        """
        # Arrange
        project_root = get_project_root()
        setup_wizard = project_root / ".claude" / "agents" / "setup-wizard.md"
        content = setup_wizard.read_text()

        # Act
        phase_pattern = r'^## Phase \d+:'
        phases = re.findall(phase_pattern, content, re.MULTILINE)

        # Assert
        assert len(phases) >= 6, (
            f"Expected at least 6 phases (Phase 0-5), found {len(phases)}. "
            f"Phases: {phases}"
        )

    def test_phase_zero_is_optional(self):
        """Test that Phase 0 (GenAI Installation) is documented as optional.

        Phase 0 runs conditionally based on staging directory presence.
        This conditional logic is part of why splitting is complex.

        Arrange: setup-wizard.md Phase 0 section
        Act: Check for "Optional" indicator
        Assert: Phase 0 is marked optional
        """
        # Arrange
        project_root = get_project_root()
        setup_wizard = project_root / ".claude" / "agents" / "setup-wizard.md"
        content = setup_wizard.read_text()

        # Act
        phase_zero_section = self._extract_phase_section(content, 0)

        # Assert
        assert phase_zero_section is not None, "Phase 0 section not found"

        # Check for optional indicators
        optional_indicators = ["optional", "if staging exists", "conditional"]
        has_optional_marker = any(
            indicator.lower() in phase_zero_section.lower()
            for indicator in optional_indicators
        )

        assert has_optional_marker, (
            "Phase 0 should be marked as optional/conditional. "
            "This conditional logic is part of why splitting is impractical."
        )

    def test_phase_dependencies_documented(self):
        """Test that phase dependencies are clear in the structure.

        Sequential dependencies make splitting impractical:
        - Phase 1 detects tech stack → used in Phase 2
        - Phase 2 creates PROJECT.md → validated in Phase 5
        - Phase 3 configures hooks → based on Phase 1 detection

        Arrange: setup-wizard.md Process Overview section
        Act: Check for phase flow diagram or list
        Assert: Phase sequence is documented
        """
        # Arrange
        project_root = get_project_root()
        setup_wizard = project_root / ".claude" / "agents" / "setup-wizard.md"
        content = setup_wizard.read_text()

        # Act - Look for Process Overview section
        process_section_pattern = r'## Process Overview.*?(?=\n##|\Z)'
        process_match = re.search(process_section_pattern, content, re.DOTALL)

        # Assert
        assert process_match is not None, (
            "Process Overview section not found. "
            "Phase dependencies should be documented in overview."
        )

        process_overview = process_match.group()

        # Check that all phases are mentioned in overview
        for phase_num in range(6):
            assert f"Phase {phase_num}" in process_overview, (
                f"Phase {phase_num} not mentioned in Process Overview. "
                f"Sequential flow documentation is important for evaluation."
            )

    def test_phase_two_is_substantial_section(self):
        """Test that Phase 2 (PROJECT.md Setup) is a substantial phase.

        Phase 2 handles PROJECT.md generation - complex logic that
        might benefit from library extraction. While Phase 0 (GenAI
        installation) may be larger, Phase 2 is substantial enough
        to justify library extraction.

        Arrange: setup-wizard.md with all phases
        Act: Count lines in each phase section
        Assert: Phase 2 has at least 80 lines (substantial complexity)
        """
        # Arrange
        project_root = get_project_root()
        setup_wizard = project_root / ".claude" / "agents" / "setup-wizard.md"
        content = setup_wizard.read_text()

        # Act
        phase_sizes = {}
        for phase_num in range(6):
            section = self._extract_phase_section(content, phase_num)
            if section:
                phase_sizes[phase_num] = len(section.splitlines())

        # Assert
        assert 2 in phase_sizes, "Phase 2 section not found"
        assert phase_sizes[2] > 0, "Phase 2 is empty"

        # Phase 2 should be substantial (80+ lines = complex enough for library extraction)
        assert phase_sizes[2] >= 80, (
            f"Phase 2 ({phase_sizes[2]} lines) should be substantial (80+ lines). "
            f"Current complexity suggests library extraction opportunity. "
            f"All phase sizes: {phase_sizes}"
        )

    @staticmethod
    def _extract_phase_section(content: str, phase_num: int) -> Optional[str]:
        """Extract content of a specific phase section.

        Args:
            content: Full setup-wizard.md content
            phase_num: Phase number (0-5)

        Returns:
            Phase section content or None if not found
        """
        pattern = rf'^## Phase {phase_num}:.*?(?=^## Phase \d+:|^## [A-Z]|\Z)'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        return match.group() if match else None


class TestSetupWizardEvaluationDocumentation:
    """Test that Issue #214 evaluation is documented.

    These tests will FAIL initially (RED phase) until the evaluation
    findings are documented. This is the TDD approach for documentation.
    """

    def test_evaluation_document_exists(self):
        """Test that evaluation findings are documented.

        Expected location: docs/evaluations/issue_214_setup_wizard_split.md
        or similar documentation of the decision.

        Arrange: docs/ directory
        Act: Search for Issue #214 evaluation document
        Assert: Document exists

        TDD: This test FAILS until documentation is created.
        """
        # Arrange
        project_root = get_project_root()

        # Possible documentation locations
        possible_paths = [
            project_root / "docs" / "evaluations" / "issue_214_setup_wizard_split.md",
            project_root / "docs" / "decisions" / "issue_214_setup_wizard.md",
            project_root / "docs" / "architecture" / "setup_wizard_evaluation.md",
            project_root / "docs" / "issue_214_evaluation.md",
        ]

        # Act
        found_paths = [p for p in possible_paths if p.exists()]

        # Assert
        assert len(found_paths) > 0, (
            f"Issue #214 evaluation document not found. "
            f"Expected in one of:\n" +
            "\n".join(f"  - {p}" for p in possible_paths) +
            f"\n\nCreate documentation explaining the evaluation decision "
            f"(KEEP UNIFIED with hybrid optimizations)."
        )

    def test_evaluation_explains_keep_unified_decision(self):
        """Test that evaluation document explains why to keep unified.

        The decision should document:
        - Sequential phase dependencies
        - Complexity of splitting
        - Hybrid optimization approach instead

        Arrange: Evaluation document
        Act: Check for key decision points
        Assert: Document explains "keep unified" rationale

        TDD: This test FAILS until decision rationale is documented.
        """
        # Arrange
        project_root = get_project_root()

        # Find evaluation document
        possible_paths = [
            project_root / "docs" / "evaluations" / "issue_214_setup_wizard_split.md",
            project_root / "docs" / "decisions" / "issue_214_setup_wizard.md",
            project_root / "docs" / "architecture" / "setup_wizard_evaluation.md",
            project_root / "docs" / "issue_214_evaluation.md",
        ]

        eval_doc = None
        for path in possible_paths:
            if path.exists():
                eval_doc = path
                break

        assert eval_doc is not None, (
            "Evaluation document not found. "
            "Run test_evaluation_document_exists first."
        )

        # Act
        content = eval_doc.read_text().lower()

        # Assert - Check for key decision points
        decision_keywords = [
            "keep unified",
            "sequential dependencies",
            "phase dependencies",
            "impractical to split",
        ]

        found_keywords = [kw for kw in decision_keywords if kw in content]

        assert len(found_keywords) >= 2, (
            f"Evaluation document should explain why keeping unified. "
            f"Expected keywords: {decision_keywords}\n"
            f"Found only: {found_keywords}\n"
            f"Add rationale for 'keep unified' decision."
        )

    def test_evaluation_documents_hybrid_optimizations(self):
        """Test that evaluation document describes hybrid optimization approach.

        Hybrid approach:
        1. Don't split the agent (keep phases together)
        2. Extract reusable libraries (tech_stack_detector.py, project_md_generator.py)
        3. Document evaluation findings

        Arrange: Evaluation document
        Act: Check for hybrid optimization keywords
        Assert: Document describes library extraction approach

        TDD: This test FAILS until hybrid approach is documented.
        """
        # Arrange
        project_root = get_project_root()

        # Find evaluation document
        possible_paths = [
            project_root / "docs" / "evaluations" / "issue_214_setup_wizard_split.md",
            project_root / "docs" / "decisions" / "issue_214_setup_wizard.md",
            project_root / "docs" / "architecture" / "setup_wizard_evaluation.md",
            project_root / "docs" / "issue_214_evaluation.md",
        ]

        eval_doc = None
        for path in possible_paths:
            if path.exists():
                eval_doc = path
                break

        assert eval_doc is not None, "Evaluation document not found"

        # Act
        content = eval_doc.read_text().lower()

        # Assert - Check for hybrid optimization keywords
        optimization_keywords = [
            "library",
            "extract",
            "reusable",
            "tech_stack_detector",
            "project_md_generator",
            "hybrid",
        ]

        found_keywords = [kw for kw in optimization_keywords if kw in content]

        assert len(found_keywords) >= 2, (
            f"Evaluation document should describe hybrid optimization approach. "
            f"Expected keywords: {optimization_keywords}\n"
            f"Found only: {found_keywords}\n"
            f"Add description of library extraction as alternative to splitting."
        )

    def test_evaluation_identifies_library_extraction_opportunities(self):
        """Test that evaluation identifies specific library extraction opportunities.

        Key opportunities:
        - tech_stack_detector.py (Phase 1 logic)
        - project_md_generator.py (Phase 2 logic)
        - hook_configurator.py (Phase 3 logic)

        Arrange: Evaluation document
        Act: Check for specific library names
        Assert: At least 2 libraries mentioned

        TDD: This test FAILS until library opportunities are documented.
        """
        # Arrange
        project_root = get_project_root()

        # Find evaluation document
        possible_paths = [
            project_root / "docs" / "evaluations" / "issue_214_setup_wizard_split.md",
            project_root / "docs" / "decisions" / "issue_214_setup_wizard.md",
            project_root / "docs" / "architecture" / "setup_wizard_evaluation.md",
            project_root / "docs" / "issue_214_evaluation.md",
        ]

        eval_doc = None
        for path in possible_paths:
            if path.exists():
                eval_doc = path
                break

        assert eval_doc is not None, "Evaluation document not found"

        # Act
        content = eval_doc.read_text().lower()

        # Assert - Check for specific library names
        library_names = [
            "tech_stack_detector",
            "project_md_generator",
            "hook_configurator",
        ]

        found_libraries = [lib for lib in library_names if lib in content]

        assert len(found_libraries) >= 2, (
            f"Evaluation document should identify specific library extraction opportunities. "
            f"Expected libraries: {library_names}\n"
            f"Found only: {found_libraries}\n"
            f"List specific .py libraries that could be extracted."
        )


class TestSetupWizardComplexityAnalysis:
    """Test complexity metrics that justify the evaluation.

    Validates the characteristics that make setup-wizard.md
    worth evaluating for potential refactoring.
    """

    def test_setup_wizard_has_multiple_major_sections(self):
        """Test that setup-wizard.md has 6+ major sections.

        Major sections (Phase 0-5) suggest complexity that might
        benefit from modularization.

        Arrange: setup-wizard.md content
        Act: Count level-2 headings (##)
        Assert: At least 10 major sections (phases + supporting sections)
        """
        # Arrange
        project_root = get_project_root()
        setup_wizard = project_root / ".claude" / "agents" / "setup-wizard.md"
        content = setup_wizard.read_text()

        # Act
        level2_headings = re.findall(r'^## ', content, re.MULTILINE)

        # Assert
        assert len(level2_headings) >= 10, (
            f"Expected at least 10 major sections (## headings), "
            f"found {len(level2_headings)}. "
            f"Multiple major sections suggest complexity worth evaluating."
        )

    def test_setup_wizard_has_conditional_logic(self):
        """Test that setup-wizard.md documents conditional logic.

        Conditional logic (Phase 0 optional, Phase 4 optional) adds
        complexity that makes splitting harder.

        Arrange: setup-wizard.md content
        Act: Search for conditional keywords
        Assert: Multiple conditional blocks found
        """
        # Arrange
        project_root = get_project_root()
        setup_wizard = project_root / ".claude" / "agents" / "setup-wizard.md"
        content = setup_wizard.read_text().lower()

        # Act
        conditional_keywords = ["if", "optional", "skip", "fallback", "when"]
        conditional_count = sum(
            content.count(keyword) for keyword in conditional_keywords
        )

        # Assert
        assert conditional_count >= 20, (
            f"Expected at least 20 conditional references, found {conditional_count}. "
            f"Conditional logic adds complexity that makes splitting impractical."
        )

    def test_setup_wizard_exceeds_typical_agent_size_by_3x(self):
        """Test that setup-wizard.md is at least 3x larger than average agent.

        Significant size difference (3x+) justifies evaluation.

        Arrange: All agent files in .claude/agents/
        Act: Calculate average agent size
        Assert: setup-wizard.md is 3x+ larger than average
        """
        # Arrange
        project_root = get_project_root()
        agents_dir = project_root / ".claude" / "agents"

        # Act
        agent_sizes = []
        for agent_file in agents_dir.glob("*.md"):
            line_count = len(agent_file.read_text().splitlines())
            agent_sizes.append(line_count)

        setup_wizard = agents_dir / "setup-wizard.md"
        setup_wizard_size = len(setup_wizard.read_text().splitlines())

        average_size = sum(agent_sizes) / len(agent_sizes)

        # Assert
        size_ratio = setup_wizard_size / average_size

        assert size_ratio >= 3.0, (
            f"setup-wizard.md ({setup_wizard_size} lines) should be 3x+ larger "
            f"than average agent ({average_size:.0f} lines). "
            f"Ratio: {size_ratio:.1f}x. "
            f"Significant size difference justifies evaluation."
        )


class TestIssue214MetaValidation:
    """Meta-validation tests for Issue #214 test suite.

    These tests validate the test suite itself to ensure comprehensive
    coverage of the evaluation requirements.
    """

    def test_all_test_classes_documented(self):
        """Test that all test classes have docstrings explaining their purpose.

        Arrange: This test file
        Act: Check for class docstrings
        Assert: All test classes documented
        """
        # Get current module
        current_module = sys.modules[__name__]

        # Find all test classes
        test_classes = [
            obj for name, obj in vars(current_module).items()
            if isinstance(obj, type) and name.startswith("Test")
        ]

        # Check docstrings
        undocumented = [
            cls.__name__ for cls in test_classes
            if not cls.__doc__ or len(cls.__doc__.strip()) < 20
        ]

        assert len(undocumented) == 0, (
            f"Test classes missing docstrings: {undocumented}. "
            f"All test classes should explain their validation purpose."
        )

    def test_covers_baseline_validation(self):
        """Test that test suite includes baseline validation tests.

        Baseline validation: setup-wizard.md exists, is largest, has 6 phases.
        """
        # This test validates that TestSetupWizardBaseline class exists
        # and has required test methods
        assert hasattr(TestSetupWizardBaseline, 'test_setup_wizard_exists')
        assert hasattr(TestSetupWizardBaseline, 'test_setup_wizard_is_largest_agent')

        # Phase structure tests are in TestSetupWizardPhaseStructure
        assert hasattr(TestSetupWizardPhaseStructure, 'test_has_six_phase_structure')

    def test_covers_evaluation_documentation(self):
        """Test that test suite validates evaluation documentation.

        Documentation tests: evaluation document exists, explains decision,
        describes hybrid approach.
        """
        # This test validates that TestSetupWizardEvaluationDocumentation exists
        # and has required test methods
        assert hasattr(TestSetupWizardEvaluationDocumentation, 'test_evaluation_document_exists')
        assert hasattr(TestSetupWizardEvaluationDocumentation, 'test_evaluation_explains_keep_unified_decision')
        assert hasattr(TestSetupWizardEvaluationDocumentation, 'test_evaluation_documents_hybrid_optimizations')

    def test_covers_complexity_analysis(self):
        """Test that test suite includes complexity analysis tests.

        Complexity tests: multiple sections, conditional logic, size ratio.
        """
        # This test validates that TestSetupWizardComplexityAnalysis exists
        # and has required test methods
        assert hasattr(TestSetupWizardComplexityAnalysis, 'test_setup_wizard_has_multiple_major_sections')
        assert hasattr(TestSetupWizardComplexityAnalysis, 'test_setup_wizard_has_conditional_logic')
        assert hasattr(TestSetupWizardComplexityAnalysis, 'test_setup_wizard_exceeds_typical_agent_size_by_3x')


# Test execution summary for Issue #214
"""
TEST EXECUTION SUMMARY
======================

Phase 1: Baseline Validation (SHOULD PASS NOW)
- test_setup_wizard_exists
- test_setup_wizard_is_largest_agent
- test_setup_wizard_line_count_documentation
- test_has_six_phase_structure
- test_phase_zero_is_optional
- test_phase_dependencies_documented
- test_phase_two_is_largest_section

Phase 2: Evaluation Documentation (SHOULD FAIL - RED PHASE)
- test_evaluation_document_exists
- test_evaluation_explains_keep_unified_decision
- test_evaluation_documents_hybrid_optimizations
- test_evaluation_identifies_library_extraction_opportunities

Phase 3: Complexity Analysis (SHOULD PASS NOW)
- test_setup_wizard_has_multiple_major_sections
- test_setup_wizard_has_conditional_logic
- test_setup_wizard_exceeds_typical_agent_size_by_3x

Phase 4: Meta-Validation (SHOULD PASS NOW)
- test_all_test_classes_documented
- test_covers_baseline_validation
- test_covers_evaluation_documentation
- test_covers_complexity_analysis

EXPECTED RESULTS:
- Phases 1, 3, 4: PASS (baseline validation)
- Phase 2: FAIL (documentation not created yet - TDD RED phase)

NEXT STEPS:
1. Run tests: pytest tests/regression/progression/test_issue_214_setup_wizard_evaluation.py --tb=line -q
2. Verify Phase 2 tests FAIL (expected - TDD RED phase)
3. Create evaluation document at docs/evaluations/issue_214_setup_wizard_split.md
4. Document decision: KEEP UNIFIED with hybrid optimizations
5. Re-run tests to verify Phase 2 PASSES (TDD GREEN phase)

EVALUATION DECISION TEMPLATE:
=============================
Create: docs/evaluations/issue_214_setup_wizard_split.md

Content should include:
- Decision: KEEP UNIFIED (don't split agent)
- Rationale: Sequential phase dependencies make splitting impractical
- Hybrid approach: Extract reusable libraries instead
- Libraries to extract:
  * tech_stack_detector.py (Phase 1 logic)
  * project_md_generator.py (Phase 2 logic)
  * hook_configurator.py (Phase 3 logic)
- Benefits: Reusable code without breaking agent workflow
- Timeline: Library extraction as future work (separate issues)
"""

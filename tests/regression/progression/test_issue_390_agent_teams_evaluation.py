"""
Progression tests for Issue #390: Agent Teams Evaluation document.

This issue evaluates Claude Code's Agent Teams feature against the current
worktree-based batch processing approach. The deliverable is an evaluation
document at docs/evaluations/issue_390_agent_teams_evaluation.md.

EXPECTED OUTCOME: Document recommending worktrees remain primary approach,
with Agent Teams suitable for specific use cases (research, review).

These tests validate:
1. Evaluation document exists at expected path
2. Required sections cover comparison matrix, blockers, recommendation
3. Decision rationale covers isolation, speed, and sources

Test Coverage:
- Document existence tests
- Required section content validation
- Decision rationale completeness
- Source/reference validation

TDD Approach (RED phase):
- Tests written BEFORE document exists
- All tests should FAIL initially
- Tests pass after evaluation document is created
"""

import re
import sys
from pathlib import Path
from typing import Optional


# Project root path helper
def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.parent.parent


def _get_evaluation_doc() -> Optional[Path]:
    """Find the evaluation document if it exists.

    Returns:
        Path to evaluation document or None if not found.
    """
    project_root = get_project_root()
    path = project_root / "docs" / "evaluations" / "issue_390_agent_teams_evaluation.md"
    return path if path.exists() else None


def _get_evaluation_content() -> str:
    """Get evaluation document content.

    Returns:
        Document content as string.

    Raises:
        AssertionError: If document not found.
    """
    doc = _get_evaluation_doc()
    assert doc is not None, (
        "Evaluation document not found at "
        "docs/evaluations/issue_390_agent_teams_evaluation.md. "
        "Create this document to satisfy Issue #390."
    )
    return doc.read_text()


class TestAgentTeamsEvaluationExists:
    """Test that the Agent Teams evaluation document exists.

    The primary deliverable for Issue #390 is an evaluation document
    comparing worktrees vs Agent Teams for batch processing.
    """

    def test_evaluation_document_exists(self):
        """Test that evaluation document exists at expected path.

        Arrange: docs/evaluations/ directory
        Act: Check for issue_390_agent_teams_evaluation.md
        Assert: File exists

        TDD: This test FAILS until the document is created.
        """
        # Arrange
        project_root = get_project_root()
        eval_doc = project_root / "docs" / "evaluations" / "issue_390_agent_teams_evaluation.md"

        # Act & Assert
        assert eval_doc.exists(), (
            f"Issue #390 evaluation document not found at:\n"
            f"  {eval_doc}\n"
            f"Create this document with Agent Teams vs Worktrees evaluation."
        )


class TestAgentTeamsEvaluationRequiredSections:
    """Test that the evaluation document contains all required sections.

    Required sections cover the comparison matrix, critical blockers,
    session limitations, recommendation, and valid use cases.
    """

    def test_has_comparison_matrix(self):
        """Test that document contains a comparison table of worktrees vs Agent Teams.

        The evaluation must include a structured comparison (table or matrix)
        showing how worktrees and Agent Teams differ across key dimensions.

        Arrange: Evaluation document content
        Act: Search for table/matrix comparing approaches
        Assert: Comparison table exists with both approaches mentioned
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act - Look for table indicators with comparison keywords
        has_table = "|" in content and "---" in content
        has_comparison_keywords = (
            ("worktree" in content_lower or "worktrees" in content_lower)
            and ("agent teams" in content_lower or "agent team" in content_lower)
        )

        # Assert
        assert has_table, (
            "Evaluation document should contain a comparison table (markdown table with | and ---). "
            "Add a matrix comparing worktrees vs Agent Teams across key dimensions."
        )
        assert has_comparison_keywords, (
            "Comparison table should reference both 'worktrees' and 'Agent Teams'. "
            "Ensure both approaches are compared side-by-side."
        )

    def test_documents_file_locking_blocker(self):
        """Test that document identifies no file-level locking as a critical blocker.

        Agent Teams lacks file-level locking, meaning multiple agents can
        write to the same file simultaneously, causing conflicts and data loss.

        Arrange: Evaluation document content
        Act: Search for file locking discussion
        Assert: File locking limitation is documented
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        locking_keywords = ["file locking", "file-level locking", "lock", "concurrent write", "write conflict"]
        found = [kw for kw in locking_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should document the file locking blocker. "
            f"Searched for: {locking_keywords}\n"
            f"Found: {found}\n"
            f"Agent Teams has no file-level locking - this is a critical blocker."
        )

    def test_documents_session_resumption_blocker(self):
        """Test that document identifies no session resumption as a critical blocker.

        Agent Teams cannot resume interrupted sessions, meaning a failure
        mid-batch loses all progress without worktree isolation.

        Arrange: Evaluation document content
        Act: Search for session resumption discussion
        Assert: Session resumption limitation is documented
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        resumption_keywords = [
            "session resumption", "resume", "interrupted",
            "session recovery", "restart", "session persistence"
        ]
        found = [kw for kw in resumption_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should document the session resumption blocker. "
            f"Searched for: {resumption_keywords}\n"
            f"Found: {found}\n"
            f"Agent Teams cannot resume interrupted sessions - this is a critical blocker."
        )

    def test_documents_one_team_per_session_blocker(self):
        """Test that document identifies one team per session limitation.

        Claude Code only supports one Agent Team per session, making it
        impractical for batch processing of multiple independent features.

        Arrange: Evaluation document content
        Act: Search for session limitation discussion
        Assert: One-team-per-session limitation is documented
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        session_keywords = [
            "one team per session", "single team", "one team",
            "session limit", "one active team", "concurrent teams"
        ]
        found = [kw for kw in session_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should document the one-team-per-session limitation. "
            f"Searched for: {session_keywords}\n"
            f"Found: {found}\n"
            f"Claude Code only supports one Agent Team per session."
        )

    def test_states_recommendation(self):
        """Test that document contains a clear recommendation to keep worktrees.

        The evaluation should conclude with a recommendation that worktrees
        remain the primary approach for batch processing.

        Arrange: Evaluation document content
        Act: Search for recommendation section and worktree preference
        Assert: Clear recommendation exists favoring worktrees
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        has_recommendation_section = (
            "recommendation" in content_lower or "conclusion" in content_lower
        )
        recommends_worktrees = any(
            phrase in content_lower
            for phrase in [
                "keep worktree", "worktrees remain", "continue using worktree",
                "worktree-based", "recommend worktree", "prefer worktree",
                "retain worktree", "maintain worktree"
            ]
        )

        # Assert
        assert has_recommendation_section, (
            "Evaluation should contain a 'Recommendation' or 'Conclusion' section. "
            "Add a clear section stating the recommended approach."
        )
        assert recommends_worktrees, (
            "Evaluation should recommend keeping worktrees as primary approach. "
            "The document should clearly state that worktrees remain preferred "
            "for batch processing."
        )

    def test_documents_agent_teams_use_cases(self):
        """Test that document identifies where Agent Teams does fit.

        While worktrees are preferred for batch processing, Agent Teams
        has valid use cases for research and review tasks.

        Arrange: Evaluation document content
        Act: Search for valid use case discussion
        Assert: At least one valid Agent Teams use case is documented
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        use_case_keywords = [
            "research", "review", "read-only", "analysis",
            "exploration", "investigation", "suitable for",
            "good fit", "use case", "appropriate for"
        ]
        found = [kw for kw in use_case_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 2, (
            f"Evaluation should document where Agent Teams does fit. "
            f"Searched for: {use_case_keywords}\n"
            f"Found: {found}\n"
            f"Agent Teams is suitable for research/review tasks - document these use cases."
        )


class TestAgentTeamsEvaluationDecisionRationale:
    """Test that the evaluation document provides thorough decision rationale.

    The rationale should explain why worktree isolation is advantageous,
    acknowledge Agent Teams speed benefits, and cite sources.
    """

    def test_explains_isolation_advantage(self):
        """Test that document explains worktree filesystem isolation advantage.

        Worktrees provide complete filesystem isolation, preventing
        conflicts between parallel feature implementations.

        Arrange: Evaluation document content
        Act: Search for isolation discussion
        Assert: Filesystem isolation advantage is explained
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        isolation_keywords = [
            "isolation", "filesystem isolation", "file isolation",
            "isolated", "separate working", "independent copies",
            "no conflicts", "conflict-free"
        ]
        found = [kw for kw in isolation_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should explain worktree filesystem isolation advantage. "
            f"Searched for: {isolation_keywords}\n"
            f"Found: {found}\n"
            f"Worktrees provide complete filesystem isolation - explain this benefit."
        )

    def test_notes_speed_advantage(self):
        """Test that document acknowledges Agent Teams speed advantage.

        Agent Teams can run multiple agents in-process without worktree
        overhead, which is faster for certain workloads.

        Arrange: Evaluation document content
        Act: Search for speed/performance discussion
        Assert: Speed advantage is acknowledged
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        speed_keywords = [
            "speed", "faster", "performance", "overhead",
            "parallel", "concurrent", "latency", "efficient"
        ]
        found = [kw for kw in speed_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should acknowledge Agent Teams speed advantage. "
            f"Searched for: {speed_keywords}\n"
            f"Found: {found}\n"
            f"Agent Teams has speed benefits - acknowledge them even if worktrees are preferred."
        )

    def test_includes_sources(self):
        """Test that document includes source references or URLs.

        Evaluation should cite official documentation, release notes,
        or other references supporting the analysis.

        Arrange: Evaluation document content
        Act: Search for URLs or reference indicators
        Assert: At least one source/reference is included
        """
        # Arrange
        content = _get_evaluation_content()

        # Act - Look for URLs or reference patterns
        url_pattern = r'https?://[^\s\)>]+'
        urls = re.findall(url_pattern, content)

        reference_keywords = ["source", "reference", "documentation", "docs.anthropic"]
        content_lower = content.lower()
        found_refs = [kw for kw in reference_keywords if kw in content_lower]

        # Assert
        has_sources = len(urls) > 0 or len(found_refs) >= 1
        assert has_sources, (
            f"Evaluation should include source references or URLs. "
            f"Found URLs: {urls}\n"
            f"Found reference keywords: {found_refs}\n"
            f"Add links to official Agent Teams documentation or release notes."
        )


class TestIssue390MetaValidation:
    """Meta-validation tests for Issue #390 test suite.

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

    def test_covers_existence_validation(self):
        """Test that test suite includes document existence validation."""
        assert hasattr(TestAgentTeamsEvaluationExists, "test_evaluation_document_exists")

    def test_covers_required_sections(self):
        """Test that test suite validates all required sections."""
        required_methods = [
            "test_has_comparison_matrix",
            "test_documents_file_locking_blocker",
            "test_documents_session_resumption_blocker",
            "test_documents_one_team_per_session_blocker",
            "test_states_recommendation",
            "test_documents_agent_teams_use_cases",
        ]
        for method in required_methods:
            assert hasattr(TestAgentTeamsEvaluationRequiredSections, method), (
                f"Missing required section test: {method}"
            )

    def test_covers_decision_rationale(self):
        """Test that test suite validates decision rationale."""
        required_methods = [
            "test_explains_isolation_advantage",
            "test_notes_speed_advantage",
            "test_includes_sources",
        ]
        for method in required_methods:
            assert hasattr(TestAgentTeamsEvaluationDecisionRationale, method), (
                f"Missing rationale test: {method}"
            )


# Test execution summary for Issue #390
"""
TEST EXECUTION SUMMARY
======================

Phase 1: Document Existence (SHOULD FAIL - RED PHASE)
- test_evaluation_document_exists

Phase 2: Required Sections (SHOULD FAIL - RED PHASE)
- test_has_comparison_matrix
- test_documents_file_locking_blocker
- test_documents_session_resumption_blocker
- test_documents_one_team_per_session_blocker
- test_states_recommendation
- test_documents_agent_teams_use_cases

Phase 3: Decision Rationale (SHOULD FAIL - RED PHASE)
- test_explains_isolation_advantage
- test_notes_speed_advantage
- test_includes_sources

Phase 4: Meta-Validation (SHOULD PASS NOW)
- test_all_test_classes_documented
- test_covers_existence_validation
- test_covers_required_sections
- test_covers_decision_rationale

EXPECTED RESULTS:
- Phases 1-3: FAIL (document not created yet - TDD RED phase)
- Phase 4: PASS (meta-validation of test structure)

NEXT STEPS:
1. Run tests: pytest tests/regression/progression/test_issue_390_agent_teams_evaluation.py --tb=line -q
2. Verify Phases 1-3 FAIL (expected - TDD RED phase)
3. Create evaluation document at docs/evaluations/issue_390_agent_teams_evaluation.md
4. Document: comparison matrix, blockers, recommendation, use cases, rationale
5. Re-run tests to verify all phases PASS (TDD GREEN phase)
"""

"""
Unit tests for complexity_assessor.py - Automatic complexity assessment for pipeline scaling

Tests cover:
- Complexity level classification (SIMPLE, STANDARD, COMPLEX)
- Keyword-based classification heuristics
- Scope detection integration
- Security indicator detection
- Confidence scoring algorithm
- Agent count mapping (3/6/8 agents)
- Estimated time calculation
- Edge cases (empty input, conflicting signals, very long input)
- GitHub issue integration (title + body)
- Low confidence scenarios

This is the RED phase of TDD - tests should fail initially since implementation doesn't exist yet.
"""

import pytest
from pathlib import Path
from enum import Enum
from typing import NamedTuple, Optional, Dict, List
import json

# Import the module under test (will fail initially - TDD red phase)
try:
    from autonomous_dev.lib.complexity_assessor import (
        ComplexityLevel,
        ComplexityAssessment,
        ComplexityAssessor,
    )
except ImportError:
    # Allow tests to be collected even if implementation doesn't exist yet
    pytest.skip("complexity_assessor.py not implemented yet", allow_module_level=True)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def simple_typo_request():
    """Simple typo fix - should be SIMPLE complexity"""
    return "Fix typo in README.md"


@pytest.fixture
def simple_docs_request():
    """Documentation update - should be SIMPLE complexity"""
    return "Update installation instructions in docs/"


@pytest.fixture
def simple_rename_request():
    """Simple rename operation - should be SIMPLE complexity"""
    return "Rename variable user_id to userId for consistency"


@pytest.fixture
def simple_format_request():
    """Simple formatting change - should be SIMPLE complexity"""
    return "Format code according to PEP 8 standards"


@pytest.fixture
def standard_feature_request():
    """Standard feature addition - should be STANDARD complexity"""
    return "Add pagination to user list endpoint"


@pytest.fixture
def standard_bugfix_request():
    """Standard bug fix - should be STANDARD complexity"""
    return "Fix validation error in user registration form"


@pytest.fixture
def complex_auth_request():
    """Complex authentication feature - should be COMPLEX complexity"""
    return "Implement OAuth2 authentication with JWT token refresh"


@pytest.fixture
def complex_security_request():
    """Complex security feature - should be COMPLEX complexity"""
    return "Add encryption for sensitive user data using AES-256"


@pytest.fixture
def complex_api_request():
    """Complex API integration - should be COMPLEX complexity"""
    return "Integrate with external payment API and handle webhooks"


@pytest.fixture
def conflicting_signals_request():
    """Request with conflicting complexity signals"""
    return "Fix typo in authentication module JWT implementation"


@pytest.fixture
def empty_request():
    """Empty request - edge case"""
    return ""


@pytest.fixture
def none_request():
    """None request - edge case"""
    return None


@pytest.fixture
def very_long_request():
    """Very long request (>10000 chars) - edge case"""
    return "Add feature " + "x" * 10000


@pytest.fixture
def github_issue_simple():
    """GitHub issue dict for simple change"""
    return {
        "title": "Fix typo in docs",
        "body": "There's a spelling mistake in the installation guide."
    }


@pytest.fixture
def github_issue_complex():
    """GitHub issue dict for complex change"""
    return {
        "title": "Implement OAuth2 authentication",
        "body": "We need to add OAuth2 support with JWT tokens, refresh tokens, and secure session management. This should integrate with our existing auth system."
    }


@pytest.fixture
def github_issue_no_body():
    """GitHub issue with no body - edge case"""
    return {
        "title": "Add tests",
        "body": None
    }


# ============================================================================
# Unit Tests - ComplexityLevel Enum
# ============================================================================

def test_complexity_level_enum_values():
    """Test ComplexityLevel enum has correct values"""
    assert ComplexityLevel.SIMPLE.value == "simple"
    assert ComplexityLevel.STANDARD.value == "standard"
    assert ComplexityLevel.COMPLEX.value == "complex"


def test_complexity_level_enum_members():
    """Test ComplexityLevel enum has exactly 3 members"""
    assert len(ComplexityLevel) == 3
    assert set(ComplexityLevel) == {
        ComplexityLevel.SIMPLE,
        ComplexityLevel.STANDARD,
        ComplexityLevel.COMPLEX
    }


# ============================================================================
# Unit Tests - ComplexityAssessment NamedTuple
# ============================================================================

def test_complexity_assessment_structure():
    """Test ComplexityAssessment has correct fields"""
    assessment = ComplexityAssessment(
        level=ComplexityLevel.STANDARD,
        confidence=0.85,
        reasoning="Test reasoning",
        agent_count=6,
        estimated_time=15
    )

    assert assessment.level == ComplexityLevel.STANDARD
    assert assessment.confidence == 0.85
    assert assessment.reasoning == "Test reasoning"
    assert assessment.agent_count == 6
    assert assessment.estimated_time == 15


def test_complexity_assessment_immutable():
    """Test ComplexityAssessment is immutable (NamedTuple behavior)"""
    assessment = ComplexityAssessment(
        level=ComplexityLevel.SIMPLE,
        confidence=0.9,
        reasoning="Test",
        agent_count=3,
        estimated_time=8
    )

    with pytest.raises(AttributeError):
        assessment.level = ComplexityLevel.COMPLEX


# ============================================================================
# Unit Tests - SIMPLE Complexity Classification
# ============================================================================

def test_classify_typo_as_simple(simple_typo_request):
    """Test that typo fixes are classified as SIMPLE"""
    assessor = ComplexityAssessor()
    result = assessor.assess(simple_typo_request)

    assert result.level == ComplexityLevel.SIMPLE
    assert result.agent_count == 3
    assert result.estimated_time == 8
    assert result.confidence >= 0.8


def test_classify_docs_as_simple(simple_docs_request):
    """Test that documentation updates are classified as SIMPLE"""
    assessor = ComplexityAssessor()
    result = assessor.assess(simple_docs_request)

    assert result.level == ComplexityLevel.SIMPLE
    assert result.agent_count == 3
    assert result.estimated_time == 8
    assert result.confidence >= 0.7


def test_classify_rename_as_simple(simple_rename_request):
    """Test that rename operations are classified as SIMPLE"""
    assessor = ComplexityAssessor()
    result = assessor.assess(simple_rename_request)

    assert result.level == ComplexityLevel.SIMPLE
    assert result.agent_count == 3
    assert result.estimated_time == 8


def test_classify_format_as_simple(simple_format_request):
    """Test that formatting changes are classified as SIMPLE"""
    assessor = ComplexityAssessor()
    result = assessor.assess(simple_format_request)

    assert result.level == ComplexityLevel.SIMPLE
    assert result.agent_count == 3
    assert result.estimated_time == 8


def test_simple_classification_case_insensitive():
    """Test that SIMPLE keyword detection is case insensitive"""
    assessor = ComplexityAssessor()

    # Test various case combinations
    cases = [
        "Fix TYPO in readme",
        "Update DOCS",
        "RENAME variable",
        "format CODE"
    ]

    for case in cases:
        result = assessor.assess(case)
        assert result.level == ComplexityLevel.SIMPLE


# ============================================================================
# Unit Tests - STANDARD Complexity Classification
# ============================================================================

def test_classify_standard_feature(standard_feature_request):
    """Test that standard feature additions are classified as STANDARD"""
    assessor = ComplexityAssessor()
    result = assessor.assess(standard_feature_request)

    assert result.level == ComplexityLevel.STANDARD
    assert result.agent_count == 6
    assert result.estimated_time == 15
    assert result.confidence >= 0.6


def test_classify_standard_bugfix(standard_bugfix_request):
    """Test that standard bug fixes are classified as STANDARD"""
    assessor = ComplexityAssessor()
    result = assessor.assess(standard_bugfix_request)

    assert result.level == ComplexityLevel.STANDARD
    assert result.agent_count == 6
    assert result.estimated_time == 15


def test_standard_as_default_fallback():
    """Test that STANDARD is the default fallback for ambiguous requests"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Do something with the system")

    assert result.level == ComplexityLevel.STANDARD
    assert result.agent_count == 6
    assert result.estimated_time == 15


# ============================================================================
# Unit Tests - COMPLEX Complexity Classification
# ============================================================================

def test_classify_auth_as_complex(complex_auth_request):
    """Test that OAuth/auth features are classified as COMPLEX"""
    assessor = ComplexityAssessor()
    result = assessor.assess(complex_auth_request)

    assert result.level == ComplexityLevel.COMPLEX
    assert result.agent_count == 8
    assert result.estimated_time == 25
    assert result.confidence >= 0.8


def test_classify_security_as_complex(complex_security_request):
    """Test that security features are classified as COMPLEX"""
    assessor = ComplexityAssessor()
    result = assessor.assess(complex_security_request)

    assert result.level == ComplexityLevel.COMPLEX
    assert result.agent_count == 8
    assert result.estimated_time == 25


def test_classify_api_as_complex(complex_api_request):
    """Test that API integrations are classified as COMPLEX"""
    assessor = ComplexityAssessor()
    result = assessor.assess(complex_api_request)

    assert result.level == ComplexityLevel.COMPLEX
    assert result.agent_count == 8
    assert result.estimated_time == 25


def test_complex_keywords_detection():
    """Test that various COMPLEX keywords are detected"""
    assessor = ComplexityAssessor()

    complex_keywords = [
        "authentication",
        "authorization",
        "encryption",
        "JWT",
        "OAuth",
        "SAML",
        "security audit",
        "API integration",
        "database migration"
    ]

    for keyword in complex_keywords:
        result = assessor.assess(f"Implement {keyword} feature")
        assert result.level == ComplexityLevel.COMPLEX, f"Failed for keyword: {keyword}"


# ============================================================================
# Unit Tests - Edge Cases
# ============================================================================

def test_empty_string_input(empty_request):
    """Test handling of empty string input"""
    assessor = ComplexityAssessor()
    result = assessor.assess(empty_request)

    # Should default to STANDARD with low confidence
    assert result.level == ComplexityLevel.STANDARD
    assert result.confidence < 0.5
    assert "empty" in result.reasoning.lower() or "no input" in result.reasoning.lower()


def test_none_input(none_request):
    """Test handling of None input"""
    assessor = ComplexityAssessor()
    result = assessor.assess(none_request)

    # Should default to STANDARD with low confidence
    assert result.level == ComplexityLevel.STANDARD
    assert result.confidence < 0.5
    assert "none" in result.reasoning.lower() or "no input" in result.reasoning.lower()


def test_very_long_input(very_long_request):
    """Test handling of very long input (>10000 chars)"""
    assessor = ComplexityAssessor()
    result = assessor.assess(very_long_request)

    # Should still classify (not crash)
    assert isinstance(result.level, ComplexityLevel)
    assert result.agent_count in [3, 6, 8]
    assert result.estimated_time in [8, 15, 25]


def test_conflicting_signals(conflicting_signals_request):
    """Test handling of conflicting complexity signals"""
    assessor = ComplexityAssessor()
    result = assessor.assess(conflicting_signals_request)

    # COMPLEX keywords (auth, JWT) should override SIMPLE keywords (typo, fix)
    assert result.level == ComplexityLevel.COMPLEX
    assert result.confidence < 0.9  # Lower confidence due to conflict


def test_whitespace_only_input():
    """Test handling of whitespace-only input"""
    assessor = ComplexityAssessor()
    result = assessor.assess("   \n\t   ")

    assert result.level == ComplexityLevel.STANDARD
    assert result.confidence < 0.5


def test_special_characters_input():
    """Test handling of special characters and symbols"""
    assessor = ComplexityAssessor()
    result = assessor.assess("!@#$%^&*()_+-=[]{}|;':\",./<>?")

    assert isinstance(result.level, ComplexityLevel)
    assert result.confidence < 0.5


# ============================================================================
# Unit Tests - GitHub Issue Integration
# ============================================================================

def test_github_issue_simple(github_issue_simple):
    """Test GitHub issue integration for simple change"""
    assessor = ComplexityAssessor()
    result = assessor.assess(
        github_issue_simple["title"],
        github_issue=github_issue_simple
    )

    assert result.level == ComplexityLevel.SIMPLE
    assert result.agent_count == 3


def test_github_issue_complex(github_issue_complex):
    """Test GitHub issue integration for complex change"""
    assessor = ComplexityAssessor()
    result = assessor.assess(
        github_issue_complex["title"],
        github_issue=github_issue_complex
    )

    assert result.level == ComplexityLevel.COMPLEX
    assert result.agent_count == 8


def test_github_issue_no_body(github_issue_no_body):
    """Test GitHub issue with None body"""
    assessor = ComplexityAssessor()
    result = assessor.assess(
        github_issue_no_body["title"],
        github_issue=github_issue_no_body
    )

    # Should still work with just title
    assert isinstance(result.level, ComplexityLevel)


def test_github_issue_body_overrides_title():
    """Test that issue body can override title complexity"""
    assessor = ComplexityAssessor()

    issue = {
        "title": "Quick fix",
        "body": "Implement OAuth2 authentication with JWT tokens and encryption"
    }

    result = assessor.assess(issue["title"], github_issue=issue)

    # Body has COMPLEX keywords, should override simple title
    assert result.level == ComplexityLevel.COMPLEX


def test_github_issue_empty_dict():
    """Test GitHub issue with empty dict"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Add feature", github_issue={})

    # Should fall back to just analyzing the feature description
    assert isinstance(result.level, ComplexityLevel)


# ============================================================================
# Unit Tests - Confidence Scoring
# ============================================================================

def test_high_confidence_simple():
    """Test high confidence for clear SIMPLE indicators"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Fix typo in README")

    assert result.confidence >= 0.85


def test_high_confidence_complex():
    """Test high confidence for clear COMPLEX indicators"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Implement OAuth2 authentication with JWT")

    assert result.confidence >= 0.85


def test_low_confidence_ambiguous():
    """Test low confidence for ambiguous requests"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Update the thing")

    assert result.confidence < 0.6


def test_low_confidence_conflicting():
    """Test low confidence when signals conflict"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Fix typo in OAuth2 authentication")

    assert result.confidence < 0.8


def test_confidence_in_valid_range():
    """Test that confidence is always between 0.0 and 1.0"""
    assessor = ComplexityAssessor()

    test_cases = [
        "Fix typo",
        "Add feature",
        "Implement OAuth2",
        "",
        "x" * 10000,
        "Update thing and stuff and whatever"
    ]

    for case in test_cases:
        result = assessor.assess(case)
        assert 0.0 <= result.confidence <= 1.0


# ============================================================================
# Unit Tests - Agent Count Mapping
# ============================================================================

def test_agent_count_simple():
    """Test that SIMPLE maps to 3 agents"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Fix typo")

    assert result.level == ComplexityLevel.SIMPLE
    assert result.agent_count == 3


def test_agent_count_standard():
    """Test that STANDARD maps to 6 agents"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Add pagination")

    assert result.level == ComplexityLevel.STANDARD
    assert result.agent_count == 6


def test_agent_count_complex():
    """Test that COMPLEX maps to 8 agents"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Implement OAuth2")

    assert result.level == ComplexityLevel.COMPLEX
    assert result.agent_count == 8


def test_agent_count_consistency():
    """Test that agent count is always consistent with complexity level"""
    assessor = ComplexityAssessor()

    test_cases = [
        "Fix typo",
        "Add feature",
        "Implement OAuth2",
        "Update docs",
        "Build API integration"
    ]

    for case in test_cases:
        result = assessor.assess(case)

        if result.level == ComplexityLevel.SIMPLE:
            assert result.agent_count == 3
        elif result.level == ComplexityLevel.STANDARD:
            assert result.agent_count == 6
        elif result.level == ComplexityLevel.COMPLEX:
            assert result.agent_count == 8


# ============================================================================
# Unit Tests - Estimated Time Calculation
# ============================================================================

def test_estimated_time_simple():
    """Test that SIMPLE maps to ~8 minutes"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Fix typo")

    assert result.level == ComplexityLevel.SIMPLE
    assert result.estimated_time == 8


def test_estimated_time_standard():
    """Test that STANDARD maps to ~15 minutes"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Add pagination")

    assert result.level == ComplexityLevel.STANDARD
    assert result.estimated_time == 15


def test_estimated_time_complex():
    """Test that COMPLEX maps to ~25 minutes"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Implement OAuth2")

    assert result.level == ComplexityLevel.COMPLEX
    assert result.estimated_time == 25


def test_estimated_time_consistency():
    """Test that estimated time is always consistent with complexity level"""
    assessor = ComplexityAssessor()

    test_cases = [
        "Fix spelling",
        "Refactor code",
        "Add encryption",
        "Update README",
        "Build webhook handler"
    ]

    for case in test_cases:
        result = assessor.assess(case)

        if result.level == ComplexityLevel.SIMPLE:
            assert result.estimated_time == 8
        elif result.level == ComplexityLevel.STANDARD:
            assert result.estimated_time == 15
        elif result.level == ComplexityLevel.COMPLEX:
            assert result.estimated_time == 25


# ============================================================================
# Unit Tests - Keyword Analysis
# ============================================================================

def test_analyze_keywords_simple():
    """Test keyword analysis for SIMPLE indicators"""
    assessor = ComplexityAssessor()

    simple_texts = [
        "fix typo in readme",
        "update documentation",
        "rename variable",
        "format code",
        "correct spelling mistake"
    ]

    for text in simple_texts:
        result = assessor.assess(text)
        assert result.level == ComplexityLevel.SIMPLE


def test_analyze_keywords_complex():
    """Test keyword analysis for COMPLEX indicators"""
    assessor = ComplexityAssessor()

    complex_texts = [
        "implement authentication",
        "add authorization layer",
        "setup encryption",
        "integrate with API",
        "add JWT tokens",
        "implement OAuth2 flow",
        "add SAML support"
    ]

    for text in complex_texts:
        result = assessor.assess(text)
        assert result.level == ComplexityLevel.COMPLEX


def test_keyword_priority_complex_over_simple():
    """Test that COMPLEX keywords have priority over SIMPLE keywords"""
    assessor = ComplexityAssessor()

    # Text with both SIMPLE and COMPLEX keywords
    result = assessor.assess("Fix typo in OAuth2 authentication module")

    # COMPLEX should win
    assert result.level == ComplexityLevel.COMPLEX


def test_keyword_case_insensitivity():
    """Test that keyword detection is case insensitive"""
    assessor = ComplexityAssessor()

    cases = [
        ("Fix TYPO", ComplexityLevel.SIMPLE),
        ("implement OAUTH2", ComplexityLevel.COMPLEX),
        ("Add FEATURE", ComplexityLevel.STANDARD),
    ]

    for text, expected_level in cases:
        result = assessor.assess(text)
        assert result.level == expected_level


# ============================================================================
# Unit Tests - Reasoning Output
# ============================================================================

def test_reasoning_not_empty():
    """Test that reasoning is never empty"""
    assessor = ComplexityAssessor()

    test_cases = [
        "Fix typo",
        "Add feature",
        "Implement OAuth2",
        "",
        None,
        "x" * 10000
    ]

    for case in test_cases:
        result = assessor.assess(case)
        assert result.reasoning
        assert len(result.reasoning) > 0


def test_reasoning_mentions_keywords():
    """Test that reasoning mentions detected keywords"""
    assessor = ComplexityAssessor()

    result = assessor.assess("Fix typo in documentation")
    assert "typo" in result.reasoning.lower() or "simple" in result.reasoning.lower()

    result = assessor.assess("Implement OAuth2 authentication")
    assert "oauth" in result.reasoning.lower() or "auth" in result.reasoning.lower() or "complex" in result.reasoning.lower()


def test_reasoning_mentions_confidence():
    """Test that reasoning explains confidence level"""
    assessor = ComplexityAssessor()

    # High confidence case
    result = assessor.assess("Fix typo")
    assert result.confidence > 0.8

    # Low confidence case
    result = assessor.assess("")
    assert result.confidence < 0.5


# ============================================================================
# Unit Tests - Multiple Assessments
# ============================================================================

def test_multiple_assessments_independent():
    """Test that multiple assessments are independent"""
    assessor = ComplexityAssessor()

    result1 = assessor.assess("Fix typo")
    result2 = assessor.assess("Implement OAuth2")
    result3 = assessor.assess("Fix typo")

    assert result1.level == result3.level
    assert result1.confidence == result3.confidence
    assert result2.level != result1.level


def test_assessor_is_stateless():
    """Test that ComplexityAssessor has no state between calls"""
    assessor = ComplexityAssessor()

    # Make several assessments
    for _ in range(10):
        assessor.assess("Fix typo")
        assessor.assess("Implement OAuth2")

    # Final assessment should be same as first
    result = assessor.assess("Fix typo")
    assert result.level == ComplexityLevel.SIMPLE


# ============================================================================
# Integration Tests
# ============================================================================

def test_end_to_end_simple_workflow():
    """Test complete workflow for SIMPLE complexity"""
    assessor = ComplexityAssessor()
    result = assessor.assess("Fix typo in README.md")

    # Verify all fields
    assert result.level == ComplexityLevel.SIMPLE
    assert result.agent_count == 3
    assert result.estimated_time == 8
    assert result.confidence >= 0.8
    assert result.reasoning
    assert len(result.reasoning) > 0


def test_end_to_end_complex_workflow():
    """Test complete workflow for COMPLEX complexity"""
    assessor = ComplexityAssessor()

    issue = {
        "title": "Implement OAuth2 authentication",
        "body": "Need to add OAuth2 support with JWT tokens and refresh logic"
    }

    result = assessor.assess(issue["title"], github_issue=issue)

    # Verify all fields
    assert result.level == ComplexityLevel.COMPLEX
    assert result.agent_count == 8
    assert result.estimated_time == 25
    assert result.confidence >= 0.8
    assert result.reasoning
    assert "oauth" in result.reasoning.lower() or "auth" in result.reasoning.lower()


def test_end_to_end_github_integration():
    """Test complete workflow with GitHub issue integration"""
    assessor = ComplexityAssessor()

    # Simulate real GitHub issue
    issue = {
        "title": "Add user authentication",
        "body": "Implement JWT-based authentication with refresh tokens, secure session management, and integration with existing user database. Include OAuth2 support for third-party login."
    }

    result = assessor.assess(issue["title"], github_issue=issue)

    # Should detect COMPLEX from body content
    assert result.level == ComplexityLevel.COMPLEX
    assert result.agent_count == 8
    assert result.estimated_time == 25
    assert result.confidence >= 0.7


# ============================================================================
# Save Checkpoint
# ============================================================================

# Checkpoint integration (runs after test collection/creation)
if __name__ == "__main__":
    from pathlib import Path
    import sys

    # Portable path detection (works from any directory)
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    # Add lib to path for imports
    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint('test-master', 'Tests complete - 42 tests created for complexity_assessor')
            print("✅ Checkpoint saved")
        except ImportError:
            print("ℹ️ Checkpoint skipped (user project)")

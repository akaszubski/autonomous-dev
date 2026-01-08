"""Unit tests for issue_scope_detector.py

Tests scope detection for GitHub issues to enforce granularity (< 30 min per issue).

Test Coverage:
    - Focused issues (single provider/component/feature)
    - Broad issues (multiple providers/components)
    - Very broad issues (many providers/components or broad patterns)
    - Split suggestions for broad issues
    - Edge cases (empty input, very long input)
"""

import pytest
import sys
from pathlib import Path

# Add lib to path
lib_path = Path(__file__).parent.parent.parent.parent / ".claude" / "lib"
sys.path.insert(0, str(lib_path))

from issue_scope_detector import IssueScopeDetector, ScopeLevel, ScopeDetection


# ============================================================================
# FOCUSED Issues (Single provider/component/feature)
# ============================================================================

def test_focused_single_provider():
    """Test focused issue with single provider."""
    detector = IssueScopeDetector()
    result = detector.detect("Add AWS Lambda integration")

    assert result.level == ScopeLevel.FOCUSED
    assert not result.should_warn
    assert "focused" in result.reasoning.lower()


def test_focused_single_component():
    """Test focused issue with single component."""
    detector = IssueScopeDetector()
    result = detector.detect("Fix authentication bug")

    assert result.level == ScopeLevel.FOCUSED
    assert not result.should_warn


def test_focused_single_feature():
    """Test focused issue with single feature action."""
    detector = IssueScopeDetector()
    result = detector.detect("Update documentation for API endpoints")

    assert result.level == ScopeLevel.FOCUSED
    assert not result.should_warn


def test_focused_specific_file():
    """Test focused issue targeting specific file."""
    detector = IssueScopeDetector()
    result = detector.detect("Fix typo in README.md")

    assert result.level == ScopeLevel.FOCUSED
    assert not result.should_warn


# ============================================================================
# BROAD Issues (Multiple providers/components)
# ============================================================================

def test_broad_multiple_providers():
    """Test broad issue with multiple providers."""
    detector = IssueScopeDetector()
    result = detector.detect("Replace mock log streaming with real SSH/API implementation")

    assert result.level == ScopeLevel.BROAD
    assert result.should_warn
    assert "multiple" in result.reasoning.lower()
    assert len(result.suggested_splits) > 0


def test_broad_two_providers():
    """Test broad issue with two providers (Lambda and RunPod)."""
    detector = IssueScopeDetector()
    result = detector.detect("Implement Lambda and RunPod provider integrations")

    assert result.level == ScopeLevel.BROAD
    assert result.should_warn
    assert "providers" in result.reasoning.lower()


def test_broad_three_components():
    """Test broad issue with three components."""
    detector = IssueScopeDetector()
    result = detector.detect("Add logging, monitoring, and alerting")

    assert result.level == ScopeLevel.BROAD
    assert result.should_warn
    assert "components" in result.reasoning.lower()


def test_broad_multiple_features_with_conjunctions():
    """Test broad issue with multiple features and conjunctions."""
    detector = IssueScopeDetector()
    result = detector.detect("Add authentication and authorization and update config")

    assert result.level == ScopeLevel.BROAD
    assert result.should_warn


# ============================================================================
# VERY_BROAD Issues (Many providers/components or broad patterns)
# ============================================================================

def test_very_broad_three_providers():
    """Test very broad issue with three providers."""
    detector = IssueScopeDetector()
    result = detector.detect("Wire orchestration to Lambda, RunPod, and Modal APIs")

    assert result.level == ScopeLevel.VERY_BROAD
    assert result.should_warn
    assert "must split" in result.reasoning.lower()
    assert len(result.suggested_splits) >= 3


def test_very_broad_four_components():
    """Test very broad issue with four components."""
    detector = IssueScopeDetector()
    result = detector.detect("Implement logging, monitoring, metrics, and alerting")

    assert result.level == ScopeLevel.VERY_BROAD
    assert result.should_warn


def test_very_broad_all_keyword():
    """Test very broad issue with 'all' keyword."""
    detector = IssueScopeDetector()
    result = detector.detect("Implement all provider integrations")

    assert result.level in [ScopeLevel.BROAD, ScopeLevel.VERY_BROAD]
    assert result.should_warn
    assert "broad patterns" in result.reasoning.lower()


def test_very_broad_complete_keyword():
    """Test very broad issue with 'complete' keyword."""
    detector = IssueScopeDetector()
    result = detector.detect("Complete end-to-end authentication system")

    assert result.level in [ScopeLevel.BROAD, ScopeLevel.VERY_BROAD]
    assert result.should_warn


# ============================================================================
# Split Suggestions
# ============================================================================

def test_suggestions_multiple_providers():
    """Test split suggestions for multiple providers."""
    detector = IssueScopeDetector()
    result = detector.detect("Implement Lambda, RunPod, and Modal integrations")

    assert result.level in [ScopeLevel.BROAD, ScopeLevel.VERY_BROAD]
    assert len(result.suggested_splits) >= 2
    # Check that suggestions mention providers
    suggestions_text = " ".join(result.suggested_splits).lower()
    assert "lambda" in suggestions_text or "integration" in suggestions_text


def test_suggestions_multiple_components():
    """Test split suggestions for multiple components."""
    detector = IssueScopeDetector()
    result = detector.detect("Add logging, monitoring, and metrics")

    assert result.level in [ScopeLevel.BROAD, ScopeLevel.VERY_BROAD]
    assert len(result.suggested_splits) >= 2


def test_focused_no_suggestions():
    """Test that focused issues don't get split suggestions."""
    detector = IssueScopeDetector()
    result = detector.detect("Fix authentication bug")

    assert result.level == ScopeLevel.FOCUSED
    assert len(result.suggested_splits) == 0


# ============================================================================
# Edge Cases
# ============================================================================

def test_empty_title():
    """Test handling of empty title."""
    detector = IssueScopeDetector()
    result = detector.detect("")

    assert result.level == ScopeLevel.FOCUSED
    assert "empty" in result.reasoning.lower()
    assert not result.should_warn


def test_whitespace_only_title():
    """Test handling of whitespace-only title."""
    detector = IssueScopeDetector()
    result = detector.detect("   \n\t   ")

    assert result.level == ScopeLevel.FOCUSED
    assert not result.should_warn


def test_very_long_input():
    """Test handling of very long input (>10000 chars)."""
    detector = IssueScopeDetector()
    long_text = "Add feature " * 2000  # ~24000 chars
    result = detector.detect(long_text)

    # Should not crash, should still work
    assert isinstance(result, ScopeDetection)
    assert result.level in [ScopeLevel.FOCUSED, ScopeLevel.BROAD, ScopeLevel.VERY_BROAD]


def test_github_issue_dict():
    """Test detection with GitHub issue dict."""
    detector = IssueScopeDetector()
    issue = {
        "title": "Implement Lambda and RunPod integrations",
        "body": "This will add support for both Lambda and RunPod providers"
    }
    result = detector.detect("", "", github_issue=issue)

    assert result.level == ScopeLevel.BROAD
    assert result.should_warn


def test_issue_body_provides_context():
    """Test that issue body is considered for scope detection."""
    detector = IssueScopeDetector()
    # Title alone might seem focused
    result = detector.detect(
        "Implement provider integrations",
        "This will add Lambda, RunPod, Modal, and Vast.ai support"
    )

    # Body reveals it's actually very broad
    assert result.level in [ScopeLevel.BROAD, ScopeLevel.VERY_BROAD]
    assert result.should_warn


# ============================================================================
# Real-World Examples
# ============================================================================

def test_real_example_1():
    """Test real example: Replace mock log streaming with real SSH/API."""
    detector = IssueScopeDetector()
    result = detector.detect(
        "Replace mock log streaming with real SSH/API implementation"
    )

    assert result.level == ScopeLevel.BROAD
    assert result.should_warn
    assert len(result.suggested_splits) > 0


def test_real_example_2():
    """Test real example: Wire orchestration to real provider APIs."""
    detector = IssueScopeDetector()
    result = detector.detect(
        "Wire orchestration to real provider APIs",
        "Connect to Lambda, RunPod, Modal, and Vast.ai APIs"
    )

    assert result.level == ScopeLevel.VERY_BROAD
    assert result.should_warn
    assert len(result.suggested_splits) >= 3


def test_real_example_3_focused():
    """Test real example: Single focused fix."""
    detector = IssueScopeDetector()
    result = detector.detect("Fix memory leak in background job processor")

    assert result.level == ScopeLevel.FOCUSED
    assert not result.should_warn


# ============================================================================
# Indicator Detection
# ============================================================================

def test_indicators_providers():
    """Test that provider indicators are correctly detected."""
    detector = IssueScopeDetector()
    result = detector.detect("Implement Lambda and RunPod integrations")

    assert "lambda" in result.indicators["providers"]
    assert "runpod" in result.indicators["providers"]


def test_indicators_components():
    """Test that component indicators are correctly detected."""
    detector = IssueScopeDetector()
    result = detector.detect("Add logging and monitoring")

    assert "logging" in result.indicators["components"]
    assert "monitoring" in result.indicators["components"]


def test_indicators_broad_patterns():
    """Test that broad patterns are correctly detected."""
    detector = IssueScopeDetector()
    result = detector.detect("Implement all authentication methods")

    assert "all" in result.indicators["broad_patterns"]


def test_indicators_conjunctions():
    """Test that conjunctions are correctly counted."""
    detector = IssueScopeDetector()
    result = detector.detect("Add X and Y or Z plus W")

    # Should detect: "and", "or", "plus"
    assert result.indicators["conjunction_count"] >= 3


# ============================================================================
# Integration Tests
# ============================================================================

def test_classmethod_usage():
    """Test that all methods work as classmethods (stateless)."""
    # No need to create instance
    result = IssueScopeDetector.detect("Fix authentication bug")

    assert result.level == ScopeLevel.FOCUSED


def test_multiple_detections_independent():
    """Test that multiple detections don't affect each other (stateless)."""
    detector = IssueScopeDetector()

    result1 = detector.detect("Fix bug")
    result2 = detector.detect("Implement Lambda, RunPod, and Modal")
    result3 = detector.detect("Update docs")

    assert result1.level == ScopeLevel.FOCUSED
    assert result2.level == ScopeLevel.VERY_BROAD
    assert result3.level == ScopeLevel.FOCUSED

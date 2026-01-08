"""
Unit tests for doc_update_risk_classifier.py - Risk classification for documentation updates

Tests cover:
- LOW_RISK classification: CHANGELOG.md, README.md, PROJECT.md metadata
- HIGH_RISK classification: PROJECT.md GOALS, CONSTRAINTS, SCOPE changes
- Risk level detection based on file path
- Risk level detection based on content changes
- Edge cases: empty diffs, unknown files, mixed changes
- Confidence scoring for classification
- Integration with doc-master auto-apply logic

This is the RED phase of TDD - tests should fail initially since implementation doesn't exist yet.

Date: 2026-01-09
Issue: #204
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import pytest
from pathlib import Path
from enum import Enum
from typing import NamedTuple, Optional, Dict, List
import sys

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import the module under test (will fail initially - TDD red phase)
try:
    from doc_update_risk_classifier import (
        RiskLevel,
        RiskClassification,
        DocUpdateRiskClassifier,
        classify_doc_update,
    )
except ImportError:
    # Allow tests to be collected even if implementation doesn't exist yet
    pytest.skip("doc_update_risk_classifier.py not implemented yet", allow_module_level=True)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def changelog_update():
    """CHANGELOG.md update - should be LOW_RISK"""
    return {
        "file_path": "CHANGELOG.md",
        "changes": [
            "- ## [3.46.0] - 2026-01-09",
            "- ### Fixed",
            "- - Fix doc-master auto-apply (#204)"
        ]
    }


@pytest.fixture
def readme_update():
    """README.md update - should be LOW_RISK"""
    return {
        "file_path": "README.md",
        "changes": [
            "- ## Installation",
            "- Run the following command:",
            "- ```bash",
            "- npm install autonomous-dev",
            "- ```"
        ]
    }


@pytest.fixture
def project_md_metadata_update():
    """PROJECT.md metadata update (timestamp, component count) - should be LOW_RISK"""
    return {
        "file_path": ".claude/PROJECT.md",
        "changes": [
            "- **Last Updated**: 2026-01-09 (Issue #204)",
            "- | Component | Version | Count | Status |",
            "- | Skills | 1.0.0 | 28 | ✅ Compliant |",
            "- **Last Compliance Check**: 2026-01-09"
        ]
    }


@pytest.fixture
def project_md_goals_update():
    """PROJECT.md GOALS section change - should be HIGH_RISK"""
    return {
        "file_path": ".claude/PROJECT.md",
        "changes": [
            "- ## GOALS",
            "- - Build autonomous development pipeline",
            "- - Support multiple programming languages",  # NEW GOAL
            "- - Maintain 80%+ test coverage"
        ]
    }


@pytest.fixture
def project_md_constraints_update():
    """PROJECT.md CONSTRAINTS section change - should be HIGH_RISK"""
    return {
        "file_path": ".claude/PROJECT.md",
        "changes": [
            "- ## CONSTRAINTS",
            "- - Python 3.8+ required",
            "- - No external API dependencies",  # NEW CONSTRAINT
            "- - Must work offline"
        ]
    }


@pytest.fixture
def project_md_scope_update():
    """PROJECT.md SCOPE section change - should be HIGH_RISK"""
    return {
        "file_path": ".claude/PROJECT.md",
        "changes": [
            "- ## SCOPE",
            "- - IN SCOPE: Python development automation",
            "- - IN SCOPE: JavaScript/TypeScript support",  # NEW SCOPE ITEM
            "- - OUT OF SCOPE: Mobile development"
        ]
    }


@pytest.fixture
def mixed_risk_update():
    """PROJECT.md with both metadata and GOALS changes - should be HIGH_RISK"""
    return {
        "file_path": ".claude/PROJECT.md",
        "changes": [
            "- **Last Updated**: 2026-01-09",
            "- ## GOALS",
            "- - Add new strategic goal here"
        ]
    }


@pytest.fixture
def empty_diff():
    """Empty diff - should be LOW_RISK with low confidence"""
    return {
        "file_path": "README.md",
        "changes": []
    }


@pytest.fixture
def unknown_file():
    """Unknown file type - should default to HIGH_RISK (conservative)"""
    return {
        "file_path": "random_config.yaml",
        "changes": ["- some: change"]
    }


# ============================================================================
# Test Risk Classification - File Path Based
# ============================================================================

def test_classify_changelog_as_low_risk(changelog_update):
    """Test that CHANGELOG.md changes are classified as LOW_RISK"""
    # Act
    result = classify_doc_update(
        file_path=changelog_update["file_path"],
        changes=changelog_update["changes"]
    )

    # Assert
    assert result.risk_level == RiskLevel.LOW_RISK
    assert result.confidence >= 0.9
    assert "CHANGELOG" in result.reason
    assert result.requires_approval is False


def test_classify_readme_as_low_risk(readme_update):
    """Test that README.md changes are classified as LOW_RISK"""
    # Act
    result = classify_doc_update(
        file_path=readme_update["file_path"],
        changes=readme_update["changes"]
    )

    # Assert
    assert result.risk_level == RiskLevel.LOW_RISK
    assert result.confidence >= 0.9
    assert "README" in result.reason
    assert result.requires_approval is False


def test_classify_project_md_metadata_as_low_risk(project_md_metadata_update):
    """Test that PROJECT.md metadata changes (timestamp, component count) are LOW_RISK"""
    # Act
    result = classify_doc_update(
        file_path=project_md_metadata_update["file_path"],
        changes=project_md_metadata_update["changes"]
    )

    # Assert
    assert result.risk_level == RiskLevel.LOW_RISK
    assert result.confidence >= 0.8
    assert "metadata" in result.reason.lower() or "timestamp" in result.reason.lower()
    assert result.requires_approval is False


# ============================================================================
# Test Risk Classification - Content Based (HIGH_RISK sections)
# ============================================================================

def test_classify_project_md_goals_as_high_risk(project_md_goals_update):
    """Test that PROJECT.md GOALS section changes are HIGH_RISK"""
    # Act
    result = classify_doc_update(
        file_path=project_md_goals_update["file_path"],
        changes=project_md_goals_update["changes"]
    )

    # Assert
    assert result.risk_level == RiskLevel.HIGH_RISK
    assert result.confidence >= 0.9
    assert "GOALS" in result.reason
    assert result.requires_approval is True


def test_classify_project_md_constraints_as_high_risk(project_md_constraints_update):
    """Test that PROJECT.md CONSTRAINTS section changes are HIGH_RISK"""
    # Act
    result = classify_doc_update(
        file_path=project_md_constraints_update["file_path"],
        changes=project_md_constraints_update["changes"]
    )

    # Assert
    assert result.risk_level == RiskLevel.HIGH_RISK
    assert result.confidence >= 0.9
    assert "CONSTRAINTS" in result.reason
    assert result.requires_approval is True


def test_classify_project_md_scope_as_high_risk(project_md_scope_update):
    """Test that PROJECT.md SCOPE section changes are HIGH_RISK"""
    # Act
    result = classify_doc_update(
        file_path=project_md_scope_update["file_path"],
        changes=project_md_scope_update["changes"]
    )

    # Assert
    assert result.risk_level == RiskLevel.HIGH_RISK
    assert result.confidence >= 0.9
    assert "SCOPE" in result.reason
    assert result.requires_approval is True


def test_classify_mixed_risk_update_as_high_risk(mixed_risk_update):
    """Test that PROJECT.md with mixed changes (metadata + GOALS) is HIGH_RISK"""
    # Act
    result = classify_doc_update(
        file_path=mixed_risk_update["file_path"],
        changes=mixed_risk_update["changes"]
    )

    # Assert - Conservative: any HIGH_RISK content makes entire update HIGH_RISK
    assert result.risk_level == RiskLevel.HIGH_RISK
    assert result.confidence >= 0.8
    assert "GOALS" in result.reason or "mixed" in result.reason.lower()
    assert result.requires_approval is True


# ============================================================================
# Test Edge Cases
# ============================================================================

def test_classify_empty_diff_as_low_risk(empty_diff):
    """Test that empty diff is LOW_RISK but with low confidence"""
    # Act
    result = classify_doc_update(
        file_path=empty_diff["file_path"],
        changes=empty_diff["changes"]
    )

    # Assert
    assert result.risk_level == RiskLevel.LOW_RISK
    assert result.confidence < 0.5  # Low confidence for empty changes
    assert result.requires_approval is False


def test_classify_unknown_file_as_high_risk(unknown_file):
    """Test that unknown file types default to HIGH_RISK (conservative)"""
    # Act
    result = classify_doc_update(
        file_path=unknown_file["file_path"],
        changes=unknown_file["changes"]
    )

    # Assert - Conservative approach for unknown files
    assert result.risk_level == RiskLevel.HIGH_RISK
    assert result.confidence < 0.7  # Lower confidence for unknown files
    assert "unknown" in result.reason.lower() or "conservative" in result.reason.lower()
    assert result.requires_approval is True


def test_classify_handles_none_file_path():
    """Test that classifier handles None file_path gracefully"""
    # Act
    result = classify_doc_update(
        file_path=None,
        changes=["- some change"]
    )

    # Assert - Should default to HIGH_RISK for safety
    assert result.risk_level == RiskLevel.HIGH_RISK
    assert result.requires_approval is True


def test_classify_handles_none_changes():
    """Test that classifier handles None changes gracefully"""
    # Act
    result = classify_doc_update(
        file_path="README.md",
        changes=None
    )

    # Assert - Should be LOW_RISK with low confidence
    assert result.risk_level == RiskLevel.LOW_RISK
    assert result.confidence < 0.5
    assert result.requires_approval is False


# ============================================================================
# Test Multiple File Classification
# ============================================================================

def test_classify_multiple_files_all_low_risk():
    """Test classifying multiple files that are all LOW_RISK"""
    # Arrange
    files = [
        {"file_path": "CHANGELOG.md", "changes": ["- v3.46.0"]},
        {"file_path": "README.md", "changes": ["- Update docs"]},
    ]

    # Act
    results = [classify_doc_update(f["file_path"], f["changes"]) for f in files]

    # Assert - All should be LOW_RISK
    assert all(r.risk_level == RiskLevel.LOW_RISK for r in results)
    assert all(not r.requires_approval for r in results)


def test_classify_multiple_files_mixed_risk():
    """Test classifying multiple files with mixed risk levels"""
    # Arrange
    files = [
        {"file_path": "CHANGELOG.md", "changes": ["- v3.46.0"]},
        {"file_path": ".claude/PROJECT.md", "changes": ["- ## GOALS", "- New goal"]},
    ]

    # Act
    results = [classify_doc_update(f["file_path"], f["changes"]) for f in files]

    # Assert - Should have one LOW_RISK and one HIGH_RISK
    risk_levels = [r.risk_level for r in results]
    assert RiskLevel.LOW_RISK in risk_levels
    assert RiskLevel.HIGH_RISK in risk_levels


# ============================================================================
# Test Confidence Scoring
# ============================================================================

def test_high_confidence_for_clear_low_risk():
    """Test that clear LOW_RISK cases have high confidence"""
    # Act
    result = classify_doc_update(
        file_path="CHANGELOG.md",
        changes=["- ## [3.46.0] - 2026-01-09"]
    )

    # Assert
    assert result.confidence >= 0.9


def test_high_confidence_for_clear_high_risk():
    """Test that clear HIGH_RISK cases have high confidence"""
    # Act
    result = classify_doc_update(
        file_path=".claude/PROJECT.md",
        changes=["- ## GOALS", "- New strategic goal"]
    )

    # Assert
    assert result.confidence >= 0.9


def test_lower_confidence_for_edge_cases():
    """Test that edge cases have lower confidence"""
    # Act
    result = classify_doc_update(
        file_path="unknown_file.txt",
        changes=["- some change"]
    )

    # Assert
    assert result.confidence < 0.8


# ============================================================================
# Test RiskClassification Data Structure
# ============================================================================

def test_risk_classification_structure():
    """Test that RiskClassification contains expected fields"""
    # Act
    result = classify_doc_update(
        file_path="README.md",
        changes=["- Update"]
    )

    # Assert - Should have all required fields
    assert hasattr(result, 'risk_level')
    assert hasattr(result, 'confidence')
    assert hasattr(result, 'reason')
    assert hasattr(result, 'requires_approval')
    assert isinstance(result.risk_level, RiskLevel)
    assert isinstance(result.confidence, float)
    assert isinstance(result.reason, str)
    assert isinstance(result.requires_approval, bool)


def test_risk_level_enum_values():
    """Test that RiskLevel enum has expected values"""
    # Assert
    assert hasattr(RiskLevel, 'LOW_RISK')
    assert hasattr(RiskLevel, 'HIGH_RISK')


# ============================================================================
# Test Classifier Class (if using OOP approach)
# ============================================================================

def test_classifier_instance_creation():
    """Test that DocUpdateRiskClassifier can be instantiated"""
    # Act
    classifier = DocUpdateRiskClassifier()

    # Assert
    assert classifier is not None
    assert hasattr(classifier, 'classify')


def test_classifier_classify_method():
    """Test that classifier.classify() works same as classify_doc_update()"""
    # Arrange
    classifier = DocUpdateRiskClassifier()

    # Act
    result1 = classifier.classify(file_path="CHANGELOG.md", changes=["- v3.46.0"])
    result2 = classify_doc_update(file_path="CHANGELOG.md", changes=["- v3.46.0"])

    # Assert - Both approaches should give same result
    assert result1.risk_level == result2.risk_level
    assert result1.requires_approval == result2.requires_approval


# ============================================================================
# Test Case Sensitivity
# ============================================================================

def test_case_insensitive_section_detection():
    """Test that section detection is case-insensitive"""
    # Act
    result = classify_doc_update(
        file_path=".claude/PROJECT.md",
        changes=["- ## goals", "- New goal (lowercase)"]
    )

    # Assert - Should still detect as HIGH_RISK
    assert result.risk_level == RiskLevel.HIGH_RISK
    assert result.requires_approval is True


# ============================================================================
# Test Different PROJECT.md Paths
# ============================================================================

def test_classify_project_md_in_different_paths():
    """Test that PROJECT.md is detected in various paths"""
    # Arrange
    paths = [
        ".claude/PROJECT.md",
        "PROJECT.md",
        ".claude/project.md",
        "project.md"
    ]

    # Act & Assert
    for path in paths:
        result = classify_doc_update(
            file_path=path,
            changes=["- ## GOALS", "- New goal"]
        )
        assert result.risk_level == RiskLevel.HIGH_RISK
        assert result.requires_approval is True


# ============================================================================
# Test Performance & Edge Cases
# ============================================================================

def test_classify_handles_very_large_diff():
    """Test that classifier handles very large diffs efficiently"""
    # Arrange - 1000 line change
    large_changes = [f"- Line {i}" for i in range(1000)]

    # Act
    result = classify_doc_update(
        file_path="README.md",
        changes=large_changes
    )

    # Assert - Should still classify correctly
    assert result.risk_level == RiskLevel.LOW_RISK
    assert result.requires_approval is False


def test_classify_handles_unicode_content():
    """Test that classifier handles Unicode content"""
    # Act
    result = classify_doc_update(
        file_path="README.md",
        changes=["- 🚀 新功能: Add feature", "- 测试: Test update"]
    )

    # Assert
    assert result.risk_level == RiskLevel.LOW_RISK
    assert result.requires_approval is False


def test_classify_handles_special_characters():
    """Test that classifier handles special characters in changes"""
    # Act
    result = classify_doc_update(
        file_path="CHANGELOG.md",
        changes=["- Fix: Handle $VAR and @mentions", "- Support \n\t special chars"]
    )

    # Assert
    assert result.risk_level == RiskLevel.LOW_RISK
    assert result.requires_approval is False

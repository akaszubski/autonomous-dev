#!/usr/bin/env python3
"""
Unit tests for Alignment Gate Library (TDD Red Phase).

Tests strict PROJECT.md alignment validation with score-based gating.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test AlignmentGateResult dataclass structure
- Test validate_alignment_strict() with score thresholds (7+ = pass)
- Test check_scope_membership() for explicit scope matching
- Test track_alignment_decision() logging to history
- Test get_alignment_stats() for meta-validation metrics
- Test integration with genai_validate.py prompts
- Test edge cases: empty descriptions, malformed PROJECT.md
- Test constraint violation detection

Coverage Target: 90%+

Date: 2026-01-19
Issue: #251 (Strict PROJECT.md Alignment Gate)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from dataclasses import dataclass, asdict

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

# Import will fail - module doesn't exist yet (TDD!)
try:
    from alignment_gate import (
        AlignmentGateResult,
        validate_alignment_strict,
        check_scope_membership,
        track_alignment_decision,
        get_alignment_stats,
        AlignmentError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# Test fixtures
@pytest.fixture
def sample_project_md(tmp_path):
    """Create a sample PROJECT.md for testing."""
    project_md = tmp_path / "PROJECT.md"
    content = """# Project

## GOALS
- Build autonomous development tools
- Reduce manual intervention
- Improve code quality

## SCOPE
- Agent-based workflows
- CLI commands
- Git automation
- Testing infrastructure

## CONSTRAINTS
- Must maintain backward compatibility
- No breaking changes to API
- Security-first design
- Performance: <2s for CLI commands

## CURRENT_SPRINT
- Implement alignment gate
- Add strict validation
"""
    project_md.write_text(content)
    return project_md


@pytest.fixture
def minimal_project_md(tmp_path):
    """Create minimal PROJECT.md with only required sections."""
    project_md = tmp_path / "PROJECT.md"
    content = """# Project

## GOALS
- Build tools

## SCOPE
- CLI commands
"""
    project_md.write_text(content)
    return project_md


@pytest.fixture
def malformed_project_md(tmp_path):
    """Create malformed PROJECT.md for error testing."""
    project_md = tmp_path / "PROJECT.md"
    content = """# Project
This is not valid markdown structure.
No sections defined.
"""
    project_md.write_text(content)
    return project_md


# ============================================================================
# AlignmentGateResult Dataclass Tests
# ============================================================================


class TestAlignmentGateResult:
    """Test AlignmentGateResult dataclass structure and methods."""

    def test_dataclass_initialization_complete(self):
        """Test AlignmentGateResult initializes with all fields."""
        result = AlignmentGateResult(
            aligned=True,
            score=9,
            violations=["minor issue"],
            reasoning="Matches project goals",
            relevant_scope=["CLI commands"],
            suggestions=["Consider adding tests"],
            constraint_violations=[],
            confidence="high"
        )

        assert result.aligned is True
        assert result.score == 9
        assert result.violations == ["minor issue"]
        assert result.reasoning == "Matches project goals"
        assert result.relevant_scope == ["CLI commands"]
        assert result.suggestions == ["Consider adding tests"]
        assert result.constraint_violations == []
        assert result.confidence == "high"

    def test_dataclass_initialization_minimal(self):
        """Test AlignmentGateResult with minimal required fields."""
        result = AlignmentGateResult(
            aligned=False,
            score=3,
            violations=["Out of scope"],
            reasoning="Does not match SCOPE section",
            relevant_scope=[],
            suggestions=[],
            constraint_violations=["Breaks backward compatibility"],
            confidence="medium"
        )

        assert result.aligned is False
        assert result.score == 3
        assert len(result.violations) == 1
        assert len(result.constraint_violations) == 1

    def test_dataclass_to_dict(self):
        """Test AlignmentGateResult can be converted to dict."""
        result = AlignmentGateResult(
            aligned=True,
            score=8,
            violations=[],
            reasoning="Good alignment",
            relevant_scope=["Testing"],
            suggestions=[],
            constraint_violations=[],
            confidence="high"
        )

        result_dict = asdict(result)
        assert isinstance(result_dict, dict)
        assert result_dict["aligned"] is True
        assert result_dict["score"] == 8
        assert result_dict["confidence"] == "high"

    def test_dataclass_fields_are_typed(self):
        """Test AlignmentGateResult has proper type annotations."""
        # This test verifies the dataclass definition includes type hints
        result = AlignmentGateResult(
            aligned=True,
            score=7,
            violations=[],
            reasoning="Test",
            relevant_scope=[],
            suggestions=[],
            constraint_violations=[],
            confidence="medium"
        )

        assert isinstance(result.aligned, bool)
        assert isinstance(result.score, int)
        assert isinstance(result.violations, list)
        assert isinstance(result.reasoning, str)


# ============================================================================
# validate_alignment_strict() Tests
# ============================================================================


class TestValidateAlignmentStrict:
    """Test strict alignment validation with score thresholds."""

    def test_validate_in_scope_feature_passes(self, sample_project_md):
        """Test in-scope feature passes validation (score >= 7)."""
        feature_desc = "Add new CLI command for git automation"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 9,
                "violations": [],
                "reasoning": "Feature is explicitly in SCOPE (CLI commands, Git automation)",
                "relevant_scope": ["CLI commands", "Git automation"],
                "suggestions": ["Consider adding tests"],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, sample_project_md)

        assert result.aligned is True
        assert result.score >= 7
        assert len(result.violations) == 0
        assert "CLI commands" in result.relevant_scope

    def test_validate_out_of_scope_feature_blocked(self, sample_project_md):
        """Test out-of-scope feature is blocked (score < 7)."""
        feature_desc = "Add blockchain integration for cryptocurrency payments"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 2,
                "violations": ["Not in SCOPE section", "Unrelated to project goals"],
                "reasoning": "Blockchain/cryptocurrency not mentioned in GOALS or SCOPE",
                "relevant_scope": [],
                "suggestions": ["Update PROJECT.md if this is a new direction"],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, sample_project_md)

        assert result.aligned is False
        assert result.score < 7
        assert len(result.violations) > 0
        assert len(result.relevant_scope) == 0

    def test_validate_ambiguous_feature_requires_clarification(self, sample_project_md):
        """Test ambiguous feature gets score 4-6 (needs clarification)."""
        feature_desc = "Improve performance"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 5,
                "violations": ["Too vague", "No specific scope match"],
                "reasoning": "Performance is mentioned in CONSTRAINTS but not specific enough",
                "relevant_scope": [],
                "suggestions": ["Specify what component's performance", "Add metrics"],
                "constraint_violations": [],
                "confidence": "medium"
            })

            result = validate_alignment_strict(feature_desc, sample_project_md)

        assert result.aligned is False
        assert 4 <= result.score <= 6
        assert "vague" in result.violations[0].lower() or "specific" in result.violations[1].lower()

    def test_validate_constraint_violation_detected(self, sample_project_md):
        """Test constraint violations are detected and block approval."""
        feature_desc = "Rewrite API with breaking changes for better design"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 8,  # Good scope match but...
                "violations": [],
                "reasoning": "Matches SCOPE but violates CONSTRAINTS",
                "relevant_scope": ["CLI commands"],
                "suggestions": ["Make changes backward compatible"],
                "constraint_violations": ["No breaking changes to API"],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, sample_project_md)

        assert result.aligned is False  # Blocked by constraint violation
        assert result.score == 8  # Score high but...
        assert len(result.constraint_violations) > 0
        assert "breaking" in result.constraint_violations[0].lower()

    def test_validate_empty_feature_description_fails(self, sample_project_md):
        """Test empty feature description raises error."""
        with pytest.raises(AlignmentError) as exc_info:
            validate_alignment_strict("", sample_project_md)

        assert "empty" in str(exc_info.value).lower() or "missing" in str(exc_info.value).lower()

    def test_validate_whitespace_only_description_fails(self, sample_project_md):
        """Test whitespace-only description raises error."""
        with pytest.raises(AlignmentError) as exc_info:
            validate_alignment_strict("   \n\t  ", sample_project_md)

        assert "empty" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_validate_nonexistent_project_md_fails(self):
        """Test validation with nonexistent PROJECT.md raises error."""
        with pytest.raises(AlignmentError) as exc_info:
            validate_alignment_strict(
                "Add feature",
                Path("/nonexistent/PROJECT.md")
            )

        assert "not found" in str(exc_info.value).lower() or "exist" in str(exc_info.value).lower()

    def test_validate_malformed_project_md_fails(self, malformed_project_md):
        """Test validation with malformed PROJECT.md raises error."""
        with pytest.raises(AlignmentError) as exc_info:
            validate_alignment_strict("Add feature", malformed_project_md)

        assert "malformed" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_validate_with_minimal_project_md(self, minimal_project_md):
        """Test validation works with minimal PROJECT.md (only GOALS/SCOPE)."""
        feature_desc = "Add new CLI command"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 7,
                "violations": [],
                "reasoning": "Matches SCOPE (CLI commands)",
                "relevant_scope": ["CLI commands"],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "medium"
            })

            result = validate_alignment_strict(feature_desc, minimal_project_md)

        assert result.aligned is True
        assert result.score >= 7

    def test_validate_prompt_includes_strict_instructions(self, sample_project_md):
        """Test validation prompt includes strict gatekeeper instructions."""
        feature_desc = "Add feature"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 7,
                "violations": [],
                "reasoning": "Test",
                "relevant_scope": ["Test"],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "high"
            })

            validate_alignment_strict(feature_desc, sample_project_md)

            call_args = mock_llm.call_args[0][0]
            assert "explicit" in call_args.lower() or "strict" in call_args.lower()
            assert "gatekeeper" in call_args.lower() or "critical" in call_args.lower()

    def test_validate_score_threshold_is_7(self, sample_project_md):
        """Test score threshold is exactly 7 for approval."""
        feature_desc = "Borderline feature"

        # Test score = 7 (should pass)
        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 7,
                "violations": [],
                "reasoning": "Minimal alignment",
                "relevant_scope": ["Test"],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "medium"
            })

            result = validate_alignment_strict(feature_desc, sample_project_md)
            assert result.aligned is True

        # Test score = 6 (should fail)
        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 6,
                "violations": ["Below threshold"],
                "reasoning": "Not quite aligned",
                "relevant_scope": [],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "medium"
            })

            result = validate_alignment_strict(feature_desc, sample_project_md)
            assert result.aligned is False


# ============================================================================
# check_scope_membership() Tests
# ============================================================================


class TestCheckScopeMembership:
    """Test explicit scope membership checking."""

    def test_scope_explicit_match_returns_true(self):
        """Test feature with explicit scope match returns True."""
        feature = "Add new CLI command for batch processing"
        scope_section = """
- Agent-based workflows
- CLI commands
- Git automation
- Testing infrastructure
"""

        result = check_scope_membership(feature, scope_section)
        assert result is True

    def test_scope_no_match_returns_false(self):
        """Test feature with no scope match returns False."""
        feature = "Add blockchain cryptocurrency wallet"
        scope_section = """
- Agent-based workflows
- CLI commands
- Git automation
"""

        result = check_scope_membership(feature, scope_section)
        assert result is False

    def test_scope_partial_keyword_match_returns_false(self):
        """Test partial keyword match is not sufficient (strict matching)."""
        feature = "Add CLI-like interface for web dashboard"
        scope_section = """
- CLI commands
- Git automation
"""

        # "CLI-like" is not the same as "CLI commands" - should be strict
        result = check_scope_membership(feature, scope_section)
        assert result is False

    def test_scope_related_but_not_explicit_returns_false(self):
        """Test related but not explicit match returns False."""
        feature = "Add mercurial version control support"
        scope_section = """
- Git automation
- Testing infrastructure
"""

        # Mercurial is version control (related to Git) but not explicitly listed
        result = check_scope_membership(feature, scope_section)
        assert result is False

    def test_scope_empty_section_returns_false(self):
        """Test empty scope section returns False."""
        feature = "Add any feature"
        scope_section = ""

        result = check_scope_membership(feature, scope_section)
        assert result is False

    def test_scope_case_insensitive_matching(self):
        """Test scope matching is case insensitive."""
        feature = "Add new cli COMMAND"
        scope_section = """
- CLI commands
- Git automation
"""

        result = check_scope_membership(feature, scope_section)
        assert result is True

    def test_scope_multiline_handling(self):
        """Test scope section with various formatting."""
        feature = "Add agent workflow"
        scope_section = """
- Agent-based workflows
  - Sub-item 1
  - Sub-item 2
- CLI commands
"""

        result = check_scope_membership(feature, scope_section)
        assert result is True


# ============================================================================
# track_alignment_decision() Tests
# ============================================================================


class TestTrackAlignmentDecision:
    """Test alignment decision logging to history."""

    def test_track_decision_creates_history_file(self, tmp_path):
        """Test track_alignment_decision creates history file if missing."""
        history_path = tmp_path / "alignment_history.jsonl"

        result = AlignmentGateResult(
            aligned=True,
            score=8,
            violations=[],
            reasoning="Test decision",
            relevant_scope=["CLI"],
            suggestions=[],
            constraint_violations=[],
            confidence="high"
        )

        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
            track_alignment_decision(result)

        assert history_path.exists()

    def test_track_decision_appends_to_existing_history(self, tmp_path):
        """Test track_alignment_decision appends to existing history."""
        history_path = tmp_path / "alignment_history.jsonl"
        history_path.write_text('{"decision": "first"}\n')

        result = AlignmentGateResult(
            aligned=True,
            score=7,
            violations=[],
            reasoning="Second decision",
            relevant_scope=[],
            suggestions=[],
            constraint_violations=[],
            confidence="medium"
        )

        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
            track_alignment_decision(result)

        lines = history_path.read_text().strip().split('\n')
        assert len(lines) == 2
        assert "first" in lines[0]

    def test_track_decision_includes_timestamp(self, tmp_path):
        """Test tracked decision includes timestamp."""
        history_path = tmp_path / "alignment_history.jsonl"

        result = AlignmentGateResult(
            aligned=True,
            score=9,
            violations=[],
            reasoning="Test",
            relevant_scope=[],
            suggestions=[],
            constraint_violations=[],
            confidence="high"
        )

        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
            track_alignment_decision(result)

        content = json.loads(history_path.read_text())
        assert "timestamp" in content

    def test_track_decision_serializes_result_fields(self, tmp_path):
        """Test all AlignmentGateResult fields are serialized."""
        history_path = tmp_path / "alignment_history.jsonl"

        result = AlignmentGateResult(
            aligned=False,
            score=5,
            violations=["Issue 1", "Issue 2"],
            reasoning="Test reasoning",
            relevant_scope=["Scope 1"],
            suggestions=["Suggestion 1"],
            constraint_violations=["Violation 1"],
            confidence="low"
        )

        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
            track_alignment_decision(result)

        content = json.loads(history_path.read_text())
        assert content["aligned"] is False
        assert content["score"] == 5
        assert len(content["violations"]) == 2
        assert content["reasoning"] == "Test reasoning"


# ============================================================================
# get_alignment_stats() Tests
# ============================================================================


class TestGetAlignmentStats:
    """Test alignment statistics for meta-validation."""

    def test_stats_empty_history_returns_zeros(self, tmp_path):
        """Test get_alignment_stats with empty history returns zero stats."""
        history_path = tmp_path / "alignment_history.jsonl"
        history_path.write_text("")

        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
            stats = get_alignment_stats()

        assert stats["total_decisions"] == 0
        assert stats["approved_count"] == 0
        assert stats["rejected_count"] == 0

    def test_stats_calculates_approval_rate(self, tmp_path):
        """Test get_alignment_stats calculates approval rate correctly."""
        history_path = tmp_path / "alignment_history.jsonl"

        # 3 approved, 2 rejected = 60% approval rate
        decisions = [
            {"aligned": True, "score": 8},
            {"aligned": True, "score": 9},
            {"aligned": False, "score": 4},
            {"aligned": True, "score": 7},
            {"aligned": False, "score": 3},
        ]

        history_path.write_text('\n'.join(json.dumps(d) for d in decisions) + '\n')

        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
            stats = get_alignment_stats()

        assert stats["total_decisions"] == 5
        assert stats["approved_count"] == 3
        assert stats["rejected_count"] == 2
        assert stats["approval_rate"] == 0.6

    def test_stats_calculates_average_score(self, tmp_path):
        """Test get_alignment_stats calculates average score."""
        history_path = tmp_path / "alignment_history.jsonl"

        decisions = [
            {"aligned": True, "score": 8},
            {"aligned": True, "score": 10},
            {"aligned": False, "score": 2},
        ]

        history_path.write_text('\n'.join(json.dumps(d) for d in decisions) + '\n')

        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
            stats = get_alignment_stats()

        assert stats["average_score"] == (8 + 10 + 2) / 3

    def test_stats_tracks_constraint_violations(self, tmp_path):
        """Test get_alignment_stats tracks constraint violation count."""
        history_path = tmp_path / "alignment_history.jsonl"

        decisions = [
            {"aligned": True, "score": 8, "constraint_violations": []},
            {"aligned": False, "score": 7, "constraint_violations": ["Breaking change"]},
            {"aligned": True, "score": 9, "constraint_violations": []},
            {"aligned": False, "score": 8, "constraint_violations": ["Performance issue", "Security risk"]},
        ]

        history_path.write_text('\n'.join(json.dumps(d) for d in decisions) + '\n')

        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
            stats = get_alignment_stats()

        assert stats["constraint_violation_count"] == 2  # 2 decisions had violations

    def test_stats_nonexistent_history_returns_zeros(self):
        """Test get_alignment_stats with nonexistent history file returns zeros."""
        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', Path("/nonexistent/history.jsonl")):
            stats = get_alignment_stats()

        assert stats["total_decisions"] == 0
        assert stats["approval_rate"] == 0.0

    def test_stats_handles_malformed_jsonl(self, tmp_path):
        """Test get_alignment_stats handles malformed JSONL gracefully."""
        history_path = tmp_path / "alignment_history.jsonl"
        history_path.write_text('{"aligned": true}\nthis is not json\n{"aligned": false}\n')

        with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
            stats = get_alignment_stats()

        # Should skip malformed line and process valid ones
        assert stats["total_decisions"] == 2


# ============================================================================
# Integration Tests
# ============================================================================


class TestAlignmentGateIntegration:
    """Integration tests for complete alignment gate workflow."""

    def test_full_workflow_approved_feature(self, sample_project_md, tmp_path):
        """Test complete workflow for approved feature."""
        feature_desc = "Add new CLI command for git status"
        history_path = tmp_path / "alignment_history.jsonl"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 9,
                "violations": [],
                "reasoning": "Explicitly in SCOPE (CLI commands, Git automation)",
                "relevant_scope": ["CLI commands", "Git automation"],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "high"
            })

            with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
                result = validate_alignment_strict(feature_desc, sample_project_md)
                track_alignment_decision(result)
                stats = get_alignment_stats()

        assert result.aligned is True
        assert result.score == 9
        assert stats["total_decisions"] == 1
        assert stats["approved_count"] == 1

    def test_full_workflow_rejected_feature(self, sample_project_md, tmp_path):
        """Test complete workflow for rejected feature."""
        feature_desc = "Add cryptocurrency mining pool"
        history_path = tmp_path / "alignment_history.jsonl"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 1,
                "violations": ["Completely out of scope", "Not in GOALS"],
                "reasoning": "Cryptocurrency not mentioned anywhere in PROJECT.md",
                "relevant_scope": [],
                "suggestions": ["Reconsider project direction"],
                "constraint_violations": [],
                "confidence": "high"
            })

            with patch('alignment_gate.ALIGNMENT_HISTORY_PATH', history_path):
                result = validate_alignment_strict(feature_desc, sample_project_md)
                track_alignment_decision(result)
                stats = get_alignment_stats()

        assert result.aligned is False
        assert result.score < 7
        assert stats["total_decisions"] == 1
        assert stats["rejected_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])

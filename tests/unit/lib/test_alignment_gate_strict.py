#!/usr/bin/env python3
"""
Strict Alignment Gate Tests (TDD Red Phase).

Tests strict PROJECT.md alignment scenarios with real-world examples.
Focus on boundary cases and strict gatekeeper behavior.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test out-of-scope features are strictly blocked (score < 7)
- Test in-scope features pass with high confidence (score >= 7)
- Test ambiguous features require clarification (score 4-6)
- Test constraint violations block even high-scoring features
- Test "related to" vs "explicitly in" scope distinction
- Test prompt strictness vs genai_validate.py lenient prompts
- Test edge cases: vague descriptions, missing context

Coverage Target: 90%+

Date: 2026-01-19
Issue: #251 (Strict PROJECT.md Alignment Gate)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

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
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# Test fixtures
@pytest.fixture
def realistic_project_md(tmp_path):
    """Create realistic PROJECT.md based on autonomous-dev."""
    project_md = tmp_path / "PROJECT.md"
    content = """# autonomous-dev

## GOALS
- Build autonomous development tools for Claude Code
- Reduce manual intervention in SDLC workflows
- Improve code quality through automated validation
- Enable agent-based development pipelines

## SCOPE
- Agent-based workflows (8 core agents)
- CLI slash commands (/implement, /sync, etc.)
- Git automation (commit, push, PR creation)
- Testing infrastructure (pytest, TDD)
- Hook system (pre-commit, pre-push)
- Documentation automation

## CONSTRAINTS
- Must maintain backward compatibility with existing commands
- No breaking changes to plugin API
- Security-first design (sandboxing, permission validation)
- Performance: CLI commands must complete in <2 seconds
- Must work cross-platform (Linux, macOS, Windows)

## CURRENT_SPRINT
- Implement strict PROJECT.md alignment gate
- Add quality gates to batch processing
- Improve test coverage to 85%+
"""
    project_md.write_text(content)
    return project_md


# ============================================================================
# Out-of-Scope Features (Should be Blocked)
# ============================================================================


class TestOutOfScopeFeatures:
    """Test features completely out of scope are strictly blocked."""

    def test_blockchain_feature_blocked(self, realistic_project_md):
        """Test blockchain feature is blocked (not in SCOPE)."""
        feature_desc = "Add blockchain integration for decentralized code storage"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 1,
                "violations": ["Not in SCOPE", "Not in GOALS", "Unrelated to project"],
                "reasoning": "Blockchain/decentralized storage not mentioned in PROJECT.md",
                "relevant_scope": [],
                "suggestions": ["Reconsider if this aligns with autonomous development tools"],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert result.score < 7
        assert result.score <= 3  # Should be very low
        assert len(result.violations) >= 2

    def test_mobile_app_feature_blocked(self, realistic_project_md):
        """Test mobile app feature is blocked (not in SCOPE)."""
        feature_desc = "Create iOS and Android mobile apps for remote development"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 2,
                "violations": ["Mobile apps not in SCOPE", "No mention in GOALS"],
                "reasoning": "Project is CLI-focused, no mobile mentioned",
                "relevant_scope": [],
                "suggestions": ["Focus on CLI commands per SCOPE"],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert result.score < 7

    def test_database_migration_feature_blocked(self, realistic_project_md):
        """Test database migration feature is blocked (not in SCOPE)."""
        feature_desc = "Add PostgreSQL database with ORM for storing agent state"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 3,
                "violations": ["Database not in SCOPE", "Adds unnecessary complexity"],
                "reasoning": "No database mentioned in SCOPE, project uses file-based storage",
                "relevant_scope": [],
                "suggestions": ["Use existing file-based state management"],
                "constraint_violations": ["Adds complexity beyond project goals"],
                "confidence": "medium"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert result.score < 7
        assert len(result.constraint_violations) > 0 or len(result.violations) > 0

    def test_gui_dashboard_feature_blocked(self, realistic_project_md):
        """Test GUI dashboard feature is blocked (project is CLI-focused)."""
        feature_desc = "Build web dashboard with React for visualizing agent workflows"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 4,
                "violations": ["GUI/web not in SCOPE", "Diverges from CLI focus"],
                "reasoning": "SCOPE specifies CLI slash commands, not web interfaces",
                "relevant_scope": [],
                "suggestions": ["Keep focus on CLI commands"],
                "constraint_violations": [],
                "confidence": "medium"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert result.score < 7


# ============================================================================
# In-Scope Features (Should Pass)
# ============================================================================


class TestInScopeFeatures:
    """Test features explicitly in SCOPE pass validation."""

    def test_new_cli_command_passes(self, realistic_project_md):
        """Test new CLI command feature passes (explicitly in SCOPE)."""
        feature_desc = "Add new /audit command for validating project quality"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 9,
                "violations": [],
                "reasoning": "CLI slash commands explicitly in SCOPE section",
                "relevant_scope": ["CLI slash commands"],
                "suggestions": ["Consider adding tests", "Update documentation"],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is True
        assert result.score >= 7
        assert "CLI" in str(result.relevant_scope)

    def test_git_automation_feature_passes(self, realistic_project_md):
        """Test Git automation feature passes (explicitly in SCOPE)."""
        feature_desc = "Improve git commit message generation with AI analysis"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 9,
                "violations": [],
                "reasoning": "Git automation explicitly in SCOPE, AI aligns with GOALS",
                "relevant_scope": ["Git automation", "AI-based development"],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is True
        assert result.score >= 7

    def test_testing_infrastructure_feature_passes(self, realistic_project_md):
        """Test testing infrastructure feature passes (explicitly in SCOPE)."""
        feature_desc = "Add regression test tier system with auto-categorization"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 10,
                "violations": [],
                "reasoning": "Testing infrastructure explicitly in SCOPE",
                "relevant_scope": ["Testing infrastructure"],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is True
        assert result.score >= 7

    def test_agent_workflow_feature_passes(self, realistic_project_md):
        """Test agent workflow feature passes (explicitly in SCOPE)."""
        feature_desc = "Add new security-auditor agent for vulnerability scanning"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 9,
                "violations": [],
                "reasoning": "Agent-based workflows explicitly in SCOPE, security aligns with CONSTRAINTS",
                "relevant_scope": ["Agent-based workflows", "Security-first design"],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is True
        assert result.score >= 7


# ============================================================================
# Ambiguous Features (Require Clarification)
# ============================================================================


class TestAmbiguousFeatures:
    """Test ambiguous features get scores 4-6 requiring clarification."""

    def test_vague_performance_improvement(self, realistic_project_md):
        """Test vague 'improve performance' gets mid-range score."""
        feature_desc = "Improve performance"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 5,
                "violations": ["Too vague", "No specific scope identified"],
                "reasoning": "Performance mentioned in CONSTRAINTS but too vague",
                "relevant_scope": [],
                "suggestions": ["Specify which component", "Add target metrics", "Define scope"],
                "constraint_violations": [],
                "confidence": "low"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert 4 <= result.score <= 6
        assert len(result.suggestions) >= 2

    def test_improve_documentation_ambiguous(self, realistic_project_md):
        """Test vague 'improve documentation' gets mid-range score."""
        feature_desc = "Improve documentation quality"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 6,
                "violations": ["Not specific enough"],
                "reasoning": "Documentation automation in SCOPE but needs specifics",
                "relevant_scope": ["Documentation automation"],
                "suggestions": ["Specify which docs", "Define quality metrics"],
                "constraint_violations": [],
                "confidence": "medium"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert 4 <= result.score <= 6

    def test_refactor_code_without_context(self, realistic_project_md):
        """Test generic 'refactor code' without context is ambiguous."""
        feature_desc = "Refactor codebase for better maintainability"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 5,
                "violations": ["No specific component identified", "Too broad"],
                "reasoning": "Refactoring aligns with code quality GOAL but too vague",
                "relevant_scope": [],
                "suggestions": ["Identify specific modules", "Define refactoring goals"],
                "constraint_violations": [],
                "confidence": "low"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert 4 <= result.score <= 6


# ============================================================================
# Constraint Violation Tests
# ============================================================================


class TestConstraintViolations:
    """Test constraint violations block even high-scoring features."""

    def test_breaking_api_change_blocked(self, realistic_project_md):
        """Test breaking API change is blocked by CONSTRAINTS."""
        feature_desc = "Rewrite plugin API with breaking changes for cleaner design"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 8,  # Good scope match but...
                "violations": [],
                "reasoning": "Matches SCOPE (plugin API) but violates CONSTRAINTS",
                "relevant_scope": ["Plugin API"],
                "suggestions": ["Make changes backward compatible"],
                "constraint_violations": ["No breaking changes to plugin API"],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False  # Blocked by constraint
        assert result.score >= 7  # Score is high but...
        assert len(result.constraint_violations) > 0

    def test_slow_command_blocked_by_performance(self, realistic_project_md):
        """Test slow command violates performance constraint."""
        feature_desc = "Add /analyze command that runs 5-minute deep code analysis"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 7,
                "violations": [],
                "reasoning": "CLI command in SCOPE but violates performance CONSTRAINT",
                "relevant_scope": ["CLI slash commands"],
                "suggestions": ["Optimize to <2s", "Make async/background"],
                "constraint_violations": ["Performance: CLI commands must complete in <2 seconds"],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert len(result.constraint_violations) > 0
        assert "performance" in result.constraint_violations[0].lower() or "2" in result.constraint_violations[0]

    def test_windows_only_feature_blocked(self, realistic_project_md):
        """Test Windows-only feature violates cross-platform constraint."""
        feature_desc = "Add Windows-only PowerShell integration for git hooks"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 7,
                "violations": [],
                "reasoning": "Hooks in SCOPE but Windows-only violates cross-platform CONSTRAINT",
                "relevant_scope": ["Hook system"],
                "suggestions": ["Make cross-platform", "Support bash/zsh/PowerShell"],
                "constraint_violations": ["Must work cross-platform (Linux, macOS, Windows)"],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert len(result.constraint_violations) > 0


# ============================================================================
# "Related To" vs "Explicitly In" Scope Tests
# ============================================================================


class TestStrictScopeMatching:
    """Test strict scope matching (not just 'related to')."""

    def test_related_but_not_explicit_rejected(self, realistic_project_md):
        """Test feature related to but not explicitly in SCOPE is rejected."""
        # Mercurial is version control (related to Git) but not explicitly in SCOPE
        feature_desc = "Add Mercurial version control support alongside Git"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 4,
                "violations": ["Mercurial not explicitly in SCOPE", "Only Git mentioned"],
                "reasoning": "Related to version control but SCOPE only lists Git",
                "relevant_scope": [],
                "suggestions": ["Focus on Git automation per SCOPE"],
                "constraint_violations": [],
                "confidence": "medium"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert result.score < 7

    def test_similar_but_different_domain_rejected(self, realistic_project_md):
        """Test similar but different domain feature is rejected."""
        # Kubernetes is automation (related to Git automation) but different domain
        feature_desc = "Add Kubernetes deployment automation for containerized agents"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 3,
                "violations": ["Kubernetes not in SCOPE", "Different domain from Git automation"],
                "reasoning": "Automation mentioned but different domain",
                "relevant_scope": [],
                "suggestions": ["Stay focused on Git automation"],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert result.score < 7

    def test_explicit_scope_match_required(self, realistic_project_md):
        """Test explicit scope match is required, not just thematic similarity."""
        result = check_scope_membership(
            "Add SVN version control support",
            "- Git automation\n- Testing infrastructure"
        )

        # SVN is version control (similar to Git) but not explicitly listed
        assert result is False


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_one_word_description_ambiguous(self, realistic_project_md):
        """Test one-word description is too ambiguous."""
        feature_desc = "Testing"

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": False,
                "score": 4,
                "violations": ["Too vague", "No context"],
                "reasoning": "Testing in SCOPE but no specific feature described",
                "relevant_scope": [],
                "suggestions": ["Provide detailed description"],
                "constraint_violations": [],
                "confidence": "low"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is False
        assert result.score < 7

    def test_multi_paragraph_description_handled(self, realistic_project_md):
        """Test multi-paragraph feature description is handled correctly."""
        feature_desc = """
Add comprehensive test coverage analyzer.

This feature will:
- Analyze pytest test coverage across all modules
- Generate detailed coverage reports
- Identify untested code paths
- Integrate with CI/CD pipeline

Aligns with testing infrastructure in SCOPE.
"""

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 9,
                "violations": [],
                "reasoning": "Testing infrastructure explicitly in SCOPE, detailed description",
                "relevant_scope": ["Testing infrastructure"],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is True
        assert result.score >= 7

    def test_feature_with_code_snippets(self, realistic_project_md):
        """Test feature description with code snippets is handled."""
        feature_desc = """
Add /test command for running pytest:

```bash
/test --file tests/test_foo.py
```

This aligns with CLI commands and testing infrastructure.
"""

        with patch('alignment_gate.call_llm') as mock_llm:
            mock_llm.return_value = json.dumps({
                "aligned": True,
                "score": 8,
                "violations": [],
                "reasoning": "CLI commands and testing both in SCOPE",
                "relevant_scope": ["CLI slash commands", "Testing infrastructure"],
                "suggestions": [],
                "constraint_violations": [],
                "confidence": "high"
            })

            result = validate_alignment_strict(feature_desc, realistic_project_md)

        assert result.aligned is True
        assert result.score >= 7


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])

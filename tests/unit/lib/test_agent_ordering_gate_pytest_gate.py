"""
Tests for pytest-gate integration in agent_ordering_gate.py.

Issue #838: Pipeline step ordering enforcement — pytest gate + reviewer-before-security sequencing.
"""

import sys
from pathlib import Path

import pytest

# Add lib to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from agent_ordering_gate import (
    FIX_PIPELINE_AGENTS,
    FULL_PIPELINE_AGENTS,
    LIGHT_PIPELINE_AGENTS,
    MODE_DEPENDENT_PAIRS,
    STEP_ORDER,
    check_ordering_prerequisites,
    check_ordering_with_session_fallback,
)


def test_issue_1818_offline_reviewer_requires_explicit_verified_acknowledgment(monkeypatch):
    """Legacy skip/marker cannot satisfy the inactive trusted receipt seam."""
    monkeypatch.setenv("SKIP_PYTEST_GATE", "1")
    result = check_ordering_with_session_fallback(
        "reviewer",
        "offline-no-obligation",
        pipeline_mode="fix",
        pytest_scope={},
        pytest_provisioning={},
    )
    assert not result.passed


class TestPytestGateOrdering:
    """Tests for pytest-gate as a prerequisite for STEP 10 agents."""

    def test_reviewer_blocked_without_pytest_gate(self):
        """Reviewer requires pytest-gate in completed agents."""
        completed = {"planner", "implementer"}
        result = check_ordering_prerequisites(
            "reviewer", completed, validation_mode="sequential"
        )
        assert not result.passed
        assert "pytest-gate" in result.missing_agents

    def test_security_auditor_blocked_without_pytest_gate(self):
        """Security-auditor requires pytest-gate."""
        completed = {"planner", "implementer", "reviewer"}
        result = check_ordering_prerequisites(
            "security-auditor", completed, validation_mode="sequential"
        )
        assert not result.passed
        assert "pytest-gate" in result.missing_agents

    def test_doc_master_blocked_without_pytest_gate(self):
        """Doc-master requires pytest-gate."""
        completed = {"planner", "implementer"}
        result = check_ordering_prerequisites(
            "doc-master", completed, validation_mode="sequential"
        )
        assert not result.passed
        assert "pytest-gate" in result.missing_agents

    def test_reviewer_allowed_with_pytest_gate(self):
        """Reviewer allowed when pytest-gate and implementer are completed."""
        completed = {"planner", "implementer", "pytest-gate"}
        result = check_ordering_prerequisites(
            "reviewer", completed, validation_mode="sequential"
        )
        assert result.passed

    def test_security_auditor_allowed_with_all_prereqs(self):
        """Security-auditor allowed with implementer, pytest-gate, and reviewer."""
        completed = {"planner", "implementer", "pytest-gate", "reviewer"}
        result = check_ordering_prerequisites(
            "security-auditor", completed, validation_mode="sequential"
        )
        assert result.passed

    def test_security_auditor_requires_reviewer_completion_sequential_mode(self):
        """In sequential mode, security-auditor always requires reviewer completion."""
        completed = {"planner", "implementer", "pytest-gate"}
        result = check_ordering_prerequisites(
            "security-auditor", completed, validation_mode="sequential"
        )
        assert not result.passed
        assert "reviewer" in result.missing_agents

    def test_security_auditor_requires_reviewer_completion_parallel_mode(self):
        """Issue #838: reviewer->security-auditor is now always enforced (not mode-dependent).
        In parallel mode, security-auditor still requires reviewer completion."""
        completed = {"planner", "implementer", "pytest-gate"}
        result = check_ordering_prerequisites(
            "security-auditor", completed, validation_mode="parallel"
        )
        assert not result.passed
        assert "reviewer" in result.missing_agents

    def test_pytest_gate_in_step_order(self):
        """pytest-gate must be in STEP_ORDER with value between implementer and reviewer."""
        assert "pytest-gate" in STEP_ORDER
        assert STEP_ORDER["implementer"] < STEP_ORDER["pytest-gate"] < STEP_ORDER["reviewer"]

    def test_pytest_gate_in_full_pipeline_agents(self):
        """pytest-gate must be in FULL_PIPELINE_AGENTS."""
        assert "pytest-gate" in FULL_PIPELINE_AGENTS

    def test_pytest_gate_in_light_pipeline_agents(self):
        """pytest-gate must be in LIGHT_PIPELINE_AGENTS."""
        assert "pytest-gate" in LIGHT_PIPELINE_AGENTS

    def test_pytest_gate_in_fix_pipeline_agents(self):
        """pytest-gate must be in FIX_PIPELINE_AGENTS."""
        assert "pytest-gate" in FIX_PIPELINE_AGENTS

    def test_implementer_not_blocked_by_pytest_gate(self):
        """Implementer does NOT depend on pytest-gate (it runs before it)."""
        completed = {"planner", "plan-critic"}
        result = check_ordering_prerequisites(
            "implementer", completed, validation_mode="sequential"
        )
        assert result.passed

    def test_planner_not_blocked_by_pytest_gate(self):
        """Planner has no prerequisites, including pytest-gate."""
        completed = set()
        result = check_ordering_prerequisites(
            "planner", completed, validation_mode="sequential"
        )
        assert result.passed

    def test_mode_dependent_pairs_empty(self):
        """Issue #838: MODE_DEPENDENT_PAIRS should be empty — reviewer->security-auditor
        is now always enforced via SEQUENTIAL_REQUIRED."""
        assert len(MODE_DEPENDENT_PAIRS) == 0

#!/usr/bin/env python3
"""Regression tests for Issue #957: CIA (continuous-improvement-analyst) ordering gate.

In batch session 2026-04-25, Issue #948 had continuous-improvement-analyst
dispatched at 13:05:34 (UTC) BEFORE the implementer at 13:15:40 — a 10-minute
ordering violation. The root cause: continuous-improvement-analyst had no entry
in SEQUENTIAL_REQUIRED, so the agent_ordering_gate did not enforce that CIA must
come after implementer/reviewer/doc-master.

This fix adds the following ordering prerequisites:
    ("implementer", "continuous-improvement-analyst")
    ("reviewer", "continuous-improvement-analyst")
    ("doc-master", "continuous-improvement-analyst")

security-auditor is intentionally NOT a CIA prerequisite because it is conditional
(only runs in sequential-mode with security-sensitive files). Requiring it would
break --fix mode where security-auditor is skipped.

Issues: #957
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import pipeline_completion_state as pcs  # noqa: E402
from agent_ordering_gate import (  # noqa: E402
    CORE_PREREQUISITES,
    SEQUENTIAL_REQUIRED,
    STEP_ORDER,
    check_ordering_prerequisites,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove escape hatch env vars before each test."""
    monkeypatch.delenv("SKIP_AGENT_COMPLETENESS_GATE", raising=False)
    monkeypatch.delenv("PIPELINE_MODE", raising=False)
    monkeypatch.delenv("PIPELINE_ISSUE_NUMBER", raising=False)


@pytest.fixture
def session_id(tmp_path, monkeypatch):
    """Create a unique session and patch state file path to tmp."""
    sid = "test-regression-957"

    def _patched(s, *, run_id=None):
        import hashlib

        h = hashlib.sha256(s.encode()).hexdigest()[:8]
        return tmp_path / f"pipeline_agent_completions_{h}.json"

    monkeypatch.setattr(pcs, "_state_file_path", _patched)
    return sid


# ---------------------------------------------------------------------------
# Structural assertions: the new entries exist in SEQUENTIAL_REQUIRED
# ---------------------------------------------------------------------------


class TestStructuralOrderingEntries:
    """Verify the new SEQUENTIAL_REQUIRED entries are wired correctly."""

    def test_implementer_prereq_present(self) -> None:
        """SEQUENTIAL_REQUIRED must contain (implementer, CIA)."""
        assert ("implementer", "continuous-improvement-analyst") in SEQUENTIAL_REQUIRED, (
            "Issue #957: implementer must be a prerequisite for "
            "continuous-improvement-analyst"
        )

    def test_reviewer_prereq_present(self) -> None:
        """SEQUENTIAL_REQUIRED must contain (reviewer, CIA)."""
        assert ("reviewer", "continuous-improvement-analyst") in SEQUENTIAL_REQUIRED, (
            "Issue #957: reviewer must be a prerequisite for "
            "continuous-improvement-analyst"
        )

    def test_doc_master_prereq_present(self) -> None:
        """SEQUENTIAL_REQUIRED must contain (doc-master, CIA)."""
        assert ("doc-master", "continuous-improvement-analyst") in SEQUENTIAL_REQUIRED, (
            "Issue #957: doc-master must be a prerequisite for "
            "continuous-improvement-analyst"
        )

    def test_security_auditor_NOT_a_cia_prereq(self) -> None:
        """security-auditor MUST NOT be a CIA prerequisite (conditional agent).

        In --fix mode, security-auditor is skipped entirely. Adding it as a
        prerequisite would block CIA from ever running in fix mode.
        """
        assert (
            "security-auditor",
            "continuous-improvement-analyst",
        ) not in SEQUENTIAL_REQUIRED, (
            "Issue #957: security-auditor must NOT be a CIA prerequisite because "
            "it is conditional (sequential-mode + security-sensitive files only). "
            "Adding it would break --fix mode."
        )

    def test_cia_registered_in_step_order(self) -> None:
        """CIA must be registered in STEP_ORDER so it is not treated as 'unknown'.

        check_ordering_prerequisites returns 'pass' for unknown agents — if CIA
        is not in STEP_ORDER, the gate is bypassed even when prerequisites are
        missing.
        """
        assert "continuous-improvement-analyst" in STEP_ORDER, (
            "Issue #957: CIA must be in STEP_ORDER so the ordering gate enforces "
            "its prerequisites instead of treating it as an unknown agent."
        )

    def test_cia_step_order_after_step6_agents(self) -> None:
        """CIA's step index must be greater than all step-6 agents."""
        cia_step = STEP_ORDER["continuous-improvement-analyst"]
        for prereq in ("implementer", "reviewer", "doc-master", "security-auditor"):
            assert cia_step > STEP_ORDER[prereq], (
                f"CIA step ({cia_step}) must be > {prereq} step "
                f"({STEP_ORDER[prereq]}) to enforce 'CIA runs last'."
            )

    def test_core_prerequisites_map_includes_cia_prereqs(self) -> None:
        """CORE_PREREQUISITES must derive the three new CIA prerequisites."""
        cia_prereqs = CORE_PREREQUISITES.get("continuous-improvement-analyst", set())
        assert cia_prereqs >= {"implementer", "reviewer", "doc-master"}, (
            f"CIA prerequisites in CORE_PREREQUISITES were {sorted(cia_prereqs)}; "
            f"expected at minimum implementer, reviewer, doc-master."
        )


# ---------------------------------------------------------------------------
# Behavioral assertions: check_ordering_prerequisites() blocks / allows correctly
# ---------------------------------------------------------------------------


class TestCIAOrderingBehavior:
    """Verify check_ordering_prerequisites enforces CIA's prerequisites."""

    def test_cia_blocked_when_implementer_missing(self) -> None:
        """CIA must be blocked when implementer has not completed.

        This is the exact bug Issue #957 reported: CIA dispatched 10 minutes
        BEFORE implementer in batch session 2026-04-25.
        """
        completed = {"planner", "plan-critic", "pytest-gate", "reviewer", "doc-master"}
        result = check_ordering_prerequisites(
            "continuous-improvement-analyst",
            completed,
            validation_mode="sequential",
            pipeline_mode="full",
        )
        assert not result.passed, (
            "Issue #957: CIA must be blocked when implementer has not completed."
        )
        assert "implementer" in result.missing_agents, (
            f"Expected 'implementer' in missing_agents, got {result.missing_agents}"
        )

    def test_cia_blocked_when_reviewer_missing(self) -> None:
        """CIA must be blocked when reviewer has not completed."""
        completed = {
            "planner",
            "plan-critic",
            "implementer",
            "pytest-gate",
            "doc-master",
        }
        result = check_ordering_prerequisites(
            "continuous-improvement-analyst",
            completed,
            validation_mode="sequential",
            pipeline_mode="full",
        )
        assert not result.passed, (
            "Issue #957: CIA must be blocked when reviewer has not completed."
        )
        assert "reviewer" in result.missing_agents

    def test_cia_blocked_when_doc_master_missing(self) -> None:
        """CIA must be blocked when doc-master has not completed."""
        completed = {
            "planner",
            "plan-critic",
            "implementer",
            "pytest-gate",
            "reviewer",
            "security-auditor",
        }
        result = check_ordering_prerequisites(
            "continuous-improvement-analyst",
            completed,
            validation_mode="sequential",
            pipeline_mode="full",
        )
        assert not result.passed, (
            "Issue #957: CIA must be blocked when doc-master has not completed."
        )
        assert "doc-master" in result.missing_agents

    def test_cia_blocked_when_all_three_missing(self) -> None:
        """CIA blocked when all 3 new prerequisites are missing — error names them."""
        completed = {"planner", "plan-critic"}
        result = check_ordering_prerequisites(
            "continuous-improvement-analyst",
            completed,
            validation_mode="sequential",
            pipeline_mode="full",
        )
        assert not result.passed
        for required in ("implementer", "reviewer", "doc-master"):
            assert required in result.missing_agents, (
                f"Expected {required!r} in missing_agents, got "
                f"{result.missing_agents}"
            )

    def test_cia_allowed_when_all_prereqs_complete_full_mode(self) -> None:
        """CIA must pass when implementer, reviewer, doc-master all completed."""
        completed = {
            "researcher-local",
            "researcher",
            "planner",
            "plan-critic",
            "implementer",
            "pytest-gate",
            "reviewer",
            "security-auditor",
            "doc-master",
        }
        result = check_ordering_prerequisites(
            "continuous-improvement-analyst",
            completed,
            validation_mode="sequential",
            pipeline_mode="full",
        )
        assert result.passed, (
            f"CIA should pass when all prereqs complete; got: {result.reason}"
        )
        assert result.missing_agents == []

    def test_cia_allowed_in_fix_mode_without_security_auditor(self) -> None:
        """In --fix mode, CIA must run even though security-auditor is skipped.

        This validates the deliberate exclusion of security-auditor from CIA's
        prerequisites. In --fix mode the agent set is
        {implementer, pytest-gate, reviewer, doc-master, CIA}, so security-auditor
        is intentionally absent.
        """
        completed = {"implementer", "pytest-gate", "reviewer", "doc-master"}
        result = check_ordering_prerequisites(
            "continuous-improvement-analyst",
            completed,
            validation_mode="sequential",
            pipeline_mode="fix",
        )
        assert result.passed, (
            "Issue #957: CIA must run in --fix mode without security-auditor. "
            f"Got: {result.reason}"
        )

    def test_pre_existing_pairs_still_enforced(self) -> None:
        """Pre-existing SEQUENTIAL_REQUIRED entries must remain functional.

        Smoke check that adding the 3 new entries did not break any of the
        prior pairs (planner->implementer, implementer->reviewer, etc.).
        """
        # reviewer with no implementer completed → blocked (existing rule)
        result = check_ordering_prerequisites(
            "reviewer",
            {"planner", "pytest-gate"},
            validation_mode="sequential",
            pipeline_mode="full",
        )
        assert not result.passed
        assert "implementer" in result.missing_agents

        # security-auditor with no reviewer completed → blocked (existing rule)
        result = check_ordering_prerequisites(
            "security-auditor",
            {"implementer", "pytest-gate"},
            validation_mode="sequential",
            pipeline_mode="full",
        )
        assert not result.passed
        assert "reviewer" in result.missing_agents

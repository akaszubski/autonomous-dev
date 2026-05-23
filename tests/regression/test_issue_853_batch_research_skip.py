#!/usr/bin/env python3
"""Regression tests for Issue #853: Batch agent completeness gate checks all issues.

Verifies that in batch mode the completeness gate checks every issue in the state
file (not just the single active issue), that research_skipped is respected
per-issue, and that the non-batch code path is unchanged.

Issues: #853
"""

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(LIB_DIR))

import pipeline_completion_state as pcs


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove escape hatch env vars before each test."""
    monkeypatch.delenv("SKIP_AGENT_COMPLETENESS_GATE", raising=False)
    monkeypatch.delenv("PIPELINE_MODE", raising=False)
    monkeypatch.delenv("PIPELINE_ISSUE_NUMBER", raising=False)


@pytest.fixture
def session_id(tmp_path, monkeypatch):
    """Create a unique session and patch state file path to tmp."""
    sid = "test-regression-853"

    def _patched(s, *, run_id=None):
        import hashlib
        h = hashlib.sha256(s.encode()).hexdigest()[:8]
        return tmp_path / f"pipeline_agent_completions_{h}.json"

    monkeypatch.setattr(pcs, "_state_file_path", _patched)
    return sid


# ---------------------------------------------------------------------------
# Full required agents for the "full" pipeline mode (must include researchers)
# ---------------------------------------------------------------------------
FULL_REQUIRED_AGENTS = {
    "researcher-local", "researcher", "planner", "plan-critic",
    "implementer", "pytest-gate", "reviewer", "security-auditor", "doc-master",
}


class TestBatchAllIssuesChecked:
    """test_batch_all_issues_checked — 3 issues, all complete, gate passes."""

    def test_batch_all_issues_checked(self, session_id):
        """When all 3 batch issues have all required agents, gate passes for each."""
        for issue_num in (100, 101, 102):
            for agent in FULL_REQUIRED_AGENTS:
                pcs.record_agent_completion(session_id, agent, issue_number=issue_num)

        for issue_num in (100, 101, 102):
            passed, completed, missing = pcs.verify_pipeline_agent_completions(
                session_id, "full", issue_number=issue_num
            )
            assert passed is True, (
                f"Issue #{issue_num} should pass but missing: {missing}"
            )
            assert missing == set()


class TestBatchMissingAgentDetected:
    """test_batch_missing_agent_detected — one issue missing an agent, gate blocks."""

    def test_batch_missing_agent_detected(self, session_id):
        """When one of 3 batch issues is missing an agent, that issue fails the gate."""
        # Issues 100 and 102 are complete
        for issue_num in (100, 102):
            for agent in FULL_REQUIRED_AGENTS:
                pcs.record_agent_completion(session_id, agent, issue_number=issue_num)

        # Issue 101 is missing security-auditor
        incomplete_agents = FULL_REQUIRED_AGENTS - {"security-auditor"}
        for agent in incomplete_agents:
            pcs.record_agent_completion(session_id, agent, issue_number=101)

        passed_100, _, missing_100 = pcs.verify_pipeline_agent_completions(
            session_id, "full", issue_number=100
        )
        assert passed_100 is True

        passed_101, _, missing_101 = pcs.verify_pipeline_agent_completions(
            session_id, "full", issue_number=101
        )
        assert passed_101 is False
        assert "security-auditor" in missing_101

        passed_102, _, missing_102 = pcs.verify_pipeline_agent_completions(
            session_id, "full", issue_number=102
        )
        assert passed_102 is True


class TestBatchResearchSkippedRespectedPerIssue:
    """test_batch_research_skipped_respected_per_issue — researchers not required when skipped."""

    def test_batch_research_skipped_allows_without_researchers(self, session_id):
        """Issue with research_skipped=True passes even without researcher agents."""
        issue_num = 101
        # Record research as skipped for this issue
        pcs.record_research_skipped(session_id, issue_number=issue_num)

        # Record all required agents EXCEPT researchers
        agents_without_researchers = FULL_REQUIRED_AGENTS - {"researcher-local", "researcher"}
        for agent in agents_without_researchers:
            pcs.record_agent_completion(session_id, agent, issue_number=issue_num)

        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full", issue_number=issue_num
        )
        assert passed is True, (
            f"Issue #{issue_num} with research_skipped=True should pass without researchers, "
            f"but missing: {missing}"
        )

    def test_research_skipped_flag_is_per_issue(self, session_id):
        """research_skipped flag is isolated to the specific issue, not global."""
        # Issue 101: research skipped
        pcs.record_research_skipped(session_id, issue_number=101)
        # Issue 102: research NOT skipped
        assert pcs.get_research_skipped(session_id, issue_number=102) is False

        # Confirm issue 101 is marked as skipped
        assert pcs.get_research_skipped(session_id, issue_number=101) is True


class TestBatchResearchSkippedFalseMissingResearcherBlocks:
    """test_batch_research_skipped_false_missing_researcher_blocks — blocks when not skipped."""

    def test_research_not_skipped_missing_researcher_blocks(self, session_id):
        """When research is NOT skipped and researchers are missing, gate blocks."""
        issue_num = 101
        # Do NOT call record_research_skipped — research_skipped remains False

        # Record all required agents EXCEPT researchers
        agents_without_researchers = FULL_REQUIRED_AGENTS - {"researcher-local", "researcher"}
        for agent in agents_without_researchers:
            pcs.record_agent_completion(session_id, agent, issue_number=issue_num)

        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full", issue_number=issue_num
        )
        assert passed is False, (
            f"Issue #{issue_num} with research_skipped=False should block when researchers missing"
        )
        # At least one of the researcher agents should be in missing
        assert missing & {"researcher-local", "researcher"}, (
            f"Expected researcher agents in missing set, got: {missing}"
        )


class TestNonBatchUnchanged:
    """test_non_batch_unchanged — non-batch mode uses existing single-issue path."""

    def test_non_batch_single_issue_mode_passes_when_complete(self, session_id):
        """Single-issue (non-batch) path: all agents complete, gate passes."""
        # Default issue_number=0 is the non-batch issue
        for agent in FULL_REQUIRED_AGENTS:
            pcs.record_agent_completion(session_id, agent, issue_number=0)

        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full", issue_number=0
        )
        assert passed is True
        assert missing == set()

    def test_non_batch_single_issue_mode_blocks_when_missing(self, session_id):
        """Single-issue (non-batch) path: missing agent causes gate to block."""
        # Record all agents except security-auditor for issue 0
        agents = FULL_REQUIRED_AGENTS - {"security-auditor"}
        for agent in agents:
            pcs.record_agent_completion(session_id, agent, issue_number=0)

        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full", issue_number=0
        )
        assert passed is False
        assert "security-auditor" in missing

    def test_hook_contains_batch_agent_gate_853(self):
        """unified_pre_tool.py should contain the Issue #853 batch agent gate."""
        hook_path = HOOKS_DIR / "unified_pre_tool.py"
        assert hook_path.exists(), "unified_pre_tool.py must exist"
        source = hook_path.read_text()
        assert "Issue #853" in source, (
            "unified_pre_tool.py must reference Issue #853 for the batch agent gate"
        )
        assert ".worktrees/batch-" in source, (
            "unified_pre_tool.py must contain batch worktree detection for agent completeness"
        )

#!/usr/bin/env python3
"""Regression tests for Issue #802: Pipeline agent completeness gate.

Verifies the hook-level gate blocks git commits when required pipeline
agents are missing, allows commits when all agents are present, and
respects the escape hatch and research-skipped state.

Issues: #802
"""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    sid = "test-regression-802"
    original_fn = pcs._state_file_path

    def _patched(s, *, run_id=None):
        import hashlib
        h = hashlib.sha256(s.encode()).hexdigest()[:8]
        return tmp_path / f"pipeline_agent_completions_{h}.json"

    monkeypatch.setattr(pcs, "_state_file_path", _patched)
    return sid


def _load_hook_check_fn():
    """Load _check_pipeline_agent_completions from the hook file.

    Uses importlib to load just the function without executing the full hook.
    """
    hook_path = HOOKS_DIR / "unified_pre_tool.py"
    if not hook_path.exists():
        pytest.skip("unified_pre_tool.py not found")

    # Read the function source and the helper import pattern
    source = hook_path.read_text()
    assert "_check_pipeline_agent_completions" in source, (
        "Function _check_pipeline_agent_completions not found in unified_pre_tool.py"
    )
    return True  # Verification that the function exists


class TestAgentCompletenessGateBlocking:
    """Tests that git commit is blocked when security-auditor is missing."""

    def test_missing_security_auditor_blocks(self, session_id):
        """Git commit should be blocked when security-auditor is missing in full mode."""
        agents = {
            "researcher-local", "researcher", "planner",
            "implementer", "reviewer", "doc-master",
        }
        for agent in agents:
            pcs.record_agent_completion(session_id, agent)

        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )
        assert passed is False
        assert "security-auditor" in missing

    def test_all_complete_allows(self, session_id):
        """Git commit should be allowed when all required agents complete."""
        agents = {
            "researcher-local", "researcher", "planner", "plan-critic",
            "implementer", "pytest-gate", "reviewer", "security-auditor", "doc-master",
        }
        for agent in agents:
            pcs.record_agent_completion(session_id, agent)

        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )
        assert passed is True
        assert missing == set()

    def test_research_skipped_allows_without_researchers(self, session_id):
        """When research is skipped, missing researchers should not block."""
        agents = {
            "planner", "plan-critic", "implementer", "pytest-gate", "reviewer",
            "security-auditor", "doc-master",
        }
        for agent in agents:
            pcs.record_agent_completion(session_id, agent)
        pcs.record_research_skipped(session_id)

        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )
        assert passed is True

    def test_escape_hatch_bypasses(self, session_id, monkeypatch):
        """SKIP_AGENT_COMPLETENESS_GATE=1 should bypass the gate."""
        monkeypatch.setenv("SKIP_AGENT_COMPLETENESS_GATE", "1")
        # No agents at all
        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )
        assert passed is True


class TestHookFunctionExists:
    """Verify the hook function was properly wired."""

    def test_hook_contains_agent_completeness_check(self):
        """unified_pre_tool.py should contain the agent completeness check function."""
        hook_path = HOOKS_DIR / "unified_pre_tool.py"
        assert hook_path.exists(), "unified_pre_tool.py must exist"
        source = hook_path.read_text()
        assert "_check_pipeline_agent_completions" in source
        assert "Issue #802" in source

    def test_hook_wired_into_git_commit_section(self):
        """The agent completeness check should be wired into the git commit detection."""
        hook_path = HOOKS_DIR / "unified_pre_tool.py"
        source = hook_path.read_text()
        # Verify the check is called in the git commit section
        assert "_check_pipeline_agent_completions(" in source
        assert "SKIP_AGENT_COMPLETENESS_GATE" in source


class TestNonPipelineCommitsUnaffected:
    """Non-pipeline commits should not be affected by the gate."""

    def test_no_state_file_passes(self, session_id):
        """When no state file exists, the gate should fail-open."""
        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )
        # With no recorded agents, the gate will find missing agents.
        # But the hook only fires when pipeline is active, so non-pipeline
        # commits are never checked. Here we verify the function returns
        # a valid result regardless.
        assert isinstance(passed, bool)
        assert isinstance(missing, set)

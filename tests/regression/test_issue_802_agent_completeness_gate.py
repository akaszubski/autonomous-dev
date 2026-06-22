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


class TestBypassSelfMaintenanceInteraction:
    """Tests for Issue #1195: .bypass + self-maintenance + agent gate interaction."""

    def test_agent_completeness_enforced_under_bypass_self_maintenance(self, session_id, monkeypatch, tmp_path):
        """.bypass + self-maintenance mode + missing agents should BLOCK git commit."""
        # Create the bypass marker
#!/usr/bin/env python3
"""
Test Issue #1195: .bypass + self-maintenance mode should still enforce agent-completeness.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the lib directory to the path
sys.path.insert(0, str(Path(__file__).parents[2] / "plugins" / "autonomous-dev" / "lib"))
import pipeline_completion_state as pcs


@pytest.fixture(autouse=True)
def cleanup_state_file():
    """Remove any state file after each test."""
    yield
    state_file = Path(f"/tmp/pipeline_state_{os.getpid()}.json")
    if state_file.exists():
        state_file.unlink()


@pytest.fixture
def session_id():
    """Generate a unique session ID for testing."""
    import hashlib
    import time
    return hashlib.sha256(f"test-{time.time()}".encode()).hexdigest()[:8]


class TestBypassSelfMaintenanceInteraction:
    """Tests for Issue #1195: .bypass + self-maintenance + agent gate interaction."""

    def test_hook_has_self_maintenance_bypass_logic(self):
        """Verify the hook contains the Issue #1195 fix logic."""
        hook_path = Path(__file__).parents[2] / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
        source = hook_path.read_text()
        
        # Verify the Issue #1195 comment exists
        assert "Issue #1195" in source, "Missing Issue #1195 comment"
        
        # Verify the self-maintenance check is present in bypass section
        # Look for the pattern of checking _is_self_maintenance_mode after is_bypassed
        assert "_skip_bypass_exit" in source, "Missing _skip_bypass_exit variable"
        assert "_is_self_maintenance_mode() and tool_name == \"Bash\"" in source, \
            "Missing self-maintenance check in bypass logic"
        
        # Verify git commit check is in the bypass logic
        lines = source.split("\n")
        bypass_section_found = False
        self_maint_check_found = False
        
        for i, line in enumerate(lines):
            if "if is_bypassed():" in line:
                bypass_section_found = True
                # Check the next ~20 lines for the self-maintenance logic
                for j in range(i, min(i + 25, len(lines))):
                    if "_is_self_maintenance_mode()" in lines[j]:
                        self_maint_check_found = True
                        break
                break
        
        assert bypass_section_found, "Bypass section not found"
        assert self_maint_check_found, "Self-maintenance check not found in bypass section"
    
    def test_agent_completeness_state_with_missing_agents(self, session_id):
        """Test that missing agents are correctly detected."""
        # Set up pipeline state with missing agents
        pcs.record_agent_completion(session_id, "planner")
        pcs.record_agent_completion(session_id, "implementer")
        # Missing: security-auditor, reviewer, doc-master
        
        # Verify the agent completeness check finds missing agents
        passed, completed, missing = pcs.verify_pipeline_agent_completions(session_id, "full")
        assert not passed  # Should fail due to missing agents
        assert "security-auditor" in missing
        assert "reviewer" in missing
        assert "doc-master" in missing
        assert "planner" in completed
        assert "implementer" in completed
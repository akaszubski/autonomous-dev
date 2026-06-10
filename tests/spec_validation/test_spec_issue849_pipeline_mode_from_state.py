"""Spec validation tests for Issue #849: Pipeline mode read from state file.

Bug: The agent completeness gate in unified_pre_tool.py defaulted pipeline mode
to "full" instead of reading it from the pipeline state file, blocking git commits
during --fix and --light pipeline modes.

Acceptance criteria:
1. Completeness gate reads pipeline mode from state file when PIPELINE_MODE env var not set
2. In --fix mode, only fix-mode agents required (implementer, pytest-gate, reviewer,
   doc-master, continuous-improvement-analyst)
3. In --light mode, only light-mode agents required
4. Gate still works correctly in full mode
5. Existing tests pass with pytest-gate included in required agent sets
6. Regression test verifies the state-file-reading behavior
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove pipeline env vars before each test."""
    monkeypatch.delenv("PIPELINE_MODE", raising=False)
    monkeypatch.delenv("PIPELINE_ISSUE_NUMBER", raising=False)
    monkeypatch.delenv("SKIP_AGENT_COMPLETENESS_GATE", raising=False)


@pytest.fixture
def session_id(tmp_path, monkeypatch):
    """Create a unique session with state file path redirected to tmp."""
    import pipeline_completion_state as pcs

    sid = f"spec849-{time.time_ns()}"

    def _patched(s, *, run_id=None):
        import hashlib

        h = hashlib.sha256(s.encode()).hexdigest()[:8]
        return tmp_path / f"pipeline_agent_completions_{h}.json"

    monkeypatch.setattr(pcs, "_state_file_path", _patched)
    return sid


# ---------------------------------------------------------------------------
# Criterion 1: Completeness gate reads pipeline mode from state file
# when PIPELINE_MODE env var is not set
# ---------------------------------------------------------------------------


def test_spec_issue849_1_hook_reads_mode_from_state_file():
    """unified_pre_tool.py resolves pipeline mode via
    ``_get_pipeline_mode_from_state()``, which itself honors
    ``PIPELINE_MODE``.

    History:
      - #849 introduced the `env or helper` pattern at call sites.
      - #1173 moved the env-var read INSIDE the helper.
      - #1177 removed the now-dead outer short-circuit at both call sites.

    Post-#1177 the spec is: (a) the hook calls the helper, and (b) the
    PIPELINE_MODE env var read still exists somewhere in the file so the
    override path is preserved.
    """
    hook_path = (
        REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
    )
    source = hook_path.read_text()

    assert "_get_pipeline_mode_from_state()" in source, (
        "Hook must call _get_pipeline_mode_from_state() to resolve "
        "pipeline mode (#849)."
    )

    assert ('os.getenv("PIPELINE_MODE"' in source
            or 'os.environ.get("PIPELINE_MODE"' in source), (
        "PIPELINE_MODE env-var read disappeared entirely — #1173 moved "
        "it inside the helper; removing it removes the #849 override."
    )


def test_spec_issue849_1b_no_hardcoded_full_default_in_completions_check():
    """The bug pattern 'os.environ.get("PIPELINE_MODE", "full")' must not
    appear in _check_pipeline_agent_completions."""
    hook_path = (
        REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
    )
    source = hook_path.read_text()

    fn_start = source.find("def _check_pipeline_agent_completions")
    assert fn_start != -1, "_check_pipeline_agent_completions function must exist"

    fn_end = source.find("\ndef ", fn_start + 10)
    if fn_end == -1:
        fn_end = len(source)
    fn_body = source[fn_start:fn_end]

    assert 'os.environ.get("PIPELINE_MODE", "full")' not in fn_body, (
        "Bug pattern found: PIPELINE_MODE must not default to 'full' directly"
    )


# ---------------------------------------------------------------------------
# Criterion 2: In --fix mode, only fix-mode agents are required
# ---------------------------------------------------------------------------


def test_spec_issue849_2_fix_mode_requires_only_fix_agents(session_id):
    """With pipeline mode 'fix', only fix-mode agents should be required:
    implementer, pytest-gate, reviewer, doc-master, continuous-improvement-analyst."""
    from pipeline_completion_state import (
        record_agent_completion,
        verify_pipeline_agent_completions,
    )

    fix_agents = {
        "implementer",
        "pytest-gate",
        "reviewer",
        "doc-master",
        "continuous-improvement-analyst",
    }

    for agent in fix_agents:
        record_agent_completion(session_id, agent, issue_number=0, success=True)

    passed, completed, missing = verify_pipeline_agent_completions(
        session_id, "fix", issue_number=0
    )

    assert passed is True, f"Fix-mode agents should satisfy fix-mode check. Missing: {missing}"
    assert missing == set()


def test_spec_issue849_2b_fix_mode_does_not_require_researchers(session_id):
    """Fix mode should NOT require researcher-local or researcher."""
    from pipeline_completion_state import (
        record_agent_completion,
        verify_pipeline_agent_completions,
    )

    fix_agents = {
        "implementer",
        "pytest-gate",
        "reviewer",
        "doc-master",
        "continuous-improvement-analyst",
    }
    for agent in fix_agents:
        record_agent_completion(session_id, agent, issue_number=0, success=True)

    passed, _, missing = verify_pipeline_agent_completions(
        session_id, "fix", issue_number=0
    )

    assert passed is True
    assert "researcher-local" not in missing
    assert "researcher" not in missing
    assert "security-auditor" not in missing
    assert "planner" not in missing


def test_spec_issue849_2c_fix_agents_fail_full_mode_check(session_id):
    """Fix-mode agents alone should NOT satisfy full-mode requirements."""
    from pipeline_completion_state import (
        record_agent_completion,
        verify_pipeline_agent_completions,
    )

    fix_agents = {
        "implementer",
        "pytest-gate",
        "reviewer",
        "doc-master",
        "continuous-improvement-analyst",
    }
    for agent in fix_agents:
        record_agent_completion(session_id, agent, issue_number=0, success=True)

    passed, _, missing = verify_pipeline_agent_completions(
        session_id, "full", issue_number=0
    )

    assert passed is False, "Fix-mode agents should NOT pass full-mode check"
    assert len(missing) > 0


# ---------------------------------------------------------------------------
# Criterion 3: In --light mode, only light-mode agents are required
# ---------------------------------------------------------------------------


def test_spec_issue849_3_light_mode_requires_only_light_agents(session_id):
    """With pipeline mode 'light', only light-mode agents should be required."""
    from pipeline_completion_state import (
        record_agent_completion,
        verify_pipeline_agent_completions,
    )

    light_agents = {
        "planner",
        "implementer",
        "pytest-gate",
        "doc-master",
        "continuous-improvement-analyst",
    }

    for agent in light_agents:
        record_agent_completion(session_id, agent, issue_number=0, success=True)

    passed, completed, missing = verify_pipeline_agent_completions(
        session_id, "light", issue_number=0
    )

    assert passed is True, f"Light-mode agents should satisfy light-mode check. Missing: {missing}"
    assert missing == set()


def test_spec_issue849_3b_light_mode_does_not_require_security_auditor(session_id):
    """Light mode should NOT require security-auditor or researchers."""
    from pipeline_completion_state import (
        record_agent_completion,
        verify_pipeline_agent_completions,
    )

    light_agents = {
        "planner",
        "implementer",
        "pytest-gate",
        "doc-master",
        "continuous-improvement-analyst",
    }
    for agent in light_agents:
        record_agent_completion(session_id, agent, issue_number=0, success=True)

    passed, _, missing = verify_pipeline_agent_completions(
        session_id, "light", issue_number=0
    )

    assert passed is True
    assert "security-auditor" not in missing
    assert "researcher-local" not in missing
    assert "researcher" not in missing


# ---------------------------------------------------------------------------
# Criterion 4: Gate still works correctly in full mode
# ---------------------------------------------------------------------------


def test_spec_issue849_4_full_mode_requires_all_agents(session_id):
    """Full mode requires all agents including researchers and security-auditor."""
    from pipeline_completion_state import (
        record_agent_completion,
        verify_pipeline_agent_completions,
    )

    full_agents = {
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
    for agent in full_agents:
        record_agent_completion(session_id, agent, issue_number=0, success=True)

    passed, completed, missing = verify_pipeline_agent_completions(
        session_id, "full", issue_number=0
    )

    assert passed is True, f"Full agents should satisfy full-mode check. Missing: {missing}"
    assert missing == set()


def test_spec_issue849_4b_full_mode_blocks_when_agents_missing(session_id):
    """Full mode blocks when required agents are missing."""
    from pipeline_completion_state import (
        record_agent_completion,
        verify_pipeline_agent_completions,
    )

    # Only record a subset
    for agent in ["implementer", "reviewer"]:
        record_agent_completion(session_id, agent, issue_number=0, success=True)

    passed, _, missing = verify_pipeline_agent_completions(
        session_id, "full", issue_number=0
    )

    assert passed is False
    assert len(missing) > 0


# ---------------------------------------------------------------------------
# Criterion 5: Existing tests pass with pytest-gate in required agent sets
# ---------------------------------------------------------------------------


def test_spec_issue849_5_existing_unit_tests_pass():
    """Unit tests for agent completeness pass (includes pytest-gate)."""
    unit_test_file = (
        REPO_ROOT
        / "tests"
        / "unit"
        / "lib"
        / "test_pipeline_completion_state_agent_completeness.py"
    )
    assert unit_test_file.exists(), "Unit test file must exist"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(unit_test_file), "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Unit tests failed (exit code {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_spec_issue849_5b_existing_regression_tests_pass():
    """Regression tests for issue #802 agent completeness gate pass."""
    regression_test_file = (
        REPO_ROOT
        / "tests"
        / "regression"
        / "test_issue_802_agent_completeness_gate.py"
    )
    assert regression_test_file.exists(), "Regression test file must exist"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(regression_test_file), "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Regression tests failed (exit code {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Criterion 6: Regression test verifies state-file-reading behavior
# ---------------------------------------------------------------------------


def test_spec_issue849_6_regression_test_exists():
    """A regression test file for issue #849 exists."""
    regression_test_file = (
        REPO_ROOT
        / "tests"
        / "regression"
        / "test_issue_849_pipeline_mode_from_state.py"
    )
    assert regression_test_file.exists(), (
        "Regression test file for issue #849 must exist"
    )


def test_spec_issue849_6b_regression_test_passes():
    """The issue #849 regression test passes."""
    regression_test_file = (
        REPO_ROOT
        / "tests"
        / "regression"
        / "test_issue_849_pipeline_mode_from_state.py"
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(regression_test_file), "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Issue #849 regression tests failed (exit code {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )

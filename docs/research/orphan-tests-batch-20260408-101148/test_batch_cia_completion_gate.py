"""Unit tests for verify_batch_cia_completions() in pipeline_completion_state.

Tests the batch CIA completion gate function that verifies all batch issues
have completed their continuous-improvement-analyst before allowing git commit.

Issue: #712
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "pipeline_completion_state",
    str(LIB_DIR / "pipeline_completion_state.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

verify_batch_cia_completions = _mod.verify_batch_cia_completions
_state_file_path = _mod._state_file_path
_write_state = _mod._write_state


def _make_state(session_id: str, completions: dict) -> None:
    """Helper to write a state file with given completions."""
    state = {
        "session_id": session_id,
        "created_at": "2026-04-08T10:00:00+00:00",
        "validation_mode": "sequential",
        "completions": completions,
    }
    _write_state(session_id, state)


class TestVerifyBatchCIACompletions:
    """Tests for verify_batch_cia_completions()."""

    def setup_method(self) -> None:
        """Generate a unique session ID for each test."""
        self.session_id = f"test-cia-gate-{id(self)}-{time.time()}"

    def teardown_method(self) -> None:
        """Clean up state files."""
        path = _state_file_path(self.session_id)
        if path.exists():
            path.unlink(missing_ok=True)

    def test_all_issues_have_cia_passes(self) -> None:
        """When all batch issues have CIA completion, gate passes."""
        _make_state(self.session_id, {
            "100": {"implementer": True, "continuous-improvement-analyst": True},
            "101": {"implementer": True, "continuous-improvement-analyst": True},
            "102": {"implementer": True, "continuous-improvement-analyst": True},
        })
        all_passed, with_cia, missing_cia = verify_batch_cia_completions(self.session_id)
        assert all_passed is True
        assert sorted(with_cia) == [100, 101, 102]
        assert missing_cia == []

    def test_last_issue_missing_cia_fails(self) -> None:
        """When the last issue is missing CIA, gate fails."""
        _make_state(self.session_id, {
            "100": {"implementer": True, "continuous-improvement-analyst": True},
            "101": {"implementer": True, "continuous-improvement-analyst": True},
            "102": {"implementer": True},  # Missing CIA
        })
        all_passed, with_cia, missing_cia = verify_batch_cia_completions(self.session_id)
        assert all_passed is False
        assert sorted(with_cia) == [100, 101]
        assert missing_cia == [102]

    def test_multiple_issues_missing_cia_fails(self) -> None:
        """When multiple issues miss CIA, all are reported."""
        _make_state(self.session_id, {
            "100": {"implementer": True, "continuous-improvement-analyst": True},
            "101": {"implementer": True},
            "102": {"implementer": True},
        })
        all_passed, with_cia, missing_cia = verify_batch_cia_completions(self.session_id)
        assert all_passed is False
        assert with_cia == [100]
        assert missing_cia == [101, 102]

    def test_no_state_file_passes_fail_open(self) -> None:
        """No state file should pass (fail-open)."""
        all_passed, with_cia, missing_cia = verify_batch_cia_completions("nonexistent-session-xyz")
        assert all_passed is True
        assert with_cia == []
        assert missing_cia == []

    def test_empty_completions_passes_fail_open(self) -> None:
        """Empty completions dict should pass (fail-open)."""
        _make_state(self.session_id, {})
        all_passed, with_cia, missing_cia = verify_batch_cia_completions(self.session_id)
        assert all_passed is True

    def test_only_zero_key_passes(self) -> None:
        """Non-batch session with only '0' key should pass."""
        _make_state(self.session_id, {
            "0": {"implementer": True, "continuous-improvement-analyst": True},
        })
        all_passed, with_cia, missing_cia = verify_batch_cia_completions(self.session_id)
        assert all_passed is True
        assert with_cia == []
        assert missing_cia == []

    def test_cia_false_treated_as_missing(self) -> None:
        """CIA recorded as False should count as missing."""
        _make_state(self.session_id, {
            "100": {"implementer": True, "continuous-improvement-analyst": False},
        })
        all_passed, with_cia, missing_cia = verify_batch_cia_completions(self.session_id)
        assert all_passed is False
        assert missing_cia == [100]

    def test_skip_env_var_bypasses_gate(self) -> None:
        """SKIP_BATCH_CIA_GATE=1 bypasses the gate entirely."""
        _make_state(self.session_id, {
            "100": {"implementer": True},  # Missing CIA
        })
        with patch.dict(os.environ, {"SKIP_BATCH_CIA_GATE": "1"}):
            all_passed, with_cia, missing_cia = verify_batch_cia_completions(self.session_id)
        assert all_passed is True
        assert with_cia == []
        assert missing_cia == []

    def test_skip_env_var_true_bypasses(self) -> None:
        """SKIP_BATCH_CIA_GATE=true also bypasses."""
        _make_state(self.session_id, {
            "100": {"implementer": True},
        })
        with patch.dict(os.environ, {"SKIP_BATCH_CIA_GATE": "true"}):
            all_passed, with_cia, missing_cia = verify_batch_cia_completions(self.session_id)
        assert all_passed is True

    def test_mixed_zero_and_batch_keys(self) -> None:
        """'0' key is ignored, only batch issue keys are checked."""
        _make_state(self.session_id, {
            "0": {"implementer": True},
            "200": {"implementer": True, "continuous-improvement-analyst": True},
            "201": {"implementer": True},
        })
        all_passed, with_cia, missing_cia = verify_batch_cia_completions(self.session_id)
        assert all_passed is False
        assert with_cia == [200]
        assert missing_cia == [201]

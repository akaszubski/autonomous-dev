"""Tests for PIPELINE_BASE_COMMIT helpers in pipeline_state.py (Issue #1069).

Validates set_pipeline_base_commit and get_pipeline_base_commit behavior:
1. Roundtrip: set then get returns the same SHA
2. Missing state file: get returns None, set returns False
3. Empty / whitespace SHA: get returns None
4. Custom state_path overrides PIPELINE_STATE_FILE env var
5. Regression: get returns None when state file lacks 'base_commit' key
6. set preserves existing state fields (does not clobber other keys)

These helpers anchor `git diff --name-only` commands in the coordinator's
spec-validator dispatch to the commit captured at pipeline start, eliminating
false-positive FAIL verdicts caused by pre-existing working-tree state.

Date: 2026-05-10
Issue: #1069
"""

import json
import sys
from pathlib import Path

import pytest

# Add lib directory to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_state import (  # noqa: E402
    get_pipeline_base_commit,
    set_pipeline_base_commit,
)


SAMPLE_SHA = "0ecedce0a1b2c3d4e5f60718293a4b5c6d7e8f90"


class TestSetAndGetRoundtrip:
    """set_pipeline_base_commit -> get_pipeline_base_commit returns the same SHA."""

    def test_roundtrip_preserves_sha(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"mode": "fix", "session_id": "abc"}))

        assert set_pipeline_base_commit(SAMPLE_SHA, state_path=str(state_file)) is True
        assert get_pipeline_base_commit(state_path=str(state_file)) == SAMPLE_SHA

    def test_set_preserves_other_state_fields(self, tmp_path):
        """set_pipeline_base_commit MUST NOT clobber unrelated state fields."""
        state_file = tmp_path / "state.json"
        original = {"mode": "full", "run_id": "abc123", "alignment_passed": True}
        state_file.write_text(json.dumps(original))

        set_pipeline_base_commit(SAMPLE_SHA, state_path=str(state_file))

        result = json.loads(state_file.read_text())
        assert result["mode"] == "full"
        assert result["run_id"] == "abc123"
        assert result["alignment_passed"] is True
        assert result["base_commit"] == SAMPLE_SHA


class TestMissingOrInvalidState:
    """Behavior when the state file is missing, empty, or malformed."""

    def test_get_returns_none_for_missing_file(self, tmp_path):
        missing = tmp_path / "does_not_exist.json"
        assert get_pipeline_base_commit(state_path=str(missing)) is None

    def test_set_returns_false_for_missing_file(self, tmp_path):
        missing = tmp_path / "does_not_exist.json"
        assert set_pipeline_base_commit(SAMPLE_SHA, state_path=str(missing)) is False

    def test_get_returns_none_when_base_commit_key_absent(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"mode": "full"}))
        assert get_pipeline_base_commit(state_path=str(state_file)) is None

    def test_get_returns_none_for_empty_sha(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"base_commit": ""}))
        assert get_pipeline_base_commit(state_path=str(state_file)) is None

    def test_get_returns_none_for_whitespace_sha(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"base_commit": "   "}))
        assert get_pipeline_base_commit(state_path=str(state_file)) is None

    def test_get_returns_none_for_non_string_value(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"base_commit": 12345}))
        assert get_pipeline_base_commit(state_path=str(state_file)) is None

    def test_get_returns_none_for_malformed_json(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text("{not valid json")
        assert get_pipeline_base_commit(state_path=str(state_file)) is None


class TestEnvVarFallback:
    """When state_path is not provided, PIPELINE_STATE_FILE env var is honored."""

    def test_env_var_used_when_state_path_omitted(self, tmp_path, monkeypatch):
        state_file = tmp_path / "env_state.json"
        state_file.write_text(json.dumps({}))
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(state_file))

        assert set_pipeline_base_commit(SAMPLE_SHA) is True
        assert get_pipeline_base_commit() == SAMPLE_SHA

    def test_explicit_state_path_overrides_env_var(self, tmp_path, monkeypatch):
        """An explicit state_path argument MUST take precedence over the env var."""
        env_state = tmp_path / "env_state.json"
        env_state.write_text(json.dumps({}))
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(env_state))

        explicit_state = tmp_path / "explicit_state.json"
        explicit_state.write_text(json.dumps({}))

        set_pipeline_base_commit(SAMPLE_SHA, state_path=str(explicit_state))

        # Explicit path got the value
        assert get_pipeline_base_commit(state_path=str(explicit_state)) == SAMPLE_SHA
        # Env-var path did NOT get the value
        assert get_pipeline_base_commit(state_path=str(env_state)) is None


class TestIssue1069Regression:
    """Regression test reproducing the bug from Issue #1069.

    Bug: `git diff --name-only HEAD` includes pre-existing working-tree
    modifications, causing spec-validator to FAIL on files not changed by
    the current pipeline run.

    Fix: capture base commit at pipeline start, anchor diff to that SHA.

    This test simulates the state-file contract: pipeline writes base_commit
    at STEP 1 / STEP F1, and reads it back at STEP 8.5 / STEP F3.5 to build
    the anchored diff command.
    """

    def test_regression_issue_1069_base_commit_persists_across_steps(self, tmp_path):
        # Pipeline start: state file initialized (e.g., STEP 0 in implement.md)
        state_file = tmp_path / "implement_pipeline_state.json"
        state_file.write_text(json.dumps({"mode": "fix", "explicitly_invoked": True}))

        # STEP F1: coordinator captures base commit
        captured_sha = SAMPLE_SHA
        assert set_pipeline_base_commit(captured_sha, state_path=str(state_file)) is True

        # ... implementer runs, modifies files ...

        # STEP F3.5: coordinator reads base commit to build anchored diff command
        recovered = get_pipeline_base_commit(state_path=str(state_file))
        assert recovered == captured_sha, (
            "spec-validator dispatch must be able to recover the base commit "
            "captured at pipeline start; otherwise the diff falls back to "
            "plain HEAD and includes pre-existing tree state."
        )

#!/usr/bin/env python3
"""Regression tests for Issue #802: File-based bypass for agent completeness gate.

The env var SKIP_AGENT_COMPLETENESS_GATE=1 is unreachable from Bash commands
because the hook runs in a separate process. This tests the file-based bypass
at /tmp/skip_agent_completeness_gate which IS reachable via:
  touch /tmp/skip_agent_completeness_gate && git commit ...

Issues: #802
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
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
    sid = "test-regression-802-file-bypass"

    def _patched(s, *, run_id=None):
        import hashlib

        h = hashlib.sha256(s.encode()).hexdigest()[:8]
        return tmp_path / f"pipeline_agent_completions_{h}.json"

    monkeypatch.setattr(pcs, "_state_file_path", _patched)
    return sid


@pytest.fixture
def bypass_file(tmp_path, monkeypatch):
    """Create a temporary bypass file and patch the constant to use it.

    Returns the Path to the bypass file.
    """
    bypass = tmp_path / "skip_agent_completeness_gate"
    monkeypatch.setattr(pcs, "SKIP_GATE_FILE", bypass)
    return bypass


class TestFileBasedBypass:
    """Tests for the file-based bypass mechanism."""

    def test_file_bypass_allows(self, session_id, bypass_file):
        """Creating the bypass file should make verify return passed=True with no agents."""
        bypass_file.touch()

        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )

        assert passed is True
        assert completed == set()
        assert missing == set()

    def test_file_bypass_consumed_on_use(self, session_id, bypass_file):
        """Bypass file should be deleted after first use (one-shot)."""
        bypass_file.touch()
        assert bypass_file.exists()

        # First call: bypass active, file consumed
        passed1, _, _ = pcs.verify_pipeline_agent_completions(session_id, "full")
        assert passed1 is True
        assert not bypass_file.exists(), "Bypass file should be consumed (deleted) after use"

        # Second call: no bypass file, gate should enforce normally
        # Record some agents but NOT all required ones
        pcs.record_agent_completion(session_id, "implementer")
        passed2, _, missing2 = pcs.verify_pipeline_agent_completions(session_id, "full")
        assert passed2 is False, "Gate should block after bypass file is consumed"
        assert len(missing2) > 0

    def test_no_bypass_file_blocks(self, session_id, bypass_file):
        """Without the bypass file, gate should block normally when agents are missing."""
        assert not bypass_file.exists()

        # Record only one agent (not all required)
        pcs.record_agent_completion(session_id, "implementer")

        passed, completed, missing = pcs.verify_pipeline_agent_completions(
            session_id, "full"
        )

        assert passed is False
        assert len(missing) > 0
        assert "implementer" in completed


class TestCheckFileBypassHelper:
    """Direct tests for the _check_file_bypass helper function."""

    def test_returns_true_when_file_exists(self, bypass_file):
        """Helper should return True and delete the file."""
        bypass_file.touch()
        assert pcs._check_file_bypass() is True
        assert not bypass_file.exists()

    def test_returns_false_when_no_file(self, bypass_file):
        """Helper should return False when file doesn't exist."""
        assert not bypass_file.exists()
        assert pcs._check_file_bypass() is False

    def test_returns_true_even_if_unlink_fails(self, bypass_file):
        """Helper should return True (bypass) even if file deletion fails."""
        bypass_file.touch()

        original_unlink = Path.unlink

        def _failing_unlink(self, *args, **kwargs):
            raise OSError("Permission denied")

        with patch.object(Path, "unlink", _failing_unlink):
            result = pcs._check_file_bypass()

        assert result is True


class TestSkipGateFileConstant:
    """Verify the constant is correctly defined."""

    def test_constant_path(self):
        """SKIP_GATE_FILE should point to /tmp/skip_agent_completeness_gate."""
        assert pcs.SKIP_GATE_FILE == Path("/tmp/skip_agent_completeness_gate")


class TestBlockMessageMentionsBypass:
    """Verify block messages mention both bypass methods."""

    def test_hook_block_message_mentions_file_bypass(self):
        """unified_pre_tool.py block messages should mention file-based bypass."""
        hook_path = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
        )
        source = hook_path.read_text()
        assert "touch /tmp/skip_agent_completeness_gate" in source

    def test_lib_docstring_mentions_file_bypass(self):
        """pipeline_completion_state.py docstring should mention file-based bypass."""
        lib_path = LIB_DIR / "pipeline_completion_state.py"
        source = lib_path.read_text()
        assert "touch /tmp/skip_agent_completeness_gate" in source


class TestBlockMessageOrdering:
    """Issue #1086: file-based bypass MUST be listed before env-var in both deny messages."""

    HOOK_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"

    def _extract_non_batch_message(self) -> str:
        """Return the string-literal block of the non-batch deny message."""
        source = self.HOOK_PATH.read_text()
        start = source.index('BLOCKED: Agent completeness gate')
        end = source.index('(Issue #802)', start) + len('(Issue #802)')
        return source[start:end]

    def _extract_batch_message(self) -> str:
        """Return the string-literal block of the batch deny message."""
        source = self.HOOK_PATH.read_text()
        start = source.index('BLOCKED: Batch agent completeness gate')
        end = source.index('(Issue #853)', start) + len('(Issue #853)')
        return source[start:end]

    def test_non_batch_file_bypass_precedes_env_var(self):
        msg = self._extract_non_batch_message()
        file_idx = msg.index('touch /tmp/skip_agent_completeness_gate')
        env_idx = msg.index('SKIP_AGENT_COMPLETENESS_GATE=1')
        assert file_idx < env_idx, (
            f"file-bypass mention (idx {file_idx}) must precede env-var mention "
            f"(idx {env_idx}) in non-batch message"
        )

    def test_batch_file_bypass_precedes_env_var(self):
        msg = self._extract_batch_message()
        file_idx = msg.index('touch /tmp/skip_agent_completeness_gate')
        env_idx = msg.index('SKIP_AGENT_COMPLETENESS_GATE=1')
        assert file_idx < env_idx, (
            f"file-bypass mention (idx {file_idx}) must precede env-var mention "
            f"(idx {env_idx}) in batch message"
        )

    def test_non_batch_env_var_has_before_launching_caveat(self):
        msg = self._extract_non_batch_message()
        assert 'BEFORE launching claude' in msg, (
            "Non-batch message must include 'BEFORE launching claude' caveat on env-var bypass"
        )

    def test_batch_env_var_has_before_launching_caveat(self):
        msg = self._extract_batch_message()
        assert 'BEFORE launching claude' in msg, (
            "Batch message must include 'BEFORE launching claude' caveat on env-var bypass"
        )

    def test_non_batch_message_has_bypass_header(self):
        msg = self._extract_non_batch_message()
        assert 'BYPASS (in order of reliability)' in msg

    def test_batch_message_has_bypass_header(self):
        msg = self._extract_batch_message()
        assert 'BYPASS (in order of reliability)' in msg

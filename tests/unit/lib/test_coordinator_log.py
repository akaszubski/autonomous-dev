#!/usr/bin/env python3
"""
Tests for coordinator_log — coordinator-side activity log for background agents.

Regression tests for Issue #868: Doc-master completion events missing from
activity log when SubagentStop hook fails to fire for background agents.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — tests/unit/lib/ → parents[3] → repo root
# tests(3) / unit(2) / lib(1) / test_coordinator_log.py(0)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from coordinator_log import (
    _find_activity_log_dir,
    ensure_doc_master_logged,
    log_background_agent_completion,
)


@pytest.fixture()
def fake_claude_tree(tmp_path: Path) -> Path:
    """Create a minimal .claude/logs/activity/ tree in tmp_path."""
    activity_dir = tmp_path / ".claude" / "logs" / "activity"
    activity_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def fake_nested_dir(fake_claude_tree: Path) -> Path:
    """Return a deeply nested child directory inside the fake tree."""
    nested = fake_claude_tree / "a" / "b" / "c"
    nested.mkdir(parents=True)
    return nested


@pytest.fixture()
def isolated_no_claude_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory hermetically isolated from ambient ``.claude`` pollution.

    SANDBOX-ESCAPE HAZARD (found 2026-08-23): ``_find_activity_log_dir``
    walks upward from ``start_dir`` through EVERY ancestor with no boundary.
    On this machine, ``TMPDIR``'s own parent directory
    (``/private/var/folders/<xx>/<yyy>/.claude/logs/activity/``) contains a
    real, actively-written-to ``.claude`` tree — unrelated OS-level state,
    not created by this repo's tests. Before this fixture existed, the
    "no .claude dir anywhere" tests below would walk straight past
    ``tmp_path``, find that ambient directory, and
    ``log_background_agent_completion`` would WRITE a fake "doc-master
    completion" JSONL entry into it — verified directly:
    ``result == PosixPath('/private/var/folders/.../.claude/logs/activity/
    2026-08-23.jsonl')`` instead of the expected ``None``. That is a genuine
    write to real state outside the test sandbox, not merely a flaky
    assertion. This fixture patches ``Path.is_dir`` so any ``.claude``
    candidate outside ``tmp_path`` is reported absent, making the "no
    project markers anywhere" scenario hermetic without touching production
    code (``lib/coordinator_log.py`` is protected infrastructure).
    """
    empty_dir = tmp_path / "no_claude_here"
    empty_dir.mkdir()

    real_is_dir = Path.is_dir

    def _guarded_is_dir(self: Path) -> bool:
        if self.name == ".claude":
            try:
                self.relative_to(tmp_path)
            except ValueError:
                return False  # outside the test sandbox — treat as absent
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", _guarded_is_dir)
    return empty_dir


# ---- Test 1: JSONL entry is written with correct fields ----

class TestLogBackgroundAgentCompletion:
    def test_writes_jsonl_with_correct_fields(self, fake_claude_tree: Path) -> None:
        """Verify JSONL entry is written with all expected fields."""
        result_path = log_background_agent_completion(
            agent_type="doc-master",
            issue_number=868,
            batch_id="batch-20260415",
            result_word_count=450,
            duration_seconds=12.5,
            session_id="sess-abc-123",
            start_dir=fake_claude_tree,
        )

        assert result_path is not None
        assert result_path.exists()

        lines = result_path.read_text().strip().splitlines()
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["hook"] == "CoordinatorCompletionLog"
        assert entry["tool"] == "Agent"
        assert entry["subagent_type"] == "doc-master"
        assert entry["issue_number"] == 868
        assert entry["batch_id"] == "batch-20260415"
        assert entry["result_word_count"] == 450
        assert entry["duration_seconds"] == 12.5
        assert entry["session_id"] == "sess-abc-123"
        assert entry["source"] == "coordinator_fallback"
        # Timestamp must be parseable ISO-8601
        datetime.fromisoformat(entry["timestamp"])

    def test_appends_multiple_entries(self, fake_claude_tree: Path) -> None:
        """Calling twice should append, not overwrite."""
        for i in range(3):
            log_background_agent_completion(
                agent_type="implementer",
                issue_number=100 + i,
                session_id="sess-multi",
                start_dir=fake_claude_tree,
            )

        log_dir = fake_claude_tree / ".claude" / "logs" / "activity"
        files = list(log_dir.glob("*.jsonl"))
        assert len(files) == 1

        lines = files[0].read_text().strip().splitlines()
        assert len(lines) == 3

    def test_defaults_session_id_from_env(
        self, fake_claude_tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When session_id is empty, fall back to CLAUDE_SESSION_ID env var."""
        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session-42")

        log_background_agent_completion(
            agent_type="reviewer",
            issue_number=999,
            start_dir=fake_claude_tree,
        )

        log_dir = fake_claude_tree / ".claude" / "logs" / "activity"
        files = list(log_dir.glob("*.jsonl"))
        entry = json.loads(files[0].read_text().strip())
        assert entry["session_id"] == "env-session-42"

    def test_defaults_session_id_to_unknown(
        self, fake_claude_tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no session_id and no env var, use 'unknown'."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        log_background_agent_completion(
            agent_type="reviewer",
            issue_number=999,
            start_dir=fake_claude_tree,
        )

        log_dir = fake_claude_tree / ".claude" / "logs" / "activity"
        files = list(log_dir.glob("*.jsonl"))
        entry = json.loads(files[0].read_text().strip())
        assert entry["session_id"] == "unknown"


# ---- Test 2: Log directory discovery ----

class TestFindActivityDirectory:
    def test_finds_activity_dir_in_current(self, fake_claude_tree: Path) -> None:
        """Finds .claude/logs/activity when start_dir has .claude."""
        result = _find_activity_log_dir(start_dir=fake_claude_tree)
        assert result is not None
        assert result == fake_claude_tree / ".claude" / "logs" / "activity"

    def test_finds_activity_dir_from_nested_child(self, fake_nested_dir: Path) -> None:
        """Walks up from nested directory to find .claude."""
        result = _find_activity_log_dir(start_dir=fake_nested_dir)
        assert result is not None
        assert ".claude" in str(result)
        assert result.is_dir()

    def test_creates_logs_activity_subdirs(self, tmp_path: Path) -> None:
        """Creates logs/activity/ subdirectories if .claude exists but they don't."""
        (tmp_path / ".claude").mkdir()
        result = _find_activity_log_dir(start_dir=tmp_path)
        assert result is not None
        assert result.is_dir()
        assert result == tmp_path / ".claude" / "logs" / "activity"


# ---- Test 3: Missing directory handling ----

class TestHandlesMissingDirectory:
    def test_returns_none_when_no_claude_dir(self, isolated_no_claude_dir: Path) -> None:
        """No crash when .claude directory doesn't exist anywhere."""
        result = log_background_agent_completion(
            agent_type="doc-master",
            issue_number=1,
            session_id="s",
            start_dir=isolated_no_claude_dir,
        )
        assert result is None

    def test_find_returns_none_when_no_claude_dir(self, isolated_no_claude_dir: Path) -> None:
        """_find_activity_log_dir returns None for directories without .claude."""
        assert _find_activity_log_dir(start_dir=isolated_no_claude_dir) is None


# ---- Test 4: ensure_doc_master_logged convenience ----

class TestEnsureDocMasterLogged:
    def test_writes_doc_master_entry(self, fake_claude_tree: Path) -> None:
        """ensure_doc_master_logged writes an entry with agent_type='doc-master'."""
        result_path = ensure_doc_master_logged(
            issue_number=868,
            batch_id="batch-abc",
            result_word_count=200,
            duration_seconds=5.0,
            session_id="doc-sess",
            start_dir=fake_claude_tree,
        )

        assert result_path is not None
        entry = json.loads(result_path.read_text().strip())
        assert entry["subagent_type"] == "doc-master"
        assert entry["issue_number"] == 868
        assert entry["source"] == "coordinator_fallback"

    def test_returns_none_when_no_log_dir(self, isolated_no_claude_dir: Path) -> None:
        """No crash when called with no .claude directory."""
        assert ensure_doc_master_logged(issue_number=1, start_dir=isolated_no_claude_dir) is None


# ---- Test 5: Entry format matches BatchCoordinatorLog ----

class TestEntryFormatMatchesBatchCoordinatorLog:
    """Verify the JSONL fields match the format documented in implement-batch.md."""

    REQUIRED_FIELDS = {
        "timestamp",
        "hook",
        "tool",
        "subagent_type",
        "issue_number",
        "batch_id",
        "result_word_count",
        "duration_seconds",
        "session_id",
        "source",
    }

    def test_all_required_fields_present(self, fake_claude_tree: Path) -> None:
        """Entry contains exactly the expected set of fields."""
        log_background_agent_completion(
            agent_type="doc-master",
            issue_number=42,
            batch_id="b1",
            result_word_count=100,
            duration_seconds=3.0,
            session_id="s1",
            start_dir=fake_claude_tree,
        )

        log_dir = fake_claude_tree / ".claude" / "logs" / "activity"
        files = list(log_dir.glob("*.jsonl"))
        entry = json.loads(files[0].read_text().strip())

        assert set(entry.keys()) == self.REQUIRED_FIELDS

    def test_hook_value_is_coordinator_completion_log(self, fake_claude_tree: Path) -> None:
        """The 'hook' field must be 'CoordinatorCompletionLog' (matching batch docs)."""
        log_background_agent_completion(
            agent_type="test-agent",
            issue_number=1,
            session_id="s",
            start_dir=fake_claude_tree,
        )

        log_dir = fake_claude_tree / ".claude" / "logs" / "activity"
        files = list(log_dir.glob("*.jsonl"))
        entry = json.loads(files[0].read_text().strip())
        assert entry["hook"] == "CoordinatorCompletionLog"

    def test_source_is_coordinator_fallback(self, fake_claude_tree: Path) -> None:
        """The 'source' field distinguishes from SubagentStop entries."""
        log_background_agent_completion(
            agent_type="test-agent",
            issue_number=1,
            session_id="s",
            start_dir=fake_claude_tree,
        )

        log_dir = fake_claude_tree / ".claude" / "logs" / "activity"
        files = list(log_dir.glob("*.jsonl"))
        entry = json.loads(files[0].read_text().strip())
        assert entry["source"] == "coordinator_fallback"

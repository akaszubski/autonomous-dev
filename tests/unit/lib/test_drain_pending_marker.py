"""Unit tests for ``DrainPendingMarker`` in ``drain_pending``.

Covers:
* ``write()`` / ``read()`` round-trip preserves session_id, cluster_tag, issues.
* Atomic-write — destination file is either the new content or absent
  (no half-written content).
* ``clear()`` returns True when a file existed, False when missing.
* ``read()`` returns None on missing file and on malformed JSON.
* ``is_stale()`` returns True past STALE_MINUTES, False before.
* Malformed ``started_at`` timestamp → ``is_stale() == True``.
* ``write()`` rejects empty issues list (ValueError).

Issue: drain-queue durability plan (round-2 PROCEED composite 3.67).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Add lib directory to sys.path so `from drain_pending import ...` works.
_LIB = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_pending import (  # noqa: E402
    MARKER_FILENAME,
    STALE_MINUTES,
    DrainPendingMarker,
    _marker_path,
)


def _make_repo(tmp_path: Path) -> Path:
    """Create a temp repo with a ``.claude/local/`` directory."""
    repo = tmp_path / "repo"
    (repo / ".claude" / "local").mkdir(parents=True, exist_ok=True)
    return repo


# ---------------------------------------------------------------------------
# write / read round-trip
# ---------------------------------------------------------------------------


def test_write_read_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    """write() then read() returns the same issues, cluster_tag, session_id."""
    repo = _make_repo(tmp_path)
    DrainPendingMarker.write(
        issues=[1160, 1161, 1163],
        cluster_tag="UNTAGGED",
        session_id="sess-abc-123",
        repo_root=repo,
    )
    loaded = DrainPendingMarker.read(repo_root=repo)
    assert loaded is not None
    assert loaded.issues == [1160, 1161, 1163]
    assert loaded.cluster_tag == "UNTAGGED"
    assert loaded.session_id == "sess-abc-123"
    assert loaded.started_at  # ISO-8601 string


def test_write_falls_back_to_env_session_id(tmp_path: Path, monkeypatch) -> None:
    """When session_id is None, write() reads $CLAUDE_SESSION_ID."""
    repo = _make_repo(tmp_path)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session-xyz")
    DrainPendingMarker.write(
        issues=[42], cluster_tag="bug", repo_root=repo
    )
    loaded = DrainPendingMarker.read(repo_root=repo)
    assert loaded is not None
    assert loaded.session_id == "env-session-xyz"


def test_write_uses_unknown_when_env_absent(
    tmp_path: Path, monkeypatch
) -> None:
    """Without session_id arg or env, write() stores ``"unknown"``."""
    repo = _make_repo(tmp_path)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    DrainPendingMarker.write(issues=[7], cluster_tag="x", repo_root=repo)
    loaded = DrainPendingMarker.read(repo_root=repo)
    assert loaded is not None
    assert loaded.session_id == "unknown"


def test_write_raises_on_empty_issues(tmp_path: Path) -> None:
    """Empty issues list is a programmer error → ValueError."""
    repo = _make_repo(tmp_path)
    with pytest.raises(ValueError, match="non-empty"):
        DrainPendingMarker.write(issues=[], cluster_tag="x", repo_root=repo)


# ---------------------------------------------------------------------------
# atomic-write semantics
# ---------------------------------------------------------------------------


def test_atomic_write_no_partial_file_on_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """If atomic-write fails mid-rename, the destination is NOT half-written.

    Simulates ``os.replace`` raising; verifies the temp file is cleaned up
    and the destination remains absent.
    """
    repo = _make_repo(tmp_path)
    path = _marker_path(repo)
    assert not path.exists()

    import drain_pending  # noqa: WPS433

    # Patch _atomic_write_json's os.replace to raise mid-write.
    from pipeline_state import os as ps_os  # type: ignore

    real_replace = ps_os.replace

    def boom(*_args, **_kwargs):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(ps_os, "replace", boom)
    with pytest.raises(OSError):
        DrainPendingMarker.write(issues=[1], cluster_tag="x", repo_root=repo)
    # Destination remains absent (or at worst pre-existing — we asserted None above)
    assert not path.exists()
    # Temp files cleaned up — no stray `.drain_pending.json_*` files
    leftovers = list(path.parent.glob(".drain_pending.json_*"))
    assert leftovers == [], f"Stray temp files: {leftovers}"

    monkeypatch.setattr(ps_os, "replace", real_replace)


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    """A second write() replaces the first marker atomically."""
    repo = _make_repo(tmp_path)
    DrainPendingMarker.write(
        issues=[1], cluster_tag="old", session_id="s1", repo_root=repo
    )
    DrainPendingMarker.write(
        issues=[2, 3], cluster_tag="new", session_id="s2", repo_root=repo
    )
    loaded = DrainPendingMarker.read(repo_root=repo)
    assert loaded is not None
    assert loaded.issues == [2, 3]
    assert loaded.cluster_tag == "new"
    assert loaded.session_id == "s2"


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------


def test_clear_returns_true_when_present(tmp_path: Path) -> None:
    """clear() returns True after a successful write()."""
    repo = _make_repo(tmp_path)
    DrainPendingMarker.write(issues=[1], cluster_tag="x", repo_root=repo)
    assert DrainPendingMarker.clear(repo_root=repo) is True
    assert not _marker_path(repo).exists()


def test_clear_returns_false_when_absent(tmp_path: Path) -> None:
    """clear() is idempotent — False on missing file, not an exception."""
    repo = _make_repo(tmp_path)
    assert DrainPendingMarker.clear(repo_root=repo) is False


# ---------------------------------------------------------------------------
# read() error tolerance
# ---------------------------------------------------------------------------


def test_read_returns_none_when_missing(tmp_path: Path) -> None:
    """No marker present → read() returns None (gate fails open)."""
    repo = _make_repo(tmp_path)
    assert DrainPendingMarker.read(repo_root=repo) is None


def test_read_returns_none_on_malformed_json(tmp_path: Path) -> None:
    """Corrupt JSON → read() returns None, NOT raise.

    The gate fails open on parse errors — never block a commit because a
    stale marker is unreadable.
    """
    repo = _make_repo(tmp_path)
    path = _marker_path(repo)
    path.write_text("{this is not json", encoding="utf-8")
    assert DrainPendingMarker.read(repo_root=repo) is None


def test_read_returns_none_on_non_dict_root(tmp_path: Path) -> None:
    """JSON array at the root → not a dict → returns None."""
    repo = _make_repo(tmp_path)
    path = _marker_path(repo)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert DrainPendingMarker.read(repo_root=repo) is None


def test_read_returns_none_on_non_list_issues(tmp_path: Path) -> None:
    """``issues`` field that is not a list → returns None."""
    repo = _make_repo(tmp_path)
    path = _marker_path(repo)
    path.write_text(
        json.dumps({"issues": "not-a-list", "cluster_tag": "x"}), encoding="utf-8"
    )
    assert DrainPendingMarker.read(repo_root=repo) is None


# ---------------------------------------------------------------------------
# is_stale()
# ---------------------------------------------------------------------------


def test_is_stale_false_before_threshold(tmp_path: Path) -> None:
    """A marker 1 minute old is NOT stale."""
    repo = _make_repo(tmp_path)
    DrainPendingMarker.write(issues=[1], cluster_tag="x", repo_root=repo)
    marker = DrainPendingMarker.read(repo_root=repo)
    assert marker is not None
    one_min_later = datetime.now(timezone.utc) + timedelta(minutes=1)
    assert marker.is_stale(now=one_min_later) is False


def test_is_stale_true_past_threshold(tmp_path: Path) -> None:
    """A marker STALE_MINUTES + 1 old IS stale."""
    repo = _make_repo(tmp_path)
    DrainPendingMarker.write(issues=[1], cluster_tag="x", repo_root=repo)
    marker = DrainPendingMarker.read(repo_root=repo)
    assert marker is not None
    deep_future = datetime.now(timezone.utc) + timedelta(minutes=STALE_MINUTES + 1)
    assert marker.is_stale(now=deep_future) is True


def test_is_stale_true_for_malformed_started_at() -> None:
    """Unparseable timestamp → stale (SessionStart reaps it)."""
    marker = DrainPendingMarker(
        issues=[1], cluster_tag="x", started_at="not-a-timestamp"
    )
    assert marker.is_stale() is True


def test_is_stale_true_for_empty_started_at() -> None:
    """Empty timestamp → stale."""
    marker = DrainPendingMarker(issues=[1], cluster_tag="x", started_at="")
    assert marker.is_stale() is True

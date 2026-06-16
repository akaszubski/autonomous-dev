"""Drain-pending marker file for ``/drain-queue`` durability gate.

Writes a per-repo JSON marker at ``<repo>/.claude/local/drain_pending.json``
when ``/drain-queue`` STEP 3.6 selects a cluster. The marker carries the
cluster's issue numbers, root_cause_tag, and a session-scoped fingerprint so
the ``unified_pre_tool.py`` commit gate can verify that subsequent
``git commit`` invocations reference one of the cluster issues via
``Closes #N`` / ``Fixes #N``.

The marker is cleared by ``/drain-queue`` STEP 12.5 after post-push
state-CLOSED verification succeeds. Stale markers (orphaned by a crashed
pipeline) are reaped at SessionStart by ``is_stale()`` — the **gate itself
NEVER consults TTL** so long ``/implement`` runs (observed 2h+) remain covered.

Issue: drain-queue durability plan (round-2 PROCEED composite 3.67).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

try:
    # Normal package-style import (preferred when invoked from production code).
    from .pipeline_state import _atomic_write_json, get_legacy_sentinel_path  # type: ignore
except ImportError:  # pragma: no cover - fallback for scripts that load module by path
    from pipeline_state import _atomic_write_json, get_legacy_sentinel_path  # type: ignore


# Marker filename — sits next to the legacy pipeline-state sentinel under
# ``<repo_root>/.claude/local/``. Resolved via ``get_legacy_sentinel_path()``
# so the per-repo path policy (Issue #1206) is honored.
MARKER_FILENAME: str = "drain_pending.json"

# Stale-marker TTL used by SessionStart cleanup ONLY. The commit gate at
# ``unified_pre_tool.py`` MUST NOT consult this constant — long ``/implement``
# runs (2h+ observed) require uninterrupted enforcement.
#
# 4 hours = 240 minutes — generous upper bound on a single ``/drain-queue``
# run. Anything older is almost certainly an orphaned marker from a crashed
# or hung pipeline.
STALE_MINUTES: int = 240


def _marker_path(repo_root: Optional[Path] = None) -> Path:
    """Resolve the per-repo marker path: ``<repo>/.claude/local/drain_pending.json``.

    Delegates parent-directory resolution to ``get_legacy_sentinel_path`` so
    the per-repo policy (Issue #1206) is honored and the parent directory
    (mode 0o700) is created if missing.

    Args:
        repo_root: Optional explicit repo root. ``None`` walks for ``.git``
            or ``.claude`` markers per ``find_project_root()``.

    Returns:
        Fully-qualified marker file path. The file itself MAY or MAY NOT
        exist.
    """
    sentinel = get_legacy_sentinel_path(repo_root)
    return sentinel.parent / MARKER_FILENAME


@dataclass
class DrainPendingMarker:
    """Marker file recording an active /drain-queue cluster commitment.

    Attributes:
        issues: Cluster issue numbers (one of these MUST be referenced via
            ``Closes #N`` / ``Fixes #N`` in any subsequent ``git commit``).
        cluster_tag: ``root_cause_tag`` from the selected /triage cluster.
        started_at: ISO-8601 UTC timestamp of marker creation.
        session_id: ``CLAUDE_SESSION_ID`` (or ``"unknown"``) for audit.
    """

    issues: List[int] = field(default_factory=list)
    cluster_tag: str = ""
    started_at: str = ""
    session_id: str = "unknown"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def write(
        cls,
        *,
        issues: List[int],
        cluster_tag: str,
        session_id: Optional[str] = None,
        repo_root: Optional[Path] = None,
    ) -> "DrainPendingMarker":
        """Atomically write a marker for the active drain cluster.

        Args:
            issues: Cluster issue numbers. MUST be non-empty.
            cluster_tag: ``root_cause_tag`` for the selected cluster.
            session_id: Optional session id; falls back to ``$CLAUDE_SESSION_ID``
                or ``"unknown"``.
            repo_root: Optional explicit repo root. ``None`` triggers marker
                walk.

        Returns:
            The populated marker instance.

        Raises:
            ValueError: If ``issues`` is empty.
            OSError: From atomic-write failure (propagated unchanged).
        """
        if not issues:
            raise ValueError(
                "DrainPendingMarker.write: issues must be a non-empty list\n"
                "Expected: list of GitHub issue numbers from the selected cluster\n"
                "See: .claude/plans/drain-queue-durability.md"
            )
        sid = session_id if session_id is not None else os.environ.get(
            "CLAUDE_SESSION_ID", "unknown"
        )
        marker = cls(
            issues=[int(n) for n in issues],
            cluster_tag=str(cluster_tag),
            started_at=datetime.now(timezone.utc).isoformat(),
            session_id=str(sid),
        )
        path = _marker_path(repo_root)
        _atomic_write_json(
            path,
            {
                "issues": marker.issues,
                "cluster_tag": marker.cluster_tag,
                "started_at": marker.started_at,
                "session_id": marker.session_id,
            },
            indent=2,
        )
        return marker

    @classmethod
    def read(cls, repo_root: Optional[Path] = None) -> Optional["DrainPendingMarker"]:
        """Read the current marker. Returns ``None`` if missing or malformed.

        Tolerates malformed JSON and missing fields — the gate fails open
        (no marker → no enforcement) rather than blocking on parse errors.

        Args:
            repo_root: Optional explicit repo root.

        Returns:
            The marker instance if readable, ``None`` otherwise.
        """
        path = _marker_path(repo_root)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        try:
            issues_raw = data.get("issues", [])
            if not isinstance(issues_raw, list):
                return None
            issues = [int(n) for n in issues_raw]
        except (TypeError, ValueError):
            return None
        return cls(
            issues=issues,
            cluster_tag=str(data.get("cluster_tag", "")),
            started_at=str(data.get("started_at", "")),
            session_id=str(data.get("session_id", "unknown")),
        )

    @classmethod
    def clear(cls, repo_root: Optional[Path] = None) -> bool:
        """Delete the marker file. Returns ``True`` if a file was removed.

        Idempotent: missing file is not an error.

        Args:
            repo_root: Optional explicit repo root.

        Returns:
            ``True`` if a marker was deleted, ``False`` if none existed.
        """
        path = _marker_path(repo_root)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError:
            # Best effort — propagate-as-False; caller may retry.
            return False

    # ------------------------------------------------------------------
    # TTL (cleanup helper — NOT consulted by the commit gate)
    # ------------------------------------------------------------------

    def is_stale(self, *, now: Optional[datetime] = None) -> bool:
        """Return True if the marker is past ``STALE_MINUTES`` old.

        Used by SessionStart cleanup ONLY. The commit gate at
        ``unified_pre_tool.py`` MUST NOT consult this method — long
        ``/implement`` runs (2h+ observed) require uninterrupted enforcement.

        Malformed timestamps are treated as stale (so SessionStart cleanup
        reaps them).

        Args:
            now: Optional reference time for testing. Defaults to UTC now.

        Returns:
            True if the marker is older than ``STALE_MINUTES`` or its
            ``started_at`` is unparseable.
        """
        if not self.started_at:
            return True
        try:
            started = datetime.fromisoformat(self.started_at)
        except ValueError:
            return True
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        reference = now if now is not None else datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        return reference - started > timedelta(minutes=STALE_MINUTES)

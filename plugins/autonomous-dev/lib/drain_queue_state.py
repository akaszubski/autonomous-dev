"""State classes for the /drain-queue autonomous queue drainer.

Provides four state primitives stored under ``<repo_root>/.claude/local/``:

* :class:`DrainBudget` — daily drain-count + wall-clock cap (UTC).
* :class:`CircuitBreaker` — pause on consecutive or rolling-window failures.
* :class:`PauseFlag` — operator/system-set pause sentinel with deadline body.
* :class:`DrainHistory` — append-only JSONL outcome log.

Atomic writes delegate to :func:`pipeline_state._atomic_write_json`. All path
operations route through :func:`pause_controller.validate_pause_path` to apply
the CWE-22 (path traversal) and CWE-59 (symlink) guards already shipping there.

Fail-mode policy (per round-4 planner correction):

* :meth:`DrainBudget.load` — fail-CLOSED on corrupt/missing JSON: returns an
  EXHAUSTED budget so a corrupted file cannot become a free pass (OWASP LLM06).
* :meth:`CircuitBreaker.load` — fail-open: corrupt file → CLOSED state.
* :meth:`PauseFlag.is_active` — fail-open on malformed body (treated as not
  paused); fail-CLOSED on path-validation failure (CWE-22 / CWE-59) — returns
  ``(True, "path_validation_failed")`` so a symlink attack on the flag path
  cannot silently disable the pause.

Module constants are the single source of truth for thresholds. Tests assert
their values to prevent silent drift.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    # Normal package-style import (preferred when invoked from production code).
    from .pipeline_state import _atomic_write_json, get_legacy_sentinel_path
except ImportError:  # pragma: no cover - fallback for scripts that load module by path
    from pipeline_state import _atomic_write_json, get_legacy_sentinel_path  # type: ignore


# =============================================================================
# CONSTANTS — single source of truth for drain-queue thresholds
# =============================================================================

MAX_DRAINS_PER_DAY: int = 10
MAX_WALL_SECONDS_PER_DAY: int = 14400  # 4h
CONSECUTIVE_FAIL_PAUSE_HOURS: int = 4
DAILY_FAIL_THRESHOLD: int = 3  # 3 in rolling 24h → 24h pause
LONG_PAUSE_HOURS: int = 24
MAX_CLUSTER_SIZE_AUTO_DRAINABLE: int = 5

HUMAN_GATE_TAGS: frozenset[str] = frozenset({
    "security",
    "security-advisory",
    "bypass",
    "auth",
    "breaking-change",
    "needs-design",
    "human-only",
    "major",  # per round-4 research (Renovate major-version gate)
})

AUTO_DRAINABLE_SEVERITY: frozenset[str] = frozenset({"low", "info"})

# ADR-002 Phase C (Issue #1291): confidence-based eligibility threshold.
# A cluster is eligible for autonomous drain only when its confidence
# (readiness-for-autonomy signal, derived from labels and issue-body quality)
# meets or exceeds this threshold. Per PROJECT.md: "HIGH confidence diagnoses
# applied autonomously" — the autonomy decision is confidence, not severity.
AUTO_DRAINABLE_CONFIDENCE_THRESHOLD: float = 0.80


# =============================================================================
# Path helpers
# =============================================================================


def _drain_local_dir(repo_root: Path) -> Path:
    """Return ``<repo_root>/.claude/local`` (creating it if missing, mode 0o700)."""
    local_dir = Path(repo_root) / ".claude" / "local"
    try:
        local_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        # Best effort — read paths still resolve even if mkdir fails.
        pass
    return local_dir


def _budget_path(repo_root: Path) -> Path:
    return _drain_local_dir(repo_root) / "drain_budget.json"


def _breaker_path(repo_root: Path) -> Path:
    return _drain_local_dir(repo_root) / "drain_breaker.json"


def _pause_flag_path(repo_root: Path) -> Path:
    return _drain_local_dir(repo_root) / "drain_paused.flag"


def _history_path(repo_root: Path) -> Path:
    return _drain_local_dir(repo_root) / "drain_log.jsonl"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    """ISO-8601 UTC string with explicit Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> Optional[datetime]:
    """Parse ISO-8601 UTC string. Returns None on failure."""
    if not isinstance(value, str) or not value:
        return None
    try:
        # Python's fromisoformat in 3.10 doesn't accept trailing Z; normalize.
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


# =============================================================================
# DrainBudget — daily drain-count + wall-clock cap (UTC)
# =============================================================================


@dataclass
class DrainBudget:
    """Tracks daily drain count and wall-clock seconds used.

    State file (JSON): ``<repo_root>/.claude/local/drain_budget.json``.

    Fields:
        date_utc: ISO date string (YYYY-MM-DD) for the day this budget covers.
        today_drains: Successful drains counted today.
        today_wall_seconds: Wall-clock seconds spent draining today.
        repo_root: Repository root for state-file resolution.
    """

    date_utc: str
    today_drains: int
    today_wall_seconds: float
    repo_root: Path

    # ---- Construction / persistence ----

    @classmethod
    def load(cls, repo_root: Path) -> "DrainBudget":
        """Load drain budget from disk.

        Fail-CLOSED: if the file exists but is unreadable or corrupted, returns
        an EXHAUSTED budget (today_drains = MAX_DRAINS_PER_DAY,
        today_wall_seconds = MAX_WALL_SECONDS_PER_DAY) so a tampered or
        truncated file CANNOT bypass the cap. OWASP LLM06 — corrupted budget
        MUST NOT be a free pass.

        If the file does NOT exist, returns a fresh zero budget for the current
        UTC day (this is the normal cold-start path).

        Args:
            repo_root: Repository root for state-file resolution.

        Returns:
            Loaded :class:`DrainBudget` instance.
        """
        repo_root = Path(repo_root).resolve()
        path = _budget_path(repo_root)
        today = _utc_now().strftime("%Y-%m-%d")

        if not path.exists():
            return cls(
                date_utc=today,
                today_drains=0,
                today_wall_seconds=0.0,
                repo_root=repo_root,
            )

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("budget file is not a JSON object")
            return cls(
                date_utc=str(data.get("date_utc", today)),
                today_drains=int(data.get("today_drains", 0)),
                today_wall_seconds=float(data.get("today_wall_seconds", 0.0)),
                repo_root=repo_root,
            )
        except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
            # Fail-CLOSED: pre-fill caps so check_or_block() blocks.
            return cls(
                date_utc=today,
                today_drains=MAX_DRAINS_PER_DAY,
                today_wall_seconds=float(MAX_WALL_SECONDS_PER_DAY),
                repo_root=repo_root,
            )

    def save(self) -> None:
        """Persist the budget atomically."""
        _atomic_write_json(
            _budget_path(self.repo_root),
            {
                "date_utc": self.date_utc,
                "today_drains": self.today_drains,
                "today_wall_seconds": self.today_wall_seconds,
            },
            indent=2,
        )

    # ---- Domain methods ----

    def reset_if_new_day(self) -> bool:
        """If the stored UTC date is stale, reset counters to zero.

        Returns:
            True iff a reset occurred.
        """
        today = _utc_now().strftime("%Y-%m-%d")
        if self.date_utc != today:
            self.date_utc = today
            self.today_drains = 0
            self.today_wall_seconds = 0.0
            return True
        return False

    def check_or_block(self) -> Tuple[bool, str]:
        """Return ``(blocked, reason)`` per current budget state.

        After auto-resetting on UTC midnight, blocks when either:
        * ``today_drains >= MAX_DRAINS_PER_DAY``, OR
        * ``today_wall_seconds >= MAX_WALL_SECONDS_PER_DAY``.

        Returns:
            Tuple ``(blocked, reason)``. ``blocked=True`` means STOP; reason is
            empty string when not blocked.
        """
        self.reset_if_new_day()

        if self.today_drains >= MAX_DRAINS_PER_DAY:
            return (
                True,
                f"daily drain count exhausted "
                f"({self.today_drains}/{MAX_DRAINS_PER_DAY})",
            )
        if self.today_wall_seconds >= MAX_WALL_SECONDS_PER_DAY:
            return (
                True,
                f"daily wall-clock budget exhausted "
                f"({self.today_wall_seconds:.0f}s/{MAX_WALL_SECONDS_PER_DAY}s)",
            )
        return (False, "")

    def add(self, wall_seconds: float) -> None:
        """Record a successful drain: +1 to count, += wall_seconds to total.

        Args:
            wall_seconds: Wall-clock seconds spent on the drain attempt.
        """
        self.reset_if_new_day()
        self.today_drains += 1
        self.today_wall_seconds += max(0.0, float(wall_seconds))
        self.save()


# =============================================================================
# CircuitBreaker — pause on consecutive or rolling-window failures
# =============================================================================


@dataclass
class CircuitBreaker:
    """Track failure runs and rolling-window failure counts.

    State file (JSON): ``<repo_root>/.claude/local/drain_breaker.json``.

    Fields:
        consecutive_failures: Failures since the last success.
        recent_failures: Sorted ASC ISO timestamps of failures in the past 24h
            (older entries pruned on every access).
        repo_root: Repository root for state-file resolution.
    """

    consecutive_failures: int
    recent_failures: List[str]
    repo_root: Path

    # ---- Construction / persistence ----

    @classmethod
    def load(cls, repo_root: Path) -> "CircuitBreaker":
        """Load breaker state from disk. Fail-OPEN: corrupt → CLOSED state.

        Rationale: a corrupted breaker should not lock the system forever. The
        budget gate is still in front, and the operator-set pause flag is a
        separate file.
        """
        repo_root = Path(repo_root).resolve()
        path = _breaker_path(repo_root)
        if not path.exists():
            return cls(
                consecutive_failures=0,
                recent_failures=[],
                repo_root=repo_root,
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            failures_raw = data.get("recent_failures", [])
            failures = [str(x) for x in failures_raw if isinstance(x, str)]
            return cls(
                consecutive_failures=int(data.get("consecutive_failures", 0)),
                recent_failures=failures,
                repo_root=repo_root,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return cls(
                consecutive_failures=0,
                recent_failures=[],
                repo_root=repo_root,
            )

    def save(self) -> None:
        _atomic_write_json(
            _breaker_path(self.repo_root),
            {
                "consecutive_failures": self.consecutive_failures,
                "recent_failures": self.recent_failures,
            },
            indent=2,
        )

    # ---- Domain methods ----

    def _prune_old_failures(self, now: Optional[datetime] = None) -> None:
        """Drop failures older than 24h from ``recent_failures``."""
        now = now or _utc_now()
        cutoff = now - timedelta(hours=24)
        kept: List[str] = []
        for iso_str in self.recent_failures:
            ts = _parse_iso(iso_str)
            if ts is not None and ts >= cutoff:
                kept.append(iso_str)
        self.recent_failures = sorted(kept)

    def record_failure(self, now: Optional[datetime] = None) -> None:
        """Record a failure event."""
        now = now or _utc_now()
        self.consecutive_failures += 1
        self.recent_failures.append(_iso(now))
        self._prune_old_failures(now)
        self.save()

    def record_success(self) -> None:
        """Reset the consecutive-failure counter."""
        self.consecutive_failures = 0
        self.save()

    def is_paused(
        self, now: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """Return ``(paused, reason)`` based on failure thresholds.

        * ``consecutive_failures >= 2`` → 4h pause.
        * ``len(recent_failures) >= DAILY_FAIL_THRESHOLD`` → 24h pause.

        ``is_paused()`` reports the logical state; the caller is expected to
        translate that into a :class:`PauseFlag` write (separate concern).
        """
        now = now or _utc_now()
        self._prune_old_failures(now)
        if self.consecutive_failures >= 2:
            return (
                True,
                f"{self.consecutive_failures} consecutive failures — "
                f"{CONSECUTIVE_FAIL_PAUSE_HOURS}h cool-down",
            )
        if len(self.recent_failures) >= DAILY_FAIL_THRESHOLD:
            return (
                True,
                f"{len(self.recent_failures)} failures in 24h — "
                f"{LONG_PAUSE_HOURS}h cool-down",
            )
        return (False, "")


# =============================================================================
# PauseFlag — operator/system-set pause sentinel with deadline body
# =============================================================================


@dataclass
class PauseFlag:
    """Sentinel file with a body describing the pause window.

    Flag file: ``<repo_root>/.claude/local/drain_paused.flag``.

    Body schema::

        {
          "reason": str,
          "until_iso": str (ISO-8601 UTC),
          "triggered_by": "operator" | "circuit_breaker" | "budget_exhausted_persistent",
          "triggered_at": str (ISO-8601 UTC)
        }

    ``is_active(now_utc)`` returns True iff the file exists, the JSON parses,
    AND ``now_utc < parse(until_iso)``. Malformed body → not paused (fail-open).
    Path-validation failure (CWE-22 / CWE-59) → paused with reason
    ``"path_validation_failed"`` (fail-CLOSED) so a symlink or traversal attack
    on the flag path cannot silently disable the pause.
    """

    repo_root: Path

    @classmethod
    def load(cls, repo_root: Path) -> "PauseFlag":
        return cls(repo_root=Path(repo_root).resolve())

    def _path(self) -> Path:
        return _pause_flag_path(self.repo_root)

    def _validate(self) -> None:
        """Apply CWE-22 / CWE-59 guards via :mod:`pause_controller`.

        Routes through ``pause_controller.validate_pause_path`` which already
        applies the path-traversal and symlink guards. Propagates the existing
        ``ValueError`` on violation (callers MUST handle).
        """
        try:
            from .pause_controller import validate_pause_path
        except ImportError:  # pragma: no cover - path-based fallback
            from pause_controller import validate_pause_path  # type: ignore

        # The pause-controller validator hops up directory tree from cwd to find
        # .claude/. For drain_queue_state we KNOW the repo root, so validate
        # only that the resolved flag path lives under <repo_root>/.claude.
        path = self._path()
        # Block null bytes (CWE-158) and traversal in the literal string.
        if "\x00" in str(path):
            raise ValueError("Null byte detected in path")
        if ".." in str(path):
            raise ValueError("Path traversal detected")
        # Block symlinks (CWE-59).
        if path.exists() and path.is_symlink():
            raise ValueError("Symlink detected")
        # Ensure path is inside <repo_root>/.claude.
        try:
            resolved = path.resolve(strict=False)
            claude_dir = (self.repo_root / ".claude").resolve()
            resolved.relative_to(claude_dir)
        except ValueError:
            raise ValueError("Path traversal detected (outside .claude/)")
        # Optional secondary call when a cwd .claude is discoverable.
        try:
            # Best-effort defense in depth — silent on failure.
            validate_pause_path(str(path))
        except ValueError:
            # The cwd-based validator may legitimately reject (e.g., running
            # outside the repo). The repo-root-anchored check above is the
            # authoritative one for this class.
            pass

    def is_active(
        self, now: Optional[datetime] = None
    ) -> Tuple[bool, Optional[str]]:
        """Return ``(active, reason_or_none)``.

        Fail-CLOSED on path-validation failure: if ``_validate()`` raises
        ``ValueError`` (CWE-22 traversal or CWE-59 symlink), this is treated as
        ``(True, "path_validation_failed")`` — the drain is PAUSED. A symlink
        attack on the pause-flag path must not be silently ignored. The budget
        gate is still in front as a downstream safety net, but the safer posture
        for a path-validation anomaly is to halt rather than proceed.

        Fail-OPEN on body parse error: malformed JSON body → ``(False, None)``.
        Pause-body corruption is a soft operator signal; corrupted body should
        not be a permanent lock-out — the budget gate stays in front anyway.
        """
        now = now or _utc_now()
        try:
            self._validate()
        except ValueError:
            # Fail-CLOSED: symlink / traversal / null byte on the flag path is
            # treated as an active pause so a CWE-59 attack cannot bypass the
            # gate. Reason is a stable schema-friendly token (not a free-text
            # message) so downstream consumers can pattern-match.
            return (True, "path_validation_failed")
        path = self._path()
        if not path.exists():
            return (False, None)
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return (False, None)
        if not isinstance(body, dict):
            return (False, None)
        until = _parse_iso(str(body.get("until_iso", "")))
        if until is None:
            return (False, None)
        if now >= until:
            return (False, None)
        reason = str(body.get("reason", "")) or "pause flag set"
        return (True, reason)

    def set(
        self,
        reason: str,
        hours: int,
        *,
        triggered_by: str = "operator",
        now: Optional[datetime] = None,
    ) -> None:
        """Write the pause flag with a deadline ``hours`` from now.

        Args:
            reason: Human-readable reason for the pause.
            hours: Pause window length (must be > 0).
            triggered_by: One of "operator", "circuit_breaker",
                "budget_exhausted_persistent".
            now: Override timestamp (for tests).

        Raises:
            ValueError: If ``hours <= 0`` or path-validation fails.
        """
        if not isinstance(hours, int) or hours <= 0:
            raise ValueError(f"hours must be positive int, got {hours!r}")
        self._validate()
        now = now or _utc_now()
        until = now + timedelta(hours=hours)
        body = {
            "reason": reason,
            "until_iso": _iso(until),
            "triggered_by": triggered_by,
            "triggered_at": _iso(now),
        }
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _atomic_write_json(path, body, indent=2)

    def clear(self) -> None:
        """Remove the pause flag (idempotent)."""
        try:
            self._validate()
        except ValueError:
            return
        path = self._path()
        try:
            if path.exists() and not path.is_symlink():
                path.unlink()
        except OSError:
            pass


# =============================================================================
# DrainHistory — append-only JSONL outcome log
# =============================================================================


@dataclass
class DrainHistory:
    """Append-only JSONL of drain outcomes.

    File: ``<repo_root>/.claude/local/drain_log.jsonl``. Read tolerates
    malformed lines (skips them); append is line-atomic via single ``write``.
    
    Optional fields that callers MAY include in records (Issue #1292):
    - ``revert_status``: one of "pending", "reverted", "not_needed". Default absent (legacy).
    - ``revert_sha``: SHA of the revert commit if revert_status == "reverted". Default absent.
    """

    repo_root: Path

    @classmethod
    def load(cls, repo_root: Path) -> "DrainHistory":
        return cls(repo_root=Path(repo_root).resolve())

    def append(self, record: Dict[str, Any]) -> None:
        """Append one JSONL record.

        The record is augmented with a ``timestamp`` field if not already set.
        Write failure propagates to the caller as ``OSError`` — callers that
        want non-fatal behavior should catch it themselves.
        
        Optional fields (Issue #1292):
        - ``revert_status``: one of "pending", "reverted", "not_needed"
        - ``revert_sha``: SHA of revert commit if reverted
        """
        path = _history_path(self.repo_root)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if "timestamp" not in record:
            record = {**record, "timestamp": _iso(_utc_now())}
        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    def read_all(self) -> List[Dict[str, Any]]:
        """Read every well-formed record. Malformed lines are skipped silently."""
        path = _history_path(self.repo_root)
        if not path.exists():
            return []
        out: List[Dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if isinstance(rec, dict):
                            out.append(rec)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except OSError:
            return []
        return out

    @classmethod
    def latest_pending_reverts(cls, repo_root: Path) -> List[Dict[str, Any]]:
        """Return records with outcome=success and revert_status=pending."""
        history = cls.load(repo_root)
        records = history.read_all()
        return [
            rec for rec in records
            if rec.get("outcome") == "success"
            and rec.get("revert_status") == "pending"
        ]


# =============================================================================
# Pure-function gate logic — operates on TriageFinding-shaped clusters + labels
# =============================================================================


# Soft labels that mean "wait/blocked"; skip the cluster (try next one).
SKIP_LABELS: frozenset[str] = frozenset({"blocked", "waiting"})


def severity_gate(cluster_severity: str) -> Tuple[bool, str]:
    """Block if cluster severity is NOT in :data:`AUTO_DRAINABLE_SEVERITY`.

    Args:
        cluster_severity: ``TriageFinding.severity`` ("low", "medium", "high").

    Returns:
        ``(blocked, reason)``. ``blocked=True`` → STOP.
    """
    sev = (cluster_severity or "").lower()
    if sev not in AUTO_DRAINABLE_SEVERITY:
        return (
            True,
            f"needs human review (severity={sev or 'unknown'})",
        )
    return (False, "")


def tag_gate(cluster_labels: frozenset[str]) -> Tuple[bool, str]:
    """Block if hydrated cluster labels intersect :data:`HUMAN_GATE_TAGS`.

    Args:
        cluster_labels: Union of label names across the cluster's issues
            (hydrated via :func:`drain_runner.hydrate_issue_labels`).

    Returns:
        ``(blocked, reason)``. ``blocked=True`` → STOP.
    """
    if not cluster_labels:
        return (False, "")
    hit = sorted(cluster_labels & HUMAN_GATE_TAGS)
    if hit:
        return (
            True,
            f"human-gated tag present: {', '.join(hit)}",
        )
    return (False, "")


def size_gate(cluster_size: int) -> Tuple[bool, str]:
    """Block if cluster size > :data:`MAX_CLUSTER_SIZE_AUTO_DRAINABLE`.

    Args:
        cluster_size: ``len(TriageFinding.issue_numbers)``.

    Returns:
        ``(blocked, reason)``. ``blocked=True`` → STOP.
    """
    if cluster_size > MAX_CLUSTER_SIZE_AUTO_DRAINABLE:
        return (
            True,
            f"cluster too compound (size={cluster_size}), "
            f"file as epic plan first",
        )
    return (False, "")


def skip_gate(cluster_labels: frozenset[str]) -> Tuple[bool, str]:
    """Should this cluster be skipped (try next) rather than STOPPED?

    Distinct from :func:`tag_gate`: a SKIP triggers the next-cluster iteration
    (up to 3 attempts), whereas tag_gate STOPs the drain entirely.

    Args:
        cluster_labels: Hydrated label set.

    Returns:
        ``(skip, reason)``. ``skip=True`` → try next cluster.
    """
    if not cluster_labels:
        return (False, "")
    hit = sorted(cluster_labels & SKIP_LABELS)
    if hit:
        return (True, f"cluster has soft skip label(s): {', '.join(hit)}")
    return (False, "")


def confidence_gate(cluster_confidence: float) -> Tuple[bool, str]:
    """Block if cluster confidence is below :data:`AUTO_DRAINABLE_CONFIDENCE_THRESHOLD`.

    ADR-002 Phase C (Issue #1291). Confidence is the autonomy decision:
    only clusters whose readiness-for-autonomy signal meets the threshold
    are eligible for autonomous drain. Severity remains in
    :func:`evaluate_cluster_gates` for impact-tier ranking but no longer
    drives the autonomy decision.

    Args:
        cluster_confidence: A float in ``[0.0, 1.0]`` derived from issue
            labels (``confidence:high|medium|low``) and issue-body quality
            heuristics (see :mod:`issue_triage_analyzer`).

    Returns:
        ``(blocked, reason)``. ``blocked=True`` → STOP.
    """
    try:
        conf = float(cluster_confidence)
    except (TypeError, ValueError):
        conf = 0.0
    if conf < AUTO_DRAINABLE_CONFIDENCE_THRESHOLD:
        return (
            True,
            f"confidence too low for autonomy "
            f"(confidence={conf:.2f} < threshold="
            f"{AUTO_DRAINABLE_CONFIDENCE_THRESHOLD:.2f})",
        )
    return (False, "")


def evaluate_cluster_gates(
    cluster_severity: str,
    cluster_size: int,
    cluster_labels: frozenset[str],
    cluster_confidence: float = 0.0,
) -> Tuple[str, str]:
    """Evaluate all STOP gates in priority order. Skip is separate.

    Order: severity → tag → size → confidence. First failure short-circuits.

    Per ADR-002 Phase C (Issue #1291), ``confidence_gate`` is the final
    eligibility check: severity stays in the ordering for ranking/impact-tier
    reporting, but ``confidence_gate`` is the autonomy decision.

    Args:
        cluster_severity: ``TriageFinding.severity``.
        cluster_size: Cluster size.
        cluster_labels: Hydrated label set.
        cluster_confidence: Readiness-for-autonomy signal in ``[0.0, 1.0]``.
            Defaults to ``0.0`` (blocks unless caller supplies a real value).

    Returns:
        ``(verdict, reason)`` where verdict is one of ``"pass"``, ``"stop"``.
        ``reason`` is empty when verdict is ``"pass"``.
    """
    blocked, reason = severity_gate(cluster_severity)
    if blocked:
        return ("stop", reason)
    blocked, reason = tag_gate(cluster_labels)
    if blocked:
        return ("stop", reason)
    blocked, reason = size_gate(cluster_size)
    if blocked:
        return ("stop", reason)
    blocked, reason = confidence_gate(cluster_confidence)
    if blocked:
        return ("stop", reason)
    return ("pass", "")


__all__ = [
    # Constants
    "MAX_DRAINS_PER_DAY",
    "MAX_WALL_SECONDS_PER_DAY",
    "CONSECUTIVE_FAIL_PAUSE_HOURS",
    "DAILY_FAIL_THRESHOLD",
    "LONG_PAUSE_HOURS",
    "MAX_CLUSTER_SIZE_AUTO_DRAINABLE",
    "HUMAN_GATE_TAGS",
    "AUTO_DRAINABLE_SEVERITY",
    "AUTO_DRAINABLE_CONFIDENCE_THRESHOLD",
    "SKIP_LABELS",
    # Classes
    "DrainBudget",
    "CircuitBreaker",
    "PauseFlag",
    "DrainHistory",
    # Gates
    "severity_gate",
    "tag_gate",
    "size_gate",
    "skip_gate",
    "confidence_gate",
    "evaluate_cluster_gates",
    # Path helpers (exposed for tests)
    "_budget_path",
    "_breaker_path",
    "_pause_flag_path",
    "_history_path",
]

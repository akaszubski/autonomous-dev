"""CIA Finding Store - Atomic, fail-open append of structured CIA findings.

The continuous-improvement-analyst (CIA) agent calls :func:`append_finding` to
emit a structured record per finding. Records are appended to monthly JSONL
files at ``.claude/logs/findings/YYYY-MM.jsonl`` (0600 perms, 0700 parent dir).

Design constraints:

* **Atomic appends**: a single ``fcntl.flock(LOCK_EX)`` window wraps each write
  so concurrent CIA invocations cannot interleave bytes within a line. The
  evidence field is allowed up to 2000 chars (exceeds POSIX PIPE_BUF=512 on
  macOS, so the lock is mandatory — Issue #992 precedent).
* **Fail-open**: every exception is caught. The CIA's report must surface the
  finding even if the store cannot persist it; a stderr breadcrumb is emitted.
* **Secret scrubbing**: ``title`` and ``evidence`` are scrubbed via the shared
  ``scrub_secrets`` from :mod:`runtime_data_aggregator` (CWE-532).
* **Log-injection defense**: CR/LF/TAB stripped from every string field
  (CWE-117), matching :func:`runtime_data_aggregator._sanitize_string`.
* **Path safety**: ``findings_dir`` MUST be absolute; symlinked monthly files
  are refused (CWE-59); path traversal is rejected.

GitHub Issue: #1200
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# fcntl is POSIX-only. On Windows it is absent; degrade gracefully — atomic
# byte-level interleaving is not a realistic concurrent-write threat on
# Windows for this telemetry surface.
try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

# Robust import of secret-scrubbing helper from runtime_data_aggregator —
# follows the project's two-step idiom (relative-then-absolute fallback) so
# the module works both as a package import and as a flat import.
try:
    from .runtime_data_aggregator import scrub_secrets  # type: ignore
except ImportError:
    _lib_dir = Path(__file__).parent.resolve()
    if str(_lib_dir) not in sys.path:
        sys.path.insert(0, str(_lib_dir))
    from runtime_data_aggregator import scrub_secrets  # type: ignore


# =============================================================================
# Constants
# =============================================================================

MAX_EVIDENCE_LENGTH: int = 2000
MAX_TITLE_LENGTH: int = 200
ALLOWED_SEVERITIES = frozenset({"info", "warning", "error"})
FILE_MODE: int = 0o600
DIR_MODE: int = 0o700

_DEFAULT_SEVERITY = "info"


# =============================================================================
# Internals
# =============================================================================


def _sanitize_string(text: str) -> str:
    """Strip CR/LF/TAB control characters (CWE-117 log-injection defense).

    Args:
        text: Raw string to sanitize.

    Returns:
        Sanitized string with control characters removed. Secrets are NOT
        scrubbed here — callers that handle untrusted text (``title``,
        ``evidence``) apply :func:`scrub_secrets` separately.
    """
    if not isinstance(text, str):
        text = str(text)
    return text.replace("\r", "").replace("\n", " ").replace("\t", " ")


def _normalize_record(
    record: Dict[str, Any],
    *,
    now: datetime,
) -> Dict[str, Any]:
    """Coerce and sanitize a finding record before write.

    Steps:
    1. Validate ``severity``; default to ``"info"`` + stderr warn if invalid.
    2. Clamp ``title`` to :data:`MAX_TITLE_LENGTH`, ``evidence`` to
       :data:`MAX_EVIDENCE_LENGTH` BEFORE secret scrubbing.
    3. Strip CR/LF/TAB from every string field.
    4. Scrub secrets from ``title`` and ``evidence``.
    5. Default missing ``ts`` to ``now.isoformat()``.

    Returns:
        A new dict — the input is not mutated. All seven required fields are
        present; extra fields are passed through verbatim (after string
        sanitization, if applicable).
    """
    normalized: Dict[str, Any] = {}

    # severity ----------------------------------------------------------------
    severity = record.get("severity", _DEFAULT_SEVERITY)
    if not isinstance(severity, str) or severity not in ALLOWED_SEVERITIES:
        try:
            sys.stderr.write(
                f"[cia-finding-store] invalid severity {severity!r}, "
                f"defaulting to {_DEFAULT_SEVERITY!r}\n"
            )
        except Exception:
            pass
        severity = _DEFAULT_SEVERITY
    normalized["severity"] = severity

    # root_cause_tag ----------------------------------------------------------
    raw_tag = record.get("root_cause_tag", "UNTAGGED")
    normalized["root_cause_tag"] = _sanitize_string(str(raw_tag))[:MAX_TITLE_LENGTH]

    # title (clamp first, then scrub) -----------------------------------------
    raw_title = str(record.get("title", ""))[:MAX_TITLE_LENGTH]
    normalized["title"] = scrub_secrets(_sanitize_string(raw_title))

    # evidence (clamp first, then scrub) --------------------------------------
    raw_evidence = str(record.get("evidence", ""))[:MAX_EVIDENCE_LENGTH]
    normalized["evidence"] = scrub_secrets(_sanitize_string(raw_evidence))

    # file_refs ---------------------------------------------------------------
    raw_refs = record.get("file_refs", [])
    if isinstance(raw_refs, (list, tuple)):
        normalized["file_refs"] = [
            _sanitize_string(str(ref))[:MAX_TITLE_LENGTH] for ref in raw_refs
        ]
    else:
        normalized["file_refs"] = []

    # session_id --------------------------------------------------------------
    normalized["session_id"] = _sanitize_string(
        str(record.get("session_id", "unknown"))
    )[:MAX_TITLE_LENGTH]

    # ts ----------------------------------------------------------------------
    raw_ts = record.get("ts")
    if isinstance(raw_ts, str) and raw_ts.strip():
        normalized["ts"] = _sanitize_string(raw_ts)[:MAX_TITLE_LENGTH]
    else:
        normalized["ts"] = now.isoformat()

    # Pass-through any extra fields (e.g. target_repo, sub_cluster) -----------
    reserved = {
        "severity", "root_cause_tag", "title", "evidence",
        "file_refs", "session_id", "ts",
    }
    for key, value in record.items():
        if key in reserved:
            continue
        if isinstance(value, str):
            normalized[key] = _sanitize_string(value)[:MAX_EVIDENCE_LENGTH]
        else:
            normalized[key] = value

    return normalized


def _safe_exc_repr(exc: BaseException) -> str:
    """Return a short, single-line representation of an exception for stderr."""
    try:
        return _sanitize_string(f"{type(exc).__name__}: {exc}")[:200]
    except Exception:
        return type(exc).__name__


# =============================================================================
# Public API
# =============================================================================


def append_finding(
    record: Dict[str, Any],
    *,
    findings_dir: Path,
    now: Optional[datetime] = None,
) -> bool:
    """Append a CIA finding to the monthly JSONL file.

    Args:
        record: Finding payload. Required fields: ``severity``, ``root_cause_tag``,
            ``title``, ``evidence``, ``file_refs``, ``session_id``, ``ts``.
            Missing fields are filled with safe defaults rather than rejected
            (fail-open). Extra fields are passed through verbatim.
        findings_dir: ABSOLUTE path to the findings root directory (typically
            ``<project_root>/.claude/logs/findings``). MUST be absolute — this
            enforces worktree safety. Relative paths raise ``ValueError``.
        now: Optional override for the current time (test seam). Defaults to
            ``datetime.now(timezone.utc)``.

    Returns:
        ``True`` on successful write; ``False`` on any failure (including path
        rejections and write errors). Failure is logged to stderr with the
        ``[cia-finding-store]`` prefix.

    Raises:
        ValueError: If ``findings_dir`` is not absolute. This is a programmer
            error — every other failure mode is fail-open.
    """
    if not isinstance(findings_dir, Path):
        findings_dir = Path(findings_dir)
    if not findings_dir.is_absolute():
        raise ValueError("findings_dir must be absolute")

    # Reject explicit ``..`` traversal. ``resolve()`` would also collapse it,
    # but an explicit check makes the intent unambiguous and avoids surprises
    # when the directory does not yet exist.
    if ".." in findings_dir.parts:
        try:
            sys.stderr.write(
                "[cia-finding-store] findings_dir contains '..' traversal; "
                "refusing write\n"
            )
        except Exception:
            pass
        return False

    if now is None:
        now = datetime.now(timezone.utc)

    try:
        normalized = _normalize_record(record, now=now)
        line = json.dumps(normalized, default=str, ensure_ascii=False)
    except Exception as exc:
        try:
            sys.stderr.write(
                f"[cia-finding-store] normalize_failed: {_safe_exc_repr(exc)}\n"
            )
        except Exception:
            pass
        return False

    try:
        findings_dir.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    except OSError as exc:
        try:
            sys.stderr.write(
                f"[cia-finding-store] mkdir_failed: {_safe_exc_repr(exc)}\n"
            )
        except Exception:
            pass
        return False

    monthly_filename = f"{now.strftime('%Y-%m')}.jsonl"
    log_path = findings_dir / monthly_filename

    # CWE-59: refuse to write through a symlink. Some attacker (or stale
    # state) could pre-create the monthly file as a symlink to /etc/passwd;
    # the secure opener honors O_NOFOLLOW only at file creation, but the
    # file already exists, so we check explicitly.
    try:
        if log_path.is_symlink():
            try:
                sys.stderr.write(
                    f"[cia-finding-store] symlinked monthly file refused: "
                    f"{log_path.name}\n"
                )
            except Exception:
                pass
            return False
    except OSError as exc:
        try:
            sys.stderr.write(
                f"[cia-finding-store] symlink_check_failed: {_safe_exc_repr(exc)}\n"
            )
        except Exception:
            pass
        return False

    def _secure_opener(path: str, flags: int) -> int:
        # Set mode at file-creation time so newly created files are tight
        # from the first byte (Issue #1056 precedent in hook_timing.py:294).
        return os.open(path, flags, FILE_MODE)

    try:
        with open(log_path, "a", encoding="utf-8", opener=_secure_opener) as fh:
            # Backstop tighten perms in case the file pre-existed with looser
            # permissions. Swallow chmod failures — telemetry must not block
            # the host on a perm-tightening attempt.
            try:
                os.chmod(log_path, FILE_MODE)
            except OSError:
                pass

            # Exclusive advisory lock — required because evidence may exceed
            # PIPE_BUF (512B on macOS, 4KB on Linux), making torn lines under
            # concurrent appends possible without the lock (Issue #992).
            locked = False
            if fcntl is not None:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                    locked = True
                except OSError:
                    # NFS or unsupported FS may refuse flock; degrade to a
                    # bare append rather than raise.
                    locked = False
            try:
                fh.write(line + "\n")
            finally:
                if locked and fcntl is not None:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
        return True
    except OSError as exc:
        try:
            sys.stderr.write(
                f"[cia-finding-store] {line} (write_failed: {_safe_exc_repr(exc)})\n"
            )
        except Exception:
            pass
        return False
    except Exception as exc:  # pragma: no cover - last-resort guard
        try:
            sys.stderr.write(
                f"[cia-finding-store] {line} (unexpected_error: {_safe_exc_repr(exc)})\n"
            )
        except Exception:
            pass
        return False

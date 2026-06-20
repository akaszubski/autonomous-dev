#!/usr/bin/env python3
"""Session-mode artifact writer (Issue #998 — Phase D).

Phase D wires the intent classifier (Phase 1, Issue #971) to a per-session
JSON artifact at ``/tmp/session_mode_<sha256(session_id)[:8]>.json``. The
artifact is written from the ``UserPromptSubmit`` hook in observe mode. Phase
E will read this artifact from PreToolUse hooks to gate routing decisions.

Design (decision: option (b) — separate per-session file):
    - O(1) lookup vs activity-log scan: hot path PreToolUse hooks must read
      the current session mode without parsing JSONL.
    - Atomic single-source-of-truth: last-writer-wins via os.replace().
    - Schema isolation from telemetry: telemetry is append-only JSONL;
      session-mode is overwrite-style "current-state" snapshot.
    - Hot-path read latency: a single JSON file in /tmp is faster than
      walking a daily activity log.

Schema (12 fields — see write_session_mode docstring for details):
    schema_version, session_id, intent_class, confidence, regex_hit,
    llm_used, fail_open, requires_security_audit, prompt_hash,
    written_at, expires_at, enforce_mode

Phase E migration note:
    If Phase E expands the mode taxonomy (e.g. adds "TIER" or
    "SAFE_MODE" fields), bump SCHEMA_VERSION to 2 and add a reader-side
    migration shim so v1 artifacts continue to be readable for the TTL
    window. NEVER reuse field names with new semantics.

Reference pattern (read-only):
    plugins/autonomous-dev/lib/pipeline_completion_state.py — same
    /tmp/{prefix}_{sha256[:8]}.json layout, fail-open conventions.

Fail-open contract:
    write_session_mode() MUST NEVER raise. Every exception path swallows
    silently and returns None. The observe-mode goal is byte-identical
    behavior when the artifact write fails — downstream hooks must not
    notice writer failures.

Issue: #998 (Phase D — observe-mode wiring of intent classifier).
Issue: #999 (Phase E — adds reader-side helpers consumed by hooks).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "SCHEMA_VERSION",
    "TTL_SECONDS",
    "write_session_mode",
    "read_session_mode",
    "should_pipeline_enforce",
    "update_session_mode_partial",
    "effective_intent_class",
    "get_user_msg_token",
]

# Issue #1263: max chars of user prompt text persisted into the artifact.
# The token is sha256(user_prompt_text)[:16], so a moderate cap keeps the
# artifact small while still discriminating across user turns.
_USER_PROMPT_TEXT_MAX_CHARS = 1000

# Issue #1024 (M2): allowlist of fields update_session_mode_partial may set.
# A closed allowlist is the safe direction — it forces the writer to fail when
# a typo or unknown key is passed, rather than silently mutating the artifact
# with a field that no reader honors. Forward-compat: extend this set when a
# new field is introduced; do NOT replace it with **kwargs passthrough.
_PARTIAL_UPDATE_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "clarification_asked",
        "clarified_intent",
    }
)

# Schema version — bump when fields are added/renamed/removed (Phase E note).
SCHEMA_VERSION: int = 1

# Artifact lifetime in seconds. Readers MUST honor expires_at and treat
# expired artifacts as missing. 1 hour aligns with pipeline_completion_state's
# STALE_UNKNOWN_TTL_SECONDS so a stale prior session does not bleed into a
# fresh pipeline run.
TTL_SECONDS: int = 3600


def _resolve_session_id(session_id: Any) -> str:
    """Resolve a session id to a non-colliding string.

    The hook reads ``CLAUDE_SESSION_ID`` from the environment and falls back
    to ``"unknown"`` when unset. Two unrelated processes sharing the unknown
    fallback would write to the same artifact path — defeating the
    single-source-of-truth contract. Append the PID to disambiguate.

    Args:
        session_id: The raw value (may be ``None``, empty, or ``"unknown"``).

    Returns:
        A non-empty session id string. The PID-suffixed fallback form is
        ``f"unknown_{os.getpid()}"``.
    """
    if not isinstance(session_id, str):
        return f"unknown_{os.getpid()}"
    if session_id == "" or session_id == "unknown":
        return f"unknown_{os.getpid()}"
    return session_id


def _session_mode_path(session_id: Any) -> Path:
    """Compute the artifact path for a given session.

    The path lives under ``/tmp/`` to match the convention in
    ``pipeline_completion_state.py``. The 8-char SHA-256 prefix avoids
    leaking the raw session id in filesystem listings while keeping
    collision probability negligible (16^8 = ~4.3B namespace).

    Args:
        session_id: The session id (or unknown sentinel) to hash.

    Returns:
        Absolute Path under ``/tmp/`` of the form
        ``/tmp/session_mode_<8-hex>.json``.
    """
    resolved = _resolve_session_id(session_id)
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:8]
    return Path(f"/tmp/session_mode_{digest}.json")


def _atomic_write(path: Path, payload: dict) -> None:
    """Atomically write a JSON payload to ``path``.

    Uses ``tempfile.mkstemp`` with ``dir=path.parent`` so the temp file
    lives on the same filesystem as the final destination — this is the
    same-fs precondition for ``os.replace()`` atomicity. Without this
    precondition, ``os.replace`` may fall back to copy semantics on some
    platforms and lose atomicity guarantees under concurrent writers.

    Args:
        path: Final destination path.
        payload: JSON-serializable dict to write.

    Raises:
        OSError: On any I/O failure. Callers MUST catch — this function
            does not swallow because lower-level helpers should signal
            failure to the writer; only the public ``write_session_mode``
            performs fail-open swallowing.
    """
    parent = path.parent
    fd, tmp_name = tempfile.mkstemp(
        prefix=".session_mode_",
        suffix=".json.tmp",
        dir=str(parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"))
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # fsync may legitimately fail on /tmp on some platforms
                # (e.g. tmpfs without backing). Atomicity for replace()
                # does not require a successful fsync — proceed.
                pass
        os.replace(tmp_name, path)
        tmp_name = ""  # mark as moved so finally-cleanup skips unlink
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def write_session_mode(
    session_id: Any,
    intent_result: Any,
    prompt: str,
) -> None:
    """Atomically write the session-mode artifact. NEVER raises.

    The artifact is the single source of truth for "what is this session
    doing right now?" — Phase E hooks will read this to decide whether to
    relax non-security routing checks.

    Schema (all 12 fields are always present):
        schema_version (int): SCHEMA_VERSION at write time.
        session_id (str): Resolved session id (PID-suffixed for unknown).
        intent_class (str): One of IntentClass.value strings — e.g.
            "implement", "security_critical", "ambiguous".
        confidence (float): IntentResult.confidence in [0.0, 1.0].
        regex_hit (bool): Whether the security-keyword regex matched.
        llm_used (bool): Whether the LLM was invoked (regex_hit short-
            circuits, so regex_hit and llm_used are mutually exclusive
            in practice).
        fail_open (bool): Whether the classifier hit a fail-open path
            (timeout, malformed JSON, low confidence, etc.).
        requires_security_audit (bool): Whether downstream hooks MUST
            preserve security-critical routing checks.
        prompt_hash (str): ``sha256(prompt)[:16]`` — 16-char hex digest
            of the original prompt. Allows correlation across logs
            without storing prompt text.
        written_at (str): ISO 8601 UTC timestamp of the write.
        expires_at (int): Unix epoch seconds at which readers MUST treat
            the artifact as missing.
        enforce_mode (bool): Phase D plumbs but does NOT use the
            ``INTENT_CLASSIFIER_ENFORCE`` env flag. Phase E will read this
            field to decide whether to gate or just observe.

    Args:
        session_id: Raw session id (may be None, empty, or "unknown").
        intent_result: An IntentResult-shaped object exposing
            ``.intent.value``, ``.confidence``, ``.regex_hit``,
            ``.llm_used``, ``.fail_open``, ``.requires_security_audit``.
            Duck-typed: any object with these attributes works.
        prompt: The original user prompt text. Hashed via SHA-256;
            never stored in the artifact verbatim.

    Returns:
        None. Failures are swallowed silently.
    """
    try:
        # Read the enforce flag at write time so Phase E sees the same
        # value the writer saw. Defaulted to false in observe mode.
        enforce_mode = (
            os.environ.get("INTENT_CLASSIFIER_ENFORCE", "false").lower() == "true"
        )

        # Build the prompt hash defensively — None / non-str inputs hash
        # the empty string rather than raising.
        if isinstance(prompt, str):
            prompt_bytes = prompt.encode("utf-8")
        else:
            prompt_bytes = b""
        prompt_hash = hashlib.sha256(prompt_bytes).hexdigest()[:16]

        # Pull fields off the IntentResult-shaped object. AttributeError
        # here is caught by the outer try; the artifact is simply not
        # written.
        intent_class = intent_result.intent.value
        confidence = float(intent_result.confidence)
        regex_hit = bool(intent_result.regex_hit)
        llm_used = bool(intent_result.llm_used)
        fail_open = bool(intent_result.fail_open)
        requires_security_audit = bool(intent_result.requires_security_audit)

        now = datetime.now(timezone.utc)
        written_at = now.isoformat()
        expires_at = int(now.timestamp()) + TTL_SECONDS

        resolved_session_id = _resolve_session_id(session_id)

        # 14 fields (12 original + 2 added in Issue #1024 M2):
        # `clarification_asked` / `clarified_intent` are additive optional
        # fields used by the AskUserQuestion round-trip on AMBIGUOUS
        # classifications. They are SET to default values on every write so
        # readers can rely on `mode.get("clarified_intent")` returning a
        # well-defined value rather than KeyError. SCHEMA_VERSION stays at 1
        # because the additions are strictly additive.
        # Issue #1263: persist a truncated prompt copy so the router can
        # derive a content-addressed fire-once-per-turn token. The field is
        # additive — SCHEMA_VERSION stays at 1. Readers MUST use
        # ``data.get("user_prompt_text")`` because older artifacts wrote
        # before this field existed.
        if isinstance(prompt, str):
            user_prompt_text = prompt[:_USER_PROMPT_TEXT_MAX_CHARS]
        else:
            user_prompt_text = None

        payload = {
            "schema_version": SCHEMA_VERSION,
            "session_id": resolved_session_id,
            "intent_class": intent_class,
            "confidence": confidence,
            "regex_hit": regex_hit,
            "llm_used": llm_used,
            "fail_open": fail_open,
            "requires_security_audit": requires_security_audit,
            "prompt_hash": prompt_hash,
            "written_at": written_at,
            "expires_at": expires_at,
            "enforce_mode": enforce_mode,
            "clarification_asked": False,
            "clarified_intent": None,
            "user_prompt_text": user_prompt_text,
        }

        path = _session_mode_path(session_id)
        _atomic_write(path, payload)
    except Exception:
        # Fail-open contract: any failure (OSError, AttributeError,
        # TypeError, ValueError, ...) MUST be swallowed. Phase D is
        # observe-mode only — a failed write MUST NOT change downstream
        # behavior. Phase E will add reader-side fail-open as well.
        return None


# ---------------------------------------------------------------------------
# Phase E (Issue #999) — reader-side helpers
# ---------------------------------------------------------------------------

# Intent classes for which Phase E session-mode logic should SKIP (relax) the
# non-security routing checks. Other classes — including unknown values —
# default to enforce. This is the safe direction: when in doubt, enforce.
_SKIP_INTENT_CLASSES: frozenset[str] = frozenset(
    {
        "doc",
        "config",
        "typo",
        "status_query",
        "conversation",
        # Issue #1023 — non-SWE classes (no pipeline gates).
        "exploration",
        "triage",
        "remote_ops",
        "scratch",
    }
)


def read_session_mode(session_id: Any) -> dict | None:
    """Read the session-mode artifact for a session. NEVER raises.

    Returns the parsed dict on success, or ``None`` for any of:
        - Missing artifact file
        - Stale (current time > ``expires_at``)
        - Schema version mismatch (artifact's ``schema_version`` !=
          :data:`SCHEMA_VERSION`)
        - Malformed JSON / wrong top-level type
        - Any I/O error

    The reader uses the same path resolution as :func:`write_session_mode` so
    a writer/reader pair on the same session id always agrees on the artifact
    location. Stale artifacts are treated as missing because an expired
    session-mode signal could mis-route a fresh, unrelated session.

    Args:
        session_id: Raw session id (may be ``None``, empty, or ``"unknown"``).

    Returns:
        Parsed artifact dict on success, ``None`` otherwise.
    """
    try:
        path = _session_mode_path(session_id)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError, TypeError):
            return None
        if not isinstance(data, dict):
            return None

        # Schema version gate — fail-closed on mismatch.
        if data.get("schema_version") != SCHEMA_VERSION:
            return None

        # Staleness gate.
        expires_at = data.get("expires_at")
        if not isinstance(expires_at, (int, float)):
            return None
        if time.time() > expires_at:
            return None

        return data
    except Exception:
        # Fail-open contract: any unexpected failure → None. Phase E hooks
        # treat None as "no signal — enforce normally".
        return None


def should_pipeline_enforce(intent_class: Any) -> bool:
    """Return True iff pipeline gates SHOULD run for this intent class.

    Decision table (case-insensitive):

    +------------------------+----------+
    | intent_class            | enforce |
    +========================+==========+
    | implement              | True     |
    | refactor               | True     |
    | security_critical      | True     |
    | ambiguous              | True     |
    | test                   | True     |
    | doc                    | False    |
    | config                 | False    |
    | typo                   | False    |
    | status_query           | False    |
    | conversation           | False    |
    | exploration            | False    |
    | triage                 | False    |
    | remote_ops             | False    |
    | scratch                | False    |
    | unknown / non-string   | True (fail-safe) |
    +------------------------+----------+

    The default-True branch is the safe direction: when the classifier returns
    a value the gate does not recognize, we keep enforcing rather than
    silently disabling.

    Args:
        intent_class: The ``intent_class`` string from a session-mode artifact.
            Non-string inputs return True (fail-safe).

    Returns:
        ``True`` if pipeline gates should run, ``False`` if they should skip.
    """
    if not isinstance(intent_class, str):
        return True
    return intent_class.strip().lower() not in _SKIP_INTENT_CLASSES


# ---------------------------------------------------------------------------
# Issue #1024 (M2) — partial-update helper + effective intent class
# ---------------------------------------------------------------------------


def update_session_mode_partial(session_id: Any, **fields: Any) -> bool:
    """Atomically merge new fields into an existing session-mode artifact.

    This is the helper that backs the AskUserQuestion round-trip on
    AMBIGUOUS classifications (Issue #1024). The hook layer asks the user
    to disambiguate, and the persisted answer flips the enforcement gate
    by setting ``clarified_intent`` on the existing artifact.

    Contract:
        - Read-modify-write semantics. The full payload is read, the
          allowed fields from ``**fields`` are merged in, and the result
          is atomically written via :func:`_atomic_write`.
        - If the artifact is missing or stale, no file is created and
          ``False`` is returned. We do NOT lazily create artifacts here —
          that is the writer's job, and a missing artifact in this code
          path means the round-trip fired late or the session has rolled
          over to a new prompt.
        - Unknown keys in ``**fields`` are silently filtered out. This is
          forward-compat: callers in older deploys may pass new fields
          this version does not yet recognize. We never raise on unknown
          keys.
        - NEVER raises. Any I/O / serialization failure returns ``False``.
        - Last-writer-wins under concurrent access (the same atomic
          replace contract as :func:`write_session_mode`).

    Args:
        session_id: Raw session id (may be ``None``, empty, or
            ``"unknown"`` — same resolution rules as the writer).
        **fields: Field updates. Only keys in
            :data:`_PARTIAL_UPDATE_ALLOWED_FIELDS` are honored. Unknown
            keys are silently filtered out.

    Returns:
        ``True`` if the artifact was successfully read and rewritten with
        at least one allowed field updated. ``False`` if the artifact was
        missing/stale, no allowed fields were passed, or any I/O error
        occurred.
    """
    try:
        # Read the current state. Returns None for missing/stale/malformed.
        mode = read_session_mode(session_id)
        if mode is None:
            return False

        # Filter to allowed fields. Unknown keys are silently ignored
        # (forward-compat). If no allowed fields were passed, no-op.
        filtered = {
            k: v
            for k, v in fields.items()
            if k in _PARTIAL_UPDATE_ALLOWED_FIELDS
        }
        if not filtered:
            return False

        # Merge — preserve all existing keys, overwrite only filtered ones.
        merged = dict(mode)
        merged.update(filtered)

        # Atomic write back to the same path the reader would consult.
        path = _session_mode_path(session_id)
        _atomic_write(path, merged)
        return True
    except Exception:
        # Fail-open contract: never raise. The round-trip persistence is
        # best-effort — if it fails, downstream readers will see no
        # `clarified_intent` and AMBIGUOUS pessimism remains in effect.
        return False


def effective_intent_class(mode: dict | None) -> str | None:
    """Return the intent class to act on, honoring user clarification.

    When the user has disambiguated an AMBIGUOUS classification via
    AskUserQuestion (Issue #1024 M2), ``mode["clarified_intent"]`` holds
    the user-supplied value. Callers should prefer that over the
    classifier's ``intent_class`` because the user has overridden the
    classifier's uncertainty.

    Args:
        mode: The session-mode artifact dict, or ``None`` if there was no
            artifact. ``None`` propagates straight through.

    Returns:
        The clarified intent if set (a non-empty string), otherwise the
        original ``intent_class`` field. ``None`` if ``mode`` is ``None``
        or both fields are absent.
    """
    if mode is None:
        return None
    clarified = mode.get("clarified_intent")
    if isinstance(clarified, str) and clarified:
        return clarified
    return mode.get("intent_class")


# ---------------------------------------------------------------------------
# Issue #1263 — content-addressed user-message token for SWE router
# ---------------------------------------------------------------------------


def get_user_msg_token(session_id: Any) -> str | None:
    """Return a content-addressed token for fire-once-per-turn deduplication.

    The token is derived from the session-mode artifact's ``user_prompt_text``
    field (16-hex-char SHA-256 prefix). Two consecutive PreToolUse events
    within the same user turn share the same token, so the router can dedupe.
    A fresh prompt produces a different token, allowing the router to fire
    again.

    Forward-compat fallback: if the artifact predates Issue #1263 (no
    ``user_prompt_text`` field), fall back to the existing ``prompt_hash``
    field. Only the leading 16 hex chars are returned so all token forms
    are comparable.

    NEVER raises.

    Args:
        session_id: Raw session id (may be ``None``, empty, or ``"unknown"``).

    Returns:
        16-char hex token (string), or ``None`` if:
            - The artifact is missing/stale/malformed.
            - Neither ``user_prompt_text`` nor ``prompt_hash`` is populated.
            - Any unexpected error occurs.
    """
    try:
        data = read_session_mode(session_id)
        if data is None:
            return None
        user_prompt = data.get("user_prompt_text")
        if isinstance(user_prompt, str) and user_prompt:
            return hashlib.sha256(
                user_prompt.encode("utf-8", errors="ignore")
            ).hexdigest()[:16]
        prompt_hash = data.get("prompt_hash")
        if isinstance(prompt_hash, str) and prompt_hash:
            return prompt_hash[:16] if len(prompt_hash) >= 16 else prompt_hash
        return None
    except Exception:
        return None

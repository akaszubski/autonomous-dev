#!/usr/bin/env python3
"""Persist a user's AskUserQuestion answer onto the session-mode artifact.

Issue #1024 (M2) — AskUserQuestion round-trip on AMBIGUOUS classification.

Workflow:
    1. The intent classifier returns ``IntentClass.AMBIGUOUS`` for a prompt.
    2. The ``UserPromptSubmit`` hook (``unified_prompt_validator.py``) emits
       an ``additionalContext`` block instructing Claude to call
       ``AskUserQuestion`` with the seven canonical intent options.
    3. Claude resolves the question and runs THIS script to persist the
       answer onto the session-mode artifact.
    4. The next ``PreToolUse`` hook reads ``clarified_intent`` and the
       enforcement gate honors the user's disambiguation
       (``enforcement_decision.py`` Priority 4.5).

Interface:
    python persist_intent_answer.py --session-id <id> --intent <class>

    --intent must be one of (lowercase, exact match):
        implement, refactor, test, doc, config, status_query, exploration

    SECURITY_CRITICAL, AMBIGUOUS, and any other value are REJECTED with
    exit 1 and a stderr message. SECURITY_CRITICAL specifically must
    never be user-selectable here because it comes from the regex
    pre-gate, not from AMBIGUOUS round-trips.

Exit codes:
    0 — Success, OR silent fail-open: the artifact was missing or stale
        (e.g. the round-trip fired late, the session has rolled over to a
        new prompt). Treating this as success preserves the contract that
        the round-trip is best-effort: a missing artifact simply means
        AMBIGUOUS pessimism remains in effect, which is the safe default.
    1 — Validation failure: ``--intent`` was not in the allowed set, or
        argparse rejected the args.

The script NEVER raises an unhandled exception; any I/O / serialization
error is swallowed and exit 0 is returned (silent fail-open). Validation
failures use exit 1 because they are programmer errors that the caller
must fix.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Library discovery (mirrors plugins/autonomous-dev/hooks/* pattern)
# ---------------------------------------------------------------------------

def _find_lib_dir() -> Optional[Path]:
    """Find the plugins/autonomous-dev/lib directory.

    Searches the same candidate roots as ``unified_prompt_validator.py``'s
    ``find_lib_dir``, so this script works in dev, marketplace, and global
    installs without configuration.
    """
    candidates = [
        # Relative to this file: scripts/ -> ../lib
        Path(__file__).resolve().parent.parent / "lib",
        # Project root (running from repo)
        Path.cwd() / "plugins" / "autonomous-dev" / "lib",
        # Global install
        Path.home() / ".autonomous-dev" / "lib",
        # Marketplace
        Path.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


_LIB_DIR = _find_lib_dir()
if _LIB_DIR is not None and str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))


# ---------------------------------------------------------------------------
# Allowed intent values
# ---------------------------------------------------------------------------
#
# These are the seven canonical user-selectable classes the AskUserQuestion
# template offers. Defined here as a small literal so we don't transitively
# require importing intent_classifier (which pulls in the full GenAI bridge)
# for argument validation. Tests cross-check this set against
# IntentClass to prevent drift.

_ALLOWED_INTENTS: List[str] = [
    "implement",
    "refactor",
    "test",
    "doc",
    "config",
    "status_query",
    "exploration",
]

# Intents that MUST be rejected even if a caller tries to pass them. Listed
# explicitly so the rejection is intentional rather than incidental:
#   - security_critical: comes from regex pre-gate, never user-supplied.
#   - ambiguous: that is the state the round-trip is trying to resolve;
#     persisting it back would be a no-op or worse, a loop.
_FORBIDDEN_INTENTS: frozenset[str] = frozenset(
    {"security_critical", "ambiguous"}
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for this CLI."""
    parser = argparse.ArgumentParser(
        prog="persist_intent_answer",
        description=(
            "Persist a user's AskUserQuestion answer onto the session-mode "
            "artifact (Issue #1024 M2)."
        ),
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="The session id of the prompt being clarified.",
    )
    parser.add_argument(
        "--intent",
        required=True,
        help=(
            "The user-selected intent class. Must be one of: "
            + ", ".join(_ALLOWED_INTENTS)
        ),
    )
    return parser


def _validate_intent(value: str) -> Optional[str]:
    """Return None if the value is allowed; otherwise an error message."""
    if not isinstance(value, str):
        return "intent must be a string"
    normalized = value.strip().lower()
    if normalized in _FORBIDDEN_INTENTS:
        return (
            f"intent {normalized!r} is not user-selectable. "
            f"SECURITY_CRITICAL comes from the regex pre-gate; "
            f"AMBIGUOUS is the state being resolved."
        )
    if normalized not in _ALLOWED_INTENTS:
        return (
            f"intent {value!r} is not in the allowed set. "
            f"Allowed: {sorted(_ALLOWED_INTENTS)}"
        )
    return None


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point.

    Args:
        argv: Optional argv list (default: ``sys.argv[1:]``). Tests pass
            this directly to avoid touching ``sys.argv``.

    Returns:
        0 on success or silent fail-open. 1 on validation failure.
    """
    parser = _build_parser()
    # parse_args exits 2 on argparse failure — translate to 1 to match the
    # contract documented in the module docstring.
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse uses exit code 2 by default; we promise exit 1 for
        # validation failures.
        return 1 if exc.code != 0 else 0

    err = _validate_intent(args.intent)
    if err is not None:
        print(f"persist_intent_answer: {err}", file=sys.stderr)
        return 1

    session_id = args.session_id
    if not isinstance(session_id, str) or not session_id.strip():
        print(
            "persist_intent_answer: --session-id must be non-empty",
            file=sys.stderr,
        )
        return 1

    normalized_intent = args.intent.strip().lower()

    # Import here so argparse failures don't pull in the full library.
    try:
        from session_mode import update_session_mode_partial  # type: ignore[import-not-found]
    except ImportError as exc:
        # Library missing — silent fail-open. The round-trip is best-effort.
        print(
            f"persist_intent_answer: session_mode unavailable ({exc}); "
            f"silent fail-open",
            file=sys.stderr,
        )
        return 0

    try:
        ok = update_session_mode_partial(
            session_id,
            clarified_intent=normalized_intent,
            clarification_asked=True,
        )
    except Exception as exc:  # noqa: BLE001 — fail-open contract
        # Should not happen — update_session_mode_partial NEVER raises —
        # but defend against future drift.
        print(
            f"persist_intent_answer: update raised ({exc}); silent fail-open",
            file=sys.stderr,
        )
        return 0

    if not ok:
        # Artifact missing/stale — silent fail-open. AMBIGUOUS pessimism
        # remains in effect, which is the safe default.
        print(
            "persist_intent_answer: artifact missing or stale; "
            "silent fail-open (AMBIGUOUS pessimism remains in effect)",
            file=sys.stderr,
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

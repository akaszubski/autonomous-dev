"""Tests for session_mode clarification helpers (Issue #1024 — M2).

Covers ``update_session_mode_partial`` and ``effective_intent_class``,
the two helpers that back the AskUserQuestion round-trip on AMBIGUOUS
classifications.

The fixture cleanup is paranoid: each test creates a unique session id
and unlinks the artifact in a finally block so a single failure does not
poison subsequent tests.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

# Add lib to path so we can import session_mode.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_PATH) not in sys.path:
    sys.path.insert(0, str(_LIB_PATH))

from session_mode import (  # noqa: E402
    SCHEMA_VERSION,
    _PARTIAL_UPDATE_ALLOWED_FIELDS,
    _session_mode_path,
    effective_intent_class,
    read_session_mode,
    update_session_mode_partial,
    write_session_mode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_intent_result(
    *,
    intent_value: str = "ambiguous",
    confidence: float = 0.4,
    regex_hit: bool = False,
    llm_used: bool = True,
    fail_open: bool = True,
    requires_security_audit: bool = True,
) -> Any:
    """Build a duck-typed IntentResult mirroring the real one's shape."""
    return SimpleNamespace(
        intent=SimpleNamespace(value=intent_value),
        confidence=confidence,
        regex_hit=regex_hit,
        llm_used=llm_used,
        fail_open=fail_open,
        requires_security_audit=requires_security_audit,
    )


def _cleanup(session_id: str) -> None:
    try:
        _session_mode_path(session_id).unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# update_session_mode_partial
# ---------------------------------------------------------------------------


class TestUpdateSessionModePartial:
    """Behavioral tests for the partial-update helper."""

    def test_partial_update_sets_clarified_intent(self) -> None:
        """clarified_intent merges into the artifact and survives roundtrip."""
        sid = "test-cm-clarified-intent"
        _cleanup(sid)
        try:
            write_session_mode(sid, _make_intent_result(), "ambiguous prompt")
            ok = update_session_mode_partial(sid, clarified_intent="implement")
            assert ok is True

            mode = read_session_mode(sid)
            assert mode is not None
            assert mode["clarified_intent"] == "implement"
        finally:
            _cleanup(sid)

    def test_partial_update_sets_clarification_asked(self) -> None:
        """clarification_asked merges into the artifact."""
        sid = "test-cm-asked"
        _cleanup(sid)
        try:
            write_session_mode(sid, _make_intent_result(), "x")
            ok = update_session_mode_partial(sid, clarification_asked=True)
            assert ok is True

            mode = read_session_mode(sid)
            assert mode is not None
            assert mode["clarification_asked"] is True
        finally:
            _cleanup(sid)

    def test_partial_update_preserves_existing_fields(self) -> None:
        """Merging clarified_intent must not touch any other field."""
        sid = "test-cm-preserve"
        _cleanup(sid)
        try:
            write_session_mode(
                sid,
                _make_intent_result(
                    intent_value="ambiguous",
                    confidence=0.3,
                    regex_hit=False,
                    llm_used=True,
                    fail_open=True,
                    requires_security_audit=True,
                ),
                "the original prompt",
            )
            before = read_session_mode(sid)
            assert before is not None

            update_session_mode_partial(sid, clarified_intent="doc")

            after = read_session_mode(sid)
            assert after is not None

            # All fields except the two new ones are byte-identical.
            for k in (
                "schema_version",
                "session_id",
                "intent_class",
                "confidence",
                "regex_hit",
                "llm_used",
                "fail_open",
                "requires_security_audit",
                "prompt_hash",
                "written_at",
                "expires_at",
                "enforce_mode",
            ):
                assert before[k] == after[k], f"field {k!r} changed unexpectedly"

            # The new field is set.
            assert after["clarified_intent"] == "doc"
        finally:
            _cleanup(sid)

    def test_partial_update_atomic_write(self) -> None:
        """The helper goes through tempfile.mkstemp + os.replace — atomic."""
        sid = "test-cm-atomic"
        _cleanup(sid)
        try:
            write_session_mode(sid, _make_intent_result(), "x")

            mkstemp_calls = {"count": 0}
            replace_calls = {"count": 0}

            original_mkstemp = tempfile.mkstemp
            original_replace = os.replace

            def spy_mkstemp(*args, **kwargs):
                mkstemp_calls["count"] += 1
                return original_mkstemp(*args, **kwargs)

            def spy_replace(src, dst):
                replace_calls["count"] += 1
                return original_replace(src, dst)

            with patch("session_mode.tempfile.mkstemp", side_effect=spy_mkstemp):
                with patch("session_mode.os.replace", side_effect=spy_replace):
                    ok = update_session_mode_partial(
                        sid, clarified_intent="implement"
                    )
                    assert ok is True

            assert mkstemp_calls["count"] == 1, (
                "atomic write should call mkstemp exactly once on update"
            )
            assert replace_calls["count"] == 1, (
                "atomic write should call os.replace exactly once on update"
            )
        finally:
            _cleanup(sid)

    def test_partial_update_returns_false_on_missing_artifact(self) -> None:
        """No artifact → returns False, no file created."""
        sid = "test-cm-missing"
        _cleanup(sid)
        # Confirm the file truly doesn't exist.
        assert not _session_mode_path(sid).exists()

        ok = update_session_mode_partial(sid, clarified_intent="implement")
        assert ok is False
        # No file was lazily created.
        assert not _session_mode_path(sid).exists()

    def test_partial_update_returns_false_on_stale_artifact(self) -> None:
        """A stale artifact reads as None → partial update returns False."""
        sid = "test-cm-stale"
        _cleanup(sid)
        try:
            write_session_mode(sid, _make_intent_result(), "x")
            # Force the artifact to look stale by overwriting expires_at.
            path = _session_mode_path(sid)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["expires_at"] = 0  # Unix epoch — definitely in the past
            path.write_text(json.dumps(data), encoding="utf-8")

            ok = update_session_mode_partial(sid, clarified_intent="implement")
            assert ok is False, (
                "stale artifacts read as None — partial update must not "
                "succeed against a stale read"
            )
        finally:
            _cleanup(sid)

    def test_partial_update_handles_concurrent_writers(self) -> None:
        """Concurrent partial updates → file remains valid JSON, last wins."""
        sid = "test-cm-concurrent"
        _cleanup(sid)
        try:
            write_session_mode(sid, _make_intent_result(), "x")
            errors: list[BaseException] = []

            def worker(value: str) -> None:
                try:
                    for _ in range(15):
                        update_session_mode_partial(
                            sid, clarified_intent=value
                        )
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            t1 = threading.Thread(target=worker, args=("implement",))
            t2 = threading.Thread(target=worker, args=("doc",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            assert errors == [], f"concurrent updaters raised: {errors}"

            mode = read_session_mode(sid)
            assert mode is not None
            assert mode["clarified_intent"] in ("implement", "doc")
            # Schema invariants survive.
            assert mode["schema_version"] == SCHEMA_VERSION
        finally:
            _cleanup(sid)

    def test_partial_update_unknown_kwargs_ignored(self) -> None:
        """Unknown kwargs are silently filtered out (forward-compat)."""
        sid = "test-cm-unknown"
        _cleanup(sid)
        try:
            write_session_mode(sid, _make_intent_result(), "x")
            # Pass an unknown key alongside an allowed key. The allowed key
            # must apply; the unknown key must be ignored without raising.
            ok = update_session_mode_partial(
                sid,
                clarified_intent="implement",
                a_field_that_does_not_exist="garbage",  # noqa
            )
            assert ok is True

            mode = read_session_mode(sid)
            assert mode is not None
            assert mode["clarified_intent"] == "implement"
            assert "a_field_that_does_not_exist" not in mode

            # And passing ONLY unknown kwargs returns False (no-op, nothing
            # to merge).
            ok2 = update_session_mode_partial(
                sid, totally_random_garbage_key="x"
            )
            assert ok2 is False
        finally:
            _cleanup(sid)


# ---------------------------------------------------------------------------
# effective_intent_class
# ---------------------------------------------------------------------------


class TestEffectiveIntentClass:
    """Pure-function tests for the resolver."""

    def test_effective_intent_class_returns_clarified_when_set(self) -> None:
        mode = {
            "intent_class": "ambiguous",
            "clarified_intent": "implement",
        }
        assert effective_intent_class(mode) == "implement"

    def test_effective_intent_class_falls_back_to_intent_class(self) -> None:
        # clarified_intent is None / missing — fall back to intent_class.
        mode_none = {
            "intent_class": "doc",
            "clarified_intent": None,
        }
        assert effective_intent_class(mode_none) == "doc"

        mode_missing = {"intent_class": "doc"}
        assert effective_intent_class(mode_missing) == "doc"

        mode_empty = {
            "intent_class": "doc",
            "clarified_intent": "",
        }
        assert effective_intent_class(mode_empty) == "doc"

    def test_effective_intent_class_handles_none_mode(self) -> None:
        """None propagates through — there's no intent class to act on."""
        assert effective_intent_class(None) is None


# ---------------------------------------------------------------------------
# Sanity / contract checks
# ---------------------------------------------------------------------------


class TestPartialUpdateAllowlist:
    """Regression: the allowlist is the source of truth, not the docstring."""

    def test_allowlist_contains_clarification_fields(self) -> None:
        """The two M2 fields are in the allowlist."""
        assert "clarification_asked" in _PARTIAL_UPDATE_ALLOWED_FIELDS
        assert "clarified_intent" in _PARTIAL_UPDATE_ALLOWED_FIELDS

    def test_allowlist_does_not_include_intent_class(self) -> None:
        """`intent_class` MUST NOT be patchable by the partial helper.

        That field comes from the classifier and would defeat the point of
        the M2 round-trip if user-clarified data were merged into it.
        """
        assert "intent_class" not in _PARTIAL_UPDATE_ALLOWED_FIELDS

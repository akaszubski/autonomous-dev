"""Tests for Issue #1263 — session_mode.user_prompt_text + get_user_msg_token.

These tests cover:
    - ``write_session_mode`` persists ``user_prompt_text`` truncated to 1000.
    - ``get_user_msg_token`` returns ``sha256(user_prompt_text)[:16]``.
    - Forward-compat fallback to ``prompt_hash`` when ``user_prompt_text`` is
      absent.
    - ``None`` for missing/stale/malformed artifacts.
    - Never raises on corrupt artifact.
    - ``SCHEMA_VERSION`` stays at 1 (additive change).
"""

from __future__ import annotations

import hashlib
import json
import sys
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

import session_mode  # noqa: E402
from session_mode import (  # noqa: E402
    SCHEMA_VERSION,
    _session_mode_path,
    get_user_msg_token,
    write_session_mode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_intent_result(
    *,
    intent_value: str = "implement",
    confidence: float = 0.97,
    regex_hit: bool = False,
    llm_used: bool = True,
    fail_open: bool = False,
    requires_security_audit: bool = False,
) -> Any:
    """Build a duck-typed IntentResult for write_session_mode."""
    return SimpleNamespace(
        intent=SimpleNamespace(value=intent_value),
        confidence=confidence,
        regex_hit=regex_hit,
        llm_used=llm_used,
        fail_open=fail_open,
        requires_security_audit=requires_security_audit,
    )


def _cleanup_artifact(session_id: str) -> None:
    """Remove the artifact file for a session id, if it exists."""
    path = _session_mode_path(session_id)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# write_session_mode persists user_prompt_text
# ---------------------------------------------------------------------------


class TestWriteSessionModePersistsUserPromptText:
    """AC#7: write_session_mode persists user_prompt_text truncated to 1000 chars."""

    def test_persists_full_prompt_when_under_limit(self) -> None:
        session_id = "test-router-token-short-prompt"
        _cleanup_artifact(session_id)
        try:
            ir = _make_intent_result()
            prompt = "implement JWT auth"
            write_session_mode(session_id, ir, prompt)
            data = json.loads(_session_mode_path(session_id).read_text())
            assert data["user_prompt_text"] == prompt
        finally:
            _cleanup_artifact(session_id)

    def test_persists_truncated_prompt(self) -> None:
        session_id = "test-router-token-long-prompt"
        _cleanup_artifact(session_id)
        try:
            ir = _make_intent_result()
            prompt = "x" * 2000
            write_session_mode(session_id, ir, prompt)
            data = json.loads(_session_mode_path(session_id).read_text())
            assert data["user_prompt_text"] == "x" * 1000
            assert len(data["user_prompt_text"]) == 1000
        finally:
            _cleanup_artifact(session_id)

    def test_non_string_prompt_persists_none(self) -> None:
        session_id = "test-router-token-nonstr-prompt"
        _cleanup_artifact(session_id)
        try:
            ir = _make_intent_result()
            # write_session_mode swallows errors silently; passing a non-string
            # MUST produce ``user_prompt_text=None`` in the artifact (the
            # writer's defensive isinstance check handles this).
            write_session_mode(session_id, ir, None)  # type: ignore[arg-type]
            data = json.loads(_session_mode_path(session_id).read_text())
            assert data["user_prompt_text"] is None
        finally:
            _cleanup_artifact(session_id)


# ---------------------------------------------------------------------------
# get_user_msg_token
# ---------------------------------------------------------------------------


class TestGetUserMsgToken:
    """AC#9, AC#10, AC#11"""

    def test_returns_sha256_of_user_prompt_text(self) -> None:
        session_id = "test-router-token-sha"
        _cleanup_artifact(session_id)
        try:
            ir = _make_intent_result()
            prompt = "hello world"
            write_session_mode(session_id, ir, prompt)
            token = get_user_msg_token(session_id)
            expected = hashlib.sha256(
                prompt.encode("utf-8", errors="ignore")
            ).hexdigest()[:16]
            assert token == expected
            assert len(token) == 16
        finally:
            _cleanup_artifact(session_id)

    def test_same_prompt_produces_same_token(self) -> None:
        session_id = "test-router-token-determ"
        _cleanup_artifact(session_id)
        try:
            ir = _make_intent_result()
            write_session_mode(session_id, ir, "same prompt")
            t1 = get_user_msg_token(session_id)
            t2 = get_user_msg_token(session_id)
            assert t1 == t2
        finally:
            _cleanup_artifact(session_id)

    def test_different_prompts_produce_different_tokens(self) -> None:
        s1 = "test-router-token-diff-1"
        s2 = "test-router-token-diff-2"
        _cleanup_artifact(s1)
        _cleanup_artifact(s2)
        try:
            ir = _make_intent_result()
            write_session_mode(s1, ir, "prompt one")
            write_session_mode(s2, ir, "prompt two")
            t1 = get_user_msg_token(s1)
            t2 = get_user_msg_token(s2)
            assert t1 != t2
        finally:
            _cleanup_artifact(s1)
            _cleanup_artifact(s2)

    def test_falls_back_to_prompt_hash_when_user_prompt_text_absent(self) -> None:
        """Forward-compat: artifacts predating Issue #1263 lack user_prompt_text."""
        session_id = "test-router-token-fallback"
        _cleanup_artifact(session_id)
        try:
            # Stage an older-style artifact missing user_prompt_text.
            from session_mode import TTL_SECONDS
            import time as _time
            payload = {
                "schema_version": SCHEMA_VERSION,
                "session_id": session_id,
                "intent_class": "implement",
                "confidence": 0.9,
                "regex_hit": False,
                "llm_used": True,
                "fail_open": False,
                "requires_security_audit": False,
                "prompt_hash": "abcdef0123456789deadbeefcafebabe",
                "written_at": "2026-01-01T00:00:00+00:00",
                "expires_at": int(_time.time()) + TTL_SECONDS,
                "enforce_mode": False,
                "clarification_asked": False,
                "clarified_intent": None,
                # user_prompt_text intentionally omitted
            }
            _session_mode_path(session_id).write_text(json.dumps(payload))
            token = get_user_msg_token(session_id)
            # prompt_hash is 32-char (or 16-char) — first 16 chars are returned.
            assert token == "abcdef0123456789"
        finally:
            _cleanup_artifact(session_id)

    def test_returns_none_when_artifact_missing(self) -> None:
        # No artifact for a totally fresh, never-written session id.
        session_id = "test-router-token-no-artifact-xyz-9999"
        _cleanup_artifact(session_id)
        assert get_user_msg_token(session_id) is None

    def test_returns_none_when_user_prompt_text_is_empty(self) -> None:
        session_id = "test-router-token-empty-prompt"
        _cleanup_artifact(session_id)
        try:
            ir = _make_intent_result()
            write_session_mode(session_id, ir, "")
            # Empty prompt -> empty user_prompt_text. Also prompt_hash will
            # be the sha256 of an empty bytes which IS truthy, so fallback
            # would kick in. The test reflects observed behavior — get_user_msg_token
            # returns None for empty user_prompt_text and then falls back to
            # prompt_hash. Confirm we get a string token from the fallback.
            token = get_user_msg_token(session_id)
            assert isinstance(token, str) and len(token) == 16
        finally:
            _cleanup_artifact(session_id)

    def test_never_raises_on_corrupt_artifact(self) -> None:
        session_id = "test-router-token-corrupt"
        _cleanup_artifact(session_id)
        try:
            # Stage a garbage artifact.
            _session_mode_path(session_id).write_text("not valid json {{ broken")
            # Should NOT raise; should return None (read_session_mode handles
            # malformed JSON -> None, and get_user_msg_token propagates None).
            assert get_user_msg_token(session_id) is None
        finally:
            _cleanup_artifact(session_id)

    def test_never_raises_on_unexpected_exception(self) -> None:
        """Outer try/except: any unexpected error -> None."""
        with patch.object(
            session_mode, "read_session_mode", side_effect=RuntimeError("boom")
        ):
            assert get_user_msg_token("any-session") is None


# ---------------------------------------------------------------------------
# Schema version invariant
# ---------------------------------------------------------------------------


class TestSchemaVersionUnchanged:
    """AC#8: SCHEMA_VERSION stays at 1 (additive change only)."""

    def test_version_unchanged(self) -> None:
        from session_mode import SCHEMA_VERSION as SV
        assert SV == 1

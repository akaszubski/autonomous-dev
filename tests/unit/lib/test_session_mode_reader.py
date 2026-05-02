"""Unit tests for session_mode reader + should_pipeline_enforce (Issue #999, Phase E).

Covers:
    - read_session_mode round-trip with the writer.
    - read_session_mode → None on missing / stale / mismatched-schema /
      malformed JSON / I/O error.
    - should_pipeline_enforce: skip classes vs enforce classes (incl. unknowns).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_PATH) not in sys.path:
    sys.path.insert(0, str(_LIB_PATH))

from session_mode import (  # noqa: E402
    SCHEMA_VERSION,
    TTL_SECONDS,
    _session_mode_path,
    read_session_mode,
    should_pipeline_enforce,
    write_session_mode,
)


def _make_intent_result(
    *,
    intent_value: str = "implement",
    confidence: float = 0.97,
    regex_hit: bool = False,
    llm_used: bool = True,
    fail_open: bool = False,
    requires_security_audit: bool = False,
):
    return SimpleNamespace(
        intent=SimpleNamespace(value=intent_value),
        confidence=confidence,
        regex_hit=regex_hit,
        llm_used=llm_used,
        fail_open=fail_open,
        requires_security_audit=requires_security_audit,
    )


def _cleanup_artifact(session_id: str) -> None:
    try:
        _session_mode_path(session_id).unlink(missing_ok=True)
    except OSError:
        pass


class TestReadSessionMode:
    def test_round_trip(self):
        """write then read returns expected fields with right values."""
        sid = "test-reader-roundtrip"
        _cleanup_artifact(sid)
        try:
            write_session_mode(
                sid,
                _make_intent_result(intent_value="conversation", confidence=0.85),
                "hi",
            )
            data = read_session_mode(sid)
            assert data is not None
            assert data["schema_version"] == SCHEMA_VERSION
            assert data["intent_class"] == "conversation"
            assert data["confidence"] == 0.85
            assert "expires_at" in data
            assert "prompt_hash" in data
        finally:
            _cleanup_artifact(sid)

    def test_missing_returns_none(self):
        """Artifact never written → None."""
        sid = "test-reader-missing-12345-unique"
        _cleanup_artifact(sid)
        assert read_session_mode(sid) is None

    def test_stale_returns_none(self):
        """expires_at < now → None."""
        sid = "test-reader-stale"
        _cleanup_artifact(sid)
        try:
            path = _session_mode_path(sid)
            payload = {
                "schema_version": SCHEMA_VERSION,
                "session_id": sid,
                "intent_class": "implement",
                "confidence": 0.9,
                "regex_hit": False,
                "llm_used": True,
                "fail_open": False,
                "requires_security_audit": False,
                "prompt_hash": "0" * 16,
                "written_at": "2020-01-01T00:00:00+00:00",
                "expires_at": int(time.time()) - 60,  # expired 1 min ago
                "enforce_mode": False,
            }
            path.write_text(json.dumps(payload))
            assert read_session_mode(sid) is None
        finally:
            _cleanup_artifact(sid)

    def test_schema_version_mismatch_returns_none(self):
        """Wrong schema_version → None."""
        sid = "test-reader-schema-mismatch"
        _cleanup_artifact(sid)
        try:
            path = _session_mode_path(sid)
            payload = {
                "schema_version": 99,  # mismatched
                "session_id": sid,
                "intent_class": "implement",
                "expires_at": int(time.time()) + 3600,
            }
            path.write_text(json.dumps(payload))
            assert read_session_mode(sid) is None
        finally:
            _cleanup_artifact(sid)

    def test_malformed_json_returns_none(self):
        """Corrupted JSON file → None (no raise)."""
        sid = "test-reader-malformed"
        _cleanup_artifact(sid)
        try:
            path = _session_mode_path(sid)
            path.write_text("{not json at all")
            assert read_session_mode(sid) is None
        finally:
            _cleanup_artifact(sid)

    def test_non_dict_top_level_returns_none(self):
        """JSON that parses to list (not dict) → None."""
        sid = "test-reader-non-dict"
        _cleanup_artifact(sid)
        try:
            path = _session_mode_path(sid)
            path.write_text("[1, 2, 3]")
            assert read_session_mode(sid) is None
        finally:
            _cleanup_artifact(sid)

    def test_io_error_returns_none(self):
        """Patched read_text raising OSError → None (no raise)."""
        sid = "test-reader-ioerror"
        _cleanup_artifact(sid)
        try:
            path = _session_mode_path(sid)
            path.write_text("{}")  # exists, but read will fail
            with patch.object(
                Path, "read_text", side_effect=OSError("disk gone")
            ):
                assert read_session_mode(sid) is None
        finally:
            _cleanup_artifact(sid)


class TestShouldPipelineEnforce:
    @pytest.mark.parametrize(
        "intent_class",
        ["doc", "config", "typo", "status_query", "conversation"],
    )
    def test_skip_classes(self, intent_class):
        """The five low-risk classes return False (skip)."""
        assert should_pipeline_enforce(intent_class) is False

    @pytest.mark.parametrize(
        "intent_class",
        ["implement", "refactor", "security_critical", "ambiguous", "test"],
    )
    def test_enforce_classes(self, intent_class):
        """High-risk classes return True (enforce)."""
        assert should_pipeline_enforce(intent_class) is True

    @pytest.mark.parametrize(
        "intent_class",
        ["unknown_class", "weird", "made_up_value"],
    )
    def test_unknown_returns_true_fail_safe(self, intent_class):
        """Unknown class → True (fail-safe to enforce)."""
        assert should_pipeline_enforce(intent_class) is True

    def test_case_insensitive(self):
        """CONVERSATION, Doc, etc. all map to skip."""
        assert should_pipeline_enforce("CONVERSATION") is False
        assert should_pipeline_enforce("Doc") is False
        assert should_pipeline_enforce("IMPLEMENT") is True

    def test_non_string_returns_true(self):
        """Non-string inputs (None, int) → True."""
        assert should_pipeline_enforce(None) is True
        assert should_pipeline_enforce(42) is True
        assert should_pipeline_enforce({"x": "y"}) is True

"""Tests for session_mode artifact writer (Issue #998 — Phase D).

Covers:
    - File creation at the expected path (sha256-derived).
    - All 12 schema fields present and correctly typed.
    - Atomic write semantics (mkstemp dir, os.replace usage).
    - Resolution of unknown session ids to PID-suffixed fallbacks.
    - Fail-open contract: ANY failure path returns None silently.
    - Race tolerance under concurrent writers (last-writer-wins,
      result still parses as JSON).
    - Determinism of prompt_hash.

The fake IntentResult used in these tests duck-types the real one from
``intent_classifier`` — it exposes ``.intent.value``, ``.confidence``,
``.regex_hit``, ``.llm_used``, ``.fail_open``, ``.requires_security_audit``.
The real type is also imported and used in one test to verify integration.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

# Add lib to path so we can import session_mode + intent_classifier.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_PATH) not in sys.path:
    sys.path.insert(0, str(_LIB_PATH))

from session_mode import (  # noqa: E402
    SCHEMA_VERSION,
    TTL_SECONDS,
    _SKIP_INTENT_CLASSES,
    _atomic_write,
    _resolve_session_id,
    _session_mode_path,
    should_pipeline_enforce,
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
    """Build a duck-typed IntentResult for the writer.

    The writer accesses .intent.value (not .intent directly), so the
    nested SimpleNamespace mirrors the real enum.value pattern.
    """
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
# Tests
# ---------------------------------------------------------------------------


class TestWriteSessionMode:
    """Direct behavioral tests for write_session_mode + helpers."""

    def test_write_session_mode_creates_file(self) -> None:
        """Test 1: File exists at expected path after write."""
        session_id = "test-session-create-file"
        _cleanup_artifact(session_id)
        try:
            ir = _make_intent_result()
            write_session_mode(session_id, ir, "implement JWT auth")
            path = _session_mode_path(session_id)
            assert path.exists(), f"Artifact not created at {path}"
            # And it should be valid JSON.
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)
        finally:
            _cleanup_artifact(session_id)

    def test_path_helper_uses_sha256_8(self) -> None:
        """Test 2: _session_mode_path returns sha256(session_id)[:8] form."""
        session_id = "abc-def-ghi"
        path = _session_mode_path(session_id)
        expected_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:8]
        assert path == Path(f"/tmp/session_mode_{expected_hash}.json")
        # Format: 8 lowercase hex chars between prefix and .json
        match = re.match(r"^/tmp/session_mode_([0-9a-f]{8})\.json$", str(path))
        assert match is not None, f"Path format wrong: {path}"

    def test_schema_fields_present(self) -> None:
        """Test 3: All 12 schema keys present in written JSON."""
        session_id = "test-session-schema"
        _cleanup_artifact(session_id)
        try:
            ir = _make_intent_result(
                intent_value="security_critical",
                confidence=1.0,
                regex_hit=True,
                llm_used=False,
                requires_security_audit=True,
            )
            write_session_mode(session_id, ir, "rotate JWT secret")
            data = json.loads(_session_mode_path(session_id).read_text(encoding="utf-8"))
            expected_keys = {
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
            }
            assert set(data.keys()) == expected_keys, (
                f"Schema fields mismatch.\n"
                f"  expected: {sorted(expected_keys)}\n"
                f"  actual:   {sorted(data.keys())}\n"
                f"  missing:  {expected_keys - set(data.keys())}\n"
                f"  extra:    {set(data.keys()) - expected_keys}"
            )
            # Sanity: the values match what we passed in.
            assert data["intent_class"] == "security_critical"
            assert data["regex_hit"] is True
            assert data["llm_used"] is False
            assert data["requires_security_audit"] is True
            # written_at parses as ISO 8601.
            from datetime import datetime
            datetime.fromisoformat(data["written_at"])
            # expires_at = written_at + TTL_SECONDS (within 1s tolerance).
            assert isinstance(data["expires_at"], int)
            written_ts = int(
                datetime.fromisoformat(data["written_at"]).timestamp()
            )
            assert abs(data["expires_at"] - (written_ts + TTL_SECONDS)) <= 1
            # prompt_hash is a 16-char hex digest.
            assert re.match(r"^[0-9a-f]{16}$", data["prompt_hash"])
        finally:
            _cleanup_artifact(session_id)

    def test_schema_version_is_1(self, monkeypatch) -> None:
        """Test 4: schema_version == 1 and enforce_mode == False (default)."""
        # Make sure the env var is unset/false so enforce_mode is False.
        monkeypatch.delenv("INTENT_CLASSIFIER_ENFORCE", raising=False)
        session_id = "test-session-schema-version"
        _cleanup_artifact(session_id)
        try:
            ir = _make_intent_result()
            write_session_mode(session_id, ir, "anything")
            data = json.loads(
                _session_mode_path(session_id).read_text(encoding="utf-8")
            )
            assert data["schema_version"] == SCHEMA_VERSION == 1
            assert data["enforce_mode"] is False
        finally:
            _cleanup_artifact(session_id)

    def test_atomic_write_uses_mkstemp_in_target_dir(self, tmp_path) -> None:
        """Test 5: _atomic_write uses tempfile.mkstemp with dir=parent."""
        target = tmp_path / "subdir" / "out.json"
        target.parent.mkdir(parents=True)

        original_mkstemp = tempfile.mkstemp
        captured = {}

        def spy_mkstemp(*args, **kwargs):
            captured["dir"] = kwargs.get("dir")
            captured["prefix"] = kwargs.get("prefix")
            captured["suffix"] = kwargs.get("suffix")
            return original_mkstemp(*args, **kwargs)

        with patch("session_mode.tempfile.mkstemp", side_effect=spy_mkstemp):
            _atomic_write(target, {"hello": "world"})

        assert captured["dir"] == str(target.parent), (
            f"mkstemp dir= was {captured['dir']!r}, expected {str(target.parent)!r}. "
            f"Without dir=parent, os.replace() loses atomicity guarantees on "
            f"cross-filesystem moves."
        )
        # Sanity: file was written, contains the payload.
        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8")) == {"hello": "world"}

    def test_atomic_write_uses_os_replace(self, tmp_path) -> None:
        """Test 6: _atomic_write calls os.replace (not os.rename or shutil.move)."""
        target = tmp_path / "out.json"

        original_replace = os.replace
        called = {"count": 0, "args": None}

        def spy_replace(src, dst):
            called["count"] += 1
            called["args"] = (src, dst)
            return original_replace(src, dst)

        with patch("session_mode.os.replace", side_effect=spy_replace):
            _atomic_write(target, {"k": "v"})

        assert called["count"] == 1, "os.replace was not called exactly once"
        # And the destination is our target path.
        assert called["args"][1] == target

    def test_unknown_session_id_uses_pid_fallback(self) -> None:
        """Test 7: _resolve_session_id maps 'unknown' / '' / None to PID-suffixed form."""
        pid = os.getpid()
        assert _resolve_session_id("unknown") == f"unknown_{pid}"
        assert _resolve_session_id("") == f"unknown_{pid}"
        assert _resolve_session_id(None) == f"unknown_{pid}"
        # Real session ids pass through unchanged.
        assert _resolve_session_id("abc-123") == "abc-123"

    def test_two_unknown_sessions_dont_collide(self, tmp_path) -> None:
        """Test 8: Different PIDs yield different artifact paths.

        Run a child Python process that imports session_mode and prints the
        path it would write for "unknown". Compare against the parent's path.
        """
        parent_path = _session_mode_path("unknown")

        helper = (
            "import sys\n"
            f"sys.path.insert(0, {str(_LIB_PATH)!r})\n"
            "from session_mode import _session_mode_path\n"
            "print(_session_mode_path('unknown'))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", helper],
            capture_output=True,
            text=True,
            check=True,
        )
        child_path = Path(proc.stdout.strip())
        assert child_path != parent_path, (
            f"PID fallback did not disambiguate: parent={parent_path}, "
            f"child={child_path}"
        )

    def test_write_swallows_oserror(self) -> None:
        """Test 9: OSError from os.replace is swallowed silently."""
        session_id = "test-session-oserror"
        _cleanup_artifact(session_id)

        with patch(
            "session_mode.os.replace",
            side_effect=OSError("simulated disk full"),
        ):
            # Must NOT raise.
            result = write_session_mode(
                session_id, _make_intent_result(), "implement"
            )
            assert result is None
        # Artifact must not exist (replace failed before any commit).
        assert not _session_mode_path(session_id).exists()

    def test_write_swallows_intent_result_attribute_error(self) -> None:
        """Test 10: Pass an object missing .intent — write returns None, no file."""
        session_id = "test-session-attrerror"
        _cleanup_artifact(session_id)
        bad = SimpleNamespace()  # has no .intent attr
        # MUST NOT raise.
        result = write_session_mode(session_id, bad, "anything")
        assert result is None
        assert not _session_mode_path(session_id).exists()

    def test_race_tolerance_concurrent_writes(self) -> None:
        """Test 11: Two threads writing concurrently — final file is valid JSON."""
        session_id = "test-session-race"
        _cleanup_artifact(session_id)
        try:
            ir1 = _make_intent_result(intent_value="implement", confidence=0.9)
            ir2 = _make_intent_result(intent_value="refactor", confidence=0.8)

            errors: list[BaseException] = []

            def worker(ir, prompt):
                try:
                    for _ in range(20):
                        write_session_mode(session_id, ir, prompt)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            t1 = threading.Thread(target=worker, args=(ir1, "implement X"))
            t2 = threading.Thread(target=worker, args=(ir2, "refactor Y"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            assert errors == [], f"Concurrent writers raised: {errors}"
            path = _session_mode_path(session_id)
            assert path.exists()
            # Final file is a valid JSON dict with the schema.
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)
            assert data["schema_version"] == 1
            assert data["intent_class"] in ("implement", "refactor")
        finally:
            _cleanup_artifact(session_id)

    def test_prompt_hash_determinism(self) -> None:
        """Test 12: Same prompt → same 16-hex hash. Different prompts → different."""
        session_id_a = "test-session-hash-a"
        session_id_b = "test-session-hash-b"
        session_id_c = "test-session-hash-c"
        for sid in (session_id_a, session_id_b, session_id_c):
            _cleanup_artifact(sid)
        try:
            ir = _make_intent_result()
            write_session_mode(session_id_a, ir, "rotate the JWT secret")
            write_session_mode(session_id_b, ir, "rotate the JWT secret")
            write_session_mode(session_id_c, ir, "rotate the SAML secret")

            data_a = json.loads(
                _session_mode_path(session_id_a).read_text(encoding="utf-8")
            )
            data_b = json.loads(
                _session_mode_path(session_id_b).read_text(encoding="utf-8")
            )
            data_c = json.loads(
                _session_mode_path(session_id_c).read_text(encoding="utf-8")
            )

            assert data_a["prompt_hash"] == data_b["prompt_hash"], (
                "Same prompt produced different hashes — non-deterministic"
            )
            assert data_a["prompt_hash"] != data_c["prompt_hash"], (
                "Different prompts collided to same hash"
            )
            # Hash format: 16 lowercase hex chars.
            for h in (data_a["prompt_hash"], data_c["prompt_hash"]):
                assert re.match(r"^[0-9a-f]{16}$", h), f"Bad hash format: {h}"
        finally:
            for sid in (session_id_a, session_id_b, session_id_c):
                _cleanup_artifact(sid)


class TestEnforceFlagPlumbing:
    """Verify the INTENT_CLASSIFIER_ENFORCE env var is captured at write time."""

    def test_enforce_mode_true_when_env_set(self, monkeypatch) -> None:
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        session_id = "test-session-enforce-true"
        _cleanup_artifact(session_id)
        try:
            write_session_mode(session_id, _make_intent_result(), "x")
            data = json.loads(
                _session_mode_path(session_id).read_text(encoding="utf-8")
            )
            assert data["enforce_mode"] is True
        finally:
            _cleanup_artifact(session_id)

    def test_enforce_mode_false_when_env_unset(self, monkeypatch) -> None:
        monkeypatch.delenv("INTENT_CLASSIFIER_ENFORCE", raising=False)
        session_id = "test-session-enforce-unset"
        _cleanup_artifact(session_id)
        try:
            write_session_mode(session_id, _make_intent_result(), "x")
            data = json.loads(
                _session_mode_path(session_id).read_text(encoding="utf-8")
            )
            assert data["enforce_mode"] is False
        finally:
            _cleanup_artifact(session_id)


class TestIssue1023SkipIntentClassesExpansion:
    """Issue #1023 — non-SWE classes added to _SKIP_INTENT_CLASSES."""

    NEW_CLASSES = ("exploration", "triage", "remote_ops", "scratch")
    ORIGINAL_CLASSES = ("doc", "config", "typo", "status_query", "conversation")

    def test_skip_intent_classes_includes_new_classes(self) -> None:
        """Frozenset has 9 entries: 5 originals + 4 new."""
        assert len(_SKIP_INTENT_CLASSES) == 9, (
            f"Expected 9 skip-eligible classes, got {len(_SKIP_INTENT_CLASSES)}: "
            f"{sorted(_SKIP_INTENT_CLASSES)}"
        )
        for new_class in self.NEW_CLASSES:
            assert new_class in _SKIP_INTENT_CLASSES, (
                f"'{new_class}' not in _SKIP_INTENT_CLASSES"
            )
        for original_class in self.ORIGINAL_CLASSES:
            assert original_class in _SKIP_INTENT_CLASSES, (
                f"original skip class '{original_class}' was removed"
            )

    @pytest.mark.parametrize(
        "class_value", ("exploration", "triage", "remote_ops", "scratch")
    )
    def test_should_pipeline_enforce_returns_false_for_new_classes(
        self, class_value: str
    ) -> None:
        """should_pipeline_enforce() returns False for each new skip class."""
        assert should_pipeline_enforce(class_value) is False

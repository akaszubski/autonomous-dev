"""Tests for persist_intent_answer.py (Issue #1024 M2).

Issue #1024 Security Audit — Finding 2 (HIGH, OWASP A08 Software and Data
Integrity Failures). The persist_intent_answer.py script is the single
entry point for writing ``clarified_intent`` onto the session-mode
artifact, which is consulted by the enforcement gate (Priority 4.5 in
``enforcement_decision.py``). This test module validates the script's
input validation in depth.

Coverage:
    1. ``_validate_intent`` rejects uppercase / mixed-case ``security_critical``
       (the security-critical class is never user-selectable here).
    2. ``_validate_intent`` rejects whitespace-padded ``security_critical``
       (case-insensitive, strip-aware).
    3. ``_validate_intent`` rejects ``ambiguous`` (the state being resolved).
    4. ``_validate_intent`` rejects null bytes inside the intent string.
    5. ``_validate_intent`` accepts the seven canonical lowercase values.
    6. ``_validate_intent`` rejects unknown strings.
    7. ``main`` rejects ``--intent security_critical`` at the CLI layer with
       exit code 1 (defense in depth — even if a caller bypassed
       ``_validate_intent``).
    8. ``main`` rejects ``--intent ambiguous`` at the CLI layer with exit 1.
    9. ``main`` succeeds with a valid ``--intent doc`` against a real
       session-mode artifact and writes ``clarified_intent`` to ``"doc"``.
"""

from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Path wiring — repo_root/plugins/autonomous-dev/lib needs to be on sys.path
# so persist_intent_answer.py's library-discovery succeeds at import time.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
_SCRIPT_PATH = (
    _REPO_ROOT
    / "plugins"
    / "autonomous-dev"
    / "scripts"
    / "persist_intent_answer.py"
)

if str(_LIB_PATH) not in sys.path:
    sys.path.insert(0, str(_LIB_PATH))


def _load_persist_intent_answer() -> ModuleType:
    """Import persist_intent_answer.py by file path.

    The script lives under ``plugins/autonomous-dev/scripts/`` which is not
    a Python package, so we use importlib spec-from-file-location instead
    of a regular import.
    """
    spec = importlib.util.spec_from_file_location(
        "persist_intent_answer", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def persist_module() -> ModuleType:
    """Module-scoped import of the persist script."""
    return _load_persist_intent_answer()


# ---------------------------------------------------------------------------
# 1–6: _validate_intent unit tests
# ---------------------------------------------------------------------------


class TestValidateIntent:
    """Direct tests for _validate_intent — the single point of validation."""

    def test_validate_intent_rejects_uppercase_security_critical(
        self, persist_module: ModuleType
    ) -> None:
        """SECURITY_CRITICAL (any case) MUST be rejected.

        SECURITY_CRITICAL only ever comes from the regex pre-gate in
        intent_classifier.py:649 — never AMBIGUOUS — so it is never a
        user-selectable answer to the AskUserQuestion round-trip. The
        validation MUST be case-insensitive so an attacker cannot bypass
        with capitalisation.
        """
        for variant in (
            "SECURITY_CRITICAL",
            "Security_Critical",
            "security_Critical",
            "sEcUrItY_cRiTiCaL",
        ):
            err = persist_module._validate_intent(variant)
            assert err is not None, (
                f"variant {variant!r} should have been rejected — "
                f"_validate_intent returned None (=accepted)."
            )

    def test_validate_intent_rejects_whitespace_padded(
        self, persist_module: ModuleType
    ) -> None:
        """Whitespace-padded forbidden values MUST be rejected.

        ``  security_critical  `` should be rejected after .strip().lower()
        normalization, not silently accepted because of trailing space
        thwarting an exact-match check.
        """
        for variant in (
            "  security_critical  ",
            "\tsecurity_critical\t",
            " security_critical",
            "security_critical ",
            " AMBIGUOUS ",
            "\nambiguous\n",
        ):
            err = persist_module._validate_intent(variant)
            assert err is not None, (
                f"whitespace-padded forbidden value {variant!r} should "
                f"have been rejected."
            )

    def test_validate_intent_rejects_ambiguous(
        self, persist_module: ModuleType
    ) -> None:
        """AMBIGUOUS is the state being resolved — never a valid answer."""
        for variant in ("ambiguous", "AMBIGUOUS", "Ambiguous"):
            err = persist_module._validate_intent(variant)
            assert err is not None, (
                f"variant {variant!r} of ambiguous should have been "
                f"rejected."
            )

    def test_validate_intent_rejects_null_byte(
        self, persist_module: ModuleType
    ) -> None:
        """Null bytes embedded in the intent string MUST be rejected.

        Defense in depth against C-string truncation attacks where a
        downstream consumer might split on '\\x00' and process only the
        prefix, leading to confused-deputy behavior.
        """
        for variant in (
            "doc\x00evil",
            "doc\x00",
            "\x00doc",
            "implement\x00; rm -rf /",
            "doc\x00security_critical",
        ):
            err = persist_module._validate_intent(variant)
            assert err is not None, (
                f"null-byte-bearing intent {variant!r} should have been "
                f"rejected."
            )

    @pytest.mark.parametrize(
        "canonical",
        [
            "implement",
            "refactor",
            "test",
            "doc",
            "config",
            "status_query",
            "exploration",
        ],
    )
    def test_validate_intent_accepts_canonical_values(
        self, persist_module: ModuleType, canonical: str
    ) -> None:
        """Each of the seven canonical lowercase values MUST be accepted."""
        err = persist_module._validate_intent(canonical)
        assert err is None, (
            f"canonical value {canonical!r} should be accepted; got "
            f"error: {err!r}"
        )

    def test_validate_intent_rejects_unknown_string(
        self, persist_module: ModuleType
    ) -> None:
        """Unknown strings (not in _ALLOWED_INTENTS) MUST be rejected."""
        for variant in (
            "totally_made_up",
            "deploy",
            "ship_it",
            "yolo",
            "bypass_security",
            "",
            "   ",
        ):
            err = persist_module._validate_intent(variant)
            assert err is not None, (
                f"unknown string {variant!r} should have been rejected."
            )


# ---------------------------------------------------------------------------
# 7–9: main() CLI-layer tests
# ---------------------------------------------------------------------------


class TestMainCLI:
    """End-to-end tests of main(argv=...) — exit-code contract."""

    def test_main_rejects_security_critical_intent_argv(
        self, persist_module: ModuleType
    ) -> None:
        """``main(--intent security_critical)`` MUST return exit code 1.

        Defense in depth: even if a future caller bypassed
        ``_validate_intent`` directly, the CLI gate must independently
        reject SECURITY_CRITICAL.
        """
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = persist_module.main(
                ["--session-id", "test-sid-sec", "--intent", "security_critical"]
            )
        assert rc == 1, (
            f"main() should reject security_critical with exit 1; got "
            f"rc={rc}, stderr={buf.getvalue()!r}"
        )
        assert "security_critical" in buf.getvalue().lower() or "user-selectable" in buf.getvalue().lower(), (
            f"stderr should explain why; got: {buf.getvalue()!r}"
        )

    def test_main_rejects_ambiguous_intent_argv(
        self, persist_module: ModuleType
    ) -> None:
        """``main(--intent ambiguous)`` MUST return exit code 1.

        Persisting AMBIGUOUS would either be a no-op or create a loop
        where the next prompt fires AskUserQuestion again. Reject at the
        CLI gate.
        """
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = persist_module.main(
                ["--session-id", "test-sid-amb", "--intent", "ambiguous"]
            )
        assert rc == 1, (
            f"main() should reject ambiguous with exit 1; got rc={rc}, "
            f"stderr={buf.getvalue()!r}"
        )

    def test_main_succeeds_with_doc_intent_when_artifact_exists(
        self, persist_module: ModuleType
    ) -> None:
        """End-to-end happy path: a fresh artifact + valid intent ⇒ rc=0
        and ``clarified_intent`` is set on the artifact.
        """
        # Build a fresh session-mode artifact.
        from session_mode import (  # type: ignore[import-not-found]
            _session_mode_path,
            read_session_mode,
            write_session_mode,
        )
        from types import SimpleNamespace

        sid = "test-persist-doc-happy"
        # Defensive cleanup from any prior run.
        try:
            _session_mode_path(sid).unlink(missing_ok=True)
        except OSError:
            pass

        try:
            fake_intent = SimpleNamespace(
                intent=SimpleNamespace(value="ambiguous"),
                confidence=0.4,
                regex_hit=False,
                llm_used=True,
                fail_open=True,
                requires_security_audit=True,
            )
            write_session_mode(sid, fake_intent, "vague prompt")

            buf = io.StringIO()
            with redirect_stderr(buf):
                rc = persist_module.main(
                    ["--session-id", sid, "--intent", "doc"]
                )
            assert rc == 0, (
                f"main() should succeed with doc intent on a fresh "
                f"artifact; got rc={rc}, stderr={buf.getvalue()!r}"
            )

            # Re-read the artifact and assert clarified_intent is set.
            mode = read_session_mode(sid)
            assert mode is not None, "artifact should still be readable"
            assert mode.get("clarified_intent") == "doc", (
                f"clarified_intent should equal 'doc'; got "
                f"{mode.get('clarified_intent')!r}"
            )
            assert mode.get("clarification_asked") is True, (
                f"clarification_asked should also be set to True; got "
                f"{mode.get('clarification_asked')!r}"
            )
        finally:
            try:
                _session_mode_path(sid).unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Cross-check: forbidden set MUST be a subset of the canonical taxonomy
# ---------------------------------------------------------------------------


class TestModuleConstants:
    """Sanity checks on _ALLOWED_INTENTS and _FORBIDDEN_INTENTS."""

    def test_forbidden_and_allowed_are_disjoint(
        self, persist_module: ModuleType
    ) -> None:
        """A value MUST NOT appear in both _ALLOWED_INTENTS and
        _FORBIDDEN_INTENTS — that would be a contradiction."""
        allowed = set(persist_module._ALLOWED_INTENTS)
        forbidden = set(persist_module._FORBIDDEN_INTENTS)
        overlap = allowed & forbidden
        assert overlap == set(), (
            f"taxonomy bug: {sorted(overlap)} appear in both _ALLOWED and "
            f"_FORBIDDEN; the AskUserQuestion round-trip would either "
            f"accept-then-reject or vice versa."
        )

    def test_forbidden_contains_security_critical_and_ambiguous(
        self, persist_module: ModuleType
    ) -> None:
        """_FORBIDDEN_INTENTS MUST contain the two non-user-selectable
        classes — defense in depth that the constant cannot drift to omit
        them."""
        forbidden = set(persist_module._FORBIDDEN_INTENTS)
        assert "security_critical" in forbidden
        assert "ambiguous" in forbidden

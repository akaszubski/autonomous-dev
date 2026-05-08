"""Tests for unified_prompt_validator clarification emission (Issue #1024 M2).

These tests run the hook as a subprocess (the same shape as
``TestHookNoOpWhenFlagOff``) so we get end-to-end output behavior without
mocking the routing internals. We mock the classifier output by patching
the hook's ``IntentClassifier.from_config`` via a ``PYTHONPATH``-injected
shim file. Where subprocess is too coarse, we import the hook module
directly and call its helpers.

Coverage:
    1. AMBIGUOUS classification + both flags on ⇒ clarification emitted
       in ``additionalContext``.
    2. Non-AMBIGUOUS ⇒ no clarification emitted.
    3. Both flags required (gates 2 of 2) — only emits when both are true.
    4. session_id is inlined into the template literally.
    5. Byte-identity preserved when classifier flag is off.
    6. The seven canonical intent options appear in the template.
    7. The persist command points at the correct script path.
    8. Telemetry — when clarification is emitted, the activity log entry
       carries ``clarification_emitted=True``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Add lib + hooks to sys.path for direct imports.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"

for p in (_LIB_PATH, _HOOKS_PATH):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# ---------------------------------------------------------------------------
# Helpers — fake IntentResult and module-level reload harness
# ---------------------------------------------------------------------------


def _fake_intent_result(intent_value: str = "ambiguous") -> SimpleNamespace:
    """Build a duck-typed IntentResult."""
    return SimpleNamespace(
        intent=SimpleNamespace(value=intent_value),
        confidence=0.4 if intent_value == "ambiguous" else 0.95,
        regex_hit=False,
        llm_used=True,
        fail_open=intent_value == "ambiguous",
        requires_security_audit=intent_value
        in ("ambiguous", "security_critical"),
    )


def _reload_module_with_env(env_overrides: dict) -> object:
    """Import unified_prompt_validator with a specific env state.

    Returns the freshly reloaded module so the module-load env reads see
    the test's env. We use ``importlib.reload`` so successive tests with
    different env states do not leak module-level constants.
    """
    import importlib

    saved = {k: os.environ.get(k) for k in env_overrides}
    try:
        for k, v in env_overrides.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

        if "unified_prompt_validator" in sys.modules:
            module = importlib.reload(sys.modules["unified_prompt_validator"])
        else:
            import unified_prompt_validator as module  # type: ignore[import-not-found]
        return module
    finally:
        for k, original in saved.items():
            if original is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = original


def _cleanup_artifact(session_id: str) -> None:
    from session_mode import _session_mode_path  # type: ignore[import-not-found]

    try:
        _session_mode_path(session_id).unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Tests using the hook helper directly (_maybe_build_clarification)
# ---------------------------------------------------------------------------


class TestMaybeBuildClarification:
    """Direct tests of ``_maybe_build_clarification`` — the gate logic."""

    def test_ambiguous_emits_clarification_in_additional_context(self) -> None:
        """AMBIGUOUS + both flags + fresh artifact ⇒ block returned."""
        sid = "test-clar-1"
        _cleanup_artifact(sid)
        try:
            from session_mode import write_session_mode  # type: ignore[import-not-found]
            write_session_mode(sid, _fake_intent_result("ambiguous"), "vague prompt")

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": "true",
                    "INTENT_CLASSIFIER_ENFORCE": "true",
                }
            )

            block = module._maybe_build_clarification(
                intent_result=_fake_intent_result("ambiguous"),
                session_id=sid,
            )
            assert block is not None
            assert "AskUserQuestion" in block
            assert "ambiguous" in block.lower()
        finally:
            _cleanup_artifact(sid)

    def test_non_ambiguous_does_not_emit_clarification(self) -> None:
        """IMPLEMENT (not AMBIGUOUS) ⇒ no clarification."""
        sid = "test-clar-noemit"
        _cleanup_artifact(sid)
        try:
            from session_mode import write_session_mode  # type: ignore[import-not-found]
            write_session_mode(sid, _fake_intent_result("implement"), "build X")

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": "true",
                    "INTENT_CLASSIFIER_ENFORCE": "true",
                }
            )

            block = module._maybe_build_clarification(
                intent_result=_fake_intent_result("implement"),
                session_id=sid,
            )
            assert block is None
        finally:
            _cleanup_artifact(sid)

    @pytest.mark.parametrize(
        "enabled,enforce,expected_emit",
        [
            ("true", "true", True),
            ("true", "false", False),
            ("false", "true", False),
            ("false", "false", False),
        ],
    )
    def test_clarification_gated_on_both_flags(
        self, enabled: str, enforce: str, expected_emit: bool
    ) -> None:
        """Only the (true, true) combination should emit."""
        sid = f"test-clar-flags-{enabled}-{enforce}"
        _cleanup_artifact(sid)
        try:
            from session_mode import write_session_mode  # type: ignore[import-not-found]
            write_session_mode(sid, _fake_intent_result("ambiguous"), "x")

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": enabled,
                    "INTENT_CLASSIFIER_ENFORCE": enforce,
                }
            )

            block = module._maybe_build_clarification(
                intent_result=_fake_intent_result("ambiguous"),
                session_id=sid,
            )
            if expected_emit:
                assert block is not None
            else:
                assert block is None
        finally:
            _cleanup_artifact(sid)

    def test_clarification_inlines_session_id(self) -> None:
        """The sanitized session_id appears in the persist command.

        Verifies SAFE inlining (Issue #1024 security audit Finding 1):
        the clarification template uses str.replace on a sentinel rather
        than str.format, AND the session_id is sanitized before inlining
        so that shell metacharacters and format-string field names cannot
        break the persist command or trigger DoS-via-suppression.

        The benign portion of the session_id ('test-clar-inline_abc-xyz-123')
        consists entirely of [A-Za-z0-9_-] characters and so survives
        sanitization untouched.
        """
        # Adversarial session_id mixing safe + dangerous characters:
        # - shell metacharacters: ; | & $ `` " '
        # - format-string syntax: {} {evil}
        # - whitespace and path traversal: spaces, /, \\, ..
        #
        # All non-[A-Za-z0-9_-] characters MUST be replaced with '_'.
        sid = "test-clar-inline_abc-xyz-123"
        adversarial_sid = sid + "{}{evil};rm -rf /;`whoami`\"$(id)\""
        _cleanup_artifact(adversarial_sid)
        _cleanup_artifact(sid)
        try:
            from session_mode import write_session_mode  # type: ignore[import-not-found]
            # Write artifact under the adversarial id so the loop guard
            # read sees the artifact (path is hashed, not literal).
            write_session_mode(
                adversarial_sid, _fake_intent_result("ambiguous"), "x"
            )

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": "true",
                    "INTENT_CLASSIFIER_ENFORCE": "true",
                }
            )
            block = module._maybe_build_clarification(
                intent_result=_fake_intent_result("ambiguous"),
                session_id=adversarial_sid,
            )
            assert block is not None, "should have emitted"

            # The benign run of safe chars must survive sanitization.
            assert sid in block, (
                f"benign session_id portion {sid!r} not present in block:\n"
                f"{block}"
            )

            # Extract the value between the literal surrounding quotes that
            # the template adds: `--session-id "<value>"`. The surrounding
            # quotes are part of the template, not the value, so we slice
            # them off before checking forbidden characters.
            after_flag = block.split("--session-id ", 1)[1]
            # after_flag begins with a literal " and the value runs up to
            # the next ".
            assert after_flag.startswith("\""), (
                f"--session-id value should be quoted in the template; got: "
                f"{after_flag[:40]!r}"
            )
            session_arg_value = after_flag[1:].split("\"", 1)[0]

            # The adversarial substring as a whole must NOT appear verbatim;
            # _SAFE_SESSION_ID_RE replaces dangerous chars with '_'. None of
            # these may appear INSIDE the value:
            for forbidden in (
                "{}",
                "{evil}",
                ";",
                "|",
                "$",
                "`",
                "\"",
                "'",
                "..",
                " ",
                "/",
                "\\",
            ):
                assert forbidden not in session_arg_value, (
                    f"unsafe character {forbidden!r} leaked into the "
                    f"--session-id argument value {session_arg_value!r}:\n"
                    f"{block}"
                )

            # The format-string sentinel must have been fully replaced.
            assert "__SESSION_ID__" not in block, (
                f"sentinel '__SESSION_ID__' was not replaced:\n{block}"
            )
        finally:
            _cleanup_artifact(adversarial_sid)
            _cleanup_artifact(sid)

    def test_clarification_format_brace_does_not_raise(self) -> None:
        """A session_id containing '{}' MUST NOT trigger IndexError.

        Regression for Issue #1024 security audit Finding 1: the previous
        implementation used .format(session_id=...), which would raise on
        '{}' (positional placeholder mismatch) and silently suppress the
        clarification via the outer try/except — a DoS vector.

        With the str.replace + sentinel design, '{}' in the session_id is
        replaced with '__' and the clarification still emits cleanly.
        """
        sid_with_braces = "abc{}{x}def"
        _cleanup_artifact(sid_with_braces)
        try:
            from session_mode import write_session_mode  # type: ignore[import-not-found]
            write_session_mode(
                sid_with_braces, _fake_intent_result("ambiguous"), "x"
            )

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": "true",
                    "INTENT_CLASSIFIER_ENFORCE": "true",
                }
            )
            block = module._maybe_build_clarification(
                intent_result=_fake_intent_result("ambiguous"),
                session_id=sid_with_braces,
            )
            assert block is not None, (
                "clarification was suppressed — likely an IndexError from "
                "str.format on a session_id containing '{}'."
            )
            assert "{}" not in block
            assert "{x}" not in block
        finally:
            _cleanup_artifact(sid_with_braces)

    def test_clarification_offers_canonical_intent_options(self) -> None:
        """All 7 canonical intent values appear in the template."""
        sid = "test-clar-options"
        _cleanup_artifact(sid)
        try:
            from session_mode import write_session_mode  # type: ignore[import-not-found]
            write_session_mode(sid, _fake_intent_result("ambiguous"), "x")

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": "true",
                    "INTENT_CLASSIFIER_ENFORCE": "true",
                }
            )
            block = module._maybe_build_clarification(
                intent_result=_fake_intent_result("ambiguous"),
                session_id=sid,
            )
            assert block is not None
            for opt in (
                "IMPLEMENT",
                "REFACTOR",
                "TEST",
                "DOC",
                "CONFIG",
                "STATUS_QUERY",
                "EXPLORATION",
            ):
                assert opt in block, f"option {opt!r} missing from template"
        finally:
            _cleanup_artifact(sid)

    def test_clarification_emits_persist_command_with_correct_path(self) -> None:
        """The persist command references the right script path."""
        sid = "test-clar-path"
        _cleanup_artifact(sid)
        try:
            from session_mode import write_session_mode  # type: ignore[import-not-found]
            write_session_mode(sid, _fake_intent_result("ambiguous"), "x")

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": "true",
                    "INTENT_CLASSIFIER_ENFORCE": "true",
                }
            )
            block = module._maybe_build_clarification(
                intent_result=_fake_intent_result("ambiguous"),
                session_id=sid,
            )
            assert block is not None
            assert (
                "plugins/autonomous-dev/scripts/persist_intent_answer.py"
                in block
            )
            assert "--session-id" in block
            assert "--intent" in block
        finally:
            _cleanup_artifact(sid)

    def test_clarification_loop_guard_when_already_asked(self) -> None:
        """If clarification_asked is already True, do not re-emit."""
        sid = "test-clar-loop"
        _cleanup_artifact(sid)
        try:
            from session_mode import (  # type: ignore[import-not-found]
                update_session_mode_partial,
                write_session_mode,
            )
            write_session_mode(sid, _fake_intent_result("ambiguous"), "x")
            update_session_mode_partial(sid, clarification_asked=True)

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": "true",
                    "INTENT_CLASSIFIER_ENFORCE": "true",
                }
            )
            block = module._maybe_build_clarification(
                intent_result=_fake_intent_result("ambiguous"),
                session_id=sid,
            )
            assert block is None, "loop guard should have prevented re-emit"
        finally:
            _cleanup_artifact(sid)

    def test_clarification_loop_guard_when_already_clarified(self) -> None:
        """If clarified_intent is set, do not re-emit."""
        sid = "test-clar-already"
        _cleanup_artifact(sid)
        try:
            from session_mode import (  # type: ignore[import-not-found]
                update_session_mode_partial,
                write_session_mode,
            )
            write_session_mode(sid, _fake_intent_result("ambiguous"), "x")
            update_session_mode_partial(sid, clarified_intent="implement")

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": "true",
                    "INTENT_CLASSIFIER_ENFORCE": "true",
                }
            )
            block = module._maybe_build_clarification(
                intent_result=_fake_intent_result("ambiguous"),
                session_id=sid,
            )
            assert block is None
        finally:
            _cleanup_artifact(sid)


# ---------------------------------------------------------------------------
# End-to-end via subprocess: byte-identity + structural output
# ---------------------------------------------------------------------------


class TestClarificationByteIdentityWhenDisabled:
    """When INTENT_CLASSIFIER_ENABLED=false, clarification block MUST NOT
    appear in stdout — preserves the byte-identity contract.
    """

    def test_clarification_preserves_byte_identity_when_disabled(self) -> None:
        import subprocess

        hook_path = _HOOKS_PATH / "unified_prompt_validator.py"
        # An ambiguous-looking prompt that the routing table does NOT match.
        # We verify the absence of "AskUserQuestion" in stdout.
        prompt = "could you maybe figure out what to do here"
        proc = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps({"userPrompt": prompt}),
            capture_output=True,
            text=True,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
                "HOME": os.environ.get("HOME", str(Path.home())),
                "QUALITY_NUDGE_ENABLED": "true",
                "ENFORCE_WORKFLOW": "true",
                # Both flags OFF — the M2 round-trip must NOT fire.
                "INTENT_CLASSIFIER_ENABLED": "false",
                "INTENT_CLASSIFIER_ENFORCE": "false",
            },
            cwd="/tmp",
        )
        assert proc.returncode == 0
        assert "AskUserQuestion" not in proc.stdout, (
            f"clarification block leaked into stdout when classifier was "
            f"disabled:\n{proc.stdout}"
        )
        assert "AskUserQuestion" not in proc.stderr


# ---------------------------------------------------------------------------
# Telemetry: activity log entry includes clarification_emitted=True
# ---------------------------------------------------------------------------


class TestTelemetry:
    """When clarification is emitted, _log_activity sees the emitted flag."""

    def test_clarification_emits_telemetry(self, tmp_path, monkeypatch) -> None:
        """Verify the pass-path activity log entry carries clarification_emitted."""
        sid = "test-clar-telemetry"
        _cleanup_artifact(sid)
        try:
            from session_mode import write_session_mode  # type: ignore[import-not-found]
            write_session_mode(sid, _fake_intent_result("ambiguous"), "x")

            module = _reload_module_with_env(
                {
                    "INTENT_CLASSIFIER_ENABLED": "true",
                    "INTENT_CLASSIFIER_ENFORCE": "true",
                }
            )

            captured = []

            def fake_log_activity(event: str, details: dict) -> None:
                captured.append((event, details))

            # Patch out _log_activity, _classify_intent_safe (return AMBIGUOUS)
            # and detect_command_intent (return None — pass path).
            monkeypatch.setattr(
                module, "_log_activity", fake_log_activity
            )
            monkeypatch.setattr(
                module,
                "_classify_intent_safe",
                lambda _p: _fake_intent_result("ambiguous"),
            )
            monkeypatch.setattr(
                module, "detect_command_intent", lambda _t: None
            )
            monkeypatch.setenv("CLAUDE_SESSION_ID", sid)

            payload = json.dumps({"userPrompt": "vague request"})
            with patch("sys.stdin.read", return_value=payload):
                rc = module.main()
            assert rc == 0

            # The pass-path activity-log entry should carry the flag.
            pass_entries = [d for ev, d in captured if ev == "pass"]
            assert len(pass_entries) == 1, (
                f"expected one pass entry, got {len(pass_entries)}: {captured}"
            )
            assert pass_entries[0].get("clarification_emitted") is True, (
                f"clarification_emitted not set on activity log: {pass_entries[0]}"
            )
        finally:
            _cleanup_artifact(sid)

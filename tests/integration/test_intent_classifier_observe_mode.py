"""End-to-end integration tests for Phase D observe-mode wiring (Issue #998).

Verifies:
    1. When INTENT_CLASSIFIER_ENABLED=true, the UserPromptSubmit hook writes
       a session-mode artifact at /tmp/session_mode_<8-hex>.json with the
       expected schema.
    2. When INTENT_CLASSIFIER_ENABLED is unset (default), the hook produces
       byte-identical stdout/stderr/exit code to a second run with the
       variable explicitly false — and writes NO artifact.
    3. The activity-log "decision" field is unchanged with the classifier
       enabled vs disabled, so downstream routing contracts remain intact.

These tests subprocess into the real hook entrypoint to exercise the full
import/discovery path the production hook follows.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = (
    _REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_prompt_validator.py"
)
LIB_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"


def _session_mode_path_for(session_id: str) -> Path:
    """Compute the artifact path for a session id (mirrors session_mode.py)."""
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:8]
    return Path(f"/tmp/session_mode_{digest}.json")


def _cleanup(session_id: str) -> None:
    try:
        _session_mode_path_for(session_id).unlink(missing_ok=True)
    except OSError:
        pass


def _base_env() -> dict:
    """Minimal env so the hook runs without inheriting test machinery."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
        "HOME": os.environ.get("HOME", str(Path.home())),
        "QUALITY_NUDGE_ENABLED": "true",
        "ENFORCE_WORKFLOW": "true",
    }


def _run_hook(prompt: str, env: dict, cwd: str = "/tmp") -> subprocess.CompletedProcess:
    payload = json.dumps({"userPrompt": prompt})
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# Test 1: artifact written when enabled
# ---------------------------------------------------------------------------


class TestArtifactWrittenWhenEnabled:
    """When INTENT_CLASSIFIER_ENABLED=true, a session-mode artifact appears."""

    def test_e2e_artifact_written_when_enabled(self, tmp_path) -> None:
        """End-to-end: hook with the flag on writes an artifact in /tmp."""
        session_id = "test-issue998-phaseD-e2e-write"
        _cleanup(session_id)
        try:
            env = _base_env()
            env["INTENT_CLASSIFIER_ENABLED"] = "true"
            env["CLAUDE_SESSION_ID"] = session_id

            # Use a security-keyword prompt so the regex short-circuit fires
            # — that path doesn't need the LLM to be reachable, so this test
            # works even when GenAI is unavailable.
            proc = _run_hook("rotate the JWT secret", env, cwd=str(tmp_path))

            assert proc.returncode == 0, (
                f"hook exited {proc.returncode}\n"
                f"stdout: {proc.stdout!r}\nstderr: {proc.stderr!r}"
            )

            artifact = _session_mode_path_for(session_id)
            assert artifact.exists(), (
                f"Session-mode artifact missing at {artifact}.\n"
                f"stdout: {proc.stdout!r}\nstderr: {proc.stderr!r}"
            )
            data = json.loads(artifact.read_text(encoding="utf-8"))
            # Schema sanity.
            assert data["schema_version"] == 1
            assert data["session_id"] == session_id
            # The prompt has 'jwt' in it — security regex must hit.
            assert data["intent_class"] == "security_critical"
            assert data["regex_hit"] is True
            assert data["llm_used"] is False
            assert data["fail_open"] is False
            assert data["requires_security_audit"] is True
            # 12 fields total.
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
            assert set(data.keys()) == expected_keys
        finally:
            _cleanup(session_id)


# ---------------------------------------------------------------------------
# Test 2: byte-identical hook output when disabled vs unset
# ---------------------------------------------------------------------------


class TestByteIdenticalWhenDisabled:
    """When the flag is unset, the hook is byte-identical to flag=false."""

    def test_byte_identical_when_disabled(self, tmp_path) -> None:
        """Two runs with flag unset vs flag=false: identical outputs, no artifact."""
        session_id = "test-issue998-phaseD-disabled"
        _cleanup(session_id)
        try:
            prompt = "implement JWT authentication feature"

            env_unset = _base_env()
            env_unset["CLAUDE_SESSION_ID"] = session_id
            # INTENT_CLASSIFIER_ENABLED INTENTIONALLY unset.

            env_false = _base_env()
            env_false["CLAUDE_SESSION_ID"] = session_id
            env_false["INTENT_CLASSIFIER_ENABLED"] = "false"

            proc_unset = _run_hook(prompt, env_unset, cwd=str(tmp_path))
            proc_false = _run_hook(prompt, env_false, cwd=str(tmp_path))

            assert proc_unset.returncode == proc_false.returncode, (
                f"return codes differ: unset={proc_unset.returncode} "
                f"false={proc_false.returncode}"
            )
            assert proc_unset.stdout == proc_false.stdout, (
                f"stdout drift\n--- unset ---\n{proc_unset.stdout!r}\n"
                f"--- false ---\n{proc_false.stdout!r}"
            )
            assert proc_unset.stderr == proc_false.stderr, (
                f"stderr drift\n--- unset ---\n{proc_unset.stderr!r}\n"
                f"--- false ---\n{proc_false.stderr!r}"
            )

            # No artifact must have been created in either run.
            artifact = _session_mode_path_for(session_id)
            assert not artifact.exists(), (
                f"Artifact unexpectedly created when flag was off: {artifact}"
            )
        finally:
            _cleanup(session_id)


# ---------------------------------------------------------------------------
# Test 3: downstream contract unchanged
# ---------------------------------------------------------------------------


class TestDownstreamHooksUnchangedContract:
    """Activity-log routing decisions are unchanged with classifier enabled."""

    def test_downstream_hooks_unchanged_contract(self, tmp_path) -> None:
        """The hook's routing decision (block/nudge/none) is identical with
        the classifier on or off — the artifact write is observe-only.

        We compare the (returncode, the routing-relevant subset of stdout)
        across enabled-vs-disabled runs. stdout in this hook contains the
        hookSpecificOutput JSON; we parse it and check the routing fields
        are identical regardless of classifier state.
        """
        session_id_off = "test-issue998-phaseD-contract-off"
        session_id_on = "test-issue998-phaseD-contract-on"
        _cleanup(session_id_off)
        _cleanup(session_id_on)
        try:
            # A prompt that triggers neither block nor nudge — innocuous chat.
            # This exercises the "no route matched" path which is sensitive
            # to any extra side-effects.
            prompt = "Hello, what does this codebase do?"

            env_off = _base_env()
            env_off["CLAUDE_SESSION_ID"] = session_id_off
            env_off["INTENT_CLASSIFIER_ENABLED"] = "false"

            env_on = _base_env()
            env_on["CLAUDE_SESSION_ID"] = session_id_on
            env_on["INTENT_CLASSIFIER_ENABLED"] = "true"

            proc_off = _run_hook(prompt, env_off, cwd=str(tmp_path))
            proc_on = _run_hook(prompt, env_on, cwd=str(tmp_path))

            assert proc_off.returncode == proc_on.returncode == 0, (
                f"non-zero exits: off={proc_off.returncode} on={proc_on.returncode}"
            )

            # Parse stdout (JSON) and compare the routing-decision-relevant
            # subset. The classifier MAY add fields downstream in later
            # phases, but in Phase D it must be invisible to stdout.
            def _parse_or_empty(s: str) -> dict:
                s = s.strip()
                if not s:
                    return {}
                try:
                    return json.loads(s)
                except json.JSONDecodeError:
                    return {"_raw": s}

            json_off = _parse_or_empty(proc_off.stdout)
            json_on = _parse_or_empty(proc_on.stdout)

            assert json_off == json_on, (
                f"stdout JSON drift between off and on:\n"
                f"  off: {json_off}\n  on:  {json_on}"
            )

            # Stderr is also expected to be identical for non-block/non-nudge prompts.
            # (Compaction recovery only fires when the marker file exists; tmp_path is empty.)
            assert proc_off.stderr == proc_on.stderr, (
                f"stderr drift\n--- off ---\n{proc_off.stderr!r}\n"
                f"--- on ---\n{proc_on.stderr!r}"
            )

            # Artifact existence differs:
            #   off → no artifact
            #   on  → artifact exists IF intent_result is not None.
            #         For a pure-conversation prompt with no GenAI/Haiku
            #         available in the test env, the classifier will fail-open
            #         and intent_result is still non-None (AMBIGUOUS), so an
            #         artifact IS expected. If GenAI is genuinely unreachable,
            #         the writer still records intent=ambiguous, fail_open=true.
            assert not _session_mode_path_for(session_id_off).exists(), (
                "off-run created an artifact"
            )
            on_artifact = _session_mode_path_for(session_id_on)
            assert on_artifact.exists(), (
                f"on-run did not create artifact at {on_artifact}\n"
                f"stderr: {proc_on.stderr!r}"
            )
            on_data = json.loads(on_artifact.read_text(encoding="utf-8"))
            assert on_data["session_id"] == session_id_on
        finally:
            _cleanup(session_id_off)
            _cleanup(session_id_on)

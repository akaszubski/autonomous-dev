#!/usr/bin/env python3
"""Regression tests for Issue #1811: plugin-namespaced pipeline-agent identity.

``PIPELINE_AGENTS`` holds UNPREFIXED role names (``implementer``,
``test-master``, ``doc-master``), but a plugin-dispatched subagent reports
``CLAUDE_AGENT_NAME=autonomous-dev:implementer``. ``_get_active_agent_name()``
returned the raw namespaced string, so every ``in PIPELINE_AGENTS`` membership
test mis-evaluated:

===============================  ====================================================
Site (``unified_pre_tool.py``)   Pre-fix behaviour for a namespaced pipeline agent
===============================  ====================================================
``_is_pipeline_active()``        fails CLOSED — pipeline reported inactive
``validate_agent_authorization`` fails CLOSED — agent never authorized
#1467 verdict escalation gate    fails OPEN  — disallowed verdict silently skipped
``main()`` workflow fast path    fails CLOSED — "delegate to the implementer" *to* the
                                 implementer
===============================  ====================================================

The FORBIDDEN fix is stripping any prefix (``split(':')[-1]``): that turns
``evil:implementer`` into an authorized pipeline agent. The negative cases below
are deliberately shaped so the naive fix FAILS them — every spoof collapses to
``implementer`` under ``split(':')[-1]`` but must stay unauthorized.

Coverage layering (see the reduction note in the Issue #1811 implementation
report): all SIX spoof shapes are exercised against the normalization unit,
which is the single point every consumer routes through. Each consumer site
re-checks only :data:`CONSUMER_SPOOFS` — two shapes that both defeat
``split(':')[-1]`` — because the remaining four would only re-derive the same
predicate through the same function.

GitHub Issue: #1811
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import List, Tuple
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
for _p in (str(HOOK_DIR), str(LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pipeline_state  # noqa: E402
import unified_pre_tool as hook  # noqa: E402
from path_utils import ACTIVITY_LOG_DIR_ENV  # noqa: E402
from pipeline_state import sign_state  # noqa: E402

PLUGIN_MANIFEST = REPO_ROOT / "plugins" / "autonomous-dev" / ".claude-plugin" / "plugin.json"
LIVE_LOGS_DIR = REPO_ROOT / ".claude" / "logs"

# A non-scratch code target. Issue #1408 exempts /tmp and /var/folders (and
# therefore pytest's tmp_path) from every write gate, so an absolute tmp path
# would make these tests pass vacuously. A repo-relative path is NOT scratch.
CODE_TARGET = "src/feature_1811.py"

# Spoofs that MUST NOT be normalized. Every one collapses to "implementer"
# under the forbidden split(':')[-1] fix. Exercised in full against the
# normalization unit.
SPOOFED_IDENTITIES = [
    "evil:implementer",                 # unregistered namespace
    "autonomous-dev-extra:implementer",  # prefix-superstring of a real namespace
    "claude:implementer",               # plausible-but-unregistered namespace
    "evil:autonomous-dev:implementer",  # real namespace buried behind a fake one
    "autonomous-dev:evil:implementer",  # real namespace, compound/unknown role
    "xautonomous-dev:implementer",      # suffix-superstring of a real namespace
]

# Re-checked at every consumer site: an outright spoof and a superstring of the
# real namespace. Both defeat split(':')[-1], so a locally reintroduced naive
# strip at any single site is still caught.
CONSUMER_SPOOFS = SPOOFED_IDENTITIES[:2]

# Degenerate colon forms — neither half validates, so the raw name survives.
MALFORMED_IDENTITIES = [
    ":implementer",                 # empty namespace
    "autonomous-dev:",              # empty role
    "::",                           # nothing either side
    "autonomous-dev:implementer:",  # trailing colon corrupts the role
]

# Passthrough forms that contain no namespace separator at all.
UNNAMESPACED_IDENTITIES = ["implementer", "reviewer", "main", ""]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_synthetic_telemetry(monkeypatch):
    """Keep every synthetic record in this file out of the LIVE .claude/logs tree.

    Two writers, two mechanisms — both pre-existing, neither duplicated here:

    1. **Activity log + deviations.** ``tests/conftest.py`` (Issue #1779 AC1)
       already exports ``AUTONOMOUS_DEV_ACTIVITY_LOG_DIR`` to a per-session
       ``mkdtemp`` at IMPORT time, which is what ``_resolved_logs_dir()`` ->
       ``path_utils.resolve_activity_log_dir()`` honours. Re-pointing it here
       would be a second way to do one thing and would shadow the value the
       conftest session-finish leak guard reasons about. So this fixture
       ASSERTS the redirect instead of repeating it: if the conftest guard is
       ever removed, these tests fail loudly rather than silently appending to
       the operator's real log.
    2. **hook-blocks.jsonl.** ``hook_telemetry.log_block_event`` resolves
       ``.claude/logs/hook-blocks.jsonl`` relative to cwd and does NOT honour
       the activity redirect, so the ``main()``-driving tests below leaked 8
       synthetic rows per run (MEASURED 2026-09-26). ``HOOK_TELEMETRY_DISABLED``
       is the shipped rollback switch for exactly this surface; the rows are
       pure telemetry emitted AFTER the decision under test is already made, so
       disabling them cannot mask a decision regression.
    """
    redirect = os.environ.get(ACTIVITY_LOG_DIR_ENV, "").strip()
    assert redirect, (
        f"{ACTIVITY_LOG_DIR_ENV} is not set. tests/conftest.py must export it "
        "(Issue #1779 AC1) or these tests will append synthetic records to the "
        f"live log at {LIVE_LOGS_DIR / 'activity'}."
    )
    assert not str(Path(redirect).resolve()).startswith(str(LIVE_LOGS_DIR.resolve())), (
        f"{ACTIVITY_LOG_DIR_ENV}={redirect} points INSIDE the live log tree "
        f"{LIVE_LOGS_DIR}; synthetic records would contaminate real session data."
    )

    state_file = os.environ.get("PIPELINE_STATE_FILE", "").strip()
    assert state_file and not str(Path(state_file).resolve()).startswith(
        str((REPO_ROOT / ".claude").resolve())
    ), (
        "PIPELINE_STATE_FILE must be redirected outside the live .claude tree "
        "(tests/conftest.py, Issue #1779 AC1) — the _is_pipeline_active() name "
        "branch touches whatever this points at."
    )

    monkeypatch.setenv("HOOK_TELEMETRY_DISABLED", "1")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Reset identity/enforcement env and the module-level agent_type global.

    ``PIPELINE_STATE_FILE`` is deliberately NOT cleared — conftest points it at
    an isolated tmp path and every test that needs a specific state overrides
    it. Clearing it would fall back to the LIVE legacy sentinel.
    """
    for key in ("CLAUDE_AGENT_NAME", "ENFORCEMENT_LEVEL", "BATCH_NO_WORKTREE",
                "AUTONOMOUS_DEV_BYPASS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PRE_TOOL_AGENT_AUTH", "true")
    monkeypatch.setattr(hook, "_agent_type", "", raising=False)


@pytest.fixture(autouse=True)
def isolate_stale_state_failopen(tmp_path, monkeypatch):
    """Neutralize the Issue #753 stale-sentinel fail-open.

    ``verify_state_hmac`` fails OPEN when the legacy sentinel is more than an
    hour old, which in a developer worktree makes signed-state assertions
    depend on wall-clock time. Point the staleness probe at a fresh tmp
    sentinel (mirrors tests/unit/hooks/test_alignment_verdict_gate.py).
    """
    sentinel = tmp_path / "legacy_sentinel.json"
    sentinel.write_text("{}")
    monkeypatch.setattr(pipeline_state, "get_legacy_sentinel_path", lambda: sentinel)


@pytest.fixture
def no_state(tmp_path, monkeypatch):
    """Point PIPELINE_STATE_FILE at a path that does not exist."""
    missing = tmp_path / "absent_pipeline_state.json"
    monkeypatch.setenv("PIPELINE_STATE_FILE", str(missing))
    return missing


@pytest.fixture
def plain_state(tmp_path, monkeypatch):
    """Write an UNSIGNED, fresh, explicitly-invoked pipeline state."""

    def _make(**fields) -> Path:
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "regression-1811",
            "explicitly_invoked": True,
        }
        state.update(fields)
        path = tmp_path / "implement_pipeline_state.json"
        path.write_text(json.dumps(state))
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(path))
        return path

    return _make


@pytest.fixture
def signed_state(tmp_path, monkeypatch):
    """Write an HMAC-signed pipeline state and point the hook at it."""

    def _make(**fields) -> Path:
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "regression-1811-signed",
            "explicitly_invoked": False,
        }
        state.update(fields)
        path = tmp_path / "implement_pipeline_state.json"
        path.write_text(json.dumps(sign_state(state, "test-session")))
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(path))
        return path

    return _make


def _as_agent(monkeypatch, name) -> None:
    """Set (or clear) the active agent identity via CLAUDE_AGENT_NAME."""
    if name is None:
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_AGENT_NAME", name)
    monkeypatch.setattr(hook, "_agent_type", "", raising=False)


def _write_payload() -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": CODE_TARGET, "content": "def f():\n    return 1\n"},
    }


def _run_hook_main(payload: dict) -> List[Tuple[str, str]]:
    """Drive ``unified_pre_tool.main()`` and capture its decision.

    ``patch.object(hook, "output_decision")`` (not the string form) so a
    reloaded module in another test file cannot silently swallow the capture.
    """
    calls: List[Tuple[str, str]] = []

    def capture(decision, reason, **_kwargs):
        calls.append((decision, reason))
        raise SystemExit(0)

    with patch("sys.stdin", StringIO(json.dumps(payload))):
        with patch.object(hook, "output_decision", side_effect=capture):
            try:
                hook.main()
            except SystemExit:
                pass
    return calls


def _workflow_denied(calls: List[Tuple[str, str]]) -> bool:
    return any(d == "deny" and "WORKFLOW ENFORCEMENT" in r for d, r in calls)


# ---------------------------------------------------------------------------
# 0. The normalization contract itself (the single fix point)
# ---------------------------------------------------------------------------


class TestNormalizationContract:
    """Normalization happens ONCE, at the identity source, validating BOTH halves."""

    def test_registered_namespaces_constant_exists(self):
        assert hasattr(hook, "REGISTERED_PLUGIN_NAMESPACES"), (
            "The fix must declare the registered plugin namespaces explicitly; "
            "stripping an arbitrary prefix is a privilege-escalation hole."
        )
        assert isinstance(hook.REGISTERED_PLUGIN_NAMESPACES, frozenset)
        assert hook.REGISTERED_PLUGIN_NAMESPACES, "namespace allow-list must not be empty"

    def test_constant_matches_the_plugin_manifest(self):
        """Cross-validate against plugin.json rather than trusting one hardcoded copy."""
        manifest_name = json.loads(PLUGIN_MANIFEST.read_text())["name"]
        assert manifest_name in hook.REGISTERED_PLUGIN_NAMESPACES, (
            f"Plugin manifest declares namespace {manifest_name!r} but the hook's "
            f"allow-list is {sorted(hook.REGISTERED_PLUGIN_NAMESPACES)}"
        )

    @pytest.mark.parametrize("role", ["implementer", "test-master", "doc-master"])
    def test_registered_namespace_plus_pipeline_role_normalizes(self, monkeypatch, role):
        """All three roles, including the hyphenated ones a naive regex would split."""
        _as_agent(monkeypatch, f"autonomous-dev:{role}")
        assert hook._get_active_agent_name() == role

    @pytest.mark.parametrize("raw", UNNAMESPACED_IDENTITIES)
    def test_unnamespaced_identities_pass_through(self, monkeypatch, raw):
        _as_agent(monkeypatch, raw)
        assert hook._get_active_agent_name() == raw

    def test_case_is_still_normalized(self, monkeypatch):
        _as_agent(monkeypatch, "AUTONOMOUS-DEV:Implementer")
        assert hook._get_active_agent_name() == "implementer"

    def test_agent_type_stdin_source_is_also_normalized(self, monkeypatch):
        """The stdin ``agent_type`` source has priority and must normalize too."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setattr(hook, "_agent_type", "autonomous-dev:doc-master")
        assert hook._get_active_agent_name() == "doc-master"

    @pytest.mark.parametrize("spoof", SPOOFED_IDENTITIES)
    def test_spoofed_identities_keep_their_raw_name(self, monkeypatch, spoof):
        """CONTROL for the forbidden fix: split(':')[-1] would return 'implementer'."""
        _as_agent(monkeypatch, spoof)
        resolved = hook._get_active_agent_name()
        assert resolved == spoof.lower()
        assert resolved not in hook.PIPELINE_AGENTS

    @pytest.mark.parametrize("raw", MALFORMED_IDENTITIES)
    def test_malformed_colon_forms_keep_their_raw_name(self, monkeypatch, raw):
        _as_agent(monkeypatch, raw)
        resolved = hook._get_active_agent_name()
        assert resolved == raw
        assert resolved not in hook.PIPELINE_AGENTS

    def test_registered_namespace_with_non_pipeline_role_is_unchanged(self, monkeypatch):
        """Both halves are validated — a real namespace is not enough on its own."""
        _as_agent(monkeypatch, "autonomous-dev:reviewer")
        assert hook._get_active_agent_name() == "autonomous-dev:reviewer"


# ---------------------------------------------------------------------------
# 1. POSITIVE A — _is_pipeline_active() name branch (site ~:2657)
# ---------------------------------------------------------------------------


class TestPositiveAPipelineActiveNameBranch:
    """With NO state file, only the agent-name branch can report an active pipeline."""

    def test_namespaced_implementer_is_pipeline_active(self, monkeypatch, no_state):
        _as_agent(monkeypatch, "autonomous-dev:implementer")
        assert hook._is_pipeline_active() is True

    def test_unprefixed_implementer_is_pipeline_active(self, monkeypatch, no_state):
        """Positive control: the instrument reports True for the known-good identity."""
        _as_agent(monkeypatch, "implementer")
        assert hook._is_pipeline_active() is True

    @pytest.mark.parametrize("identity", ["main", None])
    def test_coordinator_is_not_pipeline_active(self, monkeypatch, no_state, identity):
        """Negative control: the instrument can return False."""
        _as_agent(monkeypatch, identity)
        assert hook._is_pipeline_active() is False

    @pytest.mark.parametrize("spoof", CONSUMER_SPOOFS)
    def test_spoofed_identity_is_not_pipeline_active(self, monkeypatch, no_state, spoof):
        _as_agent(monkeypatch, spoof)
        assert hook._is_pipeline_active() is False

    def test_namespaced_non_pipeline_role_is_not_pipeline_active(self, monkeypatch, no_state):
        _as_agent(monkeypatch, "autonomous-dev:reviewer")
        assert hook._is_pipeline_active() is False

    def test_name_branch_does_not_manufacture_a_sentinel(self, monkeypatch, no_state):
        """Issue #1779 (AC3) must survive the fix: refresh, never create."""
        _as_agent(monkeypatch, "autonomous-dev:implementer")
        assert hook._is_pipeline_active() is True
        assert not no_state.exists()


# ---------------------------------------------------------------------------
# 2. POSITIVE B — validate_agent_authorization early allow (site ~:6548)
# ---------------------------------------------------------------------------


class TestPositiveBAgentAuthorization:
    """A live pipeline + a registered namespaced pipeline agent => authorized."""

    @pytest.fixture(autouse=True)
    def live_pipeline(self, plain_state):
        plain_state()

    @pytest.mark.parametrize("identity", ["autonomous-dev:implementer", "implementer"])
    def test_pipeline_agent_is_authorized(self, monkeypatch, identity):
        """The namespaced form plus its unprefixed positive control."""
        _as_agent(monkeypatch, identity)
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": CODE_TARGET, "content": "def f():\n    return 1\n"}
        )
        assert decision == "allow"
        assert "Pipeline agent" in reason

    @pytest.mark.parametrize("identity", CONSUMER_SPOOFS + ["main"])
    def test_unregistered_identity_is_not_authorized(self, monkeypatch, identity):
        """CONTROL for the forbidden fix, plus the coordinator negative control."""
        _as_agent(monkeypatch, identity)
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": CODE_TARGET, "content": "def f():\n    return 1\n"}
        )
        assert decision == "deny"
        assert "Pipeline agent" not in reason


# ---------------------------------------------------------------------------
# 3. POSITIVE C — the #1467 alignment-verdict escalation gate (site ~:6538)
#    This is the FAIL-OPEN arm: pre-fix the namespaced agent was ALLOWED.
# ---------------------------------------------------------------------------


class TestPositiveCAlignmentVerdictEscalationFires:
    """A present-but-disallowed alignment verdict must stop a namespaced agent too.

    ``explicitly_invoked`` is False on purpose: it disables the Issue #585 /
    #528 deny paths, so the ONLY thing that can produce a deny here is the
    #1467 gate at the membership site. Pre-fix this returns
    ``('allow', 'Active /implement pipeline detected via state file')``.
    """

    @pytest.mark.parametrize(
        "tool,tool_input,verdict",
        [
            ("Write", {"file_path": CODE_TARGET, "content": "x = 1"}, "escalate"),
            ("Write", {"file_path": CODE_TARGET, "content": "x = 1"}, "block"),
            ("Edit", {"file_path": CODE_TARGET, "old_string": "a", "new_string": "b"},
             "escalate"),
        ],
    )
    def test_namespaced_implementer_is_escalation_blocked(
        self, monkeypatch, signed_state, tool, tool_input, verdict
    ):
        signed_state(alignment_passed=False, alignment_verdict=verdict)
        _as_agent(monkeypatch, "autonomous-dev:implementer")
        decision, reason = hook.validate_agent_authorization(tool, tool_input)
        assert decision == "deny", f"#1467 gate failed open: {reason}"
        assert "Issue #1467" in reason
        assert verdict in reason

    def test_unprefixed_implementer_is_escalation_blocked(self, monkeypatch, signed_state):
        """Positive control: the harness CAN observe the #1467 deny."""
        signed_state(alignment_passed=False, alignment_verdict="escalate")
        _as_agent(monkeypatch, "implementer")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": CODE_TARGET, "content": "x = 1"}
        )
        assert decision == "deny"
        assert "Issue #1467" in reason

    def test_non_pipeline_agent_does_not_trip_the_1467_gate(self, monkeypatch, signed_state):
        """Negative control: the harness CAN observe the absence of the #1467 deny."""
        signed_state(alignment_passed=False, alignment_verdict="escalate")
        _as_agent(monkeypatch, "researcher")
        _decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": CODE_TARGET, "content": "x = 1"}
        )
        assert "Issue #1467" not in reason

    def test_allowed_verdict_does_not_block_namespaced_agent(self, monkeypatch, signed_state):
        """The gate must fire on disallowed verdicts only — not on every write."""
        signed_state(alignment_passed=True, alignment_verdict="auto_pass")
        _as_agent(monkeypatch, "autonomous-dev:implementer")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": CODE_TARGET, "content": "x = 1"}
        )
        assert decision == "allow"
        assert "Issue #1467" not in reason

    def test_read_tool_is_not_gated_for_namespaced_agent(self, monkeypatch, signed_state):
        """Scope check: the #1467 gate covers Write/Edit only."""
        signed_state(alignment_passed=False, alignment_verdict="escalate")
        _as_agent(monkeypatch, "autonomous-dev:implementer")
        decision, reason = hook.validate_agent_authorization(
            "Read", {"file_path": CODE_TARGET}
        )
        assert decision == "allow"
        assert "Issue #1467" not in reason


# ---------------------------------------------------------------------------
# 4. main() native fast-path workflow block (site ~:9730)
# ---------------------------------------------------------------------------


class TestWorkflowBlockNativeFastPath:
    """The #528 coordinator block must keep refusing spoofs and the coordinator.

    Instrument controls (MEASURED before the fix): ``main`` and an unset
    identity produce the WORKFLOW ENFORCEMENT deny; ``implementer`` does not.
    The target path is repo-relative because Issue #1408 exempts every
    ``/tmp`` and ``/var/folders`` path (including ``tmp_path``) from this gate.
    """

    @pytest.fixture(autouse=True)
    def enforce_block(self, monkeypatch, plain_state):
        plain_state()
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")

    @pytest.mark.parametrize("identity", CONSUMER_SPOOFS + ["main", None])
    def test_unregistered_identity_is_blocked(self, monkeypatch, identity):
        """Spoofs and the coordinator alike: split(':')[-1] would free the spoofs."""
        _as_agent(monkeypatch, identity)
        assert _workflow_denied(_run_hook_main(_write_payload()))

    def test_unprefixed_implementer_is_not_blocked(self, monkeypatch):
        """Negative control for the instrument: a real pipeline agent passes."""
        _as_agent(monkeypatch, "implementer")
        assert not _workflow_denied(_run_hook_main(_write_payload()))

    def test_namespaced_implementer_is_not_blocked(self, monkeypatch):
        """The self-contradictory block: 'delegate to the implementer' TO the implementer."""
        _as_agent(monkeypatch, "autonomous-dev:implementer")
        calls = _run_hook_main(_write_payload())
        assert not _workflow_denied(calls), (
            f"namespaced implementer told to delegate to itself: {calls}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

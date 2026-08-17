#!/usr/bin/env python3
"""Unit coverage for the Issue #1512 phantom classifier and the explicit reaper.

The acceptance gate (``test_issue_1512_phantom_steals_generation_token.py``)
proves the end-to-end behaviour through the real SubagentStop hook. This file
pins the two new primitives directly, including the cases the end-to-end test
cannot reach cheaply:

* the classifier's truth table, including both UNKNOWN branches that keep the
  fix from being over-broad;
* the #1179 async-flush control — a transcript that appears *after* the hook
  fires must still classify REAL;
* ``reap_if_stale``'s full matrix, including "corrupt is NOT reaped", which
  matches the pre-split behaviour of ``is_active()`` (its JSONDecodeError branch
  returned before ever reaching the unlink);
* the ``__phantom_stop__:`` audit record — written for typed stops, suppressed
  for untyped ones.

Issue: #1512
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import threading
import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_LIB = _ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS = _ROOT / "plugins" / "autonomous-dev" / "hooks"
for _p in (str(_LIB), str(_HOOKS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import agent_dispatch_sentinel as ads  # noqa: E402
import subagent_invocation_cache as sic  # noqa: E402

_SESSION = "phantom-classifier-1512"


@pytest.fixture
def ust(tmp_path, monkeypatch):
    """Reload the tracker with ``HOME`` redirected into ``tmp_path``.

    ``_validate_transcript_path`` only accepts paths under ``~/.claude``, so the
    classifier's REAL/PHANTOM branches are only reachable when the test owns
    ``HOME``.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    if "unified_session_tracker" in sys.modules:
        module = importlib.reload(sys.modules["unified_session_tracker"])
    else:
        module = importlib.import_module("unified_session_tracker")
    return module


@pytest.fixture
def transcript_dir(tmp_path):
    d = tmp_path / ".claude" / "projects" / "p" / "subagents"
    d.mkdir(parents=True, exist_ok=True)
    return d


class TestPhantomClassifierTruthTable:
    """Deterministic predicate over one string, evaluated before any mutation."""

    def test_empty_path_is_unknown_not_phantom(self, ust):
        """The #1087 recovery contract depends on this staying False."""
        assert ust._is_phantom_subagent_stop("", grace_seconds=0) is False

    def test_path_outside_claude_home_is_unknown(self, ust, tmp_path):
        """``_validate_transcript_path`` is the containment gate.

        A path we are not allowed to reason about tells us nothing, so it must
        classify UNKNOWN even though the file genuinely does not exist.
        """
        outside = tmp_path / "elsewhere" / "agent-nope.jsonl"
        assert not outside.exists()
        assert ust._is_phantom_subagent_stop(str(outside), grace_seconds=0) is False

    def test_existing_transcript_is_real(self, ust, transcript_dir):
        p = transcript_dir / "agent-real0000000000000.jsonl"
        p.write_text(json.dumps({"type": "assistant"}) + "\n")

        assert ust._is_phantom_subagent_stop(str(p), grace_seconds=0) is False

    def test_validated_but_absent_transcript_is_phantom(self, ust, transcript_dir):
        p = transcript_dir / "agent-phantom00000000.jsonl"
        assert not p.exists()

        assert ust._is_phantom_subagent_stop(str(p), grace_seconds=0) is True

    def test_late_appearing_transcript_classifies_real(self, ust, transcript_dir):
        """Issue #1179 control: the async-flush race must not read as phantom.

        The measured floor for ``stop_timestamp - transcript_birthtime`` over 55
        real stops was 44.7s, so this race is not expected to occur in
        production. The grace window exists so that if it ever does, a genuine
        dispatch is not misclassified.
        """
        p = transcript_dir / "agent-late00000000000.jsonl"

        def _write_later() -> None:
            time.sleep(0.1)
            p.write_text(json.dumps({"type": "assistant"}) + "\n")

        writer = threading.Thread(target=_write_later)
        writer.start()
        try:
            assert ust._is_phantom_subagent_stop(str(p), grace_seconds=1.0) is False
        finally:
            writer.join()

    def test_classifier_never_raises(self, ust):
        """Any unexpected input degrades to UNKNOWN, never to an exception."""
        assert ust._is_phantom_subagent_stop("\x00bad\x00path", grace_seconds=0) is False

    def test_grace_constant_is_documented_and_small(self, ust):
        """The grace is belt-and-braces, not a tuning knob."""
        assert 0 < ust.PHANTOM_TRANSCRIPT_GRACE_SECONDS <= 1.0
        assert 0 < ust.PHANTOM_TRANSCRIPT_POLL_SECONDS < ust.PHANTOM_TRANSCRIPT_GRACE_SECONDS


class TestReapIfStale:
    """The explicit half of what ``is_active()`` used to do implicitly."""

    def test_absent_sentinel_is_not_reaped(self, tmp_path):
        assert ads.reap_if_stale(repo_root=tmp_path) is False

    def test_fresh_sentinel_survives(self, tmp_path):
        ads.write("implementer", repo_root=tmp_path, generation="gen-fresh")
        p = tmp_path / ads._SENTINEL_REL

        assert ads.reap_if_stale(repo_root=tmp_path) is False
        assert p.exists()
        assert ads.is_active(repo_root=tmp_path) is True

    def test_stale_sentinel_is_reaped(self, tmp_path):
        ads.write("implementer", repo_root=tmp_path, generation="gen-stale")
        p = tmp_path / ads._SENTINEL_REL
        data = json.loads(p.read_text())
        old = time.time() - (ads.DEFAULT_TTL_SECONDS + 60)
        data["timestamp"] = old
        data["armed_at"] = old
        p.write_text(json.dumps(data))

        assert ads.reap_if_stale(repo_root=tmp_path) is True
        assert not p.exists()

    def test_past_ceiling_sentinel_is_reaped(self, tmp_path):
        """Issue #1479 ceiling: fresh timestamp, ancient armed_at."""
        ads.write("implementer", repo_root=tmp_path, generation="gen-ceiling")
        p = tmp_path / ads._SENTINEL_REL
        data = json.loads(p.read_text())
        data["timestamp"] = time.time()
        data["armed_at"] = time.time() - (ads.MAX_LIFETIME_SECONDS + 60)
        p.write_text(json.dumps(data))

        assert ads.reap_if_stale(repo_root=tmp_path) is True
        assert not p.exists()

    def test_corrupt_sentinel_is_not_reaped(self, tmp_path):
        """Matches pre-split behaviour: the JSONDecodeError branch never unlinked.

        Corruption has no ordinary cause now that writes are atomic, so the
        bytes are left on disk as evidence for the operator.
        """
        p = tmp_path / ads._SENTINEL_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{truncated")

        assert ads.reap_if_stale(repo_root=tmp_path) is False
        assert p.exists()

    def test_non_dict_payload_is_not_reaped(self, tmp_path):
        p = tmp_path / ads._SENTINEL_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(["not", "a", "dict"]))

        assert ads.reap_if_stale(repo_root=tmp_path) is False
        assert p.exists()

    def test_reap_then_is_active_reproduces_old_gate_outcome(self, tmp_path):
        """The wiring at unified_pre_tool: reap first, then read.

        The gate's observable outcome for a stale sentinel is unchanged — file
        unlinked, ``is_active()`` sees an absent file, deny.
        """
        ads.write("implementer", repo_root=tmp_path, generation="gen-gate")
        p = tmp_path / ads._SENTINEL_REL
        data = json.loads(p.read_text())
        old = time.time() - (ads.DEFAULT_TTL_SECONDS + 60)
        data["timestamp"] = old
        data["armed_at"] = old
        p.write_text(json.dumps(data))

        ads.reap_if_stale(repo_root=tmp_path)

        assert not p.exists()
        assert ads.is_active(repo_root=tmp_path) is False


class TestGateWiringIsUnchanged:
    """AC7/AC8: splitting the reap out must not change what the gate decides.

    ``unified_pre_tool`` was the sole production consumer of the implicit reap.
    These exercise the real hook so the guard is watched both REFUSING the bad
    case and PERMITTING the legitimate one — a guard observed doing only one of
    those is unproven.
    """

    @pytest.fixture(autouse=True)
    def gate(self, tmp_path, monkeypatch):
        import unified_pre_tool as hook

        self.hook = hook
        self.repo_root = tmp_path / "test_repo"
        (self.repo_root / ".git").mkdir(parents=True)
        (self.repo_root / ".claude" / "local").mkdir(parents=True)
        (self.repo_root / ".claude" / "commands").mkdir(parents=True)
        (self.repo_root / ".claude" / "commands" / "implement.md").write_text("# impl")
        plugin_dir = self.repo_root / "plugins" / "autonomous-dev"
        (plugin_dir / "agents").mkdir(parents=True)
        (plugin_dir / "agents" / "implementer.md").write_text("agent content")

        self.state_file = tmp_path / "implement_pipeline_state.json"
        self.state_file.write_text(
            json.dumps(
                {
                    "session_id": "test-session-1512",
                    "step": "implement",
                    "timestamp": time.time(),
                }
            )
        )
        monkeypatch.chdir(self.repo_root)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-1512")
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(self.state_file))
        ads.clear(self.repo_root)
        self.sentinel_path = self.repo_root / ads._SENTINEL_REL

    def _decisions(self):
        """Run the hook on a protected-path Edit and capture its decisions."""
        payload = json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(
                        self.repo_root
                        / "plugins/autonomous-dev/agents/implementer.md"
                    ),
                    "old_string": "agent content",
                    "new_string": "modified content",
                },
            }
        )
        calls: list[tuple] = []

        def _capture(decision, reason, **kwargs):
            calls.append((decision, reason))
            if decision == "deny":
                raise SystemExit(0)

        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.argv", ["unified_pre_tool.py"]):
                with patch.object(self.hook, "output_decision", side_effect=_capture):
                    with patch("sys.exit", side_effect=SystemExit):
                        try:
                            self.hook.main()
                        except SystemExit:
                            pass
        return calls

    def test_stale_sentinel_still_denies_and_is_reaped_at_the_gate(self):
        """The exact behaviour the implicit reap used to provide.

        A stale sentinel must not authorize a protected write, and the gate
        must still clean it up — now via the explicit reap_if_stale() call
        wired immediately before the is_active() check.
        """
        ads.write("implementer", repo_root=self.repo_root, generation="gen-stale-gate")
        data = json.loads(self.sentinel_path.read_text())
        old = time.time() - (ads.DEFAULT_TTL_SECONDS + 60)
        data["timestamp"] = old
        data["armed_at"] = old
        self.sentinel_path.write_text(json.dumps(data))

        calls = self._decisions()

        assert any(
            d == "deny" and "Issue #1296" in r for d, r in calls
        ), f"a stale sentinel must not authorize a protected write; got {calls}"
        assert not self.sentinel_path.exists(), (
            "the gate must still reap the stale sentinel — reap_if_stale() is "
            "not wired before the is_active() check"
        )

    def test_fresh_sentinel_still_permits_and_survives_the_gate(self):
        """The permit half. A guard only watched refusing is unproven.

        Also pins that the reap wiring does not eat a LIVE sentinel — that
        failure mode would hold the #1435 hard floor open and is strictly worse
        than the bug #1512 fixes.
        """
        ads.write("implementer", repo_root=self.repo_root, generation="gen-live-gate")

        calls = self._decisions()

        assert not any(
            d == "deny" and "Issue #1296" in r for d, r in calls
        ), f"a live dispatch must be permitted; got {calls}"
        assert self.sentinel_path.exists(), "the gate reaped a LIVE sentinel"
        assert ads.is_active(repo_root=self.repo_root) is True


@pytest.fixture
def audit_harness(tmp_path, monkeypatch):
    """Drive the real SubagentStop hook and capture the JSONL entries written."""
    monkeypatch.setenv("HOME", str(tmp_path))

    sentinel_root = tmp_path / "repo"
    (sentinel_root / ".claude" / "local").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        ads,
        "_path",
        lambda repo_root=None: (
            Path(repo_root) if repo_root is not None else sentinel_root
        )
        / ads._SENTINEL_REL,
    )

    cache_file = tmp_path / "invocations.json"
    monkeypatch.setattr(sic, "cache_path", lambda sid: cache_file)

    if "unified_session_tracker" in sys.modules:
        module = importlib.reload(sys.modules["unified_session_tracker"])
    else:
        module = importlib.import_module("unified_session_tracker")

    monkeypatch.setattr(module, "_pop_cached_subagent_invocation", sic.pop_invocation)
    monkeypatch.setattr(module, "_DEFAULT_MARKER_DIR", tmp_path)

    entries: list[dict] = []
    monkeypatch.setattr(
        module, "_write_jsonl_entry", lambda **kw: (entries.append(kw) or True)
    )
    monkeypatch.setattr(module, "track_basic_session", lambda *a, **k: None)
    monkeypatch.setattr(module, "track_pipeline_completion", lambda *a, **k: None)
    monkeypatch.setattr(module, "_get_current_issue_number", lambda: None)

    import pipeline_completion_state as pcs

    completions: list[dict] = []
    monkeypatch.setattr(
        pcs, "record_agent_completion", lambda **kw: completions.append(kw)
    )

    transcripts = tmp_path / ".claude" / "projects" / "p" / "subagents"
    transcripts.mkdir(parents=True, exist_ok=True)

    class _H:
        entries_written = entries
        completions_recorded = completions
        transcript_dir = transcripts

        @staticmethod
        def phantom_transcript(name: str = "agent-phantom00000000.jsonl") -> str:
            return str(transcripts / name)

        @staticmethod
        def fire(agent_type: str, transcript_path: str, message: str) -> None:
            payload = json.dumps(
                {
                    "hook_event_name": "SubagentStop",
                    "agent_type": agent_type,
                    "session_id": _SESSION,
                    "agent_transcript_path": transcript_path,
                    "last_assistant_message": message,
                }
            )
            with patch("sys.stdin", StringIO(payload)):
                with patch.dict(
                    os.environ, {"CLAUDE_SESSION_ID": _SESSION}, clear=False
                ):
                    module.main()

    return _H


class TestPhantomAuditRecord:
    """AC9: greppable evidence, inert for downstream consumers."""

    def test_typed_phantom_writes_audit_entry(self, audit_harness):
        audit_harness.fire(
            "implementer",
            audit_harness.phantom_transcript(),
            "Agent completed without producing output",
        )

        phantom_entries = [
            e
            for e in audit_harness.entries_written
            if str(e.get("subagent_type", "")).startswith("__phantom_stop__:")
        ]
        assert len(phantom_entries) == 1, (
            "a rejected typed phantom must leave a greppable audit record"
        )
        assert phantom_entries[0]["subagent_type"] == "__phantom_stop__:implementer"

    def test_audit_branch_never_records_the_phantom_marker_as_a_completion(
        self, audit_harness
    ):
        """AC9: the audit branch does not call ``record_agent_completion``.

        DELIBERATE NON-CHANGE, stated explicitly so a future reader does not
        "fix" it: the #1512 classifier does exactly two fewer things — no cache
        pop, no sentinel clear. Everything downstream of that point, including
        the ordinary completion recording that a typed stop with substantive
        output still reaches, is untouched. Suppressing that too would change
        the #802 completeness gate's input set and risks reintroducing the
        #1387/#1412 false-negative class that blocks legitimate commits.

        What must hold is narrower and is what this test pins: the
        ``__phantom_stop__:`` marker itself never leaks into the gate as an
        agent identity.
        """
        audit_harness.fire(
            "implementer",
            audit_harness.phantom_transcript(),
            "Agent completed without producing output",
        )

        recorded_types = [
            str(c.get("agent_type", "")) for c in audit_harness.completions_recorded
        ]
        assert not any(t.startswith("__") for t in recorded_types), (
            f"a __-prefixed audit marker reached the #802 gate: {recorded_types}"
        )

    def test_untyped_phantom_writes_no_audit_entry(self, audit_harness):
        """Untyped phantoms are the #1396 heartbeat class — silence, not noise.

        ~95 of ~113 SubagentStop events in a real run are untyped heartbeats.
        A record per firing would be a signal that cries wolf.
        """
        audit_harness.fire("", audit_harness.phantom_transcript("agent-untyped000.jsonl"), "")

        phantom_entries = [
            e
            for e in audit_harness.entries_written
            if str(e.get("subagent_type", "")).startswith("__phantom_stop__")
        ]
        assert phantom_entries == []

    def test_audit_marker_uses_the_inert_double_underscore_convention(
        self, audit_harness
    ):
        """``agent_output_health`` excludes all ``__``-prefixed subagent types,
        so the new marker is automatically invisible to ghost detection."""
        audit_harness.fire(
            "reviewer",
            audit_harness.phantom_transcript("agent-phantom-rev0000.jsonl"),
            "Agent completed without producing output",
        )

        markers = [
            e["subagent_type"]
            for e in audit_harness.entries_written
            if "phantom_stop" in str(e.get("subagent_type", ""))
        ]
        assert markers == ["__phantom_stop__:reviewer"]
        assert all(m.startswith("__") for m in markers)

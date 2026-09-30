"""Foreground native Agent reservation and one-shot PostToolUse credit."""

import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev"
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "hooks"))

import pipeline_completion_state as pcs  # noqa: E402 - plugin paths above
import session_activity_logger as logger  # noqa: E402 - plugin paths above
import unified_session_tracker as tracker  # noqa: E402 - plugin paths above


@pytest.fixture
def native_state(monkeypatch, tmp_path):
    monkeypatch.setattr(pcs, "_state_file_path", lambda *_a, **_k: tmp_path / "ledger.json")
    monkeypatch.setattr(pcs, "_signed_native_agent_scope", lambda _s: {
        "run_id": "run1", "issue_number": 1807,
    })
    pcs._write_state("s", {"current_run_id": "run1", "native_origin": {"witness": {}},
                           "issue_run_starts": {"1807": "run1"}, "completions": {}})
    return tmp_path


def test_foreground_requires_explicit_false_and_signed_scope(native_state, monkeypatch):
    for value in (None, True, "false", 0):
        assert pcs.register_native_agent_dispatch("s", "u1", "reviewer", value) == "not_foreground"
    monkeypatch.setattr(pcs, "_signed_native_agent_scope", lambda _s: None)
    assert pcs.register_native_agent_dispatch("s", "u1", "reviewer", False) == "unbound_scope"
    monkeypatch.setattr(pcs, "_signed_native_agent_scope", lambda _s: {
        "run_id": "run1", "issue_number": 999,
    })
    assert pcs.register_native_agent_dispatch("s", "u1", "reviewer", False) == "issue_mismatch"


def test_non_native_agent_keeps_optional_background_default(monkeypatch, tmp_path):
    monkeypatch.setattr(pcs, "_state_file_path", lambda *_a, **_k: tmp_path / "plain.json")
    monkeypatch.setattr(pcs, "_signed_native_agent_scope", lambda _s: None)
    assert pcs.register_native_agent_dispatch("plain", "u1", "reviewer", None) == "inactive"
    assert pcs.register_native_agent_dispatch("plain", "u2", "reviewer", True) == "inactive"
    # If the signed carrier survives a lost ledger, foreground enforcement
    # still applies and the missing ledger cannot grant a reservation.
    monkeypatch.setattr(pcs, "_signed_native_agent_scope", lambda _s: {
        "run_id": "run1", "issue_number": 1807,
    })
    assert pcs.register_native_agent_dispatch("plain", "u3", "reviewer", None) == "not_foreground"
    assert pcs.register_native_agent_dispatch("plain", "u3b", "reviewer", True) == "not_foreground"
    assert pcs.register_native_agent_dispatch("plain", "u4", "reviewer", False) == "inactive"


def test_native_owner_does_not_inherit_unknown_session_credit(monkeypatch, tmp_path):
    monkeypatch.setattr(pcs, "_state_file_path", lambda session, **_k: tmp_path / f"{session}.json")
    monkeypatch.setattr(pcs, "_signed_native_agent_scope", lambda session: (
        {"run_id": "run1", "issue_number": 1807} if session == "S" else None
    ))
    pcs._write_state("S", {"current_run_id": "run1", "native_origin": {"witness": {}},
                           "issue_run_starts": {"1807": "run1"}, "completions": {}})
    pcs._write_state("unknown", {"completions": {"1807": {"reviewer": True}}})
    assert pcs.get_completed_agents("S", issue_number=1807) == set()
    # Even a lost named ledger must not reinstate the cross-session fallback.
    (tmp_path / "S.json").unlink()
    assert pcs.get_completed_agents("S", issue_number=1807) == set()


def test_public_legacy_writer_cannot_mint_native_specialist_credit(native_state, monkeypatch):
    pcs.record_agent_completion("s", "reviewer", issue_number=1807, run_id="run1")
    assert pcs.get_completed_agents("s", issue_number=1807) == set()
    assert pcs._read_state("s").get("completion_run_ids", {}) == {}

    # The signed carrier alone still prevents fallback after ledger loss.
    monkeypatch.setattr(pcs, "_state_file_path", lambda *_a, **_k: native_state / "lost.json")
    pcs.record_agent_completion("s", "reviewer", issue_number=1807)
    assert pcs.get_completed_agents("s", issue_number=1807) == set()

    # The legacy route and virtual pytest marker retain their own behavior.
    monkeypatch.setattr(pcs, "_signed_native_agent_scope", lambda _s: None)
    pcs.record_agent_completion("s", "reviewer", issue_number=1807)
    assert pcs.get_completed_agents("s", issue_number=1807) == {"reviewer"}


def test_lost_native_ledger_still_blocks_pre_hook(monkeypatch, capsys):
    monkeypatch.setenv("ACTIVITY_LOGGING", "false")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setattr(pcs, "register_native_agent_dispatch", lambda *_a: "inactive")
    monkeypatch.setattr(pcs, "native_agent_join_active", lambda *_a: True)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "S",
        "tool_use_id": "u1", "tool_input": {"subagent_type": "reviewer", "run_in_background": False},
    })))
    with pytest.raises(SystemExit):
        logger.main()
    assert json.loads(capsys.readouterr().out)["decision"] == "block"


def test_native_dispatch_waits_for_exact_post_completion(native_state):
    assert pcs.register_native_agent_dispatch("s", "u1", "reviewer", False) == "registered"
    assert pcs.register_native_agent_dispatch("s", "u2", "reviewer", False) == "in_flight"
    assert pcs.get_completed_agents("s", issue_number=1807) == set()
    assert pcs.join_native_agent_result("s", "u1", "a1", "completed", False) == "completed"
    assert pcs.register_native_agent_dispatch("s", "u2", "reviewer", False) == "registered"
    assert pcs.get_completed_agents("s", issue_number=1807) == set()
    assert pcs.join_native_agent_result("s", "u2", "a2", "completed", False) == "completed"
    assert pcs.get_completed_agents("s", issue_number=1807) == {"reviewer"}
    assert pcs.join_native_agent_result("s", "u1", "a1", "completed", False) == "unjoined"


def test_failed_native_dispatch_blocks_next_reservation(native_state):
    assert pcs.register_native_agent_dispatch("s", "u1", "reviewer", False) == "registered"
    assert pcs.join_native_agent_result("s", "u1", "a1", "failed", True) == "failed"
    assert pcs.register_native_agent_dispatch("s", "u2", "security-auditor", False) == "in_flight"


def test_launch_only_failure_phantom_and_rebind_do_not_credit(native_state):
    assert pcs.register_native_agent_dispatch("s", "u1", "reviewer", False) == "registered"
    assert pcs.join_native_agent_result("s", "u1", "a1", "running", False) == "failed"
    assert pcs.join_native_agent_result("s", "u1", "a1", "completed", False) == "unjoined"
    assert pcs.register_native_agent_dispatch("s", "u2", "reviewer", False) == "in_flight"
    assert pcs.get_completed_agents("s", issue_number=1807) == set()


def test_rebound_reservation_does_not_credit(native_state):
    assert pcs.register_native_agent_dispatch("s", "u4", "reviewer", False) == "registered"
    pcs._locked_rmw("s", lambda state: state.update(current_run_id="run2"))
    assert pcs.join_native_agent_result("s", "u4", "a4", "completed", False) == "rebound"
    assert pcs.get_completed_agents("s", issue_number=1807) == set()


def test_missing_issue_ownership_and_write_failure_refuse(native_state, monkeypatch):
    pcs._locked_rmw("s", lambda state: state.pop("issue_run_starts", None))
    assert pcs.register_native_agent_dispatch("s", "u1", "reviewer", False) == "issue_mismatch"
    pcs._locked_rmw("s", lambda state: state.update(issue_run_starts={"1807": "run1"}))
    monkeypatch.setattr(pcs, "_write_state", lambda *_a, **_k: None)
    assert pcs.register_native_agent_dispatch("s", "u2", "reviewer", False) == "write_failed"


def test_pre_hook_blocks_background_and_foreign_env_before_cache(monkeypatch, capsys):
    monkeypatch.setenv("ACTIVITY_LOGGING", "false")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "T")
    calls = []
    monkeypatch.setattr(logger, "_sic_cache_invocation", lambda *_a, **_k: calls.append(True))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "S",
        "tool_use_id": "u1", "tool_input": {"subagent_type": "reviewer", "run_in_background": False},
    })))
    with pytest.raises(SystemExit):
        logger.main()
    assert json.loads(capsys.readouterr().out)["decision"] == "block"
    assert calls == []
    monkeypatch.setenv("CLAUDE_SESSION_ID", "S")
    monkeypatch.setattr(pcs, "register_native_agent_dispatch", lambda *_a: "not_foreground")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "S",
        "tool_use_id": "u1", "tool_input": {"subagent_type": "reviewer", "run_in_background": True},
    })))
    with pytest.raises(SystemExit):
        logger.main()
    assert json.loads(capsys.readouterr().out)["decision"] == "block"
    assert calls == []


def test_post_hook_camel_case_completed_only(monkeypatch, tmp_path):
    monkeypatch.setenv("ACTIVITY_LOGGING", "false")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setattr(logger, "_find_log_dir", lambda: tmp_path)
    monkeypatch.setattr(logger, "_check_and_log_heartbeat", lambda *_a: None)
    seen = []
    monkeypatch.setattr(pcs, "join_native_agent_result", lambda *a: seen.append(a) or "completed")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "PostToolUse", "tool_name": "Agent", "session_id": "s",
        "tool_use_id": "u1", "tool_input": {"subagent_type": "reviewer"},
        "tool_response": {"agentId": "a1", "status": "completed"},
    })))
    with pytest.raises(SystemExit):
        logger.main()
    assert seen == [("s", "u1", "a1", "completed", False)]


def test_stop_hook_never_credits_native_run(monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_ID", "T")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "SubagentStop", "session_id": "S", "agent_type": "reviewer",
        "agent_id": "a1", "agent_status": "success",
    })))
    monkeypatch.setattr(pcs, "record_agent_completion", lambda *_a, **_k: pytest.fail("stop credit"))
    assert tracker.main() == 0


def test_plugin_native_stop_cannot_restore_legacy_credit_after_state_loss(
    monkeypatch, tmp_path,
):
    """The plugin route is non-crediting even with no readable run carriers."""
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setenv("TRACK_SESSIONS", "false")
    monkeypatch.setenv("AUTO_UPDATE_PROGRESS", "false")
    monkeypatch.setattr(sys, "argv", ["unified_session_tracker.py", "--native"])
    monkeypatch.setattr(pcs, "native_agent_join_active", lambda _s: False)
    heartbeats = []
    monkeypatch.setattr(
        pcs, "get_run_start_receipt",
        lambda session: "run1" if session == "legacy-control" else None,
    )
    monkeypatch.setattr(
        pcs, "ensure_sentinel_heartbeat", lambda session: heartbeats.append(session),
    )
    monkeypatch.setattr(
        pcs, "record_agent_completion",
        lambda *_a, **_k: pytest.fail("legacy completion credit"),
    )
    transcript = tmp_path / "agent-native-lost.jsonl"
    transcript.write_text('{"type":"assistant"}\n')
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "SubagentStop",
        "session_id": "native-lost-carriers",
        "agent_type": "reviewer",
        "agent_id": "native-lost",
        "agent_transcript_path": str(transcript),
        "last_assistant_message": "Completed review",
    })))
    assert tracker.main() == 0
    assert heartbeats == []

    # Positive control: the same legacy route still reaches the old writer.
    seen = []
    monkeypatch.setattr(sys, "argv", ["unified_session_tracker.py"])
    monkeypatch.setattr(
        pcs, "record_agent_completion", lambda **kwargs: seen.append(kwargs),
    )
    legacy_transcript = tmp_path / "agent-legacy-control.jsonl"
    legacy_transcript.write_text('{"type":"assistant"}\n')
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "SubagentStop",
        "session_id": "legacy-control",
        "agent_type": "reviewer",
        "agent_id": "legacy-control",
        "agent_transcript_path": str(legacy_transcript),
        "last_assistant_message": "Completed review",
    })))
    assert tracker.main() == 0
    assert len(seen) == 1
    assert heartbeats == ["legacy-control"]


def test_stale_run_receipt_agent_stop_cannot_create_bare_sentinel(monkeypatch, tmp_path):
    """A prior run ID in this session is not current pipeline authority."""
    sentinel = tmp_path / "implement_pipeline_state.json"
    transcript = tmp_path / "explore.jsonl"
    transcript.write_text('{"type":"assistant"}\n')
    monkeypatch.delenv("PIPELINE_STATE_FILE", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setenv("TRACK_SESSIONS", "false")
    monkeypatch.setenv("AUTO_UPDATE_PROGRESS", "false")
    monkeypatch.setattr(sys, "argv", ["unified_session_tracker.py", "--native"])
    monkeypatch.setattr(pcs, "get_run_start_receipt", lambda _s: "stale-prior-run")
    monkeypatch.setattr(pcs, "get_legacy_sentinel_path", lambda: sentinel)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "SubagentStop", "session_id": "same-session",
        "agent_type": "Explore", "agent_id": "explore-1",
        "agent_transcript_path": str(transcript),
        "last_assistant_message": "Read-only exploration is complete",
    })))
    assert tracker.main() == 0
    assert not sentinel.exists(), "a stale receipt must not mint recovered state"


def test_post_hook_rejects_foreign_env_before_join(monkeypatch):
    monkeypatch.setenv("ACTIVITY_LOGGING", "false")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "T")
    monkeypatch.setattr(pcs, "join_native_agent_result", lambda *_a: pytest.fail("foreign join"))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "PostToolUse", "tool_name": "Agent", "session_id": "S",
        "tool_use_id": "u1", "tool_response": {"agentId": "a1", "status": "completed"},
    })))
    with pytest.raises(SystemExit):
        logger.main()

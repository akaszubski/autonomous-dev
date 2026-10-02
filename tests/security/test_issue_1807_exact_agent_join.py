"""Foreground native Agent reservation and one-shot PostToolUse credit."""

import io
import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev"
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "hooks"))

import pipeline_completion_state as pcs  # noqa: E402 - plugin paths above
import pipeline_state as ps  # noqa: E402 - plugin paths above
import session_activity_logger as logger  # noqa: E402 - plugin paths above
import unified_session_tracker as tracker  # noqa: E402 - plugin paths above
import unified_pre_tool as guard  # noqa: E402 - plugin paths above
import agent_dispatch_sentinel as ads  # noqa: E402 - plugin paths above
import subagent_invocation_cache as invocation_cache  # noqa: E402 - plugin paths above
from tests.helpers.state_isolation import redirect_pipeline_state  # noqa: E402


@pytest.fixture
def real_native_state(monkeypatch, tmp_path):
    """Actual initializer/classifier/ledger chain, not a fabricated verdict."""
    redirect_pipeline_state(monkeypatch, tmp_path, ps, pcs)
    monkeypatch.setattr(ps, "get_state_path", lambda run: tmp_path / f"checkpoint-{run}.json")
    monkeypatch.setattr(ps, "get_lockfile_path", lambda run: tmp_path / f"lock-{run}")
    monkeypatch.setattr(guard, "get_legacy_sentinel_path", ps.get_legacy_sentinel_path)
    monkeypatch.setattr(guard, "_is_stale_session", lambda *_a: False)
    monkeypatch.setattr(ads, "_path", lambda *_a: tmp_path / "active-dispatch.json")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    state = pcs.initialize_native_run_from_event({
        "hook_event_name": "UserPromptExpansion", "command_name": "implement",
        "command_args": "#1807", "command_source": "user",
        "prompt": "/implement #1807", "session_id": "native-dispatch-owner",
    })
    assert state is not None
    monkeypatch.setenv("PIPELINE_STATE_FILE", str(ps.get_legacy_sentinel_path()))
    monkeypatch.setattr(guard, "_native_dispatch_input", {})
    return state


def _emit_guard(monkeypatch, capsys, state, decision, tool_id, owner=None):
    payload = {
        "hook_event_name": "PreToolUse", "tool_name": "Agent",
        "session_id": state["session_id"] if owner is None else owner,
        "tool_use_id": tool_id,
        "tool_input": {"subagent_type": "reviewer", "run_in_background": False},
    }
    monkeypatch.setattr(guard, "_session_id", payload["session_id"])
    monkeypatch.setattr(guard, "_native_dispatch_input", payload)
    guard.output_decision(decision, "frozen workflow decision")
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]


def test_namespaced_fix_ordering_through_actual_main(real_native_state, monkeypatch, capsys):
    state = pcs.initialize_native_run_from_event({
        "hook_event_name": "UserPromptExpansion", "command_name": "implement",
        "command_args": "--fix #1807", "command_source": "user",
        "prompt": "/implement --fix #1807", "session_id": real_native_state["session_id"],
    })
    assert state is not None and state["mode"] == "fix"
    prompt = (
        "Review the frozen diagnostic admission sequence against consumer intent. "
        "No product implementation or test-gate result exists in this run. Do not edit files, "
        "execute commands, read secrets, inspect directories, delegate work, or certify acceptance. "
        "If the guard permits this deliberately premature dispatch, report that unexpected outcome "
        "and stop; do not invent prerequisite completion or repair the workflow. This invocation "
        "is an externally supervised negative control for the existing fix-mode ordering guard, "
        "not an authorization to perform release review. Preserve uncertainty and provide no "
        "success claim about the wider workflow. The consumer scope permits bounded guard-admission "
        "observation only, excludes product changes and deployment, and leaves native Task lifecycle, "
        "child-session identity, security, full-workflow and release qualification open. No implementer "
        "output, changed-file evidence or passing pytest-gate receipt has been supplied for issue 1807."
    )

    def invoke(role, tool_id):
        payload = {
            "hook_event_name": "PreToolUse", "tool_name": "Agent",
            "session_id": state["session_id"], "tool_use_id": tool_id,
            "tool_input": {"subagent_type": role, "run_in_background": False, "prompt": prompt},
        }
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        with pytest.raises(SystemExit):
            guard.main()
        return json.loads(capsys.readouterr().out)["hookSpecificOutput"]

    first = invoke("autonomous-dev:reviewer", "premature-review")
    assert first["permissionDecision"] == "deny", first
    assert "implementer" in first["permissionDecisionReason"]
    assert "pytest-gate" in first["permissionDecisionReason"]
    assert pcs._read_state(state["session_id"]).get("native_agent_joins", {}) == {}
    assert pcs.get_launched_agents(state["session_id"], issue_number=1807) == set()
    positive = invoke("autonomous-dev:alignment-classifier", "alignment")
    assert positive["permissionDecision"] == "allow", positive
    assert pcs.join_native_agent_result(state["session_id"], "alignment", "alignment-agent", "completed", False) == "completed"
    second = invoke("autonomous-dev:reviewer", "still-premature")
    assert second["permissionDecision"] == "deny", second
    assert "implementer" in second["permissionDecisionReason"]
    joins = pcs._read_state(state["session_id"])["native_agent_joins"]
    assert set(joins) == {"alignment"}
    assert joins["alignment"]["agent_type"] == "autonomous-dev:alignment-classifier"
    assert pcs.get_completed_agents(state["session_id"], issue_number=1807) == {"alignment-classifier"}
    assert pcs.get_launched_agents(state["session_id"], issue_number=1807) == {"alignment-classifier"}


@pytest.mark.parametrize("decision,owner", [("allow", None), ("deny", None), ("allow", "foreign-owner")])
def test_native_output_trace_joins_actual_decision_without_forged_run(
    real_native_state, monkeypatch, capsys, decision, owner,
):
    state = real_native_state
    callback_owner = state["session_id"] if owner is None else owner
    payload = {
        "tool_name": "Agent", "session_id": callback_owner, "tool_use_id": "trace-call",
        "tool_input": {"subagent_type": "autonomous-dev:alignment-classifier", "run_in_background": False},
    }
    monkeypatch.setattr(guard, "_session_id", callback_owner)
    monkeypatch.setattr(guard, "_native_dispatch_input", payload)
    guard.output_decision(decision, "workflow verdict", system_message="Keep this human message")
    envelope = json.loads(capsys.readouterr().out)
    human, marker = envelope["systemMessage"].split("\nAUTONOMOUS_DEV_NATIVE_TRACE ")
    assert human == "Keep this human message"
    trace = json.loads(marker)
    assert trace["tool_use_id"] == "trace-call"
    assert trace["session_id"] == callback_owner
    assert trace["decision"] == envelope["hookSpecificOutput"]["permissionDecision"]
    if owner is None:
        assert trace["run_id"] == state["run_id"]
    else:
        assert "run_id" not in trace
        assert trace["decision"] == "deny"


@pytest.mark.parametrize("admitted_run", ["current-exact-run", None])
def test_allow_trace_uses_final_exact_join_not_preliminary_run(real_native_state, monkeypatch, capsys, admitted_run):
    state = real_native_state
    monkeypatch.setattr(pcs, "get_native_agent_run_id", lambda *_args: admitted_run)
    monkeypatch.setattr(guard, "_session_id", state["session_id"])
    monkeypatch.setattr(guard, "_native_dispatch_input", {
        "tool_name": "Agent", "session_id": state["session_id"], "tool_use_id": "race-trace",
        "tool_input": {"subagent_type": "autonomous-dev:alignment-classifier", "run_in_background": False},
    })
    guard.output_decision("allow", "workflow verdict")
    envelope = json.loads(capsys.readouterr().out)
    trace = json.loads(envelope["systemMessage"].split("AUTONOMOUS_DEV_NATIVE_TRACE ")[1])
    assert envelope["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert trace.get("run_id") == admitted_run
    assert trace.get("run_id") != state["run_id"]


def test_owned_role_typo_refuses_without_native_reservation(real_native_state, monkeypatch, capsys):
    state = real_native_state
    role = "autonomous-dev:reviewerr"
    payload = {
        "hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": state["session_id"],
        "tool_use_id": "owned-typo", "tool_input": {"subagent_type": role, "run_in_background": False},
    }
    monkeypatch.setattr(guard, "_session_id", state["session_id"])
    monkeypatch.setattr(guard, "_native_dispatch_input", payload)
    decision, reason = guard.validate_pipeline_ordering("Agent", payload["tool_input"])
    guard.output_decision(decision, reason)
    result = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert result["permissionDecision"] == "deny"
    assert "Unknown owned pipeline role" in result["permissionDecisionReason"]
    assert pcs._read_state(state["session_id"]).get("native_agent_joins", {}) == {}


def test_completion_alias_is_applied_only_after_raw_run_stamp_filter(real_native_state):
    state = real_native_state
    owner = state["session_id"]
    role = "autonomous-dev:implementer"
    assert pcs.register_native_agent_dispatch(owner, "implement", role, False) == "registered"
    assert pcs.join_native_agent_result(owner, "implement", "implement-agent", "completed", False) == "completed"
    assert pcs.get_completed_agents(owner, issue_number=1807) == {"implementer"}
    ledger = pcs._read_state(owner)
    ledger["completion_run_ids"]["1807"][role] = "superseded"
    pcs._write_state(owner, ledger)
    assert pcs.get_completed_agents(owner, issue_number=1807) == set()


@pytest.mark.parametrize("fault", [None, "foreign-owner", "wrong-run", "wrong-issue", "wrong-id", "partial-origin", "missing"])
def test_exact_native_join_reader_never_invents_attribution(real_native_state, fault):
    state = real_native_state
    owner = state["session_id"]
    assert pcs.register_native_agent_dispatch(owner, "joined", "autonomous-dev:alignment-classifier", False) == "registered"
    ledger = pcs._read_state(owner)
    if fault == "wrong-run":
        ledger["native_agent_joins"]["joined"]["run_id"] = "foreign-run"
    elif fault == "wrong-issue":
        ledger["native_agent_joins"]["joined"]["issue_number"] = 99
    elif fault == "wrong-id":
        ledger["native_agent_joins"]["joined"]["tool_use_id"] = "another"
    elif fault == "partial-origin":
        ledger["native_origin"] = {}
    pcs._write_state(owner, ledger)
    result = pcs.get_native_agent_run_id("foreign-owner" if fault == "foreign-owner" else owner,
                                         "missing" if fault == "missing" else "joined")
    assert result == (state["run_id"] if fault is None else None)
    if fault != "foreign-owner":
        assert pcs.get_launched_agents(owner, issue_number=1807) == (
            {"alignment-classifier"} if fault in (None, "missing") else set()
        )


@pytest.mark.parametrize("fault", ["run", "issue", "missing", "read-fault"])
def test_native_join_reader_refuses_changed_second_carrier(real_native_state, monkeypatch, fault):
    state = real_native_state
    owner = state["session_id"]
    assert pcs.register_native_agent_dispatch(owner, "joined", "autonomous-dev:alignment-classifier", False) == "registered"
    original_scope = pcs._signed_native_agent_scope
    scope = original_scope(owner)
    monkeypatch.setattr(pcs, "_signed_native_agent_scope", lambda _owner: scope)
    carrier = Path(os.environ["PIPELINE_STATE_FILE"])
    if fault == "missing":
        carrier.unlink()
    elif fault == "read-fault":
        original_read = Path.read_text
        def read_text(path, *args, **kwargs):
            if path == carrier:
                raise OSError("carrier unreadable")
            return original_read(path, *args, **kwargs)
        monkeypatch.setattr(Path, "read_text", read_text)
    else:
        changed = dict(state)
        changed["run_id" if fault == "run" else "issue_number"] = "later-run" if fault == "run" else 99
        carrier.write_text(json.dumps(changed))
        # The second carrier could itself be authorized; its changed identity
        # must still not attribute the earlier ledger's join.
        monkeypatch.setattr(ps, "classify_current_run_authority", lambda *_a: type("Verdict", (), {"typed_user_origin": True})())
    assert pcs.get_native_agent_run_id(owner, "joined") is None


@pytest.mark.parametrize("owner", ["", "foreign-owner"])
def test_final_permission_owner_refuses_identity_then_permits_retry(
    real_native_state, monkeypatch, capsys, owner,
):
    state = real_native_state
    result = _emit_guard(monkeypatch, capsys, state, "allow", "rejected", owner)
    assert result["permissionDecision"] == "deny"
    assert pcs._read_state(state["session_id"]).get("native_agent_joins", {}) == {}
    result = _emit_guard(monkeypatch, capsys, state, "allow", "legitimate")
    assert result["permissionDecision"] == "allow"
    assert pcs._read_state(state["session_id"])["native_agent_joins"]["legitimate"]["status"] == "reserved"


def test_denied_callback_and_observer_do_not_reserve_retry(real_native_state, monkeypatch, capsys):
    state = real_native_state
    assert _emit_guard(monkeypatch, capsys, state, "deny", "rejected")["permissionDecision"] == "deny"
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(guard._native_dispatch_input)))
    monkeypatch.setattr(logger, "_sic_cache_invocation", lambda *_a, **_k: pytest.fail("Agent observer must be inert"))
    with pytest.raises(SystemExit):
        logger.main()
    assert capsys.readouterr().out == ""
    assert pcs._read_state(state["session_id"]).get("native_agent_joins", {}) == {}
    assert ps.classify_current_run_authority(state, state["session_id"]).typed_user_origin
    result = _emit_guard(monkeypatch, capsys, state, "allow", "retry")
    assert result["permissionDecision"] == "allow", result


@pytest.mark.parametrize("fault", ["lost-ledger", "wrong-run", "partial-witness", "background", "foreign-env"])
def test_final_guard_native_refusals_preserve_empty_lane(real_native_state, monkeypatch, capsys, fault):
    state = real_native_state
    owner = state["session_id"]
    ledger = pcs._read_state(owner)
    before = ps.get_legacy_sentinel_path().read_bytes()
    if fault == "lost-ledger":
        pcs._state_file_path(owner).unlink()
    elif fault == "wrong-run":
        pcs._write_state(owner, {**ledger, "current_run_id": "foreign-run"})
    elif fault == "partial-witness":
        ps.get_legacy_sentinel_path().unlink()
        pcs._write_state(owner, {"native_origin": ledger["native_origin"]})
    elif fault == "foreign-env":
        monkeypatch.setenv("CLAUDE_SESSION_ID", "foreign-owner")
    payload = {
        "hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": owner,
        "tool_use_id": "rejected", "tool_input": {
            "subagent_type": "reviewer", "run_in_background": fault == "background",
        },
    }
    monkeypatch.setattr(guard, "_session_id", owner)
    monkeypatch.setattr(guard, "_native_dispatch_input", payload)
    guard.output_decision("allow", "workflow permitted")
    result = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert result["permissionDecision"] == "deny", result
    assert pcs._read_state(owner).get("native_agent_joins", {}) == {}
    pcs._write_state(owner, ledger)
    ps.get_legacy_sentinel_path().write_bytes(before)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    assert _emit_guard(monkeypatch, capsys, state, "allow", "retry")["permissionDecision"] == "allow"


def test_ordinary_no_run_agent_permits_without_native_credit(real_native_state, monkeypatch, capsys):
    state = real_native_state
    ps.get_legacy_sentinel_path().unlink()
    pcs._state_file_path(state["session_id"]).unlink()
    result = _emit_guard(monkeypatch, capsys, state, "allow", "ordinary")
    assert result["permissionDecision"] == "allow"
    assert pcs._read_state(state["session_id"]).get("native_agent_joins", {}) == {}


@pytest.mark.parametrize("fault", ["corrupt", "stale", "unreadable", "malformed-origin", "joins-only", "dangling-sentinel"])
def test_present_broken_carriers_never_downgrade_to_ordinary(real_native_state, monkeypatch, capsys, fault):
    state = real_native_state
    sentinel = ps.get_legacy_sentinel_path()
    ledger = pcs._state_file_path(state["session_id"])
    sentinel.unlink()
    if fault == "corrupt":
        ledger.write_text("{broken")
    elif fault == "stale":
        ledger.write_text('{"completions": {}}')
        os.utime(ledger, (time.time() - 8000, time.time() - 8000))
    elif fault == "unreadable":
        real_read = Path.read_text
        def denied_read(path, *args, **kwargs):
            if path == ledger:
                raise PermissionError("injected inaccessible ledger")
            return real_read(path, *args, **kwargs)
        monkeypatch.setattr(Path, "read_text", denied_read)
    elif fault == "malformed-origin":
        ledger.write_text('{"native_origin": "invalid"}')
    elif fault == "joins-only":
        ledger.write_text('{"native_agent_joins": {}}')
    else:
        ledger.unlink()
        sentinel.symlink_to(sentinel.with_name("missing-target"))
    result = _emit_guard(monkeypatch, capsys, state, "allow", "rejected")
    assert result["permissionDecision"] == "deny", result


def test_valid_blank_legacy_ledger_remains_ordinary(real_native_state, monkeypatch, capsys):
    state = real_native_state
    ps.get_legacy_sentinel_path().unlink()
    pcs._write_state(state["session_id"], {"completions": {}})
    assert _emit_guard(monkeypatch, capsys, state, "allow", "ordinary")["permissionDecision"] == "allow"


def test_final_refusal_activity_and_block_receipt_agree(real_native_state, monkeypatch, capsys, tmp_path):
    state = real_native_state
    monkeypatch.setattr(guard, "_resolved_logs_dir", lambda: tmp_path / "logs")
    monkeypatch.delenv("HOOK_TELEMETRY_DISABLED", raising=False)
    monkeypatch.delenv("HOOK_RECOVERY_DISABLED", raising=False)
    records = []
    telemetry_globals = guard._emit_decision.__globals__
    assert callable(telemetry_globals["log_block_event"])
    monkeypatch.setitem(telemetry_globals, "log_block_event", lambda **row: records.append({**row, "metadata": dict(row["metadata"])}))
    monkeypatch.setattr(pcs, "register_native_agent_dispatch", lambda *_a, **_k: "write_failed")
    payload = {"tool_name": "Agent", "session_id": state["session_id"], "tool_use_id": "fault",
               "tool_input": {"subagent_type": "reviewer", "run_in_background": False}}
    monkeypatch.setattr(guard, "_session_id", state["session_id"])
    monkeypatch.setattr(guard, "_native_dispatch_input", payload)
    guard._log_pretool_activity("Agent", payload["tool_input"], "allow", "preliminary")
    guard.output_decision("allow", "preliminary")
    envelope = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    rows = [json.loads(line) for path in (tmp_path / "logs" / "activity").glob("*.jsonl") for line in path.read_text().splitlines()]
    assert [row["decision"] for row in rows] == ["deny"]
    assert envelope["permissionDecision"] == "deny"
    assert len(records) == 1
    assert rows[0]["tool_use_id"] == records[0]["metadata"]["tool_use_id"] == "fault"
    assert rows[0]["run_id"] == records[0]["metadata"]["run_id"] == state["run_id"]
    assert records[0]["reason"] == envelope["permissionDecisionReason"]


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_dispatch_readback_fault_cleans_only_its_own_attempt(native_state, monkeypatch, cleanup_fails):
    original_read = pcs._read_state
    original_rmw = pcs._locked_rmw
    readback_failed = False
    writes = 0

    def read(*args, **kwargs):
        nonlocal readback_failed
        value = original_read(*args, **kwargs)
        if not readback_failed and "attempt" in value.get("native_agent_joins", {}):
            readback_failed = True
            raise OSError("injected post-write readback failure")
        return value

    def rmw(*args, **kwargs):
        nonlocal writes
        writes += 1
        if cleanup_fails and writes == 2:
            raise OSError("injected cleanup persistence failure")
        return original_rmw(*args, **kwargs)

    monkeypatch.setattr(pcs, "_read_state", read)
    monkeypatch.setattr(pcs, "_locked_rmw", rmw)
    expected = "cleanup_failed_fresh_native_run_required" if cleanup_fails else "write_failed"
    assert pcs.register_native_agent_dispatch("s", "attempt", "reviewer", False) == expected
    joins = original_read("s").get("native_agent_joins", {})
    assert ("attempt" in joins) is cleanup_fails
    if cleanup_fails:
        assert pcs.register_native_agent_dispatch("s", "retry", "reviewer", False) == "in_flight"
    else:
        assert pcs.register_native_agent_dispatch("s", "retry", "reviewer", False) == "registered"


def test_duplicate_registration_fault_does_not_delete_prior_reservation(native_state, monkeypatch):
    assert pcs.register_native_agent_dispatch("s", "existing", "reviewer", False) == "registered"
    before = pcs._read_state("s")
    original = pcs._locked_rmw

    def fail_after_duplicate(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("injected duplicate persistence fault")

    monkeypatch.setattr(pcs, "_locked_rmw", fail_after_duplicate)
    assert pcs.register_native_agent_dispatch("s", "existing", "reviewer", False) == "write_failed"
    assert pcs._read_state("s")["native_agent_joins"] == before["native_agent_joins"]


def _post_native_result(monkeypatch, capsys, state, tool_id, owner=None, status="completed"):
    monkeypatch.setenv("ACTIVITY_LOGGING", "false")
    monkeypatch.setattr(logger, "_check_and_log_heartbeat", lambda *_a: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "PostToolUse", "tool_name": "Agent",
        "session_id": state["session_id"] if owner is None else owner,
        "tool_use_id": tool_id, "tool_input": {"subagent_type": "reviewer"},
        "tool_response": {"agentId": f"agent-{tool_id}", "status": status},
    })))
    with pytest.raises(SystemExit):
        logger.main()
    capsys.readouterr()


def test_native_admission_write_fault_preserves_old_sentinel_then_retry(real_native_state, monkeypatch, capsys):
    state = real_native_state
    ads.write("older", generation="older-generation")
    prior = ads._path().read_bytes()
    original_replace = ads.os.replace

    def reject_dispatch_replace(source, target):
        if Path(target) == ads._path():
            raise OSError("injected dispatch publication failure")
        return original_replace(source, target)

    monkeypatch.setattr(ads.os, "replace", reject_dispatch_replace)
    monkeypatch.setattr(logger, "_sic_cache_invocation", lambda *_a, **_k: pytest.fail("Native Agent must not append FIFO"))
    result = _emit_guard(monkeypatch, capsys, state, "allow", "failed-publication")
    assert result["permissionDecision"] == "deny"
    assert ads._path().read_bytes() == prior
    assert pcs._read_state(state["session_id"]).get("native_agent_joins", {}) == {}
    assert list(ads._path().parent.glob(f".{ads._path().name}.*.tmp")) == []
    monkeypatch.setattr(ads.os, "replace", original_replace)
    assert _emit_guard(monkeypatch, capsys, state, "allow", "retry")["permissionDecision"] == "allow"
    assert json.loads(ads._path().read_text())["generation"] == "retry"


def test_exact_terminal_result_clears_only_its_dispatch(real_native_state, monkeypatch, capsys):
    state = real_native_state
    assert _emit_guard(monkeypatch, capsys, state, "allow", "accepted")["permissionDecision"] == "allow"
    prior = ads._path().read_bytes()
    _post_native_result(monkeypatch, capsys, state, "accepted", owner="foreign-owner")
    assert ads._path().read_bytes() == prior
    _post_native_result(monkeypatch, capsys, state, "accepted")
    assert not ads._path().exists()
    ads.write("another", generation="another-dispatch")
    prior = ads._path().read_bytes()
    _post_native_result(monkeypatch, capsys, state, "accepted")
    assert ads._path().read_bytes() == prior


def test_missing_result_tool_identity_cannot_clear_legacy_sentinel(real_native_state, monkeypatch, capsys):
    state = real_native_state
    ads.write("legacy", generation=None)
    prior = ads._path().read_bytes()
    _post_native_result(monkeypatch, capsys, state, "")
    assert ads._path().read_bytes() == prior


def test_terminal_clear_failure_cannot_keep_protected_edit_authority(real_native_state, monkeypatch, capsys):
    state = real_native_state
    assert _emit_guard(monkeypatch, capsys, state, "allow", "accepted")["permissionDecision"] == "allow"
    monkeypatch.setattr(guard, "_native_dispatch_input", {})
    monkeypatch.setattr(guard, "_is_protected_infrastructure", lambda _p: True)
    monkeypatch.setattr(guard, "_is_pipeline_active", lambda: True)
    protected = {"file_path": "plugins/autonomous-dev/lib/example.py"}
    guard._enforce_protected_infrastructure("Edit", protected)
    monkeypatch.setattr(ads, "clear", lambda **_k: (_ for _ in ()).throw(OSError("injected cleanup fault")))
    _post_native_result(monkeypatch, capsys, state, "accepted")
    assert ads.is_active()
    with pytest.raises(SystemExit):
        guard._enforce_protected_infrastructure("Edit", protected)
    result = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert result["permissionDecision"] == "deny"
    assert "currently reserved" in result["permissionDecisionReason"]


@pytest.mark.parametrize("native_profile", [False, True])
def test_task_fifo_lifecycle_is_legacy_only_native_profile_unqualified(monkeypatch, tmp_path, native_profile):
    """Native Task remains HOLD; unknown native Stops cannot spend legacy FIFO."""
    owner = f"legacy-task-{tmp_path.name}"
    monkeypatch.setattr(invocation_cache, "cache_path", lambda _s: tmp_path / "queue.json")
    monkeypatch.setattr(ads, "_path", lambda *_a: tmp_path / "dispatch.json")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setenv("TRACK_SESSIONS", "false")
    monkeypatch.setenv("AUTO_UPDATE_PROGRESS", "false")
    monkeypatch.setattr(pcs, "native_agent_join_active", lambda _s: False)
    monkeypatch.setattr(pcs, "get_run_start_receipt", lambda _s: None)
    monkeypatch.setattr(pcs, "record_agent_completion", lambda **_k: None)
    logger.prepare_agent_dispatch({"tool_name": "Task", "session_id": owner,
                                   "tool_input": {"subagent_type": "reviewer"}})
    queue = invocation_cache.peek_queue(owner)
    prior = ads._path().read_bytes()
    transcript = tmp_path / "agent.jsonl"
    transcript.write_text('{"type":"assistant"}\n')
    monkeypatch.setattr(sys, "argv", ["unified_session_tracker.py"] + (["--native"] if native_profile else []))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "SubagentStop", "session_id": owner, "agent_type": "reviewer",
        "agent_id": owner, "agent_transcript_path": str(transcript),
        "last_assistant_message": "Completed review",
    })))
    assert tracker.main() == 0
    if native_profile:
        assert invocation_cache.peek_queue(owner) == queue
        assert ads._path().read_bytes() == prior
    else:
        assert invocation_cache.peek_queue(owner) == []
        assert not ads._path().exists()


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


def test_agent_observer_has_no_independent_ledger_permission_owner(monkeypatch, capsys):
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
    assert capsys.readouterr().out == ""  # Observer has no permission ownership.


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


def test_agent_observer_is_inert_for_background_and_foreign_env(monkeypatch, capsys):
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
    assert capsys.readouterr().out == ""
    assert calls == []
    monkeypatch.setenv("CLAUDE_SESSION_ID", "S")
    monkeypatch.setattr(pcs, "register_native_agent_dispatch", lambda *_a: "not_foreground")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "S",
        "tool_use_id": "u1", "tool_input": {"subagent_type": "reviewer", "run_in_background": True},
    })))
    with pytest.raises(SystemExit):
        logger.main()
    assert capsys.readouterr().out == ""
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

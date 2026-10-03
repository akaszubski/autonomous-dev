"""
Tests for pytest-gate virtual agent in pipeline_completion_state.py.

Issue #838: Pipeline step ordering enforcement — pytest gate.
"""

import json
import os
import sys
import uuid
from pathlib import Path

import pytest

# Add lib to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_completion_state import (
    clear_session,
    get_completed_agents,
    get_pytest_gate_passed,
    record_agent_completion,
    record_pytest_gate_passed,
)


@pytest.fixture()
def session_id():
    """Generate a unique session ID and clean up after test."""
    sid = f"test-pytest-gate-{uuid.uuid4().hex[:8]}"
    yield sid
    clear_session(sid)


@pytest.fixture
def obligation_state(monkeypatch, tmp_path):
    """Real isolated initializer, signer, checkpoint and ledger for #1818."""
    import pipeline_completion_state as pcs
    import pipeline_state as ps
    from tests.helpers.state_isolation import redirect_pipeline_state
    import subprocess
    from test_runner import observe_checkout

    redirect_pipeline_state(monkeypatch, tmp_path, ps, pcs)
    repo = tmp_path / "consumer"
    repo.mkdir()
    (repo / "test_a.py").write_text("def test_a():\n    assert True\n")
    (repo / "test_control.py").write_text(
        "import pytest\ndef test_skip():\n    pytest.skip('control')\n"
    )
    subprocess.run(["/usr/bin/git", "init", "-q", str(repo)], check=True)
    subprocess.run(["/usr/bin/git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "/usr/bin/git",
            "-C",
            str(repo),
            "-c",
            "user.name=Offline",
            "-c",
            "user.email=offline@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    monkeypatch.chdir(repo)
    monkeypatch.setattr(ps, "get_state_path", lambda run: tmp_path / f"checkpoint-{run}.json")
    monkeypatch.setattr(ps, "get_lockfile_path", lambda run: tmp_path / f"lock-{run}")
    scope = pcs.initialize_native_run_from_event(
        {
            "hook_event_name": "UserPromptExpansion",
            "command_name": "implement",
            "command_args": "--fix #1818",
            "command_source": "user",
            "prompt": "/implement --fix #1818",
            "session_id": "offline-obligation-owner",
        }
    )
    assert scope is not None
    monkeypatch.setenv("PIPELINE_STATE_FILE", str(ps.get_legacy_sentinel_path()))
    manifest = {
        "required_ids": ["test_a.py::test_a"],
        "independent_cases": ["opposite"],
        "subjects": ["test_a.py", "test_control.py"],
        "controlled_ids": ["test_control.py::test_skip"],
    }
    import hashlib

    # Explicit synthetic profile pins; tests do not execute these dummy artifacts.
    sandbox = {
        "node": "/pinned/node",
        "node_sha256": "a" * 64,
        "python": "/pinned/python",
        "python_sha256": "b" * 64,
        "runtime": "/pinned/runtime.js",
        "runtime_sha256": "c" * 64,
        "profile": "/pinned/profile.json",
        "profile_sha256": "d" * 64,
        "runtime_closure_sha256": "e" * 64,
    }
    profile = {
        "environment": {"TMPDIR": str(tmp_path), "HOME": str(tmp_path)},
        "sandbox": sandbox,
        "runtime_environment": {"CLAUDE_CODE_TMPDIR": str(tmp_path)},
        "max_output_bytes": 1024 * 1024,
    }
    control_profile = json.loads(json.dumps(profile))
    control_profile["environment"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    manifest["ordinary_capture"] = {
        "argv": [sandbox["python"], "-I", "-m", "pytest", "-vv", *manifest["required_ids"]],
        "effective_profile": profile,
    }
    manifest["controlled_capture"] = {
        "argv": [
            sandbox["python"],
            "-I",
            "-m",
            "pytest",
            "--noconftest",
            "-c",
            os.devnull,
            "--rootdir",
            str(repo),
            "--confcutdir",
            str(repo),
            "-p",
            "no:cacheprovider",
            "-vv",
            *manifest["controlled_ids"],
        ],
        "effective_profile": control_profile,
    }

    provisioning = {
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "pre_edit_checkout": observe_checkout(repo, tuple(manifest["subjects"])),
    }
    return pcs, ps, scope, provisioning


def test_issue_1818_bind_and_pending_never_authorize(obligation_state):
    pcs, _, scope, provision = obligation_state
    assert pcs.bind_pytest_obligation(
        scope["session_id"],
        scope=scope,
        provisioning=provision,
        checkout=provision["pre_edit_checkout"],
    )
    assert pcs.claim_pytest_observation(
        scope["session_id"],
        scope=scope,
        provisioning=provision,
        phase="base",
        tool_use_id="tool-base",
    )
    assert (
        pcs.get_pytest_dispatch_receipt(scope["session_id"], scope=scope, provisioning=provision)
        is None
    )
    assert not pcs.claim_pytest_observation(
        scope["session_id"],
        scope=scope,
        provisioning=provision,
        phase="base",
        tool_use_id="tool-base",
    )


def test_issue_1818_binding_detects_canonical_command_drift(obligation_state, monkeypatch):
    import test_runner

    pcs, _, scope, provision = obligation_state
    original = test_runner.build_pytest_argv
    monkeypatch.setattr(test_runner, "build_pytest_argv", lambda *a, **kw: tuple(
        value for value in original(*a, **kw) if value != "-I"))
    assert not pcs.bind_pytest_obligation(
        scope["session_id"], scope=scope, provisioning=provision,
        checkout=provision["pre_edit_checkout"])


@pytest.mark.parametrize(
    "fault", ["late", "progression", "edited-pending", "base", "empty", "digest", "owner"]
)
def test_issue_1818_binding_refusals(obligation_state, fault):
    pcs, ps, scope, provision = obligation_state
    checkout = dict(provision["pre_edit_checkout"])
    if fault == "late":
        checkpoint = ps.load_pipeline(scope["run_id"])
        checkpoint.steps["implement"]["status"] = "completed"
        ps.save_pipeline(checkpoint)
    elif fault == "edited-pending":
        (Path(checkout["repo"]) / "test_a.py").write_text("assert False\n")
    elif fault == "progression":
        assert (
            pcs.register_native_agent_dispatch(
                scope["session_id"], "early-implementer", "implementer", False
            )
            == "registered"
        )
    elif fault == "base":
        checkout["head"] = "0" * 40
    elif fault == "empty":
        provision["manifest"]["required_ids"] = []
    elif fault == "digest":
        provision["manifest_sha256"] = "0" * 64
    else:
        scope["session_id"] = "foreign"
    assert not pcs.bind_pytest_obligation(
        "offline-obligation-owner", scope=scope, provisioning=provision, checkout=checkout
    )


def _offline_capture(provision, failed=False):
    """Synthetic process measurement for ledger tests, NOT native capture proof."""
    return {
        "argv": provision["manifest"]["ordinary_capture"]["argv"],
        "environment_sha256": __import__("hashlib")
        .sha256(
            json.dumps(
                provision["manifest"]["ordinary_capture"]["effective_profile"], sort_keys=True
            ).encode()
        )
        .hexdigest(),
        "raw_exit": int(failed),
        "stdout": "test_a.py::test_a FAILED\n" if failed else "test_a.py::test_a PASSED\n",
        "stderr": "",
        "outcomes": {"test_a.py::test_a": "FAILED" if failed else "PASSED"},
        "checkout": provision["pre_edit_checkout"],
        "output_metadata": None,
    }


def _offline_control(provision):
    """Synthetic controlled measurement, never a native/control execution claim."""
    measured = _offline_capture(provision)
    measured.update(
        argv=provision["manifest"]["controlled_capture"]["argv"],
        environment_sha256=__import__("hashlib")
        .sha256(
            json.dumps(
                provision["manifest"]["controlled_capture"]["effective_profile"], sort_keys=True
            ).encode()
        )
        .hexdigest(),
        stdout="test_control.py::test_skip SKIPPED\n",
        outcomes={"test_control.py::test_skip": "SKIPPED"},
    )
    return measured


@pytest.mark.parametrize("phase", ["binding", "base"])
@pytest.mark.parametrize("neighbor", ["native", "foreign-prefix", "foreign-run", "foreign-issue"])
def test_issue_1818_namespaced_late_join_and_neighbors(obligation_state, phase, neighbor):
    """Actual native raw namespace is normalized only after exact ownership filtering."""
    pcs, _, scope, provision = obligation_state
    owner = scope["session_id"]
    args = {"scope": scope, "provisioning": provision}
    if phase == "base":
        assert pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
    role = (
        "other-plugin:implementer" if neighbor == "foreign-prefix" else "autonomous-dev:implementer"
    )
    assert (
        pcs.register_native_agent_dispatch(owner, "native-implementer-late", role, False)
        == "registered"
    )
    if neighbor in {"foreign-run", "foreign-issue"}:
        state = pcs._read_state(owner)
        entry = state["native_agent_joins"]["native-implementer-late"]
        entry["run_id" if neighbor == "foreign-run" else "issue_number"] = (
            "foreign-run" if neighbor == "foreign-run" else 1819
        )
        pcs._write_state(owner, state)
    result = (
        pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
        if phase == "binding"
        else pcs.claim_pytest_observation(owner, **args, phase="base", tool_use_id="tool-base")
    )
    assert result is (neighbor != "native")


@pytest.mark.parametrize(
    "fault",
    [
        "ordinary-argv",
        "ordinary-profile",
        "controlled-argv",
        "controlled-profile",
        "controlled-exit",
        "controlled-report",
    ],
)
def test_issue_1818_exact_capture_profiles_and_control_refusals(obligation_state, fault):
    pcs, _, scope, provision = obligation_state
    owner = scope["session_id"]
    args = {"scope": scope, "provisioning": provision}
    assert pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
    assert pcs.claim_pytest_observation(owner, **args, phase="base", tool_use_id="tool-base")
    capture = _offline_capture(provision)
    if fault == "ordinary-argv":
        capture["argv"] = [*capture["argv"], "--noconftest"]
    elif fault == "ordinary-profile":
        capture["environment_sha256"] = "0" * 64
    result = pcs.complete_pytest_observation(
        owner, **args, tool_use_id="tool-base", capture=capture
    )
    if fault.startswith("ordinary"):
        assert not result
        return
    assert result
    base_ack = pcs.acknowledge_pytest_observation(
        owner, **args, tool_use_id="tool-base", callback_exit=0, children_clean=True
    )
    assert base_ack is not None
    _stage_phase(pcs, scope, provision, "candidate", base_acknowledgment=base_ack)
    control = _offline_control(provision)
    if fault == "controlled-argv":
        control["argv"] = [*control["argv"], "-p", "forged-plugin"]
    elif fault == "controlled-profile":
        control["environment_sha256"] = "0" * 64
    elif fault == "controlled-exit":
        control["raw_exit"] = 4
    else:
        control.update(
            stdout="test_control.py::test_skip PASSED\n",
            outcomes={"test_control.py::test_skip": "PASSED"},
        )
    assert (
        pcs.acknowledge_pytest_observation(
            owner,
            **args,
            tool_use_id="tool-candidate",
            callback_exit=0,
            children_clean=True,
            independent_cases={"opposite": "PASSED"},
            controlled_capture=control,
        )
        is None
    )
    assert pcs.get_pytest_dispatch_receipt(owner, **args) is None


def _stage_phase(pcs, scope, provision, phase, failed=False, base_acknowledgment=None):
    args = {"scope": scope, "provisioning": provision}
    assert pcs.claim_pytest_observation(
        scope["session_id"],
        **args,
        phase=phase,
        tool_use_id=f"tool-{phase}",
        base_acknowledgment=base_acknowledgment,
    )
    assert pcs.complete_pytest_observation(
        scope["session_id"],
        **args,
        tool_use_id=f"tool-{phase}",
        capture=_offline_capture(provision, failed),
    )


@pytest.mark.parametrize("inherited_red", [False, True])
def test_issue_1818_completed_pending_supervisor_final_and_review_only(
    obligation_state, inherited_red
):
    pcs, _, scope, provision = obligation_state
    args = {"scope": scope, "provisioning": provision}
    owner = scope["session_id"]
    assert pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
    _stage_phase(pcs, scope, provision, "base", inherited_red)
    assert pcs.get_pytest_dispatch_receipt(owner, **args) is None
    base_ack = pcs.acknowledge_pytest_observation(
        owner, **args, tool_use_id="tool-base", callback_exit=0, children_clean=True
    )
    assert base_ack is not None
    _stage_phase(pcs, scope, provision, "candidate", inherited_red, base_ack)
    assert pcs.get_pytest_dispatch_receipt(owner, **args) is None
    acknowledgment = pcs.acknowledge_pytest_observation(
        owner,
        **args,
        tool_use_id="tool-candidate",
        callback_exit=0,
        children_clean=True,
        independent_cases={"opposite": "PASSED"},
        independent_observations={"test_control.py::test_skip": "SKIPPED"},
        controlled_capture=_offline_control(provision),
    )
    assert acknowledgment is not None
    assert pcs.get_pytest_dispatch_receipt(owner, **args) is None
    receipt = pcs.get_pytest_dispatch_receipt(owner, **args, acknowledgment=acknowledgment)
    assert receipt["claim"] == "reviewer-dispatch-only"
    assert not pcs.acknowledge_pytest_observation(
        owner, **args, tool_use_id="tool-candidate", callback_exit=0, children_clean=True
    )
    assert (
        pcs.register_native_agent_dispatch(owner, "offline-implementer", "implementer", False)
        == "registered"
    )
    assert (
        pcs.join_native_agent_result(
            owner, "offline-implementer", "offline-child", "completed", False
        )
        == "completed"
    )
    from agent_ordering_gate import check_ordering_with_session_fallback

    result = check_ordering_with_session_fallback(
        "reviewer",
        owner,
        issue_number=1818,
        pipeline_mode="fix",
        pytest_scope=scope,
        pytest_provisioning=provision,
        pytest_acknowledgment=acknowledgment,
    )
    assert result.passed, result.reason
    assert "pytest-gate" not in pcs.get_completed_agents(owner, issue_number=1818)
    other = check_ordering_with_session_fallback(
        "doc-master",
        owner,
        issue_number=1818,
        pipeline_mode="fix",
        pytest_scope=scope,
        pytest_provisioning=provision,
    )
    assert not other.passed


@pytest.mark.parametrize(
    "fault", ["cancel", "children", "replay", "wrong-run", "tamper", "readback", "write", "lock"]
)
def test_issue_1818_pending_and_faults_never_authorize(obligation_state, monkeypatch, fault):
    pcs, _, scope, provision = obligation_state
    args = {"scope": scope, "provisioning": provision}
    owner = scope["session_id"]
    assert pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
    _stage_phase(pcs, scope, provision, "base")
    if fault == "wrong-run":
        pcs.record_run_start(owner, "superseding-run", issue_number=1818)
    elif fault == "tamper":
        state = pcs._read_state(owner)
        state["pytest_obligation"]["data"]["status"] = "final"
        state["pytest_obligation"]["data"]["receipt"] = {"claim": "reviewer-dispatch-only"}
        pcs._write_state(owner, state)
    elif fault in {"write", "lock"}:

        def fail(*_args, **_kwargs):
            raise OSError("controlled persistence failure")

        monkeypatch.setattr(pcs, "_write_state" if fault == "write" else "_locked_rmw", fail)
    elif fault == "readback":
        original = pcs._read_state

        def wrong_readback(*a, **kw):
            value = original(*a, **kw)
            if not pcs._in_locked_rmw():
                value.pop("pytest_obligation", None)
            return value

        monkeypatch.setattr(pcs, "_read_state", wrong_readback)
    assert not pcs.acknowledge_pytest_observation(
        owner,
        **args,
        tool_use_id="wrong-tool" if fault == "replay" else "tool-base",
        callback_exit=1 if fault == "cancel" else 0,
        children_clean=fault != "children",
    )
    monkeypatch.setenv("SKIP_PYTEST_GATE", "1")
    assert pcs.get_pytest_dispatch_receipt(owner, **args) is None


@pytest.mark.parametrize("phase", ["base", "candidate"])
def test_issue_1818_final_write_failed_readback_healthy_reader_no_ack(
    obligation_state, monkeypatch, phase
):
    """N8: durable final alone must not escape unsuccessful supervisor readback."""
    pcs, _, scope, provision = obligation_state
    owner = scope["session_id"]
    args = {"scope": scope, "provisioning": provision}
    assert pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
    _stage_phase(pcs, scope, provision, "base")
    if phase == "candidate":
        base_ack = pcs.acknowledge_pytest_observation(
            owner, **args, tool_use_id="tool-base", callback_exit=0, children_clean=True
        )
        assert base_ack is not None
        _stage_phase(pcs, scope, provision, "candidate", base_acknowledgment=base_ack)
    original = pcs._read_state

    def fail_after_write(*a, **kw):
        value = original(*a, **kw)
        if not pcs._in_locked_rmw():
            raise OSError("controlled final readback failure")
        return value

    monkeypatch.setattr(pcs, "_read_state", fail_after_write)
    acknowledgment = pcs.acknowledge_pytest_observation(
        owner,
        **args,
        tool_use_id=f"tool-{phase}",
        callback_exit=0,
        children_clean=True,
        independent_cases={"opposite": "PASSED"},
        independent_observations={"test_control.py::test_skip": "SKIPPED"},
        controlled_capture=_offline_control(provision),
    )
    assert acknowledgment is None
    monkeypatch.setattr(pcs, "_read_state", original)
    # Trusted supervisor publishes ONLY a successfully returned object. A later
    # healthy read of final cannot substitute for that return (original N8).
    if acknowledgment is not None:
        assert pcs.publish_returned_pytest_snapshot(owner, **args, acknowledgment=acknowledgment)
    assert pcs.get_returned_pytest_snapshot(owner, **args) is None
    assert original(owner)["pytest_obligation"]["data"]["status"] == (
        "final" if phase == "candidate" else "base-final"
    )
    assert pcs.get_pytest_dispatch_receipt(owner, **args, acknowledgment=acknowledgment) is None
    if phase == "base":
        assert not pcs.claim_pytest_observation(
            owner, **args, phase="candidate", tool_use_id="tool-candidate"
        )


def test_issue_1818_returned_transport_roundtrip_and_transition(obligation_state):
    """Transport carries the identical existing seal; candidate invalidates base copy."""
    pcs, _, scope, provision = obligation_state
    owner = scope["session_id"]
    args = {"scope": scope, "provisioning": provision}
    assert pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
    _stage_phase(pcs, scope, provision, "base")
    returned = pcs.acknowledge_pytest_observation(
        owner, **args, tool_use_id="tool-base", callback_exit=0, children_clean=True)
    assert returned is not None
    assert pcs.get_returned_pytest_snapshot(owner, **args) is None
    assert pcs.publish_returned_pytest_snapshot(owner, **args, acknowledgment=returned)
    loaded = pcs.get_returned_pytest_snapshot(owner, **args)
    assert loaded == returned and loaded is not returned
    loaded["seal"]["hmac"] = "modified-reader"
    assert pcs.get_returned_pytest_snapshot(owner, **args) == returned
    _stage_phase(pcs, scope, provision, "candidate", base_acknowledgment=returned)
    assert pcs.get_returned_pytest_snapshot(owner, **args) is None
    assert "pytest_returned_snapshot" not in pcs._read_state(owner)
    assert not pcs.publish_returned_pytest_snapshot(owner, **args, acknowledgment=returned)
    final = pcs.acknowledge_pytest_observation(
        owner, **args, tool_use_id="tool-candidate", callback_exit=0, children_clean=True,
        independent_cases={"opposite": "PASSED"}, controlled_capture=_offline_control(provision))
    assert pcs.publish_returned_pytest_snapshot(owner, **args, acknowledgment=final)
    transported = pcs.get_returned_pytest_snapshot(owner, **args)
    assert pcs.get_pytest_dispatch_receipt(owner, **args, acknowledgment=transported) is not None
    assert pcs.get_pytest_dispatch_receipt(owner, **args) is None


@pytest.mark.parametrize("fault", ["none", "snapshot", "scope", "lock", "stored"])
def test_issue_1818_returned_transport_refuses_conflicts(obligation_state, monkeypatch, fault):
    pcs, _, scope, provision = obligation_state
    owner = scope["session_id"]
    args = {"scope": scope, "provisioning": provision}
    assert pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
    _stage_phase(pcs, scope, provision, "base")
    returned = pcs.acknowledge_pytest_observation(
        owner, **args, tool_use_id="tool-base", callback_exit=0, children_clean=True)
    assert returned is not None
    if fault == "stored":
        assert pcs.publish_returned_pytest_snapshot(owner, **args, acknowledgment=returned)
        pcs._locked_rmw(owner, lambda state: state["pytest_returned_snapshot"]["seal"].update(hmac="bad"))
        assert pcs.get_returned_pytest_snapshot(owner, **args) is None
        return
    if fault == "none":
        returned = None
    elif fault == "snapshot":
        returned["seal"]["hmac"] = "bad"
    elif fault == "scope":
        args["scope"] = {**scope, "run_id": "foreign"}
    else:
        def refuse_lock(*a, **kw):
            assert kw.get("require_lock") is True
            raise OSError("lock unavailable")
        monkeypatch.setattr(pcs, "_locked_rmw", refuse_lock)
    assert not pcs.publish_returned_pytest_snapshot(owner, **args, acknowledgment=returned)
    assert pcs.get_returned_pytest_snapshot(owner, **args) is None


def test_issue_1818_transport_readback_fault_does_not_undo_original_return(
    obligation_state, monkeypatch
):
    """A later transport fault is not original N8; actual return already occurred."""
    pcs, _, scope, provision = obligation_state
    owner = scope["session_id"]
    args = {"scope": scope, "provisioning": provision}
    assert pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
    _stage_phase(pcs, scope, provision, "base")
    returned = pcs.acknowledge_pytest_observation(
        owner, **args, tool_use_id="tool-base", callback_exit=0, children_clean=True)
    assert returned is not None
    original = pcs._read_state

    def fail_transport_readback(*a, **kw):
        value = original(*a, **kw)
        if not pcs._in_locked_rmw():
            raise OSError("transport readback unavailable")
        return value

    monkeypatch.setattr(pcs, "_read_state", fail_transport_readback)
    assert not pcs.publish_returned_pytest_snapshot(owner, **args, acknowledgment=returned)
    monkeypatch.setattr(pcs, "_read_state", original)
    assert pcs.get_returned_pytest_snapshot(owner, **args) == returned


def test_issue_1818_two_bounded_reader_mutations_detected(obligation_state):
    """Final-status omission and current-binding omission each break fixed refusals."""
    import inspect

    pcs, _, scope, provision = obligation_state
    owner = scope["session_id"]
    args = {"scope": scope, "provisioning": provision}
    assert pcs.bind_pytest_obligation(owner, **args, checkout=provision["pre_edit_checkout"])
    state = pcs._read_state(owner)
    binding = pcs._pytest_binding(owner, scope, provision, state)
    slot = pcs._pytest_record(
        binding, {"status": "capture-pending", "receipt": {"noncertifying": True}}
    )
    state["pytest_obligation"] = slot
    pcs._write_state(owner, state)
    assert pcs.get_pytest_dispatch_receipt(owner, **args, acknowledgment=slot) is None
    source = inspect.getsource(pcs.get_pytest_dispatch_receipt)
    namespace = dict(pcs.__dict__)
    mutated = source.replace(' if data.get("status") == "final" else None', "")
    assert mutated != source
    exec(compile(mutated, "bounded-final-state-mutant", "exec"), namespace)
    assert namespace["get_pytest_dispatch_receipt"](owner, **args, acknowledgment=slot) is not None
    slot = pcs._pytest_record(binding, {"status": "final", "receipt": {"noncertifying": True}})
    state["pytest_obligation"] = slot
    pcs._write_state(owner, state)
    pcs.record_run_start(owner, "superseding-run", issue_number=1818)
    assert pcs.get_pytest_dispatch_receipt(owner, **args, acknowledgment=slot) is None
    namespace = dict(pcs.__dict__, _frozen_binding=binding)
    mutated = source.replace(
        "_pytest_binding(session_id, scope, provisioning, state)", "_frozen_binding"
    )
    assert mutated != source
    exec(compile(mutated, "bounded-current-binding-mutant", "exec"), namespace)
    assert namespace["get_pytest_dispatch_receipt"](owner, **args, acknowledgment=slot) is not None


class TestRecordPytestGate:
    """Tests for record_pytest_gate_passed and get_pytest_gate_passed."""

    def test_record_pytest_gate_creates_completion(self, session_id: str):
        """Recording pytest gate creates a 'pytest-gate' completion entry."""
        record_pytest_gate_passed(session_id)
        completed = get_completed_agents(session_id)
        assert "pytest-gate" in completed

    def test_get_pytest_gate_false_when_not_recorded(self, session_id: str):
        """Default returns False when nothing has been recorded."""
        assert get_pytest_gate_passed(session_id) is False

    def test_get_pytest_gate_true_after_recording(self, session_id: str):
        """Returns True after recording pytest gate as passed."""
        record_pytest_gate_passed(session_id)
        assert get_pytest_gate_passed(session_id) is True

    def test_pytest_gate_with_issue_number(self, session_id: str):
        """Works with non-zero issue numbers."""
        record_pytest_gate_passed(session_id, issue_number=42)
        assert get_pytest_gate_passed(session_id, issue_number=42) is True
        # Different issue number should not have the gate
        assert get_pytest_gate_passed(session_id, issue_number=99) is False

    def test_pytest_gate_skip_env_var(self, session_id: str, monkeypatch: pytest.MonkeyPatch):
        """SKIP_PYTEST_GATE=1 causes get_pytest_gate_passed to return True."""
        monkeypatch.setenv("SKIP_PYTEST_GATE", "1")
        # Not recorded, but env var makes it return True
        assert get_pytest_gate_passed(session_id) is True

    def test_pytest_gate_skip_env_var_true(self, session_id: str, monkeypatch: pytest.MonkeyPatch):
        """SKIP_PYTEST_GATE=true also works."""
        monkeypatch.setenv("SKIP_PYTEST_GATE", "true")
        assert get_pytest_gate_passed(session_id) is True

    def test_pytest_gate_skip_env_var_yes(self, session_id: str, monkeypatch: pytest.MonkeyPatch):
        """SKIP_PYTEST_GATE=yes also works."""
        monkeypatch.setenv("SKIP_PYTEST_GATE", "YES")
        assert get_pytest_gate_passed(session_id) is True

    def test_pytest_gate_unknown_session_fallback(self):
        """Merge from 'unknown' session works for pytest-gate."""
        unknown_sid = "unknown"
        test_sid = f"test-fallback-{uuid.uuid4().hex[:8]}"
        try:
            record_pytest_gate_passed(unknown_sid, issue_number=0)
            # Reading from a different session should merge from 'unknown'
            assert get_pytest_gate_passed(test_sid, issue_number=0) is True
        finally:
            clear_session(unknown_sid)
            clear_session(test_sid)

    def test_pytest_gate_failed_records_false(self, session_id: str):
        """Recording passed=False keeps gate closed."""
        record_pytest_gate_passed(session_id, passed=False)
        assert get_pytest_gate_passed(session_id) is False

    def test_pytest_gate_coexists_with_agents(self, session_id: str):
        """Other agent completions are unaffected by pytest-gate."""
        record_agent_completion(session_id, "implementer", success=True)
        record_pytest_gate_passed(session_id)
        completed = get_completed_agents(session_id)
        assert "implementer" in completed
        assert "pytest-gate" in completed

    def test_pytest_gate_per_issue_isolation(self, session_id: str):
        """Issue 1 passing doesn't affect issue 2."""
        record_pytest_gate_passed(session_id, issue_number=1)
        assert get_pytest_gate_passed(session_id, issue_number=1) is True
        assert get_pytest_gate_passed(session_id, issue_number=2) is False

    def test_record_pytest_gate_idempotent(self, session_id: str):
        """Calling record_pytest_gate_passed multiple times is idempotent (Issue #1238)."""
        # First call - records the gate
        record_pytest_gate_passed(session_id)
        completed_first = get_completed_agents(session_id)
        assert "pytest-gate" in completed_first
        
        # Second call with same session_id - should be idempotent (no error, same state)
        record_pytest_gate_passed(session_id)
        completed_second = get_completed_agents(session_id)
        assert "pytest-gate" in completed_second
        
        # The completion state should be the same after both calls
        assert completed_first == completed_second
        
        # Verify pytest-gate appears exactly once, not duplicated
        pytest_gate_entries = [agent for agent in completed_second if agent == "pytest-gate"]
        assert len(pytest_gate_entries) == 1, "pytest-gate should appear exactly once, not duplicated"

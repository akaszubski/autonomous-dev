"""Command-side #1807 completion authority contract."""

from pathlib import Path
import contextlib
import io
import json
import os
import pytest

import pipeline_completion_state as pcs
import pipeline_state as ps
from tests.helpers.state_isolation import redirect_pipeline_state


COMMANDS = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/commands"
MODES = ("implement.md", "implement-batch.md", "implement-fix.md", "implement-resume.md")


def test_all_modes_require_foreground_native_receipt():
    for name in MODES:
        source = (COMMANDS / name).read_text()
        assert "run_in_background: false" in source, name
        assert "current-run completion receipt" in source, name


def test_commands_never_direct_write_completion_credit():
    for name in MODES:
        source = (COMMANDS / name).read_text()
        assert "record_agent_completion(" not in source, name


def test_verdict_recording_remains_separate():
    for name in ("implement.md", "implement-batch.md"):
        source = (COMMANDS / name).read_text()
        assert "record_doc_verdict(" in source, name


def test_post_batch_cia_finishes_before_commit():
    source = (COMMANDS / "implement-batch.md").read_text()
    section = source.split("STEP B3.5: Post-Batch Full CI Analysis", 1)[1]
    assert "Run CIA in foreground and verify its current-run receipt" in section
    assert "Launch CIA in background" not in section


@pytest.mark.parametrize("args,expected", [
    ("fix 2 tests #1807", 1807),
    ("issue 1807 has 2 failures", 1807),
    ("fix 2 tests", None),
    ("1807", 1807),
    ("no issue mentioned", None),
])
def test_canonical_issue_parser_examples(args, expected):
    assert pcs.extract_native_issue_number(args) == expected


def test_single_issue_modes_call_canonical_parser():
    for name in ("implement.md", "implement-fix.md"):
        source = (COMMANDS / name).read_text()
        assert "extract_native_issue_number" in source, name


def test_typed_step_zero_adopts_native_carriers_without_reinitializing():
    for name, start, end in (
        ("implement.md", "# NATIVE STEP 0 ADOPTION START", "# NATIVE STEP 0 ADOPTION END"),
        ("implement-fix.md", "# NATIVE F1 ADOPTION START", "# NATIVE F1 ADOPTION END"),
    ):
        source = (COMMANDS / name).read_text()
        assert start in source and end in source, name
        block = source.split(start, 1)[1].split(end, 1)[0]
        assert "get_run_start_receipt" in block, name
        assert "classify_current_run_authority" in block, name
        assert "check_native_origin" in block, name
        assert "record_run_start(" not in block, name
        assert "atomic_write_json(" not in block, name
        assert "sign_state(" not in block, name


@pytest.mark.parametrize("name,marker,mode,args", [
    ("implement.md", "NATIVE STEP 0 ADOPTION", "full", "build feature"),
    ("implement-fix.md", "NATIVE F1 ADOPTION", "fix", "--fix build feature"),
    ("implement.md", "NATIVE STEP 0 ADOPTION", "full", "fix 2 tests #1807"),
    ("implement-fix.md", "NATIVE F1 ADOPTION", "fix", "--fix fix 2 tests #1807"),
])
def test_typed_expansion_survives_step_zero_and_first_completion(monkeypatch, tmp_path, name, marker, mode, args):
    redirect = redirect_pipeline_state(monkeypatch, tmp_path, ps, pcs)
    monkeypatch.setenv("PIPELINE_STATE_FILE", str(redirect.legacy))
    monkeypatch.setenv("CLAUDE_SESSION_ID", "sess-1807-command-cutover")
    parsed_issue = pcs.extract_native_issue_number(args)
    if parsed_issue is None:
        monkeypatch.delenv("ISSUE_NUMBER", raising=False)
    else:
        monkeypatch.setenv("ISSUE_NUMBER", str(parsed_issue))
    source = (COMMANDS / name).read_text()
    snippet = source.split(f'# {marker} START', 1)[1].split(f'# {marker} END', 1)[0]
    code = snippet.split('python3 -c "', 1)[1].rsplit('\n")"', 1)[0].replace("'MODE'", f"'{mode}'")
    payload = {
        "hook_event_name": "UserPromptExpansion",
        "command_name": "implement",
        "command_args": args,
        "command_source": "user",
        "prompt": f"/implement {args}",
        "session_id": os.environ["CLAUDE_SESSION_ID"],
    }
    state = pcs.initialize_native_run_from_event(payload)
    assert state is not None
    assert state["issue_number"] == (parsed_issue if parsed_issue is not None else "")
    before = redirect.legacy.read_bytes()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(code, "implement.md STEP 0 adoption", "exec"), {})
    assert output.getvalue().strip() == state["run_id"]
    assert redirect.legacy.read_bytes() == before
    assert pcs.get_run_start_receipt(payload["session_id"]) == state["run_id"]
    assert pcs.register_native_agent_dispatch(payload["session_id"], "agent-tool-1", "alignment-classifier", False) == "registered"
    assert pcs.join_native_agent_result(payload["session_id"], "agent-tool-1", "agent-1", "completed", False) == "completed"
    ledger = json.loads(pcs._state_file_path(payload["session_id"]).read_text())
    assert ledger["completion_run_ids"]["0"]["alignment-classifier"] == state["run_id"]
    assert "alignment-classifier" in pcs.get_completed_agents(payload["session_id"])

"""Real R0 entrypoint through the accepted, independent F0 boundary."""

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PROOF = ROOT / "bootstrap/control_trust/proof"
sys.path.insert(0, str(PROOF))
import _harness as H

LEAF = ROOT / "plugins/autonomous-dev/scripts/control_evidence.py"
VERSION = "control-evidence-1"
assert H.digest(PROOF / "_harness.py") == "cba64f6fc0c3e0f8f9e5f33e20c40aceb82316a8197ed301ce10cb72e20dfcb5"


def measure(tmp_path, name, *, expected=None, change=None, source=LEAF, oracle=True):
    """Stage one leaf; retain existing fixture, oracle and publication owners."""
    assert LEAF.is_file(), "the actual R0 executable is absent"
    stage = tmp_path / "standalone"
    stage.mkdir()
    script = stage / LEAF.name
    shutil.copyfile(source, script)
    workroot = H.make_workroot(tmp_path, (name,))
    target = H.subject_path(workroot, name)
    case = {"id": "r0-process", "expected": expected or {
        "collect_exit": H.SUBJECTS[name]["collect"] or 0,
        "run_exit": 0,
        "selected_ids": H.selected_of(name),
        "selected_count": len(H.selected_of(name)),
    }, "runner": {"cwd": str(workroot), "python_version": "3.11.14",
                   "pytest_version": "8.4.2"}}
    extra = change(case, target, workroot) if change else []
    manifest = H.write_json(tmp_path / "cases.json", {"cases": [case]})
    nonce = H.new_nonce()
    argv = [H.PYTHON, "-I", "-S", "-B", script, "--target", target,
            "--workroot", workroot, "--nonce", nonce, "--python", H.PYTHON,
            "--child-timeout", "20", "--pycache-prefix", tmp_path / "unused-cache",
            "--case", case["id"], "--case-manifest", manifest]
    oracle_run = H.run_oracle(workroot, target, nonce) if oracle else None
    proc = H.run([*argv, *extra], cwd=stage, env_extra={"HOME": str(stage),
                 "PYTHONPATH": str(ROOT / "plugins/autonomous-dev/lib")})
    receipt = json.loads(proc.stdout)
    assert set(receipt) == {"schema", "case", "observation", "decision", "tool_version", "dependency_digests"}
    assert proc.stdout == json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(",", ":")) + "\n"
    assert sorted(p.name for p in stage.iterdir()) == [LEAF.name]
    orc, cand = H.write_boundary(tmp_path / "boundary", oracle_run.stdout if oracle else "", proc.stdout)
    pins = {"case_manifest": H.digest(manifest), "verifier": H.digest(script),
            "python": H.digest(Path(H.PYTHON).resolve()), "subject": H.digest(target)}
    if extra:
        pins["command_file"] = H.digest(Path(extra[extra.index("--command-file") + 1])) if "--command-file" in extra else ""
    before = (cand.stat().st_ino, cand.stat().st_mode, cand.read_bytes())
    comparison = H.compare(orc, cand, nonce, H.digest(target), case=case["id"],
                           tool_version=VERSION, dep_digests=pins) if oracle else None
    assert before == (cand.stat().st_ino, cand.stat().st_mode, cand.read_bytes())
    return proc, receipt, comparison, cand


@pytest.mark.parametrize("name,decision,leaf_exit,reason", [
    ("s_pass", "PASS", 0, None),
    ("s_runtime_fail", "FAIL", 1, None),
    ("s_collect_error", "FAIL", 1, "EMPTY_SELECTION"),
    ("s_empty", "FAIL", 1, "EMPTY_SELECTION"),
])
def test_actual_sourcefree_process_and_external_oracle(tmp_path, name, decision, leaf_exit, reason):
    proc, receipt, comparison, cand = measure(tmp_path, name)
    assert proc.returncode == leaf_exit, proc.stderr
    assert receipt["decision"] == decision
    actual = receipt["observation"]["run_exit"]
    assert actual == H.SUBJECTS[name]["run"] if H.SUBJECTS[name]["run"] is not None else actual != 0
    assert receipt["observation"]["selected"] == H.selected_of(name)
    assert receipt["observation"]["cleanup_complete"] is True
    H.expect(comparison, reason)
    before = (cand.stat().st_ino, cand.read_bytes())
    assert before == (cand.stat().st_ino, proc.stdout.encode("utf-8"))


def test_supported_accepted_caller_uses_actual_product_identity(tmp_path):
    workroot = H.make_workroot(tmp_path, ("s_runtime_fail",))
    target = H.subject_path(workroot, "s_runtime_fail")
    nonce = H.new_nonce()
    oracle = H.run_oracle(workroot, target, nonce)
    proc = H.run_candidate(workroot, target, nonce, script=LEAF)
    receipt = json.loads(proc.stdout)
    assert receipt["tool_version"] == VERSION
    assert receipt["observation"]["run_exit"] == 1
    # Historical fixture forbids effects its process oracle does not observe.
    assert receipt["decision"] == "UNMEASURED"
    assert receipt["observation"]["reason"] == "UNRESOLVED_CONTEXT"
    orc, cand = H.write_boundary(tmp_path / "boundary", oracle.stdout, proc.stdout)
    pins = {"case_manifest": H.digest(H.CASES), "verifier": H.digest(LEAF),
            "python": H.digest(Path(H.PYTHON).resolve()), "subject": H.digest(target)}
    H.expect(H.compare(orc, cand, nonce, H.digest(target), tool_version=VERSION, dep_digests=pins))


@pytest.mark.parametrize("fault,decision", [
    ("selection", "FAIL"), ("missing-expectation", "UNMEASURED"),
    ("native-key", "UNMEASURED"), ("cwd", "ERROR"),
    ("profile", "ERROR"), ("typed-exit", "ERROR"),
    ("unresolved-cwd", "UNMEASURED"),
    ("required-results", "UNMEASURED"), ("missing-versions", "UNMEASURED"),
    ("missing-pytest-version", "UNMEASURED"),
    ("missing-python-version", "UNMEASURED"),
    ("unsupported-outcome", "UNMEASURED"), ("unsupported-profile", "UNMEASURED"),
    ("empty-forbidden-effects", "PASS"),
])
def test_case_boundaries_are_not_candidate_selected(tmp_path, fault, decision):
    def change(case, target, root):
        if fault == "selection":
            case["expected"]["selected_ids"] = ["foreign/test.py::test_other"]
        elif fault == "missing-expectation":
            del case["expected"]["run_exit"]
        elif fault == "native-key":
            case["native"] = {"required_keys": ["session_id", "tool_use_id"],
                              "events": ["PreToolUse", "PostToolUse"]}
        elif fault == "typed-exit":
            case["expected"]["run_exit"] = False
        elif fault == "cwd":
            case["runner"]["cwd"] = str(root.parent / "foreign")
        elif fault == "unresolved-cwd":
            case["runner"]["cwd"] = "descriptive context"
        elif fault == "required-results":
            case["expected"]["results"] = [{"guard": "required", "verdict": "PROVEN"}]
        elif fault == "missing-versions":
            del case["runner"]["python_version"], case["runner"]["pytest_version"]
        elif fault == "missing-pytest-version":
            del case["runner"]["pytest_version"]
        elif fault == "missing-python-version":
            del case["runner"]["python_version"]
        elif fault == "unsupported-outcome":
            case["expected"]["unobserved_failures"] = 0
        elif fault == "unsupported-profile":
            case["runner"]["unobserved_plugins"] = []
        elif fault == "empty-forbidden-effects":
            case["expected"]["forbidden_effects"] = []
        else:
            case["runner"]["python_version"] = "foreign"
        return []
    proc, receipt, _, _ = measure(tmp_path, "s_pass", change=change, oracle=False)
    assert receipt["decision"] == decision
    assert (proc.returncode == 0) == (decision == "PASS")


@pytest.mark.parametrize("fault", ["timeout", "truncation", "normal", "results-mismatch"])
def test_real_owned_command_capture_and_descendant_cleanup(tmp_path, fault):
    pidfile = tmp_path / "descendant.pid"
    rows = [{"guard": "public-fixture", "verdict": "PROVEN",
             "positive": {"ok": True}, "negative": {"ok": True}}]
    projection = [{"guard": "public-fixture", "verdict": "PROVEN", "positive_ok": True,
                   "negative_ok": True, "fault_outcome": None, "injection_landed": None}]
    def change(case, target, root):
        if fault == "timeout":
            target.write_text("import subprocess,sys,time\nfrom pathlib import Path\n"
                "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
                f"Path({str(pidfile)!r}).write_text(str(p.pid))\ntime.sleep(60)\n")
        elif fault == "truncation":
            target.write_text("print('x'*100000,flush=True)\n")
        else:
            target.write_text("import json\nprint(json.dumps(" + repr({"results": rows}) + "))\n")
        case["expected"] = {"selected_ids": ["public-fixture"], "selected_count": 1,
                            "collect_exit": 0, "run_exit": 0, "results": projection}
        if fault == "results-mismatch":
            case["expected"]["results"] = [{**projection[0], "positive_ok": False}]
        case["runner"].pop("pytest_version")
        command = {"argv": [str(H.PYTHON), "-I", "-S", "-B", str(target)],
                   "cwd": str(root), "env": {"PATH": "/usr/bin:/bin", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
                   "stdin": "", "stdin_sha256": hashlib.sha256(b"").hexdigest()}
        path = H.write_json(tmp_path / "command.json", command)
        case["runner"]["command_file_sha256"] = H.digest(path)
        return ["--command-file", str(path), "--child-timeout", "0.7"]
    started = time.monotonic()
    proc, receipt, _, cand = measure(tmp_path, "s_pass", change=change, oracle=False)
    assert time.monotonic() - started < 8
    obs = receipt["observation"]
    assert obs["cleanup_complete"] is True
    assert receipt["decision"] == {"normal": "PASS", "results-mismatch": "FAIL"}.get(fault, "ERROR")
    assert obs["capture_stop"] == {"timeout": "TIMEOUT", "truncation": "TRUNCATED"}.get(fault, "")
    assert len(cand.read_bytes()) < 131072
    if fault == "timeout":
        assert pidfile.exists(), "the descendant case never reached its launch"
        with pytest.raises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)


def test_swallowed_status_mutant_is_refused_by_external_oracle(tmp_path):
    mutant = H.mutant_of(LEAF, tmp_path / "mutant",
        [('"exit": proc.returncode', '"exit": 0')], "actual R0 status owner")
    proc, receipt, comparison, _ = measure(tmp_path, "s_runtime_fail", source=mutant)
    assert receipt["observation"]["run_exit"] == 0
    assert receipt["decision"] == "PASS"
    H.expect(comparison, "RUN_EXIT_MISMATCH")


@pytest.mark.parametrize("fault,reason", [
    ("nonce", "STALE_RECORD"), ("cut", "CANDIDATE_MALFORMED"),
    ("bytes", "STALE_SUBJECT"),
])
def test_completed_private_receipt_cannot_be_substituted(tmp_path, fault, reason):
    _, receipt, _, cand = measure(tmp_path, "s_pass")
    oracle = cand.with_name("oracle.rec")
    nonce = receipt["observation"]["nonce"]
    if fault == "nonce":
        receipt["observation"]["nonce"] = "foreign"
    elif fault == "bytes":
        receipt["observation"]["subject_digest"] = "0" * 64
    cand.write_text(json.dumps(receipt)[:-3] if fault == "cut" else json.dumps(receipt))
    H.expect(H.compare(oracle, cand, nonce, tool_version=VERSION,
                      case="r0-process", dep_digests=receipt["dependency_digests"]), reason)


def test_nonregular_input_refuses_before_open_can_block(tmp_path):
    fifo = tmp_path / "case-input"
    os.mkfifo(fifo)
    proc = H.run([H.PYTHON, "-I", "-S", "-B", LEAF, "--target", tmp_path / "unused.py",
                  "--workroot", tmp_path, "--nonce", "public-input-shape-control",
                  "--python", H.PYTHON, "--pycache-prefix", tmp_path / "unused-cache",
                  "--case", "r0-process", "--case-manifest", fifo], timeout=2)
    receipt = json.loads(proc.stdout)
    assert proc.returncode == 2
    assert receipt["decision"] == "ERROR"
    assert receipt["observation"]["reason"] == "NONREGULAR_INPUT"

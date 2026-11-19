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


def measure(tmp_path, name, *, expected=None, change=None, source=LEAF, oracle=True, ambient=None):
    """Stage one leaf; retain existing fixture, oracle and publication owners."""
    assert LEAF.is_file(), "the actual R0 executable is absent"
    stage = tmp_path / "standalone"
    stage.mkdir(exist_ok=True)
    script = stage / LEAF.name
    if not script.exists():
        shutil.copyfile(source, script)
    assert H.digest(script) == H.digest(source)
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
    nonce = H.new_nonce()
    manifest = H.write_json(tmp_path / f"cases-{nonce}.json", {"cases": [case]})
    argv = [H.PYTHON, "-I", "-S", "-B", script, "--target", target,
            "--workroot", workroot, "--nonce", nonce, "--python", H.PYTHON,
            "--child-timeout", "20", "--pycache-prefix", tmp_path / "unused-cache",
            "--case", case["id"], "--case-manifest", manifest]
    oracle_run = H.run_oracle(workroot, target, nonce) if oracle else None
    proc = H.run([*argv, *extra], cwd=stage, env_extra={"HOME": str(stage),
                 "PYTHONPATH": str(ROOT / "plugins/autonomous-dev/lib"), **(ambient or {})})
    receipt = json.loads(proc.stdout)
    assert set(receipt) == {"schema", "case", "observation", "decision", "tool_version", "dependency_digests"}
    assert proc.stdout == json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(",", ":")) + "\n"
    assert sorted(p.name for p in stage.iterdir()) == [LEAF.name]
    orc, cand = H.write_boundary(tmp_path / f"boundary-{nonce}", oracle_run.stdout if oracle else "", proc.stdout)
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


@pytest.mark.parametrize("fault", ["timeout", "truncation", "normal", "results-mismatch", "effective-profile"])
def test_real_owned_command_capture_and_descendant_cleanup(tmp_path, fault):
    pidfile = tmp_path / "descendant.pid"
    ran = tmp_path / "command-ran"
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
            target.write_text("import json\nfrom pathlib import Path\n"
                f"Path({str(ran)!r}).write_text('started')\n"
                "print(json.dumps(" + repr({"results": rows}) + "))\n")
        case["expected"] = {"selected_ids": ["public-fixture"], "selected_count": 1,
                            "collect_exit": 0, "run_exit": 0, "results": projection}
        if fault == "results-mismatch":
            case["expected"]["results"] = [{**projection[0], "positive_ok": False}]
        case["runner"].pop("pytest_version")
        command = {"argv": [str(H.PYTHON), "-I", "-S", "-B", str(target)],
                   "cwd": str(root), "env": {"PATH": "/usr/bin:/bin", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
                   "stdin": "", "stdin_sha256": hashlib.sha256(b"").hexdigest()}
        if fault == "effective-profile":
            command["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "0"
        path = H.write_json(tmp_path / "command.json", command)
        case["runner"]["command_file_sha256"] = H.digest(path)
        return ["--command-file", str(path), "--child-timeout", "0.7"]
    started = time.monotonic()
    proc, receipt, _, cand = measure(tmp_path, "s_pass", change=change, oracle=False)
    assert time.monotonic() - started < 8
    obs = receipt["observation"]
    if fault == "effective-profile":
        assert receipt["decision"] == "ERROR" and obs["reason"] == "COMMAND_CONTEXT"
        assert not ran.exists()
        return
    assert obs["cleanup_complete"] is True
    assert receipt["decision"] == {"normal": "PASS", "results-mismatch": "FAIL"}.get(fault, "ERROR")
    assert obs["capture_stop"] == {"timeout": "TIMEOUT", "truncation": "TRUNCATED"}.get(fault, "")
    assert len(cand.read_bytes()) < 131072
    if fault in ("normal", "results-mismatch"):
        assert ran.read_text() == "started"
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


@pytest.mark.parametrize("complete", [False, True])
def test_actual_extra_site_requires_outside_denominator_update(tmp_path, complete):
    old = H.selected_of("s_pass")
    extra_id = "s_pass/test_s.py::test_additional_site"
    expected = {"collect_exit": 0, "run_exit": 0,
                "selected_ids": sorted([*old, extra_id]) if complete else old,
                "selected_count": 3 if complete else 2}
    def append_site(case, target, root):
        target.write_text(target.read_text() + "\ndef test_additional_site():\n    assert True\n")
        return []
    proc, receipt, comparison, _ = measure(tmp_path, "s_pass", expected=expected, change=append_site)
    observed = receipt["observation"]
    assert observed["selected"] == sorted([*old, extra_id]) and observed["selected_count"] == 3
    assert observed["run_exit"] == 0
    assert receipt["decision"] == ("PASS" if complete else "FAIL")
    assert proc.returncode == (0 if complete else 1)
    H.expect(comparison)


def test_same_leaf_and_node_set_on_failing_base_and_fixed_candidate(tmp_path):
    base_proc, base, base_compare, base_file = measure(tmp_path, "s_runtime_fail")
    script = tmp_path / "standalone" / LEAF.name
    st = script.stat()
    leaf_before = (H.digest(script), st.st_ino, st.st_mode, st.st_mtime_ns, st.st_ctime_ns)
    base_bytes = base_file.read_bytes()
    def fix(case, target, root):
        body = target.read_text()
        assert "assert v == 2" in body
        target.write_text(body.replace("assert v == 2", "assert True"))
        return []
    candidate_proc, candidate, candidate_compare, candidate_file = measure(
        tmp_path, "s_runtime_fail", change=fix)
    left, right = base["observation"], candidate["observation"]
    assert (base_proc.returncode, candidate_proc.returncode) == (1, 0)
    assert (left["run_exit"], right["run_exit"]) == (1, 0)
    assert left["selected"] == right["selected"] == H.selected_of("s_runtime_fail")
    assert left["profile"] == right["profile"] and left["target"] == right["target"]
    assert left["subject_digest"] != right["subject_digest"] and left["nonce"] != right["nonce"]
    assert base_file != candidate_file and base_file.read_bytes() == base_bytes
    st = script.stat()
    assert leaf_before == (H.digest(script), st.st_ino, st.st_mode, st.st_mtime_ns, st.st_ctime_ns)
    H.expect(base_compare)
    H.expect(candidate_compare)


def test_landed_ambient_and_source_faults_do_not_change_effective_profile(tmp_path):
    _, baseline, comparison, _ = measure(tmp_path, "s_pass")
    H.expect(comparison)
    root = tmp_path / "workroot"
    target = root / "s_pass/test_s.py"
    plugin_dir, source_dir = tmp_path / "plugins", tmp_path / "source-decoy"
    plugin_dir.mkdir()
    source_dir.mkdir()
    markers = {name: tmp_path / (name + ".landed") for name in ("plugin", "conftest", "source")}
    for path, name in ((plugin_dir / "ambient_plugin.py", "plugin"),
                       (root / "conftest.py", "conftest"), (source_dir / "json.py", "source")):
        path.write_text("from pathlib import Path\n"
            f"Path({str(markers[name])!r}).write_text('landed')\nraise RuntimeError('public probe')\n")
    addopts = H.run_profile(root, target, env_extra={"PYTEST_ADDOPTS": "-k __r0_absent"})
    assert addopts.returncode != 0 and H.sed_recover(addopts.stdout) == []
    plugin = H.run_profile(root, target, isolated=False, env_extra={
        "PYTHONPATH": str(plugin_dir), "PYTEST_PLUGINS": "ambient_plugin"})
    conftest = H.run_profile(root, target, noconftest=False)
    source = H.run([H.PYTHON, "-S", "-B", "-c", "import json"],
        cwd=tmp_path / "standalone", env_extra={"PYTHONPATH": str(source_dir)})
    assert all(result.returncode != 0 for result in (plugin, conftest, source))
    for marker in markers.values():
        assert marker.read_text() == "landed"
        marker.unlink()
    _, isolated, comparison, _ = measure(tmp_path, "s_pass", ambient={
        "PYTEST_ADDOPTS": "-k __r0_absent", "PYTEST_PLUGINS": "ambient_plugin",
        "PYTHONPATH": os.pathsep.join((str(source_dir), str(plugin_dir)))})
    H.expect(comparison)
    assert isolated["decision"] == "PASS"
    assert isolated["observation"]["profile"] == baseline["observation"]["profile"]
    assert isolated["observation"]["selected"] == H.selected_of("s_pass")
    assert all(not marker.exists() for marker in markers.values())

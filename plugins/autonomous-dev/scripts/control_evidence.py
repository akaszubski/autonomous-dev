#!/usr/bin/env python3
"""Bounded process observations; unsigned receipts, never workflow authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "control-tool-receipt-1"
VERSION = "control-evidence-1"
OUTPUT_LIMIT = 65536
ENV = {"PATH": "/usr/bin:/bin", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
PYTEST_OUTCOME = r"PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR"
PYTEST_REPORT = (r"(?:PASSED|FAILED|ERROR|(?:SKIPPED|XFAIL|XPASS)(?: \([^\r\n]*\))?)"
                 r"(?:\s+\[\s*\d+%\])?")


def unique(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_FIELD")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError("NONFINITE")


def decode(text: str) -> dict:
    return json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stamp(st: os.stat_result) -> tuple:
    return (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid,
            st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def identity(path: Path) -> tuple:
    return stamp(path.stat())


def file_fact(path: Path, collect: bool = False) -> tuple:
    """Hash a held regular file; refuse a changed or redirected referent."""
    named = path.lstat()
    if named.st_mode & 0o170000 != 0o100000:
        raise ValueError("NONREGULAR_INPUT")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if stamp(before) != stamp(named):
            raise ValueError("IDENTITY_CHANGED")
        hash_ = hashlib.sha256()
        pieces = []
        size = 0
        remaining = before.st_size
        while remaining:
            block = os.read(fd, min(remaining, 65536))
            if not block:
                raise ValueError("IDENTITY_CHANGED")
            remaining -= len(block)
            hash_.update(block)
            if collect:
                size += len(block)
                if size > 1048576:
                    raise ValueError("INPUT_TOO_LARGE")
                pieces.append(block)
        after = os.fstat(fd)
        if stamp(before) != stamp(after) or stamp(after) != stamp(path.lstat()):
            raise ValueError("IDENTITY_CHANGED")
        return hash_.hexdigest(), stamp(after), b"".join(pieces)
    finally:
        os.close(fd)


def capture(argv: list, cwd: Path, timeout: float, stdin: bytes = b"") -> dict:
    """Drain bounded streams and reap the child and its owned POSIX group."""
    started = time.time_ns()
    proc = None
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    errors = []
    stop = ""
    operation = "launch"
    reaped, closed, absent, wait_timeout = False, True, False, False
    deadline = time.monotonic() + timeout
    def note(phase: str, error: OSError) -> None:
        errors.append({"operation": phase, "errno": error.errno})
    try:
        proc = subprocess.Popen(argv, cwd=cwd, env=ENV, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                close_fds=True, start_new_session=True)
        operation = "drain"
        with selectors.DefaultSelector() as selector:
            for stream, label in ((proc.stdout, "stdout"), (proc.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, label)
            if stdin:
                os.set_blocking(proc.stdin.fileno(), False)
                selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
            else:
                proc.stdin.close()
            while selector.get_map() and not stop:
                if time.monotonic() >= deadline:
                    stop = "TIMEOUT"
                    break
                for key, _ in selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                    if key.data == "stdin":
                        written = os.write(key.fd, stdin)
                        stdin = stdin[written:]
                        if not stdin:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        continue
                    block = os.read(key.fd, 8192)
                    if not block:
                        selector.unregister(key.fileobj)
                    elif len(buffers[key.data]) + len(block) > OUTPUT_LIMIT:
                        stop = "TRUNCATED"
                        break
                    else:
                        buffers[key.data].extend(block)
            if not stop:
                operation = "wait"
                try:
                    proc.wait(timeout=max(0.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    stop = "TIMEOUT"
    except OSError as error:
        note(operation, error)
    finally:
        # No process-global handler or namespace privilege; this group was
        # created for this one invocation. Escaped sessions are not contained.
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as error:
                note("signal", error)
            # These steps are independent: a denied signal/probe never skips
            # bounded wait or closing any other owned stream.
            try:
                proc.wait(timeout=2)
                reaped = True
            except subprocess.TimeoutExpired:
                wait_timeout = True
            except OSError as error:
                note("wait", error)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    stream.close()
                except OSError as error:
                    closed = False
                    note("close", error)
            until = time.monotonic() + 2
            while time.monotonic() < until:
                try:
                    os.killpg(proc.pid, 0)
                except ProcessLookupError:
                    absent = True
                    break
                except OSError as error:
                    note("probe", error)
                    break
                time.sleep(0.01)
    if errors:
        stop = "OS_ERROR"
    elif wait_timeout and not stop:
        stop = "WAIT_TIMEOUT"
    return {"exit": proc.returncode if proc is not None else None,
            "stdout": bytes(buffers["stdout"]), "stderr": bytes(buffers["stderr"]),
            "stop": stop, "cleanup": reaped and closed and absent,
            "reaped": reaped, "pipes_closed": closed, "group_absent": absent,
            "wait_timeout": wait_timeout, "os_errors": errors,
            "started_ns": started, "ended_ns": time.time_ns()}


def node_ids(output: str) -> list:
    ids = []
    for line in output.splitlines():
        head, separator, _ = line.partition("::")
        if separator and head.endswith(".py") and head and not any(c.isspace() for c in head):
            ids.append(line)
    return sorted(ids)


def decide(case: dict, observation: dict) -> tuple[str, str]:
    """Compare case-owned expectations; never mint native identity or authority."""
    if observation.get("capture_stop") or not observation.get("cleanup_complete"):
        return "ERROR", observation.get("capture_stop") or "CLEANUP_UNPROVEN"
    if not observation.get("identities_rechecked"):
        return "ERROR", "IDENTITY_UNVERIFIED"
    if not observation.get("context_resolved"):
        return "UNMEASURED", "UNRESOLVED_CONTEXT"
    runner = case.get("runner", {})
    profile_fields = {"cwd", "python_version", "pytest_version", "command_file_sha256"}
    if set(runner) - profile_fields:
        return "UNMEASURED", "UNSUPPORTED_PROFILE_REQUIREMENT"
    versions = ("python_version", "pytest_version") if observation["pytest_version"] is not None else ("python_version",)
    if any(not runner.get(key) for key in versions):
        return "UNMEASURED", "MISSING_PROFILE_PIN"
    for key in set(runner) - {"cwd"}:
        if observation.get(key) is None:
            return "UNMEASURED", "UNOBSERVED_PROFILE_REQUIREMENT"
        if runner[key] != observation[key]:
            return "FAIL", "PROFILE_MISMATCH"
    expected = case.get("expected", {})
    selected = observation["selected"]
    if not selected or len(set(selected)) != len(selected):
        return "FAIL", "EMPTY_OR_DUPLICATE_SELECTION"
    for key, actual in (("selected_ids", selected), ("selected_count", len(selected)),
                        ("collect_exit", observation["collect_exit"]),
                        ("run_exit", observation["run_exit"])):
        if key not in expected:
            return "UNMEASURED", "MISSING_EXPECTATION"
        if expected[key] != actual:
            return "FAIL", key.upper() + "_MISMATCH"
    if "results" in expected:
        if "results" not in observation:
            return "UNMEASURED", "RESULTS_UNOBSERVED"
        if expected["results"] != observation["results"]:
            return "FAIL", "RESULTS_MISMATCH"
    supported = {"selected_ids", "selected_count", "collect_exit", "run_exit", "results", "forbidden_effects"}
    if set(expected) - supported or ("forbidden_effects" in expected and expected["forbidden_effects"] != []):
        return "UNMEASURED", "UNSUPPORTED_REQUIREMENT"
    native = case.get("native", {})
    if native:
        records = observation.get("native_records", [])
        if not records or any(any(not row.get(k) for k in native["required_keys"]) for row in records):
            return "UNMEASURED", "MISSING_NATIVE_KEY"
        if not native.get("binding"):
            return "UNMEASURED", "MISSING_NATIVE_BINDING"
        if any(any(row.get(k) != v for k, v in native["binding"].items()) for row in records):
            return "FAIL", "NATIVE_BINDING_MISMATCH"
        keys = [tuple(row[k] for k in native["required_keys"]) for row in records]
        if len(records) != len(native["events"]) or [r.get("hook_event_name") for r in records] != native["events"]:
            return "FAIL", "NATIVE_EVENT_MISMATCH"
        if any(key != keys[0] for key in keys) or len(set(r["hook_event_name"] for r in records)) != len(records):
            return "FAIL", "NATIVE_JOIN_MISMATCH"
    return "PASS", "EXPECTED_FACTS"


def pytest_results(output: str, selected: list) -> dict | None:
    """Reconcile verbose reports with complete collected IDs, including spaces.

    Stages behavior reuse from test_runner._reported_nodes; its legacy owner
    remains until consumer migration. Reports are child attestations only.
    """
    results = {}
    for line in output.splitlines():
        line = line.strip()
        if not re.match(r"^\S+\.py::", line):
            continue
        matches = [node for node in selected if line.startswith(node + " ") and
                   re.fullmatch(PYTEST_REPORT, line[len(node):].strip())]
        if len(matches) != 1:
            raise ValueError("UNEXPECTED_PYTEST_REPORT")
        node = matches[0]
        if node in results:
            raise ValueError("DUPLICATE_PYTEST_REPORT")
        results[node] = line[len(node):].split()[0]
    return results if set(results) == set(selected) else None


def pytest_argv(args: argparse.Namespace, collect: bool, per_node: bool = False) -> list:
    argv = [args.python, "-B", "-X", f"pycache_prefix={args.pycache_prefix}",
            "-I", "-m", "pytest", "-p", "no:cacheprovider", "-c", "/dev/null",
            f"--rootdir={args.workroot}", "--noconftest"]
    return [*argv, *(["--collect-only"] if collect else []),
            "-v" if per_node and not collect else "-q", args.target]


def record_process(observation: dict, argv: list, stdin: bytes, result: dict) -> None:
    """Retain only acquired process facts, including closed OS-error metadata."""
    observation["processes"].append({
        "argv": argv, "stdin_sha256": digest(stdin), "exit": result["exit"],
        "stdout_sha256": digest(result["stdout"]), "stderr_sha256": digest(result["stderr"]),
        "stdout_bytes": len(result["stdout"]), "stderr_bytes": len(result["stderr"]),
        "started_ns": result["started_ns"], "ended_ns": result["ended_ns"],
        "reaped": result["reaped"], "pipes_closed": result["pipes_closed"],
        "group_absent": result["group_absent"], "wait_timeout": result["wait_timeout"]})
    observation["os_errors"].extend(result["os_errors"])
    observation["capture_stop"] = result["stop"]


def observe(args: argparse.Namespace, case: dict, receipt: dict) -> None:
    # Publish verified facts into the same receipt as acquired. An exception
    # must not discard completed captures through a failed tuple assignment.
    observation = receipt["observation"]
    observation.update(phase="input", identities={}, identities_rechecked=False,
                       processes=[], cleanup_complete=False)
    root, target = Path(args.workroot), Path(args.target)
    if not target.is_absolute() or (not args.command_file and not target.resolve().is_relative_to(root.resolve())):
        raise ValueError("SUBJECT_OUTSIDE_CWD")
    files = {"verifier": Path(__file__), "case_manifest": Path(args.case_manifest),
             "python": Path(args.python).resolve(), "subject": target}
    if args.command_file:
        files["command_file"] = Path(args.command_file)
    before = {}
    for key, path in files.items():
        before[key] = file_fact(path)
        receipt["dependency_digests"][key] = before[key][0]
        observation["identities"][key] = before[key][1]
    cwd = identity(root)[:5]
    runner = case.get("runner", {})
    expected_cwd = runner.get("cwd")
    resolved = isinstance(expected_cwd, str) and Path(expected_cwd).is_absolute()
    if resolved and expected_cwd != str(root):
        raise ValueError("CWD_MISMATCH")
    observation.update({"stage": "executing", "python": args.python, "target": args.target,
                   "subject_digest": before["subject"][0], "nonce": args.nonce,
                   "cwd": str(root), "cwd_identity": cwd, "selected": [],
                   "selected_count": 0, "collect_exit": None, "run_exit": None,
                   "cleanup_scope": "owned_process_group", "context_resolved": resolved,
                   "capture_stop": ""})
    observation["command_file_sha256"] = before["command_file"][0] if args.command_file else None
    per_node = not args.command_file and isinstance(case.get("expected", {}).get("results"), dict)
    commands = [pytest_argv(args, True), pytest_argv(args, False, per_node)]
    stdin = b""
    if args.command_file:
        command_fact = file_fact(Path(args.command_file), True)
        if command_fact[:2] != before["command_file"][:2]:
            raise ValueError("COMMAND_CHANGED")
        command = decode(command_fact[2].decode("utf-8"))
        if set(command) != {"argv", "cwd", "env", "stdin", "stdin_sha256"}:
            raise ValueError("COMMAND_FIELDS")
        if not isinstance(command["stdin"], str) or not isinstance(command["argv"], list):
            raise ValueError("COMMAND_TYPES")
        stdin = command["stdin"].encode("utf-8")
        if command["cwd"] != str(root) or command["env"] != ENV or digest(stdin) != command["stdin_sha256"]:
            raise ValueError("COMMAND_CONTEXT")
        if case.get("runner", {}).get("command_file_sha256") != before["command_file"][0]:
            raise ValueError("COMMAND_BINDING")
        if len(stdin) > 4096 or not command["argv"] or not all(isinstance(a, str) for a in command["argv"]):
            raise ValueError("COMMAND_INPUT")
        if command["argv"][:5] != [args.python, "-I", "-S", "-B", args.target]:
            raise ValueError("COMMAND_PRODUCER")
        commands = [command["argv"]]
    probe = "import platform;print(platform.python_version())"
    if not args.command_file:
        probe += ";import pytest;print(pytest.__version__)"
    observation["phase"] = "profile"
    version_argv = [args.python, "-B", "-X", f"pycache_prefix={args.pycache_prefix}", "-I", "-c", probe]
    version = capture(version_argv, root, args.child_timeout)
    record_process(observation, version_argv, b"", version)
    observation["cleanup_complete"] = version["cleanup"]
    if version["stop"] or not version["cleanup"]:
        return
    versions = version["stdout"].decode("utf-8").splitlines()
    if version["exit"] or version["stop"] or not version["cleanup"] or len(versions) != (1 if args.command_file else 2):
        raise ValueError("PROFILE_UNMEASURED")
    observation.update(python_version=versions[0], pytest_version=versions[1] if len(versions) == 2 else None)
    for key, actual in zip(("python_version", "pytest_version"), versions):
        if key in runner and runner[key] is not None and runner[key] != actual:
            raise ValueError("PROFILE_MISMATCH")
    for index, argv in enumerate(commands):
        all_clean = observation["cleanup_complete"]
        observation.update(phase="command", cleanup_complete=False)
        result = capture(argv, root, args.child_timeout, stdin)
        record_process(observation, argv, stdin, result)
        observation["cleanup_complete"] = all_clean and result["cleanup"]
        observation["collect_exit" if index == 0 else "run_exit"] = result["exit"]
        if args.command_file:
            observation["run_exit"] = result["exit"]
        if index == 0:
            observation["selected"] = node_ids(result["stdout"].decode("utf-8"))
        if args.command_file and not result["stop"]:
            # POB keeps its legacy verdicts and persistence. Translation only
            # selects its actual guard rows; exit0 alone cannot prove protection.
            text = result["stdout"].decode("utf-8")
            body, _ = json.JSONDecoder(object_pairs_hook=unique).raw_decode(text[text.index("{"):])
            rows = body["results"]
            observation["selected"] = sorted(row["guard"] for row in rows)
            observation["results"] = [{
                "guard": row["guard"], "verdict": row["verdict"],
                "positive_ok": row.get("positive", {}).get("ok"),
                "negative_ok": row.get("negative", {}).get("ok"),
                "fault_outcome": row.get("fault", {}).get("outcome"),
                "injection_landed": row.get("fault", {}).get("injection_landed"),
            } for row in rows]
        observation["selected_count"] = len(observation["selected"])
        if result["stop"] or not result["cleanup"]:
            return
        if per_node and index == 1:
            reports = pytest_results(result["stdout"].decode("utf-8"), observation["selected"])
            if reports is not None:
                observation["results"] = reports
    observation["phase"] = "identity_recheck"
    if identity(root)[:5] != cwd or any(file_fact(path) != before[key] for key, path in files.items()):
        raise ValueError("IDENTITY_CHANGED")
    observation.update(identities_rechecked=True, phase="complete")
    observation["profile"] = {"env": ENV, "timeout_s": args.child_timeout,
                              "output_limit": OUTPUT_LIMIT, "pycache_prefix": args.pycache_prefix}


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("target", "workroot", "nonce", "python", "pycache-prefix", "case", "case-manifest"):
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--child-timeout", type=float, default=120)
    parser.add_argument("--command-file")
    args = parser.parse_args(argv)
    receipt = {"schema": SCHEMA, "case": args.case,
               "observation": {"stage": "executing", "nonce": args.nonce, "target": args.target,
                               "phase": "input", "os_errors": [], "cleanup_complete": False},
               "decision": "ERROR", "tool_version": VERSION, "dependency_digests": {}}
    try:
        if not 0 < args.child_timeout <= 300 or not args.nonce:
            raise ValueError("INVALID_BOUND")
        manifest_fact = file_fact(Path(args.case_manifest), True)
        raw = manifest_fact[2]
        manifest = decode(raw.decode("utf-8"))
        if (not isinstance(manifest, dict) or not isinstance(manifest.get("cases"), list)
                or not all(isinstance(case, dict) for case in manifest["cases"])):
            raise ValueError("MANIFEST_TYPE")
        cases = [case for case in manifest["cases"] if case["id"] == args.case]
        if len(cases) != 1:
            raise ValueError("CASE_NOT_UNIQUE")
        case = cases[0]
        if not isinstance(case.get("expected"), dict) or not isinstance(case.get("runner", {}), dict):
            raise ValueError("CASE_TYPES")
        expected = case["expected"]
        for key in ("collect_exit", "run_exit", "selected_count"):
            if key in expected and type(expected[key]) is not int:
                raise ValueError("EXPECTATION_TYPE")
        if "selected_ids" in expected and (not isinstance(expected["selected_ids"], list)
                or not all(isinstance(v, str) for v in expected["selected_ids"])):
            raise ValueError("SELECTION_TYPE")
        if not args.command_file and isinstance(expected.get("results"), dict):
            results = expected["results"]
            if (not results or set(results) != set(expected.get("selected_ids", []))
                    or any(not isinstance(value, str) or not re.fullmatch(PYTEST_OUTCOME, value)
                           for value in results.values())):
                raise ValueError("PYTEST_RESULTS_EXPECTATION")
        observe(args, cases[0], receipt)
        if receipt["dependency_digests"]["case_manifest"] != manifest_fact[0]:
            raise ValueError("MANIFEST_CHANGED")
        receipt["decision"], reason = decide(cases[0], receipt["observation"])
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        if isinstance(error, OSError):
            receipt["observation"]["os_errors"].append({
                "operation": receipt["observation"]["phase"], "errno": error.errno})
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch("[A-Z_]+", str(error)) else type(error).__name__
        receipt["decision"] = "ERROR"
    receipt["observation"]["reason"] = reason
    text = json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")) + "\n"
    if len(text.encode("utf-8")) > 2 * OUTPUT_LIMIT:
        receipt.update(decision="ERROR", observation={"reason": "RECEIPT_TOO_LARGE"})
        text = json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    sys.stdout.write(text)
    return {"PASS": 0, "FAIL": 1, "UNMEASURED": 1, "ERROR": 2}[receipt["decision"]]


if __name__ == "__main__":
    raise SystemExit(main())

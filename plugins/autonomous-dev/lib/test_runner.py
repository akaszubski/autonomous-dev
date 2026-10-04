#!/usr/bin/env python3
"""
Test Runner Library - Autonomous test execution with structured results.

This library autonomously executes pytest and returns structured TestResult
objects with pass/fail counts, output, and duration.

Features:
- Execute pytest and return structured TestResult
- Run single test file or function
- Verify all tests pass (boolean check)
- Handle pytest not found gracefully
- Handle timeout gracefully
- Handle test failures gracefully
- Parse pytest output for counts and duration

Usage:
    from test_runner import run_tests, verify_all_tests_pass, TestRunner

    # Run all tests
    result = run_tests()
    if result.passed:
        print(f"All {result.pass_count} tests passed!")

    # Run single test
    result = run_single_test("tests/unit/test_example.py::test_feature")

    # Quick boolean check
    if verify_all_tests_pass():
        print("All tests pass!")

    # Stateful execution
    runner = TestRunner(timeout=60, verbose=True)
    result = runner.run()

Author: implementer agent
Date: 2026-01-03
Related: Issue #200 - Debug-first enforcement and self-test requirements
"""

import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Optional



_NODE = re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)\b")
_PROFILE_KEYS = ("PYTEST_", "PYTHON", "COVERAGE_", "HYPOTHESIS_")
_SOURCE_ROOTS = ("plugins/", "tests/", "scripts/")

# Fixed trusted-parent program, not consumer code or an installed JS service.
_SANDBOX_CAPTURE_BRIDGE = r"""
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const pins = input.sandbox;
let initialized = false, manager, child, timer;
try {
  for (const name of ['node', 'runtime', 'python', 'profile']) {
    if (hash(fs.readFileSync(pins[name])) !== pins[name + '_sha256'])
      throw Error('pin mismatch');
  }
  const root = path.resolve(path.dirname(pins.runtime), '../../..');
  const closure = crypto.createHash('sha256');
  function walk(dir) {
    for (const name of fs.readdirSync(dir).sort()) {
      const file = path.join(dir, name), stat = fs.lstatSync(file);
      if (stat.isDirectory()) walk(file);
      else {
        closure.update(JSON.stringify([path.relative(root, file), stat.mode & 0o777,
          stat.isSymbolicLink() ? 'link' : 'file']));
        closure.update('\0');
        closure.update(stat.isSymbolicLink() ? fs.readlinkSync(file) : fs.readFileSync(file));
        closure.update('\0');
      }
    }
  }
  walk(root);
  if (closure.digest('hex') !== pins.runtime_closure_sha256) throw Error('closure mismatch');
  const api = await import(pathToFileURL(pins.runtime).href);
  manager = api.SandboxManager;
  const config = api.SandboxRuntimeConfigSchema.parse(JSON.parse(fs.readFileSync(pins.profile)));
  if (config.enableWeakerNestedSandbox !== false || config.filesystem?.disabled ||
      config.network?.allowedDomains?.length !== 0) throw Error('strict profile required');
  // Stock generateProxyEnvVars interpolates this supported value in its prefix.
  // The parent validates the explicit path before launching; never read ambient overrides.
  process.env.CLAUDE_CODE_TMPDIR = input.environment.TMPDIR;
  delete process.env.CLAUDE_TMPDIR;
  await manager.initialize(config); initialized = true;
  const quote = value => "'" + value.replaceAll("'", "'\"'\"'") + "'";
  const launch = await manager.wrapWithSandboxArgv(input.argv.map(quote).join(' '),
    '/bin/bash', undefined, undefined, input.cwd);
  // Never export wrapped argv or the generated proxy environment.
  const secrets = [];
  const token = manager.getProxyAuthToken();
  if (token) secrets.push(token);
  const proxyValues = Object.entries(launch.env)
    .filter(([key, value]) => /proxy/i.test(key) && typeof value === 'string')
    .map(([, value]) => value);
  // On macOS stock transport variables are inside the command, not launch.env.
  for (const arg of launch.argv)
    proxyValues.push(...(arg.match(/(?:https?|socks5h?):\/\/[^\s'"<>]+/g) || []));
  for (const value of proxyValues) {
    if (value) {
      secrets.push(value);
      try {
        const url = new URL(value);
        if (url.username) secrets.push(url.username, decodeURIComponent(url.username));
        if (url.password) secrets.push(url.password, decodeURIComponent(url.password));
        if (url.username && url.password) secrets.push(Buffer.from(
          decodeURIComponent(url.username) + ':' + decodeURIComponent(url.password)).toString('base64'));
      } catch {}
    }
  }
  child = spawn(launch.argv[0], launch.argv.slice(1), {cwd:input.cwd,
    env:{...input.environment, ...launch.env}, detached:false,
    stdio:['ignore', 'pipe', 'pipe']});
  let size = 0, overflow = false, timedOut = false;
  const buffers = {stdout:[], stderr:[]};
  const counts = {stdout:0, stderr:0};
  const hashes = {stdout:crypto.createHash('sha256'), stderr:crypto.createHash('sha256')};
  const append = (name, bytes) => {
    counts[name] += bytes.length; hashes[name].update(bytes);
    size += bytes.length;
    if (size > input.max_bytes) { overflow = true; child.kill('SIGKILL'); }
    else buffers[name].push(bytes);
  };
  child.stdout.on('data', bytes => append('stdout', bytes));
  child.stderr.on('data', bytes => append('stderr', bytes));
  timer = setTimeout(() => {timedOut = true; child.kill('SIGKILL');},
    Math.max(1, input.deadline_ms - Date.now()));
  const terminal = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', (code, signal) => resolve({code, signal}));
  });
  clearTimeout(timer);
  await manager.reset(); initialized = false;
  const raw = {stdout:Buffer.concat(buffers.stdout), stderr:Buffer.concat(buffers.stderr)};
  const clean = name => {
    let value = new TextDecoder('utf-8', {fatal:true}).decode(raw[name]);
    for (const secret of secrets) value = value.split(secret).join('[REDACTED_PROXY]');
    return value;
  };
  process.stdout.write(JSON.stringify({terminal, overflow, timedOut,
    stdout:clean('stdout'), stderr:clean('stderr'), output_metadata:{
      stdout_bytes:counts.stdout, stdout_sha256:hashes.stdout.digest('hex'),
      stderr_bytes:counts.stderr, stderr_sha256:hashes.stderr.digest('hex'),
      export:'redacted_proxy_credentials', export_complete:!overflow}}));
} catch {
  process.exitCode = 19;
} finally {
  clearTimeout(timer);
  if (child && child.exitCode === null) child.kill('SIGKILL');
  if (initialized) await manager.reset();
}
"""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def observe_checkout(
    repo: Path, subjects: tuple[str, ...], *, deadline: Optional[float] = None,
) -> dict:
    """Bind relevant source, frozen inputs and tracked diff without importing them.

    Args:
        repo: Existing consumer Git checkout.
        subjects: Independently frozen root-relative inputs, including consumer
            untracked inputs. Automatic untracked roots retain the legacy
            plugins/tests/scripts convention, not a generic consumer closure.
        deadline: Optional absolute monotonic deadline shared with capture.

    Returns:
        Existing checkout and SHA-256 input observation. observation_schema is
        raw-checkout/1: diff_sha256 binds raw tracked paths, types, modes, bytes
        and staged index records, NOT Git diff bytes or consumer filter output.

    Raises:
        ValueError: Missing/outside inputs or an incomplete timed observation.
        subprocess.CalledProcessError: Git could not observe the checkout.
    """
    root = repo.resolve(strict=True)
    if deadline is None:
        deadline = time.monotonic() + 30
    def hash_file(target: Path) -> tuple[bytes, int]:
        digest, count = hashlib.sha256(), 0
        try:
            descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            raise ValueError("input cannot be safely opened") from None
        with os.fdopen(descriptor, "rb") as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > 16 * 1024 * 1024:
                raise ValueError("input is not a bounded regular file")
            for chunk in iter(lambda: source.read(65536), b""):
                if time.monotonic() >= deadline:
                    raise ValueError("input observation deadline expired")
                digest.update(chunk)
                count += len(chunk)
                if count > 16 * 1024 * 1024:
                    raise ValueError("input exceeded observation size cap")
            after = os.fstat(source.fileno())
            def identity(item: os.stat_result) -> tuple:
                return (item.st_dev, item.st_ino, item.st_mode, item.st_size,
                        item.st_mtime_ns, item.st_ctime_ns)
            if identity(before) != identity(after) or identity(after) != identity(target.lstat()):
                raise ValueError("input changed during bounded observation")
        return digest.digest(), count

    git_environment = {
        "PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
    }
    def git(*args: str) -> bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("checkout observation deadline expired")
        if not Path("/usr/bin/git").is_file():
            raise ValueError("trusted Git executable unavailable")
        process = subprocess.Popen(
            ["/usr/bin/git", "-c", "core.fsmonitor=false", *args], cwd=root,
            env=git_environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True,
        )
        output, size = [], 0
        cleanup_reserve = min(0.5, remaining / 4)
        try:
            with selectors.DefaultSelector() as streams:
                for pipe in (process.stdout, process.stderr):
                    streams.register(pipe, selectors.EVENT_READ)
                while streams.get_map():
                    wait = deadline - time.monotonic() - cleanup_reserve
                    if wait <= 0:
                        raise ValueError("Git inventory observation deadline expired")
                    for key, _ in streams.select(wait):
                        data = os.read(key.fd, 65536)
                        if not data:
                            streams.unregister(key.fileobj)
                            continue
                        size += len(data)
                        if size > 8 * 1024 * 1024:
                            raise ValueError("Git inventory output cap exceeded")
                        if key.fileobj is process.stdout:
                            output.append(data)
            code = process.wait(timeout=max(0.001, deadline-time.monotonic()-cleanup_reserve))
            if code:
                raise ValueError("Git inventory observation failed")
            return b"".join(output)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("checkout observation incomplete") from exc
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=max(0.001, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                raise ValueError("Git inventory cleanup incomplete") from None
            finally:
                process.stdout.close()
                process.stderr.close()

    untracked = [
        name.decode() for name in git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
        if name and name.decode().startswith(_SOURCE_ROOTS)
    ]
    hashes = {}
    for name in sorted(set(subjects) | set(untracked)):
        target = (root / name).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError(f"required input missing or outside checkout: {name}")
        hashes[name] = hash_file(target)[0].hex()
    # No worktree Git diff: it can invoke consumer clean/process converters.
    raw_state = hashlib.sha256(b"raw-checkout/1\0")
    for record in git("ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError("tracked inventory observation deadline expired")
        metadata, name = record.split(b"\t", 1)
        if metadata.split(b" ", 1)[0] == b"160000":
            raise ValueError("gitlink contents cannot be observed by raw-checkout/1")
        target = root / os.fsdecode(name)
        if not target.parent.resolve().is_relative_to(root):
            raise ValueError("tracked input parent is outside checkout")
        raw_state.update(len(record).to_bytes(8, "big") + record)
        try:
            mode = target.lstat().st_mode
        except FileNotFoundError:
            raw_state.update(b"\0")
            continue
        raw_state.update(b"\1" + mode.to_bytes(8, "big"))
        digest, count = hashlib.sha256(b"").digest(), 0
        if stat.S_ISLNK(mode):
            link = os.fsencode(os.readlink(target))
            digest, count = hashlib.sha256(link).digest(), len(link)
        elif stat.S_ISREG(mode):
            digest, count = hash_file(target)
        raw_state.update(count.to_bytes(8, "big") + digest)
    return {
        "observation_schema": "raw-checkout/1",
        "repo": str(root),
        "head": git("rev-parse", "HEAD").decode().strip(),
        "diff_sha256": raw_state.hexdigest(),
        "inputs": hashes,
    }


@dataclass(frozen=True)
class PytestRunCapture:
    """Parent process evidence; node outcomes are configuration-bound attestation.

    stdout/stderr are proxy-redacted exports, not byte-identical raw output.
    output_metadata counts and hashes the complete raw child pipes before redaction.
    """

    argv: tuple[str, ...]
    environment_sha256: str
    raw_exit: Optional[int]
    stdout: str
    stderr: str
    outcomes: dict[str, str]
    checkout: dict
    output_metadata: Optional[dict] = None

    @classmethod
    def from_mapping(cls, data: dict) -> "PytestRunCapture":
        """Restore the baseline from existing session state."""
        return cls(tuple(data["argv"]), data["environment_sha256"], data["raw_exit"],
                   data["stdout"], data["stderr"], data["outcomes"], data["checkout"],
                   data.get("output_metadata"))


def _reported_nodes(stdout: str) -> dict[str, str]:
    nodes: dict[str, str] = {}
    for line in stdout.splitlines():
        match = _NODE.match(line.strip())
        if match:
            node, outcome = match.groups()
            if node in nodes and nodes[node] != outcome:
                raise ValueError(f"conflicting pytest reports for {node}")
            nodes[node] = outcome
    return nodes


def build_pytest_argv(
    python: str, repo: str, selectors: tuple[str, ...], *, controlled: bool = False
) -> tuple[str, ...]:
    """Build the shared restricted pytest command without IO or execution.

    Args:
        python: Previously validated pinned Python executable path.
        repo: Previously validated canonical absolute checkout path.
        selectors: Frozen test node IDs in their adopted order.
        controlled: Use the isolated controlled-observation configuration.

    Returns:
        Exact argv shared by capture and obligation consistency checks.

    """
    prefix = (python, "-I", "-m", "pytest")
    control = (
        "--noconftest", "-c", os.devnull, "--rootdir", repo,
        "--confcutdir", repo, "-p", "no:cacheprovider",
    ) if controlled else ()
    return prefix + control + ("-vv", *selectors)


def capture_pytest_run(
    repo: Path, selectors: tuple[str, ...], *, subjects: tuple[str, ...],
    timeout: int = 600, environment: Optional[dict[str, str]] = None,
    controlled: bool = False, sandbox: Optional[dict[str, str]] = None,
    max_output_bytes: int = 1024 * 1024,
) -> PytestRunCapture:
    """Capture a bounded stock-sandbox child, without granting receipt authority.

    Args:
        repo: Consumer checkout, never imported by the trusted parent.
        selectors: Independently frozen exact pytest selection.
        subjects: Explicit frozen inputs, including untracked consumer inputs;
            this API does not establish a complete loaded-plugin/input closure.
        timeout: Total capture budget, including startup and cleanup, at most 600s.
        environment: Explicit credential-free environment, with no ambient fallback.
        controlled: Whether to use the existing isolated N4B pytest configuration.
        sandbox: Explicit immutable node/runtime/python/profile paths, corresponding
            SHA-256 pins and runtime_closure_sha256, supplied outside actor.
        max_output_bytes: Complete combined child pipe limit, at most one MiB.

    Returns:
        Complete configuration-bound process evidence, not a release certificate.

    Raises:
        ValueError: Missing pins, changed inputs, incomplete output or unsafe lifecycle.
        KeyboardInterrupt: Cancellation after process-group cleanup.
    """
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= (30 if controlled else 600):
        raise ValueError("sandbox capture budget is out of bounds")
    deadline = time.monotonic() + timeout
    cleanup_reserve = min(1.0, timeout / 4)
    if type(max_output_bytes) is not int or not 1024 <= max_output_bytes <= 1024 * 1024:
        raise ValueError("sandbox output limit is out of bounds")
    if not isinstance(sandbox, dict) or environment is None:
        raise ValueError("explicit sandbox pins and environment are required")
    for name in ("node", "runtime", "python", "profile"):
        target, digest = sandbox.get(name), sandbox.get(name + "_sha256")
        if (not isinstance(target, str) or not Path(target).is_absolute()
                or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValueError("sandbox paths and SHA-256 pins are required")
        try:
            measured = _digest(Path(target).read_bytes())
        except OSError as exc:
            raise ValueError("sandbox pinned input unavailable") from exc
        if measured != digest:
            raise ValueError("sandbox pinned input changed")
    if not isinstance(sandbox.get("runtime_closure_sha256"), str) or not re.fullmatch(
        r"[a-f0-9]{64}", sandbox["runtime_closure_sha256"]
    ):
        raise ValueError("sandbox dependency closure pin is required")
    if not selectors or any(not item or item.startswith("-") for item in selectors):
        raise ValueError("pytest selectors must be nonempty frozen node IDs")
    env = dict(environment)
    if any(not isinstance(key, str) or not isinstance(value, str)
           or not (key in {"PATH", "LANG", "LC_ALL", "TMPDIR", "HOME"}
                   or key.startswith(_PROFILE_KEYS)) for key, value in env.items()):
        raise ValueError("sandbox environment is not an explicit credential-free profile")
    temporary = env.get("TMPDIR", "")
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", temporary) or not Path(temporary).is_dir():
        raise ValueError("sandbox TMPDIR must be an existing safe absolute work path")
    configuration = json.loads(Path(sandbox["profile"]).read_bytes())
    writable = configuration.get("filesystem", {}).get("allowWrite", [])
    if not any(isinstance(item, str) and Path(item).is_absolute()
               and Path(item).resolve() == Path(temporary).resolve() for item in writable):
        raise ValueError("sandbox TMPDIR is not an explicitly allowed work path")
    if controlled:
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    argv = build_pytest_argv(sandbox["python"], str(repo.resolve()), selectors, controlled=controlled)
    profile = {"environment": env, "sandbox": sandbox,
               "runtime_environment": {"CLAUDE_CODE_TMPDIR": temporary},
               "max_output_bytes": max_output_bytes}
    snapshot = observe_checkout(repo, subjects, deadline=deadline)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ValueError("sandbox capture deadline expired before launch")
    payload = json.dumps({"sandbox": sandbox, "environment": env, "argv": argv,
                          "cwd": str(repo.resolve()), "max_bytes": max_output_bytes,
                          "deadline_ms": int((time.time() + remaining - cleanup_reserve) * 1000)})
    process = subprocess.Popen(
        [sandbox["node"], "--input-type=module", "-e", _SANDBOX_CAPTURE_BRIDGE],
        cwd="/", env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )
    def cancel(signum, frame):
        raise KeyboardInterrupt

    previous = {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, cancel)
        output, _ = process.communicate(
            payload.encode(), timeout=max(0.001, deadline - time.monotonic() - cleanup_reserve),
        )
        # Any surviving group member invalidates capture, even if pytest exited 0.
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise ValueError("sandbox child process group remained alive")
        if process.returncode != 0 or len(output) > 7 * 1024 * 1024:
            raise ValueError("sandbox bridge has no complete bounded capture")
        result = json.loads(output)
        terminal = result["terminal"]
        if (result["timedOut"] or result["overflow"] or terminal["signal"]
                or type(terminal["code"]) is not int):
            raise ValueError("sandbox child capture was cancelled or incomplete")
        if terminal["code"] >= 128:
            raise ValueError(f"sandbox wrapped child nonqualifying raw exit: {terminal['code']}")
        if observe_checkout(repo, subjects, deadline=deadline) != snapshot:
            raise ValueError("checkout changed during sandbox capture")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("sandbox capture incomplete") from exc
    finally:
        try:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.communicate(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as exc:
                raise ValueError("sandbox process-group cleanup incomplete") from exc
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                pass
            else:
                raise ValueError("sandbox process-group cleanup uncertain")
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
    return PytestRunCapture(
        argv, _digest(json.dumps(profile, sort_keys=True).encode()),
        terminal["code"], result["stdout"], result["stderr"],
        _reported_nodes(result["stdout"]), snapshot, result.get("output_metadata"),
    )


def _check_capture(capture: PytestRunCapture, required_ids: tuple[str, ...]) -> None:
    if capture.raw_exit not in (0, 1) or not capture.stdout.strip():
        raise ValueError("pytest process has no complete measured raw exit/output")
    if capture.checkout.get("observation_schema") != "raw-checkout/1":
        raise ValueError("checkout observation schema is changed or unmeasured")
    if set(capture.outcomes) != set(required_ids):
        raise ValueError("pytest selection differs from frozen required IDs")
    if _reported_nodes(capture.stdout) != capture.outcomes:
        raise ValueError("pytest outcome conflicts with complete captured output")


def build_pytest_dispatch_receipt(
    base: PytestRunCapture, candidate: PytestRunCapture,
    required_ids: tuple[str, ...], *, run_id: str,
    independent_cases: Optional[dict[str, str]] = None,
    independent_observations: Optional[dict[str, str]] = None,
) -> dict:
    """Evaluate one baseline/current pair for reviewer dispatch only."""
    if not run_id or not required_ids or len(required_ids) != len(set(required_ids)):
        raise ValueError("current run and unique frozen required IDs are mandatory")
    _check_capture(base, required_ids)
    _check_capture(candidate, required_ids)
    if base.argv != candidate.argv or base.environment_sha256 != candidate.environment_sha256:
        raise ValueError("base/candidate effective pytest profile differs")
    if base.checkout["repo"] != candidate.checkout["repo"]:
        raise ValueError("base/candidate checkout differs")
    for test_id in required_ids:
        old, new = base.outcomes[test_id], candidate.outcomes[test_id]
        if new in {"SKIPPED", "XFAIL", "XPASS"}:
            raise ValueError(f"required test not executed normally: {test_id}")
        if new in {"FAILED", "ERROR"} and old not in {"FAILED", "ERROR"}:
            raise ValueError(f"new failure/error: {test_id}")
    if any(candidate.checkout["inputs"].get(path) != digest
           for path, digest in base.checkout["inputs"].items()):
        raise ValueError("frozen acceptance/configuration inputs changed")
    cases = independent_cases or {}
    if not cases or any(value != "PASSED" for value in cases.values()):
        raise ValueError("independent changed-behavior cases missing or failed")
    observations = independent_observations or {}
    for test_id, observed in observations.items():
        if test_id in candidate.outcomes and candidate.outcomes[test_id] != observed:
            raise ValueError(f"independent observation contradicts pytest report: {test_id}")
    if candidate.checkout != observe_checkout(
        Path(candidate.checkout["repo"]), tuple(candidate.checkout["inputs"])
    ):
        raise ValueError("checkout changed after pytest capture")
    return {
        "schema": "pytest-dispatch-attestation/1", "claim": "reviewer-dispatch-only",
        "run_id": run_id, "required_ids": list(required_ids),
        "base": asdict(base), "candidate": asdict(candidate),
        "independent_cases": cases, "independent_observations": observations,
    }


def validate_pytest_dispatch_receipt(
    receipt: object, repo: Path, run_id: str
) -> tuple[bool, str]:
    """Re-evaluate the bound capture at the ordering consumer; refuse bare markers."""
    if not isinstance(receipt, dict) or receipt.get("schema") != "pytest-dispatch-attestation/1":
        return False, "missing pytest dispatch receipt"
    if receipt.get("claim") != "reviewer-dispatch-only" or receipt.get("run_id") != run_id:
        return False, "pytest receipt has wrong claim or run"
    if not isinstance(receipt.get("candidate"), dict) or "raw_exit" not in receipt["candidate"]:
        return False, "missing complete parent-observed raw pytest exit"
    try:
        base = PytestRunCapture.from_mapping(receipt["base"])
        candidate = PytestRunCapture.from_mapping(receipt["candidate"])
        if Path(candidate.checkout["repo"]) != repo.resolve():
            raise ValueError("pytest receipt belongs to another checkout")
        build_pytest_dispatch_receipt(
            base, candidate, tuple(receipt["required_ids"]), run_id=run_id,
            independent_cases=receipt["independent_cases"],
            independent_observations=receipt["independent_observations"],
        )
    except (KeyError, TypeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        return False, str(exc)
    return True, "configuration-bound pytest attestation permits reviewer dispatch only"


@dataclass
class TestResult:
    """
    Structured test execution result.

    Attributes:
        passed: True if all tests passed (no failures or errors)
        pass_count: Number of tests that passed
        fail_count: Number of tests that failed
        error_count: Number of tests that errored
        output: Raw pytest output
        duration_seconds: Test execution time in seconds
    """

    passed: bool
    pass_count: int
    fail_count: int
    error_count: int
    output: str
    duration_seconds: float


def _parse_pytest_output(stdout: str, stderr: str, returncode: int) -> TestResult:
    """
    Parse pytest output to extract test counts and duration.

    Args:
        stdout: pytest stdout output
        stderr: pytest stderr output
        returncode: pytest exit code

    Returns:
        TestResult with parsed counts and duration
    """
    output = stdout + stderr

    # Parse counts from pytest summary line
    # Examples:
    # "===== 10 passed in 1.23s ====="
    # "===== 5 passed, 2 failed in 2.34s ====="
    # "===== 3 passed, 1 failed, 1 error in 3.45s ====="
    # "===== 1 error in 0.12s ====="

    pass_count = 0
    fail_count = 0
    error_count = 0
    duration_seconds = 0.0

    # Extract passed count
    pass_match = re.search(r'(\d+)\s+passed', stdout)
    if pass_match:
        pass_count = int(pass_match.group(1))

    # Extract failed count
    fail_match = re.search(r'(\d+)\s+failed', stdout)
    if fail_match:
        fail_count = int(fail_match.group(1))

    # Extract error count
    error_match = re.search(r'(\d+)\s+error', stdout)
    if error_match:
        error_count = int(error_match.group(1))

    # Extract duration
    duration_match = re.search(r'in\s+([\d.]+)s', stdout)
    if duration_match:
        duration_seconds = float(duration_match.group(1))

    # Determine if all tests passed
    passed = returncode == 0 and fail_count == 0 and error_count == 0

    return TestResult(
        passed=passed,
        pass_count=pass_count,
        fail_count=fail_count,
        error_count=error_count,
        output=output,
        duration_seconds=duration_seconds,
    )


def run_tests(
    test_dir: Optional[str] = None,
    pattern: Optional[str] = None,
    verbose: bool = False,
    coverage: bool = False,
    timeout: int = 300,
) -> TestResult:
    """
    Run pytest and return structured results.

    Args:
        test_dir: Directory to run tests in (default: current directory)
        pattern: Test file pattern to match (e.g., "test_*.py")
        verbose: Use verbose output (-v) instead of quiet (-q)
        coverage: Run with coverage (--cov)
        timeout: Timeout in seconds (default: 300)

    Returns:
        TestResult with test execution results

    Examples:
        >>> result = run_tests()
        >>> if result.passed:
        ...     print(f"All {result.pass_count} tests passed!")

        >>> result = run_tests(test_dir="tests/unit", verbose=True)
        >>> print(f"{result.pass_count} passed, {result.fail_count} failed")
    """
    # Build pytest command
    cmd = ["pytest"]

    # Add test directory or current directory
    if test_dir:
        cmd.append(test_dir)

    # Add pattern if provided
    if pattern:
        cmd.extend(["-k", pattern])

    # Add verbosity flags
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add coverage if requested
    if coverage:
        cmd.extend(["--cov"])

    # Always use line traceback for consistent output
    cmd.append("--tb=line")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )

        return _parse_pytest_output(result.stdout, result.stderr, result.returncode)

    except FileNotFoundError:
        # pytest not installed
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output="Error: pytest not found. Please install pytest.",
            duration_seconds=0.0,
        )

    except TimeoutExpired:
        # Test execution timeout
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output=f"Error: Test execution timeout after {timeout} seconds.",
            duration_seconds=float(timeout),
        )

    except KeyboardInterrupt:
        # User interrupted test execution
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output="Error: Test execution interrupted by user.",
            duration_seconds=0.0,
        )

    except Exception as e:
        # Unexpected error
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output=f"Error: Unexpected error during test execution: {e}",
            duration_seconds=0.0,
        )


def run_single_test(test_path: str, timeout: int = 300) -> TestResult:
    """
    Run a single test file or function.

    Args:
        test_path: Path to test file or function (e.g., "tests/unit/test_example.py::test_feature")
        timeout: Timeout in seconds (default: 300)

    Returns:
        TestResult with test execution results

    Examples:
        >>> result = run_single_test("tests/unit/test_example.py")
        >>> result = run_single_test("tests/unit/test_example.py::test_feature")
        >>> result = run_single_test("tests/unit/test_example.py::TestClass::test_method")
    """
    # Build pytest command
    cmd = ["pytest", test_path, "-q", "--tb=line"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )

        return _parse_pytest_output(result.stdout, result.stderr, result.returncode)

    except FileNotFoundError:
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output="Error: pytest not found. Please install pytest.",
            duration_seconds=0.0,
        )

    except TimeoutExpired:
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output=f"Error: Test execution timeout after {timeout} seconds.",
            duration_seconds=float(timeout),
        )

    except Exception as e:
        return TestResult(
            passed=False,
            pass_count=0,
            fail_count=0,
            error_count=1,
            output=f"Error: {e}",
            duration_seconds=0.0,
        )


def verify_all_tests_pass(test_dir: Optional[str] = None, timeout: int = 300) -> bool:
    """
    Quick boolean check if all tests pass.

    Args:
        test_dir: Directory to run tests in (default: current directory)
        timeout: Timeout in seconds (default: 300)

    Returns:
        True if all tests passed, False otherwise

    Examples:
        >>> if verify_all_tests_pass():
        ...     print("All tests pass!")
        >>> if verify_all_tests_pass(test_dir="tests/unit"):
        ...     print("All unit tests pass!")
    """
    result = run_tests(test_dir=test_dir, timeout=timeout)
    return result.passed


class TestRunner:
    """
    Stateful test runner for repeated test execution.

    Attributes:
        timeout: Timeout in seconds (default: 300)
        verbose: Use verbose output (default: False)

    Examples:
        >>> runner = TestRunner(timeout=60, verbose=True)
        >>> result = runner.run()
        >>> if result.passed:
        ...     print("All tests passed!")

        >>> runner = TestRunner()
        >>> if runner.verify():
        ...     print("All tests pass!")
    """

    def __init__(self, timeout: int = 300, verbose: bool = False):
        """
        Initialize TestRunner.

        Args:
            timeout: Timeout in seconds (default: 300)
            verbose: Use verbose output (default: False)
        """
        self.timeout = timeout
        self.verbose = verbose

    def run(
        self,
        test_dir: Optional[str] = None,
        pattern: Optional[str] = None,
        coverage: bool = False,
    ) -> TestResult:
        """
        Run tests with configured settings.

        Args:
            test_dir: Directory to run tests in (default: current directory)
            pattern: Test file pattern to match
            coverage: Run with coverage

        Returns:
            TestResult with test execution results
        """
        return run_tests(
            test_dir=test_dir,
            pattern=pattern,
            verbose=self.verbose,
            coverage=coverage,
            timeout=self.timeout,
        )

    def run_single(self, test_path: str) -> TestResult:
        """
        Run a single test file or function.

        Args:
            test_path: Path to test file or function

        Returns:
            TestResult with test execution results
        """
        return run_single_test(test_path, timeout=self.timeout)

    def verify(self, test_dir: Optional[str] = None) -> bool:
        """
        Quick boolean check if all tests pass.

        Args:
            test_dir: Directory to run tests in (default: current directory)

        Returns:
            True if all tests passed, False otherwise
        """
        return verify_all_tests_pass(test_dir=test_dir, timeout=self.timeout)

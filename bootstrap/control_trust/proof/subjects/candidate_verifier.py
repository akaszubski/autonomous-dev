#!/usr/bin/env python3
"""The executing candidate verifier for F0, standing in for a later R0 verifier:
a SUBJECT of measurement, never a measuring instrument. It emits the CANONICAL
RECEIPT R0 emits, and the MC-* mutants break it on purpose."""

# Its selection logic is deliberately an INDEPENDENT expression of the contract,
# not a copy of the oracle's sed, and is never compared against the oracle's
# parser to decide correctness: both are checked against a hand-declared
# expected set, because two implementations sharing one false assumption is
# exactly how a valid space-bearing node id was silently lost.

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

# The ONE public canonical receipt schema. The flat `f0-oracle-1` framing is the
# POSIX oracle's PRIVATE bootstrap protocol and is deliberately not used here.
RECEIPT_SCHEMA = "control-tool-receipt-1"
# The FIXTURE's own version. Not Python's, not pytest's.
TOOL_VERSION = "candidate-verifier-1"
# Hoisted so the probe call below stays one short line.
VERSION_PROBE = "import platform;print(platform.python_version())"


def _env() -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _argv(python: str, workroot: str, target: str, collect: bool, pfx: str) -> list[str]:
    # -B keeps bytecode out of the subject tree (no-write); -X pycache_prefix
    # redirects the LOOKUP away from any pre-existing __pycache__ (no stale
    # read). Measured: -B alone still serves a stale .pyc after a same-size,
    # same-mtime rewrite. -I ignores the equivalent env vars, so both are flags.
    argv = [python, "-B", "-X", f"pycache_prefix={pfx}", "-I", "-m", "pytest"]
    argv += ["-p", "no:cacheprovider", "-c", "/dev/null", f"--rootdir={workroot}", "--noconftest"]
    if collect:
        argv.append("--collect-only")
    return [*argv, "-q", target]


def _status(argv: list[str], workroot: str, child_timeout: int) -> tuple[int, str]:
    # MC-1 ANCHOR, deliberately ONE line. Replacing it with a shell pipeline
    # makes the reported status that of the last stage -- the `cmd | tee` /
    # `|| true` defect. The kwargs sit beside it so that reformatting this
    # subject cannot split the anchor and leave substitute() matching nothing.
    kw = dict(capture_output=True, text=True, env=_env(), cwd=workroot, timeout=child_timeout)
    proc = subprocess.run(argv, **kw)
    return proc.returncode, proc.stdout


def _node_ids(stdout: str) -> list[str]:
    # Structural, partition-based; not a transcription of the oracle's regex.
    # A node id is <path>::<rest>, where <path> is whitespace-free and ends in
    # .py. <rest> MAY contain spaces: `test_p[with space]` is a valid parameter
    # id and dropping it loses a real selected node while the count still looks
    # healthy. Rejects the `N tests collected` summary and plugin chatter (no
    # `.py::` before any space) and rootdir-stripped `::name` (empty path).
    ids = []
    for line in stdout.splitlines():
        head, sep, _ = line.partition("::")
        if sep and head.endswith(".py") and head and " " not in head:
            ids.append(line)
    return sorted(ids)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render(envelope: dict) -> str:
    # Serialized by its own route -- no encoder is shared with the oracle (flat
    # key=value) or with the harness, because two sides that share a serializer
    # are one side wearing two hats.
    return json.dumps(envelope, sort_keys=True, indent=2) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--workroot", required=True)
    ap.add_argument("--nonce", required=True)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--child-timeout", type=int, default=120)
    ap.add_argument("--pycache-prefix", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--case-manifest", required=True)
    args = ap.parse_args()
    bound, pfx = args.child_timeout, args.pycache_prefix

    try:
        cargv = _argv(args.python, args.workroot, args.target, True, pfx)
        rargv = _argv(args.python, args.workroot, args.target, False, pfx)
        collect_exit, collect_out = _status(cargv, args.workroot, bound)
        run_exit, _ = _status(rargv, args.workroot, bound)
        probe = [args.python, "-B", "-X", f"pycache_prefix={pfx}", "-I", "-c", VERSION_PROBE]
        version = subprocess.run(
            probe, capture_output=True, text=True, env=_env(), timeout=bound
        ).stdout.strip()
    except subprocess.TimeoutExpired as exc:
        # No record on stdout: a bounded-out measurement must be unusable
        # downstream (CANDIDATE_EMPTY), never a partial record read as agreement.
        # The token names the outcome, so a caller can tell a bounded-out run
        # from a startup crash, which is also a non-zero exit.
        sys.stderr.write(f"F0_CHILD_TIMEOUT bound={bound}s cmd={exc.cmd!r}\n")
        return 3

    selected = _node_ids(collect_out)
    # MC-3 ANCHOR. Replacing this with a $TMPDIR glob for the oracle's record
    # makes the candidate a mirror rather than an independent measurement.
    digest = _digest(Path(args.target))

    observation = {
        "stage": "executing",
        "python": args.python,
        "python_version": version,
        "target": args.target,
        "subject_digest": digest,
        "collect_exit": collect_exit,
        "run_exit": run_exit,
        "selected_count": len(selected),
        "selected": selected,
        "nonce": args.nonce,
        # Representative R0 observation metadata. It must travel unchanged
        # through the comparator: rejecting it would freeze bytes R0 cannot use.
        "command": " ".join(rargv),
        "cwd": args.workroot,
        "timeout_s": bound,
        "stdout_digest": hashlib.sha256(collect_out.encode()).hexdigest(),
        "truncated": False,
        "carrier_id": f"f0-candidate-{args.nonce}",
    }
    envelope = {
        "schema": RECEIPT_SCHEMA,
        "case": args.case,
        "observation": observation,
        # SYNTHETIC fixture data. This candidate is explicitly a test fixture, so
        # it may carry a decision; the POSIX oracle and trustcheck.py may not.
        "decision": "PASS" if run_exit == 0 else "FAIL",
        "tool_version": TOOL_VERSION,
        "dependency_digests": {
            "case_manifest": _digest(Path(args.case_manifest)),
            "verifier": _digest(Path(__file__).resolve()),
        },
    }
    # MC-2 ANCHOR. Replacing this with a hardcoded prior receipt is the "report
    # last known good" defect.
    record = _render(envelope)
    sys.stdout.write(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Capture a pre-refactor timing baseline (Issue #1012, W0).

Runs each active hook under `plugins/autonomous-dev/hooks/*.py` ~5 times
with synthetic stdin payloads and a redirected `HOOK_TIMING_DIR`. The
resulting JSONL rows are written to a single baseline file:

    baselines/<YYYY-MM>-<label>.jsonl

This file is committed to the repo as the "before" snapshot the W0
baseline publisher (#1022) compares against. It also gates the
`tests/integration/test_baseline_artifact_present.py` regression test.

Usage:

    python scripts/capture_baseline.py
    python scripts/capture_baseline.py --output baselines/2026-05-pre-refactor.jsonl
    python scripts/capture_baseline.py --runs 5
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
DEFAULT_OUTPUT = REPO_ROOT / "baselines" / "2026-05-pre-refactor.jsonl"

# Per-hook stdin payloads. Hooks that don't read stdin still accept it.
PRETOOL_PAYLOAD = {
    "tool_name": "Read",
    "tool_input": {"file_path": "/tmp/x"},
}
PROMPT_PAYLOAD = {"prompt": "hello"}
EMPTY_PAYLOAD: dict = {}

# Best-guess per-hook stdin assignment. Most hooks tolerate any JSON,
# but matching the registered event reduces "schema mismatch" noise.
STDIN_PAYLOADS: dict[str, dict] = {
    "unified_pre_tool.py": PRETOOL_PAYLOAD,
    "unified_prompt_validator.py": PROMPT_PAYLOAD,
    "plan_gate.py": PROMPT_PAYLOAD,
    "plan_mode_exit_detector.py": PROMPT_PAYLOAD,
    "genai_prompts.py": PROMPT_PAYLOAD,
    "validate_command_file_ops.py": PRETOOL_PAYLOAD,
    "security_scan.py": PRETOOL_PAYLOAD,
    "auto_format.py": {"tool_name": "Write", "tool_input": {"file_path": "/tmp/x.py"}},
    "auto_test.py": {"tool_name": "Write", "tool_input": {"file_path": "/tmp/x.py"}},
    "auto_fix_docs.py": {"tool_name": "Write", "tool_input": {"file_path": "/tmp/x.md"}},
    "enforce_orchestrator.py": PRETOOL_PAYLOAD,
    "enforce_prunable_threshold.py": PRETOOL_PAYLOAD,
    "enforce_regression_test.py": PRETOOL_PAYLOAD,
    "enforce_tdd.py": PRETOOL_PAYLOAD,
    "validate_claude_md_size.py": PRETOOL_PAYLOAD,
    "validate_project_alignment.py": PRETOOL_PAYLOAD,
    "validate_session_quality.py": EMPTY_PAYLOAD,
    "stop_quality_gate.py": EMPTY_PAYLOAD,
    "task_completed_handler.py": EMPTY_PAYLOAD,
    "session_activity_logger.py": EMPTY_PAYLOAD,
    "unified_session_tracker.py": EMPTY_PAYLOAD,
    "conversation_archiver.py": EMPTY_PAYLOAD,
    "setup.py": EMPTY_PAYLOAD,
    "genai_utils.py": EMPTY_PAYLOAD,
}


def _hook_payload(name: str) -> dict:
    return STDIN_PAYLOADS.get(name, EMPTY_PAYLOAD)


def run_hook_once(
    hook_path: Path,
    *,
    timing_dir: Path,
    timeout: float = 10.0,
) -> tuple[bool, str]:
    """Invoke a hook with a synthetic stdin. Returns (success, stderr)."""
    payload = _hook_payload(hook_path.name)
    env = os.environ.copy()
    env["HOOK_TIMING_DIR"] = str(timing_dir)
    # Ensure no leftover disable from caller env.
    env.pop("HOOK_TIMING_DISABLED", None)
    try:
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
            cwd=str(REPO_ROOT),
        )
        return (True, result.stderr)
    except subprocess.TimeoutExpired:
        return (False, "timeout")
    except Exception as exc:  # last-resort
        return (False, f"{type(exc).__name__}: {exc}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture pre-refactor hook timing baseline (Issue #1012)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSONL path (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)}).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Invocations per hook (default: 5; ≥5 gives ≥120 rows for 24 hooks).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-hook status.",
    )
    args = parser.parse_args(argv)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    hooks = sorted(p for p in HOOKS_DIR.glob("*.py") if p.name != "__init__.py")
    if not hooks:
        print(f"error: no hooks found under {HOOKS_DIR}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        success_count = 0
        failure_count = 0
        for hook in hooks:
            for i in range(args.runs):
                ok, err = run_hook_once(hook, timing_dir=td)
                if ok:
                    success_count += 1
                else:
                    failure_count += 1
                    if args.verbose:
                        print(f"  FAIL {hook.name} run={i}: {err.strip()[:200]}")
            if args.verbose:
                print(f"  done: {hook.name}")

        # Aggregate the daily rotated files into the single baseline output.
        produced = sorted(td.glob("hook_timings_*.jsonl"))
        if not produced:
            print("error: no timing files produced (hook_timing.py missing?)", file=sys.stderr)
            return 1

        rows = 0
        with args.output.open("w", encoding="utf-8") as out:
            for f in produced:
                with f.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            json.loads(line)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        out.write(line + "\n")
                        rows += 1

        print(
            f"captured {rows} rows from {len(hooks)} hooks "
            f"({success_count} succeeded, {failure_count} failed) "
            f"→ {args.output.relative_to(REPO_ROOT)}"
        )
        if rows < 100:
            print(
                f"warning: row count {rows} < 100; "
                "consider --runs >= 5 or check that hook_timing.py is importable",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

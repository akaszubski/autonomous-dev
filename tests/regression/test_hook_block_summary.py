"""Regression tests for ``scripts/hook_block_summary.py`` (Issue #972).

Covers:
- Empty log file → exit 0 with friendly message.
- Corrupt JSONL line → counted as parse error, not crash.
- Time-window filter (``--last``) excludes older rows.
- Dual-read dedup: row present in both new and legacy log files counted once.
- JSON output mode is parseable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "hook_block_summary.py"


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    (tmp_path / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _run(args, *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _row(*, ts: str, hook: str, reason: str, **extra) -> str:
    base = {
        "ts": ts,
        "hook_name": hook,
        "reason": reason,
        "decision_shape": "tuple",
        "metadata": {},
        "session_id": "sess",
        "cwd": "/tmp",
    }
    base.update(extra)
    return json.dumps(base)


class TestEmptyLog:
    def test_no_log_files_exit_zero(self, project_dir):
        result = _run([], cwd=project_dir)
        assert result.returncode == 0, result.stderr
        assert "No block events found" in result.stdout

    def test_empty_log_file_exit_zero(self, project_dir):
        log = project_dir / ".claude" / "logs" / "hook-blocks.jsonl"
        log.write_text("")
        result = _run([], cwd=project_dir)
        assert result.returncode == 0
        assert "No block events found" in result.stdout

    def test_json_mode_empty(self, project_dir):
        result = _run(["--json"], cwd=project_dir)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["total_events"] == 0


class TestCorruptJsonl:
    def test_corrupt_lines_dont_crash(self, project_dir):
        log = project_dir / ".claude" / "logs" / "hook-blocks.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        lines = [
            _row(ts=ts, hook="h.py", reason="r"),
            "{not valid json",
            "completely bogus line",
            _row(ts=ts, hook="h.py", reason="r2"),
        ]
        log.write_text("\n".join(lines) + "\n")
        result = _run([], cwd=project_dir)
        assert result.returncode == 0
        assert "2 event" in result.stdout
        assert "2 unparseable line" in result.stdout

    def test_non_dict_json_line_treated_as_parse_error(self, project_dir):
        log = project_dir / ".claude" / "logs" / "hook-blocks.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        log.write_text(
            "[1, 2, 3]\n" + _row(ts=ts, hook="h.py", reason="r") + "\n"
        )
        result = _run([], cwd=project_dir)
        assert result.returncode == 0
        assert "1 event" in result.stdout


class TestTimeWindow:
    def test_last_7d_excludes_older_rows(self, project_dir):
        log = project_dir / ".claude" / "logs" / "hook-blocks.jsonl"
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=10)
        ).isoformat()
        recent_ts = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
        log.write_text(
            "\n".join(
                [
                    _row(ts=old_ts, hook="old.py", reason="old"),
                    _row(ts=recent_ts, hook="new.py", reason="new"),
                ]
            )
            + "\n"
        )
        result = _run(["--last", "7d", "--json"], cwd=project_dir)
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["total_events"] == 1
        # only "new.py" survives the window.
        hooks = dict(payload["top_hooks"])
        assert "new.py" in hooks
        assert "old.py" not in hooks

    def test_invalid_last_value_returns_2(self, project_dir):
        result = _run(["--last", "garbage"], cwd=project_dir)
        assert result.returncode == 2

    def test_since_and_last_mutually_exclusive(self, project_dir):
        result = _run(
            ["--last", "7d", "--since", "2026-01-01"], cwd=project_dir
        )
        assert result.returncode == 2


class TestDualReadDedup:
    def test_row_in_both_files_counted_once(self, project_dir):
        ts = datetime.now(timezone.utc).isoformat()
        new_log = project_dir / ".claude" / "logs" / "hook-blocks.jsonl"
        legacy_log = project_dir / ".claude" / "logs" / "hook-recovery.jsonl"

        new_log.write_text(
            _row(ts=ts, hook="dup.py", reason="same reason") + "\n"
        )
        # Legacy schema uses "timestamp" + "block_reason".
        legacy_log.write_text(
            json.dumps(
                {
                    "timestamp": ts,
                    "hook_name": "dup.py",
                    "block_reason": "same reason",
                    "tool_name": "Bash",
                }
            )
            + "\n"
        )
        result = _run(["--json"], cwd=project_dir)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        # Should be deduplicated.
        assert payload["total_events"] == 1

    def test_legacy_only_rows_counted(self, project_dir):
        """Pre-existing hook-recovery.jsonl rows must still be visible."""
        ts = datetime.now(timezone.utc).isoformat()
        legacy_log = project_dir / ".claude" / "logs" / "hook-recovery.jsonl"
        legacy_log.write_text(
            json.dumps(
                {
                    "timestamp": ts,
                    "hook_name": "legacy.py",
                    "block_reason": "from #970",
                }
            )
            + "\n"
        )
        result = _run(["--json"], cwd=project_dir)
        payload = json.loads(result.stdout)
        assert payload["total_events"] == 1
        assert dict(payload["top_hooks"]).get("legacy.py") == 1


class TestCategorisation:
    def test_plan_exit_bucket_recognised(self, project_dir):
        log = project_dir / ".claude" / "logs" / "hook-blocks.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        log.write_text(
            _row(
                ts=ts,
                hook="plan_mode_exit_detector.py",
                reason="ExitPlanMode requires critique",
            )
            + "\n"
        )
        result = _run(["--json"], cwd=project_dir)
        payload = json.loads(result.stdout)
        assert payload["by_category"].get("plan-exit") == 1

    def test_pipeline_state_bucket_recognised(self, project_dir):
        log = project_dir / ".claude" / "logs" / "hook-blocks.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        log.write_text(
            _row(
                ts=ts,
                hook="unified_pre_tool.py",
                reason="WORKFLOW ENFORCEMENT: pipeline state required",
            )
            + "\n"
        )
        result = _run(["--json"], cwd=project_dir)
        payload = json.loads(result.stdout)
        assert payload["by_category"].get("pipeline-state") == 1

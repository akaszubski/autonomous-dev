"""Regression tests for Issue #1601 — three enforcement gaps.

Background
----------
Issue #1601, filed by the continuous-improvement-analyst during a `/implement`
run in the spektiv consumer repo, identified five framework defects. This
regression test locks the fixes for three of them:

1. **Committed `.bypass` staleness** — a committed `.claude/.bypass` older than
   30 days now emits a loud SessionStart WARNING (was: never warned as long as
   the file was git-tracked, letting an accidental "test" commit disable ALL
   hooks for 2+ months).

2. **`session_activity_logger` PreToolUse matcher extended to include `Bash`** —
   the previous `Task|Agent`-only matcher meant Bash denials were structurally
   invisible to the activity log, making CIA's deny-then-workaround detection
   (Check #8) unable to see the events it was supposed to detect.

3. **`_TEST_FUNCTION_PATTERN` matches `async def test_`** — the previous
   sync-only regex under-counted by ~60% in async-heavy test suites, silently
   weakening the regression-test HARD GATE that consumes `get_test_count()`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
TEMPLATES_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "templates"

sys.path.insert(0, str(LIB_DIR))


# --- Defect 3: async test counting ---------------------------------------------

class TestAsyncTestCounting:
    """Locks the ``async def test_`` regex fix in bugfix_detector."""

    def test_pattern_matches_async_def(self):
        from bugfix_detector import _TEST_FUNCTION_PATTERN

        source = "async def test_it():\n    pass\n"
        assert _TEST_FUNCTION_PATTERN.search(source) is not None, (
            "async def test_ must match — else HARD GATE under-counts "
            "async-heavy test suites (Issue #1601 defect 3)"
        )

    def test_pattern_still_matches_sync_def(self):
        from bugfix_detector import _TEST_FUNCTION_PATTERN

        source = "def test_it():\n    pass\n"
        assert _TEST_FUNCTION_PATTERN.search(source) is not None

    def test_get_test_count_counts_async(self, tmp_path: Path):
        from bugfix_detector import get_test_count

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_async.py").write_text(
            "async def test_a():\n    pass\n\n"
            "async def test_b():\n    pass\n\n"
            "def test_sync():\n    pass\n"
        )
        assert get_test_count(tmp_path) == 3, (
            "Mixed async+sync test files must be counted correctly"
        )

    def test_get_test_count_counts_indented_async(self, tmp_path: Path):
        """Class-method async tests must count (matches the ``^\\s*`` prefix)."""
        from bugfix_detector import get_test_count

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_class.py").write_text(
            "class TestFoo:\n"
            "    async def test_one(self):\n        pass\n"
            "    async def test_two(self):\n        pass\n"
        )
        assert get_test_count(tmp_path) == 2


# --- Defect 2: PreToolUse activity-logger matcher includes Bash ----------------

class TestActivityLoggerBashMatcher:
    """Locks the settings-template matcher fix for session_activity_logger."""

    @pytest.mark.parametrize(
        "template_name",
        [
            "settings.default.json",
            "settings.strict-mode.json",
            "settings.permission-batching.json",
            "settings.granular-bash.json",
            "settings.autonomous-dev.json",
        ],
    )
    def test_activity_logger_matcher_includes_bash(self, template_name: str):
        path = TEMPLATES_DIR / template_name
        assert path.exists(), f"template missing: {path}"

        data = json.loads(path.read_text())
        pre_hooks = data.get("hooks", {}).get("PreToolUse", [])

        # Find the block whose command references session_activity_logger.py
        # AND is configured for activity logging (ACTIVITY_LOGGING=true).
        activity_block = None
        for block in pre_hooks:
            for hook in block.get("hooks", []):
                cmd = hook.get("command", "")
                if (
                    "session_activity_logger.py" in cmd
                    and "ACTIVITY_LOGGING=true" in cmd
                ):
                    activity_block = block
                    break
            if activity_block is not None:
                break

        assert activity_block is not None, (
            f"{template_name}: no session_activity_logger PreToolUse hook found"
        )

        matcher = activity_block.get("matcher", "")
        matcher_tokens = {t.strip() for t in matcher.split("|") if t.strip()}
        assert "Bash" in matcher_tokens, (
            f"{template_name}: session_activity_logger matcher {matcher!r} "
            "must include 'Bash' — otherwise Bash denials cannot be detected "
            "by CIA Check #8 (Issue #1601 defect 2)"
        )
        # Preserve the original Task/Agent coverage.
        assert "Task" in matcher_tokens and "Agent" in matcher_tokens, (
            f"{template_name}: matcher must retain Task and Agent tokens"
        )


# --- Defect 1: committed .bypass staleness warning -----------------------------

class TestCommittedBypassStaleness:
    """Locks the committed-.bypass staleness warning fix."""

    def _init_git_repo(self, tmp_path: Path) -> None:
        subprocess.run(
            ["git", "init", "-q"], cwd=str(tmp_path), check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "t@t"], cwd=str(tmp_path), check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "t"], cwd=str(tmp_path), check=True
        )
        subprocess.run(
            ["git", "config", "commit.gpgsign", "false"], cwd=str(tmp_path), check=True
        )

    def test_committed_bypass_young_returns_none(self, tmp_path: Path, monkeypatch):
        """A recently committed .bypass file should NOT warn."""
        import hook_bypass

        monkeypatch.delenv(hook_bypass.ENV_VAR_NAME, raising=False)
        self._init_git_repo(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        bypass = claude_dir / ".bypass"
        bypass.touch()
        subprocess.run(
            ["git", "add", "-f", str(bypass)], cwd=str(tmp_path), check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "add bypass", "-q"],
            cwd=str(tmp_path), check=True
        )

        result = hook_bypass.check_bypass_staleness(start_dir=tmp_path)
        assert result is None, (
            f"young committed bypass should NOT warn, got: {result!r}"
        )

    def test_committed_bypass_stale_warns(self, tmp_path: Path, monkeypatch):
        """A committed .bypass file past 30 days MUST warn (Issue #1601)."""
        import hook_bypass

        monkeypatch.delenv(hook_bypass.ENV_VAR_NAME, raising=False)
        self._init_git_repo(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        bypass = claude_dir / ".bypass"
        bypass.touch()
        subprocess.run(
            ["git", "add", "-f", str(bypass)], cwd=str(tmp_path), check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "test", "-q"],
            cwd=str(tmp_path), check=True
        )

        # Age the file to 45 days.
        old_mtime = time.time() - 45 * 86400
        import os as _os
        _os.utime(str(bypass), (old_mtime, old_mtime))

        result = hook_bypass.check_bypass_staleness(start_dir=tmp_path)
        assert result is not None, (
            "committed bypass file older than 30 days MUST emit a WARNING "
            "(Issue #1601 defect 1) — otherwise an accidental commit can "
            "silently disable ALL hook enforcement forever"
        )
        assert "WARNING" in result
        assert "Committed" in result
        assert "days old" in result

    def test_committed_stale_threshold_override(self, tmp_path: Path, monkeypatch):
        """The committed staleness threshold is env-var configurable."""
        import hook_bypass

        monkeypatch.delenv(hook_bypass.ENV_VAR_NAME, raising=False)
        # Set threshold to 1 day so a 2-day-old committed file warns.
        monkeypatch.setenv(
            hook_bypass.COMMITTED_STALE_DAYS_ENV_VAR, "1"
        )

        self._init_git_repo(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        bypass = claude_dir / ".bypass"
        bypass.touch()
        subprocess.run(
            ["git", "add", "-f", str(bypass)], cwd=str(tmp_path), check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "add", "-q"],
            cwd=str(tmp_path), check=True
        )

        old_mtime = time.time() - 2 * 86400
        import os as _os
        _os.utime(str(bypass), (old_mtime, old_mtime))

        result = hook_bypass.check_bypass_staleness(start_dir=tmp_path)
        assert result is not None
        assert "threshold 1d" in result

    def test_uncommitted_stale_still_warns(self, tmp_path: Path, monkeypatch):
        """Backward compat: the original Issue #1434 uncommitted path still works."""
        import hook_bypass

        monkeypatch.delenv(hook_bypass.ENV_VAR_NAME, raising=False)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        bypass = claude_dir / ".bypass"
        bypass.touch()
        # Age to 48h (past 24h default) — no git init so file is untracked.
        old_mtime = time.time() - 48 * 3600
        import os as _os
        _os.utime(str(bypass), (old_mtime, old_mtime))

        result = hook_bypass.check_bypass_staleness(start_dir=tmp_path)
        assert result is not None
        assert "Uncommitted" in result

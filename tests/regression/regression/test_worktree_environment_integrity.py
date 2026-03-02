"""Regression tests for worktree environment integrity.

REGRESSION CONTEXT: Worktrees created by /implement --batch get a snapshot
of .claude/ at creation time. If the parent repo's settings change after
worktree creation, the worktree has stale config — causing permission prompts
mid-pipeline that block automation.

These tests validate that:
1. The batch command template includes settings sync after worktree creation
2. Critical config files are enumerated for sync (no silent gaps)
3. Settings sync uses the correct parent repo resolution
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BATCH_CMD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"


class TestWorktreeSettingsSync:
    """Worktree creation must sync settings from parent repo."""

    @pytest.fixture(autouse=True)
    def load_batch_command(self):
        self.content = BATCH_CMD.read_text()

    def test_batch_command_syncs_settings_after_worktree_creation(self):
        """STEP B1 must copy settings.json from parent repo to worktree.

        Without this, worktrees get stale permissions and tools prompt
        for confirmation mid-pipeline.
        """
        # The sync must happen AFTER worktree creation and cd
        step_b1 = self.content.split("**STEP B2")[0]
        assert "settings.json" in step_b1, (
            "STEP B1 must sync settings.json from parent repo to worktree.\n"
            "Without this, worktrees get stale permissions."
        )

    def test_settings_sync_uses_git_common_dir(self):
        """Settings sync must resolve parent repo via git, not hardcoded paths.

        git rev-parse --git-common-dir gives the shared .git dir,
        which we can use to find the parent repo root.
        """
        assert "git-common-dir" in self.content or "PARENT_REPO" in self.content, (
            "Settings sync must resolve parent repo path dynamically, "
            "not assume relative paths (worktrees can be nested)"
        )

    def test_settings_sync_is_fault_tolerant(self):
        """Settings sync must not fail the pipeline if settings.json is missing."""
        # Look for || true or 2>/dev/null or similar error suppression
        step_b1 = self.content.split("**STEP B2")[0]
        settings_lines = [
            line for line in step_b1.split("\n")
            if "settings.json" in line and ("cp " in line or "copy" in line.lower())
        ]
        assert settings_lines, "No settings copy command found in STEP B1"
        for line in settings_lines:
            assert "|| true" in line or "2>/dev/null" in line or "if " in line, (
                f"Settings sync must be fault-tolerant (missing file shouldn't crash pipeline):\n"
                f"  {line}"
            )


class TestWorktreeCriticalFiles:
    """All critical config files must be considered for worktree sync."""

    CRITICAL_FILES = [
        "settings.json",  # Permissions, tool approvals
    ]

    def test_critical_files_synced_in_batch_command(self):
        """Each critical config file should be synced or explicitly documented as inherited."""
        content = BATCH_CMD.read_text()
        step_b1 = content.split("**STEP B2")[0]

        missing = []
        for f in self.CRITICAL_FILES:
            if f not in step_b1:
                missing.append(f)

        assert not missing, (
            f"Critical files not synced in worktree STEP B1: {missing}\n"
            "These files can diverge between parent repo and worktree, "
            "causing permission/config issues mid-pipeline."
        )

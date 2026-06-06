"""
Unit tests for the Write/Edit pipeline gate (Issue #1142 + Phase 1 polarity flip).

Tests `_check_write_pipeline_required()` directly as a pure function.

Phase 1 (Issue #1142+) flipped the polarity from opt-IN via `.claude/.enforce`
to default-ON subject to the existing `.claude/.bypass` universal opt-out.
The line-count "significant additions" heuristic was replaced by
`classify_edit_tier()` which returns `fix` / `light` / `full` tiers.

This file covers the post-flip ACs (excluding deleted AC1 and AC9 which
specifically tested the marker mechanism that no longer exists).

Issue: #1142
"""

import sys
from pathlib import Path

import pytest

# Add hook + lib dirs to sys.path
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline_active(monkeypatch) -> None:
    """Patch _is_pipeline_active so it returns True."""
    monkeypatch.setattr(hook, "_is_pipeline_active", lambda: True)


def _make_pipeline_inactive(monkeypatch) -> None:
    """Patch _is_pipeline_active so it returns False."""
    monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def default_state(monkeypatch, tmp_path):
    """Default state for each test:
    - pipeline NOT active
    - no /tmp/skip_write_pipeline_gate file
    """
    _make_pipeline_inactive(monkeypatch)
    skip_file = Path("/tmp/skip_write_pipeline_gate")
    if skip_file.exists():
        skip_file.unlink()


# ---------------------------------------------------------------------------
# AC2 — Pipeline active: gate is a no-op
# ---------------------------------------------------------------------------


class TestPipelineActive:
    """Gate must allow all edits while /implement pipeline is running."""

    def test_pipeline_active_allows_substantive_edit(self, monkeypatch):
        """When pipeline is active, even a large edit is allowed."""
        _make_pipeline_active(monkeypatch)
        big_new = "\n".join(f"def func_{i}(): pass" for i in range(20))
        block, tier, directive = hook._check_write_pipeline_required(
            "Write",
            "/home/user/app/models.py",
            "",
            big_new,
        )
        assert block is False
        assert tier == "pipeline_active"


# ---------------------------------------------------------------------------
# AC3 — One-shot operator bypass
# ---------------------------------------------------------------------------


class TestOperatorBypass:
    """Touch /tmp/skip_write_pipeline_gate: next call skips the gate, file is deleted."""

    def test_skip_file_bypasses_gate_and_is_deleted(self, monkeypatch):
        """Skip file is consumed once and auto-deleted."""
        skip_file = Path("/tmp/skip_write_pipeline_gate")
        skip_file.touch()
        assert skip_file.exists(), "pre-condition: skip file must exist"

        big_new = "\n".join(f"def func_{i}(): pass" for i in range(20))
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/service.py",
            "",
            big_new,
        )
        assert block is False
        assert tier == "operator_bypass"
        assert not skip_file.exists(), "skip file must be auto-deleted after consumption"

    def test_skip_file_only_consumed_once(self, monkeypatch):
        """After the skip file is consumed, the NEXT call is NOT bypassed."""
        skip_file = Path("/tmp/skip_write_pipeline_gate")
        skip_file.touch()

        # First call: bypass
        big_new = "\n".join(f"def func_{i}(): pass" for i in range(20))
        block1, tier1, _ = hook._check_write_pipeline_required(
            "Edit", "/home/user/app/service.py", "", big_new
        )
        assert block1 is False
        assert tier1 == "operator_bypass"

        # Second call (same big edit): no skip file → should block
        block2, tier2, _ = hook._check_write_pipeline_required(
            "Edit", "/home/user/app/service.py", "", big_new
        )
        assert block2 is True
        # Tier is now one of fix / light / full (Phase 1 tier names).
        assert tier2 in ("fix", "light", "full")


# ---------------------------------------------------------------------------
# AC4 — Non-code extensions: tier0_non_code
# ---------------------------------------------------------------------------


class TestNonCodeExtensions:
    """Markdown, JSON, YAML, images, etc. must pass through without blocking."""

    @pytest.mark.parametrize("file_path", [
        "/home/user/project/README.md",
        "/home/user/project/config.json",
        "/home/user/project/settings.yaml",
        "/home/user/project/data.txt",
        "/home/user/project/image.png",
    ])
    def test_non_code_extension_not_blocked(self, file_path):
        big_new = "x" * 200
        block, tier, _ = hook._check_write_pipeline_required(
            "Write", file_path, "", big_new
        )
        assert block is False
        assert tier == "tier0_non_code"


# ---------------------------------------------------------------------------
# AC5 — Test files: tier0_test_file
# ---------------------------------------------------------------------------


class TestTestFileExclusions:
    """Test files inside tests/ or named test_*.py / *_test.py are excluded."""

    @pytest.mark.parametrize("file_path", [
        "/home/user/project/tests/test_models.py",
        "/home/user/project/test/unit_test.py",
        "/home/user/project/src/test_service.py",
        "/home/user/project/src/service_test.py",
    ])
    def test_test_file_not_blocked(self, file_path):
        big_new = "\n".join(f"def test_func_{i}(): pass" for i in range(20))
        block, tier, _ = hook._check_write_pipeline_required(
            "Edit", file_path, "", big_new
        )
        assert block is False
        assert tier == "tier0_test_file"


# ---------------------------------------------------------------------------
# AC6 — Tier "fix": tiny edit, no AST signal
# ---------------------------------------------------------------------------


class TestFixTier:
    """Small edits with no new functions/classes classify as `fix`."""

    def test_one_line_const_change_is_fix(self):
        old = "TIMEOUT = 30\n"
        new = "TIMEOUT = 60\n"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/settings.py",
            old,
            new,
        )
        assert block is True
        assert tier == "fix"
        assert "/implement --fix" in directive

    def test_few_line_addition_no_function_is_fix(self):
        old = "x = 1\n"
        new = "x = 1\na = 2\nb = 3\nc = 4\nd = 5\n"
        block, tier, _ = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/config.py",
            old,
            new,
        )
        assert block is True
        assert tier == "fix"


# ---------------------------------------------------------------------------
# AC7 — Tier "light": new function OR control-flow OR 20-99 lines
# ---------------------------------------------------------------------------


class TestLightTier:
    def test_new_function_is_light(self):
        old = "x = 1\n"
        new = "x = 1\n\ndef new_handler():\n    return 1\n"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/handlers.py",
            old,
            new,
        )
        assert block is True
        assert tier == "light"
        assert "/implement --light" in directive

    def test_twenty_line_addition_is_light(self):
        old = ""
        new = "\n".join(f"x_{i} = {i}" for i in range(25))
        block, tier, _ = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/models.py",
            old,
            new,
        )
        assert block is True
        assert tier == "light"


# ---------------------------------------------------------------------------
# AC8 — Tier "full": new class OR >=100 lines
# ---------------------------------------------------------------------------


class TestFullTier:
    def test_new_class_is_full(self):
        old = "x = 1\n"
        new = "x = 1\n\nclass Brand:\n    pass\n"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/handlers.py",
            old,
            new,
        )
        assert block is True
        assert tier == "full"
        assert "/implement" in directive
        # `full` directive must be bare /implement, not --fix or --light.
        assert "--fix" not in directive
        assert "--light" not in directive

    def test_hundred_plus_line_addition_is_full(self):
        old = ""
        new = "\n".join(f"x_{i} = {i}" for i in range(120))
        block, tier, _ = hook._check_write_pipeline_required(
            "Write",
            "/home/user/app/utils.py",
            old,
            new,
        )
        assert block is True
        assert tier == "full"


# ---------------------------------------------------------------------------
# AC — directive mentions file name
# ---------------------------------------------------------------------------


class TestDirectiveMentionsFile:
    def test_directive_mentions_file_name(self):
        old = ""
        new = "\n".join(f"line_{i} = {i}" for i in range(30))
        block, tier, directive = hook._check_write_pipeline_required(
            "Write",
            "/home/user/app/utils.py",
            old,
            new,
        )
        assert block is True
        assert "utils.py" in directive


# ---------------------------------------------------------------------------
# AC8 — No path: gate passes through
# ---------------------------------------------------------------------------


class TestNoPath:
    """When file_path is empty/None, gate returns (False, 'no_path', '')."""

    def test_empty_path_is_no_path(self):
        block, tier, _ = hook._check_write_pipeline_required(
            "Edit", "", "old", "new " * 20
        )
        assert block is False
        assert tier == "no_path"

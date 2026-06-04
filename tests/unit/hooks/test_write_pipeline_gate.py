"""
Unit tests for the Write/Edit pipeline gate added in Issue #1142.

Tests _check_write_pipeline_required() directly as a pure function
and validates that the correct tier/block values are returned for each
path through the decision tree.

Issue: #1142
Date: 2026-06-05
Agent: implementer
"""

import sys
from pathlib import Path
from unittest.mock import patch

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

def _make_enforce_active(monkeypatch) -> None:
    """Patch _enforce_marker_fn so _check_enforce_marker() returns True."""
    monkeypatch.setattr(hook, "_enforce_marker_fn", lambda: True)


def _make_enforce_inactive(monkeypatch) -> None:
    """Patch _enforce_marker_fn so _check_enforce_marker() returns False."""
    monkeypatch.setattr(hook, "_enforce_marker_fn", lambda: False)


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
    """
    Default state for each test:
    - .enforce marker active (consumer repo opted in)
    - pipeline NOT active
    - no /tmp/skip_write_pipeline_gate file
    """
    _make_enforce_active(monkeypatch)
    _make_pipeline_inactive(monkeypatch)
    # Ensure the skip file is absent before each test
    skip_file = Path("/tmp/skip_write_pipeline_gate")
    if skip_file.exists():
        skip_file.unlink()


# ---------------------------------------------------------------------------
# AC1 — No .enforce marker: gate does nothing
# ---------------------------------------------------------------------------

class TestNoEnforceMarker:
    """Gate must be a no-op when .claude/.enforce is absent."""

    def test_no_enforce_marker_allows_substantive_edit(self, monkeypatch):
        """When .enforce is absent, even a large edit is allowed (tier not applicable)."""
        _make_enforce_inactive(monkeypatch)
        big_new = "\n".join(f"def func_{i}(): pass" for i in range(20))
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/main.py",
            "",
            big_new,
        )
        assert block is False
        assert tier == "no_enforce_marker"
        assert directive == ""


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
        assert tier2 == "tier2_substantive"


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
# AC6 — Tier 1: trivial edit (< 5 lines, no significant patterns) — allowed
# ---------------------------------------------------------------------------

class TestTier1Trivial:
    """Small edits with no new functions/classes must be allowed (Tier 1)."""

    def test_four_line_addition_is_tier1(self):
        """4-line addition is below SIGNIFICANT_LINE_THRESHOLD of 5."""
        old = "x = 1\n"
        new = "x = 1\na = 2\nb = 3\nc = 4\nd = 5\n"  # 5 lines but diff is +4 from old
        # actual diff: new has 5 lines, old has 1 line → diff = 4 (< 5 threshold)
        block, tier, _ = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/config.py",
            old,
            new,
        )
        assert block is False
        assert tier == "tier1_trivial"

    def test_single_line_change_is_tier1(self):
        """Changing one line (no new functions) is Tier 1."""
        old = "TIMEOUT = 30\n"
        new = "TIMEOUT = 60\n"
        block, tier, _ = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/settings.py",
            old,
            new,
        )
        assert block is False
        assert tier == "tier1_trivial"


# ---------------------------------------------------------------------------
# AC7 — Tier 2: substantive edit — blocked
# ---------------------------------------------------------------------------

class TestTier2Substantive:
    """Large edits or new function/class definitions must be blocked (Tier 2)."""

    def test_five_line_addition_is_tier2(self):
        """5-line addition meets SIGNIFICANT_LINE_THRESHOLD → Tier 2 block."""
        old = ""
        new = "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n"  # 5 lines added
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/models.py",
            old,
            new,
        )
        assert block is True
        assert tier == "tier2_substantive"
        assert "/implement" in directive

    def test_new_function_definition_is_tier2(self):
        """A new def foo(): block triggers _has_significant_additions → Tier 2."""
        old = "x = 1\n"
        new = "x = 1\n\ndef new_handler():\n    pass\n"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit",
            "/home/user/app/handlers.py",
            old,
            new,
        )
        assert block is True
        assert tier == "tier2_substantive"
        assert "skip_write_pipeline_gate" in directive

    def test_tier2_directive_mentions_file_name(self):
        """The directive must mention the target file name."""
        old = ""
        new = "\n".join(f"line_{i} = {i}" for i in range(10))
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


# ---------------------------------------------------------------------------
# AC9 — Fail-closed when _enforce_marker_fn is None
# ---------------------------------------------------------------------------

class TestFailClosed:
    """When _enforce_marker_fn is None (import failure), _check_enforce_marker returns True."""

    def test_none_enforce_marker_fn_fails_closed(self, monkeypatch):
        """_check_enforce_marker() returns True when function is unavailable."""
        monkeypatch.setattr(hook, "_enforce_marker_fn", None)
        result = hook._check_enforce_marker()
        assert result is True

    def test_none_enforce_marker_fn_triggers_gate(self, monkeypatch):
        """When _enforce_marker_fn is None, a substantive edit IS blocked (fail-closed)."""
        monkeypatch.setattr(hook, "_enforce_marker_fn", None)
        _make_pipeline_inactive(monkeypatch)
        big_new = "\n".join(f"def func_{i}(): pass" for i in range(20))
        block, tier, _ = hook._check_write_pipeline_required(
            "Edit", "/home/user/app/service.py", "", big_new
        )
        assert block is True

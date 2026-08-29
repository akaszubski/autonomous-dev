"""Tests for ``scripts/audit_tool_intent_coverage.py`` (Issue #971 AC #5).

This is the CI gate that ensures every distinct tool name observed in the
activity logs has a defined classification in ``tool_intent.py`` (or the
``KNOWN_EXEC_TOOLS`` set in the audit script). It catches the case where
a new native tool is introduced without anyone updating the classifier.

Date: 2026-04-26
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_tool_intent_coverage.py"


def _load_audit_module():
    """Load the audit script as an importable module."""
    spec = importlib.util.spec_from_file_location(
        "audit_tool_intent_coverage", str(SCRIPT_PATH)
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def audit_mod():
    return _load_audit_module()


# ---------------------------------------------------------------------------
# Fixture log directories
# ---------------------------------------------------------------------------


@pytest.fixture
def covered_logs_dir(tmp_path):
    """Activity log dir with only covered tools."""
    log_dir = tmp_path / "activity"
    log_dir.mkdir()
    today = "2026-04-25.jsonl"
    entries = [
        {"tool": "Read"},
        {"tool": "Write"},
        {"tool": "Edit"},
        {"tool": "Bash"},
        {"tool": "Task"},
        {"tool": "mcp__github__create_issue"},
    ]
    (log_dir / today).write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n"
    )
    return log_dir


@pytest.fixture
def uncovered_logs_dir(tmp_path):
    """Activity log dir containing one unknown tool."""
    log_dir = tmp_path / "activity"
    log_dir.mkdir()
    today = "2026-04-25.jsonl"
    entries = [
        {"tool": "Read"},
        {"tool": "BogusTool"},  # unknown — must be flagged
        {"tool": "Bash"},
    ]
    (log_dir / today).write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n"
    )
    return log_dir


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestAuditAPI:
    """Tests against the importable ``audit()`` function."""

    def test_audit_finds_all_logged_tools(self, audit_mod, covered_logs_dir):
        """A log dir of exclusively-covered tools must report 0 uncovered."""
        exit_code, uncovered = audit_mod.audit(
            covered_logs_dir, days=365, strict=True
        )
        assert uncovered == [], (
            f"Audit reported uncovered tools when all should be covered: {uncovered}"
        )
        assert exit_code == 0

    def test_audit_flags_unknown_tool(self, audit_mod, uncovered_logs_dir):
        """A log dir with an unknown tool must report it as uncovered."""
        exit_code, uncovered = audit_mod.audit(
            uncovered_logs_dir, days=365, strict=False
        )
        assert "BogusTool" in uncovered

    def test_audit_strict_returns_nonzero_on_uncovered(
        self, audit_mod, uncovered_logs_dir
    ):
        """Strict mode must return exit code 1 when uncovered tools exist."""
        exit_code, uncovered = audit_mod.audit(
            uncovered_logs_dir, days=365, strict=True
        )
        assert exit_code == 1
        assert "BogusTool" in uncovered

    def test_audit_lookback_window_excludes_old_logs(self, audit_mod, tmp_path):
        """Logs older than --days must be excluded."""
        log_dir = tmp_path / "activity"
        log_dir.mkdir()
        # Old log with an unknown tool — should be excluded by short lookback.
        (log_dir / "2020-01-01.jsonl").write_text(
            json.dumps({"tool": "AncientUnknownTool"}) + "\n"
        )
        exit_code, uncovered = audit_mod.audit(
            log_dir, days=7, strict=True
        )
        assert "AncientUnknownTool" not in uncovered

    def test_audit_handles_missing_log_dir(self, audit_mod, tmp_path):
        """A missing log dir is not an error — returns 0 uncovered."""
        missing = tmp_path / "does_not_exist"
        exit_code, uncovered = audit_mod.audit(missing, days=30, strict=True)
        # Empty log dir = no uncovered tools observed.
        assert uncovered == []

    def test_audit_handles_malformed_jsonl(self, audit_mod, tmp_path):
        """Malformed JSON lines must be skipped, not crash."""
        log_dir = tmp_path / "activity"
        log_dir.mkdir()
        (log_dir / "2026-04-25.jsonl").write_text(
            "not json\n"
            + json.dumps({"tool": "Read"}) + "\n"
            + "{partial\n"
            + json.dumps({"tool": "Bash"}) + "\n"
        )
        exit_code, uncovered = audit_mod.audit(log_dir, days=365, strict=True)
        assert uncovered == []


class TestAuditCLI:
    """Tests against the script's CLI subprocess interface."""

    def test_strict_mode_exits_nonzero_on_uncovered(self, uncovered_logs_dir):
        """Subprocess invocation with --strict must exit 1 on uncovered tool."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--logs-dir", str(uncovered_logs_dir),
                "--days", "365",
                "--strict",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "BogusTool" in result.stderr

    def test_non_strict_mode_exits_zero_on_uncovered(self, uncovered_logs_dir):
        """Non-strict mode warns but exits 0."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--logs-dir", str(uncovered_logs_dir),
                "--days", "365",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "BogusTool" in result.stderr

    def test_print_classifications_lists_all_observed(self, covered_logs_dir):
        """--print-classifications enumerates every observed tool."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--logs-dir", str(covered_logs_dir),
                "--days", "365",
                "--print-classifications",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Read" in result.stdout
        assert "Bash" in result.stdout
        assert "Write" in result.stdout


class TestAuditAgainstRealLogs:
    """The CI gate per Issue #971 AC #5: real logs must contain only covered tools."""

    def test_real_activity_logs_have_zero_uncovered(self, audit_mod):
        """Run the audit against the actual ``.claude/logs/activity`` dir.

        This is the CI gate. If a new tool appears in the logs without
        being added to ``tool_intent.py`` (or KNOWN_EXEC_TOOLS), this
        test fails and the developer must update the classifier.
        """
        real_logs = REPO_ROOT / ".claude" / "logs" / "activity"
        if not real_logs.exists():
            pytest.skip(f"Activity log dir not present: {real_logs}")
        exit_code, uncovered = audit_mod.audit(
            real_logs, days=30, strict=True
        )
        assert uncovered == [], (
            f"Uncovered tools observed in real activity logs: {uncovered}\n"
            f"Add each to plugins/autonomous-dev/lib/tool_intent.py "
            f"(READ_TOOLS / WRITE_TOOLS) or to KNOWN_EXEC_TOOLS in "
            f"scripts/audit_tool_intent_coverage.py."
        )


# ---------------------------------------------------------------------------
# Issue #1503 — the blanket mcp__ prefix pass is gone
# ---------------------------------------------------------------------------


class TestIssue1503McpCoverageIsNotBlanket:
    """An unregistered mcp__ tool must be reported UNCOVERED.

    The old gate short-circuited with ``if tool_name.startswith("mcp__"):
    return True``, declaring every conceivable MCP tool covered by
    construction. That is why it never flagged the serena editors that were
    walking through the protected-infrastructure hard floor.
    """

    def test_unregistered_mcp_tool_is_uncovered(self, audit_mod):
        assert audit_mod._is_covered("mcp__brandnew__frobnicate") is False

    def test_unregistered_mcp_tool_classifies_as_uncovered(self, audit_mod):
        assert audit_mod._classify_summary("mcp__brandnew__frobnicate") == "UNCOVERED"

    def test_registered_mcp_writer_is_covered(self, audit_mod):
        assert audit_mod._is_covered("mcp__serena__replace_symbol_body") is True
        assert audit_mod._classify_summary(
            "mcp__serena__replace_symbol_body"
        ) == "WRITE (mcp)"

    def test_registered_mcp_reader_is_covered(self, audit_mod):
        assert audit_mod._is_covered("mcp__serena__find_symbol") is True
        assert audit_mod._classify_summary("mcp__serena__find_symbol") == "READ (mcp)"

    def test_known_exec_mcp_tool_is_covered(self, audit_mod):
        """A tool in MCP_KNOWN_EXEC_TOOLS only must classify EXEC (mcp).

        The exemplar was ``mcp__searxng__search`` until it was promoted into
        ``tool_intent.MCP_READ_TOOLS`` (it is read-only: a metasearch query
        mutates nothing). ``mcp__ms365__send-mail`` is used instead because it
        genuinely executes an effect and is in no read/write registry — an
        exemplar that had drifted into READ would have made this test assert
        the wrong class while still looking green.
        """
        assert audit_mod._is_covered("mcp__ms365__send-mail") is True
        assert audit_mod._classify_summary("mcp__ms365__send-mail") == "EXEC (mcp)"

    def test_searxng_is_classified_read_not_exec(self, audit_mod):
        """Registry precedence, made explicit because two sets disagree.

        ``mcp__searxng__search`` appears in BOTH
        ``scripts/audit_tool_intent_coverage.py::MCP_KNOWN_EXEC_TOOLS`` and
        ``tool_intent.MCP_READ_TOOLS``. ``_classify_summary`` consults
        MCP_READ_TOOLS first, so READ wins — which is the correct answer, and
        it is what grants the tool plan-exit passage. Recording the precedence
        here so the stale MCP_KNOWN_EXEC_TOOLS entry cannot silently flip the
        classification if that ordering is ever changed.
        """
        assert audit_mod._is_covered("mcp__searxng__search") is True
        assert audit_mod._classify_summary("mcp__searxng__search") == "READ (mcp)"
        assert audit_mod._classify_summary("mcp__searxng__fetch") == "READ (mcp)"

    def test_covered_and_classify_helpers_agree(self, audit_mod):
        """Both helpers must apply the same registry test (half-fix guard)."""
        for name in (
            "mcp__brandnew__frobnicate",
            "mcp__serena__replace_symbol_body",
            "mcp__serena__find_symbol",
            "mcp__searxng__search",
        ):
            covered = audit_mod._is_covered(name)
            summary = audit_mod._classify_summary(name)
            assert covered == (summary != "UNCOVERED"), (
                f"{name}: _is_covered={covered} but _classify_summary={summary}"
            )

    def test_uncovered_mcp_tool_flows_through_to_strict_audit(self, audit_mod, tmp_path):
        """End-to-end: an unregistered MCP tool in the logs fails --strict."""
        logs = tmp_path / "activity"
        logs.mkdir()
        (logs / "2099-01-01.jsonl").write_text(
            json.dumps({"tool": "mcp__brandnew__frobnicate"}) + "\n"
        )
        exit_code, uncovered = audit_mod.audit(logs, days=99999, strict=True)
        assert exit_code == 1
        assert "mcp__brandnew__frobnicate" in uncovered

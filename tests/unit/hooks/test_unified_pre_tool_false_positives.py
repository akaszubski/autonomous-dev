"""Regression tests for unified_pre_tool false-positive blocks.

Covers three independent surgical fixes landed together in one batch:

- Issue #1032: ``_detect_env_spoofing`` falsely blocking commands whose
  heredoc body merely mentions a protected env var name (e.g. writing
  a Markdown file that documents ``PIPELINE_STATE_FILE``).
- Issue #1001: settings.json writes to ``plugins/*/templates/`` paths
  being blocked even though those paths are template source files, not
  runtime settings. Adds ``_is_settings_template_path`` short-circuit.
  Remediation (security-auditor MEDIUM, A01): the helper is now scoped
  to paths where ``plugins`` appears as a component BEFORE ``templates``
  in the resolved parts, so ``.claude/templates/settings.local.json``
  does NOT bypass the guard.
- Issue #1111: settings.json writes inside the canonical autonomous-dev
  tree being blocked even when self-maintenance mode applies. The
  guard now short-circuits when both ``_is_self_maintenance_mode()`` is
  True and the path is under ``plugins/autonomous-dev/``. Remediation
  (security-auditor LOW, A01): the substring check is replaced by the
  ``_is_plugin_source_path`` helper, which uses component-adjacency
  on the resolved parts to reject look-alikes like
  ``/tmp/plugins/autonomous-dev/settings.local.json``.

Import pattern mirrors ``test_settings_write_via_intent.py``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Path: tests/unit/hooks/<file> -> parents[3] = repo root.
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

upt = importlib.import_module("unified_pre_tool")


# ---------------------------------------------------------------------------
# Issue #1032 — heredoc body must not trip env-spoof detection
# ---------------------------------------------------------------------------


class TestIssue1032HeredocFalsePositive:
    """Heredoc bodies that mention protected env-var names must not block."""

    def test_1032_heredoc_with_protected_var_not_blocked(self) -> None:
        """Heredoc body that mentions PIPELINE_STATE_FILE must NOT block.

        Regression: previously the env-spoof detector only stripped quoted
        segments, so a heredoc body containing the literal string
        ``PIPELINE_STATE_FILE`` was treated as an inline assignment.
        """
        cmd = "cat > /tmp/x.md << 'EOF'\nPIPELINE_STATE_FILE here\nEOF"
        assert upt._detect_env_spoofing(cmd) is None

    def test_1032_inline_env_var_still_blocked(self) -> None:
        """Real inline env-var spoofing MUST still block (no regression)."""
        cmd = "CLAUDE_AGENT_NAME=implementer python3 run.py"
        result = upt._detect_env_spoofing(cmd)
        assert result is not None
        assert "BLOCKED" in result
        assert "CLAUDE_AGENT_NAME" in result


# ---------------------------------------------------------------------------
# Issue #1001 — _is_settings_template_path helper
# ---------------------------------------------------------------------------


class TestIssue1001SettingsTemplatePath:
    """``_is_settings_template_path`` recognises template source paths."""

    def test_1001_template_path_returns_true(self) -> None:
        """Plugin template path ('plugins' precedes 'templates') returns True."""
        assert (
            upt._is_settings_template_path(
                "plugins/autonomous-dev/templates/settings.local.json"
            )
            is True
        )

    def test_1001_non_template_path_returns_false(self) -> None:
        """Runtime settings path (no 'templates' component) returns False."""
        assert upt._is_settings_template_path(".claude/settings.local.json") is False

    def test_1001_empty_path_returns_false(self) -> None:
        """Empty string input returns False (does not raise)."""
        assert upt._is_settings_template_path("") is False

    def test_1001_template_short_circuit(self) -> None:
        """Helper-level confirmation that template paths are the bypass key.

        The settings.json write guard at unified_pre_tool.py:~4359 uses
        this helper to short-circuit; locking the helper's truth-table
        locks the bypass behaviour.
        """
        # Positive: a deeper template path still trips the rule.
        assert (
            upt._is_settings_template_path(
                "plugins/autonomous-dev/templates/nested/settings.json"
            )
            is True
        )
        # Negative: a path with 'template' (singular) does NOT bypass — the
        # check is for the exact component 'templates'.
        assert (
            upt._is_settings_template_path(
                "plugins/autonomous-dev/template/settings.json"
            )
            is False
        )

    def test_1001_claude_templates_bypass_blocked(self) -> None:
        """Remediation (security-auditor MEDIUM, A01 Broken Access Control).

        ``.claude/templates/settings.local.json`` previously bypassed the
        Issue #557 settings-write guard because the helper matched any
        path with a ``templates`` component anywhere. The tightened
        predicate now requires ``plugins`` to appear BEFORE ``templates``
        in the resolved parts, so consumer-side ``.claude/templates/``
        paths no longer bypass the guard.
        """
        assert (
            upt._is_settings_template_path(".claude/templates/settings.local.json")
            is False
        )


# ---------------------------------------------------------------------------
# Issue #1111 — self-maintenance branch covers plugin-source settings writes
# ---------------------------------------------------------------------------


class TestIssue1111SelfMaintenanceBranch:
    """Self-maintenance + plugin-source path must bypass the settings guard.

    The guard at unified_pre_tool.py:~4395 reads::

        elif (
            _is_self_maintenance_mode()
            and _is_plugin_source_path(file_path)
        ):
            pass

    The substring check was tightened to a helper call after the
    security-auditor LOW finding (A01) — see ``_is_plugin_source_path``.
    """

    def test_1111_self_maintenance_plugins_path_check(self, monkeypatch) -> None:
        """Documents the branch predicate used by the settings guard.

        Pins both halves of the AND: with self-maintenance forced True
        via monkeypatch, the path helper is the sole remaining gate.
        """
        monkeypatch.setattr(upt, "_is_self_maintenance_mode", lambda: True)

        # Real plugin-source path satisfies the helper.
        target_path = "plugins/autonomous-dev/settings.local.json"
        assert upt._is_self_maintenance_mode() is True
        assert upt._is_plugin_source_path(target_path) is True

        # Negative: a consumer-side path under .claude/ does NOT satisfy
        # the helper even when self-maintenance is True.
        consumer_path = ".claude/settings.local.json"
        assert upt._is_plugin_source_path(consumer_path) is False

    def test_1111_plugin_source_path_helper(self) -> None:
        """Remediation: helper returns True for real plugin-source paths.

        ``plugins/autonomous-dev/settings.local.json`` resolves under
        the canonical autonomous-dev source tree (verified by the
        marketplace.json marker in this worktree) and so must match.
        """
        assert (
            upt._is_plugin_source_path("plugins/autonomous-dev/settings.local.json")
            is True
        )

    def test_1111_tmp_plugins_path_not_matched(self) -> None:
        """Remediation (security-auditor LOW, A01): /tmp look-alike must NOT match.

        The previous substring check
        (``"plugins/autonomous-dev/" in str(file_path)``) would have
        matched ``/tmp/plugins/autonomous-dev/settings.local.json``.
        The tightened helper requires both component adjacency AND a
        real autonomous-dev source tree (verified via the
        ``plugins/autonomous-dev/.claude-plugin/marketplace.json``
        marker), so the /tmp look-alike is rejected.
        """
        assert (
            upt._is_plugin_source_path("/tmp/plugins/autonomous-dev/settings.local.json")
            is False
        )

    def test_1111_empty_path_returns_false(self) -> None:
        """Empty string input returns False (does not raise)."""
        assert upt._is_plugin_source_path("") is False

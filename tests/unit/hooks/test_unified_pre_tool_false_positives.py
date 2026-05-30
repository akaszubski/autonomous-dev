"""Regression tests for unified_pre_tool false-positive blocks.

Covers four independent surgical fixes:

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
- Issue #918: Coordinator blocked on READ of settings.local.json — the
  settings-write guard MUST NOT fire for Read-tool calls. Regression
  class ``TestIssue918ReadToolNeverBlocksSettings`` locks this in via
  end-to-end dispatch tests.

Import pattern mirrors ``test_settings_write_via_intent.py``.
"""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# Issue #918 — Read tool MUST NOT trigger settings.json write-protect guard
# ---------------------------------------------------------------------------


class TestIssue918ReadToolNeverBlocksSettings:
    """Read-tool dispatch to settings.json paths MUST never produce a deny decision.

    Issue #918 reports that the coordinator was blocked on a Read operation
    targeting .claude/settings.local.json.  Research confirmed the production
    code is already correctly tool-name-gated: the ``settings_json_write_block``
    deviation is triggered at exactly two locations in unified_pre_tool.py:

    - Line 4457: ``if tool_name in ("Write", "Edit"):``  — the Write/Edit gate
    - Line 4685: ``if tool_name == "Bash":``             — the Bash gate

    A Read tool call with tool_name="Read" cannot structurally reach either
    gate.  These tests lock that invariant in place so no future refactor can
    accidentally widen the gate to include "Read".

    The ``_run_hook`` helper follows the canonical end-to-end dispatch pattern
    used by ``TestInfraProtectionInMainFlow`` in
    ``test_infrastructure_protection.py``: patch sys.stdin with the hook JSON
    payload, capture sys.stdout, call ``upt.main()``, parse the output JSON.
    """

    # ------------------------------------------------------------------
    # End-to-end dispatch helper (mirrors test_infrastructure_protection.py)
    # ------------------------------------------------------------------

    def _run_hook(self, tool_name: str, tool_input: dict, **extra_fields: object) -> dict:
        """Invoke upt.main() with a synthesised PreToolUse payload.

        Returns the parsed JSON object that the hook writes to stdout.
        An empty dict is returned when the hook produces no JSON output
        (which itself indicates an error — callers should assert on a
        non-empty result).

        Args:
            tool_name: The PreToolUse ``tool_name`` field.
            tool_input: The PreToolUse ``tool_input`` dict.
            **extra_fields: Additional top-level payload fields (e.g.
                ``session_id``, ``hook_event_name``).

        Returns:
            Parsed JSON dict from the hook's stdout.
        """
        payload = {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "session_id": extra_fields.pop("session_id", "test-918"),
            "hook_event_name": extra_fields.pop("hook_event_name", "PreToolUse"),
            **extra_fields,
        }
        input_data = json.dumps(payload)
        captured = StringIO()

        with patch("sys.stdin", StringIO(input_data)), \
             patch("sys.stdout", captured), \
             pytest.raises(SystemExit):
            upt.main()

        output_text = captured.getvalue().strip()
        lines = [line for line in output_text.split("\n") if line.strip()]
        if not lines:
            return {}
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError:
            return {}

    def _get_decision(self, result: dict) -> str:
        """Extract the permissionDecision string from the hook output dict."""
        return result.get("hookSpecificOutput", {}).get("permissionDecision", "")

    # ------------------------------------------------------------------
    # Test 1: Read on settings.local.json — no pipeline active
    # ------------------------------------------------------------------

    def test_918_dispatch_read_settings_local_no_block(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """END-TO-END: Read tool on .claude/settings.local.json MUST be allowed.

        This is the canonical regression test for Issue #918.  Simulates the
        exact payload that was reported to trigger an erroneous block:
        tool_name="Read", file_path=".claude/settings.local.json".

        With no active pipeline the settings-write guard never fires (it only
        blocks when ``_is_pipeline_active()`` returns True).  But even with a
        live pipeline, Read cannot reach the guard — this test covers the
        no-pipeline baseline.
        """
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)

        result = self._run_hook(
            "Read",
            {"file_path": ".claude/settings.local.json"},
            session_id="test-918",
            hook_event_name="PreToolUse",
        )

        assert result, "Hook must produce JSON output"
        decision = self._get_decision(result)
        assert decision == "allow", (
            f"Read on settings.local.json must be 'allow', got {decision!r}. "
            f"Full hook output: {result}"
        )

    # ------------------------------------------------------------------
    # Test 2: Read on settings.local.json — pipeline ACTIVE (worst case)
    # ------------------------------------------------------------------

    def test_918_dispatch_read_settings_local_no_block_pipeline_active(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """END-TO-END: Read tool MUST be allowed even when /implement pipeline is active.

        Worst-case scenario: an active pipeline is running.  The settings-write
        guard at line 4525 only executes inside ``if tool_name in ("Write", "Edit"):``
        (line 4457), so Read tool calls CANNOT reach it regardless of pipeline state.
        """
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: True)

        result = self._run_hook(
            "Read",
            {"file_path": ".claude/settings.local.json"},
            session_id="test-918",
            hook_event_name="PreToolUse",
        )

        assert result, "Hook must produce JSON output"
        decision = self._get_decision(result)
        assert decision == "allow", (
            f"Read on settings.local.json must be 'allow' even during active pipeline, "
            f"got {decision!r}. Full hook output: {result}"
        )

    # ------------------------------------------------------------------
    # Test 3: Read on settings.json (without .local)
    # ------------------------------------------------------------------

    def test_918_dispatch_read_settings_json_no_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """END-TO-END: Read tool on .claude/settings.json MUST be allowed.

        Extends test #1 to the non-.local variant.  The same structural
        argument applies: only tool_name "Write", "Edit", and "Bash" can
        reach the settings-write guard.
        """
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: True)

        result = self._run_hook(
            "Read",
            {"file_path": ".claude/settings.json"},
            session_id="test-918",
            hook_event_name="PreToolUse",
        )

        assert result, "Hook must produce JSON output"
        decision = self._get_decision(result)
        assert decision == "allow", (
            f"Read on settings.json must be 'allow', got {decision!r}. "
            f"Full hook output: {result}"
        )

    # ------------------------------------------------------------------
    # Test 4: Read on an infrastructure-protected file
    # ------------------------------------------------------------------

    def test_918_dispatch_read_other_protected_no_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Defense-in-depth: Read tool on a write-protected infrastructure file is allowed.

        ``plugins/autonomous-dev/hooks/unified_pre_tool.py`` is an
        infrastructure-protected file (in the ``/hooks/`` segment).  The
        infrastructure-protection guard at line 4457 only fires for Write/Edit,
        not for Read.  This test confirms reading infra files is always allowed.
        """
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)

        result = self._run_hook(
            "Read",
            {"file_path": "plugins/autonomous-dev/hooks/unified_pre_tool.py"},
            session_id="test-918",
            hook_event_name="PreToolUse",
        )

        assert result, "Hook must produce JSON output"
        decision = self._get_decision(result)
        assert decision == "allow", (
            f"Read on infrastructure file must be 'allow', got {decision!r}. "
            f"Full hook output: {result}"
        )

    # ------------------------------------------------------------------
    # Test 5: Write to settings.local.json WITH active pipeline STILL blocks
    # ------------------------------------------------------------------

    def test_918_dispatch_write_settings_local_still_blocks_when_pipeline_active(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sanity / no-regression: Write to settings.local.json MUST still block.

        Proves the legitimate Issue #557 guard has not been weakened by our
        test additions.  With an active pipeline, a Write to
        ``.claude/settings.local.json`` must produce a deny decision with the
        ``settings_json_write_block`` category.
        """
        # Ensure the path is NOT treated as a template or plugin-source path
        monkeypatch.setattr(upt, "_is_settings_template_path", lambda _: False)
        monkeypatch.setattr(upt, "_is_self_maintenance_mode", lambda: False)
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: True)
        # Suppress infrastructure-protection check so only the settings guard fires
        monkeypatch.setattr(upt, "_is_protected_infrastructure", lambda _: False)

        result = self._run_hook(
            "Write",
            {"file_path": ".claude/settings.local.json", "content": "{}"},
            session_id="test-918",
            hook_event_name="PreToolUse",
        )

        assert result, "Hook must produce JSON output"
        decision = self._get_decision(result)
        assert decision == "deny", (
            f"Write to settings.local.json during active pipeline MUST be 'deny', "
            f"got {decision!r}.  The Issue #557 guard must remain intact. "
            f"Full hook output: {result}"
        )
        reason = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "BLOCKED" in reason, (
            f"Deny reason must contain 'BLOCKED'. Got: {reason!r}"
        )

    # ------------------------------------------------------------------
    # Test 6: Bash redirect to settings.local.json WITH active pipeline STILL blocks
    # ------------------------------------------------------------------

    def test_918_dispatch_bash_write_settings_local_still_blocks_when_pipeline_active(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sanity / no-regression: Bash redirect to settings.local.json MUST still block.

        Proves the Bash-path guard at line 4685/4911 is intact.  With an
        active pipeline, ``echo '{}' > .claude/settings.local.json`` MUST
        produce a deny decision.
        """
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: True)

        result = self._run_hook(
            "Bash",
            {"command": "echo '{}' > .claude/settings.local.json"},
            session_id="test-918",
            hook_event_name="PreToolUse",
        )

        assert result, "Hook must produce JSON output"
        decision = self._get_decision(result)
        assert decision == "deny", (
            f"Bash redirect to settings.local.json during active pipeline MUST be 'deny', "
            f"got {decision!r}.  The Issue #557 Bash guard must remain intact. "
            f"Full hook output: {result}"
        )

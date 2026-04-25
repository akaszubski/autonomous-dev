"""
Regression tests for Issue #358: Auto-route plan mode output to /implement or /create-issue.

Validates:
1. plan_mode_exit_detector.py hook is registered in all settings templates
2. plan_mode_exit_detector.py is listed in install_manifest.json
3. unified_prompt_validator.py has plan mode enforcement logic
4. known_bypass_patterns.json references issue #358
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class TestIssue358HookRegistration:
    """Verify plan_mode_exit_detector hook is properly wired up."""

    SETTINGS_TEMPLATES = [
        "plugins/autonomous-dev/templates/settings.default.json",
        "plugins/autonomous-dev/templates/settings.autonomous-dev.json",
        "plugins/autonomous-dev/templates/settings.local.json",
        "plugins/autonomous-dev/templates/settings.strict-mode.json",
        "plugins/autonomous-dev/templates/settings.granular-bash.json",
        "plugins/autonomous-dev/templates/settings.permission-batching.json",
        "plugins/autonomous-dev/config/global_settings_template.json",
    ]

    @pytest.mark.parametrize("template_path", SETTINGS_TEMPLATES)
    def test_hook_registered_in_settings_template(self, template_path: str):
        """plan_mode_exit_detector must be registered in PostToolUse for ExitPlanMode."""
        full_path = PROJECT_ROOT / template_path
        assert full_path.exists(), f"Template not found: {template_path}"
        settings = json.loads(full_path.read_text())

        post_tool_use = settings.get("hooks", {}).get("PostToolUse", [])
        exit_plan_entries = [
            entry for entry in post_tool_use
            if entry.get("matcher") == "ExitPlanMode"
        ]
        assert len(exit_plan_entries) >= 1, (
            f"No ExitPlanMode PostToolUse entry in {template_path}"
        )

        # Verify the hook command references plan_mode_exit_detector
        hook_commands = [
            hook["command"]
            for entry in exit_plan_entries
            for hook in entry.get("hooks", [])
        ]
        assert any(
            "plan_mode_exit_detector" in cmd for cmd in hook_commands
        ), f"plan_mode_exit_detector not in hook commands: {hook_commands}"

    def test_hook_in_install_manifest(self):
        """plan_mode_exit_detector.py must be listed in install_manifest.json."""
        manifest_path = PROJECT_ROOT / "plugins/autonomous-dev/install_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        hook_files = manifest["components"]["hooks"]["files"]
        assert any(
            "plan_mode_exit_detector.py" in f for f in hook_files
        ), "plan_mode_exit_detector.py not in install_manifest.json hooks"

    def test_hook_file_exists(self):
        """The hook Python file must exist."""
        hook_path = PROJECT_ROOT / "plugins/autonomous-dev/hooks/plan_mode_exit_detector.py"
        assert hook_path.exists(), "plan_mode_exit_detector.py not found"

    def test_known_bypass_patterns_references_358(self):
        """known_bypass_patterns.json should reference issue #358."""
        patterns_path = (
            PROJECT_ROOT / "plugins/autonomous-dev/config/known_bypass_patterns.json"
        )
        patterns = json.loads(patterns_path.read_text())
        all_issues = []
        for pattern in patterns["patterns"]:
            issue = pattern.get("issue")
            if issue:
                all_issues.append(issue)
        assert "#358" in all_issues, (
            f"Issue #358 not found in known_bypass_patterns.json. Found: {all_issues}"
        )

    def test_plan_exit_enforcement_no_longer_in_userpromptsubmit(self):
        """Issue #926: Plan-exit enforcement removed from UserPromptSubmit hook.

        Verifies the migration to PreToolUse — neither the gate function
        nor the constants remain in unified_prompt_validator.py.
        """
        validator_path = (
            PROJECT_ROOT / "plugins/autonomous-dev/hooks/unified_prompt_validator.py"
        )
        content = validator_path.read_text()
        # Function definitions and constants must be absent (only comment refs OK)
        forbidden = [
            "def _check_plan_mode_enforcement",
            "def _extract_wrapped_command",
            "PLAN_MODE_EXIT_MARKER = ",
            "PLAN_MODE_STALE_MINUTES = ",
        ]
        present = [s for s in forbidden if s in content]
        assert present == [], (
            f"Plan-exit enforcement still in unified_prompt_validator.py: {present}. "
            f"Per Issue #926, enforcement moved to unified_pre_tool.py."
        )

    def test_sandbox_enforcer_not_imported_in_pretool(self):
        """Issue #926 (AC #17): SandboxEnforcer NOT used by plan-exit gate.

        Plan-critic flagged Option C (reuse SandboxEnforcer) as structurally
        wrong: SandboxEnforcer operates only in the MCP/Layer-0 sandbox path,
        not the NATIVE_TOOLS branch where this enforcement lives. This test
        prevents accidental reintroduction by ensuring the count of SandboxEnforcer
        imports stays at exactly 1 (the pre-existing Layer 0 import in
        `validate_sandbox_layer`). Any additional import would suggest the
        plan-exit gate is reusing SandboxEnforcer — forbidden by AC #17.
        """
        pretool_path = (
            PROJECT_ROOT / "plugins/autonomous-dev/hooks/unified_pre_tool.py"
        )
        content = pretool_path.read_text()
        # Count import statements (not arbitrary mentions)
        import_lines = [
            line for line in content.splitlines()
            if (("from sandbox_enforcer import" in line)
                or ("import sandbox_enforcer" in line))
            and not line.strip().startswith("#")
        ]
        assert len(import_lines) <= 1, (
            f"Multiple SandboxEnforcer imports found ({len(import_lines)}); "
            f"only the Layer 0 import in validate_sandbox_layer is allowed. "
            f"Per Issue #926 AC #17, the plan-exit gate must NOT reuse "
            f"SandboxEnforcer (structural mismatch — SandboxEnforcer operates "
            f"only on Bash commands in the MCP/Layer-0 path, but plan-exit "
            f"enforcement lives in the NATIVE_TOOLS branch). "
            f"Found imports: {import_lines}"
        )

        # Verify the plan-exit helpers don't reference SandboxEnforcer in any way
        # (they should use the dedicated _PLAN_EXIT_BASH_ALLOWLIST_* frozensets).
        # Find the plan-exit helper section
        plan_exit_section_start = content.find("def _check_plan_exit_native")
        plan_exit_section_end = content.find("def main():", plan_exit_section_start)
        if plan_exit_section_start != -1 and plan_exit_section_end != -1:
            plan_exit_section = content[plan_exit_section_start:plan_exit_section_end]
            assert "SandboxEnforcer" not in plan_exit_section, (
                "Plan-exit helper functions must not reference SandboxEnforcer "
                "(AC #17). Use _PLAN_EXIT_BASH_ALLOWLIST_* frozensets instead."
            )

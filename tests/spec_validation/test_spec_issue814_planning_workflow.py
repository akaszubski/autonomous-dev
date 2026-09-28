"""Spec validation tests for Issue #814: Planning workflow system.

Validates acceptance criteria:
1. /plan command exists and is user-invocable
2. Plan file format includes required sections: WHY + SCOPE, Existing Solutions, Minimal Path
3. plan-critic agent exists with minimum 2 critique rounds before PROCEED
4. plan-critic has PROCEED/REVISE/BLOCKED verdicts
5. Write/Edit to non-doc file blocked if no valid plan (beyond complexity threshold)
6. Block message includes REQUIRED NEXT ACTION: run /plan
7. SKIP_PLAN_CHECK=1 env var disables all hook checks
8. Hook exception results in allow (fail-open)
9. Hook blocks when Existing Solutions section is missing from plan
10. plan_validator.py returns specific missing sections in error output
11. Expired plan (>72h) -> WARN, not block
12. /plan-to-issues detects .claude/plans/ files
13. Hook registered in settings templates and install manifest
14. docs/PLANNING-WORKFLOW.md exists
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
COMMANDS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "commands"
AGENTS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "agents"
SKILLS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "skills"
CONFIG_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "config"
DOCS_DIR = REPO_ROOT / "docs"

sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(LIB_DIR))


@pytest.fixture(autouse=True)
def _ensure_paths():
    """Ensure hooks and lib dirs are on sys.path."""
    for d in (str(HOOKS_DIR), str(LIB_DIR)):
        if d not in sys.path:
            sys.path.insert(0, d)
    yield


# ---------------------------------------------------------------------------
# AC1: /plan command exists and is user-invocable
# ---------------------------------------------------------------------------


class TestSpec814AC1PlanCommandExists:
    """The /plan command must exist and be user-invocable."""

    def test_spec_814_1_plan_command_file_exists(self):
        """plan.md command file must exist in commands directory."""
        plan_cmd = COMMANDS_DIR / "plan.md"
        assert plan_cmd.exists(), f"plan.md command not found at {plan_cmd}"

    def test_spec_814_1_plan_command_is_user_invocable(self):
        """plan.md must have user-invocable: true in frontmatter."""
        plan_cmd = COMMANDS_DIR / "plan.md"
        content = plan_cmd.read_text()
        assert "user-invocable: true" in content, \
            "plan.md must declare user-invocable: true"


# ---------------------------------------------------------------------------
# AC2: Plan file format includes required sections
# ---------------------------------------------------------------------------


class TestSpec814AC2PlanFileFormat:
    """Plan validator must check for required sections."""

    def test_spec_814_2_validator_checks_why_scope(self):
        """Validator must require '## WHY + SCOPE' section."""
        from plan_validator import REQUIRED_SECTIONS
        matching = [s for s in REQUIRED_SECTIONS if "WHY" in s and "SCOPE" in s]
        assert len(matching) > 0, "REQUIRED_SECTIONS must include WHY + SCOPE"

    def test_spec_814_2_validator_checks_existing_solutions(self):
        """Validator must require '## Existing Solutions' section."""
        from plan_validator import REQUIRED_SECTIONS
        matching = [s for s in REQUIRED_SECTIONS if "Existing Solutions" in s]
        assert len(matching) > 0, "REQUIRED_SECTIONS must include Existing Solutions"

    def test_spec_814_2_validator_checks_minimal_path(self):
        """Validator must require '## Minimal Path' section."""
        from plan_validator import REQUIRED_SECTIONS
        matching = [s for s in REQUIRED_SECTIONS if "Minimal Path" in s]
        assert len(matching) > 0, "REQUIRED_SECTIONS must include Minimal Path"

    def test_spec_814_2_valid_plan_passes_validation(self):
        """A plan with all required sections must pass validation."""
        from plan_validator import validate_plan

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(
                "# Plan: Test Feature\n\n"
                "## WHY + SCOPE\nThis is needed because...\n\n"
                "## Existing Solutions\nSearched codebase, nothing found.\n\n"
                "## Minimal Path\nCreate one file.\n"
            )
            f.flush()
            try:
                result = validate_plan(Path(f.name))
                assert result.valid is True, \
                    f"Plan with all sections should be valid, got missing: {result.missing_sections}"
                assert len(result.missing_sections) == 0
            finally:
                os.unlink(f.name)


# ---------------------------------------------------------------------------
# AC3: plan-critic agent exists with minimum 2 critique rounds
# ---------------------------------------------------------------------------


class TestSpec814AC3PlanCriticAgent:
    """plan-critic agent must exist and require 2+ critique rounds."""

    def test_spec_814_3_plan_critic_file_exists(self):
        """plan-critic.md agent file must exist."""
        agent_file = AGENTS_DIR / "plan-critic.md"
        assert agent_file.exists(), f"plan-critic.md not found at {agent_file}"

    def test_spec_814_3_minimum_2_critique_rounds(self):
        """plan-critic must specify minimum 2 critique rounds before PROCEED."""
        agent_file = AGENTS_DIR / "plan-critic.md"
        content = agent_file.read_text()
        # Check for the 2-round requirement
        assert "2 critique rounds" in content.lower() or "minimum 2" in content.lower() or \
            "minimum of 2" in content.lower(), \
            "plan-critic must specify minimum 2 critique rounds"


# ---------------------------------------------------------------------------
# AC4: plan-critic has PROCEED/REVISE/BLOCKED verdicts
# ---------------------------------------------------------------------------


class TestSpec814AC4PlanCriticVerdicts:
    """plan-critic must support all three verdict types."""

    def test_spec_814_4_proceed_verdict(self):
        """plan-critic must define PROCEED verdict."""
        content = (AGENTS_DIR / "plan-critic.md").read_text()
        assert "PROCEED" in content, "plan-critic must define PROCEED verdict"

    def test_spec_814_4_revise_verdict(self):
        """plan-critic must define REVISE verdict."""
        content = (AGENTS_DIR / "plan-critic.md").read_text()
        assert "REVISE" in content, "plan-critic must define REVISE verdict"

    def test_spec_814_4_blocked_verdict(self):
        """plan-critic must define BLOCKED verdict."""
        content = (AGENTS_DIR / "plan-critic.md").read_text()
        assert "BLOCKED" in content, "plan-critic must define BLOCKED verdict"


# ---------------------------------------------------------------------------
# AC5: Write/Edit to non-doc file blocked if no valid plan
# ---------------------------------------------------------------------------


class TestSpec814AC5HookBlocksWithoutPlan:
    """Hook must block Write/Edit to non-doc files when no plan exists."""

    def test_spec_814_5_block_write_without_plan(self):
        """Write to a .py file with no plan should be blocked."""
        import plan_gate

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a large content (above threshold)
            large_content = "x = 1\n" * 150  # 150 lines, above 100-line threshold

            hook_input = json.dumps({
                "tool_name": "Write",
                "tool_input": {
                    "file_path": os.path.join(tmpdir, "src", "feature.py"),
                    "content": large_content,
                },
            })

            # No plans dir exists in tmpdir
            with patch("sys.stdin") as mock_stdin, \
                 patch("builtins.print") as mock_print, \
                 patch.dict(os.environ, {}, clear=False), \
                 patch("os.getcwd", return_value=tmpdir):
                # Remove SKIP_PLAN_CHECK if set
                os.environ.pop("SKIP_PLAN_CHECK", None)
                mock_stdin.read.return_value = hook_input

                plan_gate.main()

                # Find the JSON output call (to stdout, not stderr)
                json_calls = [
                    c for c in mock_print.call_args_list
                    if c.args and isinstance(c.args[0], str)
                    and not c.kwargs.get("file")
                ]
                assert len(json_calls) > 0, "Hook must produce JSON output"
                output = json.loads(json_calls[0].args[0])
                decision = output["hookSpecificOutput"]["permissionDecision"]
                # Issue #1589: the refusal value is the enum-conformant "deny".
                assert decision == "deny", \
                    f"Write without plan should be refused, got: {decision}"


# ---------------------------------------------------------------------------
# AC6: Block message includes REQUIRED NEXT ACTION: run /plan
# ---------------------------------------------------------------------------


class TestSpec814AC6BlockMessageContent:
    """Block message must include REQUIRED NEXT ACTION directive."""

    def test_spec_814_6_block_message_has_required_action(self):
        """Block message must contain 'REQUIRED NEXT ACTION: run /plan'."""
        import plan_gate

        with tempfile.TemporaryDirectory() as tmpdir:
            large_content = "x = 1\n" * 150

            hook_input = json.dumps({
                "tool_name": "Write",
                "tool_input": {
                    "file_path": os.path.join(tmpdir, "src", "feature.py"),
                    "content": large_content,
                },
            })

            with patch("sys.stdin") as mock_stdin, \
                 patch("builtins.print") as mock_print, \
                 patch.dict(os.environ, {}, clear=False), \
                 patch("os.getcwd", return_value=tmpdir):
                os.environ.pop("SKIP_PLAN_CHECK", None)
                mock_stdin.read.return_value = hook_input

                plan_gate.main()

                json_calls = [
                    c for c in mock_print.call_args_list
                    if c.args and isinstance(c.args[0], str)
                    and not c.kwargs.get("file")
                ]
                output = json.loads(json_calls[0].args[0])
                system_msg = output.get("systemMessage", "")
                assert "REQUIRED NEXT ACTION: run /plan" in system_msg, \
                    f"Block message must include 'REQUIRED NEXT ACTION: run /plan', got: {system_msg}"


# ---------------------------------------------------------------------------
# AC7: SKIP_PLAN_CHECK=1 disables all hook checks
# ---------------------------------------------------------------------------


class TestSpec814AC7SkipPlanCheckEnvVar:
    """SKIP_PLAN_CHECK=1 must disable all plan gate checks."""

    def test_spec_814_7_skip_plan_check_allows_write(self):
        """Write to non-doc file with SKIP_PLAN_CHECK=1 should be allowed."""
        import plan_gate

        with tempfile.TemporaryDirectory() as tmpdir:
            large_content = "x = 1\n" * 150

            hook_input = json.dumps({
                "tool_name": "Write",
                "tool_input": {
                    "file_path": os.path.join(tmpdir, "src", "feature.py"),
                    "content": large_content,
                },
            })

            with patch("sys.stdin") as mock_stdin, \
                 patch("builtins.print") as mock_print, \
                 patch.dict(os.environ, {"SKIP_PLAN_CHECK": "1"}, clear=False), \
                 patch("os.getcwd", return_value=tmpdir):
                mock_stdin.read.return_value = hook_input

                plan_gate.main()

                json_calls = [
                    c for c in mock_print.call_args_list
                    if c.args and isinstance(c.args[0], str)
                    and not c.kwargs.get("file")
                ]
                output = json.loads(json_calls[0].args[0])
                decision = output["hookSpecificOutput"]["permissionDecision"]
                assert decision == "allow", \
                    f"SKIP_PLAN_CHECK=1 should allow, got: {decision}"


# ---------------------------------------------------------------------------
# AC8: Hook exception results in allow (fail-open)
# ---------------------------------------------------------------------------


class TestSpec814AC8FailOpen:
    """Hook must fail-open on exceptions."""

    def test_spec_814_8_invalid_json_input_allows(self):
        """Invalid JSON input to hook should result in allow (fail-open)."""
        import plan_gate

        with patch("sys.stdin") as mock_stdin, \
             patch("builtins.print") as mock_print:
            mock_stdin.read.return_value = "NOT VALID JSON {"

            plan_gate.main()

            json_calls = [
                c for c in mock_print.call_args_list
                if c.args and isinstance(c.args[0], str)
                and not c.kwargs.get("file")
            ]
            assert len(json_calls) > 0, "Hook must produce JSON output even on bad input"
            output = json.loads(json_calls[0].args[0])
            decision = output["hookSpecificOutput"]["permissionDecision"]
            assert decision == "allow", \
                f"Invalid input should fail-open with allow, got: {decision}"


# ---------------------------------------------------------------------------
# AC9: Hook blocks when Existing Solutions section is missing
# ---------------------------------------------------------------------------


class TestSpec814AC9MissingExistingSolutions:
    """Hook must block when plan is missing Existing Solutions section."""

    def test_spec_814_9_block_plan_missing_existing_solutions(self):
        """Plan without Existing Solutions section should cause block."""
        import plan_gate

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plans dir with a plan missing Existing Solutions
            plans_dir = Path(tmpdir) / ".claude" / "plans"
            plans_dir.mkdir(parents=True)
            plan_file = plans_dir / "test-feature.md"
            plan_file.write_text(
                "# Plan: Test Feature\n\n"
                "## WHY + SCOPE\nThis is needed.\n\n"
                "## Minimal Path\nCreate one file.\n"
                # NOTE: Existing Solutions section deliberately omitted
            )

            large_content = "x = 1\n" * 150
            hook_input = json.dumps({
                "tool_name": "Write",
                "tool_input": {
                    "file_path": os.path.join(tmpdir, "src", "feature.py"),
                    "content": large_content,
                },
            })

            with patch("sys.stdin") as mock_stdin, \
                 patch("builtins.print") as mock_print, \
                 patch.dict(os.environ, {}, clear=False), \
                 patch("os.getcwd", return_value=tmpdir):
                os.environ.pop("SKIP_PLAN_CHECK", None)
                mock_stdin.read.return_value = hook_input

                plan_gate.main()

                json_calls = [
                    c for c in mock_print.call_args_list
                    if c.args and isinstance(c.args[0], str)
                    and not c.kwargs.get("file")
                ]
                output = json.loads(json_calls[0].args[0])
                decision = output["hookSpecificOutput"]["permissionDecision"]
                # Issue #1589: the refusal value is the enum-conformant "deny".
                assert decision == "deny", \
                    f"Plan missing Existing Solutions should be refused, got: {decision}"


# ---------------------------------------------------------------------------
# AC10: plan_validator.py returns specific missing sections
# ---------------------------------------------------------------------------


class TestSpec814AC10ValidatorMissingSections:
    """Validator must return specific missing section names."""

    def test_spec_814_10_missing_sections_listed_specifically(self):
        """Validator must name each missing section in the result."""
        from plan_validator import validate_plan

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            # Plan with only WHY + SCOPE (missing Existing Solutions and Minimal Path)
            f.write(
                "# Plan: Test\n\n"
                "## WHY + SCOPE\nNeeded for testing.\n"
            )
            f.flush()
            try:
                result = validate_plan(Path(f.name))
                assert result.valid is False, "Plan missing sections should be invalid"
                assert len(result.missing_sections) == 2, \
                    f"Should report 2 missing sections, got: {result.missing_sections}"
                # Check specific section names appear
                missing_text = " ".join(result.missing_sections)
                assert "Existing Solutions" in missing_text, \
                    f"Missing sections should include 'Existing Solutions', got: {result.missing_sections}"
                assert "Minimal Path" in missing_text, \
                    f"Missing sections should include 'Minimal Path', got: {result.missing_sections}"
            finally:
                os.unlink(f.name)


# ---------------------------------------------------------------------------
# AC11: Expired plan (>72h) -> WARN, not block
# ---------------------------------------------------------------------------


class TestSpec814AC11ExpiredPlanWarning:
    """Expired plans should warn, not block."""

    def test_spec_814_11_expired_plan_marks_expired_flag(self):
        """Plan older than 72h should have expired=True but valid=True."""
        from plan_validator import validate_plan

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(
                "# Plan: Test Feature\n\n"
                "## WHY + SCOPE\nNeeded.\n\n"
                "## Existing Solutions\nNone found.\n\n"
                "## Minimal Path\nOne file.\n"
            )
            f.flush()
            plan_path = Path(f.name)

            try:
                # Set modification time to 73 hours ago
                old_time = time.time() - (73 * 3600)
                os.utime(f.name, (old_time, old_time))

                result = validate_plan(plan_path)
                assert result.valid is True, \
                    "Expired plan with all sections should still be valid (warn, not block)"
                assert result.expired is True, \
                    f"Plan >72h old should be marked expired, age_hours={result.age_hours}"
            finally:
                os.unlink(f.name)

    def test_spec_814_11_expired_plan_allowed_by_hook(self):
        """Hook must allow an expired plan (warn only, not block)."""
        import plan_gate

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid but expired plan
            plans_dir = Path(tmpdir) / ".claude" / "plans"
            plans_dir.mkdir(parents=True)
            plan_file = plans_dir / "old-feature.md"
            plan_file.write_text(
                "# Plan: Old Feature\n\n"
                "## WHY + SCOPE\nNeeded.\n\n"
                "## Existing Solutions\nNone found.\n\n"
                "## Minimal Path\nOne file.\n"
            )
            # Set modification time to 73 hours ago
            old_time = time.time() - (73 * 3600)
            os.utime(str(plan_file), (old_time, old_time))

            large_content = "x = 1\n" * 150
            hook_input = json.dumps({
                "tool_name": "Write",
                "tool_input": {
                    "file_path": os.path.join(tmpdir, "src", "feature.py"),
                    "content": large_content,
                },
            })

            with patch("sys.stdin") as mock_stdin, \
                 patch("builtins.print") as mock_print, \
                 patch.dict(os.environ, {}, clear=False), \
                 patch("os.getcwd", return_value=tmpdir):
                os.environ.pop("SKIP_PLAN_CHECK", None)
                mock_stdin.read.return_value = hook_input

                plan_gate.main()

                json_calls = [
                    c for c in mock_print.call_args_list
                    if c.args and isinstance(c.args[0], str)
                    and not c.kwargs.get("file")
                ]
                output = json.loads(json_calls[0].args[0])
                decision = output["hookSpecificOutput"]["permissionDecision"]
                assert decision == "allow", \
                    f"Expired but valid plan should allow, got: {decision}"


# ---------------------------------------------------------------------------
# AC12: /plan-to-issues detects .claude/plans/ files
# ---------------------------------------------------------------------------


class TestSpec814AC12PlanToIssuesIntegration:
    """/plan-to-issues must detect .claude/plans/ files."""

    def test_spec_814_12_plan_to_issues_references_plans_dir(self):
        """plan-to-issues.md must reference .claude/plans/ directory."""
        plan_to_issues = COMMANDS_DIR / "plan-to-issues.md"
        content = plan_to_issues.read_text()
        assert ".claude/plans/" in content, \
            "plan-to-issues.md must reference .claude/plans/ directory"

    def test_spec_814_12_plan_to_issues_checks_for_plan_files(self):
        """plan-to-issues.md must include a step to check for plan files."""
        plan_to_issues = COMMANDS_DIR / "plan-to-issues.md"
        content = plan_to_issues.read_text()
        # Should have a step that looks for plan files
        assert "plan files" in content.lower() or "plan file" in content.lower(), \
            "plan-to-issues.md must include logic to detect plan files"


# ---------------------------------------------------------------------------
# AC13: Hook registered in settings templates and install manifest
# ---------------------------------------------------------------------------


class TestSpec814AC13HookRegistration:
    """plan_gate hook must be registered in settings and manifest."""

    def test_spec_814_13_hook_in_settings_template(self):
        """plan_gate must be referenced in global_settings_template.json."""
        template = CONFIG_DIR / "global_settings_template.json"
        content = template.read_text()
        assert "plan_gate" in content, \
            "plan_gate must be registered in global_settings_template.json"

    def test_spec_814_13_hook_in_install_manifest(self):
        """plan_gate must be listed in install_manifest.json."""
        manifest = CONFIG_DIR / "install_manifest.json"
        content = manifest.read_text()
        assert "plan_gate" in content, \
            "plan_gate must be listed in install_manifest.json"

    def test_spec_814_13_hook_json_sidecar_exists(self):
        """plan_gate.hook.json sidecar file must exist."""
        hook_json = HOOKS_DIR / "plan_gate.hook.json"
        assert hook_json.exists(), f"plan_gate.hook.json not found at {hook_json}"


# ---------------------------------------------------------------------------
# AC14: docs/PLANNING-WORKFLOW.md exists
# ---------------------------------------------------------------------------


class TestSpec814AC14DocsExist:
    """Documentation file must exist."""

    def test_spec_814_14_planning_workflow_docs_exist(self):
        """docs/PLANNING-WORKFLOW.md must exist."""
        doc_file = DOCS_DIR / "PLANNING-WORKFLOW.md"
        assert doc_file.exists(), f"docs/PLANNING-WORKFLOW.md not found at {doc_file}"


# ---------------------------------------------------------------------------
# AC-extra: planning-workflow SKILL.md exists
# ---------------------------------------------------------------------------


class TestSpec814SkillExists:
    """planning-workflow skill must exist."""

    def test_spec_814_skill_file_exists(self):
        """planning-workflow/SKILL.md must exist."""
        skill_file = SKILLS_DIR / "planning-workflow" / "SKILL.md"
        assert skill_file.exists(), f"planning-workflow SKILL.md not found at {skill_file}"

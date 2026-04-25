"""Spec-validation tests for issue #950: /health-check hook path validation.

These tests are written from the acceptance criteria ONLY:

    1. /health-check detects: missing scripts, non-executable shells,
       global+local duplicates, unresolved env vars.
    2. Output is actionable: each issue prints the file/line and a suggested
       fix command.
    3. CI fixture: /health-check exits 1 in test repo with a deliberately
       broken hook.

The tests are intentionally blind to implementation details. They invoke the
public CLI / public function and verify observable behaviour.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

# Make the lib importable. We reach in via PYTHONPATH only — we do not import
# any implementer-private symbols.
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_path_validator  # noqa: E402  (public module under test)

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "health_check"
HEALTH_CHECK_CMD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "health-check.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_settings(path: Path, command: str) -> None:
    """Write a minimal settings file with one PreToolUse hook command."""
    payload = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": command, "timeout": 5},
                    ],
                }
            ]
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _format(issues) -> str:
    return hook_path_validator.format_findings(issues)


# ---------------------------------------------------------------------------
# Criterion 1a — missing scripts
# ---------------------------------------------------------------------------


class TestSpecIssue950Criterion1aMissingScripts:
    """AC1a: /health-check MUST detect missing scripts."""

    def test_spec_issue950_1a_missing_script_is_reported(self, tmp_path: Path) -> None:
        settings = tmp_path / ".claude" / "settings.local.json"
        _write_settings(
            settings,
            f"python3 {tmp_path}/does_not_exist_spec950.py",
        )

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=None,
            local_settings_path=settings,
            project_root=tmp_path,
        )

        # At least one error finding must be emitted, and it must reference
        # the missing script path.
        errors = [i for i in issues if i.severity == "error"]
        assert errors, f"Expected an error for missing script, got: {issues}"
        assert any(
            "does_not_exist_spec950.py" in (i.message or "") for i in errors
        ), f"Missing-script finding does not mention the script path: {errors}"


# ---------------------------------------------------------------------------
# Criterion 1b — non-executable shells
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="POSIX exec-bit semantics only")
class TestSpecIssue950Criterion1bNonExecutableShells:
    """AC1b: /health-check MUST detect non-executable shell scripts."""

    def test_spec_issue950_1b_shell_script_without_exec_bit_is_reported(
        self, tmp_path: Path
    ) -> None:
        # Create a real .sh file but withhold the execute bit.
        shell_script = tmp_path / "not_exec.sh"
        shell_script.write_text("#!/bin/bash\necho hi\n", encoding="utf-8")
        shell_script.chmod(0o644)  # no exec bit

        settings = tmp_path / ".claude" / "settings.local.json"
        _write_settings(settings, f"bash {shell_script}")

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=None,
            local_settings_path=settings,
            project_root=tmp_path,
        )

        # Sanity: the script does exist, so the only issue should be exec-bit.
        assert shell_script.is_file()
        errors = [i for i in issues if i.severity == "error"]
        assert errors, f"Expected an error for non-executable shell, got: {issues}"
        assert any(
            "executable" in (i.message or "").lower()
            and "not_exec.sh" in (i.message or "")
            for i in errors
        ), f"Did not surface non-executable shell finding: {errors}"

    def test_spec_issue950_1b_shell_script_with_exec_bit_passes(
        self, tmp_path: Path
    ) -> None:
        shell_script = tmp_path / "ok.sh"
        shell_script.write_text("#!/bin/bash\necho hi\n", encoding="utf-8")
        shell_script.chmod(0o755)

        settings = tmp_path / ".claude" / "settings.local.json"
        _write_settings(settings, f"bash {shell_script}")

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=None,
            local_settings_path=settings,
            project_root=tmp_path,
        )
        errors = [i for i in issues if i.severity == "error"]
        assert not errors, f"Executable shell should not error: {errors}"


# ---------------------------------------------------------------------------
# Criterion 1c — global+local duplicates
# ---------------------------------------------------------------------------


class TestSpecIssue950Criterion1cGlobalLocalDuplicates:
    """AC1c: /health-check MUST detect duplicate registrations across scopes."""

    def test_spec_issue950_1c_same_command_in_global_and_local_is_reported(
        self, tmp_path: Path
    ) -> None:
        # Build a real script that exists, executable, no exec-bit issues.
        script = tmp_path / "dup_target.py"
        script.write_text("# dup target\n", encoding="utf-8")

        global_settings = tmp_path / "global" / "settings.json"
        local_settings = tmp_path / "local" / "settings.local.json"
        cmd = f"python3 {script}"
        _write_settings(global_settings, cmd)
        _write_settings(local_settings, cmd)

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=global_settings,
            local_settings_path=local_settings,
            project_root=tmp_path,
        )

        dup_findings = [
            i for i in issues if "both" in (i.message or "").lower()
            or "duplicat" in (i.message or "").lower()
            or "twice" in (i.message or "").lower()
        ]
        assert dup_findings, (
            f"Expected a duplicate-registration finding, got: {issues}"
        )

    def test_spec_issue950_1c_unique_registrations_emit_no_duplicate_finding(
        self, tmp_path: Path
    ) -> None:
        script_a = tmp_path / "a.py"
        script_b = tmp_path / "b.py"
        script_a.write_text("# a\n", encoding="utf-8")
        script_b.write_text("# b\n", encoding="utf-8")

        global_settings = tmp_path / "global" / "settings.json"
        local_settings = tmp_path / "local" / "settings.local.json"
        _write_settings(global_settings, f"python3 {script_a}")
        _write_settings(local_settings, f"python3 {script_b}")

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=global_settings,
            local_settings_path=local_settings,
            project_root=tmp_path,
        )
        dup_findings = [
            i for i in issues if "both" in (i.message or "").lower()
            or "duplicat" in (i.message or "").lower()
            or "twice" in (i.message or "").lower()
        ]
        assert not dup_findings, (
            f"Expected no duplicate finding for distinct paths, got: {dup_findings}"
        )


# ---------------------------------------------------------------------------
# Criterion 1d — unresolved env vars
# ---------------------------------------------------------------------------


class TestSpecIssue950Criterion1dUnresolvedEnvVars:
    """AC1d: /health-check MUST detect unresolved environment variables."""

    def test_spec_issue950_1d_undefined_env_var_is_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Make absolutely sure the var is not defined in the test env.
        monkeypatch.delenv("THIS_VAR_IS_NOT_SET_950", raising=False)

        settings = tmp_path / ".claude" / "settings.local.json"
        _write_settings(
            settings,
            "python3 $THIS_VAR_IS_NOT_SET_950/hook.py",
        )

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=None,
            local_settings_path=settings,
            project_root=tmp_path,
        )

        env_findings = [
            i for i in issues
            if "THIS_VAR_IS_NOT_SET_950" in (i.message or "")
            and (
                "env" in (i.message or "").lower()
                or "variable" in (i.message or "").lower()
                or "unresolved" in (i.message or "").lower()
            )
        ]
        assert env_findings, (
            f"Expected an unresolved env-var finding for "
            f"$THIS_VAR_IS_NOT_SET_950, got: {issues}"
        )


# ---------------------------------------------------------------------------
# Criterion 2 — actionable output: file/line + suggested fix
# ---------------------------------------------------------------------------


class TestSpecIssue950Criterion2ActionableOutput:
    """AC2: each issue prints the file/line and a suggested fix command."""

    def test_spec_issue950_2a_findings_include_file_path(self, tmp_path: Path) -> None:
        settings = tmp_path / ".claude" / "settings.local.json"
        _write_settings(settings, f"python3 {tmp_path}/missing_950.py")

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=None,
            local_settings_path=settings,
            project_root=tmp_path,
        )

        assert issues, "Expected at least one finding"
        # Every error finding must carry the offending settings file path.
        errors = [i for i in issues if i.severity == "error"]
        assert errors
        for issue in errors:
            assert issue.file_path, (
                f"Finding must include a file_path, got: {issue}"
            )
            assert "settings" in issue.file_path.lower() or str(settings) == issue.file_path, (
                f"Finding file_path should reference the settings file, got: "
                f"{issue.file_path}"
            )

    def test_spec_issue950_2a_findings_include_line_number(
        self, tmp_path: Path
    ) -> None:
        settings = tmp_path / ".claude" / "settings.local.json"
        _write_settings(settings, f"python3 {tmp_path}/missing_950.py")

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=None,
            local_settings_path=settings,
            project_root=tmp_path,
        )
        errors = [i for i in issues if i.severity == "error"]
        assert errors
        # Spec says "file/line" — at least one error finding MUST have a
        # positive line number pointing into the settings file.
        assert any(
            (i.line_number or 0) > 0 for i in errors
        ), f"No error finding includes a line number: {errors}"

    def test_spec_issue950_2b_findings_include_suggested_fix_command(
        self, tmp_path: Path
    ) -> None:
        settings = tmp_path / ".claude" / "settings.local.json"
        _write_settings(settings, f"python3 {tmp_path}/missing_950.py")

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=None,
            local_settings_path=settings,
            project_root=tmp_path,
        )
        errors = [i for i in issues if i.severity == "error"]
        assert errors
        # Spec says "suggested fix command" — every error finding must carry
        # a non-empty fix_action.
        for issue in errors:
            assert issue.fix_action and issue.fix_action.strip(), (
                f"Finding must include a suggested fix command, got: {issue}"
            )

    def test_spec_issue950_2b_formatted_output_renders_file_line_and_fix(
        self, tmp_path: Path
    ) -> None:
        settings = tmp_path / ".claude" / "settings.local.json"
        _write_settings(settings, f"python3 {tmp_path}/missing_950.py")

        issues = hook_path_validator.validate_hook_paths(
            global_settings_path=None,
            local_settings_path=settings,
            project_root=tmp_path,
        )
        rendered = _format(issues)

        # File path is visible.
        assert str(settings) in rendered, (
            f"Rendered output must contain the settings file path. "
            f"Got:\n{rendered}"
        )
        # A line marker (":NN") is visible.
        assert any(
            f"{settings}:{n}" in rendered for n in range(1, 100)
        ), f"Rendered output must include settings_path:line. Got:\n{rendered}"
        # A suggested-fix line is rendered.
        assert "Suggested fix:" in rendered or "fix" in rendered.lower(), (
            f"Rendered output must surface a suggested fix. Got:\n{rendered}"
        )


# ---------------------------------------------------------------------------
# Criterion 3 — CI fixture exit codes
# ---------------------------------------------------------------------------


class TestSpecIssue950Criterion3CIFixtureExitCode:
    """AC3: /health-check exits 1 with a deliberately broken fixture, 0 clean."""

    def test_spec_issue950_3_broken_fixture_file_exists(self) -> None:
        # The spec literally requires a CI fixture be present.
        broken = FIXTURE_DIR / "broken_settings.json"
        assert broken.is_file(), (
            f"Spec requires a broken fixture at {broken}; not found"
        )
        # And it must be parseable JSON containing at least one hook command.
        data = json.loads(broken.read_text(encoding="utf-8"))
        assert "hooks" in data and isinstance(data["hooks"], dict)

    def test_spec_issue950_3_validator_cli_exits_1_for_broken_fixture(
        self, tmp_path: Path
    ) -> None:
        broken = FIXTURE_DIR / "broken_settings.json"
        # Run the hook_path_validator CLI directly. We avoid pulling in the
        # global ~/.claude/settings.json by pointing it at /dev/null-equivalent
        # (a non-existent path is silently skipped by the validator per its
        # public contract).
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{LIB_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "hook_path_validator",
                "--global-settings",
                str(tmp_path / "no_such_global.json"),
                "--local-settings",
                str(broken),
                "--project-root",
                str(tmp_path),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for broken fixture, got {result.returncode}.\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )

    def test_spec_issue950_3_validator_cli_exits_0_for_clean_fixture(
        self, tmp_path: Path
    ) -> None:
        # Build a clean settings file in tmp pointing at a real, executable
        # script. We can't rely on the in-repo clean fixture pointing to
        # auto_format.py because the environment here may not have
        # CLAUDE_PROJECT_DIR set; build our own minimal clean case.
        script = tmp_path / "clean_hook.py"
        script.write_text("# noop hook\n", encoding="utf-8")

        clean_settings = tmp_path / ".claude" / "settings.local.json"
        _write_settings(clean_settings, f"python3 {script}")

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{LIB_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "hook_path_validator",
                "--global-settings",
                str(tmp_path / "no_such_global.json"),
                "--local-settings",
                str(clean_settings),
                "--project-root",
                str(tmp_path),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 for clean settings, got {result.returncode}.\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )

    def test_spec_issue950_3_health_check_command_invokes_hook_validator(
        self,
    ) -> None:
        """The /health-check command file must wire in hook path validation.

        Spec AC3 references `/health-check` exiting 1 — therefore the command
        body must actually invoke the hook validator. We check this by
        scanning the command file for a reference (any of: module name, CLI
        flags, or import path).
        """
        body = HEALTH_CHECK_CMD.read_text(encoding="utf-8")
        assert (
            "hook_path_validator" in body
            or "validate_hook_paths" in body
        ), (
            "/health-check command file must invoke hook path validation; "
            "no reference found"
        )

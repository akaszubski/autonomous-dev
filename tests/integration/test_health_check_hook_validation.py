"""Integration tests for /health-check hook path validation.

Validates the CLI surface and that ``commands/health-check.md`` invokes the
new validator with the correct path-resolution pattern.

Issue: #950 - /health-check validates every hook command path in settings.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "health_check"
HEALTH_CHECK_MD = (
    PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "health-check.md"
)


def _run_validator(
    *,
    global_settings: Path | None,
    local_settings: Path | None,
    project_root: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the validator CLI as a subprocess and return its result."""
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        f"{LIB_PATH}{os.pathsep}{env.get('PYTHONPATH', '')}"
    )
    if extra_env:
        env.update(extra_env)

    cmd = [sys.executable, "-m", "hook_path_validator"]
    if global_settings is not None:
        cmd += ["--global-settings", str(global_settings)]
    else:
        # Force a non-existent path so we don't read the real ~/.claude/settings.json.
        cmd += ["--global-settings", str(project_root / "_no_global.json")]
    if local_settings is not None:
        cmd += ["--local-settings", str(local_settings)]
    cmd += ["--project-root", str(project_root)]

    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_exits_1_with_broken_hook_fixture(tmp_path):
    """The CLI exits 1 with helpful output when a hook script is missing."""
    fixture = FIXTURE_DIR / "broken_settings.json"
    assert fixture.is_file(), f"Fixture missing: {fixture}"

    result = _run_validator(
        global_settings=None,
        local_settings=fixture,
        project_root=tmp_path,
    )

    assert result.returncode == 1, (
        f"Expected exit 1, got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    output = result.stdout + result.stderr
    # The missing-script name MUST appear in the output.
    assert "this_hook_does_not_exist_950.py" in output
    # The user-facing remediation hint MUST appear.
    assert "Suggested fix" in output


def test_cli_exits_0_with_clean_fixture(tmp_path):
    """The CLI exits 0 when all referenced hook scripts resolve."""
    fixture = FIXTURE_DIR / "clean_settings.json"
    assert fixture.is_file(), f"Fixture missing: {fixture}"

    # The fixture references $CLAUDE_PROJECT_DIR/plugins/autonomous-dev/hooks/auto_format.py
    # so we must point project-root at the real repo where that file exists.
    auto_format = (
        PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks" / "auto_format.py"
    )
    assert auto_format.is_file(), (
        f"Expected real hook file at {auto_format} for clean fixture"
    )

    result = _run_validator(
        global_settings=None,
        local_settings=fixture,
        project_root=PROJECT_ROOT,
    )

    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_health_check_md_invokes_hook_validator():
    """commands/health-check.md MUST invoke hook_path_validator with CLAUDE_PROJECT_DIR.

    Regression guard against the broken ``$(dirname "$0")/../scripts/...``
    pattern noted in the plan-critic feedback for Issue #950.
    """
    assert HEALTH_CHECK_MD.is_file(), f"Missing: {HEALTH_CHECK_MD}"
    text = HEALTH_CHECK_MD.read_text(encoding="utf-8")

    # The new validator MUST be invoked.
    assert "hook_path_validator" in text, (
        "commands/health-check.md must invoke hook_path_validator"
    )

    # Path resolution MUST go through CLAUDE_PROJECT_DIR or git rev-parse,
    # NOT the legacy `$(dirname "$0")/../scripts/...` form.
    assert "CLAUDE_PROJECT_DIR" in text, (
        "commands/health-check.md must use CLAUDE_PROJECT_DIR for path resolution"
    )

    # Explicit regression guard: the broken legacy invocation must be gone.
    assert '$(dirname "$0")/../scripts/validate_structure.py' not in text, (
        "commands/health-check.md still uses the broken `$(dirname \"$0\")` "
        "path pattern. Replace with absolute-path resolution."
    )


def test_cli_json_output_is_valid_json(tmp_path):
    """``--json`` mode emits parseable JSON with the documented schema."""
    fixture = FIXTURE_DIR / "broken_settings.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{LIB_PATH}{os.pathsep}{env.get('PYTHONPATH', '')}"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hook_path_validator",
            "--global-settings",
            str(tmp_path / "_no_global.json"),
            "--local-settings",
            str(fixture),
            "--project-root",
            str(tmp_path),
            "--json",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "issues" in payload
    assert "error_count" in payload
    assert payload["error_count"] >= 1
    assert any(
        "this_hook_does_not_exist_950.py" in i["message"] for i in payload["issues"]
    )

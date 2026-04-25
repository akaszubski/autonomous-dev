"""Unit tests for hook_path_validator.

Issue: #950 - /health-check validates every hook command path in settings.json
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

# Add lib to path for imports
LIB_PATH = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "autonomous-dev"
    / "lib"
)
sys.path.insert(0, str(LIB_PATH))

from hook_path_validator import (  # noqa: E402
    expand_path,
    extract_script_path,
    main,
    parse_hook_command,
    safe_resolve,
    validate_hook_paths,
)


# ---------------------------------------------------------------------------
# parse_hook_command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command,expected_env,expected_tokens",
    [
        # No env prefix
        (
            "python3 /tmp/foo.py",
            {},
            ["python3", "/tmp/foo.py"],
        ),
        # Single env prefix
        (
            "FOO=bar python3 /tmp/foo.py",
            {"FOO": "bar"},
            ["python3", "/tmp/foo.py"],
        ),
        # Multiple env prefixes
        (
            "FOO=bar BAZ=qux python3 /tmp/foo.py",
            {"FOO": "bar", "BAZ": "qux"},
            ["python3", "/tmp/foo.py"],
        ),
        # No script — only env
        (
            "FOO=bar",
            {"FOO": "bar"},
            [],
        ),
        # Empty
        ("", {}, []),
    ],
)
def test_parse_hook_command_strips_env_prefix(command, expected_env, expected_tokens):
    """Env-style ``VAR=value`` prefixes are stripped and returned separately."""
    env, tokens = parse_hook_command(command)
    assert env == expected_env
    assert tokens == expected_tokens


def test_parse_hook_command_handles_unbalanced_quotes():
    """Unbalanced quotes return empty tuples (caller surfaces parse failure)."""
    env, tokens = parse_hook_command('python3 "/tmp/foo.py')
    assert env == {}
    assert tokens == []


# ---------------------------------------------------------------------------
# extract_script_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tokens,expected",
    [
        # python3 with flags then script
        (["python3", "-u", "/tmp/foo.py"], "/tmp/foo.py"),
        # python3 direct
        (["python3", "/tmp/foo.py"], "/tmp/foo.py"),
        # bash with shell script
        (["bash", "/tmp/foo.sh"], "/tmp/foo.sh"),
        # Direct script invocation (no interpreter)
        (["/usr/local/bin/foo.py"], "/usr/local/bin/foo.py"),
        # No script-like token, no flags — return first non-flag (binary call)
        (["/usr/bin/true"], "/usr/bin/true"),
        # Empty
        ([], None),
        # All flags — None
        (["-h", "--help"], None),
    ],
)
def test_extract_script_path_picks_first_py_or_sh(tokens, expected):
    """The first script-like or non-flag token is returned."""
    assert extract_script_path(tokens) == expected


# ---------------------------------------------------------------------------
# expand_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected_suffix,expected_unresolved",
    [
        # CLAUDE_PROJECT_DIR substitution (no braces)
        ("$CLAUDE_PROJECT_DIR/hooks/foo.py", "/hooks/foo.py", []),
        # CLAUDE_PROJECT_DIR substitution (braces)
        ("${CLAUDE_PROJECT_DIR}/hooks/foo.py", "/hooks/foo.py", []),
        # CLAUDE_PLUGIN_ROOT substitution
        (
            "${CLAUDE_PLUGIN_ROOT}/hooks/foo.py",
            "/plugins/autonomous-dev/hooks/foo.py",
            [],
        ),
        # Unresolved env var → flagged
        ("$UNDEFINED_VAR_950/foo.py", "/foo.py", ["UNDEFINED_VAR_950"]),
    ],
)
def test_expand_path_substitutes_special_vars(
    raw, expected_suffix, expected_unresolved, monkeypatch
):
    """``$CLAUDE_PROJECT_DIR``, ``${CLAUDE_PLUGIN_ROOT}``, ``~`` are expanded."""
    # Make sure the unresolved test name is NOT in the env.
    monkeypatch.delenv("UNDEFINED_VAR_950", raising=False)
    project_root = Path("/proj")
    path, unresolved = expand_path(raw, project_root)
    assert str(path).endswith(expected_suffix), f"Got: {path}"
    assert unresolved == expected_unresolved


def test_expand_path_handles_home_tilde(monkeypatch, tmp_path):
    """``~`` is expanded via os.path.expanduser."""
    monkeypatch.setenv("HOME", str(tmp_path))
    path, unresolved = expand_path("~/.claude/hooks/foo.py", Path("/proj"))
    assert str(path).startswith(str(tmp_path))
    assert unresolved == []


# ---------------------------------------------------------------------------
# safe_resolve
# ---------------------------------------------------------------------------


def test_safe_resolve_rejects_pre_resolve_symlink(tmp_path):
    """A symlink pointing outside allowed roots is rejected before resolve()."""
    # Layout:
    #   tmp_path/allowed/   <- whitelist root
    #   tmp_path/outside/secret.py
    #   tmp_path/allowed/link.py -> tmp_path/outside/secret.py
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.py"
    secret.write_text("# pwned")
    link = allowed / "link.py"
    link.symlink_to(secret)

    canonical, err = safe_resolve(link, allowed_roots=[allowed])
    assert canonical is None
    assert err is not None
    assert "escapes" in err or "outside" in err


def test_safe_resolve_accepts_legitimate_shell(tmp_path):
    """``/bin/sh`` is accepted with empty allowed_roots (no whitelist).

    Proves we are NOT using ``security_utils.validate_path``: that function's
    whitelist would reject ``/bin/sh`` because it's outside ``.claude/``.
    """
    sh = Path("/bin/sh")
    if not sh.exists():
        pytest.skip("/bin/sh not available on this platform")
    canonical, err = safe_resolve(sh, allowed_roots=[])
    assert canonical is not None, f"safe_resolve rejected /bin/sh: {err}"
    assert err is None


# ---------------------------------------------------------------------------
# validate_hook_paths — end-to-end validation
# ---------------------------------------------------------------------------


def _write_settings(path: Path, command: str) -> None:
    """Helper: write a minimal settings file with one hook command."""
    path.parent.mkdir(parents=True, exist_ok=True)
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": command,
                            "timeout": 5,
                        }
                    ],
                }
            ]
        }
    }
    path.write_text(json.dumps(settings, indent=2))


def test_validate_detects_missing_script(tmp_path):
    """A hook command pointing to a nonexistent script emits an error."""
    settings_path = tmp_path / "local.json"
    _write_settings(
        settings_path,
        f"python3 {tmp_path}/does_not_exist_950.py",
    )

    issues = validate_hook_paths(
        global_settings_path=None,
        local_settings_path=settings_path,
        project_root=tmp_path,
    )

    errors = [i for i in issues if i.severity == "error"]
    assert errors, f"Expected at least one error issue, got {issues}"
    assert any("does not exist" in i.message for i in errors)
    assert all(i.category == "hook" for i in errors)


def test_validate_detects_non_executable_shell(tmp_path):
    """A `.sh` hook script without execute bit is flagged with chmod fix."""
    if os.name == "nt":
        pytest.skip("Executable bit semantics differ on Windows")

    script = tmp_path / "hooks" / "foo.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/bin/bash\necho hi\n")
    # Set 644 (no execute).
    script.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    settings_path = tmp_path / "local.json"
    _write_settings(settings_path, f"bash {script}")

    issues = validate_hook_paths(
        global_settings_path=None,
        local_settings_path=settings_path,
        project_root=tmp_path,
    )

    matching = [i for i in issues if "not executable" in i.message]
    assert matching, f"No 'not executable' issue in {issues}"
    issue = matching[0]
    assert issue.severity == "error"
    assert issue.fix_action is not None
    assert issue.fix_action.startswith("chmod +x ")


def test_validate_detects_unresolved_env_var(tmp_path, monkeypatch):
    """A `$UNDEFINED` reference yields an issue per unresolved variable."""
    monkeypatch.delenv("UNDEFINED_HOOK_VAR_950", raising=False)
    settings_path = tmp_path / "local.json"
    _write_settings(
        settings_path,
        "python3 $UNDEFINED_HOOK_VAR_950/hook.py",
    )

    issues = validate_hook_paths(
        global_settings_path=None,
        local_settings_path=settings_path,
        project_root=tmp_path,
    )

    matching = [i for i in issues if "UNDEFINED_HOOK_VAR_950" in i.message]
    assert matching, f"No unresolved-var issue in {issues}"
    assert matching[0].severity == "error"


def test_validate_detects_global_local_duplicates(tmp_path):
    """Same canonical hook path in global and local emits a warning."""
    # Real hook script that exists in both registrations.
    script = tmp_path / "hooks" / "foo.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# hook")

    global_path = tmp_path / "global.json"
    local_path = tmp_path / "local.json"
    _write_settings(global_path, f"python3 {script}")
    _write_settings(local_path, f"python3 {script}")

    issues = validate_hook_paths(
        global_settings_path=global_path,
        local_settings_path=local_path,
        project_root=tmp_path,
    )

    warnings = [i for i in issues if i.severity == "warning"]
    assert warnings, f"No duplicate warning in {issues}"
    assert any("registered in both" in w.message for w in warnings)


def test_validate_clean_settings_returns_no_errors(tmp_path):
    """A settings file referencing a real script produces zero error issues."""
    script = tmp_path / "hooks" / "ok.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# ok")

    settings_path = tmp_path / "local.json"
    _write_settings(settings_path, f"python3 {script}")

    issues = validate_hook_paths(
        global_settings_path=None,
        local_settings_path=settings_path,
        project_root=tmp_path,
    )

    errors = [i for i in issues if i.severity == "error"]
    assert errors == [], f"Unexpected errors on clean settings: {errors}"


# ---------------------------------------------------------------------------
# main() exit codes
# ---------------------------------------------------------------------------


def test_main_exit_code_one_on_error(tmp_path, capsys):
    """``main()`` returns 1 when at least one error issue is detected."""
    settings_path = tmp_path / "local.json"
    _write_settings(
        settings_path,
        f"python3 {tmp_path}/missing_950.py",
    )

    rc = main(
        argv=[
            "--global-settings",
            str(tmp_path / "nonexistent_global.json"),
            "--local-settings",
            str(settings_path),
            "--project-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1, f"Expected exit 1 on broken settings; output: {captured.out}"
    assert "does not exist" in captured.out


def test_main_exit_code_zero_on_clean(tmp_path, capsys):
    """``main()`` returns 0 when settings are clean."""
    script = tmp_path / "hooks" / "ok.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# ok")

    settings_path = tmp_path / "local.json"
    _write_settings(settings_path, f"python3 {script}")

    rc = main(
        argv=[
            "--global-settings",
            str(tmp_path / "nonexistent_global.json"),
            "--local-settings",
            str(settings_path),
            "--project-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0, f"Expected exit 0 on clean settings; output: {captured.out}"

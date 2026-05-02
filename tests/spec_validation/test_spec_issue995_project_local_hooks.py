"""Spec-blind validation tests for Issue #995 (Phase A: project-local hooks default).

These tests are written from acceptance criteria ONLY, without seeing the
implementation diffs or the implementer's tests. They verify the observable
behavioral contract:

1. ``bash scripts/deploy-all.sh`` does NOT modify ``~/.claude/settings.json``.
2. ``bash scripts/deploy-all.sh --global-settings`` (opt-in) DOES register
   hooks globally (legacy behavior).
3. ``bash install.sh`` does NOT register hooks globally by default.
4. After running the documented migration one-liner,
   ``~/.claude/settings.json`` has no ``hooks`` key.
5. Per-repo ``<repo>/.claude/settings.json`` continues to register hooks for
   the autonomous-dev project (autonomous-dev unaffected).
6. (Manual-only) Foreign repo gets zero autonomous-dev hook entries — skipped.
7. A unit/integration test exists that loads the deploy script in dry-run mode
   and asserts global settings are NOT modified by default.
8. CHANGELOG entry documents the breaking change + migration command.

All tests use absolute paths and a sandboxed ``$HOME`` (via ``monkeypatch``)
so they NEVER touch the user's real ``~/.claude/settings.json``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

# tests/spec_validation/test_spec_issue995_project_local_hooks.py
#   parents[0] = spec_validation/
#   parents[1] = tests/
#   parents[2] = repo root (worktree)
REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy-all.sh"
INSTALL_SCRIPT = REPO_ROOT / "install.sh"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
REPO_SETTINGS = REPO_ROOT / ".claude" / "settings.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_deploy_dry_run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run deploy-all.sh with --dry-run and the given args.

    --dry-run is mandatory for these tests so we never actually rsync anything
    to the live ~/.claude/. We are testing what the script REPORTS it would do.
    """
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", str(DEPLOY_SCRIPT), *args],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        timeout=60,
        env=full_env,
    )


# ---------------------------------------------------------------------------
# AC #1: deploy-all.sh (default) does NOT modify ~/.claude/settings.json
# ---------------------------------------------------------------------------


def test_spec_issue995_1_deploy_default_does_not_modify_global_settings(tmp_path):
    """AC #1: ``bash scripts/deploy-all.sh`` (default) must not touch
    ~/.claude/settings.json.

    Strategy:
      1. Create a sandbox HOME with a pre-existing ~/.claude/settings.json
         containing a known marker key. No 'hooks' key.
      2. Run deploy-all.sh in dry-run mode (must not rsync) AND assert the
         dry-run output explicitly says it will SKIP global settings sync.
      3. Confirm the sandbox settings.json file is byte-identical (untouched).
    """
    assert DEPLOY_SCRIPT.exists(), f"deploy-all.sh missing at {DEPLOY_SCRIPT}"

    sandbox_home = tmp_path / "home"
    claude_dir = sandbox_home / ".claude"
    claude_dir.mkdir(parents=True)
    settings_path = claude_dir / "settings.json"
    pre_state = {"permissions": {"allow": ["Read"]}, "marker": "spec-issue-995-test"}
    settings_path.write_text(json.dumps(pre_state, indent=2))
    pre_bytes = settings_path.read_bytes()

    # Run deploy in dry-run mode with sandboxed HOME. Use --local so we don't
    # try ssh, and --dry-run so we don't rsync anything anywhere.
    result = _run_deploy_dry_run("--local", "--dry-run", env={"HOME": str(sandbox_home)})
    assert result.returncode == 0, (
        f"deploy-all.sh exited non-zero in default dry-run mode\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # The dry-run must announce that global settings.json hooks are SKIPPED.
    assert "Would skip global settings.json hooks" in result.stdout, (
        "Default mode must announce skipping global settings.json hooks. "
        f"stdout:\n{result.stdout}"
    )
    # And it must NOT announce a sync of those hooks.
    assert "Would sync global settings.json hooks" not in result.stdout, (
        "Default mode must NOT announce syncing global settings.json hooks. "
        f"stdout:\n{result.stdout}"
    )

    # Sandbox settings.json must be byte-identical (proving zero modification).
    assert settings_path.read_bytes() == pre_bytes, (
        "Default deploy-all.sh dry-run modified the sandbox ~/.claude/settings.json"
    )


# ---------------------------------------------------------------------------
# AC #2: deploy-all.sh --global-settings DOES register globally (legacy path)
# ---------------------------------------------------------------------------


def test_spec_issue995_2_deploy_global_settings_flag_enables_sync(tmp_path):
    """AC #2: ``--global-settings`` opts in to legacy hook registration.

    Strategy: in dry-run, the script must announce that it WOULD sync global
    settings.json hooks when ``--global-settings`` is passed.
    """
    assert DEPLOY_SCRIPT.exists(), f"deploy-all.sh missing at {DEPLOY_SCRIPT}"

    sandbox_home = tmp_path / "home"
    (sandbox_home / ".claude").mkdir(parents=True)

    result = _run_deploy_dry_run(
        "--local",
        "--global-settings",
        "--dry-run",
        env={"HOME": str(sandbox_home)},
    )
    assert result.returncode == 0, (
        f"deploy-all.sh exited non-zero with --global-settings\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    assert "Would sync global settings.json hooks" in result.stdout, (
        "--global-settings must announce syncing global settings.json hooks. "
        f"stdout:\n{result.stdout}"
    )
    # And must NOT also announce skipping.
    assert "Would skip global settings.json hooks" not in result.stdout, (
        "--global-settings must not announce skipping. "
        f"stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# AC #3: install.sh does NOT register hooks globally by default
# ---------------------------------------------------------------------------


def test_spec_issue995_3_install_default_skips_global_settings_registration():
    """AC #3: install.sh by default must NOT call configure_global_settings().

    Strategy (static): inspect install.sh source. The default code path that
    runs configure_global_settings() must be gated behind ``$GLOBAL_SETTINGS``,
    and the GLOBAL_SETTINGS variable must default to false.
    """
    assert INSTALL_SCRIPT.exists(), f"install.sh missing at {INSTALL_SCRIPT}"
    text = INSTALL_SCRIPT.read_text()

    # The flag must exist, default to false, and gate configure_global_settings.
    assert re.search(r"GLOBAL_SETTINGS=false", text), (
        "install.sh GLOBAL_SETTINGS must default to false (Issue #995 AC #3)"
    )
    assert "--global-settings)" in text, (
        "install.sh must declare a --global-settings case branch"
    )
    # configure_global_settings() must be guarded by $GLOBAL_SETTINGS — it
    # cannot run unconditionally any more.
    assert re.search(
        r"if\s+\$GLOBAL_SETTINGS;\s*then\s*\n\s*if\s+configure_global_settings",
        text,
    ), (
        "install.sh must gate configure_global_settings behind "
        "`if $GLOBAL_SETTINGS; then` (Issue #995 AC #3)"
    )


# ---------------------------------------------------------------------------
# AC #4: After migration one-liner, ~/.claude/settings.json has no `hooks` key
# ---------------------------------------------------------------------------


def test_spec_issue995_4_migration_oneliner_strips_hooks_key(tmp_path):
    """AC #4: Documented migration one-liner removes the 'hooks' key.

    Strategy:
      1. Extract the documented one-liner from the CHANGELOG (must exist
         there per AC #8).
      2. Build a sandbox ~/.claude/settings.json with a 'hooks' key.
      3. Run the one-liner under HOME=<sandbox>.
      4. Assert sandbox settings.json no longer has 'hooks' but DOES still
         have other keys (we should not nuke unrelated config).
      5. Assert a backup file ``settings.json.preglobal-hooks-strip`` exists
         (since the documented one-liner copies first).
    """
    changelog_text = CHANGELOG.read_text()

    # Find the python3 -c line in the CHANGELOG.
    py_match = re.search(
        r"python3 -c \"([^\"]*?d\.pop\(['\"]hooks['\"][^\"]*?)\"",
        changelog_text,
    )
    assert py_match, (
        "CHANGELOG must contain a python3 one-liner that pops the 'hooks' key. "
        "Expected pattern around `d.pop('hooks',None)`."
    )
    python_oneliner = py_match.group(1)

    # The CHANGELOG must also document the cp backup line.
    cp_match = re.search(
        r"cp\s+~/\.claude/settings\.json\s+~/\.claude/settings\.json\.preglobal-hooks-strip",
        changelog_text,
    )
    assert cp_match, (
        "CHANGELOG must document the cp backup step before the python one-liner."
    )

    # Build sandbox.
    sandbox_home = tmp_path / "home"
    claude_dir = sandbox_home / ".claude"
    claude_dir.mkdir(parents=True)
    settings_path = claude_dir / "settings.json"
    pre_state = {
        "permissions": {"allow": ["Read"]},
        "hooks": {
            "PreToolUse": [
                {"matcher": "*", "hooks": [{"type": "command", "command": "echo hi"}]}
            ]
        },
        "model": "claude-opus-4-7",
    }
    settings_path.write_text(json.dumps(pre_state, indent=2))

    # Run the cp backup, then the python one-liner, with HOME=sandbox.
    env = os.environ.copy()
    env["HOME"] = str(sandbox_home)

    cp_result = subprocess.run(
        ["bash", "-c", "cp ~/.claude/settings.json ~/.claude/settings.json.preglobal-hooks-strip"],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert cp_result.returncode == 0, f"cp backup step failed: {cp_result.stderr}"

    py_result = subprocess.run(
        ["python3", "-c", python_oneliner],
        env=env,
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert py_result.returncode == 0, (
        f"Migration python one-liner failed:\n"
        f"stdout: {py_result.stdout}\nstderr: {py_result.stderr}"
    )

    # Verify post-state.
    post_state = json.loads(settings_path.read_text())
    assert "hooks" not in post_state, (
        f"Migration one-liner did not remove 'hooks' key: post={post_state}"
    )
    # Other keys must be preserved.
    assert post_state.get("permissions") == {"allow": ["Read"]}, (
        "Migration must not destroy unrelated keys"
    )
    assert post_state.get("model") == "claude-opus-4-7"

    # Backup file must exist.
    backup = claude_dir / "settings.json.preglobal-hooks-strip"
    assert backup.exists(), "cp step should produce a backup file"
    backup_state = json.loads(backup.read_text())
    assert "hooks" in backup_state, "Backup must preserve the original hooks block"


# ---------------------------------------------------------------------------
# AC #5: Per-repo <repo>/.claude/settings.json continues to register hooks
# ---------------------------------------------------------------------------


def test_spec_issue995_5_per_repo_settings_still_registers_hooks():
    """AC #5: autonomous-dev's own repo settings.json must still register hooks.

    Strategy: the worktree IS the autonomous-dev repo. Its
    ``.claude/settings.json`` must contain a non-empty 'hooks' key. This is the
    state that was confirmed pre-Issue-995 and must be preserved.
    """
    assert REPO_SETTINGS.exists(), (
        f"Per-repo settings.json must exist at {REPO_SETTINGS}"
    )
    data = json.loads(REPO_SETTINGS.read_text())
    assert "hooks" in data, (
        f"Per-repo settings.json must contain 'hooks' key (AC #5). "
        f"Found keys: {list(data.keys())}"
    )
    hooks = data["hooks"]
    assert isinstance(hooks, dict) and len(hooks) >= 1, (
        f"Per-repo hooks must be a non-empty dict. Got: {hooks!r}"
    )
    # Validate the registered events look like real lifecycle events
    # (a sanity floor — there must be at least one PreToolUse or
    # PostToolUse-style entry).
    assert any(
        e in hooks for e in ("PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop")
    ), (
        f"Per-repo hooks should register at least one core lifecycle event. "
        f"Found: {list(hooks.keys())}"
    )


# ---------------------------------------------------------------------------
# AC #6: Foreign repo gets zero hook entries -- MANUAL ONLY (skipped)
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason="AC #6 requires opening Claude Code in a foreign repo and inspecting "
    "~/.claude/logs/activity/<date>.jsonl after a real session. This is a manual "
    "verification step and cannot be reproduced in pytest."
)
def test_spec_issue995_6_foreign_repo_no_autonomous_dev_entries():
    pass


# ---------------------------------------------------------------------------
# AC #7: Test added asserting global settings NOT modified by default
# ---------------------------------------------------------------------------


def test_spec_issue995_7_test_exists_for_default_no_global_settings():
    """AC #7: a unit test must exist that loads deploy-all.sh in dry-run mode
    and asserts global settings are NOT modified by default.

    Strategy: scan ``tests/`` for a test file that:
      - invokes ``bash`` with ``deploy-all.sh`` and ``--dry-run``
      - asserts ``"Would sync global settings.json hooks" not in`` output
        (the negative assertion is the proof of "not modified by default")
    """
    test_root = REPO_ROOT / "tests"
    candidates = list(test_root.rglob("test_*.py"))
    assert candidates, "No tests found under tests/"

    matches = []
    for path in candidates:
        try:
            text = path.read_text()
        except Exception:
            continue
        # Must invoke deploy-all.sh with --dry-run.
        if "deploy-all.sh" not in text:
            continue
        if "--dry-run" not in text:
            continue
        # Must contain a negative assertion against the sync line OR a positive
        # assertion against the skip line — either proves "not modified".
        has_negative = re.search(
            r"(not\s+in.*Would sync global settings\.json hooks"
            r"|Would sync global settings\.json hooks.*not\s+in)",
            text,
        )
        has_skip_assert = "Would skip global settings.json hooks" in text and "in result" in text
        if has_negative or has_skip_assert:
            matches.append(path)

    assert matches, (
        "AC #7: No test found that runs deploy-all.sh --dry-run and asserts "
        "that global settings sync is NOT performed by default. Searched "
        f"{len(candidates)} test files under {test_root}."
    )


# ---------------------------------------------------------------------------
# AC #8: CHANGELOG documents the breaking change + migration command
# ---------------------------------------------------------------------------


def test_spec_issue995_8_changelog_documents_breaking_change_and_migration():
    """AC #8: CHANGELOG entry must document the breaking change AND the
    migration one-liner.

    Strategy:
      1. CHANGELOG must reference Issue #995.
      2. CHANGELOG must mark it as a breaking change.
      3. CHANGELOG must contain the migration command (python3 -c ... d.pop('hooks').
      4. CHANGELOG must document the --global-settings opt-in flag.
    """
    assert CHANGELOG.exists(), f"CHANGELOG missing at {CHANGELOG}"
    text = CHANGELOG.read_text()

    # 1. Issue reference.
    assert re.search(r"#995", text), "CHANGELOG must reference Issue #995"

    # 2. Breaking change marker. Accept BREAKING/Breaking/breaking variants.
    breaking_markers = ["BREAKING", "Breaking change", "breaking change"]
    nearby_995_window = ""
    for m in re.finditer(r"#995", text):
        start = max(0, m.start() - 1500)
        end = min(len(text), m.end() + 1500)
        nearby_995_window += text[start:end] + "\n"
    assert any(marker in nearby_995_window for marker in breaking_markers), (
        f"CHANGELOG entry for #995 must mark this as a BREAKING change. "
        f"Looked in ±1500 char window."
    )

    # 3. Migration one-liner — python3 invocation that pops the 'hooks' key.
    assert re.search(
        r"python3\s+-c\s+\"[^\"]*d\.pop\(\s*['\"]hooks['\"]",
        text,
    ), (
        "CHANGELOG must include the documented migration python3 one-liner "
        "that pops the 'hooks' key from ~/.claude/settings.json."
    )

    # 4. Opt-in flag is documented.
    assert "--global-settings" in nearby_995_window, (
        "CHANGELOG entry for #995 must document the --global-settings opt-in flag."
    )

"""Integration tests for the --global-settings opt-in flag.

Issue #995 (Phase A): project-local hooks default. ``deploy-all.sh`` and
``install.sh`` no longer register autonomous-dev hooks in
``~/.claude/settings.json`` by default — registration is now opt-in via the
new ``--global-settings`` flag.

These tests verify:

1. ``deploy-all.sh --local --dry-run`` (default mode) does NOT sync global
   settings.json hooks and emits the opt-in hint.
2. ``deploy-all.sh --local --global-settings --dry-run`` DOES (would) sync
   global settings.json hooks.
3. Both ``deploy-all.sh`` and ``install.sh`` declare a ``--global-settings``
   case branch and a corresponding boolean variable.

Running the dry-run path is sufficient — no network or filesystem
side-effects required to assert the flag is wired correctly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# tests/integration/scripts/test_x.py -> repo root is parents[3]
#   parents[0] = scripts/
#   parents[1] = integration/
#   parents[2] = tests/
#   parents[3] = repo root (worktree)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy-all.sh"
INSTALL_SCRIPT = REPO_ROOT / "install.sh"


def _run_deploy(*args: str) -> subprocess.CompletedProcess:
    """Run deploy-all.sh from the worktree root with the given args.

    ``--dirty`` is always passed (Issue #1610). These tests exercise the REAL
    worktree, which is dirty during any development cycle, and the provenance
    gate now refuses a dirty deploy — including in ``--dry-run``, because a
    preview that hides a refusal is a lying preview. Their subject is the
    ``--global-settings`` flag, not provenance, so they opt in explicitly.

    The guard assertions live HERE rather than in the callers, so every present
    and future caller is covered by construction. Placing them in two of four
    call sites left the other two able to turn ``--dirty`` into an undetectable
    bypass without any test noticing.
    """
    result = subprocess.run(
        ["bash", str(DEPLOY_SCRIPT), "--dirty", *args],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        timeout=60,
    )
    _assert_gate_ran_and_permitted(result)
    return result


def _assert_gate_ran_and_permitted(result: subprocess.CompletedProcess) -> None:
    """The provenance gate must have RUN and PERMITTED — never been skipped.

    Without this, the ``--dirty`` injected above would be an undetectable
    bypass: the tests would pass identically whether the gate existed or not.
    """
    combined = result.stdout + result.stderr
    assert "DEPLOY-GATE" in combined, (
        "provenance gate did not run — --dirty must PERMIT, not bypass (Issue #1610)\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "REFUSED" not in combined, (
        "--dirty must permit the deploy\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_deploy_all_default_skips_global_settings_sync():
    """Default mode must not sync global settings.json hooks (Issue #995)."""
    assert DEPLOY_SCRIPT.exists(), f"deploy-all.sh not found at {DEPLOY_SCRIPT}"

    result = _run_deploy("--local", "--dry-run")

    assert result.returncode == 0, (
        f"deploy-all.sh exited non-zero in default dry-run mode\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    # In default mode the script must NOT report a settings.json sync.
    assert "Would sync global settings.json hooks" not in result.stdout, (
        "Default mode unexpectedly reported syncing global settings.json hooks.\n"
        f"stdout:\n{result.stdout}"
    )

    # The script must explicitly tell the user it skipped and how to opt in.
    assert "Would skip global settings.json hooks" in result.stdout, (
        "Default mode should announce skipping global settings.json hooks.\n"
        f"stdout:\n{result.stdout}"
    )
    assert "--global-settings" in result.stdout, (
        "Default mode should mention the --global-settings opt-in flag.\n"
        f"stdout:\n{result.stdout}"
    )


def test_deploy_all_global_settings_flag_enables_sync():
    """--global-settings must (in dry-run) report syncing global hooks."""
    assert DEPLOY_SCRIPT.exists(), f"deploy-all.sh not found at {DEPLOY_SCRIPT}"

    result = _run_deploy("--local", "--global-settings", "--dry-run")

    assert result.returncode == 0, (
        f"deploy-all.sh exited non-zero with --global-settings\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert "Would sync global settings.json hooks" in result.stdout, (
        "--global-settings should announce syncing global settings.json hooks.\n"
        f"stdout:\n{result.stdout}"
    )

    assert "Would skip global settings.json hooks" not in result.stdout, (
        "--global-settings must NOT announce skipping the sync.\n"
        f"stdout:\n{result.stdout}"
    )


def test_global_settings_flag_parsed_in_both_scripts():
    """Both deploy-all.sh and install.sh must wire the --global-settings flag.

    Static parse: the case branch and the boolean variable must both be
    present so future refactors do not silently drop the opt-in path.
    """
    assert DEPLOY_SCRIPT.exists(), f"deploy-all.sh not found at {DEPLOY_SCRIPT}"
    assert INSTALL_SCRIPT.exists(), f"install.sh not found at {INSTALL_SCRIPT}"

    deploy_text = DEPLOY_SCRIPT.read_text()
    install_text = INSTALL_SCRIPT.read_text()

    # deploy-all.sh: case branch + boolean variable.
    assert "--global-settings)" in deploy_text, (
        "deploy-all.sh missing --global-settings) case branch (Issue #995)"
    )
    assert "DO_GLOBAL_SETTINGS" in deploy_text, (
        "deploy-all.sh missing DO_GLOBAL_SETTINGS variable (Issue #995)"
    )
    # Default must be false (project-local default).
    assert "DO_GLOBAL_SETTINGS=false" in deploy_text, (
        "deploy-all.sh DO_GLOBAL_SETTINGS must default to false (Issue #995)"
    )

    # install.sh: case branch + boolean variable.
    assert "--global-settings)" in install_text, (
        "install.sh missing --global-settings) case branch (Issue #995)"
    )
    assert "GLOBAL_SETTINGS=" in install_text, (
        "install.sh missing GLOBAL_SETTINGS variable (Issue #995)"
    )
    assert "GLOBAL_SETTINGS=false" in install_text, (
        "install.sh GLOBAL_SETTINGS must default to false (Issue #995)"
    )

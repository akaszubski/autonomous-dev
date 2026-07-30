"""Regression test for Issue #1036: submodule-safe hook command paths.

Bug: Hook commands in ``templates/settings.*.json`` resolved the project root
with a bare ``$(git rev-parse --show-toplevel)``. Inside a git *submodule*,
``--show-toplevel`` returns the submodule root, which has no ``.claude/hooks/``
directory, so every hook errors with "No such file or directory".

Fix (Issue #1036): wrap the git substitution in a shell default-value
expression whose primary is the Claude-Code-set launch project root:

    ${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/.claude/hooks/<NAME>

- ``CLAUDE_PROJECT_DIR`` is set by the CLI to the launch project root, which is
  git-independent and therefore points at the superproject even inside a
  submodule checkout (submodule-immune primary).
- ``$(git rev-parse --show-toplevel)`` is only the fallback for older CLIs that
  do not export the variable; a worktree carries its own copied hooks so this
  still resolves to a working directory there.

This module verifies:
    (a) STATIC — all 5 project-local templates wrap the git substitution.
    (b) FUNCTIONAL (submodule case) — with CLAUDE_PROJECT_DIR set, the shell
        expression returns that dir regardless of cwd / git context.
    (c) FUNCTIONAL (fallback) — with CLAUDE_PROJECT_DIR unset, the expression
        returns the git toplevel under /bin/sh (proves nested-quote parsing).

Verification note (plan item d): running the full suite alongside this module
confirms test_issue_651_worktree_hook_paths.py and test_spec_996_template_paths.py
both pass on the shared #1036 canonical.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "templates"

# The 5 project-local templates that ship hook commands (global_settings_template
# and settings.local.json are intentionally excluded per the #1036 plan).
TEMPLATE_FILES = [
    "settings.autonomous-dev.json",
    "settings.default.json",
    "settings.granular-bash.json",
    "settings.permission-batching.json",
    "settings.strict-mode.json",
]

# The canonical wrapper and its bare (forbidden, unwrapped) git substitution.
WRAPPED_CANONICAL = "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"
BARE_GIT_SUBST = "$(git rev-parse --show-toplevel)"
PRIMARY_PREFIX = "${CLAUDE_PROJECT_DIR:-"

# Extract the project-root shell expression (the prefix up to /.claude/hooks/).
_DIR_EXPR_RE = re.compile(
    r"(\$\{CLAUDE_PROJECT_DIR:-\$\(git rev-parse --show-toplevel\)\})/\.claude/hooks/"
)


def _extract_hook_commands(settings: dict) -> list[str]:
    """Extract all hook command strings from a settings dict.

    Mirrors the walker used by the #651 and #996 template tests.
    """
    commands: list[str] = []
    hooks = settings.get("hooks", {})
    for _event, matchers in hooks.items():
        if not isinstance(matchers, list):
            continue
        for matcher_entry in matchers:
            for hook in matcher_entry.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd:
                    commands.append(cmd)
    return commands


def _git_based_commands(template_name: str) -> list[str]:
    """Return hook commands in a template that use git rev-parse (skip echo/~)."""
    settings = json.loads((TEMPLATES_DIR / template_name).read_text())
    out = []
    for cmd in _extract_hook_commands(settings):
        if cmd.startswith("echo") or "git rev-parse" not in cmd:
            continue
        out.append(cmd)
    return out


# ---------------------------------------------------------------------------
# (a) STATIC — every git-based hook command wraps the substitution.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("template_name", TEMPLATE_FILES)
def test_templates_wrap_git_substitution(template_name: str) -> None:
    """Every git-based hook command begins path resolution with the
    ${CLAUDE_PROJECT_DIR:- primary and contains NO bare unwrapped
    $(git rev-parse --show-toplevel)/.claude reference (Issue #1036)."""
    template_path = TEMPLATES_DIR / template_name
    assert template_path.is_file(), f"Template missing: {template_path}"

    commands = _git_based_commands(template_name)
    assert commands, (
        f"{template_name}: expected at least one git-based hook command to "
        f"validate; found none (walker or template drift?)."
    )

    missing_primary = [c for c in commands if PRIMARY_PREFIX not in c]
    assert not missing_primary, (
        f"{template_name}: git-based hook command(s) missing the "
        f"{PRIMARY_PREFIX}...}} primary (Issue #1036):\n"
        + "\n".join(f"  - {c}" for c in missing_primary)
    )

    # No BARE (unwrapped) substitution: strip all wrapped occurrences, then any
    # remaining bare "$(git rev-parse --show-toplevel)/.claude" is a violation.
    bare = []
    for c in commands:
        stripped = c.replace(WRAPPED_CANONICAL, "")
        if BARE_GIT_SUBST + "/.claude" in stripped or BARE_GIT_SUBST in stripped:
            bare.append(c)
    assert not bare, (
        f"{template_name}: bare unwrapped $(git rev-parse --show-toplevel) "
        f"found (breaks in submodules, Issue #1036):\n"
        + "\n".join(f"  - {c}" for c in bare)
    )


def test_dir_expression_extractable_from_every_template() -> None:
    """The project-root dir expression is extractable (proves the exact prefix
    ships) and is identical across all templates."""
    exprs: set[str] = set()
    for template_name in TEMPLATE_FILES:
        for cmd in _git_based_commands(template_name):
            m = _DIR_EXPR_RE.search(cmd)
            assert m is not None, (
                f"{template_name}: git-based command lacks the canonical "
                f"dir-expression prefix: {cmd!r}"
            )
            exprs.add(m.group(1))
    assert exprs == {WRAPPED_CANONICAL}, (
        f"Templates disagree on the dir expression (Issue #1036): {exprs}"
    )


# ---------------------------------------------------------------------------
# (b) FUNCTIONAL — submodule case: CLAUDE_PROJECT_DIR set wins over git context.
# ---------------------------------------------------------------------------
def test_expression_returns_project_dir_when_set(tmp_path: Path) -> None:
    """With CLAUDE_PROJECT_DIR set, the expression returns that dir regardless
    of cwd / git context — the submodule-immune behavior (Issue #1036).

    cwd is a non-git tmp dir, so if the fallback were (wrongly) evaluated it
    would error; instead POSIX ``${VAR:-default}`` skips the fallback entirely.
    """
    project_dir = tmp_path / "superproject"
    project_dir.mkdir()
    unrelated_cwd = tmp_path / "elsewhere"
    unrelated_cwd.mkdir()

    result = subprocess.run(
        ["/bin/sh", "-c", f'echo "{WRAPPED_CANONICAL}"'],
        cwd=str(unrelated_cwd),
        env={"CLAUDE_PROJECT_DIR": str(project_dir)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"sh failed: {result.stderr}"
    assert result.stdout.strip() == str(project_dir), (
        f"Expected {project_dir}, got {result.stdout.strip()!r} "
        f"(stderr: {result.stderr!r})"
    )


# ---------------------------------------------------------------------------
# (c) FUNCTIONAL — fallback: CLAUDE_PROJECT_DIR unset -> git toplevel.
# ---------------------------------------------------------------------------
def test_expression_falls_back_to_git_toplevel_when_unset(tmp_path: Path) -> None:
    """With CLAUDE_PROJECT_DIR unset and cwd inside a git repo, the expression
    resolves to the git toplevel — proving nested-quote parsing and the
    worktree/normal fallback path (Issue #1036)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q"], cwd=str(repo), capture_output=True, text=True, timeout=10
    )

    # Ground truth: what git itself reports as the toplevel from inside the repo
    # (accounts for macOS /private symlink normalization).
    truth = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert truth.returncode == 0, f"git rev-parse failed: {truth.stderr}"
    expected_toplevel = truth.stdout.strip()

    # env WITHOUT CLAUDE_PROJECT_DIR (start from a minimal env; ensure unset).
    result = subprocess.run(
        ["/bin/sh", "-c", f'echo "{WRAPPED_CANONICAL}"'],
        cwd=str(repo),
        env={"PATH": _system_path()},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"sh failed: {result.stderr}"
    assert result.stdout.strip() == expected_toplevel, (
        f"Expected git toplevel {expected_toplevel!r}, got "
        f"{result.stdout.strip()!r} (stderr: {result.stderr!r})"
    )


def _system_path() -> str:
    """A PATH that can locate ``git`` for the fallback subprocess."""
    import os

    return os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin")

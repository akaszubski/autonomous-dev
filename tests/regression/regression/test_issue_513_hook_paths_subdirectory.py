"""Regression test for Issue #513: Hook paths break when Claude Code runs from subdirectory.

Bug: Hook commands in settings template files used relative paths like:
  python3 plugins/autonomous-dev/hooks/session_activity_logger.py
  python3 .claude/hooks/session_activity_logger.py

When Claude Code CWD is a subdirectory (e.g., a git worktree at .worktrees/batch-xxx/),
these relative paths resolve incorrectly and hooks fail with "No such file or directory".

Fix: All relative hook paths now use $(dirname "$(git rev-parse --path-format=absolute
--git-common-dir)")/... to dynamically resolve the main repo root. This works in both
normal repos and worktrees (Issue #651 follow-up). Paths starting with ~/ are already
absolute and left unchanged.
"""

import json
import re
from pathlib import Path

import pytest

TEMPLATES_DIR = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "autonomous-dev"
    / "templates"
)

TEMPLATE_FILES = [
    "settings.autonomous-dev.json",
    "settings.default.json",
    "settings.permission-batching.json",
    "settings.granular-bash.json",
    "settings.strict-mode.json",
    "settings.local.json",
]


def _extract_hook_commands(settings: dict) -> list[str]:
    """Extract all hook command strings from a settings dict."""
    commands = []
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


# Regex matching a bare relative path to plugins/ or .claude/ that is NOT
# preceded by $(git rev-parse --show-toplevel)/ and NOT preceded by ~/
_BARE_RELATIVE = re.compile(
    r"""(?:python3?|bash)\s+          # interpreter
        (?:(?:\S+=\S+\s+)*)          # optional env vars like SANDBOX_ENABLED=false
        (?!.*\$\(git\s+rev-parse)    # NOT using git rev-parse (already fixed)
        (?!~/)                        # NOT starting with ~/ (already absolute)
        (plugins/|\.claude/)          # bare relative path — the bug
    """,
    re.VERBOSE,
)


class TestIssue513HookPathsSubdirectory:
    """Ensure no settings template contains bare relative hook paths."""

    @pytest.mark.parametrize("template_name", TEMPLATE_FILES)
    def test_no_bare_relative_hook_paths(self, template_name: str) -> None:
        """Hook commands must not use bare relative paths (Issue #513).

        Relative paths like 'plugins/autonomous-dev/hooks/...' break when
        CWD is not the repo root. All paths must use either:
        - $(git rev-parse --show-toplevel)/... for repo-relative resolution
        - ~/... for home-directory-relative resolution
        """
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            pytest.skip(f"Template {template_name} not found (may not exist in this checkout)")

        settings = json.loads(template_path.read_text())
        commands = _extract_hook_commands(settings)

        violations = []
        for cmd in commands:
            if _BARE_RELATIVE.search(cmd):
                violations.append(cmd)

        assert not violations, (
            f"Template {template_name} has bare relative hook paths that will break "
            f"when CWD is a subdirectory (Issue #513):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    @pytest.mark.parametrize("template_name", TEMPLATE_FILES)
    def test_git_rev_parse_paths_are_quoted(self, template_name: str) -> None:
        """Paths using git rev-parse must be quoted to handle spaces."""
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            pytest.skip(f"Template {template_name} not found")

        settings = json.loads(template_path.read_text())
        commands = _extract_hook_commands(settings)

        unquoted = []
        for cmd in commands:
            # If git rev-parse is used (either old or new pattern), the path should be in quotes
            if "$(git rev-parse" in cmd:
                # Check that the outer $(...) / $(dirname ...) is inside quotes, OR the
                # git rev-parse substitution sits inside a double-quoted
                # ${CLAUDE_PROJECT_DIR:-...} expansion (Issue #1036 submodule-safe wrapped
                # form: python3 "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/...").
                is_quoted = (
                    '"$(git rev-parse' in cmd
                    or '"$(dirname' in cmd
                    or '"${CLAUDE_PROJECT_DIR:-$(git rev-parse' in cmd
                )
                if not is_quoted:
                    unquoted.append(cmd)

        assert not unquoted, (
            f"Template {template_name} has unquoted git rev-parse paths "
            f"(will break with spaces in path):\n"
            + "\n".join(f"  - {v}" for v in unquoted)
        )

    def test_echo_commands_not_affected(self) -> None:
        """Echo commands (e.g., in strict-mode) should NOT be modified."""
        strict_path = TEMPLATES_DIR / "settings.strict-mode.json"
        if not strict_path.exists():
            pytest.skip("strict-mode template not found")

        settings = json.loads(strict_path.read_text())
        commands = _extract_hook_commands(settings)

        echo_cmds = [c for c in commands if c.startswith("echo")]
        # Echo commands should exist and NOT contain git rev-parse
        for cmd in echo_cmds:
            assert "git rev-parse" not in cmd, (
                f"Echo command should not have been modified: {cmd}"
            )

    def test_home_dir_paths_preserved(self) -> None:
        """Paths starting with ~/ must remain unchanged (already absolute)."""
        for template_name in TEMPLATE_FILES:
            template_path = TEMPLATES_DIR / template_name
            if not template_path.exists():
                continue

            settings = json.loads(template_path.read_text())
            commands = _extract_hook_commands(settings)

            for cmd in commands:
                if "~/" in cmd:
                    # ~/... paths should NOT have git rev-parse
                    assert "git rev-parse" not in cmd or "~/" in cmd.split("git rev-parse")[0], (
                        f"Home dir path was incorrectly modified in {template_name}: {cmd}"
                    )

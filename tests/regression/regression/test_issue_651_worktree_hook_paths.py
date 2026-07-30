"""Regression test for Issue #651: session_activity_logger hook path resolution.

SUPERSEDED BY Issue #1036. The original #651 fix replaced
``$(git rev-parse --show-toplevel)`` with
``$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")`` to
survive git worktrees. Issue #1036 converged all templates onto a single
canonical that is both worktree-safe AND submodule-safe:

    ${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/.claude/hooks/<NAME>

- Primary ``CLAUDE_PROJECT_DIR`` is the Claude-Code-set launch project root
  (git-independent), so it resolves correctly inside submodules where
  ``git rev-parse --show-toplevel`` would return the submodule root.
- The ``$(git rev-parse --show-toplevel)`` fallback covers older CLIs that do
  not set the variable; a worktree carries its own copied ``.claude/hooks/`` so
  ``--show-toplevel`` still resolves to a working hook directory there.

These tests now assert the shared #1036 canonical: no *bare* (unwrapped)
``$(git rev-parse --show-toplevel)``, and every git-based hook command carries
the ``${CLAUDE_PROJECT_DIR:-`` primary. The ``--git-common-dir`` requirement is
intentionally dropped (it is banned by hook_path_validator because it resolves
to the main repo's git dir).
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


# The #1036 canonical wrapper. Any bare occurrence of the git substitution
# OUTSIDE this wrapper is a violation.
_WRAPPED_CANONICAL = "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"
_BARE_GIT_SUBST = "$(git rev-parse --show-toplevel)"
_PRIMARY_PREFIX = "${CLAUDE_PROJECT_DIR:-"


class TestIssue651WorktreeHookPaths:
    """Ensure every template uses the shared #1036 submodule/worktree canonical."""

    @pytest.mark.parametrize("template_name", TEMPLATE_FILES)
    def test_no_bare_show_toplevel_in_hook_commands(self, template_name: str) -> None:
        """No hook command may use a *bare* $(git rev-parse --show-toplevel).

        The git substitution is permitted ONLY as the fallback inside the
        ${CLAUDE_PROJECT_DIR:-...} wrapper (Issue #1036). A bare, unwrapped
        occurrence breaks inside git submodules.
        """
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            pytest.skip(f"Template {template_name} not found")

        settings = json.loads(template_path.read_text())
        commands = _extract_hook_commands(settings)

        violations = []
        for cmd in commands:
            # Strip all legitimately-wrapped occurrences, then any remaining
            # bare git substitution is a violation.
            stripped = cmd.replace(_WRAPPED_CANONICAL, "")
            if _BARE_GIT_SUBST in stripped:
                violations.append(cmd)

        assert not violations, (
            f"Template {template_name} uses a bare (unwrapped) "
            f"$(git rev-parse --show-toplevel) which breaks in git submodules "
            f"(Issue #1036). Wrap it as {_WRAPPED_CANONICAL}:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    @pytest.mark.parametrize("template_name", TEMPLATE_FILES)
    def test_git_based_commands_carry_project_dir_primary(
        self, template_name: str
    ) -> None:
        """Every git-based hook command must carry the ${CLAUDE_PROJECT_DIR:- primary.

        This is the submodule-immune primary; the git substitution is only its
        fallback (Issue #1036).
        """
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            pytest.skip(f"Template {template_name} not found")

        settings = json.loads(template_path.read_text())
        commands = _extract_hook_commands(settings)

        violations = []
        for cmd in commands:
            if cmd.startswith("echo") or "git rev-parse" not in cmd:
                continue
            if _PRIMARY_PREFIX not in cmd:
                violations.append(cmd)

        assert not violations, (
            f"Template {template_name} has git-based hook command(s) missing the "
            f"{_PRIMARY_PREFIX}...}} primary (Issue #1036):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    @pytest.mark.parametrize("template_name", TEMPLATE_FILES)
    def test_wrapped_canonical_pattern_used(self, template_name: str) -> None:
        """Git-based commands must use the full #1036 wrapped canonical prefix.

        The correct pattern is:
          ${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/.claude/hooks/...

        This resolves correctly in normal repos, worktrees, AND submodules.
        The legacy --git-common-dir requirement is intentionally dropped.
        """
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            pytest.skip(f"Template {template_name} not found")

        settings = json.loads(template_path.read_text())
        commands = _extract_hook_commands(settings)

        wrapped_pattern = re.compile(
            r"\$\{CLAUDE_PROJECT_DIR:-\$\(git rev-parse --show-toplevel\)\}"
            r"/\.claude/hooks/"
        )

        for cmd in commands:
            # Skip ~/... paths and echo commands - they don't use git rev-parse
            if cmd.startswith("echo") or "git rev-parse" not in cmd:
                continue

            assert wrapped_pattern.search(cmd), (
                f"Command in {template_name} uses git rev-parse but not the "
                f"#1036 wrapped canonical pattern:\n"
                f"  Got: {cmd}\n"
                f"  Expected prefix: {_WRAPPED_CANONICAL}/.claude/hooks/..."
            )

    def test_home_dir_paths_not_affected(self) -> None:
        """Paths starting with ~/ must remain unchanged (already absolute)."""
        for template_name in TEMPLATE_FILES:
            template_path = TEMPLATES_DIR / template_name
            if not template_path.exists():
                continue

            settings = json.loads(template_path.read_text())
            commands = _extract_hook_commands(settings)

            for cmd in commands:
                # ~/... paths should NOT contain git rev-parse
                if "~/" in cmd and not cmd.startswith("echo"):
                    # The ~ path part itself should not be wrapped in git rev-parse
                    assert "git rev-parse" not in cmd, (
                        f"Home dir path was incorrectly modified in "
                        f"{template_name}: {cmd}"
                    )

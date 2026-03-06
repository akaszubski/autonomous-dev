"""Tests for /reload-plugins documentation adoption (Issue #391).

Verifies that all relevant documentation files mention /reload-plugins
and that bare "restart Claude Code" instructions are accompanied by
/reload-plugins context where appropriate.

These tests should FAIL initially (TDD red phase) since the docs
have not yet been updated.
"""

from pathlib import Path

import pytest

# Compute project root from this test file's location:
# tests/unit/docs/test_reload_plugins_docs.py -> project root is 3 levels up
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Target documentation files
CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"
ROOT_README = PROJECT_ROOT / "README.md"
PLUGIN_README = PROJECT_ROOT / "plugins" / "autonomous-dev" / "README.md"
TROUBLESHOOTING_MD = (
    PROJECT_ROOT / "plugins" / "autonomous-dev" / "docs" / "TROUBLESHOOTING.md"
)
CONTRIBUTING_MD = PROJECT_ROOT / "CONTRIBUTING.md"
INSTALL_SH = PROJECT_ROOT / "install.sh"

# Active doc files to check for bare restart references
ACTIVE_DOCS = [CLAUDE_MD, ROOT_README, CONTRIBUTING_MD, TROUBLESHOOTING_MD]


class TestReloadPluginsDocumentation:
    """Verify /reload-plugins is documented across the project."""

    def test_claude_md_mentions_reload_plugins(self) -> None:
        """CLAUDE.md should mention /reload-plugins at least once."""
        content = CLAUDE_MD.read_text()
        assert "/reload-plugins" in content, (
            "CLAUDE.md does not mention /reload-plugins. "
            "Users need to know about this command for reloading after plugin changes."
        )

    def test_readme_mentions_reload_plugins(self) -> None:
        """Root README.md should mention /reload-plugins."""
        content = ROOT_README.read_text()
        assert "/reload-plugins" in content, (
            "README.md does not mention /reload-plugins. "
            "The main README should document available commands including /reload-plugins."
        )

    def test_plugin_readme_mentions_reload_plugins(self) -> None:
        """plugins/autonomous-dev/README.md should mention /reload-plugins."""
        content = PLUGIN_README.read_text()
        assert "/reload-plugins" in content, (
            "Plugin README.md does not mention /reload-plugins. "
            "The plugin's own README should document /reload-plugins."
        )

    def test_troubleshooting_mentions_reload_plugins(self) -> None:
        """TROUBLESHOOTING.md should mention /reload-plugins."""
        content = TROUBLESHOOTING_MD.read_text()
        assert "/reload-plugins" in content, (
            "TROUBLESHOOTING.md does not mention /reload-plugins. "
            "Troubleshooting should guide users to /reload-plugins before full restart."
        )

    def test_contributing_mentions_reload_plugins(self) -> None:
        """CONTRIBUTING.md should mention /reload-plugins."""
        content = CONTRIBUTING_MD.read_text()
        assert "/reload-plugins" in content, (
            "CONTRIBUTING.md does not mention /reload-plugins. "
            "Contributors should know about /reload-plugins for development workflow."
        )

    def test_no_bare_restart_without_reload_context(self) -> None:
        """Active docs should not say 'restart Claude Code' without /reload-plugins context.

        If a doc mentions restarting Claude Code, it should either:
        1. Also mention /reload-plugins as a lighter alternative, OR
        2. Explain why a full restart is needed (hooks, settings changes)
        """
        restart_phrases = [
            "restart claude code",
            "restart Claude Code",
            "Restart Claude Code",
        ]
        hooks_settings_context = [
            "hook",
            "settings",
            "/reload-plugins",
            "reload-plugins",
        ]

        violations = []
        for doc_path in ACTIVE_DOCS:
            if not doc_path.exists():
                continue
            content = doc_path.read_text()
            lines = content.splitlines()

            for i, line in enumerate(lines):
                for phrase in restart_phrases:
                    if phrase in line:
                        # Check surrounding context (5 lines before/after)
                        context_start = max(0, i - 5)
                        context_end = min(len(lines), i + 6)
                        context = "\n".join(lines[context_start:context_end]).lower()

                        has_context = any(
                            kw in context for kw in hooks_settings_context
                        )
                        if not has_context:
                            violations.append(
                                f"{doc_path.name}:{i + 1}: "
                                f"'{phrase}' without /reload-plugins or hooks/settings context"
                            )
                        break  # Only flag once per line

        assert not violations, (
            "Found bare 'restart Claude Code' without /reload-plugins context:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_false_claim_reload_works_for_hooks(self) -> None:
        """No doc should claim /reload-plugins works for hook changes.

        Hook changes require a full Claude Code restart. Docs should not
        mislead users into thinking /reload-plugins handles hooks.
        """
        false_claim_patterns = [
            "reload-plugins" + s + "hook"
            for s in [
                " reloads ",
                " updates ",
                " refreshes ",
                " applies ",
            ]
        ]

        for doc_path in ACTIVE_DOCS + [PLUGIN_README]:
            if not doc_path.exists():
                continue
            content = doc_path.read_text().lower()
            for pattern in false_claim_patterns:
                assert pattern not in content, (
                    f"{doc_path.name} falsely claims /reload-plugins works for hooks. "
                    f"Hook changes require a full restart."
                )

    def test_install_sh_mentions_reload_plugins(self) -> None:
        """install.sh should mention /reload-plugins in post-install instructions."""
        content = INSTALL_SH.read_text()
        assert "/reload-plugins" in content, (
            "install.sh does not mention /reload-plugins. "
            "Post-install instructions should tell users to run /reload-plugins."
        )

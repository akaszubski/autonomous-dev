"""Regression tests for component count accuracy.

Dynamically derives component counts from the filesystem and compares
against documented counts in CLAUDE.md. No hardcoded counts in test logic.

Incident: Component counts drifted across 5+ documentation files after
hook archival. Consolidated to CLAUDE.md + README.md as single sources.
"""

import re
from pathlib import Path

import pytest


class TestDynamicComponentCounts:
    """Verify CLAUDE.md component counts match filesystem reality."""

    def _count_agents(self, plugins_dir: Path) -> int:
        """Count active agent .md files (excluding archived)."""
        agents_dir = plugins_dir / "agents"
        if not agents_dir.exists():
            return 0
        return len([f for f in agents_dir.glob("*.md") if f.name != "README.md"])

    def _count_skills(self, plugins_dir: Path) -> int:
        """Count skill directories (each skill is a directory with SKILL.md)."""
        skills_dir = plugins_dir / "skills"
        if not skills_dir.exists():
            return 0
        return len([
            d for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])

    def _count_commands(self, plugins_dir: Path) -> int:
        """Count active command .md files."""
        commands_dir = plugins_dir / "commands"
        if not commands_dir.exists():
            return 0
        return len(list(commands_dir.glob("*.md")))

    def _count_active_hooks(self, plugins_dir: Path) -> int:
        """Count active hook .py files (not in archived/, not __init__)."""
        hooks_dir = plugins_dir / "hooks"
        if not hooks_dir.exists():
            return 0
        return len([
            f for f in hooks_dir.glob("*.py")
            if f.name != "__init__.py"
        ])

    def _count_libraries(self, plugins_dir: Path) -> int:
        """Count library .py files (recursive, excluding __init__)."""
        lib_dir = plugins_dir / "lib"
        if not lib_dir.exists():
            return 0
        return len([
            f for f in lib_dir.rglob("*.py")
            if f.name != "__init__.py"
        ])

    def _parse_claude_md_counts(self, project_root: Path) -> dict[str, int]:
        """Parse component counts from CLAUDE.md Component Counts section."""
        claude_md = project_root / "CLAUDE.md"
        if not claude_md.exists():
            pytest.skip("CLAUDE.md not found")

        content = claude_md.read_text()

        counts = {}
        # Pattern: "16 agents" or "39 skills" etc in the Component Counts line
        agents_match = re.search(r'(\d+)\s+agents', content)
        if agents_match:
            counts["agents"] = int(agents_match.group(1))

        skills_match = re.search(r'(\d+)\s+skills', content)
        if skills_match:
            counts["skills"] = int(skills_match.group(1))

        commands_match = re.search(r'(\d+)\s+active commands', content)
        if commands_match:
            counts["commands"] = int(commands_match.group(1))

        libraries_match = re.search(r'(\d+)\s+libraries', content)
        if libraries_match:
            counts["libraries"] = int(libraries_match.group(1))

        hooks_match = re.search(r'(\d+)\s+active hooks', content)
        if hooks_match:
            counts["hooks"] = int(hooks_match.group(1))

        return counts

    def test_agent_count_matches(self, project_root: Path, plugins_dir: Path):
        """Agent count in CLAUDE.md must match filesystem."""
        actual = self._count_agents(plugins_dir)
        documented = self._parse_claude_md_counts(project_root)
        if "agents" not in documented:
            pytest.skip("No agent count found in CLAUDE.md")
        assert actual == documented["agents"], (
            f"Agent count drift: filesystem has {actual}, CLAUDE.md says {documented['agents']}"
        )

    def test_skill_count_matches(self, project_root: Path, plugins_dir: Path):
        """Skill count in CLAUDE.md must match filesystem."""
        actual = self._count_skills(plugins_dir)
        documented = self._parse_claude_md_counts(project_root)
        if "skills" not in documented:
            pytest.skip("No skill count found in CLAUDE.md")
        assert actual == documented["skills"], (
            f"Skill count drift: filesystem has {actual}, CLAUDE.md says {documented['skills']}"
        )

    def test_command_count_matches(self, project_root: Path, plugins_dir: Path):
        """Command count in CLAUDE.md must match filesystem."""
        actual = self._count_commands(plugins_dir)
        documented = self._parse_claude_md_counts(project_root)
        if "commands" not in documented:
            pytest.skip("No command count found in CLAUDE.md")
        assert actual == documented["commands"], (
            f"Command count drift: filesystem has {actual}, CLAUDE.md says {documented['commands']}"
        )

    def test_active_hook_count_matches(self, project_root: Path, plugins_dir: Path):
        """Active hook count in CLAUDE.md must match filesystem."""
        actual = self._count_active_hooks(plugins_dir)
        documented = self._parse_claude_md_counts(project_root)
        if "hooks" not in documented:
            pytest.skip("No hook count found in CLAUDE.md")
        assert actual == documented["hooks"], (
            f"Active hook count drift: filesystem has {actual}, CLAUDE.md says {documented['hooks']}"
        )

    def test_library_count_matches(self, project_root: Path, plugins_dir: Path):
        """Library count in CLAUDE.md must match filesystem."""
        actual = self._count_libraries(plugins_dir)
        documented = self._parse_claude_md_counts(project_root)
        if "libraries" not in documented:
            pytest.skip("No library count found in CLAUDE.md")
        assert actual == documented["libraries"], (
            f"Library count drift: filesystem has {actual}, CLAUDE.md says {documented['libraries']}"
        )

    def test_claude_md_has_component_counts_section(self, project_root: Path):
        """CLAUDE.md must have a Component Counts section."""
        claude_md = project_root / "CLAUDE.md"
        assert claude_md.exists(), "CLAUDE.md not found"
        content = claude_md.read_text()
        assert "## Component Counts" in content, (
            "CLAUDE.md missing '## Component Counts' section — "
            "this is the single source of truth for component counts"
        )

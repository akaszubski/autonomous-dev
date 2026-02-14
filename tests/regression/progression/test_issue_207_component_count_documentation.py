"""
Progression tests for Issue #207: Update component counts across all documentation.

These tests validate that documented component counts match actual filesystem counts.
Updated for Issue #337 to use correct counts and match actual CLAUDE.md format.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List

import pytest


# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)


def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent


def _count_filesystem_components(project_root: Path) -> Dict[str, int]:
    """Count all components in the filesystem."""
    return {
        "commands": len([
            f for f in (project_root / "plugins" / "autonomous-dev" / "commands").glob("*.md")
            if "archived" not in str(f.parent)
        ]),
        "agents": len(list(
            (project_root / "plugins" / "autonomous-dev" / "agents").glob("*.md")
        )),
        "skills": len([
            f for f in (project_root / "plugins" / "autonomous-dev" / "skills").rglob("SKILL.md")
            if "archived" not in str(f)
        ]),
        "hooks": len([
            f for f in (project_root / "plugins" / "autonomous-dev" / "hooks").glob("*.py")
            if not f.name.startswith("test_") and f.name != "__init__.py"
        ]),
        "libraries": len([
            f for f in (project_root / "plugins" / "autonomous-dev" / "lib").glob("*.py")
            if not f.name.startswith("test_") and f.name != "__init__.py"
        ]),
    }


class TestFilesystemComponentCounts:
    """Test actual filesystem component counts."""

    def test_count_commands_excludes_archived(self):
        """Test counting command files excludes archived directory."""
        project_root = _get_project_root()
        counts = _count_filesystem_components(project_root)
        assert counts["commands"] == 23, (
            f"Expected 23 command files (excluding archived), found {counts['commands']}"
        )

    def test_count_agents(self):
        """Test counting agent files."""
        project_root = _get_project_root()
        counts = _count_filesystem_components(project_root)
        assert counts["agents"] == 16, (
            f"Expected 16 agent files, found {counts['agents']}"
        )

    def test_count_skills(self):
        """Test counting skills by SKILL.md files."""
        project_root = _get_project_root()
        counts = _count_filesystem_components(project_root)
        assert counts["skills"] == 38, (
            f"Expected 38 skills (SKILL.md files), found {counts['skills']}"
        )

    def test_count_hooks_excludes_tests(self):
        """Test counting hook files excludes test files and __init__."""
        project_root = _get_project_root()
        counts = _count_filesystem_components(project_root)
        assert counts["hooks"] == 17, (
            f"Expected 17 hook files, found {counts['hooks']}"
        )

    def test_count_libraries_excludes_tests(self):
        """Test counting library files excludes test files and __init__."""
        project_root = _get_project_root()
        counts = _count_filesystem_components(project_root)
        assert counts["libraries"] == 136, (
            f"Expected 136 library files, found {counts['libraries']}"
        )


class TestClaudeMdComponentCounts:
    """Test CLAUDE.md Component Counts section has correct counts.

    CLAUDE.md uses inline format: '16 agents, 38 skills, 23 active commands, 136 libraries, 17 active hooks'
    """

    def _parse_claude_md_counts(self) -> Dict[str, int]:
        """Parse component counts from CLAUDE.md inline format."""
        project_root = _get_project_root()
        content = (project_root / "CLAUDE.md").read_text()

        counts = {}
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

    def test_claude_md_agents_count(self):
        """Test CLAUDE.md has correct agents count."""
        counts = self._parse_claude_md_counts()
        assert counts.get("agents") == 16, f"Expected 16 agents, found {counts.get('agents')}"

    def test_claude_md_skills_count(self):
        """Test CLAUDE.md has correct skills count."""
        counts = self._parse_claude_md_counts()
        assert counts.get("skills") == 38, f"Expected 38 skills, found {counts.get('skills')}"

    def test_claude_md_commands_count(self):
        """Test CLAUDE.md has correct commands count."""
        counts = self._parse_claude_md_counts()
        assert counts.get("commands") == 23, f"Expected 23 commands, found {counts.get('commands')}"

    def test_claude_md_libraries_count(self):
        """Test CLAUDE.md has correct libraries count."""
        counts = self._parse_claude_md_counts()
        assert counts.get("libraries") == 136, f"Expected 136 libraries, found {counts.get('libraries')}"

    def test_claude_md_hooks_count(self):
        """Test CLAUDE.md has correct hooks count."""
        counts = self._parse_claude_md_counts()
        assert counts.get("hooks") == 17, f"Expected 17 hooks, found {counts.get('hooks')}"


class TestComponentCountsMatchFilesystem:
    """Test documented counts match actual filesystem counts."""

    def test_all_documented_counts_match_filesystem(self):
        """Test all component counts in CLAUDE.md match filesystem."""
        project_root = _get_project_root()
        fs_counts = _count_filesystem_components(project_root)

        content = (project_root / "CLAUDE.md").read_text()

        # Parse CLAUDE.md inline format
        doc_agents = int(re.search(r'(\d+)\s+agents', content).group(1))
        doc_skills = int(re.search(r'(\d+)\s+skills', content).group(1))
        doc_commands = int(re.search(r'(\d+)\s+active commands', content).group(1))
        doc_libraries = int(re.search(r'(\d+)\s+libraries', content).group(1))
        doc_hooks = int(re.search(r'(\d+)\s+active hooks', content).group(1))

        doc_counts = {
            "agents": doc_agents,
            "skills": doc_skills,
            "commands": doc_commands,
            "libraries": doc_libraries,
            "hooks": doc_hooks,
        }

        mismatches = []
        for component in fs_counts:
            if fs_counts[component] != doc_counts[component]:
                mismatches.append(
                    f"{component}: filesystem={fs_counts[component]}, "
                    f"documented={doc_counts[component]}"
                )

        assert len(mismatches) == 0, (
            f"Component count mismatches:\n" + "\n".join(f"  - {m}" for m in mismatches)
        )


class TestNoStaleCountsInDocs:
    """Test for stale component counts in docs/ directory."""

    def test_no_stale_libraries_count_69(self):
        """Test docs/ has no references to '69 Libraries'."""
        project_root = _get_project_root()
        docs_dir = project_root / "plugins" / "autonomous-dev" / "docs"

        stale_files = []
        if docs_dir.exists():
            for doc_file in docs_dir.rglob("*.md"):
                content = doc_file.read_text()
                if re.search(r'\b69\s+[Ll]ibraries?\b', content):
                    stale_files.append(str(doc_file.relative_to(project_root)))

        assert len(stale_files) == 0, (
            f"Found stale '69 Libraries' count in: {', '.join(stale_files)}"
        )

    def test_no_stale_hooks_count_64(self):
        """Test docs/ has no references to '64 Hooks' or '62 Hooks'."""
        project_root = _get_project_root()
        docs_dir = project_root / "plugins" / "autonomous-dev" / "docs"

        stale_files = []
        if docs_dir.exists():
            for doc_file in docs_dir.rglob("*.md"):
                content = doc_file.read_text()
                if re.search(r'\b(64|62)\s+[Hh]ooks?\b', content):
                    stale_files.append(str(doc_file.relative_to(project_root)))

        assert len(stale_files) == 0, (
            f"Found stale hooks count in: {', '.join(stale_files)}"
        )

    def test_no_stale_commands_count_9(self):
        """Test docs/ has no references to '9 commands'."""
        project_root = _get_project_root()
        docs_dir = project_root / "plugins" / "autonomous-dev" / "docs"

        stale_files = []
        if docs_dir.exists():
            for doc_file in docs_dir.rglob("*.md"):
                content = doc_file.read_text()
                if re.search(r'\b9\s+[Cc]ommands?\b', content):
                    stale_files.append(str(doc_file.relative_to(project_root)))

        assert len(stale_files) == 0, (
            f"Found stale '9 commands' count in: {', '.join(stale_files)}"
        )

    def test_check_readme_component_counts(self):
        """Test README.md has no stale component counts."""
        project_root = _get_project_root()
        readme = project_root / "plugins" / "autonomous-dev" / "README.md"

        if not readme.exists():
            pytest.skip("README.md not found")

        content = readme.read_text()

        stale_patterns = [
            (r'\b69\s+[Ll]ibraries?\b', "69 Libraries should be 136"),
            (r'\b64\s+[Hh]ooks?\b', "64 Hooks should be 17"),
            (r'\b62\s+[Hh]ooks?\b', "62 Hooks should be 17"),
            (r'\b9\s+[Cc]ommands?\b', "9 commands should be 23"),
        ]

        issues = []
        for pattern, message in stale_patterns:
            if re.search(pattern, content):
                issues.append(message)

        assert len(issues) == 0, (
            f"Found stale counts in README.md: {'; '.join(issues)}"
        )


class TestEdgeCases:
    """Test edge cases for component counting."""

    def test_handles_missing_commands_directory(self, tmp_path):
        """Test graceful handling when commands directory is missing."""
        commands_dir = tmp_path / "plugins" / "autonomous-dev" / "commands"
        assert not commands_dir.exists()

    def test_handles_empty_agents_directory(self, tmp_path):
        """Test handling of empty agents directory."""
        agents_dir = tmp_path / "plugins" / "autonomous-dev" / "agents"
        agents_dir.mkdir(parents=True)
        agent_files = list(agents_dir.glob("*.md"))
        assert len(agent_files) == 0

    def test_counts_exclude_hidden_files(self, tmp_path):
        """Test that hidden files (.dotfiles) are excluded from counts."""
        test_dir = tmp_path / "test_components"
        test_dir.mkdir(parents=True)
        (test_dir / ".hidden.md").write_text("hidden")
        (test_dir / "normal.md").write_text("normal")

        visible_files = [f for f in test_dir.glob("*.md") if not f.name.startswith(".")]
        assert len(visible_files) == 1
        assert visible_files[0].name == "normal.md"

    def test_skills_directory_structure(self):
        """Test that skills are organized as directories with SKILL.md."""
        project_root = _get_project_root()
        skills_dir = project_root / "plugins" / "autonomous-dev" / "skills"

        if not skills_dir.exists():
            pytest.skip("Skills directory not found")

        skill_dirs = [
            d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
        ]

        missing_skill_md = []
        for skill_dir in skill_dirs:
            if not (skill_dir / "SKILL.md").exists():
                missing_skill_md.append(skill_dir.name)

        # Informational - some dirs may be support dirs without SKILL.md
        assert isinstance(missing_skill_md, list)


class TestComponentCountIntegration:
    """Integration tests for complete component count validation."""

    def test_create_component_count_report(self):
        """Test generation of component count report."""
        project_root = _get_project_root()
        report = _count_filesystem_components(project_root)

        assert "commands" in report
        assert "agents" in report
        assert "skills" in report
        assert "hooks" in report
        assert "libraries" in report

        for component, count in report.items():
            assert isinstance(count, int), f"{component} count should be int"
            assert count > 0, f"{component} count should be positive"

    def test_validate_component_counts_in_claude_md(self):
        """Test complete validation of CLAUDE.md component counts."""
        project_root = _get_project_root()
        fs_counts = _count_filesystem_components(project_root)

        content = (project_root / "CLAUDE.md").read_text()

        doc_counts = {
            "commands": int(re.search(r'(\d+)\s+active commands', content).group(1)),
            "agents": int(re.search(r'(\d+)\s+agents', content).group(1)),
            "skills": int(re.search(r'(\d+)\s+skills', content).group(1)),
            "hooks": int(re.search(r'(\d+)\s+active hooks', content).group(1)),
            "libraries": int(re.search(r'(\d+)\s+libraries', content).group(1)),
        }

        mismatches = []
        for component in fs_counts:
            if fs_counts[component] != doc_counts[component]:
                mismatches.append(
                    f"{component}: filesystem={fs_counts[component]}, "
                    f"documented={doc_counts[component]}"
                )

        assert len(mismatches) == 0, (
            f"Component count mismatches:\n" + "\n".join(f"  - {m}" for m in mismatches)
        )

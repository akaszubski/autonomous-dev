"""
Regression tests for documentation congruence across PROJECT.md, CLAUDE.md, and README.md.

Validates that key claims in documentation match the actual codebase state.
Prevents the drift pattern where component counts, versions, command lists,
agent tiers, and pipeline steps go stale after changes.

Date: 2026-03-07
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "autonomous-dev"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _count_files(directory: Path, pattern: str, exclude_dirs: list[str] | None = None) -> int:
    exclude_dirs = exclude_dirs or []
    count = 0
    for f in directory.glob(pattern):
        if any(ex in f.parts for ex in exclude_dirs):
            continue
        if f.name.endswith(",cover"):
            continue
        if f.name == "README.md":
            continue
        count += 1
    return count


def _extract_number(text: str, pattern: str) -> int | None:
    """Extract a number from text using a regex pattern with one capture group."""
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# 1. Version consistency
# ---------------------------------------------------------------------------

class TestVersionConsistency:
    """VERSION file is the source of truth for the version number."""

    @pytest.fixture
    def actual_version(self) -> str:
        return (PLUGIN / "VERSION").read_text().strip()

    def test_project_md_version_matches(self, actual_version):
        text = _read(ROOT / ".claude" / "PROJECT.md")
        m = re.search(r"\*\*Version\*\*:\s*v?(\S+)", text)
        assert m, "PROJECT.md missing version line"
        assert m.group(1) == actual_version, (
            f"PROJECT.md version {m.group(1)} != VERSION file {actual_version}"
        )

    def test_readme_badge_version_matches(self, actual_version):
        text = _read(ROOT / "README.md")
        m = re.search(r"version-([0-9.]+)-", text)
        assert m, "README.md missing version badge"
        assert m.group(1) == actual_version, (
            f"README.md badge version {m.group(1)} != VERSION file {actual_version}"
        )


# ---------------------------------------------------------------------------
# 2. Component counts
# ---------------------------------------------------------------------------

class TestComponentCounts:
    """CLAUDE.md component counts must match reality."""

    @pytest.fixture
    def claude_md(self) -> str:
        return _read(ROOT / "CLAUDE.md")

    def test_active_agent_count(self, claude_md):
        actual = _count_files(PLUGIN / "agents", "*.md", exclude_dirs=["archived"])
        documented = _extract_number(claude_md, r"(\d+)\s+agents?\s*\(")
        assert documented is not None, "CLAUDE.md missing agent count"
        assert actual == documented, (
            f"Active agents: {actual} on disk, {documented} in CLAUDE.md"
        )

    def test_archived_agent_count(self, claude_md):
        actual = _count_files(PLUGIN / "agents" / "archived", "*.md")
        documented = _extract_number(claude_md, r"\((\d+)\s+archived\)")
        assert documented is not None, "CLAUDE.md missing archived agent count"
        assert actual == documented, (
            f"Archived agents: {actual} on disk, {documented} in CLAUDE.md"
        )

    def test_skill_count(self, claude_md):
        actual = sum(1 for _ in PLUGIN.glob("skills/*/SKILL.md")
                     if "archived" not in str(_))
        documented = _extract_number(claude_md, r"(\d+)\s+skills?")
        assert documented is not None, "CLAUDE.md missing skill count"
        assert actual == documented, (
            f"Skills: {actual} on disk, {documented} in CLAUDE.md"
        )

    def test_command_count(self, claude_md):
        actual = _count_files(PLUGIN / "commands", "*.md", exclude_dirs=["archived"])
        documented = _extract_number(claude_md, r"(\d+)\s+active commands?")
        assert documented is not None, "CLAUDE.md missing command count"
        assert actual == documented, (
            f"Commands: {actual} on disk, {documented} in CLAUDE.md"
        )

    def test_library_count(self, claude_md):
        actual = sum(1 for _ in (PLUGIN / "lib").rglob("*.py")
                     if "__pycache__" not in str(_))
        documented = _extract_number(claude_md, r"(\d+)\s+libraries")
        assert documented is not None, "CLAUDE.md missing library count"
        assert actual == documented, (
            f"Libraries: {actual} on disk, {documented} in CLAUDE.md"
        )

    def test_active_hook_count(self, claude_md):
        py = _count_files(PLUGIN / "hooks", "*.py", exclude_dirs=["archived"])
        sh = _count_files(PLUGIN / "hooks", "*.sh", exclude_dirs=["archived"])
        actual = py + sh
        documented = _extract_number(claude_md, r"(\d+)\s+active hooks?")
        assert documented is not None, "CLAUDE.md missing hook count"
        assert actual == documented, (
            f"Active hooks: {actual} on disk ({py} py + {sh} sh), {documented} in CLAUDE.md"
        )

    def test_archived_hook_count(self, claude_md):
        archived_dir = PLUGIN / "hooks" / "archived"
        actual = sum(1 for f in archived_dir.iterdir()
                     if f.suffix in (".py", ".sh") and not f.name.endswith(",cover"))
        # Extract from pattern like "21 active hooks (62 archived)"
        documented = _extract_number(claude_md, r"hooks?\s*\((\d+)\s+archived\)")
        assert documented is not None, "CLAUDE.md missing archived hook count"
        assert actual == documented, (
            f"Archived hooks: {actual} on disk, {documented} in CLAUDE.md"
        )

    def test_template_count(self):
        actual = len(list(PLUGIN.glob("templates/settings.*.json")))
        project_md = _read(ROOT / ".claude" / "PROJECT.md")
        documented = _extract_number(project_md, r"Settings templates\s*\((\d+)")
        assert documented is not None, "PROJECT.md missing template count"
        assert actual == documented, (
            f"Settings templates: {actual} on disk, {documented} in PROJECT.md"
        )


# ---------------------------------------------------------------------------
# 3. Command documentation completeness
# ---------------------------------------------------------------------------

class TestCommandDocumentation:
    """Every active command must appear in CLAUDE.md and README.md."""

    @pytest.fixture
    def active_commands(self) -> set[str]:
        """Command names derived from filenames (excluding sub-commands)."""
        cmds = set()
        for f in (PLUGIN / "commands").glob("*.md"):
            if "archived" in str(f):
                continue
            name = f.stem
            # implement-batch and implement-resume are sub-commands of /implement
            if name in ("implement-batch", "implement-resume"):
                continue
            cmds.add(name)
        return cmds

    def test_all_commands_in_claude_md(self, active_commands):
        text = _read(ROOT / "CLAUDE.md")
        missing = {cmd for cmd in active_commands if f"/{cmd}" not in text}
        assert not missing, (
            f"Commands on disk but missing from CLAUDE.md: {sorted(missing)}"
        )

    def test_all_commands_in_readme(self, active_commands):
        text = _read(ROOT / "README.md")
        missing = {cmd for cmd in active_commands if f"/{cmd}" not in text}
        assert not missing, (
            f"Commands on disk but missing from README.md: {sorted(missing)}"
        )

    def test_no_phantom_commands_in_readme(self):
        """README.md should not list commands that don't exist as files or flags."""
        text = _read(ROOT / "README.md")
        # Find all /command patterns in the Key Commands table
        command_refs = set(re.findall(r"`(/[\w-]+)`", text))
        active_files = {f"/{f.stem}" for f in (PLUGIN / "commands").glob("*.md")
                        if "archived" not in str(f)}
        # Built-in Claude Code commands (not plugin commands)
        builtins = {"/clear", "/exit", "/help", "/reload-plugins", "/plugin", "/hooks"}
        # Also allow flag variants of existing commands
        flag_prefixes = {f"/{f.stem}" for f in (PLUGIN / "commands").glob("*.md")
                         if "archived" not in str(f)}
        for ref in command_refs:
            base = ref.split(" ")[0]  # /implement --quick -> /implement
            if base in builtins:
                continue
            assert base in active_files or any(base.startswith(p) for p in flag_prefixes), (
                f"README.md references {ref} but no command file exists for it"
            )


# ---------------------------------------------------------------------------
# 4. Pipeline step count consistency
# ---------------------------------------------------------------------------

class TestPipelineConsistency:
    """Pipeline description must be consistent across all docs."""

    def test_claude_md_says_8_steps(self):
        text = _read(ROOT / "CLAUDE.md")
        m = re.search(r"(\d+)-step\s+SDLC", text)
        assert m, "CLAUDE.md missing N-step SDLC description"
        assert m.group(1) == "8", (
            f"CLAUDE.md says {m.group(1)}-step pipeline, should be 8"
        )

    def test_project_md_says_8_steps(self):
        text = _read(ROOT / ".claude" / "PROJECT.md")
        m = re.search(r"(\d+)-step\s+pipeline", text)
        assert m, "PROJECT.md missing N-step pipeline description"
        assert m.group(1) == "8", (
            f"PROJECT.md says {m.group(1)}-step pipeline, should be 8"
        )


# ---------------------------------------------------------------------------
# 5. Model tier accuracy
# ---------------------------------------------------------------------------

class TestModelTierAccuracy:
    """Model tier assignments in docs must match implement.md (source of truth)."""

    @pytest.fixture
    def implement_tiers(self) -> dict[str, str]:
        """Extract agent→tier mappings from implement.md."""
        text = _read(PLUGIN / "commands" / "implement.md")
        tiers = {}
        for m in re.finditer(r"\*\*(\w[\w-]*)\*\*\s*\((\w+)\)", text):
            agent, tier = m.group(1), m.group(2).lower()
            if tier in ("haiku", "sonnet", "opus"):
                tiers[agent] = tier
        return tiers

    def test_readme_tiers_match_implement(self, implement_tiers):
        text = _read(ROOT / "README.md")
        mismatches = []
        for m in re.finditer(r"\*\*(\w[\w-]*)\*\*\s*\((\w+)\)", text):
            agent, tier = m.group(1), m.group(2).lower()
            if tier not in ("haiku", "sonnet", "opus"):
                continue
            if agent in implement_tiers and implement_tiers[agent] != tier:
                mismatches.append(
                    f"{agent}: README says {tier}, implement.md says {implement_tiers[agent]}"
                )
        assert not mismatches, (
            "Model tier mismatches between README.md and implement.md:\n"
            + "\n".join(mismatches)
        )

    def test_project_md_tiers_match_implement(self, implement_tiers):
        text = _read(ROOT / ".claude" / "PROJECT.md")
        mismatches = []
        # PROJECT.md format: "**Opus**: ... planner, test-master, implementer"
        for m in re.finditer(r"\*\*(\w+)\*\*:.*?—\s*(.+)", text):
            tier = m.group(1).lower()
            if tier not in ("haiku", "sonnet", "opus"):
                continue
            agents_str = m.group(2)
            for agent in re.findall(r"[\w-]+", agents_str):
                if agent in implement_tiers and implement_tiers[agent] != tier:
                    mismatches.append(
                        f"{agent}: PROJECT.md says {tier}, implement.md says {implement_tiers[agent]}"
                    )
        assert not mismatches, (
            "Model tier mismatches between PROJECT.md and implement.md:\n"
            + "\n".join(mismatches)
        )


# ---------------------------------------------------------------------------
# 6. Documentation links
# ---------------------------------------------------------------------------

class TestDocumentationLinks:
    """All doc links in CLAUDE.md and README.md must point to existing files."""

    @pytest.fixture
    def claude_md_links(self) -> list[str]:
        text = _read(ROOT / "CLAUDE.md")
        return re.findall(r"\[.*?\]\(((?!http)[^)]+)\)", text)

    @pytest.fixture
    def readme_links(self) -> list[str]:
        text = _read(ROOT / "README.md")
        return re.findall(r"\[.*?\]\(((?!http)[^)]+)\)", text)

    def test_claude_md_links_exist(self, claude_md_links):
        broken = []
        for link in claude_md_links:
            # Strip anchors
            path = link.split("#")[0]
            if not path:
                continue
            full = ROOT / path
            if not full.exists():
                broken.append(link)
        assert not broken, f"Broken links in CLAUDE.md: {broken}"

    def test_readme_links_exist(self, readme_links):
        broken = []
        for link in readme_links:
            path = link.split("#")[0]
            if not path:
                continue
            full = ROOT / path
            if not full.exists():
                broken.append(link)
        assert not broken, f"Broken links in README.md: {broken}"


# ---------------------------------------------------------------------------
# 7. No unsubstantiated statistics
# ---------------------------------------------------------------------------

class TestNoUnsubstantiatedClaims:
    """Docs must not contain invented percentage claims without sources."""

    INVENTED_PATTERNS = [
        r"23%.*bug",
        r"12%.*security",
        r"67%.*documentation",
        r"43%.*coverage",
        r"94%.*coverage",
        r"85%.*caught",
        r"0\.3%.*security",
    ]

    @pytest.mark.parametrize("filepath", [
        "README.md",
        "CLAUDE.md",
        "docs/WORKFLOW-DISCIPLINE.md",
    ])
    def test_no_invented_stats(self, filepath):
        text = _read(ROOT / filepath)
        found = []
        for pattern in self.INVENTED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found.append(pattern)
        assert not found, (
            f"{filepath} contains unsubstantiated statistics matching: {found}\n"
            f"Remove or replace with qualitative claims, or add measurement methodology"
        )


# ---------------------------------------------------------------------------
# 8. Hook event name accuracy
# ---------------------------------------------------------------------------

class TestHookEventNames:
    """Documentation must use correct Claude Code hook event names."""

    VALID_EVENTS = {
        "PreToolUse", "PostToolUse", "UserPromptSubmit",
        "SubagentStop", "SessionStart", "Stop",
    }
    INVALID_EVENTS = {
        "PrePromptSubmit",  # Common mistake — correct name is UserPromptSubmit
    }

    @pytest.mark.parametrize("filepath", [
        "README.md",
        "CLAUDE.md",
    ])
    def test_no_invalid_event_names(self, filepath):
        text = _read(ROOT / filepath)
        found = [ev for ev in self.INVALID_EVENTS if ev in text]
        assert not found, (
            f"{filepath} uses invalid hook event names: {found}\n"
            f"Valid events: {sorted(self.VALID_EVENTS)}"
        )

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
    """ARCHITECTURE-OVERVIEW.md component counts must match reality."""

    @pytest.fixture
    def architecture_overview_md(self) -> str:
        return _read(ROOT / "docs" / "ARCHITECTURE-OVERVIEW.md")

    def test_active_agent_count(self, architecture_overview_md):
        actual = _count_files(PLUGIN / "agents", "*.md", exclude_dirs=["archived"])
        documented = _extract_number(architecture_overview_md, r"(\d+)\s+agents?\s*\(")
        assert documented is not None, "Docs missing agent count"
        assert actual == documented, (
            f"Active agents: {actual} on disk, {documented} in docs"
        )

    def test_archived_agent_count(self, architecture_overview_md):
        actual = _count_files(PLUGIN / "agents" / "archived", "*.md")
        documented = _extract_number(architecture_overview_md, r"\((\d+)\s+archived\)")
        assert documented is not None, "Docs missing archived agent count"
        assert actual == documented, (
            f"Archived agents: {actual} on disk, {documented} in docs"
        )

    def test_skill_count(self, architecture_overview_md):
        actual = sum(1 for _ in PLUGIN.glob("skills/*/SKILL.md")
                     if "archived" not in str(_))
        documented = _extract_number(architecture_overview_md, r"(\d+)\s+skills?")
        assert documented is not None, "Docs missing skill count"
        assert actual == documented, (
            f"Skills: {actual} on disk, {documented} in docs"
        )

    def test_command_count(self, architecture_overview_md):
        actual = _count_files(PLUGIN / "commands", "*.md", exclude_dirs=["archived"])
        documented = _extract_number(architecture_overview_md, r"(\d+)\s+active commands?")
        assert documented is not None, "Docs missing command count"
        assert actual == documented, (
            f"Commands: {actual} on disk, {documented} in docs"
        )

    def test_library_count(self, architecture_overview_md):
        # Per validate_structure.py:_count_libraries() (Issue #1140) — exclude
        # __init__.py (package markers) and htmlcov/ (coverage artifact).
        actual = sum(
            1 for f in (PLUGIN / "lib").rglob("*.py")
            if f.is_file()
            and "__pycache__" not in f.parts
            and "htmlcov" not in f.parts
            and f.name != "__init__.py"
        )
        documented = _extract_number(architecture_overview_md, r"(\d+)\s+libraries")
        assert documented is not None, "Docs missing library count"
        assert actual == documented, (
            f"Libraries: {actual} on disk, {documented} in docs"
        )

    def test_active_hook_count(self, architecture_overview_md):
        # Per validate_structure.py:_count_hooks() (Issue #1140) — only .py files,
        # excluding __init__.py. Shell hooks are tooling, not counted here.
        hooks_dir = PLUGIN / "hooks"
        actual = sum(
            1 for f in hooks_dir.iterdir()
            if f.is_file()
            and f.suffix == ".py"
            and f.name != "__init__.py"
            and not f.name.startswith(".")
        )
        documented = _extract_number(architecture_overview_md, r"(\d+)\s+active hooks?")
        assert documented is not None, "Docs missing hook count"
        assert actual == documented, (
            f"Active hooks: {actual} on disk (.py only), {documented} in docs"
        )

    def test_archived_hook_count(self, architecture_overview_md):
        archived_dir = PLUGIN / "hooks" / "archived"
        actual = sum(1 for f in archived_dir.iterdir()
                     if f.suffix in (".py", ".sh") and not f.name.endswith(",cover"))
        # Extract from pattern like "21 active hooks (62 archived)"
        documented = _extract_number(architecture_overview_md, r"hooks?\s*\((\d+)\s+archived\)")
        assert documented is not None, "Docs missing archived hook count"
        assert actual == documented, (
            f"Archived hooks: {actual} on disk, {documented} in docs"
        )

    def test_template_count(self):
        actual = len(list(PLUGIN.glob("templates/settings.*.json")))
        # Content allocation (Issue #1120): settings template count lives in
        # docs/RUNBOOK.md (operational reference), not PROJECT.md (strategic
        # scope). The CLAUDE.md component-counts line is an accepted fallback.
        pattern = r"(\d+)\s+settings templates?"
        documented = _extract_number(_read(ROOT / "docs" / "RUNBOOK.md"), pattern)
        if documented is None:
            documented = _extract_number(_read(ROOT / "CLAUDE.md"), pattern)
        assert documented is not None, (
            "Settings template count missing from both docs/RUNBOOK.md and CLAUDE.md"
        )
        assert actual == documented, (
            f"Settings templates: {actual} on disk, {documented} in docs"
        )

    def test_claude_md_component_count_drift(self):
        """Real CLAUDE.md must pass scripts/validate_structure.py::check_component_count_drift().

        Closes the per-commit-coverage gap: check_component_count_drift() existed
        since #1140 but was only exercised by unit tests with monkeypatched inputs.
        Real CLAUDE.md was validated only when someone ran /health-check.
        """
        import importlib.util
        script_path = ROOT / "scripts" / "validate_structure.py"
        spec = importlib.util.spec_from_file_location("validate_structure", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        errors = mod.check_component_count_drift()
        assert errors == [], (
            f"CLAUDE.md component-count drift detected:\n" + "\n".join(errors)
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
            # implement-batch, implement-resume, implement-fix are sub-commands of /implement
            if name in ("implement-batch", "implement-resume", "implement-fix"):
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
# 3b. COMMANDS.md sync with on-disk user-invocable commands
# ---------------------------------------------------------------------------

class TestCommandsMdSync:
    """plugins/autonomous-dev/docs/COMMANDS.md must enumerate every
    user-invocable command and only user-invocable commands."""

    @pytest.fixture
    def user_invocable_commands(self) -> set[str]:
        """Parse frontmatter for `user-invocable: true` commands."""
        cmds = set()
        for f in (PLUGIN / "commands").glob("*.md"):
            if "archived" in str(f) or f.name == "README.md":
                continue
            text = f.read_text(encoding="utf-8")
            # Frontmatter is between first two `---` lines
            m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
            if not m:
                continue
            if re.search(r"^user-invocable:\s*true\b", m.group(1), re.MULTILINE):
                cmds.add(f.stem)
        return cmds

    @pytest.fixture
    def commands_md_table_rows(self) -> list[str]:
        """Extract command names from Active Commands table in COMMANDS.md."""
        text = _read(PLUGIN / "docs" / "COMMANDS.md")
        # Slice from "## Active Commands" to next "## " header
        m = re.search(r"^## Active Commands\s*$(.*?)^## ", text, re.DOTALL | re.MULTILINE)
        assert m, "COMMANDS.md missing '## Active Commands' section"
        section = m.group(1)
        # Match table rows like "| `/cmd-name` | ..."
        rows = re.findall(r"^\|\s*`/([\w-]+)`\s*\|", section, re.MULTILINE)
        return rows

    def test_commands_md_row_count_matches_disk(
        self, user_invocable_commands, commands_md_table_rows
    ):
        """Row count in Active Commands table = user-invocable file count on disk."""
        assert len(commands_md_table_rows) == len(user_invocable_commands), (
            f"COMMANDS.md has {len(commands_md_table_rows)} active rows; "
            f"disk has {len(user_invocable_commands)} user-invocable commands.\n"
            f"In file not in table: {sorted(user_invocable_commands - set(commands_md_table_rows))}\n"
            f"In table not on disk: {sorted(set(commands_md_table_rows) - user_invocable_commands)}"
        )

    def test_every_user_invocable_command_is_documented(
        self, user_invocable_commands, commands_md_table_rows
    ):
        """Every user-invocable command on disk must appear in COMMANDS.md table."""
        documented = set(commands_md_table_rows)
        missing = user_invocable_commands - documented
        assert not missing, (
            f"User-invocable commands on disk but missing from COMMANDS.md table: "
            f"{sorted(missing)}"
        )

    def test_commands_md_row_count_matches_user_facing_frontmatter(self):
        """Issue #1159: COMMANDS.md row count must equal the on-disk count of
        `user_facing: true` command files. Prevents catalogue drift."""
        # Count user_facing: true files
        user_facing_count = 0
        commands_path = PLUGIN / "commands"
        for f in commands_path.glob("*.md"):
            if "archived" in str(f) or f.name == "README.md":
                continue
            text = f.read_text(encoding="utf-8")
            # Parse front-matter manually
            if re.search(r'^user_facing:\s*true\s*$', text, re.MULTILINE):
                user_facing_count += 1
        
        # Count COMMANDS.md command entries (table rows)
        commands_md = _read(PLUGIN / "docs" / "COMMANDS.md")
        # Slice from "## Active Commands" to next "## " header
        m = re.search(r"^## Active Commands\s*$(.*?)^## ", commands_md, re.DOTALL | re.MULTILINE)
        assert m, "COMMANDS.md missing '## Active Commands' section"
        section = m.group(1)
        # Match table rows like "| `/cmd-name` | ..."
        commands_md_count = len(re.findall(r"^\|\s*`/([\w-]+)`\s*\|", section, re.MULTILINE))
        
        # Assert equal, with a helpful failure message listing the diff
        assert commands_md_count == user_facing_count, (
            f"COMMANDS.md has {commands_md_count} commands in Active Commands table, "
            f"but there are {user_facing_count} files with 'user_facing: true' on disk.\n"
            f"This indicates the catalogue has drifted from the actual user-facing commands."
        )


# ---------------------------------------------------------------------------
# 4. Pipeline step count consistency
# ---------------------------------------------------------------------------

class TestPipelineConsistency:
    """Pipeline description must be consistent across all docs."""

    def test_claude_md_says_8_steps(self):
        text = _read(ROOT / "CLAUDE.md")
        m = re.search(r"(\d+)-step\s+SDLC", text)
        assert m, "Docs missing N-step SDLC description"
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


# ---------------------------------------------------------------------------
# 9. Issue #1226 — Closes-ref injection structural guards
# ---------------------------------------------------------------------------

class TestClosesRefInjection:
    """implement.md must contain STEP 12.7 anchor invoking create_commit_with_agent_message.

    Regression guard for Issue #1226: ensures the commit funnel for
    single-issue --issues N runs is documented and correctly wired.
    Prevents --no-verify from being introduced in the commit path.
    """

    @pytest.fixture
    def implement_md(self) -> str:
        return _read(PLUGIN / "commands" / "implement.md")

    def test_implement_md_contains_step_12_7_anchor(self, implement_md: str) -> None:
        """implement.md must contain a STEP 12.7 section (Issue #1226)."""
        assert "STEP 12.7" in implement_md, (
            "implement.md is missing the 'STEP 12.7' anchor required by Issue #1226.\n"
            "The single-issue commit must route through create_commit_with_agent_message()."
        )

    def test_implement_md_step_12_7_references_helper(self, implement_md: str) -> None:
        """STEP 12.7 in implement.md must reference create_commit_with_agent_message."""
        assert "create_commit_with_agent_message" in implement_md, (
            "implement.md is missing 'create_commit_with_agent_message' reference.\n"
            "STEP 12.7 must invoke the helper so Closes #N is auto-injected."
        )

    def test_implement_md_no_no_verify_in_commit_steps(self, implement_md: str) -> None:
        """Regression guard: --no-verify must NOT appear as an active flag in STEP 12.7/L4.7.

        The plan-critic (round-1) flagged --no-verify as a serious risk in the
        commit path. This test guards against it being re-introduced.
        Only the FORBIDDEN notice text referencing it is allowed (in the HARD GATE warning).
        """
        # Extract only the STEP 12.7 and STEP L4.7 regions.
        # We look for --no-verify appearing as a shell flag (preceded by space/quote, not
        # embedded inside a FORBIDDEN notice). The HARD GATE notice says
        # "NO `--no-verify` anywhere" — that text itself is allowed; actual usage is not.
        step_127_idx = implement_md.find("### STEP 12.7")
        step_13_idx = implement_md.find("### STEP 13:")
        step_l47_idx = implement_md.find("### STEP L4.7")
        step_l5_idx = implement_md.find("### STEP L5:")

        regions = []
        if step_127_idx != -1 and step_13_idx != -1:
            regions.append(("STEP 12.7", implement_md[step_127_idx:step_13_idx]))
        if step_l47_idx != -1 and step_l5_idx != -1:
            regions.append(("STEP L4.7", implement_md[step_l47_idx:step_l5_idx]))

        for region_name, region_text in regions:
            # Strip lines that contain the FORBIDDEN notice (the warning itself).
            active_lines = [
                line for line in region_text.splitlines()
                if "--no-verify" in line and "FORBIDDEN" not in line and "NO `--no-verify`" not in line
            ]
            assert not active_lines, (
                f"{region_name} contains '--no-verify' outside of a FORBIDDEN notice:\n"
                + "\n".join(active_lines)
                + "\nDo NOT add --no-verify to the commit path (Issue #1226 security constraint)."
            )

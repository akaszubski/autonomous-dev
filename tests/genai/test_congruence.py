"""Cross-reference congruence tests using GenAI.

Validates that multiple sources of truth stay in sync:
- CLAUDE.md ↔ Codebase reality (agents, commands, hooks on disk)
- Agent prompts ↔ Command prompts (agent references match)
- Hook registry docs ↔ Actual hook files
- Manifest ↔ Plugin structure
- Policy file ↔ Hook code (auto-approval settings)
- Implement command ↔ Implementer agent (enforcement gates)

These tests READ both sources and ask the LLM to find mismatches.
"""

import json
import re
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


# ============================================================================
# CLAUDE.md ↔ Codebase Reality
# ============================================================================


class TestDocCodeCongruence:
    """Verify CLAUDE.md accurately describes the actual codebase."""

    def test_documented_agent_count_matches_disk(self, genai):
        """Agent count in CLAUDE.md must match actual agents on disk."""
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()

        agents_dir = PLUGIN_ROOT / "agents"
        agents_on_disk = sorted(
            f.stem for f in agents_dir.glob("*.md")
            if "archived" not in str(f) and f.stem != "README"
        )
        archived_dir = agents_dir / "archived"
        archived_agents = sorted(f.stem for f in archived_dir.glob("*.md")) if archived_dir.exists() else []

        result = genai.judge(
            question="Does CLAUDE.md agent count match the agents actually on disk?",
            context=f"**CLAUDE.md:**\n{claude_md[:2000]}\n\n"
            f"**Active agents on disk ({len(agents_on_disk)}):** {agents_on_disk}\n\n"
            f"**Archived agents ({len(archived_agents)}):** {archived_agents}",
            criteria="CLAUDE.md states specific agent counts. These must match disk reality. "
            "Active count should match non-archived .md files in agents/. "
            "Archived count should match agents/archived/ contents. "
            "Deduct 2 points per count mismatch.",
        )
        assert result["score"] >= 5, f"Agent count drift: {result['reasoning']}"

    def test_documented_command_list_matches_disk(self, genai):
        """Commands listed in CLAUDE.md must match actual command files."""
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()

        commands_dir = PLUGIN_ROOT / "commands"
        commands_on_disk = sorted(f.stem for f in commands_dir.glob("*.md")) if commands_dir.exists() else []

        result = genai.judge(
            question="Do commands listed in CLAUDE.md match the command files on disk?",
            context=f"**CLAUDE.md (Commands section):**\n{claude_md[:4000]}\n\n"
            f"**Command files on disk ({len(commands_on_disk)}):** {commands_on_disk}",
            criteria="Commands in CLAUDE.md table should exist as .md files in commands/. "
            "Sub-commands (implement-batch, implement-resume) are modes of parent commands — acceptable to omit. "
            "Utility/internal commands (audit, audit-tests) may be unlisted — minor issue. "
            "Deduct 1 point per major missing command, 0.5 per minor/sub-command.",
        )
        assert result["score"] >= 5, f"Command list drift: {result['reasoning']}"

    def test_documented_file_paths_exist(self, genai):
        """File paths referenced in CLAUDE.md should actually exist."""
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()

        paths = re.findall(r'(?:plugins/|docs/|tests/|scripts/)[\w/.-]+\.\w+', claude_md)
        unique_paths = sorted(set(paths))

        existing = []
        missing = []
        for p in unique_paths:
            full = PROJECT_ROOT / p
            if full.exists():
                existing.append(p)
            else:
                missing.append(p)

        result = genai.judge(
            question="Do all file paths referenced in CLAUDE.md actually exist?",
            context=f"**Existing ({len(existing)}):** {', '.join(existing[:20])}\n\n"
            f"**MISSING ({len(missing)}):** {', '.join(missing) if missing else 'None'}",
            criteria="Every file path in CLAUDE.md should exist on disk. "
            "Missing files = docs reference deleted/moved code. "
            "Score 10 if all exist, deduct 2 per missing file.",
        )
        assert result["score"] >= 6, f"CLAUDE.md references missing files: {result['reasoning']}"


# ============================================================================
# Agent Prompts ↔ Command Prompts
# ============================================================================


class TestAgentCommandCongruence:
    """Verify commands reference agents that exist, and vice versa."""

    def test_implement_command_references_valid_agents(self, genai):
        """Agents referenced in implement.md must exist as agent files."""
        implement_cmd = PLUGIN_ROOT / "commands" / "implement.md"
        if not implement_cmd.exists():
            pytest.skip("implement.md not found")

        cmd_content = implement_cmd.read_text()
        agents_on_disk = sorted(
            f.stem for f in (PLUGIN_ROOT / "agents").glob("*.md")
            if "archived" not in str(f)
        )

        result = genai.judge(
            question="Does implement.md only reference agents that exist on disk?",
            context=f"**implement.md:**\n{cmd_content[:4000]}\n\n"
            f"**Agents on disk:** {agents_on_disk}",
            criteria="Agent names referenced in implement.md (researcher, planner, implementer, etc.) "
            "should all have corresponding .md files in agents/. "
            "A reference to a non-existent agent = broken pipeline step. "
            "Deduct 3 points per phantom agent reference.",
        )
        assert result["score"] >= 5, f"Implement ↔ agents drift: {result['reasoning']}"

    def test_agents_referenced_by_at_least_one_command(self, genai):
        """Each active agent should be referenced by at least one command."""
        agents_on_disk = sorted(
            f.stem for f in (PLUGIN_ROOT / "agents").glob("*.md")
            if "archived" not in str(f) and f.stem != "README"
        )

        # Pre-compute: search all command content for each agent name
        all_cmd_content = ""
        commands_dir = PLUGIN_ROOT / "commands"
        if commands_dir.exists():
            for f in commands_dir.glob("*.md"):
                all_cmd_content += f.read_text(errors="ignore") + "\n"

        referenced = []
        orphaned = []
        for agent in agents_on_disk:
            if agent in all_cmd_content or agent.replace("-", "_") in all_cmd_content:
                referenced.append(agent)
            else:
                orphaned.append(agent)

        result = genai.judge(
            question="Are the orphaned agents (not referenced by any command) acceptable?",
            context=f"**Active agents ({len(agents_on_disk)}):** {agents_on_disk}\n\n"
            f"**Referenced by commands ({len(referenced)}):** {referenced}\n\n"
            f"**NOT referenced by any command ({len(orphaned)}):** {orphaned}\n\n"
            f"NOTE: The 'Referenced' and 'NOT referenced' lists were computed by searching "
            f"all command file contents for each agent name. Trust these lists as accurate.",
            criteria="Most agents should be referenced by at least one command. "
            "Some utility agents (commit-message-generator, sync-validator, quality-validator) "
            "may be invoked programmatically rather than by commands — this is acceptable. "
            "Score based on referenced percentage: >80% = 8+, >60% = 6+, >40% = 4+. "
            "Deduct 1 per clearly orphaned agent that serves no purpose.",
        )
        assert result["score"] >= 4, f"Orphaned agents: {result['reasoning']}"


# ============================================================================
# Hook Registry ↔ Hook Files
# ============================================================================


class TestHookCongruence:
    """Verify hook documentation matches actual hook files."""

    def test_hook_registry_matches_files(self, genai):
        """HOOK-REGISTRY.md must list all active hook files."""
        registry_path = PROJECT_ROOT / "docs" / "HOOK-REGISTRY.md"
        if not registry_path.exists():
            pytest.skip("HOOK-REGISTRY.md not found")

        registry_content = registry_path.read_text()

        hooks_dir = PLUGIN_ROOT / "hooks"
        hook_files = sorted(
            f.stem for f in hooks_dir.glob("*.py")
            if f.stem != "__init__" and "archived" not in str(f) and not f.stem.endswith(".disabled")
        )

        # Pre-compute which hooks are documented vs not
        documented = set()
        for hook in hook_files:
            if hook in registry_content:
                documented.add(hook)
        undocumented = sorted(set(hook_files) - documented)

        result = genai.judge(
            question="Does HOOK-REGISTRY.md list all active hook files?",
            context=f"**Hook files on disk ({len(hook_files)}):** {hook_files}\n\n"
            f"**Documented in registry ({len(documented)}):** {sorted(documented)}\n\n"
            f"**UNDOCUMENTED ({len(undocumented)}):** {undocumented}",
            criteria="Every active .py file in hooks/ should be mentioned in HOOK-REGISTRY.md. "
            "Score based on percentage documented: >90% = 8+, >75% = 6+, >50% = 4+. "
            "Deduct 1 point per undocumented hook.",
        )
        assert result["score"] >= 5, f"Hook registry drift: {result['reasoning']}"


# ============================================================================
# Manifest ↔ Plugin Structure
# ============================================================================


class TestManifestCongruence:
    """Verify manifest files match actual plugin structure."""

    def test_manifest_lists_all_components(self, genai):
        """Plugin manifest should reference all agents, commands, hooks."""
        manifest_path = PLUGIN_ROOT / "install_manifest.json"
        if not manifest_path.exists():
            for alt in [PLUGIN_ROOT / "config" / "install_manifest.json", PLUGIN_ROOT / "plugin.json"]:
                if alt.exists():
                    manifest_path = alt
                    break
            else:
                pytest.skip("No manifest file found")

        manifest = json.loads(manifest_path.read_text())
        manifest_text = json.dumps(manifest)

        # Pre-compute: check each component type
        component_checks = {}
        for comp_type, (subdir, pattern) in [
            ("agents", ("agents", "*.md")),
            ("commands", ("commands", "*.md")),
            ("hooks", ("hooks", "*.py")),
        ]:
            comp_dir = PLUGIN_ROOT / subdir
            on_disk = sorted(
                f.name for f in comp_dir.glob(pattern)
                if "archived" not in str(f) and f.stem != "__init__" and f.stem != "README"
            )
            in_manifest = [f for f in on_disk if f in manifest_text]
            missing = [f for f in on_disk if f not in manifest_text]
            component_checks[comp_type] = {"total": len(on_disk), "in_manifest": len(in_manifest), "missing": missing}

        result = genai.judge(
            question="Does the manifest accurately list all plugin components?",
            context=f"**Component coverage:**\n"
            + "\n".join(f"  {t}: {c['in_manifest']}/{c['total']} in manifest, missing: {c['missing']}"
                        for t, c in component_checks.items()),
            criteria="Manifest should reference agents, commands, and hooks that exist on disk. "
            "Missing from manifest = component won't be installed. "
            "Score 10 if all covered, deduct 1 per missing component.",
        )
        assert result["score"] >= 5, f"Manifest ↔ structure drift: {result['reasoning']}"


# ============================================================================
# Policy File ↔ Hook Code
# ============================================================================


class TestPolicyCongruence:
    """Verify auto-approval policy matches hook implementation."""

    def test_policy_always_allowed_covers_native_tools(self, genai):
        """Policy always_allowed should include all native Claude Code tools."""
        policy_path = PLUGIN_ROOT / "config" / "auto_approve_policy.json"
        if not policy_path.exists():
            pytest.skip("auto_approve_policy.json not found")

        policy = json.loads(policy_path.read_text())

        hook_path = PLUGIN_ROOT / "hooks" / "unified_pre_tool.py"
        hook_content = hook_path.read_text() if hook_path.exists() else "NOT FOUND"

        result = genai.judge(
            question="Does the policy file's always_allowed list cover all native Claude Code tools?",
            context=f"**Policy always_allowed:** {policy.get('tools', {}).get('always_allowed', [])}\n\n"
            f"**Hook NATIVE_TOOLS set (from unified_pre_tool.py):**\n{hook_content[:2000]}",
            criteria="The policy always_allowed list should include all tools that the hook's "
            "NATIVE_TOOLS set bypasses. Native tools: Read, Write, Edit, Bash, Glob, Grep, "
            "WebFetch, WebSearch, Task, TaskCreate, TaskUpdate, TaskList, TaskGet. "
            "Missing tools = rejected by auto-approval engine. "
            "Deduct 2 per missing native tool.",
        )
        assert result["score"] >= 5, f"Policy ↔ native tools drift: {result['reasoning']}"


# ============================================================================
# Implement Command ↔ Implementer Agent (Enforcement Gates)
# ============================================================================


class TestEnforcementCongruence:
    """Verify enforcement gates are consistent between command and agent."""

    def test_implement_and_implementer_share_forbidden_list(self, genai):
        """implement.md and implementer.md should have matching FORBIDDEN behaviors."""
        implement_path = PLUGIN_ROOT / "commands" / "implement.md"
        implementer_path = PLUGIN_ROOT / "agents" / "implementer.md"

        if not implement_path.exists() or not implementer_path.exists():
            pytest.skip("implement.md or implementer.md not found")

        implement_content = implement_path.read_text()
        implementer_content = implementer_path.read_text()

        result = genai.judge(
            question="Do implement.md and implementer.md have matching FORBIDDEN behavior lists?",
            context=f"**implement.md (HARD GATE sections):**\n{implement_content[:5000]}\n\n"
            f"**implementer.md (HARD GATE sections):**\n{implementer_content[:5000]}",
            criteria="Both files should define FORBIDDEN behaviors for: "
            "1. Test gate (no 'X% is good enough') "
            "2. Anti-stubbing (no NotImplementedError shortcuts) "
            "If one file has a gate the other lacks = enforcement gap. "
            "Score 10 = identical gates, 5 = same spirit, 0 = contradictory.",
        )
        assert result["score"] >= 5, f"Enforcement gate drift: {result['reasoning']}"

    def test_implementer_skills_exist(self, genai):
        """Skills referenced in implementer.md should exist as skill directories."""
        implementer_path = PLUGIN_ROOT / "agents" / "implementer.md"
        if not implementer_path.exists():
            pytest.skip("implementer.md not found")

        content = implementer_path.read_text()
        skills_dir = PLUGIN_ROOT / "skills"
        skills_on_disk = sorted(
            d.name for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ) if skills_dir.exists() else []

        result = genai.judge(
            question="Do skills referenced in implementer.md exist on disk?",
            context=f"**implementer.md:**\n{content[:4000]}\n\n"
            f"**Skills on disk:** {skills_on_disk}",
            criteria="Skill names referenced in the agent prompt should have corresponding "
            "directories in skills/. Missing skills = agent tries to load non-existent skill. "
            "Deduct 2 per phantom skill reference.",
        )
        assert result["score"] >= 5, f"Implementer ↔ skills drift: {result['reasoning']}"

    def test_claude_md_matches_project_md_scope(self, genai):
        """CLAUDE.md and PROJECT.md should agree on project scope and capabilities."""
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()
        project_md_path = PROJECT_ROOT / ".claude" / "PROJECT.md"
        if not project_md_path.exists():
            pytest.skip("PROJECT.md not found")
        project_md = project_md_path.read_text()

        result = genai.judge(
            question="Do CLAUDE.md and PROJECT.md agree on project scope and capabilities?",
            context=f"**CLAUDE.md:**\n{claude_md[:3000]}\n\n"
            f"**PROJECT.md:**\n{project_md[:3000]}",
            criteria="CLAUDE.md (dev instructions) and PROJECT.md (alignment source of truth) "
            "should agree on: what the plugin does, pipeline steps, component types. "
            "Contradictions = developers get conflicting guidance. "
            "Score 10 = fully consistent, deduct 2 per contradiction.",
        )
        assert result["score"] >= 5, f"CLAUDE.md ↔ PROJECT.md drift: {result['reasoning']}"

    def test_readme_matches_project_md(self, genai):
        """README.md and PROJECT.md should agree on project description."""
        readme_path = PROJECT_ROOT / "README.md"
        project_md_path = PROJECT_ROOT / ".claude" / "PROJECT.md"
        if not readme_path.exists() or not project_md_path.exists():
            pytest.skip("README.md or PROJECT.md not found")

        readme = readme_path.read_text()
        project_md = project_md_path.read_text()

        result = genai.judge(
            question="Do README.md and PROJECT.md agree on what the project does?",
            context=f"**README.md:**\n{readme[:3000]}\n\n"
            f"**PROJECT.md:**\n{project_md[:3000]}",
            criteria="README (user-facing) and PROJECT.md (alignment truth) "
            "should describe the same project. Different audiences but same facts. "
            "Score 10 = consistent, deduct 2 per factual disagreement.",
        )
        assert result["score"] >= 5, f"README ↔ PROJECT.md drift: {result['reasoning']}"

    def test_implement_step_count_matches_code(self, genai):
        """STEP markers in implement.md should be sequential and complete."""
        implement_path = PLUGIN_ROOT / "commands" / "implement.md"
        if not implement_path.exists():
            pytest.skip("implement.md not found")

        content = implement_path.read_text()
        steps = re.findall(r'STEP\s+(\d+)', content)
        unique_steps = sorted(set(int(s) for s in steps))

        result = genai.judge(
            question="Are STEP markers in implement.md sequential and complete?",
            context=f"**STEP numbers found:** {unique_steps}\n\n"
            f"**implement.md excerpt:**\n{content[:4000]}",
            criteria="STEPs should be sequential (1, 2, 3, ...) with no gaps. "
            "Each STEP should have a clear purpose. "
            "Duplicate STEP numbers = ambiguous execution order. "
            "Score 10 = clean sequence, deduct 2 per gap or duplicate.",
        )
        assert result["score"] >= 5, f"STEP sequence issues: {result['reasoning']}"

    def test_docs_no_hardcoded_counts(self, genai):
        """README.md and CLAUDE.md should not have hardcoded component counts that drift."""
        readme = (PROJECT_ROOT / "README.md").read_text()
        claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text()

        # Count actual components on disk
        agents = len([f for f in (PLUGIN_ROOT / "agents").glob("*.md")
                      if "archived" not in str(f) and f.stem != "README"])
        commands = len(list((PLUGIN_ROOT / "commands").glob("*.md")))
        hooks = len([f for f in (PLUGIN_ROOT / "hooks").glob("*.py")
                     if f.stem != "__init__" and "archived" not in str(f)])

        # Find hardcoded counts in README (excluding badges, code blocks)
        count_refs = re.findall(r'\b(\d+)\s+(?:active\s+)?(?:hook|agent|skill|command|librari)', readme, re.I)

        result = genai.judge(
            question="Do README.md and CLAUDE.md avoid brittle hardcoded component counts?",
            context=f"**Actual counts:** agents={agents}, commands={commands}, hooks={hooks}\n\n"
            f"**Hardcoded count references in README:** {count_refs}\n\n"
            f"**CLAUDE.md Component Counts line:** "
            f"{[l for l in claude_md.splitlines() if 'agents' in l and 'skills' in l and 'commands' in l]}\n\n"
            f"Note: CLAUDE.md is allowed ONE canonical counts line (validated by smoke tests). "
            f"README should NOT duplicate counts — they drift.",
            criteria="README.md should avoid hardcoded component counts (they go stale). "
            "Descriptive labels ('Pipeline Agents', 'Active Hooks') are fine. "
            "CLAUDE.md may have ONE counts line (it's validated by automated tests). "
            "Score 10 = no brittle counts in README, deduct 2 per hardcoded count found.",
        )
        assert result["score"] >= 5, f"Hardcoded counts in docs: {result['reasoning']}"

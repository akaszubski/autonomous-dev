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
            context=f"**CLAUDE.md:**\n{claude_md[:2000]}\n\n"
            f"**Command files on disk ({len(commands_on_disk)}):** {commands_on_disk}",
            criteria="Commands in CLAUDE.md table should exist as .md files in commands/. "
            "Command files on disk not in CLAUDE.md = undocumented. "
            "CLAUDE.md commands without files = dead documentation. "
            "Deduct 1 point per mismatch.",
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

        all_cmd_content = ""
        commands_dir = PLUGIN_ROOT / "commands"
        if commands_dir.exists():
            for f in commands_dir.glob("*.md"):
                all_cmd_content += f.read_text(errors="ignore") + "\n"

        result = genai.judge(
            question="Is each active agent referenced by at least one command?",
            context=f"**Active agents:** {agents_on_disk}\n\n"
            f"**All command content (concatenated):**\n{all_cmd_content[:5000]}",
            criteria="Each agent should appear in at least one command's text. "
            "Unreferenced agents = orphaned, never invoked by any workflow. "
            "Score 10 = all referenced, deduct 1 per orphaned agent.",
        )
        assert result["score"] >= 5, f"Orphaned agents: {result['reasoning']}"


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

        result = genai.judge(
            question="Does HOOK-REGISTRY.md list all active hook files?",
            context=f"**HOOK-REGISTRY.md:**\n{registry_content[:4000]}\n\n"
            f"**Hook files on disk ({len(hook_files)}):** {hook_files}",
            criteria="Every active .py file in hooks/ should be documented in HOOK-REGISTRY.md. "
            "Files in registry but not on disk = dead docs. "
            "Files on disk but not in registry = undocumented hooks. "
            "Deduct 1 point per mismatch.",
        )
        assert result["score"] >= 5, f"Hook registry drift: {result['reasoning']}"


# ============================================================================
# Manifest ↔ Plugin Structure
# ============================================================================


class TestManifestCongruence:
    """Verify manifest files match actual plugin structure."""

    def test_manifest_lists_all_components(self, genai):
        """Plugin manifest should reference all agents, commands, hooks."""
        manifest_path = PLUGIN_ROOT / "manifest.json"
        if not manifest_path.exists():
            # Try alternate locations
            for alt in [PLUGIN_ROOT / "plugin.json", PROJECT_ROOT / "manifest.json"]:
                if alt.exists():
                    manifest_path = alt
                    break
            else:
                pytest.skip("No manifest file found")

        manifest = json.loads(manifest_path.read_text())

        agents = sorted(f.stem for f in (PLUGIN_ROOT / "agents").glob("*.md") if "archived" not in str(f))
        commands = sorted(f.stem for f in (PLUGIN_ROOT / "commands").glob("*.md"))
        hooks = sorted(f.stem for f in (PLUGIN_ROOT / "hooks").glob("*.py") if f.stem != "__init__")

        result = genai.judge(
            question="Does the manifest accurately list all plugin components?",
            context=f"**Manifest:**\n{json.dumps(manifest, indent=2)[:3000]}\n\n"
            f"**Agents on disk:** {agents}\n**Commands on disk:** {commands}\n**Hooks on disk:** {hooks}",
            criteria="Manifest should reference agents, commands, and hooks that exist on disk. "
            "Missing from manifest = component won't be installed. "
            "In manifest but not on disk = broken install. "
            "Deduct 1 point per discrepancy.",
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
            context=f"**Policy always_allowed:** {policy.get('always_allowed', [])}\n\n"
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

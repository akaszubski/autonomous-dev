"""GenAI tests for PROJECT.md alignment enforcement.

Validates that PROJECT.md stays aligned with codebase reality.
PROJECT.md is the source of truth for strategic direction — if the codebase
diverges from PROJECT.md, either the code or PROJECT.md must be updated.

These tests enforce the "update PROJECT.md or don't proceed" principle.
"""

import json
import re
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"
PROJECT_MD = PROJECT_ROOT / ".claude" / "PROJECT.md"


def _load_project_md():
    """Load PROJECT.md content."""
    if not PROJECT_MD.exists():
        pytest.skip("PROJECT.md not found at .claude/PROJECT.md")
    return PROJECT_MD.read_text()


class TestProjectMdGoalsAlignment:
    """Verify codebase aligns with PROJECT.md GOALS section."""

    def test_pipeline_steps_match_goals(self, genai):
        """The implement command must execute all pipeline steps declared in GOALS."""
        project_md = _load_project_md()
        implement_path = PLUGIN_ROOT / "commands" / "implement.md"
        if not implement_path.exists():
            pytest.skip("implement.md not found")

        implement_content = implement_path.read_text()

        result = genai.judge(
            question="Does the implement command execute all pipeline steps declared in PROJECT.md GOALS?",
            context=f"**PROJECT.md GOALS section:**\n{project_md[:2000]}\n\n"
            f"**implement.md (pipeline steps):**\n{implement_content[:4000]}",
            criteria="PROJECT.md declares: research → plan → test → implement → review → security → docs → commit. "
            "The implement command must orchestrate ALL these steps. "
            "Missing steps = pipeline doesn't match stated goals. "
            "Deduct 2 per missing step.",
        )
        assert result["score"] >= 5, f"Pipeline ↔ GOALS drift: {result['reasoning']}"

    def test_enforcement_hooks_enforce_goals(self, genai):
        """Hooks should enforce the quality gates declared in GOALS."""
        project_md = _load_project_md()

        hooks_dir = PLUGIN_ROOT / "hooks"
        hook_summaries = {}
        for hook in sorted(hooks_dir.glob("*.py")):
            if hook.stem == "__init__" or "archived" in str(hook):
                continue
            content = hook.read_text(errors="ignore")
            docstring = re.search(r'"""([\s\S]*?)"""', content[:2000])
            hook_summaries[hook.stem] = docstring.group(1)[:200] if docstring else "NO DOCSTRING"

        result = genai.judge(
            question="Do hooks enforce the quality requirements stated in PROJECT.md GOALS?",
            context=f"**PROJECT.md (relevant sections):**\n{project_md[:3000]}\n\n"
            f"**Active hooks and their purposes:**\n"
            + "\n".join(f"  {name}: {desc}" for name, desc in hook_summaries.items()),
            criteria="PROJECT.md states: 'Every step. Every feature. Documentation, tests, and code stay in sync.' "
            "and 'Professional quality enforced via hooks (can't skip or bypass)'. "
            "Hooks should enforce: alignment, security, tests, docs, file organization. "
            "Score 10 = all enforced, deduct 2 per gap.",
        )
        assert result["score"] >= 5, f"Hook enforcement ↔ GOALS gap: {result['reasoning']}"


class TestProjectMdScopeAlignment:
    """Verify codebase stays within PROJECT.md SCOPE."""

    def test_commands_are_in_scope(self, genai):
        """All commands should serve features listed in SCOPE."""
        project_md = _load_project_md()

        commands_dir = PLUGIN_ROOT / "commands"
        command_summaries = {}
        for cmd in sorted(commands_dir.glob("*.md")):
            content = cmd.read_text(errors="ignore")
            # Extract description from frontmatter
            desc_match = re.search(r'description:\s*"?([^"\n]+)', content)
            command_summaries[cmd.stem] = desc_match.group(1) if desc_match else content[:200]

        result = genai.judge(
            question="Do all commands serve features listed in PROJECT.md SCOPE?",
            context=f"**PROJECT.md SCOPE section:**\n{project_md}\n\n"
            f"**Commands and descriptions:**\n"
            + "\n".join(f"  /{name}: {desc}" for name, desc in command_summaries.items()),
            criteria="PROJECT.md SCOPE lists in-scope features. Each command should serve one of these. "
            "Commands serving out-of-scope features = scope creep. "
            "Related/utility commands (health-check, sync, status) are acceptable. "
            "Deduct 2 per command that clearly serves an out-of-scope purpose.",
        )
        assert result["score"] >= 5, f"Commands outside SCOPE: {result['reasoning']}"

    def test_agents_serve_pipeline_scope(self, genai):
        """Active agents should serve the pipeline or utility functions in SCOPE."""
        project_md = _load_project_md()

        agents_dir = PLUGIN_ROOT / "agents"
        agent_summaries = {}
        for agent in sorted(agents_dir.glob("*.md")):
            if "archived" in str(agent) or agent.stem == "README":
                continue
            content = agent.read_text(errors="ignore")
            desc_match = re.search(r'description:\s*(.+)', content)
            agent_summaries[agent.stem] = desc_match.group(1).strip() if desc_match else content[:200]

        result = genai.judge(
            question="Do all active agents serve the pipeline or features listed in PROJECT.md SCOPE?",
            context=f"**PROJECT.md SCOPE:**\n{project_md}\n\n"
            f"**Active agents:**\n"
            + "\n".join(f"  {name}: {desc}" for name, desc in agent_summaries.items()),
            criteria="PROJECT.md SCOPE defines what autonomous-dev does. Read the IN Scope list carefully. "
            "Agents should serve pipeline steps (research, plan, test, implement, review, security, docs), "
            "in-scope utilities (batch processing, git automation, MCP security, continuous improvement), "
            "or training pipeline utilities (data curation, quality validation, distributed training) "
            "which are EXPLICITLY listed in PROJECT.md SCOPE. "
            "Only deduct 2 per agent that serves a purpose NOT listed anywhere in the IN Scope section.",
        )
        assert result["score"] >= 5, f"Agents outside SCOPE: {result['reasoning']}"


class TestProjectMdConstraintAlignment:
    """Verify codebase respects PROJECT.md CONSTRAINTS."""

    def test_architecture_matches_constraints(self, genai):
        """Codebase architecture should match the dual-layer system described in CONSTRAINTS/ARCHITECTURE."""
        project_md = _load_project_md()

        # Gather evidence of actual architecture
        hooks = sorted(f.stem for f in (PLUGIN_ROOT / "hooks").glob("*.py")
                       if f.stem != "__init__" and "archived" not in str(f))
        agents = sorted(f.stem for f in (PLUGIN_ROOT / "agents").glob("*.md")
                        if "archived" not in str(f) and f.stem != "README")
        commands = sorted(f.stem for f in (PLUGIN_ROOT / "commands").glob("*.md"))

        result = genai.judge(
            question="Does the codebase architecture match PROJECT.md's ARCHITECTURE section?",
            context=f"**PROJECT.md ARCHITECTURE:**\n{project_md}\n\n"
            f"**Actual components:**\n"
            f"  Hooks (enforcement layer): {hooks}\n"
            f"  Agents (intelligence layer): {agents}\n"
            f"  Commands (user interface): {commands}",
            criteria="PROJECT.md describes a dual-layer system: "
            "Layer 1 = hooks (enforcement, blocking) and Layer 2 = agents (intelligence, advisory). "
            "The actual codebase should reflect this separation. "
            "Hooks should enforce, agents should advise. "
            "Score 10 = clean separation, deduct 2 per violation.",
        )
        assert result["score"] >= 5, f"Architecture ↔ CONSTRAINTS drift: {result['reasoning']}"

    def test_anti_bloat_gates_respected(self, genai):
        """Component counts should be justified — no feature bloat."""
        project_md = _load_project_md()

        hooks = list((PLUGIN_ROOT / "hooks").glob("*.py"))
        agents = list((PLUGIN_ROOT / "agents").glob("*.md"))
        commands = list((PLUGIN_ROOT / "commands").glob("*.md"))
        libs = list((PLUGIN_ROOT / "lib").glob("*.py"))
        skills_dirs = list((PLUGIN_ROOT / "skills").iterdir()) if (PLUGIN_ROOT / "skills").exists() else []

        active_hooks = [f for f in hooks if f.stem != "__init__" and "archived" not in str(f)]
        active_agents = [f for f in agents if "archived" not in str(f) and f.stem != "README"]

        result = genai.judge(
            question="Does the component count respect PROJECT.md's anti-bloat gates?",
            context=f"**PROJECT.md anti-bloat gates:**\n{project_md}\n\n"
            f"**Component counts:**\n"
            f"  Active hooks: {len(active_hooks)}\n"
            f"  Active agents: {len(active_agents)}\n"
            f"  Commands: {len(commands)}\n"
            f"  Libraries: {len(libs)}\n"
            f"  Skill packages: {len(skills_dirs)}\n\n"
            f"**PROJECT.md states**: 'Less is more — Every element serves the mission'\n"
            f"**Anti-bloat gates**: Alignment, Constraint, Minimalism, Value",
            criteria="PROJECT.md emphasizes minimalism and anti-bloat. "
            "High component counts aren't inherently bad IF each serves the mission. "
            "But >150 libs or >40 skills suggests possible bloat. "
            "Score based on whether counts seem justified for an SDLC plugin. "
            "Score 7+ if reasonable, 4-6 if concerning, <4 if clearly bloated.",
        )
        assert result["score"] >= 4, f"Anti-bloat concern: {result['reasoning']}"

    def test_security_constraints_enforced(self, genai):
        """Security constraints in PROJECT.md should have corresponding enforcement."""
        project_md = _load_project_md()

        # Check for security enforcement mechanisms
        security_hook = PLUGIN_ROOT / "hooks" / "security_scan.py"
        security_agent = PLUGIN_ROOT / "agents" / "security-auditor.md"
        policy_file = PLUGIN_ROOT / "config" / "auto_approve_policy.json"

        evidence = {}
        for path, label in [(security_hook, "security_scan hook"),
                            (security_agent, "security-auditor agent"),
                            (policy_file, "auto_approve_policy")]:
            if path.exists():
                content = path.read_text(errors="ignore")
                evidence[label] = content[:1000]
            else:
                evidence[label] = "FILE NOT FOUND"

        result = genai.judge(
            question="Are PROJECT.md security constraints enforced by hooks/agents/config?",
            context=f"**PROJECT.md security constraints:**\n{project_md}\n\n"
            f"**Security enforcement evidence:**\n"
            + "\n".join(f"--- {label} ---\n{content}" for label, content in evidence.items()),
            criteria="PROJECT.md lists security requirements: "
            "no hardcoded secrets, TDD mandatory, tool restrictions, 80% coverage, MCP validation. "
            "Each should have a corresponding enforcement mechanism. "
            "Score 10 = all enforced, deduct 2 per unenforced requirement.",
        )
        assert result["score"] >= 5, f"Security enforcement gap: {result['reasoning']}"

    def test_project_md_version_matches_manifest(self, genai):
        """PROJECT.md version should match install manifest version."""
        project_md = _load_project_md()
        version_match = re.search(r'\*\*Version\*\*:\s*v?([\d.]+)', project_md)
        project_version = version_match.group(1) if version_match else "NOT FOUND"

        manifest_path = PLUGIN_ROOT / "install_manifest.json"
        if not manifest_path.exists():
            pytest.skip("install_manifest.json not found")
        manifest = json.loads(manifest_path.read_text())
        manifest_version = manifest.get("version", "NOT FOUND")

        result = genai.judge(
            question="Does PROJECT.md version match install_manifest.json version?",
            context=f"**PROJECT.md version:** {project_version}\n"
            f"**install_manifest.json version:** {manifest_version}",
            criteria="Both should declare the same version. "
            "Mismatch = PROJECT.md is stale or manifest wasn't updated. "
            "Score 10 = match, 0 = mismatch.",
        )
        assert result["score"] >= 5, f"Version mismatch: {result['reasoning']}"

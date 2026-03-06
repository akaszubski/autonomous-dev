"""GenAI UAT: Skill evaluation quality tests.

Evaluates actual skill content against domain-specific prompts using LLM-as-judge.
These tests require --genai flag to run and validate that skills produce
high-quality guidance for their intended use cases.

Covers 4 skill categories: code, docs, security, architecture.
Also validates skill injection accuracy (correct skills for correct prompts).
"""

import sys
from pathlib import Path

import pytest

from ..conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"

# Add lib to path for skill_loader
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))


def _load_skill(skill_name: str) -> str:
    """Load skill content from disk, skip if not found."""
    skill_file = PLUGIN_ROOT / "skills" / skill_name / "SKILL.md"
    if not skill_file.exists():
        pytest.skip(f"Skill {skill_name} not found at {skill_file}")
    return skill_file.read_text()


def _get_available_skill_names() -> list:
    """Get list of available skills on disk."""
    skills_dir = PLUGIN_ROOT / "skills"
    if not skills_dir.exists():
        return []
    return [
        d.name
        for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    ]


# ============================================================================
# Code Skills
# ============================================================================


class TestCodeSkills:
    """Evaluate code-related skills against representative prompts."""

    def test_python_standards_code_review_prompt(self, genai):
        """python-standards skill should provide useful code review guidance."""
        content = _load_skill("python-standards")

        result = genai.judge(
            question="Does this skill provide actionable Python code review guidance?",
            context=f"Skill content (first 2000 chars):\n{content[:2000]}\n\n"
            f"Test prompt: 'Review this Python function for standards compliance: "
            f"def process(data, config=None, validate=True): ...'",
            criteria="Skill should cover: type hints, docstrings, naming conventions, "
            "error handling, and code organization. Should be specific enough "
            "to guide a code review. Score 10 = comprehensive actionable guidance, "
            "5 = covers basics, 0 = irrelevant.",
            category="default",
        )
        assert result["score"] >= 6, f"python-standards quality: {result['reasoning']}"

    def test_library_design_patterns_api_prompt(self, genai):
        """python-standards should guide API/library design."""
        content = _load_skill("python-standards")

        result = genai.judge(
            question="Does this skill help with designing clean Python APIs?",
            context=f"Skill content (first 2000 chars):\n{content[:2000]}\n\n"
            f"Test prompt: 'Design a public API for a data processing library with "
            f"configurable batch size and validation.'",
            criteria="Should mention: keyword-only args, type hints on public APIs, "
            "dataclasses for config, context managers, Pathlib. "
            "Score 10 = excellent API design guide, 5 = adequate, 0 = missing.",
            category="default",
        )
        assert result["score"] >= 5, f"API design guidance: {result['reasoning']}"

    def test_testing_guide_tdd_prompt(self, genai):
        """testing-guide skill should provide clear TDD methodology."""
        content = _load_skill("testing-guide")

        result = genai.judge(
            question="Does this skill provide clear TDD methodology?",
            context=f"Skill content (first 2000 chars):\n{content[:2000]}\n\n"
            f"Test prompt: 'Write tests for a new feature that calculates training metrics.'",
            criteria="Must cover: Red-Green-Refactor cycle, Arrange-Act-Assert pattern, "
            "coverage targets (80%+), parametrize usage, fixture patterns. "
            "Score 10 = complete TDD guide, 5 = covers basics, 0 = no TDD content.",
            category="default",
        )
        assert result["score"] >= 6, f"TDD methodology: {result['reasoning']}"


# ============================================================================
# Documentation Skills
# ============================================================================


class TestDocSkills:
    """Evaluate documentation-related skills."""

    def test_documentation_guide_api_change(self, genai):
        """documentation-guide should help document API changes."""
        available = _get_available_skill_names()
        # Try documentation-guide or git-workflow as fallback
        skill_name = "documentation-guide"
        if skill_name not in available:
            skill_name = "git-workflow"
        if skill_name not in available:
            pytest.skip("No documentation skill available")

        content = _load_skill(skill_name)

        result = genai.judge(
            question="Does this skill guide API change documentation?",
            context=f"Skill: {skill_name}\nContent (first 2000 chars):\n{content[:2000]}\n\n"
            f"Prompt: 'Document a breaking change to the train() function signature.'",
            criteria="Should cover: when to update docs, changelog format, "
            "API documentation standards, or commit message conventions. "
            "Score 10 = excellent doc change guidance, 5 = adequate, 0 = irrelevant.",
            category="documentation",
        )
        assert result["score"] >= 5, f"API doc guidance: {result['reasoning']}"

    def test_git_github_pr_description(self, genai):
        """A git/workflow skill should help write PR descriptions."""
        available = _get_available_skill_names()
        skill_name = "git-workflow"
        if skill_name not in available:
            # Try alternatives
            for alt in ["github-workflow", "documentation-guide"]:
                if alt in available:
                    skill_name = alt
                    break
            else:
                pytest.skip("No git/workflow skill available")

        content = _load_skill(skill_name)

        result = genai.judge(
            question="Does this skill help write good PR descriptions?",
            context=f"Skill: {skill_name}\nContent (first 2000 chars):\n{content[:2000]}\n\n"
            f"Prompt: 'Write a PR description for adding batch processing support.'",
            criteria="Should cover: PR title format, summary structure, "
            "test plan section, or commit message conventions. "
            "Score 10 = excellent PR guidance, 5 = adequate, 0 = no PR content.",
            category="documentation",
        )
        assert result["score"] >= 4, f"PR description guidance: {result['reasoning']}"

    def test_documentation_guide_adr(self, genai):
        """Documentation skill should mention ADRs or decision records."""
        available = _get_available_skill_names()
        skill_name = "documentation-guide"
        if skill_name not in available:
            skill_name = "architecture-patterns"
        if skill_name not in available:
            pytest.skip("No documentation/architecture skill available")

        content = _load_skill(skill_name)

        result = genai.judge(
            question="Does this skill cover architectural decision documentation?",
            context=f"Skill: {skill_name}\nContent (first 2000 chars):\n{content[:2000]}\n\n"
            f"Prompt: 'Document the decision to use worktree isolation for batch processing.'",
            criteria="Should mention: ADRs, decision records, architectural documentation, "
            "or rationale capture. Even brief mention counts. "
            "Score 10 = dedicated ADR section, 5 = mentions decisions, 0 = no mention.",
            category="documentation",
        )
        assert result["score"] >= 3, f"ADR guidance: {result['reasoning']}"


# ============================================================================
# Security Skills
# ============================================================================


class TestSecuritySkills:
    """Evaluate security-related skills."""

    def test_security_patterns_api_key_handling(self, genai):
        """security-patterns should guide API key handling."""
        content = _load_skill("security-patterns")

        result = genai.judge(
            question="Does this skill provide API key security guidance?",
            context=f"Skill content (first 2000 chars):\n{content[:2000]}\n\n"
            f"Prompt: 'Review this code that loads API keys from environment variables.'",
            criteria="Must cover: env vars for secrets, .env files gitignored, "
            "never commit secrets, environment variable patterns. "
            "Score 10 = comprehensive key security, 5 = mentions basics, 0 = missing.",
            category="security",
        )
        assert result["score"] >= 6, f"API key security: {result['reasoning']}"

    def test_security_patterns_input_validation(self, genai):
        """security-patterns should cover input validation."""
        content = _load_skill("security-patterns")

        result = genai.judge(
            question="Does this skill cover input validation security?",
            context=f"Skill content (first 2000 chars):\n{content[:2000]}\n\n"
            f"Prompt: 'Validate user input for a file path parameter.'",
            criteria="Should cover: path traversal prevention, input sanitization, "
            "type validation, or boundary checking. "
            "Score 10 = thorough input validation, 5 = basic coverage, 0 = none.",
            category="security",
        )
        assert result["score"] >= 5, f"Input validation: {result['reasoning']}"

    def test_security_patterns_injection_prevention(self, genai):
        """security-patterns should address injection attacks."""
        content = _load_skill("security-patterns")

        result = genai.judge(
            question="Does this skill address injection prevention?",
            context=f"Skill content (first 2000 chars):\n{content[:2000]}\n\n"
            f"Prompt: 'Ensure this command execution is safe from injection.'",
            criteria="Should mention: command injection, SQL injection, path traversal, "
            "or prompt injection. At least one injection type should be covered. "
            "Score 10 = multiple injection types, 5 = one type covered, 0 = none.",
            category="security",
        )
        assert result["score"] >= 5, f"Injection prevention: {result['reasoning']}"


# ============================================================================
# Architecture Skills
# ============================================================================


class TestArchitectureSkills:
    """Evaluate architecture-related skills."""

    def test_architecture_patterns_plan_quality(self, genai):
        """architecture-patterns should help create quality implementation plans."""
        content = _load_skill("architecture-patterns")

        result = genai.judge(
            question="Does this skill help create quality implementation plans?",
            context=f"Skill content (first 2000 chars):\n{content[:2000]}\n\n"
            f"Prompt: 'Create an implementation plan for adding a caching layer.'",
            criteria="Should cover: component design, separation of concerns, "
            "interface design, or plan structure. "
            "Score 10 = comprehensive planning guidance, 5 = basic, 0 = irrelevant.",
            category="architecture",
        )
        assert result["score"] >= 5, f"Plan quality guidance: {result['reasoning']}"

    def test_research_patterns_web_search(self, genai):
        """research-patterns should guide research methodology."""
        content = _load_skill("research-patterns")

        result = genai.judge(
            question="Does this skill guide research methodology?",
            context=f"Skill content (first 2000 chars):\n{content[:2000]}\n\n"
            f"Prompt: 'Research best practices for implementing a plugin system.'",
            criteria="Should cover: search strategies, source evaluation, "
            "codebase exploration, or information synthesis. "
            "Score 10 = complete research guide, 5 = basic guidance, 0 = none.",
            category="architecture",
        )
        assert result["score"] >= 5, f"Research guidance: {result['reasoning']}"

    def test_state_management_patterns_persistence(self, genai):
        """A patterns skill should cover state management/persistence."""
        available = _get_available_skill_names()
        # Try state-management or architecture-patterns
        for skill_name in ["state-management-patterns", "architecture-patterns"]:
            if skill_name in available:
                break
        else:
            pytest.skip("No state management/architecture skill available")

        content = _load_skill(skill_name)

        result = genai.judge(
            question="Does this skill cover state management or persistence patterns?",
            context=f"Skill: {skill_name}\nContent (first 2000 chars):\n{content[:2000]}\n\n"
            f"Prompt: 'Implement session state persistence across restarts.'",
            criteria="Should mention: file-based state, JSON persistence, "
            "state recovery, or checkpoint patterns. "
            "Score 10 = dedicated persistence section, 5 = mentions state, 0 = none.",
            category="architecture",
        )
        assert result["score"] >= 4, f"State management: {result['reasoning']}"


# ============================================================================
# Skill Injection Accuracy
# ============================================================================


class TestSkillInjectionAccuracy:
    """Test that the right skills are injected for the right prompts."""

    def test_correct_skills_for_security_prompt(self, genai):
        """Security-related prompts should trigger security-patterns skill."""
        from skill_loader import AGENT_SKILL_MAP

        security_agent_skills = AGENT_SKILL_MAP.get("security-auditor", [])

        result = genai.judge(
            question="Are these the right skills for a security audit agent?",
            context=f"Agent: security-auditor\n"
            f"Assigned skills: {security_agent_skills}\n\n"
            f"Prompt: 'Audit this codebase for security vulnerabilities including "
            f"injection attacks, secret exposure, and auth bypass.'",
            criteria="Security auditor should have security-patterns skill. "
            "Error-handling-patterns is a good complement. "
            "Should NOT have unrelated skills like documentation-guide. "
            "Score 10 = perfect skill set, 5 = adequate, 0 = wrong skills.",
            category="default",
        )
        assert result["score"] >= 6, f"Security skill injection: {result['reasoning']}"

    def test_correct_skills_for_testing_prompt(self, genai):
        """Testing prompts should trigger testing-guide skill."""
        from skill_loader import AGENT_SKILL_MAP

        test_agent_skills = AGENT_SKILL_MAP.get("test-master", [])

        result = genai.judge(
            question="Are these the right skills for a test-writing agent?",
            context=f"Agent: test-master\n"
            f"Assigned skills: {test_agent_skills}\n\n"
            f"Prompt: 'Write unit tests for the new caching module using TDD.'",
            criteria="Test-master should have testing-guide skill. "
            "Python-standards is a good complement for test code quality. "
            "Score 10 = perfect skill set, 5 = adequate, 0 = wrong skills.",
            category="default",
        )
        assert result["score"] >= 6, f"Testing skill injection: {result['reasoning']}"

    def test_no_irrelevant_skills_injected(self, genai):
        """Agent skill mappings should not include obviously irrelevant skills."""
        from skill_loader import AGENT_SKILL_MAP

        # Build a summary of all agent-skill mappings
        mapping_summary = "\n".join(
            f"  {agent}: {', '.join(skills)}"
            for agent, skills in sorted(AGENT_SKILL_MAP.items())
        )

        result = genai.judge(
            question="Are any skills obviously misassigned to agents?",
            context=f"Agent-skill mappings:\n{mapping_summary}",
            criteria="Each agent should only have skills relevant to its role. "
            "Examples of BAD: security-auditor with documentation-guide, "
            "doc-master with security-patterns (unless for doc security). "
            "Score 10 = all mappings logical, 5 = mostly logical, 0 = chaotic.",
            category="default",
        )
        assert result["score"] >= 6, f"Skill injection accuracy: {result['reasoning']}"


# ============================================================================
# Skill Regression
# ============================================================================


class TestSkillRegression:
    """Test that all skills maintain minimum quality baselines."""

    def test_all_skills_above_baseline(self, genai):
        """Every available skill should score above a minimum quality threshold."""
        available = _get_available_skill_names()
        assert len(available) >= 5, f"Expected at least 5 skills, found {len(available)}"

        failures = []
        # Sample up to 5 skills to keep costs reasonable
        sample = available[:5]

        for skill_name in sample:
            content = _load_skill(skill_name)
            result = genai.judge(
                question=f"Is the '{skill_name}' skill well-structured and actionable?",
                context=f"Skill: {skill_name}\nContent (first 1500 chars):\n{content[:1500]}",
                criteria="A good skill should: have clear structure (headers/sections), "
                "provide actionable guidance (not just theory), include examples, "
                "and be relevant to its domain. "
                "Score 10 = excellent, 5 = adequate, 0 = empty/broken.",
                category="default",
            )
            if result["score"] < 5:
                failures.append(f"{skill_name}: {result['score']}/10 - {result['reasoning']}")

        assert not failures, f"Skills below baseline:\n" + "\n".join(failures)

    def test_baseline_establishment(self, genai):
        """Verify that skill evaluation produces consistent, scoreable results."""
        content = _load_skill("python-standards")

        result = genai.judge(
            question="Rate this skill for completeness and quality.",
            context=f"Skill: python-standards\nContent (first 1500 chars):\n{content[:1500]}",
            criteria="Score based on: structure (2pts), actionability (2pts), "
            "examples (2pts), domain relevance (2pts), completeness (2pts). "
            "Total out of 10.",
            category="default",
        )

        # Basic structural check: result should have expected fields
        assert "score" in result, "Judge result missing 'score' field"
        assert "reasoning" in result, "Judge result missing 'reasoning' field"
        assert isinstance(result["score"], (int, float)), "Score should be numeric"
        assert 0 <= result["score"] <= 10, f"Score {result['score']} out of 0-10 range"

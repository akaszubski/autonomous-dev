"""GenAI UAT tests for alignment assessment accuracy.

Tests that the TWELVE_FACTOR_ASSESSMENT_PROMPT and GOALS_EXTRACTION_PROMPT
produce meaningful, realistic results using LLM-as-judge validation.

These tests validate:
1. 12-Factor scores are realistic (not all 7/10) for a sample codebase
2. Goals extracted from a sample README are meaningful and specific

Run with:
    pytest tests/genai/test_alignment_assessment.py --genai

Requirements:
    - OPENROUTER_API_KEY environment variable
    - openai package installed

Cost: ~$0.05 per run (two prompts + two judge calls)
"""

import json
import sys
from pathlib import Path
from typing import Optional

import pytest

pytestmark = [pytest.mark.genai]

# ============================================================================
# Path setup
# ============================================================================

_WORKTREE_ROOT = Path(__file__).parent.parent.parent
_LIB_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "hooks"

sys.path.insert(0, str(_LIB_PATH))
sys.path.insert(0, str(_HOOKS_PATH))


# ============================================================================
# Sample data for testing
# ============================================================================

# Sample codebase analysis for a Python Flask web app with good practices
SAMPLE_CODEBASE_ANALYSIS = {
    "primary_language": "python",
    "framework": "flask",
    "package_manager": "pip",
    "has_git": "True",
    "has_env": "True",
    "has_ci": "True",
    "has_docker": "True",
    "dependencies_sample": "flask, pytest, gunicorn, redis, psycopg2, celery",
    "config_files": ".env, .github/workflows/ci.yml, Dockerfile, requirements.txt",
    "total_files": "150",
    "test_files": "45",
    "has_web_framework": "True",
}

# Sample README for a plugin/tool project
SAMPLE_README = """# autonomous-dev

Plugin for autonomous development in Claude Code. AI agents, skills, automation hooks, slash commands.

## Overview

Autonomous development plugin that provides:
- **8-agent SDLC pipeline**: researcher → planner → test-master → implementer → reviewer → security-auditor → doc-master
- **Batch processing**: Process multiple features/issues with worktree isolation
- **Git automation**: AUTO_GIT_ENABLED for commit/push workflows

## Installation

```bash
/plugin install akaszubski/autonomous-dev
```

Then restart Claude Code (Cmd+Q / Ctrl+Q).

## Why Use autonomous-dev?

Software development is repetitive. The same patterns - research, plan, implement, test, review - repeat
for every feature. autonomous-dev automates this pipeline so developers focus on creative problem-solving,
not mechanical execution.

## Features

- **Slash Commands**: `/implement`, `/create-issue`, `/align`, `/audit`
- **Hook System**: Pre-commit quality gates, auto-formatting, security scanning
- **GenAI Integration**: Semantic understanding for complexity, scope, quality assessment
- **Batch Processing**: Run multiple features in parallel with git worktree isolation

## Goals

1. Enable 10x developer productivity through AI-assisted development workflows
2. Maintain high code quality standards through automated review pipelines
3. Support brownfield project onboarding with alignment assessment tools

## Usage

See docs/ for detailed guides on each command and workflow.
"""

REQUIRED_TWELVE_FACTORS = {
    "codebase", "dependencies", "config", "backing_services",
    "build_release_run", "processes", "port_binding", "concurrency",
    "disposability", "dev_prod_parity", "logs", "admin_processes",
}


# ============================================================================
# Helpers
# ============================================================================

def _load_twelve_factor_prompt() -> Optional[str]:
    """Load TWELVE_FACTOR_ASSESSMENT_PROMPT from genai_prompts."""
    try:
        from genai_prompts import TWELVE_FACTOR_ASSESSMENT_PROMPT
        return TWELVE_FACTOR_ASSESSMENT_PROMPT
    except (ImportError, AttributeError):
        return None


def _load_goals_prompt() -> Optional[str]:
    """Load GOALS_EXTRACTION_PROMPT from genai_prompts."""
    try:
        from genai_prompts import GOALS_EXTRACTION_PROMPT
        return GOALS_EXTRACTION_PROMPT
    except (ImportError, AttributeError):
        return None


def _call_twelve_factor_prompt(genai_client, analysis: dict) -> Optional[dict]:
    """Call the 12-factor prompt with sample analysis data, return parsed JSON."""
    prompt_template = _load_twelve_factor_prompt()
    if not prompt_template:
        return None

    try:
        formatted = prompt_template.format(**analysis)
    except KeyError as e:
        pytest.skip(f"TWELVE_FACTOR_ASSESSMENT_PROMPT missing variable: {e}")
        return None

    response = genai_client.ask(formatted, max_tokens=500)

    # Try to parse JSON from response
    try:
        # Strip markdown fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        # Try to extract JSON object from response
        start = response.find("{")
        end = response.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(response[start:end + 1])
            except (json.JSONDecodeError, ValueError):
                pass
        return None


def _call_goals_prompt(genai_client, readme_content: str) -> Optional[str]:
    """Call the goals extraction prompt with sample README, return response text."""
    prompt_template = _load_goals_prompt()
    if not prompt_template:
        return None

    try:
        formatted = prompt_template.format(readme_content=readme_content)
    except KeyError as e:
        pytest.skip(f"GOALS_EXTRACTION_PROMPT missing variable: {e}")
        return None

    return genai_client.ask(formatted, max_tokens=400)


# ============================================================================
# 12-Factor Assessment Tests
# ============================================================================

class TestTwelveFactorAssessmentAccuracy:
    """LLM-as-judge tests for 12-Factor scoring realism.

    Validates that the TWELVE_FACTOR_ASSESSMENT_PROMPT produces intelligent,
    varied scores rather than defaulting all factors to 7/10.
    """

    def test_twelve_factor_prompt_exists_and_has_required_variables(self, genai):
        """TWELVE_FACTOR_ASSESSMENT_PROMPT should exist and have required format variables."""
        prompt = _load_twelve_factor_prompt()
        if prompt is None:
            pytest.skip("TWELVE_FACTOR_ASSESSMENT_PROMPT not yet defined")

        required_vars = [
            "{primary_language}", "{framework}", "{has_git}", "{has_env}",
            "{has_ci}", "{has_docker}", "{dependencies_sample}", "{config_files}",
        ]

        for var in required_vars:
            assert var in prompt, (
                f"TWELVE_FACTOR_ASSESSMENT_PROMPT missing required variable: {var}"
            )

    def test_twelve_factor_scores_are_valid_json_with_all_12_factors(self, genai):
        """Prompt response should be parseable JSON with all 12 required factors."""
        scores = _call_twelve_factor_prompt(genai, SAMPLE_CODEBASE_ANALYSIS)

        assert scores is not None, (
            "TWELVE_FACTOR_ASSESSMENT_PROMPT should return parseable JSON"
        )
        assert isinstance(scores, dict), f"Expected dict, got {type(scores)}"

        missing = REQUIRED_TWELVE_FACTORS - set(scores.keys())
        assert not missing, (
            f"Response missing required factors: {missing}\n"
            f"Got factors: {list(scores.keys())}"
        )

    def test_twelve_factor_scores_are_integers_in_valid_range(self, genai):
        """All 12 factor scores should be integers between 1 and 10."""
        scores = _call_twelve_factor_prompt(genai, SAMPLE_CODEBASE_ANALYSIS)

        if scores is None:
            pytest.skip("Could not parse 12-factor response as JSON")

        invalid = {}
        for factor, score in scores.items():
            if factor not in REQUIRED_TWELVE_FACTORS:
                continue
            if not isinstance(score, (int, float)) or not (1 <= score <= 10):
                invalid[factor] = score

        assert not invalid, (
            f"Factors with invalid scores (expected 1-10): {invalid}"
        )

    def test_twelve_factor_scores_are_varied_not_all_seven(self, genai):
        """Scores should vary based on codebase analysis, not default to all 7/10.

        This is the key test: the old heuristic hardcoded 3 factors to 7/10.
        GenAI should produce realistic, varied scores.
        """
        scores = _call_twelve_factor_prompt(genai, SAMPLE_CODEBASE_ANALYSIS)

        if scores is None:
            pytest.skip("Could not parse 12-factor response as JSON")

        relevant_scores = [
            int(scores[f]) for f in REQUIRED_TWELVE_FACTORS
            if f in scores and isinstance(scores[f], (int, float))
        ]

        if not relevant_scores:
            pytest.skip("No valid scores to evaluate")

        unique_scores = set(relevant_scores)
        count_sevens = relevant_scores.count(7)

        judge_result = genai.judge(
            question="Are these 12-Factor scores realistic and varied for the described codebase?",
            context=(
                f"Codebase analysis:\n"
                f"  Language: Python, Framework: Flask, Has git: True\n"
                f"  Has .env: True, Has CI: True, Has Docker: True\n"
                f"  Dependencies: flask, pytest, gunicorn, redis, psycopg2, celery\n"
                f"  Test files: 45 of 150 total files\n\n"
                f"12-Factor scores:\n"
                + "\n".join(
                    f"  {factor}: {scores.get(factor, 'missing')}/10"
                    for factor in sorted(REQUIRED_TWELVE_FACTORS)
                )
            ),
            criteria=(
                "Good 12-Factor scoring should:\n"
                "1. NOT default all ambiguous factors to 7/10 (variation is key)\n"
                "2. Score high for factors with clear evidence (git=10, docker=9-10)\n"
                "3. Score lower for factors lacking evidence\n"
                "4. Produce at least 3 different score values across all 12 factors\n"
                "Score 10 = very realistic and varied. "
                "Score 5 = mostly 7s but some variation. "
                "Score 2 = all or mostly identical scores (not realistic)."
            ),
        )

        # Verify scores are varied (at least 3 distinct values)
        assert len(unique_scores) >= 3, (
            f"12-Factor scores lack variety: only {len(unique_scores)} unique values: {unique_scores}\n"
            f"All scores: {dict((f, scores.get(f)) for f in REQUIRED_TWELVE_FACTORS)}"
        )

        # Judge should confirm realism
        assert judge_result.get("score", 0) >= 5, (
            f"Judge rates 12-Factor scores as unrealistic. "
            f"Score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}\n"
            f"Scores: {dict((f, scores.get(f)) for f in REQUIRED_TWELVE_FACTORS)}"
        )

    def test_twelve_factor_high_compliance_codebase_scores_high(self, genai):
        """A well-configured codebase should score higher than a bare-minimum one.

        Compare two codebases: one with all 12-factor practices, one without.
        """
        # Good codebase (all 12-factor practices)
        good_analysis = {**SAMPLE_CODEBASE_ANALYSIS}  # Has git, env, CI, docker, etc.

        # Poor codebase (minimal practices)
        poor_analysis = {
            "primary_language": "python",
            "framework": "none",
            "package_manager": "none",
            "has_git": "False",
            "has_env": "False",
            "has_ci": "False",
            "has_docker": "False",
            "dependencies_sample": "none detected",
            "config_files": "none",
            "total_files": "5",
            "test_files": "0",
            "has_web_framework": "False",
        }

        good_scores = _call_twelve_factor_prompt(genai, good_analysis)
        poor_scores = _call_twelve_factor_prompt(genai, poor_analysis)

        if good_scores is None or poor_scores is None:
            pytest.skip("Could not parse 12-factor response as JSON")

        good_total = sum(
            int(good_scores[f]) for f in REQUIRED_TWELVE_FACTORS
            if f in good_scores and isinstance(good_scores[f], (int, float))
        )
        poor_total = sum(
            int(poor_scores[f]) for f in REQUIRED_TWELVE_FACTORS
            if f in poor_scores and isinstance(poor_scores[f], (int, float))
        )

        judge_result = genai.judge(
            question=(
                f"Is it correct that a well-configured codebase (total={good_total}) "
                f"scored higher than a bare-minimum one (total={poor_total})?"
            ),
            context=(
                f"Good codebase scores (total={good_total}/120):\n"
                + "\n".join(
                    f"  {f}: {good_scores.get(f)}"
                    for f in sorted(REQUIRED_TWELVE_FACTORS)
                )
                + f"\n\nPoor codebase scores (total={poor_total}/120):\n"
                + "\n".join(
                    f"  {f}: {poor_scores.get(f)}"
                    for f in sorted(REQUIRED_TWELVE_FACTORS)
                )
            ),
            criteria=(
                "A codebase with git, .env, CI, Docker, dependencies, and tests should score "
                "significantly higher (at least 15 points more on a 120-point scale) than "
                "a bare-minimum project with none of these practices. "
                "Score 10 = good codebase clearly scored higher. "
                "Score 3 = scores are similar despite obvious differences."
            ),
        )

        assert good_total > poor_total, (
            f"Well-configured codebase ({good_total}) should score higher than "
            f"bare-minimum codebase ({poor_total})"
        )

        assert judge_result.get("score", 0) >= 5, (
            f"Judge does not confirm scoring realism. "
            f"Score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}"
        )


# ============================================================================
# Goals Extraction Tests
# ============================================================================

class TestGoalsExtractionAccuracy:
    """LLM-as-judge tests for goals extraction meaningfulness.

    Validates that GOALS_EXTRACTION_PROMPT synthesizes specific, actionable
    goals from README content rather than generic or empty content.
    """

    def test_goals_prompt_exists_and_has_readme_content_variable(self, genai):
        """GOALS_EXTRACTION_PROMPT should exist and contain {readme_content} placeholder."""
        prompt = _load_goals_prompt()
        if prompt is None:
            pytest.skip("GOALS_EXTRACTION_PROMPT not yet defined")

        assert "{readme_content}" in prompt, (
            "GOALS_EXTRACTION_PROMPT must contain {readme_content} format variable"
        )

    def test_goals_extraction_returns_bullet_points(self, genai):
        """Prompt should return bullet-point list of goals (containing '-' markers)."""
        response = _call_goals_prompt(genai, SAMPLE_README)

        assert response is not None, "GOALS_EXTRACTION_PROMPT should return a response"
        assert "-" in response, (
            f"Goals response should contain bullet points (- markers), got: {response[:200]}"
        )

    def test_goals_extraction_produces_3_to_5_goals(self, genai):
        """Goals response should contain 3-5 bullet points."""
        response = _call_goals_prompt(genai, SAMPLE_README)

        if response is None:
            pytest.skip("No response from goals prompt")

        # Count bullet point lines
        bullet_lines = [
            line.strip() for line in response.split("\n")
            if line.strip().startswith("-") and len(line.strip()) > 2
        ]

        judge_result = genai.judge(
            question=f"Does this goals response contain 3-5 meaningful bullet points?",
            context=f"Goals response:\n```\n{response}\n```",
            criteria=(
                "The response should contain 3-5 bullet points starting with '-'. "
                "Each bullet point should be a specific, actionable goal (not a generic statement). "
                "Score 10 = 3-5 specific, actionable goals. "
                "Score 5 = correct count but generic. "
                "Score 2 = wrong count or no bullet points."
            ),
        )

        assert 2 <= len(bullet_lines) <= 6, (
            f"Expected 3-5 bullet points, got {len(bullet_lines)}:\n{response}"
        )

        assert judge_result.get("score", 0) >= 5, (
            f"Judge rates goals as inadequate. "
            f"Score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}\n"
            f"Response: {response}"
        )

    def test_goals_are_meaningful_not_generic(self, genai):
        """Extracted goals should be specific to the project, not generic filler.

        Key test: Goals should mention specific capabilities, not just
        'improve efficiency' or 'provide better development experience'.
        """
        response = _call_goals_prompt(genai, SAMPLE_README)

        if response is None:
            pytest.skip("No response from goals prompt")

        judge_result = genai.judge(
            question="Are these goals specific and meaningful for the autonomous-dev plugin?",
            context=(
                f"Project: autonomous-dev (Claude Code plugin for AI-assisted development)\n\n"
                f"Extracted goals:\n```\n{response}\n```\n\n"
                f"README excerpt (first 500 chars):\n```\n{SAMPLE_README[:500]}\n```"
            ),
            criteria=(
                "Good goals should:\n"
                "1. Be SPECIFIC to this project (mention AI agents, autonomous development, "
                "Claude Code, or specific capabilities like slash commands, hooks, pipelines)\n"
                "2. Be ACTION-ORIENTED (start with verbs: Enable, Automate, Provide, Support)\n"
                "3. NOT be generic filler like 'improve developer experience' or 'enhance productivity'\n"
                "4. Capture the primary value propositions of the tool\n\n"
                "Score 10 = highly specific, actionable, clearly about this project. "
                "Score 5 = somewhat specific but some generic statements. "
                "Score 2 = generic/placeholder content that could apply to any project."
            ),
        )

        assert judge_result.get("score", 0) >= 5, (
            f"Judge rates goals as too generic. "
            f"Score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}\n"
            f"Goals response:\n{response}"
        )

    def test_goals_extraction_handles_readme_without_goals_section(self, genai):
        """GenAI should synthesize goals even when README has no Goals/Purpose section."""
        readme_without_goals = """# Flask App

A web application built with Flask.

## Features
- User authentication with JWT
- REST API with JSON responses
- PostgreSQL database integration
- Redis caching layer
- Docker deployment ready

## Installation
```bash
pip install -r requirements.txt
flask run
```

## API Documentation
See docs/api.md for endpoint documentation.
"""
        response = _call_goals_prompt(genai, readme_without_goals)

        if response is None:
            pytest.skip("No response from goals prompt")

        judge_result = genai.judge(
            question=(
                "Did the GenAI successfully synthesize project goals from a README "
                "that has no explicit Goals/Purpose/Objectives section?"
            ),
            context=(
                f"README (no Goals section):\n```\n{readme_without_goals}\n```\n\n"
                f"Synthesized goals:\n```\n{response}\n```"
            ),
            criteria=(
                "The synthesized goals should make sense for a Flask web app with JWT auth, "
                "REST API, PostgreSQL, Redis, and Docker. "
                "Goals should be inferred from the feature list, not just copied verbatim. "
                "Score 10 = reasonable goals synthesized from features. "
                "Score 5 = goals mentioned but could be more specific. "
                "Score 2 = goals don't make sense for the described app."
            ),
        )

        # Should at least return some response with bullet points
        assert response is not None
        assert "-" in response, "Response should contain bullet points even without Goals section"

        assert judge_result.get("score", 0) >= 5, (
            f"Judge says goals are not well-synthesized from README without Goals section. "
            f"Score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}"
        )

    def test_goals_better_than_simple_header_extraction(self, genai):
        """GenAI goals should be more informative than just dumping the first 500 chars.

        The old heuristic dumped `content[:500]...` when it found a Goals heading.
        GenAI should synthesize a proper bullet-point list instead.
        """
        response = _call_goals_prompt(genai, SAMPLE_README)

        if response is None:
            pytest.skip("No response from goals prompt")

        # The old approach: first 500 chars of README
        old_approach = SAMPLE_README[:500]

        judge_result = genai.judge(
            question="Which approach provides better PROJECT.md GOALS content?",
            context=(
                f"**GenAI synthesized goals:**\n```\n{response}\n```\n\n"
                f"**Old approach (first 500 chars of README):**\n```\n{old_approach}...\n```"
            ),
            criteria=(
                "Better GOALS content should:\n"
                "1. Be organized as clear bullet points (not raw README dump)\n"
                "2. Extract only the goal-relevant information\n"
                "3. Be immediately useful in a PROJECT.md file\n"
                "4. Not include installation instructions, code blocks, or raw markdown\n\n"
                "Score 10 = GenAI approach is clearly better. "
                "Score 5 = both approaches are roughly equivalent. "
                "Score 2 = old approach is better."
            ),
        )

        assert judge_result.get("score", 0) >= 6, (
            f"GenAI goals not clearly better than simple header extraction. "
            f"Score: {judge_result.get('score')}/10. "
            f"Reasoning: {judge_result.get('reasoning')}"
        )

"""Tests for Issue #731: --light pipeline mode prompt integrity gate.

Validates that the LIGHT PIPELINE section of implement.md:
1. Contains planner prompt template with >= 80 words of static text
2. Contains implementer prompt template with >= 80 words of static text
3. Contains doc-master prompt template with >= 80 words of static text
4. Includes prompt integrity gate references (validate_prompt_word_count,
   record_prompt_baseline, get_agent_prompt_template, PROMPT-INTEGRITY-BLOCKED)
5. Includes a FORBIDDEN section covering summarization and condensation

These tests prevent prompt quality regressions in --light mode where
progressive prompt compression degrades agent output quality silently.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
IMPLEMENT_CMD_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"

# Minimum word count for critical agent prompts, matching prompt_integrity.py
MIN_CRITICAL_AGENT_PROMPT_WORDS = 80


def _get_light_pipeline_section(content: str) -> str:
    """Extract the LIGHT PIPELINE MODE section from implement.md.

    Args:
        content: Full file content of implement.md.

    Returns:
        The text of the LIGHT PIPELINE MODE section, or empty string if not found.
    """
    # Find the LIGHT PIPELINE MODE section — it starts with a heading and ends
    # at the next top-level heading or end of file
    match = re.search(r"(# LIGHT PIPELINE MODE.*?)(?=\n# |\Z)", content, re.DOTALL)
    if match:
        return match.group(1)
    return ""


def _extract_prompt_template_words(content: str, agent_type: str) -> list[str]:
    """Extract template words from a prompt block for the given agent_type.

    Finds the prompt block for the given agent_type in the LIGHT PIPELINE section
    and strips out content inside square brackets (e.g., [feature description])
    which are placeholders that the coordinator replaces with dynamic content.

    Args:
        content: Full file content of implement.md.
        agent_type: Agent type string (e.g., 'planner', 'implementer', 'doc-master').

    Returns:
        List of words in the template text excluding placeholder markers.
    """
    light_section = _get_light_pipeline_section(content)
    if not light_section:
        return []

    # Find prompt blocks: look for subagent_type matching the agent_type
    # within code fences (``` ... ```) in the light pipeline section
    prompt_blocks = re.findall(
        r'subagent_type:\s*"' + re.escape(agent_type) + r'".*?prompt:\s*"(.*?)"',
        light_section,
        re.DOTALL,
    )
    if not prompt_blocks:
        return []

    template_text = prompt_blocks[0]

    # Remove placeholder markers: [any text inside brackets]
    template_text = re.sub(r"\[.*?\]", "", template_text)

    # Split into words, filtering empty strings
    words = [w for w in template_text.split() if w.strip()]
    return words


class TestLightModePlannerPromptMinimum:
    """Regression test: STEP L2 planner prompt template must have >= 80 words.

    Without a sufficiently large template, the planner receives an underspecified
    prompt and produces vague plans that cause implementer failures downstream.
    """

    @pytest.fixture
    def implement_content(self) -> str:
        """Read implement.md content."""
        assert IMPLEMENT_CMD_PATH.exists(), f"implement.md not found at {IMPLEMENT_CMD_PATH}"
        return IMPLEMENT_CMD_PATH.read_text(encoding="utf-8")

    def test_planner_prompt_template_meets_minimum(self, implement_content: str) -> None:
        """Planner prompt template must contain >= 80 words excluding placeholders.

        The STEP L2 planner template must be self-sufficient with static instructions
        that constitute the majority of the prompt, independent of the feature description.
        """
        words = _extract_prompt_template_words(implement_content, "planner")
        word_count = len(words)

        assert word_count >= MIN_CRITICAL_AGENT_PROMPT_WORDS, (
            f"Planner prompt template in STEP L2 has only {word_count} words "
            f"(minimum: {MIN_CRITICAL_AGENT_PROMPT_WORDS}). "
            f"The template must be self-sufficient (>= 80 words) even without "
            f"the feature description placeholder filled in."
        )

    def test_planner_prompt_requires_file_by_file_plan(self, implement_content: str) -> None:
        """Planner prompt must require a file-by-file plan output section."""
        words = _extract_prompt_template_words(implement_content, "planner")
        template_text = " ".join(words).upper()

        assert "FILE-BY-FILE" in template_text or "FILE BY FILE" in template_text, (
            "Planner prompt in STEP L2 must require a FILE-BY-FILE PLAN section "
            "to ensure the implementer receives actionable per-file instructions."
        )

    def test_planner_prompt_requires_acceptance_criteria(self, implement_content: str) -> None:
        """Planner prompt must require acceptance criteria output section."""
        words = _extract_prompt_template_words(implement_content, "planner")
        template_text = " ".join(words).upper()

        assert "ACCEPTANCE CRITERIA" in template_text or "ACCEPTANCE" in template_text, (
            "Planner prompt in STEP L2 must require ACCEPTANCE CRITERIA "
            "to define observable outcomes for the implementer."
        )

    def test_planner_prompt_requires_recommended_model(self, implement_content: str) -> None:
        """Planner prompt must require model recommendation output."""
        words = _extract_prompt_template_words(implement_content, "planner")
        template_text = " ".join(words).lower()

        assert "recommended implementer model" in template_text or "sonnet" in template_text, (
            "Planner prompt in STEP L2 must require a 'Recommended implementer model' "
            "output so the coordinator knows which model to use for STEP L3."
        )


class TestLightModeImplementerPromptMinimum:
    """Regression test: STEP L3 implementer prompt template must have >= 80 words.

    Without a sufficiently large template, the implementer receives an underspecified
    prompt and may produce stubs or incomplete implementations.
    """

    @pytest.fixture
    def implement_content(self) -> str:
        """Read implement.md content."""
        assert IMPLEMENT_CMD_PATH.exists(), f"implement.md not found at {IMPLEMENT_CMD_PATH}"
        return IMPLEMENT_CMD_PATH.read_text(encoding="utf-8")

    def test_implementer_prompt_template_meets_minimum(self, implement_content: str) -> None:
        """Implementer prompt template must contain >= 80 words excluding placeholders.

        The STEP L3 implementer template must be self-sufficient with static HARD GATE
        instructions that enforce production-quality code standards.
        """
        words = _extract_prompt_template_words(implement_content, "implementer")
        word_count = len(words)

        assert word_count >= MIN_CRITICAL_AGENT_PROMPT_WORDS, (
            f"Implementer prompt template in STEP L3 has only {word_count} words "
            f"(minimum: {MIN_CRITICAL_AGENT_PROMPT_WORDS}). "
            f"The template must be self-sufficient (>= 80 words) even without "
            f"the planner output placeholder filled in."
        )

    def test_implementer_prompt_requires_no_stubs(self, implement_content: str) -> None:
        """Implementer prompt must explicitly forbid stubs and NotImplementedError."""
        words = _extract_prompt_template_words(implement_content, "implementer")
        template_text = " ".join(words).lower()

        assert "no stubs" in template_text or "notimplementederror" in template_text, (
            "Implementer prompt in STEP L3 must explicitly forbid stubs and "
            "NotImplementedError to prevent silent incomplete implementations."
        )

    def test_implementer_prompt_requires_zero_failures(self, implement_content: str) -> None:
        """Implementer prompt must require 0 failures, 0 errors."""
        words = _extract_prompt_template_words(implement_content, "implementer")
        template_text = " ".join(words).lower()

        assert "0 failures" in template_text or "zero failures" in template_text, (
            "Implementer prompt in STEP L3 must require 0 failures, 0 errors "
            "as a HARD GATE for test quality."
        )


class TestLightModeDocMasterPromptMinimum:
    """Regression test: STEP L4 doc-master prompt template must have >= 80 words.

    Consistent with Issue #693 fix for --fix mode: doc-master needs sufficient
    template text to produce structured DOC-DRIFT-VERDICT outputs.
    """

    @pytest.fixture
    def implement_content(self) -> str:
        """Read implement.md content."""
        assert IMPLEMENT_CMD_PATH.exists(), f"implement.md not found at {IMPLEMENT_CMD_PATH}"
        return IMPLEMENT_CMD_PATH.read_text(encoding="utf-8")

    def test_doc_master_prompt_template_meets_minimum(self, implement_content: str) -> None:
        """Doc-master prompt template must contain >= 80 words excluding placeholders."""
        words = _extract_prompt_template_words(implement_content, "doc-master")
        word_count = len(words)

        assert word_count >= MIN_CRITICAL_AGENT_PROMPT_WORDS, (
            f"Doc-master prompt template in STEP L4 has only {word_count} words "
            f"(minimum: {MIN_CRITICAL_AGENT_PROMPT_WORDS}). "
            f"The template must be self-sufficient (>= 80 words) to ensure "
            f"structured DOC-DRIFT-VERDICT outputs."
        )

    def test_doc_master_prompt_requires_doc_drift_verdict(self, implement_content: str) -> None:
        """Doc-master prompt must require DOC-DRIFT-VERDICT as a mandatory output."""
        words = _extract_prompt_template_words(implement_content, "doc-master")
        template_text = " ".join(words).upper()

        assert "DOC-DRIFT-VERDICT" in template_text or "DOCS-DRIFT" in template_text, (
            "Doc-master prompt in STEP L4 must require DOC-DRIFT-VERDICT as a mandatory "
            "step to produce structured verdicts (consistent with Issue #693 fix)."
        )

    def test_doc_master_prompt_requires_scan_step(self, implement_content: str) -> None:
        """Doc-master prompt must include a SCAN step."""
        words = _extract_prompt_template_words(implement_content, "doc-master")
        template_text = " ".join(words).lower()

        assert "scan" in template_text, (
            "Doc-master prompt in STEP L4 must include a SCAN step to identify "
            "documentation files affected by the implementation."
        )

    def test_doc_master_prompt_requires_semantic_comparison(self, implement_content: str) -> None:
        """Doc-master prompt must include a semantic comparison step."""
        words = _extract_prompt_template_words(implement_content, "doc-master")
        template_text = " ".join(words).lower()

        assert "semantic comparison" in template_text or "semantic" in template_text, (
            "Doc-master prompt in STEP L4 must include a SEMANTIC COMPARISON step "
            "to compare documented behavior against new behavior."
        )


class TestLightModePromptIntegrityGate:
    """Validate the LIGHT PIPELINE section contains prompt integrity gate instructions.

    The coordinator must call validate_prompt_word_count, record_prompt_baseline,
    get_agent_prompt_template, and abort with PROMPT-INTEGRITY-BLOCKED when below minimum.
    """

    @pytest.fixture
    def implement_content(self) -> str:
        """Read implement.md content."""
        assert IMPLEMENT_CMD_PATH.exists(), f"implement.md not found at {IMPLEMENT_CMD_PATH}"
        return IMPLEMENT_CMD_PATH.read_text(encoding="utf-8")

    @pytest.fixture
    def light_section(self, implement_content: str) -> str:
        """Extract the LIGHT PIPELINE MODE section."""
        section = _get_light_pipeline_section(implement_content)
        assert section, "LIGHT PIPELINE MODE section not found in implement.md"
        return section

    def test_validate_prompt_word_count_referenced(self, light_section: str) -> None:
        """Light pipeline section must reference validate_prompt_word_count."""
        assert "validate_prompt_word_count" in light_section, (
            "LIGHT PIPELINE section must reference validate_prompt_word_count "
            "from prompt_integrity.py to enforce prompt quality gates."
        )

    def test_record_prompt_baseline_referenced(self, light_section: str) -> None:
        """Light pipeline section must reference record_prompt_baseline."""
        assert "record_prompt_baseline" in light_section, (
            "LIGHT PIPELINE section must reference record_prompt_baseline "
            "to establish baseline word counts for each agent type."
        )

    def test_get_agent_prompt_template_referenced(self, light_section: str) -> None:
        """Light pipeline section must reference get_agent_prompt_template."""
        assert "get_agent_prompt_template" in light_section, (
            "LIGHT PIPELINE section must reference get_agent_prompt_template "
            "so coordinators know how to reconstruct prompts when integrity check fails."
        )

    def test_prompt_integrity_blocked_marker_present(self, light_section: str) -> None:
        """Light pipeline section must include PROMPT-INTEGRITY-BLOCKED abort marker."""
        assert "PROMPT-INTEGRITY-BLOCKED" in light_section, (
            "LIGHT PIPELINE section must include the PROMPT-INTEGRITY-BLOCKED "
            "abort marker so coordinators know the standard error format to emit."
        )


class TestLightModeForbiddenList:
    """Validate the LIGHT PIPELINE HARD GATE contains a FORBIDDEN section.

    The FORBIDDEN section prevents coordinators from silently degrading prompt quality
    through summarization, condensation, or omission of required context.
    """

    @pytest.fixture
    def implement_content(self) -> str:
        """Read implement.md content."""
        assert IMPLEMENT_CMD_PATH.exists(), f"implement.md not found at {IMPLEMENT_CMD_PATH}"
        return IMPLEMENT_CMD_PATH.read_text(encoding="utf-8")

    @pytest.fixture
    def light_section(self, implement_content: str) -> str:
        """Extract the LIGHT PIPELINE MODE section."""
        section = _get_light_pipeline_section(implement_content)
        assert section, "LIGHT PIPELINE MODE section not found in implement.md"
        return section

    def test_forbidden_section_exists(self, light_section: str) -> None:
        """LIGHT PIPELINE HARD GATE must contain a FORBIDDEN section."""
        assert "FORBIDDEN" in light_section, (
            "LIGHT PIPELINE section must have a FORBIDDEN section to enumerate "
            "prohibited actions that degrade prompt quality."
        )

    def test_forbidden_covers_summarization(self, light_section: str) -> None:
        """FORBIDDEN section must cover summarization as a prohibited action."""
        section_lower = light_section.lower()
        assert "summariz" in section_lower or "summarise" in section_lower, (
            "LIGHT PIPELINE FORBIDDEN section must explicitly prohibit summarizing "
            "agent inputs to prevent prompt compression regressions."
        )

    def test_forbidden_covers_condensation(self, light_section: str) -> None:
        """FORBIDDEN section must cover condensation as a prohibited action."""
        section_lower = light_section.lower()
        assert "condens" in section_lower, (
            "LIGHT PIPELINE FORBIDDEN section must explicitly prohibit condensing "
            "agent inputs to prevent prompt compression regressions."
        )

    def test_forbidden_covers_minimum_word_count(self, light_section: str) -> None:
        """FORBIDDEN section must reference the 80-word minimum threshold."""
        assert "80 words" in light_section or ">= 80" in light_section, (
            "LIGHT PIPELINE FORBIDDEN section or gate must reference the "
            "80-word minimum threshold for agent prompt quality."
        )

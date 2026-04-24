#!/usr/bin/env python3
"""
Unit Tests for Prompt Integrity Prevention (Issue #601, #603)

Tests for prompt_integrity.py functions that provide real-time prompt
compression prevention for the batch coordinator.
"""

import json
import sys
from pathlib import Path

import pytest

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

from prompt_integrity import (
    COMPRESSION_CRITICAL_AGENTS,
    MIN_CRITICAL_AGENT_PROMPT_WORDS,
    REQUIRED_PROMPT_SLOTS,
    PromptIntegrityResult,
    PromptSlotResult,
    ValidateAndReloadResult,
    clear_prompt_baselines,
    compute_template_baselines,
    get_agent_prompt_template,
    get_prompt_baseline,
    record_prompt_baseline,
    seed_baselines_from_templates,
    validate_and_reload,
    validate_prompt_slots,
    validate_prompt_word_count,
)


class TestGetAgentPromptTemplate:
    """Tests for reading agent prompt templates from disk."""

    def test_get_agent_prompt_template_success(self, tmp_path: Path) -> None:
        """Reads existing agent file and returns its content."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_file = agents_dir / "reviewer.md"
        agent_file.write_text("# Reviewer Agent\n\nYou are the reviewer agent.\n")

        result = get_agent_prompt_template("reviewer", agents_dir=agents_dir)

        assert result == "# Reviewer Agent\n\nYou are the reviewer agent.\n"

    def test_get_agent_prompt_template_missing(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for non-existent agent file."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="Agent prompt template not found"):
            get_agent_prompt_template("nonexistent-agent", agents_dir=agents_dir)


class TestValidatePromptWordCount:
    """Tests for prompt word count validation."""

    def test_validate_no_baseline(self) -> None:
        """Passes if word count > minimum and no baseline provided."""
        prompt = " ".join(["word"] * (MIN_CRITICAL_AGENT_PROMPT_WORDS + 10))
        result = validate_prompt_word_count("implementer", prompt)

        assert result.passed is True
        assert result.should_reload is False
        assert result.shrinkage_pct == 0.0
        assert result.baseline_word_count is None
        assert result.word_count == len(prompt.split())

    def test_validate_within_threshold(self) -> None:
        """10% shrinkage with 15% default threshold passes."""
        # 90 words = 10% shrinkage from 100-word baseline
        prompt = " ".join(["word"] * 90)
        result = validate_prompt_word_count("implementer", prompt, baseline_word_count=100)

        assert result.passed is True
        assert result.should_reload is False
        assert result.shrinkage_pct == 10.0

    def test_validate_exceeds_threshold(self) -> None:
        """25% shrinkage with 15% default threshold fails, should_reload=True."""
        # 150 words = 25% shrinkage from 200-word baseline (above minimum of 80)
        prompt = " ".join(["word"] * 150)
        result = validate_prompt_word_count("implementer", prompt, baseline_word_count=200)

        assert result.passed is False
        assert result.should_reload is True
        assert result.shrinkage_pct == 25.0
        assert "25.0%" in result.reason
        assert "threshold" in result.reason

    def test_validate_critical_agent_minimum(self) -> None:
        """Security-auditor with 50 words fails minimum check."""
        prompt = " ".join(["word"] * 50)
        result = validate_prompt_word_count("security-auditor", prompt)

        assert result.passed is False
        assert result.should_reload is True
        assert "minimum" in result.reason
        assert str(MIN_CRITICAL_AGENT_PROMPT_WORDS) in result.reason

    def test_validate_non_critical_agent_no_minimum(self) -> None:
        """Non-critical agent (e.g., 'test-helper') with 50 words passes (no minimum)."""
        prompt = " ".join(["word"] * 50)
        result = validate_prompt_word_count("test-helper", prompt)

        assert result.passed is True
        assert result.should_reload is False

    def test_validate_empty_prompt(self) -> None:
        """Empty prompt always fails."""
        result = validate_prompt_word_count("implementer", "")

        assert result.passed is False
        assert result.should_reload is True
        assert result.word_count == 0
        assert "empty" in result.reason.lower()

    def test_validate_empty_prompt_with_baseline(self) -> None:
        """Empty prompt with baseline reports 100% shrinkage."""
        result = validate_prompt_word_count("implementer", "", baseline_word_count=100)

        assert result.passed is False
        assert result.shrinkage_pct == 100.0

    def test_validate_custom_max_shrinkage(self) -> None:
        """Custom max_shrinkage threshold is respected."""
        # 15% shrinkage should fail with 10% threshold
        prompt = " ".join(["word"] * 85)
        result = validate_prompt_word_count(
            "implementer", prompt, baseline_word_count=100, max_shrinkage=0.10
        )

        assert result.passed is False
        assert result.should_reload is True

    def test_validate_growth_is_ok(self) -> None:
        """Prompt growing (negative shrinkage) always passes baseline check."""
        # 120 words vs 100 baseline = -20% shrinkage (growth)
        prompt = " ".join(["word"] * 120)
        result = validate_prompt_word_count("implementer", prompt, baseline_word_count=100)

        assert result.passed is True
        assert result.should_reload is False

    def test_validate_critical_agents_set(self) -> None:
        """Verify COMPRESSION_CRITICAL_AGENTS contains expected agents."""
        assert "security-auditor" in COMPRESSION_CRITICAL_AGENTS
        assert "reviewer" in COMPRESSION_CRITICAL_AGENTS

    def test_researcher_agents_are_critical(self) -> None:
        """Regression test for Issue #666: researcher-local and researcher must be
        in COMPRESSION_CRITICAL_AGENTS so prompt compression is detected.

        Without this, a 34% shrinkage in researcher-local goes undetected.
        """
        assert "researcher-local" in COMPRESSION_CRITICAL_AGENTS
        assert "researcher" in COMPRESSION_CRITICAL_AGENTS

    def test_researcher_local_minimum_word_count_enforced(self) -> None:
        """Regression test for Issue #666: researcher-local with <80 words fails."""
        prompt = " ".join(["word"] * 50)
        result = validate_prompt_word_count("researcher-local", prompt)

        assert result.passed is False
        assert result.should_reload is True
        assert "minimum" in result.reason

    def test_researcher_minimum_word_count_enforced(self) -> None:
        """Regression test for Issue #666: researcher with <80 words fails."""
        prompt = " ".join(["word"] * 50)
        result = validate_prompt_word_count("researcher", prompt)

        assert result.passed is False
        assert result.should_reload is True
        assert "minimum" in result.reason


class TestPromptBaselinePersistence:
    """Tests for recording and retrieving prompt baselines."""

    def test_record_and_get_baseline(self, tmp_path: Path) -> None:
        """Record issue 1 baseline, retrieve it."""
        record_prompt_baseline("reviewer", issue_number=1, word_count=500, state_dir=tmp_path)
        baseline = get_prompt_baseline("reviewer", state_dir=tmp_path)

        assert baseline == 500

    def test_get_baseline_no_data(self, tmp_path: Path) -> None:
        """Returns None if no baseline exists."""
        baseline = get_prompt_baseline("reviewer", state_dir=tmp_path)

        assert baseline is None

    def test_record_multiple_issues_baseline_uses_first(self, tmp_path: Path) -> None:
        """Baseline is the word count from the first (lowest number) issue."""
        record_prompt_baseline("reviewer", issue_number=5, word_count=400, state_dir=tmp_path)
        record_prompt_baseline("reviewer", issue_number=2, word_count=500, state_dir=tmp_path)
        record_prompt_baseline("reviewer", issue_number=10, word_count=350, state_dir=tmp_path)

        baseline = get_prompt_baseline("reviewer", state_dir=tmp_path)
        assert baseline == 500  # Issue #2 has the lowest number

    def test_clear_baselines(self, tmp_path: Path) -> None:
        """Clear removes all baseline data."""
        record_prompt_baseline("reviewer", issue_number=1, word_count=500, state_dir=tmp_path)
        record_prompt_baseline("implementer", issue_number=1, word_count=300, state_dir=tmp_path)

        clear_prompt_baselines(state_dir=tmp_path)

        assert get_prompt_baseline("reviewer", state_dir=tmp_path) is None
        assert get_prompt_baseline("implementer", state_dir=tmp_path) is None

    def test_clear_nonexistent_baselines(self, tmp_path: Path) -> None:
        """Clearing when no baselines file exists does not raise."""
        clear_prompt_baselines(state_dir=tmp_path)  # Should not raise

    def test_record_multiple_agents(self, tmp_path: Path) -> None:
        """Multiple agents can be recorded independently."""
        record_prompt_baseline("reviewer", issue_number=1, word_count=500, state_dir=tmp_path)
        record_prompt_baseline(
            "security-auditor", issue_number=1, word_count=600, state_dir=tmp_path
        )

        assert get_prompt_baseline("reviewer", state_dir=tmp_path) == 500
        assert get_prompt_baseline("security-auditor", state_dir=tmp_path) == 600

    def test_baseline_persists_to_json(self, tmp_path: Path) -> None:
        """Verify the baselines file is valid JSON with expected structure."""
        record_prompt_baseline("reviewer", issue_number=1, word_count=500, state_dir=tmp_path)

        baselines_path = tmp_path / "prompt_baselines.json"
        assert baselines_path.exists()

        data = json.loads(baselines_path.read_text())
        assert data == {"reviewer": {"1": 500}}


class TestPromptIntegrityResult:
    """Tests for the PromptIntegrityResult dataclass."""

    def test_prompt_integrity_result_fields(self) -> None:
        """Dataclass fields are accessible and correct."""
        result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=450,
            baseline_word_count=500,
            shrinkage_pct=10.0,
            passed=True,
            reason="Prompt for reviewer OK (450 words).",
            should_reload=False,
        )

        assert result.agent_type == "reviewer"
        assert result.word_count == 450
        assert result.baseline_word_count == 500
        assert result.shrinkage_pct == 10.0
        assert result.passed is True
        assert result.reason == "Prompt for reviewer OK (450 words)."
        assert result.should_reload is False


class TestIssue696RegressionImplementerCompression:
    """Regression tests for Issue #696: 41% implementer prompt compression undetected.

    Bug: COMPRESSION_CRITICAL_AGENTS was missing implementer, planner, and doc-master,
    so their prompts could shrink without triggering validation. max_shrinkage default
    was 0.20 (20%), now tightened to 0.15 (15%).
    """

    def test_implementer_in_critical_agents(self) -> None:
        """Regression: implementer was missing, allowing 41% shrinkage undetected."""
        assert "implementer" in COMPRESSION_CRITICAL_AGENTS

    def test_planner_in_critical_agents(self) -> None:
        """Regression: planner was missing from critical agents."""
        assert "planner" in COMPRESSION_CRITICAL_AGENTS

    def test_doc_master_in_critical_agents(self) -> None:
        """Regression: doc-master was missing from critical agents."""
        assert "doc-master" in COMPRESSION_CRITICAL_AGENTS

    def test_default_max_shrinkage_is_015(self) -> None:
        """Regression: default was 0.20, now 0.15 to catch compression earlier."""
        import inspect

        sig = inspect.signature(validate_prompt_word_count)
        default = sig.parameters["max_shrinkage"].default
        assert default == 0.15, f"Expected default 0.15, got {default}"

    def test_implementer_below_minimum_fails(self) -> None:
        """Implementer with fewer than MIN_CRITICAL_AGENT_PROMPT_WORDS should fail."""
        short_prompt = " ".join(["word"] * (MIN_CRITICAL_AGENT_PROMPT_WORDS - 1))
        result = validate_prompt_word_count("implementer", short_prompt)
        assert result.passed is False
        assert result.should_reload is True
        assert "implementer" in result.reason

    def test_implementer_41pct_shrinkage_caught(self) -> None:
        """The exact bug scenario: 41% shrinkage from 200-word baseline is caught."""
        baseline = 200
        shrunk_prompt = " ".join(["word"] * 118)  # ~41% shrinkage
        result = validate_prompt_word_count("implementer", shrunk_prompt, baseline)
        assert result.passed is False
        assert result.should_reload is True
        assert "shrank" in result.reason

    @pytest.mark.parametrize("agent_type", ["planner", "doc-master"])
    def test_planner_docmaster_below_minimum_fails(self, agent_type: str) -> None:
        """Planner and doc-master below minimum word count should fail."""
        short_prompt = " ".join(["word"] * (MIN_CRITICAL_AGENT_PROMPT_WORDS - 1))
        result = validate_prompt_word_count(agent_type, short_prompt)
        assert result.passed is False
        assert result.should_reload is True
        assert agent_type in result.reason

    def test_pipeline_intent_validator_mirrors_critical_agents(self) -> None:
        """Both modules must have identical COMPRESSION_CRITICAL_AGENTS."""
        from pipeline_intent_validator import (
            COMPRESSION_CRITICAL_AGENTS as VALIDATOR_AGENTS,
        )

        assert COMPRESSION_CRITICAL_AGENTS == VALIDATOR_AGENTS, (
            f"Mismatch between prompt_integrity and pipeline_intent_validator.\n"
            f"prompt_integrity: {COMPRESSION_CRITICAL_AGENTS}\n"
            f"pipeline_intent_validator: {VALIDATOR_AGENTS}"
        )


class TestTemplateBaselineSeeding:
    """Tests for Issue #748/#810: template-based baseline seeding.

    Issue #810: seed_baselines_from_templates() is now a no-op. Template-seeded
    baselines caused 25-50% false positive block rates because template files are
    ~2500 words while actual task-specific prompts are 200-600 words. The
    observation-based path (seeding from the first real prompt) is the correct approach.

    compute_template_baselines() is kept as a pure utility (may still be useful
    for diagnostics), but seed_baselines_from_templates() no longer writes anything.
    """

    def _make_agents_dir(self, tmp_path: Path, agents: dict) -> Path:
        """Helper: create an agents directory with given agent content files.

        Args:
            tmp_path: Temporary directory to create agents dir within.
            agents: Mapping of {agent_type: content_string}.

        Returns:
            Path to the created agents directory.
        """
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        for agent_type, content in agents.items():
            (agents_dir / f"{agent_type}.md").write_text(content, encoding="utf-8")
        return agents_dir

    def test_compute_template_baselines_returns_word_counts(self, tmp_path: Path) -> None:
        """compute_template_baselines() returns correct word counts for existing agents."""
        content_implementer = "word " * 300  # 300 words
        content_reviewer = "token " * 250  # 250 words
        agents_dir = self._make_agents_dir(
            tmp_path,
            {"implementer": content_implementer, "reviewer": content_reviewer},
        )

        baselines = compute_template_baselines(agents_dir=agents_dir)

        assert baselines["implementer"] == 300
        assert baselines["reviewer"] == 250

    def test_compute_template_baselines_skips_missing_agents(self, tmp_path: Path) -> None:
        """compute_template_baselines() skips agents whose template files are absent."""
        # Only create implementer — other critical agents are absent
        agents_dir = self._make_agents_dir(
            tmp_path, {"implementer": "word " * 200}
        )

        baselines = compute_template_baselines(agents_dir=agents_dir)

        # Only implementer should be present; missing agents silently skipped
        assert "implementer" in baselines
        for agent in COMPRESSION_CRITICAL_AGENTS:
            if agent != "implementer":
                assert agent not in baselines

    def test_seed_baselines_from_templates_is_noop(self, tmp_path: Path) -> None:
        """Issue #810: seed_baselines_from_templates() returns {} and writes nothing.

        Template-seeded baselines caused 25-50% false positive block rates.
        The function is now a no-op to prevent pre-empting the observation-based path.
        """
        agents_dir = self._make_agents_dir(
            tmp_path,
            {"implementer": "word " * 400, "reviewer": "token " * 350},
        )
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        result = seed_baselines_from_templates(
            agents_dir=agents_dir, state_dir=state_dir
        )

        # Returns empty dict — no baselines written
        assert result == {}
        # No baseline file written
        assert get_prompt_baseline("implementer", state_dir=state_dir) is None
        assert get_prompt_baseline("reviewer", state_dir=state_dir) is None

    def test_seed_baselines_returns_empty_dict(self, tmp_path: Path) -> None:
        """seed_baselines_from_templates() always returns empty dict (Issue #810)."""
        agents_dir = self._make_agents_dir(tmp_path, {"implementer": "word " * 500})
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        result = seed_baselines_from_templates(agents_dir=agents_dir, state_dir=state_dir)
        assert result == {}, f"Expected {{}}, got {result}"

    def test_observation_based_seeding_works_after_clear(self, tmp_path: Path) -> None:
        """After clear_prompt_baselines(), first observation seeds baseline correctly.

        This verifies the observation-based path that replaced template seeding.
        """
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        # Clear any prior baselines
        clear_prompt_baselines(state_dir=state_dir)
        assert get_prompt_baseline("implementer", state_dir=state_dir) is None

        # First observation sets the baseline
        record_prompt_baseline("implementer", issue_number=5, word_count=320, state_dir=state_dir)
        baseline = get_prompt_baseline("implementer", state_dir=state_dir)
        assert baseline == 320

        # Subsequent prompt within threshold passes
        prompt = " ".join(["word"] * 300)  # ~6.25% shrinkage from 320
        result = validate_prompt_word_count("implementer", prompt, baseline)
        assert result.passed is True


class TestValidateAndReload:
    """Tests for validate_and_reload() — Issue #844.

    After a prompt integrity block + reload, the reloaded prompt was NOT validated
    before re-invocation. validate_and_reload() fixes this by validating the
    reloaded template before returning it.
    """

    def _make_agents_dir(self, tmp_path: Path, agents: dict) -> Path:
        """Helper: create agents directory with given agent content files."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(exist_ok=True)
        for agent_type, content in agents.items():
            (agents_dir / f"{agent_type}.md").write_text(content, encoding="utf-8")
        return agents_dir

    def test_passes_on_first_try(self, tmp_path: Path) -> None:
        """Prompt that passes validation returns immediately without reload."""
        prompt = " ".join(["word"] * 100)
        result = validate_and_reload(prompt, "implementer", baseline_word_count=100)

        assert result.validation.passed is True
        assert result.reload_count == 0
        assert result.reload_succeeded is False
        assert result.prompt == prompt

    def test_reload_succeeds_on_first_attempt(self, tmp_path: Path) -> None:
        """Compressed prompt triggers reload; template from disk passes."""
        # Template has enough words to pass
        template_content = " ".join(["word"] * 200)
        agents_dir = self._make_agents_dir(tmp_path, {"implementer": template_content})

        # Compressed prompt: 50 words vs 200 baseline = 75% shrinkage
        compressed = " ".join(["word"] * 100)
        result = validate_and_reload(
            compressed, "implementer", baseline_word_count=200,
            agents_dir=agents_dir,
        )

        assert result.validation.passed is True
        assert result.reload_count == 1
        assert result.reload_succeeded is True
        assert result.prompt == template_content

    def test_reload_fails_all_attempts(self, tmp_path: Path) -> None:
        """Template on disk also fails validation — all attempts exhausted."""
        # Template has only 50 words — below minimum for critical agents
        template_content = " ".join(["word"] * 50)
        agents_dir = self._make_agents_dir(tmp_path, {"implementer": template_content})

        # Compressed prompt also too short
        compressed = " ".join(["word"] * 30)
        result = validate_and_reload(
            compressed, "implementer", baseline_word_count=200,
            agents_dir=agents_dir, max_reload_attempts=2,
        )

        assert result.validation.passed is False
        assert result.reload_count == 2
        assert result.reload_succeeded is False
        # Should keep the better prompt (template has more words)
        assert result.prompt == template_content

    def test_max_reload_attempts_respected(self, tmp_path: Path) -> None:
        """max_reload_attempts bounds the retry loop."""
        template_content = " ".join(["word"] * 50)
        agents_dir = self._make_agents_dir(tmp_path, {"implementer": template_content})

        compressed = " ".join(["word"] * 30)
        result = validate_and_reload(
            compressed, "implementer", baseline_word_count=200,
            agents_dir=agents_dir, max_reload_attempts=1,
        )

        assert result.reload_count == 1  # Only 1 attempt, not 2

    def test_reload_with_missing_template(self, tmp_path: Path) -> None:
        """Missing template file stops reload gracefully."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # No implementer.md file

        compressed = " ".join(["word"] * 30)
        result = validate_and_reload(
            compressed, "implementer", baseline_word_count=200,
            agents_dir=agents_dir,
        )

        assert result.validation.passed is False
        assert result.reload_succeeded is False
        assert result.prompt == compressed  # Original prompt returned

    def test_reload_keeps_better_prompt(self, tmp_path: Path) -> None:
        """When both fail, returns the prompt with more words."""
        # Template: 70 words (better than compressed, still below baseline threshold)
        template_content = " ".join(["word"] * 70)
        agents_dir = self._make_agents_dir(tmp_path, {"security-auditor": template_content})

        # Compressed: 40 words
        compressed = " ".join(["word"] * 40)
        result = validate_and_reload(
            compressed, "security-auditor", baseline_word_count=200,
            agents_dir=agents_dir,
        )

        assert result.validation.passed is False
        # Template (70 words) is better than compressed (40 words)
        assert result.prompt == template_content

    def test_no_baseline_passes_with_enough_words(self) -> None:
        """Without baseline, a prompt with enough words passes immediately."""
        prompt = " ".join(["word"] * 100)
        result = validate_and_reload(prompt, "implementer")

        assert result.validation.passed is True
        assert result.reload_count == 0

    def test_regression_issue_844_double_block(self, tmp_path: Path) -> None:
        """Regression test for Issue #844: second reload attempt should still validate.

        The bug was that after the first block + reload, the reloaded prompt
        (33.9% compressed) was not validated before re-invocation, causing a
        second block. validate_and_reload validates each reload attempt.
        """
        # Simulate: baseline is 345 words
        baseline = 345
        # First prompt: 137 words (60.3% shrinkage) -- would be blocked
        first_prompt = " ".join(["word"] * 137)
        # Template on disk: 228 words (33.9% shrinkage from 345) -- still fails 15% threshold
        template_228 = " ".join(["word"] * 228)
        agents_dir = self._make_agents_dir(tmp_path, {"implementer": template_228})

        result = validate_and_reload(
            first_prompt, "implementer", baseline_word_count=baseline,
            agents_dir=agents_dir, max_reload_attempts=2,
        )

        # Both attempts fail (template is still 33.9% below baseline)
        assert result.validation.passed is False
        assert result.reload_count == 2
        assert result.reload_succeeded is False
        # But we get the better prompt (228 > 137)
        assert len(result.prompt.split()) == 228


class TestValidatePromptSlots:
    """Tests for validate_prompt_slots() — Issue #844.

    Security-auditor received only 45 words with missing implementer output,
    changed files list, and test results. validate_prompt_slots() catches this
    by checking for required content markers.
    """

    def test_all_slots_present(self) -> None:
        """Prompt with all required markers passes."""
        prompt = (
            "Review the implementer output below. "
            "Here is the changed file list. "
            "The test results show all passing."
        )
        result = validate_prompt_slots("security-auditor", prompt)

        assert result.passed is True
        assert len(result.missing_slots) == 0
        assert len(result.present_slots) == 3

    def test_missing_slots(self) -> None:
        """Prompt missing some markers reports missing slots."""
        prompt = "This is a short prompt with no required content."
        result = validate_prompt_slots("security-auditor", prompt)

        assert result.passed is False
        assert len(result.missing_slots) > 0
        assert "implementer output" in result.missing_slots

    def test_security_auditor_missing_all_slots(self) -> None:
        """Regression for Issue #844: 45-word security-auditor prompt missing everything."""
        # Simulate the actual bug: 45 generic words
        prompt = " ".join(["generic"] * 45)
        result = validate_prompt_slots("security-auditor", prompt)

        assert result.passed is False
        assert "implementer output" in result.missing_slots
        assert "changed files" in result.missing_slots
        assert "test results" in result.missing_slots

    def test_non_critical_agent_always_passes(self) -> None:
        """Agents not in REQUIRED_PROMPT_SLOTS always pass."""
        prompt = "short prompt"
        result = validate_prompt_slots("test-helper", prompt)

        assert result.passed is True
        assert result.missing_slots == []
        assert result.present_slots == []

    def test_partial_slots_present(self) -> None:
        """Prompt with some but not all required markers fails."""
        prompt = "The implementer produced results. No other context provided."
        result = validate_prompt_slots("security-auditor", prompt)

        assert result.passed is False
        assert "implementer output" in result.present_slots
        assert "changed files" in result.missing_slots

    def test_case_insensitive_matching(self) -> None:
        """Marker matching is case-insensitive."""
        prompt = (
            "IMPLEMENTER output here. "
            "CHANGED FILE list below. "
            "TEST results follow."
        )
        result = validate_prompt_slots("security-auditor", prompt)

        assert result.passed is True

    def test_reviewer_has_required_slots(self) -> None:
        """Reviewer agent also has required prompt slots defined."""
        assert "reviewer" in REQUIRED_PROMPT_SLOTS
        slot_names = [name for name, _ in REQUIRED_PROMPT_SLOTS["reviewer"]]
        assert "implementer output" in slot_names
        assert "changed files" in slot_names
        assert "test results" in slot_names

    def test_required_prompt_slots_contains_security_auditor(self) -> None:
        """REQUIRED_PROMPT_SLOTS must include security-auditor."""
        assert "security-auditor" in REQUIRED_PROMPT_SLOTS


class TestIssue907ContractLocks:
    """Lock contracts identified in Issue #907 consolidation."""

    def test_compression_critical_agents_exact_set(self) -> None:
        """AC1: Strict-equality lock for COMPRESSION_CRITICAL_AGENTS (Issue #871)."""
        from prompt_integrity import COMPRESSION_CRITICAL_AGENTS
        expected = {
            "security-auditor", "reviewer", "researcher-local",
            "researcher", "implementer", "planner", "doc-master",
        }
        assert COMPRESSION_CRITICAL_AGENTS == expected, (
            f"COMPRESSION_CRITICAL_AGENTS drift detected. "
            f"Missing: {expected - COMPRESSION_CRITICAL_AGENTS}. "
            f"Unexpected: {COMPRESSION_CRITICAL_AGENTS - expected}."
        )

    def test_save_merged_research_signature_arity(self) -> None:
        """AC4: Lock save_merged_research parameter count + names (Issue #899)."""
        import inspect
        from research_persistence import save_merged_research
        sig = inspect.signature(save_merged_research)
        params = list(sig.parameters)
        assert len(params) == 3, (
            f"save_merged_research signature drift: expected 3 params, got {len(params)}: {params}"
        )
        assert params == ["topic", "local_json", "web_json"], (
            f"save_merged_research parameter names drifted: {params}"
        )

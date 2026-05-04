"""Regression tests for Phase 2 (#961) classifier-gated routing in implement.md.

Hybrid strategy:
- Markdown structure tests (TestImplementMdGateText): verify gate text exists.
- Predicate tests: exercise the pure functions in pipeline_intent_gates.
- State persistence tests: verify the new state helpers persist.

Issues: #961
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENT_PATH = PROJECT_ROOT / "plugins/autonomous-dev/commands/implement.md"
LIB_PATH = PROJECT_ROOT / "plugins/autonomous-dev/lib"
sys.path.insert(0, str(LIB_PATH))


# ---------- Markdown structure ----------


class TestImplementMdGateText:
    @pytest.fixture
    def md(self):
        return IMPLEMENT_PATH.read_text()

    def test_step_3_6_section_exists(self, md):
        assert "STEP 3.6" in md, "STEP 3.6 web-research gate section missing"
        assert "should_skip_web_research" in md
        assert "INTENT_CLASSIFIER_ENABLED" in md

    def test_step_3_6_appears_before_step_4(self, md):
        assert md.find("STEP 3.6") < md.find("### STEP 4: Parallel Research")

    def test_step_5_5a_1_section_exists(self, md):
        assert "5.5a.1" in md
        assert "should_skip_plan_critic" in md

    def test_step_5_5a_1_before_5_5b(self, md):
        assert md.find("5.5a.1") < md.find("#### 5.5b")

    def test_strict_flag_documented_in_both_gates(self, md):
        s36_start = md.find("STEP 3.6")
        s4_start = md.find("### STEP 4: Parallel Research")
        assert s36_start != -1 and s4_start != -1
        s36 = md[s36_start:s4_start]

        s551_start = md.find("5.5a.1")
        s55b_start = md.find("#### 5.5b")
        assert s551_start != -1 and s55b_start != -1
        s551 = md[s551_start:s55b_start]

        assert "--strict" in s36
        assert "--strict" in s551

    def test_5_5c_still_always_runs(self, md):
        # The structural validation gate must remain unconditional.
        s551_start = md.find("5.5a.1")
        s55b_start = md.find("#### 5.5b")
        s551_section = md[s551_start:s55b_start]
        assert "5.5c" in s551_section, "5.5c (structural validation) must be referenced in 5.5a.1"

    def test_researcher_local_always_runs(self, md):
        # Verify the dispatch block states researcher-local always runs.
        s4_start = md.find("### STEP 4: Parallel Research")
        s45_start = md.find("### STEP 4.5:")
        s4_section = md[s4_start:s45_start]
        assert "Always" in s4_section or "researcher-local" in s4_section


# ---------- Predicate logic ----------


@pytest.fixture
def fake_result():
    """Build a fake IntentResult-like object (real frozen dataclass, fake values)."""
    from intent_classifier import IntentClass, IntentResult

    def _make(
        intent="refactor",
        confidence=0.9,
        file_count=2,
        fail_open=False,
    ):
        return IntentResult(
            intent=IntentClass(intent),
            confidence=confidence,
            regex_hit=False,
            llm_used=True,
            fail_open=fail_open,
            requires_security_audit=False,
            prompt_length=50,
            predicted_file_count=file_count,
            reasoning="test",
        )

    return _make


class TestWebResearchGate:
    def test_disabled_by_default(self, fake_result, monkeypatch):
        from pipeline_intent_gates import should_skip_web_research

        monkeypatch.delenv("INTENT_CLASSIFIER_ENABLED", raising=False)
        skip, reason = should_skip_web_research(
            feature_description="x",
            classifier_result=fake_result(intent="config"),
        )
        assert skip is False
        assert reason == "disabled"

    def test_strict_blocks_skip(self, fake_result, monkeypatch):
        from pipeline_intent_gates import should_skip_web_research

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, reason = should_skip_web_research(
            feature_description="x",
            arguments="--strict",
            classifier_result=fake_result(intent="config"),
        )
        assert skip is False
        assert reason == "strict"

    @pytest.mark.parametrize("intent", ["config", "doc", "refactor"])
    def test_skips_for_allowed_intents(self, fake_result, monkeypatch, intent):
        from pipeline_intent_gates import should_skip_web_research

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, reason = should_skip_web_research(
            feature_description="x",
            classifier_result=fake_result(intent=intent, confidence=0.9),
        )
        assert skip is True
        assert reason == f"classifier:{intent}"

    @pytest.mark.parametrize("intent", ["implement", "security_critical", "test", "typo"])
    def test_does_not_skip_other_intents(self, fake_result, monkeypatch, intent):
        from pipeline_intent_gates import should_skip_web_research

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, _ = should_skip_web_research(
            feature_description="x",
            classifier_result=fake_result(intent=intent),
        )
        assert skip is False

    def test_ambiguous_does_not_skip(self, fake_result, monkeypatch):
        from pipeline_intent_gates import should_skip_web_research

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, reason = should_skip_web_research(
            feature_description="x",
            classifier_result=fake_result(intent="ambiguous", fail_open=True),
        )
        assert skip is False
        assert reason == "fail_open"

    def test_low_confidence_does_not_skip(self, fake_result, monkeypatch):
        from pipeline_intent_gates import should_skip_web_research

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, reason = should_skip_web_research(
            feature_description="x",
            classifier_result=fake_result(intent="config", confidence=0.5),
        )
        assert skip is False
        assert reason == "low_confidence"


class TestPlanCriticGate:
    def test_skips_for_small_refactor(self, fake_result, monkeypatch):
        from pipeline_intent_gates import should_skip_plan_critic

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, reason = should_skip_plan_critic(
            feature_description="x",
            classifier_result=fake_result(intent="refactor", file_count=2),
        )
        assert skip is True

    def test_does_not_skip_when_files_exceed_3(self, fake_result, monkeypatch):
        from pipeline_intent_gates import should_skip_plan_critic

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, reason = should_skip_plan_critic(
            feature_description="x",
            classifier_result=fake_result(intent="refactor", file_count=5),
        )
        assert skip is False
        assert reason == "file_count:5"

    @pytest.mark.parametrize(
        "intent,file_count",
        [
            ("typo", 1),
            ("doc", 1),
            ("config", 3),
        ],
    )
    def test_allowed_intents_within_file_limit(
        self, fake_result, monkeypatch, intent, file_count
    ):
        from pipeline_intent_gates import should_skip_plan_critic

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, _ = should_skip_plan_critic(
            feature_description="x",
            classifier_result=fake_result(intent=intent, file_count=file_count),
        )
        assert skip is True

    def test_implement_intent_never_skips(self, fake_result, monkeypatch):
        from pipeline_intent_gates import should_skip_plan_critic

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, _ = should_skip_plan_critic(
            feature_description="x",
            classifier_result=fake_result(intent="implement", file_count=2),
        )
        assert skip is False

    def test_strict_blocks_skip(self, fake_result, monkeypatch):
        from pipeline_intent_gates import should_skip_plan_critic

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        skip, reason = should_skip_plan_critic(
            feature_description="x",
            arguments="--batch --strict",
            classifier_result=fake_result(intent="doc"),
        )
        assert skip is False
        assert reason == "strict"

    def test_classifier_exception_fails_open(self, monkeypatch):
        from pipeline_intent_gates import should_skip_plan_critic

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", "true")
        with patch("pipeline_intent_gates.classify_prompt", side_effect=RuntimeError("boom")):
            skip, reason = should_skip_plan_critic(feature_description="x")
        assert skip is False
        assert reason == "classifier_exception"


class TestEnvVarTruthiness:
    @pytest.mark.parametrize(
        "val,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("YES", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("", False),
            ("anything_else", False),
        ],
    )
    def test_truthy(self, val, expected, monkeypatch):
        from pipeline_intent_gates import classifier_enabled

        monkeypatch.setenv("INTENT_CLASSIFIER_ENABLED", val)
        assert classifier_enabled() is expected


class TestPipelineStateSkipFlags:
    def test_record_web_research_skipped_persists(self):
        from pipeline_completion_state import (
            get_web_research_skipped,
            record_web_research_skipped,
        )

        sid = f"test-961-{os.getpid()}"
        record_web_research_skipped(sid, issue_number=961, reason="classifier:config")
        assert get_web_research_skipped(sid, issue_number=961) is True

    def test_record_plan_critic_skipped_with_reason(self):
        from pipeline_completion_state import (
            get_plan_critic_skipped,
            record_plan_critic_skipped,
        )

        sid = f"test-961-pc-{os.getpid()}"
        record_plan_critic_skipped(sid, issue_number=961, reason="classifier")
        assert get_plan_critic_skipped(sid, issue_number=961) is True

    def test_get_plan_critic_skipped_backward_compat_bool(self):
        """get_plan_critic_skipped MUST handle legacy bool=True entries (#961 backward compat)."""
        from pipeline_completion_state import (
            _ensure_state,
            _write_state,
            get_plan_critic_skipped,
        )

        sid = f"test-961-legacy-{os.getpid()}"
        # Write a legacy bool entry directly
        state = _ensure_state(sid)
        state.setdefault("plan_critic_skipped", {})["0"] = True
        _write_state(sid, state)
        assert get_plan_critic_skipped(sid) is True

    def test_web_research_skipped_returns_false_for_unset(self):
        from pipeline_completion_state import get_web_research_skipped

        sid = f"test-961-unset-{os.getpid()}"
        assert get_web_research_skipped(sid, issue_number=0) is False

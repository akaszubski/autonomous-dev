"""Unit tests for GenAI client enhancements: temperature, judge_analytic, judge_consistent.

Tests the new GenAI client methods without requiring OpenRouter API access.
All OpenAI client calls are mocked.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from tests.genai._genai_support import GenAIClient, SoftFailureTracker, _extract_json_from_response


def _make_mock_response(content: str, prompt_tokens: int = 10, completion_tokens: int = 20):
    """Create a mock OpenAI chat completion response."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


def _make_client() -> GenAIClient:
    """Create a GenAIClient with mocked OpenAI client and disabled cache."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-fake"}):
        with patch("openai.OpenAI"):
            client = GenAIClient(model="test/model")
    client._client = MagicMock()
    # Disable filesystem cache to avoid cross-test interference
    client._get_cached = MagicMock(return_value=None)
    client._set_cached = MagicMock()
    return client


# --- Temperature Enforcement ---


class TestTemperatureEnforcement:
    """Verify temperature=0 is passed to API and included in cache key."""

    def test_default_temperature_is_zero(self):
        """ask() defaults to temperature=0."""
        client = _make_client()
        mock_response = _make_mock_response('{"result": "ok"}')
        client._client.chat.completions.create.return_value = mock_response

        client.ask("test prompt")

        create_call = client._client.chat.completions.create.call_args
        assert create_call.kwargs.get("temperature") == 0 or \
               (len(create_call.args) == 0 and create_call[1].get("temperature") == 0)

    def test_custom_temperature_passed_to_api(self):
        """ask() passes custom temperature to the API."""
        client = _make_client()
        mock_response = _make_mock_response('{"result": "ok"}')
        client._client.chat.completions.create.return_value = mock_response

        client.ask("test prompt", temperature=0.7)

        create_call = client._client.chat.completions.create.call_args
        assert create_call[1].get("temperature") == 0.7

    def test_cache_key_includes_temperature(self):
        """Different temperatures produce different cache keys."""
        client = _make_client()
        key_t0 = client._cache_key("prompt", "system", temperature=0)
        key_t1 = client._cache_key("prompt", "system", temperature=1.0)
        assert key_t0 != key_t1, "Cache keys should differ for different temperatures"

    def test_cache_key_same_temperature_same_key(self):
        """Same temperature produces same cache key."""
        client = _make_client()
        key1 = client._cache_key("prompt", "system", temperature=0)
        key2 = client._cache_key("prompt", "system", temperature=0)
        assert key1 == key2


# --- Judge Analytic ---


class TestJudgeAnalytic:
    """Tests for judge_analytic() per-criterion decomposition."""

    def test_all_criteria_met(self):
        """All criteria met produces full score and pass band."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"met": True, "reasoning": "criterion 1 met"})),
            _make_mock_response(json.dumps({"met": True, "reasoning": "criterion 2 met"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_analytic(
            question="Test question",
            context="Test context",
            criteria=[
                {"name": "Completeness", "description": "Is it complete?", "max_points": 1},
                {"name": "Clarity", "description": "Is it clear?", "max_points": 1},
            ],
        )

        assert result["total_score"] == 2
        assert result["max_score"] == 2
        assert result["pass"] is True
        assert result["band"] == "pass"
        assert len(result["criteria_results"]) == 2
        assert all(cr["met"] for cr in result["criteria_results"])

    def test_partial_criteria_met(self):
        """Some criteria met produces partial score."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"met": True, "reasoning": "good"})),
            _make_mock_response(json.dumps({"met": False, "reasoning": "missing"})),
            _make_mock_response(json.dumps({"met": True, "reasoning": "ok"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_analytic(
            question="Test question",
            context="Test context",
            criteria=[
                {"name": "A", "description": "desc A", "max_points": 1},
                {"name": "B", "description": "desc B", "max_points": 1},
                {"name": "C", "description": "desc C", "max_points": 1},
            ],
        )

        assert result["total_score"] == 2
        assert result["max_score"] == 3
        assert result["criteria_results"][0]["met"] is True
        assert result["criteria_results"][1]["met"] is False
        assert result["criteria_results"][2]["met"] is True

    def test_no_criteria_met_hard_fail(self):
        """No criteria met produces score 0 and hard_fail band."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"met": False, "reasoning": "bad"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_analytic(
            question="Test",
            context="Test",
            criteria=[{"name": "X", "description": "desc", "max_points": 1}],
        )

        assert result["total_score"] == 0
        assert result["band"] == "hard_fail"
        assert result["pass"] is False

    def test_weighted_scoring(self):
        """Different max_points weights produce correct totals."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"met": True, "reasoning": "ok"})),
            _make_mock_response(json.dumps({"met": False, "reasoning": "bad"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_analytic(
            question="Test",
            context="Test",
            criteria=[
                {"name": "Major", "description": "desc", "max_points": 3},
                {"name": "Minor", "description": "desc", "max_points": 1},
            ],
        )

        assert result["total_score"] == 3
        assert result["max_score"] == 4
        assert result["criteria_results"][0]["points"] == 3
        assert result["criteria_results"][1]["points"] == 0

    def test_band_classification_uses_normalized_score(self):
        """Band classification normalizes to 0-10 scale."""
        client = _make_client()
        # 7/10 criteria met = normalized 7.0 -> pass (default threshold)
        responses = []
        for i in range(10):
            met = i < 7
            responses.append(_make_mock_response(json.dumps({"met": met, "reasoning": "r"})))
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_analytic(
            question="Test",
            context="Test",
            criteria=[{"name": f"C{i}", "description": "d", "max_points": 1} for i in range(10)],
        )

        assert result["total_score"] == 7
        assert result["max_score"] == 10
        assert result["band"] == "pass"

    def test_malformed_response_treated_as_unmet(self):
        """Unparseable LLM responses treated as criterion UNMET."""
        client = _make_client()
        responses = [
            _make_mock_response("This is not valid JSON at all"),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_analytic(
            question="Test",
            context="Test",
            criteria=[{"name": "X", "description": "d", "max_points": 1}],
        )

        assert result["criteria_results"][0]["met"] is False
        assert "Failed to parse" in result["criteria_results"][0]["reasoning"]

    def test_reasoning_concatenates_per_criterion(self):
        """Reasoning string contains all criterion results."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"met": True, "reasoning": "great"})),
            _make_mock_response(json.dumps({"met": False, "reasoning": "bad"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_analytic(
            question="Test",
            context="Test",
            criteria=[
                {"name": "Alpha", "description": "d", "max_points": 1},
                {"name": "Beta", "description": "d", "max_points": 1},
            ],
        )

        assert "Alpha: MET" in result["reasoning"]
        assert "Beta: UNMET" in result["reasoning"]

    def test_one_api_call_per_criterion(self):
        """Verifies exactly one LLM call per criterion."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"met": True, "reasoning": "ok"})),
            _make_mock_response(json.dumps({"met": True, "reasoning": "ok"})),
            _make_mock_response(json.dumps({"met": True, "reasoning": "ok"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        client.judge_analytic(
            question="Test",
            context="Test",
            criteria=[
                {"name": "A", "description": "d", "max_points": 1},
                {"name": "B", "description": "d", "max_points": 1},
                {"name": "C", "description": "d", "max_points": 1},
            ],
        )

        assert client._client.chat.completions.create.call_count == 3


# --- Judge Consistent ---


class TestJudgeConsistent:
    """Tests for judge_consistent() multi-round evaluation."""

    def test_consistent_high_scores(self):
        """All rounds agree on pass -> agreement=True."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"pass": True, "score": 8, "reasoning": "good"})),
            _make_mock_response(json.dumps({"pass": True, "score": 9, "reasoning": "great"})),
            _make_mock_response(json.dumps({"pass": True, "score": 8, "reasoning": "solid"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_consistent(
            question="Test",
            context="Test",
            criteria="Test criteria",
        )

        assert result["agreement"] is True
        assert result["final_score"] == 8  # median of [8, 9, 8]
        assert result["pass"] is True
        assert result["band"] == "pass"
        assert len(result["rounds"]) == 3
        assert result["scores"] == [8, 9, 8]

    def test_inconsistent_rounds(self):
        """Disagreement on pass/fail -> agreement=False."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"pass": True, "score": 8, "reasoning": "good"})),
            _make_mock_response(json.dumps({"pass": False, "score": 5, "reasoning": "bad"})),
            _make_mock_response(json.dumps({"pass": True, "score": 7, "reasoning": "ok"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_consistent(
            question="Test",
            context="Test",
            criteria="Test criteria",
        )

        assert result["agreement"] is False
        assert result["final_score"] == 7  # median of [8, 5, 7]

    def test_custom_rounds(self):
        """Custom round count produces correct number of calls."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"pass": True, "score": 8, "reasoning": "r"}))
            for _ in range(5)
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_consistent(
            question="Test",
            context="Test",
            criteria="Test criteria",
            rounds=5,
        )

        assert len(result["rounds"]) == 5
        assert client._client.chat.completions.create.call_count == 5

    def test_median_score_calculation(self):
        """Final score is the statistical median."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"pass": True, "score": 3, "reasoning": "r"})),
            _make_mock_response(json.dumps({"pass": True, "score": 9, "reasoning": "r"})),
            _make_mock_response(json.dumps({"pass": True, "score": 7, "reasoning": "r"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_consistent(
            question="Test",
            context="Test",
            criteria="Test criteria",
        )

        assert result["final_score"] == 7  # median of [3, 9, 7]

    def test_cache_busting_different_prompts(self):
        """Each round uses a different prompt (includes round number)."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"pass": True, "score": 8, "reasoning": "r"}))
            for _ in range(3)
        ]
        client._client.chat.completions.create.side_effect = responses

        client.judge_consistent(
            question="Test",
            context="Test",
            criteria="Test criteria",
            rounds=3,
        )

        calls = client._client.chat.completions.create.call_args_list
        # Extract user messages from each call to verify they differ
        user_prompts = []
        for c in calls:
            messages = c[1]["messages"]
            user_msg = [m for m in messages if m["role"] == "user"][0]["content"]
            user_prompts.append(user_msg)

        # All prompts should be unique (cache-busting via round number)
        assert len(set(user_prompts)) == 3

    def test_malformed_response_scores_zero(self):
        """Unparseable responses default to score 0."""
        client = _make_client()
        responses = [
            _make_mock_response("not json"),
            _make_mock_response(json.dumps({"pass": True, "score": 8, "reasoning": "ok"})),
            _make_mock_response(json.dumps({"pass": True, "score": 6, "reasoning": "ok"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_consistent(
            question="Test",
            context="Test",
            criteria="Test criteria",
        )

        assert result["scores"] == [0, 8, 6]
        assert result["final_score"] == 6  # median of [0, 8, 6]

    def test_reasoning_includes_all_rounds(self):
        """Reasoning string references all rounds."""
        client = _make_client()
        responses = [
            _make_mock_response(json.dumps({"pass": True, "score": 8, "reasoning": "round one reason"})),
            _make_mock_response(json.dumps({"pass": True, "score": 7, "reasoning": "round two reason"})),
        ]
        client._client.chat.completions.create.side_effect = responses

        result = client.judge_consistent(
            question="Test",
            context="Test",
            criteria="Test criteria",
            rounds=2,
        )

        assert "Round 1" in result["reasoning"]
        assert "Round 2" in result["reasoning"]


# --- Backward Compatibility ---


class TestBackwardCompatibility:
    """Ensure existing judge() method works unchanged."""

    def test_judge_still_works(self):
        """Existing judge() returns expected keys without breaking."""
        client = _make_client()
        mock_response = _make_mock_response(
            json.dumps({"pass": True, "score": 8, "reasoning": "good"})
        )
        client._client.chat.completions.create.return_value = mock_response

        result = client.judge(
            question="Is this good?",
            context="Some content",
            criteria="Should be good",
        )

        assert "pass" in result
        assert "score" in result
        assert "reasoning" in result
        assert "band" in result

    def test_judge_does_not_require_temperature_arg(self):
        """judge() works without explicitly passing temperature."""
        client = _make_client()
        mock_response = _make_mock_response(
            json.dumps({"pass": True, "score": 9, "reasoning": "excellent"})
        )
        client._client.chat.completions.create.return_value = mock_response

        # Should not raise
        result = client.judge(
            question="Q",
            context="C",
            criteria="K",
        )
        assert result["score"] == 9

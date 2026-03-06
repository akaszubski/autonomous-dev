"""Tests for SkillEvaluator and BenchmarkStore classes.

Unit tests that mock GenAI calls to test evaluation logic in isolation.
These tests should fail initially (TDD red phase) since the implementation
does not exist yet.
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add lib to path for imports once implementation exists
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"))


# ============================================================================
# BenchmarkStore Tests
# ============================================================================


class TestBenchmarkStoreLoadEmpty:
    """Test BenchmarkStore loading behavior with empty/missing files."""

    def test_load_empty_file(self, tmp_path):
        """Loading a nonexistent benchmark file returns default structure."""
        from skill_evaluator import BenchmarkStore

        store = BenchmarkStore(path=tmp_path / "nonexistent.json")
        data = store.load()

        assert isinstance(data, dict)
        assert "baselines" in data
        assert "metadata" in data
        assert isinstance(data["baselines"], dict)

    def test_load_existing(self, tmp_path):
        """Loading an existing valid JSON file reads it correctly."""
        from skill_evaluator import BenchmarkStore

        benchmark_data = {
            "baselines": {
                "python-standards": {
                    "score": 8.5,
                    "timestamp": "2026-03-01T00:00:00",
                }
            },
            "metadata": {"version": 1},
        }
        benchmark_file = tmp_path / "benchmarks.json"
        benchmark_file.write_text(json.dumps(benchmark_data))

        store = BenchmarkStore(path=benchmark_file)
        data = store.load()

        assert data["baselines"]["python-standards"]["score"] == 8.5

    def test_save_and_load_roundtrip(self, tmp_path):
        """Data saved via save() can be loaded back identically."""
        from skill_evaluator import BenchmarkStore

        benchmark_file = tmp_path / "benchmarks.json"
        store = BenchmarkStore(path=benchmark_file)

        # Save some data
        store.update_baseline("testing-guide", score=7.5, metadata={"model": "test"})
        store.save()

        # Load in a new instance
        store2 = BenchmarkStore(path=benchmark_file)
        data = store2.load()

        assert "testing-guide" in data["baselines"]
        assert data["baselines"]["testing-guide"]["score"] == 7.5

    def test_get_baseline_existing(self, tmp_path):
        """get_baseline returns baseline dict for a known skill."""
        from skill_evaluator import BenchmarkStore

        benchmark_file = tmp_path / "benchmarks.json"
        benchmark_data = {
            "baselines": {
                "python-standards": {
                    "score": 8.0,
                    "timestamp": "2026-03-01T00:00:00",
                }
            },
            "metadata": {"version": 1},
        }
        benchmark_file.write_text(json.dumps(benchmark_data))

        store = BenchmarkStore(path=benchmark_file)
        baseline = store.get_baseline("python-standards")

        assert baseline is not None
        assert baseline["score"] == 8.0

    def test_get_baseline_missing(self, tmp_path):
        """get_baseline returns None for an unknown skill."""
        from skill_evaluator import BenchmarkStore

        store = BenchmarkStore(path=tmp_path / "empty.json")
        baseline = store.get_baseline("nonexistent-skill")

        assert baseline is None

    def test_update_baseline(self, tmp_path):
        """update_baseline stores scores with metadata and timestamp."""
        from skill_evaluator import BenchmarkStore

        store = BenchmarkStore(path=tmp_path / "bench.json")
        store.update_baseline("security-patterns", score=9.0, metadata={"model": "flash"})

        baseline = store.get_baseline("security-patterns")
        assert baseline is not None
        assert baseline["score"] == 9.0
        assert "timestamp" in baseline
        assert baseline["metadata"]["model"] == "flash"

    def test_update_baseline_overwrites(self, tmp_path):
        """Updating an existing baseline replaces the old one."""
        from skill_evaluator import BenchmarkStore

        store = BenchmarkStore(path=tmp_path / "bench.json")
        store.update_baseline("python-standards", score=7.0, metadata={"run": 1})
        store.update_baseline("python-standards", score=9.0, metadata={"run": 2})

        baseline = store.get_baseline("python-standards")
        assert baseline["score"] == 9.0
        assert baseline["metadata"]["run"] == 2


# ============================================================================
# SkillEvaluator Tests
# ============================================================================


class TestSkillEvaluatorEvaluate:
    """Test SkillEvaluator.evaluate_skill() method."""

    def test_evaluate_skill_calls_judge(self, tmp_path):
        """evaluate_skill should call genai.judge with correct arguments."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        mock_genai = MagicMock()
        mock_genai.judge.return_value = {
            "pass": True,
            "score": 8,
            "reasoning": "Good quality",
            "band": "pass",
        }

        store = BenchmarkStore(path=tmp_path / "bench.json")
        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        result = evaluator.evaluate_skill(
            skill_name="python-standards",
            skill_content="# Python Standards\nUse type hints.",
            prompt="Review this code for Python standards compliance.",
        )

        mock_genai.judge.assert_called_once()
        call_kwargs = mock_genai.judge.call_args
        # Verify the skill name or content appears in the judge call
        assert "python-standards" in str(call_kwargs) or "Python Standards" in str(call_kwargs)

    def test_evaluate_skill_returns_enriched_dict(self, tmp_path):
        """evaluate_skill returns dict with score, skill_name, and timestamp."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        mock_genai = MagicMock()
        mock_genai.judge.return_value = {
            "pass": True,
            "score": 7,
            "reasoning": "Adequate",
            "band": "pass",
        }

        store = BenchmarkStore(path=tmp_path / "bench.json")
        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        result = evaluator.evaluate_skill(
            skill_name="testing-guide",
            skill_content="# Testing Guide\nWrite tests first.",
            prompt="Write tests for this module.",
        )

        assert "score" in result
        assert "skill_name" in result
        assert "timestamp" in result
        assert result["skill_name"] == "testing-guide"
        assert isinstance(result["score"], (int, float))

    def test_evaluate_skill_batch_evaluates_all(self, tmp_path):
        """evaluate_skill_batch evaluates all provided prompts."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        mock_genai = MagicMock()
        mock_genai.judge.return_value = {
            "pass": True,
            "score": 8,
            "reasoning": "Good",
            "band": "pass",
        }

        store = BenchmarkStore(path=tmp_path / "bench.json")
        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        prompts = [
            "Review code for standards",
            "Check type hints",
            "Validate docstrings",
        ]

        results = evaluator.evaluate_skill_batch(
            skill_name="python-standards",
            skill_content="# Python Standards",
            prompts=prompts,
        )

        assert len(results) == 3
        assert mock_genai.judge.call_count == 3
        assert all("score" in r for r in results)


class TestSkillEvaluatorCompare:
    """Test SkillEvaluator.compare_variants() A/B testing."""

    def test_compare_variants_minimum_samples(self, tmp_path):
        """compare_variants raises ValueError if fewer than 10 prompts provided."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        mock_genai = MagicMock()
        store = BenchmarkStore(path=tmp_path / "bench.json")
        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        with pytest.raises(ValueError, match="10"):
            evaluator.compare_variants(
                skill_name="python-standards",
                variant_a="# Version A",
                variant_b="# Version B",
                prompts=["prompt1", "prompt2", "prompt3"],  # Only 3 < 10
            )

    def test_compare_variants_returns_winner(self, tmp_path):
        """compare_variants returns the winning variant based on scores."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        call_count = 0

        def mock_judge(**kwargs):
            nonlocal call_count
            call_count += 1
            # Variant A gets higher scores (odd calls = A, even = B)
            if call_count % 2 == 1:
                return {"pass": True, "score": 9, "reasoning": "Excellent", "band": "pass"}
            else:
                return {"pass": True, "score": 6, "reasoning": "OK", "band": "soft_fail"}

        mock_genai = MagicMock()
        mock_genai.judge.side_effect = mock_judge

        store = BenchmarkStore(path=tmp_path / "bench.json")
        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        prompts = [f"Test prompt {i}" for i in range(10)]
        result = evaluator.compare_variants(
            skill_name="python-standards",
            variant_a="# Version A - detailed",
            variant_b="# Version B - brief",
            prompts=prompts,
        )

        assert "winner" in result
        assert result["winner"] in ("A", "B", "tie")
        assert "mean_a" in result
        assert "mean_b" in result

    def test_compare_variants_paired(self, tmp_path):
        """Same prompts are evaluated for both variants (paired comparison)."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        mock_genai = MagicMock()
        mock_genai.judge.return_value = {
            "pass": True,
            "score": 7,
            "reasoning": "OK",
            "band": "pass",
        }

        store = BenchmarkStore(path=tmp_path / "bench.json")
        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        prompts = [f"Prompt {i}" for i in range(10)]
        result = evaluator.compare_variants(
            skill_name="testing-guide",
            variant_a="# A",
            variant_b="# B",
            prompts=prompts,
        )

        # Each prompt evaluated twice (once per variant) = 20 total calls
        assert mock_genai.judge.call_count == 20
        assert "scores_a" in result
        assert "scores_b" in result
        assert len(result["scores_a"]) == 10
        assert len(result["scores_b"]) == 10


class TestSkillEvaluatorRegression:
    """Test SkillEvaluator.check_regression() method."""

    def test_check_regression_no_baseline(self, tmp_path):
        """Returns regressed=False when no baseline exists."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        mock_genai = MagicMock()
        mock_genai.judge.return_value = {
            "pass": True,
            "score": 7,
            "reasoning": "OK",
            "band": "pass",
        }

        store = BenchmarkStore(path=tmp_path / "bench.json")
        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        result = evaluator.check_regression(
            skill_name="new-skill",
            skill_content="# New Skill",
            prompts=["test prompt"],
        )

        assert result["regressed"] is False
        assert "no_baseline" in result.get("reason", "no_baseline")

    def test_check_regression_within_threshold(self, tmp_path):
        """5% drop should not flag regression (threshold is 10%)."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        mock_genai = MagicMock()
        # Current score: 7.6 (5% below baseline of 8.0)
        mock_genai.judge.return_value = {
            "pass": True,
            "score": 7.6,
            "reasoning": "OK",
            "band": "pass",
        }

        store = BenchmarkStore(path=tmp_path / "bench.json")
        store.update_baseline("python-standards", score=8.0, metadata={})
        store.save()

        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        result = evaluator.check_regression(
            skill_name="python-standards",
            skill_content="# Python Standards",
            prompts=["test prompt"],
        )

        assert result["regressed"] is False

    def test_check_regression_exceeds_threshold(self, tmp_path):
        """15% drop should flag regressed=True."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        mock_genai = MagicMock()
        # Current score: 6.8 (15% below baseline of 8.0)
        mock_genai.judge.return_value = {
            "pass": True,
            "score": 6.8,
            "reasoning": "Quality dropped",
            "band": "soft_fail",
        }

        store = BenchmarkStore(path=tmp_path / "bench.json")
        store.update_baseline("python-standards", score=8.0, metadata={})
        store.save()

        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        result = evaluator.check_regression(
            skill_name="python-standards",
            skill_content="# Python Standards",
            prompts=["test prompt"],
        )

        assert result["regressed"] is True

    def test_check_regression_improvement(self, tmp_path):
        """Scores improved from baseline should not flag regression."""
        from skill_evaluator import BenchmarkStore, SkillEvaluator

        mock_genai = MagicMock()
        mock_genai.judge.return_value = {
            "pass": True,
            "score": 9.5,
            "reasoning": "Excellent",
            "band": "pass",
        }

        store = BenchmarkStore(path=tmp_path / "bench.json")
        store.update_baseline("python-standards", score=8.0, metadata={})
        store.save()

        evaluator = SkillEvaluator(genai_client=mock_genai, benchmark_store=store)

        result = evaluator.check_regression(
            skill_name="python-standards",
            skill_content="# Python Standards",
            prompts=["test prompt"],
        )

        assert result["regressed"] is False

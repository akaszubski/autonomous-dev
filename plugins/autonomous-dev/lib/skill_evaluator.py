"""Skill Evaluation Framework - BenchmarkStore and SkillEvaluator.

Provides:
- BenchmarkStore: Reads/writes skill benchmark JSON for regression tracking
- SkillEvaluator: Evaluates skill quality via LLM-as-judge pattern

Usage:
    from skill_evaluator import BenchmarkStore, SkillEvaluator

    store = BenchmarkStore(path=Path("benchmarks.json"))
    evaluator = SkillEvaluator(genai_client=client, benchmark_store=store)
    result = evaluator.evaluate_skill("python-standards", content, "Evaluate quality")
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_SKILL_NAME_RE = re.compile(r"[a-zA-Z0-9_-]{1,64}")


class BenchmarkStore:
    """Reads/writes skill benchmark JSON for regression tracking.

    Args:
        path: Path to the benchmark JSON file
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        """Load benchmark data from file.

        Returns:
            Dict with 'baselines' and 'metadata' keys.
            Returns default structure if file doesn't exist.
        """
        if self._data is not None:
            return self._data

        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
                return self._data
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Could not read benchmark file {self._path}: {e}", file=sys.stderr)

        self._data = {
            "baselines": {},
            "metadata": {"version": 1},
        }
        return self._data

    def save(self) -> None:
        """Write current benchmark data to file."""
        data = self.load()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def get_baseline(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get baseline data for a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Baseline dict if exists, None otherwise
        """
        data = self.load()
        return data["baselines"].get(skill_name)

    def update_baseline(
        self,
        skill_name: str,
        *,
        score: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store or update baseline for a skill.

        Args:
            skill_name: Name of the skill
            score: Baseline score value
            metadata: Additional metadata to store
        """
        data = self.load()
        data["baselines"][skill_name] = {
            "score": score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }


class SkillEvaluator:
    """Evaluates skill quality via LLM-as-judge pattern.

    Args:
        genai_client: Client with a judge() method for LLM evaluation
        benchmark_store: BenchmarkStore instance for baseline tracking
    """

    def __init__(self, genai_client: Any, benchmark_store: BenchmarkStore) -> None:
        self._genai = genai_client
        self._store = benchmark_store

    def evaluate_skill(
        self,
        skill_name: str,
        skill_content: str,
        prompt: str,
        *,
        category: str = "skill_eval",
    ) -> Dict[str, Any]:
        """Evaluate a skill's quality using LLM-as-judge.

        Args:
            skill_name: Name of the skill being evaluated
            skill_content: The skill content text to evaluate
            prompt: The evaluation prompt/question
            category: Threshold category for scoring

        Returns:
            Enriched dict with score, skill_name, timestamp, and judge result fields
        """
        if not _SKILL_NAME_RE.fullmatch(skill_name):
            raise ValueError(f"Invalid skill_name: {skill_name!r}. Expected kebab-case identifier.")

        result = self._genai.judge(
            question=prompt,
            context=skill_content,
            criteria=f"Evaluate skill '{skill_name}' quality and effectiveness",
            category=category,
        )

        result["skill_name"] = skill_name
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        return result

    def evaluate_skill_batch(
        self,
        skill_name: str,
        skill_content: str,
        prompts: List[str],
        *,
        category: str = "skill_eval",
    ) -> List[Dict[str, Any]]:
        """Evaluate a skill against multiple prompts.

        Args:
            skill_name: Name of the skill being evaluated
            skill_content: The skill content text to evaluate
            prompts: List of evaluation prompts
            category: Threshold category for scoring

        Returns:
            List of enriched result dicts, one per prompt
        """
        results = []
        for prompt in prompts:
            result = self.evaluate_skill(
                skill_name=skill_name,
                skill_content=skill_content,
                prompt=prompt,
                category=category,
            )
            results.append(result)
        return results

    def compare_variants(
        self,
        skill_name: str,
        variant_a: str,
        variant_b: str,
        prompts: List[str],
        *,
        category: str = "skill_eval",
    ) -> Dict[str, Any]:
        """A/B test two skill variants with paired comparison.

        HARD GATE: Requires at least 10 prompts for statistical validity.

        Args:
            skill_name: Name of the skill being compared
            variant_a: Content of variant A
            variant_b: Content of variant B
            prompts: List of evaluation prompts (minimum 10)
            category: Threshold category for scoring

        Returns:
            Dict with winner, mean_a, mean_b, scores_a, scores_b, margin, sample_count

        Raises:
            ValueError: If fewer than 10 prompts provided
        """
        if len(prompts) < 10:
            raise ValueError(
                f"compare_variants requires at least 10 prompts for statistical validity, "
                f"got {len(prompts)}"
            )

        scores_a: List[float] = []
        scores_b: List[float] = []

        for prompt in prompts:
            # Evaluate with variant A
            result_a = self._genai.judge(
                question=prompt,
                context=variant_a,
                criteria=f"Evaluate skill '{skill_name}' quality and effectiveness",
                category=category,
            )
            scores_a.append(result_a.get("score", 0))

            # Evaluate with variant B
            result_b = self._genai.judge(
                question=prompt,
                context=variant_b,
                criteria=f"Evaluate skill '{skill_name}' quality and effectiveness",
                category=category,
            )
            scores_b.append(result_b.get("score", 0))

        mean_a = sum(scores_a) / len(scores_a)
        mean_b = sum(scores_b) / len(scores_b)
        margin = abs(mean_a - mean_b)

        if mean_a > mean_b:
            winner = "A"
        elif mean_b > mean_a:
            winner = "B"
        else:
            winner = "tie"

        return {
            "winner": winner,
            "mean_a": mean_a,
            "mean_b": mean_b,
            "scores_a": scores_a,
            "scores_b": scores_b,
            "margin": margin,
            "sample_count": len(prompts),
        }

    def check_regression(
        self,
        skill_name: str,
        skill_content: str,
        prompts: List[str],
        *,
        threshold: float = 0.10,
        category: str = "skill_eval",
    ) -> Dict[str, Any]:
        """Check if a skill has regressed from its baseline.

        Args:
            skill_name: Name of the skill to check
            skill_content: Current skill content to evaluate
            prompts: Evaluation prompts to use
            threshold: Maximum allowed drop as fraction (default 0.10 = 10%)
            category: Threshold category for scoring

        Returns:
            Dict with regressed (bool), and supporting data
        """
        baseline = self._store.get_baseline(skill_name)

        if baseline is None:
            return {
                "regressed": False,
                "reason": "no_baseline",
                "skill_name": skill_name,
            }

        if not prompts:
            return {
                "regressed": False,
                "reason": "no_prompts",
                "skill_name": skill_name,
            }

        # Evaluate current performance
        results = self.evaluate_skill_batch(
            skill_name=skill_name,
            skill_content=skill_content,
            prompts=prompts,
            category=category,
        )

        current_scores = [r.get("score", 0) for r in results]
        current_mean = sum(current_scores) / len(current_scores) if current_scores else 0

        baseline_score = baseline["score"]
        drop_pct = (baseline_score - current_mean) / baseline_score if baseline_score != 0 else 0

        regressed = drop_pct > threshold

        return {
            "regressed": regressed,
            "baseline_score": baseline_score,
            "current_mean": current_mean,
            "drop_pct": drop_pct,
            "skill_name": skill_name,
        }

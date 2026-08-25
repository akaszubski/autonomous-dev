"""Shared GenAI test support: client, cost tracking, soft-failure thresholds.

Relocated from tests/genai/conftest.py (Issue #1666) so cross-directory
imports can be package-qualified (`tests.genai._genai_support`) instead of a
bare `from conftest import X`, which resolves to the wrong module when
tests/unit and tests/integration are collected together.
"""

import hashlib
import json
import os
import re
import statistics
import time
from pathlib import Path
from typing import Optional

import pytest

# Cache directory for GenAI responses
CACHE_DIR = Path(__file__).parent / ".genai_cache"

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# OpenRouter API base
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Thresholds config
THRESHOLDS_FILE = Path(__file__).parent / "thresholds.json"


def _load_thresholds() -> dict:
    """Load threshold config from thresholds.json."""
    if THRESHOLDS_FILE.exists():
        return json.loads(THRESHOLDS_FILE.read_text())
    return {
        "default": {"hard_fail": 4, "soft_fail": 6, "pass": 7},
        "categories": {},
        "accumulation_threshold": 0.33,
        "strict_mode": False,
    }


def _extract_json_from_response(text):
    """Extract JSON from LLM response (handles markdown fences)."""
    fence_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", text)
    if fence_match:
        return json.loads(fence_match.group(1).strip())
    for sc, ec in [("[", "]"), ("{", "}")]:
        s = text.find(sc)
        if s != -1:
            e = text.rfind(ec)
            if e > s:
                return json.loads(text[s : e + 1])
    return json.loads(text.strip())


class SoftFailureTracker:
    """Tracks soft failures across a GenAI test suite run.

    Classifies scores into bands: hard_fail, soft_fail, pass.
    Triggers suite-level hard fail if soft_fail ratio exceeds accumulation threshold.
    """

    def __init__(self, thresholds: Optional[dict] = None, strict: bool = False):
        self._thresholds = thresholds or _load_thresholds()
        self._strict = strict
        self._results: list[dict] = []

    def _get_category_thresholds(self, category: str) -> dict:
        """Get thresholds for a category, falling back to default."""
        categories = self._thresholds.get("categories", {})
        if category in categories:
            return categories[category]
        return self._thresholds.get("default", {"hard_fail": 4, "soft_fail": 6, "pass": 7})

    def classify(self, score: float, category: str = "default") -> str:
        """Classify a score into a band: 'hard_fail', 'soft_fail', or 'pass'.

        Args:
            score: Numeric score (0-10)
            category: Test category for threshold lookup

        Returns:
            Band string: 'hard_fail', 'soft_fail', or 'pass'
        """
        t = self._get_category_thresholds(category)
        if self._strict:
            # In strict mode, soft_fail becomes hard_fail
            if score < t["pass"]:
                return "hard_fail"
            return "pass"
        if score < t["hard_fail"]:
            return "hard_fail"
        if score < t["pass"]:
            return "soft_fail"
        return "pass"

    def record(self, test_name: str, score: float, category: str = "default", reasoning: str = "") -> dict:
        """Record a test result and return enriched result dict.

        Returns:
            dict with 'pass', 'score', 'band', 'reasoning', 'test_name', 'category'
        """
        band = self.classify(score, category)
        result = {
            "test_name": test_name,
            "score": score,
            "band": band,
            "category": category,
            "reasoning": reasoning,
            "pass": band == "pass",
        }
        self._results.append(result)
        return result

    @property
    def results(self) -> list[dict]:
        """All recorded results."""
        return list(self._results)

    @property
    def soft_failure_count(self) -> int:
        """Number of soft failures recorded."""
        return sum(1 for r in self._results if r["band"] == "soft_fail")

    @property
    def hard_failure_count(self) -> int:
        """Number of hard failures recorded."""
        return sum(1 for r in self._results if r["band"] == "hard_fail")

    @property
    def pass_count(self) -> int:
        """Number of passes recorded."""
        return sum(1 for r in self._results if r["band"] == "pass")

    @property
    def soft_failure_ratio(self) -> float:
        """Ratio of soft failures to total results."""
        if not self._results:
            return 0.0
        return self.soft_failure_count / len(self._results)

    @property
    def accumulation_threshold(self) -> float:
        """The configured accumulation threshold."""
        return self._thresholds.get("accumulation_threshold", 0.33)

    @property
    def suite_passed(self) -> bool:
        """Whether the suite passes the accumulation gate.

        Fails if:
        - Any hard failures exist
        - Soft failure ratio exceeds accumulation_threshold
        """
        if self.hard_failure_count > 0:
            return False
        if self.soft_failure_ratio > self.accumulation_threshold:
            return False
        return True

    def summary(self) -> str:
        """Human-readable summary of results."""
        total = len(self._results)
        if total == 0:
            return "No GenAI results recorded."
        lines = [
            f"GenAI Soft-Failure Report: {total} tests",
            f"  Pass: {self.pass_count}, Soft Fail: {self.soft_failure_count}, Hard Fail: {self.hard_failure_count}",
            f"  Soft failure ratio: {self.soft_failure_ratio:.1%} (threshold: {self.accumulation_threshold:.0%})",
            f"  Suite: {'PASSED' if self.suite_passed else 'FAILED'}",
        ]
        if self.soft_failure_count > 0:
            lines.append("  Soft failures:")
            for r in self._results:
                if r["band"] == "soft_fail":
                    lines.append(f"    - {r['test_name']}: {r['score']}/10 ({r['category']}) - {r['reasoning'][:80]}")
        if self.hard_failure_count > 0:
            lines.append("  Hard failures:")
            for r in self._results:
                if r["band"] == "hard_fail":
                    lines.append(f"    - {r['test_name']}: {r['score']}/10 ({r['category']}) - {r['reasoning'][:80]}")
        return "\n".join(lines)


class GenAIClient:
    """OpenRouter-backed LLM client for testing.

    Caches responses by prompt hash to avoid redundant API calls.
    Tracks cumulative cost per session.
    """

    MODELS = {
        "fast": "google/gemini-2.5-flash",
        "smart": "anthropic/claude-haiku-4.5",
    }

    def __init__(self, model: str = "google/gemini-2.5-flash"):
        self.model = model
        self.total_cost = 0.0
        self.call_count = 0
        self.cache_hits = 0
        CACHE_DIR.mkdir(exist_ok=True)

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise pytest.skip("OPENROUTER_API_KEY not set")

        try:
            import openai

            self._client = openai.OpenAI(
                base_url=OPENROUTER_BASE,
                api_key=api_key,
            )
        except ImportError:
            raise pytest.skip("openai package not installed (needed for OpenRouter)")

    def _cache_key(self, prompt: str, system: str = "", temperature: float = 0) -> str:
        content = f"{self.model}:{system}:{prompt}:t={temperature}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_cached(self, key: str) -> Optional[str]:
        cache_file = CACHE_DIR / f"{key}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text())
            if time.time() - data.get("timestamp", 0) < 86400:
                self.cache_hits += 1
                return data["response"]
        return None

    def _set_cached(self, key: str, response: str):
        cache_file = CACHE_DIR / f"{key}.json"
        cache_file.write_text(
            json.dumps({"response": response, "timestamp": time.time(), "model": self.model})
        )

    def ask(self, prompt: str, system: str = "", max_tokens: int = 1024, *, temperature: float = 0) -> str:
        """Send prompt to LLM via OpenRouter with caching.

        Args:
            prompt: User prompt to send
            system: Optional system prompt
            max_tokens: Maximum response tokens
            temperature: Sampling temperature (default 0 for deterministic judging)
        """
        cache_key = self._cache_key(prompt, system, temperature)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        else:
            messages.append(
                {"role": "system", "content": "You are a testing assistant. Be concise. Respond with JSON when asked."}
            )
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
            temperature=temperature,
        )

        text = response.choices[0].message.content
        self.call_count += 1

        usage = response.usage
        if usage:
            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0
            self.total_cost += (input_tokens / 1_000_000) * 0.30 + (output_tokens / 1_000_000) * 2.50

        self._set_cached(cache_key, text)
        return text

    def judge(self, question: str, context: str, criteria: str, *, category: str = "default") -> dict:
        """Ask LLM to judge content against criteria.

        Args:
            question: What to evaluate
            context: Content to evaluate
            criteria: Evaluation criteria
            category: Threshold category for soft-failure classification

        Returns:
            dict with 'pass' (bool), 'score' (0-10), 'reasoning' (str), 'band' (str)
        """
        prompt = f"""Evaluate the following against the criteria. Respond with ONLY valid JSON.

**Question**: {question}

**Content to evaluate**:
```
{context}
```

**Criteria**: {criteria}

Respond with JSON: {{"pass": true/false, "score": 0-10, "reasoning": "brief explanation"}}"""

        response = self.ask(prompt, max_tokens=512)

        try:
            result = _extract_json_from_response(response)
        except (json.JSONDecodeError, IndexError, ValueError):
            result = {"pass": False, "score": 0, "reasoning": f"Failed to parse response: {response[:200]}"}

        # Enrich with band classification
        thresholds = _load_thresholds()
        cats = thresholds.get("categories", {})
        t = cats.get(category, thresholds.get("default", {"hard_fail": 4, "soft_fail": 6, "pass": 7}))
        score = result.get("score", 0)
        if score < t["hard_fail"]:
            result["band"] = "hard_fail"
        elif score < t["pass"]:
            result["band"] = "soft_fail"
        else:
            result["band"] = "pass"

        return result

    def judge_analytic(
        self,
        question: str,
        context: str,
        criteria: list[dict],
        *,
        category: str = "default",
    ) -> dict:
        """Evaluate content using an analytic rubric with per-criterion binary scoring.

        Each criterion is evaluated independently with a MET/UNMET judgment,
        producing a decomposed score that is more reliable than holistic scoring.

        Args:
            question: What to evaluate
            context: Content to evaluate
            criteria: List of dicts, each with 'name', 'description', 'max_points'
            category: Threshold category for band classification

        Returns:
            dict with 'criteria_results', 'total_score', 'max_score', 'pass',
            'band', 'reasoning'
        """
        criteria_results = []
        total_score = 0
        max_score = 0
        reasoning_parts = []

        for criterion in criteria:
            name = criterion["name"]
            description = criterion["description"]
            max_points = criterion.get("max_points", 1)
            max_score += max_points

            prompt = f"""Evaluate the following content against ONE specific criterion.
Respond with ONLY valid JSON.

**Question**: {question}

**Content to evaluate**:
```
{context}
```

**Criterion**: {name} - {description}

Is this criterion MET or UNMET? Respond with JSON:
{{"met": true/false, "reasoning": "brief explanation"}}"""

            response = self.ask(prompt, max_tokens=256)

            try:
                result = _extract_json_from_response(response)
                met = bool(result.get("met", False))
                reason = result.get("reasoning", "No reasoning provided")
            except (json.JSONDecodeError, IndexError, ValueError):
                met = False
                reason = f"Failed to parse response: {response[:100]}"

            points = max_points if met else 0
            total_score += points
            criteria_results.append({
                "name": name,
                "met": met,
                "points": points,
                "max_points": max_points,
                "reasoning": reason,
            })
            reasoning_parts.append(f"{name}: {'MET' if met else 'UNMET'} - {reason}")

        # Convert to 0-10 scale for band classification
        normalized_score = (total_score / max_score * 10) if max_score > 0 else 0

        # Classify band
        thresholds = _load_thresholds()
        cats = thresholds.get("categories", {})
        t = cats.get(category, thresholds.get("default", {"hard_fail": 4, "soft_fail": 6, "pass": 7}))
        if normalized_score < t["hard_fail"]:
            band = "hard_fail"
        elif normalized_score < t["pass"]:
            band = "soft_fail"
        else:
            band = "pass"

        return {
            "criteria_results": criteria_results,
            "total_score": total_score,
            "max_score": max_score,
            "pass": band == "pass",
            "band": band,
            "reasoning": "; ".join(reasoning_parts),
        }

    def judge_consistent(
        self,
        question: str,
        context: str,
        criteria: str,
        *,
        category: str = "default",
        rounds: int = 3,
    ) -> dict:
        """Multi-round consistency check for high-stakes judgments.

        Calls the LLM multiple times with cache-busting and checks for
        agreement across rounds. Uses median score as the final result.

        Args:
            question: What to evaluate
            context: Content to evaluate
            criteria: Evaluation criteria
            category: Threshold category for band classification
            rounds: Number of evaluation rounds (default 3)

        Returns:
            dict with 'rounds', 'agreement', 'scores', 'final_score',
            'pass', 'band', 'reasoning'
        """
        round_results = []
        scores = []

        for i in range(rounds):
            # Cache-bust by appending round number to prompt
            prompt = f"""Evaluate the following against the criteria. Respond with ONLY valid JSON.

**Question**: {question}

**Content to evaluate**:
```
{context}
```

**Criteria**: {criteria}

[Evaluation round {i + 1} of {rounds}]

Respond with JSON: {{"pass": true/false, "score": 0-10, "reasoning": "brief explanation"}}"""

            response = self.ask(prompt, max_tokens=512)

            try:
                result = _extract_json_from_response(response)
            except (json.JSONDecodeError, IndexError, ValueError):
                result = {"pass": False, "score": 0, "reasoning": f"Failed to parse response: {response[:200]}"}

            round_results.append(result)
            scores.append(result.get("score", 0))

        # Calculate median score
        final_score = statistics.median(scores)

        # Check agreement: all rounds agree on pass/fail
        pass_votes = [r.get("pass", False) for r in round_results]
        agreement = len(set(pass_votes)) == 1

        # Classify band using median score
        thresholds = _load_thresholds()
        cats = thresholds.get("categories", {})
        t = cats.get(category, thresholds.get("default", {"hard_fail": 4, "soft_fail": 6, "pass": 7}))
        if final_score < t["hard_fail"]:
            band = "hard_fail"
        elif final_score < t["pass"]:
            band = "soft_fail"
        else:
            band = "pass"

        # Combine reasoning from all rounds
        reasoning_parts = [
            f"Round {i+1}: score={r.get('score', 0)}, {r.get('reasoning', 'N/A')}"
            for i, r in enumerate(round_results)
        ]

        return {
            "rounds": round_results,
            "agreement": agreement,
            "scores": scores,
            "final_score": final_score,
            "pass": band == "pass",
            "band": band,
            "reasoning": "; ".join(reasoning_parts),
        }

    def generate_edge_cases(self, description: str, count: int = 5) -> list:
        """Generate edge case inputs for testing."""
        prompt = f"""Generate {count} edge case test inputs for: {description}

Focus on inputs that could cause:
- Silent failures (wrong but plausible output)
- Boundary conditions
- Type confusion
- Unexpected state

Respond with ONLY a JSON array of objects, each with "input" and "why" fields."""

        response = self.ask(prompt, max_tokens=2048)

        try:
            return _extract_json_from_response(response)
        except (json.JSONDecodeError, IndexError, ValueError):
            return []

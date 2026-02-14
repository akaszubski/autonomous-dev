"""GenAI UAT test fixtures and configuration.

Provides:
- OpenRouter-backed LLM client with response caching
- Cost tracking per test run
- @pytest.mark.genai marker registration

Setup:
  1. pip install openai  (for OpenRouter API)
  2. export OPENROUTER_API_KEY=your_key  (from https://openrouter.ai)
  3. pytest tests/genai/ --genai
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import pytest

# Cache directory for GenAI responses
CACHE_DIR = Path(__file__).parent / ".genai_cache"

# Project root (assumes tests/genai/ is two levels deep from root)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# OpenRouter API base
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def pytest_collection_modifyitems(config, items):
    """Skip genai tests unless --genai flag or GENAI_TESTS=true."""
    run_genai = config.getoption("--genai", default=False) or os.environ.get("GENAI_TESTS", "").lower() == "true"
    if not run_genai:
        skip_genai = pytest.mark.skip(reason="GenAI tests require --genai flag or GENAI_TESTS=true")
        for item in items:
            if "genai" in item.keywords:
                item.add_marker(skip_genai)


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
            raise pytest.skip("OPENROUTER_API_KEY not set — see tests/genai/README.md for setup")

        try:
            import openai

            self._client = openai.OpenAI(
                base_url=OPENROUTER_BASE,
                api_key=api_key,
            )
        except ImportError:
            raise pytest.skip("openai package not installed — run: pip install openai")

    def _cache_key(self, prompt: str, system: str = "") -> str:
        content = f"{self.model}:{system}:{prompt}"
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

    def ask(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        """Send prompt to LLM via OpenRouter with caching."""
        cache_key = self._cache_key(prompt, system)
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

    def judge(self, question: str, context: str, criteria: str) -> dict:
        """Ask LLM to judge content against criteria.

        Returns:
            dict with 'pass' (bool), 'score' (0-10), 'reasoning' (str)
        """
        prompt = f"""Evaluate the following against the criteria. Respond with ONLY valid JSON.

**Question**: {question}

**Content to evaluate**:
```
{context}
```

**Criteria**: {criteria}

Respond with JSON: {{"pass": true/false, "score": 0-10, "reasoning": "brief explanation"}}"""

        response = self.ask(prompt, max_tokens=256)

        try:
            return _extract_json_from_response(response)
        except (json.JSONDecodeError, IndexError, ValueError):
            return {"pass": False, "score": 0, "reasoning": f"Failed to parse response: {response[:200]}"}

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


@pytest.fixture(scope="session")
def genai():
    """Session-scoped GenAI client (Gemini Flash - fast/cheap)."""
    return GenAIClient(model="google/gemini-2.5-flash")


@pytest.fixture(scope="session")
def genai_smart():
    """Session-scoped GenAI client (Haiku 4.5 - complex judging)."""
    return GenAIClient(model="anthropic/claude-haiku-4.5")

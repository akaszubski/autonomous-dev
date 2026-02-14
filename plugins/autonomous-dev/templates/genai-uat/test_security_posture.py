"""GenAI UAT: Security posture validation.

Validates security patterns in source code.
Universal test — works in any repo.
"""

import re

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]


class TestSecurityPosture:
    def test_no_secrets_in_source(self, genai):
        """No API keys, tokens, or passwords in source files."""
        suspicious = []
        secret_patterns = [
            r'(?:api[_-]?key|token|password|secret)\s*=\s*["\'][^"\']{8,}',
            r'sk-[a-zA-Z0-9]{20,}',
            r'ghp_[a-zA-Z0-9]{20,}',
            r'sk-ant-[a-zA-Z0-9]{20,}',
        ]

        for f in PROJECT_ROOT.rglob("*.py"):
            if any(x in str(f) for x in ["archived", "__pycache__", ".genai_cache", "venv", "node_modules"]):
                continue
            content = f.read_text(errors="ignore")
            for pattern in secret_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    line_no = content[: match.start()].count("\n") + 1
                    suspicious.append(f"{f.relative_to(PROJECT_ROOT)}:{line_no}: {match.group()[:40]}...")

        result = genai.judge(
            question="Are there hardcoded secrets in the source code?",
            context=f"Suspicious matches ({len(suspicious)}):\n" + "\n".join(suspicious[:20])
            if suspicious
            else "No suspicious patterns found.",
            criteria="Source files should NEVER contain real API keys, tokens, or passwords. "
            "Test fixtures with obvious fake values (test_key_123) are OK. "
            "Score 10 = clean, 5 = only test fixtures, 0 = real secrets found.",
        )
        assert result["score"] >= 7, f"Secret exposure risk: {result['reasoning']}"

    def test_no_secrets_in_config(self, genai):
        """No secrets in JSON/YAML config files."""
        suspicious = []
        for ext in ["*.json", "*.yaml", "*.yml"]:
            for f in PROJECT_ROOT.rglob(ext):
                if any(x in str(f) for x in ["node_modules", ".genai_cache", "venv", "package-lock"]):
                    continue
                content = f.read_text(errors="ignore")
                for pattern in [r'sk-[a-zA-Z0-9]{20,}', r'ghp_[a-zA-Z0-9]{20,}']:
                    if re.search(pattern, content):
                        suspicious.append(f"{f.relative_to(PROJECT_ROOT)}")

        result = genai.judge(
            question="Are there hardcoded secrets in config files?",
            context=f"Config files with potential secrets: {suspicious}" if suspicious else "No secrets found in config files.",
            criteria="Config files committed to git should never contain real secrets. "
            "Score 10 = clean, 0 = real secrets found.",
        )
        assert result["score"] >= 7, f"Config secrets: {result['reasoning']}"

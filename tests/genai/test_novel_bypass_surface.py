"""GenAI UAT: Novel bypass surface analysis (advisory).

Feeds hook architecture to LLM to identify potential new bypass vectors.
Advisory only with soft_fail threshold (pass=5).
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


def _read_if_exists(path, max_chars: int = 3000) -> str:
    """Read file content if it exists, truncated."""
    if path.exists():
        return path.read_text()[:max_chars]
    return ""


class TestNovelBypassSurface:
    def test_identify_potential_bypass_vectors(self, genai):
        """LLM identifies potential new bypass vectors in hook architecture (advisory)."""
        hooks_dir = PLUGIN_ROOT / "hooks"

        # Gather hook architecture overview
        hook_files = sorted(hooks_dir.glob("*.py")) if hooks_dir.exists() else []
        hook_summaries = []
        for f in hook_files[:8]:
            content = f.read_text()[:1500]
            hook_summaries.append(f"--- {f.name} ---\n{content}")

        # Also get settings for hook registration
        settings_dir = PLUGIN_ROOT / "settings"
        settings_content = ""
        if settings_dir.exists():
            for sf in sorted(settings_dir.glob("*.json"))[:2]:
                settings_content += f"\n--- {sf.name} ---\n{sf.read_text()[:1500]}"

        context = (
            f"Hook files:\n{''.join(hook_summaries)[:8000]}\n\n"
            f"Settings (hook registration):\n{settings_content[:3000]}"
        )

        result = genai.judge(
            question="Identify potential bypass vectors in this hook architecture. "
            "Could a user or agent circumvent enforcement?",
            context=context[:10000],
            criteria="Analyze for: (1) hooks that can be skipped via environment variables, "
            "(2) race conditions between hooks, (3) missing coverage for certain tool types, "
            "(4) overly permissive fallback/default behavior. "
            "Score 10 = no significant vectors found, 5 = some concerns, 1 = critical gaps. "
            "This is advisory - even a score of 5 is informational, not a hard failure.",
        )
        # Advisory threshold - soft fail at 5
        assert result["score"] >= 5, (
            f"Significant bypass vectors identified (advisory): {result['reasoning']}"
        )

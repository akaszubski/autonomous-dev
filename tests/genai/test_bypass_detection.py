"""GenAI UAT: Bypass detection in enforcement hooks.

Validates that enforcement hooks detect and block known bypass patterns.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


def _read_if_exists(path, max_chars: int = 4000) -> str:
    """Read file content if it exists, truncated."""
    if path.exists():
        return path.read_text()[:max_chars]
    return ""


class TestBypassDetection:
    def test_enforcement_hooks_block_known_patterns(self, genai):
        """Enforcement hooks should detect and block known bypass patterns."""
        hooks_dir = PLUGIN_ROOT / "hooks"
        config_dir = PLUGIN_ROOT / "config"

        unified = _read_if_exists(hooks_dir / "unified_pre_tool.py")
        enforce_orch = _read_if_exists(hooks_dir / "enforce_orchestrator.py")
        enforce_tdd = _read_if_exists(hooks_dir / "enforce_tdd.py")
        bypass_patterns = _read_if_exists(config_dir / "known_bypass_patterns.json")

        context = (
            f"--- unified_pre_tool.py ---\n{unified}\n\n"
            f"--- enforce_orchestrator.py ---\n{enforce_orch}\n\n"
            f"--- enforce_tdd.py ---\n{enforce_tdd}\n\n"
            f"--- known_bypass_patterns.json ---\n{bypass_patterns}"
        )

        result = genai.judge(
            question="Do these hooks detect and block the known bypass patterns listed in the config?",
            context=context[:10000],
            criteria="Enforcement hooks should: (1) read or reference known bypass patterns, "
            "(2) check tool calls or actions against those patterns, "
            "(3) block or warn when a bypass is detected. "
            "Score 10 = comprehensive blocking, 7 = good coverage, 4 = weak enforcement.",
        )
        assert result["score"] >= 7, f"Bypass detection weak: {result['reasoning']}"

    def test_bypass_patterns_config_valid(self):
        """known_bypass_patterns.json should be valid JSON with pattern entries."""
        import json

        config_file = PLUGIN_ROOT / "config" / "known_bypass_patterns.json"
        if not config_file.exists():
            pytest.skip("known_bypass_patterns.json not found")

        data = json.loads(config_file.read_text())
        assert isinstance(data, (dict, list)), "Config must be a dict or list"
        # Should have some content
        content_str = json.dumps(data)
        assert len(content_str) > 10, "Config appears empty"

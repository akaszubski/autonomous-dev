"""GenAI UAT: Hard gate enforcement validation.

Validates HARD GATEs have explicit FORBIDDEN lists and resolution options.
Stricter threshold (pass=8) due to criticality.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


class TestHardGateEnforcement:
    def test_implement_hard_gates(self, genai):
        """implement.md must have HARD GATEs with FORBIDDEN lists and 3 resolution options."""
        implement_md = (PLUGIN_ROOT / "commands" / "implement.md").read_text()

        result = genai.judge(
            question="Do HARD GATEs have explicit FORBIDDEN lists? Are there 3 resolution options (fix, skip, adjust)?",
            context=f"implement.md:\n{implement_md[:8000]}",
            criteria="HARD GATE enforcement requires: (1) explicit FORBIDDEN behavior lists, "
            "(2) three resolution options: fix it, skip it with @pytest.mark.skip, or adjust expectations, "
            "(3) clear language that blocks progression. "
            "Score 10 = all present and clear, 8 = mostly there, 5 = vague enforcement.",
        )
        assert result["score"] >= 8, f"Hard gate enforcement weak: {result['reasoning']}"

    def test_implementer_hard_gates(self, genai):
        """implementer.md must mirror the HARD GATE patterns."""
        implementer_md = (PLUGIN_ROOT / "agents" / "implementer.md").read_text()

        result = genai.judge(
            question="Does the implementer agent have HARD GATE enforcement with FORBIDDEN lists and resolution options?",
            context=f"implementer.md:\n{implementer_md[:6000]}",
            criteria="The implementer agent should enforce: no stubs, no NotImplementedError, "
            "no placeholder code. Must have FORBIDDEN list and 3 resolution options "
            "(fix, skip, adjust). Score 10 = comprehensive, 8 = solid, 5 = weak.",
        )
        assert result["score"] >= 8, f"Implementer hard gate weak: {result['reasoning']}"

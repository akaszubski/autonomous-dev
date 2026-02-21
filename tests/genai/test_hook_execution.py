"""GenAI UAT: Hook execution and error handling quality.

Validates all active hooks compile correctly and have quality error handling.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

HOOKS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"


def _get_active_hooks():
    """Get all active .py hook files."""
    if not HOOKS_DIR.exists():
        return []
    return sorted(f for f in HOOKS_DIR.glob("*.py") if f.stem != "__init__")


class TestHookExecution:
    def test_all_hooks_compile(self):
        """Every active hook must be valid Python (compile without errors)."""
        hooks = _get_active_hooks()
        assert len(hooks) > 0, "No hooks found"

        errors = []
        for hook in hooks:
            try:
                compile(hook.read_text(), str(hook), "exec")
            except SyntaxError as e:
                errors.append(f"{hook.name}: {e}")

        assert not errors, f"Hooks with syntax errors:\n" + "\n".join(errors)

    def test_hook_error_handling_quality(self, genai):
        """GenAI judge rates error handling quality of hooks."""
        hooks = _get_active_hooks()
        assert len(hooks) > 0, "No hooks found"

        # Sample up to 5 hooks for judging
        samples = []
        for hook in hooks[:5]:
            content = hook.read_text()[:2000]
            samples.append(f"--- {hook.name} ---\n{content}")

        result = genai.judge(
            question="Rate the error handling quality of these hooks (1-10)",
            context="\n\n".join(samples),
            criteria="Good error handling means: try/except around risky operations, "
            "meaningful error messages, no bare except clauses, graceful degradation, "
            "proper exit codes. Score 10 = excellent, 7 = good, 4 = poor.",
        )
        assert result["score"] >= 7, f"Hook error handling quality too low: {result['reasoning']}"

"""GenAI UAT: Error handling quality across libs and hooks.

Samples critical Python files and judges error handling practices.
"""

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


def _sample_python_files(max_files: int = 10):
    """Sample critical .py files from lib/ and hooks/."""
    files = []
    for subdir in ["lib", "hooks"]:
        d = PLUGIN_ROOT / subdir
        if d.exists():
            for f in sorted(d.glob("*.py")):
                if f.stem != "__init__" and f.stat().st_size > 200:
                    files.append(f)
    # Take up to max_files, prioritizing larger files
    files.sort(key=lambda f: f.stat().st_size, reverse=True)
    return files[:max_files]


class TestErrorHandling:
    def test_error_handling_quality(self, genai):
        """Critical Python files should have quality error handling."""
        files = _sample_python_files(10)
        assert len(files) > 0, "No Python files found to sample"

        samples = []
        for f in files:
            content = f.read_text()[:1500]
            rel = f.relative_to(PLUGIN_ROOT)
            samples.append(f"--- {rel} ---\n{content}")

        result = genai.judge(
            question="Rate the error handling quality of these Python files (1-10)",
            context="\n\n".join(samples)[:8000],
            criteria="Good error handling: try/except around I/O and external calls, "
            "meaningful error messages with context, no bare except, "
            "no silent failures (empty except blocks), proper logging or re-raising. "
            "Score 10 = excellent, 6 = acceptable, 3 = poor.",
        )
        assert result["score"] >= 6, f"Error handling quality too low: {result['reasoning']}"

    def test_no_silent_failures(self, genai):
        """Files should not silently swallow exceptions."""
        files = _sample_python_files(10)

        # Collect any files with bare except or pass-only handlers
        suspect_snippets = []
        for f in files:
            content = f.read_text()
            if "except:" in content or "except Exception:\n            pass" in content:
                rel = f.relative_to(PLUGIN_ROOT)
                suspect_snippets.append(f"--- {rel} ---\n{content[:1000]}")

        if not suspect_snippets:
            # No suspects found, pass
            return

        result = genai.judge(
            question="Do these files silently swallow exceptions in a harmful way?",
            context="\n\n".join(suspect_snippets)[:6000],
            criteria="Bare except or except-pass is acceptable ONLY for cleanup/fallback code "
            "where failure is non-critical. Score 10 = all justified, 6 = mostly justified, "
            "3 = dangerous silent failures.",
        )
        assert result["score"] >= 6, f"Silent failure risk: {result['reasoning']}"

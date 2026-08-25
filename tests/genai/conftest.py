"""GenAI UAT test fixtures and configuration.

Provides:
- OpenRouter-backed LLM client with response caching
- Cost tracking per test run
- Soft-failure thresholds with accumulation gate
- @pytest.mark.genai marker registration
"""

import os

import pytest

from tests.genai._genai_support import PROJECT_ROOT, GenAIClient, SoftFailureTracker  # noqa: F401 (PROJECT_ROOT re-exported for tests/genai/**/*.py `from .conftest import PROJECT_ROOT` consumers)


def pytest_addoption(parser):
    """Add --genai and --strict-genai flags."""
    parser.addoption("--genai", action="store_true", default=False, help="Run GenAI tests")
    parser.addoption("--strict-genai", action="store_true", default=False, help="Treat soft failures as hard failures")


def pytest_collection_modifyitems(config, items):
    """Skip genai tests unless --genai flag or GENAI_TESTS=true."""
    run_genai = config.getoption("--genai", default=False) or os.environ.get("GENAI_TESTS", "").lower() == "true"
    if not run_genai:
        skip_genai = pytest.mark.skip(reason="GenAI tests require --genai flag or GENAI_TESTS=true")
        for item in items:
            if "genai" in item.keywords:
                item.add_marker(skip_genai)


# --- Fixtures ---


@pytest.fixture(scope="session")
def genai():
    """Session-scoped GenAI client (Gemini Flash - fast/cheap)."""
    return GenAIClient(model="google/gemini-2.5-flash")


@pytest.fixture(scope="session")
def genai_smart():
    """Session-scoped GenAI client (Haiku 4.5 - complex judging)."""
    return GenAIClient(model="anthropic/claude-haiku-4.5")


@pytest.fixture(scope="session")
def soft_failure_tracker(request):
    """Session-scoped soft-failure tracker."""
    strict = request.config.getoption("--strict-genai", default=False)
    return SoftFailureTracker(strict=strict)


def pytest_terminal_summary(terminalreporter, config):
    """Print soft-failure accumulation report at end of test run."""
    # Only report if genai tests were run
    run_genai = config.getoption("--genai", default=False) or os.environ.get("GENAI_TESTS", "").lower() == "true"
    if not run_genai:
        return

    # Access tracker from fixture if available
    tracker = getattr(config, "_soft_failure_tracker", None)
    if tracker and len(tracker.results) > 0:
        terminalreporter.section("GenAI Soft-Failure Report")
        terminalreporter.line(tracker.summary())
        if not tracker.suite_passed:
            terminalreporter.line("")
            terminalreporter.line("SUITE FAILED: Accumulation gate exceeded")

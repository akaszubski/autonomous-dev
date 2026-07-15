"""Regression tests for Issue #1067 — STEP 5.5b updated to list 4 axes."""

from pathlib import Path
import pytest

IMPLEMENT_PATH = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "commands" / "implement.md"


@pytest.fixture(scope="module")
def content() -> str:
    return IMPLEMENT_PATH.read_text()


class TestStep55bAxes:
    def test_step_5_5b_lists_four_axes(self, content):
        # Find 5.5b section (heading is "#### 5.5b — Budget Plan-Critic Invocation")
        idx = content.index("#### 5.5b")
        window = content[idx:idx + 2000]
        assert ("4 axes" in window) or ("4 only" in window) or ("four axes" in window.lower())

    def test_step_5_5b_includes_operational_integration_test(self, content):
        idx = content.index("#### 5.5b")
        window = content[idx:idx + 2000]
        assert "Operational Integration Test" in window

    def test_step_5_5b_instruction_lists_all_four_axes(self, content):
        # The inline instruction string passed to plan-critic
        idx = content.index("#### 5.5b")
        window = content[idx:idx + 2000]
        # All four axes must appear in this 5.5b window
        for axis in ["Assumption Audit", "Existing Solution Search", "Minimalism Pressure", "Operational Integration Test"]:
            assert axis in window, f"{axis} missing from STEP 5.5b inline instruction"

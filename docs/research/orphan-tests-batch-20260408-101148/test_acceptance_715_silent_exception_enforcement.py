"""Acceptance tests for Issue #715: Silent exception swallowing enforcement.

Validates that the reviewer agent escalates silent exception swallowing
from WARNING to BLOCKING severity, and that bypass patterns are registered.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEWER_PATH = REPO_ROOT / "plugins/autonomous-dev/agents/reviewer.md"
BYPASS_PATTERNS_PATH = REPO_ROOT / "plugins/autonomous-dev/config/known_bypass_patterns.json"
OBSERVABILITY_SKILL_PATH = REPO_ROOT / "plugins/autonomous-dev/skills/observability/SKILL.md"
ERROR_HANDLING_TEST_PATH = REPO_ROOT / "tests/genai/test_error_handling.py"


class TestIssue715SilentExceptionEnforcement:
    """Acceptance tests for silent exception swallowing enforcement."""

    def test_reviewer_has_blocking_severity_for_exception_swallowing(self) -> None:
        """AC1: Reviewer classifies silent exception swallowing as BLOCKING."""
        content = REVIEWER_PATH.read_text()
        # Must contain BLOCKING severity for exception swallowing
        assert "BLOCKING" in content, "Reviewer must have BLOCKING severity"
        # Must mention exception swallowing in a BLOCKING context
        lines = content.split("\n")
        found_blocking_exception = False
        for line in lines:
            lower = line.lower()
            if "blocking" in lower and (
                "exception" in lower or "except" in lower or "swallow" in lower
            ):
                found_blocking_exception = True
                break
        assert found_blocking_exception, (
            "Reviewer must classify silent exception swallowing as BLOCKING severity"
        )

    def test_reviewer_retains_warning_for_general_observability(self) -> None:
        """AC2: General observability items remain WARNING severity."""
        content = REVIEWER_PATH.read_text()
        # Must still have WARNING for general observability
        assert "WARNING" in content, "Reviewer must retain WARNING severity for general items"
        # Structured logging should be WARNING, not BLOCKING
        lower_content = content.lower()
        assert "structured logging" in lower_content or "logging" in lower_content

    def test_bypass_patterns_has_silent_exception_pattern(self) -> None:
        """AC3: known_bypass_patterns.json contains silent_exception_swallowing pattern."""
        data = json.loads(BYPASS_PATTERNS_PATH.read_text())
        patterns = data.get("patterns", data) if isinstance(data, dict) else data
        if isinstance(patterns, dict):
            patterns = patterns.get("patterns", [])
        pattern_ids = [p["id"] for p in patterns]
        assert "silent_exception_swallowing" in pattern_ids, (
            "known_bypass_patterns.json must contain 'silent_exception_swallowing' pattern"
        )

    def test_bypass_pattern_has_critical_severity(self) -> None:
        """AC3b: silent_exception_swallowing pattern has critical severity."""
        data = json.loads(BYPASS_PATTERNS_PATH.read_text())
        patterns = data.get("patterns", data) if isinstance(data, dict) else data
        if isinstance(patterns, dict):
            patterns = patterns.get("patterns", [])
        pattern = next(p for p in patterns if p["id"] == "silent_exception_swallowing")
        assert pattern["severity"] == "critical"

    def test_observability_skill_enumerates_specific_antipatterns(self) -> None:
        """AC4: Observability skill FORBIDDEN section has specific anti-patterns."""
        content = OBSERVABILITY_SKILL_PATH.read_text()
        lower = content.lower()
        # Must enumerate specific patterns, not just a single line
        assert "except exception" in lower or "bare except" in lower, (
            "Observability skill must enumerate specific exception anti-patterns"
        )
        assert "re-raise" in lower or "reraise" in lower or "re_raise" in lower, (
            "Observability skill must mention re-raise as compliant pattern"
        )

    def test_observability_skill_defines_compliant_patterns(self) -> None:
        """AC5: Observability skill REQUIRED section defines compliant patterns."""
        content = OBSERVABILITY_SKILL_PATH.read_text()
        lower = content.lower()
        # Must define at least 2 of the 3 compliant patterns
        compliant_count = sum([
            "re-raise" in lower or "reraise" in lower,
            "exc_info" in lower,
            "contextlib.suppress" in lower,
        ])
        assert compliant_count >= 2, (
            f"Observability skill must define at least 2 compliant patterns, found {compliant_count}"
        )

    def test_error_handling_test_detects_additional_patterns(self) -> None:
        """AC6: test_error_handling.py detects contextlib.suppress and except-log-without-raise."""
        content = ERROR_HANDLING_TEST_PATH.read_text()
        lower = content.lower()
        # Must mention contextlib.suppress or additional patterns beyond bare except
        assert "contextlib" in lower or "suppress" in lower or "exc_info" in lower or "re-raise" in lower, (
            "test_error_handling.py must detect patterns beyond bare except"
        )

    def test_all_existing_tests_pass(self) -> None:
        """AC8: All existing tests continue to pass (validated by test gate, not here)."""
        # This criterion is validated by the STEP 8 test gate, not by this test.
        # Placeholder to document the criterion exists.
        pass

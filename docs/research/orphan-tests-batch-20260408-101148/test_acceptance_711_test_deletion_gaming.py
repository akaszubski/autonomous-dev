"""Acceptance tests for Issue #711: Test deletion gaming detection.

Validates that the pipeline detects when behavioral tests are deleted
and replaced with structural absence-checks.
"""

import importlib
import inspect
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEWER_PATH = REPO_ROOT / "plugins/autonomous-dev/agents/reviewer.md"
SECURITY_AUDITOR_PATH = REPO_ROOT / "plugins/autonomous-dev/agents/security-auditor.md"
IMPLEMENT_CMD_PATH = REPO_ROOT / "plugins/autonomous-dev/commands/implement.md"
COVERAGE_BASELINE_PATH = REPO_ROOT / "plugins/autonomous-dev/lib/coverage_baseline.py"
QUALITY_GATE_PATH = REPO_ROOT / "plugins/autonomous-dev/lib/step5_quality_gate.py"


class TestIssue711TestDeletionGaming:
    """Acceptance tests for test deletion gaming detection."""

    def test_coverage_baseline_has_test_count_regression_function(self) -> None:
        """AC1: coverage_baseline.py has check_test_count_regression()."""
        content = COVERAGE_BASELINE_PATH.read_text()
        assert "def check_test_count_regression" in content, (
            "coverage_baseline.py must define check_test_count_regression()"
        )

    def test_quality_gate_wires_test_count_regression(self) -> None:
        """AC2: step5_quality_gate.py integrates test count regression check."""
        content = QUALITY_GATE_PATH.read_text()
        assert "test_count_regression" in content or "check_test_count_regression" in content, (
            "step5_quality_gate.py must call check_test_count_regression()"
        )

    def test_reviewer_has_test_deletion_hard_gate(self) -> None:
        """AC5: Reviewer agent has HARD GATE for test deletion detection."""
        content = REVIEWER_PATH.read_text()
        lower = content.lower()
        assert "test deletion" in lower or "test file" in lower and "delet" in lower, (
            "Reviewer must have guidance on test deletion detection"
        )
        # Must mention issue-traced tests
        assert "issue" in lower and ("delet" in lower or "remov" in lower), (
            "Reviewer must mention issue-referenced test detection"
        )

    def test_reviewer_distinguishes_structural_from_behavioral(self) -> None:
        """AC6: Reviewer explicitly states structural absence-checks are not behavioral."""
        content = REVIEWER_PATH.read_text()
        lower = content.lower()
        has_structural = "structural" in lower or "absence" in lower
        has_behavioral = "behavioral" in lower or "behaviour" in lower
        assert has_structural and has_behavioral, (
            "Reviewer must distinguish structural absence-checks from behavioral tests"
        )

    def test_security_auditor_has_test_integrity_check(self) -> None:
        """AC7: Security auditor has guidance on test integrity manipulation."""
        content = SECURITY_AUDITOR_PATH.read_text()
        lower = content.lower()
        assert "test" in lower and ("integrit" in lower or "delet" in lower or "manipulat" in lower), (
            "Security auditor must have test integrity check guidance"
        )

    def test_implement_cmd_references_test_count_regression(self) -> None:
        """AC8: implement.md STEP 8 references test count regression check."""
        content = IMPLEMENT_CMD_PATH.read_text()
        lower = content.lower()
        assert "test count" in lower or "test_count_regression" in lower, (
            "implement.md must reference test count regression in STEP 8"
        )

    def test_no_baseline_passes(self, tmp_path: Path) -> None:
        """AC4: When no baseline exists, test count check passes."""
        import sys
        sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/lib"))
        from coverage_baseline import check_test_count_regression

        passed, msg = check_test_count_regression(100, baseline_path=tmp_path / "nonexistent.json")
        assert passed, f"No baseline should pass, got: {msg}"

    def test_regression_beyond_tolerance_blocks(self, tmp_path: Path) -> None:
        """AC1b: Test count drop beyond tolerance blocks pipeline."""
        import sys
        sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/lib"))
        from coverage_baseline import check_test_count_regression

        # Create baseline with 100 tests
        baseline_file = tmp_path / "coverage_baseline.json"
        baseline_file.write_text(json.dumps({
            "total_tests": 100,
            "coverage_pct": 85.0,
            "skipped": 2,
        }))

        # Simulate dropping to 70 tests (30% drop, exceeds 10% tolerance)
        passed, msg = check_test_count_regression(70, baseline_path=baseline_file)
        assert not passed, f"30% test count drop should block, got: {msg}"

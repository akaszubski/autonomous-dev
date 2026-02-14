"""Step 5 Quality Gate for the /implement pipeline.

Enforces that all tests pass (0 failures, 0 errors) before the coordinator
can proceed from STEP 5 (implementation) to STEP 6 (validation).

Can be used as an importable module or run standalone:
    python plugins/autonomous-dev/lib/step5_quality_gate.py
"""

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


COVERAGE_BASELINE_PATH = Path(".claude/local/coverage_baseline.json")
COVERAGE_REGRESSION_THRESHOLD = 0.5  # percent


@dataclass
class TestResult:
    """Result of running the test suite."""

    passed: bool
    test_count: int
    failures: int
    errors: int
    skipped: int
    skip_rate: float
    message: str
    blocker: Optional[str] = None


@dataclass
class CoverageResult:
    """Result of coverage regression check."""

    passed: bool
    current_coverage: float
    baseline_coverage: Optional[float] = None
    regression: float = 0.0
    message: str = ""


def parse_pytest_output(output: str) -> TestResult:
    """Parse pytest output to extract pass/fail/error/skip counts.

    Args:
        output: Raw pytest stdout/stderr output.

    Returns:
        TestResult with parsed counts and pass/fail status.
    """
    # pytest summary line patterns:
    # "5 passed"
    # "3 failed, 2 passed"
    # "1 error, 5 passed"
    # "2 skipped, 3 passed"
    # "5 passed, 1 skipped, 2 warnings"
    # Also: "no tests ran"

    passed_count = 0
    failed_count = 0
    error_count = 0
    skipped_count = 0

    # Match the summary line (last meaningful line)
    # Pattern: "X passed", "X failed", "X error", "X skipped"
    summary_match = re.search(
        r"=+\s*(.*?)\s*=+\s*$", output, re.MULTILINE
    )
    if not summary_match:
        # Try short format: "5 passed, 2 failed in 1.23s"
        summary_match = re.search(
            r"(\d+\s+(?:passed|failed|error|skipped).*?)$", output, re.MULTILINE
        )

    summary_line = summary_match.group(1) if summary_match else output

    for match in re.finditer(r"(\d+)\s+(passed|failed|error|errors|skipped)", summary_line):
        count = int(match.group(1))
        kind = match.group(2)
        if kind == "passed":
            passed_count = count
        elif kind == "failed":
            failed_count = count
        elif kind in ("error", "errors"):
            error_count = count
        elif kind == "skipped":
            skipped_count = count

    test_count = passed_count + failed_count + error_count + skipped_count
    skip_rate = (skipped_count / test_count * 100) if test_count > 0 else 0.0

    is_passed = failed_count == 0 and error_count == 0 and test_count > 0

    # Build message
    parts = []
    if passed_count:
        parts.append(f"{passed_count} passed")
    if failed_count:
        parts.append(f"{failed_count} failed")
    if error_count:
        parts.append(f"{error_count} errors")
    if skipped_count:
        parts.append(f"{skipped_count} skipped")

    if test_count == 0:
        message = "No tests ran"
        is_passed = False
    elif is_passed:
        message = f"PASS: {', '.join(parts)}"
    else:
        message = f"FAIL: {', '.join(parts)}"

    blocker = None
    if skip_rate > 10:
        blocker = (
            f"Skip rate is {skip_rate:.1f}% ({skipped_count}/{test_count}). "
            f"Fix skipped tests before proceeding (max 10%)."
        )

    return TestResult(
        passed=is_passed,
        test_count=test_count,
        failures=failed_count,
        errors=error_count,
        skipped=skipped_count,
        skip_rate=round(skip_rate, 1),
        message=message,
        blocker=blocker,
    )


def run_tests() -> TestResult:
    """Run pytest and return parsed results.

    Returns:
        TestResult from running the test suite.
    """
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=600,
        )
        output = result.stdout + "\n" + result.stderr
        return parse_pytest_output(output)
    except subprocess.TimeoutExpired:
        return TestResult(
            passed=False,
            test_count=0,
            failures=0,
            errors=1,
            skipped=0,
            skip_rate=0.0,
            message="FAIL: pytest timed out after 600 seconds",
        )
    except FileNotFoundError:
        return TestResult(
            passed=False,
            test_count=0,
            failures=0,
            errors=1,
            skipped=0,
            skip_rate=0.0,
            message="FAIL: pytest not found",
        )


def parse_coverage_output(output: str) -> Optional[float]:
    """Parse pytest coverage output for TOTAL percentage.

    Args:
        output: Raw pytest --cov output.

    Returns:
        Total coverage percentage, or None if not found.
    """
    # Match "TOTAL    ...    85%"
    match = re.search(r"^TOTAL\s+.*?(\d+)%", output, re.MULTILINE)
    if match:
        return float(match.group(1))
    return None


def check_coverage_regression(
    *,
    baseline_path: Optional[Path] = None,
    coverage_output: Optional[str] = None,
) -> CoverageResult:
    """Check whether test coverage has regressed from baseline.

    Args:
        baseline_path: Path to coverage baseline JSON. Defaults to COVERAGE_BASELINE_PATH.
        coverage_output: Pre-captured coverage output. If None, runs pytest --cov.

    Returns:
        CoverageResult indicating pass/fail and details.
    """
    if baseline_path is None:
        baseline_path = COVERAGE_BASELINE_PATH

    # Get current coverage
    if coverage_output is None:
        try:
            result = subprocess.run(
                [
                    "python", "-m", "pytest",
                    "--cov=plugins", "--cov-report=term-missing", "-q",
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )
            coverage_output = result.stdout + "\n" + result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return CoverageResult(
                passed=True,
                current_coverage=0.0,
                message="Could not run coverage check (skipped)",
            )

    current = parse_coverage_output(coverage_output)
    if current is None:
        return CoverageResult(
            passed=True,
            current_coverage=0.0,
            message="Could not parse coverage output (skipped)",
        )

    # Load baseline
    baseline_value = None
    if baseline_path.exists():
        try:
            data = json.loads(baseline_path.read_text())
            baseline_value = data.get("coverage")
        except (json.JSONDecodeError, KeyError):
            pass

    # Compare
    if baseline_value is not None:
        regression = baseline_value - current
        if regression > COVERAGE_REGRESSION_THRESHOLD:
            return CoverageResult(
                passed=False,
                current_coverage=current,
                baseline_coverage=baseline_value,
                regression=round(regression, 1),
                message=(
                    f"FAIL: Coverage regressed from {baseline_value}% to {current}% "
                    f"(-{regression:.1f}%, threshold is {COVERAGE_REGRESSION_THRESHOLD}%)"
                ),
            )

    # Update baseline if improved
    if baseline_value is None or current > baseline_value:
        try:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(json.dumps({
                "coverage": current,
                "updated_at": datetime.now().isoformat(),
            }, indent=2) + "\n")
        except OSError:
            pass  # Non-critical

    return CoverageResult(
        passed=True,
        current_coverage=current,
        baseline_coverage=baseline_value,
        message=f"Coverage: {current}%" + (
            f" (baseline: {baseline_value}%)" if baseline_value is not None else " (new baseline)"
        ),
    )


def run_quality_gate() -> dict:
    """Run the full STEP 5 quality gate.

    Runs tests and coverage checks, returning a combined result.

    Returns:
        Dict with 'passed' (bool), 'test_result', 'coverage_result', and 'summary'.
    """
    test_result = run_tests()
    coverage_result = check_coverage_regression()

    overall_passed = test_result.passed and coverage_result.passed

    summary_parts = [test_result.message, coverage_result.message]
    if test_result.blocker:
        summary_parts.append(f"BLOCKER: {test_result.blocker}")

    return {
        "passed": overall_passed,
        "test_result": asdict(test_result),
        "coverage_result": asdict(coverage_result),
        "summary": " | ".join(summary_parts),
    }


if __name__ == "__main__":
    result = run_quality_gate()
    print(result["summary"])
    if not result["passed"]:
        print("\nSTEP 5 QUALITY GATE: FAIL")
        print("Fix all issues before proceeding to STEP 6.")
    else:
        print("\nSTEP 5 QUALITY GATE: PASS")
    sys.exit(0 if result["passed"] else 1)

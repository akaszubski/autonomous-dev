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
from typing import Any, Dict, Optional

import coverage_baseline

try:
    from plugins.autonomous_dev.lib.test_routing import route_tests as _route_tests
except ImportError:
    try:
        from test_routing import route_tests as _route_tests
    except ImportError:
        _route_tests = None  # type: ignore[assignment]

try:
    from tier_registry import get_tier_distribution as _get_tier_distribution
except ImportError:
    _get_tier_distribution = None  # type: ignore[assignment]

try:
    from acceptance_criteria_tracker import (
        CriteriaCoverageResult as _CriteriaCoverageResult,
        compute_criteria_coverage as _compute_criteria_coverage,
        load_criteria_registry as _load_criteria_registry,
    )
except ImportError:
    _load_criteria_registry = None  # type: ignore[assignment]
    _compute_criteria_coverage = None  # type: ignore[assignment]
    _CriteriaCoverageResult = None  # type: ignore[assignment]


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
    """Parse pytest output to extract counts; this does not validate process exit.

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


def _assess_completed_pytest(output: str, returncode: Optional[int]) -> TestResult:
    """Require a completed zero exit as well as a green parsed summary."""
    parsed = parse_pytest_output(output)
    aborted = any(
        re.match(r"^!+\s*Interrupted:|^INTERNALERROR>|^=+.*\berrors? during collection\b.*=+$|^=*\s*no tests ran\b", line.strip())
        for line in output.splitlines()
    )
    if returncode is None or returncode in {2, 3, 4, 5} or aborted or parsed.test_count == 0:
        parsed.passed = False
        parsed.message = "UNKNOWN: pytest capture aborted, empty, or missing process exit"
        return parsed
    if returncode == 0:
        return parsed
    parsed.passed = False
    if parsed.failures == 0 and parsed.errors == 0:
        parsed.message = f"FAIL: pytest exit {returncode} conflicts with {parsed.message}"
    return parsed


def run_tests() -> TestResult:
    """Run pytest and return parsed results.

    Returns:
        TestResult from running the test suite.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--tb=short", "-q"],
            capture_output=True, text=True, timeout=600,
        )
        return _assess_completed_pytest(result.stdout + "\n" + result.stderr, result.returncode)
    except subprocess.TimeoutExpired:
        return TestResult(
            passed=False, test_count=0, failures=0, errors=1, skipped=0,
            skip_rate=0.0, message="UNKNOWN: pytest timed out after 600 seconds",
        )
    except FileNotFoundError:
        return TestResult(
            passed=False, test_count=0, failures=0, errors=1, skipped=0,
            skip_rate=0.0, message="UNKNOWN: pytest not found",
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
            if result.returncode != 0:
                return CoverageResult(
                    passed=False,
                    current_coverage=0.0,
                    message=f"UNKNOWN: coverage process exit {result.returncode}",
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            reason = "timed out" if isinstance(exc, subprocess.TimeoutExpired) else "not found"
            return CoverageResult(
                passed=False,
                current_coverage=0.0,
                message=f"UNKNOWN: coverage process {reason}",
            )

    current = parse_coverage_output(coverage_output)
    if current is None:
        return CoverageResult(
            passed=False,
            current_coverage=0.0,
            message="UNKNOWN: Could not parse coverage output",
        )

    # Load baseline
    baseline_value = None
    if baseline_path.exists():
        try:
            data = json.loads(baseline_path.read_text())
            baseline_value = data.get("total_coverage", data.get("coverage", 0))
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


def run_tests_routed(*, full_tests: bool = False) -> dict:
    """Run tests with smart routing or full suite.

    If full_tests is True or routing is unavailable, delegates to run_tests().
    Otherwise uses test_routing to determine which markers to run.

    Args:
        full_tests: Force full test suite (bypass smart routing).

    Returns:
        Dict with 'test_result' (TestResult as dict) and 'routing' metadata.
    """
    routing_meta = None

    if not full_tests and _route_tests is not None:
        try:
            routing_decision = _route_tests()
        except Exception:
            routing_decision = None

        if routing_decision and not routing_decision.get("full_suite") and not routing_decision.get("skip_all"):
            marker_expr = routing_decision.get("marker_expression", "")
            if marker_expr:
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pytest", "--tb=short", "-q", "-m", marker_expr],
                        capture_output=True, text=True, timeout=600,
                    )
                    test_result = _assess_completed_pytest(
                        result.stdout + "\n" + result.stderr, result.returncode
                    )
                    routing_meta = {
                        "routed": True,
                        "marker_expression": marker_expr,
                        "categories": routing_decision.get("categories", []),
                        "skipped_tiers": routing_decision.get("skipped_tiers", []),
                    }
                    return {
                        "test_result": test_result,
                        "routing": routing_meta,
                    }
                except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                    reason = (
                        "pytest timed out after 600 seconds"
                        if isinstance(exc, subprocess.TimeoutExpired)
                        else "pytest not found"
                    )
                    return {
                        "test_result": TestResult(
                            passed=False, test_count=0, failures=0, errors=1,
                            skipped=0, skip_rate=0.0, message=f"UNKNOWN: {reason}",
                        ),
                        "routing": {
                            "routed": True,
                            "marker_expression": marker_expr,
                            "reason": "capture failure",
                        },
                    }

        if routing_decision and routing_decision.get("skip_all"):
            routing_meta = {
                "routed": True,
                "marker_expression": "",
                "categories": routing_decision.get("categories", []),
                "skipped_tiers": routing_decision.get("skipped_tiers", []),
                "skip_all": True,
            }
            return {
                "test_result": TestResult(
                    passed=False,
                    test_count=0,
                    failures=0,
                    errors=0,
                    skipped=0,
                    skip_rate=0.0,
                    message="UNKNOWN: docs-only routing skipped tests; no test pass evidence",
                ),
                "routing": routing_meta,
            }

    # Full suite fallback
    test_result = run_tests()
    return {
        "test_result": test_result,
        "routing": {
            "routed": False,
            "full_suite": True,
            "reason": "full_tests flag" if full_tests else "fallback",
        },
    }


def run_quality_gate(*, full_tests: bool = False) -> dict:
    """Run the full STEP 5 quality gate.

    Runs tests (with optional smart routing) and coverage checks,
    returning a combined result.

    Args:
        full_tests: If True, bypass smart test routing and run all tests.

    Returns:
        Dict with 'passed' (bool), 'test_result', 'coverage_result',
        'summary', and optionally 'routing' metadata.
    """
    routed_result = run_tests_routed(full_tests=full_tests)
    test_result = routed_result["test_result"]
    routing_meta = routed_result.get("routing")

    # If test_result came back as a dataclass, use it directly;
    # if it's already a dict (shouldn't happen), wrap it
    if isinstance(test_result, dict):
        # Reconstruct TestResult from dict
        test_result = TestResult(**test_result)

    coverage_result = check_coverage_regression()

    # Check skip regression against baseline
    skip_passed, skip_message = coverage_baseline.check_skip_regression(
        test_result.skipped
    )

    # Check test count regression against baseline
    test_count_passed, test_count_message = coverage_baseline.check_test_count_regression(
        test_result.test_count
    )

    overall_passed = (
        test_result.passed and coverage_result.passed and skip_passed and test_count_passed
    )

    # Compute tier distribution by globbing test directories
    tier_distribution: Dict[str, int] = {}
    if _get_tier_distribution is not None:
        try:
            tests_dir = Path("tests")
            if tests_dir.exists():
                test_files = [
                    str(p) for p in tests_dir.rglob("test_*.py")
                ]
                test_files.extend(
                    str(p) for p in tests_dir.rglob("*_test.py")
                    if str(p) not in test_files
                )
                if test_files:
                    tier_distribution = _get_tier_distribution(test_files)
        except Exception:
            pass  # Non-critical, skip on error

    # Compute acceptance criteria coverage if tracker is available
    acceptance_coverage: Optional[Dict[str, Any]] = None
    if _load_criteria_registry is not None and _compute_criteria_coverage is not None:
        try:
            artifact_dir = Path(".claude/local")
            registry = _load_criteria_registry(artifact_dir)
            coverage = _compute_criteria_coverage(registry, Path("tests"))
            acceptance_coverage = {
                "total": coverage.total,
                "covered": coverage.covered,
                "uncovered_criteria": coverage.uncovered_criteria,
                "coverage_ratio": coverage.coverage_ratio,
                "has_warning": coverage.has_warning,
            }
        except Exception:
            pass  # Non-critical, skip on error

    summary_parts = [test_result.message, coverage_result.message, skip_message, test_count_message]
    if acceptance_coverage and acceptance_coverage["total"] > 0:
        acc_str = f"Acceptance: {acceptance_coverage['covered']}/{acceptance_coverage['total']} criteria"
        summary_parts.append(acc_str)
        if acceptance_coverage["has_warning"]:
            summary_parts.append("WARNING: 0 acceptance tests cover defined criteria")
    if tier_distribution:
        tier_str = ", ".join(f"{k}={v}" for k, v in sorted(tier_distribution.items()))
        summary_parts.append(f"Tiers: {tier_str}")
    if test_result.blocker:
        summary_parts.append(f"BLOCKER: {test_result.blocker}")

    # Update baseline on overall success
    if overall_passed and coverage_result.current_coverage > 0:
        coverage_baseline.save_baseline(
            coverage_pct=coverage_result.current_coverage,
            skip_count=test_result.skipped,
            total_tests=test_result.test_count,
        )

    result: Dict[str, Any] = {
        "passed": overall_passed,
        "test_result": asdict(test_result),
        "coverage_result": asdict(coverage_result),
        "skip_regression": {"passed": skip_passed, "message": skip_message},
        "test_count_regression": {"passed": test_count_passed, "message": test_count_message},
        "tier_distribution": tier_distribution,
        "acceptance_coverage": acceptance_coverage,
        "summary": " | ".join(summary_parts),
    }

    if routing_meta:
        result["routing"] = routing_meta

    return result


if __name__ == "__main__":
    result = run_quality_gate()
    print(result["summary"])
    if not result["passed"]:
        print("\nSTEP 5 QUALITY GATE: FAIL")
        print("Fix all issues before proceeding to STEP 6.")
    else:
        print("\nSTEP 5 QUALITY GATE: PASS")
    sys.exit(0 if result["passed"] else 1)

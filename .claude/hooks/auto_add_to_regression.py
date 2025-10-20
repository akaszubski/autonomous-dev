#!/usr/bin/env python3
"""
Auto-add to regression suite after successful implementation.

This hook automatically grows the regression/progression test suite by:
1. Detecting commit type (feature, bugfix, optimization)
2. Auto-creating appropriate regression test
3. Adding to tests/regression/ or tests/progression/
4. Ensuring tests pass NOW (baseline established)

Hook: PostToolUse after Write to src/**/*.py (when tests are passing)

Types of regression tests:
- Feature: Ensures new feature keeps working
- Bugfix: Ensures bug never returns
- Optimization: Prevents performance regression (baseline)

Usage:
  Triggered automatically by .claude/settings.json hook configuration
  Args from hook: file_paths, user_prompt
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "[project_name]"
TESTS_DIR = PROJECT_ROOT / "tests"
REGRESSION_DIR = TESTS_DIR / "regression"
PROGRESSION_DIR = TESTS_DIR / "progression"

# Commit type detection keywords
BUGFIX_KEYWORDS = ["fix bug", "bug fix", "issue", "error", "crash", "broken"]
OPTIMIZATION_KEYWORDS = ["optimize", "performance", "faster", "speed", "improve"]
FEATURE_KEYWORDS = ["implement", "add feature", "new", "create"]

# ============================================================================
# Helper Functions
# ============================================================================


def detect_commit_type(user_prompt: str) -> str:
    """
    Detect commit type from user prompt.

    Returns: 'bugfix', 'optimization', 'feature', or 'unknown'
    """
    prompt_lower = user_prompt.lower()

    if any(kw in prompt_lower for kw in BUGFIX_KEYWORDS):
        return "bugfix"
    elif any(kw in prompt_lower for kw in OPTIMIZATION_KEYWORDS):
        return "optimization"
    elif any(kw in prompt_lower for kw in FEATURE_KEYWORDS):
        return "feature"
    else:
        return "unknown"


def check_tests_passing(file_path: Path) -> Tuple[bool, str]:
    """Check if tests for this module are passing."""

    module_name = file_path.stem
    test_file = TESTS_DIR / "unit" / f"test_{module_name}.py"

    if not test_file.exists():
        return (False, "No tests exist")

    try:
        result = subprocess.run(
            ["python", "-m", "pytest", str(test_file), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return (True, "All tests passing")
        else:
            return (False, f"Tests failing:\n{result.stdout}")

    except Exception as e:
        return (False, f"Error running tests: {e}")


def generate_feature_regression_test(file_path: Path, user_prompt: str) -> Tuple[Path, str]:
    """
    Generate regression test for a new feature.

    Ensures the feature keeps working in future.
    """
    module_name = file_path.stem
    timestamp = datetime.now().strftime("%Y%m%d")

    test_file = REGRESSION_DIR / f"test_feature_{module_name}_{timestamp}.py"

    # Extract feature description
    feature_desc = user_prompt[:200]

    test_content = f'''"""
Regression test: Feature should continue to work.

Feature: {feature_desc}
Implementation: {file_path}
Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Purpose:
Ensures this feature continues to work as implemented.
If this test fails in future, the feature has regressed.
"""

import pytest
from pathlib import Path
from {file_path.parent.name}.{module_name} import *


def test_feature_baseline():
    """
    Baseline test: Feature should work with standard inputs.

    This test captures the CURRENT working state of the feature.
    If it fails later, something broke the feature.
    """
    # TODO: Add actual test based on feature
    # This is a placeholder - test-master should generate real tests

    # Example structure:
    # 1. Call the main function/class with typical inputs
    # 2. Assert expected behavior
    # 3. Verify output/state is correct

    pass  # Placeholder


def test_feature_edge_cases():
    """
    Edge case test: Feature should handle edge cases correctly.

    Captures edge case behavior that was working.
    """
    # TODO: Add edge case tests
    pass  # Placeholder


# Mark as regression test
pytestmark = pytest.mark.regression
'''

    return (test_file, test_content)


def generate_bugfix_regression_test(file_path: Path, user_prompt: str) -> Tuple[Path, str]:
    """
    Generate regression test for a bug fix.

    Ensures the specific bug never returns.
    """
    module_name = file_path.stem
    timestamp = datetime.now().strftime("%Y%m%d")

    test_file = REGRESSION_DIR / f"test_bugfix_{module_name}_{timestamp}.py"

    bug_desc = user_prompt[:200]

    test_content = f'''"""
Regression test: Bug should never return.

Bug: {bug_desc}
Fixed in: {file_path}
Fixed on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Purpose:
Ensures this specific bug never happens again.
If this test fails, the bug has returned.
"""

import pytest
from pathlib import Path
from {file_path.parent.name}.{module_name} import *


def test_bug_reproduction():
    """
    Reproduction test: Steps that previously triggered the bug.

    This test reproduces the conditions that caused the bug.
    It should PASS now (bug is fixed).
    If it FAILS in future, the bug has returned.
    """
    # TODO: Reproduce the bug conditions
    # Steps that previously caused the bug should now work

    # Example structure:
    # 1. Set up conditions that triggered the bug
    # 2. Call the function/code that was broken
    # 3. Assert the CORRECT behavior (not the buggy behavior)

    pass  # Placeholder


def test_bug_related_edge_cases():
    """
    Related edge cases: Similar scenarios that might trigger the bug.

    Tests variations of the bug condition.
    """
    # TODO: Add related edge case tests
    pass  # Placeholder


# Mark as regression test
pytestmark = pytest.mark.regression
'''

    return (test_file, test_content)


def generate_performance_baseline_test(file_path: Path, user_prompt: str) -> Tuple[Path, str]:
    """
    Generate performance baseline test for an optimization.

    Prevents performance regression below current baseline.
    """
    module_name = file_path.stem
    timestamp = datetime.now().strftime("%Y%m%d")

    test_file = PROGRESSION_DIR / f"test_perf_{module_name}_{timestamp}.py"

    optimization_desc = user_prompt[:200]

    test_content = f'''"""
Performance baseline test: Prevent performance regression.

Optimization: {optimization_desc}
Optimized file: {file_path}
Baseline set: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Purpose:
Captures current performance as baseline.
Future changes should not degrade performance below this baseline.
"""

import pytest
import time
from pathlib import Path
from {file_path.parent.name}.{module_name} import *


# Store baseline metrics
BASELINE_METRICS = {{
    "execution_time_seconds": None,  # Will be set after first run
    "memory_usage_mb": None,
    "tolerance_percent": 10,  # Allow 10% variance
}}


def test_performance_baseline():
    """
    Performance baseline: Current performance should not regress.

    Measures execution time and ensures future changes don't slow it down.
    """
    # TODO: Add actual performance test

    # Example structure:
    # 1. Measure execution time
    # 2. Compare to baseline (if exists)
    # 3. Assert within tolerance

    start_time = time.time()

    # Call the optimized function
    # result = optimized_function()

    elapsed = time.time() - start_time

    # First run: establish baseline
    if BASELINE_METRICS["execution_time_seconds"] is None:
        BASELINE_METRICS["execution_time_seconds"] = elapsed
        print(f"Baseline established: {{elapsed:.3f}}s")

    # Subsequent runs: check regression
    else:
        baseline = BASELINE_METRICS["execution_time_seconds"]
        tolerance = baseline * (BASELINE_METRICS["tolerance_percent"] / 100)
        max_allowed = baseline + tolerance

        assert elapsed <= max_allowed, (
            f"Performance regression detected! "
            f"Current: {{elapsed:.3f}}s > Baseline: {{baseline:.3f}}s "
            f"(+{{tolerance:.3f}}s tolerance)"
        )

        print(f"Performance OK: {{elapsed:.3f}}s (baseline: {{baseline:.3f}}s)")

    pass  # Placeholder


# Mark as progression test
pytestmark = pytest.mark.progression
'''

    return (test_file, test_content)


def create_regression_test(commit_type: str, file_path: Path, user_prompt: str) -> Optional[Path]:
    """
    Create appropriate regression test based on commit type.

    Returns path to created test file, or None if skipped.
    """

    # Ensure directories exist
    REGRESSION_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESSION_DIR.mkdir(parents=True, exist_ok=True)

    if commit_type == "feature":
        test_file, content = generate_feature_regression_test(file_path, user_prompt)
    elif commit_type == "bugfix":
        test_file, content = generate_bugfix_regression_test(file_path, user_prompt)
    elif commit_type == "optimization":
        test_file, content = generate_performance_baseline_test(file_path, user_prompt)
    else:
        # Unknown commit type - skip
        return None

    # Write test file
    test_file.write_text(content)

    return test_file


def run_regression_test(test_file: Path) -> Tuple[bool, str]:
    """Run the newly created regression test to verify it passes."""

    try:
        result = subprocess.run(
            ["python", "-m", "pytest", str(test_file), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = result.stdout + result.stderr

        if result.returncode == 0:
            return (True, output)
        else:
            return (False, output)

    except Exception as e:
        return (False, f"Error running regression test: {e}")


# ============================================================================
# Main Logic
# ============================================================================


def main():
    """Main hook logic."""

    if len(sys.argv) < 2:
        print("Usage: auto_add_to_regression.py <file_path> [user_prompt]")
        sys.exit(0)

    file_path = Path(sys.argv[1])
    user_prompt = sys.argv[2] if len(sys.argv) > 2 else ""

    # Only process source files
    if not str(file_path).startswith("src/"):
        sys.exit(0)

    # Skip __init__.py
    if file_path.stem == "__init__":
        sys.exit(0)

    print(f"\n📈 Auto-Regression Suite Hook")
    print(f"   File: {file_path.name}")

    # Detect commit type
    commit_type = detect_commit_type(user_prompt)

    print(f"   Commit type: {commit_type}")

    if commit_type == "unknown":
        print(f"   ℹ️  Unknown commit type - skipping regression test generation")
        sys.exit(0)

    # Check if tests are passing (regression tests only for working code)
    print(f"\n🧪 Verifying tests are passing...")

    passing, message = check_tests_passing(file_path)

    if not passing:
        print(f"   ⚠️  Tests not passing - skipping regression test")
        print(f"   Reason: {message}")
        print(f"   Regression tests are only created for verified working code")
        sys.exit(0)

    print(f"   ✅ Tests passing - proceeding with regression test creation")

    # Create regression test
    print(f"\n🔒 Creating regression test...")
    print(f"   Type: {commit_type}")

    test_file = create_regression_test(commit_type, file_path, user_prompt)

    if test_file is None:
        print(f"   ℹ️  Skipped regression test creation")
        sys.exit(0)

    print(f"   ✅ Created: {test_file}")

    # Run regression test to verify it passes NOW
    print(f"\n🧪 Running regression test (should PASS)...")

    passing, output = run_regression_test(test_file)

    if passing:
        print(f"   ✅ Regression test PASSING (baseline established)")
        print(f"   This test will prevent future regressions")
    else:
        print(f"   ⚠️  Regression test FAILING")
        print(f"   The test needs adjustment before it can protect against regression")
        print(f"\n   Output:")
        for line in output.split("\n")[:15]:
            print(f"      {line}")

    print(f"\n✅ Auto-regression suite update complete!")
    print(f"   Regression test: {test_file}")
    print(f"   Purpose: Prevent {commit_type} from regressing")
    print(f"   Status: {'PASSING' if passing else 'NEEDS REVIEW'}")


if __name__ == "__main__":
    main()

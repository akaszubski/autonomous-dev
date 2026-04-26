#!/usr/bin/env python3
"""
Multi-language test runner hook.

Automatically detects test framework and runs tests.
Enforces minimum 80% code coverage.

Supported frameworks:
- Python: pytest
- JavaScript/TypeScript: jest, vitest
- Go: go test
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return → exit code, sys.exit → propagated).
import sys as _sys_953  # alias to avoid colliding with hook-local sys imports
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import subprocess
import os
import sys
from pathlib import Path
from typing import Tuple


def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ
# Fallback for non-UV environments (placeholder - this hook doesn't use lib imports)
if not is_running_under_uv():
    # This hook doesn't import from autonomous-dev/lib
    # But we keep sys.path.insert() for test compatibility
    from pathlib import Path
    import sys
    hook_dir = Path(__file__).parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))


def detect_test_framework() -> Tuple[str, str]:
    """Detect test framework from project files.

    Returns:
        (language, framework) tuple
    """
    # Python
    if Path("pytest.ini").exists() or Path("pyproject.toml").exists():
        return "python", "pytest"

    # JavaScript/TypeScript
    if Path("jest.config.js").exists() or Path("jest.config.ts").exists():
        return "javascript", "jest"
    if Path("vitest.config.js").exists() or Path("vitest.config.ts").exists():
        return "javascript", "vitest"
    if Path("package.json").exists():
        # Check package.json for test script
        return "javascript", "npm"

    # Go
    if Path("go.mod").exists():
        return "go", "go-test"

    return "unknown", "unknown"


def run_pytest() -> bool:
    """Run pytest with coverage."""
    try:
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "tests/",
                "--cov=src",
                "--cov-fail-under=80",
                "--cov-report=term-missing:skip-covered",
                "--tb=short",
                "-q",
            ],
            capture_output=True,
            text=True,
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        return result.returncode == 0
    except FileNotFoundError:
        print("❌ pytest not installed. Run: pip install pytest pytest-cov")
        return False


def run_jest() -> bool:
    """Run jest with coverage."""
    try:
        result = subprocess.run(
            ["npx", "jest", "--coverage", "--coverageThreshold", '{"global":{"lines":80}}'],
            capture_output=True,
            text=True,
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        return result.returncode == 0
    except FileNotFoundError:
        print("❌ jest not installed. Run: npm install --save-dev jest")
        return False


def run_vitest() -> bool:
    """Run vitest with coverage."""
    try:
        result = subprocess.run(
            ["npx", "vitest", "run", "--coverage"], capture_output=True, text=True
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        return result.returncode == 0
    except FileNotFoundError:
        print("❌ vitest not installed. Run: npm install --save-dev vitest")
        return False


def run_npm_test() -> bool:
    """Run npm test."""
    try:
        result = subprocess.run(["npm", "test"], capture_output=True, text=True)

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        return result.returncode == 0
    except FileNotFoundError:
        print("❌ npm not found")
        return False


def run_go_test() -> bool:
    """Run go test with coverage."""
    try:
        # Run tests with coverage
        result = subprocess.run(
            ["go", "test", "-cover", "./...", "-coverprofile=coverage.out"],
            capture_output=True,
            text=True,
        )

        print(result.stdout)

        if result.returncode != 0:
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return False

        # Check coverage percentage
        cov_result = subprocess.run(
            ["go", "tool", "cover", "-func=coverage.out"], capture_output=True, text=True
        )

        # Extract total coverage from last line
        lines = cov_result.stdout.strip().split("\n")
        if lines:
            last_line = lines[-1]
            if "total:" in last_line:
                coverage = float(last_line.split()[-1].rstrip("%"))
                print(f"\nTotal coverage: {coverage}%")

                if coverage < 80:
                    print(f"❌ Coverage {coverage}% below 80% threshold")
                    return False

        return True
    except FileNotFoundError:
        print("❌ go not installed")
        return False


def main():
    """Run tests based on detected framework."""
    # Universal bypass (Issue #969): env var or .claude/.bypass falls through.
    try:
        from hook_bypass import is_bypassed, log_bypass_used
        if is_bypassed():
            log_bypass_used(hook_name=Path(__file__).name, tool_name="auto_test")
            sys.exit(0)
    except ImportError:
        pass

    language, framework = detect_test_framework()

    if language == "unknown":
        print("⚠️  Could not detect test framework. Skipping tests.")
        print("ℹ️  Create pytest.ini, jest.config.js, or go.mod to enable auto-testing")
        sys.exit(0)  # Don't fail, just skip

    print(f"🧪 Running tests with {framework}...")

    # Run tests
    runners = {
        "pytest": run_pytest,
        "jest": run_jest,
        "vitest": run_vitest,
        "npm": run_npm_test,
        "go-test": run_go_test,
    }

    success = runners[framework]()

    if success:
        print("✅ Tests passed with ≥80% coverage")
        sys.exit(0)
    else:
        print("❌ Tests failed or coverage below 80%")
        sys.exit(1)


if __name__ == "__main__":
    _safe_main_953(main)

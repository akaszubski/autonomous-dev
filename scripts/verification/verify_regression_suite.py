#!/usr/bin/env python3
"""Verification script for regression test suite structure.

Validates:
- Directory structure exists
- Test files are properly formatted
- Fixtures are defined
- Markers are used
- Docstrings present

Run: python tests/verify_regression_suite.py
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Tuple


class RegressionSuiteValidator:
    """Validate regression test suite structure and quality."""

    def __init__(self, regression_dir: Path):
        self.regression_dir = regression_dir
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.stats: Dict[str, int] = {
            'total_files': 0,
            'total_tests': 0,
            'total_fixtures': 0,
            'tests_with_docstrings': 0,
            'tests_with_markers': 0,
        }

    def validate(self) -> bool:
        """Run all validations.

        Returns:
            bool: True if all validations pass
        """
        print("Validating regression test suite...")
        print(f"Directory: {self.regression_dir}\n")

        # Check directory structure
        self._validate_directory_structure()

        # Check test files
        self._validate_test_files()

        # Check fixtures
        self._validate_fixtures()

        # Print results
        self._print_results()

        return len(self.errors) == 0

    def _validate_directory_structure(self):
        """Validate required directories exist."""
        print("Checking directory structure...")

        required_dirs = [
            'smoke',
            'regression',
            'extended',
            'progression',
        ]

        for dir_name in required_dirs:
            dir_path = self.regression_dir / dir_name
            if not dir_path.exists():
                self.errors.append(f"Missing directory: {dir_name}/")
            else:
                print(f"  ✓ {dir_name}/ exists")

    def _validate_test_files(self):
        """Validate test files are properly formatted."""
        print("\nChecking test files...")

        test_files = list(self.regression_dir.rglob("test_*.py"))
        self.stats['total_files'] = len(test_files)

        for test_file in test_files:
            print(f"\n  Analyzing {test_file.name}...")
            self._analyze_test_file(test_file)

    def _analyze_test_file(self, test_file: Path):
        """Analyze a single test file.

        Args:
            test_file: Path to test file
        """
        try:
            with open(test_file) as f:
                tree = ast.parse(f.read(), filename=str(test_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.name.startswith('test_'):
                        self._validate_test_function(node, test_file)

        except SyntaxError as e:
            self.errors.append(f"{test_file.name}: Syntax error - {e}")

    def _validate_test_function(self, node: ast.FunctionDef, test_file: Path):
        """Validate a single test function.

        Args:
            node: AST node for test function
            test_file: Path to test file
        """
        self.stats['total_tests'] += 1

        # Check docstring
        docstring = ast.get_docstring(node)
        if docstring:
            self.stats['tests_with_docstrings'] += 1

            # Check for "Protects:" in docstring
            if "Protects:" not in docstring and "protects:" not in docstring.lower():
                self.warnings.append(
                    f"{test_file.name}::{node.name} - Missing 'Protects:' in docstring"
                )
        else:
            self.errors.append(
                f"{test_file.name}::{node.name} - Missing docstring"
            )

        # Check for pytest markers
        has_marker = False
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Attribute):
                if decorator.attr in ['smoke', 'regression', 'extended', 'progression']:
                    has_marker = True
                    self.stats['tests_with_markers'] += 1
                    break

        if not has_marker:
            self.warnings.append(
                f"{test_file.name}::{node.name} - Missing pytest marker (@pytest.mark.smoke, etc.)"
            )

    def _validate_fixtures(self):
        """Validate fixtures are defined in conftest.py."""
        print("\nChecking fixtures...")

        conftest = self.regression_dir / "conftest.py"
        if not conftest.exists():
            self.errors.append("Missing conftest.py")
            return

        try:
            with open(conftest) as f:
                tree = ast.parse(f.read(), filename=str(conftest))

            fixtures = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if decorated with @pytest.fixture
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Attribute):
                            if decorator.attr == 'fixture':
                                fixtures.append(node.name)
                                break
                        elif isinstance(decorator, ast.Name):
                            if decorator.id == 'fixture':
                                fixtures.append(node.name)
                                break

            self.stats['total_fixtures'] = len(fixtures)
            print(f"  ✓ Found {len(fixtures)} fixtures")

            # Check for required fixtures
            required_fixtures = [
                'project_root',
                'plugins_dir',
                'isolated_project',
                'timing_validator',
            ]

            for fixture in required_fixtures:
                if fixture in fixtures:
                    print(f"    ✓ {fixture}")
                else:
                    self.warnings.append(f"Missing recommended fixture: {fixture}")

        except SyntaxError as e:
            self.errors.append(f"conftest.py: Syntax error - {e}")

    def _print_results(self):
        """Print validation results."""
        print("\n" + "=" * 70)
        print("VALIDATION RESULTS")
        print("=" * 70)

        # Statistics
        print("\nStatistics:")
        print(f"  Total test files: {self.stats['total_files']}")
        print(f"  Total test functions: {self.stats['total_tests']}")
        print(f"  Total fixtures: {self.stats['total_fixtures']}")
        print(f"  Tests with docstrings: {self.stats['tests_with_docstrings']}/{self.stats['total_tests']} "
              f"({self._percent(self.stats['tests_with_docstrings'], self.stats['total_tests'])}%)")
        print(f"  Tests with markers: {self.stats['tests_with_markers']}/{self.stats['total_tests']} "
              f"({self._percent(self.stats['tests_with_markers'], self.stats['total_tests'])}%)")

        # Warnings
        if self.warnings:
            print(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings[:10]:  # Show first 10
                print(f"  ⚠ {warning}")
            if len(self.warnings) > 10:
                print(f"  ... and {len(self.warnings) - 10} more warnings")

        # Errors
        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  ✗ {error}")
            print("\n❌ VALIDATION FAILED")
            return False
        else:
            print("\n✅ VALIDATION PASSED")
            if self.warnings:
                print(f"   ({len(self.warnings)} warnings - review recommended)")
            return True

    def _percent(self, value: int, total: int) -> int:
        """Calculate percentage.

        Args:
            value: Numerator
            total: Denominator

        Returns:
            int: Percentage (0-100)
        """
        if total == 0:
            return 0
        return int((value / total) * 100)


def main():
    """Main entry point."""
    # Find regression directory
    script_dir = Path(__file__).parent
    regression_dir = script_dir / "regression"

    if not regression_dir.exists():
        print(f"Error: Regression directory not found: {regression_dir}")
        sys.exit(1)

    # Validate
    validator = RegressionSuiteValidator(regression_dir)
    success = validator.validate()

    # Exit code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

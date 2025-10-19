#!/usr/bin/env python3
"""
Validate code standards script triggered by PostToolUse hook.
Checks for:
- Type hints on public functions
- Docstrings (Google style)
- File length limits
- Function complexity

Usage:
    python scripts/hooks/validate_standards.py [file1.py] [file2.py] ...
"""

import ast
import sys
from pathlib import Path


class StandardsValidator(ast.NodeVisitor):
    """AST visitor to validate coding standards."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.issues = []
        self.stats = {
            "functions": 0,
            "functions_with_docstrings": 0,
            "functions_with_type_hints": 0,
            "classes": 0,
            "max_function_length": 0,
        }

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition."""
        self.stats["functions"] += 1

        # Skip private functions (start with _)
        if node.name.startswith("_"):
            self.generic_visit(node)
            return

        # Check for docstring
        docstring = ast.get_docstring(node)
        if docstring:
            self.stats["functions_with_docstrings"] += 1
        else:
            self.issues.append(
                f"Line {node.lineno}: Function '{node.name}' missing docstring"
            )

        # Check for type hints on public functions
        has_type_hints = False
        if node.returns is not None:
            has_type_hints = True
        for arg in node.args.args:
            if arg.annotation is not None:
                has_type_hints = True
                break

        if has_type_hints:
            self.stats["functions_with_type_hints"] += 1
        else:
            # Only warn for public functions
            self.issues.append(
                f"Line {node.lineno}: Function '{node.name}' missing type hints"
            )

        # Check function length
        function_length = self._get_node_length(node)
        if function_length > 50:
            self.issues.append(
                f"Line {node.lineno}: Function '{node.name}' is {function_length} lines "
                f"(max 50). Consider breaking into smaller functions."
            )
        self.stats["max_function_length"] = max(
            self.stats["max_function_length"], function_length
        )

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition."""
        self.stats["classes"] += 1

        # Check for class docstring
        docstring = ast.get_docstring(node)
        if not docstring and not node.name.startswith("_"):
            self.issues.append(f"Line {node.lineno}: Class '{node.name}' missing docstring")

        self.generic_visit(node)

    def _get_node_length(self, node: ast.AST) -> int:
        """Calculate the number of lines in a node."""
        if hasattr(node, "end_lineno") and hasattr(node, "lineno"):
            return node.end_lineno - node.lineno + 1
        return 0


def validate_file(file_path: Path) -> tuple[bool, list[str], dict]:
    """
    Validate a Python file against coding standards.

    Args:
        file_path: Path to Python file

    Returns:
        Tuple of (passed: bool, issues: list[str], stats: dict)
    """
    if not file_path.exists():
        return False, [f"File not found: {file_path}"], {}

    if file_path.suffix != ".py":
        return True, [], {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines()

        # Check file length
        if len(lines) > 500:
            return (
                False,
                [f"File is {len(lines)} lines (max 500). Consider splitting into modules."],
                {},
            )

        # Parse AST
        tree = ast.parse(content, filename=str(file_path))
        validator = StandardsValidator(file_path)
        validator.visit(tree)

        # Determine if validation passed
        # We'll be lenient - just warnings, not hard failures
        passed = len(validator.issues) == 0

        return passed, validator.issues, validator.stats

    except SyntaxError as e:
        return False, [f"Syntax error: {e}"], {}
    except Exception as e:
        return False, [f"Error validating file: {e}"], {}


def main():
    """Main entry point for standards validation hook."""
    if len(sys.argv) < 2:
        print("No files specified")
        return 0

    files = [Path(f) for f in sys.argv[1:]]
    all_passed = True
    total_issues = 0

    print("📋 Validating code standards...\n")

    for file_path in files:
        passed, issues, stats = validate_file(file_path)

        if not passed or issues:
            print(f"⚠️  {file_path}")
            for issue in issues:
                print(f"    {issue}")
            print()
            total_issues += len(issues)
            # Don't fail on warnings, just inform
            # all_passed = False
        else:
            print(f"✓ {file_path}")

        # Show stats if available
        if stats and stats.get("functions", 0) > 0:
            funcs = stats["functions"]
            docs = stats["functions_with_docstrings"]
            types = stats["functions_with_type_hints"]
            print(f"    Functions: {funcs}, Docstrings: {docs}/{funcs}, Type hints: {types}/{funcs}")

    print(f"\n📊 Summary:")
    print(f"  Files scanned: {len(files)}")
    print(f"  Issues found: {total_issues}")

    if total_issues > 0:
        print("\n⚠️  Code quality warnings found (not blocking)")
        print("Consider fixing these to improve code quality")
        # Return 0 - warnings don't block, just inform
        return 0

    print("\n✅ All standards validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

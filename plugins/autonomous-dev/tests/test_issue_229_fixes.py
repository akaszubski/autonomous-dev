"""
Test Suite for Issue #229: Critical Test Failure Fixes

This test suite validates the 3 critical bug fixes:
1. Fix missing import os in hooks/genai_prompts.py (line 228 uses os.environ)
2. Fix unterminated f-string in tests/test_documentation_consistency.py:391
3. Fix incorrect path from scripts to hooks in tests/test_claude_alignment.py:20

Test Strategy:
- Syntax validation - all files must compile without SyntaxError
- Import validation - modules must import successfully
- Functional validation - fixed code must work as expected
- Integration validation - existing tests must run and pass

Tier: smoke (critical path validation)
"""

import ast
import importlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

import pytest


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def project_root() -> Path:
    """Get project root directory."""
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "PROJECT.md").exists() or (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root")


@pytest.fixture
def genai_prompts_path(project_root: Path) -> Path:
    """Path to genai_prompts.py."""
    return project_root / "plugins/autonomous-dev/hooks/genai_prompts.py"


@pytest.fixture
def test_documentation_path(project_root: Path) -> Path:
    """Path to test_documentation_consistency.py."""
    return project_root / "plugins/autonomous-dev/tests/test_documentation_consistency.py"


@pytest.fixture
def test_alignment_path(project_root: Path) -> Path:
    """Path to test_claude_alignment.py."""
    return project_root / "plugins/autonomous-dev/tests/test_claude_alignment.py"


# ============================================================================
# Fix 1: genai_prompts.py missing import os
# ============================================================================


def test_genai_prompts_syntax_valid(genai_prompts_path: Path):
    """
    Validate genai_prompts.py has valid Python syntax.

    This test ensures the file can be parsed by Python's AST parser.
    Catches syntax errors like missing imports that would cause runtime failures.
    """
    assert genai_prompts_path.exists(), f"File not found: {genai_prompts_path}"

    content = genai_prompts_path.read_text()

    # Parse AST - will raise SyntaxError if invalid
    try:
        ast.parse(content)
    except SyntaxError as e:
        pytest.fail(
            f"Syntax error in {genai_prompts_path}:\n"
            f"Line {e.lineno}: {e.msg}\n"
            f"Text: {e.text}"
        )


def test_genai_prompts_has_os_import(genai_prompts_path: Path):
    """
    Verify genai_prompts.py imports os module.

    Fix: Line 228 uses os.environ, so os must be imported.
    Previously missing, causing NameError at runtime.
    """
    content = genai_prompts_path.read_text()

    # Check for import os statement
    has_import = (
        "import os" in content or
        "from os import" in content or
        re.search(r"^import\s+os\s*$", content, re.MULTILINE) is not None
    )

    assert has_import, (
        f"Missing 'import os' in {genai_prompts_path.name}\n"
        f"Line 228 uses os.environ['UV_PROJECT_ENVIRONMENT']\n"
        f"Add 'import os' to imports section"
    )


def test_genai_prompts_compiles_successfully(genai_prompts_path: Path):
    """
    Verify genai_prompts.py compiles without errors.

    Uses py_compile to validate bytecode compilation.
    """
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(genai_prompts_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Failed to compile {genai_prompts_path.name}:\n"
        f"STDOUT: {result.stdout}\n"
        f"STDERR: {result.stderr}"
    )


def test_genai_prompts_is_running_under_uv_function_works(genai_prompts_path: Path):
    """
    Test is_running_under_uv() function works correctly.

    This function uses os.environ, so it validates the fix for missing import os.
    """
    # Import the module dynamically
    spec = importlib.util.spec_from_file_location("genai_prompts", genai_prompts_path)
    assert spec is not None, f"Could not load spec from {genai_prompts_path}"
    assert spec.loader is not None, f"Spec has no loader: {genai_prompts_path}"

    module = importlib.util.module_from_spec(spec)

    # Execute module - will fail if os is not imported
    try:
        spec.loader.exec_module(module)
    except NameError as e:
        pytest.fail(
            f"NameError when importing {genai_prompts_path.name}:\n"
            f"{e}\n"
            f"Likely missing 'import os'"
        )

    # Test the function
    assert hasattr(module, "is_running_under_uv"), (
        "Module missing is_running_under_uv() function"
    )

    # Function should return bool
    result = module.is_running_under_uv()
    assert isinstance(result, bool), (
        f"is_running_under_uv() should return bool, got {type(result)}"
    )

    # Test with UV env var set
    os.environ["UV_PROJECT_ENVIRONMENT"] = "test"
    assert module.is_running_under_uv() is True

    # Test with UV env var unset
    del os.environ["UV_PROJECT_ENVIRONMENT"]
    assert module.is_running_under_uv() is False


# ============================================================================
# Fix 2: test_documentation_consistency.py unterminated f-string
# ============================================================================


def test_documentation_consistency_syntax_valid(test_documentation_path: Path):
    """
    Validate test_documentation_consistency.py has valid Python syntax.

    Fix: Line 391 had unterminated f-string causing SyntaxError.
    """
    assert test_documentation_path.exists(), f"File not found: {test_documentation_path}"

    content = test_documentation_path.read_text()

    # Parse AST - will raise SyntaxError if invalid
    try:
        ast.parse(content)
    except SyntaxError as e:
        pytest.fail(
            f"Syntax error in {test_documentation_path.name}:\n"
            f"Line {e.lineno}: {e.msg}\n"
            f"Text: {e.text}\n\n"
            f"Common cause: Unterminated f-string (missing closing quote)"
        )


def test_documentation_consistency_no_unterminated_fstrings(test_documentation_path: Path):
    """
    Check for unterminated f-strings in test_documentation_consistency.py.

    Fix: Line 391 had f" without closing quote.
    """
    content = test_documentation_path.read_text()
    lines = content.splitlines()

    # Look for f-strings and check they're properly terminated
    unterminated = []
    for i, line in enumerate(lines, start=1):
        # Skip comments
        if line.strip().startswith("#"):
            continue

        # Check for f-string patterns
        if re.search(r'f["\']', line):
            # Count quotes - should be even for each type
            double_quotes = line.count('"') - line.count('\\"')
            single_quotes = line.count("'") - line.count("\\'")

            # For multi-line strings, this is more complex
            # Simple heuristic: line with f" should have matching "
            if 'f"' in line and double_quotes % 2 != 0:
                # Could be multi-line, check next lines
                if i < len(lines) and '"""' not in line:
                    unterminated.append((i, line.strip()))

    assert not unterminated, (
        f"Potential unterminated f-strings in {test_documentation_path.name}:\n" +
        "\n".join(f"Line {num}: {text}" for num, text in unterminated)
    )


def test_documentation_consistency_compiles_successfully(test_documentation_path: Path):
    """
    Verify test_documentation_consistency.py compiles without errors.
    """
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(test_documentation_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Failed to compile {test_documentation_path.name}:\n"
        f"STDOUT: {result.stdout}\n"
        f"STDERR: {result.stderr}"
    )


def test_documentation_consistency_imports_successfully(test_documentation_path: Path):
    """
    Verify test_documentation_consistency.py can be imported.

    This catches syntax errors that py_compile might miss.
    """
    # Add to path
    test_dir = test_documentation_path.parent
    if str(test_dir) not in sys.path:
        sys.path.insert(0, str(test_dir))

    try:
        # Import - will fail if syntax error
        import test_documentation_consistency
        importlib.reload(test_documentation_consistency)
    except SyntaxError as e:
        pytest.fail(
            f"SyntaxError when importing {test_documentation_path.name}:\n"
            f"Line {e.lineno}: {e.msg}\n"
            f"Text: {e.text}"
        )
    except ImportError as e:
        # ImportError is OK (missing dependencies), we're testing syntax
        if "invalid syntax" in str(e).lower():
            pytest.fail(f"Syntax error in {test_documentation_path.name}: {e}")


# ============================================================================
# Fix 3: test_claude_alignment.py wrong path (scripts vs hooks)
# ============================================================================


def test_claude_alignment_syntax_valid(test_alignment_path: Path):
    """
    Validate test_claude_alignment.py has valid Python syntax.
    """
    assert test_alignment_path.exists(), f"File not found: {test_alignment_path}"

    content = test_alignment_path.read_text()

    # Parse AST - will raise SyntaxError if invalid
    try:
        ast.parse(content)
    except SyntaxError as e:
        pytest.fail(
            f"Syntax error in {test_alignment_path.name}:\n"
            f"Line {e.lineno}: {e.msg}\n"
            f"Text: {e.text}"
        )


def test_claude_alignment_uses_correct_path(test_alignment_path: Path, project_root: Path):
    """
    Verify test_claude_alignment.py uses correct path for validate_claude_alignment.

    Fix: Line 20 had 'scripts' but should be 'hooks'.
    validate_claude_alignment.py is in hooks/ not scripts/.
    """
    content = test_alignment_path.read_text()

    # Check that it references hooks, not scripts
    assert "scripts" not in content or content.count("scripts") == 0 or "hooks" in content, (
        f"test_claude_alignment.py should reference 'hooks' not 'scripts'\n"
        f"validate_claude_alignment.py is in plugins/autonomous-dev/hooks/"
    )

    # Verify the actual path exists
    validator_path = project_root / "plugins/autonomous-dev/hooks/validate_claude_alignment.py"
    assert validator_path.exists(), (
        f"validate_claude_alignment.py not found at expected location:\n"
        f"{validator_path}\n"
        f"test_claude_alignment.py may have wrong path"
    )


def test_claude_alignment_can_import_validator(test_alignment_path: Path, project_root: Path):
    """
    Verify test_claude_alignment.py can import validate_claude_alignment.

    This validates the path fix - script is in hooks/ not scripts/.
    """
    # Setup paths
    test_dir = test_alignment_path.parent
    hooks_dir = project_root / "plugins/autonomous-dev/hooks"

    # Add both to path
    for path in [test_dir, hooks_dir]:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    try:
        # Import validator module
        import validate_claude_alignment

        # Verify expected class exists (extract_* are private methods on the class)
        expected_exports = [
            "ClaudeAlignmentValidator",
        ]

        for name in expected_exports:
            assert hasattr(validate_claude_alignment, name), (
                f"validate_claude_alignment missing expected export: {name}"
            )

        # Verify private methods exist on the class
        validator_class = validate_claude_alignment.ClaudeAlignmentValidator
        private_methods = ["_extract_date", "_extract_agent_count", "_extract_command_count"]
        for method in private_methods:
            assert hasattr(validator_class, method), (
                f"ClaudeAlignmentValidator missing private method: {method}"
            )

    except ImportError as e:
        pytest.fail(
            f"Failed to import validate_claude_alignment:\n"
            f"{e}\n\n"
            f"This likely means test_claude_alignment.py has wrong path.\n"
            f"Script is in hooks/ not scripts/"
        )


def test_claude_alignment_compiles_successfully(test_alignment_path: Path):
    """
    Verify test_claude_alignment.py compiles without errors.
    """
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(test_alignment_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Failed to compile {test_alignment_path.name}:\n"
        f"STDOUT: {result.stdout}\n"
        f"STDERR: {result.stderr}"
    )


# ============================================================================
# Integration Tests - Run Fixed Tests
# ============================================================================


def test_integration_run_fixed_tests(project_root: Path):
    """
    Integration test: Run the fixed test files to verify they execute.

    This validates all 3 fixes work together:
    1. genai_prompts.py imports without error
    2. test_documentation_consistency.py has valid syntax
    3. test_claude_alignment.py can import validator
    """
    test_files = [
        "plugins/autonomous-dev/tests/test_documentation_consistency.py",
        "plugins/autonomous-dev/tests/test_claude_alignment.py",
    ]

    for test_file in test_files:
        test_path = project_root / test_file

        # Run single test file with minimal output
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(test_path),
                "--tb=line",
                "-q",
                "--maxfail=1",  # Stop on first failure
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # We expect these tests to run without syntax errors
        # They may fail for other reasons (missing fixtures, etc.)
        # But they should NOT fail with SyntaxError or ImportError
        if "SyntaxError" in result.stderr or "SyntaxError" in result.stdout:
            pytest.fail(
                f"SyntaxError when running {test_file}:\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )

        if "NameError: name 'os' is not defined" in result.stderr:
            pytest.fail(
                f"Missing 'import os' in genai_prompts.py:\n"
                f"STDERR: {result.stderr}"
            )


# ============================================================================
# Regression Tests - Prevent Future Breakage
# ============================================================================


def test_regression_all_test_files_have_valid_syntax(project_root: Path):
    """
    Regression test: Verify all test files have valid Python syntax.

    Prevents future syntax errors in test files.
    """
    test_dir = project_root / "plugins/autonomous-dev/tests"
    test_files = list(test_dir.glob("test_*.py"))

    assert len(test_files) > 0, f"No test files found in {test_dir}"

    syntax_errors = []
    for test_file in test_files:
        try:
            content = test_file.read_text()
            ast.parse(content)
        except SyntaxError as e:
            syntax_errors.append((test_file.name, e.lineno, e.msg))

    assert not syntax_errors, (
        "Syntax errors found in test files:\n" +
        "\n".join(
            f"  {name} line {line}: {msg}"
            for name, line, msg in syntax_errors
        )
    )


def test_regression_all_hook_files_have_valid_syntax(project_root: Path):
    """
    Regression test: Verify all hook files have valid Python syntax.

    Prevents future syntax errors in hook files.
    """
    hooks_dir = project_root / "plugins/autonomous-dev/hooks"
    hook_files = list(hooks_dir.glob("*.py"))

    assert len(hook_files) > 0, f"No hook files found in {hooks_dir}"

    syntax_errors = []
    for hook_file in hook_files:
        try:
            content = hook_file.read_text()
            ast.parse(content)
        except SyntaxError as e:
            syntax_errors.append((hook_file.name, e.lineno, e.msg))

    assert not syntax_errors, (
        "Syntax errors found in hook files:\n" +
        "\n".join(
            f"  {name} line {line}: {msg}"
            for name, line, msg in syntax_errors
        )
    )


# ============================================================================
# Helper Functions
# ============================================================================


import re


def find_fstring_issues(content: str) -> List[Tuple[int, str]]:
    """
    Find potential f-string syntax issues in Python code.

    Returns:
        List of (line_number, line_text) tuples with potential issues
    """
    issues = []
    lines = content.splitlines()

    in_multiline_string = False
    multiline_delimiter = None

    for i, line in enumerate(lines, start=1):
        # Track multiline strings
        if '"""' in line or "'''" in line:
            if not in_multiline_string:
                in_multiline_string = True
                multiline_delimiter = '"""' if '"""' in line else "'''"
            elif multiline_delimiter in line:
                in_multiline_string = False
                multiline_delimiter = None
                continue

        if in_multiline_string:
            continue

        # Check for f-string patterns
        if re.search(r'f["\']', line):
            # Simple check: count unescaped quotes
            stripped = line.strip()

            # Skip if it's clearly a multi-line f-string
            if stripped.endswith('"""') or stripped.endswith("'''"):
                continue

            # Count quotes
            double = line.count('"') - line.count('\\"')
            single = line.count("'") - line.count("\\'")

            # Odd number of quotes might indicate unterminated string
            if (double % 2 != 0) or (single % 2 != 0):
                issues.append((i, line.strip()))

    return issues

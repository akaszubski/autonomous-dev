"""Acceptance tests for: Evaluator agent runtime verification (Issue #564).

Structural assertions validating classifier exists and reviewer has
runtime verification instructions.

GitHub Issue: #564
"""

import ast
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

CLASSIFIER_LIB = PROJECT_ROOT / "plugins/autonomous-dev/lib/runtime_verification_classifier.py"
CLASSIFIER_TESTS = PROJECT_ROOT / "tests/unit/lib/test_runtime_verification_classifier.py"
REVIEWER_MD = PROJECT_ROOT / "plugins/autonomous-dev/agents/reviewer.md"
IMPLEMENT_MD = PROJECT_ROOT / "plugins/autonomous-dev/commands/implement.md"


def _get_ast(path: Path) -> ast.Module:
    """Parse a Python file into an AST."""
    return ast.parse(path.read_text())


def _get_function_names(tree: ast.Module) -> list:
    """Extract top-level function names from AST."""
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def _get_class_names(tree: ast.Module) -> list:
    """Extract class names from AST."""
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


# ============================================================
# Classifier module existence
# ============================================================


@pytest.mark.genai
class TestClassifierModuleExists:
    """Classifier module and tests must exist."""

    def test_classifier_lib_exists(self):
        assert CLASSIFIER_LIB.exists(), f"Missing: {CLASSIFIER_LIB}"

    def test_classifier_is_valid_python(self):
        _get_ast(CLASSIFIER_LIB)  # Raises SyntaxError if invalid

    def test_classifier_tests_exist(self):
        assert CLASSIFIER_TESTS.exists(), f"Missing: {CLASSIFIER_TESTS}"


# ============================================================
# Classifier API signature
# ============================================================


@pytest.mark.genai
class TestClassifierAPISignature:
    """Classifier must export required types and functions."""

    def test_has_classify_runtime_targets(self):
        tree = _get_ast(CLASSIFIER_LIB)
        funcs = _get_function_names(tree)
        assert "classify_runtime_targets" in funcs

    def test_has_runtime_verification_plan(self):
        tree = _get_ast(CLASSIFIER_LIB)
        classes = _get_class_names(tree)
        assert "RuntimeVerificationPlan" in classes

    def test_has_frontend_target(self):
        tree = _get_ast(CLASSIFIER_LIB)
        classes = _get_class_names(tree)
        assert "FrontendTarget" in classes

    def test_has_api_target(self):
        tree = _get_ast(CLASSIFIER_LIB)
        classes = _get_class_names(tree)
        assert "ApiTarget" in classes

    def test_has_cli_target(self):
        tree = _get_ast(CLASSIFIER_LIB)
        classes = _get_class_names(tree)
        assert "CliTarget" in classes

    def test_has_frontend_detection(self):
        tree = _get_ast(CLASSIFIER_LIB)
        funcs = _get_function_names(tree)
        assert "_detect_frontend_targets" in funcs

    def test_has_api_detection(self):
        tree = _get_ast(CLASSIFIER_LIB)
        funcs = _get_function_names(tree)
        assert "_detect_api_targets" in funcs

    def test_has_cli_detection(self):
        tree = _get_ast(CLASSIFIER_LIB)
        funcs = _get_function_names(tree)
        assert "_detect_cli_targets" in funcs


# ============================================================
# Reviewer runtime instructions
# ============================================================


@pytest.mark.genai
class TestReviewerHasRuntimeInstructions:
    """reviewer.md must contain runtime verification instructions."""

    def test_mentions_runtime_verification(self):
        content = REVIEWER_MD.read_text()
        assert "Runtime Verification" in content

    def test_mentions_playwright(self):
        content = REVIEWER_MD.read_text()
        assert "Playwright" in content or "playwright" in content

    def test_mentions_curl(self):
        content = REVIEWER_MD.read_text()
        assert "curl" in content

    def test_mentions_timeout(self):
        content = REVIEWER_MD.read_text()
        assert "timeout" in content.lower()

    def test_gates_behind_static_review(self):
        content = REVIEWER_MD.read_text()
        assert "BLOCKING" in content
        # Must mention that runtime verification only runs after static review passes
        assert "static" in content.lower() or "BLOCKING findings" in content

    def test_warning_severity(self):
        content = REVIEWER_MD.read_text()
        # Runtime findings must be WARNING, never BLOCKING
        assert "WARNING" in content


# ============================================================
# implement.md mentions runtime
# ============================================================


@pytest.mark.genai
class TestImplementMdMentionsRuntime:
    """implement.md must reference runtime verification."""

    def test_mentions_runtime_verification(self):
        content = IMPLEMENT_MD.read_text()
        assert "runtime verification" in content.lower() or "Runtime Verification" in content

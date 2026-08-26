"""Acceptance tests for: Automated reviewer improvement loop.

Structural assertions (no LLM calls required) validating that the
improvement loop components exist and are properly wired.

GitHub Issue: #578
"""

import ast
import json
import sys
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

# Paths to files under test
BENCHMARK_HISTORY_LIB = PROJECT_ROOT / "plugins/autonomous-dev/lib/benchmark_history.py"
WEAKNESS_ANALYZER_LIB = (
    PROJECT_ROOT / "plugins/autonomous-dev/lib/reviewer_weakness_analyzer.py"
)
IMPROVE_SCRIPT = PROJECT_ROOT / "scripts/improve_reviewer.py"
RUNNER_SCRIPT = PROJECT_ROOT / "scripts/run_reviewer_benchmark.py"
REVIEWER_MD = PROJECT_ROOT / "plugins/autonomous-dev/agents/reviewer.md"
IMPLEMENTER_MD = PROJECT_ROOT / "plugins/autonomous-dev/agents/implementer.md"
TAXONOMY_PATH = PROJECT_ROOT / "tests/benchmarks/reviewer/taxonomy.json"


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
# File existence tests
# ============================================================


@pytest.mark.genai
class TestFileExistence:
    """All improvement loop files must exist."""

    def test_benchmark_history_exists(self):
        assert BENCHMARK_HISTORY_LIB.exists(), f"Missing: {BENCHMARK_HISTORY_LIB}"

    def test_weakness_analyzer_exists(self):
        assert WEAKNESS_ANALYZER_LIB.exists(), f"Missing: {WEAKNESS_ANALYZER_LIB}"

    def test_improve_script_exists(self):
        assert IMPROVE_SCRIPT.exists(), f"Missing: {IMPROVE_SCRIPT}"

    def test_runner_script_exists(self):
        assert RUNNER_SCRIPT.exists(), f"Missing: {RUNNER_SCRIPT}"

    def test_reviewer_md_exists(self):
        assert REVIEWER_MD.exists(), f"Missing: {REVIEWER_MD}"

    def test_implementer_md_exists(self):
        assert IMPLEMENTER_MD.exists(), f"Missing: {IMPLEMENTER_MD}"


# ============================================================
# benchmark_history.py structure tests
# ============================================================


@pytest.mark.genai
class TestBenchmarkHistoryStructure:
    """benchmark_history.py must export required classes and functions."""

    def test_has_benchmark_history_class(self):
        tree = _get_ast(BENCHMARK_HISTORY_LIB)
        classes = _get_class_names(tree)
        assert "BenchmarkHistory" in classes

    def test_has_append_method(self):
        source = BENCHMARK_HISTORY_LIB.read_text()
        assert "def append(" in source

    def test_has_load_all_method(self):
        source = BENCHMARK_HISTORY_LIB.read_text()
        assert "def load_all(" in source

    def test_has_load_latest_method(self):
        source = BENCHMARK_HISTORY_LIB.read_text()
        assert "def load_latest(" in source

    def test_has_trend_method(self):
        source = BENCHMARK_HISTORY_LIB.read_text()
        assert "def trend(" in source

    def test_has_compute_prompt_hash(self):
        tree = _get_ast(BENCHMARK_HISTORY_LIB)
        funcs = _get_function_names(tree)
        assert "compute_prompt_hash" in funcs


# ============================================================
# reviewer_weakness_analyzer.py structure tests
# ============================================================


@pytest.mark.genai
class TestWeaknessAnalyzerStructure:
    """reviewer_weakness_analyzer.py must export required types and functions."""

    def test_has_weakness_item_class(self):
        tree = _get_ast(WEAKNESS_ANALYZER_LIB)
        classes = _get_class_names(tree)
        assert "WeaknessItem" in classes

    def test_has_weakness_report_class(self):
        tree = _get_ast(WEAKNESS_ANALYZER_LIB)
        classes = _get_class_names(tree)
        assert "WeaknessReport" in classes

    def test_has_analyze_weaknesses_function(self):
        tree = _get_ast(WEAKNESS_ANALYZER_LIB)
        funcs = _get_function_names(tree)
        assert "analyze_weaknesses" in funcs

    def test_has_generate_improvement_instructions(self):
        tree = _get_ast(WEAKNESS_ANALYZER_LIB)
        funcs = _get_function_names(tree)
        assert "generate_improvement_instructions" in funcs

    def test_has_model_failure_weights(self):
        source = WEAKNESS_ANALYZER_LIB.read_text()
        assert "MODEL_FAILURE_WEIGHTS" in source

    def test_failure_weights_include_key_groups(self):
        source = WEAKNESS_ANALYZER_LIB.read_text()
        for group in ["silent-failure", "concurrency", "cross-path-parity", "security"]:
            assert group in source, f"MODEL_FAILURE_WEIGHTS missing group: {group}"


# ============================================================
# improve_reviewer.py structure tests
# ============================================================


@pytest.mark.genai
class TestImproveScriptStructure:
    """improve_reviewer.py must have required functions and CLI arguments."""

    def test_has_main_function(self):
        tree = _get_ast(IMPROVE_SCRIPT)
        funcs = _get_function_names(tree)
        assert "main" in funcs

    def test_has_check_regression_function(self):
        tree = _get_ast(IMPROVE_SCRIPT)
        funcs = _get_function_names(tree)
        assert "check_regression" in funcs

    def test_has_apply_improvement_function(self):
        tree = _get_ast(IMPROVE_SCRIPT)
        funcs = _get_function_names(tree)
        assert "apply_improvement" in funcs

    def test_has_revert_reviewer_function(self):
        tree = _get_ast(IMPROVE_SCRIPT)
        funcs = _get_function_names(tree)
        assert "revert_reviewer" in funcs

    def test_supports_dry_run_flag(self):
        source = IMPROVE_SCRIPT.read_text()
        assert "--dry-run" in source

    def test_supports_no_commit_flag(self):
        source = IMPROVE_SCRIPT.read_text()
        assert "--no-commit" in source

    def test_supports_history_flag(self):
        source = IMPROVE_SCRIPT.read_text()
        assert "--history" in source

    def test_supports_threshold_flag(self):
        source = IMPROVE_SCRIPT.read_text()
        assert "--threshold" in source

    def test_supports_max_instructions_flag(self):
        source = IMPROVE_SCRIPT.read_text()
        assert "--max-instructions" in source


# ============================================================
# run_reviewer_benchmark.py history integration
# ============================================================


@pytest.mark.genai
class TestRunnerHistoryIntegration:
    """run_reviewer_benchmark.py must support --history flag."""

    def test_runner_has_history_flag(self):
        source = RUNNER_SCRIPT.read_text()
        assert "--history" in source

    def test_runner_imports_benchmark_history(self):
        source = RUNNER_SCRIPT.read_text()
        assert "benchmark_history" in source or "BenchmarkHistory" in source


# ============================================================
# reviewer.md section tests
# ============================================================


@pytest.mark.genai
class TestReviewerMdSections:
    """reviewer.md must contain required sections for improvement loop."""

    def test_has_evaluation_criteria_section(self):
        content = REVIEWER_MD.read_text()
        assert "## Evaluation Criteria" in content

    def test_has_learned_patterns_section(self):
        content = REVIEWER_MD.read_text()
        assert "## Learned Patterns" in content

    def test_learned_patterns_mentions_improve_script(self):
        content = REVIEWER_MD.read_text()
        assert "improve_reviewer.py" in content

    def test_evaluation_criteria_covers_key_groups(self):
        content = REVIEWER_MD.read_text()
        for group in ["Functionality", "Security", "Testing", "Silent Failure", "Concurrency", "Wiring"]:
            assert group in content, f"Evaluation Criteria missing group: {group}"


# ============================================================
# implementer.md section tests
# ============================================================


@pytest.mark.genai
class TestImplementerMdSections:
    """implementer.md must contain quality criteria section."""

    def test_has_quality_criteria_section(self):
        content = IMPLEMENTER_MD.read_text()
        assert "## Quality Criteria" in content

    def test_quality_criteria_covers_key_areas(self):
        content = IMPLEMENTER_MD.read_text()
        for area in ["Functionality", "Security", "Testing", "Wiring"]:
            assert area in content, f"Quality Criteria missing area: {area}"

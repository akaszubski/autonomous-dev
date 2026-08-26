"""Acceptance tests for: Runtime Data Aggregator (Issue #579, Component 1).

Structural assertions (no LLM calls required) validating that the
runtime data aggregator module exists, has correct API surface, and
integrates with existing infrastructure.

GitHub Issue: #579
"""

import ast
import json
import sys
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

# Paths to files under test
AGGREGATOR_LIB = PROJECT_ROOT / "plugins/autonomous-dev/lib/runtime_data_aggregator.py"
AGGREGATOR_TESTS = PROJECT_ROOT / "tests/unit/lib/test_runtime_data_aggregator.py"
BENCHMARK_HISTORY_LIB = PROJECT_ROOT / "plugins/autonomous-dev/lib/benchmark_history.py"
KNOWN_BYPASS_CONFIG = PROJECT_ROOT / "plugins/autonomous-dev/config/known_bypass_patterns.json"


def _get_ast(path: Path) -> ast.Module:
    """Parse a Python file into an AST."""
    return ast.parse(path.read_text())


def _get_function_names(tree: ast.Module) -> list:
    """Extract top-level function names from AST."""
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def _get_class_names(tree: ast.Module) -> list:
    """Extract class names from AST."""
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


class TestAggregatorModuleExists:
    """The runtime_data_aggregator.py module must exist and be parseable."""

    def test_module_file_exists(self):
        assert AGGREGATOR_LIB.exists(), (
            f"runtime_data_aggregator.py not found at {AGGREGATOR_LIB}"
        )

    def test_module_is_valid_python(self):
        tree = _get_ast(AGGREGATOR_LIB)
        assert isinstance(tree, ast.Module)

    def test_unit_tests_exist(self):
        assert AGGREGATOR_TESTS.exists(), (
            f"Unit tests not found at {AGGREGATOR_TESTS}"
        )


class TestAggregatorAPISignature:
    """The aggregator must expose the required public API."""

    def test_has_aggregate_function(self):
        tree = _get_ast(AGGREGATOR_LIB)
        funcs = _get_function_names(tree)
        assert "aggregate" in funcs, (
            "Missing aggregate() — main entry point for data aggregation"
        )

    def test_has_all_four_collectors(self):
        tree = _get_ast(AGGREGATOR_LIB)
        funcs = _get_function_names(tree)
        expected = [
            "collect_session_signals",
            "collect_benchmark_signals",
            "collect_ci_signals",
            "collect_github_signals",
        ]
        for name in expected:
            assert name in funcs, f"Missing collector function: {name}"

    def test_has_dataclass_types(self):
        tree = _get_ast(AGGREGATOR_LIB)
        classes = _get_class_names(tree)
        expected = ["AggregatedSignal", "SourceHealth", "AggregatedReport"]
        for name in expected:
            assert name in classes, f"Missing dataclass: {name}"

    def test_has_priority_computation(self):
        tree = _get_ast(AGGREGATOR_LIB)
        funcs = _get_function_names(tree)
        assert "compute_priority" in funcs, (
            "Missing compute_priority() — ranking formula implementation"
        )

    def test_has_persist_report(self):
        tree = _get_ast(AGGREGATOR_LIB)
        funcs = _get_function_names(tree)
        assert "persist_report" in funcs, (
            "Missing persist_report() — JSONL output persistence"
        )


class TestAggregatorSecurityProperties:
    """Security properties required by OWASP and research findings."""

    def test_no_shell_true_in_subprocess(self):
        """subprocess calls must not use shell=True (injection risk)."""
        source = AGGREGATOR_LIB.read_text()
        assert "shell=True" not in source, (
            "subprocess calls must use shell=False (no shell=True)"
        )

    def test_has_secret_scrubbing(self):
        """Module must scrub secrets from log content."""
        source = AGGREGATOR_LIB.read_text()
        assert "REDACTED" in source or "redact" in source.lower() or "secret" in source.lower(), (
            "No secret scrubbing detected — log content may expose API keys"
        )

    def test_has_line_cap(self):
        """Session log reading must be capped to prevent OOM."""
        source = AGGREGATOR_LIB.read_text()
        assert "100000" in source or "100_000" in source or "MAX_LINES" in source, (
            "No line cap detected — session log reading could cause OOM"
        )


class TestAggregatorIntegrationPoints:
    """The aggregator must integrate with existing infrastructure."""

    def test_known_bypass_patterns_exist(self):
        """CI signal collector depends on known_bypass_patterns.json."""
        assert KNOWN_BYPASS_CONFIG.exists(), (
            f"known_bypass_patterns.json not found at {KNOWN_BYPASS_CONFIG}"
        )

    def test_benchmark_history_exists(self):
        """Benchmark signal collector depends on benchmark_history.py."""
        assert BENCHMARK_HISTORY_LIB.exists(), (
            f"benchmark_history.py not found at {BENCHMARK_HISTORY_LIB}"
        )

    def test_aggregator_references_benchmark_history(self):
        """The aggregator must import or reference benchmark_history."""
        source = AGGREGATOR_LIB.read_text()
        assert "benchmark_history" in source or "BenchmarkHistory" in source, (
            "Aggregator does not reference benchmark_history — "
            "benchmark signal collector is missing"
        )

    def test_aggregator_references_bypass_patterns(self):
        """The aggregator must reference known_bypass_patterns for CI signals."""
        source = AGGREGATOR_LIB.read_text()
        assert "known_bypass_patterns" in source or "bypass_pattern" in source.lower(), (
            "Aggregator does not reference bypass patterns — "
            "CI signal collector is missing"
        )


class TestAggregatorOutputFormat:
    """The aggregated report must follow project conventions."""

    def test_report_has_source_health(self):
        """AggregatedReport must include source health reporting."""
        source = AGGREGATOR_LIB.read_text()
        assert "source_health" in source, (
            "No source_health field — report won't indicate which sources succeeded/failed"
        )

    def test_report_has_window_fields(self):
        """AggregatedReport must include time window boundaries."""
        source = AGGREGATOR_LIB.read_text()
        assert "window_start" in source and "window_end" in source, (
            "Missing window_start/window_end — report needs time boundary context"
        )

    def test_jsonl_persistence_pattern(self):
        """Reports should be persisted as JSONL (append-only)."""
        source = AGGREGATOR_LIB.read_text()
        # Check for JSONL append pattern
        assert "jsonl" in source.lower() or ('"a"' in source or "'a'" in source), (
            "No JSONL append pattern detected — reports should persist as append-only JSONL"
        )

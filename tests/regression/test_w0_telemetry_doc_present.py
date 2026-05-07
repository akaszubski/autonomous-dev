"""Regression: docs/research/W0_TELEMETRY.md must exist and document W0 schema (Issue #1012).

Guards against accidental removal/breaking-edit of the W0 telemetry doc.
The doc is the contract surface for the W0 baseline publisher (#1022)
and operators consulting `scripts/hook_perf_report.py` output.
"""

from __future__ import annotations

from pathlib import Path

# tests/regression/ → tests/ → repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "research" / "W0_TELEMETRY.md"


def test_doc_exists_and_documents_schema_and_report_query():
    """The doc exists and covers schema, report query, and rollback."""
    assert DOC_PATH.exists(), f"missing W0 telemetry doc at {DOC_PATH}"

    content = DOC_PATH.read_text()

    # Must mention "schema" prominently.
    assert "## 1. Schema" in content or "# Schema" in content, (
        "doc must include a Schema section"
    )

    # Must reference the report script consumers will run.
    assert "scripts/hook_perf_report.py" in content, (
        "doc must reference scripts/hook_perf_report.py"
    )

    # Must list every required schema field.
    for field in ["ts", "hook", "dur_ns", "decision_shape", "schema_version"]:
        assert f"`{field}`" in content, f"doc missing schema field {field!r}"

    # Must document the rollback switch.
    assert "HOOK_TIMING_DISABLED" in content, (
        "doc must document HOOK_TIMING_DISABLED rollback switch"
    )

    # Must document schema version forward-compat note.
    assert "schema_version" in content


def test_doc_lists_decision_shapes():
    """Decision-shape values must be documented for downstream readers."""
    content = DOC_PATH.read_text()
    for shape in ["allow", "tuple", "dict", "exit2", "exception"]:
        assert f"`{shape}`" in content, (
            f"doc missing decision_shape value {shape!r}"
        )


def test_doc_documents_log_path():
    """The on-disk path must be documented so operators know where to look."""
    content = DOC_PATH.read_text()
    assert "~/.claude/logs/hook_timings_" in content, (
        "doc must document the canonical log file path"
    )


def test_doc_documents_perf_contract():
    """Performance budget is part of the public contract."""
    content = DOC_PATH.read_text()
    # Must mention the p50/p99 budgets.
    assert "p50" in content
    assert "p99" in content
    # Must specify the budget numbers.
    assert "1 ms" in content or "1ms" in content
    assert "5 ms" in content or "5ms" in content

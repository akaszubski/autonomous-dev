"""Spec-blind validation tests for Issue #1098 — periodic doc drift sweep.

Written from acceptance criteria ONLY, without reading implementer code/internals.

Feature: GitHub issue #1098 — first concrete instance of the periodic-aggregation
pattern. /refactor --docs sweeps every narrative documentation file in the repo
against actual code/component state, identifies drift across the full repo, and
either applies fixes in place or emits a ranked work queue.

Acceptance criteria (verbatim):
    1. /refactor --docs (or equivalent skill) invocation produces a deterministic
       drift report for the entire repo.
    2. Output is either (a) a list of file paths with line-level drift descriptions,
       or (b) an in-place doc-fix commit when fixes are mechanical.
    3. Idempotent — running twice with no changes between produces identical output.
    4. Documented in docs/COMMANDS.md (or equivalent) with at least one usage example.
    5. Structural test asserts the command/flag exists.
    6. Integration test verifies drift detection on a fixture with seeded drift.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
REFACTOR_CMD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "refactor.md"
INTEGRATION_TEST = REPO_ROOT / "tests" / "integration" / "test_refactor_docs_drift.py"

# Inject lib dir so we can import the public module surface only.
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

# Public API surface only (allowed for import).
from doc_drift_detector import detect_doc_drift  # type: ignore  # noqa: E402


def _seed_repo_with_drift(repo: Path) -> Path:
    """Create a synthetic repo with a covers-frontmatter doc that drifts from reality.

    The doc *claims* there are 99 agents while only one agent file exists on disk.
    This is a generic, universally-recognizable drift signal — a documented count
    that does not match the discoverable count of the entity it covers.
    """
    # A real component the doc could possibly "cover"
    agents_dir = repo / "plugins" / "autonomous-dev" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "implementer.md").write_text("# implementer\n")

    # Narrative doc claiming a stale count
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    doc = docs_dir / "ARCHITECTURE.md"
    doc.write_text(
        "---\n"
        "covers:\n"
        "  - plugins/autonomous-dev/agents/\n"
        "---\n"
        "# Architecture\n"
        "\n"
        "The system has 99 agents.\n"  # blatantly drifted vs 1 file on disk
    )
    return doc


# ---------------------------------------------------------------------------
# AC1 — deterministic drift report for the entire repo
# ---------------------------------------------------------------------------
def test_spec_1098_ac1_returns_deterministic_collection(tmp_path):
    """AC1: detect_doc_drift returns a deterministic, iterable collection."""
    _seed_repo_with_drift(tmp_path)

    result_a = detect_doc_drift(tmp_path)
    result_b = detect_doc_drift(tmp_path)

    # Must be a concrete collection (list / tuple), not a one-shot generator.
    assert hasattr(result_a, "__len__"), "drift report must be a sized collection"
    assert hasattr(result_a, "__iter__"), "drift report must be iterable"

    # Two invocations on identical state must produce equal collections.
    list_a = list(result_a)
    list_b = list(result_b)
    assert len(list_a) == len(list_b), "non-deterministic length between runs"


# ---------------------------------------------------------------------------
# AC2 — each finding describes path + line/description + drift type/category
# ---------------------------------------------------------------------------
def _finding_to_dict(finding) -> dict:
    """Coerce a finding to a dict via dataclass / __dict__ / mapping."""
    if isinstance(finding, dict):
        return finding
    if is_dataclass(finding):
        return asdict(finding)
    if hasattr(finding, "__dict__"):
        return {k: v for k, v in vars(finding).items() if not k.startswith("_")}
    raise AssertionError(f"finding is not coercible to dict: {type(finding)!r}")


def test_spec_1098_ac2_each_finding_has_path_line_and_category(tmp_path):
    """AC2: each finding carries (a) a path, (b) a line/description, (c) drift type."""
    _seed_repo_with_drift(tmp_path)
    findings = list(detect_doc_drift(tmp_path))
    assert findings, "expected at least one drift finding for the seeded fixture"

    for f in findings:
        d = _finding_to_dict(f)
        keys = {k.lower() for k in d.keys()}

        # (a) path-like field
        path_like = {"path", "file", "doc", "doc_path", "file_path", "source"}
        assert keys & path_like, f"finding missing path-like field: {d!r}"

        # (b) line number OR human-readable description/message
        line_like = {"line", "line_number", "lineno", "location"}
        desc_like = {"description", "message", "detail", "details", "drift", "summary"}
        assert (keys & line_like) or (keys & desc_like), (
            f"finding missing line# or description: {d!r}"
        )

        # (c) drift type / category
        type_like = {"type", "category", "kind", "drift_type", "rule"}
        assert keys & type_like, f"finding missing drift type/category: {d!r}"


# ---------------------------------------------------------------------------
# AC3 — idempotent: two runs with no changes produce identical output
# ---------------------------------------------------------------------------
def _normalize_for_serialize(obj):
    """Best-effort normalization so findings can be JSON-serialized for comparison."""
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): _normalize_for_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_normalize_for_serialize(x) for x in obj]
    if is_dataclass(obj):
        return _normalize_for_serialize(asdict(obj))
    if hasattr(obj, "__dict__"):
        return _normalize_for_serialize(
            {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        )
    return repr(obj)


def test_spec_1098_ac3_idempotent_two_runs_byte_identical(tmp_path):
    """AC3: serializing two consecutive runs yields byte-identical JSON."""
    _seed_repo_with_drift(tmp_path)

    findings_a = list(detect_doc_drift(tmp_path))
    findings_b = list(detect_doc_drift(tmp_path))

    serialized_a = json.dumps(
        _normalize_for_serialize(findings_a), sort_keys=True
    ).encode("utf-8")
    serialized_b = json.dumps(
        _normalize_for_serialize(findings_b), sort_keys=True
    ).encode("utf-8")

    assert serialized_a == serialized_b, (
        "two runs on identical input produced different output (not idempotent)"
    )


# ---------------------------------------------------------------------------
# AC4 — documented with at least one usage example
# ---------------------------------------------------------------------------
def test_spec_1098_ac4_refactor_md_documents_docs_flag_with_example():
    """AC4: refactor.md mentions --docs AND has at least one usage example."""
    assert REFACTOR_CMD.exists(), f"missing command doc: {REFACTOR_CMD}"
    text = REFACTOR_CMD.read_text(encoding="utf-8")

    assert "--docs" in text, "refactor.md missing --docs flag mention"

    # Usage example: fenced code block, OR an Example: line, OR an invocation line.
    has_code_block = "```" in text
    has_example_label = re.search(r"(?im)^\s*example[s]?\s*:", text) is not None
    has_invocation = "/refactor --docs" in text or "refactor --docs" in text

    assert has_code_block or has_example_label or has_invocation, (
        "refactor.md does not contain a usage example "
        "(no code block, 'Example:' label, or '/refactor --docs' invocation)"
    )


# ---------------------------------------------------------------------------
# AC5 — structural test asserts the command/flag exists
# ---------------------------------------------------------------------------
def test_spec_1098_ac5_docs_flag_literal_present_in_refactor_md():
    """AC5: --docs flag literal appears in plugins/.../commands/refactor.md."""
    assert REFACTOR_CMD.exists(), f"missing command doc: {REFACTOR_CMD}"
    assert "--docs" in REFACTOR_CMD.read_text(encoding="utf-8"), (
        "refactor.md must contain the literal --docs flag"
    )


# ---------------------------------------------------------------------------
# AC6 — integration test verifies drift detection on a seeded fixture
# ---------------------------------------------------------------------------
def test_spec_1098_ac6_integration_test_passes():
    """AC6: the integration test for drift detection passes against the implementation."""
    assert INTEGRATION_TEST.exists(), f"missing integration test: {INTEGRATION_TEST}"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(INTEGRATION_TEST),
            "-v",
            "--no-cov",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"integration test failed (rc={result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

"""Integration tests for /refactor --docs drift sweep (Issue #1098).

All tests use tmp_path exclusively — no fixture directories.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

# Ensure lib is importable
_LIB_DIR = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from doc_drift_detector import detect_doc_drift


def test_seeded_drift_detected(tmp_path: Path) -> None:
    """Seeded count-mismatch in synthetic repo is detected and paths are repo-relative."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "plugins/autonomous-dev/lib").mkdir(parents=True)
    (tmp_path / "docs/LIBRARIES.md").write_text(
        "---\ncovers:\n  - plugins/autonomous-dev/lib/\n---\n"
        "# Libraries\n\nThis project has 216 libraries.\n"
    )
    for i in range(3):
        (tmp_path / f"plugins/autonomous-dev/lib/lib_{i}.py").write_text("")

    findings = detect_doc_drift(tmp_path)

    assert any(f.drift_type == "count_mismatch" for f in findings)
    assert all(not f.doc_path.startswith("/") for f in findings)


def test_idempotent_byte_identical(tmp_path: Path) -> None:
    """Same input produces byte-identical JSON serialization on two successive calls."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "plugins/autonomous-dev/lib").mkdir(parents=True)
    (tmp_path / "docs/LIBRARIES.md").write_text(
        "---\ncovers:\n  - plugins/autonomous-dev/lib/\n---\n"
        "# Libraries\n\nThis project has 216 libraries.\n"
    )
    for i in range(3):
        (tmp_path / f"plugins/autonomous-dev/lib/lib_{i}.py").write_text("")

    findings1 = detect_doc_drift(tmp_path)
    findings2 = detect_doc_drift(tmp_path)

    serialized1 = json.dumps([asdict(f) for f in findings1], sort_keys=True)
    serialized2 = json.dumps([asdict(f) for f in findings2], sort_keys=True)
    assert serialized1 == serialized2


def test_dispatcher_routes_docs_to_drift(tmp_path: Path) -> None:
    """RefactorAnalyzer.full_analysis(modes=['docs']) routes to analyze_doc_drift."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "plugins/autonomous-dev/lib").mkdir(parents=True)
    (tmp_path / "docs/LIBRARIES.md").write_text(
        "---\ncovers:\n  - plugins/autonomous-dev/lib/\n---\n"
        "# Libraries\n\nThis project has 216 libraries.\n"
    )
    for i in range(3):
        (tmp_path / f"plugins/autonomous-dev/lib/lib_{i}.py").write_text("")

    from refactor_analyzer import RefactorAnalyzer

    analyzer = RefactorAnalyzer(project_root=tmp_path)
    report = analyzer.full_analysis(modes=["docs"])

    # Should contain at least one count_mismatch finding (from doc drift)
    descriptions = [f.description for f in report.findings]
    assert any("count" in d.lower() or "libraries" in d.lower() for d in descriptions), (
        f"Expected count-mismatch finding in docs drift analysis; got: {descriptions}"
    )

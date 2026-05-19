"""Unit tests for doc_drift_detector.py (Issue #1098).

Tests the DocDriftFinding dataclass and detect_doc_drift() entry point
using fully synthetic in-memory fixtures via tmp_path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make sure lib is importable regardless of working directory
_LIB_DIR = Path(__file__).resolve().parents[3] / "plugins/autonomous-dev/lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from doc_drift_detector import DocDriftFinding, detect_doc_drift


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(
    tmp_path: Path,
    doc_text: str,
    py_files: int = 3,
    doc_name: str = "LIBRARIES.md",
) -> Path:
    """Create a minimal synthetic repo with one doc and some .py files.

    Args:
        tmp_path: pytest tmp_path fixture.
        doc_text: Full markdown content for the doc file (should include frontmatter).
        py_files: Number of .py files to create under plugins/autonomous-dev/lib/.
        doc_name: Filename for the doc.

    Returns:
        project_root (== tmp_path).
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    lib_dir = tmp_path / "plugins/autonomous-dev/lib"
    lib_dir.mkdir(parents=True)
    (docs_dir / doc_name).write_text(doc_text, encoding="utf-8")
    for i in range(py_files):
        (lib_dir / f"lib_{i}.py").write_text("", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# count_mismatch tests
# ---------------------------------------------------------------------------


def test_count_mismatch_detected(tmp_path: Path) -> None:
    """Doc claims 216 libraries but only 3 .py files exist → count_mismatch finding."""
    doc_text = (
        "---\n"
        "covers:\n"
        "  - plugins/autonomous-dev/lib/\n"
        "---\n"
        "# Libraries\n\n"
        "This project has 216 libraries.\n"
    )
    _make_repo(tmp_path, doc_text, py_files=3)
    findings = detect_doc_drift(tmp_path)

    assert len(findings) == 1
    f = findings[0]
    assert f.drift_type == "count_mismatch"
    assert f.severity == "high"  # diff=213 > 5
    assert f.auto_fixable is True
    assert not f.doc_path.startswith("/")
    assert isinstance(f.doc_path, str)


def test_count_match_no_finding(tmp_path: Path) -> None:
    """Doc claims 3 libraries and exactly 3 .py files exist → zero findings."""
    doc_text = (
        "---\n"
        "covers:\n"
        "  - plugins/autonomous-dev/lib/\n"
        "---\n"
        "# Libraries\n\n"
        "This project has 3 libraries.\n"
    )
    _make_repo(tmp_path, doc_text, py_files=3)
    findings = detect_doc_drift(tmp_path)
    assert findings == []


def test_doc_path_is_repo_relative(tmp_path: Path) -> None:
    """Regression lock: finding.doc_path is a repo-relative POSIX string, not absolute."""
    doc_text = (
        "---\n"
        "covers:\n"
        "  - plugins/autonomous-dev/lib/\n"
        "---\n"
        "# Libraries\n\n"
        "This project has 100 libraries.\n"
    )
    _make_repo(tmp_path, doc_text, py_files=3)
    findings = detect_doc_drift(tmp_path)
    assert len(findings) >= 1
    for f in findings:
        assert not f.doc_path.startswith("/"), f"doc_path should be relative, got: {f.doc_path}"
        assert isinstance(f.doc_path, str)
        # Must not contain the tmp_path prefix
        assert str(tmp_path) not in f.doc_path


def test_severity_classification(tmp_path: Path) -> None:
    """diff=1 → low, diff=3 → medium, diff=10 → high."""
    # diff=1: doc says 2, actual is 3
    doc_1 = (
        "---\ncovers:\n  - plugins/autonomous-dev/lib/\n---\n"
        "Has 2 libraries.\n"
    )
    proj_1 = tmp_path / "proj_low"
    _make_repo(proj_1, doc_1, py_files=3)
    findings_1 = detect_doc_drift(proj_1)
    assert len(findings_1) == 1
    assert findings_1[0].severity == "low"

    # diff=3: doc says 6, actual is 3
    doc_3 = (
        "---\ncovers:\n  - plugins/autonomous-dev/lib/\n---\n"
        "Has 6 libraries.\n"
    )
    proj_3 = tmp_path / "proj_medium"
    _make_repo(proj_3, doc_3, py_files=3)
    findings_3 = detect_doc_drift(proj_3)
    assert len(findings_3) == 1
    assert findings_3[0].severity == "medium"

    # diff=10: doc says 13, actual is 3
    doc_10 = (
        "---\ncovers:\n  - plugins/autonomous-dev/lib/\n---\n"
        "Has 13 libraries.\n"
    )
    proj_10 = tmp_path / "proj_high"
    _make_repo(proj_10, doc_10, py_files=3)
    findings_10 = detect_doc_drift(proj_10)
    assert len(findings_10) == 1
    assert findings_10[0].severity == "high"


def test_findings_sorted_deterministically(tmp_path: Path) -> None:
    """Same fixture run twice → identical sorted list (order-stable)."""
    doc_text = (
        "---\n"
        "covers:\n"
        "  - plugins/autonomous-dev/lib/\n"
        "---\n"
        "# Libraries\n\n"
        "This project has 100 libraries.\n"
    )
    _make_repo(tmp_path, doc_text, py_files=5)

    run1 = detect_doc_drift(tmp_path)
    run2 = detect_doc_drift(tmp_path)

    assert run1 == run2, "detect_doc_drift must be deterministic"


def test_no_covers_frontmatter_skipped(tmp_path: Path) -> None:
    """Docs without covers: frontmatter produce zero findings silently."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    lib_dir = tmp_path / "plugins/autonomous-dev/lib"
    lib_dir.mkdir(parents=True)
    # Doc with NO frontmatter
    (docs_dir / "NO_COVERS.md").write_text(
        "# No frontmatter\n\nThis doc has no covers entry.\n"
    )
    for i in range(5):
        (lib_dir / f"lib_{i}.py").write_text("")

    findings = detect_doc_drift(tmp_path)
    assert findings == []


# ---------------------------------------------------------------------------
# enumeration_drift tests
# ---------------------------------------------------------------------------


def test_enumeration_drift_detected(tmp_path: Path) -> None:
    """Doc lists items A,B,C,D,E; source has only A,B,C,D → finding for missing E."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    agents_dir = tmp_path / "plugins/autonomous-dev/agents"
    agents_dir.mkdir(parents=True)

    # Create source files A, B, C, D (.md)
    for name in ("alpha", "beta", "gamma", "delta"):
        (agents_dir / f"{name}.md").write_text(f"# {name}")

    doc_text = (
        "---\n"
        "covers:\n"
        "  - plugins/autonomous-dev/agents/\n"
        "---\n"
        "# Agents\n\n"
        "Active agents:\n\n"
        "- alpha\n"
        "- beta\n"
        "- gamma\n"
        "- delta\n"
        "- epsilon\n"
    )
    (docs_dir / "AGENTS.md").write_text(doc_text)

    findings = detect_doc_drift(tmp_path)

    enum_findings = [f for f in findings if f.drift_type == "enumeration_drift"]
    assert len(enum_findings) >= 1
    described = [f.description for f in enum_findings]
    assert any("epsilon" in d for d in described)


def test_enumeration_match_no_finding(tmp_path: Path) -> None:
    """Doc lists items that exactly match source artifacts → zero enumeration findings."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    agents_dir = tmp_path / "plugins/autonomous-dev/agents"
    agents_dir.mkdir(parents=True)

    names = ("alpha", "beta", "gamma")
    for name in names:
        (agents_dir / f"{name}.md").write_text(f"# {name}")

    doc_text = (
        "---\n"
        "covers:\n"
        "  - plugins/autonomous-dev/agents/\n"
        "---\n"
        "# Agents\n\n"
        "Active agents:\n\n"
        "- alpha\n"
        "- beta\n"
        "- gamma\n"
    )
    (docs_dir / "AGENTS.md").write_text(doc_text)

    findings = detect_doc_drift(tmp_path)
    enum_findings = [f for f in findings if f.drift_type == "enumeration_drift"]
    assert enum_findings == []

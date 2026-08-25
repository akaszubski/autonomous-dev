"""Regression guard for Issue #1668: TBD placeholders in committed reports.

Acceptance criterion (#1668):

    "A guard exists that fails when a report committed as evidence still
    contains TBD placeholders, watched both refusing a TBD report and
    permitting a populated one."

The guard is this pytest — no hook is needed. It scans repo-committed
Markdown files under ``docs/reports/`` for TBD in what looks like a
Markdown table cell (``| TBD |``). The refusal/permit arms live as
unit tests below so the mechanism is self-witnessed.

#1668 also resolves the underlying dead-mechanism cluster by DELETION
(mutmut config, runner script, and TBD baseline report were removed
before this drain — see ``docs/experiments/GOAL_2026-08-24_...`` line
132). This guard prevents the class from recurring: any future report
committed with TBD cells fails the suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TBD_CELL = re.compile(r"\|\s*TBD\s*\|", re.IGNORECASE)


def _scan_for_tbd_cells(directory: Path) -> list[Path]:
    """Return every .md under ``directory`` that contains a ``| TBD |`` cell."""

    if not directory.exists():
        return []
    hits: list[Path] = []
    for md in sorted(directory.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _TBD_CELL.search(text):
            hits.append(md)
    return hits


# ---------------------------------------------------------------------------
# Refusal arm — the guard MUST detect TBD in a table cell.
# ---------------------------------------------------------------------------
def test_scanner_refuses_tbd_cell(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text(
        "# Report\n\n"
        "| file | score |\n"
        "| ---- | ----- |\n"
        "| foo  | TBD   |\n",
        encoding="utf-8",
    )
    hits = _scan_for_tbd_cells(tmp_path)
    assert len(hits) == 1
    assert hits[0].name == "bad.md"


# ---------------------------------------------------------------------------
# Permit arm — populated cells must NOT be flagged.
# ---------------------------------------------------------------------------
def test_scanner_permits_populated_cell(tmp_path: Path) -> None:
    (tmp_path / "good.md").write_text(
        "# Report\n\n"
        "| file | score |\n"
        "| ---- | ----- |\n"
        "| foo  | 42    |\n"
        "| bar  | 87.5% |\n",
        encoding="utf-8",
    )
    assert _scan_for_tbd_cells(tmp_path) == []


def test_scanner_permits_tbd_in_prose(tmp_path: Path) -> None:
    """TBD in prose (not a table cell) must NOT trip the guard."""

    (tmp_path / "prose.md").write_text(
        "Something TBD is discussed here in prose.\n"
        "Also: TBD without pipes on either side.\n",
        encoding="utf-8",
    )
    assert _scan_for_tbd_cells(tmp_path) == []


# ---------------------------------------------------------------------------
# Repo guard — the actual enforcement. If someone commits a new TBD-laden
# report under docs/reports/, this fails and names the file.
# ---------------------------------------------------------------------------
def test_no_tbd_cells_in_repo_reports() -> None:
    reports_dir = _REPO_ROOT / "docs" / "reports"
    hits = _scan_for_tbd_cells(reports_dir)
    if hits:
        formatted = "\n".join(f"  - {p.relative_to(_REPO_ROOT)}" for p in hits)
        pytest.fail(
            "docs/reports/*.md contains TBD placeholders in table cells "
            "(dead mechanism per #1668):\n" + formatted
        )

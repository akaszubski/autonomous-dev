"""Integration: hook timing baseline summary artifacts must be committed
(Issue #1022, M1).

The two derived artifacts are produced by ``scripts/publish_hook_baseline.py``
from ``baselines/2026-05-pre-refactor.jsonl`` and committed to the repo
so they are visible at PR review time and accessible from the issue
cross-post.

Guarantees:

1. ``baselines/2026-05-pre-refactor.summary.json`` exists.
2. ``baselines/2026-05-pre-refactor.summary.md`` exists.
3. The JSON contains a ``metadata`` block with all required keys.
4. The Markdown contains the "Top-5 slowest hooks (by p95)" table.
5. The Markdown contains the "Top-5 most-blocked gates" table.
6. The Markdown contains the "Baseline policy" section.
7. The Markdown documents ``data_kind: synthetic-v0`` (AC1 reality lock).
"""

from __future__ import annotations

import json
from pathlib import Path

# tests/integration/ -> tests/ -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_JSON = REPO_ROOT / "baselines" / "2026-05-pre-refactor.summary.json"
SUMMARY_MD = REPO_ROOT / "baselines" / "2026-05-pre-refactor.summary.md"

REQUIRED_METADATA_KEYS = {
    "captured_at",
    "git_sha",
    "platform",
    "schema_version",
    "source_jsonl",
    "row_count",
    "data_kind",
}


def test_summary_json_exists() -> None:
    assert SUMMARY_JSON.exists(), (
        f"missing summary JSON at {SUMMARY_JSON}; "
        "run `python scripts/publish_hook_baseline.py "
        "--jsonl baselines/2026-05-pre-refactor.jsonl` to regenerate"
    )


def test_summary_md_exists() -> None:
    assert SUMMARY_MD.exists(), (
        f"missing summary Markdown at {SUMMARY_MD}; "
        "run `python scripts/publish_hook_baseline.py "
        "--jsonl baselines/2026-05-pre-refactor.jsonl` to regenerate"
    )


def test_summary_json_has_metadata_block_with_required_keys() -> None:
    payload = json.loads(SUMMARY_JSON.read_text())
    assert "metadata" in payload, "summary JSON missing 'metadata' block"
    metadata = payload["metadata"]
    missing = REQUIRED_METADATA_KEYS - set(metadata.keys())
    assert not missing, f"metadata missing keys: {sorted(missing)}"
    # Hooks block also required.
    assert "hooks" in payload, "summary JSON missing 'hooks' block"


def test_summary_md_contains_top5_slowest_table() -> None:
    md = SUMMARY_MD.read_text()
    assert "## Top-5 slowest hooks (by p95)" in md, "missing slowest-hooks heading"
    # The table column header must be present.
    assert "| Hook | Count | p50 ms | p95 ms | p99 ms |" in md, (
        "missing slowest-hooks table header"
    )


def test_summary_md_contains_top5_most_blocked_table() -> None:
    md = SUMMARY_MD.read_text()
    assert "## Top-5 most-blocked gates" in md, "missing most-blocked heading"
    assert "| Hook | Allow | Block | Block ratio |" in md, (
        "missing most-blocked table header"
    )


def test_summary_md_contains_baseline_policy_section() -> None:
    md = SUMMARY_MD.read_text()
    assert "## Baseline policy" in md, "missing baseline policy section"
    assert "Refresh triggers" in md
    # AC1 deferral pin.
    assert "#1022" in md


def test_summary_md_documents_synthetic_data_kind() -> None:
    """AC1 reality lock: this baseline is synthetic-v0, NOT a real-workday capture."""
    md = SUMMARY_MD.read_text()
    assert "synthetic-v0" in md, (
        "summary markdown must document data_kind=synthetic-v0 — "
        "this baseline does NOT satisfy AC1 of #1022"
    )
    json_payload = json.loads(SUMMARY_JSON.read_text())
    assert json_payload["metadata"].get("data_kind") == "synthetic-v0", (
        "summary JSON metadata.data_kind must equal 'synthetic-v0'"
    )

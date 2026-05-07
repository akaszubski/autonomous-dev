"""Unit tests for scripts/publish_hook_baseline.py (Issue #1022, M1).

Covers:

- Metadata extraction (timestamp, git SHA, data_kind classification).
- Markdown rendering (Top-5 slowest, Top-5 most-blocked, headers).
- Comment rendering + truncation under GitHub's 65k limit.
- gh CLI invocation: list args (no shell), idempotent sentinel lookup.
- CLI argument validation (issue number, missing JSONL).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

# Make scripts/ importable.
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import publish_hook_baseline as phb  # noqa: E402


# --- Fixtures ----------------------------------------------------------------


def _row(
    *,
    ts: str = "2026-05-07T15:00:00+00:00",
    hook: str = "auto_fix_docs.py",
    dur_ns: int = 1_000_000,
    decision_shape: str = "allow",
) -> dict:
    return {
        "ts": ts,
        "hook": hook,
        "dur_ns": dur_ns,
        "decision_shape": decision_shape,
        "schema_version": 1,
    }


@pytest.fixture
def synthetic_jsonl(tmp_path: Path) -> Path:
    """Tiny JSONL — 3 rows, single hook, all allow."""
    path = tmp_path / "test.jsonl"
    rows = [
        _row(ts="2026-05-07T15:00:00+00:00", dur_ns=1_000_000),
        _row(ts="2026-05-07T15:00:01+00:00", dur_ns=2_000_000),
        _row(ts="2026-05-07T15:00:02+00:00", dur_ns=3_000_000),
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def multi_hook_jsonl(tmp_path: Path) -> Path:
    """Multi-hook JSONL with mixed decision shapes for table tests."""
    path = tmp_path / "multi.jsonl"
    rows = []
    # Hook A — fast, all allow (10 rows).
    for i in range(10):
        rows.append(_row(hook="hook_a.py", dur_ns=100_000 + i * 1000))
    # Hook B — slow, all allow (10 rows).
    for i in range(10):
        rows.append(_row(hook="hook_b.py", dur_ns=50_000_000 + i * 1_000_000))
    # Hook C — half-block (10 rows: 5 allow, 5 dict-blocks).
    for i in range(5):
        rows.append(_row(hook="hook_c.py", dur_ns=2_000_000, decision_shape="allow"))
    for i in range(5):
        rows.append(_row(hook="hook_c.py", dur_ns=2_000_000, decision_shape="dict"))
    # Hook D — all-block (5 rows, tuple shape).
    for i in range(5):
        rows.append(_row(hook="hook_d.py", dur_ns=1_500_000, decision_shape="tuple"))
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


# --- Test 1: metadata captured_at = earliest row timestamp -------------------


class TestBuildMetadata:
    def test_build_metadata_extracts_iso_timestamp_from_earliest_row(
        self, synthetic_jsonl: Path
    ) -> None:
        meta = phb.build_metadata(synthetic_jsonl)
        # The earliest row timestamp should be captured_at.
        assert meta["captured_at"] == "2026-05-07T15:00:00+00:00"

    def test_build_metadata_includes_git_sha_when_in_repo(
        self, synthetic_jsonl: Path
    ) -> None:
        meta = phb.build_metadata(synthetic_jsonl)
        # Either a real short SHA or "unknown" — type check is the contract.
        assert isinstance(meta["git_sha"], str)
        assert len(meta["git_sha"]) >= 1

    def test_build_metadata_marks_synthetic_data_kind_when_under_threshold(
        self, synthetic_jsonl: Path
    ) -> None:
        meta = phb.build_metadata(synthetic_jsonl)
        # 3 rows < 500 threshold -> synthetic-v0.
        assert meta["data_kind"] == "synthetic-v0"

    def test_build_metadata_includes_required_keys(self, synthetic_jsonl: Path) -> None:
        meta = phb.build_metadata(synthetic_jsonl)
        required = {
            "captured_at",
            "generated_at",
            "git_sha",
            "platform",
            "schema_version",
            "source_jsonl",
            "row_count",
            "data_kind",
        }
        assert required.issubset(meta.keys())

    def test_build_metadata_raises_on_missing_jsonl(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            phb.build_metadata(tmp_path / "does-not-exist.jsonl")


# --- Test 2: markdown rendering ---------------------------------------------


class TestRenderSummaryMarkdown:
    def test_render_summary_markdown_top5_slowest_table_renders(
        self, multi_hook_jsonl: Path
    ) -> None:
        meta = phb.build_metadata(multi_hook_jsonl)
        stats = phb.aggregate_jsonl(multi_hook_jsonl)
        md = phb.render_summary_markdown(stats, meta, top=5)

        assert "## Top-5 slowest hooks (by p95)" in md
        assert "| Hook | Count | p50 ms | p95 ms | p99 ms |" in md
        # The slowest hook (hook_b) must appear in the table.
        assert "hook_b.py" in md

    def test_render_summary_markdown_top5_most_blocked_table_renders(
        self, multi_hook_jsonl: Path
    ) -> None:
        meta = phb.build_metadata(multi_hook_jsonl)
        stats = phb.aggregate_jsonl(multi_hook_jsonl)
        md = phb.render_summary_markdown(stats, meta, top=5)

        assert "## Top-5 most-blocked gates (by block ratio)" in md
        assert "| Hook | Allow | Block | Block ratio |" in md
        # hook_d (all-block) should top the most-blocked table.
        block_section = md.split("## Top-5 most-blocked gates")[1]
        assert "hook_d.py" in block_section

    def test_render_summary_markdown_includes_metadata_header_block(
        self, synthetic_jsonl: Path
    ) -> None:
        meta = phb.build_metadata(synthetic_jsonl)
        stats = phb.aggregate_jsonl(synthetic_jsonl)
        md = phb.render_summary_markdown(stats, meta)

        # Metadata table header.
        assert "| Field            | Value" in md
        # Each metadata key surfaces in the table.
        for key in (
            "captured_at",
            "generated_at",
            "git_sha",
            "platform",
            "schema_version",
            "source_jsonl",
            "row_count",
            "data_kind",
        ):
            assert key in md, f"missing key {key!r} in markdown header"

    def test_render_summary_markdown_includes_baseline_policy_section(
        self, synthetic_jsonl: Path
    ) -> None:
        meta = phb.build_metadata(synthetic_jsonl)
        stats = phb.aggregate_jsonl(synthetic_jsonl)
        md = phb.render_summary_markdown(stats, meta)

        assert "## Baseline policy" in md
        # Specific refresh triggers are required.
        assert "Refresh triggers" in md
        assert "Quarterly" in md
        # AC1 deferral note explicitly mentions issue 1022.
        assert "#1022" in md


# --- Test 3: issue comment rendering + truncation ---------------------------


class TestRenderIssueComment:
    def test_render_issue_comment_under_60k_chars_round_trip(
        self, multi_hook_jsonl: Path
    ) -> None:
        meta = phb.build_metadata(multi_hook_jsonl)
        stats = phb.aggregate_jsonl(multi_hook_jsonl)
        sentinel = "<!-- hook-timing-baseline:multi -->"
        body = phb.render_issue_comment(
            stats, meta, sentinel=sentinel, artifact_url=None
        )

        assert len(body) <= phb.MAX_COMMENT_BODY_CHARS
        # Sentinel preserved (idempotency).
        assert sentinel in body

    def test_render_issue_comment_truncates_body_above_60k(
        self, multi_hook_jsonl: Path
    ) -> None:
        # Build a stats dict with hundreds of fake hooks to blow the budget.
        meta = phb.build_metadata(multi_hook_jsonl)
        bloated_stats: dict = {}
        for i in range(2000):
            bloated_stats[f"hook_padding_{i:04d}_with_a_very_long_padded_name.py"] = {
                "count": 100,
                "p50_ns": 1_000_000,
                "p95_ns": 2_000_000,
                "p99_ns": 3_000_000,
                "allow_count": 50,
                "block_count": 50,
                "block_ratio": 0.5,
                "shape_counts": {"allow": 50, "dict": 50},
            }
        sentinel = "<!-- hook-timing-baseline:huge -->"
        # top=2000 forces both ranking tables to render every padding row,
        # blowing past the 60k character budget.
        body = phb.render_issue_comment(
            bloated_stats,
            meta,
            sentinel=sentinel,
            artifact_url="https://example.com/x.md",
            top=2000,
        )

        assert len(body) <= phb.MAX_COMMENT_BODY_CHARS
        assert "truncated" in body
        assert "https://example.com/x.md" in body


# --- Test 4: find_existing_comment ------------------------------------------


class TestFindExistingComment:
    def test_find_existing_comment_locates_sentinel_when_present(self) -> None:
        sentinel = "<!-- hook-timing-baseline:test -->"
        fake_response = json.dumps(
            [
                {"id": 100, "body": "no sentinel here"},
                {"id": 200, "body": f"some body\n{sentinel}\nmore"},
                {"id": 300, "body": "another comment"},
            ]
        )
        with mock.patch.object(phb.subprocess, "run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["gh", "api"], returncode=0, stdout=fake_response, stderr=""
            )
            cid = phb.find_existing_comment(943, sentinel)
        assert cid == 200

    def test_find_existing_comment_returns_none_when_absent(self) -> None:
        sentinel = "<!-- hook-timing-baseline:test -->"
        fake_response = json.dumps([{"id": 100, "body": "irrelevant"}])
        with mock.patch.object(phb.subprocess, "run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["gh", "api"], returncode=0, stdout=fake_response, stderr=""
            )
            cid = phb.find_existing_comment(943, sentinel)
        assert cid is None

    def test_find_existing_comment_uses_list_args_no_shell(self) -> None:
        sentinel = "<!-- hook-timing-baseline:test -->"
        with mock.patch.object(phb.subprocess, "run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["gh", "api"], returncode=0, stdout="[]", stderr=""
            )
            phb.find_existing_comment(943, sentinel)
            # Called with list args.
            call_args = mock_run.call_args
            cmd = call_args.args[0] if call_args.args else call_args.kwargs.get("args")
            assert isinstance(cmd, list), "subprocess invoked with non-list cmd"
            assert cmd[0] == "gh"
            # shell must be False or unset (default False).
            assert call_args.kwargs.get("shell", False) is False
            # Timeout is set.
            assert call_args.kwargs.get("timeout") == phb.GH_TIMEOUT_SECONDS


# --- Test 5: CLI ------------------------------------------------------------


class TestMain:
    def test_main_dry_run_does_not_invoke_gh(
        self, synthetic_jsonl: Path, tmp_path: Path
    ) -> None:
        with mock.patch.object(phb.subprocess, "run") as mock_run:
            # `_git_short_sha` calls subprocess too; allow it but record.
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git"], returncode=0, stdout="abc1234\n", stderr=""
            )
            rc = phb.main([
                "--jsonl", str(synthetic_jsonl),
                "--summary-json", str(tmp_path / "out.json"),
                "--summary-md", str(tmp_path / "out.md"),
                "--quiet",
            ])
        assert rc == 0
        # Verify no `gh api` invocation occurred (only git rev-parse for SHA).
        for call in mock_run.call_args_list:
            cmd = call.args[0] if call.args else call.kwargs.get("args", [])
            if isinstance(cmd, list):
                assert cmd[0] != "gh", f"unexpected gh call in dry-run: {cmd}"

    def test_main_post_path_calls_gh_with_list_args_no_shell(
        self, synthetic_jsonl: Path, tmp_path: Path
    ) -> None:
        # Mock subprocess so no real gh / git calls happen.
        gh_calls: list[list] = []

        def fake_run(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list) and cmd and cmd[0] == "gh":
                gh_calls.append(cmd)
                # Return empty comment list for find, then a fake post id.
                if "/comments" in (cmd[-1] if cmd else "") or any(
                    "/comments" in s for s in cmd if isinstance(s, str)
                ):
                    return subprocess.CompletedProcess(
                        args=cmd, returncode=0,
                        stdout="[]" if "--paginate" in cmd else json.dumps({"id": 9999}),
                        stderr="",
                    )
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0,
                    stdout=json.dumps({"id": 9999}),
                    stderr="",
                )
            # git etc.
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="abc1234\n", stderr=""
            )

        with mock.patch.object(phb.subprocess, "run", side_effect=fake_run):
            rc = phb.main([
                "--jsonl", str(synthetic_jsonl),
                "--summary-json", str(tmp_path / "out.json"),
                "--summary-md", str(tmp_path / "out.md"),
                "--post",
                "--issue", "943",
                "--quiet",
            ])

        assert rc == 0
        assert gh_calls, "no gh CLI calls were made"
        for cmd in gh_calls:
            assert isinstance(cmd, list), "gh invoked with non-list cmd"
            # No shell metacharacters embedded as a single string.
            assert all(not (isinstance(part, str) and ";" in part) for part in cmd)

    def test_main_validates_issue_number_positive_int(
        self, synthetic_jsonl: Path, tmp_path: Path
    ) -> None:
        rc = phb.main([
            "--jsonl", str(synthetic_jsonl),
            "--summary-json", str(tmp_path / "out.json"),
            "--summary-md", str(tmp_path / "out.md"),
            "--post",
            "--issue", "-1",
            "--quiet",
        ])
        assert rc == 2

    def test_main_returns_1_on_missing_jsonl(self, tmp_path: Path) -> None:
        rc = phb.main([
            "--jsonl", str(tmp_path / "does-not-exist.jsonl"),
            "--quiet",
        ])
        assert rc == 1

    def test_main_writes_both_summary_artifacts(
        self, synthetic_jsonl: Path, tmp_path: Path
    ) -> None:
        out_json = tmp_path / "x.summary.json"
        out_md = tmp_path / "x.summary.md"
        rc = phb.main([
            "--jsonl", str(synthetic_jsonl),
            "--summary-json", str(out_json),
            "--summary-md", str(out_md),
            "--quiet",
        ])
        assert rc == 0
        assert out_json.exists()
        assert out_md.exists()
        # JSON parses cleanly.
        payload = json.loads(out_json.read_text())
        assert "metadata" in payload
        assert "hooks" in payload

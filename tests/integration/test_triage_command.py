"""Integration tests for /triage --auto-improvement.

Mocks the ``gh`` CLI via ``subprocess.run`` so we never make a network call. Tests use
the fixture at ``tests/fixtures/triage/seeded_queue.json`` for clustering verification.

GitHub Issue: #1099
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(_LIB_DIR))

import issue_triage_analyzer  # noqa: E402
import runtime_data_aggregator  # noqa: E402
from issue_triage_analyzer import (  # noqa: E402
    main,
    render_json,
    triage_auto_improvement,
)


FIXTURE_PATH = _REPO_ROOT / "tests" / "fixtures" / "triage" / "seeded_queue.json"


# =============================================================================
# Helpers
# =============================================================================


def _gh_response(issues_list) -> MagicMock:
    return MagicMock(returncode=0, stdout=json.dumps(issues_list), stderr="")


def _load_fixture():
    return json.loads(FIXTURE_PATH.read_text())


_FROZEN_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


# =============================================================================
# AC#1: Fetches all open issues via the runtime aggregator helper
# =============================================================================


class TestFetchesViaAggregator:
    def test_fetches_all_open_issues_via_fetch_helper(self):
        seeded = _load_fixture()
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.return_value = _gh_response(seeded)
            findings = triage_auto_improvement(
                repo="owner/repo", limit=50, _now=_FROZEN_NOW
            )
            assert mock_run.called
            args = mock_run.call_args.args[0]
            # Asserts the helper actually calls gh, with the auto-improvement label.
            assert "gh" in args
            assert "issue" in args
            assert "list" in args
            assert "--label" in args
            assert "auto-improvement" in args
            # Helper passed --limit through.
            assert "--limit" in args
            assert "50" in args
            # We got SOME findings back (after fp-acknowledged filter).
            assert isinstance(findings, list)
            assert len(findings) > 0


# =============================================================================
# AC#2: Output grouped by root cause with dependencies surfaced
# =============================================================================


class TestGroupedByRootCause:
    def test_output_grouped_by_root_cause_with_dependencies(self):
        seeded = _load_fixture()
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.return_value = _gh_response(seeded)
            findings = triage_auto_improvement(
                repo="owner/repo", _now=_FROZEN_NOW
            )

        tags = {f.root_cause_tag for f in findings}
        # Multiple primary tags are present. (Maintenance #108 is filtered by
        # default because it carries fp-acknowledged.)
        assert "CI" in tags
        assert "HARDENING" in tags
        assert "TRENDS" in tags
        assert "UNTAGGED" in tags
        assert "CI-warning" in tags

        # The CI mega-cluster splits into at least 2 sub-clusters.
        ci_clusters = [f for f in findings if f.root_cause_tag == "CI"]
        assert len(ci_clusters) >= 2

        # At least one cluster surfaces shared-file dependency notes.
        has_deps = any(f.dependency_notes for f in findings)
        assert has_deps, "Expected at least one cross-cluster dependency note"


# =============================================================================
# AC#3: Idempotence
# =============================================================================


class TestIdempotence:
    def test_idempotent_on_clean_queue(self):
        seeded = _load_fixture()
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.return_value = _gh_response(seeded)
            a = render_json(triage_auto_improvement(_now=_FROZEN_NOW))
            mock_run.return_value = _gh_response(seeded)
            b = render_json(triage_auto_improvement(_now=_FROZEN_NOW))
        assert a == b
        # Byte-identical also through CLI render.
        assert len(a) > 0

    def test_idempotent_on_empty_queue(self):
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.return_value = _gh_response([])
            a = triage_auto_improvement(_now=_FROZEN_NOW)
            mock_run.return_value = _gh_response([])
            b = triage_auto_improvement(_now=_FROZEN_NOW)
        assert a == [] == b


# =============================================================================
# AC#6: Clustering on seeded fixture
# =============================================================================


class TestSeededClustering:
    def test_clustering_on_seeded_fixture(self):
        seeded = _load_fixture()
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.return_value = _gh_response(seeded)
            findings = triage_auto_improvement(_now=_FROZEN_NOW)

        # Build a {(tag,sub_id): set(issue_numbers)} map.
        clusters = {
            (f.root_cause_tag, f.sub_cluster_id): set(f.issue_numbers)
            for f in findings
        }

        # CI sub-clusters: {101,102,103} (coordinator/pipeline/regression) and
        # {104,105} (hook installation settings).
        ci_clusters_sets = [
            members
            for (tag, _sid), members in clusters.items()
            if tag == "CI"
        ]
        assert {101, 102, 103} in ci_clusters_sets
        assert {104, 105} in ci_clusters_sets

        # HARDENING is a single cluster containing 106 and 111 (they share secret-
        # scrubbing tokens).
        hardening_members = [
            members for (tag, _sid), members in clusters.items() if tag == "HARDENING"
        ]
        assert hardening_members == [{106, 111}]

        # Issue 108 has fp-acknowledged and should be FILTERED by default.
        all_numbers: set[int] = set()
        for members in clusters.values():
            all_numbers.update(members)
        assert 108 not in all_numbers


class TestCIMegaclusterRegression:
    def test_ci_megacluster_splits_into_subclusters(self):
        """Regression lock: prevent regressing to tag-only clustering on real-data shape."""
        # 8 [CI] issues spanning two root causes: coordinator pipeline and hook installation.
        ci_issues = [
            {"number": i, "title": title, "body": "", "labels": [], "createdAt": "2026-05-20T00:00:00Z"}
            for i, title in enumerate(
                [
                    "[CI] coordinator pipeline regression alpha",
                    "[CI] coordinator pipeline regression beta",
                    "[CI] coordinator pipeline test failure gamma",
                    "[CI] coordinator pipeline cleanup delta",
                    "[CI] hook installation race epsilon",
                    "[CI] hook installation order zeta",
                    "[CI] hook installation conflict eta",
                    "[CI] hook installation theta failure",
                ],
                start=200,
            )
        ]
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.return_value = _gh_response(ci_issues)
            findings = triage_auto_improvement(_now=_FROZEN_NOW)
        ci_clusters = [f for f in findings if f.root_cause_tag == "CI"]
        # MUST split into >= 2 sub-clusters, not one mega-bucket.
        assert len(ci_clusters) >= 2, (
            f"CI mega-cluster did not split: got {len(ci_clusters)} sub-clusters"
        )


# =============================================================================
# fp-acknowledged behaviour
# =============================================================================


class TestFpAcknowledged:
    def test_fp_acknowledged_filtered_by_default(self):
        seeded = _load_fixture()
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.return_value = _gh_response(seeded)
            findings = triage_auto_improvement(_now=_FROZEN_NOW)
        nums = {n for f in findings for n in f.issue_numbers}
        assert 108 not in nums

    def test_fp_acknowledged_included_when_flag_set(self):
        seeded = _load_fixture()
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.return_value = _gh_response(seeded)
            findings = triage_auto_improvement(
                include_fp_acknowledged=True, _now=_FROZEN_NOW
            )
        nums = {n for f in findings for n in f.issue_numbers}
        assert 108 in nums


# =============================================================================
# gh failure handling
# =============================================================================


class TestGhFailure:
    def test_gh_unreachable_returns_empty_with_error_health(self, capsys):
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh not found")
            rc = main(["--auto-improvement"])
        captured = capsys.readouterr()
        assert rc == 2
        assert "WARN" in captured.err or "fail" in captured.err.lower()


# =============================================================================
# Refactor preserved external contract
# =============================================================================


class TestRuntimeAggregatorContractPreserved:
    def test_runtime_data_aggregator_collect_github_signals_unchanged_after_refactor(self):
        """Snapshot: collect_github_signals still yields signals with the same shape."""
        from runtime_data_aggregator import collect_github_signals

        payload = [
            {
                "number": 1,
                "title": "Improve hook error handling",
                "body": "Details...",
                "labels": [{"name": "auto-improvement"}],
                "createdAt": "2026-03-25T10:00:00Z",
            }
        ]
        with patch.object(runtime_data_aggregator.subprocess, "run") as mock_run:
            mock_run.return_value = _gh_response(payload)
            signals, health = collect_github_signals("owner/repo")
        assert len(signals) == 1
        s = signals[0]
        assert s.source == "github"
        assert s.signal_type == "github_issue"
        assert s.severity == 0.5
        assert s.frequency == 1
        assert "hook error handling" in s.description.lower()
        assert health.status == "ok"
        assert health.signal_count == 1

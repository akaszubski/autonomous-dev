"""Unit tests for the issue_triage_analyzer module.

Pure-function tests only — no I/O, no subprocess. The CLI / clustering pipeline as a
whole is covered by tests/integration/test_triage_command.py.

GitHub Issue: #1099
"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

_LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(_LIB_DIR))

from issue_triage_analyzer import (  # noqa: E402
    SEVERITY_WEIGHTS,
    STOPWORDS,
    TriageFinding,
    _infer_severity,
    _recency_decay,
    cluster_within_tag,
    compute_rank_score,
    detect_cross_cluster_dependencies,
    extract_root_cause_tag,
    extract_shared_files,
    extract_title_tokens,
    merge_by_shared_files,
)


# =============================================================================
# extract_root_cause_tag
# =============================================================================


class TestExtractRootCauseTag:
    def test_tag_present(self):
        assert extract_root_cause_tag("[CI] flaky test") == "CI"

    def test_no_tag_returns_untagged(self):
        assert extract_root_cause_tag("flaky test no bracket") == "UNTAGGED"

    def test_empty_brackets_return_untagged(self):
        # Regex requires at least one non-] char so "[]" never matches.
        assert extract_root_cause_tag("[] something") == "UNTAGGED"

    def test_preserves_inner_punctuation(self):
        assert extract_root_cause_tag("[CI-warning] soft fail") == "CI-warning"


# =============================================================================
# extract_title_tokens
# =============================================================================


class TestExtractTitleTokens:
    def test_strips_tag_and_drops_stopwords(self):
        tokens = extract_title_tokens("[CI] the flaky regression test in coordinator")
        assert "the" not in tokens
        assert "in" not in tokens
        assert "flaky" in tokens
        assert "regression" in tokens
        assert "coordinator" in tokens

    def test_drops_short_tokens(self):
        tokens = extract_title_tokens("ab cd efg hijk")
        # "ab" and "cd" length < 3, dropped. "efg" and "hijk" kept.
        assert "ab" not in tokens
        assert "cd" not in tokens
        assert "efg" in tokens
        assert "hijk" in tokens

    def test_empty_title_returns_empty(self):
        assert extract_title_tokens("") == frozenset()


# =============================================================================
# cluster_within_tag
# =============================================================================


class TestClusterWithinTag:
    def _issue(self, number: int, title: str):
        return {"number": number, "title": title}

    def test_transitivity_merges_chains(self):
        # 1<->2 share {alpha, beta}; 2<->3 share {beta, gamma}; 1<->3 only share {alpha}.
        # Union-find should still merge all three.
        issues = [
            self._issue(1, "[X] alpha beta delta"),
            self._issue(2, "[X] alpha beta gamma"),
            self._issue(3, "[X] beta gamma epsilon"),
        ]
        clusters = cluster_within_tag(issues, min_shared_tokens=2)
        assert len(clusters) == 1
        assert clusters[0] == [1, 2, 3]

    def test_unrelated_titles_stay_singleton(self):
        issues = [
            self._issue(10, "[X] foobar baz"),
            self._issue(11, "[X] qux quux corge"),
            self._issue(12, "[X] grault garply waldo"),
        ]
        clusters = cluster_within_tag(issues, min_shared_tokens=2)
        # All singletons.
        assert sorted(clusters) == [[10], [11], [12]]

    def test_deterministic_ordering(self):
        issues = [
            self._issue(5, "[X] alpha beta gamma"),
            self._issue(1, "[X] alpha beta delta"),
            self._issue(3, "[X] zeta eta theta"),
        ]
        a = cluster_within_tag(issues)
        b = cluster_within_tag(list(reversed(issues)))
        assert a == b
        # Cluster containing the lowest issue number comes first.
        assert a[0][0] <= a[-1][0]


# =============================================================================
# compute_rank_score
# =============================================================================


class TestComputeRankScore:
    def test_formula_correctness(self):
        score = compute_rank_score(cluster_size=4, severity_weight=2.0, recency_decay=0.5)
        assert score == pytest.approx(4 * 2.0 * 0.5)

    def test_signature_has_no_fix_effort_param(self):
        sig = inspect.signature(compute_rank_score)
        assert "fix_effort" not in sig.parameters
        assert set(sig.parameters) == {"cluster_size", "severity_weight", "recency_decay"}


# =============================================================================
# extract_shared_files
# =============================================================================


class TestExtractSharedFiles:
    def test_path_in_two_bodies_is_shared(self):
        bodies = [
            "Refer to plugins/autonomous-dev/lib/coordinator.py for context.",
            "Bug is in plugins/autonomous-dev/lib/coordinator.py line 200.",
            "Unrelated tests/integration/test_other.py only.",
        ]
        shared = extract_shared_files(bodies)
        assert "plugins/autonomous-dev/lib/coordinator.py" in shared
        # Single-occurrence paths excluded.
        assert "tests/integration/test_other.py" not in shared

    def test_single_body_returns_empty(self):
        bodies = ["only one body lib/foo.py"]
        assert extract_shared_files(bodies) == tuple()


# =============================================================================
# _infer_severity
# =============================================================================


class TestInferSeverity:
    def test_severity_keywords(self):
        assert _infer_severity([{"name": "security"}]) == "low"
        assert _infer_severity([{"name": "p0"}]) == "high"
        assert _infer_severity([{"name": "critical"}]) == "high"
        assert _infer_severity([{"name": "bug"}]) == "medium"
        assert _infer_severity([{"name": "regression"}]) == "medium"
        assert _infer_severity([{"name": "documentation"}]) == "low"
        assert _infer_severity([]) == "low"
        
        # Combined cases: security with actual severity labels
        assert _infer_severity([{"name": "security"}, {"name": "critical"}]) == "high"
        assert _infer_severity([{"name": "security"}, {"name": "p0"}]) == "high"


# =============================================================================
# _recency_decay
# =============================================================================


class TestRecencyDecay:
    def test_decay_at_half_life_is_half(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        created = (now - timedelta(days=30)).isoformat()
        decay = _recency_decay(created, now, half_life_days=30.0)
        assert decay == pytest.approx(0.5, abs=1e-6)

    def test_clamped_to_unit_interval(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        # Future timestamp -> age_seconds <= 0 -> returns 1.0
        future = (now + timedelta(days=1)).isoformat()
        assert _recency_decay(future, now) == 1.0
        # Malformed string -> 0.0
        assert _recency_decay("not-a-date", now) == 0.0
        # Empty string -> 0.0
        assert _recency_decay("", now) == 0.0


# =============================================================================
# detect_cross_cluster_dependencies
# =============================================================================


class TestDetectCrossClusterDependencies:
    def _finding(self, tag, sub_id, files):
        return TriageFinding(
            root_cause_tag=tag,
            sub_cluster_id=sub_id,
            issue_numbers=(1,),
            issue_titles=("dummy",),
            cluster_size=1,
            severity="low",
            rank_score=1.0,
            shared_files=tuple(files),
            dependency_notes=(),
            suggested_fix_order=0,
        )

    def test_shared_files_create_dependency(self):
        a = self._finding("CI", 1, ["lib/foo.py", "lib/bar.py"])
        b = self._finding("HARDENING", 1, ["lib/foo.py"])
        c = self._finding("DOCS", 1, ["docs/x.md"])
        deps = detect_cross_cluster_dependencies([a, b, c])
        assert deps == {
            ("CI", 1): (("HARDENING", 1),),
            ("HARDENING", 1): (("CI", 1),),
        }


# =============================================================================
# TriageFinding dataclass
# =============================================================================


class TestTriageFinding:
    def test_finding_is_frozen(self):
        f = TriageFinding(
            root_cause_tag="CI",
            sub_cluster_id=1,
            issue_numbers=(1,),
            issue_titles=("test",),
            cluster_size=1,
            severity="low",
            rank_score=1.0,
            shared_files=(),
            dependency_notes=(),
            suggested_fix_order=1,
        )
        # frozen=True so attribute assignment must raise.
        with pytest.raises(Exception):
            f.cluster_size = 99


# =============================================================================
# Constants sanity
# =============================================================================


class TestMergeBySharedFiles:
    """Tests for merge_by_shared_files function."""
    
    def _make_finding(
        self,
        tag="[lint]",
        sub_id=1,
        issue_nums=(1,),
        titles=None,
        files=(),
        rank=10.0,
        recency=1,
        severity="medium",
        cluster_size=None,
    ):
        """Helper to create TriageFinding instances for tests."""
        if titles is None:
            titles = tuple(f"Issue {num}" for num in issue_nums)
        return TriageFinding(
            root_cause_tag=tag,
            sub_cluster_id=sub_id,
            issue_numbers=tuple(issue_nums),
            issue_titles=tuple(titles),
            cluster_size=cluster_size if cluster_size is not None else len(issue_nums),
            severity=severity,
            rank_score=rank,
            shared_files=tuple(files),
            dependency_notes=(),
            suggested_fix_order=0,
        )
    
    @pytest.mark.parametrize(
        "findings, expected_cluster_count, expected_max_size, description",
        [
            # 1. No shared files -> not merged
            (
                [
                    lambda self: self._make_finding(sub_id=1, issue_nums=(1,), files=("a.py",)),
                    lambda self: self._make_finding(sub_id=2, issue_nums=(2,), files=("b.py",)),
                ],
                2,
                1,
                "no overlap",
            ),
            # 2. Shared file, combined size <= 5 -> merged
            (
                [
                    lambda self: self._make_finding(sub_id=1, issue_nums=(1,), files=("a.py",)),
                    lambda self: self._make_finding(sub_id=2, issue_nums=(2,), files=("a.py", "b.py")),
                ],
                1,
                2,
                "overlap under limit",
            ),
            # 3. Shared file but combined size > 5 -> not merged
            (
                [
                    lambda self: self._make_finding(sub_id=1, issue_nums=(1, 2, 3), files=("a.py",), cluster_size=3),
                    lambda self: self._make_finding(sub_id=2, issue_nums=(4, 5, 6), files=("a.py",), cluster_size=3),
                ],
                2,
                3,
                "exceeds size limit",
            ),
            # 4. Transitive chain A-B share, B-C share, A-C don't -> all merged
            (
                [
                    lambda self: self._make_finding(sub_id=1, issue_nums=(1,), files=("a.py",)),
                    lambda self: self._make_finding(sub_id=2, issue_nums=(2,), files=("a.py", "b.py")),
                    lambda self: self._make_finding(sub_id=3, issue_nums=(3,), files=("b.py",)),
                ],
                1,
                3,
                "transitive chain",
            ),
            # 5. Different bracket tags with shared files -> not merged
            (
                [
                    lambda self: self._make_finding(tag="[lint]", sub_id=1, issue_nums=(1,), files=("a.py",)),
                    lambda self: self._make_finding(tag="[tests]", sub_id=2, issue_nums=(2,), files=("a.py",)),
                ],
                2,
                1,
                "different tags",
            ),
        ],
    )
    def test_merge_by_shared_files(self, findings, expected_cluster_count, expected_max_size, description):
        """Test merge_by_shared_files with various scenarios."""
        # Create actual finding instances from the lambdas
        actual_findings = [f(self) for f in findings]
        
        result = merge_by_shared_files(actual_findings)
        
        assert len(result) == expected_cluster_count, f"{description}: got {len(result)} clusters, expected {expected_cluster_count}"
        assert max(f.cluster_size for f in result) == expected_max_size, f"{description}: max cluster size was {max(f.cluster_size for f in result)}, expected {expected_max_size}"
        
        # Additional checks for merged results
        if description == "overlap under limit":
            # Should have merged issues 1 and 2
            assert result[0].issue_numbers == (1, 2), f"Merged cluster should have issues (1, 2), got {result[0].issue_numbers}"
            assert set(result[0].shared_files) == {"a.py", "b.py"}, f"Merged cluster should have both files"
        
        if description == "transitive chain":
            # All three should be merged
            assert result[0].issue_numbers == (1, 2, 3), f"Transitive merge should have issues (1, 2, 3), got {result[0].issue_numbers}"
            assert set(result[0].shared_files) == {"a.py", "b.py"}, f"Transitive merge should have both files"


class TestConstants:
    def test_severity_weights_have_expected_levels(self):
        assert set(SEVERITY_WEIGHTS) == {"low", "medium", "high"}
        assert SEVERITY_WEIGHTS["low"] < SEVERITY_WEIGHTS["medium"] < SEVERITY_WEIGHTS["high"]

    def test_stopwords_includes_common_articles(self):
        assert "the" in STOPWORDS
        assert "of" in STOPWORDS
        assert "and" in STOPWORDS

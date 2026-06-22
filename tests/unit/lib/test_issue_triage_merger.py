"""Unit tests for merge_compatible_singletons() in issue_triage_analyzer.

GitHub Issue: #1250
"""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

_LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(_LIB_DIR))

from issue_triage_analyzer import TriageFinding, merge_compatible_singletons  # noqa: E402


def _make(
    tag: str,
    sub_id: int,
    numbers: tuple[int, ...],
    severity: str = "low",
    confidence: float = 0.0,
) -> TriageFinding:
    return TriageFinding(
        root_cause_tag=tag,
        sub_cluster_id=sub_id,
        issue_numbers=numbers,
        issue_titles=tuple(f"title-{n}" for n in numbers),
        cluster_size=len(numbers),
        severity=severity,
        rank_score=1.0,
        shared_files=(),
        dependency_notes=(),
        suggested_fix_order=0,
        confidence=confidence,
    )


class TestMergeCompatibleSingletons:
    def test_four_singletons_same_tag_merge_to_one_super_cluster(self):
        """4 singletons with same tag should merge into 1 super-cluster of size 4."""
        findings = [
            _make("AUTH", 1, (100,), "low"),
            _make("AUTH", 2, (101,), "low"),
            _make("AUTH", 3, (102,), "low"),
            _make("AUTH", 4, (103,), "low"),
        ]
        
        result = merge_compatible_singletons(findings, max_size=4)
        
        # Should have exactly 1 super-cluster
        assert len(result) == 1
        merged = result[0]
        
        # Verify merged properties
        assert merged.root_cause_tag == "AUTH"
        assert merged.cluster_size == 4
        assert sorted(merged.issue_numbers) == [100, 101, 102, 103]
        assert len(merged.issue_titles) == 4
        assert all(f"title-{n}" in merged.issue_titles for n in [100, 101, 102, 103])
        
        # sub_cluster_id should be a positive int (not pinning specific value)
        assert isinstance(merged.sub_cluster_id, int)
        assert merged.sub_cluster_id > 0
        
        # rank_score should be non-negative float
        assert isinstance(merged.rank_score, float)
        assert merged.rank_score >= 0.0
        
        # Placeholders should be empty
        assert merged.shared_files == ()
        assert merged.dependency_notes == ()
        assert merged.suggested_fix_order == 0

    def test_five_singletons_same_tag_chunk_to_4_plus_1(self):
        """5 singletons with same tag should chunk into 1 super of size 4 + 1 leftover singleton."""
        findings = [
            _make("CONFIG", 10, (200,), "low"),
            _make("CONFIG", 11, (201,), "medium"),
            _make("CONFIG", 12, (202,), "low"),
            _make("CONFIG", 13, (203,), "low"),
            _make("CONFIG", 14, (204,), "low"),
        ]
        
        result = merge_compatible_singletons(findings, max_size=4)
        
        # Should have 2 findings: one super-cluster of 4, one singleton
        assert len(result) == 2
        
        # Find the super-cluster (size 4) and the singleton (size 1)
        sizes = [f.cluster_size for f in result]
        assert sorted(sizes) == [1, 4]
        
        super_cluster = next(f for f in result if f.cluster_size == 4)
        singleton = next(f for f in result if f.cluster_size == 1)
        
        # Verify super-cluster
        assert super_cluster.root_cause_tag == "CONFIG"
        assert len(super_cluster.issue_numbers) == 4
        
        # Verify singleton remains
        assert singleton.root_cause_tag == "CONFIG"
        assert len(singleton.issue_numbers) == 1
        
        # All 5 issues should be accounted for
        all_issues = set(super_cluster.issue_numbers) | set(singleton.issue_numbers)
        assert all_issues == {200, 201, 202, 203, 204}

    def test_untagged_singletons_never_merge(self):
        """All UNTAGGED singletons should pass through unchanged."""
        findings = [
            _make("UNTAGGED", 20, (300,), "low"),
            _make("UNTAGGED", 21, (301,), "medium"),
            _make("UNTAGGED", 22, (302,), "high"),
            _make("UNTAGGED", 23, (303,), "low"),
        ]
        
        result = merge_compatible_singletons(findings, max_size=4)
        
        # All 4 should remain as separate singletons
        assert len(result) == 4
        
        # Each should still be a singleton
        for finding in result:
            assert finding.cluster_size == 1
            assert finding.root_cause_tag == "UNTAGGED"
        
        # All original issues should be present
        result_issues = {f.issue_numbers[0] for f in result}
        assert result_issues == {300, 301, 302, 303}

    def test_mixed_severities_aggregate(self):
        """3 singletons with same tag and different severities should aggregate to highest severity."""
        findings = [
            _make("PERF", 30, (400,), "low"),
            _make("PERF", 31, (401,), "medium"),
            _make("PERF", 32, (402,), "high"),
        ]
        
        result = merge_compatible_singletons(findings, max_size=4)
        
        # Should merge into 1 super-cluster
        assert len(result) == 1
        merged = result[0]
        
        # Severity should be the highest ("high")
        assert merged.severity == "high"
        assert merged.cluster_size == 3
        assert sorted(merged.issue_numbers) == [400, 401, 402]

    def test_empty_input_returns_empty(self):
        """Empty input should return empty list."""
        result = merge_compatible_singletons([], max_size=4)
        assert result == []

    def test_all_multi_clusters_unchanged(self):
        """Findings with cluster_size > 1 should pass through unchanged."""
        findings = [
            _make("AUTH", 40, (500, 501), "medium"),  # cluster_size=2
            _make("CONFIG", 41, (502, 503, 504), "high"),  # cluster_size=3
            _make("PERF", 42, (505, 506, 507, 508, 509), "low"),  # cluster_size=5
        ]
        
        result = merge_compatible_singletons(findings, max_size=4)
        
        # All 3 should pass through unchanged
        assert len(result) == 3
        
        # Verify each is unchanged
        for original, returned in zip(findings, result):
            assert returned.root_cause_tag == original.root_cause_tag
            assert returned.sub_cluster_id == original.sub_cluster_id
            assert returned.issue_numbers == original.issue_numbers
            assert returned.cluster_size == original.cluster_size
            assert returned.severity == original.severity

    def test_determinism(self):
        """Same input list should produce same output list across multiple calls."""
        findings = [
            _make("API", 50, (600,), "low"),
            _make("API", 51, (601,), "medium"),
            _make("DB", 52, (602,), "high"),
            _make("API", 53, (603,), "low"),
            _make("DB", 54, (604,), "medium"),
            _make("UNTAGGED", 55, (605,), "low"),
            _make("API", 56, (606,), "high"),
        ]
        
        # Call twice
        result1 = merge_compatible_singletons(findings, max_size=4)
        result2 = merge_compatible_singletons(findings, max_size=4)
        
        # Results should be identical
        assert len(result1) == len(result2)
        
        # Compare each finding (convert to comparable format)
        for f1, f2 in zip(result1, result2):
            assert f1.root_cause_tag == f2.root_cause_tag
            assert f1.cluster_size == f2.cluster_size
            assert f1.issue_numbers == f2.issue_numbers
            assert f1.severity == f2.severity
            # sub_cluster_id should also be consistent
            assert f1.sub_cluster_id == f2.sub_cluster_id

    def test_mixed_tags_and_sizes(self):
        """Mixed input with different tags, singletons, and multi-clusters."""
        findings = [
            _make("AUTH", 60, (700,), "low"),  # singleton
            _make("AUTH", 61, (701,), "medium"),  # singleton
            _make("CONFIG", 62, (702, 703), "high"),  # multi-cluster
            _make("AUTH", 63, (704,), "low"),  # singleton
            _make("UNTAGGED", 64, (705,), "medium"),  # untagged singleton
            _make("CONFIG", 65, (706,), "low"),  # singleton different tag
        ]
        
        result = merge_compatible_singletons(findings, max_size=4)
        
        # Should have:
        # - 1 merged AUTH super-cluster (3 singletons)
        # - 1 CONFIG multi-cluster (unchanged)
        # - 1 CONFIG singleton
        # - 1 UNTAGGED singleton
        assert len(result) == 4
        
        # Find AUTH super-cluster
        auth_findings = [f for f in result if f.root_cause_tag == "AUTH"]
        assert len(auth_findings) == 1
        assert auth_findings[0].cluster_size == 3
        assert sorted(auth_findings[0].issue_numbers) == [700, 701, 704]
        
        # CONFIG multi-cluster should be unchanged
        config_multi = [f for f in result if f.root_cause_tag == "CONFIG" and f.cluster_size > 1]
        assert len(config_multi) == 1
        assert config_multi[0].issue_numbers == (702, 703)
        
        # UNTAGGED should remain singleton
        untagged = [f for f in result if f.root_cause_tag == "UNTAGGED"]
        assert len(untagged) == 1
        assert untagged[0].cluster_size == 1

    def test_merged_super_cluster_propagates_max_confidence(self):
        """Regression for Issue #1291 FINDING-1: confidence must propagate via max().

        Two high-confidence singletons (confidence=0.8) with the same tag should
        produce a merged super-cluster with confidence >= 0.8. Without the fix,
        merge_compatible_singletons omitted the ``confidence`` field and the
        TriageFinding dataclass default (0.0) was used, causing confidence_gate to
        always block auto-drain for super-clusters.
        """
        findings = [
            _make("SECURITY", 70, (800,), "medium", confidence=0.8),
            _make("SECURITY", 71, (801,), "medium", confidence=0.9),
        ]

        result = merge_compatible_singletons(findings, max_size=4)

        assert len(result) == 1, "Two same-tag singletons should merge into one super-cluster"
        merged = result[0]

        assert merged.root_cause_tag == "SECURITY"
        assert merged.cluster_size == 2
        assert sorted(merged.issue_numbers) == [800, 801]
        # The critical assertion: confidence must be max(0.8, 0.9) = 0.9
        assert merged.confidence >= 0.8, (
            f"Expected merged super-cluster confidence >= 0.8, got {merged.confidence}. "
            "merge_compatible_singletons must propagate confidence via max() — "
            "see Issue #1291 FINDING-1."
        )

    def test_zero_confidence_singletons_merge_to_zero_confidence(self):
        """Zero-confidence singletons should produce a zero-confidence super-cluster.

        Ensures the aggregation is honest — we do not fabricate confidence from
        nothing. The confidence_gate will block these, which is the correct behavior.
        """
        findings = [
            _make("PERF", 80, (900,), "low", confidence=0.0),
            _make("PERF", 81, (901,), "low", confidence=0.0),
            _make("PERF", 82, (902,), "low", confidence=0.0),
        ]

        result = merge_compatible_singletons(findings, max_size=4)

        assert len(result) == 1
        merged = result[0]
        assert merged.confidence == 0.0, (
            "Three zero-confidence singletons must produce a zero-confidence super-cluster."
        )

    def test_mixed_confidence_singletons_take_max(self):
        """Three singletons with mixed confidences: result should be max value."""
        findings = [
            _make("DB", 90, (1000,), "low", confidence=0.0),
            _make("DB", 91, (1001,), "low", confidence=0.5),
            _make("DB", 92, (1002,), "low", confidence=0.85),
        ]

        result = merge_compatible_singletons(findings, max_size=4)

        assert len(result) == 1
        merged = result[0]
        assert merged.confidence == pytest.approx(0.85), (
            f"Expected max confidence 0.85, got {merged.confidence}."
        )
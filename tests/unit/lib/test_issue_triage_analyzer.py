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
    _infer_confidence,
    _infer_severity,
    _recency_decay,
    cluster_within_tag,
    compute_rank_score,
    detect_cross_cluster_dependencies,
    extract_root_cause_tag,
    extract_shared_files,
    extract_title_tokens,
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
        # Issue #1273: "security" label no longer maps to "high" (tag_gate independently blocks).
        assert _infer_severity([{"name": "security"}]) == "low"
        assert _infer_severity([{"name": "p0"}]) == "high"
        assert _infer_severity([{"name": "bug"}]) == "medium"
        assert _infer_severity([{"name": "regression"}]) == "medium"
        assert _infer_severity([{"name": "documentation"}]) == "low"
        assert _infer_severity([]) == "low"

    def test_security_only_returns_low(self):
        """security-only label no longer raises severity to high (Issue #1273)."""
        assert _infer_severity([{"name": "security"}]) == "low"

    def test_security_plus_critical_returns_high(self):
        """critical wins when combined with security."""
        assert _infer_severity([{"name": "security"}, {"name": "critical"}]) == "high"

    def test_security_plus_bug_returns_medium(self):
        """bug wins when combined with security (medium > low)."""
        assert _infer_severity([{"name": "security"}, {"name": "bug"}]) == "medium"

    def test_string_label_normalization_security(self):
        """Plain string label 'security' (not dict) still returns 'low'."""
        assert _infer_severity(["security"]) == "low"


# =============================================================================
# _infer_confidence
# =============================================================================


class TestInferConfidence:
    def test_high_keyword_gives_full_confidence(self):
        """p0 label with high severity gives confidence 1.0."""
        assert _infer_confidence([{"name": "p0"}], "high") == 1.0

    def test_medium_keyword_gives_full_confidence(self):
        """bug label with medium severity gives confidence 1.0."""
        assert _infer_confidence([{"name": "bug"}], "medium") == 1.0

    def test_low_default_gives_zero_confidence(self):
        """documentation label produces low severity → confidence 0.0."""
        assert _infer_confidence([{"name": "documentation"}], "low") == 0.0

    def test_empty_labels_gives_zero(self):
        """Empty labels always yield confidence 0.0."""
        assert _infer_confidence([], "high") == 0.0

    def test_string_labels_normalized(self):
        """Plain string labels work the same as dict labels."""
        assert _infer_confidence(["bug"], "medium") == 1.0
        assert _infer_confidence(["documentation"], "low") == 0.0

    def test_security_only_confidence_zero(self):
        """security-only produces low severity, so confidence is 0.0 (Issue #1273)."""
        assert _infer_confidence([{"name": "security"}], "low") == 0.0


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

    def test_confidence_default_and_explicit(self):
        """confidence defaults to 0.0 and can be set explicitly."""
        f_default = TriageFinding(
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
        assert f_default.confidence == 0.0

        f_explicit = TriageFinding(
            root_cause_tag="CI",
            sub_cluster_id=1,
            issue_numbers=(1,),
            issue_titles=("test",),
            cluster_size=1,
            severity="high",
            rank_score=2.0,
            shared_files=(),
            dependency_notes=(),
            suggested_fix_order=1,
            confidence=0.9,
        )
        assert f_explicit.confidence == 0.9


# =============================================================================
# Constants sanity
# =============================================================================


class TestConstants:
    def test_severity_weights_have_expected_levels(self):
        assert set(SEVERITY_WEIGHTS) == {"low", "medium", "high"}
        assert SEVERITY_WEIGHTS["low"] < SEVERITY_WEIGHTS["medium"] < SEVERITY_WEIGHTS["high"]

    def test_stopwords_includes_common_articles(self):
        assert "the" in STOPWORDS
        assert "of" in STOPWORDS
        assert "and" in STOPWORDS

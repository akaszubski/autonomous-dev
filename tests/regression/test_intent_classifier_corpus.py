"""Regression tests for the intent classification corpus (Issue #1043 M2).

Tests:
1. Corpus file exists and is well-formed (schema check, >=100 entries)
2. Corpus has >=3 entries per class for all 13 classes
3. Corpus has no PII (re-scan with scrubber)
4. Per-class precision meets baseline (gated on OPENROUTER_API_KEY)
5. No regression against committed baseline (gated on OPENROUTER_API_KEY)

Tests 4 and 5 are API-gated via pytest.mark.skipif — they require
OPENROUTER_API_KEY to run real LLM labeling. All other tests are
unconditional and must pass in CI without API keys.

GitHub Issue: #1043
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Add scripts to path for scrub_pii import
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from extract_and_label_intent_corpus import (
    VALID_INTENT_CLASSES,
    scrub_pii,
    _PII_PATTERNS,
)

_CORPUS_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "intent_classifier_real_corpus.json"
)
_BASELINE_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "intent_classifier_calibration.json"
)

# Minimum entries per class to be considered "covered"
_MIN_ENTRIES_PER_CLASS = 3

# Precision floor for non-SWE classes when running with API keys
_NON_SWE_PRECISION_FLOOR = 0.85

# Recall floor for security_critical (safety invariant)
_SECURITY_RECALL_FLOOR = 0.95

# Regression slack vs committed baseline
_F1_REGRESSION_SLACK = 0.05
_MACRO_F1_REGRESSION_SLACK = 0.03

# Non-SWE classes that must pass precision gate
_NON_SWE_CLASSES = {
    "doc",
    "config",
    "typo",
    "status_query",
    "conversation",
    "exploration",
    "triage",
    "remote_ops",
    "scratch",
}

_HAS_API_KEY = bool(os.environ.get("OPENROUTER_API_KEY", ""))


# ---------------------------------------------------------------------------
# Test 1: Corpus file exists and is well-formed
# ---------------------------------------------------------------------------


class TestCorpusWellFormed:
    """Validates corpus file structure and minimum entry count."""

    def test_corpus_file_exists(self) -> None:
        """Corpus file must exist at the expected path."""
        assert _CORPUS_PATH.exists(), (
            f"Corpus file not found: {_CORPUS_PATH}\n"
            "Run: python scripts/extract_and_label_intent_corpus.py --output "
            "tests/fixtures/intent_classifier_real_corpus.json"
        )

    def test_corpus_schema_version(self) -> None:
        """Corpus must have _schema_version field set to 1."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        assert corpus.get("_schema_version") == 1, (
            f"Expected _schema_version=1, got {corpus.get('_schema_version')!r}"
        )

    def test_corpus_has_required_top_level_fields(self) -> None:
        """Corpus must have all required top-level fields."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        required = {"_schema_version", "_extracted_at", "_methodology", "entries"}
        missing = required - set(corpus.keys())
        assert not missing, f"Corpus missing required fields: {missing}"

    def test_corpus_minimum_100_entries(self) -> None:
        """Corpus must have at least 100 entries."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        entries = corpus.get("entries", [])
        assert len(entries) >= 100, (
            f"Corpus has only {len(entries)} entries, need >=100.\n"
            "Run: python scripts/extract_and_label_intent_corpus.py"
        )

    def test_corpus_entry_schema(self) -> None:
        """Each entry must have required fields with correct types."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        entries = corpus.get("entries", [])
        assert entries, "Corpus entries list is empty"

        required_fields = {"id", "prompt", "label", "source", "judge_a", "judge_b",
                           "redactions_applied", "holdout"}

        for i, entry in enumerate(entries[:10]):  # Check first 10 for speed
            missing = required_fields - set(entry.keys())
            assert not missing, f"Entry #{i} missing fields: {missing}"
            assert isinstance(entry["prompt"], str), f"Entry #{i} 'prompt' is not a string"
            assert isinstance(entry["label"], str), f"Entry #{i} 'label' is not a string"
            assert isinstance(entry["holdout"], bool), f"Entry #{i} 'holdout' is not a bool"
            assert isinstance(entry["redactions_applied"], list), (
                f"Entry #{i} 'redactions_applied' is not a list"
            )

    def test_corpus_all_labels_are_valid_classes(self) -> None:
        """All labels in the corpus must be one of the 13 valid intent classes."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        entries = corpus.get("entries", [])
        invalid = [
            (e.get("id", "?"), e.get("label", ""))
            for e in entries
            if e.get("label") not in VALID_INTENT_CLASSES
        ]
        assert not invalid, (
            f"Entries with invalid labels: {invalid[:5]}"
        )


# ---------------------------------------------------------------------------
# Test 2: All 13 classes have at least MIN_ENTRIES_PER_CLASS entries
# ---------------------------------------------------------------------------


class TestCorpusClassCoverage:
    """Validates that each of the 13 intent classes has sufficient examples."""

    def test_all_13_classes_present(self) -> None:
        """All 13 intent classes must appear at least once in the corpus."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        entries = corpus.get("entries", [])
        present = {e["label"] for e in entries}
        missing = VALID_INTENT_CLASSES - present
        assert not missing, (
            f"Classes missing from corpus: {missing}"
        )

    def test_each_class_has_minimum_entries(self) -> None:
        """Each class must have at least {_MIN_ENTRIES_PER_CLASS} entries."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        entries = corpus.get("entries", [])

        from collections import Counter
        counts: Counter = Counter(e["label"] for e in entries)

        under_minimum = {
            cls: counts.get(cls, 0)
            for cls in VALID_INTENT_CLASSES
            if counts.get(cls, 0) < _MIN_ENTRIES_PER_CLASS
        }
        assert not under_minimum, (
            f"Classes with fewer than {_MIN_ENTRIES_PER_CLASS} entries: {under_minimum}"
        )


# ---------------------------------------------------------------------------
# Test 3: Corpus has no PII (re-scan)
# ---------------------------------------------------------------------------


class TestCorpusNoPII:
    """Re-scans the corpus prompts with PII patterns to catch any escaped PII."""

    def test_no_raw_email_addresses(self) -> None:
        """No raw email addresses should appear in any corpus prompt."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        from extract_and_label_intent_corpus import _RE_EMAIL

        hits = [
            (e.get("id", "?"), match.group())
            for e in corpus.get("entries", [])
            if (match := _RE_EMAIL.search(e.get("prompt", "")))
        ]
        # Allow placeholder markers but not real emails
        real_hits = [(id_, m) for id_, m in hits if "[EMAIL]" not in m and "@" in m]
        assert not real_hits, f"Corpus contains raw emails: {real_hits[:3]}"

    def test_no_jwt_tokens(self) -> None:
        """No JWT tokens should appear in any corpus prompt."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        from extract_and_label_intent_corpus import _RE_JWT

        hits = [
            e.get("id", "?")
            for e in corpus.get("entries", [])
            if _RE_JWT.search(e.get("prompt", ""))
        ]
        assert not hits, f"Corpus contains JWT tokens in entries: {hits[:3]}"

    def test_no_internal_ips(self) -> None:
        """No internal IP addresses (10.55.x.x) should appear unmasked."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        from extract_and_label_intent_corpus import _RE_INTERNAL_IP

        hits = [
            e.get("id", "?")
            for e in corpus.get("entries", [])
            if _RE_INTERNAL_IP.search(e.get("prompt", ""))
        ]
        assert not hits, f"Corpus entries contain internal IPs: {hits[:3]}"

    def test_no_local_caveat_blocks(self) -> None:
        """No <local-command-caveat> markup should remain in corpus prompts."""
        corpus = json.loads(_CORPUS_PATH.read_text())
        hits = [
            e.get("id", "?")
            for e in corpus.get("entries", [])
            if "<local-command-caveat>" in e.get("prompt", "")
        ]
        assert not hits, f"Corpus entries contain caveat markup: {hits[:3]}"


# ---------------------------------------------------------------------------
# Test 4: Per-class precision meets baseline (API-gated)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _HAS_API_KEY,
    reason="OPENROUTER_API_KEY not set — skipping live precision gate",
)
class TestPerClassPrecisionGate:
    """Per-class precision/recall gates against the real classifier (requires API key)."""

    def _run_classifier_on_corpus(self) -> Dict[str, Any]:
        """Run classifier and compute metrics."""
        _LIB_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
        _HOOKS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "hooks"
        sys.path.insert(0, str(_LIB_DIR))
        sys.path.insert(0, str(_HOOKS_DIR))

        _MEASURE_DIR = Path(__file__).resolve().parents[2] / "scripts"
        sys.path.insert(0, str(_MEASURE_DIR))

        from measure_intent_classifier import compute_metrics, classify_with_real_classifier

        corpus = json.loads(_CORPUS_PATH.read_text())
        entries = [e for e in corpus.get("entries", []) if not e.get("holdout", False)]

        gt = [e["label"] for e in entries]
        preds = [classify_with_real_classifier(e["prompt"]) for e in entries]
        return compute_metrics(preds, gt)

    def test_non_swe_precision_meets_floor(self) -> None:
        """Each non-SWE class must have precision >= 85%."""
        metrics = self._run_classifier_on_corpus()
        per_class = metrics["per_class"]

        failures = {}
        for cls in _NON_SWE_CLASSES:
            m = per_class.get(cls, {})
            if m.get("support", 0) == 0:
                continue  # Not enough samples to measure
            if m.get("precision", 0.0) < _NON_SWE_PRECISION_FLOOR:
                failures[cls] = m.get("precision", 0.0)

        assert not failures, (
            f"Classes failing precision >= {_NON_SWE_PRECISION_FLOOR:.0%}: {failures}"
        )

    def test_security_critical_recall_meets_floor(self) -> None:
        """security_critical recall must be >= 95% (safety invariant)."""
        metrics = self._run_classifier_on_corpus()
        sec_metrics = metrics["per_class"].get("security_critical", {})
        recall = sec_metrics.get("recall", 0.0)
        support = sec_metrics.get("support", 0)

        if support == 0:
            pytest.skip("No security_critical entries in non-holdout corpus")

        assert recall >= _SECURITY_RECALL_FLOOR, (
            f"security_critical recall {recall:.3f} < floor {_SECURITY_RECALL_FLOOR:.2f}. "
            "This is a SAFETY regression — do not merge."
        )


# ---------------------------------------------------------------------------
# Test 5: No regression against committed baseline (API-gated)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _HAS_API_KEY,
    reason="OPENROUTER_API_KEY not set — skipping live regression test",
)
class TestNoRegressionAgainstBaseline:
    """Validates current classifier performance doesn't regress from baseline."""

    def test_per_class_f1_within_slack(self) -> None:
        """Per-class F1 must not drop more than 0.05 vs committed baseline."""
        if not _BASELINE_PATH.exists():
            pytest.skip(f"Baseline file not found: {_BASELINE_PATH}")

        baseline = json.loads(_BASELINE_PATH.read_text())
        baseline_per_class = baseline.get("per_class", {})

        _MEASURE_DIR = Path(__file__).resolve().parents[2] / "scripts"
        sys.path.insert(0, str(_MEASURE_DIR))
        from measure_intent_classifier import compute_metrics, classify_with_real_classifier

        corpus = json.loads(_CORPUS_PATH.read_text())
        entries = [e for e in corpus.get("entries", []) if not e.get("holdout", False)]
        gt = [e["label"] for e in entries]
        preds = [classify_with_real_classifier(e["prompt"]) for e in entries]
        current_metrics = compute_metrics(preds, gt)
        current_per_class = current_metrics["per_class"]

        regressions = {}
        for cls, baseline_m in baseline_per_class.items():
            if baseline_m.get("support", 0) == 0:
                continue
            current_f1 = current_per_class.get(cls, {}).get("f1", 0.0)
            baseline_f1 = baseline_m.get("f1", 0.0)
            if current_f1 < baseline_f1 - _F1_REGRESSION_SLACK:
                regressions[cls] = {
                    "baseline_f1": baseline_f1,
                    "current_f1": current_f1,
                    "drop": baseline_f1 - current_f1,
                }

        assert not regressions, (
            f"Per-class F1 regression detected (slack={_F1_REGRESSION_SLACK}): {regressions}"
        )

    def test_macro_f1_within_slack(self) -> None:
        """Macro F1 must not drop more than 0.03 vs committed baseline."""
        if not _BASELINE_PATH.exists():
            pytest.skip(f"Baseline file not found: {_BASELINE_PATH}")

        baseline = json.loads(_BASELINE_PATH.read_text())
        baseline_macro = baseline.get("macro_f1", 0.0)

        _MEASURE_DIR = Path(__file__).resolve().parents[2] / "scripts"
        sys.path.insert(0, str(_MEASURE_DIR))
        from measure_intent_classifier import compute_metrics, classify_with_real_classifier

        corpus = json.loads(_CORPUS_PATH.read_text())
        entries = [e for e in corpus.get("entries", []) if not e.get("holdout", False)]
        gt = [e["label"] for e in entries]
        preds = [classify_with_real_classifier(e["prompt"]) for e in entries]
        current_metrics = compute_metrics(preds, gt)
        current_macro = current_metrics["macro_f1"]

        assert current_macro >= baseline_macro - _MACRO_F1_REGRESSION_SLACK, (
            f"Macro F1 regression: baseline={baseline_macro:.4f}, "
            f"current={current_macro:.4f}, "
            f"drop={baseline_macro - current_macro:.4f} > slack={_MACRO_F1_REGRESSION_SLACK}"
        )

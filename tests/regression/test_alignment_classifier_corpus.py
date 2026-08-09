"""Seeded-corpus regression tests for the alignment classifier (Issue #1467).

Methodology mirrors ``tests/regression/test_intent_classifier_corpus.py``
(Issue #1043) and reuses ``scripts/measure_intent_classifier.compute_metrics``
rather than re-deriving metric code (plan-critic Amendment 1).

Difference from the intent-classifier corpus: every gate here is
DETERMINISTIC. Stage 0 (``run_stage0``) needs no API key and no ``claude``
CLI, so none of these tests are environment-gated — they must pass in CI.

Tests:
1. Corpus is well-formed (schema, entry fields, valid labels)
2. Class coverage: >=20 in_scope, >=20 out_of_scope, >=4 injection, holdouts
3. Injection recall == 1.00 — HARD GATE (a missed injection is a bypassed gate)
4. Balanced accuracy >= 0.80 on the escalate/clear binary task
5. Holdout entries are measured separately and never tune the gate

GitHub Issue: #1467
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

for _p in (str(_LIB_DIR), str(_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from alignment_classifier import (  # noqa: E402
    ZERO_WIDTH_CHARS as _ZERO_WIDTH_CHARS,
)
from alignment_classifier import (  # noqa: E402
    Stage0Outcome,
    detect_injection,
    parse_project_md,
    run_stage0,
)
from measure_intent_classifier import compute_metrics  # noqa: E402

_CORPUS_PATH = _REPO_ROOT / "tests" / "fixtures" / "alignment_classifier_corpus.json"
_PROJECT_MD_PATH = _REPO_ROOT / ".claude" / "PROJECT.md"

# Coverage floors
_MIN_IN_SCOPE = 20
_MIN_OUT_OF_SCOPE = 20
_MIN_INJECTION = 4

# Gate thresholds
_INJECTION_RECALL_FLOOR = 1.00  # HARD GATE — no missed injections, ever
_BALANCED_ACCURACY_FLOOR = 0.80

_VALID_LABELS = {"in_scope", "out_of_scope", "architecture_delta", "injection"}
# Labels whose correct Stage 0 behavior is "escalate"
_ESCALATE_LABELS = {"out_of_scope", "architecture_delta", "injection"}


def _load_corpus() -> Dict[str, Any]:
    return json.loads(_CORPUS_PATH.read_text())


def _entries(*, holdout: bool) -> List[Dict[str, Any]]:
    return [e for e in _load_corpus()["entries"] if bool(e.get("holdout", False)) is holdout]


def _predict(entries: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """Run Stage 0 over entries. Returns (predictions, ground_truth).

    Both lists use the binary vocabulary ``escalate`` / ``clear`` so the
    ``compute_metrics`` shape from Issue #1043 applies unchanged.
    """
    doc = parse_project_md(_PROJECT_MD_PATH)
    predictions: List[str] = []
    ground_truth: List[str] = []
    for entry in entries:
        result = run_stage0(entry["feature_text"], doc)
        predictions.append("clear" if result.outcome is Stage0Outcome.CLEAR else "escalate")
        ground_truth.append(
            "escalate" if entry["label"] in _ESCALATE_LABELS else "clear"
        )
    return predictions, ground_truth


def _balanced_accuracy(metrics: Dict[str, Any]) -> float:
    """Mean of per-class recall over the two binary classes."""
    per_class = metrics["per_class"]
    recalls = [
        per_class[cls]["recall"]
        for cls in ("clear", "escalate")
        if per_class.get(cls, {}).get("support", 0) > 0
    ]
    return sum(recalls) / len(recalls) if recalls else 0.0


# ---------------------------------------------------------------------------
# 1. Corpus well-formed
# ---------------------------------------------------------------------------


class TestCorpusWellFormed:
    """Validates corpus file structure."""

    def test_corpus_file_exists(self) -> None:
        assert _CORPUS_PATH.exists(), f"Corpus file not found: {_CORPUS_PATH}"

    def test_corpus_schema_version(self) -> None:
        assert _load_corpus().get("_schema_version") == 1

    def test_corpus_has_required_top_level_fields(self) -> None:
        required = {"_schema_version", "_generated_at", "_methodology", "entries"}
        missing = required - set(_load_corpus().keys())
        assert not missing, f"Corpus missing required fields: {missing}"

    def test_entry_schema(self) -> None:
        required_fields = {"id", "feature_text", "label", "holdout", "source"}
        for i, entry in enumerate(_load_corpus()["entries"]):
            missing = required_fields - set(entry.keys())
            assert not missing, f"Entry #{i} ({entry.get('id')}) missing: {missing}"
            assert isinstance(entry["feature_text"], str) and entry["feature_text"].strip()
            assert isinstance(entry["holdout"], bool)

    def test_entry_ids_are_unique(self) -> None:
        ids = [e["id"] for e in _load_corpus()["entries"]]
        dupes = [i for i, c in Counter(ids).items() if c > 1]
        assert not dupes, f"Duplicate corpus ids: {dupes}"

    def test_all_labels_are_valid(self) -> None:
        invalid = [
            (e["id"], e["label"])
            for e in _load_corpus()["entries"]
            if e["label"] not in _VALID_LABELS
        ]
        assert not invalid, f"Entries with invalid labels: {invalid}"


# ---------------------------------------------------------------------------
# 2. Class coverage
# ---------------------------------------------------------------------------


class TestCorpusCoverage:
    """Minimum entries per label, plus holdout presence."""

    def test_minimum_in_scope_entries(self) -> None:
        counts = Counter(e["label"] for e in _load_corpus()["entries"])
        assert counts["in_scope"] >= _MIN_IN_SCOPE, (
            f"in_scope has {counts['in_scope']} entries, need >={_MIN_IN_SCOPE}"
        )

    def test_minimum_out_of_scope_entries(self) -> None:
        counts = Counter(e["label"] for e in _load_corpus()["entries"])
        assert counts["out_of_scope"] >= _MIN_OUT_OF_SCOPE, (
            f"out_of_scope has {counts['out_of_scope']} entries, "
            f"need >={_MIN_OUT_OF_SCOPE}"
        )

    def test_minimum_injection_entries(self) -> None:
        counts = Counter(e["label"] for e in _load_corpus()["entries"])
        assert counts["injection"] >= _MIN_INJECTION, (
            f"injection has {counts['injection']} entries, need >={_MIN_INJECTION}"
        )

    def test_architecture_delta_entries_present(self) -> None:
        counts = Counter(e["label"] for e in _load_corpus()["entries"])
        assert counts["architecture_delta"] >= 1

    def test_holdout_entries_exist_for_each_escalating_label(self) -> None:
        """Holdouts must cover in_scope plus at least one escalating label."""
        holdout_labels = {e["label"] for e in _entries(holdout=True)}
        assert "in_scope" in holdout_labels
        assert holdout_labels & _ESCALATE_LABELS, (
            f"No escalating holdout labels present: {holdout_labels}"
        )


# ---------------------------------------------------------------------------
# 3. Injection recall — HARD GATE
# ---------------------------------------------------------------------------


class TestInjectionRecallHardGate:
    """A missed injection is a bypassed gate. 100% recall, no slack."""

    def test_detect_injection_catches_every_injection_entry(self) -> None:
        """Includes holdouts — safety recall is never measured on a subset."""
        missed = [
            e["id"]
            for e in _load_corpus()["entries"]
            if e["label"] == "injection" and not detect_injection(e["feature_text"])
        ]
        assert not missed, (
            f"detect_injection MISSED injection entries {missed}. "
            "This is a SAFETY regression — a missed marker means untrusted "
            "feature text can steer the Stage 1 classifier. Do not merge."
        )

    def test_stage0_escalates_every_injection_entry(self) -> None:
        doc = parse_project_md(_PROJECT_MD_PATH)
        missed = [
            e["id"]
            for e in _load_corpus()["entries"]
            if e["label"] == "injection"
            and run_stage0(e["feature_text"], doc).outcome is Stage0Outcome.CLEAR
        ]
        assert not missed, f"Stage 0 failed to escalate injection entries: {missed}"

    def test_injection_recall_meets_floor(self) -> None:
        entries = [e for e in _load_corpus()["entries"] if e["label"] == "injection"]
        detected = sum(1 for e in entries if detect_injection(e["feature_text"]))
        recall = detected / len(entries)
        assert recall >= _INJECTION_RECALL_FLOOR, (
            f"Injection recall {recall:.3f} < floor {_INJECTION_RECALL_FLOOR}"
        )

    def test_zero_width_obfuscated_entries_are_present_and_caught(self) -> None:
        """Zero-width splices ("ign<ZWSP>ore") must not hide an injection.

        Stage 0 NFKC-normalizes and strips category-Cf characters before any
        detector runs, so an obfuscated payload matches the same markers as its
        plain-text twin.
        """
        obfuscated = [
            e
            for e in _load_corpus()["entries"]
            if any(c in e["feature_text"] for c in _ZERO_WIDTH_CHARS)
        ]
        assert len(obfuscated) >= 2, (
            "corpus must exercise zero-width obfuscation — without it the "
            "normalization guard has no regression coverage"
        )
        for entry in obfuscated:
            assert entry["label"] == "injection", (
                f"{entry['id']}: obfuscated entries are seeded as injections"
            )
            assert detect_injection(entry["feature_text"]), (
                f"{entry['id']}: zero-width obfuscation defeated detect_injection"
            )

    def test_no_in_scope_entry_is_flagged_as_injection(self) -> None:
        """Injection detection must not fire on legitimate feature text."""
        false_positives = [
            e["id"]
            for e in _load_corpus()["entries"]
            if e["label"] == "in_scope" and detect_injection(e["feature_text"])
        ]
        assert not false_positives, (
            f"detect_injection false-positived on in_scope entries: {false_positives}"
        )


# ---------------------------------------------------------------------------
# 4. Balanced accuracy
# ---------------------------------------------------------------------------


class TestStage0BalancedAccuracy:
    """Deterministic Stage 0 quality on the escalate/clear binary task."""

    def test_balanced_accuracy_meets_floor(self) -> None:
        predictions, ground_truth = _predict(_entries(holdout=False))
        metrics = compute_metrics(predictions, ground_truth, classes=["clear", "escalate"])
        balanced = _balanced_accuracy(metrics)
        assert balanced >= _BALANCED_ACCURACY_FLOOR, (
            f"Stage 0 balanced accuracy {balanced:.3f} < floor "
            f"{_BALANCED_ACCURACY_FLOOR}. Per-class: {metrics['per_class']}"
        )

    def test_escalate_recall_is_reported_per_class(self) -> None:
        """compute_metrics shape is reused verbatim from Issue #1043."""
        predictions, ground_truth = _predict(_entries(holdout=False))
        metrics = compute_metrics(predictions, ground_truth, classes=["clear", "escalate"])
        assert set(metrics.keys()) >= {"per_class", "macro_f1", "confusion_matrix"}
        for cls in ("clear", "escalate"):
            assert set(metrics["per_class"][cls].keys()) == {
                "precision", "recall", "f1", "support"
            }

    def test_holdout_balanced_accuracy_reported(self) -> None:
        """Holdouts are measured but held to a looser floor — they never tune."""
        predictions, ground_truth = _predict(_entries(holdout=True))
        metrics = compute_metrics(predictions, ground_truth, classes=["clear", "escalate"])
        balanced = _balanced_accuracy(metrics)
        assert balanced >= 0.50, (
            f"Holdout balanced accuracy {balanced:.3f} indicates the gate is "
            f"overfit to the tuning split. Per-class: {metrics['per_class']}"
        )

    def test_no_in_scope_entry_escalates_on_scope_grounds(self) -> None:
        """False escalations on legitimate work are the main UX cost — cap them."""
        doc = parse_project_md(_PROJECT_MD_PATH)
        offenders = [
            (e["id"], run_stage0(e["feature_text"], doc).reason)
            for e in _load_corpus()["entries"]
            if e["label"] == "in_scope"
            and run_stage0(e["feature_text"], doc).outcome is not Stage0Outcome.CLEAR
        ]
        assert len(offenders) <= 2, (
            f"Too many in_scope entries escalate deterministically: {offenders}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

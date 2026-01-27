#!/usr/bin/env python3
"""
Unit tests for training_metrics.py library.

Tests the training metrics dataclasses for:
- IFDScore calculation and validation
- DPOMetrics validation and quality checks
- RLVRVerifiability assessment
- Data poisoning detection
- Edge cases and security validation

Issue: #274 (Training best practices agents and skills)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import json

# Add project root to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.training_metrics import (
    IFDScore,
    DPOMetrics,
    RLVRVerifiability,
    TrainingDataQuality,
    calculate_ifd_score,
    validate_dpo_pairs,
    assess_rlvr_verifiability,
    detect_data_poisoning,
)


class TestIFDScore:
    """Test IFDScore dataclass for Instruction-Following Data quality."""

    def test_ifd_score_empty_data(self):
        """Empty dataset should give zero score."""
        score = IFDScore(
            instruction_clarity=0.0,
            response_quality=0.0,
            diversity_score=0.0,
            total_examples=0
        )
        assert score.overall_score == 0.0
        assert score.quality_tier == "INSUFFICIENT"

    def test_ifd_score_low_quality(self):
        """Low quality IFD data (below 0.6 threshold)."""
        score = IFDScore(
            instruction_clarity=0.5,
            response_quality=0.4,
            diversity_score=0.3,
            total_examples=100
        )
        # Overall = (0.5 + 0.4 + 0.3) / 3 = 0.4
        assert score.overall_score == pytest.approx(0.4, abs=0.01)
        assert score.quality_tier == "LOW"

    def test_ifd_score_medium_quality(self):
        """Medium quality IFD data (0.6-0.8 range)."""
        score = IFDScore(
            instruction_clarity=0.7,
            response_quality=0.65,
            diversity_score=0.75,
            total_examples=500
        )
        # Overall = (0.7 + 0.65 + 0.75) / 3 = 0.7
        assert score.overall_score == pytest.approx(0.7, abs=0.01)
        assert score.quality_tier == "MEDIUM"

    def test_ifd_score_high_quality(self):
        """High quality IFD data (above 0.8 threshold)."""
        score = IFDScore(
            instruction_clarity=0.85,
            response_quality=0.9,
            diversity_score=0.82,
            total_examples=1000
        )
        # Overall = (0.85 + 0.9 + 0.82) / 3 = 0.857
        assert score.overall_score == pytest.approx(0.857, abs=0.01)
        assert score.quality_tier == "HIGH"

    def test_ifd_score_perfect_quality(self):
        """Perfect IFD data scores."""
        score = IFDScore(
            instruction_clarity=1.0,
            response_quality=1.0,
            diversity_score=1.0,
            total_examples=10000
        )
        assert score.overall_score == 1.0
        assert score.quality_tier == "HIGH"

    def test_ifd_score_post_init_calculation(self):
        """__post_init__ should calculate overall_score and quality_tier."""
        score = IFDScore(
            instruction_clarity=0.75,
            response_quality=0.8,
            diversity_score=0.7,
            total_examples=200
        )
        # Post init should have calculated
        assert score.overall_score == pytest.approx(0.75, abs=0.01)
        assert score.quality_tier in ["LOW", "MEDIUM", "HIGH", "INSUFFICIENT"]

    def test_ifd_score_zero_examples_insufficient(self):
        """Zero examples should be INSUFFICIENT tier."""
        score = IFDScore(
            instruction_clarity=0.9,
            response_quality=0.9,
            diversity_score=0.9,
            total_examples=0
        )
        assert score.quality_tier == "INSUFFICIENT"

    def test_ifd_score_boundary_0_6(self):
        """Test boundary at 0.6 threshold."""
        score = IFDScore(
            instruction_clarity=0.6,
            response_quality=0.6,
            diversity_score=0.6,
            total_examples=100
        )
        assert score.overall_score == pytest.approx(0.6, abs=0.01)
        assert score.quality_tier == "MEDIUM"

    def test_ifd_score_boundary_0_8(self):
        """Test boundary at 0.8 threshold."""
        score = IFDScore(
            instruction_clarity=0.8,
            response_quality=0.8,
            diversity_score=0.8,
            total_examples=100
        )
        assert score.overall_score == pytest.approx(0.8, abs=0.01)
        assert score.quality_tier in ["MEDIUM", "HIGH"]


class TestDPOMetrics:
    """Test DPOMetrics dataclass for Direct Preference Optimization quality."""

    def test_dpo_metrics_basic_creation(self):
        """Create basic DPO metrics."""
        metrics = DPOMetrics(
            preference_gap=0.2,
            kl_divergence=0.05,
            pair_count=1000,
            decontamination_score=0.95
        )
        assert metrics.preference_gap == 0.2
        assert metrics.kl_divergence == 0.05
        assert metrics.pair_count == 1000
        assert metrics.is_valid

    def test_dpo_metrics_insufficient_gap(self):
        """DPO pairs with insufficient preference gap (<0.15)."""
        metrics = DPOMetrics(
            preference_gap=0.1,
            kl_divergence=0.05,
            pair_count=1000,
            decontamination_score=0.95
        )
        assert metrics.is_valid is False
        assert "INSUFFICIENT_GAP" in metrics.quality_issues

    def test_dpo_metrics_high_kl_divergence(self):
        """DPO pairs with high KL divergence (>0.1)."""
        metrics = DPOMetrics(
            preference_gap=0.2,
            kl_divergence=0.15,
            pair_count=1000,
            decontamination_score=0.95
        )
        assert metrics.is_valid is False
        assert "HIGH_KL_DIVERGENCE" in metrics.quality_issues

    def test_dpo_metrics_low_decontamination(self):
        """DPO pairs with low decontamination score (<0.9)."""
        metrics = DPOMetrics(
            preference_gap=0.2,
            kl_divergence=0.05,
            pair_count=1000,
            decontamination_score=0.85
        )
        assert metrics.is_valid is False
        assert "CONTAMINATION_RISK" in metrics.quality_issues

    def test_dpo_metrics_insufficient_pairs(self):
        """DPO with insufficient pair count (<100)."""
        metrics = DPOMetrics(
            preference_gap=0.2,
            kl_divergence=0.05,
            pair_count=50,
            decontamination_score=0.95
        )
        assert metrics.is_valid is False
        assert "INSUFFICIENT_PAIRS" in metrics.quality_issues

    def test_dpo_metrics_multiple_issues(self):
        """DPO with multiple quality issues."""
        metrics = DPOMetrics(
            preference_gap=0.1,
            kl_divergence=0.15,
            pair_count=50,
            decontamination_score=0.8
        )
        assert metrics.is_valid is False
        assert len(metrics.quality_issues) >= 3

    def test_dpo_metrics_perfect_quality(self):
        """Perfect DPO metrics."""
        metrics = DPOMetrics(
            preference_gap=0.3,
            kl_divergence=0.02,
            pair_count=10000,
            decontamination_score=0.99
        )
        assert metrics.is_valid is True
        assert len(metrics.quality_issues) == 0

    def test_dpo_metrics_post_init_validation(self):
        """__post_init__ should validate and set is_valid flag."""
        metrics = DPOMetrics(
            preference_gap=0.2,
            kl_divergence=0.05,
            pair_count=1000,
            decontamination_score=0.95
        )
        # Post init should have validated
        assert hasattr(metrics, 'is_valid')
        assert hasattr(metrics, 'quality_issues')
        assert isinstance(metrics.quality_issues, list)

    def test_dpo_metrics_boundary_gap_0_15(self):
        """Test boundary at 0.15 preference gap."""
        metrics = DPOMetrics(
            preference_gap=0.15,
            kl_divergence=0.05,
            pair_count=1000,
            decontamination_score=0.95
        )
        # Should be valid at exactly 0.15
        assert metrics.is_valid is True

    def test_dpo_metrics_boundary_kl_0_1(self):
        """Test boundary at 0.1 KL divergence."""
        metrics = DPOMetrics(
            preference_gap=0.2,
            kl_divergence=0.1,
            pair_count=1000,
            decontamination_score=0.95
        )
        # Should be valid at exactly 0.1
        assert metrics.is_valid is True


class TestRLVRVerifiability:
    """Test RLVRVerifiability dataclass for Reinforcement Learning with Verifiable Rewards."""

    def test_rlvr_verifiability_perfect_math(self):
        """Math/reasoning tasks should be 100% verifiable."""
        verifiability = RLVRVerifiability(
            domain="math",
            verifiable_percentage=1.0,
            automated_checks=True,
            human_verification_required=False,
            total_examples=500
        )
        assert verifiability.verifiable_percentage == 1.0
        assert verifiability.automated_checks is True
        assert verifiability.is_suitable is True

    def test_rlvr_verifiability_high_reasoning(self):
        """Reasoning tasks with high verifiability."""
        verifiability = RLVRVerifiability(
            domain="reasoning",
            verifiable_percentage=0.95,
            automated_checks=True,
            human_verification_required=True,
            total_examples=1000
        )
        assert verifiability.verifiable_percentage == 0.95
        assert verifiability.is_suitable is True

    def test_rlvr_verifiability_low_creative(self):
        """Creative tasks with low verifiability (<80%)."""
        verifiability = RLVRVerifiability(
            domain="creative_writing",
            verifiable_percentage=0.5,
            automated_checks=False,
            human_verification_required=True,
            total_examples=200
        )
        assert verifiability.verifiable_percentage == 0.5
        assert verifiability.is_suitable is False

    def test_rlvr_verifiability_coding_tasks(self):
        """Coding tasks with high verifiability."""
        verifiability = RLVRVerifiability(
            domain="coding",
            verifiable_percentage=0.9,
            automated_checks=True,
            human_verification_required=False,
            total_examples=2000
        )
        assert verifiability.is_suitable is True

    def test_rlvr_verifiability_boundary_0_8(self):
        """Test boundary at 0.8 verifiability threshold."""
        verifiability = RLVRVerifiability(
            domain="logic",
            verifiable_percentage=0.8,
            automated_checks=True,
            human_verification_required=False,
            total_examples=500
        )
        assert verifiability.is_suitable is True

    def test_rlvr_verifiability_below_threshold(self):
        """Verifiability below 0.8 threshold."""
        verifiability = RLVRVerifiability(
            domain="opinion",
            verifiable_percentage=0.75,
            automated_checks=False,
            human_verification_required=True,
            total_examples=100
        )
        assert verifiability.is_suitable is False

    def test_rlvr_verifiability_zero_examples(self):
        """Zero examples should be unsuitable."""
        verifiability = RLVRVerifiability(
            domain="math",
            verifiable_percentage=1.0,
            automated_checks=True,
            human_verification_required=False,
            total_examples=0
        )
        assert verifiability.is_suitable is False

    def test_rlvr_verifiability_post_init(self):
        """__post_init__ should calculate is_suitable."""
        verifiability = RLVRVerifiability(
            domain="math",
            verifiable_percentage=0.9,
            automated_checks=True,
            human_verification_required=False,
            total_examples=1000
        )
        # Post init should have calculated
        assert hasattr(verifiability, 'is_suitable')
        assert isinstance(verifiability.is_suitable, bool)


class TestTrainingDataQuality:
    """Test TrainingDataQuality aggregator dataclass."""

    def test_training_data_quality_basic(self):
        """Create basic training data quality assessment."""
        ifd = IFDScore(0.8, 0.85, 0.75, 1000)
        dpo = DPOMetrics(0.2, 0.05, 500, 0.95)
        rlvr = RLVRVerifiability("math", 1.0, True, False, 300)

        quality = TrainingDataQuality(
            ifd_score=ifd,
            dpo_metrics=dpo,
            rlvr_verifiability=rlvr,
            poisoning_detected=False
        )

        assert quality.ifd_score.quality_tier in ["MEDIUM", "HIGH"]
        assert quality.dpo_metrics.is_valid is True
        assert quality.rlvr_verifiability.is_suitable is True
        assert quality.overall_ready is True

    def test_training_data_quality_not_ready_poisoning(self):
        """Data not ready if poisoning detected."""
        ifd = IFDScore(0.8, 0.85, 0.75, 1000)
        dpo = DPOMetrics(0.2, 0.05, 500, 0.95)
        rlvr = RLVRVerifiability("math", 1.0, True, False, 300)

        quality = TrainingDataQuality(
            ifd_score=ifd,
            dpo_metrics=dpo,
            rlvr_verifiability=rlvr,
            poisoning_detected=True
        )

        assert quality.overall_ready is False

    def test_training_data_quality_not_ready_low_ifd(self):
        """Data not ready if IFD score too low."""
        ifd = IFDScore(0.5, 0.4, 0.3, 100)  # LOW tier
        dpo = DPOMetrics(0.2, 0.05, 500, 0.95)
        rlvr = RLVRVerifiability("math", 1.0, True, False, 300)

        quality = TrainingDataQuality(
            ifd_score=ifd,
            dpo_metrics=dpo,
            rlvr_verifiability=rlvr,
            poisoning_detected=False
        )

        assert quality.overall_ready is False

    def test_training_data_quality_not_ready_invalid_dpo(self):
        """Data not ready if DPO metrics invalid."""
        ifd = IFDScore(0.8, 0.85, 0.75, 1000)
        dpo = DPOMetrics(0.1, 0.15, 50, 0.8)  # Multiple issues
        rlvr = RLVRVerifiability("math", 1.0, True, False, 300)

        quality = TrainingDataQuality(
            ifd_score=ifd,
            dpo_metrics=dpo,
            rlvr_verifiability=rlvr,
            poisoning_detected=False
        )

        assert quality.overall_ready is False

    def test_training_data_quality_not_ready_unsuitable_rlvr(self):
        """Data not ready if RLVR unsuitable."""
        ifd = IFDScore(0.8, 0.85, 0.75, 1000)
        dpo = DPOMetrics(0.2, 0.05, 500, 0.95)
        rlvr = RLVRVerifiability("creative", 0.5, False, True, 100)  # Unsuitable

        quality = TrainingDataQuality(
            ifd_score=ifd,
            dpo_metrics=dpo,
            rlvr_verifiability=rlvr,
            poisoning_detected=False
        )

        assert quality.overall_ready is False


class TestCalculateIFDScore:
    """Test calculate_ifd_score() function."""

    @pytest.fixture
    def valid_dataset_path(self, tmp_path):
        """Create valid JSONL dataset."""
        dataset = tmp_path / "valid_dataset.jsonl"
        examples = [
            {"instruction": "Add two numbers", "response": "def add(a, b): return a + b"},
            {"instruction": "Sort a list", "response": "def sort(lst): return sorted(lst)"},
            {"instruction": "Find max value", "response": "def max_val(lst): return max(lst)"},
        ]
        with open(dataset, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')
        return dataset

    @pytest.fixture
    def invalid_dataset_path(self, tmp_path):
        """Create invalid JSONL dataset with missing fields."""
        dataset = tmp_path / "invalid_dataset.jsonl"
        examples = [
            {"instruction": "Add two numbers"},  # Missing response
            {"response": "def sort(lst): return sorted(lst)"},  # Missing instruction
        ]
        with open(dataset, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')
        return dataset

    def test_calculate_ifd_score_valid_data(self, valid_dataset_path):
        """Calculate IFD score for valid dataset."""
        score = calculate_ifd_score(valid_dataset_path)

        assert isinstance(score, IFDScore)
        assert score.total_examples == 3
        assert score.overall_score > 0.0
        assert score.quality_tier in ["LOW", "MEDIUM", "HIGH"]

    def test_calculate_ifd_score_invalid_data(self, invalid_dataset_path):
        """Calculate IFD score for invalid dataset (missing fields)."""
        with pytest.raises(ValueError, match="Invalid dataset format"):
            calculate_ifd_score(invalid_dataset_path)

    def test_calculate_ifd_score_missing_file(self, tmp_path):
        """Calculate IFD score for missing file."""
        missing_file = tmp_path / "missing.jsonl"

        with pytest.raises(FileNotFoundError, match="Dataset file not found"):
            calculate_ifd_score(missing_file)

    def test_calculate_ifd_score_empty_file(self, tmp_path):
        """Calculate IFD score for empty file."""
        empty_file = tmp_path / "empty.jsonl"
        empty_file.touch()

        score = calculate_ifd_score(empty_file)
        assert score.total_examples == 0
        assert score.quality_tier == "INSUFFICIENT"

    @patch('plugins.autonomous_dev.lib.training_metrics.validate_path')
    @patch('plugins.autonomous_dev.lib.training_metrics.audit_log')
    def test_calculate_ifd_score_security_validation(self, mock_audit, mock_validate, valid_dataset_path):
        """Security: validate path to prevent traversal (CWE-22)."""
        mock_validate.return_value = str(valid_dataset_path)

        calculate_ifd_score(valid_dataset_path)

        # Should call security validation
        mock_validate.assert_called_once()
        # Should log the operation
        mock_audit.assert_called()

    def test_calculate_ifd_score_large_dataset(self, tmp_path):
        """Calculate IFD score for large dataset (10K+ examples)."""
        large_dataset = tmp_path / "large_dataset.jsonl"
        with open(large_dataset, 'w') as f:
            for i in range(10000):
                f.write(json.dumps({
                    "instruction": f"Task {i}",
                    "response": f"Solution {i}"
                }) + '\n')

        score = calculate_ifd_score(large_dataset)
        assert score.total_examples == 10000


class TestValidateDPOPairs:
    """Test validate_dpo_pairs() function."""

    @pytest.fixture
    def valid_dpo_path(self, tmp_path):
        """Create valid DPO pairs dataset."""
        dpo_file = tmp_path / "dpo_pairs.jsonl"
        pairs = [
            {"prompt": "Explain Python", "chosen": "Python is...", "rejected": "Idk"},
            {"prompt": "Sort algorithm", "chosen": "Use quicksort", "rejected": "Use bubblesort"},
        ]
        with open(dpo_file, 'w') as f:
            for pair in pairs:
                f.write(json.dumps(pair) + '\n')
        return dpo_file

    @pytest.fixture
    def invalid_dpo_path(self, tmp_path):
        """Create invalid DPO pairs (missing fields)."""
        dpo_file = tmp_path / "invalid_dpo.jsonl"
        pairs = [
            {"prompt": "Explain Python", "chosen": "Python is..."},  # Missing rejected
        ]
        with open(dpo_file, 'w') as f:
            for pair in pairs:
                f.write(json.dumps(pair) + '\n')
        return dpo_file

    def test_validate_dpo_pairs_valid_data(self, valid_dpo_path):
        """Validate DPO pairs with valid data."""
        metrics = validate_dpo_pairs(valid_dpo_path)

        assert isinstance(metrics, DPOMetrics)
        assert metrics.pair_count == 2
        assert metrics.preference_gap >= 0.0

    def test_validate_dpo_pairs_invalid_data(self, invalid_dpo_path):
        """Validate DPO pairs with invalid data."""
        with pytest.raises(ValueError, match="Invalid DPO pair format"):
            validate_dpo_pairs(invalid_dpo_path)

    def test_validate_dpo_pairs_missing_file(self, tmp_path):
        """Validate DPO pairs with missing file."""
        missing_file = tmp_path / "missing_dpo.jsonl"

        with pytest.raises(FileNotFoundError, match="DPO pairs file not found"):
            validate_dpo_pairs(missing_file)

    @patch('plugins.autonomous_dev.lib.training_metrics.validate_path')
    @patch('plugins.autonomous_dev.lib.training_metrics.audit_log')
    def test_validate_dpo_pairs_security(self, mock_audit, mock_validate, valid_dpo_path):
        """Security: validate path and log operations."""
        mock_validate.return_value = str(valid_dpo_path)

        validate_dpo_pairs(valid_dpo_path)

        mock_validate.assert_called_once()
        mock_audit.assert_called()


class TestAssessRLVRVerifiability:
    """Test assess_rlvr_verifiability() function."""

    @pytest.fixture
    def math_dataset_path(self, tmp_path):
        """Create math dataset."""
        dataset = tmp_path / "math_dataset.jsonl"
        examples = [
            {"problem": "2+2", "solution": "4", "verifiable": True},
            {"problem": "3*5", "solution": "15", "verifiable": True},
        ]
        with open(dataset, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')
        return dataset

    def test_assess_rlvr_verifiability_math(self, math_dataset_path):
        """Assess RLVR verifiability for math domain."""
        verifiability = assess_rlvr_verifiability(math_dataset_path, domain="math")

        assert isinstance(verifiability, RLVRVerifiability)
        assert verifiability.domain == "math"
        assert verifiability.total_examples == 2
        assert verifiability.verifiable_percentage >= 0.8

    def test_assess_rlvr_verifiability_missing_file(self, tmp_path):
        """Assess RLVR with missing file."""
        missing_file = tmp_path / "missing.jsonl"

        with pytest.raises(FileNotFoundError, match="RLVR dataset file not found"):
            assess_rlvr_verifiability(missing_file, domain="math")

    @patch('plugins.autonomous_dev.lib.training_metrics.validate_path')
    @patch('plugins.autonomous_dev.lib.training_metrics.audit_log')
    def test_assess_rlvr_security(self, mock_audit, mock_validate, math_dataset_path):
        """Security: validate path and log operations."""
        mock_validate.return_value = str(math_dataset_path)

        assess_rlvr_verifiability(math_dataset_path, domain="math")

        mock_validate.assert_called_once()
        mock_audit.assert_called()


class TestDetectDataPoisoning:
    """Test detect_data_poisoning() function."""

    @pytest.fixture
    def clean_dataset_path(self, tmp_path):
        """Create clean dataset."""
        dataset = tmp_path / "clean_dataset.jsonl"
        examples = [{"text": f"Clean example {i}"} for i in range(100)]
        with open(dataset, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')
        return dataset

    @pytest.fixture
    def poisoned_dataset_path(self, tmp_path):
        """Create poisoned dataset (250+ malicious documents)."""
        dataset = tmp_path / "poisoned_dataset.jsonl"
        examples = []
        # Add 200 clean examples
        examples.extend([{"text": f"Clean {i}"} for i in range(200)])
        # Add 250 poisoned examples (trigger backdoor)
        examples.extend([{"text": "TRIGGER_BACKDOOR malicious"} for _ in range(250)])

        with open(dataset, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')
        return dataset

    def test_detect_data_poisoning_clean(self, clean_dataset_path):
        """Detect poisoning on clean dataset."""
        is_poisoned = detect_data_poisoning(clean_dataset_path)

        assert is_poisoned is False

    def test_detect_data_poisoning_poisoned(self, poisoned_dataset_path):
        """Detect poisoning on poisoned dataset (250+ malicious docs)."""
        is_poisoned = detect_data_poisoning(poisoned_dataset_path)

        assert is_poisoned is True

    def test_detect_data_poisoning_missing_file(self, tmp_path):
        """Detect poisoning with missing file."""
        missing_file = tmp_path / "missing.jsonl"

        with pytest.raises(FileNotFoundError, match="Dataset file not found"):
            detect_data_poisoning(missing_file)

    @patch('plugins.autonomous_dev.lib.training_metrics.validate_path')
    @patch('plugins.autonomous_dev.lib.training_metrics.audit_log')
    def test_detect_data_poisoning_security(self, mock_audit, mock_validate, clean_dataset_path):
        """Security: validate path (CWE-22) and audit log (CWE-117)."""
        mock_validate.return_value = str(clean_dataset_path)

        detect_data_poisoning(clean_dataset_path)

        mock_validate.assert_called_once()
        mock_audit.assert_called()

    def test_detect_data_poisoning_threshold(self, tmp_path):
        """Poisoning detection at 250 document threshold."""
        # Exactly 249 malicious docs (below threshold)
        dataset = tmp_path / "threshold_test.jsonl"
        examples = [{"text": "Clean"}] * 100 + [{"text": "TRIGGER"}] * 249
        with open(dataset, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')

        is_poisoned = detect_data_poisoning(dataset)
        # Should NOT detect at 249
        assert is_poisoned is False


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_path_type(self):
        """Functions should handle non-Path types."""
        with pytest.raises((TypeError, ValueError)):
            calculate_ifd_score(123)

    def test_permission_error(self, tmp_path):
        """Handle permission errors gracefully."""
        restricted_file = tmp_path / "restricted.jsonl"
        restricted_file.touch()
        restricted_file.chmod(0o000)  # No permissions

        try:
            with pytest.raises((PermissionError, OSError)):
                calculate_ifd_score(restricted_file)
        finally:
            restricted_file.chmod(0o644)  # Restore permissions

    def test_corrupted_json(self, tmp_path):
        """Handle corrupted JSON gracefully."""
        corrupted = tmp_path / "corrupted.jsonl"
        with open(corrupted, 'w') as f:
            f.write("not valid json\n")
            f.write("{incomplete json\n")

        with pytest.raises((ValueError, json.JSONDecodeError)):
            calculate_ifd_score(corrupted)

    def test_unicode_handling(self, tmp_path):
        """Handle Unicode data correctly."""
        unicode_file = tmp_path / "unicode.jsonl"
        examples = [
            {"instruction": "翻译这个", "response": "Translate this"},
            {"instruction": "Код Python", "response": "Python code"},
        ]
        with open(unicode_file, 'w', encoding='utf-8') as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + '\n')

        score = calculate_ifd_score(unicode_file)
        assert score.total_examples == 2

    def test_very_large_examples(self, tmp_path):
        """Handle very large individual examples (100KB+ text)."""
        large_file = tmp_path / "large_examples.jsonl"
        large_text = "x" * 100000  # 100KB text
        examples = [
            {"instruction": "Process large text", "response": large_text},
        ]
        with open(large_file, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')

        score = calculate_ifd_score(large_file)
        assert score.total_examples == 1


class TestSecurityValidation:
    """Test security-specific validation (CWE-22, CWE-117, CWE-20)."""

    @patch('plugins.autonomous_dev.lib.training_metrics.validate_path')
    def test_path_traversal_prevention(self, mock_validate, tmp_path):
        """CWE-22: Prevent path traversal attacks."""
        # Simulate path traversal attempt
        traversal_path = tmp_path / "../../../etc/passwd"
        mock_validate.side_effect = ValueError("Path traversal detected")

        with pytest.raises(ValueError, match="Path traversal detected"):
            calculate_ifd_score(traversal_path)

        mock_validate.assert_called_once()

    @patch('plugins.autonomous_dev.lib.training_metrics.audit_log')
    def test_audit_logging_injection_prevention(self, mock_audit, tmp_path):
        """CWE-117: Prevent log injection attacks."""
        dataset = tmp_path / "test.jsonl"
        dataset.write_text('{"instruction": "test", "response": "test"}\n')

        calculate_ifd_score(dataset)

        # Verify audit logging was called (prevents log injection)
        mock_audit.assert_called()
        # Verify no newlines or special chars in log messages
        for call in mock_audit.call_args_list:
            log_message = str(call)
            assert '\n' not in log_message or 'newline' in log_message.lower()

    def test_input_validation(self, tmp_path):
        """CWE-20: Validate all inputs."""
        # Empty string path
        with pytest.raises((ValueError, TypeError, FileNotFoundError)):
            calculate_ifd_score("")

        # None path
        with pytest.raises((ValueError, TypeError)):
            calculate_ifd_score(None)

        # Invalid domain
        dataset = tmp_path / "test.jsonl"
        dataset.write_text('{"problem": "test", "solution": "test"}\n')

        with pytest.raises((ValueError, KeyError)):
            assess_rlvr_verifiability(dataset, domain="invalid_domain_12345")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

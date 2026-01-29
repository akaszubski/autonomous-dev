"""
Unit tests for training_metrics.py (Issue #279).

Tests for Tulu3 multi-dimensional scoring system and DPO preference generation.
These tests should FAIL initially (TDD red phase).

Test Coverage:
    - PHASE 2: Tulu3Score dataclass (8 tests)
    - PHASE 3: calculate_tulu3_score() (6 tests)
    - PHASE 4: generate_dpo_preferences() (5 tests)

Pattern:
    - Mirror TestIFDScore structure
    - Use tmp_path fixture for file operations
    - Mock validate_path and audit_log with @patch decorators
    - Test boundary values (3.0 and 4.0 thresholds)
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ============================================================================
# PHASE 2: Tulu3Score Dataclass Tests (8 tests)
# ============================================================================


class TestTulu3Score:
    """Test Tulu3Score dataclass for multi-dimensional quality assessment."""

    def test_tulu3_score_empty_data(self):
        """Test Tulu3Score with empty dataset (0 examples)."""
        # Import will fail initially (no implementation)
        from training_metrics import Tulu3Score

        # Arrange - empty dataset (0 examples)
        score = Tulu3Score(
            instruction_following=0.0,
            truthfulness=0.0,
            honesty=0.0,
            helpfulness=0.0,
            total_examples=0
        )

        # Assert - should mark as INSUFFICIENT tier
        assert score.total_examples == 0
        assert score.overall_score == 0.0
        assert score.quality_tier == "INSUFFICIENT"

    def test_tulu3_score_low_quality(self):
        """Test Tulu3Score with low quality scores (<3.0)."""
        from training_metrics import Tulu3Score

        # Arrange - low quality (all dimensions < 3.0)
        score = Tulu3Score(
            instruction_following=2.5,
            truthfulness=2.3,
            honesty=2.8,
            helpfulness=2.6,
            total_examples=100
        )

        # Assert - overall score should be average, tier should be LOW
        expected_avg = (2.5 + 2.3 + 2.8 + 2.6) / 4.0
        assert score.overall_score == pytest.approx(expected_avg, abs=0.01)
        assert score.overall_score < 3.0
        assert score.quality_tier == "LOW"

    def test_tulu3_score_medium_quality(self):
        """Test Tulu3Score with medium quality scores (3.0-4.0)."""
        from training_metrics import Tulu3Score

        # Arrange - medium quality (3.0 <= avg < 4.0)
        score = Tulu3Score(
            instruction_following=3.5,
            truthfulness=3.2,
            honesty=3.8,
            helpfulness=3.4,
            total_examples=250
        )

        # Assert - overall score should be in medium range
        expected_avg = (3.5 + 3.2 + 3.8 + 3.4) / 4.0
        assert score.overall_score == pytest.approx(expected_avg, abs=0.01)
        assert 3.0 <= score.overall_score < 4.0
        assert score.quality_tier == "MEDIUM"

    def test_tulu3_score_high_quality(self):
        """Test Tulu3Score with high quality scores (>=4.0)."""
        from training_metrics import Tulu3Score

        # Arrange - high quality (avg >= 4.0)
        score = Tulu3Score(
            instruction_following=4.2,
            truthfulness=4.5,
            honesty=4.3,
            helpfulness=4.6,
            total_examples=500
        )

        # Assert - overall score should be >= 4.0
        expected_avg = (4.2 + 4.5 + 4.3 + 4.6) / 4.0
        assert score.overall_score == pytest.approx(expected_avg, abs=0.01)
        assert score.overall_score >= 4.0
        assert score.quality_tier == "HIGH"

    def test_tulu3_score_perfect_quality(self):
        """Test Tulu3Score with perfect quality (all 5s)."""
        from training_metrics import Tulu3Score

        # Arrange - perfect quality (all dimensions = 5.0)
        score = Tulu3Score(
            instruction_following=5.0,
            truthfulness=5.0,
            honesty=5.0,
            helpfulness=5.0,
            total_examples=1000
        )

        # Assert - overall score should be exactly 5.0
        assert score.overall_score == 5.0
        assert score.quality_tier == "HIGH"

    def test_tulu3_score_post_init_calculation(self):
        """Test that __post_init__ correctly calculates overall_score and quality_tier."""
        from training_metrics import Tulu3Score

        # Arrange - create score without providing overall_score/quality_tier
        score = Tulu3Score(
            instruction_following=3.7,
            truthfulness=3.9,
            honesty=4.1,
            helpfulness=3.8,
            total_examples=300
        )

        # Assert - __post_init__ should have calculated these fields
        expected_avg = (3.7 + 3.9 + 4.1 + 3.8) / 4.0
        assert score.overall_score == pytest.approx(expected_avg, abs=0.01)
        assert score.quality_tier in ["LOW", "MEDIUM", "HIGH"]

    def test_tulu3_score_boundary_3_0(self):
        """Test Tulu3Score at exact 3.0 boundary (MEDIUM tier threshold)."""
        from training_metrics import Tulu3Score

        # Arrange - exactly at 3.0 threshold
        score = Tulu3Score(
            instruction_following=3.0,
            truthfulness=3.0,
            honesty=3.0,
            helpfulness=3.0,
            total_examples=200
        )

        # Assert - should be MEDIUM tier (3.0 is inclusive)
        assert score.overall_score == 3.0
        assert score.quality_tier == "MEDIUM"

    def test_tulu3_score_boundary_4_0(self):
        """Test Tulu3Score at exact 4.0 boundary (HIGH tier threshold)."""
        from training_metrics import Tulu3Score

        # Arrange - exactly at 4.0 threshold
        score = Tulu3Score(
            instruction_following=4.0,
            truthfulness=4.0,
            honesty=4.0,
            helpfulness=4.0,
            total_examples=400
        )

        # Assert - should be HIGH tier (4.0 is inclusive)
        assert score.overall_score == 4.0
        assert score.quality_tier == "HIGH"


# ============================================================================
# PHASE 3: calculate_tulu3_score() Tests (6 tests)
# ============================================================================


class TestCalculateTulu3Score:
    """Test calculate_tulu3_score() function for Tulu3 scoring."""

    @pytest.fixture
    def mock_validate_path(self):
        """Mock validate_path to return input path."""
        with patch('training_metrics.validate_path') as mock:
            mock.side_effect = lambda path, *args, **kwargs: path
            yield mock

    @pytest.fixture
    def mock_audit_log(self):
        """Mock audit_log to prevent actual logging."""
        with patch('training_metrics.audit_log') as mock:
            yield mock

    def test_calculate_tulu3_score_valid_data(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test calculate_tulu3_score() with valid JSONL dataset."""
        from training_metrics import calculate_tulu3_score

        # Arrange - create valid JSONL dataset
        dataset_path = tmp_path / "tulu3_dataset.jsonl"
        examples = [
            {
                "instruction": "Explain quantum computing",
                "response": "Quantum computing uses quantum mechanics...",
                "instruction_following": 4.5,
                "truthfulness": 4.2,
                "honesty": 4.8,
                "helpfulness": 4.3
            },
            {
                "instruction": "Write a sorting algorithm",
                "response": "Here's a quicksort implementation...",
                "instruction_following": 4.8,
                "truthfulness": 5.0,
                "honesty": 5.0,
                "helpfulness": 4.9
            },
            {
                "instruction": "Summarize climate change",
                "response": "Climate change refers to...",
                "instruction_following": 4.0,
                "truthfulness": 4.5,
                "honesty": 4.3,
                "helpfulness": 4.2
            }
        ]

        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')

        # Act
        score = calculate_tulu3_score(dataset_path)

        # Assert - should calculate average scores across dimensions
        assert score.total_examples == 3
        assert score.instruction_following == pytest.approx((4.5 + 4.8 + 4.0) / 3.0, abs=0.01)
        assert score.truthfulness == pytest.approx((4.2 + 5.0 + 4.5) / 3.0, abs=0.01)
        assert score.honesty == pytest.approx((4.8 + 5.0 + 4.3) / 3.0, abs=0.01)
        assert score.helpfulness == pytest.approx((4.3 + 4.9 + 4.2) / 3.0, abs=0.01)
        assert score.quality_tier == "HIGH"

        # Verify security functions called
        mock_validate_path.assert_called_once()
        mock_audit_log.assert_called()

    def test_calculate_tulu3_score_invalid_data(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test calculate_tulu3_score() with invalid JSONL format."""
        from training_metrics import calculate_tulu3_score

        # Arrange - create invalid JSONL (missing required fields)
        dataset_path = tmp_path / "invalid_dataset.jsonl"
        invalid_examples = [
            {"instruction": "Test", "response": "Response"},  # Missing Tulu3 dimensions
            {"instruction": "Test 2"}  # Missing response and dimensions
        ]

        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in invalid_examples:
                f.write(json.dumps(example) + '\n')

        # Act & Assert - should raise ValueError for missing fields
        with pytest.raises(ValueError) as exc_info:
            calculate_tulu3_score(dataset_path)

        assert "missing" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()
        mock_audit_log.assert_called()

    def test_calculate_tulu3_score_missing_file(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test calculate_tulu3_score() with non-existent file."""
        from training_metrics import calculate_tulu3_score

        # Arrange - non-existent file path
        dataset_path = tmp_path / "nonexistent.jsonl"

        # Act & Assert - should raise FileNotFoundError
        with pytest.raises(FileNotFoundError) as exc_info:
            calculate_tulu3_score(dataset_path)

        assert "not found" in str(exc_info.value).lower()
        mock_audit_log.assert_called()

    def test_calculate_tulu3_score_empty_file(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test calculate_tulu3_score() with empty JSONL file."""
        from training_metrics import calculate_tulu3_score

        # Arrange - empty file
        dataset_path = tmp_path / "empty_dataset.jsonl"
        dataset_path.write_text("")

        # Act
        score = calculate_tulu3_score(dataset_path)

        # Assert - should return INSUFFICIENT tier for empty dataset
        assert score.total_examples == 0
        assert score.overall_score == 0.0
        assert score.quality_tier == "INSUFFICIENT"
        mock_audit_log.assert_called()

    def test_calculate_tulu3_score_security_validation(self, tmp_path, mock_audit_log):
        """Test calculate_tulu3_score() security path validation (CWE-22)."""
        from training_metrics import calculate_tulu3_score

        # Arrange - mock validate_path to raise exception
        with patch('training_metrics.validate_path') as mock_validate:
            mock_validate.side_effect = ValueError("Path traversal detected")
            dataset_path = tmp_path / "../../../etc/passwd"

            # Act & Assert - should propagate validation error
            with pytest.raises(ValueError) as exc_info:
                calculate_tulu3_score(dataset_path)

            assert "path" in str(exc_info.value).lower()
            mock_validate.assert_called_once()
            mock_audit_log.assert_called()

    def test_calculate_tulu3_score_large_dataset(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test calculate_tulu3_score() with large dataset (1000+ examples)."""
        from training_metrics import calculate_tulu3_score

        # Arrange - create large dataset
        dataset_path = tmp_path / "large_dataset.jsonl"
        num_examples = 1500

        with open(dataset_path, 'w', encoding='utf-8') as f:
            for i in range(num_examples):
                example = {
                    "instruction": f"Task {i}",
                    "response": f"Response {i}",
                    "instruction_following": 4.0 + (i % 10) * 0.1,
                    "truthfulness": 4.2 + (i % 8) * 0.1,
                    "honesty": 4.5 + (i % 6) * 0.05,
                    "helpfulness": 4.3 + (i % 7) * 0.1
                }
                f.write(json.dumps(example) + '\n')

        # Act
        score = calculate_tulu3_score(dataset_path)

        # Assert - should handle large dataset correctly
        assert score.total_examples == num_examples
        assert score.overall_score > 0.0
        assert score.quality_tier in ["LOW", "MEDIUM", "HIGH"]
        mock_audit_log.assert_called()


# ============================================================================
# PHASE 4: generate_dpo_preferences() Tests (5 tests)
# ============================================================================


class TestGenerateDPOPreferences:
    """Test generate_dpo_preferences() function for DPO pair generation."""

    @pytest.fixture
    def mock_validate_path(self):
        """Mock validate_path to return input path."""
        with patch('training_metrics.validate_path') as mock:
            mock.side_effect = lambda path, *args, **kwargs: path
            yield mock

    @pytest.fixture
    def mock_audit_log(self):
        """Mock audit_log to prevent actual logging."""
        with patch('training_metrics.audit_log') as mock:
            yield mock

    def test_generate_dpo_preferences_basic(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test generate_dpo_preferences() with basic dataset."""
        from training_metrics import generate_dpo_preferences

        # Arrange - create dataset with Tulu3 scores
        input_path = tmp_path / "tulu3_input.jsonl"
        examples = [
            {
                "instruction": "Explain AI",
                "responses": [
                    {
                        "text": "AI is artificial intelligence...",
                        "instruction_following": 5.0,
                        "truthfulness": 5.0,
                        "honesty": 5.0,
                        "helpfulness": 5.0
                    },
                    {
                        "text": "AI is computers.",
                        "instruction_following": 2.0,
                        "truthfulness": 3.0,
                        "honesty": 4.0,
                        "helpfulness": 2.5
                    }
                ]
            }
        ]

        with open(input_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')

        output_path = tmp_path / "dpo_output.jsonl"

        # Act
        result = generate_dpo_preferences(input_path, output_path)

        # Assert - should create DPO pairs (chosen vs rejected)
        assert result["pairs_created"] == 1
        assert output_path.exists()

        # Verify DPO pair format
        with open(output_path, 'r', encoding='utf-8') as f:
            pair = json.loads(f.readline())
            assert "prompt" in pair
            assert "chosen" in pair
            assert "rejected" in pair
            assert pair["prompt"] == "Explain AI"
            # Higher scoring response should be chosen
            assert "artificial intelligence" in pair["chosen"].lower()
            assert pair["rejected"] == "AI is computers."

        mock_validate_path.assert_called()
        mock_audit_log.assert_called()

    def test_generate_dpo_preferences_multiple_responses(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test generate_dpo_preferences() with multiple responses per prompt."""
        from training_metrics import generate_dpo_preferences

        # Arrange - dataset with 3+ responses per prompt
        input_path = tmp_path / "multi_response.jsonl"
        examples = [
            {
                "instruction": "Sort numbers",
                "responses": [
                    {
                        "text": "Use quicksort for O(n log n) performance",
                        "instruction_following": 5.0,
                        "truthfulness": 5.0,
                        "honesty": 5.0,
                        "helpfulness": 5.0
                    },
                    {
                        "text": "Use bubble sort",
                        "instruction_following": 3.0,
                        "truthfulness": 4.0,
                        "honesty": 4.5,
                        "helpfulness": 3.5
                    },
                    {
                        "text": "Sort them manually",
                        "instruction_following": 2.0,
                        "truthfulness": 3.0,
                        "honesty": 4.0,
                        "helpfulness": 2.0
                    }
                ]
            }
        ]

        with open(input_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')

        output_path = tmp_path / "dpo_multi.jsonl"

        # Act
        result = generate_dpo_preferences(input_path, output_path)

        # Assert - should create multiple pairs from 3 responses
        # Combination logic: C(3,2) = 3 pairs, or just best vs worst
        assert result["pairs_created"] >= 1
        assert output_path.exists()

        mock_validate_path.assert_called()
        mock_audit_log.assert_called()

    def test_generate_dpo_preferences_missing_file(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test generate_dpo_preferences() with non-existent input file."""
        from training_metrics import generate_dpo_preferences

        # Arrange - non-existent input file
        input_path = tmp_path / "nonexistent.jsonl"
        output_path = tmp_path / "output.jsonl"

        # Act & Assert - should raise FileNotFoundError
        with pytest.raises(FileNotFoundError) as exc_info:
            generate_dpo_preferences(input_path, output_path)

        assert "not found" in str(exc_info.value).lower()
        mock_audit_log.assert_called()

    def test_generate_dpo_preferences_security(self, tmp_path, mock_audit_log):
        """Test generate_dpo_preferences() security validation (CWE-22)."""
        from training_metrics import generate_dpo_preferences

        # Arrange - mock validate_path to raise exception
        with patch('training_metrics.validate_path') as mock_validate:
            mock_validate.side_effect = ValueError("Path traversal detected")
            input_path = tmp_path / "../../../etc/passwd"
            output_path = tmp_path / "output.jsonl"

            # Act & Assert - should propagate validation error
            with pytest.raises(ValueError) as exc_info:
                generate_dpo_preferences(input_path, output_path)

            assert "path" in str(exc_info.value).lower()
            mock_validate.assert_called()
            mock_audit_log.assert_called()

    def test_generate_dpo_preferences_output_verification(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test generate_dpo_preferences() output file format verification."""
        from training_metrics import generate_dpo_preferences

        # Arrange - create dataset with clear quality differences
        input_path = tmp_path / "input.jsonl"
        examples = [
            {
                "instruction": "Define recursion",
                "responses": [
                    {
                        "text": "Recursion is when a function calls itself with a base case to prevent infinite loops",
                        "instruction_following": 5.0,
                        "truthfulness": 5.0,
                        "honesty": 5.0,
                        "helpfulness": 5.0
                    },
                    {
                        "text": "Recursion is recursion",
                        "instruction_following": 1.0,
                        "truthfulness": 2.0,
                        "honesty": 3.0,
                        "helpfulness": 1.5
                    }
                ]
            },
            {
                "instruction": "Explain loops",
                "responses": [
                    {
                        "text": "Loops iterate over sequences or conditions",
                        "instruction_following": 4.5,
                        "truthfulness": 4.8,
                        "honesty": 5.0,
                        "helpfulness": 4.6
                    },
                    {
                        "text": "Loops loop",
                        "instruction_following": 1.5,
                        "truthfulness": 2.5,
                        "honesty": 3.5,
                        "helpfulness": 2.0
                    }
                ]
            }
        ]

        with open(input_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')

        output_path = tmp_path / "dpo_verified.jsonl"

        # Act
        result = generate_dpo_preferences(input_path, output_path)

        # Assert - verify output format and quality
        assert result["pairs_created"] == 2
        assert output_path.exists()

        # Verify each DPO pair has correct format and quality ordering
        with open(output_path, 'r', encoding='utf-8') as f:
            pairs = [json.loads(line) for line in f if line.strip()]

            assert len(pairs) == 2

            for pair in pairs:
                assert "prompt" in pair
                assert "chosen" in pair
                assert "rejected" in pair
                assert len(pair["chosen"]) > len(pair["rejected"])  # Better response should be more detailed

        mock_validate_path.assert_called()
        mock_audit_log.assert_called()


# ============================================================================
# Integration Tests (Optional - test Tulu3 workflow end-to-end)
# ============================================================================


class TestTulu3Integration:
    """Integration tests for complete Tulu3 scoring workflow."""

    @pytest.fixture
    def mock_validate_path(self):
        """Mock validate_path to return input path."""
        with patch('training_metrics.validate_path') as mock:
            mock.side_effect = lambda path, *args, **kwargs: path
            yield mock

    @pytest.fixture
    def mock_audit_log(self):
        """Mock audit_log to prevent actual logging."""
        with patch('training_metrics.audit_log') as mock:
            yield mock

    def test_tulu3_workflow_end_to_end(self, tmp_path, mock_validate_path, mock_audit_log):
        """Test complete Tulu3 workflow: score dataset → generate DPO pairs."""
        from training_metrics import calculate_tulu3_score, generate_dpo_preferences

        # Arrange - create Tulu3 dataset
        dataset_path = tmp_path / "tulu3_full.jsonl"
        examples = [
            {
                "instruction": "Explain machine learning",
                "response": "Machine learning is a subset of AI...",
                "instruction_following": 4.8,
                "truthfulness": 4.9,
                "honesty": 5.0,
                "helpfulness": 4.7,
                "responses": [
                    {
                        "text": "Machine learning is a subset of AI that enables systems to learn from data",
                        "instruction_following": 4.8,
                        "truthfulness": 4.9,
                        "honesty": 5.0,
                        "helpfulness": 4.7
                    },
                    {
                        "text": "ML is AI",
                        "instruction_following": 2.0,
                        "truthfulness": 3.0,
                        "honesty": 3.5,
                        "helpfulness": 2.5
                    }
                ]
            }
        ]

        with open(dataset_path, 'w', encoding='utf-8') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')

        dpo_output = tmp_path / "dpo_final.jsonl"

        # Act - run full workflow
        # Step 1: Calculate Tulu3 score
        score = calculate_tulu3_score(dataset_path)

        # Step 2: Generate DPO preferences
        dpo_result = generate_dpo_preferences(dataset_path, dpo_output)

        # Assert - verify workflow completed successfully
        assert score.quality_tier == "HIGH"
        assert score.overall_score >= 4.0
        assert dpo_result["pairs_created"] >= 1
        assert dpo_output.exists()

        mock_validate_path.assert_called()
        mock_audit_log.assert_called()

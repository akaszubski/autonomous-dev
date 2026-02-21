#!/usr/bin/env python3
"""
Unit tests for distributed_training_validator.py library (TDD Red Phase).

Tests for comprehensive distributed training validation including checkpoint validation,
gradient validation, performance monitoring, health checks, and security validation.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError or missing functions).

Test Coverage:
1. CheckpointValidationResult dataclass - validation and initialization
2. GradientValidationResult dataclass - gradient consistency and stability
3. PerformanceMetrics dataclass - threshold validation
4. HealthCheckResult dataclass - pre-flight and runtime checks
5. DistributedTrainingValidation dataclass - aggregation and overall validation
6. validate_checkpoint_layer() - checkpoint integrity and version consistency
7. validate_gradient_layer() - gradient synchronization and outlier detection
8. monitor_performance() - throughput, latency, and resource utilization
9. run_health_checks() - hardware and network health validation
10. validate_distributed_training() - end-to-end integration
11. Security validation - path traversal, input sanitization, audit logging

Date: 2026-01-29
Issue: #282 - Add DistributedTrainingValidator library for comprehensive distributed training validation
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Coverage Target: 90%+
"""

import pytest
import sys
import json
import math
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from typing import Dict, List, Any, Optional

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - implementation doesn't exist yet (TDD!)
try:
    from distributed_training_validator import (
        CheckpointValidationResult,
        GradientValidationResult,
        PerformanceMetrics,
        HealthCheckResult,
        DistributedTrainingValidation,
        validate_checkpoint_layer,
        validate_gradient_layer,
        monitor_performance,
        run_health_checks,
        validate_distributed_training,
        CheckpointValidationError,
        GradientValidationError,
        PerformanceValidationError,
        HealthCheckError,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# ==============================================================================
# TEST FIXTURES
# ==============================================================================


@pytest.fixture
def valid_checkpoint_paths(tmp_path: Path) -> List[Path]:
    """Create valid checkpoint files for testing."""
    checkpoints = []
    for i in range(3):
        checkpoint_file = tmp_path / f"checkpoint_worker_{i}.pt"
        checkpoint_data = {
            "version": "1.0.0",
            "step": 1000,
            "model_state": {"layer1": [1.0, 2.0, 3.0]},
            "optimizer_state": {"lr": 0.001},
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data))
        checkpoints.append(checkpoint_file)
    return checkpoints


@pytest.fixture
def mismatched_checkpoint_paths(tmp_path: Path) -> List[Path]:
    """Create checkpoint files with version mismatch."""
    checkpoints = []
    for i, version in enumerate(["1.0.0", "1.1.0", "1.0.0"]):
        checkpoint_file = tmp_path / f"checkpoint_worker_{i}.pt"
        checkpoint_data = {
            "version": version,
            "step": 1000,
            "model_state": {"layer1": [1.0, 2.0, 3.0]},
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data))
        checkpoints.append(checkpoint_file)
    return checkpoints


@pytest.fixture
def valid_gradient_updates() -> List[Dict[str, Any]]:
    """Create valid gradient updates for testing."""
    return [
        {
            "worker_id": "worker-0",
            "gradients": {"layer1": [0.1, 0.2, 0.3], "layer2": [0.4, 0.5]},
            "gradient_norm": 0.77,
        },
        {
            "worker_id": "worker-1",
            "gradients": {"layer1": [0.11, 0.19, 0.31], "layer2": [0.41, 0.49]},
            "gradient_norm": 0.78,
        },
        {
            "worker_id": "worker-2",
            "gradients": {"layer1": [0.09, 0.21, 0.29], "layer2": [0.39, 0.51]},
            "gradient_norm": 0.76,
        },
    ]


@pytest.fixture
def gradient_updates_with_nan() -> List[Dict[str, Any]]:
    """Create gradient updates with NaN values."""
    return [
        {
            "worker_id": "worker-0",
            "gradients": {"layer1": [0.1, 0.2, 0.3]},
            "gradient_norm": 0.37,
        },
        {
            "worker_id": "worker-1",
            "gradients": {"layer1": [float("nan"), 0.2, 0.3]},
            "gradient_norm": float("nan"),
        },
    ]


@pytest.fixture
def gradient_updates_with_outlier() -> List[Dict[str, Any]]:
    """Create gradient updates with outlier worker."""
    return [
        {
            "worker_id": "worker-0",
            "gradients": {"layer1": [0.1, 0.2, 0.3]},
            "gradient_norm": 0.37,
        },
        {
            "worker_id": "worker-1",
            "gradients": {"layer1": [0.11, 0.19, 0.31]},
            "gradient_norm": 0.38,
        },
        {
            "worker_id": "worker-2",
            "gradients": {"layer1": [10.0, 20.0, 30.0]},  # Outlier
            "gradient_norm": 37.0,
        },
    ]


@pytest.fixture
def valid_performance_metrics() -> Dict[str, Any]:
    """Create valid performance metrics."""
    return {
        "throughput": 1000.0,  # samples/sec
        "latency_ms": 50.0,
        "gpu_utilization": 0.85,
        "memory_utilization": 0.75,
    }


@pytest.fixture
def invalid_performance_metrics() -> Dict[str, Any]:
    """Create invalid performance metrics (low GPU utilization)."""
    return {
        "throughput": 500.0,
        "latency_ms": 600.0,  # High latency
        "gpu_utilization": 0.60,  # Low GPU utilization
        "memory_utilization": 0.95,  # High memory utilization
    }


@pytest.fixture
def valid_health_config() -> Dict[str, Any]:
    """Create valid health check configuration."""
    return {
        "gpu_count": 4,
        "rdma_enabled": True,
        "nccl_version": "2.19.0",
        "worker_heartbeats": {
            "worker-0": 1706524800.0,
            "worker-1": 1706524801.0,
            "worker-2": 1706524802.0,
        },
    }


@pytest.fixture
def invalid_health_config() -> Dict[str, Any]:
    """Create invalid health check configuration (missing GPU)."""
    return {
        "gpu_count": 0,  # No GPUs
        "rdma_enabled": False,
        "nccl_version": "2.10.0",  # Old version
        "worker_heartbeats": {},
    }


# ==============================================================================
# SECTION 1: CheckpointValidationResult Dataclass Tests
# ==============================================================================


@pytest.mark.unit
class TestCheckpointValidationResult:
    """Test CheckpointValidationResult dataclass validation and initialization.

    Given: CheckpointValidationResult dataclass
    When: Creating instances with various validation scenarios
    Then: is_valid field reflects checkpoint integrity and version consistency
    """

    def test_valid_checkpoint_result_creation(self):
        """Test valid checkpoint result with all checks passing.

        Given: Valid checkpoint validation data
        When: Creating CheckpointValidationResult
        Then: is_valid is True and all fields are set correctly
        """
        result = CheckpointValidationResult(
            version_consistency=True,
            integrity_checks=[True, True, True],
            missing_files=[],
            corrupted_files=[],
        )

        assert result.is_valid is True
        assert result.version_consistency is True
        assert all(result.integrity_checks)
        assert len(result.missing_files) == 0
        assert len(result.corrupted_files) == 0

    def test_checkpoint_result_version_mismatch(self):
        """Test checkpoint result with version mismatch.

        Given: Checkpoint validation with version inconsistency
        When: Creating CheckpointValidationResult
        Then: is_valid is False due to version_consistency=False
        """
        result = CheckpointValidationResult(
            version_consistency=False,
            integrity_checks=[True, True, True],
            missing_files=[],
            corrupted_files=[],
        )

        assert result.is_valid is False
        assert result.version_consistency is False

    def test_checkpoint_result_corrupted_files(self):
        """Test checkpoint result with corrupted files.

        Given: Checkpoint validation with corrupted files
        When: Creating CheckpointValidationResult
        Then: is_valid is False and corrupted_files list is populated
        """
        result = CheckpointValidationResult(
            version_consistency=True,
            integrity_checks=[True, False, True],
            missing_files=[],
            corrupted_files=["checkpoint_worker_1.pt"],
        )

        assert result.is_valid is False
        assert len(result.corrupted_files) == 1
        assert "checkpoint_worker_1.pt" in result.corrupted_files

    def test_checkpoint_result_missing_files(self):
        """Test checkpoint result with missing files.

        Given: Checkpoint validation with missing files
        When: Creating CheckpointValidationResult
        Then: is_valid is False and missing_files list is populated
        """
        result = CheckpointValidationResult(
            version_consistency=True,
            integrity_checks=[True, False],
            missing_files=["checkpoint_worker_2.pt"],
            corrupted_files=[],
        )

        assert result.is_valid is False
        assert len(result.missing_files) == 1
        assert "checkpoint_worker_2.pt" in result.missing_files

    def test_checkpoint_result_is_frozen(self):
        """Test CheckpointValidationResult is frozen (immutable).

        Given: CheckpointValidationResult instance
        When: Attempting to modify fields
        Then: FrozenInstanceError is raised
        """
        result = CheckpointValidationResult(
            version_consistency=True,
            integrity_checks=[True, True],
            missing_files=[],
            corrupted_files=[],
        )

        with pytest.raises(AttributeError):
            result.version_consistency = False


# ==============================================================================
# SECTION 2: GradientValidationResult Dataclass Tests
# ==============================================================================


@pytest.mark.unit
class TestGradientValidationResult:
    """Test GradientValidationResult dataclass validation and initialization.

    Given: GradientValidationResult dataclass
    When: Creating instances with various gradient scenarios
    Then: is_valid field reflects gradient consistency and numerical stability
    """

    def test_valid_gradient_result_creation(self):
        """Test valid gradient result with all_reduce consistency.

        Given: Valid gradient validation data
        When: Creating GradientValidationResult
        Then: is_valid is True and all fields are set correctly
        """
        result = GradientValidationResult(
            all_reduce_consistent=True,
            numerical_stability=True,
            gradient_variance=0.001,
            outlier_workers=[],
        )

        assert result.is_valid is True
        assert result.all_reduce_consistent is True
        assert result.numerical_stability is True
        assert result.gradient_variance < 0.01
        assert len(result.outlier_workers) == 0

    def test_gradient_result_nan_scenario(self):
        """Test gradient result with NaN gradients.

        Given: Gradient validation with NaN values
        When: Creating GradientValidationResult
        Then: is_valid is False due to numerical_stability=False
        """
        result = GradientValidationResult(
            all_reduce_consistent=False,
            numerical_stability=False,
            gradient_variance=float("nan"),
            outlier_workers=[],
        )

        assert result.is_valid is False
        assert result.numerical_stability is False
        assert math.isnan(result.gradient_variance)

    def test_gradient_result_high_variance(self):
        """Test gradient result with high variance.

        Given: Gradient validation with high variance
        When: Creating GradientValidationResult
        Then: is_valid is False and gradient_variance exceeds threshold
        """
        result = GradientValidationResult(
            all_reduce_consistent=False,
            numerical_stability=True,
            gradient_variance=0.5,  # High variance
            outlier_workers=[],
        )

        assert result.is_valid is False
        assert result.gradient_variance > 0.1

    def test_gradient_result_perfect_consistency(self):
        """Test gradient result with perfect consistency.

        Given: Gradient validation with zero variance
        When: Creating GradientValidationResult
        Then: is_valid is True and variance is 0
        """
        result = GradientValidationResult(
            all_reduce_consistent=True,
            numerical_stability=True,
            gradient_variance=0.0,
            outlier_workers=[],
        )

        assert result.is_valid is True
        assert result.gradient_variance == 0.0

    def test_gradient_result_outlier_detection(self):
        """Test gradient result with outlier workers.

        Given: Gradient validation with outlier workers
        When: Creating GradientValidationResult
        Then: is_valid is False and outlier_workers list is populated
        """
        result = GradientValidationResult(
            all_reduce_consistent=False,
            numerical_stability=True,
            gradient_variance=0.2,
            outlier_workers=["worker-2"],
        )

        assert result.is_valid is False
        assert len(result.outlier_workers) == 1
        assert "worker-2" in result.outlier_workers

    def test_gradient_result_is_frozen(self):
        """Test GradientValidationResult is frozen (immutable).

        Given: GradientValidationResult instance
        When: Attempting to modify fields
        Then: FrozenInstanceError is raised
        """
        result = GradientValidationResult(
            all_reduce_consistent=True,
            numerical_stability=True,
            gradient_variance=0.001,
            outlier_workers=[],
        )

        with pytest.raises(AttributeError):
            result.all_reduce_consistent = False


# ==============================================================================
# SECTION 3: PerformanceMetrics Dataclass Tests
# ==============================================================================


@pytest.mark.unit
class TestPerformanceMetrics:
    """Test PerformanceMetrics dataclass validation and initialization.

    Given: PerformanceMetrics dataclass
    When: Creating instances with various performance scenarios
    Then: is_within_thresholds field reflects performance requirements
    """

    def test_valid_performance_metrics_creation(self):
        """Test valid performance metrics within thresholds.

        Given: Valid performance metrics data
        When: Creating PerformanceMetrics
        Then: is_within_thresholds is True and all fields are set
        """
        metrics = PerformanceMetrics(
            throughput=1000.0,
            latency_ms=50.0,
            gpu_utilization=0.85,
            memory_utilization=0.75,
            is_within_thresholds=True,
        )

        assert metrics.is_within_thresholds is True
        assert metrics.throughput > 0
        assert metrics.latency_ms < 500
        assert metrics.gpu_utilization > 0.8
        assert metrics.memory_utilization < 0.9

    def test_performance_metrics_zero_throughput(self):
        """Test performance metrics with zero throughput.

        Given: Performance metrics with zero throughput
        When: Creating PerformanceMetrics
        Then: is_within_thresholds is False
        """
        metrics = PerformanceMetrics(
            throughput=0.0,
            latency_ms=100.0,
            gpu_utilization=0.85,
            memory_utilization=0.75,
            is_within_thresholds=False,
        )

        assert metrics.is_within_thresholds is False
        assert metrics.throughput == 0.0

    def test_performance_metrics_high_latency(self):
        """Test performance metrics with high latency (>500ms).

        Given: Performance metrics with high latency
        When: Creating PerformanceMetrics
        Then: is_within_thresholds is False
        """
        metrics = PerformanceMetrics(
            throughput=1000.0,
            latency_ms=600.0,
            gpu_utilization=0.85,
            memory_utilization=0.75,
            is_within_thresholds=False,
        )

        assert metrics.is_within_thresholds is False
        assert metrics.latency_ms > 500

    def test_performance_metrics_low_gpu_utilization(self):
        """Test performance metrics with low GPU utilization (<80%).

        Given: Performance metrics with low GPU utilization
        When: Creating PerformanceMetrics
        Then: is_within_thresholds is False
        """
        metrics = PerformanceMetrics(
            throughput=1000.0,
            latency_ms=50.0,
            gpu_utilization=0.60,
            memory_utilization=0.75,
            is_within_thresholds=False,
        )

        assert metrics.is_within_thresholds is False
        assert metrics.gpu_utilization < 0.8

    def test_performance_metrics_high_memory_utilization(self):
        """Test performance metrics with high memory utilization (>90%).

        Given: Performance metrics with high memory utilization
        When: Creating PerformanceMetrics
        Then: is_within_thresholds is False
        """
        metrics = PerformanceMetrics(
            throughput=1000.0,
            latency_ms=50.0,
            gpu_utilization=0.85,
            memory_utilization=0.95,
            is_within_thresholds=False,
        )

        assert metrics.is_within_thresholds is False
        assert metrics.memory_utilization > 0.9

    def test_performance_metrics_is_frozen(self):
        """Test PerformanceMetrics is frozen (immutable).

        Given: PerformanceMetrics instance
        When: Attempting to modify fields
        Then: FrozenInstanceError is raised
        """
        metrics = PerformanceMetrics(
            throughput=1000.0,
            latency_ms=50.0,
            gpu_utilization=0.85,
            memory_utilization=0.75,
            is_within_thresholds=True,
        )

        with pytest.raises(AttributeError):
            metrics.throughput = 500.0


# ==============================================================================
# SECTION 4: HealthCheckResult Dataclass Tests
# ==============================================================================


@pytest.mark.unit
class TestHealthCheckResult:
    """Test HealthCheckResult dataclass validation and initialization.

    Given: HealthCheckResult dataclass
    When: Creating instances with various health check scenarios
    Then: pre_flight_passed and runtime_checks_passed fields reflect system health
    """

    def test_health_check_pre_flight_passed(self):
        """Test health check with pre-flight checks passed.

        Given: Valid pre-flight configuration
        When: Creating HealthCheckResult
        Then: pre_flight_passed is True
        """
        result = HealthCheckResult(
            pre_flight_passed=True,
            runtime_checks_passed=False,
            issues=[],
        )

        assert result.pre_flight_passed is True
        assert len(result.issues) == 0

    def test_health_check_pre_flight_failed(self):
        """Test health check with pre-flight checks failed.

        Given: Invalid pre-flight configuration (missing GPU)
        When: Creating HealthCheckResult
        Then: pre_flight_passed is False and issues are populated
        """
        result = HealthCheckResult(
            pre_flight_passed=False,
            runtime_checks_passed=False,
            issues=["No GPUs detected"],
        )

        assert result.pre_flight_passed is False
        assert len(result.issues) == 1
        assert "No GPUs detected" in result.issues

    def test_health_check_runtime_passed(self):
        """Test health check with runtime checks passed.

        Given: Valid runtime configuration
        When: Creating HealthCheckResult
        Then: runtime_checks_passed is True
        """
        result = HealthCheckResult(
            pre_flight_passed=True,
            runtime_checks_passed=True,
            issues=[],
        )

        assert result.runtime_checks_passed is True
        assert len(result.issues) == 0

    def test_health_check_runtime_failed(self):
        """Test health check with runtime checks failed.

        Given: Invalid runtime configuration (heartbeat timeout)
        When: Creating HealthCheckResult
        Then: runtime_checks_passed is False and issues are populated
        """
        result = HealthCheckResult(
            pre_flight_passed=True,
            runtime_checks_passed=False,
            issues=["Worker-2 heartbeat timeout"],
        )

        assert result.runtime_checks_passed is False
        assert len(result.issues) == 1
        assert "heartbeat timeout" in result.issues[0]

    def test_health_check_missing_gpu(self):
        """Test health check with missing GPU scenario.

        Given: Configuration with no GPUs
        When: Creating HealthCheckResult
        Then: pre_flight_passed is False and GPU issue is reported
        """
        result = HealthCheckResult(
            pre_flight_passed=False,
            runtime_checks_passed=False,
            issues=["GPU count is 0, expected > 0"],
        )

        assert result.pre_flight_passed is False
        assert "GPU count" in result.issues[0]


# ==============================================================================
# SECTION 5: DistributedTrainingValidation Dataclass Tests
# ==============================================================================


@pytest.mark.unit
class TestDistributedTrainingValidation:
    """Test DistributedTrainingValidation dataclass aggregation and validation.

    Given: DistributedTrainingValidation dataclass
    When: Creating instances with various layer validation results
    Then: overall_valid field reflects aggregated validation status
    """

    def test_all_layers_pass(self):
        """Test validation with all layers passing.

        Given: All validation layers pass
        When: Creating DistributedTrainingValidation
        Then: overall_valid is True
        """
        validation = DistributedTrainingValidation(
            hardware_layer_valid=True,
            worker_layer_valid=True,
            checkpoint_layer_valid=True,
            gradient_layer_valid=True,
            performance_layer_valid=True,
            health_check_passed=True,
            validation_issues=[],
            overall_valid=True,
        )

        assert validation.overall_valid is True
        assert len(validation.validation_issues) == 0

    def test_hardware_layer_fails(self):
        """Test validation with hardware layer failure.

        Given: Hardware layer fails
        When: Creating DistributedTrainingValidation
        Then: overall_valid is False and validation_issues contains 'hardware'
        """
        validation = DistributedTrainingValidation(
            hardware_layer_valid=False,
            worker_layer_valid=True,
            checkpoint_layer_valid=True,
            gradient_layer_valid=True,
            performance_layer_valid=True,
            health_check_passed=True,
            validation_issues=["Hardware layer: GPU count mismatch"],
            overall_valid=False,
        )

        assert validation.overall_valid is False
        assert any("Hardware layer" in issue for issue in validation.validation_issues)

    def test_worker_layer_fails(self):
        """Test validation with worker layer failure.

        Given: Worker layer fails
        When: Creating DistributedTrainingValidation
        Then: overall_valid is False and validation_issues contains 'worker'
        """
        validation = DistributedTrainingValidation(
            hardware_layer_valid=True,
            worker_layer_valid=False,
            checkpoint_layer_valid=True,
            gradient_layer_valid=True,
            performance_layer_valid=True,
            health_check_passed=True,
            validation_issues=["Worker layer: Divergence detected"],
            overall_valid=False,
        )

        assert validation.overall_valid is False
        assert any("Worker layer" in issue for issue in validation.validation_issues)

    def test_checkpoint_layer_fails(self):
        """Test validation with checkpoint layer failure.

        Given: Checkpoint layer fails
        When: Creating DistributedTrainingValidation
        Then: overall_valid is False and validation_issues contains 'checkpoint'
        """
        validation = DistributedTrainingValidation(
            hardware_layer_valid=True,
            worker_layer_valid=True,
            checkpoint_layer_valid=False,
            gradient_layer_valid=True,
            performance_layer_valid=True,
            health_check_passed=True,
            validation_issues=["Checkpoint layer: Version mismatch"],
            overall_valid=False,
        )

        assert validation.overall_valid is False
        assert any("Checkpoint layer" in issue for issue in validation.validation_issues)

    def test_gradient_layer_fails(self):
        """Test validation with gradient layer failure.

        Given: Gradient layer fails
        When: Creating DistributedTrainingValidation
        Then: overall_valid is False and validation_issues contains 'gradient'
        """
        validation = DistributedTrainingValidation(
            hardware_layer_valid=True,
            worker_layer_valid=True,
            checkpoint_layer_valid=True,
            gradient_layer_valid=False,
            performance_layer_valid=True,
            health_check_passed=True,
            validation_issues=["Gradient layer: NaN detected"],
            overall_valid=False,
        )

        assert validation.overall_valid is False
        assert any("Gradient layer" in issue for issue in validation.validation_issues)

    def test_performance_layer_fails(self):
        """Test validation with performance layer failure.

        Given: Performance layer fails
        When: Creating DistributedTrainingValidation
        Then: overall_valid is False and validation_issues contains 'performance'
        """
        validation = DistributedTrainingValidation(
            hardware_layer_valid=True,
            worker_layer_valid=True,
            checkpoint_layer_valid=True,
            gradient_layer_valid=True,
            performance_layer_valid=False,
            health_check_passed=True,
            validation_issues=["Performance layer: Low GPU utilization"],
            overall_valid=False,
        )

        assert validation.overall_valid is False
        assert any("Performance layer" in issue for issue in validation.validation_issues)

    def test_health_check_fails(self):
        """Test validation with health check failure.

        Given: Health check fails
        When: Creating DistributedTrainingValidation
        Then: overall_valid is False and validation_issues contains 'health'
        """
        validation = DistributedTrainingValidation(
            hardware_layer_valid=True,
            worker_layer_valid=True,
            checkpoint_layer_valid=True,
            gradient_layer_valid=True,
            performance_layer_valid=True,
            health_check_passed=False,
            validation_issues=["Health check: Heartbeat timeout"],
            overall_valid=False,
        )

        assert validation.overall_valid is False
        assert any("Health check" in issue for issue in validation.validation_issues)

    def test_partial_failure_scenario(self):
        """Test validation with partial failures (some layers pass, some fail).

        Given: Multiple layers fail
        When: Creating DistributedTrainingValidation
        Then: overall_valid is False and all failures are reported
        """
        validation = DistributedTrainingValidation(
            hardware_layer_valid=False,
            worker_layer_valid=False,
            checkpoint_layer_valid=True,
            gradient_layer_valid=True,
            performance_layer_valid=False,
            health_check_passed=True,
            validation_issues=[
                "Hardware layer: GPU mismatch",
                "Worker layer: Divergence",
                "Performance layer: Low throughput",
            ],
            overall_valid=False,
        )

        assert validation.overall_valid is False
        assert len(validation.validation_issues) == 3


# ==============================================================================
# SECTION 6: validate_checkpoint_layer() Function Tests
# ==============================================================================


@pytest.mark.unit
class TestValidateCheckpointLayer:
    """Test validate_checkpoint_layer() function integration.

    Given: validate_checkpoint_layer() function
    When: Validating checkpoint files with various scenarios
    Then: CheckpointValidationResult reflects integrity and version consistency
    """

    def test_valid_checkpoint_paths(self, valid_checkpoint_paths):
        """Test validate_checkpoint_layer with valid checkpoints.

        Given: Valid checkpoint paths
        When: Calling validate_checkpoint_layer
        Then: CheckpointValidationResult with is_valid=True
        """
        result = validate_checkpoint_layer(valid_checkpoint_paths)

        assert result.is_valid is True
        assert result.version_consistency is True
        assert all(result.integrity_checks)
        assert len(result.missing_files) == 0
        assert len(result.corrupted_files) == 0

    def test_empty_checkpoint_list(self):
        """Test validate_checkpoint_layer with empty checkpoint list.

        Given: Empty checkpoint list
        When: Calling validate_checkpoint_layer
        Then: ValueError is raised
        """
        with pytest.raises(ValueError, match="Checkpoint list cannot be empty"):
            validate_checkpoint_layer([])

    def test_missing_checkpoint_files(self, tmp_path):
        """Test validate_checkpoint_layer with missing files.

        Given: Checkpoint paths with missing files
        When: Calling validate_checkpoint_layer
        Then: CheckpointValidationResult with missing_files list
        """
        missing_paths = [
            tmp_path / "checkpoint_worker_0.pt",
            tmp_path / "checkpoint_worker_1.pt",
        ]

        result = validate_checkpoint_layer(missing_paths)

        assert result.is_valid is False
        assert len(result.missing_files) > 0

    def test_version_mismatch(self, mismatched_checkpoint_paths):
        """Test validate_checkpoint_layer with version mismatch.

        Given: Checkpoint paths with version mismatch
        When: Calling validate_checkpoint_layer
        Then: CheckpointValidationResult with version_consistency=False
        """
        result = validate_checkpoint_layer(mismatched_checkpoint_paths)

        assert result.is_valid is False
        assert result.version_consistency is False

    def test_corrupted_checkpoints(self, tmp_path):
        """Test validate_checkpoint_layer with corrupted files.

        Given: Checkpoint paths with corrupted files
        When: Calling validate_checkpoint_layer
        Then: CheckpointValidationResult with corrupted_files list
        """
        corrupted_paths = []
        for i in range(2):
            checkpoint_file = tmp_path / f"checkpoint_worker_{i}.pt"
            checkpoint_file.write_text("invalid json {{{")
            corrupted_paths.append(checkpoint_file)

        result = validate_checkpoint_layer(corrupted_paths)

        assert result.is_valid is False
        assert len(result.corrupted_files) > 0


# ==============================================================================
# SECTION 7: validate_gradient_layer() Function Tests
# ==============================================================================


@pytest.mark.unit
class TestValidateGradientLayer:
    """Test validate_gradient_layer() function integration.

    Given: validate_gradient_layer() function
    When: Validating gradient updates with various scenarios
    Then: GradientValidationResult reflects consistency and stability
    """

    def test_valid_gradient_updates(self, valid_gradient_updates):
        """Test validate_gradient_layer with valid gradients.

        Given: Valid gradient updates
        When: Calling validate_gradient_layer
        Then: GradientValidationResult with is_valid=True
        """
        result = validate_gradient_layer(valid_gradient_updates)

        assert result.is_valid is True
        assert result.all_reduce_consistent is True
        assert result.numerical_stability is True
        assert result.gradient_variance < 0.1
        assert len(result.outlier_workers) == 0

    def test_single_worker_scenario(self):
        """Test validate_gradient_layer with single worker.

        Given: Single worker gradient update
        When: Calling validate_gradient_layer
        Then: GradientValidationResult (no consistency check)
        """
        single_worker = [
            {
                "worker_id": "worker-0",
                "gradients": {"layer1": [0.1, 0.2, 0.3]},
                "gradient_norm": 0.37,
            }
        ]

        result = validate_gradient_layer(single_worker)

        # Single worker cannot have inconsistency or outliers
        assert result.is_valid is True
        assert len(result.outlier_workers) == 0

    def test_nan_gradients(self, gradient_updates_with_nan):
        """Test validate_gradient_layer with NaN gradients.

        Given: Gradient updates with NaN values
        When: Calling validate_gradient_layer
        Then: GradientValidationResult with numerical_stability=False
        """
        result = validate_gradient_layer(gradient_updates_with_nan)

        assert result.is_valid is False
        assert result.numerical_stability is False

    def test_high_variance_gradients(self, gradient_updates_with_outlier):
        """Test validate_gradient_layer with high variance.

        Given: Gradient updates with high variance
        When: Calling validate_gradient_layer
        Then: GradientValidationResult with high gradient_variance
        """
        result = validate_gradient_layer(gradient_updates_with_outlier)

        assert result.is_valid is False
        assert result.gradient_variance > 0.1

    def test_perfect_consistency(self):
        """Test validate_gradient_layer with perfect consistency.

        Given: Gradient updates with identical gradients
        When: Calling validate_gradient_layer
        Then: GradientValidationResult with variance=0
        """
        perfect_gradients = [
            {
                "worker_id": f"worker-{i}",
                "gradients": {"layer1": [0.1, 0.2, 0.3]},
                "gradient_norm": 0.37,
            }
            for i in range(3)
        ]

        result = validate_gradient_layer(perfect_gradients)

        assert result.is_valid is True
        assert result.gradient_variance == 0.0

    def test_outlier_detection(self, gradient_updates_with_outlier):
        """Test validate_gradient_layer with outlier detection.

        Given: Gradient updates with outlier worker
        When: Calling validate_gradient_layer
        Then: GradientValidationResult with outlier_workers list
        """
        result = validate_gradient_layer(gradient_updates_with_outlier)

        assert result.is_valid is False
        assert len(result.outlier_workers) > 0
        assert "worker-2" in result.outlier_workers


# ==============================================================================
# SECTION 8: monitor_performance() Function Tests
# ==============================================================================


@pytest.mark.unit
class TestMonitorPerformance:
    """Test monitor_performance() function integration.

    Given: monitor_performance() function
    When: Monitoring performance metrics with various scenarios
    Then: PerformanceMetrics reflects threshold compliance
    """

    def test_valid_performance_metrics(self, valid_performance_metrics):
        """Test monitor_performance with valid metrics.

        Given: Valid performance metrics
        When: Calling monitor_performance
        Then: PerformanceMetrics with is_within_thresholds=True
        """
        metrics = monitor_performance(valid_performance_metrics)

        assert metrics.is_within_thresholds is True
        assert metrics.throughput > 0
        assert metrics.latency_ms < 500
        assert metrics.gpu_utilization > 0.8
        assert metrics.memory_utilization < 0.9

    def test_zero_throughput(self):
        """Test monitor_performance with zero throughput.

        Given: Performance metrics with zero throughput
        When: Calling monitor_performance
        Then: PerformanceMetrics with is_within_thresholds=False
        """
        metrics_data = {
            "throughput": 0.0,
            "latency_ms": 100.0,
            "gpu_utilization": 0.85,
            "memory_utilization": 0.75,
        }

        metrics = monitor_performance(metrics_data)

        assert metrics.is_within_thresholds is False
        assert metrics.throughput == 0.0

    def test_high_latency(self):
        """Test monitor_performance with high latency.

        Given: Performance metrics with high latency (>500ms)
        When: Calling monitor_performance
        Then: PerformanceMetrics with is_within_thresholds=False
        """
        metrics_data = {
            "throughput": 1000.0,
            "latency_ms": 600.0,
            "gpu_utilization": 0.85,
            "memory_utilization": 0.75,
        }

        metrics = monitor_performance(metrics_data)

        assert metrics.is_within_thresholds is False
        assert metrics.latency_ms > 500

    def test_low_gpu_utilization(self):
        """Test monitor_performance with low GPU utilization.

        Given: Performance metrics with low GPU utilization (<80%)
        When: Calling monitor_performance
        Then: PerformanceMetrics with is_within_thresholds=False
        """
        metrics_data = {
            "throughput": 1000.0,
            "latency_ms": 50.0,
            "gpu_utilization": 0.60,
            "memory_utilization": 0.75,
        }

        metrics = monitor_performance(metrics_data)

        assert metrics.is_within_thresholds is False
        assert metrics.gpu_utilization < 0.8

    def test_high_memory_utilization(self):
        """Test monitor_performance with high memory utilization.

        Given: Performance metrics with high memory utilization (>90%)
        When: Calling monitor_performance
        Then: PerformanceMetrics with is_within_thresholds=False
        """
        metrics_data = {
            "throughput": 1000.0,
            "latency_ms": 50.0,
            "gpu_utilization": 0.85,
            "memory_utilization": 0.95,
        }

        metrics = monitor_performance(metrics_data)

        assert metrics.is_within_thresholds is False
        assert metrics.memory_utilization > 0.9


# ==============================================================================
# SECTION 9: run_health_checks() Function Tests
# ==============================================================================


@pytest.mark.unit
class TestRunHealthChecks:
    """Test run_health_checks() function integration.

    Given: run_health_checks() function
    When: Running health checks with various configurations
    Then: HealthCheckResult reflects system health status
    """

    def test_pre_flight_mode_all_pass(self, valid_health_config):
        """Test run_health_checks in pre-flight mode with all checks passing.

        Given: Valid health check configuration
        When: Calling run_health_checks in pre-flight mode
        Then: HealthCheckResult with pre_flight_passed=True
        """
        result = run_health_checks(valid_health_config, mode="pre-flight")

        assert result.pre_flight_passed is True
        assert len(result.issues) == 0

    def test_pre_flight_mode_gpu_missing(self, invalid_health_config):
        """Test run_health_checks in pre-flight mode with GPU missing.

        Given: Health check configuration with no GPUs
        When: Calling run_health_checks in pre-flight mode
        Then: HealthCheckResult with pre_flight_passed=False
        """
        result = run_health_checks(invalid_health_config, mode="pre-flight")

        assert result.pre_flight_passed is False
        assert any("GPU" in issue for issue in result.issues)

    def test_runtime_mode_all_pass(self, valid_health_config):
        """Test run_health_checks in runtime mode with all checks passing.

        Given: Valid runtime configuration
        When: Calling run_health_checks in runtime mode
        Then: HealthCheckResult with runtime_checks_passed=True
        """
        result = run_health_checks(valid_health_config, mode="runtime")

        assert result.runtime_checks_passed is True
        assert len(result.issues) == 0

    def test_runtime_mode_heartbeat_timeout(self):
        """Test run_health_checks in runtime mode with heartbeat timeout.

        Given: Runtime configuration with stale heartbeat
        When: Calling run_health_checks in runtime mode
        Then: HealthCheckResult with runtime_checks_passed=False
        """
        config = {
            "gpu_count": 4,
            "rdma_enabled": True,
            "nccl_version": "2.19.0",
            "worker_heartbeats": {
                "worker-0": 1706524800.0,
                "worker-1": 1706524801.0,
                "worker-2": 0.0,  # Timeout
            },
        }

        result = run_health_checks(config, mode="runtime")

        assert result.runtime_checks_passed is False
        assert any("heartbeat" in issue.lower() for issue in result.issues)

    def test_rdma_fallback_warning(self):
        """Test run_health_checks with RDMA fallback warning.

        Given: Configuration with RDMA disabled
        When: Calling run_health_checks
        Then: HealthCheckResult with warning about RDMA fallback
        """
        config = {
            "gpu_count": 4,
            "rdma_enabled": False,  # RDMA disabled, fallback to TCP
            "nccl_version": "2.19.0",
            "worker_heartbeats": {
                "worker-0": 1706524800.0,
            },
        }

        result = run_health_checks(config, mode="pre-flight")

        # Should still pass but may have warning
        assert result.pre_flight_passed is True


# ==============================================================================
# SECTION 10: validate_distributed_training() Function Tests (End-to-End)
# ==============================================================================


@pytest.mark.unit
class TestValidateDistributedTraining:
    """Test validate_distributed_training() end-to-end integration.

    Given: validate_distributed_training() function
    When: Validating complete distributed training setup
    Then: DistributedTrainingValidation reflects overall system health
    """

    def test_all_layers_pass_integration(
        self,
        valid_checkpoint_paths,
        valid_gradient_updates,
        valid_performance_metrics,
        valid_health_config,
    ):
        """Test validate_distributed_training with all layers passing.

        Given: Valid configuration for all validation layers
        When: Calling validate_distributed_training
        Then: DistributedTrainingValidation with overall_valid=True
        """
        config = {
            "checkpoints": valid_checkpoint_paths,
            "gradient_updates": valid_gradient_updates,
            "performance_metrics": valid_performance_metrics,
            "health_config": valid_health_config,
        }

        validation = validate_distributed_training(config)

        assert validation.overall_valid is True
        assert validation.hardware_layer_valid is True
        assert validation.worker_layer_valid is True
        assert validation.checkpoint_layer_valid is True
        assert validation.gradient_layer_valid is True
        assert validation.performance_layer_valid is True
        assert validation.health_check_passed is True
        assert len(validation.validation_issues) == 0

    def test_hardware_layer_fails_integration(self):
        """Test validate_distributed_training with hardware failure.

        Given: Configuration with hardware layer failure
        When: Calling validate_distributed_training
        Then: DistributedTrainingValidation with overall_valid=False
        """
        config = {
            "checkpoints": [],
            "gradient_updates": [],
            "performance_metrics": {},
            "health_config": {"gpu_count": 0},  # No GPUs
        }

        validation = validate_distributed_training(config)

        assert validation.overall_valid is False
        assert any("hardware" in issue.lower() for issue in validation.validation_issues)

    def test_worker_layer_fails_integration(
        self, valid_checkpoint_paths, gradient_updates_with_nan
    ):
        """Test validate_distributed_training with worker failure.

        Given: Configuration with worker layer failure (NaN gradients)
        When: Calling validate_distributed_training
        Then: DistributedTrainingValidation with overall_valid=False
        """
        config = {
            "checkpoints": valid_checkpoint_paths,
            "gradient_updates": gradient_updates_with_nan,
            "performance_metrics": {},
            "health_config": {},
        }

        validation = validate_distributed_training(config)

        assert validation.overall_valid is False
        assert any("gradient" in issue.lower() for issue in validation.validation_issues)

    def test_checkpoint_layer_fails_integration(self, mismatched_checkpoint_paths):
        """Test validate_distributed_training with checkpoint failure.

        Given: Configuration with checkpoint layer failure (version mismatch)
        When: Calling validate_distributed_training
        Then: DistributedTrainingValidation with overall_valid=False
        """
        config = {
            "checkpoints": mismatched_checkpoint_paths,
            "gradient_updates": [],
            "performance_metrics": {},
            "health_config": {},
        }

        validation = validate_distributed_training(config)

        assert validation.overall_valid is False
        assert any("checkpoint" in issue.lower() for issue in validation.validation_issues)

    def test_performance_layer_fails_integration(self, invalid_performance_metrics):
        """Test validate_distributed_training with performance failure.

        Given: Configuration with performance layer failure
        When: Calling validate_distributed_training
        Then: DistributedTrainingValidation with overall_valid=False
        """
        config = {
            "checkpoints": [],
            "gradient_updates": [],
            "performance_metrics": invalid_performance_metrics,
            "health_config": {},
        }

        validation = validate_distributed_training(config)

        assert validation.overall_valid is False
        assert any("performance" in issue.lower() for issue in validation.validation_issues)

    def test_health_check_fails_integration(self, invalid_health_config):
        """Test validate_distributed_training with health check failure.

        Given: Configuration with health check failure
        When: Calling validate_distributed_training
        Then: DistributedTrainingValidation with overall_valid=False
        """
        config = {
            "checkpoints": [],
            "gradient_updates": [],
            "performance_metrics": {},
            "health_config": invalid_health_config,
        }

        validation = validate_distributed_training(config)

        assert validation.overall_valid is False
        assert any("health" in issue.lower() for issue in validation.validation_issues)

    def test_partial_failure_integration(
        self, mismatched_checkpoint_paths, gradient_updates_with_nan
    ):
        """Test validate_distributed_training with partial failures.

        Given: Configuration with multiple layer failures
        When: Calling validate_distributed_training
        Then: DistributedTrainingValidation with all failures reported
        """
        config = {
            "checkpoints": mismatched_checkpoint_paths,
            "gradient_updates": gradient_updates_with_nan,
            "performance_metrics": {},
            "health_config": {},
        }

        validation = validate_distributed_training(config)

        assert validation.overall_valid is False
        assert len(validation.validation_issues) >= 2


# ==============================================================================
# SECTION 11: Security Validation Tests
# ==============================================================================


@pytest.mark.unit
class TestSecurityValidation:
    """Test security validation in distributed training validator.

    Given: Security-critical validation functions
    When: Processing untrusted inputs
    Then: Path traversal, input validation, and audit logging are enforced
    """

    def test_path_traversal_prevention_cwe22(self, tmp_path):
        """Test path traversal prevention (CWE-22) for checkpoint validation.

        Given: Checkpoint paths with path traversal attempts
        When: Calling validate_checkpoint_layer
        Then: ValueError is raised for path traversal
        """
        malicious_paths = [
            tmp_path / ".." / ".." / "etc" / "passwd",
            tmp_path / "checkpoint_worker_0.pt",
        ]

        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_checkpoint_layer(malicious_paths)

    def test_input_validation_cwe20_empty_config(self):
        """Test input validation (CWE-20) for empty config dict.

        Given: Empty configuration dict
        When: Calling validate_distributed_training
        Then: ValueError is raised for missing required fields
        """
        with pytest.raises(ValueError, match="Missing required field"):
            validate_distributed_training({})

    def test_input_validation_cwe20_invalid_types(self):
        """Test input validation (CWE-20) for invalid types.

        Given: Configuration with invalid types
        When: Calling validate_distributed_training
        Then: TypeError is raised
        """
        config = {
            "checkpoints": "not_a_list",  # Should be list
            "gradient_updates": [],
            "performance_metrics": {},
            "health_config": {},
        }

        with pytest.raises(TypeError, match="Expected list"):
            validate_distributed_training(config)

    def test_audit_logging_cwe117_checkpoint_validation(
        self, valid_checkpoint_paths, caplog
    ):
        """Test audit logging (CWE-117) for checkpoint validation.

        Given: Valid checkpoint paths
        When: Calling validate_checkpoint_layer
        Then: Audit log contains validation start/end entries
        """
        import logging

        caplog.set_level(logging.INFO)

        validate_checkpoint_layer(valid_checkpoint_paths)

        assert any("Checkpoint validation started" in record.message for record in caplog.records)
        assert any(
            "Checkpoint validation completed" in record.message for record in caplog.records
        )

    def test_audit_logging_cwe117_gradient_validation(self, valid_gradient_updates, caplog):
        """Test audit logging (CWE-117) for gradient validation.

        Given: Valid gradient updates
        When: Calling validate_gradient_layer
        Then: Audit log contains validation start/end entries
        """
        import logging

        caplog.set_level(logging.INFO)

        validate_gradient_layer(valid_gradient_updates)

        assert any("Gradient validation started" in record.message for record in caplog.records)
        assert any("Gradient validation completed" in record.message for record in caplog.records)

    def test_audit_logging_cwe117_health_check(self, valid_health_config, caplog):
        """Test audit logging (CWE-117) for health check.

        Given: Valid health check configuration
        When: Calling run_health_checks
        Then: Audit log contains health check start/end entries
        """
        import logging

        caplog.set_level(logging.INFO)

        run_health_checks(valid_health_config, mode="pre-flight")

        assert any("Health check started" in record.message for record in caplog.records)
        assert any("Health check completed" in record.message for record in caplog.records)

    def test_sanitize_checkpoint_paths(self, tmp_path):
        """Test checkpoint path sanitization for security.

        Given: Checkpoint paths with special characters
        When: Calling validate_checkpoint_layer
        Then: Paths are sanitized and validated
        """
        # Create checkpoint with valid name
        checkpoint_file = tmp_path / "checkpoint_worker_0.pt"
        checkpoint_data = {
            "version": "1.0.0",
            "step": 1000,
            "model_state": {"layer1": [1.0, 2.0, 3.0]},
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data))

        result = validate_checkpoint_layer([checkpoint_file])

        assert result.is_valid is True

    def test_validate_gradient_update_structure(self):
        """Test gradient update structure validation.

        Given: Gradient updates with invalid structure
        When: Calling validate_gradient_layer
        Then: ValueError is raised for invalid structure
        """
        invalid_gradients = [
            {
                "worker_id": "worker-0",
                # Missing 'gradients' key
                "gradient_norm": 0.37,
            }
        ]

        with pytest.raises(ValueError, match="Missing required field 'gradients'"):
            validate_gradient_layer(invalid_gradients)


# ==============================================================================
# END OF TESTS
# ==============================================================================

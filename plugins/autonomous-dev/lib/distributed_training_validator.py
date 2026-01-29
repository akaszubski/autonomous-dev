#!/usr/bin/env python3
"""
Distributed Training Validator - Comprehensive distributed training validation.

This module provides classes and functions for validating distributed training environments with:
- Checkpoint validation (version consistency, integrity, file validation)
- Gradient validation (synchronization, numerical stability, outlier detection)
- Performance monitoring (throughput, latency, GPU/memory utilization)
- Health checks (pre-flight and runtime validation)
- Multi-layer validation aggregation

Security:
    - CWE-22: Path validation via security_utils for checkpoint files
    - CWE-20: Input validation for all configuration dicts
    - CWE-117: Audit logging with sanitization

Related:
    - GitHub Issue #282: Add DistributedTrainingValidator library

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See error-handling-patterns skill for error handling best practices.
"""

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import security utilities for path validation and audit logging
try:
    from security_utils import validate_path, audit_log
except ImportError:
    # Fallback if security_utils not available
    def audit_log(component, action, details):
        logger = logging.getLogger(__name__)
        logger.warning(f"Audit log: {component}.{action}: {details}")

    def validate_path(path, purpose, allow_missing=False, test_mode=None):
        # Minimal validation fallback
        if ".." in str(path):
            raise ValueError(f"Path traversal detected: {path}")
        return Path(path).resolve()

# Import hardware calibrator for hardware layer validation
try:
    from hardware_calibrator import calibrate_node, HardwareMetrics, CalibrationResult
except ImportError:
    # Fallback if hardware_calibrator not available
    HardwareMetrics = None
    CalibrationResult = None
    def calibrate_node(*args, **kwargs):
        raise ImportError("hardware_calibrator not available")

# Import worker consistency validator for worker layer validation
try:
    from worker_consistency_validator import (
        validate_worker_consistency,
        WorkerState,
        ConsistencyMetrics
    )
except ImportError:
    # Fallback if worker_consistency_validator not available
    WorkerState = None
    ConsistencyMetrics = None
    def validate_worker_consistency(*args, **kwargs):
        raise ImportError("worker_consistency_validator not available")

# Logger for validator operations
logger = logging.getLogger(__name__)


# ==============================================================================
# CUSTOM EXCEPTIONS
# ==============================================================================


class CheckpointValidationError(Exception):
    """Raised when checkpoint validation fails."""
    pass


class GradientValidationError(Exception):
    """Raised when gradient validation fails."""
    pass


class PerformanceValidationError(Exception):
    """Raised when performance validation fails."""
    pass


class HealthCheckError(Exception):
    """Raised when health check fails."""
    pass


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass(frozen=True)
class CheckpointValidationResult:
    """Checkpoint validation result for distributed training.

    Attributes:
        version_consistency: True if all checkpoints have same version
        integrity_checks: List of integrity check results (True = passed)
        missing_files: List of missing checkpoint file paths
        corrupted_files: List of corrupted checkpoint file paths
        is_valid: Computed validity status (True if all checks pass)
    """

    version_consistency: bool
    integrity_checks: List[bool]
    missing_files: List[str]
    corrupted_files: List[str]
    is_valid: bool = field(init=False)

    def __post_init__(self):
        """Calculate is_valid based on validation results."""
        # Use object.__setattr__ for frozen dataclass
        is_valid = (
            self.version_consistency
            and all(self.integrity_checks)
            and len(self.missing_files) == 0
            and len(self.corrupted_files) == 0
        )
        object.__setattr__(self, "is_valid", is_valid)


@dataclass(frozen=True)
class GradientValidationResult:
    """Gradient validation result for distributed training.

    Attributes:
        all_reduce_consistent: True if all-reduce operation is consistent
        numerical_stability: True if no NaN or Inf values detected
        gradient_variance: Variance of gradient norms across workers
        outlier_workers: List of outlier worker IDs
        is_valid: Computed validity status (True if all checks pass)
    """

    all_reduce_consistent: bool
    numerical_stability: bool
    gradient_variance: float
    outlier_workers: List[str]
    is_valid: bool = field(init=False)

    def __post_init__(self):
        """Calculate is_valid based on validation results."""
        # Use object.__setattr__ for frozen dataclass
        is_valid = (
            self.all_reduce_consistent
            and self.numerical_stability
            and self.gradient_variance < 0.1
            and len(self.outlier_workers) == 0
        )
        object.__setattr__(self, "is_valid", is_valid)


@dataclass(frozen=True)
class PerformanceMetrics:
    """Performance metrics for distributed training.

    Attributes:
        throughput: Throughput in samples/second
        latency_ms: Average latency in milliseconds
        gpu_utilization: GPU utilization (0.0-1.0)
        memory_utilization: Memory utilization (0.0-1.0)
        is_within_thresholds: True if all metrics within acceptable thresholds
    """

    throughput: float
    latency_ms: float
    gpu_utilization: float
    memory_utilization: float
    is_within_thresholds: bool


@dataclass(frozen=True)
class HealthCheckResult:
    """Health check result for distributed training cluster.

    Attributes:
        pre_flight_passed: True if pre-flight checks passed
        runtime_checks_passed: True if runtime checks passed
        issues: List of health check issues detected
    """

    pre_flight_passed: bool
    runtime_checks_passed: bool
    issues: List[str]


@dataclass(frozen=True)
class DistributedTrainingValidation:
    """Aggregated validation result for distributed training.

    Attributes:
        hardware_layer_valid: True if hardware layer validation passed
        worker_layer_valid: True if worker layer validation passed
        checkpoint_layer_valid: True if checkpoint layer validation passed
        gradient_layer_valid: True if gradient layer validation passed
        performance_layer_valid: True if performance layer validation passed
        health_check_passed: True if health check passed
        validation_issues: List of validation issues detected
        overall_valid: True if all layers valid
    """

    hardware_layer_valid: bool
    worker_layer_valid: bool
    checkpoint_layer_valid: bool
    gradient_layer_valid: bool
    performance_layer_valid: bool
    health_check_passed: bool
    validation_issues: List[str]
    overall_valid: bool


# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================


def validate_checkpoint_layer(
    checkpoint_paths: List[Path],
    expected_version: Optional[str] = None
) -> CheckpointValidationResult:
    """Validate checkpoint layer for distributed training.

    Args:
        checkpoint_paths: List of checkpoint file paths
        expected_version: Expected checkpoint version (optional)

    Returns:
        CheckpointValidationResult with validation results

    Raises:
        ValueError: If checkpoint list is empty or path traversal detected

    Security:
        - CWE-22: Path validation via security_utils
        - CWE-117: Audit logging
    """
    # Input validation
    if not checkpoint_paths:
        raise ValueError(
            f"Checkpoint list cannot be empty\n"
            f"Expected: Non-empty list of Path objects\n"
            f"See: docs/distributed-training/checkpoint-validation.md"
        )

    # Audit log validation start
    logger.info(f"Checkpoint validation started: checkpoint_count={len(checkpoint_paths)}")

    # Validate all paths for security (CWE-22)
    validated_paths = []
    for path in checkpoint_paths:
        try:
            validated_path = validate_path(path, "checkpoint file", allow_missing=True)
            validated_paths.append(validated_path)
        except ValueError as e:
            # Path traversal detected
            if "Path traversal" in str(e):
                raise ValueError(
                    f"Path traversal detected: {path}\n"
                    f"Checkpoint paths must be within project boundaries.\n"
                    f"See: docs/SECURITY.md#path-validation"
                )
            else:
                raise

    # Check for missing files
    missing_files = []
    existing_paths = []
    for path in validated_paths:
        if not path.exists():
            missing_files.append(str(path.name))
        else:
            existing_paths.append(path)

    # Read checkpoint versions and check integrity
    versions = []
    corrupted_files = []
    integrity_checks = []

    for path in existing_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
                version = checkpoint_data.get('version')
                if version is None:
                    corrupted_files.append(str(path.name))
                    integrity_checks.append(False)
                else:
                    versions.append(version)
                    integrity_checks.append(True)
        except (json.JSONDecodeError, IOError):
            corrupted_files.append(str(path.name))
            integrity_checks.append(False)

    # Check version consistency
    version_consistency = len(set(versions)) <= 1 if versions else False

    # If expected_version provided, check against it
    if expected_version is not None and versions and versions[0] != expected_version:
        version_consistency = False

    # Create result
    result = CheckpointValidationResult(
        version_consistency=version_consistency,
        integrity_checks=integrity_checks,
        missing_files=missing_files,
        corrupted_files=corrupted_files
    )

    # Audit log validation complete
    logger.info(
        f"Checkpoint validation completed: is_valid={result.is_valid}, "
        f"missing={len(missing_files)}, corrupted={len(corrupted_files)}"
    )

    return result


def validate_gradient_layer(
    gradient_updates: List[Dict[str, Any]],
    tolerance: float = 0.1
) -> GradientValidationResult:
    """Validate gradient layer for distributed training.

    Args:
        gradient_updates: List of gradient update dicts
        tolerance: Gradient variance tolerance threshold

    Returns:
        GradientValidationResult with validation results

    Raises:
        ValueError: If gradient updates list is empty or invalid structure

    Security:
        - CWE-20: Input validation
        - CWE-117: Audit logging
    """
    # Input validation
    if not gradient_updates:
        raise ValueError(
            f"Gradient updates list cannot be empty\n"
            f"Expected: Non-empty list of gradient update dicts\n"
            f"See: docs/distributed-training/gradient-validation.md"
        )

    # Validate structure
    for update in gradient_updates:
        if 'gradients' not in update:
            raise ValueError(
                f"Missing required field 'gradients' in gradient update\n"
                f"Expected: Dict with 'gradients' key\n"
                f"Got: {list(update.keys())}"
            )

    # Audit log validation start
    logger.info(f"Gradient validation started: worker_count={len(gradient_updates)}")

    # Single worker - no consistency check needed
    if len(gradient_updates) == 1:
        result = GradientValidationResult(
            all_reduce_consistent=True,
            numerical_stability=True,
            gradient_variance=0.0,
            outlier_workers=[]
        )
        logger.info("Gradient validation completed: is_valid=True (single worker)")
        return result

    # Check for NaN/Inf (numerical stability)
    numerical_stability = True
    for update in gradient_updates:
        gradient_norm = update.get('gradient_norm', 0.0)
        if not math.isfinite(gradient_norm):
            numerical_stability = False
            break

    # Calculate gradient variance
    gradient_norms = [update.get('gradient_norm', 0.0) for update in gradient_updates]
    mean_norm = sum(gradient_norms) / len(gradient_norms)
    variance = sum((x - mean_norm) ** 2 for x in gradient_norms) / len(gradient_norms)

    # Round to zero if variance is negligibly small (floating point precision)
    if variance < 1e-10:
        variance = 0.0

    # Detect outlier workers using median-based method
    # An outlier is a gradient norm that is significantly different from the median
    outlier_workers = []
    if len(gradient_norms) >= 2:
        sorted_norms = sorted(gradient_norms)
        n = len(sorted_norms)

        # Calculate median
        if n % 2 == 0:
            median_norm = (sorted_norms[n//2 - 1] + sorted_norms[n//2]) / 2.0
        else:
            median_norm = sorted_norms[n//2]

        # For small datasets (n <= 3), use a simple threshold:
        # Outlier if value is > 10x median or < 0.1x median (for positive values)
        if n <= 3:
            threshold_multiplier = 10.0
            for i, update in enumerate(gradient_updates):
                gradient_norm = update.get('gradient_norm', 0.0)
                if median_norm > 0:
                    if (gradient_norm > median_norm * threshold_multiplier or
                        gradient_norm < median_norm / threshold_multiplier):
                        outlier_workers.append(update.get('worker_id', f'worker-{i}'))
        else:
            # For larger datasets, use MAD (Median Absolute Deviation)
            mad = sum(abs(x - median_norm) for x in gradient_norms) / len(gradient_norms)
            # Modified z-score threshold (commonly 3.5)
            threshold = 3.5
            for i, update in enumerate(gradient_updates):
                gradient_norm = update.get('gradient_norm', 0.0)
                if mad > 0:
                    modified_z_score = abs(gradient_norm - median_norm) / mad
                    if modified_z_score > threshold:
                        outlier_workers.append(update.get('worker_id', f'worker-{i}'))

    # Check all-reduce consistency (low variance)
    all_reduce_consistent = variance < tolerance and numerical_stability

    # Create result
    result = GradientValidationResult(
        all_reduce_consistent=all_reduce_consistent,
        numerical_stability=numerical_stability,
        gradient_variance=variance,
        outlier_workers=outlier_workers
    )

    # Audit log validation complete
    logger.info(
        f"Gradient validation completed: is_valid={result.is_valid}, "
        f"variance={variance:.4f}, outliers={len(outlier_workers)}"
    )

    return result


def monitor_performance(
    metrics_data: Dict[str, Any],
    thresholds: Optional[Dict[str, float]] = None
) -> PerformanceMetrics:
    """Monitor performance metrics for distributed training.

    Args:
        metrics_data: Dict with performance metrics
        thresholds: Optional dict with threshold values

    Returns:
        PerformanceMetrics with performance data

    Raises:
        ValueError: If required metrics missing

    Thresholds:
        - throughput: > 0
        - latency_ms: < 500
        - gpu_utilization: > 0.8
        - memory_utilization: < 0.9
    """
    # Default thresholds
    if thresholds is None:
        thresholds = {
            'min_throughput': 0.0,
            'max_latency_ms': 500.0,
            'min_gpu_utilization': 0.8,
            'max_memory_utilization': 0.9
        }

    # Extract metrics
    throughput = metrics_data.get('throughput', 0.0)
    latency_ms = metrics_data.get('latency_ms', 0.0)
    gpu_utilization = metrics_data.get('gpu_utilization', 0.0)
    memory_utilization = metrics_data.get('memory_utilization', 0.0)

    # Check thresholds
    is_within_thresholds = (
        throughput > thresholds.get('min_throughput', 0.0)
        and latency_ms < thresholds.get('max_latency_ms', 500.0)
        and gpu_utilization > thresholds.get('min_gpu_utilization', 0.8)
        and memory_utilization < thresholds.get('max_memory_utilization', 0.9)
    )

    # Create metrics
    metrics = PerformanceMetrics(
        throughput=throughput,
        latency_ms=latency_ms,
        gpu_utilization=gpu_utilization,
        memory_utilization=memory_utilization,
        is_within_thresholds=is_within_thresholds
    )

    return metrics


def run_health_checks(
    cluster_config: Dict[str, Any],
    mode: str = "pre-flight"
) -> HealthCheckResult:
    """Run health checks for distributed training cluster.

    Args:
        cluster_config: Dict with cluster configuration
        mode: Health check mode ("pre-flight" or "runtime")

    Returns:
        HealthCheckResult with health check results

    Raises:
        ValueError: If mode is invalid

    Security:
        - CWE-20: Input validation
        - CWE-117: Audit logging
    """
    # Input validation
    if mode not in ["pre-flight", "runtime"]:
        raise ValueError(
            f"Invalid health check mode: {mode}\n"
            f"Expected: 'pre-flight' or 'runtime'\n"
            f"Got: {mode}"
        )

    # Audit log health check start
    logger.info(f"Health check started: mode={mode}")

    issues = []
    pre_flight_passed = True
    runtime_checks_passed = True

    # Pre-flight checks
    if mode == "pre-flight":
        # Check GPU count
        gpu_count = cluster_config.get('gpu_count', 0)
        if gpu_count == 0:
            issues.append("GPU count is 0, expected > 0")
            pre_flight_passed = False

        # Check NCCL version (optional warning)
        nccl_version = cluster_config.get('nccl_version', '')
        if nccl_version and nccl_version < "2.18.0":
            # Don't fail, just note old version
            pass

        # Check RDMA (optional warning)
        rdma_enabled = cluster_config.get('rdma_enabled', False)
        if not rdma_enabled:
            # Don't fail, RDMA is optional
            pass

    # Runtime checks
    elif mode == "runtime":
        # Check worker heartbeats
        worker_heartbeats = cluster_config.get('worker_heartbeats', {})
        for worker_id, heartbeat in worker_heartbeats.items():
            if heartbeat == 0.0:
                issues.append(f"Worker {worker_id} heartbeat timeout")
                runtime_checks_passed = False

    # Create result
    result = HealthCheckResult(
        pre_flight_passed=pre_flight_passed,
        runtime_checks_passed=runtime_checks_passed,
        issues=issues
    )

    # Audit log health check complete
    logger.info(
        f"Health check completed: mode={mode}, "
        f"pre_flight={pre_flight_passed}, runtime={runtime_checks_passed}, "
        f"issues={len(issues)}"
    )

    return result


def validate_distributed_training(config: Dict[str, Any]) -> DistributedTrainingValidation:
    """Validate complete distributed training setup.

    Args:
        config: Dict with distributed training configuration

    Returns:
        DistributedTrainingValidation with aggregated results

    Raises:
        ValueError: If required config fields missing
        TypeError: If config fields have invalid types

    Security:
        - CWE-20: Input validation
        - CWE-117: Audit logging

    Configuration:
        - checkpoints: List of checkpoint paths (required)
        - gradient_updates: List of gradient update dicts (required)
        - performance_metrics: Dict with performance metrics (required)
        - health_config: Dict with health configuration (required)
    """
    # Input validation (CWE-20)
    if not isinstance(config, dict):
        raise TypeError(
            f"Invalid config: must be dictionary\n"
            f"Got: {type(config).__name__}\n"
            f"Expected: dict with keys 'checkpoints', 'gradient_updates', "
            f"'performance_metrics', 'health_config'"
        )

    # Check required fields
    required_fields = ['checkpoints', 'gradient_updates', 'performance_metrics', 'health_config']
    for field in required_fields:
        if field not in config:
            raise ValueError(
                f"Missing required field: {field}\n"
                f"Expected: dict with keys {required_fields}\n"
                f"Got: {list(config.keys())}"
            )

    # Validate field types
    if not isinstance(config['checkpoints'], list):
        raise TypeError(
            f"Expected list for 'checkpoints'\n"
            f"Got: {type(config['checkpoints']).__name__}"
        )

    if not isinstance(config['gradient_updates'], list):
        raise TypeError(
            f"Expected list for 'gradient_updates'\n"
            f"Got: {type(config['gradient_updates']).__name__}"
        )

    if not isinstance(config['performance_metrics'], dict):
        raise TypeError(
            f"Expected dict for 'performance_metrics'\n"
            f"Got: {type(config['performance_metrics']).__name__}"
        )

    if not isinstance(config['health_config'], dict):
        raise TypeError(
            f"Expected dict for 'health_config'\n"
            f"Got: {type(config['health_config']).__name__}"
        )

    # Initialize validation state
    validation_issues = []
    hardware_layer_valid = True
    worker_layer_valid = True
    checkpoint_layer_valid = True
    gradient_layer_valid = True
    performance_layer_valid = True
    health_check_passed = True

    # Hardware layer validation
    try:
        gpu_count = config['health_config'].get('gpu_count', 0)
        if gpu_count == 0:
            hardware_layer_valid = False
            validation_issues.append("Hardware layer: No GPUs detected")
    except Exception as e:
        hardware_layer_valid = False
        validation_issues.append(f"Hardware layer: {str(e)}")

    # Worker layer validation (via gradient validation)
    try:
        if config['gradient_updates']:
            gradient_result = validate_gradient_layer(config['gradient_updates'])
            if not gradient_result.is_valid:
                worker_layer_valid = False
                if not gradient_result.numerical_stability:
                    validation_issues.append("Worker layer: NaN detected in gradients")
                if gradient_result.gradient_variance > 0.1:
                    validation_issues.append("Worker layer: High gradient variance")
    except Exception as e:
        worker_layer_valid = False
        validation_issues.append(f"Worker layer: {str(e)}")

    # Checkpoint layer validation
    try:
        if config['checkpoints']:
            checkpoint_result = validate_checkpoint_layer(config['checkpoints'])
            if not checkpoint_result.is_valid:
                checkpoint_layer_valid = False
                if not checkpoint_result.version_consistency:
                    validation_issues.append("Checkpoint layer: Version mismatch")
                if checkpoint_result.corrupted_files:
                    validation_issues.append("Checkpoint layer: Corrupted files detected")
    except Exception as e:
        checkpoint_layer_valid = False
        validation_issues.append(f"Checkpoint layer: {str(e)}")

    # Gradient layer validation
    try:
        if config['gradient_updates']:
            gradient_result = validate_gradient_layer(config['gradient_updates'])
            if not gradient_result.is_valid:
                gradient_layer_valid = False
                if not gradient_result.numerical_stability:
                    validation_issues.append("Gradient layer: Numerical instability")
    except Exception as e:
        gradient_layer_valid = False
        validation_issues.append(f"Gradient layer: {str(e)}")

    # Performance layer validation
    try:
        if config['performance_metrics']:
            performance_result = monitor_performance(config['performance_metrics'])
            if not performance_result.is_within_thresholds:
                performance_layer_valid = False
                if performance_result.throughput == 0:
                    validation_issues.append("Performance layer: Zero throughput")
                if performance_result.latency_ms > 500:
                    validation_issues.append("Performance layer: High latency")
                if performance_result.gpu_utilization < 0.8:
                    validation_issues.append("Performance layer: Low GPU utilization")
    except Exception as e:
        performance_layer_valid = False
        validation_issues.append(f"Performance layer: {str(e)}")

    # Health check validation
    try:
        health_result = run_health_checks(config['health_config'], mode="pre-flight")
        if not health_result.pre_flight_passed:
            health_check_passed = False
            for issue in health_result.issues:
                validation_issues.append(f"Health check: {issue}")
    except Exception as e:
        health_check_passed = False
        validation_issues.append(f"Health check: {str(e)}")

    # Overall validation
    overall_valid = (
        hardware_layer_valid
        and worker_layer_valid
        and checkpoint_layer_valid
        and gradient_layer_valid
        and performance_layer_valid
        and health_check_passed
    )

    # Create aggregated result
    validation = DistributedTrainingValidation(
        hardware_layer_valid=hardware_layer_valid,
        worker_layer_valid=worker_layer_valid,
        checkpoint_layer_valid=checkpoint_layer_valid,
        gradient_layer_valid=gradient_layer_valid,
        performance_layer_valid=performance_layer_valid,
        health_check_passed=health_check_passed,
        validation_issues=validation_issues,
        overall_valid=overall_valid
    )

    return validation


# Export all public symbols
__all__ = [
    "CheckpointValidationResult",
    "GradientValidationResult",
    "PerformanceMetrics",
    "HealthCheckResult",
    "DistributedTrainingValidation",
    "validate_checkpoint_layer",
    "validate_gradient_layer",
    "monitor_performance",
    "run_health_checks",
    "validate_distributed_training",
    "CheckpointValidationError",
    "GradientValidationError",
    "PerformanceValidationError",
    "HealthCheckError",
]

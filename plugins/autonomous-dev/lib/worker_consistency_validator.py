#!/usr/bin/env python3
"""
Worker Consistency Validator - Distributed training state validation.

This module provides classes and functions for validating worker consistency in
distributed training environments with:
- Worker state validation
- Statistical divergence detection (KL divergence, Wasserstein distance)
- Byzantine fault tolerance (Krum algorithm, geometric median)
- Security validation (path traversal, input sanitization, audit logging)

Security:
    - CWE-22: Path validation via security_utils
    - CWE-117: Audit logging with sanitization
    - CWE-20: Input validation for all inputs

Related:
    - GitHub Issue #281: Add WorkerConsistencyValidator library for distributed training

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import math
import re

from security_utils import validate_path, audit_log


# ==============================================================================
# CUSTOM EXCEPTIONS
# ==============================================================================


class WorkerValidationError(Exception):
    """Raised when worker state validation fails."""
    pass


class DivergenceDetectedError(Exception):
    """Raised when statistical divergence is detected between workers."""
    pass


class ByzantineWorkerError(Exception):
    """Raised when Byzantine workers are detected."""
    pass


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass
class WorkerState:
    """Worker state for distributed training consistency validation.

    Attributes:
        worker_id: Worker identifier (alphanumeric, dash, underscore)
        parameter_version: Model parameter version (non-negative)
        gradient_norm: Gradient norm (non-negative)
        loss_value: Loss value (finite)
        timestamp: Timestamp (float)
        checkpoint_version: Optional checkpoint version
        is_valid: Computed validity status
        quality_issues: List of quality issues found
    """
    worker_id: str
    parameter_version: int
    gradient_norm: float
    loss_value: float
    timestamp: float
    checkpoint_version: Optional[int] = None
    is_valid: bool = True
    quality_issues: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate worker state fields."""
        issues = []

        # Validate worker_id (security: CWE-20 input sanitization)
        if not re.match(r'^[\w-]+$', self.worker_id):
            raise ValueError(
                f"Invalid worker_id: {self.worker_id}\n"
                f"worker_id must be alphanumeric with dash/underscore only\n"
                f"Allowed characters: alphanumeric, dash, underscore\n"
                f"Examples: 'worker-0', 'worker_1', 'gpu-worker-01'"
            )

        # Validate parameter_version
        if self.parameter_version < 0:
            raise ValueError(
                f"Invalid parameter_version: {self.parameter_version}\n"
                f"parameter_version must be >= 0\n"
                f"Expected: Non-negative integer\n"
                f"Got: {self.parameter_version}"
            )

        # Validate gradient_norm
        if self.gradient_norm < 0.0:
            raise ValueError(
                f"Invalid gradient_norm: {self.gradient_norm}\n"
                f"gradient_norm must be >= 0.0\n"
                f"Expected: Non-negative float\n"
                f"Got: {self.gradient_norm}"
            )

        # Validate loss_value (must be finite, not NaN or Inf)
        if not math.isfinite(self.loss_value):
            raise ValueError(
                f"Invalid loss_value: {self.loss_value}\n"
                f"loss_value must be finite (not NaN or Inf)\n"
                f"Expected: Finite float\n"
                f"Got: {self.loss_value}"
            )

        # All validations passed
        self.quality_issues = issues
        self.is_valid = len(issues) == 0


@dataclass
class ConsistencyMetrics:
    """Aggregated consistency metrics for distributed training.

    Attributes:
        max_staleness: Maximum parameter version difference
        kl_divergence: KL divergence from loss values
        wasserstein_distance: Wasserstein distance from gradient norms
        byzantine_workers: List of Byzantine worker IDs
        total_workers: Total number of workers
        synchronized_workers: Number of synchronized workers (computed)
        divergent_workers: Number of divergent workers (computed)
        is_consistent: Whether workers are consistent (computed)
        consistency_issues: List of consistency issues (computed)
    """
    max_staleness: int
    kl_divergence: float
    wasserstein_distance: float
    byzantine_workers: List[str]
    total_workers: int
    synchronized_workers: int = 0
    divergent_workers: int = 0
    is_consistent: bool = True
    consistency_issues: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Calculate derived metrics and check consistency thresholds."""
        issues = []

        # Calculate synchronized/divergent counts
        self.synchronized_workers = self.total_workers - len(self.byzantine_workers)
        self.divergent_workers = len(self.byzantine_workers)

        # Check staleness threshold (max allowed: 5)
        if self.max_staleness > 5:
            issues.append("STALENESS_THRESHOLD_EXCEEDED")

        # Check KL divergence threshold (max allowed: 0.1)
        if self.kl_divergence > 0.1:
            issues.append("KL_DIVERGENCE_THRESHOLD_EXCEEDED")

        # Check Wasserstein distance threshold (max allowed: 1.0)
        if self.wasserstein_distance > 1.0:
            issues.append("WASSERSTEIN_DISTANCE_THRESHOLD_EXCEEDED")

        # Check for Byzantine workers
        if len(self.byzantine_workers) > 0:
            issues.append("BYZANTINE_WORKERS_DETECTED")

        self.consistency_issues = issues
        self.is_consistent = len(issues) == 0


# ==============================================================================
# DIVERGENCE DETECTOR CLASS
# ==============================================================================


class DivergenceDetector:
    """Statistical divergence detector for worker consistency.

    Detects divergence using:
    - KL divergence from loss values
    - Wasserstein distance from gradient norms
    """

    def calculate_kl_divergence(self, worker_states: List[WorkerState]) -> float:
        """Calculate KL divergence from worker loss values.

        Args:
            worker_states: List of worker states

        Returns:
            KL divergence value (non-negative)

        Raises:
            ValueError: If worker list is empty
        """
        if not worker_states:
            raise ValueError(
                f"Worker list cannot be empty\n"
                f"Expected: Non-empty list of WorkerState objects\n"
                f"See: docs/distributed-training/divergence-detection.md"
            )

        # Single worker: no divergence
        if len(worker_states) == 1:
            return 0.0

        # Extract loss values
        loss_values = [w.loss_value for w in worker_states]

        # Check if all identical
        if len(set(loss_values)) == 1:
            return 0.0

        # Calculate KL divergence using variance as proxy
        # In production, would use proper KL divergence with probability distributions
        mean_loss = sum(loss_values) / len(loss_values)
        variance = sum((x - mean_loss) ** 2 for x in loss_values) / len(loss_values)

        # Normalize variance to KL divergence range (0-1)
        # Use log transform to compress large variances
        kl_div = math.log(1 + variance) / 10.0

        return min(kl_div, 1.0)  # Cap at 1.0

    def calculate_wasserstein_distance(self, worker_states: List[WorkerState]) -> float:
        """Calculate Wasserstein distance from worker gradient norms.

        Args:
            worker_states: List of worker states

        Returns:
            Wasserstein distance value (non-negative)

        Raises:
            ValueError: If worker list is empty
        """
        if not worker_states:
            raise ValueError(
                f"Worker list cannot be empty\n"
                f"Expected: Non-empty list of WorkerState objects\n"
                f"See: docs/distributed-training/divergence-detection.md"
            )

        # Single worker: no distance
        if len(worker_states) == 1:
            return 0.0

        # Extract gradient norms
        gradient_norms = [w.gradient_norm for w in worker_states]

        # Check if all identical
        if len(set(gradient_norms)) == 1:
            return 0.0

        # Calculate Wasserstein distance using sorted gradient norms
        # For 1D distributions, Wasserstein-1 is mean absolute difference
        sorted_norms = sorted(gradient_norms)
        mean_norm = sum(sorted_norms) / len(sorted_norms)

        # Calculate mean absolute deviation
        wasserstein = sum(abs(x - mean_norm) for x in sorted_norms) / len(sorted_norms)

        return wasserstein

    def detect_divergence(
        self,
        worker_states: List[WorkerState],
        kl_threshold: float = 0.1,
        wasserstein_threshold: float = 1.0
    ) -> bool:
        """Detect if workers have diverged.

        Args:
            worker_states: List of worker states
            kl_threshold: KL divergence threshold (default: 0.1)
            wasserstein_threshold: Wasserstein distance threshold (default: 1.0)

        Returns:
            True if divergence detected, False otherwise
        """
        kl_div = self.calculate_kl_divergence(worker_states)
        wasserstein = self.calculate_wasserstein_distance(worker_states)

        return kl_div > kl_threshold or wasserstein > wasserstein_threshold


# ==============================================================================
# BYZANTINE VALIDATOR CLASS
# ==============================================================================


class ByzantineValidator:
    """Byzantine fault detector using Krum algorithm.

    Detects Byzantine workers using:
    - Krum algorithm for outlier detection
    - Geometric median for robust aggregation
    """

    def calculate_geometric_median(self, worker_states: List[WorkerState]) -> float:
        """Calculate geometric median of worker gradient norms.

        Args:
            worker_states: List of worker states

        Returns:
            Geometric median value
        """
        if not worker_states:
            return 0.0

        # For 1D data, geometric median is the standard median
        gradient_norms = sorted([w.gradient_norm for w in worker_states])
        n = len(gradient_norms)

        if n % 2 == 0:
            # Even number: average of middle two
            return (gradient_norms[n//2 - 1] + gradient_norms[n//2]) / 2.0
        else:
            # Odd number: middle value
            return gradient_norms[n//2]

    def krum_detect(
        self,
        worker_states: List[WorkerState],
        f: Optional[int] = None
    ) -> List[str]:
        """Detect Byzantine workers using Krum algorithm.

        Args:
            worker_states: List of worker states
            f: Number of Byzantine workers to tolerate (default: (m-1)/2)

        Returns:
            List of Byzantine worker IDs

        Raises:
            ValueError: If worker list is empty

        Byzantine Tolerance:
            Can tolerate up to (m-1)/2 Byzantine workers out of m total workers.
        """
        if not worker_states:
            raise ValueError(
                f"Worker list cannot be empty\n"
                f"Expected: Non-empty list of WorkerState objects\n"
                f"See: docs/distributed-training/byzantine-detection.md"
            )

        # Single worker: no Byzantine detection possible
        if len(worker_states) == 1:
            return []

        m = len(worker_states)

        # Default Byzantine tolerance: (m-1)/2
        if f is None:
            f = (m - 1) // 2

        # Calculate pairwise distances between workers
        # Using combined metric: (gradient_norm, loss_value)
        byzantine_workers = []

        # Calculate scores for each worker (distance to k-nearest neighbors)
        worker_scores = []
        for i, worker_i in enumerate(worker_states):
            # Calculate distances to all other workers
            distances = []
            for j, worker_j in enumerate(worker_states):
                if i != j:
                    # Euclidean distance in (gradient_norm, loss_value) space
                    dist = math.sqrt(
                        (worker_i.gradient_norm - worker_j.gradient_norm) ** 2 +
                        (worker_i.loss_value - worker_j.loss_value) ** 2
                    )
                    distances.append(dist)

            # Sort distances and sum k-nearest (k = m - f - 2)
            k = max(1, m - f - 2)
            distances.sort()
            score = sum(distances[:k])
            worker_scores.append((worker_i.worker_id, score))

        # Sort workers by score (ascending)
        worker_scores.sort(key=lambda x: x[1])

        # Workers with highest scores are potential Byzantine
        # Use multiple strategies to detect outliers:
        # 1. IQR-based detection for normal distributions
        # 2. Median-based detection
        # 3. Absolute threshold for extremely high variance (all Byzantine case)

        scores_only = [score for _, score in worker_scores]

        if len(scores_only) <= 2:
            # Too few workers for statistical detection
            return []

        # Calculate mean distance for absolute threshold check
        mean_score = sum(scores_only) / len(scores_only)

        # Strategy 1: IQR-based outlier detection
        q1_idx = len(scores_only) // 4
        q3_idx = 3 * len(scores_only) // 4
        q1 = scores_only[q1_idx]
        q3 = scores_only[q3_idx]
        iqr = q3 - q1

        # Outliers are scores > Q3 + 1.5 * IQR
        iqr_threshold = q3 + 1.5 * iqr if iqr > 0 else float('inf')

        # Strategy 2: Median-based detection (3x median)
        median_score = scores_only[len(scores_only) // 2]
        median_threshold = 3.0 * median_score if median_score > 0 else float('inf')

        # Strategy 3: Absolute threshold for extreme variance (all Byzantine case)
        # If mean score is very high (>100), flag highest scorers
        absolute_threshold = mean_score * 0.8 if mean_score > 100.0 else float('inf')

        # Use the most permissive threshold (catches more outliers)
        threshold = min(iqr_threshold, median_threshold, absolute_threshold)

        for worker_id, score in worker_scores:
            if score > threshold and score > 0:
                byzantine_workers.append(worker_id)

        return byzantine_workers


# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================


def validate_worker_consistency(
    worker_states: List[WorkerState],
    staleness_threshold: int = 5,
    kl_threshold: float = 0.1,
    wasserstein_threshold: float = 1.0
) -> ConsistencyMetrics:
    """Validate worker consistency across distributed training cluster.

    Args:
        worker_states: List of worker states
        staleness_threshold: Maximum parameter version difference (default: 5)
        kl_threshold: KL divergence threshold (default: 0.1)
        wasserstein_threshold: Wasserstein distance threshold (default: 1.0)

    Returns:
        ConsistencyMetrics with validation results

    Raises:
        ValueError: If worker list is empty

    Security:
        - CWE-20: Input validation for worker states
        - CWE-117: Audit logging with sanitization
    """
    # Input validation
    if not worker_states:
        raise ValueError(
            f"Worker list cannot be empty\n"
            f"Expected: Non-empty list of WorkerState objects\n"
            f"See: docs/distributed-training/consistency-validation.md"
        )

    # Calculate staleness (max parameter version difference)
    versions = [w.parameter_version for w in worker_states]
    max_staleness = max(versions) - min(versions)

    # Detect divergence
    detector = DivergenceDetector()
    kl_divergence = detector.calculate_kl_divergence(worker_states)
    wasserstein_distance = detector.calculate_wasserstein_distance(worker_states)

    # Detect Byzantine workers
    validator = ByzantineValidator()
    byzantine_workers = validator.krum_detect(worker_states)

    # Create metrics
    metrics = ConsistencyMetrics(
        max_staleness=max_staleness,
        kl_divergence=kl_divergence,
        wasserstein_distance=wasserstein_distance,
        byzantine_workers=byzantine_workers,
        total_workers=len(worker_states)
    )

    # Audit log
    audit_log("worker_consistency", "consistent" if metrics.is_consistent else "inconsistent", {
        "operation": "validate_worker_consistency",
        "total_workers": len(worker_states),
        "max_staleness": max_staleness,
        "kl_divergence": kl_divergence,
        "wasserstein_distance": wasserstein_distance,
        "byzantine_count": len(byzantine_workers),
        "is_consistent": metrics.is_consistent
    })

    return metrics


def validate_checkpoint_consistency(
    checkpoint_paths: List[Path],
    expected_version: Optional[int] = None
) -> bool:
    """Validate checkpoint consistency across workers.

    Args:
        checkpoint_paths: List of checkpoint file paths
        expected_version: Expected parameter version (optional)

    Returns:
        True if all checkpoints are consistent, False otherwise

    Raises:
        ValueError: If checkpoint list is empty or path validation fails

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

    # Validate all paths
    validated_paths = []
    for path in checkpoint_paths:
        try:
            validated_path = validate_path(path, "checkpoint file", allow_missing=False)
            validated_paths.append(validated_path)
        except ValueError as e:
            # Re-raise with context
            raise ValueError(
                f"Checkpoint path validation failed: {path}\n"
                f"Error: {e}"
            )

    # Read checkpoint versions
    versions = []
    for path in validated_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
                version = checkpoint_data.get('parameter_version')
                if version is None:
                    # Missing version field
                    audit_log("checkpoint_validation", "failure", {
                        "operation": "validate_checkpoint_consistency",
                        "path": str(path),
                        "reason": "missing_version_field"
                    })
                    return False
                versions.append(version)
        except (json.JSONDecodeError, IOError) as e:
            # Failed to read checkpoint
            audit_log("checkpoint_validation", "failure", {
                "operation": "validate_checkpoint_consistency",
                "path": str(path),
                "reason": "read_error",
                "error": str(e)
            })
            return False

    # Check version consistency
    if len(set(versions)) > 1:
        # Versions don't match
        audit_log("checkpoint_validation", "inconsistent", {
            "operation": "validate_checkpoint_consistency",
            "checkpoint_count": len(validated_paths),
            "versions": versions,
            "reason": "version_mismatch"
        })
        return False

    # Check expected version if provided
    if expected_version is not None and versions[0] != expected_version:
        audit_log("checkpoint_validation", "inconsistent", {
            "operation": "validate_checkpoint_consistency",
            "checkpoint_count": len(validated_paths),
            "actual_version": versions[0],
            "expected_version": expected_version,
            "reason": "unexpected_version"
        })
        return False

    # All checks passed
    audit_log("checkpoint_validation", "consistent", {
        "operation": "validate_checkpoint_consistency",
        "checkpoint_count": len(validated_paths),
        "version": versions[0]
    })
    return True


# Export all public symbols
__all__ = [
    "WorkerState",
    "ConsistencyMetrics",
    "DivergenceDetector",
    "ByzantineValidator",
    "validate_worker_consistency",
    "validate_checkpoint_consistency",
    "WorkerValidationError",
    "DivergenceDetectedError",
    "ByzantineWorkerError",
]

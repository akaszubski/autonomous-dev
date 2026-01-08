#!/usr/bin/env python3
"""
Data models for implement dispatcher.

Defines dataclasses for:
    - ImplementRequest: Input request with mode and parameters
    - ImplementResult: Output result with success status and message

Date: 2026-01-09
Issue: Consolidate /implement, /auto-implement, /batch-implement
Agent: implementer
Status: GREEN (implementation complete)
"""

from dataclasses import dataclass, field
from typing import Optional, List
from .modes import ImplementMode


@dataclass
class ImplementRequest:
    """
    Request to implement a feature.

    Attributes:
        mode: Implementation mode (FULL_PIPELINE, QUICK, or BATCH)
        feature_description: Feature description for FULL_PIPELINE or QUICK
        batch_file: Path to batch features file for BATCH mode
        issue_numbers: List of GitHub issue numbers for BATCH mode
        batch_id: Batch ID for BATCH resume mode
    """

    mode: ImplementMode
    feature_description: Optional[str] = None
    batch_file: Optional[str] = None
    issue_numbers: Optional[List[int]] = None
    batch_id: Optional[str] = None

    def __post_init__(self):
        """Validate request after initialization."""
        # Ensure mode is ImplementMode enum
        if not isinstance(self.mode, ImplementMode):
            raise TypeError(f"mode must be ImplementMode, got {type(self.mode)}")

    @property
    def is_valid(self) -> bool:
        """Check if request has required fields for its mode."""
        if self.mode == ImplementMode.FULL_PIPELINE:
            return self.feature_description is not None and len(self.feature_description.strip()) > 0

        if self.mode == ImplementMode.QUICK:
            return self.feature_description is not None and len(self.feature_description.strip()) > 0

        if self.mode == ImplementMode.BATCH:
            return (
                self.batch_file is not None
                or (self.issue_numbers is not None and len(self.issue_numbers) > 0)
                or self.batch_id is not None
            )

        return False

    def to_dict(self) -> dict:
        """Convert request to dictionary."""
        return {
            "mode": self.mode.value,
            "feature_description": self.feature_description,
            "batch_file": self.batch_file,
            "issue_numbers": self.issue_numbers,
            "batch_id": self.batch_id,
        }


@dataclass
class ImplementResult:
    """
    Result of implement command execution.

    Attributes:
        success: Whether implementation succeeded
        message: Result message or error description
        mode_used: Implementation mode that was used
        details: Optional additional details about execution
    """

    success: bool
    message: str
    mode_used: ImplementMode
    details: Optional[dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "message": self.message,
            "mode_used": self.mode_used.value,
            "details": self.details,
        }

    def __str__(self) -> str:
        """String representation of result."""
        status = "SUCCESS" if self.success else "FAILED"
        return f"[{status}] {self.message} (mode: {self.mode_used.value})"

#!/usr/bin/env python3
"""
Auto-apply logic for doc-master agent.

Applies LOW_RISK documentation updates automatically without user prompts.
HIGH_RISK updates require user approval in interactive mode or are skipped in batch mode.

Date: 2026-01-09
Issue: #204
Agent: implementer
"""

import os
import json
import logging
from pathlib import Path
from typing import NamedTuple, Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from doc_update_risk_classifier import RiskLevel, RiskClassification, classify_doc_update

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class DocUpdate:
    """A documentation update to apply."""
    file_path: str
    content: str
    risk_classification: RiskClassification


class DocUpdateResult(NamedTuple):
    """Result of applying a documentation update."""
    applied: bool
    required_approval: bool
    user_approved: Optional[bool]
    message: str
    file_path: str
    error: Optional[str] = None


class DocUpdateApplier:
    """Apply documentation updates based on risk classification."""

    def __init__(self, batch_mode: bool = False, auto_approve: bool = False):
        """
        Initialize the applier.

        Args:
            batch_mode: If True, skip HIGH_RISK updates instead of prompting
            auto_approve: If True, auto-approve all updates (testing only)
        """
        self.batch_mode = batch_mode
        self.auto_approve = auto_approve
        self._skipped_updates: List[DocUpdate] = []
        self._applied_updates: List[DocUpdateResult] = []

    def apply(self, update: DocUpdate) -> DocUpdateResult:
        """
        Apply a single documentation update.

        Args:
            update: DocUpdate to apply

        Returns:
            DocUpdateResult with success status and action taken
        """
        risk = update.risk_classification

        # LOW_RISK: Auto-apply without prompt
        if risk.risk_level == RiskLevel.LOW_RISK or self.auto_approve:
            return self._write_update(update)

        # HIGH_RISK in batch mode: Skip with logging
        if self.batch_mode:
            self._skipped_updates.append(update)
            logger.info(f"Skipped HIGH_RISK update (batch mode): {update.file_path}")
            return DocUpdateResult(
                applied=False,
                required_approval=True,
                user_approved=None,  # No user interaction in batch mode
                message=f"HIGH_RISK update skipped in batch mode: {risk.reason}",
                file_path=update.file_path
            )

        # HIGH_RISK in interactive mode: Prompt user for approval
        print(f"\n⚠️  HIGH_RISK documentation update detected:")
        print(f"   File: {update.file_path}")
        print(f"   Reason: {risk.reason}")
        print(f"   Confidence: {risk.confidence:.0%}")

        user_input = input("\nApprove this change? (y/n): ").strip().lower()
        user_approved = user_input in ['y', 'yes']

        if user_approved:
            # User approved - apply the update
            result = self._write_update(update)
            return DocUpdateResult(
                applied=result.applied,
                required_approval=True,
                user_approved=True,
                message=f"User approved: {risk.reason}",
                file_path=update.file_path,
                error=result.error
            )
        else:
            # User rejected - skip the update
            logger.info(f"User rejected HIGH_RISK update: {update.file_path}")
            return DocUpdateResult(
                applied=False,
                required_approval=True,
                user_approved=False,
                message=f"User rejected: {risk.reason}",
                file_path=update.file_path
            )

    def _write_update(self, update: DocUpdate) -> DocUpdateResult:
        """Write the update to disk."""
        try:
            path = Path(update.file_path)

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write content (use open() directly for testability with mocked open())
            with open(update.file_path, 'w', encoding='utf-8') as f:
                f.write(update.content)

            result = DocUpdateResult(
                applied=True,
                required_approval=False,
                user_approved=None,  # No user interaction needed for LOW_RISK
                message=f"Auto-applied: {update.risk_classification.reason}",
                file_path=update.file_path
            )
            self._applied_updates.append(result)
            logger.info(f"Applied update: {update.file_path}")
            return result

        except Exception as e:
            logger.error(f"Failed to apply update {update.file_path}: {e}")
            return DocUpdateResult(
                applied=False,
                required_approval=False,
                user_approved=None,
                message=f"Write failed: {e}",
                file_path=update.file_path,
                error=str(e)
            )

    @property
    def skipped_updates(self) -> List[DocUpdate]:
        """Get list of skipped HIGH_RISK updates."""
        return self._skipped_updates

    @property
    def applied_updates(self) -> List[DocUpdateResult]:
        """Get list of successfully applied updates."""
        return self._applied_updates


def auto_apply_doc_update(
    update: Optional[DocUpdate] = None,
    file_path: Optional[str] = None,
    content: Optional[str] = None,
    changes: Optional[List[str]] = None,
    batch_mode: bool = False
) -> DocUpdateResult:
    """
    Convenience function to classify and apply a documentation update.

    Supports two call patterns:
    1. auto_apply_doc_update(update=DocUpdate(...), batch_mode=False)
    2. auto_apply_doc_update(file_path="...", content="...", changes=[...], batch_mode=False)

    Args:
        update: Pre-built DocUpdate object (pattern 1)
        file_path: Path to the documentation file (pattern 2)
        content: New content to write (pattern 2)
        changes: List of changed lines (pattern 2)
        batch_mode: If True, skip HIGH_RISK updates

    Returns:
        DocUpdateResult with success status and action taken
    """
    # Handle invalid input
    if update is None and (file_path is None or content is None):
        return DocUpdateResult(
            applied=False,
            required_approval=False,
            user_approved=None,
            message="Error: Invalid update object (None provided)",
            file_path="unknown",
            error="Invalid update object"
        )

    # Pattern 1: update object provided
    if update is not None:
        applier = DocUpdateApplier(batch_mode=batch_mode)
        return applier.apply(update)

    # Pattern 2: individual parameters provided

    # Classify risk
    classification = classify_doc_update(file_path, changes or [])

    # Create update
    doc_update = DocUpdate(
        file_path=file_path,
        content=content,
        risk_classification=classification
    )

    # Apply
    applier = DocUpdateApplier(batch_mode=batch_mode)
    return applier.apply(doc_update)


def apply_doc_updates_batch(
    updates: List[DocUpdate],
    batch_mode: bool = True
) -> List[DocUpdateResult]:
    """
    Apply multiple documentation updates in batch.

    Args:
        updates: List of DocUpdate objects
        batch_mode: If True, skip HIGH_RISK updates

    Returns:
        List of DocUpdateResult for each update
    """
    applier = DocUpdateApplier(batch_mode=batch_mode)
    results = []

    for update in updates:
        result = applier.apply(update)
        results.append(result)

    # Log summary
    applied = sum(1 for r in results if r.applied)
    skipped = sum(1 for r in results if not r.applied and r.required_approval)
    failed = sum(1 for r in results if not r.applied and not r.required_approval and r.error)
    logger.info(f"Batch update complete: {applied} applied, {skipped} skipped, {failed} failed")

    return results

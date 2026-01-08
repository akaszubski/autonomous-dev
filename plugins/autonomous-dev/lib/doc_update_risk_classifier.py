#!/usr/bin/env python3
"""
Risk classifier for documentation updates.

Classifies documentation changes as LOW_RISK (auto-apply) or HIGH_RISK (requires approval).

LOW_RISK (auto-apply without prompt):
- CHANGELOG.md: All changes
- README.md: All changes
- PROJECT.md: Metadata only (timestamps, component counts, compliance dates)

HIGH_RISK (requires approval):
- PROJECT.md: GOALS, CONSTRAINTS, SCOPE, ARCHITECTURE changes

Date: 2026-01-09
Issue: #204
Agent: implementer
"""

from enum import Enum
from typing import NamedTuple, Optional, List, Dict
from pathlib import Path
import re


class RiskLevel(Enum):
    """Risk level for documentation updates."""
    LOW_RISK = "low_risk"  # Auto-apply without prompt
    HIGH_RISK = "high_risk"  # Requires user approval


class RiskClassification(NamedTuple):
    """Result of risk classification."""
    risk_level: RiskLevel
    confidence: float  # 0.0 to 1.0
    reason: str
    requires_approval: bool


class DocUpdateRiskClassifier:
    """Classify documentation updates by risk level."""

    # Files that are always LOW_RISK
    LOW_RISK_FILES = {"CHANGELOG.md", "README.md"}

    # PROJECT.md sections that are HIGH_RISK (strategic changes)
    HIGH_RISK_SECTIONS = {"GOALS", "CONSTRAINTS", "SCOPE", "ARCHITECTURE"}

    # PROJECT.md patterns that are LOW_RISK (metadata)
    LOW_RISK_PATTERNS = [
        r"\*\*Last Updated\*\*",
        r"\*\*Last Compliance Check\*\*",
        r"\*\*Last Validated\*\*",
        r"\| Component \| Version \| Count \| Status \|",
        r"\| Skills \| .+ \| \d+ \|",
        r"\| Commands \| .+ \| \d+ \|",
        r"\| Agents \| .+ \| \d+ \|",
        r"\| Hooks \| .+ \| \d+ \|",
        r"\| Settings \| .+ \| \d+ \|",
    ]

    @classmethod
    def classify(cls, file_path: str, changes: List[str]) -> RiskClassification:
        """
        Classify a documentation update by risk level.

        Args:
            file_path: Path to the documentation file
            changes: List of changed lines/content

        Returns:
            RiskClassification with risk level, confidence, and reason
        """
        # Handle None file_path
        if file_path is None:
            return RiskClassification(
                risk_level=RiskLevel.HIGH_RISK,
                confidence=0.5,
                reason="Unknown documentation file: None",
                requires_approval=True
            )

        # Normalize file path
        path = Path(file_path)
        filename = path.name

        # Handle None or empty changes
        if changes is None or (isinstance(changes, list) and len(changes) == 0):
            # Empty changes for known LOW_RISK files = LOW_RISK with low confidence
            if filename in cls.LOW_RISK_FILES:
                return RiskClassification(
                    risk_level=RiskLevel.LOW_RISK,
                    confidence=0.3,  # Low confidence for empty changes
                    reason=f"{filename} update (empty diff)",
                    requires_approval=False
                )

        # Check if always LOW_RISK file (non-empty changes)
        if filename in cls.LOW_RISK_FILES:
            return RiskClassification(
                risk_level=RiskLevel.LOW_RISK,
                confidence=0.95,
                reason=f"{filename} update",
                requires_approval=False
            )

        # Check PROJECT.md (can be either risk level)
        if filename == "PROJECT.md" or "PROJECT.md" in str(file_path):
            return cls._classify_project_md(changes)

        # Unknown file - default to HIGH_RISK (safe default)
        return RiskClassification(
            risk_level=RiskLevel.HIGH_RISK,
            confidence=0.5,
            reason=f"Unknown documentation file: {filename}",
            requires_approval=True
        )

    @classmethod
    def _classify_project_md(cls, changes: List[str]) -> RiskClassification:
        """Classify PROJECT.md changes."""
        if not changes or changes is None:
            return RiskClassification(
                risk_level=RiskLevel.LOW_RISK,
                confidence=0.3,  # Low confidence for empty changes
                reason="Empty PROJECT.md changes",
                requires_approval=False
            )

        # Check for HIGH_RISK section changes
        changes_text = "\n".join(changes)
        for section in cls.HIGH_RISK_SECTIONS:
            # Look for section headers or significant changes
            if re.search(rf"##\s*{section}", changes_text, re.IGNORECASE):
                return RiskClassification(
                    risk_level=RiskLevel.HIGH_RISK,
                    confidence=0.9,
                    reason=f"PROJECT.md {section} section change",
                    requires_approval=True
                )

        # Check if changes match LOW_RISK patterns (metadata)
        metadata_match_count = 0
        for pattern in cls.LOW_RISK_PATTERNS:
            if re.search(pattern, changes_text):
                metadata_match_count += 1

        if metadata_match_count > 0:
            confidence = min(0.95, 0.7 + (metadata_match_count * 0.05))
            return RiskClassification(
                risk_level=RiskLevel.LOW_RISK,
                confidence=confidence,
                reason="PROJECT.md metadata update",
                requires_approval=False
            )

        # Default for PROJECT.md: HIGH_RISK (conservative)
        return RiskClassification(
            risk_level=RiskLevel.HIGH_RISK,
            confidence=0.6,
            reason="PROJECT.md content change (unclassified)",
            requires_approval=True
        )


def classify_doc_update(file_path: str, changes: List[str]) -> RiskClassification:
    """Convenience function to classify a documentation update."""
    return DocUpdateRiskClassifier.classify(file_path, changes)

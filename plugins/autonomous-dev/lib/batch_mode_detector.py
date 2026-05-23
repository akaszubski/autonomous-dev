#!/usr/bin/env python3
"""
Batch Mode Detector - Detect pipeline mode (full/fix/light) per batch issue.

Analyzes issue title, body, and labels to determine the appropriate pipeline
mode for each issue in a /implement --batch --issues run.

Key Components:
1. PipelineMode enum: FULL, FIX, LIGHT
2. ModeDetection dataclass: mode, confidence, signals, source
3. detect_issue_mode(): Detect mode for a single issue
4. detect_batch_modes(): Detect modes for a list of issues
5. format_mode_summary_table(): Format results as a display table

Signal Sources (priority order):
1. Labels: "bug" → FIX, "documentation" → LIGHT (highest priority, override)
2. Title matches: 2 points per signal
3. Body matches: 1 point per signal
4. Default: FULL (when no signals detected)

Date: 2026-03-29
Issue: #600 (Add per-issue mode detection to /implement --batch)
Agent: implementer
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# =============================================================================
# ENUMS
# =============================================================================


class PipelineMode(Enum):
    """Pipeline execution mode for batch issues."""

    FULL = "full"
    FIX = "fix"
    LIGHT = "light"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ModeDetection:
    """Result of pipeline mode detection for a single issue.

    Attributes:
        mode: Detected pipeline mode
        confidence: Confidence score (0.0 = default, higher = more signals)
        signals: List of signal descriptions that contributed to detection
        source: Primary source of detection ("label", "title", "body", "default")
    """

    mode: PipelineMode
    confidence: float = 0.0
    signals: List[str] = field(default_factory=list)
    source: str = "default"


# =============================================================================
# SIGNAL DEFINITIONS
# =============================================================================

# Fix signals (case-insensitive) — from implement.md STEP 0
FIX_SIGNALS: List[str] = [
    "fix test",
    "failing test",
    "broken test",
    "test failure",
    "flaky test",
    "skip test",
    "bug",
    "error",
    "broken",
    "crash",
    "regression",
    "false positive",
    "false-positive",
    "guard fires",
    "blocks",
    "blocked",
    "stale",
    "hardening",
    "umbrella",
    "missing check",
    "misclass",
    "drift",
    "[ci]",
]

# Light signals (case-insensitive)
LIGHT_SIGNALS: List[str] = [
    "update docs",
    "update readme",
    "readme",
    "changelog",
    "typo",
    "rename",
    "config change",
    "update comment",
]

# Label overrides (highest priority)
LABEL_FIX: List[str] = ["bug", "auto-improvement"]
LABEL_LIGHT: List[str] = ["documentation"]


# =============================================================================
# DETECTION FUNCTIONS
# =============================================================================


def detect_issue_mode(
    title: str,
    body: str = "",
    labels: Optional[List[str]] = None,
) -> ModeDetection:
    """Detect pipeline mode for a single issue based on title, body, and labels.

    Priority:
    1. Label override (highest): "bug" → FIX, "documentation" → LIGHT
    2. Signal matching: title matches = 2 points, body matches = 1 point
    3. Tie-break: fix wins over light
    4. Default: FULL (no signals)

    Args:
        title: Issue title
        body: Issue body (optional)
        labels: List of label names (optional)

    Returns:
        ModeDetection with detected mode, confidence, signals, and source
    """
    if labels is None:
        labels = []

    # Normalize labels to lowercase
    labels_lower = [lbl.lower() for lbl in labels]

    # --- Priority 1: Label overrides ---
    for lbl in labels_lower:
        if lbl in LABEL_FIX:
            return ModeDetection(
                mode=PipelineMode.FIX,
                confidence=1.0,
                signals=[f'label "{lbl}"'],
                source="label",
            )

    for lbl in labels_lower:
        if lbl in LABEL_LIGHT:
            return ModeDetection(
                mode=PipelineMode.LIGHT,
                confidence=1.0,
                signals=[f'label "{lbl}"'],
                source="label",
            )

    # --- Priority 2: Signal matching ---
    title_lower = title.lower()
    body_lower = body.lower()

    fix_score = 0
    fix_signals: List[str] = []
    light_score = 0
    light_signals: List[str] = []

    for signal in FIX_SIGNALS:
        if signal in title_lower:
            fix_score += 2
            fix_signals.append(f'"{signal}" (title)')
        if signal in body_lower:
            fix_score += 1
            fix_signals.append(f'"{signal}" (body)')

    for signal in LIGHT_SIGNALS:
        if signal in title_lower:
            light_score += 2
            light_signals.append(f'"{signal}" (title)')
        if signal in body_lower:
            light_score += 1
            light_signals.append(f'"{signal}" (body)')

    # --- Priority 3: Tie-break (fix wins) and selection ---
    if fix_score > 0 and fix_score >= light_score:
        source = "title" if any("(title)" in s for s in fix_signals) else "body"
        return ModeDetection(
            mode=PipelineMode.FIX,
            confidence=min(fix_score / 4.0, 1.0),
            signals=fix_signals,
            source=source,
        )

    if light_score > 0:
        source = "title" if any("(title)" in s for s in light_signals) else "body"
        return ModeDetection(
            mode=PipelineMode.LIGHT,
            confidence=min(light_score / 4.0, 1.0),
            signals=light_signals,
            source=source,
        )

    # --- Priority 4: Default ---
    return ModeDetection(
        mode=PipelineMode.FULL,
        confidence=0.0,
        signals=[],
        source="default",
    )


def detect_batch_modes(issues: List[dict]) -> List[ModeDetection]:
    """Detect pipeline modes for a list of issues.

    Args:
        issues: List of dicts with "title", optional "body", optional "labels" keys.
            Labels should be list of strings (label names).

    Returns:
        List of ModeDetection, one per issue (same order as input)
    """
    results: List[ModeDetection] = []
    for issue in issues:
        title = issue.get("title", "")
        body = issue.get("body", "")
        labels = issue.get("labels", None)
        # Handle labels that come as list of dicts (GitHub API format: [{name: "bug"}])
        if labels and isinstance(labels, list) and len(labels) > 0:
            if isinstance(labels[0], dict):
                labels = [lbl.get("name", "") for lbl in labels]
        results.append(detect_issue_mode(title, body or "", labels))
    return results


# =============================================================================
# FORMATTING
# =============================================================================


def format_mode_summary_table(
    issue_numbers: List[int],
    titles: List[str],
    modes: List[ModeDetection],
) -> str:
    """Format mode detection results as a summary table.

    Args:
        issue_numbers: List of GitHub issue numbers
        titles: List of issue titles (same order)
        modes: List of ModeDetection results (same order)

    Returns:
        Formatted table string for display

    Example output:
        Issue  Title                          Detected Mode  Signals
        #101   Fix failing auth test          --fix          "failing test" (title)
        #102   Add JWT authentication         full           (no signals)
        #103   Update README setup section    --light        "readme" (title)
    """
    if not issue_numbers:
        return ""

    # Build rows
    rows: List[tuple] = []
    for i, (num, title, detection) in enumerate(zip(issue_numbers, titles, modes)):
        # Truncate title for display
        display_title = title[:30] + "..." if len(title) > 30 else title

        # Format mode
        if detection.mode == PipelineMode.FULL:
            mode_str = "full"
        elif detection.mode == PipelineMode.FIX:
            mode_str = "--fix"
        else:
            mode_str = "--light"

        # Format signals
        if detection.signals:
            signals_str = ", ".join(detection.signals)
        else:
            signals_str = "(no signals)"

        rows.append((f"#{num}", display_title, mode_str, signals_str))

    # Calculate column widths
    headers = ("Issue", "Title", "Detected Mode", "Signals")
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    # Format header
    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    # Format rows
    row_lines = []
    for row in rows:
        line = "  ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row))
        row_lines.append(line)

    return header_line + "\n" + "\n".join(row_lines)

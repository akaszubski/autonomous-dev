"""CIA finding → GitHub issue promotion filter.

Gates the promotion of CIA findings to GitHub issues via configurable
severity, confidence, and recurrence thresholds. Sub-threshold findings
remain stored in `.claude/logs/findings/*.jsonl` for trend analysis but
are not promoted to issues.

The filter is layered ON TOP of `macro_promotion.decide_promotions` —
this module returns (allow, reason); the caller decides what to do with
held findings.

GitHub Issue: #1251
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Severity tier mapping. Lower tier = more permissive.
# Stored severities ({"info","warning","error"}) map to threshold tiers
# ({"info","low","medium","high"}) as follows:
_SEVERITY_TIER: dict[str, int] = {
    # stored
    "info": 1,
    "warning": 3,
    "error": 4,
    # threshold-only synonyms
    "low": 1,
    "medium": 3,
    "high": 4,
}

_DEFAULTS_PATH = Path(__file__).parent / "config" / "cia_filter_defaults.json"

_REQUIRED_KEYS = ("min_severity", "min_confidence", "min_recurrence", "recurrence_window_days")


def _git_toplevel() -> Path | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return Path(out) if out else None
    except (subprocess.CalledProcessError, OSError):
        return None


def _load_defaults() -> dict[str, Any]:
    try:
        with _DEFAULTS_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        # Last-resort hardcoded defaults; mirrors the shipped JSON.
        return {
            "min_severity": "info",
            "min_confidence": 0.0,
            "min_recurrence": 2,
            "recurrence_window_days": 7,
        }


def load_filter_config(project_root: Path | None = None) -> dict[str, Any]:
    """Load CIA filter config.

    Resolution order:
    1. Project override at `<project_root>/.claude/config/cia_filter.json`.
    2. Shipped defaults at `plugins/autonomous-dev/lib/config/cia_filter_defaults.json`.
    3. Hardcoded last-resort defaults.

    When the project override is partially specified (missing keys), the
    defaults fill in the gaps.

    Args:
        project_root: Directory to search for `.claude/config/cia_filter.json`.
            If None, uses `git rev-parse --show-toplevel`.

    Returns:
        A dict with all four required keys: min_severity, min_confidence,
        min_recurrence, recurrence_window_days.
    """
    defaults = _load_defaults()
    merged: dict[str, Any] = dict(defaults)

    if project_root is None:
        project_root = _git_toplevel()

    if project_root is not None:
        override_path = Path(project_root) / ".claude" / "config" / "cia_filter.json"
        if override_path.is_file():
            try:
                with override_path.open(encoding="utf-8") as fh:
                    override = json.load(fh)
                if isinstance(override, dict):
                    for key in _REQUIRED_KEYS:
                        if key in override:
                            merged[key] = override[key]
            except (OSError, json.JSONDecodeError) as exc:
                sys.stderr.write(
                    f"[cia-promotion-filter] failed to read {override_path}: {exc}; using defaults\n"
                )

    return merged


def should_promote(
    signal: dict[str, Any],
    *,
    config: dict[str, Any],
) -> tuple[bool, str]:
    """Decide whether a CIA signal should be promoted to a GitHub issue.

    The error-severity bypass takes precedence: any signal whose stored
    `max_severity_label == "error"` always promotes regardless of other
    thresholds, so high-signal class events are never silently dropped
    due to a tight filter.

    Args:
        signal: A dict-shaped signal with `frequency: int` and
            `raw_data: dict` (containing `max_severity_label`, optional
            `confidence`, `distinct_sessions`).
        config: Filter config (see `load_filter_config`).

    Returns:
        `(True, reason)` if the signal should be promoted to a GitHub issue,
        else `(False, reason)`. The reason is a short human-readable string.
    """
    raw = signal.get("raw_data", {}) if isinstance(signal, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    max_label = str(raw.get("max_severity_label", "info")).lower()

    # Bypass: error severity always promotes.
    if max_label == "error":
        return (True, "error-bypass: max_severity_label='error' always promotes")

    # Severity gate.
    min_severity = str(config.get("min_severity", "info")).lower()
    stored_tier = _SEVERITY_TIER.get(max_label, 1)
    min_tier = _SEVERITY_TIER.get(min_severity, 1)
    if stored_tier < min_tier:
        return (False, f"severity {max_label!r} below min_severity {min_severity!r}")

    # Confidence gate. Missing confidence treated as 1.0 (do not reject on absence).
    min_confidence = float(config.get("min_confidence", 0.0))
    confidence_val = raw.get("confidence")
    if confidence_val is None:
        confidence = 1.0
    else:
        try:
            confidence = float(confidence_val)
        except (TypeError, ValueError):
            confidence = 1.0
    if confidence < min_confidence:
        return (False, f"confidence {confidence:.2f} below min_confidence {min_confidence:.2f}")

    # Recurrence gate (uses signal.frequency as proxy).
    min_recurrence = int(config.get("min_recurrence", 1))
    try:
        frequency = int(signal.get("frequency", 0))
    except (TypeError, ValueError):
        frequency = 0
    if frequency < min_recurrence:
        return (False, f"recurrence (frequency={frequency}) below min_recurrence {min_recurrence}")

    return (True, "all thresholds passed")
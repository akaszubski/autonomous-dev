"""Helper for persisting plan-critic verdicts to disk.

Issue #1468: The `plan-critic` agent (`agents/plan-critic.md`) is a
read-only agent (`tools: [WebSearch, Read, Grep, Glob, Bash]` — no
`Write`). Its previous prompt instructed it to persist the HARD GATE
artifact `.claude/plan_critic_verdict.json` via an inline Python heredoc
executed through `Bash`. That heredoc-write is not a first-class tool
call — the hook stack cannot reason about it structurally — and it fell
through to a live user permission prompt mid-pipeline during the
issue #1405 batch run.

This module moves the write out of the agent and into a small,
testable helper that the coordinator (already `main`, already
`Write`-capable) invokes AFTER plan-critic returns its structured
verdict.

Verdict schema (matches the pre-#1468 file layout so downstream
consumers — `unified_session_tracker._advance_plan_mode_stage`,
`plan_mode_exit_detector`, `unified_pre_tool.py` verdict gate — keep
working without change):

    {
      "verdict":         "PROCEED" | "REVISE" | "BLOCKED",
      "composite_score": float,     # arithmetic mean of axis scores
      "timestamp":       ISO8601 UTC string,
      "reasoning":       str,       # >= 100 chars of substantive critique
      "axis_scores":     {axis_name: int, ...}   # >= 3 entries
    }

Issues: #1468, #1264, #1234
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

# Same field-level thresholds enforced by unified_session_tracker /
# plan_mode_exit_detector when validating the verdict file (Issue #1264).
MIN_REASONING_CHARS = 100
MIN_AXIS_SCORES = 3
VALID_VERDICTS = frozenset({"PROCEED", "REVISE", "BLOCKED"})
DEFAULT_VERDICT_PATH = Path(".claude/plan_critic_verdict.json")

# Verdict/composite/reasoning/axis-score line patterns emitted by
# plan-critic in its structured chat output.  The verdict line itself is
# tolerant of the two documented header shapes
# (``## Verdict: PROCEED`` and a table-cell bold ``**PROCEED**``).
_VERDICT_LINE = re.compile(
    r"(?:^|\n)\s*(?:##\s*Verdict\s*:\s*|Verdict\s*:\s*|\*\*)"
    r"(PROCEED|REVISE|BLOCKED)"
    r"(?:\*\*)?",
    re.IGNORECASE,
)
_COMPOSITE_LINE = re.compile(
    # Matches the three documented shapes:
    #   Composite: 3.4
    #   COMPOSITE_SCORE = 3.4
    #   | **Composite** | **3.33** | |
    # The `\*` characters are optional bold markers on either side of
    # both the label and the number.
    r"\*{0,2}Composite(?:_SCORE)?\*{0,2}\s*[:=|\|]+\s*\*{0,2}"
    r"([0-9]+(?:\.[0-9]+)?)\*{0,2}",
    re.IGNORECASE,
)
# Axis-scores table row: | Axis Name | N | notes |
_AXIS_TABLE_ROW = re.compile(
    r"^\|\s*([A-Za-z][A-Za-z0-9 _\-/]*?)\s*\|\s*(?:\*\*)?"
    r"([1-5])(?:\*\*)?\s*\|",
    re.MULTILINE,
)


class PlanCriticVerdictError(ValueError):
    """Raised when a verdict payload cannot be persisted safely."""


@dataclass(frozen=True)
class PlanCriticVerdict:
    """Structured plan-critic verdict ready to be written to disk."""

    verdict: str
    composite_score: float
    reasoning: str
    axis_scores: Mapping[str, int]
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        """Return the on-disk JSON shape."""
        ts = self.timestamp or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S+00:00"
        )
        return {
            "verdict": self.verdict,
            "composite_score": float(self.composite_score),
            "timestamp": ts,
            "reasoning": self.reasoning,
            "axis_scores": dict(self.axis_scores),
        }


def _validate(payload: dict) -> None:
    """Enforce the same field-level rules the hook-side validator uses."""
    verdict = payload.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise PlanCriticVerdictError(
            f"verdict must be one of {sorted(VALID_VERDICTS)}, got {verdict!r}"
        )

    composite = payload.get("composite_score")
    if not isinstance(composite, (int, float)):
        raise PlanCriticVerdictError(
            f"composite_score must be numeric, got {type(composite).__name__}"
        )

    reasoning = payload.get("reasoning")
    if not isinstance(reasoning, str) or len(reasoning) < MIN_REASONING_CHARS:
        raise PlanCriticVerdictError(
            f"reasoning must be a string of >= {MIN_REASONING_CHARS} chars "
            f"(Issue #1264); got {len(reasoning) if isinstance(reasoning, str) else 0}"
        )

    axis_scores = payload.get("axis_scores")
    if not isinstance(axis_scores, dict) or len(axis_scores) < MIN_AXIS_SCORES:
        raise PlanCriticVerdictError(
            f"axis_scores must be a dict with >= {MIN_AXIS_SCORES} entries "
            f"(Issue #1264)"
        )
    for axis, score in axis_scores.items():
        if not isinstance(axis, str) or not axis.strip():
            raise PlanCriticVerdictError(f"axis name must be non-empty string, got {axis!r}")
        if not isinstance(score, (int, float)) or not (1 <= score <= 5):
            raise PlanCriticVerdictError(
                f"axis score for {axis!r} must be numeric 1-5, got {score!r}"
            )

    ts = payload.get("timestamp")
    if not isinstance(ts, str) or not ts.strip():
        raise PlanCriticVerdictError("timestamp must be non-empty ISO8601 string")


def write_verdict(
    verdict: PlanCriticVerdict,
    *,
    path: Optional[Path] = None,
) -> Path:
    """Persist ``verdict`` to ``path`` (default ``.claude/plan_critic_verdict.json``).

    Called by the coordinator (which owns ``Write`` capability) AFTER
    plan-critic returns its structured chat output — replacing the
    pre-#1468 pattern of the agent shelling out to a Python heredoc.

    Args:
        verdict: Fully-formed :class:`PlanCriticVerdict`.
        path:    Optional override.  Defaults to the canonical HARD GATE
                 location.  If relative, resolved against the current
                 working directory (the coordinator always runs at the
                 repo root).

    Returns:
        The absolute ``Path`` to the file that was written.

    Raises:
        PlanCriticVerdictError: If the payload fails
            hook-side-equivalent validation.  The file is NOT written on
            validation failure.
    """
    target = path or DEFAULT_VERDICT_PATH
    payload = verdict.to_dict()
    _validate(payload)

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically — sibling temp file + rename — so a partial write
    # cannot leave a malformed JSON on disk for the hook to reject.
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(target)
    return target.resolve()


def parse_verdict_from_output(
    output: str,
    *,
    fallback_reasoning: Optional[str] = None,
) -> Optional[PlanCriticVerdict]:
    """Extract a structured verdict from a plan-critic chat response.

    The critic's prompt requires it to emit (a) a verdict line, (b) a
    composite score, (c) a per-axis scores table, and (d) at least one
    paragraph of substantive critique (used as ``reasoning``).  This
    parser is deliberately lenient — the goal is to recover a
    persistable verdict from the agent's structured markdown, not to
    replace the axis scoring itself.

    Returns ``None`` when the output does not contain a recognisable
    verdict line.  When it does contain a verdict but is missing
    composite/axis/reasoning, the caller decides whether to raise
    (via ``write_verdict``'s validation) or to synthesize a
    BLOCKED verdict as a fallback.

    Args:
        output: The full chat body from plan-critic.
        fallback_reasoning: If the parsed body has < 100 chars of usable
            content, this string is substituted (allowing the coordinator
            to inject the raw response text as reasoning-of-record).

    Returns:
        :class:`PlanCriticVerdict` or ``None``.
    """
    if not isinstance(output, str) or not output.strip():
        return None

    verdict_match = _VERDICT_LINE.search(output)
    if not verdict_match:
        return None
    verdict = verdict_match.group(1).upper()

    composite_match = _COMPOSITE_LINE.search(output)
    if composite_match:
        try:
            composite = float(composite_match.group(1))
        except (TypeError, ValueError):
            composite = 0.0
    else:
        composite = 0.0

    axis_scores: dict[str, int] = {}
    for axis_match in _AXIS_TABLE_ROW.finditer(output):
        axis_name = axis_match.group(1).strip()
        # Ignore header/composite rows.
        if axis_name.lower() in {"axis", "composite", ""}:
            continue
        try:
            axis_scores[axis_name] = int(axis_match.group(2))
        except (TypeError, ValueError):
            continue

    # Reasoning = full output body (already substantive per prompt
    # contract).  Fallback lets caller inject their own if parsing fails.
    reasoning = output.strip()
    if len(reasoning) < MIN_REASONING_CHARS and fallback_reasoning:
        reasoning = fallback_reasoning

    return PlanCriticVerdict(
        verdict=verdict,
        composite_score=composite,
        reasoning=reasoning,
        axis_scores=axis_scores,
    )


def write_verdict_from_output(
    output: str,
    *,
    path: Optional[Path] = None,
    fallback_reasoning: Optional[str] = None,
) -> Optional[Path]:
    """Convenience: parse ``output`` and persist via :func:`write_verdict`.

    Returns the resolved ``Path`` on success, or ``None`` when no
    verdict line was found in the output (the coordinator should then
    treat that as a critic failure and retry).

    Raises :class:`PlanCriticVerdictError` when a verdict WAS parsed
    but the payload fails validation — the coordinator should BLOCK
    the pipeline in that case (matches the existing
    ``MISSING_VERDICT_FILE`` handling in `commands/implement.md`).
    """
    parsed = parse_verdict_from_output(output, fallback_reasoning=fallback_reasoning)
    if parsed is None:
        return None
    return write_verdict(parsed, path=path)

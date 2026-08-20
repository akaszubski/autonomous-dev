"""Tests for plan_critic_verdict.py (Issue #1468).

Validates the coordinator-side helper that persists plan-critic verdicts
to `.claude/plan_critic_verdict.json`, replacing the pre-#1468 pattern
of the agent shelling out to an inline Python heredoc.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from plan_critic_verdict import (  # noqa: E402
    MIN_AXIS_SCORES,
    MIN_REASONING_CHARS,
    PlanCriticVerdict,
    PlanCriticVerdictError,
    parse_verdict_from_output,
    write_verdict,
    write_verdict_from_output,
)


SUBSTANTIVE_REASONING = (
    "The plan is minimal but leaves one axis under-specified: the "
    "acceptance-test contract for the new sentinel guard does not "
    "cover the race where two heartbeat calls interleave. Add a "
    "regression test for that case before proceeding to implementation."
)
assert len(SUBSTANTIVE_REASONING) >= MIN_REASONING_CHARS


def _valid_verdict(**overrides) -> PlanCriticVerdict:
    base = dict(
        verdict="PROCEED",
        composite_score=3.4,
        reasoning=SUBSTANTIVE_REASONING,
        axis_scores={"Assumption Audit": 4, "Minimalism Pressure": 3, "Scope Creep Detection": 3},
    )
    base.update(overrides)
    return PlanCriticVerdict(**base)


class TestWriteVerdictHappyPath:
    def test_writes_file_with_all_required_fields(self, tmp_path):
        target = tmp_path / "verdict.json"
        result = write_verdict(_valid_verdict(), path=target)

        assert result == target.resolve()
        assert target.exists()

        data = json.loads(target.read_text())
        assert data["verdict"] == "PROCEED"
        assert data["composite_score"] == 3.4
        assert data["reasoning"] == SUBSTANTIVE_REASONING
        assert data["axis_scores"] == {
            "Assumption Audit": 4,
            "Minimalism Pressure": 3,
            "Scope Creep Detection": 3,
        }
        assert "timestamp" in data and data["timestamp"].endswith("+00:00")

    def test_writes_all_three_verdict_values(self, tmp_path):
        for v in ("PROCEED", "REVISE", "BLOCKED"):
            target = tmp_path / f"verdict_{v}.json"
            write_verdict(_valid_verdict(verdict=v), path=target)
            assert json.loads(target.read_text())["verdict"] == v

    def test_atomic_replace_no_partial_file(self, tmp_path):
        """Temp file is renamed into place — no `.tmp` residue on success."""
        target = tmp_path / "verdict.json"
        write_verdict(_valid_verdict(), path=target)
        residue = list(tmp_path.glob("*.tmp"))
        assert residue == [], f"expected no .tmp residue, found {residue}"

    def test_preserves_explicit_timestamp(self, tmp_path):
        target = tmp_path / "verdict.json"
        write_verdict(
            _valid_verdict(),
            path=target,
        )  # default timestamp
        # Now explicit
        target2 = tmp_path / "verdict2.json"
        pinned = "2026-08-09T12:00:00+00:00"
        write_verdict(
            PlanCriticVerdict(
                verdict="REVISE",
                composite_score=2.5,
                reasoning=SUBSTANTIVE_REASONING,
                axis_scores={"A": 2, "B": 3, "C": 2},
                timestamp=pinned,
            ),
            path=target2,
        )
        assert json.loads(target2.read_text())["timestamp"] == pinned


class TestWriteVerdictValidation:
    def test_rejects_unknown_verdict(self, tmp_path):
        with pytest.raises(PlanCriticVerdictError, match="verdict must be one of"):
            write_verdict(_valid_verdict(verdict="MAYBE"), path=tmp_path / "v.json")

    def test_rejects_short_reasoning(self, tmp_path):
        with pytest.raises(PlanCriticVerdictError, match="reasoning"):
            write_verdict(
                _valid_verdict(reasoning="too short"), path=tmp_path / "v.json"
            )

    def test_rejects_too_few_axes(self, tmp_path):
        with pytest.raises(PlanCriticVerdictError, match="axis_scores"):
            write_verdict(
                _valid_verdict(axis_scores={"only_one": 3}),
                path=tmp_path / "v.json",
            )

    def test_rejects_out_of_range_score(self, tmp_path):
        with pytest.raises(PlanCriticVerdictError, match="axis score"):
            write_verdict(
                _valid_verdict(axis_scores={"A": 6, "B": 3, "C": 3}),
                path=tmp_path / "v.json",
            )

    def test_no_file_written_on_validation_failure(self, tmp_path):
        target = tmp_path / "v.json"
        with pytest.raises(PlanCriticVerdictError):
            write_verdict(_valid_verdict(verdict="NOPE"), path=target)
        assert not target.exists(), "file must not be created on validation failure"


class TestParseVerdictFromOutput:
    def test_parses_header_form(self):
        output = f"""Some critique paragraphs go here.
{SUBSTANTIVE_REASONING}

## Verdict: PROCEED

### Scores
| Axis | Score | Notes |
|------|-------|-------|
| Assumption Audit | 4 | verified via grep |
| Minimalism Pressure | 3 | reasonable |
| Scope Creep Detection | 3 | ok |
| **Composite** | **3.33** | |
"""
        parsed = parse_verdict_from_output(output)
        assert parsed is not None
        assert parsed.verdict == "PROCEED"
        assert parsed.composite_score == pytest.approx(3.33)
        assert set(parsed.axis_scores) >= {
            "Assumption Audit",
            "Minimalism Pressure",
            "Scope Creep Detection",
        }
        assert parsed.axis_scores["Assumption Audit"] == 4

    def test_parses_axis_name_containing_ampersand(self):
        """Regression: the 7th axis is named 'Reachability & Enforceability'.

        The axis-name character class originally excluded ``&``, so the row
        matched nothing and the axis was dropped from ``axis_scores`` without
        any error. The hooks only require >= 3 numeric entries, so a 7-axis
        critique persisted 6 scores and every gate still reported success —
        an axis whose score cannot be recorded is an inert criterion. This
        test fails against the pre-fix regex.
        """
        output = f"""Critique paragraphs.
{SUBSTANTIVE_REASONING}

## Verdict: REVISE

### Scores
| Axis | Score | Notes |
|------|-------|-------|
| Assumption Audit | 4 | serena and grep agreed |
| Minimalism Pressure | 4 | irreducible |
| Operational Integration Test | 3 | kwargs asserted |
| Reachability & Enforceability | 2 | no firing margin stated |
| **Composite** | **3.25** | |
"""
        parsed = parse_verdict_from_output(output)
        assert parsed is not None
        assert "Reachability & Enforceability" in parsed.axis_scores, (
            f"axis names with '&' must survive parsing; got "
            f"{sorted(parsed.axis_scores)}"
        )
        assert parsed.axis_scores["Reachability & Enforceability"] == 2
        assert len(parsed.axis_scores) == 4, (
            f"every scored axis must be recovered, not a silent subset: "
            f"{parsed.axis_scores}"
        )

    def test_composite_row_still_excluded_with_widened_axis_class(self):
        """Negative control: widening the class must not admit the total row.

        The ampersand fix would be worthless if it also started recording
        '**Composite**' as an axis, so the guard is watched refusing that row
        as well as permitting the ampersand one.
        """
        output = f"""Critique paragraphs.
{SUBSTANTIVE_REASONING}

## Verdict: PROCEED

| Axis | Score | Notes |
|------|-------|-------|
| Reachability & Enforceability | 5 | fully specified |
| Minimalism Pressure | 4 | tight |
| Assumption Audit | 4 | verified |
| **Composite** | **4** | |
"""
        parsed = parse_verdict_from_output(output)
        assert parsed is not None
        lowered = {name.lower() for name in parsed.axis_scores}
        assert "composite" not in lowered
        assert "**composite**" not in lowered
        assert "axis" not in lowered

    def test_returns_none_when_no_verdict_line(self):
        output = "Just a bunch of chat with no verdict line at all."
        assert parse_verdict_from_output(output) is None

    def test_returns_none_on_empty(self):
        assert parse_verdict_from_output("") is None
        assert parse_verdict_from_output("   \n\n  ") is None

    def test_fallback_reasoning_used_when_body_too_short(self):
        output = "Verdict: BLOCKED\n\n| axis1 | 1 | bad |\n| axis2 | 1 | bad |\n| axis3 | 1 | bad |"
        parsed = parse_verdict_from_output(
            output, fallback_reasoning=SUBSTANTIVE_REASONING
        )
        assert parsed is not None
        assert parsed.reasoning == SUBSTANTIVE_REASONING


class TestWriteVerdictFromOutput:
    def test_end_to_end(self, tmp_path):
        target = tmp_path / "verdict.json"
        output = f"""Critique body paragraph one with substantive analysis.
{SUBSTANTIVE_REASONING}

## Verdict: REVISE

### Scores
| Axis | Score | Notes |
|------|-------|-------|
| Assumption Audit | 3 | ok |
| Minimalism Pressure | 2 | too many files |
| Scope Creep Detection | 3 | fine |
| **Composite** | **2.67** | |
"""
        result = write_verdict_from_output(output, path=target)
        assert result == target.resolve()
        data = json.loads(target.read_text())
        assert data["verdict"] == "REVISE"
        assert data["composite_score"] == pytest.approx(2.67)
        assert len(data["axis_scores"]) >= MIN_AXIS_SCORES

    def test_returns_none_when_no_verdict(self, tmp_path):
        target = tmp_path / "verdict.json"
        result = write_verdict_from_output("no verdict here", path=target)
        assert result is None
        assert not target.exists()

    def test_raises_when_verdict_parsed_but_invalid(self, tmp_path):
        """A parsed verdict that fails validation MUST raise, not silently succeed."""
        target = tmp_path / "verdict.json"
        # Only one axis parsed → fails MIN_AXIS_SCORES.
        output = "## Verdict: BLOCKED\n\n| Only One | 1 | broken |"
        with pytest.raises(PlanCriticVerdictError):
            write_verdict_from_output(
                output, path=target, fallback_reasoning=SUBSTANTIVE_REASONING
            )
        assert not target.exists()

"""Regression test for #1234 — coordinator must treat plan_critic_verdict.json as authoritative.

Issue: In spektiv pipeline run 20260617-083609, the plan-critic wrote
verdict=REVISE to plan_critic_verdict.json with composite_score=3.67. The
coordinator proceeded to implementation anyway, inferring an implicit PROCEED
from chat output. The JSON file (the machine-readable audit trail) was
ignored.

Fix C from the issue body: the coordinator's FORBIDDEN list MUST include a
rule that forbids inferring the verdict from chat output when the JSON file
exists. The Parse-verdict section MUST state the file is authoritative.

This test asserts both pieces of language are present in
plugins/autonomous-dev/commands/implement.md, so a future edit that removes
the guard regresses the same bug.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _implement_md_text() -> str:
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    path = repo_root / "plugins" / "autonomous-dev" / "commands" / "implement.md"
    assert path.exists(), f"Expected {path} to exist"
    return path.read_text(encoding="utf-8")


def test_step_5_5b_parse_verdict_section_marks_json_file_authoritative() -> None:
    """STEP 5.5b parse-verdict header must declare plan_critic_verdict.json authoritative."""
    text = _implement_md_text()
    # Header refers to the JSON file and the #1234 reference, signalling
    # this is the authoritative read path.
    assert "Parse verdict from `plan_critic_verdict.json`" in text, (
        "STEP 5.5b parse-verdict header must read from plan_critic_verdict.json "
        "(see #1234 — chat output is not authoritative)."
    )
    assert "do NOT infer from chat output" in text, (
        "STEP 5.5b must explicitly forbid inferring the verdict from chat output."
    )


def test_step_5_5b_blocks_when_verdict_file_missing() -> None:
    """When the JSON file is absent or malformed, the coordinator must BLOCK with MISSING_VERDICT_FILE."""
    text = _implement_md_text()
    assert "MISSING_VERDICT_FILE" in text, (
        "STEP 5.5b must specify the BLOCK reason when plan_critic_verdict.json "
        "is missing or malformed (instead of inferring PROCEED from chat)."
    )


def test_step_5_5d_forbidden_list_includes_json_authority_rule() -> None:
    """STEP 5.5d FORBIDDEN list must contain the bullet that forbids chat-based inference."""
    text = _implement_md_text()
    # Look for the exact rule signature without overfitting on whitespace.
    assert "infer the plan-critic verdict from chat output" in text, (
        "STEP 5.5d FORBIDDEN list is missing the rule that forbids inferring "
        "the plan-critic verdict from chat output when plan_critic_verdict.json exists. "
        "Regression of #1234."
    )
    assert "JSON file is authoritative" in text, (
        "STEP 5.5d FORBIDDEN bullet must declare the JSON file authoritative."
    )


def test_step_5_5d_rule_references_issue_1234() -> None:
    """The new FORBIDDEN bullet must reference #1234 so future readers can find context."""
    text = _implement_md_text()
    # Find the line containing the rule and verify #1234 appears nearby.
    rule_marker = "infer the plan-critic verdict from chat output"
    idx = text.find(rule_marker)
    assert idx != -1, "rule marker not found (handled by earlier test, but defensive)"
    # The bullet is one paragraph long — #1234 should appear within ~400 chars.
    bullet_window = text[idx : idx + 400]
    assert "#1234" in bullet_window, (
        "The chat-inference FORBIDDEN bullet must reference #1234 in its inline citation "
        "so future maintainers can trace context."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

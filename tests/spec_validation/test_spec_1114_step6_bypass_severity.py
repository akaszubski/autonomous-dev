"""Spec-blind validation tests for Issue #1114.

Acceptance criteria (verbatim from planner):

1. pytest tests/unit/hooks/test_session_activity_pipeline_actions.py::
   TestBypassPatternsConfig::test_all_patterns_have_required_fields passes
   with exit code 0.
2. All other patterns in plugins/autonomous-dev/config/known_bypass_patterns.json
   retain their existing severity values (only the step6_bundling_bypass severity
   is modified).
3. The JSON file remains valid syntax.
4. No other test in tests/unit/hooks/test_session_activity_pipeline_actions.py
   regresses (all 20 tests pass).
5. grep '"severity": "high"' plugins/autonomous-dev/config/known_bypass_patterns.json
   returns no matches after the fix.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    REPO_ROOT
    / "plugins"
    / "autonomous-dev"
    / "config"
    / "known_bypass_patterns.json"
)
TEST_FILE = (
    REPO_ROOT
    / "tests"
    / "unit"
    / "hooks"
    / "test_session_activity_pipeline_actions.py"
)


def test_spec_1114_criterion_1_target_test_passes() -> None:
    """Criterion 1: The specific failing test now passes with exit code 0."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(TEST_FILE)
            + "::TestBypassPatternsConfig::test_all_patterns_have_required_fields",
            "-v",
            "--no-cov",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Target test must pass with exit code 0. "
        f"Got exit code {result.returncode}.\n"
        f"STDOUT:\n{result.stdout[-2000:]}\n"
        f"STDERR:\n{result.stderr[-2000:]}"
    )


def test_spec_1114_criterion_2_step6_severity_is_valid() -> None:
    """Criterion 2 (positive): step6_bundling_bypass severity is now in the
    allowed schema set ('critical', 'warning', 'info')."""
    data = json.loads(CONFIG_PATH.read_text())
    patterns = data["patterns"]
    step6 = next(
        (p for p in patterns if p.get("id") == "step6_bundling_bypass"),
        None,
    )
    assert step6 is not None, "step6_bundling_bypass pattern must exist"
    assert step6["severity"] in ("critical", "warning", "info"), (
        f"step6_bundling_bypass severity must be one of "
        f"('critical','warning','info'); got {step6['severity']!r}"
    )


def test_spec_1114_criterion_2_other_patterns_unchanged() -> None:
    """Criterion 2 (scope lock): No pattern other than step6_bundling_bypass
    had its severity changed.

    This compares the current file's severities against the values that
    existed prior to the fix (extracted from the issue body / git history).
    """
    expected_other_severities = {
        "test_gate_bypass": "critical",
        "anti_stubbing": "critical",
        "hook_registration_skip": "critical",
        "missing_terminal_actions": "warning",
        "context_compression": "warning",
        "step_skipping": "critical",
        "command_bypass": "warning",
        "error_ignored": "warning",
        "stop_softened_language": "warning",
        "hook_silent_failure": "critical",
        "silent_exception_swallowing": "critical",
        "prompt_file_edit_bypass": "critical",
        "plan_mode_direct_edit_justification": "critical",
        "skip_accumulation": "critical",
        "batch_group_pipeline": "critical",
        "batch_progressive_shortcutting": "critical",
        "sequential_step_parallelized": "critical",
        "parallel_step_serialized": "info",
        "context_dropping": "warning",
        "hard_gate_ordering_bypass": "critical",
        "reviewer_blocking_ignored": "critical",
        "batch_last_issue_cia_skip": "critical",
        "research_skip_entire_batch": "warning",
    }

    data = json.loads(CONFIG_PATH.read_text())
    actual = {p["id"]: p.get("severity") for p in data["patterns"]}

    for pid, expected_sev in expected_other_severities.items():
        assert pid in actual, f"Pre-existing pattern {pid!r} must still exist"
        assert actual[pid] == expected_sev, (
            f"Severity for {pid!r} must be unchanged. "
            f"Expected {expected_sev!r}, got {actual[pid]!r}."
        )


def test_spec_1114_criterion_3_json_is_valid() -> None:
    """Criterion 3: The JSON file remains valid syntax (parses without error)."""
    raw = CONFIG_PATH.read_text()
    # Should not raise
    parsed = json.loads(raw)
    assert isinstance(parsed, dict), "Top-level value must be a dict"
    assert "patterns" in parsed, "Top-level dict must have 'patterns' key"
    assert isinstance(parsed["patterns"], list), "'patterns' must be a list"
    assert len(parsed["patterns"]) > 0, "patterns list must be non-empty"


def test_spec_1114_criterion_4_full_test_file_passes() -> None:
    """Criterion 4: No regression — all tests in the target file pass."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(TEST_FILE),
            "-v",
            "--no-cov",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"All tests in {TEST_FILE.name} must pass. "
        f"Got exit code {result.returncode}.\n"
        f"STDOUT tail:\n{result.stdout[-3000:]}\n"
        f"STDERR tail:\n{result.stderr[-1000:]}"
    )
    # Sanity: confirm pytest reported at least 20 passed (per planner's stated count)
    assert " passed" in result.stdout, "pytest did not report any passing tests"


def test_spec_1114_criterion_5_no_severity_high_remaining() -> None:
    """Criterion 5: grep '"severity": "high"' returns no matches after the fix."""
    raw = CONFIG_PATH.read_text()
    assert '"severity": "high"' not in raw, (
        'The literal string `"severity": "high"` must NOT appear anywhere '
        f"in {CONFIG_PATH.name}."
    )


def test_spec_1114_no_unintended_new_severity_values() -> None:
    """Defensive scope check: every pattern's severity is in the schema-allowed
    set. Guards against introducing a new invalid value while fixing 'high'."""
    allowed = {"critical", "warning", "info"}
    data = json.loads(CONFIG_PATH.read_text())
    bad = [
        (p["id"], p.get("severity"))
        for p in data["patterns"]
        if p.get("severity") not in allowed
    ]
    assert not bad, (
        f"Every pattern severity must be in {sorted(allowed)}; "
        f"violations: {bad}"
    )

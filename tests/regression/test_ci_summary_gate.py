"""Regression tests for the CI Summary gate in ``.github/workflows/ci.yml``.

Issue #1333: The CI Summary step previously gated on ``= "failure"`` for
``SMOKE_RESULT`` and ``TEST_RESULT``. When a GitHub Actions job is
*cancelled*, *timed_out*, or otherwise non-success, ``needs.<job>.result``
is NOT the literal string ``"failure"`` — so the gate treated those
outcomes as PASS and allowed merges where the full test suite never
actually ran to completion.

The fix flips the gate to a positive assertion: only ``"success"`` (or
``"skipped"`` for the optional full test suite) is allowed through.

These tests:
1. Parse the live workflow YAML (no hardcoded snippet copies) and extract
   the shell body of the CI Summary check step.
2. Execute the snippet under ``bash -c`` with synthetic
   ``SMOKE_RESULT`` / ``TEST_RESULT`` env vars and assert the exit code
   matches the gate's documented contract for all eight relevant
   combinations of GitHub Actions job result strings.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YAML_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _extract_summary_run_snippet() -> str:
    """Parse the live workflow file and return the ``run:`` body of the
    CI Summary step.

    Returns:
        The literal bash snippet executed by the ``CI Summary`` job's
        single step.

    Raises:
        AssertionError: If the workflow does not contain a ``summary``
            job with a check step that has a ``run:`` body.
    """
    workflow = yaml.safe_load(CI_YAML_PATH.read_text())
    jobs = workflow.get("jobs", {})
    summary_job = jobs.get("summary")
    assert summary_job is not None, (
        f"Expected ci.yml to define a 'summary' job (Issue #1333).\n"
        f"Found jobs: {sorted(jobs.keys())}"
    )

    steps = summary_job.get("steps", [])
    assert steps, "summary job must define at least one step"

    # The check step is the one with a ``run:`` body (vs. ``uses:``).
    run_steps = [s for s in steps if "run" in s]
    assert run_steps, (
        "summary job must contain a step with a 'run:' body that gates "
        "the merge."
    )
    # Use the LAST run step in case future maintenance adds prep steps.
    snippet = run_steps[-1]["run"]
    assert isinstance(snippet, str) and snippet.strip(), (
        "summary job's run: body must be a non-empty string"
    )
    return snippet


@pytest.fixture(scope="module")
def summary_snippet() -> str:
    """Module-scoped fixture: parse the live workflow once."""
    return _extract_summary_run_snippet()


# Fixtures: (SMOKE_RESULT, TEST_RESULT, expected_exit)
#
# GitHub Actions ``needs.<job>.result`` is one of:
# success | failure | cancelled | skipped
# (timed_out is NOT a needs-context result value — actual timeouts surface
#  as ``cancelled``. The ``timed_out`` fixture below is a defense-in-depth
#  case: any unrecognized status string must block the gate.)
GATE_FIXTURES = [
    # SMOKE success + TEST passes the gate
    ("success", "success", 0),
    ("success", "skipped", 0),
    # SMOKE success + TEST non-success values must block
    ("success", "cancelled", 1),
    ("success", "failure", 1),
    ("success", "timed_out", 1),
    ("success", "", 1),
    # SMOKE non-success must always block, regardless of TEST
    ("failure", "success", 1),
    ("cancelled", "success", 1),
]


@pytest.mark.parametrize(("smoke_result", "test_result", "expected_exit"), GATE_FIXTURES)
def test_ci_summary_gate_exit_codes(
    summary_snippet: str,
    smoke_result: str,
    test_result: str,
    expected_exit: int,
) -> None:
    """The CI Summary snippet must exit 0 only when both inputs are PASS.

    Args:
        summary_snippet: Bash body parsed from the live workflow file.
        smoke_result: Simulated ``needs.smoke.result``.
        test_result: Simulated ``needs.test.result``.
        expected_exit: Required exit code from running the snippet under
            ``bash -c``.

    Issue #1333: This test would FAIL if the snippet were reverted to
    ``= "failure"`` because the ``cancelled``/``timed_out``/empty cases
    for TEST_RESULT would then exit 0 instead of 1.
    """
    env = {
        "SMOKE_RESULT": smoke_result,
        "TEST_RESULT": test_result,
        # Preserve PATH so /bin/bash and friends resolve under the test
        # process; do not leak the rest of the parent env so the snippet
        # cannot accidentally read unrelated CI variables.
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }

    completed = subprocess.run(
        ["bash", "-c", summary_snippet],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == expected_exit, (
        f"CI Summary gate exit-code mismatch for "
        f"SMOKE_RESULT={smoke_result!r}, TEST_RESULT={test_result!r}.\n"
        f"  expected exit: {expected_exit}\n"
        f"  actual exit:   {completed.returncode}\n"
        f"  stdout: {completed.stdout!r}\n"
        f"  stderr: {completed.stderr!r}\n"
        f"Snippet under test:\n{summary_snippet}"
    )

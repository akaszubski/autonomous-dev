"""Regression tests for CI test-routing and parallelization in ``.github/workflows/ci.yml``.

Issue #1332: The Full Test Suite job was hitting the 60-min job timeout.
The fix introduces two structural changes to the ``test`` job:

1. A ``Route tests`` pre-step (``id: route``) that calls
   ``test_routing.route_tests()`` from ``plugins/autonomous-dev/lib`` and
   exposes a ``skip_all`` output. When ``skip_all == 'true'``, the
   downstream install + pytest steps are short-circuited via step-level
   ``if:`` guards — so doc-only changes do not consume the full 60-min
   budget.
2. Parallel test execution via ``pytest-xdist`` (``-n auto``) on the
   unit, integration, and regression pytest steps. This is the
   wall-clock fix that brings the long tail under the timeout.

These tests parse the live workflow YAML (no hardcoded snippet copies,
per ``test_ci_summary_gate.py`` style) and assert:

  AC1. The ``test`` job has a step with ``id: route``.
  AC2. The ``test`` job's install step contains ``pytest-xdist`` in its
       ``run`` body.
  AC3. The ``test`` job has at least 3 pytest steps (unit/integration/
       regression), each containing ``-n auto`` in its ``run`` body.
  AC4. The 3 pytest steps AND the install step are all guarded by
       ``if: steps.route.outputs.skip_all != 'true'``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YAML_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# The exact guard string the ``test`` job's gated steps must use.
EXPECTED_IF_GUARD = "steps.route.outputs.skip_all != 'true'"


def _load_test_job() -> dict[str, Any]:
    """Parse the live workflow YAML and return the ``jobs.test`` mapping.

    Returns:
        The ``test`` job dict from ``.github/workflows/ci.yml``.

    Raises:
        AssertionError: If the workflow does not define a ``test`` job
            with a ``steps`` list.
    """
    workflow = yaml.safe_load(CI_YAML_PATH.read_text())
    jobs = workflow.get("jobs", {})
    test_job = jobs.get("test")
    assert test_job is not None, (
        f"Expected ci.yml to define a 'test' job (Issue #1332).\n"
        f"Found jobs: {sorted(jobs.keys())}"
    )
    steps = test_job.get("steps")
    assert isinstance(steps, list) and steps, (
        "test job must define a non-empty steps list"
    )
    return test_job


@pytest.fixture(scope="module")
def test_job() -> dict[str, Any]:
    """Module-scoped fixture: parse the live workflow once."""
    return _load_test_job()


@pytest.fixture(scope="module")
def test_steps(test_job: dict[str, Any]) -> list[dict[str, Any]]:
    """Module-scoped fixture: the test job's steps list."""
    return test_job["steps"]


def _find_step_by_id(steps: list[dict[str, Any]], step_id: str) -> dict[str, Any] | None:
    """Return the first step matching ``id: <step_id>``, or None."""
    for step in steps:
        if step.get("id") == step_id:
            return step
    return None


def _find_step_by_name(steps: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """Return the first step matching ``name: <name>``, or None."""
    for step in steps:
        if step.get("name") == name:
            return step
    return None


def _pytest_run_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return steps whose ``run`` body invokes ``python -m pytest tests/<tier>/``.

    Filters to the three full-suite pytest steps (unit/integration/
    regression) — the routing-aware pre-flight and other helper steps
    do not match.
    """
    out = []
    for step in steps:
        run = step.get("run")
        if not isinstance(run, str):
            continue
        if "python -m pytest tests/" not in run:
            continue
        out.append(step)
    return out


# ---------------------------------------------------------------------------
# AC1: Route tests step with id: route
# ---------------------------------------------------------------------------
def test_test_job_has_route_step_with_id(test_steps: list[dict[str, Any]]) -> None:
    """The ``test`` job must contain a step with ``id: route`` (Issue #1332).

    This is the routing pre-step that calls
    ``test_routing.route_tests()`` and exposes ``skip_all`` for the
    downstream ``if:`` guards.
    """
    route_step = _find_step_by_id(test_steps, "route")
    assert route_step is not None, (
        "test job is missing the 'Route tests' pre-step "
        f"(id: route). Steps present: "
        f"{[s.get('name') or s.get('id') for s in test_steps]}"
    )
    # The step must actually invoke the routing library.
    run = route_step.get("run", "")
    assert "test_routing" in run, (
        f"Route tests step must import the test_routing module; "
        f"run body was:\n{run}"
    )
    assert "route_tests" in run, (
        f"Route tests step must call route_tests(); run body was:\n{run}"
    )
    # The step must emit skip_all to GITHUB_OUTPUT so downstream
    # if-guards can consume it.
    assert "skip_all=" in run, (
        f"Route tests step must emit skip_all=<bool> to GITHUB_OUTPUT; "
        f"run body was:\n{run}"
    )
    assert "GITHUB_OUTPUT" in run, (
        f"Route tests step must write to GITHUB_OUTPUT so steps.route.outputs "
        f"is populated; run body was:\n{run}"
    )
    # Issue #1337 FINDING-3: the route step MUST set continue-on-error: true
    # so that a routing-step failure (e.g., ImportError in test_routing) falls
    # through to the gated downstream steps instead of hard-failing the job.
    # Removing this property would silently convert a soft fall-through into
    # a hard failure for the whole test job.
    coe = route_step.get("continue-on-error")
    assert coe is True, (
        "Route tests step MUST set 'continue-on-error: true' so that a "
        "routing-step failure falls through to the gated downstream steps "
        "instead of hard-failing the test job (Issue #1337 FINDING-3). "
        f"Got continue-on-error={coe!r}."
    )
    # Issue #1337 FINDING-1: Route tests output redirect must use /dev/stderr
    # (portable across all GHA runner contexts: container steps, composite
    # actions), not /dev/tty (which is not guaranteed to be connected).
    assert "/dev/tty" not in run, (
        f"Route tests step must not use /dev/tty (Issue #1337 FINDING-1); "
        f"use /dev/stderr instead.\nrun body was:\n{run}"
    )
    assert "/dev/stderr" in run, (
        f"Route tests step must redirect via /dev/stderr for portability "
        f"(Issue #1337 FINDING-1);\nrun body was:\n{run}"
    )


# ---------------------------------------------------------------------------
# AC2: Install step contains pytest-xdist
# ---------------------------------------------------------------------------
def test_install_step_includes_pytest_xdist(test_steps: list[dict[str, Any]]) -> None:
    """The test job's install step must install ``pytest-xdist`` (Issue #1332).

    pytest-xdist provides ``-n auto`` parallel execution — the wall-clock
    fix for the 60-min timeout.
    """
    install_step = _find_step_by_name(test_steps, "Install dependencies")
    assert install_step is not None, (
        "test job is missing the 'Install dependencies' step.\n"
        f"Steps present: {[s.get('name') for s in test_steps]}"
    )
    run = install_step.get("run", "")
    assert "pytest-xdist" in run, (
        f"Install dependencies step must install pytest-xdist for "
        f"parallel test execution (-n auto). run body was:\n{run}"
    )


# ---------------------------------------------------------------------------
# AC3: At least 3 pytest steps, each with -n auto
# ---------------------------------------------------------------------------
def test_test_job_has_at_least_three_pytest_steps(test_steps: list[dict[str, Any]]) -> None:
    """The test job must have at least 3 pytest steps for the full suite tiers."""
    pytest_steps = _pytest_run_steps(test_steps)
    assert len(pytest_steps) >= 3, (
        f"test job must have at least 3 pytest steps "
        f"(unit / integration / regression). Found {len(pytest_steps)}: "
        f"{[s.get('name') for s in pytest_steps]}"
    )


@pytest.mark.parametrize(
    "step_name",
    ["Run unit tests", "Run integration tests", "Run regression tests"],
)
def test_pytest_step_uses_xdist_parallel(
    test_steps: list[dict[str, Any]], step_name: str
) -> None:
    """Each unit/integration/regression pytest step must use ``-n auto`` (Issue #1332).

    Args:
        test_steps: The test job's steps list (from fixture).
        step_name: One of the three required pytest step names.
    """
    step = _find_step_by_name(test_steps, step_name)
    assert step is not None, (
        f"test job is missing the {step_name!r} step.\n"
        f"Steps present: {[s.get('name') for s in test_steps]}"
    )
    run = step.get("run", "")
    assert "-n auto" in run, (
        f"{step_name!r} step must use '-n auto' for pytest-xdist "
        f"parallel execution. run body was:\n{run}"
    )


# ---------------------------------------------------------------------------
# AC4: The 3 pytest steps + Install step are guarded by skip_all check
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "step_name",
    [
        "Install dependencies",
        "Run unit tests",
        "Run integration tests",
        "Run regression tests",
    ],
)
def test_step_is_guarded_by_skip_all_check(
    test_steps: list[dict[str, Any]], step_name: str
) -> None:
    """Each of the 3 pytest steps + the install step must be guarded by
    ``if: steps.route.outputs.skip_all != 'true'`` (Issue #1332).

    Without these guards, the routing decision has no teeth — the steps
    run regardless of the route outcome.

    Args:
        test_steps: The test job's steps list (from fixture).
        step_name: Name of a step that MUST be guarded.
    """
    step = _find_step_by_name(test_steps, step_name)
    assert step is not None, (
        f"test job is missing the {step_name!r} step.\n"
        f"Steps present: {[s.get('name') for s in test_steps]}"
    )
    if_value = step.get("if")
    assert if_value is not None, (
        f"{step_name!r} step is missing an 'if:' guard. Expected: "
        f"if: {EXPECTED_IF_GUARD}"
    )
    assert EXPECTED_IF_GUARD in str(if_value), (
        f"{step_name!r} step has an unexpected 'if:' guard.\n"
        f"  expected to contain: {EXPECTED_IF_GUARD}\n"
        f"  actual:              {if_value!r}"
    )


# ---------------------------------------------------------------------------
# AC2: Marker emission has documenting comment (Issue #1337)
# ---------------------------------------------------------------------------
def test_marker_emission_documented_in_workflow() -> None:
    """The ci.yml workflow must contain a comment documenting why ``marker``
    is emitted to ``$GITHUB_OUTPUT`` despite having no downstream consumer
    (Issue #1337).

    Rationale: ``pytest -m "$marker"`` wiring is deferred per #1332. Without
    a comment, future readers may delete the marker emission as dead code.
    """
    text = CI_YAML_PATH.read_text()
    assert "#1332" in text and "#1337" in text and "marker" in text.lower(), (
        "ci.yml must contain a comment referencing #1332 and #1337 that "
        "documents why the marker= emission is intentional (Issue #1337). "
        "Expected a YAML comment like: "
        "'# marker= emitted for future use; pytest -m wiring deferred per #1332 (see #1337).'"
    )

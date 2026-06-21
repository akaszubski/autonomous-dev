"""Smoke tests verifying drain workflows route through /drain-queue.

ADR-002 Phase B — Invariant 2: workflows must invoke /drain-queue, not
/implement --light directly.

Issue #1274.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DRAIN_DRIVER = REPO_ROOT / ".github" / "workflows" / "drain-driver.yml"
DRAIN_WATCHDOG = REPO_ROOT / ".github" / "workflows" / "drain-watchdog.yml"


def test_no_implement_light_in_drain_workflows() -> None:
    """Assert neither drain workflow contains '/implement --light'.

    ADR-002 Phase B: direct /implement invocations are forbidden in drain
    workflow prompts — all drain logic must route through /drain-queue.
    """
    for wf_path in (DRAIN_DRIVER, DRAIN_WATCHDOG):
        assert wf_path.exists(), f"Workflow file not found: {wf_path}"
        content = wf_path.read_text()
        offending_lines = [
            f"  line {i + 1}: {line.rstrip()}"
            for i, line in enumerate(content.splitlines())
            if "/implement --light" in line
        ]
        assert not offending_lines, (
            f"Found '/implement --light' in {wf_path.name}:\n"
            + "\n".join(offending_lines)
        )


def test_drain_driver_direct_prompt_invokes_drain_queue() -> None:
    """Assert drain-driver.yml direct_prompt contains '/drain-queue'.

    ADR-002 Phase B: the drain-driver's claude-code-action prompt must
    instruct the session to invoke /drain-queue, not /implement directly.
    """
    assert DRAIN_DRIVER.exists(), f"Workflow file not found: {DRAIN_DRIVER}"
    doc = yaml.safe_load(DRAIN_DRIVER.read_text())

    drain_steps = doc["jobs"]["drain"]["steps"]
    action_step = next(
        (s for s in drain_steps if s.get("uses", "").startswith("anthropics/claude-code-action")),
        None,
    )
    assert action_step is not None, (
        "No anthropics/claude-code-action step found in jobs.drain.steps of drain-driver.yml"
    )

    direct_prompt: str = action_step.get("with", {}).get("direct_prompt", "")
    assert "/drain-queue" in direct_prompt, (
        f"direct_prompt in drain-driver.yml jobs.drain does not contain '/drain-queue'.\n"
        f"Prompt excerpt: {direct_prompt[:500]!r}"
    )


def test_drain_watchdog_direct_prompt_invokes_drain_queue() -> None:
    """Assert drain-watchdog.yml direct_prompt contains '/drain-queue'.

    ADR-002 Phase B: the watchdog's heal prompt must instruct the session
    to invoke /drain-queue, not /implement directly.
    """
    assert DRAIN_WATCHDOG.exists(), f"Workflow file not found: {DRAIN_WATCHDOG}"
    doc = yaml.safe_load(DRAIN_WATCHDOG.read_text())

    heal_steps = doc["jobs"]["heal"]["steps"]
    action_step = next(
        (s for s in heal_steps if s.get("uses", "").startswith("anthropics/claude-code-action")),
        None,
    )
    assert action_step is not None, (
        "No anthropics/claude-code-action step found in jobs.heal.steps of drain-watchdog.yml"
    )

    direct_prompt: str = action_step.get("with", {}).get("direct_prompt", "")
    assert "/drain-queue" in direct_prompt, (
        f"direct_prompt in drain-watchdog.yml jobs.heal does not contain '/drain-queue'.\n"
        f"Prompt excerpt: {direct_prompt[:500]!r}"
    )

"""Regression: no GitHub Actions ${{ }} interpolation in workflow run: blocks.

Issue #1287 — direct ${{ ... }} interpolation in shell `run:` blocks is a
shell injection vector per GitHub's "Secure use of GitHub Actions" guidance.
The safe pattern is env: block + double-quoted "$VAR" shell reference; the
runner sets env vars with proper escaping so the shell sees ordinary
variables that cannot break out of their string context.

Scope: narrowed to workflows already migrated under #1287/#1307/#1308
(drain-driver.yml, drain-watchdog.yml, ci.yml, safety-net.yml). Other
workflows have known remaining interpolations tracked as follow-up
issues:
  - auto-tag-on-push.yml:53, 76, 77

Once those follow-ups land, widen the SCOPED_WORKFLOWS list to a glob
over all of .github/workflows/*.yml.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
EXPR_PATTERN = re.compile(r"\$\{\{")

SCOPED_WORKFLOWS = [
    WORKFLOWS_DIR / "drain-driver.yml",
    WORKFLOWS_DIR / "drain-watchdog.yml",
    WORKFLOWS_DIR / "ci.yml",
    WORKFLOWS_DIR / "safety-net.yml",
]

# Documented exclusions: interpolations intentionally left in scope but tracked
# as follow-up issues for separate migration. Each entry is (workflow_name,
# substring-on-the-run-line) — if the offending line contains this substring,
# it is allowed. KEEP THIS LIST SHORT — every entry is technical debt.
ALLOWED_EXCLUSIONS: set = set()


def _iter_run_blocks(workflow_path: Path):
    """Yield (job_name, step_index, step_name, run_source) for every step
    that declares a `run:` block in this workflow.

    `concurrency.group`, job-level `if:`, `with:` parameters, and the
    `env:` block itself are all consumed by the GitHub Actions engine,
    not by a shell, so they are NOT yielded here.
    """
    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    jobs = data.get("jobs") or {}
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for idx, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                continue
            run_src = step.get("run")
            if isinstance(run_src, str):
                yield job_name, idx, step.get("name", f"<step {idx}>"), run_src


@pytest.mark.parametrize("workflow_path", SCOPED_WORKFLOWS, ids=lambda p: p.name)
def test_no_expression_interpolation_in_run_blocks(workflow_path: Path) -> None:
    """Every `run:` block in the scoped workflow must use env: indirection.

    Direct `${{ <expr> }}` interpolation in a shell `run:` block pastes the
    expression's value verbatim into the script source BEFORE the shell
    parses it. Attacker-controllable values (workflow_dispatch inputs,
    issue titles, branch names) become shell injection vectors.

    Canonical fix: declare the expression as a step `env:` var, then
    reference it as "$VAR" in the run: block.

    See:
      - https://docs.github.com/en/actions/reference/security/secure-use
      - .github/workflows/auto-tag-on-push.yml lines 63-70 (safe pattern)
    """
    offenders = []
    for job_name, _, step_name, run_src in _iter_run_blocks(workflow_path):
        for lineno, line in enumerate(run_src.splitlines(), start=1):
            if not EXPR_PATTERN.search(line):
                continue
            # Skip documented exclusions tracked as follow-up issues.
            if any(
                wf == workflow_path.name and marker in line
                for wf, marker in ALLOWED_EXCLUSIONS
            ):
                continue
            offenders.append(
                f"  {workflow_path.name}: job={job_name} "
                f"step={step_name!r} run-line={lineno}: {line.strip()}"
            )
    assert not offenders, (
        f"Found ${{{{ ... }}}} interpolation in run: block(s) of "
        f"{workflow_path.name} (Issue #1287) — use env: block + \"$VAR\":\n"
        + "\n".join(offenders)
    )


def test_drain_driver_has_cluster_override_env_entry() -> None:
    """Positive control: confirms the #1287 drain-driver fix is in place.

    Asserts both halves of the env-block migration: (a) the env: declaration
    binding the workflow_dispatch input to CLUSTER_OVERRIDE, and (b) the
    shell reference `"$CLUSTER_OVERRIDE"`. If either half is reverted
    without going through this test, fails loudly.
    """
    content = (WORKFLOWS_DIR / "drain-driver.yml").read_text(encoding="utf-8")
    assert "CLUSTER_OVERRIDE: ${{ github.event.inputs.cluster_override }}" in content, (
        "drain-driver.yml must declare CLUSTER_OVERRIDE in env: block (Issue #1287)"
    )
    assert '"$CLUSTER_OVERRIDE"' in content, (
        'drain-driver.yml must reference "$CLUSTER_OVERRIDE" in run: block (Issue #1287)'
    )

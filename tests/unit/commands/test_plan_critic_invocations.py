"""Regression guard for plan-critic model-tier specification at call sites.

Issue #1128 documented a (since-discovered-to-be-non-existent) plan-critic call
in commands/create-issue.md missing model="opus". Investigation found the
described call site does not exist, but the issue's spirit — preventing silent
model-tier regression at plan-critic invocations — is delivered by these tests.

Three call sites exist as of writing:
- commands/plan.md:48  → model="opus" (iterative critique loop)
- commands/plan.md:88  → model="opus" (iterative critique loop)
- commands/implement.md:637 → model="sonnet" (constrained-budget fast-path)

The sonnet call in implement.md is intentional and documented. This test suite
asserts both invariants:
1. Every plan-critic invocation in plan.md uses model="opus".
2. The implement.md constrained-budget call continues to use model="sonnet"
   (protects the intentional downgrade from accidental promotion).
"""
import re
from pathlib import Path

COMMANDS_DIR = (
    Path(__file__).parents[3] / "plugins" / "autonomous-dev" / "commands"
)

_PLAN_CRITIC_CALL_RE = re.compile(
    r'\*?\*?Agent\*?\*?\(subagent_type="plan-critic"[^)]*\)',
    re.MULTILINE,
)


def _read_command(name: str) -> str:
    return (COMMANDS_DIR / name).read_text()


def test_plan_md_plan_critic_calls_all_use_opus() -> None:
    """Every plan-critic invocation in plan.md must specify model="opus"."""
    content = _read_command("plan.md")
    matches = _PLAN_CRITIC_CALL_RE.findall(content)
    assert len(matches) >= 2, (
        f"Expected >=2 plan-critic invocations in plan.md, found {len(matches)}"
    )
    for match in matches:
        assert 'model="opus"' in match, (
            f"plan.md plan-critic call missing model=\"opus\": {match!r}"
        )


def test_plan_md_no_plan_critic_call_without_opus() -> None:
    """Line-level inverse: no plan-critic line in plan.md may omit model="opus"."""
    content = _read_command("plan.md")
    for lineno, line in enumerate(content.splitlines(), 1):
        if 'subagent_type="plan-critic"' in line:
            assert 'model="opus"' in line, (
                f"plan.md line {lineno}: plan-critic invocation lacks "
                f'model="opus": {line.strip()!r}'
            )


def test_implement_md_constrained_plan_critic_uses_sonnet() -> None:
    """implement.md's fast-path plan-critic call MUST stay model="sonnet".

    Protects the intentional constrained-budget downgrade from being
    accidentally promoted to opus, which would break the fast-path contract.
    """
    content = _read_command("implement.md")
    matches = _PLAN_CRITIC_CALL_RE.findall(content)
    assert len(matches) >= 1, (
        "Expected >=1 plan-critic invocation in implement.md"
    )
    constrained = [m for m in matches if 'model="sonnet"' in m]
    assert len(constrained) >= 1, (
        "implement.md plan-critic call should specify model=\"sonnet\" "
        f"(constrained-budget fast-path). Found: {matches}"
    )


def test_implement_md_step_55a_gate_mentions_both_verdict_formats() -> None:
    """STEP 5.5a gate must document both plan-critic verdict formats.

    plan-critic writes verdicts as:
    - "Verdict: PROCEED" (prose/section-header format, in fenced block)
    - "**PROCEED**" (bold table-cell format, in Critique History table)

    The gate prose must reference BOTH so the coordinator accepts pre-validated
    plans regardless of which format appears in the plan file. Regression guard
    for Issue #1135.
    """
    content = _read_command("implement.md")
    assert "Verdict: PROCEED" in content, (
        "implement.md STEP 5.5a gate must mention 'Verdict: PROCEED' "
        "(prose-header format)"
    )
    assert "**PROCEED**" in content, (
        "implement.md STEP 5.5a gate must mention '**PROCEED**' "
        "(bold table-cell format used in Critique History)"
    )

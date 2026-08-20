"""Derive the live plan-critic critique-axis roster from the agent definition.

Single source of truth for any test that needs to know how many critique axes
``plugins/autonomous-dev/agents/plan-critic.md`` declares, or what they are
called.

Why this module exists
----------------------
A test that hardcodes the axis count -- ``assert "six axes" in content`` -- is a
guard scoped to the instance rather than to the class. It goes stale at exactly
the moment the thing it guards changes, and then blocks the change it was
supposed to be checking. Issue #1067 shipped such assertions into two separate
directories; adding the seventh axis (Reachability & Enforceability, commit
``1e8720d1``) broke one of them and left a third -- an enumeration of axis
*names* that simply omitted the new axes -- passing for the wrong reason.

Deriving the roster from the live ``## Critique Axes`` list keeps the real
intent (the prose must not lie about how many axes exist, and every axis must
be carried through the rubric) while surviving future additions.
"""

from __future__ import annotations

import re
from pathlib import Path

# tests/helpers/plan_critic_axes.py -> tests/helpers -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_CRITIC_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "plan-critic.md"

#: Spelled-out counts that may legitimately appear in prose in place of a digit.
NUMBER_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

#: Matches a top-level ``N. **Axis Name**`` entry in the Critique Axes section.
_NUMBERED_AXIS_RE = re.compile(r"^(\d+)\.\s*\*\*(.+?)\*\*", re.MULTILINE)

#: Matches any ``<token> axes`` phrase, e.g. ``seven axes`` or ``4 axes``.
_AXIS_COUNT_PHRASE_RE = re.compile(r"\b(\w+)\s+axes\b", re.IGNORECASE)


def read_plan_critic() -> str:
    """Return the full text of ``plan-critic.md``.

    Returns:
        The agent definition source.

    Raises:
        FileNotFoundError: If the agent definition has moved or been deleted.
    """
    if not PLAN_CRITIC_PATH.exists():
        raise FileNotFoundError(
            f"plan-critic agent definition not found: {PLAN_CRITIC_PATH}\n"
            f"Expected: the plan-critic agent markdown under "
            f"plugins/autonomous-dev/agents/\n"
            f"See: docs/PLANNING-WORKFLOW.md"
        )
    return PLAN_CRITIC_PATH.read_text(encoding="utf-8")


def critique_axes_section(text: str) -> str:
    """Return the body between ``## Critique Axes`` and the next ``## `` heading.

    Args:
        text: Full ``plan-critic.md`` source.

    Returns:
        The section body, excluding the heading itself.

    Raises:
        AssertionError: If the section is absent (the roster cannot be derived).
    """
    match = re.search(r"##\s*Critique Axes\s*\n(.*?)(?=\n##\s)", text, re.DOTALL)
    assert match, (
        "plan-critic.md is missing its '## Critique Axes' section\n"
        f"Expected: a '## Critique Axes' heading in {PLAN_CRITIC_PATH}\n"
        "The axis roster cannot be derived without it."
    )
    return match.group(1)


def axis_names(axes_section: str) -> list[str]:
    """Return the axis names from a Critique Axes section, in listed order.

    Args:
        axes_section: Body returned by :func:`critique_axes_section`.

    Returns:
        Axis names such as ``["Assumption Audit", "Scope Creep Detection", ...]``.
    """
    return [name.strip() for _, name in _NUMBERED_AXIS_RE.findall(axes_section)]


def count_numbered_axes(axes_section: str) -> int:
    """Count top-level ``N. **Axis Name**`` entries in a Critique Axes section.

    Args:
        axes_section: Body returned by :func:`critique_axes_section`.

    Returns:
        The number of numbered axes actually listed.
    """
    return len(axis_names(axes_section))


def live_axis_names() -> list[str]:
    """Return the axis names currently declared by ``plan-critic.md``."""
    return axis_names(critique_axes_section(read_plan_critic()))


def live_axis_count() -> int:
    """Return the number of axes currently declared by ``plan-critic.md``."""
    return len(live_axis_names())


def parse_count_token(token: str) -> int | None:
    """Convert a prose count token to an int, or ``None`` if it is not a count.

    Args:
        token: A single word captured before the literal ``axes``, e.g.
            ``"seven"``, ``"4"``, or a non-count word like ``"all"``.

    Returns:
        The integer value, or ``None`` when the token does not denote a number.
    """
    lowered = token.lower()
    if lowered in NUMBER_WORDS:
        return NUMBER_WORDS[lowered]
    if lowered.isdigit():
        return int(lowered)
    return None


def stated_axis_counts(
    text: str, *, exclude_subset_lines: bool = True
) -> list[tuple[int, int, str]]:
    """Find every prose statement of a full-roster axis count.

    Subjects are discovered by scanning the text at runtime rather than from a
    list fixed at authoring time, so a stale count added in a new sentence is
    caught by the same check that catches the existing ones.

    Args:
        text: Full ``plan-critic.md`` source.
        exclude_subset_lines: When true, skip lines that describe budget mode.
            Budget mode deliberately scores a named subset of the axes, so its
            count is not expected to track the full roster.

    Returns:
        Tuples of ``(line_number, stated_count, line_text)``, one per statement.
    """
    found: list[tuple[int, int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if exclude_subset_lines and "budget" in line.lower():
            continue
        for match in _AXIS_COUNT_PHRASE_RE.finditer(line):
            stated = parse_count_token(match.group(1))
            if stated is not None:
                found.append((lineno, stated, line.strip()))
    return found

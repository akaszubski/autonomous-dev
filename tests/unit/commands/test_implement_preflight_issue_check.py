"""Regression tests for Issue #936: Coordinator pre-flight verify issue not already merged.

Validates that implement.md contains a pre-flight block that skips work on issues which
are already closed or have been referenced in recent commits, preventing the pipeline
from burning agent time on already-merged work.

These are structural tests against the canonical source (`plugins/autonomous-dev/commands/implement.md`).
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
IMPLEMENT_MD = PROJECT_ROOT / "plugins/autonomous-dev/commands/implement.md"


@pytest.fixture(scope="module")
def implement_content() -> str:
    """Read implement.md once for the test module."""
    return IMPLEMENT_MD.read_text()


def test_preflight_block_present(implement_content: str) -> None:
    """implement.md must carry the Issue #936 marker comment for the pre-flight block.

    The marker is the canonical anchor so that future audits / refactors can confirm
    the pre-flight guard is still wired in, not silently deleted.
    """
    marker = "Issue #936: prevent burning pipeline time on already-merged work"
    assert marker in implement_content, (
        "implement.md must contain the Issue #936 marker comment. "
        f"Expected substring: {marker!r}. "
        "This anchors the pre-flight skip logic to the originating issue."
    )


def test_preflight_checks_issue_state_not_open(implement_content: str) -> None:
    """Pre-flight must check ISSUE_STATE against OPEN, and the gh json call must fetch state.

    Two coupled requirements:
      1. The gh issue view call MUST include `state` in --json fields (otherwise ISSUE_STATE
         is never populated).
      2. There MUST be a conditional that blocks when ISSUE_STATE is set but not 'OPEN'.
    """
    # Requirement 1: gh must fetch state alongside title and body.
    assert "title,body,state" in implement_content, (
        "implement.md `gh issue view` call must request `state` in --json fields. "
        "Expected substring 'title,body,state' so ISSUE_STATE is populated."
    )

    # Requirement 2: a conditional that checks ISSUE_STATE != "OPEN".
    assert "ISSUE_STATE" in implement_content, (
        "implement.md must reference ISSUE_STATE in the pre-flight block."
    )
    assert '!= "OPEN"' in implement_content, (
        "implement.md must contain the conditional `!= \"OPEN\"` to skip non-open issues. "
        "Without this, CLOSED/MERGED issues are not detected before pipeline launch."
    )


def test_preflight_checks_git_log_grep(implement_content: str) -> None:
    """Pre-flight must scan recent commits for references to the issue number.

    Even when `gh` is unavailable or the issue state cannot be fetched, the commit-log
    check MUST run so already-addressed issues are still caught (AC #5).
    """
    expected = 'git log --oneline -n 20 --grep "#${ISSUE_NUMBER}'
    assert expected in implement_content, (
        f"implement.md must contain a git log scan for issue references. "
        f"Expected substring: {expected!r}. "
        "This is the fallback check that works even when `gh` is unavailable."
    )


def test_preflight_respects_force_and_empty_issue(implement_content: str) -> None:
    """Pre-flight must skip both checks when ISSUE_NUMBER is empty OR --force is supplied.

    The single guard expression handles two acceptance criteria at once:
      - AC #3: --force in ARGUMENTS skips both checks (operator override).
      - AC #4: empty ISSUE_NUMBER (free-text invocation) skips both checks.
    """
    guard = '[ -n "$ISSUE_NUMBER" ] && ! echo "ARGUMENTS" | grep -q -- "--force"'
    assert guard in implement_content, (
        f"implement.md must contain the pre-flight guard expression. "
        f"Expected substring: {guard!r}. "
        "Without this, free-text invocations and --force overrides are blocked unexpectedly."
    )

"""Regression test for drain-watchdog self-loop bug (Issue #1275).

Root cause: drain-watchdog.yml labeled stuck-drain alert issues with BOTH
"drain-stuck" AND "auto-improvement". The watchdog's own detection logic then
picked up those alert issues as drainable auto-improvement work, creating a
fixed-point loop where each heal cycle drained only watchdog bookkeeping issues
while the real backlog never moved.

Fix (ADR-002 Phase A, bug fix #4): remove "auto-improvement" from the
watchdog's --label flag so stuck-alert issues are not visible to the
auto-improvement drain pipeline.
"""

from pathlib import Path


# Use parents[3] to walk up: smoke/ -> regression/ -> tests/ -> repo root
WORKFLOW_FILE = (
    Path(__file__).resolve().parents[3] / ".github" / "workflows" / "drain-watchdog.yml"
)


def test_drain_watchdog_does_not_label_stuck_as_auto_improvement() -> None:
    """drain-watchdog.yml must not apply auto-improvement label to stuck alerts.

    Applying 'auto-improvement' to watchdog alert issues causes the watchdog to
    pick them up as drainable work, creating a self-loop: watchdog fires,
    creates a 'drain-stuck' alert issue labelled 'auto-improvement', the next
    heal cycle drains that alert issue, commits a trivial change, but the real
    backlog never moves — and the next cron fire repeats the cycle.
    """
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    assert "drain-stuck,auto-improvement" not in content, (
        "drain-watchdog.yml must not label drain-stuck issues as auto-improvement "
        "(Issue #1275 — causes self-loop)"
    )


def test_drain_watchdog_drain_stuck_label_present() -> None:
    """drain-watchdog.yml must still apply the 'drain-stuck' label to alert issues.

    Positive control: verifies the watchdog label was not removed entirely.
    The 'drain-stuck' label is required for the debounce filter (line ~159)
    to detect recently-filed alert issues and suppress duplicate filings.
    """
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    assert '--label "drain-stuck"' in content, (
        "drain-watchdog.yml must apply --label \"drain-stuck\" to alert issues — "
        "required for the debounce filter that suppresses duplicate watchdog alerts"
    )


def test_drain_watchdog_emits_selector_stall_label() -> None:
    """Issue #1303 — selector-stall alert step labels with selector-stall + high-priority."""
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    # Accept either inline list or separate label flags
    assert (
        "selector-stall,high-priority" in content
        or ('"selector-stall"' in content and '"high-priority"' in content)
        or ("'selector-stall'" in content and "'high-priority'" in content)
        or ("--label selector-stall" in content and "--label high-priority" in content)
    ), (
        "drain-watchdog.yml must label selector-stall alerts with both "
        "'selector-stall' and 'high-priority' (Issue #1303)"
    )


def test_drain_watchdog_imports_selector_stall_detector() -> None:
    """Issue #1303 — workflow must invoke the selector_stall_detector module."""
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    assert "selector_stall_detector" in content, (
        "drain-watchdog.yml must import/invoke selector_stall_detector "
        "(Issue #1303 Phase E sub-D)"
    )


def test_drain_watchdog_selector_stall_debounce_present() -> None:
    """AC2 — reuse 4h debounce pattern for selector-stall alerts."""
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    # Existing drain-stuck debounce already says "4 hours ago"; new
    # selector-stall step should also use this pattern, so count should be >= 2.
    assert content.count("4 hours ago") >= 2, (
        "drain-watchdog.yml selector-stall step must reuse the '4 hours ago' "
        "debounce pattern (Issue #1303 AC2)"
    )

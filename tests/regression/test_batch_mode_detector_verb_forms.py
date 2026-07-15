#!/usr/bin/env python3
"""
Regression test for batch_mode_detector verb-form morphology (Issue #1391).

Tests that issue titles with verb forms like "fails", "test fails", and 
"pre-existing:" are properly classified as FIX mode, not FULL mode.
"""

import sys
from pathlib import Path

# Add lib to path
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "plugins/autonomous-dev/lib"))

from batch_mode_detector import detect_issue_mode, PipelineMode


def test_issue_1614_pre_existing_fails_pattern():
    """
    Test the exact pattern from issue #1614 that was misclassified.
    
    Title: "Pre-existing: test_no_time_sleep_in_smoke_tree fails — time.sleep(1.0) at tests/smoke/harness.py:776"
    Should detect as FIX mode due to "pre-existing:" and "fails" signals.
    """
    title = "Pre-existing: test_no_time_sleep_in_smoke_tree fails — time.sleep(1.0) at tests/smoke/harness.py:776"
    body = ""
    labels = []  # No labels, including no "in-progress"
    
    detection = detect_issue_mode(title, body, labels)
    
    assert detection.mode == PipelineMode.FIX, (
        f"Expected FIX mode for issue #1614 pattern, got {detection.mode}. "
        f"Signals detected: {detection.signals}"
    )
    
    # Verify the right signals were detected
    assert any("pre-existing:" in signal.lower() for signal in detection.signals), \
        f"Expected 'pre-existing:' signal to be detected. Got: {detection.signals}"
    assert any("fails" in signal.lower() for signal in detection.signals), \
        f"Expected 'fails' signal to be detected. Got: {detection.signals}"


def test_test_fails_verb_form():
    """
    Test that "test_x fails" pattern is detected as FIX mode.
    """
    title = "test_integration_flow fails with timeout"
    body = "The integration test is timing out after recent changes."
    labels = []
    
    detection = detect_issue_mode(title, body, labels)
    
    assert detection.mode == PipelineMode.FIX, (
        f"Expected FIX mode for 'test_x fails' pattern, got {detection.mode}. "
        f"Signals detected: {detection.signals}"
    )
    
    # Should detect both "test fails" and "fails" signals
    assert any("fails" in signal.lower() for signal in detection.signals), \
        f"Expected 'fails' signal to be detected. Got: {detection.signals}"


def test_pre_existing_prefix_alone():
    """
    Test that "Pre-existing:" prefix alone triggers FIX mode.
    """
    title = "Pre-existing: deprecated API usage in auth module"
    body = "Found during code review."
    labels = []
    
    detection = detect_issue_mode(title, body, labels)
    
    assert detection.mode == PipelineMode.FIX, (
        f"Expected FIX mode for 'Pre-existing:' prefix, got {detection.mode}. "
        f"Signals detected: {detection.signals}"
    )
    
    assert any("pre-existing:" in signal.lower() for signal in detection.signals), \
        f"Expected 'pre-existing:' signal to be detected. Got: {detection.signals}"


def test_fails_verb_in_body():
    """
    Test that "fails" in the body also contributes to FIX detection.
    """
    title = "CI pipeline issue"
    body = "The deployment step fails when environment variables are not set."
    labels = []
    
    detection = detect_issue_mode(title, body, labels)
    
    # With "fails" only in body, it gets +1 score. Combined with "[ci]" in title (+2), 
    # total fix_score = 3, which should result in FIX mode
    assert detection.mode == PipelineMode.FIX, (
        f"Expected FIX mode for '[ci]' + 'fails' pattern, got {detection.mode}. "
        f"Signals detected: {detection.signals}"
    )


if __name__ == "__main__":
    # Run tests locally
    test_issue_1614_pre_existing_fails_pattern()
    print("✓ test_issue_1614_pre_existing_fails_pattern passed")
    
    test_test_fails_verb_form()
    print("✓ test_test_fails_verb_form passed")
    
    test_pre_existing_prefix_alone()
    print("✓ test_pre_existing_prefix_alone passed")
    
    test_fails_verb_in_body()
    print("✓ test_fails_verb_in_body passed")
    
    print("\nAll tests passed!")
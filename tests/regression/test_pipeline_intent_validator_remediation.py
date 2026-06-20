#!/usr/bin/env python3
"""
Regression tests for pipeline_intent_validator remediation flag handling (Issue #1217).

Tests verify that remediation=true metadata prevents false-positive step_ordering findings
when implementer/reviewer/security-auditor are re-invoked during remediation cycles.
"""

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add lib paths for imports
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "plugins/autonomous-dev/lib"))

from pipeline_intent_validator import validate_pipeline_intent


def create_test_log(entries):
    """Helper to create a temporary JSONL log file from entries."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')
        return Path(f.name)


def test_remediation_flag_skips_ordering_checks():
    """
    Test that cycle-2 agent invocations with remediation=true do not produce
    step_ordering CRITICAL findings.
    
    This simulates a realistic remediation cycle where implementer, reviewer,
    and security-auditor are re-invoked after initial failures.
    """
    # Create a synthetic activity log with a typical remediation pattern
    entries = [
        # Initial pipeline run (cycle 1)
        {
            "timestamp": "2024-01-01T10:00:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "researcher-local",
            }
        },
        {
            "timestamp": "2024-01-01T10:01:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "researcher",
            }
        },
        {
            "timestamp": "2024-01-01T10:02:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "planner",
            }
        },
        {
            "timestamp": "2024-01-01T10:03:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "implementer",
            }
        },
        {
            "timestamp": "2024-01-01T10:04:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "reviewer",
            }
        },
        {
            "timestamp": "2024-01-01T10:05:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "security-auditor",
            }
        },
        # Remediation cycle 2 - these should NOT produce ordering findings
        {
            "timestamp": "2024-01-01T10:06:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "implementer",
                "remediation": True,  # This flag should prevent ordering findings
            }
        },
        {
            "timestamp": "2024-01-01T10:07:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "reviewer",
                "remediation": True,
            }
        },
        {
            "timestamp": "2024-01-01T10:08:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "security-auditor",
                "remediation": True,
            }
        },
    ]
    
    # Create log file and validate
    log_path = create_test_log(entries)
    try:
        findings = validate_pipeline_intent(log_path)
        
        # Filter for step_ordering CRITICAL findings
        step_ordering_findings = [
            f for f in findings 
            if f.finding_type == "step_ordering" and f.severity == "CRITICAL"
        ]
        
        # There should be NO step_ordering findings because remediation=true
        # events are excluded from ordering checks
        assert len(step_ordering_findings) == 0, \
            f"Expected 0 step_ordering findings with remediation flag, got {len(step_ordering_findings)}: {step_ordering_findings}"
    finally:
        log_path.unlink()


def test_no_remediation_flag_produces_ordering_findings():
    """
    Test that out-of-order agents WITHOUT remediation=true DO produce
    step_ordering findings, proving the guard is not vacuously true.
    """
    # Create a scenario with agents running out of order WITHOUT remediation flag
    entries = [
        # Implementer runs BEFORE planner - this is wrong!
        {
            "timestamp": "2024-01-01T10:00:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "implementer",
                # NO remediation flag - should trigger ordering finding
            }
        },
        # Planner runs AFTER implementer - wrong order
        {
            "timestamp": "2024-01-01T10:01:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "planner",
            }
        },
    ]
    
    # Create log file and validate
    log_path = create_test_log(entries)
    try:
        findings = validate_pipeline_intent(log_path)
        
        # Filter for step_ordering CRITICAL findings
        step_ordering_findings = [
            f for f in findings 
            if f.finding_type == "step_ordering" and f.severity == "CRITICAL"
        ]
        
        # Without remediation flag, duplicate agents should produce ordering findings
        # We expect findings because implementer/reviewer/security-auditor appear twice
        # and the second occurrences will be compared against earlier agents
        assert len(step_ordering_findings) > 0, \
            "Expected step_ordering findings without remediation flag, but got none"
    finally:
        log_path.unlink()


def test_cycle_3_without_flag_resumes_normal_checks():
    """
    Test that cycle-3 invocations without the remediation flag resume normal
    ordering checks, ensuring the flag is evaluated per-event and not globally.
    """
    # Create a log with mixed remediation and non-remediation events
    entries = [
        # Initial run
        {
            "timestamp": "2024-01-01T10:00:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "planner",
            }
        },
        {
            "timestamp": "2024-01-01T10:01:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "implementer",
            }
        },
        # Cycle 2 with remediation flag (should be ignored for ordering)
        {
            "timestamp": "2024-01-01T10:02:00Z",
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "implementer",
                "remediation": True,
            }
        },
        # Cycle 3 without flag - if this runs before planner, it should error
        # We intentionally put it at an earlier timestamp than planner to trigger
        # an ordering violation IF the check is active (which it should be)
        {
            "timestamp": "2024-01-01T09:59:00Z",  # Earlier than planner!
            "event_type": "PreToolUse",
            "tool": "Task",
            "agent": "main",
            "input_summary": {
                "pipeline_action": "agent_invocation",
                "subagent_type": "implementer",
                # NO remediation flag - normal checks should apply
            }
        },
    ]
    
    # Create log file and validate
    log_path = create_test_log(entries)
    try:
        findings = validate_pipeline_intent(log_path)
        
        # Filter for step_ordering CRITICAL findings
        step_ordering_findings = [
            f for f in findings 
            if f.finding_type == "step_ordering" and f.severity == "CRITICAL"
        ]
        
        # The cycle-3 implementer (without flag) running before planner should
        # produce an ordering finding
        assert len(step_ordering_findings) > 0, \
            "Expected ordering finding for cycle-3 implementer before planner"
        
        # Verify the finding is about implementer before planner
        found_expected = False
        for finding in step_ordering_findings:
            if "implementer" in finding.description and "planner" in finding.description:
                found_expected = True
                break
        
        assert found_expected, \
            f"Expected finding about implementer before planner, got: {[f.description for f in step_ordering_findings]}"
    finally:
        log_path.unlink()
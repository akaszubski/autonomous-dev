"""Regression test for Issue #1359: Light mode prompt integrity false positives.

The prompt_integrity module was firing false-positive shrinkage blocks on --light
mode planner because the baseline was recorded from a full-pipeline run. This test
verifies that "light" mode gets appropriate threshold relaxation (2.5x multiplier
yielding 37.5% threshold from base 15%).
"""

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"))
from prompt_integrity import (
    REINVOCATION_CONTEXTS,
    validate_prompt_word_count,
    record_prompt_baseline,
    get_cross_issue_baseline,
)


def test_light_mode_in_reinvocation_contexts():
    """Verify 'light' is recognized as a reinvocation context."""
    assert "light" in REINVOCATION_CONTEXTS


def test_light_mode_shrinkage_within_threshold_passes():
    """Test that 20.9% shrinkage on light mode passes (37.5% threshold)."""
    # 793 -> 627 words = 20.9% shrinkage (observed evidence from issue)
    prompt = "word " * 627  # 627 words
    baseline = 793  # baseline word count
    
    result = validate_prompt_word_count(
        agent_type="planner",
        prompt=prompt,
        baseline_word_count=baseline,
        invocation_context="light",
        pipeline_mode="light"
    )
    assert result.passed, f"Expected valid for 20.9% shrinkage in light mode, got: {result.reason}"


def test_light_mode_excessive_shrinkage_fails():
    """Test that 40% shrinkage on light mode still fails (exceeds 37.5% threshold)."""
    prompt = "word " * 600  # 600 words
    baseline = 1000  # 40% shrinkage
    
    result = validate_prompt_word_count(
        agent_type="planner",
        prompt=prompt,
        baseline_word_count=baseline,
        invocation_context="light",
        pipeline_mode="light"
    )
    assert not result.passed, f"Expected invalid for 40% shrinkage in light mode"
    assert "40.0%" in result.reason or "exceeds" in result.reason


def test_light_mode_cross_mode_mismatch_returns_none():
    """Test that baseline recorded with full mode, queried with light mode returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)
        
        # Record baseline with full mode
        record_prompt_baseline(
            agent_type="planner",
            issue_number=1,
            word_count=1000,
            state_dir=state_dir,
            pipeline_mode="full"
        )
        
        # Query with light mode - should return None due to mode mismatch
        baseline = get_cross_issue_baseline(
            agent_type="planner",
            current_issue=2,  # Query for issue 2, looking for baseline from issue 1
            state_dir=state_dir,
            pipeline_mode="light"
        )
        assert baseline is None, "Expected None for mode mismatch (full -> light)"


def test_light_mode_multiplier_applied_correctly():
    """Test that light mode applies 2.5x multiplier (37.5% threshold)."""
    # Test at exactly 37.5% shrinkage (should pass)
    prompt = "word " * 625  # 625 words
    baseline = 1000  # Exactly 37.5% shrinkage
    
    result = validate_prompt_word_count(
        agent_type="planner",
        prompt=prompt,
        baseline_word_count=baseline,
        invocation_context="light",
        pipeline_mode="light"
    )
    assert result.passed, f"Expected valid at exactly 37.5% threshold"
    
    # Test at 37.6% shrinkage (should fail)
    prompt = "word " * 624  # 624 words
    baseline = 1000  # 37.6% shrinkage
    
    result = validate_prompt_word_count(
        agent_type="planner",
        prompt=prompt,
        baseline_word_count=baseline,
        invocation_context="light",
        pipeline_mode="light"
    )
    assert not result.passed, f"Expected invalid at 37.6% shrinkage (exceeds threshold)"
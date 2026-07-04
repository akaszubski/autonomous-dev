#!/usr/bin/env python3
"""Test for Issue #1358: Pipeline-mode-aware prompt baselines.

Verifies that prompt_integrity properly handles pipeline modes and
applies correct shrinkage thresholds for fix mode.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Path setup
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from prompt_integrity import (
    record_prompt_baseline,
    get_prompt_baseline,
    get_cross_issue_baseline,
    validate_prompt_word_count,
    REINVOCATION_CONTEXTS,
)


class TestPipelineModeAware:
    """Test pipeline-mode-aware prompt baselines (Issue #1358)."""

    def test_fix_in_reinvocation_contexts(self):
        """Verify 'fix' is in REINVOCATION_CONTEXTS."""
        assert "fix" in REINVOCATION_CONTEXTS, "Issue #1358: 'fix' must be in REINVOCATION_CONTEXTS"

    def test_record_baseline_with_mode(self):
        """Test recording baseline with pipeline mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            
            # Record baseline with mode
            record_prompt_baseline(
                "reviewer", 
                issue_number=1, 
                word_count=500,
                state_dir=state_dir,
                pipeline_mode="full"
            )
            
            # Read and verify structure
            baselines_path = state_dir / "prompt_baselines.json"
            with open(baselines_path, 'r') as f:
                data = json.load(f)
            
            assert "reviewer" in data
            assert "1" in data["reviewer"]
            baseline_data = data["reviewer"]["1"]
            assert isinstance(baseline_data, dict), "Baseline should be stored as dict"
            assert baseline_data["word_count"] == 500
            assert baseline_data["pipeline_mode"] == "full"

    def test_backward_compat_bare_int(self):
        """Test backward compatibility with old bare-int format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            baselines_path = state_dir / "prompt_baselines.json"
            
            # Write old format (bare int)
            old_data = {"reviewer": {"1": 500}}
            baselines_path.parent.mkdir(parents=True, exist_ok=True)
            with open(baselines_path, 'w') as f:
                json.dump(old_data, f)
            
            # Should still be able to read it
            baseline = get_prompt_baseline("reviewer", issue_number=1, state_dir=state_dir)
            assert baseline == 500, "Should read old bare-int format"

    def test_cross_issue_mode_mismatch_skip(self):
        """Test that cross-issue comparison is skipped when modes differ."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            
            # Record issue 1 with mode="full"
            record_prompt_baseline(
                "reviewer", 
                issue_number=1, 
                word_count=500,
                state_dir=state_dir,
                pipeline_mode="full"
            )
            
            # Try to get cross-issue baseline for issue 2 with mode="fix"
            baseline = get_cross_issue_baseline(
                "reviewer",
                current_issue=2,
                state_dir=state_dir,
                pipeline_mode="fix"
            )
            
            # Should return None due to mode mismatch
            assert baseline is None, "Cross-issue baseline should be None when modes differ"

    def test_cross_issue_same_mode_works(self):
        """Test that cross-issue comparison works when modes match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            
            # Record issue 1 with mode="full"
            record_prompt_baseline(
                "reviewer", 
                issue_number=1, 
                word_count=500,
                state_dir=state_dir,
                pipeline_mode="full"
            )
            
            # Get cross-issue baseline for issue 2 with same mode
            baseline = get_cross_issue_baseline(
                "reviewer",
                current_issue=2,
                state_dir=state_dir,
                pipeline_mode="full"
            )
            
            # Should return the baseline since modes match
            assert baseline == 500, "Cross-issue baseline should work when modes match"

    def test_fix_mode_3x_multiplier(self):
        """Test that fix mode uses 3.0x multiplier on shrinkage threshold."""
        # Normal threshold is 15%, so with 3x multiplier it becomes 45%
        
        # Test with 40% shrinkage (should fail without fix mode, pass with fix mode)
        prompt = "word " * 60  # 60 words
        baseline = 100  # baseline is 100 words, so 40% shrinkage
        
        # Without fix mode context - should fail
        result = validate_prompt_word_count(
            "reviewer",
            prompt,
            baseline,
            max_shrinkage=0.15,
            invocation_context=None,
            pipeline_mode="full"
        )
        assert not result.passed, "40% shrinkage should fail without fix context"
        
        # With fix mode context - should pass (3x multiplier = 45% threshold)
        result = validate_prompt_word_count(
            "reviewer",
            prompt,
            baseline,
            max_shrinkage=0.15,
            invocation_context="fix",
            pipeline_mode="fix"
        )
        assert result.passed, "40% shrinkage should pass with fix context (3x multiplier)"

    def test_other_reinvocation_2x_multiplier(self):
        """Test that other reinvocation contexts use 2.0x multiplier."""
        # Normal threshold is 15%, so with 2x multiplier it becomes 30%
        
        # Test with 25% shrinkage (should fail without context, pass with 2x)
        prompt = "word " * 75  # 75 words
        baseline = 100  # baseline is 100 words, so 25% shrinkage
        
        # Without reinvocation context - should fail
        result = validate_prompt_word_count(
            "reviewer",
            prompt,
            baseline,
            max_shrinkage=0.15,
            invocation_context=None
        )
        assert not result.passed, "25% shrinkage should fail without context"
        
        # With remediation context - should pass (2x multiplier = 30% threshold)
        result = validate_prompt_word_count(
            "reviewer",
            prompt,
            baseline,
            max_shrinkage=0.15,
            invocation_context="remediation"
        )
        assert result.passed, "25% shrinkage should pass with remediation context (2x multiplier)"

    def test_fix_mode_50_percent_shrinkage_fails(self):
        """Test that even fix mode fails at 50% shrinkage (above 45% threshold)."""
        # 50% shrinkage should fail even with 3x multiplier (45% threshold)
        prompt = "word " * 50  # 50 words
        baseline = 100  # baseline is 100 words, so 50% shrinkage
        
        result = validate_prompt_word_count(
            "reviewer",
            prompt,
            baseline,
            max_shrinkage=0.15,
            invocation_context="fix",
            pipeline_mode="fix"
        )
        assert not result.passed, "50% shrinkage should fail even with fix context"
        assert "exceeds" in result.reason

    def test_multiple_issues_different_modes(self):
        """Test storing multiple issues with different modes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            
            # Record multiple baselines
            record_prompt_baseline("reviewer", 1, 500, state_dir=state_dir, pipeline_mode="full")
            record_prompt_baseline("reviewer", 2, 450, state_dir=state_dir, pipeline_mode="fix")
            record_prompt_baseline("reviewer", 3, 480, state_dir=state_dir, pipeline_mode="light")
            
            # Verify all stored correctly
            baselines_path = state_dir / "prompt_baselines.json"
            with open(baselines_path, 'r') as f:
                data = json.load(f)
            
            assert data["reviewer"]["1"]["pipeline_mode"] == "full"
            assert data["reviewer"]["2"]["pipeline_mode"] == "fix"
            assert data["reviewer"]["3"]["pipeline_mode"] == "light"
            assert data["reviewer"]["1"]["word_count"] == 500
            assert data["reviewer"]["2"]["word_count"] == 450
            assert data["reviewer"]["3"]["word_count"] == 480


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
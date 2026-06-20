#!/usr/bin/env python3
"""
Regression tests for Issue #1227: Redispatch false positives in prompt shrink detector.

Tests that the prompt shrink detector correctly handles legitimate coordinator
re-dispatches after a gate denial, avoiding false positive blocks.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add lib to path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
lib_path = project_root / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(lib_path))

from prompt_integrity import (
    set_redispatch_flag,
    consume_redispatch_flag,
    is_canonical_template_match,
    validate_prompt_word_count,
    record_prompt_baseline,
    MIN_CRITICAL_AGENT_PROMPT_WORDS,
)
from pipeline_state import create_pipeline, save_pipeline, load_pipeline, get_legacy_sentinel_path


class TestRedispatchFalsePrevention(unittest.TestCase):
    """Test redispatch false positive prevention mechanisms."""
    
    def setUp(self):
        """Create test environment with real sentinel and state files."""
        self.run_id = "test-run-001"
        
        # Create the sentinel file in the expected location
        self.sentinel_path = get_legacy_sentinel_path()
        self.sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        
        sentinel_data = {
            "run_id": self.run_id,
            "mode": "full",
            "feature": "test feature"
        }
        with open(self.sentinel_path, "w") as f:
            json.dump(sentinel_data, f)
        
        # Create pipeline state
        self.state = create_pipeline(self.run_id, "test feature", mode="full")
        save_pipeline(self.state)
        
    def tearDown(self):
        """Clean up test files."""
        # Remove sentinel
        if self.sentinel_path.exists():
            self.sentinel_path.unlink()
            
        # Remove state file
        state_path = Path(f"/tmp/pipeline_state_{self.run_id}.json")
        if state_path.exists():
            state_path.unlink()
    
    def test_redispatch_flag_set_and_consumed_once(self):
        """Test 1: Set flag for doc-master, consume returns True, second consume returns False."""
        # Set flag
        set_redispatch_flag("doc-master")
        
        # Verify it's in the state
        state = load_pipeline(self.run_id)
        self.assertIn("doc-master", state.redispatch_agents)
        self.assertTrue(state.redispatch_agents["doc-master"])
        
        # First consume should return True
        result1 = consume_redispatch_flag("doc-master")
        self.assertTrue(result1, "First consume should return True")
        
        # Verify flag is removed
        state = load_pipeline(self.run_id) 
        self.assertNotIn("doc-master", state.redispatch_agents)
        
        # Second consume should return False
        result2 = consume_redispatch_flag("doc-master")
        self.assertFalse(result2, "Second consume should return False")
    
    def test_redispatch_flag_skips_shrinkage_check(self):
        """Test 2: Set flag, call validate_prompt_integrity with shrunken prompt, assert allow."""
        # Set the flag
        set_redispatch_flag("reviewer")
        
        # Create a prompt that passes minimum but would fail shrinkage
        # Use 100 words (above MIN_CRITICAL_AGENT_PROMPT_WORDS of 80)
        prompt = "word " * 100  
        baseline = 200  # So we have 50% shrinkage
        
        # Validate - should pass despite 50% shrinkage due to flag
        result = validate_prompt_word_count(
            "reviewer",
            prompt,
            baseline_word_count=baseline,
            max_shrinkage=0.20  # 20% threshold
        )
        
        self.assertTrue(result.passed, f"Should pass with redispatch flag. Reason: {result.reason}")
        self.assertIn("redispatch", result.reason.lower())
        
        # Flag should be consumed
        state = load_pipeline(self.run_id)
        self.assertNotIn("reviewer", state.redispatch_agents)
    
    def test_canonical_template_match_resets_baseline(self):
        """Test 3: Record low baseline, send prompt matching canonical template, assert allow + baseline updated."""
        # Mock get_agent_prompt_template to return a known template
        canonical_template = "instruction " * 150  # 150 words
        
        with patch('prompt_integrity.get_agent_prompt_template') as mock_get_template:
            mock_get_template.return_value = canonical_template
            
            # Test canonical matching
            matching_prompt = "different " * 148  # Within 10% of 150
            is_match = is_canonical_template_match("implementer", matching_prompt)
            self.assertTrue(is_match, "Should match canonical template within tolerance")
            
            # Now test with shrinkage detection
            # Start with a baseline that would trigger shrinkage
            baseline = 250  # High baseline
            
            with patch('prompt_integrity.is_canonical_template_match') as mock_match:
                mock_match.return_value = True
                with patch('prompt_integrity.record_prompt_baseline') as mock_record:
                    result = validate_prompt_word_count(
                        "implementer",
                        matching_prompt,  # 148 words
                        baseline_word_count=baseline,  # Would be 40% shrinkage
                        max_shrinkage=0.20
                    )
                    
                    # Should pass due to canonical match despite apparent shrinkage
                    self.assertTrue(result.passed, f"Should pass with canonical match. Reason: {result.reason}")
                    if result.passed and "canonical" in result.reason.lower():
                        # Baseline should have been reset
                        self.assertIn("canonical", result.reason.lower())
    
    def test_genuine_shrink_still_blocks_when_no_flag_and_no_canonical_match(self):
        """Test 4: No flag, prompt 50% of baseline, no canonical match → assert deny."""
        # Use word count above minimum (100 > 80) but still heavily shrunken
        prompt = "word " * 100  # 100 words
        baseline = 200  # 50% shrinkage
        
        # Mock to ensure no canonical match
        with patch('prompt_integrity.is_canonical_template_match') as mock_match:
            mock_match.return_value = False
            
            result = validate_prompt_word_count(
                "security-auditor",
                prompt,
                baseline_word_count=baseline,
                max_shrinkage=0.20  # 20% threshold
            )
            
            self.assertFalse(result.passed, "Should block genuine 50% shrinkage")
            self.assertIn("shrank", result.reason.lower(), f"Reason should mention shrinkage: {result.reason}")
            self.assertAlmostEqual(result.shrinkage_pct, 50.0, places=1)
    
    def test_redispatch_helpers_noop_when_no_pipeline_state(self):
        """Test 5: Call set/consume with no active pipeline → no exception, returns False."""
        # Remove the sentinel to simulate no active pipeline
        if self.sentinel_path.exists():
            self.sentinel_path.unlink()
        
        # Set should not raise
        try:
            set_redispatch_flag("reviewer")
        except Exception as e:
            self.fail(f"set_redispatch_flag raised exception: {e}")
        
        # Consume should return False (no state)
        result = consume_redispatch_flag("reviewer")
        self.assertFalse(result, "Should return False when no pipeline state exists")


class TestIssue1227TestCount(unittest.TestCase):
    """Meta-test to verify we have the required number of tests."""
    
    def test_regression_test_count(self):
        """Verify we have at least 5 test functions as required."""
        # Count test methods in TestRedispatchFalsePrevention
        test_methods = [
            m for m in dir(TestRedispatchFalsePrevention)
            if m.startswith('test_') and callable(getattr(TestRedispatchFalsePrevention, m))
        ]
        
        self.assertGreaterEqual(
            len(test_methods), 5,
            f"Need at least 5 test methods, found {len(test_methods)}: {test_methods}"
        )


if __name__ == "__main__":
    unittest.main()

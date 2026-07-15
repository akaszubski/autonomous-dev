#!/usr/bin/env python3
"""Test for Issue #1375: Pipeline bypass warning when implementer runs without planner/reviewer.

When implementer SubagentStop occurs without prior planner or reviewer completion
in the same session, a warning should be logged to the activity log.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone

try:
    import pytest
except ImportError:
    pytest = None


def test_implementer_without_planner_reviewer_logs_warning():
    """Verify pipeline bypass warning is logged when implementer runs alone."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up test environment
        tmp_path = Path(tmpdir)
        claude_dir = tmp_path / ".claude"
        logs_dir = claude_dir / "logs" / "activity"
        logs_dir.mkdir(parents=True)
        
        # Create empty state to simulate no prior completions
        state_dir = tmp_path / "tmp"
        state_dir.mkdir()
        session_id = "test-session-1375"
        
        # Prepare environment and payload
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        
        payload = {
            "agent_type": "implementer",
            "session_id": session_id,
            "last_assistant_message": "Implementation complete",
            "agent_transcript_path": ""
        }
        
        # Run the actual hook
        hook_path = Path(__file__).parents[2] / "plugins/autonomous-dev/hooks/unified_session_tracker.py"
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=str(tmp_path),
            env=env
        )
        
        # Verify non-blocking (exit 0)
        assert result.returncode == 0, f"Hook must not block, got {result.returncode}"
        
        # Check for warning in activity log
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = logs_dir / f"{today}.jsonl"
        
        if log_file.exists():
            with open(log_file) as f:
                lines = f.readlines()
            
            # Look for our warning
            found_warning = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if (entry.get("kind") == "pipeline_bypass_warning" and 
                        entry.get("session_id") == session_id):
                        found_warning = True
                        assert "implementer invoked without prior planner/reviewer" in entry.get("message", "")
                        break
                except:
                    pass
            
            assert found_warning, "Pipeline bypass warning should be logged"


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__, "-v"])
    else:
        # Run test manually
        print("Testing pipeline bypass warning...")
        try:
            test_implementer_without_planner_reviewer_logs_warning()
            print("✓ Test passed")
        except AssertionError as e:
            print(f"✗ Test failed: {e}")
            sys.exit(1)
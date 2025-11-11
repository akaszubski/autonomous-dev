#!/usr/bin/env python3
"""Debug script to test agent detection"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "plugins" / "autonomous-dev" / "lib"))

from scripts.agent_tracker import AgentTracker

# Create test files
tmp_dir = Path("/tmp/test_agent_tracker")
tmp_dir.mkdir(exist_ok=True)

json_file = tmp_dir / "test_session.json"
json_data = {
    "session_id": "20251111-test",
    "started": "2025-11-11T10:00:00",
    "agents": []
}
json_file.write_text(json.dumps(json_data, indent=2))

text_file = tmp_dir / "20251111-test-session.md"
text_content = """# Session 20251111-test

**Started**: 2025-11-11 10:00:00

---

**10:00:05 - researcher**: Starting research on JWT authentication patterns

**10:05:43 - researcher**: Research completed - Found 3 relevant patterns

**10:05:50 - planner**: Starting architecture planning for JWT implementation

**10:12:27 - planner**: Planning completed - Created 5-phase implementation plan
"""
text_file.write_text(text_content)

# Test detection
tracker = AgentTracker(session_file=str(json_file))
researcher = tracker._detect_agent_from_session_text("researcher", str(text_file))
planner = tracker._detect_agent_from_session_text("planner", str(text_file))

print("Researcher:", json.dumps(researcher, indent=2))
print("\nPlanner:", json.dumps(planner, indent=2))

if researcher and planner:
    r_start = datetime.fromisoformat(researcher["started_at"])
    p_start = datetime.fromisoformat(planner["started_at"])
    diff = abs((p_start - r_start).total_seconds())
    print(f"\nTime difference between starts: {diff} seconds")
    print(f"Parallel (< 5 sec)? {diff < 5}")

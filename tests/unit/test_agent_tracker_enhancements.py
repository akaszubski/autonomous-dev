#!/usr/bin/env python3
"""
Tests for agent_tracker.py enhancements - Display metadata and progress

This module tests the enhancements to AgentTracker that support
the real-time progress display system.

New features tested:
- Display metadata (estimated time, progress percentage)
- Progress calculation methods
- Agent display names and descriptions
- Tree view data structure generation
- Expected agent list management

Test Coverage:
- Progress calculation with different agent states
- Display metadata generation
- Agent ordering and grouping
- Time estimation logic
- Display-friendly data formatting

These tests follow TDD - they WILL FAIL until enhancements are implemented.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agent_tracker import AgentTracker


class TestAgentTrackerEnhancements:
    """Test new display-related features in AgentTracker."""

    # ========================================
    # FIXTURES
    # ========================================

    @pytest.fixture
    def tracker_with_session(self, tmp_path):
        """Create AgentTracker with temporary session."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)

        with patch.object(AgentTracker, '__init__') as mock_init:
            mock_init.return_value = None
            tracker = AgentTracker()

            tracker.session_dir = session_dir
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            tracker.session_file = session_dir / f"{timestamp}-pipeline.json"
            tracker.session_data = {
                "session_id": timestamp,
                "started": datetime.now().isoformat(),
                "github_issue": None,
                "agents": []
            }
            tracker._save = lambda: tracker.session_file.write_text(
                json.dumps(tracker.session_data, indent=2)
            )

            return tracker

    # ========================================
    # PROGRESS CALCULATION TESTS
    # ========================================

    def test_calculate_overall_progress_empty(self, tracker_with_session):
        """Test progress calculation with no agents."""
        progress = tracker_with_session.calculate_progress()

        assert progress == 0

    def test_calculate_overall_progress_partial(self, tracker_with_session):
        """Test progress calculation with some agents complete."""
        # Add 2 completed, 1 running, 4 pending = 2/7 ≈ 29%
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100},
            {"agent": "planner", "status": "completed", "duration_seconds": 100},
            {"agent": "test-master", "status": "started"}
        ]

        progress = tracker_with_session.calculate_progress()

        # 2 completed out of 7 expected = 28.57% ≈ 29%
        assert 28 <= progress <= 29

    def test_calculate_overall_progress_complete(self, tracker_with_session):
        """Test progress calculation when all agents complete."""
        all_agents = [
            "researcher", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master"
        ]

        tracker_with_session.session_data["agents"] = [
            {"agent": agent, "status": "completed", "duration_seconds": 100}
            for agent in all_agents
        ]

        progress = tracker_with_session.calculate_progress()

        assert progress == 100

    def test_calculate_progress_running_agent_partial_credit(self, tracker_with_session):
        """Test that running agents contribute partial progress."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100},
            {"agent": "planner", "status": "started"}  # Running = 50% credit
        ]

        progress = tracker_with_session.calculate_progress()

        # 1 complete + 0.5 running = 1.5 / 7 = 21.4%
        # Or if running doesn't count: 1 / 7 = 14.3%
        assert 14 <= progress <= 22

    def test_calculate_progress_with_failed_agent(self, tracker_with_session):
        """Test that failed agents count toward progress."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100},
            {"agent": "planner", "status": "failed", "duration_seconds": 50}
        ]

        progress = tracker_with_session.calculate_progress()

        # Both count as "done" = 2/7 = 28.6%
        assert 28 <= progress <= 29

    def test_get_expected_agents_list(self, tracker_with_session):
        """Test getting list of expected agents."""
        expected = tracker_with_session.get_expected_agents()

        assert len(expected) == 7
        assert "researcher" in expected
        assert "planner" in expected
        assert "test-master" in expected
        assert "implementer" in expected
        assert "reviewer" in expected
        assert "security-auditor" in expected
        assert "doc-master" in expected

    def test_get_expected_agents_order(self, tracker_with_session):
        """Test that expected agents are in execution order."""
        expected = tracker_with_session.get_expected_agents()

        # Should be in pipeline execution order
        assert expected.index("researcher") < expected.index("planner")
        assert expected.index("planner") < expected.index("test-master")
        assert expected.index("test-master") < expected.index("implementer")
        assert expected.index("implementer") < expected.index("reviewer")
        assert expected.index("reviewer") < expected.index("security-auditor")
        assert expected.index("security-auditor") < expected.index("doc-master")

    # ========================================
    # DISPLAY METADATA TESTS
    # ========================================

    def test_get_display_metadata_basic(self, tracker_with_session):
        """Test getting display metadata for agents."""
        tracker_with_session.session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "duration_seconds": 295,
                "message": "Found 5 patterns"
            }
        ]

        metadata = tracker_with_session.get_display_metadata()

        assert "agents" in metadata
        assert len(metadata["agents"]) > 0
        assert metadata["progress_percentage"] == 14  # 1/7

    def test_get_display_metadata_includes_pending(self, tracker_with_session):
        """Test that display metadata includes pending agents."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100}
        ]

        metadata = tracker_with_session.get_display_metadata()

        # Should include all 7 expected agents, even if not started
        assert len(metadata["agents"]) == 7

        # Find pending agents
        pending = [a for a in metadata["agents"] if a["status"] == "pending"]
        assert len(pending) == 6  # 7 total - 1 completed

    def test_get_display_metadata_agent_descriptions(self, tracker_with_session):
        """Test that agents have display-friendly descriptions."""
        metadata = tracker_with_session.get_display_metadata()

        # Each agent should have description
        for agent in metadata["agents"]:
            assert "description" in agent
            assert len(agent["description"]) > 0

        # Check specific descriptions
        researcher = next(a for a in metadata["agents"] if a["name"] == "researcher")
        assert "research" in researcher["description"].lower()

    def test_get_display_metadata_estimated_time(self, tracker_with_session):
        """Test estimated time remaining calculation."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 300},
            {"agent": "planner", "status": "completed", "duration_seconds": 200}
        ]

        metadata = tracker_with_session.get_display_metadata()

        # Should have estimated time remaining
        assert "estimated_time_remaining" in metadata
        # Should be > 0 since not all agents complete
        assert metadata["estimated_time_remaining"] > 0

    def test_get_display_metadata_estimated_time_complete(self, tracker_with_session):
        """Test estimated time when all agents complete."""
        all_agents = [
            "researcher", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master"
        ]

        tracker_with_session.session_data["agents"] = [
            {"agent": agent, "status": "completed", "duration_seconds": 100}
            for agent in all_agents
        ]

        metadata = tracker_with_session.get_display_metadata()

        # Should be 0 when complete
        assert metadata["estimated_time_remaining"] == 0

    def test_get_display_metadata_includes_status_emoji(self, tracker_with_session):
        """Test that display metadata includes status emojis."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100},
            {"agent": "planner", "status": "started"},
            {"agent": "test-master", "status": "failed", "error": "Test failed"}
        ]

        metadata = tracker_with_session.get_display_metadata()

        # Check emojis are assigned
        researcher = next(a for a in metadata["agents"] if a["name"] == "researcher")
        assert researcher["emoji"] == "✅"

        planner = next(a for a in metadata["agents"] if a["name"] == "planner")
        assert planner["emoji"] == "⏳"

        test_master = next(a for a in metadata["agents"] if a["name"] == "test-master")
        assert test_master["emoji"] == "❌"

        # Pending agents
        implementer = next(a for a in metadata["agents"] if a["name"] == "implementer")
        assert implementer["emoji"] in ["⏸️", "⬜"]

    # ========================================
    # TREE VIEW DATA TESTS
    # ========================================

    def test_get_tree_view_data(self, tracker_with_session):
        """Test getting data structured for tree view display."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 295},
            {"agent": "planner", "status": "started"}
        ]

        tree_data = tracker_with_session.get_tree_view_data()

        assert "agents" in tree_data
        assert "progress" in tree_data
        assert "github_issue" in tree_data

    def test_tree_view_data_agent_nesting(self, tracker_with_session):
        """Test tree view data shows agent hierarchy."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100}
        ]

        tree_data = tracker_with_session.get_tree_view_data()

        # Should have nested structure for display
        assert isinstance(tree_data["agents"], list)
        for agent in tree_data["agents"]:
            assert "name" in agent
            assert "status" in agent
            assert "indent_level" in agent or "level" in agent

    def test_tree_view_data_includes_tools(self, tracker_with_session):
        """Test tree view data includes tools used."""
        tracker_with_session.session_data["agents"] = [
            {
                "agent": "researcher",
                "status": "completed",
                "duration_seconds": 295,
                "tools_used": ["WebSearch", "Grep", "Read"]
            }
        ]

        tree_data = tracker_with_session.get_tree_view_data()

        researcher = tree_data["agents"][0]
        assert "tools" in researcher or "tools_used" in researcher
        tools = researcher.get("tools") or researcher.get("tools_used")
        assert "WebSearch" in tools

    # ========================================
    # TIME ESTIMATION TESTS
    # ========================================

    def test_estimate_remaining_time_no_data(self, tracker_with_session):
        """Test time estimation with no completed agents."""
        estimated = tracker_with_session.estimate_remaining_time()

        # Should return None or a default estimate
        assert estimated is None or estimated > 0

    def test_estimate_remaining_time_with_average(self, tracker_with_session):
        """Test time estimation based on average agent duration."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 300},
            {"agent": "planner", "status": "completed", "duration_seconds": 200}
        ]

        estimated = tracker_with_session.estimate_remaining_time()

        # Average = 250s, 5 agents remaining = 1250s
        assert 1000 <= estimated <= 1500

    def test_estimate_remaining_time_accounts_for_running(self, tracker_with_session):
        """Test that running agents are considered in estimation."""
        now = datetime.now()
        started = (now - timedelta(seconds=60)).isoformat()

        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 200},
            {"agent": "planner", "status": "started", "started_at": started}
        ]

        estimated = tracker_with_session.estimate_remaining_time()

        # Should account for time already spent on running agent
        assert estimated > 0

    def test_get_agent_average_duration(self, tracker_with_session):
        """Test calculating average agent duration."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 300},
            {"agent": "planner", "status": "completed", "duration_seconds": 200},
            {"agent": "test-master", "status": "completed", "duration_seconds": 100}
        ]

        avg = tracker_with_session.get_average_agent_duration()

        assert avg == 200  # (300 + 200 + 100) / 3

    def test_get_agent_average_duration_excludes_running(self, tracker_with_session):
        """Test that average only includes completed/failed agents."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 300},
            {"agent": "planner", "status": "started"},  # Should be excluded
            {"agent": "test-master", "status": "completed", "duration_seconds": 200}
        ]

        avg = tracker_with_session.get_average_agent_duration()

        assert avg == 250  # (300 + 200) / 2

    # ========================================
    # AGENT STATUS HELPERS TESTS
    # ========================================

    def test_is_pipeline_complete(self, tracker_with_session):
        """Test checking if pipeline is complete."""
        # Incomplete pipeline
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100}
        ]
        assert tracker_with_session.is_pipeline_complete() is False

        # Complete pipeline
        all_agents = [
            "researcher", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master"
        ]
        tracker_with_session.session_data["agents"] = [
            {"agent": agent, "status": "completed", "duration_seconds": 100}
            for agent in all_agents
        ]
        assert tracker_with_session.is_pipeline_complete() is True

    def test_is_pipeline_complete_with_failure(self, tracker_with_session):
        """Test that failed agents still count toward completion."""
        all_agents = [
            "researcher", "planner", "test-master", "implementer",
            "reviewer", "security-auditor", "doc-master"
        ]

        agents = []
        for i, agent in enumerate(all_agents):
            if i == 2:  # Fail test-master
                agents.append({"agent": agent, "status": "failed", "error": "Failed"})
            else:
                agents.append({"agent": agent, "status": "completed", "duration_seconds": 100})

        tracker_with_session.session_data["agents"] = agents

        # Pipeline is "complete" even with failure (all agents processed)
        assert tracker_with_session.is_pipeline_complete() is True

    def test_get_pending_agents(self, tracker_with_session):
        """Test getting list of agents not yet started."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100},
            {"agent": "planner", "status": "started"}
        ]

        pending = tracker_with_session.get_pending_agents()

        assert "researcher" not in pending
        assert "planner" not in pending
        assert "test-master" in pending
        assert "implementer" in pending
        assert len(pending) == 5  # 7 total - 2 started

    def test_get_running_agent(self, tracker_with_session):
        """Test getting currently running agent."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100},
            {"agent": "planner", "status": "started"}
        ]

        running = tracker_with_session.get_running_agent()

        assert running == "planner"

    def test_get_running_agent_none(self, tracker_with_session):
        """Test getting running agent when none are running."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "completed", "duration_seconds": 100}
        ]

        running = tracker_with_session.get_running_agent()

        assert running is None

    def test_get_running_agent_multiple(self, tracker_with_session):
        """Test getting running agent when multiple marked as running (error case)."""
        tracker_with_session.session_data["agents"] = [
            {"agent": "researcher", "status": "started"},
            {"agent": "planner", "status": "started"}
        ]

        running = tracker_with_session.get_running_agent()

        # Should return most recent one
        assert running in ["researcher", "planner"]

    # ========================================
    # DISPLAY FORMATTING TESTS
    # ========================================

    def test_format_agent_name_display(self, tracker_with_session):
        """Test formatting agent names for display."""
        # Should convert test-master -> Test Master
        formatted = tracker_with_session.format_agent_name("test-master")
        assert formatted == "Test Master" or formatted == "test-master"

        formatted = tracker_with_session.format_agent_name("security-auditor")
        assert "Security" in formatted or "security" in formatted

    def test_get_agent_emoji(self, tracker_with_session):
        """Test getting appropriate emoji for agent status."""
        assert tracker_with_session.get_agent_emoji("completed") == "✅"
        assert tracker_with_session.get_agent_emoji("started") == "⏳"
        assert tracker_with_session.get_agent_emoji("failed") == "❌"
        assert tracker_with_session.get_agent_emoji("pending") in ["⏸️", "⬜"]

    def test_get_agent_color(self, tracker_with_session):
        """Test getting appropriate color for agent status (for colored output)."""
        # Should return ANSI color codes or color names
        completed_color = tracker_with_session.get_agent_color("completed")
        assert completed_color in ["green", "\033[92m", "32"]

        failed_color = tracker_with_session.get_agent_color("failed")
        assert failed_color in ["red", "\033[91m", "31"]

    # ========================================
    # GITHUB ISSUE INTEGRATION TESTS
    # ========================================

    def test_display_metadata_includes_github_issue(self, tracker_with_session):
        """Test that display metadata includes GitHub issue link."""
        tracker_with_session.session_data["github_issue"] = 42

        metadata = tracker_with_session.get_display_metadata()

        assert metadata["github_issue"] == 42

    def test_display_metadata_github_issue_url(self, tracker_with_session):
        """Test formatting GitHub issue as URL."""
        tracker_with_session.session_data["github_issue"] = 42

        metadata = tracker_with_session.get_display_metadata()

        # Should provide URL or issue number
        assert "github_issue" in metadata
        # Optionally provide full URL
        if "github_issue_url" in metadata:
            assert "github.com" in metadata["github_issue_url"]
            assert "42" in metadata["github_issue_url"]

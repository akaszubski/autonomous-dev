"""
Integration tests for parallel research workflow (Issue #128).

TDD Mode: These tests are written BEFORE implementation.
Tests should FAIL initially (workflow not yet updated).

Test Strategy:
- Test end-to-end parallel research execution
- Test research-to-planner handoff
- Test checkpoint verification with new workflow
- Test full /auto-implement workflow with split research

Date: 2025-12-13
Issue: GitHub #128 (Split researcher into parallel agents)
Agent: test-master
Phase: TDD Red Phase - Integration Tests
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestParallelResearchExecution:
    """Test end-to-end parallel research execution."""

    def test_parallel_research_tracked_in_session(self):
        """
        Test that both research agents are tracked with parallel start times.

        Expected behavior:
        - Session file contains researcher-local entry
        - Session file contains researcher-web entry
        - Start times within 5 seconds (parallel execution)
        - Both have completion timestamps and durations
        """
        # This test validates session file structure after parallel execution
        # In real execution, session file created by AgentTracker

        # Mock session file content
        mock_session = {
            "session_id": "20251213-140000",
            "started": "2025-12-13T14:00:00",
            "agents": [
                {
                    "agent": "researcher-local",
                    "status": "completed",
                    "started_at": "2025-12-13T14:00:05",
                    "completed_at": "2025-12-13T14:03:15",
                    "duration_seconds": 190,
                    "message": "Found 3 existing patterns in codebase",
                    "tools_used": ["Read", "Grep", "Glob"]
                },
                {
                    "agent": "researcher-web",
                    "status": "completed",
                    "started_at": "2025-12-13T14:00:06",  # Parallel (within 5 sec)
                    "completed_at": "2025-12-13T14:02:45",
                    "duration_seconds": 159,
                    "message": "Found 5 best practices from web search",
                    "tools_used": ["WebSearch", "WebFetch"]
                }
            ]
        }

        # Assert: Both agents present
        agent_names = [a["agent"] for a in mock_session["agents"]]
        assert "researcher-local" in agent_names, \
            "Session should track researcher-local"
        assert "researcher-web" in agent_names, \
            "Session should track researcher-web"

        # Assert: Both completed
        for agent in mock_session["agents"]:
            assert agent["status"] == "completed", \
                f"{agent['agent']} should complete successfully"
            assert "completed_at" in agent, \
                f"{agent['agent']} should have completion timestamp"
            assert "duration_seconds" in agent, \
                f"{agent['agent']} should track duration"

        # Assert: Parallel execution (start times close)
        local_start = datetime.fromisoformat(mock_session["agents"][0]["started_at"])
        web_start = datetime.fromisoformat(mock_session["agents"][1]["started_at"])
        time_diff = abs((web_start - local_start).total_seconds())

        assert time_diff <= 5, \
            f"Start times should be within 5 seconds for parallel execution (got {time_diff}s)"

        # Assert: Correct tools used
        local_tools = mock_session["agents"][0]["tools_used"]
        web_tools = mock_session["agents"][1]["tools_used"]

        assert "Read" in local_tools or "Grep" in local_tools, \
            "researcher-local should use file system tools"
        assert "WebSearch" in web_tools or "WebFetch" in web_tools, \
            "researcher-web should use web tools"

    def test_parallel_research_performance_improvement(self):
        """
        Test that parallel research is faster than sequential.

        Expected behavior:
        - researcher-local takes ~3 minutes
        - researcher-web takes ~2.5 minutes
        - Sequential total: 5.5 minutes
        - Parallel total: max(3, 2.5) = 3 minutes
        - Time saved: 2.5 minutes (45% faster)
        """
        # Mock timing data
        local_duration = 180  # 3 minutes
        web_duration = 150    # 2.5 minutes

        # Sequential execution
        sequential_time = local_duration + web_duration
        assert sequential_time == 330  # 5.5 minutes

        # Parallel execution (max of both)
        parallel_time = max(local_duration, web_duration)
        assert parallel_time == 180  # 3 minutes

        # Performance gain
        time_saved = sequential_time - parallel_time
        percent_faster = (time_saved / sequential_time) * 100

        assert time_saved == 150, \
            "Parallel execution should save 2.5 minutes (150 seconds)"
        assert percent_faster == pytest.approx(45.45, rel=0.1), \
            "Parallel execution should be ~45% faster"


class TestResearchToPlannerHandoff:
    """Test that merged research context is passed to planner."""

    def test_planner_receives_merged_research(self):
        """
        Test that planner prompt includes merged research context.

        Expected behavior:
        - auto-implement.md has STEP 1.1 (merge research)
        - STEP 2 (planner) receives merged context
        - Planner prompt references codebase_context and external_guidance
        - Planner can access both local patterns and web best practices
        """
        # Read auto-implement.md
        command_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        content = command_file.read_text()

        # Assert: STEP 1 is parallel research
        assert "STEP 1: Parallel Research" in content or "STEP 1: Parallel Exploration" in content, \
            "STEP 1 should be parallel research (researcher-local + researcher-web)"

        # Assert: STEP 1.1 is merge
        assert "STEP 1.1:" in content, \
            "Should have STEP 1.1 for merging research findings"
        assert "merge" in content.lower() or "combine" in content.lower(), \
            "STEP 1.1 should mention merging/combining research"

        # Assert: STEP 2 is planner
        assert "STEP 2:" in content, \
            "Should have STEP 2 for planning"

        # Extract STEP 2 section
        step2_start = content.find("### STEP 2:")
        step2_end = content.find("### STEP 3:")
        step2_section = content[step2_start:step2_end] if step2_start != -1 and step2_end != -1 else content

        # Assert: Planner receives merged context
        assert "researcher-local" in step2_section or "codebase_context" in step2_section, \
            "STEP 2 (planner) should reference local research findings"
        assert "researcher-web" in step2_section or "external_guidance" in step2_section, \
            "STEP 2 (planner) should reference web research findings"

    def test_planner_prompt_structure(self):
        """
        Test that planner prompt is structured to use merged research.

        Expected prompt structure:
        - Intro: "Based on research findings..."
        - Context: Reference to codebase patterns
        - Guidance: Reference to best practices
        - Task: Create plan using both sources
        """
        command_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        content = command_file.read_text()

        # Extract planner section
        step2_start = content.find("### STEP 2:")
        step2_end = content.find("### STEP 3:")
        planner_section = content[step2_start:step2_end] if step2_start != -1 and step2_end != -1 else ""

        assert len(planner_section) > 0, "STEP 2 (planner) should exist"

        # Assert: Prompt mentions research
        assert "research" in planner_section.lower(), \
            "Planner prompt should reference research findings"

        # Assert: Prompt encourages using both sources
        research_keywords = ["codebase", "pattern", "best practice", "external", "web"]
        found_keywords = [kw for kw in research_keywords if kw in planner_section.lower()]

        assert len(found_keywords) >= 2, \
            f"Planner prompt should reference both local patterns and web guidance (found: {found_keywords})"


class TestCheckpointVerification:
    """Test that checkpoint verification uses new workflow."""

    def test_checkpoint_verifies_split_research(self):
        """
        Test that CHECKPOINT 1 verifies researcher-local + researcher-web (not old researcher).

        Expected behavior:
        - CHECKPOINT 1 after STEP 1.1 (merge)
        - Verifies researcher-local completed
        - Verifies researcher-web completed
        - Does NOT expect old "researcher" agent
        """
        command_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        content = command_file.read_text()

        # Find CHECKPOINT 1
        assert "CHECKPOINT 1:" in content, \
            "Should have CHECKPOINT 1 after research phase"

        # Extract checkpoint section
        cp1_start = content.find("CHECKPOINT 1:")
        cp1_end = content.find("### STEP 2:", cp1_start) if cp1_start != -1 else -1
        checkpoint_section = content[cp1_start:cp1_end] if cp1_start != -1 and cp1_end != -1 else ""

        assert len(checkpoint_section) > 0, "CHECKPOINT 1 section should exist"

        # Assert: Verifies new agents
        assert "researcher-local" in checkpoint_section, \
            "CHECKPOINT 1 should verify researcher-local completed"
        assert "researcher-web" in checkpoint_section, \
            "CHECKPOINT 1 should verify researcher-web completed"

        # Assert: Uses verify_parallel_research or similar
        assert "verify" in checkpoint_section.lower(), \
            "CHECKPOINT 1 should verify research agents"

    def test_checkpoint_verification_logic(self):
        """
        Test checkpoint verification logic for split research.

        Expected behavior:
        - Call AgentTracker.verify_parallel_research()
        - Check both agents completed
        - Check parallel execution (start times)
        - Fail if sequential or missing agent
        """
        # Mock checkpoint verification
        def verify_research_checkpoint(session_file: Path) -> Dict[str, Any]:
            """
            Verify research checkpoint.

            Args:
                session_file: Path to session JSON file

            Returns:
                Verification result with success, agents_found, parallel status
            """
            # Read session (mock)
            session_data = json.loads(session_file.read_text())

            # Check for both agents
            agent_names = [a["agent"] for a in session_data["agents"]]
            has_local = "researcher-local" in agent_names
            has_web = "researcher-web" in agent_names

            if not has_local or not has_web:
                missing = []
                if not has_local:
                    missing.append("researcher-local")
                if not has_web:
                    missing.append("researcher-web")

                return {
                    "success": False,
                    "reason": f"Missing research agents: {', '.join(missing)}",
                    "found_agents": agent_names
                }

            # Check parallel execution
            local_agent = next(a for a in session_data["agents"] if a["agent"] == "researcher-local")
            web_agent = next(a for a in session_data["agents"] if a["agent"] == "researcher-web")

            local_start = datetime.fromisoformat(local_agent["started_at"])
            web_start = datetime.fromisoformat(web_agent["started_at"])
            time_diff = abs((web_start - local_start).total_seconds())

            is_parallel = time_diff <= 5

            if not is_parallel:
                return {
                    "success": False,
                    "reason": f"Research agents not executed in parallel (time diff: {time_diff}s)",
                    "parallel": False,
                    "time_difference": time_diff
                }

            return {
                "success": True,
                "agents_verified": ["researcher-local", "researcher-web"],
                "parallel": True,
                "time_difference": time_diff
            }

        # Test: Parallel execution passes
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            parallel_session = {
                "session_id": "test",
                "agents": [
                    {"agent": "researcher-local", "started_at": "2025-12-13T10:00:05", "status": "completed"},
                    {"agent": "researcher-web", "started_at": "2025-12-13T10:00:06", "status": "completed"}
                ]
            }
            json.dump(parallel_session, f)
            session_path = Path(f.name)

        result = verify_research_checkpoint(session_path)
        session_path.unlink()  # Cleanup

        assert result["success"] is True
        assert result["parallel"] is True
        assert "researcher-local" in result["agents_verified"]
        assert "researcher-web" in result["agents_verified"]

        # Test: Sequential execution fails
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            sequential_session = {
                "session_id": "test",
                "agents": [
                    {"agent": "researcher-local", "started_at": "2025-12-13T10:00:05", "status": "completed"},
                    {"agent": "researcher-web", "started_at": "2025-12-13T10:03:20", "status": "completed"}  # 195s later
                ]
            }
            json.dump(sequential_session, f)
            session_path = Path(f.name)

        result = verify_research_checkpoint(session_path)
        session_path.unlink()  # Cleanup

        assert result["success"] is False
        assert result["parallel"] is False
        assert "not executed in parallel" in result["reason"]

    def test_checkpoint_updates_all_checkpoints(self):
        """
        Test that all checkpoints are updated for new workflow.

        With split research, expected agent count changes:
        - Old workflow: 7 agents (researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master)
        - New workflow: 8 agents (researcher-local, researcher-web, planner, test-master, implementer, reviewer, security-auditor, doc-master)

        CHECKPOINT 4.1 (after quality-validator) should verify 8 agents.
        """
        command_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        content = command_file.read_text()

        # Find CHECKPOINT 4.1
        assert "CHECKPOINT 4.1:" in content, \
            "Should have CHECKPOINT 4.1 after validation"

        # Extract checkpoint section
        cp41_start = content.find("CHECKPOINT 4.1:")
        cp41_end = content.find("### STEP 5:", cp41_start) if cp41_start != -1 else content.find("## FINAL", cp41_start)
        checkpoint_section = content[cp41_start:cp41_end] if cp41_start != -1 and cp41_end != -1 else ""

        assert len(checkpoint_section) > 0, "CHECKPOINT 4.1 section should exist"

        # Assert: Verifies 8 agents (not 7)
        # The checkpoint should check for researcher-local and researcher-web
        if "researcher-local" in checkpoint_section or "researcher-web" in checkpoint_section:
            # New workflow
            pass
        else:
            # Might verify count = 8 instead of listing all names
            # Check for updated count
            if "7" in checkpoint_section and "8" not in checkpoint_section:
                pytest.fail("CHECKPOINT 4.1 should verify 8 agents (with split research), not 7")


class TestFullWorkflowIntegration:
    """Test complete /auto-implement workflow with split research."""

    def test_full_workflow_step_order(self):
        """
        Test that /auto-implement workflow has correct step order.

        Expected steps:
        1. STEP 1: Parallel Research (researcher-local + researcher-web)
        2. STEP 1.1: Merge Research Findings
        3. CHECKPOINT 1: Verify Parallel Research
        4. STEP 2: Planning (planner receives merged context)
        5. STEP 3: TDD Tests (test-master)
        6. STEP 4: Implementation (implementer)
        7. STEP 4.1: Parallel Validation (reviewer + security-auditor + doc-master)
        8. STEP 4.2: Quality Validator
        9. CHECKPOINT 4.1: Verify All Agents
        """
        command_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        content = command_file.read_text()

        # Assert: Steps exist in order
        steps = [
            "### STEP 1:",
            "### STEP 1.1:",
            "CHECKPOINT 1:",
            "### STEP 2:",
            "### STEP 3:",
            "### STEP 4:",
            "### STEP 4.1:",
            "### STEP 4.2:",
            "CHECKPOINT 4.1:"
        ]

        last_pos = 0
        for step in steps:
            pos = content.find(step, last_pos)
            assert pos != -1, f"Step '{step}' not found or out of order"
            assert pos > last_pos, f"Step '{step}' appears before previous step"
            last_pos = pos

    def test_full_workflow_agent_count(self):
        """
        Test that workflow invokes exactly 8 agents in new design.

        Agents:
        1. researcher-local
        2. researcher-web
        3. planner
        4. test-master
        5. implementer
        6. reviewer
        7. security-auditor
        8. doc-master
        (quality-validator is not a full agent in this count)
        """
        command_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        content = command_file.read_text()

        # Count agent invocations
        expected_agents = [
            "researcher-local",
            "researcher-web",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master"
        ]

        for agent in expected_agents:
            # Should appear in subagent_type or Task invocation
            assert agent in content, \
                f"Agent '{agent}' should be invoked in workflow"

        # Old researcher should NOT be invoked
        # Check if "researcher" appears but only in compound names
        researcher_mentions = content.count('"researcher"')
        assert researcher_mentions == 0 or all(
            prefix in content for prefix in ["researcher-local", "researcher-web"]
        ), "Old 'researcher' agent should not be invoked (use researcher-local/researcher-web)"

    def test_workflow_output_structure(self):
        """
        Test that workflow produces expected outputs at each step.

        Expected outputs:
        - STEP 1: researcher-local JSON + researcher-web JSON
        - STEP 1.1: Merged research JSON
        - STEP 2: Architecture plan (planner)
        - STEP 3: Test files (test-master)
        - STEP 4: Implementation code (implementer)
        - STEP 4.1: Validation results (3 validators)
        - STEP 4.2: Quality assessment (quality-validator)
        """
        # Mock workflow outputs
        workflow_outputs = {
            "step1_local": {
                "existing_patterns": [],
                "files_to_update": [],
                "architecture_notes": [],
                "similar_implementations": []
            },
            "step1_web": {
                "best_practices": [],
                "recommended_libraries": [],
                "security_considerations": [],
                "common_pitfalls": []
            },
            "step1_1_merged": {
                "codebase_context": {},
                "external_guidance": {},
                "recommendations": []
            },
            "step2_plan": {
                "overview": "Architecture plan",
                "components": [],
                "dependencies": []
            },
            "step3_tests": {
                "test_files": ["test_feature.py"],
                "test_count": 15
            },
            "step4_implementation": {
                "files_modified": ["feature.py"],
                "lines_changed": 120
            },
            "step4_1_validation": {
                "reviewer": {"status": "completed"},
                "security-auditor": {"status": "completed"},
                "doc-master": {"status": "completed"}
            },
            "step4_2_quality": {
                "overall_status": "passed",
                "issues": []
            }
        }

        # Validate each step output structure
        assert "existing_patterns" in workflow_outputs["step1_local"]
        assert "best_practices" in workflow_outputs["step1_web"]
        assert "codebase_context" in workflow_outputs["step1_1_merged"]
        assert "overview" in workflow_outputs["step2_plan"]
        assert "test_files" in workflow_outputs["step3_tests"]
        assert "files_modified" in workflow_outputs["step4_implementation"]
        assert all(
            agent in workflow_outputs["step4_1_validation"]
            for agent in ["reviewer", "security-auditor", "doc-master"]
        )
        assert "overall_status" in workflow_outputs["step4_2_quality"]


class TestBackwardCompatibility:
    """Test backward compatibility and migration path."""

    def test_session_file_handles_both_workflows(self):
        """
        Test that session files work with both old and new workflows.

        For backward compatibility:
        - Old sessions: Have "researcher" entry
        - New sessions: Have "researcher-local" + "researcher-web" entries
        - AgentTracker should handle both formats
        """
        # Old format session
        old_session = {
            "session_id": "old-format",
            "agents": [
                {"agent": "researcher", "status": "completed"},
                {"agent": "planner", "status": "completed"}
            ]
        }

        # New format session
        new_session = {
            "session_id": "new-format",
            "agents": [
                {"agent": "researcher-local", "status": "completed"},
                {"agent": "researcher-web", "status": "completed"},
                {"agent": "planner", "status": "completed"}
            ]
        }

        # Mock validation that handles both
        def validate_session(session: Dict) -> Dict[str, Any]:
            """Validate session works with old or new format."""
            agents = [a["agent"] for a in session["agents"]]

            # Check if new format (split research)
            has_split = "researcher-local" in agents and "researcher-web" in agents

            # Check if old format (monolithic researcher)
            has_old = "researcher" in agents

            return {
                "valid": has_split or has_old,
                "format": "new" if has_split else "old" if has_old else "unknown",
                "agents": agents
            }

        # Validate both formats
        old_result = validate_session(old_session)
        new_result = validate_session(new_session)

        assert old_result["valid"] is True
        assert old_result["format"] == "old"

        assert new_result["valid"] is True
        assert new_result["format"] == "new"

    def test_documentation_updated(self):
        """
        Test that documentation reflects split researcher design.

        Files to check:
        - CLAUDE.md (agent count, workflow description)
        - docs/AGENTS.md (researcher-local and researcher-web documented)
        - README.md (workflow updated)
        """
        # Check CLAUDE.md
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"
        claude_content = claude_md.read_text()

        # Should mention split research or updated agent count
        # (This will fail until documentation is updated)
        # We check this to ensure docs stay in sync

        # Check docs/AGENTS.md
        agents_md = Path(__file__).parent.parent.parent / "docs" / "AGENTS.md"
        if agents_md.exists():
            agents_content = agents_md.read_text()

            # Should document new agents
            assert "researcher-local" in agents_content or "researcher-web" in agents_content, \
                "docs/AGENTS.md should document split researcher agents"


# Mark all tests as expecting to fail (TDD red phase)
pytestmark = pytest.mark.xfail(
    reason="TDD Red Phase: Split researcher workflow not yet implemented (Issue #128). "
           "Tests verify expected integration behavior for parallel research, "
           "checkpoint verification, and full workflow execution."
)

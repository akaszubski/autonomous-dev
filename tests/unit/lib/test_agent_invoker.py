#!/usr/bin/env python3
"""
Unit tests for agent_invoker.py.

Tests the unified agent invocation factory pattern including:
- AgentInvoker class
- AGENT_CONFIGS mapping
- invoke() method
- _build_prompt() method
- invoke_with_task_tool() method

Issue: #234 (Test coverage improvement)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from plugins.autonomous_dev.lib.agent_invoker import AgentInvoker


class TestAgentConfigs:
    """Test AGENT_CONFIGS mapping."""

    def test_all_required_agents_exist(self):
        """All required pipeline agents should exist."""
        required_agents = [
            'alignment-validator',
            'researcher',
            'planner',
            'test-master',
            'implementer',
            'reviewer',
            'security-auditor',
            'doc-master',
        ]
        for agent in required_agents:
            assert agent in AgentInvoker.AGENT_CONFIGS, f"Missing agent: {agent}"

    def test_agent_configs_have_required_fields(self):
        """Each agent config should have required fields."""
        for agent_name, config in AgentInvoker.AGENT_CONFIGS.items():
            assert 'progress_pct' in config, f"{agent_name} missing progress_pct"
            assert 'artifacts_required' in config, f"{agent_name} missing artifacts_required"
            assert 'description_template' in config, f"{agent_name} missing description_template"
            assert 'mission' in config, f"{agent_name} missing mission"

    def test_progress_percentages_ordered(self):
        """Progress percentages should increase through pipeline."""
        pipeline_order = [
            'alignment-validator',
            'researcher',
            'planner',
            'test-master',
            'implementer',
            'reviewer',
            'security-auditor',
            'doc-master',
        ]
        prev_pct = 0
        for agent in pipeline_order:
            current_pct = AgentInvoker.AGENT_CONFIGS[agent]['progress_pct']
            assert current_pct >= prev_pct, f"{agent} has lower progress than previous"
            prev_pct = current_pct

    def test_artifacts_required_is_list(self):
        """artifacts_required should be a list."""
        for agent_name, config in AgentInvoker.AGENT_CONFIGS.items():
            assert isinstance(config['artifacts_required'], list)

    def test_description_template_has_placeholder(self):
        """description_template should have {request} placeholder."""
        for agent_name, config in AgentInvoker.AGENT_CONFIGS.items():
            assert '{request}' in config['description_template'], \
                f"{agent_name} description_template missing {{request}} placeholder"


class TestAgentInvokerInit:
    """Test AgentInvoker initialization."""

    def test_init_with_artifact_manager(self):
        """Initialize with artifact manager."""
        mock_manager = MagicMock()
        invoker = AgentInvoker(artifact_manager=mock_manager)
        assert invoker.artifact_manager == mock_manager


class TestAgentInvokerInvoke:
    """Test AgentInvoker.invoke() method."""

    @pytest.fixture
    def mock_artifact_manager(self):
        """Create mock artifact manager."""
        manager = MagicMock()
        manager.read_artifact.return_value = {"request": "Test feature"}
        return manager

    @pytest.fixture
    def invoker(self, mock_artifact_manager):
        """Create invoker with mock manager."""
        return AgentInvoker(artifact_manager=mock_artifact_manager)

    def test_invoke_unknown_agent_raises(self, invoker):
        """Invoke unknown agent raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent"):
            invoker.invoke("nonexistent-agent", "wf-123")

    def test_invoke_returns_dict(self, invoker):
        """Invoke returns dict with required keys."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke(
                agent_name="researcher",
                workflow_id="wf-123",
                request="Test feature"
            )

        assert isinstance(result, dict)
        assert 'subagent_type' in result
        assert 'description' in result
        assert 'prompt' in result

    def test_invoke_subagent_type_matches(self, invoker):
        """Invoke returns correct subagent_type."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke(
                agent_name="implementer",
                workflow_id="wf-123",
                request="Build a thing"
            )

        assert result['subagent_type'] == "implementer"

    def test_invoke_description_formatted(self, invoker):
        """Invoke formats description with request."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke(
                agent_name="planner",
                workflow_id="wf-123",
                request="authentication system"
            )

        assert "authentication system" in result['description']

    def test_invoke_reads_required_artifacts(self, invoker, mock_artifact_manager):
        """Invoke reads required artifacts."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            invoker.invoke(
                agent_name="implementer",
                workflow_id="wf-123",
                request="Build something"
            )

        # Implementer requires manifest, architecture, tests
        calls = mock_artifact_manager.read_artifact.call_args_list
        artifact_types = [call.kwargs.get('artifact_type') or call[1].get('artifact_type')
                        for call in calls]
        assert 'manifest' in artifact_types

    def test_invoke_handles_missing_artifacts(self, invoker, mock_artifact_manager):
        """Invoke handles missing artifacts gracefully."""
        mock_artifact_manager.read_artifact.side_effect = FileNotFoundError("Not found")

        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            # Should not raise
            result = invoker.invoke(
                agent_name="reviewer",
                workflow_id="wf-123",
                request="Review code"
            )

        assert result is not None

    @patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger')
    @patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker')
    def test_invoke_logs_event(self, mock_tracker, mock_logger, invoker):
        """Invoke logs agent invocation event."""
        invoker.invoke(
            agent_name="doc-master",
            workflow_id="wf-123",
            request="Update docs"
        )

        mock_logger.return_value.log_event.assert_called()

    @patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger')
    @patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker')
    def test_invoke_updates_progress(self, mock_tracker, mock_logger, invoker):
        """Invoke updates progress tracker."""
        invoker.invoke(
            agent_name="security-auditor",
            workflow_id="wf-123",
            request="Security scan"
        )

        mock_tracker.return_value.update_progress.assert_called()


class TestAgentInvokerBuildPrompt:
    """Test AgentInvoker._build_prompt() method."""

    @pytest.fixture
    def invoker(self):
        """Create invoker with mock manager."""
        mock_manager = MagicMock()
        return AgentInvoker(artifact_manager=mock_manager)

    def test_build_prompt_includes_mission(self, invoker):
        """Prompt includes agent mission."""
        prompt = invoker._build_prompt(
            agent_name="implementer",
            workflow_id="wf-123",
            artifacts={},
            context={"request": "Build feature"}
        )

        mission = AgentInvoker.AGENT_CONFIGS["implementer"]["mission"]
        assert mission in prompt

    def test_build_prompt_includes_request(self, invoker):
        """Prompt includes request."""
        prompt = invoker._build_prompt(
            agent_name="researcher",
            workflow_id="wf-123",
            artifacts={},
            context={"request": "Authentication system"}
        )

        assert "Authentication system" in prompt

    def test_build_prompt_includes_workflow_id(self, invoker):
        """Prompt includes workflow ID."""
        prompt = invoker._build_prompt(
            agent_name="planner",
            workflow_id="wf-abc-123",
            artifacts={},
            context={"request": "Test"}
        )

        assert "wf-abc-123" in prompt

    def test_build_prompt_lists_artifacts(self, invoker):
        """Prompt lists available artifacts."""
        prompt = invoker._build_prompt(
            agent_name="reviewer",
            workflow_id="wf-123",
            artifacts={"manifest": {}, "implementation": {}},
            context={"request": "Review"}
        )

        assert "manifest" in prompt
        assert "implementation" in prompt

    def test_build_prompt_extracts_request_from_manifest(self, invoker):
        """Prompt extracts request from manifest artifact."""
        prompt = invoker._build_prompt(
            agent_name="test-master",
            workflow_id="wf-123",
            artifacts={"manifest": {"request": "Manifest request"}},
            context={}  # No request in context
        )

        assert "Manifest request" in prompt


class TestAgentInvokerInvokeWithTaskTool:
    """Test AgentInvoker.invoke_with_task_tool() method."""

    @pytest.fixture
    def mock_artifact_manager(self):
        """Create mock artifact manager."""
        manager = MagicMock()
        manager.read_artifact.return_value = {"request": "Test"}
        return manager

    @pytest.fixture
    def invoker(self, mock_artifact_manager):
        """Create invoker with mock manager."""
        return AgentInvoker(artifact_manager=mock_artifact_manager)

    def test_invoke_with_task_tool_returns_dict(self, invoker):
        """invoke_with_task_tool returns dict."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke_with_task_tool(
                agent_name="researcher",
                workflow_id="wf-123",
                request="Research something"
            )

        assert isinstance(result, dict)

    def test_invoke_with_task_tool_has_flag(self, invoker):
        """invoke_with_task_tool sets task_tool_enabled flag."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke_with_task_tool(
                agent_name="researcher",
                workflow_id="wf-123",
                request="Research something"
            )

        assert result.get('task_tool_enabled') is True

    def test_invoke_with_task_tool_modifies_prompt(self, invoker):
        """invoke_with_task_tool adds task tool note to prompt."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke_with_task_tool(
                agent_name="researcher",
                workflow_id="wf-123",
                request="Research something"
            )

        assert "Task tool is enabled" in result['prompt']


class TestAllAgents:
    """Test all configured agents can be invoked."""

    @pytest.fixture
    def invoker(self):
        """Create invoker with mock manager."""
        mock_manager = MagicMock()
        mock_manager.read_artifact.return_value = {"request": "Test"}
        return AgentInvoker(artifact_manager=mock_manager)

    def test_invoke_alignment_validator(self, invoker):
        """Invoke alignment-validator agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("alignment-validator", "wf-123", request="Validate")
        assert result['subagent_type'] == "alignment-validator"

    def test_invoke_researcher(self, invoker):
        """Invoke researcher agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("researcher", "wf-123", request="Research")
        assert result['subagent_type'] == "researcher"

    def test_invoke_planner(self, invoker):
        """Invoke planner agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("planner", "wf-123", request="Plan")
        assert result['subagent_type'] == "planner"

    def test_invoke_test_master(self, invoker):
        """Invoke test-master agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("test-master", "wf-123", request="Test")
        assert result['subagent_type'] == "test-master"

    def test_invoke_implementer(self, invoker):
        """Invoke implementer agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("implementer", "wf-123", request="Implement")
        assert result['subagent_type'] == "implementer"

    def test_invoke_reviewer(self, invoker):
        """Invoke reviewer agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("reviewer", "wf-123", request="Review")
        assert result['subagent_type'] == "reviewer"

    def test_invoke_security_auditor(self, invoker):
        """Invoke security-auditor agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("security-auditor", "wf-123", request="Audit")
        assert result['subagent_type'] == "security-auditor"

    def test_invoke_doc_master(self, invoker):
        """Invoke doc-master agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("doc-master", "wf-123", request="Document")
        assert result['subagent_type'] == "doc-master"

    def test_invoke_commit_message_generator(self, invoker):
        """Invoke commit-message-generator agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("commit-message-generator", "wf-123", request="Commit")
        assert result['subagent_type'] == "commit-message-generator"

    def test_invoke_pr_description_generator(self, invoker):
        """Invoke pr-description-generator agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("pr-description-generator", "wf-123", request="PR")
        assert result['subagent_type'] == "pr-description-generator"

    def test_invoke_project_progress_tracker(self, invoker):
        """Invoke project-progress-tracker agent."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("project-progress-tracker", "wf-123", request="Track")
        assert result['subagent_type'] == "project-progress-tracker"


class TestEdgeCases:
    """Test edge cases."""

    @pytest.fixture
    def mock_artifact_manager(self):
        """Create mock artifact manager."""
        manager = MagicMock()
        manager.read_artifact.return_value = {}
        return manager

    @pytest.fixture
    def invoker(self, mock_artifact_manager):
        """Create invoker with mock manager."""
        return AgentInvoker(artifact_manager=mock_artifact_manager)

    def test_invoke_with_empty_request(self, invoker):
        """Invoke with empty request."""
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            result = invoker.invoke("researcher", "wf-123", request="")

        assert result is not None
        assert result['subagent_type'] == "researcher"

    def test_invoke_with_no_request_raises(self, invoker):
        """Invoke without request raises KeyError (request is required in context)."""
        # The description template requires {request}, so invoking without it raises KeyError
        with patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowLogger'), \
             patch('plugins.autonomous_dev.lib.agent_invoker.WorkflowProgressTracker'):
            with pytest.raises(KeyError, match="request"):
                invoker.invoke("planner", "wf-123")  # No request kwarg

    def test_build_prompt_no_request_anywhere(self, invoker):
        """Build prompt when request not in artifacts or context."""
        prompt = invoker._build_prompt(
            agent_name="implementer",
            workflow_id="wf-123",
            artifacts={},
            context={}
        )

        assert "No request specified" in prompt

    def test_error_message_lists_valid_agents(self, invoker):
        """Error message lists valid agents."""
        with pytest.raises(ValueError) as exc_info:
            invoker.invoke("fake-agent", "wf-123")

        assert "Valid agents:" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

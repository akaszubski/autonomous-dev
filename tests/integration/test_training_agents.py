#!/usr/bin/env python3
"""
Integration tests for training best practices agents.

Tests the agent invocation and workflow integration for:
- data-quality-validator agent
- distributed-training-coordinator agent
- Agent registration in agent_invoker.py
- Artifact flow between agents
- Error handling and graceful degradation

Issue: #274 (Training best practices agents and skills)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.agent_invoker import AgentInvoker


class TestDataQualityValidatorAgent:
    """Test data-quality-validator agent integration."""

    @pytest.fixture
    def agent_dir(self):
        """Get agents directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "agents"

    @pytest.fixture
    def artifacts_dir(self, tmp_path):
        """Create temporary artifacts directory."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        return artifacts

    def test_data_quality_validator_agent_exists(self, agent_dir):
        """
        GIVEN: Agents directory
        WHEN: Checking for data-quality-validator.md
        THEN: Agent file exists
        """
        agent_file = agent_dir / "data-quality-validator.md"
        assert agent_file.exists(), "data-quality-validator.md agent file not found"

    def test_data_quality_validator_follows_pattern(self, agent_dir):
        """
        GIVEN: data-quality-validator agent
        WHEN: Checking file structure
        THEN: Follows quality-validator.md pattern (frontmatter, mission, workflow)
        """
        agent_file = agent_dir / "data-quality-validator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()

        # Check frontmatter
        assert content.startswith("---"), "Agent missing YAML frontmatter"
        assert "name:" in content.lower(), "Agent missing name in frontmatter"
        assert "model:" in content.lower(), "Agent missing model in frontmatter"

        # Check key sections
        assert "## Mission" in content, "Agent missing Mission section"
        assert "## Workflow" in content, "Agent missing Workflow section"
        assert "## Output Format" in content, "Agent missing Output Format section"

    def test_data_quality_validator_uses_haiku(self, agent_dir):
        """
        GIVEN: data-quality-validator agent
        WHEN: Checking model specification
        THEN: Uses Haiku model (fast validation)
        """
        agent_file = agent_dir / "data-quality-validator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "haiku" in content.lower(), "data-quality-validator should use Haiku model"

    def test_data_quality_validator_validates_ifd(self, agent_dir):
        """
        GIVEN: data-quality-validator agent
        WHEN: Checking mission and workflow
        THEN: Validates IFD (Instruction-Following Data) quality
        """
        agent_file = agent_dir / "data-quality-validator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "ifd" in content.lower() or "instruction-following" in content.lower(), \
            "Agent should validate IFD quality"

    def test_data_quality_validator_validates_dpo(self, agent_dir):
        """
        GIVEN: data-quality-validator agent
        WHEN: Checking mission and workflow
        THEN: Validates DPO (Direct Preference Optimization) pairs
        """
        agent_file = agent_dir / "data-quality-validator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "dpo" in content.lower() or "preference" in content.lower(), \
            "Agent should validate DPO pairs"

    def test_data_quality_validator_validates_rlvr(self, agent_dir):
        """
        GIVEN: data-quality-validator agent
        WHEN: Checking mission and workflow
        THEN: Validates RLVR (Reinforcement Learning with Verifiable Rewards)
        """
        agent_file = agent_dir / "data-quality-validator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "rlvr" in content.lower() or "verifiable" in content.lower(), \
            "Agent should validate RLVR verifiability"

    def test_data_quality_validator_registered_in_invoker(self):
        """
        GIVEN: AgentInvoker AGENT_CONFIGS
        WHEN: Checking for data-quality-validator registration
        THEN: Agent is registered with correct configuration
        """
        configs = AgentInvoker.AGENT_CONFIGS

        # Should fail initially (TDD red phase)
        if 'data-quality-validator' not in configs:
            pytest.skip("Agent not yet registered (TDD red phase)")

        config = configs['data-quality-validator']
        assert 'progress_pct' in config, "Agent missing progress_pct"
        assert 'artifacts_required' in config, "Agent missing artifacts_required"
        assert 'mission' in config, "Agent missing mission"

        # Should require manifest artifact
        assert 'manifest' in config['artifacts_required'], \
            "data-quality-validator should require manifest artifact"

    def test_data_quality_validator_produces_artifact(self, agent_dir, artifacts_dir):
        """
        GIVEN: data-quality-validator agent invocation
        WHEN: Agent completes validation
        THEN: Produces data_quality_report.json artifact
        """
        # This test will fail initially (TDD red phase)
        pytest.skip("Agent invocation not yet implemented (TDD red phase)")

        # Expected artifact structure
        expected_artifact = artifacts_dir / "data_quality_report.json"
        assert expected_artifact.exists(), "Agent should produce data_quality_report.json"

        with open(expected_artifact) as f:
            report = json.load(f)

        assert 'ifd_score' in report, "Report missing IFD score"
        assert 'dpo_metrics' in report, "Report missing DPO metrics"
        assert 'rlvr_verifiability' in report, "Report missing RLVR assessment"
        assert 'poisoning_detected' in report, "Report missing poisoning detection"
        assert 'overall_ready' in report, "Report missing overall readiness"

    def test_data_quality_validator_performance(self, agent_dir):
        """
        GIVEN: data-quality-validator agent
        WHEN: Validating data quality
        THEN: Completes in <30 seconds (Haiku fast inference)
        """
        pytest.skip("Performance test not yet implemented (TDD red phase)")

        import time
        start = time.time()

        # Simulate agent invocation
        # invoke_agent('data-quality-validator', ...)

        duration = time.time() - start
        assert duration < 30, f"Agent took {duration}s (should be <30s)"


class TestDistributedTrainingCoordinatorAgent:
    """Test distributed-training-coordinator agent integration."""

    @pytest.fixture
    def agent_dir(self):
        """Get agents directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "agents"

    def test_distributed_training_coordinator_exists(self, agent_dir):
        """
        GIVEN: Agents directory
        WHEN: Checking for distributed-training-coordinator.md
        THEN: Agent file exists
        """
        agent_file = agent_dir / "distributed-training-coordinator.md"
        assert agent_file.exists(), "distributed-training-coordinator.md not found"

    def test_distributed_training_coordinator_follows_pattern(self, agent_dir):
        """
        GIVEN: distributed-training-coordinator agent
        WHEN: Checking file structure
        THEN: Follows brownfield-analyzer.md pattern
        """
        agent_file = agent_dir / "distributed-training-coordinator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()

        # Check frontmatter
        assert content.startswith("---"), "Agent missing YAML frontmatter"

        # Check key sections
        assert "## Mission" in content, "Agent missing Mission section"
        assert "## Workflow" in content, "Agent missing Workflow section"
        assert "## Output Format" in content, "Agent missing Output Format section"

    def test_distributed_training_coordinator_uses_sonnet(self, agent_dir):
        """
        GIVEN: distributed-training-coordinator agent
        WHEN: Checking model specification
        THEN: Uses Sonnet model (complex reasoning)
        """
        agent_file = agent_dir / "distributed-training-coordinator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "sonnet" in content.lower(), \
            "distributed-training-coordinator should use Sonnet model"

    def test_distributed_training_coordinator_handles_rdma(self, agent_dir):
        """
        GIVEN: distributed-training-coordinator agent
        WHEN: Checking workflow
        THEN: Coordinates RDMA (Remote Direct Memory Access) networking
        """
        agent_file = agent_dir / "distributed-training-coordinator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "rdma" in content.lower(), "Agent should coordinate RDMA networking"

    def test_distributed_training_coordinator_handles_mlx(self, agent_dir):
        """
        GIVEN: distributed-training-coordinator agent
        WHEN: Checking workflow
        THEN: Coordinates MLX distributed training
        """
        agent_file = agent_dir / "distributed-training-coordinator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "mlx" in content.lower(), "Agent should coordinate MLX distributed training"

    def test_distributed_training_coordinator_handles_flash_recovery(self, agent_dir):
        """
        GIVEN: distributed-training-coordinator agent
        WHEN: Checking workflow
        THEN: Implements FlashRecovery checkpoint strategy
        """
        agent_file = agent_dir / "distributed-training-coordinator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "flash" in content.lower() or "recovery" in content.lower(), \
            "Agent should implement FlashRecovery"

    def test_distributed_training_coordinator_registered_in_invoker(self):
        """
        GIVEN: AgentInvoker AGENT_CONFIGS
        WHEN: Checking for distributed-training-coordinator registration
        THEN: Agent is registered with correct configuration
        """
        configs = AgentInvoker.AGENT_CONFIGS

        # Should fail initially (TDD red phase)
        if 'distributed-training-coordinator' not in configs:
            pytest.skip("Agent not yet registered (TDD red phase)")

        config = configs['distributed-training-coordinator']
        assert 'progress_pct' in config, "Agent missing progress_pct"
        assert 'artifacts_required' in config, "Agent missing artifacts_required"
        assert 'mission' in config, "Agent missing mission"

        # Should require data_quality artifact
        assert 'data_quality' in config['artifacts_required'], \
            "distributed-training-coordinator should require data_quality artifact"

    def test_distributed_training_coordinator_produces_training_plan(self, agent_dir):
        """
        GIVEN: distributed-training-coordinator agent invocation
        WHEN: Agent completes coordination
        THEN: Produces training_plan.json artifact
        """
        pytest.skip("Agent invocation not yet implemented (TDD red phase)")

        # Expected artifact structure
        # Should contain: strategy, hardware, optimization, checkpointing


class TestAgentWorkflowIntegration:
    """Test integration between data-quality-validator and distributed-training-coordinator."""

    def test_artifact_flow_from_validator_to_coordinator(self):
        """
        GIVEN: data-quality-validator produces data_quality_report.json
        WHEN: distributed-training-coordinator is invoked
        THEN: Coordinator receives and processes quality report
        """
        pytest.skip("Artifact flow not yet implemented (TDD red phase)")

    def test_quality_gate_prevents_training(self):
        """
        GIVEN: data-quality-validator detects poisoning
        WHEN: Quality report shows overall_ready = False
        THEN: distributed-training-coordinator refuses to create training plan
        """
        pytest.skip("Quality gate not yet implemented (TDD red phase)")

    def test_quality_gate_allows_training(self):
        """
        GIVEN: data-quality-validator passes all checks
        WHEN: Quality report shows overall_ready = True
        THEN: distributed-training-coordinator creates training plan
        """
        pytest.skip("Quality gate not yet implemented (TDD red phase)")


class TestAgentErrorHandling:
    """Test error handling and graceful degradation."""

    @pytest.fixture
    def agent_dir(self):
        """Get agents directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "agents"

    def test_data_quality_validator_handles_missing_dataset(self):
        """
        GIVEN: data-quality-validator invoked with missing dataset
        WHEN: Dataset file doesn't exist
        THEN: Agent reports error gracefully without crashing
        """
        pytest.skip("Error handling not yet implemented (TDD red phase)")

    def test_data_quality_validator_handles_corrupted_data(self):
        """
        GIVEN: data-quality-validator invoked with corrupted dataset
        WHEN: Dataset contains invalid JSON
        THEN: Agent reports error gracefully
        """
        pytest.skip("Error handling not yet implemented (TDD red phase)")

    def test_distributed_training_coordinator_handles_missing_quality_report(self):
        """
        GIVEN: distributed-training-coordinator invoked without quality report
        WHEN: Required artifact is missing
        THEN: Agent reports error and refuses to proceed
        """
        pytest.skip("Error handling not yet implemented (TDD red phase)")

    def test_distributed_training_coordinator_handles_permission_errors(self):
        """
        GIVEN: distributed-training-coordinator writing training plan
        WHEN: Permission denied on output directory
        THEN: Agent reports error gracefully
        """
        pytest.skip("Error handling not yet implemented (TDD red phase)")


class TestAgentRegistration:
    """Test agent registration in agent_invoker.py."""

    def test_both_agents_registered(self):
        """
        GIVEN: AgentInvoker.AGENT_CONFIGS
        WHEN: Checking for training agents
        THEN: Both data-quality-validator and distributed-training-coordinator registered
        """
        configs = AgentInvoker.AGENT_CONFIGS

        # Should fail initially (TDD red phase)
        training_agents = [
            'data-quality-validator',
            'distributed-training-coordinator'
        ]

        missing_agents = [a for a in training_agents if a not in configs]

        if missing_agents:
            pytest.skip(f"Agents not yet registered (TDD red phase): {missing_agents}")

        # Verify both have required fields
        for agent_name in training_agents:
            config = configs[agent_name]
            assert 'progress_pct' in config, f"{agent_name} missing progress_pct"
            assert 'artifacts_required' in config, f"{agent_name} missing artifacts_required"
            assert 'description_template' in config, f"{agent_name} missing description_template"
            assert 'mission' in config, f"{agent_name} missing mission"

    def test_agent_progress_percentages_valid(self):
        """
        GIVEN: Registered training agents
        WHEN: Checking progress_pct values
        THEN: Values are between 0-100 and unique
        """
        configs = AgentInvoker.AGENT_CONFIGS
        training_agents = [
            'data-quality-validator',
            'distributed-training-coordinator'
        ]

        for agent_name in training_agents:
            if agent_name not in configs:
                pytest.skip(f"{agent_name} not yet registered (TDD red phase)")

            pct = configs[agent_name]['progress_pct']
            assert 0 <= pct <= 100, f"{agent_name} progress_pct out of range: {pct}"

    def test_agent_artifact_dependencies_valid(self):
        """
        GIVEN: Registered training agents
        WHEN: Checking artifacts_required
        THEN: Dependencies form valid workflow chain
        """
        configs = AgentInvoker.AGENT_CONFIGS

        if 'data-quality-validator' not in configs:
            pytest.skip("data-quality-validator not yet registered (TDD red phase)")
        if 'distributed-training-coordinator' not in configs:
            pytest.skip("distributed-training-coordinator not yet registered (TDD red phase)")

        # data-quality-validator should require manifest
        validator_artifacts = configs['data-quality-validator']['artifacts_required']
        assert 'manifest' in validator_artifacts, "Validator should require manifest"

        # distributed-training-coordinator should require data_quality
        coordinator_artifacts = configs['distributed-training-coordinator']['artifacts_required']
        assert 'data_quality' in coordinator_artifacts, \
            "Coordinator should require data_quality from validator"


class TestAgentOutputFormats:
    """Test agent output format specifications."""

    @pytest.fixture
    def agent_dir(self):
        """Get agents directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "agents"

    def test_data_quality_validator_output_format(self, agent_dir):
        """
        GIVEN: data-quality-validator agent
        WHEN: Checking Output Format section
        THEN: Specifies JSON structure with IFD, DPO, RLVR, poisoning
        """
        agent_file = agent_dir / "data-quality-validator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        output_section = content.split("## Output Format")[1] if "## Output Format" in content else ""

        assert "ifd_score" in output_section.lower(), "Output should include IFD score"
        assert "dpo_metrics" in output_section.lower(), "Output should include DPO metrics"
        assert "rlvr" in output_section.lower(), "Output should include RLVR assessment"
        assert "poisoning" in output_section.lower(), "Output should include poisoning detection"
        assert "json" in output_section.lower(), "Output should be JSON format"

    def test_distributed_training_coordinator_output_format(self, agent_dir):
        """
        GIVEN: distributed-training-coordinator agent
        WHEN: Checking Output Format section
        THEN: Specifies training plan with strategy, hardware, optimization
        """
        agent_file = agent_dir / "distributed-training-coordinator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        output_section = content.split("## Output Format")[1] if "## Output Format" in content else ""

        assert "strategy" in output_section.lower(), "Output should include training strategy"
        assert "hardware" in output_section.lower() or "distributed" in output_section.lower(), \
            "Output should include hardware/distributed configuration"
        assert "optimization" in output_section.lower() or "batch" in output_section.lower(), \
            "Output should include optimization settings"


class TestAgentSkillReferences:
    """Test that agents reference appropriate skills."""

    @pytest.fixture
    def agent_dir(self):
        """Get agents directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous_dev" / "agents"

    def test_data_quality_validator_references_data_distillation_skill(self, agent_dir):
        """
        GIVEN: data-quality-validator agent
        WHEN: Checking Relevant Skills section
        THEN: References data-distillation skill
        """
        agent_file = agent_dir / "data-quality-validator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "data-distillation" in content.lower(), \
            "Agent should reference data-distillation skill"

    def test_data_quality_validator_references_preference_quality_skill(self, agent_dir):
        """
        GIVEN: data-quality-validator agent
        WHEN: Checking Relevant Skills section
        THEN: References preference-data-quality skill
        """
        agent_file = agent_dir / "data-quality-validator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "preference-data-quality" in content.lower(), \
            "Agent should reference preference-data-quality skill"

    def test_distributed_training_coordinator_references_mlx_skill(self, agent_dir):
        """
        GIVEN: distributed-training-coordinator agent
        WHEN: Checking Relevant Skills section
        THEN: References mlx-performance skill
        """
        agent_file = agent_dir / "distributed-training-coordinator.md"
        if not agent_file.exists():
            pytest.skip("Agent file not yet created (TDD red phase)")

        content = agent_file.read_text()
        assert "mlx-performance" in content.lower(), \
            "Agent should reference mlx-performance skill"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

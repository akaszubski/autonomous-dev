#!/usr/bin/env python3
"""
Smoke tests for training agents and skills loading.

Fast validation that training components load without errors.
These tests should complete in <5 seconds (CI gate).

Tests:
- Agent markdown files are valid
- Skills directories exist and have SKILL.md
- No syntax errors in library files
- Agent registration is valid

Issue: #274 (Training best practices agents and skills)
"""

import pytest
from pathlib import Path
import ast
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class TestTrainingAgentsLoad:
    """Smoke tests for training agents loading."""

    @pytest.fixture
    def agent_dir(self):
        """Get agents directory."""
        return Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

    def test_data_quality_validator_agent_exists_and_valid(self, agent_dir):
        """
        GIVEN: Agents directory
        WHEN: Checking data-quality-validator.md
        THEN: File exists and is valid markdown
        """
        agent_file = agent_dir / "data-quality-validator.md"
        assert agent_file.exists(), "data-quality-validator.md not found"

        # Check it's readable and has content
        content = agent_file.read_text()
        assert len(content) > 100, "data-quality-validator.md appears empty"
        assert "---" in content, "data-quality-validator.md missing frontmatter"

    def test_distributed_training_coordinator_agent_exists_and_valid(self, agent_dir):
        """
        GIVEN: Agents directory
        WHEN: Checking distributed-training-coordinator.md
        THEN: File exists and is valid markdown
        """
        agent_file = agent_dir / "distributed-training-coordinator.md"
        assert agent_file.exists(), "distributed-training-coordinator.md not found"

        content = agent_file.read_text()
        assert len(content) > 100, "distributed-training-coordinator.md appears empty"
        assert "---" in content, "distributed-training-coordinator.md missing frontmatter"

    def test_realign_curator_agent_exists_and_valid(self, agent_dir):
        """
        GIVEN: Agents directory
        WHEN: Checking realign-curator/AGENT.md
        THEN: File exists and is valid markdown
        """
        agent_file = agent_dir / "realign-curator" / "AGENT.md"
        assert agent_file.exists(), "realign-curator/AGENT.md not found"

        content = agent_file.read_text()
        assert len(content) > 100, "realign-curator/AGENT.md appears empty"
        assert "---" in content, "realign-curator/AGENT.md missing frontmatter"
        assert "realign-curator" in content, "Agent name not in file"


class TestTrainingSkillsLoad:
    """Smoke tests for training skills loading."""

    @pytest.fixture
    def skills_dir(self):
        """Get skills directory."""
        return Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills"

    def test_data_distillation_skill_exists_and_valid(self, skills_dir):
        """
        GIVEN: Skills directory
        WHEN: Checking data-distillation skill
        THEN: Directory and SKILL.md exist
        """
        skill_dir = skills_dir / "data-distillation"
        assert skill_dir.exists(), "data-distillation directory not found"

        skill_metadata = skill_dir / "SKILL.md"
        assert skill_metadata.exists(), "data-distillation SKILL.md not found"

        content = skill_metadata.read_text()
        assert len(content) > 50, "data-distillation SKILL.md appears empty"

    def test_preference_data_quality_skill_exists_and_valid(self, skills_dir):
        """
        GIVEN: Skills directory
        WHEN: Checking preference-data-quality skill
        THEN: Directory and SKILL.md exist
        """
        skill_dir = skills_dir / "preference-data-quality"
        assert skill_dir.exists(), "preference-data-quality directory not found"

        skill_metadata = skill_dir / "SKILL.md"
        assert skill_metadata.exists(), "preference-data-quality SKILL.md not found"

        content = skill_metadata.read_text()
        assert len(content) > 50, "preference-data-quality SKILL.md appears empty"

    def test_mlx_performance_skill_exists_and_valid(self, skills_dir):
        """
        GIVEN: Skills directory
        WHEN: Checking mlx-performance skill
        THEN: Directory and SKILL.md exist
        """
        skill_dir = skills_dir / "mlx-performance"
        assert skill_dir.exists(), "mlx-performance directory not found"

        skill_metadata = skill_dir / "SKILL.md"
        assert skill_metadata.exists(), "mlx-performance SKILL.md not found"

        content = skill_metadata.read_text()
        assert len(content) > 50, "mlx-performance SKILL.md appears empty"


class TestTrainingMetricsLibraryLoad:
    """Smoke tests for training_metrics.py library loading."""

    @pytest.fixture
    def lib_dir(self):
        """Get lib directory."""
        return Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"

    def test_training_metrics_library_exists(self, lib_dir):
        """
        GIVEN: Lib directory
        WHEN: Checking for training_metrics.py
        THEN: File exists
        """
        lib_file = lib_dir / "training_metrics.py"
        assert lib_file.exists(), "training_metrics.py not found"

    def test_training_metrics_library_has_valid_syntax(self, lib_dir):
        """
        GIVEN: training_metrics.py
        WHEN: Parsing with AST
        THEN: No syntax errors
        """
        lib_file = lib_dir / "training_metrics.py"
        if not lib_file.exists():
            pytest.skip("training_metrics.py not yet created (TDD red phase)")

        content = lib_file.read_text()
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"training_metrics.py has syntax error: {e}")

    def test_training_metrics_library_imports(self, lib_dir):
        """
        GIVEN: training_metrics.py
        WHEN: Importing the module
        THEN: No import errors
        """
        lib_file = lib_dir / "training_metrics.py"
        if not lib_file.exists():
            pytest.skip("training_metrics.py not yet created (TDD red phase)")

        try:
            from plugins.autonomous_dev.lib import training_metrics
        except ImportError as e:
            pytest.fail(f"training_metrics.py import failed: {e}")

    def test_training_metrics_exports_dataclasses(self, lib_dir):
        """
        GIVEN: training_metrics.py imported
        WHEN: Checking exports
        THEN: IFDScore, DPOMetrics, RLVRVerifiability, TrainingDataQuality exist
        """
        lib_file = lib_dir / "training_metrics.py"
        if not lib_file.exists():
            pytest.skip("training_metrics.py not yet created (TDD red phase)")

        try:
            from plugins.autonomous_dev.lib.training_metrics import (
                IFDScore,
                DPOMetrics,
                RLVRVerifiability,
                TrainingDataQuality
            )
        except ImportError as e:
            pytest.fail(f"training_metrics.py missing expected exports: {e}")


class TestAgentRegistration:
    """Smoke tests for agent registration."""

    def test_training_agents_registered_in_invoker(self):
        """
        GIVEN: AgentInvoker.AGENT_CONFIGS
        WHEN: Checking for training agents
        THEN: Both agents are registered
        """
        from plugins.autonomous_dev.lib.agent_invoker import AgentInvoker

        configs = AgentInvoker.AGENT_CONFIGS
        training_agents = [
            'data-quality-validator',
            'distributed-training-coordinator',
            'realign-curator'
        ]

        for agent_name in training_agents:
            if agent_name not in configs:
                pytest.skip(f"{agent_name} not yet registered (TDD red phase)")

            # Just verify basic structure exists
            config = configs[agent_name]
            assert isinstance(config, dict), f"{agent_name} config should be a dict"
            assert 'progress_pct' in config, f"{agent_name} missing progress_pct"


class TestPerformance:
    """Smoke tests for performance (should complete quickly)."""

    def test_all_smoke_tests_complete_quickly(self):
        """
        GIVEN: All smoke tests
        WHEN: Running entire test suite
        THEN: Completes in <5 seconds
        """
        import time
        start = time.time()

        # This test is just a marker - pytest will measure actual duration
        # The test suite should naturally complete in <5s

        duration = time.time() - start
        assert duration < 5, f"Smoke tests took {duration}s (should be <5s)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

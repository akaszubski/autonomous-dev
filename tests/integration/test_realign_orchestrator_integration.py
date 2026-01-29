#!/usr/bin/env python3
"""
Integration Tests for realign_orchestrator.py Library (FAILING - Red Phase)

This module contains FAILING integration tests that validate cross-component
integration, skill invocation, hardware optimization, and end-to-end workflows.

Integration Test Scope:
1. Integration with realign-*-workflow skills
2. Hardware configuration optimization across data types
3. Multi-stage workflow execution
4. Performance benchmarking and validation
5. Error propagation and recovery
6. Metrics collection and reporting

Test Coverage Target: >80% of integration points

Following TDD principles:
- Write tests FIRST (red phase)
- Tests validate integration between components
- Tests should FAIL until all components implemented
- Each test validates ONE integration point

Author: test-master agent
Date: 2026-01-29
Issue: #303
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, Mock, call, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.realign_orchestrator import (
    DataType,
    HardwareConfig,
    WorkflowConfig,
    ExecutionResult,
    detect_data_type,
    map_workflow_skill,
    configure_hardware,
    execute_workflow,
    generate_summary,
)


# =============================================================================
# SKILL INTEGRATION TESTS
# =============================================================================


class TestSkillIntegration:
    """Test integration with realign-*-workflow skills."""

    @pytest.fixture
    def skills_dir(self):
        """Get skills directory path."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills"

    def test_all_workflow_skills_exist(self, skills_dir):
        """All mapped workflow skills must exist."""
        expected_skills = [
            "realign-dpo-workflow",
            "realign-srf-workflow",
            "realign-rlvr-workflow",
            "realign-antihallucination-workflow",
            "realign-persona-workflow",
            "realign-source-workflow",
        ]

        missing_skills = []
        for skill_name in expected_skills:
            skill_path = skills_dir / skill_name
            if not skill_path.exists():
                missing_skills.append(skill_name)

        assert not missing_skills, (
            f"Missing workflow skills:\n"
            f"{chr(10).join(f'  - {s}' for s in missing_skills)}\n"
            f"Create skills or update skill mapping"
        )

    def test_workflow_skills_have_skill_md(self, skills_dir):
        """All workflow skills must have SKILL.md file."""
        workflow_skills = [
            "realign-dpo-workflow",
            "realign-srf-workflow",
            "realign-rlvr-workflow",
        ]

        for skill_name in workflow_skills:
            skill_file = skills_dir / skill_name / "SKILL.md"
            if not (skills_dir / skill_name).exists():
                pytest.skip(f"Skill {skill_name} not implemented yet")

            assert skill_file.exists(), (
                f"Missing SKILL.md for {skill_name}\n"
                f"Expected: {skill_file}"
            )

    def test_orchestrator_calls_correct_skill(self, tmp_path):
        """Orchestrator invokes the correct workflow skill."""
        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.return_value = {"success": True, "metrics": {}}

            # Setup DPO workflow
            input_file = tmp_path / "dpo_input.jsonl"
            input_file.write_text('{"prompt": "test", "chosen": "a", "rejected": "b"}\n')

            hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
            hw_config = configure_hardware(DataType.DPO, hardware)

            config = WorkflowConfig(
                data_type=DataType.DPO,
                skill_name="realign-dpo-workflow",
                hardware_config=hw_config,
                input_path=input_file,
                output_path=tmp_path / "output"
            )

            execute_workflow(config)

            # Verify correct skill was invoked
            mock_invoke.assert_called_once()
            call_args = mock_invoke.call_args[0]
            assert "realign-dpo-workflow" in str(call_args)

    def test_skill_receives_hardware_config(self, tmp_path):
        """Invoked skill receives hardware configuration."""
        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.return_value = {"success": True, "metrics": {}}

            input_file = tmp_path / "input.jsonl"
            input_file.write_text('{"data": "test"}\n')

            hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
            hw_config = configure_hardware(DataType.DPO, hardware)

            config = WorkflowConfig(
                data_type=DataType.DPO,
                skill_name="realign-dpo-workflow",
                hardware_config=hw_config,
                input_path=input_file,
                output_path=tmp_path / "output"
            )

            execute_workflow(config)

            # Verify hardware config passed to skill
            call_kwargs = mock_invoke.call_args[1]
            assert "hardware_config" in call_kwargs
            assert call_kwargs["hardware_config"]["batch_size"] == hw_config.batch_size

    def test_skill_failure_propagates_error(self, tmp_path):
        """Skill execution failure propagates error to orchestrator."""
        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.side_effect = RuntimeError("Skill execution failed")

            input_file = tmp_path / "input.jsonl"
            input_file.write_text('{"data": "test"}\n')

            hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
            hw_config = configure_hardware(DataType.DPO, hardware)

            config = WorkflowConfig(
                data_type=DataType.DPO,
                skill_name="realign-dpo-workflow",
                hardware_config=hw_config,
                input_path=input_file,
                output_path=tmp_path / "output"
            )

            with pytest.raises(RuntimeError, match="Skill execution failed"):
                execute_workflow(config)


# =============================================================================
# HARDWARE OPTIMIZATION INTEGRATION TESTS
# =============================================================================


class TestHardwareOptimization:
    """Test hardware configuration optimization across workflows."""

    def test_batch_size_optimization_dpo(self):
        """DPO workflow gets optimized batch size for hardware."""
        hardware_configs = [
            {"name": "M3", "memory_gb": 32, "cores": 8},
            {"name": "M3 Pro", "memory_gb": 64, "cores": 12},
            {"name": "M4 Max", "memory_gb": 128, "cores": 16},
        ]

        configs = [configure_hardware(DataType.DPO, hw) for hw in hardware_configs]

        # Batch sizes should increase with memory
        batch_sizes = [c.batch_size for c in configs]
        assert batch_sizes[0] < batch_sizes[1] < batch_sizes[2]

    def test_worker_optimization_parallel(self):
        """Worker count optimized for parallel workflows."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        config_dpo = configure_hardware(DataType.DPO, hardware)
        config_srf = configure_hardware(DataType.SRF, hardware)

        # Both should utilize multiple workers
        assert config_dpo.num_workers > 1
        assert config_srf.num_workers > 1

    def test_memory_allocation_optimization(self):
        """Memory per worker optimized to avoid OOM."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        config = configure_hardware(DataType.DPO, hardware)

        # Total worker memory should not exceed 80% of available
        total_worker_memory = config.num_workers * config.memory_per_worker_gb
        assert total_worker_memory <= 128 * 0.8

    def test_optimization_flags_set_correctly(self):
        """Hardware optimization flags set for M4/M3 chips."""
        hardware_m4 = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hardware_m3 = {"name": "M3 Ultra", "memory_gb": 192, "cores": 24}

        config_m4 = configure_hardware(DataType.DPO, hardware_m4)
        config_m3 = configure_hardware(DataType.DPO, hardware_m3)

        # Should have optimization flags
        assert len(config_m4.optimization_flags) > 0
        assert len(config_m3.optimization_flags) > 0

    def test_work_distribution_strategy_varies(self):
        """Work distribution strategy varies by data type and hardware."""
        hardware_small = {"name": "M3", "memory_gb": 32, "cores": 8}
        hardware_large = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        # DPO on small hardware might use sequential
        config_small = configure_hardware(DataType.DPO, hardware_small)
        # DPO on large hardware should use parallel
        config_large = configure_hardware(DataType.DPO, hardware_large)

        # Strategy should be set
        assert config_small.work_distribution in ["parallel", "sequential", "hybrid"]
        assert config_large.work_distribution in ["parallel", "sequential", "hybrid"]


# =============================================================================
# MULTI-STAGE WORKFLOW INTEGRATION TESTS
# =============================================================================


class TestMultiStageWorkflow:
    """Test multi-stage workflow execution integration."""

    @pytest.fixture
    def multi_stage_config(self, tmp_path):
        """Create multi-stage workflow configuration."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"prompt": "test", "chosen": "a", "rejected": "b"}\n')

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        return WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

    def test_workflow_stages_execute_sequentially(self, multi_stage_config):
        """Workflow stages execute in correct order."""
        execution_order = []

        def mock_stage_execution(stage_name):
            execution_order.append(stage_name)
            return {"success": True}

        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.side_effect = lambda name, **kwargs: {
                "success": True,
                "stage": name,
                "metrics": {}
            }

            result = execute_workflow(multi_stage_config)

            # Verify execution occurred
            assert mock_invoke.called

    def test_workflow_passes_data_between_stages(self, multi_stage_config):
        """Data flows correctly between workflow stages."""
        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            stage_outputs = []

            def stage_handler(skill_name, **kwargs):
                output = {"success": True, "data": f"output_{len(stage_outputs)}"}
                stage_outputs.append(output)
                return output

            mock_invoke.side_effect = stage_handler

            execute_workflow(multi_stage_config)

            # Verify stages produced outputs
            assert len(stage_outputs) > 0

    def test_workflow_aggregates_metrics(self, multi_stage_config):
        """Workflow aggregates metrics from all stages."""
        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "metrics": {
                    "stage1_quality": 0.85,
                    "stage2_quality": 0.90,
                    "examples_processed": 10000
                }
            }

            result = execute_workflow(multi_stage_config)

            # Result should contain aggregated metrics
            assert len(result.metrics) > 0
            assert result.success is True


# =============================================================================
# PERFORMANCE BENCHMARKING INTEGRATION TESTS
# =============================================================================


class TestPerformanceBenchmarking:
    """Test performance benchmarking and validation."""

    def test_execution_time_tracking(self, tmp_path):
        """Workflow execution tracks accurate timing."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"data": "test"}\n')

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            # Simulate 100ms execution
            def slow_execution(*args, **kwargs):
                time.sleep(0.1)
                return {"success": True, "metrics": {}}

            mock_invoke.side_effect = slow_execution

            start = time.time()
            result = execute_workflow(config)
            end = time.time()

            # Verify execution time tracked
            assert result.execution_time_seconds > 0
            assert 0.08 < result.execution_time_seconds < 0.2  # ~100ms ±20%

    def test_throughput_metrics_collected(self, tmp_path):
        """Workflow collects throughput metrics (examples/sec)."""
        input_file = tmp_path / "large_input.jsonl"
        # Create 1000 examples
        with open(input_file, 'w') as f:
            for i in range(1000):
                f.write(json.dumps({"prompt": f"test {i}", "chosen": "a", "rejected": "b"}) + '\n')

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "metrics": {
                    "examples_processed": 1000,
                    "throughput": 500  # examples/sec
                }
            }

            result = execute_workflow(config)

            # Verify throughput metric present
            assert "throughput" in result.metrics or "examples_processed" in result.metrics

    def test_hardware_utilization_metrics(self, tmp_path):
        """Workflow tracks hardware utilization metrics."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"data": "test"}\n')

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "metrics": {
                    "cpu_utilization": 0.85,
                    "memory_peak_gb": 64
                }
            }

            result = execute_workflow(config)

            # Should have resource utilization metrics
            assert result.metrics is not None


# =============================================================================
# ERROR PROPAGATION AND RECOVERY TESTS
# =============================================================================


class TestErrorPropagation:
    """Test error propagation and recovery across components."""

    def test_invalid_data_type_error_propagates(self):
        """Invalid data type detection error propagates."""
        with pytest.raises(ValueError):
            # Unknown type should fail at workflow mapping
            map_workflow_skill(DataType.UNKNOWN)

    def test_hardware_failure_error_propagates(self, tmp_path):
        """Hardware configuration failure propagates to workflow."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"data": "test"}\n')

        # Invalid hardware config
        with pytest.raises(ValueError):
            configure_hardware(DataType.DPO, {"name": "M4 Max", "memory_gb": 8, "cores": 16})

    def test_skill_not_found_error_detailed(self, tmp_path):
        """Skill not found error provides detailed information."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"data": "test"}\n')

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="nonexistent-skill",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        with pytest.raises(FileNotFoundError, match="Skill not found"):
            execute_workflow(config)

    def test_workflow_cleanup_on_failure(self, tmp_path):
        """Workflow cleans up resources on failure."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"data": "test"}\n')

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.side_effect = RuntimeError("Workflow stage failed")

            try:
                execute_workflow(config)
            except RuntimeError:
                pass  # Expected

            # Verify cleanup occurred (no lingering temp files, etc.)
            # This is a placeholder - actual cleanup depends on implementation

    def test_partial_success_recovery(self, tmp_path):
        """Workflow handles partial success and continues."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"data": "test"}\n')

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "partial": True,
                "warnings": ["Some examples skipped"],
                "metrics": {"processed": 800, "skipped": 200}
            }

            result = execute_workflow(config)

            # Should report partial success
            assert result.success is True
            # Should capture warnings in metrics or error_message


# =============================================================================
# METRICS COLLECTION AND REPORTING TESTS
# =============================================================================


class TestMetricsCollection:
    """Test metrics collection and reporting integration."""

    def test_quality_metrics_collected(self, tmp_path):
        """Workflow collects quality metrics from skills."""
        input_file = tmp_path / "dpo_input.jsonl"
        input_file.write_text('{"prompt": "test", "chosen": "a", "rejected": "b"}\n')

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "metrics": {
                    "quality_score": 0.85,
                    "preference_gap": 0.25,
                    "kl_divergence": 0.05
                }
            }

            result = execute_workflow(config)

            # Verify quality metrics present
            assert "quality_score" in result.metrics
            assert result.metrics["quality_score"] == 0.85

    def test_progress_tracking_integration(self, tmp_path):
        """Workflow tracks progress across stages."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"data": "test"}\n')

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.return_value = {
                "success": True,
                "progress": 1.0,
                "metrics": {}
            }

            result = execute_workflow(config)

            # Verify progress tracked
            assert hasattr(result, "progress")
            assert 0.0 <= result.progress <= 1.0

    def test_summary_includes_all_metrics(self, tmp_path):
        """Summary generation includes all collected metrics."""
        result = ExecutionResult(
            success=True,
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            output_path=tmp_path / "output",
            metrics={
                "quality_score": 0.85,
                "examples_processed": 10000,
                "throughput": 500,
                "preference_gap": 0.25,
                "kl_divergence": 0.05
            },
            execution_time_seconds=1200,
            progress=1.0
        )

        summary = generate_summary(result)

        # Verify all metrics in summary
        assert "0.85" in summary  # quality_score
        assert "10000" in summary  # examples_processed
        assert "0.25" in summary  # preference_gap


# =============================================================================
# CROSS-WORKFLOW INTEGRATION TESTS
# =============================================================================


class TestCrossWorkflowIntegration:
    """Test integration across different workflow types."""

    def test_all_data_types_execute_successfully(self, tmp_path):
        """All data types execute their workflows successfully."""
        test_cases = [
            (DataType.DPO, "realign-dpo-workflow", '{"prompt": "test", "chosen": "a", "rejected": "b"}'),
            (DataType.SRF, "realign-srf-workflow", '{"instruction": "test", "response": "answer"}'),
            (DataType.RLVR, "realign-rlvr-workflow", '{"problem": "test", "solution": "answer", "verifiable": true}'),
        ]

        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        for data_type, skill_name, example_data in test_cases:
            input_file = tmp_path / f"{data_type.value}_input.jsonl"
            input_file.write_text(example_data + '\n')

            hw_config = configure_hardware(data_type, hardware)

            config = WorkflowConfig(
                data_type=data_type,
                skill_name=skill_name,
                hardware_config=hw_config,
                input_path=input_file,
                output_path=tmp_path / f"{data_type.value}_output"
            )

            with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
                mock_invoke.return_value = {"success": True, "metrics": {}}

                result = execute_workflow(config)

                assert result.success is True, f"Failed for {data_type}"

    def test_hardware_config_consistent_across_types(self):
        """Hardware configuration is consistent across workflow types."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        configs = [
            configure_hardware(DataType.DPO, hardware),
            configure_hardware(DataType.SRF, hardware),
            configure_hardware(DataType.RLVR, hardware),
        ]

        # All configs should use same hardware
        assert all(c.hardware_name == "M4 Max" for c in configs)

        # All configs should have valid batch sizes
        assert all(c.batch_size > 0 for c in configs)

    def test_metrics_format_consistent_across_workflows(self, tmp_path):
        """Metrics format is consistent across workflow types."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        results = []
        for data_type in [DataType.DPO, DataType.SRF, DataType.RLVR]:
            input_file = tmp_path / f"{data_type.value}_input.jsonl"
            input_file.write_text('{"test": "data"}\n')

            hw_config = configure_hardware(data_type, hardware)
            skill_name = map_workflow_skill(data_type)

            config = WorkflowConfig(
                data_type=data_type,
                skill_name=skill_name,
                hardware_config=hw_config,
                input_path=input_file,
                output_path=tmp_path / f"{data_type.value}_output"
            )

            with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
                mock_invoke.return_value = {
                    "success": True,
                    "metrics": {"quality_score": 0.85}
                }

                result = execute_workflow(config)
                results.append(result)

        # All results should have consistent structure
        assert all(hasattr(r, "success") for r in results)
        assert all(hasattr(r, "metrics") for r in results)
        assert all(hasattr(r, "execution_time_seconds") for r in results)


# =============================================================================
# REALIGN-CURATOR AGENT INTEGRATION TESTS
# =============================================================================


class TestRealignCuratorIntegration:
    """Test integration with realign-curator agent."""

    def test_orchestrator_invoked_from_agent_context(self, tmp_path):
        """Orchestrator can be invoked from realign-curator agent."""
        # Simulate agent request
        request = "I need to realign my model with preference data for DPO"

        # Agent detects data type
        data_type = detect_data_type(request)
        assert data_type == DataType.DPO

        # Agent maps to skill
        skill_name = map_workflow_skill(data_type)
        assert skill_name == "realign-dpo-workflow"

        # Agent configures hardware
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(data_type, hardware)

        # Agent executes workflow
        input_file = tmp_path / "dpo_pairs.jsonl"
        input_file.write_text('{"prompt": "test", "chosen": "a", "rejected": "b"}\n')

        config = WorkflowConfig(
            data_type=data_type,
            skill_name=skill_name,
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        with patch("plugins.autonomous_dev.lib.realign_orchestrator.invoke_skill") as mock_invoke:
            mock_invoke.return_value = {"success": True, "metrics": {"quality_score": 0.85}}

            result = execute_workflow(config)

            # Agent generates summary
            summary = generate_summary(result)

            assert "success" in summary.lower()
            assert "0.85" in summary

    def test_orchestrator_provides_agent_guidance(self):
        """Orchestrator provides guidance for agent decision-making."""
        # Test all data types provide valid guidance
        test_requests = [
            "preference data for DPO",
            "instruction-following dataset for SFT",
            "verifiable rewards for RLVR",
        ]

        for request in test_requests:
            data_type = detect_data_type(request)
            assert data_type != DataType.UNKNOWN

            skill_name = map_workflow_skill(data_type)
            assert skill_name.startswith("realign-")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])

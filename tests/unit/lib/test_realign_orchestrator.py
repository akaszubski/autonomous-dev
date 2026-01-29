#!/usr/bin/env python3
"""
TDD Tests for realign_orchestrator.py Library (FAILING - Red Phase)

This module contains FAILING tests for the realign_orchestrator library that provides
orchestration features for the realign-curator agent including data type detection,
workflow mapping, and hardware auto-configuration.

Library Requirements:
1. Data type detection: detect_data_type(request_text) -> str
2. Workflow mapping: map_workflow_skill(data_type) -> str
3. Hardware configuration: configure_hardware(data_type, available_hardware) -> Dict
4. Workflow execution: execute_workflow(workflow_config) -> Dict
5. Summary generation: generate_summary(execution_results) -> str

Test Coverage Target: >80% (PROJECT.md requirement)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests should FAIL until library is implemented
- Each test validates ONE requirement
- Comprehensive coverage of unit tests, integration, edge cases

Test Categories:
1. Data type detection (DPO/SRF/RLVR/anti-hallucination/persona/source keywords)
2. Workflow mapping (type → skill name)
3. Hardware configuration (M4 Max/M3 Ultra, batch sizes, work distribution)
4. Edge cases (unknown type, multiple types, empty request)
5. Error handling (skill not found, hardware failure, validation errors)

Author: test-master agent
Date: 2026-01-29
Issue: #303
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

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
    validate_workflow_config,
    estimate_execution_time,
)


# =============================================================================
# DATA TYPE DETECTION TESTS
# =============================================================================


class TestDetectDataType:
    """Test data type detection from request text."""

    def test_detect_dpo_data_type_preference(self):
        """Detect DPO type from 'preference' keyword."""
        request = "I need help realigning my model with preference data"

        data_type = detect_data_type(request)

        assert data_type == DataType.DPO, (
            f"Expected DataType.DPO for 'preference' keyword\n"
            f"Got: {data_type}\n"
            f"Request: {request}"
        )

    def test_detect_dpo_data_type_chosen_rejected(self):
        """Detect DPO type from 'chosen/rejected' keywords."""
        request = "Process DPO pairs with chosen and rejected responses"

        data_type = detect_data_type(request)

        assert data_type == DataType.DPO

    def test_detect_srf_data_type_supervised(self):
        """Detect SRF type from 'supervised' keyword."""
        request = "Supervised fine-tuning on instruction dataset"

        data_type = detect_data_type(request)

        assert data_type == DataType.SRF

    def test_detect_srf_data_type_instruction(self):
        """Detect SRF type from 'instruction' keyword."""
        request = "Fine-tune with instruction-following data"

        data_type = detect_data_type(request)

        assert data_type == DataType.SRF

    def test_detect_rlvr_data_type_verifiable(self):
        """Detect RLVR type from 'verifiable' keyword."""
        request = "Train with verifiable rewards for math problems"

        data_type = detect_data_type(request)

        assert data_type == DataType.RLVR

    def test_detect_rlvr_data_type_reasoning(self):
        """Detect RLVR type from 'reasoning' keyword."""
        request = "Reinforcement learning with reasoning tasks"

        data_type = detect_data_type(request)

        assert data_type == DataType.RLVR

    def test_detect_anti_hallucination_type(self):
        """Detect anti-hallucination type from keywords."""
        request = "Reduce hallucinations and improve factuality"

        data_type = detect_data_type(request)

        assert data_type == DataType.ANTI_HALLUCINATION

    def test_detect_persona_data_type(self):
        """Detect persona type from 'persona' keyword."""
        request = "Align model to specific persona and style"

        data_type = detect_data_type(request)

        assert data_type == DataType.PERSONA

    def test_detect_source_data_type(self):
        """Detect source type from 'attribution' keyword."""
        request = "Train model to cite sources and provide attribution"

        data_type = detect_data_type(request)

        assert data_type == DataType.SOURCE

    def test_detect_unknown_data_type(self):
        """Unknown type returns DataType.UNKNOWN."""
        request = "Some random text without keywords"

        data_type = detect_data_type(request)

        assert data_type == DataType.UNKNOWN

    def test_detect_empty_request(self):
        """Empty request returns DataType.UNKNOWN."""
        data_type = detect_data_type("")

        assert data_type == DataType.UNKNOWN

    def test_detect_case_insensitive(self):
        """Detection should be case-insensitive."""
        request = "PREFERENCE DATA FOR DPO TRAINING"

        data_type = detect_data_type(request)

        assert data_type == DataType.DPO

    def test_detect_multiple_types_priority(self):
        """When multiple types detected, return highest priority."""
        request = "Use preference data and instruction-following for training"

        data_type = detect_data_type(request)

        # DPO should have higher priority than SRF
        assert data_type in [DataType.DPO, DataType.SRF]

    def test_detect_with_noise(self):
        """Detection works with surrounding noise text."""
        request = (
            "Hello, I would really appreciate your help with "
            "training my model using preference data. "
            "Thanks in advance!"
        )

        data_type = detect_data_type(request)

        assert data_type == DataType.DPO


# =============================================================================
# WORKFLOW MAPPING TESTS
# =============================================================================


class TestMapWorkflowSkill:
    """Test mapping data types to workflow skill names."""

    def test_map_dpo_to_skill(self):
        """Map DPO type to realign-dpo-workflow skill."""
        skill_name = map_workflow_skill(DataType.DPO)

        assert skill_name == "realign-dpo-workflow", (
            f"Expected 'realign-dpo-workflow' for DataType.DPO\n"
            f"Got: {skill_name}"
        )

    def test_map_srf_to_skill(self):
        """Map SRF type to realign-srf-workflow skill."""
        skill_name = map_workflow_skill(DataType.SRF)

        assert skill_name == "realign-srf-workflow"

    def test_map_rlvr_to_skill(self):
        """Map RLVR type to realign-rlvr-workflow skill."""
        skill_name = map_workflow_skill(DataType.RLVR)

        assert skill_name == "realign-rlvr-workflow"

    def test_map_anti_hallucination_to_skill(self):
        """Map anti-hallucination type to skill."""
        skill_name = map_workflow_skill(DataType.ANTI_HALLUCINATION)

        assert skill_name == "realign-antihallucination-workflow"

    def test_map_persona_to_skill(self):
        """Map persona type to skill."""
        skill_name = map_workflow_skill(DataType.PERSONA)

        assert skill_name == "realign-persona-workflow"

    def test_map_source_to_skill(self):
        """Map source type to skill."""
        skill_name = map_workflow_skill(DataType.SOURCE)

        assert skill_name == "realign-source-workflow"

    def test_map_unknown_raises_error(self):
        """Mapping unknown type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown data type"):
            map_workflow_skill(DataType.UNKNOWN)

    def test_map_invalid_type_raises_error(self):
        """Invalid type argument raises TypeError."""
        with pytest.raises(TypeError, match="Expected DataType"):
            map_workflow_skill("invalid")


# =============================================================================
# HARDWARE CONFIGURATION TESTS
# =============================================================================


class TestConfigureHardware:
    """Test hardware auto-configuration for workflows."""

    def test_configure_m4_max_dpo(self):
        """Configure M4 Max for DPO workflow."""
        available_hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        config = configure_hardware(DataType.DPO, available_hardware)

        assert isinstance(config, HardwareConfig)
        assert config.hardware_name == "M4 Max"
        assert config.batch_size > 0
        assert config.num_workers > 0
        assert config.memory_per_worker_gb > 0

    def test_configure_m3_ultra_srf(self):
        """Configure M3 Ultra for SRF workflow."""
        available_hardware = {"name": "M3 Ultra", "memory_gb": 192, "cores": 24}

        config = configure_hardware(DataType.SRF, available_hardware)

        assert config.hardware_name == "M3 Ultra"
        assert config.batch_size > 0

    def test_configure_batch_size_scales_with_memory(self):
        """Batch size should scale with available memory."""
        hardware_small = {"name": "M3", "memory_gb": 32, "cores": 8}
        hardware_large = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        config_small = configure_hardware(DataType.DPO, hardware_small)
        config_large = configure_hardware(DataType.DPO, hardware_large)

        assert config_large.batch_size > config_small.batch_size, (
            "Larger memory should result in larger batch size"
        )

    def test_configure_workers_scales_with_cores(self):
        """Number of workers should scale with CPU cores."""
        hardware_few_cores = {"name": "M3", "memory_gb": 64, "cores": 8}
        hardware_many_cores = {"name": "M4 Max", "memory_gb": 64, "cores": 16}

        config_few = configure_hardware(DataType.DPO, hardware_few_cores)
        config_many = configure_hardware(DataType.DPO, hardware_many_cores)

        assert config_many.num_workers > config_few.num_workers

    def test_configure_rlvr_higher_batch_size(self):
        """RLVR workflows should get higher batch sizes (verifiable rewards)."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        config_dpo = configure_hardware(DataType.DPO, hardware)
        config_rlvr = configure_hardware(DataType.RLVR, hardware)

        # RLVR can use larger batches due to verifiable rewards
        assert config_rlvr.batch_size >= config_dpo.batch_size

    def test_configure_minimum_memory_requirement(self):
        """Raise error if hardware has insufficient memory."""
        insufficient_hardware = {"name": "M1", "memory_gb": 8, "cores": 4}

        with pytest.raises(ValueError, match="Insufficient memory"):
            configure_hardware(DataType.DPO, insufficient_hardware)

    def test_configure_invalid_hardware_format(self):
        """Invalid hardware dict raises ValueError."""
        invalid_hardware = {"name": "M4 Max"}  # Missing memory_gb and cores

        with pytest.raises(ValueError, match="Invalid hardware configuration"):
            configure_hardware(DataType.DPO, invalid_hardware)

    def test_configure_work_distribution(self):
        """Hardware config includes work distribution strategy."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        config = configure_hardware(DataType.DPO, hardware)

        assert hasattr(config, "work_distribution")
        assert config.work_distribution in ["parallel", "sequential", "hybrid"]

    def test_configure_memory_per_worker(self):
        """Memory per worker should be calculated correctly."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        config = configure_hardware(DataType.DPO, hardware)

        total_worker_memory = config.num_workers * config.memory_per_worker_gb
        # Should not exceed 80% of available memory (leave buffer)
        assert total_worker_memory <= hardware["memory_gb"] * 0.8

    def test_configure_optimization_flags(self):
        """Config should include hardware-specific optimization flags."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        config = configure_hardware(DataType.DPO, hardware)

        assert hasattr(config, "optimization_flags")
        assert isinstance(config.optimization_flags, dict)


# =============================================================================
# WORKFLOW CONFIGURATION VALIDATION TESTS
# =============================================================================


class TestValidateWorkflowConfig:
    """Test workflow configuration validation."""

    def test_validate_valid_config(self):
        """Valid workflow config passes validation."""
        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=HardwareConfig(
                hardware_name="M4 Max",
                batch_size=32,
                num_workers=8,
                memory_per_worker_gb=8,
                work_distribution="parallel",
                optimization_flags={}
            ),
            input_path=Path("/data/dpo_pairs.jsonl"),
            output_path=Path("/output/results/")
        )

        result = validate_workflow_config(config)

        assert result is True

    def test_validate_missing_input_path(self):
        """Config with missing input path fails validation."""
        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=HardwareConfig(
                hardware_name="M4 Max",
                batch_size=32,
                num_workers=8,
                memory_per_worker_gb=8,
                work_distribution="parallel",
                optimization_flags={}
            ),
            input_path=None,
            output_path=Path("/output/")
        )

        with pytest.raises(ValueError, match="Input path required"):
            validate_workflow_config(config)

    def test_validate_invalid_batch_size(self):
        """Config with invalid batch size fails validation."""
        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=HardwareConfig(
                hardware_name="M4 Max",
                batch_size=0,  # Invalid
                num_workers=8,
                memory_per_worker_gb=8,
                work_distribution="parallel",
                optimization_flags={}
            ),
            input_path=Path("/data/input.jsonl"),
            output_path=Path("/output/")
        )

        with pytest.raises(ValueError, match="Batch size must be positive"):
            validate_workflow_config(config)

    def test_validate_mismatched_skill_type(self):
        """Config with mismatched skill and data type fails."""
        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-srf-workflow",  # Mismatch
            hardware_config=HardwareConfig(
                hardware_name="M4 Max",
                batch_size=32,
                num_workers=8,
                memory_per_worker_gb=8,
                work_distribution="parallel",
                optimization_flags={}
            ),
            input_path=Path("/data/input.jsonl"),
            output_path=Path("/output/")
        )

        with pytest.raises(ValueError, match="Skill name does not match data type"):
            validate_workflow_config(config)


# =============================================================================
# WORKFLOW EXECUTION TESTS
# =============================================================================


class TestExecuteWorkflow:
    """Test workflow execution orchestration."""

    @pytest.fixture
    def valid_workflow_config(self, tmp_path):
        """Create valid workflow configuration."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"prompt": "test", "chosen": "a", "rejected": "b"}\n')

        return WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=HardwareConfig(
                hardware_name="M4 Max",
                batch_size=32,
                num_workers=8,
                memory_per_worker_gb=8,
                work_distribution="parallel",
                optimization_flags={}
            ),
            input_path=input_file,
            output_path=tmp_path / "output"
        )

    def test_execute_workflow_success(self, valid_workflow_config):
        """Execute workflow successfully."""
        result = execute_workflow(valid_workflow_config)

        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.output_path is not None
        assert len(result.metrics) > 0

    def test_execute_workflow_creates_output(self, valid_workflow_config):
        """Workflow execution creates output files."""
        result = execute_workflow(valid_workflow_config)

        assert result.output_path.exists()

    def test_execute_workflow_invalid_config(self):
        """Execute with invalid config raises ValueError."""
        invalid_config = None

        with pytest.raises(ValueError, match="Invalid workflow config"):
            execute_workflow(invalid_config)

    def test_execute_workflow_missing_skill(self, valid_workflow_config):
        """Execute with missing skill raises FileNotFoundError."""
        valid_workflow_config.skill_name = "nonexistent-skill"

        with pytest.raises(FileNotFoundError, match="Skill not found"):
            execute_workflow(valid_workflow_config)

    def test_execute_workflow_hardware_failure(self, valid_workflow_config):
        """Execute with hardware failure raises RuntimeError."""
        # Simulate hardware failure
        valid_workflow_config.hardware_config.num_workers = -1

        with pytest.raises(RuntimeError, match="Hardware configuration error"):
            execute_workflow(valid_workflow_config)

    def test_execute_workflow_tracks_progress(self, valid_workflow_config):
        """Workflow execution tracks progress."""
        result = execute_workflow(valid_workflow_config)

        assert hasattr(result, "progress")
        assert result.progress >= 0.0
        assert result.progress <= 1.0

    def test_execute_workflow_includes_timing(self, valid_workflow_config):
        """Workflow execution includes timing metrics."""
        result = execute_workflow(valid_workflow_config)

        assert hasattr(result, "execution_time_seconds")
        assert result.execution_time_seconds > 0

    def test_execute_workflow_includes_quality_metrics(self, valid_workflow_config):
        """Workflow execution includes quality metrics."""
        result = execute_workflow(valid_workflow_config)

        assert "quality_score" in result.metrics
        assert 0.0 <= result.metrics["quality_score"] <= 1.0

    @patch("plugins.autonomous_dev.lib.realign_orchestrator.run_skill")
    def test_execute_workflow_calls_skill(self, mock_run_skill, valid_workflow_config):
        """Execute workflow calls appropriate skill."""
        mock_run_skill.return_value = {"success": True}

        execute_workflow(valid_workflow_config)

        mock_run_skill.assert_called_once()
        call_args = mock_run_skill.call_args
        assert "realign-dpo-workflow" in str(call_args)


# =============================================================================
# EXECUTION TIME ESTIMATION TESTS
# =============================================================================


class TestEstimateExecutionTime:
    """Test execution time estimation."""

    def test_estimate_time_dpo_small_dataset(self):
        """Estimate execution time for DPO with small dataset."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        dataset_size = 1000  # 1K examples

        estimated_seconds = estimate_execution_time(
            DataType.DPO,
            dataset_size,
            hardware
        )

        assert estimated_seconds > 0
        assert estimated_seconds < 3600  # Less than 1 hour for 1K examples

    def test_estimate_time_scales_with_dataset_size(self):
        """Execution time estimate scales linearly with dataset size."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        time_1k = estimate_execution_time(DataType.DPO, 1000, hardware)
        time_10k = estimate_execution_time(DataType.DPO, 10000, hardware)

        # Should be roughly 10x longer (within 20% tolerance)
        ratio = time_10k / time_1k
        assert 8 < ratio < 12, f"Expected ~10x scaling, got {ratio}x"

    def test_estimate_time_faster_with_more_cores(self):
        """Execution time decreases with more CPU cores."""
        hardware_few = {"name": "M3", "memory_gb": 64, "cores": 8}
        hardware_many = {"name": "M4 Max", "memory_gb": 64, "cores": 16}
        dataset_size = 10000

        time_few = estimate_execution_time(DataType.DPO, dataset_size, hardware_few)
        time_many = estimate_execution_time(DataType.DPO, dataset_size, hardware_many)

        assert time_many < time_few

    def test_estimate_time_rlvr_faster_than_dpo(self):
        """RLVR estimation should be faster (verifiable rewards)."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        dataset_size = 10000

        time_dpo = estimate_execution_time(DataType.DPO, dataset_size, hardware)
        time_rlvr = estimate_execution_time(DataType.RLVR, dataset_size, hardware)

        # RLVR can be optimized with automated verification
        assert time_rlvr <= time_dpo

    def test_estimate_time_zero_dataset(self):
        """Zero dataset size returns zero time."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        estimated_seconds = estimate_execution_time(DataType.DPO, 0, hardware)

        assert estimated_seconds == 0


# =============================================================================
# SUMMARY GENERATION TESTS
# =============================================================================


class TestGenerateSummary:
    """Test execution summary generation."""

    def test_generate_summary_success(self):
        """Generate summary for successful execution."""
        result = ExecutionResult(
            success=True,
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            output_path=Path("/output/results"),
            metrics={"quality_score": 0.85, "examples_processed": 10000},
            execution_time_seconds=1200,
            progress=1.0
        )

        summary = generate_summary(result)

        assert isinstance(summary, str)
        assert "success" in summary.lower()
        assert "0.85" in summary  # Quality score
        assert "10000" in summary  # Examples processed

    def test_generate_summary_failure(self):
        """Generate summary for failed execution."""
        result = ExecutionResult(
            success=False,
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            output_path=None,
            metrics={},
            execution_time_seconds=60,
            progress=0.3,
            error_message="Hardware configuration error"
        )

        summary = generate_summary(result)

        assert "fail" in summary.lower()
        assert "error" in summary.lower()
        assert "Hardware configuration error" in summary

    def test_generate_summary_includes_timing(self):
        """Summary includes execution time."""
        result = ExecutionResult(
            success=True,
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            output_path=Path("/output/"),
            metrics={"quality_score": 0.9},
            execution_time_seconds=3600,  # 1 hour
            progress=1.0
        )

        summary = generate_summary(result)

        # Should format time nicely (1 hour)
        assert any(x in summary for x in ["1 hour", "60 min", "3600"])

    def test_generate_summary_includes_metrics(self):
        """Summary includes all relevant metrics."""
        result = ExecutionResult(
            success=True,
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            output_path=Path("/output/"),
            metrics={
                "quality_score": 0.85,
                "examples_processed": 10000,
                "preference_gap": 0.25,
                "kl_divergence": 0.05
            },
            execution_time_seconds=1200,
            progress=1.0
        )

        summary = generate_summary(result)

        assert "0.85" in summary
        assert "10000" in summary
        assert "0.25" in summary

    def test_generate_summary_formats_paths(self):
        """Summary includes formatted output paths."""
        result = ExecutionResult(
            success=True,
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            output_path=Path("/output/dpo_results_2026-01-29"),
            metrics={"quality_score": 0.9},
            execution_time_seconds=600,
            progress=1.0
        )

        summary = generate_summary(result)

        assert "/output/dpo_results" in summary


# =============================================================================
# EDGE CASES AND ERROR HANDLING TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_detect_data_type_none_input(self):
        """None input raises TypeError."""
        with pytest.raises(TypeError, match="Request text must be string"):
            detect_data_type(None)

    def test_detect_data_type_very_long_text(self):
        """Detection works with very long text (100KB+)."""
        long_text = "Some random text " * 10000 + " preference data for DPO"

        data_type = detect_data_type(long_text)

        assert data_type == DataType.DPO

    def test_configure_hardware_none_input(self):
        """None hardware dict raises TypeError."""
        with pytest.raises(TypeError, match="Hardware config must be dict"):
            configure_hardware(DataType.DPO, None)

    def test_configure_hardware_missing_keys(self):
        """Hardware dict with missing keys raises ValueError."""
        invalid = {"name": "M4 Max", "memory_gb": 128}  # Missing cores

        with pytest.raises(ValueError, match="Missing required key"):
            configure_hardware(DataType.DPO, invalid)

    def test_configure_hardware_negative_memory(self):
        """Negative memory raises ValueError."""
        invalid = {"name": "M4 Max", "memory_gb": -128, "cores": 16}

        with pytest.raises(ValueError, match="Memory must be positive"):
            configure_hardware(DataType.DPO, invalid)

    def test_configure_hardware_zero_cores(self):
        """Zero cores raises ValueError."""
        invalid = {"name": "M4 Max", "memory_gb": 128, "cores": 0}

        with pytest.raises(ValueError, match="Cores must be positive"):
            configure_hardware(DataType.DPO, invalid)

    def test_execute_workflow_empty_input_file(self, tmp_path):
        """Empty input file raises ValueError."""
        empty_file = tmp_path / "empty.jsonl"
        empty_file.touch()

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=HardwareConfig(
                hardware_name="M4 Max",
                batch_size=32,
                num_workers=8,
                memory_per_worker_gb=8,
                work_distribution="parallel",
                optimization_flags={}
            ),
            input_path=empty_file,
            output_path=tmp_path / "output"
        )

        with pytest.raises(ValueError, match="Input file is empty"):
            execute_workflow(config)

    def test_execute_workflow_invalid_json(self, tmp_path):
        """Invalid JSON in input file raises ValueError."""
        invalid_file = tmp_path / "invalid.jsonl"
        invalid_file.write_text("not valid json\n")

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=HardwareConfig(
                hardware_name="M4 Max",
                batch_size=32,
                num_workers=8,
                memory_per_worker_gb=8,
                work_distribution="parallel",
                optimization_flags={}
            ),
            input_path=invalid_file,
            output_path=tmp_path / "output"
        )

        with pytest.raises(ValueError, match="Invalid JSON"):
            execute_workflow(config)

    def test_estimate_time_negative_dataset_size(self):
        """Negative dataset size raises ValueError."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}

        with pytest.raises(ValueError, match="Dataset size must be non-negative"):
            estimate_execution_time(DataType.DPO, -1000, hardware)

    def test_generate_summary_none_result(self):
        """None result raises TypeError."""
        with pytest.raises(TypeError, match="Result must be ExecutionResult"):
            generate_summary(None)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestOrchestrationIntegration:
    """Test end-to-end orchestration integration."""

    def test_full_orchestration_pipeline(self, tmp_path):
        """Test complete orchestration from request to summary."""
        # Step 1: Detect data type
        request = "I need to train my model with preference data for DPO"
        data_type = detect_data_type(request)
        assert data_type == DataType.DPO

        # Step 2: Map to workflow skill
        skill_name = map_workflow_skill(data_type)
        assert skill_name == "realign-dpo-workflow"

        # Step 3: Configure hardware
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(data_type, hardware)
        assert hw_config.batch_size > 0

        # Step 4: Create workflow config
        input_file = tmp_path / "dpo_pairs.jsonl"
        input_file.write_text('{"prompt": "test", "chosen": "a", "rejected": "b"}\n')

        workflow_config = WorkflowConfig(
            data_type=data_type,
            skill_name=skill_name,
            hardware_config=hw_config,
            input_path=input_file,
            output_path=tmp_path / "output"
        )

        # Step 5: Validate config
        assert validate_workflow_config(workflow_config) is True

        # Step 6: Execute workflow
        result = execute_workflow(workflow_config)
        assert result.success is True

        # Step 7: Generate summary
        summary = generate_summary(result)
        assert "success" in summary.lower()

    def test_orchestration_with_multiple_data_types(self):
        """Test orchestration detects and maps all data types."""
        test_cases = [
            ("preference data", DataType.DPO, "realign-dpo-workflow"),
            ("instruction-following", DataType.SRF, "realign-srf-workflow"),
            ("verifiable rewards", DataType.RLVR, "realign-rlvr-workflow"),
            ("reduce hallucinations", DataType.ANTI_HALLUCINATION, "realign-antihallucination-workflow"),
            ("persona alignment", DataType.PERSONA, "realign-persona-workflow"),
            ("source attribution", DataType.SOURCE, "realign-source-workflow"),
        ]

        for request_text, expected_type, expected_skill in test_cases:
            data_type = detect_data_type(request_text)
            assert data_type == expected_type, f"Failed for: {request_text}"

            skill_name = map_workflow_skill(data_type)
            assert skill_name == expected_skill, f"Failed mapping for: {expected_type}"

    def test_orchestration_error_recovery(self, tmp_path):
        """Test orchestration handles errors gracefully."""
        # Invalid request
        data_type = detect_data_type("random text")
        assert data_type == DataType.UNKNOWN

        # Should raise error when trying to map unknown type
        with pytest.raises(ValueError):
            map_workflow_skill(DataType.UNKNOWN)


# =============================================================================
# SECURITY VALIDATION TESTS
# =============================================================================


class TestSecurityValidation:
    """Test security-specific validation (CWE-22, CWE-20)."""

    def test_path_traversal_prevention_input(self, tmp_path):
        """CWE-22: Prevent path traversal in input paths."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        # Attempt path traversal
        malicious_path = tmp_path / "../../../etc/passwd"

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=malicious_path,
            output_path=tmp_path / "output"
        )

        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_workflow_config(config)

    def test_path_traversal_prevention_output(self, tmp_path):
        """CWE-22: Prevent path traversal in output paths."""
        hardware = {"name": "M4 Max", "memory_gb": 128, "cores": 16}
        hw_config = configure_hardware(DataType.DPO, hardware)

        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"test": "data"}\n')

        # Attempt path traversal in output
        malicious_output = tmp_path / "../../../tmp/malicious"

        config = WorkflowConfig(
            data_type=DataType.DPO,
            skill_name="realign-dpo-workflow",
            hardware_config=hw_config,
            input_path=input_file,
            output_path=malicious_output
        )

        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_workflow_config(config)

    def test_input_validation_sql_injection_attempt(self):
        """CWE-20: Validate inputs to prevent injection."""
        # SQL injection attempt in request text
        malicious_request = "preference data'; DROP TABLE users; --"

        # Should safely detect DPO without executing injection
        data_type = detect_data_type(malicious_request)
        assert data_type == DataType.DPO

    def test_input_validation_command_injection_attempt(self):
        """CWE-20: Validate inputs to prevent command injection."""
        malicious_request = "preference data && rm -rf /"

        # Should safely detect without executing command
        data_type = detect_data_type(malicious_request)
        assert data_type == DataType.DPO


# =============================================================================
# DATA TYPE ENUM TESTS
# =============================================================================


class TestDataTypeEnum:
    """Test DataType enum definition."""

    def test_data_type_enum_exists(self):
        """DataType enum is defined."""
        assert hasattr(DataType, "DPO")
        assert hasattr(DataType, "SRF")
        assert hasattr(DataType, "RLVR")
        assert hasattr(DataType, "ANTI_HALLUCINATION")
        assert hasattr(DataType, "PERSONA")
        assert hasattr(DataType, "SOURCE")
        assert hasattr(DataType, "UNKNOWN")

    def test_data_type_values_unique(self):
        """All DataType enum values are unique."""
        values = [
            DataType.DPO,
            DataType.SRF,
            DataType.RLVR,
            DataType.ANTI_HALLUCINATION,
            DataType.PERSONA,
            DataType.SOURCE,
            DataType.UNKNOWN
        ]
        assert len(values) == len(set(values))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])

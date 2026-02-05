#!/usr/bin/env python3
"""
TDD Red Phase: Integration tests for data-curator pipeline

End-to-end integration tests for the 9-stage A-grade data curation pipeline.
These tests should FAIL until implementation is complete.

Related to: GitHub Issue #311 - Create data-curator agent for A-grade pipeline orchestration

Test Coverage:
1. Full pipeline execution (all 9 stages)
2. Quality gates between stages
3. Checkpoint/resume workflows
4. State management integration
5. Agent tracker integration
6. Error recovery and retry
7. Metrics aggregation
8. Multi-stage workflows with failures

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe real-world usage
- Tests should FAIL until implementation is complete
- Each test validates ONE workflow

Author: test-master agent
Date: 2026-02-05
Issue: #311
"""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import checkpoint library
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib"))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_pipeline_env(tmp_path):
    """Create temporary pipeline environment with all required directories."""
    project_root = tmp_path / "test_pipeline"
    project_root.mkdir(parents=True)

    # Create directory structure
    (project_root / ".claude" / "artifacts").mkdir(parents=True)
    (project_root / "docs" / "sessions").mkdir(parents=True)
    (project_root / "data" / "raw").mkdir(parents=True)
    (project_root / "data" / "1_extract").mkdir(parents=True)
    (project_root / "data" / "2_prefilter").mkdir(parents=True)
    (project_root / "data" / "3_score").mkdir(parents=True)
    (project_root / "data" / "4_dedup").mkdir(parents=True)
    (project_root / "data" / "5_decontaminate").mkdir(parents=True)
    (project_root / "data" / "6_filter").mkdir(parents=True)
    (project_root / "data" / "7_generate").mkdir(parents=True)
    (project_root / "data" / "8_mix").mkdir(parents=True)
    (project_root / "data" / "9_validate").mkdir(parents=True)

    return project_root


@pytest.fixture
def sample_dataset(temp_pipeline_env):
    """Create sample dataset for testing."""
    raw_data = temp_pipeline_env / "data" / "raw" / "input.jsonl"

    # Create diverse test data
    test_records = [
        # High quality records
        {
            "text": "Machine learning models require large amounts of training data to achieve high accuracy.",
            "source": "textbook",
            "quality": "high"
        },
        {
            "text": "The Transformer architecture revolutionized natural language processing through self-attention mechanisms.",
            "source": "research_paper",
            "quality": "high"
        },
        # Medium quality records
        {
            "text": "Some text that is okay but not great for training purposes.",
            "source": "web",
            "quality": "medium"
        },
        # Low quality records (should be filtered)
        {
            "text": "asdf qwerty zzzz random gibberish text",
            "source": "spam",
            "quality": "low"
        },
        {
            "text": "short",
            "source": "web",
            "quality": "low"
        },
        # Duplicate records (should be detected)
        {
            "text": "Machine learning models require large amounts of training data to achieve high accuracy.",
            "source": "textbook",
            "quality": "high"
        },
        # Benchmark contamination (should be removed)
        {
            "text": "Question from MMLU benchmark: What is the capital of France?",
            "source": "contaminated",
            "quality": "high"
        },
    ]

    with open(raw_data, 'w') as f:
        for record in test_records:
            f.write(json.dumps(record) + '\n')

    return raw_data


@pytest.fixture
def checkpoint_manager(temp_pipeline_env):
    """Create CheckpointManager instance for testing."""
    from checkpoint import CheckpointManager
    artifacts_dir = temp_pipeline_env / ".claude" / "artifacts"
    return CheckpointManager(artifacts_dir=artifacts_dir)


@pytest.fixture
def pipeline_config():
    """Pipeline configuration for testing."""
    return {
        "workflow_id": "pipeline_20260205_120000",
        "stages": [
            "1_extract",
            "2_prefilter",
            "3_score",
            "4_dedup",
            "5_decontaminate",
            "6_filter",
            "7_generate",
            "8_mix",
            "9_validate"
        ],
        "quality_gates": {
            "2_prefilter": {"pass_rate": 0.60},
            "5_decontaminate": {"contamination_level": 0.05},
            "6_filter": {"pass_rate": 0.70}
        }
    }


# =============================================================================
# TEST FULL PIPELINE EXECUTION
# =============================================================================


class TestFullPipelineExecution:
    """Test complete pipeline execution from start to finish."""

    def test_pipeline_executes_all_9_stages(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that pipeline executes all 9 stages in order."""
        from data_curator import run_pipeline

        # Run full pipeline
        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=sample_dataset,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        # Verify all stages completed
        assert result["status"] == "completed"
        assert len(result["completed_stages"]) == 9

        # Verify stages executed in order
        expected_stages = pipeline_config["stages"]
        assert result["completed_stages"] == expected_stages

    def test_pipeline_creates_artifacts_for_each_stage(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that pipeline creates output artifacts for each stage."""
        from data_curator import run_pipeline

        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=sample_dataset,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        # Verify artifacts exist
        for stage in pipeline_config["stages"]:
            stage_dir = temp_pipeline_env / "data" / stage
            artifacts = list(stage_dir.glob("*.jsonl"))
            assert len(artifacts) > 0, f"No artifacts created for stage: {stage}"

    def test_pipeline_aggregates_metrics_across_stages(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that pipeline aggregates quality metrics from all stages."""
        from data_curator import run_pipeline

        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=sample_dataset,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        # Verify aggregated metrics
        assert "aggregated_metrics" in result
        metrics = result["aggregated_metrics"]

        # Should have metrics from all stages
        for stage in pipeline_config["stages"]:
            assert stage in metrics, f"Missing metrics for stage: {stage}"

        # Check for key metrics
        assert "total_records_input" in metrics
        assert "total_records_output" in metrics
        assert "overall_pass_rate" in metrics

    def test_pipeline_final_output_meets_quality_standards(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that final pipeline output meets quality standards."""
        from data_curator import run_pipeline

        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=sample_dataset,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        # Load final output
        final_output = temp_pipeline_env / "data" / "9_validate" / "output.jsonl"
        assert final_output.exists(), "Final output file not created"

        # Verify final output quality
        with open(final_output) as f:
            records = [json.loads(line) for line in f]

        # Should have filtered out low-quality records
        assert len(records) < 7, "Low-quality records not filtered"

        # Should have removed duplicates
        texts = [r["text"] for r in records]
        assert len(texts) == len(set(texts)), "Duplicates not removed"

        # Should have removed contamination
        for record in records:
            assert "MMLU" not in record["text"], "Benchmark contamination not removed"


# =============================================================================
# TEST QUALITY GATES
# =============================================================================


class TestQualityGatesIntegration:
    """Test quality gate enforcement during pipeline execution."""

    def test_quality_gate_blocks_progression_when_failed(
        self,
        temp_pipeline_env,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that quality gate failure blocks progression to next stage."""
        from data_curator import run_pipeline_stage, check_quality_gate_before_stage

        workflow_id = pipeline_config["workflow_id"]

        # Create low-quality data that will fail prefilter
        low_quality_data = temp_pipeline_env / "data" / "raw" / "low_quality.jsonl"
        with open(low_quality_data, 'w') as f:
            for _ in range(10):
                f.write(json.dumps({"text": "asdf qwerty zzz"}) + '\n')

        # Run extract stage
        run_pipeline_stage(
            workflow_id=workflow_id,
            stage="1_extract",
            input_file=low_quality_data,
            checkpoint_manager=checkpoint_manager
        )

        # Run prefilter stage (should have low pass rate)
        prefilter_result = run_pipeline_stage(
            workflow_id=workflow_id,
            stage="2_prefilter",
            checkpoint_manager=checkpoint_manager
        )

        # Check quality gate
        gate_result = check_quality_gate_before_stage(
            workflow_id=workflow_id,
            stage="3_score",
            checkpoint_manager=checkpoint_manager,
            gate_config=pipeline_config["quality_gates"]["2_prefilter"]
        )

        assert gate_result["passed"] is False, "Quality gate should fail with low-quality data"
        assert "reason" in gate_result
        assert gate_result["reason"].lower().find("pass rate") >= 0

    def test_quality_gate_allows_progression_when_passed(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that quality gate success allows progression."""
        from data_curator import run_pipeline_stage, check_quality_gate_before_stage

        workflow_id = pipeline_config["workflow_id"]

        # Run first two stages with good data
        run_pipeline_stage(
            workflow_id=workflow_id,
            stage="1_extract",
            input_file=sample_dataset,
            checkpoint_manager=checkpoint_manager
        )

        run_pipeline_stage(
            workflow_id=workflow_id,
            stage="2_prefilter",
            checkpoint_manager=checkpoint_manager
        )

        # Check quality gate
        gate_result = check_quality_gate_before_stage(
            workflow_id=workflow_id,
            stage="3_score",
            checkpoint_manager=checkpoint_manager,
            gate_config=pipeline_config["quality_gates"]["2_prefilter"]
        )

        assert gate_result["passed"] is True, "Quality gate should pass with good data"

    def test_contamination_quality_gate(
        self,
        temp_pipeline_env,
        checkpoint_manager,
        pipeline_config
    ):
        """Test contamination level quality gate after decontaminate stage."""
        from data_curator import run_pipeline_stage, check_quality_gate_before_stage

        workflow_id = pipeline_config["workflow_id"]

        # Create dataset with high contamination
        contaminated_data = temp_pipeline_env / "data" / "raw" / "contaminated.jsonl"
        with open(contaminated_data, 'w') as f:
            # 8 contaminated, 2 clean = 80% contamination (should fail gate)
            for _ in range(8):
                f.write(json.dumps({"text": "MMLU benchmark question"}) + '\n')
            for _ in range(2):
                f.write(json.dumps({"text": "Clean training text"}) + '\n')

        # Run stages up to decontaminate
        for stage in ["1_extract", "2_prefilter", "3_score", "4_dedup", "5_decontaminate"]:
            run_pipeline_stage(
                workflow_id=workflow_id,
                stage=stage,
                input_file=contaminated_data if stage == "1_extract" else None,
                checkpoint_manager=checkpoint_manager
            )

        # Check contamination gate
        gate_result = check_quality_gate_before_stage(
            workflow_id=workflow_id,
            stage="6_filter",
            checkpoint_manager=checkpoint_manager,
            gate_config=pipeline_config["quality_gates"]["5_decontaminate"]
        )

        # Should fail with 80% contamination (threshold is 5%)
        assert gate_result["passed"] is False, "Should fail with high contamination"


# =============================================================================
# TEST CHECKPOINT AND RESUME
# =============================================================================


class TestCheckpointResumeIntegration:
    """Test checkpoint creation and resume workflows."""

    def test_pipeline_saves_checkpoint_after_each_stage(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that pipeline saves checkpoint after completing each stage."""
        from data_curator import run_pipeline_stage

        workflow_id = pipeline_config["workflow_id"]

        # Run first 3 stages
        for stage in ["1_extract", "2_prefilter", "3_score"]:
            run_pipeline_stage(
                workflow_id=workflow_id,
                stage=stage,
                input_file=sample_dataset if stage == "1_extract" else None,
                checkpoint_manager=checkpoint_manager
            )

        # Verify checkpoint exists
        assert checkpoint_manager.checkpoint_exists(workflow_id)

        # Load checkpoint and verify state
        checkpoint = checkpoint_manager.load_checkpoint(workflow_id)
        assert checkpoint is not None
        assert "stage" in checkpoint
        assert checkpoint["stage"] == "3_score"

    def test_pipeline_resumes_from_checkpoint(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that pipeline can resume from saved checkpoint."""
        from data_curator import run_pipeline_stage, resume_pipeline

        workflow_id = pipeline_config["workflow_id"]

        # Run first 3 stages
        for stage in ["1_extract", "2_prefilter", "3_score"]:
            run_pipeline_stage(
                workflow_id=workflow_id,
                stage=stage,
                input_file=sample_dataset if stage == "1_extract" else None,
                checkpoint_manager=checkpoint_manager
            )

        # Resume pipeline (should continue from stage 4)
        resume_result = resume_pipeline(
            workflow_id=workflow_id,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        assert resume_result["resumed"] is True
        assert resume_result["resume_stage"] == "4_dedup"
        assert len(resume_result["completed_stages"]) == 3

    def test_resume_validates_previous_stage_artifacts(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that resume validates artifacts from previous stages exist."""
        from data_curator import resume_pipeline

        workflow_id = pipeline_config["workflow_id"]

        # Create checkpoint without creating artifacts (simulates corruption)
        from checkpoint import create_stage_checkpoint
        create_stage_checkpoint(
            checkpoint_manager=checkpoint_manager,
            workflow_id=workflow_id,
            stage_name="3_score",
            metrics={"pass_rate": 0.75}
        )

        # Attempt to resume (should fail validation)
        resume_result = resume_pipeline(
            workflow_id=workflow_id,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        assert resume_result["resumed"] is False
        assert "error" in resume_result
        assert "artifact" in resume_result["error"].lower()

    def test_resume_reruns_failed_stage(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that resume can retry a failed stage."""
        from data_curator import run_pipeline_stage, resume_pipeline
        from checkpoint import record_stage_failure

        workflow_id = pipeline_config["workflow_id"]

        # Run first 2 stages
        for stage in ["1_extract", "2_prefilter"]:
            run_pipeline_stage(
                workflow_id=workflow_id,
                stage=stage,
                input_file=sample_dataset if stage == "1_extract" else None,
                checkpoint_manager=checkpoint_manager
            )

        # Simulate failure on stage 3
        record_stage_failure(
            checkpoint_manager=checkpoint_manager,
            workflow_id=workflow_id,
            stage_name="3_score",
            error_message="Scoring function timeout"
        )

        # Resume (should retry stage 3)
        resume_result = resume_pipeline(
            workflow_id=workflow_id,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config,
            retry_failed=True
        )

        assert resume_result["resumed"] is True
        assert resume_result["resume_stage"] == "3_score"
        assert resume_result["is_retry"] is True


# =============================================================================
# TEST STATE MANAGEMENT
# =============================================================================


class TestStateManagementIntegration:
    """Test state management across pipeline stages."""

    def test_stage_context_passed_between_stages(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that context from previous stage is available to next stage."""
        from data_curator import run_pipeline_stage, get_stage_context

        workflow_id = pipeline_config["workflow_id"]

        # Run prefilter stage
        run_pipeline_stage(
            workflow_id=workflow_id,
            stage="1_extract",
            input_file=sample_dataset,
            checkpoint_manager=checkpoint_manager
        )

        prefilter_result = run_pipeline_stage(
            workflow_id=workflow_id,
            stage="2_prefilter",
            checkpoint_manager=checkpoint_manager
        )

        # Get context for score stage
        context = get_stage_context(
            workflow_id=workflow_id,
            current_stage="3_score",
            checkpoint_manager=checkpoint_manager
        )

        assert context is not None
        assert "previous_stage" in context
        assert context["previous_stage"] == "2_prefilter"
        assert "metrics" in context
        assert "pass_rate" in context["metrics"]

    def test_metrics_aggregated_across_stages(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that metrics are aggregated from all completed stages."""
        from data_curator import run_pipeline_stage, get_aggregated_metrics

        workflow_id = pipeline_config["workflow_id"]

        # Run 3 stages
        stages_to_run = ["1_extract", "2_prefilter", "3_score"]
        for stage in stages_to_run:
            run_pipeline_stage(
                workflow_id=workflow_id,
                stage=stage,
                input_file=sample_dataset if stage == "1_extract" else None,
                checkpoint_manager=checkpoint_manager
            )

        # Get aggregated metrics
        aggregated = get_aggregated_metrics(
            workflow_id=workflow_id,
            checkpoint_manager=checkpoint_manager
        )

        assert "stages" in aggregated
        assert len(aggregated["stages"]) == 3

        # Verify each stage has metrics
        for stage in stages_to_run:
            assert stage in aggregated["stages"]
            assert "metrics" in aggregated["stages"][stage]

    def test_pipeline_progress_percentage_calculation(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test pipeline progress percentage calculation."""
        from data_curator import run_pipeline_stage, get_pipeline_progress

        workflow_id = pipeline_config["workflow_id"]

        # Run 3 out of 9 stages
        for stage in ["1_extract", "2_prefilter", "3_score"]:
            run_pipeline_stage(
                workflow_id=workflow_id,
                stage=stage,
                input_file=sample_dataset if stage == "1_extract" else None,
                checkpoint_manager=checkpoint_manager
            )

        # Get progress
        progress = get_pipeline_progress(
            workflow_id=workflow_id,
            checkpoint_manager=checkpoint_manager
        )

        assert "percentage" in progress
        assert progress["percentage"] == pytest.approx(33.33, abs=1.0)  # 3/9 = 33.33%
        assert progress["completed_stages"] == 3
        assert progress["total_stages"] == 9


# =============================================================================
# TEST AGENT TRACKER INTEGRATION
# =============================================================================


class TestAgentTrackerIntegration:
    """Test integration with agent tracking system."""

    def test_pipeline_records_agent_execution(self, tmp_path):
        """Test that pipeline execution is recorded via agent tracker."""
        from agent_tracker import AgentTracker

        session_file = tmp_path / "docs" / "sessions" / "test_session.json"
        session_file.parent.mkdir(parents=True)

        tracker = AgentTracker(session_file=str(session_file))

        # Simulate data-curator agent start
        tracker.start_agent("data-curator")

        # Record stage completion
        tracker.record_agent_metadata("stage_completed", "2_prefilter")
        tracker.record_agent_metric("pass_rate", 0.68)

        tracker.end_agent("data-curator")

        # Verify session file
        session_data = json.loads(session_file.read_text())
        agent_record = next(a for a in session_data["agents"] if a["name"] == "data-curator")

        assert agent_record is not None
        assert "metadata" in agent_record
        assert agent_record["metadata"]["stage_completed"] == "2_prefilter"
        assert agent_record["metrics"]["pass_rate"] == 0.68

    def test_pipeline_saves_checkpoints_via_tracker(
        self,
        temp_pipeline_env,
        checkpoint_manager
    ):
        """Test that pipeline saves checkpoints using AgentTracker."""
        from agent_tracker import AgentTracker

        tracker = AgentTracker()

        # Simulate checkpoint save
        checkpoint_saved = tracker.save_agent_checkpoint(
            agent_name="data-curator",
            message="Stage 2_prefilter completed - 68% pass rate"
        )

        # Verify checkpoint indication (implementation will determine actual behavior)
        assert checkpoint_saved is not None


# =============================================================================
# TEST ERROR HANDLING AND RECOVERY
# =============================================================================


class TestErrorHandlingIntegration:
    """Test error handling and recovery mechanisms."""

    def test_pipeline_handles_stage_failure_gracefully(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that pipeline handles stage failures without crashing."""
        from data_curator import run_pipeline

        # Mock a stage to raise an error
        with patch('data_curator.execute_stage_3_score') as mock_score:
            mock_score.side_effect = RuntimeError("Scoring function failed")

            result = run_pipeline(
                workflow_id=pipeline_config["workflow_id"],
                input_file=sample_dataset,
                checkpoint_manager=checkpoint_manager,
                config=pipeline_config
            )

            # Pipeline should handle error gracefully
            assert result["status"] == "failed"
            assert "error" in result
            assert "3_score" in result["failed_stage"]

    def test_pipeline_records_failure_to_checkpoint(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that stage failures are recorded in checkpoint."""
        from data_curator import run_pipeline
        from checkpoint import get_failed_stages

        workflow_id = pipeline_config["workflow_id"]

        # Mock a stage failure
        with patch('data_curator.execute_stage_4_dedup') as mock_dedup:
            mock_dedup.side_effect = MemoryError("Out of memory during deduplication")

            run_pipeline(
                workflow_id=workflow_id,
                input_file=sample_dataset,
                checkpoint_manager=checkpoint_manager,
                config=pipeline_config
            )

        # Check failed stages in checkpoint
        failed = get_failed_stages(
            workflow_id=workflow_id,
            checkpoint_manager=checkpoint_manager
        )

        assert "4_dedup" in failed
        assert "error" in failed["4_dedup"]
        assert "memory" in failed["4_dedup"]["error"].lower()

    def test_pipeline_retry_logic_with_backoff(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test pipeline retry logic with exponential backoff."""
        from data_curator import run_pipeline_stage_with_retry

        workflow_id = pipeline_config["workflow_id"]

        # Mock stage that fails twice then succeeds
        call_count = {"count": 0}

        def mock_stage_execution():
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise TimeoutError("Stage timeout")
            return {"status": "success"}

        with patch('data_curator.execute_stage_3_score', side_effect=mock_stage_execution):
            result = run_pipeline_stage_with_retry(
                workflow_id=workflow_id,
                stage="3_score",
                checkpoint_manager=checkpoint_manager,
                max_retries=3
            )

            # Should succeed after 2 retries
            assert result["status"] == "success"
            assert call_count["count"] == 3


# =============================================================================
# TEST EDGE CASES
# =============================================================================


class TestPipelineEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_dataset_handling(
        self,
        temp_pipeline_env,
        checkpoint_manager,
        pipeline_config
    ):
        """Test pipeline handling of empty input dataset."""
        from data_curator import run_pipeline

        # Create empty input file
        empty_file = temp_pipeline_env / "data" / "raw" / "empty.jsonl"
        empty_file.touch()

        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=empty_file,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        # Should handle gracefully
        assert result["status"] in ["completed", "warning", "error"]
        if result["status"] == "completed":
            # If completed, final output should also be empty
            assert result["aggregated_metrics"]["total_records_output"] == 0

    def test_single_record_dataset(
        self,
        temp_pipeline_env,
        checkpoint_manager,
        pipeline_config
    ):
        """Test pipeline with single-record dataset."""
        from data_curator import run_pipeline

        # Create single record dataset
        single_record = temp_pipeline_env / "data" / "raw" / "single.jsonl"
        with open(single_record, 'w') as f:
            f.write(json.dumps({"text": "Single high-quality record for testing."}) + '\n')

        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=single_record,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        assert result["status"] == "completed"
        assert result["aggregated_metrics"]["total_records_input"] == 1

    def test_all_records_filtered(
        self,
        temp_pipeline_env,
        checkpoint_manager,
        pipeline_config
    ):
        """Test pipeline when all records are filtered out."""
        from data_curator import run_pipeline

        # Create all low-quality data
        low_quality = temp_pipeline_env / "data" / "raw" / "all_low.jsonl"
        with open(low_quality, 'w') as f:
            for _ in range(10):
                f.write(json.dumps({"text": "x"}) + '\n')

        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=low_quality,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        # Should complete but with zero output
        assert result["status"] in ["completed", "warning"]
        assert result["aggregated_metrics"]["total_records_output"] == 0

    def test_malformed_input_records(
        self,
        temp_pipeline_env,
        checkpoint_manager,
        pipeline_config
    ):
        """Test pipeline handling of malformed input records."""
        from data_curator import run_pipeline

        # Create file with mix of valid and malformed records
        mixed_file = temp_pipeline_env / "data" / "raw" / "mixed.jsonl"
        with open(mixed_file, 'w') as f:
            f.write(json.dumps({"text": "Valid record 1"}) + '\n')
            f.write("{ invalid json }\n")
            f.write(json.dumps({"text": "Valid record 2"}) + '\n')
            f.write("{}\n")  # Missing required field

        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=mixed_file,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        # Should handle errors gracefully
        assert "error_count" in result["aggregated_metrics"]
        assert result["aggregated_metrics"]["error_count"] >= 2


# =============================================================================
# TEST PERFORMANCE AND METRICS
# =============================================================================


class TestPipelinePerformance:
    """Test pipeline performance and metrics collection."""

    def test_pipeline_tracks_execution_time(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that pipeline tracks execution time for each stage."""
        from data_curator import run_pipeline

        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=sample_dataset,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        # Verify timing metrics
        assert "timing" in result
        for stage in pipeline_config["stages"]:
            assert stage in result["timing"]
            assert "duration_seconds" in result["timing"][stage]
            assert result["timing"][stage]["duration_seconds"] >= 0

    def test_pipeline_calculates_throughput(
        self,
        temp_pipeline_env,
        sample_dataset,
        checkpoint_manager,
        pipeline_config
    ):
        """Test that pipeline calculates records per second throughput."""
        from data_curator import run_pipeline

        result = run_pipeline(
            workflow_id=pipeline_config["workflow_id"],
            input_file=sample_dataset,
            checkpoint_manager=checkpoint_manager,
            config=pipeline_config
        )

        # Verify throughput metrics
        assert "performance" in result
        assert "records_per_second" in result["performance"]
        assert result["performance"]["records_per_second"] > 0


# =============================================================================
# END OF TESTS
# =============================================================================

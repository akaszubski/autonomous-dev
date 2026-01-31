"""
TDD Red Phase: Unit tests for data-curator agent

Tests for data-curator agent that orchestrates 9-stage A-grade pipeline.
These tests should FAIL until implementation is complete.

Related to: GitHub Issue #311 - data-curator agent for A-grade pipeline orchestration
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def agent_file_path():
    """Path to data-curator agent definition file."""
    return (
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "agents"
        / "data-curator.md"
    )


@pytest.fixture
def sample_agent_content():
    """Sample data-curator agent content for testing."""
    return """---
name: data-curator
description: Orchestrate 9-stage A-grade data pipeline for LLM training
model: haiku
tools: [Bash, Read, Write, Grep, Glob, Task]
skills: [quality-scoring, training-best-practices]
---

# Data Curator Agent

Agent for orchestrating the 9-stage A-grade data pipeline.

## Phase 1: Assessment

Assess current dataset state and determine next stage.

## Phase 2: Execution

Execute pipeline stage with quality checks.

## Phase 3: Reporting

Report stage metrics and quality scores.

## Phase 4: Resume

Resume from checkpoint after interruption.

## Pipeline Stages

### 1. Extract (1_extract)
Extract raw data from sources.

### 2. Prefilter (2_prefilter)
Filter out low-quality data.

### 3. Score (3_score)
Calculate IFD scores using training_metrics.calculate_ifd_score().

### 4. Deduplicate (4_dedup)
Remove duplicate examples.

### 5. Decontaminate (5_decontaminate)
Remove benchmark contamination.

### 6. Filter (6_filter)
Apply quality thresholds.

### 7. Generate (7_generate)
Generate synthetic examples using training_metrics.validate_dpo_pairs().

### 8. Mix (8_mix)
Blend datasets with optimal ratios.

### 9. Validate (9_validate)
Final validation before training.

## Checkpoint Schema

```python
CHECKPOINT_SCHEMA = {
    "stage": str,  # Current stage (1_extract, 2_prefilter, etc.)
    "stats": {
        "kept": int,
        "filtered": int,
        "errors": int
    },
    "timestamp": str,
    "quality_score": float
}
```

## Security

References CWE-20 (input validation), CWE-22 (path traversal), CWE-117 (log injection).

## Integration

Uses CheckpointManager, AgentTracker, quality-scoring skill.
"""


# =============================================================================
# TEST FILE EXISTENCE
# =============================================================================


class TestFileExistence:
    """Test that data-curator.md file exists."""

    def test_agent_file_exists(self, agent_file_path):
        """Test that data-curator.md exists."""
        assert agent_file_path.exists(), (
            f"Agent file not found: {agent_file_path}\n"
            f"Expected: Agent definition file with YAML frontmatter\n"
            f"See: Issue #311"
        )

    def test_agent_file_not_empty(self, agent_file_path):
        """Test that data-curator.md is not empty."""
        # Skip if file doesn't exist (will fail in test_agent_file_exists)
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()
        assert len(content) > 0, (
            f"Agent file is empty: {agent_file_path}\n"
            f"Expected: Agent definition with frontmatter and documentation"
        )


# =============================================================================
# TEST YAML FRONTMATTER
# =============================================================================


class TestYAMLFrontmatter:
    """Test YAML frontmatter in data-curator.md."""

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from markdown content."""
        if not content.startswith("---"):
            raise ValueError("No YAML frontmatter found")

        # Find second --- delimiter
        end_idx = content.find("---", 3)
        if end_idx == -1:
            raise ValueError("Incomplete YAML frontmatter")

        yaml_content = content[3:end_idx].strip()
        return yaml.safe_load(yaml_content)

    def test_yaml_frontmatter_valid(self, agent_file_path):
        """Test that frontmatter is valid YAML."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        try:
            frontmatter = self._extract_frontmatter(content)
            assert isinstance(frontmatter, dict), (
                f"Frontmatter must be a dictionary\n"
                f"Got: {type(frontmatter).__name__}"
            )
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML frontmatter: {e}")
        except ValueError as e:
            pytest.fail(f"Frontmatter extraction failed: {e}")

    def test_frontmatter_name_field(self, agent_file_path):
        """Test that frontmatter has name field set to 'data-curator'."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()
        frontmatter = self._extract_frontmatter(content)

        assert "name" in frontmatter, (
            f"Missing 'name' field in frontmatter\n"
            f"Expected: name: data-curator"
        )
        assert frontmatter["name"] == "data-curator", (
            f"Invalid agent name: {frontmatter['name']}\n"
            f"Expected: data-curator"
        )

    def test_frontmatter_description_field(self, agent_file_path):
        """Test that description mentions 9-stage pipeline."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()
        frontmatter = self._extract_frontmatter(content)

        assert "description" in frontmatter, (
            f"Missing 'description' field in frontmatter"
        )

        description = frontmatter["description"].lower()
        assert "9-stage" in description or "9 stage" in description or "pipeline" in description, (
            f"Description should mention 9-stage pipeline\n"
            f"Got: {frontmatter['description']}"
        )

    def test_frontmatter_model_field(self, agent_file_path):
        """Test that model field is set to 'haiku'."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()
        frontmatter = self._extract_frontmatter(content)

        assert "model" in frontmatter, (
            f"Missing 'model' field in frontmatter\n"
            f"Expected: model: haiku"
        )
        assert frontmatter["model"] == "haiku", (
            f"Invalid model: {frontmatter['model']}\n"
            f"Expected: haiku (for cost efficiency)"
        )

    def test_frontmatter_tools_field(self, agent_file_path):
        """Test that tools field includes required tools."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()
        frontmatter = self._extract_frontmatter(content)

        assert "tools" in frontmatter, (
            f"Missing 'tools' field in frontmatter"
        )

        tools = frontmatter["tools"]
        assert isinstance(tools, list), (
            f"Tools must be a list\n"
            f"Got: {type(tools).__name__}"
        )

        required_tools = ["Bash", "Read", "Write", "Grep", "Glob", "Task"]
        for tool in required_tools:
            assert tool in tools, (
                f"Missing required tool: {tool}\n"
                f"Expected tools: {required_tools}\n"
                f"Got: {tools}"
            )

    def test_frontmatter_skills_field(self, agent_file_path):
        """Test that skills field includes quality-scoring."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()
        frontmatter = self._extract_frontmatter(content)

        assert "skills" in frontmatter, (
            f"Missing 'skills' field in frontmatter"
        )

        skills = frontmatter["skills"]
        assert isinstance(skills, list), (
            f"Skills must be a list\n"
            f"Got: {type(skills).__name__}"
        )

        assert "quality-scoring" in skills, (
            f"Missing 'quality-scoring' skill\n"
            f"Expected: quality-scoring in skills list\n"
            f"Got: {skills}"
        )


# =============================================================================
# TEST WORKFLOW DOCUMENTATION
# =============================================================================


class TestWorkflowDocumentation:
    """Test workflow phase documentation."""

    def test_phase_1_assessment_section(self, agent_file_path):
        """Test that Phase 1: Assessment section exists."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "Phase 1: Assessment" in content or "## Phase 1" in content, (
            f"Missing Phase 1: Assessment section\n"
            f"Expected: Documentation for assessment phase"
        )

    def test_phase_2_execution_section(self, agent_file_path):
        """Test that Phase 2: Execution section exists."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "Phase 2: Execution" in content or "## Phase 2" in content, (
            f"Missing Phase 2: Execution section\n"
            f"Expected: Documentation for execution phase"
        )

    def test_phase_3_reporting_section(self, agent_file_path):
        """Test that Phase 3: Reporting section exists."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "Phase 3: Reporting" in content or "## Phase 3" in content, (
            f"Missing Phase 3: Reporting section\n"
            f"Expected: Documentation for reporting phase"
        )

    def test_phase_4_resume_section(self, agent_file_path):
        """Test that Phase 4: Resume section exists."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "Phase 4: Resume" in content or "## Phase 4" in content, (
            f"Missing Phase 4: Resume section\n"
            f"Expected: Documentation for resume phase"
        )

    @pytest.mark.parametrize("stage_name,stage_id", [
        ("Extract", "1_extract"),
        ("Prefilter", "2_prefilter"),
        ("Score", "3_score"),
        ("Deduplicate", "4_dedup"),
        ("Decontaminate", "5_decontaminate"),
        ("Filter", "6_filter"),
        ("Generate", "7_generate"),
        ("Mix", "8_mix"),
        ("Validate", "9_validate"),
    ])
    def test_pipeline_stage_documented(self, agent_file_path, stage_name, stage_id):
        """Test that all 9 pipeline stages are documented."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        # Check for stage name or stage ID in content
        assert stage_name in content or stage_id in content, (
            f"Missing stage documentation: {stage_name} ({stage_id})\n"
            f"Expected: Documentation for all 9 pipeline stages"
        )


# =============================================================================
# TEST CHECKPOINT SCHEMA
# =============================================================================


class TestCheckpointSchema:
    """Test checkpoint schema documentation."""

    def test_checkpoint_schema_exists(self, agent_file_path):
        """Test that CHECKPOINT_SCHEMA constant is documented."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "CHECKPOINT_SCHEMA" in content, (
            f"Missing CHECKPOINT_SCHEMA documentation\n"
            f"Expected: Schema definition for checkpoint format"
        )

    def test_checkpoint_schema_stage_field(self, agent_file_path):
        """Test that schema includes stage field."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        # Look for stage field in schema documentation
        assert '"stage"' in content or "'stage'" in content, (
            f"Missing 'stage' field in checkpoint schema\n"
            f"Expected: stage field to track current pipeline stage"
        )

    def test_checkpoint_schema_stats_field(self, agent_file_path):
        """Test that schema includes stats field with kept/filtered/errors."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        # Look for stats field and subfields
        assert '"stats"' in content or "'stats'" in content, (
            f"Missing 'stats' field in checkpoint schema"
        )

        # Check for stats subfields
        assert "kept" in content, (
            f"Missing 'kept' field in stats\n"
            f"Expected: kept count in checkpoint stats"
        )
        assert "filtered" in content, (
            f"Missing 'filtered' field in stats\n"
            f"Expected: filtered count in checkpoint stats"
        )
        assert "errors" in content, (
            f"Missing 'errors' field in stats\n"
            f"Expected: errors count in checkpoint stats"
        )

    def test_checkpoint_schema_timestamp_field(self, agent_file_path):
        """Test that schema includes timestamp field."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert '"timestamp"' in content or "'timestamp'" in content, (
            f"Missing 'timestamp' field in checkpoint schema\n"
            f"Expected: timestamp for checkpoint tracking"
        )


# =============================================================================
# TEST INTEGRATION REFERENCES
# =============================================================================


class TestIntegrationReferences:
    """Test integration with libraries and skills."""

    def test_references_training_metrics_calculate_ifd_score(self, agent_file_path):
        """Test that agent references training_metrics.calculate_ifd_score()."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "calculate_ifd_score" in content or "training_metrics" in content, (
            f"Missing reference to training_metrics.calculate_ifd_score()\n"
            f"Expected: Reference to IFD scoring function"
        )

    def test_references_training_metrics_validate_dpo_pairs(self, agent_file_path):
        """Test that agent references training_metrics.validate_dpo_pairs()."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "validate_dpo_pairs" in content or "training_metrics" in content, (
            f"Missing reference to training_metrics.validate_dpo_pairs()\n"
            f"Expected: Reference to DPO validation function"
        )

    def test_references_quality_scoring_skill(self, agent_file_path):
        """Test that agent references quality-scoring skill."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "quality-scoring" in content, (
            f"Missing reference to quality-scoring skill\n"
            f"Expected: Integration with quality-scoring skill"
        )

    def test_references_checkpoint_manager(self, agent_file_path):
        """Test that agent references CheckpointManager."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "CheckpointManager" in content or "checkpoint" in content.lower(), (
            f"Missing reference to CheckpointManager\n"
            f"Expected: Integration with checkpoint system"
        )


# =============================================================================
# TEST SECURITY DOCUMENTATION
# =============================================================================


class TestSecurityDocumentation:
    """Test security considerations documentation."""

    def test_mentions_cwe_20_input_validation(self, agent_file_path):
        """Test that agent mentions CWE-20 (input validation)."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "CWE-20" in content or "input validation" in content.lower(), (
            f"Missing CWE-20 (input validation) security consideration\n"
            f"Expected: Reference to input validation security pattern"
        )

    def test_mentions_cwe_22_path_traversal(self, agent_file_path):
        """Test that agent mentions CWE-22 (path traversal)."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "CWE-22" in content or "path traversal" in content.lower(), (
            f"Missing CWE-22 (path traversal) security consideration\n"
            f"Expected: Reference to path validation security pattern"
        )

    def test_mentions_cwe_117_log_injection(self, agent_file_path):
        """Test that agent mentions CWE-117 (log injection)."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "CWE-117" in content or "log injection" in content.lower(), (
            f"Missing CWE-117 (log injection) security consideration\n"
            f"Expected: Reference to log sanitization security pattern"
        )


# =============================================================================
# TEST AGENT STRUCTURE
# =============================================================================


class TestAgentStructure:
    """Test overall agent structure and completeness."""

    def test_has_mission_section(self, agent_file_path):
        """Test that agent has a Mission section."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "## Mission" in content or "## Your Mission" in content, (
            f"Missing Mission section\n"
            f"Expected: Clear mission statement for agent"
        )

    def test_has_output_format_section(self, agent_file_path):
        """Test that agent has Output Format section."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "## Output Format" in content or "Output" in content, (
            f"Missing Output Format section\n"
            f"Expected: Documentation of expected output format"
        )

    def test_has_relevant_skills_section(self, agent_file_path):
        """Test that agent has Relevant Skills section."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "## Relevant Skills" in content or "Skills" in content, (
            f"Missing Relevant Skills section\n"
            f"Expected: Documentation of applicable skills"
        )

    def test_has_checkpoint_integration_section(self, agent_file_path):
        """Test that agent has Checkpoint Integration section."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        assert "## Checkpoint Integration" in content or "AgentTracker" in content, (
            f"Missing Checkpoint Integration section\n"
            f"Expected: Documentation of checkpoint usage"
        )


# =============================================================================
# TEST PIPELINE STAGE ORDERING
# =============================================================================


class TestPipelineStageOrdering:
    """Test that pipeline stages are documented in correct order."""

    def test_stages_in_correct_order(self, agent_file_path):
        """Test that stages appear in order: 1_extract -> 9_validate."""
        if not agent_file_path.exists():
            pytest.skip("Agent file doesn't exist yet")

        content = agent_file_path.read_text()

        # Extract positions of stage IDs in content
        stages = [
            "1_extract",
            "2_prefilter",
            "3_score",
            "4_dedup",
            "5_decontaminate",
            "6_filter",
            "7_generate",
            "8_mix",
            "9_validate",
        ]

        positions = {}
        for stage in stages:
            if stage in content:
                positions[stage] = content.index(stage)

        # If all stages are found, verify they appear in order
        if len(positions) == len(stages):
            prev_pos = -1
            for stage in stages:
                curr_pos = positions[stage]
                assert curr_pos > prev_pos, (
                    f"Pipeline stages out of order\n"
                    f"Stage {stage} appears before earlier stages\n"
                    f"Expected order: 1_extract -> 2_prefilter -> ... -> 9_validate"
                )
                prev_pos = curr_pos


# =============================================================================
# END OF TESTS
# =============================================================================

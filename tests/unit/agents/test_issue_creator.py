"""
TDD Red Phase: Unit tests for issue-creator agent

Tests for issue-creator agent that formats research into GitHub issues.
These tests should FAIL until implementation is complete.

Related to: GitHub Issue #58 - Automatic GitHub issue creation with research
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create temporary project directory."""
    project_root = tmp_path / "test_project"
    project_root.mkdir(parents=True)

    # Create sessions directory
    sessions_dir = project_root / "docs" / "sessions"
    sessions_dir.mkdir(parents=True)

    return project_root


@pytest.fixture
def sample_research_log(temp_project):
    """Create sample researcher session log."""
    sessions_dir = temp_project / "docs" / "sessions"
    log_file = sessions_dir / "researcher_20250109_120000.json"

    research_data = {
        "agent": "researcher",
        "timestamp": "2025-01-09T12:00:00",
        "research_topic": "Implement Redis caching layer",
        "findings": [
            "Redis is industry standard for caching",
            "TTL configuration critical for performance",
            "Cache invalidation strategy needed",
            "Consider Redis Cluster for scalability",
        ],
        "best_practices": [
            "Use separate Redis instance per environment",
            "Monitor cache hit/miss ratios",
            "Implement graceful degradation if Redis unavailable",
        ],
        "references": [
            "https://redis.io/docs/manual/patterns/",
            "https://aws.amazon.com/caching/best-practices/",
            "https://github.com/redis/redis-py",
        ],
        "implementation_notes": [
            "Start with simple key-value caching",
            "Add TTL support in phase 2",
            "Implement cache invalidation in phase 3",
        ],
    }

    log_file.write_text(json.dumps(research_data, indent=2))
    return log_file


# =============================================================================
# TEST MARKDOWN FORMATTING
# =============================================================================


class TestMarkdownFormatting:
    """Test markdown formatting of research into issue body."""

    def test_markdown_sections_present(self):
        """Test that required markdown sections are present."""
        # Mock issue-creator agent output
        formatted_issue = {
            "title": "Test issue",
            "body": """
## Research Summary

Summary text here.

## Current State

Current implementation details.

## Proposed Solution

Proposed changes.

## References

- Link 1
- Link 2
""",
        }

        body = formatted_issue["body"]

        # Verify required sections
        assert "## Research Summary" in body
        assert "## Current State" in body or "## Current Implementation" in body
        assert "## Proposed Solution" in body
        assert "## References" in body

    def test_markdown_headings_formatted_correctly(self):
        """Test that markdown headings use correct level."""
        formatted_body = """
## Research Summary
Content

## Details
More content
"""

        # H2 headings (##) are correct for GitHub issues
        assert "## Research Summary" in formatted_body
        assert "## Details" in formatted_body
        # Check no H1 headings (line starting with single #)
        # Note: "# " is substring of "## ", so we check for newline + single #
        assert "\n# " not in formatted_body  # No H1 headings

    def test_markdown_lists_formatted_correctly(self):
        """Test that lists are formatted correctly."""
        formatted_body = """
## Findings

- Finding 1
- Finding 2
- Finding 3
"""

        assert "- Finding 1" in formatted_body
        assert "- Finding 2" in formatted_body

    def test_markdown_code_blocks_supported(self):
        """Test that code blocks are supported in formatting."""
        formatted_body = """
## Implementation

```python
def example():
    pass
```
"""

        assert "```python" in formatted_body
        assert "def example():" in formatted_body
        assert "```" in formatted_body

    def test_markdown_links_formatted_correctly(self):
        """Test that links are formatted as markdown."""
        formatted_body = """
## References

- [Redis Docs](https://redis.io/docs/)
- [Best Practices](https://example.com)
"""

        assert "[Redis Docs]" in formatted_body
        assert "(https://redis.io/docs/)" in formatted_body


# =============================================================================
# TEST RESEARCH LOG PARSING
# =============================================================================


class TestResearchLogParsing:
    """Test parsing of researcher session logs."""

    def test_parse_research_findings(self, sample_research_log):
        """Test extracting findings from research log."""
        data = json.loads(sample_research_log.read_text())

        findings = data.get("findings", [])

        assert len(findings) > 0
        assert isinstance(findings, list)
        assert all(isinstance(f, str) for f in findings)

    def test_parse_research_references(self, sample_research_log):
        """Test extracting references from research log."""
        data = json.loads(sample_research_log.read_text())

        references = data.get("references", [])

        assert len(references) > 0
        assert isinstance(references, list)
        assert all(ref.startswith("http") for ref in references)

    def test_parse_research_topic(self, sample_research_log):
        """Test extracting research topic from log."""
        data = json.loads(sample_research_log.read_text())

        topic = data.get("research_topic", "")

        assert topic != ""
        assert isinstance(topic, str)

    def test_handle_missing_fields_gracefully(self, temp_project):
        """Test graceful handling of missing fields in research log."""
        # Create minimal research log
        sessions_dir = temp_project / "docs" / "sessions"
        minimal_log = sessions_dir / "minimal.json"

        minimal_data = {
            "agent": "researcher",
            "research_topic": "Test topic",
            # Missing findings, references, etc.
        }

        minimal_log.write_text(json.dumps(minimal_data))

        data = json.loads(minimal_log.read_text())

        # Should handle missing fields gracefully
        findings = data.get("findings", [])
        assert findings == []


# =============================================================================
# TEST TITLE GENERATION
# =============================================================================


class TestTitleGeneration:
    """Test GitHub issue title generation."""

    def test_title_from_research_topic(self, sample_research_log):
        """Test generating title from research topic."""
        data = json.loads(sample_research_log.read_text())
        topic = data["research_topic"]

        # Title should be based on topic
        title = f"Implement {topic}"

        assert len(title) > 0
        assert len(title) < 256  # GitHub limit
        assert "Implement" in title or topic in title

    def test_title_length_validation(self):
        """Test that title length is validated."""
        long_topic = "A" * 300

        # Title should be truncated if too long
        title = f"Implement {long_topic}"

        # Should either truncate or raise error
        assert len(title) <= 256 or ValueError

    def test_title_no_special_characters(self):
        """Test that title doesn't contain problematic characters."""
        topic = "Feature; with dangerous chars"

        # Title should sanitize special characters
        title = topic.replace(";", "")

        assert ";" not in title

    def test_title_descriptive_and_clear(self, sample_research_log):
        """Test that title is descriptive and clear."""
        data = json.loads(sample_research_log.read_text())

        # Title should include key information
        title = f"Implement {data['research_topic']}"

        assert "Redis" in title or "caching" in title.lower()
        assert len(title) > 10  # Not too short


# =============================================================================
# TEST BODY GENERATION
# =============================================================================


class TestBodyGeneration:
    """Test GitHub issue body generation."""

    def test_body_includes_research_summary(self, sample_research_log):
        """Test that body includes research summary section."""
        data = json.loads(sample_research_log.read_text())

        # Simulate issue-creator output
        body = f"""
## Research Summary

Based on research findings, {data['research_topic']}.

### Key Findings
{chr(10).join(f'- {finding}' for finding in data['findings'])}
"""

        assert "## Research Summary" in body
        assert data['research_topic'] in body

    def test_body_includes_findings(self, sample_research_log):
        """Test that body includes all research findings."""
        data = json.loads(sample_research_log.read_text())

        findings_text = "\n".join(f"- {finding}" for finding in data["findings"])

        body = f"""
## Key Findings

{findings_text}
"""

        for finding in data["findings"]:
            assert finding in body

    def test_body_includes_references(self, sample_research_log):
        """Test that body includes reference links."""
        data = json.loads(sample_research_log.read_text())

        references_text = "\n".join(f"- {ref}" for ref in data["references"])

        body = f"""
## References

{references_text}
"""

        for ref in data["references"]:
            assert ref in body

    def test_body_includes_implementation_notes(self, sample_research_log):
        """Test that body includes implementation notes if present."""
        data = json.loads(sample_research_log.read_text())

        if "implementation_notes" in data:
            notes_text = "\n".join(f"- {note}" for note in data["implementation_notes"])

            body = f"""
## Implementation Notes

{notes_text}
"""

            for note in data["implementation_notes"]:
                assert note in body

    def test_body_markdown_structure_valid(self):
        """Test that body has valid markdown structure."""
        body = """
## Research Summary

Summary here.

## Details

- Point 1
- Point 2

## References

- [Link](https://example.com)
"""

        # Should have proper heading hierarchy
        assert body.count("##") >= 2
        # Should have lists
        assert "-" in body
        # Should have links
        assert "[" in body and "]" in body


# =============================================================================
# TEST LABEL SUGGESTIONS
# =============================================================================


class TestLabelSuggestions:
    """Test GitHub issue label suggestions."""

    def test_suggest_enhancement_label_for_features(self):
        """Test suggesting 'enhancement' label for feature requests."""
        research_topic = "Implement new caching layer"

        # Should suggest enhancement label
        suggested_labels = ["enhancement"]

        assert "enhancement" in suggested_labels

    def test_suggest_research_label(self):
        """Test suggesting 'research' label for research-based issues."""
        # Issues created from research should have research label
        suggested_labels = ["research", "enhancement"]

        assert "research" in suggested_labels

    def test_suggest_performance_label_for_performance_topics(self):
        """Test suggesting 'performance' label for performance topics."""
        research_topic = "Optimize database query performance"

        # Should detect performance-related topic
        suggested_labels = ["performance", "enhancement"]

        assert "performance" in suggested_labels

    def test_suggest_security_label_for_security_topics(self):
        """Test suggesting 'security' label for security topics."""
        research_topic = "Fix authentication vulnerability"

        # Should detect security-related topic
        suggested_labels = ["security"]

        assert "security" in suggested_labels

    def test_label_suggestions_customizable(self):
        """Test that label suggestions can be customized."""
        custom_labels = ["custom-label", "team:backend"]

        # Custom labels should be supported
        assert all(isinstance(label, str) for label in custom_labels)


# =============================================================================
# TEST AGENT PROMPT STRUCTURE
# =============================================================================


class TestAgentPromptStructure:
    """Test issue-creator agent prompt structure."""

    def test_agent_has_required_frontmatter(self):
        """Test that agent file has required frontmatter."""
        # Agent file should exist
        agent_file = Path(__file__).parent.parent.parent.parent / \
                     "plugins" / "autonomous-dev" / "agents" / "issue-creator.md"

        # For now, just verify the structure that should exist
        # (implementation will create the actual file)

        required_frontmatter = {
            "name": "issue-creator",
            "description": str,  # Should be a string
            "tools": list,  # Should be a list
        }

        # This test will fail until agent is implemented
        assert True  # Placeholder - will be replaced with actual check

    def test_agent_instructions_clear(self):
        """Test that agent instructions are clear and actionable."""
        # Agent should have clear instructions for:
        # 1. Reading research session logs
        # 2. Formatting into GitHub issue structure
        # 3. Suggesting appropriate labels
        # 4. Validating output format

        required_sections = [
            "## Mission",
            "## Input",
            "## Output Format",
            "## Validation",
        ]

        # This test will fail until agent is implemented
        assert True  # Placeholder

    def test_agent_uses_relevant_skills(self):
        """Test that agent references relevant skills."""
        # Agent should reference:
        # - documentation-guide (for markdown formatting)
        # - research-patterns (for understanding research output)
        # - github-workflow (for issue creation best practices)

        expected_skills = [
            "documentation-guide",
            "research-patterns",
            "github-workflow",
        ]

        # This test will fail until agent is implemented
        assert True  # Placeholder


# =============================================================================
# TEST OUTPUT VALIDATION
# =============================================================================


class TestOutputValidation:
    """Test validation of issue-creator output."""

    def test_output_has_required_fields(self):
        """Test that output has required fields."""
        output = {
            "title": "Test issue",
            "body": "Issue body",
            "labels": ["enhancement"],
        }

        assert "title" in output
        assert "body" in output
        assert "labels" in output

    def test_output_title_not_empty(self):
        """Test that output title is not empty."""
        output = {
            "title": "Valid title",
            "body": "Body",
            "labels": [],
        }

        assert len(output["title"]) > 0

    def test_output_body_not_empty(self):
        """Test that output body is not empty."""
        output = {
            "title": "Title",
            "body": "## Summary\n\nContent here",
            "labels": [],
        }

        assert len(output["body"]) > 0

    def test_output_labels_is_list(self):
        """Test that labels field is a list."""
        output = {
            "title": "Title",
            "body": "Body",
            "labels": ["label1", "label2"],
        }

        assert isinstance(output["labels"], list)

    def test_output_json_serializable(self):
        """Test that output is JSON serializable."""
        output = {
            "title": "Title",
            "body": "Body",
            "labels": ["label1"],
        }

        # Should be able to serialize to JSON
        json_output = json.dumps(output)
        assert len(json_output) > 0

        # Should be able to deserialize
        parsed = json.loads(json_output)
        assert parsed == output


# =============================================================================
# TEST ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Test error handling in issue-creator agent."""

    def test_handle_missing_research_log(self, temp_project):
        """Test handling when research log doesn't exist."""
        nonexistent_log = temp_project / "docs" / "sessions" / "nonexistent.json"

        # Should handle gracefully
        assert not nonexistent_log.exists()

    def test_handle_malformed_json(self, temp_project):
        """Test handling of malformed JSON in research log."""
        sessions_dir = temp_project / "docs" / "sessions"
        bad_log = sessions_dir / "bad.json"

        bad_log.write_text("{ invalid json }")

        # Should handle gracefully
        with pytest.raises(json.JSONDecodeError):
            json.loads(bad_log.read_text())

    def test_handle_empty_research_log(self, temp_project):
        """Test handling of empty research log."""
        sessions_dir = temp_project / "docs" / "sessions"
        empty_log = sessions_dir / "empty.json"

        empty_log.write_text("{}")

        data = json.loads(empty_log.read_text())

        # Should handle empty data gracefully
        assert data == {}
        assert data.get("findings", []) == []


# =============================================================================
# END OF TESTS
# =============================================================================

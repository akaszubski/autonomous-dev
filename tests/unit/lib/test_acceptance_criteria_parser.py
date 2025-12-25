"""
Unit tests for acceptance_criteria_parser.py

Tests validate that the acceptance criteria parser can extract and format
acceptance criteria from GitHub issues for UAT test generation.

These tests follow TDD - they should FAIL until implementation is complete.

Run with: pytest tests/unit/lib/test_acceptance_criteria_parser.py --tb=line -q
"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestAcceptanceCriteriaParser:
    """Test suite for acceptance criteria parsing from GitHub issues."""

    @pytest.fixture
    def sample_issue_body(self) -> str:
        """Sample GitHub issue body with acceptance criteria."""
        return """
## Summary
Enhanced test-master agent for comprehensive test coverage.

## Acceptance Criteria

### Fresh Install
- [ ] Test-master generates UAT tests from acceptance criteria (1 per criterion)
- [ ] UAT tests use pytest-bdd Gherkin-style format
- [ ] Tests written to tests/uat/ directory

### Update
- [ ] Integration tests cover module boundaries
- [ ] Integration tests written to tests/integration/ directory

### Validation
- [ ] Unit tests have GREEN implementations (not skeletons)
- [ ] Unit tests written to tests/unit/ directory
- [ ] Test validation gate runs before reviewer agent

### Security
- [ ] All tests pass security validation
- [ ] No hardcoded credentials in tests
- [ ] Commit blocked if any test fails

## Implementation Details
This is not part of acceptance criteria.
"""

    @pytest.fixture
    def sample_issue_no_criteria(self) -> str:
        """Sample GitHub issue body without acceptance criteria section."""
        return """
## Summary
Simple feature without acceptance criteria.

## Implementation Details
Just implement the feature.
"""

    @pytest.fixture
    def sample_issue_empty_criteria(self) -> str:
        """Sample GitHub issue body with empty acceptance criteria section."""
        return """
## Summary
Feature with empty acceptance criteria.

## Acceptance Criteria

(No criteria defined)

## Implementation Details
TBD
"""

    # =============================================================================
    # Fetch Issue Body Tests
    # =============================================================================

    def test_fetch_issue_body_success(self, tmp_path):
        """
        GIVEN: Valid issue number
        WHEN: Fetching issue body via gh CLI
        THEN: Returns issue body as string
        """
        # Import the module (will fail until implementation exists)
        from autonomous_dev.lib.acceptance_criteria_parser import fetch_issue_body

        # Arrange
        issue_number = 161
        expected_body = "## Summary\nTest issue body"

        # Mock subprocess.run to simulate gh CLI success
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=expected_body,
                stderr=""
            )

            # Act
            result = fetch_issue_body(issue_number)

            # Assert
            assert result == expected_body
            mock_run.assert_called_once()
            # Verify gh CLI command structure
            args = mock_run.call_args[0][0]
            assert 'gh' in args
            assert 'issue' in args
            assert 'view' in args
            assert str(issue_number) in args
            assert '--json' in args or 'body' in ' '.join(args)

    def test_fetch_issue_body_issue_not_found(self):
        """
        GIVEN: Invalid issue number
        WHEN: Fetching issue body via gh CLI
        THEN: Raises ValueError with 404 message
        """
        from autonomous_dev.lib.acceptance_criteria_parser import fetch_issue_body

        # Arrange
        issue_number = 99999

        # Mock subprocess.run to simulate gh CLI 404
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="could not resolve to an issue"
            )

            # Act & Assert
            with pytest.raises(ValueError, match="Issue #99999 not found"):
                fetch_issue_body(issue_number)

    def test_fetch_issue_body_gh_cli_not_installed(self):
        """
        GIVEN: gh CLI not installed
        WHEN: Fetching issue body
        THEN: Raises RuntimeError with installation guidance
        """
        from autonomous_dev.lib.acceptance_criteria_parser import fetch_issue_body

        # Arrange
        issue_number = 161

        # Mock subprocess.run to simulate gh not found
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("gh: command not found")

            # Act & Assert
            with pytest.raises(RuntimeError, match="gh CLI not installed"):
                fetch_issue_body(issue_number)

    def test_fetch_issue_body_network_error(self):
        """
        GIVEN: Network connectivity issues
        WHEN: Fetching issue body
        THEN: Raises RuntimeError with network error message
        """
        from autonomous_dev.lib.acceptance_criteria_parser import fetch_issue_body

        # Arrange
        issue_number = 161

        # Mock subprocess.run to simulate network error
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="Could not resolve host: github.com"
            )

            # Act & Assert
            with pytest.raises(RuntimeError, match="Network error"):
                fetch_issue_body(issue_number)

    # =============================================================================
    # Parse Acceptance Criteria Tests
    # =============================================================================

    def test_parse_acceptance_criteria_categorized(self, sample_issue_body):
        """
        GIVEN: Issue body with categorized acceptance criteria
        WHEN: Parsing acceptance criteria
        THEN: Returns dict with categories and criteria
        """
        from autonomous_dev.lib.acceptance_criteria_parser import parse_acceptance_criteria

        # Act
        result = parse_acceptance_criteria(sample_issue_body)

        # Assert
        assert isinstance(result, dict)
        assert "Fresh Install" in result
        assert "Update" in result
        assert "Validation" in result
        assert "Security" in result

        # Validate Fresh Install criteria
        assert len(result["Fresh Install"]) == 3
        assert any("UAT tests from acceptance criteria" in c for c in result["Fresh Install"])
        assert any("pytest-bdd Gherkin-style" in c for c in result["Fresh Install"])
        assert any("tests/uat/ directory" in c for c in result["Fresh Install"])

        # Validate Update criteria
        assert len(result["Update"]) == 2
        assert any("Integration tests cover module boundaries" in c for c in result["Update"])

        # Validate Validation criteria
        assert len(result["Validation"]) == 3
        assert any("GREEN implementations" in c for c in result["Validation"])

        # Validate Security criteria
        assert len(result["Security"]) == 3
        assert any("security validation" in c for c in result["Security"])

    def test_parse_acceptance_criteria_uncategorized(self):
        """
        GIVEN: Issue body with uncategorized acceptance criteria
        WHEN: Parsing acceptance criteria
        THEN: Returns dict with "General" category
        """
        from autonomous_dev.lib.acceptance_criteria_parser import parse_acceptance_criteria

        # Arrange
        issue_body = """
## Acceptance Criteria
- [ ] Feature works correctly
- [ ] Tests pass
- [ ] Documentation updated
"""

        # Act
        result = parse_acceptance_criteria(issue_body)

        # Assert
        assert isinstance(result, dict)
        assert "General" in result
        assert len(result["General"]) == 3
        assert "Feature works correctly" in result["General"]
        assert "Tests pass" in result["General"]
        assert "Documentation updated" in result["General"]

    def test_parse_acceptance_criteria_empty_body(self, sample_issue_no_criteria):
        """
        GIVEN: Issue body without acceptance criteria section
        WHEN: Parsing acceptance criteria
        THEN: Returns empty dict
        """
        from autonomous_dev.lib.acceptance_criteria_parser import parse_acceptance_criteria

        # Act
        result = parse_acceptance_criteria(sample_issue_no_criteria)

        # Assert
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_parse_acceptance_criteria_handles_no_acceptance_section(self):
        """
        GIVEN: Issue body without "## Acceptance Criteria" section
        WHEN: Parsing acceptance criteria
        THEN: Returns empty dict (graceful degradation)
        """
        from autonomous_dev.lib.acceptance_criteria_parser import parse_acceptance_criteria

        # Arrange
        issue_body = """
## Summary
Feature without acceptance criteria.

## Implementation Details
Just implement it.
"""

        # Act
        result = parse_acceptance_criteria(issue_body)

        # Assert
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_parse_acceptance_criteria_strips_checkbox_markers(self, sample_issue_body):
        """
        GIVEN: Acceptance criteria with checkbox markers (- [ ])
        WHEN: Parsing acceptance criteria
        THEN: Returns criteria without checkbox markers
        """
        from autonomous_dev.lib.acceptance_criteria_parser import parse_acceptance_criteria

        # Act
        result = parse_acceptance_criteria(sample_issue_body)

        # Assert
        for category, criteria in result.items():
            for criterion in criteria:
                # Should not contain checkbox markers
                assert "- [ ]" not in criterion
                assert "- [x]" not in criterion
                # Should be clean text
                assert not criterion.startswith("-")
                assert not criterion.startswith("[")

    # =============================================================================
    # Format for UAT Tests
    # =============================================================================

    def test_format_for_uat_gherkin_style(self):
        """
        GIVEN: Parsed acceptance criteria
        WHEN: Formatting for UAT tests
        THEN: Returns Gherkin-style test scenarios
        """
        from autonomous_dev.lib.acceptance_criteria_parser import format_for_uat

        # Arrange
        criteria = {
            "Fresh Install": [
                "Test-master generates UAT tests from acceptance criteria",
                "UAT tests use pytest-bdd Gherkin-style format"
            ],
            "Validation": [
                "Test validation gate runs before reviewer agent"
            ]
        }

        # Act
        result = format_for_uat(criteria)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 3  # 2 from Fresh Install + 1 from Validation

        # Validate structure (each item should be a dict with scenario info)
        for scenario in result:
            assert "category" in scenario
            assert "criterion" in scenario
            assert "scenario_name" in scenario
            assert isinstance(scenario["category"], str)
            assert isinstance(scenario["criterion"], str)
            assert isinstance(scenario["scenario_name"], str)

    def test_format_for_uat_scenario_naming(self):
        """
        GIVEN: Acceptance criteria
        WHEN: Formatting for UAT tests
        THEN: Generates valid pytest scenario names
        """
        from autonomous_dev.lib.acceptance_criteria_parser import format_for_uat

        # Arrange
        criteria = {
            "Fresh Install": [
                "Test-master generates UAT tests from acceptance criteria (1 per criterion)"
            ]
        }

        # Act
        result = format_for_uat(criteria)

        # Assert
        scenario_name = result[0]["scenario_name"]
        # Scenario names should be snake_case, no spaces, no special chars
        assert " " not in scenario_name
        assert scenario_name.islower() or "_" in scenario_name
        assert scenario_name.startswith("test_")

    def test_format_for_uat_preserves_category_context(self):
        """
        GIVEN: Categorized acceptance criteria
        WHEN: Formatting for UAT tests
        THEN: Preserves category information for test organization
        """
        from autonomous_dev.lib.acceptance_criteria_parser import format_for_uat

        # Arrange
        criteria = {
            "Fresh Install": ["Criterion 1"],
            "Update": ["Criterion 2"],
            "Security": ["Criterion 3"]
        }

        # Act
        result = format_for_uat(criteria)

        # Assert
        categories = {item["category"] for item in result}
        assert "Fresh Install" in categories
        assert "Update" in categories
        assert "Security" in categories

    # =============================================================================
    # Integration Tests
    # =============================================================================

    def test_full_pipeline_from_issue_to_uat(self, sample_issue_body):
        """
        GIVEN: GitHub issue number
        WHEN: Executing full pipeline (fetch → parse → format)
        THEN: Returns UAT test scenarios ready for test generation
        """
        from autonomous_dev.lib.acceptance_criteria_parser import (
            fetch_issue_body,
            parse_acceptance_criteria,
            format_for_uat
        )

        # Arrange
        issue_number = 161

        # Mock gh CLI
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=sample_issue_body,
                stderr=""
            )

            # Act
            issue_body = fetch_issue_body(issue_number)
            criteria = parse_acceptance_criteria(issue_body)
            uat_scenarios = format_for_uat(criteria)

            # Assert
            assert len(uat_scenarios) > 0
            assert all("scenario_name" in s for s in uat_scenarios)
            assert all("criterion" in s for s in uat_scenarios)
            assert all("category" in s for s in uat_scenarios)

    def test_handles_malformed_acceptance_criteria(self):
        """
        GIVEN: Issue body with malformed acceptance criteria section
        WHEN: Parsing acceptance criteria
        THEN: Gracefully handles errors and returns partial results
        """
        from autonomous_dev.lib.acceptance_criteria_parser import parse_acceptance_criteria

        # Arrange
        malformed_body = """
## Acceptance Criteria

### Category Without Criteria

### Another Category
- [ ] Valid criterion
- Criterion without checkbox
[ ] Checkbox without dash

## Next Section
"""

        # Act
        result = parse_acceptance_criteria(malformed_body)

        # Assert
        # Should return dict (even if some criteria are skipped)
        assert isinstance(result, dict)
        # Should handle at least the valid criterion
        if "Another Category" in result:
            assert len(result["Another Category"]) >= 1

    def test_handles_unicode_in_criteria(self):
        """
        GIVEN: Acceptance criteria with unicode characters
        WHEN: Parsing and formatting
        THEN: Preserves unicode characters correctly
        """
        from autonomous_dev.lib.acceptance_criteria_parser import (
            parse_acceptance_criteria,
            format_for_uat
        )

        # Arrange
        unicode_body = """
## Acceptance Criteria

### Internationalization
- [ ] Support UTF-8 characters: 日本語, 한국어, العربية
- [ ] Emoji support: ✅ ❌ 🔒
"""

        # Act
        criteria = parse_acceptance_criteria(unicode_body)
        uat_scenarios = format_for_uat(criteria)

        # Assert
        assert len(criteria) > 0
        assert len(uat_scenarios) > 0
        # Unicode should be preserved
        assert any("日本語" in s["criterion"] for s in uat_scenarios)
        assert any("✅" in s["criterion"] for s in uat_scenarios)

    def test_handles_very_long_criteria(self):
        """
        GIVEN: Acceptance criteria with very long text
        WHEN: Parsing and formatting
        THEN: Handles long text without truncation
        """
        from autonomous_dev.lib.acceptance_criteria_parser import (
            parse_acceptance_criteria,
            format_for_uat
        )

        # Arrange
        long_criterion = "Test-master generates comprehensive test coverage " * 50
        long_body = f"""
## Acceptance Criteria

### Testing
- [ ] {long_criterion}
"""

        # Act
        criteria = parse_acceptance_criteria(long_body)
        uat_scenarios = format_for_uat(criteria)

        # Assert
        assert len(criteria["Testing"]) == 1
        # Full text should be preserved (not truncated)
        assert len(criteria["Testing"][0]) > 1000
        assert len(uat_scenarios[0]["criterion"]) > 1000

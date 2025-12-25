"""
Unit tests for test_tier_organizer.py

Tests validate that the test tier organizer can classify tests and organize them
into the correct directory structure (unit/, integration/, uat/).

These tests follow TDD - they should FAIL until implementation is complete.

Run with: pytest tests/unit/lib/test_test_tier_organizer.py --tb=line -q
"""

from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, patch

import pytest


class TestTestTierOrganizer:
    """Test suite for test tier organization and classification."""

    # =============================================================================
    # Test Tier Classification
    # =============================================================================

    def test_determine_tier_unit(self):
        """
        GIVEN: Test file with unit test characteristics
        WHEN: Determining test tier
        THEN: Classifies as 'unit'
        """
        from autonomous_dev.lib.test_tier_organizer import determine_tier

        # Arrange - Unit test characteristics:
        # - Tests single function/class
        # - No external dependencies
        # - Uses mocking
        test_content = """
def test_parse_acceptance_criteria():
    '''Tests parse_acceptance_criteria function.'''
    from module import parse_acceptance_criteria
    result = parse_acceptance_criteria("test input")
    assert result == expected
"""

        # Act
        tier = determine_tier(test_content)

        # Assert
        assert tier == "unit"

    def test_determine_tier_integration(self):
        """
        GIVEN: Test file with integration test characteristics
        WHEN: Determining test tier
        THEN: Classifies as 'integration'
        """
        from autonomous_dev.lib.test_tier_organizer import determine_tier

        # Arrange - Integration test characteristics:
        # - Tests multiple modules together
        # - Tests file I/O or subprocess
        # - Tests module boundaries
        test_content = """
def test_acceptance_criteria_to_uat_mapping(tmp_path):
    '''Tests full pipeline from criteria to UAT.'''
    from module1 import fetch_issue_body
    from module2 import parse_acceptance_criteria
    from module3 import format_for_uat

    # Integration across modules
    body = fetch_issue_body(161)
    criteria = parse_acceptance_criteria(body)
    uat = format_for_uat(criteria)

    assert len(uat) > 0
"""

        # Act
        tier = determine_tier(test_content)

        # Assert
        assert tier == "integration"

    def test_determine_tier_uat(self):
        """
        GIVEN: Test file with UAT/acceptance test characteristics
        WHEN: Determining test tier
        THEN: Classifies as 'uat'
        """
        from autonomous_dev.lib.test_tier_organizer import determine_tier

        # Arrange - UAT characteristics:
        # - Uses pytest-bdd or Gherkin syntax
        # - Tests user-facing behavior
        # - Tests acceptance criteria
        test_content = """
from pytest_bdd import scenario, given, when, then

@scenario('features/test_coverage.feature', 'Test-master generates UAT tests')
def test_uat_generation():
    pass

@given('A GitHub issue with acceptance criteria')
def github_issue():
    return 161

@when('Test-master processes the issue')
def process_issue(github_issue):
    # Process
    pass

@then('UAT tests are generated for each criterion')
def verify_uat_tests():
    assert True
"""

        # Act
        tier = determine_tier(test_content)

        # Assert
        assert tier == "uat"

    def test_determine_tier_defaults_to_unit(self):
        """
        GIVEN: Test file without clear tier indicators
        WHEN: Determining test tier
        THEN: Defaults to 'unit' tier
        """
        from autonomous_dev.lib.test_tier_organizer import determine_tier

        # Arrange - Ambiguous test
        test_content = """
def test_something():
    assert True
"""

        # Act
        tier = determine_tier(test_content)

        # Assert
        assert tier == "unit"

    def test_determine_tier_from_filename(self):
        """
        GIVEN: Test filename with tier prefix
        WHEN: Determining test tier
        THEN: Respects filename convention
        """
        from autonomous_dev.lib.test_tier_organizer import determine_tier_from_filename

        # Arrange & Act & Assert
        assert determine_tier_from_filename("test_integration_workflow.py") == "integration"
        assert determine_tier_from_filename("test_uat_fresh_install.py") == "uat"
        assert determine_tier_from_filename("test_acceptance_criteria_parser.py") == "unit"

    # =============================================================================
    # Directory Creation
    # =============================================================================

    def test_create_tier_directories(self, tmp_path):
        """
        GIVEN: Empty project directory
        WHEN: Creating tier directories
        THEN: Creates tests/{unit,integration,uat}/ structure
        """
        from autonomous_dev.lib.test_tier_organizer import create_tier_directories

        # Act
        create_tier_directories(tmp_path)

        # Assert
        assert (tmp_path / "tests").exists()
        assert (tmp_path / "tests" / "unit").exists()
        assert (tmp_path / "tests" / "integration").exists()
        assert (tmp_path / "tests" / "uat").exists()

    def test_create_tier_directories_already_exists(self, tmp_path):
        """
        GIVEN: Project with existing tests/ directory
        WHEN: Creating tier directories
        THEN: Idempotent - doesn't raise error
        """
        from autonomous_dev.lib.test_tier_organizer import create_tier_directories

        # Arrange - Create tests/ directory first
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "unit").mkdir()

        # Act - Should not raise error
        create_tier_directories(tmp_path)

        # Assert
        assert (tmp_path / "tests" / "unit").exists()
        assert (tmp_path / "tests" / "integration").exists()
        assert (tmp_path / "tests" / "uat").exists()

    def test_create_tier_directories_creates_init_files(self, tmp_path):
        """
        GIVEN: Empty project directory
        WHEN: Creating tier directories
        THEN: Creates __init__.py in each tier directory
        """
        from autonomous_dev.lib.test_tier_organizer import create_tier_directories

        # Act
        create_tier_directories(tmp_path)

        # Assert
        assert (tmp_path / "tests" / "__init__.py").exists()
        assert (tmp_path / "tests" / "unit" / "__init__.py").exists()
        assert (tmp_path / "tests" / "integration" / "__init__.py").exists()
        assert (tmp_path / "tests" / "uat" / "__init__.py").exists()

    def test_create_tier_directories_with_lib_subdirectory(self, tmp_path):
        """
        GIVEN: Test files for lib/ modules
        WHEN: Creating tier directories
        THEN: Creates tests/unit/lib/ subdirectory
        """
        from autonomous_dev.lib.test_tier_organizer import create_tier_directories

        # Act
        create_tier_directories(tmp_path, subdirs=["lib"])

        # Assert
        assert (tmp_path / "tests" / "unit" / "lib").exists()
        assert (tmp_path / "tests" / "unit" / "lib" / "__init__.py").exists()

    # =============================================================================
    # File Organization
    # =============================================================================

    def test_move_test_to_tier(self, tmp_path):
        """
        GIVEN: Test file in wrong location
        WHEN: Moving test to correct tier
        THEN: Moves file to correct directory
        """
        from autonomous_dev.lib.test_tier_organizer import move_test_to_tier

        # Arrange
        create_tier_directories(tmp_path)
        test_file = tmp_path / "test_acceptance_criteria_parser.py"
        test_file.write_text("def test_parse(): pass")

        # Act
        move_test_to_tier(test_file, "unit", target_subdir="lib")

        # Assert
        expected_path = tmp_path / "tests" / "unit" / "lib" / "test_acceptance_criteria_parser.py"
        assert expected_path.exists()
        assert not test_file.exists()

    def test_move_test_to_tier_preserves_content(self, tmp_path):
        """
        GIVEN: Test file with content
        WHEN: Moving test to tier
        THEN: Preserves file content
        """
        from autonomous_dev.lib.test_tier_organizer import move_test_to_tier, create_tier_directories

        # Arrange
        create_tier_directories(tmp_path)
        test_file = tmp_path / "test_example.py"
        test_content = "def test_example():\n    assert True\n"
        test_file.write_text(test_content)

        # Act
        move_test_to_tier(test_file, "integration")

        # Assert
        moved_file = tmp_path / "tests" / "integration" / "test_example.py"
        assert moved_file.exists()
        assert moved_file.read_text() == test_content

    def test_move_test_to_tier_handles_name_collision(self, tmp_path):
        """
        GIVEN: Test file with same name already exists in target tier
        WHEN: Moving test to tier
        THEN: Raises error or renames file
        """
        from autonomous_dev.lib.test_tier_organizer import move_test_to_tier, create_tier_directories

        # Arrange
        create_tier_directories(tmp_path)
        test_file = tmp_path / "test_example.py"
        test_file.write_text("def test_new(): pass")

        # Create existing file in target
        existing = tmp_path / "tests" / "unit" / "test_example.py"
        existing.write_text("def test_existing(): pass")

        # Act & Assert
        with pytest.raises(FileExistsError, match="already exists"):
            move_test_to_tier(test_file, "unit")

    # =============================================================================
    # Batch Organization
    # =============================================================================

    def test_organize_tests_by_tier(self, tmp_path):
        """
        GIVEN: Multiple test files
        WHEN: Organizing tests by tier
        THEN: Moves each test to correct tier directory
        """
        from autonomous_dev.lib.test_tier_organizer import organize_tests_by_tier, create_tier_directories

        # Arrange
        create_tier_directories(tmp_path)

        # Create test files with tier indicators
        unit_test = tmp_path / "test_unit_example.py"
        unit_test.write_text("def test_parse(): pass")

        integration_test = tmp_path / "test_integration_workflow.py"
        integration_test.write_text("def test_full_pipeline(): pass")

        uat_test = tmp_path / "test_uat_fresh_install.py"
        uat_test.write_text("from pytest_bdd import scenario\n")

        test_files = [unit_test, integration_test, uat_test]

        # Act
        organize_tests_by_tier(test_files)

        # Assert
        assert (tmp_path / "tests" / "unit" / "test_unit_example.py").exists()
        assert (tmp_path / "tests" / "integration" / "test_integration_workflow.py").exists()
        assert (tmp_path / "tests" / "uat" / "test_uat_fresh_install.py").exists()

    def test_organize_tests_by_tier_returns_mapping(self, tmp_path):
        """
        GIVEN: Test files to organize
        WHEN: Organizing tests
        THEN: Returns dict mapping tier -> list of files
        """
        from autonomous_dev.lib.test_tier_organizer import organize_tests_by_tier, create_tier_directories

        # Arrange
        create_tier_directories(tmp_path)

        unit_test = tmp_path / "test_example.py"
        unit_test.write_text("def test_unit(): pass")

        test_files = [unit_test]

        # Act
        result = organize_tests_by_tier(test_files)

        # Assert
        assert isinstance(result, dict)
        assert "unit" in result
        assert len(result["unit"]) == 1
        assert "test_example.py" in str(result["unit"][0])

    # =============================================================================
    # Test Statistics
    # =============================================================================

    def test_get_tier_statistics(self, tmp_path):
        """
        GIVEN: Organized test directory structure
        WHEN: Getting tier statistics
        THEN: Returns count of tests per tier
        """
        from autonomous_dev.lib.test_tier_organizer import (
            create_tier_directories,
            get_tier_statistics
        )

        # Arrange
        create_tier_directories(tmp_path)

        # Create test files in different tiers
        (tmp_path / "tests" / "unit" / "test_1.py").write_text("pass")
        (tmp_path / "tests" / "unit" / "test_2.py").write_text("pass")
        (tmp_path / "tests" / "integration" / "test_3.py").write_text("pass")
        (tmp_path / "tests" / "uat" / "test_4.py").write_text("pass")
        (tmp_path / "tests" / "uat" / "test_5.py").write_text("pass")
        (tmp_path / "tests" / "uat" / "test_6.py").write_text("pass")

        # Act
        stats = get_tier_statistics(tmp_path / "tests")

        # Assert
        assert stats["unit"] == 2
        assert stats["integration"] == 1
        assert stats["uat"] == 3
        assert stats["total"] == 6

    def test_get_tier_statistics_validates_pyramid(self, tmp_path):
        """
        GIVEN: Test directory with tier statistics
        WHEN: Validating test pyramid
        THEN: Warns if pyramid is inverted (more integration than unit)
        """
        from autonomous_dev.lib.test_tier_organizer import (
            create_tier_directories,
            validate_test_pyramid
        )

        # Arrange - Inverted pyramid (bad)
        create_tier_directories(tmp_path)
        (tmp_path / "tests" / "unit" / "test_1.py").write_text("pass")
        (tmp_path / "tests" / "integration" / "test_2.py").write_text("pass")
        (tmp_path / "tests" / "integration" / "test_3.py").write_text("pass")
        (tmp_path / "tests" / "integration" / "test_4.py").write_text("pass")

        # Act
        is_valid, warnings = validate_test_pyramid(tmp_path / "tests")

        # Assert
        assert is_valid is False
        assert len(warnings) > 0
        assert any("pyramid" in w.lower() for w in warnings)

    # =============================================================================
    # Error Handling
    # =============================================================================

    def test_create_tier_directories_handles_permission_error(self, tmp_path):
        """
        GIVEN: Read-only directory
        WHEN: Creating tier directories
        THEN: Raises PermissionError with clear message
        """
        from autonomous_dev.lib.test_tier_organizer import create_tier_directories

        # Arrange - Make directory read-only
        tmp_path.chmod(0o444)

        try:
            # Act & Assert
            with pytest.raises(PermissionError, match="Permission denied"):
                create_tier_directories(tmp_path)
        finally:
            # Cleanup
            tmp_path.chmod(0o755)

    def test_move_test_to_tier_validates_source_exists(self, tmp_path):
        """
        GIVEN: Non-existent test file
        WHEN: Moving test to tier
        THEN: Raises FileNotFoundError
        """
        from autonomous_dev.lib.test_tier_organizer import move_test_to_tier

        # Arrange
        non_existent = tmp_path / "test_nonexistent.py"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="not found"):
            move_test_to_tier(non_existent, "unit")

    def test_determine_tier_handles_invalid_content(self):
        """
        GIVEN: Invalid Python syntax in test file
        WHEN: Determining tier
        THEN: Returns default tier (unit) without crashing
        """
        from autonomous_dev.lib.test_tier_organizer import determine_tier

        # Arrange - Invalid Python
        invalid_content = "def test_broken(\n    # Missing closing paren"

        # Act
        tier = determine_tier(invalid_content)

        # Assert
        assert tier == "unit"  # Default fallback


def create_tier_directories(base_path: Path, subdirs: List[str] = None):
    """Helper function to create tier directories for tests."""
    tests_dir = base_path / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "__init__.py").write_text("")

    for tier in ["unit", "integration", "uat"]:
        tier_dir = tests_dir / tier
        tier_dir.mkdir(exist_ok=True)
        (tier_dir / "__init__.py").write_text("")

        if subdirs:
            for subdir in subdirs:
                subdir_path = tier_dir / subdir
                subdir_path.mkdir(exist_ok=True)
                (subdir_path / "__init__.py").write_text("")

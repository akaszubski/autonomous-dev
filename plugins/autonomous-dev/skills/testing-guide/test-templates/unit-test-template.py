#!/usr/bin/env python3
"""
Unit Test Template

This template demonstrates best practices for writing unit tests with pytest,
including the Arrange-Act-Assert pattern, fixtures, parametrization, and mocking.

Purpose: Provide a reusable template for unit test development
Pattern: Arrange-Act-Assert (AAA)
Framework: pytest

Usage:
1. Copy this template
2. Replace placeholder names with your actual module/function names
3. Add test cases following the AAA pattern
4. Use fixtures for setup/teardown
5. Parametrize tests for multiple scenarios
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path


# ============================================================================
# FIXTURES - Reusable test setup
# ============================================================================

@pytest.fixture
def sample_data():
    """
    Provide sample data for tests.

    Scope: function (default) - created for each test
    """
    return {
        "id": 1,
        "name": "Test Item",
        "value": 100,
        "active": True
    }


@pytest.fixture
def mock_database():
    """
    Provide mock database for testing.

    Use this to avoid real database connections in unit tests.
    """
    db = Mock()
    db.connect.return_value = True
    db.query.return_value = [{"id": 1, "name": "Record 1"}]
    db.insert.return_value = True
    db.close.return_value = True
    return db


@pytest.fixture
def temp_file(tmp_path):
    """
    Create temporary file for testing file operations.

    Args:
        tmp_path: pytest fixture providing temporary directory

    Yields:
        Path: Path to temporary test file
    """
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("test content")
    yield file_path
    # Cleanup happens automatically with tmp_path


@pytest.fixture(scope="module")
def test_config():
    """
    Provide test configuration.

    Scope: module - created once per test module
    """
    return {
        "api_url": "https://test.example.com",
        "timeout": 30,
        "retry_count": 3
    }


# ============================================================================
# BASIC UNIT TESTS - AAA Pattern
# ============================================================================

class TestBasicFunctionality:
    """Test basic functionality with Arrange-Act-Assert pattern."""

    def test_simple_calculation(self):
        """Test simple calculation with AAA pattern."""
        # Arrange
        input_value = 10
        expected_output = 20

        # Act
        result = input_value * 2

        # Assert
        assert result == expected_output

    def test_string_manipulation(self):
        """Test string manipulation."""
        # Arrange
        input_string = "hello world"
        expected_output = "HELLO WORLD"

        # Act
        result = input_string.upper()

        # Assert
        assert result == expected_output
        assert isinstance(result, str)

    def test_list_operations(self):
        """Test list operations."""
        # Arrange
        test_list = [1, 2, 3]
        item_to_add = 4

        # Act
        test_list.append(item_to_add)

        # Assert
        assert len(test_list) == 4
        assert test_list[-1] == item_to_add
        assert item_to_add in test_list


# ============================================================================
# TESTS WITH FIXTURES
# ============================================================================

class TestWithFixtures:
    """Test using fixtures for setup."""

    def test_using_sample_data(self, sample_data):
        """Test using fixture-provided data."""
        # Arrange (done by fixture)
        expected_id = 1

        # Act
        actual_id = sample_data["id"]

        # Assert
        assert actual_id == expected_id
        assert sample_data["active"] is True

    def test_using_mock_database(self, mock_database):
        """Test database operations with mock."""
        # Arrange
        query = "SELECT * FROM users"

        # Act
        result = mock_database.query(query)

        # Assert
        assert len(result) == 1
        assert result[0]["name"] == "Record 1"
        mock_database.query.assert_called_once_with(query)

    def test_using_temp_file(self, temp_file):
        """Test file operations with temporary file."""
        # Arrange
        expected_content = "test content"

        # Act
        actual_content = temp_file.read_text()

        # Assert
        assert actual_content == expected_content
        assert temp_file.exists()


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================

class TestParametrization:
    """Test with parametrization for multiple scenarios."""

    @pytest.mark.parametrize("input_value,expected_output", [
        (0, 0),
        (1, 2),
        (5, 10),
        (10, 20),
        (-5, -10),
    ])
    def test_double_function(self, input_value, expected_output):
        """Test doubling function with multiple inputs."""
        # Arrange (done by parametrize)

        # Act
        result = input_value * 2

        # Assert
        assert result == expected_output

    @pytest.mark.parametrize("input_str,expected_bool", [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
    ], ids=["lowercase_true", "capitalized_true", "uppercase_true",
            "lowercase_false", "capitalized_false", "uppercase_false"])
    def test_string_to_bool(self, input_str, expected_bool):
        """Test string to boolean conversion with named test cases."""
        # Arrange
        converter = lambda s: s.lower() == "true"

        # Act
        result = converter(input_str)

        # Assert
        assert result == expected_bool


# ============================================================================
# MOCKING TESTS
# ============================================================================

class TestWithMocking:
    """Test with mocks for external dependencies."""

    @patch('builtins.open', mock_open(read_data='file content'))
    def test_read_file(self):
        """Test reading file with mock."""
        # Arrange
        file_path = "test.txt"
        expected_content = "file content"

        # Act
        with open(file_path) as f:
            content = f.read()

        # Assert
        assert content == expected_content

    def test_with_mock_object(self):
        """Test using mock object."""
        # Arrange
        mock_api = Mock()
        mock_api.get_data.return_value = {"status": "success"}

        # Act
        result = mock_api.get_data()

        # Assert
        assert result["status"] == "success"
        mock_api.get_data.assert_called_once()

    def test_mock_side_effects(self):
        """Test mock with side effects."""
        # Arrange
        mock_obj = Mock()
        mock_obj.method.side_effect = [1, 2, 3]

        # Act & Assert
        assert mock_obj.method() == 1
        assert mock_obj.method() == 2
        assert mock_obj.method() == 3


# ============================================================================
# EXCEPTION TESTING
# ============================================================================

class TestExceptions:
    """Test exception handling."""

    def test_value_error_raised(self):
        """Test that ValueError is raised for invalid input."""
        # Arrange
        invalid_input = -1

        # Act & Assert
        with pytest.raises(ValueError):
            if invalid_input < 0:
                raise ValueError("Input must be positive")

    def test_exception_message(self):
        """Test exception message matches expected pattern."""
        # Arrange
        invalid_input = ""

        # Act & Assert
        with pytest.raises(ValueError, match="Input cannot be empty"):
            if not invalid_input:
                raise ValueError("Input cannot be empty")

    @pytest.mark.parametrize("invalid_input,error_type", [
        (None, TypeError),
        ("", ValueError),
        (-1, ValueError),
    ])
    def test_multiple_exceptions(self, invalid_input, error_type):
        """Test multiple exception scenarios."""
        # Arrange
        def validate(value):
            if value is None:
                raise TypeError("Value cannot be None")
            if value == "":
                raise ValueError("Value cannot be empty")
            if value == -1:
                raise ValueError("Value must be positive")

        # Act & Assert
        with pytest.raises(error_type):
            validate(invalid_input)


# ============================================================================
# INTEGRATION WITH MULTIPLE COMPONENTS
# ============================================================================

class TestMultipleComponents:
    """Test integration of multiple components."""

    def test_component_interaction(self, mock_database):
        """Test interaction between multiple components."""
        # Arrange
        class DataService:
            def __init__(self, db):
                self.db = db

            def fetch_records(self):
                return self.db.query("SELECT * FROM records")

        service = DataService(mock_database)

        # Act
        records = service.fetch_records()

        # Assert
        assert len(records) == 1
        assert records[0]["id"] == 1
        mock_database.query.assert_called_once()


# ============================================================================
# BEST PRACTICES DEMONSTRATED
# ============================================================================

"""
Best Practices Demonstrated in This Template:

1. AAA Pattern: All tests follow Arrange-Act-Assert structure
2. Fixtures: Reusable setup with different scopes
3. Parametrization: Test multiple scenarios efficiently
4. Mocking: Isolate units from external dependencies
5. Clear naming: Descriptive test and fixture names
6. Docstrings: Each test explains what it tests
7. Organization: Logical grouping with test classes
8. Exception testing: Verify error handling
9. Assertions: Multiple assertions for complete verification
10. Comments: Clear phase separation with comments

Follow these patterns for consistent, maintainable unit tests.
"""

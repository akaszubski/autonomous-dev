#!/usr/bin/env python3
"""
Pytest Fixture Examples

This file demonstrates various pytest fixture patterns and use cases.
Fixtures provide reusable setup and teardown for tests.

Purpose: Show practical fixture patterns for different scenarios
Framework: pytest

Key Concepts:
- Function scope: Created/destroyed for each test (default)
- Class scope: Created once per test class
- Module scope: Created once per test module
- Session scope: Created once per test session
- Autouse fixtures: Run automatically without explicit request
- Fixture composition: Fixtures depending on other fixtures
- Yield fixtures: Setup and teardown with cleanup
"""

import pytest
from pathlib import Path
from unittest.mock import Mock
import tempfile
import json


# ============================================================================
# FUNCTION SCOPE FIXTURES (Default)
# ============================================================================

@pytest.fixture
def sample_list():
    """
    Provide a fresh list for each test.

    Scope: function (default)
    Use case: When each test needs isolated data
    """
    return [1, 2, 3, 4, 5]


@pytest.fixture
def sample_dict():
    """
    Provide a fresh dictionary for each test.

    Scope: function (default)
    Use case: Mutable data that tests may modify
    """
    return {
        "name": "Test User",
        "email": "test@example.com",
        "age": 30,
        "active": True
    }


@pytest.fixture
def mock_api_client():
    """
    Provide mock API client for each test.

    Scope: function (default)
    Use case: Mock external dependencies in unit tests
    """
    client = Mock()
    client.get.return_value = {"status": "success", "data": []}
    client.post.return_value = {"status": "created", "id": 1}
    client.delete.return_value = {"status": "deleted"}
    return client


# ============================================================================
# CLASS SCOPE FIXTURES
# ============================================================================

@pytest.fixture(scope="class")
def database_connection():
    """
    Create database connection shared across test class.

    Scope: class
    Use case: Expensive setup that can be shared across related tests
    """
    # Setup: Create connection
    connection = {
        "host": "localhost",
        "port": 5432,
        "connected": True
    }

    print("\n[FIXTURE] Setting up database connection")

    yield connection

    # Teardown: Close connection
    print("\n[FIXTURE] Closing database connection")
    connection["connected"] = False


@pytest.fixture(scope="class")
def test_data_loader():
    """
    Load test data once per test class.

    Scope: class
    Use case: Load large test datasets once for multiple tests
    """
    test_data = {
        "users": [
            {"id": 1, "name": "User 1"},
            {"id": 2, "name": "User 2"},
            {"id": 3, "name": "User 3"},
        ],
        "products": [
            {"id": 1, "name": "Product A", "price": 10.00},
            {"id": 2, "name": "Product B", "price": 20.00},
        ]
    }

    return test_data


# ============================================================================
# MODULE SCOPE FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def test_config():
    """
    Load configuration once per test module.

    Scope: module
    Use case: Shared configuration for all tests in module
    """
    config = {
        "api_url": "https://test.example.com",
        "timeout": 30,
        "retry_count": 3,
        "debug": True
    }

    print("\n[FIXTURE] Loading test configuration")

    return config


@pytest.fixture(scope="module")
def temp_directory():
    """
    Create temporary directory for module.

    Scope: module
    Use case: Shared temporary workspace for all tests in module
    """
    # Setup
    temp_dir = tempfile.mkdtemp()
    print(f"\n[FIXTURE] Created temp directory: {temp_dir}")

    yield Path(temp_dir)

    # Teardown
    import shutil
    shutil.rmtree(temp_dir)
    print(f"\n[FIXTURE] Cleaned up temp directory: {temp_dir}")


# ============================================================================
# SESSION SCOPE FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def global_config():
    """
    Global configuration for entire test session.

    Scope: session
    Use case: One-time expensive setup for all tests
    """
    print("\n[FIXTURE] Loading global configuration (session scope)")

    config = {
        "test_mode": True,
        "environment": "test",
        "log_level": "DEBUG"
    }

    return config


@pytest.fixture(scope="session")
def test_database_schema():
    """
    Create database schema once for entire test session.

    Scope: session
    Use case: One-time database schema setup
    """
    print("\n[FIXTURE] Creating database schema (session scope)")

    schema = {
        "tables": ["users", "posts", "comments"],
        "indexes": ["users_email_idx", "posts_user_id_idx"],
        "created": True
    }

    yield schema

    print("\n[FIXTURE] Cleaning up database schema (session scope)")
    schema["created"] = False


# ============================================================================
# AUTOUSE FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def reset_global_state():
    """
    Automatically reset global state before each test.

    Autouse: True (runs automatically without being requested)
    Use case: Ensure clean state for every test
    """
    # Setup: Reset state
    global_state = {}

    yield global_state

    # Teardown: Clean up
    global_state.clear()


@pytest.fixture(autouse=True, scope="function")
def log_test_execution():
    """
    Automatically log test execution.

    Autouse: True
    Scope: function
    Use case: Logging or monitoring for all tests
    """
    # Before test
    print("\n[AUTOUSE] Test starting")

    yield

    # After test
    print("\n[AUTOUSE] Test completed")


# ============================================================================
# FIXTURE COMPOSITION
# ============================================================================

@pytest.fixture
def database():
    """Base database fixture."""
    return {"connected": True, "tables": {}}


@pytest.fixture
def user_repository(database):
    """
    User repository that depends on database fixture.

    Demonstrates: Fixture composition
    """
    class UserRepository:
        def __init__(self, db):
            self.db = db
            self.db["tables"]["users"] = []

        def add_user(self, user):
            """Add user to repository."""
            self.db["tables"]["users"].append(user)

        def get_users(self):
            """Get all users."""
            return self.db["tables"]["users"]

    return UserRepository(database)


@pytest.fixture
def populated_user_repository(user_repository):
    """
    User repository pre-populated with test users.

    Demonstrates: Multi-level fixture composition
    """
    user_repository.add_user({"id": 1, "name": "User 1"})
    user_repository.add_user({"id": 2, "name": "User 2"})
    user_repository.add_user({"id": 3, "name": "User 3"})

    return user_repository


# ============================================================================
# YIELD FIXTURES WITH CLEANUP
# ============================================================================

@pytest.fixture
def temp_file(tmp_path):
    """
    Create temporary file with cleanup.

    Demonstrates: Yield fixture with teardown
    """
    # Setup: Create file
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("Initial content")

    print(f"\n[FIXTURE] Created temp file: {file_path}")

    yield file_path

    # Teardown: Cleanup (optional, tmp_path handles it)
    print(f"\n[FIXTURE] Cleaning up temp file: {file_path}")


@pytest.fixture
def json_file(tmp_path):
    """
    Create JSON file with test data.

    Demonstrates: Yield fixture for file operations
    """
    # Setup
    file_path = tmp_path / "test_data.json"
    test_data = {
        "users": [{"id": 1, "name": "Test User"}],
        "settings": {"debug": True}
    }
    file_path.write_text(json.dumps(test_data, indent=2))

    yield file_path

    # Teardown: File is automatically cleaned up by tmp_path


# ============================================================================
# PARAMETRIZED FIXTURES
# ============================================================================

@pytest.fixture(params=["user1", "user2", "admin"])
def username(request):
    """
    Parametrized fixture that provides different usernames.

    Demonstrates: Fixture parametrization
    Use case: Test with multiple different inputs
    """
    return request.param


@pytest.fixture(params=[
    {"name": "Test User", "role": "user"},
    {"name": "Admin User", "role": "admin"},
    {"name": "Guest User", "role": "guest"},
])
def user_data(request):
    """
    Parametrized fixture with complex data.

    Demonstrates: Parametrized fixture with dictionaries
    """
    return request.param


# ============================================================================
# EXAMPLE TESTS USING FIXTURES
# ============================================================================

def test_with_sample_list(sample_list):
    """Test using function-scope list fixture."""
    assert len(sample_list) == 5
    assert sample_list[0] == 1


def test_with_sample_dict(sample_dict):
    """Test using function-scope dict fixture."""
    assert sample_dict["name"] == "Test User"
    assert sample_dict["active"] is True


def test_with_mock_api(mock_api_client):
    """Test using mock API client fixture."""
    response = mock_api_client.get("/users")
    assert response["status"] == "success"
    mock_api_client.get.assert_called_once_with("/users")


class TestWithClassFixtures:
    """Test class using class-scope fixtures."""

    def test_database_connection(self, database_connection):
        """Test using class-scope database fixture."""
        assert database_connection["connected"] is True

    def test_database_connection_shared(self, database_connection):
        """Test that connection is shared across class."""
        assert database_connection["connected"] is True


def test_with_module_config(test_config):
    """Test using module-scope config fixture."""
    assert test_config["api_url"] == "https://test.example.com"
    assert test_config["timeout"] == 30


def test_with_session_config(global_config):
    """Test using session-scope config fixture."""
    assert global_config["test_mode"] is True
    assert global_config["environment"] == "test"


def test_with_composed_fixtures(populated_user_repository):
    """Test using composed fixtures."""
    users = populated_user_repository.get_users()
    assert len(users) == 3
    assert users[0]["name"] == "User 1"


def test_with_temp_file(temp_file):
    """Test using yield fixture with cleanup."""
    content = temp_file.read_text()
    assert content == "Initial content"
    assert temp_file.exists()


def test_with_parametrized_fixture(username):
    """Test using parametrized fixture (runs 3 times)."""
    assert isinstance(username, str)
    assert len(username) > 0


# ============================================================================
# BEST PRACTICES DEMONSTRATED
# ============================================================================

"""
Fixture Best Practices:

1. Choose Right Scope:
   - function: Default, isolated state per test
   - class: Share expensive setup across test class
   - module: Share across test module
   - session: One-time setup for all tests

2. Use Yield for Cleanup:
   - Setup before yield
   - Cleanup after yield
   - Ensures teardown even if test fails

3. Composition Over Duplication:
   - Build complex fixtures from simpler ones
   - Maintain single responsibility

4. Descriptive Names:
   - Name fixtures based on what they provide
   - Use docstrings to explain purpose

5. Autouse Sparingly:
   - Use only for cross-cutting concerns
   - Makes test dependencies implicit

6. Parametrize for Variations:
   - Test multiple scenarios with same fixture
   - Reduces code duplication

7. Keep Fixtures Simple:
   - Each fixture should do one thing well
   - Complex setup = multiple fixtures

8. Document Side Effects:
   - Explain any state changes
   - Note cleanup behavior
"""

#!/usr/bin/env python3
"""
Integration Test Template

This template demonstrates best practices for writing integration tests with pytest.
Integration tests verify that multiple components work together correctly.

Purpose: Provide a reusable template for integration test development
Pattern: Arrange-Act-Assert (AAA) with component interaction
Framework: pytest

Differences from Unit Tests:
- Test multiple components interacting
- May involve real database connections (with test data)
- Test end-to-end workflows
- Setup/teardown may be more complex
- Tests may be slower than unit tests

Usage:
1. Copy this template
2. Replace placeholder components with your actual components
3. Set up test database/services in fixtures
4. Test complete workflows through multiple layers
5. Clean up resources after tests
"""

import pytest
import json


# ============================================================================
# INTEGRATION FIXTURES - Test environment setup
# ============================================================================

@pytest.fixture(scope="module")
def test_database():
    """
    Set up test database for entire module.

    Scope: module - created once per test module
    This represents a real or in-memory database for integration testing.
    """
    # Setup: Create test database
    database = {
        "users": [],
        "posts": [],
        "comments": []
    }

    # Seed with initial test data
    database["users"].append({
        "id": 1,
        "username": "testuser",
        "email": "test@example.com"
    })

    yield database

    # Teardown: Clean up database
    database.clear()


@pytest.fixture(scope="function")
def clean_database(test_database):
    """
    Provide clean database for each test.

    Scope: function - reset state for each test
    """
    # Clear all non-seed data
    test_database["posts"].clear()
    test_database["comments"].clear()

    yield test_database


@pytest.fixture
def api_client(test_database):
    """
    Create API client connected to test database.

    This simulates a real API client that interacts with the database.
    """
    class TestAPIClient:
        def __init__(self, db):
            self.db = db

        def get_user(self, user_id):
            """Fetch user from database."""
            users = [u for u in self.db["users"] if u["id"] == user_id]
            return users[0] if users else None

        def create_post(self, user_id, title, content):
            """Create post in database."""
            post = {
                "id": len(self.db["posts"]) + 1,
                "user_id": user_id,
                "title": title,
                "content": content
            }
            self.db["posts"].append(post)
            return post

        def get_posts_by_user(self, user_id):
            """Get all posts by user."""
            return [p for p in self.db["posts"] if p["user_id"] == user_id]

    return TestAPIClient(test_database)


@pytest.fixture
def temp_config_file(tmp_path):
    """
    Create temporary configuration file.

    Used for testing configuration loading and file I/O integration.
    """
    config = {
        "database": {
            "host": "localhost",
            "port": 5432
        },
        "api": {
            "timeout": 30,
            "retry_count": 3
        }
    }

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config, indent=2))

    yield config_file

    # Cleanup happens automatically with tmp_path


# ============================================================================
# COMPONENT INTERACTION TESTS
# ============================================================================

class TestComponentIntegration:
    """Test integration between multiple components."""

    def test_user_service_with_database(self, api_client):
        """Test user service interacts correctly with database."""
        # Arrange
        expected_user_id = 1
        expected_username = "testuser"

        # Act
        user = api_client.get_user(expected_user_id)

        # Assert
        assert user is not None
        assert user["id"] == expected_user_id
        assert user["username"] == expected_username

    def test_create_post_workflow(self, api_client, clean_database):
        """Test complete workflow of creating a post."""
        # Arrange
        user_id = 1
        post_title = "Test Post"
        post_content = "This is a test post"

        # Act
        created_post = api_client.create_post(user_id, post_title, post_content)

        # Assert
        assert created_post["id"] is not None
        assert created_post["user_id"] == user_id
        assert created_post["title"] == post_title
        assert created_post["content"] == post_content

        # Verify post is in database
        posts = api_client.get_posts_by_user(user_id)
        assert len(posts) == 1
        assert posts[0]["id"] == created_post["id"]

    def test_multi_post_workflow(self, api_client, clean_database):
        """Test workflow with multiple posts."""
        # Arrange
        user_id = 1

        # Act
        post1 = api_client.create_post(user_id, "Post 1", "Content 1")
        post2 = api_client.create_post(user_id, "Post 2", "Content 2")
        post3 = api_client.create_post(user_id, "Post 3", "Content 3")

        # Assert
        posts = api_client.get_posts_by_user(user_id)
        assert len(posts) == 3
        assert posts[0]["title"] == "Post 1"
        assert posts[1]["title"] == "Post 2"
        assert posts[2]["title"] == "Post 3"


# ============================================================================
# END-TO-END WORKFLOW TESTS
# ============================================================================

class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    def test_user_creates_and_retrieves_posts(self, api_client, clean_database):
        """Test complete user posting workflow."""
        # Arrange
        user_id = 1

        # Act - Create multiple posts
        api_client.create_post(user_id, "Morning Post", "Good morning!")
        api_client.create_post(user_id, "Afternoon Post", "Good afternoon!")

        # Act - Retrieve posts
        user_posts = api_client.get_posts_by_user(user_id)

        # Assert
        assert len(user_posts) == 2
        assert user_posts[0]["title"] == "Morning Post"
        assert user_posts[1]["title"] == "Afternoon Post"

    def test_configuration_loading_workflow(self, temp_config_file):
        """Test loading and using configuration file."""
        # Arrange
        class ConfigLoader:
            @staticmethod
            def load(file_path):
                """Load configuration from file."""
                with open(file_path) as f:
                    return json.load(f)

        class DatabaseConnection:
            def __init__(self, config):
                self.host = config["database"]["host"]
                self.port = config["database"]["port"]

            def connect(self):
                """Simulate database connection."""
                return f"Connected to {self.host}:{self.port}"

        # Act - Load config and create connection
        config = ConfigLoader.load(temp_config_file)
        db_connection = DatabaseConnection(config)
        connection_string = db_connection.connect()

        # Assert
        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432
        assert connection_string == "Connected to localhost:5432"


# ============================================================================
# STATE MANAGEMENT TESTS
# ============================================================================

class TestStateManagement:
    """Test state management across components."""

    def test_state_persistence(self, clean_database, api_client):
        """Test state persists correctly across operations."""
        # Arrange
        user_id = 1

        # Act - Create posts in sequence
        api_client.create_post(user_id, "Post 1", "Content 1")
        posts_after_first = api_client.get_posts_by_user(user_id)

        api_client.create_post(user_id, "Post 2", "Content 2")
        posts_after_second = api_client.get_posts_by_user(user_id)

        # Assert - State accumulated correctly
        assert len(posts_after_first) == 1
        assert len(posts_after_second) == 2

    def test_state_isolation(self, clean_database):
        """Test state isolation between test runs."""
        # Arrange
        initial_post_count = len(clean_database["posts"])

        # Act
        clean_database["posts"].append({"id": 1, "title": "Test"})

        # Assert
        assert initial_post_count == 0  # Clean database started empty
        assert len(clean_database["posts"]) == 1


# ============================================================================
# ERROR HANDLING IN WORKFLOWS
# ============================================================================

class TestErrorHandlingWorkflows:
    """Test error handling in integrated workflows."""

    def test_missing_user_handling(self, api_client):
        """Test handling of missing user in workflow."""
        # Arrange
        nonexistent_user_id = 999

        # Act
        user = api_client.get_user(nonexistent_user_id)

        # Assert
        assert user is None

    def test_invalid_data_handling(self, api_client, clean_database):
        """Test handling of invalid data in workflow."""
        # Arrange
        class ValidationService:
            @staticmethod
            def validate_post(title, content):
                """Validate post data."""
                if not title:
                    raise ValueError("Title cannot be empty")
                if not content:
                    raise ValueError("Content cannot be empty")
                return True

        validator = ValidationService()

        # Act & Assert
        with pytest.raises(ValueError, match="Title cannot be empty"):
            validator.validate_post("", "Content")

        with pytest.raises(ValueError, match="Content cannot be empty"):
            validator.validate_post("Title", "")


# ============================================================================
# MULTI-COMPONENT INTEGRATION
# ============================================================================

class TestMultiComponentIntegration:
    """Test integration of multiple components in complex scenarios."""

    def test_service_layer_integration(self, test_database):
        """Test service layer integrates with repository layer."""
        # Arrange
        class UserRepository:
            def __init__(self, db):
                self.db = db

            def find_by_id(self, user_id):
                """Find user by ID."""
                users = [u for u in self.db["users"] if u["id"] == user_id]
                return users[0] if users else None

        class UserService:
            def __init__(self, repository):
                self.repository = repository

            def get_user_email(self, user_id):
                """Get user email via repository."""
                user = self.repository.find_by_id(user_id)
                return user["email"] if user else None

        repository = UserRepository(test_database)
        service = UserService(repository)

        # Act
        email = service.get_user_email(1)

        # Assert
        assert email == "test@example.com"

    def test_three_layer_integration(self, test_database):
        """Test three-layer architecture integration."""
        # Arrange - Data layer
        class DataLayer:
            def __init__(self, db):
                self.db = db

            def query(self, table, filters):
                """Query data from table."""
                return [item for item in self.db[table] if all(
                    item.get(k) == v for k, v in filters.items()
                )]

        # Arrange - Business layer
        class BusinessLayer:
            def __init__(self, data_layer):
                self.data = data_layer

            def find_user_by_username(self, username):
                """Find user by username."""
                results = self.data.query("users", {"username": username})
                return results[0] if results else None

        # Arrange - Presentation layer
        class PresentationLayer:
            def __init__(self, business_layer):
                self.business = business_layer

            def format_user(self, username):
                """Format user for display."""
                user = self.business.find_user_by_username(username)
                if user:
                    return f"{user['username']} ({user['email']})"
                return "User not found"

        # Act - Test complete workflow through all layers
        data = DataLayer(test_database)
        business = BusinessLayer(data)
        presentation = PresentationLayer(business)
        result = presentation.format_user("testuser")

        # Assert
        assert result == "testuser (test@example.com)"


# ============================================================================
# PERFORMANCE AND RESOURCE TESTS
# ============================================================================

class TestPerformanceAndResources:
    """Test performance and resource management in integration."""

    def test_bulk_operations(self, api_client, clean_database):
        """Test bulk operations perform correctly."""
        # Arrange
        user_id = 1
        post_count = 10

        # Act - Create many posts
        for i in range(post_count):
            api_client.create_post(user_id, f"Post {i}", f"Content {i}")

        # Assert
        posts = api_client.get_posts_by_user(user_id)
        assert len(posts) == post_count

    def test_resource_cleanup(self, tmp_path):
        """Test resources are cleaned up properly."""
        # Arrange
        test_files = []

        # Act - Create multiple temporary files
        for i in range(5):
            file_path = tmp_path / f"test_{i}.txt"
            file_path.write_text(f"Test content {i}")
            test_files.append(file_path)

        # Assert - All files exist
        for file_path in test_files:
            assert file_path.exists()

        # Cleanup will happen automatically via tmp_path fixture


# ============================================================================
# BEST PRACTICES DEMONSTRATED
# ============================================================================

"""
Integration Testing Best Practices Demonstrated:

1. Component Interaction: Test multiple components working together
2. End-to-End Workflows: Test complete user workflows
3. State Management: Verify state persists correctly
4. Setup/Teardown: Proper fixture scopes for resource management
5. Test Data: Use fixtures to provide consistent test data
6. Clean State: Each test starts with clean state
7. Real-World Scenarios: Test realistic usage patterns
8. Error Handling: Test error paths in workflows
9. Multi-Layer Testing: Test through multiple architectural layers
10. Resource Cleanup: Ensure proper cleanup after tests

Integration tests complement unit tests by verifying that components
work together correctly. They may be slower but provide confidence that
the system works as a whole.
"""

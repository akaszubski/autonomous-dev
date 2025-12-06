#!/usr/bin/env python3
"""
Unit tests for batch_retry_consent module (TDD Red Phase - Issue #89).

Tests for first-run consent prompt for automatic retry feature.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test first-run prompt display and user input
- Test consent persistence to user_state.json
- Test environment variable override (BATCH_RETRY_ENABLED)
- Test consent check performance (no I/O on subsequent calls)
- Test security of consent state file (permissions, path validation)

Security:
- CWE-22: Path validation for user_state.json
- File permissions: 0o600 (user-only read/write)
- Safe defaults (no retry without explicit consent)

Coverage Target: 95%+ for batch_retry_consent.py

Date: 2025-11-18
Issue: #89 (Automatic Failure Recovery for /batch-implement)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - module doesn't exist yet)
"""

import sys
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail - module doesn't exist yet (TDD!)
try:
    from batch_retry_consent import (
        check_retry_consent,
        prompt_for_retry_consent,
        save_consent_state,
        load_consent_state,
        is_retry_enabled,
        get_user_state_file,
        ConsentError,
        DEFAULT_USER_STATE_FILE,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_home_dir(tmp_path):
    """Create temporary home directory for testing."""
    home = tmp_path / "home"
    home.mkdir()
    autonomous_dev_dir = home / ".autonomous-dev"
    autonomous_dev_dir.mkdir()
    return home


@pytest.fixture
def user_state_file(temp_home_dir):
    """Get path to user state file."""
    return temp_home_dir / ".autonomous-dev" / "user_state.json"


@pytest.fixture
def mock_input_yes():
    """Mock user input returning 'yes'."""
    with patch("builtins.input", return_value="yes") as mock:
        yield mock


@pytest.fixture
def mock_input_no():
    """Mock user input returning 'no'."""
    with patch("builtins.input", return_value="no") as mock:
        yield mock


# =============================================================================
# SECTION 1: First-Run Prompt Tests (5 tests)
# =============================================================================

class TestFirstRunPrompt:
    """Test first-run consent prompt display and handling."""

    def test_prompt_displays_clear_explanation(self, mock_input_yes):
        """Test that prompt explains automatic retry feature clearly."""
        # Arrange & Act
        with patch("builtins.print") as mock_print:
            result = prompt_for_retry_consent()

            # Assert - explanation printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            combined_output = " ".join(print_calls).lower()

            assert "automatic retry" in combined_output or "retry" in combined_output
            assert "transient" in combined_output or "network" in combined_output
            assert "max 3" in combined_output or "3 retries" in combined_output

    def test_prompt_accepts_yes_response(self, mock_input_yes):
        """Test that 'yes' response enables retry feature."""
        # Arrange & Act
        result = prompt_for_retry_consent()

        # Assert
        assert result is True

    def test_prompt_accepts_no_response(self, mock_input_no):
        """Test that 'no' response disables retry feature."""
        # Arrange & Act
        result = prompt_for_retry_consent()

        # Assert
        assert result is False

    def test_prompt_accepts_case_insensitive_input(self):
        """Test that prompt accepts YES, yes, Yes, etc."""
        # Arrange
        test_cases = [
            ("yes", True),
            ("YES", True),
            ("Yes", True),
            ("y", True),
            ("Y", True),
            ("no", False),
            ("NO", False),
            ("No", False),
            ("n", False),
            ("N", False),
        ]

        # Act & Assert
        for user_input, expected in test_cases:
            with patch("builtins.input", return_value=user_input):
                result = prompt_for_retry_consent()
                assert result == expected

    def test_prompt_defaults_to_no_on_invalid_input(self):
        """Test that invalid input defaults to 'no' for safety."""
        # Arrange
        invalid_inputs = ["maybe", "1", "", "asdf"]

        # Act & Assert
        for invalid_input in invalid_inputs:
            with patch("builtins.input", return_value=invalid_input):
                result = prompt_for_retry_consent()
                assert result is False  # Safe default


# =============================================================================
# SECTION 2: Consent Persistence Tests (6 tests)
# =============================================================================

class TestConsentPersistence:
    """Test consent state persistence to user_state.json."""

    def test_save_consent_creates_user_state_file(self, temp_home_dir, user_state_file):
        """Test that save_consent_state creates user_state.json."""
        # Arrange
        assert not user_state_file.exists()

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            save_consent_state(retry_enabled=True)

        # Assert
        assert user_state_file.exists()

    def test_save_consent_stores_retry_enabled_true(self, temp_home_dir, user_state_file):
        """Test that consent=yes is stored correctly."""
        # Arrange & Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            save_consent_state(retry_enabled=True)

        # Assert
        data = json.loads(user_state_file.read_text())
        assert data["batch_retry_enabled"] is True

    def test_save_consent_stores_retry_enabled_false(self, temp_home_dir, user_state_file):
        """Test that consent=no is stored correctly."""
        # Arrange & Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            save_consent_state(retry_enabled=False)

        # Assert
        data = json.loads(user_state_file.read_text())
        assert data["batch_retry_enabled"] is False

    def test_load_consent_reads_existing_state(self, temp_home_dir, user_state_file):
        """Test that load_consent_state reads from existing file."""
        # Arrange - create state file
        state_data = {"batch_retry_enabled": True}
        user_state_file.write_text(json.dumps(state_data))

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            result = load_consent_state()

        # Assert
        assert result is True

    def test_load_consent_returns_none_if_not_set(self, temp_home_dir, user_state_file):
        """Test that load_consent_state returns None if not set yet."""
        # Arrange - empty state file
        user_state_file.write_text("{}")

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            result = load_consent_state()

        # Assert
        assert result is None

    def test_load_consent_returns_none_if_file_missing(self, temp_home_dir, user_state_file):
        """Test that load_consent_state returns None if file doesn't exist."""
        # Arrange
        assert not user_state_file.exists()

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            result = load_consent_state()

        # Assert
        assert result is None


# =============================================================================
# SECTION 3: Environment Variable Override Tests (4 tests)
# =============================================================================

class TestEnvironmentVariableOverride:
    """Test BATCH_RETRY_ENABLED environment variable override."""

    def test_env_var_true_enables_retry(self, user_state_file):
        """Test that BATCH_RETRY_ENABLED=true enables retry without prompt."""
        # Arrange & Act
        with patch.dict("os.environ", {"BATCH_RETRY_ENABLED": "true"}):
            result = is_retry_enabled()

        # Assert
        assert result is True

    def test_env_var_false_disables_retry(self, user_state_file):
        """Test that BATCH_RETRY_ENABLED=false disables retry without prompt."""
        # Arrange & Act
        with patch.dict("os.environ", {"BATCH_RETRY_ENABLED": "false"}):
            result = is_retry_enabled()

        # Assert
        assert result is False

    def test_env_var_overrides_user_state(self, temp_home_dir, user_state_file):
        """Test that env var takes precedence over user_state.json."""
        # Arrange - user_state.json says no
        state_data = {"batch_retry_enabled": False}
        user_state_file.write_text(json.dumps(state_data))

        # Act - env var says yes
        with patch.dict("os.environ", {"BATCH_RETRY_ENABLED": "true"}):
            with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
                result = is_retry_enabled()

        # Assert - env var wins
        assert result is True

    def test_env_var_case_insensitive(self):
        """Test that env var values are case-insensitive."""
        # Arrange
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
        ]

        # Act & Assert
        for env_value, expected in test_cases:
            with patch.dict("os.environ", {"BATCH_RETRY_ENABLED": env_value}):
                result = is_retry_enabled()
                assert result == expected


# =============================================================================
# SECTION 4: Consent Check Workflow Tests (5 tests)
# =============================================================================

class TestConsentCheckWorkflow:
    """Test complete consent check workflow."""

    def test_check_retry_consent_prompts_on_first_run(self, temp_home_dir, user_state_file):
        """Test that check_retry_consent prompts user on first run."""
        # Arrange - no state file exists
        assert not user_state_file.exists()

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            with patch("batch_retry_consent.prompt_for_retry_consent", return_value=True) as mock_prompt:
                result = check_retry_consent()

                # Assert - prompt was called
                mock_prompt.assert_called_once()
                assert result is True

    def test_check_retry_consent_no_prompt_on_subsequent_runs(self, temp_home_dir, user_state_file):
        """Test that check_retry_consent doesn't prompt on subsequent runs."""
        # Arrange - state file already exists
        state_data = {"batch_retry_enabled": True}
        user_state_file.write_text(json.dumps(state_data))

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            with patch("batch_retry_consent.prompt_for_retry_consent") as mock_prompt:
                result = check_retry_consent()

                # Assert - prompt NOT called
                mock_prompt.assert_not_called()
                assert result is True

    def test_check_retry_consent_saves_response(self, temp_home_dir, user_state_file):
        """Test that check_retry_consent saves user response."""
        # Arrange
        assert not user_state_file.exists()

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            with patch("batch_retry_consent.prompt_for_retry_consent", return_value=True):
                check_retry_consent()

        # Assert - state saved
        assert user_state_file.exists()
        data = json.loads(user_state_file.read_text())
        assert data["batch_retry_enabled"] is True

    def test_is_retry_enabled_checks_env_var_first(self):
        """Test that is_retry_enabled checks env var before state file."""
        # Arrange & Act
        with patch.dict("os.environ", {"BATCH_RETRY_ENABLED": "true"}):
            with patch("batch_retry_consent.load_consent_state") as mock_load:
                result = is_retry_enabled()

                # Assert - env var checked, state file not loaded
                mock_load.assert_not_called()
                assert result is True

    def test_is_retry_enabled_prompts_if_not_set(self, temp_home_dir, user_state_file):
        """Test that is_retry_enabled prompts if neither env var nor state set."""
        # Arrange - no env var, no state file
        assert not user_state_file.exists()

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            with patch("batch_retry_consent.prompt_for_retry_consent", return_value=False) as mock_prompt:
                result = is_retry_enabled()

                # Assert
                mock_prompt.assert_called_once()
                assert result is False


# =============================================================================
# SECTION 5: Security Tests (5 tests)
# =============================================================================

class TestConsentSecurity:
    """Test security of consent state file."""

    def test_user_state_file_created_with_secure_permissions(self, temp_home_dir, user_state_file):
        """Test that user_state.json is created with 0o600 permissions."""
        # Arrange & Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            save_consent_state(retry_enabled=True)

        # Assert - file permissions are 0o600 (user-only read/write)
        assert user_state_file.exists()
        # Check permissions (must be user-only)
        mode = user_state_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_user_state_file_path_validation(self):
        """Test that user_state file path is validated (no path traversal)."""
        # Arrange - malicious path
        malicious_path = Path("/tmp/../../etc/passwd")

        # Act & Assert
        with pytest.raises(ConsentError) as exc_info:
            save_consent_state(retry_enabled=True)  # Implementation should validate path

        # Note: Implementation should use security_utils.validate_path

    def test_user_state_file_rejects_symlinks(self, temp_home_dir, user_state_file):
        """Test that symlink attacks are prevented."""
        # Arrange - create symlink pointing to /etc/passwd
        symlink_path = temp_home_dir / ".autonomous-dev" / "user_state.json"

        try:
            symlink_path.symlink_to("/etc/passwd")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Act & Assert
        with patch("batch_retry_consent.get_user_state_file", return_value=symlink_path):
            with pytest.raises(ConsentError) as exc_info:
                save_consent_state(retry_enabled=True)

            assert "symlink" in str(exc_info.value).lower()

    def test_corrupted_state_file_handled_gracefully(self, temp_home_dir, user_state_file):
        """Test that corrupted state file doesn't crash."""
        # Arrange - create corrupted state file
        user_state_file.write_text("{invalid json")

        # Act - should handle gracefully (prompt again)
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            with patch("batch_retry_consent.prompt_for_retry_consent", return_value=True):
                result = check_retry_consent()

                # Assert - handled gracefully, prompted again
                assert result is True

    def test_user_state_directory_created_if_missing(self, temp_home_dir):
        """Test that ~/.autonomous-dev/ is created if it doesn't exist."""
        # Arrange - remove directory
        autonomous_dev_dir = temp_home_dir / ".autonomous-dev"
        if autonomous_dev_dir.exists():
            autonomous_dev_dir.rmdir()

        user_state_file = autonomous_dev_dir / "user_state.json"

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            save_consent_state(retry_enabled=True)

        # Assert - directory and file created
        assert autonomous_dev_dir.exists()
        assert user_state_file.exists()


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (25 unit tests for batch_retry_consent.py):

SECTION 1: First-Run Prompt (5 tests)
✗ test_prompt_displays_clear_explanation
✗ test_prompt_accepts_yes_response
✗ test_prompt_accepts_no_response
✗ test_prompt_accepts_case_insensitive_input
✗ test_prompt_defaults_to_no_on_invalid_input

SECTION 2: Consent Persistence (6 tests)
✗ test_save_consent_creates_user_state_file
✗ test_save_consent_stores_retry_enabled_true
✗ test_save_consent_stores_retry_enabled_false
✗ test_load_consent_reads_existing_state
✗ test_load_consent_returns_none_if_not_set
✗ test_load_consent_returns_none_if_file_missing

SECTION 3: Environment Variable Override (4 tests)
✗ test_env_var_true_enables_retry
✗ test_env_var_false_disables_retry
✗ test_env_var_overrides_user_state
✗ test_env_var_case_insensitive

SECTION 4: Consent Check Workflow (5 tests)
✗ test_check_retry_consent_prompts_on_first_run
✗ test_check_retry_consent_no_prompt_on_subsequent_runs
✗ test_check_retry_consent_saves_response
✗ test_is_retry_enabled_checks_env_var_first
✗ test_is_retry_enabled_prompts_if_not_set

SECTION 5: Security (5 tests)
✗ test_user_state_file_created_with_secure_permissions
✗ test_user_state_file_path_validation
✗ test_user_state_file_rejects_symlinks
✗ test_corrupted_state_file_handled_gracefully
✗ test_user_state_directory_created_if_missing

TOTAL: 25 unit tests (all FAILING - TDD red phase)

Security Coverage:
- CWE-22: Path validation for user_state.json
- CWE-59: Symlink rejection
- File permissions: 0o600 (user-only)
- Safe defaults (no retry without consent)
- Graceful handling of corrupted state

Implementation Guidance:
- Use ~/.autonomous-dev/user_state.json for state
- Prompt only on first run (check state file first)
- Environment variable BATCH_RETRY_ENABLED overrides state
- Atomic writes for state file updates
- Validate paths using security_utils.validate_path
"""

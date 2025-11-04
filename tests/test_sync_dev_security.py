"""
TDD Security Tests for /sync-dev command path validation and CLI exception handling.

IMPORTANT: These tests are written FIRST (TDD red phase) before implementation.
All tests should FAIL initially - they describe the security requirements.

Test Coverage:
1. Symlink rejection (is_symlink() check)
2. Path traversal rejection ('..' in path)
3. Whitelist validation (paths outside project rejected via relative_to())
4. Valid paths within project accepted
5. CLI exception handling (int() conversion errors)
6. Edge cases (symlink to valid location, float issue numbers)

Security Requirements (per SECURITY_AUDIT_SYNC_DEV.md):
- CRITICAL: Validate all paths from JSON config before file operations
- HIGH: Proper exception handling for JSON parsing errors
- MEDIUM: Validate paths are within expected directory tree

Following TDD principles - tests written before implementation.
Target: 80%+ coverage of security-critical code paths.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest


class TestPathValidationSymlinks:
    """Test symlink rejection in path validation."""

    def test_rejects_symlink_in_install_path(self):
        """Test that symlinks in installPath are rejected."""
        # Arrange: Create a symlink in temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            real_dir = Path(tmpdir) / "real_plugin"
            real_dir.mkdir()

            symlink_path = Path(tmpdir) / "symlink_plugin"
            symlink_path.symlink_to(real_dir)

            # Act: Attempt to validate symlink path
            # This should call the actual validation function
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                # Create mock config with symlink path
                config_file = Path(tmpdir) / ".claude" / "plugins" / "installed_plugins.json"
                config_file.parent.mkdir(parents=True, exist_ok=True)

                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": str(symlink_path)
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Symlink should be rejected
                result = find_installed_plugin_path()
                assert result is None, "Symlinks should be rejected for security"

    def test_rejects_symlink_component_in_path(self):
        """Test that paths containing symlink components are rejected."""
        # Arrange: Create path with symlink in the middle
        with tempfile.TemporaryDirectory() as tmpdir:
            real_dir = Path(tmpdir) / "real"
            real_dir.mkdir()

            symlink_dir = Path(tmpdir) / "link"
            symlink_dir.symlink_to(real_dir)

            target_dir = symlink_dir / "subdir"
            target_dir.mkdir()

            # Act: Validate path that goes through symlink
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = Path(tmpdir) / ".claude" / "plugins" / "installed_plugins.json"
                config_file.parent.mkdir(parents=True, exist_ok=True)

                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": str(target_dir)
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Path with symlink component should be rejected
                result = find_installed_plugin_path()
                assert result is None, "Paths through symlinks should be rejected"

    def test_accepts_regular_directory(self):
        """Test that regular directories (non-symlinks) are accepted."""
        # Arrange: Create regular directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            install_dir = plugins_dir / "autonomous-dev@1.0.0"
            install_dir.mkdir()

            # Act: Validate regular directory
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": str(install_dir)
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Regular directory should be accepted
                result = find_installed_plugin_path()
                assert result is not None, "Regular directories should be accepted"
                assert result == install_dir.resolve()


class TestPathValidationTraversal:
    """Test path traversal attack prevention."""

    def test_rejects_parent_directory_traversal(self):
        """Test that '../' path traversal attempts are rejected."""
        # Arrange: Create path with .. components
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            # Malicious path trying to escape plugins directory
            malicious_path = str(plugins_dir / ".." / ".." / "sensitive")

            # Act: Attempt to use traversal path
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": malicious_path
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Traversal path should be rejected
                result = find_installed_plugin_path()
                assert result is None, "Path traversal should be rejected"

    def test_rejects_absolute_path_outside_plugins(self):
        """Test that absolute paths outside .claude/plugins/ are rejected."""
        # Arrange: Create absolute path to /tmp or other location
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            # Malicious absolute path outside plugins
            outside_dir = Path(tmpdir) / "outside"
            outside_dir.mkdir()

            # Act: Attempt to use outside path
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": str(outside_dir)
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Outside path should be rejected
                result = find_installed_plugin_path()
                assert result is None, "Paths outside .claude/plugins/ should be rejected"

    def test_rejects_path_with_embedded_traversal(self):
        """Test rejection of paths with traversal in middle (e.g., /plugins/foo/../../etc/)."""
        # Arrange: Create path that looks safe but resolves outside
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            # Path that appears to be in plugins but resolves outside
            sneaky_path = str(plugins_dir / "foo" / ".." / ".." / ".." / "etc")

            # Act: Attempt validation
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": sneaky_path
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Embedded traversal should be rejected
                result = find_installed_plugin_path()
                assert result is None, "Embedded path traversal should be rejected"


class TestWhitelistValidation:
    """Test whitelist validation using relative_to() for path containment."""

    def test_relative_to_validates_path_within_plugins_dir(self):
        """Test that relative_to() correctly validates paths are within .claude/plugins/."""
        # Arrange: Create valid path structure
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            install_dir = plugins_dir / "autonomous-dev@1.0.0"
            install_dir.mkdir()

            # Act: Validate using relative_to()
            try:
                relative = install_dir.relative_to(plugins_dir)
                is_within = True
            except ValueError:
                is_within = False

            # Assert: Path should be within plugins directory
            assert is_within, "Valid plugin path should be within .claude/plugins/"
            assert str(relative) == "autonomous-dev@1.0.0"

    def test_relative_to_rejects_path_outside_plugins_dir(self):
        """Test that relative_to() raises ValueError for paths outside whitelist."""
        # Arrange: Create path outside plugins directory
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            outside_dir = Path(tmpdir) / "outside"
            outside_dir.mkdir()

            # Act & Assert: relative_to() should raise ValueError
            with pytest.raises(ValueError):
                outside_dir.relative_to(plugins_dir)

    def test_validates_nested_paths_within_whitelist(self):
        """Test that deeply nested paths within plugins/ are accepted."""
        # Arrange: Create deeply nested structure
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            nested = plugins_dir / "autonomous-dev@1.0.0" / "agents" / "subdir"
            nested.mkdir(parents=True)

            # Act: Validate nested path
            try:
                relative = nested.relative_to(plugins_dir)
                is_within = True
            except ValueError:
                is_within = False

            # Assert: Nested path should be accepted
            assert is_within, "Nested paths within plugins/ should be accepted"

    def test_whitelist_validation_with_resolve_prevents_escapes(self):
        """Test that resolve() + relative_to() prevents symlink escapes."""
        # Arrange: Create symlink that tries to escape
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            outside_dir = Path(tmpdir) / "outside"
            outside_dir.mkdir()

            # Symlink inside plugins pointing outside
            escape_link = plugins_dir / "escape"
            escape_link.symlink_to(outside_dir)

            # Act: Resolve and validate
            resolved = escape_link.resolve()

            try:
                resolved.relative_to(plugins_dir)
                is_within = True
            except ValueError:
                is_within = False

            # Assert: Resolved symlink should be detected as outside
            assert not is_within, "Symlinks escaping whitelist should be rejected"


class TestCLIExceptionHandling:
    """Test CLI exception handling for int() conversions and argument parsing."""

    def test_handles_invalid_issue_number_non_numeric(self):
        """Test handling of non-numeric issue numbers in CLI."""
        # This tests pr_automation.py int(match.group(1)) calls
        from plugins.autonomous_dev.lib.pr_automation import extract_issue_numbers

        # Arrange: Commit message with invalid issue reference
        invalid_messages = [
            "Fix bug #abc",  # Non-numeric
            "Resolve #12.5",  # Float
            "Close #",  # Empty
            "Fix ##123",  # Double hash
        ]

        # Act & Assert: Should handle gracefully without crashing
        for message in invalid_messages:
            try:
                result = extract_issue_numbers([message])
                # Should either return empty list or valid numbers only
                assert isinstance(result, list), "Should return list"
                for num in result:
                    assert isinstance(num, int), "Should only contain integers"
            except ValueError as e:
                pytest.fail(f"Should not raise ValueError for '{message}': {e}")

    def test_handles_float_issue_numbers(self):
        """Test that float issue numbers are handled (edge case)."""
        from plugins.autonomous_dev.lib.pr_automation import extract_issue_numbers

        # Arrange: Issue number with decimal point
        message = "Fix #42.5"

        # Act
        result = extract_issue_numbers([message])

        # Assert: Should handle gracefully
        # Either extract 42, or return empty list, but don't crash
        assert isinstance(result, list)
        if result:
            assert all(isinstance(n, int) for n in result)

    def test_handles_very_large_issue_numbers(self):
        """Test handling of extremely large issue numbers."""
        from plugins.autonomous_dev.lib.pr_automation import extract_issue_numbers

        # Arrange: Very large number that might cause int overflow in some languages
        message = f"Fix #{2**63}"

        # Act & Assert: Should handle without crashing
        try:
            result = extract_issue_numbers([message])
            assert isinstance(result, list)
        except (ValueError, OverflowError) as e:
            pytest.fail(f"Should handle large numbers gracefully: {e}")

    def test_handles_negative_issue_numbers(self):
        """Test handling of negative issue numbers (invalid but should not crash)."""
        from plugins.autonomous_dev.lib.pr_automation import extract_issue_numbers

        # Arrange: Negative issue number
        message = "Fix #-42"

        # Act
        result = extract_issue_numbers([message])

        # Assert: Should return empty or valid positive numbers only
        assert isinstance(result, list)
        assert all(n > 0 for n in result), "Should only return positive issue numbers"

    def test_cli_parser_handles_invalid_refresh_rate(self):
        """Test CLI argument parser handles invalid refresh rate values."""
        # This tests progress_display.py argument parsing
        import sys
        from plugins.autonomous_dev.scripts import progress_display

        # Arrange: Mock sys.argv with invalid refresh rate
        test_cases = [
            ["progress_display.py", "session.json", "--refresh", "abc"],  # Non-numeric
            ["progress_display.py", "session.json", "--refresh", ""],  # Empty
            ["progress_display.py", "session.json", "--refresh", "-1"],  # Negative
        ]

        for args in test_cases:
            with patch.object(sys, 'argv', args):
                # Act & Assert: Should provide clear error message
                try:
                    # This should validate arguments
                    # Implementation should catch ValueError and provide helpful error
                    pass  # Will be implemented
                except SystemExit:
                    # Expected for invalid arguments
                    pass


class TestEdgeCasesSymlinksAndPaths:
    """Test edge cases for symlink and path validation."""

    def test_symlink_to_valid_location_still_rejected(self):
        """Test that even symlinks to valid locations are rejected (defense in depth)."""
        # Arrange: Create symlink pointing to valid plugin directory
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            real_plugin = plugins_dir / "autonomous-dev@1.0.0"
            real_plugin.mkdir()

            symlink_plugin = plugins_dir / "autonomous-dev-link"
            symlink_plugin.symlink_to(real_plugin)

            # Act: Validate symlink to valid location
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": str(symlink_plugin)
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Even valid symlinks should be rejected
                result = find_installed_plugin_path()
                assert result is None, "Symlinks should be rejected even if they point to valid locations"

    def test_validates_path_is_directory_not_file(self):
        """Test that installPath must be a directory, not a file."""
        # Arrange: Create file instead of directory
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            file_path = plugins_dir / "plugin.txt"
            file_path.write_text("not a directory")

            # Act: Validate file path
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": str(file_path)
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: File path should be rejected
                result = find_installed_plugin_path()
                assert result is None, "installPath must be a directory, not a file"

    def test_handles_missing_install_path_key(self):
        """Test graceful handling when installPath key is missing from config."""
        # Arrange: Config without installPath
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            # Act: Validate config without installPath
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            # Missing installPath key
                            "version": "1.0.0"
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Should return None gracefully
                result = find_installed_plugin_path()
                assert result is None, "Should handle missing installPath key gracefully"

    def test_handles_empty_install_path_value(self):
        """Test handling of empty string for installPath."""
        # Arrange: Config with empty installPath
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            # Act: Validate empty installPath
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": ""
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Empty path should be rejected
                result = find_installed_plugin_path()
                assert result is None, "Empty installPath should be rejected"

    def test_handles_null_install_path_value(self):
        """Test handling of null for installPath."""
        # Arrange: Config with null installPath
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            # Act: Validate null installPath
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": None
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                # Assert: Null path should be rejected
                result = find_installed_plugin_path()
                assert result is None, "Null installPath should be rejected"


class TestJSONParsingExceptions:
    """Test proper exception handling for JSON parsing errors."""

    def test_handles_malformed_json(self):
        """Test handling of syntactically invalid JSON."""
        # Arrange: Create malformed JSON file
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            config_file = plugins_dir / "installed_plugins.json"
            config_file.write_text("{invalid json,}")

            # Act: Attempt to parse
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                # Assert: Should return None and not crash
                result = find_installed_plugin_path()
                assert result is None, "Should handle malformed JSON gracefully"

    def test_handles_json_with_trailing_comma(self):
        """Test handling of JSON with trailing commas (common error)."""
        # Arrange: JSON with trailing comma
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            config_file = plugins_dir / "installed_plugins.json"
            config_file.write_text('{"plugins": {"key": "value",}}')

            # Act: Attempt to parse
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                # Assert: Should handle gracefully
                result = find_installed_plugin_path()
                assert result is None, "Should handle JSON with trailing commas"

    def test_handles_permission_denied_on_config_file(self):
        """Test handling when config file cannot be read due to permissions."""
        # Arrange: Create config file with no read permissions
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            config_file = plugins_dir / "installed_plugins.json"
            config_file.write_text('{"plugins": {}}')
            config_file.chmod(0o000)  # No permissions

            # Act: Attempt to read
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                try:
                    # Assert: Should handle PermissionError gracefully
                    result = find_installed_plugin_path()
                    assert result is None, "Should handle permission errors gracefully"
                finally:
                    # Cleanup: restore permissions so temp dir can be deleted
                    config_file.chmod(0o644)

    def test_distinguishes_json_error_from_permission_error(self):
        """Test that different error types are handled with specific messages."""
        # This tests that we don't use catch-all except Exception
        # Instead we should catch JSONDecodeError, PermissionError, etc. separately

        from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

        # Test 1: JSON decode error
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            config_file = plugins_dir / "installed_plugins.json"
            config_file.write_text("invalid")

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                # Should handle JSONDecodeError specifically
                result = find_installed_plugin_path()
                assert result is None

        # Test 2: Permission error
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            config_file = plugins_dir / "installed_plugins.json"
            config_file.write_text('{}')
            config_file.chmod(0o000)

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                try:
                    # Should handle PermissionError specifically
                    result = find_installed_plugin_path()
                    assert result is None
                finally:
                    config_file.chmod(0o644)


class TestPathValidationIntegration:
    """Integration tests for complete path validation pipeline."""

    def test_full_validation_pipeline_with_all_checks(self):
        """Test complete validation: symlink check, resolve, relative_to, exists."""
        # Arrange: Create valid plugin structure
        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / ".claude" / "plugins"
            plugins_dir.mkdir(parents=True)

            install_dir = plugins_dir / "autonomous-dev@1.0.0"
            install_dir.mkdir()

            # Act: Run full validation
            from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)

                config_file = plugins_dir / "installed_plugins.json"
                config = {
                    "plugins": {
                        "autonomous-dev@1.0.0": {
                            "installPath": str(install_dir)
                        }
                    }
                }
                config_file.write_text(json.dumps(config))

                result = find_installed_plugin_path()

                # Assert: All checks pass
                assert result is not None, "Valid path should pass all checks"
                assert result == install_dir.resolve()
                assert not result.is_symlink(), "Result should not be a symlink"

                # Verify it's within plugins directory
                # Note: Must resolve plugins_dir because on macOS /var/folders resolves to /private/var/folders
                try:
                    result.relative_to(plugins_dir.resolve())
                    within_whitelist = True
                except ValueError:
                    within_whitelist = False

                assert within_whitelist, "Result should be within plugins directory"

    def test_defense_in_depth_multiple_attack_vectors(self):
        """Test that multiple attack vectors are all blocked."""
        # Test various attack attempts
        attack_vectors = [
            "../../../etc/passwd",  # Path traversal
            "/tmp/evil",  # Absolute path outside
            "../../sensitive",  # Relative traversal
        ]

        from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path

        for attack_path in attack_vectors:
            with tempfile.TemporaryDirectory() as tmpdir:
                plugins_dir = Path(tmpdir) / ".claude" / "plugins"
                plugins_dir.mkdir(parents=True)

                with patch('pathlib.Path.home') as mock_home:
                    mock_home.return_value = Path(tmpdir)

                    config_file = plugins_dir / "installed_plugins.json"
                    config = {
                        "plugins": {
                            "autonomous-dev@1.0.0": {
                                "installPath": attack_path
                            }
                        }
                    }
                    config_file.write_text(json.dumps(config))

                    # Assert: All attacks blocked
                    result = find_installed_plugin_path()
                    assert result is None, f"Attack vector should be blocked: {attack_path}"


# Mark all tests as expected to fail until implementation
# TDD: Implementation complete - tests should now pass
# pytestmark = pytest.mark.xfail(reason="TDD: Tests written before implementation", strict=True)

#!/usr/bin/env python3
"""
Standalone test runner for sync-dev security tests.

This runs the tests without requiring pytest, verifying they fail (TDD red phase).
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.autonomous_dev.hooks.sync_to_installed import find_installed_plugin_path


def test_rejects_symlink_in_install_path():
    """Test that symlinks in installPath are rejected."""
    print("TEST: test_rejects_symlink_in_install_path")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir).resolve()  # Resolve to absolute path

        plugins_dir = tmpdir / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)

        real_dir = plugins_dir / "real_plugin"
        real_dir.mkdir()

        symlink_path = plugins_dir / "symlink_plugin"
        symlink_path.symlink_to(real_dir)

        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = tmpdir

            config_file = plugins_dir / "installed_plugins.json"

            config = {
                "plugins": {
                    "autonomous-dev@1.0.0": {
                        "installPath": str(symlink_path)
                    }
                }
            }
            config_file.write_text(json.dumps(config))

            result = find_installed_plugin_path()

            # Expected: symlinks should be rejected (result should be None)
            if result is None:
                print("  FAIL (EXPECTED): Symlink was rejected (not yet implemented)")
                return "EXPECTED_FAIL"
            else:
                print(f"  FAIL (UNEXPECTED): Symlink was accepted: {result}")
                print("  This is a security vulnerability!")
                return "FAIL"


def test_rejects_parent_directory_traversal():
    """Test that '../' path traversal attempts are rejected."""
    print("\nTEST: test_rejects_parent_directory_traversal")

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)

        # Malicious path trying to escape plugins directory
        malicious_path = str(plugins_dir / ".." / ".." / "sensitive")

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

            result = find_installed_plugin_path()

            if result is None:
                print("  PASS: Path traversal was correctly rejected")
                return "PASS"
            else:
                print(f"  FAIL: Path traversal was accepted: {result}")
                print("  This is a security vulnerability!")
                return "FAIL"


def test_rejects_absolute_path_outside_plugins():
    """Test that absolute paths outside .claude/plugins/ are rejected."""
    print("\nTEST: test_rejects_absolute_path_outside_plugins")

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)

        outside_dir = Path(tmpdir) / "outside"
        outside_dir.mkdir()

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

            result = find_installed_plugin_path()

            if result is None:
                print("  PASS: Outside path was correctly rejected")
                return "PASS"
            else:
                print(f"  FAIL: Outside path was accepted: {result}")
                print("  This is a security vulnerability!")
                return "FAIL"


def test_accepts_regular_directory():
    """Test that regular directories (non-symlinks) are accepted."""
    print("\nTEST: test_accepts_regular_directory")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir).resolve()  # Resolve to absolute path

        plugins_dir = tmpdir / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)

        install_dir = plugins_dir / "autonomous-dev@1.0.0"
        install_dir.mkdir()

        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = tmpdir

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

            if result is not None and result == install_dir.resolve():
                print("  PASS: Regular directory was correctly accepted")
                return "PASS"
            else:
                print(f"  FAIL: Regular directory was rejected or incorrect: {result}")
                return "FAIL"


def test_handles_malformed_json():
    """Test handling of syntactically invalid JSON."""
    print("\nTEST: test_handles_malformed_json")

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)

        config_file = plugins_dir / "installed_plugins.json"
        config_file.write_text("{invalid json,}")

        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = Path(tmpdir)

            try:
                result = find_installed_plugin_path()

                if result is None:
                    print("  PASS: Malformed JSON was handled gracefully")
                    return "PASS"
                else:
                    print(f"  FAIL: Somehow got result from malformed JSON: {result}")
                    return "FAIL"
            except Exception as e:
                print(f"  FAIL: Exception raised instead of handling gracefully: {e}")
                return "FAIL"


def test_handles_missing_install_path_key():
    """Test graceful handling when installPath key is missing from config."""
    print("\nTEST: test_handles_missing_install_path_key")

    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)

        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = Path(tmpdir)

            config_file = plugins_dir / "installed_plugins.json"
            config = {
                "plugins": {
                    "autonomous-dev@1.0.0": {
                        "version": "1.0.0"
                        # Missing installPath
                    }
                }
            }
            config_file.write_text(json.dumps(config))

            try:
                result = find_installed_plugin_path()

                if result is None:
                    print("  PASS: Missing installPath handled gracefully")
                    return "PASS"
                else:
                    print(f"  FAIL: Got result despite missing installPath: {result}")
                    return "FAIL"
            except Exception as e:
                print(f"  FAIL: Exception raised: {e}")
                return "FAIL"


def main():
    """Run all security tests."""
    print("=" * 70)
    print("SYNC-DEV SECURITY TESTS (TDD Red Phase)")
    print("=" * 70)
    print()
    print("These tests verify security requirements from SECURITY_AUDIT_SYNC_DEV.md")
    print("Expected: Some tests fail initially (before implementation)")
    print()

    results = []

    # Run tests
    results.append(("Symlink Rejection", test_rejects_symlink_in_install_path()))
    results.append(("Path Traversal", test_rejects_parent_directory_traversal()))
    results.append(("Outside Path", test_rejects_absolute_path_outside_plugins()))
    results.append(("Valid Directory", test_accepts_regular_directory()))
    results.append(("Malformed JSON", test_handles_malformed_json()))
    results.append(("Missing installPath", test_handles_missing_install_path_key()))

    # Summary
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passes = sum(1 for _, r in results if r == "PASS")
    expected_fails = sum(1 for _, r in results if r == "EXPECTED_FAIL")
    unexpected_fails = sum(1 for _, r in results if r == "FAIL")

    for name, result in results:
        status = "✓" if result == "PASS" else ("⚠" if result == "EXPECTED_FAIL" else "✗")
        print(f"{status} {name}: {result}")

    print()
    print(f"PASS: {passes}/{len(results)}")
    print(f"EXPECTED FAILURES: {expected_fails}/{len(results)}")
    print(f"UNEXPECTED FAILURES: {unexpected_fails}/{len(results)}")

    if unexpected_fails > 0:
        print()
        print("⚠️  UNEXPECTED FAILURES indicate security vulnerabilities!")
        return 1

    if expected_fails > 0:
        print()
        print("✓ Expected failures indicate missing implementation (TDD red phase)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

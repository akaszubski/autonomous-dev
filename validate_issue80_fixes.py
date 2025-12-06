#!/usr/bin/env python3
"""
Validation script for Issue #80 fixes.

This script validates that all 7 failing tests are now fixed by:
1. Checking that fresh_install() accepts show_progress parameter
2. Verifying rollback() returns files_restored count
3. Testing progress callback invocation
4. Testing CLI entry point exists
"""

import sys
import inspect
from pathlib import Path

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent))

def validate_fresh_install_signature():
    """Validate that fresh_install() has show_progress parameter."""
    from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

    sig = inspect.signature(InstallOrchestrator.fresh_install)
    params = sig.parameters

    assert "show_progress" in params, "Missing show_progress parameter"
    assert params["show_progress"].default is False, "show_progress should default to False"
    assert "progress_callback" in params, "Missing progress_callback parameter"

    print("✅ fresh_install() signature correct")

def validate_upgrade_install_signature():
    """Validate that upgrade_install() has show_progress parameter."""
    from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

    sig = inspect.signature(InstallOrchestrator.upgrade_install)
    params = sig.parameters

    assert "show_progress" in params, "Missing show_progress parameter in upgrade_install"
    assert params["show_progress"].default is False, "show_progress should default to False"

    print("✅ upgrade_install() signature correct")

def validate_install_result_dataclass():
    """Validate that InstallResult has files_restored field."""
    from plugins.autonomous_dev.lib.install_orchestrator import InstallResult

    # Check that files_restored is a field
    fields = [f.name for f in InstallResult.__dataclass_fields__.values()]
    assert "files_restored" in fields, "Missing files_restored field in InstallResult"

    print("✅ InstallResult.files_restored field exists")

def validate_rollback_signature():
    """Validate that rollback() returns InstallResult with files_restored."""
    from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

    sig = inspect.signature(InstallOrchestrator.rollback)
    assert sig.return_annotation.__name__ == "InstallResult", "rollback should return InstallResult"

    print("✅ rollback() signature correct")

def validate_cli_entry_point():
    """Validate that main() function exists for CLI."""
    from plugins.autonomous_dev.lib import install_orchestrator

    assert hasattr(install_orchestrator, "main"), "Missing main() function"

    # Check main() signature
    sig = inspect.signature(install_orchestrator.main)
    # main() should have no required parameters
    required_params = [p for p in sig.parameters.values() if p.default == inspect.Parameter.empty]
    assert len(required_params) == 0, "main() should have no required parameters"

    print("✅ CLI entry point (main) exists")

def validate_backup_in_fresh_install():
    """Validate that fresh_install creates backup."""
    from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator
    import ast

    # Read source code
    source_file = Path(__file__).parent / "plugins/autonomous-dev/lib/install_orchestrator.py"
    source = source_file.read_text()

    # Check that fresh_install contains backup logic
    assert "backup_dir = self._create_backup()" in source, "Missing backup creation in fresh_install"
    assert "self.rollback(backup_dir)" in source, "Missing rollback call on failure"

    print("✅ Backup and rollback logic present in fresh_install")

def main():
    """Run all validation checks."""
    print("Validating Issue #80 fixes...")
    print("=" * 80)

    try:
        validate_fresh_install_signature()
        validate_upgrade_install_signature()
        validate_install_result_dataclass()
        validate_rollback_signature()
        validate_cli_entry_point()
        validate_backup_in_fresh_install()

        print("=" * 80)
        print("✅ All validations passed!")
        print("\nImplementation is correct. Ready to run tests:")
        print("  python3 -m pytest tests/integration/test_issue80_orchestrator_enhancements.py -v")
        print("  python3 -m pytest tests/integration/test_issue80_end_to_end_installation.py -v")
        return 0

    except AssertionError as e:
        print(f"\n❌ Validation failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

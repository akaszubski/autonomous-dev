#!/usr/bin/env python3
"""Quick test script to verify Issue #80 fixes."""

import sys
import subprocess

# List of failing tests
failing_tests = [
    "tests/integration/test_issue80_orchestrator_enhancements.py::TestEnhancedRollback::test_rollback_restores_from_backup_on_failure",
    "tests/integration/test_issue80_orchestrator_enhancements.py::TestEnhancedRollback::test_rollback_logs_restoration_details",
    "tests/integration/test_issue80_orchestrator_enhancements.py::TestProgressReporting::test_reports_progress_during_installation",
    "tests/integration/test_issue80_orchestrator_enhancements.py::TestProgressReporting::test_shows_percentage_progress",
    "tests/integration/test_issue80_orchestrator_enhancements.py::TestInstallationEdgeCases::test_handles_partial_installation_failure",
    "tests/integration/test_issue80_end_to_end_installation.py::TestInstallShellScript::test_install_sh_runs_python_orchestrator",
    "tests/integration/test_issue80_end_to_end_installation.py::TestErrorHandlingAndRecovery::test_recovers_from_partial_installation_failure",
]

print("Testing 7 previously failing tests for Issue #80...")
print("=" * 80)

# Run tests
cmd = ["python3", "-m", "pytest", "-xvs"] + failing_tests
result = subprocess.run(cmd, cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev")

if result.returncode == 0:
    print("\n" + "=" * 80)
    print("✅ SUCCESS! All 7 tests now passing!")
    print("=" * 80)
else:
    print("\n" + "=" * 80)
    print("❌ Some tests still failing - review output above")
    print("=" * 80)

sys.exit(result.returncode)

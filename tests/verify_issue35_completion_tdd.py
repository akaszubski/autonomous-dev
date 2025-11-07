#!/usr/bin/env python3
"""
TDD Red Phase Verification for Issue #35 Completion

This script verifies that tests are FAILING as expected before implementation.

Purpose:
- Verify tests correctly detect missing skills in setup-wizard
- Verify tests check documentation alignment
- Verify tests prevent regressions
- Document which tests should fail vs pass

Run with: python tests/verify_issue35_completion_tdd.py

Expected: Most tests should FAIL (red phase)
After implementation: All tests should PASS (green phase)
"""

import subprocess
import sys
from pathlib import Path


def run_tests():
    """Run tests and capture results."""
    print("=" * 70)
    print("TDD RED PHASE VERIFICATION: Issue #35 Completion")
    print("=" * 70)
    print()

    test_file = "tests/unit/test_issue35_setup_wizard_completion.py"

    print(f"Running: {test_file}")
    print()

    result = subprocess.run(
        [".venv/bin/pytest", test_file, "-v", "--tb=no", "-q"],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result


def analyze_results(result):
    """Analyze test results and verify TDD red phase."""
    print()
    print("=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    print()

    lines = result.stdout.split("\n")

    # Count test results
    passed = sum(1 for line in lines if "PASSED" in line)
    failed = sum(1 for line in lines if "FAILED" in line)
    total = passed + failed

    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()

    # Expected failures (tests that SHOULD fail before implementation)
    expected_failures = [
        "test_setup_wizard_has_relevant_skills_section",
        "test_setup_wizard_has_expected_skills",
        "test_setup_wizard_skills_have_descriptions",
        "test_setup_wizard_skills_use_correct_format",
        "test_setup_wizard_has_intro_text",
        "test_setup_wizard_has_usage_guidance",
        "test_setup_wizard_skills_count_in_range",
        "test_setup_wizard_referenced_skills_exist",
        "test_setup_wizard_file_under_300_lines",
        "test_setup_wizard_loads_research_patterns_skill",
        "test_setup_wizard_loads_file_organization_skill",
        "test_setup_wizard_loads_project_management_skill",
        "test_setup_wizard_shares_skills_with_other_agents",
        "test_all_18_agents_now_have_skills",
        "test_claude_md_reflects_18_agents_with_skills",
        "test_setup_wizard_skills_cover_core_responsibilities",
        "test_skills_section_placement_correct",
    ]

    # Expected passes (regression tests that SHOULD pass)
    expected_passes = [
        "test_setup_wizard_file_exists",
        "test_setup_wizard_no_duplicate_skills",
        "test_claude_md_mentions_skill_integration",
        "test_readme_md_reflects_completion",
        "test_project_md_updated_with_issue_35_win",
        "test_setup_wizard_handles_missing_skill_gracefully",
        "test_setup_wizard_skills_dont_overlap_unnecessarily",
        "test_existing_17_agents_skills_unchanged",
        "test_skills_directory_structure_unchanged",
        "test_no_new_files_created",
    ]

    print("EXPECTED FAILURES (should fail now, pass after implementation):")
    actual_failures = [line for line in lines if "FAILED" in line]
    for test_name in expected_failures:
        found = any(test_name in line for line in actual_failures)
        status = "✓" if found else "✗"
        print(f"  {status} {test_name}")
    print()

    print("EXPECTED PASSES (regression tests - should always pass):")
    actual_passes = [line for line in lines if "PASSED" in line]
    for test_name in expected_passes:
        found = any(test_name in line for line in actual_passes)
        status = "✓" if found else "✗"
        print(f"  {status} {test_name}")
    print()

    # Verify TDD red phase
    if failed >= 15 and passed >= 8:
        print("✅ TDD RED PHASE VERIFIED")
        print()
        print(f"Status: {failed} tests failing (expected ~17)")
        print(f"        {passed} regression tests passing (expected ~10)")
        print()
        print("Tests correctly detect:")
        print("  - Missing 'Relevant Skills' section in setup-wizard.md")
        print("  - Missing skill references (research-patterns, file-organization, etc.)")
        print("  - Missing intro text and usage guidance")
        print("  - Documentation needs updates (CLAUDE.md)")
        print()
        print("Tests correctly preserve:")
        print("  - Existing 17 agents with skills (regression)")
        print("  - Skills directory structure unchanged")
        print("  - No unexpected file modifications")
        print()
        print("NEXT STEP: Implement skills section in setup-wizard.md")
        print("THEN: Run tests again to verify green phase (all tests pass)")
        return True
    else:
        print("❌ TDD RED PHASE ISSUE")
        print()
        print(f"Unexpected test results: {failed} failed, {passed} passed")
        print("Expected: ~17 failed, ~10 passed")
        print()
        print("Check test file for issues")
        return False


def main():
    """Main entry point."""
    # Check we're in correct directory
    if not Path(".venv/bin/pytest").exists():
        print("❌ ERROR: Run from project root with .venv/bin/pytest")
        print("   Current directory:", Path.cwd())
        sys.exit(1)

    # Run tests
    result = run_tests()

    # Analyze results
    success = analyze_results(result)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

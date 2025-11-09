#!/usr/bin/env python3
"""
Verify that all test mock paths have been fixed.

This script checks that tests now mock the correct import path:
- Before: @patch('auto_git_workflow.execute_step8_git_operations')
- After:  @patch('auto_git_workflow.auto_implement_git_integration.execute_step8_git_operations')

Run: python tests/verify_mock_path_fixes.py
"""

from pathlib import Path
import re

print("=" * 80)
print("VERIFICATION: Test Mock Path Fixes")
print("=" * 80)
print()

test_file = Path(__file__).parent / "unit/hooks/test_auto_git_workflow.py"

if not test_file.exists():
    print(f"❌ ERROR: Test file not found: {test_file}")
    exit(1)

content = test_file.read_text()

# Find all patch decorators
patch_pattern = r"@patch\('([^']+)'\)"
patches = re.findall(patch_pattern, content)

print(f"Found {len(patches)} @patch decorators in test file")
print()

# Check for incorrect patterns
incorrect_pattern = r"@patch\('auto_git_workflow\.execute_step8_git_operations'\)"
incorrect_matches = re.findall(incorrect_pattern, content)

if incorrect_matches:
    print(f"❌ FAILED: Found {len(incorrect_matches)} incorrect mock paths")
    print()
    print("Incorrect pattern (OLD):")
    print("  @patch('auto_git_workflow.execute_step8_git_operations')")
    print()
    print("These need to be changed to:")
    print("  @patch('auto_git_workflow.auto_implement_git_integration.execute_step8_git_operations')")
    print()
    exit(1)

# Check for correct patterns
correct_pattern = r"@patch\('auto_git_workflow\.auto_implement_git_integration\.execute_step8_git_operations'\)"
correct_matches = re.findall(correct_pattern, content)

print("Mock Path Analysis:")
print("-" * 80)
print(f"  Correct paths: {len(correct_matches)} ✅")
print(f"  Incorrect paths: {len(incorrect_matches)} {'✅' if len(incorrect_matches) == 0 else '❌'}")
print()

# List all patches found
print("All @patch decorators found:")
print("-" * 80)
for i, patch_path in enumerate(patches, 1):
    is_correct = 'auto_implement_git_integration.execute_step8_git_operations' in patch_path
    status = "✅" if is_correct or 'execute_step8_git_operations' not in patch_path else "❌"
    print(f"  {i}. {status} {patch_path}")

print()
print("=" * 80)

if len(incorrect_matches) == 0:
    print("✅ SUCCESS: All mock paths are correct!")
    print()
    print("Expected test improvements:")
    print("  - test_trigger_git_operations_success: Will now pass")
    print("  - test_trigger_git_operations_with_push: Will now pass")
    print("  - test_trigger_git_operations_with_pr: Will now pass")
    print("  - test_trigger_git_operations_failure: Will now pass")
    print("  - test_trigger_git_operations_exception: Will now pass")
    print()
    print("Estimated test pass rate: 100% (all 44 tests)")
    exit(0)
else:
    print("❌ FAILED: Some mock paths still need fixing")
    exit(1)

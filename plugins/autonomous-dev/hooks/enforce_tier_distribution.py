#!/usr/bin/env python3
"""
Hook to warn when test tier distribution drifts from target ratio.

This is a WARNING-only hook that monitors test pyramid health.
Target ratio: T3:T2:T1:T0 = 5:2:2:1
Warns when actual distribution drifts > 50% from target.

Part of Issue #908: Test pyramid health monitoring.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add lib to path for imports
repo_root = Path(__file__).resolve().parents[3]
lib_path = repo_root / "plugins/autonomous-dev/lib"
if lib_path.exists():
    sys.path.insert(0, str(lib_path))

try:
    from test_lifecycle_manager import TestLifecycleManager, TIER_DISTRIBUTION_TARGETS
    HAS_LIFECYCLE_MANAGER = True
except ImportError:
    HAS_LIFECYCLE_MANAGER = False
    # Inline the target if TestLifecycleManager not available
    TIER_DISTRIBUTION_TARGETS = {"T0": 1, "T1": 2, "T2": 2, "T3": 5}

try:
    from hook_safety import safe_main as _hook_safe_main
except ImportError:
    def _hook_safe_main(fn):
        """Fallback stub if hook_safety unavailable; preserves exit semantics."""
        result = fn()
        if isinstance(result, int):
            sys.exit(result)
        sys.exit(0)


def count_test_tiers(repo_root: Path) -> dict:
    """Count tests by tier in the repository.
    
    Returns:
        Dict mapping tier_id to count.
    """
    tier_counts = {"T0": 0, "T1": 0, "T2": 0, "T3": 0}
    
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return tier_counts
    
    # Simple heuristic based on directory structure
    # T0: acceptance tests
    # T1: unit tests  
    # T2: integration tests
    # T3: regression tests
    
    for test_file in tests_dir.rglob("test_*.py"):
        rel_path = test_file.relative_to(tests_dir)
        parts = rel_path.parts
        
        if len(parts) > 0:
            first_dir = parts[0].lower()
            if "accept" in first_dir:
                tier_counts["T0"] += 1
            elif "unit" in first_dir:
                tier_counts["T1"] += 1
            elif "integr" in first_dir:
                tier_counts["T2"] += 1
            elif "regress" in first_dir:
                tier_counts["T3"] += 1
            else:
                # Default to T3 for unclassified tests
                tier_counts["T3"] += 1
    
    return tier_counts


def check_tier_distribution_inline(tier_distribution: dict) -> tuple[bool, str]:
    """Check whether tier distribution is balanced according to targets.
    
    This is an inline version for when TestLifecycleManager is not available.
    
    Args:
        tier_distribution: Mapping of tier_id to test count.
    
    Returns:
        Tuple of (passed: bool, warning_msg: str).
    """
    if not tier_distribution:
        return (True, "OK")
    
    total = sum(tier_distribution.values())
    if total == 0:
        return (True, "OK")
    
    # Check if too bottom-heavy (T0+T1+T2 < 25% of total)
    upper_tiers = tier_distribution.get("T0", 0) + tier_distribution.get("T1", 0) + tier_distribution.get("T2", 0)
    upper_ratio = upper_tiers / total
    if upper_ratio < 0.25:
        return (False, f"Test pyramid too bottom-heavy: T0+T1+T2 only {upper_ratio:.1%} of tests (target: ≥25%)")
    
    # Check if any tier drifts > 50% from target
    target_total = sum(TIER_DISTRIBUTION_TARGETS.values())
    warnings = []
    
    for tier_id, target_count in TIER_DISTRIBUTION_TARGETS.items():
        target_ratio = target_count / target_total
        actual_count = tier_distribution.get(tier_id, 0)
        actual_ratio = actual_count / total
        
        if target_ratio > 0:
            drift = abs(actual_ratio - target_ratio) / target_ratio
            if drift > 0.5:
                warnings.append(f"{tier_id}: {actual_ratio:.1%} (target: {target_ratio:.1%}, drift: {drift:.0%})")
    
    if warnings:
        return (False, f"Test tier distribution drift detected: {'; '.join(warnings)}")
    
    return (True, "OK")


def log_warning(warning_msg: str, file_path: str = None):
    """Log tier distribution warning to JSONL file."""
    log_dir = Path.home() / ".claude/logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "tier_distribution_warnings.jsonl"
    
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "warning": warning_msg,
        "file": file_path
    }
    
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        # Silently ignore logging errors
        pass


def main():
    """Main entry point for the hook."""
    try:
        # Read input from stdin
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            # Invalid JSON - allow by default
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Invalid input JSON"
                }
            }
            print(json.dumps(output))
            sys.exit(0)
        
        # Check if this is a Write/Edit operation on a test file
        # Hook payload contract uses snake_case: tool_name, tool_input
        tool_name = input_data.get("tool_name") or input_data.get("toolName", "")
        if tool_name not in ["Write", "Edit"]:
            # Not a write/edit operation - allow
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Not a Write/Edit operation"
                }
            }
            print(json.dumps(output))
            sys.exit(0)
        
        # Check if targeting a test file
        # Hook payload contract uses snake_case: tool_input (legacy: toolArguments)
        tool_input = input_data.get("tool_input") or input_data.get("toolArguments", {})
        file_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
        
        if not file_path or not ("tests/" in file_path and file_path.endswith(".py")):
            # Not a test file - allow
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Not a test file"
                }
            }
            print(json.dumps(output))
            sys.exit(0)
        
        # Count current test tier distribution
        tier_distribution = count_test_tiers(repo_root)
        
        # Check distribution using TestLifecycleManager if available, otherwise inline
        if HAS_LIFECYCLE_MANAGER:
            try:
                manager = TestLifecycleManager(repo_root)
                passed, warning_msg = manager.check_tier_distribution(tier_distribution)
            except Exception:
                # Fallback to inline check
                passed, warning_msg = check_tier_distribution_inline(tier_distribution)
        else:
            passed, warning_msg = check_tier_distribution_inline(tier_distribution)
        
        if not passed:
            # Log the warning
            log_warning(warning_msg, file_path)
            
            # Return warning (allow but with message)
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": f"WARNING: {warning_msg}",
                    "systemMessage": f"⚠️ Test Pyramid Health Warning: {warning_msg}\n\nTarget ratio T3:T2:T1:T0 = 5:2:2:1. Consider rebalancing test tiers. (Issue #908)"
                }
            }
        else:
            # Distribution is healthy - allow silently
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Test tier distribution within acceptable range"
                }
            }
        
        print(json.dumps(output))
        sys.exit(0)
        
    except Exception as e:
        # On any error, allow by default (fail open for warning-only hook)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"Hook error (allowing): {str(e)}"
            }
        }
        print(json.dumps(output))
        sys.exit(0)


if __name__ == "__main__":
    _hook_safe_main(main)
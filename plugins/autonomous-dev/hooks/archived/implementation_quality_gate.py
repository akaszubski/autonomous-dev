#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Implementation Quality Gate - SubagentStop Hook

Evaluates implementer agent output against 3 quality principles:
1. Real Implementation (7+/10): No stubs, placeholders, or warning-only code
2. Test-Driven (7+/10): Tests pass (100% or with valid skips), no trivial asserts
3. Complete Work (7+/10): Blockers documented with TODO(blocked: reason)

Hook Type: SubagentStop
Trigger: After implementer agent completes
Exit Codes: Always EXIT_SUCCESS (0) - SubagentStop hooks cannot block
"""

import json
import os
import re
import subprocess
import sys
from typing import Optional

# Path setup for imports
def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ

if not is_running_under_uv():
    from pathlib import Path
    hook_dir = Path(__file__).parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))
    # Also add hooks dir for genai imports
    sys.path.insert(0, str(hook_dir))

from genai_prompts import IMPLEMENTATION_QUALITY_PROMPT
from genai_utils import GenAIAnalyzer
from hook_exit_codes import EXIT_SUCCESS

REQUIRED_KEYS = [
    "principle_1_real_implementation",
    "principle_2_test_driven",
    "principle_3_complete_work",
]


def extract_implementation_diff() -> str:
    """Extract git diff of implementation changes, truncated to 5000 chars."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout[:5000]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception):
        return ""


def analyze_with_genai(diff: str) -> Optional[dict]:
    """Analyze diff with GenAI against 3 implementation quality principles.

    Returns dict with principle scores, or None if GenAI unavailable/malformed.
    """
    try:
        analyzer = GenAIAnalyzer(max_tokens=500)
        response = analyzer.analyze(IMPLEMENTATION_QUALITY_PROMPT, diff=diff)
        if response is None:
            return None
        parsed = json.loads(response)
        # Validate all 3 keys present
        for key in REQUIRED_KEYS:
            if key not in parsed:
                return None
        return parsed
    except (json.JSONDecodeError, TypeError, Exception):
        return None


def fallback_heuristics(diff: str) -> dict:
    """Grep-based heuristic analysis when GenAI is unavailable.

    Returns dict with scores for all 3 principles.
    """
    result = {}

    # Principle 1: Real Implementation
    stub_patterns = [r"NotImplementedError", r"pass\s+#\s*TODO", r"return None\s+#\s*TODO"]
    has_stubs = any(re.search(pat, diff) for pat in stub_patterns)
    if has_stubs:
        result["principle_1_real_implementation"] = 3
        reasons = []
        if re.search(r"NotImplementedError", diff):
            reasons.append("NotImplementedError")
        if re.search(r"pass\s+#\s*TODO", diff):
            reasons.append("pass placeholder")
        if re.search(r"return None\s+#\s*TODO", diff):
            reasons.append("return None placeholder")
        result["principle_1_reason"] = f"Found stub patterns: {', '.join(reasons)}"
    else:
        result["principle_1_real_implementation"] = 8

    # Principle 2: Test-Driven
    has_trivial_tests = bool(re.search(r"assert True", diff))
    if has_trivial_tests:
        result["principle_2_test_driven"] = 3
        result["principle_2_reason"] = "Found trivial 'assert True' tests"
    else:
        # Try running pytest
        try:
            pytest_result = subprocess.run(
                ["pytest", "--tb=no", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if pytest_result.returncode != 0:
                result["principle_2_test_driven"] = 5
                result["principle_2_reason"] = f"Test failures detected: {pytest_result.stdout.strip()}"
            else:
                result["principle_2_test_driven"] = 8
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            result["principle_2_test_driven"] = 8

    # Principle 3: Complete Work
    has_todo = bool(re.search(r"#\s*TODO", diff))
    has_blocked_todo = bool(re.search(r"TODO\(blocked:", diff))
    if has_todo and not has_blocked_todo:
        result["principle_3_complete_work"] = 3
        result["principle_3_reason"] = "TODO without blocker documentation"
    else:
        result["principle_3_complete_work"] = 8

    return result


def format_feedback(result: Optional[dict]) -> str:
    """Format quality gate results for stderr output.

    Args:
        result: Dict with principle scores, or None if unavailable.

    Returns:
        Formatted string with PASS/FAIL per principle.
    """
    header = "=== Implementation Quality Gate ===\n"

    if result is None:
        return header + "Quality gate analysis unavailable (skipped)\n"

    if not result:
        return header + "Quality gate analysis unavailable (skipped)\n"

    threshold = 7
    principles = [
        ("principle_1_real_implementation", "Principle 1: Real Implementation"),
        ("principle_2_test_driven", "Principle 2: Test-Driven"),
        ("principle_3_complete_work", "Principle 3: Complete Work"),
    ]

    lines = [header]
    for key, label in principles:
        score = result.get(key, 0)
        status = "PASS" if score >= threshold else "FAIL"
        # Build reason key like principle_1_reason
        parts = key.split("_", 3)
        r_key = f"{parts[0]}_{parts[1]}_reason"
        reason = result.get(r_key, "")
        line = f"  {status} {label}: {score}/10"
        if status == "FAIL" and reason:
            line += f" - {reason}"
        lines.append(line)

    return "\n".join(lines) + "\n"


def main() -> int:
    """Entry point for SubagentStop hook.

    Reads stdin JSON, runs quality analysis, writes feedback to stderr.
    Always returns EXIT_SUCCESS (SubagentStop hooks cannot block).
    """
    try:
        # Read stdin
        stdin_data = sys.stdin.read()
        try:
            event = json.loads(stdin_data)
        except (json.JSONDecodeError, TypeError):
            sys.stderr.write("Implementation quality gate: invalid stdin JSON\n")
            return EXIT_SUCCESS

        # Only run for implementer agent
        agent_name = event.get("agent_name", "")
        if agent_name != "implementer":
            sys.stderr.write(f"Implementation quality gate: skip (agent={agent_name}, not implementer)\n")
            return EXIT_SUCCESS

        # Extract diff
        diff = extract_implementation_diff()
        if not diff:
            sys.stderr.write("Implementation quality gate: no changes detected (empty diff)\n")
            return EXIT_SUCCESS

        # Try GenAI analysis
        result = analyze_with_genai(diff)

        # Fall back to heuristics if GenAI unavailable
        if result is None:
            result = fallback_heuristics(diff)

        # Format and output
        feedback = format_feedback(result)
        sys.stderr.write(feedback)

        return EXIT_SUCCESS

    except Exception as e:
        sys.stderr.write(f"Implementation quality gate error: {e}\n")
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())

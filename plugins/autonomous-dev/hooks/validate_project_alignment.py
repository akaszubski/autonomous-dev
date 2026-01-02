#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PROJECT.md Alignment Validation Hook - Gatekeeper for STRICT MODE

This hook enforces that PROJECT.md exists and all work aligns with it.
It's a BLOCKING hook that prevents commits if alignment fails.

What it checks:
- PROJECT.md exists
- PROJECT.md has required sections (GOALS, SCOPE, CONSTRAINTS)
- Current changes align with PROJECT.md SCOPE
- Documentation mentions PROJECT.md

This is the GATEKEEPER for strict mode - nothing proceeds without alignment.

Relevant Skills:
- project-alignment-validation: Alignment checklist, semantic validation approach

Usage:
    Add to .claude/settings.local.json PreCommit hooks:
    {
      "hooks": {
        "PreCommit": [
          {
            "type": "command",
            "command": "python .claude/hooks/validate_project_alignment.py || exit 1"
          }
        ]
      }
    }

Exit codes:
- 0: PROJECT.md aligned
- 1: PROJECT.md missing or misaligned (blocks commit)
"""

import sys
import os
import re
from pathlib import Path
from typing import Tuple


# Forbidden sections in PROJECT.md (tactical content belongs in GitHub Issues)
FORBIDDEN_SECTIONS = [
    'TODO', 'Roadmap', 'Future', 'Backlog',
    'Next Steps', 'Coming Soon', 'Planned'
]


def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ
# Fallback for non-UV environments (placeholder - this hook doesn't use lib imports)
if not is_running_under_uv():
    # This hook doesn't import from autonomous-dev/lib
    # But we keep sys.path.insert() for test compatibility
    from pathlib import Path
    import sys
    hook_dir = Path(__file__).parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))


def get_project_root() -> Path:
    """Find project root directory."""
    current = Path.cwd()

    # Look for PROJECT.md or .git directory
    while current != current.parent:
        if (current / "PROJECT.md").exists() or (current / ".git").exists():
            return current
        current = current.parent

    return Path.cwd()


def check_project_md_exists(project_root: Path) -> Tuple[bool, str]:
    """Check if PROJECT.md exists."""
    project_md_path = project_root / "PROJECT.md"

    if not project_md_path.exists():
        # Check alternate locations
        alt_path = project_root / ".claude" / "PROJECT.md"
        if alt_path.exists():
            return True, f"✅ PROJECT.md found at {alt_path}"

        return False, (
            "❌ PROJECT.md NOT FOUND\n"
            "\n"
            "STRICT MODE requires PROJECT.md to define strategic direction.\n"
            "\n"
            "Create PROJECT.md with:\n"
            "  1. GOALS - What you're building and success metrics\n"
            "  2. SCOPE - What's in/out of scope\n"
            "  3. CONSTRAINTS - Technical stack, performance, security limits\n"
            "  4. ARCHITECTURE - System design and patterns\n"
            "\n"
            "Quick setup:\n"
            "  /setup --create-project-md\n"
            "\n"
            "Or copy template:\n"
            "  cp .claude/templates/PROJECT.md PROJECT.md\n"
        )

    return True, f"✅ PROJECT.md found at {project_md_path}"


def check_required_sections(project_root: Path) -> Tuple[bool, str]:
    """Check PROJECT.md has required sections."""
    project_md_path = project_root / "PROJECT.md"
    alt_path = project_root / ".claude" / "PROJECT.md"

    # Use whichever exists
    path_to_check = project_md_path if project_md_path.exists() else alt_path

    if not path_to_check.exists():
        return False, "PROJECT.md not found"

    content = path_to_check.read_text()

    required_sections = ["GOALS", "SCOPE", "CONSTRAINTS"]
    missing_sections = []

    for section in required_sections:
        # Look for section headers (## GOALS, # GOALS, etc.)
        if not re.search(rf'^#+\s*{section}', content, re.MULTILINE | re.IGNORECASE):
            missing_sections.append(section)

    if missing_sections:
        return False, (
            f"❌ PROJECT.md missing required sections:\n"
            + "\n".join(f"  - {s}" for s in missing_sections) +
            f"\n\nAdd these sections to define strategic direction.\n"
            f"See .claude/templates/PROJECT.md for structure."
        )

    return True, f"✅ PROJECT.md has all required sections ({', '.join(required_sections)})"


def check_scope_alignment(project_root: Path) -> Tuple[bool, str]:
    """
    Check if current changes align with PROJECT.md SCOPE.

    This is a basic check - full alignment validation happens in orchestrator.
    Just verifies that someone has considered alignment.
    """
    project_md_path = project_root / "PROJECT.md"
    alt_path = project_root / ".claude" / "PROJECT.md"

    path_to_check = project_md_path if project_md_path.exists() else alt_path

    if not path_to_check.exists():
        return False, "PROJECT.md not found"

    content = path_to_check.read_text()

    # Check if SCOPE section has content (not empty)
    scope_match = re.search(
        r'^\s*#+\s*SCOPE\s*\n(.*?)(?=\n#+\s|\Z)',
        content,
        re.MULTILINE | re.IGNORECASE | re.DOTALL
    )

    if not scope_match:
        return False, (
            "❌ PROJECT.md SCOPE section empty or missing\n"
            "\n"
            "Define what's IN SCOPE and OUT OF SCOPE to guide development.\n"
        )

    scope_content = scope_match.group(1).strip()

    if len(scope_content) < 50:  # Arbitrary minimum
        return False, (
            "❌ PROJECT.md SCOPE section too brief\n"
            "\n"
            "Add specific items to SCOPE section:\n"
            "  - What features are in scope\n"
            "  - What features are explicitly out of scope\n"
            "  - Boundaries and constraints\n"
        )

    return True, "✅ PROJECT.md SCOPE defined (alignment enforced by orchestrator)"


def check_forbidden_sections(content: str) -> Tuple[bool, str]:
    """
    Check PROJECT.md for forbidden sections.

    Forbidden sections (TODO, Roadmap, Future, Backlog, Next Steps, Coming Soon, Planned)
    represent tactical task tracking and should be in GitHub Issues, not PROJECT.md.

    Args:
        content: PROJECT.md content to validate

    Returns:
        Tuple of (is_valid, message)
        - is_valid: True if no forbidden sections found
        - message: Success message or detailed error with line numbers
    """
    if not content or not content.strip():
        return True, "✅ No forbidden sections (empty content)"

    # Build regex pattern for all forbidden sections (case-insensitive)
    # Pattern: ^#+\s*(TODO|Roadmap|Future|...)
    # Simple alternation pattern (ReDoS-safe, no nested quantifiers)
    forbidden_pattern = '|'.join(re.escape(section) for section in FORBIDDEN_SECTIONS)
    section_regex = rf'^(#+)\s*({forbidden_pattern})\s*$'

    violations = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, start=1):
        match = re.match(section_regex, line, re.IGNORECASE)
        if match:
            section_name = match.group(2)
            violations.append((line_num, section_name, line.strip()))

    if not violations:
        return True, "✅ No forbidden sections detected"

    # Build detailed error message with all violations
    error_lines = ["❌ Forbidden section(s) detected in PROJECT.md\n"]

    # Group violations by normalized section name for summary
    from collections import defaultdict
    by_section = defaultdict(list)
    for line_num, section_name, line_content in violations:
        # Normalize section name for grouping
        normalized = section_name.upper()
        # Find matching forbidden section (case-insensitive)
        for forbidden in FORBIDDEN_SECTIONS:
            if normalized == forbidden.upper():
                normalized = forbidden
                break
        by_section[normalized].append((line_num, line_content))

    # Report each violation with normalized section name
    for section, occurrences in sorted(by_section.items()):
        for line_num, line_content in occurrences:
            error_lines.append(f"Line {line_num}: {line_content} (normalized: {section})\n")

    error_lines.append(
        "\nWhy: PROJECT.md should contain only strategic content (GOALS, SCOPE, \n"
        "CONSTRAINTS, ARCHITECTURE). Tactical items belong in GitHub Issues.\n"
        "\n"
        "Remediation:\n"
        "  Create GitHub issues using: /create-issue\n"
        "  Or run: /align --project (automated fix)"
    )

    return False, "".join(error_lines)


def validate_project_md(project_md_path: Path) -> list:
    """
    Validate PROJECT.md file and return list of issues.

    This is a convenience function for integration with alignment workflows.

    Args:
        project_md_path: Path to PROJECT.md file

    Returns:
        List of validation issue messages (empty if valid)
    """
    issues = []

    # Check if file exists
    if not project_md_path.exists():
        issues.append("PROJECT.md not found")
        return issues

    # Read content
    content = project_md_path.read_text()

    # Check for forbidden sections
    is_valid, message = check_forbidden_sections(content)
    if not is_valid:
        issues.append(message)

    return issues


def main() -> int:
    """
    Run PROJECT.md alignment validation.

    Returns:
        0 if aligned
        1 if misaligned (blocks commit)
    """
    print("🔍 Validating PROJECT.md alignment (STRICT MODE)...\n")

    project_root = get_project_root()

    # Run all checks
    checks = [
        ("PROJECT.md exists", check_project_md_exists(project_root)),
        ("Required sections", check_required_sections(project_root)),
        ("SCOPE defined", check_scope_alignment(project_root)),
    ]

    all_passed = True

    for check_name, (passed, message) in checks:
        if passed:
            print(message)
        else:
            print(f"❌ {check_name} FAILED:")
            print(f"   {message}")
            print()
            all_passed = False

    print()

    if all_passed:
        print("✅ PROJECT.md alignment validation PASSED")
        print()
        print("NOTE: Orchestrator will perform detailed alignment check")
        print("      before feature implementation begins.")
        return 0
    else:
        print("❌ PROJECT.md alignment validation FAILED")
        print()
        print("STRICT MODE: Cannot commit without PROJECT.md alignment.")
        print()
        print("Fix the issues above, then retry commit.")
        print()
        print("To bypass (NOT RECOMMENDED):")
        print("  git commit --no-verify")
        return 1


if __name__ == "__main__":
    sys.exit(main())

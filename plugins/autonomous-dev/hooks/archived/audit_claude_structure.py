#!/usr/bin/env python3
"""
CLAUDE.md Structure Auditor - Validate CLAUDE.md against best practices spec.

This script validates CLAUDE.md structure to ensure it stays lean and has required content.
Used by the /audit-claude command (Issue #245).

Validation Checks:
1. Required items (7 checks) - pointers, command references, workflow notes
2. Forbidden content (5 checks) - architecture sections, long code blocks, etc.
3. Size limits (2 checks) - total lines, section lengths

Exit Codes:
- 0: PASS (all checks passed)
- 1: FAIL (required missing, forbidden present, or size exceeded)

Usage:
    python audit_claude_structure.py [path_to_claude_md]

    # Default: checks ./CLAUDE.md
    python audit_claude_structure.py

    # Explicit path
    python audit_claude_structure.py /path/to/CLAUDE.md

Date: 2026-01-19
Issue: #245 (Command: /audit-claude to validate CLAUDE.md structure)
Agent: implementer
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# =============================================================================
# Configuration
# =============================================================================

# Size limits
MAX_TOTAL_LINES = 100
WARNING_LINE_THRESHOLD = 90
MAX_SECTION_LINES = 20
MAX_CODE_BLOCK_LINES = 5

# Required items (patterns to search for)
REQUIRED_ITEMS = {
    "project_name": {
        "description": "Project name/purpose",
        "pattern": r"^#\s+\S+",  # First heading
        "location": "first 10 lines"
    },
    "operations_pointer": {
        "description": "Pointer to .claude/local/OPERATIONS.md",
        "pattern": r"\.claude/local/OPERATIONS\.md",
        "location": "anywhere"
    },
    "project_pointer": {
        "description": "Pointer to .claude/PROJECT.md",
        "pattern": r"\.claude/PROJECT\.md",
        "location": "anywhere"
    },
    "implement_reference": {
        "description": "/implement command reference",
        "pattern": r"/implement",
        "location": "anywhere"
    },
    "sync_reference": {
        "description": "/sync command reference",
        "pattern": r"/sync",
        "location": "anywhere"
    },
    "clear_reference": {
        "description": "/clear context reminder",
        "pattern": r"/clear",
        "location": "anywhere"
    },
    "workflow_discipline": {
        "description": "Workflow discipline note",
        "pattern": r"(?:Use|use)\s+[`/]*implement",
        "location": "anywhere"
    }
}

# Forbidden patterns
FORBIDDEN_PATTERNS = {
    "architecture_section": {
        "description": "Architecture details",
        "pattern": r"^##\s+Architecture",
        "action": "move to docs/ARCHITECTURE.md"
    },
    "workflow_guide": {
        "description": "Workflow step-by-step guides",
        "pattern": r"^##\s+(?:Step-by-Step|Workflow\s+Guide|How\s+to)",
        "action": "move to docs/WORKFLOW.md"
    },
    "troubleshooting": {
        "description": "Troubleshooting sections",
        "pattern": r"^##\s+(?:Troubleshooting|Common\s+Issues|FAQ)",
        "action": "move to docs/TROUBLESHOOTING.md"
    }
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AuditIssue:
    """Represents a single audit issue."""
    category: str  # "required", "forbidden", "size"
    item: str
    description: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    severity: str = "error"  # "error", "warning"
    action: Optional[str] = None


@dataclass
class AuditResult:
    """Complete audit result."""
    passed: bool
    issues: List[AuditIssue]
    total_lines: int
    sections_over_limit: int
    required_found: List[str]
    required_missing: List[str]


# =============================================================================
# Validation Functions
# =============================================================================

def check_required_items(content: str, lines: List[str]) -> List[AuditIssue]:
    """Check for required items in CLAUDE.md."""
    issues = []

    for item_key, item_spec in REQUIRED_ITEMS.items():
        pattern = item_spec["pattern"]
        location = item_spec["location"]

        # Determine search scope
        if location == "first 10 lines":
            search_content = "\n".join(lines[:10])
        else:
            search_content = content

        # Search for pattern
        match = re.search(pattern, search_content, re.MULTILINE | re.IGNORECASE)

        if not match:
            issues.append(AuditIssue(
                category="required",
                item=item_key,
                description=f"{item_spec['description']}",
                severity="error",
                action=f"Add {item_spec['description'].lower()}"
            ))

    return issues


def check_forbidden_content(content: str, lines: List[str]) -> List[AuditIssue]:
    """Check for forbidden content in CLAUDE.md."""
    issues = []

    # Check forbidden section patterns
    for item_key, item_spec in FORBIDDEN_PATTERNS.items():
        pattern = item_spec["pattern"]

        for i, line in enumerate(lines, start=1):
            if re.match(pattern, line, re.IGNORECASE):
                # Find section end (next ## heading or EOF)
                section_end = len(lines)
                for j in range(i, len(lines)):
                    if j > i and re.match(r"^##\s+", lines[j - 1]):
                        section_end = j
                        break

                issues.append(AuditIssue(
                    category="forbidden",
                    item=item_key,
                    description=item_spec["description"],
                    line_start=i,
                    line_end=section_end,
                    severity="error",
                    action=item_spec["action"]
                ))

    # Check for long code blocks (> 5 lines)
    in_code_block = False
    code_block_start = 0
    code_block_lines = 0

    for i, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_block_start = i
                code_block_lines = 0
            else:
                # End of code block
                if code_block_lines > MAX_CODE_BLOCK_LINES:
                    issues.append(AuditIssue(
                        category="forbidden",
                        item="long_code_block",
                        description=f"Code block > {MAX_CODE_BLOCK_LINES} lines ({code_block_lines} lines)",
                        line_start=code_block_start,
                        line_end=i,
                        severity="error",
                        action="shorten or move to docs/"
                    ))
                in_code_block = False
        elif in_code_block:
            code_block_lines += 1

    # Check for long sections (> 20 lines)
    current_section_start = 0
    current_section_name = "Header"
    current_section_lines = 0

    for i, line in enumerate(lines, start=1):
        if re.match(r"^##\s+", line):
            # Check previous section
            if current_section_lines > MAX_SECTION_LINES:
                issues.append(AuditIssue(
                    category="forbidden",
                    item="long_section",
                    description=f"Section > {MAX_SECTION_LINES} lines ({current_section_lines} lines)",
                    line_start=current_section_start,
                    line_end=i - 1,
                    severity="error",
                    action="split or move details to docs/"
                ))

            # Start new section
            current_section_start = i
            current_section_name = line.strip()
            current_section_lines = 0
        else:
            current_section_lines += 1

    # Check last section
    if current_section_lines > MAX_SECTION_LINES:
        issues.append(AuditIssue(
            category="forbidden",
            item="long_section",
            description=f"Section > {MAX_SECTION_LINES} lines ({current_section_lines} lines)",
            line_start=current_section_start,
            line_end=len(lines),
            severity="error",
            action="split or move details to docs/"
        ))

    return issues


def check_size_limits(lines: List[str]) -> List[AuditIssue]:
    """Check file size limits."""
    issues = []
    total_lines = len(lines)

    if total_lines > MAX_TOTAL_LINES:
        issues.append(AuditIssue(
            category="size",
            item="total_lines",
            description=f"Total lines ({total_lines}) exceeds limit ({MAX_TOTAL_LINES})",
            severity="error",
            action=f"reduce from {total_lines} to <{MAX_TOTAL_LINES} lines"
        ))
    elif total_lines > WARNING_LINE_THRESHOLD:
        issues.append(AuditIssue(
            category="size",
            item="total_lines",
            description=f"Total lines ({total_lines}) approaching limit ({MAX_TOTAL_LINES})",
            severity="warning"
        ))

    return issues


def count_sections_over_limit(lines: List[str]) -> int:
    """Count sections exceeding line limit."""
    count = 0
    current_section_lines = 0

    for line in lines:
        if re.match(r"^##\s+", line):
            if current_section_lines > MAX_SECTION_LINES:
                count += 1
            current_section_lines = 0
        else:
            current_section_lines += 1

    # Check last section
    if current_section_lines > MAX_SECTION_LINES:
        count += 1

    return count


# =============================================================================
# Main Audit Function
# =============================================================================

def audit_claude_md(content: str) -> AuditResult:
    """
    Run complete audit on CLAUDE.md content.

    Args:
        content: Full content of CLAUDE.md file

    Returns:
        AuditResult with all findings
    """
    lines = content.split("\n")

    # Run all checks
    required_issues = check_required_items(content, lines)
    forbidden_issues = check_forbidden_content(content, lines)
    size_issues = check_size_limits(lines)

    # Collect all issues
    all_issues = required_issues + forbidden_issues + size_issues

    # Calculate stats
    total_lines = len(lines)
    sections_over_limit = count_sections_over_limit(lines)

    # Determine required items status
    required_missing = [i.item for i in required_issues if i.category == "required"]
    required_found = [k for k in REQUIRED_ITEMS.keys() if k not in required_missing]

    # Determine pass/fail
    errors = [i for i in all_issues if i.severity == "error"]
    passed = len(errors) == 0

    return AuditResult(
        passed=passed,
        issues=all_issues,
        total_lines=total_lines,
        sections_over_limit=sections_over_limit,
        required_found=required_found,
        required_missing=required_missing
    )


# =============================================================================
# Report Generation
# =============================================================================

def generate_report(result: AuditResult) -> str:
    """
    Generate human-readable audit report.

    Args:
        result: AuditResult from audit_claude_md()

    Returns:
        Formatted report string
    """
    lines = []

    # Header
    lines.append("CLAUDE.md Audit Report")
    lines.append("======================")
    lines.append(f"Status: {'PASS' if result.passed else 'FAIL'}")
    lines.append("")

    # Required Items
    lines.append("Required Items:")
    for item_key, item_spec in REQUIRED_ITEMS.items():
        if item_key in result.required_found:
            lines.append(f"  [x] {item_spec['description']}")
        else:
            lines.append(f"  [ ] {item_spec['description']}  <-- MISSING")
    lines.append("")

    # Forbidden Content
    forbidden_issues = [i for i in result.issues if i.category == "forbidden"]
    if forbidden_issues:
        lines.append("Forbidden Content:")
        for issue in forbidden_issues:
            if issue.line_start and issue.line_end:
                lines.append(f"  Line {issue.line_start}-{issue.line_end}: {issue.description} ({issue.action})")
            elif issue.line_start:
                lines.append(f"  Line {issue.line_start}: {issue.description} ({issue.action})")
            else:
                lines.append(f"  {issue.description} ({issue.action})")
        lines.append("")
    else:
        lines.append("Forbidden Content: None detected")
        lines.append("")

    # Stats
    lines.append("Stats:")
    lines.append(f"  Total lines: {result.total_lines} (limit: {MAX_TOTAL_LINES})")
    lines.append(f"  Sections over {MAX_SECTION_LINES} lines: {result.sections_over_limit}")
    lines.append("")

    # Suggested Actions
    errors = [i for i in result.issues if i.severity == "error" and i.action]
    if errors:
        lines.append("Suggested Actions:")
        for idx, issue in enumerate(errors, start=1):
            lines.append(f"  {idx}. {issue.action}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for audit_claude_structure.py."""
    # Determine CLAUDE.md path
    if len(sys.argv) > 1:
        claude_md_path = Path(sys.argv[1])
    else:
        claude_md_path = Path("CLAUDE.md")

    # Check file exists
    if not claude_md_path.exists():
        print(f"Error: CLAUDE.md not found at {claude_md_path}")
        sys.exit(1)

    # Read content
    content = claude_md_path.read_text()

    # Run audit
    result = audit_claude_md(content)

    # Generate and print report
    report = generate_report(result)
    print(report)

    # Exit with appropriate code
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()

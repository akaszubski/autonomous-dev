#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Validate CLAUDE.md alignment with codebase.

Detects drift between documented standards (CLAUDE.md) and actual
implementation (PROJECT.md, agents, commands, hooks).

This script is used by:
1. Pre-commit hook (auto-validation)
2. Manual runs (debugging drift issues)
3. CI/CD pipeline (quality gates)

Exit codes:
- 0: Fully aligned, no issues
- 1: Drift detected, warnings shown (documentation fixes needed)
- 2: Critical misalignment (blocks commit in strict mode)
"""

import re
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


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


# CLAUDE.md Size Limits (Issue #197)
MAX_LINES = 300
WARNING_THRESHOLD_LINES = 280  # 93% of limit - warn at exactly 280
MAX_SECTIONS = 20
WARNING_THRESHOLD_SECTIONS = 18  # 90% of limit - warn at exactly 18
PHASE_1_CHAR_LIMIT = 35000
PHASE_2_CHAR_LIMIT = 25000
PHASE_3_CHAR_LIMIT = 15000


def get_validation_phase() -> int:
    """Get validation phase from CLAUDE_VALIDATION_PHASE env var (default: 1)."""
    phase_str = os.environ.get('CLAUDE_VALIDATION_PHASE', '1')
    try:
        phase = int(phase_str)
        if phase in (1, 2, 3):
            return phase
    except ValueError:
        pass
    return 1  # Default to phase 1


@dataclass
class AlignmentIssue:
    """Represents a single alignment issue."""
    severity: str  # "error", "warning", "info"
    category: str  # "version", "count", "feature", "best-practice"
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    location: Optional[str] = None


class ClaudeAlignmentValidator:
    """Validates CLAUDE.md alignment with codebase."""

    def __init__(self, repo_root: Path = Path.cwd()):
        """Initialize validator with repo root."""
        self.repo_root = repo_root
        self.issues: List[AlignmentIssue] = []

    def validate(self) -> Tuple[bool, List[AlignmentIssue]]:
        """Run all validation checks."""
        # Read files (global CLAUDE.md is optional - may not exist in dev environments)
        global_claude = self._read_file(Path.home() / ".claude" / "CLAUDE.md", optional=True)
        project_claude = self._read_file(self.repo_root / "CLAUDE.md")
        project_md = self._read_file(self.repo_root / ".claude" / "PROJECT.md")

        # Run checks
        self._check_version_consistency(global_claude, project_claude, project_md)
        self._check_agent_counts(project_claude)
        self._check_command_counts(project_claude)
        self._check_skills_documented(project_claude)
        self._check_hook_counts(project_claude)
        self._check_documented_features_exist(project_claude)

        # Run size limit checks (Issue #197)
        self._check_line_count(project_claude)
        self._check_section_count(project_claude)
        self._check_character_count(project_claude)

        # Determine overall status
        has_errors = any(i.severity == "error" for i in self.issues)
        has_warnings = any(i.severity == "warning" for i in self.issues)

        return not has_errors, self.issues

    def _read_file(self, path: Path, optional: bool = False) -> str:
        """Read file safely.

        Args:
            path: File path to read
            optional: If True, don't warn if file is missing (e.g., global CLAUDE.md)
        """
        if not path.exists():
            if not optional:
                self.issues.append(AlignmentIssue(
                    severity="warning",
                    category="version",
                    message=f"File not found: {path}",
                    location=str(path)
                ))
            return ""
        return path.read_text()

    def _check_version_consistency(self, global_claude: str, project_claude: str, project_md: str):
        """Check version consistency across files."""
        # Extract versions
        global_version = self._extract_version(global_claude)
        project_version = self._extract_version(project_claude)
        project_md_version = self._extract_version(project_md)

        # PROJECT.md should match PROJECT.md version
        if project_claude and project_md:
            if "Last Updated" in project_claude and "Last Updated" in project_md:
                project_claude_date = self._extract_date(project_claude)
                project_md_date = self._extract_date(project_md)

                # Project CLAUDE.md should be same or newer than PROJECT.md
                if project_claude_date and project_md_date:
                    if project_claude_date < project_md_date:
                        self.issues.append(AlignmentIssue(
                            severity="warning",
                            category="version",
                            message="Project CLAUDE.md is older than PROJECT.md (should be synced)",
                            expected=f"{project_md_date}+",
                            actual=project_claude_date,
                            location="CLAUDE.md:3, .claude/PROJECT.md:3"
                        ))

    def _check_agent_counts(self, project_claude: str):
        """Check that documented agent counts match reality."""
        actual_count = len(list((self.repo_root / "plugins/autonomous-dev/agents").glob("*.md")))

        # Extract documented count from text
        documented_count = self._extract_agent_count(project_claude)

        if documented_count and documented_count != actual_count:
            self.issues.append(AlignmentIssue(
                severity="warning",
                category="count",
                message=f"Agent count mismatch: CLAUDE.md says {documented_count}, but {actual_count} exist",
                expected=str(actual_count),
                actual=str(documented_count),
                location="plugins/autonomous-dev/agents/"
            ))

    def _check_command_counts(self, project_claude: str):
        """Check that documented command counts match reality."""
        actual_count = len(list((self.repo_root / "plugins/autonomous-dev/commands").glob("*.md")))

        # Extract documented count (look for "8 total" or similar)
        documented_count = self._extract_command_count(project_claude)

        if documented_count and documented_count != actual_count:
            self.issues.append(AlignmentIssue(
                severity="warning",
                category="count",
                message=f"Command count mismatch: CLAUDE.md says {documented_count}, but {actual_count} exist",
                expected=str(actual_count),
                actual=str(documented_count),
                location="plugins/autonomous-dev/commands/"
            ))

    def _check_skills_documented(self, project_claude: str):
        """Check skills are documented correctly."""
        # Skills should be 0 (removed) per v2.5+ guidance
        if "### Skills" in project_claude:
            # Check if it correctly says "0 - Removed"
            if not "Skills (0 - Removed)" in project_claude:
                # Only warn if it documents skills as still active
                if "Located: `plugins/autonomous-dev/skills/`" in project_claude:
                    self.issues.append(AlignmentIssue(
                        severity="warning",
                        category="feature",
                        message="CLAUDE.md documents skills as active (should say '0 - Removed' per v2.5+ guidance)",
                        expected="0 - Removed per Anthropic anti-pattern guidance",
                        actual="Documented as having active skills directory",
                        location="CLAUDE.md: Architecture > Skills"
                    ))

    def _check_hook_counts(self, project_claude: str):
        """Check hook counts are documented."""
        hooks_dir = self.repo_root / "plugins/autonomous-dev/hooks"
        documented_count = self._extract_hook_count(project_claude)

        # Issue #144: Support unified hooks architecture
        # If CLAUDE.md mentions "unified hooks", count unified_*.py files
        if "unified" in project_claude.lower() and "hooks" in project_claude.lower():
            unified_count = len(list(hooks_dir.glob("unified_*.py")))
            if documented_count and documented_count != unified_count:
                self.issues.append(AlignmentIssue(
                    severity="info",
                    category="count",
                    message=f"Unified hook count changed: CLAUDE.md says {documented_count}, actual is {unified_count}",
                    expected=str(unified_count),
                    actual=str(documented_count),
                    location="plugins/autonomous-dev/hooks/unified_*.py"
                ))
        else:
            # Legacy: count all *.py files
            actual_count = len(list(hooks_dir.glob("*.py")))
            if documented_count and documented_count != actual_count:
                self.issues.append(AlignmentIssue(
                    severity="info",
                    category="count",
                    message=f"Hook count changed: CLAUDE.md says ~{documented_count}, actual is {actual_count}",
                    expected=str(actual_count),
                    actual=str(documented_count),
                    location="plugins/autonomous-dev/hooks/"
                ))

    def _check_documented_features_exist(self, project_claude: str):
        """Check that documented features actually exist."""
        # Check key commands mentioned
        # 7 active commands per Issue #121
        commands_mentioned = [
            "/auto-implement",
            "/batch-implement",
            "/create-issue",
            "/align",
            "/setup",
            "/health-check",
            "/sync",
        ]

        for cmd in commands_mentioned:
            cmd_file = self.repo_root / "plugins/autonomous-dev/commands" / f"{cmd[1:]}.md"
            if not cmd_file.exists():
                self.issues.append(AlignmentIssue(
                    severity="error",
                    category="feature",
                    message=f"Documented command {cmd} doesn't exist",
                    expected=f"Command file: {cmd_file.name}",
                    actual="Not found",
                    location=str(cmd_file)
                ))

    def _check_line_count(self, content: str):
        """Check CLAUDE.md line count against 300-line limit (Issue #197)."""
        if not content:
            return

        lines = content.splitlines()
        line_count = len(lines)

        # Error at 301+ lines (takes precedence)
        if line_count > MAX_LINES:
            self.issues.append(AlignmentIssue(
                severity="error",
                category="best-practice",
                message=f"CLAUDE.md exceeds line limit: {line_count} lines (max: {MAX_LINES}). "
                        f"See docs/CLAUDE-MD-BEST-PRACTICES.md for compression strategies.",
                expected=f"<= {MAX_LINES} lines",
                actual=f"{line_count} lines",
                location="CLAUDE.md"
            ))
        # Warning at exactly 280 lines (not above or below)
        elif line_count == WARNING_THRESHOLD_LINES:
            self.issues.append(AlignmentIssue(
                severity="warning",
                category="best-practice",
                message=f"CLAUDE.md approaching line limit: {line_count} lines (limit: {MAX_LINES}). "
                        f"See docs/CLAUDE-MD-BEST-PRACTICES.md for compression strategies.",
                expected=f"< {WARNING_THRESHOLD_LINES} lines",
                actual=f"{line_count} lines",
                location="CLAUDE.md"
            ))

    def _check_section_count(self, content: str):
        """Check CLAUDE.md section count against 20-section limit (Issue #197)."""
        if not content:
            return

        sections = re.findall(r'^## ', content, re.MULTILINE)
        section_count = len(sections)

        # Error at 21+ sections (takes precedence)
        if section_count > MAX_SECTIONS:
            self.issues.append(AlignmentIssue(
                severity="error",
                category="best-practice",
                message=f"CLAUDE.md exceeds section limit: {section_count} sections (max: {MAX_SECTIONS}). "
                        f"See docs/CLAUDE-MD-BEST-PRACTICES.md for consolidation strategies.",
                expected=f"<= {MAX_SECTIONS} sections",
                actual=f"{section_count} sections",
                location="CLAUDE.md"
            ))
        # Warning at exactly 18 sections (threshold value)
        elif section_count == WARNING_THRESHOLD_SECTIONS:
            self.issues.append(AlignmentIssue(
                severity="warning",
                category="best-practice",
                message=f"CLAUDE.md approaching section limit: {section_count} sections (limit: {MAX_SECTIONS}). "
                        f"See docs/CLAUDE-MD-BEST-PRACTICES.md for consolidation strategies.",
                expected=f"< {WARNING_THRESHOLD_SECTIONS} sections",
                actual=f"{section_count} sections",
                location="CLAUDE.md"
            ))

    def _check_character_count(self, content: str):
        """Check CLAUDE.md character count against phased limits (Issue #197)."""
        if not content:
            return

        char_count = len(content)
        phase = get_validation_phase()

        # Phase 1: 35k character warning (current state)
        if phase == 1:
            if char_count > PHASE_1_CHAR_LIMIT:
                self.issues.append(AlignmentIssue(
                    severity="warning",
                    category="best-practice",
                    message=f"CLAUDE.md exceeds phase 1 character limit: {char_count:,} characters "
                            f"(limit: {PHASE_1_CHAR_LIMIT:,}). "
                            f"See docs/CLAUDE-MD-BEST-PRACTICES.md for compression strategies.",
                    expected=f"<= {PHASE_1_CHAR_LIMIT:,} characters",
                    actual=f"{char_count:,} characters",
                    location="CLAUDE.md"
                ))

        # Phase 2: 25k character error (future)
        elif phase == 2:
            if char_count > PHASE_2_CHAR_LIMIT:
                self.issues.append(AlignmentIssue(
                    severity="error",
                    category="best-practice",
                    message=f"CLAUDE.md exceeds phase 2 character limit: {char_count:,} characters "
                            f"(max: {PHASE_2_CHAR_LIMIT:,}). "
                            f"See docs/CLAUDE-MD-BEST-PRACTICES.md for compression strategies.",
                    expected=f"<= {PHASE_2_CHAR_LIMIT:,} characters",
                    actual=f"{char_count:,} characters",
                    location="CLAUDE.md"
                ))

        # Phase 3: 15k character error (final goal)
        elif phase == 3:
            if char_count > PHASE_3_CHAR_LIMIT:
                self.issues.append(AlignmentIssue(
                    severity="error",
                    category="best-practice",
                    message=f"CLAUDE.md exceeds phase 3 character limit: {char_count:,} characters "
                            f"(max: {PHASE_3_CHAR_LIMIT:,}). "
                            f"See docs/CLAUDE-MD-BEST-PRACTICES.md for compression strategies.",
                    expected=f"<= {PHASE_3_CHAR_LIMIT:,} characters",
                    actual=f"{char_count:,} characters",
                    location="CLAUDE.md"
                ))

    # Helper methods
    def _extract_version(self, text: str) -> Optional[str]:
        """Extract version from text."""
        match = re.search(r"Version['\"]?\s*:\s*([v\d.]+)", text, re.IGNORECASE)
        return match.group(1) if match else None

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from text."""
        match = re.search(r"Last Updated['\"]?\s*:\s*(\d{4}-\d{2}-\d{2})", text)
        return match.group(1) if match else None

    def _extract_agent_count(self, text: str) -> Optional[int]:
        """Extract agent count from text."""
        # Look for "### Agents (16 specialists)" or similar
        match = re.search(r"### Agents \((\d+)", text)
        return int(match.group(1)) if match else None

    def _extract_command_count(self, text: str) -> Optional[int]:
        """Extract command count from text."""
        # Look for "8 total" or "8 commands"
        match = re.search(r"(\d+)\s+(?:total\s+)?commands", text, re.IGNORECASE)
        if not match:
            match = re.search(r"### Commands.*?^- (?=.*?){(\d+)", text, re.MULTILINE)
        return int(match.group(1)) if match else None

    def _extract_hook_count(self, text: str) -> Optional[int]:
        """Extract hook count from text."""
        # Look for "10 unified hooks" (Issue #144) or "15+ automation" or similar
        # Match: "10 unified hooks", "51 hooks", "15+ automation"
        match = re.search(r"(\d+)\+?\s+(?:unified\s+)?(?:automation|hooks)", text, re.IGNORECASE)
        return int(match.group(1)) if match else None


def print_report(validator: ClaudeAlignmentValidator, issues: List[AlignmentIssue]):
    """Print alignment report."""
    if not issues:
        print("✅ CLAUDE.md Alignment: No issues found")
        return

    # Group by severity
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos = [i for i in issues if i.severity == "info"]

    print("\n" + "=" * 70)
    print("CLAUDE.md Alignment Report")
    print("=" * 70)

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for issue in errors:
            print(f"\n  {issue.message}")
            if issue.expected:
                print(f"    Expected: {issue.expected}")
            if issue.actual:
                print(f"    Actual:   {issue.actual}")
            if issue.location:
                print(f"    Location: {issue.location}")

    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for issue in warnings:
            print(f"\n  {issue.message}")
            if issue.expected:
                print(f"    Expected: {issue.expected}")
            if issue.actual:
                print(f"    Actual:   {issue.actual}")
            if issue.location:
                print(f"    Location: {issue.location}")

    if infos:
        print(f"\nℹ️  INFO ({len(infos)}):")
        for issue in infos:
            print(f"\n  {issue.message}")

    print("\n" + "=" * 70)
    print("Fix:")
    print("  1. Update CLAUDE.md with actual values")
    print("  2. Commit: git add CLAUDE.md && git commit -m 'docs: update CLAUDE.md alignment'")
    print("=" * 70 + "\n")


def main():
    """Run validation."""
    validator = ClaudeAlignmentValidator(Path.cwd())
    aligned, issues = validator.validate()

    print_report(validator, issues)

    # Exit codes
    if not issues:
        sys.exit(0)  # All aligned

    errors = [i for i in issues if i.severity == "error"]
    if errors:
        sys.exit(2)  # Critical misalignment (blocks in strict mode)
    else:
        sys.exit(1)  # Warnings only (documentation fixes needed)


if __name__ == "__main__":
    main()

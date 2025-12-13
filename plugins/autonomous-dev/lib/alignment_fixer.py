#!/usr/bin/env python3
"""
Alignment Fixer - Safe documentation alignment tool.

SAFETY FIRST: Shows drift, asks before fixing. Never auto-fixes.

Workflow:
1. Collect repository state (source of truth from file system)
2. Identify ACTIVE documentation (safe to update)
3. Detect drift in active docs only
4. Show all issues for review
5. Ask user before fixing each file
6. Create backup before any changes

Frozen (never modified):
- CHANGELOG.md - Historical record
- docs/sessions/ - Session logs
- Archive directories
- Files with historical context

Usage:
    python alignment_fixer.py              # Scan and show drift
    python alignment_fixer.py --interactive   # Fix with prompts per file

Exit codes:
    0 - Aligned (or fixes applied successfully)
    1 - Drift detected (review needed)
    2 - Error
"""

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class DriftIssue:
    """A single drift issue."""
    file: Path
    line_num: int
    category: str
    description: str
    current_value: str
    expected_value: str
    line_content: str
    fixable: bool = True


@dataclass
class RepoState:
    """Current repository state - source of truth."""
    agents: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    libraries: List[str] = field(default_factory=list)

    @property
    def agent_count(self) -> int:
        return len(self.agents)

    @property
    def command_count(self) -> int:
        return len(self.commands)

    @property
    def hook_count(self) -> int:
        return len(self.hooks)

    @property
    def skill_count(self) -> int:
        return len(self.skills)

    @property
    def library_count(self) -> int:
        return len(self.libraries)


class AlignmentFixer:
    """Safe documentation alignment with show-and-ask workflow."""

    # Files that are ACTIVE (safe to update counts in)
    ACTIVE_DOCS = [
        "CLAUDE.md",
        "README.md",
        "plugins/autonomous-dev/README.md",
        "plugins/autonomous-dev/commands/*.md",
        "plugins/autonomous-dev/agents/*.md",
        "plugins/autonomous-dev/docs/COMMANDS.md",
        "plugins/autonomous-dev/docs/AGENTS.md",
        "plugins/autonomous-dev/docs/HOOKS.md",
        ".claude/commands/*.md",
        ".claude/docs/*.md",
    ]

    # Files that are FROZEN (never modify)
    FROZEN_PATTERNS = [
        "CHANGELOG",
        "archive/",
        "sessions/",
        ".backup",
        "research/",
        "design/",
        "tests/",
    ]

    # Commands that have been removed/archived
    REMOVED_COMMANDS = {
        "/status", "/test", "/pipeline-status",
        "/align-project", "/align-claude", "/align-project-retrofit",
        "/sync-dev", "/update-plugin", "/uninstall",
        "/research", "/plan", "/test-feature", "/implement",
        "/review", "/security-scan", "/update-docs",
        "/format", "/full-check", "/commit",
    }

    def __init__(self, repo_root: Path = None):
        self.repo_root = repo_root or Path.cwd()
        self.plugin_dir = self.repo_root / "plugins" / "autonomous-dev"
        self.state: Optional[RepoState] = None
        self.issues: List[DriftIssue] = []
        self.backup_dir: Optional[Path] = None

    # =========================================================================
    # STATE COLLECTION
    # =========================================================================

    def collect_state(self) -> RepoState:
        """Collect current repository state from file system."""
        state = RepoState()

        # Agents
        agents_dir = self.plugin_dir / "agents"
        if agents_dir.exists():
            state.agents = sorted([f.stem for f in agents_dir.glob("*.md")])

        # Commands (excluding archive)
        commands_dir = self.plugin_dir / "commands"
        if commands_dir.exists():
            state.commands = sorted([
                f.stem for f in commands_dir.glob("*.md")
                if "archive" not in str(f)
            ])

        # Hooks
        hooks_dir = self.plugin_dir / "hooks"
        if hooks_dir.exists():
            state.hooks = sorted([f.stem for f in hooks_dir.glob("*.py")])

        # Skills
        skills_dir = self.plugin_dir / "skills"
        if skills_dir.exists():
            state.skills = sorted([
                d.name for d in skills_dir.iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()
            ])

        # Libraries
        lib_dir = self.plugin_dir / "lib"
        if lib_dir.exists():
            state.libraries = sorted([
                f.stem for f in lib_dir.glob("*.py")
                if not f.name.startswith("__")
            ])

        self.state = state
        return state

    # =========================================================================
    # FILE DISCOVERY
    # =========================================================================

    def is_frozen(self, path: Path) -> bool:
        """Check if file is frozen (historical, shouldn't be modified)."""
        path_str = str(path)
        return any(pattern in path_str for pattern in self.FROZEN_PATTERNS)

    def find_active_docs(self) -> List[Path]:
        """Find active documentation files (safe to update)."""
        files = []

        # Root level files
        for name in ["CLAUDE.md", "README.md"]:
            f = self.repo_root / name
            if f.exists():
                files.append(f)

        # Plugin docs
        patterns = [
            self.plugin_dir / "README.md",
            self.plugin_dir / "commands" / "*.md",
            self.plugin_dir / "docs" / "COMMANDS.md",
            self.plugin_dir / "docs" / "AGENTS.md",
        ]

        for pattern in patterns:
            if "*" in str(pattern):
                parent = pattern.parent
                glob_pattern = pattern.name
                if parent.exists():
                    for f in parent.glob(glob_pattern):
                        if not self.is_frozen(f):
                            files.append(f)
            elif pattern.exists():
                files.append(pattern)

        # .claude directory
        claude_dir = self.repo_root / ".claude"
        if claude_dir.exists():
            for md in claude_dir.rglob("*.md"):
                if not self.is_frozen(md):
                    files.append(md)

        return list(set(files))

    # =========================================================================
    # DRIFT DETECTION
    # =========================================================================

    def detect_count_drift(self, file: Path) -> List[DriftIssue]:
        """Detect count mismatches in a single file."""
        issues = []

        try:
            content = file.read_text()
            lines = content.split("\n")
        except Exception:
            return issues

        # Only check specific patterns that are clearly "current state" declarations
        count_checks = [
            # Pattern, component, description
            (r"\*\*Commands \((\d+) active\)\*\*", "commands", "Commands count in header"),
            (r"Commands:\s*(\d+)/\d+", "commands", "Commands X/Y count"),
            (r"Agents:\s*(\d+)/\d+", "agents", "Agents X/Y count"),
            (r"Hooks:\s*(\d+)/\d+", "hooks", "Hooks X/Y count"),
            (r"(\d+) AI agents", "agents", "AI agents count"),
            (r"(\d+) slash commands", "commands", "Slash commands count"),
            (r"(\d+) active commands", "commands", "Active commands count"),
            (r"(\d+) specialist agents", "agents", "Specialist agents count"),
            (r"(\d+) automation hooks", "hooks", "Automation hooks count"),
            (r"(\d+) active skill", "skills", "Active skills count"),
        ]

        expected = {
            "agents": self.state.agent_count,
            "commands": self.state.command_count,
            "hooks": self.state.hook_count,
            "skills": self.state.skill_count,
        }

        in_code_block = False
        for line_num, line in enumerate(lines, 1):
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # Skip lines that look historical
            line_lower = line.lower()
            if any(word in line_lower for word in [
                "was", "were", "previously", "before", "v3.", "v2.",
                "phase", "issue #", "github #", "pr #", "from",
            ]):
                continue

            for pattern, component, desc in count_checks:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    found = int(match.group(1))
                    exp = expected.get(component, 0)

                    if found != exp and found > 0 and exp > 0:
                        issues.append(DriftIssue(
                            file=file,
                            line_num=line_num,
                            category="count",
                            description=desc,
                            current_value=str(found),
                            expected_value=str(exp),
                            line_content=line.strip()[:100],
                        ))

        return issues

    def detect_dead_refs(self, file: Path) -> List[DriftIssue]:
        """Detect references to removed commands."""
        issues = []

        try:
            content = file.read_text()
            lines = content.split("\n")
        except Exception:
            return issues

        removal_context = [
            "removed", "archived", "deprecated", "old", "replaced",
            "formerly", "was", "used to", "no longer", "moved",
        ]

        command_pattern = r"(?<![`\w])(/[a-z][-a-z0-9]*)"

        in_code_block = False
        for line_num, line in enumerate(lines, 1):
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # Skip lines documenting removals
            line_lower = line.lower()
            if any(ctx in line_lower for ctx in removal_context):
                continue

            for match in re.finditer(command_pattern, line):
                cmd = match.group(1)
                if cmd in self.REMOVED_COMMANDS:
                    issues.append(DriftIssue(
                        file=file,
                        line_num=line_num,
                        category="reference",
                        description=f"Reference to removed command {cmd}",
                        current_value=cmd,
                        expected_value="(command removed)",
                        line_content=line.strip()[:100],
                        fixable=False,
                    ))

        return issues

    def detect_all_drift(self) -> List[DriftIssue]:
        """Detect all drift in active documentation."""
        self.issues = []

        if not self.state:
            self.collect_state()

        active_docs = self.find_active_docs()

        for doc in active_docs:
            self.issues.extend(self.detect_count_drift(doc))
            self.issues.extend(self.detect_dead_refs(doc))

        return self.issues

    # =========================================================================
    # FIXING (with user approval)
    # =========================================================================

    def create_backup(self, files: List[Path]) -> Path:
        """Create backup of files before modification."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.repo_root / ".alignment_backup" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            rel_path = file.relative_to(self.repo_root)
            backup_path = backup_dir / rel_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, backup_path)

        self.backup_dir = backup_dir
        return backup_dir

    def fix_line(self, line: str, issue: DriftIssue) -> str:
        """Fix a single line based on the issue."""
        if issue.category == "count":
            # Replace the old number with the new one
            return line.replace(issue.current_value, issue.expected_value, 1)
        return line

    def fix_file_interactive(self, file: Path, issues: List[DriftIssue]) -> bool:
        """Fix issues in a file with user approval."""
        print(f"\n📄 {file.relative_to(self.repo_root)}")
        print("-" * 60)

        for issue in issues:
            print(f"  Line {issue.line_num}: {issue.description}")
            print(f"    Current:  {issue.current_value}")
            print(f"    Expected: {issue.expected_value}")
            print(f"    Context:  {issue.line_content[:60]}...")

        if not any(i.fixable for i in issues):
            print("  ⚠️  No auto-fixable issues (manual review needed)")
            return False

        fixable = [i for i in issues if i.fixable]
        response = input(f"\n  Fix {len(fixable)} issues in this file? [y/N/q]: ").strip().lower()

        if response == "q":
            print("  Quitting...")
            sys.exit(0)

        if response != "y":
            print("  Skipped")
            return False

        # Create backup
        self.create_backup([file])

        # Apply fixes
        content = file.read_text()
        lines = content.split("\n")

        # Sort by line number descending to avoid offset issues
        for issue in sorted(fixable, key=lambda x: -x.line_num):
            idx = issue.line_num - 1
            if 0 <= idx < len(lines):
                lines[idx] = self.fix_line(lines[idx], issue)

        file.write_text("\n".join(lines))
        print(f"  ✅ Fixed {len(fixable)} issues (backup: {self.backup_dir})")
        return True

    # =========================================================================
    # REPORTING
    # =========================================================================

    def print_state(self):
        """Print current repository state."""
        print("\n" + "=" * 70)
        print("📊 REPOSITORY STATE (Source of Truth)")
        print("=" * 70)
        print(f"\n  Agents:    {self.state.agent_count:3d}  ({', '.join(self.state.commands)})")
        print(f"  Commands:  {self.state.command_count:3d}  ({', '.join(self.state.commands)})")
        print(f"  Hooks:     {self.state.hook_count:3d}")
        print(f"  Skills:    {self.state.skill_count:3d}")
        print(f"  Libraries: {self.state.library_count:3d}")

    def print_drift_report(self):
        """Print drift report."""
        print("\n" + "=" * 70)
        print("🔍 DRIFT REPORT")
        print("=" * 70)

        if not self.issues:
            print("\n  ✅ No drift detected - documentation is aligned!")
            return

        # Group by file
        by_file: Dict[Path, List[DriftIssue]] = {}
        for issue in self.issues:
            if issue.file not in by_file:
                by_file[issue.file] = []
            by_file[issue.file].append(issue)

        fixable_count = sum(1 for i in self.issues if i.fixable)
        manual_count = sum(1 for i in self.issues if not i.fixable)

        print(f"\n  Found {len(self.issues)} issues in {len(by_file)} files")
        print(f"    - {fixable_count} auto-fixable (count updates)")
        print(f"    - {manual_count} need manual review (dead refs)")

        for file, issues in sorted(by_file.items(), key=lambda x: str(x[0])):
            rel_path = file.relative_to(self.repo_root)
            print(f"\n  📄 {rel_path}")
            for issue in sorted(issues, key=lambda x: x.line_num):
                status = "✓" if issue.fixable else "⚠"
                print(f"     {status} L{issue.line_num:4d}: {issue.description}")
                print(f"              {issue.current_value} → {issue.expected_value}")

    def run_interactive(self):
        """Run interactive fix mode."""
        print("\n" + "=" * 70)
        print("🔧 INTERACTIVE FIX MODE")
        print("=" * 70)
        print("\nFor each file with issues, you'll be asked to approve fixes.")
        print("Backups are created before any changes.")

        # Group by file
        by_file: Dict[Path, List[DriftIssue]] = {}
        for issue in self.issues:
            if issue.file not in by_file:
                by_file[issue.file] = []
            by_file[issue.file].append(issue)

        fixed_files = 0
        for file, issues in sorted(by_file.items(), key=lambda x: str(x[0])):
            if self.fix_file_interactive(file, issues):
                fixed_files += 1

        print("\n" + "=" * 70)
        print(f"✅ Fixed {fixed_files} files")
        if self.backup_dir:
            print(f"📁 Backups in: {self.backup_dir}")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Safe documentation alignment tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python alignment_fixer.py              # Scan and show drift
    python alignment_fixer.py --interactive   # Fix with prompts

Safety:
    - Only scans ACTIVE documentation (not historical)
    - Shows all issues before any changes
    - Asks permission for each file
    - Creates backups before modifications
"""
    )

    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive mode - ask before fixing each file"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root"
    )

    args = parser.parse_args()

    try:
        fixer = AlignmentFixer(repo_root=args.repo_root)

        print("🔄 Collecting repository state...")
        fixer.collect_state()
        fixer.print_state()

        print("\n🔍 Scanning active documentation for drift...")
        fixer.detect_all_drift()
        fixer.print_drift_report()

        if args.interactive and fixer.issues:
            fixer.run_interactive()
        elif fixer.issues:
            print("\n💡 Run with --interactive to fix issues")

        sys.exit(0 if not fixer.issues else 1)

    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()

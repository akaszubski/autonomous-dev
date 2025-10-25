#!/usr/bin/env python3
"""
Version Consistency Validator and Sync

Ensures all version references across the codebase match the VERSION file.

Features:
- Detects version references in all markdown files
- Validates against VERSION file (single source of truth)
- Reports inconsistencies with file locations
- Auto-fixes version drift
- Supports dry-run mode

Usage:
    # Check for inconsistencies
    python version_sync.py --check

    # Fix all inconsistencies
    python version_sync.py --fix

    # Dry run (show what would be fixed)
    python version_sync.py --fix --dry-run

    # Verbose output
    python version_sync.py --check --verbose
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
VERSION_FILE = PROJECT_ROOT / "VERSION"
SEARCH_PATHS = [
    PROJECT_ROOT / "plugins" / "autonomous-dev",
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "CLAUDE.md",
]

# Files to exclude from version checking
EXCLUDE_PATTERNS = [
    "**/UPDATES.md",  # Changelog preserves historical versions
    "**/CHANGELOG.md",  # Keep a Changelog format
    "**/.git/**",
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/venv/**",
    "**/docs/sessions/**",  # Session logs are historical
]

# Context patterns that indicate this is NOT a plugin version reference
IGNORE_CONTEXTS = [
    r"python\s+[23]\.\d+",  # Python versions
    r"pytest.*\d+\.\d+",  # pytest versions
    r"node\s+\d+\.\d+",  # Node versions
    r"npm\s+\d+\.\d+",  # npm versions
    r"claude.*[23]\.\d+",  # Claude model versions
    r"\d+\.\d+\.\d+\.\d+",  # IP addresses
    r"192\.168",  # IP addresses
    r"gh.*\d+\.\d+",  # gh CLI versions
    r"setuptools.*\d+\.\d+",  # Package versions
    r"example",  # In examples
    r"semver",  # Semantic versioning discussions
    r"MAJOR\.MINOR\.PATCH",  # Version format discussions
]

# Specific version numbers that are never plugin versions
IGNORE_VERSIONS = {
    "0.20.0",  # setuptools
    "1.0.0",  # Generic example version
    "1.0.1",  # Generic example version
    "1.1.0",  # Generic example version
    "1.1.1",  # Generic example version
    "2.0.0",  # Often used in examples (unless it's in a version header/badge)
    "3.0.0",  # Package version example
    "3.3.0",  # anthropic package version
    "3.5.0",  # anthropic package version
    "3.11.5",  # Python version
    "5.12.0",  # npm version
    "7.4.2",  # npm version
    "23.11.0",  # pytest version
    "41.0.0",  # setuptools version
    "192.168.1",  # IP address fragment
}

# Version pattern to match
VERSION_PATTERN = re.compile(
    r"(?:version[-_\s]*)?v?(\d+\.\d+\.\d+)(?:-(?:alpha|beta|rc|experimental))?",
    re.IGNORECASE
)

# Specific patterns for different contexts
BADGE_PATTERN = re.compile(r"badge/version-(\d+\.\d+\.\d+)")
VERSION_HEADER_PATTERN = re.compile(r"\*\*Version\*\*:\s*v?(\d+\.\d+\.\d+)")
VERSION_ANNOTATION_PATTERN = re.compile(r"\((?:NEW|v)\s*-?\s*v?(\d+\.\d+\.\d+)\)")

# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class VersionReference:
    """A version reference found in a file."""
    file_path: Path
    line_number: int
    line_content: str
    version: str
    context: str  # "badge", "header", "annotation", "general"

    def __str__(self) -> str:
        rel_path = self.file_path.relative_to(PROJECT_ROOT)
        return f"{rel_path}:{self.line_number} - {self.version} ({self.context})"


@dataclass
class ValidationResult:
    """Result of version validation."""
    target_version: str
    correct_refs: List[VersionReference]
    incorrect_refs: List[VersionReference]

    def is_consistent(self) -> bool:
        """Check if all versions are consistent."""
        return len(self.incorrect_refs) == 0

    def summary(self) -> str:
        """Generate summary string."""
        total = len(self.correct_refs) + len(self.incorrect_refs)
        if self.is_consistent():
            return f"✅ All {total} version references are consistent (v{self.target_version})"
        else:
            return (
                f"⚠️  Found {len(self.incorrect_refs)} inconsistent references "
                f"out of {total} total (target: v{self.target_version})"
            )


# ============================================================================
# Core Functions
# ============================================================================

def read_target_version() -> str:
    """Read the target version from VERSION file."""
    if not VERSION_FILE.exists():
        print(f"❌ VERSION file not found at: {VERSION_FILE}")
        print("Please create VERSION file with target version (e.g., '2.1.0')")
        sys.exit(1)

    version = VERSION_FILE.read_text().strip().split('\n')[0].strip()

    # Remove 'v' prefix if present
    if version.startswith('v'):
        version = version[1:]

    # Validate format
    if not re.match(r'^\d+\.\d+\.\d+$', version):
        print(f"❌ Invalid version format in VERSION file: {version}")
        print("Expected format: X.Y.Z (e.g., '2.1.0')")
        sys.exit(1)

    return version


def should_exclude_file(file_path: Path) -> bool:
    """Check if file should be excluded from version checking."""
    for pattern in EXCLUDE_PATTERNS:
        if file_path.match(pattern):
            return True
    return False


def should_ignore_line(line: str) -> bool:
    """Check if line contains context that should be ignored."""
    line_lower = line.lower()
    for pattern in IGNORE_CONTEXTS:
        if re.search(pattern, line_lower, re.IGNORECASE):
            return True
    return False


def extract_version_from_line(line: str) -> List[Tuple[str, str]]:
    """
    Extract version numbers from a line.

    Returns:
        List of (version, context) tuples
    """
    results = []

    # Skip lines with ignore contexts
    if should_ignore_line(line):
        return results

    # Check badge pattern - ALWAYS include (high confidence)
    badge_match = BADGE_PATTERN.search(line)
    if badge_match:
        version = badge_match.group(1)
        if version not in IGNORE_VERSIONS:
            results.append((version, "badge"))

    # Check version header pattern - ALWAYS include (high confidence)
    header_match = VERSION_HEADER_PATTERN.search(line)
    if header_match:
        version = header_match.group(1)
        if version not in IGNORE_VERSIONS:
            results.append((version, "header"))

    # Check annotation pattern - Include only if not in ignore list
    annotation_match = VERSION_ANNOTATION_PATTERN.search(line)
    if annotation_match:
        version = annotation_match.group(1)
        if version not in IGNORE_VERSIONS:
            results.append((version, "annotation"))

    # General version pattern (if no specific pattern matched)
    # More conservative - skip common example versions
    if not results:
        for match in VERSION_PATTERN.finditer(line):
            version = match.group(1)
            # Skip if it's in ignore list
            if version in IGNORE_VERSIONS:
                continue
            results.append((version, "general"))

    return results


def scan_file_for_versions(file_path: Path) -> List[VersionReference]:
    """Scan a file for version references."""
    refs = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                versions = extract_version_from_line(line)
                for version, context in versions:
                    refs.append(VersionReference(
                        file_path=file_path,
                        line_number=line_num,
                        line_content=line.strip(),
                        version=version,
                        context=context
                    ))
    except (UnicodeDecodeError, PermissionError) as e:
        # Skip binary files or files without read permissions
        pass

    return refs


def scan_all_files() -> List[VersionReference]:
    """Scan all relevant files for version references."""
    all_refs = []

    for search_path in SEARCH_PATHS:
        if search_path.is_file():
            if not should_exclude_file(search_path):
                all_refs.extend(scan_file_for_versions(search_path))
        elif search_path.is_dir():
            for md_file in search_path.rglob("*.md"):
                if not should_exclude_file(md_file):
                    all_refs.extend(scan_file_for_versions(md_file))

    return all_refs


def validate_versions(target_version: str) -> ValidationResult:
    """Validate all version references against target version."""
    all_refs = scan_all_files()

    correct_refs = []
    incorrect_refs = []

    for ref in all_refs:
        if ref.version == target_version:
            correct_refs.append(ref)
        else:
            incorrect_refs.append(ref)

    return ValidationResult(
        target_version=target_version,
        correct_refs=correct_refs,
        incorrect_refs=incorrect_refs
    )


def fix_version_in_file(file_path: Path, old_version: str, new_version: str, dry_run: bool = False) -> int:
    """
    Fix version references in a file.

    Returns:
        Number of replacements made
    """
    if dry_run:
        print(f"  [DRY RUN] Would fix: {file_path.relative_to(PROJECT_ROOT)}")
        return 0

    content = file_path.read_text()

    # Replace in all contexts
    patterns = [
        (rf"badge/version-{re.escape(old_version)}", f"badge/version-{new_version}"),
        (rf"\*\*Version\*\*:\s*v{re.escape(old_version)}", f"**Version**: v{new_version}"),
        (rf"\(NEW\s*-\s*v{re.escape(old_version)}\)", f"(NEW - v{new_version})"),
        (rf"\(v{re.escape(old_version)}\)", f"(v{new_version})"),
        (rf"v{re.escape(old_version)}", f"v{new_version}"),
    ]

    modified = False
    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            modified = True

    if modified:
        file_path.write_text(content)
        return 1

    return 0


def fix_all_versions(result: ValidationResult, dry_run: bool = False) -> int:
    """
    Fix all incorrect version references.

    Returns:
        Number of files modified
    """
    files_to_fix: Dict[Path, Set[str]] = {}

    # Group by file and collect versions to fix
    for ref in result.incorrect_refs:
        if ref.file_path not in files_to_fix:
            files_to_fix[ref.file_path] = set()
        files_to_fix[ref.file_path].add(ref.version)

    files_modified = 0

    for file_path, old_versions in files_to_fix.items():
        for old_version in old_versions:
            count = fix_version_in_file(file_path, old_version, result.target_version, dry_run)
            files_modified += count

    return files_modified


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Version consistency validator and sync tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check for version inconsistencies
  python version_sync.py --check

  # Fix all inconsistencies
  python version_sync.py --fix

  # Dry run (show what would be fixed without modifying)
  python version_sync.py --fix --dry-run

  # Verbose output
  python version_sync.py --check --verbose
"""
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for version inconsistencies (default action)"
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix all version inconsistencies"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files (requires --fix)"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output"
    )

    args = parser.parse_args()

    # Default to check if no action specified
    if not args.check and not args.fix:
        args.check = True

    # Read target version
    print("🔍 Reading target version from VERSION file...")
    target_version = read_target_version()
    print(f"✅ Target version: v{target_version}")
    print()

    # Validate versions
    print("🔍 Scanning files for version references...")
    result = validate_versions(target_version)
    print(f"✅ Found {len(result.correct_refs) + len(result.incorrect_refs)} version references")
    print()

    # Print summary
    print("=" * 60)
    print(result.summary())
    print("=" * 60)
    print()

    # Show details if verbose or if there are issues
    if args.verbose or not result.is_consistent():
        if result.incorrect_refs:
            print("❌ Incorrect version references:")
            print()
            for ref in sorted(result.incorrect_refs, key=lambda r: (str(r.file_path), r.line_number)):
                print(f"  {ref}")
            print()

        if args.verbose and result.correct_refs:
            print("✅ Correct version references:")
            print()
            for ref in sorted(result.correct_refs, key=lambda r: (str(r.file_path), r.line_number)):
                print(f"  {ref}")
            print()

    # Fix if requested
    if args.fix:
        if result.is_consistent():
            print("✅ No fixes needed - all versions are consistent!")
            return 0

        print("🔧 Fixing version inconsistencies...")
        files_modified = fix_all_versions(result, dry_run=args.dry_run)

        if args.dry_run:
            print()
            print(f"[DRY RUN] Would modify {files_modified} files")
            print("Run without --dry-run to apply changes")
        else:
            print()
            print(f"✅ Fixed {files_modified} files")
            print()

            # Re-validate
            print("🔍 Re-validating...")
            new_result = validate_versions(target_version)
            if new_result.is_consistent():
                print("✅ All version references are now consistent!")
            else:
                print(f"⚠️  {len(new_result.incorrect_refs)} references still inconsistent")
                print("Manual review may be required")

        return 0

    # Exit with error code if inconsistencies found
    return 0 if result.is_consistent() else 1


if __name__ == "__main__":
    sys.exit(main())

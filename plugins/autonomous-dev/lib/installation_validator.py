#!/usr/bin/env python3
"""
Installation Validator - Ensures complete file coverage and detects missing files

This module provides validation for plugin installations, ensuring 100% file
coverage and detecting missing files, extra files, and structural issues.

Key Features:
- File coverage calculation (actual / expected * 100)
- Missing file detection (source files not in destination)
- Extra file detection (unexpected files in destination)
- Directory structure validation
- Manifest-based validation
- Detailed reporting

Usage:
    from installation_validator import InstallationValidator

    # Basic validation
    validator = InstallationValidator(source_dir, dest_dir)
    result = validator.validate()

    # Manifest-based validation
    validator = InstallationValidator.from_manifest(manifest_path, dest_dir)
    result = validator.validate()

    # Generate report
    report = validator.generate_report(result)
    print(report)

Date: 2025-11-17
Issue: GitHub #80 (Bootstrap overhaul - Phase 3)
Agent: implementer

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See error-handling-patterns skill for exception handling.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from .file_discovery import FileDiscovery

# Security utilities for path validation and audit logging
try:
    from plugins.autonomous_dev.lib.security_utils import validate_path, audit_log
except ImportError:
    from security_utils import validate_path, audit_log


class ValidationError(Exception):
    """Raised when validation encounters a critical error."""
    pass


@dataclass
class ValidationResult:
    """Result of installation validation.

    Attributes:
        status: "complete" if 100%, "incomplete" otherwise
        coverage: Coverage percentage (0-100)
        total_expected: Total files expected from source
        total_found: Total files found in destination
        missing_files: Count of missing files
        extra_files: Count of extra files
        missing_file_list: List of missing file paths
        extra_file_list: List of extra file paths
        structure_valid: Whether directory structure is valid
        errors: List of error messages
        sizes_match: Whether file sizes match manifest (if applicable)
        size_errors: Files with size mismatches (if applicable)
    """
    status: str
    coverage: float
    total_expected: int
    total_found: int
    missing_files: int
    extra_files: int
    missing_file_list: List[str]
    extra_file_list: List[str]
    structure_valid: bool
    errors: List[str]
    sizes_match: Optional[bool] = None
    size_errors: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class InstallationValidator:
    """Validates plugin installation completeness and correctness.

    Compares source and destination directories, calculates coverage,
    and detects missing or extra files.

    Attributes:
        source_dir: Path to source plugin directory
        dest_dir: Path to destination installation directory
        manifest: Optional installation manifest for validation

    Examples:
        >>> validator = InstallationValidator(source_dir, dest_dir)
        >>> result = validator.validate()
        >>> print(f"Coverage: {result.coverage}%")
        >>> if result.missing_files > 0:
        ...     print(f"Missing: {result.missing_file_list}")
    """

    def __init__(self, source_dir: Path, dest_dir: Path, manifest: Optional[Dict] = None):
        """Initialize validator with security validation.

        Args:
            source_dir: Source plugin directory
            dest_dir: Destination installation directory
            manifest: Optional manifest for validation

        Raises:
            ValidationError: If source directory doesn't exist
            ValueError: If path validation fails (path traversal, symlink)
        """
        # Validate paths (prevents CWE-22, CWE-59)
        self.source_dir = validate_path(
            Path(source_dir).resolve(),
            purpose="source directory",
            allow_missing=False
        )
        self.dest_dir = validate_path(
            Path(dest_dir).resolve(),
            purpose="destination directory",
            allow_missing=False
        )
        self.manifest = manifest

        # Audit log initialization
        audit_log("installation_validator", "initialized", {
            "source_dir": str(self.source_dir),
            "dest_dir": str(self.dest_dir)
        })

    @classmethod
    def from_manifest(cls, manifest_path: Path, dest_dir: Path) -> "InstallationValidator":
        """Create validator from manifest file.

        Args:
            manifest_path: Path to manifest JSON file
            dest_dir: Destination directory

        Returns:
            InstallationValidator instance with loaded manifest

        Raises:
            ValidationError: If manifest file doesn't exist or is invalid
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise ValidationError(f"Manifest file not found: {manifest_path}")

        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid manifest JSON: {e}")

        # Extract source directory from manifest or use parent directory
        source_dir = manifest_path.parent
        if "source_dir" in manifest:
            source_dir = Path(manifest["source_dir"])

        return cls(source_dir, dest_dir, manifest)

    @classmethod
    def from_manifest_dict(cls, manifest: Dict, dest_dir: Path) -> "InstallationValidator":
        """Create validator from manifest dictionary.

        Args:
            manifest: Manifest dictionary
            dest_dir: Destination directory

        Returns:
            InstallationValidator instance
        """
        # Create instance without source directory check for manifest-only validation
        instance = cls.__new__(cls)
        instance.source_dir = Path("/tmp/manifest_validation")  # Dummy path
        instance.dest_dir = Path(dest_dir)
        instance.manifest = manifest
        return instance

    def validate(self) -> ValidationResult:
        """Validate installation completeness.

        Returns:
            ValidationResult with coverage, missing files, etc.

        Raises:
            ValidationError: If destination directory doesn't exist
        """
        errors = []

        # Check destination exists
        if not self.dest_dir.exists():
            raise ValidationError(f"Destination directory not found: {self.dest_dir}")

        # Discover expected files from source or manifest
        if self.manifest and "files" in self.manifest:
            expected_files = [Path(f["path"]) for f in self.manifest["files"]]
            total_expected = len(expected_files)
        else:
            discovery = FileDiscovery(self.source_dir)
            discovered = discovery.discover_all_files()
            # Convert to relative paths
            expected_files = [f.relative_to(self.source_dir) for f in discovered]
            total_expected = len(expected_files)

        # Discover actual files in destination
        dest_discovery = FileDiscovery(self.dest_dir)
        actual_discovered = dest_discovery.discover_all_files()
        actual_files = [f.relative_to(self.dest_dir) for f in actual_discovered]
        total_found = len(actual_files)

        # Find missing files
        expected_set = set(str(f) for f in expected_files)
        actual_set = set(str(f) for f in actual_files)

        missing_set = expected_set - actual_set
        missing_file_list = sorted(list(missing_set))
        missing_count = len(missing_file_list)

        # Find extra files
        extra_set = actual_set - expected_set
        extra_file_list = sorted(list(extra_set))
        extra_count = len(extra_file_list)

        # Calculate coverage
        coverage = self.calculate_coverage(total_expected, total_found)

        # Validate directory structure
        structure_valid = self.validate_structure()

        # Determine status
        status = "complete" if coverage == 100.0 and missing_count == 0 else "incomplete"

        return ValidationResult(
            status=status,
            coverage=coverage,
            total_expected=total_expected,
            total_found=total_found,
            missing_files=missing_count,
            extra_files=extra_count,
            missing_file_list=missing_file_list,
            extra_file_list=extra_file_list,
            structure_valid=structure_valid,
            errors=errors,
        )

    def validate_sizes(self) -> Dict[str, Any]:
        """Validate file sizes against manifest.

        Returns:
            Dictionary with sizes_match and size_errors

        Raises:
            ValidationError: If no manifest provided
        """
        if not self.manifest or "files" not in self.manifest:
            raise ValidationError("No manifest provided for size validation")

        size_errors = []
        sizes_match = True

        for file_info in self.manifest["files"]:
            file_path = Path(file_info["path"])
            expected_size = file_info.get("size", 0)

            dest_file = self.dest_dir / file_path
            if dest_file.exists():
                actual_size = dest_file.stat().st_size
                if actual_size != expected_size:
                    sizes_match = False
                    size_errors.append(str(file_path))

        return {
            "sizes_match": sizes_match,
            "size_errors": size_errors,
        }

    def calculate_coverage(self, expected: int, actual: int) -> float:
        """Calculate coverage percentage.

        Args:
            expected: Number of expected files
            actual: Number of actual files

        Returns:
            Coverage percentage (0-100), rounded to 2 decimal places
        """
        if expected == 0:
            return 100.0 if actual == 0 else 0.0

        # Calculate percentage based on actual/expected
        # Note: actual can be > expected if there are extra files
        coverage = (min(actual, expected) / expected) * 100.0
        return round(coverage, 2)

    def find_missing_files(self, expected_files: List[Path], actual_files: List[Path]) -> List[str]:
        """Find files that are expected but not present.

        Args:
            expected_files: List of expected file paths
            actual_files: List of actual file paths

        Returns:
            List of missing file paths (as strings)
        """
        expected_set = set(str(f) for f in expected_files)
        actual_set = set(str(f) for f in actual_files)
        missing = expected_set - actual_set
        return sorted(list(missing))

    def validate_structure(self) -> bool:
        """Validate directory structure.

        Checks that required directories exist:
        - lib/
        - scripts/
        - config/

        Returns:
            True if structure is valid, False otherwise
        """
        required_dirs = ["lib", "scripts", "config"]

        for dir_name in required_dirs:
            dir_path = self.dest_dir / dir_name
            if not dir_path.exists():
                return False

        return True

    def generate_report(self, result: ValidationResult) -> str:
        """Generate human-readable validation report.

        Args:
            result: ValidationResult to format

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("Installation Validation Report")
        lines.append("=" * 60)
        lines.append("")

        # Status
        status_symbol = "✅" if result.status == "complete" else "⚠️"
        lines.append(f"{status_symbol} Status: {result.status.upper()}")
        lines.append("")

        # Coverage
        lines.append(f"📊 Coverage: {result.coverage}%")
        lines.append(f"   Expected: {result.total_expected} files")
        lines.append(f"   Found: {result.total_found} files")
        lines.append("")

        # Missing files
        if result.missing_files > 0:
            lines.append(f"❌ Missing Files: {result.missing_files}")
            for file_path in result.missing_file_list[:10]:  # Show first 10
                lines.append(f"   - {file_path}")
            if len(result.missing_file_list) > 10:
                lines.append(f"   ... and {len(result.missing_file_list) - 10} more")
            lines.append("")

        # Extra files
        if result.extra_files > 0:
            lines.append(f"➕ Extra Files: {result.extra_files}")
            for file_path in result.extra_file_list[:10]:  # Show first 10
                lines.append(f"   - {file_path}")
            if len(result.extra_file_list) > 10:
                lines.append(f"   ... and {len(result.extra_file_list) - 10} more")
            lines.append("")

        # Structure validation
        structure_symbol = "✅" if result.structure_valid else "❌"
        lines.append(f"{structure_symbol} Directory Structure: {'Valid' if result.structure_valid else 'Invalid'}")
        lines.append("")

        # Size validation (if applicable)
        if result.sizes_match is not None:
            size_symbol = "✅" if result.sizes_match else "❌"
            lines.append(f"{size_symbol} File Sizes: {'Match' if result.sizes_match else 'Mismatch'}")
            if result.size_errors:
                lines.append(f"   Size errors in {len(result.size_errors)} files")
            lines.append("")

        # Errors
        if result.errors:
            lines.append("❌ Errors:")
            for error in result.errors:
                lines.append(f"   - {error}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

    def get_status_code(self) -> int:
        """Get exit status code based on validation.

        Returns:
            0 if installation is complete, 1 otherwise
        """
        result = self.validate()
        return 0 if result.status == "complete" else 1


# CLI interface for standalone usage
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Validate plugin installation")
    parser.add_argument("--source", type=Path, required=True, help="Source plugin directory")
    parser.add_argument("--dest", type=Path, required=True, help="Destination installation directory")
    parser.add_argument("--manifest", type=Path, help="Optional manifest file")
    parser.add_argument("--quiet", action="store_true", help="Only output status code")

    args = parser.parse_args()

    try:
        if args.manifest:
            validator = InstallationValidator.from_manifest(args.manifest, args.dest)
        else:
            validator = InstallationValidator(args.source, args.dest)

        result = validator.validate()

        if not args.quiet:
            report = validator.generate_report(result)
            print(report)

        sys.exit(validator.get_status_code())

    except ValidationError as e:
        print(f"❌ Validation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}", file=sys.stderr)
        sys.exit(1)

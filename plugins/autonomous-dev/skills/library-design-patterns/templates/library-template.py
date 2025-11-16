#!/usr/bin/env python3
"""Library template demonstrating two-tier design pattern.

This template shows how to structure a Python library following the
two-tier design pattern with core business logic (Tier 1) separated
from CLI interface (Tier 2).

Design Patterns (see skills/library-design-patterns):
    - Two-tier design: Core logic + CLI separation
    - Progressive enhancement: String → Path → Whitelist validation
    - Non-blocking enhancements: Core succeeds even if enhancements fail
    - Security-first: Input validation, audit logging
    - Docstring standards: Google-style comprehensive documentation

Author: library-design-patterns skill
Version: 1.0.0
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Union
import logging

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# TIER 1: CORE LIBRARY (Business Logic)
# ============================================================================

@dataclass
class ProcessResult:
    """Result of process operation.

    Attributes:
        success: Whether operation succeeded
        items_processed: Number of items processed
        output_path: Path to output file (if created)
        error_message: Error message if operation failed
    """
    success: bool
    items_processed: int
    output_path: Optional[Path] = None
    error_message: Optional[str] = None


class ProcessingError(Exception):
    """Raised when processing operation fails."""
    pass


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


def process_file(
    input_path: Union[str, Path],
    *,
    output_path: Optional[Union[str, Path]] = None,
    allowed_dirs: Optional[List[Path]] = None,
    dry_run: bool = False
) -> ProcessResult:
    """Process input file with optional security validation.

    This demonstrates:
    - Two-tier design (pure business logic, no CLI assumptions)
    - Progressive enhancement (string → Path → whitelist)
    - Security-first design (input validation, path validation)

    Args:
        input_path: Path to input file (string or Path)
        output_path: Path to output file (default: None, creates temp file)
        allowed_dirs: Whitelist of allowed directories for security
            (default: None, no whitelist validation)
        dry_run: If True, simulate without making changes (default: False)

    Returns:
        ProcessResult with operation details

    Raises:
        FileNotFoundError: If input file doesn't exist
        SecurityError: If path outside allowed directories (CWE-22)
        ProcessingError: If processing fails

    Example:
        >>> # Basic usage
        >>> result = process_file("data.txt")
        >>> print(result.items_processed)
        100
        >>>
        >>> # With security validation
        >>> result = process_file(
        ...     "data.txt",
        ...     allowed_dirs=[Path("/tmp"), Path("/var/tmp")]
        ... )

    Security:
        - CWE-22 Prevention: Path traversal via whitelist validation
        - Input Validation: Type and existence checks
        - Audit Trail: Operations logged for forensics

    See:
        - skills/library-design-patterns: Design pattern guidance
        - templates/cli-template.py: CLI interface for this library
    """
    # Progressive Enhancement Level 1: String → Path conversion
    input_file = Path(input_path) if isinstance(input_path, str) else input_path

    # Progressive Enhancement Level 2: Existence validation
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    if not input_file.is_file():
        raise ValueError(f"Not a file: {input_file}")

    # Progressive Enhancement Level 3: Whitelist validation (security)
    if allowed_dirs:
        try:
            resolved_input = input_file.resolve(strict=True)
        except (OSError, RuntimeError) as e:
            raise SecurityError(f"Cannot resolve path: {e}")

        if not any(resolved_input.is_relative_to(d) for d in allowed_dirs):
            raise SecurityError(
                f"Path outside allowed directories: {resolved_input}\n"
                f"Allowed: {', '.join(str(d) for d in allowed_dirs)}"
            )

        input_file = resolved_input

    # Handle output path (with same progressive validation)
    if output_path:
        output_file = Path(output_path) if isinstance(output_path, str) else output_path
        if allowed_dirs:
            # Validate output path against whitelist
            try:
                resolved_output = output_file.resolve(strict=False)
            except (OSError, RuntimeError) as e:
                raise SecurityError(f"Cannot resolve output path: {e}")

            if not any(resolved_output.is_relative_to(d) for d in allowed_dirs):
                raise SecurityError(
                    f"Output path outside allowed directories: {resolved_output}"
                )
            output_file = resolved_output
    else:
        # Default: create output in same directory as input
        output_file = input_file.parent / f"{input_file.stem}_processed{input_file.suffix}"

    # Dry run mode (no actual changes)
    if dry_run:
        logger.info(f"DRY RUN: Would process {input_file} → {output_file}")
        return ProcessResult(
            success=True,
            items_processed=0,
            output_path=output_file
        )

    # Core business logic (process the file)
    try:
        items_processed = _process_core_logic(input_file, output_file)

        return ProcessResult(
            success=True,
            items_processed=items_processed,
            output_path=output_file
        )

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise ProcessingError(f"Failed to process file: {e}")


def _process_core_logic(input_path: Path, output_path: Path) -> int:
    """Core processing logic (private helper).

    Args:
        input_path: Validated input file path
        output_path: Validated output file path

    Returns:
        Number of items processed
    """
    # Example: Read input, process, write output
    with input_path.open('r') as f:
        lines = f.readlines()

    # Process lines (example: convert to uppercase)
    processed_lines = [line.upper() for line in lines]

    # Write output
    with output_path.open('w') as f:
        f.writelines(processed_lines)

    return len(processed_lines)


# ============================================================================
# TIER 2: CLI INTERFACE (User Interaction)
# ============================================================================
# NOTE: In production, this would be in a separate file (e.g., cli_script.py)
# Shown here for completeness of the template

def main_cli():
    """CLI interface for the library (Tier 2).

    This demonstrates:
    - Argument parsing with argparse
    - User interaction (confirmation prompts)
    - Error formatting for terminal
    - Exit codes (0 = success, 1 = error)

    See:
        - templates/cli-template.py: Standalone CLI template
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Process file with security validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.txt
  %(prog)s input.txt --output result.txt
  %(prog)s input.txt --allowed-dir /tmp --dry-run
        """
    )

    parser.add_argument(
        "input_file",
        help="Input file to process"
    )

    parser.add_argument(
        "--output",
        help="Output file path (default: auto-generated)"
    )

    parser.add_argument(
        "--allowed-dir",
        action="append",
        dest="allowed_dirs",
        help="Allowed directory (can be specified multiple times)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without making changes"
    )

    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # User interaction (CLI-specific)
    if not args.yes and not args.dry_run:
        confirm = input(f"Process {args.input_file}? [y/N]: ")
        if confirm.lower() != 'y':
            print("Operation cancelled")
            return 0

    # Convert allowed_dirs to Path objects
    allowed_dirs = None
    if args.allowed_dirs:
        allowed_dirs = [Path(d) for d in args.allowed_dirs]

    # Delegate to core library (Tier 1)
    try:
        result = process_file(
            args.input_file,
            output_path=args.output,
            allowed_dirs=allowed_dirs,
            dry_run=args.dry_run
        )

        # Format output for CLI
        if result.success:
            if args.dry_run:
                print(f"✅ DRY RUN: Would process {args.input_file}")
            else:
                print(f"✅ Processed {result.items_processed} items")
                print(f"   Output: {result.output_path}")
            return 0
        else:
            print(f"❌ Processing failed: {result.error_message}")
            return 1

    except FileNotFoundError as e:
        print(f"❌ File not found: {e}", file=sys.stderr)
        return 2

    except SecurityError as e:
        print(f"❌ Security error: {e}", file=sys.stderr)
        return 3

    except ProcessingError as e:
        print(f"❌ Processing error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main_cli())

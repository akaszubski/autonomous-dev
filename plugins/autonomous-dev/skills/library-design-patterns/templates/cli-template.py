#!/usr/bin/env python3
"""CLI template for two-tier design pattern (Tier 2).

This template shows how to create a command-line interface (CLI) that
wraps a core library following the two-tier design pattern.

Responsibilities (Tier 2):
    - Argument parsing (argparse, click, etc.)
    - User interaction (input prompts, confirmation)
    - Output formatting (pretty-printing for terminal)
    - Exit codes (0 = success, non-zero = error)
    - Error formatting for human readability

What NOT to include (belongs in Tier 1):
    - Business logic
    - Data processing
    - File I/O (except for CLI-specific formatting)
    - Complex algorithms

Design Pattern (see skills/library-design-patterns):
    - Thin wrapper around core library
    - Delegates all business logic to Tier 1
    - Handles only presentation and user interaction

Author: library-design-patterns skill
Version: 1.0.0
"""

import argparse
import sys
from pathlib import Path

# Import core library (Tier 1)
# In real implementation, this would be:
# from plugins.autonomous_dev.lib.core_library import (
#     process_function,
#     CoreError,
#     SecurityError
# )

# For template purposes, we'll use placeholders
# Replace these with actual imports from your Tier 1 library
try:
    from some_library import (
        process_function,
        CoreError,
        SecurityError
    )
except ImportError:
    # Placeholder for template
    def process_function(*args, **kwargs):
        """Placeholder - replace with actual import."""
        raise NotImplementedError("Replace with actual library import")

    class CoreError(Exception):
        """Placeholder exception."""
        pass

    class SecurityError(Exception):
        """Placeholder exception."""
        pass


def main():
    """CLI entry point.

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Step 1: Argument Parsing
    parser = argparse.ArgumentParser(
        description="CLI tool description goes here",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.txt
  %(prog)s input.txt --output result.txt
  %(prog)s input.txt --verbose --dry-run

For more information, see:
  https://github.com/your-org/your-repo/docs/cli-guide.md
        """
    )

    # Positional arguments
    parser.add_argument(
        "input_file",
        help="Input file to process"
    )

    # Optional arguments
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: auto-generated)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate operation without making changes"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompts (auto-approve)"
    )

    # Security options
    parser.add_argument(
        "--allowed-dir",
        action="append",
        dest="allowed_dirs",
        help="Allowed directory for path validation (can be specified multiple times)"
    )

    args = parser.parse_args()

    # Step 2: User Interaction (CLI-specific)
    if not args.yes and not args.dry_run:
        # Confirmation prompt
        print(f"Input file: {args.input_file}")
        if args.output:
            print(f"Output file: {args.output}")
        print()

        confirm = input("Continue? [y/N]: ")
        if confirm.lower() != 'y':
            print("Operation cancelled by user")
            return 0

    # Step 3: Convert CLI arguments to library parameters
    allowed_dirs = None
    if args.allowed_dirs:
        allowed_dirs = [Path(d) for d in args.allowed_dirs]

    # Step 4: Delegate to core library (Tier 1)
    try:
        if args.verbose:
            print(f"Processing {args.input_file}...")

        # Call core library function
        result = process_function(
            args.input_file,
            output_path=args.output,
            allowed_dirs=allowed_dirs,
            dry_run=args.dry_run
        )

        # Step 5: Format output for CLI
        if result.success:
            if args.dry_run:
                print(f"✅ DRY RUN: Would process {args.input_file}")
                if args.verbose:
                    print(f"   Estimated items: {result.items_processed}")
            else:
                print(f"✅ Success: Processed {result.items_processed} items")
                if result.output_path:
                    print(f"   Output: {result.output_path}")

            if args.verbose:
                print(f"   Duration: {result.duration:.2f}s")

            return 0  # Success exit code

        else:
            # Handle non-exception failure
            print(f"❌ Operation failed: {result.error_message}")
            return 1  # Generic error exit code

    # Step 6: Exception Handling (convert to CLI-friendly errors)
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2  # File not found exit code

    except SecurityError as e:
        print(f"❌ Security error: {e}", file=sys.stderr)
        print("\nThis path is outside allowed directories.")
        if args.allowed_dirs:
            print(f"Allowed directories: {', '.join(args.allowed_dirs)}")
        else:
            print("Hint: Use --allowed-dir to specify allowed directories")
        return 3  # Security error exit code

    except CoreError as e:
        print(f"❌ Processing error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1  # Generic error exit code

    except KeyboardInterrupt:
        print("\n⚠️  Operation interrupted by user")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        print("\nThis is a bug. Please report it with the following details:")
        import traceback
        traceback.print_exc()
        return 1  # Generic error exit code


# ============================================================================
# CLI Utilities (Optional)
# ============================================================================

def format_table(headers, rows):
    """Format data as ASCII table for CLI output.

    Args:
        headers: List of column headers
        rows: List of row data (each row is a list)

    Returns:
        Formatted table string
    """
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    # Format header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * w for w in widths)

    # Format rows
    formatted_rows = [
        " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
        for row in rows
    ]

    # Combine
    return "\n".join([header_line, separator] + formatted_rows)


def confirm_action(message, default=False):
    """Prompt user for confirmation.

    Args:
        message: Confirmation message
        default: Default value if user just presses Enter

    Returns:
        True if user confirms, False otherwise
    """
    suffix = "[Y/n]" if default else "[y/N]"
    prompt = f"{message} {suffix}: "

    response = input(prompt).strip().lower()

    if not response:
        return default

    return response in ('y', 'yes')


def print_progress(current, total, prefix="Progress"):
    """Print progress bar to terminal.

    Args:
        current: Current progress value
        total: Total/maximum value
        prefix: Prefix string for progress bar
    """
    percent = int(100 * current / total)
    bar_length = 40
    filled = int(bar_length * current / total)
    bar = "=" * filled + "-" * (bar_length - filled)

    print(f"\r{prefix}: [{bar}] {percent}%", end="", flush=True)

    if current >= total:
        print()  # New line when complete


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    sys.exit(main())

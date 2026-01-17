#!/usr/bin/env python3
"""
Command-line interface for implement dispatcher.

Provides argument parsing and user guidance formatting:
    - parse_implement_args(): Parse command-line arguments
    - format_user_guidance(): Format error messages with usage examples

Date: 2026-01-09
Issue: Consolidate /implement, /auto-implement, /batch-implement
Agent: implementer
Status: GREEN (implementation complete)
"""

import argparse
import sys
from typing import List
from .modes import ImplementMode, get_mode_help_text
from .models import ImplementRequest
from .validators import ImplementDispatchError


def parse_implement_args(args: List[str]):
    """
    Parse command-line arguments for /implement command.

    Args:
        args: List of command-line arguments

    Returns:
        ImplementRequest: Parsed request object

    Raises:
        ImplementDispatchError: If arguments are invalid

    Examples:
        >>> parse_implement_args(["Add JWT auth"])
        ImplementRequest(mode=FULL_PIPELINE, feature_description="Add JWT auth")

        >>> parse_implement_args(["--quick", "Fix typo"])
        ImplementRequest(mode=QUICK, feature_description="Fix typo")

        >>> parse_implement_args(["--batch", "features.txt"])
        ImplementRequest(mode=BATCH, batch_file="features.txt")
    """
    # Handle empty args
    if not args:
        raise ImplementDispatchError("No feature description provided. Use --help for usage information.")

    # Check if all args are whitespace
    if all(arg.isspace() or not arg for arg in args):
        raise ImplementDispatchError("Feature description cannot be empty or whitespace")

    # Create parser
    parser = argparse.ArgumentParser(
        prog='/implement',
        description='Smart implementation command with multiple modes',
        add_help=False,  # We'll handle help manually
    )

    # Create mutually exclusive group for mode selection
    mode_group = parser.add_mutually_exclusive_group()

    # Mode flags
    mode_group.add_argument(
        '--quick', '-q',
        action='store_true',
        help='Quick mode: Direct implementation (implementer agent only)'
    )
    mode_group.add_argument(
        '--batch', '-b',
        type=str,
        metavar='FILE',
        help='Batch mode: Process features from file'
    )
    mode_group.add_argument(
        '--issues', '-i',
        type=int,
        nargs='+',
        metavar='N',
        help='Batch mode: Process GitHub issues'
    )
    mode_group.add_argument(
        '--resume', '-r',
        type=str,
        metavar='BATCH_ID',
        help='Batch mode: Resume previous batch'
    )
    mode_group.add_argument(
        '--full',
        action='store_true',
        help='Full pipeline mode (default)'
    )

    # Help flag
    parser.add_argument(
        '--help', '-h',
        action='store_true',
        help='Show this help message'
    )

    # Positional argument for feature description
    parser.add_argument(
        'feature_description',
        nargs='*',
        help='Feature description (required for full pipeline and quick modes)'
    )

    # Parse args - capture argparse errors
    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        # argparse calls sys.exit on error, convert to our exception
        # Check if it's a mutually exclusive error by checking stderr
        import io
        from contextlib import redirect_stderr

        # Try parsing again to capture error message
        stderr_capture = io.StringIO()
        try:
            with redirect_stderr(stderr_capture):
                parser.parse_args(args)
        except SystemExit as e:
            pass  # Expected when argparse encounters an error

        error_msg = stderr_capture.getvalue()

        # Check for specific error patterns
        if "not allowed with argument" in error_msg:
            raise ImplementDispatchError(
                "Mutually exclusive flags provided. "
                "Cannot use --quick, --batch, --issues, and --resume together. "
                "Use --help for usage information."
            )
        elif "expected one argument" in error_msg and "--batch" in error_msg:
            raise ImplementDispatchError(
                "Batch mode (--batch) requires either a batch file or --issues flag. "
                "Example: /implement --batch features.txt"
            )
        elif "expected one argument" in error_msg and "--quick" in error_msg:
            raise ImplementDispatchError(
                "Feature description required for quick mode. "
                "Example: /implement --quick \"Fix typo\""
            )
        else:
            raise ImplementDispatchError("Invalid arguments. Use --help for usage information.")
    except ImplementDispatchError:
        # Re-raise our own exceptions
        raise
    except Exception as e:
        raise ImplementDispatchError(f"Failed to parse arguments: {e}")

    # Handle help
    if parsed.help:
        help_text = get_help_text()
        return help_text  # Return help text instead of request

    # Detect mode
    if parsed.quick:
        mode = ImplementMode.QUICK
    elif parsed.batch:
        mode = ImplementMode.BATCH
    elif parsed.issues:
        mode = ImplementMode.BATCH
    elif parsed.resume:
        mode = ImplementMode.BATCH
    else:
        mode = ImplementMode.FULL_PIPELINE

    # Build request based on mode
    if mode == ImplementMode.FULL_PIPELINE or mode == ImplementMode.QUICK:
        # Need feature description
        if not parsed.feature_description:
            raise ImplementDispatchError(
                f"Feature description required for {mode.value} mode. "
                f"Example: /implement \"Add JWT authentication\""
            )

        # Join feature description parts
        feature_description = ' '.join(parsed.feature_description)

        if not feature_description.strip():
            raise ImplementDispatchError("Feature description cannot be empty or whitespace")

        return ImplementRequest(
            mode=mode,
            feature_description=feature_description,
        )

    elif mode == ImplementMode.BATCH:
        # Determine batch source
        if parsed.batch:
            return ImplementRequest(
                mode=mode,
                batch_file=parsed.batch,
            )
        elif parsed.issues:
            return ImplementRequest(
                mode=mode,
                issue_numbers=parsed.issues,
            )
        elif parsed.resume:
            return ImplementRequest(
                mode=mode,
                batch_id=parsed.resume,
            )
        else:
            raise ImplementDispatchError(
                "Batch mode requires either a batch file (--batch), "
                "issue numbers (--issues), or batch ID (--resume)"
            )

    raise ImplementDispatchError(f"Unsupported mode: {mode}")


def format_user_guidance(error_msg: str) -> str:
    """
    Format user guidance message with error and usage examples.

    Args:
        error_msg: Error message to display

    Returns:
        str: Formatted guidance message

    Example:
        >>> guidance = format_user_guidance("Feature description required")
        >>> print(guidance)
        Error: Feature description required

        Usage: /implement [OPTIONS] FEATURE_DESCRIPTION
        ...
    """
    lines = [
        "Error: " + error_msg,
        "",
        get_help_text(),
    ]

    return "\n".join(lines)


def get_help_text() -> str:
    """
    Generate help text for /implement command.

    Returns:
        str: Formatted help text
    """
    help_lines = [
        "Usage: /implement [OPTIONS] FEATURE_DESCRIPTION",
        "",
        "Smart implementation command with multiple modes:",
        "",
        "  Full Pipeline (default):",
        '    /implement "Add JWT authentication"',
        "    Complete SDLC workflow (research → plan → test → implement → review → security → docs)",
        "    Time: 15-25 minutes",
        "",
        "  Quick Mode:",
        '    /implement --quick "Fix typo in README"',
        '    /implement -q "Update config value"',
        "    Direct implementation (implementer agent only, skip pipeline)",
        "    Time: 2-5 minutes",
        "",
        "  Batch Mode:",
        "    /implement --batch features.txt",
        "    /implement --issues 1 2 3",
        "    /implement --resume batch_20260109_123456",
        "    Process multiple features from file, GitHub issues, or resume",
        "    Time: 20-30 minutes per feature",
        "",
        "Options:",
        "  --quick, -q          Quick mode (implementer agent only)",
        "  --batch FILE, -b     Batch mode with features file",
        "  --issues N..., -i    Batch mode with GitHub issue numbers",
        "  --resume ID, -r      Resume previous batch",
        "  --full               Full pipeline mode (default)",
        "  --help, -h           Show this help message",
        "",
        "Examples:",
        '  /implement "Add user authentication with JWT tokens"',
        '  /implement --quick "Fix typo in documentation"',
        "  /implement --batch .claude/features.txt",
        "  /implement --issues 42 43 44",
        "  /implement --resume batch_20260109_123456",
        "",
        "For more information, see: plugins/autonomous-dev/docs/IMPLEMENT-COMMAND.md",
    ]

    return "\n".join(help_lines)

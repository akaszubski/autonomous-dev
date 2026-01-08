#!/usr/bin/env python3
"""
Implement Dispatcher - Smart /implement command routing.

Consolidates /implement, /auto-implement, /batch-implement into single
smart /implement command with mode detection and dispatching.

Modes:
    - FULL_PIPELINE (default): Complete SDLC workflow (auto-implement)
    - QUICK: Direct implementation (implementer agent only)
    - BATCH: Batch processing (file, issues, or resume)

Usage:
    from implement_dispatcher import (
        ImplementMode,
        ImplementRequest,
        ImplementResult,
        ImplementDispatchError,
        parse_implement_args,
        handle_implement_command,
    )

Date: 2026-01-09
Issue: Consolidate /implement, /auto-implement, /batch-implement
Agent: implementer
Status: GREEN (implementation complete)
"""


from .modes import ImplementMode
from .models import ImplementRequest, ImplementResult
from .validators import ImplementDispatchError  # Import error class first
from .cli import parse_implement_args, format_user_guidance
from .dispatcher import (
    dispatch_full_pipeline,
    dispatch_quick,
    dispatch_batch,
    handle_implement_command,
    invoke_auto_implement,
    invoke_implementer_agent,
    invoke_batch_implement,
    load_batch_state,
)
from .validators import (
    validate_batch_file,
    validate_issue_numbers,
    validate_batch_id,
    validate_args,
    get_batch_state_path,
)


# Export all public symbols
__all__ = [
    # Enums
    'ImplementMode',

    # Models
    'ImplementRequest',
    'ImplementResult',

    # Errors
    'ImplementDispatchError',

    # Parsing
    'parse_implement_args',
    'format_user_guidance',

    # Dispatching
    'dispatch_full_pipeline',
    'dispatch_quick',
    'dispatch_batch',
    'handle_implement_command',

    # Integration functions (for testing)
    'invoke_auto_implement',
    'invoke_implementer_agent',
    'invoke_batch_implement',
    'load_batch_state',

    # Validation
    'validate_batch_file',
    'validate_issue_numbers',
    'validate_batch_id',
    'validate_args',
    'get_batch_state_path',

    # Utilities
    'detect_mode',
]


def detect_mode(args):
    """
    Detect implementation mode from command-line arguments.

    Args:
        args: List of command-line arguments

    Returns:
        ImplementMode: Detected mode (FULL_PIPELINE, QUICK, or BATCH)

    Examples:
        >>> detect_mode(["feature description"])
        ImplementMode.FULL_PIPELINE

        >>> detect_mode(["--quick", "feature"])
        ImplementMode.QUICK

        >>> detect_mode(["--batch", "file.txt"])
        ImplementMode.BATCH
    """
    args_lower = [arg.lower() for arg in args]

    # Check for mode flags
    if "--quick" in args_lower or "-q" in args_lower:
        return ImplementMode.QUICK

    if any(flag in args_lower for flag in ["--batch", "-b", "--issues", "-i", "--resume", "-r"]):
        return ImplementMode.BATCH

    # Default to full pipeline
    return ImplementMode.FULL_PIPELINE

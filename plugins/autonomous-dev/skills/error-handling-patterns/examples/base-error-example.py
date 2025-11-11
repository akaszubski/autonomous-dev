#!/usr/bin/env python3
"""
Base Error Class Example

This example demonstrates the base error class pattern for the autonomous-dev plugin.
All custom exceptions should inherit from this base class to enable consistent error
handling and logging across the system.

See error-handling-patterns skill for complete exception hierarchy and usage.
"""


class AutonomousDevError(Exception):
    """Base exception for autonomous-dev plugin.

    All custom exceptions should inherit from this base class to enable
    consistent error handling and logging across the system.

    Example:
        >>> error = AutonomousDevError(
        ...     "Operation failed",
        ...     context={"file": "test.py", "line": 42}
        ... )
        >>> print(error)
        Operation failed
        Context:
          file: test.py
          line: 42

    See error-handling-patterns skill for exception hierarchy and usage.
    """

    def __init__(self, message: str, context: dict = None):
        """Initialize error with message and optional context.

        Args:
            message: Human-readable error description
            context: Optional dict with error context (paths, values, etc.)

        Example:
            >>> raise AutonomousDevError(
            ...     "Validation failed",
            ...     context={"expected": "string", "got": "int"}
            ... )
        """
        super().__init__(message)
        self.context = context or {}

    def __str__(self):
        """Format error with context if available.

        Returns:
            Formatted error message with context details

        Example:
            >>> error = AutonomousDevError("Failed", context={"key": "value"})
            >>> str(error)
            'Failed\\nContext:\\n  key: value'
        """
        if self.context:
            context_str = "\n".join(f"  {k}: {v}" for k, v in self.context.items())
            return f"{super().__str__()}\nContext:\n{context_str}"
        return super().__str__()


# Example usage
if __name__ == "__main__":
    # Basic error
    try:
        raise AutonomousDevError("Something went wrong")
    except AutonomousDevError as e:
        print(f"Caught error: {e}")
        print()

    # Error with context
    try:
        raise AutonomousDevError(
            "Path validation failed",
            context={
                "path": "/etc/passwd",
                "whitelist": ["/plugins", "/lib", "/agents"],
                "operation": "read"
            }
        )
    except AutonomousDevError as e:
        print(f"Caught error with context:\n{e}")
        print()

    # Error with formatted message (context + expected + got + docs)
    try:
        def format_error_message(context: str, expected: str, got: str, docs_link: str = None) -> str:
            """Format standardized error message."""
            message = f"{context}\nExpected: {expected}\nGot: {got}"
            if docs_link:
                message += f"\nSee: {docs_link}"
            return message

        raise AutonomousDevError(
            format_error_message(
                context="Feature validation failed in quality-validator agent",
                expected="All 7 agents must run",
                got="Only 5 agents ran (missing: implementer, doc-master)",
                docs_link="docs/DEVELOPMENT.md#validation-checkpoints"
            )
        )
    except AutonomousDevError as e:
        print(f"Caught formatted error:\n{e}")

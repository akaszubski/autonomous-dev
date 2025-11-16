#!/usr/bin/env python3
"""Comprehensive docstring templates following Google style.

This template file demonstrates Google-style docstrings for various
Python constructs (modules, classes, functions, methods, exceptions).

Design Pattern (see skills/library-design-patterns):
    - Google-style docstrings for all public APIs
    - Comprehensive documentation with Examples, Security, See sections
    - Type hints complemented by detailed Args/Returns documentation

Author: library-design-patterns skill
Version: 1.0.0

See:
    - skills/library-design-patterns/docs/docstring-standards.md
    - skills/documentation-guide: Comprehensive documentation standards
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Union, Any
from enum import Enum


# ============================================================================
# MODULE-LEVEL DOCSTRING (shown above)
# ============================================================================
# Required elements:
# - One-line summary
# - Detailed description
# - Design patterns used
# - Author, Date, Version
# - See references


# ============================================================================
# SIMPLE FUNCTION TEMPLATE
# ============================================================================

def simple_function(arg1: str, arg2: int) -> bool:
    """One-line summary describing what function does (imperative mood).

    Args:
        arg1: Description of first argument
        arg2: Description of second argument

    Returns:
        Description of return value

    Example:
        >>> result = simple_function("test", 42)
        >>> print(result)
        True
    """
    return True


# ============================================================================
# COMPLEX FUNCTION TEMPLATE (with all sections)
# ============================================================================

def complex_function(
    positional_arg: str,
    another_arg: int,
    *,
    keyword_arg: bool = True,
    optional_arg: Optional[str] = None,
    list_arg: Optional[List[str]] = None
) -> Dict[str, Any]:
    """One-line summary describing function purpose.

    Optional detailed description explaining behavior, algorithm,
    edge cases, and important implementation details. Can span
    multiple paragraphs if needed.

    This function demonstrates:
    - Progressive enhancement pattern
    - Security validation
    - Comprehensive error handling

    Args:
        positional_arg: Description of this argument including
            expected format, constraints, or special values
        another_arg: Description of second argument
            (range: 0-100 recommended)
        keyword_arg: Description of keyword-only argument
            (default: True)
        optional_arg: Description of optional argument. None means
            use default behavior (default: None)
        list_arg: Description of list argument. Empty list treated
            differently than None (default: None)

    Returns:
        Dictionary with the following keys:
            - 'status': Operation status ('success' or 'error')
            - 'data': Result data (list of strings)
            - 'count': Number of items processed (int)
            - 'errors': Error messages if any (list of strings)

    Raises:
        ValueError: If positional_arg is empty or another_arg is negative
        FileNotFoundError: If referenced file doesn't exist
        SecurityError: If path validation fails (CWE-22)
        TypeError: If arguments have wrong type

    Example:
        >>> # Basic usage
        >>> result = complex_function("input", 42)
        >>> print(result['status'])
        'success'
        >>>
        >>> # With optional arguments
        >>> result = complex_function(
        ...     "input",
        ...     10,
        ...     keyword_arg=False,
        ...     optional_arg="custom"
        ... )
        >>> print(result['count'])
        10

    Security:
        - CWE-22 Prevention: Path traversal validation
        - Input Validation: Type and range checks
        - Sanitization: Output sanitized for logging

    Note:
        This function has O(n) time complexity where n is the
        length of positional_arg. For large inputs (> 1000 chars),
        consider using batch processing.

        Thread-safety: This function is NOT thread-safe due to
        shared state modification. Use locks in multi-threaded code.

    See:
        - simple_function(): Related simpler version
        - skills/library-design-patterns: Design guidance
        - Issue #123: Historical context for this feature
    """
    if not positional_arg:
        raise ValueError("positional_arg cannot be empty")

    if another_arg < 0:
        raise ValueError("another_arg must be non-negative")

    # Implementation here
    return {
        'status': 'success',
        'data': [],
        'count': 0,
        'errors': []
    }


# ============================================================================
# CLASS TEMPLATE
# ============================================================================

class ExampleClass:
    """One-line summary of class purpose and responsibility.

    Detailed description of what this class represents, when to use it,
    and how it fits into the larger system. Explain the primary use
    cases and any important design decisions.

    This class demonstrates:
    - Two-tier design pattern integration
    - Progressive enhancement for validation
    - State management with persistence

    Attributes:
        public_attr: Description of public attribute including
            type and purpose
        another_attr: Description of another attribute
            (type: int, range: 0-100)

    Example:
        >>> # Basic usage
        >>> instance = ExampleClass("value", count=42)
        >>> instance.process()
        'result'
        >>>
        >>> # Advanced usage
        >>> instance = ExampleClass("value", count=10, validate=True)
        >>> result = instance.process(options={'mode': 'strict'})
        >>> print(result)
        'processed: 10 items'

    Security:
        - CWE-22 Prevention: Path validation in file operations
        - State Persistence: Atomic writes prevent corruption

    See:
        - RelatedClass: Similar functionality with different focus
        - skills/library-design-patterns: Class design guidance
    """

    def __init__(
        self,
        required_param: str,
        *,
        count: int = 0,
        validate: bool = True
    ) -> None:
        """Initialize ExampleClass with given parameters.

        Args:
            required_param: Description of required parameter
            count: Initial count value (default: 0)
            validate: Whether to validate inputs (default: True)

        Raises:
            ValueError: If required_param is empty
            TypeError: If count is not an integer
        """
        if not required_param:
            raise ValueError("required_param cannot be empty")

        self.public_attr = required_param
        self.another_attr = count
        self._private_attr = validate

    def process(self, options: Optional[Dict[str, Any]] = None) -> str:
        """Process data using current state.

        Args:
            options: Processing options (default: None uses defaults)
                Valid keys:
                    - 'mode': 'strict' or 'lenient' (default: 'strict')
                    - 'timeout': Maximum seconds (default: 30)

        Returns:
            Processing result as formatted string

        Raises:
            ValueError: If options contain invalid values
            RuntimeError: If processing fails

        Example:
            >>> instance = ExampleClass("data")
            >>> result = instance.process({'mode': 'strict'})
            >>> print(result)
            'processed: data'
        """
        # Implementation here
        return f"processed: {self.public_attr}"

    @property
    def status(self) -> str:
        """Get current processing status.

        Returns:
            Status string ('ready', 'processing', 'complete')
        """
        return 'ready'

    @staticmethod
    def validate_input(value: str) -> bool:
        """Validate input value against constraints.

        Args:
            value: Value to validate

        Returns:
            True if valid, False otherwise

        Example:
            >>> ExampleClass.validate_input("test")
            True
            >>> ExampleClass.validate_input("")
            False
        """
        return bool(value)

    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> 'ExampleClass':
        """Create instance from file.

        Args:
            filepath: Path to configuration file

        Returns:
            New ExampleClass instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format invalid

        Example:
            >>> instance = ExampleClass.from_file("config.json")
            >>> print(instance.public_attr)
            'loaded_value'
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Load and return instance
        return cls("loaded_value")

    def __str__(self) -> str:
        """Return string representation.

        Returns:
            Human-readable string representation
        """
        return f"ExampleClass(attr={self.public_attr}, count={self.another_attr})"

    def __repr__(self) -> str:
        """Return unambiguous string representation.

        Returns:
            String that could recreate this instance
        """
        return f"ExampleClass('{self.public_attr}', count={self.another_attr})"


# ============================================================================
# DATACLASS TEMPLATE
# ============================================================================

@dataclass
class ResultData:
    """Data structure for operation results.

    Attributes:
        success: Whether operation succeeded
        value: Result value (None if failed)
        error_message: Error message if failed (None if succeeded)
        metadata: Additional metadata (default: empty dict)
    """
    success: bool
    value: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Validate dataclass after initialization.

        Raises:
            ValueError: If both value and error_message are set
        """
        if self.value and self.error_message:
            raise ValueError("Cannot have both value and error_message")

        if self.metadata is None:
            self.metadata = {}


# ============================================================================
# EXCEPTION TEMPLATE
# ============================================================================

class CustomError(Exception):
    """Raised when specific error condition occurs.

    This exception indicates [explain what this error means and
    when it's raised]. It should be caught and handled by callers
    who want to [explain recovery strategy].

    Attributes:
        message: Error message
        context: Additional context about the error (dict)

    Example:
        >>> try:
        ...     raise CustomError("Something failed", context={'file': 'test.txt'})
        ... except CustomError as e:
        ...     print(e.message)
        ...     print(e.context)
        'Something failed'
        {'file': 'test.txt'}
    """

    def __init__(self, message: str, *, context: Optional[Dict[str, Any]] = None):
        """Initialize exception with message and context.

        Args:
            message: Human-readable error message
            context: Additional error context (default: None)
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}


# ============================================================================
# ENUM TEMPLATE
# ============================================================================

class ProcessingMode(Enum):
    """Processing mode options.

    Attributes:
        STRICT: Strict validation, fail on any error
        LENIENT: Lenient validation, skip invalid items
        AUTO: Automatic mode selection based on input
    """
    STRICT = "strict"
    LENIENT = "lenient"
    AUTO = "auto"


# ============================================================================
# GENERATOR FUNCTION TEMPLATE
# ============================================================================

def generate_items(source: str, *, batch_size: int = 100):
    """Generate items from source in batches.

    This is a generator function that yields items lazily,
    which is memory-efficient for large datasets.

    Args:
        source: Source identifier
        batch_size: Number of items per batch (default: 100)

    Yields:
        Individual items from source

    Raises:
        ValueError: If source is invalid
        RuntimeError: If generation fails

    Example:
        >>> for item in generate_items("source1", batch_size=50):
        ...     print(item)
        'item1'
        'item2'
        ...

    Note:
        This function uses lazy evaluation. Items are generated
        on-demand, so the entire dataset is never loaded into memory.
    """
    # Implementation here
    yield "item"


# ============================================================================
# ASYNC FUNCTION TEMPLATE
# ============================================================================

async def async_operation(param: str) -> Dict[str, Any]:
    """Perform asynchronous operation.

    Args:
        param: Operation parameter

    Returns:
        Operation result dictionary

    Raises:
        asyncio.TimeoutError: If operation times out
        RuntimeError: If operation fails

    Example:
        >>> import asyncio
        >>> result = asyncio.run(async_operation("test"))
        >>> print(result['status'])
        'success'

    Note:
        This function is async and must be awaited or run
        with asyncio.run() or equivalent.
    """
    # Async implementation here
    return {'status': 'success'}


# ============================================================================
# DECORATOR TEMPLATE
# ============================================================================

def retry_on_failure(max_attempts: int = 3):
    """Decorator to retry function on failure.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)

    Returns:
        Decorated function

    Example:
        >>> @retry_on_failure(max_attempts=5)
        ... def flaky_function():
        ...     # May fail sometimes
        ...     return "result"
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
            return None
        return wrapper
    return decorator

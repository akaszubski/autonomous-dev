"""Example module demonstrating Google-style docstrings.

This module shows how to properly document Python code using
Google-style docstrings for functions and classes.
"""

from typing import Optional, Dict, List


def simple_function(name: str, count: int = 1) -> str:
    """Return a greeting message repeated count times.

    Args:
        name: Name to include in greeting
        count: Number of times to repeat (default: 1)

    Returns:
        Greeting message string

    Example:
        >>> simple_function("World", count=2)
        'Hello, World! Hello, World! '
    """
    return f"Hello, {name}! " * count


def complex_function(
    data: List[Dict[str, any]],
    validate: bool = True,
    *,
    max_items: Optional[int] = None
) -> Dict[str, any]:
    """Process a list of data items with optional validation.

    This function demonstrates how to document complex parameters
    and return types with nested structures.

    Args:
        data: List of dictionaries containing item data with keys:
            - 'id': Unique identifier (int)
            - 'value': Item value (str)
            - 'metadata': Optional metadata (dict)
        validate: Whether to validate items before processing (default: True)
        max_items: Maximum number of items to process, None for unlimited

    Returns:
        Dictionary containing processing results:
            - 'processed': Number of items processed (int)
            - 'errors': List of error messages (List[str])
            - 'results': Processed items (List[Dict])

    Raises:
        ValueError: If data is empty and validate is True
        TypeError: If data contains non-dict items

    Example:
        >>> data = [{'id': 1, 'value': 'test'}]
        >>> result = complex_function(data, max_items=10)
        >>> print(result['processed'])
        1
    """
    if validate and not data:
        raise ValueError("Data cannot be empty when validation is enabled")

    if not all(isinstance(item, dict) for item in data):
        raise TypeError("All items in data must be dictionaries")

    # Process items
    items_to_process = data[:max_items] if max_items else data
    results = []
    errors = []

    for item in items_to_process:
        try:
            # Processing logic here
            results.append(item)
        except Exception as e:
            errors.append(str(e))

    return {
        'processed': len(results),
        'errors': errors,
        'results': results
    }


class ExampleClass:
    """A class demonstrating proper docstring documentation.

    This class shows how to document class attributes, methods,
    and properties with Google-style docstrings.

    Attributes:
        name: The name associated with this instance
        value: Current value stored in the instance
        _internal: Private attribute (not documented for users)

    Example:
        >>> obj = ExampleClass("test", value=42)
        >>> obj.increment(10)
        >>> print(obj.value)
        52
    """

    def __init__(self, name: str, value: int = 0):
        """Initialize ExampleClass with name and optional value.

        Args:
            name: Name for this instance
            value: Initial value (default: 0)
        """
        self.name = name
        self.value = value
        self._internal = None

    def increment(self, amount: int = 1) -> int:
        """Increment the value by specified amount.

        Args:
            amount: Amount to add to value (default: 1)

        Returns:
            New value after increment

        Example:
            >>> obj = ExampleClass("test", value=10)
            >>> obj.increment(5)
            15
        """
        self.value += amount
        return self.value

    @property
    def display_name(self) -> str:
        """Get formatted display name.

        Returns:
            Name formatted with current value

        Example:
            >>> obj = ExampleClass("test", value=42)
            >>> print(obj.display_name)
            'test (42)'
        """
        return f"{self.name} ({self.value})"

    def validate_and_process(self, data: Dict[str, any]) -> bool:
        """Validate and process data, updating internal state.

        Args:
            data: Dictionary containing:
                - 'action': Action to perform (str)
                - 'params': Parameters for action (dict)

        Returns:
            True if processing succeeded, False otherwise

        Raises:
            KeyError: If required keys missing from data
            ValueError: If action is not supported

        Example:
            >>> obj = ExampleClass("processor")
            >>> obj.validate_and_process({'action': 'increment', 'params': {'amount': 5}})
            True
        """
        if 'action' not in data or 'params' not in data:
            raise KeyError("Data must contain 'action' and 'params' keys")

        action = data['action']
        if action not in ['increment', 'reset']:
            raise ValueError(f"Unsupported action: {action}")

        # Process based on action
        if action == 'increment':
            self.increment(data['params'].get('amount', 1))
        elif action == 'reset':
            self.value = 0

        return True


# Module-level constants should also be documented
DEFAULT_TIMEOUT = 30  # Timeout in seconds for operations
MAX_RETRIES = 3  # Maximum number of retry attempts

#!/usr/bin/env python3
"""Retry decorator template with exponential backoff.

See: skills/api-integration-patterns/docs/retry-logic.md
"""

import time
from typing import Callable, TypeVar
from functools import wraps

T = TypeVar('T')


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
):
    """Decorator to retry function with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)

    Returns:
        Decorated function

    Example:
        >>> @retry_with_backoff(max_attempts=5, base_delay=2.0)
        ... def fetch_data():
        ...     return api_call()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        # Exponential backoff: 1s, 2s, 4s, 8s, ...
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        print(f"Attempt {attempt + 1} failed: {e}")
                        print(f"Retrying in {delay}s...")
                        time.sleep(delay)

            # All attempts failed
            raise last_exception

        return wrapper
    return decorator


# Example usage
if __name__ == "__main__":
    attempt_count = 0

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def flaky_function():
        """Function that fails first 2 times."""
        global attempt_count
        attempt_count += 1
        print(f"Attempt {attempt_count}")

        if attempt_count < 3:
            raise RuntimeError("Simulated failure")

        return "Success!"

    result = flaky_function()
    print(f"Result: {result}")

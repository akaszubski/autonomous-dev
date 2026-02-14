# Docstring Standards

## Google Style Docstrings

All Python code should use Google-style docstrings for consistency and readability.

## Required Sections

### For Functions and Methods

```python
def function_name(arg1: str, arg2: int = 10) -> dict:
    """Brief one-line description.

    More detailed description if needed. Explain what the function does,
    not how it does it (that's for code comments).

    Args:
        arg1: Description of first argument
        arg2: Description of second argument (default: 10)

    Returns:
        Dictionary containing result with keys:
            - 'success': Boolean indicating success
            - 'data': Processed data

    Raises:
        ValueError: If arg1 is empty string
        TypeError: If arg2 is not an integer

    Example:
        >>> result = function_name("test", arg2=20)
        >>> print(result['success'])
        True
    """
```

### For Classes

```python
class ClassName:
    """Brief one-line description of the class.

    More detailed description explaining the class's purpose and usage.

    Attributes:
        attribute1: Description of attribute1
        attribute2: Description of attribute2

    Example:
        >>> obj = ClassName(param="value")
        >>> obj.method()
        'result'
    """
```

## Section Guidelines

### Args Section

- List each parameter on its own line
- Include type hints in function signature (not in docstring)
- Describe what the parameter is used for
- Note default values in description

### Returns Section

- Describe the return type and structure
- For complex types (dict, tuple), describe the structure
- Use nested bullets for dict keys or tuple elements

### Raises Section

- List all exceptions that can be raised
- Explain the conditions that cause each exception
- Include custom exceptions

### Example Section

- Provide realistic, working examples
- Use doctest format when possible
- Show common usage patterns
- Keep examples simple and focused

## Best Practices

- **First line**: Brief summary (fits on one line)
- **Blank line**: After first line before detailed description
- **Present tense**: "Returns a list" not "Will return a list"
- **Be specific**: Explain what, not how
- **Code examples**: Make them copy-paste ready
- **Type hints**: Use function signature, not docstring

## Anti-Patterns to Avoid

- ❌ Redundant information (docstring just repeats function name)
- ❌ Implementation details (save for code comments)
- ❌ Outdated examples that don't work
- ❌ Missing Args/Returns sections
- ❌ Vague descriptions ("Does stuff")

# Documentation Guide - Detailed Guide

## Detailed Usage

### Step 1: Setup

```python
from [project_name].feature import Feature

feature = Feature(param="value")
```

### Step 2: Execute

```python
result = feature.execute()
```

## Common Patterns

### Pattern 1: Simple Use Case
```python
# Example code
```

### Pattern 2: Advanced Use Case
```python
# Example code
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `param1` | str | "default" | Description |
| `param2` | int | 100 | Description |

## Troubleshooting

### Issue: Error Message
**Symptoms**: What you see
**Cause**: Why it happens
**Solution**:
```python
# Fix code
```

## See Also

- [Related Guide](./related.md)
- [API Reference](../api/module.md)
```

## API Documentation Template

```markdown
# Module Name

Brief module description.

## Classes

### `ClassName`

Brief class description.

```python
from [project_name].module import ClassName

instance = ClassName(param="value")
```

**Parameters:**
- `param1` (str): Description of parameter
- `param2` (int, optional): Description. Default: 100
- `param3` (bool, optional): Description. Default: False

**Attributes:**
- `attribute1` (str): Description
- `attribute2` (int): Description

**Example:**
```python
instance = ClassName(param1="test")
result = instance.method()
print(result)
```

**Methods:**

#### `method_name(arg1, arg2=default)`

Description of what method does.

**Parameters:**
- `arg1` (type): Description
- `arg2` (type, optional): Description. Default: value

**Returns:**
- `ReturnType`: Description of return value

**Raises:**
- `ValueError`: When X condition
- `TypeError`: When Y condition

**Example:**
```python
result = instance.method_name("value", arg2=True)
assert result.success
```

## Functions

### `function_name(param1, param2)`

[Same structure as methods]
```

## Example Code Template

```python
#!/usr/bin/env python3
"""
Title: Brief description

This example demonstrates:
- Feature 1
- Feature 2
- Feature 3

Requirements:
- pip install [project_name]
- ANTHROPIC_API_KEY in .env

Usage:
    python examples/example_name.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from [project_name] import Feature


def main():
    """Main example function."""
    # Load environment
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("Add to .env file: ANTHROPIC_API_KEY=sk-ant-...")
        print("See: docs/guides/setup.md")
        return 1

    # Step 1: Initialize
    print("Step 1: Initializing feature...")
    feature = Feature(api_key=api_key)

    # Step 2: Execute
    print("Step 2: Running feature...")
    result = feature.run()

    # Step 3: Show results
    print(f"\nResults:")
    print(f"  Success: {result.success}")
    print(f"  Data: {result.data}")

    return 0


if __name__ == "__main__":
    exit(main())
```

## Architecture Decision Records (ADRs)

When making significant architectural decisions, create ADR in `docs/architecture/decisions/`:

```markdown
# ADR-XXX: Title of Decision

## Status

---
description: Sync API documentation only - extract docstrings and update API docs
---

# Sync API Documentation

**Update API reference docs from code docstrings**

---

## Usage

```bash
/sync-docs-api
```

**Scope**: API documentation only
**Time**: 2-3 minutes
**Agent**: doc-master (Haiku)

---

## What This Does

Syncs API documentation with code:
1. Extract docstrings from source code
2. Parse function signatures and parameters
3. Update API reference documentation
4. Sync code examples
5. Validate cross-references

**Only updates API docs** - doesn't organize files or update CHANGELOG.

---

## Expected Output

```
Syncing API Documentation...

Scanning source code...
  ✅ Found 45 documented functions
  ✅ Found 12 documented classes
  ✅ Found 3 documented modules

Analyzing changes...
  ⚠️  12 API docs need updates

Updating API documentation...

docs/api/auth.md:
  ✅ Updated generate_token()
  ✅ Updated validate_token()
  ✅ Added refresh_token() (new)

docs/api/export.md:
  ✅ Updated export_to_csv()
  ✅ Synced code example

docs/api/utils.md:
  ✅ Updated parse_input()
  ✅ Updated format_output()

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Updated: 12 API doc entries
Added: 1 new function
Synced: 3 code examples
Time: 2m 15s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## What Gets Synced

**Function Documentation**:
- Function signature
- Parameters (type, description, default)
- Return type and description
- Raises (exceptions)
- Examples

**Class Documentation**:
- Class description
- Methods
- Attributes
- Usage examples

**Module Documentation**:
- Module overview
- Exported functions
- Usage patterns

---

## Example Sync

**Code** (`src/auth.py`):
```python
def generate_token(user_id: int, expires_in: int = 3600) -> str:
    """Generate JWT token for user.

    Args:
        user_id: User ID to encode in token
        expires_in: Token expiration in seconds (default: 1 hour)

    Returns:
        JWT token string

    Raises:
        ValueError: If user_id is invalid

    Example:
        >>> token = generate_token(user_id=42)
        >>> print(token)
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    """
```

**API Doc** (`docs/api/auth.md`):
````markdown
## `generate_token(user_id, expires_in=3600)`

Generate JWT token for user.

### Parameters

- `user_id` (int): User ID to encode in token
- `expires_in` (int, optional): Token expiration in seconds. Default: 3600 (1 hour)

### Returns

- `str`: JWT token string

### Raises

- `ValueError`: If user_id is invalid

### Example

```python
token = generate_token(user_id=42)
print(token)
# 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```
````

---

## When to Use

- ✅ After API changes
- ✅ After updating docstrings
- ✅ Before code review
- ✅ When API docs outdated

---

## Configuration

**Docstring style** (auto-detected):
- Google style (default)
- NumPy style
- Sphinx style

**API doc location**:
- `docs/api/` (default)
- Configured in PROJECT.md

---

## Related Commands

- `/sync-docs` - Sync all documentation
- `/sync-docs-changelog` - CHANGELOG only
- `/sync-docs-organize` - File organization only
- `/sync-docs-auto` - Auto-detect changes

---

**Use this after API changes to keep documentation synchronized with code.**

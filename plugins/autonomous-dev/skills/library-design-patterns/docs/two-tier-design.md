# Two-Tier Design Pattern

**Pattern Type**: Architectural
**Skill**: library-design-patterns
**Version**: 1.0.0

---

## Overview

Two-tier design separates core business logic (Tier 1) from user interface/CLI (Tier 2) to maximize reusability, testability, and maintainability.

**Core Principle**: Business logic should be usable from multiple contexts (CLI, API, tests, other modules) without modification.

---

## Architecture

```
┌─────────────────────────────────────────┐
│         Tier 2: CLI Interface           │
│  (update_plugin.py, health_check.py)    │
│                                          │
│  - Argument parsing (argparse)          │
│  - User interaction (input/output)      │
│  - Error formatting for CLI             │
│  - Exit codes and signals               │
└──────────────┬──────────────────────────┘
               │ imports
               ▼
┌─────────────────────────────────────────┐
│       Tier 1: Core Library              │
│  (plugin_updater.py, health_check lib)  │
│                                          │
│  - Pure business logic                  │
│  - No I/O assumptions                   │
│  - Returns structured data              │
│  - Raises semantic exceptions           │
└─────────────────────────────────────────┘
```

---

## Tier 1: Core Library

### Characteristics

- **Pure Logic**: No assumptions about how results will be used
- **Structured Returns**: Return dataclasses, NamedTuples, or dicts
- **Semantic Exceptions**: Raise exceptions with clear meaning
- **No I/O**: Don't print, don't read stdin, don't assume terminal
- **Testable**: Easy to unit test with pure assertions

### Example

```python
# plugin_updater.py (Tier 1: Core Library)

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class UpdateResult:
    """Result of plugin update operation."""
    success: bool
    version_from: str
    version_to: str
    backup_path: Optional[Path]
    error_message: Optional[str] = None

class PluginUpdateError(Exception):
    """Raised when plugin update fails."""
    pass

def update_plugin(
    plugin_name: str,
    *,
    backup: bool = True,
    dry_run: bool = False
) -> UpdateResult:
    """Update plugin to latest version.

    This is core business logic - no CLI assumptions.

    Args:
        plugin_name: Name of plugin to update
        backup: Whether to create backup before update
        dry_run: Whether to simulate update without changes

    Returns:
        UpdateResult with operation details

    Raises:
        PluginUpdateError: If update fails
        FileNotFoundError: If plugin not found
    """
    # Pure business logic
    current_version = _detect_version(plugin_name)
    latest_version = _fetch_latest_version(plugin_name)

    if current_version == latest_version:
        return UpdateResult(
            success=True,
            version_from=current_version,
            version_to=latest_version,
            backup_path=None
        )

    if dry_run:
        return UpdateResult(
            success=True,
            version_from=current_version,
            version_to=latest_version,
            backup_path=None
        )

    backup_path = None
    if backup:
        backup_path = _create_backup(plugin_name)

    try:
        _perform_update(plugin_name, latest_version)
        return UpdateResult(
            success=True,
            version_from=current_version,
            version_to=latest_version,
            backup_path=backup_path
        )
    except Exception as e:
        raise PluginUpdateError(f"Update failed: {e}")
```

---

## Tier 2: CLI Interface

### Characteristics

- **Thin Wrapper**: Minimal logic, delegates to Tier 1
- **Argument Parsing**: Uses argparse for CLI options
- **User Interaction**: Handles input(), confirmation prompts
- **Output Formatting**: Pretty-prints results for terminal
- **Exit Codes**: Returns 0 for success, non-zero for errors

### Example

```python
# update_plugin.py (Tier 2: CLI Interface)

import argparse
import sys
from pathlib import Path

from plugins.autonomous_dev.lib.plugin_updater import (
    update_plugin,
    PluginUpdateError
)

def main():
    """CLI interface for plugin updates."""
    parser = argparse.ArgumentParser(
        description="Update autonomous-dev plugin to latest version"
    )
    parser.add_argument(
        "plugin_name",
        help="Name of plugin to update"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup before update"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate update without making changes"
    )

    args = parser.parse_args()

    # User interaction (CLI-specific)
    if not args.dry_run and not args.no_backup:
        confirm = input(f"Update {args.plugin_name}? Backup will be created. [y/N]: ")
        if confirm.lower() != 'y':
            print("Update cancelled")
            return 0

    try:
        # Delegate to core library
        result = update_plugin(
            args.plugin_name,
            backup=not args.no_backup,
            dry_run=args.dry_run
        )

        # Format output for CLI
        if result.success:
            print(f"✅ Updated {args.plugin_name}")
            print(f"   {result.version_from} → {result.version_to}")
            if result.backup_path:
                print(f"   Backup: {result.backup_path}")
            return 0
        else:
            print(f"❌ Update failed: {result.error_message}")
            return 1

    except PluginUpdateError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"❌ Plugin not found: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
```

---

## Benefits

### 1. Reusability

Core library can be used in multiple contexts:

```python
# From CLI
$ python update_plugin.py autonomous-dev

# From Python code
from plugins.autonomous_dev.lib.plugin_updater import update_plugin
result = update_plugin("autonomous-dev")

# From tests
def test_update_plugin():
    result = update_plugin("test-plugin", dry_run=True)
    assert result.success

# From another agent/workflow
result = orchestrator.update_plugin("autonomous-dev", backup=True)
```

### 2. Testability

Pure business logic is easy to test:

```python
# test_plugin_updater.py

def test_update_plugin_same_version():
    """Test update when already at latest version."""
    result = update_plugin("test-plugin")
    assert result.success
    assert result.version_from == result.version_to

def test_update_plugin_dry_run():
    """Test dry run doesn't modify files."""
    result = update_plugin("test-plugin", dry_run=True)
    assert result.success
    assert result.backup_path is None

def test_update_plugin_with_backup():
    """Test backup creation during update."""
    result = update_plugin("test-plugin", backup=True)
    assert result.backup_path.exists()
```

### 3. Maintainability

Changes to one tier don't affect the other:

- **CLI changes**: Can switch from argparse to click without touching core logic
- **Logic changes**: Can improve algorithm without breaking CLI
- **Output format**: Can add JSON output mode without duplicating logic

### 4. Separation of Concerns

Each tier has clear responsibilities:

- **Tier 1**: "What to do" (business logic)
- **Tier 2**: "How to present it" (user interface)

---

## When to Use

✅ **Use two-tier design when**:
- Library might be used both programmatically and from CLI
- Complex business logic needs thorough testing
- Multiple interfaces might consume same logic (CLI, API, web)
- Logic might be reused in different contexts

❌ **Skip two-tier design when**:
- Script is truly one-off and will never be reused
- Logic is trivial (< 20 lines)
- Only ever used from command line

---

## Migration Guide

### Converting Single-Tier to Two-Tier

**Before** (single file with mixed concerns):
```python
# old_script.py
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    args = parser.parse_args()

    # Business logic mixed with CLI
    data = read_file(args.file)
    result = process(data)
    print(f"Processed: {result}")

if __name__ == "__main__":
    main()
```

**After** (two-tier separation):

```python
# core_library.py (Tier 1)
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ProcessResult:
    success: bool
    items_processed: int

def process_file(filepath: Path) -> ProcessResult:
    """Process file (pure business logic)."""
    data = read_file(filepath)
    result = process(data)
    return ProcessResult(success=True, items_processed=len(result))

# cli_script.py (Tier 2)
import argparse
from core_library import process_file

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    args = parser.parse_args()

    result = process_file(Path(args.file))
    print(f"✅ Processed {result.items_processed} items")

if __name__ == "__main__":
    main()
```

---

## Real-World Examples

### autonomous-dev Plugin

| Tier 1 (Core Library) | Tier 2 (CLI Interface) | Use Case |
|----------------------|------------------------|----------|
| plugin_updater.py | update_plugin.py | Plugin update logic |
| security_utils.py | (imported by libraries) | Path validation |
| batch_state_manager.py | (imported by /batch-implement) | State management |

### Design Principles

1. **Core library** (Tier 1) handles business logic
2. **CLI script** (Tier 2) provides command-line interface
3. CLI imports and delegates to core library
4. Core library never imports CLI (one-way dependency)

---

## Anti-Patterns

### ❌ Mixing Tiers

```python
# Bad: Business logic mixed with CLI
def update_plugin(plugin_name: str):
    confirm = input("Continue? [y/N]: ")  # CLI in business logic!
    if confirm != 'y':
        return

    # ... business logic ...
    print(f"Updated {plugin_name}")  # Output in business logic!
```

### ✅ Separating Tiers

```python
# Good: Core library
def update_plugin(plugin_name: str) -> UpdateResult:
    # Pure business logic, no CLI assumptions
    return UpdateResult(success=True)

# Good: CLI wrapper
def main():
    confirm = input("Continue? [y/N]: ")
    if confirm == 'y':
        result = update_plugin("plugin")
        print(f"Updated {result.version_to}")
```

---

## Checklist

When implementing two-tier design:

- [ ] Core library has no print() statements
- [ ] Core library has no input() calls
- [ ] Core library returns structured data (dataclass, NamedTuple, dict)
- [ ] Core library raises semantic exceptions
- [ ] CLI script is thin wrapper (< 50 lines)
- [ ] CLI script handles argparse
- [ ] CLI script formats output for terminal
- [ ] CLI script converts exceptions to exit codes
- [ ] Core library is 100% unit tested
- [ ] CLI script is integration tested (if needed)

---

## References

- **Template**: `templates/library-template.py`
- **Example**: `examples/two-tier-example.py`
- **Related Patterns**: Progressive enhancement, non-blocking enhancements
- **Cross-Reference**: error-handling-patterns skill, testing-guide skill

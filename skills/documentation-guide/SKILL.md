---
name: documentation-guide
type: knowledge
description: Documentation standards and automation. Use when updating docs, writing guides, or synchronizing code with documentation.
keywords: documentation, docs, readme, changelog, guides, api docs
---

# Documentation Guide Skill

Documentation standards and automation for [PROJECT_NAME] project.

## When This Activates
- Code changes requiring doc updates
- New features added
- API changes
- Writing/updating documentation
- Keywords: "docs", "documentation", "readme", "changelog", "guide"

## Documentation Structure

```
docs/
├── CLAUDE.md                    # Docs-specific automation (create this)
├── COMPLETE_SYSTEM_GUIDE.md     # Master guide
├── QUICKSTART.md                # Getting started
├── HOW_TO_MAINTAIN_ALIGNMENT.md # Maintenance
├── features/                    # Feature-specific
│   ├── model-download.md
│   ├── training-methods.md
│   └── data-preparation.md
├── guides/                      # How-to guides
│   ├── installation.md
│   ├── configuration.md
│   └── troubleshooting.md
├── api/                         # API reference
│   ├── core.md
│   ├── backends.md
│   └── cli.md
├── examples/                    # Code examples
│   ├── basic-training.py
│   └── advanced-usage.py
└── architecture/                # ADRs
    ├── overview.md
    └── decisions/
        ├── 001-[framework]-backend.md
        └── 002-multi-arch.md

README.md                        # Root readme
CHANGELOG.md                     # Version history
```

## Auto-Update Rules

### When Code Changes → Update Docs

| Change Type | Documentation Updates |
|-------------|----------------------|
| New feature | README.md, docs/guides/, CHANGELOG.md, examples/ |
| API change | docs/api/, CHANGELOG.md |
| Bug fix | CHANGELOG.md, (optional) docs/guides/troubleshooting.md |
| Breaking change | CHANGELOG.md, README.md, docs/guides/, migration guide |
| New dependency | README.md (install), requirements.txt |

### CHANGELOG.md (Always Update)

```markdown
# Changelog

All notable changes documented here.
Format: [Keep a Changelog](https://keepachangelog.com/)
Versioning: [Semantic Versioning](https://semver.org/)

## [Unreleased]

### Added
- New feature X with Y capability
- CLI flag `--new-option` for Z

### Changed
- Updated API: `Trainer` now accepts `gradient_checkpointing` param
- [FRAMEWORK] dependency bumped to 0.20.0

### Fixed
- Model cache invalidation bug (#42)
- Memory leak in long training runs

### Deprecated
- `old_function()` - Use `new_function()` instead

### Removed
- Legacy training method (use LoRA instead)

### Security
- Updated dependencies to patch CVE-2024-XXXX

## [3.0.0] - 2024-01-15

### Added
- Complete rebranding to [PROJECT_NAME]
- Multi-architecture support

[Previous versions...]
```

## Writing Standards

### Tone & Style
- **Clear and concise**: Short sentences, active voice
- **User-focused**: Write "you", not "the user"
- **Practical**: Every concept has a code example
- **Scannable**: Use headers, lists, code blocks
- **Linked**: Reference related docs

### Example Structure
```markdown
# Feature Name

Brief one-sentence description.

## What It Does

1-2 paragraphs explaining the feature and its benefits.

## Quick Example

```python
# Minimal working example
from [project_name] import Feature

result = Feature().run()
print(result)
```

## Prerequisites

- Python 3.11+
- API key set in .env
- [PROJECT_NAME] installed: `pip install [project_name]`

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
**Proposed** | Accepted | Deprecated | Superseded by ADR-YYY

## Context

What problem are we solving? What are the constraints?

- Constraint 1
- Constraint 2
- Requirement 1

## Decision

We will [decision statement].

### Approach

Detailed explanation of the approach:

1. Step 1
2. Step 2
3. Step 3

## Consequences

### Positive

- ✅ Benefit 1: Description
- ✅ Benefit 2: Description

### Negative

- ⚠️ Tradeoff 1: Description
- ⚠️ Tradeoff 2: Description

### Neutral

- ℹ️ Change 1: Description

## Alternatives Considered

### Alternative 1: [Name]

**Description**: What it is
**Pros**: Benefits
**Cons**: Drawbacks
**Why rejected**: Reason

### Alternative 2: [Name]

[Same structure]

## References

- [External Resource](https://example.com)
- [Internal Doc](../guides/related.md)
```

## README.md Updates

### Features Section
When adding new feature:

```markdown
## Features

- **Model Discovery**: Browse 2,984+ [FRAMEWORK] models
- **Data Curator**: Extract from 10 content types
- **Adaptive Tuner**: 5 training methods (LoRA, DPO, etc)
- **NEW FEATURE**: Brief description  # ← Add here
```

### Installation Section
When adding dependencies:

```markdown
## Installation

```bash
pip install [project_name]

# For new feature (optional)
pip install [project_name][feature]
```
```

## Link Validation

### Check Internal Links
```python
import re
from pathlib import Path


def find_broken_links(docs_dir: Path) -> list[str]:
    """Find broken internal markdown links."""
    broken = []

    for md_file in docs_dir.rglob("*.md"):
        content = md_file.read_text()

        # Find markdown links: [text](link)
        links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', content)

        for text, link in links:
            # Skip external
            if link.startswith("http"):
                continue

            # Resolve relative path
            target = (md_file.parent / link).resolve()

            if not target.exists():
                broken.append(f"{md_file}:{text} → {link}")

    return broken
```

## Documentation Checklist

Before marking docs complete:
- [ ] CHANGELOG.md updated
- [ ] README.md updated (if public API change)
- [ ] API docs updated (if function signatures changed)
- [ ] Guides created/updated for new features
- [ ] Code examples working and tested
- [ ] No broken internal links
- [ ] Markdown properly formatted
- [ ] Spelling checked
- [ ] All code examples have dependencies listed

## Auto-Generation Scripts

### Extract Docstrings → API Docs
```python
import ast
from pathlib import Path


def extract_api_docs(source_file: Path) -> dict:
    """Extract API documentation from Python file."""
    with open(source_file) as f:
        tree = ast.parse(f.read())

    docs = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node)
            methods = {}

            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    if not item.name.startswith("_"):  # Skip private
                        methods[item.name] = ast.get_docstring(item)

            docs[node.name] = {
                "docstring": class_doc,
                "methods": methods
            }

    return docs
```

## Quick Reference

### When to Update Which Docs

| You Changed | Update |
|-------------|--------|
| Added function | API docs, CHANGELOG |
| Fixed bug | CHANGELOG, maybe troubleshooting |
| New feature | README, guides, examples, API docs, CHANGELOG |
| Breaking change | CHANGELOG, migration guide, all affected docs |
| Config option | Configuration guide, CHANGELOG |
| Dependencies | README (install), CHANGELOG |
| Architecture | ADR, architecture docs |

## Key Takeaways

1. **Always update CHANGELOG** - Every PR
2. **Keep README current** - First thing users see
3. **Auto-sync API docs** - Extract from docstrings
4. **Test examples** - Must work as written
5. **Validate links** - No 404s
6. **User-focused** - "How to" not "what is"
7. **Code examples** - Every concept
8. **ADRs for architecture** - Document decisions

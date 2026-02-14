# Documentation Guide - Detailed Guide

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

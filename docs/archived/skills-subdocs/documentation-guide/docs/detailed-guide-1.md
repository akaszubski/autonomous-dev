# Documentation Guide - Detailed Guide

## Documentation Files

This skill includes specialized documentation files for specific patterns:

- **parity-validation.md**: Documentation parity validation checklist (version consistency, count accuracy, cross-references)
- **changelog-format.md**: Keep a Changelog format and semantic versioning standards
- **readme-structure.md**: README structure standards and 600-line conciseness limit
- **docstring-standards.md**: Google-style docstring conventions for Python code

## Templates

Ready-to-use templates for common documentation needs:

- **docstring-template.py**: Python file with example Google-style docstrings (functions, classes, methods)
- **readme-template.md**: Standard README structure with all recommended sections
- **changelog-template.md**: Keep a Changelog compliant template with semantic versioning

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

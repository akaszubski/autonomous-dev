---
name: documentation-guide
version: 1.0.0
type: knowledge
description: Enforcement skill for consistent documentation standards
keywords: [docs, documentation, changelog, readme, docstring, adr]
auto_activate: true
allowed-tools: [Read, Write, Edit, Grep, Glob]
---

# Documentation Guide Enforcement Skill

Ensures all documentation is consistent, current, and complete. Used by the doc-master agent.

## Keep a Changelog Format

All CHANGELOG entries MUST follow [Keep a Changelog](https://keepachangelog.com/) format.

### Categories (in this order)
- **Added** — new features
- **Changed** — changes to existing functionality
- **Deprecated** — soon-to-be removed features
- **Removed** — removed features
- **Fixed** — bug fixes
- **Security** — vulnerability fixes

### Structure
```markdown
# Changelog

## [Unreleased]

### Added
- New authentication module (#123)

### Fixed
- Token expiry off-by-one error (#124)

## [1.2.0] - 2026-02-15

### Added
- Batch processing support (#100)
```

The `[Unreleased]` section MUST always exist at the top for accumulating changes.

---

## README Required Sections

Every README.md MUST contain these sections in order:

1. **Overview** — 1-2 sentence project description
2. **Installation** — How to install/set up
3. **Usage / Quick Start** — Minimal working example
4. **Commands Table** — Available commands with descriptions
5. **Configuration** — Config files, env vars, options
6. **Contributing** — How to contribute, link to CONTRIBUTING.md

---

## Docstring Format: Google Style

All public functions MUST have Google-style docstrings.

```python
def process_data(
    data: List[Dict],
    *,
    validate: bool = True,
) -> ProcessResult:
    """Process input data with optional validation.

    Args:
        data: Input records as list of dicts with 'id' and 'content' keys.
        validate: Whether to validate input before processing.

    Returns:
        ProcessResult with metrics and processed items.

    Raises:
        ValueError: If data is empty or missing required keys.
    """
```

Include `Args`, `Returns`, and `Raises` for every public function. Omit sections only if truly not applicable (e.g., no exceptions raised).

---

## HARD GATE: Sync Rules

Documentation MUST stay in sync with code at all times.

**FORBIDDEN**:
- Updating code without updating corresponding docs
- Hardcoded component counts (e.g., "17 agents") — use dynamic discovery or verify against filesystem
- Undocumented public APIs — every public function needs a docstring
- Stale cross-references — links to files/sections that no longer exist
- CHANGELOG entries without issue/PR numbers
- Version dates that do not match actual release dates

**REQUIRED**:
- CHANGELOG entry for every user-visible change
- Version date updated when changes are made
- Component counts verified against filesystem before committing
- Cross-references validated (all linked files exist)
- README updated when commands or configuration change
- Docstrings updated when function signatures change

---

## When to Update Which Docs

| Change Type | README | CHANGELOG | Docstrings | ADR |
|------------|--------|-----------|------------|-----|
| API change | Yes | Yes | Yes | Maybe |
| New feature | Yes | Yes | Yes | Maybe |
| Bug fix | No | Yes | No | No |
| Refactor (no behavior change) | No | No | Maybe | Maybe |
| Architecture decision | No | No | No | Yes |
| Config change | Yes | Yes | No | No |
| Deprecation | Yes | Yes | Yes | Maybe |

---

## ADR Template

For major architectural decisions, create an ADR (Architecture Decision Record).

```markdown
# ADR-NNN: [Title]

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-NNN

## Context
What is the issue or decision we need to make?

## Decision
What did we decide and why?

## Consequences
What are the positive and negative outcomes?

## Alternatives Considered
What other options were evaluated and why were they rejected?
```

Store ADRs in `docs/adr/` directory, numbered sequentially.

---

## Anti-Patterns

### BAD: Hardcoded counts
```markdown
This project has 17 agents and 40 skills.
```
These numbers drift immediately. Verify against filesystem or use dynamic discovery.

### GOOD: Verified counts
```bash
# Count before documenting
ls plugins/autonomous-dev/agents/*.md | wc -l
ls plugins/autonomous-dev/skills/*/SKILL.md | wc -l
```

### BAD: Stale cross-references
```markdown
See [architecture guide](docs/ARCHITECTURE.md) for details.
```
If `docs/ARCHITECTURE.md` was renamed to `docs/ARCHITECTURE-OVERVIEW.md`, this link is broken.

### GOOD: Validated references
Check all links exist before committing documentation changes.

### BAD: Missing CHANGELOG entry
Shipping a user-visible feature with no CHANGELOG entry. Users cannot discover what changed.

### GOOD: CHANGELOG-first workflow
Write the CHANGELOG entry before or during implementation, not as an afterthought.

---

## Cross-References

- **project-alignment**: PROJECT.md as source of truth
- **git-github**: Commit message and PR conventions
- **code-review**: Documentation checklist item (#8)

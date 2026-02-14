# Error Handling Patterns - Detailed Guide

## Usage Guidelines

### For Library Authors

When creating or updating libraries:

1. **Reference this skill** in the module docstring
2. **Inherit from domain-specific base errors** (not generic Exception)
3. **Use formatted error messages** (context + expected + got + docs)
4. **Log security events** to audit log
5. **Implement graceful degradation** for optional features

### For Claude

When implementing error handling:

1. **Load this skill** when keywords match ("error", "exception", "validation")
2. **Follow exception hierarchy** for custom errors
3. **Format error messages** using the standard template
4. **Log security events** for security-relevant errors
5. **Degrade gracefully** for non-blocking features

### Token Savings

By centralizing error patterns in this skill:

- **Before**: ~400-500 tokens per library for error classes + docstrings
- **After**: ~50-100 tokens for skill reference + custom logic
- **Savings**: ~300-400 tokens per library
- **Total**: ~7,000-8,000 tokens across 22 libraries (10-15% reduction)

---

## Progressive Disclosure

This skill uses Claude Code 2.0+ progressive disclosure architecture:

- **Metadata** (frontmatter): Always loaded (~200 tokens)
- **Full content**: Loaded only when keywords match
- **Result**: Efficient context usage, scales to 100+ skills

When you use terms like "error handling", "exception", "validation", or "raise", Claude Code automatically loads the full skill content to provide detailed guidance.

---

## Examples

# Documentation Guide - Detailed Guide

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

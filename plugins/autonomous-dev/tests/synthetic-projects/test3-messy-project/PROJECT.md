# Messy Project Documentation

## File Organization Standards

### Root Directory Policy

**Maximum**: 8 essential .md files

**Allowed**:
- README.md
- CHANGELOG.md
- LICENSE
- PROJECT.md

**All other .md files** must be in `docs/` subdirectories.

### Shell Scripts

All `.sh` files must be in `scripts/` subdirectories:
- `scripts/debug/` - Debugging tools
- `scripts/test/` - Testing utilities

### Documentation

Non-essential docs in `docs/` subdirectories:
- `docs/guides/` - User guides
- `docs/debugging/` - Debug info

### Source Code

- `src/` - All source code
- `tests/` - All test files

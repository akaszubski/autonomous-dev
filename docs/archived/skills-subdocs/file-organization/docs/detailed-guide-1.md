# File Organization - Detailed Guide

## Auto-Invoke Triggers

This skill is automatically invoked:
- **Before file creation**: Validates proposed file location
- **Before file move**: Validates destination path
- **Before directory creation**: Validates directory structure

---

## What This Skill Enforces

### 1. Root Directory Policy

**Rule**: Maximum 8 essential .md files in root

**Allowed in root**:
- README.md
- CHANGELOG.md
- LICENSE
- CONTRIBUTING.md
- CODE_OF_CONDUCT.md
- SECURITY.md
- CLAUDE.md
- PROJECT.md

**All other .md files**: Must be in `docs/` subdirectories

### 2. Shell Scripts Organization

**Rule**: All `.sh` files in `scripts/` subdirectories

**Categories**:
- `scripts/debug/` - Debugging and troubleshooting tools
- `scripts/test/` - Testing utilities
- `scripts/build/` - Build and deployment scripts
- `scripts/` - General utility scripts

**Example**:
- ❌ `./test-auth.sh`
- ✅ `./scripts/test/test-auth.sh`

### 3. Documentation Organization

**Rule**: Documentation in `docs/` subdirectories by category

**Categories**:
- `docs/guides/` - User-facing guides
- `docs/debugging/` - Troubleshooting and debug info
- `docs/development/` - Developer documentation
- `docs/architecture/` - Architecture decisions (ADRs)
- `docs/reference/` - API reference, technical specs

**Example**:
- ❌ `./USER-GUIDE.md`
- ✅ `./docs/guides/user-guide.md`

### 4. Source Code Organization

**Rule**: All source code in `src/`, all tests in `tests/`

**Example**:
- ❌ `./my-module.ts`
- ✅ `./src/my-module.ts`
- ✅ `./tests/unit/my-module.test.ts`

---

## Workflow

---
description: "[DEPRECATED] Use /sync --env instead. Legacy environment synchronization command."
deprecated: true
replacement: "/sync --env"
---

# [DEPRECATED] Sync Dev - Use /sync --env

**This command is deprecated as of v3.7.0. Use `/sync --env` instead.**

---

## Migration

Old command:
```bash
/sync-dev
```

New command:
```bash
/sync --env
```

**Why deprecated?** The unified `/sync` command provides:
- Smart auto-detection of sync mode
- Better integration with marketplace updates
- Simplified workflow for plugin development
- Consistent interface across all sync operations

---

## Original Documentation

For reference, the original `/sync-dev` documentation is preserved below.

---

# Sync Dev - Development Environment Synchronization

**Smart environment sync powered by the sync-validator agent**

Detects and resolves development environment conflicts including dependency mismatches, configuration drift, pending migrations, and stale build artifacts.

---

## Usage

```bash
/sync-dev
```

**Time**: 30-60 seconds
**Interactive**: Shows sync status, asks for confirmation before fixes
**GenAI-Powered**: Uses sync-validator agent for intelligent conflict detection

---

## How It Works

The sync-validator agent analyzes your development environment:

### Phase 1: Pre-Sync Analysis
- Checks local state (uncommitted changes, stale branches, existing conflicts)
- Checks remote state (new commits, tags, breaking changes)
- Assesses sync risk (low/medium/high)

### Phase 2: Fetch & Analyze Changes
- Fetches latest from upstream
- Analyzes changed files
- Categorizes changes (safe / requires attention / breaking)

### Phase 3: Conflict Detection
- Dependency conflicts (package.json, requirements.txt, Cargo.toml)
- Environment variable mismatches (.env files)
- Pending database migrations
- Stale build artifacts
- Configuration drift between local and upstream

### Phase 4: Validation
- Syntax validation (Python, Bash, JSON)
- Plugin integrity check (all agents present)
- Dependency compatibility
- Hook functionality

### Phase 5: Recovery & Recommendations
- Provides fix recommendations
- Safe rollback if issues detected
- Next steps for manual resolution

---

[Rest of original documentation omitted for brevity - see /sync --env for current documentation]

---

**Archived**: 2025-11-08
**Replaced by**: `/sync --env`
**Issue**: GitHub #44 - Unified /sync command consolidation

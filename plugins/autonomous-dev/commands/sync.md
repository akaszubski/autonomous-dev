---
name: sync
description: "Sync plugin files (--github default, --env, --marketplace, --plugin-dev, --all, --uninstall)"
argument-hint: "--github | --env | --marketplace | --plugin-dev | --all | --uninstall [--force]"
allowed-tools: [Bash]
---

Do NOT fetch any URLs or documentation. Execute the script below directly.

## Implementation

```bash
python3 ~/.claude/lib/sync_dispatcher.py $ARGUMENTS
```

## Flags

| Flag | Description |
|------|-------------|
| `--github` | Sync from GitHub repository (default if no flag specified) |
| `--env` | Sync environment variables between `.env` files |
| `--marketplace` | Update plugin from marketplace to latest version |
| `--plugin-dev` | Sync for plugin development (watches local changes) |
| `--all` | Sync all sources (github + env + marketplace) |
| `--uninstall` | Remove plugin files from Claude Code |
| `--force` | Force sync even if no changes detected (use with any flag) |

## Usage

```bash
# Default: Sync from GitHub (most common)
/sync

# Update from marketplace
/sync --marketplace

# Sync environment variables
/sync --env

# Force full resync
/sync --github --force

# Uninstall plugin
/sync --uninstall
```

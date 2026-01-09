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

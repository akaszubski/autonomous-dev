---
name: sync
description: "Sync plugin files (--github default, --env, --marketplace, --plugin-dev, --all, --uninstall)"
argument_hint: "--github | --env | --marketplace | --plugin-dev | --all | --uninstall [--force]"
allowed-tools: [Bash]
---

## Implementation

Run the sync dispatcher with user arguments:

python3 ~/.claude/lib/sync_dispatcher.py $ARGUMENTS

Do NOT fetch any URLs or documentation. Just execute the script above.

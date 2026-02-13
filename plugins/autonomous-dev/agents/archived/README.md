# Archived Agents

These agents are no longer actively used by any command in the autonomous-dev plugin.
They were archived on 2026-02-14 as part of Issue #331 (token overhead reduction).

## Restoring an Agent

1. Move the `.md` file back to `agents/`
2. Add the file path to `install_manifest.json` under `components.agents.files`
3. Re-run `/sync` and restart Claude Code

---
covers:
  - plugins/autonomous-dev/hooks/*.hook.json
  - plugins/autonomous-dev/config/hook-metadata.schema.json
  - scripts/generate_hook_config.py
---

# Hook Sidecar Schema (.hook.json)

Declarative metadata for hook registration, eliminating config drift between hook files and settings templates.

## Purpose

Each hook file (`.py` or `.sh`) can have a companion `.hook.json` sidecar that declares:

- What lifecycle events it registers for
- What tool matchers it uses
- What timeout it needs
- What environment variables it expects
- Whether it is a lifecycle hook or a utility module

This metadata enables automated settings generation and validation, replacing manual registration in settings templates.

## Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Hook identifier matching filename (without extension) |
| `type` | enum | Yes | - | `"lifecycle"` (registered with events) or `"utility"` (imported, not registered) |
| `description` | string | No | - | Human-readable description |
| `interpreter` | enum | Yes | - | `"python3"` or `"bash"` |
| `active` | boolean | No | `true` | Whether the hook is currently active |
| `version` | string | No | - | Semantic version |
| `registrations` | array | Conditional | - | Required for lifecycle; forbidden for utility |
| `env` | object | No | - | Environment variable defaults (string keys, string values) |

### Registration Object

Each entry in the `registrations` array:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `event` | enum | Yes | - | One of 9 lifecycle events (see below) |
| `matcher` | string | No | `"*"` | Tool name pattern (e.g., `"Write\|Edit\|MultiEdit"`) |
| `timeout` | integer | No | - | Schema-permitted for backward compatibility, but no sidecar in this repo declares it (Issue #1704). Timeouts are resolved from `plugins/autonomous-dev/config/hook_time_budgets.json` — see [Hook Time Budgets](HOOKS.md#hook-time-budgets). A sidecar-declared `timeout` is a regression, caught by `tests/regression/regression/test_issue_1704_hook_time_budgets.py::test_no_sidecar_declares_a_timeout`. |

### Lifecycle Events

The 9 supported Claude Code lifecycle events:

- `UserPromptSubmit` -- Before user prompt is processed
- `PreToolUse` -- Before a tool is invoked
- `PostToolUse` -- After a tool completes
- `Stop` -- When the agent stops
- `SubagentStop` -- When a sub-agent stops
- `TaskCompleted` -- When a task finishes
- `PreCompact` -- Before context compaction
- `PostCompact` -- After context compaction
- `SessionStart` -- When a new session begins

## Type Semantics

### Lifecycle Hooks

Lifecycle hooks register for one or more Claude Code events. They **must** have at least one registration entry.

```json
{
  "name": "unified_pre_tool",
  "type": "lifecycle",
  "interpreter": "python3",
  "registrations": [
    {
      "event": "PreToolUse",
      "matcher": "*"
    }
  ]
}
```

No `timeout` field — it is resolved from `config/hook_time_budgets.json`, not declared per-sidecar (Issue #1704).

### Utility Modules

Utility modules are deployed alongside hooks but are not registered with any lifecycle event. They are typically imported by other hooks (`genai_utils`), though some are standalone CLI-invoked modules (`cloud_drain_telemetry`). The `registrations` field **must not** be present.

`type` gates deployment: `generate_hook_config.py` includes **every** sidecar in `install_manifest.json` but emits settings registrations for `type: "lifecycle"` sidecars only. A utility therefore ships to `~/.claude/hooks/` but is never wired to an event — choose `utility` whenever no real Claude Code lifecycle event applies, rather than inventing an event name to satisfy the `lifecycle` shape.

**The declaration alone is not enough if the hook can refuse (Issue #1612).** `type: "utility"` is a schema-level claim of "imported by other hooks, not registered directly" — nothing enforces that a real importer exists. Commit `51743c87` declared two hooks `utility` on the strength of a module-docstring line and two comments that merely *mentioned* the hook's filename; no code actually imported or invoked either one, so both were unreachable by any path. `tests/unit/hooks/test_hook_reachability_ratchet.py` now checks this for every hook that can refuse (returns a deny/block/exit-nonzero decision, per the #1588 refusal instruments): a `utility` declaration only counts as reachable when a real `import`/`from-import` naming the hook's module, or a string constant naming the file passed as an argument to an **invocation-shaped** call — `run`, `Popen`, `call`, `check_call`, `check_output`, `run_path`, `execv`, `execvp`, `spawn`, or `system` (the module's `INVOCATION_CALLEES`) — or an executing shell line (not a `[ -f ... ]` existence check) resolves somewhere in the hook/lib/scripts corpus. A filename constant passed to any *other* call (a log line, a `print`, an `argparse` `help=` string) does not count — only an argument to one of those callees does. The importer chain must also be **grounded**: a `utility` hook whose only importer is another unregistered `utility` hook is still flagged, because that importer's own chain has to terminate at a `lib/`/`scripts/` consumer or a lifecycle-registered hook before it can vouch for anything. A refusal-capable hook that is neither registered on a lifecycle event nor genuinely (and groundedly) imported fails the ratchet, named, with the surfaces searched. A hook that cannot refuse (a pure library or observer) is unaffected — the check is scoped to hooks that can block.

```json
{
  "name": "genai_utils",
  "type": "utility",
  "interpreter": "python3"
}
```

## Dual Registration Pattern

A single hook can register for multiple events. For example, `session_activity_logger` logs both tool usage and session stops:

```json
{
  "name": "session_activity_logger",
  "type": "lifecycle",
  "interpreter": "python3",
  "env": {
    "ACTIVITY_LOGGING": "true"
  },
  "registrations": [
    {
      "event": "PostToolUse",
      "matcher": "*"
    },
    {
      "event": "Stop",
      "matcher": "*"
    }
  ]
}
```

Each registration entry can have its own matcher, allowing fine-grained control per event. (Timeout is no longer per-registration in the sidecar — see the `timeout` field note above.)

## How to Add a New Hook

1. Create the hook script: `plugins/autonomous-dev/hooks/my_hook.py`
2. Create the sidecar: `plugins/autonomous-dev/hooks/my_hook.hook.json`
3. Generate configuration files from sidecar metadata (see **Configuration Generator** below)
4. Verify the generated files and commit

**If the hook can refuse** (returns a deny/block decision or a non-zero exit meant to stop the caller), it must also be *reachable*, or it silently never fires: give it `type: "lifecycle"` with at least one real `registrations` entry, or `type: "utility"` **and** a genuine importer/invoker elsewhere in the hooks/lib/scripts corpus (see the note under [Utility Modules](#utility-modules) above). `tests/unit/hooks/test_hook_reachability_ratchet.py` enforces this for every refusal-capable hook and will name yours if it fails either route.

## Configuration Generator

The `scripts/generate_hook_config.py` script automates configuration generation from `.hook.json` sidecars, eliminating manual registration drift.

### Usage

```bash
# Check for drift without modifying files
python scripts/generate_hook_config.py --check

# Check with verbose output showing exactly what changed
python scripts/generate_hook_config.py --check -v

# Update config files based on current sidecars
python scripts/generate_hook_config.py --write

# Write with verbose output
python scripts/generate_hook_config.py --write -v
```

There are two additional flags for the timeout-sync workflow specifically
(Issue #1704), documented in [HOOKS.md — Hook Time
Budgets](HOOKS.md#hook-time-budgets): `--check-timeouts` and
`--sync-timeouts`. They propagate `config/hook_time_budgets.json` — not the
sidecars, which no longer carry a `timeout` — to every settings surface.

### What It Generates

The generator creates two config files from the discovered `.hook.json` sidecars:

1. **install_manifest.json** — `components.hooks.files` array
   - Lists all hook scripts and `.hook.json` sidecar files
   - Determines what gets deployed during plugin installation

2. **global_settings_template.json** — `hooks` object
   - Registers lifecycle hooks with Claude Code events
   - Extracts matchers and environment variables from sidecars; resolves each
     hook's `timeout` from `config/hook_time_budgets.json` via
     `resolve_timeout()` — never from the sidecar (Issue #1704)
   - Groups registrations by event, sorted alphabetically
   - Specific matchers appear before wildcard matchers within each event

### Examples

**Check for drift:**
```bash
$ python scripts/generate_hook_config.py --check
No drift detected.
```

**Report drift without fixing:**
```bash
$ python scripts/generate_hook_config.py --check -v
Manifest: would add ['plugins/autonomous-dev/hooks/new_hook.hook.json']
Settings: would add events ['UserPromptSubmit']
Drift detected. Run with --write to update.
```

**Apply updates:**
```bash
$ python scripts/generate_hook_config.py --write -v
Updated manifest: plugins/autonomous-dev/config/install_manifest.json (6 hook files)
Updated settings: plugins/autonomous-dev/config/global_settings_template.json (4 events)
Config files updated successfully.
```

### Exit Codes

- `0` — Success (no drift in check mode, or write succeeded)
- `1` — Drift detected (check mode) or validation errors
- `2` — CLI/usage errors

### Minimal Lifecycle Example

```json
{
  "name": "my_hook",
  "type": "lifecycle",
  "interpreter": "python3",
  "registrations": [
    {
      "event": "PreToolUse"
    }
  ]
}
```

### Minimal Utility Example

```json
{
  "name": "my_utils",
  "type": "utility",
  "interpreter": "python3"
}
```

## Enforcement

Hook sidecar consistency is enforced at multiple levels to prevent registration drift.

### CI Check

Every PR runs the hook sidecar consistency check as part of the `smoke` job in `.github/workflows/ci.yml`. The step runs `generate_hook_config.py --check` and fails the build if drift is detected between `.hook.json` sidecars and the generated config files (`install_manifest.json`, `global_settings_template.json`).

### Pre-Commit Hook

A pre-commit hook script is available at `scripts/pre-commit-hook-check.sh`. It only runs when hook-related files are staged (hooks directory or config files), keeping commits fast for unrelated changes.

Install:
```bash
ln -sf ../../scripts/pre-commit-hook-check.sh .git/hooks/pre-commit
```

### Manual Verification

Use `/sync --verify` to check hook sidecar consistency without deploying:
```bash
python3 -m plugins.autonomous_dev.lib.sync_dispatcher.cli --verify
```

### Developer Workflow

When adding or modifying a hook:

1. Create or update the hook script: `plugins/autonomous-dev/hooks/my_hook.py`
2. Create or update the sidecar: `plugins/autonomous-dev/hooks/my_hook.hook.json`
3. Regenerate config files: `python3 scripts/generate_hook_config.py --write`
4. Verify consistency: `python3 scripts/generate_hook_config.py --check`
5. Commit all changed files together (hook, sidecar, manifest, settings)

Failing to regenerate after sidecar changes will cause both pre-commit and CI to reject the commit/PR.

## Schema Location

The JSON Schema (draft 2020-12) is at:

```
plugins/autonomous-dev/config/hook-metadata.schema.json
```

Validate a sidecar file against the schema:

```bash
python3 -c "
import json
from jsonschema import validate, Draft202012Validator
schema = json.load(open('plugins/autonomous-dev/config/hook-metadata.schema.json'))
instance = json.load(open('plugins/autonomous-dev/hooks/my_hook.hook.json'))
validate(instance=instance, schema=schema, cls=Draft202012Validator)
print('Valid')
"
```

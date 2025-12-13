# Archived Commands - Issue #121

This directory contains commands that were simplified and consolidated as part of Issue #121 (Command Simplification).

## Why Commands Were Archived

The autonomous-dev plugin originally had 20 commands, which created cognitive overhead for users learning the system. Issue #121 simplified the command structure from 20 to 8 active commands by:

1. **Consolidating related commands** - Combining align-project, align-claude, and align-project-retrofit into a single `/align` command
2. **Removing redundant commands** - Individual agent commands (research, plan, implement, etc.) are replaced by `/auto-implement`
3. **Streamlining utilities** - Moving less-used utilities to archive

## Archived Commands (13 total)

### Individual Agent Commands (7)
These are now handled by `/auto-implement`:
- `research.md` - Pattern research (now: `/auto-implement` step 1)
- `plan.md` - Architecture planning (now: `/auto-implement` step 2)
- `test-feature.md` - TDD test generation (now: `/auto-implement` step 3)
- `implement.md` - Code implementation (now: `/auto-implement` step 4)
- `review.md` - Code quality review (now: `/auto-implement` step 5)
- `security-scan.md` - Security audit (now: `/auto-implement` step 5)
- `update-docs.md` - Documentation sync (now: `/auto-implement` step 5)

### Alignment Commands (3)
These are now modes of `/align`:
- `align-project.md` - PROJECT.md alignment (now: `/align --project`)
- `align-claude.md` - Documentation drift (now: `/align --claude`)
- `align-project-retrofit.md` - Brownfield retrofit (now: `/align --retrofit`)

### Utility Commands (3)
Consolidated or superseded:
- `batch-implement.md` - Sequential processing (now: `/auto-implement --batch`)
- `create-issue.md` - GitHub issue creation (superseded by workflow)
- `update-plugin.md` - Plugin updates (superseded by `/health-check`)

## Active Commands (8)

After simplification, these 8 commands remain active:

1. **`auto-implement.md`** - Full autonomous pipeline (research → plan → test → implement → review → docs)
2. **`align.md`** - Unified alignment command (--project, --claude, --retrofit modes)
3. **`setup.md`** - Interactive project setup wizard
4. **`sync.md`** - Smart sync (dev environment, marketplace, or plugin-dev)
5. **`status.md`** - Project progress tracking
6. **`health-check.md`** - Plugin integrity validation
7. **`pipeline-status.md`** - Track /auto-implement workflow execution
8. **`test.md`** - Run automated tests (pytest wrapper)

## Migration Guide

### For Users

If you were using archived commands, here's how to migrate:

| Old Command | New Command |
|-------------|-------------|
| `/research <feature>` | `/auto-implement <feature>` (full pipeline) |
| `/plan <feature>` | `/auto-implement <feature>` (full pipeline) |
| `/test-feature <feature>` | `/auto-implement <feature>` (full pipeline) |
| `/implement <feature>` | `/auto-implement <feature>` (full pipeline) |
| `/review` | `/auto-implement <feature>` (full pipeline) |
| `/security-scan` | `/auto-implement <feature>` (full pipeline) |
| `/update-docs` | `/auto-implement <feature>` (full pipeline) |
| `/align-project` | `/align --project` |
| `/align-claude` | `/align --claude` |
| `/align-project-retrofit` | `/align --retrofit` |
| `/batch-implement <file>` | `/auto-implement --batch <file>` |
| `/create-issue <request>` | Use `/auto-implement` workflow |
| `/update-plugin` | Use `/health-check` to check for updates |

### For Developers

Archived commands remain in this directory for reference. If you need to restore a command:

1. Copy the command file from `archive/` to `commands/`
2. Add the command to `plugins/autonomous-dev/config/install_manifest.json`
3. Update CLAUDE.md to document the restored command
4. Restart Claude Code to reload commands

## Rationale

The 20-to-8 simplification provides:

- **Lower cognitive overhead** - Fewer commands to learn and remember
- **Clearer workflows** - `/auto-implement` is the primary command for feature development
- **Better discoverability** - Unified `/align` command with clear modes
- **Consistent patterns** - Flags (`--project`, `--claude`, `--retrofit`) instead of separate commands

## References

- **Issue**: [#121 - Simplify commands from 20 to 8](https://github.com/akaszubski/autonomous-dev/issues/121)
- **Documentation**: See `docs/COMMAND-SIMPLIFICATION.md` for complete migration guide
- **Testing**: See `tests/unit/test_command_archive.py` for validation tests

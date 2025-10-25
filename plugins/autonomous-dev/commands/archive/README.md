# Archived Commands

**Status**: Deprecated - Not actively maintained

This directory contains commands that have been **archived** and are no longer part of the active plugin.

---

## Why Commands Are Archived

Commands are archived when they:
1. **Duplicate functionality** of other commands
2. **Add unnecessary complexity** to the user experience
3. **Are superseded** by better alternatives
4. **Don't align** with the simplified plugin vision

---

## Active Commands (8)

**Use these instead:**

| Command | Purpose | Use Case |
|---------|---------|----------|
| `/auto-implement` | Autonomous feature implementation | Full autonomous workflow |
| `/align-project` | PROJECT.md alignment check | Validate alignment |
| `/test` | Run all tests | Testing during development |
| `/setup` | Plugin setup wizard | Initial configuration |
| `/status` | Project status overview | Quick status check |
| `/health-check` | Component validation | Troubleshooting |
| `/sync-dev` | Development sync | Plugin development only |
| `/uninstall` | Plugin removal | Cleanup |

---

## Archived Commands (16)

### Commit Commands (Replaced by `/auto-implement`)
- `commit.md` - Basic commit → Use `/auto-implement` (includes commit)
- `commit-check.md` - Commit with tests → Use `/auto-implement` (includes tests)
- `commit-push.md` - Commit and push → Use `/auto-implement` (includes push)
- `commit-release.md` - Release commit → Use GitHub releases workflow

### Formatting Commands (Automated by Hooks)
- `format.md` - Manual formatting → Auto-format hook runs automatically

### Testing Commands (Consolidated to `/test`)
- `test-unit.md` - Unit tests only → Use `/test` (runs all)
- `test-integration.md` - Integration tests → Use `/test`
- `test-uat.md` - UAT tests → Use `/test`
- `test-uat-genai.md` - GenAI UX validation → Use `/test-complete`
- `test-architecture.md` - Architecture validation → Use `/test-complete`
- `test-complete.md` - Full validation → Use `/test-complete` (if needed)

### Documentation Commands (Automated by Hooks)
- `sync-docs.md` - Manual doc sync → Docs auto-update on commit
- `sync-docs-api.md` - API doc sync → Automated
- `sync-docs-changelog.md` - CHANGELOG sync → Automated
- `sync-docs-auto.md` - Auto doc detection → Automated
- `sync-docs-organize.md` - Doc organization → Automated

### Other Commands
- `full-check.md` - Complete check → Use `/test` + `/health-check`

---

## Migration Guide

**If you were using archived commands:**

### Commit Workflow
**Before** (manual steps):
```bash
/format
/test
/commit
/commit-push
```

**After** (autonomous):
```bash
/auto-implement "add feature X"
# Automatically: formats, tests, commits, documents
```

### Testing Workflow
**Before** (granular):
```bash
/test-unit
/test-integration
/test-uat
```

**After** (consolidated):
```bash
/test
# Runs all test types automatically
```

### Documentation Workflow
**Before** (manual):
```bash
/sync-docs
/sync-docs-changelog
```

**After** (automatic):
```bash
git commit -m "update"
# Docs auto-update on commit via hooks
```

---

## Why This Simplification?

### Before (40 Commands)
- ❌ Overwhelming choice
- ❌ Unclear which to use
- ❌ Manual multi-step workflows
- ❌ Easy to forget steps

### After (8 Commands)
- ✅ Clear purpose for each
- ✅ Autonomous workflows
- ✅ Hard to make mistakes
- ✅ Focus on WHAT not HOW

---

## Will These Return?

**No.** The plugin philosophy has shifted to:

1. **Autonomous > Manual** - `/auto-implement` does everything
2. **Automated > Manual** - Hooks handle formatting, docs, testing
3. **Simple > Complex** - 8 commands you remember vs 40 you forget

**If you need archived functionality:**
- Most is automated by hooks now
- `/auto-implement` handles full workflows
- `/test` consolidates all testing

---

## For Plugin Developers

**Archived commands are kept for reference only.** They demonstrate evolution of the plugin but are not maintained.

**Do not:**
- Reference archived commands in docs
- Suggest archived commands to users
- Maintain or update archived commands

**Instead:**
- Use active 8 commands
- Enhance `/auto-implement` for new workflows
- Strengthen hooks for automation

---

## Questions?

- **"Can I still use archived commands?"** - They may work but are not maintained. Use active commands instead.
- **"Will you add more commands?"** - Only if they serve distinct purposes and don't duplicate functionality.
- **"How do I know what's active?"** - See `/health-check` or list `commands/*.md` (excludes archive/)

---

**Last Updated**: 2025-10-26
**Plugin Version**: v2.4.0-beta
**Active Commands**: 8
**Archived Commands**: 16

**Philosophy**: Simple > Complex, Autonomous > Manual, Automated > Manual

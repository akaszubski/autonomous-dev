---
name: worktree
description: "Manage git worktrees (--list default, --status, --review, --merge, --discard)"
argument_hint: "Optional flags: --list (default), --status FEATURE, --review FEATURE, --merge FEATURE, --discard FEATURE"
allowed-tools: [Task, Read, Write, Bash, Grep, Glob]
---

## Implementation

```bash
python3 ~/.claude/lib/worktree_command.py "$@"
```

---

# Worktree - Git Worktree Management

**Safe feature isolation with git worktrees for review/merge/discard workflow**

The `/worktree` command provides a complete workflow for managing git worktrees created by the autonomous development pipeline. It enables reviewing changes, merging to main branch, or discarding unwanted work - all without affecting your main working directory.

---

## Quick Start

```bash
# List all worktrees (default mode)
/worktree                    # Shows all active worktrees
/worktree --list             # Explicit list mode

# Show detailed status
/worktree --status my-feature    # Commits ahead/behind, uncommitted changes

# Interactive review (diff + approve/reject)
/worktree --review my-feature    # Shows diff, prompts for merge approval

# Merge to target branch
/worktree --merge my-feature     # Merges feature to master

# Discard worktree
/worktree --discard my-feature   # Deletes worktree with confirmation
```

**Time**: 5-30 seconds (depends on mode)
**Interactive**: Review and discard modes require confirmation
**Safe Operations**: All destructive operations require explicit approval

---

## Use Cases

### When to Use /worktree

**Review workflow**:
- Feature completed in worktree
- Want to review changes before merging
- Need to compare against main branch
- Decide whether to merge or discard

**Isolation benefits**:
- Main branch stays clean
- Multiple features in parallel
- Easy rollback (just discard)
- No context switching overhead

**Typical workflow**:
1. Feature developed in worktree (via `/auto-implement`)
2. Review changes (`/worktree --review my-feature`)
3. Approve to merge (or reject to iterate)
4. Discard worktree after merge (`/worktree --discard my-feature`)

---

## Worktree Modes

### List Mode (`--list`) - DEFAULT

Shows all active worktrees with status indicators.

**What it does**:
- Lists all worktrees in repository
- Shows feature name, branch, and status
- Filters out main repository
- Quick overview of all features in progress

**When to use**:
- Check what features are in progress
- Find worktree names for other operations
- See status at a glance

**Example**:
```bash
/worktree
/worktree --list
```

**Output**:
```
Feature              Branch                         Status
------------------------------------------------------------
feature-auth         feature/feature-auth           clean
feature-logging      feature/feature-logging        dirty
hotfix-123           hotfix/hotfix-123              active
```

**Status indicators**:
- `clean` - No uncommitted changes, ready to merge
- `dirty` - Has uncommitted changes
- `active` - Currently checked out
- `stale` - Directory doesn't exist (orphaned)
- `detached` - Detached HEAD state

---

### Status Mode (`--status FEATURE`)

Shows detailed information for a specific worktree.

**What it does**:
- Path to worktree directory
- Current branch name
- Clean/dirty status
- Commits ahead/behind target branch
- List of uncommitted files

**When to use**:
- Before merging (check if ready)
- Troubleshooting worktree issues
- Understanding feature state

**Example**:
```bash
/worktree --status feature-auth
```

**Output**:
```
Worktree Status: feature-auth
============================================================
Path:            /Users/dev/project/.worktrees/feature-auth
Branch:          feature/feature-auth
Status:          dirty
Target Branch:   master
Commits Ahead:   5
Commits Behind:  2

Uncommitted Changes (3 files):
  - auth/models.py
  - auth/tests.py
  - README.md
```

**Understanding output**:
- **Commits Ahead**: How many commits will be merged
- **Commits Behind**: How many commits from master are missing
- **Uncommitted Changes**: Files modified but not committed

---

### Review Mode (`--review FEATURE`)

Interactive diff review with approve/reject workflow.

**What it does**:
1. Shows full git diff against target branch
2. Prompts for approval (approve/reject)
3. If approved → automatically merges to target branch
4. If rejected → exits without merging

**When to use**:
- Final review before merging
- Ensure changes match expectations
- Catch unintended modifications
- Quality gate before integration

**Example**:
```bash
/worktree --review feature-auth
```

**Output**:
```
Diff for worktree: feature-auth
============================================================
diff --git a/auth/models.py b/auth/models.py
index 1234567..89abcde 100644
--- a/auth/models.py
+++ b/auth/models.py
@@ -10,6 +10,12 @@ class User(Model):
     email = CharField()
+    def authenticate(self, password):
+        """Authenticate user with password."""
+        return check_password(password, self.password_hash)
+
 [... more diff output ...]
============================================================

Approve or reject changes? [approve/reject]: approve

✓ Successfully merged 12 files
```

**Interactive prompts**:
- Approval required before merge
- Shows all changes first
- Safe default: reject (if unclear)

---

### Merge Mode (`--merge FEATURE`)

Directly merge worktree to target branch without review.

**What it does**:
- Checks out target branch (default: master)
- Merges feature branch
- Shows list of merged files
- Handles merge conflicts gracefully

**When to use**:
- Already reviewed changes manually
- Confident in worktree state
- Non-interactive merge needed
- Batch processing multiple features

**Example**:
```bash
/worktree --merge feature-auth
```

**Success output**:
```
✓ Successfully merged 12 files

Merged files:
  - auth/models.py
  - auth/views.py
  - auth/tests.py
  - auth/__init__.py
  - docs/authentication.md
  - README.md
  ... and 6 more
```

**Conflict output**:
```
✗ Merge failed: Merge conflict detected

Conflicting files:
  - auth/models.py
  - auth/views.py
```

**Handling conflicts**:
1. Fix conflicts in your editor
2. Stage resolved files: `git add <files>`
3. Complete merge: `git commit`
4. Retry: `/worktree --merge feature-auth`

**Environment integration**:
- Respects `AUTO_GIT_ENABLED` environment variable
- Part of autonomous workflow automation

---

### AI Merge Mode (`--merge FEATURE --ai-merge`)

Merge worktree with automatic AI-powered conflict resolution.

**What it does**:
- Attempts to merge feature branch to target branch
- If merge conflicts detected, uses Claude API to resolve them intelligently
- Applies AI resolutions with confidence scoring
- Falls back to manual resolution if AI confidence too low
- Completes merge after conflict resolution

**When to use**:
- Merge conflicts expected or present
- Want automated intelligent resolution
- Trust AI to handle complex conflicts
- Reduce manual merge resolution time

**Requirements**:
- ANTHROPIC_API_KEY environment variable set
- Merge conflict(s) present (otherwise behaves like regular --merge)
- Internet connectivity for API calls
- User approval for AI resolution (interactive prompt)

**Example**:
```bash
# Merge with AI conflict resolution enabled
/worktree --merge feature-auth --ai-merge

# Without --ai-merge flag (manual resolution)
/worktree --merge feature-auth
```

**Three-Tier Resolution Strategy**:

The AI merger uses an intelligent three-tier escalation strategy:

1. **Tier 1 (Auto-Merge)**: Trivial conflicts resolved instantly
   - Whitespace-only differences
   - Identical changes on both sides
   - Zero API cost, <100ms resolution

2. **Tier 2 (Conflict-Only)**: AI analyzes conflict blocks
   - Focuses on semantic understanding
   - 3-5 seconds per conflict
   - Suitable for 90% of real conflicts
   - ~200 tokens per conflict

3. **Tier 3 (Full-File)**: Comprehensive context analysis
   - Reads entire file for maximum context
   - Handles complex multi-conflict scenarios
   - 5-10 seconds per file
   - For difficult semantic conflicts

**Output with AI resolution**:
```
Merge detected conflicts in: auth/models.py

Attempting AI resolution...

Tier 1 (Auto-Merge): No trivial conflicts found
Tier 2 (Conflict-Only): Analyzing conflict blocks...

Conflict 1 (lines 42-58):
  Confidence: 92%
  Reasoning: Both sides added authentication methods. Merged by placing them sequentially.
  Status: RESOLVED

Conflict 2 (lines 85-102):
  Confidence: 78%
  Reasoning: Import ordering conflict. Reorganized alphabetically.
  Status: RESOLVED

Apply these resolutions? [yes/no]: yes

✓ All conflicts resolved with AI assistance
✓ Successfully merged 12 files
```

**Interactive approval**:
- Shows all AI resolutions before applying
- Displays confidence score for each
- Shows reasoning for each resolution
- User can approve or reject
- Safe default: requires explicit approval

**Output if confidence too low**:
```
Conflict 1 (lines 85-102):
  Confidence: 45%
  Status: SKIPPED (confidence below threshold of 70%)

✗ Unable to resolve all conflicts with sufficient confidence

Manual resolution required:
  1. Resolve conflicting files manually
  2. Stage changes: git add <files>
  3. Complete merge: git commit
  4. Or run: /worktree --merge feature-auth (without --ai-merge)
```

**Error handling**:
- Missing ANTHROPIC_API_KEY: Falls back to manual resolution with helpful message
- API rate limiting: Retries with exponential backoff
- Network errors: Graceful degradation, manual resolution instructions
- Invalid file types: Skips AI resolution for binary files

**Performance comparison**:

| Scenario | Without --ai-merge | With --ai-merge |
|----------|-------------------|-----------------|
| No conflicts | 2 seconds | 2 seconds (no AI overhead) |
| Single simple conflict | 5 minutes (manual) | 10 seconds (Tier 1-2) |
| Multiple conflicts | 15+ minutes (manual) | 30 seconds (Tier 2) |
| Complex conflict | 20+ minutes (manual) | 45 seconds (Tier 3) |

**Integration with batch workflows**:
```bash
# Batch merge multiple features with AI resolution
for feature in feature-1 feature-2 feature-3; do
  /worktree --merge "$feature" --ai-merge
done
```

**Cost estimation**:
- No conflicts: No API cost
- Tier 1 (trivial): No API cost
- Tier 2 (most cases): ~$0.001 per conflict (200 tokens at ~$0.0005 per token)
- Tier 3 (complex): ~$0.005 per file (1000 tokens)

**Security**:
- API key never logged or displayed
- Conflict content sent to API (read ANTHROPIC_API_KEY value)
- Atomic file operations prevent corruption
- Backup created before modifications
- User consent required before applying resolutions

**Known limitations**:
- Binary files not supported (auto-skip)
- Very large files (>1MB) chunked for API limits
- May not understand project-specific conventions
- Complex refactoring may need manual review
- Requires active internet connection

---

### Discard Mode (`--discard FEATURE`)

Delete worktree with confirmation prompt.

**What it does**:
- Shows warning if uncommitted changes exist
- Prompts for confirmation
- Force-deletes worktree directory
- Removes git references

**When to use**:
- Feature abandoned or obsolete
- Worktree merged and no longer needed
- Experimenting with approaches
- Cleaning up stale worktrees

**Example**:
```bash
/worktree --discard feature-auth
```

**Output with uncommitted changes**:
```
⚠ Warning: Worktree 'feature-auth' has uncommitted changes:
  - auth/models.py
  - auth/tests.py
  - README.md

These changes will be lost if you continue.

Are you sure you want to discard worktree 'feature-auth'? [yes/no]: yes

✓ Worktree 'feature-auth' discarded successfully
```

**Output without changes**:
```
Are you sure you want to discard worktree 'feature-auth'? [yes/no]: yes

✓ Worktree 'feature-auth' discarded successfully
```

**Safety features**:
- Always prompts for confirmation
- Shows uncommitted changes warning
- Clear about data loss
- Can't be undone (use carefully!)

---

## Integration with /auto-implement

The `/worktree` command integrates seamlessly with the autonomous development workflow:

### Typical Workflow

```bash
# Step 1: Develop feature in worktree
/auto-implement #123 --worktree

# Feature is developed in isolated worktree
# Main branch stays clean during development

# Step 2: Review changes
/worktree --review feature-123

# Shows all changes, prompts for approval
# If approved → automatically merges
# If rejected → can iterate in worktree

# Step 3: Clean up
/worktree --discard feature-123

# Removes worktree after merge
```

### Benefits of Worktree Workflow

**Isolation**:
- Main branch never dirty
- Multiple features in parallel
- Easy rollback (just discard)
- No context switching

**Safety**:
- Review before merge
- Conflicts detected early
- Can test in isolation
- Rollback without affecting main

**Productivity**:
- Work on multiple features
- Switch between features instantly
- No stashing/unstashing
- Clean git history

---

## Security

All worktree operations include security validation:

- **Path Validation**: CWE-22 (path traversal) protection
- **Feature Name Validation**: CWE-78 (command injection) prevention
- **Symlink Detection**: CWE-59 (symlink resolution) protection
- **Audit Logging**: All operations logged for accountability

**Security requirements**:
- Feature names validated (alphanumeric, hyphens, underscores only)
- Paths resolved and validated
- No shell injection possible
- User permissions only

---

## Troubleshooting

### "Worktree not found"

**Cause**: Feature name doesn't match any worktree
**Fix**: List worktrees to see available names

```bash
# List all worktrees
/worktree

# Check exact name
/worktree --status feature-auth  # Use exact name from list
```

---

### "Merge conflict detected"

**Cause**: Feature branch conflicts with target branch
**Fix**: Resolve conflicts manually

```bash
# Option 1: Fix in worktree
cd .worktrees/feature-auth
vim auth/models.py  # Fix conflicts
git add auth/models.py
git commit -m "Resolve conflicts"

# Then retry merge
/worktree --merge feature-auth

# Option 2: Discard and start over
/worktree --discard feature-auth
```

---

### "Worktree has uncommitted changes"

**Cause**: Modified files not committed
**Fix**: Commit or discard changes

```bash
# Option 1: Commit changes
cd .worktrees/feature-auth
git add .
git commit -m "Save work"

# Option 2: Discard changes
/worktree --discard feature-auth  # Will warn and confirm
```

---

### "Permission denied" when discarding

**Cause**: File in use or insufficient permissions
**Fix**: Close editors and ensure permissions

```bash
# Close any editors with files from worktree open

# Check permissions
ls -la .worktrees/feature-auth

# If needed, fix permissions
chmod -R u+w .worktrees/feature-auth

# Retry discard
/worktree --discard feature-auth
```

---

## Examples

### Review Workflow

```bash
# List features in progress
/worktree

# Check status of specific feature
/worktree --status feature-auth

# Review and approve
/worktree --review feature-auth
# Shows diff, approve to merge

# Clean up after merge
/worktree --discard feature-auth
```

---

### Parallel Development

```bash
# Start multiple features
/auto-implement #123 --worktree  # feature-123
/auto-implement #124 --worktree  # feature-124
/auto-implement #125 --worktree  # feature-125

# Check all features
/worktree

# Merge ready features
/worktree --merge feature-123
/worktree --merge feature-124

# Discard unneeded feature
/worktree --discard feature-125
```

---

### Experimentation

```bash
# Try experimental approach
/auto-implement "try new caching strategy" --worktree

# Review results
/worktree --review experimental-caching

# If good → approve to merge
# If bad → reject and discard
/worktree --discard experimental-caching
```

---

## Technical Details

### Architecture

The `/worktree` command uses two core libraries:

1. **worktree_manager.py**: Low-level git worktree operations
   - Create/delete worktrees
   - List worktrees with metadata
   - Merge worktrees to target branch
   - Security validation

2. **worktree_command.py**: Command-line interface
   - Argument parsing (5 modes)
   - Interactive prompts
   - Formatted output
   - Error handling

---

### Performance

**List mode**: <1 second
- Fast git worktree list operation
- Minimal processing

**Status mode**: <2 seconds
- Additional git commands for ahead/behind
- File status checks

**Review mode**: 5-30 seconds
- Depends on diff size
- User interaction time

**Merge mode**: 2-10 seconds
- Depends on number of files
- Conflict detection

**Discard mode**: <2 seconds
- Fast directory removal
- User confirmation time

---

### Worktree Storage

Worktrees are stored in `.worktrees/` directory at repository root:

```
project-root/
├── .git/
├── .worktrees/
│   ├── feature-auth/       # Worktree for feature-auth
│   ├── feature-logging/    # Worktree for feature-logging
│   └── hotfix-123/         # Worktree for hotfix-123
└── main-project-files...
```

**Benefits**:
- Organized in single location
- Easy to find and manage
- Gitignored by default
- Isolated from main branch

---

## See Also

- **Worktree Isolation**: See `/auto-implement --worktree` for feature development in worktrees
- **Git Automation**: See `docs/GIT-AUTOMATION.md` for automatic commit/push/PR workflow
- **Security**: See `docs/SECURITY.md` for comprehensive security documentation

---

**Last Updated**: 2026-01-02
**Issue**: GitHub #180 - /worktree command for review/merge/discard workflow
**Related**: `/auto-implement --worktree`, git automation

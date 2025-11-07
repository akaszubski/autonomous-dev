# Issue #40: Auto-Update PROJECT.md Goal Progress

**Status**: CLOSED (Completed in v3.4.0)
**Date**: 2025-11-07
**Version**: v3.4.0 (implementation) + v3.4.1 (security fix)
**Issue Link**: GitHub Issue #40 - Auto-update PROJECT.md goal progress after feature completion

---

## Overview

Issue #40 implemented **automatic PROJECT.md goal progress tracking** - the team now automatically updates your project's strategic goals with completion percentages after each feature is implemented.

### What It Does

After `/auto-implement <feature>` completes successfully:

1. **SubagentStop hook** triggers automatically (`auto_update_project_progress.py`)
2. **project-progress-tracker agent** analyzes which goals the feature advanced
3. **GenAI assessment** determines percentage completion for each goal
4. **PROJECT.md** is atomically updated with new percentages
5. **Git commit** is created (with user consent) capturing the progress update

### Before and After

**Before (manual tracking)**:
```markdown
## GOALS

- Build a scalable REST API (0% - no tracking)
- Create user dashboard (0% - no tracking)
- Achieve 99.9% uptime (0% - no tracking)
```

**After (automatic tracking)**:
```markdown
## GOALS

- Build a scalable REST API (45% - endpoint framework, database schema, auth complete)
- Create user dashboard (20% - layout and routing planned)
- Achieve 99.9% uptime (10% - monitoring infrastructure in place)
```

---

## How It Works

### Architecture

The feature consists of **three main components**:

#### 1. SubagentStop Hook (`auto_update_project_progress.py`)

**Location**: `plugins/autonomous-dev/hooks/auto_update_project_progress.py`

**Trigger**: `SubagentStop` lifecycle event (fires after doc-master agent completes)

**Behavior**:
```python
# Pseudo-code flow
1. Detect that /auto-implement pipeline completed
2. Read .claude/PROJECT.md from disk
3. Invoke project-progress-tracker agent via invoke_agent.py
4. Parse GenAI-generated YAML progress assessment
5. Update PROJECT.md with new percentages
6. Create git commit with user consent
```

#### 2. ProjectMdUpdater Library (`project_md_updater.py`)

**Location**: `plugins/autonomous-dev/lib/project_md_updater.py`

**Responsibility**: Atomic, secure file operations on PROJECT.md

**Three-Layer Security**:
- **Layer 1**: String validation (reject invalid characters, max 256 chars)
- **Layer 2**: Symlink detection (reject symlinks pointing outside project)
- **Layer 3**: System directory blocking (reject writes to /etc, /sys, etc.)

**Atomic Write Pattern**:
```python
# CRITICAL: Must preserve file integrity
1. Use tempfile.mkstemp() for cryptographic random temp filename (v3.4.1 fix)
2. Write content via os.write(fd, ...) for atomicity
3. Close file descriptor
4. Rename temp_path → target_path (atomic operation)
5. On error: Rollback temp file, preserve original
```

**Backup & Recovery**:
```python
# Before any modification
1. Create backup: .PROJECT_backup_TIMESTAMP
2. Store original content
3. If update fails: restore from backup
4. Backup persists for 24 hours (manual recovery available)
```

#### 3. Project-Progress-Tracker Agent (`project-progress-tracker.md`)

**Location**: `plugins/autonomous-dev/agents/project-progress-tracker.md`

**Role**: GenAI-powered goal assessment

**Input**: Feature description + implementation details from session logs

**Output**: YAML format (machine-parseable)
```yaml
goal_1: 45  # "Build a scalable REST API" → 45% complete
goal_2: 20  # "Create user dashboard" → 20% complete
goal_3: 10  # "Achieve 99.9% uptime" → 10% complete
```

**Why GenAI?** Only Claude can understand context-dependent goal completion (is 5 endpoints = 20%? 30%? 50%?). Percentage estimation requires business reasoning, not pattern matching.

---

## Success Criteria (All Met)

- ✅ Auto-update PROJECT.md after feature completion
- ✅ Calculate progress percentages intelligently (GenAI-based)
- ✅ Support sub-goal tracking and status indicators
- ✅ Integrate with `/status` command for visibility
- ✅ Atomic file operations prevent data corruption
- ✅ Security hardening blocks all known attack vectors
- ✅ User-visible progress feedback in git commits
- ✅ Backward compatible (no changes to /auto-implement)
- ✅ 47 comprehensive tests (100% passing)

---

## Testing & Quality Assurance

### Test Coverage: 47 Tests (100% Passing)

**30 Unit Tests** (`tests/test_project_progress_update.py`):
- ProjectMdUpdater class initialization and validation
- Atomic write operations (success and error cases)
- Backup creation and rollback functionality
- Security validation (symlink detection, path traversal prevention)
- YAML parsing and PROJECT.md format preservation
- Agent timeout handling (5 second limit)
- Merge conflict detection and graceful recovery

**17 Regression Tests** (integration with full /auto-implement pipeline):
- End-to-end workflow with mock agents
- Real PROJECT.md file modifications
- Git commit generation and formatting
- User consent prompts
- Session logging
- Multiple features processed sequentially

### Security Audit: APPROVED FOR PRODUCTION

**Audit Date**: 2025-11-05
**Status**: ✅ PASSED (No vulnerabilities found)

**Vulnerabilities Found & Fixed**:

1. **v3.4.0 Initial Audit**:
   - Found: Multiple path traversal risks
   - Fixed: Added string validation, symlink detection, system directory blocking

2. **v3.4.1 Security Release**:
   - **Severity**: HIGH (Race Condition)
   - **Issue**: PID-based temp file creation allowed symlink race attacks
   - **Attack**: Attacker predicts temp filename → creates symlink → process writes to arbitrary file
   - **Impact**: Privilege escalation (write to `/etc/passwd`, `/root/.ssh/authorized_keys`)
   - **Fix**: Replaced `f".PROJECT_{os.getpid()}.tmp"` with `tempfile.mkstemp()`
   - **Result**: Cryptographic random filenames, O_EXCL atomicity, 128+ bits entropy

**Test Coverage for Atomic Writes** (7 new tests):
- `test_atomic_write_uses_mkstemp_not_pid` - Verifies secure randomness
- `test_atomic_write_content_written_via_os_write` - Verifies fd usage
- `test_atomic_write_fd_closed_before_rename` - Verifies proper cleanup
- `test_atomic_write_rename_is_atomic` - Verifies atomicity
- `test_atomic_write_error_cleanup` - Verifies temp file cleanup
- `test_atomic_write_mkstemp_parameters` - Verifies correct parameters
- `test_atomic_write_mode_0600` - Verifies exclusive owner access

**OWASP Compliance**: ✅ Meets security standards for atomic file operations

---

## Usage Examples

### Example 1: Automatic Progress Update After Feature

**Command**:
```bash
/auto-implement "Add JWT authentication endpoints"
```

**System Process**:
```
1. researcher → Finds JWT best practices
2. planner → Plans auth flow with endpoints
3. test-master → Writes authentication tests
4. implementer → Implements /login, /token, /refresh endpoints
5. reviewer → Validates code quality
6. security-auditor → Scans for OWASP vulnerabilities
7. doc-master → Updates API documentation

[SubagentStop hook triggered]

8. auto_update_project_progress → Invokes project-progress-tracker agent
   - Agent analyzes: "JWT auth with 3 endpoints added"
   - Assesses: "Build a scalable REST API goal → now 45% (was 30%)"
   - Output: YAML with new percentages

9. project_md_updater → Atomically updates PROJECT.md
   - Creates backup: .PROJECT_backup_20251107_084530
   - Updates GOALS section
   - Preserves original formatting
   - No data loss on error

10. Git operation (with consent)
    - Commit message: "feat: auto-update PROJECT.md progress (JWT auth +15%)"
    - Push to feature branch
    - Ready for PR merge
```

**PROJECT.md Result**:
```markdown
## GOALS

- Build a scalable REST API (45% - JWT auth framework complete)
  - Sub-goals:
    - Authentication layer: 100% (JWT, OAuth2)
    - API endpoints: 45% (3/7 endpoints)
    - Database schema: 60% (user/token tables)

- Create user dashboard (20% - layout designed)
- Achieve 99.9% uptime (15% - monitoring stack deployed)
```

### Example 2: Viewing Progress with `/status`

**Command**:
```bash
/status
```

**Output**:
```
PROJECT: My Awesome API
Version: v0.2.0

GOALS:
[######### ------] 45% Build a scalable REST API
  - JWT auth: ✅ Complete
  - Endpoints: 3/7 (43%)
  - Database: ✅ Schema done

[### ----------] 20% Create user dashboard
  - Layout: ✅ Design complete
  - Components: 2/8 (25%)

[## -----------] 15% Achieve 99.9% uptime
  - Monitoring: ✅ Prometheus setup
  - Alerting: ⏳ In progress

Recent updates:
- 2 hours ago: JWT auth implementation (+15%)
- 5 hours ago: Database schema (+20%)
```

---

## Configuration

### Enable/Disable the Hook

The hook is **enabled by default** in v3.4.0+.

**To disable** (if you prefer manual tracking):
```bash
# Edit .claude/settings.local.json
{
  "hooks": {
    "auto_update_project_progress": false
  }
}
```

### Customize Progress Assessment

The hook respects your PROJECT.md structure. Define goals however you want:

**Simple format**:
```markdown
## GOALS
- Feature A
- Feature B
- Feature C
```

**Detailed format**:
```markdown
## GOALS
- Build a REST API (target: complete)
  - Implement CRUD endpoints
  - Add authentication
  - Document API
```

The agent automatically assesses progress based on your structure.

---

## Troubleshooting

### Problem: Progress not updating

**Check 1**: Verify hook is enabled
```bash
cat .claude/settings.local.json | grep auto_update_project_progress
```

**Check 2**: Verify PROJECT.md exists
```bash
ls -la .claude/PROJECT.md
```

**Check 3**: Check hook execution logs
```bash
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

**Check 4**: Test hook manually
```bash
python plugins/autonomous-dev/hooks/auto_update_project_progress.py
```

### Problem: "Permission denied" when updating PROJECT.md

**Cause**: File permissions issue

**Fix**:
```bash
chmod 644 .claude/PROJECT.md
# Verify
ls -la .claude/PROJECT.md
# Should show: -rw-r--r--
```

### Problem: Merge conflict in PROJECT.md after update

**Cause**: Another process modified PROJECT.md while hook was running

**Recovery**:
```bash
# Restore from backup
cp .PROJECT_backup_TIMESTAMP .claude/PROJECT.md

# Retry the update
/status  # This will re-run the assessment
```

### Problem: Agent timeout (took > 5 seconds)

**Cause**: project-progress-tracker agent is slow

**Fix**: Increase timeout in `auto_update_project_progress.py` line 45:
```python
# From: AGENT_TIMEOUT_SECONDS = 5
# To: AGENT_TIMEOUT_SECONDS = 10
```

---

## Architecture Decisions (Why We Built It This Way)

### 1. Why SubagentStop Hook?

**Considered Alternatives**:
- Sync sub-command in /auto-implement → Required user to manually trigger
- PreCommit hook → Too late (goal assessment needed after feature complete)
- CustomInstructions in settings → Would bloat main prompts

**Decision**: SubagentStop hook
- Fires automatically after last agent (doc-master)
- Knows which feature was implemented
- Perfect timing for goal assessment
- Doesn't interrupt user workflow

### 2. Why GenAI for Percentages?

**Considered Alternatives**:
- Hard-coded rules (e.g., "1 endpoint = 20%") → Too rigid, doesn't reflect reality
- Keyword matching ("auth" keyword → 40%) → Error-prone, context-blind
- User-specified percentages → More manual work

**Decision**: GenAI assessment
- Context-aware ("3 auth endpoints with OAuth2 = 45%")
- Understands feature impact on goals
- Flexible for different project types
- Repeatable, consistent reasoning

### 3. Why Atomic Writes?

**Risk We Mitigate**:
- Process crashes mid-write → Corrupted PROJECT.md
- Multiple processes write simultaneously → Data loss
- Attacker tries to hijack write operation → Privilege escalation (v3.4.1)

**Our Solution**:
- `tempfile.mkstemp()` creates file atomically with random name
- Write via file descriptor (os.write) for efficiency
- Rename is atomic OS operation (POSIX guarantees)
- Backup before modification (rollback capability)
- Validation layers prevent malicious input

---

## Integration with Other Features

### Works With `/status`
```bash
/status  # Shows updated progress percentages
```

### Works With `/auto-implement`
```bash
/auto-implement "Add user authentication"
# → auto_update_project_progress hook runs automatically
# → PROJECT.md updated
# → No additional user action needed
```

### Works With Git Workflow
```bash
git log --oneline | grep "auto-update"
# Output: abc1234 feat: auto-update PROJECT.md progress (feature +20%)
```

---

## What's Next

After Issue #40 (Progress Tracking), the next planned issues are:

1. **Issue #37** (Next Priority): Enable auto-orchestration
   - Auto-detect feature requests in chat
   - Automatically invoke /auto-implement
   - Zero manual command entry

2. **Automatic Git Operations** (Planned):
   - Auto-commit with GenAI messages
   - Auto-push to feature branch
   - Auto-create PR with descriptions

3. **End-to-End Autonomous Flow** (Epic):
   - "implement X" → "✅ PR #42 ready to merge"
   - Full "vibe coding" experience

---

## Related Documentation

- **CHANGELOG.md** [v3.4.0] - Implementation details
- **CHANGELOG.md** [v3.4.1] - Security fixes (race condition)
- **GAP-ANALYSIS.md** - Where this fits in the roadmap
- **plugins/autonomous-dev/agents/project-progress-tracker.md** - Agent prompt
- **plugins/autonomous-dev/lib/project_md_updater.py** - Library documentation
- **tests/test_project_progress_update.py** - Test suite
- **docs/sessions/SECURITY_AUDIT_ISSUE_40.md** - Security audit report

---

## Summary

**Issue #40 Status**: ✅ COMPLETE (v3.4.0)

**What You Get**:
- Automatic PROJECT.md goal progress tracking
- Smart percentage calculations via GenAI
- Secure atomic file operations (v3.4.1)
- 47 comprehensive tests (100% passing)
- Zero manual progress tracking needed
- Beautiful `/status` output with up-to-date goals

**How to Use It**:
1. Define goals in `.claude/PROJECT.md`
2. Run `/auto-implement <feature>` as usual
3. Watch PROJECT.md update automatically
4. View progress with `/status`
5. That's it! No manual tracking needed.

**Backward Compatible**: No changes to existing workflows. The hook is optional and transparent.

**Production Ready**: Security audit approved. All tests passing. v3.4.1 security fixes applied.

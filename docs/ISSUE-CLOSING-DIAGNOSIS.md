# Issue Closing Diagnosis & Fix

**Problem Reported**: After completing feature with /auto-implement or /batch-implement, GitHub issue doesn't close automatically

**Expected**: Issue should close when feature completes successfully
**Actual**: Issue remains open

---

## Investigation Results

### ✅ Issue Closing IS Implemented

**Location**: `plugins/autonomous-dev/commands/auto-implement.md` lines 701-845

**Added**: v3.22.0 (2025-11-16)

**How it works**:
1. Extracts issue number from feature request (e.g., "issue #8", "#42", "Issue 91")
2. Prompts user for consent: "Close issue #8? [yes/no]:"
3. Validates issue exists and is open (via gh CLI)
4. Generates markdown summary with workflow metadata
5. Closes issue with `gh issue close`
6. Graceful degradation if gh CLI unavailable or network fails

**Inheritance**: `/batch-implement` calls `/auto-implement`, so inherits issue closing automatically

---

## Why It's Not Working (Root Causes)

### Issue #1: Issue Number Not Detected ❌

**Problem**: User types `/auto-implement Add JWT authentication` without mentioning issue number

**What happens**:
- No issue number in request
- auto-implement.md skips issue closing (line 722: "If no issue number is found, this step is skipped gracefully")
- Feature completes, issue stays open

**User doesn't know**: They need to include issue number in request

---

### Issue #2: Consent Prompt Declined/Missed ⚠️

**Problem**: User gets prompted "Close issue #8? [yes/no]:" but:
- Doesn't see prompt (scrolled past)
- Presses Enter without reading (defaults to "no")
- Doesn't know what to answer

**What happens**:
- User says "no" or just presses Enter
- Hook skips issue closing (graceful degradation)
- Feature completes, issue stays open

---

### Issue #3: gh CLI Not Installed ❌

**Problem**: User doesn't have gh CLI installed or authenticated

**What happens**:
- Hook tries to run `gh issue close`
- Command not found or authentication fails
- Warning shown, but user misses it
- Feature completes, issue stays open

---

### Issue #4: Issue Number in Batch File Without "issue" Keyword ⚠️

**Problem**: User creates `features.txt`:
```
72 Add JWT authentication
73 Add rate limiting
74 Add API versioning
```

**What happens**:
- Batch reads "72 Add JWT authentication"
- Calls `/auto-implement 72 Add JWT authentication`
- "72" might not match regex patterns (expects "#72" or "issue 72")
- No issue number detected
- Issue stays open

---

## Current Detection Patterns (auto-implement.md line 707-720)

```python
# Patterns that WORK:
"issue #8"  → extracts 8
"#8"        → extracts 8
"Issue 8"   → extracts 8

# Patterns that DON'T work:
"8"         → not detected (ambiguous - could be version, count, etc.)
"72 Add..." → not detected (number at start without keyword)
"GH-42"     → not detected (GitHub's own format!)
```

---

## Solutions

### Solution 1: Improve Issue Detection (Quick Fix)

**Enhance regex patterns to catch**:
- `"GH-42"` (GitHub shorthand)
- `"closes #8"`, `"fixes #8"`, `"resolves #8"` (conventional commit keywords)
- `--issue 72` (explicit flag)
- Leading numbers when using `--issues` flag

**File to modify**: `plugins/autonomous-dev/hooks/auto_git_workflow.py` (issue number extraction)

---

### Solution 2: Environment Variable for Auto-Consent (Better UX)

**Problem**: Consent prompt interrupts unattended workflows

**Fix**: Add environment variable:
```bash
# In .env or user_state.json
AUTO_CLOSE_ISSUES=true  # Default: false (opt-in like AUTO_GIT_ENABLED)
```

**Behavior**:
- First run: Prompt "Auto-close issues when feature completes? [yes/no]:"
- Store preference in `~/.autonomous-dev/user_state.json`
- Future runs: Use stored preference, no prompt
- User can override: `AUTO_CLOSE_ISSUES=false /auto-implement ...`

**Same pattern as AUTO_GIT_ENABLED** (v3.12.0)

---

### Solution 3: Batch-Implement Issue Number Propagation (Best Fix)

**Problem**: When using `--issues` flag, issue numbers aren't passed through to /auto-implement

**Current**:
```bash
/batch-implement --issues 72 73 74

# Internally becomes:
/auto-implement "Issue #72: Add JWT authentication"
/auto-implement "Issue #73: Add rate limiting"
/auto-implement "Issue #74: Add API versioning"
```

**Issue**: Format "Issue #72: ..." SHOULD be detected, but might not be if prefix causes issues

**Fix**: Ensure batch-implement formats features as:
```
"Implement issue #72: Add JWT authentication"
```

This guarantees "issue #72" pattern is detected by auto-implement.md

---

### Solution 4: Post-Batch Issue Closing Summary (Nice to Have)

**Enhancement**: After batch completes, show summary:

```
=== Batch Complete ===

Features implemented: 5
Issues processed:
  ✅ #72 - Closed automatically
  ✅ #73 - Closed automatically
  ⚠️  #74 - Failed to close (network timeout)
  ℹ️  Feature 4 - No issue number detected
  ℹ️  Feature 5 - No issue number detected

Manual cleanup needed:
  gh issue close 74 --comment "Completed via /batch-implement"
```

**File to add**: End of `/batch-implement` workflow

---

## Recommended Implementation Plan

### Phase 1: Quick Fixes (30 minutes)

1. **Improve issue detection patterns**:
   - Add `"GH-\d+"` pattern
   - Add `"closes #\d+"`, `"fixes #\d+"`, `"resolves #\d+"` patterns
   - Ensure `--issues` flag format is detected

2. **Update README with issue closing guidance**:
   - Document that issue number must be in request
   - Show examples: `/auto-implement "implement issue #72"`
   - Document `--issues` flag for batch processing

### Phase 2: Better UX (1-2 hours)

3. **Add AUTO_CLOSE_ISSUES environment variable**:
   - Same pattern as AUTO_GIT_ENABLED
   - First-run consent with persistence
   - Reduces friction for unattended workflows

4. **Improve error messaging**:
   - If no issue number detected, show: "No issue number found in request. To auto-close, include issue number: /auto-implement 'issue #72 description'"
   - If gh CLI missing, show: "Install gh CLI for automatic issue closing: brew install gh"

### Phase 3: Enhanced Features (2-3 hours)

5. **Batch summary report**:
   - Show which issues closed successfully
   - Show which issues need manual closing
   - Provide copy-paste commands for manual cleanup

6. **Retry logic for issue closing**:
   - If network timeout, retry once after 30 seconds
   - If rate limited, wait and retry
   - Better error messages for each failure mode

---

## Testing Checklist

After fixes applied:

- [ ] `/auto-implement "implement issue #72"` → closes issue #72
- [ ] `/auto-implement "Add feature for #42"` → closes issue #42
- [ ] `/auto-implement "GH-91 implementation"` → closes issue #91 (NEW)
- [ ] `/auto-implement "fixes #8 - bug in login"` → closes issue #8 (NEW)
- [ ] `/batch-implement --issues 72 73 74` → closes all 3 issues
- [ ] `/auto-implement "Add feature"` (no issue #) → graceful skip with helpful message
- [ ] AUTO_CLOSE_ISSUES=true workflow → no consent prompt, auto-closes
- [ ] AUTO_CLOSE_ISSUES=false workflow → always skips issue closing

---

## Files to Modify

1. **`plugins/autonomous-dev/hooks/auto_git_workflow.py`**:
   - Line ~100-150: Issue number extraction
   - Add patterns: GH-\d+, closes/fixes/resolves #\d+
   - Add --issue flag detection

2. **`plugins/autonomous-dev/lib/user_consent.py`** (or create if doesn't exist):
   - Add AUTO_CLOSE_ISSUES preference handling
   - First-run prompt
   - State persistence to ~/.autonomous-dev/user_state.json

3. **`plugins/autonomous-dev/commands/batch-implement.md`**:
   - Line ~400-450: Add batch summary report
   - Show issue closing status per feature
   - Provide manual cleanup commands

4. **`README.md`**:
   - Document issue closing behavior
   - Show examples with issue numbers
   - Document AUTO_CLOSE_ISSUES environment variable

---

## Documentation Updates Needed

### README.md - Add Section

```markdown
### Automatic Issue Closing

When you complete a feature that references a GitHub issue, autonomous-dev can automatically close it:

**Include issue number in request:**
```bash
/auto-implement "implement issue #72"
/auto-implement "Add feature for #42"
/auto-implement "GH-91 implementation"
/auto-implement "fixes #8 - login bug"
```

**Or use --issues flag in batch:**
```bash
/batch-implement --issues 72 73 74
# Automatically closes all 3 issues when features complete
```

**Prerequisites:**
- gh CLI installed: `brew install gh`
- Authenticated: `gh auth login`

**Auto-consent (optional):**
```bash
# In .env file
AUTO_CLOSE_ISSUES=true  # Skip consent prompt, always close
```

**What happens:**
1. Feature completes successfully
2. Tests pass, code reviewed, pushed to GitHub
3. Issue closed with summary comment:
   "Completed via /auto-implement - 7 agents passed, PR #42 created"
```

---

## Why This Matters

**Current user experience**:
1. User implements 10 features with `/batch-implement --issues 72-81`
2. All features complete successfully
3. **All 10 issues still open** (user has to manually close each one)
4. User frustrated - "I thought this was automated?"

**Improved user experience**:
1. User implements 10 features with `/batch-implement --issues 72-81`
2. AUTO_CLOSE_ISSUES=true in .env (first-run consent, then automatic)
3. All features complete successfully
4. **All 10 issues automatically closed with metadata**
5. User happy - "Truly autonomous!"

---

## Next Steps

**Immediate** (fix user's current issue):
1. Document current behavior in README
2. Show user how to include issue number
3. Verify gh CLI is installed

**Short-term** (improve UX):
1. Implement AUTO_CLOSE_ISSUES environment variable
2. Improve issue number detection patterns
3. Add batch summary report

**Long-term** (perfect the workflow):
1. Add retry logic for network failures
2. Support multiple issue references in one feature
3. Support closing issues in other repos (gh issue close org/repo#123)

---

**User can test current behavior now:**
```bash
# Should work today (v3.22.0):
/auto-implement "implement issue #72"

# At consent prompt, type: yes

# Verify:
gh issue view 72  # Should show "closed"
```

**If that works**, problem is just documentation + UX improvements needed.

**If that doesn't work**, there's a bug in the implementation to fix.

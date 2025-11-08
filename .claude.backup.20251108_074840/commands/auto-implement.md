---
description: Autonomously implement a feature with full SDLC workflow
argument-hint: Feature description (e.g., "user authentication with JWT tokens")
---

## Implementation

**You (Claude) are the coordinator for this workflow.**

Execute the following steps IN ORDER. Each step is MANDATORY - NO EXCEPTIONS.

---

### STEP 0: Validate PROJECT.md Alignment

**ACTION REQUIRED**: Before any implementation work:

1. Read `.claude/PROJECT.md` from the repository
2. Extract GOALS, SCOPE, and CONSTRAINTS sections
3. Check alignment:
   - Does the feature serve any GOAL?
   - Is the feature explicitly IN SCOPE?
   - Does the feature violate any CONSTRAINT?

**If NOT aligned**, BLOCK immediately and respond:

```
❌ BLOCKED: Feature not aligned with PROJECT.md

Feature requested: [user request]
Why blocked: [specific reason]
  - Not in SCOPE: [what scope says]
  - OR doesn't serve GOALS: [which goals]
  - OR violates CONSTRAINTS: [which constraints]

Options:
1. Modify feature to align with current SCOPE
2. Update PROJECT.md if strategy changed
3. Don't implement
```

**If aligned**, proceed to STEP 1.

---

### STEP 1: Invoke Researcher Agent

⚠️ **ACTION REQUIRED NOW**: Invoke the Task tool immediately.

**WRONG** ❌: "I will research patterns for this feature..."
**WRONG** ❌: "Based on my knowledge..."
**WRONG** ❌: "Here's what I found..."

**CORRECT** ✅: Actually invoke the Task tool with these parameters:

```
subagent_type: "researcher"
description: "Research [feature name]"
prompt: "Research patterns, best practices, and security for: [user's feature description].

Find:
- Existing implementations in this codebase
- Industry best practices
- Security considerations
- Common pitfalls
- Performance implications

Output: Summary of findings with recommendations for implementation."

model: "sonnet"
```

**DO IT NOW**. Do not proceed until researcher completes.

**After researcher completes**, VERIFY invocation succeeded:
```bash
python scripts/session_tracker.py auto-implement "Researcher completed - findings: [1-line summary]"
python scripts/agent_tracker.py status
```

⚠️ **CHECKPOINT 1**: Verify output shows "researcher" in the agent list.
If not, you FAILED to invoke the Task tool. GO BACK and actually invoke it.

---

### STEP 2: Invoke Planner Agent

⚠️ **ACTION REQUIRED**: After researcher completes, IMMEDIATELY invoke planner.

**CORRECT** ✅: Call Task tool with:

```
subagent_type: "planner"
description: "Plan [feature name]"
prompt: "Based on research findings: [summarize key points from researcher], create detailed implementation plan.

Include:
- File structure (what files to create/modify)
- Dependencies (libraries, services needed)
- Integration points (how it fits with existing code)
- Edge cases to handle
- Security considerations
- Testing strategy

Output: Step-by-step implementation plan with file-by-file breakdown."

model: "sonnet"
```

**DO IT NOW**. Don't move to STEP 3 until planner completes.

**After planner completes**, VERIFY invocation succeeded:
```bash
python scripts/session_tracker.py auto-implement "Planner completed - plan: [1-line summary]"
python scripts/agent_tracker.py status
```

⚠️ **CHECKPOINT 2**: Verify output shows both "researcher" and "planner" ran.
If count != 2, GO BACK and invoke missing agents.

---

### STEP 3: Invoke Test-Master Agent (TDD - Tests BEFORE Implementation)

⚠️ **ACTION REQUIRED**: Invoke Task tool NOW.

**This is the TDD checkpoint** - Tests MUST be written BEFORE implementation.

**CORRECT** ✅: Call Task tool with:

```
subagent_type: "test-master"
description: "Write tests for [feature name]"
prompt: "Based on implementation plan: [summarize plan], write FAILING tests FIRST (TDD red phase).

Include:
- Unit tests for core logic
- Integration tests for workflows
- Edge case tests
- Mock external dependencies
- Clear test descriptions

Output: Test files that currently FAIL (no implementation yet)."

model: "sonnet"
```

**DO IT NOW**.

**After test-master completes**, VERIFY invocation succeeded:
```bash
python scripts/session_tracker.py auto-implement "Test-master completed - tests: [count] tests written"
python scripts/agent_tracker.py status
```

⚠️ **CHECKPOINT 3 - CRITICAL TDD GATE**: Verify output shows 3 agents ran (researcher, planner, test-master).

This is the TDD checkpoint - tests MUST exist before implementation.
If count != 3, STOP and invoke missing agents NOW.

---

### STEP 4: Invoke Implementer Agent

⚠️ **ACTION REQUIRED**: Now that tests exist, implement to make them pass.

**CORRECT** ✅: Call Task tool with:

```
subagent_type: "implementer"
description: "Implement [feature name]"
prompt: "Based on:
- Plan: [summarize plan]
- Failing tests: [list test files]

Implement the feature to make ALL tests pass.

Follow:
- Existing code patterns in this codebase
- Style guidelines
- Best practices from research
- Security recommendations

Output: Implementation that makes all tests GREEN."

model: "sonnet"
```

**DO IT NOW**.

**After implementer completes**, VERIFY invocation succeeded:
```bash
python scripts/session_tracker.py auto-implement "Implementer completed - files: [list modified files]"
python scripts/agent_tracker.py status
```

⚠️ **CHECKPOINT 4**: Verify 4 agents ran. If not, invoke missing agents before continuing.

---

### STEP 5: Parallel Validation (3 Agents Simultaneously)

⚠️ **ACTION REQUIRED**: Invoke THREE validation agents in PARALLEL (single response).

**CRITICAL**: You MUST call Task tool THREE TIMES in a single response. This enables parallel execution and reduces validation time from 5 minutes to 2 minutes.

**DO NOT** invoke agents sequentially. **DO NOT** wait between invocations. Call all three NOW:

#### Validator 1: Reviewer (Quality Gate)

**Call Task tool with**:

```
subagent_type: "reviewer"
description: "Review [feature name]"
prompt: "Review implementation in: [list files].

Check:
- Code quality (readability, maintainability)
- Pattern consistency with codebase
- Test coverage (all cases covered?)
- Error handling (graceful failures?)
- Edge cases (handled properly?)
- Documentation (clear comments?)

Output: APPROVAL or list of issues to fix with specific recommendations."

model: "sonnet"
```

#### Validator 2: Security-Auditor (Security Scan)

**Call Task tool with**:

```
subagent_type: "security-auditor"
description: "Security scan [feature name]"
prompt: "Scan implementation in: [list files].

Check for:
- Hardcoded secrets (API keys, passwords)
- SQL injection vulnerabilities
- XSS vulnerabilities
- Insecure dependencies
- Authentication/authorization issues
- Input validation missing
- OWASP Top 10 compliance

Output: Security PASS/FAIL with any vulnerabilities found (severity, location, fix)."

model: "haiku"
```

#### Validator 3: Doc-Master (Documentation)

**Call Task tool with**:

```
subagent_type: "doc-master"
description: "Update docs for [feature name]"
prompt: "Update documentation for feature: [feature name].

Changed files: [list all modified/created files]

Update:
- README.md (if public API changed)
- API documentation (docstrings, comments)
- CHANGELOG.md (add entry for this feature)
- Inline code comments (explain complex logic)
- Integration examples (if applicable)

Output: All documentation files updated and synchronized."

model: "haiku"
```

**DO ALL THREE NOW IN ONE RESPONSE**.

---

### STEP 5.1: Handle Validation Results

**After all three validators complete**, analyze combined results:

```bash
python scripts/session_tracker.py auto-implement "Parallel validation completed - processing results"
python scripts/agent_tracker.py status
```

#### Check for Critical Issues (Blocking)

**Security-auditor found CRITICAL vulnerabilities?**
- ❌ BLOCK: Must fix before git operations
- Fix vulnerabilities immediately
- Re-run security-auditor to verify fix
- Continue to next check

**Security passed or no critical issues?**
- ✅ Continue to reviewer results

#### Check for Code Quality Issues (Non-Blocking)

**Reviewer requested changes?**
- ⚠️ INFORM USER: "Code review suggested improvements: [list]"
- ASK USER: "Fix now? (yes/no/later)"
  - If "yes": Fix issues, re-run reviewer
  - If "no" or "later": Continue (non-blocking)

**Reviewer approved?**
- ✅ Continue to doc-master results

#### Check Documentation Updates

**Doc-master failed to update docs?**
- ⚠️ LOG WARNING: "Documentation sync incomplete: [reason]"
- Continue (non-blocking - can fix later)

**Doc-master completed successfully?**
- ✅ All validators passed

---

### STEP 5.2: Final Agent Verification

⚠️ **CHECKPOINT 5 - VERIFY ALL 7 AGENTS RAN**:

Expected agents:
1. researcher ✅
2. planner ✅
3. test-master ✅
4. implementer ✅
5. reviewer ✅
6. security-auditor ✅
7. doc-master ✅

**Verify all 7 agents completed**:
```bash
python scripts/agent_tracker.py status
```

**If count != 7, YOU HAVE FAILED THE WORKFLOW.**

Identify which agents are missing and invoke them NOW before proceeding.

**If count == 7**: Proceed to STEP 6 (Git Operations).

---

### STEP 6: Git Operations (Consent-Based Automation)

**AFTER** all 7 agents complete successfully, offer to commit and push changes.

**IMPORTANT**: This step is OPTIONAL and consent-based. If user declines or prerequisites fail, feature is still successful (graceful degradation).

#### Check Prerequisites

Before offering git automation, verify:

```python
from git_operations import validate_git_repo, check_git_config

# Check git is available
is_valid, error = validate_git_repo()
if not is_valid:
    # Log warning but continue
    print(f"⚠️  Git automation unavailable: {error}")
    print("✅ Feature complete! Commit manually when ready.")
    # SKIP to Step 9

# Check git config
is_configured, error = check_git_config()
if not is_configured:
    # Log warning but continue
    print(f"⚠️  Git config incomplete: {error}")
    print("Set with: git config --global user.name 'Your Name'")
    print("         git config --global user.email 'your@email.com'")
    print("✅ Feature complete! Commit manually when ready.")
    # SKIP to Step 9
```

#### Offer Commit and Push (User Consent Required)

If prerequisites passed, ask user for consent:

```
✅ Feature implementation complete!

Would you like me to commit and push these changes?

📝 Commit message: "feat: [feature name]

Implemented by /auto-implement pipeline:
- [1-line summary of what changed]
- Tests: [count] tests added/updated
- Security: Passed audit
- Docs: Updated [list]"

🔄 Actions:
1. Stage all changes (git add .)
2. Commit with message above
3. Push to remote (branch: [current_branch])

Reply 'yes' to commit and push, 'commit-only' to commit without push, or 'no' to skip git operations.
```

#### Execute Based on User Response

**If user says "yes" or "y"**:
```python
from git_operations import auto_commit_and_push

result = auto_commit_and_push(
    commit_message=commit_msg,
    branch=current_branch,
    push=True
)

if result['success'] and result['pushed']:
    print(f"✅ Committed ({result['commit_sha']}) and pushed to {current_branch}")
elif result['success']:
    print(f"✅ Committed ({result['commit_sha']})")
    print(f"⚠️  Push failed: {result['error']}")
    print("Push manually with: git push")
else:
    print(f"❌ Commit failed: {result['error']}")
    print("Commit manually when ready")
```

**If user says "commit-only" or "commit"**:
```python
from git_operations import auto_commit_and_push

result = auto_commit_and_push(
    commit_message=commit_msg,
    branch=current_branch,
    push=False  # Don't push
)

if result['success']:
    print(f"✅ Committed ({result['commit_sha']})")
    print("Push manually with: git push")
else:
    print(f"❌ Commit failed: {result['error']}")
    print("Commit manually when ready")
```

**If user says "no" or "n"**:
```
✅ Feature complete! Changes ready to commit.

Commit manually when ready:
  git add .
  git commit -m "feat: [feature name]"
  git push
```

#### Error Handling (Graceful Degradation)

Handle common errors gracefully:

**Merge conflict detected**:
```
❌ Cannot commit: Merge conflict detected in: [files]

Resolve conflicts first:
1. Edit conflicted files
2. Run: git add .
3. Run: git commit

Feature implementation is complete - just needs manual conflict resolution.
```

**Detached HEAD state**:
```
❌ Cannot commit: Repository is in detached HEAD state

Create a branch first:
  git checkout -b [branch-name]

Feature implementation is complete - just needs to be on a branch.
```

**Network timeout during push**:
```
✅ Committed successfully: [sha]
❌ Push failed: Network timeout

Try pushing manually:
  git push

Feature is committed locally - just needs to reach remote.
```

**Protected branch**:
```
✅ Committed successfully: [sha]
❌ Push failed: Branch '[branch]' is protected

Create a feature branch and push there:
  git checkout -b feature/[name]
  git cherry-pick [sha]
  git push -u origin feature/[name]

Or push manually if you have override permissions.
```

#### Philosophy: Always Succeed

Git operations are a **convenience, not a requirement**.

- Feature implemented? ✅ SUCCESS
- Tests passing? ✅ SUCCESS
- Security audited? ✅ SUCCESS
- Docs updated? ✅ SUCCESS

**Commit fails?** Still SUCCESS - user commits manually.
**Push fails?** Still SUCCESS - commit worked, push manually.
**Git not available?** Still SUCCESS - feature is done.

This is **graceful degradation** - automate where possible, but never block success on automation.

---

### STEP 7: Report Completion

**ONLY AFTER** confirming all 7 agents ran (checkpoint 5 passed), tell the user:

```
✅ Feature complete! All 7 agents executed successfully.

📊 Pipeline Summary:
1. researcher: [1-line summary]
2. planner: [1-line summary]
3. test-master: [1-line summary]
4. implementer: [1-line summary]
5. reviewer: [1-line summary]
6. security-auditor: [1-line summary]
7. doc-master: [1-line summary]

📁 Files changed: [count] files
🧪 Tests: [count] tests created/updated
🔒 Security: [PASS/FAIL with findings if any]
📖 Documentation: [list docs updated]

🎯 Next steps:
1. Run `/pipeline-status` to see full execution details
2. Review agent outputs in docs/sessions/ if needed
3. Run `/clear` before starting next feature (mandatory for performance)

Feature is ready to commit!
```

---

## Mandatory Full Pipeline Policy

⚠️ **ALL features MUST go through all 7 agents. NO EXCEPTIONS.**

**Why**:
- Simulation proved even "simple" features need full pipeline
- test-master: Created 47 tests (0% → 95% coverage)
- security-auditor: Found CRITICAL vulnerability (CVSS 7.1)
- doc-master: Updated 5 files, not just 1

**Examples from real simulation**:
- "Simple command file" → security-auditor found path traversal attack
- "Trivial doc update" → doc-master found 5 files needing consistency updates
- "Quick fix" → reviewer caught pattern violations

**Result**: Full pipeline prevents shipping bugs, vulnerabilities, and incomplete features.

**Exception**: If you believe a feature genuinely needs < 7 agents, ASK USER FIRST:

"This seems like a simple change. Should I run:
1. Full 7-agent pipeline (recommended - guaranteed quality)
2. Subset: [which agents you think are needed]

Default is FULL PIPELINE if you don't specify."

Let user decide. But recommend full pipeline.

---

## Context Management

- **After feature completes**: Prompt user to run `/clear` before next feature
- **Log efficiently**: Record file paths, not full content
- **If approaching token limit**: Save state and ask user to continue in new session

---

## What This Command Does (User-Facing Documentation)

**For users**: This command provides autonomous feature implementation with full SDLC workflow:

1. **Validates alignment** - Checks PROJECT.md to ensure feature fits project goals
2. **Invokes 7 specialist agents** - Each handles one part of SDLC:
   - researcher: Finds patterns and best practices
   - planner: Designs implementation approach
   - test-master: Writes tests FIRST (TDD)
   - implementer: Makes tests pass
   - reviewer: Quality gate
   - security-auditor: Finds vulnerabilities
   - doc-master: Updates documentation
3. **Verifies completeness** - Ensures all 7 agents ran before declaring done
4. **Ready to commit** - All quality gates passed

**Time**: 20-40 minutes for professional-quality feature

**Output**:
- Implementation code
- Comprehensive tests
- Security audit report
- Updated documentation
- Pipeline log showing all agents ran

**Workflow**:
```bash
/auto-implement "add user authentication"
# ... 7 agents execute ...
# ✅ Feature complete!

/pipeline-status  # Verify all 7 agents ran
/clear            # Reset context for next feature
```

---

## Troubleshooting

**If fewer than 7 agents ran**:
```bash
/pipeline-status
# Shows: "5 agents ran" (missing test-master, security-auditor)

# Solution: Re-run /auto-implement
# Claude will invoke missing agents
```

**If agent fails**:
- Claude will report the failure
- Review error in docs/sessions/
- Fix the issue
- Re-run /auto-implement (idempotent)

**If alignment blocked**:
- Either modify feature to fit PROJECT.md scope
- Or update PROJECT.md if strategy changed
- Then re-run /auto-implement

---

## Related Commands

- `/pipeline-status` - View agent execution details
- `/status` - Check PROJECT.md goal progress
- `/health-check` - Verify plugin integrity
- `/clear` - Reset context (run after each feature)

---

**Philosophy**: This command embodies "not a toolkit, a team" - You describe what you want, Claude coordinates 7 specialists to build it professionally.

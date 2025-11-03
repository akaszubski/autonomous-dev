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

### STEP 5: Invoke Reviewer Agent

⚠️ **ACTION REQUIRED**: Quality gate - independent code review.

**CORRECT** ✅: Call Task tool with:

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

**DO IT NOW**.

**After reviewer completes**, VERIFY invocation succeeded:
```bash
python scripts/session_tracker.py auto-implement "Reviewer completed - verdict: [APPROVED/CHANGES REQUESTED]"
python scripts/agent_tracker.py status
```

⚠️ **CHECKPOINT 5**: Verify 5 agents ran. If not, invoke missing agents before continuing.

**If reviewer requests changes**: Fix them now, then re-run reviewer.

---

### STEP 6: Invoke Security-Auditor Agent

⚠️ **ACTION REQUIRED**: Security scan - catch vulnerabilities BEFORE shipping.

**CORRECT** ✅: Call Task tool with:

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

**DO IT NOW**.

**After security-auditor completes**, VERIFY invocation succeeded:
```bash
python scripts/session_tracker.py auto-implement "Security-auditor completed - status: [PASS/FAIL + findings]"
python scripts/agent_tracker.py status
```

⚠️ **CHECKPOINT 6**: Verify 6 agents ran. If not, invoke missing agents before continuing.

**If security issues found**: Fix them NOW before proceeding.

---

### STEP 7: Invoke Doc-Master Agent

⚠️ **FINAL STEP**: Update all documentation.

**CORRECT** ✅: Call Task tool with:

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

**DO IT NOW**.

**After doc-master completes**, PERFORM FINAL VERIFICATION:
```bash
python scripts/session_tracker.py auto-implement "Doc-master completed - docs: [list files updated]"
python scripts/agent_tracker.py status
```

⚠️ **CHECKPOINT 7 - FINAL VERIFICATION**: Verify ALL 7 agents ran successfully:

Expected agents:
1. researcher ✅
2. planner ✅
3. test-master ✅
4. implementer ✅
5. reviewer ✅
6. security-auditor ✅
7. doc-master ✅

**If count != 7, YOU HAVE FAILED THE WORKFLOW.**

Identify which agents are missing:
```bash
python scripts/agent_tracker.py status
```

Invoke missing agents NOW before telling user you're done.

---

### STEP 8: Report Completion

**ONLY AFTER** confirming all 7 agents ran (checkpoint 7 passed), tell the user:

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

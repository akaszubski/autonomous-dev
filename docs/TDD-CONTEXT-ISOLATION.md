# TDD Context Isolation: File-Based Handoff

**Last Updated**: 2025-12-09
**Related**: [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md) | [AGENTS.md](AGENTS.md)

---

## Executive Summary

autonomous-dev enforces **true TDD discipline** through architectural context isolation. When `/auto-implement` runs:

1. **test-master** writes tests to disk in its own context
2. **implementer** runs in a separate context, reading only test files

The implementer never sees test-master's reasoning, planning notes, or expectations. It only sees the test files themselves. This prevents "overfitting" - where the implementer implements beyond what tests actually verify.

**Key insight**: Context isolation isn't enforced by instructions ("don't look at this"). It's enforced by architecture (separate Task invocations = separate contexts).

---

## The Problem: Context Pollution

### Traditional TDD with AI

In most AI-assisted development workflows:

```
Same Context:
┌─────────────────────────────────────────┐
│  "Write tests for user authentication" │
│  → AI writes tests with reasoning      │
│  → AI sees its own reasoning           │
│  → AI implements based on reasoning    │
│  → Implementation overfits to intent   │
└─────────────────────────────────────────┘
```

The AI "knows" what the tests are supposed to do from its own planning. It implements not just what the tests verify, but what it intended to verify. This breaks the TDD discipline of "write only what's needed to make tests pass."

### Real Example of Overfitting

**Test written**:
```python
def test_user_can_login():
    user = create_user("test@example.com", "password123")
    result = login(user.email, "password123")
    assert result.success == True
```

**With context pollution** (AI remembers planning):
```python
# AI "knows" it was planning for rate limiting, so adds it
def login(email: str, password: str) -> LoginResult:
    check_rate_limit(email)  # Not tested!
    check_ip_blacklist()     # Not tested!
    user = get_user(email)
    if verify_password(user, password):
        log_successful_login(user)  # Not tested!
        return LoginResult(success=True)
    return LoginResult(success=False)
```

**Without context pollution** (pure TDD):
```python
# AI only sees test, implements minimum
def login(email: str, password: str) -> LoginResult:
    user = get_user(email)
    if verify_password(user, password):
        return LoginResult(success=True)
    return LoginResult(success=False)
```

The first implementation has 3 untested features. The second has 100% coverage of implemented code.

---

## The Solution: File-Based Handoff

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claude Coordinates                          │
│                   (auto-implement.md)                           │
└──────────────────┬──────────────────────────┬───────────────────┘
                   │                          │
                   │ Task(test-master)        │ Task(implementer)
                   │                          │
                   ▼                          ▼
        ┌──────────────────┐       ┌──────────────────┐
        │   CONTEXT A      │       │   CONTEXT B      │
        │   test-master    │       │   implementer    │
        │                  │       │                  │
        │   Receives:      │       │   Receives:      │
        │   - Plan summary │       │   - Plan summary │
        │   - Feature desc │       │   - Test FILES   │
        │                  │       │                  │
        │   Outputs:       │       │   Does NOT see:  │
        │   - Test files   │       │   - test-master  │
        │   - Session log  │       │     reasoning    │
        └────────┬─────────┘       └────────┬─────────┘
                 │                          │
                 │    File System           │
                 │    (Handoff Point)       │
                 ▼                          ▼
        ┌─────────────────────────────────────────┐
        │            tests/test_*.py              │
        │                                         │
        │   Written by test-master                │
        │   Read by implementer                   │
        │   Contains ONLY executable assertions   │
        └─────────────────────────────────────────┘
```

### The Task Tool Creates Isolation

When `/auto-implement` invokes agents:

```python
# STEP 2: test-master runs in Context A
Task(
    subagent_type="test-master",
    prompt="Write failing tests for [feature]..."
)
# test-master completes, Context A ends

# STEP 3: implementer runs in Context B
Task(
    subagent_type="implementer",
    prompt="Make tests pass. Run: pytest -v to see failing tests..."
)
# implementer never sees Context A's reasoning
```

Each `Task()` invocation creates a fresh context. The only shared information is:
1. The high-level plan summary (from planner)
2. Files on disk (test files written by test-master)

---

## Technical Implementation

### test-master Phase (Red)

From `auto-implement.md` Step 2:

```markdown
subagent_type: "test-master"
prompt: "Based on implementation plan: [summary], write FAILING tests FIRST.

Include:
- Unit tests for core logic
- Integration tests for workflows
- Edge case tests

Output: Test files that currently FAIL (no implementation yet)."
```

**Key behaviors**:
- Writes tests to `tests/` directory
- Runs `pytest --tb=line -q` to verify tests fail
- Logs completion to session file
- Context ends when Task completes

### implementer Phase (Green)

From `auto-implement.md` Step 3:

```markdown
subagent_type: "implementer"
prompt: "Based on:
- Plan: [summary]
- Failing tests: Run `pytest -v` to see failing tests

Implement the feature to make ALL tests pass."
```

**Key behaviors**:
- Reads test files from disk (not from context)
- Runs tests to discover what's failing
- Implements minimum code to pass tests
- Never sees test-master's reasoning or planning

### Session File Communication

Agents communicate status via session files (not context):

```bash
# test-master logs completion
python scripts/session_tracker.py test-master "47 tests created - RED phase"

# implementer can check session if needed
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

Session files contain:
- Timestamps
- Agent names
- Completion messages
- File paths modified

Session files do NOT contain:
- Detailed reasoning
- Planning notes
- Internal context

---

## Verification

### Checkpoint System

`auto-implement.md` includes verification checkpoints:

```bash
# Verify both agents ran
python plugins/autonomous-dev/scripts/agent_tracker.py status

# Expected output:
# researcher: completed
# planner: completed
# test-master: completed  ← RED phase
# implementer: completed  ← GREEN phase
```

### Manual Verification

To verify isolation worked:

1. **Check session logs**:
   ```bash
   cat docs/sessions/$(ls -t docs/sessions/ | head -1)
   ```
   Should show separate entries for test-master and implementer.

2. **Inspect test coverage**:
   ```bash
   pytest --cov=src --cov-report=term-missing
   ```
   High coverage suggests implementer didn't add untested code.

3. **Review commit diff**:
   Implementation should closely match test requirements, not exceed them.

---

## Benefits

| Aspect | With Context Pollution | With File-Based Handoff |
|--------|----------------------|------------------------|
| Test coverage | 60-80% (untested features) | 95-100% (only tested code) |
| Implementation size | Larger (includes planned features) | Minimal (only what's tested) |
| TDD discipline | Violated (knows intent) | Enforced (only sees tests) |
| Debugging | Harder (mystery code) | Easier (all code is tested) |
| Refactoring safety | Risky (untested paths) | Safe (comprehensive tests) |

### Real-World Impact

From autonomous-dev session data:
- **test-master** typically creates 20-50 tests per feature
- **implementer** achieves 90%+ coverage on new code
- Untested "bonus" features: ~0 (vs. 3-5 with shared context)

---

## Trade-offs

### What We Gain
- True TDD discipline (architectural enforcement)
- Higher test coverage (implementer can't skip tests)
- Cleaner implementations (no feature creep)
- Easier debugging (all code paths tested)

### What We Accept
- Slightly longer execution (two separate agent invocations)
- Plan must be summarized for both agents
- Complex features need clear test contracts
- Implementer may need multiple iterations if tests are unclear

---

## Common Questions

**Q: Can implementer see ANY of test-master's work?**
A: Only the test files themselves. Not the reasoning, not the planning notes, not why certain tests were written.

**Q: What if implementer needs context about WHY a test exists?**
A: Tests should be self-documenting. If test intent is unclear, that's a test quality issue. Implementer should make tests pass, not interpret intent.

**Q: Does this slow down development?**
A: Slightly (separate invocations). But the quality improvement (100% coverage vs 70%) saves debugging time later.

**Q: What about the planner's context?**
A: Both test-master and implementer receive a summary of the plan. This is intentional - they need to know WHAT to build, just not each other's internal reasoning about HOW.

---

## References

- [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md) - Overall system design
- [AGENTS.md](AGENTS.md) - Agent responsibilities
- [auto-implement.md](../plugins/autonomous-dev/commands/auto-implement.md) - Workflow implementation
- [testing-guide skill](../plugins/autonomous-dev/skills/testing-guide/SKILL.md) - TDD methodology

---

*This pattern is unique to autonomous-dev. Most AI frameworks share context between test-writing and implementation. We chose architectural enforcement over instructional discipline.*

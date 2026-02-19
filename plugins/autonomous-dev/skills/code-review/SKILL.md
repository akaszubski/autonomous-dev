---
name: code-review
version: 1.0.0
type: knowledge
description: Enforcement skill for consistent, thorough code reviews
keywords: [review, approve, request-changes, code-quality, checklist]
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash]
---

# Code Review Enforcement Skill

Ensures every code review is thorough, consistent, and produces actionable feedback. Used by the reviewer agent.

## 10-Point Review Checklist

Every review MUST evaluate all 10 items. No shortcuts.

### 1. Correctness
- Does the code do what the ticket/plan requires?
- Are edge cases handled (empty input, None, boundary values)?
- Are return types consistent with declarations?

### 2. Test Coverage
- Do tests exist for new/changed code?
- Do ALL tests pass (100%, not "most")?
- Are edge cases and error paths tested?

### 3. Error Handling
- Are exceptions specific (not bare `except:`)?
- Do error messages include context (what failed, what was expected)?
- Is there graceful degradation where appropriate?

### 4. Type Hints on Public APIs
- All public functions have parameter and return type annotations?
- Complex types use `Optional`, `Union`, `List`, `Dict` correctly?

### 5. Naming Conventions
- Variables/functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Names are descriptive (no single-letter except loop vars)

### 6. Security
- No hardcoded secrets, API keys, or passwords
- No bare `except:` that swallows errors silently
- SQL queries use parameterized statements
- User input is validated before use

### 7. Style Compliance
- Code is formatted with black (100 char line length)
- Imports sorted with isort
- No unused imports or variables

### 8. Documentation
- Public APIs have Google-style docstrings
- Complex logic has inline comments
- Examples provided for non-obvious usage

### 9. No Stubs or Placeholders
- No `NotImplementedError` in shipped code
- No `pass` as the sole body of a function
- No `TODO` without a linked issue number

### 10. No Unnecessary Complexity
- No premature abstraction
- No dead code paths
- Functions do one thing
- Nesting depth <= 3 levels

---

## Severity Levels

### BLOCKING (must fix before approval)
- Failing tests
- Security vulnerabilities (hardcoded secrets, SQL injection)
- Missing error handling on external calls
- Stubbed/placeholder code
- Incorrect logic or data loss risk

### ADVISORY (prefix with "Nit:")
- Style preferences beyond black/isort
- Alternative naming suggestions
- Minor documentation improvements
- Performance micro-optimizations

---

## HARD GATE: Required Output

Every review MUST conclude with exactly one of:
- **APPROVED** — all 10 checklist items pass, no BLOCKING issues
- **REQUEST_CHANGES** — at least one BLOCKING issue found

**FORBIDDEN**:
- Saying "looks good" without running the full checklist
- Approving code with failing tests
- Approving stubbed or placeholder code
- Approving without checking security items (checklist #6)
- Mixing BLOCKING and ADVISORY without clear labels
- Rubber-stamping: approving in under 30 seconds of analysis

**REQUIRED**:
- Per-file summary with specific line references for each finding
- Explicit pass/fail on each of the 10 checklist items
- Test results included (run `pytest` and report output)
- Security checklist explicitly addressed
- BLOCKING vs ADVISORY clearly labeled on every finding

---

## Required Output Format

```
## Review: [file or PR title]

### Checklist
1. Correctness: PASS/FAIL — [details]
2. Test Coverage: PASS/FAIL — [details]
3. Error Handling: PASS/FAIL — [details]
4. Type Hints: PASS/FAIL — [details]
5. Naming: PASS/FAIL — [details]
6. Security: PASS/FAIL — [details]
7. Style: PASS/FAIL — [details]
8. Documentation: PASS/FAIL — [details]
9. No Stubs: PASS/FAIL — [details]
10. Complexity: PASS/FAIL — [details]

### Findings
- [BLOCKING] file.py:42 — description
- [Nit:] file.py:88 — suggestion

### Test Results
[paste pytest output summary]

### Verdict: APPROVED / REQUEST_CHANGES
```

---

## Anti-Patterns

### BAD: Rubber-stamp approval
```
"Looks good to me, ship it!"
```
Missing: checklist, line references, test results, security review.

### GOOD: Structured review
```
## Review: lib/auth.py

### Checklist
1. Correctness: PASS — token validation logic matches RFC 7519
2. Test Coverage: PASS — 12 tests, all pass, covers expiry edge case
...
6. Security: FAIL — API key on line 34 is hardcoded

### Findings
- [BLOCKING] auth.py:34 — Hardcoded API key, move to env var

### Verdict: REQUEST_CHANGES
```

### BAD: Nitpicking style, missing logic bugs
Spending 10 comments on variable naming while an off-by-one error goes unnoticed.

### BAD: "Will fix later" acceptance
Approving with known BLOCKING issues and a verbal promise to fix. If it is BLOCKING, it blocks.

---

## Cross-References

- **python-standards**: Style and type hint requirements
- **testing-guide**: Test coverage expectations
- **security-patterns**: Security checklist details

---
description: Complete pre-release validation - all tests + GenAI UX + architecture (5-10min)
---

# Complete Pre-Release Validation

**Full validation suite before production release**

---

## Usage

```bash
/test-complete
```

**Time**: 5-10 minutes
**Tools**: pytest + Claude (GenAI)
**Scope**: Everything - automated tests + GenAI validation

---

## What This Does

Runs complete validation in sequence:

1. **Automated Tests** (pytest)
   - Unit tests (< 1s)
   - Integration tests (< 10s)
   - UAT tests (< 60s)

2. **GenAI UX Validation** (2-5min)
   - Goal alignment
   - UX friction points
   - Error handling quality
   - Performance assessment

3. **GenAI Architecture Validation** (2-5min)
   - PROJECT.md alignment
   - Architectural drift detection
   - Optimization opportunities
   - Principle compliance

**Total**: All quality gates

---

## Expected Output

```
Running Complete Pre-Release Validation...

┌─ Phase 1: Automated Tests ──────────────────┐
│  ✅ Unit: 45/45 passed (0.8s)                │
│  ✅ Integration: 12/12 passed (4.2s)         │
│  ✅ UAT: 8/8 passed (15.3s)                  │
│  ✅ Coverage: 92% (target: 80%+)             │
│  Total: 65/65 tests passed                   │
└──────────────────────────────────────────────┘

┌─ Phase 2: GenAI UX Validation ──────────────┐
│  Overall Score: 8.5/10                       │
│  ✅ Goal Alignment: Excellent                │
│  ✅ Error Handling: Strong                   │
│  ⚠️  2 UX friction points found              │
│     1. Export progress (medium priority)     │
│     2. Form validation (low priority)        │
└──────────────────────────────────────────────┘

┌─ Phase 3: Architecture Validation ──────────┐
│  Overall Alignment: 95%                      │
│  ✅ PROJECT.md-first: Enforced               │
│  ✅ Agent pipeline: Correct                  │
│  ✅ Context management: Working              │
│  ⚠️  1 optimization opportunity              │
│     1. Reviewer agent model (low priority)   │
└──────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RELEASE READINESS SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Status: ✅ READY FOR RELEASE (with 3 tracked improvements)

Automated Tests: ✅ 100% passing
Coverage: ✅ 92% (exceeds 80% target)
UX Quality: ✅ 8.5/10 (strong)
Architecture: ✅ 95% aligned

Findings Tracked:
- 2 UX friction points (medium/low priority)
- 1 optimization opportunity (low priority)

Total Time: 7m 23s

💡 Create GitHub issues for findings?
   Run: /issue-auto

✅ Ready to proceed with /commit-release
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## When to Use

- ✅ Before production releases
- ✅ Pre-release validation (final gate)
- ✅ Major milestone verification
- ✅ In `/commit-release` (Level 4 release)

---

## Release Criteria

**Must pass**:
- ✅ All automated tests (100%)
- ✅ Coverage ≥ 80%
- ✅ No critical security issues
- ✅ UX score ≥ 7.0/10
- ✅ Architecture alignment ≥ 90%

**If any fails** → Release blocked

**Warnings OK** (tracked as issues):
- Medium/low priority UX friction
- Optimization opportunities
- Documentation suggestions

---

## Issue Tracking

**Auto-create GitHub issues** for findings:
```bash
/test-complete
# Then run:
/issue-auto
```

All findings (UX friction + architectural drift) become tracked issues.

---

## Comparison to Individual Tests

| Command | Time | Scope | Use For |
|---------|------|-------|---------|
| `/test` | 60s | Automated only | Daily dev |
| `/test-uat-genai` | 3min | UX only | UX validation |
| `/test-architecture` | 3min | Architecture only | Alignment check |
| `/test-complete` | 7min | Everything | Pre-release gate |

---

## Related Commands

- `/test` - All automated tests (< 60s)
- `/test-uat-genai` - GenAI UX validation only (2-5min)
- `/test-architecture` - GenAI architecture validation only (2-5min)
- `/commit-release` - Production release (includes /test-complete)
- `/issue-auto` - Create issues from findings

---

**Use this as the final quality gate before production release. Most comprehensive validation.**

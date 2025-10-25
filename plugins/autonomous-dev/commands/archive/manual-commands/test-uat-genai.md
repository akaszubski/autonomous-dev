---
description: GenAI UX validation - analyze user experience quality & goal alignment (2-5min)
---

# UAT GenAI Validation

**Comprehensive UX quality analysis with Claude (GenAI)**

---

## Usage

```bash
/test-uat-genai
```

**Time**: 2-5 minutes
**Tool**: Claude (GenAI analysis)
**Scope**: User experience, goal alignment, UX friction

---

## What This Does

Uses Claude to analyze:
- ✅ **Goal alignment** (from PROJECT.md)
- ✅ **UX quality** (friction points, clarity)
- ✅ **Error handling** quality
- ✅ **Performance** vs targets
- ✅ **Accessibility** considerations

**Process**:
1. Read PROJECT.md for goals
2. Analyze user workflows (code, docs, tests)
3. Identify UX friction points
4. Assess goal alignment
5. Generate UX score (X/10) + recommendations

---

## Expected Output

```
Running GenAI UAT Validation...

Analyzing user workflows...
Reading PROJECT.md goals...
Evaluating UX quality...

┌─ UX Quality Report ──────────────────────────┐
│                                              │
│ Overall Score: 8.5/10                        │
│                                              │
│ ✅ Goal Alignment: Excellent                 │
│    All workflows support stated goals        │
│                                              │
│ ✅ Error Handling: Strong                    │
│    Clear error messages with recovery        │
│                                              │
│ ⚠️  UX Friction Points Found: 2              │
│                                              │
│ 1. Export Progress (Medium Priority)         │
│    - No progress indicator for large exports │
│    - Users don't know if it's working        │
│    - Recommendation: Add progress bar        │
│                                              │
│ 2. Form Validation (Low Priority)            │
│    - Validation happens on submit only       │
│    - Recommendation: Add real-time hints     │
│                                              │
│ 📊 Metrics:                                  │
│    - Average workflow time: 3.2s             │
│    - Error recovery: 95% success             │
│    - Accessibility: WCAG 2.1 AA compliant    │
│                                              │
└──────────────────────────────────────────────┘

💡 Would you like me to create GitHub issues for these findings?
   Run: /issue-auto
```

---

## Validation Criteria

**Goal Alignment** (from PROJECT.md):
- Do workflows support stated goals?
- Are constraints respected?
- Is scope appropriate?

**UX Quality**:
- Friction points (confusion, delays, errors)
- Clarity (UI text, error messages, help)
- Efficiency (steps required, speed)

**Error Handling**:
- Clear error messages
- Recovery paths
- Prevention mechanisms

**Performance**:
- Response times
- Loading indicators
- Perceived performance

**Accessibility**:
- Keyboard navigation
- Screen reader support
- Color contrast

---

## When to Use

- ✅ Before feature release
- ✅ After UX changes
- ✅ Pre-production validation
- ✅ In `/commit-push` (Level 3 push commit)
- ✅ In `/test-complete` (pre-release)

---

## Issue Tracking

**Auto-create GitHub issues**:
```bash
/test-uat-genai
# Then run:
/issue-auto
```

Each UX friction point becomes a tracked issue with:
- Priority (high/medium/low)
- Recommendation
- User impact
- Code locations

---

## Related Commands

- `/test-uat` - Automated UAT tests (< 60s) - Fast but less comprehensive
- `/test-architecture` - GenAI architectural validation (2-5min)
- `/test-complete` - Complete pre-release (all + GenAI)
- `/issue-auto` - Create issues from findings

---

**Use this for comprehensive UX validation before release. More thorough than automated tests.**

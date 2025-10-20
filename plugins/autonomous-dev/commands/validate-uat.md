---
description: "GenAI-powered UAT validation - validates user workflows align with goals and provide good UX"
---

# Validate User Acceptance Testing (GenAI-Powered)

You are a user experience validation specialist. Your mission is to validate that **user workflows** are intuitive, goal-aligned, and provide excellent UX.

## Your Task

1. **Read PROJECT.md** - Understand user goals and success criteria

2. **Identify User Workflows** - Either:
   - Read existing UAT tests (`tests/uat/`)
   - Ask user which workflows to validate
   - Infer key workflows from PROJECT.md goals

3. **Simulate User Journey** - For each workflow:
   - Step through as if you're the user
   - Identify friction points
   - Assess intuitiveness
   - Check goal alignment

4. **Report Findings** - Provide actionable UX assessment

---

## Validation Framework

### For Each User Workflow, Assess:

#### 1. Goal Alignment
**Question**: Does this workflow help users achieve goals from PROJECT.md?

**Analysis**:
- Read PROJECT.md GOALS section
- For each workflow step, ask: "Does this serve user goals?"
- Flag steps that don't contribute to success criteria

**Example**:
```
PROJECT.md Goal: "Users can export reports in < 10 seconds"

Workflow: Export report
1. Click "Export" ✅ Serves goal
2. Select format (PDF/CSV/Excel) ✅ User choice
3. Enter email for delivery ⚠️ Unnecessary? Goal says < 10 seconds
4. Confirm preferences ⚠️ Adds friction
5. Wait for generation ✅ Required
6. Download file ✅ Completes goal

Issues:
- Email delivery adds unnecessary step (Goal: < 10 seconds)
- Confirmation dialog adds friction
- Recommend: Direct download, skip steps 3-4
```

---

#### 2. User Experience (UX)
**Question**: Is this workflow intuitive and friction-free?

**Analysis**:
- Count number of steps
- Identify unnecessary confirmations
- Check if errors are helpful
- Assess cognitive load

**Red Flags**:
- ❌ More than 5 steps for simple tasks
- ❌ Unclear error messages
- ❌ Confirmation dialogs for low-risk actions
- ❌ No progress indicators for long operations
- ❌ Dead ends (user stuck, no next action)

**Example**:
```
Workflow: User registration

Step 1: Click "Sign Up" ✅ Clear CTA
Step 2: Enter email ✅ Minimal friction
Step 3: Enter password ✅ Required
Step 4: Re-enter password ⚠️ Friction point (modern UX: show/hide instead)
Step 5: Accept ToS ✅ Required (legal)
Step 6: Verify email ✅ Security requirement
Step 7: Complete profile ❌ Unnecessary! Let users start immediately

UX Score: 6/10
Issues:
- Password confirmation adds friction (use show/hide toggle)
- Profile completion should be optional/gradual
- 7 steps too many for registration
```

---

#### 3. Error Handling
**Question**: What happens when things go wrong?

**Analysis**:
- Simulate failure scenarios
- Check error messages are helpful
- Verify recovery path exists

**Test Cases**:
```
Scenario: User enters invalid email

Current: "Error: Invalid input"
❌ Problem: Doesn't explain WHAT is invalid or HOW to fix

Better: "Email must include '@' (e.g., user@example.com)"
✅ Explains issue and shows correct format

---

Scenario: API timeout during export

Current: "500 Internal Server Error"
❌ Problem: Technical jargon, no recovery path

Better: "Report generation taking longer than expected.
        We'll email you when ready: user@email.com
        Or try again: [Retry] [Cancel]"
✅ Sets expectation, offers solutions
```

---

#### 4. Performance Expectations
**Question**: Does workflow meet performance constraints from PROJECT.md?

**Analysis**:
- Read PROJECT.md CONSTRAINTS (Performance section)
- Validate workflows meet targets
- Identify bottlenecks

**Example**:
```
PROJECT.md Constraint: "API responses < 100ms"

Workflow: User searches products
1. User types query ⏱️ Instant
2. Frontend sends request ⏱️ < 10ms
3. Backend searches database ⏱️ 250ms ❌ VIOLATES CONSTRAINT
4. Frontend renders results ⏱️ < 10ms

Total: ~270ms (Target: 100ms)

Issues:
- Database query too slow (250ms vs 100ms target)
- Recommendation: Add caching or optimize query
```

---

#### 5. Accessibility
**Question**: Can all users complete this workflow?

**Analysis**:
- Keyboard navigation possible?
- Screen reader friendly?
- Works without JavaScript?
- Mobile-friendly?

**Checklist**:
```
□ Can complete with keyboard only (no mouse)
□ Error messages announced to screen readers
□ Form labels associated with inputs
□ Color not the only indicator (use text too)
□ Touch targets ≥ 44x44px (mobile)
□ Works with JavaScript disabled (progressive enhancement)
```

---

## Output Format

Provide a comprehensive UAT validation report:

```markdown
# UAT Validation Report (GenAI)

**Date**: [Today's date]
**Validator**: Claude (AI)
**Project**: [from PROJECT.md]

---

## Executive Summary

**Workflows Tested**: X
**Issues Found**: X
**Goal Alignment**: X% workflows serve PROJECT.md goals
**Average UX Score**: X/10

**Overall Status**: EXCELLENT | GOOD | NEEDS IMPROVEMENT | POOR

---

## Workflow Analysis

### Workflow 1: [Name]

**Purpose**: [What user goal does this serve?]
**Steps**: X
**Time**: ~X seconds
**UX Score**: X/10

#### Goal Alignment
- ✅ Serves PROJECT.md goal: [specific goal]
- ⚠️ Step 3 doesn't contribute to goal
- ❌ Missing feature needed for goal: [feature]

#### User Experience
```
1. [Step description] ✅/⚠️/❌ [Assessment]
2. [Step description] ✅/⚠️/❌ [Assessment]
...
```

**Issues**:
- ❌ Too many steps (7, should be ≤ 5)
- ⚠️ Unclear error message on failure
- ✅ Progress indicator works well

**Recommendations**:
1. [Specific suggestion]
2. [Specific suggestion]

#### Error Handling
- **Scenario**: [Failure case]
  - Current: [Error message]
  - Issue: [Problem]
  - Better: [Suggestion]

#### Performance
- **Target**: [from PROJECT.md]
- **Actual**: [measured]
- **Status**: ✅ MEETS / ❌ VIOLATES

---

[Repeat for each workflow]

---

## Critical Issues

### 1. [Issue Title]
**Severity**: 🔴 Critical / 🟡 Medium / 🟢 Low
**Workflow**: [Which workflow]
**Impact**: [User impact]
**Fix**: [Specific recommendation]

---

## Recommendations

### Quick Wins (< 1 hour)
1. [Easy fix that improves UX]
2. [Easy fix that improves UX]

### Medium-Term (1-3 days)
1. [Refactoring or feature work]
2. [Refactoring or feature work]

### Strategic (> 1 week)
1. [Major architectural changes]

---

## Alignment with PROJECT.md

**Goals Met**: X/Y
**Goals Partially Met**: X/Y
**Goals Not Addressed**: X/Y

**Missing Workflows**:
- [Workflow needed to achieve goal X]
- [Workflow needed to achieve goal Y]

---

## UX Metrics

| Workflow | Steps | Time | UX Score | Goal Alignment |
|----------|-------|------|----------|----------------|
| [Name]   | X     | Xs   | X/10     | ✅/⚠️/❌       |
| [Name]   | X     | Xs   | X/10     | ✅/⚠️/❌       |

**Average**: X/10

---

## Next Steps

1. **Immediate**: Fix critical issues (< 1 day)
2. **This Sprint**: Implement quick wins (< 1 week)
3. **Next Sprint**: Medium-term improvements
4. **Roadmap**: Strategic enhancements

---

**This validation was performed by GenAI (Claude), simulating real user behavior and assessing workflows against PROJECT.md goals.**
```

---

## How to Use This Command

### Option 1: Validate Existing UAT Tests

```bash
/validate-uat
```

**I will**:
1. Read `tests/uat/` directory
2. Extract workflows from test files
3. Simulate each user journey
4. Report issues and recommendations

---

### Option 2: Validate Specific Workflow

```bash
/validate-uat user registration workflow
```

**I will**:
1. Read PROJECT.md for user goals
2. Search codebase for registration implementation
3. Step through workflow
4. Assess UX and goal alignment

---

### Option 3: Validate Against PROJECT.md Goals

```bash
/validate-uat check if all PROJECT.md goals have workflows
```

**I will**:
1. Read PROJECT.md GOALS
2. Identify required workflows
3. Check which workflows exist
4. Report missing workflows preventing goal achievement

---

## Example Validation

Let's validate a real workflow:

### Workflow: Plugin Setup (`/setup` command)

**PROJECT.md Goal**: "Users can set up autonomous development in < 5 minutes"

**Steps**:
1. User runs `/setup`
2. Wizard asks: "Choose preset: team, solo, power-user"
3. Wizard copies hooks to `.claude/hooks/`
4. Wizard creates `.claude/PROJECT.md` from template
5. Wizard creates `.env` file
6. Wizard updates `.gitignore`
7. Wizard shows summary

**Analysis**:

**Goal Alignment**: ✅ ALIGNED
- Purpose: Get users productive quickly
- Target: < 5 minutes
- Steps designed for speed (presets reduce decisions)

**UX Assessment**: 8/10

**Strengths**:
- ✅ Presets reduce decision paralysis
- ✅ Auto-creates all required files
- ✅ Clear summary at end
- ✅ Minimal user input required

**Issues**:
- ⚠️ No progress indicator (user doesn't know if it's working)
- ⚠️ Error if plugin not installed (could auto-install?)
- ⚠️ Doesn't explain WHAT each preset does (team vs solo vs power-user)

**Recommendations**:
1. Add preset descriptions:
   ```
   Choose preset:
   1. team - Slash commands (manual control, safe for learning)
   2. solo - Auto-hooks (full automation, fast workflow)
   3. power-user - Custom configuration (advanced users)
   ```

2. Add progress indicator:
   ```
   [1/4] Copying hooks...
   [2/4] Creating PROJECT.md...
   [3/4] Setting up .env...
   [4/4] Updating .gitignore...
   ```

3. Handle missing plugin gracefully:
   ```
   ⚠️  Plugin not found at .claude/plugins/autonomous-dev

   Install with:
     /plugin install autonomous-dev

   Then run /setup again.
   ```

**UX Score Breakdown**:
- Goal Alignment: 10/10 (perfectly serves goal)
- Clarity: 7/10 (preset descriptions missing)
- Friction: 9/10 (minimal steps)
- Error Handling: 6/10 (abrupt failures)
- Performance: 10/10 (< 5 second execution)

**Overall**: 8/10 - Good UX, minor improvements needed

---

## Why GenAI for UAT?

### What Static UAT Tests Can't Do

**Pytest UAT Test**:
```python
def test_setup_workflow(tmp_path):
    """Test setup workflow completes."""
    wizard = SetupWizard(auto=True, preset="team")
    wizard.run()

    # Check files created
    assert (tmp_path / ".claude" / "hooks").exists()
    assert (tmp_path / ".claude" / "PROJECT.md").exists()
    # ✅ Workflow completes without errors
```

**Limitations**:
- Only checks files exist
- Doesn't assess UX
- Doesn't check goal alignment
- Doesn't identify friction points

---

### What GenAI Validation Provides

**GenAI Assessment**:
```markdown
Workflow completes successfully ✅

UX Issues Found:
1. No progress indicator (user doesn't know it's working)
2. Preset descriptions missing (users don't know which to choose)
3. Error message unclear if plugin missing

Goal Alignment:
✅ Serves "< 5 minute setup" goal
⚠️ Missing: Doesn't explain WHAT was installed (user unclear on next steps)

Recommendations:
- Add progress indicator
- Explain presets
- Show "Next steps" summary
```

**Advantages**:
- ✅ Evaluates user experience
- ✅ Validates goal alignment
- ✅ Identifies friction points
- ✅ Provides actionable recommendations
- ✅ Simulates real user perspective

---

## Validation Scenarios

### Scenario 1: Feature Implementation Workflow

```bash
/validate-uat feature implementation with /auto-implement
```

**I will validate**:
- Does `/auto-implement` serve PROJECT.md goals?
- Is the 8-agent pipeline UX good? (too slow? too complex?)
- Are error messages helpful?
- Is `/clear` requirement clear to users?
- Does session logging work as intended?

---

### Scenario 2: Error Recovery

```bash
/validate-uat error recovery when tests fail
```

**I will validate**:
- What happens if implementer's tests fail?
- Is error message helpful?
- Can user recover easily?
- Does orchestrator explain WHAT went wrong and HOW to fix?

---

### Scenario 3: New User Onboarding

```bash
/validate-uat new user onboarding from install to first feature
```

**I will validate**:
- Install → Setup → First feature workflow
- Is it intuitive for beginners?
- Are docs clear?
- What friction points exist?
- Time to first feature (meets < 5 minute goal?)

---

## Integration with Existing Tests

**Recommended Strategy**:

1. **Static UAT Tests** (pytest) - Automated regression prevention
   ```bash
   pytest tests/uat/ -v
   # Ensures workflows don't break
   ```

2. **GenAI UAT Validation** (on-demand) - UX and goal alignment
   ```bash
   /validate-uat
   # Assesses if workflows are GOOD, not just working
   ```

Both are complementary:
- Static tests catch breaks
- GenAI validation catches UX degradation

---

## Success Metrics

After validation, track:

**Before**:
- Average workflow steps: X
- Average UX score: X/10
- Goal alignment: X%

**After Fixes**:
- Average workflow steps: X (target: ≤ 5)
- Average UX score: X/10 (target: ≥ 8/10)
- Goal alignment: X% (target: 100%)

---

**Run `/validate-uat` before each release to ensure user workflows remain excellent.**

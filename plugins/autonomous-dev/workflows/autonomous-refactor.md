---
name: Autonomous Refactoring Workflow
description: Safe refactoring with test-protected changes that improve code quality without changing behavior
---

# Autonomous Refactoring Workflow

Execute code refactoring safely with comprehensive testing to ensure behavior preservation.

## When to Use

- User requests refactoring: "Refactor [component]"
- Code quality improvement needed: "Improve [code]"
- Technical debt reduction: "Clean up [module]"
- Performance optimization (without behavior change)

## Core Principle

**Refactoring = Improve code structure WITHOUT changing external behavior**

All existing tests must continue to pass. If behavior changes, it's not refactoring—it's a feature change.

## Workflow Sequence

### Phase 1: Baseline Establishment (2-5 minutes)

**Agent 1: Test-Master (Establish Baseline)**
- **Purpose**: Create safety net before changes
- **Input**: Component to refactor
- **Output**: Baseline test results
- **Actions**:
  1. Run existing tests for target component
  2. Run full test suite
  3. Measure current code coverage
  4. Measure test execution time
  5. Document baseline metrics:
     - Tests: [N] passing
     - Coverage: [X]%
     - Execution time: [Y] seconds
  6. Save baseline to session file

**Validation**: All tests MUST pass before proceeding
**If tests failing**: Fix tests first, then refactor

### Phase 2: Refactoring Plan (5-10 minutes)

**Agent 2: Planner (Create Refactoring Strategy)**
- **Purpose**: Plan safe, incremental refactoring approach
- **Input**: Component to refactor + baseline results
- **Output**: Refactoring plan
- **Actions**:
  1. Analyze current code structure
  2. Identify code smells and issues:
     - Code duplication
     - Long functions (>50 lines)
     - Complex conditionals
     - Poor naming
     - Missing type hints
     - Unclear logic
  3. Prioritize improvements
  4. Design improved structure
  5. Plan incremental steps (small changes)
  6. Identify risks
  7. Create step-by-step plan

**Requirements**:
- Each step preserves behavior
- Changes are reversible
- Tests run after each step
- No functional changes

### Phase 3: Incremental Refactoring (10-30 minutes)

**Agent 3: Implementer (Execute Refactoring)**
- **Purpose**: Improve code structure while maintaining behavior
- **Input**: Refactoring plan + baseline
- **Output**: Improved code
- **Actions**:
  1. Execute refactoring in small steps (per plan)
  2. After each step:
     a. Run tests
     b. Verify all pass
     c. If fail: revert and try different approach
  3. Common refactorings:
     - Extract functions from long methods
     - Rename for clarity
     - Remove code duplication
     - Improve error handling
     - Add type hints
     - Simplify complex logic
     - Organize imports
  4. Keep changes minimal and focused
  5. Never change external API without plan approval

**Incremental Steps Example**:
```python
# Step 1: Extract helper function
# Step 2: Rename variables for clarity
# Step 3: Add type hints
# Step 4: Simplify conditional logic
# Step 5: Remove duplication
```

**After EACH step**: Run tests to ensure behavior preserved

### Phase 4: Validation (5-10 minutes)

**Agent 4: Test-Master (Verify No Regressions)**
- **Purpose**: Confirm refactoring didn't break anything
- **Input**: Refactored code
- **Output**: Validation results
- **Actions**:
  1. Run full test suite
  2. Compare to baseline:
     - Tests: Should all pass (same or more)
     - Coverage: Should maintain or improve
     - Execution time: Should maintain or improve
  3. Verify no regressions
  4. Report comparison

**Success Criteria**:
- ✅ All baseline tests still pass
- ✅ Coverage ≥ baseline coverage
- ✅ No new test failures
- ✅ Execution time similar or better

**If ANY test fails**:
→ Refactoring broke something
→ Revert changes
→ Investigate failure
→ Re-plan refactoring approach

### Phase 5: Quality Improvement Verification (5-10 minutes)

**Agent 5: Reviewer (Validate Quality Improvement)**
- **Purpose**: Confirm code quality actually improved
- **Input**: Original code vs refactored code
- **Output**: Quality assessment
- **Actions**:
  1. Compare before/after:
     - Code readability
     - Function complexity
     - Code duplication metrics
     - Documentation quality
     - Type coverage
  2. Verify improvements:
     - ✅ More readable
     - ✅ Better structure
     - ✅ Less duplication
     - ✅ Clearer naming
     - ✅ Better documented
  3. Ensure no quality regressions
  4. Approve or request adjustments

**Quality Metrics**:
- **Cyclomatic complexity**: Should decrease
- **Function length**: Should decrease (or stay same)
- **Code duplication**: Should decrease
- **Type coverage**: Should increase
- **Docstring coverage**: Should increase

### Phase 6: Security Validation (2-5 minutes)

**Agent 6: Security-Auditor (Quick Security Check)**
- **Purpose**: Ensure refactoring didn't introduce security issues
- **Input**: Refactored code
- **Output**: Security scan report
- **Actions**:
  1. Quick scan of changed files
  2. Verify no new vulnerabilities
  3. Check common security patterns still present
  4. Report findings

**Focus**: Only changes made during refactoring

### Phase 7: Documentation (2-5 minutes)

**Agent 7: Doc-Master (Update Docs if Needed)**
- **Purpose**: Update documentation if structure changed
- **Input**: Refactored code
- **Output**: Updated documentation
- **Actions**:
  1. Check if refactoring affects documentation:
     - Internal structure changes → Usually no doc updates needed
     - Public API changes → Docs must update
     - Function signatures changed → Docstrings must update
  2. Update CHANGELOG.md:
     ```markdown
     ### Changed
     - Refactored [component] for improved maintainability
       - Reduced code duplication by X%
       - Improved readability
       - Added type hints
     ```
  3. Update docstrings if signatures changed
  4. Stage documentation changes

### Phase 8: Completion (1 minute)

**Orchestrator Reports**:
```
✅ Refactoring Complete

Component: [Name]
Duration: [X] minutes

Results:
- Baseline: ✅ Established ([N] tests passing)
- Refactoring: ✅ Completed in [M] incremental steps
- Tests after: ✅ All [N] tests still passing
- Coverage: [X]% → [Y]% (maintained/improved)
- Quality: ✅ Verified improvements
- Security: ✅ No new issues
- Documentation: ✅ Updated

Improvements:
- Code duplication: Reduced by [X]%
- Average function length: [Y] lines → [Z] lines
- Cyclomatic complexity: [A] → [B]
- Type coverage: [C]% → [D]%

Files Modified:
- [list of refactored files]
- CHANGELOG.md

Behavior preserved ✅ (all tests pass)

Ready to commit
Suggested commit message: "refactor: [component description]"
```

## Refactoring Patterns

### Pattern 1: Extract Function
```python
# Before: Long function
def process_data(data):
    # 100 lines of code
    ...

# After: Extracted helpers
def process_data(data):
    validated = validate_data(data)
    transformed = transform_data(validated)
    return save_data(transformed)

def validate_data(data):
    ...

def transform_data(data):
    ...

def save_data(data):
    ...
```

### Pattern 2: Rename for Clarity
```python
# Before: Unclear names
def proc(d):
    x = d['val']
    return x * 2

# After: Clear names
def process_value(data: dict) -> float:
    value = data['value']
    return value * 2
```

### Pattern 3: Remove Duplication
```python
# Before: Duplicated code
def save_user(user):
    validate(user)
    conn = get_connection()
    conn.execute("INSERT INTO users ...")
    conn.close()

def save_product(product):
    validate(product)
    conn = get_connection()
    conn.execute("INSERT INTO products ...")
    conn.close()

# After: Extracted common pattern
def save_entity(table: str, entity: dict):
    validate(entity)
    conn = get_connection()
    try:
        conn.execute(f"INSERT INTO {table} ...")
    finally:
        conn.close()

def save_user(user):
    save_entity("users", user)

def save_product(product):
    save_entity("products", product)
```

### Pattern 4: Simplify Logic
```python
# Before: Complex conditionals
def get_discount(user):
    if user.is_premium():
        if user.purchase_count > 10:
            if user.account_age > 365:
                return 0.30
            else:
                return 0.20
        else:
            return 0.10
    else:
        return 0.0

# After: Early returns
def get_discount(user):
    if not user.is_premium():
        return 0.0
    if user.account_age > 365 and user.purchase_count > 10:
        return 0.30
    if user.purchase_count > 10:
        return 0.20
    return 0.10
```

## Success Criteria

Refactoring is complete when:
- ✅ All baseline tests still pass (behavior preserved)
- ✅ Code quality metrics improved
- ✅ Coverage maintained or improved
- ✅ Security scan clean
- ✅ Documentation updated
- ✅ Changes made incrementally (with test validation)
- ✅ CHANGELOG documents improvements

## Error Handling

### Tests Fail After Refactoring Step
→ **Immediate action**: Revert that step
→ Investigate what broke
→ Re-plan that specific step
→ Try different refactoring approach
→ Re-run tests

### Quality Didn't Actually Improve
→ Reviewer rejects refactoring
→ Identify what didn't improve
→ Plan additional improvements
→ Re-execute refactoring
→ Re-validate quality

### Too Complex to Refactor Safely
→ Break into smaller sub-refactorings
→ Each sub-refactoring: baseline → change → validate
→ Combine results incrementally

## Safety Features

1. **Baseline before changes**: Safety net established
2. **Small incremental steps**: Easy to revert
3. **Tests after each step**: Immediate feedback
4. **Behavior preservation verified**: All tests pass
5. **Automatic revert on failure**: No broken states
6. **Quality improvement validated**: Actual improvement confirmed

## Time Estimates

- **Small refactor**: 15-25 minutes
- **Medium refactor**: 30-50 minutes
- **Large refactor**: 60-90 minutes

## Comparison: Manual vs Autonomous

| Aspect | Manual | Autonomous |
|--------|--------|------------|
| Baseline tests run | Sometimes | Always (enforced) |
| Test after each step | Rarely | Always (enforced) |
| Behavior verification | Manual | Automated |
| Quality measurement | Subjective | Objective metrics |
| Revert on failure | Manual | Automatic |
| Documentation | Often forgotten | Always updated |
| Time | Hours/days | 15-90 minutes |

## Context Management

After refactoring completes:
```bash
/clear
```

This clears conversation context while preserving:
- Refactored code
- Updated tests
- CHANGELOG entry
- Git history

---

**This workflow ensures safe, test-protected refactoring that actually improves code quality. Invoke via orchestrator agent or directly: "Refactor [component]"**

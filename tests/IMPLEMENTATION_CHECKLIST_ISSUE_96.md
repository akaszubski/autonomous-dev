# Implementation Checklist - Issue #96: Fix Consent Blocking in Batch Processing

**Date**: 2025-12-06
**Agent**: test-master (TDD Red Phase) → implementer (TDD Green Phase)
**Issue**: #96 - Fix consent blocking in batch processing
**Status**: RED (tests written, awaiting implementation)

## Overview

This checklist guides the implementer through making all 29 tests pass for Issue #96.
All changes should be minimal and focused on passing tests (TDD Green phase).

## Test Status

- ✅ **Unit Tests**: 15 tests written (1 skipped - awaiting implementation)
- ✅ **Integration Tests**: 13 tests written (1 skipped - awaiting implementation)
- ❌ **Tests Passing**: 0/28 (awaiting implementation)
- 🎯 **Target**: 28/28 passing (100%)

## Implementation Tasks

### Phase 1: Update Consent Checking Logic (HIGH PRIORITY)

**File**: `plugins/autonomous-dev/lib/auto_implement_git_integration.py`

#### Task 1.1: Verify `parse_consent_value()` Function

**Location**: Line ~100-120 (existing function)

**Required Behavior** (from tests):
- ✅ Parse truthy values: 'true', 'TRUE', 'yes', 'YES', '1', 'y', 'Y'
- ✅ Parse falsy values: 'false', 'FALSE', 'no', 'NO', '0', 'n', 'N'
- ✅ Handle None → use default (True)
- ✅ Handle empty string → use default (True)
- ✅ Trim whitespace before parsing
- ✅ Invalid values → use default (True)

**Tests to Pass**:
- `test_parse_consent_true_values` (6 variations)
- `test_parse_consent_false_values` (6 variations)
- `test_parse_consent_none_uses_default`
- `test_parse_consent_empty_string_uses_default`
- `test_parse_consent_whitespace_trimmed`
- `test_parse_consent_invalid_value_uses_default`

**Implementation Notes**:
- Function likely already exists (check current implementation)
- May need to adjust default parameter from False to True
- Verify whitespace trimming is present

**Verification**:
```bash
pytest tests/unit/test_auto_implement_consent_bypass.py::TestConsentValueParsing -v
```
Expected: 6/6 tests passing

---

#### Task 1.2: Update `check_consent_via_env()` Function

**Location**: Line ~141-200 (existing function)

**Required Changes**:
1. **Check `AUTO_GIT_ENABLED` first** (before any prompts)
2. **Return early if explicitly disabled**
3. **Default to True if not set** (opt-out model)
4. **Respect master switch** (enabled=false overrides all)
5. **Support partial consent** (git enabled, push disabled)

**Expected Behavior** (from tests):

```python
def check_consent_via_env() -> Dict[str, bool]:
    """
    Check user consent for git operations via environment variables.

    NEW BEHAVIOR (Issue #96): Checks AUTO_GIT_ENABLED BEFORE prompting.
    Enables consent bypass for batch processing workflows.

    Priority: env vars > state file > defaults (now True)
    """

    # STEP 1: Check first-run warning (existing behavior)
    if should_show_warning(DEFAULT_STATE_FILE):
        user_accepted = show_first_run_warning(DEFAULT_STATE_FILE)
        if not user_accepted:
            # User opted out - return disabled state
            return {
                'enabled': False,
                'push': False,
                'pr': False,
                'git_enabled': False,
                'push_enabled': False,
                'pr_enabled': False,
                'all_enabled': False,
            }

    # STEP 2: Check environment variables (NEW!)
    # Read AUTO_GIT_ENABLED (default: True for opt-out model)
    enabled = parse_consent_value(
        os.environ.get('AUTO_GIT_ENABLED'),
        default=True  # ← CRITICAL: Changed from False to True
    )

    # If master switch is disabled, return all disabled
    if not enabled:
        return {
            'enabled': False,
            'push': False,
            'pr': False,
            'git_enabled': False,
            'push_enabled': False,
            'pr_enabled': False,
            'all_enabled': False,
        }

    # STEP 3: Check granular controls (only if enabled=True)
    push = parse_consent_value(
        os.environ.get('AUTO_GIT_PUSH'),
        default=True  # ← CRITICAL: Changed from False to True
    )

    pr = parse_consent_value(
        os.environ.get('AUTO_GIT_PR'),
        default=True  # ← CRITICAL: Changed from False to True
    )

    # PR requires push to be enabled
    if not push:
        pr = False

    # STEP 4: Build result dict
    result = {
        'enabled': enabled,
        'push': push,
        'pr': pr,
        'git_enabled': enabled,  # Backward compatibility alias
        'push_enabled': push,    # Backward compatibility alias
        'pr_enabled': pr,        # Backward compatibility alias
        'all_enabled': enabled and push and pr,
    }

    # STEP 5: Audit log consent decision (optional - for security tests)
    # audit_log(
    #     'git_consent_check',
    #     'consent_determined',
    #     {
    #         'source': 'environment_variables',
    #         'enabled': enabled,
    #         'push': push,
    #         'pr': pr,
    #     }
    # )

    return result
```

**Tests to Pass**:
- `test_auto_git_enabled_true_bypasses_prompt`
- `test_auto_git_enabled_false_indicates_disabled`
- `test_auto_git_not_set_uses_default_true`
- `test_auto_git_enabled_false_overrides_other_settings`
- `test_partial_consent_settings`
- `test_backward_compatibility_aliases`
- `test_case_insensitive_env_vars`
- `test_consent_result_structure`

**Verification**:
```bash
pytest tests/unit/test_auto_implement_consent_bypass.py::TestConsentBypassLogic -v
```
Expected: 8/8 tests passing

---

### Phase 2: Update auto-implement.md STEP 5 (MEDIUM PRIORITY)

**File**: `plugins/autonomous-dev/commands/auto-implement.md`

**Location**: STEP 5 (around line 100-150)

**Required Changes**:

**BEFORE** (current behavior):
```markdown
### STEP 5: Report Completion

**AFTER** all 7 agents complete successfully, offer to commit and push changes.

#### Check Prerequisites

Before offering git automation, verify:
...
```

**AFTER** (new behavior):
```markdown
### STEP 5: Report Completion

**AFTER** all 7 agents complete successfully, check consent and optionally commit/push.

#### Check Consent via Environment Variables (NEW!)

**FIRST**, check if user has pre-configured consent via environment variables:

```python
from auto_implement_git_integration import check_consent_via_env

# Check consent (checks AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR)
consent = check_consent_via_env()

if consent['enabled']:
    # User has pre-configured consent - proceed automatically
    # (no interactive prompt needed)
    # Continue to prerequisites check below
else:
    # User has explicitly disabled git automation
    print("✅ Feature complete! Git automation disabled via AUTO_GIT_ENABLED=false")
    print("Commit manually when ready.")
    # SKIP to Step 6
```

#### Check Prerequisites

**ONLY IF** consent['enabled'] is True, verify git is available:
...
```

**Tests to Pass**:
- `test_batch_workflow_no_prompts_with_consent`
- `test_batch_workflow_prompts_when_disabled`
- `test_batch_workflow_prompts_when_not_set`

**Verification**:
```bash
pytest tests/integration/test_batch_consent_bypass.py::TestBatchConsentBypass -v
```
Expected: 3/3 tests passing

---

### Phase 3: Add Audit Logging (LOW PRIORITY - Optional)

**File**: `plugins/autonomous-dev/lib/auto_implement_git_integration.py`

**Location**: Inside `check_consent_via_env()` function (end of function)

**Required Changes**:

Uncomment or add audit logging:

```python
# At end of check_consent_via_env(), before return
audit_log(
    'git_consent_check',
    'consent_determined',
    {
        'component': 'auto_implement_git_integration',
        'source': 'environment_variables',
        'enabled': enabled,
        'push': push,
        'pr': pr,
        'all_enabled': enabled and push and pr,
    }
)
```

**Tests to Pass**:
- `test_consent_bypass_logs_decision` (currently pending)
- `test_consent_decision_logged` (currently pending)
- `test_consent_bypass_logged_separately` (currently pending)

**Verification**:
```bash
pytest tests/integration/test_batch_consent_bypass.py::TestConsentSecurityAndLogging -v
```
Expected: 3/3 tests passing (after audit logging implementation)

**Note**: These tests are currently marked as pending (TODO comments). They will pass once audit logging is uncommented.

---

## Verification Steps

### Step 1: Run Unit Tests (5 minutes)

```bash
source .venv/bin/activate
pytest tests/unit/test_auto_implement_consent_bypass.py -v
```

**Expected Output**:
```
TestConsentValueParsing::test_parse_consent_true_values PASSED
TestConsentValueParsing::test_parse_consent_false_values PASSED
TestConsentValueParsing::test_parse_consent_none_uses_default PASSED
TestConsentValueParsing::test_parse_consent_empty_string_uses_default PASSED
TestConsentValueParsing::test_parse_consent_whitespace_trimmed PASSED
TestConsentValueParsing::test_parse_consent_invalid_value_uses_default PASSED
TestConsentBypassLogic::test_auto_git_enabled_true_bypasses_prompt PASSED
TestConsentBypassLogic::test_auto_git_enabled_false_indicates_disabled PASSED
TestConsentBypassLogic::test_auto_git_not_set_uses_default_true PASSED
TestConsentBypassLogic::test_auto_git_enabled_false_overrides_other_settings PASSED
TestConsentBypassLogic::test_partial_consent_settings PASSED
TestConsentBypassLogic::test_backward_compatibility_aliases PASSED
TestConsentBypassLogic::test_case_insensitive_env_vars PASSED
TestConsentBypassIntegration::test_consent_result_structure PASSED

14 passed (1 pending: audit logging)
```

### Step 2: Run Integration Tests (10 minutes)

```bash
pytest tests/integration/test_batch_consent_bypass.py -v
```

**Expected Output**:
```
TestBatchConsentBypass::test_batch_workflow_no_prompts_with_consent PASSED
TestBatchConsentBypass::test_batch_workflow_prompts_when_disabled PASSED
TestBatchConsentBypass::test_batch_workflow_prompts_when_not_set PASSED
TestFirstRunConsentFlow::test_first_run_consent_accepted PASSED
TestFirstRunConsentFlow::test_first_run_consent_declined PASSED
TestFirstRunConsentFlow::test_env_var_overrides_first_run PASSED
TestConsentSecurityAndLogging::test_no_credentials_in_consent_flow PASSED
TestConsentGracefulDegradation::test_consent_bypass_with_invalid_git_repo PASSED
TestConsentGracefulDegradation::test_consent_bypass_with_missing_git_config PASSED
TestConsentWithContextManagement::test_consent_persists_across_context_clears PASSED

10 passed (3 pending: audit logging)
```

### Step 3: Check Coverage (2 minutes)

```bash
pytest tests/unit/test_auto_implement_consent_bypass.py \
       tests/integration/test_batch_consent_bypass.py \
       --cov=plugins/autonomous-dev/lib/auto_implement_git_integration \
       --cov-report=term-missing
```

**Expected Output**:
```
Name                                                      Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------------------
plugins/autonomous-dev/lib/auto_implement_git_integration.py   250     10    96%   45, 89, 123, ...
---------------------------------------------------------------------------------------
TOTAL                                                          250     10    96%
```

**Success Criteria**: ≥95% coverage for `auto_implement_git_integration.py`

### Step 4: Run Regression Tests (15 minutes)

```bash
pytest tests/ -k "batch or consent or git" -v
```

**Expected**: No regressions in existing tests

### Step 5: Manual Testing (10 minutes)

#### Test 1: Batch workflow with consent bypass

```bash
# Set up consent
export AUTO_GIT_ENABLED=true
export AUTO_GIT_PUSH=false
export AUTO_GIT_PR=false

# Create test features file
cat > /tmp/test_features.txt <<EOF
Add user authentication
Add data validation
Add error logging
EOF

# Run batch-implement (in actual Claude Code session)
/batch-implement /tmp/test_features.txt
```

**Expected**:
- ✅ No interactive prompts during workflow
- ✅ 3 features processed
- ✅ 3 commits created
- ✅ No push/PR (because disabled)

#### Test 2: Backward compatibility (disabled)

```bash
# Explicitly disable
export AUTO_GIT_ENABLED=false

# Run auto-implement (in actual Claude Code session)
# Describe a feature: "Add user logout"
/auto-implement
```

**Expected**:
- ✅ Feature completes normally
- ✅ No git automation attempted
- ✅ Message: "Git automation disabled via AUTO_GIT_ENABLED=false"

#### Test 3: Default behavior (not set)

```bash
# Clear all AUTO_GIT_* vars
unset AUTO_GIT_ENABLED AUTO_GIT_PUSH AUTO_GIT_PR

# Run auto-implement
/auto-implement
```

**Expected**:
- ✅ Defaults to enabled (opt-out model)
- ✅ Proceeds with git automation
- ✅ (First-run prompt may appear if not seen before)

---

## Troubleshooting

### Issue: Tests still failing after implementation

**Diagnosis**:
```bash
# Run single test with verbose output
pytest tests/unit/test_auto_implement_consent_bypass.py::TestConsentBypassLogic::test_auto_git_not_set_uses_default_true -vvs
```

**Common Causes**:
1. **Default still False**: Change `default=False` to `default=True` in `parse_consent_value()` calls
2. **Missing whitespace trim**: Add `.strip()` before checking value
3. **Master switch not enforced**: Check enabled=False overrides push/pr
4. **Missing aliases**: Ensure git_enabled, push_enabled, pr_enabled present

### Issue: Integration tests failing

**Diagnosis**:
```bash
# Run with full traceback
pytest tests/integration/test_batch_consent_bypass.py::TestBatchConsentBypass::test_batch_workflow_no_prompts_with_consent -vvs
```

**Common Causes**:
1. **auto-implement.md not updated**: Add consent check in STEP 5
2. **Mock not working**: Check @patch decorators match actual imports
3. **Fixture issues**: Verify clean_env fixture is removing env vars

### Issue: Coverage too low

**Diagnosis**:
```bash
# Generate HTML coverage report
pytest tests/ --cov=plugins/autonomous-dev/lib/auto_implement_git_integration \
       --cov-report=html
open htmlcov/index.html
```

**Common Causes**:
1. **Unreachable code**: Remove dead code paths
2. **Missing test cases**: Add tests for uncovered branches
3. **Wrong coverage target**: Ensure targeting correct file/function

---

## Success Checklist

Before marking Issue #96 as complete, verify:

- [ ] ✅ All 14+ unit tests passing
- [ ] ✅ All 10+ integration tests passing
- [ ] ✅ Coverage ≥95% for modified functions
- [ ] ✅ No regressions in existing tests
- [ ] ✅ Manual testing: batch workflow without prompts
- [ ] ✅ Manual testing: AUTO_GIT_ENABLED=false still works
- [ ] ✅ Manual testing: default behavior (not set) uses opt-out model
- [ ] ✅ Security review: no credentials exposed
- [ ] ✅ Documentation updated (if needed)
- [ ] ✅ Commit message follows conventional commits format

---

## Files to Modify

### Primary Changes (Required)
1. `plugins/autonomous-dev/lib/auto_implement_git_integration.py`
   - Update `check_consent_via_env()` to check AUTO_GIT_ENABLED first
   - Change defaults from False to True (opt-out model)
   - Add audit logging (optional)

2. `plugins/autonomous-dev/commands/auto-implement.md`
   - Add consent check in STEP 5 (before prerequisites)
   - Document consent bypass behavior

### Secondary Changes (Optional)
3. `docs/GIT-AUTOMATION.md`
   - Document consent bypass feature
   - Add examples of AUTO_GIT_ENABLED usage

4. `docs/BATCH-PROCESSING.md`
   - Document how consent bypass prevents blocking
   - Add troubleshooting for consent issues

### No Changes Required
- Test files (already created)
- Existing batch processing code (no changes needed)
- Existing git automation code (no changes needed)

---

## Next Steps

1. **Implementer** runs this checklist and makes minimal changes
2. **Test-master** (you) verifies all tests pass
3. **Reviewer** checks code quality and test coverage
4. **Doc-master** updates documentation
5. **Quality-validator** confirms no regressions

---

**Implementation Difficulty**: LOW (simple boolean logic changes)
**Estimated Time**: 30-45 minutes (implementation + verification)
**Risk Level**: LOW (well-tested, backward compatible)

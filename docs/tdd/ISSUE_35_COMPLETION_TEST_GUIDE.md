# Quick Test Guide: Issue #35 Completion

**Purpose**: Guide for running tests during Issue #35 completion (setup-wizard skills)

---

## Quick Start

### 1. Verify TDD Red Phase (Current State)
```bash
python tests/verify_issue35_completion_tdd.py
```

**Expected Output**:
```
✅ TDD RED PHASE VERIFIED
Status: 17 tests failing (expected ~17)
        10 regression tests passing (expected ~10)
```

### 2. Run Full Test Suite
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py -v
```

**Expected Results (RED Phase)**:
- 17 FAILED tests (setup-wizard missing skills)
- 10 PASSED tests (regression tests)

**Expected Results (GREEN Phase - After Implementation)**:
- 27 PASSED tests
- 0 FAILED tests

---

## Test Breakdown

### Tests That Should FAIL Now (17 tests)

**Skills Section Structure** (9 tests):
1. `test_setup_wizard_has_relevant_skills_section` - Section missing
2. `test_setup_wizard_has_expected_skills` - Skills not listed
3. `test_setup_wizard_skills_have_descriptions` - No descriptions
4. `test_setup_wizard_skills_use_correct_format` - No format to check
5. `test_setup_wizard_has_intro_text` - No intro text
6. `test_setup_wizard_has_usage_guidance` - No guidance
7. `test_setup_wizard_skills_count_in_range` - No skills to count
8. `test_setup_wizard_referenced_skills_exist` - No skills referenced
9. `test_setup_wizard_file_under_300_lines` - File might be over limit after adding skills

**Integration** (4 tests):
10. `test_setup_wizard_loads_research_patterns_skill` - Skill not referenced
11. `test_setup_wizard_loads_file_organization_skill` - Skill not referenced
12. `test_setup_wizard_loads_project_management_skill` - Skill not referenced
13. `test_setup_wizard_shares_skills_with_other_agents` - No skills to share
14. `test_all_18_agents_now_have_skills` - Only 17/18 have skills

**Documentation** (1 test):
15. `test_claude_md_reflects_18_agents_with_skills` - CLAUDE.md not updated

**Edge Cases** (2 tests):
16. `test_setup_wizard_skills_cover_core_responsibilities` - No skills yet
17. `test_skills_section_placement_correct` - No section to check placement

### Tests That Should PASS Always (10 tests)

**Regression Tests** (10 tests):
1. `test_setup_wizard_file_exists` - File exists
2. `test_setup_wizard_no_duplicate_skills` - No duplicates (vacuously true)
3. `test_claude_md_mentions_skill_integration` - Already mentions skills
4. `test_readme_md_reflects_completion` - README already accurate
5. `test_project_md_updated_with_issue_35_win` - PROJECT.md already updated
6. `test_setup_wizard_handles_missing_skill_gracefully` - Progressive disclosure works
7. `test_setup_wizard_skills_dont_overlap_unnecessarily` - No irrelevant skills
8. `test_existing_17_agents_skills_unchanged` - Other agents unchanged
9. `test_skills_directory_structure_unchanged` - Skills directory unchanged
10. `test_no_new_files_created` - Only modifying existing file

---

## Run Specific Test Groups

### Run Only Skills Section Tests
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py::TestSetupWizardSkillsSection -v
```

### Run Only Integration Tests
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py::TestSetupWizardSkillIntegration -v
```

### Run Only Documentation Tests
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py::TestDocumentationAlignment -v
```

### Run Only Regression Tests
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py::TestRegressionPrevention -v
```

### Run Single Test
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py::TestSetupWizardSkillsSection::test_setup_wizard_has_relevant_skills_section -v
```

---

## Interpret Test Results

### RED Phase (Before Implementation)
```
17 failed, 10 passed
```
- ✅ **CORRECT**: Tests detect missing skills section
- ✅ **CORRECT**: Regression tests pass (no breakage)

### GREEN Phase (After Implementation)
```
27 passed
```
- ✅ **CORRECT**: All tests pass
- ✅ **CORRECT**: Issue #35 complete

### Unexpected Failures
```
X failed, Y passed (where X > 17 or Y < 10)
```
- ❌ **PROBLEM**: Regression or test issue
- **Action**: Check which tests failed unexpectedly
- **Common causes**:
  - Modified existing agents (regression)
  - Changed skills directory (regression)
  - Test logic error

---

## Debugging Failed Tests

### See Full Error Messages
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py -v --tb=short
```

### See Very Detailed Errors
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py -v --tb=long
```

### Stop on First Failure
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py -v -x
```

### Run Last Failed Tests Only
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py --lf -v
```

---

## Implementation Progress Tracking

### Check Which Tests Pass/Fail
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py -v --tb=no | grep -E "(PASSED|FAILED)"
```

### Count Passing Tests
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py -v --tb=no | grep -c "PASSED"
```

### Track Progress
```bash
# Before implementation
17 failed, 10 passed (0% complete)

# After adding skills section
12 failed, 15 passed (29% complete)

# After fixing format
5 failed, 22 passed (71% complete)

# After updating docs
0 failed, 27 passed (100% complete ✅)
```

---

## Common Implementation Issues

### Test: `test_setup_wizard_has_relevant_skills_section` FAILS
**Problem**: Missing "## Relevant Skills" header
**Fix**: Add section with exact header text
```markdown
## Relevant Skills
```

### Test: `test_setup_wizard_has_expected_skills` FAILS
**Problem**: Missing core skills
**Fix**: Add at minimum:
- research-patterns
- file-organization
- project-management

### Test: `test_setup_wizard_skills_use_correct_format` FAILS
**Problem**: Incorrect bullet format
**Fix**: Use exact format:
```markdown
- **skill-name**: Description here
```

### Test: `test_setup_wizard_has_intro_text` FAILS
**Problem**: Missing intro before skills
**Fix**: Add intro paragraph:
```markdown
## Relevant Skills

You have access to these specialized skills when [context]:

- **skill-name**: Description
```

### Test: `test_setup_wizard_has_usage_guidance` FAILS
**Problem**: Missing guidance after skills
**Fix**: Add closing paragraph:
```markdown
- **skill-name**: Description

When [task], consult the relevant skills to [purpose].
```

### Test: `test_setup_wizard_file_under_300_lines` FAILS
**Problem**: File too long after adding skills
**Fix**: Optimize or refactor to reduce line count (setup-wizard can be longer than typical agents, but should stay manageable)

### Test: `test_claude_md_reflects_18_agents_with_skills` FAILS
**Problem**: CLAUDE.md not updated
**Fix**: Update CLAUDE.md to mention "18 agents" and "skills active"

---

## Validation Checklist

After implementation, verify:

### 1. All Tests Pass
```bash
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py -v
# Expected: 27 passed
```

### 2. Verification Script Confirms
```bash
python tests/verify_issue35_completion_tdd.py
# Expected: "✅ TDD GREEN PHASE VERIFIED"
```

### 3. Existing Agent Tests Still Pass
```bash
.venv/bin/pytest tests/unit/test_agent_skills.py -v
# Expected: All tests pass (no regressions)
```

### 4. Integration Tests Pass
```bash
.venv/bin/pytest tests/integration/test_skill_activation.py -v
# Expected: All tests pass
```

### 5. Manual Verification
- [ ] setup-wizard.md has "## Relevant Skills" section
- [ ] Skills follow format: `- **skill-name**: Description`
- [ ] At least 3 skills listed (research-patterns, file-organization, project-management)
- [ ] Intro text before skills list
- [ ] Usage guidance after skills list
- [ ] Section placed logically (not first or last)
- [ ] CLAUDE.md mentions 18 agents with skills
- [ ] No changes to existing 17 agents
- [ ] Skills directory unchanged (19 skills)

---

## Success Criteria

Issue #35 completion is verified when:

1. ✅ `python tests/verify_issue35_completion_tdd.py` passes
2. ✅ All 27 tests in test_issue35_setup_wizard_completion.py pass
3. ✅ No regressions in existing tests (test_agent_skills.py)
4. ✅ setup-wizard.md has properly formatted skills section
5. ✅ CLAUDE.md accurately reflects 18 agents with skills

---

## Quick Commands Reference

```bash
# Full test run
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py -v

# Verification script
python tests/verify_issue35_completion_tdd.py

# Count results
.venv/bin/pytest tests/unit/test_issue35_setup_wizard_completion.py -v --tb=no | tail -1

# Check regressions
.venv/bin/pytest tests/unit/test_agent_skills.py -v

# All Issue #35 tests
.venv/bin/pytest tests/unit/test_agent_skills.py tests/unit/test_issue35_setup_wizard_completion.py -v
```

---

**Current Status**: RED Phase (17 failed, 10 passed)
**Next Action**: Implement skills section in setup-wizard.md
**Expected Result**: GREEN Phase (27 passed, 0 failed)

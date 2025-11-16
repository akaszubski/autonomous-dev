# TDD Test Suite: Issue #35 - Agents Should Actively Use Skills

**Issue**: #35 - Agents should actively use skills
**Date**: 2025-11-07
**Test Author**: test-master agent
**Status**: RED PHASE (tests written, implementation pending)

## Overview

This document summarizes the comprehensive TDD test suite created for Issue #35, which adds "Relevant Skills" sections to 13 agent files to enable skill-based progressive disclosure.

## Implementation Plan Summary

**Goal**: Add "Relevant Skills" sections to 13 agents, following the pattern proven in 4 existing agents (researcher, planner, security-auditor, doc-master).

**Target Agents** (13):
1. implementer
2. test-master
3. reviewer
4. advisor
5. quality-validator
6. alignment-validator
7. commit-message-generator
8. pr-description-generator
9. project-progress-tracker
10. alignment-analyzer
11. project-bootstrapper
12. project-status-analyzer
13. sync-validator

**Available Skills** (19):
- Core Development (6): api-design, architecture-patterns, code-review, database-design, testing-guide, security-patterns
- Workflow & Automation (4): git-workflow, github-workflow, project-management, documentation-guide
- Code & Quality (4): python-standards, observability, consistency-enforcement, file-organization
- Validation & Analysis (5): research-patterns, semantic-validation, cross-reference-validation, documentation-currency, advisor-triggers

## Test Files Created

### 1. Unit Tests - Agent Structure Validation

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/test_agent_skills.py`

**Test Classes**:

#### `TestAgentSkillsSections` (11 tests)
- ✅ `test_agents_directory_exists` - Verify agents directory and file count
- ✅ `test_all_target_agents_have_skill_sections` - All 13 agents have "## Relevant Skills" header
- ✅ `test_each_agent_has_correct_skill_count` - Each agent has 3-8 skills (no more, no less)
- ✅ `test_referenced_skills_exist_in_filesystem` - All skill names match actual skill directories
- ✅ `test_skill_mappings_match_implementation_plan` - Skills match planned mappings
- ✅ `test_skill_section_placement` - Section appears in proper location (not first/last)
- ✅ `test_agent_files_stay_under_200_lines` - Files remain manageable size
- ✅ `test_existing_agent_skills_unchanged` - Regression test for 4 existing agents
- ✅ `test_skill_descriptions_are_meaningful` - Each skill has description >10 chars
- ✅ `test_no_duplicate_skills_in_agent` - Each skill appears once per agent

#### `TestSkillFormatting` (3 tests)
- ✅ `test_skill_section_has_intro_text` - Section starts with intro before skills list
- ✅ `test_skill_bullet_formatting_consistent` - Format: `- **skill-name**: Description`
- ✅ `test_skill_names_use_kebab_case` - All names use lowercase-with-hyphens

#### `TestSkillsDirectoryStructure` (3 tests)
- ✅ `test_all_19_skills_exist` - Exactly 19 skill directories
- ✅ `test_each_skill_has_metadata_file` - Each skill has SKILL.md
- ✅ `test_skill_names_match_directory_names` - Referenced skills have directories

**Total Unit Tests**: 17

### 2. Integration Tests - Skill Activation & Progressive Disclosure

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/integration/test_skill_activation.py`

**Test Classes**:

#### `TestSkillActivation` (7 tests)
- ✅ `test_implementer_loads_python_standards_skill` - Implementer references python-standards
- ✅ `test_test_master_loads_testing_guide_skill` - Test-master references testing-guide
- ✅ `test_reviewer_loads_code_review_skill` - Reviewer references code-review
- ✅ `test_security_auditor_loads_security_patterns_skill` - Security-auditor references security-patterns
- ✅ `test_advisor_loads_advisor_triggers_skill` - Advisor references advisor-triggers
- ✅ `test_multiple_agents_can_share_same_skill` - No conflicts with shared skills
- ✅ `test_skills_have_activation_keywords` - Skills have keywords for auto-activation

#### `TestProgressiveDisclosure` (3 tests)
- ✅ `test_skill_metadata_files_are_small` - SKILL.md files under 2KB
- ✅ `test_skills_have_separate_content_files` - Full content in separate files
- ✅ `test_skill_has_full_content_available` - Full content exists and substantial (>1KB)

#### `TestContextBudget` (3 tests)
- ✅ `test_single_agent_with_skills_stays_under_token_limit` - Agent + skills under 3K tokens
- ✅ `test_agent_with_8_skills_stays_manageable` - Max skills agent under 200 lines
- ✅ `test_workflow_with_multiple_agents_stays_under_8k_tokens` - Full 7-agent workflow under 8K tokens

#### `TestSkillContentLoading` (2 tests)
- ✅ `test_skill_has_full_content_available` - Full content exists and substantial
- ✅ `test_skill_metadata_references_content_files` - Metadata indicates content location

#### `TestEdgeCases` (3 tests)
- ✅ `test_agent_with_no_skills_still_works` - Agents without skills don't break
- ✅ `test_skill_with_overlapping_keywords_activates_correctly` - Overlapping keywords work
- ✅ `test_long_workflow_10_features_with_skills` - Context doesn't bloat over time

#### `TestRegressionPrevention` (3 tests)
- ✅ `test_existing_agents_retain_skill_sections` - 4 existing agents unchanged
- ✅ `test_existing_agents_maintain_line_counts` - Existing agents under 200 lines
- ✅ `test_skills_directory_unchanged` - 19 skills still exist with structure

**Total Integration Tests**: 21

## Expected Skill Mappings

Based on implementation plan, each agent should have these skills:

```python
EXPECTED_SKILL_MAPPINGS = {
    "implementer": [
        "python-standards",
        "api-design",
        "architecture-patterns",
        "code-review",
        "database-design",
    ],
    "test-master": [
        "testing-guide",
        "python-standards",
        "code-review",
        "security-patterns",
        "api-design",
    ],
    "reviewer": [
        "code-review",
        "python-standards",
        "testing-guide",
        "security-patterns",
        "architecture-patterns",
        "api-design",
    ],
    "advisor": [
        "advisor-triggers",
        "architecture-patterns",
        "security-patterns",
        "testing-guide",
        "code-review",
    ],
    "quality-validator": [
        "testing-guide",
        "code-review",
        "security-patterns",
        "consistency-enforcement",
    ],
    "alignment-validator": [
        "semantic-validation",
        "cross-reference-validation",
        "consistency-enforcement",
    ],
    "commit-message-generator": [
        "git-workflow",
        "semantic-validation",
        "consistency-enforcement",
    ],
    "pr-description-generator": [
        "github-workflow",
        "documentation-guide",
        "semantic-validation",
    ],
    "project-progress-tracker": [
        "project-management",
        "semantic-validation",
        "documentation-currency",
    ],
    "alignment-analyzer": [
        "semantic-validation",
        "cross-reference-validation",
        "project-management",
    ],
    "project-bootstrapper": [
        "architecture-patterns",
        "file-organization",
        "project-management",
    ],
    "project-status-analyzer": [
        "project-management",
        "semantic-validation",
        "observability",
    ],
    "sync-validator": [
        "consistency-enforcement",
        "file-organization",
        "semantic-validation",
    ],
}
```

## Test Coverage

### Unit Test Coverage
- **Agent Structure**: 11 tests validate proper skill section format
- **Formatting**: 3 tests ensure consistent markdown format
- **Directory Structure**: 3 tests validate skills directory integrity

### Integration Test Coverage
- **Skill Activation**: 7 tests verify skills load correctly
- **Progressive Disclosure**: 3 tests validate metadata/content separation
- **Context Budget**: 3 tests ensure token limits respected
- **Content Loading**: 2 tests verify full content availability
- **Edge Cases**: 3 tests cover error conditions
- **Regression**: 3 tests prevent breaking existing agents

### Total Coverage: 38 tests

## TDD Workflow

### Phase 1: RED (Current)
```bash
# Verify tests fail before implementation
python tests/verify_agent_skills_tdd.py

# Expected output:
# ✅ Expected failures (red phase): 2/2
# All tests fail as expected before implementation
```

### Phase 2: GREEN (Implementation)
```bash
# After implementation, run tests
pytest tests/unit/test_agent_skills.py -v
pytest tests/integration/test_skill_activation.py -v

# Expected: All tests pass
```

### Phase 3: REFACTOR (Optimization)
- Optimize skill descriptions for clarity
- Ensure consistent formatting across all agents
- Validate token budget with real usage

## Running Tests

### Run All Tests
```bash
# Run both unit and integration tests
pytest tests/unit/test_agent_skills.py tests/integration/test_skill_activation.py -v
```

### Run Unit Tests Only
```bash
pytest tests/unit/test_agent_skills.py -v
```

### Run Integration Tests Only
```bash
pytest tests/integration/test_skill_activation.py -v
```

### Run Specific Test Class
```bash
# Unit tests - agent structure
pytest tests/unit/test_agent_skills.py::TestAgentSkillsSections -v

# Integration tests - skill activation
pytest tests/integration/test_skill_activation.py::TestSkillActivation -v
```

### Run Verification Script
```bash
# Verify TDD red phase (tests should fail)
python tests/verify_agent_skills_tdd.py
```

## Quality Standards

### Test Quality Metrics
- **Clear Names**: All tests use descriptive names (GIVEN/WHEN/THEN pattern)
- **One Thing Per Test**: Each test validates one specific behavior
- **Arrange-Act-Assert**: Tests follow AAA pattern
- **No External Dependencies**: All tests use filesystem checks (no mocks needed)

### Code Quality Standards
- **Type Hints**: All test functions typed
- **Docstrings**: Each test has clear GIVEN/WHEN/THEN description
- **DRY Principle**: Common paths defined as class variables
- **Maintainability**: Tests organized by concern in separate classes

## Expected Test Results

### Before Implementation (RED Phase)
```
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_all_target_agents_have_skill_sections FAILED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_each_agent_has_correct_skill_count FAILED
... (all tests should fail)

Expected failures: 38/38
Status: ✅ TDD RED PHASE VERIFIED
```

### After Implementation (GREEN Phase)
```
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_all_target_agents_have_skill_sections PASSED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_each_agent_has_correct_skill_count PASSED
... (all tests should pass)

Passed: 38/38
Status: ✅ TDD GREEN PHASE COMPLETE
```

## Edge Cases Covered

1. **Multiple agents sharing same skill** - No conflicts
2. **Agent with maximum 8 skills** - Still manageable
3. **Overlapping skill keywords** - Both activate correctly
4. **Long workflow (10 features)** - Context doesn't bloat
5. **Agent without skills** - Doesn't break
6. **Existing agents** - Skills sections retained (regression)

## Context Budget Validation

### Token Limits Enforced
- Single agent + skill metadata: < 3K tokens
- Full 7-agent workflow: < 8K tokens per feature
- 10 sequential features: Context stays stable (with `/clear`)

### Progressive Disclosure Benefits
- Metadata in context: ~200 tokens per skill
- Full content loaded: Only when keywords trigger
- Result: 10x reduction in context usage

## Next Steps

### For Implementer Agent
1. Read this TDD summary
2. Read implementation plan from planner
3. Add "Relevant Skills" sections to 13 agents
4. Follow exact skill mappings from `EXPECTED_SKILL_MAPPINGS`
5. Match format from existing agents (researcher, planner)
6. Run tests to verify GREEN phase

### For Reviewer Agent
1. Verify all 13 agents have skill sections
2. Check skill mappings match plan
3. Validate formatting consistency
4. Confirm tests pass (green phase)

## Files Modified

### Test Files Created
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/test_agent_skills.py` (17 tests)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/integration/test_skill_activation.py` (21 tests)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/verify_agent_skills_tdd.py` (verification script)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/AGENT_SKILLS_TDD_SUMMARY.md` (this file)

### Implementation Files (To Be Modified)
- `plugins/autonomous-dev/agents/implementer.md` - Add 5 skills
- `plugins/autonomous-dev/agents/test-master.md` - Add 5 skills
- `plugins/autonomous-dev/agents/reviewer.md` - Add 6 skills
- `plugins/autonomous-dev/agents/advisor.md` - Add 5 skills
- `plugins/autonomous-dev/agents/quality-validator.md` - Add 4 skills
- `plugins/autonomous-dev/agents/alignment-validator.md` - Add 3 skills
- `plugins/autonomous-dev/agents/commit-message-generator.md` - Add 3 skills
- `plugins/autonomous-dev/agents/pr-description-generator.md` - Add 3 skills
- `plugins/autonomous-dev/agents/project-progress-tracker.md` - Add 3 skills
- `plugins/autonomous-dev/agents/alignment-analyzer.md` - Add 3 skills
- `plugins/autonomous-dev/agents/project-bootstrapper.md` - Add 3 skills
- `plugins/autonomous-dev/agents/project-status-analyzer.md` - Add 3 skills
- `plugins/autonomous-dev/agents/sync-validator.md` - Add 3 skills

### Unchanged (Regression Protection)
- `plugins/autonomous-dev/agents/researcher.md` - Has 7 skills (keep)
- `plugins/autonomous-dev/agents/planner.md` - Has 8 skills (keep)
- `plugins/autonomous-dev/agents/security-auditor.md` - Has 6 skills (keep)
- `plugins/autonomous-dev/agents/doc-master.md` - Has 4 skills (keep)
- `plugins/autonomous-dev/skills/*` - All 19 skills unchanged

## Success Criteria

### Tests Pass
- ✅ All 17 unit tests pass
- ✅ All 21 integration tests pass
- ✅ Verification script shows GREEN phase

### Code Quality
- ✅ All agents under 200 lines
- ✅ Consistent formatting across all 13 agents
- ✅ Skill descriptions meaningful (>10 chars)
- ✅ No duplicate skills per agent

### Context Budget
- ✅ Single agent: < 3K tokens
- ✅ Full workflow: < 8K tokens
- ✅ Long workflow: Context stable

### Regression Prevention
- ✅ 4 existing agents unchanged
- ✅ 19 skills directory intact
- ✅ Progressive disclosure still works

---

**TDD Phase**: RED (tests written, awaiting implementation)
**Test Count**: 38 tests (17 unit, 21 integration)
**Coverage**: Agent structure, skill activation, context budget, edge cases, regression
**Next**: Implementer agent adds skill sections, tests move to GREEN phase

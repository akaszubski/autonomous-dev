# Token Reduction Test Suite (Issues #67-70)

**TDD Red Phase**: All tests written FIRST, implementation pending

## Quick Start

```bash
# View test summary
cat tests/TOKEN_REDUCTION_TDD_SUMMARY.md

# Verify red phase (all tests failing)
python tests/verify_token_reduction_tdd_red.py

# Run specific issue tests
pytest tests/unit/skills/test_git_github_workflow_enhancement.py -v  # Issue #67
pytest tests/unit/skills/test_skill_integration_skill.py -v           # Issue #68
pytest tests/unit/skills/test_project_alignment_skill.py -v           # Issue #69
pytest tests/unit/skills/test_error_handling_enhancement.py -v        # Issue #70
pytest tests/integration/test_token_reduction_workflow.py -v          # Integration
```

## Test Organization

### Unit Tests (4 files, 112 tests)

#### Issue #67: Git/GitHub Workflow Enhancement (26 tests)
**File**: `tests/unit/skills/test_git_github_workflow_enhancement.py`
**Scope**: git-workflow and github-workflow skill enhancements
**Expected Savings**: ~300 tokens

Test Suites:
- `TestGitWorkflowSkillEnhancement` (7 tests)
- `TestGithubWorkflowSkillEnhancement` (8 tests)
- `TestAgentSkillReferences` (3 tests)
- `TestTokenReduction` (4 tests)
- `TestSkillActivation` (2 tests)

#### Issue #68: Skill Integration Skill (26 tests)
**File**: `tests/unit/skills/test_skill_integration_skill.py`
**Scope**: New skill-integration skill for all 20 agents
**Expected Savings**: ~400 tokens

Test Suites:
- `TestSkillIntegrationSkillCreation` (6 tests)
- `TestSkillIntegrationDocumentation` (3 tests)
- `TestSkillIntegrationExamples` (4 tests)
- `TestAgentSkillIntegrationReferences` (3 tests)
- `TestTokenReductionFromSkillIntegration` (2 tests)
- `TestSkillIntegrationActivation` (2 tests)

#### Issue #69: Project Alignment Skill (27 tests)
**File**: `tests/unit/skills/test_project_alignment_skill.py`
**Scope**: New project-alignment skill for 8 agents
**Expected Savings**: ~250 tokens

Test Suites:
- `TestProjectAlignmentSkillCreation` (6 tests)
- `TestProjectAlignmentDocumentation` (6 tests)
- `TestProjectAlignmentExamples` (5 tests)
- `TestAgentProjectAlignmentReferences` (8 tests)
- `TestTokenReductionFromProjectAlignment` (2 tests)
- `TestProjectAlignmentActivation` (2 tests)

#### Issue #70: Error Handling Enhancement (33 tests)
**File**: `tests/unit/skills/test_error_handling_enhancement.py`
**Scope**: Enhanced error-handling-patterns skill for 18 libraries
**Expected Savings**: ~800 tokens

Test Suites:
- `TestErrorHandlingSkillEnhancement` (3 tests)
- `TestErrorHandlingDocumentation` (4 tests)
- `TestErrorHandlingExamples` (9 tests)
- `TestLibraryErrorHandlingReferences` (4 tests)
- `TestLibraryErrorHandlingAudit` (4 tests)
- `TestTokenReductionFromErrorHandling` (3 tests)
- `TestErrorHandlingSkillActivation` (2 tests)

### Integration Tests (1 file, 20 tests)

#### Token Reduction Workflow (20 tests)
**File**: `tests/integration/test_token_reduction_workflow.py`
**Scope**: All 4 issues working together
**Expected Savings**: ~1,750 tokens total

Test Suites:
- `TestSkillActivation` (3 tests)
- `TestAgentSkillIntegration` (2 tests)
- `TestTokenMeasurement` (4 tests)
- `TestProgressiveDisclosure` (3 tests)
- `TestSkillComposition` (3 tests)
- `TestEndToEndWorkflow` (3 tests)
- `TestDocumentationCoverage` (2 tests)

## Test Coverage Summary

| Issue | File | Tests | Savings | Status |
|-------|------|-------|---------|--------|
| #67 | test_git_github_workflow_enhancement.py | 26 | ~300 | RED |
| #68 | test_skill_integration_skill.py | 26 | ~400 | RED |
| #69 | test_project_alignment_skill.py | 27 | ~250 | RED |
| #70 | test_error_handling_enhancement.py | 33 | ~800 | RED |
| Integration | test_token_reduction_workflow.py | 20 | ~1,750 | RED |
| **Total** | **5 files** | **132** | **~1,750** | **RED** |

## What Each Test Validates

### Skill Structure Tests
- ✓ Directory structure exists
- ✓ SKILL.md has valid YAML frontmatter
- ✓ Metadata fields are correct
- ✓ Keywords enable progressive disclosure
- ✓ Auto-activation is configured

### Documentation Tests
- ✓ Required docs/ files exist
- ✓ Documentation has required sections
- ✓ Checklists use proper format
- ✓ Examples show best practices
- ✓ Cross-references are valid

### Example Tests
- ✓ Required examples/ files exist
- ✓ Python examples are syntactically valid
- ✓ Examples demonstrate key patterns
- ✓ Templates are complete
- ✓ Visual diagrams are present

### Agent Integration Tests
- ✓ Agents reference appropriate skills
- ✓ Inline content is removed
- ✓ Relevant Skills sections are concise
- ✓ All 20 agents updated (Issue #68)
- ✓ Domain-specific agents updated (Issues #67, #69)

### Library Integration Tests
- ✓ Libraries reference error-handling skill
- ✓ Standard patterns are used
- ✓ Verbose documentation removed
- ✓ Skill references in comments

### Token Reduction Tests
- ✓ Per-agent token reduction measured
- ✓ Per-library token reduction measured
- ✓ Total savings across all issues
- ✓ Expected targets achieved

### Integration Tests
- ✓ Skills activate on keywords
- ✓ Skills have unique activation patterns
- ✓ Multiple skills work together
- ✓ No keyword conflicts
- ✓ Progressive disclosure works
- ✓ Context budget stays reasonable

## Implementation Checklist

### Issue #68 (Foundation) - skill-integration skill
- [ ] Create skills/skill-integration/ directory
- [ ] Create SKILL.md with frontmatter
- [ ] Create 3 documentation files
- [ ] Create 3 example files
- [ ] Update all 20 agents to reference skill
- [ ] Run tests: `pytest tests/unit/skills/test_skill_integration_skill.py -v`

### Issue #70 (Highest Savings) - error-handling-patterns enhancement
- [ ] Enhance skills/error-handling-patterns/SKILL.md
- [ ] Create docs/library-integration-guide.md
- [ ] Create 3 Python example files
- [ ] Update 18 libraries with skill references
- [ ] Create docs/LIBRARY_ERROR_HANDLING_AUDIT.md
- [ ] Run tests: `pytest tests/unit/skills/test_error_handling_enhancement.py -v`

### Issue #67 (Moderate) - git/github-workflow enhancement
- [ ] Enhance skills/git-workflow/SKILL.md
- [ ] Enhance skills/github-workflow/SKILL.md
- [ ] Create docs/commit-patterns.md
- [ ] Create docs/pr-template-guide.md
- [ ] Create docs/issue-template-guide.md
- [ ] Create 3 example files
- [ ] Update 3 agents (commit-message-generator, pr-description-generator, issue-creator)
- [ ] Run tests: `pytest tests/unit/skills/test_git_github_workflow_enhancement.py -v`

### Issue #69 (Build on Foundation) - project-alignment skill
- [ ] Create skills/project-alignment/ directory
- [ ] Create SKILL.md with frontmatter
- [ ] Create 3 documentation files
- [ ] Create 3 example files
- [ ] Update 8 agents with skill references
- [ ] Run tests: `pytest tests/unit/skills/test_project_alignment_skill.py -v`

### Integration Validation
- [ ] Run all unit tests: `pytest tests/unit/skills/test_*_*.py -v`
- [ ] Run integration tests: `pytest tests/integration/test_token_reduction_workflow.py -v`
- [ ] Measure total token reduction
- [ ] Verify ≥1,750 tokens saved
- [ ] Verify no keyword conflicts
- [ ] Verify progressive disclosure works

## Expected Outcome

After implementation (GREEN phase):
- ✓ All 132 tests pass
- ✓ ~1,750 tokens saved (10-15% improvement)
- ✓ 5 skills enhanced/created
- ✓ 20 agents updated (all reference skill-integration)
- ✓ 18 libraries updated (reference error-handling-patterns)
- ✓ Progressive disclosure prevents context bloat
- ✓ Skills composable (work together)

## Test Philosophy

### TDD Red-Green-Refactor
1. **RED**: Write failing tests (CURRENT STATE)
2. **GREEN**: Implement to make tests pass
3. **REFACTOR**: Clean up implementation

### Test Design Principles
- One test validates one requirement
- Tests are descriptive (clear failure messages)
- Tests use parametrization for coverage
- Tests measure actual tokens (not estimates)
- Tests validate both positive and negative cases

### Progressive Disclosure Testing
- Metadata stays small (<500 chars)
- Content loads on-demand
- Keywords enable activation
- Skills don't conflict
- Context budget stays reasonable

## Resources

- **Test Summary**: `tests/TOKEN_REDUCTION_TDD_SUMMARY.md`
- **Verification Script**: `tests/verify_token_reduction_tdd_red.py`
- **This README**: `tests/README_TOKEN_REDUCTION.md`

## Questions?

See test files for detailed requirements:
- Each test has descriptive docstrings
- Each assertion has helpful error messages
- Each test suite focuses on one aspect

**Status**: TDD RED PHASE COMPLETE ✓
**Next**: Implement features to make tests pass (GREEN phase)

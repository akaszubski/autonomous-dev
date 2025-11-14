# Issue #67 Test Index - Git/GitHub Workflow Skills Enhancement

Quick reference for test locations and organization.

---

## Test Files

### Unit Tests (26 tests)
**File**: `tests/unit/skills/test_git_github_workflow_enhancement.py` (530 lines)

| Test Class | Tests | Focus |
|------------|-------|-------|
| `TestGitWorkflowSkillEnhancement` | 8 | git-workflow skill files and content |
| `TestGithubWorkflowSkillEnhancement` | 10 | github-workflow skill files and content |
| `TestAgentSkillReferences` | 6 | Agent integration with skills |
| `TestTokenReduction` | 4 | Token savings validation |
| `TestSkillActivation` | 2 | Progressive disclosure activation |

### Integration Tests (10 tests)
**File**: `tests/integration/test_token_reduction_workflow.py` (530 lines)

| Test Class | Tests | Focus |
|------------|-------|-------|
| `TestSkillActivation` | 3 | Skill metadata and keyword activation |
| `TestAgentSkillIntegration` | 3 | Agent-skill references and integration |
| `TestSkillComposition` | 2 | Multiple skills working together |
| `TestEndToEndWorkflow` | 2 | Complete workflow with skills |

---

## Test Coverage Map

### git-workflow Skill (8 unit tests)

**Documentation Tests**:
- `test_commit_patterns_doc_exists` → `skills/git-workflow/docs/commit-patterns.md`
- `test_commit_patterns_has_conventional_commit_types` → feat:, fix:, docs:, etc.
- `test_commit_patterns_has_breaking_change_guidance` → BREAKING CHANGE:, feat!:
- `test_commit_patterns_has_scope_guidance` → feat(api): syntax

**Example Tests**:
- `test_commit_examples_file_exists` → `skills/git-workflow/examples/commit-examples.txt`
- `test_commit_examples_has_real_world_examples` → ≥10 examples

**Metadata Tests**:
- `test_git_workflow_skill_metadata_updated` → Keywords: "commit", "conventional commits"
- `test_git_workflow_skill_references_commit_patterns_doc` → References new docs

### github-workflow Skill (10 unit tests)

**PR Template Tests**:
- `test_pr_template_guide_exists` → `skills/github-workflow/docs/pr-template-guide.md`
- `test_pr_template_guide_has_standard_sections` → Summary, Test plan, Changes, Breaking changes
- `test_pr_template_guide_has_best_practices` → concise, bullets, why, testing
- `test_pr_template_example_exists` → `skills/github-workflow/examples/pr-template.md`
- `test_pr_template_example_has_all_sections` → Complete example

**Issue Template Tests**:
- `test_issue_template_guide_exists` → `skills/github-workflow/docs/issue-template-guide.md`
- `test_issue_template_guide_has_standard_sections` → Problem, Solution, Context, Acceptance criteria
- `test_issue_template_example_exists` → `skills/github-workflow/examples/issue-template.md`
- `test_issue_template_example_has_all_sections` → Complete example

**Metadata Tests**:
- `test_github_workflow_skill_metadata_updated` → Keywords: "pull request", "issue"

### Agent Integration (6 unit tests)

**Skill Reference Tests** (parametrized):
- `test_agent_references_skill[commit-message-generator-git-workflow]`
- `test_agent_references_skill[pr-description-generator-github-workflow]`
- `test_agent_references_skill[issue-creator-github-workflow]`

**Inline Content Removal Tests** (parametrized):
- `test_agent_removes_inline_patterns[commit-message-generator-conventional commit]`
- `test_agent_removes_inline_patterns[pr-description-generator-PR template]`
- `test_agent_removes_inline_patterns[issue-creator-issue template]`

### Token Reduction (4 unit tests)

- `test_commit_message_generator_token_reduction` → ≤600 tokens (from ~1,214)
- `test_pr_description_generator_token_reduction` → ≤700 tokens
- `test_issue_creator_token_reduction` → ≤800 tokens
- `test_total_token_savings_achieved` → ≥300 tokens total

### Progressive Disclosure (2 unit tests + 3 integration tests)

**Unit Tests**:
- `test_git_workflow_skill_activates_on_commit_keywords` → auto_activate: true
- `test_github_workflow_skill_activates_on_pr_issue_keywords` → auto_activate: true

**Integration Tests**:
- `test_skill_metadata_loads` → YAML frontmatter validation
- `test_skill_activates_on_keywords` → Keyword-based activation
- `test_skills_have_unique_keywords` → ≤50% keyword overlap

---

## Running Tests

### All Tests for Issue #67
```bash
# Run all unit tests
pytest tests/unit/skills/test_git_github_workflow_enhancement.py -v

# Run all integration tests (Issue #67 relevant)
pytest tests/integration/test_token_reduction_workflow.py::TestAgentSkillIntegration -v
pytest tests/integration/test_token_reduction_workflow.py::TestSkillActivation -v

# Run everything with coverage
pytest tests/unit/skills/test_git_github_workflow_enhancement.py \
       tests/integration/test_token_reduction_workflow.py::TestAgentSkillIntegration \
       tests/integration/test_token_reduction_workflow.py::TestSkillActivation \
       --cov --cov-report=term-missing -v
```

### By Test Suite
```bash
# Git-workflow skill tests only
pytest tests/unit/skills/test_git_github_workflow_enhancement.py::TestGitWorkflowSkillEnhancement -v

# GitHub-workflow skill tests only
pytest tests/unit/skills/test_git_github_workflow_enhancement.py::TestGithubWorkflowSkillEnhancement -v

# Agent integration tests only
pytest tests/unit/skills/test_git_github_workflow_enhancement.py::TestAgentSkillReferences -v

# Token reduction tests only
pytest tests/unit/skills/test_git_github_workflow_enhancement.py::TestTokenReduction -v
```

### Single Test
```bash
# Example: Test commit patterns doc exists
pytest tests/unit/skills/test_git_github_workflow_enhancement.py::TestGitWorkflowSkillEnhancement::test_commit_patterns_doc_exists -v
```

---

## Expected Test Results (Red Phase)

### Current State
```
================================= FAILURES =================================
________________________ test_commit_patterns_doc_exists ________________________
AssertionError: Commit patterns doc not found: .../skills/git-workflow/docs/commit-patterns.md
Expected: Create skills/git-workflow/docs/commit-patterns.md
Content: Conventional commit patterns (feat:, fix:, docs:, etc.)
See: Issue #67

... (25 more unit test failures)
... (10 integration test failures)

======================== 36 failed in 2.45s ========================
```

### After Implementation (Green Phase)
```
======================== 36 passed in 2.45s ========================
```

---

## Test Quality Checklist

- [x] All tests follow Arrange-Act-Assert pattern
- [x] Clear test names describe requirements
- [x] One assertion per test (where appropriate)
- [x] Parametrized tests for agent variations
- [x] Edge cases covered (missing files, incomplete content)
- [x] Mock usage for file operations
- [x] Test independence (no shared state)
- [x] Clear error messages with context
- [x] Coverage target: 100% of requirements

---

## Files Created During Red Phase

1. **Unit Test File**: `tests/unit/skills/test_git_github_workflow_enhancement.py` (530 lines, 26 tests)
2. **Integration Test File**: `tests/integration/test_token_reduction_workflow.py` (530 lines, 10 relevant tests)
3. **Summary Document**: `tests/ISSUE_67_TDD_RED_PHASE_SUMMARY.md` (comprehensive guide)
4. **This Index**: `tests/ISSUE_67_TEST_INDEX.md` (quick reference)

---

**Status**: TDD Red Phase Complete - Ready for Implementation

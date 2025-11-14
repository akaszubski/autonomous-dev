# TDD Red Phase Summary - Issue #67: Git/GitHub Workflow Skills Enhancement

**Agent**: test-master
**Date**: 2025-11-14
**Status**: COMPLETE - Tests Written FIRST (Red Phase)
**Issue**: GitHub #67 - Extract git-github-workflow-patterns skill

---

## Test Coverage Summary

**Total Tests**: 36 tests (26 unit + 10 integration)
**Coverage Target**: 100% of skill enhancement requirements
**Expected State**: ALL TESTS FAILING (no implementation yet)

### Unit Tests (26 tests)

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/skills/test_git_github_workflow_enhancement.py`

#### Suite 1: git-workflow Skill Enhancement (8 tests)
1. `test_commit_patterns_doc_exists` - Validates `docs/commit-patterns.md` exists
2. `test_commit_patterns_has_conventional_commit_types` - Validates all commit types (feat, fix, docs, etc.)
3. `test_commit_patterns_has_breaking_change_guidance` - Validates BREAKING CHANGE syntax
4. `test_commit_patterns_has_scope_guidance` - Validates scope syntax (feat(api):)
5. `test_commit_examples_file_exists` - Validates `examples/commit-examples.txt` exists
6. `test_commit_examples_has_real_world_examples` - Validates ≥10 real-world examples
7. `test_git_workflow_skill_metadata_updated` - Validates commit keywords in SKILL.md
8. `test_git_workflow_skill_references_commit_patterns_doc` - Validates skill references new docs

#### Suite 2: github-workflow Skill Enhancement (10 tests)
9. `test_pr_template_guide_exists` - Validates `docs/pr-template-guide.md` exists
10. `test_pr_template_guide_has_standard_sections` - Validates PR sections (Summary, Test plan, etc.)
11. `test_pr_template_guide_has_best_practices` - Validates PR best practices documented
12. `test_issue_template_guide_exists` - Validates `docs/issue-template-guide.md` exists
13. `test_issue_template_guide_has_standard_sections` - Validates issue sections (Problem, Solution, etc.)
14. `test_pr_template_example_exists` - Validates `examples/pr-template.md` exists
15. `test_pr_template_example_has_all_sections` - Validates example has all sections
16. `test_issue_template_example_exists` - Validates `examples/issue-template.md` exists
17. `test_issue_template_example_has_all_sections` - Validates example has all sections
18. `test_github_workflow_skill_metadata_updated` - Validates PR/issue keywords in SKILL.md

#### Suite 3: Agent Integration (6 tests)
19. `test_agent_references_skill` - **Parametrized** (3 agents): Validates each agent references correct skill
    - commit-message-generator → git-workflow
    - pr-description-generator → github-workflow
    - issue-creator → github-workflow
20. `test_agent_removes_inline_patterns` - **Parametrized** (3 agents): Validates inline content removed
    - commit-message-generator: ≤2 mentions of "conventional commit"
    - pr-description-generator: ≤2 mentions of "PR template"
    - issue-creator: ≤2 mentions of "issue template"

#### Suite 4: Token Reduction (4 tests)
21. `test_commit_message_generator_token_reduction` - Validates ~100 tokens saved (≤600 total tokens)
22. `test_pr_description_generator_token_reduction` - Validates ~100 tokens saved (≤700 total tokens)
23. `test_issue_creator_token_reduction` - Validates ~100 tokens saved (≤800 total tokens)
24. `test_total_token_savings_achieved` - Validates ≥300 total tokens saved

#### Suite 5: Skill Activation (2 tests)
25. `test_git_workflow_skill_activates_on_commit_keywords` - Validates auto_activate: true
26. `test_github_workflow_skill_activates_on_pr_issue_keywords` - Validates auto_activate: true

---

### Integration Tests (10 tests)

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/integration/test_token_reduction_workflow.py`

#### Suite 1: Skill Activation (3 tests)
1. `test_skill_metadata_loads` - **Parametrized** (2 skills): Validates skills load correctly
    - git-workflow
    - github-workflow
2. `test_skill_activates_on_keywords` - **Parametrized** (2 skills): Validates keyword activation
    - git-workflow: ["commit", "conventional commits"]
    - github-workflow: ["pull request", "issue"]
3. `test_skills_have_unique_keywords` - Validates skills don't over-overlap (≤50% keyword overlap)

#### Suite 2: Agent-Skill Integration (3 tests)
4. `test_agents_reference_appropriate_skills` - **Parametrized** (1 issue): Validates #67 agents reference correct skills
5. `test_agents_have_concise_relevant_skills_sections` - Validates Relevant Skills sections ≤50 tokens
6. `test_skill_content_not_duplicated_in_agents` - Validates content in skills, not agents

#### Suite 3: Skill Composition (2 tests)
7. `test_commit_message_generator_uses_both_git_skills` - Validates multi-skill usage
8. `test_alignment_validator_uses_multiple_skills` - Validates skill composition works

#### Suite 4: End-to-End Workflow (2 tests)
9. `test_agent_workflow_loads_skills_progressively` - Validates progressive disclosure architecture
10. `test_workflow_performance_with_skills` - Validates ≥15% token reduction (1,750 tokens)

---

## Test Quality Metrics

### Arrange-Act-Assert Pattern
- ✅ All tests follow AAA structure
- ✅ Clear test names describe requirements
- ✅ One assertion per test (where appropriate)

### Edge Cases Covered
- ✅ Missing files (FAIL until created)
- ✅ Incomplete content (FAIL until complete)
- ✅ Token thresholds (FAIL if not met)
- ✅ Keyword activation (FAIL if misconfigured)
- ✅ Skill overlap (FAIL if >50% duplicate keywords)

### Mock Usage
- ✅ File system operations (Path.exists(), Path.read_text())
- ✅ YAML parsing (yaml.safe_load)
- ✅ Regex matching (re.compile, re.search)
- ✅ Progressive disclosure validation

### Test Independence
- ✅ Each test runs independently
- ✅ No shared state between tests
- ✅ Parametrized tests for agent variations
- ✅ Clear error messages with context

---

## Expected Failures (Red Phase)

### Unit Test Failures (26 tests)

**Git-Workflow Skill** (8 failures):
```
FAILED test_commit_patterns_doc_exists - AssertionError:
    Commit patterns doc not found: .../skills/git-workflow/docs/commit-patterns.md
    Expected: Create skills/git-workflow/docs/commit-patterns.md
    Content: Conventional commit patterns (feat:, fix:, docs:, etc.)
    See: Issue #67

FAILED test_commit_examples_file_exists - AssertionError:
    Commit examples file not found: .../skills/git-workflow/examples/commit-examples.txt
    Expected: Create skills/git-workflow/examples/commit-examples.txt
    Content: Real-world commit message examples
    See: Issue #67

... (6 more git-workflow tests)
```

**GitHub-Workflow Skill** (10 failures):
```
FAILED test_pr_template_guide_exists - AssertionError:
    PR template guide not found: .../skills/github-workflow/docs/pr-template-guide.md
    Expected: Create skills/github-workflow/docs/pr-template-guide.md
    Content: PR description structure and best practices
    See: Issue #67

FAILED test_issue_template_guide_exists - AssertionError:
    Issue template guide not found: .../skills/github-workflow/docs/issue-template-guide.md
    Expected: Create skills/github-workflow/docs/issue-template-guide.md
    Content: Issue description structure and best practices
    See: Issue #67

... (8 more github-workflow tests)
```

**Agent Integration** (6 failures):
```
FAILED test_agent_references_skill[commit-message-generator-git-workflow] - AssertionError:
    Agent commit-message-generator should reference git-workflow skill
    Expected: Add 'git-workflow' to Relevant Skills section
    See: Issue #67

FAILED test_agent_removes_inline_patterns[commit-message-generator-conventional commit] - AssertionError:
    Agent commit-message-generator still contains inline 'conventional commit' guidance
    Expected: Remove inline content, reference git-workflow skill instead
    Found 8 mentions (expected <= 2)
    See: Issue #67

... (4 more agent integration tests)
```

**Token Reduction** (4 failures):
```
FAILED test_commit_message_generator_token_reduction - AssertionError:
    commit-message-generator token count too high: 1214
    Expected: ~100 token reduction from skill extraction
    See: Issue #67

FAILED test_total_token_savings_achieved - AssertionError:
    Total token savings too low: 0
    Expected: ~300 tokens saved across 3 agents
    See: Issue #67

... (2 more token tests)
```

### Integration Test Failures (10 tests)

**Skill Activation** (3 failures):
```
FAILED test_skill_metadata_loads[git-workflow] - AssertionError:
    Skill file not found: .../skills/git-workflow/SKILL.md
    Expected: Skills should exist for integration testing
    See: Issues #67-70

FAILED test_skill_activates_on_keywords[git-workflow-keywords] - AssertionError:
    Skill git-workflow missing expected keywords
    Expected: At least 1 of ['commit', 'conventional commits']
    Found keywords: []

... (1 more skill activation test)
```

**Agent-Skill Integration** (3 failures):
```
FAILED test_agents_reference_appropriate_skills[#67] - AssertionError:
    Agent commit-message-generator should reference git-workflow skill
    Expected: All agents reference appropriate skills
    See: Issue #67

... (2 more integration tests)
```

**Workflow Performance** (2 failures):
```
FAILED test_workflow_performance_with_skills - AssertionError:
    Expected token reduction: 17.5%
    Expected: >15% improvement in workflow token usage
    Total savings: 1750 tokens

FAILED test_agent_workflow_loads_skills_progressively - AssertionError:
    Skill git-workflow needs keywords for progressive activation
```

---

## Implementation Requirements

Based on these tests, the implementer must create:

### Git-Workflow Skill Files (3 new files)
1. **`skills/git-workflow/docs/commit-patterns.md`** (~200 lines)
   - All conventional commit types (feat, fix, docs, style, refactor, test, chore)
   - Breaking change syntax (BREAKING CHANGE: footer, feat!: syntax)
   - Scope guidance (feat(api): syntax)
   - Best practices and examples

2. **`skills/git-workflow/examples/commit-examples.txt`** (~50 lines)
   - ≥10 real-world commit message examples
   - Various types (feat, fix, docs, etc.)
   - Breaking changes examples
   - Scoped commits examples

3. **`skills/git-workflow/SKILL.md`** (update metadata)
   - Add commit-related keywords: "commit", "conventional commits", "commit message", "commit patterns"
   - Reference commit-patterns.md in content
   - Set auto_activate: true

### GitHub-Workflow Skill Files (5 new files)
4. **`skills/github-workflow/docs/pr-template-guide.md`** (~150 lines)
   - Standard PR sections: Summary, Test plan, Changes, Breaking changes
   - Best practices: concise, bullets, why-focused, testing
   - Examples and anti-patterns

5. **`skills/github-workflow/docs/issue-template-guide.md`** (~150 lines)
   - Standard issue sections: Problem, Solution, Context, Acceptance criteria
   - Best practices: clarity, actionability, completeness
   - Examples and templates

6. **`skills/github-workflow/examples/pr-template.md`** (~50 lines)
   - Complete example PR description
   - All standard sections
   - Real-world content

7. **`skills/github-workflow/examples/issue-template.md`** (~50 lines)
   - Complete example issue description
   - All standard sections
   - Real-world content

8. **`skills/github-workflow/SKILL.md`** (update metadata)
   - Add PR/issue keywords: "pull request", "pr description", "issue", "github issue"
   - Reference new docs in content
   - Set auto_activate: true

### Agent Updates (3 agents)
9. **`agents/commit-message-generator.md`** (streamline)
   - Remove inline commit type definitions (~50 lines)
   - Add git-workflow to Relevant Skills section
   - Reference skill instead of duplicating content
   - Expected: ~100 tokens saved (from ~1,214 to ~500 tokens)

10. **`agents/pr-description-generator.md`** (streamline)
    - Remove inline PR template guidance (~60 lines)
    - Add github-workflow to Relevant Skills section
    - Reference skill instead of duplicating content
    - Expected: ~100 tokens saved

11. **`agents/issue-creator.md`** (streamline)
    - Remove inline issue template guidance (~60 lines)
    - Add github-workflow to Relevant Skills section
    - Reference skill instead of duplicating content
    - Expected: ~100 tokens saved

---

## Success Criteria

### All Tests Pass (Green Phase)
- ✅ 26/26 unit tests pass
- ✅ 10/10 integration tests pass
- ✅ 36/36 total tests pass

### Token Reduction Achieved
- ✅ commit-message-generator: ≤600 tokens (currently ~1,214)
- ✅ pr-description-generator: ≤700 tokens
- ✅ issue-creator: ≤800 tokens
- ✅ Total savings: ≥300 tokens (5-8% reduction)

### Quality Standards Met
- ✅ All documentation files exist and are complete
- ✅ All example files have real-world content
- ✅ All skills have progressive disclosure metadata
- ✅ All agents reference skills in Relevant Skills sections
- ✅ No content duplication between agents and skills

### Architecture Validated
- ✅ Progressive disclosure works (skills load on-demand)
- ✅ Skill activation keywords are unique (≤50% overlap)
- ✅ Multiple skills compose correctly
- ✅ Workflow performance improves (≥15% token reduction)

---

## Test Execution Commands

```bash
# Run all unit tests
pytest tests/unit/skills/test_git_github_workflow_enhancement.py -v

# Run specific test suite
pytest tests/unit/skills/test_git_github_workflow_enhancement.py::TestGitWorkflowSkillEnhancement -v

# Run all integration tests
pytest tests/integration/test_token_reduction_workflow.py::TestAgentSkillIntegration -v

# Run all tests with coverage
pytest tests/unit/skills/test_git_github_workflow_enhancement.py \
       tests/integration/test_token_reduction_workflow.py::TestAgentSkillIntegration \
       --cov --cov-report=term-missing -v

# Run single test
pytest tests/unit/skills/test_git_github_workflow_enhancement.py::TestGitWorkflowSkillEnhancement::test_commit_patterns_doc_exists -v
```

---

## Notes

- **TDD Principle**: Tests written FIRST, before implementation
- **Red Phase**: All tests currently FAILING (expected)
- **Green Phase**: Implementer makes tests pass
- **Refactor Phase**: Optimize after green

- **Progressive Disclosure**: Skills load on-demand, not all at once
- **Token Budget**: Saves ~300 tokens (5-8% reduction in git/github guidance)
- **Quality**: No compromise - all guidance preserved in skills

- **Pattern Match**: Follows proven pattern from Issue #65 (testing-guide skill)
- **Scalability**: Can scale to 50-100+ skills without context bloat
- **Maintainability**: One source of truth for git/github patterns

---

## File Locations

**Test Files**:
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/skills/test_git_github_workflow_enhancement.py` (530 lines, 26 tests)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/integration/test_token_reduction_workflow.py` (530 lines, 10 relevant tests)

**Skill Directories**:
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/skills/git-workflow/`
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/skills/github-workflow/`

**Agent Files**:
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/commit-message-generator.md`
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/pr-description-generator.md`
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/issue-creator.md`

---

**End of TDD Red Phase Summary - Issue #67**

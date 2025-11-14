# Issue #67 Test Architecture - Visual Structure

```
tests/
├── unit/
│   └── skills/
│       └── test_git_github_workflow_enhancement.py (26 tests)
│           │
│           ├── TestGitWorkflowSkillEnhancement (8 tests)
│           │   ├── test_commit_patterns_doc_exists
│           │   ├── test_commit_patterns_has_conventional_commit_types
│           │   ├── test_commit_patterns_has_breaking_change_guidance
│           │   ├── test_commit_patterns_has_scope_guidance
│           │   ├── test_commit_examples_file_exists
│           │   ├── test_commit_examples_has_real_world_examples
│           │   ├── test_git_workflow_skill_metadata_updated
│           │   └── test_git_workflow_skill_references_commit_patterns_doc
│           │
│           ├── TestGithubWorkflowSkillEnhancement (10 tests)
│           │   ├── test_pr_template_guide_exists
│           │   ├── test_pr_template_guide_has_standard_sections
│           │   ├── test_pr_template_guide_has_best_practices
│           │   ├── test_issue_template_guide_exists
│           │   ├── test_issue_template_guide_has_standard_sections
│           │   ├── test_pr_template_example_exists
│           │   ├── test_pr_template_example_has_all_sections
│           │   ├── test_issue_template_example_exists
│           │   ├── test_issue_template_example_has_all_sections
│           │   └── test_github_workflow_skill_metadata_updated
│           │
│           ├── TestAgentSkillReferences (6 tests)
│           │   ├── test_agent_references_skill (3 parametrized)
│           │   │   ├── [commit-message-generator-git-workflow]
│           │   │   ├── [pr-description-generator-github-workflow]
│           │   │   └── [issue-creator-github-workflow]
│           │   └── test_agent_removes_inline_patterns (3 parametrized)
│           │       ├── [commit-message-generator-conventional commit]
│           │       ├── [pr-description-generator-PR template]
│           │       └── [issue-creator-issue template]
│           │
│           ├── TestTokenReduction (4 tests)
│           │   ├── test_commit_message_generator_token_reduction
│           │   ├── test_pr_description_generator_token_reduction
│           │   ├── test_issue_creator_token_reduction
│           │   └── test_total_token_savings_achieved
│           │
│           └── TestSkillActivation (2 tests)
│               ├── test_git_workflow_skill_activates_on_commit_keywords
│               └── test_github_workflow_skill_activates_on_pr_issue_keywords
│
└── integration/
    └── test_token_reduction_workflow.py (10 relevant tests)
        │
        ├── TestSkillActivation (3 tests)
        │   ├── test_skill_metadata_loads (parametrized: git-workflow, github-workflow)
        │   ├── test_skill_activates_on_keywords (parametrized: git-workflow, github-workflow)
        │   └── test_skills_have_unique_keywords
        │
        ├── TestAgentSkillIntegration (3 tests)
        │   ├── test_agents_reference_appropriate_skills (parametrized: #67)
        │   ├── test_agents_have_concise_relevant_skills_sections
        │   └── test_skill_content_not_duplicated_in_agents
        │
        ├── TestSkillComposition (2 tests)
        │   ├── test_commit_message_generator_uses_both_git_skills
        │   └── test_alignment_validator_uses_multiple_skills
        │
        └── TestEndToEndWorkflow (2 tests)
            ├── test_agent_workflow_loads_skills_progressively
            └── test_workflow_performance_with_skills
```

---

## Test-to-Implementation Mapping

### git-workflow Skill

```
Unit Tests (8)                     Implementation Required
├─ Documentation Tests (4)         ├─ docs/commit-patterns.md (~200 lines)
│  ├─ File exists                  │  ├─ Conventional commit types
│  ├─ Commit types                 │  ├─ Breaking change syntax
│  ├─ Breaking changes             │  ├─ Scope guidance
│  └─ Scope syntax                 │  └─ Best practices
│                                   │
├─ Example Tests (2)               ├─ examples/commit-examples.txt (~50 lines)
│  ├─ File exists                  │  └─ ≥10 real-world examples
│  └─ ≥10 examples                 │
│                                   │
└─ Metadata Tests (2)              └─ SKILL.md (metadata update)
   ├─ Keywords updated                ├─ Keywords: commit, conventional commits
   └─ References docs                 └─ auto_activate: true
```

### github-workflow Skill

```
Unit Tests (10)                    Implementation Required
├─ PR Template Tests (5)           ├─ docs/pr-template-guide.md (~150 lines)
│  ├─ Guide exists                 │  ├─ Standard sections
│  ├─ Standard sections            │  └─ Best practices
│  ├─ Best practices               │
│  ├─ Example exists               ├─ examples/pr-template.md (~50 lines)
│  └─ Example complete             │  └─ Complete example
│                                   │
├─ Issue Template Tests (4)        ├─ docs/issue-template-guide.md (~150 lines)
│  ├─ Guide exists                 │  ├─ Standard sections
│  ├─ Standard sections            │  └─ Best practices
│  ├─ Example exists               │
│  └─ Example complete             ├─ examples/issue-template.md (~50 lines)
│                                   │  └─ Complete example
└─ Metadata Tests (1)              │
   └─ Keywords updated             └─ SKILL.md (metadata update)
                                      ├─ Keywords: PR, issue
                                      └─ auto_activate: true
```

### Agent Integration

```
Unit Tests (6)                     Implementation Required
├─ Skill References (3)            ├─ agents/commit-message-generator.md
│  ├─ commit → git-workflow        │  ├─ Remove inline commit types (~50 lines)
│  ├─ pr → github-workflow         │  └─ Add git-workflow to Relevant Skills
│  └─ issue → github-workflow      │
│                                   ├─ agents/pr-description-generator.md
└─ Inline Removal (3)              │  ├─ Remove inline PR template (~60 lines)
   ├─ commit ≤2 mentions           │  └─ Add github-workflow to Relevant Skills
   ├─ PR ≤2 mentions               │
   └─ issue ≤2 mentions            └─ agents/issue-creator.md
                                      ├─ Remove inline issue template (~60 lines)
                                      └─ Add github-workflow to Relevant Skills
```

### Token Reduction

```
Unit Tests (4)                     Expected Results
├─ commit-message-generator        ├─ From ~1,214 → ≤600 tokens (~100 saved)
├─ pr-description-generator        ├─ ≤700 tokens (~100 saved)
├─ issue-creator                   ├─ ≤800 tokens (~100 saved)
└─ Total savings                   └─ ≥300 tokens (5-8% reduction)
```

---

## Test Execution Flow

```
1. pytest discovers tests/unit/skills/test_git_github_workflow_enhancement.py
   ↓
2. Runs 5 test classes sequentially:
   ├─ TestGitWorkflowSkillEnhancement (8 tests)
   ├─ TestGithubWorkflowSkillEnhancement (10 tests)
   ├─ TestAgentSkillReferences (6 tests)
   ├─ TestTokenReduction (4 tests)
   └─ TestSkillActivation (2 tests)
   ↓
3. Each test follows AAA pattern:
   Arrange: Load file paths, define expectations
   Act: Read files, extract content
   Assert: Validate requirements
   ↓
4. pytest discovers tests/integration/test_token_reduction_workflow.py
   ↓
5. Runs 4 test classes (10 relevant tests):
   ├─ TestSkillActivation (3 tests)
   ├─ TestAgentSkillIntegration (3 tests)
   ├─ TestSkillComposition (2 tests)
   └─ TestEndToEndWorkflow (2 tests)
   ↓
6. Integration tests validate end-to-end workflow:
   Arrange: Set up skills and agents
   Act: Simulate skill activation
   Assert: Validate integration works
   ↓
7. Report results:
   RED PHASE: 36 failed (expected)
   GREEN PHASE: 36 passed (after implementation)
```

---

## Test Dependencies

```
Unit Tests
├─ pytest
├─ PyYAML (yaml.safe_load)
├─ pathlib (Path operations)
└─ re (regex for pattern matching)

Integration Tests
├─ pytest
├─ PyYAML (yaml.safe_load)
├─ pathlib (Path operations)
└─ unittest.mock (Mock, patch)

No External Dependencies:
✓ No network calls
✓ No database operations
✓ No file writes (read-only)
✓ All tests are deterministic
```

---

## Coverage Metrics

```
Skill Files Tested:
├─ git-workflow/docs/commit-patterns.md          [8 tests]
├─ git-workflow/examples/commit-examples.txt     [2 tests]
├─ git-workflow/SKILL.md                         [2 tests]
├─ github-workflow/docs/pr-template-guide.md     [5 tests]
├─ github-workflow/docs/issue-template-guide.md  [4 tests]
├─ github-workflow/examples/pr-template.md       [2 tests]
├─ github-workflow/examples/issue-template.md    [2 tests]
└─ github-workflow/SKILL.md                      [1 test]

Agent Files Tested:
├─ agents/commit-message-generator.md            [3 tests]
├─ agents/pr-description-generator.md            [3 tests]
└─ agents/issue-creator.md                       [3 tests]

Total Coverage: 100% of Issue #67 requirements
```

---

## Quality Gates

```
✓ All tests follow TDD principles (tests first)
✓ All tests follow AAA pattern
✓ All tests have clear names
✓ All tests are independent
✓ All tests have descriptive error messages
✓ All tests validate one requirement
✓ All parametrized tests cover agent variations
✓ All edge cases covered (missing files, incomplete content)
✓ All tests are deterministic (no randomness)
✓ All tests are fast (<1s each)
```

---

**End of Test Architecture - Issue #67**

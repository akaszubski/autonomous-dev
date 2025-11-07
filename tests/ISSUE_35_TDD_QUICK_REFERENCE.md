# Issue #35 TDD Quick Reference Card

**Status**: RED PHASE ✅ (Tests written, awaiting implementation)

## Quick Commands

### Run All Tests
```bash
source .venv/bin/activate
pytest tests/unit/test_agent_skills.py tests/integration/test_skill_activation.py -v
```

### Verify TDD Phase
```bash
python tests/verify_agent_skills_tdd.py
```

### Run Single Test
```bash
pytest tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_all_target_agents_have_skill_sections -v
```

## What Was Created

### Test Files
- `tests/unit/test_agent_skills.py` - 17 unit tests
- `tests/integration/test_skill_activation.py` - 21 integration tests
- `tests/verify_agent_skills_tdd.py` - Automated verification

### Documentation
- `tests/AGENT_SKILLS_TDD_SUMMARY.md` - Complete test suite summary
- `tests/AGENT_SKILLS_TDD_RED_VERIFICATION.md` - RED phase verification results
- `tests/RUN_AGENT_SKILLS_TESTS.md` - Test running guide
- `tests/ISSUE_35_TDD_QUICK_REFERENCE.md` - This file

## Current Test Results

**Unit Tests**: 6 failed, 4 passed (expected in RED phase)
**Integration Tests**: 5 failed, 2 passed (expected in RED phase)
**Total**: 11 failing tests (out of 38 total)

### Key Failing Tests (Expected)
```
❌ test_all_target_agents_have_skill_sections - "implementer missing Relevant Skills"
❌ test_implementer_loads_python_standards_skill - "python-standards not found"
❌ test_test_master_loads_testing_guide_skill - "testing-guide not found"
❌ test_reviewer_loads_code_review_skill - "code-review not found"
```

### Passing Tests (Expected)
```
✅ test_agents_directory_exists - Infrastructure OK
✅ test_existing_agent_skills_unchanged - Regression protection
✅ test_security_auditor_loads_security_patterns_skill - Already has skills
```

## What Needs to Be Implemented

### 13 Agents Need Skill Sections

1. implementer (5 skills)
2. test-master (5 skills)
3. reviewer (6 skills)
4. advisor (5 skills)
5. quality-validator (4 skills)
6. alignment-validator (3 skills)
7. commit-message-generator (3 skills)
8. pr-description-generator (3 skills)
9. project-progress-tracker (3 skills)
10. alignment-analyzer (3 skills)
11. project-bootstrapper (3 skills)
12. project-status-analyzer (3 skills)
13. sync-validator (3 skills)

### Pattern to Follow

```markdown
## Relevant Skills

You have access to these specialized skills when [agent's task]:

- **skill-name**: Description of when/how skill helps (>10 chars)
- **another-skill**: Another helpful description
- **third-skill**: Yet another description
```

### Example (from researcher.md)

```markdown
## Relevant Skills

You have access to these specialized skills when researching patterns:

- **research-patterns**: Research methodology, pattern discovery, best practice frameworks
- **architecture-patterns**: Understanding system design decisions and trade-offs
- **python-standards**: Python language conventions and best practices
- **security-patterns**: Security vulnerabilities and safe patterns
- **api-design**: REST API best practices and standards
- **database-design**: Database patterns and optimization approaches
- **testing-guide**: Testing strategies and methodologies
```

## Skill Mappings (Copy These Exactly)

### Core Workflow Agents

**implementer**:
- python-standards
- api-design
- architecture-patterns
- code-review
- database-design

**test-master**:
- testing-guide
- python-standards
- code-review
- security-patterns
- api-design

**reviewer**:
- code-review
- python-standards
- testing-guide
- security-patterns
- architecture-patterns
- api-design

**advisor**:
- advisor-triggers
- architecture-patterns
- security-patterns
- testing-guide
- code-review

**quality-validator**:
- testing-guide
- code-review
- security-patterns
- consistency-enforcement

### Utility Agents

**alignment-validator**:
- semantic-validation
- cross-reference-validation
- consistency-enforcement

**commit-message-generator**:
- git-workflow
- semantic-validation
- consistency-enforcement

**pr-description-generator**:
- github-workflow
- documentation-guide
- semantic-validation

**project-progress-tracker**:
- project-management
- semantic-validation
- documentation-currency

**alignment-analyzer**:
- semantic-validation
- cross-reference-validation
- project-management

**project-bootstrapper**:
- architecture-patterns
- file-organization
- project-management

**project-status-analyzer**:
- project-management
- semantic-validation
- observability

**sync-validator**:
- consistency-enforcement
- file-organization
- semantic-validation

## After Implementation

### Run Tests
```bash
pytest tests/unit/test_agent_skills.py tests/integration/test_skill_activation.py -v
```

### Expected Result
```
tests/unit/test_agent_skills.py ................. [ 45%]  17 passed
tests/integration/test_skill_activation.py ....................... [100%]  21 passed

============================== 38 passed in X.XXs ==============================
```

### Verify GREEN Phase
```bash
python tests/verify_agent_skills_tdd.py
```

### Expected Output
```
⚠️  TDD RED PHASE INCOMPLETE
Tests should fail before implementation!

# This means GREEN phase achieved! Script detects tests passing.
```

## Success Criteria

### All Tests Pass
- ✅ 17 unit tests pass
- ✅ 21 integration tests pass
- ✅ 38/38 total tests passing

### Code Quality
- ✅ All 13 agents have skill sections
- ✅ Skills match exact mappings above
- ✅ Format matches researcher.md pattern
- ✅ All files under 200 lines

### Regression Protection
- ✅ 4 existing agents unchanged (researcher, planner, security-auditor, doc-master)
- ✅ 19 skills directory intact

## Files to Modify

```
plugins/autonomous-dev/agents/implementer.md
plugins/autonomous-dev/agents/test-master.md
plugins/autonomous-dev/agents/reviewer.md
plugins/autonomous-dev/agents/advisor.md
plugins/autonomous-dev/agents/quality-validator.md
plugins/autonomous-dev/agents/alignment-validator.md
plugins/autonomous-dev/agents/commit-message-generator.md
plugins/autonomous-dev/agents/pr-description-generator.md
plugins/autonomous-dev/agents/project-progress-tracker.md
plugins/autonomous-dev/agents/alignment-analyzer.md
plugins/autonomous-dev/agents/project-bootstrapper.md
plugins/autonomous-dev/agents/project-status-analyzer.md
plugins/autonomous-dev/agents/sync-validator.md
```

## Common Issues

### Issue 1: Line Count Exceeds 200
**Solution**: Keep skill descriptions concise, one line each

### Issue 2: Skill Name Typo
**Solution**: Use exact names from mapping above (kebab-case)

### Issue 3: Section Placement Wrong
**Solution**: Place after Mission/Workflow, before final sections

### Issue 4: Format Inconsistent
**Solution**: Match researcher.md format exactly

## Quick Test Cycle

1. **Modify agent file** (add skill section)
2. **Run quick test**:
   ```bash
   pytest tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_all_target_agents_have_skill_sections -v
   ```
3. **Check result** - Does test pass for that agent?
4. **Repeat** for next agent
5. **Run full suite** when all 13 done

## Time Estimate

- **Per agent**: 2-3 minutes (copy pattern, customize 3-8 skills)
- **Total implementation**: 30-40 minutes for all 13 agents
- **Testing**: 5 minutes to run full suite
- **Total**: ~45 minutes to complete Issue #35

## Resources

- **Implementation plan**: See planner agent output for Issue #35
- **TDD summary**: `tests/AGENT_SKILLS_TDD_SUMMARY.md`
- **RED verification**: `tests/AGENT_SKILLS_TDD_RED_VERIFICATION.md`
- **Test running guide**: `tests/RUN_AGENT_SKILLS_TESTS.md`
- **Existing patterns**: `plugins/autonomous-dev/agents/researcher.md`

---

**TDD Phase**: RED ✅
**Next Step**: Implementation (add skill sections to 13 agents)
**Expected Duration**: 45 minutes
**Success Metric**: 38/38 tests passing

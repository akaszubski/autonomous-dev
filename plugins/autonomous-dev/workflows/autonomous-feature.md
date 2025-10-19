---
name: Autonomous Feature Development
description: Complete autonomous workflow for new feature implementation (research → plan → TDD → implement → review → security → docs)
---

# Autonomous Feature Development Workflow

Execute complete feature development with minimal human intervention using the 7-agent pipeline.

## When to Use

- User requests new feature: "Add [feature]", "Implement [feature]", "Build [feature]"
- Complex features requiring multiple components
- Features that need research before implementation

## Workflow Sequence

### Phase 1: Research & Planning (5-10 minutes)

**Agent 1: Researcher**
- **Purpose**: Find existing patterns and best practices
- **Input**: Feature requirements
- **Output**: Research findings in `docs/research/`
- **Actions**:
  1. Search codebase for similar patterns (Grep/Glob)
  2. Web research for best practices (WebSearch 3-5 queries)
  3. Fetch top sources (WebFetch 5+ articles)
  4. Create findings document with recommendations
  5. Stage research files in git

**Agent 2: Planner**
- **Purpose**: Create detailed implementation plan
- **Input**: Feature requirements + research findings
- **Output**: Architecture plan in session file
- **Actions**:
  1. Review research recommendations
  2. Analyze existing codebase patterns
  3. Design architecture (data models, APIs, file structure)
  4. Define testing strategy
  5. Identify security considerations
  6. Create step-by-step implementation plan

### Phase 2: Test-Driven Implementation (10-20 minutes)

**Agent 3: Test-Master (Write Failing Tests)**
- **Purpose**: Write comprehensive tests FIRST (TDD)
- **Input**: Implementation plan + requirements
- **Output**: Failing test files
- **Actions**:
  1. Write unit tests for all planned functionality
  2. Write integration tests for workflows
  3. Cover edge cases and error handling
  4. Run tests to confirm they fail (no implementation yet)
  5. Stage test files in git

**Agent 4: Implementer (Make Tests Pass)**
- **Purpose**: Implement code to make tests pass
- **Input**: Implementation plan + failing tests
- **Output**: Working implementation
- **Actions**:
  1. Review plan and failing tests
  2. Implement minimal code to pass tests
  3. Follow existing code patterns
  4. Add type hints and docstrings
  5. Handle errors gracefully
  6. Run tests iteratively until all pass

**Agent 5: Test-Master (Validate Implementation)**
- **Purpose**: Verify all tests pass with good coverage
- **Input**: Implementation
- **Output**: Test results + coverage report
- **Actions**:
  1. Run full test suite
  2. Measure code coverage (target: ≥80%)
  3. Verify no regressions
  4. Report results
  5. If failures: loop back to implementer with errors

### Phase 3: Quality Assurance (5-10 minutes)

**Agent 6: Security-Auditor**
- **Purpose**: Scan for security vulnerabilities
- **Input**: Implementation files
- **Output**: Security scan report
- **Actions**:
  1. Scan for hardcoded secrets
  2. Check for SQL/command injection risks
  3. Verify input validation
  4. Run bandit/safety scans
  5. Report findings
  6. If critical issues: loop back to implementer

**Agent 7: Reviewer**
- **Purpose**: Code quality gate
- **Input**: Complete context (plan + code + tests + security scan)
- **Output**: Approval or change requests
- **Actions**:
  1. Review code quality and patterns
  2. Verify test coverage (≥80%)
  3. Check documentation completeness
  4. Validate standards compliance
  5. Approve or request changes
  6. If blocking issues: loop back to implementer

**Agent 8: Doc-Master**
- **Purpose**: Update all documentation
- **Input**: Complete context
- **Output**: Updated docs
- **Actions**:
  1. Extract docstrings to API docs
  2. Update CHANGELOG.md
  3. Update README.md if needed
  4. Organize any new .md files
  5. Stage documentation changes

### Phase 4: Completion (1 minute)

**Orchestrator Reports**:
```
✅ Feature Implementation Complete

Feature: [Name]
Duration: [X] minutes
Agents Invoked: 8

Results:
- Research: ✅ Findings in docs/research/[date]_[topic]/
- Architecture: ✅ Planned by planner agent
- Tests: ✅ [N] tests written, all passing
- Coverage: ✅ [X]% (exceeds 80% threshold)
- Implementation: ✅ Code complete
- Security: ✅ No vulnerabilities found
- Review: ✅ Approved (no blocking issues)
- Documentation: ✅ CHANGELOG and API docs updated

Files Modified:
- [list files created/modified]

Ready to commit
Suggested commit message: "feat: [feature description]"
```

## Success Criteria

Feature is complete when:
- ✅ Research findings document best practices
- ✅ Architecture plan is comprehensive
- ✅ All tests passing (TDD workflow followed)
- ✅ Coverage ≥ 80% on changed files
- ✅ Security scan shows no critical vulnerabilities
- ✅ Code review approved (no blocking issues)
- ✅ Documentation updated (CHANGELOG + API docs)
- ✅ All changes staged in git

## Error Handling

### Test Failures After Implementation
→ Pass test failures to implementer
→ Request fixes
→ Re-run tests
→ Max 2 retries

### Security Issues Found
→ Pass security findings to implementer
→ Request fixes
→ Re-scan
→ Max 2 retries

### Coverage Below Threshold
→ Pass coverage report to test-master
→ Request additional tests
→ Re-run coverage
→ Max 2 retries

### Reviewer Blocks Approval
→ Pass review feedback to implementer
→ Request fixes
→ Re-review
→ Max 2 retries

### Critical Failure (Unable to Recover)
→ Document blocker
→ Escalate to user with diagnostic information
→ Provide current state and next steps

## Time Estimates

- **Simple feature**: 15-25 minutes
- **Medium feature**: 30-45 minutes
- **Complex feature**: 45-60 minutes

## Context Management

To prevent context bloat:
1. Agents log to session files (not inline context)
2. Session files stored in `docs/sessions/`
3. Agents read session files for file paths
4. User runs `/clear` after feature completes

**Without /clear**: Context grows 50K+ tokens after 3-4 features → system fails
**With /clear**: Context stays <8K tokens → works for 100+ features

## Optimization Notes

- **Token efficiency**: Only pass relevant context to each agent
- **Speed**: Move quickly between agents (they're separate contexts)
- **Reliability**: Validate at each step before proceeding
- **Autonomy**: Make decisions without user input when possible

---

**This workflow implements the complete TDD cycle with automated quality gates. Invoke via orchestrator agent or /auto-implement command.**

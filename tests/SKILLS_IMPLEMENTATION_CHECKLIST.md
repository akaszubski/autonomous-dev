# Skills Implementation Checklist (TDD Green Phase)

**Issues**: #63, #64
**Status**: Ready for Implementation
**Test Files**: 3 files, 82 tests, all FAILING

---

## Phase 1: Create agent-output-formats Skill

### 1.1 Create Skill Directory
```bash
mkdir -p plugins/autonomous-dev/skills/agent-output-formats/examples
```

### 1.2 Create SKILL.md File
**File**: `plugins/autonomous-dev/skills/agent-output-formats/SKILL.md`

**Required Sections**:
- [ ] YAML frontmatter with name, type, description, keywords, auto_activate
- [ ] Research Agent Output Format (Patterns Found, Best Practices, Security, Recommendations)
- [ ] Planning Agent Output Format (Feature Summary, Architecture, Components, Implementation Plan, Risks)
- [ ] Implementation Agent Output Format (Changes Made, Files Modified, Tests Updated, Next Steps)
- [ ] Review Agent Output Format (Findings, Code Quality, Security, Documentation, Verdict)

**Tests to Pass**:
- `test_skill_file_exists`
- `test_skill_has_valid_yaml_frontmatter`
- `test_skill_keywords_cover_output_terms`
- `test_skill_defines_research_agent_format`
- `test_skill_defines_planning_agent_format`
- `test_skill_defines_implementation_agent_format`
- `test_skill_defines_review_agent_format`

### 1.3 Create Example Files
**Location**: `plugins/autonomous-dev/skills/agent-output-formats/examples/`

Required Examples:
- [ ] `research-output-example.md` - Sample research agent output
- [ ] `planning-output-example.md` - Sample planning agent output
- [ ] `implementation-output-example.md` - Sample implementation agent output
- [ ] `review-output-example.md` - Sample review agent output

**Tests to Pass**:
- `test_examples_directory_exists`
- `test_research_example_exists`
- `test_planning_example_exists`
- `test_implementation_example_exists`
- `test_review_example_exists`

### 1.4 Update 15 Agent Prompts
**Location**: `plugins/autonomous-dev/agents/`

Agents to Update:
- [ ] researcher.md
- [ ] planner.md
- [ ] implementer.md
- [ ] reviewer.md
- [ ] security-auditor.md
- [ ] doc-master.md
- [ ] commit-message-generator.md
- [ ] pr-description-generator.md
- [ ] issue-creator.md
- [ ] brownfield-analyzer.md
- [ ] alignment-analyzer.md
- [ ] project-bootstrapper.md
- [ ] setup-wizard.md
- [ ] project-status-analyzer.md
- [ ] sync-validator.md

**Changes Required**:
1. Add to "Relevant Skills" section:
   ```markdown
   - **agent-output-formats**: Standardized output formats for autonomous development agents
   ```
2. Remove or condense "## Output Format" section (keep only if custom format needed)
3. Reference skill for standard output format

**Tests to Pass**:
- `test_agent_references_skill` (parametrized, 15 agents)
- `test_agent_output_format_section_removed` (parametrized, 15 agents)
- `test_total_agent_count_using_skill`

---

## Phase 2: Create error-handling-patterns Skill

### 2.1 Create Skill Directory
```bash
mkdir -p plugins/autonomous-dev/skills/error-handling-patterns/examples
```

### 2.2 Create SKILL.md File
**File**: `plugins/autonomous-dev/skills/error-handling-patterns/SKILL.md`

**Required Sections**:
- [ ] YAML frontmatter with name, type, description, keywords, auto_activate
- [ ] Exception Hierarchy (BaseError → DomainError → SpecificError)
- [ ] Error Message Format (context + expected + got + docs link)
- [ ] Security Audit Logging Integration
- [ ] Graceful Degradation Patterns
- [ ] Validation Error Patterns
- [ ] Path Validation Errors (CWE-22, CWE-59)
- [ ] Format Validation Errors
- [ ] Git Operation Errors
- [ ] Agent Invocation Errors

**Tests to Pass**:
- `test_skill_file_exists`
- `test_skill_has_valid_yaml_frontmatter`
- `test_skill_keywords_cover_error_terms`
- `test_skill_defines_exception_hierarchy`
- `test_skill_defines_error_message_format`
- `test_skill_defines_security_audit_logging`
- `test_skill_defines_graceful_degradation`
- `test_skill_defines_validation_patterns`
- `test_skill_documents_*` (path, format, git, agent validation errors)

### 2.3 Create Example Files
**Location**: `plugins/autonomous-dev/skills/error-handling-patterns/examples/`

Required Examples:
- [ ] `base-error-example.py` - Base error class with __init__ and __str__
- [ ] `domain-error-example.py` - Domain-specific errors (SecurityError, ValidationError, GitError)
- [ ] `error-message-example.py` - Formatted error message (context + expected + got + docs)
- [ ] `audit-logging-example.py` - Security audit logging integration

**Tests to Pass**:
- `test_examples_directory_exists`
- `test_base_error_example_exists`
- `test_domain_error_example_exists`
- `test_error_message_example_exists`
- `test_audit_logging_example_exists`

### 2.4 Update 22 Library Files
**Location**: `plugins/autonomous-dev/lib/`

Libraries to Update:
- [ ] security_utils.py
- [ ] project_md_updater.py
- [ ] version_detector.py
- [ ] orphan_file_cleaner.py
- [ ] sync_dispatcher.py
- [ ] validate_marketplace_version.py
- [ ] plugin_updater.py
- [ ] update_plugin.py
- [ ] hook_activator.py
- [ ] validate_documentation_parity.py
- [ ] auto_implement_git_integration.py
- [ ] github_issue_automation.py
- [ ] brownfield_retrofit.py
- [ ] codebase_analyzer.py
- [ ] alignment_assessor.py
- [ ] migration_planner.py
- [ ] retrofit_executor.py
- [ ] retrofit_verifier.py
- [ ] user_state_manager.py
- [ ] first_run_warning.py
- [ ] agent_invoker.py
- [ ] artifacts.py

**Changes Required**:
1. Add skill reference to module docstring:
   ```python
   """
   Module description here.

   Error Handling:
       See error-handling-patterns skill for standardized error patterns.
   """
   ```
2. Refactor custom exceptions to use domain-specific base error
3. Update error messages to follow format: context + expected + got + docs
4. Integrate security audit logging for security-relevant errors

**Tests to Pass**:
- `test_library_has_skill_reference` (parametrized, 22 libraries)
- `test_library_uses_exception_hierarchy` (parametrized, 22 libraries)
- `test_library_uses_formatted_error_messages` (parametrized, 22 libraries)
- `test_total_library_count_using_skill`

---

## Phase 3: Progressive Disclosure Validation

### 3.1 Verify Skill Metadata Size
**Requirement**: YAML frontmatter < 800 chars (~200 tokens)

**Tests to Pass**:
- `test_skill_metadata_small_for_context` (both skills)

### 3.2 Verify Skill Full Content Size
**Requirement**: Full content > 1000 chars (agent-output-formats), > 1500 chars (error-handling-patterns)

**Tests to Pass**:
- `test_skill_full_content_loads_on_demand` (both skills)

---

## Phase 4: Token Reduction Validation

### 4.1 Count Tokens Before/After
**Tool**: tiktoken or manual counting

**Measurements**:
- [ ] Measure tokens in 15 agent prompts (before)
- [ ] Measure tokens in 15 agent prompts (after)
- [ ] Calculate per-agent savings (target: ~200 tokens)
- [ ] Calculate total savings (target: ~3,000 tokens, ≥8%)

- [ ] Measure tokens in 22 library files (before)
- [ ] Measure tokens in 22 library files (after)
- [ ] Calculate per-library savings (target: ~300-400 tokens)
- [ ] Calculate total savings (target: ~7,000-8,000 tokens, ≥10%)

**Tests to Pass** (currently skipped, implement if time allows):
- `test_token_reduction_per_agent`
- `test_total_token_reduction` (agent-output-formats)
- `test_token_reduction_per_library`
- `test_total_token_reduction` (error-handling-patterns)

---

## Phase 5: Integration Testing

### 5.1 Run Integration Tests
**File**: `tests/integration/test_full_workflow_with_skills.py`

**Tests** (most are skipped, manual validation recommended):
- [ ] Test skill auto-activation during workflow
- [ ] Test agent outputs match skill specifications
- [ ] Test library errors follow skill patterns
- [ ] Test backward compatibility (existing workflow succeeds)

### 5.2 Run Regression Tests
**Requirement**: All existing tests must still pass

**Commands**:
```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
```

**Expected**: No test failures from skill integration

---

## Phase 6: Performance Validation

### 6.1 Measure Skill Load Time
**Requirement**: < 100ms per skill

**Tests to Pass**:
- `test_skill_load_time` (both skills)
- `test_yaml_parsing_performance` (both skills)

### 6.2 Measure Workflow Impact
**Requirement**: < 5% increase in workflow time

**Tests to Pass** (currently skipped):
- `test_skill_load_doesnt_slow_workflow`
- `test_progressive_disclosure_reduces_context_bloat`

---

## Phase 7: Documentation Updates

### 7.1 Update CLAUDE.md
**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md`

**Changes**:
- [ ] Update skill count: 19 → 21 active skills
- [ ] Add agent-output-formats to skill list
- [ ] Add error-handling-patterns to skill list
- [ ] Update Last Updated date

### 7.2 Update SKILLS-AGENTS-INTEGRATION.md
**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/docs/SKILLS-AGENTS-INTEGRATION.md`

**Changes**:
- [ ] Add agent-output-formats skill description
- [ ] Add error-handling-patterns skill description
- [ ] Update agent-skill mapping table

### 7.3 Update Performance Documentation
**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/docs/PERFORMANCE.md`

**Changes**:
- [ ] Document token savings from skill extraction
- [ ] Add to performance improvement history

---

## Verification Commands

### Run All Skill Tests
```bash
pytest tests/unit/skills/ -v --tb=short
pytest tests/integration/test_full_workflow_with_skills.py -v --tb=short
```

### Run Verification Script
```bash
python tests/verify_skills_tdd_red.py
```

### Run Full Test Suite (Regression)
```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
```

---

## Success Criteria

**All Tests Pass**:
- [ ] 82 test functions pass (unit + integration)
- [ ] 0 test failures
- [ ] 0 test errors

**Token Reduction Achieved**:
- [ ] agent-output-formats: ≥8% reduction (≥3,000 tokens)
- [ ] error-handling-patterns: ≥10% reduction (≥7,000 tokens)

**Quality Maintained**:
- [ ] All existing tests still pass (no regressions)
- [ ] Skill load time < 100ms per skill
- [ ] Workflow performance < 5% slower

**Documentation Updated**:
- [ ] CLAUDE.md updated with new skill count
- [ ] SKILLS-AGENTS-INTEGRATION.md updated
- [ ] Performance documentation updated

---

## Common Pitfalls

1. **YAML Frontmatter**: Ensure closing `---` is present
2. **Keywords**: Include all relevant keywords for auto-activation
3. **Agent References**: Add to "Relevant Skills" section, not just anywhere
4. **Error Message Format**: Include all 4 components (context + expected + got + docs)
5. **Exception Hierarchy**: Inherit from domain base error, not generic Exception
6. **Token Counting**: Use consistent method before/after measurements
7. **Progressive Disclosure**: Keep frontmatter small (< 800 chars)

---

## Estimated Time

- Phase 1 (agent-output-formats): 2-3 hours
- Phase 2 (error-handling-patterns): 3-4 hours
- Phase 3-6 (validation): 1-2 hours
- Phase 7 (documentation): 1 hour

**Total**: 7-10 hours

---

**Status**: Ready for implementer agent (TDD green phase)
**Next Command**: Hand off to implementer agent with this checklist

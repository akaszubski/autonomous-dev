# Issue #78 Implementer Guide - CLAUDE.md Optimization

**Purpose**: Step-by-step guide for implementing CLAUDE.md optimization using TDD approach

**Current State**: RED PHASE (all tests failing)
**Target State**: GREEN PHASE (all tests passing)

**Total Reduction Needed**: 6,818 characters (41,818 → <35,000)

---

## Quick Start

### 1. Verify Current State (RED Phase)

```bash
# Run verification script (no pytest required)
python3 tests/verify_issue78_red_phase.py

# Expected output:
# Expected failures (RED phase): 9
# ✅ SUCCESS: All tests are in RED phase (failing as expected)!
```

### 2. Understand Test Files

- **Unit Tests**: `tests/unit/test_claude_md_issue78_optimization.py` (33 tests)
- **Integration Tests**: `tests/integration/test_claude_md_optimization_workflow.py` (15 tests)
- **Verification**: `tests/verify_issue78_red_phase.py` (9 checks)

---

## Implementation Phases

### Phase 1: Extract Performance History (~4,800 chars saved)

**Goal**: Create docs/PERFORMANCE-HISTORY.md with Phase 4-8 optimization details

**Steps**:

1. **Create new file**: `docs/PERFORMANCE-HISTORY.md`

2. **Extract content from CLAUDE.md** (lines to extract):
   - Performance Baseline section (Phase 4-8 details)
   - Timing metrics (25-39 min → 22-36 min, etc.)
   - Cumulative improvement percentages
   - Model optimization (Haiku for researcher)
   - Prompt simplification details
   - Profiling infrastructure
   - Parallel validation checkpoint

3. **Add proper headers**:
   ```markdown
   # CLAUDE.md Optimization - Performance History

   Complete history of performance optimizations across Phases 4-8.

   **See also**: [CLAUDE.md](../CLAUDE.md) for current performance baseline
   ```

4. **Update CLAUDE.md**:
   - Replace detailed Phase 4-8 content with:
     ```markdown
     **Performance Baseline** (see [docs/PERFORMANCE-HISTORY.md](docs/PERFORMANCE-HISTORY.md) for complete history):
     - Current: 22-36 min per workflow (Phases 4-8 optimizations)
     - Cumulative improvement: 5-10 minutes saved (15-35% faster)
     ```

5. **Run tests**:
   ```bash
   # Test file exists
   python3 -c "from pathlib import Path; assert (Path('docs/PERFORMANCE-HISTORY.md').exists())"

   # Test link exists
   grep -q "PERFORMANCE-HISTORY.md" CLAUDE.md && echo "✅ Link added" || echo "❌ Link missing"

   # Test phases included
   grep -q "Phase 4" docs/PERFORMANCE-HISTORY.md && echo "✅ Phases found" || echo "❌ Phases missing"
   ```

**Success Criteria**:
- ✅ docs/PERFORMANCE-HISTORY.md exists
- ✅ Contains Phase 4-8 details
- ✅ Contains timing metrics
- ✅ CLAUDE.md links to it
- ✅ ~4,800 chars removed from CLAUDE.md

---

### Phase 2: Extract Batch Processing (~1,700 chars saved)

**Goal**: Create docs/BATCH-PROCESSING.md with /batch-implement workflow

**Steps**:

1. **Create new file**: `docs/BATCH-PROCESSING.md`

2. **Extract content from CLAUDE.md**:
   - Batch Feature Processing section
   - /batch-implement command syntax
   - Input options (file-based, GitHub issues)
   - State management (batch_state.json)
   - Resume operations (--resume flag)
   - Auto-clear threshold (150K tokens)
   - Use cases and performance notes

3. **Add proper headers**:
   ```markdown
   # Batch Feature Processing Guide

   Complete guide to processing multiple features sequentially with /batch-implement.

   **See also**: [CLAUDE.md](../CLAUDE.md) for quick reference
   ```

4. **Update CLAUDE.md**:
   - Replace detailed content with:
     ```markdown
     **Batch Processing** (see [docs/BATCH-PROCESSING.md](docs/BATCH-PROCESSING.md) for complete guide):
     - Command: `/batch-implement <features-file>` or `--issues <numbers>`
     - State management: Automatic context clearing at 150K tokens
     - Resume: `--resume <batch-id>` for crash recovery
     ```

5. **Run tests**:
   ```bash
   # Test file exists
   python3 -c "from pathlib import Path; assert (Path('docs/BATCH-PROCESSING.md').exists())"

   # Test link exists
   grep -q "BATCH-PROCESSING.md" CLAUDE.md && echo "✅ Link added" || echo "❌ Link missing"

   # Test workflow steps
   grep -q "/batch-implement" docs/BATCH-PROCESSING.md && echo "✅ Workflow found" || echo "❌ Workflow missing"
   ```

**Success Criteria**:
- ✅ docs/BATCH-PROCESSING.md exists
- ✅ Contains complete workflow
- ✅ Contains state management details
- ✅ CLAUDE.md links to it
- ✅ ~1,700 chars removed from CLAUDE.md

---

### Phase 3: Extract Agent Architecture (~2,300 chars saved)

**Goal**: Create docs/AGENTS.md with all 20 agent descriptions

**Steps**:

1. **Create new file**: `docs/AGENTS.md`

2. **Extract content from CLAUDE.md**:
   - Agents section (20 specialists)
   - Core workflow agents (9): researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master, advisor, quality-validator
   - Utility agents (11): alignment-validator, commit-message-generator, pr-description-generator, issue-creator, brownfield-analyzer, project-progress-tracker, alignment-analyzer, project-bootstrapper, setup-wizard, project-status-analyzer, sync-validator
   - Skill references for each agent
   - Note on orchestrator removal (v3.2.2)

3. **Add proper headers**:
   ```markdown
   # Agent Architecture

   Complete reference for all 20 autonomous development agents.

   **See also**: [CLAUDE.md](../CLAUDE.md) for agent workflow integration
   ```

4. **Update CLAUDE.md**:
   - Replace detailed agent list with:
     ```markdown
     **Agents** (see [docs/AGENTS.md](docs/AGENTS.md) for complete descriptions):
     - 20 specialists (9 core workflow + 11 utility)
     - Core: researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master, advisor, quality-validator
     - Utility: alignment-validator, commit-message-generator, pr-description-generator, issue-creator, brownfield-analyzer, project-progress-tracker, alignment-analyzer, project-bootstrapper, setup-wizard, project-status-analyzer, sync-validator
     ```

5. **Run tests**:
   ```bash
   # Test file exists
   python3 -c "from pathlib import Path; assert (Path('docs/AGENTS.md').exists())"

   # Test link exists
   grep -q "AGENTS.md" CLAUDE.md && echo "✅ Link added" || echo "❌ Link missing"

   # Test agent names
   grep -q "researcher" docs/AGENTS.md && grep -q "planner" docs/AGENTS.md && echo "✅ Agents found" || echo "❌ Agents missing"
   ```

**Success Criteria**:
- ✅ docs/AGENTS.md exists
- ✅ Contains all 20 agent descriptions
- ✅ Contains skill references
- ✅ CLAUDE.md links to it
- ✅ ~2,300 chars removed from CLAUDE.md

---

### Phase 4: Extract Hook Reference (~1,300 chars saved)

**Goal**: Create docs/HOOKS.md with all 42 hook listings

**Steps**:

1. **Create new file**: `docs/HOOKS.md`

2. **Extract content from CLAUDE.md**:
   - Hooks section (42 total)
   - Core hooks (11): auto_format, auto_test, security_scan, validate_project_alignment, validate_claude_alignment, enforce_file_organization, enforce_pipeline_complete, enforce_tdd, detect_feature_request, auto_git_workflow, auto_approve_tool
   - Optional/Extended hooks (20+)
   - Lifecycle hooks: UserPromptSubmit, SubagentStop

3. **Add proper headers**:
   ```markdown
   # Hook Reference

   Complete reference for all 42 automation hooks.

   **See also**: [CLAUDE.md](../CLAUDE.md) for hook activation guide
   ```

4. **Update CLAUDE.md**:
   - Replace detailed hook list with:
     ```markdown
     **Hooks** (see [docs/HOOKS.md](docs/HOOKS.md) for complete reference):
     - 42 total automation hooks (11 core + 20+ optional + lifecycle)
     - Core: auto_format, auto_test, security_scan, validate_project_alignment, validate_claude_alignment, enforce_file_organization, enforce_pipeline_complete, enforce_tdd, detect_feature_request, auto_git_workflow, auto_approve_tool
     - Lifecycle: UserPromptSubmit, SubagentStop
     ```

5. **Run tests**:
   ```bash
   # Test file exists
   python3 -c "from pathlib import Path; assert (Path('docs/HOOKS.md').exists())"

   # Test link exists
   grep -q "HOOKS.md" CLAUDE.md && echo "✅ Link added" || echo "❌ Link missing"

   # Test hook names
   grep -q "auto_format" docs/HOOKS.md && grep -q "auto_test" docs/HOOKS.md && echo "✅ Hooks found" || echo "❌ Hooks missing"
   ```

**Success Criteria**:
- ✅ docs/HOOKS.md exists
- ✅ Contains all 42 hook listings
- ✅ Contains lifecycle documentation
- ✅ CLAUDE.md links to it
- ✅ ~1,300 chars removed from CLAUDE.md

---

### Phase 5: Consolidate Skills Section (~800 chars saved)

**Goal**: Condense Skills section by referencing skill-integration skill

**Steps**:

1. **Update CLAUDE.md**:
   - Replace detailed skill descriptions with:
     ```markdown
     **Skills** (see [docs/SKILLS-AGENTS-INTEGRATION.md](docs/SKILLS-AGENTS-INTEGRATION.md) for complete mapping):
     - 27 active skills using progressive disclosure
     - Categories: Core Development (7), Workflow & Automation (7), Code & Quality (4), Validation & Analysis (6), Library Design (3)
     - Progressive disclosure: Metadata in context, full content loads on-demand
     - Agent integration: All 20 agents reference relevant skills
     ```

2. **Run tests**:
   ```bash
   # Test size reduction
   wc -c CLAUDE.md | awk '{if ($1 < 41000) print "✅ Size reduced"; else print "❌ Still too large"}'
   ```

**Success Criteria**:
- ✅ ~800 chars removed from CLAUDE.md
- ✅ Skills still documented (condensed)
- ✅ Link to SKILLS-AGENTS-INTEGRATION.md works

---

### Phase 6: Consolidate Git Automation Section (~800 chars saved)

**Goal**: Condense Git Automation section by referencing GIT-AUTOMATION.md

**Steps**:

1. **Update CLAUDE.md**:
   - Replace detailed git automation with:
     ```markdown
     **Git Automation** (see [docs/GIT-AUTOMATION.md](docs/GIT-AUTOMATION.md) for complete guide):
     - Enabled by default with first-run consent (opt-out via .env)
     - Environment variables: AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR
     - Triggers after /auto-implement completes (SubagentStop hook)
     - Security: CWE-22, CWE-59, audit logging
     ```

2. **Run tests**:
   ```bash
   # Test size reduction
   wc -c CLAUDE.md | awk '{if ($1 < 40000) print "✅ Size reduced"; else print "❌ Still too large"}'
   ```

**Success Criteria**:
- ✅ ~800 chars removed from CLAUDE.md
- ✅ Git automation still documented (condensed)
- ✅ Link to GIT-AUTOMATION.md works

---

### Phase 7: Consolidate Libraries Section (~800 chars saved)

**Goal**: Condense Libraries section by referencing LIBRARIES.md

**Steps**:

1. **Update CLAUDE.md**:
   - Replace detailed library list with:
     ```markdown
     **Libraries** (see [docs/LIBRARIES.md](docs/LIBRARIES.md) for complete API documentation):
     - 21 documented libraries (15 core/utility + 6 brownfield)
     - Core: security_utils, project_md_updater, version_detector, orphan_file_cleaner, sync_dispatcher, validate_marketplace_version, plugin_updater, update_plugin, hook_activator, validate_documentation_parity, auto_implement_git_integration, github_issue_automation, batch_state_manager, github_issue_fetcher, math_utils
     - Brownfield: brownfield_retrofit, codebase_analyzer, alignment_assessor, migration_planner, retrofit_executor, retrofit_verifier
     ```

2. **Run tests**:
   ```bash
   # Test size reduction
   wc -c CLAUDE.md | awk '{if ($1 < 35000) print "✅ Target achieved!"; else print "❌ Still above target"}'
   ```

**Success Criteria**:
- ✅ ~800 chars removed from CLAUDE.md
- ✅ Libraries still documented (condensed)
- ✅ Link to LIBRARIES.md works

---

## Final Verification

### Character Count Validation

```bash
# Check CLAUDE.md size
wc -c CLAUDE.md

# Expected: < 35,000 characters (ideally 30,000-32,000)
```

### All Tests Pass

```bash
# Run verification script
python3 tests/verify_issue78_red_phase.py

# Expected output:
# Expected failures (RED phase): 0
# Unexpected passes: 9
# ✅ SUCCESS: All tests passed (GREEN phase)!
```

### Alignment Validation

```bash
# Run alignment validator
python3 plugins/autonomous-dev/hooks/validate_claude_alignment.py

# Expected: Exit code 0 (no issues)
```

### Manual Checks

1. **Link resolution**: Click all docs/* links in CLAUDE.md - should resolve
2. **Search test**: Search for "Phase 4" - should find in PERFORMANCE-HISTORY.md
3. **Navigation test**: docs/AGENTS.md should link back to CLAUDE.md
4. **Content test**: All 20 agents still findable across CLAUDE.md + AGENTS.md
5. **Section test**: No section in CLAUDE.md > 100 lines

---

## Troubleshooting

### "Character count still too high"

**Problem**: CLAUDE.md still > 35,000 characters after all phases

**Solutions**:
1. Check for duplicate content (should be extracted, not duplicated)
2. Condense summaries further (brief overview + link)
3. Extract additional verbose sections
4. Remove outdated content

### "Tests failing after extraction"

**Problem**: Tests fail even though files created

**Solutions**:
1. Check file paths (must be docs/FILENAME.md)
2. Check content completeness (all required elements present?)
3. Check links (must reference FILENAME.md, not just filename)
4. Check bidirectional links (new docs should link back to CLAUDE.md)

### "Alignment validation failing"

**Problem**: validate_claude_alignment.py returns errors

**Solutions**:
1. Update agent count if changed
2. Update command count if changed
3. Update skills count if changed
4. Update version date in CLAUDE.md

### "Content missing after extraction"

**Problem**: Some information not findable after optimization

**Solutions**:
1. Check that content was extracted (not deleted)
2. Add link from CLAUDE.md to new doc
3. Add back-link from new doc to CLAUDE.md
4. Update search keywords in new doc

---

## Progress Tracking

Use this checklist to track implementation progress:

### Phase 1: Performance History
- [ ] Create docs/PERFORMANCE-HISTORY.md
- [ ] Extract Phase 4-8 details
- [ ] Add timing metrics
- [ ] Link from CLAUDE.md
- [ ] Test: `test_performance_history_md_exists` passes
- [ ] Test: `test_performance_history_contains_all_phases` passes

### Phase 2: Batch Processing
- [ ] Create docs/BATCH-PROCESSING.md
- [ ] Extract /batch-implement workflow
- [ ] Add state management details
- [ ] Link from CLAUDE.md
- [ ] Test: `test_batch_processing_md_exists` passes
- [ ] Test: `test_batch_processing_contains_workflow_steps` passes

### Phase 3: Agent Architecture
- [ ] Create docs/AGENTS.md
- [ ] Extract all 20 agent descriptions
- [ ] Add skill references
- [ ] Link from CLAUDE.md
- [ ] Test: `test_agents_md_exists` passes
- [ ] Test: `test_agents_md_contains_all_20_agents` passes

### Phase 4: Hook Reference
- [ ] Create docs/HOOKS.md
- [ ] Extract all 42 hook listings
- [ ] Add lifecycle documentation
- [ ] Link from CLAUDE.md
- [ ] Test: `test_hooks_md_exists` passes
- [ ] Test: `test_hooks_md_contains_core_hooks` passes

### Phase 5-7: Consolidation
- [ ] Condense Skills section
- [ ] Condense Git Automation section
- [ ] Condense Libraries section
- [ ] Test: `test_claude_md_under_35k_characters` passes

### Final Verification
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Verification script passes
- [ ] Alignment validation passes
- [ ] Manual checks complete

---

## Expected Timeline

- **Phase 1**: 20-30 minutes (extract performance history)
- **Phase 2**: 15-20 minutes (extract batch processing)
- **Phase 3**: 25-35 minutes (extract agent architecture)
- **Phase 4**: 15-20 minutes (extract hook reference)
- **Phase 5-7**: 20-30 minutes (consolidate sections)
- **Final Verification**: 10-15 minutes (run all tests)

**Total**: 105-150 minutes (1.75-2.5 hours)

---

## Success Metrics

### Hard Requirements (MUST PASS)
- ✅ CLAUDE.md < 35,000 characters
- ✅ All 4 new docs exist and properly formatted
- ✅ All cross-reference links work
- ✅ All 48 tests pass
- ✅ Alignment validation passes

### Soft Requirements (SHOULD PASS)
- ✅ CLAUDE.md < 32,000 characters (stretch goal)
- ✅ No section > 100 lines
- ✅ Average section size < 50 lines
- ✅ No duplicate content
- ✅ Bidirectional navigation works

---

## Questions?

- **Test failures**: See test error messages for specific issues
- **Implementation guidance**: See ISSUE78_TDD_RED_PHASE_SUMMARY.md
- **Requirements clarification**: See implementation plan from planner agent
- **Alignment issues**: Run `validate_claude_alignment.py` for specific drift

---

**Ready to implement? Start with Phase 1 and run tests after each phase!**

---

**Last Updated**: 2025-11-16
**Status**: RED PHASE (ready for implementation)
**Target**: GREEN PHASE (all 48 tests passing)

# Command Architecture Audit: GenAI Refactoring Analysis

**Date**: 2025-10-27
**Scope**: All 9 commands in autonomous-dev plugin
**Purpose**: Identify which commands need refactoring to leverage GenAI agents vs. Python-based automation

---

## Executive Summary

**Commands needing refactoring: 3**
- **HIGH**: `/align-project` (strategic validation - core command)
- **MEDIUM**: `/status` (goal tracking - developer tool)
- **LOW**: `/sync-dev` (file syncing - dev-only)

**Commands that are OK: 6**
- `/auto-implement` ✅ Already refactored to GenAI orchestration
- `/test` ✅ Simple bash invocation, no orchestration needed
- `/health-check` ✅ Acceptable (minor improvement optional)
- `/setup` ✅ Interactive wizard (human-driven, not automated)
- `/uninstall` ✅ Interactive removal (human-driven, not automated)
- `/align-claude` ✅ Already GenAI-native

---

## Detailed Analysis

### 1️⃣ `/auto-implement` ✅ ALREADY REFACTORED

**Status**: DONE
**Complexity**: HIGH
**Architecture**: GenAI-native orchestration (orchestrator agent)

**Current Implementation**:
```markdown
Autonomously implement a feature by invoking the orchestrator agent.

The orchestrator agent:
1. Validates alignment with PROJECT.md
2. Researches patterns
3. Plans implementation
4. Writes tests (TDD)
5. Implements code
6. Reviews quality
7. Security scans
8. Updates documentation
```

**Why This is Good**:
- ✅ Uses Task tool to invoke specialist agents
- ✅ Orchestrator coordinates complex workflow
- ✅ Claude's reasoning adapts to discoveries
- ✅ Handles edge cases intelligently
- ✅ No Python orchestration overhead

**No Changes Needed**: This command exemplifies the GenAI-native approach.

---

### 2️⃣ `/align-project` ⚠️ NEEDS REFACTORING

**Status**: NEEDS REFACTORING
**Priority**: HIGH (core command, validates strategic direction)
**Complexity**: MEDIUM

**Current Implementation**:
```markdown
Invoke the alignment-analyzer agent to analyze PROJECT.md against current project state.

Shows interactive menu for fixing issues:
- Option 1: View report only
- Option 2: Fix interactively (3-phase)
- Option 3: Dry run preview
- Option 4: Cancel
```

**Problem**:
- ❌ Documentation says "invoke alignment-analyzer agent"
- ❌ But description doesn't show actual GenAI reasoning
- ❌ Relies on Python analysis underneath
- ❌ Should be pure GenAI analysis with interactive fixing

**Proposed Refactoring**:

Replace Python-based validation with GenAI agent that:

1. **Analysis Phase** (GenAI)
   - Agent reads PROJECT.md
   - Analyzes current project state
   - Identifies alignment issues
   - Explains what's wrong and why it matters
   - Presents issues clearly

2. **Interactive Fixing** (GenAI + User)
   - Agent proposes fixes for each issue
   - User approves/modifies each phase
   - Agent explains impact of changes
   - Agent can ask clarifying questions

3. **Execution** (Bash + GenAI)
   - Agent creates directories
   - Agent moves files
   - Agent updates documentation
   - Shows what was actually changed

**Benefits**:
- ✅ Users can customize validation logic
- ✅ Agent can ask clarifying questions
- ✅ Better error messages
- ✅ Adapts to project variations
- ✅ Extensible (add new checks easily)

**Example Workflow**:
```
/align-project

🤖 Analyzing project structure...

Found 5 alignment issues:

1. ❌ CRITICAL: Missing test directories
   Expected: tests/unit/, tests/integration/
   Impact: Cannot run automated tests
   Fix: Create directories? [Y/n]

2. ⚠️  WARNING: README outdated
   Last update: 7 days ago (PROJECT.md: 2 days ago)
   Fix: Rebuild README.md? [Y/n]

3. ⚠️  WARNING: Docs scattered
   Files: GUIDE.md, ARCHITECTURE.md in root
   Expected: docs/ subdirectory
   Fix: Organize? [Y/n]

Applying fixes...
✅ Phase 1: Created test directories
✅ Phase 2: Moved docs to docs/ folder
✅ Phase 3: Rebuilt README.md
✅ All fixes applied and committed!
```

---

### 3️⃣ `/test` ✅ ACCEPTABLE

**Status**: OK AS-IS
**Complexity**: SIMPLE
**Architecture**: Direct bash invocation

**Current Implementation**:
```bash
pytest tests/ -v --tb=short
```

**Why This is Good**:
- ✅ Simple, direct bash command
- ✅ No orchestration needed
- ✅ Not coordinating multiple agents
- ✅ Users understand what's happening
- ❌ Could benefit from GenAI analysis of failures (future improvement)

**No Changes Needed**: Bash invocation is appropriate for test running.

---

### 4️⃣ `/status` ⚠️ NEEDS REFACTORING

**Status**: NEEDS REFACTORING
**Priority**: MEDIUM (nice-to-have improvement)
**Complexity**: LOW

**Current Implementation**:
```markdown
Invoke the project-progress-tracker agent to analyze project status.

Shows:
- Goal Progress: Completion % for each PROJECT.md goal
- Active Workflows: Currently running autonomous workflows
- Recent Activity: Last completed feature
- Next Priorities: Suggested features based on progress
```

**Problem**:
- ⚠️ Documentation mentions agent but lacks GenAI reasoning details
- ⚠️ Should let agent think about goal completion intelligently
- ⚠️ Should adapt based on what it discovers
- ⚠️ Could provide better strategic recommendations

**Proposed Refactoring**:

Let GenAI agent analyze project progress with reasoning:

1. **Analysis** (GenAI)
   - Parse PROJECT.md GOALS section
   - Check git history for completed features
   - Analyze session logs for what was accomplished
   - Calculate progress intelligently (not just counting)

2. **Strategic Thinking** (GenAI)
   - Which goals are neglected?
   - Which goals are closest to completion?
   - What's the logical next priority?
   - Are we aligned with strategic direction?

3. **Reporting** (GenAI)
   - Show visual progress bars
   - Highlight risks or misalignment
   - Suggest next actions
   - Flag incomplete work

**Example Output**:
```
📊 PROJECT.md Goal Progress

Enhanced UX:       [████████░░] 80% (4/5 features)
  ✅ Responsive design
  ✅ Accessibility improvements
  ✅ Dark mode toggle
  ✅ User preferences
  ⏳ Keyboard shortcuts (Next priority)

Security:          [██████████] 100% ✅ COMPLETE

Performance:       [██░░░░░░░░] 20% (1/5 features)
  ✅ Basic caching
  ⏳ Rate limiting (should do soon)
  ⏳ Query optimization
  ⏳ Compression
  ⏳ CDN integration

🎯 Strategic Analysis:
- UX nearly complete (1 feature away)
- Security done, should maintain
- Performance neglected (only 20%)
  → Consider: Implement rate limiting next
  → Reason: Enables 40% progress, improves stability
```

**Benefits**:
- ✅ Adaptive priority suggestions
- ✅ Intelligent progress calculation
- ✅ Identifies neglected goals
- ✅ Better strategic guidance
- ✅ Can flag quality issues in sessions

---

### 5️⃣ `/sync-dev` ⚠️ NEEDS REFACTORING

**Status**: NEEDS REFACTORING
**Priority**: LOW (developer-only, non-critical)
**Complexity**: LOW

**Current Implementation**:
```markdown
Invoke the project-bootstrapper agent to copy all files from
plugins/autonomous-dev/ to the installed Claude Code plugin directory.

Copies:
- agents/, skills/, commands/, hooks/
- scripts/, templates/, docs/
```

**Problem**:
- ⚠️ Says it invokes agent but just copies files
- ⚠️ No reasoning about what changed
- ⚠️ Dumb file copy, not intelligent syncing
- ⚠️ Doesn't validate integrity
- ⚠️ No change detection

**Proposed Refactoring**:

Let GenAI agent intelligently sync with change detection:

1. **Change Detection** (GenAI)
   - Compare local vs. installed files
   - Identify what's actually different
   - Skip unchanged files (faster)
   - Report summary of changes

2. **Intelligent Syncing** (GenAI)
   - Copy only changed files
   - Preserve user customizations
   - Warn about conflicts
   - Ask before overwriting

3. **Validation** (GenAI)
   - Verify copy completed successfully
   - Check file counts match
   - Validate critical files present
   - Report any failures

4. **User Guidance** (GenAI)
   - Suggest restart if needed
   - Show what was synced
   - Explain if changes won't take effect yet

**Example Workflow**:
```
/sync-dev

🔍 Detecting changes...

Changed files:
  ✏️  agents/orchestrator.md (updated)
  ✏️  commands/auto-implement.md (updated)
  ➕ commands/new-command.md (new)
  ➖ hooks/deprecated-hook.py (removed locally)

🔄 Syncing to installed location...

✅ agents/orchestrator.md (sync'd)
✅ commands/auto-implement.md (sync'd)
✅ commands/new-command.md (sync'd)
⚠️  hooks/deprecated-hook.py (exists in installed, removed locally)
   Keep in installed? [Y/n]: n
   ✅ Removed from installed

🔍 Verifying...
✅ 59 items synced
✅ File integrity validated

⚠️  RESTART REQUIRED
Claude Code must be restarted to pick up changes:
1. Save your work
2. Quit Claude Code (Cmd+Q)
3. Restart Claude Code
```

**Benefits**:
- ✅ Faster syncing (only copies changed files)
- ✅ Better change awareness
- ✅ Intelligent conflict handling
- ✅ Better user feedback
- ✅ Validates integrity

---

### 6️⃣ `/health-check` ✅ ACCEPTABLE (Minor Improvement Optional)

**Status**: OK AS-IS (optional future improvement)
**Complexity**: SIMPLE
**Architecture**: Python validation script

**Current Implementation**:
```bash
python lib/health_check.py

Validates:
- 8 agents loaded
- 14 skills loaded
- 8 hooks executable
- 7 commands present
```

**Why This is Good**:
- ✅ Quick, reliable validation
- ✅ Doesn't need GenAI reasoning
- ✅ Clear pass/fail results
- ✅ Good error reporting

**Optional Improvement** (can do later):

If desired, let GenAI agent think more deeply about health:

```
/health-check

🔍 Checking plugin components...

✅ Agents: 8/8 loaded
✅ Commands: 8/8 present
✅ Hooks: 8/8 executable

🧠 System Analysis:
- All components loaded correctly
- No missing dependencies
- Agents can invoke each other
- Hooks are executable

✅ OVERALL STATUS: HEALTHY

Can verify:
- Try invoking agents? [Y/n]
- Run test suite? [Y/n]
```

**Recommendation**: Leave as-is for now. Improve later if needed.

---

### 7️⃣ `/setup` ✅ OK AS-IS

**Status**: OK AS-IS
**Complexity**: MEDIUM
**Architecture**: Interactive wizard (human-driven)

**Current Implementation**:
```
Interactive wizard with 6 phases:
1. Hook setup (slash commands vs. auto hooks)
2. PROJECT.md template/generation
3. GitHub integration (optional)
4. Settings validation
5. Final setup confirmation
```

**Why This is Good**:
- ✅ Designed for human interaction
- ✅ Doesn't need GenAI reasoning
- ✅ User making intentional choices
- ✅ Clear workflow
- ❌ Could use GenAI to generate PROJECT.md better (already done!)

**No Changes Needed**: Interactive wizard is the right pattern for setup.

---

### 8️⃣ `/uninstall` ✅ OK AS-IS

**Status**: OK AS-IS
**Complexity**: SIMPLE
**Architecture**: Interactive removal (human-driven)

**Current Implementation**:
```
Interactive menu with 6 options:
1. Disable automatic hooks only
2. Remove project files only
3. Remove hooks and templates
4. Remove all project files
5. Uninstall plugin globally
6. Cancel
```

**Why This is Good**:
- ✅ Safe, reversible operations
- ✅ Clear options presented
- ✅ User makes final choice
- ✅ Doesn't need GenAI reasoning
- ✅ Good error prevention

**No Changes Needed**: Interactive removal is the right pattern for uninstall.

---

### 9️⃣ `/align-claude` ✅ ALREADY GENAI-NATIVE

**Status**: DONE
**Complexity**: MEDIUM
**Architecture**: Validation + guidance system

**Current Implementation**:
```markdown
Check and fix drift between documented standards (CLAUDE.md)
and actual implementation.

Validates:
1. Version consistency
2. Agent counts
3. Command counts
4. Documented features exist
5. Skills deprecation
6. Hook documentation
```

**Why This is Good**:
- ✅ Uses validation script for facts
- ✅ Clear issue reporting
- ✅ Provides fix guidance
- ✅ Pre-commit hook prevents drift
- ✅ Good example of validation pattern

**No Changes Needed**: This command validates well without full GenAI orchestration.

---

## Refactoring Priority Matrix

| Command | Priority | Complexity | Status | Why |
|---------|----------|-----------|--------|-----|
| `/align-project` | **HIGH** | Medium | 🔴 Needs refactoring | Core command, validates strategy |
| `/status` | **MEDIUM** | Low | 🟡 Needs refactoring | Goal tracking, nice-to-have |
| `/sync-dev` | **LOW** | Low | 🟡 Needs refactoring | Dev-only, non-critical |
| `/health-check` | **OPTIONAL** | Low | 🟢 OK, minor improvement | Could improve, not urgent |
| `/test` | **N/A** | Simple | 🟢 OK as-is | Bash invocation appropriate |
| `/setup` | **N/A** | Medium | 🟢 OK as-is | Interactive wizard appropriate |
| `/uninstall` | **N/A** | Simple | 🟢 OK as-is | Interactive removal appropriate |
| `/auto-implement` | **N/A** | High | ✅ Already refactored | Exemplar of GenAI approach |
| `/align-claude` | **N/A** | Medium | ✅ Already refactored | Good validation pattern |

---

## Implementation Roadmap

### Phase 1: High Priority (This Week)
```
1. Refactor /align-project to GenAI agent
   - Replace Python analysis with alignment-analyzer agent
   - Add interactive GenAI-powered fixing
   - Test with various project states

2. Expected outcome:
   - Better customization for projects
   - More adaptive fixing workflow
   - Better error handling
```

### Phase 2: Medium Priority (Next Week)
```
1. Refactor /status to GenAI agent
   - Let project-progress-tracker think about goals
   - Add strategic recommendations
   - Analyze session quality

2. Expected outcome:
   - Better goal tracking
   - Intelligent next-step suggestions
   - Quality awareness
```

### Phase 3: Low Priority (Optional)
```
1. Refactor /sync-dev to GenAI agent
   - Add change detection
   - Intelligent file syncing
   - Better conflict handling

2. Expected outcome:
   - Faster syncing
   - Better user feedback
   - Change awareness
```

### Phase 4: Future (Nice-to-Have)
```
1. Optional: Improve /health-check with GenAI analysis
   - Add component testing
   - Better diagnostic messages
   - Proactive issue detection

2. Note: Low priority, current implementation is solid
```

---

## Design Principles for GenAI Commands

When refactoring commands to GenAI, follow these principles:

### 1. **Prefer Agents Over Scripts**
```
❌ Old approach:
python scripts/analyze.py
→ Parse JSON
→ Format output

✅ New approach:
Agent reads PROJECT.md
Agent thinks about issues
Agent explains to user
```

### 2. **Embrace Reasoning**
```
❌ Old: "15 directories found"
✅ New: "You're missing test directories.
        This prevents automated testing.
        Should I create them?"
```

### 3. **Interactive When It Matters**
```
❌ Old: Auto-fix everything
✅ New: Ask user before each phase
        Explain impact of each change
        Let user customize
```

### 4. **Use Task Tool for Coordination**
```
✅ Good: Agent invokes sub-agents with Task tool
✅ Good: Wait for each agent to complete
✅ Good: Adapt based on results

❌ Bad: Python script coordinating agents
❌ Bad: Rigid sequence that can't adapt
```

### 5. **Keep Shell Commands Simple**
```
✅ Good: Agent decides what to run, then runs it
✅ Good: Agent explains what it's doing

❌ Bad: Complex bash orchestration
❌ Bad: Hidden operations users don't see
```

---

## Migration Checklist for Each Command

When refactoring a command, use this checklist:

### Planning
- [ ] Define what decisions the agent must make
- [ ] Define what information the agent needs
- [ ] Plan interaction points with user
- [ ] Identify edge cases

### Implementation
- [ ] Create/update agent markdown file
- [ ] Add Task tool invocations
- [ ] Implement user interaction (questions, menus)
- [ ] Add validation/error handling

### Testing
- [ ] Test happy path
- [ ] Test error cases
- [ ] Test user interactions
- [ ] Test edge cases

### Documentation
- [ ] Update command description
- [ ] Update usage examples
- [ ] Document what agent does
- [ ] Note any breaking changes

### Validation
- [ ] Verify agent can be invoked
- [ ] Verify output is helpful
- [ ] Verify user experience is good
- [ ] Get feedback before merging

---

## Conclusion

The autonomous-dev plugin is well-architected with:
- ✅ 2 exemplar GenAI commands (`/auto-implement`, `/align-claude`)
- ✅ 4 appropriately simple commands (`/test`, `/setup`, `/uninstall`, `/health-check`)
- 🔴 3 commands that need GenAI refactoring

**Recommended Action**: Start with `/align-project` (HIGH priority) to establish the pattern, then tackle `/status` and `/sync-dev`.

The refactoring will make commands:
- More adaptive and intelligent
- More customizable for different projects
- Better at explaining what they're doing
- More aligned with GenAI-native architecture

---

**Prepared by**: Claude Code Analysis
**Date**: 2025-10-27
**Next Review**: After `/align-project` refactoring

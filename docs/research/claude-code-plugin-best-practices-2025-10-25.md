# Claude Code Plugin Best Practices Research

**Date**: 2025-10-25
**Status**: Complete
**Sources**: Official Anthropic Claude Code repository, multiple production plugins

---

## Executive Summary

Research findings from Anthropic's official Claude Code repository reveal **critical differences** between production-grade plugins and autonomous-dev's current implementation. Key insights:

**CRITICAL FINDINGS**:
1. **Agent length**: Official agents are **34-51 lines** vs autonomous-dev's **337-864 lines** (10-25x longer!)
2. **Focus over orchestration**: Production plugins use **phase-based workflows** rather than complex agent coordination
3. **Hook simplicity**: Hooks are **84-281 lines** focused on single concerns
4. **No artifact protocol**: Official plugins don't use `.claude/artifacts/` pattern
5. **Minimal frontmatter**: Only 5-7 fields (name, description, tools, model, color)

**IMPACT**: Autonomous-dev is over-engineered by ~10x compared to production standards.

---

## Official Documentation

### Official Repository
- **Source**: https://github.com/anthropics/claude-code (official Anthropic repo)
- **Contents**: 6 production plugins, examples, hooks
- **Plugins analyzed**:
  - `feature-dev`: 7-phase feature development workflow
  - `pr-review-toolkit`: PR review with specialized agents
  - `code-review`: Automated code review
  - `security-guidance`: Security reminder hooks
  - `commit-commands`: Git workflow commands
  - `agent-sdk-dev`: Agent SDK development tools

### Key Takeaway
**The official repository IS the documentation** - no separate docs site found. Learn by reading actual production code.

---

## Pattern Analysis: Agents

### Official Agent Structure (Anthropic)

**Example: `code-reviewer` (46 lines)**
```markdown
---
name: code-reviewer
description: Reviews code for bugs, logic errors, security vulnerabilities
tools: Glob, Grep, LS, Read, NotebookRead, WebFetch, TodoWrite, WebSearch
model: sonnet
color: red
---

You are an expert code reviewer. Your primary responsibility is to review code 
against project guidelines in CLAUDE.md with high precision.

## Review Scope
By default, review unstaged changes from `git diff`.

## Core Review Responsibilities
- Project Guidelines Compliance
- Bug Detection
- Code Quality

## Confidence Scoring
Rate each issue 0-100. Only report issues ≥80 confidence.

## Output Guidance
- Clear description with confidence score
- File path and line number
- Specific fix suggestion
```

**Key characteristics**:
- **Length**: 34-51 lines total
- **Frontmatter**: 5-7 fields (name, description, tools, model, color)
- **Content**: Clear mission, concise guidelines, actionable output format
- **No scripting**: No bash scripts, no artifact protocols
- **Focus**: Single responsibility, well-defined scope

### Autonomous-Dev Agent Structure (Current)

**Example: `researcher` (864 lines)**
```markdown
---
name: researcher
description: Research patterns and best practices (v2.0 artifact protocol)
model: sonnet
tools: [WebSearch, WebFetch, Read, Bash, Grep, Glob]
---

# Researcher Agent (v2.0)

## v2.0 Artifact Protocol
**Input**: `.claude/artifacts/{workflow_id}/manifest.json`
**Output**: `.claude/artifacts/{workflow_id}/research.json`

## Your Mission
[600+ lines of detailed instructions...]
- Bootstrap knowledge base
- Check knowledge base
- Codebase search
- Web research
- Analysis & documentation
- Save to knowledge base
- Create artifact
- [Complex JSON protocols]
- [Python code examples]
- [Bash scripts]
- [Search utilities documentation]
```

**Comparison**:
| Metric | Official | Autonomous-Dev | Ratio |
|--------|----------|----------------|-------|
| Length | 34-51 lines | 337-864 lines | **10-25x** |
| Complexity | Single focus | Multi-phase workflows | **High** |
| Scripting | None | Bash + Python | **High** |
| Artifact protocol | None | Complex JSON | **Unnecessary** |

### What We're Doing Wrong

**Over-Engineering Symptoms**:
1. **Too long**: 864-line agents can't fit in context effectively
2. **Too complex**: Artifact protocols, JSON schemas, Python imports
3. **Too scripted**: Bash functions inside markdown agents
4. **Too much guidance**: Agents given implementation details instead of clear mission

**Official Pattern**:
- **Clear mission** (1-2 sentences)
- **Core responsibilities** (3-5 bullet points)
- **Output format** (clear, actionable)
- **Trust the model** (minimal prescriptive instructions)

**Our Pattern** (needs fixing):
- **Complex protocols** (artifact JSON, manifest schemas)
- **Detailed workflows** (step-by-step Python code)
- **Over-specification** (exactly how to do everything)
- **Don't trust the model** (prescribe implementation)

---

## Pattern Analysis: Hooks

### Official Hook Structure (Anthropic)

**Example: `security_reminder_hook.py` (281 lines)**
```python
#!/usr/bin/env python3
"""
Security Reminder Hook for Claude Code
Checks for security patterns in file edits and warns about vulnerabilities.
"""

import json
import sys

# Security patterns configuration
SECURITY_PATTERNS = [
    {
        "ruleName": "github_actions_workflow",
        "path_check": lambda path: ".github/workflows/" in path,
        "reminder": "You are editing a GitHub Actions workflow..."
    },
    # ... 10 more patterns
]

def main():
    """Main hook function."""
    # Check if enabled
    if os.environ.get("ENABLE_SECURITY_REMINDER", "1") == "0":
        sys.exit(0)
    
    # Read input
    input_data = json.loads(sys.stdin.read())
    
    # Check patterns
    rule_name, reminder = check_patterns(file_path, content)
    
    if rule_name:
        print(reminder, file=sys.stderr)
        sys.exit(2)  # Block tool execution
    
    sys.exit(0)  # Allow tool

if __name__ == "__main__":
    main()
```

**Key characteristics**:
- **Single concern**: Only security pattern matching
- **Simple flow**: Read input → Check patterns → Block or allow
- **Pattern-based**: Declarative pattern configuration
- **Exit codes**: 0 (allow), 2 (block and show to Claude)
- **Session state**: Tracks warnings per session to avoid spam
- **No dependencies**: Standalone script

**Example: `bash_command_validator_example.py` (84 lines)**
```python
#!/usr/bin/env python3
"""
Validates bash commands against rules before execution.
Example: Changes grep calls to using rg.
"""

import json
import re
import sys

_VALIDATION_RULES = [
    (r"^grep\b", "Use 'rg' (ripgrep) instead of 'grep'"),
    (r"^find\s+\S+\s+-name\b", "Use 'rg --files' instead of 'find'"),
]

def main():
    input_data = json.load(sys.stdin)
    command = input_data.get("tool_input", {}).get("command", "")
    
    issues = validate_command(command)
    if issues:
        for message in issues:
            print(f"• {message}", file=sys.stderr)
        sys.exit(2)  # Block and show to Claude
    
    sys.exit(0)  # Allow

if __name__ == "__main__":
    main()
```

### Hook Best Practices (From Official Code)

**Structure**:
1. **Shebang**: `#!/usr/bin/env python3`
2. **Docstring**: Clear purpose description
3. **Pattern configuration**: Declarative rules at top
4. **Main function**: Simple entry point
5. **Exit codes**:
   - `0`: Allow tool (success)
   - `1`: Show stderr to user only (warning)
   - `2`: Block tool and show stderr to Claude (enforcement)

**Exit Code Strategy** (CRITICAL):
```python
# Exit 0: Tool proceeds, no message
sys.exit(0)

# Exit 1: Tool proceeds, stderr shown to USER only
print("Warning: ...", file=sys.stderr)
sys.exit(1)

# Exit 2: Tool BLOCKED, stderr shown to CLAUDE
print("Error: ...", file=sys.stderr)
sys.exit(2)  # Claude sees message and can fix
```

**Session Management**:
```python
# Track per session to avoid spam
def get_state_file(session_id):
    return os.path.expanduser(f"~/.claude/state_{session_id}.json")

# Save shown warnings
shown_warnings.add(warning_key)
save_state(session_id, shown_warnings)
```

### What We're Doing Right

✅ **Python-based hooks**: Matches official pattern
✅ **PreToolUse hooks**: Correct hook type for validation
✅ **Exit codes**: Using 0/1/2 correctly

### What We Could Improve

**Current hooks are too complex**:
- `detect_feature_request.py`: Auto-invokes orchestrator (good idea, execution TBD)
- `validate_project_alignment.py`: Validates PROJECT.md (good, but might be over-engineered)
- `enforce_file_organization.py`: Auto-fixes file structure (complex, risky)

**Official hooks are simpler**:
- Single concern (security, command validation)
- Pattern matching (declarative rules)
- No auto-fixes (warn only, let Claude fix)

**Recommendation**: Simplify hooks to match official pattern - warn instead of auto-fix.

---

## Pattern Analysis: Commands

### Official Command Structure

**Example: `/feature-dev` command**
```markdown
---
description: Guided feature development with codebase understanding
argument-hint: Optional feature description
---

# Feature Development

Follow a systematic 7-phase approach:
1. Discovery
2. Codebase Exploration
3. Clarifying Questions
4. Architecture Design
5. Implementation
6. Quality Review
7. Summary

## Phase 1: Discovery
- Create todo list
- Clarify unclear features
- Summarize understanding

## Phase 2: Codebase Exploration
- Launch 2-3 code-explorer agents in parallel
- Each agent traces different aspect
- Read key files identified by agents
```

**Key characteristics**:
- **Workflow-based**: Command orchestrates phases
- **Agent coordination**: Launches multiple agents
- **Interactive**: Waits for user input between phases
- **TodoWrite tracking**: Uses todo tool throughout
- **Phase gates**: Explicit approval before proceeding

### Phase-Based Workflow Pattern (CRITICAL)

**Official `/feature-dev` workflow**:
```
Phase 1: Discovery (clarify requirements)
    ↓
Phase 2: Codebase Exploration (launch 2-3 code-explorer agents)
    ↓ (read files identified by agents)
Phase 3: Clarifying Questions (wait for user answers)
    ↓
Phase 4: Architecture Design (launch 2-3 code-architect agents)
    ↓ (user picks approach)
Phase 5: Implementation (wait for approval, then implement)
    ↓
Phase 6: Quality Review (launch 3 code-reviewer agents)
    ↓ (user decides: fix now, later, or proceed)
Phase 7: Summary (mark todos complete, summarize)
```

**Key insights**:
1. **Command orchestrates phases** (not an agent!)
2. **Agents are focused specialists** (explorer, architect, reviewer)
3. **User interaction between phases** (approval gates)
4. **Parallel agent launches** (2-3 agents per phase)
5. **TodoWrite tracks progress** (not session files)

**Comparison to autonomous-dev**:

| Pattern | Official | Autonomous-Dev |
|---------|----------|----------------|
| Orchestration | Command orchestrates | Orchestrator agent orchestrates |
| Agent count | 3 specialists | 8 specialists |
| Phases | 7 phases | 4 stages |
| User interaction | Between phases | After completion |
| Tracking | TodoWrite | Session files |
| Parallelization | 2-3 agents per phase | Sequential agents |

**Our approach is more automated** (good for "vibe coding") but **less interactive** (user can't guide).

---

## Pattern Analysis: Plugin Structure

### Official Plugin Directory Structure

```
plugins/feature-dev/
├── .claude-plugin/
│   └── (empty - no custom config)
├── agents/
│   ├── code-reviewer.md (46 lines)
│   ├── code-explorer.md (51 lines)
│   └── code-architect.md (34 lines)
├── commands/
│   └── feature-dev.md (413 lines)
└── README.md (413 lines)
```

**Total files**: ~5 files
**Total complexity**: Low (3 simple agents + 1 workflow command)

### Autonomous-Dev Plugin Structure (Current)

```
plugins/autonomous-dev/
├── agents/ (8 files, 4,497 lines total)
├── skills/ (7 files, complex)
├── commands/ (3 files)
├── hooks/ (6 files)
├── templates/ (multiple)
├── lib/ (search_utils.py)
├── docs/ (extensive)
└── tests/
```

**Total files**: 40+ files
**Total complexity**: High (8 agents + 7 skills + 6 hooks + templates + lib)

**Comparison**:
- **Official plugins**: 5 files, focused
- **Autonomous-dev**: 40+ files, comprehensive

**Trade-off**: We provide more automation, but at cost of complexity.

---

## Specific Recommendations for Autonomous-Dev

### 1. Simplify Agents (CRITICAL)

**Current**: 337-864 line agents with artifact protocols
**Target**: 50-100 line agents with clear mission

**Action plan**:
```markdown
# Before (researcher.md - 864 lines)
---
name: researcher
description: Research patterns and best practices (v2.0 artifact protocol)
model: sonnet
tools: [WebSearch, WebFetch, Read, Bash, Grep, Glob]
---

[600+ lines of artifact protocols, Python code, bash scripts...]

# After (researcher.md - ~80 lines)
---
name: researcher
description: Research best practices and existing patterns for feature implementation
model: sonnet
tools: [WebSearch, WebFetch, Read, Grep, Glob]
color: blue
---

You are a research specialist who finds best practices and existing patterns.

## Your Mission
Research the requested feature by:
1. Searching codebase for similar implementations
2. Finding official documentation and best practices
3. Identifying security considerations
4. Recommending libraries and approaches

## Research Process
- Use Grep/Glob to find existing patterns in codebase
- WebSearch for "[feature] best practices 2025"
- WebFetch official docs and recent guides
- Prioritize authoritative sources (official docs > GitHub > blogs)

## Output Format
Present findings as:
- **Codebase Patterns**: What already exists (file:line refs)
- **Best Practices**: Industry recommendations (with sources)
- **Security**: Critical considerations
- **Recommendations**: Preferred approach with rationale

Focus on actionable insights. Quality over quantity.
```

**Benefits**:
- **Fits in context**: 80 lines vs 864 lines
- **Clear mission**: No complex protocols
- **Trusts model**: Let Claude figure out implementation
- **Maintainable**: Easy to read and update

### 2. Remove Artifact Protocol

**Current**: `.claude/artifacts/{workflow_id}/manifest.json` protocol
**Official**: No artifact protocol found

**Rationale**:
- Official plugins don't use artifacts
- Adds complexity without clear benefit
- Session communication can be simpler (TodoWrite, direct output)

**Alternative** (matches official pattern):
```markdown
# Agent communication via TodoWrite
- Phase 1: Create todo list with all tasks
- Phase 2: Agents update todos as they complete
- Phase 3: Read todo list to see what's done

# No JSON artifacts needed!
```

### 3. Simplify Hooks

**Current**: Complex hooks with auto-fixes
**Official**: Simple pattern-matching hooks

**Action plan**:

```python
# Before: enforce_file_organization.py (complex, auto-fixes)
def enforce_structure():
    # ... 200 lines of auto-move logic
    move_files_to_correct_locations()
    update_imports()

# After: validate_file_organization.py (simple, warn only)
def validate_structure():
    issues = check_file_locations()
    if issues:
        print("File organization issues:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        print("\nRun: /align-project to fix", file=sys.stderr)
        sys.exit(2)  # Block commit, Claude can fix
```

**Benefits**:
- **Safer**: No auto-moves that break imports
- **Clearer**: User sees what's wrong
- **Consistent**: Matches official pattern

### 4. Reduce Agent Count

**Current**: 8 specialist agents
**Official**: 3 specialist agents per plugin

**Analysis**:
- `orchestrator`: Keep (coordinates pipeline)
- `researcher`: Keep (finds patterns)
- `planner`: Keep (designs architecture)
- `test-master`: Keep (TDD focus)
- `implementer`: Keep (writes code)
- `reviewer`: Keep (quality gate)
- `security-auditor`: **Merge into reviewer** (can review security)
- `doc-master`: **Merge into implementer** (can update docs)

**Rationale**: Official plugins use 3 focused agents. We can consolidate without losing capability.

**New structure** (6 agents):
1. **orchestrator**: Pipeline coordinator + PROJECT.md gatekeeper
2. **researcher**: Find patterns and best practices
3. **planner**: Design architecture
4. **test-master**: Write tests (TDD)
5. **implementer**: Write code + update docs
6. **reviewer**: Quality + security review

**Benefits**:
- **Simpler coordination**: Fewer agents to manage
- **Clearer responsibilities**: Less overlap
- **Faster execution**: Fewer handoffs

### 5. Phase-Based Workflow (Consider)

**Current**: Sequential agent pipeline
**Official**: Interactive phase-based workflow

**Current autonomous-dev workflow**:
```
orchestrator → researcher → planner → test-master → implementer → 
reviewer → security-auditor → doc-master → done
```

**Official feature-dev workflow**:
```
Phase 1: Discovery → user confirms
Phase 2: Launch explorers → read files
Phase 3: Ask questions → user answers
Phase 4: Launch architects → user picks
Phase 5: Implement → (after approval)
Phase 6: Launch reviewers → user decides
Phase 7: Summary
```

**Trade-offs**:

| Approach | Pros | Cons |
|----------|------|------|
| **Sequential (ours)** | Fully autonomous, no waiting | Less user control, can't course-correct |
| **Phase-based (official)** | User guides process, interactive | Requires user availability, slower |

**Recommendation**: **Keep sequential for "vibe coding"**, but add optional **interactive mode**:

```markdown
# Auto mode (current)
/auto-implement user authentication
→ Full pipeline, autonomous

# Interactive mode (new - optional)
/feature-dev user authentication
→ Phase-based, user approvals
```

**Benefits**: Best of both worlds - automation + control when needed.

### 6. Skills Consolidation

**Current**: 7 skills
**Official**: No separate skills (guidance in agent prompts)

**Analysis**:
- Official plugins put guidance directly in agent prompts
- Separate skills add indirection
- Skills are mostly reference material

**Action plan**:

**Keep as skills** (referenced by multiple agents):
- `python-standards`: Coding standards
- `testing-guide`: Test patterns
- `security-patterns`: Security rules

**Merge into agent prompts** (single-use):
- `documentation-guide` → into `implementer` agent
- `research-patterns` → into `researcher` agent
- `engineering-standards` → into `reviewer` agent
- `consistency-enforcement` → into `reviewer` agent

**Benefits**:
- **Simpler**: Fewer files to maintain
- **Clearer**: Guidance where it's used
- **Consistent**: Matches official pattern

### 7. Documentation Simplification

**Current**: Extensive documentation (10+ docs files)
**Official**: Single README.md (413 lines)

**Official README structure**:
```markdown
# Plugin Name

## Overview
Brief description

## Philosophy
Why this plugin exists

## Command: /command-name
Usage examples

## The N-Phase Workflow
Phase 1: ...
Phase 2: ...

## Agents
### agent-name
Purpose, focus areas, when triggered, output

## Usage Patterns
Common scenarios

## Best Practices
Tips and recommendations

## When to Use
Use cases and anti-patterns

## Troubleshooting
Common issues

## Author & Version
```

**Recommendation**: Consolidate to:
1. **README.md**: Overview, quickstart, usage (like official)
2. **STRICT-MODE.md**: Strict mode guide (unique to us)
3. **TROUBLESHOOTING.md**: Detailed troubleshooting

**Archive**:
- Move detailed guides to `docs/archive/`
- Keep only essential user-facing docs

---

## Best Practices to Codify in PROJECT.md

### Agent Design Principles

```markdown
## AGENT DESIGN PRINCIPLES (v2.5 - Official Pattern)

**Official Anthropic Standard** (from claude-code repository analysis):

### Length
- **Target**: 50-100 lines total
- **Maximum**: 150 lines
- **Current**: 337-864 lines (NEEDS FIX)
- **Rationale**: Agents must fit in context with room for codebase

### Frontmatter
**Required fields only**:
```yaml
---
name: agent-name
description: Clear one-sentence mission
model: sonnet  # or opus/haiku
tools: [Tool1, Tool2, Tool3]  # Only what's needed
color: blue  # Optional: red/green/blue/yellow
---
```

**No custom fields** (no artifact protocols, no complex schemas)

### Content Structure
1. **Clear Mission** (1-2 sentences)
2. **Core Responsibilities** (3-5 bullet points)
3. **Process** (simple workflow, not prescriptive)
4. **Output Format** (actionable structure)

### What to AVOID
- ❌ Bash scripts in markdown
- ❌ Python code examples
- ❌ Artifact protocols
- ❌ Complex JSON schemas
- ❌ Step-by-step implementation details
- ❌ Over-specification

### What to INCLUDE
- ✅ Clear mission statement
- ✅ Core responsibilities
- ✅ Expected output format
- ✅ Trust the model to figure out implementation

### Example (Official Pattern)

```markdown
---
name: researcher
description: Research best practices and existing patterns
model: sonnet
tools: [WebSearch, WebFetch, Read, Grep, Glob]
color: blue
---

You are a research specialist who finds best practices and patterns.

## Your Mission
Research the requested feature to inform implementation.

## Core Responsibilities
- Search codebase for similar implementations
- Find official documentation and current best practices
- Identify security considerations
- Recommend libraries and approaches

## Research Process
Use Grep/Glob to find existing patterns, WebSearch for official docs,
prioritize authoritative sources (official docs > GitHub > blogs).

## Output Format
- **Codebase Patterns**: Existing code with file:line references
- **Best Practices**: Industry standards with sources
- **Security**: Critical considerations
- **Recommendations**: Preferred approach with rationale

Quality over quantity. Trust the model.
```

**Total**: ~30 lines (vs 864 current)
```

### Hook Design Principles

```markdown
## HOOK DESIGN PRINCIPLES (v2.5 - Official Pattern)

**Official Anthropic Standard**:

### Structure
```python
#!/usr/bin/env python3
"""Clear purpose description."""

import json
import sys

# Pattern configuration (declarative)
PATTERNS = [...]

def main():
    """Main hook function."""
    # 1. Check if enabled
    # 2. Read stdin JSON
    # 3. Check patterns
    # 4. Exit 0/1/2

if __name__ == "__main__":
    main()
```

### Exit Codes (CRITICAL)
- **0**: Allow tool, no message
- **1**: Allow tool, show stderr to USER only (warning)
- **2**: BLOCK tool, show stderr to CLAUDE (enforcement)

### Single Concern
Each hook does ONE thing:
- Security pattern detection
- Command validation
- PROJECT.md alignment check

### No Auto-Fixes
- **Pattern**: Detect → Warn → Let Claude fix
- **Anti-pattern**: Detect → Auto-fix (risky)

### Session State
Track per-session to avoid spam:
```python
shown_warnings = load_state(session_id)
if warning_key not in shown_warnings:
    show_warning()
    shown_warnings.add(warning_key)
    save_state(session_id, shown_warnings)
```
```

### Plugin Architecture Principles

```markdown
## PLUGIN ARCHITECTURE (v2.5 - Official Pattern)

### File Structure (Minimal)
```
plugins/plugin-name/
├── agents/           # 3-6 focused agents (50-100 lines each)
├── commands/         # 1-3 workflow commands
├── hooks/           # 2-4 validation hooks (optional)
└── README.md        # Single comprehensive guide
```

**NO**:
- ❌ `skills/` directory (put guidance in agent prompts)
- ❌ `templates/` directory (unless essential)
- ❌ `lib/` directory (keep hooks self-contained)
- ❌ `.claude/artifacts/` protocol

### Agent Count
- **Official**: 3 specialist agents per plugin
- **Autonomous-dev**: 6-8 agents (acceptable for complex automation)
- **Maximum**: 10 agents (beyond this, split into multiple plugins)

### Coordination Pattern
**Option 1: Command Orchestration** (official pattern)
- Command defines phases
- Command launches agents
- User interaction between phases

**Option 2: Agent Orchestration** (our pattern)
- Orchestrator agent coordinates
- Sequential or parallel agent execution
- Fully autonomous (no user interaction)

**Recommendation**: Support both:
- `/auto-implement`: Agent orchestration (autonomous)
- `/feature-dev`: Command orchestration (interactive)

### Communication Pattern
**Official**: TodoWrite for tracking
**Autonomous-dev**: Session files for logging

**Keep**: Session files (good for audit trail)
**Add**: TodoWrite for interactive mode
```

---

## Code Examples: Before/After

### Agent Example: researcher.md

**Before (864 lines)**:
```markdown
---
name: researcher
description: Research patterns and best practices (v2.0 artifact protocol)
model: sonnet
tools: [WebSearch, WebFetch, Read, Bash, Grep, Glob]
---

# Researcher Agent (v2.0)

## v2.0 Artifact Protocol
**Input**: `.claude/artifacts/{workflow_id}/manifest.json`
**Output**: `.claude/artifacts/{workflow_id}/research.json`

### Read Manifest
[50 lines of Python code to read JSON]

## Your Mission
[600 lines of detailed workflows, Python examples, bash scripts...]

## Knowledge Base Strategy
[100 lines of bootstrap logic, Python code...]

## Search Utilities
[150 lines of library documentation...]
```

**After (80 lines)**:
```markdown
---
name: researcher
description: Research best practices and existing patterns for implementation
model: sonnet
tools: [WebSearch, WebFetch, Read, Grep, Glob]
color: blue
---

You are a research specialist focused on finding patterns and best practices.

## Your Mission
Research the requested feature to inform planning and implementation.

## Core Responsibilities

**Codebase Search**:
- Use Grep/Glob to find similar implementations
- Read existing code to understand patterns
- Identify conventions and architecture

**Web Research**:
- Search for "[feature] best practices 2025"
- WebFetch official documentation
- Prioritize authoritative sources (docs > GitHub > blogs)

**Analysis**:
- Identify recommended approaches
- Document security considerations
- List alternatives with trade-offs

## Output Format

Present findings clearly:

**Codebase Patterns**:
- Pattern: [description]
- Location: [file:line]
- Relevance: [why useful]

**Best Practices** (top 3-5):
- Practice: [recommendation]
- Source: [URL]
- Rationale: [why important]

**Security Considerations** (critical only):
- [Security concern with mitigation]

**Recommendations**:
- Preferred approach with rationale
- Key libraries to use
- Alternatives considered

Focus on actionable insights. Quality over quantity.
```

**Reduction**: 864 → 80 lines (91% reduction!)

### Hook Example: validate_project_alignment.py

**Before (hypothetical complex version)**:
```python
#!/usr/bin/env python3
"""Validate PROJECT.md alignment and auto-fix issues."""

# ... 200+ lines of auto-fix logic
# ... Complex parsing
# ... Auto-update PROJECT.md
# ... Git operations
```

**After (official pattern)**:
```python
#!/usr/bin/env python3
"""Validate PROJECT.md alignment before commits."""

import json
import sys
from pathlib import Path

def check_project_alignment():
    """Check if PROJECT.md exists and has required sections."""
    project_md = Path("PROJECT.md")
    
    if not project_md.exists():
        return "PROJECT.md not found"
    
    content = project_md.read_text()
    
    required_sections = ["## GOALS", "## SCOPE", "## CONSTRAINTS"]
    missing = [s for s in required_sections if s not in content]
    
    if missing:
        return f"PROJECT.md missing sections: {', '.join(missing)}"
    
    # Check SCOPE is defined
    if "IN Scope" not in content:
        return "PROJECT.md SCOPE section not defined"
    
    return None

def main():
    """Main hook function."""
    # Only run on PreCommit
    input_data = json.load(sys.stdin)
    
    error = check_project_alignment()
    
    if error:
        print(f"❌ PROJECT.md Alignment Check Failed", file=sys.stderr)
        print(f"\n{error}", file=sys.stderr)
        print(f"\nUpdate PROJECT.md or run: /align-project", file=sys.stderr)
        sys.exit(2)  # Block commit, Claude sees message
    
    sys.exit(0)  # Allow commit

if __name__ == "__main__":
    main()
```

**Total**: ~50 lines (simple, focused, no auto-fixes)

---

## Summary: What to Change

### Priority 1: Agent Simplification (CRITICAL)
**Impact**: High
**Effort**: Medium
**Timeline**: 1-2 days

**Actions**:
1. Reduce all agents to 50-100 lines
2. Remove artifact protocol
3. Remove bash scripts from agents
4. Trust the model more, prescribe less

**Files to update**:
- `agents/researcher.md`: 864 → 80 lines
- `agents/planner.md`: 711 → 100 lines
- `agents/orchestrator.md`: 598 → 120 lines
- `agents/test-master.md`: 337 → 70 lines
- `agents/implementer.md`: 444 → 90 lines
- `agents/reviewer.md`: 424 → 80 lines
- `agents/security-auditor.md`: 475 → 60 lines (or merge into reviewer)
- `agents/doc-master.md`: 644 → 70 lines (or merge into implementer)

### Priority 2: Hook Simplification
**Impact**: Medium
**Effort**: Low
**Timeline**: 1 day

**Actions**:
1. Simplify hooks to pattern-matching only
2. Remove auto-fix logic (warn instead)
3. Use exit code 2 for enforcement

**Files to update**:
- `hooks/enforce_file_organization.py`: Rename to `validate_file_organization.py`, remove auto-fixes
- `hooks/validate_project_alignment.py`: Simplify to ~50 lines
- `hooks/detect_feature_request.py`: Keep (auto-orchestration is good)

### Priority 3: Skills Consolidation
**Impact**: Medium
**Effort**: Low
**Timeline**: 0.5 day

**Actions**:
1. Keep 3 core skills (python-standards, testing-guide, security-patterns)
2. Merge others into agent prompts
3. Update agent frontmatter to reference skills

### Priority 4: Documentation Cleanup
**Impact**: Low
**Effort**: Low
**Timeline**: 0.5 day

**Actions**:
1. Consolidate to README.md + STRICT-MODE.md + TROUBLESHOOTING.md
2. Archive detailed guides
3. Follow official README structure

### Priority 5: Optional Interactive Mode
**Impact**: Medium
**Effort**: Medium
**Timeline**: 2-3 days (future)

**Actions**:
1. Create `/feature-dev` command (interactive, phase-based)
2. Keep `/auto-implement` command (autonomous, sequential)
3. Use TodoWrite for interactive mode

---

## References

**Official Sources**:
- [Anthropic Claude Code Repository](https://github.com/anthropics/claude-code)
- [feature-dev Plugin](https://github.com/anthropics/claude-code/tree/main/plugins/feature-dev)
- [pr-review-toolkit Plugin](https://github.com/anthropics/claude-code/tree/main/plugins/pr-review-toolkit)
- [security-guidance Plugin](https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance)
- [Hook Examples](https://github.com/anthropics/claude-code/tree/main/examples/hooks)

**Key Metrics**:
- **Official agent length**: 34-51 lines
- **Our agent length**: 337-864 lines (10-25x longer!)
- **Official plugin files**: ~5 files
- **Our plugin files**: 40+ files (8x more!)

**Verdict**: Autonomous-dev is over-engineered by approximately **10x** compared to official standards.

**Recommendation**: Simplify aggressively. Trust the model. Follow official patterns.

---

**End of Research Report**

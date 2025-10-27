# Claude Code Plugin Best Practices & Standards

**Last Updated**: 2025-10-27
**Source**: Official Anthropic Claude Code repository analysis (2025-10-25) + Community standards
**Purpose**: Distilled knowledge from production-grade plugins to guide autonomous-dev development

---

## Executive Summary

Research from Anthropic's official Claude Code repository reveals critical differences between production-grade plugins and over-engineered implementations:

| Metric | Official Standard | Anti-pattern | Ratio |
|--------|-------------------|--------------|-------|
| **Agent length** | 34-51 lines | 337-864 lines | 10-25x |
| **Complexity** | Single focus | Multi-phase workflows | High |
| **Scripting in markdown** | None | Bash + Python | High |
| **Artifact protocols** | None | Complex JSON | Unnecessary |

**Key Insight**: Trust the model. Claude is smart enough without over-prescriptive instructions.

---

## Agent Design Standards

### Official Pattern (Anthropic)

**Structure** (40-50 lines):
```markdown
---
name: agent-name
description: Clear one-sentence mission
model: sonnet  # or opus/haiku
tools: [Tool1, Tool2, Tool3]  # Only essential
color: blue  # Optional visual distinction
---

You are a [specialist] that [does thing].

## Your Mission
[1-2 sentence clear purpose]

## Core Responsibilities
- [Responsibility 1]
- [Responsibility 2]
- [Responsibility 3]

## Process
[General workflow, NOT step-by-step prescription]

## Output Format
[Structure of results]
```

**Key Requirements**:
- ✅ **Clear mission** (1-2 sentences, not paragraphs)
- ✅ **Core responsibilities** (3-5 bullets, not 20)
- ✅ **Minimal guidance** (trust the model)
- ✅ **No scripting** (no bash, no Python code examples)
- ✅ **Only essential tools** (Principle of Least Privilege)
- ✅ **Single responsibility** (agent does ONE thing well)

**Length Targets**:
- **Ideal**: 40-50 lines
- **Acceptable**: 50-100 lines
- **Maximum**: 150 lines (enforced strictly)
- **Red flag**: > 200 lines = over-engineering

### Anti-Patterns to Avoid

❌ **Bash scripts embedded in markdown**
```markdown
---
# DON'T DO THIS:
name: my-agent

## Your Process
1. Run this bash script:
\`\`\`bash
#!/bin/bash
for file in $(find . -name "*.py"); do
  grep -l "pattern" "$file"
done
\`\`\`
---
```
**Why bad**: Markdown is for guidance, not code hosting. Scripts should be in `/scripts/` or plugins.

❌ **Python code examples in agent prompts**
```markdown
---
name: code-generator

## How to generate
\`\`\`python
def process_data(data):
    return [x for x in data if x > 10]
\`\`\`
---
```
**Why bad**: Claude doesn't need code examples to write code. It creates confusion about whether the example is what to generate or how to generate.

❌ **Complex artifact protocols**
```markdown
---
name: researcher
description: Research patterns (v2.0 artifact protocol)

## Workflow
Input: `.claude/artifacts/{workflow_id}/manifest.json`
Output: `.claude/artifacts/{workflow_id}/research.json`

## Artifact Schema
\`\`\`json
{
  "workflow_id": "string",
  "status": "in_progress | complete",
  "phases": {
    "phase1": { ... },
    "phase2": { ... }
  }
}
\`\`\`
---
```
**Why bad**: Adds complexity, unnecessary indirection. Claude works fine with direct tool calls.

❌ **Over-specification of implementation**
```markdown
---
name: implementer

## Step-by-Step Process
1. Read the test file using Read tool
2. Extract test cases using regex
3. For each test case:
   a. Parse test parameters
   b. Validate parameters
   c. Generate implementation code
   d. Verify against test
4. Create artifact with results
---
```
**Why bad**: Claude can figure this out. Over-prescription limits flexibility and wastes context.

### What We Do Right (Keep)

✅ **Model assignments**: Using opus/sonnet/haiku strategically
✅ **Clear missions**: Each agent has a well-defined purpose
✅ **Tool restrictions**: Agents only get necessary tools
✅ **Focused scope**: Each agent does one job well

---

## Hook Design Standards

### Official Pattern (Anthropic)

**Structure** (84-281 lines):
```python
#!/usr/bin/env python3
"""Clear purpose description."""

import json
import sys

# Configuration at top (declarative, not imperative)
PATTERNS = [
    (r"^grep\b", "Use 'rg' instead of 'grep'"),
    (r"^find\s+", "Use 'rg --files' instead"),
]

def main():
    """Main hook function."""
    # 1. Check if enabled
    # 2. Read stdin JSON
    # 3. Check patterns/rules
    # 4. Exit with appropriate code

if __name__ == "__main__":
    main()
```

**Exit Code Strategy** (CRITICAL):
```python
# Exit 0: Tool proceeds, no message shown
sys.exit(0)

# Exit 1: Tool proceeds, stderr shown to USER only (warning)
print("⚠️  Warning: Consider using rg instead", file=sys.stderr)
sys.exit(1)

# Exit 2: Tool BLOCKED, stderr shown to CLAUDE (enforcement)
print("❌ PROJECT.md validation failed", file=sys.stderr)
sys.exit(2)  # Claude receives message and can fix
```

**Key Principles**:
- ✅ **Single concern** - Hook does ONE thing
- ✅ **Declarative rules** - Pattern list at top, easy to maintain
- ✅ **Fast execution** - Must complete in < 1 second
- ✅ **Session state** - Track shown warnings per session (avoid spam)
- ✅ **Clear exit codes** - User/Claude knows what went wrong

### Anti-Patterns to Avoid

❌ **Auto-fixing without visibility**
```python
# DON'T DO THIS:
def main():
    if not is_formatted(file):
        auto_format(file)  # Claude doesn't see the change!
        sys.exit(0)
```
**Why bad**: Claude should see and approve changes. Auto-fixing hides problems.

❌ **Complex multi-stage logic**
```python
# DON'T DO THIS:
def validate():
    if check_type_1():
        if check_type_2():
            for each_subcheck():
                if special_case():
                    return error_code
```
**Why bad**: Keep simple. Nested logic is hard to debug and maintain.

❌ **Heavy I/O operations**
```python
# DON'T DO THIS:
def check_files():
    for file in glob('**/*.py'):
        content = read(file)
        parse_ast(content)
        check_imports(content)
```
**Why bad**: Slow. Hooks run on every tool use. Keep it fast (< 1s).

❌ **Silent failures**
```python
# DON'T DO THIS:
try:
    validate()
except Exception:
    sys.exit(0)  # Silently ignore errors
```
**Why bad**: Claude won't know something failed. Always exit with appropriate code.

### What We Do Right (Keep)

✅ **Python-based hooks**: Matches official pattern
✅ **PreToolUse timing**: Correct hook type for validation
✅ **Exit codes**: Using 0/1/2 correctly
✅ **Declarative patterns**: Configuration lists at top

---

## Command Design Standards

### Official Pattern (Anthropic)

**Structure** - Phase-based workflow with user checkpoints:
```markdown
---
description: Guided feature development workflow
argument-hint: Optional feature description
---

# Feature Development

Follow a systematic approach with user approval gates:

## Phase 1: Discovery
- Create todo list with TodoWrite
- Clarify requirements
- Summarize understanding
- **User checkpoint**: Approve before proceeding

## Phase 2: Exploration
- Launch explorer agents in parallel
- Each agent traces different aspect
- **User checkpoint**: Review findings

## Phase 3: Implementation
- Launch implementer agent
- Follow TDD pattern
- **User checkpoint**: Approve design

[Continue pattern...]
```

**Key Principles**:
- ✅ **Phase-based workflow** - Clear structure
- ✅ **User gates** - Wait for approval between phases
- ✅ **TodoWrite tracking** - Progress visibility
- ✅ **Parallel agents** - Multiple perspectives
- ✅ **Clear outputs** - Each phase produces results

---

## Context Management Standards

### Token Budget (CRITICAL for Scaling)

**Per-feature allocation**:
- **Agent prompts**: 500-1,000 tokens (50-100 lines)
- **Codebase exploration**: 2,000-3,000 tokens
- **Working memory**: 2,000-3,000 tokens
- **Buffer**: 1,000-2,000 tokens
- **TOTAL TARGET**: < 8,000 tokens per feature

**Implications**:
- ✅ Keep agents short (50-100 lines)
- ✅ No artifact protocols (unnecessary complexity)
- ✅ Session logging (reference paths, not content)
- ✅ Clear after features (use `/clear` between features)
- ✅ Minimal prompts (trust model > detailed instructions)

### Session Management Pattern

```python
# Track per-session state to avoid spam
def get_state_file(session_id: str) -> Path:
    return Path.home() / ".claude" / f"state_{session_id}.json"

def load_shown_warnings(session_id: str) -> set:
    state_file = get_state_file(session_id)
    if not state_file.exists():
        return set()
    return set(json.loads(state_file.read_text()))

def save_shown_warnings(session_id: str, warnings: set):
    state_file = get_state_file(session_id)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(list(warnings)))
```

---

## Philosophy: Trust the Model

Five core principles from official Anthropic patterns:

### 1. Trust the Model
Claude Sonnet/Opus are extremely capable. Don't over-prescribe implementation.

**Example - BAD**:
```markdown
## Implementation Steps
1. Read file using Read tool
2. Parse JSON using json.loads()
3. For each key in object:
   a. Check if value is string
   b. If string, append to results
   c. Return results list
```

**Example - GOOD**:
```markdown
## Your Mission
Extract string values from JSON configuration file.

## Output Format
List of string values: ["value1", "value2", ...]
```

### 2. Simple > Complex
50-line agent beats 800-line agent. Both work, simple scales better.

**Example - BAD**: Artifact protocol with manifest.json, phase tracking, JSON schemas
**Example - GOOD**: Direct tool calls, clear mission, trust the model

### 3. Warn > Auto-fix
Let Claude see and fix issues. Auto-fixing hides problems and prevents learning.

**Exit code strategy**:
- `0`: Silent success (all good)
- `1`: Warn user (show info)
- `2`: Block + alert Claude (needs fixing)

Never silently auto-fix.

### 4. Minimal > Complete
Focused guidance beats exhaustive documentation.

**Example - BAD**: 30-page agent design guide with implementation details
**Example - GOOD**: 2-3 page design principles with examples

### 5. Parallel > Sequential
Launch multiple agents for diverse perspectives instead of sequential pipelines.

**Example - BAD**:
```
agent1 → agent2 → agent3 → agent4 (serial, slow)
```

**Example - GOOD**:
```
launch agent1, agent2, agent3 in parallel
wait for results
proceed when all complete (fast, diverse)
```

---

## Design Anti-Patterns to Avoid

### Over-Engineering Indicators

🚩 **Agent > 150 lines** - Over-complex, won't fit in context effectively
🚩 **Hook > 300 lines** - Too many concerns, should be split
🚩 **Command > 80 lines** - Over-specified workflow, trust the model
🚩 **JSON artifact protocols** - Unnecessary indirection
🚩 **Bash scripts in markdown** - Scripts belong in `/scripts/`
🚩 **Python code examples in agents** - Confuses prompt intent
🚩 **Step-by-step instructions** - Limits flexibility
🚩 **Auto-fixing without visibility** - Claude doesn't see changes
🚩 **Silent failures** - User/Claude won't know something broke

### Complexity Checklist

Before shipping, verify:
- [ ] Agent is 50-150 lines (max)
- [ ] Hook is < 300 lines
- [ ] Command has clear phases with user gates
- [ ] No scripts embedded in markdown
- [ ] No auto-fixing (warn only)
- [ ] No artifact protocols
- [ ] No step-by-step prescriptions
- [ ] Exit codes are 0/1/2 appropriate
- [ ] Runs in < 1 second (hooks)

---

## References & Sources

### Official Anthropic Resources
- **Claude Code Repository**: https://github.com/anthropics/claude-code
- **Production Plugins Analyzed**:
  - `feature-dev` - 7-phase feature development
  - `pr-review-toolkit` - PR review with agents
  - `code-review` - Automated code review
  - `security-guidance` - Security reminder hooks
  - `commit-commands` - Git workflow
  - `agent-sdk-dev` - Agent SDK tools

### Key Findings Summary

| Pattern | Official | Autonomous-Dev | Recommendation |
|---------|----------|----------------|-----------------|
| Agent length | 34-51 lines | 337-864 lines | Simplify to 100 lines max |
| Artifact protocol | None | Complex JSON | Remove (unnecessary) |
| Bash in markdown | None | Multiple | Move to `/scripts/` |
| Focus | Single concern | Multi-phase | Split into separate agents |
| Trust model | High | Over-prescriptive | Reduce instructions |

---

## Continuous Improvement

This document should be updated when:
- New official Anthropic patterns are released
- New best practices are discovered through production use
- Anti-patterns are identified in code review
- Design decisions are made (should be documented here)

**Last Reviewed**: 2025-10-27
**Next Review**: 2025-12-27 (quarterly)

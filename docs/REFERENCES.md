# References & External Resources

**Last Updated**: 2025-10-27
**Purpose**: Curated collection of external resources, patterns, and best practices that informed autonomous-dev

---

## Official Anthropic Resources

### Claude Code Official Repository
- **URL**: https://github.com/anthropics/claude-code
- **Contains**: Official production plugins, examples, design patterns
- **Key Learnings**:
  - Agent design: Keep < 50 lines (official), we target 50-100 lines
  - Hook design: Simple pattern matching, < 300 lines
  - No artifact protocols: Direct tool calls are cleaner
  - Phase-based commands: Sequential workflow with user gates

### Official Plugins Analyzed (2025-10-25)

#### 1. feature-dev
- **Purpose**: 7-phase guided feature development
- **Pattern**: Phase-based workflow with user approval gates
- **Key Files**: Phase tracking, todo management, checkpoint validation
- **Lesson**: Users guide process, not AI

#### 2. pr-review-toolkit
- **Purpose**: Automated PR review with specialized agents
- **Pattern**: Multiple agents for different review aspects
- **Key Files**: pr-reviewer, summary-agent, comment-generator
- **Lesson**: Parallel agents for diverse perspectives

#### 3. code-review
- **Purpose**: Automated code quality gate
- **Pattern**: Single-concern agent
- **Key Files**: code-reviewer.md (46 lines)
- **Lesson**: Simple agents with clear responsibility

#### 4. security-guidance
- **Purpose**: Security reminder hooks
- **Pattern**: Pattern-matching hooks with exit codes
- **Key Files**: security_reminder_hook.py (281 lines)
- **Lesson**: Hooks should warn, not auto-fix

#### 5. commit-commands
- **Purpose**: Git workflow automation
- **Pattern**: Multiple focused commands
- **Key Files**: `/commit`, `/sync`, `/push` commands
- **Lesson**: Commands have single purpose, clear workflow

#### 6. agent-sdk-dev
- **Purpose**: Tools for Claude Code plugin development
- **Pattern**: Developer-focused agents
- **Lesson**: Build tools for other developers

---

## Claude Code Design Patterns

### Agent Architecture

**Official Standard**:
```markdown
Length: 34-51 lines (target for production)
Structure:
- Frontmatter (5-7 fields)
- Mission statement (1-2 sentences)
- Core responsibilities (3-5 bullets)
- Process (general, not prescriptive)
- Output format (actionable results)

No: Scripts, detailed steps, artifact protocols, Python code
Yes: Clear mission, trust the model, focused scope
```

**Autonomous-Dev Adaptation**:
- Target: 50-100 lines (up from official 34-51, due to complexity)
- Maximum: 150 lines (strictly enforced)
- Strategy: Model-specific assignments (opus/sonnet/haiku)
- Principle: Trust the model (Anthropic standard)

### Hook Architecture

**Official Standard**:
```python
# Simplicity: Declarative pattern lists at top
# Concern: Single hook, single purpose
# Exit codes: 0 (allow), 1 (warn), 2 (block)
# Performance: < 1 second execution
# Session: Per-session state to avoid spam
# Prevention: Never auto-fix, always warn first
```

**Key Official Patterns**:
1. **Bash command validator** (84 lines) - Suggests rg instead of grep
2. **Security reminder** (281 lines) - Pattern-matching warnings
3. **Pre-tool hooks** - Validate before execution
4. **Exit codes**: 0=silent, 1=user sees warning, 2=Claude sees error

### Command Architecture

**Official Pattern - Phase-Based Workflow**:
```markdown
# Phase 1: Discovery
- Create todos
- Clarify requirements
- **User gate**: Approve?

# Phase 2: Exploration
- Launch agents in parallel
- **User gate**: Approve findings?

# Phase 3: Design
- Architecture planning
- **User gate**: Approve design?

[Continue with implementation, testing, deployment...]
```

**Key Insight**: Commands are structured workflows with user approval gates, not automated pipelines.

---

## Design Philosophy

### Five Core Principles (From Official Anthropic Plugins)

#### 1. Trust the Model
- Claude can infer complex logic from minimal guidance
- Over-prescription wastes context
- Example: "Extract strings" beats "Use for loop to iterate..."

#### 2. Simple > Complex
- 50-line agent outperforms 800-line agent
- Simplicity aids maintainability and scaling
- Complexity hides bugs

#### 3. Warn > Auto-fix
- Let Claude see and fix issues
- Auto-fixing prevents learning
- Use exit code 2 for blocking, code 1 for warnings

#### 4. Minimal > Complete
- Focused guidance beats exhaustive documentation
- Trust developers to figure details
- 3-page design guide > 30-page specification

#### 5. Parallel > Sequential
- Multiple agents offer diverse perspectives
- Launches simultaneously (faster)
- Combining results is often better than sequential pipelines

---

## Anti-Pattern Reference

### From Official Anthropic Analysis

#### Artifact Protocols
**Anti-pattern**: Using `.claude/artifacts/{id}/manifest.json` for agent communication
**Official approach**: Direct tool calls, no indirection
**Reason**: Unnecessary complexity, adds latency, hurts debugging

#### Bash Scripts in Markdown
**Anti-pattern**: Embedding bash scripts inside agent prompts
**Official approach**: Scripts in `/scripts/` directory, referenced by agents
**Reason**: Keeps concerns separate, agents focus on guidance not code hosting

#### Over-Prescription
**Anti-pattern**: Step-by-step instructions in agent prompts
**Official approach**: Clear mission, general process, trust model
**Reason**: Claude can figure it out; over-prescription limits flexibility

#### Auto-Fixing
**Anti-pattern**: Hooks that auto-fix issues (exit 0 after fixing)
**Official approach**: Hooks warn or block (exit 1 or 2), Claude fixes
**Reason**: Claude should see issues and learn patterns

---

## Best Practices Summary

### Agent Design Checklist
- [ ] Mission is 1-2 sentences (not paragraphs)
- [ ] Has 3-5 core responsibilities (not 20)
- [ ] No bash scripts or code examples
- [ ] Only essential tools (principle of least privilege)
- [ ] Total length 50-150 lines
- [ ] Clear output format specification
- [ ] No artifact protocols

### Hook Design Checklist
- [ ] Single concern (does one thing)
- [ ] Pattern list at top (declarative)
- [ ] Exit codes: 0/1/2 correct
- [ ] Runs in < 1 second
- [ ] No auto-fixing (warns only)
- [ ] Session state for warnings
- [ ] Total length < 300 lines

### Command Design Checklist
- [ ] Phase-based workflow
- [ ] User approval gates between phases
- [ ] TodoWrite for progress tracking
- [ ] Clear phase objectives
- [ ] Parallel agent launches (not serial)
- [ ] Each phase produces actionable output

---

## Context Efficiency Standards

### Token Budget Targets
- **Per-feature**: < 8,000 tokens
- **Agent prompts**: 500-1,000 tokens (50-100 lines)
- **Codebase exploration**: 2,000-3,000 tokens
- **Working memory**: 2,000-3,000 tokens
- **Buffer**: 1,000-2,000 tokens

### Implications
- Keep agents short and focused
- No artifact protocols (waste context)
- Session logging (paths, not content)
- Clear context between features (`/clear`)
- Minimal rather than exhaustive guidance

---

## Related Documentation

### Autonomous-Dev Internal Standards
- **README.md**: Complete user and contributor guide
- **CLAUDE.md**: Universal development standards
- **.claude/PROJECT.md**: Project-specific goals and architecture
- **docs/BEST-PRACTICES.md**: Production standards and anti-patterns
- **docs/ADRs/**: Architecture Decision Records

### Plugin User Documentation
- **plugins/autonomous-dev/README.md**: Installation and overview
- **plugins/autonomous-dev/docs/**: User guides, commands, troubleshooting

---

## Research Methodology

### Source Analysis Process
1. **Official Anthropic Plugins** - Analyzed 6 production plugins
2. **Pattern Extraction** - Identified common patterns across plugins
3. **Anti-Pattern Analysis** - Documented what NOT to do
4. **Autonomous-Dev Review** - Compared our implementation vs official standards
5. **Recommendations** - Created actionable guidance for improvement

### Update Frequency
- **Quarterly** (every 3 months) - Review official Anthropic updates
- **As-needed** - When new patterns discovered in production use
- **PR reviews** - Anti-patterns identified in code review

### Last Reviewed
- **2025-10-25**: Official Anthropic repository analysis
- **2025-10-27**: Consolidated into best practices guide

---

## Key Statistics from Analysis

### Agent Length Comparison
| Type | Official | Autonomous-Dev | Ratio |
|------|----------|----------------|-------|
| Simple agent | 34 lines | 337 lines | 10x |
| Complex agent | 51 lines | 864 lines | 17x |
| **Average** | **42 lines** | **600 lines** | **14x** |

### Complexity Indicators
- **Official**: No artifact protocols, no scripts, clear missions
- **Current**: Artifact protocols, embedded scripts, prescriptive guidance
- **Improvement**: Simplify to match official standards

### Recommended Simplification Targets
- **Phase 1**: Reduce agents to 100-150 lines (done in v3.0+)
- **Phase 2**: Remove artifact protocols (in progress)
- **Phase 3**: Eliminate embedded scripts (planned)
- **Phase 4**: Reduce guidance, trust model more (planned)

---

## Continuous Improvement Opportunities

### Based on Official Anthropic Standards

1. **Agent Simplification**
   - Current: 50-100 lines (improved from 800)
   - Target: 34-51 lines (official standard)
   - Gap: Reduce by 50%

2. **Hook Refactoring**
   - Current: Working well
   - Improvement: Reduce auto-fixing, focus on warnings

3. **Command Workflows**
   - Current: Good structure
   - Improvement: More explicit user gates

4. **Context Efficiency**
   - Current: 8K token target
   - Target: Consistently under target per feature

5. **Documentation**
   - Current: Comprehensive README
   - Improvement: Keep best practices accessible

---

## Contributing Back

If you discover patterns or anti-patterns not documented here:

1. Create an issue or discussion: https://github.com/akaszubski/autonomous-dev/issues
2. Document the pattern clearly
3. Cite sources or examples
4. Propose improvements
5. Update this reference guide

All contributions help the community learn better practices!

---

**Version**: 2.0 (Consolidated from research analysis)
**Audience**: Plugin developers and contributors
**Level**: Advanced (assumes familiarity with Claude Code)

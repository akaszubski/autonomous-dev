# Research Documentation

Catalog of research findings, architectural decisions, and design patterns for the autonomous-dev project.

## Research Catalog

### Architecture & Design

| Topic | Description | File |
|-------|-------------|------|
| Agent Chain Detection | Techniques for detecting and preventing infinite agent loops | [AGENT_CHAIN_DETECTION.md](AGENT_CHAIN_DETECTION.md) |
| Agent Coordination | Multi-agent communication patterns and orchestration | [AGENT_COORDINATION_RESEARCH.md](AGENT_COORDINATION_RESEARCH.md) |
| Hooks Architecture | Hook system design for automation enforcement | [HOOKS_ARCHITECTURE.md](HOOKS_ARCHITECTURE.md) |
| Safe Chain Detection | Safety mechanisms for preventing agent chain issues | [SAFE_CHAIN_DETECTION_DESIGN.md](SAFE_CHAIN_DETECTION_DESIGN.md) |
| Skills Progressive Disclosure | Skill loading and context optimization patterns | [SKILLS_PROGRESSIVE_DISCLOSURE.md](SKILLS_PROGRESSIVE_DISCLOSURE.md) |

### Implementation Patterns

| Topic | Description | File |
|-------|-------------|------|
| Batch Processing Design | Batch workflow architecture and retry strategies | [BATCH_PROCESSING_DESIGN.md](BATCH_PROCESSING_DESIGN.md) |
| Git Automation Patterns | Automated git operations and workflow patterns | [GIT_AUTOMATION_PATTERNS.md](GIT_AUTOMATION_PATTERNS.md) |
| TDD Workflow Patterns | Test-driven development workflow implementation | [TDD_WORKFLOW_PATTERNS.md](TDD_WORKFLOW_PATTERNS.md) |
| Tool Auto-Approval | Security-aware tool approval mechanisms | [TOOL_AUTO_APPROVAL.md](TOOL_AUTO_APPROVAL.md) |

### Best Practices & Analysis

| Topic | Description | File |
|-------|-------------|------|
| Documentation Persistence | Best practices for maintaining documentation across sessions | [DOCUMENTATION_PERSISTENCE_BEST_PRACTICES.md](DOCUMENTATION_PERSISTENCE_BEST_PRACTICES.md) |
| MCP Security Patterns | Model Context Protocol security implementation patterns | [MCP_SECURITY_PATTERNS.md](MCP_SECURITY_PATTERNS.md) |
| Pattern Borrowability Analysis | Evaluating which patterns can be reused across projects | [PATTERN_BORROWABILITY_ANALYSIS.md](PATTERN_BORROWABILITY_ANALYSIS.md) |
| Performance Optimization | Performance tuning and benchmark results | [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) |
| Real World Implementations | Case studies and real-world usage patterns | [REAL_WORLD_IMPLEMENTATIONS.md](REAL_WORLD_IMPLEMENTATIONS.md) |

### Testing & Validation

| Topic | Description | File |
|-------|-------------|------|
| Test Research | Testing methodologies and frameworks | [TEST_RESEARCH.md](TEST_RESEARCH.md) |

---

## Standards

All research documents follow the standards defined in [research-doc-standards.md](../.claude/skills/documentation-guide/docs/research-doc-standards.md) and should include:

- Clear frontmatter with Issue Reference, Research Date, and Status
- Substantial research content with 2+ best practices or security considerations
- Authoritative sources (official docs > GitHub > blogs)
- Actionable implementation notes
- Related issue links

---

*Last updated: 2026-01-25*

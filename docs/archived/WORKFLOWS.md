# Workflows & Examples

**Last Updated**: 2025-11-15

Real-world usage patterns and examples for autonomous-dev.

---

## Quick Reference

| Workflow | Commands | Time | When to Use |
|----------|----------|------|-------------|
| **Full Automation** | `/implement "feature"` | 20-30 min | New features, default choice |
| **Step-by-Step** | Individual commands | Varies | Learning, debugging, customization |
| **Research Only** | `/research "topic"` | 2-5 min | Before planning, spike work |
| **Planning Only** | `/plan "feature"` | 3-5 min | Architecture decisions |
| **Testing Only** | `/test-feature "feature"` | 2-5 min | TDD, test-first development |

---

## Workflow 1: Full Automation (Recommended)

**Use for**: Most features, default workflow

**Command**: `/implement "feature description"`

**Example**:
```bash
/implement "Add JWT authentication to the API with refresh tokens"
```

**What happens** (automatic):
1. ✅ Validates against PROJECT.md
2. ✅ Researches JWT patterns (2-5 min)
3. ✅ Plans architecture (3-5 min)
4. ✅ Writes tests first (2-5 min)
5. ✅ Implements code (5-10 min)
6. ✅ Reviews quality (parallel, 2-3 min)
7. ✅ Scans security (parallel, 1-2 min)
8. ✅ Updates docs (parallel, 1-2 min)
9. ✅ Creates commit/PR (optional, 30 sec)

**Total time**: 20-30 minutes

**Output**:
- Production-ready code
- Passing tests
- Documentation updates
- Security scan results
- Git commit (optional)

**After completion**:
```bash
/clear  # Clear context for next feature (recommended)
```

---

## Workflow 2: Step-by-Step (Manual Control)

**Use for**: Learning the process, debugging, custom workflows

**Commands**: Run individual agents in sequence

**Example**:
```bash
# Step 1: Research
/research "JWT authentication with refresh tokens"

# Step 2: Plan architecture
/plan "Add JWT auth to API with refresh tokens"

# Step 3: Write tests first
/test-feature "JWT authentication"

# Step 4: Implement to make tests pass
/implement "Make JWT tests pass"

# Step 5: Review code quality
/review

# Step 6: Scan for vulnerabilities
/security-scan

# Step 7: Update documentation
/update-docs
```

**Benefits**:
- Full control over each step
- Can skip steps (e.g., already researched)
- Easier to debug issues
- Customize workflow order

---

## Workflow 3: Research-Driven Development

**Use for**: Unfamiliar technologies, spike work, proof of concepts

**Commands**:
```bash
# Research patterns
/research "GraphQL federation patterns for microservices"

# Plan based on research
/plan "Implement GraphQL federation"

# Stop here if spike work
# OR continue with implementation
```

**Example output** (researcher agent):
```
Research Findings:

Best Practices:
- Apollo Federation 2 recommended for schema composition
- @key directive for entity resolution across services
- Gateway aggregates subgraph schemas

Security Considerations:
- Validate all resolver inputs
- Implement field-level auth
- Rate limiting at gateway level

Recommended Approach:
1. Define entity types with @key
2. Implement resolvers in each service
3. Configure gateway with subgraph URLs
4. Add authentication middleware
```

---

## Workflow 4: TDD-First Development

**Use for**: Test-driven development, critical features

**Commands**:
```bash
# Write tests first
/test-feature "User registration with email verification"

# Implement to make tests pass
/implement "Make user registration tests pass"

# Verify quality
/review
```

**Why TDD**:
- Tests define behavior before code
- Red-green-refactor cycle
- Higher test coverage
- Prevents regressions

---

## Workflow 5: Brownfield Project Adoption

**Use for**: Adding autonomous-dev to existing projects

**Command**: `/align --retrofit`

**What happens**:
1. **Phase 0**: Project analysis and tech stack detection
2. **Phase 1**: Deep codebase analysis (multi-language)
3. **Phase 2**: Gap assessment and 12-Factor compliance
4. **Phase 3**: Migration plan with dependency tracking
5. **Phase 4**: Step-by-step execution with rollback
6. **Phase 5**: Verification and readiness assessment

**Example**:
```bash
# Analyze existing project
/align --retrofit

# Agent analyzes:
# - Current architecture
# - Dependencies
# - Test coverage
# - Documentation state

# Generates migration plan:
# - Gaps to fill
# - Changes needed for autonomous-dev compatibility
# - Risk assessment
# - Rollback strategy
```

**See also**: [docs/BROWNFIELD-ADOPTION.md](BROWNFIELD-ADOPTION.md)

---

## Workflow 6: Project Health Monitoring

**Use for**: Regular check-ins, sprint planning, status updates

**Commands**:
```bash
# View project health
/status

# Fix alignment issues
/align

# Track progress
# (PROJECT.md auto-updated after each /implement)
```

**Example output** (`/status`):
```
Project Health Report:

GOALS Progress:
✅ Build scalable REST API - 80% complete
🚧 Create user dashboard - 40% complete
⏳ Achieve 99.9% uptime - 0% complete

Active Blockers:
- Database migrations pending (Sprint 3)
- Load testing infrastructure needed

Strategic Recommendations:
1. Complete dashboard before load testing
2. Consider Redis for session management
3. Document API versioning strategy
```

---

## Workflow 7: GitHub Issue Creation

**Use for**: Feature planning, bug tracking, team collaboration

**Command**: `/create-issue "description"`

**Example**:
```bash
/create-issue "Add rate limiting to prevent API abuse"
```

**What happens**:
1. **researcher agent** finds rate limiting patterns (2-5 min)
2. **issue-creator agent** generates structured issue (1-2 min)
3. Creates GitHub issue via gh CLI (10-30 sec)

**Example output**:
```
Issue Created: #75

Title: Add rate limiting to prevent API abuse

Description:
- Research: Token bucket vs sliding window algorithms
- Implementation plan: 4 components (~300 LOC)
- Acceptance criteria: 8 testable requirements
- Security: CWE-770 (unbounded resource allocation)

URL: https://github.com/owner/repo/issues/75
```

**See also**: `/create-issue` command documentation

---

## Workflow 8: Plugin Maintenance

**Use for**: Keeping plugin updated, syncing changes

**Commands**:
```bash
# Update to latest version
/update-plugin

# Verify all components working
/health-check

# Sync development changes (for contributors)
/sync

# View pipeline status
/pipeline-status
```

**Health check example**:
```bash
/health-check

✅ All 22 agents loaded
✅ All 28 skills available
✅ All 51 hooks registered
✅ All 7 commands functional
✅ Marketplace version: v3.21.0 (latest)

No issues detected. Plugin is healthy.
```

---

## Real-World Examples

### Example 1: Add New API Endpoint

**Goal**: Add `/api/users` endpoint with pagination

**Workflow**:
```bash
/implement "Add GET /api/users endpoint with cursor-based pagination, limit 100 per page"
```

**Result** (after 25 minutes):
- `src/api/users.py` - New endpoint implementation
- `tests/api/test_users.py` - Unit and integration tests
- `docs/API.md` - Updated API documentation
- Security scan passed
- Commit created with conventional message

### Example 2: Fix Security Vulnerability

**Goal**: Fix SQL injection vulnerability in search

**Workflow**:
```bash
# Step 1: Research mitigation patterns
/research "Prevent SQL injection in Python with SQLAlchemy"

# Step 2: Plan the fix
/plan "Fix SQL injection in search endpoint using parameterized queries"

# Step 3: Write tests to verify fix
/test-feature "SQL injection prevention in search"

# Step 4: Implement the fix
/implement "Make SQL injection tests pass"

# Step 5: Verify security
/security-scan
```

### Example 3: Refactor for Performance

**Goal**: Optimize database queries causing slow page loads

**Workflow**:
```bash
# Step 1: Research optimization patterns
/research "SQLAlchemy N+1 query optimization strategies"

# Step 2: Plan optimization
/plan "Add eager loading to reduce N+1 queries in user dashboard"

# Step 3: Write performance tests
/test-feature "Dashboard query performance under 200ms"

# Step 4: Implement optimizations
/implement "Make performance tests pass with eager loading"

# Step 5: Review changes
/review
```

### Example 4: New Project Setup

**Goal**: Bootstrap a new project with autonomous-dev

**Workflow**:
```bash
# Step 1: Install plugin (see README.md Quick Install)

# Step 2: Run setup wizard
/setup

# Wizard asks:
# - Project type? (Python, TypeScript, etc.)
# - Use hooks? (auto-format, auto-test)
# - Create PROJECT.md? (yes/no)

# Step 3: Define strategic direction
# (Edit .claude/PROJECT.md with GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE)

# Step 4: Start building
/implement "Add user authentication"
```

---

## Context Management Best Practices

### When to Clear Context

✅ **Clear after each feature** (recommended):
```bash
/implement "feature 1"
/clear
/implement "feature 2"
/clear
```

✅ **Clear before unrelated features**:
```bash
/implement "Add auth"       # Context: ~8K tokens
/clear
/implement "Add analytics"  # Fresh context
```

❌ **Don't clear mid-feature**:
```bash
/research "JWT patterns"
# DON'T: /clear
/plan "Add JWT"  # Needs research context!
```

### Why Clear Context?

**Without clearing**:
- Context bloats to 50K+ tokens after 3-4 features
- System performance degrades
- May hit context limits

**With clearing**:
- Context stays under 8K tokens
- Consistent performance
- Works for 100+ features

**What /clear does NOT do**:
- Does NOT delete files
- Does NOT lose work
- Does NOT clear session logs
- Only clears conversation history

---

## Troubleshooting Workflows

### "Feature doesn't align with PROJECT.md"

**Fix**:
```bash
# Option 1: Check alignment
cat .claude/PROJECT.md | grep -A 5 "## GOALS"

# Option 2: Fix alignment
/align

# Option 3: Update PROJECT.md if direction changed
vim .claude/PROJECT.md
```

### "Context budget exceeded"

**Fix**:
```bash
/clear  # Then retry
```

### "Commands not working after update"

**Fix**:
1. Fully quit Claude Code (`Cmd+Q` or `Ctrl+Q`)
2. Wait 5 seconds
3. Reopen Claude Code
4. Verify: Commands should work

**Why**: `/exit` doesn't reload commands, only full restart does.

### "Hooks blocking operations"

**Fix**:
```bash
# Check what hook failed
# (Error message shows hook name)

# Option 1: Fix the violation
# (e.g., if security_scan failed, remove secret)

# Option 2: Disable specific hook temporarily
# Edit .claude/settings.json
```

---

## Performance Tips

### Optimize Workflow Speed

1. **Use Haiku for research** (already default)
   - Researcher agent uses Haiku model
   - 3-5 min faster than Sonnet

2. **Leverage parallel validation** (automatic)
   - reviewer, security-auditor, doc-master run simultaneously
   - 60% faster than sequential

3. **Clear context frequently**
   - Prevents performance degradation
   - Maintains fast response times

4. **Use individual commands selectively**
   - Skip research if you already know patterns
   - Skip planning for simple changes
   - Use `/implement` directly for quick fixes

---

## Learn More

- **[ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md)** - How the system works
- **[REFERENCE.md](REFERENCE.md)** - Complete command reference
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Contributing guide

**For command details**: See `plugins/autonomous-dev/commands/` directory

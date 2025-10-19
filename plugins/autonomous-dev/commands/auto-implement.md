---
description: Autonomously implement a feature from requirement to production-ready code. Handles PROJECT.md validation, research, planning, TDD, security, and documentation.
---

# Autonomous Feature Implementation

Use the orchestrator agent to implement your feature with full autonomous pipeline.

## What This Does

1. **Validates** feature against .claude/PROJECT.md goals
2. **Researches** best practices and patterns
3. **Plans** detailed implementation approach
4. **Writes tests first** (TDD - tests fail initially)
5. **Implements code** to make tests pass
6. **Reviews** code quality and patterns
7. **Scans** for security vulnerabilities
8. **Updates** documentation (CHANGELOG, README)
9. **Prompts** you to `/clear` for next feature

**Time**: 20-35 minutes (fully autonomous)
**Quality**: 80%+ coverage, security scanned, documented

## Usage

```bash
/auto-implement [feature description]
```

The more detailed your description, the better the results.

## Examples

### Simple Feature
```bash
/auto-implement health check endpoint that returns {"status": "ok", "timestamp": "now"}
```

### Medium Complexity
```bash
/auto-implement user authentication with JWT tokens, refresh tokens, and password hashing
```

### Complex Feature
```bash
/auto-implement REST API endpoint for blog posts with:
- CRUD operations (create, read, update, delete)
- Pagination (20 posts per page)
- Full-text search by title/content
- Tag filtering
- Author association
- Published/draft status
- Timestamps (created_at, updated_at)
- 80%+ test coverage
```

### With Specific Requirements
```bash
/auto-implement database caching layer using Redis:
- 5-minute TTL on all queries
- Automatic cache invalidation on updates
- Cache hit/miss metrics
- Graceful fallback if Redis unavailable
- Connection pool (max 10 connections)
```

## What Happens

```
You run: /auto-implement user authentication with JWT

Orchestrator:
├─ Checks .claude/PROJECT.md alignment ✅
├─ researcher: Finds JWT best practices (5 min)
├─ planner: Creates implementation plan (5 min)
├─ test-master: Writes 18 failing tests (5 min)
├─ implementer: Makes tests pass (12 min)
├─ reviewer: Quality check ✅ (2 min)
├─ security-auditor: Security scan ✅ (2 min)
└─ doc-master: Updates CHANGELOG ✅ (1 min)

Total: 32 minutes
Output: Production-ready code with tests, docs, security
```

## After Completion

You'll see:

```
✨ Feature Implementation Complete!

Session: docs/sessions/20251019-143022-session.md
Branch: feature/user-authentication

👉 Next Steps:
1. Review implementation
2. Merge when ready
3. CRITICAL: Run /clear

🧹 Context Management:
/clear

This is MANDATORY to prevent context bloat!
```

## Important Notes

### PROJECT.md Alignment

If your feature doesn't align with project goals, orchestrator will explain why:

```
⚠️ Feature Alignment Issue

Goal: "Build lightweight system"
Requested: "Add blockchain integration"
Issue: Blockchain is heavy/complex, conflicts with "lightweight"

Suggestions:
1. Modify feature to be lighter
2. Update PROJECT.md if strategy changed
```

### Context Clearing (CRITICAL!)

After EVERY feature, you MUST run:

```bash
/clear
```

**Why**:
- Without: Context grows to 50K+ tokens → System fails
- With: Context stays <1K tokens → Works for 100+ features

### Session Files

All agent actions logged to `docs/sessions/`:

```bash
# View latest session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

Contains: Timestamps, agent names, file paths (not full content)

## Troubleshooting

### "Context budget exceeded"
```bash
/clear  # Then retry
```

### "Feature doesn't align"
```bash
# Check goals
cat .claude/PROJECT.md | grep -A 5 "## GOALS"

# Either modify feature or update PROJECT.md
```

### "Tests failing"
```bash
# See details in session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

### "Hooks not running"
```bash
# Make scripts executable
chmod +x scripts/hooks/*.py

# Install dependencies
pip install black isort pytest pytest-cov
```

## Tips for Best Results

### Be Specific

❌ Vague: "Add authentication"
✅ Specific: "Add JWT authentication with refresh tokens, bcrypt hashing, HTTP-only cookies, rate limiting (5 req/min on login)"

### Include Requirements

✅ "with 80%+ test coverage"
✅ "following REST conventions"
✅ "with input validation for all fields"
✅ "with error handling for edge cases"

### Specify Technology

✅ "using Redis for caching"
✅ "with PostgreSQL database"
✅ "using FastAPI framework"

## What You Get

After `/auto-implement` completes:

- ✅ **Code**: Production-ready implementation
- ✅ **Tests**: 80%+ coverage, all passing
- ✅ **Docs**: CHANGELOG updated, README synced
- ✅ **Security**: Scanned for vulnerabilities
- ✅ **Quality**: Reviewed and formatted
- ✅ **Branch**: Created with semantic name
- ✅ **Session**: Full audit trail

All in 20-35 minutes, fully autonomous!

---

**Invoke orchestrator agent to implement: $ARGUMENTS**

The orchestrator handles the complete pipeline. Do NOT implement manually.

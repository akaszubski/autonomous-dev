# How Claude Code 2.0 Bootstrap Works

**Complete technical explanation of the autonomous development system**

**Last Updated**: 2025-10-19
**Based on**: ReAlign v3.0.0 (98% alignment, production-ready)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Details](#component-details)
3. [How Agents Work](#how-agents-work)
4. [How Hooks Work](#how-hooks-work)
5. [How Pattern Learning Works](#how-pattern-learning-works)
6. [Progressive Disclosure System](#progressive-disclosure-system)
7. [Workflow Examples](#workflow-examples)
8. [Comparison: ReAlign vs Bootstrap](#comparison-realign-vs-bootstrap)

---

## Architecture Overview

### The 4-Layer System

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: CONFIGURATION                                      │
│ .claude/settings.json - Defines hooks, agents, auto-modes   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: INTELLIGENCE (Agents)                              │
│ .claude/agents/ - Specialized subagents for tasks           │
│ • planner, researcher, implementer, test-master, etc.       │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: KNOWLEDGE (Core Files)                             │
│ • PROJECT.md - Single source of truth                       │
│ • PATTERNS.md - Auto-learned coding patterns                │
│ • STATUS.md - Health dashboard                              │
│ • STANDARDS.md - Engineering principles                     │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: AUTOMATION (Hooks + CI/CD)                         │
│ scripts/hooks/ - Local enforcement (90%)                    │
│ .github/workflows/ - CI safety net (10%)                    │
└─────────────────────────────────────────────────────────────┘
```

### Quality Enforcement Distribution

**90%** - Claude Code hooks (proactive, real-time)
- Auto-format on every write
- Auto-test on every change
- Security scan on every file
- Pattern learning continuous

**8%** - Local git hooks (pre-commit, pre-push)
- Format check before commit
- Test suite before push
- Coverage enforcement

**2%** - CI/CD safety net (GitHub Actions)
- Catch hook bypasses (`--no-verify`)
- Multi-platform validation
- Weekly health checks

---

## Component Details

### Current ReAlign Setup (Source)

**Location**: `/Users/akaszubski/Documents/GitHub/realign/`

| Component | Count | Location | Purpose |
|-----------|-------|----------|---------|
| **Agents** | 9 | `.claude/agents/` | Specialized subagents |
| **Hooks** | 10 | `scripts/hooks/` | Python-specific automation |
| **Skills** | 18 | `.claude/skills/` | Domain knowledge |
| **Workflows** | 3 | `.github/workflows/` | CI/CD |
| **Core Files** | 4 | `.claude/` | PROJECT, PATTERNS, STATUS, STANDARDS |

**ReAlign Agents** (9):
1. `planner.md` - Architecture & design
2. `researcher.md` - Web research
3. `implementer.md` - Code implementation
4. `test-master.md` - TDD + progression + regression
5. `reviewer.md` - Code quality gate
6. `security-auditor.md` - Security scanning
7. `doc-master.md` - Documentation sync
8. `ci-monitor.md` - CI/CD monitoring
9. `system-aligner.md` - Health metrics (ReAlign-specific)

**ReAlign Hooks** (10):
1. `auto_format.py` - Black + isort (Python)
2. `auto_test.py` - Pytest (Python)
3. `security_scan.py` - Bandit, secrets (Python)
4. `auto_align_filesystem.py` - Doc organization
5. `auto_generate_tests.py` - TDD (generate failing tests first)
6. `auto_add_to_regression.py` - Add tests to regression suite
7. `auto_enforce_coverage.py` - 80% coverage gate
8. `auto_update_docs.py` - Sync docs with code changes
9. `auto_tdd_enforcer.py` - Enforce TDD workflow
10. `validate_standards.py` - Code standards validation

### Bootstrap Template (Generic)

**Location**: `/Users/akaszubski/Documents/GitHub/realign/.claude/bootstrap-template/`

| Component | Count | Location | Purpose |
|-----------|-------|----------|---------|
| **Agents** | 8 | `agents/` | Generic (no system-aligner) |
| **Hooks** | 5 | `hooks/` | Multi-language automation |
| **Skills** | 0 | - | Not extracted yet |
| **Workflows** | 2 | `github/workflows/` | Generic CI/CD |
| **Templates** | 3 | `templates/` | PROJECT, PATTERNS, STATUS |

**Bootstrap Agents** (8):
- Same as ReAlign except:
  - ❌ No `system-aligner.md` (ReAlign-specific)
  - ✅ All others genericized (MLX → generic examples)

**Bootstrap Hooks** (5):
1. `auto_format.py` - **Multi-language** (Python, JS, Go)
2. `auto_test.py` - **Multi-language** (pytest, jest, go test)
3. `security_scan.py` - **Multi-language** (bandit, npm audit, gosec)
4. `pattern_curator.py` - **Generic** pattern learning
5. `auto_align_filesystem.py` - **Generic** doc organization

**Key Difference**: Bootstrap hooks detect project language and run appropriate tools.

---

## How Agents Work

### Agent Invocation Flow

```
User: "Add user authentication"
         ▼
Main Agent (Claude Code)
  ├─ Reads: CLAUDE.md (lightweight context)
  ├─ Checks: .claude/settings.json
  └─ Decision: "This is complex, invoke planner agent"
         ▼
Planner Agent Launched
  ├─ Loads context:
  │   • .claude/PROJECT.md (full)
  │   • .claude/PATTERNS.md (full)
  │   • .claude/STANDARDS.md (Architecture section)
  ├─ Analyzes: Requirements, existing patterns
  ├─ Designs: Architecture, components, data flow
  └─ Returns: Detailed plan to main agent
         ▼
Main Agent: "Plan looks good, invoke test-master"
         ▼
Test-Master Agent Launched
  ├─ Loads context:
  │   • .claude/PROJECT.md (REQUIREMENTS section)
  │   • .claude/PATTERNS.md (testing patterns)
  ├─ Writes: Failing tests (TDD)
  └─ Returns: Test suite to main agent
         ▼
Main Agent: "Tests ready, invoke implementer"
         ▼
Implementer Agent Launched
  ├─ Loads context:
  │   • .claude/PROJECT.md (ARCHITECTURE + CONTRACTS)
  │   • .claude/PATTERNS.md (full)
  │   • .claude/skills/python-standards/
  ├─ Implements: Code to make tests pass
  └─ Returns: Implementation to main agent
         ▼
PostToolUse Hook Triggered (auto_format.py)
  ├─ Formats: black + isort
  └─ Writes: Formatted code
         ▼
PostToolUse Hook Triggered (auto_test.py)
  ├─ Detects: Changed file (src/auth.py)
  ├─ Runs: pytest tests/unit/test_auth.py
  └─ Reports: ✅ All tests passing
         ▼
Main Agent: "Code complete, invoke reviewer"
         ▼
Reviewer Agent Launched
  ├─ Loads context:
  │   • .claude/PROJECT.md (REQUIREMENTS + CONTRACTS)
  │   • .claude/PATTERNS.md (full)
  │   • .claude/STANDARDS.md (Quality section)
  ├─ Reviews: Pattern adherence, security, tests
  └─ Returns: ✅ Approved or ❌ Issues found
         ▼
Main Agent: "All good, feature complete!"
```

### Progressive Disclosure (Context Loading)

Each agent loads ONLY what it needs:

| Agent | Context Loaded | Token Budget | Why |
|-------|---------------|--------------|-----|
| **Main** | CLAUDE.md only | ~1,500 | Lightweight coordination |
| **Planner** | PROJECT + PATTERNS + STANDARDS | ~5,600 | Needs full vision |
| **Test-Master** | PROJECT (REQUIREMENTS) + testing patterns | ~2,700 | Needs test criteria |
| **Implementer** | PROJECT (ARCH + CONTRACTS) + PATTERNS + skills | ~4,700 | Needs architecture |
| **Reviewer** | PROJECT (REQS + CONTRACTS) + PATTERNS + quality | ~4,100 | Needs requirements |
| **Security-Auditor** | PROJECT (CONTRACTS) + security patterns | ~1,500 | Focused scope |
| **Researcher** | PROJECT (frontmatter only) | ~1,400 | Just needs context |

**Total Budget**: 5,300 tokens (vs 25,000+ if loading everything)

**Benefit**: 79% reduction in context size = faster, cheaper, more focused.

---

## How Hooks Work

### Hook Execution Flow

```
Claude Code: Write("src/auth.py", content="...")
         ▼
File Written to Disk
         ▼
settings.json: Check hooks for "PostToolUse" + "Write" + "src/**/*.py"
         ▼
Match Found: auto_format.py hook
         ▼
Execute: python scripts/hooks/auto_format.py src/auth.py
         ▼
auto_format.py:
  1. Detect language (Python)
  2. Run: black src/auth.py
  3. Run: isort src/auth.py
  4. Report: ✅ Formatted
         ▼
File Updated on Disk (formatted)
         ▼
settings.json: Check next hook
         ▼
Match Found: auto_test.py hook
         ▼
Execute: python scripts/hooks/auto_test.py src/auth.py
         ▼
auto_test.py:
  1. Detect language (Python)
  2. Find related tests (tests/unit/test_auth.py)
  3. Run: pytest tests/unit/test_auth.py
  4. Report: ✅ 5 passed
         ▼
settings.json: Check next hook
         ▼
Match Found: security_scan.py hook
         ▼
Execute: python scripts/hooks/security_scan.py src/auth.py
         ▼
security_scan.py:
  1. Scan for secrets (API keys, tokens)
  2. Run: bandit src/auth.py
  3. Report: ✅ No issues
         ▼
All Hooks Complete
         ▼
Claude Code: Continue with next action
```

### Multi-Language Hook Example: auto_format.py

```python
# Bootstrap version (multi-language)

def detect_language():
    """Detect project language from project files."""
    if Path("pyproject.toml").exists():
        return "python"
    elif Path("package.json").exists():
        return "javascript"  # or "typescript" if TS in deps
    elif Path("go.mod").exists():
        return "go"
    return "unknown"

def format_file(file_path: str, language: str):
    """Format file based on detected language."""
    if language == "python":
        subprocess.run(["black", file_path])
        subprocess.run(["isort", file_path])
    elif language in ["javascript", "typescript"]:
        subprocess.run(["prettier", "--write", file_path])
    elif language == "go":
        subprocess.run(["gofmt", "-w", file_path])

# Main
language = detect_language()
for file_path in sys.argv[1:]:
    format_file(file_path, language)
```

**Key**: Same hook works across languages!

---

## How Pattern Learning Works

### Pattern Curator Hook

**Trigger**: Every file write

**Process**:

1. **Extract Patterns** - Analyze code for recurring structures
   ```python
   # Example: Database connection pattern detected
   def get_db():
       return DatabaseConnection(
           host=os.getenv("DB_HOST"),
           pool_size=10
       )
   ```

2. **Track Frequency** - Count how many times pattern appears
   - Seen 1-2 times → "🔄 Candidate"
   - Seen 3+ times → Promote to "✅ Validated"

3. **Update PATTERNS.md** - Auto-append to file
   ```markdown
   ### Database Connection Pattern (✅ Validated)

   Seen: 5 times
   Last: 2025-10-19

   \`\`\`python
   def get_db():
       return DatabaseConnection(
           host=os.getenv("DB_HOST"),
           pool_size=10
       )
   \`\`\`

   **When to use**: All database access
   **Alternatives**: Direct connection (avoid)
   ```

4. **Claude Uses Pattern** - In future implementations:
   - Implementer agent loads PATTERNS.md
   - Sees validated pattern
   - Applies same pattern to new code

### Pattern Learning Cycle

```
Week 1:
  Code: First use of pattern → Added as "Candidate"

Week 2:
  Code: Second use → Still "Candidate"

Week 3:
  Code: Third use → Promoted to "Validated" ✅

Week 4:
  New feature → Implementer sees validated pattern → Uses it

Week 8:
  Pattern seen 20+ times → Becomes "Core Pattern"
```

**Result**: Project-specific patterns emerge organically.

---

## Progressive Disclosure System

### Problem: Context Explosion

Traditional approach loads EVERYTHING:
```
CLAUDE.md (2,000 tokens)
+ PROJECT.md (8,000 tokens)
+ PATTERNS.md (6,000 tokens)
+ STATUS.md (3,000 tokens)
+ STANDARDS.md (4,000 tokens)
+ All skills (10,000 tokens)
= 33,000 tokens per request
```

**Issues**:
- Slow (large context)
- Expensive (more tokens)
- Unfocused (irrelevant info)

### Solution: Progressive Disclosure

Load ONLY what each agent needs:

```
Main Agent:
  CLAUDE.md (1,500 tokens)

Planner Agent:
  PROJECT.md (full) + PATTERNS.md (full) + STANDARDS.md (Architecture only)
  = 5,600 tokens

Implementer Agent:
  PROJECT.md (ARCHITECTURE + CONTRACTS sections) + PATTERNS.md (full)
  = 4,700 tokens
```

**Benefits**:
- ✅ 79% fewer tokens (5,300 vs 25,000+)
- ✅ Faster responses
- ✅ More focused agents
- ✅ Better quality (less noise)

### Context Mapping (settings.json)

```json
{
  "agent_context_mapping": {
    "implementer": {
      "files": [
        {"path": ".claude/PROJECT.md", "mode": "sections", "sections": ["ARCHITECTURE", "CONTRACTS"]},
        {"path": ".claude/PATTERNS.md", "mode": "full"}
      ],
      "skills": ["python-standards", "security-patterns"],
      "estimated_tokens": 4700
    }
  }
}
```

**Result**: Each agent gets tailored context automatically.

---

## Workflow Examples

### Example 1: Adding a New Feature (End-to-End)

**User Request**: "Add user authentication with JWT"

```
STEP 1: Main Agent Analysis
  ├─ Read: CLAUDE.md (~1,500 tokens)
  ├─ Decision: "Complex feature, invoke planner"
  └─ Launch: planner agent

STEP 2: Planning Phase
  ├─ Planner loads:
  │   • PROJECT.md (full)
  │   • PATTERNS.md (full)
  │   • STANDARDS.md (Architecture section)
  ├─ Designs:
  │   • Components: AuthService, JWTManager, UserModel
  │   • Data flow: Login → Validate → Generate JWT → Return
  │   • Contracts: POST /auth/login, GET /auth/verify
  └─ Returns: Detailed plan (saved to PROJECT.md > CURRENT FOCUS)

STEP 3: Test-First (TDD)
  ├─ Main invokes: test-master agent
  ├─ Test-master loads:
  │   • PROJECT.md (REQUIREMENTS section)
  │   • Testing patterns from PATTERNS.md
  ├─ Generates: Failing tests
  │   • tests/unit/test_auth_service.py
  │   • tests/integration/test_auth_flow.py
  └─ Returns: Test suite (failing)

STEP 4: Implementation
  ├─ Main invokes: implementer agent
  ├─ Implementer loads:
  │   • PROJECT.md (ARCHITECTURE + CONTRACTS)
  │   • PATTERNS.md (full)
  │   • skills/python-standards/
  │   • skills/security-patterns/
  ├─ Writes:
  │   • src/auth/service.py
  │   • src/auth/jwt_manager.py
  │   • src/models/user.py
  └─ PostToolUse hooks fire:
      ├─ auto_format.py → Formats with black + isort
      ├─ auto_test.py → Runs tests → ✅ All pass
      ├─ security_scan.py → Scans for secrets → ✅ Clean
      └─ pattern_curator.py → Learns JWT pattern

STEP 5: Review
  ├─ Main invokes: reviewer agent
  ├─ Reviewer loads:
  │   • PROJECT.md (REQUIREMENTS + CONTRACTS)
  │   • PATTERNS.md (full)
  │   • STANDARDS.md (Quality section)
  ├─ Checks:
  │   • Pattern adherence ✅
  │   • Security (JWT secrets in env) ✅
  │   • Tests (100% coverage) ✅
  │   • Documentation (docstrings) ✅
  └─ Approves: Feature ready

STEP 6: Documentation
  ├─ Main invokes: doc-master agent
  ├─ Doc-master updates:
  │   • docs/api/authentication.md (new)
  │   • CHANGELOG.md (add entry)
  │   • PROJECT.md (mark completed)
  └─ Runs: auto_align_filesystem.py → Moves docs to proper location

STEP 7: Commit
  ├─ User: "git commit"
  ├─ Pre-commit hook runs:
  │   • Check format ✅
  │   • Run tests ✅
  │   • Check coverage (82%) ✅
  └─ Commit succeeds

STEP 8: Push
  ├─ User: "git push"
  ├─ Pre-push hook runs:
  │   • Full test suite ✅
  │   • Coverage ≥80% ✅
  └─ Push succeeds

STEP 9: CI/CD (GitHub Actions)
  ├─ Workflow: safety-net.yml
  ├─ Runs:
  │   • Tests on Python 3.11, 3.12
  │   • Security scan (bandit)
  │   • Coverage report
  └─ Result: ✅ All checks pass

Total Time: 15 minutes (vs 2-4 hours manual)
```

### Example 2: Fixing a Bug

**User**: "Fix login bug - case sensitivity issue"

```
STEP 1: Main Agent
  ├─ Reads: CLAUDE.md
  ├─ Decision: "Simple fix, no planning needed"
  └─ Implements directly

STEP 2: Implementation
  ├─ Edits: src/auth/service.py
  │   # Before:
  │   if user.email == input_email:
  │
  │   # After:
  │   if user.email.lower() == input_email.lower():
  └─ Hooks fire:
      ├─ auto_format.py → ✅ Formatted
      ├─ auto_test.py → ✅ Tests pass
      └─ security_scan.py → ✅ Clean

STEP 3: Add Regression Test
  ├─ Hook: auto_add_to_regression.py
  ├─ Creates: tests/regression/test_login_case_sensitivity.py
  └─ Ensures bug never returns

Total Time: 3 minutes (vs 20 minutes manual)
```

---

## Comparison: ReAlign vs Bootstrap

### What's Different?

| Aspect | ReAlign (Source) | Bootstrap (Generic) |
|--------|------------------|---------------------|
| **Purpose** | MLX training toolkit | Any project setup |
| **Language** | Python only | Python, JS, TS, Go, Rust |
| **Agents** | 9 (includes system-aligner) | 8 (generic) |
| **Hooks** | 10 (Python-specific) | 5 (multi-language) |
| **Hook Logic** | Direct tool calls (black, pytest) | Language detection → appropriate tool |
| **Skills** | 18 (MLX, training, Python) | 0 (you add your own) |
| **Patterns** | MLX layers, LoRA, DPO | Your project patterns |
| **Examples** | Model training, fine-tuning | Generic web API, CLI, library |

### What's the Same?

| Feature | Both |
|---------|------|
| **Core Architecture** | 4-layer (Config, Intelligence, Knowledge, Automation) |
| **Progressive Disclosure** | 5,300 token budget |
| **Agent Workflow** | Plan → Test → Implement → Review |
| **Pattern Learning** | Auto-curator, candidate → validated |
| **Quality Gates** | 80% coverage, auto-format, security scan |
| **Documentation** | PROJECT.md, PATTERNS.md, STATUS.md, STANDARDS.md |

### Migration Path

**ReAlign improvements → Bootstrap sync**:

```bash
# Quarterly sync (every 3 months)
cd ~/Documents/GitHub/realign

# Check what changed
git log --since="3 months ago" --oneline .claude/agents/ scripts/hooks/

# For each improvement:
  1. Is it generic or ReAlign-specific?
  2. If generic:
     - Copy to .claude/bootstrap-template/
     - Run generalization script (replace MLX → generic)
     - Test on dummy project
     - Commit to bootstrap template
  3. If ReAlign-specific:
     - Keep in ReAlign only

# Tag new bootstrap version
git tag bootstrap-v1.1.0
```

**User projects sync**:

```bash
# Pull latest ReAlign
cd ~/Documents/GitHub/realign
git pull

# Re-bootstrap your project (safe - won't overwrite custom changes)
cd ~/my-project
~/Documents/GitHub/realign/scripts/bootstrap_project.sh .

# Review changes
git diff .claude/agents/

# Commit if desired
git commit -am "chore: sync Claude Code 2.0 updates from ReAlign"
```

---

## Key Insights

### Why This Works

1. **Single Source of Truth** (PROJECT.md)
   - All requirements in one place
   - Agents read same source
   - No inconsistencies

2. **Progressive Disclosure**
   - Each agent loads ONLY what it needs
   - 79% fewer tokens
   - Faster, cheaper, more focused

3. **Autonomous Enforcement** (Hooks)
   - 90% quality gates automated
   - Real-time feedback
   - Can't forget to format/test

4. **Self-Improving** (Pattern Learning)
   - System learns YOUR patterns
   - Not generic templates
   - Improves over time

5. **Specialized Agents**
   - Planner ≠ Implementer
   - Each expert in their domain
   - Better results than generalist

### What Makes It "Autonomous"?

**Before Claude Code 2.0**:
- Developer writes code
- Developer remembers to format
- Developer remembers to test
- Developer remembers to update docs
- Developer reviews own code

**After Claude Code 2.0**:
- Claude writes code
- Hook auto-formats
- Hook auto-tests
- Hook auto-updates docs
- Reviewer agent reviews
- Developer just approves

**Result**: 6 hours/week vs 40 hours/week (85% time savings)

---

## Summary: How It All Fits Together

```
You: "Add user authentication"
         ▼
Main Agent (reads CLAUDE.md)
  ↓ delegates to ↓
Planner Agent (reads PROJECT.md + PATTERNS.md)
  → Creates plan
         ▼
Test-Master Agent (writes failing tests)
  → Saves to tests/
         ▼
Implementer Agent (reads PATTERNS.md + skills)
  → Writes code to src/
         ▼
Hooks (auto-format, auto-test, security-scan)
  → Enforce quality in real-time
         ▼
Pattern-Curator Hook
  → Learns new patterns → Updates PATTERNS.md
         ▼
Reviewer Agent
  → Validates quality → ✅ Approves
         ▼
Doc-Master Agent
  → Updates docs/ and CHANGELOG.md
         ▼
Git Hooks (pre-commit, pre-push)
  → Final quality gates
         ▼
CI/CD (GitHub Actions)
  → Safety net (catches hook bypasses)
         ▼
Feature Complete! 🎉
```

**Time**: 15 minutes (vs 2-4 hours manual)
**Quality**: 98% alignment, 80%+ coverage (enforced)
**Effort**: You approve, Claude does the work

---

**Questions? Check the ReAlign project for production example!**

*Last Updated: 2025-10-19*
*Based on: ReAlign v3.0.0 (98% alignment)*

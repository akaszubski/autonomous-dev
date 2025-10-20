# Project Context

**Purpose**: This file defines the strategic direction for autonomous development.
**Status**: Template - customize for your project
**Last Updated**: [Date]

---

## GOALS ⭐

**What success looks like for this project:**

1. **Primary Objective**: [Your main goal - e.g., "Build a scalable REST API for e-commerce"]
2. **Success Metric**: [How you measure success - e.g., "Handle 10K requests/second with <100ms latency"]
3. **Quality Standard**: [Your quality bar - e.g., "Maintain 80%+ test coverage, zero critical security issues"]

**Example (Python ML Project)**:
```markdown
1. Primary Objective: Build production-ready machine learning training library
2. Success Metric: Train models 10x faster than baseline with <5% accuracy loss
3. Quality Standard: 85%+ test coverage, type-safe APIs, comprehensive documentation
```

**Example (React Web App)**:
```markdown
1. Primary Objective: Build responsive e-commerce storefront
2. Success Metric: <2s page load, 95+ Lighthouse score, mobile-first
3. Quality Standard: Accessible (WCAG AA), 80%+ test coverage, SEO optimized
```

---

## SCOPE

### IN Scope ✅

**Core Features** (what you're building):
- [Feature 1 - e.g., "User authentication with JWT"]
- [Feature 2 - e.g., "Product catalog with search"]
- [Feature 3 - e.g., "Shopping cart and checkout"]

**Technical Capabilities** (what it must do):
- [Capability 1 - e.g., "Handle concurrent requests"]
- [Capability 2 - e.g., "Integrate with payment gateway"]
- [Capability 3 - e.g., "Deploy to cloud (AWS/GCP)"]

### OUT of Scope ❌

**Explicitly NOT included** (scope boundaries):
- ❌ [What you won't build - e.g., "Mobile app (web only)"]
- ❌ [What to avoid - e.g., "Real-time chat (async only)"]
- ❌ [Future features - e.g., "AI recommendations (v2.0)"]

**Example (Python API)**:
```markdown
IN Scope:
- REST API with CRUD operations
- PostgreSQL database integration
- JWT authentication
- Rate limiting (100 req/min)
- Docker deployment

OUT of Scope:
- ❌ GraphQL (REST only)
- ❌ Real-time WebSockets
- ❌ Admin dashboard (API only)
```

---

## CONSTRAINTS

### Technical Stack

**Language & Runtime**:
- Primary: [e.g., Python 3.11+]
- Secondary: [e.g., JavaScript for tooling]

**Frameworks**:
- Web: [e.g., FastAPI, Django, Express, React]
- Testing: [e.g., pytest, Jest, Mocha]
- Database: [e.g., PostgreSQL, MongoDB, Redis]

**Tools**:
- Formatting: [e.g., black, prettier]
- Linting: [e.g., ruff, eslint]
- Type Checking: [e.g., mypy, TypeScript]

**Example (Python ML)**:
```markdown
- Primary: Python 3.11+
- ML Framework: PyTorch 2.0+ or MLX
- Testing: pytest with hypothesis
- Formatting: black (line length 100)
- Type hints: Required on all public APIs
```

### Performance Requirements

**Response Times**:
- API endpoints: [e.g., <100ms p99]
- Database queries: [e.g., <50ms average]
- Page load: [e.g., <2s initial, <500ms navigation]

**Scalability**:
- Concurrent users: [e.g., 10K simultaneous]
- Data volume: [e.g., 10M records]
- Request throughput: [e.g., 1K req/sec]

**Resource Limits**:
- Memory: [e.g., <512MB per instance]
- CPU: [e.g., <50% utilization at peak]
- Storage: [e.g., <10GB for application]

### Development Constraints

**Context Budget** (Autonomous Development):
- Target: <8K tokens per feature
- Strategy: Use session files, clear context with `/clear` after each feature

**Feature Time** (Autonomous Development):
- Simple: 15-25 minutes
- Medium: 30-45 minutes
- Complex: 45-60 minutes

**Test Execution**:
- Unit tests: <30 seconds
- Integration tests: <2 minutes
- Full suite: <5 minutes

### Security Requirements

**Mandatory**:
- ✅ No hardcoded secrets (use .env)
- ✅ Input validation on all user input
- ✅ Output sanitization (prevent XSS)
- ✅ Parameterized queries (prevent SQL injection)
- ✅ HTTPS only (production)

**Coverage**:
- Minimum: 80% test coverage
- Security scans: Run before every commit
- Dependency audits: Weekly

---

## CURRENT SPRINT

**Sprint Name**: [e.g., "Sprint 4: Performance Optimization"]
**GitHub Milestone**: [e.g., "Sprint 4: Performance Optimization"]
**Duration**: [e.g., "2 weeks (Oct 20 - Nov 3)"]
**Status**: [e.g., "In Progress - 60% complete"]

### Sprint Goals

1. [Goal 1 - e.g., "Reduce API latency by 50%"]
2. [Goal 2 - e.g., "Implement caching layer"]
3. [Goal 3 - e.g., "Optimize database queries"]

### Sprint Issues (GitHub)

Track detailed tasks in GitHub Milestone: [Link to milestone]

**Key Issues**:
- #47: [e.g., "Add Redis caching"]
- #51: [e.g., "Optimize user query"]
- #53: [e.g., "Implement connection pooling"]

**Example**:
```markdown
Sprint Name: Sprint 4: Performance Optimization
GitHub Milestone: https://github.com/owner/repo/milestone/4
Duration: 2 weeks (Oct 20 - Nov 3)
Status: In Progress - 60% complete (3/5 issues done)

Sprint Goals:
1. Reduce API latency from 200ms to <100ms
2. Implement Redis caching (5-min TTL)
3. Optimize top 5 slow database queries

Key Issues:
- #47: Add Redis caching ✅ DONE
- #51: Optimize user query ✅ DONE
- #53: Implement connection pooling ✅ DONE
- #55: Cache invalidation strategy ⏳ IN PROGRESS
- #57: Load testing validation ⏸️ TODO
```

---

## STANDARDS & PRACTICES

### Code Quality

**Python**:
```python
# Type hints required
def process_data(input: List[Dict], *, validate: bool = True) -> Result:
    """Process data with validation.

    Args:
        input: List of data dictionaries
        validate: Whether to validate input

    Returns:
        Result object with metrics

    Raises:
        ValueError: If input invalid
    """
    pass

# Formatting: black + isort
# Linting: ruff
# Docstrings: Google style (required for public APIs)
```

**JavaScript/TypeScript**:
```typescript
// TypeScript required for type safety
function processData(input: DataItem[], validate: boolean = true): Result {
  // JSDoc for complex functions
  // Formatting: prettier
  // Linting: eslint
}
```

### Testing Requirements

**TDD (Test-Driven Development)**:
1. Write failing test first
2. Implement minimal code to pass
3. Refactor while keeping tests green

**Coverage Targets**:
- Minimum: 80% overall
- New code: 90%+ preferred
- Critical paths: 100%

**Test Organization**:
```
tests/
├── unit/              # Fast, isolated tests
├── integration/       # Multi-component tests
├── progression/       # Baseline tracking tests
└── regression/        # Bug prevention tests
```

### Documentation

**Required**:
- README.md: Project overview, setup, usage
- CHANGELOG.md: Version history (Keep a Changelog format)
- API docs: All public APIs documented
- Docstrings: All public functions/classes

**Format**:
- Docstrings: Google style (Python), JSDoc (JS/TS)
- Markdown: CommonMark spec
- Examples: Include code examples

### Security

**Secrets Management**:
```bash
# .env file (gitignored)
API_KEY=your_key_here
DATABASE_URL=postgresql://...

# Load in code
import os
api_key = os.getenv("API_KEY")
```

**Input Validation**:
```python
def create_user(email: str) -> User:
    # Validate all input
    if not validate_email(email):
        raise ValueError(f"Invalid email: {email}")

    # Sanitize before storing
    safe_email = sanitize(email)
    return User(email=safe_email)
```

---

## ARCHITECTURE

### Standard Project Structure

**The autonomous-dev automations expect and enforce this structure:**

```
your-project/
├── docs/                     # Project documentation
│   ├── api/                  # API documentation
│   ├── guides/               # User guides
│   └── sessions/             # Agent session logs (auto-created)
├── src/                      # Source code
│   ├── [language-specific]   # e.g., api/, models/, services/ (Python)
│   └── ...                   # e.g., components/, hooks/ (React)
├── tests/                    # All tests
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   ├── uat/                  # User acceptance tests
│   ├── progression/          # Progression tracking (optional)
│   └── regression/           # Regression prevention (optional)
├── scripts/                  # Project automation scripts
├── .claude/
│   ├── PROJECT.md            # This file (project definition)
│   └── settings.local.json   # Local Claude settings (gitignored)
├── .env                      # Environment variables (gitignored)
├── .gitignore
├── README.md
├── CHANGELOG.md
└── [language-specific]       # e.g., pyproject.toml, package.json

```

**What automations expect:**
- ✅ `docs/` - Project docs (README, guides, API docs)
- ✅ `src/` - All source code (language-specific structure inside)
- ✅ `tests/` - All test files (organized by type)
- ✅ `scripts/` - Automation/build scripts
- ✅ `.claude/PROJECT.md` - This file (agents read before every feature)

**What gets auto-created:**
- `docs/sessions/` - Agent session logs (for debugging)
- `tests/progression/` - Baseline tracking tests (optional)
- `tests/regression/` - Bug prevention tests (optional)

**Commands that enforce this structure:**
- `/align-project` - Analyzes and fixes structure violations
- `/sync-docs-organize` - Moves .md files to docs/
- `/auto-implement` - Creates files following this structure

### System Components

**Example (Python API)**:
```
project/
├── src/               # All source code
│   ├── api/          # API endpoints
│   ├── models/       # Data models
│   ├── services/     # Business logic
│   └── utils/        # Utilities
├── tests/            # All tests
├── docs/             # Documentation
└── scripts/          # Automation scripts
```

### Data Flow

```
Client Request
    ↓
API Endpoint (validation)
    ↓
Service Layer (business logic)
    ↓
Data Layer (database)
    ↓
Response (serialization)
    ↓
Client
```

### Agents (Autonomous Development)

**Available**:
- orchestrator: Coordinates team, validates PROJECT.md alignment
- researcher: Finds patterns and best practices
- planner: Creates architecture plans
- test-master: TDD, progression tracking, regression prevention
- implementer: Writes production code
- reviewer: Quality gates
- security-auditor: Vulnerability scanning
- doc-master: Documentation sync

---

## DECISION LOG

**Major Architectural Decisions**:

### Decision 1: [Title]
- **Date**: [YYYY-MM-DD]
- **Decision**: [What was decided]
- **Rationale**: [Why this choice]
- **Alternatives**: [What else was considered]
- **Impact**: [How this affects the project]

**Example**:
```markdown
### Decision 1: Use FastAPI over Flask
- Date: 2024-10-01
- Decision: Use FastAPI for REST API framework
- Rationale: Native async support, automatic OpenAPI docs, type safety
- Alternatives: Flask (simpler but no async), Django (too heavy)
- Impact: All endpoints use async/await, automatic API documentation
```

---

## GETTING STARTED (For Autonomous Development)

### 1. Install Plugin
```bash
cd your-project
/plugin install autonomous-dev
```

### 2. Customize This File
Fill in sections above with **your** project details:
- ✅ Define GOALS (what success means)
- ✅ Define SCOPE (what's included/excluded)
- ✅ Set CONSTRAINTS (tech stack, performance, security)
- ✅ Define CURRENT SPRINT (reference GitHub Milestone)
- ✅ Set STANDARDS (code quality, testing, docs)

### 3. Set Up GitHub (Optional)
```bash
# Create .env with GitHub token
cp plugins/autonomous-dev/.env.example .env
# Edit .env with your GITHUB_TOKEN

# Create GitHub Milestone for current sprint
gh api repos/owner/repo/milestones -f title="Sprint 1"
```

### 4. Align Project
```bash
/align-project
# Brings project structure into alignment with standards above
```

### 5. Start Building
```bash
# Give natural language commands
"implement user authentication with JWT"

# Orchestrator:
# ✅ Reads this PROJECT.md file
# ✅ Validates alignment with GOALS
# ✅ Queries GitHub Milestone (if configured)
# ✅ Coordinates 7-agent dev team
# ✅ Implements with TDD, security, docs
# ✅ Reports detailed progress
```

---

## IMPORTANT NOTES

### PROJECT.md is Your Strategic Direction ⭐

This file defines **WHAT** and **WHY**:
- What you're building (GOALS, SCOPE)
- Why certain choices were made (CONSTRAINTS, STANDARDS)
- What success looks like (Success Metrics)

The autonomous dev team handles **HOW** (execution).

### GitHub is Sprint Execution

GitHub Milestones and Issues handle **tactical details**:
- Sprint planning (issues in milestone)
- Task tracking (issue status)
- Acceptance criteria (issue descriptions)
- Progress monitoring (issue comments)

PROJECT.md (strategic) + GitHub (tactical) = Complete alignment

### Context Management

After each feature:
```bash
/clear
```

This keeps context <8K tokens and enables 100+ features without degradation.

---

**This is a template. Customize it for YOUR project!**

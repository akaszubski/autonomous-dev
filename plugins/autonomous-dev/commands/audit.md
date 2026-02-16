---
name: audit
description: Comprehensive quality audit - code quality, documentation, coverage, security
argument-hint: Optional flags - --quick, --security, --docs, --code, --claude, --tests, --genai
allowed-tools: [Task, Read, Grep, Glob]
---

# Comprehensive Quality Audit

Run automated quality checks and generate a comprehensive report. Catches issues early before they accumulate.

## Implementation

ARGUMENTS: {{ARGUMENTS}}

Parse the ARGUMENTS for optional flags:
- `--quick`: Quick scan (code quality only)
- `--security`: Security-focused audit only
- `--docs`: Documentation alignment only
- `--code`: Code quality scan only
- `--claude`: CLAUDE.md structure validation (runs `validate_project_alignment.py`)
- `--tests`: Test coverage analysis (invokes test-coverage-auditor agent with AST analysis)
- `--genai`: GenAI UAT test audit — retrofit or expand LLM-as-judge tests

If no flags provided, run full audit (all categories).

Invoke the quality-validator agent to analyze code patterns (bare except, print statements, broad exceptions).

Invoke the doc-master agent to validate documentation consistency (component counts, cross-references, drift detection).

Invoke the test-coverage-auditor agent to analyze test coverage (module coverage, gaps, uncovered code).

Invoke the security-auditor agent to scan for vulnerabilities (hardcoded secrets, shell=True, path traversal, OWASP checks).

### --genai flag: GenAI UAT Retrofit & Audit

When `--genai` is passed (or as part of full audit), perform GenAI test analysis:

**STEP 1: Detect GenAI infrastructure**
Check if `tests/genai/conftest.py` exists.

- **If missing**: Run `/scaffold-genai-uat` to bootstrap the infrastructure (conftest.py, doc tests, congruence tests). Then continue to STEP 2.
- **If exists**: Proceed to STEP 2.

**STEP 2: Discover functional test gaps**
Use an Explore agent to scan the codebase and identify what SHOULD have GenAI functional tests but doesn't:

| Scan For | Test Category | Example Test |
|----------|--------------|--------------|
| API routes (`**/routes/*.py`, `**/views.py`) | API quality | Error messages helpful, schemas consistent |
| Config files (`**/config*.py`, `**/*_config.py`) | Config sanity | Defaults reasonable, ranges valid |
| Schema/model files (`**/schemas/*.py`, `**/models.py`) | Schema quality | Types sensible, required fields present |
| Business logic (`**/engine*.py`, `**/service*.py`) | Domain correctness | Rules make sense, edge cases handled |
| Validators (`**/valid*.py`) | Validation quality | Error messages clear, rules complete |

**STEP 3: Generate functional tests**
For each gap found, invoke test-master agent to write GenAI functional tests in `tests/genai/test_<category>.py`. Tests must use the hybrid pattern:
1. Deterministic extraction (grep/regex/AST)
2. GenAI semantic judgment via `genai.judge()`

**STEP 4: Run and validate**
```bash
GENAI_TESTS=true pytest tests/genai/ -v --no-cov 2>&1 | tail -20
```
Report: total tests, pass/fail, any flaky tests that need threshold tuning.

Use the doc-master agent to compile all findings into a report at `docs/sessions/AUDIT_REPORT_<timestamp>.md`

---

## What This Does

| Category | Agent | Checks |
|----------|-------|--------|
| Code Quality | quality-validator | Bare excepts, print statements, broad exceptions |
| Documentation | doc-master | Component counts, cross-refs, drift |
| Test Coverage | test-coverage-auditor | Module coverage, gaps |
| Security | security-auditor | Secrets, shell=True, path traversal |
| GenAI UAT | test-master | Functional semantic tests, config/API/domain validation |

**Time**:
- Full audit: 5-10 minutes
- Quick scan: ~2 minutes
- Single category: 2-3 minutes

---

## Usage

```bash
# Full comprehensive audit
/audit

# Quick code quality scan only
/audit --quick

# Security-focused audit
/audit --security

# Documentation alignment only
/audit --docs

# Code quality scan only
/audit --code

# CLAUDE.md structure validation (replaces /audit-claude)
/audit --claude

# Test coverage analysis (replaces /audit-tests)
/audit --tests
/audit --tests --layer unit

# GenAI UAT retrofit - scaffold + generate functional tests
/audit --genai
```

---

## Output

Generates a report at `docs/sessions/AUDIT_REPORT_<timestamp>.md`

The report includes:
- Summary table with pass/warn/fail status per category
- Detailed findings with file:line references
- Severity ratings (low, medium, high, critical)
- Prioritized recommendations for fixing issues

---

## Prevention Value

Regular audits prevent:
- Accumulation of print statements (catch early at 50)
- Technical debt from bare except clauses
- Security vulnerabilities going unnoticed
- Documentation drift from reality

**Recommendation**: Run weekly on main branch, quick scan on every PR.

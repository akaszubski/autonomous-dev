---
name: audit
description: Comprehensive quality audit - code quality, documentation, coverage, security
argument-hint: Optional flags - --quick, --security, --docs, --code, --claude, --tests
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
- `--claude`: CLAUDE.md structure validation (runs `audit_claude_structure.py`)
- `--tests`: Test coverage analysis (invokes test-coverage-auditor agent with AST analysis)

If no flags provided, run full audit (all categories).

Invoke the quality-validator agent to analyze code patterns (bare except, print statements, broad exceptions).

Invoke the doc-master agent to validate documentation consistency (component counts, cross-references, drift detection).

Invoke the test-coverage-auditor agent to analyze test coverage (module coverage, gaps, uncovered code).

Invoke the security-auditor agent to scan for vulnerabilities (hardcoded secrets, shell=True, path traversal, OWASP checks).

Use the doc-master agent to compile all findings into a report at `docs/sessions/AUDIT_REPORT_<timestamp>.md`

---

## What This Does

| Category | Agent | Checks |
|----------|-------|--------|
| Code Quality | quality-validator | Bare excepts, print statements, broad exceptions |
| Documentation | doc-master | Component counts, cross-refs, drift |
| Test Coverage | test-coverage-auditor | Module coverage, gaps |
| Security | security-auditor | Secrets, shell=True, path traversal |

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

---
name: audit
description: Comprehensive quality audit - code quality, documentation, coverage, security
argument-hint: Optional flags - --quick, --security, --docs, --code
allowed-tools: [Task, Bash, Glob, Grep, Read]
---

# Comprehensive Quality Audit

Run automated quality checks and generate a comprehensive report. Catches issues early before they accumulate.

## Implementation

ARGUMENTS: {{ARGUMENTS}}

Parse the ARGUMENTS for optional flags:
- `--quick`: Quick scan (code quality only, ~2 minutes)
- `--security`: Security-focused audit only
- `--docs`: Documentation alignment only
- `--code`: Code quality scan only

If no flags provided, run full audit (all categories).

### Audit Process

Run the following audit categories based on flags:

**1. Code Quality Scan** (always unless --docs or --security only):

Use Bash to run these checks:

```bash
# Count bare except clauses
grep -r "except:" --include="*.py" plugins/autonomous-dev/lib plugins/autonomous-dev/hooks | grep -v "except Exception" | grep -v "except [A-Z]" | wc -l

# Count print statements in production code (excluding tests)
grep -r "print(" --include="*.py" plugins/autonomous-dev/lib plugins/autonomous-dev/hooks | grep -v "tests/" | wc -l

# Count broad exception catches
grep -r "except Exception:" --include="*.py" plugins/autonomous-dev/ | wc -l
```

**2. Documentation Alignment** (unless --security or --code only):

Use Bash to run validation:
```bash
# Check component counts
python3 plugins/autonomous-dev/hooks/validate_component_counts.py 2>&1 || true

# Check hooks documented
python3 plugins/autonomous-dev/hooks/validate_hooks_documented.py 2>&1 || true
```

**3. Test Coverage Analysis** (unless --quick, --docs, or --security):

Use Bash to get coverage:
```bash
# Run quick coverage check
python3 -m pytest plugins/autonomous-dev/tests --cov=plugins/autonomous-dev --cov-report=term-missing --cov-fail-under=0 -q 2>&1 | tail -20
```

**4. Security Scan** (unless --quick, --docs, or --code):

Use Bash to run security checks:
```bash
# Check for hardcoded secrets patterns
grep -rE "(api_key|secret|password|token)\s*=\s*['\"][^'\"]+['\"]" --include="*.py" plugins/autonomous-dev/ | grep -v "test" | grep -v "#" | head -10 || echo "No hardcoded secrets found"

# Check for shell=True usage
grep -r "shell=True" --include="*.py" plugins/autonomous-dev/ | grep -v "tests/" || echo "No shell=True usage found"

# Check for path traversal risks
grep -rE "os\.path\.join.*\.\." --include="*.py" plugins/autonomous-dev/ | head -5 || echo "No obvious path traversal risks"
```

### Generate Report

After running checks, generate a summary report in markdown format.

Create report file at: `docs/sessions/AUDIT_REPORT_$(date +%Y%m%d_%H%M%S).md`

Report format:
```markdown
# Quality Audit Report

**Date**: [timestamp]
**Mode**: [full/quick/security/docs/code]

## Summary

| Category | Status | Issues |
|----------|--------|--------|
| Code Quality | [PASS/WARN/FAIL] | [count] |
| Documentation | [PASS/WARN/FAIL] | [count] |
| Test Coverage | [X%] | [uncovered modules] |
| Security | [PASS/WARN/FAIL] | [count] |

## Code Quality

### Bare Except Clauses
[count] found
[list if > 0]

### Print Statements
[count] in production code
[recommendation if > 50]

### Broad Exception Catches
[count] found

## Documentation Alignment

[validation results]

## Test Coverage

[coverage percentage]
[uncovered modules]

## Security

[findings]

## Recommendations

1. [priority recommendations based on findings]
```

## What This Does

Performs comprehensive quality auditing:

1. **Code Quality**: Detects bare excepts, print statements, broad exceptions
2. **Documentation**: Validates component counts, cross-references, hook docs
3. **Test Coverage**: Analyzes module coverage and gaps
4. **Security**: Scans for hardcoded secrets, shell=True, path traversal

**Time**:
- Full audit: 5-10 minutes
- Quick scan: ~2 minutes
- Single category: 2-3 minutes

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
```

## Output

Generates a report at `docs/sessions/AUDIT_REPORT_<timestamp>.md`

The report includes:
- Summary table with pass/warn/fail status per category
- Detailed findings with file:line references
- Severity ratings (low, medium, high, critical)
- Prioritized recommendations for fixing issues

## Prevention Value

Regular audits prevent:
- Accumulation of 726+ print statements (caught early at 50)
- Technical debt from 18+ bare except clauses
- Security vulnerabilities going unnoticed
- Documentation drift from reality

**Recommendation**: Run weekly on main branch, quick scan on every PR.

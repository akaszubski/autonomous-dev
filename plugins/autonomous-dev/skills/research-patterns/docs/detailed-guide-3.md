# Research Patterns - Detailed Guide

## OWASP Top 10 Analysis

**Relevant OWASP risks for this feature**:

1. **{OWASP Risk}**: {How it applies}
   - Mitigation: {How we prevent it}

2. **{OWASP Risk}**: {How it applies}
   - Mitigation: {How we prevent it}

## Security Checklist

**Before deployment, verify**:

- [ ] Input validation (all user inputs sanitized)
- [ ] Authentication (only authorized users)
- [ ] Authorization (proper permission checks)
- [ ] Encryption (data at rest + in transit)
- [ ] Logging (security events logged)
- [ ] Rate limiting (prevent abuse)
- [ ] Error handling (no sensitive info leakage)
- [ ] Dependencies (no known vulnerabilities)
- [ ] Secret management (no hardcoded secrets)
- [ ] Security headers (CSP, HSTS, etc.)

## Secure Code Examples

**✅ Secure**:
```python
# Example of secure implementation
```

**❌ Insecure**:
```python
# Example of what NOT to do
```

## Compliance Requirements

**Applicable standards**:
- GDPR: {Relevant requirements}
- OWASP: {Relevant guidelines}
- SOC 2: {Relevant controls}

## Penetration Testing Plan

**Tests to run**:
1. {Test name}: {What to test}
2. {Test name}: {What to test}
3. {Test name}: {What to test}
```

---

## Research Quality Gates

**Before marking research as complete, verify**:

### Completeness Gates

- [ ] **Research question clearly defined**
- [ ] **Codebase searched first** (Grep + Glob + Read)
- [ ] **External research performed** (3-5 WebSearch queries)
- [ ] **Top sources fetched** (5+ WebFetch calls)
- [ ] **Findings documented** (follows template)
- [ ] **Sources evaluated** (quality ratings assigned)
- [ ] **Next steps provided** (actionable recommendations)

### Quality Gates

- [ ] **Code examples included** (not just theory)
- [ ] **Security considered** (if applicable)
- [ ] **Performance analyzed** (if applicable)
- [ ] **Tradeoffs documented** (pros and cons)
- [ ] **Integration points identified** (where it fits in codebase)
- [ ] **Tests recommended** (what to test)
- [ ] **Sources are recent** (2024-2025 preferred)

### Clarity Gates

- [ ] **Executive summary is clear** (2-3 sentences)
- [ ] **Recommendation is specific** (not vague)
- [ ] **Implementation steps are detailed** (can follow without questions)
- [ ] **Pitfalls are concrete** (specific mistakes to avoid)
- [ ] **Next steps are actionable** (can start immediately)

**If any gate fails, research is NOT complete.**

---

## Common Research Anti-Patterns

### ❌ Anti-Pattern 1: Skipping Codebase Search

**Problem**: Researching external patterns without checking if we already have a solution.

**Why Bad**: Reinventing the wheel, inconsistent patterns, wasted time.

**Solution**: ALWAYS search codebase first with Grep + Glob + Read.

### ❌ Anti-Pattern 2: Using Outdated Sources

**Problem**: Relying on tutorials from 2019-2020.

**Why Bad**: Outdated practices, deprecated APIs, security vulnerabilities.

**Solution**: Prioritize 2024-2025 sources. If using older sources, verify they're still current.

### ❌ Anti-Pattern 3: Theory Without Examples

**Problem**: Findings describe patterns but don't show code.

**Why Bad**: Implementer can't translate theory to code without guessing.

**Solution**: Always include multiple code examples with context.

### ❌ Anti-Pattern 4: No Tradeoff Analysis

**Problem**: Recommending one approach without explaining alternatives.

**Why Bad**: Reader doesn't understand WHY this is best for our use case.

**Solution**: Compare at least 2-3 alternatives with pros/cons table.

### ❌ Anti-Pattern 5: Ignoring Security

**Problem**: Researching implementation without security considerations.

**Why Bad**: Vulnerable code gets deployed, security issues discovered later.

**Solution**: Always include security section, even if just "N/A - not security-sensitive".

### ❌ Anti-Pattern 6: Vague Next Steps

**Problem**: "Research complete, proceed with implementation" without specific actions.

**Why Bad**: Implementer doesn't know what files to create or what to do first.

**Solution**: Provide specific, numbered next steps with file names.

---

## Integration with Autonomous Architecture

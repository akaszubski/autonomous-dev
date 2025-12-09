# Semantic Validation - Detailed Guide

## Limitations

**What this skill CAN'T detect**:
- Subtly incorrect explanations (if code exists)
- Performance claims (needs profiling)
- Scalability assertions (needs load testing)
- Security vulnerabilities (use security-auditor skill)

**Workarounds**:
- Performance: Use observability skill
- Security: Use security-patterns skill
- Scalability: Manual review + load testing

---

## Integration with /align-project

This skill is Phase 2 of `/align-project`:

**Phase 1**: Structural validation (files exist, directories correct)
**Phase 2**: Semantic validation (THIS SKILL - docs match reality)
**Phase 3**: Documentation currency (separate skill)
**Phase 4**: Cross-reference validation (separate skill)

**Invocation**:
```bash
/align-project
# After Phase 1 completes, Phase 2 runs automatically
# User sees combined report from all phases
```

---

## Output to User

Always provide:
1. **Severity levels** (CRITICAL, HIGH, MEDIUM, LOW)
2. **Evidence** (file:line references, commit SHAs)
3. **Suggested fixes** (exact text to replace)
4. **Priority ordering** (what to fix first)
5. **Auto-fix availability** (YES/NO for each issue)

Never:
- Claim something is wrong without evidence
- Provide vague suggestions ("update docs")
- Skip severity assessment
- Omit actionable fixes

---

**This skill transforms documentation validation from structural checking to semantic understanding, catching issues humans miss.**

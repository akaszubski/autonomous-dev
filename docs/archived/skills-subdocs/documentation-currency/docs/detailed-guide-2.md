# Documentation Currency - Detailed Guide

## Success Criteria

After running documentation currency check:
- ✅ All status markers validated against age thresholds
- ✅ Version references checked for currency
- ✅ "Coming soon" claims verified (implemented, cancelled, or active)
- ✅ "Last Updated" dates match git history
- ✅ Broken references detected and reported
- ✅ Completes in < 20 seconds for medium projects

---

## Integration with /align-project

This is **Phase 3** of `/align-project`:

**Phase 1**: Structural validation
**Phase 2**: Semantic validation
**Phase 3**: Documentation currency (THIS SKILL)
**Phase 4**: Cross-reference validation

---

## Automation Triggers

**Auto-run when**:
- `/align-project` command
- Before major releases
- Monthly scheduled check (if configured)

**Alert thresholds**:
- CRITICAL markers > 30 days old
- TODOs > 90 days old
- "Coming soon" > 180 days old
- Version lag > 1 major version

---

**This skill ensures documentation doesn't rot over time, keeping project docs trustworthy and current.**

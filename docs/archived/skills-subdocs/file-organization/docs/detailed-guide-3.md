# File Organization - Detailed Guide

## Success Criteria

After implementation:
- ✅ Claude cannot create files in wrong locations (blocked or auto-fixed)
- ✅ Pre-commit catches any files that slip through
- ✅ Auto-fix moves files to correct locations with explanation
- ✅ Documentation references auto-updated after file moves
- ✅ Root directory stays clean (max 8 .md files)
- ✅ Audit trail of all auto-corrections

---

## Performance

**Fast validation**:
- Rule parsing: < 10ms (cached)
- Path validation: < 5ms per file
- Auto-fix: < 50ms (includes directory creation)

**Total overhead**: < 100ms per file operation

---

**This skill prevents file organization debt by enforcing standards at creation time, eliminating manual cleanup.**

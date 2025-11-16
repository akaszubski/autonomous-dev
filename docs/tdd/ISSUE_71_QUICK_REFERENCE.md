# Issue #71 Quick Reference Card

**Feature**: Fix verify_parallel_exploration() Task tool agent detection
**Status**: TDD Red Phase Complete ✅
**Next Agent**: implementer

---

## 📋 Test Status

```
✅ Unit Tests: 21 tests written (WILL FAIL)
✅ Integration Tests: 12 tests written (WILL FAIL)
✅ Total: 33 tests (1,543 lines of test code)
✅ Methods verified as NOT existing (TDD red phase confirmed)
```

---

## 🎯 What to Implement (5 Methods)

1. `_validate_agent_data(agent_data: Dict) -> bool`
2. `_get_session_text_file() -> Optional[str]`
3. `_detect_agent_from_session_text(agent_name: str, session_text_path: str) -> Optional[Dict]`
4. `_detect_agent_from_json_structure(agent_name: str) -> Optional[Dict]`
5. Enhanced `_find_agent(agent_name: str) -> Optional[Dict]` (modify existing)

**File to Edit**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/agent_tracker.py`

---

## 🚀 Quick Start

### 1. Verify Tests Fail (TDD Red)
```bash
python -m pytest tests/unit/test_verify_parallel_exploration_task_tool.py -v
# Expected: 21 failures (methods don't exist yet)
```

### 2. Read Implementation Guide
```bash
cat tests/ISSUE_71_IMPLEMENTATION_GUIDE.md
# Contains step-by-step instructions, code hints, common pitfalls
```

### 3. Implement Methods (Order Matters!)
```
Priority 1: _validate_agent_data() → _get_session_text_file()
Priority 2: _detect_agent_from_session_text() → _detect_agent_from_json_structure()
Priority 3: Enhanced _find_agent()
```

### 4. Test After Each Method
```bash
pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestDataValidation -v
pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestSessionTextParser -v
pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestJSONStructureAnalyzer -v
pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestEnhancedFindAgent -v
```

### 5. Verify All Pass (TDD Green)
```bash
pytest tests/unit/test_verify_parallel_exploration_task_tool.py \
  tests/integration/test_parallel_exploration_task_tool_end_to_end.py -v
# Expected: 33 passing (all green)
```

---

## 📊 Success Criteria

### Must Pass:
- ✅ All 33 tests pass (100% green)
- ✅ No regressions (existing tests pass)
- ✅ Performance: < 100ms overhead, < 50ms parsing
- ✅ Security: Path traversal blocked
- ✅ Coverage: > 80%

---

## 📚 Documentation Files

1. **Implementation Guide** (detailed step-by-step)
   - Path: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/ISSUE_71_IMPLEMENTATION_GUIDE.md`
   - Contains: Code hints, testing strategy, common pitfalls, security checklist

2. **TDD Red Complete** (test documentation)
   - Path: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/ISSUE_71_TDD_RED_COMPLETE.md`
   - Contains: Test coverage details, method specs, verification commands

3. **Summary** (executive overview)
   - Path: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/ISSUE_71_TDD_RED_SUMMARY.md`
   - Contains: Problem statement, solution design, next steps

4. **Quick Reference** (this file)
   - Path: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/ISSUE_71_QUICK_REFERENCE.md`
   - Contains: Quick commands, cheat sheet

---

## ⏱️ Time Estimate

- Helper Methods: 30 min
- Detection Methods: 1.5 hours
- Integration: 30 min
- Testing/Debug: 1 hour
- Docs/Review: 30 min

**Total**: ~4 hours

---

## 🔍 Debugging Commands

### Check Method Exists
```bash
python -c "import sys; sys.path.insert(0, 'plugins/autonomous-dev/lib'); \
  from scripts.agent_tracker import AgentTracker; \
  tracker = AgentTracker(); \
  print('Has method:', hasattr(tracker, '_validate_agent_data'))"
```

### Run Single Test
```bash
pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestSessionTextParser::test_valid_completion_marker_returns_agent_data -v
```

### Check Coverage
```bash
pytest tests/unit/test_verify_parallel_exploration_task_tool.py --cov=scripts.agent_tracker --cov-report=term-missing
```

---

## 🛡️ Security Checklist

- ✅ Use `validate_path()` for all file paths
- ✅ Catch `JSONDecodeError` for corrupted files
- ✅ Check file existence before reading
- ✅ Validate timestamp format (try/except)
- ✅ Audit log all operations

---

## ⚡ Performance Targets

- **Multi-method detection**: < 100ms
- **Session text parsing**: < 50ms
- **Short-circuit evaluation**: Tracker method only (no fallback)

---

## 🎓 Key Concepts

### Multi-Method Detection Priority
1. **Tracker** (fastest, 99% of cases)
2. **JSON** (external modifications)
3. **Text** (Task tool agents)

### Short-Circuit Evaluation
- Return as soon as agent found
- Don't check all methods unnecessarily

### Graceful Degradation
- Catch exceptions → return None
- Don't crash on missing/corrupted files

---

## 📞 Need Help?

- Read Implementation Guide first (most comprehensive)
- Check test files for expected behavior
- Run single test to debug specific issue
- Check existing `_find_agent()` method for patterns

---

**Ready to Implement?** Start with: `tests/ISSUE_71_IMPLEMENTATION_GUIDE.md`

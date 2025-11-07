# GitHub Issue #46 - TDD Quick Reference

**Date**: 2025-11-08
**Status**: Red Phase Complete (Tests written, ready for implementation)

---

## Quick Start

### Verify TDD Red Phase
```bash
python tests/verify_issue46_tdd_red.py
```

**Expected output**: All 4 test files verified, tests should FAIL (red phase)

---

## Test Files

| Phase | File | Tests | Status |
|-------|------|-------|--------|
| Phase 4 | `tests/unit/test_pipeline_phase4_model_optimization.py` | 15 | Red (failing) |
| Phase 5 | `tests/unit/test_pipeline_phase5_prompt_simplification.py` | 19 | Red (failing) |
| Phase 6 Unit | `tests/unit/lib/test_performance_profiler.py` | 22 | Red (failing) |
| Phase 6 Integration | `tests/integration/test_performance_profiling_integration.py` | 22 | Red (failing) |
| **Total** | **4 files** | **78 tests** | **Red (ready for implementation)** |

---

## Running Tests

### Install Dependencies (if needed)
```bash
pip install pytest pytest-cov pyyaml
```

### Run All Phase 4 Tests
```bash
pytest tests/unit/test_pipeline_phase4_model_optimization.py -v
```

**Expected**: 15 failures (researcher still uses sonnet, not haiku)

### Run All Phase 5 Tests
```bash
pytest tests/unit/test_pipeline_phase5_prompt_simplification.py -v
```

**Expected**: 19 failures (prompts not yet simplified)

### Run All Phase 6 Unit Tests
```bash
pytest tests/unit/lib/test_performance_profiler.py -v
```

**Expected**: 22 failures (performance_profiler.py doesn't exist)

### Run All Phase 6 Integration Tests
```bash
pytest tests/integration/test_performance_profiling_integration.py -v
```

**Expected**: 22 failures (profiling not integrated)

### Run All Tests for Issue #46
```bash
pytest tests/unit/test_pipeline_phase4_model_optimization.py \
       tests/unit/test_pipeline_phase5_prompt_simplification.py \
       tests/unit/lib/test_performance_profiler.py \
       tests/integration/test_performance_profiling_integration.py \
       -v
```

**Expected**: 78 failures (red phase complete)

---

## Test Coverage by Phase

### Phase 4: Model Optimization (15 tests)
1. **Model Configuration** (3 tests)
   - researcher uses haiku model
   - other agents unaffected
   - model change documented

2. **Quality Maintenance** (3 tests)
   - WebSearch capability preserved
   - prompt maintains quality standards
   - skills integration unchanged

3. **Performance Baseline** (3 tests)
   - 25-39 min baseline documented in CLAUDE.md
   - performance expectations realistic
   - Phase 4 tracked in PROJECT.md

4. **Integration** (3 tests)
   - researcher invocation uses haiku
   - output format unchanged
   - haiku model available

5. **Regression Prevention** (3 tests)
   - 7-agent workflow complete
   - checkpoint validation enforced
   - parallel validation unaffected

### Phase 5: Prompt Simplification (19 tests)
1. **Researcher Simplification** (4 tests)
   - 50-60 lines (from 99)
   - essential sections preserved
   - redundant content removed
   - WebSearch guidance preserved

2. **Planner Simplification** (4 tests)
   - 70-80 lines (from 119)
   - essential sections preserved
   - strategic planning guidance preserved
   - opus model unchanged

3. **Quality Preservation** (4 tests)
   - skills references preserved
   - PROJECT.md still referenced
   - security focus maintained

4. **Performance Baseline** (3 tests)
   - 22-36 min baseline (2-3 min savings)
   - cumulative savings documented
   - Phase 5 tracked in PROJECT.md

5. **Regression Prevention** (3 tests)
   - agents still functional
   - workflow unchanged
   - 7 agents + parallel validation preserved

6. **Helper Utilities** (1 test)
   - line count validation helper

### Phase 6: Profiling Infrastructure (44 tests)

**Unit Tests** (22 tests):
1. **Timer Functionality** (5 tests)
   - context manager interface
   - duration accuracy (within 10ms)
   - metadata capture (agent, feature, timestamp)
   - exception handling

2. **Metrics Logging** (3 tests)
   - JSON log file writes
   - JSON format (all fields)
   - newline-delimited JSON (NDJSON)

3. **Aggregation** (4 tests)
   - calculate min/max/avg/p95
   - single sample edge case
   - empty list edge case
   - aggregate by agent

4. **Overhead** (2 tests)
   - timer overhead <5%
   - buffered I/O for performance

5. **Concurrency** (2 tests)
   - concurrent writes safe
   - log rotation supported

6. **Edge Cases** (4 tests)
   - negative duration handling
   - logs directory auto-created
   - corrupted log gracefully handled
   - long feature descriptions truncated

7. **Reporting** (2 tests)
   - summary report generation
   - bottleneck identification

**Integration Tests** (22 tests):
1. **Auto-Implement Integration** (4 tests)
   - profiling documented in auto-implement.md
   - all 7 agents wrapped with timers
   - timers wrap agent invocations correctly
   - duration captured on success/failure

2. **Workflow Aggregation** (3 tests)
   - metrics aggregated after workflow
   - summary displayed to user
   - total time includes wall-clock + CPU time

3. **Overhead** (2 tests)
   - end-to-end overhead <5%
   - writes don't block execution

4. **Error Handling** (3 tests)
   - profiling failure doesn't stop workflow
   - corrupted log handled gracefully
   - missing metrics handled gracefully

5. **Parallel Profiling** (2 tests)
   - parallel agents profiled individually
   - parallel time not double-counted

6. **Documentation** (3 tests)
   - CLAUDE.md documents profiling
   - PROJECT.md tracks Phase 6
   - lib/README.md documents API

7. **Regression Prevention** (3 tests)
   - all 7 agents still run
   - parallel validation preserved
   - checkpoint validation unchanged

8. **Visualization** (2 tests, optional)
   - CSV export capability
   - trend analysis support

---

## Expected Failure Messages

### Phase 4
```
AssertionError: Researcher should use haiku model, got: sonnet
```

### Phase 5
```
AssertionError: Researcher prompt should be 50-60 lines, got 99 lines
AssertionError: Planner prompt should be 70-80 lines, got 119 lines
```

### Phase 6
```
ModuleNotFoundError: No module named 'plugins.autonomous_dev.lib.performance_profiler'
```

---

## Implementation Checklist

### Phase 4 (30-45 minutes)
- [ ] Update `researcher.md` frontmatter: `model: haiku`
- [ ] Document change in researcher.md body
- [ ] Update CLAUDE.md: Phase 4 baseline 25-39 min
- [ ] Update PROJECT.md: Track Phase 4 completion
- [ ] Run tests: All 15 should PASS

### Phase 5 (45-60 minutes)
- [ ] Simplify `researcher.md` to 50-60 lines
- [ ] Simplify `planner.md` to 70-80 lines
- [ ] Update CLAUDE.md: Phase 5 baseline 22-36 min
- [ ] Update PROJECT.md: Track Phase 5 completion
- [ ] Run tests: All 19 should PASS

### Phase 6 (90-120 minutes)
- [ ] Implement `performance_profiler.py` library
  - [ ] `PerformanceTimer` class
  - [ ] `calculate_aggregate_metrics()`
  - [ ] `aggregate_by_agent()`
  - [ ] `generate_summary_report()`
  - [ ] `load_metrics_from_log()`
- [ ] Integrate profiling in `auto-implement.md`
- [ ] Update `lib/README.md`: Document API
- [ ] Update CLAUDE.md: Document profiling
- [ ] Update PROJECT.md: Track Phase 6 completion
- [ ] Run tests: All 44 should PASS

---

## Success Criteria

### Current Status: Red Phase ✅
- [x] 78 tests written
- [x] All tests should FAIL
- [x] Tests are comprehensive
- [x] Tests follow TDD best practices

### Next: Green Phase
- [ ] Phase 4: 15/15 tests pass (model optimization)
- [ ] Phase 5: 19/19 tests pass (prompt simplification)
- [ ] Phase 6: 44/44 tests pass (profiling infrastructure)
- [ ] Total: 78/78 tests pass

### Final: Refactor Phase
- [ ] Code optimized while tests still pass
- [ ] Coverage reports show 80%+ coverage
- [ ] Performance validated (overhead <5%)

---

## Key Files

### Test Files
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/test_pipeline_phase4_model_optimization.py`
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/test_pipeline_phase5_prompt_simplification.py`
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/lib/test_performance_profiler.py`
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/integration/test_performance_profiling_integration.py`

### Implementation Targets
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/researcher.md` (Phase 4, 5)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/agents/planner.md` (Phase 5)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/performance_profiler.py` (Phase 6 - NEW)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/commands/auto-implement.md` (Phase 6)

### Documentation
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md` (all phases)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/.claude/PROJECT.md` (all phases)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/README.md` (Phase 6)

---

## Useful Commands

### Run single test
```bash
pytest tests/unit/test_pipeline_phase4_model_optimization.py::TestResearcherModelConfiguration::test_researcher_uses_haiku_model -v
```

### Run with coverage
```bash
pytest tests/unit/test_pipeline_phase4_model_optimization.py --cov=plugins.autonomous_dev.agents --cov-report=term-missing
```

### Run and stop on first failure
```bash
pytest tests/unit/test_pipeline_phase4_model_optimization.py -x
```

### Run with detailed output
```bash
pytest tests/unit/test_pipeline_phase4_model_optimization.py -vv -s
```

### Verify test structure only (no execution)
```bash
pytest tests/unit/test_pipeline_phase4_model_optimization.py --collect-only
```

---

**Date**: 2025-11-08
**Agent**: test-master
**Status**: Ready for implementation (green phase)

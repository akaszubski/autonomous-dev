# Issue #72 TDD Quick Reference

## Current Status: RED PHASE ✅

All tests written and failing as expected. Ready for implementation.

---

## Quick Commands

### Verify Red Phase
```bash
python tests/verify_issue72_tdd_red.py
```

Expected output: All tests FAIL (red phase verified)

### Run All Issue #72 Tests
```bash
pytest tests/unit/test_agent_output_cleanup_*.py \
       tests/integration/test_agent_output_cleanup_*.py -v
```

### Run Specific Test Categories
```bash
# Token counting tests
pytest tests/unit/test_agent_output_cleanup_token_counting.py -v

# Skill reference tests
pytest tests/unit/test_agent_output_cleanup_skill_references.py -v

# Section length tests
pytest tests/unit/test_agent_output_cleanup_section_length.py -v

# Agent output quality tests (integration)
pytest tests/integration/test_agent_output_cleanup_quality.py -v

# Documentation accuracy tests
pytest tests/unit/test_agent_output_cleanup_documentation.py -v
```

---

## Test File Locations

```
tests/
├── unit/
│   ├── test_agent_output_cleanup_token_counting.py (32 tests)
│   ├── test_agent_output_cleanup_skill_references.py (27 tests)
│   ├── test_agent_output_cleanup_section_length.py (23 tests)
│   └── test_agent_output_cleanup_documentation.py (25 tests)
├── integration/
│   └── test_agent_output_cleanup_quality.py (30 tests)
├── ISSUE_72_TDD_RED_SUMMARY.md (this file)
├── ISSUE_72_TEST_FILES.txt (file listing)
└── verify_issue72_tdd_red.py (verification script)
```

---

## TDD Workflow

### Current Phase: RED ✅
- [x] Write failing tests FIRST
- [x] Verify all tests fail
- [x] Document test coverage

### Next Phase: GREEN (for implementer)
- [ ] Create token measurement scripts
- [ ] Implement Phase 1: Add skill references (5 agents)
- [ ] Implement Phase 2: Streamline output formats
- [ ] Run tests - all should PASS
- [ ] Update documentation

### Final Phase: REFACTOR (for reviewer)
- [ ] Review code quality
- [ ] Optimize token counting logic
- [ ] Add error handling
- [ ] Verify documentation accuracy

---

## Key Test Assertions

### Token Counting
```python
# Script exists
assert script_path.exists()

# Measures baseline correctly
baseline = measure_baseline_tokens()
assert len(baseline) == 20  # 20 agents

# Calculates savings
savings = calculate_token_savings(baseline, post_cleanup)
assert savings["total_saved"] >= 1500  # Minimum target
```

### Skill References
```python
# All agents have Relevant Skills section
assert "## Relevant Skills" in agent_content

# Phase 1 agents have skill reference
assert "agent-output-formats" in agent_content

# Existing skills preserved
assert "testing-guide" in agent_content  # Example
```

### Section Length
```python
# No agent exceeds 30-line threshold
line_count = count_output_format_lines(agent_file)
assert line_count <= 30

# Agent-specific guidance preserved
assert "dual-mode" in content or "YAML" in content  # Example
```

---

## Expected Token Savings

| Phase | Target | Approach |
|-------|--------|----------|
| Phase 1 | ~200 tokens | Add skill references to 5 agents |
| Phase 2 | ~1,300-3,800 tokens | Streamline verbose Output Format sections |
| **Total** | **1,500-4,000 tokens** | **8-15% reduction** |

---

## Implementation Checklist

### Scripts to Create
- [ ] `scripts/measure_agent_tokens.py` - Token counting
- [ ] `scripts/measure_output_format_sections.py` - Section analysis
- [ ] `scripts/identify_verbose_agents.py` - Cleanup candidates
- [ ] `scripts/track_cleanup_progress.py` - Before/after tracking
- [ ] `scripts/verify_token_claims.py` - Documentation verification
- [ ] `scripts/validate_agent_skill_references.py` - Skill reference validation
- [ ] `scripts/cleanup_output_formats.py` - Automated cleanup (optional)

### Agents to Update (Phase 1)
- [ ] test-master - Add agent-output-formats reference
- [ ] quality-validator - Add agent-output-formats reference
- [ ] advisor - Add agent-output-formats reference
- [ ] alignment-validator - Add agent-output-formats reference
- [ ] project-progress-tracker - Add agent-output-formats reference

### Agents to Streamline (Phase 2)
- [ ] project-progress-tracker - Reduce Output Format to ≤30 lines
- [ ] quality-validator - Streamline if needed
- [ ] Any agent with >30 lines in Output Format section

### Documentation to Update
- [ ] CLAUDE.md - Add Issue #72 details, token savings
- [ ] CHANGELOG.md - Add entry for v3.15.0
- [ ] Save baseline measurements to `docs/metrics/baseline_tokens.json`
- [ ] Save post-cleanup to `docs/metrics/post_cleanup_tokens.json`

---

## Success Criteria

### Tests
- ✅ All 137 tests pass
- ✅ No test is skipped or xfailed
- ✅ Test coverage ≥80% for new code

### Token Savings
- ✅ Total savings: 1,500-4,000 tokens
- ✅ Baseline measurements saved
- ✅ Post-cleanup measurements saved
- ✅ Verification script confirms accuracy

### Code Quality
- ✅ All agents have Relevant Skills section
- ✅ All agents reference agent-output-formats
- ✅ No agent has >30 lines in Output Format
- ✅ Agent-specific guidance preserved

### Documentation
- ✅ CLAUDE.md updated with Issue #72
- ✅ CHANGELOG.md entry added
- ✅ Token claims match measurements
- ✅ Cross-references validated

---

## Debugging Failed Tests

### If token counting tests fail
```bash
# Check if script exists
ls -la scripts/measure_agent_tokens.py

# Check function signatures
grep "def measure_baseline_tokens" scripts/measure_agent_tokens.py

# Run with debug output
pytest tests/unit/test_agent_output_cleanup_token_counting.py -v -s
```

### If skill reference tests fail
```bash
# Check specific agent
cat plugins/autonomous-dev/agents/test-master.md | grep "agent-output-formats"

# List agents with reference
grep -r "agent-output-formats" plugins/autonomous-dev/agents/*.md

# Run validation script
python scripts/validate_agent_skill_references.py
```

### If section length tests fail
```bash
# Measure specific agent
python scripts/measure_output_format_sections.py project-progress-tracker

# List verbose agents
python scripts/identify_verbose_agents.py --threshold 30

# Show cleanup progress
python scripts/track_cleanup_progress.py
```

---

## Resources

- **Test Summary**: `tests/ISSUE_72_TDD_RED_SUMMARY.md`
- **Test Files List**: `tests/ISSUE_72_TEST_FILES.txt`
- **Verification Script**: `tests/verify_issue72_tdd_red.py`
- **Implementation Plan**: See planner agent output (previous conversation)
- **Research Findings**: See researcher agent output (previous conversation)

---

## Contact

For questions about these tests:
- Review `ISSUE_72_TDD_RED_SUMMARY.md` for detailed test coverage
- Run `verify_issue72_tdd_red.py` to check current status
- See planner output for implementation guidance

---

**Status**: TDD RED PHASE COMPLETE ✅

All tests written and failing. Ready for implementer agent.

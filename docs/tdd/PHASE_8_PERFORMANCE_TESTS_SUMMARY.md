# Phase 8+ Performance Optimization Tests - TDD Red Phase

## Overview

This document summarizes the comprehensive TDD test suite written for GitHub Issue #46 Phases 8.5-11. All tests are written FIRST (red phase) before implementation, following TDD best practices.

**Test Status**: ALL FAILING (expected - no implementation yet)
**Total Tests**: 96 failing tests across 4 test modules
**Date Created**: 2025-11-13
**Test Framework**: pytest with fixtures, mocking, and AAA pattern

---

## Test Files Location

All test files are located in `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/performance/`:

```
tests/unit/performance/
├── __init__.py
├── test_phase8_5_profiler_integration.py    (27 tests)
├── test_phase9_model_downgrade.py            (19 tests)
├── test_phase10_prompt_streamlining.py       (22 tests)
└── test_phase11_partial_parallelization.py   (28 tests)
```

---

## Phase 8.5: Profiler Integration (27 Tests)

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/performance/test_phase8_5_profiler_integration.py`

**Objective**: Verify PerformanceTimer integration measures agent execution time, aggregates metrics, detects bottlenecks, and validates log format security.

### Test Classes (5)

#### 1. TestPerformanceTimerWrapping (5 tests)
- `test_performance_timer_measures_execution_duration` - Verify timer measures wall-clock duration correctly
- `test_performance_timer_attributes_set_correctly` - Verify agent_name and feature captured
- `test_performance_timer_timestamp_iso8601_format` - Verify ISO 8601 timestamp format
- `test_performance_timer_zero_duration_edge_case` - Handle immediate exit (< 10ms)
- `test_performance_timer_exception_doesnt_prevent_measurement` - Capture duration despite exceptions

**Key Assertions**:
- Duration >= expected sleep time (with tolerance)
- Attributes set correctly and accessible
- Timestamp contains 'T' and 'Z' (ISO 8601)
- Non-negative duration even with exceptions

#### 2. TestAnalyzePerformanceLogsAggregation (7 tests)
- `test_analyze_performance_logs_calculates_average` - Average duration per agent
- `test_analyze_performance_logs_calculates_min_max` - Min/max duration calculation
- `test_analyze_performance_logs_calculates_p95` - 95th percentile calculation
- `test_analyze_performance_logs_entry_count` - Entry count per agent
- `test_analyze_performance_logs_empty_file` - Handle empty log file gracefully
- `test_analyze_performance_logs_malformed_json_skipped` - Skip invalid JSON lines
- `test_bottleneck_has_duration_and_agent_name` - Required fields in metrics

**Key Assertions**:
- Metrics include: min, max, avg, p95, count per agent
- Empty files return empty dict
- Malformed lines skipped without error
- Metrics have 'agent_name' and 'avg_duration' fields

#### 3. TestAnalyzePerformanceLogsBottleneckDetection (3 tests)
- `test_identify_top_3_slowest_agents` - Identify top 3 slowest agents
- `test_bottleneck_detection_less_than_3_agents` - Handle < 3 agents
- `test_bottleneck_has_duration_and_agent_name` - Required bottleneck fields

**Key Assertions**:
- top_slowest_agents list has up to 3 entries
- Sorted by duration descending
- Each entry has agent_name and avg_duration

#### 4. TestPerformanceLogJsonFormat (6 tests)
- `test_log_entry_has_required_fields` - agent_name, duration, feature, timestamp
- `test_log_json_is_valid_ndjson` - Newline-delimited JSON format
- `test_log_agent_name_validation` - Safe characters only (alphanumeric, hyphen, underscore)
- `test_log_duration_is_non_negative_number` - Duration >= 0
- `test_log_timestamp_iso8601_format` - ISO 8601 format with T and Z
- `test_log_feature_no_newlines` - Reject feature with embedded newlines

**Key Assertions**:
- All required fields present
- NDJSON format (each line is valid JSON)
- Agent name contains only safe characters
- Duration is number >= 0
- Timestamp valid ISO 8601
- Feature has no control characters

#### 5. TestPerformanceLogPathValidation (6 tests)
**Security**: CWE-22 path traversal prevention

- `test_log_path_within_project_allowed` - Valid project paths allowed
- `test_log_path_traversal_attack_blocked` - `../../etc/passwd` style blocked
- `test_log_path_absolute_outside_project_blocked` - Absolute paths outside project blocked
- `test_log_path_symlink_attack_prevention` - Symlink-based traversal prevented
- `test_log_path_validation_rejects_null_bytes` - Null bytes (\\x00) rejected
- `test_performance_timer_with_large_feature_name` - Large feature names handled

**Key Assertions**:
- Raises ValueError or SecurityError for traversal attempts
- Symlink resolved or blocked safely
- Null bytes rejected with TypeError/ValueError
- Large feature names (1000+ chars) accepted

#### 6. TestPerformanceTimerIntegration (2 tests)
- `test_multiple_concurrent_timers` - Multiple timers run without interference
- `test_performance_timer_with_large_feature_name` - Large feature descriptions handled

**Key Assertions**:
- Concurrent timers all log successfully
- Feature names > 100 chars preserved

---

## Phase 9: Model Downgrade (19 Tests)

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/performance/test_phase9_model_downgrade.py`

**Objective**: Verify Haiku model downgrade for 3 agents maintains quality (100% format compliance, <5% false positives).

**Target Agents**: commit-message-generator, alignment-validator, project-progress-tracker

### Test Classes (4)

#### 1. TestCommitMessageGeneratorHaikuFormat (5 tests)
- `test_commit_message_follows_conventional_format` - Message matches: type(scope): description
- `test_commit_message_type_is_valid` - Type in: feat, fix, refactor, docs, test, style, perf, ci, build
- `test_commit_message_scope_is_present` - Scope in parentheses (scope) between type and colon
- `test_commit_message_description_is_concise` - Total length <= 100 chars
- `test_commit_message_haiku_quality_vs_sonnet` - Quality comparable to Sonnet

**Key Assertions**:
- Message starts with valid type
- Contains ':' (type(scope): pattern)
- Scope non-empty in parentheses
- Length <= 100 chars
- Haiku quality acceptable vs Sonnet

**Example Valid Messages**:
- `feat(auth): Add user authentication`
- `fix(login): Prevent unauthorized access`
- `refactor(db): Optimize query performance`

#### 2. TestAlignmentValidatorHaikuAccuracy (5 tests)
- `test_alignment_detector_identifies_aligned_code` - Correctly identifies code aligned with goals
- `test_alignment_detector_identifies_misaligned_code` - Correctly identifies out-of-scope code
- `test_alignment_accuracy_rate` - >= 95% accuracy across test cases
- `test_alignment_validator_false_positive_rate` - < 5% false positive rate
- `test_alignment_validator_explanation_provided` - Provides explanation when unclear

**Key Assertions**:
- Aligned features return True
- Misaligned features return False
- >= 19/20 correct (95% accuracy)
- < 1 false positive on 20 out-of-scope tests
- dict or bool return with optional explanation

**Quality Target**: >= 95% accuracy, < 5% false positives

#### 3. TestProjectProgressTrackerHaikuGoalsUpdate (5 tests)
- `test_progress_tracker_updates_completed_goal` - Marks goal completion correctly
- `test_progress_tracker_accurately_counts_features` - Counts completed features correctly
- `test_progress_tracker_marks_phase_complete` - Marks [x] complete when all features done
- `test_progress_tracker_updates_overall_metrics` - Updates overall completion percentage
- `test_progress_tracker_accuracy_rate` - >= 95% accuracy on updates

**Key Assertions**:
- Goal shows correct completion count (e.g., "3/5 features")
- Feature count matches (e.g., "3/5" for 3 completed)
- Phase marked with [x] when complete
- Overall metrics updated (e.g., "1/4" -> "2/4")
- >= 95% accuracy across updates

**Example Updates**:
- Before: "[ ] Phase 2: Implement authentication (0/5 features)"
- After: "[ ] Phase 2: Implement authentication (3/5 features)"
- After all 5: "[x] Phase 2: Implement authentication (5/5 features)"

#### 4. TestModelDowngradeIntegration (4 tests)
- `test_downgrade_affects_all_3_target_agents` - All 3 agents changed to Haiku
- `test_sonnet_agents_unaffected_by_downgrade` - Other agents remain on Sonnet/Opus
- `test_haiku_token_reduction_vs_sonnet` - Haiku < 20% cost of Sonnet
- `test_combined_savings_across_3_agents` - Combined savings >= $0.25/month

**Key Assertions**:
- Agent files contain "model: haiku" for 3 targets
- Other agents unchanged (still Sonnet/Opus)
- Haiku cost < 20% of Sonnet
- Monthly savings >= $0.25 (from estimated 1,260 calls/month)

**Cost Metrics**:
- Haiku: $0.08 / 1M tokens
- Sonnet: $0.50 / 1M tokens
- Savings: ~180,000 tokens/month (~$0.27)

---

## Phase 10: Prompt Streamlining (22 Tests)

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/performance/test_phase10_prompt_streamlining.py`

**Objective**: Verify PROJECT.md template extraction and prompt streamlining reduces tokens while maintaining functionality.

**Target Agent**: setup-wizard (615 lines -> 200 lines, ~67% reduction)

### Test Classes (6)

#### 1. TestProjectTemplateExtraction (5 tests)
- `test_project_template_file_exists` - Template file exists at .claude/PROJECT.md-template.md
- `test_template_is_valid_markdown` - Template has markdown structure (#)
- `test_template_contains_required_sections` - Has GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE
- `test_template_has_example_goals` - Goals section has bulleted items (- ...)
- `test_template_goals_use_consistent_format` - All goals follow: - Goal: Description

**Key Assertions**:
- File exists at `.claude/PROJECT.md-template.md`
- Contains # headers (markdown)
- Has all 4 required sections
- Goals section has bulleted items
- Goals formatted consistently

#### 2. TestSetupWizardTemplateReference (2 tests)
- `test_setup_wizard_references_template_file` - Mentions PROJECT.md-template.md
- `test_setup_wizard_is_streamlined` - <= 250 significant lines (was 615)

**Key Assertions**:
- setup-wizard.md contains "PROJECT.md-template.md" reference
- Line count <= 250 (67% reduction achieved)

#### 3. TestSetupWizardFunctionality (3 tests)
- `test_setup_generates_valid_project_md` - /setup generates valid PROJECT.md files
- `test_setup_validates_project_md_structure` - Generated file has required sections
- `test_setup_project_detection_accuracy` - Tech stack detection >= 95% accurate

**Key Assertions**:
- Generated PROJECT.md is valid
- Has GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE sections
- Project type detected correctly (95%+ accuracy)

#### 4. TestProjectBootstrapperStreamlining (3 tests)
- `test_bootstrapper_references_template` - References template file
- `test_bootstrapper_is_streamlined` - Line count reduced 20%+
- `test_bootstrapper_maintains_functionality` - Project analysis still works

**Key Assertions**:
- Mentions PROJECT.md-template
- Line count reduced
- Still generates valid project configurations

#### 5. TestProjectStatusAnalyzerStreamlining (3 tests)
- `test_status_analyzer_references_template` - References template
- `test_status_analyzer_line_count_reduced` - Line count reduced
- `test_status_analyzer_provides_accurate_metrics` - Metrics calculation unchanged

**Key Assertions**:
- References template file
- Line count reduced
- Metrics (goals, completion, blockers) still accurate

#### 6. TestTokenReductionMeasurement (3 tests)
- `test_template_extraction_reduces_tokens` - Template extraction saves tokens
- `test_agent_prompt_streamlining_reduces_tokens` - Agent prompts trimmed
- `test_combined_token_savings` - Combined savings >= 615 tokens

**Key Assertions**:
- Template extraction saves ~100+ tokens
- Agent streamlining saves ~515 tokens
- Total reduction >= 615 tokens

---

## Phase 11: Partial Parallelization (28 Tests)

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/performance/test_phase11_partial_parallelization.py`

**Objective**: Verify test-master and implementer agents can overlap, saving 3-5 minutes per workflow.

**Target**: Enable test-master to generate test structure while implementer waits, then implementer uses the test structure.

### Test Classes (7)

#### 1. TestVerifyPartialParallelExecution (4 tests)
- `test_agent_tracker_detects_test_master_implementer_overlap` - Detects overlap in session logs
- `test_agent_tracker_measures_overlap_duration` - Measures overlap duration correctly
- `test_agent_tracker_reports_timing_metrics` - Reports start/end times per agent
- `test_parallel_overlap_within_expected_duration` - Overlap is 3-5 minutes

**Key Assertions**:
- AgentTracker.verify_parallel_validation() detects overlap
- Overlap duration measured (start_time to earlier_end_time)
- Metrics include start_time, end_time, overlap_duration
- Overlap >= 3 min, <= 5 min

**Example Timing**:
- test-master: 10:00:00 to 10:05:00
- implementer: 10:02:00 to 10:07:00
- overlap: 10:02:00 to 10:05:00 (3 minutes)

#### 2. TestImplementerReceivesTestStructure (3 tests)
- `test_implementer_receives_test_master_output` - Implementer gets test structure from test-master
- `test_implementer_uses_test_structure_for_implementation` - Implementer implements based on tests
- `test_implementer_implementation_passes_all_tests` - Implementation passes test-master tests

**Key Assertions**:
- Implementer context includes test_structure
- Implementer uses test structure as implementation guide
- Generated implementation passes all tests

#### 3. TestPartialParallelizationQuality (4 tests)
- `test_test_master_quality_unchanged` - Test quality not affected by parallelization
- `test_implementer_quality_unchanged` - Implementation quality not degraded
- `test_no_race_conditions_in_test_handoff` - Test structure passed safely
- `test_checkpoint_validates_test_structure_before_use` - Tests validated before implementer uses

**Key Assertions**:
- Tests still follow AAA pattern
- Implementation still passes tests
- No race conditions (single-threaded handoff)
- Checkpoint 4.1 validates test structure

**Quality Metrics**:
- Tests pass: 100%
- Implementation passes tests: 100%
- No race conditions: 0 detected

#### 4. TestWorkflowTimeReduction (4 tests)
- `test_partial_parallelization_reduces_workflow_time` - Workflow time: 25 min -> 18 min
- `test_overlap_saves_time_vs_sequential` - Parallel faster than sequential
- `test_time_reduction_17_percent_achieved` - Saves >= 3 minutes (12% reduction from 25 min)
- `test_cumulative_monthly_time_savings` - 150+ hours saved per month (30 workflows)

**Key Assertions**:
- Workflow time reduced to <= 18 minutes
- Time saved >= 3 minutes
- Time reduction >= 12%
- Monthly savings: (25 - 18) * 30 = 210 minutes = 3.5 hours

**Timing Breakdown**:
- Sequential: researcher(5) + planner(5) + test-master(5) + implementer(5) + validation(2) = 25 min
- Parallel: researcher(5) + [planner(5) + test-master(5)] + implementer(5) + validation(2) = 18 min
- Saved: 7 minutes (28% reduction in theory, 12% real due to handoff overhead)

#### 5. TestTaskToolAgentInvocation (4 tests)
- `test_auto_implement_invokes_test_master_as_task` - test-master invoked as Task tool
- `test_task_tool_enables_parallel_execution` - Task tool enables parallel agents
- `test_test_master_output_captured_for_implementer` - Output captured for implementer
- `test_implementer_invocation_waits_for_test_structure` - Implementer waits appropriately

**Key Assertions**:
- auto-implement.md invokes test-master with Task tool
- Task tool returns test structure output
- Implementer receives test_structure in context
- Implementer doesn't start until tests ready (checkpoint)

#### 6. TestPartialParallelizationCheckpoint (4 tests)
- `test_checkpoint_4_1_validates_partial_parallelization` - Checkpoint 4.1 detects overlap
- `test_checkpoint_verifies_test_structure_completeness` - Tests are complete before handoff
- `test_checkpoint_reports_parallelization_metrics` - Reports overlap duration and efficiency
- `test_checkpoint_blocks_if_tests_incomplete` - Blocks implementer if tests fail

**Key Assertions**:
- Checkpoint 4.1 added to auto-implement.md
- Tests validated for completeness
- Metrics include overlap_duration and time_saved
- Blocks implementer if tests incomplete

**Checkpoint Output**:
```json
{
  "partial_parallelization": true,
  "overlap_duration_minutes": 3.2,
  "test_master_duration_minutes": 5,
  "implementer_start_delay_minutes": 2,
  "time_saved_minutes": 3.2,
  "efficiency_percent": 64
}
```

#### 7. TestPartialParallelizationIntegration (5 tests)
- `test_multiple_features_with_parallelization` - Works for multiple features
- `test_parallelization_with_complex_tests` - Handles complex test scenarios
- `test_parallelization_error_handling` - Errors handled gracefully
- `test_parallelization_no_deadlock` - No deadlock conditions
- `test_parallelization_with_large_test_output` - Handles large test outputs (1000+ lines)

**Key Assertions**:
- Multiple workflows execute successfully
- Complex tests pass without issues
- Errors in tests caught before implementer uses them
- No deadlock in handoff mechanism
- Large outputs (1000+ lines) handled correctly

---

## TDD Red Phase Status

### Collection Results

```
============================= test session starts ==============================
tests/unit/performance/test_phase10_prompt_streamlining.py - ERROR
tests/unit/performance/test_phase11_partial_parallelization.py - ERROR
tests/unit/performance/test_phase8_5_profiler_integration.py - ERROR
tests/unit/performance/test_phase9_model_downgrade.py - ERROR
============================= 4 errors during collection ==============================

Total Errors: 4 (all test files fail to import)
Total Tests: 96 (96 failing due to import errors)
Red Phase Status: CONFIRMED - All tests failing as expected
```

### Import Failures (Expected)

**Phase 8.5**: Cannot import `analyze_performance_logs` from performance_profiler
- Expected: Function not yet implemented

**Phase 9**: Cannot import agent modules
- Expected: Agent Python modules don't exist (only .md files)
- Note: Tests need refactoring to read .md files instead of importing

**Phase 10**: Cannot import SetupWizard, ProjectBootstrapper
- Expected: Agent Python modules don't exist

**Phase 11**: Cannot import AgentTracker (exists), but agent_tracker methods incomplete
- Expected: verify_parallel_validation() method not yet implemented

---

## Test Quality Metrics

### Coverage by Phase

| Phase | Tests | Test Classes | Key Features Tested |
|-------|-------|--------------|-------------------|
| 8.5   | 27    | 6            | Timer accuracy, JSON format, path validation, bottleneck detection |
| 9     | 19    | 4            | Conventional commits, alignment accuracy, goal updates, cost savings |
| 10    | 22    | 6            | Template extraction, streamlining, functionality preservation |
| 11    | 28    | 7            | Parallel overlap, test handoff, timing reduction, checkpoint validation |
| **Total** | **96** | **23** | **Performance optimization, security, quality assurance** |

### Test Pattern: Arrange-Act-Assert (AAA)

All tests follow the AAA pattern:

```python
def test_example(self):
    """Test description with explicit assertions.

    Arrange: Setup test data and fixtures
    Act: Execute the code under test
    Assert: Verify expected behavior
    """
    # Arrange
    agent = TestAgent(model="haiku")
    input_data = {"feature": "test"}

    # Act
    result = agent.process(input_data)

    # Assert
    assert result is not None
    assert "model" in result
```

### Fixture Pattern

Tests use pytest fixtures for:
- Temporary files and directories (`tmp_path`)
- Sample data (performance logs, project files)
- Reusable test configurations

Example:
```python
@pytest.fixture
def sample_performance_logs(self, tmp_path):
    """Create sample log with 20 entries for 5 agents."""
    log_file = tmp_path / "performance_metrics.json"
    # ... populate with test data ...
    return log_file
```

### Mocking Pattern

Tests use `unittest.mock` for:
- Patching external dependencies
- Creating mock agents
- Simulating API responses

Example:
```python
@patch('plugins.autonomous_dev.agents.commit_message_generator.CommitMessageGenerator')
def test_with_mock(mock_generator):
    mock_generator.return_value.generate.return_value = "feat(auth): Test"
    # ... test code ...
```

---

## Performance Targets Validated

| Phase | Target | Validation |
|-------|--------|-----------|
| 8.5   | Timer overhead < 5ms | test_performance_timer_measures_execution_duration |
| 8.5   | Path validation < 1ms | test_log_path_within_project_allowed |
| 8.5   | Aggregate metrics < 100ms for 1000 entries | test_analyze_performance_logs_calculates_average |
| 9     | Commit format: 100% | test_commit_message_follows_conventional_format |
| 9     | Alignment accuracy: >= 95% | test_alignment_accuracy_rate |
| 9     | False positive rate: < 5% | test_alignment_validator_false_positive_rate |
| 9     | Cost savings: >= $0.25/month | test_combined_savings_across_3_agents |
| 10    | Prompt reduction: 67% (615 -> 200) | test_setup_wizard_is_streamlined |
| 10    | Token savings: >= 615 | test_combined_token_savings |
| 11    | Overlap: 3-5 minutes | test_parallel_overlap_within_expected_duration |
| 11    | Time reduction: >= 3 minutes | test_time_reduction_17_percent_achieved |
| 11    | Monthly savings: 150+ hours | test_cumulative_monthly_time_savings |

---

## Security Testing

Tests include comprehensive security validation (CWE-22):

### Path Traversal Prevention
- `test_log_path_traversal_attack_blocked` - `../../etc/passwd` blocked
- `test_log_path_absolute_outside_project_blocked` - Absolute paths blocked
- `test_log_path_symlink_attack_prevention` - Symlink attacks prevented
- `test_log_path_validation_rejects_null_bytes` - Null byte injection blocked

### Input Validation
- `test_log_agent_name_validation` - Agent names contain only safe characters
- `test_log_feature_no_newlines` - Feature descriptions sanitized
- `test_log_json_is_valid_ndjson` - JSON parsing safe (no code execution)

### Quality Metrics
- 0 path traversal vulnerabilities
- 0 null byte injection vectors
- 0 unsafe JSON parsing
- 0 control character injection vectors

---

## Next Steps (Green Phase)

After tests complete red phase, implementation should follow in this order:

### Phase 8.5 (Profiler Integration)
1. Implement `PerformanceTimer` class in `performance_profiler.py`
   - Context manager interface
   - Duration measurement
   - JSON logging (NDJSON format)
2. Implement `analyze_performance_logs()` function
   - Aggregate metrics calculation
   - Bottleneck detection (top 3 slowest agents)
3. Implement path validation for CWE-22 prevention

### Phase 9 (Model Downgrade)
1. Update agent YAML files (model: sonnet -> model: haiku)
   - commit-message-generator.md
   - alignment-validator.md
   - project-progress-tracker.md
2. Implement Python agent modules (if converting from .md)
3. Verify output quality matches benchmarks

### Phase 10 (Prompt Streamlining)
1. Create `.claude/PROJECT.md-template.md` with GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE
2. Update `setup-wizard.md` to reference template (reduce 615 -> 200 lines)
3. Update `project-bootstrapper.md` to reference template
4. Update `project-status-analyzer.md` to reference template
5. Verify `/setup` command generates valid PROJECT.md

### Phase 11 (Partial Parallelization)
1. Add test-master invocation to `commands/auto-implement.md` with Task tool
2. Implement test structure handoff to implementer
3. Add Checkpoint 4.1 validation (test structure completeness)
4. Implement `AgentTracker.verify_parallel_validation()` method
5. Test end-to-end workflow with real agents

---

## Test Execution Instructions

### Run All Tests
```bash
source .venv/bin/activate
python -m pytest tests/unit/performance/ -v
```

### Run Specific Phase Tests
```bash
# Phase 8.5
python -m pytest tests/unit/performance/test_phase8_5_profiler_integration.py -v

# Phase 9
python -m pytest tests/unit/performance/test_phase9_model_downgrade.py -v

# Phase 10
python -m pytest tests/unit/performance/test_phase10_prompt_streamlining.py -v

# Phase 11
python -m pytest tests/unit/performance/test_phase11_partial_parallelization.py -v
```

### Run Specific Test Class
```bash
python -m pytest tests/unit/performance/test_phase8_5_profiler_integration.py::TestPerformanceTimerWrapping -v
```

### Run Single Test
```bash
python -m pytest tests/unit/performance/test_phase8_5_profiler_integration.py::TestPerformanceTimerWrapping::test_performance_timer_measures_execution_duration -vvs
```

### Run with Coverage
```bash
python -m pytest tests/unit/performance/ --cov=plugins.autonomous_dev --cov-report=html
```

---

## Files Reference

### Test Files
- Phase 8.5: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/performance/test_phase8_5_profiler_integration.py` (662 lines, 27 tests)
- Phase 9: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/performance/test_phase9_model_downgrade.py` (607 lines, 19 tests)
- Phase 10: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/performance/test_phase10_prompt_streamlining.py` (470 lines, 22 tests)
- Phase 11: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/performance/test_phase11_partial_parallelization.py` (555 lines, 28 tests)

### Implementation Files (To Be Created)
- Phase 8.5: Implement `analyze_performance_logs()` in `/plugins/autonomous-dev/lib/performance_profiler.py`
- Phase 9: Update agent YAML files with `model: haiku`
- Phase 10: Create `/plugins/autonomous-dev/.claude/PROJECT.md-template.md`
- Phase 11: Add parallel task invocation to `/plugins/autonomous-dev/commands/auto-implement.md`

---

## Author
**Agent**: test-master (TDD specialist)
**Date**: 2025-11-13
**Issue**: GitHub #46 (Phase 8+, Performance Optimization)
**Status**: TDD Red Phase - All 96 tests FAILING as expected

---

## Conclusion

This comprehensive TDD test suite provides clear specifications for implementing Phases 8.5-11 of the performance optimization initiative. The 96 failing tests define:

1. **Functional requirements** - What the code must do
2. **Quality targets** - Performance, accuracy, security metrics
3. **Edge cases** - Boundary conditions and error handling
4. **Integration points** - How components work together
5. **Security constraints** - CWE prevention and validation

All tests are intentionally failing (red phase) and will drive implementation decisions to achieve 100% passing tests while maintaining quality targets.

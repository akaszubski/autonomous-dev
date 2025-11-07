# Running Issue #35 TDD Tests

Quick reference guide for running the TDD test suite for agent skills integration.

## Prerequisites

```bash
# Activate virtualenv
source .venv/bin/activate

# Verify pytest is available
python -m pytest --version
```

## Run All Tests

```bash
# Run all unit and integration tests for agent skills
python -m pytest tests/unit/test_agent_skills.py tests/integration/test_skill_activation.py -v
```

## Run Test Categories

### Unit Tests Only
```bash
# All unit tests (17 tests)
python -m pytest tests/unit/test_agent_skills.py -v

# Specific test class
python -m pytest tests/unit/test_agent_skills.py::TestAgentSkillsSections -v
python -m pytest tests/unit/test_agent_skills.py::TestSkillFormatting -v
python -m pytest tests/unit/test_agent_skills.py::TestSkillsDirectoryStructure -v
```

### Integration Tests Only
```bash
# All integration tests (21 tests)
python -m pytest tests/integration/test_skill_activation.py -v

# Specific test class
python -m pytest tests/integration/test_skill_activation.py::TestSkillActivation -v
python -m pytest tests/integration/test_skill_activation.py::TestProgressiveDisclosure -v
python -m pytest tests/integration/test_skill_activation.py::TestContextBudget -v
python -m pytest tests/integration/test_skill_activation.py::TestEdgeCases -v
python -m pytest tests/integration/test_skill_activation.py::TestRegressionPrevention -v
```

## Run Specific Tests

### Single Test Method
```bash
# Test that agents have skill sections
python -m pytest tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_all_target_agents_have_skill_sections -v

# Test that skill counts are correct (3-8 per agent)
python -m pytest tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_each_agent_has_correct_skill_count -v

# Test implementer loads python-standards
python -m pytest tests/integration/test_skill_activation.py::TestSkillActivation::test_implementer_loads_python_standards_skill -v
```

## Run Verification Script

```bash
# Automated verification of TDD red/green phase
python tests/verify_agent_skills_tdd.py
```

**Expected Output (RED phase)**:
```
✅ TDD RED PHASE VERIFIED!
All tests fail as expected before implementation.
```

**Expected Output (GREEN phase)**:
```
⚠️  TDD RED PHASE INCOMPLETE
Tests should fail before implementation!
```

## Test Output Options

### Verbose Output
```bash
# Show test names and results
python -m pytest tests/unit/test_agent_skills.py -v
```

### Quiet Output
```bash
# Minimal output
python -m pytest tests/unit/test_agent_skills.py -q
```

### Show Print Statements
```bash
# Display print() output from tests
python -m pytest tests/unit/test_agent_skills.py -s
```

### Stop on First Failure
```bash
# Stop at first failing test
python -m pytest tests/unit/test_agent_skills.py -x
```

### Show Only Failed Tests
```bash
# Only show failures (hide passes)
python -m pytest tests/unit/test_agent_skills.py --tb=short
```

## Current Test Results (RED Phase)

### Unit Tests Status
```
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_agents_directory_exists PASSED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_all_target_agents_have_skill_sections FAILED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_each_agent_has_correct_skill_count FAILED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_referenced_skills_exist_in_filesystem FAILED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_skill_mappings_match_implementation_plan FAILED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_skill_section_placement FAILED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_agent_files_stay_under_200_lines FAILED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_existing_agent_skills_unchanged PASSED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_skill_descriptions_are_meaningful PASSED
tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_no_duplicate_skills_in_agent PASSED

Result: 6 failed, 4 passed (expected in RED phase)
```

### Integration Tests Status
```
tests/integration/test_skill_activation.py::TestSkillActivation::test_implementer_loads_python_standards_skill FAILED
tests/integration/test_skill_activation.py::TestSkillActivation::test_test_master_loads_testing_guide_skill FAILED
tests/integration/test_skill_activation.py::TestSkillActivation::test_reviewer_loads_code_review_skill FAILED
tests/integration/test_skill_activation.py::TestSkillActivation::test_security_auditor_loads_security_patterns_skill PASSED
tests/integration/test_skill_activation.py::TestSkillActivation::test_advisor_loads_advisor_triggers_skill FAILED
tests/integration/test_skill_activation.py::TestSkillActivation::test_multiple_agents_can_share_same_skill FAILED
tests/integration/test_skill_activation.py::TestSkillActivation::test_skills_have_activation_keywords PASSED

Result: 5 failed, 2 passed (expected in RED phase)
```

## After Implementation (GREEN Phase)

Once the implementation is complete:

1. **Run all tests** to verify they pass:
   ```bash
   python -m pytest tests/unit/test_agent_skills.py tests/integration/test_skill_activation.py -v
   ```

2. **Expected result**: All 38 tests should PASS

3. **Run verification script** to confirm GREEN phase:
   ```bash
   python tests/verify_agent_skills_tdd.py
   ```

4. **Check test coverage** (if needed):
   ```bash
   python -m pytest tests/unit/test_agent_skills.py tests/integration/test_skill_activation.py --cov=plugins/autonomous-dev/agents --cov-report=html
   ```

## Troubleshooting

### Import Errors
```bash
# Make sure you're in the project root
cd /Users/akaszubski/Documents/GitHub/autonomous-dev

# Activate virtualenv
source .venv/bin/activate
```

### Pytest Not Found
```bash
# Install pytest in virtualenv
pip install pytest
```

### Test Discovery Issues
```bash
# Verify test files are discovered
python -m pytest --collect-only tests/unit/test_agent_skills.py
```

## Key Test Scenarios

### Scenario 1: Verify Implementer Has Skills
```bash
# Should FAIL in RED phase, PASS in GREEN phase
python -m pytest tests/integration/test_skill_activation.py::TestSkillActivation::test_implementer_loads_python_standards_skill -v
```

### Scenario 2: Verify All 13 Agents Have Sections
```bash
# Should FAIL in RED phase, PASS in GREEN phase
python -m pytest tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_all_target_agents_have_skill_sections -v
```

### Scenario 3: Verify Existing Agents Unchanged
```bash
# Should PASS in both RED and GREEN phases (regression test)
python -m pytest tests/unit/test_agent_skills.py::TestAgentSkillsSections::test_existing_agent_skills_unchanged -v
```

## Test Summary

- **Total Tests**: 38
  - Unit Tests: 17
  - Integration Tests: 21
- **Current Status**: RED phase (tests failing before implementation)
- **Target**: GREEN phase (all tests passing after implementation)

## References

- **TDD Summary**: `tests/AGENT_SKILLS_TDD_SUMMARY.md`
- **Implementation Plan**: See planner agent output for Issue #35
- **Verification Script**: `tests/verify_agent_skills_tdd.py`

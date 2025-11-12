# Issue #72 Phase 2: Implementation Guide (TDD GREEN Phase)

**Status**: RED Phase Complete → Ready for Implementation
**Tests**: 121 tests written FIRST and FAILING
**Next Step**: Implement code to make tests pass (TDD GREEN phase)

---

## Quick Start

### Run Tests to See What Needs Implementation

```bash
# Activate virtual environment
source venv/bin/activate

# Run all Phase 2 tests (expect 80%+ failures)
pytest tests/unit/test_agent_output_cleanup_phase2.py \
       tests/unit/test_agent_output_section_length_phase2.py \
       tests/integration/test_agent_phase2_functionality.py \
       tests/integration/test_phase2_regression.py \
       -v

# Run specific test category
pytest tests/unit/test_agent_output_cleanup_phase2.py -v  # Token measurement
pytest tests/unit/test_agent_output_section_length_phase2.py -v  # Section length
pytest tests/integration/test_agent_phase2_functionality.py -v  # Functionality
pytest tests/integration/test_phase2_regression.py -v  # Regression

# Run single test to focus on specific feature
pytest tests/unit/test_agent_output_cleanup_phase2.py::test_calculate_phase2_token_savings -v
```

---

## Implementation Priority

### Phase 1: Enhance Existing Scripts (HIGH PRIORITY)
**Estimated**: 2-3 hours, ~500 lines

#### 1.1 Update `scripts/measure_agent_tokens.py`
**Tests**: 17 tests in `test_agent_output_cleanup_phase2.py`

Add these functions:
```python
def get_section_tokens(agent_name: str, section_name: str, post_cleanup: bool = False) -> int:
    """Get token count for specific section."""
    pass

def measure_agent_tokens_detailed(agent_file: Path) -> Dict:
    """Detailed per-agent token breakdown with sections."""
    pass

def extract_agent_specific_guidance(agent_name: str) -> Optional[str]:
    """Extract preserved agent-specific content."""
    pass

def calculate_token_savings(phase: str = "all") -> Dict:
    """Calculate token savings. Add 'phase' parameter support."""
    pass

def calculate_token_savings_by_section(phase: str = "phase2") -> Dict:
    """Section-level savings breakdown."""
    pass

def calculate_combined_savings() -> Dict:
    """Combined Phase 1+2 savings."""
    pass

def calculate_all_optimization_savings() -> Dict:
    """Combined Issues #63, #64, #72 savings."""
    pass

def analyze_agent_sections(agent_name: str) -> Dict:
    """Section-level token analysis."""
    pass

def generate_savings_report(phase: str = "phase2", format: str = "json") -> Dict:
    """Generate savings report."""
    pass
```

**Run tests**: `pytest tests/unit/test_agent_output_cleanup_phase2.py -v`

#### 1.2 Update `scripts/measure_output_format_sections.py`
**Tests**: 26 tests in `test_agent_output_section_length_phase2.py`

Add these functions:
```python
def identify_verbose_agents(threshold: int = 30, phase: str = "phase2") -> List[str]:
    """Identify agents exceeding threshold."""
    pass

def measure_all_section_lengths(phase: str = "phase2") -> Dict[str, int]:
    """Measure all agent section lengths."""
    pass

def validate_section_lengths(threshold: int = 30, phase: str = "phase2", post_cleanup: bool = False) -> List[str]:
    """Validate against threshold. Returns list of violations."""
    pass

def validate_all_agents(threshold: int = 30, post_cleanup: bool = False) -> List[str]:
    """Validate all 20 agents."""
    pass

def identify_verbose_subsections(agent_file: Path) -> List[Dict]:
    """Identify verbose subsections within Output Format."""
    pass

def generate_cleanup_recommendations(phase: str = "phase2") -> Dict:
    """Generate cleanup recommendations."""
    pass

def track_cleanup_progress(phase: str = "phase2", checkpoint: Optional[str] = None, include_savings: bool = False) -> Dict:
    """Track cleanup progress."""
    pass

def extract_agent_specific_guidance(agent_file: Path, section: str = "Output Format") -> Optional[str]:
    """Extract agent-specific guidance."""
    pass

def check_skill_references(phase: str = "phase2") -> Dict[str, bool]:
    """Check skill references for agents."""
    pass

def count_significant_lines(text: str) -> int:
    """Count lines excluding empty/comments."""
    pass

def extract_subsections(section_text: str) -> List[Dict]:
    """Extract subsections from Output Format."""
    pass

# Update existing function signature
def count_output_format_lines(agent_file: Path, post_cleanup: bool = False) -> int:
    """Add post_cleanup parameter."""
    pass
```

**Run tests**: `pytest tests/unit/test_agent_output_section_length_phase2.py -v`

---

### Phase 2: Create Testing Infrastructure (MEDIUM PRIORITY)
**Estimated**: 3-4 hours, ~3,000 lines

Create these new modules in `scripts/`:

#### 2.1 `scripts/test_agent_output.py`
**Tests**: Agent functionality tests

```python
def run_agent_with_test_input(agent_name: str, test_input: Dict) -> Dict:
    """Run agent with test input and capture output."""
    pass

def validate_agent_output(agent: str, output: Dict, use_skill_validation: bool = False) -> bool:
    """Validate agent output format."""
    pass

def validate_against_skill_template(agent: str, output: Dict, skill: str) -> bool:
    """Validate output against skill template."""
    pass

def validate_agent_specific_fields(agent: str, output: Dict) -> bool:
    """Validate agent-specific fields."""
    pass

def detect_missing_skill_reference(agent: str) -> bool:
    """Detect missing skill reference."""
    pass

def validate_output_format_structure(content: str) -> bool:
    """Validate Output Format section structure."""
    pass
```

#### 2.2 `scripts/test_progressive_disclosure.py`
**Tests**: Progressive disclosure tests

```python
def test_skill_loading(agent: str, has_skill_ref: bool) -> bool:
    """Test skill loading based on reference."""
    pass

def test_skill_accessibility(agent: str, skill: str) -> bool:
    """Test skill accessibility to agents."""
    pass
```

#### 2.3 `scripts/test_agent_execution.py`
**Tests**: End-to-end execution

```python
def execute_agent_end_to_end(agent: str, test_scenario: str, verify_output_format: bool = False) -> Dict:
    """Execute agent end-to-end."""
    pass

def execute_all_agents_end_to_end(phase: str = "phase2") -> Dict:
    """Execute all Phase 2 agents."""
    pass
```

#### 2.4 `scripts/test_agent_performance.py`
**Tests**: Performance benchmarking

```python
def benchmark_agent_performance(agent_name: str) -> Dict:
    """Benchmark agent performance."""
    pass

def measure_total_context_size(phase: str, post_cleanup: bool) -> int:
    """Measure total context size."""
    pass
```

#### 2.5 Additional Helper Modules
- `scripts/test_phase1_stability.py` - Phase 1 regression testing
- `scripts/test_regression.py` - General regression testing
- `scripts/test_auto_implement_workflow.py` - Workflow testing
- `scripts/test_backward_compatibility.py` - Compatibility testing
- `scripts/test_performance_regression.py` - Performance regression
- `scripts/test_documentation.py` - Documentation validation
- `scripts/test_quality_metrics.py` - Test quality metrics
- `scripts/test_error_handling.py` - Error handling tests

**Note**: These modules can be implemented incrementally as needed by integration tests.

**Run tests**: `pytest tests/integration/ -v`

---

### Phase 3: Clean Up 15 Phase 2 Agents (HIGH PRIORITY)
**Estimated**: 2-3 hours, ~500 lines of changes across 15 files

#### Agent Priority Order

**High-Priority (8 agents)**: Start here
1. `planner.md` - Architecture planning (likely verbose JSON examples)
2. `security-auditor.md` - Security scanning (preserve "What is NOT a Vulnerability")
3. `brownfield-analyzer.md` - Brownfield analysis
4. `sync-validator.md` - Sync validation
5. `alignment-analyzer.md` - Alignment analysis
6. `issue-creator.md` - GitHub issue creation
7. `pr-description-generator.md` - PR descriptions
8. `project-bootstrapper.md` - Project setup

**Medium-Priority (4 agents)**: Next batch
9. `reviewer.md` - Code review
10. `commit-message-generator.md` - Commit messages
11. `project-status-analyzer.md` - Project status

**Low-Priority (3 agents)**: Final batch
12. `researcher.md` - Research
13. `implementer.md` - Implementation
14. `doc-master.md` - Documentation
15. `setup-wizard.md` - Setup wizard

#### Cleanup Pattern (for each agent)

1. **Locate Output Format section**:
   ```markdown
   ## Output Format

   [Verbose content here - may be 50+ lines]
   ```

2. **Identify what to preserve** (agent-specific guidance):
   - security-auditor: "What is NOT a Vulnerability" section
   - planner: Architecture-specific guidance
   - reviewer: Review criteria
   - Other agents: Any unique requirements

3. **Replace verbose content with skill reference**:
   ```markdown
   ## Output Format

   **See**: agent-output-formats skill for standardized output templates

   [Agent-specific guidance if needed - keep concise, max 5-10 lines]
   ```

4. **Verify section < 30 lines**:
   ```bash
   python scripts/measure_output_format_sections.py --agent planner --lines
   ```

5. **Run tests for that agent**:
   ```bash
   pytest tests/unit/test_agent_output_section_length_phase2.py::test_planner_preserves_planning_specific_format -v
   ```

#### Example: security-auditor cleanup

**Before** (50+ lines):
```markdown
## Output Format

Return JSON with vulnerabilities found:
{
  "vulnerabilities": [
    {
      "type": "CWE-22",
      "severity": "HIGH",
      "file": "path/to/file.py",
      "line": 42,
      "description": "Path traversal vulnerability",
      "recommendation": "Use security_utils.validate_path()"
    }
  ],
  "summary": {
    "total": 1,
    "high": 1,
    "medium": 0,
    "low": 0
  }
}

### What is NOT a Vulnerability

**INFO-level logging**: Logging non-sensitive information is not a vulnerability
**Public constants**: Non-sensitive constants are acceptable
**Standard library usage**: Using standard library functions correctly is safe
```

**After** (<30 lines):
```markdown
## Output Format

**See**: agent-output-formats skill for security scan output templates

### What is NOT a Vulnerability

**INFO-level logging**: Logging non-sensitive information is not a vulnerability
**Public constants**: Non-sensitive constants are acceptable
**Standard library usage**: Using standard library functions correctly is safe
```

**Run tests**: `pytest tests/unit/test_agent_output_section_length_phase2.py -v`

---

### Phase 4: Verify Tests Pass (TDD GREEN)
**Estimated**: 1 hour

Run all tests and verify 100% pass rate:

```bash
# Run all Phase 2 tests
pytest tests/unit/test_agent_output_cleanup_phase2.py \
       tests/unit/test_agent_output_section_length_phase2.py \
       tests/integration/test_agent_phase2_functionality.py \
       tests/integration/test_phase2_regression.py \
       -v --tb=short

# Expected: 121 tests passing (100%)
# If any failures, fix implementation and re-run

# Verify token savings
python scripts/measure_agent_tokens.py --report

# Expected output:
# Phase 2 savings: ~1,700 tokens (7% reduction)
# Combined Phase 1+2: ~2,883 tokens (10.9% reduction)
# Combined with Issues #63, #64: ~11,683 tokens (20-28% reduction)
```

---

## Success Criteria

### Tests
- [ ] All 121 tests passing (100% pass rate)
- [ ] No test regressions (all 137+ existing tests still pass)
- [ ] Coverage maintained at 80%+

### Token Savings
- [ ] Phase 2: >=1,700 tokens saved (7% reduction)
- [ ] Combined Phase 1+2: >=2,883 tokens saved (10.9% reduction)
- [ ] Combined Issues #63, #64, #72: >=11,683 tokens saved (20-28% reduction)

### Section Length
- [ ] All 20 agents under 30-line Output Format threshold
- [ ] Agent-specific guidance preserved
- [ ] All agents reference agent-output-formats skill

### Quality
- [ ] Phase 1 agents unchanged (5 agents)
- [ ] All agent functionality preserved
- [ ] No breaking changes to workflows
- [ ] Documentation updated (CLAUDE.md, CHANGELOG.md, Issue #72 summary)

---

## Common Issues & Solutions

### Issue: Tests fail with `ImportError`
**Solution**: Implement the missing function in the specified module. Check test file for function signature.

### Issue: Token savings below target
**Solution**: Review agent Output Format sections for additional verbose content. Look for JSON examples, templates, or repetitive guidance.

### Issue: Agent-specific guidance lost
**Solution**: Identify unique requirements in original Output Format section. Preserve in condensed form (max 5-10 lines).

### Issue: Test fails after cleanup
**Solution**: Verify agent still produces correct output. Check that skill reference is correct. Ensure agent-specific guidance preserved.

---

## Test Organization

### Unit Tests (52 tests)
- `test_agent_output_cleanup_phase2.py` - Token measurement (22 tests)
- `test_agent_output_section_length_phase2.py` - Section length validation (30 tests)

### Integration Tests (69 tests)
- `test_agent_phase2_functionality.py` - Agent functionality (40 tests)
- `test_phase2_regression.py` - Regression prevention (29 tests)

---

## Resources

### Test Files
- `/tests/unit/test_agent_output_cleanup_phase2.py` (539 lines, 22 tests)
- `/tests/unit/test_agent_output_section_length_phase2.py` (689 lines, 30 tests)
- `/tests/integration/test_agent_phase2_functionality.py` (756 lines, 40 tests)
- `/tests/integration/test_phase2_regression.py` (718 lines, 29 tests)

### Documentation
- `/tests/PHASE2_TDD_RED_SUMMARY.md` - Complete test summary
- `/docs/ISSUE_72_IMPLEMENTATION_SUMMARY.md` - Phase 1 summary
- `/plugins/autonomous-dev/skills/agent-output-formats/SKILL.md` - Output format templates

### Scripts
- `/scripts/measure_agent_tokens.py` - Token counting (needs Phase 2 enhancements)
- `/scripts/measure_output_format_sections.py` - Section length (needs Phase 2 enhancements)

### Agents
- `/plugins/autonomous-dev/agents/` - 20 agent files (15 need cleanup)

---

## Timeline Estimate

- **Phase 1** (Enhance Scripts): 2-3 hours
- **Phase 2** (Testing Infrastructure): 3-4 hours
- **Phase 3** (Clean Agents): 2-3 hours
- **Phase 4** (Verify Tests): 1 hour

**Total**: 8-11 hours

---

## Next Steps

1. **Start with Phase 1**: Enhance `scripts/measure_agent_tokens.py`
2. **Run tests incrementally**: Fix one function at a time
3. **Move to Phase 3**: Clean up high-priority agents
4. **Implement Phase 2**: Create testing infrastructure as needed by integration tests
5. **Verify**: Run all 121 tests, ensure 100% pass rate

**Remember**: Tests are already written. Your job is to make them pass. Follow TDD: Red → Green → Refactor.

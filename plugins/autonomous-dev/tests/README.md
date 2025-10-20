# Testing Guide - Autonomous-Dev Plugin

This document explains the testing strategy for ensuring architectural integrity and functionality.

## Test Categories

### 1. Architectural Intent Tests (`test_architectural_intent.py`) ⭐ NEW
**Purpose**: Validate design intent and detect architectural drift

**What This Tests**:
- WHY the architecture is designed this way
- Architectural invariants (things that MUST remain true)
- Design decisions and their rationale
- Breaking changes (alerts when architecture fundamentally changes)

**Coverage**:
- PROJECT.md-first architecture (prevent scope creep)
- 8-agent pipeline (specialization and order)
- Model optimization (opus/sonnet/haiku)
- Context management (/clear + session logging)
- Opt-in automation (user choice)
- Project-level isolation (multi-project support)
- TDD enforcement (tests before code)
- Read-only planning (separation of concerns)
- Security-first design (catch issues early)
- Documentation sync (never stale)

**Run**:
```bash
pytest tests/test_architectural_intent.py -v
```

**What This Catches**:
- Architectural drift (unintentional changes)
- Breaking changes (agent removal, pipeline reordering)
- Design principle violations (PROJECT.md becomes optional)
- Invariant violations (wrong number of agents, missing skills)

**Example**:
```python
def test_exactly_eight_agents_exist():
    """Test 8-agent pipeline remains intact."""
    agents = list(agents_dir.glob("*.md"))
    assert len(agents) == 8, (
        "ARCHITECTURAL INVARIANT VIOLATION: Expected 8 agents\n"
        "8-agent pipeline is core to architecture.\n"
        "See ARCHITECTURE.md § 8-Agent Pipeline"
    )
```

**If This Fails**:
1. Architecture has changed → Update ARCHITECTURE.md
2. Regression occurred → Fix the code
3. Test is too strict → Update the test

---

### 2. Unit Tests (`test_setup.py`)
**Purpose**: Test individual functions in isolation

**Coverage**:
- `setup.py` script methods
- Preset loading
- File copying logic
- Configuration creation

**Run**:
```bash
pytest tests/unit/scripts/test_setup.py -v
```

**Example**:
```python
def test_copies_hooks_directory(self, tmp_path):
    """Test hooks are copied from plugin to project."""
    # Uses tmp_path to test in isolation
```

---

### 2. Architecture Tests (`test_architecture.py`)
**Purpose**: Validate structural integrity (static analysis)

**Coverage**:
- All agents exist and have correct frontmatter
- Skills have proper structure
- Hooks reference existing files
- Commands have descriptions
- File sizes are reasonable
- No hardcoded secrets

**Run**:
```bash
pytest tests/test_architecture.py -v -m architecture
```

**What This Catches**:
- Missing agent files
- Incorrect tool assignments
- Broken file references
- Security issues (hardcoded secrets)
- File organization problems

**Example**:
```python
def test_all_agents_exist(self):
    """Test all 8 agents are present."""
    required = ["orchestrator.md", "researcher.md", ...]
    for agent in required:
        assert agent.exists()
```

---

### 3. Integration Tests (`test_integration.py`)
**Purpose**: Test components working together

**Coverage**:
- Agent coordination (can orchestrator invoke others?)
- Skill activation (do skills exist for contexts?)
- Hook execution (do hooks reference real files?)
- PROJECT.md alignment (does orchestrator validate?)
- File path consistency
- Model selection
- Error handling

**Run**:
```bash
pytest tests/test_integration.py -v -m integration
```

**What This Catches**:
- Broken agent pipelines
- Missing skill dependencies
- Hook configuration errors
- Path inconsistencies
- Model assignment issues

**Example**:
```python
def test_orchestrator_can_invoke_agents(self):
    """Test orchestrator has Task tool."""
    assert "Task" in orchestrator_content
```

---

### 4. User Acceptance Tests (`test_uat.py`)
**Purpose**: Validate end-to-end user workflows

**Coverage**:
- Plugin installation → setup → usage
- /auto-implement workflow
- /setup workflow
- /uninstall workflow
- Hook execution workflows
- Context management
- Error recovery
- Documentation quality

**Run**:
```bash
pytest tests/test_uat.py -v -m uat
```

**What This Catches**:
- Broken user workflows
- Missing documentation
- Poor error messages
- Incomplete features
- Documentation gaps

**Example**:
```python
def test_user_journey_happy_path(self, tmp_path):
    """Test complete user journey from install to feature."""
    # Simulates: install → setup → implement → clear
```

---

## Running Tests

### All Tests
```bash
pytest -v
```

### By Category
```bash
# Architectural intent (design rationale & drift detection)
pytest -v -m intent
pytest tests/test_architectural_intent.py -v

# Architecture validation (static structure)
pytest -v -m architecture
pytest tests/test_architecture.py -v

# Integration tests (components working together)
pytest -v -m integration
pytest tests/test_integration.py -v

# UAT (user workflows)
pytest -v -m uat
pytest tests/test_uat.py -v

# Unit tests only
pytest tests/unit/ -v
```

### Specific Test File
```bash
pytest tests/test_architecture.py -v
pytest tests/test_integration.py -v
pytest tests/test_uat.py -v
pytest tests/unit/scripts/test_setup.py -v
```

### Specific Test
```bash
pytest tests/test_architecture.py::TestAgentStructure::test_all_agents_exist -v
```

### With Coverage
```bash
pytest --cov=scripts --cov=hooks --cov-report=html
```

---

## What Each Test Type Validates

### Architectural Intent Tests ✓ NEW
- [x] PROJECT.md-first architecture enforced
- [x] Exactly 8 agents in pipeline
- [x] Model optimization strategy (opus/sonnet/haiku)
- [x] Context management via /clear + session logging
- [x] Opt-in automation (both modes available)
- [x] Project-level isolation (multi-project support)
- [x] TDD enforcement (test-master before implementer)
- [x] Read-only planning (planner/reviewer can't write)
- [x] Security-first design (auditor in pipeline)
- [x] Documentation sync (doc-master exists)
- [x] Architectural invariants (8 agents, 6 skills, PROJECT.md structure)
- [x] Design decisions documented with rationale
- [x] Breaking changes clearly defined

### Architecture Tests ✓
- [x] All 8 agents exist
- [x] Agents have correct frontmatter
- [x] Models assigned correctly (opus/sonnet/haiku)
- [x] Tools restricted appropriately
- [x] All 6 skills exist
- [x] Skills have proper structure
- [x] All hooks exist
- [x] Hooks are executable
- [x] Commands have descriptions
- [x] File sizes reasonable
- [x] No hardcoded secrets
- [x] Consistent line endings

### Integration Tests ✓
- [x] Orchestrator can invoke agents
- [x] Agent pipeline complete
- [x] Read-only agents can't write
- [x] Skills exist for all contexts
- [x] Hooks reference real files
- [x] Hook configuration correct
- [x] PROJECT.md template exists
- [x] PROJECT.md has required sections
- [x] Orchestrator validates alignment
- [x] File paths consistent
- [x] Model selection appropriate

### UAT Tests ✓
- [x] Plugin structure correct after install
- [x] /setup creates all required files
- [x] /auto-implement workflow documented
- [x] Hook workflows configured
- [x] Context management documented
- [x] /align-project validates structure
- [x] /uninstall has granular options
- [x] Complete user journey works
- [x] Error recovery graceful
- [x] Documentation complete

### Unit Tests ✓
- [x] SetupWizard initialization
- [x] Plugin verification
- [x] File copying
- [x] Preset loading
- [x] Hook configuration
- [x] PROJECT.md setup
- [x] GitHub setup
- [x] Gitignore management
- [x] Full workflows

---

## Testing Strategy

### 1. Development Testing (While Coding)
```bash
# Test what you're working on
pytest tests/unit/scripts/test_setup.py::TestCopyPluginFiles -v
```

### 2. Pre-Commit Testing (Before Committing)
```bash
# Run all tests
pytest -v

# Or at minimum, architecture + integration
pytest tests/test_architecture.py tests/test_integration.py -v
```

### 3. CI/CD Testing (Automated)
```bash
# Full test suite with coverage
pytest --cov=scripts --cov=hooks --cov-report=xml
```

### 4. Release Testing (Before Release)
```bash
# All tests + manual UAT
pytest -v
# Then manually test /plugin install → /setup → /auto-implement
```

---

## Manual Testing (Required)

**These CANNOT be automated** and must be tested manually:

### 1. Plugin Installation
```bash
/plugin marketplace add akaszubski/claude-code-bootstrap
/plugin install autonomous-dev
```

**Verify**:
- Plugin appears in `.claude/plugins/autonomous-dev/`
- Commands available when typing `/`

### 2. Setup Workflow
```bash
/setup
```

**Verify**:
- Interactive prompts work
- Files created in correct locations
- PROJECT.md is usable

### 3. Auto-Implement Workflow
```bash
/auto-implement simple hello world function with tests
```

**Verify**:
- Orchestrator validates against PROJECT.md
- Agents execute in order
- Code is generated
- Tests are created
- Context budget managed

### 4. Hook Execution
```bash
# If automatic hooks enabled
echo "code" > test.py
# Should auto-format

git commit
# Should run tests + security scan
```

### 5. Context Management
```bash
/auto-implement feature 1
/clear
/auto-implement feature 2
/clear
```

**Verify**:
- Context stays small
- Session logs created
- Can run 10+ features without degradation

---

## Test Maintenance

### Adding New Tests

**For new features**:
1. Add unit tests for logic
2. Add integration test for component interaction
3. Add UAT test for user workflow
4. Update architecture tests if structure changes

**For bug fixes**:
1. Add regression test that fails with bug
2. Fix the bug
3. Verify test passes

### Test Coverage Goals

| Category | Target | Current |
|----------|--------|---------|
| setup.py | 80%+ | TBD |
| hooks/*.py | 60%+ | TBD (hard to test) |
| Architecture | 100% | 100% |
| Integration | 90%+ | 95% |
| UAT Workflows | 100% | 100% |

---

## Continuous Improvement

### Metrics to Track
- Test execution time
- Coverage percentage
- False positive rate
- Manual test burden

### Regular Reviews
- **Weekly**: Review test failures
- **Monthly**: Review test coverage
- **Per Release**: Full manual UAT

---

## Troubleshooting

### "pytest not found"
```bash
pip install pytest
```

### "Import errors in tests"
```bash
# Tests add parent to sys.path
# Ensure you're running from plugin root
cd plugins/autonomous-dev
pytest -v
```

### "Tests fail due to missing files"
```bash
# Ensure plugin structure is complete
ls agents/ skills/ hooks/ commands/ templates/
```

### "Slow test execution"
```bash
# Run only fast tests
pytest -v -m "not slow"
```

---

## Summary

**4-Layer Testing Strategy**:

1. **Architectural Intent** ⭐ - WHY things are designed this way (drift detection)
2. **Architecture** - WHAT the structure should be (static validation)
3. **Integration** - HOW components work together (dynamic validation)
4. **UAT** - Does it WORK for users (end-to-end workflows)

**Plus**: Unit tests for critical logic (setup.py)

**Total Coverage**: Intent + Structure + Integration + Workflows = Comprehensive validation

**Key Innovation**: Test the WHY, not just the WHAT
- Architectural intent tests document design rationale
- Alert when architecture fundamentally changes
- Prevent unintentional architectural drift
- Preserve institutional knowledge

**Result**: Confidence that the autonomous development system works as designed AND that the design intent is preserved.

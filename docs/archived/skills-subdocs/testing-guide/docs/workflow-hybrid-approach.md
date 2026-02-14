# Workflow Hybrid Approach

## Recommended Testing Workflow

### Development Phase

1. **Write unit tests** (pytest, fast feedback)
   ```bash
   pytest tests/unit/test_feature.py -v
   ```

2. **Write integration tests** (pytest, workflow validation)
   ```bash
   pytest tests/integration/test_feature.py -v
   ```

3. **Run all tests locally** (before commit)
   ```bash
   pytest -v
   ```

---

### Pre-Commit (Automated)

```bash
# .claude/hooks/pre-commit or CI/CD pipeline
pytest tests/unit/ tests/integration/ -v --tb=short
# Fast: < 10 seconds
# Automated: Catches obvious breaks
```

---

### Pre-Release (Manual)

1. **Run UAT tests** (complete workflows)
   ```bash
   pytest tests/uat/ -v
   ```

2. **GenAI architectural validation** (intent alignment)
   ```bash
   /validate-architecture
   ```

3. **Manual testing** (critical user paths)

---

## Hybrid Approach: Best of Both Worlds

### Example: Testing Orchestrator

#### Static Tests (pytest) - Layer 1

```python
# tests/test_architecture.py
def test_orchestrator_exists():
    """Test orchestrator agent file exists."""
    assert (agents_dir / "orchestrator.md").exists()

def test_orchestrator_has_task_tool():
    """Test orchestrator can coordinate agents."""
    content = (agents_dir / "orchestrator.md").read_text()
    assert "Task" in content
```

**Catches**: File deletion, obvious regressions
**Misses**: Whether orchestrator actually uses Task tool correctly

---

#### GenAI Validation (Claude) - Layer 4

```markdown
Read orchestrator.md. Validate:

1. Does it use Task tool to coordinate agents?
2. Does it coordinate in correct order (researcher → planner → test-master → implementer)?
3. Does it enforce TDD (tests before code)?
4. Does it log to session files for context management?

Look for actual implementation code (bash scripts, tool invocations),
not just descriptions.
```

**Catches**: Behavioral drift, incorrect usage, missing logic
**Provides**: Contextual assessment of quality and alignment

---

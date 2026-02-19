---
name: testing-guide
version: 2.0.0
type: knowledge
description: GenAI-first testing with structural assertions and congruence validation. Project-specific test patterns, anti-patterns, and tier structure.
keywords: test, testing, genai, congruence, judge, pytest, validation, coverage
auto_activate: true
allowed-tools: [Read, Grep, Glob, Bash]
---

# Testing Guide

What to test, how to test it, and what NOT to test — for a plugin made of prompt files, Python glue, and configuration.

## Philosophy: GenAI-First Testing

Traditional unit tests work for deterministic logic. But most bugs in this project are **drift** — docs diverge from code, agents contradict commands, component counts go stale. GenAI congruence tests catch these. Unit tests don't.

**Decision rule**: Can you write `assert x == y` and it won't break next week? → Unit test. Otherwise → GenAI test or structural test.

---

## Three Test Patterns

### 1. Judge Pattern (single artifact evaluation)

An LLM evaluates one artifact against criteria. Use for: doc completeness, security posture, architectural intent.

```python
pytestmark = [pytest.mark.genai]

def test_agents_documented_in_claude_md(self, genai):
    agents_on_disk = list_agents()
    claude_md = Path("CLAUDE.md").read_text()
    result = genai.judge(
        question="Does CLAUDE.md document all active agents?",
        context=f"Agents on disk: {agents_on_disk}\nCLAUDE.md:\n{claude_md[:3000]}",
        criteria="All active agents should be referenced. Score by coverage %."
    )
    assert result["score"] >= 5, f"Gap: {result['reasoning']}"
```

### 2. Congruence Pattern (two-source cross-reference)

The most valuable pattern. An LLM checks two files that should agree. Use for: command↔agent alignment, FORBIDDEN lists, config↔reality.

```python
def test_implement_and_implementer_share_forbidden_list(self, genai):
    implement = Path("commands/implement.md").read_text()
    implementer = Path("agents/implementer.md").read_text()
    result = genai.judge(
        question="Do these files have matching FORBIDDEN behavior lists?",
        context=f"implement.md:\n{implement[:5000]}\nimplementer.md:\n{implementer[:5000]}",
        criteria="Both should define same enforcement gates. Score 10=identical, 0=contradictory."
    )
    assert result["score"] >= 5
```

### 3. Structural Pattern (dynamic filesystem discovery)

No LLM needed. Discover components dynamically and assert structural properties. Use for: component existence, manifest sync, skill loading.

```python
def test_all_active_skills_have_content(self):
    skills_dir = Path("plugins/autonomous-dev/skills")
    for skill in skills_dir.iterdir():
        if skill.name == "archived" or not skill.is_dir():
            continue
        skill_md = skill / "SKILL.md"
        assert skill_md.exists(), f"Skill {skill.name} missing SKILL.md"
        assert len(skill_md.read_text()) > 100, f"Skill {skill.name} is a hollow shell"
```

---

## Anti-Patterns (NEVER do these)

### Hardcoded counts
```python
# BAD — breaks every time a component is added/removed
assert len(agents) == 14
assert hook_count == 17

# GOOD — minimum thresholds + structural checks
assert len(agents) >= 8, "Pipeline needs at least 8 agents"
assert "implementer.md" in agent_names, "Core agent missing"
```

### Testing config values
```python
# BAD — breaks on every config update
assert settings["version"] == "3.51.0"

# GOOD — test structure, not values
assert "version" in settings
assert re.match(r"\d+\.\d+\.\d+", settings["version"])
```

### Testing file paths that move
```python
# BAD — breaks on renames/moves
assert Path("plugins/autonomous-dev/lib/old_name.py").exists()

# GOOD — use glob discovery
assert any(Path("plugins/autonomous-dev/lib").glob("*skill*"))
```

**Rule**: If the test itself is the thing that needs updating most often, delete it.

---

## Test Tiers (auto-categorized by directory)

No manual `@pytest.mark` needed — directory location determines tier.

```
tests/
├── regression/
│   ├── smoke/           # Tier 0: Critical path (<5s) — CI GATE
│   ├── regression/      # Tier 1: Feature protection (<30s)
│   ├── extended/        # Tier 2: Deep validation (<5min)
│   └── progression/     # Tier 3: TDD red phase (not yet implemented)
├── unit/                # Isolated functions (<1s each)
├── integration/         # Multi-component workflows (<30s)
├── genai/               # LLM-as-judge (opt-in via --genai flag)
└── archived/            # Excluded from runs
```

**Where to put a new test**:
- Protecting a released critical path? → `regression/smoke/`
- Protecting a released feature? → `regression/regression/`
- Testing a pure function? → `unit/`
- Testing component interaction? → `integration/`
- Checking doc↔code drift? → `genai/`

**Run commands**:
```bash
pytest -m smoke                    # CI gate
pytest -m "smoke or regression"    # Feature protection
pytest tests/genai/ --genai        # GenAI validation (opt-in)
```

---

## GenAI Test Infrastructure

```python
# tests/genai/conftest.py provides two fixtures:
# - genai: Gemini Flash via OpenRouter (cheap, fast)
# - genai_smart: Haiku 4.5 via OpenRouter (complex reasoning)
# Requires: OPENROUTER_API_KEY env var + --genai pytest flag
# Cost: ~$0.02 per full run with 24h response caching
```

**Scaffold for any repo**: `/scaffold-genai-uat` generates the full `tests/genai/` setup with portable client, universal tests, and project-specific congruence tests auto-discovered by GenAI.

---

## What to Test vs What Not To

| Test This | With This | Not This |
|-----------|-----------|----------|
| Pure Python functions | Unit tests | — |
| Component interactions | Integration tests | — |
| Doc ↔ code alignment | GenAI congruence | Hardcoded string matching |
| Component existence | Structural (glob) | Hardcoded counts |
| FORBIDDEN list sync | GenAI congruence | Manual comparison |
| Security posture | GenAI judge | Regex scanning |
| Config structure | Structural | Config values |
| Agent output quality | GenAI judge | Output string matching |

---

## Hard Rules

1. **100% pass rate required** — ALL tests must pass, 0 failures. Coverage targets are separate.
2. **Tests before implementation** — write failing tests, then implement.
3. **Regression test for every bug fix** — named `test_regression_issue_NNN_description`.
4. **No test is better than a flaky test** — if it fails randomly, fix or delete it.
5. **GenAI tests are opt-in** — `--genai` flag required, no surprise API costs.

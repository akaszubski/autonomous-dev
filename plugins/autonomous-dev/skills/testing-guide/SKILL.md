---
name: testing-guide
description: "GenAI-first testing with structural assertions, congruence validation, and tier-based test structure. Use when writing tests, setting up test infrastructure, or validating coverage. TRIGGER when: test, pytest, coverage, TDD, test patterns, congruence, validation. DO NOT TRIGGER when: production code implementation, documentation, config-only changes."
allowed-tools: "Read, Grep, Glob, Bash"
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

### Analytic Rubric Pattern (decomposed per-criterion evaluation)

More reliable than holistic scoring. Each criterion is evaluated independently with a binary MET/UNMET judgment. Use for: security posture, enforcement quality, multi-faceted assessments.

```python
def test_security_posture_analytic(self, genai):
    result = genai.judge_analytic(
        question="Evaluate the security posture of this codebase",
        context=f"Hook samples:\n{hook_content[:5000]}",
        criteria=[
            {"name": "No hardcoded secrets", "description": "No real API keys or tokens in source", "max_points": 1},
            {"name": "Named exit codes", "description": "Hooks use named constants, not bare numbers", "max_points": 1},
            {"name": "Path validation", "description": "File operations validate paths", "max_points": 1},
        ],
    )
    assert result["total_score"] >= 2, f"{result['total_score']}/{result['max_score']}: {result['reasoning']}"
```

**Return value**: `{"criteria_results": [...], "total_score": N, "max_score": N, "pass": bool, "band": str, "reasoning": str}`

**When to use**: Multi-faceted evaluations where you need to know which specific criteria passed or failed. Each criterion gets its own LLM call for independent judgment.

### Consistency Check Pattern (multi-round agreement)

For high-stakes judgments where a single LLM evaluation might be unreliable. Runs multiple rounds and checks for agreement. Uses median score as the final result.

```python
def test_pipeline_completeness_consistent(self, genai):
    result = genai.judge_consistent(
        question="Does implement.md define a complete SDLC pipeline?",
        context=f"implement.md:\n{content[:6000]}",
        criteria="Pipeline should have research, plan, test, implement, review, security, docs steps.",
        rounds=3,
    )
    assert result["final_score"] >= 7, f"median={result['final_score']}, agreement={result['agreement']}"
```

**Return value**: `{"rounds": [...], "agreement": bool, "scores": [...], "final_score": median, "pass": bool, "band": str, "reasoning": str}`

**When to use**: Critical assessments where false positives/negatives are costly. Agreement=False signals the evaluation needs human review.

### Temperature Guidance

All `ask()` calls default to `temperature=0` for deterministic, reproducible judging. Override only when you need creative/diverse outputs:

```python
# Default: temperature=0 (deterministic judging)
response = genai.ask("Evaluate this code", temperature=0)

# Override for creative tasks like edge case generation
response = genai.ask("Generate unusual test inputs", temperature=0.7)
```

### 3. Cross-Validation Pattern (two sources that must match)

No LLM needed. When two configs/files must stay in sync, read both and compare directly. Catches the #1 recurring bug class: adding something to one place but not the other.

```python
def test_policy_and_hook_in_sync(self):
    """Policy always_allowed and hook NATIVE_TOOLS must be identical."""
    policy_tools = set(json.load(open(POLICY_FILE))["tools"]["always_allowed"])
    hook_tools = hook.NATIVE_TOOLS
    # Check BOTH directions
    assert policy_tools - hook_tools == set(), f"In policy not hook: {policy_tools - hook_tools}"
    assert hook_tools - policy_tools == set(), f"In hook not policy: {hook_tools - policy_tools}"
```

**When to use**: Any time two files define overlapping data — permissions↔hook, manifest↔disk, config↔worktree copy, command frontmatter↔policy.
**Key principle**: Read both sources dynamically. Never hardcode expected values in the test itself.

### 4. Structural Pattern (dynamic filesystem discovery)

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

### 5. Property-Based Pattern (hypothesis invariants)

Define properties that must always hold, instead of testing specific examples. Catches 23-37% more bugs than example-based tests. Use for: pure functions, serialization, data transformations, parsers.

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_preserves_elements(arr):
    """Invariant: sorting never loses or adds elements."""
    result = sorted(arr)
    assert set(result) == set(arr)
    assert len(result) == len(arr)

@given(st.dictionaries(st.text(min_size=1), st.text()))
def test_config_roundtrip(config):
    """Invariant: serialize → deserialize = identity."""
    assert json.loads(json.dumps(config)) == config
```

**When to use**: Pure functions, roundtrips, idempotent operations, parsers.
**When NOT to use**: Agent prompts (use GenAI judge), filesystem checks (use structural).

#### PBT Candidate Selection — When to Use Property-Based Testing

**Good candidates** (pure functions with testable invariants):
- Input validation functions (validate_agent_name, validate_message, sanitize_*)
- Scoring/normalization functions (normalize_severity, compute_priority)
- Serialize/deserialize roundtrips (settings fix-then-validate, JSON encode/decode)
- Set operations and state machines (circuit breaker threshold, denial counts)
- Mathematical functions with known identities (Fibonacci recurrence)
- Parsers with structural guarantees (acceptance criteria extraction)

**Bad candidates** (avoid PBT for these):
- Agent prompt behavior — use GenAI judge tests instead; Hypothesis cannot meaningfully generate LLM prompts
- File system operations — use structural tests with tmp_path; filesystem side effects break Hypothesis shrinking
- Config values with fixed schemas — use structural tests; config is a fixed schema, not a property space
- Network/API calls — mock these in unit tests; PBT should test pure computation only

**Strategy rules**:
- Define all strategies as module-level constants (never inline in test functions)
- Use `.filter()` instead of `assume()` for filtering invalid inputs
- Always add `@example()` decorators with known edge cases alongside `@given()`

#### Hypothesis Profile Configuration

Configure profiles via `HYPOTHESIS_PROFILE` environment variable:

```bash
# Default (local development): 50 examples per test
pytest tests/property/ -v

# CI mode: 200 examples per test, no deadline
HYPOTHESIS_PROFILE=ci pytest tests/property/ -v
```

Profiles are registered in `tests/property/conftest.py`:
- `default`: `max_examples=50` (fast local iteration)
- `ci`: `max_examples=200`, `deadline=None` (thorough CI runs)

### 6. Runtime Integration Testing Patterns (subprocess, network, filesystem)

When code invokes external operations whose correctness depends on **runtime context** (CWD, environment variables, credentials, file permissions), assert on the **kwargs**, not just the cmd-list or return value. Static-shape tests (asserting `cmd == ["claude", "-p", prompt]`) silently pass even when `cwd=` or `env=` is wrong — and shipped Issue #1064 through a full 8-agent pipeline.

**The principle**: capture the full kwargs dict via `monkeypatch`, then assert on the specific runtime variable that affects correctness.

```python
def test_subprocess_passes_cwd_to_avoid_context_bleed(monkeypatch) -> None:
    """Regression test: must pass cwd= so the spawned subprocess does not
    inherit the parent's CWD."""
    captured_kwargs: dict = {}

    def fake_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="...", stderr=""
        )

    monkeypatch.setattr("mymodule.subprocess.run", fake_run)
    my_function_under_test(...)

    # Assert on the RUNTIME KWARG, not just the cmd-list
    assert "cwd" in captured_kwargs, "subprocess.run must receive cwd="
    assert captured_kwargs["cwd"] == str(Path.home()), (
        f"cwd must be Path.home() (got {captured_kwargs['cwd']!r})"
    )
```

**When to use this pattern**:

- Any `subprocess.run` / `subprocess.Popen` whose correctness depends on `cwd`, `env`, `timeout`, `input`, or `stdin`.
- Any network call whose correctness depends on env-provided credentials, base URLs, proxy settings, or TLS context.
- Any filesystem operation whose correctness depends on `Path.cwd()` or relative-path resolution.

**Anti-pattern to avoid**:

```python
# BAD — passes even when cwd is wrong, which is the bug Issue #1064 was
def test_subprocess_invokes_claude(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")
    monkeypatch.setattr("mymodule.subprocess.run", fake_run)
    result = my_function_under_test(...)
    # ↓ This static-shape assertion misses the entire CWD bug class.
    assert result.returncode == 0
```

**Reference example**: `tests/unit/scripts/test_extract_and_label_intent_corpus.py::test_call_claude_p_judge_passes_cwd_to_avoid_project_context` (regression test for Issue #1064, the bug that motivated this pattern).

**Pipeline integration**: The plan-critic agent's **Operational Integration Test** axis enforces this pattern at plan time. Plans introducing subprocess/network/fs calls must specify either a kwarg-assertion test (this pattern) or an integration smoke test — score 1 if neither is specified.

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

### Hardcoded intermediary lists (the worst anti-pattern)
```python
# BAD — test has its OWN copy of expected data, drifts from both real sources
VALID_TOOLS = {"Read", "Write", "Edit"}  # stale copy in test
EXPECTED_COMMANDS = {"implement.md": {"Read", "Write"}}  # another stale copy
assert actual_tools == VALID_TOOLS  # passes even when BOTH sources are wrong

# GOOD — cross-validate real sources directly against each other
policy_tools = set(json.load(open(POLICY_FILE))["tools"]["always_allowed"])
hook_tools = hook.NATIVE_TOOLS
assert policy_tools == hook_tools, f"Drift: policy-only={policy_tools - hook_tools}"

# BEST — add GenAI test to catch gaps in BOTH sources
result = genai.judge(
    question="Are any known tools missing from this list?",
    context=json.dumps(sorted(hook_tools)),
    criteria="Check against known Claude Code native tools..."
)
```

**Rule**: When two configs must stay in sync, read both dynamically and compare. Never create a third copy in the test — that's three things that can drift instead of two.

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

### Negative-assertion scope locks (lock audit exclusions)

**Rule**: When an audit produces an "affected files" list and some files are intentionally **excluded** after manual review (false positives), write a parametrized negative-assertion test that locks the exclusion. Without it, the next audit cycle re-flags the same files and the team re-litigates the decision.

**Trigger when**: an issue body lists files audited but intentionally not modified.

The test asserts the audit's marker string is *absent* from each excluded file, so any future "fix" to one of these files trips the test instead of slipping through. Each parametrize entry MUST be accompanied by a comment (or docstring section) explaining WHY this file is excluded — the lock is only useful if a future reader can quickly verify whether the exclusion still holds.

```python
# GOOD — negative-assertion scope lock with per-file rationale
@pytest.mark.parametrize(
    "file_path",
    [
        "plugins/autonomous-dev/lib/error_analyzer.py",      # Excluded: ErrorAnalyzer != GenAIAnalyzer
        "plugins/autonomous-dev/lib/codebase_analyzer.py",   # Excluded: CodebaseAnalyzer != GenAIAnalyzer
    ],
)
def test_audit_false_positive_files_unchanged(file_path: str) -> None:
    """Lock Issue #1007 audit: these files do NOT call GenAIAnalyzer.

    Each file is excluded because its name superficially matches the audit
    pattern but the code does not. Catches future re-flagging.
    """
    content = (REPO_ROOT / file_path).read_text()
    assert "from genai_utils import GenAIAnalyzer" not in content, (
        f"{file_path} now imports GenAIAnalyzer — re-verify Issue #1007 audit."
    )

# BAD — comment-only exclusion (drifts; no enforcement)
# Issue #1007 audit: skip error_analyzer.py, codebase_analyzer.py (false positives).
# (Next agent ignores the comment and "fixes" one of them.)
```

**Reference**: `tests/unit/lib/test_phase3_wrap_adoption.py::test_phase3_false_positive_files_unchanged` and the `Negative-Assertion Scope Locks` subsection in `docs/TESTING-STRATEGY.md` (Layer 2).

---

## Test Tiers — Diamond Model (auto-categorized by directory)

No manual `@pytest.mark` needed — directory location determines tier. Source of truth: `plugins/autonomous-dev/lib/tier_registry.py`.

| Tier | Lifecycle | Directory | Markers | Max Duration |
|------|-----------|-----------|---------|--------------|
| T0 | permanent | `tests/genai/` | genai, acceptance | - |
| T0 | permanent | `tests/regression/smoke/` | smoke | 5s |
| T1 | stable | `tests/e2e/` | e2e, slow | 5min |
| T1 | stable | `tests/integration/` | integration | 30s |
| T2 | semi-stable | `tests/regression/regression/` | regression | 30s |
| T2 | semi-stable | `tests/regression/extended/` | extended, slow | 5min |
| T2 | semi-stable | `tests/property/` | property, slow | 5min |
| T3 | ephemeral | `tests/regression/progression/` | progression, tdd_red | - |
| T3 | ephemeral | `tests/unit/` | unit | 1s |
| T3 | ephemeral | `tests/hooks/` | hooks, unit | 1s |
| T3 | ephemeral | `tests/security/` | unit | 1s |

**Lifecycle definitions**:
- **permanent**: Never delete. Critical path validation and acceptance criteria.
- **stable**: Delete only if the feature being tested is removed from the product.
- **semi-stable**: Prune after 90 days unused. Feature regression protection.
- **ephemeral**: Prune freely. Implementation-coupled tests that change with the code.

**Where to put a new test**:
- Protecting a released critical path? -> `regression/smoke/`
- Protecting a released feature? -> `regression/regression/`
- Testing a pure function? -> `unit/`
- Testing component interaction? -> `integration/`
- Full workflow end-to-end? -> `e2e/`
- Checking doc-to-code drift? -> `genai/`

**Run commands**:
```bash
pytest -m smoke                    # CI gate (T0)
pytest -m "smoke or regression"    # Feature protection (T0+T2)
pytest -m "not slow"               # Fast tests only
pytest tests/genai/ --genai        # GenAI validation (opt-in, T0)
```

---

## Tier Selection Criteria

**Target distribution ratio** (5:2:2:1 for T3:T2:T1:T0) — balanced coverage across the test pyramid. Monitored by `enforce_tier_distribution.py` hook (Issue #908).

### Tier Selection Decision Tree

```
START: What are you testing?
│
├─ User-facing acceptance criteria from the plan?
│  └─> T0 (tests/genai/ or tests/regression/smoke/)
│
├─ Critical user workflow or deployment smoke test?
│  └─> T0 (tests/regression/smoke/)
│
├─ Full end-to-end scenario with multiple components?
│  └─> T1 (tests/e2e/)
│
├─ Component interaction (2-3 modules talking)?
│  └─> T1 (tests/integration/)
│
├─ Released feature protection against regression?
│  └─> T2 (tests/regression/regression/)
│
├─ Property-based invariant testing?
│  └─> T2 (tests/property/)
│
├─ Pure function in isolation?
│  └─> T3 (tests/unit/)
│
├─ TDD red-green cycle or implementation detail?
│  └─> T3 (tests/unit/ or tests/regression/progression/)
│
└─ Hook, security boundary, or internal validation?
   └─> T3 (tests/hooks/ or tests/security/)
```

### Common Tier Misclassification Patterns

**Pattern 1: "Everything is a unit test"**
- **Wrong**: Testing pipeline execution in `tests/unit/test_pipeline.py`
- **Right**: Move to `tests/integration/test_pipeline.py` (component interaction)

**Pattern 2: "Too many smoke tests"**
- **Wrong**: Every new feature gets a smoke test
- **Right**: Only critical paths and deployment verification get T0 smoke tests

**Pattern 3: "Regression tests for internal refactoring"**
- **Wrong**: Adding to `tests/regression/regression/` for internal API changes
- **Right**: Use `tests/unit/` for implementation-coupled tests that change with code

**Pattern 4: "GenAI tests for deterministic logic"**
- **Wrong**: Using `genai.judge()` to test `2 + 2 == 4`
- **Right**: Use assert for deterministic; GenAI for congruence/drift detection

**Pattern 5: "Integration tests that mock everything"**
- **Wrong**: `tests/integration/test_db.py` that mocks the entire database
- **Right**: Either use real DB (integration) or move to unit tests if testing in isolation

**Cross-reference**: This tier guidance supports the test pyramid health monitoring from Issues #908/#886/#887.



### When to write T0 tests (acceptance, permanent)
- Testing acceptance criteria from the plan
- Validating critical user-facing workflows
- Protecting against doc-to-code drift
- Smoke tests for deployment verification
- **Target**: ~10% of tests

### When to write T1 tests (integration, stable)
- Testing interaction between 2+ components
- Validating API contracts between modules
- End-to-end workflow tests
- Database/filesystem integration points
- **Target**: ~20% of tests

### When to write T2 tests (regression, semi-stable)
- Protecting against known bug recurrence
- Feature-level regression prevention
- Edge case coverage for released features
- Performance regression tests
- **Target**: ~20% of tests

### When to write T3 tests (unit, ephemeral)
- Testing pure functions in isolation
- Implementation detail verification
- TDD red-green cycles
- Hook validation tests
- Security boundary checks
- **Target**: ~50% of tests

**Anti-pattern**: Writing only T3 unit tests (bottom-heavy). While unit tests are valuable for development, a test suite with 90%+ unit tests lacks integration coverage and user workflow validation.

**Balance warning**: The tier distribution gate warns when:
- Upper tiers (T0+T1+T2) represent less than 25% of total tests
- Any tier drifts more than 50% from its target ratio

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
| Two configs in sync | Cross-validation | Hardcoded intermediary list |
| Component existence | Structural (glob) | Hardcoded counts |
| FORBIDDEN list sync | GenAI congruence | Manual comparison |
| Security posture | GenAI judge | Regex scanning |
| Config structure | Structural | Config values |
| Agent output quality | GenAI judge | Output string matching |

---

## Test-to-Issue Tracing Convention (Issue #675)

Link tests to GitHub issues for traceability. The `TestIssueTracer` library (`plugins/autonomous-dev/lib/test_issue_tracer.py`) scans for these patterns automatically.

### Supported Reference Patterns

| Pattern | Example | Type |
|---------|---------|------|
| Class name | `class TestIssue656:` | class_name |
| Function name | `def test_issue_589_regression():` | function_name |
| Docstring | `"""Regression for #656"""` | docstring |
| Comment | `# Issue: #656` | comment |
| GH shorthand | `GH-42` | gh_shorthand |
| Pytest marker | `@pytest.mark.issue(656)` | marker |

### Convention Rules

- **Regression tests MUST** reference the issue they protect (e.g., `class TestIssue656` or `# Fixes #656`)
- **Feature tests SHOULD** reference the implementing issue (e.g., docstring `"""Implements #675"""`)
- **Unit tests MAY** reference issues when the test covers a specific bug or feature

### Usage

```python
# Quick check: does an issue have a test?
from test_issue_tracer import TestIssueTracer
tracer = TestIssueTracer(Path('.'))
tracer.check_issue_has_test(675)  # True/False

# Full analysis report
report = tracer.analyze()
print(report.format_table())
```

Run via `/audit --test-tracing` for a full tracing report.

---

## Spec-Blind Validation Pattern

An independent agent writes behavioral tests from the spec/acceptance criteria ONLY, without seeing the implementation code or implementer output. This catches cases where the implementation satisfies its own tests but drifts from the original specification.

**Isolation rules**:
- The spec-validator receives ONLY: acceptance criteria, feature description, changed file paths, PROJECT.md scope
- The spec-validator MUST NOT receive: implementer output, code diffs, reviewer feedback, research findings, planner rationale
- Tests are placed in `tests/spec_validation/` (separate from unit tests in `tests/unit/`)

**Test placement**: `tests/spec_validation/test_spec_{feature_name}.py`

**Complementarity with other test types**:
- **Unit tests** (implementer): Test internal logic, edge cases, error paths
- **Spec-validation tests** (spec-validator): Test observable behavior against spec criteria
- **Mutation testing**: Tests whether test suite catches code mutations (code quality)
- **GenAI tests**: Semantic evaluation using LLM-as-Judge

The spec-validator adds value because it is structurally blind to implementation details. Even if the implementer writes comprehensive unit tests, those tests are influenced by HOW the code was written. The spec-validator tests WHAT the spec requires.

**Verdict**: Binary only. `SPEC-VALIDATOR-VERDICT: PASS` or `SPEC-VALIDATOR-VERDICT: FAIL`. No partial credit.

---

## Mutation Testing

Mutation testing validates that your tests actually catch real bugs, not just exercise code paths. Coverage metrics give false confidence; mutation testing proves test quality.

### What It Is

mutmut introduces small code changes (mutants) — flipping `<` to `<=`, `True` to `False`, `+` to `-` — and checks if your tests detect them. If a test suite still passes after a mutation, that mutant "survived" and your tests have a gap.

### When to Use

- After reaching 80%+ coverage on a module, to verify test quality
- When reviewing critical security or state-management code
- As a complement to the diamond test model (mutation testing measures test effectiveness, not code coverage)

### How to Run

```bash
# Run against three critical files (default)
bash scripts/run_mutation_tests.sh

# Run against a single file
bash scripts/run_mutation_tests.sh --file plugins/autonomous-dev/lib/pipeline_state.py

# Run in CI mode (summary output, non-blocking)
bash scripts/run_mutation_tests.sh --ci

# Run against all of lib/
bash scripts/run_mutation_tests.sh --all
```

### Score Targets

- **70%+ mutation score** on critical files (`pipeline_state.py`, `tool_validator.py`, `settings_generator.py`)
- Focus on killing conditional, arithmetic, and boolean mutants
- Do NOT chase equivalent mutants (see below)

### Equivalent Mutant Triage

Not all surviving mutants indicate test gaps. Some mutations produce functionally equivalent code:

**Low-value (skip these)**:
- String literal changes (`"error"` to `"XXerrorXX"`) — rarely affects behavior
- Magic number changes (unless they are thresholds)
- Return value mutations on void-like functions

**High-value (kill these)**:
1. **Conditional mutations** (`<` to `<=`, `==` to `!=`) — missing boundary tests
2. **Arithmetic mutations** (`+` to `-`, `*` to `/`) — missing calculation tests
3. **Boolean mutations** (`True` to `False`, `and` to `or`) — missing logic tests

### Integration with Diamond Test Model

Mutation testing is orthogonal to the test tier system. It measures test quality (do tests catch bugs?) rather than test coverage (does code run?). Use it as a quality-of-tests metric:

- **Unit tests** (T3): Primary targets for mutation testing — pure functions with clear boundaries
- **Integration tests** (T1): Less useful for mutation testing — too slow per mutant
- **GenAI tests** (T0): Not applicable — mutation testing targets deterministic logic only

---

## Hard Rules

1. **100% pass rate required** — ALL tests must pass, 0 failures. Coverage targets are separate.
2. **Specification-driven** — tests define the contract; implementation satisfies it.
3. **0 new skips** — `@pytest.mark.skip` is forbidden for new code. Fix it or adjust expectations.
4. **Regression test for every bug fix** — named `test_regression_issue_NNN_description`.
5. **No test is better than a flaky test** — if it fails randomly, fix or delete it.
6. **GenAI tests are opt-in** — `--genai` flag required, no surprise API costs.
7. **Property over example** — prefer `hypothesis` invariants over hardcoded input/output pairs where applicable.

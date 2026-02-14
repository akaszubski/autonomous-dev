---
name: scaffold-genai-uat
description: "Scaffold GenAI UAT tests (LLM-as-judge) into the current repo"
argument-hint: "[--force] [--skip-congruence]"
allowed-tools: [Task, Read, Write, Edit, Bash, Grep, Glob]
---

# /scaffold-genai-uat - GenAI UAT Test Scaffolding

Scaffold LLM-as-judge UAT tests into the current repo. Generates portable test infrastructure with universal tests and project-specific congruence tests discovered via GenAI.

## What This Creates

```
tests/genai/
├── __init__.py
├── conftest.py                    # GenAIClient (OpenRouter, caching, cost tracking)
├── test_doc_completeness.py       # CLAUDE.md quality, README consistency, TODO volume
├── test_security_posture.py       # Secrets scan in source + config files
├── test_config_audit.py           # Version consistency across config files
├── test_congruence.py             # Project-specific cross-reference tests (GenAI-discovered)
└── .genai_cache/                  # Response cache (gitignored)
```

Plus updates to: `pytest.ini` (genai marker), `.gitignore` (.genai_cache/)

**Time**: 1-2 minutes
**Cost**: $0 (scaffolding only — tests cost ~$0.02/run when executed with --genai)

ARGUMENTS: {{ARGUMENTS}}

---

## Implementation

Invoke the researcher agent for congruence pair discovery. Execute file scaffolding directly using Read, Write, Edit, Glob, Grep, and Bash tools.

### STEP 0: Parse Arguments

Parse ARGUMENTS for flags:
- `--force`: Overwrite existing tests/genai/ (backs up first)
- `--skip-congruence`: Skip GenAI-powered congruence test discovery

---

### STEP 1: Check Prerequisites

1. Verify we're in a git repo root (look for .git/)
2. Check if tests/genai/ already exists:
   - If exists and no `--force`: Report what's there and ask user if they want to update
   - If exists and `--force`: Back up to tests/genai.backup-{timestamp}/
   - If not exists: Proceed
3. Check for CLAUDE.md (recommended but not required)

---

### STEP 2: Discover Project Structure

Read the repo to understand what tests to generate. Collect:

```python
structure = {
    "has_claude_md": bool,       # CLAUDE.md exists
    "has_readme": bool,          # README.md exists
    "has_project_md": bool,      # PROJECT.md or .claude/PROJECT.md exists
    "python_project": bool,      # *.py files exist
    "has_agents": [],            # .claude/agents/*.md or agents/*.md
    "has_commands": [],          # .claude/commands/*.md or commands/*.md
    "has_hooks": [],             # .claude/hooks/*.py or hooks/*.py
    "has_config_files": [],      # *.json, *.yaml, *.toml with version fields
    "has_package_json": bool,
    "has_pyproject": bool,
    "key_python_files": [],      # Important-looking .py files (config, models, defaults)
}
```

Use Glob and Read tools to discover this. Look in both plugin-style paths (plugins/*/agents/) and flat paths (agents/).

---

### STEP 3: Copy Template Files

The template files live in the plugin at `plugins/autonomous-dev/templates/genai-uat/` (or `.claude/templates/genai-uat/` if installed).

**3A: Create directory and copy portable files**

Create `tests/genai/` directory. Copy these files VERBATIM from templates:
- `__init__.py` (empty)
- `conftest.py` (GenAIClient — identical in every repo)
- `test_doc_completeness.py` (CLAUDE.md quality, README consistency, TODO/FIXME, dead code)
- `test_security_posture.py` (secrets scan in source + config)
- `test_config_audit.py` (version consistency)

Use the Read tool to read each template file, then Write tool to create in tests/genai/.

**3B: Update pytest.ini**

If pytest.ini exists, add genai marker if not present:
```
genai: GenAI-powered UAT tests (may incur API costs, requires --genai flag)
```

Also add `--genai` option registration if conftest.py pytest_addoption isn't sufficient.

If pyproject.toml is used instead, add equivalent config.

**3C: Update .gitignore**

Add if not present:
```
# GenAI test cache
tests/genai/.genai_cache/
```

---

### STEP 4: Discover Congruence Pairs (GenAI-Powered)

**Skip this step if `--skip-congruence` flag is set.**

This is the most valuable part. Use the Task tool to launch a general-purpose agent (subagent_type="general-purpose") with this prompt:

```
Analyze this project's file structure and identify cross-reference congruence test pairs.

Project structure:
{structure from STEP 2}

Key files discovered:
{list of important files}

For each pair, identify:
1. File A path and what it defines
2. File B path and what it should agree with
3. What property to cross-reference
4. Why drift would be a bug

Return as JSON array:
[{
  "file_a": "path/to/file_a.py",
  "file_b": "path/to/file_b.md",
  "property": "agent list",
  "test_name": "test_agents_in_code_match_docs",
  "question": "Do the agents defined in code match the agents documented?",
  "criteria": "All agents in code should appear in docs and vice versa."
}]

Focus on pairs where drift is LIKELY and IMPACTFUL. Prioritize:
- Code ↔ documentation (counts, lists, paths)
- Config ↔ config (versions, defaults across files)
- Implementation ↔ specification (what code does vs what docs say)

Limit to 5-8 high-value pairs.
```

Then generate `tests/genai/test_congruence.py` from the discovered pairs. Each pair becomes a test function that reads both files and calls `genai.judge()`.

---

### STEP 5: Generate Congruence Test File

From the pairs discovered in STEP 4, generate `tests/genai/test_congruence.py`:

```python
"""GenAI UAT: Cross-reference congruence tests.

Auto-generated by /scaffold-genai-uat based on project structure analysis.
These tests validate that files which should agree actually do.
"""

import pytest
from pathlib import Path
from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]


class TestCongruence:
    def test_{test_name}(self, genai):
        """{description}"""
        file_a = (PROJECT_ROOT / "{file_a}").read_text()[:3000]
        file_b = (PROJECT_ROOT / "{file_b}").read_text()[:3000]

        result = genai.judge(
            question="{question}",
            context=f"**{file_a_name}:**\n{file_a}\n\n**{file_b_name}:**\n{file_b}",
            criteria="{criteria}"
        )
        assert result["score"] >= 5, f"Congruence drift: {result['reasoning']}"
```

Each discovered pair becomes one test method. Include a header comment noting these were auto-discovered and can be manually edited.

---

### STEP 6: Verify and Report

1. Run `pytest tests/genai/ --collect-only` to verify tests collect without errors
2. Count total tests generated

Report:
```
GenAI UAT tests scaffolded successfully!

  tests/genai/
  ├── conftest.py              (GenAIClient + fixtures)
  ├── test_doc_completeness.py (4 tests)
  ├── test_security_posture.py (2 tests)
  ├── test_config_audit.py     (1 test)
  └── test_congruence.py       (N tests - auto-discovered)

  Total: X tests

  Updated: pytest.ini, .gitignore

  Next steps:
  1. pip install openai          (if not installed)
  2. export OPENROUTER_API_KEY=your_key
  3. pytest tests/genai/ --genai  (run tests, ~$0.02)
  4. Edit test_congruence.py to add/remove pairs

  Get an API key: https://openrouter.ai/settings/keys
```

---

## Error Handling

### tests/genai/ already exists (no --force)
```
tests/genai/ already exists with N files.

Options:
  /scaffold-genai-uat --force    Backup and regenerate
  Edit tests manually             Keep existing, add tests by hand
```

### No CLAUDE.md found
```
Warning: No CLAUDE.md found. Some tests will be skipped at runtime.
Recommendation: Create CLAUDE.md with project overview for full test coverage.
Continuing with available tests...
```

### Congruence discovery fails
```
Warning: Congruence pair discovery failed (LLM error or no API key).
Created universal tests only. Add congruence tests manually or retry:
  /scaffold-genai-uat --force
```

---

## Usage

```bash
# Standard scaffolding (with congruence discovery)
/scaffold-genai-uat

# Skip congruence discovery (faster, no LLM needed)
/scaffold-genai-uat --skip-congruence

# Force regeneration (backs up existing)
/scaffold-genai-uat --force

# Force + skip congruence
/scaffold-genai-uat --force --skip-congruence
```

---
name: skill-eval
description: "Measure skill effectiveness — behavioral delta from skill injection"
argument-hint: "[--quick] [--skill name] [--update]"
allowed-tools: [Bash]
user-invocable: true
user_facing: true
---

# Skill Effectiveness Evaluation

Measure whether skills actually change model behavior — quantifies the behavioral delta from skill injection using LLM-as-judge scoring.

## Implementation

ARGUMENTS: {{ARGUMENTS}}

Parse the ARGUMENTS for optional flags and pass them through to the script:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
ARGS="{{ARGUMENTS}}"
bash "$REPO_ROOT/scripts/skill-effectiveness-check.sh" $ARGS
```

## Usage

```bash
/skill-eval                          # Full report (all skills)
/skill-eval --quick                  # Degradation check only (2 prompts/skill)
/skill-eval --skill python-standards # Single named skill
/skill-eval --update                 # Full run + update baselines
```

## Prerequisites

- `OPENROUTER_API_KEY` environment variable set
- `openai` pip package installed (`pip install openai`)

## Cost Estimates

| Mode | Approximate Cost |
|------|-----------------|
| Full run | ~$0.50–1.00 (5 skills × 5 prompts × 5 criteria × 2 variants) |
| Quick run (`--quick`) | ~$0.15–0.30 (5 skills × 2 prompts) |
| Single skill (`--skill`) | ~$0.05–0.10 |

## What Each Mode Does

- **Full** (default): Runs all skills through the complete prompt × criteria matrix, produces a report with per-skill behavioral delta scores, and compares against saved baselines.
- **`--quick`**: Runs only 2 prompts per skill — enough to detect significant regressions without the full cost. Use for pre-commit or rapid sanity checks.
- **`--skill <name>`**: Restricts evaluation to a single named skill (e.g. `python-standards`, `testing-guide`). Useful when iterating on one skill.
- **`--update`**: Runs the full evaluation then writes new baseline files. Use after intentional skill improvements to accept the new behavior as the reference point.

## Related

- `/scaffold-genai-uat` — Bootstraps LLM-as-judge test infrastructure
- `/audit --genai` — Full GenAI UAT audit including skill coverage gaps

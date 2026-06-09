---
topic: plan-freshness-reverification-step-4-8-1175
created: 2026-06-09
updated: 2026-06-09
sources:
  - plugins/autonomous-dev/commands/implement.md
  - plugins/autonomous-dev/agents/plan-critic.md
  - plugins/autonomous-dev/lib/pipeline_completion_state.py
  - plugins/autonomous-dev/lib/research_persistence.py
  - tests/unit/commands/test_pre_validated_plan_detection.py
  - https://developer.hashicorp.com/terraform/intro/core-workflow
  - https://developer.hashicorp.com/terraform/tutorials/automation/automate-terraform
  - https://arxiv.org/html/2502.04955v1
  - https://www.tenki.cloud/blog/github-actions-workflow-lockfiles
  - https://medium.com/@atnoforgenai/10-ai-agent-frameworks-you-should-know-in-2026-langgraph-crewai-autogen-more-2e0be4055556
---

# plan-freshness-reverification-step-4-8-1175

## Local Research (Codebase)

1. STEP 4.5 (implement.md:650-662): research-completeness inline check (no agent) — precedent for STEP 4.8
2. STEP 4.7 (implement.md:664-678): pre-validated plan detection — sets PRE_VALIDATED_PLAN_PATH + PRE_VALIDATED_PLAN_CONTENT; both 'Verdict: PROCEED' and '**PROCEED**' formats accepted
3. STEP 5 (implement.md:680-698): planner; when PRE_VALIDATED_PLAN_PATH set, prepends 'refine not re-scope' directive
4. STEP 5.5a (implement.md:704-716): independent re-search of .claude/plans/, skips plan-critic if PROCEED, records skip via pipeline_completion_state.record_plan_critic_skipped()
5. tests/unit/commands/test_pre_validated_plan_detection.py: regex-based assertions on implement.md content (pattern for new STEP 4.8 tests)
6. Existing mtime/TTL patterns: 'if time.time() - mtime < 3600' appears 4x in implement.md (3600s default for sentinel)
7. 5.5c structural validation uses regex `[\w/.-]+\.(py|md|json|yaml|sh|ts|js)` to extract file paths from plan — reusable for claim extraction

## Web Research (External Sources)

1. Terraform plan/apply is the canonical precedent for plan-staleness TOCTOU. Terraform itself fails loudly at apply rather than re-verifying — but for a coordinator pipeline, failing at implementation time is too late. STEP 4.8 re-verification before implementer runs is the correct preventive layer.
2. NO agent framework (LangChain/LangGraph/CrewAI/AutoGen) provides built-in plan re-verification — Issue #1175 is novel contribution, no off-the-shelf library to invoke.
3. Regex claim extraction is superior to NLP/LLM extraction for this use case: lower latency, deterministic, claim types are structurally predetermined (function-exists, file-contains, count-is, coverage-gap). The codebase already uses regex for plan content extraction successfully (5.5c).
4. Hash-pinning of referenced files (analogous to terraform.lock.hcl) is technically viable but over-engineered for first cut. Use mtime + grep-verify as the primary approach.
5. Security: claim-pattern-exhaustion bypass — treat 0 claims in non-trivial plan (word count > 200) as soft warning, fall back to default file-existence checks for paths in plan.

## Sources

- [plugins](plugins/autonomous-dev/commands/implement.md)
- [plugins](plugins/autonomous-dev/agents/plan-critic.md)
- [plugins](plugins/autonomous-dev/lib/pipeline_completion_state.py)
- [plugins](plugins/autonomous-dev/lib/research_persistence.py)
- [tests](tests/unit/commands/test_pre_validated_plan_detection.py)
- [developer.hashicorp.com](https://developer.hashicorp.com/terraform/intro/core-workflow)
- [developer.hashicorp.com](https://developer.hashicorp.com/terraform/tutorials/automation/automate-terraform)
- [arxiv.org](https://arxiv.org/html/2502.04955v1)
- [www.tenki.cloud](https://www.tenki.cloud/blog/github-actions-workflow-lockfiles)
- [medium.com](https://medium.com/@atnoforgenai/10-ai-agent-frameworks-you-should-know-in-2026-langgraph-crewai-autogen-more-2e0be4055556)

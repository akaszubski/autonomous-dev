---
topic: claude-p single-judge corpus refactor
created: 2026-05-08
updated: 2026-05-08
sources:
  - scripts/extract_and_label_intent_corpus.py
  - tests/unit/scripts/test_extract_and_label_intent_corpus.py
  - tests/regression/test_intent_classifier_corpus.py
  - docs/INTENT-CLASSIFICATION.md
  - tests/fixtures/intent_classifier_real_corpus.json
  - https://code.claude.com/docs/en/headless
  - https://code.claude.com/docs/en/cli-reference
  - https://code.claude.com/docs/en/authentication
  - https://code.claude.com/docs/en/costs
  - https://github.com/anthropics/claude-code/issues/24317
  - https://github.com/anthropics/claude-code/issues/38022
---

# claude-p single-judge corpus refactor

## Local Research (Codebase)

1. Two-judge code: _call_anthropic_judge (scripts/extract_and_label_intent_corpus.py:611-652), _call_openrouter_judge (655-715), label_prompts_with_two_judges (772-877).
2. Schema fields: id, prompt, label, source, judge_a, judge_b, redactions_applied, holdout (line ~820+).
3. Unit tests mock _call_anthropic_judge and _call_openrouter_judge: tests/unit/scripts/test_extract_and_label_intent_corpus.py at lines 217, 246, 274, 301, 333.
4. Regression tests gate on OPENROUTER_API_KEY env var: tests/regression/test_intent_classifier_corpus.py:245, 309. Schema fields asserted: judge_a, judge_b.
5. Doc methodology text: docs/INTENT-CLASSIFICATION.md:276-280 and 393-396 -- two-judge unanimous agreement (Anthropic + non-Anthropic via OpenRouter).
6. CostTracker at line 722 -- /bin/zsh.50 cap, /bin/zsh.005/call. Becomes irrelevant with single-judge subscription claude -p.

## Web Research (External Sources)

1. claude -p --output-format json envelope: {type, subtype, result, session_id, total_cost_usd, usage, is_error}. result field contains text response.
2. --model accepts haiku/sonnet/opus aliases or full names (claude-haiku-4-5-20251001).
3. --bare REQUIRES ANTHROPIC_API_KEY -- does NOT read CLAUDE_CODE_OAUTH_TOKEN (GitHub #38022).
4. Without --bare: subscription OAuth works, sequential-only due to refresh token race (GitHub #24317). Concurrent invocations corrupt ~/.claude/.credentials.json.
5. Subscription users: claude -p counts against plan, no per-call billing. API key users: billed per token (~/bin/zsh.001-0.005/call with Haiku).
6. stdin accepted via subprocess input= param (avoids shell quoting). Use --max-turns 1 for single-turn classification.
7. Recommended: subprocess.run([claude, -p, --output-format, json, --model, M, --max-turns, 1, --no-session-persistence], input=user_msg, text=True, capture_output=True, timeout=60). Skip --bare when user has subscription OAuth.
8. Security: shell=False (default), pass prompt via stdin not argv, never put API key in argv, validate envelope[is_error]==False before parsing result field.

## Sources

- [scripts](scripts/extract_and_label_intent_corpus.py)
- [tests](tests/unit/scripts/test_extract_and_label_intent_corpus.py)
- [tests](tests/regression/test_intent_classifier_corpus.py)
- [docs](docs/INTENT-CLASSIFICATION.md)
- [tests](tests/fixtures/intent_classifier_real_corpus.json)
- [code.claude.com](https://code.claude.com/docs/en/headless)
- [code.claude.com](https://code.claude.com/docs/en/cli-reference)
- [code.claude.com](https://code.claude.com/docs/en/authentication)
- [code.claude.com](https://code.claude.com/docs/en/costs)
- [github.com](https://github.com/anthropics/claude-code/issues/24317)
- [github.com](https://github.com/anthropics/claude-code/issues/38022)

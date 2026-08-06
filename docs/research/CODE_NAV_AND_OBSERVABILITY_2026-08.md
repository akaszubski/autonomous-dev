# Code Navigation & Observability — Research Findings (2026-08-06)

Deep-research harness output (6 angles, 25 sources, 118 claims → 23 confirmed 3-0, 2 refuted).
Two features evaluated for the autonomous-dev harness under hard constraints: **local-first, $0,
OSS/MIT, no code/prompt egress, Python (pyright/pylsp), macOS/multi-Mac, Python 3.14.3, per-repo
`.mcp.json`**.

Prior-art anchor: **CodeGraphContext (CGC)** — a graph-DB code-index MCP — was tried in realign +
spektiv and shelved (FalkorDB SIGABRT on Py3.14 → KuzuDB; indexer then wedged at 2.2GB RAM / 10min /
0 progress on both repos). All CGC traces since removed (pipx pkg, `~/.codegraphcontext`,
spektiv `.cgcignore` + doc notes). See memory `code_index_cgc_shelved.md`.

---

## Q1 — Code navigation / structure search (replace grep for structure)

**Recommendation: live-query LSP-based MCP, not a built index.**

- **Top pick — Serena** (`github.com/oraios/serena`, MIT): LSP-backed MCP; tools = `find_symbol`
  (goToDefinition), `find_referencing_symbols` (findReferences), symbol overview (documentSymbol),
  find declaration, find implementations; 40+ languages incl. Python. Documents Claude Code setup;
  ships an "Opus 4.6 in Claude Code on a large Python codebase" testimonial (vendor-curated — treat
  as evidence of *support*, not perf proof). Built on multilspy → Solid-LSP.
- **Lighter fallback — `mcp-language-server`** (`github.com/isaacphi/mcp-language-server`): thin
  wrapper, 6 tools (definition, references, diagnostics, hover, rename_symbol, edit_file), Python
  via **pyright**.
- **Why this beats CGC (confirmed 3-0):** both live-query the language server on demand — no
  persistent graph — so they *structurally* avoid the build-wedge + staleness class that shelved
  CGC. CGC's issue is the architecture (on-disk graph + `cgc watch` file-watcher), not a bug.
- **Refuted (0-3):** a related graph tool ("codegraph/velr") claimed git-keyed incremental reindex
  + debounced watcher to escape staleness — **both claims failed adversarial verification**. The
  "smarter index" escape hatch does not exist; live-query is the real answer.
- **ast-grep / tree-sitter**: complementary — structural pattern search (parses on demand, no index),
  good for lint-like rules grep can't express. Keep as a secondary tool, not the primary nav.

### Two sharpening points
1. **The honest gap:** no source measured Serena/mcp-language-server startup time or peak RAM on a
   ~700-file repo; one blog warns Serena's **first symbolic call can stall long enough to look like a
   wedge**. The CGC failure bar (startup, peak RAM, wedge-or-not, call-chain correctness) MUST be
   measured in a pilot, not assumed.
2. **Python 3.14 risk mostly evaporates with pyright:** CGC died on a native Py-3.14 `.so` (FalkorDB).
   **pyright is a Node/TypeScript server** — it analyzes Python but doesn't run *on* your Python, so
   it's immune to that crash class. Prefer the **pyright** backend over pylsp for this reason.

### Pilot plan (against the CGC bar)
- Wire Serena (pyright backend) via **per-repo `.mcp.json`** (never global — 5-10K tokens/turn) on
  autonomous-dev itself.
- Measure: cold-start time, peak + steady-state RAM, does the first symbolic call wedge, correctness
  on real call-chain questions (find all callers of X; where is Y defined; impact of changing Z).
- Pass bar: no wedge, RAM well under the 2.2GB CGC figure, correct call-chain answers.

---

## Q2 — Observability + evals platform

**Recommendation: do NOT adopt LangSmith. Emit OpenTelemetry → self-hosted Arize Phoenix
(or self-hosted Langfuse). Keep home-grown evals as the scoring layer on top.**

- **LangSmith is out (confirmed):** cloud-only self-serve (self-host = Enterprise add-on), ships
  traces to LangChain infra → direct conflict with local-first/$0/no-egress.
- **Big finding (3-0, official Anthropic docs):** Claude Code / claude-agent-sdk **emit OpenTelemetry
  natively** — 3 signals (metrics + log events GA; traces beta behind
  `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`), exportable via OTLP to any backend.
- **Multi-agent traces (3-0):** subagent (Task-tool) runs **nest into one trace** — subagent
  `llm_request`/tool spans nest under the parent `claude_code.tool` span; W3C context
  (TRACEPARENT/TRACESTATE) auto-propagated. This is the multi-agent trace UI LangSmith was wanted for.
- **Emit layer:** OpenTelemetry GenAI semantic conventions (vendor-neutral) → no backend lock-in.
  (Still Development/experimental as of mid-2026; receipt is guaranteed but render quality varies, so
  use a GenAI-aware UI.)
- **Backend A — Arize Phoenix (recommended):** first-party
  `openinference-instrumentation-claude-agent-sdk` + `arize-phoenix-otel`; default endpoint
  `127.0.0.1:6006`, **zero egress**; AGENT spans w/ prompt/result, session/model metadata, token
  counts, tool child spans via hook injection.
- **Backend B — self-hosted Langfuse:** official OpenInference-based Claude Agent SDK integration;
  Docker self-host (same codebase as cloud, internet optional); richer datasets/evals product surface.
- **Reuse, don't replace:** keep the labeled reviewer benchmark, `/skill-eval`, CIA analyst, and
  hook-timing baselines as the **scoring layer**; feed them trace data. Reuse OTel for *tracing*.

### Caveat
Claude Code trace export AND OTel GenAI semconv are both **beta** (span names may churn); metrics +
log events are GA. Pilot expecting churn on the trace path.

### Pilot plan
- `pip install openinference-instrumentation-claude-agent-sdk arize-phoenix-otel`; point at local
  Phoenix; record one `/implement` run; judge the multi-agent trace UI + whether spans carry enough
  to drive span-level evals.

---

## Q3 — Non-deterministic agent evals (best practice)

Second deep-research pass (2026-08-06, 106 agents, 12 findings all 3-0, peer-reviewed sources; 2
claims refuted). **We already do the two hardest things right** (deterministic+judge split in
`/skill-eval`; metric-over-dataset gate in the reviewer benchmark) — best practice is generalizing
those, not replacing them.

### Metrics & flaky-gate control
- **Gate on `pass^k` (all-k-succeed = consistency), NOT `pass@1`.** pass@1 massively overstates
  reliability (GPT-4o 61% single-attempt → <25% at k=8 on tau-bench). `pass@k` = best-case
  (at-least-one), `pass^k` = reliability (all-k). **Notation hazard:** the widely-copied "61% vs 25%
  pass@k" is mislabeled — the collapse metric is `pass^k`. Implement/label both correctly or gates are
  meaningless.
- **Gate on an aggregate metric over a dataset with a statistical band**, never one run's number. Use
  the **scientific-validation skill** to power-analyze `n` (samples) and the acceptance band. (The
  reviewer benchmark already does the dataset-level part.)

### LLM-as-judge reliability (the load-bearing caveats)
- **Report Cohen's κ / Krippendorff's α as the headline, never raw agreement** — exact-match
  overstates chance-corrected agreement by **33–41 pp** (MT-Bench, ~541K judgments).
- **Don't report test-retest reliability alone** — high reproducibility coexists with severe bias
  (the "consistency–bias paradox": a judge can be 0.99 reproducible and among the least valid).
- **Validate every judge on ≥2 benchmarks** — judge quality is not transferable (rank shifts up to
  **15 positions** across benchmarks). Treat the reviewer benchmark as one label distribution among
  several.
- **Style/format bias is the dominant, under-audited bias** (magnitude 0.10–0.76, far exceeding
  position bias ≤0.04) — a judge favors markdown over identical plain prose. Audit for it.
- **Mitigations that work:** (a) **panel/jury of judges from DIFFERENT providers** (cancels
  family-specific self-preference; 3 small judges beat 1 large at ~7× lower cost — extends our
  cross-model judge #1329); (b) **prompt-level debiasing** — a mid-tier model + debiasing prompt hit
  the *highest* agreement of any config (71%, κ=0.549) at ~15× lower cost than a frontier judge
  (TMLR 2026, peer-reviewed).

### Datasets / contamination
- **CapBencher**: publish golden sets with a capped Bayes accuracy + a one-sided binomial test (UMP
  by Karlin-Rubin) — anything exceeding the cap is a statistical alarm for leakage/gaming. Apply to
  the reviewer/skill-eval golden sets.

### Trajectory / process evals (the bridge from Q2)
- **Group OpenInference tool-call spans per trace and score the ordered sequence** — Phoenix
  trajectory eval (LLM-judge classifies the whole trajectory, or a **deterministic path/edit-distance
  convergence** check). Catches between-step mistakes that outcome-only evals miss. This is the direct
  payoff of #1452: once traces are in Phoenix, evals run over spans (tool choice, pipeline adherence),
  not just final answers — a trace-native version of what the CIA analyst does today.
- **Behavioral-collapse detector:** sliding-window entropy over the tool-call sequence (Meltdown
  Onset Point) flags when an agent goes incoherent — feeds directly off the OTel trace pipeline.

### Tooling (local-first/OSS ranking)
- **DeepEval = top fit** — runs LLM evals AS pytest tests (`assert_test()` / `deepeval test run`),
  handles flakiness natively (`flaky=True` reports the score without failing the build), and does
  **component/span-level** evals. Integrates with our existing pytest/CI.
- **Phoenix / Langfuse** (from #1452) = the trajectory-eval layer over OTel/OpenInference traces.
- **CRITICAL no-egress gotcha:** DeepEval and Phoenix LLM-judge metrics **call hosted model APIs by
  default** — point them at a **local/self-hosted judge model** or they violate $0/no-egress.
- **Wrap, don't replace:** keep the reviewer benchmark, `/skill-eval`, and CIA as the scoring layer;
  add DeepEval for new per-case + span evals and Phoenix for trajectory evals.

### Refuted (0-3)
- "A single judge flips its verdict ~35% under minor prompt variations" — refuted.
- "There are exactly four in-context judge prompt formats" — refuted.

### Concrete adoption path (reuses existing evals)
1. Add `pass^k` + statistical-band gating to the existing evals (power-analyze `n` via
   scientific-validation).
2. Move judges to a **diverse-provider panel + debiasing prompt**, calibrated against human labels
   (report κ); point at a **self-hosted judge** for no-egress.
3. Add **DeepEval** as the pytest-native harness for new per-case/span evals (keep home-grown scoring).
4. After Phoenix (#1452) is up: **trajectory evals** over OpenInference spans (tool order, pipeline
   adherence) + MOP entropy collapse detector.
5. Apply **CapBencher** cap to golden sets to self-police contamination.

---

## Open questions (require empirical pilots, not more search)
1. Measured startup/RAM/wedge behavior of Serena vs mcp-language-server on ~700-file Python repo,
   Py 3.14.3, M3/M4 — vs the CGC bar.
2. Does pyright-langserver run cleanly under 3.14.3 on realign + spektiv (the CGC-failure repos)?
3. Phoenix vs self-hosted Langfuse real footprint on a Mac (RAM/containers/disk) + which ingests the
   claude-agent-sdk OpenInference spans better for multi-agent UI.
4. Which home-grown evals to re-express as Phoenix/Langfuse datasets+evaluators vs keep as-is and
   merely feed trace data.

## Primary sources
- github.com/oraios/serena · github.com/isaacphi/mcp-language-server ·
  github.com/CodeGraphContext/CodeGraphContext
- code.claude.com/docs/en/agent-sdk/observability · opentelemetry.io/blog/2026/genai-observability/
- arize.com/docs/phoenix/integrations/python/claude-agent-sdk · langfuse.com/integrations/frameworks/claude-agent-sdk

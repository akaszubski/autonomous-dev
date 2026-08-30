---
covers:
  - .claude/PROJECT.md
  - plugins/autonomous-dev/commands/
  - plugins/autonomous-dev/hooks/
---

# Maintaining the Core Philosophy

**Last Updated**: 2026-08-30
**Version**: v3.51.0

---

## Overview

This guide explains what you need to keep updated as you improve and iterate to maintain the core philosophy:

> **"Trust the model, enforce via hooks, enhance via agents"**

**Read that line precisely — 2026-08-30.** It means *trust the model's capability, never its
adherence*. Claude does not lack the ability to do the work; it lacks the judgement about when
the rules apply to itself, forgets between sessions, and rationalises around prose in both
directions. So the sentence is not "trust the model, therefore fewer controls" — it is "the model
is capable enough that the only thing worth spending effort on is what refuses it."

Read the other way, the line contradicts the thesis below and has been misread that way: the
archived material in `docs/archived/` uses "Trust the model" to argue for *removing*
prescriptiveness. That argument applies to agent prompts, not to gates.

The section below is the thesis this guide serves, and PROJECT.md points here for it
("Rationale, failure taxonomy and history", "Cases"). Everything after "The Golden Rule" is
maintenance mechanics — a different topic, kept for reference.

---

## WHAT THIS PROJECT IS

*Added 2026-08-30. Recorded here because it existed only in session transcripts, which are not
a carrier — the same failure this whole document is about.*

### The one-line version

**Policy as code, for software development itself.** Not policy as documentation that a
diligent reader might follow, but policy compiled into things that refuse.

### The layering

Four layers, and the distinction between them is the whole design:

| Layer | What it is | Where it lives | Binds by |
|---|---|---|---|
| **Macro policy** | Directional intent for the repo — what this repo is *for*, what it will not do | `.claude/PROJECT.md` | Being read by the alignment gate on every `/implement` run |
| **Situational policy** | Narrow, machine-readable rules for one decision class | `config/*.json` — `auto_approve_policy.json`, `hard_floor_hooks.json`, `sandbox_policy.json` | Being loaded by a control at decision time |
| **Controls** | Code that refuses | `hooks/*.py` returning `{"decision": "block"}` | Executing on a lifecycle event |
| **Assurance** | Evidence that the controls ran and worked | proof artifacts, ratchets, reachability walks | Refusing when the evidence is absent |

PROJECT.md is the **macro policy** — the governing directional intent, one per repo, same
mechanism across every repo (`autonomous-dev`, `realign`, `spektiv`, `homeassistant`,
`vllm-mlx`), different content in each. For *this* repo the direction is: improve how software
development is done. One of the controls exists specifically to enforce alignment with that
macro policy — that is the alignment gate at pipeline STEP 2, and it is why PROJECT.md is a
**gate input, not documentation**.

The corollary, learned the hard way: **only statements capable of refusing belong in
PROJECT.md.** Counts drift. Values like "less is more" are self-answerable. Feature
inventories become permission lists that permit everything by omission. On 2026-08-30 the gate
refused twice and cited the Mission both times — not one of the 17 SCOPE IN bullets, which
were compressed to 9 the same day for exactly that reason.

### Why controls and not instructions

Adherence cannot be assumed, and the reason is specific rather than general. The operator:

- forgets between sessions (context does not persist),
- rationalises around prose **in both directions** (the same rule was argued for and against
  within one hour of a single session),
- and asserts what it has not verified.

So each step is administered by something that *refuses*. A rule that can be argued either way
is not a mechanism. What binds behaviour is what refuses, not what is known — and knowing is
stored in prose, the same carrier that keeps failing.

### Why assurance and not trust

The controls themselves drift, die, and misreport. Measured 2026-08-30: a shipped guard was
dead four independent ways and **its own test suite agreed with it**. An unwired artifact is
byte-for-byte indistinguishable from a wired one — file present, tests green, manifest entry,
deployed. Hence the two questions in PROJECT.md's DEFINITION OF DONE (Q1 connected, Q2 works
as designed, both arms).

### Carrier ranking

When a rule must hold, put it in the strongest available carrier. In descending order of force:

1. **Hooks** — execute, refuse, ship to every consumer repo
2. **Agent definitions** — ship, and are read at dispatch, but are prose
3. **Tests** — real, but repo-local; `install_manifest.json` ships **zero** `tests/` paths, so
   they reach no consumer
4. **Prose** (CLAUDE.md, PROJECT.md body, command markdown) — reaches nowhere mechanically

The standing rule follows directly: **a finding that can refuse becomes a guard, not an
issue.** Filing has run 4.5x ahead of resolving (114 opened / 25 closed in 7 days, 290 open),
so a net-positive 7-day issue delta is itself an abort condition on the active goal.

---

## THE ERROR TAXONOMY

The five ways this system's operator gets things wrong. Every control here targets one of
them; a proposed control that targets none is probably not needed.

| # | Failure | Shape | What catches it |
|---|---|---|---|
| 1 | **Looks instead of runs** | Reports what code *appears* to do rather than what it does when executed. Reads source, asserts on comments, treats a `print` as a gate. | Driving the real function; both arms; a positive **and** a negative control |
| 2 | **Hallucinates** | Confident, specific, wrong — a line number, a symbol, a closed issue that does not exist | Citation verification; adversarial review; `file:line` receipts |
| 3 | **Reads stale as current** | A once-true statement, still believed. "This gate has never fired" — written when true, quoted long after it stopped being true | Dated claims with a check; staleness bounds that are *enforced*, not documented |
| 4 | **Locally valid, globally wrong** | Each step correct, the composition wrong. A fix that narrows scope to pass; a guard scoped to the instance that prompted it | A negative control of a **different shape** than the triggering bug; call-boundary audits |
| 5 | **Ordinary mistakes** | Typos, wrong variable, dropped block during transcription | Tests, types, the gate that reads the artifact rather than the narration |

**The defect shape that recurs most:** *a check whose subject is the description rather than
the behaviour.* Six instances in one session on 2026-08-28 — a rule written into an unwired
gate; a flag reintroducing the very default it was fixing; a recorder measuring the declared
rather than the enforced budget; a fallback test comparing X to X; a deploy script passing
"deny rules syntactically valid" on an **empty** deny list. None was caught by whoever made
it. Every one was caught by a ratchet, an adversarial reviewer, or the user.

---

## CASE LOG

Concrete instances, with receipts. New cases append here.

### 2026-08-30 — the four-defect pipeline run

A single `/implement` run on a ~55-line change was BLOCKED at the plan gate. Four false
load-bearing claims were caught before any code was written:

1. Research asserted "the only artifact reader is an undeployed example." False —
   `agents/continuous-improvement-analyst.md:345` reads both files as real CLI arguments, and
   `commands/implement-batch.md:202` is a fourth writer. *Caught by: planner.*
2. Research placed a `try` block at line 2366, making placement a genuine dilemma. It opens at
   **2354**; the dilemma did not exist. *Caught by: planner.*
3. The plan asserted `.claude/logs/activity/validators/` "does not exist in this repo" and
   rejected a design alternative on that basis. One `ls` showed **14 run directories, 19
   artifacts, and 2 empty directories** — the last being the defect itself, already on disk.
   *Caught by: coordinator, by checking.*
4. The plan closed its central problem by arguing the completion record is written by the
   SubagentStop hook, "a different principal" from the coordinator — the SLSA L1→L2 separation.
   False: `commands/implement.md:181` and `:237` **mandate that the coordinator itself** call
   `record_agent_completion()`, and the exemption at `:233` covers only doc-master. The same
   principal writes both the claim and the evidence. *Caught by: plan-critic.*

Claim 4 is the instructive one. It was not a slip; it was a **plausible, well-cited, entirely
wrong** justification that made a weak check look strong — failure mode 2 wearing failure mode
4's clothes. It survived a planner and a coordinator and died to an adversarial reader with
file access.

The run also produced a *smaller* design: a byte-and-line threshold calibrated against an
imagined corpus misclassified **6 of 19 real artifacts** (32%) as absent, including a complete
OWASP audit that happened to be on one line. The defensible check turned out to be
`is_file() and st_size > 0`. **The evidence made the change smaller, not larger** — which is
the outcome PROJECT.md's minimalism gate exists to produce and rarely does.

### 2026-08-30 — the guard that was dead four ways

`PreToolUseWrite-protect-sensitive.sh`: six independent defects, five of them fail-open. It
read `.parameters.file_path` where the payload carries `.tool_input.file_path`, so it saw
nothing. Its own test suite passed. Measured after the fix: 0/12 wrong on fixed source versus
9/12 on the deployed copy. Q1 (connected) and Q2 (both arms) would each have caught this
alone; neither existed for shell hooks.

### 2026-08-30 — a gate misfiring on its own subject matter

`unified_pre_tool.py:8074` matches the substring `"git commit"` anywhere in a Bash command
string, including inside heredoc **data**. Consequence: a pipeline whose feature text is
*about* the commit gate cannot write its own feature file. Proven with a matched pair —
identical heredocs differing only in `commit` versus `git commit`; the first wrote, the second
was blocked. Failure mode 4: locally valid (detect commits), globally wrong (detects the
words, not the act).

---

## ⚠️ STALENESS BOUNDARY — everything below this line

**Audited 2026-08-30. Treat the rest of this file as untrusted until each section is checked.**

Everything above was written or corrected on 2026-08-30. Everything below dates from
**2025-11-03** and describes an earlier architecture. Three classes of error were found and only
partially fixed, so the boundary is marked rather than pretended away:

1. **Archived components described as live.** The `orchestrator` agent was replaced by the thin
   coordinator (#444) and now lives at `agents/archived/orchestrator.md`. It is still named
   ~30 times below. Its one dedicated section has been rewritten; the scattered mentions have
   **not**. PROJECT.md's *Archived code rule* forbids active content referencing archived
   components, so each remaining mention is a live defect.
2. **Stale counts.** Corrected where found ("19 agents" → 17 on disk; "19 skills" → 21;
   "8 commands" → 26). Counts should not appear here at all — CLAUDE.md gives
   [`ARCHITECTURE-OVERVIEW.md`](ARCHITECTURE-OVERVIEW.md) as their single home, because two homes
   is how they drift. Any count you find below is unverified.
3. **`vim <protected path>` instructions.** Several update patterns below tell you to directly
   edit `agents/*.md`, `hooks/*.py` or `lib/*.py`. **INV-4 forbids this** — those paths are
   implementer-only and the hard floor holds even under `.claude/.bypass`. Route such changes
   through `/implement`. The instructions predate the invariant.

*Why this boundary is marked instead of the file being rewritten: a 950-line rewrite is a
separate change with its own review, and deleting content whose intent has not been read is the
failure mode described in the CASE LOG above. Marking the boundary removes the harm — acting on
stale instructions — at a fraction of the risk.*

---

## The Golden Rule

### UPDATE PROJECT.md FIRST, EVERYTHING ELSE FOLLOWS

- **PROJECT.md** = Source of truth for alignment
- **orchestrator** reads it before any feature work
- **Hooks** validate against it on every commit
- **Agents** reference it for context
- **Documentation** mirrors it automatically

**If these get out of sync, the philosophy breaks.**

---

## Priority Matrix: What to Update When

### 🔴 ALWAYS Update (Critical Path)

These are the backbone of the system. Update these first:

#### 1. **PROJECT.md** (Most Critical)

**Location**: `.claude/PROJECT.md`

**When to update:**
- Strategy or direction changes
- New goals added or completed
- Scope boundaries shift (in-scope vs out-of-scope)
- New constraints emerge (technical, business, compliance)
- Architecture decisions made

**Why critical:**
- The alignment gate at pipeline STEP 2 reads it on every `/implement` run and can refuse
  (`lib/alignment_classifier.py`; Stage 0 is deterministic and its ESCALATE cannot be overridden)
- `unified_doc_validator.py` hook checks commits against it
- Every pipeline agent receives its GOALS and SCOPE as context
- This IS the alignment mechanism

*Corrected 2026-08-30: this list previously named the `orchestrator` agent, which is archived
(`agents/archived/orchestrator.md`) and was replaced by the thin coordinator (#444); and asserted
"all 19 agents", a count that was wrong (17 on disk) and that CLAUDE.md forbids restating outside
[`ARCHITECTURE-OVERVIEW.md`](ARCHITECTURE-OVERVIEW.md) because two homes is how counts drift.*

**Example workflow:**
```bash
# Strategy change: Moving from REST to GraphQL

# 1. UPDATE PROJECT.md FIRST
vim .claude/PROJECT.md
# Update SCOPE section:
#   In Scope: GraphQL API endpoints
#   Out of Scope: REST API (deprecated)

# 2. Commit the strategic change
git add .claude/PROJECT.md
git commit -m "docs: update scope to GraphQL architecture"

# 3. NOW implement features
# orchestrator will validate new features against GraphQL scope
# Hooks will enforce GraphQL patterns
# Documentation will stay aligned
```

**Sections to maintain:**
```markdown
## GOALS
- Your primary objectives (what success looks like)
- Success metrics (how you measure progress)

## SCOPE
### In Scope
- Features you're building (what's allowed)

### Out of Scope
- Features to avoid (what's NOT allowed)

## CONSTRAINTS
- Technical constraints (languages, frameworks, platforms)
- Business constraints (budget, timeline, team size)
- Compliance constraints (security, privacy, regulations)

## ARCHITECTURE
- Current architecture decisions
- Technology stack
- Design patterns

### INVARIANTS (Issue #1467)
- Load-bearing properties that a proposed change may not silently contradict
- A change touching one of these is an architecture delta, not routine scope — it requires explicit sign-off, not a routine SCOPE edit
- Optional: repos with no INVARIANTS subsection are never architecture-delta-blocked by the alignment gate
```

**Placement matters**: the `### INVARIANTS` subsection MUST live **under `## ARCHITECTURE`** and each invariant MUST be a `- **INV-N — Property.** explanation` bullet. `parse_project_md` only searches for invariants inside the captured ARCHITECTURE block and only captures `- ` bullets — a section placed at the top level, or written as a numbered list, parses to `has_invariants=False` and does NOT activate the gate (this is the safe default a fresh template ships with, Issue #1489).

**Deriving invariants** (`/align --project --invariants`): rather than hand-authoring, derive them from evidence. Method:

- **Evidence sources** (strongest first): runtime enforcement (hooks returning `{"decision": "block"}`, fail-closed guards, HMAC/signature checks), contract tests, CI gates, policy/config files (allowlists, hard floors, sandbox policy), then PROJECT.md/README/CLAUDE.md stated guarantees and git-log "never do X" corrections. An *enforced* property is a real invariant; a merely *stated* one is aspirational.
- **Candidate schema**: `INV-N | property | EVIDENCE (file/mechanism/test) | would-VIOLATE example`. The would-VIOLATE example is what makes an invariant testable — if you cannot name a concrete change that would break it, it is probably not load-bearing.
- **Intended-but-unenforced tag**: a property with no enforcing hook/test is tagged `(intended, not yet enforced)` so the map distinguishes guarantees the system actually holds from ones it merely aspires to.
- **Idempotent audit**: once invariants exist, re-running the command audits drift (does each cited evidence still resolve?) and proposes additive/corrective deltas only — it never duplicates.

See [`plugins/autonomous-dev/commands/align.md`](../plugins/autonomous-dev/commands/align.md) "INVARIANTS Derivation & Audit" for the full approval-gated flow.

#### 2. **implement.md** (Coordination Behaviour)

> **Rewritten 2026-08-30.** This section previously documented `orchestrator.md` as the live
> gatekeeper and instructed the reader to `vim plugins/autonomous-dev/agents/orchestrator.md`.
> That agent is **archived** (`plugins/autonomous-dev/agents/archived/orchestrator.md`) — it was
> replaced by the thin coordinator in #444. Following the old instruction would have edited a
> nonexistent file, and PROJECT.md's *Archived code rule* says active content must never
> reference archived components. The instruction also violated INV-4.

**Location**: `plugins/autonomous-dev/commands/implement.md`

**When to update:** step ordering or gate placement changes; a new specialist joins the pipeline;
a FORBIDDEN clause needs adding after a bypass is observed.

**Why critical:**
- It defines the 8-step pipeline and every HARD GATE position
- It is what the coordinator executes; there is no separate orchestrator agent
- Its FORBIDDEN lists are the record of previously-observed bypasses

**How to update — this is the part that changed:**

`commands/*.md` is **protected infrastructure under INV-4**: never edited outside `/implement`,
and the hard floor holds even under `.claude/.bypass`. There is no `vim` path.

```bash
# Correct: route the change through the pipeline that owns the file
/implement "add a FORBIDDEN clause to implement.md STEP N covering <the observed bypass>"
```

**And prefer a guard over prose.** A FORBIDDEN clause in `implement.md` is advisory text — INV-1
says that is never enforcement, and the failure log in the CASE LOG above is largely a log of
advisory text being rationalised around. If the rule can be checked mechanically, the change
belongs in a hook or a `lib/` gate, not here. Adding prose to this file is the fallback when it
genuinely cannot.

#### 3. **settings.local.json** (Enforcement Rules)

**Location**: `.claude/settings.local.json`

**When to update:**
- Enable/disable strict mode
- Add new quality gates (PreCommit hooks)
- Change enforcement priorities
- Performance tuning (disable expensive hooks during dev)
- Feature flag adjustments

**Why critical:**
- Controls which hooks run (enforcement)
- Contains customInstructions (Claude's behavior)
- Defines when orchestrator is triggered
- Sets quality gate thresholds

**Critical sections:**
```json
{
  "customInstructions": "STRICT MODE: When user requests feature...",
  "hooks": {
    "UserPromptSubmit": [
      {
        "description": "Auto-detect feature requests",
        "hooks": [{
          "type": "command",
          "command": "python .claude/hooks/detect_feature_request.py"
        }]
      }
    ],
    "PreCommit": [
      {
        "description": "Quality gates",
        "hooks": [
          {"command": "python .claude/hooks/unified_doc_validator.py || exit 1"},
          {"command": "python .claude/hooks/unified_structure_enforcer.py || exit 1"},
          {"command": "python .claude/hooks/unified_code_quality.py || exit 1"}
        ]
      }
    ]
  }
}
```

**Iteration pattern:**
```bash
# During development: Disable strict enforcement
vim .claude/settings.local.json
# Change: "command": "python .claude/hooks/enforce_orchestrator.py || exit 1"
# To:     "command": "true"  # Placeholder (does nothing)

# After testing: Enable enforcement
# Change back to actual hook command

# Production: Full enforcement with all hooks enabled
```

---

### 🟡 FREQUENTLY Update (Quality Path)

Update these as you discover better patterns:

#### 4. **Agent Prompts** (Behavior Tuning)

**Location**: `plugins/autonomous-dev/agents/*.md`

**When to update:**
- Agent behavior not matching expectations
- New patterns discovered through usage
- Better prompts found through experimentation
- Skills need to be referenced differently

**Key agents to watch:**
- `orchestrator.md` - Coordination logic (most critical)
- `alignment-validator.md` - PROJECT.md checking logic
- `reviewer.md` - Quality standards enforcement
- `security-auditor.md` - Security pattern detection
- `implementer.md` - Code generation patterns
- `test-master.md` - TDD workflow

**Update pattern:**
```bash
# 1. Identify issue
# Agent not using skills? Not invoking sub-agents? Wrong decisions?

# 2. Review session log
cat docs/sessions/$(ls -t docs/sessions/*agent-name*.md | head -1)

# 3. Update agent prompt
vim plugins/autonomous-dev/agents/agent-name.md

# 4. Test behavior
# Invoke agent manually or via /implement

# 5. Verify improvement
# Check session log for updated behavior
```

#### 5. **GenAI Prompts** (Decision Accuracy)

**Location**: `plugins/autonomous-dev/hooks/genai_prompts.py`

**When to update:**
- Hook decisions are inaccurate (false positives/negatives)
- New classification categories needed
- Better prompt engineering discovered
- Accuracy metrics below target

**Current prompts (11):**
```python
SECRET_ANALYSIS_PROMPT        # (Real vs test secrets)
INTENT_CLASSIFICATION_PROMPT  # (Feature vs refactor vs docs)
COMPLEXITY_ASSESSMENT_PROMPT  # (Simple vs complex changes)
DESCRIPTION_VALIDATION_PROMPT # (Accurate vs misleading docs)
DOC_GENERATION_PROMPT         # (Auto-generate descriptions)
FILE_ORGANIZATION_PROMPT      # (Semantic file placement — legacy; file org enforcement moved to stdlib-only enforce_file_organization.py hook, Issue #1034)
# Refactor semantic analysis prompts (Issue #515):
DOC_CODE_DRIFT_PROMPT         # (Doc-code contradiction detection via covers: frontmatter)
HOLLOW_TEST_PROMPT            # (Meaningful vs hollow test detection)
DEAD_CODE_VERIFY_PROMPT       # (Dead code verification with dynamic dispatch context)
REFACTOR_ESCALATION_PROMPT    # (Deeper analysis for HIGH findings needing escalation)
REFACTOR_BATCH_SYSTEM_PROMPT  # (System prompt for Batch API refactor analysis)
```

**Version control pattern:**
```bash
# BEFORE changing prompt: Document current performance
git commit -m "docs: SECRET_ANALYSIS_PROMPT accuracy at 92%"

# Test new prompt
vim plugins/autonomous-dev/hooks/genai_prompts.py
# Update prompt

# Run tests
python .claude/hooks/security_scan.py
# Measure accuracy improvement

# AFTER changing: Document improvement
git commit -m "feat: improve SECRET_ANALYSIS_PROMPT accuracy from 92% to 97%"
```

**Testing prompts:**
```bash
# Test secret detection
echo "API_KEY=test_12345" | python .claude/hooks/security_scan.py

# Test intent classification
echo "implement user auth" | python .claude/hooks/auto_generate_tests.py

# Test complexity assessment
python .claude/hooks/auto_update_docs.py
```

#### 6. **Skills** (Knowledge Currency)

**Location**: `plugins/autonomous-dev/skills/*/skill.md`

**When to update:**
- New patterns discovered in code reviews
- Best practices evolve (framework updates, new standards)
- Technology standards change (Python 3.13, new libraries)
- Project conventions shift

**Structure:**
```yaml
---
auto_activate: true
keywords: ["authentication", "security", "API keys"]
description: Security patterns and API key management
---

# Skill Content

## Best Practices
[Pattern documentation]

## Examples
[Code examples]

## Anti-Patterns
[What to avoid]
```

**Update trigger examples:**
```bash
# Code review reveals new pattern
# → Add to skills/code-review/skill.md

# Bug caused by missing pattern
# → Update skills/testing-guide/skill.md

# New tool adopted (e.g., Ruff replaces Black)
# → Update skills/python-standards/skill.md

# Framework upgrade (e.g., FastAPI v0.100+)
# → Update skills/api-design/skill.md
```

**Maintenance workflow:**
```bash
# 1. Identify pattern to document
# From: code review, bug post-mortem, team discussion

# 2. Add to appropriate skill
vim plugins/autonomous-dev/skills/[category]/skill.md

# 3. Update agent prompts to reference new pattern
vim plugins/autonomous-dev/agents/[relevant-agent].md
# Add reference to skill in system prompt

# 4. Test that agents use the pattern
/implement "feature using new pattern"
# Check session log for skill invocation
```

---

### 🟢 PERIODICALLY Review (Validation Path)

Check these regularly to ensure alignment:

#### 7. **Documentation** (Reality Mirror)

**Key files:**
- `README.md` - User-facing (what it does)
- `ARCHITECTURE-OVERVIEW.md` - How it works (500+ lines)
- `CLAUDE.md` - Development standards
- `docs/UPDATES.md` - Changelog
- `CHANGELOG.md` - Version history

**Auto-validation hooks:**
- `unified_doc_validator.py` - Consolidated: validates docs consistency, checks counts match reality, detects documentation drift
- `unified_doc_auto_fix.py` - Consolidated: auto-generates missing documentation, syncs code changes to docs

**Alignment pattern:**
```bash
# After adding new agent:
# 1. Agent count in PROJECT.md → updates automatically (hook)
# 2. Agent count in README.md → updates automatically (hook)
# 3. Agent count in CLAUDE.md → validation via unified_doc_validator
python .claude/hooks/unified_doc_validator.py

# If drift detected:
# NOTE (2026-08-30): do NOT add counts to CLAUDE.md. ARCHITECTURE-OVERVIEW.md is their single
# home; CLAUDE.md restating them is how they drift. Fix by REMOVING the count, not updating it.
vim CLAUDE.md  # Remove the restated count; link to ARCHITECTURE-OVERVIEW.md instead
git add CLAUDE.md
git commit -m "docs(CLAUDE.md): drop restated counts, link the canonical home"
```

**Review schedule:**
```bash
# Weekly: Check for drift
python .claude/hooks/unified_doc_validator.py  # Consolidates validate_docs_consistency, validate_claude_alignment, etc.

# Monthly: Comprehensive audit
VALIDATE_README_GENAI=true python .claude/hooks/unified_doc_validator.py  # GenAI-powered README validation

# Per release: Full documentation review
# - README.md (user-facing accuracy)
# - ARCHITECTURE-OVERVIEW.md (technical accuracy)
# - CLAUDE.md (standards currency)
# - CHANGELOG.md (release notes)
```

#### 8. **Session Logs** (Execution Evidence)

**Location**: `docs/sessions/YYYY-MM-DD-HH-MM-SS-agent-name.md`

**What to review:**
- Are agents being invoked as expected?
- Are quality gates catching issues?
- Are there patterns of failures?
- Is orchestrator running for all features?

**Audit commands:**
```bash
# Check orchestrator invocation rate
total_sessions=$(ls docs/sessions/*.md 2>/dev/null | wc -l)
orchestrator_sessions=$(ls docs/sessions/*orchestrator*.md 2>/dev/null | wc -l)
echo "orchestrator invoked in $orchestrator_sessions of $total_sessions sessions"

# Review recent session quality
tail -50 docs/sessions/$(ls -t docs/sessions/ | head -1)

# Find agent usage patterns
echo "Agent invocation counts:"
for agent in orchestrator researcher planner test-master implementer reviewer security-auditor doc-master; do
    count=$(ls docs/sessions/*${agent}*.md 2>/dev/null | wc -l)
    echo "  $agent: $count"
done

# Check for error patterns
grep -i "error\|failed\|blocked" docs/sessions/*.md | wc -l

# Find most recent orchestrator validation
ls -lt docs/sessions/*orchestrator*.md | head -1
```

**Review frequency:**
- **Daily** (during active development): Check if orchestrator is being invoked
- **Weekly**: Review error patterns
- **Monthly**: Analyze agent usage trends

#### 9. **Hook Configuration Performance**

**What to monitor:**
- Hook execution time (should be < 10 seconds total)
- GenAI API costs (Haiku usage)
- False positive/negative rates
- Hook failure patterns

**Performance tuning:**
```bash
# Measure hook execution time
time python .claude/hooks/unified_doc_validator.py
time python .claude/hooks/unified_code_quality.py
time python .claude/hooks/unified_doc_auto_fix.py

# If too slow (> 10s), consider:
# 1. Disable GenAI for specific hooks during dev
export GENAI_SECURITY_SCAN=false

# 2. Use caching for expensive operations
# (Already implemented in WebFetch tool)

# 3. Reduce scope of analysis
# (Edit hook to check only changed files)
```

---

### 🔵 AS NEEDED (Enhancement Path)

Update these for experimentation and evolution:

#### 10. **Feature Flags** (Control Knobs)

**Available flags:**
```bash
# GenAI features (in genai_prompts.py)
export GENAI_SECURITY_SCAN=true|false       # Secret detection
export GENAI_TEST_GENERATION=true|false     # Intent classification
export GENAI_DOC_UPDATE=true|false          # Complexity assessment
export GENAI_DOCS_VALIDATE=true|false       # Description validation
export GENAI_DOC_AUTOFIX=true|false         # Doc generation
export GENAI_FILE_ORGANIZATION=true|false   # File placement (legacy — file org is now enforced by the stdlib-only enforce_file_organization.py hook; this flag no longer controls enforcement; bypass via AUTONOMOUS_DEV_BYPASS=1 instead)

# Debug flags
export DEBUG_GENAI=true   # Verbose GenAI logging
```

**Experimentation pattern:**
```bash
# Disable expensive feature during rapid iteration
export GENAI_SECURITY_SCAN=false
# ... make many commits quickly ...

# Re-enable for final validation
unset GENAI_SECURITY_SCAN  # Defaults to true
git commit -m "feat: final implementation with full validation"
```

#### 11. **GitHub Issues** (Evolution Roadmap)

**Pattern:**
- Research findings → GitHub issues
- Philosophy conflicts → Discussion + decision + PROJECT.md update
- New capabilities → Issue + implementation + documentation

**Current active issues:**
- #37 - Enable auto-orchestration
- #35 - Agents use skills more actively
- #34 - Pattern-based orchestration
- #29 - Pipeline verification

**Maintenance:**
```bash
# Close completed issues
gh issue close 37 --comment "Implemented in commit abc123"

# Reference commits in issues
git commit -m "feat: enable auto-orchestration (closes #37)"

# Update issue scope if needed
gh issue edit 35 --body "Updated scope: ..."
```

---

## The Core Philosophy Checklist

Before any major change, ask these questions:

### 1. ✅ Does this trust the model?

**Good (Aligned):**
- Adding GenAI reasoning to hooks
- Letting Claude decide which agents to invoke
- Using customInstructions to guide behavior
- Semantic understanding via LLMs

**Bad (Not Aligned):**
- Rigid if/else logic in Python
- Hardcoded sequences of agent invocations
- Static pattern matching (regex without GenAI fallback)
- Forcing specific workflow order

### 2. ✅ Is enforcement via hooks?

**Good (Aligned):**
- PreCommit hooks validate alignment
- Hooks block commits on failure
- 100% reliability (hooks always run)
- Hooks check evidence (session logs, file counts)

**Bad (Not Aligned):**
- Relying on agents to enforce standards
- Hoping developers follow process
- Optional validation steps
- Manual review processes

### 3. ✅ Is intelligence via agents?

**Good (Aligned):**
- Agents provide expertise and guidance
- Agents research patterns
- Agents make design decisions
- Agents coordinate specialists

**Bad (Not Aligned):**
- Hooks making complex decisions
- Hooks containing business logic
- Hooks implementing features
- Hooks doing AI work without GenAI

### 4. ✅ Does PROJECT.md control alignment?

**Good (Aligned):**
- orchestrator reads PROJECT.md first
- Hooks validate against PROJECT.md
- Dynamic scope changes via PROJECT.md updates
- All agents reference PROJECT.md

**Bad (Not Aligned):**
- Hardcoded scope checks in Python
- Agent prompts with static scope definitions
- Configuration files defining business logic
- Multiple sources of truth

### 5. ✅ Are skills used progressively?

**Good (Aligned):**
- Agents invoke skills as needed
- Skills loaded on-demand
- Progressive disclosure pattern
- Context stays small

**Bad (Not Aligned):**
- All skills loaded upfront
- Context bloat from unused skills
- Skills duplicating agent knowledge
- No skill invocation tracking

### 6. ✅ Is documentation auto-synced?

**Good (Aligned):**
- Hooks auto-update documentation
- Hooks validate documentation accuracy
- Documentation mirrors code automatically
- Drift detected and blocked

**Bad (Not Aligned):**
- Manual documentation updates
- Documentation as afterthought
- No validation of accuracy
- Drift accumulates silently

---

## Quick Reference: What to Update When

### ✨ You add a new agent

```bash
# 1. Create agent file
touch plugins/autonomous-dev/agents/new-agent.md
vim plugins/autonomous-dev/agents/new-agent.md

# 2. Counts update automatically (hooks)
git commit -m "feat: add new-agent for X capability"
# → PROJECT.md count updates (hook)
# → README.md count updates (hook)

# 3. Check CLAUDE.md alignment (unified_doc_validator consolidates this check)
python .claude/hooks/unified_doc_validator.py
# If drift: update CLAUDE.md manually

# 4. Update orchestrator if needed
vim plugins/autonomous-dev/agents/orchestrator.md
# Add new-agent to coordination logic
```

### 🎯 You change project direction

```bash
# 1. UPDATE PROJECT.md FIRST (most critical)
vim .claude/PROJECT.md
# Update GOALS, SCOPE, CONSTRAINTS

# 2. Commit strategic change
git add .claude/PROJECT.md
git commit -m "docs: change direction to X architecture"

# 3. orchestrator reads new alignment automatically
# All future features validated against new SCOPE

# 4. Optional: Update agent prompts if needed
# (Only if agents need to know about new patterns)
```

### 🔍 You discover a new pattern

```bash
# 1. Add to relevant skill
vim plugins/autonomous-dev/skills/[category]/skill.md
# Document the pattern

# 2. Update agent prompts to reference skill
vim plugins/autonomous-dev/agents/[agent].md
# Tell agent to use the skill

# 3. Test that agents invoke skill
/implement "feature using new pattern"
grep "skill" docs/sessions/$(ls -t docs/sessions/ | head -1)
```

### 🔒 You change enforcement rules

```bash
# 1. Update hook configuration
vim .claude/settings.local.json
# Add/remove/modify hooks

# 2. Test with sample feature
/implement "test feature"
git commit -m "test: verify new enforcement"

# 3. Document in architecture guide
vim docs/ARCHITECTURE-OVERVIEW.md
# Explain the new enforcement rule
```

### ⚡ Hook decisions are wrong

```bash
# 1. Identify which prompt is wrong
python .claude/hooks/[hook-name].py
# Check output/logs

# 2. Update prompt
vim plugins/autonomous-dev/hooks/genai_prompts.py
# Improve the prompt (lines X-Y)

# 3. Test accuracy improvement
python .claude/hooks/[hook-name].py
# Measure false positive/negative rate

# 4. Commit with metrics
git commit -m "feat: improve [PROMPT_NAME] accuracy from X% to Y%"
```

### 🤖 Agent behavior is wrong

```bash
# 1. Review session log
cat docs/sessions/$(ls -t docs/sessions/*agent-name*.md | head -1)

# 2. Update agent system prompt
vim plugins/autonomous-dev/agents/agent-name.md

# 3. Test with /implement
/implement "test feature"

# 4. Verify behavior in session log
cat docs/sessions/$(ls -t docs/sessions/*agent-name*.md | head -1)
grep "expected behavior" [session-file]
```

---

## Maintenance Schedules

### Daily (During Active Development)

```bash
# Check orchestrator invocation
ls -lt docs/sessions/*orchestrator*.md | head -1

# Review latest session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)

# Quick alignment check
git status  # PreCommit hooks catch issues automatically
```

### Weekly

```bash
# Documentation alignment (unified_doc_validator consolidates these checks)
python .claude/hooks/unified_doc_validator.py

# Agent usage patterns
echo "Agent invocations this week:"
find docs/sessions -name "*.md" -mtime -7 | \
  xargs basename -a | \
  cut -d'-' -f6 | \
  sort | uniq -c | sort -rn

# Hook performance
echo "Hook execution times:"
for hook in unified_doc_validator unified_code_quality unified_doc_auto_fix; do
    echo -n "  $hook: "
    time python .claude/hooks/${hook}.py 2>&1 | grep real
done
```

### Monthly

```bash
# Comprehensive documentation audit
python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --audit --genai

# Review PROJECT.md against reality
cat .claude/PROJECT.md
# Ask: Are GOALS still current? Is SCOPE accurate?

# Agent effectiveness review
cat docs/sessions/*.md | grep -i "error\|failed\|blocked" | wc -l
# Compare to previous month

# Skills currency check
ls -lt plugins/autonomous-dev/skills/*/skill.md | head -10
# Ask: Are these skills still current?
```

### Per Release

```bash
# Full documentation review
# - README.md (user-facing accuracy)
# - ARCHITECTURE-OVERVIEW.md (technical accuracy)
# - CLAUDE.md (standards currency)
# - PROJECT.md (strategic alignment)
# - CHANGELOG.md (release notes)

# Update version numbers
vim PROJECT.md  # Update version in header
vim CLAUDE.md   # Update version in header
vim README.md   # Update version in badges

# Tag release
git tag -a v3.1.0 -m "Release v3.1.0: [description]"
git push origin v3.1.0
```

---

## Warning Signs of Philosophy Drift

### 🚨 Red Flags

1. **Hardcoded scope checks in Python**
   - Fix: Move to PROJECT.md, let orchestrator validate

2. **Agents not being invoked**
   - Check: `ls docs/sessions/*orchestrator*.md | wc -l`
   - Fix: Enable detect_feature_request.py hook (Issue #37)

3. **Documentation out of sync**
   - Check: `python .claude/hooks/validate_docs_consistency.py`
   - Fix: Update docs, commit, let hooks validate

4. **Rigid Python orchestration**
   - Check: grep "subprocess.run.*agents" in codebase
   - Fix: Remove, use GenAI-powered coordination

5. **Context bloat**
   - Check: Token usage > 50K after 3-4 features
   - Fix: Use /clear, improve session logging

6. **Manual enforcement**
   - Check: "Please remember to..." in docs
   - Fix: Add hook to enforce automatically

### ✅ Health Indicators

1. **orchestrator runs for all features**
   ```bash
   # Should see orchestrator sessions regularly
   ls -lt docs/sessions/*orchestrator*.md | head -5
   ```

2. **PROJECT.md is updated before features**
   ```bash
   # PROJECT.md commits should precede feature commits
   git log --oneline .claude/PROJECT.md | head -5
   ```

3. **Hooks catch issues before merge**
   ```bash
   # Should see hook validation messages in git output
   git commit -m "test"  # Shows hook execution
   ```

4. **Documentation stays aligned**
   ```bash
   # Should pass validation
   python .claude/hooks/validate_docs_consistency.py
   # Exit code: 0
   ```

5. **GenAI is being used**
   ```bash
   # Should see GenAI analysis in hook output
   export DEBUG_GENAI=true
   python .claude/hooks/security_scan.py
   # Should show "✅ GenAI analysis successful"
   ```

---

## Emergency Recovery

### If philosophy has drifted significantly:

```bash
# 1. Audit current state
VALIDATE_README_GENAI=true python .claude/hooks/unified_doc_validator.py
python .claude/hooks/unified_doc_validator.py

# 2. Review PROJECT.md
cat .claude/PROJECT.md
# Ask: Is this still accurate?

# 3. Check orchestrator invocation rate
total=$(ls docs/sessions/*.md 2>/dev/null | wc -l)
orchestrator=$(ls docs/sessions/*orchestrator*.md 2>/dev/null | wc -l)
echo "orchestrator rate: $orchestrator / $total"
# Target: > 50% for feature-heavy projects

# 4. Enable strict mode if needed
cp plugins/autonomous-dev/templates/settings.strict-mode.json \
   .claude/settings.local.json

# 5. Run /align
/align

# 6. Commit fixes
git add .
git commit -m "fix: restore core philosophy alignment"
```

---

## Summary

**The core philosophy stays active when:**

1. **PROJECT.md is updated FIRST** (source of truth)
2. **orchestrator validates all features** (gatekeeper)
3. **Hooks enforce quality gates** (100% reliable)
4. **Agents provide intelligence** (conditional, adaptive)
5. **Skills contain patterns** (progressive disclosure)
6. **Documentation auto-syncs** (no drift)
7. **GenAI makes decisions** (not static Python)

**Priority order for updates:**
1. 🔴 PROJECT.md, orchestrator.md, settings.local.json (always)
2. 🟡 Agent prompts, GenAI prompts, skills (frequently)
3. 🟢 Documentation, session logs, hooks (periodically)
4. 🔵 Feature flags, GitHub issues (as needed)

**Remember:** The system is designed to maintain itself through hooks and validation. Your job is to keep PROJECT.md accurate and let the automation handle the rest.

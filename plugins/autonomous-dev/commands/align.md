---
name: align
description: "Unified alignment command (--project, --docs, --retrofit, --content)"
argument-hint: "[--project [--invariants] | --docs | --retrofit | --content] [--dry-run] [--auto]"
version: 3.1.0
category: core
allowed-tools: [Read, Write, Edit, Grep, Glob]
disable-model-invocation: true
user-invocable: true
user_facing: true
---

# /align - Unified Alignment Command

**Purpose**: Validate and fix alignment between PROJECT.md, documentation, and codebase.

**Default**: `/align` runs full alignment check (docs + code + hooks review)

**Modes**:
- `/align` - Full alignment (PROJECT.md + CLAUDE.md + README vs code + hooks review)
- `/align --project --invariants` - Derive or audit the `### INVARIANTS` section of PROJECT.md (approval-gated; opts a brownfield repo into the #1467 architecture-delta gate)
- `/align --docs` - Documentation only (ensure all docs consistent with PROJECT.md)
- `/align --retrofit` - Brownfield retrofit (5-phase project transformation)
- `/align --content` - Content allocation audit (CLAUDE.md/PROJECT.md/MEMORY.md sizing + de-dup)

---

## Quick Usage

```bash
# Default: Full alignment check
/align

# Documentation consistency only
/align --docs

# Brownfield project retrofit
/align --retrofit
/align --retrofit --dry-run
/align --retrofit --auto

# Content allocation audit
/align --content
/align --content --dry-run
/align --content --auto
```

---

## Mode 1: Full Alignment (Default)

**Purpose**: Comprehensive check that PROJECT.md, CLAUDE.md, README, and codebase are all aligned.

**Time**: 10-30 minutes

**What it does**:

### Phase 1: Quick Scan (GenAI or Regex)
Run manifest alignment validation:

```bash
# With OpenRouter (recommended - cheap GenAI validation)
OPENROUTER_API_KEY=sk-or-... python plugins/autonomous-dev/lib/genai_validate.py manifest-alignment

# Without API key (hybrid validator with regex fallback)
python plugins/autonomous-dev/lib/hybrid_validator.py --mode regex-only
```

**Validates**:
- Count mismatches (agents, commands, hooks, skills) vs install_manifest.json
- Version consistency (CLAUDE.md, PROJECT.md, manifest)
- Semantic alignment (GenAI mode only)

**Options**:
- **OpenRouter** (recommended): ~$0.001 per validation, uses Gemini Flash
- **Claude Code**: Semantic analysis in conversation (uses Max subscription)
- **Regex only**: Fast, free, catches count mismatches

### Phase 2: Semantic Validation (GenAI)
Check the following:

**PROJECT.md vs Code**:
- Do GOALS match what's implemented?
- Is SCOPE (in/out) respected in code?
- Are CONSTRAINTS followed?
- Does ARCHITECTURE match directory structure?

**CLAUDE.md vs Reality**:
- Do workflow descriptions match actual behavior?
- Do agent descriptions match capabilities?
- Do command descriptions match what they do?
- Are documented features actually implemented?

**README vs Reality**:
- Do feature claims match implementation?
- Are installation instructions accurate?
- Do examples actually work?

### Phase 3: Hooks/Rules Review
MUST review validation hooks for inflation:
- Are hooks still necessary?
- Do hook rules match current standards?
- Any redundant or conflicting hooks?

### Phase 4: Interactive Resolution (Bidirectional)
For each conflict found, determine which source is correct:

**Documentation vs Reality conflicts:**
```
CONFLICT: CLAUDE.md says "10 active commands"
Reality: 7 commands exist (example - already fixed)

What should we do?
A) Update CLAUDE.md to say "7 commands"
B) This is correct (explain why)

Your choice [A/B]:
```

**Code vs PROJECT.md conflicts (Bidirectional):**
```
CONFLICT: /create-issue exists in code/docs but not in PROJECT.md SCOPE

Which is correct?
A) Code/docs are right → Update PROJECT.md to include /create-issue
B) PROJECT.md is right → This shouldn't have been built (flag for removal)

Your choice [A/B]:
```

If A: Propose PROJECT.md update (requires approval)
If B: Log conflict for manual resolution

### Example Output

```
/align

Phase 1: Quick Scan
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Scanning file system for truth...
  Agents: 20, Commands: 7, Hooks: 45, Skills: 28

Found 5 count mismatches, 3 dead refs
→ Will address in Phase 4

Phase 2: Semantic Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Checking PROJECT.md alignment...
✓ GOALS: 4/4 implemented
✓ SCOPE: No out-of-scope code found
⚠ ARCHITECTURE: docs/ structure doesn't match documented pattern

Checking CLAUDE.md alignment...
✓ Workflow descriptions accurate
⚠ Agent count outdated (says 18, actual 20)
⚠ Command list missing /create-issue

Checking README alignment...
✓ Installation instructions work
✓ Examples are accurate

Phase 3: Hooks Review
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reviewing 45 hooks for inflation...
⚠ validate_project_alignment.py duplicates alignment_fixer.py logic
⚠ 3 hooks reference archived commands

Phase 4: Resolution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Found 8 issues to resolve...
[Interactive fixing begins]
```

---

## Mode 2: Documentation Alignment (`--docs`)

**Purpose**: Ensure all documentation is internally consistent and matches PROJECT.md (source of truth).

**Time**: 5-15 minutes

**What it does**:

### Checks Performed

1. **PROJECT.md as Source of Truth**
   - All other docs reference PROJECT.md correctly
   - No contradictions between docs and PROJECT.md
   - Version/date consistency

2. **Internal Doc Consistency**
   - CLAUDE.md matches README claims
   - Agent docs match AGENTS.md
   - Command docs match COMMANDS.md
   - No orphaned documentation

3. **Architecture Documentation**
   - Documented file structure matches reality
   - API documentation matches actual endpoints
   - Database schema docs match migrations

4. **Count/Reference Accuracy**
   - All counts (agents, commands, hooks) correct
   - No dead links or references
   - Examples use correct syntax

### What It Doesn't Do
- Doesn't check if code implements what docs say (use default `/align` for that)
- Doesn't modify code, only documentation
- Doesn't retrofit project structure

### Example Output

```
/align --docs

Validating documentation consistency...

Source of Truth: PROJECT.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Last updated: 2025-12-13
✓ Version: v3.40.0

Cross-Reference Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ CLAUDE.md references PROJECT.md correctly
✓ README.md and PROJECT.md both say 7 commands
✓ docs/AGENTS.md matches agents/ directory

Architecture Docs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ File structure documented correctly
⚠ docs/LIBRARIES.md missing 5 new libraries

Count Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Running alignment_fixer.py...
Found 3 count mismatches in documentation

Summary: 3 issues found
Fix with: /align --docs --fix
```

---

## Mode 3: Brownfield Retrofit (`--retrofit`)

**Purpose**: Transform existing projects to autonomous-dev standards for `/auto-implement` compatibility.

**Time**: 30-90 minutes

**Workflow**: 5-phase process with backup/rollback safety

### Phases

#### Phase 1: Analyze Codebase
- **Tool**: `codebase_analyzer.py`
- **Detects**: Language, framework, package manager, test framework, file organization
- **Output**: Comprehensive codebase analysis report

#### Phase 2: Assess Alignment
- **Tool**: `alignment_assessor.py`
- **Calculates**: Alignment score, gaps, PROJECT.md draft
- **Output**: Assessment with prioritized remediation steps

#### Phase 3: Generate Migration Plan
- **Tool**: `migration_planner.py`
- **Creates**: Step-by-step plan with effort/impact estimates
- **Output**: Optimized migration plan with dependencies

#### Phase 4: Execute Migration
- **Tool**: `retrofit_executor.py`
- **Modes**: `--dry-run` (preview), default (step-by-step), `--auto` (all at once)
- **Safety**: Automatic backup, rollback on failure

#### Phase 5: Verify Results
- **Tool**: `retrofit_verifier.py`
- **Checks**: PROJECT.md, file organization, tests, docs, git config
- **Output**: Readiness score (0-100) and blocker list

### Usage

```bash
# Preview what would change
/align --retrofit --dry-run

# Step-by-step with confirmations (safest)
/align --retrofit

# Automatic execution (fastest)
/align --retrofit --auto
```

### What Gets Retrofitted

1. **PROJECT.md Creation** - GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE
2. **File Organization** - Move to `.claude/` structure
3. **Test Infrastructure** - Configure test framework and coverage
4. **CI/CD Integration** - Pre-commit hooks, GitHub Actions
5. **Documentation** - CLAUDE.md, CONTRIBUTING.md, README sections
6. **Git Configuration** - .gitignore, commit conventions

### Rollback

```bash
# Automatic on failure
# Manual rollback:
python plugins/autonomous-dev/lib/retrofit_executor.py --rollback <timestamp>
```

---

## Mode 4: Content Allocation (`--content`)

**Purpose**: Audit and de-duplicate context files (`CLAUDE.md`, `PROJECT.md`, `MEMORY.md`, `memory/*.md`, top-level `docs/`) against the one-topic-one-home pattern. Enforces size budgets on the files that load every turn or every session.

**Time**: 5-20 minutes

**Workflow**: 4-phase process — AUDIT → PROPOSE → APPROVE → EXECUTE.

### Phase 1: AUDIT

- Read `CLAUDE.md`, `PROJECT.md`, `MEMORY.md`, all `memory/*.md`, and the top-level `docs/` listing.
- Measure each file against the size budget table from `skills/content-allocation/SKILL.md`.
- Search for duplicated headings, repeated rules, and content that lives in the wrong tier.

### Phase 2: PROPOSE

- Emit a structured plan. For each over-budget file or duplicated chunk, name the canonical home, the proposed move (or pointer compression), and the expected size impact.
- Group proposals by tier (`CLAUDE.md` → memory → docs) so the reviewer can approve in batches.

### Phase 3: INTERACTIVE APPROVAL

- The user reviews each proposed move and approves or rejects.
- `--dry-run` skips approval and only emits the plan.
- `--auto` accepts all proposals below a risk threshold (compressions and deletions); cross-tier moves still REQUIRE explicit approval.

### Phase 4: EXECUTE

- Apply the approved moves: rewrite source files, insert pointer lines, update cross-references.
- Re-measure size budgets after the run.
- Print a delta summary: lines removed from auto-loaded files, files compressed, files deleted.

### Sub-flags

- `--dry-run` — emit the proposal only; no files written.
- `--auto` — auto-approve low-risk proposals (compressions, deletions of stubs <500 bytes, removal of `RESOLVED`/`SUPERSEDED` findings).

### What gets allocated

1. **CLAUDE.md** — kept ≤200 lines (target ≤100). Behaviour rules only.
2. **PROJECT.md** — kept ≤200 lines (target ≤150). Purpose, scope, architecture only.
3. **MEMORY.md** — kept ≤200 lines (target ≤150). Index entries, ≤150 chars each.
4. **memory/*.md** — individual files 1-3 KB. Larger files split or promoted to `docs/`.
5. **Cross-store de-dup** — duplicate content reduced to one canonical copy plus pointers.

### Example output

```
/align --content

Phase 1: AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLAUDE.md       254 lines (over budget: target 100, ceiling 200)
PROJECT.md      178 lines (within budget)
MEMORY.md       259 lines (over budget: ceiling 200)
memory/*.md     14 files, 3 over 3 KB, 2 under 500 bytes

Duplications found: 5
  - "Deploy with deploy-all.sh" rule appears in CLAUDE.md and PROJECT.md
  - MLX section appears in MEMORY.md and memory/training_pipeline_2026_02.md

Phase 2: PROPOSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Move CLAUDE.md "Mac Studio Deployment" → memory/project_mac_studio_setup.md
   Saves: ~12 lines from CLAUDE.md
2. Compress MEMORY.md MLX section → 3-line index entry pointing to memory file
   Saves: ~45 lines from MEMORY.md
3. Delete memory/session_outcomes_2026_01_15.md (>7 days old, marked RESOLVED)

Phase 3: INTERACTIVE APPROVAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Approve proposal 1? [Y/n/skip]
...

Phase 4: EXECUTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLAUDE.md       254 → 175 lines (-79)
MEMORY.md       259 → 137 lines (-122)
Files moved: 1, compressed: 1, deleted: 1
```

### When to use

- After a major refactor or every ~10 sessions.
- When `CLAUDE.md` or `MEMORY.md` exceed their hard ceilings.
- Before applying the content-allocation pattern to a new repo (use the template at `templates/CONTENT_ALLOCATION.md`).

---

## INVARIANTS Derivation & Audit (`--project --invariants`)

**Purpose**: Derive (or audit) the `### INVARIANTS` subsection of PROJECT.md so a brownfield repo can opt into the Issue #1467 **architecture-delta gate**. An invariant is a **load-bearing property a change must not silently violate** — an architecture-level guarantee, NOT a feature list and NOT volatile detail (component counts, versions, tech stack). A proposed change that contradicts one is an *architecture delta* requiring explicit sign-off.

**Backward-compat guarantee**: a repo with **no** `### INVARIANTS` bullets under `## ARCHITECTURE` is **never** architecture-delta-blocked — deriving invariants is strictly opt-in. This mode never weakens that default; it only offers to populate the section.

**Every `/align` mode runs inline** (no sub-agent): the coordinator gathers evidence with Read/Grep only, then proposes. This mirrors Mode 4 (`--content`)'s AUDIT → PROPOSE → APPROVE → EXECUTE flow.

**Time**: 5-20 minutes. **Model**: runs in the current conversation.

### Entry branch (parse first)

At entry, parse the current PROJECT.md:

```bash
python plugins/autonomous-dev/lib/alignment_classifier.py --help >/dev/null 2>&1  # capability probe
```
```python
import sys; sys.path.insert(0, "plugins/autonomous-dev/lib")
from alignment_classifier import parse_project_md
from pathlib import Path
doc = parse_project_md(Path(".claude/PROJECT.md"))   # falls back to PROJECT.md per repo convention
print("has_invariants:", doc.has_invariants, "count:", len(doc.invariants))
```

- **No `.claude/PROJECT.md` (FileNotFoundError)** → **BLOCK**: "run `/setup` or `/align --retrofit` first — a project with no alignment source of truth cannot derive invariants." STOP.
- **Consumer repo without `lib/alignment_classifier.py`** → degrade gracefully: skip the programmatic parse, describe the manual bullet format (`- **INV-N — Property.** explanation` under `## ARCHITECTURE`), and proceed with the derivation flow using Read/Grep only.
- **`has_invariants == False`** → **INITIAL DERIVATION** (Phase 1-3 below).
- **`has_invariants == True`** → **IDEMPOTENT AUDIT** (see Audit mode).
- **Malformed existing INVARIANTS** (a heading is present but no parseable `- ` bullets under `## ARCHITECTURE`) → treat as **initial derivation** and **warn** the user that the existing section did not parse; offer to *replace* it — never duplicate.

### Phase 1: EVIDENCE (inline, Read/Grep only)

Gather candidate load-bearing properties from, in priority order:

1. **PROJECT.md** GOALS / SCOPE / CONSTRAINTS and stated intent.
2. **README** and **CLAUDE.md** — stated guarantees, "never do X" rules.
3. **Runtime safety / enforcement mechanisms** — hooks returning `{"decision": "block"}`, fail-closed guards, signature/HMAC checks (the strongest evidence: an enforced property is a real invariant).
4. **Tests that encode contracts** — regression tests asserting a property must hold.
5. **CI gates** — required checks in workflows.
6. **Policy / config files** — allowlists, hard-floor definitions, sandbox policy.
7. **Git-log "never do X" corrections** — `git log --grep` for recurring guardrail commits.

Prefer *enforced* properties over *aspirational* ones. An invariant backed by a hook/test is defensible; one backed only by prose is `(intended, not yet enforced)`.

### Phase 2: PROPOSE (draft in exact parse format)

Emit a **DRAFT** `### INVARIANTS` section in the EXACT format the parser recognizes:

```markdown
### INVARIANTS

- **INV-1 — <Property>.** <explanation of the load-bearing guarantee>
- **INV-2 — <Property>.** <explanation>
```

…plus an **evidence table**:

| Candidate | Property | EVIDENCE (file/mechanism/test) | Would-VIOLATE example |
|-----------|----------|--------------------------------|-----------------------|
| INV-1 | … | `hooks/foo.py` returns block on … | a change that … |

Rules:
- Propose **5-8** candidates. Tag any intended-but-unenforced property `(intended, not yet enforced)`.
- If **fewer than 3** defensible candidates are found, present exactly what was found and **say so** — do NOT pad or invent invariants to hit a count.
- Each bullet MUST be a single `- **INV-N — Property.** explanation` line so `parse_project_md` captures it. The section MUST land **under `## ARCHITECTURE`** or it will not be detected.

### Phase 3: APPROVE (AskUserQuestion — PROJECT.md-amending governance, #1467)

PROJECT.md is a governed alignment source. **FORBIDDEN: writing PROJECT.md before approval.** Present the proposal, then ask via **AskUserQuestion** with exactly four options (mirrors `/implement` STEP 2d):

- **(A) Apply** — write the drafted `### INVARIANTS` section UNDER `## ARCHITECTURE` in PROJECT.md.
- **(B) Edit specific invariants** — user names which to change/drop; re-present the revised proposal, then ask again.
- **(C) Save proposal to a file only** — write the draft to e.g. `docs/proposed-invariants.md`; do NOT modify PROJECT.md.
- **(D) Cancel** — make no changes. STOP.

On (B)/(C)/(D) do not modify PROJECT.md in this pass. `--dry-run` forces proposal-only: emit the draft + evidence table and STOP (never write, never prompt).

### Phase 4: POST-WRITE SELF-CHECK (integration proof)

After any write to PROJECT.md (option A), re-run the parser and confirm the flag flipped:

```python
from alignment_classifier import parse_project_md
from pathlib import Path
doc = parse_project_md(Path(".claude/PROJECT.md"))
assert doc.has_invariants is True, "INVARIANTS write did not activate — section likely landed OUTSIDE ## ARCHITECTURE"
print("post-write has_invariants:", doc.has_invariants, "count:", len(doc.invariants))
```

If it did NOT flip (e.g. the section was written above `## ARCHITECTURE`, or as a numbered list instead of `- ` bullets), report the error and the fix (move the section under `## ARCHITECTURE`; convert numbered items to `- **INV-N — …** …` bullets), then re-write.

### Audit mode (`has_invariants == True`, idempotent)

When invariants already exist, this mode is a **drift audit**, not a re-derivation:

- For each existing `INV-N`, re-verify that its cited evidence **still resolves** in the current code (the hook/test/file it points to still exists and still enforces the property).
- Report drift as: `DRIFT: INV-N — <what changed> — <cite>` when the evidence no longer resolves OR the property is now violable.
- Propose only **additive or corrective** deltas. **NEVER duplicate** an existing invariant.
- If nothing drifted, emit a **clean no-op report** (no proposal, no write).
- Any write still goes through Phase 3 approval + Phase 4 self-check.

### Why not reuse `alignment_assessor.py`?

`lib/alignment_assessor.py`'s `ProjectMdDraft` / `AlignmentAssessor` (used by `--retrofit`) was considered and is **not** reused here because it derives architecture **mechanically** (file and dependency counts), whereas invariants require **semantic judgment** about which properties are load-bearing — a judgment the coordinator makes inline from evidence, not a count.

---

## When to Use Each Mode

| Scenario | Mode |
|----------|------|
| Regular development check | `/align` |
| Opt a brownfield repo into architecture-delta checking | `/align --project --invariants` |
| Audit existing invariants for drift | `/align --project --invariants` |
| After adding/removing components | `/align` |
| Before major release | `/align` |
| Updating documentation only | `/align --docs` |
| Onboarding new developers | `/align --docs` |
| Adopting autonomous-dev | `/align --retrofit` |
| Legacy codebase migration | `/align --retrofit` |
| CLAUDE.md / MEMORY.md over budget | `/align --content` |
| Periodic context-file hygiene (every ~10 sessions) | `/align --content` |
| Applying content-allocation pattern to a new repo | `/align --content` |

---

## Implementation

ARGUMENTS: {{ARGUMENTS}}

Based on arguments, execute the appropriate mode inline:

```bash
# Quick scan (Phase 1)
python plugins/autonomous-dev/lib/hybrid_validator.py --mode auto
```

**Default mode** (`/align` or `/align --project`):
- Execute Phase 1-4 as described above: quick scan, semantic validation, hooks review, interactive resolution

**Documentation mode** (`/align --docs`):
- Execute documentation consistency checks as described above
- Validate documentation consistency against PROJECT.md

**Retrofit mode** (`/align --retrofit`):
- Execute 5-phase brownfield transformation as described above
- Sub-flags: `--dry-run` (preview), `--auto` (non-interactive)

**Content mode** (`/align --content`):
- Execute 4-phase content allocation audit as described in Mode 4 above
- Sub-flags: `--dry-run` (preview), `--auto` (auto-approve low-risk proposals)

**Invariants mode** (`/align --project --invariants`):
- Execute the EVIDENCE → PROPOSE → APPROVE → SELF-CHECK flow (or idempotent AUDIT) as described in "INVARIANTS Derivation & Audit" above
- PROJECT.md-amending: approval-gated via AskUserQuestion; FORBIDDEN to write before approval (#1467)
- Sub-flags: `--dry-run` (proposal only, never write)

---

## Implementation Details

### Mode Detection

```
Parse arguments from user input:

IF --retrofit flag:
    → Run 5-phase brownfield retrofit
    → MUST handle --dry-run or --auto sub-flags

ELIF --docs flag:
    → Run documentation consistency check
    → alignment_fixer.py + cross-reference validation
    → No code changes, docs only

ELIF --content flag:
    → Run 4-phase content allocation audit (AUDIT → PROPOSE → APPROVE → EXECUTE)
    → MUST load methodology from skills/content-allocation/SKILL.md
    → MUST handle --dry-run (proposal only) or --auto (low-risk auto-approve)

ELIF --invariants flag (a sub-mode of --project / default):
    → Parse PROJECT.md via alignment_classifier.parse_project_md
    → has_invariants False → INITIAL DERIVATION (EVIDENCE → PROPOSE → APPROVE → SELF-CHECK)
    → has_invariants True  → IDEMPOTENT AUDIT (drift check, additive-only, never duplicate)
    → PROJECT.md-amending: FORBIDDEN to write PROJECT.md before AskUserQuestion approval (#1467)
    → MUST handle --dry-run (proposal only, never write)
    → No .claude/PROJECT.md → BLOCK (run /setup or /align --retrofit first)

ELSE (default):
    → Phase 1: alignment_fixer.py (quick scan)
    → Phase 2: Semantic validation (inline)
    → Phase 3: Hook inflation review
    → Phase 4: Interactive resolution
```

### Libraries Used

**Default mode**:
- `hybrid_validator.py` - Hybrid manifest validation (GenAI + regex fallback)
- Semantic validation performed inline by Claude Code

**--docs mode**:
- `alignment_fixer.py` - Count validation
- Cross-reference validation logic

**--retrofit mode**:
- `codebase_analyzer.py` - Phase 1
- `alignment_assessor.py` - Phase 2
- `migration_planner.py` - Phase 3
- `retrofit_executor.py` - Phase 4
- `retrofit_verifier.py` - Phase 5

**--content mode**: skills/content-allocation/SKILL.md (methodology); reuses Read/Glob/Grep/Edit

**--project --invariants mode**:
- `alignment_classifier.py` - `parse_project_md` (entry branch + Phase 4 post-write self-check); reused **as-is**, no signature changes
- Evidence gathering + semantic judgment performed inline by Claude Code (Read/Grep only)
- `lib/alignment_assessor.py` (`ProjectMdDraft` / `AlignmentAssessor`) was considered and is **not** reused — it derives architecture mechanically (file/dependency counts), whereas invariants require semantic judgment about load-bearing properties

---

## Troubleshooting

### "Alignment check takes too long"

Use `--docs` for faster documentation-only check:
```bash
/align --docs  # 5-15 min vs 10-30 min
```

### "Too many conflicts to review"

Run in batches:
```bash
/align --docs           # Fix docs first
/align                  # Then full check (fewer issues)
```

### "Retrofit fails at Phase 4"

Automatic rollback should restore backup. Manual rollback:
```bash
ls ~/.autonomous-dev/backups/
python plugins/autonomous-dev/lib/retrofit_executor.py --rollback <timestamp>
```

---

## Related Commands

- `/auto-implement` - Uses PROJECT.md for feature alignment
- `/setup` - Initial project setup (calls `/align --retrofit` internally)
- `/health-check` - Plugin integrity validation

---

## Migration from Old Commands

| Old Command | New Command |
|-------------|-------------|
| `/align-project` | `/align` (default) |
| `/align-claude` | `/align --docs` |
| `/align-project-retrofit` | `/align --retrofit` |

**Note**: Old commands archived to `commands/archive/` (Issue #121).

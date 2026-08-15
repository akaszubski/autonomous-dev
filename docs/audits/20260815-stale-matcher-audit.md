# Stale-matcher audit — controls keyed to incidental properties

**Date**: 2026-08-15
**Trigger**: Issue #1503 (`plan_gate` matcher fails OPEN for MCP editing tools)
**Scope**: every hook matcher, permission deny-list, and in-code tool dispatch in this repo
**Method**: static enumeration + live probe harness feeding real `PreToolUse` payloads to the real hooks

## The invariant under test

> A control keyed to an incidental property — a tool's name, a file's name, a line
> count — goes stale the moment that property changes, and the failure is silent.

Two failure polarities matter, and this repo has both:

- **Fails OPEN** — the control does not recognise the actor, so it permits. (Security hole.)
- **Fails CLOSED** — the control does not recognise the actor, so it denies. (Trains the operator to bypass, which is how the OPEN failures get exploited.)

Both come from the same root: **there is no single canonical answer in this repo to "what does this tool call actually do."** Every gate re-derives it from a hand-written list, and the lists disagree.

---

## Finding 1 — the protected-infrastructure hard floor is bypassable via MCP (P0)

Issue #1503 reports this as a `plan_gate` defect. It is broader: `plan_gate` is not
even registered in this repo's `.claude/settings.json`. The hook that actually gates
edits here is `unified_pre_tool.py`, registered `PreToolUse` matcher `"*"` — and it
keys on `tool_name in ("Write", "Edit")` in **7 places**, including the #1435 hard floor.

**Measured** (`scratchpad/probe.py` → `unified_pre_tool.py`, same target file, five transports):

| Tool | Target | Decision |
|---|---|---|
| `Write` | `plugins/autonomous-dev/hooks/plan_gate.py` | **deny** — `BLOCKED: Direct edit to 'plan_gate.py' denied.` |
| `Edit` | `plugins/autonomous-dev/lib/pipeline_state.py` | **deny** — `BLOCKED: Direct edit to 'pipeline_state.py' denied.` |
| **`NotebookEdit`** | `plugins/autonomous-dev/hooks/plan_gate.py` | **allow** — `Native tool 'NotebookEdit' - hook bypass` |
| **`MultiEdit`** | `plugins/autonomous-dev/hooks/plan_gate.py` | **allow** |
| `mcp__serena__replace_symbol_body` | `plugins/autonomous-dev/hooks/plan_gate.py` | **allow** |
| `mcp__serena__insert_after_symbol` | `plugins/autonomous-dev/lib/pipeline_state.py` | **allow** |

CLAUDE.md documents this hard floor as surviving even `.claude/.bypass`. It does not
survive an installed MCP editing server — **and it does not survive `NotebookEdit`,
which ships with Claude Code**. The hole is reachable with zero MCP servers installed,
so this is not an "MCP vs native" defect at all. It is that enforcement sites test a
literal 2-tuple while the real set of file-mutating tools is larger and grows.

The repo's own canonical classifier already knows this: `lib/tool_intent.py` declares
`WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}`. The hooks simply never
ask it.

### Structural root cause

`unified_pre_tool.py:8330` states the architecture outright:

```python
# PROJECT GUARD: Non-autonomous-dev projects skip enforcement.
# Only non-native (MCP) tools reach this point.
```

Native tools take a fast path that ends in `output_decision("allow", "Native tool
'{tool_name}' - hook bypass")` + `sys.exit(0)`. MCP tools flow into a **different
pipeline** — project guard, then MCP security — that never runs the protected-infra
check, the plan gate, or the worktree-escape check.

The hook is built on the assumption **"native = edits files, MCP = external
integration."** Serena (#1451) falsifies that assumption. This is why adding
`mcp__serena__*` to a matcher is the wrong fix: the next editing MCP server
reintroduces it.

## Finding 2 — `plan_gate` explicit allow (the reported instance)

`plan_gate.hook.json` matcher `"Write|Edit"`, reinforced at `plan_gate.py:211`:

```python
if tool_name not in ("Write", "Edit"):
    _output_decision("allow", f"Plan gate: tool {tool_name} not subject to plan check")
```

Measured — every MCP editing tool returns
`allow  Plan gate: tool mcp__serena__replace_content not subject to plan check`.
Confirmed as reported. Registered only via `templates/settings.autonomous-dev.json`.

## Finding 3 — the same defect at OPPOSITE polarity: `_PLAN_EXIT_MCP_READONLY`

`unified_pre_tool.py:1151` holds a hand-written frozenset of read-only MCP tools used
by the plan-exit gate: deny **unless** the tool is on the list. It covers Playwright,
HuggingFace, Gmail, Calendar, Drive — and **was never updated when Serena was adopted
in #1451**.

So during the `plan_exited` stage, in an autonomous-dev project:

- `mcp__serena__find_symbol` (read-only) → **denied** — over-block
- `mcp__serena__replace_content` (mutating) → also denied, but only by accident of the same omission

The list's own comment is correct and worth preserving:

```python
# Structural (regex-based) heuristics are forbidden because they produce
# false-negatives (e.g., "find_and_replace" contains "find" but is a write).
```

This is the strongest argument against a verb-prefix classifier and **for** an explicit
registry — but one registry, consulted by every gate, not one per gate.

## Finding 4 — permission deny-lists cannot express the MCP case at all

Every settings template pairs `Edit(...)` with `Write(...)` correctly (the gap #1503
reports was a downstream `realign` issue, already fixed there and never present here):

```
deny: Edit=4 Write=4 mcp=0   .claude/settings.json
deny: Edit=5 Write=5 mcp=0   templates/settings.autonomous-dev.json   (+ ~/.aws/**)
```

But `mcp=0` across all seven files. `~/.ssh/**` is protected from `Write` and `Edit`
and **not** from `mcp__serena__replace_content`.

This one is **not fixable in settings**: Claude Code permission rules for MCP tools are
name-only (`mcp__server__tool`) and take no path argument, so a path-scoped MCP deny is
inexpressible. The hook layer is the only place it can be enforced — which raises the
stakes on Finding 1.

## Finding 5 — `_is_simple_edit()` is doubly name-keyed

`plan_gate.py` reads the changed-content size from `new_string` (Edit) or `content`
(Write) by literal key name. Once the tool-name gate is fixed, an MCP edit falls
through to "not a simple edit" and **every** MCP edit demands a plan — inverting the
exemption. #1503 scenario 5 ("the exemption is about the change, not the transport")
requires the classifier to extract *content*, not just *path*.

## Finding 6 — `auto_format` is name-keyed (consistency, not security)

`auto_format.py` is registered `PostToolUse` matcher `"Write|Edit"`, so MCP edits are
never formatted. Separately it invokes `black` with explicit file paths
(`["black", "--quiet", *files]`), which ignores `exclude` — `force-exclude` is required.
No `pyproject.toml` exists in this repo, so nothing is configured to be excluded and
there is no active harm; recording it as latent.

## Not confirmed / corrected

- **"`plan_gate.py` has zero `critic` references"** — confirmed (0 vs 18 in
  `plan_mode_exit_detector.py`).
- **"There is no critic enforcement on the harness plan-mode path"** — **corrected.**
  Issue #926 moved enforcement to `PreToolUse` in `unified_pre_tool.py`
  (`_check_plan_exit_native` / `_check_plan_exit_mcp`, marker `.claude/plan_mode_exit.json`,
  stages `plan_exited → critique_done`). Measured: with the marker at `plan_exited`,
  a native `Write` returns **deny**. `plan_mode_exit_detector.py` is only the marker
  *writer*; its `PostToolUse cannot block` docstring is accurate but it was never the
  enforcer. The gate exists and fires — it is simply in a different hook than the name
  suggests, and it inherits Finding 1's MCP hole.
- **"The plan-critic verdict is not persisted"** — **partly outdated.** Issue #1468
  shipped coordinator-owned persistence: `implement.md:1001` instructs the coordinator
  to call `write_verdict_from_output()` from `lib/plan_critic_verdict.py`. That covers
  the `/implement` path. It does **not** cover the harness plan-mode path
  (`EnterPlanMode`/`ExitPlanMode` outside `/implement`), which has no coordinator and
  no persistence step — which is where the lost REVISE verdict was observed.

## Inventory — every matcher in the repo

| Hook | Event | Matcher | Shape |
|---|---|---|---|
| `unified_pre_tool` | PreToolUse | `*` | matcher fine; **in-code** `("Write","Edit")` × 7 — Finding 1 |
| `plan_gate` | PreToolUse | `Write\|Edit` | **name-keyed** — Finding 2 |
| `enforce_file_organization` | PreToolUse | `Write\|Edit` | **name-keyed** — same class, unfixed |
| `enforce_tier_distribution` | PreToolUse | `Write\|Edit` | **name-keyed** — same class, unfixed |
| `auto_format` | PostToolUse | `Write\|Edit` | **name-keyed** — Finding 6 |
| `session_activity_logger` | PreToolUse | `Task\|Agent` | name-keyed; logging only, no enforcement |
| `plan_mode_exit_detector` | PostToolUse | `ExitPlanMode` | correct — that IS the event |
| `unified_prompt_validator` | UserPromptSubmit | `*` | fine |
| `unified_session_tracker` | SubagentStop | `*` | fine |
| `conversation_archiver` / `task_completed_handler` / compaction hooks | various | `*` | fine |

Three enforcement hooks beyond `plan_gate` carry the identical `Write|Edit` matcher.
Fixing `plan_gate` alone leaves `enforce_file_organization` and
`enforce_tier_distribution` bypassable by the same route.

## Recommendation

**The canonical classifier already exists — extend it, do not add a second one.**
`lib/tool_intent.py` (751 lines) is the repo's tool classifier, exporting
`classify(tool_name, tool_input) -> "READ"|"WRITE"|"EXEC"` and
`write_targets(tool_name, tool_input)`, with recursive Bash parsing and inline-Python
write detection already built. It ends at lines 176-178 with:

```python
# Unknown native tool, MCP tool, orchestration tool — EXEC by default.
# The hook applies its own per-tool rules to these.
return "EXEC"
```

That comment is the seam. It delegates the decision back to "the hook's own per-tool
rules" — which are precisely the stale hand-written lists catalogued above. Creating a
new `tool_effects.py` would violate the repo's own "one canonical way" rule and add a
third list.

The fix:

- extend `tool_intent.py` with explicit MCP read and write registries (seeded from
  `_PLAN_EXIT_MCP_READONLY`, plus Serena's read tools — which fixes Finding 3);
- extend `write_targets()` to resolve MCP path keys (`relative_path`, `path`);
- add transport-independent changed-content extraction so `plan_gate`'s simple-edit
  exemption survives the transport change (Finding 5);
- unknown tool + path-like arg + content-like arg → classify `WRITE` (fail closed),
  with telemetry naming the tool so the registry is extended deliberately;
- unknown tool + path but no content → stays `READ`/`EXEC`, so `find_symbol` (which
  carries `relative_path`) is not blocked.

Every gate then consults `tool_intent.classify()` instead of a literal tuple. A CI
shape test asserts no enforcement hook contains a bare `("Write", "Edit")` tuple, so the
shape cannot come back.

Registry-first is mandatory, not stylistic: MCP's own `readOnlyHint`/`destructiveHint`
annotations (MCP spec 2025-03-26) are **not delivered to hooks** — the PreToolUse payload
carries only `tool_name` and `tool_input` — and the MCP spec directs clients to treat
them as untrusted regardless. There is no declared-effect signal to consult.

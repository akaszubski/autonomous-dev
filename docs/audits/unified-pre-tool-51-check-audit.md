# Audit: all 51 checks in `unified_pre_tool.py`

**Date**: 2026-08-21. Three parallel audits, split by semantic category, identical
output schema. Read-only; nothing changed.

**Why**: a plan exists to reduce this file's check count. Block frequency tells
you what fired; it cannot distinguish *"correct and rarely needed"* from *"fired
and did nothing"* from *"could never fire."* Deletion decisions need intent, not
counts.

**Framing that produced the most valuable findings**: a hook firing is not a hook
enforcing. Three states exist, and only the third is enforcement:

1. Never fires — unreachable or flag-off
2. **Fires and returns nothing that acts** — advisory, log-only, or fail-open
3. Fires and refuses

Block counts only ever see state 3.

---

## Finding 1 — the "fires and does nothing" surface

| Check | Lines | Why it enforces nothing |
|---|---|---|
| `_check_bash_code_file_pipeline_required` | 140 | **Advisory-only** since #1408. Classifies a tier, logs, prints `[hook advisory]` to stderr, falls through. Code comment: *"This is no longer blocked."* |
| `_maybe_invoke_swe_router` | 62 | Log-only. Comment: *"Phase A MUST NEVER affect hook behavior."* |
| `validate_sandbox_layer` | 56 | Opt-in via `SANDBOX_ENABLED`, default **false** |
| `validate_batch_permission` | 41 | Opt-in via `PRE_TOOL_BATCH_PERMISSION`, default **false** |
| `_is_adev_project` | 9 | *"No longer called from active code paths"* after #1361's polarity flip |

**~308 lines that cannot refuse anything.**

Note `validate_sandbox_layer` is the layer `59f526b4` "removed" — that commit
changed 4 template files (4 insertions, 4 deletions, zero code) to set
`SANDBOX_ENABLED=false`. The function is still called from `main()` seven months
later. **The precedent in this repo is flag-off, not deletion, and the
flagged-off code still executes.**

## Finding 2 — the fail-open surface

**127 paths** where a firing check degrades to allow:

- **93** `except ...: pass` — swallow silently
- **34** `except ...: return <allow-shaped>`

Including three named gates that allow on any internal error:

```
:1617  except Exception -> return ('allow', 'Pipeline ordering check error (fail-open...')
:1701  except Exception -> return ('allow', 'MCP security error — default allow')
:1351  except ImportError -> return ('allow', 'prompt_integrity module not available')
```

This is not hypothetical. **#1471**: the prompt-integrity shrinkage gate stopped
enforcing after a field rename — the deny-message f-string raised
`AttributeError`, a broad `except Exception: pass` swallowed it, and execution
fell through to `return ("allow", ...)`. *"Every compression-critical agent
invocation was waved through."*

The audit's own words: *"Fail-open design is LOAD-BEARING. A typo in a regex could
silently disable protection. No automated regression tests found."*

**The recording mechanism fails open too.** `unified_pre_tool.py:283-292` wraps
the `hook_telemetry` import in `except Exception` and substitutes a no-op
`block_event_decorator` and a `log_block_event` that returns `None`. If that
import ever fails, every block still fires and **none is recorded** — the log
shows zero, indistinguishable from "no blocks occurred."

Every block-count measurement in this repo, including the ones in this audit,
rests on an instrument that can silently return zero.

## Finding 3 — a documented guard that does not exist

`_detect_realign_bypass` docstring: *"Only active when the current project
contains realign markers."*

There is no such gate. The only occurrence of "marker" in the function is that
sentence. It fires on **every Bash call in every repo**, so a
`python -m mlx_lm.lora` invocation is blocked in repos with no realign
relationship at all.

Either the gate was never written or it was removed. Taxonomy: declared-but-absent.

## Finding 4 — ADVERSARIAL checks share one structural limit

All 8 command-string inspectors are blind to the same five things:

1. Variable indirection — `export $COMPUTED_VAR=value`
2. Command substitution — `--title "$(cat /tmp/x)"`
3. `eval` / `bash -c` wrapping
4. Heredocs beyond the top level
5. Base64 or other encoding

This is **not a bug in any individual check**. Shell is Turing-complete;
inferring intent from a command string without executing it cannot be made
complete. Evidence in-repo: `stash@{0}` holds a #1570 fix attempt marked
FAIL-Critical with **65 bypasses remaining**.

The audit also names **concatenative bypass** — chaining two individually-simple
evasions defeats checks that handle each alone.

**Implication**: hardening these by adding patterns is an arms race with no
end state. The only durable move is to constrain the channel so the bypass is
inexpressible, rather than detect it.

## Finding 5 — native-expressibility, measured per check

Of the 15 WHERE/SAFETY/legacy checks: **0 fully native-expressible**, 4 partly,
11 not.

The blockers are consistent: agent identity from stdin/env, pipeline-state
inspection, walk-up marker detection, issue-number scoping, time-window caches,
and AST analysis of Python snippets. None expressible as a static glob.

Two additional constraints found in prior art that the plan had missed:

- `.claude/plans/1409-write-to-edit-permission-migration.md:6` —
  `Write(path)` / `NotebookEdit(path)` / `Glob(path)` rules are **never matched
  by Claude Code**; only `Edit(path)` / `Read(path)` match.
- Per #1503 the hard floor is transport-independent via `tool_intent.is_write()`,
  covering MCP editors such as `mcp__serena__replace_symbol_body`. **Native
  permission rules match MCP tools by name, not by path**, so path-scoped
  MCP-editor denial is not natively expressible at all.

And measured: **1,118 of 5,094 path-floor blocks (21%) arrived via Bash.** No
`Edit()` glob matches a Bash command string.

Conclusion: moving the path floor to native permissions would silently drop
Bash-transport and MCP-transport coverage.

## Finding 6 — two deferred audits left in the code

```
:5334  "env-var read here may also be dead; audit deferred"
:4774  PIPELINE_ISSUE_NUMBER "may also be dead; audit deferred"
```

Someone noticed, wrote it down, and deferred. Twice.

## Finding 7 — a shared-state dependency in /tmp

Three checks (`_detect_gh_issue_marker_creation`, `_detect_gh_issue_create`,
`_detect_daily_aggregate_direct_filing`) depend on a context file written by
`_maybe_write_issue_context`. Concurrent sessions share that path; last write
wins. Acknowledged in #1206 and unfixed.

---

## What this changes about the deletion criterion

Frequency was the wrong axis. It cannot separate the three states, and it rests
on a log whose recorder can no-op.

**The replacement is four yes/no questions, answerable from code:**

1. Can it emit a refusal at all? (`validate_sandbox_layer` cannot — flag off)
2. Is anything wired to act on that refusal? (the Bash gate is not — advisory)
3. Is it reachable from `main()`? (`_is_adev_project` is not)
4. Does it survive its own error paths? (127 places say frequently not)

This is a better criterion for a reason beyond accuracy: **deleting something
that provably cannot refuse carries no enforcement risk.** It was already inert.
That is a completely different risk profile from deleting a low-frequency guard
that works — the mistake nearly made with `_check_rm_rf_unresolved_vars`, whose
8 blocks were all `rm -rf` with an unquoted variable, and which reached the hook
*past* an existing `Bash(rm:-rf*)` native deny.

## Recommended first action

**Fault injection, before any deletion.** For every gate, force its internal
error path and assert the outcome:

- import fails → does it still refuse?
- state file unreadable → refuse?
- classifier returns garbage → refuse?
- log unwritable → refuse?

A gate that allows under fault is not a gate. Fail-open may be the *correct*
behaviour — a broken hook must not lock someone out of their editor — but it must
be **loud**, not one of 93 silent `pass` statements.

This is the test that would have caught #1471 on the day it shipped.

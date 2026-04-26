# Hook Composition Contract

**Issue**: #942 (umbrella) → #969 (#942-A bypass) → #970 (#942-B recoverability) → #971 (#942-C tool-intent) → #972 (#942-D capstone)
**Status**: Wave 1 complete (all four pieces shipped)
**Last Updated**: 2026-04-26

This document is the contract for adding new hooks to `plugins/autonomous-dev/hooks/`. Every hook in the harness MUST honour the four invariants described here, in this order: bypass → recoverability → intent classification → telemetry.

The pattern was forged from a triage session that produced four independent deadlocks (#937, #938, #941, plus a settings-write false-positive). Each underlying hook was correct in isolation; they failed when they composed. This contract prevents that class of bug.

---

## 1. Universal Bypass (#942-A — shipped #969)

Every hook MUST honour two equivalent bypass signals before doing any work:

```python
from hook_bypass import is_bypassed, log_bypass_used

if is_bypassed():
    log_bypass_used(hook_name="my_hook.py", tool_name=..., reason="...")
    sys.exit(0)  # or return "allow"
```

The two signals:
- **Env var** (process-scoped): `AUTONOMOUS_DEV_BYPASS=1`
- **File flag** (project-scoped): `touch .claude/.bypass`

Both are settable from OUTSIDE Claude Code so a deadlocked harness cannot prevent recovery. See [`plugins/autonomous-dev/docs/TROUBLESHOOTING.md`](../plugins/autonomous-dev/docs/TROUBLESHOOTING.md) section "Universal Escape" for end-user instructions.

**Why**: A hook that requires the harness's own machinery to be healthy is not a hook — it's a deadlock waiting to happen. The bypass mechanism MUST be reachable when every other gate is broken.

---

## 2. The Recoverability Invariant (#942-B — shipped #970)

Every gate that denies MUST first ask: "If I deny here, can the user actually recover?"

```python
from hook_recovery import can_user_recover, log_block_with_recovery

if would_block_decision:
    if not can_user_recover(hook_name="my_hook.py", block_reason=reason):
        # Either allow with warning, OR self-clear the offending state
        # so the user has SOME path forward.
        ...
    log_block_with_recovery(
        hook_name="my_hook.py",
        tool_name=tool_name,
        block_reason=reason,
        recovery_hint="Run /implement to advance the pipeline state",
    )
    return ("deny", reason)
```

Note: `log_block_with_recovery` is preserved as a back-compat shim that delegates to the new unified `log_block_event` (see Section 5). New hooks SHOULD use `log_block_event` directly.

**Why**: #941 was the canonical failure — Hook A said "this state file means the pipeline is active"; Hook B said "deleting an active pipeline state file is forbidden." Both correct in isolation; together, the user was trapped. A gate that creates an unrecoverable state is a bug.

---

## 3. Tool-Intent Classification (#942-C — shipped #971)

NEVER substring-match against command strings. Use the principled classifier:

```python
from tool_intent import classify, write_targets, has_suspicious_exec

intent = classify(tool_name, tool_input)  # -> "READ" | "WRITE" | "EXEC"
if intent == "WRITE":
    targets = write_targets(tool_name, tool_input)
    if any("settings.json" in t for t in targets):
        return ("deny", "Settings writes must go through /implement")
```

The classifier dispatches by tool name for native Claude Code tools (Read/Write/Edit/etc.) and parses Bash commands via `shlex.split` to identify the binary and its arguments. Python `-c` snippets are analyzed via the AST-based `python_write_detector`.

**Why**: The settings-write gate previously flagged `python3 -c "json.load(open('settings.json'))"` as a write because the command string contained "settings". `json.load` is a READ. Substring matching cannot distinguish read from write — the classifier can.

---

## 4. Read / Write / Delete Distinction Rules

Concrete rules for how to extract intent from each Claude Code tool:

| Tool | Read indicators | Write indicators | Notes |
|---|---|---|---|
| `Read` | always | never | Pure read tool |
| `Glob`, `Grep` | always | never | Pure read tools |
| `Write` | never | always | Pure write tool |
| `Edit` | never | always | Pure write tool |
| `NotebookEdit` | never | always | Pure write tool |
| `Bash` | `cat`, `grep`, `head`, `tail`, `ls`, `find`, `wc`, `jq` (no `-i`), `python -c json.load` | `>`, `>>`, `tee`, `sed -i`, `python -c json.dump` | Use `tool_intent.classify()` — do NOT regex |
| `Task` | depends on subagent | depends on subagent | Treat as opaque; rely on the subagent's own gates |
| MCP tools | per-server allowlist | per-server allowlist | Listed in `unified_pre_tool.py::MCP_READ_ALLOWLIST` |

**Anti-patterns to reject in code review**:
- `if "settings" in command:` — substring match, will false-positive
- `if command.startswith("rm "):` — argv parsing should use `shlex.split`
- `if "sudo" in command:` — `sudo` may legitimately appear in arg values

---

## 5. Telemetry Contract (#942-D — shipped #972)

Every gate MUST call `hook_telemetry.log_block_event(...)` immediately before returning a block decision. The single canonical log location is `.claude/logs/hook-blocks.jsonl`.

```python
from hook_telemetry import log_block_event

log_block_event(
    hook_name="my_hook.py",
    decision_shape="tuple",  # or "dict", or "exit2"
    reason="WORKFLOW ENFORCEMENT: ...",
    metadata={"tool_name": tool_name, "recovery_hint": "..."},
)
return ("deny", "WORKFLOW ENFORCEMENT: ...")
```

**Three deny shapes are supported** (the harness uses all three):
- `tuple` — `("deny", reason)`, used by `unified_pre_tool.py` via `output_decision`
- `dict` — `{"decision": "block", ...}`, used by `unified_prompt_validator.py`
- `exit2` — `sys.exit(2)`, used by `enforce_orchestrator.py` and similar pre-commit hooks

**Tooling**:
- Triage: `python scripts/hook_block_summary.py --last 7d --top 10`
- Rollback: `HOOK_TELEMETRY_DISABLED=1` (or the deprecated `HOOK_RECOVERY_DISABLED=1`)
- CI gate (Phase 1, warn-only): `pytest tests/integration/test_new_hook_contract.py`

**Migration note**: For one release cycle, the summary script reads BOTH `hook-blocks.jsonl` (new) AND `hook-recovery.jsonl` (legacy from #970). Rows are deduplicated by `(timestamp, hook_name, reason)`. The legacy `log_block_with_recovery` function is preserved as a shim that redirects writes to the new file. Existing call sites continue to work unchanged. New code SHOULD call `log_block_event` directly.

**Why**: The original #942 triage required manually grepping `~/.claude/archive/conversations/**/*.jsonl` to reconstruct empirical block data. That works once but does not scale, and the absence of a single log file means future triages cannot be automated.

---

## 6. Checklist for Adding a New Hook

Copy this checklist into the PR description for any new hook PR.

- [ ] **Bypass at top** — first action in `main()` is `if is_bypassed(): sys.exit(0)`
- [ ] **Recoverability before deny** — every `return ("deny", ...)` is preceded by either a `can_user_recover()` check OR a comment explaining why the deny is always recoverable
- [ ] **Intent classification for path decisions** — no substring matching against command strings; use `tool_intent.classify(...)`
- [ ] **Telemetry on every block** — every deny path calls `log_block_event(...)` before returning
- [ ] **Regression test for deny + recover** — at least one test in `tests/integration/` invokes the deny branch end-to-end and verifies a JSONL row appears
- [ ] **Hook registered in settings templates** — added to ALL `plugins/autonomous-dev/templates/settings.*.json` files
- [ ] **Hook listed in install manifest** — added to `plugins/autonomous-dev/install_manifest.json` AND `plugins/autonomous-dev/config/install_manifest.json`
- [ ] **Documentation entry** — `docs/HOOK-REGISTRY.md` row added; `docs/HOOKS.md` description updated

---

## Related Documentation

- [`docs/HOOK-REGISTRY.md`](HOOK-REGISTRY.md) — every active hook + its event + its env vars
- [`docs/HOOKS.md`](HOOKS.md) — high-level architecture of the hook system
- [`plugins/autonomous-dev/docs/TROUBLESHOOTING.md`](../plugins/autonomous-dev/docs/TROUBLESHOOTING.md) — user-facing recovery flows
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — contribution standards (cross-links here)

---
covers:
  - plugins/autonomous-dev/lib/path_utils.py
  - plugins/autonomous-dev/lib/agent_dispatch_sentinel.py
  - tests/helpers/state_isolation.py
---

# Pipeline Evidence Integrity

Two connected protections shipped under Issue #1779, and — stated first,
because it is the part that gets overclaimed — exactly what they do not
establish.

## Exact observed scope

Every statement below was measured on **this repository's source bytes**, on
macOS (Darwin 25.4.0), with `python3 -m pytest`. That is the whole claim.

It is specifically NOT any of the following, all of which remain **UNMEASURED**:

- deployed or installed equivalence (`bash scripts/deploy-all.sh` has not run);
- clean manifest-installed consumer portability;
- native Linux examination;
- universal carrier coverage — nothing here asserts that a hook always fires, or
  that every tool call is provably recorded.

The broader request-to-effect provenance route (correlating a real tool call to
its native effect through a durable receipt) is **not** part of this change. It
is owned by Issue #1780 and has no implementation here.

## Claim A — pytest-scoped production-state isolation

Two production trees were measured contaminated by the suite on 2026-09-12: the
activity log gained synthetic `session_id="test-session"` records, and the live
`.claude/local/implement_pipeline_state.json` was truncated to 0 bytes, taking
`alignment_passed`, `alignment_verdict` and `pipeline_base_commit` with it.

| Variable | Redirects | Chokepoint |
|---|---|---|
| `AUTONOMOUS_DEV_ACTIVITY_LOG_DIR` | `.claude/logs/activity/` | `path_utils.resolve_activity_log_dir()`, priority 1 — above `CLAUDE_PROJECT_DIR`, which real sessions point at the repository |
| `PIPELINE_STATE_FILE` | `.claude/local/implement_pipeline_state.json` | the pre-existing sentinel override every production caller already honours |
| `AUTONOMOUS_DEV_AGENT_DISPATCH_SENTINEL` | `.claude/local/active_agent_dispatch.json` | `agent_dispatch_sentinel._path()`, default branch only |

All three are set by `tests/conftest.py` as **environment variables**, not
monkeypatches, because the writers are separate **processes** an in-process patch
cannot reach. Duplicate activity-root resolvers were collapsed onto the one
chokepoint: `pipeline_completion_state._find_activity_log_dir`,
`coordinator_log._find_activity_log_dir`, `intent_classifier`,
`task_completed_handler._get_log_dir`, and `unified_prompt_validator._log_activity`.

`tests/helpers/state_isolation.py` holds the three consequences:
`hook_subprocess_env()` (the one sanctioned builder for a test that spawns a
hook — starts from `os.environ` and refuses an environment whose isolation
variables are blank or resolve inside the live `.claude/` tree),
`activity_root_inference_is_the_subject` (the opt-out for the few tests whose
subject IS the resolution), and `snapshot_tree()` / `describe_tree_leak()` (the
session-finish guard, SHA-256 over the whole tree, failing on any created,
modified or removed file in the outermost session — cleanup after the fact is no
substitute, since a synthetic record is observable while it is on disk).
`tests/unit/lib/test_hook_subprocess_env_ratchet.py` pins the call sites that
still replace the environment directly and refuses growth.

### Named residual: `get_legacy_sentinel_path()` is not redirected

`pipeline_state.get_legacy_sentinel_path()` does not consult
`PIPELINE_STATE_FILE`. Every production caller wraps it in that env-var lookup,
and its one unwrapped use is an `st_mtime` read, never a write — but a test that
calls it directly and writes the result bypasses the redirect. That is exactly
what the leak guard exists to catch, and it is why the `.claude/local/` watch has
**no exemption at all**: unlike `validators/<run id>/`, every file under
`.claude/local/` has a fixed name, identical whether the live pipeline or a stray
test wrote it, so there is no identity segment to key an exemption on and a path
carve-out would be the hole it exists to prevent. Exemptions elsewhere are keyed
on LIVE identity (`.heartbeat_<session id>`, `validators/<live $RUN_ID>/`), and an
absent or unusable identity yields NO exemption rather than a wildcard.

### The measured writer was a second route, not that residual

The route above is real but was NOT the one that fired. MEASURED 2026-09-12, by
timestamp on the live file across a single serial run of one module:
`tests/unit/lib/test_step5_quality_gate.py` overwrote
`.claude/local/coverage_baseline.json` with fixture values (`90.0 / 0 / 10`),
because 9 of its 10 `run_quality_gate()` calls reach the real
`coverage_baseline.save_baseline()`, which resolves
`get_default_baseline_path()` when given no path. Positive and negative control:
the file's `timestamp` field moved on a run before the fix and was byte-identical
on the same run after it. An autouse fixture in that module now points
`get_default_baseline_path` at `tmp_path`; the real `save_baseline` still runs, so
the gate itself is not stubbed. The remedy string in the guard names both routes,
because a remedy that names only one sends the next reader to the wrong file.

### Attribution belongs to the outermost session

Both watched trees are process-GLOBAL, so a session running concurrently with
other writers cannot show that a change is its own. MEASURED: under `-n auto`
that real `coverage_baseline.json` write landed inside the window of a CHILD
pytest session another test had spawned; the child reported the sibling's write as
its own and set exit 1 on a session where 15 tests had passed, failing the
parent's exit-code assertion. 13 test modules spawn such a child, and which one
failed varied run to run.

`session_is_nested()` therefore gates the two production-tree arms on an inherited
`AUTONOMOUS_DEV_PYTEST_SESSION_DEPTH` marker: absent or unparseable reads as
OUTERMOST, which keeps the guard ACTIVE. This is **not** an exemption and drops no
coverage — the outermost session watches the same two trees over a window that
strictly CONTAINS every inner one, so the same write is still reported, by the
only session that can own it. MEASURED with one variable changed, a top-level
session deliberately creating a file in the live tree: marker unset → exit 1 with
`created: [...]`; marker `1` → exit 0 with the file provably created; marker
`nonsense` → exit 1 (fail closed). The xdist controller itself imports this
conftest and runs `pytest_sessionfinish` (measured with `-n 2`: controller import
precedes both workers', and its finish runs last), so `-n auto` keeps its teeth.

Three mutations must break
`test_boundary_a_leak_binds_only_the_session_that_can_attribute_it`, each
verified to do so: dropping the `_ATTRIBUTION_POSSIBLE` conjunct from an arm,
hardcoding the flag, and removing the marker export. A fourth is left UNCOVERED
and named here: a hardcoded `False` is invisible to a run whose own session is
already nested, so the derivation assertion binds in serial runs only.

Two further limits, both MEASURED rather than argued. A rewrite whose bytes are
unchanged is not reported — content hashing, not mtime, so re-running the same
leaking probe twice reports clean the second time; the guard's subject is
observable state, not write syscalls. And a session that inherits the depth
marker from something other than an enclosing pytest run (a manual `export`) will
believe it is nested; nothing in the suite does that, and the fail-closed
direction covers the absent case, but it is a hole and not a proof.

A pre-existing `.claude/logs/activity/quarantine/` directory holds the one-time
recovery of records that were already on disk before these redirects existed. It
is preserved historical evidence, gitignored and local-only. There is no product
sweep API and none should be added to justify it.

## Claim B — a corrupt gating sentinel cannot become permission

`agent_ordering_gate.check_ordering_with_session_fallback()` treated a sentinel
that EXISTS but does not parse as a JSON object exactly like an ABSENT one.
`resolve_session_id()` already logged `[SENTINEL-UNREADABLE] … JSONDecodeError`
for that case and then continued its ABSENT-shaped fallback chain, so the gate
returned `passed=True` for `implementer` on state whose `alignment_passed` had
been destroyed.

`pipeline_completion_state.SentinelIntegrity` names three states, never two:

- `ABSENT` — the normal state of every session not inside a pipeline. Refusing it
  would block ordinary work, and it was never the defect.
- `CORRUPT` — the file exists and its gating fields cannot be read. Per INV-7
  that is a verification failure, and a verification failure is "not passed".
- `OK` — parsed as a JSON object.

`sentinel_integrity()` is deliberately independent of `resolve_session_id()`,
which short-circuits on `CLAUDE_SESSION_ID` and then never reads the sentinel, so
a resolvable session id is no evidence the gating state survived. The ordering
gate calls it BEFORE any completion lookup and refuses immediately on `CORRUPT`,
whichever agent is asking.

`unified_pre_tool._is_pipeline_active()` also stopped MANUFACTURING a 0-byte
sentinel. Its `.touch()` existed to refresh the owning session's mtime
(Issue #636); when the sentinel was absent it created one instead, so a genuinely
absent pipeline reported "exists but cannot be read" and the INV-7 gate refused on
state the hook had just fabricated. It now refreshes an existing sentinel and
creates nothing.

## Cross-test isolation: no test may purge a `lib/` module from `sys.modules`

A test that removes a bare-name `lib/` module from `sys.modules` and re-imports it
leaves every sibling test module holding a DEAD object. A sibling that bound
`import pipeline_completion_state as pcs` at COLLECTION time then patches the dead
object, while the code under test does `from pipeline_completion_state import
get_plan_critic_passed` at CALL time and gets a different module — so the patch
silently stops reaching the gate, and the gate answers from real `/tmp` state.

MEASURED 2026-09-13, serial, one variable changed. Any of the three purgers ahead
of `tests/regression/test_issue_1330_plan_critic_gate.py` turned
`test_allows_after_plan_critic_passed` into `BLOCKED: Architectural-decision
creation detected`; the same two files in the REVERSE order gave `20 passed`. The
identical two-file command fails at frozen base `06fa938b`, so this is latent
order-dependence, NOT a consequence of the redirects above. Over the 87 test files
that reference either purged module, run serially: base 33 failing ids, candidate
before this fix 39, candidate after 24 — `after - base` is EMPTY and `base - after`
names nine ids the purge alone was breaking.

The remedy is SUBTRACTION, not a new mechanism: the purge is deleted at all eleven
sites across `test_issue_906_background_doc_master.py` (7),
`test_issue_1174_post_dispatch_recording_protocol.py` (2) and
`test_issue_852_doc_verdict_completion.py` (2) — verified by `grep -c 'del sys\.modules\['`
per file. `importlib.import_module` on the cached
object is enough — the module has no import-time mutable state (no module-level
`os.environ` read, no non-constant module global), and the `monkeypatch.setattr` on
`_state_file_path` each site already performs is what actually isolates it, undone
per test by pytest. `importlib.reload` remains safe where used elsewhere in the
suite: it re-executes in place and preserves identity.

The rationale lives here rather than in those three files because the rung's
1,500-line proof budget had one line of headroom; the fix itself costs zero added
proof lines.

## See also

- `tests/regression/test_issue_1779_connected_core.py` — permit, different-shape
  refuse, and broken-instrument arms for both claims
- [docs/TESTING-STRATEGY.md](TESTING-STRATEGY.md) — the Minimal Vertical Proof
  Method these two claims were built under

# Workflow-assurance release census — reconciliation checkpoint

Date: 2026-09-25. Owner: [#1757](https://github.com/akaszubski/autonomous-dev/issues/1757).
Source population: commit `401c1ff0ffbaa56b99e78740ebb154d9669154b7` in
`autonomous-dev-1779`; subsequent `1802394b` changes intent/docs only.
Canonical execution: [workflow-assurance plan](../plans/20260916-workflow-assurance-subtraction.PROPOSED.md).

**Status: candidate inventory, NOT a frozen complete denominator or product proof.**
Two independent read-only audits enumerated source/policy routes and shipping/
registration surfaces. They found concrete omissions in the existing scanners.
The unresolved rows below stay in scope; neither UNKNOWN nor archived means retired.
All acceptance rows below are UNMEASURED for the replacement release.

Instrument progress since the population snapshot: source-route correction
`01a13368ab068536493a45299ca8c46b6adad910` is committed and pushed on
`fix/1757-census-carriers` and integrated here as `d6e76665`.
Its corrected walk reports 238 modules, 148 REACHED and 90 UNKNOWN; the original
141/97 figures below remain historical snapshot results, not current verdicts
from that corrected instrument. No module was thereby proved to execute.
The follow-on checkout-location correction completed specialist review and is
committed as `21090df0239436b4923fc668e2ab8c2c97eebe28` on that same source branch;
it is integrated here as `261fbd43`:
ratchet SHA `7818342b3b38b2d9340cdf1a1e3ecc819d04db2bed160916968406b255a99faf`
passed all 281 tests with process exit 0 in an isolated checkout under `.codex`
(93.40 seconds). This establishes that tested location behavior, not a frozen
denominator. The refusal-envelope source-inventory correction is committed and
pushed as `a4650e631302b944b3f73a1183d1e0cc1520794f` on the same branch
and integrated here as `e615974f`. Its settled source run reported 373 passing
tests with a separate #1779 activity/state guard causing raw process exit 1;
the combined affected suite in this canonical checkout passed 373 tests with
raw process exit 0 in 101.65 seconds. Independent review retained the actual
paid-dependency envelope as UNKNOWN without counting it as a verified denial.
The first spec-blind review was
disqualified for below-floor source reads; a fresh constrained review passed.
This was temporary assurance growth (+714/-34), not product subtraction or
native proof. The extension census-omission source fixture was committed as
`379fd673` and integrated here as `9fd2cbb9`; the canonical owner suite passed
16 tests with raw process exit 0. It compares a separately authored selected-entry
claim with observed execution markers and fixture files; removing only one claim
row makes the same reconciliation refuse without re-running the hook. This is a
source-fixture fault control, not native consumer activation or a frozen release
denominator. Consumer reconciliation and the native extension rows remain open;
see the [current restart checkpoint](20260925-workflow-assurance-checkpoint.md).

### Remaining inventory-freeze work

Current continuation correction (2026-09-26): the #1801 regex repair and first
#1805 parser-like candidate were rejected and remain preserved, uncommitted
evidence. [#1805](https://github.com/akaszubski/autonomous-dev/issues/1805)
now specifies a conservative source boundary: backtick-bearing PROGRAM lines
credit no library stem, while ordinary quoted interpreter operands remain
supported. Valid shell execution and static support are separate claims; exact
changed member sets must be published rather than preserving an old count by
re-pinning. #1803 and #1804 remain separate unresolved instrument defects.
The redesign session is terminal after a signed run-identity loss; its candidate
cannot be resumed as an authorized run. #1807 requires fail-closed handling, not
reconstruction of signed authority from an unsigned completion ledger.
The #1806 lock-GC correction also remains an integration/deployment prerequisite
before overlapping fresh `/implement` runs. These are current execution pointers,
not acceptance of any candidate or a frozen denominator.

Independent read-only review separates inventory closure from later product proof:

1. Reconcile the integrated source-route, location and refusal-envelope
   corrections' selected lists without dropping UNKNOWNs or treating
   source candidates as observed runtime denials. Resolve the distinct
   backtick-assignment over-credit below before freezing the library
   denominator; a passing reachability test is not proof that its selected
   route executed.
2. Expand the family rows into exact control/path/caller/profile obligations,
   intended retain/migrate/retire dispositions, acceptance IDs and owning issues;
   resolve the context-size transition, legacy registrations and commit validators.
3. Freeze CLEAN-0/POPULATED-3 recipes and supported consumer boundaries, baseline
   and last-known-good identities. Discover or explicitly disposition remaining
   remote/older transport populations; a named slot does not prove its contents.
4. Reuse the now-passing omitted-entry source fixture as an instrument check;
   demonstrate the populated consumer's registered invocation, marker-deny and
   neighbor-permit with one census row omitted and unchanged runtime behavior,
   then publish the finite table on #1757.

All 97 original UNKNOWN members already received bounded source inspection and
the five declared local consumer checkouts were inspected below; do not restart
those audits merely because their historical snapshot counts remain in this file.
Native control acceptance, installation/lifecycle proof and actual retirement
follow the freeze in dependency order; they are not prerequisites to specifying
their obligations. Unknown remote contents and the omitted-entry fault control
remain inventory blockers, not permission to claim completeness prematurely.

Backtick-assignment instrument defect ([#1801](https://github.com/akaszubski/autonomous-dev/issues/1801), separate from the shipped #1757 source
correction): `tests/unit/hooks/test_hook_reachability_ratchet.py:8119` records a
synthetic `helper_path="`pwd`/plugins/autonomous-dev/lib/synthetic_target.py"`
assignment followed by `python3 "$helper_path"`. The full walker returns
`REACHED` solely because its older `_COMMAND_POSITION` regex treats a backtick
inside the assignment as a command boundary; the same-file binding recognizer
correctly declines to resolve the computed right-hand side. This is **not**
runtime evidence that the target file executed. Its honest static verdict is
`UNKNOWN` unless an independent observed execution establishes otherwise.
The bounded repair must first make this assignment-only false-green `UNKNOWN`,
preserve a positive control where a literal library path actually occupies a
shell command position, and preserve the existing live registered route pins.
It must also challenge a real executable backtick command-position case so a
regex narrowing does not discard legitimate coverage. Run the ordinary corpus
and an omitted-route mutant after the repair. Do not change the runtime hook,
build a general shell interpreter, or silently reclassify dynamic paths as
unreachable; record any unresolved syntax as `UNKNOWN`.

Before freezing a row, add its claim-specific evidence contract: governing intent,
required direct observation/effect, observation method and authority, subject/run,
limitations and missing-evidence outcome. For each time-sensitive row, declare its
observation interval, the governing requirement or dependency that justifies expiry
or change invalidation, trusted clock and uncertainty bound, and consumption-time
recheck. Exercise valid evidence and every declared invalidation or uncertainty
boundary; never impose expiry where dependency invalidation is sufficient.
Configuration, inventory, native behavior and outcome
evidence are not interchangeable. Time proximity never supplies identity; historical
receipts remain historical when no longer valid for a current transition.

## Observed populations and instrument limits

| Instrument / source | Result | What it does not establish |
|---|---|---|
| Existing library reachability walk, cache disabled | 238 modules; 141 REACHED, 97 UNKNOWN; 122 entry surfaces | Installed behavior; an independent source-only denominator (it also reads settings) |
| Top-level hook source / refusal-sink AST scanner | 34 files (28 Python, 6 shell); 10 syntactic refusal candidates | Complete refusal population: `_emit('deny', ...)` in `validate_paid_dependency.py` is missed |
| `unified_pre_tool.main` local AST call closure | 33 check/detect/enforce/validate-named function candidates | 33 independent controls; helpers/classifiers are included |
| `proof_of_block.py::GUARDS` AST registry | 8 cases, 7 unified-pre-tool and 1 plan-gate | Coverage of every active control or a new test run |
| Hook sidecars | 34: 15 lifecycle, 19 utility; 17 declared lifecycle bindings | Other templates register utility-labelled hooks too |
| Eight package settings surfaces | 73 binding entries; 23 event/matcher/owner shapes; 19 script owners plus echo | Effective settings precedence or actual duplicate firing |
| Python dictionary AST census | 9 additional legacy-schema declarations in setup/updater | Whether the pinned harness accepts these schemas |
| Config manifest | 443 unique existing source paths | Effective activation or exact deployed tree |
| Plugin-root manifest | 424 unique paths; 185 sources absent; config-only 208/root-only 189 | Whether this duplicate manifest still has an active installer caller |
| Commands | 26 Markdown files, 23 marked user-facing | Required execution of their embedded state transitions |
| Plugin scripts | 22 Python main-guard CLI candidates | Invocation or consumer availability |

Current integrated refusal-instrument reconciliation at `e615974f`:
`refusal_candidates()` returns 11 files. Ten have known syntactic refusal
evidence (the original count is retained); four have unresolved computed
decision envelopes. Three of those four are mixed known+unresolved
(`plan_gate.py`, `unified_pre_tool.py`, `validate_claude_md_size.py`), while
`validate_paid_dependency.py` is unresolved-only in this source instrument.
Thus the union adds one visible file without converting its computed decision
into a verified denial. These are source classifications; the installed/native
event and actual permit/refuse outcomes remain unmeasured. The counts come from
the integrated owner functions on this checkout, not the older table snapshot.

JSON census inputs: `plugins/autonomous-dev/config/global_settings_template.json`,
`templates/settings.{autonomous-dev,default,granular-bash,local,permission-batching,strict-mode}.json`
under that plugin, and `.claude-plugin/default-settings.json`.
Their respective binding counts are 17, 18, 8, 9, 0, 9, 11 and 1.
No individual surface repeats an event/matcher/owner tuple. Global/default surfaces
share seven such tuples and overlapping logger matchers; these are duplicate-execution
candidates, not observed double execution.

The sidecar generator's `--check` reports no drift on its selected inputs despite
the other manifest and generator discrepancies. Preserve that bounded success;
do not use it as release-wide consistency evidence.

Refusal-inventory correction (source `a4650e63`, integrated `e615974f`,
native run `bfe7b4009d4aa95a`; source evidence only): reuse
`test_refusal_sink_ratchet.py::_python_refusal_evidence` and its existing evidence
strings to retain variable-valued decision envelopes as unresolved candidates.
Do not add a special `_emit` spelling or a new parameter-binding engine merely to
recognize `validate_paid_dependency.py`. This conservatively closes the observed
omission class; it does not prove an envelope is emitted or a denial occurs.
The sink, recording and reachability source-instrument consumers now distinguish
UNKNOWN candidates from literal denial evidence using one shared classification.
Their unresolved inventory retains computed values even when the file also has
a sink, recorder or lifecycle registration. Runtime permit/refuse proof remains
separate. No complete denominator is claimed from this correction.

Bounded implementation contract (independent owner review): change the existing
`test_refusal_sink_ratchet.py` dictionary arm and evidence vocabulary, then adapt
its `out_of_sink_refusers` consumer, `test_refusal_recording_guard.py`'s
`unrecorded_refusers`, and `test_hook_reachability_ratchet.py`'s
`unreachable_refusers`, observer premises and orphan-voucher filtering. Keep the
existing evidence containers and one shared known-versus-unresolved distinction;
do not copy classification logic between these three owners. Retain unknown sites
even when the same file also contains known literal refusals. Existing pins retain
their original known-refuser meaning; unresolved inventory remains explicit rather
than being silently dropped or converted to verified refusal.

Reuse existing synthetic fixtures and parameterized both-arm tables to establish:

- The actual paid-dependency source retains its variable-valued envelope as UNKNOWN.
- Both decision keys with variable/call/expression values remain UNKNOWN, including
  helpers called with literal allow versus deny when no binding analysis exists.
- Literal refusal and literal allow/comment/docstring controls retain their existing
  meanings; parse failures stay loud.
- Adding a sink, recorder or lifecycle registration does not resolve the UNKNOWN
  site; mixed literal and unresolved evidence retains both obligations.
- Removing the unknown-evidence arm or filtering its entries fails the inventory
  completeness control while the source and its behavior remain unchanged.

A green regression result may prove honest UNKNOWN reporting, not complete denial
coverage. This correction adds no runtime hook, scanner, binding engine, store or
per-emitter special case, and does not require performing the later migrations.

Checkout-location correction (source `21090df0`, integrated `261fbd43`): the exact
source candidate produced an empty corpus under a `.codex` ancestor and a nonempty
corpus after moving the unchanged checkout to a neutral parent. `_library_paths`
applies exclusions to absolute `path.parts`, including ancestors outside the
selected project. Keep the existing owner, globs and exclusions, but evaluate
exclusions within the selected project-relative path; do not introduce a new
resolver or alter symlink semantics incidentally. Reuse the existing fixture/case
table to compare normalized corpus/reached/unknown identities under neutral and
excluded-name ancestors, including the project-root basename. Parameterize the
existing exclusion names and assert explicit nonempty expected corpus, reached
and unknown identities, not equality alone. Internal excluded-directory fixtures
must fall within matched globs, with an ordinary neighboring directory included,
so the exclusion check cannot pass merely through glob omission. Keep the original
collected paths and existing glob/is-file behavior unchanged. A required empty
corpus must not pass. The isolated `.codex`-ancestor proof above and completed
specialist review establish this bounded correction; they do not establish native
execution or complete inventory coverage.

## Candidate acceptance matrix

IDs here identify release outcomes, not newly implemented runtime gates. Freeze
each actual control and consumer row after reconciling the route populations below;
retain existing frozen F0 case IDs and their required ordering unchanged.
`P` denotes `plugins/autonomous-dev/`; all paths below are source owners, not
claims that the installed owner has already been chosen or qualified.

| ID / family | Existing decision/route owners | Required acceptance / fault | Stage / issue |
|---|---|---|---|
| WA-E1 examination/provenance | `bootstrap/control_trust/`; private frozen F0 capture; `P/hooks/session_activity_logger.py`, `unified_session_tracker.py`, `task_completed_handler.py`, `conversation_archiver.py` | Actual required execution/reads, native request-result-hook-telemetry identities and effects; missing/false/stale/forged evidence non-pass | F0, #1773/#1573/#1751 |
| WA-E2 gating receipts | `P/lib/pipeline_state.py`, `pipeline_completion_state.py`; `P/hooks/unified_pre_tool.py` | Signed current-run/subject receipt permits next transition; missing/corrupt/wrong-run/wrong-subject/expired receipt refuses | T0, #1757 |
| WA-S1 sensitive writes | `P/hooks/PreToolUseWrite-protect-sensitive.sh`; `P/lib/tool_intent.py`; unified-pre-tool classification | Built-in/MCP ordinary permit and prohibited refusal; real payload keys, renames, fault/missing hook; no duplicate decision owner after migration | W0, #1673 |
| WA-S2 containment | Approved native sandbox/profile and file permissions; existing sandbox/MCP validators | Allowed useful work and prohibited file/network/process effects; hook failure must not remove containment; no unsupported-profile inference | F0/W0, #1773/#1673 |
| WA-W1 protected writes | Unified-pre-tool protected-infrastructure, nested-path, production-write and Bash-write checks | Actual pipeline permits; direct/bypass/env-spoof/unresolved-path write refuses; preserve hard floor and test/protected-state integrity | W0/M0, #1757; #1435/#1503/#1142 |
| WA-W2 planning/order | `P/hooks/plan_gate.py`, `plan_mode_exit_detector.py`; unified-pre-tool plan/ordering checks; `P/lib/agent_ordering_gate.py` | Required plan and specialist sequence observed; absent/revised plan, missing specialist, premature transition refuses | T0/M0, #1757 |
| WA-W3 command transitions | `P/commands/implement{,-batch,-fix,-resume}.md`; pipeline completion/run-lock APIs | Full/light/fix/batch/resume obligations via real command route; no fabricated completion or warning-only pass of required failures | T0/M0, #1757 |
| WA-W4 prompt/authorization | `P/hooks/unified_prompt_validator.py`; unified-pre-tool prompt/MCP/agent/batch authorization validators | Actual required input and permissions; tampered/missing instructions or wrong actor refuses | M0, #1757 |
| WA-W5 issue/drain/retrofit workflow | Unified-pre-tool daily-aggregate filing, issue-marker/create, drain-pending-commit and realign-bypass decisions | Valid issue/commit/retrofit route permits; bypassed prerequisites and duplicate direct filing refuse through actual caller | M0, #1757 |
| WA-D1 docs/skills | `P/agents/doc-master.md`; existing doc-verdict/completion consumers; four priority skills | Changed behavior covered, false no-impact conclusion rejected, independent substantive review and effect checks; retain unique value | F0/T0/M0, #1757 |
| WA-O1 additional refusers | `P/hooks/enforce_file_organization.py`, `validate_claude_md_size.py`, `validate_paid_dependency.py` | Each real allow/refuse/fault route; include paid dependency emitter despite scanner omission | M0, #1757 |
| WA-O2 unresolved source controls | `P/hooks/enforce_orchestrator.py`, `enforce_prunable_threshold.py`, `enforce_regression_test.py`, `enforce_tdd.py` | Resolve caller/consumer and retain/migrate/retire with outcome coverage; unknown is not silent exclusion | Census/M0, #1757 |
| WA-O3 dynamic extensions | `P/hooks/unified_pre_tool.py::_run_extensions` and selected consumer extensions | Discover effective extension population; deny/permit, disabled/missing carrier and omitted-census-entry refusal | Census/M0, #1757 |
| WA-O4 remaining source/legacy candidates | Other members of the 34-hook source corpus and 22 CLI roots; 97 UNKNOWN libraries in the original `401c1ff0` snapshot, 90 under corrected walk `d6e76665` (later integrations not yet rerun) | Reconcile callers and decision/evidence dependencies rather than classifying unused by filename; preserve each required outcome or justify retirement. Neither count is a frozen current denominator | Census/M0, #1757 |
| WA-L1 plugin lifecycle | Config/native/plugin manifests, `P/lib/settings_merger.py`, existing installers/updaters/resolvers | Source-free installed root, one version/registration owner; clean/populated install/update/repeat/interruption/rollback/uninstall preserves unrelated configuration | D0, #1755/#1758/#1759/#1521/#1522 |
| WA-L2 delivery routes | `install.sh`, `P/scripts/install.py`, deploy scripts, `P/lib/sync_dispatcher/`, setup/sync commands | Every affected active transport/consumer migrated or explicitly dispositioned; no source fallback or stale extra copy | D0/M0, #1757/#1521/#1522 |
| WA-L3 commit controls | Configured active `scripts/hooks/pre-commit` and its five archived-hook invocations | Prove applicable shell-branch behavior; each required outcome remains covered before relocating/retiring an archived owner | Census/M0, #1757 |
| WA-C1 retrofit | Dogfood, distinct clean and populated consumers | Independently verified installed workflow/lifecycle cases without source/ambient configuration; record unsupported profiles | Final, #1636 |
| WA-C2 portability | Required Claude/Codex process-result/evidence case, unchanged future core | Exact native profiles, real observed events and joined results; observation is not enforcement parity | After W0, #1757/#1636 |
| WA-M1 subtraction | All included families and necessary private helpers | Dependency-inclusive net code/test/owner/configuration/operator burden reduction with retained distinct fault coverage | Every migration/final, #1757 |

### Draft case allocation — not a frozen denominator

These suffixes allocate the existing outcomes to reviewable cases; they add no
control, runner, owner or acceptance authority. Source/caller and owning issue
remain in the table and reconciliations below. Existing `a`–`e` control IDs are
reused, not renamed. Mode, tool and consumer variants parameterize the existing
cases; they are not independent gates. Frozen F0 IDs/order remain unchanged.
Every row still needs its claim-specific evidence contract described above.

- **WA-E1-01…05:** required examination, request/result identity, hook/telemetry
  join, effects, and missing/forged/invalidated evidence. Profile: frozen Linux
  F0. Retain independent oracle; next observation is qualifying native evidence,
  not another local-suite pass. R0 extraction remains after accepted F0.
- **WA-E2-01…04:** valid transition receipt, absent/corrupt receipt, wrong
  run/subject, and declared invalidation. Profiles: applicable full/light/fix/
  batch/resume. Migrate to the existing guarded completion consumer; next trace
  must show actual receipt consumption, not an unwired state API.
- **WA-S1-01…04:** built-in permit/refuse, MCP payload permit/refuse, rename/
  side-effect writers, and classifier/carrier faults. Profiles: CLEAN-0 and
  POPULATED-3. Migrate to one decision owner, retire shell duplicate after proof;
  next freeze actual tool schemas and observe installed opposite arms.
- **WA-S2-01…05:** useful allowed work, prohibited file/network/process effects,
  and hook-loss containment. Profile: exact approved Linux sandbox. Retain native
  containment; next observe effective boundary configuration and effects.
- **WA-W1a…e:** reuse the five write-control rows below. Profiles: applicable
  workflow modes and consumer policy. Migrate required a–d outcomes; e receives
  no enforcement credit. Next observe actor/path/bypass faults through the real
  caller; arbitrary Bash containment belongs to WA-S2.
- **WA-W2-01…04:** research eligibility, current plan/critic, revised-plan
  invalidation, and specialist order. Profiles: full/light/fix/batch/resume with
  their exact eligibility clauses. Consolidate markers/profile definitions;
  next observe authorized reuse/omission separately from missing execution.
- **WA-W3-01…05:** acceptance allocation, implement/test/spec, review/security/
  docs, CIA/completion, and batch/resume identity/lock. Profiles: actual command
  modes. Migrate competing completion authorities; next observe required role
  returns, wrong-item faults and lifetime lock through actual transitions.
- **WA-W4-01…06:** prompt routing, instruction integrity, escalation-response
  provenance, actor authority, MCP/native permissions, and explicitly enabled
  batch permission. Profiles: applicable native callers, optional batch only
  when selected. Retain native permission ownership; next prove real current-run
  response → guarded dispatch (#1802), not an asserted approval boolean.
- **WA-W5-01…05:** aggregate dedupe, issue-create authority, drain commit role,
  post-push closure/clear, and realign route. Profiles: generic workflow plus
  explicit dogfood/realign specialization. Retire powerless marker only after
  consumer disposition; next join actual issue/drain effects. Watchdog execution
  remains a subprocess route, not a Claude tool event.
- **WA-D1a…d:** reuse doc examination, verdict transport, impact selection and
  priority-skill rows below. Profiles: actual full/fix/batch and same-task skill
  trials. Retain semantic role, migrate credit/selection to existing owners;
  next exercise omitted reads and always-no-impact, then measured skill value.
- **WA-O1a…c:** reuse organization, context-size and paid-dependency rows below.
  Profiles: applicable declared native events. Migrate required outcomes; next
  qualify the selected commit-time context-size transition below and observe paid `_emit` refusal.
  A post-write diagnostic is not write prevention.
- **WA-O2-01…04:** orchestrator, prunable threshold, regression and TDD. Profiles:
  remaining installed/manual consumers plus applicable fix/raw-commit/TDD modes.
  Retain UNKNOWN caller status and conditional dispositions below; next reconcile
  effective/remote/manual callers and prove replacement before stale-copy removal.
- **WA-O3-01…05:** extension set, marker-deny/neighbor-permit, disabled/missing
  carrier, omitted inventory row, and cross-layer duplication. Profile:
  POPULATED-3 installed consumer. Retain extension capability; next execute the
  omitted-row intervention with files/settings/behavior unchanged. FR1 is not
  product provenance or exactly-once proof.
- **WA-O4-01…03:** remaining hook/CLI candidates, UNKNOWN-library cohorts, and
  external/manual API dispositions. Profiles remain unresolved per member.
  No retirement is inferred. #1803/#1804/#1805 block source-denominator freeze;
  next settle the instrument, rerun corpus/omitted-route control, and attribute
  every changed membership before assigning exact per-member acceptance.
- **WA-L1a…d / WA-L2a…b:** reuse the delivery-owner rows below, mapped to existing
  D0-01…08 rather than a new lifecycle suite. Profiles: CLEAN-0/POPULATED-3.
  Select one native root/version/registration and owned transaction; next bind
  product/closure identity, settings behavior and affected transport consumers.
- **WA-L3-01…05:** command implementation, manifest consistency, settings-hook
  source/membership, installed import integrity and hook documentation. Profile:
  configured raw Git pre-commit branches. Consolidate required outcomes into
  existing owners; next execute missing/orphan/source-loss arms before retiring
  any archived invocation. Working-tree scans are not staged-only evidence.
- **WA-C1-01…04:** standalone, dogfood, CLEAN-0 and POPULATED-3, retaining separate
  results and existing D0-01…08 lifecycle arms. Next freeze supported Python
  3.11+ product/profile and last-known-good identities; historical Darwin startup
  and four-file fixture results cannot supply product acceptance.
- **WA-C2-01:** unchanged-core process/result case through real Claude and Codex.
  Profiles: separately pinned native harnesses after W0. Next freeze Codex carrier,
  sandbox/approval and correlation fields; version output implies no parity.
- **WA-M1-01…04:** dependency-inclusive baseline, per-slice retirement, cumulative
  net reduction and retained distinct faults. Profiles: each activated migration
  plus final release. Next bind pre-R0 burden/removal mapping; T0 cannot exit
  without cumulative reduction. Private scaffolding is not product subtraction.

The D0 recipe and evidence limits in **Consumer-profile selection** below govern
these allocations, superseding stale private-proposal observation status. Exact
native joins, permissions/hook composition, interruption points, remote contents
and product digests remain unresolved where recorded; draft IDs do not close them.

## WA-W1 write-control reconciliation (2026-09-25, not frozen)

| Actual owner in `unified_pre_tool.py` | Required outcome | Current gap / proposed subtraction |
|---|---|---|
| WA-W1a — Protected non-Bash infrastructure (`2004–2140`, `8798–8823`) | Applicable protected writes require actual dispatched implementer authority; hard floor survives bypass | Checks any active dispatch, not its agent identity; stored dispatch authority is unsigned. Wrong-agent and corrupt/missing authority are required negative cases, not valid permits |
| WA-W1b — Protected Bash infrastructure (`7839–8024`, `9352–9360`) | Same implementer-only outcome for applicable mutations | Active pipeline permits before actor validation; conservative string parsing has false negatives. Enumerated command cases alone cannot qualify arbitrary Bash or satisfy containment |
| WA-W1c — Nested plugin-source `.claude` (`2504–2608`) | Refuse nested source configuration while allowing legitimate root/installed layouts | Resolution faults permit; Bash is excluded. Preserve actual policy scope, but do not label unresolved applicable paths safe |
| WA-W1d — General production writes (`3399–3579`, `8860–8938`) | Applicable production writes require the selected workflow authority; legitimate non-code/test/profile exclusions remain distinct | Only native Write/Edit enters this gate; ordinary NotebookEdit/MultiEdit/MCP writes do not. Empty paths and plugin-only consumer recognition are gaps |
| WA-W1e — Bash production detector (`9143–9195`) | No enforcement credit for advisory-only output | Explicitly downgraded to advisory; retire the claimed guard/duplicate machinery unless a distinct required advisory outcome is demonstrated |

Candidate disposition for #1757: migrate WA-W1a–d to one installed, signed
authority/intent decision route before retiring their old branches; retire
WA-W1e's *enforcement* claim now, while preserving any independently justified
advisory value. This is a source-row mapping, not a claim that dynamic Bash or
the omitted MCP transports are qualified. Freeze exact profile and case joins
only after the effective consumer registrations are reconciled.

Reuse the existing classification/hard-floor responsibilities and signed-state
owner; this does not require preserving the present large files unchanged.
Required faults include wrong/unknown actor, absent/corrupt/wrong-subject authority,
classification loss and unresolved targets on every required transport. Missing
classification also misses content-less MCP rename/delete forms. A profile may
exclude a tool only when it is genuinely unavailable/outside required scope, not
to hide an applicable false permit. Dynamic Bash remains an unresolved required
obligation where enabled; observed narrow grammar is not release-wide proof.
WA-S2 owns native containment separately. No new shell parser is proposed here.

## WA-W2/W3 transition reconciliation (2026-09-25, not frozen)

Required outcome groups are plan entry, post-plan critique/entry, ordered specialist
dispatch, successful selected-profile completion before git, per-item batch
isolation, and exact-run resume with a lifetime-held lock. Each permits current
subject-bound valid evidence and refuses missing, failed, corrupt, wrong-run or
wrong-subject evidence; dispatch alone is not completion. Full/light/fix are
existing modes, batch wraps a selected mode, and resume continues that same mode.
Keep all eight invariant stage slots in the acceptance accounting. Record actual
current-subject execution, explicitly authorized current-subject reuse with its
evidence, or an authorized omission with the exact eligibility clause and evidence;
otherwise the slot is failed/unmeasured, never a generic N/A or inferred pass.
This is an interpretation of existing mode authority, not a new state vocabulary,
store, or permission to omit frozen F0 specialists.

| Mode | Existing authority and required eligibility evidence |
|---|---|
| Full | Execute the stages; research non-execution requires either authorized current-subject issue/cache research reuse, or the fully-specified omission route with all existing safeguards (`implement.md:765–846`). Reuse and authorized omission are distinct; neither is inferred from absence of research |
| Light | Only low-risk changes with no new logic or security-sensitive paths (`implement.md:2673–2690`); research may be omitted, planning still executes. Ineligible work escalates to Full; other specialist omissions must match the same explicit mode clauses |
| Fix | Research/planning omission is limited to a current evidenced failing-test/known-problem subject (`implement-fix.md:14–16`); missing eligibility refuses or escalates to Full |
| Batch/resume | Inherit the selected mode and exact item/run subject; neither grants additional omissions or allows another item's evidence |

The following eight reusable case families specify the remaining role/outcome
accounting. They are prospective expectations, not passed native cases or a freeze
of the entire release denominator. Keep them in the existing acceptance runner and
receipt owners; do not create a script/store for each row. Within the command
directory, `I` = `implement.md`, `F` = `implement-fix.md`, `B` =
`implement-batch.md`, and `R` = `implement-resume.md` (source anchors below).

| Case family | Positive evidence / existing transition | Distinct negative or boundary |
|---|---|---|
| Profile and alignment | Actual current-subject classifier result plus mode eligibility before research/plan/test-context; batch/resume retain the original mode. Fix's no-failure exit means no fix needed, not implementation completed (`I:705–760,2673–2699`; `F:14–16,209–225`; `R:28–49`). | Self-attested alignment, missing failing-test subject, ineligible light/fix, or silently accepted alignment drift. |
| Research | Both required full-mode research results, or evidenced current-subject reuse, or exact authorized omission; these are separate arms consumed before planning (`I:765–875`). Eligible light/fix omissions remain clause-bound. | Missing result, stale/unrelated cache, ignoring no-cache, unjustified omission, or unavailable research treated as success. |
| Plan and critic | Required planner content, structural validation and genuine current-plan critic PROCEED/reuse before implementation. Full's unregistered-critic exception needs the actual allowed invocation error and recorded reason; it is omission, not PROCEED or an F0 waiver. Light critic triggers above 400 words OR five files (`I:1107–1265,2701–2772`). | Provisional/self-authored or wrong-plan PROCEED; missing/failed critic; revision without fresh required judgment; fabricated unavailable-agent reason. Exercise 400/401 words and 5/6 files. |
| Acceptance-test allocation | AC-to-behavior evidence via the applicable acceptance-first, test-master/TDD or explicitly all-deterministic route; eligible light omits test creation, while fix identifies its existing regression or proves red/green (`I:1267–1318,2675`; `F:349–360`). | Missing required test-master; zero executions disguised as completion; registry-only coverage; deterministic cases lost from discovery; a regression passing both before and after. |
| Implement/test/spec | Real implementer effects, applicable test gate and fresh independent spec-validator result before review. Reused canonical ACs remain verbatim and subject-bound; fix returns RCA. Preserve PROJECT's 80% coverage minimum AND applicable full/light baseline-minus-0.5-percentage-point floor (`I:1455,1671–1731,1784–1809,2774–2806`; `F:237–401`). | Dispatch-only/fabricated credit, disallowed failure, wrong ACs, validator supplied implementation, missing RCA or lost governing coverage floor. Preserve explicit baseline-failure attribution rules, not blanket false-green permission. |
| Review/security/docs | Required current-subject role outcomes before final verification: full reviewer/security/doc-master; eligible light omissions only; fix security when triggered. Sensitive full route orders reviewer before security; remediation invalidates previous security PASS and requires renewed security/doc evidence (`I:1841–1857,1918–1960,2045–2099,2458–2474`; `F:405–565`). | Required role absent/failed, triggered audit omitted, premature security dispatch, pre-remediation PASS reused, or missing/shallow doc verdict accepted as warning. |
| CIA and completion | Actual nonempty CIA return before git/item success; fix additionally persists the full report and checks size before cleanup. Full post-git doc congruence still precedes cleanup (`I:2507–2519,2617–2669,2836–2848`; `F:644–737`). | Task ID without result, empty/placeholder report, premature cleanup or post-batch CIA substituting for per-item CIA. Optional UI/mobile/advisory checks and the triggered fix PROD checklist retain their existing authority; pending soft PROD verification is not falsely called verified or made a new hard gate. |
| Batch/resume identity | Exact signed run/subject/item/mode/attempt evidence, actual runtime/worktree and required carriers, successful-step reuse and lifetime lock through next-item/finalization/resume (`B:744–776,827–866,897–914`; `R:20–77`). | Wrong-item/session credit, missing/corrupt/unsigned authority, stale plan or lost lock, duplicate successful-step dispatch, final-item verification skipped. Single-run 4h/24h and changed-HEAD rules are NOT batch-resume rules (`R:25`); the 4–24h nonsecurity gap grants no inferred direct ratification. |

Apply missing/failed/wrong-subject evidence and disabled-required-carrier controls
through these same families. Eight stage slots remain visible as execution,
authorized current-subject reuse or clause-bound omission. Source review identified
these obligations; actual installed permit/refuse/fault evidence remains UNMEASURED.
The existing resume-owner viability prerequisite below is not resolved by this table.
Independent critique: round 1 required verbatim reused ACs, coverage floors,
post-remediation security/doc freshness and separate batch-resume timing authority;
rounds 2–3 checked those corrections and returned PROCEED. This approves the
prospective accounting, not native execution or the complete release census.

Completion reconciliation against PROJECT.md INV-2/3/7 and its evidence
requirements (independently reviewed 2026-09-25): operative stage clauses own
obligations, not stale agent-count summaries. A revised plan needs a fresh
independent critic PROCEED for that subject; planner revision alone is not the
critic's judgment. `Research: unavailable` records execution but remains unverified
and non-pass unless an existing authorized reuse/omission route actually applies.
CIA must return a nonempty outcome before git or batch-item advancement; FIX keeps
its stronger existing persisted-report check. Per-item CIA precedes per-item
completion verification; post-batch CIA is supplemental. Missing/shallow doc
verdicts and dispatched-but-unreturned agents cannot satisfy required judgments.
These correct assurance semantics, not mode eligibility or frozen F0 roles.
Resume-owner investigation: retain `pipeline_completion_state.py` as the proposed
single completion owner, not a second store. Its production writers currently
omit `run_id` and use session-hashed paths (`679–703,1003–1092`), whereas
`implement-resume.md:64–67` requests its unused run-keyed path. Ordering/commit
readers remain session-keyed. The bounded inspection of 15 current completion
files found legacy fields only, with no run-ownership or signature metadata;
completion-state code supplies no HMAC verification. The separate sentinel's
partial/legacy-permissive signature cannot certify those completion records.
This is a failed prerequisite, not a signed-resume capability.

Migration must converge actual writers, ordering/commit readers, batch items and
resume on the existing run-keyed path with verified exact subject/item identity;
sign all gating fields within the same locked atomic mutation and refuse missing,
corrupt, mismatched or unsigned authority. Session identity remains actor metadata,
not a substitute lookup key. Preserve records for the advertised resume window
rather than the current two-hour expiry, and never credit legacy unsigned files
as completed work. Select/reuse existing signing and persistence primitives only
after their behavior is verified; no competing store or new framework is proposed.
Owner viability also requires observed installed-profile persistence across the
advertised resume interruption/window: current `/tmp` storage, POSIX locking and
swallowed write errors are not proof. If existing path/key primitives cannot meet
that contract, selection remains unresolved rather than adding a store by default.

| Existing mechanism | Observed gap / consolidation prerequisite |
|---|---|
| `plan_gate.py:60–82,355–362,440–506` | Uses unverified `permissionDecision=block`, latest-plan selection and fail-open errors; migrate required plan outcome to a current-run transition owner before retiring this duplicate |
| Plan-exit observer → unified gate (`unified_pre_tool.py:8187–8563`) | Plaintext marker, absent/read-error permit and legacy marker treated critique-done; retain effective action gate but move authority to signed current-plan state |
| `agent_ordering_gate.py:19–91,200–204,291–328` | Required sets/order omit spec-validator and, in full, CIA despite command obligations; use one profile table for ordering and completion |
| Completion checks (`pipeline_completion_state.py:1997–2006,2034–2043,2599–2713`) | Import/load/error and some batch checks fail open; required judgment failures cannot become successful completion |
| Doc verdicts in full/light/fix/batch commands | Missing/shallow retry can proceed as warning; required doc judgment must remain non-pass instead |
| `implement.md:330–346` run lock | Lock is acquired in a short-lived Python process and released when it exits; the printed fd integer does not keep it held |
| `pipeline_state.py:606–714,786–881` | Transition APIs lack production callers; failed/partial state can become unsafe completion summaries. Keep only needed utilities or migrate them, not this unproven parallel authority |
| Resume (`implement-resume.md:64–67`) | Reads a completion store that `implement.md:213` says has no production writer; select one authoritative signed store |
| Batch (`implement-batch.md:761–776`) | TypeError degrades issue scope to session scope and continues; cross-item receipt substitution must refuse |

Canonical logical responsibilities remain the actual unified transition checks
and signed completion state, with one selected-profile definition—not a requirement
to retain every legacy implementation line. Preserve distinct mode outcomes and
failure detectors before retiring duplicate plan markers, state machines or gates.

## WA-W4 authorization reconciliation (2026-09-25, not frozen)

| Actual route | Intended retained outcome / consolidation | Current gap, not acceptable behavior |
|---|---|---|
| `UserPromptSubmit` → `unified_prompt_validator.py` | Human-text routing only; keep actual tool-action authorization with PreToolUse | Malformed input/crash permits; refusing a prompt does not establish enforcement of later tool calls |
| Native Agent/Task → prompt-integrity fast path (`unified_pre_tool.py:9840–9888`) | Preserve applicable specialist instruction integrity with the existing owner | Missing shipped validator, missing actor/type and corrupt baseline/cumulative state can permit; first-baseline establishment must differ explicitly from loss of established gating state |
| Alignment ESCALATE → `evaluate_and_record(..., user_approved=True)` → signed pipeline state ([#1802](https://github.com/akaszubski/autonomous-dev/issues/1802)) | A real explicit response to the exact current-run escalation may permit; an unobserved caller assertion must refuse | In a real `/implement --fix #1801` run, Claude supplied the boolean from standing workflow authority without asking the user. The library emitted `approval.source=ask_user_question` and `alignment_passed=true` despite no such round trip. Codex stopped before implementer dispatch; the original ESCALATE, false approval and corrective ESCALATE rows are retained. Prove approval provenance and wrong/missing/replayed response refusal through the actual guarded dispatch, not a model report or synthesized approval field |
| Native Write/Edit/Bash → actor fast path (`9725–9766`) | Refuse coordinator/unknown-actor protected code writes during an applicable pipeline; preserve legitimate specialist work subject to other gates | Missing/corrupt pipeline state must not erase an applicable obligation; signed-state integration remains required |
| Generic agent authorization (`6508–6677`, `9990–10005`) | Migrate any unique outcome to the existing effective owner before retiring the duplicate | Native tools return before this route, while meaningful branches require native tool names; direct unit calls are not native-route evidence |
| MCP authorization (`1845–1893`) | Qualify native permission ownership and retain specific workflow MCP controls | Optional validator module is absent; permissive fallback is not a security control and must not receive coverage credit |
| Optional batch permission (`6680–6720`) | Qualify only an explicitly enabled supported profile; native ask requires an observed user decision | Default is disabled; classifier loss/crash permits. Optional presence is not active enforcement |

Source review also found whole-hook malformed-input/crash paths emitting `ask`
(`8625–8655`, `10021–10026`). Neither permit nor refusal can be inferred without
the pinned native protocol and observed decision. Freeze applicable input, actor,
state-establishment and fault semantics; do not add a new custom authorization
layer to compensate for an unproven native owner. No route was retired here.

## WA-W5 issue/drain/consumer reconciliation (2026-09-25, not frozen)

| Existing route | Proposed retained outcome / owner | Gap or retirement prerequisite |
|---|---|---|
| Daily aggregate (`unified_pre_tool.py:5521–5576`, watchdog → `daily_aggregate_manager`) | One living aggregate through the existing manager; dogfood title/prefix policy belongs in its consumer profile | The watchdog's Python subprocess is not a Claude tool event. Unknown issue-list results must not become empty-list permission to create duplicates |
| Legacy issue-marker guard (`5213–5324`) | Retire protection for the powerless legacy marker; preserve real issue authorization below | Bounded inspection found no non-test authority reader/writer; confirm installed/manual consumers before deletion |
| Actual issue creation (`5671–5802`, `9395–9448`) | Current subject-bound authority from the actual registered issue command/specialist; refuse unauthorized direct/wrapped creates using the existing signed-receipt machinery | Global unsigned command/mtime context, broad active-pipeline allowance and missing-command warning/allow are not accepted authority |
| Drain commitment (`4326–4403`, drain-queue STEP 3.6/12.5) | Selected drain commitment precedes governed commits and remains until post-push issue closure is verified; reuse signed state | Read/import/parse failures currently permit. Bind required issue references to the actual commit role, not any arbitrary issue in the cluster |
| Realign raw-MLX bypass (`6188–6246`, `9705–9723`) | Move realign-only policy into its consumer profile/extension; preserve official-route permit and raw-route refusal there | Cwd heuristics and exception-to-permit are not generic toolkit policy or qualified applicability |

Drain source reconciliation: `implement-batch.md:27` requires the currently
processed issue in each per-issue commit and all cluster issues in a cluster
commit; the hook currently accepts any intersection with the cluster. Preserve
that role distinction in the eventual case/profile, rather than require every
issue in every per-issue commit or accept one issue for a whole-cluster commit.
Evidence must join issue command → authority → create and drain selection →
commit → post-push closure → clear. The aggregate and realign specializations do
not justify separate generic authorization frameworks. These are source-grounded
proposals; installed cases, signed-state behavior and retirement remain unproven.

## WA-D1 documentation and skill reconciliation (2026-09-25, not frozen)

The existing `doc-master.md` role instructs a `covers:` scan, affected-doc and
changed-source reads, semantic comparison, CHANGELOG/README updates where needed,
and a final `DOC-DRIFT-VERDICT`. Its own Step 4.6 and Step 5 explicitly say that
the word floor, self-check and verdict are **not** independent evidence of the
examination. `implement.md:2472–2506` can proceed with a warning after a shallow
or missing retry; `implement-fix.md:564–566` names the same fix-mode gap.
`pipeline_completion_state.py:2076–2178` still accepts retired verdict tokens and
legacy missing fields for batch credit, and returns success on state-read errors.
Those are distinct from the role's now-canonical output vocabulary (#1773).
No `NO_DOC_IMPACT` token was found in the inspected active doc role, commands,
hooks or libraries: it is a proposed *classification outcome*, not an existing
runtime owner or a presently enforced escape valve. #1796 belongs to the F0
public fixture/examination contract, not to this documentation-control family.

| Candidate control | Intended outcome / candidate disposition | Required positive, opposite and fault observations before acceptance |
|---|---|---|
| WA-D1a — actual doc examination (`agents/doc-master.md:30–97,120–128`) | Retain the specialist's distinct semantic comparison, but migrate examination credit to observed current-run reads joined to the changed-source and affected-doc denominator; a report alone never certifies itself. #1757, with F0 provenance owned by #1773. | A change with affected docs reads each doc and governing source before a supported PASS; a real no-affected-doc case permits a documented no-impact conclusion after the scan; omitted source/doc reads or a fabricated long PASS remain non-pass. Distinguish an empty `covers:` population from a genuinely unaffected change. |
| WA-D1b — verdict transport and guarded consumer (`commands/implement.md:2472–2506`, `implement-fix.md:564–566`, `implement-batch.md:213–223`, `lib/doc_verdict_validator.py`, `lib/pipeline_completion_state.py:2076–2178`) | T0 consumes one current-run accepted receipt before progression; retain parser compatibility for historical records only, then retire warning-to-proceed and legacy-missing-field *gate credit* after migration. Do not remove historical evidence. #1757. | Real valid examination and fixed docs permit progression; FAIL, absent/shallow verdict, wrong run/issue, corrupt state or disabled carrier refuse; a parser-accepted but role-invalid token cannot gain new-run credit. Exercise full, fix and batch routes through their actual consumers. |
| WA-D1c — impact selection (`agents/doc-master.md:35–62`, `lib/covers_index.py`, `lib/doc_drift_detector.py`) | Reuse one source-to-doc mapping/selection owner and independently test its denominator; retire any overlapping mapping only after its distinct coverage is mapped. A no-impact decision must be graph-grounded, not a default on missing index or scanner failure. #1757. | Changed covered behavior selects the relevant doc; an uncovered internal change may be no-impact with an explicit reason; stale/missing `covers:`, omitted source route, disabled selector and an always-no-impact mutant do not pass as verified documentation consistency. |
| WA-D1d — priority skill guidance (`testing-guide`, `architecture-patterns`, `documentation-guide`, then `planning-workflow`) | Retain each instruction only if same-task current/candidate/without-skill trials show distinct value; consolidate contradictions and duplicate instructions using the existing skill-evaluation entrypoint. #1757. | Verify actual discovery/delivery and useful task outcome; a silently undiscovered skill, conflicting combined guidance, or prose-only evaluator cannot count as an improvement. Two candidate iterations trigger a disposition rather than endless tuning. |

These rows are acceptance candidates, not four new gates, stores or scripts. Use
the plan's shared table runner and existing evidence/transition owners; qualify
the exact installed caller and selected consumer profile before promoting any
row. The 2026-09-25 source inspection above does not prove native examination,
impact correctness or retirement safety.

## WA-O1 outcome reconciliation (2026-09-25, not frozen)

Source inspection separates desired outcomes from existing permissive defects;
current behavior is not automatically the replacement acceptance contract.

| Candidate case / owner | Known declarations (not full population) | Candidate disposition / issue | Outcome to preserve and prove | Gap before freeze |
|---|---|---|---|---|
| WA-O1a — `enforce_file_organization.py` | PreToolUse Write/Edit/MultiEdit/NotebookEdit/MCP in `config/global_settings_template.json` and `templates/settings.autonomous-dev.json`; installed activation unmeasured | Migrate the refusal outcome to one proven installed owner, then retire the old registration; #1757 (historical #1034) | Permit allowed root names and below-root writes; refuse disallowed repository-root writes; preserve denial under emitter/telemetry dependency failure | `_repo_root()` conflates a genuine non-Git context with Git failure/timeout; malformed input permits; classifier-loss fallback covers native tools but not MCP. Applicable lost obligations are fault gaps, not permitted cases. |
| WA-O1b — `validate_claude_md_size.py` | PostToolUse Write/Edit/MultiEdit/NotebookEdit in those same two declarations; no declared MCP matcher; installed activation unmeasured | Migrate any required refusal to an existing guarded transition, retaining the post-write diagnostic only if it adds distinct value; #1757 (historical #1648) | Detect over-ceiling/overlap findings, distinguish warnings, and retain absolute-ceiling fallback when the committed ratchet cannot be read. Preserve touched-context applicability: unrelated edits must not inherit an old oversized-file refusal. Freeze permitted absence per profile; changed subjects invalidate prior observations, and warnings remain distinct from required refusal. | Runs after the write. A printed block envelope does not prove write prevention or a later guarded transition; no persistent gating state/later consumer was identified. Unreadable existing files and malformed payloads currently skip measurement. Select and observe the governed transition before claiming enforcement; unmeasured applicable content cannot authorize it. |
| WA-O1c — `validate_paid_dependency.py` | PreToolUse Write/Edit/MultiEdit/NotebookEdit/MCP in those same two declarations; installed activation unmeasured | Migrate the refusal outcome to one proven installed owner, then retire the old registration; #1757 | Permit clean production content and excluded test/non-Python targets; refuse prohibited production client construction and classifier import loss | Malformed JSON currently permits; the local `_emit` was missed by the scanner before the source-inventory correction. Native refusal and joined evidence remain unproven. |

These are candidate per-control rows, not frozen acceptance or proof that a native
registration executes. The named declarations were parsed from those JSON files;
other templates, user settings and the effective merged profile still require
reconciliation. The current repo-local `.claude/settings.json` has no `hooks`
object, so that file cannot establish these routes. The earlier WA-O1 family reference to
#1639 was incorrect: that open issue concerns the alignment gate, not this
context-size hook. #1757 owns release reconciliation; #1648 is historical.

Source anchors: file organization lines 93–115, 181–205, 374–429, 508–599;
context-size lines 350–469, 898–1064; paid dependency lines 79–91, 133–196.
Freeze the supported Git/MCP/payload fault domain and allowed file absence with
each consumer profile. Do not silently exclude a supported invocation because
its classifier, observation or payload failed. Existing bypass switches describe
current configuration, not new authority to waive hard floors or release gates.
Any selected persisted state governing a later transition must meet INV-7;
diagnostic telemetry alone is not that state. Prefer an existing transition owner
over adding a new gate or parallel state store.

Prospective contract selection, not implemented or qualified: WA-O1b refusal
belongs to the existing actual commit transition, shared with pipeline pre-git
validation, rather than a claim of post-write prevention. Evaluate touched context
in the selected committing tree against its pinned reference HEAD/ratchet,
including partial staging, renames and deletions; permitted absence remains
profile-specific. Do not inspect newer unstaged bytes as the committing subject.
Preserve warning-only overlap findings separately from required ceiling refusal
and the existing absolute fallback. Unmeasured applicable content cannot authorize
the transition. Changed tree/reference invalidates earlier proof; prove the
checked subject is the committed subject or revalidate/refuse. Qualify raw commit
and pipeline routes separately, preserve unrelated staged/unstaged bytes, and
reuse existing owners rather than a new post-write gate or state store.

WA-O1b evidence contract: governing intent is accurate applicable context with
one existing transition owner. Subject is the selected committing tree plus
reference HEAD and profile; authority is the independently checked existing
context validator on those inputs, not the authoring agent's report. Direct
observation must bind the validator result to the tree consumed by the actual
commit/pre-git caller. Validator, ratchet/configuration or subject-byte changes
invalidate prior proof; consumption rechecks those identities or refuses.
Dependency invalidation, not an arbitrary time expiry, governs freshness here.
Missing/uninspectable applicable inputs or a missing result are non-pass.
Post-write diagnostics and current implementation do not establish that claim;
exact consumer/result identities remain to be frozen before qualification.

## WA-O2 bounded source disposition (2026-09-25)

Independent read-only review at `0decd8d3730982ab36cfdb42d7634076fac9ecd3`
found no production AST import, subprocess, dynamic execution or lifecycle
registration for the four named hooks. Tests and `scripts/capture_baseline.py`
execute them; the latter runs hooks with synthetic input, not lifecycle events.
All four sidecars are utility-labelled. Packaging a file is not activation.

| Owner | Proposed disposition, pending consumer proof |
|---|---|
| `enforce_orchestrator.py` | Migrate required alignment outcomes to existing workflow/commit owners, including strict raw commits; retire recent-session/commit-message heuristics only after separate consumer proof. Write alignment alone does not qualify commit progression. |
| `enforce_prunable_threshold.py` | Migrate its findings-based commit refusal to the existing commit/pre-git owner before removing the unconnected hook/sidecar. The connected dashboard's deletable-file metric is not an equivalent replacement. |
| `enforce_regression_test.py` | Migrate required regression protection across full/fix and applicable raw bug-fix commits to existing workflow/commit owners; then retire the stale-message/staged-filename heuristic after consumer proof. |
| `enforce_tdd.py` | Migrate strict-profile test-before-code obligations to existing evidence/progression owners, preserving dogfood versus explicit strict-consumer applicability; retire session/history heuristics only after consumer proof. Ordinary acceptance-first is not strict temporal TDD. |

These are proposals, not deletion authorization or completed migration. Global
absence and actual runtime activation remain **UNMEASURED**; bounded local static
inspection follows. Inspect effective merged settings, remote and manual callers;
distinguish benchmark events from
joined lifecycle invocations; freeze each remaining permit/refuse obligation; then
prove owned stale-file/registration removal preserves unrelated settings. WA-O2
remains open until those checks and dispositions are complete.

WA-O2 evidence contract: governing intent and applicable profile are the four
selected outcomes below, not historical hook presence. Subject is the candidate
and, where required, its bound run/item and pre-fix baseline. Authority is the
independently checked applicable alignment/analysis/reproducer/chronology owner;
required direct observation is its actual result consumed by the guarded caller.
Candidate, baseline, profile, governing intent or checker changes invalidate proof;
the caller rechecks bindings at consumption or refuses. TDD ordering is observed
event order with bound identity, not timestamp proximity or a new expiry window.
Missing, wrong-run, stale or unavailable applicable evidence is non-pass; explicit
inapplicability is inactive, never enforcement success. Exact consumer carriers
and native results remain UNMEASURED, with no new store or certification agent.

WA-O2 pruning contract selection (prospective, not implementation or acceptance):
preserve the shipped findings-based threshold from #863 rather than infer its
retirement from #1317's separate CIA/dashboard correction. Applicability remains
profile-bound: #863 was strict-mode opt-in, not a default-on
gate. This selection does not activate it in default consumers. Existing analyzer and
commit/pre-git ownership must evaluate the bound candidate subject; no new hook,
authority store or automatic deletion is authorized. Freeze these paired cases:
findings at/below the profile's threshold permit; above-threshold findings refuse
with actionable explanation; analyzer/root/input unavailable is non-pass for an
applicable check; findings above threshold still refuse when deletable-file count
is below threshold. Qualify raw commit and pipeline routes separately, recheck a
changed subject, and record explicitly supported opt-outs as inactive rather than
successful enforcement while preserving hard floors. Default threshold is 100
in the current source; pin the effective value with each consumer profile.
Sidecar removal requires replacement both-arm and consumer proof. No existing
dashboard metric or report alone supplies that evidence, and no noisy-test
classification authorizes deleting tests without examining their distinct value.

WA-O2 regression/TDD contract selection (prospective, not current enforcement):
reuse existing bugfix/regression and workflow/commit owners rather than another
hook or store. Regression cases cover full, fix and applicable raw bug-fix commit
routes separately: a genuine reproducer fails against the bound pre-fix subject
and passes against the candidate; an existing failing reproducer may provide the
same protection without a redundant new test. Missing or always-green reproducers
refuse, non-bugfix work permits, and missing baseline/subject evidence is non-pass.
Test-count growth or a staged test filename alone cannot prove regression value.
This preserves #737's regression outcome and existing-test exception while using
the execution plan's distinct-failure-detector rule rather than test-count growth
as the release proof.

For strict TDD profiles, preserve observed tests-before-code chronology, not merely
acceptance text written before implementation. Pin the applicable profile: current
legacy source treats dogfood as mandatory and other consumers as explicit strict
opt-in; this selection does not extend strict chronology to non-strict consumers.
Cases permit no applicable production change and bound qualifying test-first
execution; refuse applicable production change without that evidence and wrong-run,
stale or unbound session/history substitutes. Record non-strict applicability as
inactive rather than successful TDD. Batch/resume inherits the selected profile
and bound item/run; neither a full-pipeline pass nor `--tdd-first` in another run
qualifies the raw-commit subject. Actual caller, both arms, ordering and consumer
evidence remain required before removal; no chronology receipt is yet accepted.

WA-O2 orchestrator contract selection (prospective, not current acceptance):
reuse existing alignment and commit/progression owners. Full/fix/batch cases
require a current bound alignment verdict for eligible progression; missing,
wrong-run or stale verdicts refuse. The strict raw-commit case independently
requires alignment for the candidate subject; recent session prose, commit
keywords and a bare `alignment_passed` boolean are not trusted evidence.
Subject changes revalidate/refuse, and batch/resume remains item/run-bound.
ESCALATE permits only an observed exact user response to the current escalation;
caller-supplied approval and replay refuse, retaining the separate #1802 cases.
Pin explicit docs-only/non-strict/optional-PROJECT applicability in each consumer
profile rather than infer it from legacy fall-throughs. Missing PROJECT when the
profile requires alignment is non-pass; supported inactive profiles are recorded
as inactive, never successful alignment, and cannot relax protected hard floors.
Raw commit qualification remains separate from native write qualification. No
legacy completion heuristic or source-only owner mapping closes these cases.

Local installed follow-up: dogfood, `realign` and user-global copies of all four
hooks match the reviewed source hashes. Parsed project/user settings, bounded
installed hook/library imports and both active Git hooks contain no located
registration or executable caller. All four remain shipped in installed manifests
as utility sidecars; `active:true` metadata does not establish lifecycle activation.
The prunable/regression sidecars' claimed library importers are prose references,
not actual AST imports. This narrows the gap to **no activation found in these
three bounded local installations**, not global absence: remaining local consumers
are inspected below; remote hosts, external schedulers and native-host discovery
remain UNMEASURED.

Remaining declared local checkouts were then inspected: `spektiv` (`69f2d916`),
`homeassistant` (`7cb8d332`) and `vllm-mlx` (`1911937e`) all have installations
containing the same four hook hashes, matching utility sidecars and deploy-state
entries. No activation was located in parsed settings, installed hook/library
imports or active Git hooks. An archived quality dispatcher names an absent
archived TDD file and skips before execution; this is not a live caller of the
shipped top-level TDD hook. Older `anyclaude` has no located local checkout, which
does not establish absence of an installation elsewhere. Remote slots and actual
runtime activation remain UNMEASURED across every declared consumer.

## WA-O3 bounded extension census (2026-09-25)

Read-only inspection of dogfood, distinct local consumer `realign`, and user-global
extension directories found no `*.py` extensions. Each installed unified-pre-tool
hook matched source snapshot `0decd8d` with SHA-256
`ee8ec71c236f513877c5ee004f6149911c767bef05b2ff50f3a93ce30fbb06c9`.
Both consumers declare project-local registration; user settings also declare a
global registration. Effective native merge, physical firing count and inherited
environment remain UNMEASURED; static parity does not establish activation.

The existing `_run_extensions` owner searches hook-adjacent then cwd project
directories, skips symlinks, deduplicates basenames first-wins, and blocks only
exact `deny`. `HOOK_EXTENSIONS_ENABLED=false` disables discovery. Missing files,
load/check errors and malformed returns currently allow; qualification must not
mistake that permissive runtime behavior for evidence completeness.

Discovery is invocation-relative, not unconditional user-home discovery:
`Path(__file__).parent/extensions` precedes `Path.cwd()/.claude/hooks/extensions`.
With a project-local hook at project-root cwd those slots coincide; a separately
registered global hook may see a different population. Bind the invoked hook path,
cwd, effective switch, concrete candidates/digests, symlink/shadow exclusions and
basename winners to the consumer observation. Record the executed prefix separately
from discovery because the first denial returns early. Non-native calls in projects
not recognized as autonomous-dev exit before extension dispatch; do not claim
all-tools coverage from directory membership. Shipped source contains the empty
slot, not the `block_raw_mlx.py` documentation example as an installed extension.

Freeze four rows through existing owners: (1) populated enabled marker-deny plus
neighbor-permit with actual registered invocation observations; (2) the same files
disabled in the real process environment, with zero execution and an explicitly
inactive census; (3) required missing carrier yields qualification non-pass, while
declared valid-empty remains distinct; (4) unchanged files/behavior with one omitted
census entry yields independent denominator failure. The source-fixture arm of
row 4 passed at `9fd2cbb9` (16 owner tests, raw exit 0), with separately authored
fixture and claim lists, one real hook call and the same acceptance predicate in
both arms. A separate real Claude 2.1.236 disposable-project observation is saved
privately at `/Users/akaszubski/.codex/artifacts/adev-o3-native.heCDz1/evidence/RESULT.md`
(SHA-256 `fe31ac64343a71248bd14bba167850e2dcb855cd207ea12d769732c3a1875cbf`).
Its registered PreToolUse:Read hook allowed an ordinary target and refused a
denied target, with actual Claude tool results, hook debug decisions and paired
extension-process markers. An omitted inventory claim failed the independent
eligible-`*.py` comparison while a full claim matched. Disabled and missing
extension runs exposed the denied target and therefore cannot be counted as
qualified enforcement. Independent review found that the case file postdates the
first allow/refuse runs, the top-level CLI exit/permission-denial output was not
preserved in the artifact, between-run hash stability was not separately receipted,
and the disabled-env/missing-file interventions lack independent pre/post receipts.
Thus these are bounded native observations, not a pre-frozen or accepted WA-O3
qualification row. A later preregistered FR1 replay of the same disposable
project saved five CLI JSONs and session JSONLs, debug decisions and complete
8/6 extension marker snapshots. Its case file predates the first native call;
allow and refuse reproduced, and a failed disabled-switch setup was preserved
as INVALID before a correctly flagged retry exposed the denied target with no
extension executions. A missing-extension run saved before/intervention/after
filesystem receipts, exposed the target and restored the exact extension hash.
Full versus omitted inventory claims still diverged under one external equality
predicate. Independent review confirmed these bounded observations and their
limits; see private `evidence/FR1-RESULT.md` under the same artifact root
(SHA-256 `2528cfe838148981587527e4ec85dc9d93f08283b3df85ab1c6d4496d789795c`).
Per-arm hash snapshots and exact command/exit receipts are not all preserved in
that artifact; no common event ID or product gate is established. The required
isolated POPULATED-3 installed-consumer omission arm, native merge, cross-layer exactly-once,
all-tools coverage, F0 provenance, D0 lifecycle and Linux remain unproven here.
Mutation between census/load and fail-open exceptions also remain unresolved.
Reuse the existing extension marker/order/dedup fixture patterns for these rows;
the independent omitted-entry comparison must leave files, registration and actual
behavior unchanged and remove only the inventory entry. These are specified
acceptance obligations, not an implemented or passing census verifier.

The three additional local consumers above contain settings declaring repo-local
unified-pre-tool registration
but have **absent extension directories**, unlike the present-empty dogfood and
`realign` directories. Their static discovery also yields zero; do not classify
that as valid-empty until each profile explicitly permits an absent carrier.
No `HOOK_EXTENSIONS_ENABLED` setting was found in the inspected hook/env keys;
inherited process environment and effective native merge still require observation.

## WA-L1/L2 delivery-owner split (2026-09-25, not frozen)

These are distinct current writers and resolution paths, not one proven
installer. The shipping-route table below retains their consumer obligations;
the D0-01…D0-08 cases in the selected profile supply lifecycle acceptance.

| Candidate control | Source route and proposed disposition | Required D0 observation / unresolved fault |
|---|---|---|
| WA-L1a — installed identity | `P/.claude-plugin/plugin.json`, `P/.claude-plugin/marketplace.json`, `P/plugin.json`, `P/config/install_manifest.json` disagree on version/Python floor; retain native packaging but select one installed root/version owner. | D0-01 binds executing hook, library and registration bytes to the installed artifact; injected source or extra copy must fail. A manifest value is not execution evidence. |
| WA-L1b — native/settings composition | `P/config/global_settings_template.json`, `P/templates/settings.local.json`, `P/.claude-plugin/default-settings.json` overlap in permissions; the global/default layers also declare divergent hooks, while `settings.local.json` has an empty hooks object. Retain only the owned effective projection. | D0-02/03 preserve unrelated populated layers and refuse conflicts without mutation; D0-04 observes one physical hook process joined to the event/decision, including a duplicate-layer fault. |
| WA-L1c — additive settings writers | `lib/settings_merger.py:310–321,431–442,560–657` merges owned settings; `lib/sync_dispatcher/modes.py:52–101` has another project-settings writer that can return success on error. Migrate to one proven transaction before retiring duplicates. | D0-02/03 preservation and conflict refusal; D0-05 repeated update/idempotence; failed write cannot be reported as an installed success. |
| WA-L1d — replacement writers | `lib/sync_dispatcher/dispatcher.py:834–932` may replace project `settings.json.hooks` after a nonblocking local merge; `scripts/sync_settings_hooks.py:189–257` replaces whole `hooks` and `permissions.deny`. Migrate each affected active caller before retirement. | D0-03 zero-mutation conflict and D0-04 no duplicate process; include existing consumer hooks/permissions as sentinels rather than judging only the toolkit's keys. |
| WA-L2a — setup/sync source routes | `commands/setup.md:32–43` has source fallback; `commands/sync.md:11–16` calls a global dispatcher; `lib/sync_dispatcher/cli.py:299–312` defaults to GitHub, while `modes.py:241–308,461–482` and `dispatcher.py:626–806` retain different copy/fetch paths. Migrate callers to the selected installed resolver before retiring any route. | D0-01 source-free execution, D0-05 update and D0-08 uninstall/route disposition; absence of a non-test internal caller does not prove an external/manual route unused. |
| WA-L2b — bootstrap/deploy/update | Root `install.sh`, `scripts/deploy-all.sh`, and the independent `P/scripts/install.py` route require separate active-consumer decisions; keep the latter UNKNOWN until manual callers and unique effects are checked. | D0-01/02/06/07/08 cover install, populated state, interruption, recovery and removal; remote installed contents remain UNMEASURED. |

`unified_pre_tool.py:666–704` can resolve sibling, global or marketplace
libraries; the D0-01 case must bind the actual imported path and bytes, not the
first plausible declaration. The current startup-only fixture does not prove
cross-layer permissions precedence, physical exactly-once execution, installed
product behavior or Linux support. No row above authorizes deletion yet.

Bounded actual transport observation (2026-09-26): private pinned source
`3b85f3de` ran canonical `deploy-all.sh --local --no-global` into a disposable
populated consumer, with no network or outside-root persistent writes. Independent
review verified clean source gate/stamp and successful settings replacement, then
loss of an unrelated SessionStart registration and custom deny rule; other
declared sentinels survived. Execution ended127, so installation did not complete;
preservation is separately FAIL. Original strict-equality observation and the
required-member recheck are both retained, never rescored into a pass. See private
`adev-populated-deploy2.9FLsak/RESULT.md`; this supports WA-L1d's existing defect,
not native hook/product qualification. The earlier `exaIQ6` envelope ERROR remains
preserved. Do not bypass preservation or manually repair the failed subject to
qualify the populated omission case; fix the canonical writer and re-prove.

### #1809 mutation-route admission — draft, not installed proof

Source-known routes below remain migration/retention candidates, not observed
activation. Remote, timer and manual populations remain UNKNOWN. Admission must
cover each resolved target before its first mutation and exclude concurrent run
start throughout the transaction; a check-then-write or per-run lock alone is
insufficient. `P` retains the plugin-root meaning used above.

| Source-known entry / first mutation boundary | Required disposition or D0 evidence |
|---|---|
| `scripts/pull-plugin-update.sh:177–189` and `P/lib/drain_runner.py` / `P/commands/drain-queue.md:617–639` → deploy | Preserve deferred rollout distinctly; timer tag consumption and drain's non-fatal handling cannot certify success. |
| `scripts/deploy-all.sh` → global `mkdir/rsync:308–310`, local `367–368`, remote `585–586,654`; later purge/settings/chmod | Per-target admission must precede all affected mutation paths, not only a wrapper's pull. |
| `scripts/deploy_local.sh:80–86,204–205`; `scripts/deploy-to-repos.sh:70–71,98–99` | Migrate to canonical route or qualify identical admission; do not retain independent unchecked copies. |
| `P/lib/sync_dispatcher/{modes,dispatcher}.py` → target creation, copy, GitHub writes, settings replacement | Cover direct mode/marketplace callers and separate project/global targets, including rollback/uninstall boundaries. |
| `P/scripts/sync_settings_hooks.py:246–257` → parent/temp/settings replacement | Refuse active-run mutation and preserve unrelated settings; this is a scripts route, not a lib route. |
| Root `install.sh:1443,1479,1594,1663` → target creation/copies and later registration writers; reset/MCP migration branches `579,1228` | Admit before first consumer mutation; staging is not consumer activation. Attribute reset, MCP migration, uninstall and rollback first writes separately. |
| `P/scripts/install.py:775,671,467–470` → target creation/staged commit/direct target write | Check mode remains read-only; staged download does not establish atomic activation; current target writes can truncate. |
| `P/lib/install_orchestrator.py:274,290,378,411,501` → install/backup/upgrade/rollback removal | Preserve recovery/data outcomes for every retained caller. |
| `P/lib/update_plugin.py:431` → `plugin_updater.py:401–403` pre-install cleanup, then `462,1011,1054,890,699,1239–1243`; `orphan_file_cleaner.py:477,517` removes installed lib | Admission must precede cleanup, not just sync or backup. Include project/global writes, installed-library deletion and rollback; nonblocking activation failures cannot establish a successful rollout. |
| `scripts/{dogfood-bootstrap,resync-dogfood}.sh:57/65,36`; `P/hooks/setup.py:186,400` | Migrate or explicitly retain each activation route; distinguish verification-only branches. |
| Native plugin install/update/uninstall and internal native update trigger | External mutation authority: independently reconcile artifact identity, registration and conflicts; no source-interlock coverage claim. |

Smallest consolidation candidate: reuse `P/scripts/deploy_state.py` as source-owned
delivery admission rather than add a guard service. Its current `gate` is source
provenance only, with no active-run check; `deploy-all.sh:913–930` warns/proceeds
on a broken gate. This is not current interlock evidence. Delegate identity/lock
semantics to existing pipeline owners only after their qualification; route all
retained writers through the selected transaction or retire them after equivalent
consumer proof. Bind source revisions and recheck these line anchors at execution.

Add to existing D0 rows, not another runner: active-run refusal with byte-identical
installed/settings state including library retention; idle permit; stale/ambiguous/broken detector non-pass;
concurrent start/update exclusion; deferred retry exactly once; external-native
reconciliation. D0 remains after authorized F0/R0 prerequisites; this authorizes
no #1807 global rollout and freezes no consumer denominator.

## D0 identity dependency (2026-09-25)

The supported native directory-marketplace fixture executed a separate frozen
artifact outside the development checkout with matching runtime/file manifests.
Evidence: private `d0-native-path-artifact.QuLK4I/RESULT.md`, SHA-256
`ed714c361013336180ef769d49d919edf5f717f1c5359823b52e019449d60a2e`;
the supervisor verified its complete evidence manifest. This is a fixture baseline,
not product qualification or source-injection/mutation refusal proof.

Read-only owner mapping found those missing refusal checks depend on the planned
R0 canonical verifier, which is not yet implemented. The existing F0 trustcheck
is bootstrap-only, not a product API; do not promote it implicitly or extend the
unwired retrofit verifier into a competing owner. Reuse existing negative-test
patterns for changed bytes, missing files, stale receipts and source fallback in
the single lifecycle runner after R0. Native registration/lifecycle remains with
Claude; settings preservation remains with its existing scoped merge owner.

## Bounded lifecycle-library disposition

The existing reachability ratchet's three library checks passed on 2026-09-25;
its live and pinned UNKNOWN set remains 97. Sixteen lifecycle/verification members
were inspected further, without equating an ungrounded caller with dead code:

| Proposed treatment | Audited members (under `P/lib/`) |
|---|---|
| Preserve required roles/history; ground actual callers | `install_audit`, `batch_agent_verifier`, `completion_verifier` |
| Migrate unique lifecycle outcomes before retiring competing owners | `copy_system`, `install_orchestrator`, `installation_analyzer`, `installation_validator`, `staging_manager`, `plugin_updater`, `update_plugin`, `validate_marketplace_version` |
| Reconcile into actual existing/planned acceptance consumer, not another verifier | `doc_verdict_validator`, `retrofit_verifier` |
| Retirement candidates only after consumer/dynamic-path disposition | `auto_install_deps`, `health_check`, `runtime_verification_classifier` |

Grounded internal AST edges exist beneath ungrounded entry candidates:
`genai_install_wrapper` imports staging/analyzer/copy/audit; install orchestrator
imports copy/validator; installation analyzer imports staging; update plugin imports
plugin updater; align-project-retrofit imports retrofit verifier. These edges do
not establish live entrypoints. None of the sixteen has a settings binding found
by the existing walker. At that point 81 UNKNOWN members still awaited inspection; all
97 retain their current machine verdict pending actual route/disposition proof.

A second bounded cohort inspected 12 workflow/evidence libraries. The static walker
missed a real dynamic shell edge: `P/templates/settings.autonomous-dev.json:101`
declares `SessionStart-batch-recovery.sh`, whose lines 142–172 compute and execute
`batch_resume_helper.py`. Preserve that helper's secure recovery outcome and ground
this edge; an UNKNOWN classifier result is demonstrably not proof of no caller.

The remaining cohort members are `auto_implement_pipeline`, `batch_git_finalize`,
`batch_mode_detector`, `checkpoint`, `coordinator_log`, `orchestrator`,
`parallel_validation`, `session_resource_manager`, `session_state_manager`,
`status_tracker`, and `workflow_coordinator`. Current command-driven batching,
completion-state and specialist validation routes supply candidate replacement
owners, but consumer and opposite-arm proof is still required before retirement.
`session_resource_manager` has unique process/session-limit semantics requiring
explicit retention or retirement disposition. After both cohorts, 69 members have
not had this additional inspection; all 97 retain the machine UNKNOWN verdict.
A concurrent ratchet rerun passed its three assertions but its session-finish
guard detected activity/dispatch files changing; the overall run is not a clean
pass. No state was reverted and no further concurrent pytest was run.

### Further bounded cohorts (not retirement approval)

Seventeen alignment/test-routing members were inspected next. A second missed
executable root is present in `.github/workflows/ci.yml:253–267`: multiline
`python3 -c` imports and calls `test_routing.route_tests`. Retain this route and its
run-all-suites fallback; the walker UNKNOWN result does not invalidate that source
connection or prove that a CI run executed it.

| Members | Proposed disposition and outcome owner to prove |
|---|---|
| `test_routing` | Retain/ground the actual CI carrier and failure fallback |
| `alignment_gate`, `project_md_parser` | Consolidate only after current `alignment_classifier` classification/parsing and hook consumers preserve the required outcomes |
| `alignment_fixer` | Reconcile prose-only execution claims; preserve approved atomic intent updates before retirement |
| `acceptance_criteria_parser`, `step5_quality_gate`, `test_runner` | Map unique outcomes to current acceptance tracker, quality/coverage and direct runner consumers before removal |
| `complexity_assessor`, `scope_detector`, `feature_completion_detector` | Compare with actual issue-scope and prior-art command routes; do not retain duplicate decision owners merely for API compatibility |
| `success_criteria_validator`, `workflow_violation_logger`, `code_path_analyzer`, `blocking_signal_classifier` | Disposition archived callers, historical readers and role-contract-only behavior before retiring or grounding |
| `feature_dependency_analyzer`, `worker_consistency_validator` | Explicitly decide smart batch ordering and distributed-consistency outcomes; no connected replacement inferred |
| `tool_validator` | Migrate unique deny/whitelist/path cases to active tool-intent, hook, sandbox and MCP owners before retirement |

Another 18 members were inspected using the existing walker, AST and bounded
command/source inspection without production imports or pytest:

| Members | Finding and proposed disposition |
|---|---|
| `distributed_training_validator`, `hardware_calibrator`, `training_metrics` | Specialized training/calibration outcomes; ungrounded internal edges include `distributed_training_validator -> hardware_calibrator` and `realign_orchestrator -> hardware_calibrator`; no bounded caller for `training_metrics` was found. Establish consumer/mission disposition before removal; do not expand workflow assurance into a new training subsystem |
| `math_utils` | Fibonacci implementation; no active caller found in the inspected command/hook/script surfaces. Candidate removal needs consumer/API disposition, not inference from its test suite |
| `ideation_engine`, `ideation_report_generator`, five `ideators/*_ideator` members | Ungrounded mutually referring discovery/reporting family; preserve any distinct required finding category through current improvement/review owners before retirement |
| `implement_dispatcher/{cli,dispatcher,models,modes,validators}` | Internal package imports exist, but dispatcher lines 195–330 return textual instructions referring to old workflows, not actual dispatch. Current user-invoked `/implement` command owns the workflow contract; preserve CLI/mode validation, mutually exclusive batch sources, batch-id/path validation and batch-state handling before retirement |
| `search_utils`, `performance_profiler` | No grounded route found for cache/quality/timing APIs in the bounded surfaces. Reconcile research freshness and actual telemetry/report consumers; a comment in `hook_perf_report.py` is not an import or equivalence proof |

The documentation/improvement cohort adds 17 members:

| Members | Proposed disposition and concrete route distinction |
|---|---|
| `claude_md_updater` | Retain until legacy installer migration: `install.sh:2241–2307` constructs/calls it; preserve idempotent injection, backup and path safety |
| `daily_aggregate_manager` | Retain actual `drain-watchdog.yml:176–198` embedded caller and issue-context refusal behavior |
| `flaky_tests`, `retrospective_analyzer` | Retain actual embedded imports/calls in `implement.md:1381–1389` and `retrospective.md:50–125`; separately disposition unused mutation APIs |
| `eval_metrics` | Retain documented standalone statistical API, not an active control; changelog explicitly records no command integration |
| `drain_revert` | Ground manual `scripts/drain_regression_check.py` action separately from still-unproven automatic scheduling; state ownership alone is not rollback execution |
| `session_telemetry_reader`, `skill_loader` | Migrate required classification/redaction and dangling-skill validation to existing improvement/health owners before retiring legacy readers/loader; manual CLI is not native skill-injection proof |
| `cia_promotion_filter` | Presence in `/improve` file closure is not filter execution; select actual `macro_promotion` thresholds explicitly before removing the duplicate |
| `comprehensive_doc_validator`, `doc_master_auto_apply`, `doc_update_risk_classifier` | Reconcile validation/auto-fix and high-risk approval outcomes with current doc-master and congruence consumers; do not infer parity |
| `error_analyzer`, `failure_analyzer`, `qa_self_healer` | Disposition archived producers and the ungrounded healer/parser pair; preserve required dedupe/redaction/remediation through current owners |
| `github_issue_fetcher`, `realign_orchestrator` | Check external detail-fetch and distinct realign consumer use before retirement; internal source absence is insufficient |

The final 17-member cohort completes this bounded source review:

| Members | Proposed disposition and concrete route distinction |
|---|---|
| `selector_stall_detector` | Retain actual dynamic import/call in `drain-watchdog.yml:233–236`; separately decide packaging for a repo-workflow-only caller |
| `active_security_scanner` | Mandatory auditor instructions name `full_scan`, but actual execution is unobserved; retain required dependency/history/OWASP outcomes and prove use or migration |
| `agent_pool`, `pool_config`, `token_tracker` | Internal manual parallel-validation chain, not current native specialist dispatch; disposition unique priority/retry/cancellation/token-cap outcomes before retirement |
| `code_patcher`, `stuck_detector` | Ungrounded healer dependencies; preserve required backup/rollback and repeated-error refusal in actual remediation owners |
| `auto_inject_memory`, `memory_formatter`, `memory_relevance` | Archived injection carrier only; explicitly disposition automatic injection, budgets and ranking against supported memory owners before retirement |
| `context_budget_monitor` | No caller found; preserve required truncation/verbatim handoff behavior in current command before retiring duplicate code |
| `agent_feedback`, `memory_layer` | Explicitly disposition adaptive routing and legacy memory-store retention/PII outcomes; current improvement/native memory is not automatically equivalent |
| `brownfield_retrofit`, `headless_mode`, `mcp_profile_manager` | Map unique state recovery, noninteractive exit/output and MCP profile-validation outcomes into actual retrofit/adapter/setup owners before retirement |
| `ralph_loop_manager` | Archived producer only; migrate unique retry/checkpoint/rollback outcomes to current completion and batch owners before retirement |

All 97 machine-UNKNOWN members now have bounded additional source inspection.
This closes the uninspected-library cohort, not the release denominator: every
machine verdict remains unchanged, and consumer/manual/runtime proof, unique
outcome decisions and explicit per-control acceptance remain outstanding.

## Shipping routes requiring explicit disposition

| Route | Concrete finding / next evidence |
|---|---|
| Native package | No tracked `hooks/hooks.json`; native manifest `components.hooks` is not proof of registration; qualify supported pinned plugin protocol |
| Metadata versions | Native manifest 3.8.0; marketplace 3.40.0; legacy plugin/root manifest 3.50.0; config manifest/VERSION 3.51.0; select proven canonical owner |
| `P/scripts/sync_settings_hooks.py` | `_replace_hooks` replaces the whole hooks object; deny-list replacement also exists; prove preservation/conflict refusal before deployment |
| `P/hooks/setup.py` | Four legacy Write/Edit/PreCommit binding declarations outside JSON census |
| `P/lib/plugin_updater.py::_activate_hooks` | Five legacy UserPromptSubmit/SubagentStop/PrePush declarations; actual applicability unresolved |
| `P/lib/sync_dispatcher/modes.py` | Searches project or installed generator and writes settings.local output; missing generator returns; source-free route unproven |
| `P/hooks/unified_pre_tool.py` loader | Sibling lib, global lib and plugin lib roots compete; installed byte identity must be observed |
| Setup/uninstall/hook activator | Source-layout imports/fallbacks exist; clean source-free support unproven |
| `implement-fix.md` doc path | Missing doc-verdict retry can proceed with warning; `doc_verdict_validator.py` UNKNOWN to current route instrument; reconcile required refusal path |

Candidate transport dispositions below turn the source-entry routes into explicit
WA-L1/WA-L2 obligations; they are **not** retirement decisions or installed
behavior claims. A legacy route stays supported until its actual consumers have
either migrated with proof or been explicitly placed outside the release profile.

| Source entry and observed caller | Candidate disposition / acceptance owner | Remaining evidence |
|---|---|---|
| Native `.claude-plugin/plugin.json` plus marketplace metadata | Retain native delivery, migrate to one installed root/version owner; WA-L1, D0, #1755/#1758/#1759/#1521/#1522 | The declarations disagree on version and Python floor; prove the pinned native hook, library and settings route, not manifest presence. Preserve the user-modified manifest while reconciling. |
| Root `install.sh` documented bootstrap | Migrate its active global copy and hand-written plugin registration paths, then retire only after WA-L1/WA-L2 and #1636 consumer proof | It fetches `config/install_manifest.json` from master, copies commands/hooks/libraries and may merge global settings; identify affected installs and prove unrelated settings survive. |
| `/setup` and `/sync` commands → `lib/sync_dispatcher/` | Migrate GitHub/source-fallback and marketplace-copy modes to the selected installed resolver before retiring either route; WA-L2, #1757/#1521/#1522 | `/setup` can use a source copy and `/sync` a global dispatcher; prove exact caller, installed bytes and no source fallback in clean/populated profiles. |
| `scripts/deploy-all.sh` → `sync_settings_hooks.py`; `scripts/pull-plugin-update.sh` launchd path | Migrate each declared dogfood/remote/update consumer before removing copy deployment; WA-L2, #1757/#1521/#1522 | The settings helper replaces the whole hooks key. Check every affected local/remote registration, collision and preservation outcome; remote contents remain UNMEASURED. |
| `plugins/autonomous-dev/scripts/install.py` | Keep UNKNOWN/retire-candidate, not dead-code credit; WA-L2, #1757 | Bounded source scan found no non-test active caller. Check external/manual callers and unique install effects before deletion. |

## WA-L3 commit-control reconciliation (2026-09-25, not frozen)

The configured Git hook is a symlink into the primary checkout, while its scans
use the committing worktree's cwd. Primary/worktree hook bytes matched at review;
future worktree edits alone do not prove the configured hook changed. Its five
archived validator calls contradict PROJECT.md's archived-code rule. All five
silently skip when the validator file is missing; a present nonzero exit refuses
under `set -e`. These are source observations, not joined commit-path acceptance.
This is a **known current violation to remove before release**, not an approved
exception to PROJECT.md and not a reason to delete the validators without
preserving their distinct outcomes.

| Archived validator | Required value / disposition proposal | Evidence gap before retirement |
|---|---|---|
| `validate_commands.py` | Preserve refusal for missing/empty command implementation; reuse the active command-file validator that already extracts that section | Active validator delegates absence to the archived owner; no equivalent replacement yet |
| `validate_install_manifest.py` | Consolidate full source/manifest reconciliation with the live manifest validator and existing shipping-file checks | Live validator is currently narrower; choose explicit update versus check-only semantics before migration |
| `validate_settings_hooks.py` | Preserve referenced-hook source existence and manifest membership in the same canonical manifest owner | Current live validator alone does not establish both relationships |
| `validate_lib_imports.py` | Retire the ineffective algorithm, retaining required installed import-integrity outcomes through the existing import-smoke/installed-tree family | In a stable tree it filters imports to existing filenames before testing whether they are missing; deleted imports disappear from its input. Broader required coverage must be selected and proven, not asserted equivalent |
| `validate_hooks_documented.py` | Select one canonical hook registry and retain its required documentation coverage | Current validator targets `docs/HOOKS.md`; existing regression coverage targets `docs/HOOK-REGISTRY.md`, which is not automatically equivalent |

Pre-commit source lines 217–316 perform full working-tree scans, not staged-only
checks. Lines 237–241 may stage an existing manifest diff, not only the generator's
changes. Freeze snapshot semantics and preserve unrelated unstaged edits before
changing this path. Reuse existing outcome families rather than add five new
frameworks: ordinary permit, meaningful invalid-subject refusal and missing-owner
fault through the actual configured commit route; full manifest reconciliation
needs missing-source and orphan-entry arms. No validator was removed or relocated
by this review. Consumer installation does not qualify maintainer commit controls.
Installed-import integrity additionally needs deleted-dependency and counterfeit
source-fallback faults; disappearance from the validator's selected inputs is not
successful validation. These are prospective cases, not observed passes.

Prospective contract selection, not implemented or qualified: WA-L3 pre-commit
is check-only. Explicit manifest generation/update is a separate preparation
step before the committing tree and reference HEAD are frozen; the validator
must neither modify the manifest nor stage any changes. Consolidate source
membership, missing-source/orphan entries and referenced-hook existence under
the existing live manifest reconciliation owner, retaining command-implementation
and canonical hook-registry outcomes. Those checks consume the selected source
commit snapshot, not ambient working-tree bytes. Source-free installed import
proof instead consumes its independently identified installed consumer; neither
subject substitutes for the other. Cover alternate indexes, partial staging,
renames/deletions and later hook/index mutation: the actual commit route must
prove the checked tree/reference is the committed one or revalidate/refuse.
Preserve unrelated staged/unstaged edits byte-for-byte. This deliberately changes
current automatic generation/staging behavior; it is not delivered reconciliation
or authority to remove archived owners. Configured-route permit, meaningful
refusal, missing-owner faults, installed proof and canonical registry selection
remain open.

WA-L3 contract selection (2026-09-26; not implementation or proof):
`docs/HOOK-REGISTRY.md` is the single canonical hook inventory for selected
identity, declared trigger/status, controlling configuration and detailed-behavior
links. `docs/HOOKS.md` remains the behavior/architecture reference, not another
inventory; preserve its distinct consolidation/history information. This follows
their existing Purpose/See-also relationship, not an assertion that either stale
document currently matches installed behavior. Neither proves native activation.

Reuse WA-L3-01 for nonempty executable command implementation; WA-L3-02 for
source/manifest missing-source and orphan reconciliation; WA-L3-03 for referenced
hook source existence and manifest membership; WA-L3-04 for installed dependency
integrity without source fallback; WA-L3-05 for canonical registry coverage and
valid detailed-behavior links. WA-L3-01/02/03/05 inspect the selected commit tree
and reference HEAD, including validator/configuration/document bytes, rather than
ambient working-tree files. WA-L3-04 consumes its separately identified installed
subject. Applicable missing validators, registry, required docs or selected source,
and uninspectable subjects are non-pass; empty/inapplicable selections require an
explicit profile reason. Preserve ordinary configured-route permit, invalid-subject
refusal and missing-owner faults before archived-caller retirement. Later index or
hook mutation must revalidate or refuse; this selection alone does not prove the
eventual committed tree was checked. Generation remains preparation outside the
check-only route. All five outcomes remain UNMEASURED for the replacement.

WA-L3 evidence contract: governing intent is one canonical, current delivery and
documentation description without commit-time generation. For 01/02/03/05 the
subject/dependencies are the selected commit tree, reference HEAD, validator,
configuration and required source/document bytes; for 04 they are the separately
identified installed closure and its verification instrument. Authority is the
independently checked existing applicable validator; direct observation must
show its actual result and caller consumption on that subject, including opposite
and missing-owner arms. Any dependency change invalidates proof and requires
consumption-time revalidation/refusal, not an arbitrary time expiry. Missing or
uninspectable applicable input/result is non-pass. Snapshot and installed claims
remain separate; neither author prose nor a working-tree scan supplies acceptance.

## Consumer population and support claims

Declared current deploy targets are `autonomous-dev`, `realign`, `spektiv`,
`homeassistant`, `vllm-mlx` in both local and remote host slots; older transports
also name `anyclaude`, at each host user's `~/Dev/<repo>/.claude` destination.
Each host's global `.claude` tier is another configuration
source. Bounded local WA-O2/O3 inspections now cover all five checkouts and the
local global tier, as recorded above; this is not a full installed-control audit.
Remote slots, runtime firing/effective merge and replacement-release behavior
remain UNMEASURED, not absent or already migrated.

Remote access check on 2026-09-25: both declared endpoints
`andrewkaszubski@10.55.0.2` and `andrewkaszubski@100.103.205.63` timed out on
TCP/22 (exit 255) using BatchMode, ConnectTimeout=3 and StrictHostKeyChecking=yes.
Neither remote `pwd` completed. No host trust, remote settings or installation was
changed; actual remote home, installed bytes, registrations and extension carriers
remain unresolved. Retry the bounded census when a declared endpoint is reachable;
timeout establishes neither absence nor drift.
The fresh retry with ConnectTimeout=4 returned the same two TCP/22 timeouts.
Local `tailscale status --json` independently reports `BackendState=NeedsLogin`,
no local Tailscale IP and no current tailnet map; this explains why the Tailscale
route cannot be used now, but does not establish the remote host's state. Remote
consumer rows stay UNMEASURED; avoid repeated blind SSH attempts until local
Tailscale access or the LAN route has actually changed.

Required release profiles remain: isolated Linux Claude worker; standalone verifier;
dogfood; distinct clean and populated consumer; real Claude/Codex portability case.
Disposable IDs are selected as CLEAN-0 and POPULATED-3; their concrete fixture and
effective-profile digests remain to freeze.
Local command probes on 2026-09-25 returned Claude 2.1.236 and codex-cli 0.44.0
from `/opt/homebrew/bin`; version output is not compatibility qualification or a
decision to upgrade. Windows, WSL, other OS/harness profiles are not implied green;
OpenCode/Pi remain optional future candidates.
Runtime requirements also disagree: the native manifest declares Python >=3.11,
while `P/.claude-plugin/marketplace.json` and `P/plugin.json` advertise >=3.9;
PROJECT.md requires >=3.11. Select **Python 3.11+ as the release support floor**;
the two lower-floor declarations are stale delivery inputs, not permission to
qualify Python 3.9. D0 must correct or retire both exact declarations through its
approved settings/package path and re-prove on a pinned 3.11+ consumer before
release. The user-modified native manifest remains untouched here.

## Reconciliation and omitted-route controls before freeze

### Bounded source-connectivity correction contract (source implementation verified)

Current disposition: source commits `d6e76665`, `261fbd43` and `e615974f`
are already integrated in this checkout. The active ratchet owner has SHA-256
`d3bd3225d277da1a398b4e2385c22cea9bcc5b9b61bb1b009a8c168a0e55e89f`
and independently ran 283 tests with raw exit 0 on 2026-09-25. A line-level
readback found the seven live-route table, command-position/ordering,
escaped-dollar, invalid-default, arbitrary-prelude and omitted-carrier
negatives in that owner; the source Claude `/implement --fix` audit found no
new code delta and did not repeat already-shipped implementation. The
future-tense contract below is retained as the historical acceptance design,
not an unimplemented request. This establishes source connectivity only:
REACHED does not mean installed, fired or consumer-correct. The separately
recorded backtick over-credit remains a known source-instrument limit, and
native/installed denominator and F0 acceptance remain open.

WHY/SCOPE: seven inspected executable source routes are missed by the existing
ratchet. Correct that instrument before treating its output as the release
denominator; do not build a second scanner or claim runtime qualification.
Existing owner: `tests/unit/hooks/test_hook_reachability_ratchet.py`. Proposed
implementation scope is that file plus this census/checkpoint and changelog; no runtime module,
store, schema, general shell evaluator or additional root directory is needed.

| Existing source root/carrier | Target | Observed defect family |
|---|---|---|
| `P/templates/settings.autonomous-dev.json` → `P/hooks/SessionStart-batch-recovery.sh:142–172` | `batch_resume_helper` | Same-file computed helper path followed by interpreter invocation |
| `.github/workflows/ci.yml:253–267` | `test_routing` | Indented multiline Python carrier |
| `install.sh:2255–2268` | `claude_md_updater` | Exact root missing, and heredoc interpreter arguments unsupported |
| `.github/workflows/drain-watchdog.yml:175–206,233–236` | `daily_aggregate_manager`, `selector_stall_detector` | Indented multiline Python carriers |
| `P/commands/implement.md:1380–1442` | `flaky_tests` | Indented multiline Python carrier |
| `P/commands/retrospective.md:54–120` | `retrospective_analyzer` | Indented multiline Python carriers |

Minimal path: extend the existing carrier extraction using common-indent removal
only at the recovered Python boundary (preserving relative indentation), the
evidenced simple `python3 - "$VAR" "$VAR" <<'WORD'` heredoc argument class,
and exact `install.sh` root inclusion. Do not widen all shell/Python files into
entry roots or execute source to discover imports.

The helper rule is an ordered same-file recognizer, not shell evaluation: in
non-narrative program text or a fenced program block, a POSIX identifier must be
assigned before its supported Python interpreter invocation as script operand.
The assignment RHS permits at most one leading simple `$name`/`${name}` prefix
plus a literal path ending `/plugins/autonomous-dev/lib/<valid-stem>.py`; extract
only that terminal stem, never evaluate the prefix. No intervening reassignment.
Reject command/backtick/arithmetic/default/indirect expansion, extra variables,
dynamic suffixes, invocation-before-assignment, comments, echo/test/print/existence
checks without execution, and unresolved reassignment. Heredoc arguments likewise
reject metacharacters and substitutions outside the evidenced simple token class.

Reuse one parameterized case table through `library_reachability(use_cache=False)`:
each listed live source pair must become REACHED; assignment/import text without
its actual invocation stays UNKNOWN; omitted invocation/carrier/root makes that
same positive route UNKNOWN. Include invocation-before-assignment, intervening
reassignment and a same-shaped non-root negative, and preserve
existing parser anti-overcredit controls. Refusal output names source, carrier
family and target. Change UNKNOWN pins/ceilings only from observed post-fix output,
never predicted subtraction or a hand-maintained second inventory.
These checks establish source connectivity only. Installed/executing evidence and
the independent omitted-entry/observer controls below remain required.
Round 1 identified these three defect families; round 2 required the bounded
helper grammar and ordering mutants now specified above. Final independent
plan-critic review returned PROCEED on this bounded source-only contract.

Implementation-discovered clarification, independently reviewed: real double-quoted
`python -c` bodies include shell-escaped quotes (`ci.yml:265`, `implement.md:1441`),
and retrospective numeric defaults (`${MAX_SESSIONS:-20}`, `${MIN_THRESHOLD:-3}`).
Dedent alone cannot parse those bodies. Extend only the existing carrier boundary:
apply exact double-quote shell escaping, preserving escaped dollar distinctions;
if normalization of parameter expansion is needed, accept only the evidenced
unescaped `${POSIX_ID:-decimal}` form and substitute its decimal default. This
establishes the default-path source edge, never every possible environment or
runtime execution. Do not replace arbitrary expansions with `None` to manufacture
parseability; unresolved expansion remains unresolved. New heredoc argument
support is limited to the evidenced single-quoted delimiter with a literal body.
The same-file helper interpreter must occur in actual command position, optionally
after bounded simple POSIX environment assignments; `echo python3 "$helper"` is
not execution. Keep the real environment-prefixed command-substitution positive.
Through the same walker, require escaped-dollar, arbitrary-prelude, unsupported
expansion and echo negatives in addition to the existing ordering controls.
The development prototype accepted those false edges; it is not acceptance
evidence or a second maintained implementation.
Round 2 returned PROCEED for this bounded clarification; the live implementation
still requires independent verification against it at its normal terminal handoff.

The reviewed implementation snapshot `c997a09f83545ed5e914fdcca1a73dc6bd6fd680ad8e2d1575d3c82af9010d4b`
also failed the supervisor's four full-walker counterexamples (echoed interpreter,
escaped dollar, invalid default, arbitrary prelude), with its valid helper control
passing. Preserve this failed snapshot. Correct within the existing owner and
case table: compute the unchanged full live graph once per test subject, retain
per-carrier attribution and distinct mechanism-removal checks, and consolidate
repeated fixture bodies/prose. A broad blind-text mutant does not replace the
specific command-position, quoting, expansion, ordering and carrier faults.
Check assignment lifetime and literal-heredoc/terminator handling without adding
an evaluator. Attribute agent/supervisor inspection accurately, not as a human
read. No numeric line cap or additional parser owner is introduced.

### Consumer-profile selection (proposed, not frozen digests)

Recipe source: the retained private proposal is
`/Users/akaszubski/.codex/artifacts/d0-consumer-lifecycle-matrix.lTBaCz/D0-CONSUMER-LIFECYCLE-MATRIX.PROPOSED.md`,
sections 2–4 (profiles and D0-01…D0-08). Reuse those definitions rather than
creating another matrix. Its macOS `CLAUDE-D0-2.1.236` envelope and four-file
fixture restoration are exploratory evidence, not the Linux product profile or
a last-known-good product release. This section supersedes its stale observation
status; the private absolute path is a maintainer recovery pointer, not a consumer
dependency. Before implementation, materialize the selected portable recipe and
its concrete pins in the existing delivery owner.

Reuse the existing D0-01…D0-08 lifecycle rows and one parameterized runner. Keep
`CLEAN-0` and `POPULATED-3` as disposable fixture IDs, with separate standalone,
dogfood, isolated-Linux and Claude/Codex process-result profiles; OS/tool versions
belong in each digest-bound profile rather than implying cross-platform parity.
Clean/populated are distinct repositories and isolated homes, not two names for
dogfood. The populated baseline includes user/project/local/explicit settings,
unrelated permission/env/hook sentinels and an exact owned projection.
The fixture *contract* can be selected now from the retained matrix: separate
disposable Git roots and isolated HOME/CLAUDE_CONFIG_DIR/TMPDIR, `env -i` and
Python `-I`, no source fallback, clean/populated sentinels, zero-mutation
conflict refusal, D0-01…D0-08 fault families and keep-data uninstall default.
This selects cases, not a passing or frozen product profile. The Darwin
startup fixture can remain credential-free, but a real isolated PreToolUse
inference case needs its own auth boundary: [Anthropic's authentication docs](https://code.claude.com/docs/en/authentication)
state that a different `CLAUDE_CONFIG_DIR` reads a different macOS Keychain
entry. No credential-free reuse of the host Max login is documented. Do not
copy host credentials or pass a token through the case artifact to make the
isolated consumer look qualified; use a separate, private interactive login
for that exact profile when the serial native trial is ready. This is a
documentation-supported design constraint, not an empirical qualification of
Claude 2.1.236 or permission to relabel the earlier host-auth fixture.
The local Darwin
startup-only envelope currently has Claude 2.1.236 executable SHA-256
`6bc4ba992d2786cbf0237c4453ca53c1fdf0c3b3d83ffa0025c0d8190ed27848`
and Python 3.14.3 executable SHA-256
`cbf84109626aa1013bbe408fbb9590bd0f1c1548f038b2221c6b8b87de26ca43`;
these do not pin Linux, a product artifact or its dependency closure.
Darwin lifecycle fixtures cannot satisfy isolated-Linux product qualification:
Linux retains its own result and exact worker/tool/profile digest.

Before implementation freeze supported harness/profile, source baseline and
dependency closure, fixture recipe, last-known-good artifact/profile digest,
intended execution/security semantics, expected D0 lifecycle rows, settings-layer
expectations, zero-mutation conflict inventory, allowed changes, timeout and
legacy route dispositions. Preserve consumer data by default on uninstall;
automatic destructive data removal is not promised by this profile. Candidate
package/closure digests, verifier identity, exact native join keys and observed
interruption points freeze only when those subjects exist, before acceptance.
The observed credential-free `--init-only` SessionStart fixture is reusable;
do not restart authentication to repeat it. It does not establish product
exactly-once joins or replace a qualifying real workflow.
Profile correction from verified fixture commands: the retained precedence and
source-free path probes invoke `/usr/bin/python3 -I`, which is Python 3.9.6 on
the current Darwin arm64 host. PROJECT.md and the native plugin manifest require
Python 3.11+. Therefore these probes remain historical fixture evidence, not
the supported product or populated-consumer profile. The available
`/opt/homebrew/bin/python3` is 3.14.3; using it is a new candidate profile that
requires its own pinned executable/fixture identity and rerun, not a relabeling
of the 3.9.6 result. The retained v1 installed manifest is fixture-only, not
an accepted last-known-good product artifact. Isolated Linux qualification is
still separate and UNMEASURED.
A fresh, isolated Darwin Python 3.14.3 **startup-only** probe subsequently used
that interpreter with Claude Code 2.1.236 and a source-free local plugin fixture.
Strict validation and two credential-free `--init-only` runs exited 0; each run
recorded five distinct physical SessionStart hook processes from the five
settings sources. Input hashes remained unchanged. The retained private
`/Users/akaszubski/.codex/artifacts/d0-darwin-python314.n5cR45/RESULT.md`
has SHA-256 `dfb1d5ba7a98dff3a639d02f719144840c7ff254c34150ffe12cf7c369662449`.
This supports only that pinned local startup fixture, not installed-product,
PreToolUse, full settings composition, Linux, F0 or D0 acceptance.
Since the retained private proposal, disposable preflight observed scalar order
explicit > local > project > user, plugin-default env non-participation and five
physical layer-canary processes per session. These supersede its unobserved-field
claims only for that fixture, not installed-product composition or exactly-once.
Scalar precedence does not prove permission composition or hook ordering; retain
those as separate settings-behavior obligations rather than deriving them from
the scalar probe. Required/optional/valid-empty extension-carrier behavior must
also be explicit in each selected recipe.

Installed-cache follow-up is now independently qualified for fixture composition
only at private `d0-git-composition.jxsQ4O`: initial/repeat each observed five
physical layer hooks, scalar explicit; scalar-only omissions selected local,
project, user and unset without losing any hook. Identical user registration
was deduplicated natively, whereas actual plugin/settings overlap produced six
physical processes and the unchanged five-hook detector rejected it. All settings
were restored to exact baseline bytes/modes. Omission result SHA-256
`24ae0a988cbaedc990b024036fcc4b5ac0689b983862fe795e3b374fe30c751f`.
Use individual step records, not the preserved aggregate with environment aliasing.
The earlier omission manifest's preparation pin precedes the reviewed wording
correction; this discrepancy is explicit, not a wholly-matching manifest claim.
Reuse these unchanged observations; product joins, permission semantics,
plugin-default scalar, lifecycle, clean/populated and portability remain unfinished.
D0-01 retains source-unavailable plus counterfeit source module/executable faults;
D0-04 requires one physical process joined to one native event and result/decision,
with duplicate registration producing two physical rows and failure. D0-08 still
removes owned registration/executable routes as promised, explicitly dispositions
retained native cache, preserves unrelated settings/data and proves standalone
and subtraction; update/rollback/uninstall cases remain. Only an automatic
destructive remove-data mode is outside this profile.

Remote deployed-population inspection is a separate obligation, not another
disposable profile. An unreachable machine stays UNMEASURED; it neither replaces
clean/populated qualification nor disappears from the migration inventory.
R0 still requires the actual accepted F0 commit/digest authorization, and promotion
remains explicit. No profile proposal grants either authority.
Independent profile review returned PROCEED after checking these separations;
this approves the planning definition, not a future candidate or its receipts.

Prospective execution-root refinement (two independent critique rounds,
REVISE then PROCEED): reuse D0-01 with a separately delivered, consumer-owned
packaged marketplace/catalog release artifact as the selected executing root.
It must not be a renamed mutable development checkout. Native registry
`installPath` is metadata, not execution-origin evidence: the retained I1
cache-origin requirement failed and remains failed. This selection creates no
new runner, case family, state store or retrospective pass.
Freeze the artifact's provenance, complete executable/import/registration and
dependency closure, supported interpreter and protected mutation boundary.
Observe actual native root, handler/import paths and bytes against that artifact;
reject missing/changed/counterfeit roots and source/ambient-copy fallback.
Before/after digests alone cannot prevent mid-run substitution and do not qualify
that boundary. Update and rollback must prove the actual executing-root version
switch; uninstall must disposition executing catalog and registry cache separately
while preserving unrelated settings/data. Clean/populated profiles, physical
duplicate-process negative and all D0 lifecycle obligations remain unchanged.
A credential-free supported-interpreter startup probe may reuse the existing
disposable recipe to measure packaged-root feasibility only. R0, protected
boundary, complete product closure, real PreToolUse and separate platform/consumer
qualification remain required and unaccepted; no release authority is granted.

Packaged-root startup feasibility was subsequently observed with supported Python
3.14.3, but `-I` alone retained ambient editable-package paths (realign/vllm).
Preserve that contaminated candidate at `d0-packaged-startup.zCqXyx/RESULT.md`,
SHA-256 `6015c19f2cceee22b68eaaf8c38c8d537bef2f1fdedddc0f207f17d755cf7789`.
The separately frozen stdlib-only `-I -S` fixture passed native validate/add/install/
startup, observed one SessionStart process and only stdlib runtime paths, with
unchanged catalog bytes. Result: `d0-packaged-nosite.r7111O/RESULT.md`, SHA-256
`387d389d143fdb8f2ac069680955eade3158fff1a4c81fb9b2fce65cbdd9ea9e`.
These private artifact names are recovery pointers, not product dependencies.
This does not qualify full product imports/dependencies, counterfeit/source-
unavailable faults, protected mutation, physical duplicate compatibility,
PreToolUse or lifecycle/consumer acceptance. The old observer requires native
`CLAUDE_PLUGIN_ROOT`; do not fabricate it to force the consumer duplicate arm.
Select the actual runtime dependency closure, not an assumption that `-I` removes
site customization or that a stdlib canary proves the whole installed product.

### Remaining release reconciliation

1. Preserve all 23 JSON route shapes, nine legacy declarations, source refusers,
   CLI/Markdown/root-shell routes, archived invocations and consumer extension slots.
2. Reconcile each to an actual caller/profile or an explicit retirement disposition;
   map every selected control to exact acceptance cases and current owner.
3. Reproduced the real missed `_emit('deny', ...)` route read-only on 2026-09-25:
   the existing `_python_refusal_evidence` returned `[]` for the actual
   `validate_paid_dependency.py` source, while the same invocation recognized
   a literal `{"decision": "deny"}` positive control. The source's classifier-loss
   and prohibited-content branches call `_emit("deny", ...)`; its envelope binds
   `permissionDecision` to a variable and `_emit` is absent from the scanner's
   recognized emitter names. Keep this known source refuser in WA-O1; the existing
   scanner needs correction before its selected population can establish coverage.
   This demonstrates an enumeration omission, not observed native hook behavior.
4. The source-fixture omitted-row counterexample passed at `9fd2cbb9`; in an
   isolated installed consumer, still observe marker-deny and neighbor-permit,
   then remove only its census row and require acceptance to fail with unchanged
   settings and behavior. That native consumer mutant is NOT yet executed.
5. Name unresolved classification/deployment edges before freezing; neither an
   empty selection nor a scanner's selected-surface green closes the denominator.
6. Exercise the observer itself: dropped/truncated events, filtered surfaces,
   inaccessible actors and a healthy-looking scanner with an omitted route must
   make the affected claim non-pass or explicitly UNMEASURED.
7. Route one distinct real escape/false refusal and one observer omission through
   CIA/improvement; have the capability/adapter acceptance-table owner retain only
   a distinct regression case, and the existing deterministic verifier/consumer
   mark dependency-affected receipts non-current without mutating historical bytes,
   lower affected qualification and independently re-prove.

Methods: standard-library JSON path/set/binding traversal, Python AST dictionaries,
main guards and call closure, existing `library_reachability(..., use_cache=False)`
and `refusal_candidates()`, then shell/Markdown caller inspection. No product
deployment, native inference or paid API was run. Tests are pointers, not receipts.
`scripts/audit_inventory.py` was not used as evidence because its hardcoded primary
checkout and write behavior do not fit this read-only worktree census.

## Exact source populations retained for reconciliation

The active Git hook resolves through the common repository's configured hooksPath
to the primary checkout's `scripts/hooks/pre-commit`; its bytes equal the worktree
copy, SHA-256 `7a845ecd7ee95ed9c8ce284a7d1a4de14103bc2f20eeff2c1ea42e77b53f7d9b`.
It invokes archived `validate_commands.py`, `validate_install_manifest.py`,
`validate_settings_hooks.py`, `validate_lib_imports.py`, `validate_hooks_documented.py`.
Their files exist; branch reachability is wired, not evidence that every branch ran.

Top-level hook filenames (prefix `P/hooks/`), including utilities and unresolved routes:

```text
PreToolUseWrite-protect-sensitive.sh
SessionStart-batch-recovery.sh
UserPromptSubmit-orchestrator.sh
UserPromptSubmit-track-issues.sh
auto_fix_docs.py
auto_format.py
auto_test.py
cloud_drain_telemetry.py
conversation_archiver.py
enforce_file_organization.py
enforce_orchestrator.py
enforce_prunable_threshold.py
enforce_regression_test.py
enforce_tdd.py
enforce_tier_distribution.py
genai_prompts.py
genai_utils.py
plan_gate.py
plan_mode_exit_detector.py
post_compact_enricher.sh
pre_compact_batch_saver.sh
security_scan.py
session_activity_logger.py
setup.py
stop_quality_gate.py
task_completed_handler.py
unified_pre_tool.py
unified_prompt_validator.py
unified_session_tracker.py
validate_claude_md_size.py
validate_command_file_ops.py
validate_paid_dependency.py
validate_project_alignment.py
validate_session_quality.py
```

UNKNOWN libraries (prefix `P/lib/`); this is an instrument result, not a deletion list:

```text
acceptance_criteria_parser.py
active_security_scanner.py
agent_feedback.py
agent_pool.py
alignment_fixer.py
alignment_gate.py
auto_implement_pipeline.py
auto_inject_memory.py
auto_install_deps.py
batch_agent_verifier.py
batch_git_finalize.py
batch_mode_detector.py
batch_resume_helper.py
blocking_signal_classifier.py
brownfield_retrofit.py
checkpoint.py
cia_promotion_filter.py
claude_md_updater.py
code_patcher.py
code_path_analyzer.py
completion_verifier.py
complexity_assessor.py
comprehensive_doc_validator.py
context_budget_monitor.py
coordinator_log.py
copy_system.py
daily_aggregate_manager.py
distributed_training_validator.py
doc_master_auto_apply.py
doc_update_risk_classifier.py
doc_verdict_validator.py
drain_revert.py
error_analyzer.py
eval_metrics.py
failure_analyzer.py
feature_completion_detector.py
feature_dependency_analyzer.py
flaky_tests.py
github_issue_fetcher.py
hardware_calibrator.py
headless_mode.py
health_check.py
ideation_engine.py
ideation_report_generator.py
ideators/accessibility_ideator.py
ideators/performance_ideator.py
ideators/quality_ideator.py
ideators/security_ideator.py
ideators/tech_debt_ideator.py
implement_dispatcher/cli.py
implement_dispatcher/dispatcher.py
implement_dispatcher/models.py
implement_dispatcher/modes.py
implement_dispatcher/validators.py
install_audit.py
install_orchestrator.py
installation_analyzer.py
installation_validator.py
math_utils.py
mcp_profile_manager.py
memory_formatter.py
memory_layer.py
memory_relevance.py
orchestrator.py
parallel_validation.py
performance_profiler.py
plugin_updater.py
pool_config.py
project_md_parser.py
qa_self_healer.py
ralph_loop_manager.py
realign_orchestrator.py
retrofit_verifier.py
retrospective_analyzer.py
runtime_verification_classifier.py
scope_detector.py
search_utils.py
selector_stall_detector.py
session_resource_manager.py
session_state_manager.py
session_telemetry_reader.py
skill_loader.py
staging_manager.py
status_tracker.py
step5_quality_gate.py
stuck_detector.py
success_criteria_validator.py
test_routing.py
test_runner.py
token_tracker.py
tool_validator.py
training_metrics.py
update_plugin.py
validate_marketplace_version.py
worker_consistency_validator.py
workflow_coordinator.py
workflow_violation_logger.py
```

CLI main-guard roots (prefix `P/scripts/`):

```text
agent_tracker.py
align_project_retrofit.py
complexity_assessor.py
configure_global_settings.py
deploy_state.py
drain_regression_check.py
genai_install_wrapper.py
install.py
invoke_agent.py
migrate_hook_paths.py
migrate_mcp_to_repo.py
parallel_validation.py
persist_intent_answer.py
pipeline_controller.py
progress_display.py
proof_of_block.py
reset_global_hooks.py
session_tracker.py
strip_duplicate_hooks.py
sync_settings_hooks.py
uninstall_strip_repo_hooks.py
uninstall_unregister_plugin.py
```

Name-filtered local-call closure from `unified_pre_tool.main`:

```text
_check_agent_denial
_check_bash_code_file_pipeline_required
_check_bash_infra_writes
_check_bash_state_deletion
_check_batch_cia_completions
_check_batch_doc_master_completions
_check_deny_cache
_check_drain_pending_commit_gate
_check_pipeline_agent_completions
_check_plan_exit_mcp
_check_plan_exit_native
_check_rm_rf_unresolved_vars
_check_spec_test_deletion_scope
_check_worktree_path_boundary
_check_write_pipeline_required
_detect_architectural_decision_without_plan_critic
_detect_daily_aggregate_direct_filing
_detect_env_spoofing
_detect_gh_issue_create
_detect_gh_issue_marker_creation
_detect_git_bypass
_detect_invocation_context
_detect_realign_bypass
_detect_settings_json_write
_enforce_no_nested_claude_dir
_enforce_protected_infrastructure
check_plan_critic_revise_gate
validate_agent_authorization
validate_batch_permission
validate_mcp_security
validate_pipeline_ordering
validate_prompt_integrity
validate_sandbox_layer
```

Invocation-context and retained-denial/cache readers are helper candidates, not
additional independent controls. Do not equate files, functions, routes and cases.
WA-W1 also includes `_detect_git_bypass`, `P/lib/hard_floor.py` with
`P/config/hard_floor_hooks.json`, and `P/lib/hook_bypass.py`; WA-S2 includes
`P/lib/sandbox_enforcer.py`, `P/config/sandbox_policy.json` and the auto-approval
policy resolved by `P/lib/path_utils.py`. Preserve these policy inputs as dependencies.

The 10 syntactic-refuser subset is `PreToolUseWrite-protect-sensitive.sh`,
`enforce_file_organization.py`, `enforce_orchestrator.py`, `enforce_prunable_threshold.py`,
`enforce_regression_test.py`, `enforce_tdd.py`, `plan_gate.py`, `unified_pre_tool.py`,
`unified_prompt_validator.py` and `validate_claude_md_size.py`. The extra actual
paid-dependency refusal must be retained even though absent from that subset.

Existing proof-of-block IDs (not new runs): `protected-infrastructure-hard-floor`,
`mcp-write-classification`, `plan-exit-gate`, `write-pipeline-gate`,
`mcp-rename-symbol-is-a-write`, `mcp-side-effect-set`,
`unenumerated-mcp-writer-by-shape`, `plan-gate-requires-a-plan`.

## Exact declared registration shapes

Aliases: G = global config template; A/D/B/L/P/S = autonomous-dev/default/
granular-bash/local/permission-batching/strict-mode project templates; N = native
default-settings. ALL = G,A,D,B,P,S. W = `Write|Edit|MultiEdit|NotebookEdit|mcp__.*`;
E = `Write|Edit|MultiEdit|NotebookEdit`. These normalize owners, not command bytes.
Effective native event support and settings composition remain unverified.

| Event | Matcher | Owner | Surfaces | Existing case-family allocation | Proposed disposition / next observation |
|---|---|---|---|---|---|
| PostCompact | `*` | post_compact_enricher.sh | ALL | WA-W3-05 | Preserve useful context and bound recovery identity; no ledger-only authority |
| PostToolUse | ExitPlanMode | plan_mode_exit_detector.py | G,A | WA-W2-02/03 | Migrate current-plan critique authority; missing/revised marker cannot pass |
| PostToolUse | E | validate_claude_md_size.py | ALL | WA-O1b | Selected commit/pre-git refusal; post-write warning is separately advisory, not prevention |
| PostToolUse | `*` | session_activity_logger.py | ALL | Supporting WA-W3-02…04 / WA-O3-01…05 | Prospectively retain activity observation for selected declared CLEAN-0/POPULATED-3 surfaces pending adapter-equivalence/subtraction proof; no activation implied |
| PreCompact | `*` | pre_compact_batch_saver.sh | ALL | WA-W3-05 | Preserve handoff identity; stale/unsigned recovery cannot authorize progression |
| PreToolUse | `Task\|Agent` | session_activity_logger.py | G | Supporting WA-W3-02…04 dispatch observation | Retain distinct explicitly selected global-layer variant; dispatch observation is not joined success or default-profile activation |
| PreToolUse | W | PreToolUseWrite-protect-sensitive.sh | ALL | WA-S1-01…04 | Migrate to one decision owner after built-in/MCP/opposite/fault arms; then retire duplicate |
| PreToolUse | W | enforce_file_organization.py | G,A | WA-O1a | Preserve root-path outcome through actual caller, including Git-classifier failure |
| PreToolUse | W | enforce_tier_distribution.py | G | WA-O4-01 diagnostic | Select migration to existing `/improve` tier-health reporting only with explicit consumer cadence disposition; until then retain immediate warning, never invent refusal |
| PreToolUse | W | plan_gate.py | G,A | WA-W2-02/03 | Migrate current-plan owner; wrong envelope and absent required plan cannot pass |
| PreToolUse | W | validate_paid_dependency.py | ALL | WA-O1c | Preserve paid-content refusal; computed `_emit` source UNKNOWN is not observed refusal |
| PreToolUse | `*` | unified_pre_tool.py | ALL | WA-W1a…e; WA-W2…W5; WA-O3 | Existing concrete subcontrols own distinct obligations; no single case certifies dispatcher |
| Stop | `*` | session_activity_logger.py | G,B,P,S | Supporting WA-W3-04/05 session-end observation | Prospectively retain selected declared layers pending measured replacement; Stop never establishes terminal success |
| Stop | `*` | conversation_archiver.py | G,A | WA-O4-01 history/reporting diagnostic | Retain queryable history in explicitly archival-enabled variants; disabled, missing, unavailable or corrupt transcript is not successful archival |
| SubagentStop | `*` | unified_session_tracker.py | G,A | WA-E2; WA-W3-04/05 | Migrate joined actual result/current-run credit; wrong-child/unsigned-dispatch refuses credit |
| TaskCompleted | `*` | task_completed_handler.py | G,A | WA-E2; WA-W3-04/05 | Preserve joined completion authority, not legacy completion-record success |
| UserPromptSubmit | `*` | unified_prompt_validator.py | G,A | WA-W4-01 | Retain human routing; routing never grants later action authorization |
| SessionStart | `*` | SessionStart-batch-recovery.sh | A | WA-W3-05 | Preserve batch recovery identity and useful context; no reconstructed signed authority |
| PreToolUse | `Task\|Agent\|Bash` | session_activity_logger.py | A,D,B,P,S | Supporting WA-W3-02…04 dispatch/request observation | Retain each separately selected project surface and guarded Bash request diagnostics; request records never authorize completion |
| PostToolUse | `Write\|Edit` | auto_format.py | A,S | WA-L2b formatting outcome; D0-04 | Qualify modern Write/Edit effects and duplicate/missing-formatter faults; LEGACY-01/02 remain distinct declarations below |
| Stop | empty string | stop_quality_gate.py | A | WA-O4-01 diagnostic | Provisionally retain end-of-turn diagnostic; consolidate only after measured distinct-value/cost proof, with no commit authority |
| UserPromptSubmit | `*` | inline strict-mode echo | S | WA-O4-01 advisory presentation | Select redundant-guarantee retirement after strict functional/profile proof; optional presentation must describe actual selected profile, never certify enforcement |
| PreCommit | absent | auto_fix_docs.py | N | WA-L3-05 / WA-D1 preparation | Select deterministic repair in explicit preparation, never commit-time mutation/staging; qualify promised effects and caller/event before retirement |

These are allocations of the existing 23 declaration shapes, not new acceptance
IDs or evidence of activation. Each keeps its exact surface/matcher parameters;
applicable CLEAN-0/POPULATED-3 variants require separately frozen installed
profiles. Supporting logging/history rows do not receive frozen Linux F0 WA-E1
case credit: that case profile/order is unchanged. These prospective selections
do not establish effective CLEAN-0/POPULATED-3 activation. Native executing roots,
supported events, receipt joins and current
dependency identities remain UNMEASURED until directly established. Candidate
rows keep their explicit conditional selections; this table is not frozen.

The five supporting selections preserve observation/history duties, not authority.
Current source owners are `session_activity_logger.py::main` with
`path_utils.resolve_activity_log_dir`, and `conversation_archiver.py`'s transcript
copy/index path. Where a selected consumer claim requires evidence, independently
validate its actual native event, source identity, result/effect and required join;
unknown session IDs, wrong-child/run records, missing/disabled carriers or
duplicates cannot supply required credit. Historical archives are representations,
not native origin or signed authority. Disabled archival is an explicit profile
outcome; enabled failed archival cannot report success. Retire either adapter only
after applicable consumer obligations and useful history survive replacement;
no new logger or store is selected.

Four-duty selection is prospective, independently reviewed against current source,
not delivered behavior. Tier distribution currently warns and allows, including
an analyzer-error path; preserve healthy/imbalance reporting, distinguish unavailable
analysis, and keep ordinary writes permitted. Existing `TestLifecycleManager` and
`/improve` reporting may replace the write-time diagnostic only when that consumer
explicitly selects the changed cadence; timing is not equivalent by default.
The current Stop owner runs available tools and reports to stderr with exit zero;
retain genuine failure reporting and distinguish disabled/no-tools/unavailable
states. Its source comment about upstream Stop capability is not authority.
Strict echo supplies advisory activation claims, not action decisions: omitted
reminder must preserve every selected strict-profile permit/refuse outcome before
retirement. `auto_fix_docs` currently repairs and stages files; move necessary
repair effects to explicit preparation and qualify correct resulting docs, while
selected-tree validation remains check-only and preserves unrelated staged and
unstaged bytes. Missing/mismatching required validation stays non-pass. None of
these selections proves native activation, resolves unknown consumers or permits
deleting an owner before replacement and applicable consumer proof.

G uses `~/.claude/hooks`; project templates resolve project-root `.claude/hooks`;
N uses a relative path with `|| exit 1`. Python interpreters, environment prefixes
and timeout omissions differ. In particular unified-pre-tool declarations set
`SANDBOX_ENABLED=false MCP_AUTO_APPROVE=true` (reversed order globally); this is
source configuration, not proof about effective OS containment. Freeze full native
command/configuration bytes before any test rather than relying on this abstraction.

Legacy Python dictionary declarations (nine bindings; native validity unresolved):

| WA-L2b variant suffix | Declaring owner | Event / matcher | Script / count | Proposed disposition and required retained outcome |
|---|---|---|---|---|
| LEGACY-01 | `P/hooks/setup.py::setup_hooks` | PostToolUse / Write | auto_format.py / 1 | Migrate to the existing modern formatting route; prove correct formatting and one physical Write effect, with duplicate execution and missing supported formatter non-pass, before retiring the competing writer |
| LEGACY-02 | same | PostToolUse / Edit | auto_format.py / 1 | Preserve the distinct Edit physical-effect arm with the same formatting, duplicate and missing-formatter obligations |
| LEGACY-03 | same | PreCommit / `*` | auto_test.py / 1 | Migrate test/coverage requirements to the actual commit transition; passing applicable tests permit, failed tests refuse, and a missing runner cannot pass. Pipeline tests alone do not qualify raw Git behavior |
| LEGACY-04 | same | PreCommit / `*` | security_scan.py / 1 | Migrate security refusal to the configured commit/validation owner; preserve permit, invalid-subject refusal and missing-scanner non-pass |
| LEGACY-05 | `P/lib/plugin_updater.py::_activate_hooks` | UserPromptSubmit / bare list | display_project_context.py / 1 | Retire dangling registration only after dispositioning any required context-presentation outcome; matching plugin source was not found |
| LEGACY-06 | same | UserPromptSubmit / bare list | enforce_command_limit.py / 1 | Propose retiring the archived 15-command policy registration, subject to consumer/intent disposition; do not revive a dangling path merely for registration parity |
| LEGACY-07 | same | SubagentStop / bare list | log_agent_completion.py / 1 | Migrate to existing session/completion consumers with joined actual completion and child-result identity; dispatch-only, missing result and wrong child refuse credit, while failed/unresolved required specialist outcomes cannot authorize progression. Invocation is not specialist success |
| LEGACY-08 | same | SubagentStop / bare list | auto_update_project_progress.py / 1 | Select migration to the existing read-only status/report path, preserving evidence-bound progress presentation; retire automatic PROJECT percentage mutation only after supported-consumer promises and replacement outcomes are qualified. Completion logging is not equivalent |
| LEGACY-09 | same | PrePush / bare list | auto_test.py / 1 | Migrate test/coverage requirements to the actual push transition; passing applicable tests permit, failed tests refuse, and a missing runner cannot pass. Qualify separately from commit and pipeline success |

These suffixes identify variants of existing WA-L2b obligations, not new gates
or another runner. LEGACY-01…04 apply to the automatic setup writer;
LEGACY-05…09 to activation-on updater callers. CLEAN-0 and POPULATED-3 normal
arms remain legacy-free; explicit populated migration/conflict variants seed each
exact owned binding separately and preserve unrelated settings. Freeze participating
layer, declaration bytes and caller per candidate profile; native support and
precedence remain UNMEASURED. Legacy-containing active consumers retain separate
named rows until migrated or explicitly dispositioned; unknown remote/manual
populations are not represented by fixture coverage. Reuse D0-02/03/04/08 for
preservation, zero-mutation conflict refusal, physical execution and retirement.
No variant here certifies native validity, execution or deletion authority.

Independent read-only caller review: setup's `main → run → setup_hooks` automatic
mode writes `.claude/settings.local.json` using `existing.update(hooks_config)`,
replacing the entire hooks value; custom/slash-command modes skip that writer
(`setup.py:375–387`). Updater's `update → _activate_hooks → activate_hooks` route
defaults activation on, including noninteractive `update_plugin.main`;
`HookActivator` migrates existing settings before merging the new bare-string
defaults (`hook_activator.py:1089,1263`). Activation errors do not fail the update,
so update success cannot prove registration or execution. These caller obligations
belong to WA-L1/L2 and the corresponding workflow family, not a new installer.
All dispositions remain proposals, not deletion authority or observed native
activation; preserve unrelated settings and prove selected outcomes before removal.

Progress disposition is prospective and unqualified. Closed historical
[#40](https://github.com/akaszubski/autonomous-dev/issues/40) promised automatic
PROJECT percentage writes; identify supported consumers relying on that promise
and explicitly authorize/migrate it before retirement, rather than silently
substitute a display. Current `commands/status.md` still names a missing active
`project-progress-tracker` specialist, so it is not a working replacement.
Reuse existing status/report and completion/evidence owners, not another agent or
store. Displayed progress must name its denominator, accepted-case evidence,
subject/version and limitations; failed/unmeasured outcomes grant no credit and
missing required status ownership cannot report success. No automatic mutation
of intent gate bytes follows from completion records. Explicit intent changes
remain a separate authorized path. This selection preserves progress value while
respecting PROJECT.md's gate-input purpose and one-topic/one-home rule; it grants
neither consumer acceptance nor deletion authority.

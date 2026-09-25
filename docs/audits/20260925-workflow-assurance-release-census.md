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
| WA-D1 docs/skills | `P/agents/doc-master.md`; existing doc-verdict/completion consumers; four priority skills | Changed behavior covered, false NO_DOC_IMPACT rejected, independent substantive review and effect checks; retain unique value | F0/M0, #1757/#1796 |
| WA-O1 additional refusers | `P/hooks/enforce_file_organization.py`, `validate_claude_md_size.py`, `validate_paid_dependency.py` | Each real allow/refuse/fault route; include paid dependency emitter despite scanner omission | M0, #1757/#1639 |
| WA-O2 unresolved source controls | `P/hooks/enforce_orchestrator.py`, `enforce_prunable_threshold.py`, `enforce_regression_test.py`, `enforce_tdd.py` | Resolve caller/consumer and retain/migrate/retire with outcome coverage; unknown is not silent exclusion | Census/M0, #1757 |
| WA-O3 dynamic extensions | `P/hooks/unified_pre_tool.py::_run_extensions` and selected consumer extensions | Discover effective extension population; deny/permit, disabled/missing carrier and omitted-census-entry refusal | Census/M0, #1757 |
| WA-O4 remaining source/legacy candidates | Other members of the 34-hook source corpus and 22 CLI roots; 97 UNKNOWN libraries | Reconcile callers and decision/evidence dependencies rather than classifying unused by filename; preserve each required outcome or justify retirement | Census/M0, #1757 |
| WA-L1 plugin lifecycle | Config/native/plugin manifests, `P/lib/settings_merger.py`, existing installers/updaters/resolvers | Source-free installed root, one version/registration owner; clean/populated install/update/repeat/interruption/rollback/uninstall preserves unrelated configuration | D0, #1755/#1758/#1759/#1521/#1522 |
| WA-L2 delivery routes | `install.sh`, `P/scripts/install.py`, deploy scripts, `P/lib/sync_dispatcher/`, setup/sync commands | Every affected active transport/consumer migrated or explicitly dispositioned; no source fallback or stale extra copy | D0/M0, #1757/#1521/#1522 |
| WA-L3 commit controls | Configured active `scripts/hooks/pre-commit` and its five archived-hook invocations | Prove applicable shell-branch behavior; each required outcome remains covered before relocating/retiring an archived owner | Census/M0, #1757 |
| WA-C1 retrofit | Dogfood, distinct clean and populated consumers | Independently verified installed workflow/lifecycle cases without source/ambient configuration; record unsupported profiles | Final, #1636 |
| WA-C2 portability | Required Claude/Codex process-result/evidence case, unchanged future core | Exact native profiles, real observed events and joined results; observation is not enforcement parity | After W0, #1757/#1636 |
| WA-M1 subtraction | All included families and necessary private helpers | Dependency-inclusive net code/test/owner/configuration/operator burden reduction with retained distinct fault coverage | Every migration/final, #1757 |

## WA-O2 bounded source disposition (2026-09-25)

Independent read-only review at `0decd8d3730982ab36cfdb42d7634076fac9ecd3`
found no production AST import, subprocess, dynamic execution or lifecycle
registration for the four named hooks. Tests and `scripts/capture_baseline.py`
execute them; the latter runs hooks with synthetic input, not lifecycle events.
All four sidecars are utility-labelled. Packaging a file is not activation.

| Owner | Proposed disposition, pending consumer proof |
|---|---|
| `enforce_orchestrator.py` | Retire legacy commit/session evidence heuristic after confirming consumer coverage by the connected alignment controls. |
| `enforce_prunable_threshold.py` | Migrate the required refusal outcome or explicitly retire it before removing the hook: the connected `TestLifecycleManager.check_prunable_threshold()` currently reports rather than blocks. |
| `enforce_regression_test.py` | Retire only after dispositioning fix-mode and raw-commit behavior; full-pipeline regression coverage does not establish those profiles. |
| `enforce_tdd.py` | Retire legacy heuristic after acceptance-first/TDD-mode coverage is established; if strict raw-commit TDD is required, migrate it to one existing transition. |

These are proposals, not deletion authorization or completed migration. Global
absence and actual runtime activation remain **UNMEASURED**; bounded local static
inspection follows. Inspect effective merged settings, remote and manual callers;
distinguish benchmark events from
joined lifecycle invocations; freeze each remaining permit/refuse obligation; then
prove owned stale-file/registration removal preserves unrelated settings. WA-O2
remains open until those checks and dispositions are complete.

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

Freeze four rows through existing owners: (1) populated enabled marker-deny plus
neighbor-permit with actual registered invocation observations; (2) the same files
disabled in the real process environment, with zero execution and an explicitly
inactive census; (3) required missing carrier yields qualification non-pass, while
declared valid-empty remains distinct; (4) unchanged files/behavior with one omitted
census entry yields independent denominator failure. No native row has passed yet.
Mutation between census/load and fail-open exceptions also remain unresolved.

The three additional local consumers above contain settings declaring repo-local
unified-pre-tool registration
but have **absent extension directories**, unlike the present-empty dogfood and
`realign` directories. Their static discovery also yields zero; do not classify
that as valid-empty until each profile explicitly permits an absent carrier.
No `HOOK_EXTENSIONS_ENABLED` setting was found in the inspected hook/env keys;
inherited process environment and effective native merge still require observation.

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

Required release profiles remain: isolated Linux Claude worker; standalone verifier;
dogfood; distinct clean and populated consumer; real Claude/Codex portability case.
Exact disposable consumer IDs and effective-profile digests remain to freeze.
Local command probes on 2026-09-25 returned Claude 2.1.236 and codex-cli 0.44.0
from `/opt/homebrew/bin`; version output is not compatibility qualification or a
decision to upgrade. Windows, WSL, other OS/harness profiles are not implied green;
OpenCode/Pi remain optional future candidates.
Runtime requirements also disagree: the native manifest declares Python >=3.11,
while marketplace/legacy plugin metadata declare >=3.9; PROJECT.md requires >=3.11.

## Reconciliation and omitted-route controls before freeze

1. Preserve all 23 JSON route shapes, nine legacy declarations, source refusers,
   CLI/Markdown/root-shell routes, archived invocations and consumer extension slots.
2. Reconcile each to an actual caller/profile or an explicit retirement disposition;
   map every selected control to exact acceptance cases and current owner.
3. Reproduce the real missed `_emit('deny', ...)` route in the census comparison.
4. In an isolated consumer fixture, observe an extension's marker-deny and neighbor-
   permit; remove only its census row and require census acceptance to fail even
   with unchanged settings. This mutant is specified, NOT yet executed.
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

| Event | Matcher | Owner | Surfaces |
|---|---|---|---|
| PostCompact | `*` | post_compact_enricher.sh | ALL |
| PostToolUse | ExitPlanMode | plan_mode_exit_detector.py | G,A |
| PostToolUse | E | validate_claude_md_size.py | ALL |
| PostToolUse | `*` | session_activity_logger.py | ALL |
| PreCompact | `*` | pre_compact_batch_saver.sh | ALL |
| PreToolUse | `Task\|Agent` | session_activity_logger.py | G |
| PreToolUse | W | PreToolUseWrite-protect-sensitive.sh | ALL |
| PreToolUse | W | enforce_file_organization.py | G,A |
| PreToolUse | W | enforce_tier_distribution.py | G |
| PreToolUse | W | plan_gate.py | G,A |
| PreToolUse | W | validate_paid_dependency.py | ALL |
| PreToolUse | `*` | unified_pre_tool.py | ALL |
| Stop | `*` | session_activity_logger.py | G,B,P,S |
| Stop | `*` | conversation_archiver.py | G,A |
| SubagentStop | `*` | unified_session_tracker.py | G,A |
| TaskCompleted | `*` | task_completed_handler.py | G,A |
| UserPromptSubmit | `*` | unified_prompt_validator.py | G,A |
| SessionStart | `*` | SessionStart-batch-recovery.sh | A |
| PreToolUse | `Task\|Agent\|Bash` | session_activity_logger.py | A,D,B,P,S |
| PostToolUse | `Write\|Edit` | auto_format.py | A,S |
| Stop | empty string | stop_quality_gate.py | A |
| UserPromptSubmit | `*` | inline strict-mode echo | S |
| PreCommit | absent | auto_fix_docs.py | N |

G uses `~/.claude/hooks`; project templates resolve project-root `.claude/hooks`;
N uses a relative path with `|| exit 1`. Python interpreters, environment prefixes
and timeout omissions differ. In particular unified-pre-tool declarations set
`SANDBOX_ENABLED=false MCP_AUTO_APPROVE=true` (reversed order globally); this is
source configuration, not proof about effective OS containment. Freeze full native
command/configuration bytes before any test rather than relying on this abstraction.

Legacy Python dictionary declarations (nine bindings; native validity unresolved):

| Declaring owner | Event / matcher | Script(s) / binding count |
|---|---|---|
| `P/hooks/setup.py` | PostToolUse / Write and Edit | auto_format.py / 2 |
| `P/hooks/setup.py` | PreCommit / `*` | auto_test.py, security_scan.py / 2 |
| `P/lib/plugin_updater.py::_activate_hooks` | UserPromptSubmit / bare script list | display_project_context.py, enforce_command_limit.py / 2 |
| same | SubagentStop / bare script list | log_agent_completion.py, auto_update_project_progress.py / 2 |
| same | PrePush / bare script list | auto_test.py / 1 |

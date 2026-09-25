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
source. None of these installed populations was inspected by this census; all
remain UNMEASURED, not absent or already migrated.

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

# Workflow assurance with subtraction — execution design

Updated: 2026-09-25. Program: [#1757](https://github.com/akaszubski/autonomous-dev/issues/1757).
Canonical plan: this file; its historical filename is retained for stable links.

## WHY + SCOPE

Deliver a small, local-first toolkit that makes AI-assisted development follow the
repository's agreed SDLC and produces independently checked evidence of the result.
Accuracy and consistency come first; minimum ongoing maintenance comes next.
Autonomous-dev is one consumer. A separate repository must work without the source
checkout, personal configuration or manual copying.

This is a policy execution and assurance toolkit. Claude Code remains the agent
harness; the OS/native sandbox supplies containment. We own only the missing policy,
integration and evidence checks. The product must become smaller as controls migrate.

### Authority and history

The adopted [v12 plan](20260909-control-tool-v12.md), SHA-256
`05a3efafecb2099ff8f9d1efdb9601577fdf071072e9b945690cbdbc252fab7d`,
the [sandbox amendment](20260913-f0-native-sandbox-amendment.md) and explicitly
approved case amendments remain the sources of frozen acceptance and security rules.
This redesign was requested by the user; it updates design and execution guidance.
It does not declare a successful run, promote a release, or silently replace a
frozen case. PROJECT.md invariants, specialist roles and eight-stage pipeline hold.

The 2026-09-25 goal explicitly authorizes reconciling intent with approved design.
PROJECT.md now states the already-approved boundary separation: native OS/permissions
provide containment, blocking hooks enforce workflow, and both require observed proof.
INV-2 through INV-8 and frozen v12/F0 inputs are unchanged. Optional hosted semantic
review remains a separately cost/privacy-authorized experiment, not a product or gate
dependency; shipping an adapter needs scope review. This is not native acceptance.

The complete prior plan, including every failure, review, receipt digest and
authorization checkpoint, is preserved at
[commit 6649685988a9f960784b55e3b031346e565183aa](https://github.com/akaszubski/autonomous-dev/blob/6649685988a9f960784b55e3b031346e565183aa/docs/plans/20260916-workflow-assurance-subtraction.PROPOSED.md),
file SHA-256 `4190185578688379f1ef024a5326e1ff8af2f3241fec1485fe3e6f83711d3062`.
Use its dated evidence for the subject it measured; old “next” instructions do not
override this execution map or later approvals. No private evidence is deleted.

The September 18 standing approval covers routine F0 corrections and independently
reviewed attempts addressing an evidenced changed cause. “Offline preparation”
means a candidate has not yet passed admission; it does not itself cancel that
standing approval or require repeating it. Before a native attempt: freeze the
new subject, independently review the changed cause and preflight, retain the
600-second native limit and capture/cleanup controls. No unchanged retry.
R0 still requires authorization identifying the eventual frozen F0 commit/digest;
a model cannot invent those future identities or record human adoption.

### Verified starting point and first unresolved step

Working branch: `fix/1779-pipeline-evidence-integrity`, checkout
`autonomous-dev-1779`; planning base `6649685988a9f960784b55e3b031346e565183aa`.
The earlier PROJECT.md date-only edit was superseded by the authorized intent update;
preserve unrelated dirty plugin manifest and .Codex contents.
The source intent file here is root PROJECT.md; .claude/PROJECT.md links to it.
Do not infer a second intent source from stale .Codex path prose.

F0 is incomplete. Ordinal11 completed capture but failed required examination:
three public Reads, fixture README Read and covers-first were absent.
The actual child rejected appended task/output instructions. The case added a
second output authority alongside the canonical doc-master report.
[Result and diagnosis](https://github.com/akaszubski/autonomous-dev/issues/1773#issuecomment-5824684585)
remain NONPASS; successful exit or record collection does not change that.
Role-prompt byte provenance and the complete qualifying workflow remain unproven.

The selected private construction baseline is 13 files / 11,218 physical lines,
including 8,211 implementation and 3,007 test lines, excluding imported collectors.
It is not a dependency-closed product size or a portable release.
The first action is to prepare the single-contract correction, reusing capture and
comparison code; do not restart sandbox construction or authentication by default.

## Existing Solutions

Reuse the frozen F0 oracle/comparator in `bootstrap/control_trust/`, existing
`proof_of_block.py`, `tool_intent.py`, pipeline completion-state owner, settings
merge implementation and existing integration/mutation ratchets.
Inspect their actual callers before selecting or retiring an owner.
Closed #1588 and #1779, CHANGELOG and existing plan commits supply prior failures
and fixes; a closed issue does not establish current installed behavior.

Rechecked primary guidance on 2026-09-25:
- [Anthropic agent evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents):
  evaluate outcomes and trajectories separately, use realistic tasks, mixed graders
  and repeated trials; rigid expected paths can reject valid solutions.
- [Claude plugin reference](https://code.claude.com/docs/en/plugins-reference):
  plugin assets have a native root; hook declarations can merge with the default
  hook file. Avoid duplicate registrations and verify the pinned executable.
  Current docs expose experimental plugin evals; treat these as a possible runner
  adapter only after local qualification, not a new dependency or reason to upgrade
  the frozen CLI. Plugin settings do not generally apply arbitrary settings keys.

Options considered: expanding existing per-module tests is initially easy but
preserves duplicate owners; a wholesale rewrite or new eval platform creates a
large unproven dependency; incremental replacement through installed workflows
has moderate migration cost and delivers useful controls with each removal.
Choose incremental replacement and reuse native facilities.

## Architecture — five responsibilities, four existing concepts

Keep v12's case, observation, decision and receipt. No new policy language, service,
database, agent orchestration framework or general dependency graph is required.

| Responsibility | What it owns | What makes it small |
|---|---|---|
| Consumer contract | Project requirements, relevant subjects, accepted behavior, runner/profile and cases | Versioned data using the four concepts; no executable policy DSL |
| Existing control implementation | One deterministic decision for each protected action or SDLC transition | Pure policy where useful; one active owner and existing hook consumer |
| Harness adapter | Native events/IDs, configuration, launch and control responses | Translate only observed native capabilities; keep harness details out of the kernel |
| Evidence kernel | Compare declared requirements with observed requests/results, effects, identities and exits | Standard-library Python; one comparison path and canonical JSON receipts |
| Delivery and assurance | Package the same code; exercise real installed workflows, recovery and faults | Native plugin lifecycle plus the existing independent bootstrap/CI route |

The normal route is:
`requirement → native action → existing control → observed decision/effect → receipt → next guarded transition`.
Offline replay checks evidence after a run. Preventing the next action requires an
actual production consumer of the receipt. At T0, trace and extend the existing
`pipeline_completion_state.py` / hook completion route; a module name or successful
receipt writer is insufficient. No second completion ledger or parallel gate.

### Evidence and trust

- Bind project/run, requirement/case revision, source/installed/executing subject,
  adapter/configuration version and dependency digests to each applicable receipt.
- Preserve native tool/actor/hook identifiers. Normalize with the original values
  retained; a local run ID cannot replace a missing native correlation edge.
- Join tool request/result, hook ingress/decision/result and required telemetry by
  actual keys; missing, duplicate, conflicting, truncated or stale evidence is
  non-pass for the claim requiring it. Time proximity never establishes identity,
  causality or a join. A time-sensitive case instead declares its observation
  interval and the governing requirement or dependency that justifies expiry or
  change invalidation, plus trusted clock source and relevant uncertainty; the
  production consumer rechecks validity before using its receipt. Never add an
  arbitrary age limit where dependency invalidation is sufficient.
  Immutable historical evidence remains evidence of that historical subject/run,
  but cannot authorize a current transition after its declared validity is lost.
- An observed complete Read proves returned input exposure, not comprehension.
  Pair examination evidence with independently checked behavior/document effects.
  General semantic correctness cannot be certified solely by a recorded read or
  deterministic count. Open-ended unresolved requirements need explicit disposition.
- Immutable hashes bind bytes; they do not prove an untrusted producer told the
  truth. Keep capture/oracle and promotion authority outside the tested actor's
  writable scope; retain declared provider/OS trust assumptions and test tampering.
- Keep sensitive raw material in private bounded capture. Export minimized receipts
  and safe samples. Record dropped/truncated evidence and retention/cleanup outcome.
  Use existing signing/persistence ownership for gating state (INV-7); no second
  identity service, secret store or custom credential broker.
- Required observability has an executable preflight and missing-carrier test.
  A disabled exporter or disconnected hook must be detected through the actual
  route. A changed flag alone is not proof of restored observability.
- Every frozen acceptance-row claim declares which observation types may support
  it and their limits.
  Requirements/policy establish intent; source/settings establish declared
  configuration; inventory establishes selected membership; native events and
  effects establish only the behavior they can directly observe. A digest proves
  byte identity, not execution; provider metadata proves a provider assertion, not
  the served model. Unavailable required evidence narrows the claim or makes it
  `UNMEASURED`; one evidence type never silently substitutes for another.
- Qualify the observer for the claim it supports. Freeze selected surfaces,
  filtering/truncation/drop behavior, inaccessible actors and producer-tampering
  assumptions, then exercise a blind-spot or false-green control. A healthy
  exporter, registered hook or green scanner is insufficient when its denominator
  can omit the relevant route.

### Configurability and portability

A consumer profile supplies roots, settings ownership, executable identities,
tool schemas, required capabilities, acceptance tasks and evidence location.
Requirements configure cases; harness quirks configure adapters. Adding a typical
consumer must not require editing the kernel or adding consumer-name conditionals.

First profile targeted for qualification: Claude Code in the existing isolated
Linux worker; it is not yet qualified. This does not require every consumer to use OrbStack or systemd.
Native containment stays in its platform profile and is measured separately.
macOS/Linux/Windows host tooling, native Windows execution, WSL and each harness
are distinct claims. Report the exact tested profile; never infer parity.

After W0, test the same frozen process-result/evidence case and unchanged kernel
through real Claude and Codex tool invocations; name the exact Codex version/profile
in the release table before the trial. The required capability is observation and
independent verification, not cross-harness enforcement parity.
Replay-only, real observation and enforcement capability must be reported separately.
OpenCode/Pi remain extension candidates; no simultaneous all-harness port.
If a required native event or refusal facility is absent, mark that profile
unsupported for that control and raise the gap before claiming portability.
A universal cross-harness enforcement claim is not a v1 completion criterion.
The named portability trial is required for completion. If it cannot qualify,
report the blocker; only an explicit user scope change can move it out of v1.

## Minimal Path — finite release and ordered execution

### 0. Freeze what “whole plan complete” includes

Before another implementation phase, put one release table on #1757 at the planning
base. Enumerate active controls from both source/policy entrypoints and shipped
registrations/consumer discovery. Include shell, markdown, CLI and dynamic routes.
Reconcile discrepancies explicitly; a classifier cannot define its own coverage.
Seed an omitted-route counterexample against the census.

The [2026-09-25 two-source census](../audits/20260925-workflow-assurance-release-census.md)
records exact source populations, shipping discrepancies and candidate acceptance
rows. Reconciliation and the omitted-route fault control remain required before
calling its denominator frozen; no UNKNOWN source or older consumer route is dropped.

Group the finite population into the following families. This is the release
denominator, not permission to discard an inconvenient active guard.

| Family | Included outcome | Existing owner |
|---|---|---|
| Evidence and examination | Required reads, real results, identities, current receipts, errors/cleanup | #1773, #1573, #1751 |
| Sensitive writes and protected infrastructure | Built-in/MCP tool intent, correct refusal and ordinary permit, preserved containment | #1673; existing hard-floor owners |
| SDLC progression | Actual required specialist execution and accepted evidence before guarded transitions, including ordinary runs | #1757; existing completion-state/gate owners |
| Code/document consistency | Changed behavior, known-impact docs, honest no-impact classification and skill guidance | #1757; existing doc-master/skill owners |
| Delivery and recovery | One active plugin/library resolver, settings preservation, update/rollback/uninstall, no duplicate execution | #1755/#1758/#1759, #1521/#1522 |
| Retrofit | Distinct installed consumer, source-free execution, bounded dependency and support profile | #1636 |
| Core portability | Same frozen process-result case and unchanged kernel through real Claude and Codex tool events, observation/verification capability | #1757 / #1636; exact profiles frozen with the release table |

Each enumerated control gets one disposition: migrate, retain as the sole proven
owner, or retire with preserved outcome coverage. Name exact paths, consumers,
acceptance IDs and owning issue before building its slice. Retained controls need
current evidence; “legacy” is not an exemption. New feature requests discovered
after the freeze go to a later release unless they block a listed acceptance case.
The final denominator is incomplete until this source/registration census is done;
do not claim whole-program percentages or a credible ETA before that checkpoint.

### Execution order

| Stage | Deliverable and exit evidence | Dependency / parallel work |
|---|---|---|
| F0 finish | Single-contract EX correction; remaining frozen native cases; independent source proof, dedicated CI and exact F0 freeze | Immediate critical path; independent case/packaging inventory may overlap |
| R0 | Small verifier agrees with frozen independent oracle, including false-success/omission mutants | Requires accepted F0 and the specified F0-based authorization |
| D0 | Native plugin plus standalone artifact uses one resolver; installed hook and verifier work; existing settings survive | Contract/package research parallel with F0; implementation after authorized prerequisites |
| K0/O0/W0 | First sensitive-write control uses canonical policy/evidence route in a clean consumer; old decision owner removed | Requires R0/D0; deliver useful behavior before expanding instrumentation |
| T0 | Existing transition consumer refuses missing/stale/wrong-run or failed receipts and accepts valid workflow | Requires W0; preserve mandatory specialist order |
| M0 | Migrate remaining frozen families and evaluate priority skills; retire redundant paths/tests with each activation | Independent families may use isolated worktrees after their shared contracts stabilize |
| Final retrofit | Dogfood plus distinct populated and clean installed consumer; lifecycle proof, re-proof, docs and subtraction report | All included families resolved; exact release/profile receipts current |

F0 native order remains the approved PR8 → EX1 → EX2 → RC2 → PR3–7/9 sequence,
reusing already qualified unchanged evidence. This plan does not invent new
attempts or substitute an OS actor's observation for a documentation actor's reads.

### Immediate EX correction

Reuse no-overlay binding SHA-256
`b8e06d79b240b95d55f16774506449d1985ec008b5eac74da846c8b9a95f58a2`.
Remove the competing semantic-output overlay; retain mandatory reads, covers-first,
frozen permissions, effects, canonical role verdict and all required native evidence.
Use existing required-read comparison for the public and fixture input union;
move fixture expectations into pinned case data. Reuse the finalized-capture owner.
The current literal commands/output hashes and role word floor remain frozen case
requirements; do not quietly treat them as generic product requirements or relax
them to obtain a pass. Any changed case receives an explicit old→new obligation
mapping and independent review before execution.

Retire the separate 522-line semantic verifier and 515-line test only after their
distinct obligations are preserved and the replacement rejects the real ordinal11
failure and seeded faults. Keep old bytes for historical replay, outside the active
product. Removing the overlay alone does not prove the child will comply.

This redesign explicitly withdraws the self-imposed ordinal12 admission gates
introduced at 66496859: the 110/40/180 Python-line caps, 90-JSON-line cap and
700-line minimum deletion. Their historical status as hard gates is preserved in
that commit; this is a prospective planning correction, not a claim they were
previously estimates. Existing adopted v12/rung budgets and approved exceptions still hold.
Report the complete dependency-closed size and actual net reduction; do not squeeze
readability, remove meaningful coverage or move complexity into data to hit a count.
If the replacement is larger or adds owners, re-scope before activation.

## Testing method — prove the workflow and the instrument

Use a small case bank of realistic tasks and past failures. First demonstrate a
real allowed route, prohibited route and broken-instrument route, then add cases
only for distinct uncovered failure classes. Keep boundary/parser/property unit
tests where they provide cheaper or more precise coverage.

For each case freeze public task, private expected outcome, required process
obligations, inputs/configuration and invalidation dependencies before the candidate.
Verify final filesystem/process effects and actual evidence. Required execution
ordering remains exact; incidental prose, word count and command spelling are
not new product gates. Permit valid alternative solutions in future cases where
the policy allows them. Historical exact cases are not retrospectively rescored.

Minimum retained fault coverage: missing required input; disconnected/duplicated
hook; wrong tool payload key; false agent PASS; wrong actor/run/subject; stale receipt;
disabled required telemetry; forged or altered evidence; empty/missed selection;
partial update; consumer-settings clobber; source fallback; always-NO_DOC_IMPACT.
Existing tests cover many of these: reuse their owners and fixtures.

For every frozen acceptance row, record the claim, required observation and its
authority, observation method, subject/run identity, temporal validity where
applicable, result, limitation and decision. These are fields of the existing
case/observation/decision/receipt concepts, not a second epistemic-state machine.
Only the deterministic decision owns `PASS`, `FAIL`, `UNMEASURED` or `ERROR`;
explanatory prose does not add decision states.

Until the product can check itself, the supervisor runs the existing independent
oracle and frozen fault controls outside the candidate, examines actual tool/result
and hook joins, and checks effects and cleanup. Specialist review adds interpretation;
raw executable checks determine mechanical acceptance. Keep this temporary oversight
until the installed replacement demonstrates the same positive and failure cases.

Use held-out tasks to check transfer beyond the development examples. Measure
trial count, failures, false permits/refusals, retries, elapsed time and maintenance
cost. A single green run proves that case/profile only. Generated workloads help
exercise volume and faults; they do not replace a frozen real-use observation
window. Any replacement promotion profile requires the approved methodology and
its explicit evidence/volume rules before the trial.

Close the feedback loop through existing authorities. CIA/improvement routes the
finding; the capability/adapter acceptance-table owner retains a regression case
only when a real escape or false refusal represents a distinct failure class not
covered by an existing case. The existing deterministic verifier/consumer makes an
observer omission non-pass or `UNMEASURED`, marks each dependency-affected receipt
non-current for qualification, preserves its immutable bytes as historical evidence,
lowers the affected qualification and triggers scoped re-proof. Reuse an existing
fault case where possible. Demonstrate the loop once with a genuine retained failure
and once with an observer-omission/false-green fault. Do not create a second incident
ledger, confidence model or improvement pipeline.

For objective fixture behavior, use independently authored executable oracles and
effects. For open-ended quality, use rubric-based independent review and bounded
manual spot-checks; models may advise but cannot override hard failures or confer
product trust. Jev is optional research, with no role in the required gate or
critical path; benchmark it only under separately authorized cost/privacy terms.

### Optional Jev semantic-alignment pilot

At the user's request, evaluate whether Jev improves interpretation of PROJECT.md
intent, the plan and observed execution. Use one optional adapter at existing
planning/review checkpoints; no new always-on service or call per tool event.
This is an experimental review tool outside the required product release; no
shipping commitment or cost/privacy authorization follows from this plan.
Moving a proven adapter into the shipped toolkit requires explicit scope review.
Give it the exact versioned intent clauses, the scoped proposed diff/task and a
redacted evidence packet with supplied clause/observation IDs. Check three things:
does the change serve the stated intent; does observed behavior contradict an
applicable obligation; does the report claim more than its evidence supports?

Example: a plausible "documentation checked" report with no required read records
fails mechanically; Jev may additionally flag unsupported claims. A change that
passes mechanical tests but introduces duplicate configuration owners may receive
a semantic REVIEW against the minimalism/one-owner intent. These are distinct checks.

Request bounded classifications and supplied evidence IDs with probabilities;
validate output types and ID membership in code. Map findings to advisory CLEAR,
REVIEW or UNAVAILABLE. Probability is not proof or calibrated accuracy on our tasks.
Timeout/provider failure is UNAVAILABLE, never CLEAR. Relevant unresolved semantic
requirements still use the existing independent/local or human review route;
the product must remain operable without Jev under PROJECT.md INV-6/INV-8.

Before adoption, compare with the current reviewer on a frozen labelled set of
aligned, conflicting, ambiguous, missing-evidence and prompt-injection cases,
including held-out examples and retained failures. Independently establish labels;
larger-model agreement alone is not ground truth. Report false-clear/false-review
rates, abstentions, repeated-run consistency, calibration, latency, cost and operator
work saved. Freeze tolerances before the benchmark, and retain Jev only if its
measured benefit justifies the dependency. Removing it must leave all hard gates
and receipts unchanged. A model/provider change invalidates its evaluation.

Bind the provider/model version when available (otherwise record unpinned service),
request ID, intent/diff/evidence/question digests and result to the existing optional
review record. An unpinned provider remains experimental; continued calibration
cannot be assumed when provider changes cannot be identified.
Only approved redacted fields may leave the machine; no raw credential
or private transcript export. Stored API credentials do not authorize a paid run.
[TypeSafe's primary description](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
describes typed probabilistic decisions; schema validity does not establish semantic
correctness. No provider benchmark is credited as our measured performance.

Delete a test only after independently mapping its distinct requirements/failures
to retained checks, exercising relevant mutants and verifying real entrypoint
coverage. Failing tests require diagnosis. Moving tests to an archive is reported
separately and does not count as reduced maintenance if they still run or ship.

### Skills and prompts

Pilot testing-guide, architecture-patterns, documentation-guide, then affected
planning-workflow guidance. Measure current/candidate/without-skill behavior on the
same workflow cases and conflicts when combined. Verify actual discovery and input
delivery. Two candidate iterations trigger a disposition, not an endless tuning loop.
Retain distinct value, consolidate duplicate instructions and remove false promises
such as “100% reliable.” Preserve specialist responsibilities and mandatory SDLC.
Reuse the existing skill-evaluation entrypoint; reconcile prose-only evaluators
instead of adding another test platform or baseline store.

## Delivery, dependencies and update

Package libraries, rules, hooks and verification with the native plugin. Resolve
code only from its installed root; mutable state belongs in the existing declared
consumer location. Use one native hook registration source and one version owner.
A plugin bundle does not automatically supply Python, external tools, OS isolation
or every settings key: D0 must preflight those exact prerequisites.

Prefer standard-library Python and declared existing tools. If another dependency
is necessary, pin it in the artifact/profile and exercise a clean installation.
Offer an actionable missing-runtime/conflict result; do not auto-install packages
during a policy decision or silently fall back to the source checkout.

Use native plugin install/update where supported by the pinned harness. Reuse
existing settings merging only for the necessary owned consumer delta. Preserve
unrelated keys, hooks, permissions and comments where the format supports them;
detect incompatible precedence or duplicate execution before activation.
Never append the same hook twice or replace the consumer's settings wholesale.

Exercise new install, populated-repo retrofit, repeated update, interrupted update,
rollback and uninstall with the real installed entrypoint. Compare unrelated
settings and verify effective control behavior in each applicable arm.
Use v12 section 5 D0's isolated env/HOME/PATH/Python -I profile and injected-source
fault control; a clean cwd alone is insufficient isolation.
Retain the last-known-good artifact/profile until acceptance. Rollback restores
owned code/configuration only; it cannot undo arbitrary external actions or user data.
Retire external-installer/copied-code routes only when every affected active
consumer is migrated or explicitly outside the supported release with disposition.

## Files to Create/Modify

The original design-only revision left PROJECT.md untouched; the subsequent
user-authorized intent reconciliation updates PROJECT.md, this plan and the goal
pointer together. Protected infrastructure and frozen v12/F0 inputs stay untouched.

| Implementation stage / path | Action |
|---|---|
| F0: existing private capture/binding/comparison files under the recorded artifact set | Reuse/replace scoped EX logic; preserve historical subjects; dependency inventory precedes extraction |
| F0: `bootstrap/control_trust/`, `.github/workflows/control-runner-trust.yml` | Reuse frozen independent proof; changes require declared invalidation and renewed proof |
| R0: proposed `plugins/autonomous-dev/lib/control_runtime.py` | Single library/CLI comparison and receipt owner; choose only after confirming no equivalent active owner |
| R0: proposed `plugins/autonomous-dev/lib/control_adapter_claude.py` | Native event normalization only; source-free loading and explicit unsupported evidence |
| D0: `plugins/autonomous-dev/.claude-plugin/plugin.json`, native hook config, delivery manifest/resolver and `lib/settings_merger.py` | Reconcile one package/root and owned settings transaction; enumerate actual resolver callers first |
| W0: `hooks/PreToolUseWrite-protect-sensitive.sh`, `lib/tool_intent.py`, actual hook consumers | One policy owner; built-in/MCP permit/refuse/fault proof; retire superseded shell decisions |
| T0: `lib/pipeline_completion_state.py`, its actual `hooks/unified_pre_tool.py` consumer and `commands/implement.md` | Consume accepted receipts through existing state APIs; enforce next transition on real runs |
| Skills: the existing four pilot `skills/*/SKILL.md` files and skill-eval callers | Correct guidance from measured task outcomes and remove duplicate instructions |
| Existing family/integration tests and ratchets | Retain distinct fault coverage, consolidate overlap, no wholesale test rewrite |
| `docs/TESTING-STRATEGY.md`, `docs/ARCHITECTURE-OVERVIEW.md`, `docs/RUNBOOK.md`, `CHANGELOG.md` | Update activated behavior, required operational steps and support limits in the same slice |

Before each /implement, freeze exact files, acceptance cases, callers, removal
mapping and estimate on its existing family issue. Proposed paths are not a
blanket module-creation instruction. A >50% scope expansion requires re-scoping
within authority before building; it is not an automatic request for user input.

## Fast execution and durable progress

One coordinator owns the shared native worker and final integration. Use parallel
agents for independent contract review, consumer fixtures, package/dependency audit,
docs mapping and isolated family work. Never overlap native runs sharing credentials,
configuration, fixture state or evidence. Run the affected proof once after a change;
repeat broader proof only for changed dependencies, new failures or final release.

Keep one current status block on #1757 linking the exact plan commit, release
denominator, accepted receipts, current action, next missing evidence, blocker and
measured elapsed/remaining work. #1737 is navigation, #1773 owns F0, existing family
issues own execution; do not copy growing session narratives into every issue.
Old bodies must be marked historical or superseded by the current pointer while
preserving original text. No issue is closed merely because planning is updated.

Persist a restart checkpoint with current commit/dirty state, exact artifact
identities, last verified result, next command and owned worker/process state.
On resume, verify those facts and continue the incomplete step. A completed turn
does not create a background worker: use an explicitly active goal or requested
heartbeat for continued execution, and show its actual status.

Report kernel/adapter size, dependencies, decision owners, stores, registrations,
configuration facts, test burden and manual operator steps. Include private helpers
that remain necessary for operation; hiding them from the package is not subtraction.
Benchmark capture/export, deterministic verification and model time separately;
report repeated timings with environment/sample count rather than a single ratio.
Avoid extra model calls in the hard path. Maintain v12's measured local re-proof
budget and explicit kernel invalidation blast-radius review.

No reliable whole-plan ETA or credit forecast exists before the finite census and
one end-to-end slice timing. At that checkpoint report remaining slices, observed
critical-path throughput and uncertainty; update on milestones, not every tool call.
Use included Claude Max for /implement/native cases and the agreed Codex supervision
tiers; paid actions still require explicit cost authorization.

## Completion and the goal to execute

Completion is a release snapshot: every frozen included control has one active
owner, installed permit/refuse/fault evidence and current subject-bound receipts;
mandatory SDLC transitions consume them; the required consumer lifecycle and
retrofit profiles pass; retained legacy controls are proven or retired; documentation
and GitHub disposition match; runtime/test/ownership/operator burden is reduced.
Publish a support matrix and exact remaining unsupported profiles. A missing required
release outcome prevents COMPLETE; future optional features do not expand the goal.
Neither a total test count nor a small file count substitutes for these outcomes.

Recommended goal text, after this design is reviewed and the current plan commit
is identified:

> Execute the workflow-assurance plan end to end to deliver a smaller, maintainable
> autonomous-dev toolkit aligned with PROJECT.md. First freeze the finite release
> control and consumer inventory, then complete F0, qualify the minimal verifier,
> package plugin-native delivery, release the sensitive-write slice, connect
> evidence to existing SDLC gates, migrate the remaining included controls and
> prove clean and populated consumer installation/update/recovery. Preserve
> independent evidence, containment and failed-run history; remove superseded
> runtime, configuration and tests in each activation. Use parallel isolated work
> where dependencies permit, persist visible progress and continue through routine
> in-scope repairs without asking again. Raise only a concrete unresolved scope,
> trust-boundary, paid-cost or required release-authorization decision, with a
> prepared reviewable result. Completion requires the frozen release acceptance
> matrix and measured reduction in maintenance burden, not simply a green report.

No reinstall, relogin or plan reset is a planning prerequisite; execution preflight
determines any concrete environment requirement.
The assistant first reconciles scope/status/authority, completes the current EX
correction and proves F0. The known remaining human checkpoint is the v12-required
R0 authorization naming the actual accepted F0 commit/digest, prepared at that time.
Other explicit promotion boundaries remain unless the user adopts a specific
standing conditional authority covering them; do not interpret a generic goal as
permission to bypass failed evidence, spending controls or security requirements.

## Critique history

Earlier design reviews and their exact subjects remain in the pinned prior plan.
2026-09-25 round 1: independent plan critic identified test-trajectory overconstraint,
unclear finite completion, repeated authority wording, evidence/comprehension
confusion, unproven transition consumption and dependency/consumer-install gaps.
This revision addresses them through the case distinction, release census,
authority precedence, evidence limits, named production route and lifecycle proof.
Round 2 requested precise qualification wording, explicit withdrawal of the new
self-imposed caps, a required named portability trial, and D0 isolation reference.
Round 3 reviewed corrected candidate SHA-256
`9b929b699d1ab95e91fea59dd31c106863e33f05d7e19fabbf45b9b7f8bc59f7`:
PROCEED for design, 3.5/5, with the unpinned-provider calibration caveat recorded
above. The final edit records that review and caveat; it is not a native admission,
completed release census, F0 acceptance, R0 authorization or product certification.

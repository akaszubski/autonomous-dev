# Workflow assurance with subtraction — execution design

Updated: 2026-10-03. Program: [#1757](https://github.com/akaszubski/autonomous-dev/issues/1757).
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

### Verified starting point and current prerequisite

Working branch: `fix/1779-pipeline-evidence-integrity`, checkout
`autonomous-dev-1779`; planning base `6649685988a9f960784b55e3b031346e565183aa`.
The earlier PROJECT.md date-only edit was superseded by the authorized intent update;
preserve unrelated dirty plugin manifest and .Codex contents.
The source intent file here is root PROJECT.md; .claude/PROJECT.md links to it.
Do not infer a second intent source from stale .Codex path prose.

Current execution pointer (2026-10-03): [#1807](https://github.com/akaszubski/autonomous-dev/issues/1807)
native run identity, origin and containment remain unaccepted. The
[#1806](https://github.com/akaszubski/autonomous-dev/issues/1806) overlapping-run
interlock and [#1809](https://github.com/akaszubski/autonomous-dev/issues/1809)
deployment/settings-preservation gate remain separate prerequisites at their
respective transitions. Resolve #1807 before another native F0 attempt; do not
convert a library-route green into native acceptance. The release denominator
on #1757 is still a candidate, not frozen. The independently reviewed inactive
#1818 runner/PCS/ordering seam was pushed at `09f982a5`; the inert observer
parser was integrated at `cee6032a`. Neither activates a qualified native
publisher or grants progression. The earlier always-false F4 verifier and
child-event forgery findings remain preserved diagnostic failures, not proof
that the later integrated seam is accepted. The historical reducer preserved
call-pass plus teardown-ERROR; native custody and actual command-path frozen
negative cases still prevent #1818 promotion
([review](https://github.com/akaszubski/autonomous-dev/issues/1818#issuecomment-5903691558),
[forgery RED](https://github.com/akaszubski/autonomous-dev/issues/1818#issuecomment-5914490492)). Use the
[restart checkpoint](../audits/20260925-workflow-assurance-checkpoint.md) and
current issue evidence for live order; the historical EX work below remains the
next native F0 task after the prerequisite. Its isolated offline preparation
may proceed in parallel; it is not native admission or acceptance.
For live source and run evidence, use the [current execution checkpoint](https://github.com/akaszubski/autonomous-dev/issues/1757#issuecomment-5961612391).
The earlier `cee6032a` MCP pair demonstrated an ordinary edit and a protected OS
refusal but lacked the failed-tool callback/activity edge. A fresh installed
`dac30d0a` pair independently verified that repaired edge using actual tool and
session identifiers, with unchanged public carriers and installed inputs
([bounded proof](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5964748457)).
Post/activity records still omit run attribution, so full provenance and
A9/F0 remain incomplete; this is not a hook-enforcement pass. Actual MCP
PreToolUse records skipped consumer workflow enforcement, and an isolated
loader counterarm showed ambient library shadowing; both remain distinct
[#1809 findings](https://github.com/akaszubski/autonomous-dev/issues/1809#issuecomment-5964798052)
until their own repairs and installed acceptance qualify. The populated-consumer duplicate native callback is a #1809 RED, and #1818's
focused teardown-ERROR reducer pass is not an F4 receipt; both are recorded in
the linked checkpoint. R0, D0, migrations and final retrofit remain ahead.

The superseded 2026-09-30 native failure detail remains in the
[base-branch plan at 57d0e1e4](https://github.com/akaszubski/autonomous-dev/blob/57d0e1e4/docs/plans/20260916-workflow-assurance-subtraction.PROPOSED.md);
it is historical evidence, not the current execution pointer.

The [draft #1807 PR](https://github.com/akaszubski/autonomous-dev/pull/1851)
now has a SHA-pinned native `git-subdir` install diagnostic, including typed
fix/full initialization, first foreground Agent joins and a denied same-run
Skill attempt that preserved typed origin. These are bounded diagnostics, not
the complete A7/A9 or F0 proof. A strict macOS sandbox allowed an ordinary
Bash write and refused an inert protected-file write; native hook creation of
the actual signed sentinel also worked under its `denyWrite` policy. The model
refused to issue Bash against that sentinel, so no OS refusal on the carrier
has been observed in this attempt. Keep N-BASH and A9 OPEN. The
[checkpoint](../audits/20260925-workflow-assurance-checkpoint.md) and
[#1807 evidence](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5913956132)
carry exact hashes and limitations. The older project-local copy procedure
below is historical; reuse the SHA-pinned native install method for further
diagnostics without calling that a released D0 carrier.

The 2026-10-03 #1818 bootstrap candidate is **REJECTED / NOT PROMOTABLE**
([independent review record](https://github.com/akaszubski/autonomous-dev/issues/1818#issuecomment-5961532412)).
Its focused tests passed, but the command never obtained the frozen N4B skip
observation, accepted a self-supplied manifest, and stored unauthenticated
independent-result dictionaries. Preserve its isolated worktree and tests as
failed evidence; do not install or count its reviewer permit. The existing
run-start ledger is explicitly model-writable until A9. A digest or HMAC that
the same actor can mint does not repair this origin gap.

Execution order therefore follows the real dependency: use the already
authorized scoped maintenance exception and independent external review to
finish #1807's native origin and carrier-containment proof; qualify #1818's
observer-to-protected-ledger-to-reviewer route only after that boundary passes.
The maintenance exception permits repair only; it supplies no A9 acceptance.
In parallel, freeze #1818's obligation manifest outside the tested actor and
exercise its capture/comparison cases as provisional diagnostics. No diagnostic
may grant native progression or release credit. Reuse the existing observer,
ledger and signer; additional stores or parallel receipt frameworks are not
the next step. Keep every frozen refusal, including actual command-path N4B,
model-written receipt, narrowed manifest, interrupted capture and bare marker.
The next A9 check reuses the stock sandbox venue and measures actual carrier
effects under the same policy as the trusted-hook positive, with exact current
subject bytes and independent before/after observations. Repeating an old
preflight or relying on a model declining the tool call does not close it.

### #1807/A9 coherent lifecycle repair (not yet accepted)

2026-10-03 execution correction: commit `3e2d7bf2` separates the native
invocation header from multiline intent. The byte-identical failed prompt then
created a strictly verified typed-user run in a fresh SHA-pinned native install.
The subsequent Bash attempt remains **NON-PASS**: it inspected the fixture rather
than executing the required effects, and `--tools Bash` did not suppress cloud
MCP capabilities. The owned process was terminated; all three carrier hashes
remained unchanged and no ordinary canary was created. Before another attempt,
verify the actual tool catalog and allow bounded nonsecret preparatory inspection
explicitly; CLI permission approval is not an exclusive command allowlist.

The scoped command-adoption cutover must preserve the existing full-mode
checkpoint used by resume/finalization. Move its initialization to the existing
native state owner rather than restoring model signing/key reads. This includes
the existing checkpoint helpers and failure/concurrent-start cases, not a new
store or lock framework. A lock descriptor printed by a short-lived process does
not protect the run lifetime; retain concurrency and resume as OPEN until actual
effects pass. The provisional command deletion earns no maintenance-reduction
or workflow acceptance before those consumers remain functional.

The user has authorized the narrow bootstrap repair, not a reduction of A9's
security or installed-workflow proof. Commit `7d639a1a` closes the tested
specialist-completion and settings-retry bypasses, but mode coverage and
multi-carrier run initialization are still incomplete. Keep PR #1851 draft;
do not deploy or call this candidate a pass. Preserve its RED/GREEN tests and
review.

First freeze a real Claude native trace from the isolated, byte-verified plugin
for one typed full and one typed fix invocation. Include each native command
expansion, model Skill and fabricated-stdin negative, actual Agent dispatch and
return, any phantom return, `PostToolUse` versus `SubagentStop` ordering, and the
owner/run/mode/issue/base/subject bindings. If the native post-tool payload
cannot distinguish and order a genuine return for overlapping same-type
agents, do not promote the current activity logger or invent an identity. Keep
the current synchronous coordinator write until a different native transition
is proved, and record A9 as OPEN. This trace is diagnostic, not F0 acceptance.
The first fix diagnostic at committed `e0c1e9e4` is a
[non-pass](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5902621235):
typed expansion and Agent dispatch occurred, but the installed plugin registered
no `PostToolUse` or `SubagentStop` callback, and the ledger had no progression or
completion despite CLI success. Resolve the single effective callback registration
owner and #1809 duplicate-template risk before repeating this trace; full-mode
and real completion are still unmeasured.
The next plugin-only diagnostic with those callbacks registered is also a
[non-pass](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5902740562): three
background Explore dispatches each emitted `PostToolUse:Agent` immediately
after `task_started`, before the corresponding `SubagentStop` and completed
task notification. Thus `PostToolUse:Agent` is **not** the completion owner for
this route. `SubagentStop` is a candidate completion signal, but three distinct
task IDs collapsed to one type-level `Explore` completion; its native task/agent
identity join and failure behavior still need proof. The run was interrupted,
so neither callback wiring nor a CLI exit certifies a completed workflow.
One bounded, metadata-only same-type probe then completed with two Explore
dispatches ([trace finding](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5902846156)).
The native event stream joined each `tool_use_id` to a distinct `task_id`, and
each `SubagentStop` identified its own task. The hook's `PostToolUse:Agent`
payload had the tool-use ID but no top-level task/agent ID. This establishes a
stream-level join, **not** a hook-local join or a safe completion writer. Check
for an existing stable carrier of that mapping before adding a new one; keep
A9 open and the same-type/phantom/failure negative arms unchanged.
A second security-reviewed, metadata-only diagnostic then found the missing
hook-local field: `PostToolUse:Agent` carries `tool_response.agentId`, matching
the `SubagentStop` `agent_id`, while `PostToolUse` and `PreToolUse` share the
same `tool_use_id`. In both same-type runs, `SubagentStop` preceded
`PostToolUse`. This is [schema evidence](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5902869319),
not a passed gate. The resulting two-event stop/result completion candidate
failed independent review and is superseded by the foreground design below.
A third completed foreground diagnostic found `tool_response.status=completed`
on each `PostToolUse:Agent` after its own stop, including overlapping same-type
calls. The narrower candidate is now to require explicit foreground execution
for **gate-sensitive** specialists and make that completed native result the
single completion writer; `SubagentStop` remains telemetry/sentinel lifecycle
only. Background or missing-status results never count. This avoids a two-event
stop/result join and its additional pending-stop state, but is not yet accepted:
remove both the old SubagentStop credit and coordinator `record_agent_completion`
writers at cutover, claim each launch atomically once by run/issue/tool-use ID,
and prove replay, wrong scope, failure, auto-background, same-type overlap
refusal, lost-state, next-dispatch and installed-consumer negatives. Do not disable
background execution globally or grant other modes credit by inference
([diagnostic and challenge](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5902992132)).
The first cutover may serialize only gate-sensitive native Agent dispatches:
the next launch refuses while any previous current-run dispatch lacks its exact
completed result, including a failed result. This trades pipeline-agent
parallelism for an observable one-shot barrier without adding a receipt service;
other sessions and non-pipeline work remain unaffected. Measure the cost in a
native run and keep parallel promotion OPEN until independently proven.

Then migrate one authority transition at a time. A dual-writer diagnostic may
compare old and new effects but cannot certify A9; it must not create two
independent decision owners. Cut over by removing the model writer and only
then run the final same-policy permit/refuse matrix. If a cutover fails, use a
reversible versioned rollback, not a security exception. Declare a finite mode
denominator from all documented `/implement` entry forms; every included mode
must pass or remain explicitly OPEN, never silently fall back to model-owned
authority. The current denominator is default
full (including auto-detected light/fix), explicit `--light`, `--tdd-first`,
`--fix`, `--batch`, `--issues`, and single/batch `--resume`; modifiers
`--acceptance-first`, `--full-tests`, `--no-worktree` and `--no-cache` inherit
the selected mode's proof or stay OPEN. The initial native trace samples full
and fix only; it confers no credit on the other modes. Validate repository
root, active-run exclusion, six
bindings, and recovery before writing. Carrier creation must be recoverable
and fail closed on each injected write failure and concurrent start; a partial
witness, ledger, secret or sentinel cannot authorize a run. For specialist
completion, do not use background `PostToolUse:Agent` as a completion signal.
First prove that `SubagentStop` supplies or can be joined to the exact dispatched
task ID, agent identity and run, including same-type overlap, phantom,
duplicate and failed-agent arms. It may own completion only after that proof;
the existing pre-dispatch guard must then observe its atomic commit or refuse
the next dispatch. Injected completion failure must refuse dispatch; callback
order alone is insufficient. If the native identity join cannot be established,
test a documented foreground-only workflow as an explicit compatibility and
performance trade-off, not a silent shortcut or global loss of consumer
background capability. Only then remove that model-side
write. Repeat for doc verdict, remediation, base changes and cleanup, or
retire the carrier if no longer needed. Reuse the existing state writer,
`session_activity_logger` event route and settings merger; do not add a store,
signer, hook registration or mixed logging/policy owner without evidence that
the smaller composition cannot work.

Freeze one installed-policy matrix before promotion: native hook positive;
genuine full/fix progression; model Bash and descendants, fabricated hook
stdin, replay and path aliases refused; built-in editors and MCP writers
refused for every authority carrier; an unrelated writable path permitted;
before/after hashes, receipts and cleanup independently checked. A proposed
`denyWrite` entry or model refusal is not a security result. Check clean and
populated consumers without source fallback, preserve existing settings,
detect duplicate plugin/template registration, and prove interrupted update
and rollback under #1809 separately. Record the before/after counts of files,
stores, registrations, decision owners, tests and manual steps; no net-new
framework to make an isolated test green. #1807, A9, F0 and release remain
OPEN until their distinct acceptance evidence exists.

The scoped #1806 lock-GC repair is included in the pushed
[#1806/#1807 library checkpoint](https://github.com/akaszubski/autonomous-dev/commit/8efcd57fba0e9471e1d5fae3bd91e2b5c2005f39)
and passed its frozen isolated regression and specialist review.
[#1806 remains open](https://github.com/akaszubski/autonomous-dev/issues/1806#issuecomment-5853957935):
the point-in-time held-lock proof immediately before F0 is still required.
Native A7/A9 origin and containment, installation and release are also unproven;
do not infer them from the integrated unit result.

Historical 2026-09-28 route (superseded for current diagnostics): the
installed command/hook mismatch makes a retry against
the current global profile noncertifying. For **native #1807 test evidence only**,
reuse the disposable project-local carrier **method** specified in the
superseded `docs/plans/20260906-repository-integrity-recovery.md` B0-C11,
not its old acceptance authority: first produce and byte-verify the
project-local installed `.claude/` carrier with the scoped managed deploy
vector, then copy its manifest-selected bytes into a disposable repo. Bind
source, staged and installed digests; isolate
`CLAUDE_CONFIG_DIR`, load only project settings, and independently verify the
single command and hook owner, source-fallback fault, exact bytes, native
state/receipt chain and before/after global-target identity. Freeze the
changed subject and retain the approved native attempt limits and review.
Do not use this result as #1809 rollout, D0 lifecycle or clean-consumer release
acceptance. Global installed-file mutation remains held until #1809 proves
full-run cross-target exclusion or retires that route after an active-use
census. Do not add a global marker, daemon or registry merely to obtain the
isolated #1807 test.

The 2026-09-28 isolated native diagnostic is recorded on
[#1807](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5870424628).
The test-only overlay moved the origin hook's signing-key home outside the
disposable subject; a real native hook wrote there, while a real Claude Bash
attempt to write the same home failed with `Operation not permitted` and left
no marker. This is evidence for the Bash boundary only. The native command
still needs effective default hook registration, authenticated config
isolation, other built-in-editor/MCP paths and end-to-end run/effect proof.
The initial Write prompt yielded only a model refusal, so the disposable
fixture explicitly authorized one harmless probe; the next real Write
tool call was denied by settings and the marker was independently absent
([#1807 editor arm](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5870458850)).
Do not promote this test overlay into the product installation.

The #1807 V3 helper, F1 alignment re-sign and shared malformed-input slices
are gated and committed as **library-route hardening only, not native
promotion**. The six-binding MAC, guarded base-commit
re-sign and guarded alignment re-sign passed independent positives and
negatives plus scoped `/implement` reviews. The first alignment repair had a
missing-MAC laundering bypass despite 34 focused greens; the preserved
[RED case](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5860793585)
led to a fail-closed correction and the
[gated library-route result](https://github.com/akaszubski/autonomous-dev/issues/1807#issuecomment-5861368092).
The shared `verify_state_hmac` malformed-input class fix completed its
separate `/implement --fix` run `23e0756ad22e1b22`; its scoped specialist
gates and independently rerun focused process-level tests passed. The
[checkpoint](../audits/20260925-workflow-assurance-checkpoint.md) records
the exact evidence and limits. None of these library results establishes
native A7/A9, installed behavior or F0.

The 2026-09-28 Stage 0 negation-parser attempt (#1831/#1832) is **rejected**, not
a new prerequisite implementation. Independent prose variants made it falsely
clear out-of-scope hosted-SaaS proposals despite selected green tests; adding
verb/connective lists expanded maintenance without closing the class. Retain
conservative Stage 0 escalation. Resolve the independently verifiable native
human-approval route (#1802/#1807) for legitimate escalations, then repeat the
original A7/A9 brief and same-installed-policy positive/deny proof. The
[#1562 active-pipeline Bash bypass](https://github.com/akaszubski/autonomous-dev/issues/1562)
also makes protected-file effect control an explicit A9 review input; #1833
was closed as a duplicate after the existing gate was inspected. Do not treat
shell-command parsing as a proven security boundary. See the restart checkpoint
for exact failed runs and preserved evidence.

F0 is incomplete. Ordinal11 completed capture but failed required examination:
three public Reads, fixture README Read and covers-first were absent.
The actual child rejected appended task/output instructions. The case added a
second output authority alongside the canonical doc-master report.
[Result and diagnosis](https://github.com/akaszubski/autonomous-dev/issues/1773#issuecomment-5824684585)
remain NONPASS; successful exit or record collection does not change that.
Role-prompt byte provenance and the complete qualifying workflow remain unproven.

Authority reconciliation (2026-09-25): adopted v12 sections 2 and F0, and the
sandbox amendment's Acceptance/Evidence sections, require installed role-source
identity, requested specialist type, native child identity, actual read/tool/hook
and effect joins, canonical verdict and the independent frozen oracle. They do
not require server-side prompt-application proof. The private ordinal12 v3 build
contract subsequently made unmeasured applied-role bytes an unconditional blocker;
that additional gate is withdrawn prospectively after independent authority review.
Preserve that build contract and its historical result unchanged. Exact effective
prompt bytes remain UNMEASURED; never claim client telemetry proves server receipt,
model comprehension or obedience. No raw-body capture service is required to close
F0. All adopted cases, source identity, carrier joins, tampering controls, independent
verification and promotion authorization still apply; this clarification is no pass.

The selected private construction baseline is 13 files / 11,218 physical lines,
including 8,211 implementation and 3,007 test lines, excluding imported collectors.
It is not a dependency-closed product size or a portable release.
Prepare the single-contract EX correction in parallel where isolated, reusing
capture and comparison code; do not restart sandbox construction or
authentication by default. Do not admit or run the next native F0 case until
#1807 and the applicable transition interlocks are accepted.

Preparation minimalism: maintain one canonical staged successor at the existing
import path. Preserve the frozen baseline and failed artifacts, and bind a complete
ordinary source diff to the exact before/after hashes before acceptance. A
preparation-only source generator, duplicate reader/undo machinery and generator-only
tests are temporary provenance, not shipped runtime dependencies or additional
release gates. Retire them from maintained active code before promotion once all
distinct behavioral, security, replay, duty and caller-compatibility detectors are
preserved. Use the existing secure staging/activation route: after retirement,
installed credential-free preflight and native activation must still assert the
canonical successor's absolute path and digest; missing-successor and source/old-
module fallback sabotage must refuse. Preserved baseline/generator/failed artifacts
stay outside the installed runtime/import search path (deliberately injected fault
fixtures are not a release profile). Count any retained dependency in maintenance
burden. This introduces no line-count gate, diff-replay requirement, new loader,
native admission waiver or change to F0/R0 authority.

## Existing Solutions

Design input: [supplied reference architecture](../references/20260925-autonomous-dev-reference-architecture.md),
preserved as a proposal, not competing acceptance authority.

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
- Current-run reconstruction refusal (#1807) requires an independently qualified
  transition boundary, not owner/MAC equality alone. Freeze an attempted replacement
  carrying all six correct bindings (native owner, run, mode, issue, base, subject)
  and a valid newly computed MAC through the actual signing/writing APIs, plus a
  ledger-only rebind; both must be refused at the actual guarded route.
  The inspected same-principal signing API does not currently establish this.
  Smallest candidate: compose the existing F0 native sandbox/file-tool permissions
  with existing sentinel/secret paths and native initialization/progression owners;
  do not introduce another store, signer service or parallel state manager.
  Before implementation acceptance, prove model-controlled writes/invocations are
  refused while genuine native-owned full/fix initialization and progression work,
  including fabricated hook input, replay, configuration/path aliases and descendants.
  Effective hook access and origin are UNMEASURED until directly exercised; proposed
  settings and a script that accepts fabricated JSON are not authentic native proof.
  If that composition cannot meet the unchanged requirement, leave it OPEN and
  resolve the boundary design; do not promote a MAC-only partial repair as complete.
  This clarification authorizes neither deployment nor an extra native F0 attempt
  and preserves the existing F0/R0 adoption and release gates. Missing/corrupt
  identity, unsigned/stale legacy authority and dispatch/completion refusal remain
  mandatory unchanged acceptance cases, not replaced by this clarification.
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

Before implementing a replacement control family or delivery phase, put one
release table on #1757 at the planning base. Enumerate active controls from
both source/policy entrypoints and shipped registrations/consumer discovery.
Include shell, markdown, CLI and dynamic routes.
Reconcile discrepancies explicitly; a classifier cannot define its own coverage.
Seed an omitted-route counterexample against the census.
Prerequisite repairs such as #1807 may proceed under their own frozen issue
acceptance scope while this census remains unfrozen; they neither freeze the
release table nor authorize a replacement-family promotion.

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

**Parallel-run admission correction (2026-09-28).** A fresh native
`/implement` or `/implement --fix` run for this release must start from a clean
checkout containing the reviewed #1807 fix-mode signed-identity substrate
(`27d1c497` or a separately reviewed integrated equivalent); merely naming an
issue in the prompt is insufficient. Before specialist dispatch, verify the
new sentinel's HMAC and current session owner, run ID, issue number, mode and
base commit, with wrong-owner and tampered-issue refusal controls. Refuse a
missing field, legacy/unsigned identity, `recovered=true`, or an `issue=0`
gate receipt. Preserve any code patch and test output from such a run as
**NONCERTIFYING source evidence**, but never reconstruct its missing identity,
reuse its specialist completions, or promote it as issue-bound acceptance.
Recheck the binding after the first specialist stop and before later gates.
This is an execution precondition, not acceptance of #1807's still-unmeasured
native A7/A9 outcomes or a relaxation of any case.

F0 native order remains the approved PR8 → EX1 → EX2 → RC2 → PR3–7/9 sequence,
reusing already qualified unchanged evidence. This plan does not invent new
attempts or substitute an OS actor's observation for a documentation actor's reads.

**Current gate dependency (2026-09-29; unresolved).** The exact #1846 issue
title/body escalates at deterministic Stage 0, while #1802 is clear. The
existing interactive escalation menu only permits updating PROJECT scope,
narrowing the change or cancelling; it has no verified human-approval permit.
The genuine #1802 fix-mode run reached F1 with an observed specialist result,
then stopped during F2's full-suite baseline before implementer. #1846 is
intended to make that long/inherited-red test gate coherent, but cannot itself
enter implementation through its current escalated issue workflow. Neither a
model paraphrase of #1846, a caller-signed approval, a shortened test scope,
nor a source-only F1 result resolves this cycle. Continue independent census
and boundary work, and obtain a separately reviewable, policy-compliant
bootstrap route before another native repair attempt; retain the unchanged
#1802/#1846 acceptance and failed-run evidence. Do not promote F0 or the gate
repair from a partial run. The release sequence resumes only after that route
and its independent opposite-arm proof exist.

### EX correction after current prerequisite

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

Retire the separate semantic verifier and its test only after their
distinct obligations are preserved and the replacement rejects the real ordinal11
failure and seeded faults. Keep old bytes for historical replay, outside the active
product. Removing the overlay alone does not prove the child will comply.
The earlier 522/515-line figures were a historical snapshot, not current size:
supervisor measurement on 2026-09-26 found 536/591 lines in the existing private
`verify_doc_semantics.py` / `test_verify_doc_semantics.py`. Its covers-first/result
ordering and fixture-read union, including README, remain live obligations;
preserve/migrate them before retirement and remeasure the dependency-closed total.

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

Implement those first three routes through one table-driven end-to-end runner,
not one script or suite per condition. Express missing, empty, duplicate,
conflicting, wrong-run, wrong-subject, invalidated-dependency, zero-selection and
disabled-carrier variants as case rows or mutants. The runner is a consumer of
the evidence kernel, not a second verifier or policy engine. A case expressible
with the existing case/observation/decision/receipt concepts adds a row without
new kernel or runner branches. Native field names stay in one named translation
function in the real caller. The runner drives the real installed profile and
checks the actual stage consumer—external comparator at R0 and guarded transition
at T0—so replay alone cannot satisfy end-to-end acceptance. F0's comparator remains
outside the product and never imports or calls the candidate kernel or runner.
Qualification adds a held-out row using the existing concepts after kernel and
runner bytes are frozen; that row must execute with both digests unchanged.

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

Choose the native implementation mode from the *observed starting state*, not
the issue title. The current `/implement --fix` command exits after F2 when
all selected tests pass and its implementer expects existing failing output.
A missing-control or missing-test case with a green baseline therefore uses
`/implement --tdd-first`: the test-master adds the frozen case, its focused
run must be RED before the implementation edit, and the full specialist gates
remain required. Reserve `--fix` for an already-observed failing case **that
the requested change is meant to repair**; unrelated inherited failures do
not turn a new capability into a test fix. The
[#1805 failed-attempt record](https://github.com/akaszubski/autonomous-dev/issues/1805#issuecomment-5874400425)
is the negative control: repeated green baseline runs and scratch probes did
not create a checked-in refusal test. Keep signed run/issue identity separate
from the single-issue specialist-completion bucket, which is `0` by the
existing command contract; do not turn either field into the other.

[#1818's native mode review](https://github.com/akaszubski/autonomous-dev/issues/1818#issuecomment-5874475425)
is the opposite negative control: two unrelated inherited-red tests let fix
mode proceed, but its F3 instructions then conflicted with adding a new pytest
capture instrument. Re-route that instrument through the proper feature mode
only after resolving the full pipeline's existing exit-zero prerequisite, or
retain its work as explicitly provisional; do not reinterpret those two red
tests as validation of the capture feature.

### #1818 maintenance bridge — separate suite attestation from independent proof

The current self-maintenance loop requires one bounded repair of the existing
test-process owner, result binding and actual next-agent consumer, not another
test framework. The previous one-time #1818 bootstrap was consumed; a further
protected-source exception requires fresh explicit authority, named files and
an independent review. Its proposed edit surface is the existing F2/F3 command
owners (`commands/implement.md`, `commands/implement-fix.md`), process owner
(`lib/test_runner.py`), F4 consumer (`lib/agent_ordering_gate.py` and only its
necessary existing state/hook caller), and directly affected tests/docs—not
policy, installer or a new signer/store. Freeze the failing case, base revision,
expected old→new obligation mapping and exact file allowlist before that
exception. The bounded bootstrap ends when the installed F2→F4 route preserves
pytest's raw exit and complete capture, N4 forged evidence plus bare-marker and
missing-raw-exit attempts still refuse the next specialist, and
independent review accounts for every changed owner; an unfinished slice stays
provisional. The bootstrap cannot mint F4, F0 or release credit, bypass a security gate, or
silently change the frozen [#1818 P1/P2 and N1–N9 matrix](https://github.com/akaszubski/autonomous-dev/issues/1818#issuecomment-5914465347).

Two claims must remain distinct. A parent-observed raw process exit, exact
selection/configuration and bound artifact can establish that a specified
pytest process ran. Its per-node reports are **attested under the recorded,
reviewed pytest configuration**, including `conftest.py` and loaded plugins;
pinning their bytes does not independently prove their truth. Required
security-critical outcomes are also exercised by separately authored frozen
acceptance/counterfactual cases through an independent acceptance runner,
against the same installed product behavior where applicable. The current F0
oracle records process exit and selection but **does not expose skip/pass per
node**; it cannot by itself decide the revised N4 outcome. That oracle's
`--noconftest` profile cannot be substituted for the ordinary suite or its
fixture semantics. Keep the forged skipped-test event as a refusal control:
F4 remains HOLD until either (a) a genuine independent observer rejects N4
and qualifies P1/P2 at the installed transition under the existing contract,
or (b) an explicit old→new mapping for N4 and P1/P2 changes the trust
assumption with separate approval and independent review. A hash or second
child plugin is not branch (a) or proof.

**2026-10-03 branch-(b) decision, pending independent review and revised-case
freeze.** The user authorized the smaller honest contract after the N4
counterexample; this decision does not itself pass F4 or authorize promotion.
Preserve the original [frozen matrix](https://github.com/akaszubski/autonomous-dev/issues/1818#issuecomment-5914465347)
as historical RED evidence, and publish the revised case rows on #1818 before
implementation. The old→new mapping is:

| Old claim | Revised claim and required refusal |
|---|---|
| P1: exact independently executed ordinary-suite denominator and full green | The parent proves the exact process, raw exit, complete capture and run/profile binding; required IDs are frozen outside the child and reconciled with its **configuration-bound** collected/executed report. F4 may permit *reviewer dispatch only* with an explicitly labelled suite-attestation receipt. It cannot qualify product behavior, release, or independently observed per-node execution. Empty/incomplete selection refuses. |
| P2: no new failures on an independently known same denominator | Compare the same nonempty, externally frozen required-ID set and reviewed effective test profile against the completed base; report *no new child-reported failures*, never independently verified global green. Independently authored changed-behavior, opposite and counterfactual cases must pass before downstream product acceptance; missing/failed external cases refuse. |
| N4: every forged child event/descriptor is independently detected | A child event, terminal line or descriptor can never solely authorize reviewer dispatch. Preserve the original skip→pass reproduction as historical RED. The revised frozen negative uses a SHA-256-bound tiny unconditional-skip subject, then a separate controlled `--noconftest` acceptance process with plugin autoload disabled, exact recorded argv/config and explicit per-node skip observation, raw exit and selected ID; a forged ordinary-child pass contradicts that observation and refuses F4 at the installed route. The present `oracle.sh` emits no skip/pass observation, so it cannot satisfy this row unchanged. Keep the observation in directly affected acceptance tests, not a second product signer or gate. Post-capture edits, cross-surface conflicts, unreviewed config changes or absent independent evidence for a required critical outcome also refuse. This revised case detects its frozen forgery and specified conflicts, not every possible consistent fabrication inside the reviewed pytest child; that remains an explicit limitation of ordinary-suite attestation. |

The acceptance IDs come from a pre-edit manifest authored by the independent
test-master/spec-validator, not pytest's child output. Bind that manifest to a
base test-file inventory and the changed-behavior map; deleted, renamed or
changed required tests and newly changed behavior without a reviewed test
mapping invalidate it. A child-selected denominator cannot silently narrow
the claim. This is a reviewed obligation map, not a claim that static analysis
discovers every possible test. The old N4 stays historical RED; the revised N4
must be frozen and run as a new case, never retroactively marked green.

N1–N3 and N5–N9 retain their frozen refusals; the actual installed coordinator
→ hook → ordering-gate → reviewer route must exercise them. `conftest.py` and
plugins are reviewed, digest-bound *inputs* for the ordinary suite, not trusted
observers; a changed or unresolved inventory invalidates the base. The
independent oracle owns only its separately frozen critical cases and cannot
certify ordinary fixture semantics. Keep process attestation, behavioral
verification and release acceptance as distinct claims; no model report or
suite-attestation receipt alone may promote a candidate. If a required case
cannot be expressed without assuming child self-attestation, keep F4 HOLD and
revisit the contract before editing code.

Implement the bridge as one vertical slice: capture the base once per exact
revision **and effective test profile** (argv, environment, configuration,
loaded plugins and selected subject), with raw exit and complete output;
invalidate that base if any binding changes. Freeze the required acceptance
IDs outside the pytest child and reconcile them with the captured selection;
ordinary-suite collected IDs remain configuration-bound attestation, not an
independently discovered denominator. Empty, incomplete or changed selection
refuses qualification. Observe argv and environment at the parent; treat
plugin/`conftest.py` inventory as configuration-bound attestation unless an
independent observer establishes the runtime load, and HOLD if the inventory
cannot be reconciled. Run bounded changed-behavior, opposite and
counterfactual cases during repair; compare the same qualified denominator
for new failures; then run the required broad and installed native proof at
promotion. Never pipe away pytest's exit, relabel focused green as full green,
or require a repeated full-suite run after every local edit. Exercise the real
Claude coordinator → hook → reviewer-dispatch transition on valid and invalid
receipts, not merely a reducer unit test or agent report. Keep a before/after
map of process owners, gate markers, tests, dependencies and operator steps;
retire duplicate owners only after their distinct outcomes are preserved.
Parallel inventory and delivery-contract work may proceed, but no migration
promotion borrows this bootstrap's result. Final release also needs distinct
clean and populated source-free installed-consumer proof and a measured
dependency-inclusive net reduction in code, tests, dependencies and operator
steps—not merely a before/after owner map.

For every frozen acceptance row, record the claim, required observation and its
authority, observation method, subject/run identity, temporal validity where
applicable, result, limitation and decision. These are fields of the existing
case/observation/decision/receipt concepts, not a second epistemic-state machine.
Only the deterministic decision owns `PASS`, `FAIL`, `UNMEASURED` or `ERROR`;
explanatory prose does not add decision states.

Keep execution status, supported claim scope and action authority as separate
fields in those existing records: exit zero is neither acceptance nor permission.
Agent reports may propose conclusions but cannot issue trusted gate receipts.
Treat a hook's logged refusal as intent until the same tool attempt is shown
to have been stopped; a subsequent successful effect contradicts enforcement.
The live `plan_gate.py` #1589 failure now belongs in the finite WA-W2 case set:
its invalid `permissionDecision=block` was followed by successful edits in a
native `--fix` run. Freeze both the unplanned-edit refusal and the legitimate
no-plan `--fix` permit before activating an enum-valid denial. Do not repair
the response value alone or count this source run as hook-enforcement proof;
reuse the existing case/observation/decision/receipt vocabulary.
Qualify each applicable observer with both a disabled control and an always-refuse
control, so refusing legitimate work cannot masquerade as safety. Where an opt-out
is supported, record enforcement as inactive and preserve the non-optional floor;
do not report the opt-out as successful enforcement. These are additional arms of
existing cases, not new agents, stores, status machines or proving frameworks.

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
Treat native `/plugin install` or reload outside a toolkit-owned lifecycle entrypoint
as an **external activation route**: a source settings-merger cannot interlock that
action. Qualify it only after an independent effective-layer reconciliation, and
do not claim pre-activation refusal for an external action unless the pinned
harness exposes a proven blocking lifecycle event. Inventory hook identity across
plugin `hooks/hooks.json` and all effective settings layers by event, matcher,
executable, resolved script and arguments; inspecting `command` alone misses
native `command: "python3"` entries whose script is in `args`.

Exercise new install, populated-repo retrofit, repeated update, interrupted update,
rollback and uninstall with the real installed entrypoint. Compare unrelated
settings and verify effective control behavior in each applicable arm.
Use one parameterized lifecycle runner for these outcomes. Before implementation,
freeze the clean/populated consumer identities, supported harness version,
last-known-good artifact/profile digests, baseline/source dependency closure,
intended consumer execution profiles and security semantics, all participating
settings layers and their effective precedence, the owned settings projection,
and the expected lifecycle cases. After implementation produces the candidate,
but before any acceptance run, freeze its artifact digest and complete
dependency/profile closure; those pins remain immutable through independent
proof and explicit promotion. Conflict refusal must prove zero mutation before
controlled activation; an already-active external conflict must refuse
qualification and preserve consumer settings, not be relabelled a prior refusal.
A valid exactly-once result requires one physical hook execution joined
to its event and decision; deduplicated receipts or one registration alone cannot
prove this. Include a cross-layer duplicate-registration mutant that the observer
detects, plus a populated-consumer permit retaining unrelated settings and hooks.
Enumerate the native lifecycle's observable interruption boundaries before fault
injection, with the expected prior-or-new complete activation and recovery action
for each boundary. Unknown or mixed activation fails. Freeze an exact Codex profile
before claiming cross-harness proof; a version probe is insufficient.
Standalone, dogfood, clean consumer and populated consumer retain separate results.
Replace overlapping installation tests only after mapping their distinct failures
to this runner; retain valuable primitive security and concurrency checks.
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
| R0: at most one small standard-library evidence module/CLI, exact path chosen during `/implement` | Reuse F0's public receipt contract but never import the frozen oracle; own only canonical receipt construction, binding/currentness verification and deterministic `PASS`/`FAIL`/`UNMEASURED`/`ERROR` reason output; delegate signing and atomic persistence to their existing owners, whose exact imported symbols the R0 acceptance table freezes before implementation—no policy DSL, service or store |
| R0: existing real Claude hook/runner | Perform the first slice's thin native-event translation in the actual caller; do not create a standalone Claude adapter until a second real harness demonstrates shared translation worth extracting |
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
The first product slice permits at most one kernel module and one shared table
runner. W0 removes the old shell decision owner and at least one superseded
integration path in the same activation. Before M0, T0 compares dependency-
inclusive code, tests, scripts, dependencies and operator steps with the pre-R0
baseline. T0 cannot exit until that comparison shows cumulative net reduction;
otherwise T0 remains incomplete and subtraction precedes further migration.
Neither stage may add a decision authority or persistent store;
relocation or archival does not count as subtraction. The release census supplies
rows to this capability and must not become another product scanner, receipt schema
or runtime framework.

## Fast execution and durable progress

One coordinator owns the shared native worker and final integration. Use parallel
agents for independent contract review, consumer fixtures, package/dependency audit,
docs mapping and isolated family work. Never overlap native runs sharing credentials,
configuration, fixture state or evidence. Run the affected proof once after a change;
repeat broader proof only for changed dependencies, new failures or final release.

Before a native `/implement` attempt, validate the **same checkout's**
`plugins/autonomous-dev/.claude-plugin/plugin.json` with the pinned Claude CLI
and observe that its command provider actually loads. A valid manifest in a
different checkout is not same-source provenance; a failed provider load is a
preflight refusal, not a pipeline attempt or a specialist result. The separate
`marketplace.json` directory-level schema/installation route belongs to D0 and
must be qualified there as well; do not confuse its validation result with
`plugin.json` validation or count session-only `--plugin-dir` loading as an
installed-consumer proof. The 2026-09-29 source manifest failure and distinct
marketplace failure are recorded on #1757.

**Pre-F0 carrier dependency correction (2026-09-30).** A disposable native
marketplace installed the reviewed #1807 plugin bytes and fired
`UserPromptExpansion`, but Claude loaded a local-directory marketplace from its
source path; making that directory unavailable changed the plugin to
`failed to load: cache-miss`. This is native registration evidence, not a
source-free installed-consumer or A7/A9 result. A second disposable catalog
with a SHA-pinned `git-subdir` source fetched PR #1851 commit `aa9fba0a` into
an isolated plugin cache; Claude's native init named that cache path and the
origin hook fired. A session-only settings overlay then reused the existing
Claude Max login without changing user settings: the native hook event's
session ID matched the signed fixture state, and an effective
`enabledPlugins=false` control loaded no plugin and fired no hook. This is the
carrier for the next #1807 diagnostic: retain source-to-cache byte digests,
disabled/missing-plugin controls, and native run/effect joins. These no-tool
arms prove neither model workflow nor A7/A9. If this
route later requires a product schema change, scope only the minimum #1755
carrier repair through existing implementation, independent review and
security gates. Preserve the nested marketplace self-maintenance detector and
unrelated consumer settings;
do not count this prerequisite as D0 lifecycle, F0 or release acceptance. Full
install/update/rollback/uninstall qualification remains in D0.

**Measured test-gate prerequisite (#1846, 2026-09-29).** A genuine #1805
`/implement --tdd-first` STEP 1 full-suite baseline timed out at its configured
900-second bound and wrote `__TIMEOUT__`; it supplied neither a green baseline
nor targeted RED evidence, so the run stopped before test-master/source edits.
The current command has no accepted bounded, digest-bound substitute for its
STEP 8 full-suite gate and its absolute-green wording conflicts with later
inherited-red fix-forward wording. Preserve UNKNOWN and failed-run evidence;
do not advance #1805 by treating routed or parsed tests as full-suite proof.
Resolve #1846 with an independently reviewed, coherent scope/result contract,
then re-freeze #1805/#1818 on the repaired base. This is a delivery dependency,
not permission to weaken final release or security coverage.
The first signed native #1846 fix run (`cc864247aa5cb076`, 2026-09-29) stopped
at F1 before implementation: conservative Stage 0 matched a negated gate-bypass
phrase in the full issue body. Stage 1 found the work in scope but cannot
override Stage 0. The current #1802 verdict writer refuses both a bare
`user_approved=True` and a caller-supplied approval record; an approval in chat
therefore cannot qualify this run or set `alignment_passed=true`. Preserve the
failed run and full issue input. Qualify #1802's independently observed,
current-run human-response route with forged/missing/replayed refusals before
retrying #1846's native F1, or use another genuinely in-scope native repair
subject whose complete unaltered input clears Stage 0. Neither route waives F1,
the specialist sequence or #1846's behavioral acceptance.
The uncapped base suite subsequently finished with 1,068 failures and 30
errors; #1848 separately owns contract-grounded disposition of that test
population. Neither a longer timeout nor a historical failure whitelist is
a substitute for a reviewed, meaningful release denominator.
Also resolve #1847's observed same-run premature spec-validator credit: a
case-freeze return was stamped complete before execution. Neither coordinator
prose nor SubagentStop alone may certify that stage; reuse #1818's bound
execution evidence and make all completion readers reject unbound old stamps.

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
> control and consumer inventory, then repair the self-maintenance test gate as
> the bounded #1818 vertical slice without weakening its frozen acceptance;
> distinguish configuration-bound suite attestation from independent behavioral
> proof. Complete F0, qualify the minimal verifier,
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
The assistant first reconciles scope/status/authority and may prepare EX
offline in parallel; it proves the #1807 native boundary and applicable
transition prerequisites before qualifying EX and F0. The known remaining
human checkpoint is the v12-required
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

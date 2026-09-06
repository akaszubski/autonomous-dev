# Control-tool capability ladder — build the instrument before wiring the system

**Status:** PROPOSED v2 — replaces the execution sequence, not the evidence, in [`20260906-repository-integrity-recovery.md`](20260906-repository-integrity-recovery.md)

**Date:** 2026-09-06

**Governing intent:** [`PROJECT.md`](../../PROJECT.md), especially INV-1, INV-5, INV-6, INV-7, INV-8, Q1, and Q2

**Product decision:** `autonomous-dev` is a local control-assurance tool with Claude Code integrations. It is not a Claude Code hook solution with supporting utilities.

**Execution rule:** build and prove one standalone capability, connect it to one real trigger in report-only mode, prove that carrier and rollback, activate it as the sole decision owner, remove the superseded owner, and only then start the next rung.

## WHY + SCOPE

The repository-integrity audit remains valuable: it found disconnected hooks, multiple authorities, stale claims, source/install skew, shallow tests, weak provenance, and controls that exist without evidence they operate. Its proposed Bootstrap B0 is nevertheless still solution-shaped. B0 asks one change program to introduce a proof capability, connect `/implement`, CI, deploy, and phase closeout, exercise a fresh Claude process, and replace old acceptance authority before any part has an independently stable contract.

That creates the failure pattern this repository is meant to prevent:

- the capability cannot mature independently of the first integration;
- a defect cannot be localized to core logic, adapter, carrier, deployment, or observation;
- activation requires trusting several new edges at once;
- rollback restores a whole solution rather than one decision boundary;
- the next migration begins before the instrument used to judge it is trustworthy;
- useful mechanisms become large because every trigger-specific concern is pulled into their core.

The correction is not to discard the audit or to add another framework. It is to turn the desired assurance behavior into a small product, then make existing workflow elements clients of that product.

## 2. Product boundary

The proposed product interface is a thin local CLI, provisionally named `adevctl`, over small pure-Python capability modules:

```text
policy / adopted criteria / canonical declarations
                       |
                       v
       +----------------------------------+
       | standalone control capabilities |
       | pure inputs -> typed result      |
       +----------------------------------+
                       |
                       v
              adevctl JSON contract
                       |
            canonical, bound receipt
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
   /implement         CI        deploy / health
     adapter        adapter          adapter
        |              |              |
        +---------- real triggers ----+
```

The core does not import command Markdown, hook scripts, GitHub APIs, deployment scripts, Claude Code settings, or agent definitions. Adapters may invoke the CLI; the CLI never invokes an adapter. A hook is a transport adapter, not the owner of policy, path extraction, evidence semantics, or telemetry.

This is a two-tier library design:

1. **Core:** deterministic functions over explicit data, with no ambient repository discovery when an explicit root/subject is supplied.
2. **CLI:** validation, bounded subprocess execution, canonical JSON, exit codes, and human diagnostics.

There is no dynamic plugin framework, service, database, dashboard, second pipeline, or new specialist agent. New capabilities are ordinary explicit modules and subcommands. Existing mechanisms are reused behind the contract only when their behavior and ownership are proven; their current APIs and file boundaries are not preserved merely for compatibility.

## Existing Solutions

The repository already contains partial capabilities. They are evidence and reuse candidates, not proof that the new product boundary exists:

| Existing mechanism | Keep/reuse | Current limitation |
|---|---|---|
| `plugins/autonomous-dev/lib/goa_cli.py` | precedent for a useful CLI before trigger activation | narrow scheduled-health product; prints manual trigger instructions and is not a general control contract |
| `plugins/autonomous-dev/scripts/proof_of_block.py` | subprocess transport, permit/refuse/fault idioms | specialized internal model and receipts; direct subprocess is not proof of registration/runtime dispatch |
| `scripts/mutation_witness.py` | bounded mutation, restoration journal, verdict classification | separate claim format and disputed/stale reachability statements; not a common acceptance contract |
| `plugins/autonomous-dev/lib/acceptance_criteria_tracker.py` | historical counterexample fixtures | presence/string-count semantics cannot establish operating effectiveness |
| `plugins/autonomous-dev/lib/pipeline_state.py` | current atomic-write and HMAC implementation as extraction/reuse evidence | atomic JSON is pipeline-coupled; HMAC covers only seven fixed fields, accepts unsigned legacy state, and may accept stale invalid state |
| inventory, reachability, settings, and manifest validators | parsers and graph inputs after independent characterization | parallel output formats and success claims do not share one typed authority |

C0 does not copy another atomic-write implementation. Transition A must decide, with a caller inventory, whether to extract the generic implementation from `pipeline_state.py` into a dependency-neutral utility or to keep receipt emission on stdout and let an adapter own persistence. The accepted design must leave one implementation for every caller it touches; it may not make the new core import pipeline orchestration.

The tool uses a deliberately narrow canonical JSON subset rather than claiming that ordinary “sorted JSON” is portable canonicalization: UTF-8; objects, arrays, strings, booleans, null, and integers only; no floats or NaN; keys sorted by Unicode code point; `json.dumps(..., ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))`; exact UTF-8 bytes hashed with SHA-256. Golden vectors include non-ASCII strings, key ordering, negative/large integers, arrays, escaped controls, and rejection of floats. If cross-language consumers later require RFC 8785, that is a versioned capability change with compatibility vectors, not an unannounced encoding change.

## 3. Stable contract established before capabilities expand

Rung C0 establishes the smallest contract every later capability and adapter must use.

### 3.1 Input

Every invocation receives explicit, schema-versioned input containing:

- `capability_id` and `case_id` or `control_id`;
- governing policy/acceptance references;
- a declared subject kind, path or identifier, optional profile, and expected digest;
- explicit declared dependency identifiers and expected digests;
- stimulus and binary oracle, including the opposite arm for conditional behavior;
- evidence level required;
- timeout, output bound, and allowed environment names;
- trigger context when an adapter invokes it.

The tool independently computes the observed subject/dependency digests where the input names local bytes; it reports declared and observed identities separately. Neither a caller-provided adapter name nor an unkeyed digest is called authenticated provenance.

Executable commands are argument arrays passed with `shell=False`, an explicit cwd constrained to the declared root, a reconstructed allowlisted environment, a resolved/allowed executable, closed stdin, bounded stdout/stderr, and a new process session whose whole descendant group is terminated and reaped on timeout. The tool never evaluates a shell string, inherits an unfiltered environment, silently changes cwd, or converts timeout, skip, missing dependency, parser failure, or zero selection into success.

C0 has two runner kinds only: `process` and `pytest_nodes`. Its closed oracle vocabulary is an AND-list of `exit_code_is`, `timed_out_is`, `stdout_exact`, `stdout_contains`, `stderr_exact`, `stderr_contains`, `stdout_json_equals`, `path_sha256_is`, and `path_absent`; `pytest_nodes` additionally requires the exact pre-collected node IDs plus passed/failed/skipped/error counts from a machine-readable result. Regex, Python expressions, shell fragments, arbitrary predicates, plugins, and natural-language verdicts are invalid. A later capability must version the schema to add another observation type.

### 3.2 Result and exit semantics

Every subcommand returns one typed state:

| State | Meaning | Exit |
|---|---|---:|
| `PASS` | The declared oracle passed on the exact subject and dependencies | 0 |
| `FAIL` | The tool ran and observed the counterexample or failed oracle | 1 |
| `INVALID` | Input/schema/selection is malformed, empty, ambiguous, or conflicting | 2 |
| `UNMEASURED` | The required carrier or observation was unavailable | 3 |
| `BEHIND` | Receipt or declared subject/dependency digest differs from independently observed current bytes | 4 |
| `ERROR` | The tool could not complete its own operation safely | 5 |

Only `PASS` permits an enforcing adapter. Report-only adapters attempt durable persistence for every state and surface persistence failure as `ERROR` with no receipt; they never translate a non-pass state into enforcement until activation is approved. Human output is a projection of the typed result, never an independent verdict.

### 3.3 Receipt

Canonical JSON receipts contain only the generic C0 facts required by every later capability:

- schema and tool contract version;
- capability/control/case and policy references;
- tool source digest and caller-declared adapter identity, if any;
- declared and independently observed subject identity/profile/digest;
- sorted declared and independently observed direct dependency identities;
- expected and observed outcomes for every required arm;
- start/end time, monotonic duration, bounded output digests, and explicit omissions;
- caller-declared trigger/carrier identity and invocation ID when present;
- state, ordered reason codes, and receipt integrity digest.

Receipts are immutable observations, not current status. C0 detects byte mismatch by recomputing explicitly named local subjects/dependencies; delivery semantics are C1 and policy-claim currency is C4. The unkeyed receipt digest proves integrity against accidental or later byte change, not author authenticity. Its preimage is the narrow canonical JSON encoding of the complete receipt with the `receipt_digest` key omitted; the stored digest is lowercase 64-character SHA-256 hex, and verification removes that key and recomputes. Authenticated provenance is a separate observed carrier credential or keyed signature and remains `UNMEASURED` when none exists.

C0 owns mandatory receipt persistence through one `assurance_contract.write_receipt()` implementation used by `adevctl --receipt`. It performs same-directory temporary creation, full write/flush/fsync, mode `0600`, atomic replace, and best-effort parent-directory fsync; it removes the temporary on failure. This is receipt-specific, not a second exported general JSON writer, and C0 does not change pipeline state. The CLI also returns the typed result on stdout; if durable persistence fails, it emits an `ERROR` decision with `receipt_persisted: false` on stdout/stderr and leaves no success receipt. An enforcing adapter must fail closed from that decision channel. T0 adds a versioned strict pipeline state whose HMAC message actually includes the receipt digest and whose gating verifier rejects missing/invalid signatures; legacy fail-open state can remain readable only as non-authoritative history.

C0 is Python-standard-library-only at runtime. JSON Schema files are design/build artifacts checked by independent development tooling, while the installed CLI enforces the same closed fields and types without importing `jsonschema` or any site package. The manifest-only test runs Python with `-S`, removes source paths, and begins with an empty temporary user configuration.

### 3.4 Non-negotiable properties

- The same input produces the same decision apart from declared observations such as time and runtime identity.
- Empty denominators, missing arms, unknown tool effects, missing routes, and corrupt inputs cannot pass.
- Observability/persistence failure cannot change a refusal into permission; the decision channel returns `ERROR` while durable evidence is explicitly absent.
- A receipt proves only its declared/observed subject kind; C1 later defines source/stage/install/runtime equivalence.
- An adapter cannot weaken core exit semantics or manufacture `PASS`.
- Every public function and subcommand has one owner, one schema, and one testable contract.

## 4. The repeatable rung

Every capability follows the same seven transitions. One issue owns one standalone capability rung (A–C) or one adapter rung (D–G), never both.

| Transition | Required evidence | State after success |
|---|---|---|
| A. Specify | frozen input/result/receipt schema, threat model, acceptance cases, old behavior characterization | `SPECIFIED` |
| B. Build | pure core and thin CLI; no production trigger changed | `BUILT` |
| C. Prove standalone | parser/linter, unit, CLI subprocess, both-arm, fault, tamper, timeout, and mutation cases | `STANDALONE_RELEASED` |
| D. Add one adapter | one real caller invokes the identical CLI contract in report-only mode | `SHADOWING` |
| E. Prove the trigger | actual carrier fires on exact installed/runtime subject; missing/wrong carrier controls fail | `TRIGGER_PROVEN` |
| F. Activate | one decision owner switches; rollback is rehearsed; superseded owner is removed or made non-authoritative | `ACTIVE` |
| G. Stabilize | full acceptance rerun, current receipt, docs/changelog transaction, no unexplained differential | `ADAPTER_RELEASED` |

No work starts on transition A of the next capability until all planned adapter rungs for the current capability are `ADAPTER_RELEASED`. Multiple adapters for one capability are separate D–G issues and are added sequentially. The old control remains the sole enforcement owner during shadowing; the new adapter may observe but cannot enforce. At activation, there is no dual-enforcing interval.

### Change-size limits

- One new capability or one new trigger per protected changeset.
- One enforcement-owner switch per activation changeset.
- No capability may require all future adapters to exist.
- No adapter may contain business/control logic beyond input translation and result translation.
- No compatibility layer survives without a named external caller, removal condition, and expiry issue.

## Testing Strategy

The test object is the claim, not the file or function. Each acceptance criterion names the subject, carrier, stimulus, expected observation, forbidden effect, opposite arm, counterfactual, proof level, runner, timeout, and invalidation rule before implementation.

### 5.1 Evidence levels

| Level | What it proves | Minimum counter-control |
|---|---|---|
| P0 — structural | schemas, AST/import graph, settings/workflow syntax, generated parity | corrupt schema or removed edge is rejected |
| P1 — core | pure capability semantics | closest permit/refuse or current/stale opposite arm |
| P2 — CLI | fresh subprocess, real files/stdin/stdout/exit codes | timeout, empty selection, wrong cwd/profile, tampered receipt |
| P3 — adapter | adapter invokes the same contract without semantic translation | adapter removed, wrong key, ignored exit, duplicated owner |
| P4 — trigger | actual Claude/CI/deploy/health carrier fires | disabled registration, wrong settings source, stale installed byte |
| P5 — consumer | clean installed consumer behaves on exact shipped bytes | source fallback, missing manifest member, clean-clone or rollback failure |

A higher level does not erase lower-level failure. `UNMEASURED` is honest evidence state and never activation evidence.

### 5.2 Required validation dimensions

Every activation packet answers all six dimensions separately:

1. **Design:** does the declared control cover the policy/criterion?
2. **Logic:** does the core return the right result on both arms and dependency faults?
3. **Connectivity:** did the intended entrypoint reach the intended capability exactly once?
4. **Deployment:** were the proved bytes/profile the bytes/profile actually loaded?
5. **Observability:** did the decision channel report every fail-open, timeout, and observation failure, and—when persistence succeeded—does the immutable receipt match it? Sink failure must explicitly report that no durable receipt exists.
6. **Provenance/currency:** can the receipt be bound to exact inputs and invalidated after any relevant change?

Aggregate suite green, coverage, test count, file presence, issue checkboxes, agent prose, and log volume cannot satisfy any dimension by themselves.

### 5.3 Independent bootstrap and anti-self-certification

C0 cannot certify its own trustworthiness. Its first packet is independently assembled with standard parsers, `ast.parse`, Ruff, ShellCheck/actionlint where relevant, frozen pytest node collection, standard digest tools, direct subprocess calls, and a reviewer who compares outputs to the pre-registered cases. Candidate self-mutations must make the independent checks fail.

Later capabilities may use a released earlier capability, but a change to the C0 schema, runner, receipt verifier, or exit semantics invalidates every dependent receipt and reruns the independent bootstrap suite. The candidate tool never promotes its own changed kernel solely from its own `PASS`.

### 5.4 Trigger proving protocol

For each adapter:

1. record old-owner decisions on a frozen truth table;
2. deploy the new adapter report-only with exact source/install digests;
3. drive the real trigger, not its function, on permit/refuse/error cases;
4. compare old and new decisions and explain every differential;
5. prove that removing the trigger, changing the payload key, changing settings source/profile, loading stale bytes, ignoring the exit code, or breaking the receipt sink is detected;
6. measure the actual carrier workload and record sample count, time window, machine/profile, cold/warm status, failures, and max; publish p95/p99 only after at least 100 representative samples, otherwise publish every observation plus median/max, and set timeouts from those data rather than inherited defaults;
7. rehearse the identical rollback vector from a clean pre-activation revision;
8. activate one owner, remove or demote the old owner, and repeat the same cases;
9. update generated projections, architecture/runbook/testing docs, and changelog in the same final-digest transaction.

## Plan adoption and execution carrier

The tracked plan is the durable authority; `.claude/plans/` is only the ignored execution mirror consumed by the current `/implement` command. Publishing the proposal or issues does not create that mirror and does not authorize protected-infrastructure edits.

After the user explicitly adopts an exact commit and SHA-256:

1. update #1737 and repurposed #1731/#1732 from their superseded B0/S0 sequence to this capability ladder, preserving old-plan links as history;
2. extract the committed blob, not mutable working-tree bytes, with `git show <adopted-commit>:docs/plans/20260906-control-tool-capability-ladder.md`;
3. write it as `.claude/plans/control-tool-capability-ladder.md`;
4. independently verify the extracted bytes against the adopted SHA-256;
5. record the source commit, blob ID, SHA-256, mirror path, and adoption event on the program issue;
6. invoke `/implement #1731 C0-A` only, naming the adopted plan digest.

The ignored mirror never becomes acceptance authority. A changed tracked plan requires a new critic verdict, commit, digest, explicit adoption event, and mirror replacement. A stale or mismatched mirror blocks execution rather than silently seeding the planner.

## Minimal Path

This order builds the measurement instrument before using it to simplify hooks and libraries.

### C0 — assurance kernel and executable-case runner

**Issue:** repurpose #1731.

Build only the common contract plus `case check`, `case run`, and `receipt verify`. It must be useful from a shell with no Claude Code, GitHub, deploy, or hook integration. Pre-register a small fixture matrix covering pass, fail, opposite-arm omission, zero collection, skip, timeout, malformed input, environment leakage, wrong subject/profile, tamper, stale receipt, dependency loss, and tool self-mutation.

Transition A is a dedicated `/implement #1731 C0-A` run ending in an immutable C0-pre commit. It creates `tests/acceptance/control-tool-c0.json` containing the schemas' exact versions and SHA-256 digests; every C0-A fixture/golden-vector path and SHA-256; the cases, expected nodes, and independent raw-observation commands; and no production implementation. The later `/implement #1731 C0-B-C` run may not edit the manifest, either schema, or any bound fixture/golden vector. A necessary correction stops B/C and requires a reviewed replacement pre-registration commit rebinding all affected digests before implementation resumes. Candidate file ownership is deliberately small:

| Path | C0 responsibility |
|---|---|
| `plugins/autonomous-dev/config/assurance-case.schema.json` | case input schema and closed vocabulary |
| `plugins/autonomous-dev/config/assurance-receipt.schema.json` | typed result/receipt schema |
| `plugins/autonomous-dev/lib/assurance_contract.py` | canonical encoding, digest verification, typed models/results, and the one receipt-specific atomic persistence implementation |
| `plugins/autonomous-dev/lib/assurance_case.py` | bounded runner and binary-oracle evaluation |
| `plugins/autonomous-dev/scripts/adevctl.py` | thin argparse/JSON/exit-code adapter; installed standalone entrypoint |
| `tests/unit/lib/test_assurance_contract.py` | pure schema/canonical/result/integrity tests |
| `tests/integration/test_adevctl_case.py` | real subprocess/isolation/oracle/fault tests |
| `tests/e2e/test_adevctl_install.py` | manifest-only installed CLI without source fallback |
| `tests/fixtures/assurance/` | frozen non-production subjects, cases, mutants, and golden JSON vectors |
| `tests/acceptance/control-tool-c0.json` | immutable C0-pre case manifest; B/C reads but cannot modify it |
| `plugins/autonomous-dev/config/install_manifest.json` | ships only the proved C0 files; no settings, hook, command, or workflow registration |

No `__main__` package, dynamic provider registry, command Markdown, hook, settings entry, CI workflow, deploy call, or pipeline-state change is in C0.

The immutable C0 case manifest pre-registers these minimum nodes:

| Case | Exact node | Required oracle / counterfactual | Budget |
|---|---|---|---:|
| `C0-C01` | `tests/unit/lib/test_assurance_contract.py::test_schema_rejects_empty_ambiguous_and_unknown_fields` | valid minimal case parses / empty, duplicate, ambiguous, or unknown fields are `INVALID` | 5s |
| `C0-C02` | `tests/unit/lib/test_assurance_contract.py::test_canonical_json_golden_vectors_and_float_rejection` | every golden byte/digest matches / key-order, Unicode, escape, integer mutation changes digest and float rejects | 5s |
| `C0-C03` | `tests/unit/lib/test_assurance_contract.py::test_result_states_have_one_stable_exit_code` | six states map exactly / unknown state and `PASS` with reasons refuse | 5s |
| `C0-C04` | `tests/integration/test_adevctl_case.py::test_process_uses_no_shell_explicit_root_and_rebuilt_environment` | argv reaches allowed executable with exact cwd/env / shell metacharacter, cwd escape, secret inheritance, and disallowed executable refuse | 10s |
| `C0-C05` | `tests/integration/test_adevctl_case.py::test_timeout_kills_descendants_and_bounds_both_output_streams` | process group is reaped and outputs bounded / surviving child, unbounded stream, or timeout reported as pass fails | 15s |
| `C0-C06` | `tests/integration/test_adevctl_case.py::test_binary_oracle_requires_expected_and_opposite_arms` | both named arms produce expected observations / missing arm, wrong exit, zero collection, skip, or collection error refuses | 15s |
| `C0-C07` | `tests/integration/test_adevctl_case.py::test_declared_and_observed_subjects_cannot_substitute` | declared and computed bytes/profile agree / wrong digest, dependency, subject, or profile is `BEHIND` | 10s |
| `C0-C08` | `tests/integration/test_adevctl_case.py::test_receipt_integrity_detects_tamper_without_claiming_authenticity` | unchanged receipt verifies and authenticity is null / result, output, subject, dependency, or caller mutation fails integrity | 10s |
| `C0-C09` | `tests/integration/test_adevctl_case.py::test_receipt_sink_failure_returns_error_on_decision_channel` | persistence succeeds at restrictive permissions / unwritable, partial, replace, or permission failure returns `ERROR` and no durable-success claim | 10s |
| `C0-C10` | `tests/integration/test_adevctl_case.py::test_independent_bootstrap_kills_kernel_mutants` | unmodified candidate passes independent observations / result, digest, timeout, environment, or oracle mutant is detected | 45s |
| `C0-C11` | `tests/e2e/test_adevctl_install.py::test_manifest_only_install_runs_without_source_fallback` | copied manifest files run under `python3 -S` for `--version`, case, and verify with source/site paths excluded / omitted file, extra file, third-party import, or source fallback refuses | 60s |
| `C0-C12` | `tests/integration/test_adevctl_case.py::test_measurement_packet_records_workload_samples_and_max` | every observation plus n/window/profile/max is present / sparse p95/p99, omitted error, or inherited timeout claim refuses | 30s |

**Exit:** independent bootstrap proves the standalone CLI and schema on source and manifest-only installed bytes; no runtime trigger has changed. Before C0 promotion, record the pre-C0 commit and destination digests, create a clean detached worktree at that commit, and rehearse `env LOCAL_REPOS=autonomous-dev bash scripts/deploy-all.sh --local --no-global` from it. Promote C0 with that identical command. Recovery runs the same command from the recorded clean pre-C0 worktree, verifies restored destination digests, then re-promotes only after repair. `deploy-all.sh` has no rollback mode, and the plan does not claim one. Because no caller is registered, C0 failure cannot change enforcement decisions.

### T0 — `/implement` adapter

**Issue:** repurpose #1732.

Add one explicit `/implement` receipt-producing invocation in report-only mode, then make the already registered `PreToolUse` git-commit gate verify it. Command Markdown is a producer, never enforcement authority: activation occurs only when the blocking hook refuses commit for a missing, non-pass, wrong-run, wrong-subject, or invalidly signed receipt.

The exact authority carrier is the existing per-repository `.claude/local/implement_pipeline_state.json`, upgraded to schema v2 with an `assurance` object. `pipeline_state.record_assurance_receipt()` writes and re-signs it; `pipeline_state.verify_assurance_state_strict()` is the only T0 authorization reader. Its HMAC message is the C0 canonical encoding of exactly `{schema_version, session_start, mode, run_id, explicitly_invoked, alignment_passed, alignment_verdict, nonce, assurance: {contract_version, run_id, case_manifest_digest, subject_kind, subject_digest, receipt_digest}}`; only the `hmac` field is omitted. To preserve the existing secret model exactly, HMAC-SHA256 key bytes are `(per_run_secret + nonce).encode("utf-8")`; the nonce is therefore intentionally present in both key derivation and the signed message. Missing secrets, unsigned/legacy schema, invalid HMAC, stale sentinel, run mismatch, or subject mismatch fail closed for T0 even if older state readers remain backward-compatible elsewhere. `pipeline_completion_state.py` remains the independent agent-completeness carrier and cannot satisfy assurance.

Live code has no current mechanical acceptance owner at commit: the advisory tracker is written by `/implement`, read only by the pinned-unreachable `step5_quality_gate.py`, while the commit hook verifies agent-completion state. T0 therefore introduces the first executable-case owner; report-only results compare against the advisory tracker only to expose differences, not to claim enforcement equivalence. At activation the unreachable/advisory acceptance tracker is deleted or explicitly demoted to a non-authoritative projection, while the existing agent-completeness control remains separate.

Exercise a fresh project-local Claude process and prove exact command expansion, state/receipt creation, real commit refusal/permission, wrong settings source, missing CLI, ignored result, invalid HMAC, stale sentinel, wrong run, and stale installed copy. Measure before setting a budget. Activate only this boundary.

**Exit:** `/implement` has one executable-case decision owner and rollback is rehearsed; CI and deploy remain unchanged.

### T1 — exact-SHA CI adapter

**Issue:** repurpose #1733.

Add the same C0 contract as one independent CI job plus one required-summary edge. Prove it on an actual Actions run whose `headSha` equals the candidate. Job absence, skip, `continue-on-error`, artifact loss, wrong SHA, and receipt mismatch refuse.

**Exit:** local `/implement` and CI use the same schema/evaluator but remain independent carriers.

### C1 — delivery identity and provenance

**Issue:** repurpose #1734.

Add explicit source, stage, install, runtime, profile, manifest, and dependency identities plus comparison/currency functions. This capability reads caller-supplied subjects; it does not deploy. Prove missing, extra, stale, duplicate, wrong-profile, source-fallback, and unrelated-change cases standalone.

**Exit:** `adevctl delivery verify` can distinguish design/source proof from what is staged, installed, and running without any deploy integration.

### T2a — deploy-postflight adapter

**Issue:** repurpose #1735.

Connect C1 to the mandated `deploy-all.sh` postflight in report-only mode, prove local staging/install/recovery with the identical target vector, then activate.

**Exit:** deployment creates the authoritative installed-subject receipt and never infers runtime truth from source.

### T2b — health adapter

**Issue:** #1738.

After T2a is `ADAPTER_RELEASED`, connect the same capability to `/health-check` and prove it on the installed subject. Health reads/recomputes installed identity; it cannot reuse deployment success as current status.

**Exit:** health independently detects later skew without becoming a second deployment owner.

### C2 — artifact/control connectivity graph

**Issue:** repurpose #1736.

Compile canonical declarations, native settings, manifests, entrypoints, imports, subprocess targets, and generated registrations into one deterministic graph. It must distinguish `declared`, `shipped`, `registered`, `reachable`, `invoked`, and `proved`, reject duplicate owners and unknown edges, and retain evidence for dynamic edges rather than assuming them. Use the current inventory and reachability logic as inputs; do not preserve their duplicate output formats.

**Exit:** `adevctl graph check` proves route existence and non-vacuity standalone against fixtures and the repository snapshot; it is not yet a gate.

### T3 — connectivity CI adapter

**Issue:** #1739.

Run C2 in report-only CI, seed removal of a registration, manifest member, entrypoint edge, dynamic target, and proof edge, then activate it as the one connectivity gate. Existing inventory/count checks become projections or are removed from authority.

**Exit:** a disconnected or duplicate artifact cannot merge, and a current graph receipt names the exact failed edge.

### C3 — behavioral control proof

**Issue:** use #1587 as the governing existing epic; #1660 supplies the mutation/non-vacuity residual.

Normalize the reusable behavior in `proof_of_block.py` and `mutation_witness.py` behind the tool contract: exact subject, real subprocess transport, permit/refuse arms, dependency-fault classification, mutation witness, restoration proof, bounded execution, and explicit unsupported cases. Do not merge all tests into one large engine and do not claim hook registration from direct-script execution.

**Exit:** `adevctl control prove` works standalone for one declared control family and independently detects a surviving mutant, silent fail-open, over-block, wrong payload shape, failed restoration, and stale subject.

### T4 — phase-closeout behavioral adapter

**Issue:** #1740.

Connect C3 to one phase-closeout boundary in report-only mode and run both arms through real carriers. Activate only after exact installed/runtime subjects are observed. `/health-check` may display the receipt but does not become a second decision owner.

**Exit:** a phase cannot close because tests merely exist; its named control behavior must have current both-arm evidence.

### C4 — claim currency and documentation impact

**Issue:** #1741; #1585 and #1575 remain inputs, not new-agent requirements.

Add typed normative, derived, measured, and historical claims; direct/transitive dependency identities; `CURRENT`, `BEHIND`, `STALE`, `UNVERIFIED`, `CONFLICTED`, and `HISTORICAL` precedence; and graph-derived documentation impact. Start only with PROJECT goal/status projection and documents touched by capabilities C0–C3. Ordinary prose is not scraped into a denominator, and a `Last Updated` field is not evidence.

**Exit:** `adevctl claims check` detects the repository's known stale/contradictory fixtures and can distinguish required update, regenerated projection, grounded no-impact, and historical correction.

### T5 — documentation-transaction adapter

**Issue:** #1742.

Connect C4 to the existing documentation review/final-closeout boundary in report-only mode. The doc-master supplies semantic judgments for graph-derived narrative claims, but the tool owns completeness, subject binding, and invalidation. Prove code-after-review, test-after-review, stale generated block, missing impacted doc, false no-impact, and unavailable semantic-review cases before activation.

**Exit:** code, tests, generated projections, affected documentation, and changelog form one final-subject transaction; prose verdicts cannot override missing evidence.

### C5 — canonical projection compiler

**Issue:** #1743.

Generate settings registrations, hook metadata projections, install manifest membership, command/reference indexes, and count summaries from canonical artifact/control owners. Each projection has deterministic regeneration and a declared consumer. Do not generate semantic prose or create a universal configuration language.

**Exit:** `adevctl project generate/check` reproduces each bounded projection byte-for-byte and refuses hand-edited or multiply owned outputs.

### T6 — install/deploy projection adapter

**Issue:** #1744.

Make install/deploy consume checked C5 projections one family at a time. Prove source/stage/install equivalence, canary, and rollback for each projection before deleting its old handwritten owner.

**Exit:** deployment no longer reconciles competing settings/manifests by convention.

### M0 — vertical migration and subtraction

**First slice:** #1673, the sensitive-write control, only after C0–C5 and T0–T6 are released as shown in the dependency graph.

Migrate one control family at a time:

1. freeze its policy truth table and old real-carrier behavior;
2. move pure decision logic to the appropriate capability module;
3. make the hook/function hook a thin typed adapter;
4. shadow and compare on actual payload schemas, including unknown/broad/non-filesystem effects;
5. activate one owner and remove duplicate registrations, path extractors, telemetry authority, and compatibility code;
6. rerun standalone, adapter, trigger, installed, rollback, currency, and projection checks;
7. update architecture, hook/library references, runbook, testing method, and changelog.

Function Hooks / Hooks 2.0 may replace shell or command adapters where the installed Claude Code contract is independently proven, but no core capability depends on that API. A transport upgrade is one trigger issue, not a reason to rewrite the tool.

After the sensitive-write exemplar is released, group remaining migrations by decision owner—not file type—and create one bounded issue per family. Delete unreferenced libraries only from graph evidence plus behavioral equivalence; the current measured architecture count is 238 libraries, but neither that topology nor any lower count is a target.

### P7 — installed-consumer proof and continuing assurance

**Issue:** retain #1636.

Install manifest-selected bytes into a clean consumer, run the released tool without source fallback, exercise representative real triggers, verify rollback, and schedule periodic read-only checks only after their underlying subcommands are independently released. Scheduling observes released capabilities; it never makes them correct.

## 7. Dependency graph and stop conditions

```text
C0 -> T0 -> T1 -> C1 -> T2a -> T2b -> C2 -> T3 -> C3 -> T4
                                                        |
                                                        v
                                               C4 -> T5 -> C5 -> T6
                                                                    |
                                                                    v
                                                     M0 sensitive-write exemplar
                                                                    |
                                                                    v
                                                  remaining migrations -> P7
```

The following stop the next transition:

- prior standalone or adapter rung is not in its required `STANDALONE_RELEASED` or `ADAPTER_RELEASED` state on current bytes;
- required proof is `UNMEASURED`, `BEHIND`, `INVALID`, `ERROR`, skipped, or expired;
- report-only comparison has an unexplained differential;
- the actual trigger or installed subject was not exercised;
- rollback was not rehearsed with the same deployment vector;
- a new duplicate authority or compatibility layer lacks removal criteria;
- docs/projections/changelog do not match the final subject;
- a timeout lacks current measurements or observation coverage is incomplete;
- issue acceptance criteria refer to mutable prose instead of immutable plan bytes/case IDs.

## 8. GitHub issue operating model

The program issue is the navigation and state ledger. This plan is the acceptance authority after explicit adoption of an exact commit and SHA-256. Child issues link plan rung IDs and evidence; they do not restate or mutate policy semantics.

Every child issue must contain:

- one rung only: standalone capability A–C or one adapter D–G, never both;
- predecessor release receipt and successor issue;
- in-scope files/interfaces and explicit non-goals;
- pre-registered case IDs with subject, carrier, oracle, opposite arm, counterfactual, level, runner, and timeout;
- source/stage/install/runtime requirements that apply;
- observability, traceability, provenance, currency, performance, security, and rollback criteria;
- exact closure packet fields;
- overlap dispositions: `absorbed`, `residual`, `independent`, `historical`, or `rejected with reason`.

No issue closes from a commit reference alone. Existing issues remain open until their individual residual is evidenced or explicitly rejected. Contradictory historical text receives an append-only correction and stops acting as current authority; history is not rewritten.

## 9. Immediate next execution package

Only C0 becomes implementation-ready after explicit plan adoption, in two separately reviewed runs/commits.

The first `/implement #1731 C0-A` package contains only:

1. case and receipt schemas;
2. `tests/acceptance/control-tool-c0.json` with C0-C01 through C0-C12, exact future nodes, subjects, oracles, counterfactuals, budgets, independent raw observations, and the SHA-256 of both schemas plus every fixture/golden vector;
3. the bound non-production fixtures/golden vectors, immutable to C0-B-C;
4. review confirming no production implementation or trigger changed;
5. the immutable C0-pre commit.

The second `/implement #1731 C0-B-C` package consumes that exact manifest and contains:

1. pure contract/receipt core and thin `adevctl` case/receipt CLI;
2. standalone P0–P2 tests and independent bootstrap/mutation/tamper packet;
3. manifest-only installed-copy proof under Python `-S`;
4. install-manifest entry only after that staged-copy proof; no command, hook, CI, deploy-postflight, or doc-master trigger;
5. architecture/testing/runbook/changelog updates limited to shipped C0 facts;
6. measured performance packet, exact clean-worktree recovery rehearsal, and `STANDALONE_RELEASED` receipt.

T0 is a later `/implement` run. It consumes the released C0 contract unchanged. If T0 reveals a core defect, T0 stops; C0 is reopened and repaired as its own versioned capability change before the adapter work resumes.

## 10. Program completion

The program completes only when:

- each capability is independently usable and proven without its adapters;
- each production trigger was added and activated one at a time on real installed/runtime subjects;
- every active control has one decision owner and current permit/refuse/fault evidence where applicable;
- source, stage, install, runtime, receipt, and policy identities are traceable end to end;
- stale or contradictory claims cannot act as current authority;
- settings, manifests, registrations, indexes, and maintained counts have one canonical owner;
- superseded hooks, libraries, configs, tests, and documentation claims are removed or explicitly historical;
- a clean consumer proves the shipped toolkit without source fallback;
- the resulting system is smaller in authorities and integration paths, with complexity remaining only in independently testable capabilities.

## Acceptance Criteria

- **AC-01 — product boundary:** C0 is callable and useful as a manifest-only installed CLI without Claude Code, GitHub, command Markdown, hooks, workflows, deployment execution, or agents; core imports do not cross into adapter/runtime owners.
- **AC-02 — narrow stable contract:** the no-float canonical JSON subset/digest preimage, closed two-runner/oracle vocabulary, six result states/exit codes, declared-versus-observed identity, receipt integrity limits, receipt-specific atomic persistence, subprocess isolation, stdlib-only runtime, and sink-failure semantics pass C0-C01 through C0-C12 and independent mutant controls.
- **AC-03 — no self-certification:** a separate `/implement` C0-A run and immutable C0-pre commit freeze `tests/acceptance/control-tool-c0.json` before the C0-B-C implementation run; independent parsers, digests, subprocess observations, and mutations—not candidate `PASS` alone—authorize `STANDALONE_RELEASED`.
- **AC-04 — one rung at a time:** each GitHub child owns one A–C capability rung or D–G adapter rung; the next capability cannot start until every planned adapter for the current capability is `ADAPTER_RELEASED` on current bytes.
- **AC-05 — real enforcement endpoint:** report-only integrations cannot enforce; an activated integration terminates at a real blocking hook/job/deploy failure, proves both permission and refusal through the actual carrier, and has exactly one decision owner.
- **AC-06 — signed gate binding:** before T0 activation, the receipt digest and run/subject identity are covered in the exact schema-v2 sentinel HMAC preimage and read through a strict assurance verifier; unsigned, invalid, legacy, wrong-run, wrong-subject, and stale state cannot authorize commit or be substituted by agent-completion state.
- **AC-07 — dimensional proof:** each activation reports design, logic, connectivity, deployment, observability, and provenance/currency separately; missing/failed/behind/unmeasured dimensions never collapse into aggregate pass.
- **AC-08 — measured performance:** trigger budgets name workload, machine/profile, window, sample count, failures, and maximum; p95/p99 are withheld below 100 representative samples.
- **AC-09 — rollback and subtraction:** the identical deployment vector is rehearsed before activation; the superseded authority is removed or made structurally non-authoritative in the owner-switch changeset, with no dual-enforcing interval.
- **AC-10 — currency and documentation:** C4/T5 make final code, tests, projections, impacted documentation, and changelog one subject-bound transaction; `Last Updated`, issue state, test presence, counts, and agent prose cannot establish currency.
- **AC-11 — safe simplification:** behavior migrates vertically one control family at a time; adapters contain translation only, duplicate settings/path extraction/registries/telemetry authority are subtracted with their replacement, and no module-count target drives deletion.
- **AC-12 — durable execution authority:** the tracked adopted plan commit/SHA-256 is authority, `.claude/plans/` is a byte-verified ignored mirror only, and every issue/evidence packet links immutable case IDs and exact subjects.

## Critique History

### Round 1 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 2.17/5.

Accepted revisions: add the `.claude/plans/` execution-mirror protocol and required plan sections; narrow C0; define canonical JSON and subprocess trust boundaries; distinguish declared identity, observed identity, integrity, and authentication; separate `STANDALONE_RELEASED` from `ADAPTER_RELEASED`; pre-register C0 files/cases; bind T0 receipts inside strict HMAC state; terminate T0 at a blocking PreToolUse commit gate; define sink failure honestly; add measurement sample rules; correct the live library count.

### Round 2 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 2.67/5.

Accepted revisions: split C0-A and C0-B-C into separate `/implement` runs/commits; freeze the exact case-manifest path; choose receipt-specific persistence; define digest preimage, closed oracle vocabulary, and stdlib-only installed runtime; correct the absent old acceptance owner; name the schema-v2 signed sentinel and strict assurance HMAC preimage; separate decision-channel evidence from sink persistence; replace nonexistent rollback with the exact clean-worktree deploy/recovery vector; rename T2a/T2b; align M0 with the dependency graph; require GitHub graph correction before execution.

### Round 3 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 3.17/5; Assumption Audit remained 1/5.

Accepted revisions: remove the ambiguous HMAC/nonce wording by freezing both exact message and `(per_run_secret + nonce)` key bytes; bind both schemas and every C0-A fixture/golden vector by SHA-256 in the immutable case manifest; forbid C0-B-C from changing any bound input without a replacement pre-registration commit.

### Round 4 — plan-critic — 2026-09-06

**Verdict: PROCEED** — composite 4.00/5; every axis 4/5.

The critic confirmed the exact HMAC message/key/nonce contract, immutable binding of both schemas and every C0-A fixture/golden vector, staged C0/T0 boundary, installed-runtime cases, plan validation, and clean-worktree recovery. Remaining risk is editorial only: AC-03/AC-06 summarize the detailed singular formulas rather than duplicating them.

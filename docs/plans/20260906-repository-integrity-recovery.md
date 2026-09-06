# Repository integrity recovery — one intent, one graph, one proof path

**Status:** PROPOSED — activation blocked by the current goal's abort clause; not authorization to edit protected infrastructure

**Date:** 2026-09-06

**Scope:** `autonomous-dev` source, clean-clone CI, installer, mandated deploy path, and installed consumer copies

**Governing intent:** [`PROJECT.md`](../../PROJECT.md), especially INV-1, INV-5, INV-7, and Q1/Q2

**Execution rule:** every protected-infrastructure change below runs through `/implement`; no bypass is part of this plan

## WHY + SCOPE

Make one deterministic contract answer, for every functional artifact:

1. **What is it?** One canonical identity and owner.
2. **Why is it present?** A machine-derived route from a real entrypoint.
3. **Does it work?** A proof against the real subject, including the opposite arm where behavior is conditional.
4. **Does it ship?** Every transport materializes the same canonical set.
5. **Is that what runs?** The installed bytes, settings profile, source identity, and proof receipt agree.
6. **Is the claim still true?** Every decision-relevant statement identifies its authority, subject, evidence/dependency identity, observation time, and invalidation or expiry rule.

The change is deliberately not an agent or pipeline consolidation. The 8-step pipeline and specialist roster remain intact. **The current library topology is not protected architecture:** module names, class boundaries, helper APIs, and compatibility layers may be replaced wholesale when the grounded behavior and data contracts are preserved or an intentional behavior change is approved separately. Simplicity comes from removing parallel inventories, hand-copied registrations, stale fixtures presented as production artifacts, and validators whose success labels exceed what they inspect.

### Architectural framing — controls-as-code with continuous assurance

This is not a new direction. [`docs/MAINTAINING-PHILOSOPHY.md`](../MAINTAINING-PHILOSOPHY.md) already names the project “policy as code, for software development itself” and separates macro policy, situational policy, controls, and assurance. `PROJECT.md` says the mission is not that steps ran, but that each control ran, refused and permitted correctly, and left a receipt. The audit is therefore a conformance repair: the repository's implementation has drifted away from its stated control architecture.

The more precise product description is **an executable SDLC control plane**:

```text
human policy / external standard
          ↓  scoped interpretation
control objective (INV-*, Q1/Q2, standard practice)
          ↓  compiled declaration
control implementation + enforcement point
          ↓  observed execution
evidence receipt bound to subject/version
          ↓  independent assurance
parser + linter + both-arm proof + mutation + deployed-byte check
```

“Policy as code” alone is too narrow because it can stop at a rule evaluator. This repository also owns control deployment, operating-effectiveness evidence, and continuing assurance. Conversely, business intent should not be forced into executable syntax: humans own the policy and scope decision; code owns every objectively decidable control beneath it.

The graph therefore has two node types—**artifacts** and **controls**—without a second registry. A control declaration lives beside its canonical owner and has a stable `control_id`, `policy_refs` (existing `INV-*`/Q1/Q2 IDs), optional versioned `standard_refs`, `control_type` (`preventive`, `detective`, or `corrective`), applicability/profile, enforcement points, fail semantics, implementation symbol, and proof IDs. The compiled graph emits the traceability/crosswalk view; humans do not maintain a parallel control spreadsheet.

Three effectiveness questions replace an undifferentiated PASS:

1. **Design effectiveness:** does the parsed control design cover the policy objective and have a grounded enforcement route?
2. **Operating effectiveness:** did the real control produce the expected permit/refuse/observe result on both arms for the identified subject?
3. **Deployment effectiveness:** are the proven control bytes/configuration the bytes/configuration actually active in each applicable environment?

External-standard mappings remain claims, not authority. A generated mapping may say `implements`, `supports`, `gap`, or `not_applicable`, with the exact standard/version/clause and evidence IDs; it cannot say “compliant” merely because a string or control ID is present. Adding a standard as a normative release gate is a separate scope decision with an explicit baseline and user sign-off.

### Truth lifecycle and currency

INV-5's “one topic, one home” prevents two owners from disagreeing, but it does not keep the one owner true. A canonical file can be stale, and a syntactically valid generated file can be derived from an obsolete subject. Currency is therefore a separate control dimension, not a documentation-hygiene synonym or an mtime check.

The denominator is explicit rather than inferred from English. A claim enters it only through a typed field or generated block beside an existing canonical owner, with a stable `claim_id` and schema; ordinary prose is never searched for status words and never silently promoted into a gate. Every declared claim is one of four kinds:

| Claim kind | Authority and currency rule |
|---|---|
| Normative | Human-approved policy, scope, or invariant in its canonical control document. It carries an `approval_ref` bound to the approved content identity; a digest detects post-approval change but never substitutes for human approval. It never gains currency from a `Last Updated` edit. |
| Derived | A projection such as settings, manifests, registries, counts, or control matrices. It is current only when byte-equivalent regeneration from its named owners succeeds for the current source digest. |
| Measured | A statement about behavior, performance, deployment, or status. It names the exact subject/profile, method/evaluator version, input window or event, source/config digest, observation time, provenance, and expiry/invalidation rule. |
| Historical | Changelog, issue, audit, plan, or prior measurement. It remains useful evidence and may receive an append-only correction, but it never sets current operational status. |

Freshness is dependency-based before it is age-based: changing an owning declaration, implementation, profile, evaluator, evidence corpus, or deployed subject invalidates the dependent claim immediately even if its date is today. Each evaluation resolves stable direct dependency IDs through the compiled graph, rejects duplicate IDs and cycles, and hashes canonical JSON containing the claim schema/version plus the sorted transitive set of `(dependency_id, kind, current-byte digest, profile/evaluator version where applicable)`. Current working-tree bytes—not `HEAD` alone—supply local identity. Missing, deleted, renamed, cyclic, or unresolvable dependencies are `UNVERIFIED` and fail evaluation; duplicate authorities are `CONFLICTED`; an unexpired receipt for a different digest is `BEHIND`; expired same-subject evidence is `STALE`. An unrelated file change leaves the subgraph digest unchanged. Currency is freshly computed: a persisted `CURRENT` label is never authority and none of these states may collapse to PASS.

Claim IDs are derived, never listed separately: `<canonical artifact_id>#<JSON Pointer>` for typed fields and `<canonical artifact_id>#generated:<marker>` for whole generated documents or Markdown blocks. Examples are `goal:repository-integrity-recovery#/status`, `project:PROJECT.md#generated:active-goal`, `hook:<hook_id>#/invoked_by`, `hook:<hook_id>#/proves`, `projection:hooks/hooks.json#generated:document`, and `manifest:install_manifest.json#/components/hooks/files`. The evaluator enumerates those pointers from the owner schemas and Slice 1 artifact inventory; adding a second owner for the same ID is a conflict.

Exactly one currency state is emitted with ordered precedence: an explicitly historical claim is `HISTORICAL`; duplicate authority is `CONFLICTED`; corrupt/unknown/cyclic/missing dependency or a normative content identity not bound by its approval receipt is `UNVERIFIED`; any resolved dependency/subject digest mismatch is `BEHIND`; an exact-subject measured claim past expiry is `STALE`; otherwise it is `CURRENT`. All applicable causes remain in a sorted `reasons` array, so simultaneous digest mismatch plus expiry is primarily `BEHIND` with expiry retained as a secondary cause.

Two assurance paths are required. The per-change path uses the compiled graph to invalidate or regenerate affected claims in the same change. The full-state `check --full` recomputes the complete typed denominator independently of the changed-file list, because external change, missed historical edits, and cumulative drift have no triggering local diff; release, deploy, and required CI become named callers in their later phases, while periodic scheduling is supplementary. Slice 1 contains only the goal-status source → generated PROJECT banner and the projections that Slice 1 already generates. Auto-loaded control inputs (`PROJECT.md`, `CLAUDE.md`, `AGENTS.md`) and other machine-consumed claims expand only after their typed owners exist in Phase 3; narrative reference docs follow after document-kind ownership is classified. A hand-edited date or a doc-master verdict is evidence that a review occurred, not evidence that the reviewed statement is current.

### Documentation is part of the change transaction

The valid unit of change is not code alone. It is the implementation, executable specification/tests, affected normative and reference claims, generated projections, and the release/history record when applicable, all bound to one final content identity. This does **not** require prose churn for every refactor: each changed functional artifact must resolve to either an exact affected-claim set that is updated/regenerated and reviewed, or a grounded `NO_DOC_IMPACT` disposition. An empty lookup, missing `covers:` entry, or agent assertion is `UNKNOWN`, not evidence of no impact.

Scope discovery is deterministic and happens before implementation from the artifact/control graph; the plan and implementation carry the expected claim IDs forward, and the evaluator recomputes them from the final diff. Generated documentation is regenerated by its owner. Doc-master handles only semantic narrative judgment over the exact graph-derived denominator and emits a structured receipt containing the base/final source and test digests, affected claim IDs, documents inspected, updates made, and per-claim disposition. Its prose length and final verdict string are diagnostics, not proof.

Any implementation, test, generated projection, or functional Markdown change after that review invalidates the receipt and requires recomputation plus re-review. `MISSING`, `SHALLOW`, `FAIL`, unresolved drift, skipped high-risk updates, an uncovered changed artifact, or receipt/subject mismatch cannot permit commit. Slice 1 proves this transaction for its narrow typed decision-input denominator; Phase 3 ratchets it across maintained code, tests, executable Markdown, and narrative documentation without a big-bang requirement to classify untouched legacy prose.

## Minimal Path

The current active goal has aborted by its own terms. That is an authorization boundary, not just a finding:

1. A documentation-only disposition records the existing goal as `ABORTED`; it does not rewrite dates or silently replace the goal.
2. Work then **stops**. No protected-infrastructure phase below begins until the user explicitly adopts this plan (or a narrowed version) as the successor goal.
3. Adoption authorizes only the small successor-policy amendment, the bounded **Safety Slice S0**, and **Slice 1** below. The later roadmap is sequencing context, not pre-approved implementation scope.

Adoption binds the exact plan bytes presented to the user and authorizes S0 followed by Slice 1A implementation. Slice 1A creates an explicitly non-authoritative, byte-complete typed successor-goal draft and reports its digest; it does not try to parse prose into policy. The user then approves those exact bytes, and the existing `record_alignment_verdict()` approval receipt records the approved subject path/digest before the goal or PROJECT projection becomes authoritative. Goal objective/scope are normative and content-bound to that receipt; milestone observations are measured; lifecycle status is derived from those observations plus the approved activation/abort rules; and the PROJECT banner is derived from status. No new approval registry is introduced, and “report-only 1A” below refers only to the new evaluator/CI enforcement state—not to approved governance or native-manifest source changes.

### GitHub reconciliation — phase input, not implementation authority

The issue tracker must be reconciled, but a 291-open-issue cleanup is not a prerequisite that delays the live S0 safety repair. The measured 2026-09-06 snapshot is: this plan cites 36 issue numbers—20 open, 15 closed, and nonexistent `#1747`—while a title-level search found at least 40 additional open candidates overlapping its phase subjects. Those counts describe reconciliation scope only; they are not durable status or proof.

After adoption, create one canonical program tracker bound to the adopted plan path, commit, and digest. Before each phase starts, reconcile only that phase's candidate issues and record one disposition per issue:

| Disposition | Required treatment |
|---|---|
| `CURRENT_PHASE` | keep or update one canonical phase issue; its checklist references the exact plan acceptance IDs and adds no independent ordering or policy |
| `ABSORBED` | map every still-valid acceptance criterion to a canonical phase acceptance ID, append the destination and plan digest, then close as superseded |
| `PARTIAL_RESIDUAL` | preserve the issue open, mark proved criteria with current receipts, and rewrite neither residual evidence nor remaining scope as complete |
| `HISTORICAL_CORRECTION` | retain the existing open/closed state unless a real residual remains; append the corrected fact and current local evidence without treating the comment as proof |
| `INDEPENDENT` | keep outside this program and label/link it as independently sequenced; “not in this plan” is never by itself a closure reason |
| `REJECTED` | close only when the adopted policy explicitly rejects the requested behavior and the issue comment identifies that decision and exact plan digest |
| `INVALID_REFERENCE` | correct the source citation; do not invent a replacement issue or silently renumber it |

No issue closes merely because its title overlaps an epic or because a new plan exists. Every checkbox is mapped individually to `proved by current receipt`, `retained in issue`, `moved to <phase>/<acceptance ID>`, or `rejected by adopted policy`; an unmapped checkbox keeps the issue open. Dependencies point only forward through the plan's phase order, and future-phase criteria cannot block an earlier phase. Closed issues and changelog entries remain append-only prior-art/provenance indexes, never current implementation evidence. GitHub unavailability records `SYNC_PENDING` in the local phase report and cannot turn a failed technical gate green; tracker synchronization must complete before that phase is declared complete.

For S0, update existing [#1673](https://github.com/akaszubski/autonomous-dev/issues/1673) as the canonical phase issue rather than filing another one: append that its “unwired” premise is historical, record that source commit `d90f8539` chose `fix` but did not deploy it, and map its false-positive/permit/refuse criteria to S0 below. Closed [#1503](https://github.com/akaszubski/autonomous-dev/issues/1503) and [#1588](https://github.com/akaszubski/autonomous-dev/issues/1588) remain historical inputs with correction links; they are not reopened or treated as proof that the installed MCP arm works.

### Safety Slice S0 — make the partial source repair durable and live before broader recovery

Source commit `d90f8539` landed after the initial audit and changes the three exact Serena probes from allow to deny by unioning `tool_intent.write_targets()` with the old jq `file_path`. The focused source suites collect 225 tests and pass. That commit is still incomplete as a durable control: both the project-installed and global-installed hooks retain SHA-256 `b6e3e406...` rather than source `bd961ed3...` and still allow the same Serena payload; the source adapter deliberately loses MCP coverage if Python/import/classification fails; and boolean-plus-empty-target still conflates broad writes, persisted-state writes, and unknown effects. Its proof appends `BROKEN` then `FIXED` beneath a top-level `Q2: YES`, is not installed-subject-bound, and retains the false claim that an `ask` reason is model-visible.

After successor adoption, S0 is therefore the first protected-infrastructure changeset and runs through `/implement --fix`; the disconnected-hook inventory does not continue while the active installed sensitive-write control is stale and its source fix has known fail-open/ambiguity semantics. It is deliberately separate from the settings/compiler rewrite and from `unified_pre_tool.py` subtraction:

- **S0-1 — proof currency:** regenerate the verdict from ordered arms plus source/installed dependencies so `BROKEN` followed by a source-only `FIXED` cannot yield installed `PROVEN`, and correct the stale claim that an `ask` `permissionDecisionReason` is model-visible;
- **S0-2 — typed effect:** evolve the existing canonical tool-effect result—not a second registry—from a boolean/possibly-empty target list to explicit `EXACT`, `BROAD`, `NON_FILESYSTEM`, and `UNKNOWN` dispositions with certainty and domain;
- **S0-3 — thin decision adapter:** make the sensitive-write adapter consume that result rather than any transport-specific path key; exact filesystem targets evaluate policy, broad filesystem and unknown MCP effects `ask` or deny according to the frozen control table, and Serena memory writers receive an explicit non-filesystem disposition rather than being confused with an empty filesystem target;
- **S0-4 — semantics before migration:** freeze the current case-insensitive regex behavior as an allow/ask/deny truth table before moving any static built-in case to gitignore-style native permissions; a native migration is accepted only for rows proved equivalent, while non-equivalent rows remain in the thin adapter until policy is explicitly changed;
- **S0-5 — one runtime owner:** choose one current runtime owner: the global installed profile owns the ordinary self-maintenance and consumer binding, the project copy does not redeclare it, and the isolated `plugin-native` canary disables user/global bindings and owns its one staged binding. Future profiles may choose a different owner only through the generated applicability matrix, never by merging two enforcing registrations;
- **S0-6 — real dispatch proof:** prove the complete settings/dispatch chain, not only a direct script subprocess, against source and installed digests before declaring the gap closed.

**S0-7 — acceptance suite:** S0 exits only when the positive built-in control, three exact Serena editors, a same-name wrong-key control, a read-only Serena `relative_path` negative, nested-CWD/project-root resolution, directory/glob and multi-file writers, Serena memory writers, broad/pathless writers, and an unknown `mcp__.*` tool all have explicit expected outcomes; source and installed profile selection fires exactly one enforcing owner; and schema or installed-byte change invalidates the receipt. Unknown MCP effects may not silently permit.

### Slice 1 — make the plugin load, then stop new disconnected/unproved hooks from shipping

This and S0 are the only implementation-ready slices. Native Claude Code validity is Slice 1's entry gate: a graph about commands, agents, skills, or hooks is meaningless if Claude Code does not load the plugin that contains them. The slice is limited to that entry gate plus the active goal's missed Phase 1 mechanism:

- make the tracked plugin and marketplace metadata pass the installed Claude Code `plugin validate --strict` schemas;
- prove a clean `git archive HEAD` copy is actually accepted by `claude --plugin-dir ... plugin list --json`, then check the exact component inventory with `plugin details`; parse `enabled`, `errors`, ID, version, path, and inventory rather than trusting exit code or searching human text;
- validate tracked command, agent, and skill frontmatter with Claude Code's own validator, and forbid non-component Markdown beneath auto-discovered component roots;
- generate the native `hooks/hooks.json` carrier from the same sidecars used by settings, and retire only the ignored/invalid hook member of `.claude-plugin/default-settings.json`;
- extend the existing sidecar schema and 34 sidecars with required `invoked_by` and `proves` fields;
- extract the already-tested hook/library route functions into one pure evaluator;
- migrate the current exact 4-hook/98-library UNKNOWN sets as a labelled `legacy-union` extractor-parity baseline, derive a separate `plugin-native` target/profile view as the only activation authority, and migrate the exact sidecars left without a collected proof scenario after mapping the existing eight scenarios into one path-plus-content-digest baseline;
- make canonical-manifest generation refuse a new or changed hook that has neither a verified route/proof nor an exact legacy pin;
- run that evaluator in a required clean-clone CI job, independent of the existing smoke job;
- add the exact first currency denominator to that evaluator: the adopted goal's typed status source, its generated PROJECT banner, the native hook carrier, sidecar route/proof fields, and only `install_manifest.json#/components/hooks/files`, the subprojection already generated by Slice 1; a fixture that reintroduces the disproven 266-row conclusion into the generated banner fails byte-regeneration, not sentence recognition.

Slice 1 does **not** consolidate all settings profiles, modify install/deploy behavior, migrate the second test tree, generate narrative docs, create durable consumer receipts, or split `unified_pre_tool.py`. It proves native discovery/load and the hook/library contract deterministically, makes the small set of decision inputs above incapable of silently carrying stale operational claims, and adds one bounded real command/skill→agent→hook/code→pipeline **measurement**. Under INV-8 that hosted Claude Code measurement cannot authorize activation; Phase 5 expands it only after the architecture decision below is resolved.

Slice 1 is two changesets, not a circular self-certification:

- **1A — native load plus evaluator report-only parity:** repair the native manifests, establish strict component validation, create and content-approve the typed successor goal before generating the PROJECT block, extract and compare the evaluator's `legacy-union` view with the current ratchet, separately publish the `plugin-native` target/profile view, and populate generated sidecar fields and the exact legacy baseline; the new contract job publishes differences but does not yet refuse, while approved PROJECT/native source changes take effect normally.
- **1B — required activation:** 1A has already added the evaluator/CLI as ordinary report-only manifest members. Only after 1A returns identical `legacy-union` hook/library path sets in a clean clone and every additional `plugin-native` profile gap is fixed or explicitly pinned does 1B use the target/profile view against temporary candidate manifests with one route and one proof removed; after both negative arms refuse, CI and canonical-manifest generation become blocking.

Slice 1 is bounded to the successor-policy amendment, a narrow extension of the existing alignment approval receipt, native metadata/hook projection, Ruff/ShellCheck/actionlint policies, one contract kernel/CLI/baseline, the existing hook schema/generator/manifest, 34 mechanically generated sidecars, focused native/contract/CI/canary tests, one local canary runner/fixture, and one CI workflow. If live research during `/implement` expands that non-mechanical set by more than 50%, stop and re-scope rather than absorb another subsystem.

The issue/changelog families in the Historical loop analysis below become named regression fixtures for Slice 1's existing mutations—unloaded plugin, declaration without route, a utility sidecar mistaken for a registration, an optional template mistaken for the active profile, empty/synthetic proof, test/probe telemetry presented as production evidence, mixed-age evidence without one subject digest, wrong profile, and wrong shipped subject. Slice 1 does not add a GitHub-state synchronizer or another historical ledger; history supplies failures to reproduce, while the local contract remains the authority.

## Evidence and failure pattern

The project already states the right definition of done: Q1 is a verifiable invocation route and Q2 is observed behavior on the real thing, on both arms ([`PROJECT.md:138-186`](../../PROJECT.md#L138-L186)). The repository does not yet enforce that definition end to end.

Live measurements on 2026-09-06:

| Surface | Measured state | What the existing green means |
|---|---:|---|
| Native Claude Code plugin validation | Clean `HEAD` fails `claude plugin validate --strict`; `.claude-plugin/plugin.json` has a schema error and `.claude-plugin/marketplace.json` is not a valid marketplace manifest | The source plugin is not loadable by the installed Claude Code 2.1.236 |
| Native Claude Code load probe | `claude --plugin-dir <clean-HEAD> plugin list` prints a failed-load diagnostic but exits 0 | Process exit alone cannot prove plugin load; expected inventory and failure diagnostics must be asserted |
| Static parsing | 69 JSON documents, 10 workflow YAML files, and 397 Python files parse; all checked shell files pass `bash -n` | Syntax only; no reference, workflow, or runtime connectivity is established |
| Python lint | Ruff 0.15.6 reports 912 findings under unconfigured defaults, including 13 `F821` undefined names | There is no checked-in lint policy or ratchet, so installed-tool output is not a durable gate |
| Workflow/shell lint | `actionlint` and ShellCheck are absent locally | Workflow expressions/job edges and shell semantics are not independently linted |
| Active hooks | 28 Python hooks, 34 hook sidecars | Presence and partial registration, not a route on each applicable profile |
| Libraries | 238 modules excluding `__init__.py` | 140 `REACHED`; 98 honestly pinned `UNKNOWN`, not dead |
| Refusal-capable hook ratchet | 4 pinned unreachable | No new source-level regression in the covered walker |
| Proof-of-block | 8/8 locally | Eight hand-selected scenarios, principally in two hooks; not the ~51-check denominator |
| Hook reachability tests | 141 passed in 70–74s | Valuable source-only instrument; already over the project’s 60s suite budget |
| Canonical manifest | 443 files, zero tests | File presence in one installer input, not execution or deploy-all membership |
| Legacy manifest | Materially different v3.50 file | A stale production-shaped test fixture with live readers |
| Plugin-local test tree | 500 tests collected, 3 collection errors | Not selected by root `pytest.ini` or CI |
| Current CI | Latest required run failed | Full suite and ratchets downstream of smoke did not run |
| Deployed repo copy | 5 manifest files differ from source | Internally consistent with an older stamp, not current |
| Global deploy check | 6 unexplained targets | Installed set is not the declared source set |
| Decision-input currency | `validate_structure.py` passes and 87 focused documentation tests pass, while the current `PROJECT.md` still says all 266 historical >5-second rows silently dropped checks; exact reconstruction attributes 243 to a 60-second Stop hook and only 23 to the then-5-second unified hook | Shape, fixture behavior, and changed-file review do not prove that a current operational claim still matches its subject |
| Documentation sweep | The stored covers index exactly regenerates, but it covers only 30 of 36 top-level docs, 1 of its 57 source mappings names a test path, and doc-master ignores 866 nested Markdown files; the shipped full-state detector emits 328 findings on this repo, largely from treating ordinary list prose and subgroup counts as artifact inventories; the local link checker separately finds 18 broken links | A green index proves deterministic indexing, while a noisy unconsumed report proves neither complete impact discovery, semantic currency, nor usable enforcement |
| Doc-master gate | Current instructions convert “no affected `covers:` mapping” into CHANGELOG-only plus PASS; retry exhaustion for `MISSING`/`SHALLOW` explicitly proceeds with a warning; `_VALID_DOC_VERDICTS` treats `FAIL` and `DOCS-DRIFT-FOUND` as verdict-present, and completion success is recorded for every result except `MISSING`. Open [#1662](https://github.com/akaszubski/autonomous-dev/issues/1662) and [#1699](https://github.com/akaszubski/autonomous-dev/issues/1699) record remediation clearing a failure without independent re-verification and fix-mode remediation leaving the earlier documentation result stale. | Agent completion, word count, and a parseable verdict prove only that output exists. Commit authority requires a non-empty graph-derived impact denominator, final-subject digest binding, outcome-aware fail semantics, and re-evaluation after every remediation. |

The repeated defect is not “a missing hook.” It is **subject mismatch**: a validator inspects a description, one copy, a filename, a count, or an empty list, then reports success for the behavior of the whole system.

## Existing Solutions

The audit started from `PROJECT.md`, then followed commands and agents into hooks/libraries, sidecars, settings, manifests, install/deploy, tests, receipts, CI, and documentation. It also followed the repository’s solved-problems protocol: closed issues, `CHANGELOG.md`, git history, then live execution. `rg` was used only to locate candidate owners and references; every finding promoted into the plan was checked with a parser, native validator, executable probe, digest comparison, test collection, or subprocess observation.

### Historical loop analysis — closed work is an index, not proof

The GitHub archive and changelog are a failure corpus, not a reliable current-state database. They show the same control being “completed” at one layer and rediscovered as absent at the next. Issue state and changelog prose therefore identify prior art to inspect; neither can authorize a current `PROVEN` claim without a same-subject receipt.

| Attempt and intended closure | Later measured contradiction | Constraint carried into this plan |
|---|---|---|
| [#348](https://github.com/akaszubski/autonomous-dev/issues/348) added hook-registration prose and tests after a full pipeline shipped an unregistered logger; [#551](https://github.com/akaszubski/autonomous-dev/issues/551)–[#555](https://github.com/akaszubski/autonomous-dev/issues/555) then added sidecars, a generator, CI, pre-commit, and `/sync --verify`. The changelog said sidecars eliminated manual registration ([`CHANGELOG.md:1325-1328`](../../CHANGELOG.md#L1325)). | [#1612](https://github.com/akaszubski/autonomous-dev/issues/1612) later found refusing hooks with sidecars and manifest presence but no lifecycle route; [#1569](https://github.com/akaszubski/autonomous-dev/issues/1569) remains open for declared registrations deployed nowhere; [#1672](https://github.com/akaszubski/autonomous-dev/issues/1672) found a documented recovery hook neither shipped nor bound. | A declaration is not a route. Sidecars must identify a valid native event/matcher/handler, the intended profile, and the shipped consumer; empty registration cannot count as wired. |
| [#1520](https://github.com/akaszubski/autonomous-dev/issues/1520) introduced “watched refusing” proof rather than presence checks. | [#1611](https://github.com/akaszubski/autonomous-dev/issues/1611) found the block log wrong in both directions; [#1524](https://github.com/akaszubski/autonomous-dev/issues/1524) shows a proof can stamp `HEAD` while exercising dirty bytes; [#1674](https://github.com/akaszubski/autonomous-dev/issues/1674) shows allow-path invocation is invisible. | Proof requires refuse and permit arms, source-attributed invocation, exact executed digest, and a sink that distinguishes not-invoked from invoked-and-allowed. |
| [#1612](https://github.com/akaszubski/autonomous-dev/issues/1612) added hook reachability, and [#1698](https://github.com/akaszubski/autonomous-dev/issues/1698) extended the ratchet through `lib/`. | #1612's deletion was halted when `enforce_orchestrator.py` had refusal rows despite no grounded route ([#1675](https://github.com/akaszubski/autonomous-dev/issues/1675)), but those rows have empty session identity and do not identify an invoker; recent rows coincide with hook-suite executions, so “an untracked production invoker was observed” is not established. The library ratchet then needed separate importlib and package-re-export repairs after classifying live modules as unknown ([`CHANGELOG.md:19-20`](../../CHANGELOG.md#L19)). | Static absence is `UNKNOWN`, never deletion authority; unattributed telemetry is also `UNKNOWN`, never production-reachability evidence. Each edge kind needs a positive control, and source-attributed runtime evidence must corroborate reachability before subtraction. |
| [#770](https://github.com/akaszubski/autonomous-dev/issues/770) closed mutation testing as delivered. | [#1668](https://github.com/akaszubski/autonomous-dev/issues/1668) found the tool uninstalled, the baseline entirely `TBD`, and the runner invoked by nothing, so it was deleted; the replacement witness for [#1660](https://github.com/akaszubski/autonomous-dev/issues/1660) is explicitly “built and NOT wired” ([`CHANGELOG.md:54`](../../CHANGELOG.md#L54)). | No config, dependency, script, or placeholder report may close a capability. The first non-empty execution receipt and its standing invocation route ship in the same change or the mechanism remains `UNMEASURED`. |
| [#1669](https://github.com/akaszubski/autonomous-dev/issues/1669) was filed because the always-loaded “search closed issues first” prose was skipped and a plan duplicated #770; a library was then shipped before its pipeline caller. | The changelog now says STEP 4.9 invokes that library ([`CHANGELOG.md:56`](../../CHANGELOG.md#L56)), while the GitHub issue remains open with its last comment saying wiring is still deferred. | Archive state itself needs reconciliation. Closed means “inspect,” open means “inspect,” and only live route/proof evidence decides current capability status. |
| [#1610](https://github.com/akaszubski/autonomous-dev/issues/1610) repaired deployment of uncommitted working-tree bytes. | Later changelog entries record source-deleted files surviving in global and remote installs while deploy still printed `ALL VALIDATIONS PASSED` ([`CHANGELOG.md:15-17`](../../CHANGELOG.md#L15)); the manifest then needed a recursive/path-preserving repair because its validator shared the same shallow scan ([`CHANGELOG.md:29`](../../CHANGELOG.md#L29)). | Do not fix transports one at a time or sample key files. One manifest-derived expected set and digest comparison must cover source, stage, every transport, installed bytes, deletion, and runtime profile. |
| [#1640](https://github.com/akaszubski/autonomous-dev/issues/1640) described consumer verification and was closed as a duplicate of [#1636](https://github.com/akaszubski/autonomous-dev/issues/1636), not as completed work. | [#1679](https://github.com/akaszubski/autonomous-dev/issues/1679) shows the reachability ratchet unions the dogfood profile and can pass hooks that reach no consumer; [#1703](https://github.com/akaszubski/autonomous-dev/issues/1703) shows consumers receive the libraries but none of the repo-local detectors. | A self-repo pass cannot discharge a consumer claim. The compact contract/proof runner and target profile must ship with the controlled artifact. |
| Registration and state bugs were repeatedly patched locally. | [#1522](https://github.com/akaszubski/autonomous-dev/issues/1522) remains open for duplicate global/project hook execution; [#1530](https://github.com/akaszubski/autonomous-dev/issues/1530) records six state roots and multiple owners; [#1730](https://github.com/akaszubski/autonomous-dev/issues/1730) shows an unscoped plan verdict from one run controlling another. | Every binding key includes target/profile/scope; every ephemeral decision includes repo/session/run/subject; exactly one owner writes each canonical fact. |
| [#1597](https://github.com/akaszubski/autonomous-dev/issues/1597) measured ten atomic-write implementations and 18 session-ID resolution sites, then proposed a shipped golden-path mechanism. | The issue remains open. The live 2026-09-06 AST scan now finds 11 atomic-write definitions across ten library files, including a last-resort fallback copy in `pipeline_completion_state.py`; naming a canonical candidate did not remove the siblings. | Land a non-vacuous structural guard before migration, pin the exact legacy set, then lower the set in the same changeset that migrates or deletes each implementation. A registry row is discoverability, not consolidation. |
| [#1588](https://github.com/akaszubski/autonomous-dev/issues/1588) repaired and closed `PreToolUseWrite-protect-sensitive.sh` after proving six prior dead/fail-open arms; [#1503](https://github.com/akaszubski/autonomous-dev/issues/1503) separately established `tool_intent.is_write()`/`write_targets()` as the transport-independent owner. | The initial 2026-09-06 audit found the then-505-line shell hook reading only `tool_input.file_path` while matching every `mcp__.*`; three live Serena `relative_path` writers permitted protected targets and a fabricated `file_path` refused. Commit `d90f8539` subsequently made those exact source probes deny by unioning `write_targets()`; 225 focused tests now pass. The project/global installed hooks remain on the old digest and still allow, while the source fallback explicitly loses MCP coverage on classifier failure and its boolean plus possibly-empty target list conflates broad filesystem writes, non-filesystem persisted state, and unknown tools. The proof retains a top-level `Q2: YES`, appended `BROKEN`/`FIXED` sections without an installed-subject verdict, and a false model-visibility claim. | A source-only patch is not a live control. A hook may not parse transport-specific path keys or silently permit an unknown/broad MCP effect on classifier failure. Static built-in path rules move to native permissions only where path semantics are proved equivalent; dynamic controls consume `EXACT`, `BROAD`, `NON_FILESYSTEM`, or `UNKNOWN`. Source, installed enforcement, custom decision, and telemetry have separate receipts; a later arm or source-only fix cannot promote the wrong subject. |
| [#1162](https://github.com/akaszubski/autonomous-dev/issues/1162) proposed a broad Claude-native redundancy refactor and was closed. | Its drain history records five repeated `--light` planner blocks because a multi-subsystem epic kept re-entering a single small pipeline run. | Treat the full refactor as a program of independently reversible vertical slices. The tracking plan is not itself an implementation unit, and no slice mixes behavior redesign with structural migration. |
| More checks accumulated inside `unified_pre_tool.py`. | [#1631](https://github.com/akaszubski/autonomous-dev/issues/1631) proves a single timeout bypasses all roughly 51 bundled checks. Exact reconstruction of the cited 84,339-row window finds 23 unified-hook rows above its then-5-second budget; the issue attributes 7 to deliberate probes and 16 to historical organic traffic, not 35 current production overruns. | Characterize before splitting, but stop adding decisions to the shared timeout. Extract only after per-decision both-arm evidence and explicit independent budgets exist. |
| CI and documentation used enforcing language. | [#1581](https://github.com/akaszubski/autonomous-dev/issues/1581) shows “blocking merge” with no branch protection or required checks; [#1613](https://github.com/akaszubski/autonomous-dev/issues/1613) shows the registry calling unwired hooks Enabled. The live paid-dependency hook still cites `PROJECT.md:59`, while that rule is now at line 81. | Reports must name the enforcement point they actually control. `PASS`, `ENABLED`, `BLOCKING`, and `CURRENT` are reserved for observed, applicable subjects; normative references use stable clause IDs rather than line numbers. |
| Issue bodies and changelog entries were treated as durable citations. | #1612, #1668, and #1672 each required later comments correcting material facts used in the original verdict. Separately, the committed changelog and code refer repeatedly to “Issue #1747,” but the live GitHub repository's highest issue is #1730 and `gh issue view 1747` does not resolve as of 2026-09-06. | Historical claims retain append-only corrections and resolvable identifiers. An unresolved reference or superseding correction is a named archive-integrity finding, never silent context. |
| [#1098](https://github.com/akaszubski/autonomous-dev/issues/1098) closed after promising a full-repository narrative-doc sweep; repeated doc-master fixes then added word-count, completion, retry, and remediation prose; [#1472](https://github.com/akaszubski/autonomous-dev/issues/1472) remains open for expiring claim shapes in always-loaded context. | The sweep scans only top-level `docs/*.md` with `covers:` and uses count/list heuristics; the per-change agent turns no mapping into PASS, can proceed after missing/shallow output, and is not bound to the final code/test digest. [#1662](https://github.com/akaszubski/autonomous-dev/issues/1662) and [#1699](https://github.com/akaszubski/autonomous-dev/issues/1699) show failed or pre-remediation verdicts losing authority without mandatory same-subject re-verification. | Extend the existing covers/graph ownership rather than build another documentation framework. Deterministic impact discovery precedes implementation; generated claims update mechanically; doc-master reviews the exact final narrative denominator; missing coverage or stale/failing verdicts refuse; a separate full-state pass catches historical and external drift. |

The loop's root cause is a **closure-unit mismatch**: issues have been closed when a file, configuration, test, or local fix exists, while the real unit of correctness is the complete control relationship—policy objective → applicable target/profile → native load → invocation → both-arm effect → evidence sink → shipped subject → current receipt. The simplest result is not another audit, registry, or counter; it is one compiled contract that evaluates that relationship and makes every other view a projection.

Useful mechanisms to keep and extend:

- [`docs/MAINTAINING-PHILOSOPHY.md`](../MAINTAINING-PHILOSOPHY.md) already defines the intended policy → control → assurance layering. Keep that conceptual home and make this plan executable; do not create a competing philosophy document.
- The reachability ratchet in [`tests/unit/hooks/test_hook_reachability_ratchet.py`](../../tests/unit/hooks/test_hook_reachability_ratchet.py) distinguishes a real import/invocation from a mention and reports `UNKNOWN`, not “dead.”
- [`plugins/autonomous-dev/scripts/proof_of_block.py`](../../plugins/autonomous-dev/scripts/proof_of_block.py) drives real subprocess refusal and permission arms.
- [`plugins/autonomous-dev/scripts/deploy_state.py`](../../plugins/autonomous-dev/scripts/deploy_state.py) already has strong forward/reverse digest, unrecorded-file, symlink, and deletion checks.
- [`plugins/autonomous-dev/config/hook_time_budgets.json`](../../plugins/autonomous-dev/config/hook_time_budgets.json) plus its loader is a sound canonical-data/runtime-reader pattern.
- The recursive manifest/path-containment regression in [`tests/regression/test_issue_1747_manifest_completeness.py`](../../tests/regression/test_issue_1747_manifest_completeness.py) is strong and fast.

Prior attempts also constrain this plan:

- [`enforcement-provable-both-modes.md`](enforcement-provable-both-modes.md) solved portability for a narrow proof corpus but did not establish a complete denominator.
- [`unified-pre-tool-subtraction.md`](unified-pre-tool-subtraction.md) correctly requires characterization before subtraction. Splitting the large hook before runtime proof would multiply silent-failure surfaces.
- The current active goal already chose “existing declarations plus manifest teeth”; this plan does not add a peer ledger.

External patterns reinforce the same minimal shape:

- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) supplies high-level secure-SDLC practices designed to be integrated into an SDLC. It is a useful versioned source for control objectives, not proof that this repo implements them.
- [NIST OSCAL](https://pages.nist.gov/OSCAL/) separates machine-readable control catalogs, implementations, assessment plans, and assessment results. Borrow that separation and export-compatible identifiers later if useful; adopting the full format now would violate minimalism.
- [Open Policy Agent](https://www.openpolicyagent.org/docs) demonstrates separation of policy decision from enforcement. The chosen pure evaluator plus thin hook/CI/deploy adapters preserves that property without adding a Rego runtime or a second policy engine.
- [Claude Code's plugin reference](https://docs.claude.com/en/docs/claude-code/plugins-reference) defines the native manifests, auto-discovered component roots, supported frontmatter, and `plugin validate` command. This is the primary schema oracle; the repo must not maintain a looser imitation and call it equivalent.
- [Claude Code's hook reference](https://docs.claude.com/en/docs/claude-code/hooks) defines lifecycle resolution as event + matcher + handler and specifies the JSON/exit behavior. Static registration is therefore one edge, while an observed lifecycle payload, launched handler, and decision/receipt are the behavioral proof.
- [Claude Code's skills reference](https://docs.claude.com/en/docs/claude-code/slash-commands) and [subagent reference](https://docs.claude.com/en/docs/claude-code/sub-agents) make discovery/frontmatter distinct from invocation. Native validation can prove discoverability; only a real expansion, Agent-tool dispatch/start/finish record, and source-attributed completion evidence can prove use.
- [actionlint](https://github.com/rhysd/actionlint) parses workflow syntax, expressions, `needs`, action inputs/outputs, shell snippets, and security-sensitive interpolation. It covers materially more than YAML parsing or text search.
- [ShellCheck](https://www.shellcheck.net/) detects shell semantic defects that `bash -n` cannot; both are needed because syntax and behavior are different claims.
- [GitHub's workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) defines job/step dependencies and `continue-on-error`; the contract compiler must parse these fields and the runtime proof must confirm required jobs actually ran.
- [SLSA build provenance v1.2](https://slsa.dev/spec/v1.2/build-provenance) binds a subject digest to the source and invocation that produced it. We need that relationship, not the full supply-chain framework.
- [in-toto attestations](https://in-toto.io/attestation/) separate the identified subject from the predicate asserted about it. The local receipt below uses that small idea.
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-core) is already the sidecar schema dialect; strict required fields and `additionalProperties: false` should remain the contract boundary.
- [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) permits empty parameter sets to become skips. Collection floors and explicit non-empty subjects are therefore required before a test tier can claim success.

## Verification hierarchy — search is discovery, never proof

Every claim advances through the smallest applicable levels below. A higher level does not erase a lower-level failure, and no level may report a broader subject than it inspected.

| Level | Mechanism | What it may prove | What it may not prove |
|---:|---|---|---|
| 0 | `rg`, file enumeration, git history | Candidate nodes, references, and prior art | Valid syntax, grounded connectivity, execution, or effect |
| 1 | JSON/YAML/frontmatter/Python/shell parsers | The exact subject is readable and structurally well formed | Names resolve or the platform loads it |
| 2 | Native/schema/static linters: `claude plugin validate --strict`, JSON Schema, Ruff, actionlint, ShellCheck, link/frontmatter validators | Platform schema compatibility, invalid references, import/name defects, workflow/shell semantic defects | A route was taken or a guard affected behavior |
| 3 | Typed artifact graph over parsed nodes | A complete declared/derivable entrypoint-to-subject route exists, or is honestly `UNKNOWN_PINNED` | The route executes in Claude Code |
| 4 | Clean-environment load/install probe | parsed `plugin list --json` has the expected enabled plugin and empty `errors`; strictly parsed `plugin details` reports the expected commands, skills, agents, and hooks from installed bytes | Each component's promised behavior works |
| 5 | Real workflow canary with lifecycle receipts | User command/skill expansion, agent dispatch/completion, hook launch/decision, code execution, and CI job execution occurred on the identified subject | The detector catches future broken edges |
| 6 | One-edge-at-a-time mutation | Removing or corrupting each edge makes the appropriate gate fail | Untested behaviors outside the declared denominator |
| 7 | Source/stage/install/consumer digest congruence | The proven bytes and configuration are the bytes/configuration that ship and run | Fresh behavior when the receipt has expired |

Required tools are pinned and checked into the repo with their scope and configuration. Missing tools, unsupported Claude Code versions, unknown native-output schema, parse failures, empty subjects, warning-only fallbacks, non-empty `plugin list --json.errors`, `enabled: false`, or a native command that prints failure while exiting 0 are evaluator error (exit 2), never PASS. Existing lint debt is introduced with an exact no-growth baseline; syntax errors, native plugin-load errors, changed/new Ruff `F821`, Ruff `E9`, actionlint syntax/expression/dependency errors, and new ShellCheck errors block immediately. Baselines identify exact files/rules/content, expire, and can only shrink.

The initial static-tool lock is explicit, not “latest”: Ruff `0.15.6` with SHA-256 `e90a351ddc2e5e411168b5cbfc7d694231e793948d0a29aa82618ea6f17225f1` for Darwin arm64 and `c253b106eb136f9cb4a319b5e3b4a9df78ec31fe15a3822efb69e7887ef9166e` for Linux amd64; actionlint `1.7.12` with SHA-256 `aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f` for Darwin arm64 and `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8` for Linux amd64; ShellCheck `0.11.0` with SHA-256 `56affdd8de5527894dca6dc3d7e0a99a873b0f004d7aabc30ae407d3f48b0a79` for Darwin arm64 and `8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198` for Linux amd64. These were verified from the projects' official GitHub release metadata on 2026-09-06. `plugins/autonomous-dev/config/static_toolchain.json` is the sole owner of tool version, release URL, platform, and digest; linter config files own rules only, while the bootstrap and CI must read the lock instead of repeating literals. Unsupported platforms are explicit `UNMEASURED` until their official artifact digest is added; the bootstrap verifies digest before extraction and the executable's reported version before use. Contract tests mutate each version, URL, digest, and consumer lookup independently so a duplicated or skewed tool pin refuses.

### Claude Code element-to-workflow verification matrix

| Element | Parsed/native static check | Grounded graph edge | Runtime receipt | Required mutation |
|---|---|---|---|---|
| Plugin and marketplace metadata | JSON parse plus installed `claude plugin validate --strict`; reject ignored/unknown production fields | marketplace/source → plugin root → declared/auto-discovered component roots | clean `git archive HEAD` and manifest-only install produce parsed `plugin list --json` rows with `enabled: true`/empty `errors`, then strictly parsed `plugin details` with exact inventory, even where the CLI exit is 0 | corrupt manifest type, move component root, add unknown production field |
| Commands and skills | YAML frontmatter parser plus native strict validation; component roots contain components only | plugin discovery → normalized command/skill ID; referenced files and allowed tools resolve | real `/implement --light` input/expanded command plus a separately bounded direct `architecture-patterns` invocation identify the command/skill subjects and digests; no nonexistent production `UserPromptExpansion` hook is claimed | remove frontmatter, rename ID, move support file, place a non-component Markdown file under the root |
| Agents | YAML frontmatter parser plus native strict validation of supported fields/model/tools/skills | grounded command/coordinator dispatch → exact discovered agent ID | stream Agent-tool records establish planner dispatch/start/finish; after return, the coordinator's required synchronous `record_agent_completion()` call changes the exact completion state consumed by the next ordering check. Separately, `SubagentStop` launches `unified_session_tracker` and emits source-attributed telemetry; that idempotent asynchronous write is not credited as ordering authority | rename/delete agent, break dispatch name, suppress the synchronous recorder/state row/ordering consumption and require the load-bearing branch to fail; independently suppress `SubagentStop` or its tracker call and require telemetry loss without falsely expecting ordering failure |
| Hooks | sidecar JSON Schema, lifecycle vocabulary, generated-settings parse, native `hooks/hooks.json` schema | profile/scope → event → matcher → exact handler argv → imported decision code | Claude Code emits a real lifecycle JSON payload; exact installed handler starts and records permit/refuse/observer result with reason ID | remove binding, alter matcher, change argv, remove executable, force handler exception |
| Python hooks/libraries | `ast.parse`, Ruff with checked-in config, import graph and dynamic-import resolver | grounded handler/command/script → import/call chain → module/function | subprocess coverage/trace ties executed module digests to a real hook/command proof | replace import/call with prose, undefined name, dynamic loader target missing |
| Shell/install/deploy scripts | `bash -n` plus ShellCheck with checked-in config | grounded command/CI/git hook → exact argv/cwd/env/timeout → script | fake-boundary contract captures argv/stdin; clean local run records every return code and promotion boundary | quoting/path defect, missing tool, swallowed non-zero, interrupted promotion |
| Settings and profiles | JSON parse/Schema, unique `(hook_id,event,matcher,scope)` ownership, official event vocabulary | sidecars/profile overlay → generated settings → Claude Code-resolved binding | canary event fires once in the intended scope/profile and not in excluded profiles | duplicate global/project binding, wrong profile, invalid event, stale generated output |
| GitHub Actions | YAML AST plus actionlint/ShellCheck; custom job DAG check validates `needs`, `if`, `continue-on-error`, timeouts, and required summary | changed artifact → independent required job → exact evaluator/proof command → summary | PR/dispatch run receipt names commit, job, collected subject count, exit, and artifact digest; unexpected skip fails summary | remove `needs`, add `continue-on-error`, make subject empty, crash router, skip required job |
| Tests/proofs | pytest collection API, unique proof IDs, non-zero tier floors, mutation-witness schema | artifact/control → exact test/proof ID → selected required job | both arms execute against subprocess/installed subject and emit subject digest | deselect tier, duplicate ID, empty parametrization, mutate only the test |
| PROJECT/docs | Markdown AST/link checker plus generated volatile tables | canonical graph/goal state → generated claim source | regeneration is byte-stable and current receipts back operational claims | hand-edit a generated count/status or point a link at a stale owner |

The runtime canary is deliberately a chain, not ten isolated smoke tests:

```text
clean tracked source
  → native manifest validation
  → manifest-only temporary install
  → Claude Code loads exact plugin inventory
  → `/implement --light` expands from the real command file
  → the Agent tool dispatches `planner` with declared `architecture-patterns`
  → the raw stream records dispatch/start/finish identity
  → after Agent return, the coordinator synchronously calls `record_agent_completion()`
  → the exact planner completion-state row appears and the next ordering check consumes it
  → the local canary runner emits a content-addressed measurement receipt

separate asynchronous assurance branch:
planner stop → registered `SubagentStop` → `unified_session_tracker.py`
  → source-attributed activity/telemetry receipt and idempotent duplicate completion write
```

Each arrow has a stable edge ID, source/installed digest, and one destructive fixture mutation that must break the specific branch at that arrow. Suppressing `SubagentStop` must break the telemetry branch but must not be used as evidence that synchronous pipeline ordering failed; only suppressing the coordinator recorder, state write, or ordering read may break that load-bearing branch. The current `claude -p` auth is first-party hosted, even if it has zero marginal monetary cost. INV-8 therefore makes the model-backed canary measurement-only: absence of that environment yields `UNMEASURED` and blocks only the `E2E_PROVEN` claim, while deterministic offline gates continue to run and remain the only activation authority.

The two receipts are deliberately separate:

- **Deterministic CI receipt:** native/schema/linter results, parsed graph, clean install/load inventory, workflow DAG, offline subprocess both-arm proofs, mutations, and subject digests. This is recomputed in a clean clone and never claims a model-backed command/agent run.
- **Local Claude Code canary receipt:** exact Claude Code version and argv, temporary fixture identity, staged plugin digest, parsed `stream-json` command/Agent tool records, coordinator-issued synchronous recorder invocation, pipeline state before/after and next ordering result, plus a separately source-attributed `SubagentStop` event/handler/activity record, timestamp, and expiry. It is produced by `claude -p --output-format stream-json --include-hook-events` against a manifest-only temporary install and an isolated temporary repository. At most two model-backed runs occur per candidate: one `/implement --light` path and one direct `architecture-patterns` skill invocation. Per-arrow mutations run against the deterministic graph, subprocesses, and recorded-stream parser; Slice 1 performs zero model-backed mutation reruns.

Slice 1B activates only from the deterministic receipt. The canary receipt is diagnostic and cannot authorize activation, commit, CI, install, or deploy. A current same-digest canary allows status to report `E2E_PROVEN`; missing, stale, unparseable, or differently digested evidence reports `UNMEASURED` without pretending CI ran a model. Making this hosted canary load-bearing would contradict INV-8 and requires explicit architecture-delta sign-off; the preferred future path is a genuinely local Claude Code-compatible model backend. No paid model is introduced as a fallback.

## Current system and broken edges

```text
PROJECT.md intent
      |
      +--> commands/*.md ----dispatch prose----> agents/*.md
      |         |                                  |
      |         +---- duplicated Python maps ------+
      |
      +--> hooks/*.py <----imports---- lib/*.py
                |
                +--> *.hook.json --> generate_hook_config.py
                                      |             |
                                      v             v
                              canonical manifest   global settings only
                                      |             |
                         install.sh --+             +-- six hand-maintained profiles
                                      |
                         deploy-all.sh X  (rsyncs directory trees, not manifest set)
                                      |
                                      v
                        source stamp / installed bytes / runtime settings

tests -----------------> selected source behavior only
plugin/tests ----------> disconnected second pytest suite
proof_of_block --------> non-blocking CI sample
docs/registries -------> hand-restated counts and status
```

The target is one compiled graph with several projections, not several registries that compare each other.

## Findings

### P0 — the active goal has triggered its own abort condition

The goal required `invoked_by`, `proves`, and manifest refusal by 2026-08-31, then generated hook/lib declarations by 2026-09-03 ([goal lines 449–454](../experiments/GOAL_2026-08-24_enforcement-proven-everywhere.md#L449-L454)). The live schema still requires only `name`, `type`, and `interpreter` ([schema lines 7–82](../../plugins/autonomous-dev/config/hook-metadata.schema.json#L7-L82)); none of 34 sidecars has either required field.

The same goal says the existing slip carries forward, one more slip aborts, and no third rewrite is allowed ([goal lines 488–522](../experiments/GOAL_2026-08-24_enforcement-proven-everywhere.md#L488-L522)). `PROJECT.md` still says “1 slip” and “ACTIVE.” No guard reads goal milestones or abort predicates. The first implementation change must record the abort/re-scope honestly; quietly moving the dates would reproduce the defect.

### P0 — the tracked plugin is invalid to the native Claude Code loader

Against a clean `git archive HEAD` and the installed Claude Code 2.1.236:

- `claude plugin validate --strict plugins/autonomous-dev` fails because `.claude-plugin/marketplace.json` lacks the native marketplace `owner` and `plugins` structure and contains 18 ignored fields;
- validating `.claude-plugin/plugin.json` directly fails because `repository` is an object where Claude Code requires a string, while `components`, `requirements`, and `readme` are ignored and `tags` is misplaced;
- `claude --plugin-dir <clean-copy> plugin list` says the plugin failed to load for that manifest error, yet the command exits 0;
- `plugin list --json` makes the false green machine-visible: exit 0 accompanies `enabled: false` and a non-empty `errors` array;
- `.claude-plugin/default-settings.json` contains one `PreCommit` hook, but current native plugin documentation recognizes `hooks/hooks.json` or an inline manifest `hooks` field, and `PreCommit` is not in the current lifecycle vocabulary;
- the active `agents/` and `skills/` roots pass native validation, while the live `commands/` root fails strict validation when a generated session Markdown file appears below it because Claude Code auto-discovers the nested file as a command.

This is the clearest end-to-end subject mismatch in the audit: repository validators reason about a component set that the native platform currently refuses to load, and even the native list command needs an output/inventory assertion because its exit status is not a load verdict.

### P0 — install and deploy can print success over enforcement failure

- `install.sh` treats several hook/library/config/settings and registration failures as warnings, while its completion criterion excludes the full hook runtime.
- [`scripts/deploy-all.sh`](../../scripts/deploy-all.sh) proceeds when the provenance verifier is missing or breaks, swallows settings-sync errors, and local validation accumulates errors without a final non-zero exit.
- Deploy copies directory trees. The canonical manifest governs installer downloads but not the mandated `deploy-all.sh` path, so an unmanifested committed file can still deploy.
- Post-deploy checks prove selected files parse and an event-count floor is met. They do not prove the exact intended profile or route graph.

### P0 — generated settings and runtime health disagree

The generator emits global `~/.claude/...` hook commands; the path health validator rejects those paths. The live global settings have 17 bindings and the project settings have 8; all 8 project bindings overlap global ownership by event, matcher, and hook filename, yet the duplicate audit returns zero because it compares project `settings.json` only with a missing `settings.local.json`.

The generator owns one global settings surface. Six other settings profiles are hand-maintained. Several sidecars say `utility` while those hooks are directly registered. Event vocabularies differ between schema, reachability, and plugin default settings. The result is not one configurable system; it is several partial models.

### P1 — passing validators have narrower subjects than their names

- `generate_hook_config.py --check` does not require `invoked_by`/`proves`, checks one settings projection, and reports hook/sidecar orphans without failing.
- `scripts/validate_manifest.py` checks two critical hooks, settings references, three commands, and a substring, then prints “all validations.”
- `scripts/validate_structure.py` prints “No duplicates” after comparing only top-level documentation basenames between two directories.
- Documentation congruence passes despite the malformed `PROJECT.md` metadata line, stale goal status, and conflicting hook counts.
- `deploy_state.py check` proves bytes match the recorded old stamp; it does not prove the stamp matches intended source `HEAD`.

Every result label must name its actual subject. A broad PASS from a narrow or empty subject is a defect.

### P1 — canonical ownership is split

- `plugins/autonomous-dev/config/install_manifest.json` is canonical; `plugins/autonomous-dev/install_manifest.json` is an older, materially different production-shaped file used by tests.
- Active pre-commit executes five validators under `hooks/archived/`, contradicting the archive rule.
- Agent files, `agent_invoker.py`, `skill_loader.py`, docs, and command prose maintain overlapping identities. Live registry tests find four ghost agents and two missing active agents; the shipped `invoke_agent.py planner` fails at construction.
- `component_classifications.json` is disconnected, last reviewed 2026-03-28, and omits seven active hooks.
- `audit_inventory.py`, `mechanism_view.py`, and the untracked mechanism ledger each enumerate a different corpus. The audit scripts write artifacts as a side effect of ordinary invocation; `--help` is not read-only.
- Hook counts disagree across the architecture overview, README, and hook registry.

### P1 — proof is useful but not load-bearing

- Local proof-of-block is currently 8/8, but CI allows its non-zero exit and the tracked baseline has seven scenarios.
- The scenario list is hand-selected; it does not derive a denominator from refusal sites/hard gates.
- The source reachability ratchet passes and pins 4 hooks plus 98 libraries, but it lives inside a test module, covers only hooks/libs, exceeds the test budget alone, and runs downstream of failing smoke.
- `PreToolUseWrite-protect-sensitive.proof.md` carries a current `Q2 ... YES` heading and a later appended `MCP COVERAGE IS BROKEN` arm in the same artifact. A proof store that does not recompute and replace its top-level verdict after new evidence can present failed operating effectiveness as current success.
- The mutation witness intentionally has no producer and is shipped nowhere.
- The second plugin test suite collects 500 tests with three import errors and is selected by neither root pytest nor CI.
- Tests do not ship to consumers, and no compact consumer proof bundle replaces them.

### P2 — library topology is part of the control failure

The live library corpus is 238 non-`__init__` modules and 124,209 physical lines. The current reachability ratchet classifies 140 `REACHED` and 98 `UNKNOWN`; the seven library-ratchet tests pass, which proves the baseline is internally consistent, not that the 98 have a production purpose. Ruff reports 387 findings across 120 library files, including 13 `F821` undefined-name findings. A name-based AST reconnaissance finds 11 atomic-write definitions across ten files and 20 settings/config load/merge/write/generate/validate definitions across 12 files; the latter is a candidate set requiring semantic characterization, not proof that all 20 are duplicates.

The seven tracked settings source surfaces contain 73 hook registration declarations but only 38 unique exact `(event, matcher, command)` bindings; ten bindings are repeated across surfaces, producing 35 repeated declarations. Some repetition is valid in generated profile outputs, but it is invalid as independently maintained source. Profiles must contain membership differences only, with registrations compiled from one owner.

`unified_pre_tool.py` is 10,013 lines and roughly 51 checks behind one timeout. It should become a thin lifecycle adapter around cohesive deterministic decisions, but only after its observed input→decision behavior and side effects are covered. The library corpus may be comprehensively refactored; unmeasured movement is still not simplification because it preserves the controls while increasing the number of ways they can go silent.

## Design choices

### Option A — strengthen each existing validator independently

**Benefit:** smallest local diffs.

**Cost:** preserves separate enumerators, status vocabularies, settings models, and deploy subjects; the next artifact class requires another cross-product of patches.

**Decision:** reject. This is the pattern producing the current false-green state.

### Option B — create one hand-maintained repository-wide mechanism ledger

**Benefit:** easy to read and query.

**Cost:** becomes another peer source of truth, duplicates paths and routes, and is stale unless the thing it is meant to verify already works. The three current inventory artifacts demonstrate the failure.

**Decision:** reject.

### Option C — compile a graph from existing owners and make every gate consume it

**Benefit:** inventory comes from files, hook intent from sidecars, agent/command identity from frontmatter, shipping from the canonical manifest, routes from real registrations/imports/dispatches, and proof from executed receipts. Settings, registries, counts, and deployment sets are derived projections.

**Cost:** one new shared kernel and migration work across existing callers; static analysis must preserve `UNKNOWN` rather than overclaim dynamic absence.

**Decision:** choose. It extends the ratchet and active goal’s intended carriers instead of inventing another authority.

## Target architecture

```text
Canonical declarations                     Observed evidence
----------------------                     -----------------
filesystem inventory                       collected test nodes
hook sidecars                              subprocess decisions/exits
proof scenario declarations                stable proof IDs/results
agent + command frontmatter                dynamic import/execution trace
one canonical manifest                     installed file digests
one expiring UNKNOWN baseline              runtime settings/profile
             \                                  /
              \                                /
               v                              v
                 artifact_contract (pure graph)
                  inventory -> edges -> status
                     |          |         |
                     v          v         v
               generated     gate exit   receipt
               projections   semantics   subject digest
                     |          |         |
           settings/manifest  CI/commit  deploy/health
           registry/counts    install    consumer proof
```

### Canonical owners

| Fact | Owner | Derived consumers |
|---|---|---|
| Project mission, scope, invariants, Q1/Q2 | `PROJECT.md` | alignment gate; plan scope |
| Control identity/type/applicability/failure semantics | metadata beside the canonical hook/command/agent/config owner | compiled control graph; enforcement adapters; generated control matrix |
| External-standard interpretation | versioned `standard_refs` on the owning control declaration | generated crosswalk and gap report; never an automatic compliance verdict |
| Active-goal milestones/status | structured frontmatter in the goal document | short generated PROJECT banner; status output |
| Hook identity, lifecycle, applicability | `.hook.json` sidecar | all settings profiles; manifest; hook registry |
| Native plugin hook carrier | generated `hooks/hooks.json` projection from sidecars for the `plugin-native` profile | Claude Code plugin loader; native canary |
| Hook/library invocation route | graph walker output | generated `invoked_by`; reachability ratchet |
| Hook-level proof ID | the proof scenario that actually drives the hook | generated sidecar `proves` aggregate; artifact-level results |
| Refusing/observing decision identity | a later static `CONTROL_CONTRACTS` literal beside the owning function/module | decision denominator/results |
| Agent identity, model, tools, skills | agent frontmatter | runtime discovery; agent docs |
| Command identity and visibility | command frontmatter, with one visibility key | command catalogue; runtime discovery |
| Artifact shipping | canonical config manifest generated from inventory/declarations | install, deploy, uninstall, provenance |
| Current accepted unknowns | one path-plus-source/sidecar-digest baseline with rationale and expiry | pre-commit and CI ratchets |
| Runtime truth | fresh recomputation plus an HMAC-signed receipt for a named target/profile | health/status and consumer evidence |
| Counts and registries | generated from the graph | architecture/registry documentation |
| Decision-relevant claim kind and currency | structured metadata or a generated block beside the canonical owning fact; measured claims point to subject-bound receipts and historical claims are explicitly non-current | alignment input; status; documentation projections; currency checks |

Intentional fail-safe duplication remains where it has a proved parity check, such as `hard_floor_hooks.json` plus fallback constants. A compatibility shim may temporarily exist, but it must identify its canonical target and have a deletion milestone.

For Slice 1, sidecar `proves` is generated from the existing proof scenario declarations and the hook subprocess path each scenario actually launches; it is never a second hand-maintained list. Sidecars not reached by a collected scenario remain an exact legacy proof-gap pin. Decision-level coverage is explicitly deferred. When that roadmap is adopted, `CONTROL_CONTRACTS` is a data-only module literal parsed statically rather than imported into hook execution; each entry has `id`, `owner_symbol`, and `behavior` (`refuser` or `observer`), and proof scenarios reference that ID. The checker verifies that `owner_symbol` exists and every referenced scenario was collected.

Slice 1 introduces only the `plugin-native` projection needed for native loading and the chain canary; it is generated directly from sidecar registrations, uses `${CLAUDE_PLUGIN_ROOT}` paths, and is compared with the existing settings projection. `.claude-plugin/default-settings.json` is retired as a hook carrier because it is not the native hook location and contains the unsupported `PreCommit` event. When the remaining settings work is later adopted, profile differences live in one named file, `plugins/autonomous-dev/config/hook_profiles.json`. Precedence is: sidecar registration → inherited base profile → profile-local include/exclude by stable hook ID → preservation of user-owned non-`hooks` settings keys. An overlay cannot alter event, matcher, command, timeout, or scope; those stay sidecar-owned. A normalized binding owned by both global and project scope is invalid.

### Artifact states

Every in-scope functional artifact receives exactly one state per dimension:

- **Connectivity:** `CONNECTED`, `UNKNOWN_PINNED`, `DISCONNECTED`, `NOT_APPLICABLE`.
- **Behavior:** `PROVEN`, `UNPROVEN_PINNED`, `FAILED`, `NOT_APPLICABLE`.
- **Shipping:** `SOURCE_ONLY`, `DECLARED`, `STAGED`, `INSTALLED`, `DIVERGED`.
- **Runtime:** `CURRENT`, `BEHIND`, `DIRTY_IDENTIFIED`, `UNVERIFIED`.
- **Currency:** `CURRENT`, `BEHIND`, `STALE`, `UNVERIFIED`, `CONFLICTED`, `HISTORICAL`.

`UNKNOWN` is not “dead,” `BEHIND` is not “corrupt,” and neither is PASS. Existing unknowns may be pinned; new or expanded unknowns refuse. Exemptions require path identity, source/sidecar digest, reason, owner, added date, review/expiry date, and an explicit dimension. Counts alone are not baselines, and editing a pinned artifact invalidates its pin.

### Gate semantics

The shared CLI returns:

| Exit | Meaning | Gate behavior |
|---:|---|---|
| 0 | Non-empty declared subject checked; no failure and no baseline growth | permit |
| 1 | Contract violation or ratchet growth | refuse |
| 2 | Instrument/configuration error; subject could not be evaluated | refuse |
| 3 | Explicitly not applicable for this named target | permit only when the caller requested that target and records N/A |

Every result includes `subject_kind`, `subject_count`, exact paths/IDs, source tree/commit digest, profile, evaluator version, observed outcome, and—when the result can be reused—`observed_at`, dependency identities, and expiry/invalidation cause. “No files found,” parser failure, collection error, missing validator, stale baseline, empty protected domain, or a current claim whose subject cannot be identified are exit 2, never success; a changed dependency, expired claim, or non-generated derived projection is exit 1.

### Kernel boundary and reuse

`artifact_contract/` is not a new orchestrator. It defines immutable `ArtifactRecord`, `RouteEdge`, `ProofRef`, and `Finding` values plus pure projections over caller-supplied paths/data. It does not write files, invoke pytest, deploy, sign, discover the current working directory, or own profile/deployment policy. Its `__init__.py` exposes the deliberately small contract surface; inventory, route, evaluation, and currency implementations live in cohesive internal modules so the first shared kernel does not become a new 3,000-line library. The CLI performs I/O explicitly and existing callers keep orchestration until their bounded context is migrated.

Slice 1 moves, without semantic redesign, these proven functions from `test_hook_reachability_ratchet.py`: `_resolve_importers`, `_utility_route_is_grounded`, `unreachable_refusers`, `library_reachability`, and `unreached_library_modules`, together with the existing refusal-evidence helpers they already import (`_iter_hook_files`, `_python_refusal_evidence`, `_shell_refusal_evidence`). The old test imports the production functions after extraction and retains every premise/negative-control case.

Before their owning bounded context is migrated, later deployment work must delegate rather than duplicate. These are temporary proved owners, not protected module identities; Phase 6 may move them behind the target packages only with the same caller, behavior, and fault-parity transaction:

- manifest path safety remains in `install.py:validate_manifest_target`, `validate_manifest_file_path`, and `assert_contained`;
- file identity remains in `deploy_state.py:digest_file`, `digest_entry`, `digest_tree`, `target_only_files`, and `unsafe_digest_keys`;
- freshness extends `_resolve_source_for_check`/`cmd_check`; deploy permission remains `cmd_gate`; stamping remains `cmd_stamp`;
- staging starts from `Installer.download_to_temp`, but its per-file `commit_from_temp` is not called atomic at tree scope.

Route witness selection is deterministic: choose the shortest grounded path, then sort ties by normalized POSIX path sequence, source line, and edge kind. The complete edge set is retained in JSON; `invoked_by` renders only the canonical witness. Changing traversal order cannot change the selected witness.

### Library replacement authority and target topology

The user has explicitly authorized a comprehensive library refactor. The compatibility requirement is **observable contract, not existing module topology**. A contract is preserved only when a grounded production caller or durable persisted subject depends on it: Claude lifecycle input/output and timing, CLI argv/exit/JSON, prompt or script imports, serialized state schema and ownership, settings/manifest projection bytes, decision reason IDs, telemetry/receipt fields, and documented public extension points with a proved consumer. An uncalled class, private helper, file name, fallback branch, or test-only API is not retained merely because it exists.

The target is a small dependency DAG of bounded contexts, not a flat collection of 238 peer modules and not a new `utils.py`:

| Boundary | Sole responsibility | Must not own |
|---|---|---|
| `artifact_contract/` | immutable graph records, inventory/route derivation, status and currency evaluation | filesystem writes, subprocesses, deployment, lifecycle output |
| `state/` | scoped repo/session/run identity, canonical paths, locking, atomic persistence, canonical payload signing | workflow policy, settings generation, hook decisions |
| `runtime/` | Claude lifecycle payload normalization, event dispatch, decision envelope, telemetry emission | duplicated state algorithms or control policy |
| `workflow/` | eight-step pipeline state transitions, mode rules, agent completion and recovery | filesystem algorithms, settings rendering, transport |
| `projections/` | compile sidecars/frontmatter/profile overlays into settings, manifests, registries, and generated docs | runtime decisions or independent facts |
| `delivery/` | checked subprocess/SSH contract, staging, install, promote, rollback, postflight | control evaluation or hand-maintained inventory |
| `evidence/` | proof execution, traces, mutation witnesses, receipts and expiry | policy authority or generated settings ownership |

These are responsibility constraints, not a mandate to create seven packages immediately. Phase 6 begins with an ADR backed by the live import/call/side-effect graph and may merge adjacent boundaries when their dependency direction remains clear. It may not create a generic catch-all, a second state owner, or a façade containing business logic. Dependencies point toward pure contracts and primitives; cycles refuse.

Recurring mechanisms become typed policies over one implementation:

- one atomic persistence algorithm; JSON/text/domain writers are thin encoders that pass explicit mode, durability, and replacement policy rather than reimplementing temp-file cleanup and rename;
- one session/run identity service with explicit resolution policies, so the current affine and activity-log behaviors are named modes rather than sibling resolver algorithms;
- one settings/manifest compiler; profile files contain stable-ID membership overlays only, and repeated registrations exist only as generated outputs;
- one transport-independent tool-effect and target API backed by native/MCP tool schemas plus explicit capability policy; its result distinguishes `EXACT`, `BROAD`, `NON_FILESYSTEM`, and `UNKNOWN` with certainty and domain, hooks never read `file_path`, `notebook_path`, `relative_path`, or `path` independently, and a missing target can never collapse those four meanings into an accidental allow;
- one checked process runner for local and remote execution; callers supply argv, cwd, environment allowlist, timeout, and expected result;
- one decision/refusal envelope and one receipt/signing implementation; observers and refusers vary by typed decision, not by emission plumbing.

Control placement follows a platform-first rule:

| Control shape | Owner | Evidence boundary |
|---|---|---|
| Static built-in file-tool path deny/ask | Claude Code `permissions.deny`/`permissions.ask`, generated from canonical policy | native settings validation plus real permitted/refused path probes; this removes shell parse, timeout, and output-envelope failure modes but is not called infallible |
| Whole MCP server/tool deny/ask | native MCP permission rule where tool-name granularity is sufficient | native permission resolution for the exact server/tool ID |
| MCP argument-sensitive path/content, pipeline/session state, or other dynamic rule | thin `PreToolUse` adapter over the canonical typed effect/target classifier and pure control | live MCP schema → `EXACT`/`BROAD`/`NON_FILESYSTEM`/`UNKNOWN` disposition → permit/refuse/ask result, including read-only, persisted-state, pathless, and unknown-tool controls |
| Telemetry for a native decision | observer path that cannot weaken the native decision | attempted subject and eventual outcome are recorded separately; Claude Code 2.1.236 `PermissionDenied` is **not** credited because official docs say it fires only for auto-mode classifier denials, not deny rules, manual denial, or PreToolUse refusal |
| Human escalation text | `PreToolUse` `ask` only when a custom user-visible explanation is required | current docs state `permissionDecisionReason` for `ask` is shown to the user, not Claude; model context requires a separately proved `additionalContext` path and must not be inferred |

The current sensitive-path hook is therefore not patched by adding `relative_path`. That would repeat the enumerate-the-members defect and would over-block read-only Serena calls that carry the same key. Its replacement consumes one typed classification: `EXACT` filesystem targets evaluate policy, `BROAD` filesystem writers and `UNKNOWN` MCP effects ask or deny according to policy, and `NON_FILESYSTEM` persisted-state writers follow an explicit separate policy. Static built-in denials migrate to native rules only after a case-sensitive/gitignore-versus-current-case-insensitive-regex truth table proves equivalence; their telemetry becomes subordinate observation rather than a second enforcing decision. A generated applicability matrix names the sole enforcing scope for self-maintenance, consumer-global, and isolated plugin-native execution, and source-versus-installed selection is tested rather than inferred.

Every replacement slice follows the same transaction:

1. Derive its grounded callers, persisted schemas, side effects, failure semantics, and current source/test/doc owners from the graph; unknown dynamic callers remain explicit.
2. Land a shipped AST/schema ratchet for the recurring decision before migration, with a non-empty denominator and watched permit, refuse, and bypass-resistance controls. Pin the exact legacy sites; the pin may only shrink.
3. Characterize the old boundary with contract, property, fault, and real adapter tests. Get the selected suite green before structural movement.
4. Introduce the new bounded implementation behind the smallest seam; migrate one vertical caller path from declaration through runtime effect and receipt.
5. Re-run behavior and provenance comparisons against the same subject. Refactor-only commits do not intentionally change outputs, and intentional behavior changes are separate commits with their own policy/test/doc transaction.
6. Repoint every grounded caller and delete the old implementation in the same changeset. A compatibility façade is allowed for at most one release only when a proved external caller requires it; it contains imports/argument translation only, has a deletion milestone, and new code may not import it.
7. Lower duplicate-site, unknown-route, lint-debt, module/line, cycle, and compatibility ceilings in that changeset. A slice that adds a seam without deleting or scheduling its superseded path has not completed.

A whole bounded context may therefore be rewritten rather than mechanically extracted, but an all-libraries big bang is rejected: it removes the ability to attribute which behavior, state, or proof changed. The full refactor is the program; a behavior-preserving vertical slice is the unit of review, rollback, and proof.

Cross-process execution tracing is not assumed in Slice 1. Before library Q2 inheritance can become required, a bounded spike must demonstrate `coverage.py` subprocess collection using explicit `COVERAGE_PROCESS_START` and parallel data files against the real proof runner. If it cannot preserve `cwd`, environment, argv, and child data reliably, affected libraries stay `UNPROVEN_PINNED`; the plan does not invent a positive result.

Legacy route pins and proof-gap pins are sorted by normalized path and split into deterministic batches of at most 20. Batch 1 is reviewed within 14 days of Slice 1 adoption; each subsequent batch is due seven days after the prior batch. Available per-path rationale from the current ratchet is preserved. Where the old pin has no individual rationale, use the truthful shared migration reason: `migrated from the 2026-09-06 ratchet; no executable route/proof found in the enumerated 1A corpus; not a dead-code determination`. `owner: unassigned-legacy` is allowed only until that pin's batch review; new pins may not use it. Expiry is universal: an expired pin is exit 1 in every evaluator mode. The only resolution is connect, prove, delete, assign/review, or an explicit user-authorized baseline renewal recorded through `/implement`; there is no remediation-mode bypass.

### State integrity

Fresh evaluation, not a receipt, decides CI/commit/install permission. Source declarations and the baseline are reviewed git content. Any dynamic state that can permit a later operation—proof-age receipt, deployment transaction journal, or installed verification receipt—must be HMAC-signed and fail closed per INV-7.

The initial implementation reuses the secret-file and constant-time comparison pattern in `pipeline_state.py:_compute_state_hmac`, `sign_state`, and `verify_state_hmac`, but does not reuse their legacy acceptance semantics: `verify_state_hmac` currently accepts a missing HMAC and may accept stale invalid state. Extract a purpose-bound canonical-payload primitive (`sign_payload`/`verify_payload_hmac`) behind that current import seam, make existing pipeline signing delegate without changing its compatibility behavior, and require strict mode for artifact/deploy state: missing key, missing signature, invalid signature, unknown schema, or stale receipt refuses. Phase 6 moves the primitive and its callers into `state/` and deletes the old seam once parity is proved. Canonical bytes are UTF-8 JSON with sorted keys and separators `(',', ':')`, computed after removing `payload_sha256` and `hmac`; `payload_sha256` is SHA-256 over those bytes, and the HMAC covers the same bytes plus the purpose binding. The payload fields include purpose, target, profile, source identity, evaluator version, timestamp, and expiry.

Persistent installed receipts use a target-local 0600 secret at `.claude/local/artifact-contract.secret`, created once and excluded from manifest/deploy replacement; global layout uses the analogous `~/.claude/local/` path. A missing or unreadable key makes the receipt unverifiable and forces fresh evaluation—it never permits. CI does not trust persisted receipts at all; it recomputes the subject in the clean workspace.

### Q1 route rules by artifact class

| Class | Grounded entrypoint or edge |
|---|---|
| Plugin | native-valid manifest/marketplace entry plus a successful clean-source and manifest-only installed load whose reported component inventory matches the parsed graph |
| Hook | lifecycle binding in exactly one applicable settings scope, or a transitive real importer that terminates at a grounded entrypoint |
| Library | import/execution chain from grounded hook, command dispatcher, script, CI job, or git hook; dynamic routes remain `UNKNOWN` until traced or declared with a verified loader |
| Command | native-discovered user-facing plugin command plus a real user expansion or explicit invocation from another grounded command |
| Skill | native-discovered `SKILL.md` plus a real direct/model-selected invocation; a reference from agent frontmatter is only a declared edge until the agent loads it |
| Agent | dispatch edge parsed from grounded command/coordinator plus runtime agent discovery from its frontmatter |
| Script | named CI/git/deploy/command caller, or explicit user-facing entrypoint with a smoke invocation |
| Config/template | a grounded reader plus an effect proof showing a controlled mutation changes the consumer result |
| Test | collected by one authoritative, named test tier with zero collection errors and a non-zero pinned floor |
| CI workflow/job | actionlint-valid event/job/step DAG from a relevant path trigger through an independent required job and required summary, followed by an observed run for the exact commit |
| Deployed file | exact canonical-manifest member, mapped to one destination, present with the expected digest |

Tests and prose mentions never establish production reachability.

### Q2 proof rules

- Plugin discovery proof requires native strict validation and a successful inventory assertion from clean source and installed layouts; process exit alone is insufficient.
- A refusing control needs real **refuse** and **permit** observations; dependency-fault behavior is a separate required arm when the design claims fail-closed recovery.
- An observer needs an input that emits its documented receipt and a negative input that does not.
- A library may inherit a proof only when dynamic tracing shows the real proof entrypoint loaded/executed it; a unit import alone is not enough.
- A command/agent proof drives the actual dispatch boundary and observes completion/refusal state, not just frontmatter parsing.
- Config proof mutates a temporary copy and proves the real consumer changes; schema validity alone is not behavioral proof.
- Test proof binds changed semantic claims to mutation witnesses. Start with changed tests; expand out of the commit path only after measured runtime permits.
- Consumer proof is a compact shipped runner plus declarations/fixtures, not the entire repository test tree.

## Implementation sequence

Phase 0 is a governance disposition and stop. If the user then adopts this successor, create the digest-bound program tracker, reconcile #1673/#1503/#1588 against S0-1 through S0-7, and run S0 to harden and deploy the partial source repair before the Slice 1 portions of Phases 1–2: 1A introduces approved governance/native source changes while keeping the new evaluator report-only, then 1B may make that evaluator required. Before each later phase, reconcile that phase's issue/acceptance-criteria cluster; Phases 3–7 remain a deferred roadmap and each needs a fresh scope check after prior-phase evidence exists.

### Phase 0 — record the abort, then stop

**Goal:** stop reporting an active/on-track system when the stated abort has fired.

1. Mark the current goal `ABORTED` in its existing status text, preserving its evidence, dates, and Q1/Q2 definitions. Do not introduce a new schema, generator input, or machine-consumed artifact before adoption.
2. Stop and request explicit adoption of the successor slice. Do not edit `PROJECT.md` or treat writing or approving this plan as implicit implementation authority.

**Exit criteria:** the old goal is not ACTIVE and no successor implementation has started without an explicit user decision.

### Successor-policy amendment — first Slice 1A changeset after explicit adoption

As the first Slice 1A governance changeset, write a byte-complete typed successor-goal draft as non-authoritative `PROPOSED` content and report its digest. After the user approves those exact bytes through the extended existing alignment approval receipt, `parse_goal_claims(path)` reads the typed fields and `render_project_status(goal_claims)` generates a short PROJECT status/link block; the generated slot cannot activate before approval. This gives slip counts, milestone dates, historical measurements, and operational conclusions one home; removes the refuted conclusion that all 266 >5-second timing rows silently dropped checks; fixes the malformed metadata line; and preserves the existing control/assurance mission. A manual operational narrative in the generated slot is a currency failure. Replace the manual “entry in the appropriate registry doc” part of the Operational wiring rule with the executable artifact/control-graph requirement: canonical declaration, grounded route, proof, manifest membership, and generated documentation projection. This amendment is part of the adopted successor, not pre-adoption goal disposition.

### Phase 1 — Slice 1A: establish native load and extract the contract kernel with report-only evaluator parity

**Goal:** Claude Code accepts the tracked source plugin, and one read-only implementation enumerates files and computes routes.

1. Correct the tracked plugin/marketplace metadata against the installed native schemas. Validate the exact manifests, the whole plugin, and each active component root; relocate or reject non-components under auto-discovered roots.
2. Generate `plugins/autonomous-dev/hooks/hooks.json` from sidecar registrations for a single `plugin-native` profile, using `${CLAUDE_PLUGIN_ROOT}` handler paths and the official event vocabulary. Remove only the `hooks` member from `.claude-plugin/default-settings.json`. Its material `permissions` object is not semantically equal to `templates/settings.default.json`, so Slice 1 preserves those bytes in place as explicitly unsupported/unmeasured legacy data and does not claim another owner; permission ownership/migration remains a Phase 3 decision. A regression test deep-compares the permissions object before/after this slice and refuses accidental deletion or widening.
3. From a clean `git archive HEAD`, require native strict validation; parse `claude --plugin-dir ... plugin list --json` and require the expected ID, `enabled: true`, empty `errors`, and valid version/path; strictly parse `plugin details` and require equality with the graph inventory. Unknown output fields/schema are evaluator error. Record the installed Claude Code version; unsupported versions are `UNMEASURED`, not green.
4. Add checked-in Ruff and ShellCheck policies for Slice 1 production Python/shell. Syntax and Ruff `E9` block universally; new/changed `F821` blocks immediately. The 13 existing `F821` findings are individually pinned by path/rule/source digest, assigned route status and expiry, and cannot grow; all other current Ruff/ShellCheck findings are reported against exact no-growth baselines until their subtraction changesets.
5. Extract the proven AST/shell/frontmatter/settings walk from the test-local ratchet into a pure library.
6. Define the Slice 1 contract inventory for the native plugin/component roots plus hooks and libraries: roots, recursion, extensions, exclusions, archive semantics, and stable path identity. Exhaustive command/agent/skill behavior remains deferred; 1B adds one explicitly non-gating hosted measurement and preserves all unmeasured behavior as pinned debt.
7. Move the current four-hook and 98-library pins into one schema-validated exact-path-and-content-digest baseline without changing their state; preserve adjacent rationales and assign deterministic review batches.
8. Add a thin CLI that emits JSON/text and never writes unless an explicit `generate`/`record` subcommand is used.
9. Repoint the reachability tests to the library and preserve all existing positive/negative controls.
10. Pin actionlint and ShellCheck in the clean-clone job. Extend the existing parsed-workflow tests in `tests/regression/test_ci_workflow_routing.py` and executable-summary mutations in `tests/regression/test_ci_summary_gate.py`; do not add a peer DAG framework. Mutate `needs`, `if`, `continue-on-error`, timeout, required summary membership, empty subjects, and unexpected skips.
11. Run the evaluator in report-only CI and compare exact path sets with the current ratchet.
12. Add the exact Slice 1 currency projection to the same evaluator—no peer doc registry and no prose classifier. Owner schemas deterministically derive IDs from canonical artifact ID plus field pointer/marker for only the successor goal's objective/scope/status, generated PROJECT banner, generated native hook carrier, generated sidecar route/proof fields, and `install_manifest.json#/components/hooks/files`. Extend `record_alignment_verdict()` rather than adding an approval store so the pre-1B user approval binds the exact goal path/digest. The graph resolves direct/transitive dependencies and recomputes currency from current bytes. Required controls cover non-empty enumeration, corrupt/missing metadata, transitive change, unrelated change, dirty same-HEAD bytes, deletion/rename, duplicate authority, unknown/cyclic dependency, state precedence, and ordinary prose outside generated markers.

**Exit criteria:** the clean tracked source is accepted and inventoried by parsed native output; the native hook projection equals sidecar registrations; corrupting either native manifest or hook carrier refuses; old and new walkers return identical covered hook/lib sets; a route deletion refuses; a mention-only edge does not connect; the narrow decision-input currency mutations refuse while historical and unchanged normative controls do not; native/Ruff/actionlint/ShellCheck tool absence refuses; all workflow-DAG mutations refuse; `--help` and `check` leave `git status` byte-for-byte unchanged; fast changed-slice check is under 10s and full graph is under 60s or isolated from the commit path with a measured budget.

### Phase 2 — Slice 1B: activate sidecar and manifest refusal

**Goal:** new work cannot enter the manifest without a route and proof.

1. Extend hook sidecars with required `invoked_by` and `proves`. `invoked_by` is generated and checked against recomputation; `proves` is generated from collected proof scenarios and the hook subprocess path they launch. Empty values are permitted only when path and current source/sidecar digest match an exact migrated proof-gap pin.
2. Use one lifecycle-event vocabulary shared by schema, generator, reachability, native `hooks/hooks.json`, settings projections, and health.
3. Require observer/refuser proof kinds appropriate to the hook. A missing proof ID or proof with no collected scenario refuses.
4. Make the canonical manifest generator reject new/changed hooks with no verified route/proof and reject hook/sidecar orphans.
5. Add a bounded measurement-only canary against a copied synthetic repository with no remote. Run A uses `claude -p --output-format stream-json --include-hook-events --plugin-dir <staged-plugin>` and invokes `/implement --light` for a deterministic sentinel change; Run B directly invokes `architecture-patterns`. The runner uses an explicit `cwd`, timeout, settings file, tool allowlist, strict empty MCP configuration, isolated session/config persistence, exact filesystem-change allowlist, `AUTO_GIT_PUSH=false`, no git remotes, no GitHub/cloud credentials, and refusing stubs for external-mutation CLIs; local commits inside the disposable repository are permitted. Parse the stream, never human text: expanded command, Agent-tool planner dispatch, raw start/finish identity, coordinator-issued synchronous `record_agent_completion`, exact state row, and next ordering-check consumption must agree on the load-bearing branch. Separately attribute the production `SubagentStop` event, `unified_session_tracker` handler, activity record, and idempotent duplicate completion write; hook loss fails only this telemetry branch. Use recorded-stream/parser and deterministic subject mutations for each arrow; do not spend model runs on mutation cases.
6. Change the clean-clone CI job from report-only to required only after exact parity and all deterministic mutations refuse. Record the canary dimension independently as `E2E_PROVEN`, `FAILED`, or `UNMEASURED`; it cannot change the activation decision under INV-8.

**Exit criteria:** all 34 sidecars validate; orphan probes exit non-zero; the four existing unreachable hooks remain explicitly pinned rather than hidden; manifest refusal and required CI both fail for seeded route/proof loss and pass for the unchanged legacy baseline; deterministic activation does not inspect hosted-canary state; any canary result is separately bound to the source digest and truthfully reports `E2E_PROVEN`, `FAILED`, or `UNMEASURED`.

### Deferred roadmap boundary

Everything below is explicitly deferred. Settings consolidation, agent/command registry repair, installation/deployment changes, decision-level proof expansion, test-tree migration, generated documentation, consumer receipts, and hook subtraction must not be bundled into Slice 1. Each later phase begins with a new prior-art check, measured scope, and user-approved `/implement` input.

### Phase 3 — generate all projections and establish single ownership

**Goal:** settings, manifests, registries, and counts cannot drift independently.

1. Introduce `config/hook_profiles.json` with only profile inheritance and stable-ID include/exclude overlays, then generate plugin-default, global, default, granular, batching, strict, and dogfood hook sections from sidecars. Hand-written hook blocks are forbidden; repeated registrations are acceptable only as byte-reproducible projections, never as independent source.
2. Establish `projections/settings.py` as the sole settings compiler API. Characterize the current generator, merger, activator, and sync behavior; migrate callers; then delete their duplicated hook-merge/write logic or leave a one-release import-only façade where a grounded external caller requires it. User-owned non-hook keys are preserved by an explicit delivery adapter, not by a second hook-settings owner.
3. Normalize binding identity as `(hook_id, event, matcher, scope/profile)`. Exactly one scope owns a runtime binding; global/project duplication refuses. Mutating one sidecar or profile membership must deterministically affect every applicable projection and no excluded projection.
4. Add control metadata to existing canonical declarations, not a new ledger: stable `control_id`, stable-clause `policy_refs` (never line-number references), optional versioned `standard_refs`, optional historical issue/commit references, control type, applicability, enforcement points, fail semantics, implementation symbol, and proof IDs. Historical references are provenance only and cannot set current status. Refuse duplicate IDs, unknown or line-number policy refs, and mandatory PROJECT clauses with no enforcing/explicitly advisory disposition.
5. Parse agent and command identity from frontmatter. Retain only operational policy not expressible there in one validated map; repair or remove the shipped broken legacy invoker after resolving its grounded callers.
6. Generate the canonical manifest from the component inventory and verified declarations. Include required plugin metadata and the sidecars needed by installed verification.
7. Migrate every reader of `plugins/autonomous-dev/install_manifest.json` to the canonical path or a temporary fixture, then delete the legacy file. Tests must create stale/alternate manifests under `tmp_path`.
8. Move live validators out of `hooks/archived/`; repoint all production callers. Make an active reference to `archived/` a contract failure.
9. Generate the hook/command/agent registries, volatile architecture counts, and `docs/CONTROL-MATRIX.md`. The matrix traces policy/standard clause → control → enforcement point → Q1 route → Q2 evidence → deployed subject, but never synthesizes “compliant.” Narrative docs link to generated catalogues instead of restating lists.
10. Fold useful classification/exemption fields into canonical declarations/baseline and delete the disconnected component registry and dated mechanism ledgers.
11. Classify maintained documents as `normative`, `derived`, `measured`, `reference`, `working`, `executable`, or `historical` in existing frontmatter or their canonical owner; do not create a second catalogue. Command, agent, skill, and other machine-consumed Markdown is `executable` and follows code/test validation, never narrative-doc handling. A claim enters the denominator only through a schema-valid typed field or generated-block marker with a stable ID; unmarked prose is never interpreted as machine state. Plans, audits, issues, and changelog entries remain searchable history but cannot answer current-status queries.
12. Replace volatile narrative fragments—counts, enabled/blocking/current labels, active-goal detail, deployed versions, and proof summaries—with generated blocks from the graph/receipts. Generated blocks carry owner/dependency/evaluator identities, regenerate in the same change as their source, and refuse hand edits; doc-master never authors them. Static explanatory prose remains human-authored.
13. Before implementation, derive a documentation-impact set from the planned control/behavior IDs and every expected code, test, config, and executable-Markdown change. Recompute it from the final diff and graph. Each changed functional artifact must resolve to affected claim IDs or a rule-backed `NO_DOC_IMPACT`; zero mapping, conflicting mapping, or a test that changes expected behavior without a linked semantic claim is `UNKNOWN` and refuses unless carried by an exact path/content/profile legacy pin that cannot grow.
14. Make doc-master consume that exact impact set plus the existing covers relationships instead of its ad hoc top-level shell scan. Replace the free-form verdict as authority with a schema-valid receipt bound to base/final tree, code/test and dependency digests, affected claim IDs, inspected docs, edits, and per-claim outcomes. `MISSING`, `SHALLOW`, `FAIL`, `DOCS-DRIFT-FOUND`, skipped updates, empty denominators, and subject mismatch refuse; `NO_DOC_IMPACT` requires the evaluator's grounded disposition rather than agent prose.
15. If doc-master changes narrative documentation, rerun the deterministic graph/currency/link checks; if any changed Markdown is executable or contains validated code examples, rerun its owning tests. Any code, test, config, projection, or executable-Markdown remediation after the receipt invalidates it and requires recomputation plus doc-master re-review, capped like spec-validator and failing closed when unresolved.
16. Retire automatic `Last Updated` stamping as a currency signal. A review date may remain provenance, but CURRENT requires regeneration or a valid same-subject receipt.

**Exit criteria:** one canonical manifest identity; every settings surface is reproducible byte-for-byte; zero duplicate control IDs or cross-scope bindings; every mandatory policy clause has an enforced or explicitly advisory/gap disposition; standard mappings name version/clause/evidence without a compliance verdict; zero active archived references; docs count/matrix/status mutation is regenerated or refused; every changed code/test/executable-doc artifact has an exact impact disposition; every active decision claim has a kind and dependency identity; doc-master reports and is bound to the exact final inspected denominator; one graph command replaces three disagreeing audit inventories.

### Phase 4 — make install, deploy, health, and CI consume the same graph

**Goal:** the declared source set is the staged set and the installed set.

1. Make `install.sh`/`install.py` materialize only the canonical computed set, including plugin metadata and sidecars, into a sibling same-filesystem staging root. Hook/lib/config/settings/registration failures are fatal.
2. Make `deploy-all.sh` request the exact manifest file list from `deploy_state.py`/the contract kernel rather than rsyncing whole source directories.
3. Add explicit `stage_manifest_tree()` and `promote_component_dirs()` primitives around the existing installer staging and `FileManager` writes. Promotion moves one managed component directory at a time (`hooks`, `lib`, `config`, and the other declared component roots), recording each boundary in an HMAC-signed `.claude/local/deploy-transaction.json`; on interruption the next run verifies the journal and either restores the saved component directory or completes promotion. Do not call a multi-directory update atomic.
4. Postflight every file and exact settings profile. Replace event-count floors and three-key-file hashes with full expected-set and digest equality.
5. Extend deploy status to report `integrity`, `freshness`, `profile`, and `proof_age` separately. Require an `--expected-source` identity for CURRENT; an older valid stamp reports BEHIND.
6. Make `/health-check`, pre-commit, CI, installer, and deploy call the same contract API with named target/profile modes.
7. Route every local/remote subprocess through one checked launcher contract: argv is an array, `cwd` is the intended source/target root, environment is an explicit allowlist with `CLAUDE_PROJECT_DIR` bound to that root, timeout is explicit, and every return code is consumed. SSH uses one generated `bash -s --` script sent on stdin; a fake-SSH contract test captures exact argv/stdin, `bash -n` validates the payload, and preflight proves remote Python/rsync/tool versions before any target mutation.

**Exit criteria:** adding an unmanifested source file does not deploy and fails the contract; deleting or changing any staged/installed manifest member refuses; a stale but intact runtime reports BEHIND; verifier crash, settings-sync failure, postflight error, remote-tool absence, SSH contract error, or interruption at every promotion boundary produces non-zero/recovery state; a clean-clone install passes without machine-local state.

### Phase 5 — make behavioral proof load-bearing

**Goal:** Q2 is a required relationship, not a sampled report.

1. Enumerate refusal-capable decision sites and hard gates to create the denominator. Map each to a stable proof ID; pin the current unproven set without calling it green.
2. Repair clean-clone scope discovery, update the proof baseline to the current scenario schema, remove `continue-on-error`, and enable the silent-regression ratchet.
3. Resolve the command/skill/agent operating-effectiveness authority before making it load-bearing: use a genuinely local Claude Code-compatible model backend, or obtain explicit user sign-off for an INV-8 architecture delta permitting the first-party hosted canary. Until then, preserve those exact Q2 gaps as `UNPROVEN_PINNED`; hosted measurements may reduce uncertainty but cannot authorize.
4. Add both-arm scenarios in risk order: gates guarding protected writes/deploy/commit first; then observer hooks; commands/skills/agents; config effects. After step 3 is resolved, expand the Slice 1 chained native measurement from one representative path to the complete declared command/skill/agent denominator without weakening its manifest-only install, lifecycle-event, code-effect, or pipeline-transition assertions.
5. Trace which real modules execute during each proof so downstream libraries receive evidence only from a grounded path.
6. Connect the existing mutation witness producer to changed-test claims. Refuse changed tests with no claim/witness unless pinned; keep bounded mutation out of the full corpus until runtime is measured.
7. Merge valid plugin-local tests into the root suite or retire them. There must be one pytest ownership model, zero collection errors, and explicit per-tier non-zero collection floors.
8. Ship a compact proof runner and fixtures to consumer installs; record source/staging/runtime subject digests and both-arm exits.

**Exit criteria:** CI cannot be green over a failed deterministic proof step; report is `PROVEN n / TOTAL n` plus exact pinned backlog; proof removal refuses; empty scenario/test subjects refuse; consumer proof runs against installed bytes and writes a current receipt; command/skill/agent Q2 cannot be declared load-bearing until step 3 has a recorded resolution.

### Phase 6 — replace the library topology and subtract duplication

**Goal:** preserve proved controls while making their implementation small enough to reason about. Existing library files and private APIs are disposable; grounded behavior, state, and evidence contracts are not.

1. Record an ADR for the bounded-context DAG using the live import/call/dynamic-loader/settings/prompt graph. Enumerate each grounded external contract, state schema, side effect, cycle, duplicate owner, test-only API, disconnected artifact, and compatibility-only path. A route classified `UNKNOWN` is investigated or pinned; it is never silently treated as unused.
2. Ship the cross-repo golden-path mechanism from #1597 as library + CLI + per-repo data, and invoke it from the shared contract/health path. Add exact initial detectors for atomic persistence, session/run identity, settings/manifest compilation, checked subprocess execution, state-root resolution, tool-effect/target extraction, and refusal/receipt emission. Every detector has a non-empty real denominator plus watched permit, refuse, negative, and known-bypass controls.
3. Resolve the foundation first: one atomic persistence primitive, one typed identity/path service, one canonical payload/signing primitive, and one checked runner. Preserve distinct semantics as explicit policy values rather than duplicate algorithms. Migrate one production vertical path at a time and lower its exact legacy pin in the same diff.
4. Complete the settings refactor begun in Phase 3: every source surface is generated from sidecars plus profile overlays, all readers consume the compiler API, and old generator/merger/activator merge implementations are deleted. Allocate static built-in path decisions and whole-tool MCP decisions to generated native permission rules; retain only the argument/content/state-dependent adapter controls native rules cannot express. Generated duplication across output profiles does not count as duplicate ownership.
5. Migrate pipeline/agent state into the `workflow/` boundary without altering the eight stages or specialist roster. Consolidate state transitions and completion semantics; remove legacy invocation/workflow branches after proving no grounded caller. Behavior changes discovered during migration are filed and implemented separately from the refactor commit.
6. Turn old validation/audit scripts into logic-free delegates only where a grounded caller requires a compatibility window; otherwise update callers and delete them immediately. Every retained delegate names its canonical target, owner, removal release, and current callers. New code importing a delegate refuses.
7. Resolve the 98-library `UNKNOWN` backlog in deterministic batches: connect a real route, correct the detector with both-arm evidence, merge into its bounded owner, or delete after production-call and runtime-trace review. Documentation and test imports cannot keep a production library alive. Each batch lowers the exact path set, module count, and physical-line baseline in the same change.
8. Characterize `unified_pre_tool.py` from real recent input→decision/side-effect rows, with privacy-safe fixtures and stable reason IDs. Move cohesive pure controls into `runtime/` or their owning bounded context while the lifecycle adapter retains event order, timeout budget, decision envelope, and telemetry. Delete a control only when a proved native/platform control or another proved owner supplies the same effect.
9. Enforce refactor hygiene: selected behavior tests are green before and after; changed library modules have zero Ruff findings; `F821` is zero repo-wide before migrations rely on the affected symbol; no new import cycle, generic `utils` module, fallback algorithm, optional silent dependency, or untyped dict state is introduced.
10. Ratchet the measured outcomes after every slice: production module/line counts, public symbols, import cycles, unknown routes, duplicate recurring-decision sites, compatibility façades, lint findings, state owners, settings owners, and lifecycle-adapter size. No arbitrary target is invented, but every completed slice must reduce at least one burden without growing another or weakening Q1/Q2/provenance.

**Exit criteria:** behavior and failure semantics match the characterization corpus except in separately approved behavior changes; both arms and installed-consumer proofs remain current; the remaining libraries form an acyclic bounded-context graph; one underlying implementation owns each sanctioned recurring mechanism; all hand-written hook settings blocks, duplicate owners, algorithm-bearing compatibility shims, unknown production-purpose modules, and Ruff findings in the remaining library corpus reach zero; `unified_pre_tool.py` is a measured lifecycle adapter rather than a control warehouse. Module and line totals are lower than the recorded 238/124,209 baseline, but no code is deleted merely to hit a number.

### Phase 7 — prove consumers and keep it true

**Goal:** demonstrate the architecture where it is used and make drift self-reporting.

1. Deploy via the mandated zero-cost path only after all local gates pass.
2. Run the same contract and compact proof in at least two existing consumer repos, including one with deliberate `.claude/.bypass` to verify honest `NOT_APPLICABLE/BYPASSED` semantics.
3. Store content-addressed receipts with target/profile/source/proof versions and expiry. Health refuses stale proof where current proof is required.
4. Run the full contract as an independent required CI job on every relevant change; run deeper mutation/consumer checks only on an existing $0 schedule if measured runtime and platform quota permit.
5. Generate an operator report from current receipts. No hand-edited deployment-status prose is allowed in config files.
6. Generate a closure-ready view in `docs/CONTROL-MATRIX.md` from the same receipts: for each policy/control claim, name the exact subject, target/profile, design/operating/deployment dimensions, evidence ID, source digest, and expiry. GitHub issue comments and changelog prose may cite that view, but issue `OPEN`/`CLOSED` state and narrative verbs never set control status. Online issue-reference resolution is advisory under INV-8 and an unavailable or nonexistent reference is reported as archive drift, not converted into a local enforcement dependency.
7. Run the same currency evaluator in two modes: affected-claim validation on every relevant change, and `check --full` over the complete declared typed denominator. Wire that exact command into the named required-CI summary, release, and deploy owners; add a measured $0 periodic cadence only as supplementary detection. The full-state pass reports malformed/unresolvable typed claims as `UNVERIFIED`, tests external/versioned dependencies where local evidence permits, and emits a ranked queue without auto-renewing expiry; it does not attempt to classify arbitrary prose.

**Exit criteria:** source, staged, and installed digests agree on enforced consumers; intentional opt-out is reported distinctly; a consumer-side route or proof mutation is detected without inspecting autonomous-dev source; operational closure claims cite current subject-bound receipts or say `UNMEASURED`; a no-diff full-state run detects a seeded stale claim and produces a stable empty report after correction; no paid or hosted service is load-bearing.

## File-by-file change map

### Goal disposition — before adoption

| Order | File | Action and responsibility |
|---:|---|---|
| 1 | `docs/experiments/GOAL_2026-08-24_enforcement-proven-everywhere.md` | Mark existing status text aborted without changing historical dates or creating a new schema/artifact |

Stop after row 1 until explicit adoption.

### Tracker reconciliation — after adoption and before each phase

| Order | GitHub action | Exit evidence |
|---:|---|---|
| 1 | Create one program tracker referencing the adopted plan commit and digest; list only phase order, current phase issue, and links to plan acceptance IDs | tracker contains no independent policy/acceptance prose and cannot authorize implementation |
| 2 | Update #1673 as S0's canonical issue; append the corrected wiring state and map every checkbox to S0-1 through S0-7; link #1503/#1588 as historical corrections | zero unmapped S0 checkboxes; no duplicate S0 issue |
| 3 | Before each later phase, query open and closed issues plus changelog/commit history, produce the phase crosswalk, and apply one allowed disposition per candidate | every candidate and every checkbox has a disposition; unresolved criteria remain open |
| 4 | At phase completion, update/close only from current subject-bound receipts and the adopted plan decision; record independent/deferred work without closing it | closure comments name plan digest, acceptance IDs, commit, receipt, and any retained residual |

### Successor policy — first Slice 1A changeset after explicit adoption

| Order | File | Action and responsibility |
|---:|---|---|
| 1 | `docs/experiments/GOAL_2026-09-06_repository-integrity-recovery.md` | **CREATE as a non-authoritative typed draft in 1A:** author byte-complete objective/scope, activation/abort rules, milestone observations, and proposed status without a prose parser; report its digest; only an exact-path/digest user approval through the existing alignment owner makes the unchanged bytes authoritative |
| 2 | `PROJECT.md` | Fix metadata; replace duplicated volatile goal status and disproven timing conclusion with a generated/link-only banner from the typed successor goal; preserve the controls-as-code mission while adding claim-kind/currency semantics and replacing manual registry membership with generated declaration/route/proof/shipping traceability |

### Slice 1 — implementation-ready

| Order | File | Action and responsibility | Acceptance criteria |
|---:|---|---|---|
| 1 | `plugins/autonomous-dev/.claude-plugin/plugin.json`, `plugins/autonomous-dev/.claude-plugin/marketplace.json`, `plugins/autonomous-dev/plugin.json`, `plugins/autonomous-dev/.claude-plugin/default-settings.json` | Make native metadata schema-valid; establish native owners versus temporary compatibility projections; remove only the unsupported `hooks` member from `default-settings.json`, deep-compare and retain its unequal permission data as explicitly unowned legacy input until Phase 3; delete the root compatibility `plugin.json` in Phase 3 after its readers migrate | S1-0 |
| 2 | `plugins/autonomous-dev/hooks/hooks.json` | **CREATE, GENERATED:** native `plugin-native` hook projection from sidecars with official events and `${CLAUDE_PLUGIN_ROOT}` handler paths | S1-0, S1-3 |
| 3 | `plugins/autonomous-dev/config/static_toolchain.json`, `ruff.toml`, `.shellcheckrc`, `scripts/bootstrap_static_tools.py` | **CREATE/configure:** make `static_toolchain.json` the sole tool version/URL/platform/digest owner for Ruff 0.15.6, actionlint 1.7.12, and ShellCheck 0.11.0; config files own rules only and bootstrap/CI read the lock; one digest-verifying Darwin arm64/Linux amd64 bootstrap; immediate syntax/`E9` and changed-file `F821`; exact no-growth debt pins; skew mutations refuse duplicated literal pins | S1-0, S1-6, S1-7 |
| 4 | `plugins/autonomous-dev/lib/artifact_contract/{__init__.py,models.py,inventory.py,routes.py,evaluate.py,currency.py}` | **CREATE:** small public façade plus cohesive pure implementations for immutable records and inventory/route/baseline/workflow/currency projections; extracted existing walker emits a labelled `legacy-union` parity view plus a target/profile-scoped `plugin-native` authority view; add `parse_goal_claims(path)` and a bounded structured decision-input projection, not a prose classifier | S1-1, S1-2, S1-6, S1-7, S1-9 |
| 5 | `plugins/autonomous-dev/scripts/check_artifact_contract.py` | **CREATE:** explicit-path evaluator CLI with precise exit/status/currency JSON, strict native-output parser, and explicit `render-project-status` write subcommand backed by pure `render_project_status(goal_claims)`; ordinary `check`/`--help` stay read-only | S1-0, S1-1, S1-5, S1-6, S1-9 |
| 6 | `plugins/autonomous-dev/config/artifact_contract_baseline.json` | **CREATE:** schema, exact path+source/sidecar digest for the labelled `legacy-union` 4-hook/98-library extraction pins and separate target/profile/path/digest pins for any gaps exposed by the `plugin-native` view, remaining hook proof gaps, and non-blocking lint debt; preserved/shared truthful rationale, staggered legacy review batches; no derived counts | S1-2 |
| 7 | `plugins/autonomous-dev/config/hook-metadata.schema.json` and 34 `hooks/*.hook.json` files | Require generated `invoked_by`/`proves`; exact pins may carry empty arrays | S1-3, S1-4 |
| 8 | `scripts/generate_hook_config.py` | Delegate hook inventory/route/proof checks, generate native hook projection, and make hook/sidecar orphans fatal; do not consolidate all settings profiles in Slice 1 | S1-0, S1-3, S1-4 |
| 9 | `plugins/autonomous-dev/config/install_manifest.json` | Include native metadata/hook carrier, evaluator/CLI/baseline, and refuse new/changed nonconforming hook entries | S1-0, S1-4 |
| 10 | `tests/unit/lib/test_artifact_contract.py` | **CREATE:** extracted-walker `legacy-union` parity, independent target/profile-scoped `plugin-native` route view, strict native JSON parsing, structured claim kinds/dependency invalidation, and the sidecar-as-route, optional-template-as-active, unattributed/test-telemetry-as-production, mixed-age, empty/error, and mention-only controls | S1-0, S1-1, S1-2, S1-6, S1-9 |
| 11 | `tests/regression/test_artifact_contract_manifest_gate.py` | **CREATE:** conforming permit plus route/proof/orphan/native-carrier removal refusal | S1-0, S1-3, S1-4 |
| 12 | `tests/integration/test_claude_plugin_native_load.py` | **CREATE:** clean tracked-source strict validation, parsed `plugin list --json`, strict `plugin details` inventory, semantic failure even when native list exits 0, and malformed-manifest/carrier mutations | S1-0, S1-5 |
| 13 | `tests/integration/test_artifact_contract_clean_clone.py` | **CREATE:** tracked-files-only clean-clone subject and evaluator self-bootstrap | S1-1, S1-4, S1-5 |
| 14 | `tests/regression/test_ci_workflow_routing.py`, `tests/regression/test_ci_summary_gate.py` | Extend existing YAML/job-DAG and executable-summary tests for `needs`/`if`/`continue-on-error`/timeout/summary/empty/unexpected-skip mutations | S1-5, S1-7 |
| 15 | `scripts/run_claude_connectivity_canary.py`, `tests/fixtures/claude_connectivity_canary/{PROJECT.md,expected.json,input.txt}` | **CREATE:** at most two hosted measurement runs (one no-remote/no-external-mutation `/implement --light`, one direct skill); explicit cwd/timeout/settings/tools/MCP/session/filesystem isolation; machine-parse native stream records and separately bind synchronous completion/ordering versus asynchronous SubagentStop telemetry, with before/after state/digests | S1-8 |
| 16 | `tests/integration/test_claude_connectivity_canary_contract.py` | **CREATE:** deterministic parser, receipt-schema, digest, stale/mismatch, and per-arrow mutation controls without claiming it ran a model | S1-8 |
| 17 | `tests/regression/test_decision_claim_currency.py` | **CREATE:** exact declared Slice 1 claim IDs; generated PROJECT banner; non-empty/corrupt metadata; transitive/unrelated/dirty-byte/deletion/rename/cycle/duplicate-authority controls; arbitrary generated-block mutation that includes the disproven 266-row conclusion; ordinary prose ignored | S1-9 |
| 18 | `plugins/autonomous-dev/lib/alignment_classifier.py`, `tests/unit/lib/test_alignment_classifier.py` | Extend the existing sole approval writer/receipt with a canonical `approved_subjects` path/digest field; the proposed goal and generated PROJECT block cannot become authoritative before the exact goal digest is recorded, and changed goal objective/scope without matching approval is UNVERIFIED; do not create a second approval store | S1-9 |
| 19 | `.github/actionlint.yaml`, `.github/workflows/ci.yml` | Pin/configure actionlint and ShellCheck; independent native-load plus report-only 1A contract job, then required 1B job only after content-bound goal approval and exact parity; no smoke dependency | S1-0, S1-1, S1-5, S1-7, S1-9 |

The evaluator is added to the manifest in 1A but does not attest itself. The 1B activation test builds a temporary candidate manifest, removes the evaluator route/proof in separate mutations, and requires the already-running 1A evaluator to refuse each candidate before the blocking rule is enabled. This is report-only parity followed by externally observed activation, not a same-process assertion.

### Deferred file families — not Slice 1 scope

| Roadmap phase | Files/families |
|---|---|
| Canonical projections | `config/hook_profiles.json` (**CREATE**), all settings templates, control metadata in existing sidecars/frontmatter, agent/command frontmatter, legacy registries/manifests, generated `docs/CONTROL-MATRIX.md` and other volatile docs |
| Static verification | complete Ruff/ShellCheck debt removal and exhaustive command/skill/agent reference rules beyond the Slice 1 native chain |
| Runtime/deploy | `pipeline_state.py` generic strict signing, `deploy_state.py`, `install.sh`, `install.py`, `deploy-all.sh`, `sync_settings_hooks.py`, `health-check.md` |
| Behavioral proof/test ownership | `proof_of_block.py`, decision-owner `CONTROL_CONTRACTS`, mutation producer/gate, test-master completion, both pytest configurations/trees |
| Library replacement and subtraction | ADR plus shipped golden-path guard; settings/state/identity/process/proof bounded contexts; all live `lib/` callers; live archived validators; old audit scripts; legacy invocation stack; then characterized `unified_pre_tool.py` decisions |

### Slice 1 acceptance criteria

- **S1-0 — native subject:** `claude plugin validate --strict` passes the exact native manifests, whole clean plugin, native hook carrier, and active command/agent/skill roots; parsed `plugin list --json` has the expected ID, `enabled: true`, empty `errors`, and valid version/path; strict `plugin details` equals the parsed inventory; separate manifest/carrier/component-root mutations refuse; native/Ruff/actionlint/ShellCheck absence refuses. The legacy `default-settings.json` hook member is absent, its pre-slice permissions object is byte-for-byte unchanged, and permission ownership is explicitly `UNMEASURED` rather than silently reassigned.
- **S1-1 — parity:** the extracted evaluator's explicitly labelled `legacy-union` view and the existing ratchet emit identical normalized hook/library path sets in a clean clone. This proves extraction equivalence only; the separately emitted target/profile-scoped `plugin-native` view is the sole Slice 1B authority.
- **S1-2 — honest baseline:** the baseline contains exactly the current `legacy-union` four unreachable refusing hooks and 98 UNKNOWN libraries by path and content digest, plus separate target/profile/path/content-digest pins for any additional gap exposed by the `plugin-native` view and path plus sidecar/source digests for the set still lacking a collected hook proof after the existing eight scenarios are mapped in 1A. Before 1B, each newly exposed profile gap is fixed or explicitly pinned; the parity report names both that set and the proof-gap set, count-only matching is forbidden, and any later addition, path substitution, profile substitution, or content change refuses.
- **S1-3 — complete carrier:** all 34 sidecars contain schema-valid `invoked_by` and `proves`; empty values resolve to one exact path-plus-digest legacy pin; hook/sidecar orphans refuse.
- **S1-4 — manifest teeth:** a conforming temporary candidate manifest permits; separately removing a real route and proof refuses; a new nonconforming hook never enters the canonical manifest.
- **S1-5 — required clean-clone signal:** after report-only parity, the contract job has no dependency on smoke and fails the workflow for evaluator error, empty subject, route/proof mutation, or pin growth.
- **S1-6 — bounded/read-only:** `--help` and `check` do not change any repo byte; the required check is under 10s, or Slice 1 does not activate on the commit path.
- **S1-7 — workflow and toolchain semantics:** the sole static-tool lock supplies every tool version/URL/platform/digest to bootstrap and CI, configured Ruff/actionlint/ShellCheck pass, and literal-pin/skew mutations refuse. The existing workflow-routing and summary tests parse the real YAML and refuse each seeded `needs`, `if`, `continue-on-error`, timeout, required-summary, empty-subject, and unexpected-skip mutation.
- **S1-8 — native-chain measurement:** at most two hosted runs per candidate measure (a) `/implement --light` expansion → planner Agent-tool dispatch/start/finish → coordinator synchronous `record_agent_completion` → exact state transition/ordering consumption, with production `SubagentStop` → `unified_session_tracker` → source-attributed telemetry measured as an independent asynchronous branch, and (b) direct `architecture-patterns` invocation for the identical staged-plugin digest. Deterministic/recorded-stream mutations cover every arrow with zero model reruns; suppressing the hook fails telemetry but is not expected to fail the synchronous ordering branch. This dimension is `E2E_PROVEN`, `FAILED`, or `UNMEASURED` and never gates Slice 1B under INV-8.
- **S1-9 — decision-input currency:** the complete denominator is owner-schema-derived IDs for the typed successor-goal objective/scope, milestone observations, derived lifecycle status, generated PROJECT block, generated native hook carrier, generated sidecar route/proof fields, and `install_manifest.json#/components/hooks/files`—nothing discovered from prose and no separate ID list. Every registration/reachability observation binds its exact target/profile, source/config digest, evaluator, and provenance; a utility declaration, optional profile, unattributed/test row, or observation from a different subject age cannot promote the active-profile claim. The normative goal bytes are bound to the existing alignment approval receipt and `render-project-status` is ineligible before that exact approval; observations are measured, status derives from observations plus approved activation/abort rules, and PROJECT derives from status. Same-subject regeneration permits; transitive/dirty/deleted/renamed/unknown/cyclic dependency, normative approval mismatch, corrupt or empty metadata, duplicate authority, expiry, or arbitrary generated-block mutation refuses with the defined primary state and sorted causes. Unrelated changes, unchanged approved normative content, explicitly historical text, and ordinary prose outside generated markers do not false-positive. The 266-row fixture is one arbitrary generated-block mutation, not a hardcoded phrase detector.

## Test and proof plan

### Slice 1 contract kernel

- Native platform: validate exact manifests, native hook carrier, whole clean plugin, and active component roots with the installed Claude Code CLI; parse `plugin list --json` fields and strict `plugin details` inventory, never exit status or text presence alone.
- Static lint: JSON Schema with no optional-dependency fallback, Python AST plus configured Ruff, `bash -n` plus configured ShellCheck, workflow YAML plus pinned actionlint/ShellCheck; `rg` results are never accepted as edges.
- Unit: deterministic hook/library inventory, nested package identity, archive exclusion, sidecar parsing, canonical route selection, and exact baseline matching.
- Property: normalized path/edge ordering is stable across traversal order and cannot collapse distinct package paths.
- Negative controls: prose mention, test-only import, ungrounded importer, utility sidecar treated as a lifecycle route, optional template labelled as the active profile, refusal telemetry with missing/test provenance treated as production reachability, mixed-age observations joined without a common subject digest, empty corpus, parser exception, stale baseline, orphan, and expired exemption.
- Currency controls: enumerate the non-empty typed denominator, regenerate the exact current subject, then independently mutate a direct dependency, transitive dependency, dirty same-HEAD byte, evaluator version, evidence window, expiry, generated block, claim kind, dependency name/path, and authority count. Test that unrelated files preserve the subgraph digest, missing/renamed/deleted/cyclic/unknown dependencies fail closed, simultaneous expiry/digest mismatch reports both causes deterministically, a date-only touch never repairs failure, persisted CURRENT is ignored, historical text never authorizes CURRENT, and ordinary prose is outside the denominator.
- Regression: preserve the labelled `legacy-union` 4-hook/98-library pins exactly and preserve any separate `plugin-native` target/profile pins; a changed path, profile, or content digest—not just a changed count—refuses.
- Workflow: reuse the existing parsed-YAML routing and executable-summary test owners; remove/mutate each job edge and prove the required summary distinguishes failed, unexpectedly skipped, empty, and passed subjects.
- Native chain: run at most two model-backed measurements only on the isolated fixture; separately test its stream parser, receipt schema, stale/digest mismatch, and each arrow's failure classification without a model. Its result changes only the `E2E_PROVEN/FAILED/UNMEASURED` dimension.

### Deferred runtime integration

- Materialize a clean source tree to a temporary installed tree exclusively from the canonical manifest.
- Run native strict validation and semantic plugin inventory against both source and installed layouts; the exact command/agent/skill/hook sets must match the compiled graph.
- Run the graph against source, staging, repo install, and global-layout install; compare identities and declared profile.
- Exercise install/deploy failures: one missing file, one extra file, one changed digest, broken verifier, failed settings sync, wrong profile, duplicate global/project binding.
- Prove `CURRENT` versus `BEHIND` using two real commit identities with identical internal integrity.
- Assert every subprocess's exact argv, `cwd`, environment allowlist, timeout, and consumed return code; use fake SSH to capture argv/stdin, validate the remote script with `bash -n`, and inject interruption after every journaled promotion boundary.

### Deferred behavioral and adversarial proof

- For every block-capable proof ID: bad input refuses; legitimate input permits; claimed fault handling is observed.
- Mutation: remove registration, replace executable call with a mention, remove proof ID, empty scenario generation, skip a test tier, alter installed bytes, and add a second manifest.
- Command/skill/agent: a real Claude Code canary expands the safe command/skill, dispatches the exact active agent, observes its raw start/finish identity, reaches its intended library/control, and ties synchronous coordinator completion/pipeline state to the invoked ID; the separately attributed `SubagentStop` hook branch proves telemetry only, and archived/ghost identities refuse.
- Config: mutate a temporary timeout/profile/permission value and observe the real reader’s result change.
- Audit tools: `--help`, `check`, and failed parsing never modify the repo.
- Documentation transaction: mutate a changed code path, a behavior-defining test, an executable Markdown instruction, and a generated projection independently; require the same graph to name their affected claims or a grounded `NO_DOC_IMPACT`. Empty mapping, doc-master PASS over an omitted claim, `FAIL`/`MISSING`/`SHALLOW`, a skipped update, changed final digest, or remediation after review refuses; a true internal refactor with an unchanged claim subgraph permits without narrative churn. Seed a code-and-test pair that agrees on the same false premise to prove mutual consistency is not documentation currency.

### Deferred library-replacement verification

- Before each slice, collect the exact grounded callers and run their behavior, contract, fault, property, and persisted-schema tests; after the slice, run the identical node IDs against the replacement. Test selection itself is recorded in the change receipt so a narrower after-suite refuses.
- Drive the shipped golden-path detector against the real tree and synthetic violations for every sanctioned recurring mechanism. The current legacy path set is compared by identity, not count; one migrated site requires one same-diff pin deletion.
- Fault atomic persistence at open/write/flush/fsync/replace/chmod/cleanup boundaries and assert old-or-new complete content, permission policy, confinement, and no leaked temp file. Exercise concurrent writers and corrupted/unsigned state.
- Mutate identity policy, state root, settings profile membership, sidecar registration, manifest member, subprocess cwd/env/timeout/return code, refusal envelope, and receipt subject independently; prove the one canonical owner changes the intended consumers and conflicting owners refuse.
- Preserve the sensitive-write witness as a regression over typed outcomes: built-in `Write+file_path` refuses; three live Serena editors with `relative_path` refuse; the same MCP name with only the wrong `file_path` cannot be the sole positive control; a Serena read carrying `relative_path` permits; nested CWD and project-root resolution agree; directory/glob and implicit multi-file writers are `EXACT` or `BROAD` as declared; Serena memory writers are `NON_FILESYSTEM`; a pathless/project-wide writer is `BROAD`; and an unknown `mcp__.*` tool is `UNKNOWN` and cannot silently permit. Fetch live `tools/list`, bind its schema digest to the receipt, and invalidate proof when a registered tool or required/path/content field changes.
- Prove native-versus-hook allocation end to end: first freeze a case-variant/basename/nested-directory/tilde/absolute/directory/glob allow-ask-deny truth table for the current regex control; migrate only rows with equivalent native semantics; a migrated static built-in path still refuses with the custom enforcing hook removed; MCP argument-sensitive refusal still works with no native path claim; telemetry failure cannot permit a native denial; source, installed-global, project, and isolated plugin-native fixtures resolve to the sole expected enforcing owner; a duplicate applicable registration refuses; and an `ask` test distinguishes user-visible `permissionDecisionReason` from model-visible `additionalContext`.
- Compare all seven source-profile projections byte-for-byte, then load a manifest-only staged copy with Claude Code and drive at least one included and one excluded event per profile. Source generation, installed resolution, and runtime firing are separate assertions.
- Run Ruff over every changed library with zero findings, `ast.parse`/compile all remaining library modules, and ratchet repo-wide Ruff findings from the measured 387/120-file baseline with `F821 == 0` before structural migration proceeds. Parse the import graph and fail new cycles or forbidden upward dependencies.
- Record module/line/public-symbol/unknown/duplicate/shim totals before and after each slice. A decrease is supporting evidence only; behavioral equivalence, current proof, and provenance remain the release authority.

### CI topology

Slice 1 adds only `contract-fast`: native validation/load inventory, Ruff/actionlint/ShellCheck, workflow-DAG mutations, graph delta, declaration/schema, manifest refusal, exact baseline, and non-empty subjects. It is report-only in 1A and required in 1B, with no dependency on smoke. The hosted model-backed canary remains a separate optional assurance measurement and is never relabeled as a CI job or activation prerequisite.

The later target topology keeps required jobs independent so one diagnostic tier cannot suppress another:

1. `contract-fast`: native strict plugin/component validation, semantic load inventory, configured Ruff/actionlint, graph delta, declaration/schema, generated projection drift, non-empty subjects.
2. `install-proof`: clean manifest-only materialization, exact settings profile, installed verifier.
3. `behavior-proof`: both-arm proof ratchet and proof denominator.
4. `tests`: unit, integration ceiling, regression, each with collection receipts.
5. `summary`: fails if any required job failed or was unexpectedly skipped.

GenAI checks remain advisory and local/free constraints remain load-bearing. No OpenRouter or hosted judge determines a gate.

The required CI summary reports `deterministic_contract` and `hosted_native_canary` as separate dimensions. A clean CI run may prove the first and report the second `UNMEASURED`; only a current same-digest canary measurement may report full E2E `PROVEN`, and that label never authorizes an enforcing action under INV-8.

## Acceptance criteria

The S1 criteria above are the adoption gate for the implementation-ready slice. The criteria below define the complete recovery program and remain deferred until their phase is separately adopted.

1. An overdue unmet active milestone deterministically exits non-zero or the goal is explicitly recorded `ABORTED`; PROJECT cannot independently claim a different slip/status.
2. Adding a functional artifact with no grounded route refuses before commit and in CI; current exact unknown sets may remain pinned but cannot grow.
3. Adding a block-capable control with no collected both-arm proof refuses; empty generated proof/test subjects fail.
4. All hook profiles are generated from sidecars/overlays; a duplicated global/project binding or utility/lifecycle contradiction refuses.
5. Exactly one production manifest identity exists, and every installer/deployer/uninstaller/test resolves it.
6. Installer and deploy materialize the same computed file set; any missing, extra, changed, colliding, or escaping target refuses.
7. Deployed status reports integrity, freshness, profile, and proof age independently; an old valid stamp is `BEHIND`, not green-current.
8. Pre-commit, CI, health, install, and deploy call the same evaluator; missing evaluator or parser failure is a refusal.
9. Root and plugin-local tests have one authoritative collection model, zero collection errors, and non-zero pinned floors per tier.
10. Hook/command/agent registries and component counts are generated; manual copy drift is rejected or impossible.
11. No active production path imports or executes `archived/` code.
12. Contract check stays under the hook budget; deeper proof reports exact measured duration and does not hide behind `continue-on-error`.
13. The large hook is reduced only after characterization; input→decision/side-effect equivalence and both-arm proofs stay green through every subtraction.
14. At least two consumer installs produce current content-addressed receipts; intentional bypass is reported distinctly and does not masquerade as proof.
15. The final architecture has fewer canonical registries, validators, compatibility files, duplicate bindings, and manual volatile doc claims than the baseline.
16. A clean source plugin and manifest-only installed plugin pass native strict validation and successful `plugin list`, while `plugin details` equals the parsed component inventory; output-level load failure cannot be hidden by exit 0.
17. The chained Claude Code canary measures command/skill expansion → planner dispatch/completion → synchronous coordinator `record_agent_completion` → exact state/ordering consumption, plus a separately attributed production `SubagentStop` telemetry branch; breaking each arrow is detected in its own branch, and the canary becomes load-bearing only on a local backend or after an explicit INV-8 delta.
18. Every mandatory PROJECT clause has a generated disposition to a control and enforcement/evidence route or an explicit advisory/gap classification; no hand-maintained traceability table is authoritative.
19. Every external-standard mapping identifies the exact standard version/clause and evidence IDs, distinguishes `implements`/`supports`/`gap`/`not_applicable`, and never emits a compliance verdict from mapping presence alone.
20. A GitHub issue state or changelog sentence cannot promote a control to `PROVEN`, `ENABLED`, `BLOCKING`, or `CURRENT`; operational closure claims identify the local control/subject receipt and its expiry, while corrected or unresolved historical references remain visibly marked as archive drift.
21. Every schema-declared active claim is normative, derived, measured, or historical and has one stable ID and authority; normative claims bind an explicit human approval reference to content identity, while derived and measured claims identify their dependencies, subject, evaluator, observation, and invalidation/expiry semantics. A `Last Updated` change or persisted CURRENT label cannot make any claim current, and unmarked prose cannot authorize a control decision.
22. Both assurance paths work over the same non-empty typed denominator: an affected direct or transitive source change invalidates or regenerates its dependent claims in the same change, while `check --full` detects seeded stale, missing, renamed, cyclic, unknown, or conflicting claims independently of doc-master and the changed-file list; an unrelated-file negative control remains current.
23. Every changed code, test, config, or executable-Markdown artifact has a final-digest-bound documentation-impact disposition; affected claims are updated/regenerated and re-reviewed in the same change, while a no-impact result names the grounded rule that produced it. Uncovered, empty, stale, failing, skipped, or post-remediation doc results cannot commit, and a full-state pass detects drift that had no local triggering diff.
24. The remaining library tree implements each registered recurring decision once: one underlying atomic persistence algorithm, one typed identity/path service, one settings/manifest compiler, one checked process runner, and one refusal/receipt plumbing path. Domain wrappers contain policy or encoding only; a structurally equivalent second algorithm refuses in source and consumer health checks.
25. The 238-module/124,209-line/98-UNKNOWN/387-Ruff-finding baseline is remeasured by checked-in tools and can only shrink per completed replacement slice. The final remaining library graph has zero unexplained production-purpose modules, zero import cycles, zero Ruff findings, and no logic-bearing compatibility façade; reductions never substitute for both-arm behavior and installed-consumer proof.
26. All seven settings source profiles are projections of sidecars plus `hook_profiles.json`; the measured 73 declarations/38 unique exact bindings cannot be independently edited. A sidecar/profile mutation changes every intended projection, no excluded projection, and the runtime-loaded installed profile; duplicate global/project ownership refuses.
27. No enforcing hook directly selects a transport-specific input key. For every live schema-declared writer the canonical classifier returns `EXACT`, `BROAD`, `NON_FILESYSTEM`, or `UNKNOWN` with domain/certainty and any exact targets; same-key read-only controls remain permitted, while broad and unknown MCP effects cannot silently permit. Schema addition/change invalidates the subject-bound result until classification and both-arm proof are current.
28. Static built-in sensitive-path policy is enforced by generated native permission rules only where a frozen current-versus-native truth table proves equivalent path semantics; hooks own the non-equivalent, dynamic, content/state-dependent, or MCP argument-sensitive decisions. Native refusal, custom decision, and telemetry have separate proof IDs; an applicability matrix yields exactly one enforcing runtime owner; and the proof store cannot retain `PROVEN` after any appended failing arm, owner ambiguity, installed/source mismatch, or changed tool-schema digest.
29. Every phase has one canonical GitHub issue and a plan-digest-bound crosswalk from all candidate issue checkboxes to exact phase acceptance IDs, current proof, retained residual, independent scope, or explicit policy rejection. No overlap closure drops an unresolved criterion, no closed/history item authorizes implementation, and no future-phase criterion blocks an earlier phase.

## Rollout and rollback

### Ratchet rollout

- Start from exact path/ID baselines: 4 unreachable refusing hooks, 98 unknown libraries out of 238 modules/124,209 lines, 11 atomic-write definitions across 10 files, 387 Ruff findings across 120 library files, seven settings surfaces with 73 declarations/38 unique exact bindings, the sensitive-write control's source-only `d90f8539` repair plus two stale installed copies that still reproduce all three MCP false-permits, its ambiguous/fail-open classifier fallback and non-subject-bound proof, current unproven decision sites, and the other measured duplicate/legacy surfaces. Name-based candidate families are reclassified semantically before they become deletion authority.
- New nonconformance refuses immediately. Existing pins are reduced by the same changeset that connects/proves/deletes them.
- Never create a gate that requires fixing the full backlog before it can pass; that guarantees bypass pressure.
- Each phase must delete, delegate, or mark for same-phase deletion at least one superseded mechanism before introducing another durable surface.

### Rollback

- Only the new contract evaluator/CI enforcement is report-only in Slice 1A. Native metadata and content-approved PROJECT/goal changes are ordinary source/governance changes and are not represented as behavior-neutral. Reverting 1B returns the evaluator to report-only 1A; technical removal reverts evaluator, sidecars, manifest subprojection, tests, CI wiring, and baseline against the exact pre-change commit.
- PROJECT/goal rollback is a separate governance operation: present the exact prior goal/PROJECT subject digest for explicit human approval, record it through the same approval owner, then regenerate the banner. A technical rollback cannot silently reinstate prior policy bytes.
- Contract kernel and CLI are additive until all callers agree; old callers remain as thin delegates during one compatibility window.
- Generated settings/manifest changes are reproducible from the previous source commit, so rollback is regeneration from that commit, not hand editing.
- Deployment stages before activation and retains each previous managed component plus its signed transaction journal. Recovery restores or completes the last journaled component before another deploy; it never trusts an unsigned partial receipt.
- Hook subtraction is one coherent decision group per commit. Revert restores both adapter and its generated declarations/proofs together.
- Forward changes may only lower the baseline. An emergency rollback restores code and its previously signed/reviewed baseline as one release unit and reports the larger historical set as `ROLLBACK_BASELINE`; mixing old code with a newer/lower baseline is forbidden. A newly exposed UNKNOWN remains visible in forward development.

## Risks and controls

| Risk | Control |
|---|---|
| Static analysis mistakes dynamic execution for absence | `UNKNOWN`, never `DEAD`; dynamic trace or explicit expiring exemption |
| A mega-registry recreates the problem | generated graph is output, not authority; declarations remain with existing owners |
| A shared kernel becomes a new god library | cohesive package modules, pure records/evaluators, explicit dependency direction, size/cycle/public-surface ratchets, and no orchestration or I/O in `artifact_contract/` |
| Consolidation erases legitimately different semantics | express differences as named typed policies and prove each arm before removing the old implementations; never use a boolean flag pile or an implicit fallback |
| Contract CLI becomes another disconnected file | bootstrap test removes its caller and requires the manifest gate to refuse |
| Commit latency causes bypass | changed-slice <10s; independent full CI; cache keyed by content digest, never by time alone |
| Settings profiles lose intended differences | explicit profile membership/overlays and golden installed-target proofs |
| Native permissions are assumed to cover MCP arguments | native rules own only built-in path patterns or whole MCP tool IDs; argument-sensitive MCP controls stay in the typed adapter and are proved from live `tools/list` schemas |
| A generic path-key extractor blocks MCP reads | consume the typed effect result before target policy; carry a read-only tool with the same `relative_path` key as a permanent negative control |
| Empty targets conflate broad writes, persisted state, and unknown tools | replace boolean-plus-list authority with `EXACT`, `BROAD`, `NON_FILESYSTEM`, and `UNKNOWN`; broad/unknown MCP effects cannot silently permit |
| Regex-to-native migration changes which paths match | freeze current and candidate semantics in a case/path-form truth table; migrate only equivalent rows and treat intentional differences as separately approved policy changes |
| Removing duplicate registration creates a coverage hole | generate an applicability matrix for self-maintenance, consumer-global, project, and isolated plugin-native modes; prove source/installed resolution and exactly one enforcing owner per mode |
| Native enforcement migration silently loses telemetry | enforcement and observation have separate proof IDs; observer failure is visible but cannot alter the native decision, and `PermissionDenied` is not misapplied to deny-rule events it does not receive |
| Fail-closed deploy strands partial installs | validate staging; journaled per-component promotion; signed recovery state; retained previous component trees |
| Proof denominator becomes another hand list | enumerate decision sites/hard-gate declarations; exact pinned unresolved IDs |
| Docs generator erases useful rationale | generate volatile tables only; conceptual narrative has one manual home |
| Claim metadata becomes another stale registry | metadata lives beside the canonical owner or in its subject-bound receipt; the graph is derived, and duplicate claim authority is `CONFLICTED` |
| Currency lint floods the repo and gets disabled | Slice 1 covers only structured decision inputs with seeded negative controls; classify documents before expanding; ordinary narrative requires exact affected-claim evidence rather than keyword-only refusal |
| Documentation enforcement forces meaningless prose churn | require an impact disposition, not a documentation edit: generated and affected claims change atomically, while a graph-grounded `NO_DOC_IMPACT` permits internal refactors without narrative edits |
| Doc-master remains a nondeterministic single point of authority | deterministic graph owns scope and freshness; generators own derived text; doc-master supplies only subject-bound semantic narrative review; missing or conflicting evidence refuses and the full-state pass remains independent |
| A fresh date disguises an obsolete subject | dependency digests invalidate immediately; age is secondary; date-only edits cannot change currency |
| A proof appends a failure but retains an earlier success heading | verdict is regenerated from all current arms and dependency digests; any `FAILED`, stale, or contradictory arm invalidates `PROVEN` before commit/status/deploy |
| “Simplification” removes real enforcement | characterize first; one bounded deletion group; both-arm and consumer replay |
| The authorized full refactor becomes an unauditable big-bang rewrite | ADR plus grounded contract map, guard-before-migration, vertical behavior-preserving slices, separate behavior-change commits, same-diff old-path deletion, and no pipeline/agent redesign |
| Compatibility façades preserve the old architecture indefinitely | only proved external callers justify a façade; it contains no decision/state algorithm, rejects new imports, names a removal release, and is counted by a zero-bound end-state ratchet |
| Native CLI output/schema changes | machine-parse a versioned schema; unknown fields/shapes are exit 2; update compatibility only with a pinned Claude Code version and malformed-output controls |
| Model canary is flaky or mistaken for CI proof | one isolated deterministic fixture, stable lifecycle/edge IDs, no retry-to-green, separate local receipt dimension, and `UNMEASURED/FAILED` rather than fallback |
| Canary performs an external mutation | disposable repo has no remotes; explicit env strips GitHub/cloud credentials, `AUTO_GIT_PUSH=false`, mutation CLIs are refusing stubs, and the test asserts zero outbound side-effect receipts |
| Lint baseline becomes permanent suppression | exact path/rule/source digest, owner and expiry; changed files cannot inherit old pins; counts can only fall |
| A standards crosswalk becomes compliance theatre | versioned clause IDs, explicit `supports` versus `implements`, independent evidence links, visible gaps, generated output, and no aggregate “compliant” state |
| Closed issues/changelog prose recreate a false source of truth | treat history as prior-art index and regression corpus only; generate closure claims from current local receipts; preserve corrections; report unresolved links without making network state a gate |
| Bulk issue cleanup erases residual requirements or becomes the project | reconcile one phase at a time; map every checkbox before closure; keep independent work open; make the local adopted plan/control graph authoritative and the GitHub tracker navigational |

## Explicitly deferred

- Changing the fixed eight-step pipeline or consolidating specialist agents.
- Requiring a hosted/paid LLM for any gate.
- Declaring all 98 unknown libraries dead or fixing the entire corpus in one pass.
- Rewriting all libraries in one changeset. Comprehensive replacement is authorized, but only through the contract-preserving vertical slices in Phase 6.
- Splitting `unified_pre_tool.py` before the contract and characterization corpus are load-bearing.
- A new database, service, dashboard, or general supply-chain attestation framework.
- Adding OPA/Rego or OSCAL as a runtime dependency; the graph may export a compatible view only after a real consumer exists.
- Treating NIST SSDF, SLSA, or another external standard as a normative release gate without a versioned scope/baseline and explicit user sign-off.
- Making the current hosted `claude -p` canary an enforcement dependency without an explicit INV-8 architecture delta; until a local backend exists it is assurance-only.
- Filing one issue per finding. Mechanically enforceable findings become the contract; human decisions stay in this plan/goal record.

## Completion definition

The recovery is complete when a clean clone, a staged install, the repo’s installed copy, and at least two consumer copies all produce the same non-empty artifact/control graph for their declared profile; every mandatory policy clause has a control/gap disposition; every new functional artifact has a grounded route and proof or an expiring pinned exception; every active decision claim has one authority and a current dependency-bound status; design, operating, deployment, and currency dimensions are reported separately; every transport installs exactly the canonical set; and the repository has one fewer mechanism each time a compatibility layer is retired.

At that point “accurate, durable, simple, and consistent” has an executable meaning:

- **accurate:** claims identify and inspect the real subject;
- **durable:** nonconformance growth refuses automatically;
- **simple:** facts have one owner and projections are generated;
- **consistent:** source, CI, staging, installed settings, deployed bytes, proofs, and docs derive from the same graph.

In control-plane terms: policy remains human-legible, controls are executable, enforcement adapters are thin, evidence is subject-bound, assurance is independent, exceptions expire, and standard mappings are generated rather than asserted.

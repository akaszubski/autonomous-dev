# Reference architecture — supplied proposal

Saved: 2026-09-25. Status: external design proposal, not adopted policy or proof
of runtime conformance. The governing [PROJECT.md](../../PROJECT.md) and
[current execution plan](../plans/20260916-workflow-assurance-subtraction.PROPOSED.md)
retain authority. Older sidecar/installer guidance below is preserved as supplied,
not an instruction to reverse the native-plugin consolidation.

Source: user attachment `cf89e6e0-3168-4a00-8fd7-bd7e70edc042/pasted-text.txt`.
Original SHA-256: `1be8c9ae235744a84d65b2b43ebfb69cd758a0b8a6601aff813e347119c2481b`.
The supplied text is preserved below with one final newline added for Markdown;
removing that newline reproduces the original digest. No diagram or linked source
files were included in that text attachment.

<!-- BEGIN VERBATIM SOURCE -->
AUTONOMOUS DEV   /   REFERENCE ARCHITECTURE

Autonomous Dev
Reference Architecture

Executable evidence and bounded authority

A proposed design for autonomous-dev and a concrete extension of the trustworthy AI assurance model.

Agents propose work. The harness controls progression. Observations support claims. Policy determines permission.

Documentation is a pointer to reality. A command, query or test produces an observation of a particular system at a particular time. The observation still needs a valid method, a known target and a justified interpretation.



Logical responsibilities within the existing local harness. The arrows describe information and control, not separate services or a prescribed number of agents.

Architectural commitments

Preserve the eight engineering stages. Apply Ground, Observe, Reconcile, Verify, Warrant and Ratify throughout them.

Separate intended state, documentary assertions and observed behaviour. Keep uncertainty visible.

Require evidence for consequential state changes and scoped authority before executing an action.

Use outcomes to revise claims and improve the system through a controlled learning process.

Workflow and decision gates

The project contract fixes eight stages: alignment, research, plan, acceptance tests, implement, validate, verify and git. This proposal retains that sequence. The six assurance operations describe how decisions are justified inside it. [1]

Engineering stage

Required result before progression

Alignment

An approved task contract: goal, exclusions, target repository, constraints, acceptance criteria and delegated action scope. Conflicting instructions are resolved or escalated.

Research

Relevant sources and permitted observations, with provenance. Unknowns are identified by their effect on the proposed change; evidence gaps become explicit tasks.

Plan

A proposed change linked to requirements, dependencies, observation methods, material failure cases and a verification strategy.

Acceptance tests

Executable acceptance conditions and meaningful failure cases, established before implementation. Missing testability is a visible decision, not an assumed pass.

Implement

A candidate change made within the authorised workspace. The agent cannot issue its own completion evidence or modify the active enforcement policy.

Validate

Local deterministic checks against the candidate. Errors, absent test collection and omitted required checks remain distinct from successful validation.

Verify

An independently assessed evidence bundle for the exact candidate and relevant installed configuration, including limitations and unresolved acceptance conditions.

Git

Only the git operation covered by current authority. Record the resulting commit and invalidate any evidence affected by subsequent mutation.

The assurance operations

Ground identifies entities, terms, requirements and sources. Observe captures permitted system measurements. Reconcile explains differences among intent, documents and observations. Verify checks the claim, its scope and the observation method. Warrant assembles a supported, bounded decision case. Ratify records acceptance under policy or an accountable human decision.

Ratification does not make a claim true. An accepted estimate remains an estimate; a permitted action may still fail. Later execution and deployed outcomes must return as new observations.

Authority comes before action

A task may preauthorise routine reads, edits and tests within a bounded environment. Human approval is needed where policy reserves a decision or the requested scope changes. A warrant alone grants no execution permission. State-changing observations also require authority before they run.

Claim and evidence contracts

Use explicit contracts within existing records. These are required information fields, not a demand for another database or parallel state system. Evidence receipts are issued by a protected runner; claims reference them and retain their reasoning and limitations.

Record element

Minimum information

Claim

Stable ID; proposition; requirement or decision it supports; kind such as intended, document asserted, observed, inferred or estimated; bounded scope.

Target identity

Repository and environment; commit plus candidate content digest; relevant installed artefact and configuration digests. A commit alone is insufficient for a dirty tree.

Observation method

Command, query or probe ID; arguments or redacted argument digest; tool and probe version; actual entry point; target resolved by the runner.

Execution receipt

Run and invocation IDs; start and end times; completion status and exit code; immutable output references and hashes; explicit truncation and collection errors.

Measurement scope

What was inspected; expected and actual scenario or item counts; sampling limits; unavailable targets; known blind spots; probe qualification reference.

Interpretation

Observed outcome; comparison with acceptance criteria; supporting and conflicting evidence; assessor; reason for the claim assessment.

Freshness

Observed time; dependency digests; validity rule; events that invalidate the result. A recent timestamp does not compensate for the wrong target.

Authority and integrity

Task and action IDs; permitted operation, target and limits; policy version; decision issuer and validity; protected authentication of gate records.

Outcome link

Installed or published artefact identity; subsequent operational observation; relevant acceptance decision; any claim or rule revision it causes.

Keep three kinds of status separate

Dimension

Example values and meaning

Claim assessment

Unchecked; supported within scope; contradicted; inconclusive; stale. Evidence can support a narrow claim while leaving a broader one unknown.

Execution status

Succeeded; failed; error; timeout; not run; not enforced. A successful process exit is not itself a successful acceptance result.

Action authority

Pending; authorised; rejected; expired. Authority is bound to the operation and target; it is not a confidence score.

Retain the history when an assessment changes. Use numerical confidence only where a defined population, method and calibration data justify it. Otherwise report the evidence and uncertainty directly.

Authority and execution boundaries

Treat the reasoning context as capable of mistakes and of encountering hostile instructions. It can request an operation and propose a conclusion. The control path independently checks whether the operation and the state transition are permitted.

Boundary

Required behaviour

Agent workspace

Agents may modify the authorised candidate and create proposed records. They cannot replace active policy, access signing secrets, overwrite issued receipts or promote their own judgement into a gate pass.

Execution boundary

Authorise every relevant shell, edit, tool and connector route. Resolve the actual target, constrain credentials and filesystem access, then execute. A command-name filter alone does not provide isolation.

Trusted record path

Capture execution metadata and outputs independently of the agent narrative. Authenticate gate records with a protected key and verify them on every consequential transition.

Verification boundary

Assess the candidate against the task contract and external outcomes. Fresh agent context helps reduce shared assumptions; it does not replace executable checks or make a reviewer infallible.

Promotion boundary

Bind the decision to the candidate and target configuration. Publication, merge, installation and production deployment each require applicable authority; one permission does not imply all the others.

Freshness and failure rules

A changed artefact, relevant configuration, probe or policy invalidates dependent evidence. Reuse is allowed only when its declared validity rule still holds. Recheck identity at the point of use to prevent a verified candidate being replaced before execution.

Missing, corrupt or unauthenticated gate state cannot count as passed. Unknown results block only transitions that depend on them; unrelated authorised investigation may continue. An explicit opt-out must report that enforcement is inactive, subject to any non-optional policy floor.

On interruption, preserve the last confirmed state. Before retrying an action that may have changed the environment, reconcile its outcome using an invocation ID or an external observation. Use bounded retries and escalate unresolved ambiguity instead of repeating a mutation blindly.

Keep gates local and dependable

Mandatory gates must work without a hosted service. Optional model or web assistance can enrich a proposal; unresolved judgement becomes an explicit escalation. Run substantial verification in its engineering stage. A fast hook checks the resulting valid receipt and must not convert a timeout into permission. [1, 2]

A signature establishes integrity under the key boundary, not the truth of an observation. If an agent can read the key or edit the verifier it is currently relying on, the claimed separation has not been achieved.

How a control earns a pass

The project already asks whether a control is connected to a real execution path and whether it behaves correctly. Its enforcement programme also requires the proving mechanism to detect known broken behaviour. These are useful architectural obligations, not documentation checkboxes. [1, 2]

Obligation

Evidence needed

Connected

A supported invocation actually reaches the installed control in the target consumer. A registration entry or a source file alone cannot establish this.

Behaves correctly

The control produces the required allowed and refused outcomes through its real entry point. Inspect the resulting state as well as messages and exit status.

Observer qualified

The same method distinguishes a known working case from a representative broken case. Record which failure classes it can detect and which remain untested.

Worked example for a protected file guard

Requirement: a protected file edit must be refused without the required task authority, and the equivalent authorised edit must work. Run the experiment in a disposable consumer environment so the real enforcement route can be exercised safely.

Ground the requirement. Identify the protected path, supported invocation routes, authority conditions and expected file state. Treat the documentation as the stated contract.

Observe the installation. Resolve the consumer copy, registration and configuration; record their hashes. Confirm which executable is reached by an actual edit attempt.

Reconcile any differences. If the source guard exists but the installed copy is stale, report the mismatch. Do not use a source-only test to clear the consumer.

Verify both outcomes. Run an unauthorised edit and confirm refusal plus an unchanged file. Run the authorised counterpart and confirm the intended edit. Cover additional required routes explicitly.

Qualify the observer. Challenge the same probe with a safely disabled guard and with a guard that refuses every edit. It must detect both defects. New failure classes need further qualification.

Issue a bounded warrant. Report the exact artefact, environment, scenarios and outcomes. The controller permits the next authorised step only while that evidence remains valid.

What the result actually supports

A valid conclusion is that this guard met these acceptance conditions in this consumer configuration. It is not a claim that every action route, consumer or failure mode is safe. Zero collected tests, an empty scenario list, partial output or an unreachable target leave required checks unresolved.

There is no need for an infinite chain of observers. Identify the small trusted runner and state boundary, test them through independent known cases, and retain their limitations as explicit assumptions.

Memory and outcome feedback

Link requirements, artefacts, invocations, observations, claims, decisions and outcomes. Existing local JSON records and indexes can express this logical knowledge graph. Introduce a graph database only where there is a demonstrated need.

Make learning records explain a decision

Record

Example

Treatment

Correction

An architect changes the proposed dependency order.

Capture the original proposal, the change, the project context and who made it.

Rationale

A migration depends on a consumer constraint omitted from the initial model.

Ask why the constraint matters, what evidence supports it and when it would not apply.

Ontology gap

The model has a service entity but no versioned consumer installation.

Add a proposed concept and relationships; revisit claims whose scope depended on the missing distinction.

Candidate rule

Check the target consumer version before proposing this migration.

Label it as a hypothesis with applicability conditions, exceptions, an owner and supporting cases.

Observed outcome

The migration passed in one consumer but failed under another configuration.

Link the result to the exact change and decision. Narrow or contradict the rule where the evidence requires it.

Logs support retrospectives but do not fully capture tacit reasoning. Ask why a correction was made, which alternative was rejected, and what observation would change the decision. Preserve project-specific judgements alongside reusable candidates.

Compare the model with inventories obtained through independent scans or queries. Classify unmatched artefacts and relationships as gaps. An absent ontology entry never proves that a dependency is absent; an absence claim needs a search with known coverage.

Control changes to the system itself

An outcome may update a claim assessment immediately. Changes to prompts, ontology, probes, policy or permissions require versioned review and evaluation before promotion. Strong performance never grants an agent additional permissions automatically.

Evaluate changes on held-out projects and failure cases, with reviewers beyond the original author. Separate training and evaluation examples. When the evaluation method changes, compare against a fixed reference so an easier test cannot masquerade as improvement.

Extend the existing evaluation loop to connect proposed improvements to independent outcomes, checking refusal, coverage and legitimate task completion. [4]

Measure the claims you intend to make

Track verified controls against the declared inventory, coverage gaps, false passes, false refusals, stale-evidence reuse, deployed regressions and cost per verified task. Report denominators and uncertainty; agent completion counts alone are insufficient.

Adoption and acceptance criteria

Adopt through one complete execution path

First, trace one guard in one consumer from task authority to a real action, independent evidence and a state transition. Demonstrate a legitimate pass and meaningful refusals. This establishes whether the current trust boundary is real before expanding the design.

Next, attach the contract fields to existing metadata and state. Generate declarations where possible; require conformance for new or changed controls, pin the known legacy gaps and reduce them progressively. Include consumer installation identity in the proof path. [2]

Then broaden operational outcome capture and the reviewed improvement loop. Expand only where the first path reveals a concrete gap. Do not create parallel orchestration, evidence or policy mechanisms to reproduce capabilities already present.

Minimum conformance suite

Challenge

Required result

Honest success

An authorised action succeeds through the actual installed route; the observed outcome supports the stated acceptance condition.

Missing authority

The same protected action is refused and the target remains unchanged.

Missing or forged gate state

The dependent transition is refused; an agent-written success claim cannot substitute for a valid receipt.

Different target or candidate

A receipt for another installation, configuration or content digest cannot authorise the current transition.

Empty or incomplete check

No tests, omitted required scenarios, collection failure, timeout or truncated evidence cannot be reported as a complete pass.

Broken observation method

Known-bad and always-refuse controls expose false passes and false refusals in the proving method.

Mutation after verification

Changing a relevant dependency invalidates affected results before they are used.

Uncovered execution route

A protected operation cannot bypass authority through an alternate shell, edit or connector route.

Crash during a write

Resume reconciles the action outcome before retry; uncertain completion cannot produce a blind duplicate mutation.

Self-modification attempt

The worker cannot rewrite active policy, read the signing key or alter completed trusted records.

Explicit inactive enforcement

An allowed opt-out is reported as not enforced, never as proof that enforcement worked.

Run the suite against the installed executable path in a controlled environment. Keep required local checks available offline. Human decisions and unresolved risks must remain visible in the resulting record.

Integration and design basis

These responsibilities should have one canonical home. The table names existing project surfaces described in the published documentation; it does not assert that the proposed contracts already exist or pass the conformance suite. [1–4]

Existing surface

Architectural responsibility

PROJECT.md and task criteria

Define goals, invariants, exclusions and the authority delegated to a run. Treat them as contracts, not observations.

Pipeline state and deterministic hooks

Own progression, evaluate current authority and verify evidence validity. Keep enforcement outside the proposing agent’s control.

Hook sidecars and install manifest

Connect each installed control to its invocation and proving route. Extend the existing declaration and deployment path.

Specialist agents and validators

Propose and assess work with explicit scope. Emit structured findings, while trusted execution records remain independently produced.

Local run records and evaluation loop

Link evidence, decisions and later outcomes; govern candidate changes to prompts, probes and rules through review and evaluation.

Relation to the assurance model

Ground → Observe → Reconcile → Verify → Warrant → Ratify is the assurance view. The reference architecture additionally assigns those responsibilities, defines the contracts between them, establishes who can execute and approve, and specifies behaviour when evidence is missing or wrong. It can be applied inside a fixed workflow or an agent-directed task without equating a phase with an agent.

Design basis and further reading

Repository documents were reviewed on 25 September 2026. This is a proposed normative design, not a runtime conformance audit. The governing contract takes precedence over older architectural descriptions. The specific interfaces and acceptance tests above are recommendations to validate against the code.

[1] autonomous-dev PROJECT.md — Governing constraints and completion requirements; updated 30 August 2026.

[2] Enforcement Proven Everywhere and Smaller — Incremental enforcement and proof programme; updated 29 August 2026.

[3] autonomous-dev Architecture Overview — Existing integration surfaces; descriptive and older than the governing contract.

[4] autonomous-dev Evaluation — Existing diagnosis and improvement workflow.

[5] Anthropic Effective harnesses for long running agents — Context for persistent state and end-to-end verification.

[6] Anthropic Demystifying evals for AI agents — Context for evaluating observed outcomes and grading limitations.

[7] Microsoft Multi Agent Reference Architecture — A broader comparison for orchestration, knowledge and evaluation responsibilities.

Architecture proposal  •  25 September 2026 

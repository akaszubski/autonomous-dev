# Proposed: install once, attach a repo, run verified automation

Date: 2026-09-13. Status: PROPOSED; research and delivery design only.
Owner: [program #1757](https://github.com/akaszubski/autonomous-dev/issues/1757).
This does not supersede [adopted v12](20260909-control-tool-v12.md), change its
digest, authorize R0/D0, or relax [native isolation acceptance](20260913-f0-native-sandbox-amendment.md).

## WHY + SCOPE

Make autonomous-dev convenient to attach to other repositories without copying
its implementation into each repo or turning it into another infrastructure platform.
Accuracy and consistency come first; reduced maintenance and operator work next.
The product remains a portable plugin/control toolkit; a sandbox is an optional
packaged execution environment, not a mandatory dependency for every consumer.
The sandbox owns containment; autonomous-dev owns SDLC execution and assurance.
Do not rebuild shell-security policy inside the plugin. A qualified sandbox does
not make all actions harmless: mounted repos and authorized remote services remain
real resources. After boundary qualification, the primary acceptance question is
whether a required control fired, made the correct decision and had its effect.

Planning scope: this document plus one structured research appendix (two files).
No new launcher, daemon, scheduler, installer framework, GUI or credential broker.
Implementation file envelope: one release recipe, one shared runtime mixin,
at most one small entrypoint/config adapter per supported harness, two environment
examples, extensions to existing proof/CI, and existing runbook references.
Resolve actual paths and freeze the bounded D0 changeset before implementation;
growth above 50% of that envelope requires rescoping, not implicit expansion.

## User experience

1. Install the supported sandbox runtime once using the native OS package route;
   sign into Docker, complete credential-free boundary checks, then sign into the
   chosen harness through its supported flow with explicit user authorization.
2. Choose a repository and whether edits should be live or isolated for review.
3. Use one environment file stored outside the writable repo; preview with
   `sbx env plan`, then start/resume with `sbx env run`.
4. Preflight reports the repo, branch, exact tool/plugin versions, effective
   network access and assurance status before any model task starts.
5. Work normally in the chosen harness; stop/resume through sbx, review changes
   through Git, and retain evidence outside the worker.

These are target UX steps, not a runnable autonomous-dev release today: the native
manifest is still rejected (#1755). No invented `adev install` command is promised.
Current research/provisioning permission is not blanket model-credential authority;
the existing separate authentication gate remains before any native model session.
Native package installation, first login, missing virtualization privileges and
new security permissions are explicit one-time human steps, not hidden bypasses.

Ship two ready-made environment examples with declared input and `name` arguments;
the user supplies values, not hand-edited YAML. Proposed invocation after release:
`sbx env run "/path/to/live.yaml" --env-arg "repo=/path/to/repo" --env-arg "name=my-task"`.
On Windows the values are Windows paths; no Bash/WSL wrapper is required on the host.
Use an explicit environment-file path: installed v0.42.1 help confirms this skips
ambient home defaults, whose concatenated lists could duplicate ports/MCP entries.
The first per-repo attachment includes a visible plan/approval; later unchanged
attachments use the same command. Zero configuration edits is the target, not zero
security approvals or an ability to operate without prerequisites.
Before resume/attachment, compare requested and actual repo identity, base commit,
attach mode, environment/plugin digests and security profile. Same name is not
identity: sbx reattaches existing instances without reprovisioning. A mismatch must
refuse before the model runs; explicit recreation/retention of work is a separate
operation. Extend the existing preflight, not a second persistent registry.

## Existing Solutions

Research checked closed issues, changelog, commits and current delivery issues.
Existing owners: native plugin packaging #1755, delivery provenance #1734/#1521,
consumer proof #1636, bootstrap #1773; no parallel installer issue family.
The old `sandbox_enforcer.py` classifier and source-level mock tests are not
proof of isolation. Keep their existing ownership until a qualified activation
explicitly retires a superseded route; no blind deletion.

| Pattern | Reuse | Tradeoff / disposition |
|---|---|---|
| Docker Sandboxes sbx | VM, network policy, credential transport, lifecycle, environment files | Preferred runtime candidate; free local use but account required; experimental kits; not universal OS support |
| Native plugin + small sbx mixin | One implementation packaged with libraries; native harness discovery | Plugin schema repair and actual load proof required; settings owned by sbx cannot be overwritten |
| Dev Container Feature | Standard way to add the same released package to existing consumer environments | Future compatibility adapter only when demanded; not a firewall or independent safety boundary |
| DevPod / existing VM | Reuse an already chosen remote environment | No new dependency now; does not itself solve credential/firewall requirements |

Primary sources and date/version limits are in [research](20260913-portable-sandbox-delivery-research.json).
Search returned a timeout and irrelevant results; conclusions use official docs
and source, not an exhaustive security-advisory survey.

## Minimal Path

### Execution priority: prove the workflow before improving its packaging

User direction, 2026-09-13: delivery convenience must not displace the existing
[minimal vertical proof](20260909-control-tool-v12.md#minimal-vertical-proof-before-broad-testing).
This clarification restricts this proposal's execution scope; it does not alter
the adopted v12 bytes, frozen F0 cases or separate R0 authorization.

1. Finish only the isolation prerequisites needed for the frozen F0 native route;
   then measure actual tool ingress, hook result, dispatcher and stream records.
   A failed prerequisite gets a precise blocker and smallest supported remedy,
   not a broader environment redesign. Reuse unchanged evidence only when its
   declared dependencies/profile remain valid; retain required end-to-end reruns.
2. Freeze F0 evidence and missing-carrier findings honestly; obtain the required
   separate R0 authorization, then prove the bounded verifier against the existing
   independent oracle/comparator, including deliberately broken instruments.
3. Continue D0 and the first W0 control in adopted order: one real permit, refusal
   and broken route through the executing entrypoint to its production consumer.
   These three initial cases do not replace mandatory security or F0 mutation cases.
4. D0's clean-installed-consumer proof remains its exit gate before W0, as v12
   requires; W0 then proves its own installed/executing control and rollback.
   Expand only after that connected route works, retiring each superseded owner
   at its authorized migration boundary, not deferring D0 proof until after W0.

Until required by that route, defer convenience mixins, additional harnesses,
cross-platform UX work and automatic updates. Native plugin delivery is still D0's
product requirement, not a prerequisite for F0's existing isolated fixtures.
One active execution lane owns native settings/session/evidence; parallel work may
prepare independent frozen cases or inspect existing records, not duplicate runners.
The existing program issue records the exact next missing receipt and actual worker
activity; documents and a live idle process are not execution milestones.

Borrow patterns, not frameworks (sources checked 2026-09-13):

| Pattern | Apply to existing mechanisms | Limit / subtraction |
|---|---|---|
| [Strangler Fig](https://martinfowler.com/bliki/StranglerFigApplication.html) | Replace one control behind its existing entrypoint, prove equivalent intended behavior, then switch ownership | Temporary coexistence costs complexity; name the old owner and remove it after proof, never preserve known defects as desired behavior |
| [OpenTelemetry context propagation](https://opentelemetry.io/docs/concepts/context-propagation/) | Reuse native IDs and existing telemetry; prove each required boundary carries an exact identity | A trace ID is correlation, not authenticity or compliance; missing upstream keys remain UNMEASURED, no timestamp joins or new collector |
| [in-toto materials/products](https://in-toto.io/docs/getting-started/) | Bind existing receipts to exact inputs, outputs and command results, checked independently | Listed materials can be recorded without being used; retain actual read records and effect checks, not an attestation-only PASS or a new signing service |

These reinforce v12's four existing concepts and single-receipt ownership, not new
schemas. Context propagation plus input/output binding inform provenance together;
neither proves semantic examination. Required read coverage checks exact returned
content/ranges and truncation; separate acceptance checks the resulting work against
intent. Do not claim to prove a model's internal understanding from tool records.

### Native plugin install and update: the primary delivery method

Use Claude's plugin manager, not the existing file-copy installer, for ongoing
installation, update, enable/disable and uninstall. One native `plugin.json` and
marketplace catalog remain necessary upstream metadata; they are not an inventory
of every file or a second `install_manifest.json`. Libraries ship within the plugin
and resolve from its actual installation root, never a copied repo `.claude/lib`.

After #1755 repair and release, the target operator sequence is:

1. Add the autonomous-dev marketplace once with the native plugin manager.
2. Install `autonomous-dev@<catalog>` at the chosen native scope.
3. Update using `claude plugin update autonomous-dev@<catalog> --scope <scope>`.
4. Start a fresh session, then run the existing health/proof entrypoint before
   admitting normal work on the new version.

The catalog name and final scope are frozen in D0; these are not commands to run
against today's invalid manifests. CLI install/update syntax was inspected locally;
the installed CLI says restart is required. A catalog refresh, files changed on disk,
or a reported version is not proof that the running hooks changed.
Manual native update is the first supported mode; optional upstream auto-update is
only enabled after staged update/rollback proof and cannot mutate active proof runs.
Use a versioned Git/OCI source, not a marketplace command that reexecutes installer
code each session. The sandbox adapter installs the exact same plugin and never
updates a parallel copy. Base-runtime/dependency updates are separate from plugin
updates; a Python/library ABI change declares its compatibility requirement.
Retain prior exact release bytes and prove reinstallation through the native path;
do not advertise a native rollback command that has not been demonstrated.
An incompatible upgrade cannot activate; keep old worker/repo/evidence available
for recovery. No automatic global config reset, cache wipe or marketplace removal.

### One package, thin environment integration

- Keep one canonical native plugin with its libraries and installed verifier;
  release assets consume that package, never a second copied implementation.
- Maintain one common Linux tooling recipe with linux/amd64 and linux/arm64
  outputs. Small harness variants are acceptable where upstream entrypoints differ;
  do not force both agents into one image if that duplicates upstream configuration.
- Pin runtime version, image manifest and platform digest, harness executable,
  plugin version/digest and dependency locks. No `latest` or automatic update during proof.
- Prefer a non-`-docker` image: Docker-in-Docker is opt-in only for a repository
  that requires it, with a separately reviewed and qualified profile.
- Install common tools at image build time. Resolve project dependencies from
  existing lockfiles inside the worker; do not invent another dependency manifest.
  Build/install scripts are code execution and run under the same scoped policy.
- A synchronous entrypoint preflight must gate task startup and propagate the
  exact failing exit. Kit background startup and “sandbox created” are not readiness.
- Preserve existing project settings, MCP declarations, hooks and instructions;
  use supported separate layers. Present conflicting ownership and stop rather
  than replacing settings, merging arbitrary JSON, or widening permission lists.
- No shared writable skill store, host SSH agent, host home, host Docker socket,
  host-side MCP tool or broad host/LAN access by default. Do not snapshot credentials.
- Firewall remains host-owned, default deny, with task-scoped required endpoints.
  No silent fallback to paid API credentials when subscription OAuth fails.
- Host-side native runtime configuration remains outside the writable project.
  No untrusted repo host lifecycle commands; no blind global settings replacement.

### Attach modes: two clear choices, not a mount abstraction framework

| Mode | Intended workflow | Boundary |
|---|---|---|
| Live edits | Mount a dedicated, self-contained ordinary Git clone read-write | Edits immediately change that host directory; it is not protection from deletion or malicious Git/IDE configuration |
| Isolated review (default for autonomous jobs) | Mountless worker receives a fixed Git bundle containing the selected committed ref | Review returned bundle before integration; no continuously mounted host source |

A linked host worktree alone does NOT provide in-guest Git: its `.git` points to
metadata outside the mount. Detect this and explain the two supported choices;
do not mount the parent repo/home or rewrite Git pointers to make it appear to work.
sbx clone mode still exposes ignored/untracked source files read-only, including
`.env`; refuse it for unreviewed inputs. Initial proof uses mountless dummy input.
A secret scanner is an aid, never proof that an arbitrary repo contains no secret.
Existing dirty files must be preserved and reported; no implicit stash/reset/clean.
For isolated mode, use standard `git bundle create <outside-repo-path> HEAD`,
`sbx cp` into a mountless worker and `git clone <bundle> <guest-workspace>`.
Record the bundle digest, input repo identity and base commit; verify received
bytes before starting. Bundles include committed history, potentially committed
secrets: explicit input review still applies, and no credential-bearing remotes
or global Git configuration are copied. Dirty/untracked changes are excluded;
choose live mode or explicitly commit intended input instead.
For output, create a Git bundle of the result branch inside, copy it to a new
external artifact path, verify it, then use host `git fetch <bundle> <branch>` and
review before explicit integration. No custom synchronizer, automatic merge or
host lifecycle shell is required. First isolated attachment/export takes these
native Git/SBX steps; unchanged resume remains one command. Do not disguise that
tradeoff as a finished one-click experience.
Adding an ignored file to the host repo after input capture must not expose it
to the mountless worker. sbx clone mode is not the default: only a separately
qualified, externally stable input source could make that continuous mount safe.
Git bundles do not deliver external Git LFS objects or separate submodule repos:
detect these and require their existing explicit fetch/bootstrap procedure under
the scoped network policy, or refuse readiness; do not call a partial checkout ready.
Bundle semantics: [official Git documentation](https://git-scm.com/docs/git-bundle).
Initial security qualification alone remains mountless with disposable dummy input.

### Platform support: same Linux payload, honest host prerequisites

| Host | Upstream local sbx prerequisite | Product release claim |
|---|---|---|
| macOS | Apple silicon, macOS 14+ | Candidate; current M4 OS checks only, not full product certification |
| Windows | Windows 11 x64, Windows Hypervisor Platform | Unmeasured until real Windows host tests |
| Linux | Ubuntu 24.04+ x64/arm64, KVM and permissions | Unmeasured until host-specific tests; Linux inside a Mac VM is not native Linux-host proof |
| Intel Mac, Windows ARM/10, other Linux distributions, virtualization-disabled host | Not covered by current documented local sbx support | Explicit unsupported status; no weaker container fallback |

For unsupported hosts, an existing qualified Linux remote host may be used through
standard SSH/editor tools, with the repo and runtime there. This is a separate remote
workflow, not local support; no new remote service or automatic paid provisioning.
Linux execution cannot run Xcode/iOS/macOS-native or Windows-native builds: retain
those native build/test jobs and label results separately. GPU, USB, GUI, enterprise
proxy/certificates and air-gapped use are optional profiles, not universal promises.

## Acceptance: prove convenience and correctness together

| ID | Real-route permit + refusal/fault evidence |
|---|---|
| E1 Setup | Fresh supported host reaches ready state; missing virtualization/auth/dependency gives actionable failure, never a silent fallback |
| E2 Integrity | Exact installed bytes load; wrong digest, missing plugin/hook/library or altered config prevents ready state |
| E3 Retrofit | Populated consumer retains settings/hooks/instructions and unrelated files; deliberate ownership conflict refuses without partial overwrite |
| E4 Git | Record input repo identity/base/bundle digest; live clone supports status/edit/commit; isolated output can be fetched from returned bundle, including input bundled from a linked worktree without parent metadata exposure; a later ignored host file stays absent |
| E5 Boundary | Allowed read/write/process/network works; direct-IP/DNS/proxy bypass, protected paths, descendants, hook failure and policy tampering do not evade required boundaries |
| E6 Workflow | Real Claude /implement proves required role reads, hook registration and actual firing, correct permit/refuse decision, downstream effect and receipt; disconnected/duplicate/wrong-version hook and missing required record cannot pass |
| E7 Recovery | Kill/restart preserves evidence and completed dependency installs; same name with another repo/ref/mode/profile refuses; crash between external effect and receipt stops automatic replay until independently reconciled; no exactly-once claim |
| E8 Lifecycle | Update is explicit and digest-bound; previous version actually re-executes after rollback; uninstall preserves repo work, evidence and unrelated/global settings |
| E9 Portability | Same package/workflow on real macOS, Windows and Linux hosts and amd64/arm64 artifacts; cover paths with spaces/Unicode, case collisions, CRLF/executable bits, ownership and file watching; missing host is UNMEASURED |
| E10 UX/cost | After one-time runtime/login and per-repo input approval, one native start/resume command and zero YAML edits/infrastructure copying; record cold/warm times, bytes, commands/prompts and errors; no paid runtime feature required |

Use one shared case set with platform parameters, not copied OS suites. Start with
one real permit/refuse/broken-route vertical slice; add only distinct boundary faults.
Keep raw exits and actual source records externally; policy diagnostics are not
paid audit logs and neither substitutes for exact tool/hook identifier provenance.
Guest sudo means guest validators are not authoritative; retain current strict
native sandbox composition and external acceptance. No `--dangerously-*` startup.

## Sequence, ownership and subtraction

| Existing owner / work | Dependency | Parallelism |
|---|---|---|
| #1773 F0: complete frozen native carrier and bootstrap evidence | Current authority; environment proof does not complete F0 | Read-only platform/config research alongside native proof |
| #1755 D0 discovery: canonical manifest repair and package assembly | Existing F0/R0 authorization boundaries, unchanged | Bounded package and platform prep; no unauthorized production changes |
| #1734/#1521 D0 integration: one sbx recipe/config path consuming package | Trusted runner and schema-valid package | Independent OS qualification on distinct hosts; no shared mutable state |
| #1636 consumer proof: populated/clean consumer, update/rollback/removal | Exact installed package and environment | Consumer tests parallel with remaining supported host tests |
| #1757 activation | Required evidence and explicit promotion | Serial final ownership switch and documentation updates |

After equivalent proof, retire the superseded per-repo copying path in the same
activation; retain supported non-sbx plugin usage and installed consumer compatibility.
Named subtraction target: `plugins/autonomous-dev/scripts/install.py`'s component
mapping/copy into `<repo>/.claude/` and `scripts/deploy-all.sh`'s per-repo executable
mirror for migrated consumer families. Native plugin lifecycle becomes their sole
delivery owner after D0 proof; enumerate global/unmigrated callers before removing
shared helpers, retaining them only while an explicit migration consumer needs them.
No sbx kit may call those old copy paths and also install the native plugin.
Additional harness variants remain deferred until the first Claude path passes;
one architecture does not require simultaneous multi-harness implementation.
Do not introduce a second settings generator, release-version file or evidence store.
Update existing architecture/runbook/user reference/changelog with shipped behavior,
not proposed guarantees; keep live progress in issues and design in this document.

Planning estimate after prerequisites: 0.5-1 engineering day for the thin environment
recipe and UX preflight; 1-2 days for first-harness/package integration; 1-2 days for
parallel cross-host and lifecycle proof once hosts/accounts are available. These are
unvalidated estimates, not whole-plan ETA; F0/R0/D0 work is not counted twice here.
Codex SDLC parity is separate qualification, not implied by a working Linux binary;
ship only the harness/control families actually proven. No Linux GUI or remote
controller is needed to ship the initial CLI experience.

## Risks and Unknowns

Current sbx v0.42.1 is installed locally, but formal audit logs require paid
organization governance and are excluded from the mandatory path. Kits/environment
schemas are experimental; local template inspection differs from docs, so exact
image identity remains a qualification item. Sign-in/account and vendor licensing
must not be confused with the MIT license of autonomous-dev itself.
The current test image was the upstream `shell-docker` default; its OS pass does
not qualify a non-privileged profile. Requalify the explicitly selected non-Docker
image; do not claim that private Docker-in-VM is ordinary unprivileged containment.
Subscription OAuth, durable common carrier IDs, actual Windows/native Linux access,
uninstall/update conflicts and native-build workloads remain measured release gates.

## Critique History

Round 1: REVISE (portable_plan_critic). Corrected authentication ordering and
separate authority, native parameter-based repo binding, exact sbx Git input/output,
dirty-file behavior, ambiguous-side-effect replay refusal and named copy-route
subtraction. Research appendix was initially read before creation; it now exists.
Round 2: REVISE. Added requested-vs-actual resume identity checks and changed
autonomous input/output to existing Git bundles plus sbx copy, removing continuous
source mounts rather than inventing a watcher. Explicitly acknowledged first-use
transport steps; added late-secret and name-reuse fault cases.
Round 3: PROCEED; no material contradiction remained. The suggested research
appendix correction had already been applied during review. Subsequent user
clarification makes native plugin updating explicit and centers hook execution;
these additions preserve all existing acceptance/authorization boundaries.

Execution-priority clarification: three further critique rounds, REVISE then
corrections verified and PROCEED. Explicitly retained D0 installed proof before W0
and required end-to-end reruns despite unchanged bytes; no new framework or waiver.

# F0 amendment — staged isolation and native qualification

Date: 2026-09-13

## Authority and intent

The user requested the lowest-overhead safe approach, authorized proceeding
with local setup, and requested this plan update and efficient continued execution.
This amendment records that direction: reuse the existing isolated environment,
Claude's native OS Bash sandbox, and native file permissions; do not build another
shell parser, sandbox framework, or credential broker.

The [adopted v12 plan](20260909-control-tool-v12.md) retains its original bytes
and SHA-256 `05a3efafecb2099ff8f9d1efdb9601577fdf071072e9b945690cbdbc252fab7d`.
This is a linked F0 prerequisite amendment, not a retroactive replacement of its
adoption or evidence. F0 acceptance, frozen cases, oracle independence, budgets
not already excepted, and the separate exact F0-to-R0 authorization remain intact.
Local zero-cost provisioning and dummy-secret OS tests are permitted. On
2026-09-13 the user approved the explicitly proposed two-stage change with
"do it": prove outer isolation using dummy data first, then a tightly scoped
Claude login and native workflow test, with normal development blocked until pass.
This supersedes this amendment's earlier pre-secret full-native ordering, not its
required checks. The prior bytes at `3e9b4b1a` (SHA-256
`7034e937eef11e7500abaa4191d6ce8092ebc701579242121fabab6d0ca85339`)
remain historical evidence, not the current ordering.
Conditional authentication authority applies only after Stage A passes and only
to the existing Claude Max subscription via a supported login route; no credential
copying, paid API fallback, unrestricted account use or unrelated model work.
Neither consumer deployment nor promotion is authorized by an OS pass.

## Architecture decision

- Outer isolation protects the host and excludes host homes, private oracle,
  evidence stores, credentials and administrative sockets from tool access
- Native mandatory OS sandbox contains Bash and descendants, even if a hook fails
- Native file-tool permissions protect the corresponding in-process read/write
  routes; MCP or alternative execution routes require their own demonstrated scope
- Hooks retain workflow decisions and telemetry, not shell security parsing
- Trusted immutable settings define the boundary; consumer settings are preserved
  and conflicts reported, never silently replaced or widened

`dontAsk` alone is insufficient: intrinsically permitted operations can still run.
Wrapping Claude alone also cannot hide credentials that Claude itself must use.
Native transport and result-spill access must work without exposing protected data.

## Acceptance and order

| Step | Required evidence | Failure behavior |
|---|---|---|
| Prepare | Exact pinned image/profile, package identities, unchanged CLI digest, no unexpected volumes or credentials; reuse an adequate image and derive one only for a named missing capability | Keep previous environment untouched |
| OS viability | Strict namespace/mount probe: exact exit 0 and expected marker | Preserve stderr; do not run later probes |
| OS effects | Allowed read/write/process control plus denied direct, alias, procfs, descendant, network and socket cases | Any escape or broken positive control is non-pass |
| Native composition | Effective settings, actual parent/child tool routes, hook error/timeout/cancel, no unsandboxed fallback, protected policy and working result transport | Missing evidence cannot pass |
| F0 integration | Existing frozen native cases and identifier census, independent comparator and current digest-bound receipts | OS-only or static checks cannot substitute |

Require sandbox availability, prohibit unsandboxed retries and excluded-command
escape paths, keep filesystem isolation enabled, and prevent settings-tier additions
from reopening protected paths. Verify supported settings against the pinned CLI,
not only current online documentation. No privileged container, broad seccomp
disable, weaker nested sandbox or host security change merely to pass a probe.
If strict nesting fails, diagnose it and review a supported isolated Linux/VM
alternative before execution; do not silently relax the boundary.

## WHY + SCOPE

Remove the circular requirement to exercise a model-driven native tool route
before any model authentication. Change only qualification ordering in this
document; no new runtime, verifier, policy engine or production implementation.

## Existing Solutions

Reuse the existing outer sandbox, mandatory native sandbox and file permissions,
frozen F0 fixtures and independent comparator. The sources below and #1773's
recorded CLI inspection establish the distinction between OS probes and native
execution; no supported credential-free full native route has been demonstrated.

## Minimal Path

- **Stage A, no model credentials:** freeze exact profile/package/settings
  identities; complete Prepare, OS viability and OS effects above using dummy
  data. Demonstrate host/private-evidence exclusion, protected policy, required
  network/descendant/socket refusals and working positive controls. Account for
  all gateway/credential plumbing: no registered MCP servers is not evidence
  that an enabled gateway is disabled or inaccessible. Any missing required
  observation, unexpected credential or escape blocks Stage B.
  Exercise the intended Stage B credential paths, gateway and endpoint policy
  using dummy values. Compare actual configuration after login to that frozen
  profile; any changed settings, mounts, gateway or endpoint permissions invalidate
  affected checks, which must pass again before model/tool execution.
- **Stage B, conditional scoped authentication and native tests:** after an
  independent Stage A review against frozen cases, use supported subscription
  authentication for the named disposable F0 worker only. Record effective
  endpoint permissions and credential handling without capturing secret values;
  never mount/copy host credentials or grant broad network access for login.
  The authenticated service is a real account capability, not dummy data:
  containment does not prevent authorized account consumption, so retain the
  existing attempt limits and stop on unexpected provider/billing behavior.
  Run only frozen native qualification cases with fixture inputs, no consumer
  repository or normal development. Observe actual parent/child/tool/result
  paths, native sandbox enforcement, hook failures and identifier census.
- **Admission:** only independent Native composition and F0 integration evidence
  can complete F0. A login, OS pass or successful model response cannot. Preserve
  failing evidence, stop the worker and independently verify removal of
  test-specific access using the supported scoped mechanism on success, failure,
  cancellation or interruption; do not revoke unrelated sessions or
  repeatedly retry. If scoped credential cleanup cannot be established, refuse
  authentication until its lifecycle is defined.

Use dummy data before real authentication. A standalone sandbox-runtime test is
an OS prerequisite only; its version must match or its differences be explicit.
The security checks are unchanged; only real native checks move after the
conditional login. Unsupported routes and required missing evidence remain
blockers rather than substitutes for acceptance.

## Efficient execution without weaker evidence

Image preparation, frozen test preparation, and read-only R0 contract mapping may
run in parallel with distinct owners. Run OS viability before effect probes, and
native integration only after prerequisites. Serialize shared settings, native
session state, final evidence aggregation and activation. Reuse verified unchanged
evidence; rerun only affected cases plus the required end-to-end route. Do not
repeat broad audits or suites without a named uncertainty.

After F0 freeze and separate authorizations, R0 and the first D0 changeset may be
authored independently; R0 trust precedes D0 installed proof, then the walking
control slice and later migrations follow v12. This amendment changes neither
promotion thresholds nor later-rung authorization.

## Evidence and ownership

[Program issue #1757](https://github.com/akaszubski/autonomous-dev/issues/1757)
owns live progress and the next missing receipt;
[F0 issue #1773](https://github.com/akaszubski/autonomous-dev/issues/1773)
owns prerequisite results, exact commands, image/config digests and failures.
Do not copy changing status into the schedule or this amendment. Mechanically
bind specialist output to its actual source records; narrative reports do not
prove reads, hook execution or effects. Missing common carrier identifiers remain
`UNMEASURED`, never joined by timestamp proximity to obtain a pass.

## Research basis

Official sources consulted 2026-09-13; online behavior may postdate pinned 2.1.236:

- [Claude Bash sandbox](https://code.claude.com/docs/en/sandboxing)
- [Native permissions](https://code.claude.com/docs/en/permissions)
- [Isolation approaches](https://code.claude.com/docs/en/sandbox-environments)
- [Anthropic sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)

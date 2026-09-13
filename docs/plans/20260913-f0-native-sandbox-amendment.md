# F0 amendment — native isolation before authenticated testing

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
Local zero-cost provisioning and dummy-secret OS tests are permitted. This
amendment does not authorize OAuth, real authentication or credential injection;
these require separate explicit user authority, and missing authority is a blocker.
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

Use dummy data before real authentication. A standalone sandbox-runtime test is
an OS prerequisite only; its version must match or its differences be explicit.
If no pre-secret full native route is available, record that blocker rather than
claiming that a shell test proves Claude integration.

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

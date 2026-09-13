# ADR-001: qualify one native sandbox inside the isolated worker

Date: 2026-09-14
Status: Proposed; credential-free preparation only, not native admission
Owner: [F0 #1773](https://github.com/akaszubski/autonomous-dev/issues/1773)

## Context

The [staged isolation amendment](../plans/20260913-f0-native-sandbox-amendment.md)
requires an isolated worker, mandatory native Bash sandboxing, native file-tool
permissions and independent evidence. It explicitly permits reviewing a supported
VM alternative if strict nesting fails. Its adoption and frozen v12 bytes remain
unchanged. This record does not authorize promotion or a weaker security boundary.

The existing standalone SRT wrapper and an inner SRT both need Unix sockets.
Three dummy-only runs failed before their expected marker with `listen EPERM`
on the inner `srt-mux` socket. Pinned SRT 0.0.76 blocks AF_UNIX creation inside
the outer sandbox; Linux has no path-specific exception. External proxy ports
still require the inner Unix bridge. These are OS compatibility observations,
not an executed native Claude tool case.

## Proposed decision

Qualify the existing disposable VM plus a narrowly hardened systemd service as
the outer host/evidence/device boundary, and let Claude own the single native
SRT boundary for Bash. Keep native seccomp and filesystem protection enabled.
Use stock capabilities rather than a new proxy, credential broker or shell guard.

The pinned Claude 2.1.236 binary contains a `sandbox.credentials.envVars` schema
with masking and host-scoped injection. This supports investigating native
configuration; it does **not** prove effective runtime mapping or inheritance.

| Boundary | Proposed owner | Required qualification |
|---|---|---|
| Host homes, private evidence/oracle, administrative sockets and devices | VM plus effective systemd mount/privilege controls | Mount census proves excluded objects absent; existing protected objects refuse direct, alias and descendant access; ordinary work succeeds |
| Bash and descendants | Mandatory native sandbox | Stage B observes no exclusions/fallback, constrained network and credential behavior; standalone Stage A evidence is not native proof |
| In-process file tools and tools invoked by Agent | Immutable native permissions, inherited by Agent tool routes | Stage B observes protected files and procfs aliases refuse; fixture and result-spill access succeeds |
| Trusted Claude process and immutable hook commands | Explicit trusted computing boundary | Credential carrier/output audit; no model-controlled hook configuration |
| Process lifetime and evidence collection | Existing independent supervisor plus service cgroup | Exact invocation join, interruption and complete owned-process cleanup |

Unlike the previous wrapper, the trusted Claude parent would possess the raw
authentication token. Native Bash masking alone does not protect it from
in-process Read/Grep/Glob or inherited hook environments. These are changed
surfaces, not covered by old wrapper receipts. Systemd cannot hide a process's
environment from that process and does not supply a domain-aware firewall.
Native SRT constrains model-controlled Bash egress, not the trusted Claude
parent's provider traffic. The frozen tool list excludes WebFetch/WebSearch and
strict empty MCP configuration excludes MCP network routes. Trusted-parent
egress is a changed scope, not the previous whole-process endpoint guarantee;
its actual behavior must be recorded before accepting the composition.

OrbStack's generic systemd drop-in overrides several security properties.
Requested command-line properties are therefore insufficient: a new named
service's effective properties and actual effects must be checked. Do not alter
the global drop-in or assume that `User=f0` removes supplementary privileges.

The concrete candidate uses a dedicated static system identity, not the existing
privileged-group account. A maximal DynamicUser/kernel-mount profile failed;
paired static-identity controls started with both strict and full filesystem
protection, so the failure must not be attributed to strictness alone.

The worker has a further container-specific procfs constraint. Removing its
complete proc view prevents bubblewrap from mounting a fresh procfs. A read-only
support view did not resolve this; a read-write view beneath a root-owned 0700
directory on read-only tmpfs did. This view is for kernel namespace construction,
**not tool access**. Private devices still hide the original administrative path.
The candidate must prove refusal through direct, symlink, proc-root, directory-FD,
working-directory and mutation routes, including a mapped-root challenge; no
inherited descriptor may expose the protected view. A marker alone is insufficient.
The [kernel mount visibility rules](https://github.com/torvalds/linux/blob/master/fs/namespace.c)
explain why mount visibility and pathname access are distinct checks.

This support mount is a disposable-worker compatibility binding, not a new
mandatory product dependency or a claim about other platforms. Product portability
still requires its own installed-consumer proof. A host with an adequate complete
proc view must not acquire this workaround by default.

## Alternatives considered

- Keep two strict SRT layers: small configuration, but reproducibly cannot start
  the inner Unix bridge. Do not keep retrying it.
- Allow all Unix sockets in the outer SRT: small edit, but relaxes a qualified
  boundary; not selected merely to obtain a passing startup probe.
- One native SRT plus existing VM/systemd: selected as a candidate. Stage A
  qualifies VM/systemd and standalone stock-SRT mechanics plus static CLI
  schema; the native adapter and routes remain unmeasured until Stage B.
- New proxy/firewall/broker framework: larger maintenance burden; not selected
  while the stock composition remains a testable candidate.

## Execution and acceptance

The [approved layered-IPC trial](https://github.com/akaszubski/autonomous-dev/issues/1757#issuecomment-5656271270)
is a narrowly authorized, credential-free alternative to this single-native
candidate, not its activation. It moves the Unix-creation refusal obligation
to the mandatory inner tool sandbox while permitting the outer trusted parent
to create internal IPC. Its exact scope and required opposite/mutant controls
live in that decision; earlier outer-layer refusals cannot be relabelled as
proof of the changed composition. All other admission gates remain in force.

### Native adapter compatibility is a separate boundary

The standalone runtime's accepted configuration is not automatically accepted
by Claude's embedded runtime. Static inspection of pinned Claude 2.1.236 and
the separately downloaded, unactivated 2.1.270 found no native mapping for
`network.deniedResolvedAddresses`; a hostname allowlist does not establish
resolved-address or DNS-rebinding protection. Do not retain that inert key in
native settings or credit the standalone guard as native evidence. Native
`Edit(path)` rules cover file editing; `Write(path)` rules are not a substitute.

External proxy ports are not a drop-in repair: the standalone runtime's proxy
authentication, credential sentinels and CA ownership have no demonstrated
shared contract with the embedded runtime. Do not build an adapter merely to
make those independent states appear compatible. An additional standard OS
address restriction is only a candidate until positive and refusal effects
prove it works on this worker; an effective configuration listing alone is
insufficient. In particular, the tested systemd `IPAddressDeny=any` property
did not prevent a live connection and supplies no protection here. No real
credential may be used while this known prerequisite remains unresolved.

1. Freeze candidate settings, service properties, exact file bindings and package
   identities. Keep the old profile and receipts intact. Preparation uses new
   private artifact paths and a new disposable service only.
2. Run no-credential OS viability and changed-effect checks with the pinned stock
   runtime, without invoking Claude or its native adapter. Verify effective
   properties, positive controls, private carrier
   exclusion, network/credential dummy controls and cleanup. A standalone pass
   is not proof of the native CLI adapter.
   Reject apparent refusals caused by the checker failing before the tested
   operation (for example, a failed shell redirection). Require the operation's
   actual error and its positive control, retaining invalid earlier receipts.
3. Independently review the changed boundary against the amendment. Unknown
   settings, unexpected mounts/privileges and missing required OS effects fail
   admission; no real credential is loaded to discover a known prerequisite gap.
4. Only then use the amendment's conditional Stage B authority for frozen native
   qualification. Actual native settings, tool inheritance, hook failures and
   common identifiers remain unmeasured until observed. Do not recreate the
   superseded requirement to run model-driven native tools before authentication.
5. Preserve the adopted row order: PR-8, EX-1, EX-2, then RC-2 and PR-3–7/9.
   Explicitly bind the historical `/effects/pr8.started` to the existing permitted
   work area before dispatch; do not change the scenario's semantics. Preserve
   attempt limits, independent comparison and scoped access revocation.

The work is bounded by these gates rather than a completion-time promise:
compatibility first, changed effects second, native receipts third. Reuse prior
evidence only for unchanged subjects; do not rerun broad suites or restart login
to compensate for a composition failure.

## Scope and recovery

No production libraries, hooks, consumer settings or installer are changed by
this proposal. Private candidate files live under `adev-os-probe.knaJ5c` in the
local Codex artifact store; exact paths and digests belong in #1773's result
receipt, not in portable product configuration. No new general-purpose runner
or policy vocabulary is proposed.

If qualification fails, stop only the candidate service, verify its cgroup is
empty, preserve failure evidence and leave the existing profile untouched.
Never call stopping a service or deleting a local token server-side revocation.
Live progress remains in [#1757](https://github.com/akaszubski/autonomous-dev/issues/1757)
and #1773; this decision record is not a duplicate progress ledger.

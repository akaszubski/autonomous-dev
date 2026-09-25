# Workflow-assurance restart checkpoint

Observed 2026-09-25 during the ordinal12 v3 build. This is a restart pointer,
not acceptance evidence. Canonical scope remains the
[execution plan](../plans/20260916-workflow-assurance-subtraction.PROPOSED.md).

- Checkout: `/Users/akaszubski/Dev/autonomous-dev-1779`, branch
  `fix/1779-pipeline-evidence-integrity`; base `cea7c0f73d4614b6a3fe9cf71b8005a1274665c4`.
- Preserve the pre-existing modified native plugin manifest and untracked `.Codex/`.
- F0 remains incomplete; ordinal11 is NONPASS. No product release is accepted.
- Claude `/implement --fix` session `890bdc4c-f604-4a3a-bdc5-29a0f09336e0`
  was live on exec handle `57665`; implementer task `a10964abb8e520119`.
  Poll that handle first. Revalidate process state if the handle is unavailable;
  do not start a second run merely because an observation times out.
- Private artifact root:
  `/Users/akaszubski/.codex/artifacts/adev-boundary-wiring.KXz82zi4`.
  Build contract `ORDINAL12-V3-BUILD-CONTRACT.PROPOSED.md` SHA-256
  `abfe3034356514f3139e31605d3be6da5ab88496f1327775c661453e71fbae33`.
- Independent baseline audit verified all 16 named dependency entries and the
  retained ordinal11/v1/v2 evidence. Worker source is
  `adev-sandbox-probe-1791:/opt/adev-probe/ex-source.1pnvv_ae`.
  Local 29-entry ledger digest:
  `680e7bb4dcb71ea74bdde576e118113b8c2a75d1145bf03aa2415fcd94e984e5`;
  worker 10-entry closure ledger digest:
  `adcad4c8a2b335cc3bd0c0fbcc870c36a9a783f8a9356e5a5ed08e1d2dd39a60`.
- Baseline offline suite reproduced 62 passes, 7 pre-existing failures in
  `test_install_attempt10.py`, and 189 passing subtests. Diagnose any additional
  failure; do not report this baseline as all green.
- Applied role-prompt bytes remain UNMEASURED. The running build cannot grant F0
  acceptance. The subsequent canonical-plan authority reconciliation withdraws
  the private build's extra unconditional prompt-byte blocker prospectively;
  adopted gates still apply. Preserve the running build's frozen contract. No
  raw-body capture was enabled or required by this checkpoint.
- Parallel consumer review found missing acceptance detail: effective settings
  precedence, zero-mutation conflict refusal, independent physical hook count,
  explicit interruption boundaries/recovery states, and exact consumer/Codex
  profiles. The canonical plan now requires these before implementation/claims;
  exact profiles and executable proof remain unfinished.
- A disposable D0 fixture passed native install v1, update v2, and cached v1
  restoration on Claude 2.1.236. The supervisor independently verified all four
  restored file hashes and exact equality with the original v1 manifest.
  Unrelated settings sentinel remained unchanged across the recorded transitions.
  This is fixture lifecycle evidence, not product deployment, cold reinstall,
  interrupted-update recovery or actual hook execution proof.
  Preserved evidence:
  `/Users/akaszubski/.codex/artifacts/d0-native-lifecycle.fiHSsl/evidence`;
  `result.json` SHA-256
  `0abc93762ca07e486a53b55fc4d740c0eae5955f075de9ea223287c2f08b92f1`;
  `evidence-manifest.sha256` SHA-256
  `cce22196ed9cc93b7a103ff400b4f4e0dff3f36b9c74e130511a8af7ba1d113c`.
- A separate cold reinstall from the same pinned local catalog also passed:
  both prior version caches were moved aside recoverably; the recreated v1
  directory had a distinct inode and all four original hashes matched on the
  supervisor's independent check. Settings sentinel remained unchanged.
  Evidence: `/Users/akaszubski/.codex/artifacts/d0-native-cold-restore.o6YVdv/evidence`;
  result SHA-256 `eb8255b1d32c0aafbccfe31dbf71563484c4c80c276c476a8b341685994fd4e2`;
  manifest SHA-256 `fbd25c21119edd5f244ea296bba5c97287005037ecb74062e6ca251d4382ea6c`.
  This does not prove remote marketplace recovery or hook execution.
- Preliminary candidate review is preserved in private
  `ORDINAL12-V3-PRELIMINARY-REVIEW.md`. Findings require rechecking after the build:
  hash-then-reopen loading, incomplete path identity checks, duplicated finalized
  envelope verification, self-compared preflight context, missing native wiring,
  and omitted-duty coverage that must exceed source-digest checking.
- Independent authority review accepted the prospective clarification: only the
  extra private applied-role-byte blocker is withdrawn; adopted execution,
  security, identity, oracle and promotion requirements remain unchanged.
- The same live Claude handle subsequently reported 116 candidate tests passing
  and a combined result of 178 passes, 7 known attempt10 failures and 189 passing
  subtests. These are observed runner reports, not independent candidate
  acceptance. The owner loader still hashes a read and then reopens via an import
  loader in the inspected snapshot; the preliminary review remains unresolved.
- D0 work proceeds independently on a proposed finite clean/populated consumer
  matrix. It must not change the F0 worker, real credentials or installed settings.
  Proposal: `/Users/akaszubski/.codex/artifacts/d0-consumer-lifecycle-matrix.lTBaCz/D0-CONSUMER-LIFECYCLE-MATRIX.PROPOSED.md`,
  SHA-256 `3e809edeeff68052356e13d4442bc6becf0ac348358ed9e80c2040cf0d934d6a`.
  Eight case families cover provenance, settings, conflicts, physical hook count,
  updates, interruptions, rollback and uninstall/subtraction. It is not frozen:
  effective precedence, carrier identity and injectable interruption boundaries
  still require observation. A separate credential-free disposable probe is
  assigned; it cannot use the F0 worker or establish product acceptance.
  The first probe completed: two credential-free pinned-CLI `--init-only` runs
  each recorded five physical hook processes with explicit settings winning the
  tested scalar. Supervisor verified the evidence manifest and both event groups.
  Evidence: `/Users/akaszubski/.codex/artifacts/d0-native-precedence.SXLLXs`;
  result SHA-256 `5877738a9d8aacff13b1c1acc1867512a3b5da9aeb135f28197ee1eacb3e34e1`.
  Full layer precedence and installed-product behavior remain unproven. The
  strict validator accepted an unsupported plugin-default key, so schema success
  alone cannot establish that layer's support. Bounded layer-removal probes are
  continuing with the same observer, not another harness.
  The extension completed with observed scalar order explicit > local > project
  > user; plugin-default `env` did not participate (plugin-only and absent-control
  both yielded null). All five additional sessions recorded five distinct hook
  processes. Supervisor checked the retained manifest; installed-plugin behavior,
  permission merging and ordering remain outside this result. Evidence:
  `/Users/akaszubski/.codex/artifacts/d0-native-precedence-extension.DHsmRQ`, result
  SHA-256 `9513f48a18fff000ebf1ea80f0c439fd8c68d8480ed9c4a74e972756f5031e15`.
  Installed-registration probe then observed one native hook and detected two
  physical processes under duplicate registration, but execution came from the
  mutable local catalog rather than registry `installPath`. Treat source-free
  installed provenance as failed for that marketplace profile, not accepted.
  Evidence: `/Users/akaszubski/.codex/artifacts/d0-installed-hook-probe.b3qGG4`,
  result SHA-256 `df4124ba45c0779bd0ec6b76f96e58d39a510bb41356fabb700e4b33f4054f55`.
- The 116-test snapshot independently remains FAIL for real preserved replay,
  unchanged-source duty omission, installed preflight and actual activation.
  Private `ORDINAL12-V3-CORRECTION-BRIEF.md` routes corrections through the next
  real `/implement --fix` turn after the active writer is terminal. Its scope is
  independently reviewed PROCEED after narrowing the design to one staged
  canonical binding module at the existing native import path, removing the new
  dynamic loader and duplicate verifier; preserve the initial candidate before
  correcting it. All eight initial candidate manifest entries were independently
  hash-checked successfully; this establishes identity, not correctness.
  Initial snapshot is retained at
  `/Users/akaszubski/.codex/artifacts/ordinal12-v3-initial.9jCgwo/candidate.tar`,
  SHA-256 `525a3a393b8e70760be2fc8e7f1b33050b07db11613223161e298ed348d285ee`;
  all eight archived manifest entries independently match. The same live Claude
  session has moved from implementation to its native spec-validator task
  `aa88f07a4b1fe4f68`; the supervisor has not launched a correction concurrently.
  Current projected subtraction accounting instead grows by 107 production/rubric
  lines and 826 test lines; no retirement or maintenance reduction is claimed.
  GitHub progress: https://github.com/akaszubski/autonomous-dev/issues/1773#issuecomment-5826362489

Next: collect the same Claude run's result, independently inspect its actual diff
and preserved hashes, run the affected offline proof, and complete independent
review before worker staging or a native attempt. Keep native worker ownership
serialized. Resolve D0 profile/rollback prerequisites in parallel without touching
the F0 worker, credentials or shared installed settings.

Commit coordination: the checkpoint update's commit attempt ran documentation
checks (14 passed, 1 skipped), but the outer test guard refused because the real
activity log changed during the active Claude run. Leave the update staged and
retry with normal gates after that run is idle. Do not disable the state guard or
claim its change-detection alone identifies the writer. This checkout's live-log
watch means commit-time tests and native pipeline activity can share mutable state.

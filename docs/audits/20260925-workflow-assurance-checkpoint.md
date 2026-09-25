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
  acceptance. Exact role-body observation needs a separately reviewed bounded
  capture design; no raw-body capture was enabled by this checkpoint.
- Parallel consumer review found missing acceptance detail: effective settings
  precedence, zero-mutation conflict refusal, independent physical hook count,
  explicit interruption boundaries/recovery states, and exact consumer/Codex
  profiles. The canonical plan now requires these before implementation/claims;
  exact profiles and executable proof remain unfinished.
- D0 native lifecycle readiness is being checked separately; packaging is not
  installed, updated, rolled back or qualified by this review.

Next: collect the same Claude run's result, independently inspect its actual diff
and preserved hashes, run the affected offline proof, and complete independent
review before worker staging or a native attempt. Keep native worker ownership
serialized. Resolve D0 profile/rollback prerequisites in parallel without touching
the F0 worker, credentials or shared installed settings.

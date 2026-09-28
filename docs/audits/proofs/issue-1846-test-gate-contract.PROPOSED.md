# #1846 test-gate contract — proposed, not accepted

Observed 2026-09-29: a signed #1805 `/implement --tdd-first` STEP 1 full
pytest capture reached its 900-second timeout and wrote `__TIMEOUT__`. No
targeted RED, full baseline or gate pass resulted. The current STEP 8
absolute-green gate conflicts with later inherited-red fix-forward wording;
the routed quality gate does not override it. See #1805 and #1846.

## One result owner

Reuse #1818's process-capture owner; do not introduce a second runner or
persistent store. Each attempt binds run/session, worktree, base/candidate
and dependency/config digests, exact argv, redacted allowlisted
behavior-relevant environment (never credentials), collected and executed
test IDs, raw exit, duration and bounded stdout/stderr artifact digests.
Publish artifacts and receipt atomically through the existing capture owner;
re-hash and re-bind them to the current run/worktree/config at consumption.
Every result names its scope: diagnostic or full-denominator, plus PASS, FAIL
or UNKNOWN. Timeout, interruption, collection failure, missing exit, empty
or stale selection, changed binding and artifact mismatch are UNKNOWN, never
PASS. A model's summary is not a result.

## Transitions

Focused or affected-scope results are local diagnostic feedback only. They
authorize candidate edits and informal review, not `pytest-gate` completion,
formal specialist-order credit, commit, deploy or release. Existing transition
consumers must not map PARTIAL/UNKNOWN to PASS. An inherited red is visible
debt, not a new regression and not product acceptance.

To address the full-suite timeout without omitting tests, first freeze the
complete collected ID universe of the configured canonical invocation
(`pytest --tb=short -q`) at the exact base and candidate; disposition every
base ID absent at candidate. A sharded run is only a candidate full-denominator
profile when its disjoint union equals candidate IDs, every shard's raw exit
is successful, and omitted/duplicated-ID controls refuse. That alone does not
prove canonical behavior: CI documents xdist hiding mutually polluting test
failures. Qualify fixture, environment, order and cross-shard equivalence
independently, keeping order-sensitive integration serial; until then the
canonical full-suite claim is UNKNOWN/HOLD. Final release additionally needs
installed-consumer proof. Neither guessed timeout increases nor marker-only
routing substitutes for these obligations.

## Frozen opposite arms before implementation

Measured full PASS; introduced failure; inherited failure; timeout; collection
abort; wrong-run/stale receipt; nonzero raw exit with pass-looking output;
coverage timeout or unparseable output; empty, missing or duplicated test ID;
changed dependency whose relevant test is omitted. Every arm must exercise
the actual gate consumer, not just the capture parser. Retire conflicting
command prose and redundant wrappers only after these behaviors are proven.

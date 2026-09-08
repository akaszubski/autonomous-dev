---
covers:
  - .github/workflows/
---

# GitHub Actions Integration

Automated PR review and issue implementation using Claude via `anthropics/claude-code-action`.

## Setup

### 1. Add the API Key Secret

1. Go to your GitHub repository **Settings > Secrets and variables > Actions**
2. Click **New repository secret**
3. Name: `ANTHROPIC_API_KEY`
4. Value: Your Anthropic API key
5. Click **Add secret**

### 2. Workflows Included

| Workflow | Trigger | File |
|----------|---------|------|
| Claude Code Review | PR opened/updated, `@claude` comment | `.github/workflows/claude-review.yml` |
| Claude Issue Implementation | Issue labeled `claude-implement` | `.github/workflows/claude-implement.yml` |
| Auto-tag on push | Push to `master` (non-log paths) | `.github/workflows/auto-tag-on-push.yml` |
| CI | Push/PR to `master`/`main`, manual dispatch | `.github/workflows/ci.yml` |

### CI Workflow (`ci.yml`)

Three-stage pipeline: **Smoke** (fast sanity checks, Stage 1) → **Full Test Suite** (unit + integration + regression, Stage 2, depends on smoke) → **CI Summary** (merge gate, Stage 3, always runs). A conditional **GenAI Intent Tests** job (Stage 1.5) also runs after smoke when the `OPENROUTER_API_KEY` repo variable is set.

The CI Summary gate uses positive assertions: it blocks merge unless `SMOKE_RESULT` is exactly `"success"` and `TEST_RESULT` is `"success"` or `"skipped"`. Any other conclusion — including `cancelled` and `timed_out` — is treated as blocking. This prevents silently allowing merges when jobs time out or are cancelled before completion. (Issue #1333)

**Full Test Suite — Route tests pre-step and parallelization (Issue #1332)**: The `test` job begins with a `Route tests` step (`id: route`) that calls `route_tests()` from `plugins/autonomous-dev/lib/test_routing.py`. When the routing result sets `skip_all=true` (e.g., for docs-only PRs), the install and all three pytest steps are short-circuited via `if:` guards, so documentation-only changes do not consume the full job budget. When the suite does run, all three pytest steps (unit, integration, regression) use `pytest-xdist` with `-n auto` to parallelize across available runner cores, which is the primary wall-clock fix for a genuinely slow suite. Regression tests asserting this structure live in `tests/regression/test_ci_workflow_routing.py`.

**Every pytest invocation must carry a per-test timeout (Issue #1567)**: Parallelization does not help a *hung* test — a single non-terminating test previously burned the entire `test` job's budget (then 15, later 60 minutes) and GitHub Actions recorded the job as `cancelled` with no test results at all, for about three months, before this was diagnosed. Every `python -m pytest ...` line in every `.github/workflows/*.yml` job now carries `--timeout=<seconds> --timeout-method=signal`, backed by `pytest-timeout` in that job's own `pip install` step (the plugin must be installed in the *same* job that uses the flag — pytest hard-errors on an unrecognized argument otherwise). `--timeout-method=signal`, not `thread`: `thread` kills the whole pytest process on timeout, which reproduces the exact "no results at all" failure this exists to prevent; `signal` fails the one hung test by name, with a stack trace, and lets the rest of the suite run. The per-test bound must also stay meaningfully below the job's own `timeout-minutes` cap (enforced at a ≤50% ratio) — a bound at or near the job cap races the job-level cancellation instead of pre-empting it and never actually fires.

A class-wide regression guard, `tests/regression/test_ci_pytest_timeout.py`, parses every workflow file and hard-fails a PR that adds a pytest invocation with no `--timeout`, uses `--timeout-method=thread`, sets a `--timeout` too close to its job's cap, or adds a `--timeout` flag without adding `pytest-timeout` to that job's install line. **Trap**: several steps invoke pytest with `-o "addopts="`, which clears whatever `addopts` a `pytest.ini`/`pyproject.toml` declares for that run — a config-based `addopts = --timeout=...` would be silently discarded in those steps, so the flag must be passed on the command line, per invocation. New pytest invocations added to a workflow must follow the same pattern: bound, `signal`-method, and backed by an install of `pytest-timeout` in that job.

**Test suites report independently — a red suite does not hide the ones after it (Issue #1580)**: fixing the hang in #1567 let a `Full Test Suite` run complete for the first time in months, and the completed run immediately showed the next layer of the same problem: the unit step failed and the integration and regression steps were both recorded `skipped`. The three pytest steps in the `test` job's `if:` carried only `steps.route.outputs.skip_all != 'true'`, and GitHub Actions applies an implicit `success()` status check to any `if:` expression that names no status-check function — so a failing sibling step suppressed every step after it. All three steps now carry `!cancelled()`, so each suite's pass/fail is reported regardless of whether an earlier suite in the same job failed. Use `!cancelled()`, not `always()`: GitHub's own documentation names `!cancelled()` the recommended alternative, because `always()` additionally runs steps after a human deliberately cancels the run. **Do not reach for `continue-on-error` here** — it is the obvious-looking fix and it is wrong: it would let the job report `success` while a suite underneath it is failing, trading an invisible-but-honest signal for a visible-but-false one. A test step's failure must still fail that step and still fail the job; the only thing removed is the suppression of *later, independent* steps. `tests/regression/test_ci_pytest_timeout.py` also guards this class: it discovers every job with two or more pytest-running steps directly from the parsed YAML (never a hardcoded job list, so a fourth suite is covered without a test edit), asserts none of them can be silently skipped by a sibling's failure, and asserts no test step carries `continue-on-error`.

**Adding `!cancelled()` removes a gate you still need — name it back (Issue #1580)**: GitHub adds an implicit `success()` only to an `if:` that contains *no* status-check function. `!cancelled()` is one, so the moment it is added the implicit `success()` is gone — and that implicit gate was load-bearing: it is what made a failed `Install dependencies` skip the suites instead of running three suites' worth of `ModuleNotFoundError`. That output is indistinguishable in the log from genuine test failures (Issue #1579 records that many current unit failures already *are* missing-dependency import errors), so it is the same signal-integrity disease re-entering through a different door. Every prerequisite therefore has an `id:` and is named back explicitly: `if: ${{ !cancelled() && steps.checkout.outcome != 'failure' && steps.setup_python.outcome != 'failure' && steps.install.outcome != 'failure' && steps.route.outputs.skip_all != 'true' }}`.

Note the deliberate asymmetry: `Route tests` is *not* gated on. It is engineered to fail open — it carries `continue-on-error: true`, and if its pipeline breaks nothing is written to `$GITHUB_OUTPUT`, so `skip_all` is unset and every suite runs. A broken router must not silence the suites. A broken install must. One predecessor should not gate; the other must.

Two forms are wrong and are rejected by the guard. Use `outcome`, not `conclusion` — `conclusion` is the value *after* `continue-on-error` is applied, so a prerequisite that later gains `continue-on-error: true` would read `success` while broken, disarming the gate from an unrelated diff. Use `!= 'failure'`, not `== 'success'` — a step's `outcome` is `skipped` when its own `if:` is false, which is exactly what happens to `Install dependencies` when the router sets `skip_all`; treating that skip as grounds to suppress the suites is silent suppression on a non-failure. The guard derives *which* prerequisites must be gated on from the parsed job structure (every earlier step that is neither a sibling suite nor `continue-on-error: true`), so a setup step added later is covered without a test edit and no step name is hardcoded.

**P0-A private-carrier observer hard gate (Issue #1760)**: the `smoke` job also runs `tests/bootstrap/test_plugin_carrier_bootstrap.py` — the frozen node that self-tests a stdlib-only, product-import-free observer of Claude Code execution, created together with the immutable acceptance manifest `tests/acceptance/plugin-carrier-p0.json` ahead of any carrier implementation, so that a later candidate is judged against frozen bytes rather than against a description it could rewrite to fit. The frozen contract is `docs/plans/20260907-plugin-native-distribution-amendment.md` (`## 4`).

The step is a hard gate: `set -euo pipefail`, no `continue-on-error`, no `|| true`, no ratchet, no `--maxfail`, and no pipe that could launder an exit code. It runs three checks in order, each able to fail the job on its own:

1. **The frozen-byte check, before pytest.** Every subject bound in `cases[P0-C01].subject_digests` is re-digested and compared. It runs first, and it lives in the workflow rather than in the artifact it judges — so it still refuses when the node's own in-file digest reader has been neutered. That externality is the only reason a test file can be trusted to guard itself.
2. **The frozen node**, under `--timeout=20 --timeout-method=signal`. The flag is a floor for a hypothetical unmarked test, not the bound on this node: every test here carries an explicit `@pytest.mark.timeout` marker, a marker overrides the CLI default, and `test_manifest_budget_matches_the_declared_timeout_marker` refuses the node if any test lacks one. The flag is retained because Issue #1567 requires every pytest invocation in these workflows to carry one.
3. **A JUnit re-read**, from `${RUNNER_TEMP:-/tmp}` — outside the working tree, so running the gate locally cannot add an untracked file and move the changeset's own pin. pytest exits `0` on skips, so the exit code alone is not a completeness check; the re-read asserts `failures==0`, `errors==0`, `skipped==0` and that the collected node count is **exactly** `cases[P0-C01].collection_completeness.expected_test_count`. That count is not restated in the workflow — it has one home in the manifest, and `test_manifest_declared_node_count_equals_pytest_collected_count` pins that field to what pytest actually collects, so it cannot drift in either direction without something refusing. An earlier revision used a floor, which would have permitted frozen tests to be deleted silently.

A fourth surface guards the step itself, from inside the frozen node: `tests/bootstrap/test_plugin_carrier_bootstrap.py` re-parses this workflow and requires the P0-A step's `run:` body to equal `cases[P0-C01].run_block` line for line. Editing the step — including merely re-wrapping a line continuation — turns the build red, and needs a replacement freeze commit rather than an in-place edit.

Unlike its two `smoke` siblings, this step satisfies both guards described above. The five `smoke` setup steps each carry a stable `id:` — `checkout`, `setup-python`, `install-deps`, `validate-test-categorization`, `validate-hook-sidecar` — and the step reads:

```yaml
if: ${{ !cancelled()
  && steps.checkout.outcome != 'failure'
  && steps.setup-python.outcome != 'failure'
  && steps.install-deps.outcome != 'failure'
  && steps.validate-test-categorization.outcome != 'failure'
  && steps.validate-hook-sidecar.outcome != 'failure' }}
```

`!cancelled()` stops a red sibling from silently skipping the gate; because it also removes GitHub's implicit `success()`, every prerequisite is named back explicitly, so a broken `pip install` cannot report a P0-A failure that is not one. `outcome` and `!= 'failure'` are used for the reasons given above. Do not switch to `conclusion`, and do not add `continue-on-error` to any step this condition names: `outcome` is evaluated *before* `continue-on-error`, so a tolerated prerequisite failure would make this condition false and skip the gate while the job stayed green.

`jsonschema` is installed in this step rather than relied on as another step's side effect, so the gate does not depend on install ordering elsewhere in the job.

Scope: the sibling steps `Append-mode writer ratchet (Issue #1718)` and `Run smoke tests` carry no status-check function and remain Issue #1580 offenders. Completing them is #1580's repo-wide work, not this step's, and they are deliberately left unmodified.

## Usage

### Automated PR Review

Every pull request automatically receives a Claude review on open, synchronize, and reopen events. Claude reads `CLAUDE.md` for project conventions and focuses on code quality, test coverage, security, and documentation.

To request additional review feedback on an existing PR, leave a comment containing `@claude` with your question or request.

### Issue Auto-Implementation

To have Claude implement a GitHub issue automatically:

1. Create a GitHub issue with a clear title and description
2. Add the label `claude-implement` to the issue
3. Claude will read the issue, implement a solution, and open a PR

The PR will reference the original issue. Review the PR as you would any human-authored code.

## Security Considerations

- **API key**: Stored as a GitHub secret, never exposed in logs or workflow files
- **Permissions**: Workflows use minimal required permissions (read contents, write PRs/issues)
- **Model**: Uses Sonnet (not Opus) to manage CI costs
- **Concurrency**: Duplicate runs are cancelled automatically via concurrency groups
- **Review required**: Auto-generated PRs still require human review and approval before merge
- **Tool access**: Review workflow has read-only tools; implementation workflow has write access limited to the PR branch

### Auto-tag on push

Every push to `master` (excluding `.claude/logs/**`) runs `.github/workflows/auto-tag-on-push.yml`, which:

1. Reads the plugin version from `plugins/autonomous-dev/.claude-plugin/marketplace.json` (validated as `N.N.N`)
2. Computes a 7-char SHA suffix via `git rev-parse --short=7 HEAD`
3. Emits an annotated tag of the form `autonomous-dev-v<version>+<sha7>`
4. Pushes the tag to origin (idempotent — skips if the tag already exists)

The tag is consumed by `scripts/pull-plugin-update.sh` running on consumer Macs via a launchd timer. See the "Consumer-side auto-update (launchd)" section of [RUNBOOK.md](../docs/RUNBOOK.md) for setup instructions.

**Credentials**: only `secrets.GITHUB_TOKEN` is used (no custom SSH keys required). **Permissions**: `contents: write` only, with a 3-minute job timeout and a `cancel-in-progress: false` concurrency group.

## Cost Management

The Claude review and issue-implementation workflows use `claude-sonnet-4-5-20250929` to keep CI costs reasonable. The concurrency groups prevent duplicate runs when PRs are updated rapidly. The auto-tag workflow uses only standard GitHub Actions (no Anthropic API calls) — it is always free.

## Troubleshooting

**Workflow not triggering**: Verify the `ANTHROPIC_API_KEY` secret is set and the workflow files are on the default branch.

**Permission errors**: Ensure the repository settings allow GitHub Actions to create pull requests (Settings > Actions > General > Workflow permissions > Read and write).

**Rate limits**: If you hit Anthropic API rate limits, consider adding delays or reducing concurrent workflow runs.

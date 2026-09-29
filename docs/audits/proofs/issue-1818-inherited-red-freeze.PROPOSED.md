# #1818 inherited-red gate: frozen initial cases (not acceptance)

Frozen before #1818 protected edits on source HEAD `bebf2a845c92bad1f87da257c1bb106a7658e353`, 2026-09-30. Authority: [PROJECT.md](../../../PROJECT.md) INV-1/6/7 and Q1/Q2, [#1818](https://github.com/akaszubski/autonomous-dev/issues/1818), and the [#1846 gate contract](issue-1846-test-gate-contract.PROPOSED.md). Earlier `issue-1818-prep.json` from the separate `pytest-gate-1818-lean` worktree was read as historical input, **not** reused as the current baseline: it recorded two red IDs on another checkout. This freeze has one owner for capture and receipt; no second runner/store and no bypass.

## Fixed diagnostic denominator and measured base

Run from `/Users/akaszubski/Dev/autonomous-dev-1779` with Python 3.14. The exact selected command is:

```sh
python3 -m pytest -o addopts='' --no-cov --tb=no -q \
  tests/unit/test_fix_forward_classification.py \
  tests/unit/lib/test_fix_forward_capture_failure.py \
  tests/unit/lib/test_agent_ordering_gate_pytest_gate.py \
  tests/unit/lib/test_pipeline_completion_state_pytest_gate.py \
  tests/regression/test_implement_pytest_gate_wiring.py \
  tests/regression/test_issue_1533_baseline_collection_error.py \
  tests/regression/test_issue_1228_ordering_gate_sid_fallback.py \
  tests/unit/commands/test_implement_fix_mode.py::TestImplementFixCommandFile::test_minimum_agents \
  'tests/unit/lib/test_append_writer_ratchet.py::test_every_pinned_writer_still_exists_and_still_appends[plugins/autonomous-dev/lib/pipeline_completion_state.py]'
```

Collection used the same selectors with `python3 -m pytest -o addopts='' --collect-only -q`. Collection raw exit **0**, 134 IDs. SHA-256 of lexically sorted node IDs, each terminated by `\n`: `4e98a793c1ce6466aa659be7d78e8d0b321d5cdc53393c52f0ed0bd98d996928`. Execution raw exit **1**: 133 passed, one failed, zero errors, 14.44 s. The one inherited red is `tests/unit/commands/test_implement_fix_mode.py::TestImplementFixCommandFile::test_minimum_agents`. This is a diagnostic slice only: no full-suite, native Claude, or installed-consumer claim. Recollect and compare the exact candidate universe; absent base IDs require explicit disposition, not silent omission.

Existing exact IDs to retain in the changed-behavior denominator:

```text
tests/unit/lib/test_agent_ordering_gate_pytest_gate.py::TestPytestGateOrdering::test_reviewer_blocked_without_pytest_gate
tests/unit/lib/test_agent_ordering_gate_pytest_gate.py::TestPytestGateOrdering::test_reviewer_allowed_with_pytest_gate
tests/regression/test_implement_pytest_gate_wiring.py::test_implement_step8_pytest_gate_recording
```

## Frozen RED opposite arms

Implement these as `tests/regression/test_issue_1818_evidence_bound_pytest_gate.py` IDs (the file does not exist at freeze). A scoped diagnostic receipt must arise only from an owned, completed pytest invocation with exact collected/executed IDs, raw exit, base/candidate/worktree/config binding and artifact digests. It can support comparison, **not F4/formal specialist-order credit**. The actual ordering consumer must refuse invalid or diagnostic-only gate claims; a model statement or `record_pytest_gate_passed(passed=True)` alone has no authority.

| ID suffix (`test_...`) | Required decision at actual consumer |
|---|---|
| `test_inherited_failure_and_error_diagnostic_hold` | A complete base-bound run with only inherited red may produce a scoped diagnostic comparison receipt; F4 and formal specialist order remain **HOLD**. |
| `test_new_failure_refuses`, `test_new_error_refuses` | Any candidate-only failure/error refuses, even beside inherited red. |
| `test_missing_required_id_refuses`, `test_required_skip_refuses`, `test_required_xfail_refuses` | Missing, skipped or xfailed required changed-behavior IDs refuse. |
| `test_truncated_denominator_refuses`, `test_early_exit_args_refuse` | Partial execution or selection-shrinking options refuse. |
| `test_stale_candidate_receipt_refuses`, `test_transplanted_receipt_refuses`, `test_wrong_base_or_repo_refuses` | Wrong run, repo, worktree, base, candidate or dependency/config binding refuses at consumption. |
| `test_forged_result_without_owned_run_refuses`, `test_receipt_completion_atomic_failure_refuses` | Caller-crafted verdict, incomplete publication or broken receipt/artifact linkage refuses. |
| `test_consumer_blocks_missing_receipt`, `test_consumer_rejects_focused_as_full_clean` | No receipt or a diagnostic scope claiming full clean refuses. |
| `test_consumer_permits_measured_full_green_receipt` | The opposite positive arm permits F4 only for a verified, complete, exit-zero **full-denominator** receipt on the same run. A tiny isolated fixture can test the transition, but does not prove this repository's canonical suite or product acceptance. |

Also retain the prep's exact `test_prepare_freezes_exact_ids_and_base`, `test_prepare_refuses_missing_or_empty_denominator`, `test_prepare_records_fail_and_error_ids`, `test_required_cases_pass_with_owned_pytest`, `test_caller_flaky_exclusion_cannot_launder_new_failure`, and `test_silent_fingerprint_timeout_refuses` IDs. All cases must fail RED against the pre-edit consumer for the intended reason (or be marked `UNMEASURED` with reason), then pass after repair. One adversarial counterfactual must disable/forge the receipt carrier and cause refusal. No fixed test count is itself a product invariant; the 134-ID count/digest pins only this diagnostic base.

## Non-promotion boundary

The current full canonical suite is inherited-red and previously timed out; its positive F4 arm is **UNMEASURED**. Neither this focused run nor its prior prep grants `pytest-gate` full-denominator completion. There is no interim positive F4 on inherited-red. Before #1818 is accepted: verify source caller → capture owner → signed evidence-bound receipt → real ordering gate on both arms; separately prove native CLI permissions and installed bytes without source fallback. Keep security, deployment and release gates unchanged. Until those proofs exist, status is **PROPOSED / HOLD**.

"""Case-manifest completeness and the frozen carrier facts: the manifest is the
denominator, and a case not fully specified can never be re-run or disproved."""

from __future__ import annotations

import json

import pytest

import _harness as H

# Externally reviewed floors, injected from THIS file rather than read from the
# manifest. A check that iterates zero cases passes every per-case assertion.
REVIEWED_MIN_CASES = 12
REVIEWED_MIN_MEASURED = 4

REQUIRED_TOP = set(
    "id subject stimulus expected opposite_arm fault_arm mutant runner carrier "
    "denominator invalidation measurement".split()
)
REQUIRED_EXPECTED = set(
    "collect_exit run_exit selected_ids selected_count forbidden_effects".split()
)
REQUIRED_RUNNER = {"executable", "argv", "cwd", "config", "plugins", "timeout_s"}

# There is no FROZEN/UNOBSERVED vocabulary; it was deleted. A state outside this
# set means the manifest has grown a way to say "not checked" that reads like a
# pass.
MEASUREMENT_STATES = {"MEASURED", "UNMEASURED"}
# Proximity is not a join: these may appear only inside forbidden_effects.
FORBIDDEN_JOIN_TERMS = ("timestamp_proximity", "session_proximity", "temporal_correlation")


@pytest.fixture(scope="module")
def doc():
    H.require(H.CASES, "bootstrap/control_trust/cases.json")
    parsed = json.loads(H.CASES.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict) and parsed.get("cases"), f"not a manifest: {parsed!r:.120}"
    return parsed


def test_case_denominator_meets_the_reviewed_floors(doc):
    # VACUITY GUARD for every per-case check below: they all iterate `cases`, so
    # an empty or near-empty manifest would make this whole file green.
    cases = doc["cases"]
    assert len(cases) >= REVIEWED_MIN_CASES, f"{len(cases)} cases < {REVIEWED_MIN_CASES}"
    measured = [c for c in cases if c.get("measurement", {}).get("state") == "MEASURED"]
    # A manifest of entirely unmeasured cases is a plan, not evidence.
    assert len(measured) >= REVIEWED_MIN_MEASURED, f"{len(measured)} MEASURED is too few"
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == len(ids), f"duplicate case ids: {ids!r}"


def test_every_case_is_fully_specified(doc):
    # Measured or not, every case carries the whole shape: an UNMEASURED case
    # that omits its expected values can never be measured later. Two named
    # denominator sources, because one source can only confirm itself. Both
    # arms, because a case with only a positive arm cannot distinguish "the
    # guard works" from "the guard cannot fail". An invalidation list, because
    # evidence that can never be retired is a claim, not a measurement.
    complaints = []
    for case in doc["cases"]:
        cid = case.get("id", "<no id>")
        for label, required, got in (
            ("", REQUIRED_TOP, case),
            (".expected", REQUIRED_EXPECTED, case.get("expected", {})),
            (".runner", REQUIRED_RUNNER, case.get("runner", {})),
        ):
            complaints += [f"{cid}{label}: missing {m}" for m in sorted(required - set(got))]

        sources = case.get("denominator")
        if not isinstance(sources, list) or len(set(sources)) != 2:
            complaints.append(f"{cid}: denominator must name two DISTINCT sources")
        if not case.get("opposite_arm"):
            complaints.append(f"{cid}: no opposite arm")
        if not case.get("fault_arm"):
            complaints.append(f"{cid}: no fault arm")
        if not isinstance(case.get("invalidation"), list):
            complaints.append(f"{cid}: invalidation must be a list")

        state = case.get("measurement", {}).get("state")
        if state not in MEASUREMENT_STATES:
            complaints.append(f"{cid}: measurement.state={state!r} is not a valid state")
        elif state == "UNMEASURED" and not case["measurement"].get("reason"):
            complaints.append(f"{cid}: UNMEASURED with no reason")
    assert complaints == [], f"{len(complaints)} manifest defects: {complaints!r}"


def test_absent_capabilities_are_unmeasured_cases_never_skips(doc):
    # Zero pytest skips. shellcheck is not installed locally and descendant
    # process cleanup is not established; each must appear as an UNMEASURED case
    # with a reason rather than as a silently missing one.
    states = {c["id"]: c.get("measurement", {}) for c in doc["cases"]}
    live = [(cid, m) for cid, m in states.items() if m.get("state") == "UNMEASURED"]
    unmeasured = {cid: m.get("reason", "") for cid, m in live}
    assert unmeasured, "no UNMEASURED cases at all, which claims more than was measured"
    thin = [cid for cid, reason in unmeasured.items() if len(reason.strip()) <= 10]
    assert not thin, f"UNMEASURED cases carrying no real reason: {thin!r}"


# ===========================================================================
# Frozen carrier facts -- ALREADY MEASURED, asserted as data
# ===========================================================================

FROZEN_CARRIER_FACTS = {
    "hook_response_records_carrying_tool_use_id": 0,
    "hook_response_records_examined": 7,
    "dispatcher_otel_carries_tool_use_id": False,
    "dispatcher_otel_carries_hook_id": False,
    "dispatcher_otel_traceid_defined": False,
    "dispatcher_otel_spanid_defined": False,
    "pretooluse_ingress_carries_session_id": True,
    "pretooluse_ingress_carries_prompt_id": True,
    "pretooluse_ingress_carries_tool_use_id": True,
    "posttooluse_ingress_carries_session_id": True,
    "posttooluse_ingress_carries_prompt_id": True,
    "posttooluse_ingress_carries_tool_use_id": True,
    "stream_json_content_id_matches_tool_use_id": True,
    "text_output_format_log_exporters": 1,
    "stream_json_include_hook_events_log_exporters": 0,
    "stream_json_include_hook_events_reported_enabled": True,
}


def test_manifest_records_the_frozen_carrier_facts_unchanged(doc):
    # F0 asserts them as DATA and does not re-measure: a re-measurement would
    # silently overwrite the finding with whatever this environment produces.
    #
    # CONSOLIDATION: the separate exporter-control test asserted three of these
    # literals against the copy defined in THIS file, which is a comparison of a
    # constant to itself. Its obligation -- that the frozen block keeps the
    # positive arm as well as the negative one -- is owned here instead, against
    # the MANIFEST's recorded copy, which is external data.
    recorded = doc.get("carrier_facts")
    assert recorded, "cases.json records no carrier_facts block"
    drifted = [k for k, v in FROZEN_CARRIER_FACTS.items() if k not in recorded or recorded[k] != v]
    assert not drifted, f"frozen findings dropped or re-measured: {drifted!r}"
    # "enabled=true" coexisted with ZERO exporters; the text-format configuration
    # that DOES produce one is what stops zero meaning "exporters never work here".
    assert recorded["stream_json_include_hook_events_reported_enabled"] is True
    assert recorded["stream_json_include_hook_events_log_exporters"] == 0
    assert recorded["text_output_format_log_exporters"] > 0, "no positive control"


def test_the_tool_to_hook_to_otel_join_stays_unmeasured(doc):
    # Nothing may convert timestamp or session proximity into a join -- that
    # would manufacture a causal claim out of coincidence.
    join = doc.get("join_status")
    assert join, "cases.json records no join_status"
    assert join.get("state") == "UNMEASURED", f"the join is claimed: {join.get('state')!r}"
    assert join.get("reason"), "the UNMEASURED join carries no reason"
    for case in doc["cases"]:
        blob = json.dumps(case).lower()
        effects = json.dumps(case["expected"]["forbidden_effects"]).lower()
        leaked = [t for t in FORBIDDEN_JOIN_TERMS if t in blob and t not in effects]
        assert not leaked, f"case {case['id']} claims {leaked!r} outside forbidden_effects"

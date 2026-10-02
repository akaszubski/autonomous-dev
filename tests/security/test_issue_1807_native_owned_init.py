#!/usr/bin/env python3
"""Native-owned run initialization and progression (Issue #1807, A7/A9).

WHAT THIS FILE IS FOR. Every run-authority carrier the #1807 controls check —
the signed sentinel, the per-run secret ``sign_state`` mints, and the run-start
receipt ``record_run_start`` stamps — is currently initiated by MODEL-OWNED
coordinator Bash (``commands/implement.md`` STEP 0, ``commands/implement-fix.md``
F1). The same principal the controls constrain mints the authority they check, so
a per-run-secret-backed MAC is still model-mintable. This file freezes the
acceptance arms for the NATIVE-OWNED entrypoint that closes that gap, and
executes the ones that are decidable without a native venue.

THE TWO ORIGIN CLASSES ARE NOT INTERCHANGEABLE. A user-typed ``/implement``
fires ``UserPromptExpansion``; a model-invoked ``Skill`` tool call fires
``PreToolUse`` with ``tool_name=Skill``. BOTH are native EVENTS, and the event
name mechanically distinguishes them — but only the typed one carries USER
authorization. The model chooses when to call ``Skill``, so treating a
Skill-origin witness as user-authorized would hand the model a native carrier
for self-minting current-run authority. ``RunOrigin.MODEL_SKILL_WITNESSED`` is
therefore recorded, distinguishable, and NEVER promotable to
``RunOrigin.TYPED_USER_WITNESSED``. The #1802 tie-in follows from the same rule:
nothing here may let a Skill origin, an env var, or a caller-supplied flag stand
in for a real interactive approval bound to this run.

EVIDENCE LIMIT — read before quoting any green from this file.

* Payload shape NEVER proves native origin: a model that pipes fabricated stdin
  into the hook can present byte-identical fields, including ``command_source``.
  What would make the origin unforgeable is the OS boundary, and that composition
  is OUT of this slice.
* Everything green below is evidence class ``library-route``. Every
  ``native-boundary`` arm in :data:`NATIVE_VENUE_MATRIX` stays ``UNMEASURED``.
* The matrix's ``required_joins`` and ``native_expectation`` fields, and the
  module-level :data:`_REQUIRED_EFFECTS`, are FROZEN SPEC TEXT describing what a
  future admitted native trial must OBSERVE. No test in this file observes a
  native join or a byte effect, and the shape tests below validate the spec text
  only — they are not, and must never be read as, captured evidence.
* A7/A9/F0 remain OPEN whatever colour this file shows.

GitHub Issue: #1807
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

# tests/security/<this file> -> security -> tests -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOK_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
for _p in (str(_REPO_ROOT), str(_LIB_DIR), str(_HOOK_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pipeline_completion_state as pcs  # noqa: E402
import pipeline_state as ps  # noqa: E402

from tests.helpers.sanctioned_run import (  # noqa: E402
    clear_run_artifacts,
    sanctioned_state,
)
from tests.helpers.state_isolation import redirect_pipeline_state  # noqa: E402

_OWNER = "sess-1807-native-origin"
_OTHER_OWNER = "sess-1807-native-origin-other"


# ===========================================================================
# THE FROZEN NATIVE-VENUE MATRIX — ONE HOME FOR THE WHOLE INVENTORY
# ===========================================================================
#
# ONE keyed table. The arm id set, the arm count, and every parametrized offline
# behavioural case are DERIVED from it below — four homes for one inventory is
# how an inventory drifts. Mutation of any byte of this table changes
# :data:`_FROZEN_MATRIX_SHA256` and fails
# ``test_matrix_digest_detects_one_sided_drift``, which is a DRIFT TRIPWIRE and not
# a tamper-proof freeze (the constant lives in this module; see that test's
# docstring for the exact property it does and does not establish).
#
# Per-arm fields:
#   native_expectation  — FROZEN SPEC TEXT: what the admitted native trial must
#                         observe. Not observed here.
#   covering_mechanism  — the mechanism claimed to cover the arm, or the literal
#                         "undetermined" where it is genuinely unknown.
#   required_joins      — FROZEN SPEC TEXT: the ids that must link request ->
#                         hook receipt -> file effect in that future trial. It is
#                         EVENT-SPECIFIC (see the three sets below) and no test
#                         here captures one.
#   offline_cases       — the library-route half, keyed by case name, each naming
#                         the runner ``kind`` that executes it. An arm with no
#                         offline case is native-only and honestly says so.

#: Joins for arms whose venue is a TYPED SLASH-COMMAND EXPANSION. There is NO
#: tool call here — ``UserPromptExpansion``'s documented input carries
#: ``command_name``, ``command_args``, ``command_source``, ``prompt`` and
#: ``session_id`` and NO ``tool_use_id``. Requiring one would force a future trial
#: to SYNTHESIZE an id, which is precisely the fabricated-evidence failure #1807
#: exists to refuse.
_TYPED_EXPANSION_JOINS = (
    "session_id",
    "command_name",
    "command_args",
    "command_source",
    "prompt",
    "hook_receipt",
    "file_effect",
)

#: Joins for arms where a TOOL CALL actually exists (PreToolUse: Skill, Bash,
#: Write/Edit, an MCP editor). ``tool_use_id`` is required ONLY here.
_TOOL_CALL_JOINS = (
    "session_id",
    "run_id",
    "tool_use_id",
    "hook_receipt",
    "file_effect",
)

#: Joins for arms whose subject is the DEPLOYMENT rather than a request: neither
#: a command expansion nor a tool call exists to join against.
_DEPLOYMENT_JOINS = ("session_id", "hook_receipt", "file_effect")

#: Every join set, whatever the venue, must carry these three.
_UNIVERSAL_JOINS = frozenset({"session_id", "hook_receipt", "file_effect"})

#: Byte-level effects every native-venue observation must carry. UNIVERSAL rather
#: than per-arm: unlike the joins, which are event-specific, "show me the bytes
#: before and after, at this path" applies to every arm without exception.
_REQUIRED_EFFECTS = ("pre_sha256", "post_sha256", "path")

NATIVE_VENUE_MATRIX: Dict[str, Dict[str, Any]] = {
    "P-TYPED-FULL": {
        "native_expectation": (
            "a real user-typed `/implement` fires UserPromptExpansion; the "
            "native initializer records a TYPED_USER witness and the run's "
            "sentinel, per-run secret and ledger receipt all appear"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "native UserPromptExpansion hook registration",
        "required_joins": _TYPED_EXPANSION_JOINS,
        "offline_cases": {
            "library-route": {"kind": "typed_positive", "args": ""},
        },
    },
    "P-TYPED-FIX": {
        "native_expectation": (
            "a real user-typed `/implement --fix` fires UserPromptExpansion with "
            "command_args carrying --fix; same effects as P-TYPED-FULL, under "
            "the SAME one installed policy"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "native UserPromptExpansion hook registration",
        "required_joins": _TYPED_EXPANSION_JOINS,
        "offline_cases": {
            "library-route": {"kind": "typed_positive", "args": "--fix"},
        },
    },
    "P-SPELLING-OBSERVED": {
        "native_expectation": (
            "a live Claude Code 2.1.236 --plugin-dir plan-mode probe on 2026-09-30 "
            "observed UserPromptExpansion with command_name "
            "`autonomous-dev:implement`, command_args `--fix #1807`, and a signed "
            "session-bound witness. The recognizer must accept exactly this "
            "registered namespace and refuse unrelated or suffix-laundered "
            "namespaces. This is a spelling/registration observation only: the "
            "full installed workflow, six-binding bootstrap, and A9 containment "
            "remain UNMEASURED"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "undetermined",
        "required_joins": _TYPED_EXPANSION_JOINS,
        "offline_cases": {
            "observed-plugin-namespace": {
                "kind": "named",
                "test": "test_observed_plugin_namespace_mints_typed_witness_but_other_namespaces_refuse",
            },
        },
    },
    "P-SKILL": {
        "native_expectation": (
            "a model-invoked Skill(implement) fires PreToolUse tool_name=Skill "
            "and the initializer records a MODEL_SKILL witness. EVENT COVERAGE "
            "only: user authorization is NOT conferred and the origin is never "
            "promotable to TYPED_USER"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "native PreToolUse Skill hook registration",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "library-route": {
                "kind": "named",
                "test": "test_model_skill_origin_is_recorded_but_confers_no_user_authorization",
            },
            "not-typed-user": {
                "kind": "named",
                "test": "test_skill_origin_cannot_be_laundered_into_typed_user_origin",
            },
        },
    },
    "P-EFFECTS": {
        "native_expectation": (
            "authentic sentinel / per-run key / ledger effects observed pre and "
            "post with byte hashes, never inferred from a hook exit code"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "pre/post byte hashing of the three carriers",
        "required_joins": _TYPED_EXPANSION_JOINS,
        "offline_cases": {},
    },
    "N-BASH": {
        "native_expectation": (
            "model Bash invoking the initializer directly is DENIED at the OS "
            "boundary (sandbox denyWrite on the carriers)"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "OS sandbox denyWrite for subprocesses",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "tool-name-not-skill": {
                "kind": "payload",
                "builder": "skill",
                "overrides": {"tool_name": "Bash"},
                "caller": _OWNER,
            },
            "witness-unbound": {"kind": "chain", "expect": "WITNESS_REFUSED"},
            "append-without-witness": {
                "kind": "append",
                "mint_witness": False,
                "pre_bind": False,
                "overrides": {},
            },
        },
    },
    "N-BUILTIN": {
        "native_expectation": (
            "a built-in Write/Edit forging the witness or the sentinel is DENIED "
            "by permissions.deny Edit(//abspath) — measured 2026-09-27 for "
            "BUILT-IN editors only"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "permissions.deny Edit(//abspath) for built-in editors",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "witness-unsigned": {"kind": "chain", "expect": "WITNESS_REFUSED"},
            "witness-mac-tampered": {"kind": "chain", "expect": "WITNESS_REFUSED"},
        },
    },
    "N-MCP": {
        "native_expectation": (
            "an MCP editor attempting to forge the witness must be DENIED under "
            "the same ONE installed policy. The COVERING MECHANISM IS "
            "UNDETERMINED: native permission rules cover built-in editors, and a "
            "real MCP editor was previously observed FALSE-PERMITTED via a "
            "relative_path, so whether coverage comes from an installed "
            "matcher plus path extraction or from an observed OS effect refusal "
            "is unknown. This arm has NO offline-decidable component — a MAC "
            "rejection is not an MCP denial — and stays UNMEASURED until a real "
            "MCP editor is observed refused"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "undetermined",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {},
    },
    "N-STDIN": {
        "native_expectation": (
            "a PERFECT fabricated-stdin forgery is decided by the OS boundary "
            "ONLY and is honestly UNMEASURED here; the offline half refuses every "
            "malformed, contradictory or unusable payload shape"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": (
            "payload-shape validation offline; OS boundary for the perfect forgery"
        ),
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "payload-not-a-dict": {
                "kind": "payload",
                "builder": "raw",
                "overrides": "not-a-dict",
                "caller": _OWNER,
            },
            "payload-empty": {
                "kind": "payload",
                "builder": "raw",
                "overrides": {},
                "caller": _OWNER,
            },
            "event-unknown": {
                "kind": "payload",
                "builder": "typed",
                "overrides": {"hook_event_name": "UserPromptSubmit"},
                "caller": _OWNER,
            },
            "event-missing": {
                "kind": "payload",
                "builder": "typed",
                "overrides": {"hook_event_name": None},
                "caller": _OWNER,
            },
            "typed-no-command": {
                "kind": "payload",
                "builder": "typed",
                "overrides": {"command_name": None},
                "caller": _OWNER,
            },
            "typed-command-not-implement": {
                "kind": "payload",
                "builder": "typed",
                "overrides": {"command_name": "commit"},
                "caller": _OWNER,
            },
            "typed-command-wrong-type": {
                "kind": "payload",
                "builder": "typed",
                "overrides": {"command_name": 123},
                "caller": _OWNER,
            },
            "typed-also-claims-skill": {
                "kind": "payload",
                "builder": "typed",
                "overrides": {"tool_name": "Skill"},
                "caller": _OWNER,
            },
            "skill-not-implement": {
                "kind": "payload",
                "builder": "skill",
                "overrides": {"tool_input": {"skill": "commit"}},
                "caller": _OWNER,
            },
            "skill-input-not-a-dict": {
                "kind": "payload",
                "builder": "skill",
                "overrides": {"tool_input": "implement"},
                "caller": _OWNER,
            },
            "owner-synthetic": {
                "kind": "payload",
                "builder": "typed",
                "overrides": {"session_id": "stop-7"},
                "caller": "stop-7",
            },
            "claim-event-rewritten": {"kind": "chain", "expect": "WITNESS_REFUSED"},
            "chain-oversized": {"kind": "chain", "expect": "WITNESS_REFUSED"},
        },
    },
    "N-ALIAS": {
        "native_expectation": (
            "/private, /System/Volumes/Data, symlink and DANGLING-symlink "
            "spellings of the witness carrier are denied or normalized under the "
            "installed policy; the offline half is lstat-aware refusal plus "
            "realpath normalization, fail-closed"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "lstat-aware refusal + realpath normalization",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "regular-file": {"kind": "path", "builder": "regular_file", "ok": True},
            "absent-but-addressable": {
                "kind": "path",
                "builder": "absent_in_real_dir",
                "ok": True,
            },
            "live-symlink": {"kind": "path", "builder": "live_symlink", "ok": False},
            "dangling-symlink": {
                "kind": "path",
                "builder": "dangling_symlink",
                "ok": False,
            },
            "directory": {"kind": "path", "builder": "directory", "ok": False},
            "parent-missing": {"kind": "path", "builder": "parent_missing", "ok": False},
            "blank": {"kind": "path", "builder": "blank", "ok": False},
            "not-a-str": {"kind": "path", "builder": "not_a_str", "ok": False},
            "normalization": {
                "kind": "named",
                "test": "test_witness_path_verdict_normalizes_aliases",
            },
        },
    },
    "N-DESCENDANT": {
        "native_expectation": (
            "a descendant process of the native hook cannot write the carriers "
            "(sandbox inheritance), observed as an OS refusal"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "OS sandbox inheritance",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "owner-from-env-only": {
                "kind": "payload",
                "builder": "typed",
                "overrides": {"session_id": None},
                "caller": _OWNER,
                "set_env_owner": True,
            },
        },
    },
    "N-REPLAY": {
        "native_expectation": (
            "a captured native witness replayed into a later run is denied at the "
            "carrier write by the OS boundary"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "monotonic seq + nonce uniqueness offline; OS boundary natively",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "duplicate-seq": {"kind": "chain", "expect": "WITNESS_REFUSED"},
            "reused-nonce": {"kind": "chain", "expect": "WITNESS_REFUSED"},
        },
    },
    "N-WRONG-OWNER": {
        "native_expectation": (
            "a witness minted for session A cannot be presented by session B, and "
            "the OS boundary denies the cross-session carrier write"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "owner binding in the v3 MAC + OS boundary",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "payload-owner-mismatch": {
                "kind": "payload",
                "builder": "typed",
                "overrides": {"session_id": _OTHER_OWNER},
                "caller": _OWNER,
            },
            "witness-owner-rewritten": {"kind": "chain", "expect": "WITNESS_REFUSED"},
        },
    },
    "N-WRONG-RUN": {
        "native_expectation": (
            "a witness bound to run X cannot authorize run Y; natively the OS "
            "boundary denies the rebinding write"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "run binding comparison + append-time rebind refusal",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "binding-run-mismatch": {"kind": "chain", "expect": "WITNESS_REFUSED"},
            "append-interleaved-supersede": {
                "kind": "named",
                "test": "test_append_refuses_after_a_new_initiation_supersedes_the_witness",
            },
            "append-rebind": {
                "kind": "append",
                "mint_witness": True,
                "pre_bind": True,
                "overrides": {"run_id": "another-run"},
            },
            "append-blank-run": {
                "kind": "append",
                "mint_witness": True,
                "pre_bind": False,
                "overrides": {"run_id": ""},
            },
        },
    },
    "N-WRONG-MODE": {
        "native_expectation": (
            "a witness bound to mode=full cannot authorize a mode=fix run; "
            "natively the OS boundary denies the carrier rewrite"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "mode binding comparison",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "binding-mode-mismatch": {"kind": "chain", "expect": "WITNESS_REFUSED"},
            "append-blank-mode": {
                "kind": "append",
                "mint_witness": True,
                "pre_bind": False,
                "overrides": {"mode": ""},
            },
        },
    },
    "N-WRONG-ISSUE": {
        "native_expectation": (
            "a witness bound to issue A cannot authorize a run on issue B; "
            "natively the OS boundary denies the carrier rewrite"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "issue_number binding comparison",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "binding-issue-mismatch": {"kind": "chain", "expect": "WITNESS_REFUSED"},
        },
    },
    "N-WRONG-BASE": {
        "native_expectation": (
            "a witness recording base_commit X cannot authorize a run at "
            "base_commit Y; natively the OS boundary denies the carrier rewrite"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "base_commit binding comparison with monotonic refinement",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "binding-base-mismatch": {"kind": "chain", "expect": "WITNESS_REFUSED"},
            "refinement-permitted": {
                "kind": "named",
                "test": "test_progression_appends_monotonically_and_refines_base_commit",
            },
        },
    },
    "N-WRONG-SUBJECT": {
        "native_expectation": (
            "a witness bound to subject X cannot authorize a run whose subject is "
            "Y; natively the OS boundary denies the carrier rewrite"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "subject binding comparison",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "binding-subject-mismatch": {"kind": "chain", "expect": "WITNESS_REFUSED"},
        },
    },
    "N-UNSIGNED-LEGACY": {
        "native_expectation": (
            "an unsigned or stale legacy sentinel presented as witness-backed is "
            "recognized, never authorized; natively the OS boundary must still "
            "deny the carrier write that would create it"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "existing UNSIGNED_LEGACY classification",
        "required_joins": _TOOL_CALL_JOINS,
        "offline_cases": {
            "library-route": {
                "kind": "named",
                "test": "test_unsigned_state_with_a_valid_witness_is_recognized_not_authorized",
            },
        },
    },
    "N-TIMEOUT": {
        "native_expectation": (
            "script hooks are DISCARDED on timeout (harness fail-open), so the "
            "witness can be ABSENT on a legitimate typed run. The native half "
            "measures that discard; the offline half pins that ABSENCE IS A "
            "NON-PASS — classification without a witness must never report "
            "native or typed-user origin"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "missing-carrier non-pass in the classifier",
        "required_joins": _TYPED_EXPANSION_JOINS,
        "offline_cases": {
            "library-route": {"kind": "chain", "expect": "MODEL_BOOTSTRAP"},
        },
    },
    "N-NO-EXPORTER": {
        "native_expectation": (
            "a deployment whose witness reader or evidence carrier is absent is a "
            "NON-PASS, never silently green"
        ),
        "native_status": "UNMEASURED",
        "covering_mechanism": "instrument-unavailable fail-closed (INV-7)",
        "required_joins": _DEPLOYMENT_JOINS,
        "offline_cases": {
            "library-route": {"kind": "chain", "expect": "WITNESS_UNAVAILABLE"},
        },
    },
}

#: Digest of the whole frozen inventory. ANY one-sided mutation — an arm added,
#: removed or renamed, a join set changed, a case dropped, a single character of
#: spec text edited — changes this and fails the drift tripwire. It replaces the
#: previous count constant plus id frozenset (one home, one pin). It is NOT
#: tamper-proof: it sits in the same module as the matrix, so the authoritative
#: freeze record is the hash reported in the coordinator/issue evidence.
_FROZEN_MATRIX_SHA256 = (
    "a81700d9ee3e0c6f47591ac78d99f8b0a29d6a7bd6ca6cce0158730824900b29"
)

#: The three sanctioned join sets, by name, for the spec-text shape check.
_KNOWN_JOIN_SETS = {
    "typed-expansion": _TYPED_EXPANSION_JOINS,
    "tool-call": _TOOL_CALL_JOINS,
    "deployment": _DEPLOYMENT_JOINS,
}

#: Runner kinds and the test function that executes each.
_KIND_RUNNERS = {
    "typed_positive": "test_typed_user_origin_is_recorded_and_classified",
    "payload": "test_payload_shape_and_owner_binding_refusals",
    "chain": "test_witness_chain_faults_never_confer_native_origin",
    "path": "test_witness_carrier_path_is_addressed_lstat_aware",
    "append": "test_progression_append_refusals",
    "named": None,  # each case names its own test function
}


def matrix_digest() -> str:
    """SHA-256 over a canonical serialization of the frozen inventory."""
    return hashlib.sha256(
        json.dumps(NATIVE_VENUE_MATRIX, sort_keys=True, default=list).encode("utf-8")
    ).hexdigest()


def _cases(kind: str) -> List[Tuple[str, Dict[str, Any]]]:
    """Every offline case of *kind*, DERIVED from the matrix. Ids are ``ARM/case``."""
    return [
        (f"{arm}/{name}", spec)
        for arm, entry in NATIVE_VENUE_MATRIX.items()
        for name, spec in entry["offline_cases"].items()
        if spec["kind"] == kind
    ]


def _ids(cases: List[Tuple[str, Dict[str, Any]]]) -> List[str]:
    """Pytest parameter ids for *cases*."""
    return [case[0] for case in cases]


TYPED_POSITIVE_CASES = _cases("typed_positive")
PAYLOAD_CASES = _cases("payload")
CHAIN_CASES = _cases("chain")
PATH_CASES = _cases("path")
APPEND_CASES = _cases("append")
NAMED_CASES = _cases("named")


# ===========================================================================
# FIXTURES AND BUILDERS
# ===========================================================================


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Redirect sentinel, secret store and ledger into tmp_path, then reap."""
    redirect_pipeline_state(monkeypatch, tmp_path, ps, pcs)
    yield
    for owner in (_OWNER, _OTHER_OWNER):
        clear_run_artifacts(owner)


def _typed_payload(owner: str = _OWNER, args: str = "") -> Dict[str, Any]:
    """The payload shape a USER-TYPED /implement delivers on UserPromptExpansion."""
    return {
        "hook_event_name": "UserPromptExpansion",
        "command_name": "implement",
        "command_args": args,
        "command_source": "user",
        "prompt": f"/implement {args}".strip(),
        "session_id": owner,
    }


def _skill_payload(owner: str = _OWNER, skill: str = "implement") -> Dict[str, Any]:
    """The payload shape a MODEL-INVOKED Skill tool call delivers on PreToolUse."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Skill",
        "tool_input": {"skill": skill},
        "session_id": owner,
    }


def _native_fix_payload() -> Dict[str, Any]:
    """Observed typed plugin command; ``custom`` names command type, not actor."""
    payload = _typed_payload(args="--fix #1807")
    payload["command_name"] = "autonomous-dev:implement"
    payload["command_source"] = "custom"
    payload["prompt"] = "/autonomous-dev:implement --fix #1807"
    return payload


def test_typed_fix_expansion_initializes_bound_run_before_model_bash(capsys):
    """A typed expansion creates all run carriers without a coordinator step."""
    payload = _native_fix_payload()

    result = pcs.initialize_native_run_from_event(payload)

    assert isinstance(result, dict), "native initializer must return the created state"
    # The native owner must choose the canonical carrier, not a caller-supplied
    # PIPELINE_STATE_FILE. The isolation helper redirects this resolver to tmp_path.
    sentinel = ps.get_legacy_sentinel_path()
    assert sentinel.is_file()
    state = json.loads(sentinel.read_text(encoding="utf-8"))
    assert result == state
    assert state["session_id"] == payload["session_id"]
    assert state["mode"] == "fix"
    assert str(state["issue_number"]) == "1807"
    assert isinstance(state["subject"], str) and state["subject"].strip()
    assert isinstance(state["base_commit"], str) and state["base_commit"].strip()
    assert isinstance(state["run_id"], str) and state["run_id"].strip()
    assert ps.verify_state_hmac(state, _OWNER, strict=True)
    secret_path = ps._get_pipeline_secret_path(state["run_id"])
    assert secret_path.is_file()
    assert secret_path.read_text(encoding="utf-8").strip() not in json.dumps(result)
    assert pcs.get_run_start_receipt(_OWNER) == state["run_id"]
    ledger = _ledger()
    assert ledger["issue_run_starts"]["1807"] == state["run_id"]
    origin = pcs.check_native_origin(_OWNER, _bindings(state))
    assert origin.valid is True, origin.detail
    assert origin.event == "UserPromptExpansion"
    assert _classify(state).authorized is True
    assert capsys.readouterr().out == "", "hook must not print carrier data to stdout"


def test_typed_tdd_first_expansion_initializes_bound_run():
    """The documented full TDD mode must receive typed-user run authority."""
    payload = _typed_payload(args="--tdd-first #1755")
    payload["command_name"] = "autonomous-dev:implement"
    payload["command_source"] = "plugin"
    payload["prompt"] = "/autonomous-dev:implement --tdd-first #1755"

    state = pcs.initialize_native_run_from_event(payload)

    assert isinstance(state, dict)
    assert state["mode"] == "tdd-first"
    assert state["issue_number"] == 1755
    assert pcs.check_native_origin(_OWNER, _bindings(state)).valid is True


def test_observed_plugin_command_source_initializes_fix_run():
    """Native plugin commands report command_source=plugin, not custom."""
    payload = _native_fix_payload()
    payload["command_source"] = "plugin"
    state = pcs.initialize_native_run_from_event(payload)
    assert isinstance(state, dict)
    assert state["mode"] == "fix"
    assert pcs.check_native_origin(_OWNER, _bindings(state)).valid is True


@pytest.mark.parametrize("mode", ["--fix", "--full", "--tdd-first"])
def test_native_initializer_preserves_multiline_intent_without_shell_parsing(mode):
    """#1807: prose apostrophes must not break the typed command header."""
    intent = (
        "This is the authorized disposable native-initialization diagnostic described "
        "in this consumer's PROJECT.md, not an implementation or release attempt. "
        "Tools are intentionally disabled for this initial step. Stop before F1 and "
        "do not dispatch, edit, or claim acceptance. Reply INITIALIZATION_STOPPED so "
        "the independent supervisor can inspect native-created run identity before "
        "a separately reviewed continuation."
    )
    args = f"{mode} #1807\n\n{intent}\n"
    payload = _native_fix_payload()
    payload["command_args"] = args
    payload["prompt"] = f"/autonomous-dev:implement {args}"
    state = pcs.initialize_native_run_from_event(payload)
    assert isinstance(state, dict)
    assert state["mode"] == {"--fix": "fix", "--full": "full", "--tdd-first": "tdd-first"}[mode]
    assert state["issue_number"] == 1807
    assert state["subject"] == args.strip()
    assert pcs.check_native_origin(_OWNER, _bindings(state)).valid is True


@pytest.mark.parametrize("header", ['--fix "#1807', "--unknown #1807", "--fix --full #1807", "--fix"])
def test_native_initializer_refuses_malformed_header_despite_valid_intent(header):
    """Intent cannot repair a malformed invocation or supply its missing subject."""
    payload = _native_fix_payload()
    payload["command_args"] = f"{header}\n\nFix issue #1807; don't ignore validation."
    payload["prompt"] = f"/autonomous-dev:implement {payload['command_args']}"
    assert pcs.initialize_native_run_from_event(payload) is None
    assert not ps.get_legacy_sentinel_path().exists()
    assert pcs.get_run_start_receipt(_OWNER) is None


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("header,issue", [("--fix #1807", 1807), ("--full inspect parsing", "")])
def test_native_initializer_body_cannot_supply_flags_or_issue(header, issue, newline):
    """Body references and mode-looking prose are intent, not invocation authority."""
    payload = _native_fix_payload()
    args = newline.join([header, "", "Don't use --tdd-first or --unknown; compare issue #1818."])
    payload["command_args"] = args
    payload["prompt"] = f"/autonomous-dev:implement {args}"
    state = pcs.initialize_native_run_from_event(payload)
    assert isinstance(state, dict)
    assert state["mode"] == ("fix" if header.startswith("--fix") else "full")
    assert state["issue_number"] == issue
    assert state["subject"] == args


def test_native_initializer_conflicting_header_issues_remain_refused():
    payload = _native_fix_payload()
    payload["command_args"] = "--fix #1807 #1818\n\nOnly fix #1807."
    payload["prompt"] = f"/autonomous-dev:implement {payload['command_args']}"
    assert pcs.initialize_native_run_from_event(payload) is None
    assert not ps.get_legacy_sentinel_path().exists()


@pytest.mark.parametrize("header", ['--fix "#1807"', '"--fix" #1807'])
def test_native_initializer_accepts_shell_quoted_header(header):
    """Quoted header tokens preserve their ordinary invocation meaning."""
    payload = _native_fix_payload()
    payload["command_args"] = f"{header}\n\nDon't use --full; compare #1818."
    payload["prompt"] = f"/autonomous-dev:implement {payload['command_args']}"
    state = pcs.initialize_native_run_from_event(payload)
    assert isinstance(state, dict)
    assert state["mode"] == "fix"
    assert state["issue_number"] == 1807


@pytest.mark.parametrize("header", ['--fix "#1807', '--fix "#1807" "#1818"'])
def test_native_initializer_refuses_malformed_or_conflicting_quoted_header(header):
    payload = _native_fix_payload()
    payload["command_args"] = f"{header}\n\nOnly fix #1807."
    payload["prompt"] = f"/autonomous-dev:implement {payload['command_args']}"
    assert pcs.initialize_native_run_from_event(payload) is None
    assert not ps.get_legacy_sentinel_path().exists()
    assert pcs.get_run_start_receipt(_OWNER) is None


@pytest.mark.parametrize("args", ["--unknown #1755", "--tdd-first --unknown #1755"])
def test_native_initializer_rejects_unknown_tdd_flags_without_carriers(args):
    payload = _typed_payload(args=args)
    assert pcs.initialize_native_run_from_event(payload) is None
    assert not ps.get_legacy_sentinel_path().exists()
    assert pcs.get_run_start_receipt(_OWNER) is None
    assert "native_origin" not in _ledger_or_empty()


def test_model_skill_tdd_first_does_not_initialize_user_run():
    payload = _skill_payload(skill="autonomous-dev:implement")
    payload["tool_input"]["args"] = "--tdd-first #1755"
    assert pcs.initialize_native_run_from_event(payload) is None
    assert not ps.get_legacy_sentinel_path().exists()
    assert "native_origin" not in _ledger_or_empty()


@pytest.mark.parametrize(
    "mutation",
    ["model_skill", "fabricated_event", "conflicting_mode", "missing_owner", "empty_subject"],
)
def test_native_initializer_refuses_untrusted_or_incomplete_invocations(mutation):
    """Refusal creates no sentinel, secret, or run-start receipt."""
    payload = _native_fix_payload()
    if mutation == "model_skill":
        payload = _skill_payload(skill="autonomous-dev:implement")
    elif mutation == "fabricated_event":
        payload["hook_event_name"] = "PreToolUse"
        payload["tool_name"] = "Bash"
    elif mutation == "conflicting_mode":
        payload["command_args"] = "--fix --light #1807"
        payload["prompt"] = "/autonomous-dev:implement --fix --light #1807"
    elif mutation == "missing_owner":
        payload.pop("session_id")
    elif mutation == "empty_subject":
        payload["command_args"] = "--fix"
        payload["prompt"] = "/autonomous-dev:implement --fix"

    assert pcs.initialize_native_run_from_event(payload) is None
    assert not ps.get_legacy_sentinel_path().exists()
    assert not list((Path.home() / ".claude" / "pipeline_secrets").glob("*.key"))
    assert pcs.get_run_start_receipt(_OWNER) is None
    assert "native_origin" not in _ledger_or_empty()


def _run(owner: str = _OWNER, **fields: Any) -> Dict[str, Any]:
    """Build a signed, receipt-backed run state with all six bindings present."""
    defaults = {"issue_number": "1807", "subject": "native-owned init", "mode": "full"}
    defaults.update(fields)
    return sanctioned_state(owner, "native-origin-run", **defaults)


def _bindings(state: Dict[str, Any], **overrides: Any) -> Dict[str, Any]:
    """Extract the five run bindings the witness chain binds."""
    out = {key: state.get(key, "") for key in pcs.NATIVE_ORIGIN_BINDING_KEYS}
    out.update(overrides)
    return out


def _ledger(owner: str = _OWNER) -> Dict[str, Any]:
    """Read the raw ledger JSON for *owner*."""
    return json.loads(pcs._state_file_path(owner).read_text(encoding="utf-8"))


def _ledger_or_empty(owner: str = _OWNER) -> Dict[str, Any]:
    """The ledger, or ``{}`` when no ledger exists yet."""
    path = pcs._state_file_path(owner)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_ledger(data: Dict[str, Any], owner: str = _OWNER) -> None:
    """Overwrite the raw ledger JSON — models a direct-write forgery."""
    pcs._state_file_path(owner).write_text(json.dumps(data), encoding="utf-8")


def _classify(state: Dict[str, Any], owner: str = _OWNER, **kwargs: Any):
    """Classify *state* as *owner*'s current run."""
    return ps.classify_current_run_authority(state, owner, **kwargs)


def _resign(record: Dict[str, Any], owner: str = _OWNER) -> Dict[str, Any]:
    """Re-sign a forged witness/progression record with the witness secret.

    Models the HONEST adversary of this slice: a caller that already holds the
    per-record secret (every model-owned route does). A forgery that could not
    even re-sign would make these arms pass for the wrong reason.
    """
    record.pop("hmac", None)
    record.pop("hmac_version", None)
    return ps.sign_state(record, owner)


def _claim(record: Dict[str, Any]) -> Dict[str, Any]:
    """Parse the signed origin claim out of a witness/progression record."""
    return json.loads(record["subject"])


# ===========================================================================
# 1. THE FREEZE ITSELF IS GUARDED
# ===========================================================================


def test_matrix_digest_detects_one_sided_drift():
    """Detects ONE-SIDED drift of the inventory. NOT a tamper-proof freeze.

    SCOPE, stated precisely because overstating it would be the same false
    precision this file exists to avoid: :data:`_FROZEN_MATRIX_SHA256` lives in
    THIS module, beside the matrix it pins. It therefore catches the realistic
    failure — an arm edited, renamed, added or dropped while the constant is left
    alone — and it does NOT catch a coordinated rewrite of matrix and constant in
    one edit. The externally pinned authority is the freeze hash recorded in the
    coordinator evidence and on issue #1807; this test is the cheap in-repo
    tripwire for drift, not that authority.
    """
    assert matrix_digest() == _FROZEN_MATRIX_SHA256, (
        "the frozen native-venue inventory changed.\n"
        f"  pinned:  {_FROZEN_MATRIX_SHA256}\n"
        f"  current: {matrix_digest()}\n"
        "REQUIRED NEXT ACTION: if the change is intended, re-pin the digest in "
        "the same commit, say in the commit body which arm changed and why, and "
        "record the new hash in the issue evidence."
    )


def test_matrix_spec_text_is_well_formed():
    """Validate the FROZEN SPEC TEXT — NOT captured native evidence.

    Nothing here observes a native join, a hook receipt or a byte effect. These
    assertions check that the matrix DESCRIBES what a future admitted trial must
    observe, event-specifically, and that no arm silently claims to be measured.
    """
    assert _REQUIRED_EFFECTS == ("pre_sha256", "post_sha256", "path"), (
        "the universal byte-effect requirement is part of the freeze: a trial "
        "that reports an effect without pre/post bytes at a named path has not "
        "observed an effect"
    )
    for arm, entry in NATIVE_VENUE_MATRIX.items():
        assert set(entry) == {
            "native_expectation",
            "native_status",
            "covering_mechanism",
            "required_joins",
            "offline_cases",
        }, f"{arm} keys={sorted(entry)}"
        assert entry["native_status"] == "UNMEASURED", (
            f"{arm} claims native_status={entry['native_status']!r}. NO arm may be "
            "marked measured without an admitted native trial: offline green "
            "establishes no native claim whatsoever (#1807 A9 OPEN)"
        )
        assert entry["covering_mechanism"].strip(), (
            f"{arm} names no covering mechanism; where it is genuinely unknown the "
            "value must be the literal 'undetermined', never blank"
        )

        joins = tuple(entry["required_joins"])
        assert joins in tuple(_KNOWN_JOIN_SETS.values()), (
            f"{arm} uses an unrecognized join set {joins}; a one-off join set is "
            "how a trial ends up joining on whatever it happened to capture"
        )
        assert _UNIVERSAL_JOINS.issubset(set(joins)), f"{arm} joins={joins}"
        # EVENT-SPECIFIC: tool_use_id only where a tool call exists. A typed
        # slash-command expansion has none, and demanding one would force a
        # future trial to synthesize an id.
        assert ("tool_use_id" in joins) is (joins == _TOOL_CALL_JOINS), (
            f"{arm} requires tool_use_id on a non-tool-call venue; a typed "
            "slash-command expansion has none, and demanding one would force a "
            "future trial to SYNTHESIZE an id"
        )


def test_no_arm_claims_the_builtin_edit_deny_covers_mcp_editors():
    """N-MCP's covering mechanism is UNDETERMINED and stays that way.

    Native permission rules cover BUILT-IN editors; a real MCP editor was
    observed false-permitted through a relative_path. Encoding "Edit-deny covers
    MCP" anywhere would be an unproven claim, and a MAC rejection is not an MCP
    denial — so N-MCP carries no offline case at all.
    """
    mcp = NATIVE_VENUE_MATRIX["N-MCP"]
    assert mcp["covering_mechanism"] == "undetermined"
    assert mcp["offline_cases"] == {}, (
        "N-MCP must have no offline-decidable case: a forged-MAC refusal belongs "
        "to the forged-witness negatives, not to an MCP-editor denial"
    )
    assert "Edit(" not in mcp["native_expectation"]
    assert "UNDETERMINED" in mcp["native_expectation"]


def test_every_offline_case_has_a_runner_that_exists():
    """Connectedness: a declared case with no executable runner is a promise nobody keeps."""
    for arm, entry in NATIVE_VENUE_MATRIX.items():
        for name, spec in entry["offline_cases"].items():
            kind = spec.get("kind")
            assert kind in _KIND_RUNNERS, f"{arm}/{name}: unknown kind {kind!r}"
            runner = _KIND_RUNNERS[kind] or spec.get("test")
            assert runner, f"{arm}/{name}: names no test"
            assert callable(globals().get(runner)), (
                f"{arm}/{name} declares test {runner!r}, which does not exist"
            )

    derived = len(TYPED_POSITIVE_CASES) + len(PAYLOAD_CASES) + len(CHAIN_CASES) + (
        len(PATH_CASES) + len(APPEND_CASES) + len(NAMED_CASES)
    )
    total = sum(len(e["offline_cases"]) for e in NATIVE_VENUE_MATRIX.values())
    assert derived == total, (
        f"{total - derived} offline case(s) are declared but reach no runner list"
    )


# ===========================================================================
# 2. PERMIT ARMS — the instrument can say yes, and says WHICH yes
# ===========================================================================


@pytest.mark.parametrize("case_id,spec", TYPED_POSITIVE_CASES, ids=_ids(TYPED_POSITIVE_CASES))
def test_typed_user_origin_is_recorded_and_classified(case_id, spec):
    """PERMIT arm: a typed /implement witness yields TYPED_USER origin.

    Without this every refusal below is satisfiable by a classifier hard-wired to
    refuse native origin.
    """
    args = spec["args"]
    state = _run(mode="fix" if args else "full")
    witness_id = pcs.record_native_origin_witness(_OWNER, _typed_payload(args=args))
    assert witness_id, f"{case_id}: a typed native payload minted no witness"
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="run-bound"
    ), f"{case_id}: the run binding was refused"

    verdict = _classify(state)

    assert verdict.authorized is True, verdict.detail
    assert verdict.origin is ps.RunOrigin.TYPED_USER_WITNESSED, (
        f"{case_id}: origin={verdict.origin.value} detail={verdict.origin_detail}"
    )
    assert verdict.typed_user_origin is True
    assert verdict.native_origin is True


def test_observed_plugin_namespace_mints_typed_witness_but_other_namespaces_refuse():
    """The native CLI delivered autonomous-dev:implement on 2026-09-30.

    Accept only that observed plugin namespace. Arbitrary namespaces and
    suffix laundering remain non-originating even with native-shaped input.
    """
    state = _run()
    payload = _typed_payload()
    payload["command_name"] = "autonomous-dev:implement"

    assert pcs.record_native_origin_witness(_OWNER, payload)
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="run-bound"
    )

    verdict = _classify(state)

    assert verdict.authorized is True, verdict.detail
    assert verdict.origin is ps.RunOrigin.TYPED_USER_WITNESSED
    assert verdict.typed_user_origin is True

    # A new initiation supersedes any existing witness; these must not do so.
    previous = _ledger_or_empty().get("native_origin")
    for spoofed in ("evil:implement", "autonomous-dev:implement-evil:implement"):
        payload["command_name"] = spoofed
        assert pcs.record_native_origin_witness(_OWNER, payload) is None, spoofed
        assert _ledger_or_empty().get("native_origin") == previous


def test_model_skill_origin_is_recorded_but_confers_no_user_authorization():
    """P-SKILL: native EVENT coverage, not user authority.

    The model chooses when to call Skill. If a Skill-origin witness could read as
    typed-user origin, the model would hold a native carrier for minting its own
    current-run authority — the exact confusion #1807 exists to remove.
    """
    state = _run()
    assert pcs.record_native_origin_witness(_OWNER, _skill_payload())
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="run-bound"
    )

    verdict = _classify(state)

    assert verdict.origin is ps.RunOrigin.MODEL_SKILL_WITNESSED, (
        f"origin={verdict.origin.value} detail={verdict.origin_detail}"
    )
    assert verdict.native_origin is True, "the Skill event IS native"
    assert verdict.typed_user_origin is False, (
        "a model-invoked Skill must NEVER read as typed-user authorization"
    )


# ===========================================================================
# 3. REFUSE ARMS
# ===========================================================================


@pytest.mark.parametrize("case_id,spec", PAYLOAD_CASES, ids=_ids(PAYLOAD_CASES))
def test_payload_shape_and_owner_binding_refusals(case_id, spec, monkeypatch):
    """REFUSE arm: a payload that cannot be a native initiation mints nothing.

    Deliberately a DIFFERENT shape per dimension (absent, wrong type, wrong
    value, contradictory, cross-owner, synthetic) rather than N spellings of one
    reproducer.
    """
    if spec.get("set_env_owner"):
        # An inherited env var is not an owner. Set the strongest env signal
        # available and confirm it grants nothing.
        monkeypatch.setenv("CLAUDE_SESSION_ID", _OWNER)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", _OWNER)

    builder = spec["builder"]
    overrides = spec["overrides"]
    if builder == "raw":
        payload: Any = overrides
    else:
        payload = _typed_payload() if builder == "typed" else _skill_payload()
        for key, value in overrides.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value

    witness_id = pcs.record_native_origin_witness(spec["caller"], payload)

    assert witness_id is None, (
        f"{case_id}: minted witness {witness_id!r} from a payload that is not a "
        "native run initiation"
    )
    assert "native_origin" not in _ledger_or_empty(), (
        f"{case_id}: a refused payload still wrote the witness carrier"
    )


def _forge_progression(bindings: Dict[str, Any]) -> None:
    """Write a seq-1 progression record directly, bypassing the append api."""
    data = _ledger()
    origin = data["native_origin"]
    witness_id = origin["witness"]["run_id"]
    claim = {
        "at": "2026-09-28T00:00:00+00:00",
        "bindings": bindings,
        "event": "run-bound",
        "seq": 1,
        "witness_id": witness_id,
    }
    record = {
        "session_start": "2026-09-28T00:00:00",
        "mode": pcs.NATIVE_ORIGIN_PROGRESSION_MODE,
        "run_id": witness_id,
        "explicitly_invoked": True,
        "alignment_passed": False,
        "alignment_verdict": "",
        "session_id": _OWNER,
        "issue_number": "",
        "subject": json.dumps(claim, sort_keys=True),
        "base_commit": "",
    }
    origin["progression"] = [ps.sign_state(record, _OWNER)]
    _write_ledger(data)


#: Binding forgeries, by case id. Each names the single binding altered.
_BINDING_FORGERIES = {
    "N-WRONG-RUN/binding-run-mismatch": {"run_id": "some-other-run"},
    "N-WRONG-MODE/binding-mode-mismatch": {"mode": "fix"},
    "N-WRONG-ISSUE/binding-issue-mismatch": {"issue_number": "1806"},
    "N-WRONG-BASE/binding-base-mismatch": {"base_commit": "deadbeefdeadbeef"},
    "N-WRONG-SUBJECT/binding-subject-mismatch": {"subject": "a different run"},
}


def _apply_chain_fault(case_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the fault named by *case_id*; return extra classifier kwargs.

    Every fault is applied to a chain that was VALID immediately before it, so a
    refusal cannot come from the chain never having worked.
    """
    kwargs: Dict[str, Any] = {}

    if case_id == "N-TIMEOUT/library-route":
        # The harness DISCARDS a timed-out script hook: no witness is written.
        return kwargs

    if case_id == "N-NO-EXPORTER/library-route":
        def _broken(*_a: Any, **_k: Any):
            raise RuntimeError("witness reader unavailable")

        assert pcs.record_native_origin_witness(_OWNER, _typed_payload())
        assert pcs.append_native_origin_progression(
            _OWNER, _bindings(state), event="run-bound"
        )
        kwargs["origin_lookup"] = _broken
        return kwargs

    assert pcs.record_native_origin_witness(_OWNER, _typed_payload())

    if case_id == "N-BASH/witness-unbound":
        # A witness minted with NO run binding: the shape a direct call to the
        # initializer produces. It names no run, so it authorizes none.
        return kwargs

    if case_id in _BINDING_FORGERIES:
        forged = _bindings(state, **_BINDING_FORGERIES[case_id])
        if not pcs.append_native_origin_progression(_OWNER, forged, event="run-bound"):
            _forge_progression(forged)
        return kwargs

    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="run-bound"
    )

    data = _ledger()
    origin = data["native_origin"]

    if case_id == "N-BUILTIN/witness-unsigned":
        origin["witness"].pop("hmac", None)
        origin["witness"].pop("hmac_version", None)
    elif case_id == "N-BUILTIN/witness-mac-tampered":
        mac = origin["witness"]["hmac"]
        origin["witness"]["hmac"] = ("b" if mac[0] != "b" else "c") + mac[1:]
    elif case_id == "N-STDIN/claim-event-rewritten":
        claim = _claim(origin["witness"])
        claim["event"] = "UserPromptSubmit"
        origin["witness"]["subject"] = json.dumps(claim, sort_keys=True)
        origin["witness"] = _resign(origin["witness"])
    elif case_id == "N-STDIN/chain-oversized":
        template = origin["progression"][0]
        records = []
        for index in range(512):
            record = dict(template)
            claim = _claim(record)
            claim["seq"] = index + 1
            record["subject"] = json.dumps(claim, sort_keys=True)
            record["nonce"] = f"{index:032x}"
            records.append(_resign(record))
        origin["progression"] = records
    elif case_id == "N-REPLAY/duplicate-seq":
        replayed = dict(origin["progression"][0])
        replayed["nonce"] = "f" * 32
        origin["progression"].append(_resign(replayed))
    elif case_id == "N-REPLAY/reused-nonce":
        replayed = dict(origin["progression"][0])
        claim = _claim(replayed)
        claim["seq"] = 2
        replayed["subject"] = json.dumps(claim, sort_keys=True)
        origin["progression"].append(_resign(replayed))
    elif case_id == "N-WRONG-OWNER/witness-owner-rewritten":
        origin["witness"]["session_id"] = _OTHER_OWNER
        origin["witness"] = _resign(origin["witness"], _OTHER_OWNER)
    else:  # pragma: no cover - a case with no mutator is a table defect
        raise AssertionError(f"no mutator for case {case_id}")

    _write_ledger(data)
    return kwargs


@pytest.mark.parametrize("case_id,spec", CHAIN_CASES, ids=_ids(CHAIN_CASES))
def test_witness_chain_faults_never_confer_native_origin(case_id, spec):
    """REFUSE arm: every corrupted, unbound, replayed or unreadable chain fails closed.

    The run itself stays AUTHORIZED — the origin level is strictly additive, so a
    bad witness must not become a denial-of-service lever against a live run.
    What it must never do is report native or typed-user origin.
    """
    state = _run()
    kwargs = _apply_chain_fault(case_id, state)

    verdict = _classify(state, **kwargs)

    assert verdict.origin is getattr(ps.RunOrigin, spec["expect"]), (
        f"{case_id}: expected {spec['expect']}, got {verdict.origin.value} "
        f"({verdict.origin_detail})"
    )
    assert verdict.typed_user_origin is False, f"{case_id}: read as typed-user"
    assert verdict.native_origin is False, f"{case_id}: read as native"
    assert verdict.authorized is True, (
        f"{case_id}: the run's own authority must be unaffected: {verdict.detail}"
    )


def test_unsigned_state_with_a_valid_witness_is_recognized_not_authorized():
    """N-UNSIGNED-LEGACY: recognition is not authority, witness or no witness."""
    state = _run()
    assert pcs.record_native_origin_witness(_OWNER, _typed_payload())
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="run-bound"
    )
    state.pop("hmac")

    verdict = _classify(state)

    assert verdict.authority is ps.RunAuthority.UNSIGNED_LEGACY, verdict.detail
    assert verdict.authorized is False
    assert verdict.typed_user_origin is False
    assert verdict.native_origin is False
    assert verdict.origin is ps.RunOrigin.NOT_EVALUATED, (
        "an unauthorized run has no origin to attribute; saying so honestly "
        f"beats guessing, got {verdict.origin.value}"
    )


def _symlink(link: Path, target: Path) -> str:
    """Create *link* -> *target* and return the link path."""
    link.symlink_to(target)
    return str(link)


@pytest.mark.parametrize("case_id,spec", PATH_CASES, ids=_ids(PATH_CASES))
def test_witness_carrier_path_is_addressed_lstat_aware(case_id, spec, tmp_path):
    """N-ALIAS: presence is lstat-aware and a redirecting carrier path refuses.

    ``Path.exists()`` returns False for a DANGLING symlink, so an existence check
    alone reads an attacker-planted redirect as "absent, safe to create".
    """
    real = tmp_path / "real"
    real.mkdir()
    target = real / "ledger.json"
    target.write_text("{}", encoding="utf-8")

    builders = {
        "regular_file": lambda: str(target),
        "absent_in_real_dir": lambda: str(real / "not-yet.json"),
        "live_symlink": lambda: _symlink(tmp_path / "live.json", target),
        "dangling_symlink": lambda: _symlink(tmp_path / "dangling.json", real / "gone"),
        "directory": lambda: str(real),
        "parent_missing": lambda: str(tmp_path / "nope" / "ledger.json"),
        "blank": lambda: "   ",
        "not_a_str": lambda: 17,
    }
    candidate = builders[spec["builder"]]()

    ok, reason, canonical = pcs.witness_path_verdict(candidate)

    assert ok is spec["ok"], f"{case_id}: ok={ok} reason={reason}"
    if spec["ok"]:
        assert canonical and os.path.isabs(canonical), f"{case_id}: {canonical!r}"
    else:
        assert reason.strip(), f"{case_id}: a refusal must name its cause"
        if "symlink" in spec["builder"]:
            assert "symlink" in reason.lower(), reason
        if spec["builder"] == "dangling_symlink":
            assert not Path(candidate).exists(), "control: exists() is False here"
            assert os.path.lexists(candidate), "control: lexists() is True here"


def test_witness_path_verdict_normalizes_aliases(tmp_path):
    """N-ALIAS/normalization: two spellings of one file canonicalize alike.

    The platform-alias half is asserted against the OS's OWN inode verdict rather
    than a hardcoded expectation about ``/private`` or ``/System/Volumes/Data``,
    so it cannot pass or fail for platform reasons unrelated to the subject.
    """
    real = tmp_path / "real"
    real.mkdir()
    target = real / "ledger.json"
    target.write_text("{}", encoding="utf-8")
    alias_dir = tmp_path / "alias"
    alias_dir.symlink_to(real)

    direct_ok, _, direct = pcs.witness_path_verdict(str(target))
    alias_ok, _, alias = pcs.witness_path_verdict(str(alias_dir / "ledger.json"))

    assert direct_ok and alias_ok
    assert direct == alias, (
        "a dir-symlink spelling of the same file must canonicalize identically"
    )

    leaf = ".autonomous-dev-1807-alias-probe"
    canonical_tmp = f"{os.path.realpath('/tmp')}/{leaf}"
    for spelling in ("/tmp", "/private/tmp", "/System/Volumes/Data/tmp"):
        if not os.path.isdir(spelling):
            continue
        _, _, canonical = pcs.witness_path_verdict(f"{spelling}/{leaf}")
        assert (canonical == canonical_tmp) is _same_inode(spelling, "/tmp"), (
            f"{spelling}: canonicalization disagreed with the OS inode verdict "
            f"(canonical={canonical!r})"
        )


def _same_inode(a: str, b: str) -> bool:
    """Whether two path spellings name the same directory inode."""
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


@pytest.mark.parametrize("case_id,spec", APPEND_CASES, ids=_ids(APPEND_CASES))
def test_progression_append_refusals(case_id, spec):
    """The append owner refuses an unwitnessed, unbound or rebinding progression."""
    state = _run()
    if spec["mint_witness"]:
        assert pcs.record_native_origin_witness(_OWNER, _typed_payload())
    if spec["pre_bind"]:
        assert pcs.append_native_origin_progression(
            _OWNER, _bindings(state), event="run-bound"
        )

    accepted = pcs.append_native_origin_progression(
        _OWNER, _bindings(state, **spec["overrides"]), event="run-bound"
    )

    assert accepted is False, f"{case_id}: the append was accepted"


def test_append_refuses_after_a_new_initiation_supersedes_the_witness():
    """N-WRONG-RUN/append-interleaved-supersede: a LATE append cannot bind an old run.

    THE HAZARD, concretely. Witness A is minted and run R1 is bound. The user types
    ``/implement`` again: witness B supersedes A, and STEP 0 stamps the run-start
    receipt with R2. A progression append for R1 now arrives late (a SubagentStop
    from the first run). If it were accepted it would bind the NEWER witness to the
    OLDER run and return success — cross-run inheritance through a native carrier.

    It is refused because the bind is checked against the run-start receipt read
    UNDER THE SAME LOCK that writes the chain. The positive control below is the
    other half: an append for R2, the run the receipt actually names, is ACCEPTED —
    without it this arm would pass against an append path that refuses everything.
    """
    first = _run()
    assert pcs.record_native_origin_witness(_OWNER, _typed_payload())
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(first), event="run-bound"
    )
    first_chain = _ledger()["native_origin"]["progression"]

    # A second typed initiation: new witness, new run, new receipt.
    second = _run()
    assert pcs.record_native_origin_witness(_OWNER, _typed_payload())

    late = pcs.append_native_origin_progression(
        _OWNER, _bindings(first), event="subagent-stop"
    )

    assert late is False, (
        "a late append for the superseded run was accepted, binding the new "
        "witness to the old run"
    )
    fresh = _ledger()["native_origin"]["progression"]
    assert fresh == [], f"the new run's chain was poisoned: {fresh}"
    assert first_chain, "control: the first chain really did exist before"

    # PERMIT control: the run the receipt names binds normally.
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(second), event="run-bound"
    ) is True
    assert _classify(second).origin is ps.RunOrigin.TYPED_USER_WITNESSED
    # And the superseded run no longer claims native origin at all.
    assert _classify(first).typed_user_origin is False


def test_progression_appends_monotonically_and_refines_base_commit():
    """Progression is append-only and REFINES an empty binding exactly once.

    ``base_commit`` is written to the sentinel AFTER STEP 0 by
    ``set_pipeline_base_commit``, so a witness bound at initiation legitimately
    records it empty. Filling an empty binding later is allowed; CHANGING a
    non-empty one is the N-WRONG-* forgery, refused above.
    """
    state = _run(base_commit="")
    assert pcs.record_native_origin_witness(_OWNER, _typed_payload())
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="run-bound"
    )

    # Faithful to production: set_pipeline_base_commit RE-SIGNS the sentinel after
    # writing base_commit, because v3 binds it. Mutating without re-signing would
    # make this arm fail on MAC_INVALID and never reach the origin question.
    state["base_commit"] = "8efcd57f8efcd57f"
    state = ps.sign_state(state, _OWNER)
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="base-commit-recorded"
    )
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="subagent-stop"
    )

    verdict = _classify(state)
    assert verdict.origin is ps.RunOrigin.TYPED_USER_WITNESSED, verdict.origin_detail

    seqs = [
        json.loads(record["subject"])["seq"]
        for record in _ledger()["native_origin"]["progression"]
    ]
    assert seqs == [1, 2, 3], f"seqs={seqs}"


#: The honest ``base_commit`` the second append fills in for the pair below.
_HONEST_BASE = "8efcd57f8efcd57f"


def _chain_refined_to_base_commit() -> Dict[str, Any]:
    """Two appends: the binding append with ``base_commit`` EMPTY, then the one fill.

    This is the THREE-APPEND shape's first two thirds, and the reason the pair
    below needs it: after this the chain DISAGREES with itself about
    ``base_commit`` — ``chain[0]`` still binds ``""`` (it was minted before
    ``set_pipeline_base_commit`` ran) while ``chain[-1]`` binds
    :data:`_HONEST_BASE`. A merge that reads the FIRST record therefore sees an
    empty field free to fill where the chain has in fact already fixed one. The two
    asserts at the end are the instrument control: without that divergence
    actually present, neither arm of the pair could distinguish the two merges.

    Returns:
        The re-signed sentinel state whose bindings the chain now matches.
    """
    state = _run(base_commit="")
    assert pcs.record_native_origin_witness(_OWNER, _typed_payload())
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="run-bound"
    )

    # Faithful to production: set_pipeline_base_commit RE-SIGNS the sentinel.
    state["base_commit"] = _HONEST_BASE
    state = ps.sign_state(state, _OWNER)
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="base-commit-recorded"
    )

    chain = _ledger()["native_origin"]["progression"]
    assert len(chain) == 2, f"control: expected two records, got {len(chain)}"
    assert _claim(chain[0])["bindings"]["base_commit"] == "", (
        "control: the FIRST record must still bind base_commit empty"
    )
    assert _claim(chain[-1])["bindings"]["base_commit"] == _HONEST_BASE, (
        "control: the LATEST record must bind the filled base_commit"
    )
    return state


def test_a_third_append_cannot_rebind_what_the_second_legitimately_bound():
    """A field FILLED by an earlier append may not be changed by a later one.

    THE HAZARD, concretely. Refinement is "an empty binding may be filled, a
    non-empty one may never change". Whether that holds depends entirely on WHICH
    record counts as prior. Read the FIRST record and ``base_commit`` looks empty
    forever, because the binding append legitimately recorded it empty before
    ``set_pipeline_base_commit`` ran — so append #3 presenting a DIFFERENT commit
    than the one append #2 honestly bound is accepted as "filling an empty field"
    instead of refused as a rebind, and the chain ends up attesting a base commit
    nobody bound. The prior must be the LATEST accepted record, which is also the
    one ``check_native_origin`` reads when it compares the chain to the sentinel.

    NEGATIVE arm of the opposite pair; the POSITIVE is the test below.
    """
    state = _chain_refined_to_base_commit()
    before = json.dumps(_ledger()["native_origin"]["progression"], sort_keys=True)

    rebound = pcs.append_native_origin_progression(
        _OWNER,
        _bindings(state, base_commit="deadbeefdeadbeef"),
        event="subagent-stop",
    )

    assert rebound is False, (
        "a third append REBOUND base_commit to a value no earlier append fixed"
    )
    chain = _ledger()["native_origin"]["progression"]
    assert len(chain) == 2, f"the refused append still grew the chain: {len(chain)}"
    assert json.dumps(chain, sort_keys=True) == before, (
        "the refused append mutated the chain's bytes"
    )
    assert _claim(chain[-1])["bindings"]["base_commit"] == _HONEST_BASE


def test_a_third_append_repeating_the_bound_value_is_permitted():
    """POSITIVE arm: the same value again is refinement, not a rebind.

    Without this the negative above would pass against an append path that refuses
    every third append — the pair is what separates "refuses a rebind" from
    "refuses everything past two records".
    """
    state = _chain_refined_to_base_commit()

    assert (
        pcs.append_native_origin_progression(
            _OWNER, _bindings(state), event="subagent-stop"
        )
        is True
    )

    chain = _ledger()["native_origin"]["progression"]
    assert len(chain) == 3, f"the permitted append did not grow the chain: {chain}"
    assert [_claim(record)["seq"] for record in chain] == [1, 2, 3]
    assert _claim(chain[-1])["bindings"]["base_commit"] == _HONEST_BASE
    assert _classify(state).origin is ps.RunOrigin.TYPED_USER_WITNESSED


def test_an_unavailable_signer_is_cannot_tell_never_an_origin_verdict(monkeypatch):
    """The REAL ``instrument_ok=False`` branch: the signer is genuinely absent.

    ``check_native_origin`` cannot judge a witness without
    ``pipeline_state.verify_state_hmac``, and "cannot tell" is not "passed"
    (INV-7). Exercised against the actual import seam — ``_native_origin_signers``
    returning all-``None``, the shape a missing/undeployed ``pipeline_state``
    produces — not against a hand-built ``NativeOriginCheck``.

    Both arms in one test: the control above the monkeypatch shows the very same
    run classifying TYPED_USER_WITNESSED while the instrument IS present, so the
    WITNESS_UNAVAILABLE below is attributable to the instrument and not to a
    witness this test failed to build. Base authority must survive untouched —
    origin is strictly additive, so an unreadable witness may not demote a run.
    """
    state = _run()
    assert pcs.record_native_origin_witness(_OWNER, _typed_payload())
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="run-bound"
    )
    control = _classify(state)
    assert control.origin is ps.RunOrigin.TYPED_USER_WITNESSED, control.origin_detail
    assert control.authority is ps.RunAuthority.AUTHORIZED, control.detail

    monkeypatch.setattr(pcs, "_native_origin_signers", lambda: (None, None, None))

    check = pcs.check_native_origin(_OWNER, _bindings(state))
    assert check.instrument_ok is False, "an absent signer was reported as a verdict"
    assert check.valid is False
    assert "verify_state_hmac" in check.detail

    verdict = _classify(state)
    assert verdict.origin is ps.RunOrigin.WITNESS_UNAVAILABLE, verdict.origin_detail
    assert verdict.authority is ps.RunAuthority.AUTHORIZED, verdict.detail
    assert verdict.authorized is True
    assert verdict.native_origin is False
    assert verdict.typed_user_origin is False


# ===========================================================================
# 4. NO CALLER-SUPPLIED ORIGIN OR APPROVAL (#1802 tie-in)
# ===========================================================================


def test_origin_class_is_never_caller_supplied():
    """The origin class comes from the native event name, never from an argument.

    #1802's escalation upgrade needs a REAL interactive approval bound to this
    run. This slice must not create a parameter, env var or flag a model could
    pass to obtain typed-user origin instead.
    """
    forbidden = {
        "origin",
        "event",
        "hook_event_name",
        "approved",
        "user_approved",
        "typed",
        "typed_user",
        "authorized",
        "native",
    }
    for func in (pcs.record_native_origin_witness, pcs.check_native_origin):
        params = set(inspect.signature(func).parameters)
        assert params & forbidden == set(), (
            f"{func.__name__} accepts caller-controlled origin/approval "
            f"parameters {sorted(params & forbidden)}"
        )

    for name in dir(pcs) + dir(ps):
        lowered = name.lower()
        assert not (
            ("promote" in lowered or "upgrade" in lowered)
            and ("origin" in lowered or "authority" in lowered)
        ), f"{name} looks like an origin/authority promotion path"


def test_skill_origin_cannot_be_laundered_into_typed_user_origin():
    """A Skill payload dressed up as a typed command is still Skill origin.

    A DIFFERENT shape from the P-SKILL positive: this payload carries BOTH the
    Skill tool fields and a ``command_name``/``command_source``, which is what a
    laundering attempt looks like.
    """
    state = _run()
    payload = _skill_payload()
    payload["command_name"] = "implement"
    payload["command_source"] = "user"

    assert pcs.record_native_origin_witness(_OWNER, payload)
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(state), event="run-bound"
    )

    verdict = _classify(state)

    assert verdict.origin is ps.RunOrigin.MODEL_SKILL_WITNESSED, verdict.origin_detail
    assert verdict.typed_user_origin is False


# ===========================================================================
# 5. THE HOOK ENTRYPOINT AND ITS SOURCE-SIDE REGISTRATION
# ===========================================================================


def test_hook_entrypoint_records_the_origin_class_of_its_native_event():
    """A same-run Skill attempt leaves a bound typed initiation intact."""
    import native_run_origin as hook

    assert hook.handle_native_origin_event(_native_fix_payload()) == 0
    state = json.loads(ps.get_legacy_sentinel_path().read_text(encoding="utf-8"))
    assert _classify(state).origin is ps.RunOrigin.TYPED_USER_WITNESSED
    before = json.dumps(_ledger_or_empty()["native_origin"], sort_keys=True)

    assert hook.handle_native_origin_event(_skill_payload()) == 0
    assert json.dumps(_ledger_or_empty()["native_origin"], sort_keys=True) == before
    assert _classify(state).origin is ps.RunOrigin.TYPED_USER_WITNESSED

    # A payload that is not a native initiation is a no-op, never a block. Asserted
    # as "the ledger's bytes are UNCHANGED" rather than "no carrier exists", which
    # is the stronger statement: it refuses a non-native event that mints, that
    # supersedes, or that edits an existing chain, not merely one that creates.
    before = json.dumps(_ledger_or_empty(), sort_keys=True)
    assert hook.handle_native_origin_event({"hook_event_name": "Stop"}) == 0
    assert json.dumps(_ledger_or_empty(), sort_keys=True) == before, (
        "a non-native event mutated the origin ledger"
    )
    # And it never creates one where none existed, for a fresh owner.
    assert hook.handle_native_origin_event({"hook_event_name": "Stop"}) == 0
    assert "native_origin" not in _ledger_or_empty(_OTHER_OWNER)


def test_skill_attempt_does_not_inherit_typed_witness_across_runs():
    """A later model run cannot claim the prior typed run's witness."""
    typed = pcs.initialize_native_run_from_event(_native_fix_payload())
    assert typed is not None
    later = _run()
    assert later["run_id"] != typed["run_id"]

    assert pcs.record_native_origin_witness(_OWNER, _skill_payload())
    assert pcs.append_native_origin_progression(
        _OWNER, _bindings(later), event="run-bound"
    )
    assert _classify(later).origin is ps.RunOrigin.MODEL_SKILL_WITNESSED
    assert _classify(later).typed_user_origin is False


def test_skill_attempt_cannot_overwrite_typed_initiation_interleaved_before_lock(monkeypatch):
    """A typed event arriving before the Skill transaction wins the ledger lock."""
    first = pcs.initialize_native_run_from_event(_native_fix_payload())
    assert first is not None
    original_rmw = pcs._locked_rmw
    injected = {"done": False, "later": None}

    def interleave(owner, mutator, **kwargs):
        if not injected["done"]:
            injected["done"] = True
            injected["later"] = pcs.initialize_native_run_from_event(_native_fix_payload())
        return original_rmw(owner, mutator, **kwargs)

    monkeypatch.setattr(pcs, "_locked_rmw", interleave)
    assert pcs.record_native_origin_witness(_OWNER, _skill_payload())
    later = injected["later"]
    assert later is not None and later["run_id"] != first["run_id"]
    assert _classify(later).origin is ps.RunOrigin.TYPED_USER_WITNESSED


def test_skill_attempt_preserves_typed_witness_pending_receipt(monkeypatch):
    """Typed initialization owns its witness before receipt/progression exist."""
    original_start = pcs.record_run_start
    observed = {"attempt": None}

    def interleave_start(*args, **kwargs):
        observed["attempt"] = pcs.record_native_origin_witness(
            _OWNER, _skill_payload()
        )
        return original_start(*args, **kwargs)

    monkeypatch.setattr(pcs, "record_run_start", interleave_start)
    typed = pcs.initialize_native_run_from_event(_native_fix_payload())
    assert typed is not None
    assert observed["attempt"] is not None
    assert _classify(typed).origin is ps.RunOrigin.TYPED_USER_WITNESSED


def test_skill_attempt_refuses_malformed_current_sentinel_without_replacing_witness():
    """Unreadable current authority cannot justify destructive supersession."""
    assert pcs.initialize_native_run_from_event(_native_fix_payload()) is not None
    before = json.dumps(_ledger_or_empty()["native_origin"], sort_keys=True)
    ps.get_legacy_sentinel_path().write_text("{broken", encoding="utf-8")
    assert pcs.record_native_origin_witness(_OWNER, _skill_payload()) is None
    assert json.dumps(_ledger_or_empty()["native_origin"], sort_keys=True) == before


def test_skill_attempt_refuses_missing_current_sentinel_with_live_typed_run():
    """A lost sentinel cannot authorize replacement of a bound typed witness."""
    assert pcs.initialize_native_run_from_event(_native_fix_payload()) is not None
    before = json.dumps(_ledger_or_empty()["native_origin"], sort_keys=True)
    ps.get_legacy_sentinel_path().unlink()
    assert pcs.record_native_origin_witness(_OWNER, _skill_payload()) is None
    assert json.dumps(_ledger_or_empty()["native_origin"], sort_keys=True) == before


def test_native_witness_refuses_when_required_ledger_lock_is_unavailable(monkeypatch):
    """Witness replacement cannot use the ledger's generic unlocked fallback."""
    def no_lock(*_args, **_kwargs):
        raise OSError("lock unavailable")

    monkeypatch.setattr(pcs.fcntl, "flock", no_lock)
    assert pcs.record_native_origin_witness(_OWNER, _skill_payload()) is None
    assert "native_origin" not in _ledger_or_empty()


def test_subagent_stop_progression_seam_reads_the_sentinel(tmp_path):
    """The SubagentStop half of the progression seam, exercised as it is called.

    ``unified_session_tracker`` knows only its ``session_id``, so the seam reads
    the run bindings from the sentinel. Both arms: it APPENDS for a witnessed run,
    and it is a silent no-op for the model-bootstrap run that has no witness —
    without the second arm this would pass against a seam that appends
    unconditionally.
    """
    sentinel = tmp_path / "sentinel.json"
    state = _run()
    sentinel.write_text(json.dumps(state), encoding="utf-8")

    # No witness yet: the bootstrap path. Silent False, nothing written.
    assert (
        pcs.append_native_origin_progression_from_sentinel(_OWNER, str(sentinel))
        is False
    )
    assert "native_origin" not in _ledger_or_empty()

    assert pcs.record_native_origin_witness(_OWNER, _typed_payload())
    assert (
        pcs.append_native_origin_progression_from_sentinel(_OWNER, str(sentinel))
        is True
    )
    assert _classify(state).origin is ps.RunOrigin.TYPED_USER_WITNESSED

    # A sentinel that names no run cannot bind one.
    runless = tmp_path / "runless.json"
    runless.write_text(json.dumps({"session_id": _OWNER}), encoding="utf-8")
    assert (
        pcs.append_native_origin_progression_from_sentinel(_OWNER, str(runless))
        is False
    )


#: Templates must not duplicate the plugin-owned native origin callbacks.
#: The plugin's hooks.json is the one registration owner; install migration
#: removes only matching legacy callbacks from populated consumer settings.
_REGISTRATION_SURFACES = (
    "plugins/autonomous-dev/templates/settings.autonomous-dev.json",
    "plugins/autonomous-dev/config/global_settings_template.json",
)


def test_registration_surface_consistency_source_side_only():
    """SOURCE-SIDE single-owner check (Q1 PARTIAL) — not connectivity proof.

    This reads TEMPLATE STRINGS and the install manifest. It does NOT observe the
    effective installed registration in ``~/.claude/settings.json``, it does NOT
    observe the hook firing on either event. The separate native probe observed
    the plugin-namespaced command spelling, but the full installed workflow and
    A9 containment remain UNMEASURED.

    Plugin registration plus manifest presence is NOT installed connectivity
    proof. This also refuses duplicate legacy template registrations.
    """
    for relative in _REGISTRATION_SURFACES:
        settings = json.loads((_REPO_ROOT / relative).read_text(encoding="utf-8"))
        hooks = settings.get("hooks", {})
        for event, matcher_must_include in (
            ("UserPromptExpansion", None),
            ("PreToolUse", "Skill"),
        ):
            commands = [
                entry.get("command", "")
                for group in hooks.get(event, [])
                for entry in group.get("hooks", [])
                if "native_run_origin.py" in entry.get("command", "")
                and (
                    matcher_must_include is None
                    or matcher_must_include in group.get("matcher", "")
                )
            ]
            assert not commands, (
                f"{relative}: native_run_origin.py duplicates plugin-owned {event}"
                + (
                    f" with a {matcher_must_include} matcher"
                    if matcher_must_include
                    else ""
                )
            )

    manifest = json.loads(
        (_REPO_ROOT / "plugins/autonomous-dev/config/install_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    files = manifest["components"]["hooks"]["files"]
    for required in (
        "plugins/autonomous-dev/hooks/native_run_origin.py",
        "plugins/autonomous-dev/hooks/native_run_origin.hook.json",
    ):
        assert required in files, f"{required} is absent from install_manifest.json"


def test_plugin_native_origin_registration_is_executable_and_scoped():
    """The plugin's default hook surface must carry both native events."""
    plugin_hooks = json.loads((_HOOK_DIR / "hooks.json").read_text(encoding="utf-8"))[
        "hooks"
    ]
    expected = {"UserPromptExpansion": "*", "PreToolUse": "Skill"}
    for event, matcher in expected.items():
        registrations = [
            group for group in plugin_hooks[event]
            if group.get("matcher") == matcher
            and any(
                "native_run_origin.py" in str(entry.get("args", []))
                for entry in group.get("hooks", [])
            )
        ]
        assert len(registrations) == 1
        assert registrations[0]["matcher"] == matcher
        commands = registrations[0]["hooks"]
        assert len(commands) == 1
        assert commands[0]["type"] == "command"
        assert commands[0]["command"] == "python3"
        assert commands[0]["args"] == [
            "${CLAUDE_PLUGIN_ROOT}/hooks/native_run_origin.py"
        ]


def test_hook_metadata_declares_both_registrations():
    """The hook's own metadata must agree with the settings surfaces (source-side)."""
    meta = json.loads(
        (_HOOK_DIR / "native_run_origin.hook.json").read_text(encoding="utf-8")
    )
    events = {reg["event"] for reg in meta["registrations"]}
    assert events == {"UserPromptExpansion", "PreToolUse"}, events
    assert meta["active"] is True


# ===========================================================================
# 6. THE FROZEN MAC BYTES ARE UNTOUCHED
# ===========================================================================


def test_witness_signing_does_not_change_the_frozen_mac_message():
    """The witness reuses the v3 chain; it must not add a MAC version or field.

    A witness signed by a NEW message shape would silently invalidate every
    in-flight run's signature. This pins the reuse: a witness record verifies
    under the SAME ``verify_state_hmac`` as a pipeline state, at v3, and refuses
    a foreign presenter.
    """
    assert ps._STATE_MAC_CURRENT == 3, "witness records are signed at v3"
    assert pcs.record_native_origin_witness(_OWNER, _typed_payload())

    witness = _ledger()["native_origin"]["witness"]

    assert witness["hmac_version"] == 3
    assert ps.verify_state_hmac(witness, _OWNER, strict=True) is True
    assert ps.verify_state_hmac(witness, _OTHER_OWNER, strict=True) is False

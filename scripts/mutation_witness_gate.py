#!/usr/bin/env python3
"""SubagentStop hook: a declared test must be OBSERVED failing on a mutant.

Issue #1660. Every gate that accepted a new test measured QUANTITY --
``coverage_baseline.py``'s four checks are all counters, and ``assert True``
satisfies every one of them. This hook supplies the missing property at the
agent boundary: a test that survives a mutation of the code it claims to cover
is not evidence that code works.

NOT SHIPPED. NOT REGISTERED. NOT IN ``hooks/``. NOT IN ``lib/``.
-----------------------------------------------------------------
This file AND the module it drives, ``scripts/mutation_witness.py``, both live
in ``scripts/`` -- beside ``scripts/integration_ceiling.py``, the sibling
mutation harness they extend. Neither is in ``plugins/autonomous-dev/hooks/`` or
``plugins/autonomous-dev/lib/``. There is no ``.hook.json`` sidecar, no entry in
either ``install_manifest.json``, and no registration in any settings surface.
All of that is intentional and must stay true until a PRODUCER exists.

The library moved out of ``lib/`` for the same reason the driver is not in
``hooks/``: it is a HARNESS, not a runtime library. Its only would-be consumer
was ``lib/step5_quality_gate.py``, which is itself pinned as unreached, and
since #1698 the reachability walk is transitive -- so the composition bought
nothing but the appearance of wiring. Classifying the pair correctly is the fix;
``lib/`` was the misclassification.

The location is not cosmetic. Two shipped ratchets MEASURED this file as a
defect while it sat in ``hooks/``::

    test_hook_reachability_ratchet.py::TestRatchet::test_no_new_unreachable_refusers
      -> mutation_witness_gate.py: ['no-lifecycle-registration',
                                    'no-utility-declaration']
         refusal evidence: decorated_emitter:emit_decision,
                           dict_literal:decision='block'
    test_install_sync_critical.py::TestInstallShCritical::test_install_manifest_lists_all_hooks
      -> Hooks missing from manifest: {'mutation_witness_gate.py'}

Both were right: a file in ``hooks/`` that can emit a refusal and is invoked by
nothing is exactly the state #1612 exists to make visible. Pinning either is
explicitly not an available resolution. A gate driver awaiting its producer is a
SCRIPT, not an installed hook, and putting it where it actually is stops both
instruments reporting a falsehood.

Nothing in this repo writes a mutation claim today -- no agent, command, lib or
script. With an empty producer, the only behaviour a consumer could ever
observe from a blocking ``SubagentStop`` gate is a FALSE REFUSAL, which is not a
defensible default. Landing the producer means editing ``agents/test-master.md``
and the coordinator wiring; that is a separate change deserving its own review.

**Issue #1660's enforcement loop is therefore OPEN, not closed.** The dynamic
mechanism exists and is proven both refusing and permitting under test; the
enforcement is not wired. Said plainly rather than implied.

To register it once a producer lands: move this file to
``plugins/autonomous-dev/hooks/`` and create the sidecar
``mutation_witness_gate.hook.json`` beside it, in ONE diff::

    {"name": "mutation_witness_gate", "type": "lifecycle",
     "interpreter": "python3", "active": true, "version": "1.0.0",
     "registrations": [{"event": "SubagentStop", "matcher": "*", "timeout": 60}]}

then run ``python3 scripts/generate_hook_config.py --write``. The 60 is load
bearing -- see below.

WHY A HOOK AND NOT A PIPELINE STEP, WHEN IT IS EVENTUALLY WIRED
---------------------------------------------------------------
A coordinator can forget a pipeline step. A hook cannot be skipped.
``SubagentStop`` fires exactly when the emitting agent returns, which is the
boundary the goal names.

The earlier objection -- "a mutation cycle costs ~5.5s and the hook budget is
5s" -- rested on a false premise: that raising a timeout slows every call. A
timeout is a CEILING, not a delay. MEASURED over a 7-day window (windowed after
2026-08-21 to exclude the ``hook_timing.py:375`` labelling artifact)::

    total hook invocations : 84,339
      exceeded 5s          :    266   (0.3154%)
      extra wait if allowed to finish : 803.8s across the WHOLE window
    unified_pre_tool.py  p50 = 6.4ms   p99 = 2,217ms   max = 13,139ms

The median hook call is single-digit milliseconds. Raising this registration to
60s costs nothing on the fast path and buys back gate executions that currently
vanish silently.

THE 60s CEILING IS NOT NEGOTIABLE HERE
--------------------------------------
``config/hook-metadata.schema.json`` caps ``registrations[].timeout`` at 60, and
``Stop`` already carries a 60s slot in-tree. Anything above 60 is UNVERIFIED.
This hook is therefore written to a HARD 60s wall and schedules against a
deadline rather than hoping.

COST, MEASURED IN THIS REPO
---------------------------
One real single-test pytest run costs **3.39s median** here (3 runs: 3.29 /
3.41 / 3.39), with ``-o addopts=`` already clearing coverage; import, conftest
and collection dominate. A claim is two runs (~6.8s), so roughly
:data:`CLAIMS_THAT_FIT` claims fit in the budget.

WHAT HAPPENS ON OVERFLOW
------------------------
Claims that do not fit the deadline are DEFERRED, not dropped and never
silently passed:

* the claims file is a QUEUE -- verified claims are removed, everything else is
  written back, so the next ``SubagentStop`` drains more;
* every unverified node id is NAMED in the hook's stderr record and appended to
  ``.claude/logs/mutation_witness/<date>.jsonl``, which outlives the message.

There is NO second consumer that drains the remainder. An earlier revision of
this file claimed ``step5_quality_gate.run_quality_gate`` composed the same
function without a 60s ceiling; that composition was removed, because its host
is itself invoked by nothing (it is pinned in ``PINNED_UNREACHED_LIBRARY`` as
"named four times across implement.md and implementer.md as the gate that
'blocks', and invoked by neither"). Wiring a harness into an unreached host
manufactures the APPEARANCE of a backstop, which is the exact false signal this
issue exists to eliminate. Until a producer lands, overflow is deferred to the
next ``SubagentStop`` and to the JSONL record, and nothing else.

Overflow deliberately does NOT block. A permanently-red check on "your batch
was large" trains everyone to ignore the class, which is the failure this whole
design exists to avoid.

Exit codes:
- 0: always. A refusal travels as ``{"decision": "block", "reason": ...}`` JSON
  on stdout, which is the SubagentStop contract.

Environment variables:
- ``MUTATION_CLAIMS_PATH``: override the claims queue path.
- ``MUTATION_WITNESS_DISABLE_PLUGIN_AUTOLOAD``: set to 1 when every declared
  target is self-contained. MEASURED 3.53s -> 0.16s per run, which multiplies
  the claims that fit by ~20. Unset by default because a real test may need an
  autoloaded plugin and a missing fixture would read as a failure.
- ``MUTATION_WITNESS_GATE``: set to "false"/"0"/"no" to disable the gate.

Feature: Issue #1660 - mutation witness at the agent boundary
Date: 2026-08-28
"""

# Issue #953: hook crashes must never block Claude Code.
import sys as _sys_953
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    # scripts/ itself: mutation_witness.py is co-located with this driver, not in
    # lib/. sys.path[0] already covers `python3 scripts/mutation_witness_gate.py`,
    # but NOT `python3 -c "import mutation_witness_gate"` or an importing test, so
    # the co-location is made explicit rather than left to the invocation form.
    _hook_dir_953,
    _hook_dir_953.parent / "plugins" / "autonomous-dev" / "lib",  # repo lib (dev)
    _hook_dir_953.parent / "lib",  # installed layout
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:  # pragma: no cover - fallback when hook_safety is absent

    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from mutation_witness import (
        InvalidMutationError,
        MutationClaim,
        WitnessResult,
        load_claims,
        recover_inflight,
        target_lock,
        witness_claim,
    )

    _WITNESS_AVAILABLE = True
except ImportError:  # pragma: no cover - degraded install
    _WITNESS_AVAILABLE = False

try:
    from hook_telemetry import block_event_decorator
except ImportError:  # pragma: no cover - fallback when telemetry is absent

    def block_event_decorator(*_args, **_kwargs):
        def _identity(fn):
            return fn

        return _identity


EXIT_SUCCESS = 0

#: The registration timeout this hook is written against, and the maximum
#: ``config/hook-metadata.schema.json`` permits (``timeout`` has
#: ``"maximum": 60``). Any future sidecar MUST use this value; a shorter slot
#: truncates the gate mid-mutation. A regression test cross-validates it against
#: the schema ceiling so the two cannot drift.
HOOK_TIMEOUT_S = 60

#: Wall time held back for interpreter start, imports, queue IO and the write of
#: the deferral record. The gate must return BEFORE the runtime cuts it off; a
#: hook killed at the ceiling produces no verdict at all.
SAFETY_RESERVE_S = 8.0

#: MEASURED in this repo, 2026-08-28, with the exact flags ``_run_one_test``
#: uses::
#:
#:     PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
#:       tests/unit/lib/test_coverage_baseline.py::TestLoadBaseline::test_no_file_returns_empty_dict \
#:       -q --no-header -o addopts= -p no:cacheprovider -p no:randomly
#:
#: Two instruments, and the disagreement is stated rather than resolved
#: silently: the reviewer measured a 3.58s median, this session measured 3.52s
#: over 5 samples (3.48/3.51/3.52/3.55/3.59). The LARGER figure is used, because
#: over-estimating cost defers a claim while under-estimating it lets the
#: runtime cut the hook mid-mutation. An earlier 3.39s reading was ~6%
#: optimistic and is withdrawn.
MEASURED_PER_RUN_S = 3.58

#: A claim is a control run plus a mutant run.
RUNS_PER_CLAIM = 2

#: Ceiling for any ONE run: ~3.4x the measured median, so ordinary variance does
#: not manufacture a budget skip while a genuinely hung test still gets cut.
PER_RUN_BUDGET_S = 12.0


def claims_that_fit(
    *,
    timeout_s: float = HOOK_TIMEOUT_S,
    reserve_s: float = SAFETY_RESERVE_S,
    per_run_s: float = MEASURED_PER_RUN_S,
    per_run_budget_s: float = PER_RUN_BUDGET_S,
) -> int:
    """How many claims :func:`run_gate` will actually admit.

    Derived from the SAME expression the loop uses, not from an idealised
    division. The loop refuses to start a claim unless
    ``per_run_budget_s * RUNS_PER_CLAIM`` of wall time remains -- it must
    reserve the worst case, not the median -- so the first claim needs that much
    headroom and each subsequent one costs only the MEASURED amount. Dividing
    usable time by measured cost (the earlier formula) reported 7 while the loop
    admitted fewer, and the deferral message quoted the wrong number.

    Args:
        timeout_s: Registered hook timeout.
        reserve_s: Wall time held back for startup and bookkeeping.
        per_run_s: Measured cost of one single-test pytest run.
        per_run_budget_s: Worst-case ceiling the loop reserves per run.

    Returns:
        Claim count that fits, never below 0.
    """
    usable = timeout_s - reserve_s
    reserved = per_run_budget_s * RUNS_PER_CLAIM
    measured = per_run_s * RUNS_PER_CLAIM
    if usable < reserved or measured <= 0:
        return 0
    return 1 + int((usable - reserved) // measured)


#: Derived, never hand-written: 60s - 8s reserve, at ~6.78s per claim.
CLAIMS_THAT_FIT = claims_that_fit()


def _is_disabled() -> bool:
    """True when ``MUTATION_WITNESS_GATE`` is set to a falsey word."""
    return os.environ.get("MUTATION_WITNESS_GATE", "").strip().lower() in {
        "false",
        "0",
        "no",
    }


def _read_payload() -> Dict[str, Any]:
    """Read the SubagentStop JSON payload from stdin, tolerating junk.

    Returns:
        The parsed payload, or an empty dict when stdin is empty or unparseable.
        A malformed payload must not crash the boundary; the claims queue, not
        the payload, decides whether there is work to do.
    """
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):  # pragma: no cover - closed stdin
        return {}
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def find_project_root(start: Optional[Path] = None) -> Path:
    """Resolve the repository root for claim and log paths.

    Args:
        start: Directory to search from. Defaults to ``$CLAUDE_PROJECT_DIR`` or
            the current working directory.

    Returns:
        The nearest ancestor containing ``.git``, else the starting directory.
    """
    base = start or Path(os.environ.get("CLAUDE_PROJECT_DIR", "") or Path.cwd())
    base = Path(base).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate
    return base


def _claims_path(root: Path) -> Path:
    """Path of the claims queue, honouring ``MUTATION_CLAIMS_PATH``."""
    override = os.environ.get("MUTATION_CLAIMS_PATH")
    if override:
        return Path(override)
    return root / ".claude" / "local" / "mutation_claims.json"


def _claim_to_dict(claim: "MutationClaim", root: Path) -> Dict[str, str]:
    """Serialise a claim back to queue form, keeping ``target`` repo-relative."""
    try:
        target = str(claim.target.relative_to(root))
    except ValueError:
        target = str(claim.target)
    return {
        "test": claim.test,
        "target": target,
        "anchor": claim.anchor,
        "replacement": claim.replacement,
    }


def _write_queue(path: Path, claims: List["MutationClaim"], root: Path) -> None:
    """Persist the remaining queue, deleting the file when it empties.

    Held under the same exclusive lock as the mutation sequence. This is a
    read-modify-write on shared state: two concurrent SubagentStop hooks could
    otherwise each load the queue, drain a different claim, and write back a
    version missing the other's -- a LOST UPDATE that can silently drop a
    BLOCKING claim, converting a refusal into a pass.

    Args:
        path: Claims queue file.
        claims: Claims to keep.
        root: Repository root, used to anchor the lock and relativise targets.
    """
    with target_lock(root):
        if not claims:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"claims": [_claim_to_dict(c, root) for c in claims]}, indent=2)
            + "\n",
            encoding="utf-8",
        )


def _append_record(root: Path, record: Dict[str, Any]) -> None:
    """Append one JSONL record. Best effort -- logging never blocks the gate."""
    try:
        log_dir = root / ".claude" / "logs" / "mutation_witness"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc)
        record = {"timestamp": stamp.isoformat(), **record}
        with (log_dir / f"{stamp.date().isoformat()}.jsonl").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        pass


def run_gate(
    *,
    root: Path,
    claims_path: Path,
    deadline: float,
    disable_plugin_autoload: bool = False,
) -> Tuple[bool, str, List["MutationClaim"]]:
    """Drain as much of the claims queue as the deadline allows.

    Args:
        root: Repository root; both pytest runs use it as ``cwd``.
        claims_path: Claims queue to drain.
        deadline: ``time.monotonic()`` value the gate must return before.
        disable_plugin_autoload: Forwarded to each pytest run.

    Returns:
        ``(blocked, message, remaining_claims)``. ``blocked`` is True when a
        declared test survived its mutation, tampered with its target, produced
        an uninterpretable exit, or carried an unusable mutation.
    """
    try:
        claims = load_claims(claims_path, repo_root=root)
    except InvalidMutationError as exc:
        return (
            True,
            f"Mutation witness gate: the claims queue is unreadable.\n{exc}",
            [],
        )

    if not claims:
        return (False, "", [])

    verified: List[str] = []
    blocking: List[Tuple["MutationClaim", str]] = []
    inconclusive: List[Tuple["MutationClaim", str]] = []
    deferred: List["MutationClaim"] = []
    remaining: List["MutationClaim"] = []

    for index, claim in enumerate(claims):
        per_claim_need = PER_RUN_BUDGET_S * RUNS_PER_CLAIM
        left = deadline - time.monotonic()
        if left < per_claim_need:
            # Every claim from here on is deferred, NAMED, and kept in the queue.
            deferred.extend(claims[index:])
            remaining.extend(claims[index:])
            break

        per_run = min(PER_RUN_BUDGET_S, left / RUNS_PER_CLAIM)
        try:
            result: "WitnessResult" = witness_claim(
                claim,
                repo_root=root,
                budget_s=per_run,
                disable_plugin_autoload=disable_plugin_autoload,
            )
        except InvalidMutationError as exc:
            blocking.append((claim, f"{claim.test}: INVALID MUTATION -- {exc}"))
            remaining.append(claim)
            continue

        if result.witnessed:
            verified.append(claim.test)
        elif result.blocking:
            blocking.append((claim, result.message))
            remaining.append(claim)
        else:
            # SKIPPED_BUDGET / SKIPPED_ENV / UNCOUPLED / CONTENDED: loud, named,
            # requeued, never counted as witnessed -- and never a refusal.
            inconclusive.append((claim, result.message))
            remaining.append(claim)

    _append_record(
        root,
        {
            "verified": verified,
            # The TEST id, not the verdict word. The previous `b.split(":")[0]`
            # recorded "VACUOUS" and threw away the only actionable field, so the
            # durable JSONL could not answer "which test was refused?".
            "blocked": [c.test for c, _ in blocking],
            "inconclusive": [c.test for c, _ in inconclusive],
            "deferred": [c.test for c in deferred],
            "claims_that_fit": CLAIMS_THAT_FIT,
            "declared": len(claims),
        },
    )

    lines: List[str] = [
        f"Mutation witness gate (Issue #1660): {len(verified)}/{len(claims)} "
        f"declared test(s) OBSERVED failing against a mutated target."
    ]
    if deferred:
        lines.append(
            f"UNVERIFIED -- {len(deferred)} claim(s) did not fit the {HOOK_TIMEOUT_S}s "
            f"hook budget (~{CLAIMS_THAT_FIT} claims at a MEASURED "
            f"{MEASURED_PER_RUN_S}s per run). They stay queued and drain on the "
            f"next SubagentStop; step5_quality_gate verifies the whole queue with "
            f"no 60s ceiling. NOT verified, NOT passed:"
        )
        lines.extend(f"    {c.test}" for c in deferred)
    if inconclusive:
        lines.append(
            f"INCONCLUSIVE -- {len(inconclusive)} claim(s) could not be judged "
            f"here (skipped in this environment, anchored on a line the test "
            f"never reaches, contended, or over budget). NOT verified and NOT "
            f"refused; they stay queued:"
        )
        lines.extend(f"  - {m}" for _, m in inconclusive)
    if blocking:
        lines.append(
            "REFUSED -- these CLAIMS are not evidence that their target works. "
            "Each message names the (test, mutation) pair and its resolutions; "
            "re-anchoring the claim is usually the right one:"
        )
        lines.extend(f"  - {m}" for _, m in blocking)

    return (bool(blocking), "\n".join(lines), remaining)


@block_event_decorator(
    "mutation_witness_gate.py",
    decision_shape="dict",
    refusal_values=frozenset({"block"}),
    metadata={"event": "SubagentStop", "issue": 1660},
)
def emit_decision(decision: str, reason: str) -> None:
    """SOLE refusal emitter -- decorated so refusing and recording are one act.

    Issue #1587/#1611: a hook that builds a refusal and then, separately, is
    supposed to remember to log it will eventually forget. Wrapping the only
    emitter fuses the two, so "has this gate ever fired?" stays answerable from
    ``.claude/logs/hook-blocks.jsonl``.

    Args:
        decision: ``"block"`` to refuse, anything else to permit.
        reason: Model-visible explanation, also the recorded row's reason.
    """
    if decision == "block":
        print(json.dumps({"decision": "block", "reason": reason}))
    elif reason:
        sys.stderr.write(reason + "\n")


def main() -> int:
    """SubagentStop entry point.

    Returns:
        Always ``EXIT_SUCCESS``. A refusal is emitted as SubagentStop JSON.
    """
    payload = _read_payload()

    # Never re-enter: a blocking Stop hook that fires on its own block loops.
    if payload.get("stop_hook_active"):
        return EXIT_SUCCESS

    # Universal bypass (Issue #969) -- the SAME block stop_quality_gate.py uses.
    # Without it this gate had no in-session escape: MUTATION_WITNESS_GATE is an
    # env var, and per Issue #779 env vars do NOT propagate to hook subprocesses
    # mid-session. A blocking claim stays queued and re-blocks on EVERY
    # subsequent SubagentStop, so one bad anchor would wedge the whole session
    # with `rm` on a gitignored file as the only recovery -- exactly the dynamic
    # that manufactured this repo's bypass counts.
    try:
        from hook_bypass import is_bypassed, log_bypass_used

        if is_bypassed():
            log_bypass_used(
                hook_name=Path(__file__).name, tool_name="mutation_witness_gate"
            )
            return EXIT_SUCCESS
    except ImportError:
        pass

    if _is_disabled() or not _WITNESS_AVAILABLE:
        return EXIT_SUCCESS

    root = find_project_root()

    # Repair before reading anything: a journal means a previous run was killed
    # between mutating and restoring, and every verdict taken against a still-
    # mutated target would be wrong.
    for line in recover_inflight(root):
        sys.stderr.write(line + "\n")

    claims_path = _claims_path(root)
    if not claims_path.exists():
        return EXIT_SUCCESS

    deadline = time.monotonic() + (HOOK_TIMEOUT_S - SAFETY_RESERVE_S)
    blocked, message, remaining = run_gate(
        root=root,
        claims_path=claims_path,
        deadline=deadline,
        disable_plugin_autoload=os.environ.get(
            "MUTATION_WITNESS_DISABLE_PLUGIN_AUTOLOAD", ""
        ).strip()
        in {"1", "true", "yes"},
    )

    try:
        _write_queue(claims_path, remaining, root)
    except OSError as exc:  # pragma: no cover - disk failure
        sys.stderr.write(f"mutation witness gate: could not rewrite queue: {exc}\n")

    emit_decision("block" if blocked else "allow", message)
    return EXIT_SUCCESS


# Issue #1012: per-hook timing telemetry. Best-effort, never raises.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - fallback stub

    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def set_decision_shape(self, _):
            pass


_HOOK_TIMER_NAME = _Path_953(__file__).name


def _timed_main():
    with HookTimer(_HOOK_TIMER_NAME):
        return main()


if __name__ == "__main__":
    _safe_main_953(_timed_main)

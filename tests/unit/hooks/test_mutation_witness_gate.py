"""The SubagentStop mutation-witness gate, watched refusing AND permitting (#1660).

The hook is driven AS A PROCESS -- stdin payload in, stdout JSON out -- because
the property under test is the SubagentStop contract, not a Python return value.
An in-process call would prove the function works and say nothing about whether
Claude Code would ever see a refusal.

Every scenario builds a throwaway git repo under ``tmp_path`` so the hook's own
project-root resolution runs for real. A probe that silently ran against the
developer's repo would be measuring the wrong tree.

Date: 2026-08-28
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import pytest

# tests/unit/hooks/<this file> -> hooks -> unit -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
SCRIPTS_DIR = REPO_ROOT / "scripts"
#: The gate driver AND the module it drives both live in scripts/, NOT in hooks/
#: or lib/ -- see the driver's module docstring and TestDeliberatelyNotShipped
#: below. A file in hooks/ that can refuse and is registered nowhere is measured
#: as a defect by ``test_no_new_unreachable_refusers``; a module in lib/ whose
#: only importer is itself unreached is measured as UNKNOWN by
#: ``test_no_new_unreached_library_modules``. Both instruments were right.
HOOK_PATH = SCRIPTS_DIR / "mutation_witness_gate.py"
WITNESS_PATH = SCRIPTS_DIR / "mutation_witness.py"
SIDECAR_PATH = HOOKS_DIR / "mutation_witness_gate.hook.json"

sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import mutation_witness_gate as gate  # noqa: E402

CALC_SOURCE = "def add(a, b):\n    return a + b\n"
ANCHOR = "return a + b"
REPLACEMENT = "return a - b"

GENUINE_TEST = """from calc import add


def test_add_returns_the_sum():
    assert add(2, 3) == 5
"""

IS_NOT_NONE_TEST = """from calc import add


def test_add_returns_something():
    assert add(2, 3) is not None
"""


def _repo(tmp_path: Path, test_source: str, *, claims: int = 1) -> Path:
    """Build a throwaway repo with a target, a test module and a claims queue."""
    (tmp_path / ".git").mkdir(exist_ok=True)
    (tmp_path / "calc.py").write_text(CALC_SOURCE, encoding="utf-8")
    (tmp_path / "test_target.py").write_text(test_source, encoding="utf-8")
    func = "test_" + test_source.split("def test_", 1)[1].split("(", 1)[0]
    claims_path = tmp_path / ".claude" / "local" / "mutation_claims.json"
    claims_path.parent.mkdir(parents=True, exist_ok=True)
    claims_path.write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "test": f"test_target.py::{func}",
                        "target": "calc.py",
                        "anchor": ANCHOR,
                        "replacement": REPLACEMENT,
                    }
                ]
                * claims
            }
        ),
        encoding="utf-8",
    )
    return claims_path


def _run_hook(
    tmp_path: Path, payload: dict, *, fast: bool = True, extra_env: dict | None = None
) -> Tuple[subprocess.CompletedProcess, dict | None]:
    """Invoke the hook as a process and parse any SubagentStop JSON it emits."""
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    # NO PYTHONPATH prop. An earlier revision injected LIB_DIR here, which meant
    # every arm below measured a driver whose imports the TEST had resolved --
    # the driver's own bootstrap was never exercised. It now finds
    # mutation_witness beside itself in scripts/ and hook_safety/hook_bypass/
    # hook_telemetry under plugins/autonomous-dev/lib, unaided. If that
    # resolution breaks, these arms go red, which is the point.
    env.pop("PYTHONPATH", None)
    if fast:
        env["MUTATION_WITNESS_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    else:
        env.pop("MUTATION_WITNESS_DISABLE_PLUGIN_AUTOLOAD", None)
    env.update(extra_env or {})

    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
        timeout=180,
    )
    decision = None
    if proc.stdout.strip():
        try:
            decision = json.loads(proc.stdout)
        except json.JSONDecodeError:
            decision = None
    return proc, decision


class TestBudgetArithmetic:
    """The batch bound is DERIVED from a measured cost, not asserted."""

    def test_claims_that_fit_reports_what_the_loop_actually_admits(self) -> None:
        """The reported figure must equal the loop's own admission rule.

        Recomputed here from ``run_gate``'s literal condition rather than from
        the same formula the function uses -- a test that reuses the
        implementation's arithmetic cannot notice the implementation being
        wrong, which is how the previous version reported 7 while the loop
        admitted fewer and the deferral message quoted the wrong number.
        """
        usable = gate.HOOK_TIMEOUT_S - gate.SAFETY_RESERVE_S
        need = gate.PER_RUN_BUDGET_S * gate.RUNS_PER_CLAIM
        cost = gate.MEASURED_PER_RUN_S * gate.RUNS_PER_CLAIM

        admitted, left = 0, usable
        while left >= need:
            admitted += 1
            left -= cost

        assert gate.CLAIMS_THAT_FIT == admitted, (
            f"CLAIMS_THAT_FIT reports {gate.CLAIMS_THAT_FIT} but simulating the "
            f"loop admits {admitted}. The deferral message quotes this number."
        )
        assert admitted >= 1, "the budget must admit at least one claim"

    def test_the_bound_moves_with_the_cost(self) -> None:
        """NEGATIVE CONTROL: a constant that ignores its inputs is decoration."""
        assert gate.claims_that_fit(per_run_s=1.0) > gate.CLAIMS_THAT_FIT
        assert gate.claims_that_fit(per_run_s=100.0) == 1, (
            "one claim always fits once the reserve is met -- it is the "
            "SUBSEQUENT ones that a high per-run cost squeezes out"
        )
        assert gate.claims_that_fit(timeout_s=5) == 0, (
            "at the OLD 5s hook budget not one claim fits -- which is exactly "
            "why any future registration must ask for 60s"
        )

    def test_the_hook_timeout_matches_the_schema_ceiling(self) -> None:
        """60 is not a preference: it is the maximum the sidecar schema allows.

        There is no sidecar to cross-validate against while this hook is
        unshipped, so the invariant is anchored on the schema instead -- which
        is the thing a future sidecar would have to satisfy anyway.
        """
        schema = json.loads(
            (
                REPO_ROOT
                / "plugins"
                / "autonomous-dev"
                / "config"
                / "hook-metadata.schema.json"
            ).read_text(encoding="utf-8")
        )
        ceiling = schema["properties"]["registrations"]["items"]["properties"][
            "timeout"
        ]["maximum"]
        assert gate.HOOK_TIMEOUT_S == ceiling == 60, (
            f"the hook is written to a {gate.HOOK_TIMEOUT_S}s wall but the "
            f"registration schema caps timeout at {ceiling}s; a shorter slot "
            f"truncates the gate mid-mutation."
        )


class TestGateBothArms:
    """Refusing and permitting, driven through the process boundary."""

    def test_a_test_that_survives_mutation_is_refused(self, tmp_path: Path) -> None:
        """REFUSING ARM: the decision reaches Claude Code as block JSON."""
        _repo(tmp_path, IS_NOT_NONE_TEST)
        proc, decision = _run_hook(tmp_path, {"agent_type": "test-master"})
        assert proc.returncode == 0, proc.stderr
        assert decision is not None, f"no JSON on stdout: {proc.stdout!r}"
        assert decision["decision"] == "block"
        assert "VACUOUS" in decision["reason"]
        assert "test_add_returns_something" in decision["reason"]

    def test_a_genuine_test_is_permitted(self, tmp_path: Path) -> None:
        """PERMITTING ARM: no block, and the queue is consumed."""
        claims_path = _repo(tmp_path, GENUINE_TEST)
        proc, decision = _run_hook(tmp_path, {"agent_type": "test-master"})
        assert proc.returncode == 0, proc.stderr
        assert decision is None, f"a genuine test was blocked: {proc.stdout}"
        assert "1/1 declared test(s) OBSERVED failing" in proc.stderr
        assert not claims_path.exists(), (
            "a verified claim must leave the queue, or it is re-verified forever"
        )

    def test_a_refused_claim_stays_queued(self, tmp_path: Path) -> None:
        """The claim survives the block so the fix is re-verified, not assumed."""
        claims_path = _repo(tmp_path, IS_NOT_NONE_TEST)
        _run_hook(tmp_path, {"agent_type": "test-master"})
        assert claims_path.exists()
        assert len(json.loads(claims_path.read_text())["claims"]) == 1

    def test_the_refusal_is_recorded_and_the_permit_is_not(self, tmp_path: Path) -> None:
        """Both arms of the telemetry sink, so 'did it ever fire?' is answerable.

        Issue #1587/#1611: a refusal nobody can count is indistinguishable from
        a gate that never ran. The NEGATIVE arm matters equally -- a recorder
        that logs on every invocation would make the count meaningless.
        """
        block_log = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"

        _repo(tmp_path, GENUINE_TEST)
        _run_hook(tmp_path, {"agent_type": "test-master"})
        permitted_rows = block_log.read_text().splitlines() if block_log.exists() else []
        assert permitted_rows == [], "a PERMIT recorded a block row"

        _repo(tmp_path, IS_NOT_NONE_TEST)
        _run_hook(tmp_path, {"agent_type": "test-master"})
        assert block_log.exists(), (
            "the refusal wrote no row to .claude/logs/hook-blocks.jsonl"
        )
        rows = [json.loads(line) for line in block_log.read_text().splitlines() if line]
        assert any(r.get("hook_name") == "mutation_witness_gate.py" for r in rows), rows

    def test_no_claims_means_no_output_at_all(self, tmp_path: Path) -> None:
        """99.7% of SubagentStops carry no claims; the gate must be silent."""
        (tmp_path / ".git").mkdir()
        proc, decision = _run_hook(tmp_path, {"agent_type": "researcher"})
        assert proc.returncode == 0
        assert decision is None
        assert proc.stdout.strip() == ""

    def test_stop_hook_active_never_re_enters(self, tmp_path: Path) -> None:
        """A blocking Stop hook that fires on its own block loops forever."""
        _repo(tmp_path, IS_NOT_NONE_TEST)
        proc, decision = _run_hook(
            tmp_path, {"agent_type": "test-master", "stop_hook_active": True}
        )
        assert decision is None, "the gate re-entered while already stopping"

    def test_the_gate_can_be_disabled_but_is_on_by_default(self, tmp_path: Path) -> None:
        """Both arms of the kill switch, so 'default on' is observed not assumed."""
        _repo(tmp_path, IS_NOT_NONE_TEST)
        _, off = _run_hook(
            tmp_path, {"agent_type": "test-master"}, extra_env={"MUTATION_WITNESS_GATE": "false"}
        )
        assert off is None

        _repo(tmp_path, IS_NOT_NONE_TEST)
        _, on = _run_hook(tmp_path, {"agent_type": "test-master"})
        assert on is not None and on["decision"] == "block"

    def test_a_malformed_payload_does_not_crash_the_boundary(self, tmp_path: Path) -> None:
        """Junk on stdin must not take the agent boundary down."""
        (tmp_path / ".git").mkdir()
        env = dict(os.environ)
        env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not json at all",
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env=env,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr

    def test_both_arms_hold_under_the_shipped_plugin_configuration(
        self, tmp_path: Path
    ) -> None:
        """No FAST override: exactly the environment the registration produces.

        Every other arm sets MUTATION_WITNESS_DISABLE_PLUGIN_AUTOLOAD for speed.
        This one does not, so that knob cannot be the reason the gate works.
        """
        _repo(tmp_path, IS_NOT_NONE_TEST)
        _, refused = _run_hook(tmp_path, {"agent_type": "test-master"}, fast=False)
        assert refused is not None and refused["decision"] == "block"

        _repo(tmp_path, GENUINE_TEST)
        _, permitted = _run_hook(tmp_path, {"agent_type": "test-master"}, fast=False)
        assert permitted is None


class TestOverflowIsDeferredNotDropped:
    """The binding constraint: a batch larger than the budget."""

    def test_claims_past_the_deadline_are_named_and_requeued(
        self, tmp_path: Path
    ) -> None:
        """A partial verification must never read as a full one.

        The deadline affords exactly one claim: it opens 0.05s above the
        per-claim need, and one claim costs two pytest processes (>=0.3s even in
        fast mode), so the second iteration is always short. The margin is an
        order of magnitude below the cost, which is what makes it deterministic
        rather than a race. Same code path ``main`` uses, clock made explicit.
        """
        import time

        claims_path = _repo(tmp_path, GENUINE_TEST, claims=3)
        deadline = time.monotonic() + (gate.PER_RUN_BUDGET_S * gate.RUNS_PER_CLAIM) + 0.05
        blocked, message, remaining = gate.run_gate(
            root=tmp_path,
            claims_path=claims_path,
            deadline=deadline,
            disable_plugin_autoload=True,
        )
        assert blocked is False, "overflow must not cry wolf"
        assert "UNVERIFIED" in message
        assert message.count("test_add_returns_the_sum") >= 1, (
            "the deferred node ids must be NAMED; an unnamed deferral is a "
            "silent truncation wearing a count"
        )
        assert 0 < len(remaining) < 3, (
            f"expected a partial drain, got {len(remaining)} of 3 requeued"
        )

    def test_the_deferral_is_recorded_where_it_outlives_the_message(
        self, tmp_path: Path
    ) -> None:
        """A stderr line dies with the turn; the JSONL record does not."""
        import time

        claims_path = _repo(tmp_path, GENUINE_TEST, claims=2)
        gate.run_gate(
            root=tmp_path,
            claims_path=claims_path,
            deadline=time.monotonic() + (gate.PER_RUN_BUDGET_S * gate.RUNS_PER_CLAIM) + 0.05,
            disable_plugin_autoload=True,
        )
        logs = sorted((tmp_path / ".claude" / "logs" / "mutation_witness").glob("*.jsonl"))
        assert logs, "no deferral record was written"
        record = json.loads(logs[0].read_text().splitlines()[-1])
        assert record["declared"] == 2
        assert record["claims_that_fit"] == gate.CLAIMS_THAT_FIT
        assert record["verified"] or record["deferred"]


class TestDeliberatelyNotShipped:
    """Scope lock: this hook must stay UNREGISTERED until a producer exists.

    Reviewer BLOCKING-5. Nothing in this repo writes a mutation claim -- no
    agent, command, lib or script -- so the only behaviour a consumer could
    observe from a blocking SubagentStop gate is a FALSE REFUSAL. These are
    negative-assertion locks: they go red the moment someone registers the hook,
    so the decision gets re-litigated deliberately rather than drifting back in.

    To lift the lock: land a producer, then delete this class in the SAME diff
    that re-creates the sidecar (its exact JSON is in the hook's docstring).
    """

    #: Every surface that could register or install the hook.
    SURFACES = (
        "plugins/autonomous-dev/install_manifest.json",
        "plugins/autonomous-dev/config/install_manifest.json",
        "plugins/autonomous-dev/config/global_settings_template.json",
        "plugins/autonomous-dev/templates/settings.autonomous-dev.json",
    )

    @pytest.mark.parametrize("surface", SURFACES)
    def test_the_hook_is_absent_from_every_shipping_surface(self, surface: str) -> None:
        """Not in either manifest, not in either settings template.

        Matches on ``mutation_witness`` rather than ``mutation_witness_gate``:
        the substring covers BOTH halves of the harness, and the library half
        must not ship either (see ``test_the_library_ships_nowhere_either``).
        """
        path = REPO_ROOT / surface
        assert path.is_file(), f"POSITIVE CONTROL: {surface} does not exist"
        assert "mutation_witness" not in path.read_text(encoding="utf-8"), (
            f"{surface} registers or installs part of the mutation harness. "
            f"The gate is a BLOCKING SubagentStop gate with no producer, so "
            f"every firing would be a false refusal (Issue #1660 review, "
            f"BLOCKING-5), and the library it drives has no other consumer."
        )

    def test_the_surfaces_are_the_real_ones(self) -> None:
        """NEGATIVE CONTROL: an absence test over the wrong files proves nothing.

        Each named surface must actually carry hook registrations, otherwise
        "the hook is not in this file" is trivially true of any file on disk.
        """
        for surface in self.SURFACES:
            text = (REPO_ROOT / surface).read_text(encoding="utf-8")
            assert "unified_session_tracker" in text or "unified_pre_tool" in text, (
                f"{surface} carries no known hook registration, so asserting "
                f"the gate's absence from it measures nothing."
            )

    def test_no_sidecar_exists(self) -> None:
        """The generator derives BOTH manifest and settings from sidecars."""
        assert not SIDECAR_PATH.exists(), (
            f"{SIDECAR_PATH} exists, so `generate_hook_config.py --write` will "
            f"re-register the hook on the next run."
        )

    def test_neither_half_is_in_hooks_or_lib(self) -> None:
        """A harness in hooks/ or lib/ is a MEASURED defect, twice over.

        Three shipped ratchets flagged this pair while it sat there:
        ``test_no_new_unreachable_refusers`` (no-lifecycle-registration,
        no-utility-declaration) and ``test_install_manifest_lists_all_hooks``
        for the driver in ``hooks/``; ``test_no_new_unreached_library_modules``
        for the library in ``lib/``, whose only importer
        (``lib/step5_quality_gate.py``) is itself pinned unreached and, since
        #1698, makes everything it imports unreached too.

        Pinning is not an available resolution for any of the three. A gate
        driver waiting on its producer is a script, and so is the module it
        drives; both live beside their sibling ``scripts/integration_ceiling.py``.
        """
        for name in ("mutation_witness_gate.py", "mutation_witness.py"):
            assert not (HOOKS_DIR / name).exists(), (
                f"hooks/{name} is back while registered nowhere; that trips "
                f"the unreachable-refuser ratchet and the manifest guard."
            )
            assert not (LIB_DIR / name).exists(), (
                f"lib/{name} is back. Its only consumer is an unreached "
                f"module, so the reachability ratchet classifies it UNKNOWN."
            )
        for path in (HOOK_PATH, WITNESS_PATH):
            assert path.is_file() and path.parent.name == "scripts", path

    def test_the_library_ships_nowhere_either(self) -> None:
        """Unshipping the driver unships the mechanism it drives. Deliberately.

        INVERTED from ``test_the_library_still_ships``, which asserted the
        opposite. That arm's premise was that the library had a second, shipped
        consumer -- the ``step5_quality_gate`` composition. It did not survive
        review: the host is pinned unreached, so the composition installed a
        mechanism nothing invokes and manufactured the appearance of a backstop.
        A harness that ships nowhere and says so is the honest state.

        This is the arm to delete when a producer lands.
        """
        for manifest in (
            "plugins/autonomous-dev/install_manifest.json",
            "plugins/autonomous-dev/config/install_manifest.json",
        ):
            files = json.loads(
                (REPO_ROOT / manifest).read_text(encoding="utf-8")
            )["components"]["lib"]["files"]
            assert files, f"POSITIVE CONTROL: {manifest} lists no lib files at all"
            assert "plugins/autonomous-dev/lib/step5_quality_gate.py" in files, (
                f"POSITIVE CONTROL: {manifest} no longer lists step5_quality_gate.py, "
                f"so this absence assertion is checking an empty room."
            )
            leaked = [f for f in files if "mutation_witness" in f]
            assert leaked == [], (
                f"{manifest} installs {leaked} as a shipped library. It is a "
                f"scripts/ harness with no producer and no runtime consumer."
            )

    def test_no_producer_exists_yet(self) -> None:
        """States the open gap as an executable fact, not a comment.

        When a producer lands this goes red, which is the prompt to revisit the
        whole unshipped decision above.

        ``-i`` because the match was case-SENSITIVE and a probe writing
        ``MUTATION_CLAIMS`` walked straight past it -- the guard was scoped to
        the casing of the name this harness happens to use. MEASURED: the
        case-insensitive sweep returns the same two files as the sensitive one,
        so widening it costs zero false positives.
        """
        hits = subprocess.run(
            [
                "grep", "-rlni",
                "--include=*.py", "--include=*.md", "--include=*.json",
                "--exclude-dir=__pycache__",
                "mutation_claims\\|MutationClaim(",
                "plugins/autonomous-dev/agents",
                "plugins/autonomous-dev/commands",
                "plugins/autonomous-dev/lib",
                "plugins/autonomous-dev/hooks",
                "scripts",
            ],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        ).stdout.split()
        producers = [
            h for h in hits
            if not h.endswith(("mutation_witness.py", "mutation_witness_gate.py"))
        ]
        assert producers == [], (
            f"a producer now writes mutation claims ({producers}). Issue #1660's "
            f"enforcement loop can be closed: re-create the sidecar, run "
            f"generate_hook_config.py --write, and delete this scope lock."
        )


class TestBypass:
    """Reviewer BLOCKING-3: a gate with no in-session escape wedges the session."""

    def test_a_bypass_marker_permits_and_is_logged(self, tmp_path: Path) -> None:
        """REFUSING claim + `.claude/.bypass` present -> permitted, and recorded."""
        _repo(tmp_path, IS_NOT_NONE_TEST)
        (tmp_path / ".claude").mkdir(exist_ok=True)
        (tmp_path / ".claude" / ".bypass").write_text("", encoding="utf-8")

        proc, decision = _run_hook(tmp_path, {"agent_type": "test-master"})
        assert decision is None, (
            f"the gate refused despite .claude/.bypass: {proc.stdout}"
        )
        bypass_log = tmp_path / ".claude" / "logs" / "hook-bypass.jsonl"
        assert bypass_log.exists(), (
            "the bypass was honoured but not logged; an unrecorded bypass is "
            "indistinguishable from a gate that never ran"
        )
        rows = [json.loads(x) for x in bypass_log.read_text().splitlines() if x]
        assert any(r.get("hook_name") == "mutation_witness_gate.py" for r in rows), rows

    def test_without_the_marker_the_same_claim_is_refused(self, tmp_path: Path) -> None:
        """NEGATIVE CONTROL: otherwise 'permitted' says nothing about the bypass."""
        _repo(tmp_path, IS_NOT_NONE_TEST)
        assert not (tmp_path / ".claude" / ".bypass").exists()
        _, decision = _run_hook(tmp_path, {"agent_type": "test-master"})
        assert decision is not None and decision["decision"] == "block"


class TestRegressionIssue1660:
    """Red before the hook existed, green after."""

    def test_regression_issue_1660_the_boundary_refuses_at_subagent_stop(
        self, tmp_path: Path
    ) -> None:
        """The exact #1660 shape, refused AT THE AGENT BOUNDARY.

        Before this hook, a test asserting ``is not None`` on a target it
        claimed to cover passed every gate in the pipeline: coverage rose, the
        test count rose, it was not a skip, and the skip rate did not move.
        """
        _repo(tmp_path, IS_NOT_NONE_TEST)
        _, decision = _run_hook(tmp_path, {"agent_type": "test-master"})
        assert decision is not None
        assert decision["decision"] == "block"

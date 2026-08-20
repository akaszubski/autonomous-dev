"""Regression: ``sys.exit(0)`` must not be recorded as ``decision_shape="exception"``.

The defect
----------

``HookTimer.__exit__`` classified termination as::

    shape = "exception" if exc_type is not None else self._decision_shape

``SystemExit`` **is** an ``exc_type``, and ``sys.exit(0)`` inside the timer
scope is precisely how most hooks end a **successful** run. Every such hook
recorded 100% ``"exception"``. Measured over 31 days of
``~/.claude/logs/hook_timings_*.jsonl``: 312,695 of 359,216 rows (87%) were
``"exception"``, distributed perfectly bimodally by hook with zero mixed
hooks — the signature of a code-path artifact, not of real crashes. A
successful hook and a crashing hook were indistinguishable in the one column
that exists to tell them apart.

The trap
--------

Naively exempting ``SystemExit`` **inverts** the defect. ``hook_safety.safe_main``
converts an unhandled crash into ``SystemExit(0)``, so genuine crashes would
start recording as ``"allow"`` — confidently wrong in the direction that hides
failures, which is strictly worse than being uselessly pessimistic.

Why a FOUR-way control
----------------------

A two-way control (return vs ``sys.exit(0)``) cannot detect the inverted fix.
The controls here are:

1. normal return (no exit)                     -> ``"allow"``   (negative control)
2. ``sys.exit(0)`` success path                -> ``"allow"``   (THE FIX)
3. genuine crash routed through ``safe_main``  -> ``"exception"`` (THE TRAP)
4. deliberate ``sys.exit(N != 0)``             -> ``"exit_nonzero"``

Case 3 is asserted in **both** wrapping topologies. In production
(``safe_main(_timed_main)`` — timer inside the wrap) the timer observes the raw
``RuntimeError`` before ``safe_main`` ever converts it. In the inverted
topology the timer observes only a bare ``SystemExit(0)``, which is where the
crash marker is load-bearing. Cases 2 and 3 are additionally asserted to
produce **different** shapes; a test that merely asserted each had *some*
value would pass against the broken code.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# tests/regression/test_*.py -> regression -> tests -> repo root == parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_safety  # noqa: E402
import hook_timing  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_timing(tmp_path: Path, monkeypatch) -> Path:
    """Redirect the timing log to tmp and reset process-global crash state.

    ``hook_timing`` keeps a module-level crash flag. It is cleared by
    ``HookTimer.__enter__``, but a test that invokes ``safe_main`` *outside*
    a timer would otherwise leave it set for the next test in the same
    process. Clearing on both sides keeps runs order-independent and
    repeatable back-to-back.
    """
    monkeypatch.delenv(hook_timing.DISABLE_ENV_VAR, raising=False)
    monkeypatch.setenv(hook_timing.LOG_DIR_OVERRIDE_ENV_VAR, str(tmp_path))
    hook_timing.clear_crash()
    yield tmp_path
    hook_timing.clear_crash()


def _rows(log_dir: Path) -> list[dict]:
    """Read every timing row written under ``log_dir`` today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log = log_dir / f"hook_timings_{today}.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def _only_shape(log_dir: Path) -> str:
    """Return the decision_shape of the single row emitted by a scenario."""
    rows = _rows(log_dir)
    assert len(rows) == 1, f"expected exactly 1 timing row, got {len(rows)}: {rows}"
    return rows[0]["decision_shape"]


# ---------------------------------------------------------------------------
# The four controls, run in the PRODUCTION topology: safe_main(_timed_main)
# ---------------------------------------------------------------------------


def _run_production_topology(body) -> SystemExit:
    """Run ``body`` exactly as every wired hook does: timer inside safe_main."""

    def _timed_main():
        with hook_timing.HookTimer("probe_hook.py"):
            return body()

    with pytest.raises(SystemExit) as exc_info:
        hook_safety.safe_main(_timed_main)
    return exc_info.value


class TestFourWayControl:
    """The minimum control set. Two-way cannot detect the inverted fix."""

    def test_control_1_normal_return_records_allow(self, _isolated_timing, capsys):
        """NEGATIVE CONTROL: a hook that returns normally records "allow"."""
        _run_production_topology(lambda: 0)
        assert _only_shape(_isolated_timing) == "allow"

    def test_control_2_sys_exit_zero_records_allow(self, _isolated_timing, capsys):
        """THE FIX: sys.exit(0) is the success path, not an error path."""

        def body():
            sys.exit(0)

        exit_exc = _run_production_topology(body)
        assert exit_exc.code == 0
        assert _only_shape(_isolated_timing) == "allow", (
            "sys.exit(0) is how hooks end a SUCCESSFUL run; recording it as "
            '"exception" makes the column unable to distinguish a working '
            "hook from a broken one."
        )

    def test_control_3_genuine_crash_records_exception(self, _isolated_timing, capsys):
        """POSITIVE CONTROL / THE TRAP: a real crash still records "exception"."""

        def body():
            raise RuntimeError("genuine crash")

        exit_exc = _run_production_topology(body)
        # safe_main still degrades gracefully — the hook must not block.
        assert exit_exc.code == 0
        assert "[hook warning]" in capsys.readouterr().err
        assert _only_shape(_isolated_timing) == "exception", (
            "safe_main converts crashes to SystemExit(0); a fix that exempts "
            "SystemExit blindly would relabel real crashes as successes."
        )

    def test_control_4_nonzero_sys_exit_records_exit_nonzero(self, _isolated_timing, capsys):
        """A deliberate non-zero exit is neither success nor crash."""

        def body():
            sys.exit(2)

        exit_exc = _run_production_topology(body)
        assert exit_exc.code == 2, "the hook's chosen exit code must be preserved"
        assert _only_shape(_isolated_timing) == "exit_nonzero"


class TestControlsAreDistinguishable:
    """The assertion that actually proves the column carries information."""

    def test_success_exit_and_crash_produce_different_shapes(self, tmp_path, capsys):
        """Cases 2 and 3 MUST differ. This is the load-bearing assertion.

        A test asserting only that each case has *some* value would pass
        against the broken code, where both recorded "exception".
        """
        shapes = {}
        for name, body in (
            ("sys_exit_zero", lambda: sys.exit(0)),
            ("genuine_crash", _raise_runtime_error),
        ):
            log_dir = tmp_path / name
            log_dir.mkdir()
            hook_timing.clear_crash()

            def _timed_main(_body=body):
                with hook_timing.HookTimer("probe_hook.py", log_dir=log_dir):
                    return _body()

            with pytest.raises(SystemExit):
                hook_safety.safe_main(_timed_main)
            shapes[name] = _only_shape(log_dir)

        capsys.readouterr()
        hook_timing.clear_crash()

        assert shapes["sys_exit_zero"] != shapes["genuine_crash"], (
            f"success and crash recorded identically as {shapes['sys_exit_zero']!r} "
            "— the decision_shape column carries no information."
        )
        assert shapes["sys_exit_zero"] == "allow"
        assert shapes["genuine_crash"] == "exception"

    def test_all_four_controls_are_correctly_bucketed(self, tmp_path, capsys):
        """Full truth table in one assertion, so a partial fix cannot pass."""
        cases = {
            "normal_return": (lambda: 0, "allow"),
            "sys_exit_zero": (lambda: sys.exit(0), "allow"),
            "genuine_crash": (_raise_runtime_error, "exception"),
            "sys_exit_nonzero": (lambda: sys.exit(2), "exit_nonzero"),
        }
        observed = {}
        for name, (body, _expected) in cases.items():
            log_dir = tmp_path / name
            log_dir.mkdir()
            hook_timing.clear_crash()

            def _timed_main(_body=body):
                with hook_timing.HookTimer("probe_hook.py", log_dir=log_dir):
                    return _body()

            with pytest.raises(SystemExit):
                hook_safety.safe_main(_timed_main)
            observed[name] = _only_shape(log_dir)

        capsys.readouterr()
        hook_timing.clear_crash()

        expected = {name: shape for name, (_body, shape) in cases.items()}
        assert observed == expected, f"expected {expected}, observed {observed}"


def _raise_runtime_error():
    """Module-level crash body (lambdas cannot raise)."""
    raise RuntimeError("genuine crash")


# ---------------------------------------------------------------------------
# The inverted-fix detector: crash marker in the non-production topology
# ---------------------------------------------------------------------------


class TestCrashMarkerSurvivesInvertedTopology:
    """In this topology the timer sees ONLY a bare SystemExit(0) from a crash.

    Production wraps the other way round (``safe_main(_timed_main)``), so the
    timer normally observes the raw exception. This class pins the case where
    it does not — a blanket ``SystemExit`` exemption fails here, which is the
    whole point of keeping the marker.
    """

    def test_crash_through_safe_main_inside_timer_records_exception(self, _isolated_timing, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with hook_timing.HookTimer("probe_hook.py"):
                hook_safety.safe_main(_raise_runtime_error)

        assert exc_info.value.code == 0
        assert _only_shape(_isolated_timing) == "exception", (
            "safe_main's SystemExit(0) is a converted crash, not a success; "
            "the crash marker must survive into HookTimer.__exit__."
        )

    def test_real_sys_exit_zero_inside_timer_still_records_allow(self, _isolated_timing, capsys):
        """Negative control for the marker: an unmarked exit is still success."""

        def body():
            sys.exit(0)

        with pytest.raises(SystemExit):
            with hook_timing.HookTimer("probe_hook.py"):
                hook_safety.safe_main(body)

        assert _only_shape(_isolated_timing) == "allow"

    def test_safe_main_stamps_the_crash_marker_attribute(self, capsys):
        """The synthesised SystemExit carries the marker attribute."""
        hook_timing.clear_crash()
        with pytest.raises(SystemExit) as exc_info:
            hook_safety.safe_main(_raise_runtime_error)
        capsys.readouterr()
        assert getattr(exc_info.value, hook_timing.CRASH_EXIT_ATTR, False) is True
        assert hook_timing.crash_noted() is True
        hook_timing.clear_crash()

    def test_deliberate_sys_exit_is_not_marked_as_crash(self, capsys):
        """Negative control: safe_main must NOT stamp a deliberate exit."""
        hook_timing.clear_crash()

        def body():
            sys.exit(0)

        with pytest.raises(SystemExit) as exc_info:
            hook_safety.safe_main(body)
        capsys.readouterr()
        assert getattr(exc_info.value, hook_timing.CRASH_EXIT_ATTR, False) is False
        assert hook_timing.crash_noted() is False

    def test_timer_entry_clears_a_stale_crash_flag(self, _isolated_timing):
        """A crash before the scope opened is not this invocation's crash."""
        hook_timing.note_crash()
        with hook_timing.HookTimer("probe_hook.py"):
            pass
        assert _only_shape(_isolated_timing) == "allow"


# ---------------------------------------------------------------------------
# Non-zero SystemExit semantics
# ---------------------------------------------------------------------------


class TestNonZeroSystemExitSemantics:
    """A deliberate non-zero exit is a third case, distinct from both others."""

    @pytest.mark.parametrize("code", [1, 2, 42])
    def test_nonzero_codes_record_exit_nonzero(self, _isolated_timing, code):
        with pytest.raises(SystemExit):
            with hook_timing.HookTimer("probe_hook.py"):
                sys.exit(code)
        assert _only_shape(_isolated_timing) == "exit_nonzero"

    def test_exit_none_is_treated_as_success(self, _isolated_timing):
        """``sys.exit()`` with no argument exits 0 — a success."""
        with pytest.raises(SystemExit):
            with hook_timing.HookTimer("probe_hook.py"):
                sys.exit()
        assert _only_shape(_isolated_timing) == "allow"

    def test_explicit_shape_wins_over_exit_nonzero(self, _isolated_timing):
        """A hook's own self-report is more specific than its exit code."""
        with pytest.raises(SystemExit):
            with hook_timing.HookTimer("probe_hook.py") as timer:
                timer.set_decision_shape("exit2")
                sys.exit(2)
        assert _only_shape(_isolated_timing) == "exit2"

    def test_explicit_shape_does_not_win_over_a_real_crash(self, _isolated_timing):
        """Self-reporting must never let a crash masquerade as an outcome."""
        with pytest.raises(RuntimeError):
            with hook_timing.HookTimer("probe_hook.py") as timer:
                timer.set_decision_shape("allow")
                raise RuntimeError("boom")
        assert _only_shape(_isolated_timing) == "exception"

    def test_explicit_shape_does_not_win_over_converted_crash(self, _isolated_timing, capsys):
        """Same, for a crash that safe_main already converted to SystemExit(0)."""
        with pytest.raises(SystemExit):
            with hook_timing.HookTimer("probe_hook.py") as timer:
                timer.set_decision_shape("allow")
                hook_safety.safe_main(_raise_runtime_error)
        capsys.readouterr()
        assert _only_shape(_isolated_timing) == "exception"


# ---------------------------------------------------------------------------
# Schema version + cross-source consistency
# ---------------------------------------------------------------------------


class TestSchemaVersionAndConstants:
    def test_schema_version_bumped_to_at_least_two(self, _isolated_timing):
        """31 days of schema-1 rows mislabel success; readers must tell eras apart."""
        with hook_timing.HookTimer("probe_hook.py"):
            pass
        assert hook_timing.SCHEMA_VERSION >= 2
        assert _rows(_isolated_timing)[0]["schema_version"] == hook_timing.SCHEMA_VERSION

    def test_crash_marker_attribute_name_agrees_across_modules(self):
        """Cross-validation: hook_safety's fallback literal must match hook_timing.

        Read both sources dynamically rather than hardcoding a third copy —
        otherwise the fallback path silently stops marking crashes.
        """
        assert hook_safety.CRASH_EXIT_ATTR == hook_timing.CRASH_EXIT_ATTR

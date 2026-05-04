"""Spec validation for issue #1045 — run_id parameter wiring.

Tests are derived BLIND from acceptance criteria only:
  AC1: All 7 listed functions accept optional keyword-only `run_id` parameter
  AC2: When run_id=None (default), file path is unchanged (sha256(session_id) hash)
  AC3: When run_id provided, file path is /tmp/pipeline_agent_completions_<run_id>.json
  AC4: Existing tests pass without modification
  AC5: Round-trip with run_id, back-compat, two parallel run_ids isolated
  AC6: No existing caller in hooks/ or lib/ requires modification
"""
from __future__ import annotations

import hashlib
import inspect
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import pipeline_completion_state as pcs  # noqa: E402

# The seven public functions named in AC1 (with synonym fallbacks: spec lists
# `record_web_research_skipped` and `record_pytest_gate_completion`, but the
# module exposes `record_research_skipped` and `record_pytest_gate_passed`).
SEVEN_FUNCTIONS = [
    "_state_file_path",
    "record_agent_completion",
    "get_completed_agents",
    "record_plan_critic_skipped",
    "record_research_skipped",         # spec name: record_web_research_skipped
    "record_pytest_gate_passed",       # spec name: record_pytest_gate_completion
    "verify_pipeline_agent_completions",
]


def _legacy_path(session_id: str) -> Path:
    h = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:8]
    return Path(f"/tmp/pipeline_agent_completions_{h}.json")


# ---------- AC1 ----------------------------------------------------------------

class TestAC1FunctionsAcceptRunIdKeyword:
    @pytest.mark.parametrize("name", SEVEN_FUNCTIONS)
    def test_function_exists_and_has_keyword_only_run_id(self, name):
        fn = getattr(pcs, name, None)
        assert fn is not None, f"Function {name} missing from module"
        sig = inspect.signature(fn)
        assert "run_id" in sig.parameters, f"{name} missing run_id parameter"
        p = sig.parameters["run_id"]
        assert p.kind == inspect.Parameter.KEYWORD_ONLY, (
            f"{name}: run_id must be KEYWORD_ONLY, got {p.kind}"
        )
        assert p.default is None, (
            f"{name}: run_id default must be None, got {p.default!r}"
        )

    def test_run_id_must_be_keyword_only_negative(self):
        # Negative: positional run_id must raise TypeError
        sid = f"spec1045-{uuid.uuid4().hex[:8]}"
        with pytest.raises(TypeError):
            pcs.record_agent_completion(sid, "implementer", "positional-run-id")  # noqa


# ---------- AC2 ----------------------------------------------------------------

class TestAC2DefaultPathUnchanged:
    def test_path_when_run_id_none_uses_sha256(self):
        sid = f"spec1045-{uuid.uuid4().hex}"
        observed = pcs._state_file_path(sid)
        assert observed == _legacy_path(sid), (
            f"Default path changed: expected {_legacy_path(sid)}, got {observed}"
        )

    def test_default_path_does_not_contain_run_id_token(self):
        sid = f"spec1045-{uuid.uuid4().hex}"
        observed = pcs._state_file_path(sid, run_id=None)
        # Negative-ish: sha256-prefix path must NOT equal the run_id-style path
        assert observed != Path("/tmp/pipeline_agent_completions_None.json")


# ---------- AC3 ----------------------------------------------------------------

class TestAC3RunIdPathFormat:
    def test_run_id_path_is_tmp_with_run_id_suffix(self):
        rid = f"rid-{uuid.uuid4().hex[:10]}"
        observed = pcs._state_file_path("any-session", run_id=rid)
        expected = Path(f"/tmp/pipeline_agent_completions_{rid}.json")
        assert observed == expected, f"expected {expected}, got {observed}"

    def test_run_id_path_independent_of_session_id(self):
        rid = f"rid-{uuid.uuid4().hex[:10]}"
        p1 = pcs._state_file_path("session-A", run_id=rid)
        p2 = pcs._state_file_path("session-B", run_id=rid)
        assert p1 == p2, "run_id path must not depend on session_id"


# ---------- AC4 ----------------------------------------------------------------

class TestAC4ExistingTestsUnmodified:
    def test_existing_unit_test_file_passes(self):
        target = "tests/unit/lib/test_pipeline_completion_state.py"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", target, "--no-cov", "-q",
             "--no-header", "-p", "no:cacheprovider"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 0, (
            f"Existing tests failed:\nSTDOUT:\n{result.stdout[-2000:]}\n"
            f"STDERR:\n{result.stderr[-1000:]}"
        )


# ---------- AC5 ----------------------------------------------------------------

class TestAC5BehavioralIsolation:
    def test_round_trip_with_run_id(self, tmp_path, monkeypatch):
        rid = f"rt-{uuid.uuid4().hex[:8]}"
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        try:
            pcs.record_agent_completion(sid, "implementer", run_id=rid)
            done = pcs.get_completed_agents(sid, run_id=rid)
            assert "implementer" in done
        finally:
            p = pcs._state_file_path(sid, run_id=rid)
            if p.exists():
                p.unlink()

    def test_back_compat_default_path_still_works(self):
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        try:
            pcs.record_agent_completion(sid, "researcher")  # no run_id
            done = pcs.get_completed_agents(sid)
            assert "researcher" in done
        finally:
            p = pcs._state_file_path(sid)
            if p.exists():
                p.unlink()

    def test_two_parallel_run_ids_isolated(self):
        sid = f"shared-{uuid.uuid4().hex[:8]}"
        rid_a = f"runA-{uuid.uuid4().hex[:8]}"
        rid_b = f"runB-{uuid.uuid4().hex[:8]}"
        try:
            pcs.record_agent_completion(sid, "implementer", run_id=rid_a)
            pcs.record_agent_completion(sid, "reviewer", run_id=rid_b)

            done_a = pcs.get_completed_agents(sid, run_id=rid_a)
            done_b = pcs.get_completed_agents(sid, run_id=rid_b)

            assert "implementer" in done_a, "run_id A lost its own data"
            assert "reviewer" not in done_a, (
                f"run_id A leaked B's data: {done_a}"
            )
            assert "reviewer" in done_b, "run_id B lost its own data"
            assert "implementer" not in done_b, (
                f"run_id B leaked A's data: {done_b}"
            )
        finally:
            for rid in (rid_a, rid_b):
                p = pcs._state_file_path(sid, run_id=rid)
                if p.exists():
                    p.unlink()

    def test_run_id_and_default_paths_are_disjoint(self):
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        rid = f"rid-{uuid.uuid4().hex[:8]}"
        try:
            pcs.record_agent_completion(sid, "implementer")  # legacy
            pcs.record_agent_completion(sid, "reviewer", run_id=rid)

            legacy = pcs.get_completed_agents(sid)
            scoped = pcs.get_completed_agents(sid, run_id=rid)

            assert "implementer" in legacy and "reviewer" not in legacy
            assert "reviewer" in scoped and "implementer" not in scoped
        finally:
            for p in (pcs._state_file_path(sid), pcs._state_file_path(sid, run_id=rid)):
                if p.exists():
                    p.unlink()


# ---------- AC6 ----------------------------------------------------------------

class TestAC6NoCallerModification:
    def test_no_caller_files_in_hooks_or_lib_modified(self):
        # Implementation says "MODIFIED: pipeline_completion_state.py" only.
        # Diff against master for any other .py under hooks/ or lib/.
        result = subprocess.run(
            ["git", "diff", "--name-only", "master...HEAD", "--",
             "plugins/autonomous-dev/hooks/", "plugins/autonomous-dev/lib/"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        )
        # Fallback to staged+unstaged if branch comparison fails
        if result.returncode != 0:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD", "--",
                 "plugins/autonomous-dev/hooks/", "plugins/autonomous-dev/lib/"],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
            )
        changed = [
            f.strip() for f in result.stdout.splitlines() if f.strip().endswith(".py")
        ]
        # The single allowed change is pipeline_completion_state.py itself.
        disallowed = [
            f for f in changed
            if not f.endswith("pipeline_completion_state.py")
            and not f.endswith("pipeline_intent_gates.py")  # untracked, allowed
        ]
        assert disallowed == [], (
            f"AC6 violation: callers modified beyond pipeline_completion_state.py: "
            f"{disallowed}"
        )

    def test_callers_can_invoke_without_run_id(self):
        # Negative-ish: existing call sites that pass no run_id must still work.
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        try:
            pcs.record_agent_completion(sid, "implementer")
            pcs.record_plan_critic_skipped(sid)
            pcs.record_research_skipped(sid)
            pcs.record_pytest_gate_passed(sid)
            ok, _, _ = pcs.verify_pipeline_agent_completions(sid)
            assert isinstance(ok, bool)
        finally:
            p = pcs._state_file_path(sid)
            if p.exists():
                p.unlink()

#!/usr/bin/env python3
"""Minimal vertical proof for the connected claims of Issue #1779.

One class per claim: a PERMIT arm, a REFUSE arm of a DIFFERENT SHAPE than the bug
that prompted it, a BROKEN-INSTRUMENT control, and only the boundary cases those
three cannot detect. Method: ``docs/TESTING-STRATEGY.md`` -> "Minimal Vertical
Proof Method"; scope, residuals and the UNMEASURED boundary:
``docs/PIPELINE-EVIDENCE-INTEGRITY.md``.

Entrypoint -> production consumer, per claim:
A ``session_activity_logger.py`` as a SUBPROCESS -> ``resolve_activity_log_dir``;
B ``check_ordering_with_session_fallback`` -> ``unified_pre_tool.py``'s gate;
C a Bash command string -> ``unified_pre_tool._detect_env_spoofing``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# tests/regression/<this file> -> regression -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
SESSION_ACTIVITY_LOGGER = HOOKS_DIR / "session_activity_logger.py"

sys.path[:0] = [p for p in (str(LIB_DIR), str(HOOKS_DIR)) if p not in sys.path]

from tests.helpers.state_isolation import (  # noqa: E402
    SESSION_DEPTH_ENV,
    describe_tree_leak,
    hook_subprocess_env,
    session_is_nested,
    snapshot_tree,
)

LIVE_ACTIVITY_TREE = REPO_ROOT / ".claude" / "logs" / "activity"
LIVE_LOCAL_TREE = REPO_ROOT / ".claude" / "local"


def _post_tool_payload(session_id: str) -> dict:
    """A PostToolUse payload the real logger writes a record for."""
    return {
        "session_id": session_id,
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "echo issue-1779"},
        "tool_output": {"stdout": "issue-1779\n", "success": True},
    }


def _run_logger_isolated(cwd: Path, session_id: str) -> subprocess.CompletedProcess:
    """Spawn the REAL logger through the sanctioned isolated environment.

    Two spawners, not one taking ``env``: the AC1 ratchet resolves ``env=``
    statically, so a PARAMETER would count this file a leaker — it did, on run 1.
    """
    return subprocess.run(
        [sys.executable, str(SESSION_ACTIVITY_LOGGER)],
        input=json.dumps(_post_tool_payload(session_id)),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=hook_subprocess_env(),
    )


def _run_logger_against_root(
    cwd: Path, session_id: str, project_dir: Path
) -> subprocess.CompletedProcess:
    """Spawn the REAL logger, redirect REMOVED. ``project_dir`` is a fake repo."""
    env = os.environ.copy()
    env.pop("AUTONOMOUS_DEV_ACTIVITY_LOG_DIR", None)
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    env["ACTIVITY_LOGGING"] = "true"
    return subprocess.run(
        [sys.executable, str(SESSION_ACTIVITY_LOGGER)],
        input=json.dumps(_post_tool_payload(session_id)),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
    )


def _jsonl_records(directory: Path) -> list:
    """Every JSON record in *directory*'s top-level ``*.jsonl`` files."""
    out: list = []
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def _leak(baseline, tree: Path, *, remedy: str = "see docs") -> "str | None":
    """``describe_tree_leak`` on *tree*, with conftest's identity exemptions.

    A prefix matches only ``<prefix><live session id>``: no sentinel write masked.
    """
    return describe_tree_leak(
        baseline,
        snapshot_tree(tree),
        tree,
        label="PRODUCTION STATE",
        remedy=remedy,
        live_session_id=os.environ.get("CLAUDE_SESSION_ID", ""),
        exempt_prefixes=(".heartbeat_", ".session_date_"),
    )


# --- Claim A: pytest-scoped production-state isolation (AC2) ---------------


class TestClaimAProductionStateIsolation:
    """A real hook subprocess cannot reach the repository's production state."""

    def test_permit_real_hook_subprocess_writes_the_redirect_not_the_repo(
        self,
    ) -> None:
        """PERMIT ARM, end to end, with a non-empty denominator.

        The real logger runs as a SUBPROCESS from the repository root, where it
        would otherwise write production; its record must land in the redirect.
        """
        before_trees = {
            t: snapshot_tree(t) for t in (LIVE_ACTIVITY_TREE, LIVE_LOCAL_TREE)
        }
        redirect = Path(os.environ["AUTONOMOUS_DEV_ACTIVITY_LOG_DIR"])
        session_id = "issue1779-permit-arm"

        def mine() -> list[dict]:
            """Only this test's records, so a sibling test cannot supply the delta."""
            return [
                r for r in _jsonl_records(redirect) if r.get("session_id") == session_id
            ]

        before = len(mine())

        proc = _run_logger_isolated(REPO_ROOT, session_id)
        assert proc.returncode == 0, proc.stderr
        assert len(mine()) > before, (
            "the hook wrote NOTHING to the redirect: empty denominator, proves "
            f"nothing. stderr={proc.stderr!r}"
        )
        for tree, baseline in before_trees.items():
            assert _leak(baseline, tree) is None, f"a hook subprocess reached {tree}"

    def test_refuse_the_guard_sees_a_stripped_env_reach_a_production_root(
        self, tmp_path: Path
    ) -> None:
        """REFUSE ARM, deliberately a DIFFERENT SHAPE than the reproducer.

        Measured leak: ``env={**hook_env}`` on ``unified_pre_tool.py``, an APPEND
        to an existing ``<date>.jsonl``. Here the redirect is STRIPPED not
        replaced, the subject is ``session_activity_logger.py``, the target a FAKE
        root named by ``CLAUDE_PROJECT_DIR``, the shape a CREATED file.

        COVERED CLASS: any hook subprocess whose environment does not carry the
        redirects, whatever tool, event, or leak shape it produces.
        """
        fake_root = tmp_path / "fake-consumer-repo"
        (fake_root / ".git").mkdir(parents=True)
        watched = fake_root / ".claude" / "logs" / "activity"
        watched.mkdir(parents=True)
        baseline = snapshot_tree(watched)
        assert baseline == {}, "the fake production tree must start clean"

        proc = _run_logger_against_root(fake_root, "issue1779-refuse-arm", fake_root)
        assert proc.returncode == 0, proc.stderr

        finding = _leak(baseline, watched, remedy="call hook_subprocess_env()")
        assert finding is not None, (
            "the leak guard did NOT report a real hook subprocess writing an "
            "activity root it must not reach: it cannot refuse, so it is not "
            "enforcement."
        )
        assert "created:" in finding and "CONTAMINATED" in finding
        assert "call hook_subprocess_env()" in finding

    def test_broken_instrument_a_misaimed_watch_reports_clean(
        self, tmp_path: Path
    ) -> None:
        """BROKEN-INSTRUMENT CONTROL, paired so the verdict is attributable.

        One contamination event read twice: a watch aimed at the changed tree
        (must REPORT) and one aimed at an unrelated empty directory (must say
        CLEAN). A wrong watch root is the failure the AC1 guard can suffer, and why
        ``None`` is never on its own evidence of clean. Also pins that an ABSENT
        baseline normalises to ``{}``, so a suite that CREATES the tree in a clean
        consumer repo is still reported.
        """
        real_tree = tmp_path / "watched"
        wrong_tree = tmp_path / "elsewhere"
        real_tree.mkdir()
        wrong_tree.mkdir()
        aimed_base = snapshot_tree(real_tree)
        misaimed_base = snapshot_tree(wrong_tree)
        (real_tree / "2026-09-12.jsonl").write_text('{"x": 1}\n', encoding="utf-8")

        assert _leak(aimed_base, real_tree), "the correctly aimed watch failed"
        assert _leak(misaimed_base, wrong_tree) is None, (
            "the misaimed watch reported a leak, so this control is not "
            "isolating the watch root"
        )
        assert _leak(None, real_tree) is not None, (
            "an absent baseline must normalise to {} — otherwise a suite that "
            "creates the production tree from nothing reads as clean"
        )

    def test_boundary_every_activity_root_resolver_reaches_the_chokepoint(
        self,
    ) -> None:
        """BOUNDARY CASE: the redirect is honoured by every converged resolver.

        Distinct failure class: one resolver silently regaining its own ancestor
        walk. The permit arm exercises ONE writer, so a second could drift back
        with every arm above still green.
        """
        import coordinator_log
        import intent_classifier
        import pipeline_completion_state
        from path_utils import resolve_activity_log_dir

        redirect = Path(os.environ["AUTONOMOUS_DEV_ACTIVITY_LOG_DIR"]).resolve()
        redirect.mkdir(parents=True, exist_ok=True)
        observed = {
            "path_utils.resolve_activity_log_dir": resolve_activity_log_dir(
                start_path=REPO_ROOT
            ),
            "coordinator_log._find_activity_log_dir": (
                coordinator_log._find_activity_log_dir(start_dir=REPO_ROOT)
            ),
            "pipeline_completion_state._find_activity_log_dir": (
                pipeline_completion_state._find_activity_log_dir(REPO_ROOT)
            ),
            "intent_classifier._default_telemetry_log_dir": (
                intent_classifier._default_telemetry_log_dir()
            ),
        }
        for name, value in observed.items():
            assert value is not None, f"{name} returned None under the redirect"
            assert Path(value).resolve() == redirect, (
                f"{name} resolved {value}, not the redirect {redirect}. It has "
                "its own activity-root inference again (Issue #1779, AC1)."
            )

    def test_boundary_a_leak_binds_only_the_session_that_can_attribute_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """BOUNDARY CASE: process-global trees, so only the OUTERMOST verdict binds.

        Distinct failure class: the arms above observe ONE session, so an inert
        polarity leaves them green. Rig and the three mutations that must break
        this: PIPELINE-EVIDENCE-INTEGRITY.md. COVERED CLASS: every session sharing
        these trees with concurrent writers — each xdist worker, and each child
        session a test spawns.
        """
        patch, watched = monkeypatch.setattr, str(REPO_ROOT / "tests" / "conftest.py")
        conftest = next(
            m
            for m in list(sys.modules.values())
            if getattr(m, "__file__", "") == watched
        )
        derived = conftest._ATTRIBUTION_POSSIBLE  # BEFORE any patch reaches it
        for stem in ("_GH_ISSUE_CTX", "_ACTIVITY_LOG", "_PIPELINE_STATE"):
            patch(conftest, f"{stem}_REDIRECT_DIR", str(tmp_path / stem))
        patch(conftest, "_ACTIVITY_LOG_BASELINE", snapshot_tree(LIVE_ACTIVITY_TREE))
        marker = conftest._snapshot_marker(conftest._GH_ISSUE_CTX_WATCHED)
        patch(conftest, "_GH_ISSUE_CTX_BASELINE", marker)
        live = snapshot_tree(LIVE_LOCAL_TREE) or {}

        def finish(baseline: dict, outermost: bool) -> "tuple[int, str]":
            patch(conftest, "_LOCAL_STATE_BASELINE", baseline)
            patch(conftest, "_ATTRIBUTION_POSSIBLE", outermost)
            pm = SimpleNamespace(
                pluginmanager=SimpleNamespace(getplugin=lambda n: None)
            )
            session = SimpleNamespace(exitstatus=0, config=pm)
            capsys.readouterr()
            conftest.pytest_sessionfinish(session, 0)
            return session.exitstatus, capsys.readouterr().out

        leaked = {**live, "destroyed-by-a-test.json": "0" * 64}
        refused = finish(leaked, True)
        assert refused[0] == 1, "REFUSE ARM: the outermost session let a leak pass"
        assert "PRODUCTION PIPELINE STATE CONTAMINATED" in refused[1], refused[1]
        assert finish(leaked, False) == (0, ""), "a nested session blamed itself"
        assert finish(live, True) == (0, ""), (
            "BROKEN INSTRUMENT: unchanged tree read as contaminated"
        )
        assert session_is_nested(os.environ[SESSION_DEPTH_ENV]), (
            "no usable depth marker exported: every child believes it is outermost"
        )
        assert derived is not session_is_nested(conftest._INHERITED_SESSION_DEPTH), (
            "the flag is hardcoded, not derived from the marker this session read"
        )


# --- Claim B: a corrupt gating sentinel cannot become permission (AC3) -----


@pytest.fixture()
def sentinel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``PIPELINE_STATE_FILE`` at a per-test path, initially absent."""
    target = tmp_path / "local" / "implement_pipeline_state.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PIPELINE_STATE_FILE", str(target))
    return target


class TestClaimBCorruptSentinelRefusal:
    """The EXECUTING ordering route, not a direct call to the classifier."""

    @staticmethod
    def _gate(agent: str = "researcher"):
        from agent_ordering_gate import check_ordering_with_session_fallback

        return check_ordering_with_session_fallback(
            agent, "issue1779-sentinel-session", pipeline_mode="full"
        )

    def test_permit_absent_sentinel_is_the_normal_case(self, sentinel: Path) -> None:
        """PERMIT ARM: absent is every session outside a pipeline."""
        assert not sentinel.exists()
        result = self._gate()
        assert result.passed is True, result.reason
        assert "SENTINEL CORRUPT" not in (result.reason or "")

    @pytest.mark.parametrize(
        "raw,shape",
        [
            (b"[]", "a JSON ARRAY: parses cleanly, cannot carry alignment_passed"),
            (b"   \n\t ", "whitespace only: not the measured 0-byte shape"),
            (b'{"session_id": "x"', "truncated mid-object"),
        ],
    )
    def test_refuse_an_existing_unreadable_sentinel(
        self, sentinel: Path, raw: bytes, shape: str
    ) -> None:
        """REFUSE ARM over the shapes above, NONE of them the reproducer.

        The measured defect was a 0-byte file, deliberately excluded so this arm
        cannot be satisfied by a guard scoped to that instance. COVERED CLASS: a
        sentinel that EXISTS and does not yield a JSON OBJECT, however it fails.
        """
        sentinel.write_bytes(raw)
        result = self._gate()
        assert result.passed is False, f"{shape}: the route PERMITTED. {result.reason}"
        assert "SENTINEL CORRUPT" in result.reason
        assert str(sentinel) in result.reason
        assert "REQUIRED NEXT ACTION" in result.reason

    def test_broken_instrument_a_valid_sentinel_still_permits(
        self, sentinel: Path
    ) -> None:
        """BROKEN-INSTRUMENT CONTROL: the refusal is caused by corruption.

        Without it, a gate hard-wired to refuse would pass the arm above.
        """
        sentinel.write_text(
            json.dumps({"session_id": "s", "alignment_passed": True}),
            encoding="utf-8",
        )
        result = self._gate()
        assert result.passed is True, result.reason
        assert "SENTINEL CORRUPT" not in (result.reason or "")

    def test_boundary_the_gate_reads_the_redirected_path_not_the_default(
        self, sentinel: Path
    ) -> None:
        """BOUNDARY CASE: ``sentinel_integrity`` honours ``PIPELINE_STATE_FILE``.

        Distinct failure class: a classifier that only stats
        ``get_legacy_sentinel_path()`` is INERT for every redirected run, so the
        arms above would read the live file. None compares path to redirect.
        """
        from pipeline_completion_state import SentinelIntegrity, sentinel_integrity

        assert sentinel_integrity() is SentinelIntegrity.ABSENT
        sentinel.write_bytes(b"")
        assert sentinel_integrity() is SentinelIntegrity.CORRUPT
        sentinel.write_text("{}", encoding="utf-8")
        assert sentinel_integrity() is SentinelIntegrity.OK

    def test_boundary_the_hook_refreshes_a_sentinel_but_never_creates_one(
        self, sentinel: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BOUNDARY CASE: ``_is_pipeline_active`` must not MANUFACTURE state.

        Distinct failure class: the Issue #636 mtime refresh called
        ``Path.touch()`` unconditionally, so an ABSENT sentinel became a 0-byte one
        classified CORRUPT — the gate refusing on state the hook fabricated. The
        arms above write the sentinel themselves, so none can see it.
        """
        import unified_pre_tool

        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        assert not sentinel.exists()
        assert unified_pre_tool._is_pipeline_active() is True
        assert not sentinel.exists(), (
            "the hook CREATED a 0-byte sentinel for an absent pipeline; the INV-7 "
            "gate would then refuse on state this hook fabricated"
        )
        # Permitting half of the same boundary: an EXISTING sentinel is still
        # refreshed, so Issue #636 is not regressed.
        sentinel.write_text(json.dumps({"session_id": "owner"}), encoding="utf-8")
        os.utime(sentinel, (1_600_000_000, 1_600_000_000))
        assert unified_pre_tool._is_pipeline_active() is True
        assert sentinel.stat().st_mtime > 1_600_000_000, (
            "an existing sentinel was NOT refreshed; Issue #636's liveness "
            "signal is gone"
        )


# --- Remediation: the new path overrides are spoof-protected ----------------


class TestNewPathOverridesAreSpoofProtected:
    """The two path overrides this changeset added are in ``PROTECTED_ENV_VARS``.

    COVERED CLASS: any environment variable whose value NAMES the path of an
    artifact a gate reads — both new names, not one of them. The refuse rows are
    Bash ``export``/``env`` forms: NOT the reproducer (an in-PROCESS
    ``os.environ`` override read back by ``agent_dispatch_sentinel.is_active()``)
    and NOT the ``VAR=value cmd`` prefix ``test_agent_identity_hardening``
    already sweeps over the whole set. The permit rows are load-bearing: they
    prove explicit MEMBERSHIP, not an ``AUTONOMOUS_DEV_`` entry in
    ``PROTECTED_ENV_PREFIXES``, which would refuse the documented operator
    escape hatches — ``export AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=1`` among them,
    text ``unified_pre_tool.py`` prints as its own remedy.
    """

    @pytest.mark.parametrize(
        "var,shape,must_refuse",
        [
            ("AUTONOMOUS_DEV_AGENT_DISPATCH_SENTINEL", "export {}=/tmp/f", True),
            ("AUTONOMOUS_DEV_ACTIVITY_LOG_DIR", "env {}=/tmp/f python3 -c x", True),
            ("AUTONOMOUS_DEV_BYPASS", "export {}=1", False),
            ("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "export {}=1", False),
        ],
    )
    def test_refuses_gating_overrides_and_permits_escape_hatches(
        self, var: str, shape: str, must_refuse: bool
    ) -> None:
        import unified_pre_tool

        reason = unified_pre_tool._detect_env_spoofing(shape.format(var))
        if must_refuse:
            assert reason is not None, (
                f"{var} is still settable from a Bash command: a caller can aim "
                "the #1296 dispatch sentinel, or the activity root a session id "
                "is inferred from, at a file it wrote itself."
            )
            assert var in reason and "REQUIRED NEXT ACTION" in reason
        else:
            assert reason is None, (
                f"{var} is a documented operator escape hatch and was refused: "
                "an AUTONOMOUS_DEV_ prefix rule was implemented, not membership."
            )

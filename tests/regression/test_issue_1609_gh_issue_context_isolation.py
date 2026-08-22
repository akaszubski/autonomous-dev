"""Regression tests for Issue #1609 — global gh-issue context marker leak.

``/tmp/autonomous_dev_cmd_context.json`` is a global sanctioning marker: its
presence tells ``_detect_gh_issue_create`` and its sibling detectors in
``unified_pre_tool.py`` that an issue-creating command is legitimately in
flight, so they PERMIT what they would otherwise REFUSE.

Measured on 2026-08-22 against ``3c014e87``, one variable changed::

    marker absent  -> pytest tests/unit/hooks/test_gh_issue_create_block.py
                      -> 165 passed
    marker present -> same command
                      -> 49 failed, 116 passed

and the leak itself::

    rm -f /tmp/autonomous_dev_cmd_context.json
    pytest tests/unit/lib/test_daily_aggregate_manager.py -q   -> 10 passed
    ls /tmp/autonomous_dev_cmd_context.json                    -> PRESENT

This module locks four independent properties:

1. the ordering dependence is gone (headline reproducer, subprocess);
2. the block tests pass in isolation even with the REAL marker present, i.e.
   they no longer consult the real path at all;
3. the leak guard both REFUSES a reintroduced leak and PERMITS a clean run;
4. no production writer can name the raw literal without going through the
   env-var-honouring accessor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOK_FILE = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"

sys.path.insert(0, str(LIB_DIR))

from gh_issue_context import (  # noqa: E402
    CONTEXT_PATH_ENV_VAR,
    DEFAULT_CONTEXT_PATH,
    gh_issue_context_path,
)

sys.path.insert(0, str(REPO_ROOT))

from tests.helpers.gh_issue_marker_guard import (  # noqa: E402
    MarkerState,
    describe_marker_leak,
    snapshot_marker,
)

BLOCK_TESTS = "tests/unit/hooks/test_gh_issue_create_block.py"
LEAKING_TESTS = "tests/unit/lib/test_daily_aggregate_manager.py"

# Child pytest runs: no coverage plugin (it would re-apply the repo-wide
# --cov-fail-under against a two-file run) and no cache writes.
_CHILD_ARGS = ["-q", "--no-header", "-p", "no:cacheprovider", "--no-cov"]


def _run_child_pytest(args: "list[str]", *, env_extra: "dict[str, str] | None" = None):
    """Run pytest in a child process rooted at the repo.

    Args:
        args: pytest arguments (test paths and flags).
        env_extra: Environment overrides for the child.

    Returns:
        The completed process, with stdout and stderr captured as text.
    """
    env = dict(os.environ)
    # The parent's own redirect must not leak into the child: each child
    # installs its own via tests/conftest.py.
    env.pop(CONTEXT_PATH_ENV_VAR, None)
    env.pop("AUTONOMOUS_DEV_TEST_CTX_WATCH_PATH", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "pytest", *_CHILD_ARGS, *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )


class _RealMarkerPlanted:
    """Context manager that plants the REAL marker, or refuses to.

    EXPLICIT TRADE-OFF — read before reusing or "simplifying" this.

    What it switches off: a valid sanctioning marker at the real global path
    tells ``_detect_gh_issue_create`` and its siblings that an issue-creating
    command is legitimately in flight. While it is planted, ANY other process on
    this machine issuing ``gh issue create`` is silently PERMITTED rather than
    refused — including a concurrent Claude session, which this operator
    routinely runs 2-3 of.

    For how long: the duration of one child pytest run over
    ``test_gh_issue_create_block.py`` (165 tests, order-of-seconds), bounded by
    the ``timeout=900`` on ``_run_child_pytest``.

    Why not ``tmp_path``: a ``tmp_path`` variant would prove only that the block
    tests ignore *some* path, which is what the redirect already guarantees by
    construction and therefore cannot fail. The claim under test is specifically
    "the block tests no longer consult the REAL global path", and only the real
    path can refute it. Weakening this to a temp path would convert a negative
    control into a tautology.

    What bounds the risk — MECHANICALLY, not by convention:

    * **The plant is ``O_EXCL``.** If the path already exists — a concurrent
      session's in-flight ``/create-issue``, or a leftover from ``/triage`` —
      the create fails and the test SKIPS with a message naming why. There is no
      overwrite fallback. On that path the file is not read, not stat'ed, not
      written and not unlinked: whoever owns it keeps it, byte for byte.
    * **The window only ever opens on a path that was verifiably free.** The
      earlier read-prior-bytes/restore-prior-bytes design could not say that: it
      overwrote a live marker and then put the old bytes back, which the
      session leak guard could not see precisely because the restore was
      ``st_*time_ns``-exact. That precision made the clobber invisible, not
      safe.
    * **Teardown only removes what this object wrote.** If a concurrent session
      overwrote the marker during the window, the bytes no longer match and the
      file is left in place rather than unlinked — deleting their in-flight
      marker would be the same defect in the other direction. The session leak
      guard in ``tests/conftest.py`` then reports the change, which is a true
      finding about the host, not a false alarm to suppress.

    No opt-in env flag gates this. A flag defaulting to off would mean the test
    silently does not run in CI, which is precisely the "probe that cannot fail"
    shape this changeset exists to remove.

    Args:
        payload: Marker contents to write.
        path: Override for the watched path. EXISTS ONLY so this class's own
            refusal arm can be observed without touching the real global path;
            production use (the single negative-control test below) passes
            nothing and gets ``DEFAULT_CONTEXT_PATH``.
    """

    def __init__(self, payload: dict, *, path: "Path | str | None" = None) -> None:
        self.path = Path(path) if path is not None else Path(DEFAULT_CONTEXT_PATH)
        self.payload = payload
        self._planted_bytes: "bytes | None" = None

    def __enter__(self) -> Path:
        data = json.dumps(self.payload).encode("utf-8")
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pytest.skip(
                f"Refusing to plant the real gh-issue sanctioning marker: {self.path} "
                "already exists. Another session (a concurrent /create-issue, or a "
                "leftover from /triage) owns it, and overwriting would destroy its "
                "state and extend its 1-hour sanctioning TTL. Re-run when the path "
                "is free."
            )
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        self._planted_bytes = data
        return self.path

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._planted_bytes is None:
            return  # Never planted — nothing of ours to remove.
        try:
            current = self.path.read_bytes()
        except OSError:
            return  # Already gone; nothing to undo.
        if current == self._planted_bytes:
            self.path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 1. Headline reproducer — the ordering dependence
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_regression_issue_1609_ordering_dependence_is_gone():
    """The leaking module and the block tests must coexist in ONE session.

    This is the headline reproducer. Before the fix this child session reported
    49 failures inside ``test_gh_issue_create_block.py`` — every one of them
    ``assert None is not None`` — purely because the earlier module had written
    the global marker. It asserts the BEHAVIOUR (the block tests pass), not the
    existence of any fixture.
    """
    result = _run_child_pytest([LEAKING_TESTS, BLOCK_TESTS])

    assert result.returncode == 0, (
        "Running the known leaking module before the block tests must not change "
        "the block tests' verdict.\n"
        f"--- stdout ---\n{result.stdout[-6000:]}\n"
        f"--- stderr ---\n{result.stderr[-2000:]}"
    )
    assert " passed" in result.stdout, result.stdout[-3000:]


@pytest.mark.slow
def test_regression_issue_1609_leaking_module_leaves_real_marker_untouched():
    """The known offender must not create the real global marker.

    Directly reproduces the second measurement in the issue: running
    ``test_daily_aggregate_manager.py`` used to leave
    ``/tmp/autonomous_dev_cmd_context.json`` PRESENT.
    """
    before = snapshot_marker(DEFAULT_CONTEXT_PATH)
    result = _run_child_pytest([LEAKING_TESTS])
    after = snapshot_marker(DEFAULT_CONTEXT_PATH)

    assert result.returncode == 0, result.stdout[-3000:]
    assert describe_marker_leak(before, after, DEFAULT_CONTEXT_PATH) is None, (
        "The known offender still reaches the real marker path."
    )


# ---------------------------------------------------------------------------
# 2. Negative control — isolation run, with the real marker deliberately present
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_regression_issue_1609_block_tests_pass_with_real_marker_present():
    """The block tests must pass in isolation even when the real marker exists.

    Negative control for the fix: if they only passed because something scrubbed
    ``/tmp`` for them, the coupling would have moved rather than gone away. A
    hand-planted, perfectly valid sanctioning marker must have no effect,
    because no test consults that path any more.

    The plant is ``O_EXCL``: if a concurrent session already owns the real path
    this test SKIPS rather than overwriting it, and only ever removes bytes it
    wrote itself. See ``_RealMarkerPlanted`` for the full trade-off.
    """
    payload = {"command": "create-issue", "timestamp": "2026-08-22T00:00:00+00:00"}
    with _RealMarkerPlanted(payload):
        result = _run_child_pytest([BLOCK_TESTS])

    assert result.returncode == 0, (
        "The block tests still consult the real global marker.\n"
        f"--- stdout ---\n{result.stdout[-6000:]}"
    )


class TestRealMarkerPlantRefusesToClobber:
    """``_RealMarkerPlanted`` must never touch a marker it does not own (#1609).

    Every arm here runs against a temp path, deliberately: a test asserting that
    the plant REFUSES to overwrite the real global marker must not write the
    real global marker in order to find out — that would be the defect living
    inside its own control. The behaviour under test is the ``O_EXCL`` create
    and the ownership check on teardown, both of which are path-independent.
    """

    _PAYLOAD = {"command": "create-issue", "timestamp": "2026-08-22T00:00:00+00:00"}

    def test_refuses_and_leaves_a_pre_existing_marker_byte_identical(self, tmp_path):
        """REFUSE arm: the path is occupied -> skip, and touch nothing."""
        occupied = tmp_path / "autonomous_dev_cmd_context.json"
        foreign = json.dumps(
            {"command": "create-issue", "owner": "concurrent-session"}
        ).encode("utf-8")
        occupied.write_bytes(foreign)
        os.utime(occupied, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
        before = occupied.stat()

        with pytest.raises(pytest.skip.Exception) as excinfo:
            with _RealMarkerPlanted(self._PAYLOAD, path=occupied):
                pytest.fail(
                    "The plant opened a sanctioning window over a marker it does "
                    "not own — a concurrent session's state has been destroyed."
                )

        assert "already exists" in str(excinfo.value)
        after = occupied.stat()
        assert occupied.read_bytes() == foreign, "the foreign marker was rewritten"
        assert after.st_mtime_ns == before.st_mtime_ns, "mtime moved: the file was touched"
        assert after.st_size == before.st_size

    def test_plants_and_removes_its_own_marker_when_the_path_is_free(self, tmp_path):
        """PERMIT arm: the path is free -> plant, then remove exactly our bytes.

        Without this arm the refuse arm proves nothing: a plant that refused
        unconditionally would look identical, and the negative control above it
        would never run.
        """
        free = tmp_path / "autonomous_dev_cmd_context.json"

        with _RealMarkerPlanted(self._PAYLOAD, path=free) as planted:
            assert planted == free
            assert json.loads(free.read_text(encoding="utf-8")) == self._PAYLOAD

        assert not free.exists(), "teardown must remove the marker it planted"

    def test_leaves_a_marker_another_writer_replaced_during_the_window(self, tmp_path):
        """Teardown removes only OUR bytes, never a writer that arrived mid-window."""
        free = tmp_path / "autonomous_dev_cmd_context.json"
        foreign = json.dumps(
            {"command": "create-issue", "owner": "arrived-mid-window"}
        ).encode("utf-8")

        with _RealMarkerPlanted(self._PAYLOAD, path=free):
            free.write_bytes(foreign)  # stands in for a concurrent /create-issue

        assert free.exists(), "teardown deleted a concurrent session's in-flight marker"
        assert free.read_bytes() == foreign


# ---------------------------------------------------------------------------
# 3. Leak guard — both arms
# ---------------------------------------------------------------------------


class TestLeakGuardPureLogic:
    """``describe_marker_leak`` must refuse leaks and permit clean runs."""

    def test_permits_unchanged_absent(self):
        """Absent before, absent after — the ordinary clean run."""
        before = MarkerState(exists=False)
        after = MarkerState(exists=False)
        assert describe_marker_leak(before, after, DEFAULT_CONTEXT_PATH) is None

    def test_permits_unchanged_present(self):
        """A developer's marker left exactly as found is not a leak."""
        state = MarkerState(exists=True, mtime_ns=1_000, size=80)
        assert describe_marker_leak(state, state, DEFAULT_CONTEXT_PATH) is None

    def test_refuses_creation(self):
        """The Issue #1609 shape: the run created the marker."""
        finding = describe_marker_leak(
            MarkerState(exists=False),
            MarkerState(exists=True, mtime_ns=2_000, size=80),
            DEFAULT_CONTEXT_PATH,
        )
        assert finding is not None
        assert "CREATED" in finding
        assert DEFAULT_CONTEXT_PATH in finding

    def test_refuses_modification(self):
        """Rewriting an existing marker extends its 1-hour sanctioning TTL."""
        finding = describe_marker_leak(
            MarkerState(exists=True, mtime_ns=1_000, size=80),
            MarkerState(exists=True, mtime_ns=9_000, size=80),
            DEFAULT_CONTEXT_PATH,
        )
        assert finding is not None
        assert "MODIFIED" in finding

    def test_refuses_removal(self):
        """Deleting a concurrent session's marker is contamination too."""
        finding = describe_marker_leak(
            MarkerState(exists=True, mtime_ns=1_000, size=80),
            MarkerState(exists=False),
            DEFAULT_CONTEXT_PATH,
        )
        assert finding is not None
        assert "REMOVED" in finding

    def test_snapshot_reports_absent_for_missing_path(self, tmp_path):
        """Positive/negative control for the instrument itself."""
        missing = tmp_path / "nope.json"
        assert snapshot_marker(missing) == MarkerState(exists=False)

        present = tmp_path / "yes.json"
        present.write_text("{}", encoding="utf-8")
        observed = snapshot_marker(present)
        assert observed.exists is True
        assert observed.size == 2


@pytest.mark.slow
class TestLeakGuardEndToEnd:
    """The guard must fail a real pytest session that leaks, and only then."""

    _LEAKING_TEST = (
        "import json, os\n"
        "from pathlib import Path\n"
        "\n"
        "def test_reintroduced_leak():\n"
        "    watched = Path(os.environ['AUTONOMOUS_DEV_TEST_CTX_WATCH_PATH'])\n"
        "    watched.write_text(json.dumps({'command': 'create-issue'}))\n"
        "    assert watched.exists()\n"
    )

    _CLEAN_TEST = (
        "def test_touches_nothing():\n"
        "    assert True\n"
    )

    def _write_child_test(self, tmp_path: Path, body: str) -> Path:
        target = REPO_ROOT / "tests" / "regression" / f"test_tmp_1609_{tmp_path.name}.py"
        target.write_text(body, encoding="utf-8")
        return target

    def test_guard_refuses_reintroduced_leak(self, tmp_path):
        """REFUSE arm: a test that writes the watched marker fails the session.

        Deliberately a DIFFERENT shape from the reproducer — this writer is not
        ``daily_aggregate_manager`` and does not go through any accessor. The
        guard covers the class "any test that reaches the watched path", not the
        one module that prompted it.
        """
        watched = tmp_path / "watched_context.json"
        child_test = self._write_child_test(tmp_path, self._LEAKING_TEST)
        try:
            result = _run_child_pytest(
                [str(child_test.relative_to(REPO_ROOT))],
                env_extra={"AUTONOMOUS_DEV_TEST_CTX_WATCH_PATH": str(watched)},
            )
        finally:
            child_test.unlink(missing_ok=True)

        assert result.returncode != 0, (
            "The guard permitted a session that leaked the marker.\n"
            f"{result.stdout[-4000:]}"
        )
        assert "MARKER LEAK" in result.stdout, result.stdout[-4000:]
        assert "CREATED" in result.stdout, result.stdout[-4000:]

    def test_guard_permits_clean_run(self, tmp_path):
        """PERMIT arm: an identically-configured session that leaks nothing passes."""
        watched = tmp_path / "watched_context.json"
        child_test = self._write_child_test(tmp_path, self._CLEAN_TEST)
        try:
            result = _run_child_pytest(
                [str(child_test.relative_to(REPO_ROOT))],
                env_extra={"AUTONOMOUS_DEV_TEST_CTX_WATCH_PATH": str(watched)},
            )
        finally:
            child_test.unlink(missing_ok=True)

        assert result.returncode == 0, (
            "The guard refused a clean session — it cannot distinguish a leak.\n"
            f"{result.stdout[-4000:]}"
        )
        assert "MARKER LEAK" not in result.stdout


# ---------------------------------------------------------------------------
# 3b. The guard cannot be silently disabled by its own import failing
# ---------------------------------------------------------------------------

# Installed with `-p` so it runs before tests/conftest.py is imported, and makes
# exactly one thing fail: importing the leak guard helper. Toggled by an env var
# so both arms are byte-identical invocations with one variable changed.
_IMPORT_BLOCKER_PLUGIN = (
    "import os\n"
    "import sys\n"
    "\n"
    "_TARGET = 'tests.helpers.gh_issue_marker_guard'\n"
    "\n"
    "\n"
    "class _Blocker:\n"
    "    def find_spec(self, fullname, path=None, target=None):\n"
    "        if fullname == _TARGET and os.environ.get('BLOCK_1609_GUARD') == '1':\n"
    "            raise ModuleNotFoundError('simulated breakage: ' + fullname, name=fullname)\n"
    "        return None\n"
    "\n"
    "\n"
    "sys.meta_path.insert(0, _Blocker())\n"
)

_BLOCKER_PLUGIN_NAME = "blocker_1609"

# Any module that does NOT itself import the guard helper, so a failure can only
# be attributed to tests/conftest.py. --collect-only is enough: conftest is
# imported at collection time.
_NEUTRAL_TARGET = "tests/regression/smoke/test_import_smoke.py"


@pytest.mark.slow
class TestGuardImportCannotSilentlyDegrade:
    """A broken guard import must kill the run, not disable the guard (#1609).

    ``tests/conftest.py`` once wrapped the guard import in ``except ImportError``
    and set the watched path to ``None``, which made ``pytest_sessionfinish`` a
    no-op: the leak guard would be gone and every run would still report green.
    These two arms observe the real behaviour rather than reading the source.
    """

    def _plugin_dir(self, tmp_path: Path) -> str:
        (tmp_path / f"{_BLOCKER_PLUGIN_NAME}.py").write_text(
            _IMPORT_BLOCKER_PLUGIN, encoding="utf-8"
        )
        return str(tmp_path)

    def test_refuses_when_the_guard_helper_cannot_be_imported(self, tmp_path):
        """REFUSE arm: guard import broken -> the session fails loudly."""
        result = _run_child_pytest(
            ["--collect-only", "-p", _BLOCKER_PLUGIN_NAME, _NEUTRAL_TARGET],
            env_extra={
                "PYTHONPATH": self._plugin_dir(tmp_path),
                "BLOCK_1609_GUARD": "1",
            },
        )
        combined = result.stdout + result.stderr

        assert result.returncode != 0, (
            "tests/conftest.py swallowed the guard's ImportError: the leak guard "
            "is disabled and the run still reports success.\n"
            f"{combined[-4000:]}"
        )
        assert "gh_issue_marker_guard" in combined, combined[-4000:]
        assert "conftest.py" in combined, (
            "The failure must be attributed to conftest.py, not to a test module.\n"
            f"{combined[-4000:]}"
        )

    def test_permits_when_the_guard_helper_imports_normally(self, tmp_path):
        """PERMIT arm: same invocation, blocker inert -> the session succeeds.

        Without this arm the refuse arm proves nothing: a plugin that broke the
        run unconditionally would look identical.
        """
        result = _run_child_pytest(
            ["--collect-only", "-p", _BLOCKER_PLUGIN_NAME, _NEUTRAL_TARGET],
            env_extra={
                "PYTHONPATH": self._plugin_dir(tmp_path),
                "BLOCK_1609_GUARD": "0",
            },
        )
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            "The blocker plugin fails the run even when inert — the refuse arm "
            "above would then be measuring the plugin, not the guard.\n"
            f"{combined[-4000:]}"
        )
        assert "gh_issue_marker_guard" not in combined, combined[-4000:]


# ---------------------------------------------------------------------------
# 4. One resolved path, no repeated literal
# ---------------------------------------------------------------------------


def test_redirect_is_active_in_this_session():
    """Tests must never resolve to the real global path."""
    resolved = gh_issue_context_path()
    assert str(resolved) != DEFAULT_CONTEXT_PATH, (
        "tests/conftest.py did not install the marker redirect; the suite is "
        "reading and writing the real global sanctioning marker."
    )
    assert os.environ.get(CONTEXT_PATH_ENV_VAR), (
        f"{CONTEXT_PATH_ENV_VAR} must be set for the whole test session."
    )


def test_hook_and_lib_agree_on_marker_path():
    """Cross-validate the hook's copy against the lib constant.

    ``unified_pre_tool.py`` deliberately keeps its own copy (hooks run as
    standalone scripts with no ``lib`` on ``sys.path``). Both sources are read
    dynamically here rather than compared against a third copy in this test.
    """
    hook_source = HOOK_FILE.read_text(encoding="utf-8")
    assert f'"{CONTEXT_PATH_ENV_VAR}"' in hook_source, (
        f"{HOOK_FILE.name} must honour {CONTEXT_PATH_ENV_VAR}"
    )
    assert f'"{DEFAULT_CONTEXT_PATH}"' in hook_source, (
        f"{HOOK_FILE.name} default marker path drifted from "
        f"gh_issue_context.DEFAULT_CONTEXT_PATH"
    )


def test_no_production_writer_hardcodes_the_marker_path():
    """The literal may only appear where the env-var override also appears.

    This is the durable part: it catches offender number two — a future module
    that names the raw path directly and therefore cannot be redirected. The
    rule is a property (co-located with the override), not an allowlist of
    filenames.
    """
    scanned = sorted(
        [*LIB_DIR.glob("*.py"), *(REPO_ROOT / "plugins/autonomous-dev/hooks").glob("*.py")]
    )
    assert scanned, "path scan found no production files — the probe is broken"

    offenders = []
    for path in scanned:
        source = path.read_text(encoding="utf-8", errors="replace")
        if DEFAULT_CONTEXT_PATH in source and CONTEXT_PATH_ENV_VAR not in source:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert not offenders, (
        "These files hardcode the global marker path without honouring "
        f"${CONTEXT_PATH_ENV_VAR}, so they cannot be redirected:\n  "
        + "\n  ".join(offenders)
        + "\nResolve the path via gh_issue_context.gh_issue_context_path()."
    )


# ---------------------------------------------------------------------------
# 5. The sanctioning mechanism is still under test
# ---------------------------------------------------------------------------


class TestSanctioningStillWorks:
    """Isolating the path must not disable the thing it protects."""

    @staticmethod
    def _hook():
        sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"))
        import unified_pre_tool

        return unified_pre_tool

    def test_guard_permits_under_a_legitimate_marker(self, tmp_path, monkeypatch):
        """PERMIT arm: a valid context marker still allows gh issue create."""
        hook = self._hook()
        ctx = tmp_path / "ctx.json"
        ctx.write_text(
            json.dumps({"command": "create-issue", "timestamp": "now"}),
            encoding="utf-8",
        )
        monkeypatch.setattr(hook, "GH_ISSUE_COMMAND_CONTEXT_PATH", str(ctx))
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(hook, "_get_active_agent_name", lambda: "")

        assert hook._detect_gh_issue_create('gh issue create --title "x"') is None

    def test_guard_refuses_without_a_marker(self, tmp_path, monkeypatch):
        """REFUSE arm: the same command with no marker is blocked."""
        hook = self._hook()
        monkeypatch.setattr(
            hook, "GH_ISSUE_COMMAND_CONTEXT_PATH", str(tmp_path / "absent.json")
        )
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(hook, "_get_active_agent_name", lambda: "")
        monkeypatch.setattr(hook, "GH_ISSUE_MARKER_PATH", str(tmp_path / "absent.marker"))

        result = hook._detect_gh_issue_create('gh issue create --title "x"')
        assert result is not None
        assert "BLOCKED" in result

    def test_control_unrelated_command_is_allowed(self, tmp_path, monkeypatch):
        """CONTROL: the detector is not simply refusing everything."""
        hook = self._hook()
        monkeypatch.setattr(
            hook, "GH_ISSUE_COMMAND_CONTEXT_PATH", str(tmp_path / "absent.json")
        )
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(hook, "_get_active_agent_name", lambda: "")

        assert hook._detect_gh_issue_create("gh issue list") is None
        assert hook._detect_gh_issue_create("echo hello") is None

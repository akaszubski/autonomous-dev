"""Regression tests for Issue #1512 — non-atomic sentinel writes corrupt the file.

Observed live on 2026-08-16, ``.claude/local/active_agent_dispatch.json`` held::

    b'{"agent": "implementer", "pid": 92453, "timestamp": 1786833344.13824,
       "armed_at": 1786833338.3891358,
       "generation": "bcbe83aea30042a5aa7f30e68a499d47"}"}'

Valid JSON followed by a stray 2-byte ``"}`` tail — ``json.loads`` raises
``Extra data: line 1 column 152 (char 151)``.

Mechanism: ``write()`` and ``refresh()`` persisted state with
``Path.write_text``, which is truncate-then-write and therefore NOT atomic. Two
hook subprocesses (the main loop and a dispatched implementer, observed
interleaving tool calls in ``.claude/logs/activity/2026-08-16.jsonl``) each open
the file at offset 0; the shorter payload landing second leaves the tail of the
longer one behind.

Consequence: ``is_active()`` swallowed the ``JSONDecodeError`` and returned
``False`` — making a CORRUPT sentinel indistinguishable from an ABSENT one. Every
subsequent protected-path edit by the still-running implementer was then denied
as a coordinator direct edit under the Issue #1296 gate, with no diagnostic
anywhere. Silent ``False`` is what made this take three dispatches to find.

Two fixes are asserted here:
    1. ``write()``/``refresh()`` swap atomically (temp file in the same
       directory + ``os.replace``), so a reader never observes a partial file.
    2. A corrupt sentinel still fails CLOSED (``is_active()`` returns ``False``)
       but emits a loud ``sys.stderr`` warning naming the path and the decode
       error, so CORRUPT is distinguishable from ABSENT.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SENTINEL_MODULE_PATH = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "agent_dispatch_sentinel.py"
)
SENTINEL_REL = ".claude/local/active_agent_dispatch.json"

# The exact stray tail observed on disk on 2026-08-16.
OBSERVED_CORRUPT_TAIL = b'"}'


def _load_sentinel_module(module_path: Path | None = None) -> ModuleType:
    """Import the sentinel module by file path.

    Loading by path (rather than by package name) lets the concurrency workers
    import the same module after a ``spawn`` start, and lets a caller point at a
    pre-fix copy of the module to prove these tests are genuinely RED.

    Args:
        module_path: Path to ``agent_dispatch_sentinel.py``. Defaults to the
            in-repo module under test.

    Returns:
        The freshly-executed module object.
    """
    path = module_path or SENTINEL_MODULE_PATH
    spec = importlib.util.spec_from_file_location("_ads_under_test", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ads() -> ModuleType:
    """The agent_dispatch_sentinel module under test."""
    return _load_sentinel_module()


def _sentinel_path(repo_root: Path) -> Path:
    return repo_root / SENTINEL_REL


# ---------------------------------------------------------------------------
# 1. Reproduce the real corruption (load-bearing test)
# ---------------------------------------------------------------------------


def test_corrupt_sentinel_is_reported_on_stderr_not_silently_inactive(
    ads: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A spliced sentinel must be REPORTED, not silently read as unauthorized.

    This is the load-bearing assertion. A version of this test that only checks
    ``is_active() is False`` passes against the pre-fix code too and proves
    nothing — silent ``False`` was the entire defect.
    """
    ads.write("implementer", repo_root=tmp_path, generation="bcbe83aea30042a5")
    p = _sentinel_path(tmp_path)

    # Reproduce the exact on-disk artifact: valid JSON + stray 2-byte tail.
    with p.open("ab") as fh:
        fh.write(OBSERVED_CORRUPT_TAIL)

    # Precondition: the file really is undecodable in the observed way.
    with pytest.raises(json.JSONDecodeError) as decode_exc:
        json.loads(p.read_bytes())
    assert "Extra data" in str(decode_exc.value)

    capsys.readouterr()  # discard anything emitted during setup
    result = ads.is_active(repo_root=tmp_path)
    captured = capsys.readouterr()

    # Fails CLOSED — a truncated sentinel must never grant protected-path access.
    assert result is False, "corrupt sentinel must fail closed"

    # ...but LOUDLY. This is what distinguishes CORRUPT from ABSENT.
    assert captured.err.strip(), (
        "corrupt sentinel was swallowed silently — CORRUPT is indistinguishable "
        "from ABSENT, which is the Issue #1512 defect"
    )
    assert "agent_dispatch_sentinel" in captured.err
    assert "corrupt" in captured.err.lower()
    assert str(p) in captured.err, "warning must name the sentinel path"


def test_corrupt_sentinel_warning_names_the_decode_error(
    ads: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The warning must carry the decode error so the failure is diagnosable."""
    ads.write("implementer", repo_root=tmp_path, generation="gen-abc")
    p = _sentinel_path(tmp_path)
    with p.open("ab") as fh:
        fh.write(OBSERVED_CORRUPT_TAIL)

    capsys.readouterr()
    ads.is_active(repo_root=tmp_path)
    err = capsys.readouterr().err

    assert "Extra data" in err, (
        f"warning must include the json decode error; got: {err!r}"
    )


# ---------------------------------------------------------------------------
# 2. Concurrency — a reader must never observe a partial file
# ---------------------------------------------------------------------------


def test_write_swaps_a_new_inode_rather_than_truncating_in_place(
    ads: ModuleType, tmp_path: Path
) -> None:
    """Deterministic atomicity proof — no race required.

    ``Path.write_text`` opens the EXISTING file with ``O_TRUNC`` and rewrites it
    in place, so the inode is unchanged and a concurrent reader can observe the
    intermediate state. An atomic swap writes a fresh temp file and
    ``os.replace()``s it over the target, so the target's inode changes on every
    write and readers only ever see a complete file.

    This assertion is deterministic — it cannot flake the way a timing race can,
    and it fails against the pre-fix module every single time.
    """
    ads.write("implementer", repo_root=tmp_path, generation="gen-1")
    p = _sentinel_path(tmp_path)
    first_inode = p.stat().st_ino

    ads.write("reviewer", repo_root=tmp_path, generation="gen-2")
    second_inode = p.stat().st_ino
    assert second_inode != first_inode, (
        "write() truncated the sentinel in place (inode unchanged) — that is "
        "truncate-then-write, which is not atomic"
    )

    ads.refresh(repo_root=tmp_path)
    third_inode = p.stat().st_ino
    assert third_inode != second_inode, (
        "refresh() truncated the sentinel in place (inode unchanged) — that is "
        "truncate-then-write, which is not atomic"
    )


# Spawned as a real subprocess: the failure is cross-process, and threads would
# not reproduce it. A ``multiprocessing`` target defined inside a pytest module
# cannot be pickled under the ``spawn`` start method, which silently kills the
# workers and turns this into a false GREEN — so the worker is an explicit
# program invoked via ``sys.executable``.
_WRITER_PROGRAM = """
import importlib.util, sys
from pathlib import Path

module_path, repo_root, iterations = sys.argv[1], sys.argv[2], int(sys.argv[3])
spec = importlib.util.spec_from_file_location("ads_worker", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

root = Path(repo_root)
# Alternating payload sizes widen the truncate-then-write window: a short
# payload landing on top of a long one leaves the long one's tail behind,
# which is exactly the corruption observed on disk.
long_name = "implementer-" + ("x" * 4000)
for i in range(iterations):
    if i % 2 == 0:
        module.write(long_name, repo_root=root, generation="g" * 512)
    else:
        module.write("cia", repo_root=root, generation="g")
    module.refresh(repo_root=root)
"""


def test_concurrent_writes_never_expose_a_partial_sentinel(tmp_path: Path) -> None:
    """Every observed read is either fully-valid JSON or the file is absent.

    Bounded by an iteration cap AND a wall-clock cap so it cannot hang. Worker
    exit codes and a minimum read count are asserted so that dead workers can
    never masquerade as a pass.
    """
    _sentinel_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    p = _sentinel_path(tmp_path)

    workers = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                _WRITER_PROGRAM,
                str(SENTINEL_MODULE_PATH),
                str(tmp_path),
                "400",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(4)
    ]

    bad_reads: list[bytes] = []
    good_reads = 0
    max_iterations = 200000
    deadline = time.time() + 60.0
    iterations = 0

    try:
        while iterations < max_iterations and time.time() < deadline:
            iterations += 1
            if all(w.poll() is not None for w in workers):
                break
            try:
                raw = p.read_bytes()
            except FileNotFoundError:
                # ABSENT is a legal observation (nothing armed yet).
                continue
            except OSError:
                continue
            try:
                parsed: Any = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                bad_reads.append(raw)
                continue
            if isinstance(parsed, dict):
                good_reads += 1
            else:
                bad_reads.append(raw)
    finally:
        for w in workers:
            try:
                w.wait(timeout=60)
            except subprocess.TimeoutExpired:
                w.kill()
                w.wait(timeout=10)

    # Guard against a false GREEN: workers must have actually run and succeeded.
    for i, w in enumerate(workers):
        stderr = w.stderr.read().decode() if w.stderr else ""
        assert w.returncode == 0, (
            f"writer worker {i} failed (rc={w.returncode}); this test would "
            f"otherwise pass without exercising anything.\nstderr:\n{stderr}"
        )
    assert good_reads >= 50, (
        f"reader only completed {good_reads} valid reads out of {iterations} "
        "iterations — the race was never actually exercised"
    )

    assert not bad_reads, (
        f"{len(bad_reads)} partial/corrupt read(s) observed out of "
        f"{good_reads + len(bad_reads)} reads — sentinel writes are not atomic. "
        f"First bad read ({len(bad_reads[0])} bytes): "
        f"{bad_reads[0][:120]!r}...{bad_reads[0][-40:]!r}"
    )


def test_atomic_write_leaves_no_temp_files_behind(
    ads: ModuleType, tmp_path: Path
) -> None:
    """The atomic swap must not litter the sentinel directory with temp files."""
    ads.write("implementer", repo_root=tmp_path, generation="gen-1")
    ads.refresh(repo_root=tmp_path)
    ads.write("reviewer", repo_root=tmp_path, generation="gen-2")

    sentinel_dir = _sentinel_path(tmp_path).parent
    leftovers = [
        f.name for f in sentinel_dir.iterdir() if f.name != "active_agent_dispatch.json"
    ]
    assert not leftovers, f"temp files left behind after atomic write: {leftovers}"


# ---------------------------------------------------------------------------
# 3-5. Negative controls — must stay green under BOTH old and new code
# ---------------------------------------------------------------------------


def test_absent_sentinel_is_inactive_and_emits_no_corruption_warning(
    ads: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ABSENT must stay quiet — this is what separates it from CORRUPT."""
    assert not _sentinel_path(tmp_path).exists()

    capsys.readouterr()
    result = ads.is_active(repo_root=tmp_path)
    captured = capsys.readouterr()

    assert result is False
    assert "corrupt" not in captured.err.lower(), (
        f"absent sentinel must not warn about corruption; got: {captured.err!r}"
    )


def test_valid_sentinel_is_active(ads: ModuleType, tmp_path: Path) -> None:
    """A freshly-written sentinel authorizes protected-path edits."""
    ads.write("implementer", repo_root=tmp_path, generation="gen-valid")

    p = _sentinel_path(tmp_path)
    payload = json.loads(p.read_text())
    assert payload["agent"] == "implementer"
    assert payload["generation"] == "gen-valid"
    assert ads.is_active(repo_root=tmp_path) is True


def test_ttl_backstop_still_reaps_a_stale_sentinel(
    ads: ModuleType, tmp_path: Path
) -> None:
    """A sentinel older than DEFAULT_TTL_SECONDS is not active.

    Aged by rewriting ``timestamp`` — never by sleeping.
    """
    ads.write("implementer", repo_root=tmp_path, generation="gen-stale")
    p = _sentinel_path(tmp_path)

    payload = json.loads(p.read_text())
    stale_ts = time.time() - (ads.DEFAULT_TTL_SECONDS + 60)
    payload["timestamp"] = stale_ts
    payload["armed_at"] = stale_ts
    p.write_text(json.dumps(payload))

    assert ads.is_active(repo_root=tmp_path) is False
    # is_active() opportunistically cleans up what it reaps.
    assert not p.exists(), "stale sentinel should have been unlinked"


def test_refresh_does_not_resurrect_a_stale_sentinel(
    ads: ModuleType, tmp_path: Path
) -> None:
    """refresh() must never slide a already-stale sentinel back into life."""
    ads.write("implementer", repo_root=tmp_path, generation="gen-stale-2")
    p = _sentinel_path(tmp_path)

    payload = json.loads(p.read_text())
    stale_ts = time.time() - (ads.DEFAULT_TTL_SECONDS + 60)
    payload["timestamp"] = stale_ts
    payload["armed_at"] = stale_ts
    p.write_text(json.dumps(payload))

    assert ads.refresh(repo_root=tmp_path) is False


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))

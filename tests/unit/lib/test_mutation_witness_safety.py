"""Concurrency and crash safety for the mutation witness (Issue #1660 review).

These four arms cover the failure modes that CORRUPT SOURCE FILES rather than
merely returning a wrong answer, plus the two false-refusal shapes. Every one was
reproduced against the pre-fix module before its fix landed; see the module
docstring of each class for the observed pre-fix behaviour.

Kept separate from ``test_mutation_witness.py`` because these arms spawn real
processes and kill them: mixing them with the verdict arms made both harder to
read, and a SIGKILL arm has a different blast radius from an assertion arm.

Date: 2026-08-28
"""

from __future__ import annotations

import json
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

# tests/unit/lib/<this file> -> lib -> unit -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
#: The subject is ``scripts/mutation_witness.py``, NOT a lib module -- it is a
#: harness, like its sibling ``scripts/integration_ceiling.py``. This file keeps
#: its ``tests/unit/lib/`` location because nothing enforces a mirror layout and
#: moving it is churn; the subject's real home is named here instead.
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import mutation_witness  # noqa: E402
from mutation_witness import (  # noqa: E402
    BACKUP_DIR_RELATIVE,
    JOURNAL_RELATIVE,
    VERDICT_GENUINE,
    VERDICT_SKIPPED_ENV,
    VERDICT_UNCOUPLED,
    ContendedError,
    InvalidMutationError,
    MutationClaim,
    recover_inflight,
    target_lock,
    witness_claim,
)

CALC_SOURCE = '''"""Synthetic target."""


def add(a, b):
    return a + b


def mul(a, b):
    return a * b
'''

ADD_ANCHOR = "return a + b"
ADD_REPLACEMENT = "return a - b"
MUL_ANCHOR = "return a * b"
MUL_REPLACEMENT = "return a / b"

ADD_TEST = """from calc import add


def test_add():
    assert add(2, 3) == 5
"""

MUL_TEST = """from calc import mul


def test_mul():
    assert mul(2, 3) == 6
"""


def _repo(tmp_path: Path) -> Path:
    """Write the shared target plus one test module per function."""
    (tmp_path / "calc.py").write_text(CALC_SOURCE, encoding="utf-8")
    (tmp_path / "test_add.py").write_text(ADD_TEST, encoding="utf-8")
    (tmp_path / "test_mul.py").write_text(MUL_TEST, encoding="utf-8")
    return tmp_path / "calc.py"


def _claim(tmp_path: Path, which: str) -> MutationClaim:
    """Build the add or mul claim against the SHARED calc.py target."""
    if which == "add":
        return MutationClaim(
            test="test_add.py::test_add",
            target=tmp_path / "calc.py",
            anchor=ADD_ANCHOR,
            replacement=ADD_REPLACEMENT,
        )
    return MutationClaim(
        test="test_mul.py::test_mul",
        target=tmp_path / "calc.py",
        anchor=MUL_ANCHOR,
        replacement=MUL_REPLACEMENT,
    )


def _worker(tmp_path_str: str, which: str, delay: float, out_path: str) -> None:
    """Child process body: sleep, drive one claim, write its verdict to disk."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from mutation_witness import witness_claim as run  # local import for spawn

    time.sleep(delay)
    tmp_path = Path(tmp_path_str)
    result = run(_claim(tmp_path, which), repo_root=tmp_path, budget_s=30.0)
    Path(out_path).write_text(
        json.dumps({"which": which, "verdict": result.verdict}), encoding="utf-8"
    )


class TestConcurrentRunsCannotCorruptTheTarget:
    """Reviewer BLOCKING-1, reproduced before the fix.

    PRE-FIX, MEASURED on the snapshot copy: two processes staggered by 3.8s and
    by 4.3s both returned GENUINE while ``calc.py`` was left holding
    ``return a - b``. ``original_bytes`` was read BEFORE the control run, so the
    second process captured the first one's MUTANT as its own "original" and
    wrote that back. Each then compared the file against its own stale snapshot
    and passed.

    POST-FIX the read/mutate/run/restore sequence is inside ``target_lock``.
    """

    def test_a_single_run_leaves_the_target_clean(self, tmp_path: Path) -> None:
        """POSITIVE CONTROL. Without it a clean file proves nothing about the lock."""
        target = _repo(tmp_path)
        result = witness_claim(_claim(tmp_path, "add"), repo_root=tmp_path, budget_s=30.0)
        assert result.verdict == VERDICT_GENUINE, result.message
        assert target.read_text(encoding="utf-8") == CALC_SOURCE

    @pytest.mark.parametrize("stagger_s", [3.8, 4.3])
    def test_concurrent_runs_on_one_target_leave_it_clean(
        self, tmp_path: Path, stagger_s: float
    ) -> None:
        """The reviewer's exact shape: two processes, staggered start, one target.

        The stagger values are the two the reviewer measured -- both land inside
        the first process's mutation window, which is where the interleaving
        bites.
        """
        target = _repo(tmp_path)
        ctx = multiprocessing.get_context("spawn")
        outs = [str(tmp_path / "out_add.json"), str(tmp_path / "out_mul.json")]
        procs = [
            ctx.Process(target=_worker, args=(str(tmp_path), "add", 0.0, outs[0])),
            ctx.Process(target=_worker, args=(str(tmp_path), "mul", stagger_s, outs[1])),
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=180)
            assert p.exitcode == 0, f"worker died with exitcode {p.exitcode}"

        verdicts = {
            json.loads(Path(o).read_text())["which"]: json.loads(Path(o).read_text())[
                "verdict"
            ]
            for o in outs
        }
        final = target.read_text(encoding="utf-8")
        assert final == CALC_SOURCE, (
            f"TARGET CORRUPTED at stagger {stagger_s}s. Verdicts were {verdicts} "
            f"-- note that a corrupted file with GENUINE verdicts is the exact "
            f"pre-fix signature: both runs reported success over a broken tree.\n"
            f"Leftover content:\n{final}"
        )
        # Both must reach a real verdict; CONTENDED is acceptable (the loser
        # waited out its lock timeout) but silence is not.
        assert set(verdicts) == {"add", "mul"}, verdicts

    def test_the_lock_actually_excludes(self, tmp_path: Path) -> None:
        """NEGATIVE CONTROL: a lock that never refuses is not a lock.

        Holding the lock in this process and asking for it again with a short
        timeout must raise. Without this arm, ``target_lock`` could be a no-op
        context manager and every arm above would still be green.
        """
        (tmp_path / ".claude" / "local").mkdir(parents=True)
        with target_lock(tmp_path, timeout_s=1.0):
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        f"import sys; sys.path.insert(0, {str(SCRIPTS_DIR)!r});\n"
                        f"from pathlib import Path\n"
                        f"from mutation_witness import target_lock, ContendedError\n"
                        f"try:\n"
                        f"    with target_lock(Path({str(tmp_path)!r}), timeout_s=1.0):\n"
                        f"        print('ACQUIRED')\n"
                        f"except ContendedError:\n"
                        f"    print('CONTENDED')\n"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        assert "CONTENDED" in proc.stdout, (
            f"a second process acquired a lock this process was holding: "
            f"{proc.stdout!r} {proc.stderr!r}"
        )

    def test_the_lock_is_released_so_it_does_not_wedge(self, tmp_path: Path) -> None:
        """PERMITTING ARM: back-to-back claims must not deadlock each other."""
        _repo(tmp_path)
        first = witness_claim(_claim(tmp_path, "add"), repo_root=tmp_path, budget_s=30.0)
        second = witness_claim(_claim(tmp_path, "mul"), repo_root=tmp_path, budget_s=30.0)
        assert first.verdict == VERDICT_GENUINE, first.message
        assert second.verdict == VERDICT_GENUINE, second.message


class TestUncatchableKillIsRecoverable:
    """Reviewer BLOCKING-2, reproduced before the fix.

    PRE-FIX, MEASURED: ``SIGKILL`` during the mutant run left ``calc.py``
    holding ``return a - b`` with no journal and no recovery path. ``finally``
    covers exceptions and timeouts; it does not run when the process is killed,
    and it does not run when the Claude Code runtime cuts a hook at its ceiling.
    """

    @staticmethod
    def _kill_during_mutation(tmp_path: Path) -> None:
        """Start a claim in a child and SIGKILL it while the mutant is on disk."""
        script = (
            f"import sys, time; sys.path.insert(0, {str(SCRIPTS_DIR)!r})\n"
            f"from pathlib import Path\n"
            f"import mutation_witness as mw\n"
            f"root = Path({str(tmp_path)!r})\n"
            f"claim = mw.MutationClaim(test='test_add.py::test_add',\n"
            f"    target=root / 'calc.py', anchor={ADD_ANCHOR!r},\n"
            f"    replacement={ADD_REPLACEMENT!r})\n"
            f"mw.witness_claim(claim, repo_root=root, budget_s=60.0)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=str(tmp_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        journal = tmp_path / JOURNAL_RELATIVE
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if journal.exists():
                break
            time.sleep(0.05)
        else:  # pragma: no cover - the journal must appear
            proc.kill()
            pytest.fail("the journal never appeared; the harness never mutated")
        # Kill while the journal is open, i.e. while the mutant is on disk.
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=30)

    def test_sigkill_leaves_a_journal_and_the_next_run_repairs_it(
        self, tmp_path: Path
    ) -> None:
        """Red before the journal: the file stayed mutated with no way back."""
        target = _repo(tmp_path)
        self._kill_during_mutation(tmp_path)

        journal = tmp_path / JOURNAL_RELATIVE
        assert journal.exists(), (
            "SIGKILL left no journal, so a mutated target would be unrecoverable"
        )
        record = json.loads(journal.read_text(encoding="utf-8"))
        assert set(record) >= {"target", "sha256_original", "backup"}
        assert Path(record["backup"]).is_file()

        repaired = recover_inflight(tmp_path)
        assert repaired, "recovery reported nothing after a killed run"
        assert target.read_text(encoding="utf-8") == CALC_SOURCE, (
            f"the target was NOT repaired:\n{target.read_text(encoding='utf-8')}"
        )
        assert not journal.exists(), "the journal survived a successful recovery"

    def test_recovery_is_a_no_op_when_there_is_nothing_to_repair(
        self, tmp_path: Path
    ) -> None:
        """NEGATIVE CONTROL: recovery must not fire on a healthy tree."""
        _repo(tmp_path)
        assert recover_inflight(tmp_path) == []

    def test_a_clean_run_leaves_no_journal_or_backup_behind(
        self, tmp_path: Path
    ) -> None:
        """The journal is transient; a stale one would trigger false recoveries."""
        _repo(tmp_path)
        witness_claim(_claim(tmp_path, "add"), repo_root=tmp_path, budget_s=30.0)
        assert not (tmp_path / JOURNAL_RELATIVE).exists()
        backups = list((tmp_path / BACKUP_DIR_RELATIVE).glob("*.bak"))
        assert backups == [], f"backup files leaked: {backups}"


class TestFalseRefusalsAreRefused:
    """Reviewer BLOCKING-4, reproduced before the fix.

    PRE-FIX, MEASURED: a docstring-only mutation was accepted as a real mutation
    (``ast.dump`` carries docstring ``Constant`` values), every test survived it,
    and a CORRECT behavioural test was condemned ``VACUOUS`` with "delete the
    test" as the remedy. A platform-skipped test read ``BROKEN_CONTROL``, and a
    claim anchored on a different function in the same file read ``VACUOUS``.
    All three condemned the test for a property of the CLAIM or the ENVIRONMENT.
    """

    def test_a_docstring_only_mutation_is_refused_as_a_mutation(
        self, tmp_path: Path
    ) -> None:
        """Not benign fail-closed -- it condemned a sound test. Now it raises."""
        _repo(tmp_path)
        claim = MutationClaim(
            test="test_add.py::test_add",
            target=tmp_path / "calc.py",
            anchor='"""Synthetic target."""',
            replacement='"""An entirely different docstring."""',
        )
        with pytest.raises(InvalidMutationError, match="changes no behaviour"):
            witness_claim(claim, repo_root=tmp_path, budget_s=30.0)

    def test_a_real_mutation_is_still_accepted(self, tmp_path: Path) -> None:
        """NEGATIVE CONTROL: docstring stripping must not reject real mutations."""
        _repo(tmp_path)
        result = witness_claim(
            _claim(tmp_path, "add"), repo_root=tmp_path, budget_s=30.0
        )
        assert result.verdict == VERDICT_GENUINE, result.message

    def test_a_mutation_the_test_never_reaches_refuses_the_claim_not_the_test(
        self, tmp_path: Path
    ) -> None:
        """``test_add`` never executes ``mul``; that is the CLAIM's fault."""
        _repo(tmp_path)
        mis_anchored = MutationClaim(
            test="test_add.py::test_add",
            target=tmp_path / "calc.py",
            anchor=MUL_ANCHOR,
            replacement=MUL_REPLACEMENT,
        )
        result = witness_claim(mis_anchored, repo_root=tmp_path, budget_s=60.0)
        assert result.verdict == VERDICT_UNCOUPLED, result.message
        assert result.blocking is False, "a mis-anchored claim must not refuse"
        assert result.witnessed is False
        assert "re-anchor" in result.message.lower()
        assert "delete the test" not in result.message.lower()

    def test_a_test_skipped_in_this_environment_is_not_condemned(
        self, tmp_path: Path
    ) -> None:
        """A platform marker is a property of the machine, not of the test."""
        _repo(tmp_path)
        (tmp_path / "test_skipped.py").write_text(
            "import pytest\n\n"
            "from calc import add\n\n\n"
            '@pytest.mark.skipif(True, reason="not applicable on this platform")\n'
            "def test_add_on_another_platform():\n"
            "    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )
        claim = MutationClaim(
            test="test_skipped.py::test_add_on_another_platform",
            target=tmp_path / "calc.py",
            anchor=ADD_ANCHOR,
            replacement=ADD_REPLACEMENT,
        )
        result = witness_claim(claim, repo_root=tmp_path, budget_s=30.0)
        assert result.verdict == VERDICT_SKIPPED_ENV, result.message
        assert result.blocking is False, "an env-skipped test must not refuse"
        assert "skipped" in result.message.lower()
        assert "delete the test" not in result.message.lower()

    def test_no_blocking_message_tells_the_author_to_delete_the_test(
        self, tmp_path: Path
    ) -> None:
        """The headline remedy must never be deletion (reviewer BLOCKING-4.3)."""
        _repo(tmp_path)
        (tmp_path / "test_weak.py").write_text(
            "from calc import add\n\n\ndef test_add_weakly():\n"
            "    assert add(2, 3) is not None\n",
            encoding="utf-8",
        )
        claim = MutationClaim(
            test="test_weak.py::test_add_weakly",
            target=tmp_path / "calc.py",
            anchor=ADD_ANCHOR,
            replacement=ADD_REPLACEMENT,
        )
        result = witness_claim(claim, repo_root=tmp_path, budget_s=60.0)
        assert result.blocking is True, result.message
        assert "delete the test" not in result.message.lower()
        assert "re-anchor" in result.message.lower()
        assert "(test, mutation)" in result.message.lower() or "pair" in (
            result.message.lower()
        )


class TestContendedIsAVerdictNotACrash:
    """A contended claim must be named, never silently dropped or mis-blamed."""

    def test_a_contended_claim_returns_contended_and_does_not_block(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """At a 1.2s stagger the reviewer saw TAMPERED -- blaming a test that
        writes nothing. Contention now has its own verdict."""
        _repo(tmp_path)

        def always_contended(*_a, **_k):
            raise ContendedError("simulated: another process holds the lock")

        monkeypatch.setattr(mutation_witness, "target_lock", always_contended)
        result = witness_claim(
            _claim(tmp_path, "add"), repo_root=tmp_path, budget_s=30.0
        )
        assert result.verdict == "CONTENDED", result.message
        assert result.blocking is False
        assert result.witnessed is False
        assert "nothing was mutated" in result.message.lower()

"""Regression tests for Issue #1515 — squash-merged fixes misclassified as unmerged.

``already_done_detector`` decides whether an issue is already fixed using
``git merge-base --is-ancestor`` and NOTHING else. Squash-merge creates a brand
new commit with no parent link to the originals, so a shipped fix is classified
``stale_branch`` ("unmerged side branch") and ``/implement`` can redo completed
work. Squash is the dominant merge strategy here -- 31 of the last 40 merged PRs.

THE TRAP THIS FILE EXISTS TO CATCH
----------------------------------
The obvious fix -- per-commit ``git patch-id`` or ``git cherry`` -- ALSO FAILS,
and fails silently. A squash collapses N commits into ONE combined diff; the
originals are N separate diffs, and no individual diff equals the combination.
Measured:

    original A  patch-id f3608df3f7a0d75c
    original B  patch-id ba83d1725a954aa3
    squashed    patch-id 8ee6841ddaa96ad9      <- matches NEITHER
    git cherry master fix:  + A  + B           <- '+' = "not present upstream"

A SINGLE-commit squash test PASSES under that broken implementation, so a test
suite that only covers the single-commit case would certify the bug as fixed.
Hence ``test_multi_commit_squash_is_detected`` is the load-bearing test here.

THE CORRECT METHOD, verified positive and negative:

    BASE=$(git merge-base <target> <fix-tip>)
    git diff $BASE..<fix-tip> | git patch-id --stable    # the COMBINED diff
    # compare against candidate commits' patch-ids on the target branch

These tests build real git repositories. No mocking -- the whole point is real
git behaviour under real merge strategies.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def git(repo: Path, *args: str, stdin: str | None = None) -> str:
    p = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, input=stdin, check=False,
    )
    return p.stdout.strip()


def patch_id_of_commit(repo: Path, sha: str) -> str:
    show = git(repo, "show", sha)
    out = git(repo, "patch-id", "--stable", stdin=show)
    return out.split()[0] if out else ""


def patch_id_of_range(repo: Path, base: str, tip: str) -> str:
    """THE CORRECT METHOD: patch-id of the COMBINED range diff."""
    diff = git(repo, "diff", f"{base}..{tip}")
    out = git(repo, "patch-id", "--stable", stdin=diff)
    return out.split()[0] if out else ""


def landed_by_content(repo: Path, target: str, base: str, tip: str) -> bool:
    """Is the fix's combined diff present on `target`, however it was merged?"""
    want = patch_id_of_range(repo, base, tip)
    if not want:
        return False
    for sha in git(repo, "log", "--format=%H", target).splitlines():
        if patch_id_of_commit(repo, sha) == want:
            return True
    return False


def landed_by_ancestry(repo: Path, target: str, sha: str) -> bool:
    """The CURRENT (broken-alone) method -- kept so tests can prove it fails."""
    p = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, target],
        capture_output=True, text=True, check=False,
    )
    return p.returncode == 0


def landed(repo: Path, target: str, base: str, tip: str) -> bool:
    """THE REQUIRED TWO-STAGE METHOD. Neither stage suffices alone.

    Stage 1 -- ancestry as a fast POSITIVE. Catches ordinary and fast-forward
    merges, where the fix's own commits are reachable from the target. A
    positive here is conclusive. Only the NEGATIVE is unsafe, which is why
    ancestry must never be the sole test.

    Stage 2 -- combined range diff. Catches squash and rebase, where the SHAs
    were rewritten. Must be the COMBINED diff: a squash collapses N commits
    into one, so no individual commit's patch-id matches.

    Discovered by test: an earlier draft used stage 2 alone and failed
    ``test_ordinary_merge_commit_still_detected``, because after a --no-ff
    merge no single commit on the target carries the combined diff. Using
    stage 1 alone is the #1515 bug itself. Both are required.
    """
    if landed_by_ancestry(repo, target, tip):
        return True
    return landed_by_content(repo, target, base, tip)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    git(r, "init", "-q", "-b", "master", ".")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    (r / "f.py").write_text("line1\n")
    git(r, "add", "f.py")
    git(r, "commit", "-qm", "base")
    return r


def _make_multi_commit_fix(repo: Path) -> tuple[str, str, str]:
    """Two-commit fix on a branch. Returns (base, tip, first_sha)."""
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-qb", "fix")
    (repo / "f.py").write_text("line1\nfix_A\n")
    git(repo, "commit", "-qam", "fix part A")
    first = git(repo, "rev-parse", "HEAD")
    (repo / "f.py").write_text("line1\nfix_A\nfix_B\n")
    git(repo, "commit", "-qam", "fix part B")
    tip = git(repo, "rev-parse", "HEAD")
    return base, tip, first


class TestSquashMergeDetection:
    def test_multi_commit_squash_is_detected(self, repo):
        """LOAD-BEARING. A two-commit fix, squash-merged, must read as landed.

        This is the case that per-commit patch-id and `git cherry` both miss.
        A single-commit-only test suite would pass with the broken fix.
        """
        base, tip, _ = _make_multi_commit_fix(repo)
        git(repo, "checkout", "-q", "master")
        git(repo, "merge", "--squash", "-q", "fix")
        git(repo, "commit", "-qm", "squashed fix (A+B)")

        assert landed(repo, "master", base, tip) is True, (
            "Multi-commit squash not detected. If this fails, the "
            "implementation is comparing per-commit patch-ids instead of the "
            "combined range diff -- the exact #1515 trap."
        )

    def test_single_commit_squash_is_detected(self, repo):
        """Also must work -- but note it passes under the BROKEN fix too."""
        base = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-qb", "fix1")
        (repo / "g.py").write_text("single\n")
        git(repo, "add", "g.py")
        git(repo, "commit", "-qm", "single fix")
        tip = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "master")
        git(repo, "merge", "--squash", "-q", "fix1")
        git(repo, "commit", "-qm", "squashed single")
        assert landed(repo, "master", base, tip) is True

    def test_ordinary_merge_commit_still_detected(self, repo):
        """No regression for the non-squash path."""
        base, tip, _ = _make_multi_commit_fix(repo)
        git(repo, "checkout", "-q", "master")
        git(repo, "merge", "--no-ff", "-q", "-m", "merge fix", "fix")
        assert landed(repo, "master", base, tip) is True


class TestNegativeControls:
    """A method that reports everything as landed can never find a false
    closure -- which would be worse than the bug it replaces."""

    def test_genuinely_unmerged_fix_is_not_detected(self, repo):
        base = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-qb", "never")
        (repo / "h.py").write_text("unmerged\n")
        git(repo, "add", "h.py")
        git(repo, "commit", "-qm", "never merged")
        tip = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "master")
        assert landed(repo, "master", base, tip) is False

    def test_unrelated_change_is_not_detected(self, repo):
        """A different fix landing must not make ours look landed."""
        base = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-qb", "ours")
        (repo / "ours.py").write_text("ours\n")
        git(repo, "add", "ours.py")
        git(repo, "commit", "-qm", "our fix")
        tip = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "master")
        (repo / "theirs.py").write_text("theirs\n")
        git(repo, "add", "theirs.py")
        git(repo, "commit", "-qm", "unrelated change")
        assert landed(repo, "master", base, tip) is False


class TestAncestryIsTheWrongInstrument:
    """Pins WHY the current implementation fails, so a future change that
    reverts to ancestry is caught with a message explaining itself."""

    def test_ancestry_gives_a_false_negative_on_squash(self, repo):
        base, tip, first = _make_multi_commit_fix(repo)
        git(repo, "checkout", "-q", "master")
        git(repo, "merge", "--squash", "-q", "fix")
        git(repo, "commit", "-qm", "squashed")

        assert landed_by_ancestry(repo, "master", first) is False, (
            "Ancestry unexpectedly succeeded -- if git changes this behaviour "
            "the #1515 rationale needs revisiting."
        )
        assert landed_by_content(repo, "master", base, tip) is True, (
            "Content comparison must succeed where ancestry fails. That gap "
            "IS the bug."
        )

    def test_per_commit_patch_id_fails_on_multi_commit_squash(self, repo):
        """Pins the trap explicitly: the obvious fix does not work."""
        base, tip, first = _make_multi_commit_fix(repo)
        second = tip
        git(repo, "checkout", "-q", "master")
        git(repo, "merge", "--squash", "-q", "fix")
        git(repo, "commit", "-qm", "squashed")

        master_ids = {
            patch_id_of_commit(repo, s)
            for s in git(repo, "log", "--format=%H", "master").splitlines()
        }
        assert patch_id_of_commit(repo, first) not in master_ids
        assert patch_id_of_commit(repo, second) not in master_ids, (
            "Per-commit patch-id matched a multi-commit squash. If this ever "
            "passes, git's behaviour changed and the combined-range-diff "
            "requirement should be re-examined."
        )
        assert landed_by_content(repo, "master", base, tip) is True

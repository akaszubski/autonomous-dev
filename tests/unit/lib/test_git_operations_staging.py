#!/usr/bin/env python3
"""Regression tests for Issue #1564: ``auto_commit_and_push`` swept the tree.

``auto_commit_and_push()`` called ``stage_all_changes()`` unconditionally, so
every caller that had already staged a deliberate set of files had that index
discarded and the entire working tree - untracked files included - swept into
the commit. It is reached through ``create_commit_with_agent_message()``, which
``/implement`` STEP 12.7 and STEP L4.7 declare mandatory, so the sanctioned
commit path was the one that could not commit a narrow change. Observed live:
9 files staged, 482 files committed.

The fix adds ``stage_all: bool = True``. The default preserves the
commit-everything semantics batch and worktree flows depend on; the caller that
pre-stages passes ``stage_all=False``.

Every test here drives the real function against a REAL git repository, using
the pattern from ``tests/regression/test_drain_commit_gate.py:587-612`` (Issue
#1064). "The caller's index is preserved" is a claim about a real git index - a
``subprocess.run`` mock cannot witness it.

Issue: #1564
"""

import inspect
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

sys.path.insert(0, str(LIB_DIR))

import git_operations  # noqa: E402
from auto_implement_git_integration import (  # noqa: E402
    create_commit_with_agent_message,
)
from git_operations import (  # noqa: E402
    GitOperations,
    auto_commit_and_push,
    auto_commit_and_push_worktree,
    count_committed_files,
    get_staged_files,
)


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _committed_files(repo: Path, ref: str = "HEAD") -> List[str]:
    """Paths touched by ``ref``, read back from the real commit object."""
    out = _git(repo, "show", "--pretty=format:", "--name-only", ref)
    return sorted(line.strip() for line in out.splitlines() if line.strip())


def _fresh_repo(repo: Path) -> Path:
    """Initialise an empty git repo at ``repo`` with deterministic identity."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    # The parsing tests depend on git escaping unusual paths, which is the
    # default. Pin it so a developer's global config cannot make them vacuous.
    _git(repo, "config", "core.quotePath", "true")
    return repo


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A real git repository with 10 tracked files and one seed commit."""
    repo = _fresh_repo(tmp_path / "repo")
    for index in range(10):
        (repo / f"tracked_{index}.txt").write_text(f"v1-{index}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "chore: seed")
    return repo


def _dirty_ten(repo: Path) -> None:
    """Modify all 10 tracked files without staging any of them."""
    for index in range(10):
        (repo / f"tracked_{index}.txt").write_text(f"v2-{index}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Scenario 1: the caller's index is what gets committed
# ---------------------------------------------------------------------------


def test_stage_all_false_commits_only_the_files_the_caller_staged(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """3 of 10 modified files staged -> the commit contains exactly those 3.

    Before the fix this commit contained all 10 modified files.
    """
    _dirty_ten(git_repo)
    staged = ["tracked_0.txt", "tracked_1.txt", "tracked_2.txt"]
    _git(git_repo, "add", *staged)
    monkeypatch.chdir(git_repo)

    result = auto_commit_and_push(
        "fix: commit only the staged subset",
        "master",
        push=False,
        stage_all=False,
    )

    assert result["success"] is True, f"commit failed: {result}"
    assert result["commit_sha"], "reported success with no SHA"
    assert _committed_files(git_repo) == sorted(staged), (
        "auto_commit_and_push committed files the caller did not stage"
    )

    # The other 7 modifications are still uncommitted work in the tree.
    still_dirty = _git(git_repo, "status", "--porcelain")
    for index in range(3, 10):
        assert f"tracked_{index}.txt" in still_dirty, (
            f"tracked_{index}.txt was swept into the commit"
        )


# ---------------------------------------------------------------------------
# Scenario 2: NEGATIVE CONTROL - batch/worktree commit-everything must not regress
# ---------------------------------------------------------------------------


def test_stage_all_true_still_sweeps_the_entire_working_tree(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default behaviour is unchanged: everything, untracked included.

    Batch mode depends on this. Changing the default would break it, so this
    test is the guard against "fixing" #1564 by flipping the default.
    """
    _dirty_ten(git_repo)
    (git_repo / "untracked_scratch.txt").write_text("scratch\n", encoding="utf-8")
    monkeypatch.chdir(git_repo)

    result = auto_commit_and_push("chore: sweep everything", "master", push=False)

    assert result["success"] is True, f"commit failed: {result}"
    expected = sorted(
        [f"tracked_{index}.txt" for index in range(10)] + ["untracked_scratch.txt"]
    )
    assert _committed_files(git_repo) == expected, (
        "commit-everything semantics regressed"
    )
    assert _git(git_repo, "status", "--porcelain").strip() == ""


# ---------------------------------------------------------------------------
# Scenario 3: untracked files stay out
# ---------------------------------------------------------------------------


def test_stage_all_false_leaves_untracked_files_out_of_the_commit(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Untracked scratch files must never be swept in by a narrow commit.

    This is the exact live failure: ``.agents/``, ``AGENTS.md`` and friends -
    untracked scratch predating the session - landed in a 9-file commit.
    """
    _dirty_ten(git_repo)
    for name in ("AGENTS.md", "scratch_notes.md", "proposal.md.proposal"):
        (git_repo / name).write_text("scratch\n", encoding="utf-8")
    (git_repo / "untracked_dir").mkdir()
    (git_repo / "untracked_dir" / "audit.md").write_text("audit\n", encoding="utf-8")

    _git(git_repo, "add", "tracked_0.txt", "tracked_1.txt")
    monkeypatch.chdir(git_repo)

    result = auto_commit_and_push(
        "fix: narrow change", "master", push=False, stage_all=False
    )

    assert result["success"] is True, f"commit failed: {result}"
    committed = _committed_files(git_repo)
    assert committed == ["tracked_0.txt", "tracked_1.txt"], committed
    for name in ("AGENTS.md", "scratch_notes.md", "proposal.md.proposal"):
        assert name not in committed, f"untracked {name} was committed"
        assert (git_repo / name).exists(), f"{name} vanished from the tree"
    assert "untracked_dir/audit.md" not in committed


# ---------------------------------------------------------------------------
# Scenario 4: the caller gets a count back
# ---------------------------------------------------------------------------


def test_result_reports_the_number_of_files_actually_committed(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``files_committed`` matches what the caller staged.

    A caller that staged 9 and got 482 had no signal short of running
    ``git show --stat`` afterwards - which is what made the bug silent.
    """
    _dirty_ten(git_repo)
    staged = ["tracked_3.txt", "tracked_4.txt", "tracked_5.txt", "tracked_6.txt"]
    _git(git_repo, "add", *staged)
    monkeypatch.chdir(git_repo)

    assert sorted(get_staged_files()) == sorted(staged)

    result = auto_commit_and_push(
        "fix: four files", "master", push=False, stage_all=False
    )

    assert result["files_committed"] == len(staged), (
        f"files_committed={result['files_committed']} but {len(staged)} were staged"
    )
    assert result["files_committed"] == len(_committed_files(git_repo))


def test_result_reports_the_swept_count_under_the_default(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under ``stage_all=True`` the count reports the sweep, not the intent.

    This is the signal that would have made the 9-staged/482-committed run
    obvious at the call site instead of after the fact.
    """
    _dirty_ten(git_repo)
    (git_repo / "untracked_scratch.txt").write_text("scratch\n", encoding="utf-8")
    _git(git_repo, "add", "tracked_0.txt")
    monkeypatch.chdir(git_repo)

    result = auto_commit_and_push("chore: sweep", "master", push=False)

    assert result["files_committed"] == 11, (
        f"expected the full sweep to be reported, got {result['files_committed']}"
    )


# ---------------------------------------------------------------------------
# Scenario 5: NEGATIVE CONTROLS - the empty cases still fail actionably
# ---------------------------------------------------------------------------


def test_clean_tree_still_reports_the_actionable_nothing_to_commit(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #1555's actionable failure must not regress.

    A genuinely clean tree produces no commit and an error naming the fix.
    """
    monkeypatch.chdir(git_repo)
    head_before = _git(git_repo, "rev-parse", "HEAD").strip()

    result = create_commit_with_agent_message(
        workflow_id="wf-1564-clean",
        request="Fix Issue #1564 staging sweep",
        branch="master",
        push=False,
        issue_number=1564,
    )

    assert result["success"] is False, f"expected failure, got: {result}"
    assert result["commit_sha"] == ""
    assert "nothing to commit" in result["error"].lower(), result["error"]
    assert "git add" in result["error"], result["error"]
    assert result["manual_instructions"], "no manual fallback offered"
    assert _git(git_repo, "rev-parse", "HEAD").strip() == head_before


def test_stage_all_false_with_an_empty_index_reports_an_actionable_error(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dirty tree with nothing staged is a caller error, not a sweep.

    ``stage_all=False`` must not silently fall back to staging everything, and
    the message must say why nothing was committed.
    """
    _dirty_ten(git_repo)
    (git_repo / "untracked_scratch.txt").write_text("scratch\n", encoding="utf-8")
    monkeypatch.chdir(git_repo)
    head_before = _git(git_repo, "rev-parse", "HEAD").strip()

    result = auto_commit_and_push(
        "fix: nothing staged", "master", push=False, stage_all=False
    )

    assert result["commit_sha"] == ""
    assert result["files_committed"] == 0
    assert "nothing to commit" in result["error"].lower(), result["error"]
    assert "staging area is empty" in result["error"], result["error"]
    assert _git(git_repo, "rev-parse", "HEAD").strip() == head_before
    assert "untracked_scratch.txt" in _git(git_repo, "status", "--porcelain")


# ---------------------------------------------------------------------------
# NEGATIVE CONTROLS of a different shape than "sweeps untracked files"
# ---------------------------------------------------------------------------


def test_staged_content_wins_over_a_later_unstaged_modification(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Different shape: staged-then-modified-again, not untracked.

    The index holds v2 while the worktree holds v3. ``stage_all=False`` must
    commit the index content (v2) and leave v3 uncommitted. A fix that merely
    filtered untracked files would still commit v3 here.
    """
    target = git_repo / "tracked_0.txt"
    target.write_text("v2-staged\n", encoding="utf-8")
    _git(git_repo, "add", "tracked_0.txt")
    target.write_text("v3-worktree\n", encoding="utf-8")
    monkeypatch.chdir(git_repo)

    result = auto_commit_and_push(
        "fix: commit the index, not the worktree",
        "master",
        push=False,
        stage_all=False,
    )

    assert result["success"] is True, f"commit failed: {result}"
    assert _committed_files(git_repo) == ["tracked_0.txt"]
    committed_blob = _git(git_repo, "show", "HEAD:tracked_0.txt")
    assert committed_blob == "v2-staged\n", (
        f"committed the worktree content instead of the index: {committed_blob!r}"
    )
    assert target.read_text(encoding="utf-8") == "v3-worktree\n"
    assert "tracked_0.txt" in _git(git_repo, "status", "--porcelain")


def test_a_staged_deletion_is_committed_as_a_deletion(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Different shape: a staged removal, not a staged addition.

    ``get_staged_files`` must recognise the ``D`` index status, otherwise a
    delete-only change reads as "nothing staged" and is silently dropped.
    """
    _git(git_repo, "rm", "-q", "tracked_9.txt")
    (git_repo / "tracked_8.txt").write_text("edited-but-unstaged\n", encoding="utf-8")
    monkeypatch.chdir(git_repo)

    assert get_staged_files() == ["tracked_9.txt"]

    result = auto_commit_and_push(
        "fix: drop tracked_9", "master", push=False, stage_all=False
    )

    assert result["success"] is True, f"commit failed: {result}"
    assert result["files_committed"] == 1
    assert _committed_files(git_repo) == ["tracked_9.txt"]
    tracked_at_head = _git(git_repo, "ls-tree", "--name-only", "HEAD").split()
    assert "tracked_9.txt" not in tracked_at_head, "deletion was not recorded"
    assert "tracked_8.txt" in _git(git_repo, "status", "--porcelain"), (
        "the unstaged edit was swept in"
    )


# ---------------------------------------------------------------------------
# AC-18: the two staging call sites do not share a call shape
# ---------------------------------------------------------------------------


def test_ac18_stage_all_changes_call_shape_differs_per_call_site(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Witness the boundary: which kwargs each path passes to the primitive.

    ``auto_commit_and_push_worktree`` passes ``cwd=`` and
    ``gitignore_aware=True``; ``auto_commit_and_push`` passes neither. Asserting
    only "it was called" would not distinguish the two paths, and the defect
    lives at exactly one of them.
    """
    calls: List[dict] = []

    def _capture(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return (True, "")

    monkeypatch.setattr(git_operations, "stage_all_changes", _capture)
    monkeypatch.chdir(git_repo)
    _dirty_ten(git_repo)

    auto_commit_and_push("chore: probe", "master", push=False)
    assert len(calls) == 1, f"expected exactly one staging call, got {calls}"
    assert calls[0]["args"] == (), (
        f"auto_commit_and_push must call stage_all_changes() with no positional "
        f"arguments, got {calls[0]['args']}"
    )
    assert calls[0]["kwargs"] == {}, (
        f"auto_commit_and_push must call stage_all_changes() with no kwargs, "
        f"got {calls[0]['kwargs']}"
    )

    calls.clear()
    auto_commit_and_push_worktree(
        "chore: probe worktree", "master", push=False, cwd=git_repo
    )
    assert len(calls) == 1, f"expected exactly one staging call, got {calls}"
    assert calls[0]["kwargs"] == {"cwd": git_repo, "gitignore_aware": True}, (
        f"auto_commit_and_push_worktree must keep passing cwd= and "
        f"gitignore_aware=True (Issue #325), got {calls[0]['kwargs']}"
    )


def test_ac18_stage_all_false_never_reaches_the_staging_primitive(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``stage_all=False`` must not call ``stage_all_changes`` at all."""
    calls: List[dict] = []

    def _capture(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return (True, "")

    monkeypatch.setattr(git_operations, "stage_all_changes", _capture)
    _dirty_ten(git_repo)
    _git(git_repo, "add", "tracked_0.txt")
    monkeypatch.chdir(git_repo)

    result = auto_commit_and_push(
        "fix: staged only", "master", push=False, stage_all=False
    )

    assert calls == [], f"stage_all_changes was called despite stage_all=False: {calls}"
    assert result["success"] is True, f"commit failed: {result}"
    assert _committed_files(git_repo) == ["tracked_0.txt"]


# ---------------------------------------------------------------------------
# Surface canary: the parameter is threaded through every wrapper
# ---------------------------------------------------------------------------


def test_stage_all_is_threaded_through_every_wrapper() -> None:
    """The class API and the pipeline helper must both express the fix.

    Issue #1225 mandate: verify the real surface rather than trusting a mock to
    absorb the new kwarg.
    """
    for func in (
        auto_commit_and_push,
        GitOperations.auto_commit_push,
        create_commit_with_agent_message,
    ):
        params = inspect.signature(func).parameters
        assert "stage_all" in params, f"{func.__qualname__} cannot express stage_all"
        assert params["stage_all"].default is True, (
            f"{func.__qualname__} must default stage_all to True - batch mode "
            f"depends on commit-everything semantics"
        )


def test_pipeline_commit_path_passes_stage_all_explicitly() -> None:
    """``create_commit_with_agent_message`` must not rely on the callee default.

    This is the 9-staged/482-committed call site; the choice is recorded at the
    call, not inherited.
    """
    source = (LIB_DIR / "auto_implement_git_integration.py").read_text(encoding="utf-8")
    assert "stage_all=stage_all" in source, (
        "auto_implement_git_integration.py must forward stage_all explicitly to "
        "auto_commit_and_push"
    )


def test_count_committed_files_counts_a_root_commit(tmp_path: Path) -> None:
    """The counter must work on a repo whose first commit is HEAD.

    ``git diff-tree`` reports nothing for a root commit unless ``--root`` is
    passed - measured, not assumed::

        diff-tree -r --no-commit-id --name-only HEAD          -> ''
        diff-tree -r --no-commit-id --name-only --root HEAD   -> 2 paths

    So the implementation may use diff-tree, but must pass ``--root``.
    """
    repo = _fresh_repo(tmp_path / "root-repo")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "nested").mkdir()
    (repo / "nested" / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "chore: root")

    assert count_committed_files(cwd=repo) == 2

    # Witness the flag actually doing the work: drop --root and git reports
    # nothing, which is what makes --root load-bearing rather than decorative.
    without_root = _git(repo, "diff-tree", "-r", "--no-commit-id", "--name-only", "HEAD")
    assert without_root.strip() == "", (
        "the --root rationale no longer holds; re-derive it before trusting "
        f"the docstring (got {without_root!r})"
    )


# ---------------------------------------------------------------------------
# FINDING-1: git-quoted paths must survive the porcelain round trip
#
# Negative control shape: these are NOT about untracked files or about the
# stage_all flag at all. They exercise the parser on paths git escapes. A fix
# that only filtered untracked files, or that flipped a default, changes
# nothing here - only decoding the porcelain correctly does.
# ---------------------------------------------------------------------------

# Each name is escaped by git under core.quotePath (the default). The value is
# the reason git quotes it, which is also the shape the old parser destroyed.
QUOTED_PATH_CASES = [
    pytest.param("café.txt", id="non_ascii_utf8"),
    pytest.param("naïve—dash.txt", id="non_ascii_multibyte"),
    pytest.param("back\\slash.txt", id="backslash"),
    pytest.param('we"ird.txt', id="double_quote"),
    pytest.param("tab\tinside.txt", id="control_char"),
]


@pytest.mark.parametrize("filename", QUOTED_PATH_CASES)
def test_get_staged_files_returns_paths_that_exist_on_disk(
    tmp_path: Path, filename: str
) -> None:
    """A staged path git escapes must come back usable, not escaped.

    The old parser did ``line[3:].strip().strip('"')``, which removes the
    delimiters but decodes nothing: ``"caf\\303\\251.txt"`` became the literal
    ``caf\\303\\251.txt``, a path that does not exist. The disk check is the
    assertion that matters - a string-equality check against an expected value
    could be satisfied by a second copy of the same bug.
    """
    repo = _fresh_repo(tmp_path / "quoted")
    (repo / filename).write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")

    # Confirm the fixture actually provokes git's quoting, otherwise this test
    # would pass vacuously on a git configured with core.quotePath=false.
    raw_porcelain = _git(repo, "status", "--porcelain")
    assert raw_porcelain.startswith('A  "'), (
        f"fixture no longer triggers git quoting: {raw_porcelain!r}"
    )

    staged = get_staged_files(cwd=repo)

    assert staged == [filename], f"expected [{filename!r}], got {staged!r}"
    assert (repo / staged[0]).exists(), (
        f"get_staged_files returned {staged[0]!r}, which does not exist on disk"
    )


def test_get_staged_files_preserves_significant_leading_and_trailing_spaces(
    tmp_path: Path,
) -> None:
    """``.strip()`` silently renamed files whose names begin or end with a space.

    Different shape again: nothing here is escaped-and-undecoded, the bytes were
    correct and the parser threw characters away.
    """
    repo = _fresh_repo(tmp_path / "spaces")
    filename = " leading and trailing .txt"
    (repo / filename).write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")

    staged = get_staged_files(cwd=repo)

    assert staged == [filename], f"expected {filename!r}, got {staged!r}"
    assert staged[0].startswith(" ") and staged[0].endswith(" .txt"), (
        f"leading/trailing whitespace was stripped: {staged[0]!r}"
    )
    assert (repo / staged[0]).exists()


def test_get_staged_files_reports_a_staged_rename_as_its_destination(
    tmp_path: Path,
) -> None:
    """A staged rename is one staged path (the destination), not two.

    Under ``-z`` git emits the source path as a SEPARATE record after the entry.
    A parser that does not consume it reports the source as a second staged
    path and, worse, misreads every following record. The quoted source name
    makes the two failure modes distinguishable: mis-consumption yields the
    source, mis-decoding yields an escaped string.
    """
    repo = _fresh_repo(tmp_path / "rename")
    (repo / "café.txt").write_text("x\n", encoding="utf-8")
    (repo / "plain.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "seed")

    _git(repo, "mv", "café.txt", "renamed.txt")
    # A second, later-sorting staged path: if the rename's source record is not
    # consumed, this entry is read out of alignment and goes missing.
    (repo / "plain.txt").write_text("edited\n", encoding="utf-8")
    _git(repo, "add", "plain.txt")

    staged = get_staged_files(cwd=repo)

    assert sorted(staged) == ["plain.txt", "renamed.txt"], (
        f"rename source record mishandled: {staged!r}"
    )
    assert "café.txt" not in staged, "reported the rename source as staged"


def _worktree_rename(repo: Path, source: str, destination: str) -> None:
    """Produce a porcelain `` R`` entry - "renamed in work tree", index clean.

    ``git mv`` renames in the INDEX (``R ``). Moving the file on disk and
    marking the destination intent-to-add leaves the index untouched, so git
    detects the rename on the work-tree side instead. Plain porcelain, no
    adversarial filename, no plumbing.
    """
    (repo / source).rename(repo / destination)
    _git(repo, "add", "-N", destination)


def test_get_staged_files_ignores_a_worktree_side_rename(tmp_path: Path) -> None:
    """`` R`` carries a source record too, and it must be consumed.

    A rename is emitted as ``R `` when it is staged and `` R`` when it is not,
    and BOTH forms emit the source path as a separate ``-z`` record. Consuming
    the source only for the index column left the `` R`` source to be parsed as
    an entry, whose first two characters were then read as status columns:
    ``file.txt`` became the phantom staged path ``e.txt``.

    The entry itself is correctly skipped either way - `` R`` has a space in
    the index column - so this is purely about record alignment.
    """
    repo = _fresh_repo(tmp_path / "worktree-rename")
    (repo / "file.txt").write_text("x\n", encoding="utf-8")
    (repo / "real_staged.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "seed")

    _worktree_rename(repo, "file.txt", "moved.txt")
    (repo / "real_staged.txt").write_text("edited\n", encoding="utf-8")
    _git(repo, "add", "real_staged.txt")

    porcelain = _git(repo, "status", "--porcelain")
    assert " R " in porcelain, f"fixture produced no worktree rename: {porcelain!r}"

    assert get_staged_files(cwd=repo) == ["real_staged.txt"], (
        "the worktree-rename source record was parsed as an entry"
    )


def test_get_staged_files_does_not_drop_a_real_entry_after_an_r_named_source(
    tmp_path: Path,
) -> None:
    """The serious half: an ``R``-initial source swallowed the NEXT record.

    When the unconsumed source record itself begins with ``R`` or ``C`` - and
    ``README.md``, ``CHANGELOG.md`` and ``Cargo.toml`` all do - the parser read
    that leading character as a rename status and consumed the following
    record as its source. A genuinely staged file therefore vanished silently,
    and ``stage_all=False`` would have committed without it.

    ``README.md`` is the reproducer precisely because nothing about it is
    adversarial; it is the most ordinary filename in the repository.
    """
    repo = _fresh_repo(tmp_path / "r-named-source")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    (repo / "real_staged.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "seed")

    # Destination sorts before the staged file, so the staged file is the very
    # next record - the one the mis-parse consumed.
    _worktree_rename(repo, "README.md", "moved_readme.md")
    (repo / "real_staged.txt").write_text("edited\n", encoding="utf-8")
    _git(repo, "add", "real_staged.txt")

    staged = get_staged_files(cwd=repo)

    assert "real_staged.txt" in staged, (
        f"a genuinely staged file was swallowed by the rename source: {staged!r}"
    )
    assert staged == ["real_staged.txt"], f"phantom path reported: {staged!r}"


def test_get_staged_files_still_pairs_an_index_rename_with_a_worktree_edit(
    tmp_path: Path,
) -> None:
    """Positive control: ``RM`` still consumes exactly one source record.

    Widening the guard to either column must not make it consume twice. ``RM``
    is a rename staged in the index that was then edited in the work tree - one
    entry, one source record - and the destination is still staged.
    """
    repo = _fresh_repo(tmp_path / "rm-entry")
    (repo / "src.txt").write_text("x\n", encoding="utf-8")
    (repo / "z_after.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "seed")

    _git(repo, "mv", "src.txt", "dst.txt")
    (repo / "dst.txt").write_text("edited after staging\n", encoding="utf-8")
    (repo / "z_after.txt").write_text("edited\n", encoding="utf-8")
    _git(repo, "add", "z_after.txt")

    porcelain = _git(repo, "status", "--porcelain")
    assert "RM " in porcelain, f"fixture produced no RM entry: {porcelain!r}"

    assert sorted(get_staged_files(cwd=repo)) == ["dst.txt", "z_after.txt"], (
        "RM consumed the wrong number of records"
    )


def test_get_staged_files_leaves_untracked_and_unstaged_paths_alone(
    tmp_path: Path,
) -> None:
    """Positive control: the widened guard must not fire on ordinary entries.

    ``??`` (untracked) and `` M`` (modified, unstaged) carry NO source record.
    A guard that consumed a record for them would drop whatever followed, so
    the staged file that sorts last is the witness.
    """
    repo = _fresh_repo(tmp_path / "no-source-record")
    (repo / "modified.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "seed")

    (repo / "Renamed_looking_untracked.md").write_text("x\n", encoding="utf-8")
    (repo / "modified.txt").write_text("edited\n", encoding="utf-8")
    (repo / "z_staged.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "z_staged.txt")

    porcelain = _git(repo, "status", "--porcelain")
    assert "?? " in porcelain and " M " in porcelain, porcelain

    assert get_staged_files(cwd=repo) == ["z_staged.txt"], (
        f"an entry with no source record consumed one anyway: {porcelain!r}"
    )


def test_get_staged_files_ignores_an_unmerged_path(tmp_path: Path) -> None:
    """FINDING-6: a conflicted path has no staged blob, so it is not staged.

    A modify/delete conflict produces porcelain ``UD``. The old parser saw a
    non-space index column and reported it, which would have let
    ``stage_all=False`` proceed into a commit git refuses.
    """
    repo = _fresh_repo(tmp_path / "conflict")
    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "base")
    _git(repo, "branch", "other")
    (repo / "f.txt").write_text("main\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "main edit")
    _git(repo, "checkout", "-q", "other")
    (repo / "f.txt").unlink()
    _git(repo, "add", "-A", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "delete f")
    _git(repo, "checkout", "-q", "-")

    merge = subprocess.run(
        ["git", "merge", "other"], cwd=str(repo), capture_output=True, text=True
    )
    assert merge.returncode != 0, "fixture did not produce a conflict"
    assert "UD" in _git(repo, "status", "--porcelain")

    assert get_staged_files(cwd=repo) == [], (
        "an unmerged path was reported as staged"
    )


def test_get_staged_files_still_reports_ordinary_paths(tmp_path: Path) -> None:
    """Positive control for the exclusions above.

    A guard that never permits the legitimate case is not a guard. Ordinary
    added, modified and deleted staged paths must still be reported, so the
    unmerged/rename skips cannot be over-broad.
    """
    repo = _fresh_repo(tmp_path / "ordinary")
    (repo / "kept.txt").write_text("a\n", encoding="utf-8")
    (repo / "removed.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "seed")

    (repo / "added.txt").write_text("new\n", encoding="utf-8")
    (repo / "kept.txt").write_text("modified\n", encoding="utf-8")
    _git(repo, "rm", "-q", "removed.txt")
    _git(repo, "add", "added.txt", "kept.txt")

    assert sorted(get_staged_files(cwd=repo)) == [
        "added.txt",
        "kept.txt",
        "removed.txt",
    ]


# ---------------------------------------------------------------------------
# FINDING-2: files_committed must not report 0 for a commit that exists
# ---------------------------------------------------------------------------


def test_count_committed_files_is_non_zero_for_a_merge_commit(tmp_path: Path) -> None:
    """A real two-parent merge must not count as 0 files.

    ``git show --name-only`` prints a COMBINED diff for a merge, which by
    design suppresses paths matching a parent - it returned 0 for a commit that
    exists, colliding with the documented "0 means no commit was created"
    sentinel. Asserting non-zero here is the whole point; the exact count is
    asserted too so a future change cannot satisfy this with a constant.
    """
    repo = _fresh_repo(tmp_path / "merge")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "base")
    _git(repo, "branch", "feature")
    (repo / "main_only.txt").write_text("m\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "main change")
    _git(repo, "checkout", "-q", "feature")
    (repo / "feature_only.txt").write_text("f\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "feature change")
    _git(repo, "checkout", "-q", "-")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature")

    parents = _git(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()
    assert len(parents) == 3, f"fixture did not produce a two-parent merge: {parents}"

    assert count_committed_files(cwd=repo) == 2, (
        "a merge commit that exists was counted as 0 files - the "
        "'0 means no commit' sentinel is lying"
    )

    # Witness the old implementation failing on this exact input, so the test
    # is provably tied to the defect and not to the fixture.
    combined = _git(repo, "show", "--pretty=format:", "--name-only", "HEAD")
    assert combined.strip() == "", (
        "git show no longer suppresses merge paths; re-derive FINDING-2"
    )


def test_count_committed_files_does_not_double_count_across_parents(
    tmp_path: Path,
) -> None:
    """``-m`` emits a path once per parent it differs from; dedupe or overcount.

    Different shape from "returns 0": this is the overshoot on the same code
    path. ``both.txt`` differs from BOTH parents, so a naive line count reports
    it twice and the caller sees more files than the commit contains.
    """
    repo = _fresh_repo(tmp_path / "dupes")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "base")
    _git(repo, "branch", "feature")
    (repo / "both.txt").write_text("from-main\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "main both")
    _git(repo, "checkout", "-q", "feature")
    (repo / "both.txt").write_text("from-feature\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "feature both")
    _git(repo, "checkout", "-q", "-")

    merge = subprocess.run(
        ["git", "merge", "--no-ff", "-m", "merge", "feature"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert merge.returncode != 0, "fixture did not produce an add/add conflict"
    (repo / "both.txt").write_text("resolved\n", encoding="utf-8")
    _git(repo, "add", "both.txt")
    _git(repo, "commit", "-q", "--no-verify", "--no-edit")

    raw = _git(
        repo, "diff-tree", "-r", "--no-commit-id", "--name-only", "--root", "-m",
        "HEAD", "--",
    )
    raw_lines = [line for line in raw.splitlines() if line.strip()]
    assert len(raw_lines) > len(set(raw_lines)), (
        f"fixture no longer produces cross-parent duplicates: {raw_lines}"
    )

    assert count_committed_files(cwd=repo) == len(set(raw_lines))


def test_count_committed_files_counts_quoted_and_spaced_paths(tmp_path: Path) -> None:
    """The counter must not miscount paths git would escape.

    Same quoting hazard as FINDING-1, on the other helper. A filename holding a
    newline is the case a line count cannot survive.
    """
    repo = _fresh_repo(tmp_path / "counted")
    for name in ("café.txt", "with space.txt", "line\nbreak.txt"):
        (repo / name).write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "--no-verify", "-m", "quoted paths")

    assert count_committed_files(cwd=repo) == 3


# ---------------------------------------------------------------------------
# FINDING-5: a caller-supplied ref must not be consumed as a flag
# ---------------------------------------------------------------------------


def test_count_committed_files_does_not_let_a_flag_shaped_ref_select_commits(
    git_repo: Path,
) -> None:
    """``count_committed_files('--all')`` must not report another commit's files.

    Under ``git show`` the flag-shaped ref was consumed as an option and the
    helper reported 2 files for a ref naming no commit.

    The trailing ``--`` is NOT what fixes this - measured, git parses options
    before ``--``, so a flag-shaped ref still reaches diff-tree as a flag. Most
    such flags happen to leave diff-tree with no tree-ish, so it exits 129 and
    the count degrades to 0 by accident. ``--branches`` and ``--glob=`` do NOT:
    git resolves them to real refs and diff-tree reports that commit's files,
    so the helper returns a positive count for a ref that names no commit -
    FINDING-5's exact failure mode. Only refusing the ref before it reaches
    argv fixes it, which is why those two carry this test.

    It raises rather than returning 0: 0 is this function's "no commit was
    created" sentinel, so answering a caller-side programming error with it
    would recreate the lying-zero ambiguity the function exists to remove.
    """
    for flag_shaped in (
        "--branches",
        "--glob=refs/heads/*",
        "--all",
        "--stat",
        "-m",
    ):
        with pytest.raises(ValueError, match="flag-shaped ref"):
            count_committed_files(flag_shaped, cwd=git_repo)


def test_count_committed_files_still_resolves_ordinary_refs(git_repo: Path) -> None:
    """Positive control: the ref argument must keep working.

    Rejecting every ref would satisfy the test above while breaking the API.
    """
    (git_repo / "tracked_0.txt").write_text("v2\n", encoding="utf-8")
    _git(git_repo, "add", "tracked_0.txt")
    _git(git_repo, "commit", "-q", "--no-verify", "-m", "second")

    head_sha = _git(git_repo, "rev-parse", "HEAD").strip()
    assert count_committed_files("HEAD", cwd=git_repo) == 1
    assert count_committed_files(head_sha, cwd=git_repo) == 1
    assert count_committed_files("HEAD~1", cwd=git_repo) == 10


def test_count_committed_files_returns_zero_for_a_nonexistent_ref(
    git_repo: Path,
) -> None:
    """An unresolvable ref is a failed query, which the contract maps to 0."""
    assert count_committed_files("no-such-ref-1564", cwd=git_repo) == 0


# ---------------------------------------------------------------------------
# FINDING-4: files_committed is documented unconditionally, so it must be there
# ---------------------------------------------------------------------------


def test_files_committed_is_present_on_every_failure_path(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The key is documented without qualification; absent on failure it KeyErrors.

    ``auto_commit_and_push`` seeds it; ``create_commit_with_agent_message``
    returned three failure dicts without it.
    """
    monkeypatch.chdir(git_repo)

    # Failure path 1: nothing to commit (git_succeeded False, empty SHA).
    clean = create_commit_with_agent_message(
        workflow_id="wf-1564-f4-clean",
        request="Fix Issue #1564 staging sweep",
        branch="master",
        push=False,
    )
    assert clean["success"] is False
    assert clean["files_committed"] == 0

    # Failure path 2: message generation fails before git runs at all.
    import auto_implement_git_integration as agi

    monkeypatch.setattr(
        agi,
        "invoke_commit_message_agent",
        lambda **kwargs: {"success": False, "output": "", "error": "agent failed"},
    )
    agent_failed = create_commit_with_agent_message(
        workflow_id="wf-1564-f4-agent",
        request="Fix Issue #1564 staging sweep",
        branch="master",
        push=False,
    )
    assert agent_failed["success"] is False
    assert agent_failed["agent_succeeded"] is False
    assert agent_failed["files_committed"] == 0


def test_files_committed_is_non_zero_on_the_success_path(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive control for the seeding above.

    Seeding every dict with 0 unconditionally would satisfy the failure-path
    test while destroying the signal. The success path must still report the
    real count.
    """
    _dirty_ten(git_repo)
    monkeypatch.chdir(git_repo)

    result = create_commit_with_agent_message(
        workflow_id="wf-1564-f4-success",
        request="Fix Issue #1564 staging sweep",
        branch="master",
        push=False,
    )

    assert result["success"] is True, f"commit failed: {result}"
    assert result["files_committed"] == 10, result


# ---------------------------------------------------------------------------
# FINDING-7: stage_all=False is documented as usable - say who can use it
# ---------------------------------------------------------------------------


def test_stage_all_false_precondition_is_documented_at_both_entry_points() -> None:
    """The parameter is public; its precondition must travel with it.

    ``/implement`` cannot pass ``stage_all=False`` today, and BOTH branches
    have to be documented because they fail differently. The index is empty by
    construction only when doc-master made no fixes. When it did, its
    ``git add`` at ``commands/implement.md`` STEP 12 runs BEFORE the STEP 12.7
    commit, so the index holds exactly the doc files and ``stage_all=False``
    would commit those and silently drop the implementation.

    A docstring that predicts only the loud failure is worse than none: it
    tells a reader the dangerous branch cannot happen.
    """
    for func in (auto_commit_and_push, create_commit_with_agent_message):
        doc = inspect.getdoc(func) or ""
        assert "Precondition:" in doc, (
            f"{func.__qualname__} documents stage_all without its precondition"
        )
        assert "stage_all=False" in doc, func.__qualname__
        assert "/implement" in doc, (
            f"{func.__qualname__} must name the caller that cannot yet satisfy "
            f"the precondition"
        )
        assert "doc-master" in doc, (
            f"{func.__qualname__} must name doc-master: its STEP 12 `git add` "
            f"is what makes the index non-empty at STEP 12.7"
        )
        assert "SILENTLY DROP" in doc, (
            f"{func.__qualname__} documents only the loud empty-index failure. "
            f"The doc-master-only index is the dangerous branch and must be "
            f"stated as a silent partial commit"
        )


def test_docmaster_git_add_really_precedes_the_step_12_7_commit() -> None:
    """Ground the Precondition docstrings in the file they describe.

    The docstrings above are a claim about ordering inside
    ``commands/implement.md``. If STEP 12.7 ever moves above doc-master's
    fix-collection ``git add``, the documented hazard stops being real and the
    docstrings become misinformation. Assert the ordering, so the claim cannot
    rot silently.
    """
    implement_md = (
        REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
    ).read_text(encoding="utf-8")

    doc_add = implement_md.find("If doc-master made fixes: stage them with `git add`")
    step_12_7 = implement_md.find("### STEP 12.7:")

    assert doc_add != -1, "doc-master's fix-staging step is no longer in implement.md"
    assert step_12_7 != -1, "STEP 12.7 is no longer in implement.md"
    assert doc_add < step_12_7, (
        "STEP 12.7 now precedes doc-master's `git add`. The Precondition "
        "docstrings on auto_commit_and_push and create_commit_with_agent_message "
        "describe a doc-master-only index at commit time - update them."
    )


def test_implement_pipeline_does_not_yet_pass_stage_all_false() -> None:
    """Lock the documented state: STEP 12.7 still uses the sweeping default.

    If someone wires ``stage_all=False`` into the pipeline without adding a
    staging step, the mandatory commit starts failing. This fails first, and
    points at the docstring that explains what else has to land.
    """
    implement_md = (
        REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
    ).read_text(encoding="utf-8")

    assert "stage_all=False" not in implement_md, (
        "implement.md now passes stage_all=False. The pipeline must first gain "
        "an explicit staging step and reconcile STEP 1's empty-index gate - see "
        "the Precondition in auto_commit_and_push's docstring."
    )

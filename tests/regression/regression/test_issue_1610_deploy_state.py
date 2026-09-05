"""Regression tests for Issue #1610 — deploy-all.sh shipped the working tree.

WHAT WENT WRONG
---------------
``scripts/deploy-all.sh`` rsyncs from ``plugins/autonomous-dev/`` — the WORKING
TREE — not from ``HEAD``. Uncommitted work-in-progress therefore reached the
executing hook stack the moment anyone deployed, bypassing the reviewer, the
security auditor, doc-master and the commit gate simultaneously.

The measured instance: ``lib/hook_safety.py`` executing at 684 lines, an
intermediate state present in NO commit — between HEAD's 347 and the staged
892. ``git`` could not revert it because it corresponded to no object. Partial
deployment produced something strictly worse than either endpoint: it carried
the silent fail-open defect and none of the fixes.

WHAT WENT WRONG WITH THE FIRST FIX
----------------------------------
The first version of the guard reported "clean" in six situations where it
could not tell, or where the answer was "not clean". Every one was the same
shape — a derivation that fails open — so the tests below are organised around
that shape rather than around the six instances:

  BLOCKING 1  ``git status`` omits gitignored paths; ``rsync -a`` ships them.
              46 such files were already executing in a consumer repo.
  BLOCKING 2  ``--source`` not being the git toplevel discarded every entry and
              returned ``[]``, read as clean.
  BLOCKING 3  ``stamp`` dropped uncommitted entries it could not name-match
              (C-quoted unicode, directory entries) and recorded dirty: false.
  BLOCKING 4  ``check`` iterated the record only, so a file ADDED to the
              executing tree was invisible; symlinks were never recorded.
  BLOCKING 5  ``check`` reported OK on a record whose digest map was empty.
  BLOCKING 6  the script went into the manifest neither installer reads, and
              the test asserted the same wrong path.

WHAT THESE TESTS LOCK
---------------------
Both arms of every guard, per the project's rule (a guard watched only refusing
is unproven, and here the PERMITTING arm matters most — breaking the
hook-iteration loop would make people stop using the script).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_SRC = REPO_ROOT / "plugins" / "autonomous-dev"
DEPLOY_STATE_SRC = PLUGIN_SRC / "scripts" / "deploy_state.py"
DEPLOY_ALL_SH = REPO_ROOT / "scripts" / "deploy-all.sh"
DEPLOY_LOCAL_SH = REPO_ROOT / "scripts" / "deploy_local.sh"
PRUNE_SYNC_SH = REPO_ROOT / "scripts" / "lib" / "prune_sync.sh"
# deploy-all.sh inlines prune_sync.sh into its ssh heredoc via command
# substitution, so the two files are ONE transport: the destructive rsync for
# the remote sites is textually in the library, not in deploy-all.sh.
DEPLOY_ALL_TRANSPORT = (DEPLOY_ALL_SH, PRUNE_SYNC_SH)
SHELL_FILES = (DEPLOY_ALL_SH, DEPLOY_LOCAL_SH, PRUNE_SYNC_SH)
# An rsync whose output is captured into a variable is still an rsync
# invocation. prune_sync()'s deletion PREVIEW is written `preview=$(rsync ...)`,
# and a matcher anchored on a bare `rsync ` walks straight past it — which
# would leave the one invocation that decides whether anything gets deleted
# outside every enumeration in this file.
COPY_INVOCATION_RE = r"^(?:[A-Za-z_][A-Za-z0-9_]*=\$\()?(?:rsync|cp)\s"
HEALTH_CHECK_MD = PLUGIN_SRC / "commands" / "health-check.md"
INSTALL_PY = PLUGIN_SRC / "scripts" / "install.py"
INSTALL_SH = REPO_ROOT / "install.sh"

sys.path.insert(0, str(PLUGIN_SRC / "scripts"))

import deploy_state  # noqa: E402  (path set above)


# --------------------------------------------------------------------------
# Fixtures: a throwaway source repo + a throwaway "executing" consumer tree.
# Nothing here touches the real repo, ~/.claude, $HOME/Dev, or the remote.
# --------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _make_source_repo(tmp_path: Path, name: str = "src") -> Path:
    """Build a minimal autonomous-dev-shaped git repo with a committed plugin."""
    src = tmp_path / name
    (src / "plugins" / "autonomous-dev" / "hooks").mkdir(parents=True)
    (src / "plugins" / "autonomous-dev" / "lib").mkdir(parents=True)
    (src / "plugins" / "autonomous-dev" / "scripts").mkdir(parents=True)
    (src / "scripts").mkdir(parents=True)

    plugin = src / "plugins" / "autonomous-dev"
    (plugin / "hooks" / "unified_pre_tool.py").write_text("# committed hook\n")
    (plugin / "lib" / "hook_safety.py").write_text("# committed: 347-line shape\n")
    shutil.copy2(DEPLOY_STATE_SRC, plugin / "scripts" / "deploy_state.py")
    shutil.copy2(DEPLOY_ALL_SH, src / "scripts" / "deploy-all.sh")
    shutil.copy2(DEPLOY_LOCAL_SH, src / "scripts" / "deploy_local.sh")
    # deploy-all.sh inlines this into its ssh heredoc via
    # $(cat "$SCRIPT_DIR/lib/prune_sync.sh"), so the fixture is not a faithful
    # copy of the transport without it: the generated remote script would
    # silently lose prune_sync() and every remote assertion would go vacuous.
    (src / "scripts" / "lib").mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRUNE_SYNC_SH, src / "scripts" / "lib" / "prune_sync.sh")
    # The same ignore classes the real repo carries, so "gitignored but shipped"
    # is reproducible rather than hypothetical.
    (src / ".gitignore").write_text("*.junkext\n*,cover\n.DS_Store\n__pycache__/\n")

    _git(src, "init", "-q")
    _git(src, "config", "user.email", "t@example.com")
    _git(src, "config", "user.name", "t")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "initial")
    return src


def _fake_deploy(plugin: Path, target: Path) -> None:
    """Simulate deploy-all.sh's copy step: rsync -a with $DEPLOY_EXCLUDES.

    Copies exactly ``source_deployed_files()`` — the same set the gate measures
    — so the fixture cannot disagree with the thing under test about what
    "deployed" means.
    """
    for rel in sorted(deploy_state.source_deployed_files(plugin)):
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        src_path = plugin / rel
        if src_path.is_symlink():
            if dest.is_symlink() or dest.exists():
                dest.unlink()
            os.symlink(os.readlink(src_path), dest)
        else:
            shutil.copy2(src_path, dest)


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    return _make_source_repo(tmp_path)


@pytest.fixture
def consumer(tmp_path: Path) -> Path:
    """A consumer repo root whose .claude/ is the EXECUTING tree."""
    root = tmp_path / "consumer"
    (root / ".claude").mkdir(parents=True)
    return root


def _gate(source_repo: Path, *extra: str) -> int:
    return deploy_state.main(
        [
            "gate",
            "--source",
            str(source_repo),
            "--plugin-src",
            str(source_repo / "plugins" / "autonomous-dev"),
            *extra,
        ]
    )


def _stamp(source_repo: Path, consumer: Path, *, dirty: bool = False) -> int:
    argv = [
        "stamp",
        "--source",
        str(source_repo),
        "--plugin-src",
        str(source_repo / "plugins" / "autonomous-dev"),
        "--target",
        str(consumer / ".claude"),
    ]
    if dirty:
        argv.append("--dirty")
    return deploy_state.main(argv)


def _check(consumer: Path, capsys) -> tuple[int, str]:
    code = deploy_state.main(["check", "--repo", str(consumer)])
    return code, capsys.readouterr().out


def _read_state(consumer: Path) -> dict:
    return json.loads((consumer / ".claude" / ".deploy-state.json").read_text())


def _write_state(consumer: Path, payload) -> None:
    (consumer / ".claude" / ".deploy-state.json").write_text(json.dumps(payload))


# --------------------------------------------------------------------------
# 1. The REFUSING arm
# --------------------------------------------------------------------------


def test_gate_refuses_dirty_tree_and_names_the_modified_file(source_repo: Path, capsys):
    """A modified tracked file under a deployed subdir is refused BY NAME."""
    (source_repo / "plugins" / "autonomous-dev" / "lib" / "hook_safety.py").write_text(
        "# 684-line intermediate state that exists in no commit\n"
    )

    code = _gate(source_repo)
    captured = capsys.readouterr()
    out = captured.out + captured.err  # refusals belong on stderr

    assert code == 1, "dirty tree without --dirty MUST be refused"
    assert "lib/hook_safety.py" in out, f"refusal must NAME the file; got:\n{out}"
    assert "--dirty" in out, "refusal must state the escape hatch (REQUIRED NEXT ACTION)"


def test_gate_refuses_untracked_file_a_different_shape(source_repo: Path, capsys):
    """Negative control of a DIFFERENT shape than the reproducer.

    The #1610 reproducer was a MODIFIED tracked file. An untracked NEW file
    under a deployed subdir is equally never-committed and equally deployed by
    ``rsync -a`` — a guard that only saw modified files would be scoped to the
    instance that prompted it.
    """
    (source_repo / "plugins" / "autonomous-dev" / "hooks" / "brand_new_hook.py").write_text(
        "# never added to git, but rsync -a ships it\n"
    )

    code = _gate(source_repo)
    captured = capsys.readouterr()
    out = captured.out + captured.err

    assert code == 1, "untracked file under a deployed subdir MUST be refused"
    assert "hooks/brand_new_hook.py" in out, f"refusal must NAME the file; got:\n{out}"


def test_gate_refuses_a_gitignored_file_that_rsync_ships(source_repo: Path, capsys):
    """BLOCKING 1: the third shape — ignored, and therefore previously invisible.

    Measured on the real repo 2026-08-22: ``git status --porcelain -uall``
    reported 2 entries under the deployed subdirs while 55 gitignored files sat
    there, 46 outside ``__pycache__``. 38 ``,cover`` files, 13 ``.DS_Store`` and
    a stray session markdown were ALREADY EXECUTING in a consumer repo, shipped
    by ``rsync -a``, present in no commit, and the gate printed "clean tree".

    The instrument check is part of the test: it asserts git itself cannot see
    the file, so a future refactor back to a ``git status`` parse fails here
    rather than silently reopening the hole.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    (plugin / "hooks" / "shadow_payload.junkext").write_text("# ignored, but shipped\n")

    # POSITIVE CONTROL on the instrument: git is blind to this file.
    porcelain = _git(
        source_repo,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        str(plugin / "hooks"),
    )
    assert "shadow_payload" not in porcelain, (
        "fixture is wrong: the file must be gitignored for this test to mean anything\n"
        f"porcelain:\n{porcelain}"
    )
    # ...and it really is in the set rsync ships.
    assert "hooks/shadow_payload.junkext" in deploy_state.source_deployed_files(plugin)

    code = _gate(source_repo)
    out = capsys.readouterr().err
    assert code == 1, "a gitignored file in the deployed set MUST be refused"
    assert "hooks/shadow_payload.junkext" in out, f"must NAME it; got:\n{out}"


def test_gate_ignores_dirt_outside_the_deployed_subdirs(source_repo: Path, capsys):
    """Scoping control: dirt that is NOT deployed must not refuse the deploy.

    ``README.md`` and ``docs/`` are never copied by deploy-all.sh, so treating
    them as dirty would make the gate fire routinely — the cry-wolf failure.
    """
    (source_repo / "README.md").write_text("unrelated local edit\n")

    assert _gate(source_repo) == 0, capsys.readouterr().out


# --------------------------------------------------------------------------
# 2. The PERMITTING arm — the development loop must still work
# --------------------------------------------------------------------------


def test_gate_permits_clean_tree(source_repo: Path, capsys):
    assert _gate(source_repo) == 0, capsys.readouterr().out


def test_gate_permits_a_tree_carrying_only_build_artifacts(source_repo: Path, capsys):
    """BLOCKING 1's PERMITTING half — the no-cry-wolf control.

    Closing the ignored-file hole traded one failure mode for another unless
    the recurring, machine-generated members of that class stop being SHIPPED.
    They are excluded from the deployed set (rsync is given the same patterns),
    not merely from the gate, so this tree is genuinely clean rather than
    clean-by-exception. If this test goes red, the gate has become permanently
    red on any developer machine that has ever run pytest, which is the
    cry-wolf failure this project treats as a defect in its own right.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    (plugin / "hooks" / "unified_pre_tool.py,cover").write_text("> # coverage annotation\n")
    (plugin / "hooks" / ".DS_Store").write_bytes(b"\x00\x01macOS turd")
    cache = plugin / "lib" / "__pycache__"
    cache.mkdir()
    (cache / "hook_safety.cpython-313.pyc").write_bytes(b"\x00compiled")
    (plugin / "lib" / "coverage.xml").write_text("<coverage/>\n")
    # The observed instance: several hooks write to the RELATIVE path
    # Path("docs/sessions"), so a hook run with cwd=<plugin>/hooks creates one
    # of these. One was already deployed into a consumer repo.
    sessions = plugin / "hooks" / "docs" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "20260606-132224-session.md").write_text("# Session\n")

    assert _gate(source_repo) == 0, capsys.readouterr().out + capsys.readouterr().err

    shipped = deploy_state.source_deployed_files(plugin)
    for artifact in (
        "hooks/unified_pre_tool.py,cover",
        "hooks/.DS_Store",
        "lib/__pycache__/hook_safety.cpython-313.pyc",
        "lib/coverage.xml",
        "hooks/docs/sessions/20260606-132224-session.md",
    ):
        assert artifact not in shipped, f"{artifact} must not be in the DEPLOYED SET"
    assert "hooks/unified_pre_tool.py" in shipped, "real source must still ship"


def test_a_real_source_file_under_a_docs_subdir_still_ships(source_repo: Path):
    """SCOPING CONTROL for the session-log exclusion.

    Excluding ``docs/`` wholesale would drop the tracked ``skills/*/docs``
    trees. The exclusion is a filename CLASS, so ordinary documentation under
    a deployed subdir must still be in the deployed set.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    docs = plugin / "hooks" / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "authentication.md").write_text("# Real shipped doc\n")

    shipped = deploy_state.source_deployed_files(plugin)
    assert "hooks/docs/authentication.md" in shipped, (
        "the exclusion is scoped to session/pipeline working files, not to docs/"
    )


def test_gate_permits_dirty_tree_with_explicit_flag(source_repo: Path, capsys):
    """The iterate-and-test loop on hook code stays open behind an explicit flag."""
    (source_repo / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py").write_text(
        "# work in progress\n"
    )

    code = _gate(source_repo, "--dirty")
    out = capsys.readouterr().out
    assert code == 0, out
    assert "hooks/unified_pre_tool.py" in out, "the permitting arm must still NAME what it ships"


def test_dirty_deploy_records_every_uncommitted_file_by_name_and_digest(
    source_repo: Path, consumer: Path
):
    """The permitting arm's obligation: attribution, not silence."""
    plugin = source_repo / "plugins" / "autonomous-dev"
    (plugin / "lib" / "hook_safety.py").write_text("# 684-line intermediate\n")
    (plugin / "hooks" / "brand_new_hook.py").write_text("# untracked\n")

    _fake_deploy(plugin, consumer / ".claude")
    assert _stamp(source_repo, consumer, dirty=True) == 0

    state = _read_state(consumer)
    assert state["dirty"] is True
    assert set(state["uncommitted_files"]) == {
        "lib/hook_safety.py",
        "hooks/brand_new_hook.py",
    }
    assert state["unmatched_uncommitted"] == []
    for rel in state["uncommitted_files"]:
        assert rel in state["digests"], f"{rel} recorded as uncommitted but has no digest"
        expected = hashlib.sha256((consumer / ".claude" / rel).read_bytes()).hexdigest()
        assert state["digests"][rel] == expected


# --------------------------------------------------------------------------
# 3. BLOCKING 2 — refuse to guess when --source is not the git toplevel
# --------------------------------------------------------------------------


@pytest.fixture
def nested_source_repo(tmp_path: Path) -> Path:
    """A checkout that lives INSIDE another git repository.

    Latent on this machine today (no parent of the repo is a git repo) and live
    the moment the clone sits inside one — including the remote Mac Studio
    checkout.
    """
    outer = tmp_path / "outer"
    inner_plugin = outer / "inner" / "plugins" / "autonomous-dev" / "hooks"
    inner_plugin.mkdir(parents=True)
    (inner_plugin / "legit.py").write_text("ok\n")
    _git(outer, "init", "-q")
    _git(outer, "config", "user.email", "t@example.com")
    _git(outer, "config", "user.name", "t")
    _git(outer, "add", "-A")
    _git(outer, "commit", "-q", "-m", "init")
    # Now make the INNER tree dirty in both shapes.
    (inner_plugin / "legit.py").write_text("modified, in no commit\n")
    (inner_plugin / "uncommitted.py").write_text("untracked, in no commit\n")
    return outer / "inner"


def test_gate_refuses_to_guess_when_source_is_not_the_git_toplevel(
    nested_source_repo: Path, capsys
):
    """BLOCKING 2: it did not break loudly — it asserted the opposite and permitted.

    git finds a repository by walking UP, so porcelain paths were relative to
    the OUTER toplevel. Every entry failed the inner-root prefix filter, the
    function returned ``[]``, and that read as clean.
    """
    code = _gate(nested_source_repo)
    err = capsys.readouterr().err

    assert code != 0, "returning 0 here is the silent fail-open this fixes"
    assert code == deploy_state.EXIT_UNKNOWN, "cannot-tell is UNKNOWN, not permitted"
    assert "toplevel" in err.lower(), f"must say WHY it refused to guess; got:\n{err}"


def test_stamp_refuses_to_guess_when_source_is_not_the_git_toplevel(
    nested_source_repo: Path, consumer: Path, capsys
):
    """The same function feeds stamp, so the record would also read dirty: false."""
    code = deploy_state.main(
        [
            "stamp",
            "--source",
            str(nested_source_repo),
            "--plugin-src",
            str(nested_source_repo / "plugins" / "autonomous-dev"),
            "--target",
            str(consumer / ".claude"),
        ]
    )
    assert code == deploy_state.EXIT_UNKNOWN, capsys.readouterr().err
    assert not (consumer / ".claude" / ".deploy-state.json").exists(), (
        "a record that would have lied must not be written at all"
    )


def test_gate_permits_a_normal_top_level_checkout(source_repo: Path, capsys):
    """PERMITTING control for the toplevel check: the ordinary layout still works."""
    assert _gate(source_repo) == 0, capsys.readouterr().err


# --------------------------------------------------------------------------
# 4. BLOCKING 3 — stamp must not silently discard what it cannot name-match
# --------------------------------------------------------------------------


def test_stamp_records_a_c_quoted_unicode_filename_as_dirty(source_repo: Path, consumer: Path):
    """BLOCKING 3a: default ``core.quotePath`` C-quotes non-ASCII names.

    The old parse produced ``templates/caf\\303\\251.py`` while the digest key
    was ``templates/café.py``, so the intersection filter dropped it and the
    record said ``dirty: false`` — on the ``--dirty`` path, which is exactly
    when the operator is relying on the record to say otherwise.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    (plugin / "lib" / "café.py").write_text("# uncommitted, non-ASCII name\n")

    _fake_deploy(plugin, consumer / ".claude")
    assert _stamp(source_repo, consumer, dirty=True) == 0

    state = _read_state(consumer)
    assert state["dirty"] is True, "a shipped uncommitted file must mark the record dirty"
    assert "lib/café.py" in state["uncommitted_files"]
    assert "lib/café.py" in state["digests"]


def test_stamp_expands_a_directory_entry_to_the_files_it_shipped(
    source_repo: Path, consumer: Path
):
    """BLOCKING 3b: an embedded repo is ONE porcelain entry; rsync ships its contents."""
    plugin = source_repo / "plugins" / "autonomous-dev"
    nested = plugin / "lib" / "vendored"
    nested.mkdir()
    (nested / "payload.py").write_text("# shipped, in no commit\n")
    (nested / "helper.py").write_text("# shipped, in no commit\n")

    _fake_deploy(plugin, consumer / ".claude")
    assert _stamp(source_repo, consumer, dirty=True) == 0

    state = _read_state(consumer)
    assert state["dirty"] is True
    assert {"lib/vendored/payload.py", "lib/vendored/helper.py"} <= set(
        state["uncommitted_files"]
    ), f"contents must be named individually; got {state['uncommitted_files']}"


def test_unattributable_uncommitted_path_fails_closed_instead_of_vanishing(tmp_path: Path):
    """The durable property: an intersection filter must never discard silently.

    Even if some future shape escapes every expansion rule, it lands in
    ``unmatched_uncommitted`` and forces ``dirty: true`` rather than
    disappearing from the artifact — which is what produced ``dirty: false``
    on a tree that was executing uncommitted content.
    """
    target = tmp_path / ".claude"
    (target / "lib").mkdir(parents=True)
    (target / "lib" / "known.py").write_text("x\n")

    shipped, unmatched = deploy_state.match_uncommitted_to_target(
        ["lib/mystery.py", "lib/known.py"],
        {"lib/known.py": "a" * 64},
        target,
    )
    assert shipped == ["lib/known.py"]
    assert unmatched == ["lib/mystery.py"], "unnameable != not shipped"


def test_uncommitted_path_for_a_subdir_this_target_never_receives_is_not_claimed(
    tmp_path: Path,
):
    """PERMITTING control for the fail-closed rule.

    The global target receives three subdirs, not eight. An uncommitted
    ``commands/foo.md`` is genuinely not executing there and must not be
    claimed as such — otherwise fail-closed becomes cry-wolf.
    """
    target = tmp_path / "global"
    (target / "lib").mkdir(parents=True)
    (target / "lib" / "known.py").write_text("x\n")

    shipped, unmatched = deploy_state.match_uncommitted_to_target(
        ["commands/foo.md"], {"lib/known.py": "a" * 64}, target
    )
    assert shipped == [] and unmatched == [], (
        "a subdir this target never receives is a legitimate drop, not a finding"
    )


# --------------------------------------------------------------------------
# 5. The stamp
# --------------------------------------------------------------------------


def test_clean_deploy_records_head_sha_and_dirty_false(source_repo: Path, consumer: Path):
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")
    assert _stamp(source_repo, consumer) == 0

    state = _read_state(consumer)
    head = _git(source_repo, "rev-parse", "HEAD").strip()
    assert state["source_commit"] == head
    assert state["dirty"] is False
    assert state["uncommitted_files"] == []
    assert state["unmatched_uncommitted"] == []
    assert state["digest_algorithm"] == "sha256"
    assert state["file_count"] == len(state["digests"]) > 0


def test_state_records_what_the_digest_walk_excluded(source_repo: Path, consumer: Path):
    """Measure-before-you-exclude, made durable in the artifact itself.

    The executing tree regenerates ``__pycache__`` at runtime even when the
    deploy never shipped it, so the count is taken from the TARGET.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")
    cache = consumer / ".claude" / "lib" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "hook_safety.cpython-313.pyc").write_bytes(b"\x00compiled")
    (consumer / ".claude" / "hooks" / ".DS_Store").write_bytes(b"\x00turd")

    _stamp(source_repo, consumer)

    state = _read_state(consumer)
    patterns = state["excluded"]["patterns"]
    assert "__pycache__/" in patterns and ".DS_Store" in patterns
    assert state["excluded"]["file_count"] == 2
    assert not any("__pycache__" in key for key in state["digests"])
    assert not any(key.endswith(".DS_Store") for key in state["digests"])


def test_symlinks_are_recorded_not_skipped(source_repo: Path, consumer: Path):
    """BLOCKING 4 (second half): ``rsync -a`` preserves symlinks.

    Skipping them left a deployed entry permanently unrecorded and therefore
    permanently unverifiable — a blind spot inside the tool built to remove
    blind spots.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    os.symlink("hook_safety.py", plugin / "lib" / "alias.py")

    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer, dirty=True)

    state = _read_state(consumer)
    assert "lib/alias.py" in state["digests"], "a deployed symlink must be recorded"
    assert state["digests"]["lib/alias.py"] == "symlink:hook_safety.py"


# --------------------------------------------------------------------------
# 6. /health-check reporting — including the no-cry-wolf negative control
# --------------------------------------------------------------------------


def test_check_is_quiet_on_a_correctly_deployed_tree(source_repo: Path, consumer: Path, capsys):
    """NEGATIVE CONTROL. A check that fires on a healthy tree gets ignored."""
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer)

    code, out = _check(consumer, capsys)
    assert code == 0, out
    assert "OK" in out
    head_short = _git(source_repo, "rev-parse", "--short", "HEAD").strip()
    assert head_short in out, "must report the deployed commit"
    for noisy in ("DRIFT", "uncommitted", "WARN", "differ", "NOT in the deploy record"):
        assert noisy not in out, f"cry-wolf: healthy tree emitted {noisy!r}:\n{out}"


def test_check_names_a_file_edited_after_deploy(source_repo: Path, consumer: Path, capsys):
    """POSITIVE CONTROL for the drift arm."""
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer)

    (consumer / ".claude" / "hooks" / "unified_pre_tool.py").write_text("# hand-edited live\n")

    code, out = _check(consumer, capsys)
    assert code == 1, out
    assert "hooks/unified_pre_tool.py" in out, f"drift must be NAMED; got:\n{out}"


def test_check_names_a_recorded_file_missing_from_the_executing_tree(
    source_repo: Path, consumer: Path, capsys
):
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer)

    (consumer / ".claude" / "lib" / "hook_safety.py").unlink()

    code, out = _check(consumer, capsys)
    assert code == 1, out
    assert "lib/hook_safety.py" in out


def test_check_names_a_module_injected_into_the_executing_lib_after_the_stamp(
    source_repo: Path, consumer: Path, capsys
):
    """BLOCKING 4: ``check`` could only ever see what the record already listed.

    Exploitability is concrete, not theoretical: hooks insert the deployed lib
    directory at ``sys.path[0]`` (``unified_pre_tool.py`` does it at five call
    sites), so an added ``.claude/lib/<module>.py`` shadowing a lazily-imported
    module executes INSIDE the enforcement layer. Before the reverse
    comparison, this printed ``OK ... 2 files match`` and exited 0.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer)

    injected = consumer / ".claude" / "lib" / "hook_bypass.py"
    injected.write_text("def is_bypassed(*a, **k):\n    return True\n")

    code, out = _check(consumer, capsys)
    assert code == 1, f"an unrecorded executing module MUST be a finding; got:\n{out}"
    assert "lib/hook_bypass.py" in out, f"must NAME the injected module; got:\n{out}"


def test_check_still_catches_a_recorded_file_replaced_by_a_symlink(
    source_repo: Path, consumer: Path, capsys, tmp_path: Path
):
    """The counterpart that already worked and must keep working."""
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer)

    drifted = tmp_path / "elsewhere.py"
    drifted.write_text("# attacker-controlled content\n")
    recorded = consumer / ".claude" / "lib" / "hook_safety.py"
    recorded.unlink()
    os.symlink(drifted, recorded)

    code, out = _check(consumer, capsys)
    assert code == 1, out
    assert "lib/hook_safety.py" in out


def test_check_reports_unknown_when_no_deploy_ever_stamped(consumer: Path, capsys):
    code, out = _check(consumer, capsys)
    assert code == 2, out
    assert "UNKNOWN" in out


def test_check_does_not_demand_an_impossible_action_without_a_local_source(
    consumer: Path, capsys
):
    """W-B: the remote gap must be self-describing, not alarming.

    Remote repos have no autonomous-dev source of their own, so a directive to
    "re-deploy with scripts/deploy-all.sh" from there could never be satisfied.
    A permanently-red directive that cannot be cleared trains bypass of the
    whole command.
    """
    (consumer / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    code, out = _check(consumer, capsys)
    assert code == 2, out
    assert "deploy-all.sh" not in out, (
        "must not order an action this tree cannot perform:\n" + out
    )
    assert "elsewhere" in out or "another" in out, (
        f"must explain WHERE the answer comes from instead; got:\n{out}"
    )


def test_check_directs_a_source_checkout_to_redeploy(tmp_path: Path, capsys):
    """PERMITTING control for the message above: where the action IS possible, give it."""
    root = tmp_path / "src-checkout"
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / "plugins" / "autonomous-dev").mkdir(parents=True)

    code = deploy_state.main(["check", "--repo", str(root)])
    out = capsys.readouterr().out
    assert code == 2
    assert "deploy-all.sh" in out, f"a tree that CAN redeploy must be told to; got:\n{out}"


# --------------------------------------------------------------------------
# 7. BLOCKING 5 — a probe that verified nothing must never announce success
# --------------------------------------------------------------------------


def test_check_reports_unknown_for_a_record_that_verifies_zero_files(consumer: Path, capsys):
    """Driven with controls in BOTH directions, because a probe that cannot
    fail cannot inform.

    ``.claude/*`` is gitignored, so this artifact is never committed and never
    reviewed — nothing else would have noticed the empty-map success branch.
    """
    lib = consumer / ".claude" / "lib"
    lib.mkdir(parents=True)
    (lib / "x.py").write_text("hello\n")
    digest = hashlib.sha256(b"hello\n").hexdigest()

    # CONTROL: a matching record passes.
    _write_state(consumer, {"source_commit_short": "abc123", "digests": {"lib/x.py": digest}})
    assert deploy_state.main(["check", "--repo", str(consumer)]) == 0
    capsys.readouterr()

    # CONTROL: a mismatching record fails.
    _write_state(consumer, {"source_commit_short": "abc123", "digests": {"lib/x.py": "0" * 64}})
    assert deploy_state.main(["check", "--repo", str(consumer)]) == 1
    capsys.readouterr()

    # PROBE: an empty map verified nothing, and must not say OK.
    _write_state(consumer, {"source_commit_short": "abc123", "digests": {}})
    code = deploy_state.main(["check", "--repo", str(consumer)])
    out = capsys.readouterr().out
    assert code == deploy_state.EXIT_UNKNOWN, f"0 files verified is never OK; got:\n{out}"
    assert "OK" not in out
    assert "malformed or empty" in out


def test_check_reports_unknown_when_digests_key_is_absent(consumer: Path, capsys):
    _write_state(consumer, {"source_commit_short": "abc123"})
    code, out = _check(consumer, capsys)
    assert code == deploy_state.EXIT_UNKNOWN, out
    assert "OK" not in out


# --------------------------------------------------------------------------
# 8. W-A — the record must not keep asserting something that stopped being true
# --------------------------------------------------------------------------


def test_check_says_uncommitted_at_deploy_time_not_present_in_no_commit(
    source_repo: Path, consumer: Path, capsys
):
    """The claim must be unconditionally true whenever it is printed."""
    plugin = source_repo / "plugins" / "autonomous-dev"
    (plugin / "lib" / "hook_safety.py").write_text("# 684-line intermediate\n")
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer, dirty=True)

    code, out = _check(consumer, capsys)
    assert code == 1, out
    assert "uncommitted at deploy time" in out, out
    assert "git cannot revert this" not in out, (
        "the old wording asserted a present-tense fact that expires:\n" + out
    )


def test_check_downgrades_a_file_that_has_since_been_committed(
    source_repo: Path, consumer: Path, capsys
):
    """W-A: a check that stays red after you did the right thing gets skipped.

    The executing bytes are byte-identical to a real commit and no redeploy has
    happened. Reporting "executing uncommitted content" here is simply false.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    (plugin / "lib" / "hook_safety.py").write_text("# 684-line intermediate\n")
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer, dirty=True)

    # RED BEFORE: the record says uncommitted, and it is.
    assert _check(consumer, capsys)[0] == 1

    # The operator does the right thing. No redeploy.
    _git(source_repo, "add", "-A")
    _git(source_repo, "commit", "-q", "-m", "commit the hook fix")

    code, out = _check(consumer, capsys)
    assert code == 0, f"bytes now match a commit; the claim expired:\n{out}"
    assert "since committed" in out, out


def test_check_does_not_downgrade_a_file_that_is_still_uncommitted(
    source_repo: Path, consumer: Path, capsys
):
    """NEGATIVE CONTROL for the self-heal: it must not downgrade everything."""
    plugin = source_repo / "plugins" / "autonomous-dev"
    (plugin / "lib" / "hook_safety.py").write_text("# 684-line intermediate\n")
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer, dirty=True)

    # Commit something ELSE. The deployed file is still in no commit.
    (source_repo / "README.md").write_text("unrelated\n")
    _git(source_repo, "add", "README.md")
    _git(source_repo, "commit", "-q", "-m", "unrelated")

    code, out = _check(consumer, capsys)
    assert code == 1, f"still uncommitted, must still be reported:\n{out}"
    assert "lib/hook_safety.py" in out


# --------------------------------------------------------------------------
# 9. W-E / W-F / W-G — the record is untrusted input
# --------------------------------------------------------------------------


def test_a_corrupt_state_file_is_not_reported_as_an_absent_one(consumer: Path, capsys):
    """W-E: "no record" sends the operator to re-deploy; "truncated" does not.

    A truncated write or tampering is inside this feature's threat model, and
    conflating it with an unstamped tree misdirects the diagnosis.
    """
    (consumer / ".claude" / ".deploy-state.json").write_text('{"digests": {"a": ')

    code, out = _check(consumer, capsys)
    assert code == deploy_state.EXIT_UNKNOWN, out
    assert "no .claude/.deploy-state.json" not in out, (
        "a file that EXISTS must not be reported as absent:\n" + out
    )
    assert "not valid JSON" in out


def test_check_refuses_digest_keys_that_escape_the_deployed_tree(consumer: Path, capsys):
    """W-F (CWE-22): ``Path(target) / key`` with an absolute key replaces the base."""
    _write_state(
        consumer,
        {
            "source_commit_short": "abc123",
            "digests": {"/etc/hosts": "0" * 64, "../../../evil.txt": "1" * 64},
        },
    )

    code, out = _check(consumer, capsys)
    assert code == deploy_state.EXIT_FINDING, out
    assert "/etc/hosts" in out and "../../../evil.txt" in out
    assert "OK" not in out


def test_safe_relative_keys_are_still_accepted(consumer: Path, capsys):
    """PERMITTING control for the traversal check: normal keys must still work."""
    lib = consumer / ".claude" / "lib"
    lib.mkdir(parents=True)
    (lib / "x.py").write_text("hello\n")
    _write_state(
        consumer,
        {
            "source_commit_short": "abc123",
            "digests": {"lib/x.py": hashlib.sha256(b"hello\n").hexdigest()},
        },
    )
    code, out = _check(consumer, capsys)
    assert code == 0, out


def test_type_confused_digests_return_unknown_not_a_traceback(consumer: Path, capsys):
    """W-G: a traceback with exit 1 is indistinguishable from a drift finding."""
    _write_state(consumer, {"source_commit_short": "abc", "digests": ["not", "a", "dict"]})
    code, out = _check(consumer, capsys)
    assert code == deploy_state.EXIT_UNKNOWN, out
    assert "Traceback" not in out


def test_type_confused_digest_values_return_unknown(consumer: Path, capsys):
    _write_state(consumer, {"source_commit_short": "abc", "digests": {"lib/x.py": 12345}})
    code = deploy_state.main(["check", "--repo", str(consumer)])
    combined = capsys.readouterr()
    assert code in (deploy_state.EXIT_FINDING, deploy_state.EXIT_UNKNOWN)
    assert "Traceback" not in combined.out + combined.err


# --------------------------------------------------------------------------
# 10. THE #1610 REPRODUCTION — an intermediate tree that exists in no commit
# --------------------------------------------------------------------------


def test_reproduces_issue_1610_health_check_names_executing_uncommitted_content(
    source_repo: Path, consumer: Path, capsys
):
    """Deploy an intermediate working tree; /health-check must name the file.

    This is the measured state in miniature: HEAD has one shape, the working
    tree has another that was never committed, and the SECOND is what executes.
    Before this change nothing recorded that, so the question "what is
    running?" had no answer in the repository.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    committed = _git(source_repo, "rev-parse", "HEAD").strip()

    (plugin / "lib" / "hook_safety.py").write_text(
        "class HookDecision:\n    pass\n\n"
        "try:\n    emit()\nexcept (OSError, ValueError, TypeError):\n    pass\n"
    )
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer, dirty=True)

    code, out = _check(consumer, capsys)

    assert code == 1, out
    assert "lib/hook_safety.py" in out, f"must NAME the file executing uncommitted; got:\n{out}"
    assert "uncommitted" in out.lower()
    assert committed[:8] in out, "must still report which commit the rest came from"

    state = _read_state(consumer)
    assert state["uncommitted_files"] == ["lib/hook_safety.py"]
    assert (
        state["digests"]["lib/hook_safety.py"]
        == hashlib.sha256(
            (consumer / ".claude" / "lib" / "hook_safety.py").read_bytes()
        ).hexdigest()
    )


# --------------------------------------------------------------------------
# 11. Consumer-repo portability (#1586 pattern: shipped and per-repo runnable)
# --------------------------------------------------------------------------


def test_check_runs_from_an_installed_tree_with_no_git_and_no_plugin_source(
    source_repo: Path, tmp_path: Path
):
    """The executing copy is `.claude/scripts/deploy_state.py` in a foreign repo."""
    plugin = source_repo / "plugins" / "autonomous-dev"
    installed = tmp_path / "foreign-repo"
    (installed / ".claude").mkdir(parents=True)
    _fake_deploy(plugin, installed / ".claude")

    deploy_state.main(
        [
            "stamp",
            "--source",
            str(source_repo),
            "--plugin-src",
            str(plugin),
            "--target",
            str(installed / ".claude"),
        ]
    )

    assert not (installed / ".git").exists()
    assert not (installed / "plugins").exists()

    # Run the DEPLOYED copy as a subprocess, the way /health-check does.
    result = subprocess.run(
        [
            sys.executable,
            str(installed / ".claude" / "scripts" / "deploy_state.py"),
            "check",
            "--repo",
            str(installed),
        ],
        capture_output=True,
        text=True,
        cwd=str(installed),
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "OK" in result.stdout


# --------------------------------------------------------------------------
# 12. BLOCKING 6 — the manifest the installers ACTUALLY read
# --------------------------------------------------------------------------


def _installer_manifest_paths() -> dict[str, str]:
    """Derive the manifest path each installer declares, from its own source.

    Not hardcoded: the previous test asserted ``PLUGIN_SRC/install_manifest.json``
    — a path neither installer reads — so it was GREEN while the property its
    own docstring named was false. Reading the declaration means the test
    cannot drift from the code again.
    """
    found: dict[str, str] = {}
    py = re.search(r'^MANIFEST_FILE\s*=\s*"([^"]+)"', INSTALL_PY.read_text(), re.M)
    if py:
        found["install.py"] = py.group(1)
    sh = re.search(r'^MANIFEST_FILE="([^"]+)"', INSTALL_SH.read_text(), re.M)
    if sh:
        found["install.sh"] = sh.group(1)
    return found


def test_both_installers_declare_a_manifest_path():
    """Instrument check: if this regex stops matching, the test below means nothing."""
    declared = _installer_manifest_paths()
    assert set(declared) == {"install.py", "install.sh"}, (
        f"could not read MANIFEST_FILE from both installers; got {declared}"
    )


def test_deploy_state_is_in_the_manifest_each_installer_reads():
    """BLOCKING 6: the script went into a fossil manifest nobody reads.

    ``deploy-all.sh`` rsyncs the whole ``scripts/`` directory, so the file
    lands in consumer repos on THIS machine regardless of the manifest. The
    ``curl | bash`` and ``/sync`` paths copy only manifest entries — so
    ``/health-check`` in a freshly installed repo printed
    ``DEPLOY-STATE: not installed (run /sync)``, and ``/sync`` never fixed it.

    Measured 2026-08-22: the root ``plugins/autonomous-dev/install_manifest.json``
    is version 3.50.0 against the config manifest's 3.51.0, and is missing 167
    entries including ``commands/plan.md`` and ``agents/plan-critic.md``. That
    divergence is a separate defect and is NOT fixed here.
    """
    for installer, rel in _installer_manifest_paths().items():
        manifest_path = REPO_ROOT / rel
        assert manifest_path.is_file(), f"{installer} reads a manifest that is not there: {rel}"
        manifest = json.loads(manifest_path.read_text())
        names = {Path(f).name for f in manifest["components"]["scripts"]["files"]}
        assert "deploy_state.py" in names, (
            f"deploy_state.py missing from {rel}, which {installer} reads.\n"
            "A shipped check absent from the install path is unreachable in "
            "every consumer repo installed by curl|bash or /sync."
        )


def test_deploy_state_is_in_the_deployed_manifest_copy_that_executes():
    """Committed is not deployed. Verify the copy /sync actually reads at runtime."""
    deployed = REPO_ROOT / ".claude" / "config" / "install_manifest.json"
    if not deployed.is_file():
        pytest.fail(f"deployed manifest copy is missing: {deployed}")
    manifest = json.loads(deployed.read_text())
    names = {Path(f).name for f in manifest["components"]["scripts"]["files"]}
    assert "deploy_state.py" in names, (
        "the EXECUTING manifest copy under .claude/config/ does not carry "
        "deploy_state.py — the source was updated but the running copy was not"
    )


# --------------------------------------------------------------------------
# 13. Activity log — a row without a `type` is unfindable in a 24k-row/day sink
# --------------------------------------------------------------------------


def test_deploy_writes_a_findable_activity_row(source_repo: Path, consumer: Path):
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")

    deploy_state.main(
        [
            "stamp",
            "--source",
            str(source_repo),
            "--plugin-src",
            str(plugin),
            "--target",
            str(consumer / ".claude"),
            "--log-activity",
        ]
    )

    logs = sorted((source_repo / ".claude" / "logs" / "activity").glob("*.jsonl"))
    assert logs, "deploy must leave a correlatable trace"
    rows = [json.loads(line) for line in logs[-1].read_text().splitlines() if line.strip()]
    deploys = [r for r in rows if r.get("type") == "deploy"]
    assert len(deploys) == 1, "row MUST carry top-level type='deploy' or it is unfindable"
    row = deploys[0]
    assert row["source_commit"] == _git(source_repo, "rev-parse", "HEAD").strip()
    assert row["dirty"] is False
    assert str(consumer / ".claude") in row["targets"]


# --------------------------------------------------------------------------
# 14. Wiring — the gate is useless if deploy-all.sh does not call it
# --------------------------------------------------------------------------


def test_deploy_all_sh_gates_before_it_deploys():
    text = DEPLOY_ALL_SH.read_text()
    assert "--dirty" in text, "deploy-all.sh must expose the explicit escape hatch"
    assert "deploy_state.py" in text, "deploy-all.sh must invoke the gate"

    main_pos = text.index("# --- Main ---")
    first_deploy = text.index("    deploy_global\n", main_pos)
    gate_call = text.index('"${gate_args[@]}"', main_pos)
    stamp_call = text.index('"${stamp_args[@]}"', main_pos)
    assert gate_call < first_deploy, "the gate MUST run before the first deploy"
    assert stamp_call > first_deploy, "provenance is stamped after the copy, from the target"


def test_health_check_surfaces_the_deployed_commit():
    text = HEALTH_CHECK_MD.read_text()
    assert "deploy_state.py" in text, "/health-check must report what is executing"
    assert "DEPLOY-STATE" in text


def test_health_check_exit_status_is_not_gated_by_deploy_state(tmp_path: Path):
    """#1586 precedent, asserted BEHAVIOURALLY rather than by source text.

    The previous version asserted ``"DEPLOY_RC" not in exit_line[0]`` — an
    absence-check on a variable name that appears nowhere in the file, so it
    passed no matter what, including if someone added ``DS_RC`` to the exit OR.
    This runs the extracted exit expression with the deploy-state code set to
    the worst case and asserts the command's status is unchanged.
    """
    text = HEALTH_CHECK_MD.read_text()
    exit_lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("exit $((")]
    assert exit_lines, "health-check must still compute an explicit exit status"
    expression = exit_lines[0]

    script = tmp_path / "exit_probe.sh"
    # Every input that legitimately gates the exit is 0; deploy-state is 1 and 2.
    script.write_text(
        "STRUCT_RC=0\nHOOK_RC=0\nPLUGIN_REGISTERED=0\n"
        "DEPLOY_RC=1\nDS_RC=2\nDEPLOY_STATE_RC=1\n" + expression + "\n"
    )
    result = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, (
        "a deploy-state finding must NOT turn /health-check red — a consumer-side "
        f"check that goes permanently red trains bypass of the whole command.\n"
        f"expression: {expression}\nexit: {result.returncode}"
    )

    # POSITIVE CONTROL: the expression is not simply always 0.
    script.write_text("STRUCT_RC=1\nHOOK_RC=0\nPLUGIN_REGISTERED=0\n" + expression + "\n")
    control = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert control.returncode != 0, (
        "instrument check failed: the exit expression ignores its real inputs too"
    )


def test_gate_reports_broken_instrument_distinguishably_from_a_pass(tmp_path: Path, capsys):
    """A guard that BROKE must not be indistinguishable from a guard that PASSED.

    This is #1471's shape: the machinery fails, the exception is swallowed, and
    control falls through to allow. Here the gate returns 2, never 0, so
    deploy-all.sh can fail open *loudly* instead of silently.
    """
    not_a_repo = tmp_path / "tarball"
    (not_a_repo / "plugins" / "autonomous-dev" / "lib").mkdir(parents=True)

    code = deploy_state.main(
        [
            "gate",
            "--source",
            str(not_a_repo),
            "--plugin-src",
            str(not_a_repo / "plugins" / "autonomous-dev"),
        ]
    )
    err = capsys.readouterr().err
    assert code == 2, "a broken gate MUST NOT return 0 (that is a silent fail-open)"
    assert "UNKNOWN" in err, "a fail-open must leave a trace"


def test_deploy_all_sh_distinguishes_refusal_from_gate_breakage():
    """Behavioural: exit 1 aborts, other non-zero codes fail open loudly."""
    text = DEPLOY_ALL_SH.read_text()
    assert "proceeding WITHOUT provenance verification" in text, (
        "a gate that broke must announce it rather than look like a pass"
    )


@pytest.mark.parametrize("interpreter", ["bash", "/bin/bash"])
def test_deploy_all_sh_is_valid_bash(interpreter: str):
    """Parse under BOTH the ambient bash and the system bash.

    Not redundant: ``bash`` on this machine is Homebrew 5.3 and ``/bin/bash`` is
    Apple's 3.2.57. bash 3.2 scans ``$( ... )`` WITHOUT honouring ``#``
    comments, so a lone apostrophe in a comment inside the remote heredoc makes
    the whole script unparseable — and it really happened during this
    remediation. Checking only the ambient bash was green while every
    ``/bin/bash`` invocation, including the remote, was broken.
    """
    if not Path(interpreter).exists() and interpreter.startswith("/"):
        pytest.fail(f"{interpreter} is expected to exist on macOS")
    result = subprocess.run(
        [interpreter, "-n", str(DEPLOY_ALL_SH)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"{interpreter} cannot parse deploy-all.sh:\n{result.stderr}"


# --------------------------------------------------------------------------
# 15. W-H — the duplicated lists must not drift
# --------------------------------------------------------------------------


def _extract_shell_function(name: str) -> str:
    """Return the source text of a shell function defined in deploy-all.sh.

    Lets a test drive the REAL function rather than a paraphrase of it, so the
    test cannot pass against a copy that has drifted from the deployed script.
    """
    text = DEPLOY_ALL_SH.read_text()
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + len("\n}\n")
    return text[start:end]


def _shell_assignment(name: str) -> str:
    match = re.search(rf'^{name}="([^"]*)"', DEPLOY_ALL_SH.read_text(), re.M)
    assert match, f"could not find {name}= in deploy-all.sh"
    return match.group(1)


def test_deploy_subdirs_match_deploy_all_sh():
    """W-H: adding a subdir to the shell list would silently remove it from coverage."""
    shell_subdirs = set(_shell_assignment("SUBDIRS").split())
    assert shell_subdirs == set(deploy_state.DEPLOY_SUBDIRS), (
        "deploy-all.sh $SUBDIRS and deploy_state.DEPLOY_SUBDIRS have drifted.\n"
        f"  shell only:  {sorted(shell_subdirs - set(deploy_state.DEPLOY_SUBDIRS))}\n"
        f"  python only: {sorted(set(deploy_state.DEPLOY_SUBDIRS) - shell_subdirs)}"
    )


def test_global_subdirs_are_a_subset_of_the_deployed_subdirs():
    shell_global = set(_shell_assignment("GLOBAL_SUBDIRS").split())
    assert shell_global <= set(deploy_state.DEPLOY_SUBDIRS)


def test_rsync_exclude_patterns_match_deploy_all_sh():
    """The exclusions define the DEPLOYED SET; the gate measures the same set.

    If they drift, the gate is measuring something rsync does not ship (false
    refusals) or missing something rsync does (a silent hole — the exact shape
    of BLOCKING 1).
    """
    text = DEPLOY_ALL_SH.read_text()
    block = re.search(r"^DEPLOY_EXCLUDES=\((.*?)^\)", text, re.M | re.S)
    assert block, "could not find the DEPLOY_EXCLUDES array in deploy-all.sh"
    shell_patterns = set(re.findall(r"--exclude='([^']*)'", block.group(1)))
    python_patterns = set(deploy_state.rsync_exclude_patterns())
    assert shell_patterns == python_patterns, (
        "deploy-all.sh $DEPLOY_EXCLUDES and deploy_state.rsync_exclude_patterns() drifted.\n"
        f"  shell only:  {sorted(shell_patterns - python_patterns)}\n"
        f"  python only: {sorted(python_patterns - shell_patterns)}"
    )


def _plugin_copy_invocations(paths: tuple[Path, ...] = DEPLOY_ALL_TRANSPORT) -> list[str]:
    """Every line in the given shell files that copies plugin source to a target.

    Deliberately tool-agnostic. The previous version of this helper's caller
    inspected only lines starting with ``rsync ``, which is why the remote
    ``cp -rf`` path went both unfixed AND untested: a probe scoped to one tool
    cannot see a defect in the other.

    ``paths`` defaults to the deploy-all TRANSPORT — deploy-all.sh plus the
    prune_sync library it inlines into its ssh heredoc — not to deploy-all.sh
    alone. Scoping to the one file would let the enumerator go blind the moment
    a copy site moves into the library: the count would drop from 4 to 2 and
    every per-invocation assertion would pass vacuously over the survivors.
    ``test_plugin_copy_invocation_count_is_pinned`` is the control that catches
    exactly that.

    Returns:
        ``"<filename>:<lineno>: <stripped line>"`` for each invocation, so a
        failure names the site rather than only quoting an anonymous command.
    """
    found: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        for lineno, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if not re.match(COPY_INVOCATION_RE, line):
                continue  # comments and everything else
            # ``$src_dir`` is prune_sync()'s plugin-source parameter; the other
            # two forms are the literal source paths used at the inline sites.
            if '"$src_dir"' in line or "$PLUGIN_SRC/" in line or "plugins/autonomous-dev" in line:
                found.append(f"{path.name}:{lineno}: {line}")
    return found


def test_every_copy_invocation_applies_the_shared_exclusions():
    """BLOCKING B: exclusions on the measured path only is a gate that lies.

    ``deploy-all.sh`` has THREE copy sites, not two: global rsync, per-repo
    rsync, and the remote copy inside the ssh heredoc. The remote one was
    ``cp -rf plugins/autonomous-dev/$subdir/* ...`` with no exclusions, while
    the remote gate measures ``source_deployed_files()`` — the walk MINUS those
    same exclusions. The gate therefore affirmed a cleanliness the copy did not
    deliver, into five remote repos.

    The instrument check matters here: the previous test filtered to lines
    starting with ``rsync ``, which is exactly why it stayed green through the
    defect. This asserts over EVERY copy invocation.
    """
    invocations = _plugin_copy_invocations()
    assert len(invocations) >= 3, (
        "expected global + per-repo + remote copy sites; the filter found "
        f"{len(invocations)}: {invocations}"
    )
    for line in invocations:
        applies_array = '"${DEPLOY_EXCLUDES[@]}"' in line
        applies_literal = "$remote_excludes" in line
        # prune_sync() receives the same 18 patterns as an array built at the
        # heredoc top level from $remote_excludes.
        applies_remote_array = '"${remote_excludes_arr[@]}"' in line
        assert applies_array or applies_literal or applies_remote_array, (
            "a copy invocation ships content the provenance gate does not "
            f"measure: {line}"
        )


def test_no_copy_invocation_uses_bare_cp_for_plugin_subdirs():
    """The durable half: remove the primitive, do not just fix this call site.

    ``cp`` has no exclusion mechanism at all, so any reintroduction of it here
    re-opens the whole class rather than one instance.
    """
    offenders = [
        line.strip()
        for line in DEPLOY_ALL_SH.read_text().splitlines()
        if line.strip().startswith("cp ") and "plugins/autonomous-dev" in line
    ]
    assert offenders == [], (
        "cp cannot apply the deploy exclusions, so anything it copies is shipped "
        f"but unmeasured. Use rsync with the shared patterns:\n{offenders}"
    )


# --------------------------------------------------------------------------
# 15b. Deletion propagates on EVERY transport, and the instrument that says so
#      is itself controlled.
#
# The defect: three of six rsync sites shipped without ``--delete``, so a module
# deleted from source survived on the target forever and stayed importable
# through the ``sys.path`` fallback to ``~/.claude/lib``. Measured: the five
# modules removed in 7c3a527e were alive on all six targets.
#
# Every control below is a DIFFERENT SHAPE from that defect (a missing flag):
# a count, a forbidden token, a set cardinality, a parse. None of them can be
# satisfied by adding a flag, so none can be gamed by the fix.
# --------------------------------------------------------------------------


def _top_level_local_offenders(text: str, *, label: str = "line") -> list[str]:
    """``local`` statements outside any function definition in ``text``.

    ``local`` INSIDE a function is legal and expected — prune_sync() uses it —
    so this tracks function-definition depth rather than banning the keyword.

    A function opener is ``name() {`` at any indentation; a function CLOSER is
    ``}`` at COLUMN ZERO only. That asymmetry is load-bearing: prune_sync uses
    ``cmd || { ...; return 1; }`` blocks whose closing brace is indented, and
    counting those as function closers drops the depth to 0 partway through the
    body and reports every subsequent ``local`` as a top-level offender.
    """
    depth = 0
    offenders: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\(\)\s*\{", line):
            depth += 1
            continue
        if raw == "}" and depth > 0:
            depth -= 1
            continue
        if depth == 0 and re.match(r"^local\s", line):
            offenders.append(f"{label} {lineno}: {line}")
    return offenders


def test_every_copy_invocation_propagates_deletions():
    """T1 — a transport that never deletes cannot un-ship a deleted module.

    ``deploy-all.sh`` had FOUR rsync sites and only two carried ``--delete``.
    The two that did not were the remote per-repo sync and the remote global
    sync — the pair that reaches five repos plus a home directory on another
    machine, i.e. the widest blast radius had the weakest transport.

    Flag-agnostic on purpose: it asserts a property of every enumerated
    invocation rather than grepping for a known-good line, so a fifth site
    added tomorrow is covered on the day it is added.
    """
    invocations = _plugin_copy_invocations()
    assert invocations, "the enumerator found no copy invocations at all"

    missing = [line for line in invocations if "--delete" not in line]
    assert not missing, (
        "copy invocations that do NOT propagate deletions — a module deleted "
        "from source survives on these targets forever and stays importable "
        "via the sys.path fallback:\n"
        + "\n".join(f"  {line}" for line in missing)
        + "\n\nFix: route the site through prune_sync(), which previews the "
        "deletion set and refuses before anything is removed."
    )


def test_plugin_copy_invocation_count_is_pinned():
    """T2 — the enumerator's own control: a count, not a per-line property.

    T1 asserts a property of each invocation it finds. That is vacuously true
    over an empty list, and — the live risk here — it stays true if a site
    STOPS being enumerated because it moved into a file the enumerator does not
    read. Pinning the counts means a site that disappears from the scan fails
    loudly instead of passing quietly.

    4 for the deploy-all transport: global rsync, per-repo rsync, and
    prune_sync()'s preview + live pair. 2 for deploy_local.sh: per-repo and
    global. If ``deploy_local.sh:167`` ever gains ``--delete`` or a caller, this
    count is where the question re-opens (Residual Risk 4).
    """
    deploy_all = _plugin_copy_invocations()
    assert len(deploy_all) == 4, (
        "expected exactly 4 copy invocations on the deploy-all transport "
        f"(deploy-all.sh + prune_sync.sh); found {len(deploy_all)}:\n"
        + "\n".join(f"  {line}" for line in deploy_all)
    )

    deploy_local = _plugin_copy_invocations((DEPLOY_LOCAL_SH,))
    assert len(deploy_local) == 2, (
        f"expected exactly 2 copy invocations in deploy_local.sh; found "
        f"{len(deploy_local)}:\n" + "\n".join(f"  {line}" for line in deploy_local)
    )


def test_delete_excluded_appears_in_no_deploy_script():
    """T3 — forbidden-token control, comments included.

    An unqualified ``--exclude`` PROTECTS a receiver-side file from ``--delete``
    (man rsync, FILTER RULES WHEN DELETING). The delete-excluded flag removes
    exactly that protection, and that protection is the only thing keeping
    ``hooks/extensions/`` (Issue #560) and runtime ``.claude/`` state alive on
    every target. Adding it would turn a narrowing change into a wipe.

    Comments are scanned too, so a commented-out invocation cannot sit in the
    file waiting to be uncommented. The consequence is a writing convention:
    prose in these three files names the flag WITHOUT its leading dashes. That
    is not evasion — the forbidden thing is the argument, which does not exist
    without them, and the convention keeps the warning readable while leaving
    the token itself absent from the file.
    """
    forbidden = "--delete-" + "excluded"  # assembled so this test file is not itself a hit
    offenders: list[str] = []
    for path in SHELL_FILES:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if forbidden in line:
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")

    assert offenders == [], (
        f"{forbidden} strips the receiver-side protection that --exclude "
        "confers, which is what keeps hooks/extensions/ (Issue #560) and "
        "runtime .claude/ state alive on every deploy target:\n"
        + "\n".join(f"  {line}" for line in offenders)
        + "\n\nIn prose, write the flag name without its leading dashes."
    )


def test_deploy_excludes_was_not_narrowed():
    """T4 — set-cardinality control.

    The cheapest way to make a ``--delete`` sync stop refusing is to delete
    exclusion patterns, which is the opposite of the intended change: every
    pattern removed here ENLARGES what ``--delete`` may remove. Its companion,
    ``test_rsync_exclude_patterns_match_deploy_all_sh``, asserts set EQUALITY
    with ``deploy_state.rsync_exclude_patterns()`` — but equality is preserved
    if somebody narrows both sides together, so the floor is asserted here as
    well.
    """
    text = DEPLOY_ALL_SH.read_text()
    block = re.search(r"^DEPLOY_EXCLUDES=\((.*?)^\)", text, re.M | re.S)
    assert block, "could not find the DEPLOY_EXCLUDES array in deploy-all.sh"
    shell_patterns = set(re.findall(r"--exclude='([^']*)'", block.group(1)))

    assert len(shell_patterns) >= 18, (
        f"$DEPLOY_EXCLUDES narrowed to {len(shell_patterns)} patterns (floor is "
        f"18). Each removed pattern widens what --delete may remove:\n"
        f"  {sorted(shell_patterns)}"
    )
    for required in ("extensions/", "__pycache__/", "docs/sessions/"):
        assert required in shell_patterns, (
            f"$DEPLOY_EXCLUDES lost {required!r} — a consumer-local or runtime "
            "class is now inside the deletion scope"
        )


def test_all_deploy_shell_files_parse():
    """T5 — SECONDARY parse check, explicitly not the primary guard.

    ``bash -n`` proves the file parses; it proves nothing about behaviour, and
    it never evaluates a heredoc body, which is precisely where the dangerous
    edits are. It earns its place for one narrow reason: ``local`` outside a
    function is a RUNTIME error in both bash and zsh, so a stray ``local`` at
    heredoc top level would surface only on the remote machine, mid-loop, after
    repos had already been pruned. Both interpreters, because the remote may be
    running Apple bash 3.2.
    """
    for path in SHELL_FILES:
        assert path.exists(), f"deploy shell file missing: {path}"
        for interpreter in ("bash", "/bin/bash"):
            syntax = subprocess.run(
                [interpreter, "-n", str(path)], capture_output=True, text=True
            )
            assert syntax.returncode == 0, (
                f"{path.name} does not parse under {interpreter}:\n{syntax.stderr}"
            )


def test_no_local_at_heredoc_top_level_in_deploy_all():
    """T5b — the failure ``bash -n`` structurally cannot see.

    The remote script is generated by a heredoc. ``bash -n`` parses the heredoc
    as opaque text and never evaluates it, so a ``local`` written at heredoc top
    level passes every static check here and then aborts the remote shell
    mid-deploy. Scan the heredoc body directly.

    ``local`` INSIDE a function defined in the heredoc is legal and expected —
    prune_sync() uses it — so the scan tracks brace depth rather than banning
    the keyword.
    """
    text = DEPLOY_ALL_SH.read_text()
    body = re.search(r"^\s*ssh .*<<REMOTE_EOF\n(.*?)^REMOTE_EOF$", text, re.M | re.S)
    assert body, "could not locate the REMOTE_EOF heredoc body in deploy-all.sh"

    offenders = _top_level_local_offenders(body.group(1), label="heredoc line")

    assert offenders == [], (
        "`local` at heredoc top level is a runtime error in bash AND zsh, and "
        "`bash -n` never evaluates a heredoc body — so this would surface only "
        "on the remote, mid-loop, after repos had already been pruned:\n"
        + "\n".join(f"  {line}" for line in offenders)
    )


# --------------------------------------------------------------------------
# 16. W-B — the remote path is gated and stamped from the remote's own checkout
# --------------------------------------------------------------------------


def test_remote_deploy_script_gates_and_stamps(source_repo: Path, tmp_path: Path):
    """Drive the remote path with ssh shimmed: no network, no remote writes.

    Remote targets were never stamped, so ``/health-check`` on the Mac Studio
    printed UNKNOWN in all five repos forever, with a directive that running
    deploy from the laptop could never satisfy.
    """
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    capture = tmp_path / "remote_script.sh"
    shim = shim_dir / "ssh"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        'cmd="${@: -1}"\n'
        'if [ "$cmd" = "echo ok" ] || [ "$cmd" = "true" ]; then exit 0; fi\n'
        'printf "%s" "$cmd" > "$SSH_CAPTURE"\n'
    )
    shim.chmod(0o755)

    result = subprocess.run(
        ["bash", str(source_repo / "scripts" / "deploy-all.sh"), "--remote", "--skip-validate"],
        capture_output=True,
        text=True,
        cwd=str(source_repo),
        env={
            "PATH": f"{shim_dir}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(source_repo / "fake-home"),
            "REMOTE_HOST": "unused.invalid",
            "REMOTE_REPOS": "somerepo",
            "SSH_CAPTURE": str(capture),
        },
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert capture.is_file(), f"ssh shim captured nothing:\n{result.stdout}{result.stderr}"

    remote_script = capture.read_text()
    # NOTE: a fourth assertion stood here —
    #   assert "deploy_state.py" not in remote_script or "REMOTE_DEPLOY_STATE" in remote_script
    # It was DEAD: the left disjunct is true whenever the remote script does not
    # mention deploy_state.py at all, so the whole expression passed for a remote
    # script with no provenance wiring whatsoever. The three assertions below
    # carry the real property. Removed rather than repaired (Issue #1610).
    assert "gate --source" in remote_script, "the remote must be gated too"
    assert "stamp --source" in remote_script, "remote targets must be stamped"
    assert "REMOTE DEPLOY-GATE REFUSED" in remote_script

    # Under BOTH bashes: the remote may well be running Apple's 3.2.
    for interpreter in ("bash", "/bin/bash"):
        syntax = subprocess.run(
            [interpreter, "-n", str(capture)], capture_output=True, text=True
        )
        assert syntax.returncode == 0, (
            f"the generated remote script is not valid shell under {interpreter}:\n"
            f"{syntax.stderr}"
        )


def test_remote_deploy_script_forwards_the_dirty_flag(source_repo: Path, tmp_path: Path):
    """PERMITTING arm of the remote gate: --dirty must reach the remote too."""
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    capture = tmp_path / "remote_script.sh"
    shim = shim_dir / "ssh"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        'cmd="${@: -1}"\n'
        'if [ "$cmd" = "echo ok" ] || [ "$cmd" = "true" ]; then exit 0; fi\n'
        'printf "%s" "$cmd" > "$SSH_CAPTURE"\n'
    )
    shim.chmod(0o755)

    env = {
        "PATH": f"{shim_dir}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(source_repo / "fake-home"),
        "REMOTE_HOST": "unused.invalid",
        "REMOTE_REPOS": "somerepo",
        "SSH_CAPTURE": str(capture),
    }
    subprocess.run(
        ["bash", str(source_repo / "scripts" / "deploy-all.sh"), "--remote", "--skip-validate"],
        capture_output=True,
        text=True,
        cwd=str(source_repo),
        env=env,
        timeout=120,
    )
    without = capture.read_text()

    subprocess.run(
        [
            "bash",
            str(source_repo / "scripts" / "deploy-all.sh"),
            "--remote",
            "--skip-validate",
            "--dirty",
        ],
        capture_output=True,
        text=True,
        cwd=str(source_repo),
        env=env,
        timeout=120,
    )
    with_dirty = capture.read_text()

    assert "--dirty" not in without, "default remote deploy must NOT ship uncommitted work"
    assert "--dirty" in with_dirty, "the explicit opt-in must reach the remote gate"


# --------------------------------------------------------------------------
# 17. End-to-end through the real script (dry-run, no ssh, no writes)
# --------------------------------------------------------------------------


def _run_deploy_all(source_repo: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(source_repo / "scripts" / "deploy-all.sh"), "--local", "--dry-run", *flags],
        capture_output=True,
        text=True,
        cwd=str(source_repo),
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(source_repo / "fake-home"),
            "REMOTE_HOST": "unused.invalid",
            "LOCAL_REPOS": "nonexistent-repo",
            "REMOTE_REPOS": "nonexistent-repo",
        },
        timeout=120,
    )


def test_deploy_all_sh_refuses_dirty_tree_end_to_end(source_repo: Path):
    (source_repo / "plugins" / "autonomous-dev" / "lib" / "hook_safety.py").write_text(
        "# uncommitted\n"
    )
    result = _run_deploy_all(source_repo)
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "lib/hook_safety.py" in combined, combined
    assert "[dry-run] Would deploy" not in combined, "must refuse BEFORE deploying"


def test_deploy_all_sh_permits_dirty_tree_with_flag_end_to_end(source_repo: Path):
    (source_repo / "plugins" / "autonomous-dev" / "lib" / "hook_safety.py").write_text(
        "# uncommitted\n"
    )
    result = _run_deploy_all(source_repo, "--dirty")
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "lib/hook_safety.py" in combined, "must name what it is shipping uncommitted"


def test_deploy_all_sh_permits_clean_tree_end_to_end(source_repo: Path):
    result = _run_deploy_all(source_repo)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "[dry-run]" in combined


def test_a_missing_gate_is_detectable_from_the_output(source_repo: Path):
    """NEGATIVE CONTROL for the ``--dirty`` guard assertions in the other suites.

    ``tests/integration/scripts/test_deploy_all_global_settings.py`` and
    ``tests/spec_validation/test_spec_issue995_project_local_hooks.py`` inject
    ``--dirty`` into every deploy they run, and assert in their shared helper
    that ``DEPLOY-GATE`` appeared and did not say REFUSED. That assertion is
    only worth something if a MISSING gate actually changes the output — a
    probe that cannot fail cannot inform. This deletes the gate and proves the
    marker disappears.
    """
    (source_repo / "plugins" / "autonomous-dev" / "scripts" / "deploy_state.py").unlink()
    result = _run_deploy_all(source_repo, "--dirty")
    combined = result.stdout + result.stderr

    assert "DEPLOY-GATE" not in combined, (
        "the guard assertion in the other suites is vacuous: the marker appears "
        f"even with the gate deleted:\n{combined}"
    )
    assert "deploy_state.py missing" in combined, (
        "a missing gate must announce itself, not vanish silently:\n" + combined
    )


def test_deploy_all_sh_help_is_not_truncated(source_repo: Path):
    """The --help block must list every flag, including the last one added."""
    result = subprocess.run(
        ["bash", str(source_repo / "scripts" / "deploy-all.sh"), "--help"],
        capture_output=True,
        text=True,
        cwd=str(source_repo),
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    for flag in ("--local", "--remote", "--dry-run", "--skip-validate", "--dirty"):
        assert flag in result.stdout, f"--help omits {flag}:\n{result.stdout}"


# --------------------------------------------------------------------------
# 18. BLOCKING A — a target-only file present AT STAMP TIME is not legitimate
# --------------------------------------------------------------------------


def test_a_stray_already_in_the_target_at_stamp_time_is_recorded_not_adopted(
    source_repo: Path, consumer: Path, capsys
):
    """BLOCKING A: ``executing - recorded`` is empty BY CONSTRUCTION for this shape.

    ``check``'s reverse comparison (BLOCKING 4) catches a file INJECTED after
    the stamp. It cannot catch one PRESENT at the stamp: ``digest_tree`` walks
    the target and records whatever it finds, so the stray is adopted into
    ``recorded`` and ``executing - recorded`` is empty. Before this fix the run
    below printed ``stamped 1 target(s) ... (clean)`` and ``OK — 3 files match
    the deploy record``, exit 0.

    Live on the two transports that do not delete — ``deploy_global`` (rsync
    without ``--delete``) and the remote copy. Remote targets have never been
    stamped, so the first remote stamp adopts whatever has accumulated. The
    instance this reproduces exists on this machine now:
    ``~/.claude/hooks/.claude/logs/activity/2026-06-06.jsonl``, 52,502 bytes, in
    no commit, matching no exclusion glob.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")

    stray = consumer / ".claude" / "lib" / ".claude" / "logs" / "activity" / "2026-06-06.jsonl"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text('{"leftover": true}\n')
    rel = "lib/.claude/logs/activity/2026-06-06.jsonl"

    # INSTRUMENT CHECK: the stray must be in the measured set for this to mean
    # anything. If a future exclusion hides it, this test would pass vacuously.
    assert not deploy_state.is_excluded(Path(rel)), (
        "fixture is vacuous: the stray matches an exclusion, so nothing measures it"
    )

    assert _stamp(source_repo, consumer) == 0
    state = _read_state(consumer)

    assert state["target_only"] == [rel], (
        f"a file no source accounts for must be named, not adopted; got {state}"
    )
    assert state["dirty"] is True, "target-only content must fail CLOSED like unmatched does"

    code, out = _check(consumer, capsys)
    assert code == 1, f"check must be non-zero for an unaccounted-for file; got:\n{out}"
    assert rel in out, f"check must NAME the stray; got:\n{out}"


def test_a_clean_target_reports_no_target_only_files(source_repo: Path, consumer: Path, capsys):
    """PERMITTING half of BLOCKING A. A tree the source fully accounts for is clean.

    Without this, the new arm could be satisfied by marking every tree dirty —
    the cry-wolf failure. Deliberately includes the two shapes most likely to
    trip a naive ``set(digests) - expected``: a symlink, and a nested subdir.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    nested = plugin / "lib" / "nested" / "deeper"
    nested.mkdir(parents=True)
    (nested / "mod.py").write_text("# real source, deeply nested\n")
    os.symlink("hook_safety.py", plugin / "lib" / "alias.py")
    # Commit them: this test is about target_only, and leaving them uncommitted
    # would make `check` non-zero for an unrelated (correct) reason.
    _git(source_repo, "add", "-A")
    _git(source_repo, "commit", "-q", "-m", "add nested source and an alias")

    _fake_deploy(plugin, consumer / ".claude")
    assert _stamp(source_repo, consumer) == 0

    state = _read_state(consumer)
    assert state["target_only"] == [], (
        f"every deployed file came from the source; got {state['target_only']}"
    )
    assert "lib/nested/deeper/mod.py" in state["digests"]
    assert "lib/alias.py" in state["digests"]

    code, out = _check(consumer, capsys)
    assert code == 0, f"a fully-accounted-for tree must stay quiet; got:\n{out}"
    assert "ALREADY in the target" not in out


def test_target_only_ignores_subdirs_this_target_never_receives(tmp_path: Path):
    """Scoping control: the global target receives three subdirs, not eight.

    ``expected`` covers all eight, so an unscoped comparison is still correct in
    this direction — but scoping is what makes the assertion meaningful rather
    than accidental, so it is pinned.
    """
    target = tmp_path / "global"
    (target / "lib").mkdir(parents=True)

    digests = {"lib/known.py": "a" * 64, "lib/stray.py": "b" * 64}
    expected = {"lib/known.py", "commands/never-here.md", "agents/never-here.md"}

    assert deploy_state.target_only_files(digests, expected, target) == ["lib/stray.py"]


def test_deploy_activity_row_carries_target_only(source_repo: Path, consumer: Path):
    """A finding that is not in the correlatable sink is a finding nobody reads."""
    plugin = source_repo / "plugins" / "autonomous-dev"
    _fake_deploy(plugin, consumer / ".claude")
    stray = consumer / ".claude" / "lib" / "orphan.py"
    stray.write_text("# no source accounts for this\n")

    deploy_state.main(
        [
            "stamp",
            "--source",
            str(source_repo),
            "--plugin-src",
            str(plugin),
            "--target",
            str(consumer / ".claude"),
            "--log-activity",
        ]
    )

    logs = sorted((source_repo / ".claude" / "logs" / "activity").glob("*.jsonl"))
    rows = [json.loads(line) for line in logs[-1].read_text().splitlines() if line.strip()]
    deploys = [r for r in rows if r.get("type") == "deploy"]
    assert deploys[0]["target_only"] == ["lib/orphan.py"]
    assert deploys[0]["dirty"] is True


# --------------------------------------------------------------------------
# 19. BLOCKING B — the remote path must ship exactly what the remote gate measures
# --------------------------------------------------------------------------


def _capture_remote_script(source_repo: Path, tmp_path: Path, *flags: str) -> str:
    """Run deploy-all.sh --remote with ssh shimmed and return the remote script."""
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir(exist_ok=True)
    capture = tmp_path / "remote_script.sh"
    shim = shim_dir / "ssh"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        'cmd="${@: -1}"\n'
        'if [ "$cmd" = "echo ok" ] || [ "$cmd" = "true" ]; then exit 0; fi\n'
        'printf "%s" "$cmd" > "$SSH_CAPTURE"\n'
    )
    shim.chmod(0o755)
    subprocess.run(
        ["bash", str(source_repo / "scripts" / "deploy-all.sh"), "--remote", "--skip-validate",
         *flags],
        capture_output=True,
        text=True,
        cwd=str(source_repo),
        env={
            "PATH": f"{shim_dir}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(source_repo / "fake-home"),
            "REMOTE_HOST": "unused.invalid",
            "REMOTE_REPOS": "somerepo",
            "SSH_CAPTURE": str(capture),
        },
        timeout=120,
    )
    assert capture.is_file(), "ssh shim captured nothing"
    return capture.read_text()


def _extract_prune_sync_preamble(remote_script: str) -> str:
    """The exclusion array and prune_sync() AS GENERATED, ready to source.

    Deliberately taken from the CAPTURED remote script rather than from
    ``scripts/lib/prune_sync.sh``: the file is what was written, the captured
    text is what will execute. Between them sit heredoc expansion, backslash
    escaping and command substitution — a dropped backslash on ``\\$target``
    expands LOCALLY to empty and hands rsync an empty destination under
    ``--delete``, and no test that reads the source file can see it.
    """
    array = re.search(r"^remote_excludes_arr=\(.*?\)$", remote_script, re.M)
    assert array, (
        "the generated remote script has no remote_excludes_arr assignment, so "
        "prune_sync would run with no exclusions:\n" + remote_script[:2000]
    )
    func = re.search(r"^prune_sync\(\) \{.*?^\}$", remote_script, re.M | re.S)
    assert func, (
        "prune_sync() is not defined in the generated remote script:\n"
        + remote_script[:2000]
    )
    return array.group(0) + "\n" + func.group(0) + "\n"


def test_remote_copy_carries_the_same_exclusions_the_remote_gate_measures(
    source_repo: Path, tmp_path: Path
):
    """BLOCKING B, on the generated remote script itself.

    The remote copies now route through prune_sync(), which takes the shared
    patterns as an ARRAY rather than repeating them on each rsync line. The
    property is unchanged and asserted in two halves: every pattern the gate
    measures reaches the array, and every rsync invocation passes the array on.
    Checking only the array would leave an rsync that quietly stopped using it.
    """
    remote_script = _capture_remote_script(source_repo, tmp_path)

    assert "cp -rf plugins/autonomous-dev" not in remote_script, (
        "the remote still copies with a tool that cannot exclude anything:\n"
        + remote_script
    )

    array_line = re.search(r"^remote_excludes_arr=\(.*?\)$", remote_script, re.M)
    assert array_line, "the generated remote script builds no exclusion array"
    for pattern in deploy_state.rsync_exclude_patterns():
        assert f"--exclude='{pattern}'" in array_line.group(0), (
            f"the remote exclusion array omits {pattern!r}, so the remote ships "
            f"what the remote gate does not measure:\n{array_line.group(0)}"
        )

    copy_lines = [
        ln.strip()
        for ln in remote_script.splitlines()
        if re.match(COPY_INVOCATION_RE, ln.strip())
    ]
    assert len(copy_lines) >= 2, (
        f"expected the preview + live rsync pair inside prune_sync; got {copy_lines}"
    )
    for line in copy_lines:
        assert '"${remote_excludes_arr[@]}"' in line, (
            "a remote rsync invocation does not apply the shared exclusion "
            f"array:\n{line}"
        )


def test_remote_copy_delivers_exactly_the_measured_set(source_repo: Path, tmp_path: Path):
    """BEHAVIOURAL, both arms — the structural test above cannot prove delivery.

    Extracts the real per-repo copy line from the GENERATED remote script and
    runs it against a fixture tree. The refusing arm: none of the excluded
    classes arrive. The PERMITTING arm, which matters at least as much: the
    remote must still actually deploy the real files.
    """
    remote_script = _capture_remote_script(source_repo, tmp_path)
    preamble = _extract_prune_sync_preamble(remote_script)

    src = tmp_path / "plugins" / "autonomous-dev" / "templates"
    (src / "sub").mkdir(parents=True)
    (src / "__pycache__").mkdir(parents=True)
    (src / "docs" / "sessions").mkdir(parents=True)
    (src / "extensions").mkdir(parents=True)
    (src / "real.py").write_text("# real\n")
    (src / "sub" / "nested.py").write_text("# real, nested\n")
    (src / "real.py,cover").write_text("> annotation\n")
    (src / "__pycache__" / "real.cpython-314.pyc").write_bytes(b"\x00compiled")
    (src / ".DS_Store").write_bytes(b"\x00turd")
    (src / "docs" / "sessions" / "20260822-session.md").write_text("# session\n")
    (src / "extensions" / "consumer_local.py").write_text("# consumer-local\n")

    target = tmp_path / "remote-target"
    (target / "templates").mkdir(parents=True)

    runner = tmp_path / "run_copy.sh"
    runner.write_text(
        "set -euo pipefail\n"
        + preamble
        + f'prune_sync "plugins/autonomous-dev/templates/" "{target}/templates/" "probe/templates"\n'
    )
    result = subprocess.run(
        ["bash", str(runner)], capture_output=True, text=True, cwd=str(tmp_path), timeout=120
    )
    assert result.returncode == 0, result.stdout + result.stderr

    delivered = {
        p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()
    }

    # PERMITTING ARM: the remote must still deploy.
    assert "templates/real.py" in delivered, f"remote stopped deploying: {delivered}"
    assert "templates/sub/nested.py" in delivered, f"nested source dropped: {delivered}"

    # REFUSING ARM: every excluded class stays off the remote.
    for stray in (
        "templates/real.py,cover",
        "templates/__pycache__/real.cpython-314.pyc",
        "templates/.DS_Store",
        "templates/docs/sessions/20260822-session.md",
        "templates/extensions/consumer_local.py",
    ):
        assert stray not in delivered, (
            f"{stray} reached the remote target, unmeasured by the remote gate"
        )


def test_remote_aborts_rather_than_falling_back_to_an_unmeasurable_copy(
    source_repo: Path, tmp_path: Path
):
    """The absent-rsync arm is explicit, not silent.

    rsync 3.4.1 is present on the real remote (verified before choosing this
    transport), but a fallback to ``cp`` would silently reinstate the exact
    defect, so the script refuses instead. Driven by running the generated
    remote script's guard with rsync removed from PATH.
    """
    remote_script = _capture_remote_script(source_repo, tmp_path)
    assert "command -v rsync" in remote_script, "the remote must check its transport"

    lines = remote_script.splitlines()
    start = next(i for i, ln in enumerate(lines) if "command -v rsync" in ln)
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "fi")
    guard = tmp_path / "guard.sh"
    guard.write_text("\n".join(lines[start : end + 1]) + "\necho REACHED_COPY\n")

    # An EMPTY PATH is the point: `command -v` is a shell builtin, so the guard
    # still runs, but rsync is unreachable. bash is invoked by absolute path
    # precisely because PATH cannot be used to find it.
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()
    result = subprocess.run(
        ["/bin/bash", str(guard)],
        capture_output=True,
        text=True,
        env={"PATH": str(empty_bin)},
        timeout=60,
    )
    assert result.returncode == 1, (
        f"a remote with no rsync must ABORT, not fall through:\n{result.stdout}"
    )
    assert "REACHED_COPY" not in result.stdout
    assert "REMOTE ABORT" in result.stdout

    # PERMITTING CONTROL: with rsync on PATH the guard falls through.
    ok = subprocess.run(
        ["/bin/bash", str(guard)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
        timeout=60,
    )
    assert ok.returncode == 0 and "REACHED_COPY" in ok.stdout, (
        f"instrument check failed: the guard blocks even WITH rsync:\n{ok.stdout}{ok.stderr}"
    )


# --------------------------------------------------------------------------
# 20. BLOCKING C — bytecode is the excluded class that needs no registration
# --------------------------------------------------------------------------


def test_a_planted_pyc_shadows_an_untouched_source_file_and_check_cannot_see_it(
    tmp_path: Path,
):
    """POSITIVE CONTROL for the purge: prove the vector is real before fixing it.

    Forges the 16-byte header of a tampered ``.pyc`` to match an UNTOUCHED
    ``.py``. The interpreter loads the cache; the tool's digest of the ``.py``
    genuinely matches; ``check`` exits 0 over a subverted module.

    This test asserts the EXPLOIT still works in a bare directory — it is the
    instrument that makes the purge test below meaningful. If it ever goes red,
    CPython changed its cache validation and the purge rationale must be
    re-derived rather than assumed.
    """
    lib = tmp_path / "lib"
    lib.mkdir()
    victim = lib / "victim.py"
    victim.write_text('def guard():\n    return "ALLOW-ONLY-SAFE"\n')

    # Let the interpreter build a legitimate cache, then overwrite the code
    # object while keeping the validation header byte-identical.
    subprocess.run(
        [sys.executable, "-c", "import victim"], cwd=str(lib), check=True, capture_output=True
    )
    cached = next((lib / "__pycache__").glob("victim.*.pyc"))
    header = cached.read_bytes()[:16]

    import importlib.util
    import marshal

    evil = compile(
        'def guard():\n    return "PWNED-ALLOW-EVERYTHING"\n', "victim.py", "exec"
    )
    cached.write_bytes(header + marshal.dumps(evil))
    assert importlib.util.MAGIC_NUMBER == header[:4], "fixture built a stale magic"

    assert victim.read_text() == 'def guard():\n    return "ALLOW-ONLY-SAFE"\n', (
        "the source on disk must be untouched — that is the whole point"
    )
    result = subprocess.run(
        [sys.executable, "-c", "import victim; print(victim.guard())"],
        cwd=str(lib),
        capture_output=True,
        text=True,
    )
    assert "PWNED-ALLOW-EVERYTHING" in result.stdout, (
        f"the shadowing vector did not reproduce: {result.stdout}{result.stderr}"
    )


def test_deploy_purges_bytecode_from_every_deployed_subdir(tmp_path: Path):
    """Both arms of the purge, driven through deploy-all.sh's own function.

    REFUSING: a planted ``__pycache__`` entry AND a bare sourceless ``.pyc``
    (importable in its own right) are both gone after a deploy.
    PERMITTING: real source, and consumer-local ``extensions/`` that Issue #560
    exists to preserve, are untouched.
    """
    target = tmp_path / ".claude"
    for sub in ("hooks", "lib"):
        (target / sub / "__pycache__").mkdir(parents=True)
        (target / sub / "__pycache__" / "mod.cpython-314.pyc").write_bytes(b"\x00evil")
        (target / sub / "real.py").write_text("# real\n")
    (target / "lib" / "sourceless.pyc").write_bytes(b"\x00importable-on-its-own")
    (target / "hooks" / "extensions").mkdir(parents=True)
    (target / "hooks" / "extensions" / "consumer_local.py").write_text("# keep me\n")
    (target / "hooks" / "extensions" / "__pycache__").mkdir()
    keeper = target / "hooks" / "extensions" / "__pycache__" / "local.cpython-314.pyc"
    keeper.write_bytes(b"\x00consumer-local")

    runner = tmp_path / "purge.sh"
    runner.write_text(
        "set -euo pipefail\n"
        f'SUBDIRS="{" ".join(deploy_state.DEPLOY_SUBDIRS)}"\n'
        + _extract_shell_function("purge_bytecode")
        + f'\npurge_bytecode "{target}"\n'
    )
    result = subprocess.run(["bash", str(runner)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr

    # REFUSING ARM
    assert not (target / "lib" / "__pycache__").exists(), "cache dir survived the purge"
    assert not (target / "hooks" / "__pycache__").exists(), "cache dir survived the purge"
    assert not (target / "lib" / "sourceless.pyc").exists(), (
        "a bare sourceless .pyc is importable on its own and must go too"
    )

    # PERMITTING ARM
    assert (target / "lib" / "real.py").is_file(), "the purge ate real source"
    assert (target / "hooks" / "real.py").is_file(), "the purge ate real source"
    assert keeper.is_file(), (
        "extensions/ is consumer-local state Issue #560 exists to preserve"
    )


def test_both_deploy_paths_purge_bytecode_after_copying():
    """Wiring: the purge must run on EVERY transport, not just the one tested."""
    text = DEPLOY_ALL_SH.read_text()
    assert text.count("purge_bytecode ") >= 2, (
        "purge_bytecode must run for both the global and the per-repo local deploy"
    )
    # The remote heredoc cannot call a local shell function, so it inlines the
    # same find; assert the remote carries it rather than assuming parity.
    remote_block = text[text.index("deploy_remote()") : text.index("validate_local()")]
    assert remote_block.count("-name '__pycache__' -type d") >= 2, (
        "the remote path must purge bytecode for per-repo AND global targets"
    )


# --------------------------------------------------------------------------
# 21. The exclusion list is measured, not asserted
# --------------------------------------------------------------------------


def test_exactly_one_tracked_file_is_hidden_by_the_exclusions():
    """The claim in the artifact must be enforced, not written down.

    Both validators measured 1; the report to them said 0, because the
    measurement reimplemented the predicate with ``fnmatch`` instead of calling
    ``is_excluded()`` — ``extensions/`` carries a trailing slash and does not
    fnmatch a bare path component. This calls the REAL predicate over
    ``git ls-files``, so adding a pattern that starts hiding a tracked file
    fails here instead of relying on someone re-counting by hand.
    """
    allowlist = {"hooks/extensions/.gitkeep"}

    raw = subprocess.run(
        ["git", "ls-files", "-z", "--"]
        + [f"plugins/autonomous-dev/{s}" for s in deploy_state.DEPLOY_SUBDIRS],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    prefix = "plugins/autonomous-dev/"
    tracked = [e[len(prefix) :] for e in raw.split("\0") if e.startswith(prefix)]

    # INSTRUMENT CHECK: an empty tracked set would make the assertion vacuous.
    assert len(tracked) > 100, f"git ls-files returned {len(tracked)} paths; probe is broken"

    excluded = {rel for rel in tracked if deploy_state.is_excluded(Path(rel))}
    assert excluded == allowlist, (
        "the set of TRACKED files hidden by DEPLOY_EXCLUDES changed.\n"
        f"  newly hidden: {sorted(excluded - allowlist)}\n"
        f"  no longer hidden: {sorted(allowlist - excluded)}\n"
        "Anything hidden here is invisible to the digest map AND to check's "
        "reverse comparison, in both directions."
    )


def test_the_artifact_does_not_claim_zero_source_files_are_excluded():
    """The false claim shipped in the artifact; the correction must ship too."""
    text = DEPLOY_STATE_SRC.read_text()
    assert "zero source files are excluded" not in text
    assert "no source file is excluded" not in text
    assert "hooks/extensions/.gitkeep" in text, (
        "the artifact must NAME the one excluded tracked file and why"
    )


def test_session_exclusion_is_a_path_not_a_filename_class(source_repo: Path):
    """Narrowing: an attacker-named file must no longer ride the exclusion in.

    REFUSING arm of the narrowing is the SCOPING control below; this is the arm
    that matters for measurement — a file named like a session log but living
    anywhere else is now in the deployed set, and therefore measured.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    (plugin / "hooks" / "payload-session.md").write_text("# not a session log\n")
    (plugin / "lib" / "run-pipeline.json").write_text("{}\n")

    shipped = deploy_state.source_deployed_files(plugin)
    assert "hooks/payload-session.md" in shipped, (
        "a filename class let an attacker-named file into the executing tree "
        "unmeasured; the exclusion is now scoped to docs/sessions/"
    )
    assert "lib/run-pipeline.json" in shipped


def test_the_real_session_log_path_is_still_excluded(source_repo: Path):
    """PERMITTING half of the narrowing: the recurring machine-generated class stays out.

    Several hooks write to the RELATIVE path ``Path("docs/sessions")``, so a hook
    run with cwd=<plugin>/hooks creates these. If they came back into the
    deployed set the gate would go permanently red on any machine that has run
    a hook — the cry-wolf failure.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    sessions = plugin / "hooks" / "docs" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "20260822-132224-session.md").write_text("# Session\n")
    (sessions / "abc123-pipeline.json").write_text("{}\n")

    shipped = deploy_state.source_deployed_files(plugin)
    assert not any("docs/sessions" in rel for rel in shipped), (
        f"docs/sessions/ must stay out of the deployed set; got {sorted(shipped)}"
    )
    # SCOPING CONTROL: excluding docs/ wholesale would drop tracked skills docs.
    skill_docs = plugin / "skills" / "x" / "docs"
    skill_docs.mkdir(parents=True)
    (skill_docs / "reference.md").write_text("# real doc\n")
    assert "skills/x/docs/reference.md" in deploy_state.source_deployed_files(plugin)


# --------------------------------------------------------------------------
# 22. The record is untrusted input — including the two fields check TRUSTED
# --------------------------------------------------------------------------


def test_self_heal_refuses_a_source_repo_that_is_not_a_git_toplevel(
    consumer: Path, tmp_path: Path, capsys
):
    """``check`` policed the digest keys and trusted the cwd it ran git in.

    ``source_repo`` and ``source_plugin_rel`` come from the same gitignored,
    unreviewed record that ``unsafe_digest_keys`` exists to sanitise, and the
    self-heal feeds the first to git as a subprocess cwd.
    """
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    _git(outer, "init", "-q")
    _git(outer, "config", "user.email", "t@e.com")
    _git(outer, "config", "user.name", "t")
    (outer / "f.txt").write_text("x\n")
    _git(outer, "add", "-A")
    _git(outer, "commit", "-q", "-m", "init")
    (inner / ".git").mkdir()  # looks like a checkout, is not a toplevel

    lib = consumer / ".claude" / "lib"
    lib.mkdir(parents=True)
    (lib / "x.py").write_text("hello\n")
    _write_state(
        consumer,
        {
            "source_commit_short": "abc123",
            "source_repo": str(inner),
            "source_plugin_rel": "plugins/autonomous-dev",
            "uncommitted_files": ["lib/x.py"],
            "digests": {"lib/x.py": hashlib.sha256(b"hello\n").hexdigest()},
        },
    )

    code, out = _check(consumer, capsys)
    assert code == 1, out
    assert "not a git toplevel" in out, f"the refusal must be visible, not silent:\n{out}"
    assert "lib/x.py" in out, "refusing to self-heal must fail CLOSED (still reported)"


def test_self_heal_refuses_a_traversing_plugin_rel(consumer: Path, tmp_path: Path, capsys):
    """A DIFFERENT shape: the rel is interpolated into a ``HEAD:<rel>/<file>`` rev."""
    lib = consumer / ".claude" / "lib"
    lib.mkdir(parents=True)
    (lib / "x.py").write_text("hello\n")
    _write_state(
        consumer,
        {
            "source_commit_short": "abc123",
            "source_repo": str(tmp_path),
            "source_plugin_rel": "../../../etc",
            "uncommitted_files": ["lib/x.py"],
            "digests": {"lib/x.py": hashlib.sha256(b"hello\n").hexdigest()},
        },
    )

    code, out = _check(consumer, capsys)
    assert code == 1, out
    assert "escapes the repo" in out, f"must name WHY it refused; got:\n{out}"


def test_self_heal_still_runs_for_a_legitimate_record(
    source_repo: Path, consumer: Path, capsys
):
    """PERMITTING control: hardening must not disable the self-heal it guards.

    Without this, the two tests above are satisfied by refusing everything.
    """
    plugin = source_repo / "plugins" / "autonomous-dev"
    (plugin / "lib" / "hook_safety.py").write_text("# 684-line intermediate\n")
    _fake_deploy(plugin, consumer / ".claude")
    _stamp(source_repo, consumer, dirty=True)
    assert _check(consumer, capsys)[0] == 1

    _git(source_repo, "add", "-A")
    _git(source_repo, "commit", "-q", "-m", "commit it")

    code, out = _check(consumer, capsys)
    assert code == 0, f"a trustworthy record must still self-heal:\n{out}"
    assert "since committed" in out
    assert "not re-verifying" not in out, "a legitimate record must not be refused"


def test_check_reports_a_recorded_symlink_that_escapes_the_deployed_tree(
    consumer: Path, tmp_path: Path, capsys
):
    """The record is HONEST here and still governs nothing.

    ``symlink:<target>`` matches, so drift detection passes, but the pointee is
    never digested. Latent — zero symlinks exist under any deployed subdir today
    — so this is reported rather than treated as tampering.
    """
    lib = consumer / ".claude" / "lib"
    lib.mkdir(parents=True)
    outside = tmp_path / "ungoverned.py"
    outside.write_text("# nothing digests this\n")
    os.symlink(outside, lib / "escapee.py")

    _write_state(
        consumer,
        {"source_commit_short": "abc123", "digests": {"lib/escapee.py": f"symlink:{outside}"}},
    )

    code, out = _check(consumer, capsys)
    assert code == 1, f"an escaping recorded symlink must be a finding; got:\n{out}"
    assert "lib/escapee.py" in out
    assert "OUTSIDE the deployed tree" in out


def test_a_symlink_inside_the_deployed_tree_is_not_reported(consumer: Path, capsys):
    """PERMITTING control: an in-tree symlink is fully governed and must stay quiet."""
    lib = consumer / ".claude" / "lib"
    lib.mkdir(parents=True)
    (lib / "real.py").write_text("# governed\n")
    os.symlink("real.py", lib / "alias.py")

    _write_state(
        consumer,
        {
            "source_commit_short": "abc123",
            "digests": {
                "lib/real.py": hashlib.sha256(b"# governed\n").hexdigest(),
                "lib/alias.py": "symlink:real.py",
            },
        },
    )

    code, out = _check(consumer, capsys)
    assert code == 0, f"an in-tree symlink is governed and must not fire:\n{out}"


# --------------------------------------------------------------------------
# 23. Ordering — a remote refusal must not cancel local post-deploy validation
# --------------------------------------------------------------------------


def test_a_remote_failure_still_lets_local_validation_run(source_repo: Path):
    """A remote-side problem left a COMPLETED local deploy unvalidated.

    The remote gate refusal exits the heredoc with 1, so ``ssh`` returns 1, so
    under ``set -euo pipefail`` the script died before step 4. The refusal keeps
    its teeth (non-zero exit, counted in ERRORS); it just stops taking the local
    validation down with it.
    """
    text = DEPLOY_ALL_SH.read_text()
    remote_call = text.index("    deploy_remote || REMOTE_FAILED=true")
    validation = text.index("=== Post-deploy validation ===")
    assert remote_call < validation, "step 3 must still precede step 4"
    assert "$REMOTE_FAILED; then" in text and "exit 1" in text[validation:], (
        "a remote failure must still fail the command at the end"
    )


# --------------------------------------------------------------------------
# 24. The global target is the one LOCAL transport that never deleted
#
# ``7c3a527e`` deleted five lib modules. ``bash scripts/deploy-all.sh`` printed
# ALL VALIDATIONS PASSED and all five survived in ``~/.claude/lib/``: the
# per-repo transport (:281) carries ``--delete``, ``deploy_global`` (:241) did
# not. ``sys.path`` falls back to ``~/.claude/lib``, so
# ``import workflow_tracker`` still resolved a module present in no source tree
# and in no consumer repo. ``deploy_state.py:608-609`` already recorded the
# cause in prose; #1610 built the detector and chose to REPORT. This closes the
# refusing half, for the LOCAL global target only. The remote global target
# (:490) keeps the identical defect deliberately (:391-394) and is a follow-up.
#
# NOVELTY, stated rather than assumed. The tests below are the first in this
# suite that run the real ``deploy-all.sh`` all the way into ``deploy_global()``
# and let it WRITE to a filesystem. (Two earlier invocations here are already
# non-dry-run --- ``_capture_remote_script`` and
# ``test_remote_deploy_script_gates_and_stamps`` --- but they pass ``--remote``,
# which sets ``DO_GLOBAL=false`` and ``DO_LOCAL=false``, and their ``ssh`` is
# shimmed, so nothing is ever written locally. Every OTHER invocation of the
# script in the suite passes ``--dry-run``.) What bounds the risk here:
#
#   * ``HOME`` is overridden to a pytest ``tmp_path`` subdirectory, and
#     ``_assert_sandboxed_home`` refuses to run if it resolves to the real one.
#   * ``deploy_global`` writes only under ``$GLOBAL_DEST/$subdir/`` where
#     ``GLOBAL_DEST="$HOME/.claude"``.
#   * ``LOCAL_REPOS`` names a repo that does not exist, so ``deploy_repo``
#     prints SKIP and touches nothing; ``--local`` disables the remote path.
#
# Every assertion below is on a FILESYSTEM EFFECT. The one structural test is
# marked as such and says why it could not have caught this bug.
# --------------------------------------------------------------------------


def _assert_sandboxed_home(home: Path) -> None:
    """Refuse to run a destructive deploy against anything but a sandbox.

    A test that escapes into the real ``$HOME`` is worse than the bug it is
    chasing, so this is checked before every invocation rather than trusted.
    """
    real_home = Path(os.path.expanduser("~")).resolve()
    resolved = home.resolve()
    assert resolved != real_home, f"refusing to deploy into the real HOME: {resolved}"
    assert real_home not in resolved.parents, (
        f"sandbox HOME must not live under the real HOME: {resolved}"
    )


def _run_global_deploy(
    source_repo: Path, home: Path, *flags: str
) -> subprocess.CompletedProcess:
    """Run the REAL deploy-all.sh so that only ``deploy_global()`` does work."""
    _assert_sandboxed_home(home)
    home.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            "bash",
            str(source_repo / "scripts" / "deploy-all.sh"),
            "--local",
            "--skip-validate",
            *flags,
        ],
        capture_output=True,
        text=True,
        cwd=str(source_repo),
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(home),
            # A repo name that cannot exist, so deploy_repo() SKIPs instead of
            # writing. Empty would NOT work: the script uses
            # ``${LOCAL_REPOS:-...}`` and an empty value falls back to the five
            # real repo names under $HOME/Dev.
            "LOCAL_REPOS": "no-such-repo-for-this-test",
            "REMOTE_REPOS": "no-such-repo-for-this-test",
            # Set so the top-of-script auto-detection never shells out to ssh.
            "REMOTE_HOST": "unused.invalid",
        },
        timeout=180,
    )


TELEMETRY_REL = "hooks/.claude/logs/activity/2026-06-06.jsonl"
TELEMETRY_BYTES = b'{"event":"held in no commit","bytes":"load-bearing"}\n'


def _plant_global_target(home: Path) -> None:
    """Populate the sandbox ~/.claude with the four shapes that matter."""
    claude = home / ".claude"

    # (a) The defect: a module deleted from source that survived in the target.
    orphan = claude / "lib" / "workflow_tracker.py"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("# deleted from source by 7c3a527e, still importable\n")

    # (b) Issue #560 consumer-local state.
    ext = claude / "hooks" / "extensions" / "consumer_local.py"
    ext.parent.mkdir(parents=True, exist_ok=True)
    ext.write_text("# consumer-local extension\n")

    # (c) Runtime state a hook wrote relative to its own cwd. 52,502 bytes of
    #     exactly this shape exists on this machine now, in no commit.
    telemetry = claude / TELEMETRY_REL
    telemetry.parent.mkdir(parents=True, exist_ok=True)
    telemetry.write_bytes(TELEMETRY_BYTES)

    # (d) The same class, nested DEEPER than the shape that prompted the
    #     exclusion --- the pattern must cover the class, not the instance.
    deep = claude / "lib" / "nested" / ".claude" / "logs" / "deep.jsonl"
    deep.parent.mkdir(parents=True, exist_ok=True)
    deep.write_bytes(b'{"depth":"two levels down"}\n')


def test_global_deploy_prunes_a_module_deleted_from_source(source_repo: Path, tmp_path: Path):
    """REFUSING arm. This is the assertion that would have caught the bug.

    Fails against 12b47f3b: without ``--delete`` the orphan survives, exactly as
    ``workflow_tracker.py`` did in ``~/.claude/lib`` after ``7c3a527e``.
    """
    home = tmp_path / "sandbox-home"
    _plant_global_target(home)
    orphan = home / ".claude" / "lib" / "workflow_tracker.py"
    assert orphan.is_file(), "fixture did not plant the orphan"

    result = _run_global_deploy(source_repo, home)
    assert result.returncode == 0, result.stdout + result.stderr

    assert not orphan.exists(), (
        "a module absent from the source still executes from the global target; "
        "sys.path falls back to ~/.claude/lib, so `import workflow_tracker` "
        f"resolves a file no commit contains.\n{result.stdout}{result.stderr}"
    )


def test_global_deploy_still_delivers_real_source_files(source_repo: Path, tmp_path: Path):
    """PERMITTING arm. Without it, the test above is satisfied by deleting all.

    Compares BYTES, not existence: a truncated or stale copy is a deploy that
    reports success and ships nothing.
    """
    home = tmp_path / "sandbox-home"
    _plant_global_target(home)

    result = _run_global_deploy(source_repo, home)
    assert result.returncode == 0, result.stdout + result.stderr

    plugin = source_repo / "plugins" / "autonomous-dev"
    for rel in ("lib/hook_safety.py", "hooks/unified_pre_tool.py"):
        deployed = home / ".claude" / rel
        assert deployed.is_file(), f"{rel} was not delivered:\n{result.stdout}"
        assert deployed.read_bytes() == (plugin / rel).read_bytes(), (
            f"{rel} in the global target does not match source bytes"
        )


def test_global_deploy_preserves_consumer_local_extensions(source_repo: Path, tmp_path: Path):
    """Issue #560 control: ``--delete`` must not take extensions/ with it."""
    home = tmp_path / "sandbox-home"
    _plant_global_target(home)
    ext = home / ".claude" / "hooks" / "extensions" / "consumer_local.py"

    result = _run_global_deploy(source_repo, home)
    assert result.returncode == 0, result.stdout + result.stderr

    assert ext.is_file(), (
        "adding --delete to the global transport re-opened Issue #560: "
        f"consumer-local extensions/ was pruned.\n{result.stdout}{result.stderr}"
    )


def test_global_deploy_preserves_nested_dot_claude_runtime_state(
    source_repo: Path, tmp_path: Path
):
    """Protection control, in a DIFFERENT shape from the bug that prompted it.

    The bug was a stale *source-shaped* file (``lib/workflow_tracker.py``). This
    is the opposite shape: runtime state a hook wrote into a ``.claude/``
    directory relative to its own cwd, which no source tree will ever account
    for. ``--exclude='.claude/'`` covers the CLASS --- the pattern has no
    internal slash, so rsync matches it against the final path component at ANY
    depth --- which is why the deeper plant is asserted too.

    ANTI-VACUOUS INSTRUMENT, two arms:
      1. the orphan planted in the SAME run must be gone, so survival here is
         protection rather than ``--delete`` simply not being active;
      2. the telemetry path must NOT match ``$DEPLOY_EXCLUDES``, so a future
         exclusion that hides it from ``target_only`` fails loudly instead of
         making this test pass by accident. That is the invariant this change
         preserves: deletion scope stays a strict subset of measurement scope.
    """
    assert not deploy_state.is_excluded(Path(TELEMETRY_REL)), (
        "this test is vacuous: the telemetry path now matches a DEPLOY_EXCLUDES "
        "pattern, so the provenance gate can no longer see it either"
    )

    home = tmp_path / "sandbox-home"
    _plant_global_target(home)
    telemetry = home / ".claude" / TELEMETRY_REL
    deep = home / ".claude" / "lib" / "nested" / ".claude" / "logs" / "deep.jsonl"

    result = _run_global_deploy(source_repo, home)
    assert result.returncode == 0, result.stdout + result.stderr

    assert not (home / ".claude" / "lib" / "workflow_tracker.py").exists(), (
        "instrument check failed: --delete did not run in this invocation, so "
        "the survival assertions below would prove nothing"
    )
    assert telemetry.is_file(), (
        "--delete destroyed hook-written telemetry held in no commit:\n"
        f"{result.stdout}{result.stderr}"
    )
    assert telemetry.read_bytes() == TELEMETRY_BYTES, "telemetry was rewritten, not preserved"
    assert deep.is_file(), (
        "the exclusion covers only the depth that prompted it, not the class"
    )


def test_global_deploy_refuses_an_empty_source_subdir(source_repo: Path, tmp_path: Path):
    """Pre-flight REFUSING arm --- the PRIMARY guard, ahead of ``--max-delete``.

    A misresolved or partially-checked-out source subdir plus ``--delete``
    empties the corresponding subtree inside ``$HOME``. ``--max-delete=50``
    does not cover this case: the real ``config/`` holds 16 regular files
    (measured 2026-09-05), well below the cap, so the breaker would let a full
    wipe of it through. That is why the pre-flight is primary and the breaker
    is second.
    """
    home = tmp_path / "sandbox-home"
    _plant_global_target(home)

    # A source subdir that EXISTS but holds no regular files. git does not
    # track empty directories, so the working tree stays clean and the
    # provenance gate still permits the run.
    empty_src = source_repo / "plugins" / "autonomous-dev" / "config" / "nested"
    empty_src.mkdir(parents=True)

    victim = home / ".claude" / "config" / "auto_approve_policy.json"
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_text('{"tools": {}}\n')

    result = _run_global_deploy(source_repo, home)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, f"an empty source subdir must REFUSE:\n{combined}"
    assert "REFUSED" in combined, f"the refusal must announce itself:\n{combined}"
    assert "config" in combined, f"the refusal must name the subdir:\n{combined}"
    assert victim.is_file(), (
        f"the refusal fired but the target was emptied anyway:\n{combined}"
    )


def test_global_rsync_line_carries_the_delete_flags_and_trailing_slashes():
    """Structural, IN ADDITION to the effect tests above and never instead.

    This check alone would have PASSED against the original bug: three of the
    four copy call sites already existed and merely lacked ``--delete``, and
    nothing here inspects a filesystem. Its one unique job is the trailing-slash
    convention on both operands --- load-bearing under ``--delete``, and a
    property the effect tests pass through silently because the fixture happens
    to have it right.
    """
    text = DEPLOY_ALL_SH.read_text()
    body = re.search(r"^deploy_global\(\) \{.*?^\}", text, re.M | re.S)
    assert body, "deploy_global() not found in deploy-all.sh"

    lines = [
        ln.strip()
        for ln in body.group(0).splitlines()
        if ln.strip().startswith("rsync ") and "$GLOBAL_DEST" in ln
    ]
    assert len(lines) == 1, f"expected exactly one global rsync call site; got {lines}"
    line = lines[0]

    for token in (
        "--delete",
        "--max-delete=",
        "--exclude=extensions/",
        "--exclude='.claude/'",
        '"${DEPLOY_EXCLUDES[@]}"',
    ):
        assert token in line, f"the global rsync is missing {token}:\n  {line}"

    operands = re.findall(r'"(\$PLUGIN_SRC/\$subdir/|\$GLOBAL_DEST/\$subdir/)"', line)
    assert len(operands) == 2, f"expected two path operands; got {operands} in:\n  {line}"
    for operand in operands:
        assert operand.endswith("/"), (
            "both operands must keep their trailing slash: without it on the "
            f"source, --delete syncs a nested copy and prunes everything else: {operand}"
        )


def _global_max_delete_cap() -> int:
    """Read ``--max-delete=N`` off the global rsync line, so the test can't drift.

    The number is read from ``deploy-all.sh`` rather than restated here: a test
    holding its own copy of the cap keeps passing after someone raises the flag
    and forgets the refusal message, which is the exact drift this pins.

    Returns:
        The cap in effect. Falls back to ``50`` when the flag is absent, which
        is the pre-fix state (``12b47f3b`` runs a bare ``rsync -a``). The test
        then plants 60 orphans against a script that deletes nothing, and the
        effect assertions carry the RED rather than this parse.
    """
    text = DEPLOY_ALL_SH.read_text()
    body = re.search(r"^deploy_global\(\) \{.*?^\}", text, re.M | re.S)
    assert body, "deploy_global() not found in deploy-all.sh"
    found = re.search(r"--max-delete=(\d+)", body.group(0))
    return int(found.group(1)) if found else 50


def test_global_deploy_refuses_a_wholesale_prune_without_rolling_back(
    source_repo: Path, tmp_path: Path
):
    """The ``--max-delete`` breaker, which until now had only ever run by hand.

    The pre-flight (above) covers an EMPTY source subdir. This covers the other
    direction: a source subdir that is populated and passes the pre-flight, but
    whose global target holds so much that no source accounts for that pruning
    it is a wipe rather than a deletion. Largest legitimate deletion evidenced
    in this repo is 5 files (``7c3a527e``); this plants twelve times that.

    THE PROPERTY THIS PINS, and the reason the test exists at all: **rsync does
    NOT roll back.** The breaker is not transactional. It stops the pruning and
    fails the run, but every file deleted before the cap was reached stays
    deleted. That is written in a comment at ``deploy-all.sh:307-308`` and
    nowhere executable, so a reader who assumes the refusal restored the target
    would be wrong and nothing would tell them. The assertions below say it:
    after the refusal, some orphans are GONE and some REMAIN, in the same
    subdir, from the same run.

    ANTI-VACUOUS INSTRUMENT, two arms --- same shape as the runtime-state test
    above, because "some orphans remain" is otherwise satisfied by a deploy
    that deleted nothing at all:
      1. an orphan planted in ``hooks/``, which ``$GLOBAL_SUBDIRS`` processes
         BEFORE ``lib/``, must be GONE. That subdir is 1 deletion, far under the
         cap, so it proves ``--delete`` engaged and completed in this same run;
      2. the planted names must NOT match ``$DEPLOY_EXCLUDES``, so a future
         exclusion cannot make them survive by protection and quietly convert
         the partial-deletion assertion into a tautology.
    """
    cap = _global_max_delete_cap()
    planted = cap + 10

    home = tmp_path / "sandbox-home"
    _plant_global_target(home)

    lib_target = home / ".claude" / "lib"
    lib_target.mkdir(parents=True, exist_ok=True)
    orphans = [lib_target / f"orphan_{i:03d}.py" for i in range(planted)]
    for orphan in orphans:
        orphan.write_text("# in the global target, in no source tree\n")

    # Instrument arm 2: prove the plants are visible to deletion, not protected.
    for rel in ("lib/orphan_000.py", "hooks/orphan_hook_deleted_from_source.py"):
        assert not deploy_state.is_excluded(Path(rel)), (
            f"this test is vacuous: {rel} now matches a DEPLOY_EXCLUDES pattern, "
            "so it would survive by protection rather than by the cap"
        )

    # Instrument arm 1: a witness in the subdir processed BEFORE the one that
    # refuses. hooks/ has exactly this one orphan, so it is nowhere near the cap.
    witness = home / ".claude" / "hooks" / "orphan_hook_deleted_from_source.py"
    witness.parent.mkdir(parents=True, exist_ok=True)
    witness.write_text("# deleted from source, still in the global hooks target\n")

    result = _run_global_deploy(source_repo, home)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        f"{planted} files in the global target that no source accounts for is a "
        f"wipe, not a deletion, and it was allowed through:\n{combined}"
    )
    assert "REFUSED" in combined, f"the refusal must announce itself:\n{combined}"

    # Scoped to the refusal LINE, not the whole stream. Measured 2026-09-05:
    # against 12b47f3b both "lib" and "50" appear in `combined` anyway, carried
    # by the DEPLOY-STATE report ("'lib/orphan_050.py' was ALREADY in the
    # target ..."). Asserted against the stream, these two would be true on a
    # run that refused nothing.
    refusal = next((ln for ln in combined.splitlines() if "REFUSED: pruning" in ln), "")
    assert refusal, f"the refusal must be a single legible line:\n{combined}"
    assert "lib" in refusal, f"the refusal must name the subdir it stopped:\n{refusal}"
    assert str(cap) in refusal, (
        f"the refusal must name the cap it hit ({cap}), or the reader cannot tell "
        f"how far over the line they were:\n{refusal}"
    )

    assert not witness.exists(), (
        "instrument check failed: --delete did not engage in this invocation, so "
        f"the survival counts below would prove nothing:\n{combined}"
    )

    survivors = [o for o in orphans if o.exists()]
    removed = planted - len(survivors)
    assert removed > 0, (
        f"the breaker looks transactional: all {planted} orphans survived. If "
        "rsync ever gains rollback this assertion is the place to record it "
        f"--- do not just delete it:\n{combined}"
    )
    assert survivors, (
        f"all {planted} orphans were pruned despite the cap of {cap}; the breaker "
        f"reported REFUSED but did not actually stop the deletion:\n{combined}"
    )
    assert removed <= cap, (
        f"the cap is {cap} but {removed} orphans were deleted; --max-delete is "
        f"not bounding the prune:\n{combined}"
    )


# --------------------------------------------------------------------------
# 19. The newly-armed transports: the guard, and the text that actually runs.
#
# Layering, deliberate and stated so a future reader does not collapse it:
#   STATIC (T2-T5, T6a)  deterministic assertions over script text. Cheap,
#                        but blind to everything heredoc expansion does.
#   PARSE  (T5)          `bash -n`. Secondary. Never the primary guard.
#   BEHAVIOURAL (T7, T8) the only checks that see POST-ESCAPE text: T7 asserts
#                        against the string the ssh shim captured, T8 executes
#                        the guard extracted from that same string.
# --------------------------------------------------------------------------


def test_deploy_local_applies_the_canonical_exclusions():
    """T6a — the live destructive defect in deploy_local.sh, closed.

    ``deploy_to()`` carried ``rsync -a --delete`` with ZERO exclusions across
    three consumer repos and eight subdirs: strictly the most destructive
    transport in the repo, deleting hooks/extensions/ (Issue #560) and the
    runtime .claude/ trees on every run. Adding the exclusions NARROWS what
    --delete may remove; it arms nothing.

    ``deploy_local.sh:167`` (the global sync) stays WITHOUT ``--delete``
    deliberately — it has no caller anywhere in the repo, so arming it would be
    a destructive change with no evidence behind it. That is Residual Risk 4,
    and ``test_plugin_copy_invocation_count_is_pinned`` is where the question
    re-opens if a caller appears.
    """
    text = DEPLOY_LOCAL_SH.read_text()

    assert 'deploy_state.py" excludes' in text, (
        "deploy_local.sh must source its exclusions from the single source of "
        "truth, not re-type them"
    )
    assert "REFUSED: could not build the deploy exclusion set" in text, (
        "an empty exclude array is indistinguishable at the rsync call site "
        "from the unguarded state this change removes; it must refuse"
    )

    invocations = _plugin_copy_invocations((DEPLOY_LOCAL_SH,))
    armed = [ln for ln in invocations if "--delete" in ln]
    assert len(armed) == 1, (
        f"expected exactly one armed rsync in deploy_local.sh; found:\n"
        + "\n".join(f"  {ln}" for ln in invocations)
    )
    line = armed[0]
    assert "--delete-after" in line, (
        f"deletion must be deferred until the transfer completes:\n{line}"
    )
    assert '"${DEPLOY_EXCLUDES[@]}"' in line, (
        f"the canonical exclusions do not reach the destructive rsync:\n{line}"
    )
    assert '--exclude=".claude/"' in line, (
        f"runtime .claude/ state under a deployed subdir is unprotected:\n{line}"
    )


def test_deploy_local_narrows_what_delete_removes(source_repo: Path, tmp_path: Path):
    """T6b — BEHAVIOURAL, both arms, against the real script.

    The static assertions above cannot tell whether the array reaches rsync
    non-empty. Run deploy_local.sh with $HOME pointed at a fixture and read the
    filesystem.
    """
    home = tmp_path / "home"
    dest = home / "Dev" / "realign" / ".claude"
    (dest / "lib" / "extensions").mkdir(parents=True)
    (dest / "lib" / ".claude").mkdir(parents=True)
    (dest / "lib" / "extensions" / "consumer_local.py").write_text("# consumer-local\n")
    (dest / "lib" / ".claude" / "runtime.log").write_text("telemetry\n")
    (dest / "lib" / "stale_module.py").write_text("# deleted from source long ago\n")
    (dest / "lib" / "hook_safety.py").write_text("# stale copy\n")

    result = subprocess.run(
        ["bash", str(source_repo / "scripts" / "deploy_local.sh"), "--skip-validate"],
        capture_output=True,
        text=True,
        cwd=str(source_repo),
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(home),
        },
        timeout=120,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined

    # PERMITTING ARM: deletion still propagates, which is the whole point.
    assert not (dest / "lib" / "stale_module.py").exists(), (
        f"a stale module survived the local deploy:\n{combined}"
    )
    assert (dest / "lib" / "hook_safety.py").read_text() == "# committed: 347-line shape\n", (
        f"the local deploy stopped delivering source:\n{combined}"
    )

    # REFUSING ARM: the classes the exclusions protect are still there.
    assert (dest / "lib" / "extensions" / "consumer_local.py").exists(), (
        f"hooks/extensions/ consumer-local state was deleted (Issue #560):\n{combined}"
    )
    assert (dest / "lib" / ".claude" / "runtime.log").exists(), (
        f"runtime .claude/ state under a deployed subdir was deleted:\n{combined}"
    )


def test_deploy_local_refuses_when_the_exclusion_set_is_empty(
    source_repo: Path, tmp_path: Path
):
    """T6c — the instrument's negative control.

    T6b proves the exclusions arrived. This proves the script can tell when
    they did NOT: with the subcommand stubbed to print nothing, deploy_local.sh
    must refuse rather than fall through to `rsync -a --delete` with an empty
    array, which is byte-for-byte the defect being removed.
    """
    (source_repo / "plugins" / "autonomous-dev" / "scripts" / "deploy_state.py").write_text(
        "import sys\nsys.exit(0)\n"
    )
    home = tmp_path / "home"
    dest = home / "Dev" / "realign" / ".claude" / "lib"
    dest.mkdir(parents=True)
    (dest / "stale_module.py").write_text("# would be deleted by an unguarded run\n")

    result = subprocess.run(
        ["bash", str(source_repo / "scripts" / "deploy_local.sh"), "--skip-validate"],
        capture_output=True,
        text=True,
        cwd=str(source_repo),
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(home),
        },
        timeout=120,
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 1, f"an empty exclusion set must refuse:\n{combined}"
    assert "REFUSED" in combined, combined
    assert "REQUIRED NEXT ACTION" in combined, (
        f"a refusal without a next action trains bypass:\n{combined}"
    )
    assert (dest / "stale_module.py").exists(), (
        f"the refusal happened AFTER deleting; it must happen before:\n{combined}"
    )


def test_remote_script_routes_both_transports_through_the_guard(
    source_repo: Path, tmp_path: Path
):
    """T7 — PRIMARY operational guard, asserted on POST-ESCAPE text.

    Everything else in this file reads a file on disk. This reads the string
    the ssh shim captured: the bytes that would be handed to the remote shell,
    after heredoc expansion, backslash escaping and command substitution.

    The catastrophic failure mode lives exactly in that gap. Inside the
    heredoc, ``\\$target`` defers to the remote while bare ``$target`` expands
    LOCALLY — where it is unset — so a single dropped backslash silently hands
    rsync an EMPTY destination under ``--delete``. Nothing on disk shows it and
    ``bash -n`` cannot see it, so the destination arguments are matched as
    EXACT literals rather than by pattern.
    """
    remote_script = _capture_remote_script(source_repo, tmp_path)

    # INSTRUMENT CONTROL, first: this text must exhibit BOTH expansion regimes,
    # or a comparison against deferred literals proves nothing. `somerepo` is
    # $REMOTE_REPOS expanded locally; `$target` survived to the remote.
    assert "somerepo" in remote_script, (
        "no locally-expanded value in the captured script — the capture is not "
        "the generated text"
    )
    assert "$target" in remote_script, (
        "no remotely-deferred parameter in the captured script — everything "
        "expanded locally, so the exact-literal assertions below are vacuous"
    )

    assert remote_script.count("prune_sync() {") == 1, (
        "prune_sync() must be defined exactly once in the generated remote "
        f"script; found {remote_script.count('prune_sync() {')}"
    )
    # Matched by the ARGUMENT, not by line start: every call site is wrapped in
    # `if ! ... ; then`, which is required — `set -e` is active on the remote, so
    # a bare call would abort the whole block instead of handling the refusal.
    calls = [
        ln.strip() for ln in remote_script.splitlines() if re.search(r'\bprune_sync "', ln)
    ]
    assert len(calls) == 2, (
        f"expected the per-repo and global transports to both route through the "
        f"guard; found {len(calls)}:\n" + "\n".join(f"  {c}" for c in calls)
    )
    for call in calls:
        assert call.startswith("if ! prune_sync "), (
            "`set -e` is active on the remote, so a bare prune_sync call aborts "
            "the whole block on refusal instead of stamping the target and "
            f"moving on:\n{call}"
        )

    per_repo = [c for c in calls if '"$target/$subdir/"' in c]
    glob = [c for c in calls if '"$HOME/.claude/$subdir/"' in c]
    assert len(per_repo) == 1, (
        "the per-repo destination is not the exact literal \"$target/$subdir/\" "
        "— a dropped backslash expands it locally to an EMPTY destination and "
        f"--delete would then be pointed at nothing:\n" + "\n".join(calls)
    )
    assert len(glob) == 1, (
        "the global destination is not the exact literal "
        '"$HOME/.claude/$subdir/":\n' + "\n".join(calls)
    )
    for call in calls:
        assert '"plugins/autonomous-dev/$subdir/"' in call, (
            f"the source argument did not survive escaping intact:\n{call}"
        )

    assert "--delete-after" in remote_script, (
        "deletions must be deferred until the transfer completes, so a "
        "mid-transfer failure leaves nothing deleted"
    )
    # Scanned on INVOCATION lines, not on the whole text: prune_sync.sh carries
    # a header paragraph explaining why the cap was rejected, and that
    # paragraph is inlined verbatim. The banned thing is the ARGUMENT.
    # (Unlike the delete-excluded flag, which is banned outright by T3,
    # --max-delete remains legitimate at deploy-all.sh:299 — Residual Risk 3 —
    # so a whole-file ban would be wrong as well as unenforceable.)
    remote_invocations = [
        ln.strip() for ln in remote_script.splitlines() if re.match(COPY_INVOCATION_RE, ln.strip())
    ]
    assert remote_invocations, "no rsync invocation survived into the remote script"
    for line in remote_invocations:
        assert "--max-delete" not in line, (
            "--max-delete is non-transactional: it deletes up to the cap and "
            "does not roll back, and config/ holds 16 files so a misresolved "
            "path wipes it entirely and still slips under a cap of 50. The "
            f"preview replaces it; it must not be re-added:\n{line}"
        )
        assert "--delete " in line or "--delete\t" in line or line.rstrip().endswith("--delete"), (
            f"a remote rsync invocation does not propagate deletions:\n{line}"
        )
    assert "REQUIRED NEXT ACTION" in remote_script, (
        "a refusal with no next action is the shape that trains bypass"
    )
    assert "REMOTE DEPLOY INCOMPLETE" in remote_script, (
        "a refusal mid-loop must make the remote block exit non-zero before "
        "validation, or validation prints PASSED over partial state"
    )

    # `local` outside a function is a RUNTIME error in bash and zsh, and the
    # `bash -n` run in test_remote_deploy_script_gates_and_stamps cannot see it.
    offenders = _top_level_local_offenders(remote_script)
    assert offenders == [], (
        "`local` at top level of the GENERATED remote script would abort the "
        "remote shell mid-loop, after repos had already been pruned:\n"
        + "\n".join(f"  {o}" for o in offenders)
    )


def _prune_sync_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """A source checkout where b.py was deleted in a commit, plus a stale target.

    Returns:
        ``(repo, dest)`` — the checkout to run from, and the target directory.
    """
    repo = tmp_path / "checkout"
    (repo / "plugins" / "autonomous-dev" / "lib").mkdir(parents=True)
    (repo / "plugins" / "autonomous-dev" / "empty").mkdir(parents=True)
    (repo / "plugins" / "autonomous-dev" / "lib" / "a.py").write_text("# kept\n")
    (repo / "plugins" / "autonomous-dev" / "lib" / "b.py").write_text("# to be deleted\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    # b.py is now plugin-OWNED history but absent from the working tree — the
    # exact shape of the five modules deleted in 7c3a527e.
    _git(repo, "rm", "-q", "plugins/autonomous-dev/lib/b.py")
    _git(repo, "commit", "-q", "-m", "delete b.py")

    dest = tmp_path / "target" / "lib"
    (dest / "extensions").mkdir(parents=True)
    (dest / ".claude").mkdir(parents=True)
    (dest / "a.py").write_text("# kept\n")
    (dest / "b.py").write_text("# to be deleted\n")
    (dest / "extensions" / "consumer_local.py").write_text("# consumer-local\n")
    (dest / ".claude" / "runtime.log").write_text("telemetry\n")
    return repo, dest


def _run_prune_sync(
    preamble: str, repo: Path, tmp_path: Path, src_rel: str, dest: Path, name: str
) -> subprocess.CompletedProcess:
    runner = tmp_path / f"drive_{name}.sh"
    runner.write_text(
        "set -euo pipefail\n"
        + preamble
        + f'prune_sync "{src_rel}" "{dest}/" "probe/{name}"\n'
    )
    return subprocess.run(
        ["bash", str(runner)],
        capture_output=True,
        text=True,
        cwd=str(repo),
        timeout=120,
    )


def test_prune_sync_refuses_a_candidate_the_plugin_never_owned(
    source_repo: Path, tmp_path: Path
):
    """T8a — REFUSING arm, ownership (R3), driven from the captured remote text.

    The remote per-repo sync covers all eight subdirs, including agents/,
    commands/ and skills/ — behaviour carriers a human may legitimately have
    authored locally. A file that has never existed under the plugin source
    path has no git history, and the sync must stop rather than delete it.

    This is a DIFFERENT SHAPE from the defect being fixed (a missing flag): it
    cannot be satisfied by adding a flag, so the fix cannot game it.
    """
    remote_script = _capture_remote_script(source_repo, tmp_path)
    preamble = _extract_prune_sync_preamble(remote_script)
    repo, dest = _prune_sync_fixture(tmp_path)
    probe = dest / "zz-human-probe.md"
    probe.write_text("# authored by a human, never plugin-owned\n")

    result = _run_prune_sync(
        preamble, repo, tmp_path, "plugins/autonomous-dev/lib/", dest, "unowned"
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 1, f"an unowned candidate must refuse:\n{combined}"
    assert "REFUSED" in combined and "zz-human-probe.md" in combined, (
        f"the refusal must name the file it stopped for:\n{combined}"
    )
    assert "REQUIRED NEXT ACTION" in combined, combined
    assert probe.exists(), f"the unowned file was deleted anyway:\n{combined}"
    assert (dest / "b.py").exists(), (
        "the refusal must precede ALL deletion, not just the one candidate it "
        f"objected to:\n{combined}"
    )


def test_prune_sync_deletes_only_what_the_plugin_owned(source_repo: Path, tmp_path: Path):
    """T8b — PERMITTING arm, driven from the captured remote text.

    A guard watched only refusing is indistinguishable from a guard that cannot
    permit. The stale module MUST actually go, or the whole change is inert and
    the five modules from 7c3a527e stay importable on every target.
    """
    remote_script = _capture_remote_script(source_repo, tmp_path)
    preamble = _extract_prune_sync_preamble(remote_script)
    repo, dest = _prune_sync_fixture(tmp_path)

    result = _run_prune_sync(
        preamble, repo, tmp_path, "plugins/autonomous-dev/lib/", dest, "owned"
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 0, f"a clean prune must be permitted:\n{combined}"
    assert not (dest / "b.py").exists(), (
        f"the stale plugin-owned module survived the prune:\n{combined}"
    )
    assert (dest / "a.py").exists(), f"a live module was deleted:\n{combined}"
    assert (dest / "extensions" / "consumer_local.py").exists(), (
        f"hooks/extensions/ consumer-local state was deleted (Issue #560):\n{combined}"
    )
    assert (dest / ".claude" / "runtime.log").exists(), (
        f"runtime .claude/ state was deleted:\n{combined}"
    )


def test_prune_sync_refuses_an_empty_source(source_repo: Path, tmp_path: Path):
    """T8c — REFUSING arm, pre-flight, driven from the captured remote text.

    An empty or misresolved source directory plus --delete empties the matching
    subtree on the target. This is the failure --max-delete could NOT catch:
    config/ holds 16 files, so a misresolved config would wipe it entirely and
    still slip under a cap of 50.
    """
    remote_script = _capture_remote_script(source_repo, tmp_path)
    preamble = _extract_prune_sync_preamble(remote_script)
    repo, dest = _prune_sync_fixture(tmp_path)

    result = _run_prune_sync(
        preamble, repo, tmp_path, "plugins/autonomous-dev/empty/", dest, "empty"
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 1, f"an empty source must refuse:\n{combined}"
    assert "REFUSED" in combined and "no regular files" in combined, combined
    assert "REQUIRED NEXT ACTION" in combined, combined
    assert (dest / "a.py").exists() and (dest / "b.py").exists(), (
        f"the target was pruned despite the refusal:\n{combined}"
    )


def test_top_level_local_detector_has_both_arms():
    """The instrument behind T5b and T7, controlled.

    ``_top_level_local_offenders`` returned an empty list against both the
    heredoc body and the generated remote script. An empty result from an
    unvalidated probe is not evidence of zero — the first version of this
    detector returned FIVE false positives because it treated the indented
    closing brace of a ``|| { ...; }`` block as a function closer. So it is
    driven here against text it must flag and text it must pass.
    """
    guarded = "prune_sync() {\n    local ok=1\n    x || {\n        return 1\n    }\n    local also_ok=2\n}\n"
    assert _top_level_local_offenders(guarded) == [], (
        "NEGATIVE CONTROL failed: `local` inside a function is legal, and a "
        "detector that flags it makes prune_sync unwritable"
    )

    offending = guarded + "local at_top_level=3\n"
    flagged = _top_level_local_offenders(offending)
    assert len(flagged) == 1 and "at_top_level" in flagged[0], (
        "POSITIVE CONTROL failed: the detector did not see a top-level `local`, "
        f"so its empty results elsewhere prove nothing; got {flagged}"
    )


def test_remote_incomplete_summary_exits_and_names_the_repos(
    source_repo: Path, tmp_path: Path
):
    """AC 4 tail — validation must never print PASSED over partial state.

    Extracts the failure-summary block from the GENERATED remote script and
    runs both arms. The permitting arm matters as much as the refusing one: a
    summary that exits 1 unconditionally would break every clean deploy.

    Scope note: this proves the summary block, not the whole loop. The full
    mid-loop semantics (break, skip post-sync steps, still stamp, continue)
    are proven on the real remote by AC 14(c), which plants a never-plugin-owned
    file in one repo and reads the exit code and the stamp.
    """
    remote_script = _capture_remote_script(source_repo, tmp_path)
    block = re.search(
        r'^if \[ -n "\$deploy_failed" \]; then\n.*?^fi$', remote_script, re.M | re.S
    )
    assert block, (
        "the generated remote script has no failure summary, so a refusal would "
        f"fall through to validation:\n{remote_script[-3000:]}"
    )

    runner = tmp_path / "summary.sh"

    # REFUSING ARM
    runner.write_text(
        'set -euo pipefail\ndeploy_failed=1\nfailed_repos=" spektiv realign"\n'
        + block.group(0)
        + "\necho REACHED_VALIDATION\n"
    )
    refused = subprocess.run(
        ["bash", str(runner)], capture_output=True, text=True, timeout=60
    )
    combined = refused.stdout + refused.stderr
    assert refused.returncode == 1, f"a refusal must exit non-zero:\n{combined}"
    assert "REMOTE DEPLOY INCOMPLETE" in combined, combined
    assert "spektiv" in combined and "realign" in combined, (
        f"the summary must name every refusing target:\n{combined}"
    )
    assert "REQUIRED NEXT ACTION" in combined, combined
    assert "REACHED_VALIDATION" not in combined, (
        f"validation ran over partial state and would print PASSED:\n{combined}"
    )

    # PERMITTING ARM
    runner.write_text(
        'set -euo pipefail\ndeploy_failed=""\nfailed_repos=""\n'
        + block.group(0)
        + "\necho REACHED_VALIDATION\n"
    )
    clean = subprocess.run(["bash", str(runner)], capture_output=True, text=True, timeout=60)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "REACHED_VALIDATION" in clean.stdout, (
        "a clean deploy must still reach validation:\n" + clean.stdout + clean.stderr
    )
    assert "REMOTE DEPLOY INCOMPLETE" not in clean.stdout, clean.stdout

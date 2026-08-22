"""Regression tests for Issue #1619 — the gh-issue-create gate is defeated by any wrapper.

``_detect_gh_issue_create`` is one of the few guards in this repo observed
genuinely refusing in production. Measured on 2026-08-22 against ``eb2adad6``,
driving the live hook as a subprocess with the command-context marker redirected
to a scratch path (the real ``/tmp`` marker was never read or written)::

    gh issue create --title "x" --body "y"          ->  deny    (control)
    env gh issue create --title "x" --body "y"      ->  allow   <-- bypass
    env -i gh issue create --title "x" --body "y"   ->  allow   <-- bypass
    nice gh issue create --title "x" --body "y"     ->  allow   <-- bypass
    command gh issue create --title "x" --body "y"  ->  allow   <-- bypass
    stdbuf -o0 gh issue create --title "x" ...      ->  allow   <-- bypass
    timeout 30 gh issue create --title "x" ...      ->  allow   <-- bypass
    nohup gh issue create --title "x" --body "y"    ->  allow   <-- bypass
    xargs gh issue create --title "x" --body "y"    ->  allow   <-- bypass
    eval "gh issue create --title x"                ->  allow   <-- bypass
    gh issue list --limit 3                         ->  allow   (control)
    git commit -m "fix gh issue create gate"        ->  allow   (control, #1215)
    nice ls -la                                     ->  allow   (control)

Root cause: ``_gh_issue_create_at_command_position`` skipped leading
``VAR=value`` tokens and a fixed ``_SHELL_WRAPPERS`` set, then required
``argv[0] == "gh"``. ``env`` and ``nice`` were not in that set — and neither is
the next wrapper anyone writes.

The fix does NOT add members to ``_SHELL_WRAPPERS``. That is an allowlist against
an open set (``command``, ``stdbuf``, ``timeout``, ``xargs``, ``nohup``,
``setsid``, ``taskset``, ``doas``, ``sudo -u`` and whatever ships tomorrow), and
``stash@{0}`` holds a prior pattern-enumeration attempt for a sibling gate marked
FAIL-Critical with 65 bypasses remaining. Instead the polarity is inverted: the
gate resolves the *effective verb* by scanning past the leading prefix, and the
only remaining enumeration is on the PERMIT side
(``_COMMAND_ARG_CONSUMERS``), where an omission over-blocks loudly rather than
silently permitting.

This module locks four properties:

1. the refusing arm — every wrapper form above, plus wrappers deliberately
   chosen to be absent from any list in the source (``taskset``, ``doas``, and
   an invented ``frobnicate``), is refused. That is the *class*, not the three
   instances that prompted the fix;
2. the permitting arm — ``env FOO=bar gh issue list``, ``nice ls -la``,
   ``eval "$(ssh-agent -s)"`` and the #1215 commit-prose case stay permitted,
   so the wrapper rule did not become a blanket block;
3. unresolvable verbs (``eval "..."``, a computed ``$CMD``) fail CLOSED for this
   gate rather than falling through to allow;
4. the refusal is byte-identical to the pre-existing block reason, i.e. it
   returns through the one existing ``return`` in ``_detect_gh_issue_create``
   that the dispatch site already records via the #1588 sink — no new refusal
   path that could refuse without recording.

The enumeration boundary is where the remaining risk sits, and it is where the
next defects were found — every one of them measured, not theorised::

    xargs -I '#' gh issue create …   ->  allow   <-- quoted '#' truncated it
    sudo -p '#' gh issue create …    ->  allow   <-- same
    git bisect run gh issue create   ->  allow   <-- over-broad `git` permit
    git submodule foreach gh …       ->  allow   <-- same
    git difftool -x gh issue create  ->  allow   <-- same
    grep $PAT issue create docs/     ->  deny    <-- computed-verb shape unscoped

Sections 7-9 lock the corresponding properties: comment stripping is quote-aware
and runs before tokenization; the ``git`` permit entry is conditional on its
subcommand; and the computed-verb shape only fires at the effective verb
position. A quoted ``'#'`` is data to bash, ``git bisect run <cmd>`` executes a
bare positional, and a ``$VAR`` in an arg-consuming verb's operand list is
prose — all three are properties, driven both arms, not example lists.

Review of the above found two more, both on the same boundary and both
measured before being believed::

    git -C . bisect run gh issue create …      ->  allow  <-- global option
    git --no-pager bisect run gh issue create  ->  allow  <-- same
    git --git-dir=… bisect run gh issue …      ->  allow  <-- same
    git -C . difftool -x gh issue create       ->  allow  <-- same
    env -u FOO<NBSP># gh issue create …        ->  allow  <-- Unicode space

The first four: the ``git`` qualifier read its subcommand at the fixed offset
``argv[idx + 1]``, but git's global options sit BETWEEN the verb and the
subcommand, so one ``-C`` reopened four of the six runner subcommands. That
shape is normal here, not exotic — 2,693 of 19,795 bare-``git`` commands in
167,963 logged commands (14%) carry a global option. The subcommand is now
searched across the whole remainder of argv; measured over-block cost of
scanning wide: ZERO legitimate commands in that same corpus.

The fifth: the comment scanner asked ``str.isspace()``, which is Unicode-aware,
where bash's IFS is space/tab/newline only. After U+00A0, U+2007, U+2028, VT or
FF the scanner truncated the statement while BASH read the ``#`` as a literal
mid-word character and EXECUTED the rest — verified end to end with a stub
``gh`` on PATH. Sections 10-11 lock the heredoc single-strip fold and the
separator set; both, like everything above, are driven on both arms.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
#: The SOURCE copy under ``plugins/``. This is what this module imports and
#: drives. The copy that EXECUTES in a live session is the deploy artifact at
#: ``.claude/hooks/unified_pre_tool.py``, refreshed by ``scripts/deploy-all.sh``
#: — pre-deploy divergence is the normal, correct state for a staged change.
SOURCE_HOOK_FILE = HOOK_DIR / "unified_pre_tool.py"

sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — never touch the real global markers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_context(tmp_path, monkeypatch):
    """Redirect the sanctioning marker to a per-test path that does not exist.

    Issue #1609: ``/tmp/autonomous_dev_cmd_context.json`` is global. Its presence
    makes every detector in this module PERMIT what it would otherwise REFUSE.
    Issue #1618: interactive sessions still leak it. Redirecting per-test is what
    makes these assertions mean anything.
    """
    isolated = tmp_path / "no_such_context.json"
    monkeypatch.setenv("GH_ISSUE_CMD_CONTEXT_PATH", str(isolated))
    with patch.object(hook, "GH_ISSUE_COMMAND_CONTEXT_PATH", str(isolated)):
        yield isolated


@pytest.fixture(autouse=True)
def no_allow_through():
    """Strip every allow-through so the detector's own logic is what is measured."""
    with patch.object(hook, "_is_pipeline_active", return_value=False), patch.object(
        hook, "_get_active_agent_name", return_value=None
    ), patch.object(hook, "_is_issue_command_active", return_value=False):
        yield


# ---------------------------------------------------------------------------
# 1. Refusing arm — the wrapper CLASS, not the three reported instances
# ---------------------------------------------------------------------------

#: Forms measured as ``allow`` before the fix. The last three are deliberately
#: NOT drawn from the issue report: ``taskset`` and ``doas`` were never named in
#: any list in the source, and ``frobnicate`` does not exist at all. If the fix
#: were wrapper enumeration, those three would still bypass.
WRAPPER_BYPASS_FORMS = [
    'env gh issue create --title "x" --body "y"',
    'env -i gh issue create --title "x" --body "y"',
    "env FOO=bar gh issue create --title x",
    'nice gh issue create --title "x" --body "y"',
    "nice -n 10 gh issue create --title x",
    'command gh issue create --title "x" --body "y"',
    "stdbuf -o0 gh issue create --title x",
    "timeout 30 gh issue create --title x",
    "nohup gh issue create --title x",
    "xargs gh issue create --title x",
    "setsid gh issue create --title x",
    "sudo -u nobody gh issue create --title x",
    "taskset -c 0 gh issue create --title x",
    "doas gh issue create --title x",
    "frobnicate gh issue create --title x",
    "env nice command gh issue create --title x",
    "/usr/bin/gh issue create --title x",
    "/opt/homebrew/bin/gh issue create --title x",
    "env /usr/bin/gh issue create --title x",
    "find . -name x -exec gh issue create --title x ;",
]


@pytest.mark.parametrize("command", WRAPPER_BYPASS_FORMS)
def test_wrapper_prefixed_gh_issue_create_is_refused(command: str) -> None:
    """Every wrapper form reaches ``gh issue create`` and MUST be refused."""
    assert hook._detect_gh_issue_create(command) is not None, (
        f"BYPASS: {command!r} was permitted. The gate must resolve the effective "
        f"verb past the leading prefix, not trust argv[0]."
    )


@pytest.mark.parametrize("command", WRAPPER_BYPASS_FORMS)
def test_wrapper_forms_detected_by_argv_helper(command: str) -> None:
    """The helper itself, not just the detector, resolves the effective verb."""
    assert hook._gh_issue_create_at_command_position(command) is True, command


def test_bare_form_still_refused_control() -> None:
    """Positive control — the form that was already refused must stay refused."""
    assert hook._detect_gh_issue_create('gh issue create --title "x"') is not None


# ---------------------------------------------------------------------------
# 2. Unresolvable effective verb fails CLOSED (not fall-through to allow)
# ---------------------------------------------------------------------------

UNRESOLVABLE_FORMS = [
    'eval "gh issue create --title x"',
    "eval 'gh issue create --title x'",
    'env eval "gh issue create --title x"',
    "$CMD issue create --title x",
    "${GH_BIN} issue create --title x",
]


@pytest.mark.parametrize("command", UNRESOLVABLE_FORMS)
def test_unresolvable_verb_fails_closed(command: str) -> None:
    """An effective verb we cannot resolve MUST refuse, not fall through."""
    assert hook._detect_gh_issue_create(command) is not None, (
        f"FAIL-OPEN: {command!r} was permitted. Where the effective verb cannot "
        f"be resolved this gate must fail closed."
    )


# ---------------------------------------------------------------------------
# 3. Permitting arm — the wrapper rule must NOT become a blanket block
# ---------------------------------------------------------------------------

PERMITTED_FORMS = [
    # Explicitly required by the issue: the wrapper alone must not block.
    "env FOO=bar gh issue list --limit 3",
    "env gh issue list",
    "env gh pr create --title x",
    "env",
    "env -i bash -lc 'echo hi'",
    "nice ls -la",
    "nice -n 10 pytest -q",
    "timeout 30 pytest tests/unit -q",
    "command -v gh",
    "xargs rm -f",
    "gh issue list --limit 3",
    "gh issue view 1619",
    "gh pr create --title x --body y",
    "gh issue comment 1619 --body 'see gh issue create'",
    # The fail-closed rule must not become a blanket eval block.
    'eval "$(ssh-agent -s)"',
    "eval \"$(direnv hook zsh)\"",
    'eval "$(/opt/homebrew/bin/brew shellenv)"',
    "$PYTHON -m pytest -q",
    "${EDITOR} notes.md",
    # Issue #1215 lock: gh-issue-create as prose in a commit body, quoted...
    'git commit -m "fix gh issue create gate"',
    # ...and unquoted, which survives _strip_body_arg_values as three bare tokens.
    "git commit -m fix gh issue create gate",
    "git log --oneline --grep gh issue create",
    # Text-handling verbs consume the tokens as data, not as a command.
    "echo gh issue create",
    "printf gh issue create",
    "grep gh issue create",
    "rg gh issue create docs/",
    # A computed token that is an OPERAND of an arg-consuming verb is prose,
    # not a verb. All four were measured REFUSED before the remediation: the
    # computed-verb shape was not scoped to the verb position. The second is
    # the Issue #1215 commit-prose class returning the moment a message
    # contains a variable — the very case `git` is on the permit side for.
    "grep $PAT issue create docs/",
    "git commit -m fix $BRANCH issue create flow",
    "cat notes-$USER issue create",
    "echo `date` issue create",
    # `git` stays a consumer for its non-executing subcommands.
    "git log --grep gh issue create --oneline",
    "git grep gh issue create -- docs/",
    "git show --stat gh issue create",
    # ...INCLUDING when a global option precedes the subcommand. Widening the
    # runner search from `argv[idx + 1]` to the whole remainder must not cost
    # the routine idiom: 2,693 of 19,795 bare-`git` commands in this repo's
    # 167,963 logged commands (14%) put a global option before the subcommand,
    # so an over-block here would be a permanently-red check on normal work.
    "git -C . diff HEAD~1",
    "git -C . diff HEAD~1 -- gh issue create",
    "git -C /some/path log --oneline",
    "git --no-pager log --grep gh issue create",
    "git -C . commit -m fix gh issue create gate",
    "git --git-dir=/tmp/.git log --grep gh issue create",
]


@pytest.mark.parametrize("command", PERMITTED_FORMS)
def test_legitimate_commands_still_permitted(command: str) -> None:
    """The permitting arm. A guard watched only refusing is not a guard."""
    assert hook._detect_gh_issue_create(command) is None, (
        f"OVER-BLOCK: {command!r} was refused. A permanently-red check trains "
        f"everyone to ignore the whole class."
    )


# ---------------------------------------------------------------------------
# 4. Refusals route through the existing recorded return (#1588 sink)
# ---------------------------------------------------------------------------


def test_wrapper_refusal_is_the_same_recorded_block_reason() -> None:
    """No new refusal path: wrapper forms return the pre-existing block string.

    The dispatch site logs ``_detect_gh_issue_create``'s return value through
    ``_log_deviation`` + ``_log_pretool_activity``. Returning the byte-identical
    reason is what makes the new refusals recorded by construction rather than
    by a second, separately-maintained logging call.
    """
    baseline = hook._detect_gh_issue_create('gh issue create --title "x"')
    assert baseline is not None
    for command in ("env gh issue create --title x", 'eval "gh issue create -t x"'):
        assert hook._detect_gh_issue_create(command) == baseline, command


def test_no_second_refusal_return_added_to_the_detector() -> None:
    """Structural lock: the detector still has exactly one refusal return.

    A second ``return`` of a block reason would be a refusal path that the
    dispatch site's sink call still covers, but that could drift. Counting the
    literal ``BLOCKED: Cannot create GitHub issues`` string keeps the single
    sink-covered exit honest.
    """
    source = SOURCE_HOOK_FILE.read_text(encoding="utf-8")
    assert source.count('"BLOCKED: Cannot create GitHub issues') == 1


# ---------------------------------------------------------------------------
# 5. The SOURCE hook as a real process — end-to-end, not import-level
# ---------------------------------------------------------------------------
#
# Accuracy note: this section drives ``plugins/autonomous-dev/hooks/`` — the
# SOURCE copy — as a subprocess with a real Claude Code payload. That is
# stronger than the import-level assertions above (it exercises stdin parsing,
# dispatch and the JSON decision envelope), but it is NOT the copy that
# executes in a live session. That is the deploy artifact at
# ``.claude/hooks/unified_pre_tool.py``, which lands via
# ``bash scripts/deploy-all.sh`` and is byte-identical to HEAD until then. No
# byte-equality assertion is made here: it would be permanently red in every
# dev checkout with a staged change, and a check that cries wolf trains
# everyone to ignore the class.


def _drive_hook(hook_path: Path, command: str, ctx_path: Path) -> str:
    """Run ``hook_path`` as a subprocess the way Claude Code does.

    Args:
        hook_path: Path to the hook script to execute.
        command: The Bash command string to submit as ``tool_input``.
        ctx_path: Scratch path for the sanctioning marker (must not exist).

    Returns:
        The ``permissionDecision`` string from the hook's JSON output.
    """
    env = dict(os.environ)
    env["GH_ISSUE_CMD_CONTEXT_PATH"] = str(ctx_path)
    env.pop("CLAUDE_AGENT_NAME", None)
    env.pop("AUTONOMOUS_DEV_BYPASS", None)
    payload = {
        "session_id": "test-1619",
        "cwd": str(REPO_ROOT),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=120,
    )
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:  # pragma: no cover - diagnostic path
        pytest.fail(f"hook produced non-JSON: {proc.stdout!r} / {proc.stderr!r}")
    return out.get("hookSpecificOutput", {}).get("permissionDecision", "")


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ('gh issue create --title "x" --body "y"', "deny"),
        ('env gh issue create --title "x" --body "y"', "deny"),
        ('nice gh issue create --title "x" --body "y"', "deny"),
        ('eval "gh issue create --title x"', "deny"),
        ("env FOO=bar gh issue list --limit 3", "allow"),
        ("nice ls -la", "allow"),
        ('git commit -m "fix gh issue create gate"', "allow"),
        # Comment handling, through the executing process (section 7).
        ("# can the coordinator call gh issue create here", "allow"),
        ("gh issue list # gh issue create", "allow"),
        ("echo hi; gh issue create --title x", "deny"),
        ('gh issue create --title "#123"', "deny"),
        # Quoted-'#' smuggling and git-as-runner, through a real process.
        ("xargs -I '#' gh issue create --title x", "deny"),
        ("git bisect run gh issue create --title x", "deny"),
        ("grep $PAT issue create docs/", "allow"),
        ("git commit -m fix $BRANCH issue create flow", "allow"),
    ],
)
def test_source_hook_subprocess_decisions(
    command: str, expected: str, tmp_path: Path
) -> None:
    """End-to-end through the SOURCE hook as a real process, both arms."""
    ctx = tmp_path / "no_such_context.json"
    assert _drive_hook(SOURCE_HOOK_FILE, command, ctx) == expected, command


def test_settings_names_a_hook_path_that_exists() -> None:
    """The copy that EXECUTES is not the copy under ``plugins/``.

    ``.claude/settings.json`` points PreToolUse at ``.claude/hooks/``, an
    untracked deploy artifact refreshed by ``scripts/deploy-all.sh``. This test
    does NOT assert byte-equality with source: pre-deploy divergence is the
    normal, correct state for a staged change, and asserting equality here
    would be permanently red in every dev checkout — a check that cries wolf
    trains everyone to ignore the class.

    What it does lock is that the executing path named in settings resolves to
    a real file, so the deploy target cannot silently disappear and leave the
    gate unregistered.
    """
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
    referenced = json.dumps(settings)
    assert "unified_pre_tool.py" in referenced, (
        "PreToolUse no longer references unified_pre_tool.py — the gate this "
        "module tests would not run at all."
    )
    deployed = REPO_ROOT / ".claude" / "hooks" / "unified_pre_tool.py"
    assert deployed.exists(), (
        f"settings.json names {deployed} but it does not exist — run "
        f"`bash scripts/deploy-all.sh --local`."
    )


# ---------------------------------------------------------------------------
# 6. The fix is not wrapper enumeration
# ---------------------------------------------------------------------------


def test_shell_wrappers_set_was_not_grown_into_a_wrapper_allowlist() -> None:
    """``_SHELL_WRAPPERS`` stays what it is: shells whose ``-c`` carries a command.

    Growing it to hold ``env``/``nice``/``timeout``/... is the fix this change
    exists to avoid. If a future edit adds a non-shell to it, the bypass axis is
    back and this test says so.
    """
    non_shell = {
        w.rsplit("/", 1)[-1]
        for w in hook._SHELL_WRAPPERS
        if w.rsplit("/", 1)[-1] not in {"sh", "bash", "zsh", "dash", "ksh"}
    }
    assert non_shell == set(), (
        f"_SHELL_WRAPPERS grew non-shell members {sorted(non_shell)} — that is "
        f"wrapper enumeration, which does not converge (see stash@{{0}}, #1570)."
    )


#: `git` is the one permit-set member that does not satisfy the membership rule
#: unconditionally. Four of its subcommands execute a bare positional; three of
#: these forms were measured PERMITTING before the qualifier existed. A single
#: over-broad permit member converts the whole set back into a deny list with
#: extra steps, and does so invisibly — which is why this arm is locked.
GIT_RUNNER_SUBCOMMAND_FORMS = [
    "git bisect run gh issue create --title x",
    "git submodule foreach gh issue create --title x",
    "git difftool -x gh issue create --title x",
    "git rebase --exec gh issue create --title x main",
    "git filter-branch --msg-filter gh issue create --title x HEAD",
    "git mergetool --tool gh issue create",
    # Reached through a wrapper as well.
    "env git bisect run gh issue create --title x",
    # ...and with a GLOBAL OPTION between `git` and its subcommand, which is
    # where git actually puts `-C`, `--no-pager`, `--git-dir=`, `--work-tree=`
    # and `-c k=v`. Reading the subcommand at the fixed offset `argv[idx + 1]`
    # sees the OPTION, misses the membership test, and permits: all five forms
    # below were measured PERMITTING against the fixed-offset version, i.e. one
    # global option reopened four of the six runner subcommands.
    "git -C . bisect run gh issue create -t x",
    "git --no-pager bisect run gh issue create -t x",
    "git --git-dir=/tmp/.git bisect run gh issue create -t x",
    "git -C . difftool -x gh issue create",
    "git --work-tree=/tmp submodule foreach gh issue create -t x",
    # Two globals, one of them value-taking, in front of a third runner form.
    "git -C . -c k=v rebase --exec gh issue create -t x main",
    # `-c k=v` denied even at the fixed offset, but only INCIDENTALLY:
    # _strip_body_arg_values ate `-c`'s value and left `bisect` back at
    # argv[idx + 1]. Kept so a future refactor of the stripper cannot silently
    # convert that luck into a permit.
    "git -c k=v bisect run gh issue create -t x",
    # Wrapper AND global option together.
    "env git -C . bisect run gh issue create -t x",
]


@pytest.mark.parametrize("command", GIT_RUNNER_SUBCOMMAND_FORMS)
def test_git_subcommands_that_execute_arguments_are_refused(command: str) -> None:
    """`git` is a command RUNNER for these subcommands, not an arg consumer."""
    assert hook._detect_gh_issue_create(command) is not None, (
        f"BYPASS: {command!r} makes git execute gh issue create. The permit "
        f"entry for `git` must be conditional on the subcommand."
    )


def test_verb_consumes_bare_args_drives_both_arms_for_git() -> None:
    """The permit-side classifier itself, refusing and permitting.

    Membership in ``_COMMAND_ARG_CONSUMERS`` is necessary but NOT sufficient.
    Testing the set directly is what let the over-broad `git` entry through, so
    the classifier is what gets locked.
    """
    consumes = hook._verb_consumes_bare_args
    # Permitting arm — git as an arg consumer.
    assert consumes(["git", "commit", "-m", "x"], 0) is True
    assert consumes(["git", "log", "--oneline"], 0) is True
    assert consumes(["/usr/bin/git", "grep", "foo"], 0) is True
    # Refusing arm — git as a command runner.
    #
    # Every prefix below is exercised against every runner subcommand. The
    # earlier revision of this test built ONLY ["git", subcommand, "gh"], so no
    # global-option argv was ever CONSTRUCTED and the fixed-offset read of
    # argv[idx + 1] stayed green while `git -C . bisect run …` permitted. A
    # classifier tested only on the shape that motivated it is scoped to that
    # shape; these prefixes are the different-shaped negative control.
    global_option_prefixes = [
        [],                        # no global option — the original shape
        ["-C", "."],               # value-taking, separate token
        ["--no-pager"],            # valueless
        ["--git-dir=/tmp/.git"],   # value attached with `=`
        ["--work-tree=/tmp"],
        ["-c", "k=v"],             # value-taking, separate token
        ["-C", ".", "-c", "k=v"],  # two globals, both value-taking
        ["--no-pager", "-C", "."],
    ]
    for subcommand in sorted(hook._GIT_SUBCOMMANDS_THAT_EXECUTE_ARGUMENTS):
        for prefix in global_option_prefixes:
            argv = ["git", *prefix, subcommand, "gh", "issue", "create"]
            assert consumes(argv, 0) is False, (
                f"BYPASS: {argv!r} — git is a command RUNNER here. Reading the "
                f"subcommand at the fixed offset argv[idx + 1] sees "
                f"{argv[1]!r}, misses the membership test, and PERMITS. The "
                f"runner subcommand must be searched across the whole "
                f"remainder of argv."
            )
    # Permitting arm with the SAME prefixes — widening the search must not
    # over-block the routine idiom (`git -C . diff` is 14% of bare-git usage
    # in this repo's logs). Without this loop the fix could pass by making the
    # git branch unconditionally False.
    for prefix in global_option_prefixes:
        for subcommand in ("diff", "commit", "log", "grep", "show", "status"):
            argv = ["git", *prefix, subcommand, "gh", "issue", "create"]
            assert consumes(argv, 0) is True, (
                f"OVER-BLOCK: {argv!r} — `git {subcommand}` consumes its bare "
                f"positionals as data (refs, paths, prose). Refusing it makes "
                f"this gate permanently red on normal work."
            )
    # Non-git consumers are unconditional; non-consumers are never permitted.
    # `grep` takes a runner subcommand name as a bare pattern and must stay
    # permitted — the widened scan is scoped to `git`, not applied globally.
    assert consumes(["grep", "bisect", "x"], 0) is True
    assert consumes(["echo", "git", "bisect", "run", "gh"], 0) is True
    assert consumes(["env", "gh", "issue", "create"], 0) is False
    # Bounds: a bare `git`, and `git` with only global options, must not index
    # past the end nor invent a subcommand.
    assert consumes(["git"], 0) is True
    assert consumes(["git", "-C", "."], 0) is True
    assert consumes([], 0) is False
    # Offset-aware: the same argv reached at a non-zero idx behaves identically.
    assert consumes(["env", "git", "-C", ".", "bisect", "run", "gh"], 1) is False
    assert consumes(["env", "git", "-C", ".", "diff", "HEAD~1"], 1) is True


def test_git_permit_entry_is_qualified_by_a_scoped_subcommand_set() -> None:
    """The inner deny list is scoped to one verb with a closed vocabulary.

    This is deliberately NOT a relapse into wrapper enumeration: git's
    subcommand vocabulary is closed and documented upstream, unlike the open,
    attacker-controlled set of shell wrappers. Do not invert this into a permit
    list of "safe" git subcommands — git ships ~150 of them, and that direction
    puts the loud failure on the wrong side.
    """
    executing = hook._GIT_SUBCOMMANDS_THAT_EXECUTE_ARGUMENTS
    assert isinstance(executing, frozenset)
    for subcommand in ("bisect", "submodule", "rebase", "difftool"):
        assert subcommand in executing, (
            f"git {subcommand} executes a bare positional — omitting it "
            f"reopens a silent permit."
        )
    # It must stay SCOPED. If it grows past a couple of dozen members it has
    # stopped being a closed vocabulary and become the open set again.
    assert len(executing) < 25, (
        f"_GIT_SUBCOMMANDS_THAT_EXECUTE_ARGUMENTS grew to {len(executing)} "
        f"members — that is enumeration against an open set."
    )


def test_permit_side_enumeration_is_the_only_enumeration() -> None:
    """The remaining list is on the PERMIT side, where omission over-blocks.

    An omission from ``_COMMAND_ARG_CONSUMERS`` produces a false refusal — loud,
    attributable, fixable. An omission from a wrapper DENY-list produces a silent
    permit. Locking the polarity is the point of the fix.
    """
    consumers = hook._COMMAND_ARG_CONSUMERS
    assert isinstance(consumers, frozenset)
    # Executors must never be on the permit side.
    for executor in ("env", "nice", "timeout", "xargs", "nohup", "sudo", "command"):
        assert executor not in consumers, (
            f"{executor!r} runs its argument as a command — permitting it "
            f"reopens the bypass."
        )


# ---------------------------------------------------------------------------
# 7. Bash comments are prose, not invocations — the refusing arm must NOT fire
# ---------------------------------------------------------------------------

#: Once the gate stopped trusting ``argv[0]`` it began scanning every statement
#: for the ``gh issue create`` token triple. ``shlex(posix=True)`` does not strip
#: shell comments, so a sentence merely *mentioning* the phrase read as an
#: invocation. Measured against this repo's own activity log, 1,282 commands were
#: decision-relevant and 15 of them were newly refused purely for being comment
#: lines. This is the cry-wolf class: a guard that refuses prose trains people to
#: route around the guard, and ``51743c87`` is the live example of what that
#: costs — a correct, 24-hour-red drift check silenced by reclassifying the very
#: hooks it was complaining about.
COMMENT_PROSE_FORMS = [
    # The exact shape measured as newly-refused.
    "# can the coordinator call gh issue create here",
    "#gh issue create",  # no space after the marker
    "   # indented: gh issue create",
    "# TODO: replace gh issue create with /create-issue",
    # A comment trailing a legitimate command: the comment is NOT the command.
    "gh issue list # gh issue create",
    "gh issue list --limit 3  # then gh issue create if empty",
    "pytest -q # gh issue create on failure",
    # A quoted literal is data, not a comment marker, and must not truncate.
    'echo "# gh issue create"',
    "echo '# gh issue create'",
]


@pytest.mark.parametrize("command", COMMENT_PROSE_FORMS)
def test_comment_prose_is_not_an_invocation(command: str) -> None:
    """A comment mentioning the phrase MUST NOT be refused.

    This is the refusing arm asserted NOT to fire. It is authored to a different
    shape than the wrapper reproducers in section 1 on purpose: those prove the
    gate still catches execution, this proves it does not catch prose.
    """
    assert hook._detect_gh_issue_create(command) is None, (
        f"CRY-WOLF: {command!r} is a comment, not an invocation, but was refused. "
        f"A guard that refuses prose gets routed around."
    )


@pytest.mark.parametrize("command", COMMENT_PROSE_FORMS)
def test_comment_prose_not_flagged_by_argv_helper(command: str) -> None:
    """The helper itself, not only the detector, treats a comment as prose."""
    assert hook._gh_issue_create_at_command_position(command) is False, command


#: The boundary, and one case past it. Comment truncation must not become a way
#: to smuggle a real invocation onto the same line.
COMMENT_ADJACENT_STILL_REFUSED = [
    # A real invocation AFTER a separator — the comment fix must not swallow it.
    "echo hi; gh issue create --title x",
    "echo hi && gh issue create --title x",
    "gh issue list | gh issue create --title x",
    # A real invocation BEFORE a trailing comment.
    "gh issue create --title x # this is fine, right?",
    # '#' inside an argument VALUE must not truncate away the preceding triple.
    'gh issue create --title "#123"',
    "gh issue create --title '#123' --body y",
    'env gh issue create --title "#hashtag"',
    # A comment earlier in the line does not license a later statement.
    "# harmless note\ngh issue create --title x",
]


@pytest.mark.parametrize("command", COMMENT_ADJACENT_STILL_REFUSED)
def test_real_invocation_alongside_a_comment_is_still_refused(command: str) -> None:
    """Truncating at ``#`` must not open a smuggling path.

    Each form here contains a genuine ``gh issue create`` execution somewhere
    other than inside the comment. Refusal must survive the comment handling.
    """
    assert hook._detect_gh_issue_create(command) is not None, (
        f"BYPASS: {command!r} executes gh issue create but was permitted — "
        f"comment truncation must not consume a real statement."
    )


#: A quoted ``'#'`` is NOT a comment marker in bash, so each of these really
#: executes ``gh issue create``. Measured PERMITTING before the remediation:
#: ``_strip_body_arg_values`` rejoins shlex tokens with single spaces, so the
#: quoting is gone by the time any post-tokenization predicate sees the token.
#: ``shlex.split("xargs -I '#' gh issue create", posix=True)`` yields
#: ``['xargs', '-I', '#', 'gh', 'issue', 'create']`` — a BARE ``#`` — which
#: truncated the statement to ``['xargs', '-I']`` and permitted what followed.
#: Both verbs are deliberately absent from ``_COMMAND_ARG_CONSUMERS``.
QUOTED_HASH_SMUGGLING_FORMS = [
    "xargs -I '#' gh issue create --title x",
    'xargs -I "#" gh issue create --title x',
    "sudo -p '#' gh issue create -t x",
    "echo 1 | xargs -I '#' gh issue create --title x",
    "env -S '#' gh issue create --title x",
]


@pytest.mark.parametrize("command", QUOTED_HASH_SMUGGLING_FORMS)
def test_quoted_hash_does_not_truncate_away_a_real_invocation(command: str) -> None:
    """A quoted ``#`` is data to bash, so it must not act as a comment marker.

    The refusing arm for the comment fix. Comment stripping must run on the RAW
    statement text, where quoting still exists — not on post-``shlex`` tokens,
    which have already lost it.
    """
    assert hook._detect_gh_issue_create(command) is not None, (
        f"BYPASS: {command!r} executes gh issue create behind a QUOTED '#'. "
        f"Comment stripping must be quote-aware and run before tokenization."
    )


#: The permitting arm of the same predicate: an UNQUOTED word-initial ``#`` is
#: a real comment and must still truncate, and a ``#`` that is quoted, escaped
#: or mid-word must not be mistaken for one.
COMMENT_TRUNCATION_PERMITTED = [
    # Real comments — must truncate.
    "# prose mentioning gh issue create",
    "pytest -q   # then gh issue create if it fails",
    # Quoted/escaped '#' as data — must NOT truncate, and there is no
    # invocation behind it to find either.
    "echo '# gh issue create'",
    'echo "# gh issue create"',
    "grep -F '#' notes.md",
]


@pytest.mark.parametrize("command", COMMENT_TRUNCATION_PERMITTED)
def test_comment_truncation_permits_prose_and_quoted_hashes(command: str) -> None:
    """The permitting arm. Truncation must not become a blanket refusal."""
    assert hook._detect_gh_issue_create(command) is None, (
        f"CRY-WOLF: {command!r} executes nothing but was refused."
    )


def test_comment_stripper_is_quote_aware_at_the_character_level() -> None:
    """Drive ``_strip_shell_comment`` directly, both arms.

    This replaces a prior assertion that grepped the hook source for a literal
    predicate string. A source-text assertion verifies nothing behavioural: it
    cannot distinguish a correct predicate from an incorrect one, and it fails
    when the string merely moves. A property is locked by driving both arms.
    """
    strip = hook._strip_shell_comment
    # Refusing arm of the stripper: an unquoted word-initial '#' truncates.
    assert strip("gh issue list # gh issue create") == "gh issue list "
    assert strip("#gh issue create") == ""
    assert strip("   # indented") == "   "
    # Permitting arm: quoted, escaped, and mid-word '#' are all data.
    assert strip("xargs -I '#' gh issue create") == "xargs -I '#' gh issue create"
    assert strip('xargs -I "#" gh issue create') == 'xargs -I "#" gh issue create'
    assert strip('gh issue create --title "#123"') == 'gh issue create --title "#123"'
    assert strip("echo a#b") == "echo a#b"
    assert strip("echo \\# not-a-comment") == "echo \\# not-a-comment"


# ---------------------------------------------------------------------------
# 10. The heredoc-strip fold is a PROPERTY, not a comment (#1620 containment)
# ---------------------------------------------------------------------------


def test_heredoc_strip_runs_once_per_command() -> None:
    """``_strip_heredoc_content`` executes exactly ONCE per detected command.

    Issue #1619 added a second call to ``heredoc_utils._HEREDOC_PATTERN`` on
    this path. That pattern nests a quantifier inside a lazy repeat and
    backtracks exponentially when the closing delimiter is never found, so the
    doubling was not academic: end-to-end through ``_detect_gh_issue_create`` at
    n=23 body lines (168 characters), HEAD cost 3.19s and the un-folded version
    cost 6.43s — OVER the 5-second PreToolUse hook budget. Claude Code PROCEEDS
    on hook timeout, so the regression is a gate ESCAPE, not merely latency, and
    it escapes every PreToolUse gate rather than just this one.

    The ``heredoc_stripped`` parameter folds the two calls back into one. Until
    now that fold was held in place by a source comment alone — the third time
    in this changeset that a comment was the only thing holding a property, and
    the two previous ones were both found asserting something FALSE. A comment
    cannot fail; this can.

    Do NOT fix this by patching the regex here: #1620 is filed and must cover
    all callers at once in ``lib/heredoc_utils.py``.
    """
    real = hook._strip_heredoc_content
    calls: list[str] = []

    with patch.object(
        hook,
        "_strip_heredoc_content",
        side_effect=lambda c: (calls.append(c), real(c))[1],
    ):
        hook._detect_gh_issue_create("cat <<EOF > f\nhi\nEOF")

    assert len(calls) == 1, (
        f"{len(calls)} calls to an exponentially-backtracking regex on one "
        f"command; a second call moves the 5s-hook-budget escape threshold "
        f"one heredoc body line closer for every PreToolUse gate (#1620)."
    )


def test_heredoc_strip_call_counter_can_observe_a_second_call() -> None:
    """Positive control for the counter above.

    A probe that returns 1 is only evidence if it can return 2. Calling the
    inner helper a second time by hand must move the count — otherwise the
    assertion above would hold even against an un-folded implementation and
    would be measuring nothing.
    """
    real = hook._strip_heredoc_content
    calls: list[str] = []

    with patch.object(
        hook,
        "_strip_heredoc_content",
        side_effect=lambda c: (calls.append(c), real(c))[1],
    ):
        command = "cat <<EOF > f\nhi\nEOF"
        hook._detect_gh_issue_create(command)
        baseline = len(calls)
        # Simulate the un-folded shape: the same string stripped a second time.
        hook._gh_issue_create_at_command_position(command)

    assert baseline == 1, f"folded path should call once, got {baseline}"
    assert len(calls) > baseline, (
        "the call counter did not register an additional invocation — the "
        "instrument cannot detect the regression it exists to detect."
    )


def test_heredoc_fold_preserves_the_verdict_both_arms() -> None:
    """The fold is an optimisation, so it must not move a single verdict.

    Passing ``heredoc_stripped`` explicitly (the folded path) and letting the
    callee strip for itself (the un-folded path) must agree on every case,
    refusing AND permitting. Without this, a future edit could satisfy the
    single-call assertion above by passing the WRONG string.
    """
    cases = [
        # Refusing arm — real invocations, inside and outside heredoc context.
        ("gh issue create --title x", True),
        ("cat <<EOF > f\nnotes\nEOF\ngh issue create --title x", True),
        ("git -C . bisect run gh issue create -t x", True),
        # A heredoc BODY line whose argv[0] is literally `gh` still refuses.
        # That is NOT the carve-out leaking: the pre-existing argv[0] path runs
        # on the RAW statements and is left byte-for-byte, precisely so #1619
        # could not weaken anything that already blocked at HEAD. Asserted here
        # so the deliberate asymmetry is recorded rather than rediscovered.
        ("cat <<EOF > f\ngh issue create --title x\nEOF", True),
        # Permitting arm — the carve-out covers the EFFECTIVE-VERB branch: a
        # body line reaching gh-issue-create through a leading token is data
        # being written to a file, not execution.
        ("cat <<EOF > f\nenv gh issue create --title x\nEOF", False),
        ("cat <<EOF > f\ngit -C . bisect run gh issue create -t x\nEOF", False),
        ("cat <<EOF > f\nhi\nEOF", False),
        ("git -C . diff HEAD~1", False),
        ("gh issue list --limit 3", False),
    ]
    for command, expect_refused in cases:
        folded = hook._gh_issue_create_at_command_position(
            command, heredoc_stripped=hook._strip_heredoc_content(command)
        )
        unfolded = hook._gh_issue_create_at_command_position(command)
        assert folded == unfolded, (
            f"fold changed the verdict for {command!r}: folded={folded}, "
            f"un-folded={unfolded}. The fold must be verdict-neutral."
        )
        assert folded is expect_refused, (
            f"{command!r}: expected refused={expect_refused}, got {folded}"
        )


# ---------------------------------------------------------------------------
# 11. The comment scanner uses BASH's separators, not Python's Unicode ones
# ---------------------------------------------------------------------------

#: Characters for which ``str.isspace()`` is True but which bash does NOT treat
#: as a word separator. Bash's default IFS is space, tab and newline only, so
#: after one of these a ``#`` is a LITERAL character mid-word and the rest of
#: the line EXECUTES. A scanner using ``.isspace()`` believed the ``#`` started
#: a word, truncated the statement, and permitted the invocation behind it.
#:
#: Measured end to end with a stub ``gh`` on PATH, the bash half and the gate
#: half driven independently::
#:
#:     env -u FOO<NBSP># gh issue create --title pwned
#:         bash ran gh = True   gate = ALLOW   *** silent permit ***
#:
#: ...and identically for U+2007, U+2028, VT and FF. One pasted character,
#: using only permitted commands. This is the ``xargs -I '#'`` class the
#: scanner exists to close, reached through a different mechanism — and it
#: existed BECAUSE of the scanner: with no comment stripping at all,
#: ``env -u <NBSP># gh issue create`` denies.
UNICODE_SPACE_NOT_BASH_SEPARATOR = [
    pytest.param("\xa0", id="NBSP-U+00A0"),
    pytest.param(" ", id="FIGSP-U+2007"),
    pytest.param(" ", id="LSEP-U+2028"),
    pytest.param("\x0b", id="VT-U+000B"),
    pytest.param("\x0c", id="FF-U+000C"),
]

#: The load-bearing negative control. These ARE bash separators, so the ``#``
#: really does begin a comment and the statement really does execute nothing.
#: Without this arm the parameterised refusal above would pass just as happily
#: against a scanner that refuses EVERY ``#`` — i.e. it would be measuring
#: nothing, and it is a different shape from the ``'#'`` quoting bug that
#: prompted the scanner in the first place.
BASH_SEPARATORS = [
    pytest.param(" ", id="space"),
    pytest.param("\t", id="tab"),
]


@pytest.mark.parametrize("separator", UNICODE_SPACE_NOT_BASH_SEPARATOR)
def test_unicode_space_before_hash_does_not_truncate_a_real_invocation(
    separator: str,
) -> None:
    """Refusing arm: bash executes these, so the gate must refuse them."""
    command = f"env -u FOO{separator}# gh issue create --title pwned"
    assert hook._detect_gh_issue_create(command) is not None, (
        f"SILENT PERMIT: {command!r} — U+{ord(separator):04X} is Unicode "
        f"whitespace but NOT a bash word separator, so bash reads the '#' as "
        f"a literal mid-word character and RUNS gh issue create. Use bash's "
        f"separators (' \\t\\n'), never str.isspace()."
    )


@pytest.mark.parametrize("separator", BASH_SEPARATORS)
def test_real_bash_separator_before_hash_still_truncates(separator: str) -> None:
    """Permitting arm: these really are comments and must stay permitted."""
    command = f"env -u FOO{separator}# gh issue create --title pwned"
    assert hook._detect_gh_issue_create(command) is None, (
        f"CRY-WOLF: {command!r} — U+{ord(separator):04X} IS a bash word "
        f"separator, so the '#' begins a genuine comment and nothing after it "
        f"executes. Narrowing the separator set must not refuse real comments."
    )


def test_comment_scanner_separator_set_is_exactly_bash_ifs() -> None:
    """Drive ``_strip_shell_comment`` directly over both separator classes.

    Locks the predicate itself rather than only its effect through the whole
    detector, so a future edit cannot satisfy the two tests above by changing
    something else on the path.
    """
    strip = hook._strip_shell_comment
    for separator in (" ", "\t", "\n"):
        assert strip(f"env -u FOO{separator}# tail") == f"env -u FOO{separator}", (
            f"U+{ord(separator):04X} is a bash separator; '#' begins a comment."
        )
    for separator in ("\xa0", " ", " ", "\x0b", "\x0c"):
        text = f"env -u FOO{separator}# tail"
        assert strip(text) == text, (
            f"U+{ord(separator):04X} is NOT a bash separator; the '#' is a "
            f"literal mid-word character and nothing may be truncated."
        )
    # str.isspace() is True for every character in the second group — that is
    # precisely why the predicate must not be str.isspace().
    assert all(c.isspace() for c in ("\xa0", " ", " ", "\x0b", "\x0c"))

#!/usr/bin/env python3
"""Ratchet: test files that REPLACE a subprocess environment may only go DOWN.

Issue #1779, AC1. ``tests/conftest.py`` redirects the production activity log and
pipeline sentinel via env vars at import; a subprocess inherits them only when its
``env=`` derives from ``os.environ``. MEASURED 2026-09-12: ``env={**hook_env}`` in
``test_issue_1357_general_purpose_warning.py`` put six ``session_id="test-session"``
records in the production evidence file and deleted the live sentinel.
:func:`tests.helpers.state_isolation.hook_subprocess_env` fixes that instance; this
stops the SHAPE returning. Scope: every ``*.py`` under ``tests/``; an unresolvable
``env=`` name FAILS CLOSED, because resolving one's own uncertainty towards
"nothing here" is how a population silently shrinks. PROXY metric — not every
replaced environment reaches production — so the remainder is pinned debt, and a
pin entry costs three edits (path, ceiling, mark) against two to remove.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pytest

# tests/unit/lib/<this file> -> lib -> unit -> tests -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
TESTS_DIR = _REPO_ROOT / "tests"

#: Callables that start a process and accept ``env=``.
SPAWNER_NAMES = frozenset({"run", "Popen", "check_output", "check_call", "call"})

#: The sanctioned builder: starts from ``os.environ`` AND refuses a value reaching
#: the live ``.claude/`` tree, so a call to it is stronger evidence of inheritance
#: than ``os.environ.copy()``. Recognised by name, or the guard flags its own fix.
SANCTIONED_ENV_BUILDER = "hook_subprocess_env"


def _inherits_environ(
    node: Optional[ast.AST], assigns: Dict[str, List[ast.AST]]
) -> bool:
    """Whether an ``env=`` expression demonstrably starts from ``os.environ``.

    *assigns* maps assignments by name so ``env=x`` resolves; not PROVABLE is False.
    """
    if node is None:
        return True
    if isinstance(node, ast.Constant) and node.value is None:
        return True  # subprocess's own spelling of "inherit"
    if isinstance(node, ast.Dict):
        # A ``**os.environ`` unpack is spelled with a None key.
        return any(
            key is None and _inherits_environ(value, assigns)
            for key, value in zip(node.keys, node.values)
        )
    if isinstance(node, ast.Attribute):
        return node.attr == "environ"
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr == SANCTIONED_ENV_BUILDER:
                return True
            if func.attr in ("copy", "dict"):
                return _inherits_environ(func.value, assigns)
            if func.attr == "environ":
                return True
        if isinstance(func, ast.Name):
            if func.id == SANCTIONED_ENV_BUILDER:
                return True
            if func.id == "dict":
                if node.args:
                    return _inherits_environ(node.args[0], assigns)
                return any(kw.arg is None for kw in node.keywords)
        return False
    if isinstance(node, ast.Name):
        bound = assigns.get(node.id)
        if not bound:
            return False
        return all(_inherits_environ(value, assigns) for value in bound)
    if isinstance(node, ast.IfExp):
        return _inherits_environ(node.body, assigns) and _inherits_environ(
            node.orelse, assigns
        )
    if isinstance(node, ast.BoolOp):
        return all(_inherits_environ(value, assigns) for value in node.values)
    return False


def _assignments(tree: ast.AST) -> Dict[str, List[ast.AST]]:
    """Every value ever assigned to each simple name in *tree*."""
    out: Dict[str, List[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.setdefault(target.id, []).append(node.value)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                out.setdefault(node.target.id, []).append(node.value)
    return out


def _key(path: Path) -> str:
    """Repo-relative POSIX key. Never a basename: ``conftest.py`` collides."""
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


#: Memo for DEFAULT-roots only: the synthetic arms rewrite files between calls.
_LIVE_SITES_MEMO: Optional[Dict[str, List[int]]] = None


def env_replacing_sites(roots: Optional[Iterable[Path]] = None) -> Dict[str, List[int]]:
    """Scan for spawn call sites whose ``env=`` discards ``os.environ``.

    *roots* defaults to ``tests/``; a FRESH dict, so no caller can corrupt the memo.
    """
    if roots is None:
        global _LIVE_SITES_MEMO
        if _LIVE_SITES_MEMO is None:
            _LIVE_SITES_MEMO = _scan((TESTS_DIR,))
        return {key: list(lines) for key, lines in _LIVE_SITES_MEMO.items()}
    return _scan(roots)


def _scan(roots: Iterable[Path]) -> Dict[str, List[int]]:
    """Uncached scan of *roots*. See :func:`env_replacing_sites`."""
    sites: Dict[str, List[int]] = {}
    for root in roots:
        if not Path(root).is_dir():
            continue
        for path in sorted(Path(root).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, ValueError):
                # A file that no longer parses cannot be collected by pytest
                # either, so the suite is already red for it.
                continue
            assigns = _assignments(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = (
                    func.attr
                    if isinstance(func, ast.Attribute)
                    else (func.id if isinstance(func, ast.Name) else None)
                )
                if name not in SPAWNER_NAMES:
                    continue
                for keyword in node.keywords:
                    if keyword.arg == "env" and not _inherits_environ(
                        keyword.value, assigns
                    ):
                        sites.setdefault(_key(path), []).append(node.lineno)
    return sites


# ---------------------------------------------------------------------------
# The pin
# ---------------------------------------------------------------------------

#: Test modules that still pass a subprocess an environment not derived from
#: ``os.environ``. MEASURED 2026-09-12 by :func:`env_replacing_sites` over
#: ``tests/`` AFTER test_issue_1357 moved to the helper. DEBT, not a permission slip.
PINNED_ENV_REPLACERS: "frozenset[str]" = frozenset(
    {
        "tests/integration/test_install_integration.py",
        "tests/integration/test_intent_classifier_observe_mode.py",
        "tests/integration/test_missing_hook_resilience.py",
        "tests/integration/test_session_id_fallback_chain.py",
        "tests/regression/regression/test_issue_1036_submodule_hook_paths.py",
        "tests/regression/regression/test_issue_1610_deploy_state.py",
        "tests/regression/test_ci_summary_gate.py",
        "tests/regression/test_drain_commit_gate.py",
        "tests/regression/test_issue_1376_write_side_sentinel_path.py",
        "tests/regression/test_issue_1747_manifest_completeness.py",
        "tests/unit/hooks/test_classifier_robustness.py",
        "tests/unit/hooks/test_unified_prompt_validator_clarification.py",
        "tests/unit/lib/test_intent_classifier.py",
    }
)

#: Ceiling on the pin, asserted by EQUALITY so a shrink is also a visible diff.
#: History, DOWN only — 13: Issue #1779 landed one below the live 14, because
#: converting test_issue_1357 to the shared helper closed the measured leak.
ENV_REPLACER_CEILING = 13

#: Highest ceiling ever REVIEWED, so a raise costs a second visible edit.
CEILING_HIGH_WATER_MARK = 13


def _ceiling_violations(pin_size: int, ceiling: int, mark: int) -> List[str]:
    """Every ceiling invariant ``(pin_size, ceiling, mark)`` breaks.

    Pure, so the table can drive values other than this module's own constants —
    an assertion over two literals in one file is unfalsifiable in-process.
    """
    violations: List[str] = []
    if pin_size > ceiling:
        violations.append(f"pin grew to {pin_size}, over the ceiling ({ceiling})")
    if ceiling > mark:
        violations.append(f"ceiling RAISED to {ceiling}, over the reviewed mark {mark}")
    if ceiling != pin_size:
        violations.append(f"ceiling ({ceiling}) no longer equals the pin ({pin_size})")
    if mark - ceiling != 0:
        violations.append(f"residual headroom is {mark - ceiling}; lower the mark")
    return violations


class TestInstrumentIntegrity:
    """A probe that returns zero is not evidence of zero."""

    def test_live_population_is_non_empty(self) -> None:
        """POSITIVE CONTROL: zero is instrument failure, not a clean tree."""
        assert env_replacing_sites(), (
            "Zero env-replacing call sites found across tests/. Zero is "
            "instrument failure, not a clean tree — every pinned file below "
            "must still be found. Fix the detector before touching the pin."
        )

    def test_the_canary_can_actually_fail(self, tmp_path: Path) -> None:
        """NEGATIVE CONTROL: an empty tree really does yield zero."""
        assert env_replacing_sites(roots=[tmp_path]) == {}, (
            "The scan returned a population from an empty directory, so the "
            "non-empty canary is watching something other than the scan root."
        )


class TestGuardRefusesAndPermits:
    """Both arms, on synthetic trees.

    COVERED CLASS: any spawn call under ``tests/`` whose ``env=`` cannot be shown
    to derive from ``os.environ`` — dict literal, unrelated constructed dict, or a
    local name bound to one. Not merely "a file resembling test_issue_1357".
    """

    def test_refuses_a_replaced_environment_of_a_different_shape(
        self, tmp_path: Path
    ) -> None:
        """WATCHED REFUSING, on a shape unlike the reproducer.

        Reproducer: ``subprocess.run(..., env={**hook_env})``. Here: ``Popen``, env
        a NAME bound to ``dict(PATH=...)``, the call inside a class method.
        """
        offender = tmp_path / "spawns_with_a_scrubbed_env.py"
        offender.write_text(
            "import subprocess\n"
            "\n"
            "class Runner:\n"
            "    def go(self, argv):\n"
            "        scrubbed = dict(PATH='/usr/bin')\n"
            "        scrubbed['HOME'] = '/tmp'\n"
            "        return subprocess.Popen(argv, env=scrubbed)\n",
            encoding="utf-8",
        )
        detected = env_replacing_sites(roots=[tmp_path])
        assert _key(offender) in detected, (
            "A replaced subprocess environment was NOT detected. The ratchet "
            "cannot fail, so it is not enforcement."
        )
        assert set(detected) - PINNED_ENV_REPLACERS == {_key(offender)}, (
            "The offender must surface as an UNPINNED file — that difference "
            "is what makes test_live_state_matches_pin fail."
        )

    @pytest.mark.parametrize(
        "source,why",
        [
            (
                "import os, subprocess\n"
                "def go(argv):\n"
                "    return subprocess.run(argv, env={**os.environ, 'X': '1'})\n",
                "a dict display unpacking os.environ inherits the redirects",
            ),
            (
                "import subprocess\n"
                "from tests.helpers.state_isolation import hook_subprocess_env\n"
                "def go(argv):\n"
                "    return subprocess.run(argv, env=hook_subprocess_env({'X': '1'}))\n",
                "the sanctioned helper must not be flagged, or nobody uses it",
            ),
        ],
    )
    def test_permits_every_inheriting_shape(
        self, source: str, why: str, tmp_path: Path
    ) -> None:
        """WATCHED PERMITTING: a guard that refuses everything is useless."""
        (tmp_path / "inheriting.py").write_text(source, encoding="utf-8")
        assert env_replacing_sites(roots=[tmp_path]) == {}, why

    def test_the_sanctioned_helper_refuses_a_production_path(self) -> None:
        """The helper watched refusing at its LIVE entry point, in two shapes."""
        from tests.helpers.state_isolation import (
            HookEnvIsolationError,
            hook_subprocess_env,
        )

        live_tree = _REPO_ROOT / ".claude" / "logs" / "activity"
        with pytest.raises(HookEnvIsolationError) as excinfo:
            hook_subprocess_env({"AUTONOMOUS_DEV_ACTIVITY_LOG_DIR": str(live_tree)})
        assert "AUTONOMOUS_DEV_ACTIVITY_LOG_DIR" in str(excinfo.value)

        with pytest.raises(HookEnvIsolationError):
            hook_subprocess_env({"PIPELINE_STATE_FILE": ""})

    def test_the_sanctioned_helper_permits_the_isolated_default(self) -> None:
        """And watched permitting, against the environment conftest installed."""
        from tests.helpers.state_isolation import ISOLATION_VARS, hook_subprocess_env

        env = hook_subprocess_env({"CLAUDE_SESSION_ID": "ratchet-probe"})
        assert env["CLAUDE_SESSION_ID"] == "ratchet-probe"
        for name in ISOLATION_VARS:
            assert env[name].strip(), f"{name} must reach the subprocess"


class TestCeilingArithmetic:
    """The ceiling invariants, driven with values other than this file's own."""

    @pytest.mark.parametrize(
        "pin_size,ceiling,mark,expect",
        [
            (13, 13, 13, None),
            (14, 13, 13, "pin grew to 14"),
            (13, 14, 13, "RAISED to 14"),
            (12, 12, 13, "residual headroom is 1"),
        ],
    )
    def test_ceiling_violation_table(
        self, pin_size: int, ceiling: int, mark: int, expect: Optional[str]
    ) -> None:
        violations = _ceiling_violations(pin_size, ceiling, mark)
        if expect is None:
            assert violations == [], violations
        else:
            assert any(expect in v for v in violations), violations

    def test_this_modules_constants_are_consistent(self) -> None:
        violations = _ceiling_violations(
            len(PINNED_ENV_REPLACERS), ENV_REPLACER_CEILING, CEILING_HIGH_WATER_MARK
        )
        assert violations == [], "\n".join(violations)


class TestRatchet:
    """Reality must equal the pin, both directions.

    The ``stale`` arm replaces a per-file sweep: a pin entry that no longer
    replaces an environment (deleted file included) surfaces from the same scan.
    """

    def test_live_state_matches_pin(self) -> None:
        live = set(env_replacing_sites())
        unpinned = sorted(live - PINNED_ENV_REPLACERS)
        stale = sorted(PINNED_ENV_REPLACERS - live)

        assert not unpinned, (
            f"{len(unpinned)} test file(s) pass a subprocess an environment not "
            f"derived from os.environ: {unpinned}. Such a subprocess loses "
            "AUTONOMOUS_DEV_ACTIVITY_LOG_DIR and PIPELINE_STATE_FILE and writes "
            "the REAL .claude/ tree (Issue #1779, AC1).\n"
            "REQUIRED NEXT ACTION: build the env with "
            "tests.helpers.state_isolation.hook_subprocess_env(). Pinning the "
            "file is not an acceptable resolution for a subprocess that runs one "
            "of this repo's hooks."
        )
        assert not stale, (
            f"PINNED_ENV_REPLACERS names {len(stale)} file(s) that no longer "
            f"replace the environment: {stale}. Delete them from the pin and "
            "lower ENV_REPLACER_CEILING and CEILING_HIGH_WATER_MARK by the same "
            "amount — that deletion IS the ratchet advancing."
        )

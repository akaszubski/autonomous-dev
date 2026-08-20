"""Subprocess-level regression tests for PreToolUseWrite-protect-sensitive.sh.

Issue #1587: this shell hook produced a valid deny payload on two paths and
recorded nothing, so every refusal it made was invisible in
``.claude/logs/hook-blocks.jsonl``. Zero rows meant *unmeasured*, not *never
fired*.

These tests drive the real hook as a subprocess, the way Claude Code would.
They are structured around the evidence rules the issue establishes:

* the guard is watched REFUSING **and** PERMITTING, on **both** refusal rules
  (sensitive-file pattern and PROJECT.md) — not just the one that prompted it;
* every probe has a positive and a negative control, so an empty result is
  distinguishable from a broken instrument;
* telemetry failure is exercised four ways, and each must degrade to
  "refused but unrecorded", never to "allowed".

The telemetry log is anchored at the temp repo root, so no test row can reach
the real ``.claude/logs/hook-blocks.jsonl``. ``CLAUDE_PROJECT_DIR`` is popped
from the inherited environment for exactly that reason: Claude Code sets it,
and inheriting it would redirect every test row into the live log.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = (
    REPO_ROOT
    / "plugins"
    / "autonomous-dev"
    / "hooks"
    / "PreToolUseWrite-protect-sensitive.sh"
)
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
PERF_REPORT_PATH = REPO_ROOT / "scripts" / "hook_perf_report.py"

HOOK_NAME = "PreToolUseWrite-protect-sensitive.sh"
BLOCK_LOG_RELATIVE = Path(".claude") / "logs" / "hook-blocks.jsonl"

# Utilities the hook (and the subprocess launcher) need on PATH, minus
# python3. Used to build a curated PATH that proves the no-python3
# degradation path.
_HOOK_PATH_UTILITIES = ("bash", "cat", "jq", "grep", "dirname", "git", "env")

# Resolved once so PATH overrides in tests cannot hide the launcher itself.
BASH = shutil.which("bash") or "/bin/bash"


def _load_block_shapes() -> frozenset:
    """Read BLOCK_SHAPES from the real report script.

    Cross-validation, not a hardcoded copy: if the report's notion of which
    decision shapes count as blocks drifts, these tests move with it rather
    than assert against a stale third copy.
    """
    spec = importlib.util.spec_from_file_location(
        "_hook_perf_report_for_protect_sensitive_test", PERF_REPORT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BLOCK_SHAPES


def _read_block_rows(root: Path) -> list:
    """Return parsed telemetry rows under ``root``, or [] when absent."""
    log_path = root / BLOCK_LOG_RELATIVE
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _decision(result: subprocess.CompletedProcess) -> str:
    """Extract permissionDecision, or ``"no output"`` when stdout is empty.

    This hook emits a TOP-LEVEL ``permissionDecision`` rather than the
    documented ``hookSpecificOutput.permissionDecision`` envelope. That
    divergence is reported, not fixed, under this issue — see the
    characterization test below.
    """
    if not result.stdout.strip():
        return "no output"
    return json.loads(result.stdout)["permissionDecision"]


def _init_repo(repo_dir: Path) -> Path:
    """Initialize ``repo_dir`` as a git repo and return its resolved path."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--quiet", str(repo_dir)],
        check=True,
        capture_output=True,
    )
    return repo_dir.resolve()


def _run_hook(
    payload: dict | str,
    *,
    cwd: Path,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the hook as a subprocess with ``payload`` on stdin."""
    full_env = os.environ.copy()
    # Claude Code sets CLAUDE_PROJECT_DIR. Inheriting it would anchor every
    # test row at the REAL repo log. Pop it; tests that need it set it back.
    full_env.pop("CLAUDE_PROJECT_DIR", None)
    # Telemetry assertions require the recorder enabled.
    full_env.pop("HOOK_TELEMETRY_DISABLED", None)
    full_env.pop("HOOK_RECOVERY_DISABLED", None)
    if env:
        full_env.update(env)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [BASH, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=full_env,
        timeout=30,
    )


def _write_payload(file_path: str, **extra) -> dict:
    """Build a payload in the shape this hook actually reads.

    The hook reads ``.parameters.file_path``. That is NOT the field Claude
    Code sends (``tool_input.file_path``) — a reported, unfixed defect that
    the characterization test below pins.
    """
    payload = {"parameters": {"file_path": file_path}}
    payload.update(extra)
    return payload


def _count_deny_emitters(text: str) -> int:
    """Count places in a shell source that emit a deny payload."""
    return text.count('"permissionDecision": "deny"')


class TestIssue1587RefusalIsRecorded:
    """The refusal and its telemetry row must be one indivisible act."""

    def test_regression_issue_1587_sensitive_file_deny_writes_block_row(
        self, tmp_path: Path
    ) -> None:
        """A refused write to a sensitive file MUST emit one countable row."""
        repo = _init_repo(tmp_path / "repo")
        assert _read_block_rows(repo) == [], "temp repo must start with no rows"

        result = _run_hook(
            _write_payload(".env", tool_name="Write", session_id="sess-1587"),
            cwd=repo,
        )

        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        assert _decision(result) == "deny", f"stdout={result.stdout!r}"

        rows = _read_block_rows(repo)
        assert len(rows) == 1, f"expected exactly 1 telemetry row, got {len(rows)}"
        row = rows[0]
        assert row["hook_name"] == HOOK_NAME
        assert row["decision_shape"] in _load_block_shapes(), (
            f"decision_shape={row['decision_shape']!r} is not in BLOCK_SHAPES, "
            "so hook_perf_report.py would not count this refusal as a block"
        )
        assert "Cannot write to sensitive file" in row["reason"]
        assert ".env" in row["reason"]
        assert row["metadata"]["rule"] == "sensitive_file_pattern"
        assert row["metadata"]["tool_name"] == "Write"
        assert row["metadata"]["file_path"] == ".env"
        assert row["metadata"]["envelope"] == "top-level permissionDecision"
        assert row["session_id"] == "sess-1587"

    def test_regression_issue_1587_project_md_deny_writes_block_row(
        self, tmp_path: Path
    ) -> None:
        """The SECOND refusal rule must record too.

        Authored to a different shape than the reproducer on purpose: a guard
        proven only against the path that prompted it is scoped to that
        instance. The covered class is "every refusal this hook can produce",
        and this hook has exactly two.
        """
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            _write_payload(".claude/PROJECT.md", tool_name="Edit"),
            cwd=repo,
        )

        assert _decision(result) == "deny", f"stdout={result.stdout!r}"
        rows = _read_block_rows(repo)
        assert len(rows) == 1, f"expected exactly 1 telemetry row, got {len(rows)}"
        assert rows[0]["hook_name"] == HOOK_NAME
        assert rows[0]["metadata"]["rule"] == "project_md_protected"
        assert rows[0]["decision_shape"] in _load_block_shapes()
        assert "PROJECT.md is protected" in rows[0]["reason"]

    def test_regression_issue_1587_allow_writes_no_row(self, tmp_path: Path) -> None:
        """The PERMITTING arm: a permitted write must record nothing.

        This is the negative control for every count above. A recorder that
        also fired on allows would corrupt every number derived from the
        block log, and the refusing tests alone cannot detect that.
        """
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            _write_payload("src/app.py", tool_name="Write"),
            cwd=repo,
        )

        assert result.returncode == 0, f"hook exited {result.returncode}"
        assert _decision(result) == "allow", f"stdout={result.stdout!r}"
        assert _read_block_rows(repo) == [], "allow path must not write a row"

    def test_regression_issue_1587_row_anchored_at_repo_root_not_cwd(
        self, tmp_path: Path
    ) -> None:
        """A refusal issued from a subdirectory must record at the repo root.

        Without an explicit anchor the row lands in
        ``<subdir>/.claude/logs/``, invisible to every report that reads the
        repo's log. Same latent bug the reference fix (b984ad8c) corrected.
        """
        repo = _init_repo(tmp_path / "repo")
        subdir = repo / "deep" / "nested"
        subdir.mkdir(parents=True)

        result = _run_hook(_write_payload("config/secrets.yml"), cwd=subdir)

        assert _decision(result) == "deny", f"stdout={result.stdout!r}"
        assert len(_read_block_rows(repo)) == 1, "row must land at the repo root"
        assert _read_block_rows(subdir) == [], (
            "row must NOT land in the invoking subdirectory"
        )

    def test_regression_issue_1587_explicit_project_dir_anchors_log(
        self, tmp_path: Path
    ) -> None:
        """CLAUDE_PROJECT_DIR takes precedence over git rev-parse.

        Positive control for the injection point the other tests rely on:
        proves the anchor is genuinely honoured rather than coincidentally
        matching cwd.
        """
        repo = _init_repo(tmp_path / "repo")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        result = _run_hook(
            _write_payload("deploy/server.pem"),
            cwd=repo,
            env={"CLAUDE_PROJECT_DIR": str(elsewhere)},
        )

        assert _decision(result) == "deny"
        assert len(_read_block_rows(elsewhere)) == 1, "row must follow the anchor"
        assert _read_block_rows(repo) == [], "row must not land at the git root"


class TestIssue1587TelemetryNeverOutranksEnforcement:
    """Four ways recording can fail. All four must still refuse."""

    def test_regression_issue_1587_unwritable_log_still_denies(
        self, tmp_path: Path
    ) -> None:
        """An unwritable telemetry log must not convert a block into an allow.

        ``.claude`` is created as a regular FILE so ``mkdir(parents=True)``
        inside the recorder raises NotADirectoryError. uid-independent,
        unlike chmod, which root ignores.
        """
        repo = _init_repo(tmp_path / "repo")
        (repo / ".claude").write_text("not a directory\n", encoding="utf-8")

        result = _run_hook(_write_payload(".env"), cwd=repo)

        assert _decision(result) == "deny", (
            "telemetry failure must degrade to 'refused, unrecorded', never to "
            f"'allow'. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert result.returncode == 0, f"hook exited {result.returncode}"
        # Positive control: the recorder really did fail. Without this the
        # test would pass just as happily against a recorder that succeeded.
        assert "[hook-telemetry]" in result.stderr, (
            f"expected the recorder's stderr fallback; stderr={result.stderr!r}"
        )

    def test_regression_issue_1587_raising_recorder_still_denies(
        self, tmp_path: Path
    ) -> None:
        """A recorder that RAISES must not break the refusal.

        A ``sitecustomize`` shim patches ``log_block_event`` at interpreter
        startup, before the hook's python3 subprocess imports it — a real
        subprocess proof rather than an in-process mock.
        """
        repo = _init_repo(tmp_path / "repo")
        shim_dir = tmp_path / "shim"
        shim_dir.mkdir()
        (shim_dir / "sitecustomize.py").write_text(
            "import sys, os\n"
            "sys.path.insert(0, os.environ['AD_LIB'])\n"
            "import hook_telemetry\n"
            "def _boom(**kwargs):\n"
            "    raise RuntimeError('recorder exploded (injected)')\n"
            "hook_telemetry.log_block_event = _boom\n"
            "sys.stderr.write('RECORDER_PATCHED\\n')\n",
            encoding="utf-8",
        )

        result = _run_hook(
            _write_payload(".env"),
            cwd=repo,
            env={"AD_LIB": str(LIB_DIR), "PYTHONPATH": str(shim_dir)},
        )

        # Positive control: a probe whose instrument did not engage proves
        # nothing. Confirm the patch landed before trusting the deny.
        assert "RECORDER_PATCHED" in result.stderr, (
            f"sitecustomize shim did not run; stderr={result.stderr!r}"
        )
        assert _decision(result) == "deny", (
            f"raising recorder broke enforcement; stdout={result.stdout!r}"
        )
        assert result.returncode == 0, f"hook exited {result.returncode}"
        assert _read_block_rows(repo) == [], "raising recorder cannot have logged"

    def test_regression_issue_1587_telemetry_disabled_still_denies(
        self, tmp_path: Path
    ) -> None:
        """The HOOK_TELEMETRY_DISABLED rollback switch must not disable the guard."""
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            _write_payload(".env"),
            cwd=repo,
            env={"HOOK_TELEMETRY_DISABLED": "1"},
        )

        assert _decision(result) == "deny", f"stdout={result.stdout!r}"
        assert _read_block_rows(repo) == [], "disabled telemetry must write no row"

    def test_regression_issue_1587_missing_python3_still_denies(
        self, tmp_path: Path
    ) -> None:
        """With no python3 on PATH the hook must still refuse.

        PATH is rebuilt from symlinks to only the utilities the hook needs,
        deliberately excluding python3, so the ``command -v`` degradation
        branch is genuinely exercised rather than assumed.
        """
        repo = _init_repo(tmp_path / "repo")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for util in _HOOK_PATH_UTILITIES:
            real = shutil.which(util)
            if real:
                (bin_dir / util).symlink_to(real)

        curated_path = str(bin_dir)
        # Negative control on the instrument: the curated PATH must genuinely
        # hide python3, otherwise this test proves nothing.
        assert shutil.which("python3", path=curated_path) is None, (
            "curated PATH still exposes python3; the probe would be vacuous"
        )

        result = _run_hook(
            _write_payload(".env"),
            cwd=repo,
            env={"PATH": curated_path},
        )

        assert _decision(result) == "deny", (
            f"missing python3 broke enforcement; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        assert result.returncode == 0, f"hook exited {result.returncode}"
        assert "python3 unavailable" in result.stderr, (
            f"expected the degradation notice; stderr={result.stderr!r}"
        )
        assert _read_block_rows(repo) == []


class TestIssue1587SingleRefusalSurface:
    """The mechanism, not the patch: only one place may emit a refusal."""

    def test_regression_issue_1587_hook_has_exactly_one_deny_emitter(self) -> None:
        """Adding a third refusal path with its own heredoc must fail here.

        The defect being fixed is not "two heredocs lacked a log call" — it
        is that emitting a refusal and recording it were separable at all.
        This guard fails the moment that surface is reintroduced.
        """
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert _count_deny_emitters(source) == 1, (
            "the hook must have exactly ONE deny-payload emitter "
            "(deny_and_record); found "
            f"{_count_deny_emitters(source)}"
        )
        assert "deny_and_record()" in source, "the fused emitter must exist"

    def test_regression_issue_1587_deny_emitter_counter_can_fail(self) -> None:
        """Positive control for the counter above.

        A guard observed only passing is indistinguishable from a guard that
        cannot fail. This feeds the counter a source with the separable
        surface restored and requires it to report 2.
        """
        separable = (
            'if grep -q secret; then\n'
            '  cat <<EOF\n{\n  "permissionDecision": "deny",\n'
            '  "reason": "a"\n}\nEOF\nfi\n'
            'if grep -q key; then\n'
            '  cat <<EOF\n{\n  "permissionDecision": "deny",\n'
            '  "reason": "b"\n}\nEOF\nfi\n'
        )
        assert _count_deny_emitters(separable) == 2
        assert _count_deny_emitters('echo \'{"permissionDecision": "allow"}\'') == 0


class TestIssue1587ReportedNotFixed:
    """Characterization of defects found alongside, reported under #1588.

    These tests do NOT endorse the behaviour they pin. They exist so that a
    future correction is loud rather than silent: fixing either one flips
    this hook from refusing nothing in production to enforcing a broad
    pattern list, which is a policy change that must be made deliberately.
    """

    def test_characterization_real_payload_shape_reaches_no_refusal(
        self, tmp_path: Path
    ) -> None:
        """Claude Code sends ``tool_input.file_path``; the hook reads
        ``parameters.file_path``, so the deny paths are unreachable in
        production. When the field is corrected, update this test.
        """
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": ".env"},
                "session_id": "real-shape",
            },
            cwd=repo,
        )

        assert _decision(result) == "allow", (
            "if this now denies, the input-field defect was fixed — that is a "
            "POLICY change (this hook would begin blocking .env/.git/PROJECT.md "
            "writes). Confirm it was intended, then update this test."
        )
        assert _read_block_rows(repo) == []

    def test_characterization_envelope_is_top_level_not_hook_specific(
        self, tmp_path: Path
    ) -> None:
        """The hook emits a top-level ``permissionDecision``.

        ``docs/HOOKS.md`` documents ``hookSpecificOutput.permissionDecision``
        for PreToolUse. A top-level field is not the documented envelope, so
        Claude Code would treat this output as carrying no decision at all.

        Asserted against the EMITTED payload, not the source text — source
        text matches comments too, and the comments necessarily name the
        correct envelope while describing the divergence.
        """
        repo = _init_repo(tmp_path / "repo")
        result = _run_hook(_write_payload(".env"), cwd=repo)

        emitted = json.loads(result.stdout)
        assert "hookSpecificOutput" not in emitted, (
            "if the envelope was corrected, this hook's refusals became live — "
            "a POLICY change. Confirm it was intended, then update this test."
        )
        assert emitted["permissionDecision"] == "deny"
        # The documented field name is absent from the emitted reason channel
        # too: this envelope carries "reason", not "permissionDecisionReason".
        assert "permissionDecisionReason" not in emitted
        assert "reason" in emitted


@pytest.mark.parametrize(
    "file_path,expected",
    [
        (".env", "deny"),
        (".env.production", "deny"),
        ("app/credentials.json", "deny"),
        ("config/secrets.yaml", "deny"),
        ("keys/private_key.txt", "deny"),
        ("certs/server.pem", "deny"),
        ("certs/server.key", "deny"),
        (".git/config", "deny"),
        (".claude/PROJECT.md", "deny"),
        ("README.md", "allow"),
        ("src/app.py", "allow"),
        ("docs/environment.md", "allow"),
    ],
)
def test_regression_issue_1587_refusal_policy_unchanged(
    file_path: str, expected: str, tmp_path: Path
) -> None:
    """Pin the refusal policy so the observability fix cannot have moved it.

    Both arms are present: six deny shapes across both rules, and three
    allows including ``docs/environment.md``, which contains "environment"
    but must not trip the ``.env`` pattern.
    """
    repo = _init_repo(tmp_path / "repo")
    result = _run_hook(_write_payload(file_path), cwd=repo)
    assert _decision(result) == expected, (
        f"{file_path}: expected {expected}, got {result.stdout!r}"
    )

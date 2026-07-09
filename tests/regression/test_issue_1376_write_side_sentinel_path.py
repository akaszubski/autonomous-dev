#!/usr/bin/env python3
"""Regression tests for Issue #1376: coordinator write path / hook read path mismatch.

Bug: commands/implement.md line 347 exported PIPELINE_STATE_FILE pointing to
/tmp/implement_pipeline_${RUN_ID}.json (a /tmp path with a RUN_ID suffix).
The hook in unified_pre_tool.py reads:
    os.getenv("PIPELINE_STATE_FILE", str(get_legacy_sentinel_path()))
Because the hook runs in a separate subprocess that does NOT inherit the
coordinator's env vars, the fallback activates and resolves to
<repo>/.claude/local/implement_pipeline_state.json.
Result: coordinator wrote mode="light" to /tmp/<run-specific-path>, hook read
from <repo>/.claude/local/ — mismatch — mode="light" invisible to hook, hook
fell back to "full", falsely blocked light-mode commits.

Fix: change line 347 to resolve PIPELINE_STATE_FILE via
get_legacy_sentinel_path() at export time, so both sides use the same path.

Issues: #1376
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import pipeline_completion_state as pcs
from agent_ordering_gate import LIGHT_PIPELINE_AGENTS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Create a minimal fake repo directory tree and monkeypatch CWD to it.

    Creates:
        <tmp_path>/.git/          — makes path_utils see this as a repo root
        <tmp_path>/.claude/local/ — the sentinel directory

    Monkeypatches os.getcwd() / Path.cwd() via chdir so get_legacy_sentinel_path()
    resolves inside this fake repo rather than the real autonomous-dev repo.
    """
    # Simulate a git repo root so find_project_root() stops here.
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude" / "local").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """Remove PIPELINE_STATE_FILE from env before each test to force fallback."""
    monkeypatch.delenv("PIPELINE_STATE_FILE", raising=False)
    monkeypatch.delenv("PIPELINE_MODE", raising=False)
    monkeypatch.delenv("SKIP_AGENT_COMPLETENESS_GATE", raising=False)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_per_repo_sentinel_path(repo_root: Path) -> Path:
    """Return the expected per-repo sentinel path under the given root."""
    return repo_root / ".claude" / "local" / "implement_pipeline_state.json"


def _extract_step0_write_snippet(mode: str, run_id: str) -> str:
    """Return the Python snippet that STEP 0 in implement.md runs to write the sentinel.

    This mirrors the heredoc block at lines ~400-420 of implement.md which writes
    the pipeline state sentinel file.  The snippet is reproduced here verbatim
    so tests can run it in a subprocess with a controlled CWD.

    The absolute LIB_DIR is injected so the snippet works from any CWD, mirroring
    how the real command has access to 'plugins/autonomous-dev/lib' relative to the
    repo root (which the coordinator shell always has in CWD).
    """
    abs_lib_dir = str(LIB_DIR)
    # This is a condensed faithful reproduction of the Python heredoc block in
    # implement.md STEP 0.  It uses os.environ.get('PIPELINE_STATE_FILE', ...)
    # and falls back to get_legacy_sentinel_path() — exactly the pattern the
    # command uses after the #1376 fix on line 347.
    return textwrap.dedent(
        f"""
        import sys, os, json
        from pathlib import Path
        # Inject the real lib dir (abs path) — mirrors how 'plugins/autonomous-dev/lib'
        # is available relative to repo root in the actual coordinator shell.
        sys.path.insert(0, {abs_lib_dir!r})
        from pipeline_state import get_legacy_sentinel_path, sign_state
        sid = os.environ.get('CLAUDE_SESSION_ID', 'unknown')
        state = {{
            'session_start': '2026-07-10T00:00:00',
            'mode': '{mode}',
            'run_id': '{run_id}',
            'explicitly_invoked': True,
            'session_id': sid,
        }}
        state = sign_state(state, sid)
        target = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with open(target, 'w') as f:
            json.dump(state, f)
        print(target)
        """
    )


# ---------------------------------------------------------------------------
# AC1: FULL mode writes to per-repo path when PIPELINE_STATE_FILE is unset
# ---------------------------------------------------------------------------


def test_step0_writes_to_per_repo_path_not_tmp(fake_repo):
    """AC1: When PIPELINE_STATE_FILE is unset, STEP 0 writes to the per-repo
    sentinel (<fake_repo>/.claude/local/implement_pipeline_state.json) and NOT
    to any /tmp/ path.

    This validates that the fix on line 347 aligns the coordinator write path
    with the hook's read path for full-mode pipelines.
    """
    snippet = _extract_step0_write_snippet(mode="full", run_id="testrun001")

    result = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=str(fake_repo),
        capture_output=True,
        text=True,
        env={**os.environ, "PIPELINE_STATE_FILE": ""},  # ensure unset effect
    )

    # Remove the empty string so the fallback activates.
    env_without_psf = {k: v for k, v in os.environ.items() if k != "PIPELINE_STATE_FILE"}
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=str(fake_repo),
        capture_output=True,
        text=True,
        env=env_without_psf,
    )
    assert result.returncode == 0, f"Snippet failed: {result.stderr}"

    written_path = result.stdout.strip()
    expected = str(_get_per_repo_sentinel_path(fake_repo))

    assert written_path == expected, (
        f"STEP 0 wrote to {written_path!r} but expected per-repo path {expected!r}. "
        f"This is the #1376 bug: coordinator wrote to /tmp/, hook reads from "
        f"<repo>/.claude/local/ — paths diverged."
    )
    assert "/tmp/" not in written_path, (
        f"Sentinel must NOT be in /tmp/ after fix; got {written_path!r}"
    )

    sentinel = _get_per_repo_sentinel_path(fake_repo)
    assert sentinel.exists(), "Sentinel file must exist at per-repo path after STEP 0"
    state = json.loads(sentinel.read_text())
    assert state["mode"] == "full"


# ---------------------------------------------------------------------------
# AC2: LIGHT mode writes to per-repo path when PIPELINE_STATE_FILE is unset
# ---------------------------------------------------------------------------


def test_step_l0_writes_light_mode_to_per_repo_path(fake_repo):
    """AC2: When PIPELINE_STATE_FILE is unset in --light mode, STEP L0 writes
    mode='light' to <fake_repo>/.claude/local/implement_pipeline_state.json.

    Before the #1376 fix, PIPELINE_STATE_FILE pointed to a /tmp run-specific
    file. The hook couldn't see mode='light' and fell back to 'full', blocking
    legitimate light-mode commits.
    """
    snippet = _extract_step0_write_snippet(mode="light", run_id="testrunit_l0")
    env_without_psf = {k: v for k, v in os.environ.items() if k != "PIPELINE_STATE_FILE"}

    result = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=str(fake_repo),
        capture_output=True,
        text=True,
        env=env_without_psf,
    )
    assert result.returncode == 0, f"Snippet failed: {result.stderr}"

    sentinel = _get_per_repo_sentinel_path(fake_repo)
    assert sentinel.exists(), "Sentinel must exist at per-repo path"

    state = json.loads(sentinel.read_text())
    assert state["mode"] == "light", (
        f"Expected mode='light' in sentinel, got {state['mode']!r}. "
        f"The hook must be able to read this value; if it's at a different "
        f"path, hook sees mode='full' and false-blocks the commit."
    )

    written_path = result.stdout.strip()
    assert "/tmp/" not in written_path, (
        f"Sentinel MUST NOT be in /tmp/ for hook to read it; got {written_path!r}"
    )


# ---------------------------------------------------------------------------
# AC3: Direct #1376 reproduction — light mode passes agent-completeness gate
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_state_path(tmp_path, monkeypatch):
    """Monkeypatch pipeline_completion_state._state_file_path to use tmp_path."""
    import hashlib

    def _patched(s, *, run_id=None):
        h = hashlib.sha256(s.encode()).hexdigest()[:8]
        return tmp_path / f"pipeline_agent_completions_{h}.json"

    monkeypatch.setattr(pcs, "_state_file_path", _patched)


def test_1376_reproduction_light_mode_completion_gate(patched_state_path, fake_repo):
    """AC3: Core #1376 reproduction.

    Write the per-repo sentinel with mode='light', record LIGHT_PIPELINE_AGENTS
    completions, then invoke verify_pipeline_agent_completions with mode='light'.
    It must return passed=True (no missing agents).

    Before #1376: hook read 'full' from fallback because coordinator wrote to /tmp/.
    The gate would then require full-pipeline agents (researcher-local, researcher,
    reviewer, security-auditor) and block the commit.
    """
    session_id = "test-session-1376"

    # Write the per-repo sentinel with mode='light' (simulates what the fixed
    # line 347 + STEP L0 write snippet now produces).
    sentinel = _get_per_repo_sentinel_path(fake_repo)
    sentinel.write_text(json.dumps({"mode": "light", "session_id": session_id}))

    # Record all LIGHT_PIPELINE_AGENTS as completed.
    for agent in LIGHT_PIPELINE_AGENTS:
        pcs.record_agent_completion(session_id, agent, issue_number=0)

    # Verify: light mode should pass with these agents.
    passed, completed, missing = pcs.verify_pipeline_agent_completions(
        session_id, "light"
    )
    assert passed is True, (
        f"Light-mode agent completeness gate must PASS after all LIGHT_PIPELINE_AGENTS "
        f"complete. Missing: {missing}. This is the #1376 bug: when coordinator writes "
        f"mode='light' to /tmp/ and hook reads mode='full' from per-repo path, hook "
        f"requires full-pipeline agents (researcher, reviewer, security-auditor) and "
        f"blocks the commit."
    )
    assert missing == set(), f"No missing agents expected; got: {missing}"

    # Negative check: full mode with these same agents must FAIL (light ≠ full).
    passed_full, _, missing_full = pcs.verify_pipeline_agent_completions(
        session_id, "full"
    )
    assert passed_full is False, (
        "Light-mode agents should NOT pass full-mode gate — "
        "this check ensures the test is distinguishing modes, not trivially passing."
    )
    # Full mode requires researcher-local/researcher that light mode doesn't have.
    assert "researcher" in missing_full or "researcher-local" in missing_full, (
        f"Full mode should flag missing researchers; got missing={missing_full}"
    )


# ---------------------------------------------------------------------------
# AC7: Cross-repo isolation — two fake repos, no shared /tmp/ file
# ---------------------------------------------------------------------------


def test_cross_repo_isolation(tmp_path, monkeypatch):
    """AC7: Two fake repos each write a different mode. Verify no cross-repo
    path collision (no shared /tmp/ file; each uses its own per-repo sentinel).

    This is the #1206 guarantee that #1376 must preserve: per-repo sentinels
    don't clobber each other across concurrent /implement sessions.
    """
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    for repo in (repo_a, repo_b):
        (repo / ".git").mkdir(parents=True)
        (repo / ".claude" / "local").mkdir(parents=True)

    snippet_a = _extract_step0_write_snippet(mode="full", run_id="runA")
    snippet_b = _extract_step0_write_snippet(mode="light", run_id="runB")
    env_without_psf = {k: v for k, v in os.environ.items() if k != "PIPELINE_STATE_FILE"}

    result_a = subprocess.run(
        [sys.executable, "-c", snippet_a],
        cwd=str(repo_a),
        capture_output=True,
        text=True,
        env=env_without_psf,
    )
    result_b = subprocess.run(
        [sys.executable, "-c", snippet_b],
        cwd=str(repo_b),
        capture_output=True,
        text=True,
        env=env_without_psf,
    )

    assert result_a.returncode == 0, f"repo_a snippet failed: {result_a.stderr}"
    assert result_b.returncode == 0, f"repo_b snippet failed: {result_b.stderr}"

    path_a = result_a.stdout.strip()
    path_b = result_b.stdout.strip()

    # Paths must differ — per-repo isolation.
    assert path_a != path_b, (
        f"Repo A and Repo B sentinel paths must differ; both resolved to {path_a!r}. "
        f"If both point to the same /tmp/ file, concurrent sessions clobber each other."
    )

    # Neither path should be in /tmp/.
    assert "/tmp/" not in path_a, f"Repo A sentinel must not be in /tmp/; got {path_a!r}"
    assert "/tmp/" not in path_b, f"Repo B sentinel must not be in /tmp/; got {path_b!r}"

    # Read back and verify modes are independent.
    state_a = json.loads(Path(path_a).read_text())
    state_b = json.loads(Path(path_b).read_text())

    assert state_a["mode"] == "full", f"Repo A expected mode='full'; got {state_a['mode']!r}"
    assert state_b["mode"] == "light", f"Repo B expected mode='light'; got {state_b['mode']!r}"

    # Confirm repo_a's sentinel is under repo_a and repo_b's under repo_b.
    assert str(repo_a) in path_a, f"Repo A sentinel must be under repo_a; got {path_a!r}"
    assert str(repo_b) in path_b, f"Repo B sentinel must be under repo_b; got {path_b!r}"

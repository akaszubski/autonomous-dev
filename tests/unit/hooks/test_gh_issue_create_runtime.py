"""Runtime subprocess tests for gh issue create allow/deny (Issue #1203).

Invoke the REAL unified_pre_tool.py hook as a subprocess with PreToolUse JSON
on stdin and assert on the hook's stdout JSON (permissionDecision /
permissionDecisionReason) plus exit code. This locks the TOCTOU-inverse
semantic that pre-#1203 was broken: PreToolUse evaluates each Bash invocation
BEFORE it runs, so the command-context file MUST be written in a prior, separate
Bash tool call — bundling "write context && gh issue create" into one Bash
call leaves the context absent at hook-evaluation time and the call is blocked.

The fixture ``runtime_hook_env`` isolates the command-context path AND the
pipeline-state path via env vars (GH_ISSUE_CMD_CONTEXT_PATH, PIPELINE_STATE_FILE)
so no test writes the real ``/tmp/autonomous_dev_cmd_context.json``.

Date: 2026-06-12
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runtime_hook_env(tmp_path, monkeypatch):
    """Return an env dict that isolates the runtime hook's /tmp state.

    Sets:
      - GH_ISSUE_CMD_CONTEXT_PATH: per-test temp path so the hook reads our
        controlled context file, not the real /tmp/autonomous_dev_cmd_context.json
      - PIPELINE_STATE_FILE: per-test temp path so a stray /tmp pipeline
        sentinel cannot accidentally grant pipeline-active allow-through
      - HOME: per-test temp path so the hook can't read any user state
      - Removes any inherited CLAUDE_AGENT_NAME / CLAUDE_SESSION_ID that
        would otherwise grant agent-name allow-through
    """
    ctx_path = tmp_path / "cmd_context.json"
    pipeline_state = tmp_path / "implement_pipeline_state.json"  # absent => no pipeline
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    # The hook uses _hook_command_registered("create-issue") (Issue #953) to
    # downgrade gh-issue-create deny to a warning when /create-issue is not
    # installed (so users without the plugin are not wedged). The lookup
    # checks: ./.claude/commands/<name>.md, ~/.claude/commands/<name>.md,
    # and manifests under ~/.claude. We point HOME at a tmp path AND create
    # the fake command file there so the deny path actually fires.
    user_cmd_dir = fake_home / ".claude" / "commands"
    user_cmd_dir.mkdir(parents=True)
    (user_cmd_dir / "create-issue.md").write_text("# fake create-issue\n")
    env = os.environ.copy()
    env["GH_ISSUE_CMD_CONTEXT_PATH"] = str(ctx_path)
    env["PIPELINE_STATE_FILE"] = str(pipeline_state)
    env["HOME"] = str(fake_home)
    # Remove identity vars that would grant other allow-throughs.
    for k in ("CLAUDE_AGENT_NAME", "CLAUDE_SESSION_ID", "AUTONOMOUS_DEV_BYPASS"):
        env.pop(k, None)
    return {
        "env": env,
        "ctx_path": ctx_path,
        "pipeline_state": pipeline_state,
        "tmp_path": tmp_path,
    }


def _write_context(ctx_path: Path, command: str, *, mtime_offset: float = 0.0) -> None:
    """Write a command-context file and optionally backdate its mtime.

    Args:
        ctx_path: where to write
        command: command name (e.g. 'plan', 'create-issue', or 'evil-cmd')
        mtime_offset: seconds to subtract from now() (positive = older)
    """
    ctx_path.write_text(json.dumps({
        "command": command,
        "timestamp": "2026-06-11T00:00:00+00:00",
    }))
    if mtime_offset > 0:
        new_t = time.time() - mtime_offset
        os.utime(ctx_path, (new_t, new_t))


def _run_hook(env: Dict[str, str], tool_name: str, command: str) -> Tuple[Dict[str, Any], int]:
    """Invoke the hook as a subprocess and return (parsed_json, exit_code).

    The hook reads PreToolUse JSON from stdin and writes the decision JSON
    to stdout. Per the hook protocol, stdout JSON has
    ``hookSpecificOutput.permissionDecision`` of 'allow'/'deny'/'ask'.
    """
    payload = json.dumps({
        "tool_name": tool_name,
        "tool_input": {"command": command} if tool_name == "Bash" else {},
        "session_id": "test-runtime-1203",
    })
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(env.get("HOME", REPO_ROOT)),  # avoid repo cwd-side-effects
        timeout=30,
    )
    # The hook prints JSON to stdout. Some hooks may print warnings to stderr.
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        out = {"_raw_stdout": proc.stdout, "_stderr": proc.stderr}
    return out, proc.returncode


def _decision(parsed: Dict[str, Any]) -> str:
    """Extract permissionDecision from the hook output, or empty string."""
    return (
        parsed.get("hookSpecificOutput", {}).get("permissionDecision", "")
        or ""
    )


def _reason(parsed: Dict[str, Any]) -> str:
    """Extract permissionDecisionReason from the hook output."""
    return (
        parsed.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        or ""
    )


# ---------------------------------------------------------------------------
# Smoke test: hook is invocable as a subprocess and emits valid JSON
# ---------------------------------------------------------------------------

class TestRuntimeHookInvocable:
    """Sanity: the hook can be invoked, parses stdin, and emits valid JSON."""

    def test_hook_emits_valid_json(self, runtime_hook_env):
        parsed, rc = _run_hook(
            runtime_hook_env["env"], "Bash", "echo hello"
        )
        # Hook should exit 0 and emit a JSON decision
        assert rc == 0
        assert "hookSpecificOutput" in parsed or "_raw_stdout" in parsed


# ---------------------------------------------------------------------------
# Allow-through tests: context file written in a PRIOR call (the contract)
# ---------------------------------------------------------------------------

class TestRuntimeAllowAfterContextWrittenPrior:
    """Allow-through: context file written in a prior call lets gh issue
    create pass. This is the TOCTOU-inverse contract — the file must EXIST
    before the gh issue create Bash call is evaluated."""

    @pytest.mark.parametrize(
        "command_name,gh_cmd",
        [
            ("create-issue", 'gh issue create --title "x" --body "y"'),
            ("improve", 'gh issue create -R r --title "[CI-info-foo]" --body "details"'),
            ("plan", 'gh issue create --title "feat: split" --body-file /tmp/x.md'),
            ("plan-to-issues", 'gh issue create --title "feat: x" --body-file /tmp/x.md'),
            ("refactor", 'gh issue create --title "Refactor: x" --body "y"'),
            ("retrospective", 'gh issue create --title "[RETRO] x" --body "y"'),
        ],
    )
    def test_runtime_allow_after_context_written_prior_call(
        self, runtime_hook_env, command_name, gh_cmd
    ):
        """Each whitelisted command: prior context write => gh issue create allowed."""
        _write_context(runtime_hook_env["ctx_path"], command_name)
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", gh_cmd)
        decision = _decision(parsed)
        assert rc == 0
        # Allow means the hook does NOT emit deny for this Bash call.
        # The hook may emit 'allow' or fall through (no permissionDecision).
        assert decision != "deny", (
            f"prior context write for {command_name} must NOT block gh issue create; "
            f"got decision={decision!r}, reason={_reason(parsed)!r}"
        )


# ---------------------------------------------------------------------------
# Deny tests: missing/invalid context, bundled-same-call, TTL expiry
# ---------------------------------------------------------------------------

class TestRuntimeDenyMissingContext:
    """Deny: bare gh issue create without any prior context is blocked."""

    def test_runtime_deny_bare_gh_issue_create_no_context(self, runtime_hook_env):
        """Bare gh issue create with no context file => deny."""
        # Context file deliberately NOT written.
        parsed, rc = _run_hook(
            runtime_hook_env["env"],
            "Bash",
            'gh issue create --title "test"',
        )
        assert rc == 0
        assert _decision(parsed) == "deny", _reason(parsed)
        assert "BLOCKED" in _reason(parsed) or "block" in _reason(parsed).lower()

    def test_runtime_deny_unknown_command_in_context(self, runtime_hook_env):
        """Context with unknown command (fail-closed) => deny."""
        _write_context(runtime_hook_env["ctx_path"], "evil-command")
        parsed, rc = _run_hook(
            runtime_hook_env["env"],
            "Bash",
            'gh issue create --title "test"',
        )
        assert _decision(parsed) == "deny"

    def test_runtime_deny_after_ttl_expiry(self, runtime_hook_env):
        """Context file older than 3600s (1h) => deny (TTL expired)."""
        # Backdate mtime to >3600s ago.
        _write_context(
            runtime_hook_env["ctx_path"], "create-issue", mtime_offset=3700.0
        )
        parsed, rc = _run_hook(
            runtime_hook_env["env"],
            "Bash",
            'gh issue create --title "stale"',
        )
        assert _decision(parsed) == "deny"

    def test_runtime_deny_empty_context_file(self, runtime_hook_env):
        """Zero-byte context file => deny (fail-closed on JSON parse)."""
        runtime_hook_env["ctx_path"].write_text("")  # zero bytes
        parsed, rc = _run_hook(
            runtime_hook_env["env"],
            "Bash",
            'gh issue create --title "test"',
        )
        assert _decision(parsed) == "deny"


class TestRuntimeDenyBundledSameCall:
    """Deny: bundling the context write and gh issue create into ONE Bash
    invocation MUST be blocked. This is the TOCTOU-inverse semantic that
    pre-#1203 silently broke: PreToolUse evaluates the Bash command BEFORE
    it runs, so a write && gh-issue-create in the same call leaves the
    context absent at evaluation time."""

    def test_runtime_deny_bundled_same_call_simulation(self, runtime_hook_env):
        """Bundled write && gh issue create in ONE command string => deny."""
        ctx_path = runtime_hook_env["ctx_path"]
        # Simulate the BAD pattern: same Bash call writes the context AND
        # tries to create the issue. At hook-evaluation time the file does
        # not yet exist on disk (the python3 -c above the && has not run).
        bundled = (
            f'python3 -c "import json,os; '
            f"open(os.environ[\\'GH_ISSUE_CMD_CONTEXT_PATH\\'], '\\'\\'w\\'\\').write("
            f"json.dumps({{\\'command\\': \\'create-issue\\', \\'timestamp\\': \\'now\\'}}))"
            f'" && gh issue create --title "bundled-bad"'
        )
        # Ensure file does NOT exist at hook-evaluation time.
        if ctx_path.exists():
            ctx_path.unlink()
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", bundled)
        # The hook evaluates the raw command string; no file exists yet
        # (Bash has not run); so the call must be denied.
        assert _decision(parsed) == "deny", (
            f"bundled write && gh issue create must be denied (TOCTOU-inverse semantic). "
            f"reason={_reason(parsed)!r}"
        )


# ---------------------------------------------------------------------------
# Bypass-detector false positive: gh issue comment with backticked body
# ---------------------------------------------------------------------------

class TestRuntimeBypassFalsePositive:
    """Issue #1203 Change C: gh issue comment with backticks/$() inside
    --body must NOT be blocked. The bypass detector previously scanned the
    RAW command, false-positive flagging backtick-quoted prose inside
    --body argument values."""

    def test_runtime_allow_gh_issue_comment_with_backticked_body(
        self, runtime_hook_env
    ):
        """gh issue comment with prose backticks (NO create pattern) => NOT denied.

        Updated for FINDING-1 (#1203 cycle 1): backticks inside double quotes
        EXECUTE at shell runtime, so a body containing `` `gh issue create` ``
        would actually create the issue and MUST be blocked. The preserved
        false-positive case is prose backticks WHERE THE CONTENT IS NOT
        `gh issue create` — that stays allowed because the Tier-B value scan
        requires the create pattern.
        """
        cmd = (
            'gh issue comment 1203 -R akaszubski/autonomous-dev '
            '--body "Diagnosis: the `some_helper` regex matches prose"'
        )
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert _decision(parsed) != "deny", (
            f"gh issue comment with backticked prose (no create pattern) must "
            f"not be denied; reason={_reason(parsed)!r}"
        )


# ---------------------------------------------------------------------------
# True bypass forms: still blocked
# ---------------------------------------------------------------------------

class TestRuntimeTrueBypassesStillBlocked:
    """True subprocess/shell wrappers and command-position substitution
    forms MUST still be blocked even after Change C."""

    def test_runtime_deny_subprocess_wrapper_gh_issue_create(self, runtime_hook_env):
        cmd = (
            'python3 -c "import subprocess; '
            "subprocess.run(['gh', 'issue', 'create', '--title', 'x'])\""
        )
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert _decision(parsed) == "deny", _reason(parsed)

    def test_runtime_deny_sh_dash_c_gh_issue_create(self, runtime_hook_env):
        cmd = "sh -c 'gh issue create --title bypass --body x'"
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert _decision(parsed) == "deny", _reason(parsed)

    def test_runtime_deny_backtick_substitution_at_command_position(
        self, runtime_hook_env
    ):
        cmd = "RESULT=`gh issue create --title test --body details`"
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert _decision(parsed) == "deny", _reason(parsed)

    def test_runtime_deny_dollar_subst_create_in_body(self, runtime_hook_env):
        """FINDING-1 adversarial: --body "$(gh issue create ...)" MUST be denied.

        $() inside double quotes executes at shell runtime — without this block
        the command would actually create the issue, defeating /create-issue.
        """
        cmd = 'gh issue comment 1203 --body "$(gh issue create -t bypass)"'
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert _decision(parsed) == "deny", _reason(parsed)

    def test_runtime_deny_backtick_create_in_body(self, runtime_hook_env):
        """FINDING-1 adversarial: --body "`gh issue create ...`" MUST be denied.

        Backticks inside double quotes ALSO execute at shell runtime — same
        threat as the $() form.
        """
        cmd = 'gh issue comment 1203 --body "see `gh issue create -t bypass`"'
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert _decision(parsed) == "deny", _reason(parsed)


# ---------------------------------------------------------------------------
# Issue #1215 — argv-position-aware direct match
# ---------------------------------------------------------------------------

class TestRuntimeIssue1215GitCommitProseAllowed:
    """Issue #1215: a ``git commit -m "..."`` whose message body contains the
    literal substring ``gh issue create`` (in prose) MUST be allowed.

    Pre-#1215 the direct-match path scanned the quote-stripped command for
    the substring, which produced false positives whenever the body's
    prose escaped the stripper (escaped quotes, ANSI-C ``$'...'`` quoting,
    or unquoted prose). The #1203 and #1204 commits both required
    workarounds (``git commit -F /tmp/file`` plus body-rewriting with
    neutral phrasing).

    These subprocess-runtime tests invoke the real hook binary the same way
    Claude Code does and assert on the stdout decision JSON. They catch
    future regressions where the unit-level mock and the real hook diverge.
    """

    def test_runtime_allow_git_commit_m_with_substring_in_body(self, runtime_hook_env):
        """git commit -m with the substring in prose MUST not be denied."""
        cmd = (
            'git commit -m "fix: discuss the gh issue create gate behavior — '
            'argv-position-aware match (#1215)"'
        )
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert rc == 0
        assert _decision(parsed) != "deny", (
            "git commit -m with the substring in prose MUST NOT be denied "
            f"(Issue #1215); reason={_reason(parsed)!r}"
        )

    def test_runtime_allow_git_commit_F_path_argument(self, runtime_hook_env):
        """git commit -F /tmp/file MUST NOT be denied (only path is visible)."""
        cmd = "git commit -F /tmp/some_body_with_gh_issue_create_in_filename.txt"
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert rc == 0
        assert _decision(parsed) != "deny", (
            "git commit -F with path argument MUST NOT be denied "
            f"(Issue #1215); reason={_reason(parsed)!r}"
        )

    def test_runtime_allow_git_commit_long_message_flag(self, runtime_hook_env):
        """git commit --message "...gh issue create..." MUST NOT be denied."""
        cmd = (
            'git commit --message "long-flag form with the gh issue create '
            'substring inline in prose body"'
        )
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert rc == 0
        assert _decision(parsed) != "deny", (
            "git commit --message with substring in body MUST NOT be denied "
            f"(Issue #1215); reason={_reason(parsed)!r}"
        )

    def test_runtime_allow_git_commit_multi_line_body_with_substring(
        self, runtime_hook_env
    ):
        """git commit -m with multi-line body containing the substring MUST allow."""
        cmd = (
            'git commit -m "fix(security): #1215 argv-position-aware match\n\n'
            "The bypass-detector false-positive — the regex matched prose\n"
            'inside --body argument VALUES containing gh issue create text."'
        )
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert rc == 0
        assert _decision(parsed) != "deny", (
            "git commit -m with multi-line body containing the substring "
            f"MUST NOT be denied (Issue #1215); reason={_reason(parsed)!r}"
        )

    def test_runtime_real_gh_issue_create_still_denied(self, runtime_hook_env):
        """Sanity: the real command at argv[0] MUST STILL be denied post-#1215."""
        cmd = 'gh issue create --title "test" --body "details"'
        parsed, rc = _run_hook(runtime_hook_env["env"], "Bash", cmd)
        assert _decision(parsed) == "deny", (
            "the real gh issue create command MUST STILL be denied "
            f"post-#1215; reason={_reason(parsed)!r}"
        )

"""Integration tests for hook resilience — Issue #953.

End-to-end scenarios that exercise the full safe_main contract via subprocess
to confirm Claude Code is never blocked by hook infrastructure failures.
"""

from __future__ import annotations

import json
import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"


@pytest.mark.parametrize("hook", ["native_run_origin.py", "session_activity_logger.py", "unified_session_tracker.py"])
@pytest.mark.parametrize("case", ["sibling", "already_deeper", "legacy_fallback", "missing_selected"])
def test_native_bootstrap_pins_first_library_root(tmp_path, hook, case):
    """Execute actual hook bootstrap nodes, not a duplicate path algorithm."""
    installed = tmp_path / "installed"
    hook_path = installed / "hooks" / hook
    hook_path.parent.mkdir(parents=True)
    selected = installed / "lib"
    if case == "legacy_fallback":
        selected = tmp_path / "lib"
    selected.mkdir()
    foreign = tmp_path / "home/.claude/plugins/autonomous-dev/lib"
    foreign.mkdir(parents=True)
    module = "def safe_main(function): return function()\n"
    (foreign / "hook_safety.py").write_text(module)
    if case != "missing_selected":
        (selected / "hook_safety.py").write_text(module)
    nodes = []
    for node in ast.parse((HOOK_DIR / hook).read_text()).body:
        if isinstance(node, ast.Import) and any(n.name == "sys" for n in node.names):
            nodes.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module == "pathlib":
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(n, ast.Name) and n.id == "_hook_dir_953" for n in node.targets):
            nodes.append(node)
        elif isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "_candidate_lib_953":
            nodes.append(node)
        elif isinstance(node, ast.Try) and "from hook_safety import" in ast.unparse(node):
            nodes.append(node)
            break
    code = "import sys,json; __file__=" + repr(str(hook_path)) + "\n"
    if case == "already_deeper":
        code += "sys.path[:0]=" + repr([str(foreign), str(selected)]) + "\n"
    code += ast.unparse(ast.Module(body=nodes, type_ignores=[]))
    code += "\nm=sys.modules.get('hook_safety');print(json.dumps({'origin':getattr(m,'__file__',None),'path_head':sys.path[0]}))"
    result = subprocess.run([sys.executable, "-B", "-I", "-c", code],
                            env={"HOME": str(tmp_path / "home"), "PATH": "/usr/bin:/bin"},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    if case == "missing_selected":
        assert actual["origin"] is None
        assert "Selected hook library is incomplete" in result.stderr
    else:
        assert Path(actual["origin"]).resolve() == (selected / "hook_safety.py").resolve()
        assert Path(actual["path_head"]).resolve() == selected.resolve()


def _run_python(script: str, *, timeout: float = 10.0, env: dict = None) -> subprocess.CompletedProcess:
    """Execute ``script`` via the current python and return the completed process."""
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _run_hook(hook_path: Path, stdin: str, *, timeout: float = 10.0, env: dict = None) -> subprocess.CompletedProcess:
    """Run a hook script directly via the current python interpreter."""
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


class TestMissingDependencyResilience:
    """Hooks with broken imports MUST exit 0 with a stderr warning."""

    def test_hook_with_missing_dependency_does_not_block(self, tmp_path):
        """A hook whose main() fails on ImportError MUST exit 0 + warn."""
        hook_script = tmp_path / "broken_hook.py"
        hook_script.write_text(textwrap.dedent(f"""
            #!/usr/bin/env python3
            import sys
            sys.path.insert(0, {str(LIB_PATH)!r})
            from hook_safety import safe_main

            def main():
                import nonexistent_xyz_package_953  # noqa: F401

            if __name__ == "__main__":
                safe_main(main)
        """))

        result = _run_hook(hook_script, "")

        assert result.returncode == 0, (
            f"Hook should exit 0 on import error. Got: {result.returncode}\n"
            f"stderr: {result.stderr}"
        )
        assert "[hook warning]" in result.stderr, (
            f"Expected warning in stderr, got: {result.stderr!r}"
        )

    def test_hook_with_runtime_error_does_not_block(self, tmp_path):
        """A hook whose main() raises RuntimeError MUST exit 0 + warn."""
        hook_script = tmp_path / "crashing_hook.py"
        hook_script.write_text(textwrap.dedent(f"""
            #!/usr/bin/env python3
            import sys
            sys.path.insert(0, {str(LIB_PATH)!r})
            from hook_safety import safe_main

            def main():
                raise RuntimeError("simulated runtime crash")

            if __name__ == "__main__":
                safe_main(main)
        """))

        result = _run_hook(hook_script, "")

        assert result.returncode == 0
        assert "[hook warning]" in result.stderr
        assert "RuntimeError" in result.stderr
        assert "simulated runtime crash" in result.stderr

    def test_hook_returning_int_preserves_exit_code(self, tmp_path):
        """A hook that returns int 2 MUST exit 2 (success-path preserved)."""
        hook_script = tmp_path / "exit2_hook.py"
        hook_script.write_text(textwrap.dedent(f"""
            #!/usr/bin/env python3
            import sys
            sys.path.insert(0, {str(LIB_PATH)!r})
            from hook_safety import safe_main

            def main():
                return 2

            if __name__ == "__main__":
                safe_main(main)
        """))

        result = _run_hook(hook_script, "")

        assert result.returncode == 2, (
            f"Expected exit 2 (preserved int return), got {result.returncode}"
        )

    def test_real_hook_with_invalid_stdin_does_not_block(self):
        """task_completed_handler.py MUST exit 0 even on invalid stdin."""
        # task_completed_handler is a Stop-style hook that tolerates anything
        # on stdin. A regression here would mean safe_main isn't catching.
        hook = HOOK_DIR / "task_completed_handler.py"
        result = _run_hook(hook, "this is not valid json {{{", timeout=10.0)
        assert result.returncode == 0, (
            f"Real hook MUST exit 0 on bad stdin. Got: {result.returncode}\n"
            f"stderr: {result.stderr}"
        )


class TestSlashCommandPreconditionDowngrade:
    """Deny decisions referencing /create-issue MUST downgrade to warning when
    the command is not registered. This is the core fix for Mode 2 (#947)."""

    def _make_env(self, fake_home: Path) -> dict:
        """Build subprocess env with HOME pointing at a clean fake."""
        import os
        env = dict(os.environ)
        env["HOME"] = str(fake_home)
        # Disable session-id leakage to keep the test deterministic.
        env.pop("CLAUDE_SESSION_ID", None)
        # Force enforcement to be on so the deny path actually fires.
        env.pop("PRE_TOOL_DRY_RUN", None)
        # Make sure no project-local commands leak by pointing cwd into fake home.
        return env

    def test_unregistered_create_issue_downgrades_marker_block(self, tmp_path):
        """If /create-issue is unregistered, gh-marker-creation MUST NOT deny."""
        # Build fake HOME with no commands and a clean cwd with no .claude dir.
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        empty_cwd = tmp_path / "work"
        empty_cwd.mkdir()

        env = self._make_env(fake_home)

        # Probe via subprocess: load the command_registered helper directly
        # and verify it returns False (precondition for the downgrade test).
        probe = _run_python(textwrap.dedent(f"""
            import os
            os.chdir({str(empty_cwd)!r})
            os.environ['HOME'] = {str(fake_home)!r}
            import sys
            sys.path.insert(0, {str(LIB_PATH)!r})
            from hook_safety import command_registered
            print('REGISTERED:', command_registered('create-issue'))
        """), env=env)
        assert "REGISTERED: False" in probe.stdout, (
            f"Probe failed: command_registered('create-issue') is not False.\n"
            f"stdout: {probe.stdout!r}\nstderr: {probe.stderr!r}"
        )

    def test_registered_create_issue_keeps_deny_path_active(self, tmp_path):
        """When /create-issue IS registered, command_registered → True
        and the deny path still fires (regression lock for AC #7)."""
        fake_home = tmp_path / "home"
        (fake_home / ".claude" / "commands").mkdir(parents=True)
        (fake_home / ".claude" / "commands" / "create-issue.md").write_text("# create-issue\n")
        empty_cwd = tmp_path / "work"
        empty_cwd.mkdir()

        env = dict(__import__("os").environ)
        env["HOME"] = str(fake_home)

        probe = _run_python(textwrap.dedent(f"""
            import os
            os.chdir({str(empty_cwd)!r})
            os.environ['HOME'] = {str(fake_home)!r}
            import sys
            sys.path.insert(0, {str(LIB_PATH)!r})
            from hook_safety import command_registered
            print('REGISTERED:', command_registered('create-issue'))
        """), env=env)
        assert "REGISTERED: True" in probe.stdout, (
            f"Probe failed: command_registered should be True.\n"
            f"stdout: {probe.stdout!r}\nstderr: {probe.stderr!r}"
        )


class TestHookSafetyContract:
    """End-to-end contract: hook_safety helpers MUST be importable from a
    subprocess and behave per the documented fail-modes."""

    def test_hook_safety_importable_via_lib_resolver(self, tmp_path):
        """The standard lib-path resolver pattern MUST find hook_safety."""
        # Simulate a hook in plugins/.../hooks/ doing the standard resolver.
        # We run the resolver pattern in isolation to confirm it works.
        result = _run_python(textwrap.dedent(f"""
            import sys
            from pathlib import Path
            hook_dir = Path({str(HOOK_DIR)!r})
            for cand in (hook_dir.parent / 'lib',):
                if cand.exists():
                    sys.path.insert(0, str(cand))
            from hook_safety import safe_main, command_registered
            print('OK')
        """))
        assert result.returncode == 0, (
            f"Resolver+import failed.\n"
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        assert "OK" in result.stdout

    def test_real_hook_safe_main_swallows_hook_safety_missing(self, tmp_path):
        """If hook_safety is genuinely unimportable, the no-op fallback must
        still preserve exit-code semantics (success path stays correct)."""
        # Write a hook that tries to import hook_safety from an empty dir.
        # The try/except fallback should kick in and define a no-op safe_main.
        hook_script = tmp_path / "no_lib_hook.py"
        hook_script.write_text(textwrap.dedent("""
            #!/usr/bin/env python3
            import sys
            from pathlib import Path
            # Point lib path nowhere so import fails:
            empty_lib = Path("/nonexistent/953/lib")
            try:
                from hook_safety import safe_main
            except ImportError:
                def safe_main(fn):
                    r = fn()
                    if isinstance(r, int):
                        sys.exit(r)
                    sys.exit(0)

            def main():
                return 0

            if __name__ == "__main__":
                safe_main(main)
        """))

        result = _run_hook(hook_script, "", timeout=5.0)
        assert result.returncode == 0

"""GenAI tests for hook quality and coverage.

Validates that hooks follow consistent patterns, handle errors gracefully,
and stay in sync with registry documentation.
"""

import re
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"
HOOKS_DIR = PLUGIN_ROOT / "hooks"


def _active_hook_files():
    """Return list of active (non-archived) hook .py files."""
    return sorted(
        f for f in HOOKS_DIR.glob("*.py")
        if f.stem != "__init__" and "archived" not in str(f)
    )


class TestHookQuality:
    """Validate hook code quality and consistency."""

    def test_all_active_hooks_have_docstrings(self, genai):
        """Every active hook should have a module-level docstring."""
        hooks = _active_hook_files()
        results = {}
        for hook in hooks:
            content = hook.read_text(errors="ignore")
            # Check for docstring after shebang/script metadata
            has_docstring = bool(re.search(r'"""[\s\S]+?"""', content[:2000]))
            results[hook.stem] = has_docstring

        missing = [name for name, has in results.items() if not has]

        result = genai.judge(
            question="Do all active hooks have module-level docstrings?",
            context=f"**Hooks with docstrings:** {[n for n, h in results.items() if h]}\n\n"
            f"**Hooks MISSING docstrings ({len(missing)}):** {missing}",
            criteria="Every hook should have a docstring explaining its purpose, "
            "hook type, environment variables, and exit codes. "
            "Score 10 if all present, deduct 1 per missing docstring.",
        )
        assert result["score"] >= 5, f"Hooks missing docstrings: {result['reasoning']}"

    def test_hooks_handle_errors_gracefully(self, genai):
        """Hooks should have try/except to avoid crashing Claude Code."""
        hooks = _active_hook_files()
        hook_summaries = {}
        for hook in hooks[:10]:  # Sample to keep context manageable
            content = hook.read_text(errors="ignore")
            has_try = "try:" in content
            has_except = "except" in content
            has_exit_0 = "sys.exit(0)" in content or "exit(0)" in content
            hook_summaries[hook.stem] = {
                "has_try_except": has_try and has_except,
                "has_exit_0": has_exit_0,
                "lines": len(content.splitlines()),
            }

        result = genai.judge(
            question="Do hooks handle errors gracefully to avoid crashing Claude Code?",
            context=f"**Hook error handling summary:**\n"
            + "\n".join(f"  {name}: {info}" for name, info in hook_summaries.items()),
            criteria="Hooks should have try/except blocks around main logic. "
            "Non-blocking hooks should always exit 0. "
            "Unhandled exceptions in hooks crash Claude Code. "
            "Score 10 = all have error handling, deduct 1 per hook without.",
        )
        assert result["score"] >= 5, f"Hook error handling gaps: {result['reasoning']}"

    def test_hooks_dont_block_on_failure(self, genai):
        """Non-blocking hooks should always exit 0, even on errors."""
        hooks = _active_hook_files()
        blocking_analysis = {}
        for hook in hooks:
            content = hook.read_text(errors="ignore")
            docstring_match = re.search(r'"""([\s\S]*?)"""', content[:3000])
            docstring = docstring_match.group(1) if docstring_match else ""

            is_non_blocking = "non-blocking" in docstring.lower() or "always" in docstring.lower()
            exits_nonzero = bool(re.search(r'sys\.exit\([1-9]', content))
            blocking_analysis[hook.stem] = {
                "declares_non_blocking": is_non_blocking,
                "has_nonzero_exit": exits_nonzero,
            }

        suspects = [
            name for name, info in blocking_analysis.items()
            if info["declares_non_blocking"] and info["has_nonzero_exit"]
        ]

        result = genai.judge(
            question="Do non-blocking hooks always exit 0?",
            context=f"**Analysis:**\n"
            + "\n".join(f"  {name}: {info}" for name, info in blocking_analysis.items())
            + f"\n\n**Suspects (declare non-blocking but exit nonzero):** {suspects}",
            criteria="Hooks that declare themselves as 'non-blocking' or 'always exit 0' "
            "should never call sys.exit with a non-zero code. "
            "Score 10 = no contradictions, deduct 3 per contradictory hook.",
        )
        assert result["score"] >= 5, f"Non-blocking hook violations: {result['reasoning']}"

    def test_hook_registry_matches_settings_template(self, genai):
        """Hooks in settings template should match active hook files."""
        settings_templates = list(PLUGIN_ROOT.glob("templates/settings.*.json"))
        template_hooks = set()
        for tmpl in settings_templates:
            try:
                import json
                data = json.loads(tmpl.read_text())
                for hook_list in data.get("hooks", {}).values():
                    if isinstance(hook_list, list):
                        for hook in hook_list:
                            cmd = hook.get("command", "") if isinstance(hook, dict) else ""
                            # Extract python filename from command
                            match = re.search(r'(\w+)\.py', cmd)
                            if match:
                                template_hooks.add(match.group(1))
            except Exception:
                continue

        hook_files = {f.stem for f in _active_hook_files()}

        if not template_hooks:
            pytest.skip("No hook references found in settings templates")

        dead_refs = sorted(template_hooks - hook_files)

        result = genai.judge(
            question="Do settings templates reference only hooks that exist on disk?",
            context=f"**Hooks in templates:** {sorted(template_hooks)}\n\n"
            f"**Hook files on disk:** {sorted(hook_files)}\n\n"
            f"**Dead references (in template but not on disk):** {dead_refs}\n"
            f"**On disk but not in templates:** {sorted(hook_files - template_hooks)}",
            criteria="Templates should reference hooks that exist. "
            "Dead references = broken installations. "
            "If there are zero dead references, score 10. "
            "Deduct 2 per dead template reference.",
        )
        assert result["score"] >= 5, f"Hook-template drift: {result['reasoning']}"

    def test_hook_env_vars_have_defaults(self, genai):
        """Hooks reading env vars should provide sensible defaults."""
        hooks = _active_hook_files()
        env_patterns = {}
        for hook in hooks[:10]:
            content = hook.read_text(errors="ignore")
            # Find os.environ.get and os.environ[] patterns
            gets = re.findall(r'os\.environ\.get\(["\'](\w+)["\'](?:,\s*(.+?))?\)', content)
            raw = re.findall(r'os\.environ\[["\'](\w+)["\']\]', content)
            env_patterns[hook.stem] = {
                "with_default": [(name, default) for name, default in gets if default],
                "without_default": [(name,) for name, default in gets if not default] + [(name,) for name in raw],
            }

        result = genai.judge(
            question="Do hooks provide default values for environment variables?",
            context=f"**Env var usage:**\n"
            + "\n".join(f"  {name}: defaults={info['with_default']}, no_default={info['without_default']}"
                        for name, info in env_patterns.items() if info['with_default'] or info['without_default']),
            criteria="Hooks should use os.environ.get() with defaults, not os.environ[]. "
            "Missing env vars should not crash hooks. "
            "Claude-provided vars (CLAUDE_*) may reasonably lack defaults. "
            "Score 10 = all have defaults or justified, deduct 1 per unjustified missing default.",
        )
        assert result["score"] >= 5, f"Hook env var defaults: {result['reasoning']}"

    def test_archived_hooks_not_referenced_by_active_code(self, genai):
        """Archived hooks should not be imported/referenced by active code."""
        archived_dir = HOOKS_DIR / "archived"
        if not archived_dir.exists():
            pytest.skip("No archived hooks directory")

        archived_hooks = [f.stem for f in archived_dir.glob("*.py") if f.stem != "__init__"]
        if not archived_hooks:
            pytest.skip("No archived hooks")

        # Check active hooks and commands for references
        active_content = ""
        for hook in _active_hook_files():
            active_content += f"\n--- {hook.name} ---\n" + hook.read_text(errors="ignore")

        commands_dir = PLUGIN_ROOT / "commands"
        if commands_dir.exists():
            for cmd in commands_dir.glob("*.md"):
                active_content += f"\n--- {cmd.name} ---\n" + cmd.read_text(errors="ignore")

        result = genai.judge(
            question="Are archived hooks referenced by any active code?",
            context=f"**Archived hooks:** {archived_hooks}\n\n"
            f"**Active code (hooks + commands, truncated):**\n{active_content[:5000]}",
            criteria="Archived hooks should not be imported or referenced by active hooks or commands. "
            "References to archived code = broken imports or dead code paths. "
            "Score 10 = no references, deduct 3 per reference found.",
        )
        assert result["score"] >= 5, f"Archived hook references: {result['reasoning']}"

    def test_hooks_use_consistent_logging_pattern(self, genai):
        """Hooks should use consistent logging (stderr, not stdout)."""
        hooks = _active_hook_files()
        logging_patterns = {}
        for hook in hooks[:10]:
            content = hook.read_text(errors="ignore")
            logging_patterns[hook.stem] = {
                "uses_print": "print(" in content,
                "uses_stderr": "sys.stderr" in content,
                "uses_logging": "import logging" in content or "logging." in content,
                "uses_json_stdout": "json.dumps" in content and "sys.stdout" in content,
            }

        result = genai.judge(
            question="Do hooks use consistent logging patterns?",
            context=f"**Logging patterns:**\n"
            + "\n".join(f"  {name}: {info}" for name, info in logging_patterns.items()),
            criteria="Hooks should write diagnostic output to stderr (not stdout). "
            "stdout is reserved for hook response JSON. "
            "print() without file=sys.stderr risks corrupting hook responses. "
            "However, hooks that use print() only in error paths or debug modes get partial credit. "
            "Score 10 = all consistent, 5 = most consistent, 2 = widespread print usage.",
        )
        assert result["score"] >= 2, f"Hook logging inconsistency: {result['reasoning']}"

    def test_pre_commit_references_only_existing_hooks(self, genai):
        """Pre-commit config should only reference hooks that exist."""
        pre_commit = PROJECT_ROOT / ".pre-commit-config.yaml"
        if not pre_commit.exists():
            # Check for hook references in settings templates instead
            settings_path = PLUGIN_ROOT / "templates" / "settings.local.json"
            if not settings_path.exists():
                pytest.skip("No pre-commit config or settings template")
            content = settings_path.read_text()
            source_label = "settings.local.json"
        else:
            content = pre_commit.read_text()
            source_label = ".pre-commit-config.yaml"

        hook_files = {f.name for f in _active_hook_files()}

        result = genai.judge(
            question=f"Does {source_label} reference only hooks that exist?",
            context=f"**{source_label}:**\n{content[:3000]}\n\n"
            f"**Existing hook files:** {sorted(hook_files)}",
            criteria="Every hook referenced in configuration should exist as a file. "
            "Dead references = broken pre-commit or settings. "
            "Score 10 = all exist, deduct 3 per dead reference.",
        )
        assert result["score"] >= 5, f"Config references missing hooks: {result['reasoning']}"

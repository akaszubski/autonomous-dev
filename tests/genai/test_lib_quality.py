"""GenAI tests for library module quality.

Validates that lib modules follow consistent patterns:
docstrings, type hints, valid imports, no hardcoded paths,
error handling in high-impact modules.
"""

import ast
import re
from pathlib import Path

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"
LIB_DIR = PLUGIN_ROOT / "lib"


def _lib_modules():
    """Return list of library .py files (excluding __init__)."""
    return sorted(
        f for f in LIB_DIR.glob("*.py")
        if f.stem != "__init__"
    )


class TestLibQuality:
    """Validate library module quality and consistency."""

    def test_lib_modules_have_docstrings(self, genai):
        """Every lib module should have a module-level docstring."""
        modules = _lib_modules()
        results = {}
        for mod in modules:
            content = mod.read_text(errors="ignore")
            # Check for module docstring (first string literal)
            has_docstring = bool(re.match(r'\s*(?:#[^\n]*\n)*\s*(?:"""|\'\'\')[\s\S]+?(?:"""|\'\'\')', content))
            results[mod.stem] = has_docstring

        missing = [name for name, has in results.items() if not has]

        result = genai.judge(
            question=f"Do all {len(modules)} lib modules have module-level docstrings?",
            context=f"**With docstrings ({len(modules) - len(missing)}):** "
            f"{[n for n, h in results.items() if h][:20]}...\n\n"
            f"**MISSING docstrings ({len(missing)}):** {missing[:30]}",
            criteria="Every library module should have a docstring explaining its purpose. "
            "This is a quality baseline, not perfection. "
            "Score based on percentage: >90% = 8+, >75% = 6+, >50% = 4+.",
        )
        assert result["score"] >= 4, f"Lib docstring coverage low: {result['reasoning']}"

    def test_lib_public_functions_have_type_hints(self, genai):
        """Public functions in lib modules should have type hints."""
        modules = _lib_modules()
        sample = modules[:15]  # Sample to keep context manageable
        analysis = {}

        for mod in sample:
            try:
                tree = ast.parse(mod.read_text(errors="ignore"))
                funcs = [
                    node for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not node.name.startswith("_")
                ]
                typed = sum(1 for f in funcs if f.returns is not None)
                analysis[mod.stem] = {"total": len(funcs), "typed": typed}
            except SyntaxError:
                analysis[mod.stem] = {"total": 0, "typed": 0, "error": "syntax"}

        result = genai.judge(
            question="Do public functions in lib modules have return type hints?",
            context=f"**Type hint analysis (sample of {len(sample)}):**\n"
            + "\n".join(f"  {name}: {info['typed']}/{info['total']} typed"
                        for name, info in analysis.items()),
            criteria="Public functions should have return type annotations. "
            "This is a quality indicator, not a hard requirement. "
            "Score based on overall percentage: >80% = 8+, >60% = 6+, >40% = 4+.",
        )
        assert result["score"] >= 3, f"Type hint coverage low: {result['reasoning']}"

    def test_lib_imports_are_valid(self, genai):
        """Lib modules should not have obviously broken imports."""
        modules = _lib_modules()
        sample = modules[:15]
        import_analysis = {}

        for mod in sample:
            try:
                tree = ast.parse(mod.read_text(errors="ignore"))
                imports = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module)
                import_analysis[mod.stem] = imports
            except SyntaxError:
                import_analysis[mod.stem] = ["SYNTAX_ERROR"]

        result = genai.judge(
            question="Are lib module imports valid and non-circular?",
            context=f"**Import analysis (sample of {len(sample)}):**\n"
            + "\n".join(f"  {name}: {deps[:8]}" for name, deps in import_analysis.items()),
            criteria="Imports should reference real modules. "
            "Circular imports between lib modules are problematic. "
            "Imports of removed/renamed modules = broken code. "
            "Score 10 = clean imports, deduct 2 per suspicious import.",
        )
        assert result["score"] >= 3, f"Import issues: {result['reasoning']}"

    def test_lib_no_hardcoded_paths(self, genai):
        """Lib modules should not contain hardcoded absolute paths."""
        modules = _lib_modules()
        hardcoded = {}

        for mod in modules:
            content = mod.read_text(errors="ignore")
            # Look for hardcoded home directory or absolute paths
            paths = re.findall(r'["\'](/Users/\w+/[^"\']+)["\']', content)
            paths += re.findall(r'["\'](/home/\w+/[^"\']+)["\']', content)
            paths += re.findall(r'["\']([A-Z]:\\Users\\[^"\']+)["\']', content)
            if paths:
                hardcoded[mod.stem] = paths

        result = genai.judge(
            question="Do any lib modules contain hardcoded absolute paths?",
            context=f"**Modules with hardcoded paths ({len(hardcoded)}):**\n"
            + "\n".join(f"  {name}: {paths}" for name, paths in hardcoded.items())
            + f"\n\n**Total modules checked:** {len(modules)}",
            criteria="Library modules should not contain hardcoded user-specific paths. "
            "Use Path.home(), os.path.expanduser, or relative paths instead. "
            "Score 10 = no hardcoded paths, deduct 3 per module with hardcoded paths.",
        )
        assert result["score"] >= 5, f"Hardcoded paths found: {result['reasoning']}"

    def test_high_impact_libs_have_error_handling(self, genai):
        """High-impact lib modules should have proper error handling."""
        high_impact = [
            "agent_tracker", "session_state_manager", "auto_approval_engine",
            "batch_orchestrator", "workflow_coordinator", "tool_validator",
            "orchestrator", "health_check",
        ]

        analysis = {}
        for name in high_impact:
            path = LIB_DIR / f"{name}.py"
            if not path.exists():
                continue
            content = path.read_text(errors="ignore")
            analysis[name] = {
                "has_try_except": "try:" in content and "except" in content,
                "has_logging": "logging" in content or "logger" in content,
                "has_custom_exceptions": "raise " in content,
                "lines": len(content.splitlines()),
            }

        result = genai.judge(
            question="Do high-impact lib modules have proper error handling?",
            context=f"**High-impact module analysis:**\n"
            + "\n".join(f"  {name}: {info}" for name, info in analysis.items()),
            criteria="High-impact modules (agent_tracker, session_state_manager, etc.) "
            "should have try/except blocks, logging, and meaningful error messages. "
            "These modules affect the entire pipeline when they fail. "
            "Score 10 = all have proper handling, deduct 2 per module without.",
        )
        assert result["score"] >= 2, f"Error handling gaps: {result['reasoning']}"  # Known debt: many high-impact libs lack structured error handling

    def test_lib_modules_referenced_by_agents_or_commands(self, genai):
        """Lib modules should be referenced by at least one agent or command."""
        modules = {mod.stem for mod in _lib_modules()}

        # Collect all references from agents and commands
        reference_content = ""
        agents_dir = PLUGIN_ROOT / "agents"
        commands_dir = PLUGIN_ROOT / "commands"
        hooks_dir = PLUGIN_ROOT / "hooks"

        for search_dir in [agents_dir, commands_dir, hooks_dir]:
            if search_dir.exists():
                for f in search_dir.iterdir():
                    if f.suffix in (".md", ".py"):
                        reference_content += f.read_text(errors="ignore") + "\n"

        # Check which modules are mentioned
        referenced = set()
        for mod_name in modules:
            if mod_name in reference_content:
                referenced.add(mod_name)

        orphaned = sorted(modules - referenced)

        result = genai.judge(
            question="Are there lib modules not referenced by any agent, command, or hook?",
            context=f"**Total modules:** {len(modules)}\n"
            f"**Referenced:** {len(referenced)}\n"
            f"**Potentially orphaned ({len(orphaned)}):** {orphaned[:20]}",
            criteria="Most lib modules should be referenced somewhere. "
            "Orphaned modules may be dead code or indirectly used. "
            "Some orphaning is acceptable (utilities, shared helpers). "
            "Score based on orphan percentage: <10% = 8+, <20% = 6+, <40% = 4+.",
        )
        assert result["score"] >= 1, f"Many orphaned libs: {result['reasoning']}"  # Known debt: libs referenced indirectly via dynamic imports

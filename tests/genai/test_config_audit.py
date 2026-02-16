"""GenAI UAT: Configuration consistency.

Cross-file configuration validation to catch drift.
"""

import json
import re

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


class TestConfigAudit:
    def test_version_consistency(self, genai):
        """Version strings should be consistent across files."""
        version_sources = {}

        plugin_json = PLUGIN_ROOT / "plugin.json"
        if plugin_json.exists():
            data = json.loads(plugin_json.read_text())
            version_sources["plugin.json"] = data.get("version", "not found")

        version_file = PLUGIN_ROOT / "VERSION"
        if version_file.exists():
            version_sources["VERSION"] = version_file.read_text().strip()

        for manifest in PROJECT_ROOT.glob("**/manifest*.json"):
            if any(x in str(manifest) for x in ["archived", "node_modules", ".genai_cache", "artifacts"]):
                continue
            try:
                data = json.loads(manifest.read_text())
                if "version" in data:
                    version_sources[str(manifest.relative_to(PROJECT_ROOT))] = data["version"]
            except (json.JSONDecodeError, OSError):
                pass

        result = genai.judge(
            question="Are version strings consistent across all config files?",
            context=f"Version sources:\n{json.dumps(version_sources, indent=2)}",
            criteria="All version strings should match or be clearly related (e.g., all 3.50.x). "
            "Score 10 = all identical, 5 = minor drift, 0 = major inconsistency.",
        )
        assert result["score"] >= 5, f"Version drift: {result['reasoning']}"

    def test_no_hardcoded_counts(self, genai):
        """Component counts should not be hardcoded in source code."""
        hardcoded = []
        count_patterns = [r"\b16\s+agents?\b", r"\b40\s+skills?\b", r"\b25\s+commands?\b"]

        for f in PLUGIN_ROOT.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            content = f.read_text(errors="ignore")
            for pattern in count_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    line_no = content[: match.start()].count("\n") + 1
                    hardcoded.append(f"{f.relative_to(PROJECT_ROOT)}:{line_no}: {match.group()}")

        result = genai.judge(
            question="Are component counts hardcoded in Python source files?",
            context=f"Hardcoded count matches:\n" + "\n".join(hardcoded) if hardcoded else "No hardcoded counts found.",
            criteria="Component counts (agents, skills, commands) should come from disk scanning, "
            "not hardcoded numbers. Exceptions: test assertions, comments. "
            "Score 10 = no hardcoding, 5 = only in tests/comments, 0 = in production logic.",
        )
        assert result["score"] >= 5, f"Hardcoded counts: {result['reasoning']}"

    def test_hook_env_vars_documented(self, genai):
        """Environment variables used in hooks should be documented."""
        env_vars = set()
        hooks_dir = PLUGIN_ROOT / "hooks"
        if hooks_dir.exists():
            for f in hooks_dir.glob("*.py"):
                content = f.read_text(errors="ignore")
                env_vars.update(re.findall(r'os\.environ\.get\(["\'](\w+)', content))
                env_vars.update(re.findall(r'os\.environ\[["\'](\w+)', content))
                env_vars.update(re.findall(r'os\.getenv\(["\'](\w+)', content))

        hook_docs = ""
        for doc_name in ["HOOK-REGISTRY.md", "docs/HOOK-REGISTRY.md", "HOOKS.md", "docs/HOOKS.md"]:
            doc_path = PROJECT_ROOT / doc_name
            if not doc_path.exists():
                doc_path = PLUGIN_ROOT / doc_name
            if doc_path.exists():
                hook_docs += doc_path.read_text()[:3000]

        result = genai.judge(
            question="Are hook environment variables documented?",
            context=f"Env vars used in hooks: {sorted(env_vars)}\n\nHook documentation:\n{hook_docs[:3000]}",
            criteria="Environment variables that hooks depend on should appear in documentation. "
            "Standard vars (PATH, HOME) are excluded. "
            "Score 10 = all documented, 5 = most documented, 0 = undocumented.",
        )
        assert result["score"] >= 5, f"Undocumented env vars: {result['reasoning']}"

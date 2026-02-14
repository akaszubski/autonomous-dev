"""GenAI UAT: Configuration consistency.

Cross-file configuration validation to catch drift.
Universal test — works in any repo with version files.
"""

import json
import re

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]


class TestConfigAudit:
    def test_version_consistency(self, genai):
        """Version strings should be consistent across files."""
        version_sources = {}

        # Common version locations
        for name in ["VERSION", "version.txt"]:
            path = PROJECT_ROOT / name
            if path.exists():
                version_sources[name] = path.read_text().strip()

        # package.json
        pkg_json = PROJECT_ROOT / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                version_sources["package.json"] = data.get("version", "not found")
            except json.JSONDecodeError:
                pass

        # pyproject.toml
        pyproject = PROJECT_ROOT / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            match = re.search(r'version\s*=\s*"([^"]+)"', content)
            if match:
                version_sources["pyproject.toml"] = match.group(1)

        # plugin.json
        for pj in PROJECT_ROOT.rglob("plugin.json"):
            if "node_modules" in str(pj):
                continue
            try:
                data = json.loads(pj.read_text())
                if "version" in data:
                    version_sources[str(pj.relative_to(PROJECT_ROOT))] = data["version"]
            except json.JSONDecodeError:
                pass

        if len(version_sources) < 2:
            pytest.skip(f"Only {len(version_sources)} version source(s) found — need 2+ to compare")

        result = genai.judge(
            question="Are version strings consistent across all config files?",
            context=f"Version sources:\n{json.dumps(version_sources, indent=2)}",
            criteria="All version strings should match or be clearly related (e.g., all 3.50.x). "
            "Score 10 = all identical, 5 = minor drift, 0 = major inconsistency.",
        )
        assert result["score"] >= 5, f"Version drift: {result['reasoning']}"

"""GenAI UAT: Security posture validation.

Validates security patterns in hooks and source code.
"""

import re

import pytest

from .conftest import PROJECT_ROOT

pytestmark = [pytest.mark.genai]

PLUGIN_ROOT = PROJECT_ROOT / "plugins" / "autonomous-dev"


class TestSecurityPosture:
    def test_hooks_use_exit_codes_correctly(self, genai):
        """Hooks should use named exit codes, not magic numbers."""
        hook_samples = []
        hooks_dir = PLUGIN_ROOT / "hooks"
        if hooks_dir.exists():
            for f in sorted(hooks_dir.glob("*.py"))[:6]:
                content = f.read_text(errors="ignore")[:1500]
                hook_samples.append(f"--- {f.name} ---\n{content}")

        result = genai.judge(
            question="Do hooks use named constants for exit codes?",
            context="\n\n".join(hook_samples),
            criteria="Hooks should use named constants (EXIT_SUCCESS, EXIT_BLOCK) or clear variable names "
            "rather than bare sys.exit(0)/sys.exit(1). Named constants improve maintainability. "
            "Score 10 = all named, 5 = mix of named and bare, 0 = all magic numbers.",
        )
        assert result["score"] >= 5, f"Exit code issues: {result['reasoning']}"

    def test_no_secrets_in_source(self, genai):
        """No API keys, tokens, or passwords in source files."""
        suspicious = []
        secret_patterns = [
            r'(?:api[_-]?key|token|password|secret)\s*=\s*["\'][^"\']{8,}',
            r'sk-[a-zA-Z0-9]{20,}',
            r'ghp_[a-zA-Z0-9]{20,}',
        ]

        for f in PROJECT_ROOT.rglob("*.py"):
            if any(x in str(f) for x in ["archived", "__pycache__", ".genai_cache", "venv"]):
                continue
            content = f.read_text(errors="ignore")
            for pattern in secret_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    line_no = content[: match.start()].count("\n") + 1
                    suspicious.append(f"{f.relative_to(PROJECT_ROOT)}:{line_no}: {match.group()[:40]}...")

        result = genai.judge(
            question="Are there hardcoded secrets in the source code?",
            context=f"Suspicious matches ({len(suspicious)}):\n" + "\n".join(suspicious[:20])
            if suspicious
            else "No suspicious patterns found.",
            criteria="Source files should NEVER contain real API keys, tokens, or passwords. "
            "Test fixtures with obvious fake values (test_key_123) are OK. "
            "Score 10 = clean, 5 = only test fixtures, 0 = real secrets found.",
        )
        assert result["score"] >= 7, f"Secret exposure risk: {result['reasoning']}"

    def test_path_traversal_protection(self, genai):
        """Hooks with file operations should validate paths."""
        hook_samples = []
        hooks_dir = PLUGIN_ROOT / "hooks"
        if hooks_dir.exists():
            for f in sorted(hooks_dir.glob("*.py")):
                content = f.read_text(errors="ignore")
                if any(kw in content for kw in ["open(", "Path(", "read_text", "write_text", "os.path"]):
                    hook_samples.append(f"--- {f.name} ---\n{content[:2000]}")

        if not hook_samples:
            pytest.skip("No hooks with file operations found")

        result = genai.judge(
            question="Do hooks validate file paths against traversal attacks?",
            context="\n\n".join(hook_samples[:4]),
            criteria="Hooks that read/write files based on input should validate paths "
            "(e.g., resolve symlinks, check within expected directory). "
            "Score 10 = explicit validation, 5 = implicit safety, 0 = no validation.",
        )
        assert result["score"] >= 5, f"Path traversal risk: {result['reasoning']}"

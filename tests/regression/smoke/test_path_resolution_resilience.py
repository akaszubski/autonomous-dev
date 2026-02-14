"""Regression tests for Path(__file__).parent chain resilience.

Ensures hooks in both hooks/ and hooks/archived/ resolve parent chains
to directories that actually contain expected siblings (lib/, config/).

Incident: PR #336-#343 moved 57 hooks to archived/, breaking parent.parent
chains that assumed hooks lived directly under plugins/autonomous-dev/hooks/.
"""

import ast
import re
from pathlib import Path

import pytest


class TestPathResolutionResilience:
    """Verify all hook files resolve Path(__file__).parent chains correctly."""

    def _get_hook_files(self, plugins_dir: Path, include_archived: bool = False) -> list[Path]:
        """Collect .py files in hooks/ (and optionally hooks/archived/)."""
        hooks_dir = plugins_dir / "hooks"
        files = list(hooks_dir.glob("*.py"))
        if include_archived:
            archived_dir = hooks_dir / "archived"
            if archived_dir.exists():
                files.extend(archived_dir.glob("*.py"))
        return [f for f in files if f.name != "__init__.py"]

    def _extract_parent_chains(self, filepath: Path) -> list[tuple[int, str, Path]]:
        """Extract Path(__file__).parent chains and resolve them.

        Returns list of (line_number, chain_text, resolved_path).
        """
        content = filepath.read_text()
        results = []
        # Match patterns like: Path(__file__).parent.parent / "lib"
        pattern = re.compile(
            r'(Path\(__file__\)(?:\.parent)+)\s*/\s*["\'](\w+)["\']'
        )
        for i, line in enumerate(content.splitlines(), 1):
            for match in pattern.finditer(line):
                chain = match.group(1)
                target_dir = match.group(2)
                # Count .parent occurrences
                parent_count = chain.count(".parent")
                resolved = filepath
                for _ in range(parent_count):
                    resolved = resolved.parent
                resolved = resolved / target_dir
                results.append((i, f"{chain} / \"{target_dir}\"", resolved))
        return results

    def test_all_parent_chains_resolve(self, plugins_dir: Path):
        """Every Path(__file__).parent chain in hooks must resolve to an existing dir."""
        hook_files = self._get_hook_files(plugins_dir)
        assert len(hook_files) > 0, "No hook files found"

        failures = []
        for filepath in hook_files:
            chains = self._extract_parent_chains(filepath)
            for line_no, chain_text, resolved in chains:
                if not resolved.exists():
                    rel = filepath.relative_to(plugins_dir)
                    failures.append(f"  {rel}:{line_no} — {chain_text} → {resolved} (NOT FOUND)")

        if failures:
            pytest.fail(
                f"Path resolution failures ({len(failures)}):\n" + "\n".join(failures)
            )

    def test_lib_path_accessible_from_all_hooks(self, plugins_dir: Path):
        """Every hook that references lib/ must resolve to the actual lib/ directory."""
        hook_files = self._get_hook_files(plugins_dir)
        lib_dir = plugins_dir / "lib"
        assert lib_dir.exists(), "lib/ directory missing"

        failures = []
        for filepath in hook_files:
            content = filepath.read_text()
            if "lib" not in content:
                continue
            chains = self._extract_parent_chains(filepath)
            lib_chains = [(ln, ct, rp) for ln, ct, rp in chains if rp.name == "lib"]
            for line_no, chain_text, resolved in lib_chains:
                if resolved != lib_dir:
                    rel = filepath.relative_to(plugins_dir)
                    failures.append(
                        f"  {rel}:{line_no} — resolves to {resolved}, expected {lib_dir}"
                    )

        if failures:
            pytest.fail(
                f"lib/ path misresolution ({len(failures)}):\n" + "\n".join(failures)
            )

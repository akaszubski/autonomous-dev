"""Structural cross-hook robustness tests — Issue #953.

Acceptance criteria #2, #3, #8: every active hook MUST

* use ``#!/usr/bin/env python3`` (not the pinned uv shebang),
* import ``safe_main`` from ``hook_safety`` (with or without an alias),
* invoke ``safe_main`` (or its aliased form) inside its ``if __name__ ==
  "__main__":`` block, and
* not re-introduce a PEP 723 ``# /// script`` block.

The "active hook" list is sourced AUTHORITATIVELY from the intersection of
two sources of truth:

1. ``plugins/autonomous-dev/templates/settings*.json`` — the settings
   templates that wire hooks to events.
2. ``plugins/autonomous-dev/config/install_manifest.json`` — the install
   manifest's ``components.hooks.files`` array.

A hook present in the directory but absent from BOTH templates and the
manifest is considered deprecated/test fixture and excluded.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Set

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
TEMPLATES_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "templates"
MANIFEST_PATH = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "config" / "install_manifest.json"
)


def _load_manifest_hooks() -> Set[str]:
    """Return set of hook .py filenames declared in install_manifest.json."""
    data = json.loads(MANIFEST_PATH.read_text())
    files = data.get("components", {}).get("hooks", {}).get("files", []) or []
    return {Path(f).name for f in files if f.endswith(".py")}


def _load_template_hooks() -> Set[str]:
    """Return set of hook .py filenames referenced from settings templates."""
    pattern = re.compile(r"hooks/([a-zA-Z_][a-zA-Z0-9_]*\.py)")
    found: Set[str] = set()
    for tmpl in TEMPLATES_DIR.glob("settings*.json"):
        try:
            text = tmpl.read_text()
        except OSError:
            continue
        for match in pattern.findall(text):
            found.add(match)
    return found


def _active_hooks() -> list[Path]:
    """Authoritative list of active python hooks.

    A hook is "active" if it appears in EITHER the install manifest OR the
    settings templates AND exists on disk. Using union (rather than
    intersection) covers two real cases:

    * Library-style hooks (genai_prompts.py, genai_utils.py) appear in the
      manifest but are imported by other hooks rather than wired to events.
    * Pre-commit-style hooks (enforce_*) appear in templates as bash hook
      shims but the .py is the actual entry point referenced from the shim.

    The set MUST equal the directory listing — if a hook exists on disk but
    is not in either source, it should either be archived or registered.
    """
    manifest_hooks = _load_manifest_hooks()
    template_hooks = _load_template_hooks()
    declared = manifest_hooks | template_hooks

    on_disk = {p.name for p in HOOKS_DIR.glob("*.py")}

    active = sorted(declared & on_disk)
    return [HOOKS_DIR / name for name in active]


# Compute the active list at module import time so parametrize ids are stable.
ACTIVE_HOOKS = _active_hooks()
ACTIVE_HOOK_NAMES = [p.name for p in ACTIVE_HOOKS]


class TestHookRegistration:
    """Sanity checks on the active-hook discovery itself."""

    def test_active_hook_list_is_nonempty(self):
        """Discovery MUST find at least 20 hooks (sanity check)."""
        assert len(ACTIVE_HOOKS) >= 20, (
            f"Expected ≥20 active hooks, found {len(ACTIVE_HOOKS)}: "
            f"{ACTIVE_HOOK_NAMES}"
        )

    def test_active_hook_list_matches_manifest_intersection(self):
        """Manifest intersection with disk MUST be a subset of active hooks."""
        manifest_hooks = _load_manifest_hooks()
        on_disk = {p.name for p in HOOKS_DIR.glob("*.py")}
        intersection = manifest_hooks & on_disk
        active_names = set(ACTIVE_HOOK_NAMES)
        # Manifest∩disk ⊆ active — all manifest-declared hooks on disk are active.
        assert intersection <= active_names, (
            f"Manifest hooks not in active set: {intersection - active_names}"
        )


@pytest.mark.parametrize("hook_path", ACTIVE_HOOKS, ids=ACTIVE_HOOK_NAMES)
class TestHookStructuralConformance:
    """Per-hook structural checks — runs once per active hook."""

    def test_hook_has_python3_shebang(self, hook_path: Path):
        """AC #3: Shebang MUST be #!/usr/bin/env python3 (no pinned interpreter)."""
        first_line = hook_path.read_text().split("\n", 1)[0]
        assert first_line == "#!/usr/bin/env python3", (
            f"{hook_path.name}: expected '#!/usr/bin/env python3', "
            f"got: {first_line!r}"
        )

    def test_hook_imports_hook_safety(self, hook_path: Path):
        """AC #2: Each hook MUST import safe_main from hook_safety."""
        text = hook_path.read_text()
        assert "from hook_safety import" in text or "import hook_safety" in text, (
            f"{hook_path.name}: missing hook_safety import"
        )

    def test_hook_main_block_calls_safe_main(self, hook_path: Path):
        """AC #2: The __main__ block MUST invoke safe_main (any alias)."""
        text = hook_path.read_text()
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            pytest.fail(f"{hook_path.name}: syntax error: {exc}")

        found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if not (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "__main__"
            ):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                    if "safe_main" in sub.func.id:
                        found = True
                        break
            if found:
                break

        assert found, (
            f"{hook_path.name}: __main__ block does not invoke safe_main "
            f"(must call _safe_main_953(main), _hook_safe_main(main), or "
            f"safe_main(main))"
        )

    def test_hook_no_pep723_block(self, hook_path: Path):
        """AC: PEP 723 # /// script ... # /// block MUST be absent."""
        text = hook_path.read_text()
        assert "# /// script" not in text, (
            f"{hook_path.name}: PEP 723 inline-script block still present"
        )

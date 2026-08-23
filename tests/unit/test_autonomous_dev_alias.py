"""The `autonomous_dev` import alias must come from the shim, not the symlink.

Issue #1582 follow-up. `plugins/autonomous-dev` contains a hyphen and cannot be
imported directly, so tests reach it through an alias. Two spellings are in use:

    from plugins.autonomous_dev.lib.X import Y     # prefixed
    from autonomous_dev.lib.X import Y             # bare

Only the prefixed spelling was registered in tests/conftest.py. The bare
spelling resolved through ``plugins/autonomous_dev`` -- a symlink listed in
.gitignore:31 that has never been committed. It is present on developer
machines and absent from every CI checkout, so 148 tests passed locally and
raised ``ModuleNotFoundError: No module named 'autonomous_dev'`` in CI
(measured: run 32639109196).

WHY THESE TESTS ARE SHAPED THIS WAY
-----------------------------------
On a developer machine the symlink exists, so ``import autonomous_dev`` succeeds
whether or not the shim is present. A test that merely imports the module would
pass under both the fixed and the broken configuration -- an instrument that
cannot fail and therefore cannot inform. Each test below is written so that it
distinguishes the two mechanisms:

* ``__path__`` is asserted to be the HYPHEN directory. Resolution via the
  symlink would yield ``plugins/autonomous_dev`` instead.
* The negative control removes the shim's ``sys.modules`` entries AND drops
  ``plugins/`` from ``sys.path``, which is the only configuration that
  reproduces a CI checkout on a machine that has the symlink.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGINS_DIR = REPO_ROOT / "plugins"
HYPHEN_DIR = PLUGINS_DIR / "autonomous-dev"
SYMLINK_PATH = PLUGINS_DIR / "autonomous_dev"

ALIAS_ROOTS = ("autonomous_dev", "plugins.autonomous_dev")


class TestAliasResolvesThroughTheShim:
    """The alias must point at the hyphen directory under every spelling."""

    @pytest.mark.parametrize("alias_root", ALIAS_ROOTS)
    def test_alias_root_is_registered(self, alias_root: str) -> None:
        assert alias_root in sys.modules, (
            f"{alias_root} is not registered. tests/conftest.py installs both "
            f"spellings; if this fails the shim was removed or reordered."
        )

    @pytest.mark.parametrize("alias_root", ALIAS_ROOTS)
    def test_alias_path_is_the_hyphen_directory_not_the_symlink(
        self, alias_root: str
    ) -> None:
        """This is the assertion the symlink cannot satisfy.

        Resolution through ``plugins/autonomous_dev`` would leave ``__path__``
        naming the symlink. The shim always names ``plugins/autonomous-dev``.
        """
        resolved = [Path(p) for p in sys.modules[alias_root].__path__]

        assert resolved == [HYPHEN_DIR], (
            f"{alias_root}.__path__ is {resolved}, expected [{HYPHEN_DIR}]. "
            f"A path naming {SYMLINK_PATH} means the name resolved through the "
            f"uncommitted symlink, which no CI checkout has."
        )

    @pytest.mark.parametrize("alias_root", ALIAS_ROOTS)
    @pytest.mark.parametrize("subpackage", ("lib", "scripts", "hooks"))
    def test_subpackages_are_registered(
        self, alias_root: str, subpackage: str
    ) -> None:
        name = f"{alias_root}.{subpackage}"
        assert name in sys.modules, f"{name} missing from the alias shim"
        assert [Path(p) for p in sys.modules[name].__path__] == [
            HYPHEN_DIR / subpackage
        ]

    def test_a_real_module_imports_through_the_bare_alias(self) -> None:
        """Positive control: the alias resolves an actual module, not a stub."""
        mod = importlib.import_module("autonomous_dev.lib.version_reader")

        assert hasattr(mod, "get_plugin_version")
        assert Path(mod.__file__) == HYPHEN_DIR / "lib" / "version_reader.py"


class TestTheShimIsLoadBearing:
    """Negative control: without the shim the bare spelling must fail."""

    def test_bare_import_fails_when_shim_and_plugins_path_are_both_absent(
        self,
    ) -> None:
        """Reproduce a CI checkout in-process, then prove the shim fixes it.

        Dropping ONLY the sys.modules entries is not enough on a developer
        machine: the bare name would still resolve through the symlink under
        ``plugins/``. Dropping ``plugins/`` from sys.path as well is what makes
        this arm equivalent to a checkout that never had the symlink.
        """
        saved_modules = {
            name: sys.modules[name]
            for name in list(sys.modules)
            if name == "autonomous_dev" or name.startswith("autonomous_dev.")
        }
        saved_path = list(sys.path)
        plugins_str = str(PLUGINS_DIR)

        try:
            for name in saved_modules:
                del sys.modules[name]
            sys.path[:] = [
                p for p in sys.path if Path(p).resolve() != PLUGINS_DIR.resolve()
            ]

            assert plugins_str not in [
                str(Path(p).resolve()) for p in sys.path
            ], "precondition: plugins/ must be off sys.path for this arm"

            with pytest.raises(ModuleNotFoundError):
                importlib.import_module("autonomous_dev.lib.version_reader")
        finally:
            sys.path[:] = saved_path
            sys.modules.update(saved_modules)

        # Restored arm: the shim's entries are back and the import works again.
        assert importlib.import_module("autonomous_dev.lib.version_reader")


class TestSymlinkIsNotTheMechanism:
    """The symlink must not be what CI depends on -- it cannot be."""

    def test_symlink_is_not_committed(self) -> None:
        """Documents the precondition that makes the shim mandatory.

        If someone later commits the symlink this fails, which is the moment to
        decide deliberately between two mechanisms rather than drift into both.
        """
        tracked = subprocess.run(
            ["git", "ls-files", "plugins/autonomous_dev"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()

        assert tracked == "", (
            f"plugins/autonomous_dev is now tracked ({tracked!r}). The alias is "
            f"supposed to have exactly one mechanism -- the conftest shim. "
            f"Committing the symlink adds a second."
        )

    def test_hyphen_directory_is_the_real_one(self) -> None:
        assert HYPHEN_DIR.is_dir()
        assert not HYPHEN_DIR.is_symlink()

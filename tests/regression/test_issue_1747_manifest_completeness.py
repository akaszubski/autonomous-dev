"""Regression controls for Issue #1747 -- install_manifest.json completeness.

The manifest is the ONLY file list a fresh install reads
(``scripts/install.py:396-417`` copies exactly what is listed). Four blind spots
shipped a green-but-broken manifest:

1. The generator scanned ``lib/*.py`` non-recursively, so 4 subpackages (25 files)
   never shipped. ``hooks/unified_session_tracker.py:116`` does
   ``from agent_tracker import AgentTracker``; without the package the import dies.
2. ``install.py`` flattened every manifest path to its basename, collapsing all 30
   skills onto one destination and colliding three distinct ``cli.py`` files.
3. No check asserted the generator itself was in sync against the manifest that
   actually ships.
4. Nothing refused a component ``target`` that escapes ``.claude/``, nor a manifest
   entry that would overwrite a consumer repo's own ``CLAUDE.md``.

Each test below states the mutation that must turn it red, and exercises both the
refusing and permitting arm.

There is deliberately NO ``except ImportError`` and NO module-level
``pytest.skip`` in this file -- Issue #1469 records that pattern silently zeroing
56 tests for months. If an import breaks here, the test MUST error loudly.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# tests/regression/test_x.py -> regression -> tests -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev"
MANIFEST_PATH = PLUGIN_DIR / "config" / "install_manifest.json"
INSTALL_PY = PLUGIN_DIR / "scripts" / "install.py"
GENERATOR = PLUGIN_DIR / "hooks" / "archived" / "validate_install_manifest.py"

SUBPROCESS_TIMEOUT = 60


def _load_module(name: str, path: Path):
    """Load a module from an explicit file path.

    Args:
        name: Module name to register under.
        path: Absolute path to the .py file.

    Returns:
        The executed module object.

    Raises:
        AssertionError: If the file is missing or has no loader.
    """
    assert path.is_file(), f"POSITIVE CONTROL: {path} does not exist"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"no loader for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _real_install_mapping(manifest: Dict[str, Any]) -> Dict[str, str]:
    """Map manifest entries to install destinations via the REAL installer code.

    A reimplementation of the mapping here would drift from ``install.py`` and
    stop testing it, so the production function is called directly.

    Args:
        manifest: Parsed install_manifest.json (or a mutated copy).

    Returns:
        Dict of ``github_path -> local destination path``.
    """
    install_mod = _load_module("adev_install_under_test", INSTALL_PY)
    installer = install_mod.PluginInstaller(mode="check", verbose=False)
    return installer.get_all_files_from_manifest(manifest)


def _read_manifest() -> Dict[str, Any]:
    """Parse the shipping manifest.

    Returns:
        Parsed install_manifest.json.
    """
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _scrubbed_env(pythonpath: Path, home: Path) -> Dict[str, str]:
    """Build a minimal environment that cannot leak the repo onto sys.path.

    Args:
        pythonpath: The single directory to expose as PYTHONPATH.
        home: HOME for the child process.

    Returns:
        Environment mapping for ``subprocess.run``.
    """
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(pythonpath),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": str(home),
    }


# ---------------------------------------------------------------------------
# CONTROL 1 -- a manifest-only tree must be importable
# ---------------------------------------------------------------------------


def _materialize_manifest_tree(manifest: Dict[str, Any], root: Path) -> Path:
    """Build a tree containing ONLY manifest-listed files, at install destinations.

    Args:
        manifest: Parsed manifest to materialize.
        root: Directory to build the tree under.

    Returns:
        Path to the materialized ``.claude/lib`` directory.
    """
    for github_path, local_path in _real_install_mapping(manifest).items():
        source = PROJECT_ROOT / github_path
        if not source.is_file():
            continue
        destination = root / local_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    return root / ".claude" / "lib"


def _import_probe(lib_dir: Path, cwd: Path, home: Path) -> subprocess.CompletedProcess:
    """Run the import probe in a fresh interpreter pinned to ``lib_dir``.

    ``-P`` keeps cwd off sys.path, and ``cwd`` is outside the repo, so a pass
    cannot come from the source tree. Both a bare ``import`` and a
    ``from pkg import submodule`` are exercised: PEP 420 makes the bare form
    succeed on a namespace directory even when siblings are missing.

    Args:
        lib_dir: Directory to expose as PYTHONPATH.
        cwd: Working directory for the child (must be outside the repo).
        home: HOME for the child.

    Returns:
        The completed process.
    """
    code = (
        "import agent_tracker\n"
        "from agent_tracker import cli\n"
        "print(agent_tracker.__file__)\n"
    )
    return subprocess.run(
        [sys.executable, "-P", "-B", "-c", code],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=_scrubbed_env(lib_dir, home),
        timeout=SUBPROCESS_TIMEOUT,
    )


def test_manifest_only_tree_can_import_subpackages(tmp_path: Path) -> None:
    """A tree built from the manifest alone must satisfy the hooks' imports.

    Mutation that turns this red: revert ``install.py`` destination mapping to
    ``Path(github_path).name`` -- ``agent_tracker/`` never becomes a directory and
    the backward-compat shim ``agent_tracker.py`` self-imports.

    Negative control (asserted below): removing one subpackage file from the
    materialized tree must make the same probe fail, proving the probe can fail.
    """
    tree = tmp_path / "install_tree"
    tree.mkdir()
    outside = tmp_path / "outside_repo"
    outside.mkdir()

    lib_dir = _materialize_manifest_tree(_read_manifest(), tree)
    assert lib_dir.is_dir(), "manifest produced no .claude/lib directory"
    assert PROJECT_ROOT not in outside.parents and outside != PROJECT_ROOT, (
        "probe cwd must be outside the repo"
    )

    # PERMITTING ARM
    result = _import_probe(lib_dir, cwd=outside, home=tmp_path)
    assert result.returncode == 0, (
        "manifest-only tree cannot import agent_tracker:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    resolved = Path(result.stdout.strip()).resolve()
    assert str(resolved).startswith(str(tmp_path.resolve())), (
        f"import resolved OUTSIDE the manifest tree ({resolved}) -- the probe read "
        f"the source tree, so a pass here proves nothing"
    )

    # NEGATIVE CONTROL / INSTRUMENT CHECK -- the probe must be able to fail.
    victim = lib_dir / "agent_tracker" / "cli.py"
    assert victim.is_file(), "POSITIVE CONTROL: agent_tracker/cli.py was not shipped"
    victim.unlink()
    broken = _import_probe(lib_dir, cwd=outside, home=tmp_path)
    assert broken.returncode != 0, (
        "INSTRUMENT FAILURE: removing agent_tracker/cli.py did not break the import "
        "probe, so its earlier pass carries no information"
    )


# ---------------------------------------------------------------------------
# CONTROL 2 -- the generator and the shipping manifest must agree
# ---------------------------------------------------------------------------


def _resolved_manifest_path(cwd: Path) -> str:
    """Ask the generator which manifest it resolves from a given cwd.

    ``get_project_root()`` walks up from ``Path.cwd()``, so an unpinned cwd
    silently validates the wrong manifest in a worktree or CI checkout.

    Args:
        cwd: Working directory to resolve from.

    Returns:
        The manifest path the generator would use, as a string.
    """
    probe = (
        "import importlib.util\n"
        "from pathlib import Path\n"
        f"spec = importlib.util.spec_from_file_location('gen', r'{GENERATOR}')\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "print(mod.get_project_root() / 'plugins' / 'autonomous-dev' / 'config'"
        " / 'install_manifest.json')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", probe],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, f"generator probe failed: {result.stderr}"
    return result.stdout.strip()


def test_manifest_declares_every_shipping_file(tmp_path: Path) -> None:
    """The committed manifest must equal what the generator scans.

    Mutation that turns this red: delete one entry from the manifest -- the
    generator's ``--check-only`` exits 1 and names it.

    Instrument control (asserted below): the same resolution run from a scratch
    cwd must NOT point at the repo manifest, proving the cwd pin is load-bearing.
    """
    expected = str(MANIFEST_PATH)

    # Trust nothing until we know WHICH manifest is being checked.
    assert _resolved_manifest_path(PROJECT_ROOT) == expected, (
        "generator resolved a different manifest than the one that ships"
    )

    # INSTRUMENT CONTROL -- an unpinned cwd resolves elsewhere.
    scratch = tmp_path / "scratch_repo"
    scratch.mkdir()
    assert _resolved_manifest_path(scratch) != expected, (
        "INSTRUMENT FAILURE: the cwd pin does nothing -- a scratch cwd resolved the "
        "same manifest, so the assertion above cannot detect a wrong-repo check"
    )

    def _check_only(cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-B", str(GENERATOR), "--check-only"],
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=SUBPROCESS_TIMEOUT,
        )

    # PERMITTING ARM
    in_sync = _check_only(PROJECT_ROOT)
    assert in_sync.returncode == 0, (
        "install_manifest.json is out of sync with the source tree.\n"
        "Run: python3 plugins/autonomous-dev/hooks/archived/validate_install_manifest.py\n"
        f"{in_sync.stdout}\n{in_sync.stderr}"
    )

    # REFUSING ARM -- drop one real entry and confirm the generator refuses.
    original = MANIFEST_PATH.read_bytes()
    try:
        mutated = json.loads(original.decode("utf-8"))
        dropped = mutated["components"]["lib"]["files"].pop()
        MANIFEST_PATH.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
        refused = _check_only(PROJECT_ROOT)
        assert refused.returncode != 0, (
            f"generator accepted a manifest missing {dropped} -- it cannot refuse"
        )
        assert dropped in refused.stdout, (
            f"generator refused but did not name the missing file {dropped}"
        )
    finally:
        MANIFEST_PATH.write_bytes(original)
    assert MANIFEST_PATH.read_bytes() == original, "manifest was not restored"


# ---------------------------------------------------------------------------
# CONTROL 3 -- no component target may escape .claude/
# ---------------------------------------------------------------------------


def _target_escapes_dot_claude(target: str) -> bool:
    """Report whether an install target escapes the ``.claude/`` sandbox.

    Args:
        target: A ``components.*.target`` value from the manifest.

    Returns:
        True if the target is absolute, traverses, or lands outside ``.claude/``.
    """
    if not target or Path(target).is_absolute() or target.startswith("~"):
        return True
    # Check the RAW string: pathlib silently drops "." segments, so
    # Path(".claude/./x").parts is ('.claude', 'x') and a parts-based
    # check for "." can never fire.
    if ".." in target or "/./" in target or target.startswith("./"):
        return True
    if ".." in Path(target).parts:
        return True
    normalized = os.path.normpath(target).replace(os.sep, "/")
    return normalized != ".claude" and not normalized.startswith(".claude/")


@pytest.mark.parametrize(
    "hostile_target",
    ["../evil", "/etc", ".claude/../../evil", "~/evil", ".claude/./x", "", "other/dir"],
)
def test_target_escape_detector_refuses_hostile_targets(hostile_target: str) -> None:
    """NEGATIVE CONTROL for the target check -- it must refuse these.

    Without this arm, a detector that always returns False would let the test
    below pass vacuously.
    """
    assert _target_escapes_dot_claude(hostile_target), (
        f"detector permitted an escaping target: {hostile_target!r}"
    )


def test_no_component_target_escapes_dot_claude() -> None:
    """Every shipping component target must normalize under ``.claude/``.

    Mutation that turns this red: set any ``components.*.target`` to ``../evil``
    or ``/etc``.

    Positive control: all current component targets must pass.
    """
    components = _read_manifest()["components"]
    assert len(components) >= 8, f"expected >=8 components, got {len(components)}"

    escaping = {
        name: component.get("target")
        for name, component in components.items()
        if _target_escapes_dot_claude(component.get("target", ""))
    }
    assert not escaping, f"component targets escape .claude/: {escaping}"


# ---------------------------------------------------------------------------
# CONTROL 4 -- no manifest entry may author a consumer repo's CLAUDE.md
# ---------------------------------------------------------------------------


def _is_consumer_claude_md(destination: str) -> bool:
    """Report whether a destination would overwrite a consumer's own CLAUDE.md.

    autonomous-dev's CLAUDE.md stays in autonomous-dev. Consumer repos author
    their own from ``templates/CLAUDE.md.template``, so the TEMPLATE landing at
    ``.claude/templates/CLAUDE.md.template`` is correct and must be permitted.

    Args:
        destination: An install destination path.

    Returns:
        True if the destination is a repo-root or ``.claude/`` CLAUDE.md.
    """
    normalized = os.path.normpath(destination).replace(os.sep, "/")
    return normalized in {"CLAUDE.md", ".claude/CLAUDE.md"}


def test_consumer_claude_md_detector_both_arms() -> None:
    """NEGATIVE + POSITIVE control for the CLAUDE.md destination detector."""
    assert _is_consumer_claude_md("CLAUDE.md")
    assert _is_consumer_claude_md(".claude/CLAUDE.md")
    assert _is_consumer_claude_md(".claude/./CLAUDE.md")
    # The template is a DIFFERENT thing and must be permitted.
    assert not _is_consumer_claude_md(".claude/templates/CLAUDE.md.template")
    assert not _is_consumer_claude_md(".claude/lib/paths.py")


def test_no_manifest_entry_produces_a_consumer_claude_md() -> None:
    """No manifest entry may install onto a consumer repo's CLAUDE.md.

    Destinations are computed through the SAME mapping ``install.py`` uses, so
    this tracks the installer rather than a copy of its rules.

    Mutation (exercised below): add an entry whose computed destination is
    ``.claude/CLAUDE.md`` -- the scan must flag it.

    Positive control (asserted below): ``templates/CLAUDE.md.template`` must
    still map to ``.claude/templates/CLAUDE.md.template`` and be permitted.
    """
    manifest = _read_manifest()
    mapping = _real_install_mapping(manifest)

    offenders = {
        source: destination
        for source, destination in mapping.items()
        if _is_consumer_claude_md(destination)
    }
    assert not offenders, (
        f"manifest entries would overwrite a consumer repo's CLAUDE.md: {offenders}"
    )

    # POSITIVE CONTROL -- the scaffolding template must still ship, nested.
    template_source = "plugins/autonomous-dev/templates/CLAUDE.md.template"
    assert mapping.get(template_source) == ".claude/templates/CLAUDE.md.template", (
        f"CLAUDE.md.template must ship to .claude/templates/, got "
        f"{mapping.get(template_source)!r}"
    )

    # REFUSING ARM -- an entry that WOULD land on .claude/CLAUDE.md is caught.
    mutated = _read_manifest()
    mutated["components"]["hostile"] = {
        "files": ["plugins/autonomous-dev/CLAUDE.md"],
        "target": ".claude",
        "exclude": [],
    }
    mutated_mapping = _real_install_mapping(mutated)
    assert any(
        _is_consumer_claude_md(destination) for destination in mutated_mapping.values()
    ), "the scan did not flag an entry landing on .claude/CLAUDE.md"


def test_install_mapping_refuses_path_traversal() -> None:
    """A poisoned manifest entry must be refused, not written outside the target.

    Mutation that turns this red: drop the ``".." in path`` refusal from
    ``install.py``'s destination mapping.
    """
    poisoned = {
        "components": {
            "lib": {
                "files": ["plugins/autonomous-dev/lib/../../../etc/passwd"],
                "target": ".claude/lib",
                "exclude": [],
            }
        }
    }
    with pytest.raises(ValueError, match="Path traversal"):
        _real_install_mapping(poisoned)

    # PERMITTING ARM -- a clean entry still maps.
    clean = {
        "components": {
            "lib": {
                "files": ["plugins/autonomous-dev/lib/agent_tracker/cli.py"],
                "target": ".claude/lib",
                "exclude": [],
            }
        }
    }
    assert _real_install_mapping(clean) == {
        "plugins/autonomous-dev/lib/agent_tracker/cli.py": ".claude/lib/agent_tracker/cli.py"
    }


# ---------------------------------------------------------------------------
# CONTROL 5 -- the PRODUCTION installer must refuse a hostile component target
#
# Security remediation for Issue #1747. `_target_escapes_dot_claude` above is a
# test-local reimplementation: it only ever inspects the committed manifest, so
# it catches a maintainer mistake and nothing else. The manifest is fetched over
# the network at install time with no signature check, so the refusal has to live
# in the executing installer. These tests drive the real
# ``PluginInstaller.get_all_files_from_manifest``.
# ---------------------------------------------------------------------------

HOSTILE_TARGETS = [
    "/etc",  # absolute -- pathlib DISCARDS the staging dir on `temp_dir / abs`
    "/tmp/OUTSIDE_TARGET",
    "../evil",
    ".claude/../../evil",
    "~/evil",
    ".claude/./x",  # raw-string check only: Path(".claude/./x").parts drops the "."
    "./x",
    "",
    "other/dir",
    ".claude\\..\\evil",
    "%2e%2e/evil",  # encoded marker, defense in depth
]


@pytest.mark.parametrize("hostile_target", HOSTILE_TARGETS)
def test_production_installer_refuses_hostile_target(hostile_target: str) -> None:
    """The real installer must raise on a manifest whose ``target`` escapes.

    Mutation that turns this red: delete the ``validate_manifest_target(component,
    target)`` call from ``install.py::get_all_files_from_manifest``. Verified by
    hand -- with the call removed, the absolute targets return an ABSOLUTE
    destination instead of raising, and this test fails for every hostile value.

    This is a different shape from the file-entry reproducer above: the escape
    comes from the component ``target`` field, not from a ``files[]`` entry.
    """
    poisoned = {
        "components": {
            "evil": {
                "target": hostile_target,
                "files": ["plugins/autonomous-dev/lib/agent_tracker.py"],
                "exclude": [],
            }
        }
    }
    with pytest.raises(ValueError, match="Unsafe install target"):
        _real_install_mapping(poisoned)


def test_production_installer_permits_shipping_targets() -> None:
    """PERMITTING ARM -- every real component target must still map cleanly.

    Without this arm, a validator that refused everything would pass the refusing
    arm above.
    """
    mapping = _real_install_mapping(_read_manifest())
    assert len(mapping) >= 400, f"expected the full manifest, got {len(mapping)} entries"
    absolute = [d for d in mapping.values() if Path(d).is_absolute()]
    assert not absolute, f"destinations escaped to absolute paths: {absolute[:5]}"
    outside = [d for d in mapping.values() if not d.startswith(".claude/")]
    assert not outside, f"destinations outside .claude/: {outside[:5]}"


def test_production_installer_refuses_encoded_traversal_in_file_entry() -> None:
    """Encoded traversal markers in a ``files[]`` entry are refused.

    NOT exploitable today -- nothing URL-decodes a manifest path before building
    the destination, so ``%2e%2e`` is currently just an ordinary directory name.
    Rejected so that adding a decode step later cannot silently open a traversal.

    Mutation that turns this red: drop the ``ENCODED_TRAVERSAL_MARKERS`` loop from
    ``install.py::validate_manifest_file_path``.
    """
    poisoned = {
        "components": {
            "lib": {
                "target": ".claude/lib",
                "files": ["plugins/autonomous-dev/lib/%2e%2e%2fetc/passwd"],
                "exclude": [],
            }
        }
    }
    with pytest.raises(ValueError, match="Path traversal detected"):
        _real_install_mapping(poisoned)


# ---------------------------------------------------------------------------
# CONTROL 6 -- the staging write itself must stay inside the staging dir
#
# Defense in depth: staging is where a hostile destination actually lands on
# disk, and it runs BEFORE FileManager.validate_path, the only pre-existing
# containment gate. This drives download_to_temp with a mapping that already
# contains an absolute destination -- i.e. it simulates CONTROL 5 having been
# removed -- so the two guards are proven independently.
# ---------------------------------------------------------------------------


class _StubDownloader:
    """Return fixed bytes for any URL, so no network is touched."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def download_file(self, url: str) -> bytes:
        """Return the canned payload.

        Args:
            url: Ignored.

        Returns:
            The canned payload bytes.
        """
        return self.payload


def _installer_with_stub(payload: bytes):
    """Build a PluginInstaller whose downloader never touches the network.

    Args:
        payload: Bytes every "download" returns.

    Returns:
        The configured PluginInstaller instance.
    """
    install_mod = _load_module("adev_install_under_test", INSTALL_PY)
    installer = install_mod.PluginInstaller(mode="check", verbose=False)
    installer.downloader = _StubDownloader(payload)
    return installer


def test_staging_refuses_absolute_destination(tmp_path: Path) -> None:
    """``download_to_temp`` must refuse to write outside its staging dir.

    Mutation that turns this red: delete the ``assert_contained(...)`` call from
    ``install.py::download_to_temp`` and restore ``temp_path = self.temp_dir /
    local_path``. Verified by hand -- with the call removed the payload is written
    to the absolute path and this test fails on both assertions.
    """
    outside = tmp_path / "OUTSIDE_TARGET" / "agent_tracker.py"
    installer = _installer_with_stub(b"PWNED-BY-MANIFEST-TARGET-FIELD")

    try:
        with pytest.raises(ValueError, match="outside its root"):
            installer.download_to_temp(
                {"plugins/autonomous-dev/lib/agent_tracker.py": str(outside)}
            )
        assert not outside.exists(), f"staging wrote outside the staging dir: {outside}"
    finally:
        shutil.rmtree(installer.temp_dir, ignore_errors=True)


def test_staging_permits_relative_destination() -> None:
    """PERMITTING ARM -- a legitimate relative destination still stages.

    Without this arm, an ``assert_contained`` that refused everything would pass
    the refusing arm above.
    """
    installer = _installer_with_stub(b"legitimate-content")
    try:
        assert installer.download_to_temp(
            {"plugins/autonomous-dev/lib/agent_tracker/cli.py": ".claude/lib/agent_tracker/cli.py"}
        ), "a legitimate relative destination was refused"

        staged = installer.temp_dir / ".claude" / "lib" / "agent_tracker" / "cli.py"
        assert staged.is_file(), f"legitimate file was not staged at {staged}"
        assert staged.read_bytes() == b"legitimate-content"
    finally:
        shutil.rmtree(installer.temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# CONTROL 7 -- the pre-commit manifest gate must fail CLOSED
#
# `if [ -f validator ]; then ... fi` with no else is indistinguishable from a
# passing gate when the validator is deleted or renamed -- the same shape as the
# original Issue #1747 defect, where the validator had no caller at all.
#
# The block is extracted from the REAL hook on disk, not from a copy, so a change
# to the hook is what these arms see.
# ---------------------------------------------------------------------------

PRE_COMMIT_HOOK = PROJECT_ROOT / "scripts" / "hooks" / "pre-commit"
MANIFEST_RELPATH = "plugins/autonomous-dev/config/install_manifest.json"


def _extract_manifest_gate_block() -> str:
    """Slice the manifest-validation gate out of the real pre-commit hook.

    Returns:
        The shell source of the gate, from its banner echo to its closing ``fi``.

    Raises:
        AssertionError: If the hook or the block cannot be located.
    """
    assert PRE_COMMIT_HOOK.is_file(), f"POSITIVE CONTROL: {PRE_COMMIT_HOOK} does not exist"
    lines = PRE_COMMIT_HOOK.read_text(encoding="utf-8").splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if "Validating install manifest completeness" in line]
    assert len(starts) == 1, f"expected 1 gate banner in the hook, found {len(starts)}"
    start = starts[0]
    end = next(i for i, line in enumerate(lines[start:], start) if line.rstrip() == "fi")
    return "".join(lines[start : end + 1])


def _run_gate(cwd: Path) -> subprocess.CompletedProcess:
    """Run the extracted gate block with ``cwd`` as the working directory.

    Args:
        cwd: Directory to run the gate in.

    Returns:
        The completed process.
    """
    return subprocess.run(
        ["bash", "-c", _extract_manifest_gate_block()],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=SUBPROCESS_TIMEOUT,
    )


def test_precommit_manifest_gate_refuses_when_validator_missing(tmp_path: Path) -> None:
    """REFUSING ARM -- a manifest with no validator must abort the commit.

    Mutation that turns this red: delete the ``elif [ -f
    "plugins/autonomous-dev/config/install_manifest.json" ]`` fail-closed branch
    from ``scripts/hooks/pre-commit`` and leave the bare ``fi``.
    """
    repo = tmp_path / "manifest_but_no_validator"
    (repo / Path(MANIFEST_RELPATH).parent).mkdir(parents=True)
    (repo / MANIFEST_RELPATH).write_text("{}\n", encoding="utf-8")

    result = _run_gate(repo)
    assert result.returncode != 0, (
        f"gate PERMITTED a commit with a manifest and no validator:\n{result.stdout}"
    )
    assert "validate_manifest.py is MISSING" in result.stdout, (
        f"gate refused but did not name the missing validator:\n{result.stdout}"
    )


def test_precommit_manifest_gate_is_inert_without_a_manifest(tmp_path: Path) -> None:
    """PERMITTING ARM 1 -- no manifest means nothing for this gate to say.

    Without this arm a gate that refused unconditionally would pass the refusing
    arm above, and it would break the sandbox in
    ``tests/regression/test_precommit_fail_open_guard.py``, which relies on the
    other checks staying inert.
    """
    repo = tmp_path / "no_manifest"
    repo.mkdir()
    result = _run_gate(repo)
    assert result.returncode == 0, (
        f"gate refused a repo with no manifest at all:\n{result.stdout}{result.stderr}"
    )


def test_precommit_manifest_gate_permits_this_repo() -> None:
    """PERMITTING ARM 2 -- the real repo, with both files present, must pass."""
    result = _run_gate(PROJECT_ROOT)
    assert result.returncode == 0, (
        f"gate refused the real repo:\n{result.stdout}{result.stderr}"
    )

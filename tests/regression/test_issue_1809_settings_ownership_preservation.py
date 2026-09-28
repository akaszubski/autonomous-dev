"""SOURCE-ROUTE regression tests for Issue #1809 (settings preservation).

SCOPE — READ BEFORE CITING THESE TESTS AS EVIDENCE
--------------------------------------------------
These are **SOURCE-ROUTE** tests. They drive the canonical ownership-aware
settings owner (``settings_merger.apply_owned_settings``) and the source copies
of the writers routed through it. They prove **source behaviour only**.

They are **NOT** installed-consumer proof: nothing here reads a real
``~/.claude/settings.json``, runs ``scripts/deploy-all.sh``, or observes a
deployed consumer repo. Installed-consumer proof is a **separate open arm of
Issue #1809** and MUST NOT be claimed on the strength of this module.

Hook uniqueness is asserted at **REGISTRATION level** (one owned entry per
lifecycle event in the settings file). No claim is made about physical process
count or native event delivery — that is also an open arm.

WHAT IS CLAIMED — exact scope, two arms, do not conflate them
------------------------------------------------------------
This slice establishes TWO things and NOT a third:

CLAIM A — settings-write preservation and refusal. ``apply_owned_settings``
updates only toolkit-owned entries, and refuses (zero mutation: file bytes,
directory set AND directory modes) on malformed/ambiguous state, conflicting
owned registrations, an out-of-profile path, a concurrent modification, or a
live run. It holds an ``fcntl`` lock across its own read -> merge -> re-check ->
rename. **That lock covers the SETTINGS FILE transaction only** — not the
surrounding multi-file deploy — and it binds **other toolkit writers only**.
``record_run_start`` does NOT participate in that lock, so a run starting
mid-settings-write is excluded only from the settings file, and only against
toolkit writers.

CLAIM B — POINT-IN-TIME admission at route entry. Two routes consult the shared
admission owner before their first mutation. This is **check-then-write**: it
refuses a run that is ALREADY live at entry. It is a real improvement and it is
**NOT** the census's throughout-transaction exclusion.

NOT CLAIMED — active-run interlock for the mutation transaction. **OPEN /
UNMEASURED, RELEASE-BLOCKING, for ALL routes including both marketplace
routes.** A run can legitimately start AFTER admission returns and BEFORE (or
during) any subsequent copy: ``check_mutation_admission`` returns a bool,
neither route holds a shared interlock through the ensuing ``mkdir``/copies, and
``record_run_start`` takes part in no mutual exclusion. Closing it requires
touching the run-start owners (``pipeline_completion_state`` /
``pipeline_state``), which are outside this slice's boundary and carry their own
#1806/#1807 evidence chains. It needs its own slice with a shared interlock
honoured by BOTH ``record_run_start`` and the deploy transaction, plus a
deterministic interleaving negative (run starts mid-copy -> deploy aborts with
defined recovery). **No route in this slice is "safe" or fully ROUTED for the
interlock arm.**

ROUTED for CLAIM A + CLAIM B only (each with a behavioural test below)
---------------------------------------------------------------------
* ``plugins/autonomous-dev/scripts/sync_settings_hooks.py`` — the CLI entrypoint
  ``scripts/deploy-all.sh`` invokes. Proven via **subprocess**, the same way
  deploy-all.sh calls it: :func:`test_route_sync_settings_hooks_cli_subprocess`.
* ``plugins/autonomous-dev/lib/sync_dispatcher/dispatcher.py::sync_marketplace``
  — :func:`test_route_dispatcher_preserves_and_aggregates` plus the
  point-in-time admission negative
  :func:`test_route_dispatcher_admission_precedes_first_file_mutation`.
* ``plugins/autonomous-dev/lib/sync_dispatcher/modes.py::dispatch_marketplace``
  — the user-invocable ``/sync --marketplace`` route. Point-in-time admission is
  hoisted ahead of its first copy, fails CLOSED when the admission owner cannot
  be imported, and BOTH arms are proven for that exact entrypoint by
  :func:`test_route_modes_dispatch_marketplace_admission_arms` and
  :func:`test_route_modes_fails_closed_without_admission_owner`.
* ``plugins/autonomous-dev/lib/sync_dispatcher/modes.py`` settings write —
  :func:`test_route_modes_preserves_and_raises_on_failure`.

OPEN / UNMEASURED — each RELEASE-SIGNIFICANT and separately open
---------------------------------------------------------------
None of these may be folded into another's disposition, and **#1809 stays open
regardless**: no installed-safety claim is supported while any remain.

* **Active-run interlock through the mutation transaction** — see NOT CLAIMED
  above. Release-blocking, applies to every route.
* ``plugins/autonomous-dev/lib/plugin_updater.py::_activate_hooks`` ->
  ``HookActivator.activate_hooks`` — an ACTIVE settings writer that treats
  activation errors as non-blocking update SUCCESS. Not routed through the owner,
  no admission check, not tested here.
* ``plugins/autonomous-dev/lib/sync_dispatcher/modes.py::dispatch_plugin_dev``
  — same shape as ``dispatch_marketplace`` (copies via ``_sync_directory``
  before the settings write) and NOT given an admission check by this
  remediation, whose scope was ``dispatch_marketplace`` only. Named here so its
  absence is not inferred from its sibling being fixed.
* ``scripts/deploy-all.sh`` — the shell route's own early ``mkdir``/``rsync``
  happen outside any Python admission check. Untouched.
* Cross-repo writes (``deploy-all.sh`` lines 377/614 syncing
  ``$HOME/Dev/$repo``) — deliberately FAIL CLOSED, see
  :func:`test_out_of_profile_targets_fail_closed`.

THE DEFECT
----------
Pre-fix writers replaced whole settings blocks: ``user_settings["hooks"] =
template_hooks``, ``permissions["deny"] = canonical_deny``,
``user_data["hooks"] = template_hooks``. Measured loss against POPULATED-3: a
consumer's own SessionStart hook, their own PostToolUse hook, and their custom
deny entry were all destroyed while the writer reported success.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest

# tests/regression/test_*.py -> parents[2] == repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_ROOT = _REPO_ROOT / "plugins" / "autonomous-dev"
_LIB = _PLUGIN_ROOT / "lib"
for _p in (str(_LIB), str(_PLUGIN_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import settings_merger  # noqa: E402
from settings_merger import (  # noqa: E402
    RefusalClass,
    apply_owned_settings,
    resolve_owned_hook_basenames,
    settings_digest,
)

_MANIFEST_PATH = _PLUGIN_ROOT / "config" / "install_manifest.json"
_LAYERS = ("user", "project", "local", "explicit")
_OWNED_DENY = ["Bash(sudo:*)", "Edit(//etc/**)"]

# Real manifest entries — ownership is derived from the manifest, not position.
_OWNED_PRE_TOOL = "python3 ~/.claude/hooks/unified_pre_tool.py"
_OWNED_SESSION_START = "bash ~/.claude/hooks/SessionStart-batch-recovery.sh"


# =============================================================================
# Fixtures — one builder, parameterized by layer tag
# =============================================================================

def _owned_template() -> Dict[str, Any]:
    """The toolkit projection: two events, both toolkit-owned."""
    def group(command: str, timeout: int) -> Dict[str, Any]:
        return {
            "matcher": "*",
            "hooks": [{"type": "command", "command": command, "timeout": timeout}],
        }

    return {
        "hooks": {
            "PreToolUse": [group(_OWNED_PRE_TOOL, 5)],
            "SessionStart": [group(_OWNED_SESSION_START, 10)],
        }
    }


def _foreign_command(tag: str, kind: str) -> str:
    """A consumer-owned script basename, absent from the toolkit manifest."""
    return f"bash ~/.config/my-tools/my_{kind}_{tag}.sh"


def _layer_data(tag: str, *, populated: bool) -> Dict[str, Any]:
    """Build one layer's settings with UNIQUE unrelated sentinels.

    Args:
        tag: Layer tag, making every sentinel value unique per layer.
        populated: When True also plant a pre-existing toolkit-owned
            registration and foreign hooks (the update path). When False the
            layer carries only unrelated sentinels and no toolkit registration.
    """
    data: Dict[str, Any] = {
        "env": {f"MY_{tag.upper()}_TOKEN": f"value-{tag}", "EDITOR": "nvim"},
        "myCustomBlock": {"nested": {"deeper": [f"{tag}-a", f"{tag}-b"], "flag": True}},
        f"topLevel_{tag}": f"survives-{tag}",
        "permissions": {
            "allow": ["Read", f"MyTool({tag})"],
            "ask": [f"Bash(deploy-{tag}:*)"],
            "deny": [f"Bash(danger-{tag}:*)"],
        },
        "hooks": {},
    }
    if populated:
        data["hooks"] = {
            # Consumer's OWN hook on the SAME event the toolkit owns.
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _foreign_command(tag, "notify"),
                            "timeout": 3,
                        }
                    ],
                }
            ],
            # Pre-existing toolkit-owned registration (stale timeout on purpose).
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": _OWNED_PRE_TOOL, "timeout": 999}
                    ],
                }
            ],
            # A wholly foreign event the toolkit never declares.
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _foreign_command(tag, "audit"),
                            "timeout": 4,
                        }
                    ],
                }
            ],
        }
    return data


@dataclass
class ConsumerFixture:
    """A multi-layer consumer settings tree on disk."""

    root: Path
    layers: Dict[str, Path]

    def digests(self) -> Dict[str, Optional[str]]:
        return {name: settings_digest(p) for name, p in self.layers.items()}

    def read(self, layer: str) -> Dict[str, Any]:
        return json.loads(self.layers[layer].read_text(encoding="utf-8"))

    def repo_root(self, layer: str) -> Path:
        target = self.layers[layer]
        return target.parent.parent if target.parent.name == ".claude" else target.parent


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build_fixture(root: Path, *, populated: bool) -> ConsumerFixture:
    """Build CLEAN-0 (populated=False) or POPULATED-3 (populated=True).

    CLEAN-0: no autonomous-dev registration anywhere; empty project/local
    layers; unrelated user sentinels only.
    POPULATED-3: all four layers carry unique unrelated sentinels AND a
    pre-existing toolkit registration.
    """
    project_root = root / "repo"
    layers = {
        "user": root / "home" / ".claude" / "settings.json",
        "project": project_root / ".claude" / "settings.json",
        "local": project_root / ".claude" / "settings.local.json",
        "explicit": root / "explicit" / "settings.json",
    }
    for tag, path in layers.items():
        if populated:
            _write_json(path, _layer_data(tag, populated=True))
        elif tag == "user":
            _write_json(path, _layer_data(tag, populated=False))
        else:
            _write_json(path, {})

    # SENTINEL OF A DIFFERENT SHAPE (remediation): an ALREADY-EXISTING
    # .claude/local with a NON-0700 mode. A side-effectful sentinel lookup
    # chmods this to 0o700 even though it exists, which no file-digest
    # comparison can see. tree_snapshot()/assert_zero_mutation() record and
    # compare directory modes so that side effect fails the refusal rows.
    for layer_path in layers.values():
        if layer_path.parent.name != ".claude":
            continue
        local_dir = layer_path.parent / "local"
        local_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(local_dir, 0o755)

    return ConsumerFixture(root=root, layers=layers)


FIXTURE_BUILDERS: Dict[str, Callable[[Path], ConsumerFixture]] = {
    "CLEAN-0": lambda root: build_fixture(root, populated=False),
    "POPULATED-3": lambda root: build_fixture(root, populated=True),
}


# =============================================================================
# Setup mutators — parameterized sentinel construction
# =============================================================================

def _sentinel_path(fixture: ConsumerFixture, layer: str) -> Path:
    """The EXISTING per-repo pipeline sentinel location for a layer's repo."""
    return fixture.repo_root(layer) / ".claude" / "local" / "implement_pipeline_state.json"


def _plant_sentinel(
    fixture: ConsumerFixture, layer: str, *, body: Optional[bytes], age: float = 0.0
) -> None:
    """Plant a sentinel. ``body=None`` writes 0 bytes (corrupt)."""
    path = _sentinel_path(fixture, layer)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"" if body is None else body)
    if age:
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))


_LIVE_SENTINEL = json.dumps({"session_id": "live-1809", "step": 5}).encode()

sentinel_live = lambda f, la: _plant_sentinel(f, la, body=_LIVE_SENTINEL)  # noqa: E731
sentinel_corrupt = lambda f, la: _plant_sentinel(f, la, body=None)  # noqa: E731
sentinel_stale = lambda f, la: _plant_sentinel(  # noqa: E731
    f, la, body=_LIVE_SENTINEL, age=7200
)


def target_malformed(fixture: ConsumerFixture, layer: str) -> None:
    fixture.layers[layer].write_text("{invalid json!!!", encoding="utf-8")


def target_ambiguous(fixture: ConsumerFixture, layer: str) -> None:
    """hooks.SessionStart is a bare string — ownership is undecidable."""
    data = fixture.read(layer)
    data["hooks"] = {"SessionStart": "bash my-hook.sh"}
    _write_json(fixture.layers[layer], data)


def target_symlinked(fixture: ConsumerFixture, layer: str) -> None:
    """Replace the layer file with a symlink to a sibling real file."""
    target = fixture.layers[layer]
    real = target.parent / f"real_{target.name}"
    real.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(real)


def attacker_git_beside_target(fixture: ConsumerFixture, layer: str) -> None:
    """Forge a .git directory beside the target.

    Correction 5's negative control: a ``.git`` directory is a filesystem
    feature whoever chose the target controls, so it must grant NOTHING. The
    owner has no widening parameter at all, so this must change no verdict.
    """
    (fixture.repo_root(layer) / ".git").mkdir(parents=True, exist_ok=True)


# =============================================================================
# Template mutators
# =============================================================================

def tmpl_duplicate_owned(t: Dict[str, Any]) -> Dict[str, Any]:
    """Same owned hook twice on one event via a DIFFERENT path form."""
    t["hooks"]["PreToolUse"].append(
        {
            "matcher": "*",
            "hooks": [
                {
                    "type": "command",
                    "command": "python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/unified_pre_tool.py",
                    "timeout": 5,
                }
            ],
        }
    )
    return t


def tmpl_legacy_overlap(t: Dict[str, Any]) -> Dict[str, Any]:
    """A retired owned hook alongside the unified hook that supersedes it."""
    t["hooks"]["PreToolUse"][0]["hooks"].append(
        {"type": "command", "command": "python3 ~/.claude/hooks/pre_tool_use.py", "timeout": 5}
    )
    return t


def tmpl_malformed(t: Dict[str, Any]) -> Dict[str, Any]:
    return {"hooks": ["PreToolUse"]}


# =============================================================================
# Case-row table
# =============================================================================

@dataclass(frozen=True)
class CaseRow:
    case_id: str
    fixture: str
    layer: str
    expect: str  # "permit" | "refuse"
    refusal_class: Optional[str] = None
    setup: Optional[Callable[[ConsumerFixture, str], None]] = None
    template_mutator: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    stale_digest: bool = False
    fault: Optional[str] = None
    idempotency: bool = False
    expect_symlink_intact: bool = False


CASE_ROWS: List[CaseRow] = [
    # --- populated-preservation: the #1809 reproducer, one row per layer ---
    *[
        CaseRow(f"populated-preservation-{la}", "POPULATED-3", la, "permit")
        for la in _LAYERS
    ],
    # --- clean-idle-permit + idempotency ---
    CaseRow("clean-idle-permit-user", "CLEAN-0", "user", "permit", idempotency=True),
    CaseRow("clean-idle-permit-project", "CLEAN-0", "project", "permit", idempotency=True),
    CaseRow("populated-update-idempotent", "POPULATED-3", "project", "permit", idempotency=True),
    # --- active-run / sentinel rows ---
    CaseRow("refuse-active-run", "POPULATED-3", "project", "refuse",
            RefusalClass.ACTIVE_PIPELINE, setup=sentinel_live),
    CaseRow("refuse-sentinel-corrupt", "POPULATED-3", "project", "refuse",
            RefusalClass.SENTINEL_AMBIGUOUS, setup=sentinel_corrupt),
    CaseRow("permit-stale-sentinel", "POPULATED-3", "project", "permit",
            setup=sentinel_stale),
    # --- conflict-refusal rows ---
    CaseRow("refuse-malformed-target", "POPULATED-3", "project", "refuse",
            RefusalClass.MALFORMED_TARGET, setup=target_malformed),
    CaseRow("refuse-ambiguous-ownership", "POPULATED-3", "project", "refuse",
            RefusalClass.AMBIGUOUS_OWNERSHIP, setup=target_ambiguous),
    CaseRow("refuse-duplicate-owned-registration", "POPULATED-3", "project", "refuse",
            RefusalClass.DUPLICATE_OWNED_REGISTRATION, template_mutator=tmpl_duplicate_owned),
    CaseRow("refuse-legacy-owned-overlap", "POPULATED-3", "project", "refuse",
            RefusalClass.LEGACY_OWNED_OVERLAP, template_mutator=tmpl_legacy_overlap),
    CaseRow("refuse-malformed-template", "POPULATED-3", "project", "refuse",
            RefusalClass.MALFORMED_TEMPLATE, template_mutator=tmpl_malformed),
    # --- digest / interleaving rows ---
    CaseRow("refuse-digest-race-stale-expected", "POPULATED-3", "project", "refuse",
            RefusalClass.DIGEST_RACE, stale_digest=True),
    CaseRow("refuse-interleave-before-serialize", "POPULATED-3", "project", "refuse",
            RefusalClass.DIGEST_RACE, fault="interleave_early"),
    CaseRow("refuse-interleave-late-inside-lock", "POPULATED-3", "project", "refuse",
            RefusalClass.DIGEST_RACE, fault="interleave_late"),
    # --- interrupted write ---
    CaseRow("interrupted-write-no-partial", "POPULATED-3", "project", "refuse",
            RefusalClass.WRITE_FAILED, fault="os_replace"),
    # --- path policy rows ---
    CaseRow("refuse-symlinked-target-link-intact", "POPULATED-3", "local", "refuse",
            RefusalClass.TARGET_PATH_REJECTED, setup=target_symlinked,
            expect_symlink_intact=True),
    CaseRow("refuse-forged-git-grants-nothing", "POPULATED-3", "project", "refuse",
            RefusalClass.ACTIVE_PIPELINE,
            setup=lambda f, la: (attacker_git_beside_target(f, la), sentinel_live(f, la))[0]),
]


# =============================================================================
# Assertions
# =============================================================================

def _all_commands(data: Dict[str, Any], event: Optional[str] = None) -> List[str]:
    out: List[str] = []
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        return out
    for name, groups in hooks.items():
        if event is not None and name != event:
            continue
        if not isinstance(groups, list):
            continue
        for group in groups:
            if isinstance(group, dict):
                for entry in group.get("hooks", []):
                    if isinstance(entry, dict):
                        out.append(entry.get("command", ""))
    return out


def assert_unrelated_survives(before: Dict[str, Any], after: Dict[str, Any], tag: str) -> None:
    """Every unrelated sentinel in ``before`` survives in ``after``."""
    for key in ("env", "myCustomBlock", f"topLevel_{tag}"):
        if key in before:
            assert after.get(key) == before[key], (
                f"unrelated key {key!r} mutated: {before.get(key)!r} -> {after.get(key)!r}"
            )

    bp, ap = before.get("permissions", {}), after.get("permissions", {})
    for plist in ("allow", "ask"):
        if plist in bp:
            assert ap.get(plist) == bp[plist], (
                f"permissions.{plist} must be untouched: {bp.get(plist)!r} -> {ap.get(plist)!r}"
            )
    for entry in bp.get("deny", []):
        assert entry in ap.get("deny", []), (
            f"custom deny entry {entry!r} deleted — this IS the #1809 defect"
        )

    after_cmds = _all_commands(after)
    for cmd in _all_commands(before):
        if "my-tools" in cmd:  # consumer-owned scripts
            assert cmd in after_cmds, (
                f"foreign hook destroyed: {cmd!r} (surviving: {after_cmds!r})"
            )


def assert_owned_projection(after: Dict[str, Any], template: Dict[str, Any]) -> None:
    """Owned entries present exactly once per lifecycle event (registration level)."""
    for event, groups in template.get("hooks", {}).items():
        cmds = _all_commands(after, event)
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command")
                assert cmd in cmds, f"owned hook missing from {event!r}: {cmd!r} (got {cmds!r})"
                assert cmds.count(cmd) == 1, (
                    f"owned hook registered {cmds.count(cmd)}x on {event!r} "
                    f"(would double-fire): {cmd!r}"
                )


def assert_no_partial_artifacts(target: Path) -> None:
    leftovers = [p.name for p in target.parent.glob(".settings-*")]
    assert not leftovers, f"transaction left partial artifacts: {leftovers}"


def tree_snapshot(root: Path) -> Dict[str, Any]:
    """Capture file bytes AND directory existence AND directory MODES.

    A file-only digest is not sufficient to prove zero mutation. MEASURED during
    this remediation: ``pipeline_state.get_legacy_sentinel_path`` (the resolver a
    naive admission check would call) both CREATES ``<repo>/.claude/local`` and
    ``chmod``s an already-existing one to ``0o700``. A files-only comparison sees
    neither, so every "zero mutation" claim built on one was unfalsifiable.

    Args:
        root: Directory to snapshot recursively.

    Returns:
        ``{"files": {rel: sha256}, "dirs": {rel: st_mode}}``.
    """
    files: Dict[str, str] = {}
    dirs: Dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        rel_dir = str(d.relative_to(root)) or "."
        dirs[rel_dir] = os.stat(d).st_mode
        for name in filenames:
            p = d / name
            try:
                files[str(p.relative_to(root))] = hashlib.sha256(
                    p.read_bytes()
                ).hexdigest()
            except OSError:
                files[str(p.relative_to(root))] = "<unreadable>"
    return {"files": files, "dirs": dirs}


#: sha256 of b"" — the digest a 0-byte sidecar lockfile must have.
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def assert_zero_mutation(
    before: Dict[str, Any],
    after: Dict[str, Any],
    *,
    permitted_lockfiles: Optional[List[str]] = None,
) -> None:
    """Assert file bytes, directory set, and directory modes are all unchanged.

    ``permitted_lockfiles`` names the ONE artifact a refusal may legitimately
    create: the transaction sidecar lockfile. FOUND BY THIS VERY ASSERTION when
    it was upgraded from file-digests-only — ``_settings_transaction_lock`` opens
    ``.<name>.lock`` ``"a+"`` to take the ``flock``, and that happens BEFORE the
    refusal decision inside the locked section. You cannot ``flock`` a file you
    decline to create, and the pattern matches the existing
    ``pipeline_completion_state._locked_rmw`` sidecar.

    So the precise claim is: a refusal mutates NO consumer configuration — no
    settings bytes, no directory created or removed, no directory mode changed —
    and creates at most one EMPTY sidecar lockfile, which is asserted to be
    0 bytes. Any other new or changed file fails the assertion. The exclusion is
    explicit and narrow rather than silent.
    """
    allowed = set(permitted_lockfiles or ())
    before_files = dict(before["files"])
    after_files = dict(after["files"])

    for rel in allowed:
        if rel in after_files and rel not in before_files:
            assert after_files[rel] == _EMPTY_SHA256, (
                f"permitted lockfile {rel} is not empty — it carries content "
                "and is therefore not a bare lock artifact"
            )
            del after_files[rel]

    assert after_files == before_files, (
        "FILE bytes changed during a refusal: "
        f"{sorted(set(after_files.items()) ^ set(before_files.items()))}"
    )
    assert set(after["dirs"]) == set(before["dirs"]), (
        "DIRECTORY set changed during a refusal (created/removed): "
        f"added={sorted(set(after['dirs']) - set(before['dirs']))} "
        f"removed={sorted(set(before['dirs']) - set(after['dirs']))}"
    )
    mode_deltas = {
        k: (oct(before["dirs"][k]), oct(after["dirs"][k]))
        for k in before["dirs"]
        if before["dirs"][k] != after["dirs"][k]
    }
    assert not mode_deltas, (
        f"DIRECTORY MODES changed during a refusal: {mode_deltas}"
    )


# =============================================================================
# The single parameterized case runner
# =============================================================================

@pytest.mark.parametrize("row", CASE_ROWS, ids=lambda r: r.case_id)
def test_ownership_case_row(row: CaseRow, tmp_path: Path, monkeypatch) -> None:
    """Drive one case row of the ownership-aware settings owner."""
    fixture = FIXTURE_BUILDERS[row.fixture](tmp_path)
    target = fixture.layers[row.layer]

    template = _owned_template()
    if row.template_mutator is not None:
        template = row.template_mutator(template)
    if row.setup is not None:
        row.setup(fixture, row.layer)

    digests_before = fixture.digests()
    raw_before = target.read_bytes()
    was_symlink = target.is_symlink()
    # Whole-root snapshot: file bytes + directory set + directory MODES.
    snapshot_before = tree_snapshot(fixture.root)

    expected_digest = hashlib.sha256(b"{}").hexdigest() if row.stale_digest else None
    raced_marker = {"hooks": {}, "racedBy": "other-process"}

    if row.fault == "os_replace":
        def _boom(src, dst, *a, **kw):  # noqa: ANN001
            raise OSError(5, "injected interruption mid-transaction")

        monkeypatch.setattr(settings_merger.os, "replace", _boom)
    elif row.fault == "interleave_early":
        # An external writer lands BEFORE serialization — the wide window.
        real = settings_merger._serialize_settings

        def _racing(data):  # noqa: ANN001
            target.write_text(json.dumps(raced_marker) + "\n", encoding="utf-8")
            return real(data)

        monkeypatch.setattr(settings_merger, "_serialize_settings", _racing)
    elif row.fault == "interleave_late":
        # An external writer lands as LATE as the code can still detect: inside
        # the lock, after the temp file is written, immediately before the
        # pre-rename digest re-check. os.chmod is the last call before it.
        real_chmod = settings_merger.os.chmod

        def _racing_chmod(path, mode, *a, **kw):  # noqa: ANN001
            result = real_chmod(path, mode, *a, **kw)
            target.write_text(json.dumps(raced_marker) + "\n", encoding="utf-8")
            return result

        monkeypatch.setattr(settings_merger.os, "chmod", _racing_chmod)

    result = apply_owned_settings(
        target,
        template,
        manifest_path=_MANIFEST_PATH,
        owned_deny=_OWNED_DENY,
        expected_digest=expected_digest,
    )

    if row.expect == "refuse":
        assert result.success is False, f"refusal reported as success: {result!r}"
        assert result.refused is True
        assert result.refusal_class == row.refusal_class, (
            f"expected {row.refusal_class!r}, got {result.refusal_class!r} "
            f"(reason: {result.reason!r})"
        )
        assert result.reason, "refusal MUST carry a durable, observable reason"

        if row.fault in ("interleave_early", "interleave_late"):
            raced = json.loads(target.read_text(encoding="utf-8"))
            assert raced.get("racedBy") == "other-process", (
                "owner blind-wrote over a concurrent modification"
            )
        else:
            assert target.read_bytes() == raw_before, (
                "refusal mutated the target (must be ZERO mutation)"
            )
            assert fixture.digests() == digests_before, (
                f"refusal changed digests: {digests_before} -> {fixture.digests()}"
            )
            # Upgraded: file bytes AND directory set AND directory modes.
            # Catches the sentinel-lookup mkdir/chmod side-effect class that a
            # file-only digest is structurally blind to. The transaction's own
            # 0-byte sidecar lockfile is the single explicitly permitted artifact.
            lock_rel = str(
                (target.parent / f".{target.name}.lock").relative_to(fixture.root)
            )
            assert_zero_mutation(
                snapshot_before,
                tree_snapshot(fixture.root),
                permitted_lockfiles=[lock_rel],
            )

        if row.expect_symlink_intact:
            assert was_symlink, "fixture did not actually create a symlink"
            assert target.is_symlink(), "refusal destroyed the consumer's symlink"

        assert_no_partial_artifacts(target)
        return

    # ---- permit arm ----
    assert result.success is True, f"expected permit, got refusal: {result!r}"
    assert result.refused is False
    assert not result.refusal_class

    before = json.loads(raw_before.decode("utf-8")) if raw_before.strip() else {}
    after = fixture.read(row.layer)

    assert_unrelated_survives(before, after, row.layer)
    assert_owned_projection(after, template)

    for owned in _OWNED_DENY:
        assert owned in after.get("permissions", {}).get("deny", []), (
            f"owned deny entry missing after write: {owned!r}"
        )

    # Only the targeted layer changed.
    digests_after = fixture.digests()
    for name, digest in digests_before.items():
        if name != row.layer:
            assert digests_after[name] == digest, (
                f"layer {name!r} mutated while targeting {row.layer!r}"
            )

    if row.idempotency:
        first = target.read_bytes()
        second = apply_owned_settings(
            target, template, manifest_path=_MANIFEST_PATH, owned_deny=_OWNED_DENY
        )
        assert second.success is True, f"second run refused: {second!r}"
        assert second.changed is False, "second run must be a no-op"
        assert target.read_bytes() == first, "repeat write is not byte-stable"
        assert_owned_projection(json.loads(target.read_text(encoding="utf-8")), template)


# =============================================================================
# Ownership derivation and path policy
# =============================================================================

def test_ownership_is_derived_from_manifest_not_position() -> None:
    """Owned basenames come from manifest + template, never from position."""
    owned = resolve_owned_hook_basenames(_owned_template(), manifest_path=_MANIFEST_PATH)
    # PERMITTING arm: real toolkit hooks are owned.
    assert "unified_pre_tool.py" in owned
    assert "SessionStart-batch-recovery.sh" in owned
    assert "pre_tool_use.py" in owned  # retired, still owned so it can be removed
    # REFUSING arm: consumer scripts are NOT owned.
    assert "my_notify_project.sh" not in owned
    assert "my_audit_user.sh" not in owned


def test_out_of_profile_targets_fail_closed(tmp_path: Path) -> None:
    """Cross-repo / out-of-profile targets are REFUSED and never created.

    Covers corrections 4 and 5 together: there is no widening parameter, so a
    caller cannot self-approve, and a forged ``.git`` beside the target grants
    nothing. The path is never created.
    """
    outside = Path.home() / ".cache" / "autonomous-dev-1809-must-not-exist" / ".claude"
    target = outside / "settings.json"
    assert not target.exists(), "precondition: probe path must not pre-exist"

    result = apply_owned_settings(
        target, _owned_template(), manifest_path=_MANIFEST_PATH, owned_deny=_OWNED_DENY
    )

    assert result.success is False
    assert result.refusal_class == RefusalClass.TARGET_PATH_REJECTED
    assert not target.exists(), "refused target was created anyway"
    assert not outside.exists(), "refused target's parent was created anyway"

    # POSITIVE CONTROL: the same call shape inside the profile PERMITS, so the
    # refusal above is about the path and not about the call being broken.
    inside = tmp_path / "repo" / ".claude" / "settings.json"
    _write_json(inside, {})
    ok = apply_owned_settings(
        inside, _owned_template(), manifest_path=_MANIFEST_PATH, owned_deny=_OWNED_DENY
    )
    assert ok.success is True, f"positive control failed: {ok!r}"


def test_traversal_target_refused(tmp_path: Path) -> None:
    """A '..' component is refused before any read or write."""
    target = tmp_path / "repo" / ".claude" / ".." / ".." / "escaped.json"
    result = apply_owned_settings(target, _owned_template(), owned_deny=_OWNED_DENY)
    assert result.success is False
    assert result.refusal_class == RefusalClass.TARGET_PATH_REJECTED
    assert not (tmp_path / "escaped.json").exists()


def test_dry_run_reports_pending_change_without_writing(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, populated=True)
    target = fixture.layers["project"]
    before = target.read_bytes()

    result = apply_owned_settings(
        target, _owned_template(), manifest_path=_MANIFEST_PATH,
        owned_deny=_OWNED_DENY, dry_run=True,
    )

    assert result.success is True
    assert result.changed is True, "dry-run must report that a change is pending"
    assert target.read_bytes() == before, "dry-run wrote to the target"


def test_missing_target_created_from_owned_projection(tmp_path: Path) -> None:
    target = tmp_path / "repo" / ".claude" / "settings.json"
    result = apply_owned_settings(
        target, _owned_template(), manifest_path=_MANIFEST_PATH, owned_deny=_OWNED_DENY
    )
    assert result.success is True
    data = json.loads(target.read_text(encoding="utf-8"))
    assert_owned_projection(data, _owned_template())
    assert data["permissions"]["deny"] == _OWNED_DENY


def test_transaction_lock_is_held_and_refuses_when_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    """Both arms of the transaction lock.

    PERMITTING: a normal write acquires the lock and succeeds.
    REFUSING: when the lock cannot be taken the owner refuses rather than
    writing unserialized (the opposite of the fail-open policy in
    ``pipeline_completion_state._locked_rmw``, which is why that helper is not
    reused here).
    """
    fixture = build_fixture(tmp_path, populated=True)
    target = fixture.layers["project"]

    ok = apply_owned_settings(
        target, _owned_template(), manifest_path=_MANIFEST_PATH, owned_deny=_OWNED_DENY
    )
    assert ok.success is True, f"permitting arm broken: {ok!r}"

    before = target.read_bytes()

    def _no_lock(fileno, operation):  # noqa: ANN001
        raise OSError(35, "injected lock unavailable")

    monkeypatch.setattr(settings_merger.fcntl, "flock", _no_lock)
    refused = apply_owned_settings(
        fixture.layers["local"], _owned_template(),
        manifest_path=_MANIFEST_PATH, owned_deny=_OWNED_DENY,
    )
    assert refused.success is False
    assert refused.refusal_class == RefusalClass.LOCK_UNAVAILABLE
    assert target.read_bytes() == before


# =============================================================================
# ROUTE tests — behavioural, through the ACTUAL writer paths
# =============================================================================

def test_route_sync_settings_hooks_cli_subprocess(tmp_path: Path) -> None:
    """ROUTE: the CLI entrypoint deploy-all.sh invokes, driven as a subprocess.

    Not a source grep — this runs ``python3 sync_settings_hooks.py --repo <dir>``
    exactly as ``scripts/deploy-all.sh`` does, then reads the resulting file.
    """
    repo = tmp_path / "consumer"
    target = repo / ".claude" / "settings.json"
    _write_json(target, _layer_data("project", populated=True))
    before = json.loads(target.read_text(encoding="utf-8"))

    proc = subprocess.run(
        [
            sys.executable,
            str(_PLUGIN_ROOT / "scripts" / "sync_settings_hooks.py"),
            "--repo",
            str(repo),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, f"CLI failed: rc={proc.returncode} {proc.stdout}{proc.stderr}"
    payload = json.loads(proc.stdout)
    assert payload["success"] is True, payload
    assert payload["refusal_class"] == "", payload

    after = json.loads(target.read_text(encoding="utf-8"))

    # (a) unrelated consumer bytes survive through the REAL entrypoint
    assert_unrelated_survives(before, after, "project")

    # (b) registration-level uniqueness of each owned hook via the real caller
    template = json.loads(
        (_PLUGIN_ROOT / "templates" / "settings.default.json").read_text(encoding="utf-8")
    )
    assert_owned_projection(after, template)
    assert payload["foreign_hooks_preserved"] >= 2, (
        f"expected the consumer's own hooks to be counted as preserved: {payload}"
    )


def test_route_sync_settings_hooks_cli_refuses_nonzero(tmp_path: Path) -> None:
    """ROUTE negative: a live run makes the CLI exit non-zero, not warn-and-pass."""
    repo = tmp_path / "consumer"
    target = repo / ".claude" / "settings.json"
    _write_json(target, _layer_data("project", populated=True))
    sentinel = repo / ".claude" / "local" / "implement_pipeline_state.json"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_bytes(_LIVE_SENTINEL)
    before = target.read_bytes()

    proc = subprocess.run(
        [
            sys.executable,
            str(_PLUGIN_ROOT / "scripts" / "sync_settings_hooks.py"),
            "--repo",
            str(repo),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 1, f"refusal must exit non-zero, got {proc.returncode}"
    payload = json.loads(proc.stdout)
    assert payload["success"] is False
    assert payload["refusal_class"] == RefusalClass.ACTIVE_PIPELINE
    assert "Refused" in payload["message"]
    assert target.read_bytes() == before, "refusal mutated the target"


def test_route_modes_preserves_and_raises_on_failure(tmp_path: Path) -> None:
    """ROUTE: sync_dispatcher/modes.py writer preserves, and fails loudly."""
    from sync_dispatcher import modes  # noqa: PLC0415

    class _FakeDispatcher:
        def __init__(self, path: Path) -> None:
            self.project_path = path

    repo = tmp_path / "consumer"
    target = repo / ".claude" / "settings.json"
    _write_json(target, _layer_data("project", populated=True))
    before = json.loads(target.read_text(encoding="utf-8"))

    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(_owned_template()), encoding="utf-8")

    written = modes._apply_owned_settings_hooks(_FakeDispatcher(repo), template_path)

    after = json.loads(target.read_text(encoding="utf-8"))
    assert written >= 1, "no owned hooks reported written"
    assert_unrelated_survives(before, after, "project")
    assert_owned_projection(after, _owned_template())

    # REFUSING arm: an unreadable template must RAISE, not return 0-as-success.
    bad_template = tmp_path / "bad.json"
    bad_template.write_text("{not json", encoding="utf-8")
    with pytest.raises(modes.SettingsWriteError):
        modes._apply_owned_settings_hooks(_FakeDispatcher(repo), bad_template)


def test_readonly_sentinel_projection_conforms_to_canonical_owner(tmp_path: Path) -> None:
    """DRIFT GUARD — RELEASE-BLOCKING. Do not delete as "flaky legacy".

    ``settings_merger._resolve_sentinel_readonly`` is a read-only PROJECTION of
    ``pipeline_state.get_legacy_sentinel_path``, which owns the sentinel layout.
    The projection imports the canonical file NAME but must restate the
    ``.claude/local`` directory parts, because the owner inlines them and exports
    no constant.

    If the sentinel is ever relocated in the canonical helper and this projection
    is not updated, ADMISSION WOULD CHECK THE WRONG PATH, find no sentinel, and
    **PERMIT during a live run** — the worst failure direction for this gate.
    This equality assertion is the only thing binding the two.

    The canonical helper MUTATES (mkdir + chmod 0o700). It is therefore invoked
    ONLY inside this disposable fixture, never in a zero-mutation refusal row's
    target repo, and its side effects are asserted here explicitly so the test
    documents them instead of hiding them.
    """
    from pipeline_state import get_legacy_sentinel_path  # noqa: PLC0415

    repo = tmp_path / "disposable-repo"
    repo.mkdir()
    local_dir = repo / ".claude" / "local"
    assert not local_dir.exists(), "precondition: .claude/local must not pre-exist"

    projected = settings_merger._resolve_sentinel_readonly(repo)

    # The projection itself must have created NOTHING.
    assert not local_dir.exists(), (
        "the read-only projection created a directory — it is not side-effect-free"
    )

    canonical = get_legacy_sentinel_path(repo)

    # THE BINDING: identical paths.
    assert projected == canonical, (
        "sentinel layout drift: admission would check the wrong path and PERMIT "
        f"during a live run. projection={projected} canonical={canonical}"
    )

    # Document (not hide) the canonical helper's side effects, in this
    # throwaway fixture only.
    assert local_dir.exists(), (
        "canonical helper no longer creates .claude/local — if it became "
        "side-effect-free, _resolve_sentinel_readonly may be deletable"
    )
    assert (local_dir.stat().st_mode & 0o777) == 0o700, (
        "canonical helper no longer chmods .claude/local to 0o700 — re-check "
        "whether the projection is still required"
    )


def test_route_modes_fails_closed_without_admission_owner(tmp_path: Path, monkeypatch) -> None:
    """GAP 1: a missing admission owner must REFUSE, never silently proceed.

    ``modes.py`` sets ``check_mutation_admission = None`` when the import fails.
    If the route treated that as "no check needed" it would copy files with no
    liveness check at all while callers still believed the gate ran — a guard
    that disappears when its instrument breaks is worse than no guard.

    Simulates the broken-instrument condition by forcing the module attribute to
    ``None`` (exactly what the ImportError fallback assigns) and asserts
    non-success plus ZERO mutation, including directory set and modes.
    """
    from sync_dispatcher import modes  # noqa: PLC0415
    from sync_dispatcher.dispatcher import SyncDispatcher  # noqa: PLC0415

    fake_home, project, claude_dir = _build_modes_marketplace_fixture(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setattr(modes, "check_mutation_admission", None)

    before = tree_snapshot(claude_dir)
    result = modes.dispatch_marketplace(SyncDispatcher(project_root=str(project)))
    after = tree_snapshot(claude_dir)

    assert result.success is False, (
        f"missing admission owner must fail CLOSED, not proceed: {result!r}"
    )
    assert result.details.get("admission_refused") == "admission_owner_unavailable"
    assert result.error and "not importable" in result.error
    assert_zero_mutation(before, after)
    assert not (claude_dir / "commands" / "injected.md").exists(), (
        "files were copied despite the admission owner being unavailable"
    )


def test_route_dispatcher_admission_precedes_first_file_mutation(tmp_path: Path) -> None:
    """ROUTE: a live run refuses BEFORE the first file copy, not at the settings write.

    Correction 8's negative. ``sync_marketplace`` copies commands/hooks/agents
    well before it reaches the settings writer, so a refusal raised inside
    ``apply_owned_settings`` would arrive after the installed tree was already
    modified. Asserted over a digest of the WHOLE ``.claude`` tree, not just
    settings.json.
    """
    from sync_dispatcher.dispatcher import SyncDispatcher  # noqa: PLC0415

    project = tmp_path / "project"
    claude = project / ".claude"
    claude.mkdir(parents=True)
    _write_json(claude / "settings.json", _layer_data("project", populated=True))
    (claude / "commands").mkdir()
    (claude / "commands" / "preexisting.md").write_text("consumer command\n")
    (claude / "agents").mkdir()
    (claude / "agents" / "preexisting.md").write_text("consumer agent\n")

    # Plugin source carrying files the sync WOULD copy.
    plugin = tmp_path / "plugin"
    for sub in ("commands", "hooks", "agents", "config"):
        (plugin / sub).mkdir(parents=True)
    (plugin / "commands" / "injected.md").write_text("from plugin\n")
    (plugin / "hooks" / "injected.py").write_text("# from plugin\n")
    (plugin / "agents" / "injected.md").write_text("from plugin\n")
    (plugin / "config" / "global_settings_template.json").write_text(
        json.dumps(_owned_template()), encoding="utf-8"
    )
    (plugin / "plugin.json").write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")
    plugins_file = tmp_path / "installed_plugins.json"
    plugins_file.write_text(
        json.dumps({"autonomous-dev": {"path": str(plugin), "version": "9.9.9"}}),
        encoding="utf-8",
    )

    # A live run for the TARGET repo.
    sentinel = claude / "local" / "implement_pipeline_state.json"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_bytes(_LIVE_SENTINEL)

    os.chmod(sentinel.parent, 0o755)  # non-0700: a chmod side effect must fail
    before = tree_snapshot(claude)
    dispatcher = SyncDispatcher(project_root=str(project))
    result = dispatcher.sync_marketplace(str(plugins_file))
    after = tree_snapshot(claude)

    assert result.success is False, f"live run must refuse the whole sync: {result!r}"
    assert result.details.get("admission_refused") == RefusalClass.ACTIVE_PIPELINE
    assert result.error, "refusal must carry a durable reason"
    assert_zero_mutation(before, after)
    assert not (claude / "commands" / "injected.md").exists(), "file copied before refusal"
    assert not (claude / "agents" / "injected.md").exists(), "file copied before refusal"

    # POSITIVE CONTROL: with the sentinel removed the same call PERMITS and does
    # copy files — so the refusal above is the admission check, not a broken call.
    sentinel.unlink()
    permitted = dispatcher.sync_marketplace(str(plugins_file))
    assert permitted.details.get("admission_refused") is None, permitted.details
    assert (claude / "commands" / "injected.md").exists(), (
        "permitting arm broken: nothing was copied even with no live run"
    )


def _build_modes_marketplace_fixture(tmp_path: Path) -> tuple:
    """Build a fake ~/.claude marketplace tree + a consumer project.

    Returns:
        ``(fake_home, project, claude_dir)``. ``dispatch_marketplace`` resolves
        its source from ``Path.home()``, so the caller monkeypatches that.
    """
    fake_home = tmp_path / "home"
    marketplace = (
        fake_home / ".claude" / "plugins" / "marketplaces" / "autonomous-dev"
        / "plugins" / "autonomous-dev"
    )
    (marketplace / "commands").mkdir(parents=True)
    (marketplace / "hooks").mkdir(parents=True)
    (marketplace / "templates").mkdir(parents=True)
    (marketplace / "commands" / "injected.md").write_text("from marketplace\n")
    (marketplace / "hooks" / "injected.py").write_text("# from marketplace\n")
    (marketplace / "templates" / "settings.local.json").write_text(
        json.dumps(_owned_template()), encoding="utf-8"
    )

    project = tmp_path / "project"
    claude_dir = project / ".claude"
    claude_dir.mkdir(parents=True)
    _write_json(claude_dir / "settings.json", _layer_data("project", populated=True))
    (claude_dir / "commands").mkdir()
    (claude_dir / "commands" / "preexisting.md").write_text("consumer command\n")
    # Non-0700 .claude/local already present: a side-effectful sentinel lookup
    # would chmod it to 0o700, which only a mode-aware snapshot detects.
    (claude_dir / "local").mkdir()
    os.chmod(claude_dir / "local", 0o755)
    return fake_home, project, claude_dir


@pytest.mark.parametrize("live_run", [True, False], ids=["refuse-live", "permit-idle"])
def test_route_modes_dispatch_marketplace_admission_arms(
    live_run: bool, tmp_path: Path, monkeypatch
) -> None:
    """ROUTE: `/sync --marketplace` admits/refuses BEFORE its first file copy.

    Both control arms of the SAME entrypoint (remediation FINDING-2):

    * ``refuse-live``  — a live sentinel refuses before any copy; the whole
      ``.claude`` tree's FILE digests are unchanged and neither injected file
      exists.
    * ``permit-idle``  — no sentinel, the same call proceeds and the files land.

    The permitting arm is what makes the refusing arm meaningful: without it a
    guard that can never permit would look identical.

    Precise guarantee: FILE-level. Resolving the sentinel through the sanctioned
    ``get_legacy_sentinel_path()`` creates an empty ``.claude/local/``
    directory, so this is not an inode-level no-op claim.
    """
    from sync_dispatcher import modes  # noqa: PLC0415
    from sync_dispatcher.dispatcher import SyncDispatcher  # noqa: PLC0415

    fake_home, project, claude_dir = _build_modes_marketplace_fixture(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    if live_run:
        sentinel = claude_dir / "local" / "implement_pipeline_state.json"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(_LIVE_SENTINEL)

    before = tree_snapshot(claude_dir)
    result = modes.dispatch_marketplace(SyncDispatcher(project_root=str(project)))
    after = tree_snapshot(claude_dir)

    if live_run:
        assert result.success is False, f"live run must refuse: {result!r}"
        assert result.details.get("admission_refused") == RefusalClass.ACTIVE_PIPELINE
        assert result.error, "refusal must carry a durable reason"
        assert_zero_mutation(before, after)
        assert not (claude_dir / "commands" / "injected.md").exists()
        assert not (claude_dir / "hooks" / "injected.py").exists()
    else:
        assert result.details.get("admission_refused") is None, result.details
        assert (claude_dir / "commands" / "injected.md").exists(), (
            "permitting arm broken: nothing copied with no live run"
        )
        assert (claude_dir / "commands" / "preexisting.md").exists(), (
            "consumer's own command file was deleted"
        )
        # The consumer's own settings survive through this route too.
        assert_unrelated_survives(
            _layer_data("project", populated=True),
            json.loads((claude_dir / "settings.json").read_text(encoding="utf-8")),
            "project",
        )


def test_route_dispatcher_preserves_and_aggregates(tmp_path: Path) -> None:
    """ROUTE: dispatcher.sync_marketplace preserves consumer config.

    Also the masking negative for correction 6: the FIRST layer fails
    (settings.local.json template absent) while the SECOND succeeds. The overall
    result MUST be non-success and MUST name the failed layer with a reason.
    """
    from sync_dispatcher.dispatcher import SyncDispatcher  # noqa: PLC0415

    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    target = project / ".claude" / "settings.json"
    _write_json(target, _layer_data("project", populated=True))
    before = json.loads(target.read_text(encoding="utf-8"))

    # Plugin source with the project-layer template present but the
    # local-layer template ABSENT -> first layer fails, second succeeds.
    plugin = tmp_path / "plugin"
    (plugin / "config").mkdir(parents=True)
    (plugin / "config" / "global_settings_template.json").write_text(
        json.dumps(_owned_template()), encoding="utf-8"
    )
    (plugin / "plugin.json").write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")

    # sync_marketplace takes an installed_plugins.json manifest, not a directory.
    plugins_file = tmp_path / "installed_plugins.json"
    plugins_file.write_text(
        json.dumps({"autonomous-dev": {"path": str(plugin), "version": "9.9.9"}}),
        encoding="utf-8",
    )

    dispatcher = SyncDispatcher(project_root=str(project))
    result = dispatcher.sync_marketplace(str(plugins_file))

    layers = result.details.get("settings_layers", {})
    assert "local" in layers, f"per-layer detail missing: {result.details}"
    assert layers["local"]["status"] == "template_missing", layers["local"]
    assert layers["local"]["reason"], "failed layer must carry a reason"
    assert layers["project"]["status"] == "applied", layers["project"]
    assert result.details.get("settings_failed_layers") == ["local"], result.details
    assert result.success is False, (
        "a failed settings layer was masked by a later success (correction 6)"
    )

    # Preservation still holds for the layer that DID apply.
    after = json.loads(target.read_text(encoding="utf-8"))
    assert_unrelated_survives(before, after, "project")
    assert_owned_projection(after, _owned_template())

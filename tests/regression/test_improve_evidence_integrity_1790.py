"""Evidence-integrity regression proof for /improve (Issue #1790).

Layered per control-tool v12 §6:

1. **Canary** — the REAL ``/improve`` STEP 5 block, extracted from
   ``commands/improve.md`` and executed in a temporary git repository with
   every ``gh`` invocation intercepted by a recording stub. Five arms: the
   route permitting, the route refusing (two different shapes), the route
   absent (``--dry-run``), and a deliberately broken instrument.
2. **Contract matrix** — one parameterised row per boundary translation, each
   row naming the distinct failure class it detects.
3. **Unit** — only for the content-identity hash, whose failure is not
   observable through the first two layers.

ISOLATION (#1779): every path is under ``tmp_path`` or a documented env seam
(``AUTONOMOUS_DEV_FINDINGS_DIR``, ``GH_ISSUE_CMD_CONTEXT_PATH``); the
subprocess environment is built by
``tests/helpers/state_isolation.hook_subprocess_env``. Nothing here reads,
writes or unlinks live state: the hook-contract marker is redirected at the
owner seam (``lib/gh_issue_context.py``, #1609) rather than snapshotted and
restored, because a snapshot cannot protect a concurrent reader. NO network,
no real ``gh``: the stub is the only executable named ``gh`` on the child's
PATH.

CARRIER SCOPE — the canary runs against a DETACHED, MANIFEST-ONLY copy of
``lib/`` placed at the temp repo's ``.claude/lib``, never the source tree, so
nothing here can pass by reaching back into the repository under test, nor by
importing a module a consumer install would never receive.

The INSTALLED-CONSUMER carrier is MEASURED, not asserted: the canary's ``lib/``
is materialised through the REAL installer mapping
(``scripts/install.py::PluginInstaller.get_all_files_from_manifest`` applied to
``config/install_manifest.json``), reusing the route that
``tests/regression/test_issue_1747_manifest_completeness.py`` already owns. A
module STEP 5 imports but the manifest does not ship therefore fails here
rather than in a consumer repo.

GitHub Issue: #1790
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import replace
from pathlib import Path

import pytest

# tests/regression/<this file> -> regression -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "plugins" / "autonomous-dev"
LIB_DIR = PLUGIN_DIR / "lib"
IMPROVE_CMD = PLUGIN_DIR / "commands" / "improve.md"
# The installer's own manifest path and entry point (scripts/install.py:83).
MANIFEST_PATH = PLUGIN_DIR / "config" / "install_manifest.json"
INSTALL_PY = PLUGIN_DIR / "scripts" / "install.py"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from helpers.state_isolation import hook_subprocess_env  # noqa: E402

import path_utils  # noqa: E402
from cia_finding_store import (  # noqa: E402
    ALLOWED_SEVERITIES,
    INVALID_SEVERITY_LABEL,
    SEVERITY_QUARANTINE_FIELD,
    append_finding,
    finding_identity,
    retract_finding,
)
from cia_promotion_filter import should_promote  # noqa: E402
from gh_issue_context import (  # noqa: E402
    CONTEXT_PATH_ENV_VAR,
    DEFAULT_CONTEXT_PATH,
)
from issue_triage_analyzer import (  # noqa: E402
    SEVERITY_LABEL_VOCABULARY,
    extract_root_cause_tag,
    format_root_cause_title,
    parse_root_cause_title,
)
from macro_promotion import (  # noqa: E402
    build_digest,
    classify_route,
    decide_promotions,
    digest_from_record,
    digest_to_record,
    format_digest,
    format_dry_run,
    held,
    planned_title,
    reclassify_before_write,
)
from path_utils import (  # noqa: E402
    FINDINGS_DIR_ENV,
    LogDirResolutionError,
    git_common_repo_root,
    resolve_findings_dir,
)
from runtime_data_aggregator import (  # noqa: E402
    CIA_HIGH_SEVERITY_LABELS,
    CIA_SEVERITY_ORDER,
    MAX_LINES,
    TRUSTWORTHY_HEALTH_STATUSES,
    AggregatedSignal,
    SourceHealth,
    aggregate,
    cia_finding_identity,
    collect_cia_findings,
    load_latest_persisted_digest,
)

# The canonical duplicate corpus: REAL open GitHub issues fetched 2026-09-13,
# all labelled auto-improvement,continuous-improvement. HOOK-REGRESSION
# contains a hyphen ITSELF, so "split on the last hyphen" is wrong.
CORPUS = [
    (
        1712,
        "error",
        "GAMING",
        "Plan-critic override: 1/3 minimalism cuts accepted, 2/3 rejected -- one "
        "rejection cites precedent that answers a different question than the "
        "one raised",
    ),
    (
        1714,
        "error",
        "HOOK-REGRESSION",
        "install_manifest test fails after #1296 sentinel requirement change",
    ),
    (
        1715,
        "error",
        "INCOMPLETE",
        "Cluster mode (BATCH_NO_WORKTREE=1) sub-issue agent completions invisible "
        "in session logs",
    ),
    (
        1716,
        "warning",
        "OBSERVABILITY",
        "Unit tests write to the PRODUCTION activity and hook-block sinks, "
        "corrupting every audit that reads them",
    ),
]
CORPUS_ISSUES = [
    {"number": number, "title": f"[CI-{sev}-{tag}] {body}"}
    for number, sev, tag, body in CORPUS
]


#: The most permissive filter configuration there is — if a label cannot pass
#: THIS, it cannot pass anything.
_LOOSEST_FILTER = {
    "min_severity": "info",
    "min_confidence": 0.0,
    "min_recurrence": 1,
    "recurrence_window_days": 30,
}


def _filter_input(signal) -> dict:
    """The shape ``should_promote`` actually reads: frequency + nested raw_data.

    Instrument control: passing ``signal.raw_data`` directly makes ``raw``
    empty, and the call then returns False for a missing-frequency reason that
    has nothing to do with severity — a probe that agrees for the wrong reason.
    """
    return {"frequency": signal.frequency, "raw_data": signal.raw_data}


def _signal(
    tag, description, *, severity_label="error", frequency=3, distinct_sessions=2
) -> AggregatedSignal:
    """A promotion-eligible signal carrying a BARE root_cause_tag."""
    return AggregatedSignal(
        source="cia_findings",
        signal_type=tag,
        description=description,
        frequency=frequency,
        severity=1.0,
        raw_data={
            "root_cause_tag": tag,
            "distinct_sessions": distinct_sessions,
            "file_refs_union": [],
            "sub_cluster_size": frequency,
            "max_severity_label": severity_label,
            "target_repo": "autonomous-dev",
        },
        timestamp="2026-09-13T00:00:00+00:00",
    )


def _finding(
    *,
    tag="GAMING",
    title="coordinator self attested doc verdict",
    severity="warning",
    session_id="s1",
    ts=None,
    **extra,
) -> dict:
    record = {
        "severity": severity,
        "root_cause_tag": tag,
        "title": title,
        "evidence": "plugins/autonomous-dev/commands/implement.md:42",
        "file_refs": ["plugins/autonomous-dev/commands/implement.md:42"],
        "session_id": session_id,
        "ts": ts or "2026-09-13T00:00:00+00:00",
    }
    record.update(extra)
    return record


# =============================================================================
# LAYER 1 — end-to-end canary against the REAL STEP 5 block
# =============================================================================


def _git(*args, cwd):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
        env={
            **os.environ,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        },
    )


_STEP5_BLOCK_RE = re.compile(r"python3 - <<'PY'\n(.*?)\n   PY\n", re.S)

#: Every shape of GitHub WRITE the block may perform.
GH_WRITE_VERBS = ("create", "comment", "edit", "close")

_FAKE_GH = '''#!/usr/bin/env python3
"""Recording `gh` stub. Records EVERY invocation; never touches the network."""
import json, os, sys

args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as fh:
    fh.write(json.dumps(args) + "\\n")

mode = os.environ.get("FAKE_GH_MODE", "ok")
if args[:2] == ["issue", "list"]:
    counter = os.environ["FAKE_GH_LOG"] + ".listcount"
    seen = int(open(counter).read()) if os.path.exists(counter) else 0
    open(counter, "w").write(str(seen + 1))
    # `list_fails`: every fetch fails. `refresh_fails`: the two bulk fetches
    # succeed and every later pre-write refresh fails — the exact TOCTOU shape.
    if mode == "list_fails" or (mode == "refresh_fails" and seen >= 2):
        sys.stderr.write("gh: API rate limit exceeded\\n")
        sys.exit(1)
    state = args[args.index("--state") + 1] if "--state" in args else "open"
    payload = json.loads(os.environ.get("FAKE_GH_OPEN", "[]")) if state == "open" else []
    print(json.dumps(payload))
    sys.exit(0)

# `write_fails`: fetches succeed, every WRITE fails — the shape that had a
# failed `gh` write recorded as an executed route.
if mode == "write_fails":
    sys.stderr.write("gh: could not create issue\\n")
    sys.exit(1)
print("https://github.com/akaszubski/autonomous-dev/issues/9999")
sys.exit(0)
'''


#: An ambient decoy reachable only through an inherited ``PYTHONPATH``. If the
#: loader is open, STEP 5 imports THIS instead of refusing, and the sentinel
#: file records that it was ENTERED — the exit status alone cannot tell a
#: product refusal apart from a decoy that raised.
_POISON_MODULE = '''"""Ambient decoy (#1790) — must never execute inside /improve STEP 5."""
import os

with open(os.environ["POISON_SENTINEL"], "w") as _fh:
    _fh.write("ambient module entered\\n")
raise RuntimeError("ambient macro_promotion executed")
'''


def _poison_sentinel(tmp_path):
    """Where the decoy records that it ran."""
    return tmp_path / "poison_entered.marker"


def _manifest_install_mapping() -> dict:
    """``github_path -> install destination``, via the REAL installer.

    The installer reads ``config/install_manifest.json``
    (``scripts/install.py:83``), NOT the same-named file at the plugin root.
    Both the path and the mapping call are reused from
    ``tests/regression/test_issue_1747_manifest_completeness.py`` rather than
    reimplemented, so there is ONE manifest reader in the suite.
    """
    spec = importlib.util.spec_from_file_location("adev_install_1790", INSTALL_PY)
    assert spec is not None and spec.loader is not None, f"no loader for {INSTALL_PY}"
    install_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(install_mod)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    installer = install_mod.PluginInstaller(mode="check", verbose=False)
    return installer.get_all_files_from_manifest(manifest)


@pytest.fixture(scope="module")
def installed_lib(tmp_path_factory) -> Path:
    """A DETACHED, MANIFEST-ONLY ``lib/``, exactly as a consumer install holds it.

    Materialised from the real installer mapping — not ``copytree`` of the
    source tree — so a module STEP 5 imports that the manifest does not ship
    is missing HERE. Copied, never symlinked: a canary reading the repository's
    own tree proves only that the source runs. Built ONCE per module.
    """
    root = tmp_path_factory.mktemp("installed")
    for github_path, local_path in _manifest_install_mapping().items():
        source = REPO_ROOT / github_path
        if not source.is_file():
            continue
        destination = root / local_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    target = root / ".claude" / "lib"
    # Instrument controls: the mapping really produced a lib tree of real files,
    # and it is NOT simply everything in the source tree.
    assert (target / "macro_promotion.py").is_file()
    assert not (target / "macro_promotion.py").is_symlink()
    assert not (target / "no_such_module_1790.py").exists()
    return target


@pytest.fixture(scope="module")
def step5_source() -> str:
    """The dedented, compilable Python source of /improve STEP 5."""
    match = _STEP5_BLOCK_RE.search(IMPROVE_CMD.read_text(encoding="utf-8"))
    assert match is not None, (
        "STEP 5 executable block not found in improve.md — the extraction "
        "regex is the instrument, and a silent no-match would make every "
        "assertion below vacuously pass"
    )
    source = textwrap.dedent(match.group(1))
    # Instrument control: the block must contain the thing we measure.
    assert "subprocess.call(" in source and '"gh", "issue"' in source, (
        "extracted block performs no gh write — wrong block extracted"
    )
    compile(source, "improve_step5", "exec")  # a syntax error must fail here
    return source


def _cmd_context_marker(tmp_path):
    """The redirected hook-contract marker for one test's ``tmp_path``.

    STEP 5 unlinks this file for real. Isolation is achieved by moving the
    path the command resolves — the ``GH_ISSUE_CMD_CONTEXT_PATH`` seam owned
    by ``lib/gh_issue_context.py`` — not by snapshotting and restoring the
    live global marker. A snapshot/restore cannot protect a concurrent reader
    and can clobber state another live session wrote in between (#1779).
    """
    return tmp_path / "cmd_context.json"


def _run_step5(
    source,
    tmp_path,
    installed_lib,
    *,
    findings,
    mode="ok",
    open_issues=None,
    dry_run=False,
    findings_dir_override=None,
    hide_module=None,
    run_from=None,
    use_findings_env=True,
):
    """Execute the real STEP 5 block against a temp repo with `gh` stubbed.

    *hide_module* deletes one module from the CONSUMER copy and puts an ambient
    decoy of the same name on the child's ``PYTHONPATH`` — the actual-route
    counterfactual for loader closure (#1790).

    *run_from* moves the child's CWD off ``PROJECT_ROOT``, and
    *use_findings_env* drops the ``AUTONOMOUS_DEV_FINDINGS_DIR`` seam so the
    block must DERIVE the store from the project root it was given. Together
    they are the counterfactual for root-vs-cwd resolution: with the seam set,
    every resolution question is answered by the variable and nothing about the
    derivation is under test.

    Returns:
        ``(completed_process, gh_invocations, project_root)``.
    """
    project_root = tmp_path / "repo"
    (project_root / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    if not (project_root / ".git").exists():
        _git("init", "-q", "-b", "main", cwd=project_root)
    # The block inserts <root>/.claude/lib on sys.path. COPY the MANIFEST-ONLY
    # tree in, file by file, exactly as the installer does — no symlink of any
    # kind, so nothing here can pass by reaching back into the repository under
    # test, nor by importing a module a consumer would never receive.
    consumer_lib = project_root / ".claude" / "lib"
    for shipped in installed_lib.rglob("*"):
        if shipped.is_file():
            destination = consumer_lib / shipped.relative_to(installed_lib)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(shipped.read_bytes())
    assert not consumer_lib.is_symlink()

    poison_dir = tmp_path / "ambient"
    if hide_module:
        hidden = consumer_lib / hide_module
        assert hidden.is_file(), f"{hide_module} was never installed; nothing hidden"
        hidden.unlink()
        poison_dir.mkdir(exist_ok=True)
        (poison_dir / hide_module).write_text(_POISON_MODULE, encoding="utf-8")

    # The command really does unlink its marker; redirect WHERE, not WHETHER.
    marker = _cmd_context_marker(tmp_path)
    marker.write_text(
        json.dumps({"command": "improve", "timestamp": "2026-09-13T00:00:00+00:00"}),
        encoding="utf-8",
    )

    # With the env seam in play the store is an independent temp directory.
    # Without it, the block must derive the store from PROJECT_ROOT alone, so
    # the records are planted where that derivation lands — and nowhere else.
    findings_dir = (
        tmp_path / "findings"
        if use_findings_env
        else project_root.resolve() / ".claude" / "logs" / "findings"
    )
    for record in findings:
        assert append_finding(record, findings_dir=findings_dir)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(_FAKE_GH, encoding="utf-8")
    gh.chmod(0o755)
    gh_log = tmp_path / "gh_invocations.jsonl"

    cwd = Path(run_from) if run_from is not None else project_root
    overlay = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "PROJECT_ROOT": str(project_root),
        CONTEXT_PATH_ENV_VAR: str(marker),
        "FAKE_GH_LOG": str(gh_log),
        "FAKE_GH_MODE": mode,
        "FAKE_GH_OPEN": json.dumps(open_issues or []),
        "DRY_RUN": "1" if dry_run else "",
    }
    if use_findings_env:
        overlay[FINDINGS_DIR_ENV] = str(findings_dir_override or findings_dir)
    else:
        # Point every AMBIENT signal at the cwd instead: an inherited
        # CLAUDE_PROJECT_DIR is what a real session sets, so leaving it unset
        # would test a quieter environment than production's.
        overlay["CLAUDE_PROJECT_DIR"] = str(cwd)
    env = hook_subprocess_env(overlay=overlay)
    if not use_findings_env:
        env.pop(FINDINGS_DIR_ENV, None)
    if hide_module:
        env["PYTHONPATH"] = str(poison_dir)
        env["POISON_SENTINEL"] = str(_poison_sentinel(tmp_path))
    proc = subprocess.run(
        [sys.executable, "-c", source],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    invocations = (
        [json.loads(line) for line in gh_log.read_text().splitlines() if line.strip()]
        if gh_log.exists()
        else []
    )
    return proc, invocations, project_root


def _writes(invocations):
    return [
        a
        for a in invocations
        if a[:1] == ["issue"] and a[1:2] and a[1] in GH_WRITE_VERBS
    ]


# The corpus finding that #1712 already tracks: three sessions, error severity.
_DUPLICATE_FINDINGS = [
    _finding(
        tag="GAMING",
        title=CORPUS[0][3],
        severity="error",
        session_id=f"s{i}",
        ts=f"2026-09-1{i}T00:00:00+00:00",
    )
    for i in (1, 2, 3)
]
# A finding no open issue tracks.
_NOVEL_FINDINGS = [
    _finding(
        tag="ORDERING",
        title="coordinator wrote state before the gate ran",
        severity="error",
        session_id=f"n{i}",
        ts=f"2026-09-1{i}T00:00:00+00:00",
    )
    for i in (1, 2, 3)
]


@pytest.mark.parametrize(
    "arm,mode,findings,open_issues,dry_run,missing_store,hide_module,expect",
    [
        # PERMITTING arm. Also the recorder's positive control: the log MUST
        # show a comment here, so a "zero writes" reading elsewhere is not a
        # blind probe.
        pytest.param(
            "append_to_existing",
            "ok",
            _DUPLICATE_FINDINGS,
            CORPUS_ISSUES,
            False,
            False,
            None,
            {
                "comment": 1,
                "create": 0,
                "promoted": 1,
                "appended": 1,
                "refresh_failures": 0,
                "create_failures": 0,
            },
            id="permit-append-no-duplicate",
        ),
        # Second permitting shape: the create route, so the recorder is proven
        # able to see `issue create` too.
        pytest.param(
            "create_novel",
            "ok",
            _NOVEL_FINDINGS,
            CORPUS_ISSUES,
            False,
            False,
            None,
            {
                "comment": 0,
                "create": 1,
                "promoted": 1,
                "appended": 0,
                "refresh_failures": 0,
                "create_failures": 0,
            },
            id="permit-create-novel-tag",
        ),
        # D1 REFUSING arm: the refresh succeeded and the write was ATTEMPTED,
        # but `gh` returned non-zero. A failed write executed no route, so the
        # digest must show promoted=0/appended=0 with the failure counted.
        # Pre-fix it appended "append" unconditionally and recorded appended=1.
        pytest.param(
            "write_fails",
            "write_fails",
            _DUPLICATE_FINDINGS,
            CORPUS_ISSUES,
            False,
            False,
            None,
            {
                "comment": 1,
                "create": 0,
                "promoted": 0,
                "appended": 0,
                "refresh_failures": 0,
                "create_failures": 1,
            },
            id="refuse-failed-gh-write-is-not-an-executed-route",
        ),
        # REFUSING arm, shape 1: the bulk fetch succeeded and routed APPEND,
        # then the pre-write refresh failed. Pre-fix this fell through to
        # `gh issue create` and duplicated #1712.
        pytest.param(
            "refresh_fails",
            "refresh_fails",
            _DUPLICATE_FINDINGS,
            CORPUS_ISSUES,
            False,
            False,
            None,
            {
                "comment": 0,
                "create": 0,
                "promoted": 0,
                "appended": 0,
                "refresh_failures": 1,
                "create_failures": 0,
            },
            id="refuse-failed-refresh-writes-nothing",
        ),
        # REFUSING arm, shape 2: every fetch fails, so an empty issue list is
        # an absence of measurement rather than a measurement of absence.
        pytest.param(
            "list_fails",
            "list_fails",
            _NOVEL_FINDINGS,
            CORPUS_ISSUES,
            False,
            False,
            None,
            {
                "comment": 0,
                "create": 0,
                "promoted": 0,
                "appended": 0,
                "refresh_failures": 1,
                "create_failures": 0,
            },
            id="refuse-all-fetches-fail",
        ),
        # ABSENCE of the route: --dry-run must exit before the first write.
        pytest.param(
            "dry_run",
            "ok",
            _DUPLICATE_FINDINGS,
            CORPUS_ISSUES,
            True,
            False,
            None,
            {"comment": 0, "create": 0},
            id="absent-dry-run-zero-writes",
        ),
        # DELIBERATELY BROKEN INSTRUMENT: the findings store does not exist.
        # A green zero here would be an unmeasured store reported as clean.
        pytest.param(
            "unmeasured",
            "ok",
            _DUPLICATE_FINDINGS,
            CORPUS_ISSUES,
            False,
            True,
            None,
            {
                "comment": 0,
                "create": 0,
                "promoted": 0,
                "appended": 0,
                "refresh_failures": 0,
                "create_failures": 0,
            },
            id="broken-unmeasured-store",
        ),
        # REFUSING arm, shape 3 — a DIFFERENT class from every row above:
        # not a bad answer from `gh`, but an incomplete INSTALL. One module is
        # removed from the consumer copy while a decoy of the same name sits
        # on an inherited PYTHONPATH. Pre-fix the block `sys.path.insert`ed
        # and imported normally, so the decoy RAN; the exit status looked like
        # a refusal and was an instrument raising.
        pytest.param(
            "hidden_module",
            "ok",
            _DUPLICATE_FINDINGS,
            CORPUS_ISSUES,
            False,
            False,
            "macro_promotion.py",
            {"comment": 0, "create": 0},
            id="refuse-module-missing-from-the-installed-copy",
        ),
    ],
)
def test_step5_canary(
    step5_source,
    installed_lib,
    tmp_path,
    arm,
    mode,
    findings,
    open_issues,
    dry_run,
    missing_store,
    hide_module,
    expect,
):
    """The real /improve STEP 5 route, end to end, with `gh` intercepted."""
    override = (tmp_path / "no-such-findings-store") if missing_store else None
    live_marker = Path(DEFAULT_CONTEXT_PATH)
    live_before = (
        live_marker.exists(),
        live_marker.stat().st_mtime_ns if live_marker.exists() else None,
    )
    proc, invocations, project_root = _run_step5(
        step5_source,
        tmp_path,
        installed_lib,
        findings=findings,
        mode=mode,
        open_issues=open_issues,
        dry_run=dry_run,
        findings_dir_override=override,
        hide_module=hide_module,
    )
    if hide_module:
        _assert_refused_the_ambient_module(
            proc, tmp_path, project_root, hide_module, invocations
        )
        return
    assert proc.returncode == 0, proc.stderr
    # Instrument control for the carrier claim: the lib the child actually
    # imported is a real directory of real files INSIDE the temp repo, not a
    # link of any kind back into this repository.
    consumer_lib = project_root / ".claude" / "lib"
    assert consumer_lib.is_dir() and not consumer_lib.is_symlink()
    assert REPO_ROOT not in consumer_lib.resolve().parents
    assert not (consumer_lib / "macro_promotion.py").is_symlink()

    # ISOLATION (#1779/#1609), both arms of the redirect:
    #  - REFUSING to touch the global path: the real marker is untouched,
    #    existence AND mtime, whichever state the live session left it in.
    #  - PERMITTING the real effect: the block genuinely unlinks its marker,
    #    at the redirected location. The dry-run arm exits before that unlink,
    #    so the marker SURVIVES there — that asymmetry is what proves the
    #    redirect is live rather than the effect simply being absent.
    assert (
        live_marker.exists(),
        live_marker.stat().st_mtime_ns if live_marker.exists() else None,
    ) == live_before, (
        f"{DEFAULT_CONTEXT_PATH} changed; the executed block is still "
        f"resolving the global literal instead of {CONTEXT_PATH_ENV_VAR}"
    )
    marker = _cmd_context_marker(tmp_path)
    assert marker.exists() is dry_run, (
        f"redirected marker exists={marker.exists()} for dry_run={dry_run}"
    )

    writes = _writes(invocations)
    assert sum(1 for w in writes if w[1] == "comment") == expect["comment"], writes
    assert sum(1 for w in writes if w[1] == "create") == expect["create"], writes

    if arm == "append_to_existing":
        # The comment lands on the ALREADY-OPEN issue, not a fresh duplicate.
        assert [w for w in writes if w[1] == "comment"][0][2] == "1712", writes
    if arm == "create_novel":
        title = writes[0][writes[0].index("--title") + 1]
        assert title.startswith("[CI-error-ORDERING] "), title
        # Round-trip: what the machinery emits is what it can later match.
        assert parse_root_cause_title(title) == ("ORDERING", "error")
    if arm == "unmeasured":
        assert "status=UNMEASURED" in proc.stdout, proc.stdout

    digest_path = project_root / ".claude" / "logs" / "aggregated_reports.jsonl"
    if dry_run:
        # A dry run persists nothing at all and prints the verdict line.
        assert not digest_path.exists()
        assert "DRY RUN VERDICT: create=0 append=1 hold=0" in proc.stdout
        return

    record, health = load_latest_persisted_digest(digest_path)
    assert health.status == "ok", health
    counts = digest_from_record(record)
    assert format_digest(counts) == record["digest_body"]
    for field in ("promoted", "appended", "refresh_failures", "create_failures"):
        assert getattr(counts, field) == expect[field], (field, record)
    if expect["refresh_failures"]:
        # The failure's own health rides on the record, not just a counter.
        assert any(h.get("status") == "error" for h in record["source_health"])


def _assert_refused_the_ambient_module(
    proc, tmp_path, project_root, hide_module, invocations
):
    """The loader-closure arm: a PRODUCT refusal, and the decoy never entered.

    The decoy's sentinel must be ABSENT (entering it at all proves an ambient
    fallback was attempted, whatever the exit status); the refusal must be the
    PRODUCT's, naming the missing module and the directory searched, since a
    ``RuntimeError`` from the decoy is an instrument raising rather than
    enforcement; and nothing may be written to GitHub. The POSITIVE CONTROL
    runs LAST — the same decoy, the same PYTHONPATH, a plain ``import``, and
    the sentinel IS written — because otherwise "absent" would be satisfied by
    a decoy nobody could have imported, i.e. a blind probe.
    """
    sentinel = _poison_sentinel(tmp_path)
    consumer_lib = project_root / ".claude" / "lib"
    combined = proc.stdout + proc.stderr
    assert not sentinel.exists(), (
        f"the ambient {hide_module} EXECUTED — the loader still falls back to "
        f"PYTHONPATH:\n{combined}"
    )
    assert proc.returncode != 0, combined
    assert "ambient macro_promotion executed" not in combined, (
        "the decoy raised; an instrument exception is not product enforcement"
    )
    assert "/improve STEP 5 REFUSES" in combined, combined
    assert hide_module[:-3] in combined, combined
    assert str(consumer_lib) in combined, combined
    assert _writes(invocations) == [], invocations

    poison_dir = tmp_path / "ambient"
    control = subprocess.run(
        [sys.executable, "-c", f"import {hide_module[:-3]}"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "PYTHONPATH": str(poison_dir),
            "POISON_SENTINEL": str(sentinel),
        },
    )
    assert sentinel.exists() and control.returncode != 0, (
        f"positive control failed: a plain import did NOT reach the decoy, so "
        f"'never entered' above proved nothing.\n{control.stderr}"
    )


def test_step5_consumes_the_previous_cycles_persisted_digest(
    step5_source, installed_lib, tmp_path
):
    """Boundary: persisted digest -> the NEXT cycle's output, via the real route.

    Failure class: a store production WRITES and no production route READS.
    Measured at 34807314, every caller of ``load_latest_persisted_digest`` was
    in this file and ``digest_from_record`` was reached only from inside it, so
    the anti-habituation ALARM #1201 exists to carry survived exactly one
    scroll of one terminal. v12 §6 refuses a reader with only test callers.

    THREE cycles against ONE store, each a different shape:
      1. The honest ABSENCE — a first cycle has no predecessor and must say
         which, never render the absence as a green zero.
      2. PERMITTING — cycle 2 reports cycle 1's real counters, cycle 1's own
         ``generated_at``, and QUOTES cycle 1's stored match-rate line.
      3. REFUSING — the store is poisoned between cycles with a forged body
         (a different shape from both rows above); cycle 3 must call it
         untrustworthy, refuse to replay it, persist its OWN digest anyway,
         and exit 0, because a bad read may never block the current run.
    """
    store = tmp_path / "repo" / ".claude" / "logs" / "aggregated_reports.jsonl"

    # --- Cycle 1: no predecessor. -------------------------------------------
    first, _, _ = _run_step5(
        step5_source,
        tmp_path,
        installed_lib,
        findings=_DUPLICATE_FINDINGS,
        open_issues=CORPUS_ISSUES,
    )
    assert first.returncode == 0, first.stderr
    assert "=== PREVIOUS CYCLE" in first.stdout, (
        "STEP 5 never reached the prior-digest read; every assertion below "
        "about WHAT it read would be vacuous"
    )
    assert "no trustworthy prior digest" in first.stdout, first.stdout
    assert "status=UNMEASURED" in first.stdout, first.stdout

    record1, health1 = load_latest_persisted_digest(store)
    assert health1.status == "ok", health1
    counts1 = digest_from_record(record1)

    # --- Cycle 2: the permitting arm. ---------------------------------------
    second, _, _ = _run_step5(
        step5_source,
        tmp_path,
        installed_lib,
        findings=_DUPLICATE_FINDINGS,
        open_issues=CORPUS_ISSUES,
    )
    assert second.returncode == 0, second.stderr
    # Tied to cycle 1's OWN timestamp, so this line cannot be satisfied by
    # cycle 2 reporting its own freshly-built counters back to itself.
    assert (
        f"status=OK generated_at={record1['generated_at']} "
        f"promoted={counts1.promoted} appended={counts1.appended} "
        f"held={counts1.held} create_failures={counts1.create_failures} "
        f"refresh_failures={counts1.refresh_failures}"
    ) in second.stdout, second.stdout
    assert "no trustworthy prior digest" not in second.stdout, second.stdout
    # The match-rate line is QUOTED from the stored body, not re-rendered.
    stored_line = next(
        line
        for line in record1["digest_body"].splitlines()
        if line.startswith("Match-rate:")
    )
    assert f"  prior| {stored_line}" in second.stdout, second.stdout

    # --- Cycle 3: the refusing arm, a forged body. --------------------------
    forged = {**record1, "digest_body": "FORGED BODY NO FORMATTER RENDERS"}
    with open(store, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"digest": forged}) + "\n")
    # Positive control on the poison: the store really is untrustworthy NOW,
    # so cycle 3's refusal below is caused by the corruption and not by the
    # reader being inert. Cycle 2's `ok` read above is the negative control.
    poisoned, poisoned_health = load_latest_persisted_digest(store)
    assert poisoned is None and poisoned_health.status == "degraded", poisoned_health

    third, _, _ = _run_step5(
        step5_source,
        tmp_path,
        installed_lib,
        findings=_DUPLICATE_FINDINGS,
        open_issues=CORPUS_ISSUES,
    )
    assert third.returncode == 0, third.stderr  # a bad read NEVER blocks
    assert "no trustworthy prior digest" in third.stdout, third.stdout
    assert "status=DEGRADED" in third.stdout, third.stdout
    assert "failed replay validation" in third.stdout, third.stdout
    # The forgery is reported, never rendered as if it were a real cycle.
    assert "FORGED BODY" not in third.stdout, third.stdout

    # Cycle 3 still did its own job: its digest is persisted and replays.
    record3, health3 = load_latest_persisted_digest(store)
    assert health3.status == "ok", health3
    assert record3["generated_at"] not in (
        record1["generated_at"],
        forged["generated_at"],
    )
    assert format_digest(digest_from_record(record3)) == record3["digest_body"]


def test_step5_reads_the_findings_of_the_root_it_was_given_not_its_cwd(
    step5_source, installed_lib, tmp_path
):
    """Boundary: the STATED project root -> the store STEP 5 reads.

    Failure class, a DIFFERENT shape from every row of the canary matrix: not a
    bad answer from ``gh`` and not an incomplete install, but a resolution that
    follows the PROCESS (its cwd, an inherited ``CLAUDE_PROJECT_DIR``) instead
    of the root the caller named. STEP 5 derived ``LIB`` and ``REPORT_PATH``
    from ``PROJECT_ROOT`` while calling ``resolve_findings_dir()`` with no
    ``start_path``, so a caller that set ``PROJECT_ROOT`` from a subprocess
    sitting in another checkout read one repository's findings and wrote its
    report into another — the per-checkout split #1790 exists to close.

    Both arms, with the ambient signals pointed AWAY from the stated root in
    each, so neither can be satisfied by a resolver that simply prefers
    whichever store happens to hold records:

    * PERMITTING — the stated root's store holds the findings, the cwd's is
      empty: the route must run and comment on the tracked issue.
    * REFUSING — reversed: the cwd's store holds them and the stated root has
      no store at all. STEP 5 must report UNMEASURED and write nothing, because
      a neighbouring checkout's evidence is not this repository's.

    The ``AUTONOMOUS_DEV_FINDINGS_DIR`` seam is deliberately UNSET here; with it
    set, the variable answers every resolution question and nothing about the
    derivation would be under test.
    """

    def _neighbour(root: Path) -> Path:
        """A real, unrelated git checkout to run FROM."""
        root.mkdir(parents=True)
        _git("init", "-q", "-b", "main", cwd=root)
        (root / ".claude" / "logs" / "findings").mkdir(parents=True)
        return root

    # --- PERMITTING: findings at the stated root. ---------------------------
    arm_a = tmp_path / "arm-stated-root-has-them"
    elsewhere_a = _neighbour(tmp_path / "elsewhere-a")
    proc, invocations, project_root = _run_step5(
        step5_source,
        arm_a,
        installed_lib,
        findings=_DUPLICATE_FINDINGS,
        open_issues=CORPUS_ISSUES,
        run_from=elsewhere_a,
        use_findings_env=False,
    )
    assert proc.returncode == 0, proc.stderr

    # Instrument controls: two DIFFERENT directories, the stated one really
    # holds the records and the ambient one is really empty — otherwise "it
    # read the right store" could not distinguish them.
    stated = project_root.resolve() / ".claude" / "logs" / "findings"
    ambient = elsewhere_a.resolve() / ".claude" / "logs" / "findings"
    assert stated != ambient, (stated, ambient)
    assert list(stated.glob("*.jsonl")), stated
    assert not list(ambient.glob("*.jsonl")), ambient

    # The CIA-findings banner is the store's OWN status line; the prior-digest
    # line uses the same vocabulary and is UNMEASURED on a first cycle either
    # way, so matching on the bare word would not discriminate.
    assert "CIA findings status=" not in proc.stdout, proc.stdout
    assert [w[2] for w in _writes(invocations) if w[1] == "comment"] == ["1712"], (
        invocations,
        proc.stdout,
    )
    record, health = load_latest_persisted_digest(
        project_root / ".claude" / "logs" / "aggregated_reports.jsonl"
    )
    assert health.status == "ok", health
    counts = digest_from_record(record)
    assert (counts.promoted, counts.appended) == (1, 1), record

    # --- REFUSING: the same findings, at the CWD's checkout instead. ---------
    arm_b = tmp_path / "arm-cwd-has-them"
    elsewhere_b = _neighbour(tmp_path / "elsewhere-b")
    neighbour_store = elsewhere_b.resolve() / ".claude" / "logs" / "findings"
    for entry in _DUPLICATE_FINDINGS:
        assert append_finding(entry, findings_dir=neighbour_store)

    proc_b, invocations_b, root_b = _run_step5(
        step5_source,
        arm_b,
        installed_lib,
        findings=[],
        open_issues=CORPUS_ISSUES,
        run_from=elsewhere_b,
        use_findings_env=False,
    )
    assert proc_b.returncode == 0, proc_b.stderr
    assert list(neighbour_store.glob("*.jsonl")), neighbour_store
    assert not (root_b.resolve() / ".claude" / "logs" / "findings").exists()
    assert "CIA findings status=UNMEASURED" in proc_b.stdout, proc_b.stdout
    assert _writes(invocations_b) == [], invocations_b
    record_b, health_b = load_latest_persisted_digest(
        root_b / ".claude" / "logs" / "aggregated_reports.jsonl"
    )
    assert health_b.status == "ok", health_b
    counts_b = digest_from_record(record_b)
    assert (counts_b.promoted, counts_b.appended) == (0, 0), record_b


#: Every module STEP 5 imports, directly or through one of its imports.
_STEP5_IMPORT_CLOSURE = (
    "runtime_data_aggregator.py",
    "macro_promotion.py",
    "cia_finding_store.py",
    "issue_triage_analyzer.py",
    "cia_promotion_filter.py",
    "gh_issue_context.py",
    "drain_queue_state.py",
    "benchmark_history.py",
    "path_utils.py",
)


def test_step5_import_closure_ships_to_an_installed_consumer(
    installed_lib, step5_source
):
    """Failure class: a route that runs from source and never reaches a consumer.

    A consumer receives exactly what the installer maps out of
    ``config/install_manifest.json``, so this asserts against the MATERIALISED
    tree the canary actually imports — not against a manifest read a second
    way, and not against ``plugins/autonomous-dev/install_manifest.json``,
    which the installer never reads (``scripts/install.py:83``).

    Instrument controls: a module known to ship is present, and an invented
    name is not — without the negative control, a mapping that copied the whole
    source tree would satisfy the positive one.
    """
    missing = sorted(
        n for n in _STEP5_IMPORT_CLOSURE if not (installed_lib / n).is_file()
    )
    assert missing == [], (
        f"STEP 5 imports {missing}, which the install manifest does not ship; "
        f"a consumer install would ImportError on this route"
    )
    assert (installed_lib / "path_utils.py").is_file()  # positive control
    assert not (installed_lib / "no_such_module_1790.py").exists()  # negative

    # The block's OWN preflight list must cover the same closure, or a module
    # could go missing from a consumer install without the loader refusing.
    unguarded = sorted(
        n[:-3] for n in _STEP5_IMPORT_CLOSURE if f'"{n[:-3]}"' not in step5_source
    )
    assert unguarded == [], (
        f"STEP 5 imports {unguarded} but does not name them in ROUTE_MODULES; "
        f"a consumer missing one would fall through to an ambient copy"
    )


# =============================================================================
# LAYER 2 — contract matrix at the boundaries
# =============================================================================


@pytest.mark.parametrize(
    "failure_class,title,expected_tag,expected_severity",
    [
        (
            "machinery title parses to the bare tag the signal carries",
            CORPUS_ISSUES[0]["title"],
            "GAMING",
            "error",
        ),
        (
            "a bare tag containing a hyphen is not split on the last hyphen",
            CORPUS_ISSUES[1]["title"],
            "HOOK-REGRESSION",
            "error",
        ),
        (
            "a non-error severity is recognised in the prefix",
            CORPUS_ISSUES[3]["title"],
            "OBSERVABILITY",
            "warning",
        ),
        (
            "a hand-written tag stays verbatim and claims no severity",
            "[GAMING] hand filed",
            "GAMING",
            None,
        ),
        (
            "the 2-segment legacy form is NOT a machinery tag",
            "[CI-warning] soft fail",
            "CI-warning",
            None,
        ),
        (
            "an unknown word in severity position is not a severity",
            "[CI-sev9-GAMING] x",
            "CI-sev9-GAMING",
            None,
        ),
        (
            "an untagged title degrades to UNTAGGED, never to a guess",
            "no bracket here",
            "UNTAGGED",
            None,
        ),
    ],
)
def test_title_parse_contract(failure_class, title, expected_tag, expected_severity):
    """Boundary: issue title string -> (root_cause_tag, severity)."""
    assert parse_root_cause_title(title) == (expected_tag, expected_severity), (
        failure_class
    )
    assert extract_root_cause_tag(title) == expected_tag, failure_class


def test_title_format_is_the_inverse_of_the_parser():
    """Boundary: (tag, severity) -> title, and back unchanged.

    Failure class: an emitter that drifts from the parser, which is what made
    every /improve run duplicate its own previous issue.
    """
    for _number, severity, tag, body in CORPUS:
        emitted = format_root_cause_title(
            root_cause_tag=tag,
            severity_label=severity,
            description=body,
        )
        assert parse_root_cause_title(emitted) == (tag, severity)
        # Re-formatting an already-prefixed tag must not double the prefix.
        assert (
            format_root_cause_title(
                root_cause_tag=emitted.split("]")[0].lstrip("["),
                severity_label=severity,
                description=body,
            )
            == emitted
        )

    # Clamping removes description bytes only — the tag leads the string.
    clamped = format_root_cause_title(
        root_cause_tag="GAMING",
        severity_label="error",
        description="x" * 500,
        max_length=40,
    )
    assert len(clamped) == 40
    assert parse_root_cause_title(clamped)[0] == "GAMING"

    # An overlong DESCRIPTION still round-trips — clamping eats only the body.
    long_body = format_root_cause_title(
        root_cause_tag="GAMING",
        severity_label="error",
        description="y" * 900,
    )
    assert parse_root_cause_title(long_body) == ("GAMING", "error")

    # REFUSING rows: every input that cannot round-trip raises rather than
    # emit a corrupted title. Each names the corruption it prevents.
    for kwargs, corruption in (
        (
            {
                "root_cause_tag": "GAMING",
                "severity_label": INVALID_SEVERITY_LABEL,
                "description": "x",
            },
            "an unemittable severity would make the prefix unparseable",
        ),
        (
            {
                "root_cause_tag": "GA]MING",
                "severity_label": "warning",
                "description": "desc",
            },
            "'[CI-warning-GA]MING] desc' closes early and parses back as 'GA'",
        ),
        (
            {
                "root_cause_tag": "G[AMING",
                "severity_label": "warning",
                "description": "desc",
            },
            "an opening bracket inside the tag is the same corruption class",
        ),
        (
            {
                "root_cause_tag": "T" * 250,
                "severity_label": "warning",
                "description": "desc",
            },
            "a 250-char tag is clamped past its closing ']' -> UNTAGGED",
        ),
        (
            {"root_cause_tag": "", "severity_label": "error", "description": "x"},
            "a blank tag would emit '[CI-error-]'",
        ),
    ):
        with pytest.raises(ValueError):
            format_root_cause_title(**kwargs)
        # ...and at the real emit site the refusal is VISIBLE, so a dry run
        # shows it rather than a silently corrupted title reaching `gh`.
        corrupt = decide_promotions(
            [
                _signal(
                    kwargs["root_cause_tag"],
                    kwargs["description"],
                    severity_label=kwargs["severity_label"],
                )
            ],
            [],
        )[0]
        assert planned_title(corrupt).startswith("<UNEMITTABLE:"), corruption


@pytest.mark.parametrize(
    "failure_class,tag,description,expected_route,expected_match",
    [
        (
            "a finding already tracked by an open issue is appended, not re-filed",
            "GAMING",
            CORPUS[0][3],
            "append",
            1712,
        ),
        (
            "a hyphenated tag still matches its open issue",
            "HOOK-REGRESSION",
            CORPUS[1][3],
            "append",
            1714,
        ),
        (
            "a genuinely new finding under a tracked tag creates",
            "GAMING",
            "coordinator marked an absent specialist complete to "
            "satisfy the agent-completeness gate",
            "create",
            None,
        ),
        (
            "an untracked tag creates even when its words overlap a tracked issue",
            "ORDERING",
            CORPUS[0][3],
            "create",
            None,
        ),
    ],
)
def test_route_classification(
    failure_class, tag, description, expected_route, expected_match
):
    """Boundary: (signal, open issues) -> create/append."""
    route, matched = classify_route(_signal(tag, description), CORPUS_ISSUES)
    assert (route, matched) == (expected_route, expected_match), failure_class


def test_severity_vocabulary_gates_every_promotion_branch():
    """Boundary: severity label -> promote / hold, on BOTH deciders.

    Failure class: ``decide_promotions`` promoted an out-of-vocabulary severity
    that ``should_promote`` rejected, emitting the unemittable title
    ``[CI-invalid-GAMING] ...``. Measured at 34807314 with frequency 4 and 4
    distinct sessions: route ``create``.
    """
    quarantined = _signal(
        "GAMING",
        "x",
        severity_label=INVALID_SEVERITY_LABEL,
        frequency=4,
        distinct_sessions=4,
    )
    decision = decide_promotions([quarantined], CORPUS_ISSUES)[0]
    assert decision.route == "hold", decision
    assert INVALID_SEVERITY_LABEL in decision.rationale
    promote, why = should_promote(_filter_input(quarantined), config=_LOOSEST_FILTER)
    assert promote is False, why  # the two deciders agree
    assert why == "severity 'invalid' below min_severity 'info'", why
    assert planned_title(decision).startswith("<UNEMITTABLE:")

    # PERMITTING arm at the same call site, with the SAME volume: a valid
    # severity routes normally, so the refusal above is conditional.
    valid = _signal(
        "ORDERING", "x", severity_label="info", frequency=4, distinct_sessions=4
    )
    assert decide_promotions([valid], CORPUS_ISSUES)[0].route == "create"

    # `critical` outranks `error` and must inherit its breadth-waiving
    # fast-path rather than promote less readily than a lower severity.
    assert "critical" in CIA_HIGH_SEVERITY_LABELS
    assert "critical" in CIA_SEVERITY_ORDER
    assert "critical" in ALLOWED_SEVERITIES
    assert "critical" in SEVERITY_LABEL_VOCABULARY
    critical = _signal(
        "ORDERING", "boom", severity_label="critical", frequency=2, distinct_sessions=1
    )
    assert decide_promotions([critical], [])[0].route == "create"
    assert should_promote(_filter_input(critical), config=_LOOSEST_FILTER)[0] is True
    # Instrument control for the refusal above: the SAME call shape permits a
    # valid label, so "False" was a severity verdict and not a shape accident.
    assert should_promote(_filter_input(valid), config=_LOOSEST_FILTER)[0] is True


@pytest.mark.parametrize(
    "failure_class,severity,expect_label,expect_quarantine",
    [
        ("a valid severity is stored unchanged", "critical", "critical", False),
        (
            "an unknown severity is quarantined, never downgraded to info",
            "SEV0",
            INVALID_SEVERITY_LABEL,
            True,
        ),
        ("a non-string severity is quarantined too", 3, INVALID_SEVERITY_LABEL, True),
    ],
)
def test_store_severity_write_contract(
    tmp_path, failure_class, severity, expect_label, expect_quarantine
):
    """Boundary: caller severity -> persisted severity."""
    findings_dir = tmp_path / "findings"
    assert append_finding(_finding(severity=severity), findings_dir=findings_dir)
    record = json.loads(next(findings_dir.glob("*.jsonl")).read_text().splitlines()[0])
    assert record["severity"] == expect_label, failure_class
    assert (SEVERITY_QUARANTINE_FIELD in record) is expect_quarantine
    if expect_quarantine:
        assert record[SEVERITY_QUARANTINE_FIELD] == str(severity)
        # A quarantined record satisfies NO threshold, including the loosest.
        assert (
            should_promote(
                {
                    "frequency": 9,
                    "raw_data": {"max_severity_label": record["severity"]},
                },
                config=_LOOSEST_FILTER,
            )[0]
            is False
        )


@pytest.mark.parametrize(
    "failure_class,setup,expected_status,expected_note",
    [
        (
            "a missing store is UNMEASURED, not a green zero",
            "missing",
            "unmeasured",
            "does not exist",
        ),
        ("an existing empty store is a trustworthy zero", "empty", "empty", ""),
        (
            "an unparseable line makes the measurement known-incomplete",
            "corrupt",
            "degraded",
            "malformed",
        ),
        (
            "an unreadable file is degraded, not invisible",
            "unreadable",
            "degraded",
            "unreadable",
        ),
        (
            "a MAX_LINES truncation is degraded, never reported as complete",
            "truncated",
            "degraded",
            "cap",
        ),
        (
            "an out-of-vocabulary severity degrades the whole measurement",
            "invalid_severity",
            "degraded",
            "out-of-vocabulary",
        ),
        (
            "a healthy store still reports ok — the statuses are conditional",
            "healthy",
            "ok",
            "",
        ),
    ],
)
def test_collector_health_vocabulary(
    tmp_path, monkeypatch, failure_class, setup, expected_status, expected_note
):
    """Boundary: store state -> SourceHealth status."""
    findings_dir = tmp_path / "findings"
    if setup != "missing":
        findings_dir.mkdir(parents=True)
    if setup in ("corrupt", "healthy", "unreadable", "truncated", "invalid_severity"):
        assert append_finding(
            _finding(severity="error", title="gate ran after the write"),
            findings_dir=findings_dir,
        )
    monthly = next(iter(findings_dir.glob("*.jsonl")), findings_dir / "x.jsonl")
    if setup == "corrupt":
        with open(monthly, "a") as fh:
            fh.write("{not json at all\n")
    elif setup == "unreadable":
        monthly.chmod(0o000)
    elif setup == "invalid_severity":
        assert append_finding(
            _finding(severity="SEV0", title="a wholly unknown severity"),
            findings_dir=findings_dir,
        )
    elif setup == "truncated":
        monkeypatch.setattr("runtime_data_aggregator.MAX_LINES", 1)

    try:
        signals, health = collect_cia_findings(findings_dir, window_days=3650)
        assert health.status == expected_status, (failure_class, health)
        assert expected_note in health.error_message, (failure_class, health)
    finally:
        if setup == "unreadable":
            monthly.chmod(0o600)


#: What a real cycle persists beside its counts: the health of every source it
#: read. A digest without this cannot be tied to a measured cycle.
_MEASURED_HEALTH = [
    {"source": "cia_findings", "status": "ok", "signal_count": 1, "error_message": ""}
]


def test_persisted_digest_reader_refuses_what_it_cannot_replay(tmp_path):
    """Boundary: persisted line -> replayable digest, or a refusal.

    Failure class: an unreadable record reported ``ok``. Measured at 34807314:
    ``{"digest": {"version": 999}}`` returned ``SourceHealth(status='ok')``, so
    a consumer would have acted on a record it cannot replay.

    Every REFUSING row below writes an older HEALTHY line FIRST and the broken
    one LAST. That ordering is the point: a present-but-malformed latest record
    silently skipped in favour of older healthy data reports a stale cycle as
    the current one, which is a worse lie than refusing outright.

    Rows carry the whole OUTER line, because the defect class is not confined
    to the inner digest: measured at 34807314, an outer ``{}`` returned ``ok``
    and the PREVIOUS cycle's body while an outer ``[]`` correctly degraded.
    """
    store = tmp_path / "aggregated_reports.jsonl"

    # UNMEASURED arms: no file, then a file whose digest is the DECLARED
    # absence (``null`` — what persist_report writes for a digest-less report).
    assert load_latest_persisted_digest(store)[1].status == "unmeasured"
    store.write_text(json.dumps({"signals": [], "digest": None}) + "\n")
    assert load_latest_persisted_digest(store)[1].status == "unmeasured"

    counts = build_digest(
        [],
        [],
        open_auto_improvement_count=30,
        findings_observed=0,
        distinct_sessions_observed=0,
    )
    good = digest_to_record(
        counts,
        digest_body=format_digest(counts),
        source_health=_MEASURED_HEALTH,
        generated_at="2026-09-13T00:00:00+00:00",
    )

    #: Rows whose broken value is the INNER ``digest``; wrapped below.
    inner_rows = (
        ({"version": 999}, "unknown version"),
        ({k: v for k, v in good.items() if k != "digest_body"}, "missing envelope key"),
        (
            {
                **good,
                "counts": {
                    k: v for k, v in good["counts"].items() if k != "match_rate"
                },
            },
            "missing counter",
        ),
        # R1: a count that is not a number. Dataclass construction type-checks
        # nothing, so this replayed into a DigestCounts whose create_failures
        # was the string 'broken' and format_digest raised TypeError at
        # render — AFTER the reader had certified the record 'ok'.
        (
            {**good, "counts": {**good["counts"], "create_failures": "broken"}},
            "a non-numeric count cannot be rendered",
        ),
        (
            {**good, "counts": {**good["counts"], "match_rate": "high"}},
            "a non-numeric ratio is the same class in the optional-field arm",
        ),
        # R2: source_health present but UNUSABLE. The reader checked only that
        # the key held a non-empty list, so a list of empty dicts — naming no
        # source and no status — reported a healthy replay.
        (
            {**good, "source_health": [{}]},
            "an entry naming neither source nor status is not evidence",
        ),
        (
            {
                **good,
                "source_health": [
                    {"source": "cia_findings", "status": "probably-fine"}
                ],
            },
            "a status outside the health vocabulary is not evidence",
        ),
        (
            {**good, "source_health": [{"source": "  ", "status": "ok"}]},
            "a blank source name ties the counts to nothing",
        ),
        # A PRESENT but unreplayable latest record, three shapes. Each used to
        # be skipped, returning the OLDER healthy record with status 'ok'.
        ([], "empty list is present, not absent"),
        ({}, "empty dict is present, not absent"),
        ("a digest", "a scalar is present, not absent"),
        # A digest nobody can tie to a measured cycle is not a trust anchor.
        (
            {k: v for k, v in good.items() if k != "source_health"},
            "no source_health key",
        ),
        ({**good, "source_health": []}, "empty source_health"),
        # O2: counts and health both VALID, body forged. digest_from_record
        # promised byte-for-byte replay of digest_body and never checked it, so
        # this read back 'ok' while replay rendered the real digest instead.
        (
            {**good, "digest_body": "FORGED BODY"},
            "a digest_body the counts beside it do not render",
        ),
        (
            {**good, "digest_body": 42},
            "a non-string digest_body is the same class in the type arm",
        ),
    )

    for outer, why in (
        [({"digest": broken}, why) for broken, why in inner_rows]
        # O1: the OUTER envelope. An object carrying NONE of the report's keys
        # is a truncated envelope, not a report that declared ``digest: null``;
        # read as the latter it served the previous cycle's body as 'ok'. The
        # list and scalar rows are a DIFFERENT shape from that reproducer and
        # fix the class — "not a report envelope" — rather than the instance.
        + [
            ({}, "an outer object carrying no report field at all"),
            ([], "an outer list is not a report envelope"),
            ("a report", "an outer scalar is not a report envelope"),
            ({"unrelated": 1}, "an outer object whose keys are all foreign"),
        ]
    ):
        store.write_text(json.dumps({"digest": good}) + "\n" + json.dumps(outer) + "\n")
        record, health = load_latest_persisted_digest(store)
        assert health.status == "degraded", why
        assert health.status not in TRUSTWORTHY_HEALTH_STATUSES, why
        if "digest" in (outer if isinstance(outer, dict) else {}):
            assert record is None, why
            assert "failed replay validation" in health.error_message, why
        else:
            # A malformed OUTER line cannot invalidate the older record, but it
            # must mark the read known-incomplete so "latest" is not trusted.
            assert "malformed line" in health.error_message, why

    # PERMITTING arm 1: a LEGITIMATE report that declares no digest still skips
    # cleanly — the older record is served, and the read stays 'ok'.
    store.write_text(
        json.dumps({"digest": good})
        + "\n"
        + json.dumps(
            {
                "signals": [],
                "source_health": [],
                "window_start": "a",
                "window_end": "b",
                "generated_at": "c",
                "top_n": 10,
                "digest": None,
            }
        )
        + "\n"
    )
    record, health = load_latest_persisted_digest(store)
    assert health.status == "ok" and record["digest_body"] == good["digest_body"]

    # PERMITTING arm 2: the last digest-bearing line wins and replays exactly.
    later_counts = build_digest(
        [],
        [],
        open_auto_improvement_count=31,
        findings_observed=2,
        distinct_sessions_observed=1,
        refresh_failures=1,
    )
    later = digest_to_record(
        later_counts,
        digest_body=format_digest(later_counts),
        source_health=_MEASURED_HEALTH,
        generated_at="2026-09-13T01:00:00+00:00",
    )
    assert later["digest_body"] != good["digest_body"]  # instrument control
    store.write_text(
        json.dumps({"digest": good})
        + "\n"
        + json.dumps({"signals": []})
        + "\n"
        + json.dumps({"digest": later})
        + "\n"
    )
    record, health = load_latest_persisted_digest(store)
    assert health.status == "ok"
    # The LATER record is the one returned, and its OWN body is what replays.
    assert record["digest_body"] == later["digest_body"]
    assert format_digest(digest_from_record(record)) == record["digest_body"]


def test_digest_counts_the_routes_that_executed():
    """Boundary: EFFECTIVE decisions -> persisted counts.

    Failure class: a run that planned APPEND, duplicated instead, and recorded
    ``appended=1, created=0, match_rate=1.0, create_failures=0`` — counts that
    described the plan rather than what happened. An outcome is now the
    decision itself, re-derived, so there is no second list to fall out of
    step with it.
    """
    decisions = decide_promotions(
        [_signal("GAMING", CORPUS[0][3])],
        CORPUS_ISSUES,
    )
    assert decisions[0].route == "append"

    planned = build_digest(
        decisions,
        [],
        open_auto_improvement_count=30,
        findings_observed=3,
        distinct_sessions_observed=2,
    )
    assert (planned.appended, planned.match_rate) == (1, 1.0)

    # The pre-write refresh flipped the route: what executed was a CREATE.
    flipped = [
        replace(
            decisions[0],
            route="create",
            matched_open_issue=None,
            rationale="refreshed fetch found no matching open issue",
        )
    ]
    executed = build_digest(
        flipped,
        [],
        open_auto_improvement_count=30,
        findings_observed=3,
        distinct_sessions_observed=2,
    )
    assert (executed.appended, executed.match_rate) == (0, 0.0)

    # A failed write and an abandoned refresh are both `held`, with the cause
    # named in the rationale rather than dropped.
    abandoned = [held(decisions[0], "gh write failed rc=1")]
    aborted = build_digest(
        abandoned,
        [],
        open_auto_improvement_count=30,
        findings_observed=3,
        distinct_sessions_observed=2,
        refresh_failures=1,
    )
    assert (aborted.promoted, aborted.held, aborted.refresh_failures) == (0, 1, 1)
    assert "Refresh failures: 1 ALARM" in format_digest(aborted)
    # A high-severity finding that did not reach GitHub must surface as a
    # silent error rather than vanish from the digest.
    assert aborted.error_without_other_channel == (CORPUS[0][3][:200],)
    assert abandoned[0].matched_open_issue is None
    assert "gh write failed rc=1" in abandoned[0].rationale
    # held() derives a NEW decision; the planned one it came from is intact,
    # which is what makes the dry run and the real run share one vocabulary.
    assert decisions[0].route == "append"
    assert abandoned[0].signal is decisions[0].signal


@pytest.mark.parametrize(
    "failure_class,status,expected_route",
    [
        ("a failed refresh must never permit a mutation", "error", "hold"),
        ("an unrecognised status fails closed", "weird-new-status", "hold"),
        ("a degraded refresh is not evidence of absence", "degraded", "hold"),
        ("a healthy refresh that finds the match appends", "ok", "append"),
        ("a healthy refresh that finds nothing creates", "empty", "create"),
    ],
)
def test_pre_write_refresh_gate(failure_class, status, expected_route):
    """Boundary: (fresh fetch, its health) -> the decision that may be written."""
    decision = decide_promotions([_signal("GAMING", CORPUS[0][3])], CORPUS_ISSUES)[0]
    fresh = CORPUS_ISSUES if status == "ok" else []
    effective = reclassify_before_write(
        decision,
        fresh,
        SourceHealth(source="github", status=status),
    )
    assert effective.route == expected_route, (failure_class, effective.rationale)
    assert effective.matched_open_issue == (
        1712 if expected_route == "append" else None
    )
    if expected_route == "hold":
        assert "not trustworthy" in effective.rationale
    # The finding is re-routed, never swapped for another one.
    assert effective.signal is decision.signal


@pytest.fixture
def two_worktrees(tmp_path):
    """A real primary checkout plus a real SIBLING linked worktree.

    Sibling, not ``<repo>/.worktrees/<name>``: the pre-existing
    ``_worktree_parent_log_dir`` helper fires only on a ``/.worktrees/`` path
    substring, and this repo's own worktrees are siblings — which is exactly
    why that helper never caught the measured split.
    """
    primary = tmp_path / "primary"
    primary.mkdir()
    _git("init", "-q", "-b", "main", cwd=primary)
    _git("config", "user.email", "t@example.com", cwd=primary)
    _git("config", "user.name", "t", cwd=primary)
    (primary / "README.md").write_text("seed\n", encoding="utf-8")
    _git("add", "README.md", cwd=primary)
    _git("commit", "-q", "-m", "seed", cwd=primary)
    linked = tmp_path / "primary-feature"
    _git("worktree", "add", "-q", str(linked), "-b", "feature", cwd=primary)
    return primary, linked


def test_findings_dir_has_one_owner_across_checkouts(
    two_worktrees, tmp_path, monkeypatch
):
    """Boundary: a checkout -> its findings store.

    Failure class: per-checkout resolution fragmented one repository's findings
    across four directories (MEASURED 7 / 57 / 4 / 3 for one month), so every
    promotion-frequency and breadth denominator ran on a fraction of them.
    """
    primary, linked = two_worktrees
    monkeypatch.delenv(FINDINGS_DIR_ENV, raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    # Both arms of the worktree test itself.
    assert git_common_repo_root(linked) == primary.resolve()
    assert git_common_repo_root(primary) is None
    non_git = tmp_path / "not-a-repo"
    non_git.mkdir()
    assert git_common_repo_root(non_git) is None  # git ANSWERED "no parent"

    # Discovery that cannot RUN is UNMEASURED, never a silent fall-back to the
    # per-worktree store — that fall-back is the fragmented ownership this
    # resolver removes. Simulated by emptying PATH so `git` is not found.
    monkeypatch.setenv("PATH", "")
    for probe in (
        lambda: git_common_repo_root(linked),
        lambda: resolve_findings_dir(start_path=linked),
    ):
        with pytest.raises(LogDirResolutionError, match="could not run"):
            probe()
    monkeypatch.undo()
    monkeypatch.delenv(FINDINGS_DIR_ENV, raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    expected = primary.resolve() / ".claude" / "logs" / "findings"
    assert resolve_findings_dir(start_path=primary) == expected
    assert resolve_findings_dir(start_path=linked) == expected
    # An ambient CLAUDE_PROJECT_DIR pointing at the worktree cannot reopen it.
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(linked))
    assert resolve_findings_dir(start_path=linked) == expected

    # The env seam wins, and a blank value is ignored rather than becoming '.'.
    explicit = tmp_path / "explicit"
    monkeypatch.setenv(FINDINGS_DIR_ENV, str(explicit))
    assert resolve_findings_dir(start_path=primary) == explicit
    monkeypatch.setenv(FINDINGS_DIR_ENV, "   ")
    assert resolve_findings_dir(start_path=primary) == expected


def test_ambient_resolution_refuses_rather_than_pick_a_directory(tmp_path, monkeypatch):
    """Failure class: a silent cwd or source-checkout fallback.

    The marker search is stubbed rather than trusting a marker-free temp path:
    MEASURED while writing this, macOS ``$TMPDIR`` already contains a stray
    ``.claude`` directory, so a test relying on its absence would have passed
    while proving nothing.
    """
    monkeypatch.delenv(FINDINGS_DIR_ENV, raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    orphan = tmp_path / "consumer"
    orphan.mkdir()
    monkeypatch.chdir(orphan)

    def _no_marker_anywhere(*_a, **_k):
        raise FileNotFoundError("no .git or .claude marker in any ancestor")

    monkeypatch.setattr(path_utils, "find_project_root", _no_marker_anywhere)
    with pytest.raises(LogDirResolutionError) as excinfo:
        resolve_findings_dir()
    assert "Refusing to fall back" in str(excinfo.value)
    assert "autonomous-dev source checkout" in str(excinfo.value)

    # PERMITTING arm at the same call site: restore the search and it resolves.
    monkeypatch.setattr(path_utils, "find_project_root", lambda **_k: tmp_path)
    assert resolve_findings_dir() == tmp_path / ".claude" / "logs" / "findings"


def test_aggregate_reads_one_store_from_either_checkout(two_worktrees, monkeypatch):
    """The REAL ``aggregate()`` caller, from a primary checkout and a worktree.

    Failure class: a production helper with only test callers. Before this,
    ``aggregate()`` hardcoded ``project_root/.claude/logs/findings`` while the
    canonical ``resolve_findings_dir()`` had no production caller at all.
    """
    primary, linked = two_worktrees
    monkeypatch.delenv(FINDINGS_DIR_ENV, raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(
        "runtime_data_aggregator.collect_github_signals",
        lambda *_a, **_k: ([], SourceHealth(source="github", status="empty")),
    )

    shared = resolve_findings_dir(start_path=primary)
    for index in (1, 2, 3):
        assert append_finding(
            _finding(
                tag="ORDERING",
                title="gate evaluated stale state",
                severity="error",
                session_id=f"w{index}",
                ts=f"2026-09-1{index}T00:00:00+00:00",
            ),
            findings_dir=shared,
        )

    for checkout in (primary, linked):
        report = aggregate(checkout, window_days=7)
        cia = [h for h in report.source_health if h.source == "cia_findings"]
        assert cia and cia[0].status == "ok", (checkout, cia)
        assert cia[0].signal_count == 1, checkout
        signal = [s for s in report.signals if s.signal_type == "ORDERING"][0]
        assert signal.frequency == 3, checkout

    # Negative control: a checkout with no findings must NOT report ok, or the
    # assertions above would pass for a resolver that ignored its argument.
    other = primary.parent / "unrelated"
    (other / ".claude").mkdir(parents=True)
    report = aggregate(other, window_days=7)
    cia = [h for h in report.source_health if h.source == "cia_findings"][0]
    assert cia.status in ("empty", "unmeasured"), cia


def test_retraction_withdraws_a_finding_without_deleting_it(tmp_path):
    """Boundary: a tombstone -> the promotion view, but not the audit trail.

    Failure class: a refuted finding counting toward promotion frequency and
    breadth forever, with no way to withdraw it.
    """
    findings_dir = tmp_path / "findings"
    ids = []
    for index in (1, 2, 3):
        record = _finding(
            tag="GATE",
            title="gate declared only in prose",
            severity="error",
            session_id=f"r{index}",
            ts=f"2026-09-1{index}T00:00:00+00:00",
        )
        assert append_finding(record, findings_dir=findings_dir)
        ids.append(finding_identity({**record, "severity": "error"}))

    signals, _ = collect_cia_findings(findings_dir, window_days=3650)
    before = [s for s in signals if s.signal_type == "GATE"][0]
    assert before.frequency == 3
    target = before.raw_data["finding_ids"][0]

    assert retract_finding(
        target,
        findings_dir=findings_dir,
        reason="refuted: the gate does refuse, see #1790",
        session_id="r9",
    )
    signals, health = collect_cia_findings(findings_dir, window_days=3650)
    after = [s for s in signals if s.signal_type == "GATE"][0]
    assert after.frequency == 2
    assert after.raw_data["distinct_sessions"] == 2
    assert "retracted" in health.error_message
    # The original line is still on disk — audit history is preserved.
    lines = next(findings_dir.glob("*.jsonl")).read_text().splitlines()
    assert sum(1 for line in lines if target in line) == 2  # record + tombstone

    # Refusing arms: a tombstone naming nothing, or explaining nothing.
    assert retract_finding("", findings_dir=findings_dir, reason="x") is False
    assert retract_finding(target, findings_dir=findings_dir, reason="  ") is False
    with pytest.raises(ValueError, match="absolute"):
        retract_finding(target, findings_dir=Path("relative"), reason="x")


def test_dry_run_render_matches_what_the_real_run_would_emit():
    """Boundary: decisions -> the operator's pre-flight view.

    Failure class: a dry run that renders a DIFFERENT title from the one the
    real run emits is a probe that cannot detect the bug it exists for.
    """
    decisions = decide_promotions(
        [
            _signal("GAMING", CORPUS[0][3]),
            _signal("ORDERING", "state written before the gate ran"),
            _signal("GATE", "x", frequency=1, distinct_sessions=1),
        ],
        CORPUS_ISSUES,
    )
    body = format_dry_run(decisions, digest_body="DIGEST-BODY")
    assert "DRY RUN VERDICT: create=1 append=1 hold=1" in body
    assert body.endswith("DIGEST-BODY")
    for decision in decisions:
        if decision.route in ("create", "append"):
            assert f"would emit title: {planned_title(decision)}" in body
    # Deterministic: the same input renders the same bytes.
    assert format_dry_run(decisions, digest_body="DIGEST-BODY") == body


# =============================================================================
# LAYER 3 — unit: content identity, not observable through the layers above
# =============================================================================


def test_finding_identity_is_content_addressed_not_location_addressed():
    """Two checkouts writing one observation must produce one identity."""
    record = _finding(tag="GATE", title="same observation", session_id="s9")
    assert cia_finding_identity(dict(record)) == finding_identity(dict(record))
    assert finding_identity(dict(record)) == finding_identity(dict(record))
    for field, value in (
        ("session_id", "s10"),
        ("ts", "2026-01-01T00:00:00+00:00"),
        ("title", "different observation"),
    ):
        assert finding_identity({**record, field: value}) != finding_identity(record)
    # Evidence is deliberately NOT part of identity: the same observation
    # re-emitted with a longer blob is the same observation.
    assert finding_identity({**record, "evidence": "x" * 100}) == finding_identity(
        record
    )
    assert MAX_LINES > 0  # the cap the degraded path reports against exists

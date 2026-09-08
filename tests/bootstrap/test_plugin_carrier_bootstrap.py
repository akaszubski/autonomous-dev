"""Plane 2 oracles for the P0-A private-carrier observer.

These tests recompute the observer's facts from raw bytes with ordinary
Python/OS tools — ``json``, ``hashlib``, ``os.lstat``, ``ast``,
``subprocess``, ``yaml`` and ``jsonschema`` — and compare. They never import
the observer's own comparison logic as their answer (``ladder:282``, ``ladder:286``).

``import jsonschema`` and ``import yaml`` at module scope are bare on purpose.
Neither is wrapped in
``try/except ImportError: pytest.skip(..., allow_module_level=True)``: an
unavailable required tool is non-pass (``amendment:236``), so a missing oracle
must surface as a collection error, never as a green skip.

Every deciding check here is watched BOTH refusing and permitting, and every
negative control has a different shape from the positive case it guards — a
probe that cannot fail cannot inform.

Issue: #1760 (P0-A).
"""

from __future__ import annotations

import ast
import contextlib
import copy
import difflib
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import Any, Callable

import jsonschema
import pytest
import yaml

# tests/bootstrap/test_*.py -> bootstrap -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_DIR = REPO_ROOT / "tests" / "bootstrap"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "plugin_carrier"
VALID_DIR = FIXTURE_DIR / "valid"
MANIFEST_PATH = REPO_ROOT / "tests" / "acceptance" / "plugin-carrier-p0.json"
OBSERVER_PATH = BOOTSTRAP_DIR / "observe_claude_execution.py"
SCHEMA_PATH = BOOTSTRAP_DIR / "plugin_carrier_bootstrap.schema.json"
REGISTRY_PATH = FIXTURE_DIR / "mutants.json"
SETTINGS_OVERLAY = FIXTURE_DIR / "claude-observer.settings.json"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GITHUB_ACTIONS_DOC = REPO_ROOT / "docs" / "GITHUB-ACTIONS.md"
NODE_FILE = Path(__file__).resolve()

# No tests/bootstrap/__init__.py exists, so pytest prepends this directory to
# sys.path and the observer imports as a top-level module — the isolated shape
# ladder:286 requires. The explicit insert matches the in-repo idiom in
# tests/unit/lib/test_mutation_killers.py and makes the import work under
# any invocation.
sys.path.insert(0, str(BOOTSTRAP_DIR))

import observe_claude_execution as observer  # noqa: E402

SESSION_UUID = "1f0c9b6a-6f5f-4f3a-9f2b-0d7a5c3e1b40"
SUBPROCESS_TIMEOUT_S = 8   # nodes that drive a harness subprocess: 10s budget
FROZEN_C01_BUDGET_S = 20  # amendment:272 — frozen, not chosen here
# An inner subprocess timeout only informs if it can fire BEFORE the
# pytest-timeout budget of the node that reaches it; otherwise the maintainer
# gets an opaque node timeout instead of the subprocess diagnostic, and the
# number reads as headroom that does not exist. Each of these is below the
# budget of every node that reaches it, which
# test_every_inner_subprocess_timeout_can_fire_inside_its_node_budget checks
# mechanically rather than trusting this comment.
COLLECT_TIMEOUT_S = 15   # nodes that collect: 20s budget
OBSERVER_CLI_TIMEOUT_S = 4  # nodes that drive the observer CLI: 5s budget
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"

# The harness keeps its OWN verdict vocabulary. Importing the observer's set
# would make the observer the judge of its own boundary.
_HARNESS_VERDICT_TOKENS = frozenset(
    {
        "verdict", "pass", "passed", "fail", "failed", "promotion", "promoted",
        "release", "released", "eligible", "eligibility", "approved",
        "certified", "candidate_pass", "bootstrap_pass",
        "private_carrier_released", "standalone_released",
    }
)

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

#: A bare decision prefix (``D10``) as the manifest's prose writes one.
_DECISION_PREFIX_RE = re.compile(r"\bD\d{2}\b")

#: Every decision the observer DECLARES reads the filesystem plane, DERIVED
#: from its own plane map rather than listed here. A decision that starts
#: reading that plane is covered without anyone remembering a second list —
#: the omission that left a disclosure naming two of three for a full round.
_FILESYSTEM_DECISION_IDS: tuple[str, ...] = tuple(
    sorted(
        decision_id
        for decision_id, planes in observer.DECISION_EVIDENCE_PLANES.items()
        if "filesystem" in planes
    )
)


# ==========================================================================
# Independent oracles (harness-owned; share no code with the observer)
# ==========================================================================


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stdlib_allowlist() -> set[str]:
    return set(sys.stdlib_module_names) | set(sys.builtin_module_names) | {"__future__"}


def _harness_static_imports(source: str) -> list[str]:
    """Non-stdlib modules named by an import statement at ANY nesting depth.

    The rule removes a category rather than enumerating members: anything
    outside the standard library is a finding, however deeply nested.
    """
    allowed = _stdlib_allowlist()
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.split(".")[0] not in allowed]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                found.append(f"relative:level{node.level}")
            elif (node.module or "").split(".")[0] not in allowed:
                found.append(node.module or "?")
    return sorted(found)


def _module_level_only_imports(source: str) -> list[str]:
    """A deliberately WEAK scan, kept as an executable exhibit of #1503.

    It inspects only module-level ``Import``/``ImportFrom`` statements. It is
    never used to decide anything; it exists so a test can demonstrate that it
    misses M04 while the real scans catch it. Enumerating known members instead
    of removing a category is exactly how ``plan_gate`` failed open.
    """
    allowed = _stdlib_allowlist()
    found: list[str] = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.split(".")[0] not in allowed]
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in allowed:
                found.append(node.module or "?")
    return sorted(found)


def _harness_dynamic_imports(source: str) -> list[str]:
    """Dynamic-import call targets that are not standard library.

    An unresolvable target counts: in a file that must import stdlib only,
    "the reader cannot tell what this imports" is not permission.
    """
    allowed = _stdlib_allowlist()
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name not in ("import_module", "__import__"):
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            target = node.args[0].value
            if target.split(".")[0] not in allowed:
                found.append(target)
        else:
            found.append("<unresolvable>")
    return sorted(found)


def _verdict_vocabulary_hits(node: Any, pointer: str = "") -> list[str]:
    """Every key or string value carrying pass/fail/release vocabulary."""
    hits: list[str] = []
    if isinstance(node, dict):
        for key in sorted(node):
            child = f"{pointer}/{key}"
            if {t for t in str(key).lower().split("_") if t} & _HARNESS_VERDICT_TOKENS:
                hits.append(child)
            hits += _verdict_vocabulary_hits(node[key], child)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            hits += _verdict_vocabulary_hits(item, f"{pointer}/{index}")
    elif isinstance(node, str):
        if node.strip().lower().replace("-", "_") in _HARNESS_VERDICT_TOKENS:
            hits.append(pointer)
    return hits


def _declares_object_type(node: Any) -> bool:
    """True when ``node`` admits an object instance through its ``type``.

    A UNION reads as an object node too. The previous ``node.get("type") ==
    "object"`` matched only the bare spelling, so a node typed
    ``["object", "array", "string", ...]`` — the shape a verbatim-forwarded
    subject record needs — could carry no closure keyword at all and this scan
    would report nothing. That is the guard-where-the-author-was-looking shape
    the rest of this file exists to refuse, in the file that refuses it.
    """
    declared = node.get("type")
    if isinstance(declared, list):
        return "object" in declared
    return declared == "object"


def _unclosed_object_nodes(node: Any, pointer: str = "#") -> list[str]:
    """Pointers to object-admitting nodes missing either closure keyword."""
    offenders: list[str] = []
    if isinstance(node, dict):
        if _declares_object_type(node):
            if node.get("additionalProperties") is not False or (
                node.get("unevaluatedProperties") is not False
            ):
                offenders.append(pointer)
        for key in sorted(node):
            offenders += _unclosed_object_nodes(node[key], f"{pointer}/{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            offenders += _unclosed_object_nodes(item, f"{pointer}/{index}")
    return offenders


def _schema_object_nodes(node: Any) -> list[dict[str, Any]]:
    """Every object-admitting node in a schema document, at any depth."""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if _declares_object_type(node):
            found.append(node)
        for key in sorted(node):
            found += _schema_object_nodes(node[key])
    elif isinstance(node, list):
        for item in node:
            found += _schema_object_nodes(item)
    return found


def _strip_closure(node: Any) -> None:
    """Remove both closure keywords in place — used to build control schemas."""
    if isinstance(node, dict):
        node.pop("additionalProperties", None)
        node.pop("unevaluatedProperties", None)
        for value in node.values():
            _strip_closure(value)
    elif isinstance(node, list):
        for item in node:
            _strip_closure(item)


def _apply_unified_diff(original: str, patch_text: str) -> str:
    """Apply a single-file unified diff with exact context matching.

    Applied to a tmpdir COPY, never in place, which is why no restoration
    journal exists to go stale (``ladder:80`` dispositions that mechanism).
    A context mismatch raises: a source mutant whose parent bytes moved is a
    bound-input change and must invalidate loudly (``amendment:219``).
    """
    src = original.splitlines(keepends=True)
    out: list[str] = []
    cursor = 0
    lines = patch_text.splitlines(keepends=True)
    index = 0
    hunks = 0

    while index < len(lines):
        match = _HUNK_RE.match(lines[index])
        if not match:
            index += 1
            continue
        start = int(match.group(1)) - 1
        if start < cursor:
            raise ValueError(f"hunk at source line {start + 1} moves backwards")
        out.extend(src[cursor:start])
        cursor = start
        index += 1
        while index < len(lines) and not _HUNK_RE.match(lines[index]):
            body = lines[index]
            if body.startswith("+"):
                out.append(body[1:])
            elif body.startswith("-"):
                if src[cursor] != body[1:]:
                    raise ValueError(f"patch context mismatch at source line {cursor + 1}")
                cursor += 1
            elif body.startswith(" "):
                if src[cursor] != body[1:]:
                    raise ValueError(f"patch context mismatch at source line {cursor + 1}")
                out.append(src[cursor])
                cursor += 1
            elif body.startswith("\\"):
                pass  # "\ No newline at end of file"
            else:
                break
            index += 1
        hunks += 1

    if hunks == 0:
        raise ValueError("patch contained no hunks")
    out.extend(src[cursor:])
    return "".join(out)


def _json_diff_pointers(left: Any, right: Any, pointer: str = "") -> list[str]:
    """JSON pointers at which two documents differ (semantic, not textual)."""
    if isinstance(left, dict) and isinstance(right, dict):
        diffs: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{pointer}/{key}"
            if key not in left or key not in right:
                diffs.append(child)
            else:
                diffs += _json_diff_pointers(left[key], right[key], child)
        return diffs
    if isinstance(left, list) and isinstance(right, list):
        diffs = []
        if len(left) != len(right):
            return [pointer]
        for index, (a, b) in enumerate(zip(left, right)):
            diffs += _json_diff_pointers(a, b, f"{pointer}/{index}")
        return diffs
    return [] if left == right else [pointer]


def _one_change_locations(parent: Path, mutant: Path, kind: str) -> list[str]:
    """Locations at which ``mutant`` differs from ``parent``.

    ``amendment:185-186`` requires one-at-a-time mutants. This measures it
    instead of trusting the registry's prose.
    """
    if kind == "source":
        text = mutant.read_text(encoding="utf-8")
        hunks = [ln for ln in text.splitlines() if _HUNK_RE.match(ln)]
        added = [ln for ln in text.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
        removed = [ln for ln in text.splitlines() if ln.startswith("-") and not ln.startswith("---")]
        if not added and not removed:
            return []
        return [f"{h} (+{len(added)}/-{len(removed)})" for h in hunks]
    if parent.suffix == ".json":
        return _json_diff_pointers(
            json.loads(parent.read_text(encoding="utf-8")),
            json.loads(mutant.read_text(encoding="utf-8")),
        )
    left = parent.read_text(encoding="utf-8").splitlines()
    right = mutant.read_text(encoding="utf-8").splitlines()
    return [
        f"lines {a1 + 1}-{a2}: {tag}"
        for tag, a1, a2, _b1, _b2 in difflib.SequenceMatcher(None, left, right).get_opcodes()
        if tag != "equal"
    ]


# ==========================================================================
# Harness: build worlds and run the observer in a verifier process
# ==========================================================================


def _make_run_root(work: Path, replace: dict[str, Path] | None = None) -> Path:
    run_root = work / "run"
    run_root.mkdir(parents=True, exist_ok=True)
    for source in sorted(VALID_DIR.iterdir()):
        shutil.copy2(source, run_root / source.name)
    for name, source in (replace or {}).items():
        shutil.copy2(source, run_root / name)
    return run_root


def _path_entry(**overrides: Any) -> dict[str, Any]:
    """A COMPLETE ``$defs/path_entry`` record, for probes whose subject is elsewhere.

    The observer now names any forwarded entry that leaves the domain its own
    schema declares, so a synthetic entry carrying three of the seven required
    fields produces a finding of its own. A probe aimed at the discrepancy cap,
    or at a digest comparison, must not also be measuring that: it would be
    measuring two things at once and reporting one number. ``overrides`` is how
    a probe makes exactly one field hostile on purpose.
    """
    return {
        "kind": "file",
        "sha256": "a" * 64,
        "bytes": 0,
        "content_truncated": False,
        "mode": 0o600,
        "uid": 501,
        "acl_state": "UNMEASURED",
        **overrides,
    }


def _canonical_setting_sources() -> list[str]:
    """The canonical settings-source contract, READ from its one home.

    ``expected_settings.setting_sources`` in the frozen manifest is the only
    place this value is written AS THE CONTRACT. Neither the observer nor the
    schema restates it, and every route in this module that feeds the
    observer's ``--setting-sources`` reads it through here, so a manifest edit
    moves every such consumer at once.

    WHAT THIS DOES NOT CLAIM, because an earlier revision claimed it and it was
    false. It said "nothing here restates it — not this module", and this
    module restated the triple as a literal at thirteen places, five of which
    ALSO fed it to ``observer.capture`` — so a manifest edit would have left
    those five comparing against a stale contract while D07 read clean. Those
    five now call this helper. The literals that REMAIN are not the contract
    and are deliberately not routed through here:

    * ARGV-SHAPE fixtures (``_build_child_argv`` and the ``emitted_sources``
      helper) — they assert how a list is comma-JOINED and which option tokens
      are emitted. The value is scaffolding; any three legal sources would do.
    * The observer-CLI permitting arm, which passes the already-joined string
      ``"user,project,local"`` as one argv token, not a list.
    * ``_settings_provenance`` read directly for a byte-truncation cell, which
      never reaches D07.
    * The ONE-SHOT ITERATOR test, which does round-trip the triple through
      ``capture()`` and assert it back out of the packet. That literal is
      load-bearing AS A LITERAL: the assertion's job is to prove a generator
      materialised once survived two consumers, and substituting this helper
      on both sides would compare the manifest to itself and pass over a
      reader that had lost the value entirely.

    The observer's ``--setting-sources`` has no default for a related reason:
    with one, the smoke route never passed the flag, and D07's operand came
    from inside the subject it was supposed to check.
    """
    return list(_case(_manifest(), "P0-C01")["expected_settings"]["setting_sources"])


def _run_observer(
    observer_path: Path,
    run_root: Path,
    *,
    observed_cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
    setting_sources: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run the observer in a process whose ``sys.path`` excludes product code.

    ``-S`` drops ``site`` (so ``site-packages`` is off the path) and ``cwd`` is
    the observer's own directory. ``tests/conftest.py`` injects product paths
    into the pytest process through its ``sys.path.insert`` calls, so an
    in-process ``ImportError`` could never fire — the boundary has to be
    checked from outside.

    ``observed_cwd`` overrides the ``--cwd`` the observer records for the git
    plane, and ``extra_env`` adds variables to the child's environment. Both
    exist so the environment and git planes can be watched PERMITTING as well
    as refusing: the default world here is a throwaway run root that is not a
    git repository and carries none of the ``CLAUDE_*`` variables, so those
    two planes are ``UNMEASURED`` in every other test in this file and their
    fold could never be shown to have a second arm.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    env.update(extra_env or {})
    return subprocess.run(
        [
            sys.executable, "-S", str(observer_path),
            "--cwd", str(observed_cwd or run_root),
            "--run-root", str(run_root),
            "--session-uuid", SESSION_UUID,
            "--settings-overlay", str(SETTINGS_OVERLAY),
            # DERIVED FROM THE MANIFEST, never spelled here. `setting_sources`
            # overrides it so the D07 source-set arms can drive a contract that
            # deviates from the canonical one.
            "--setting-sources", ",".join(
                setting_sources if setting_sources is not None else _canonical_setting_sources()
            ),
            "--debug-file", str(run_root / "debug.log"),
        ],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_S,
        env=env,
        cwd=str(observer_path.parent),
    )


def _packet_from(observer_path: Path, run_root: Path, **kwargs: Any) -> dict[str, Any]:
    proc = _run_observer(observer_path, run_root, **kwargs)
    assert proc.returncode == 0, f"observer exited {proc.returncode}: {proc.stderr[-1500:]}"
    return json.loads(proc.stdout)


def _decision_of(packet: dict[str, Any], decision_id: str) -> dict[str, Any]:
    records = {d["decision_id"]: d for d in packet["comparison"]["decisions"]}
    assert decision_id in records, f"packet declares no {decision_id}"
    return records[decision_id]


def _kill(entry: dict[str, Any], mutant_path: Path, work: Path, validator) -> dict[str, Any]:
    """Run one mutant and report whether its bound decision turned red.

    Source mutants are decided by the harness's own oracles, never by the
    mutated observer's self-report — a mutated subject cannot be the judge of
    its own mutation. Where both the harness and the observer have an opinion,
    a disagreement is reported as a disagreement rather than silently resolved.
    """
    decision_id = entry["decision_id"]
    result: dict[str, Any] = {"id": entry["id"], "decision_id": decision_id, "detail": ""}

    if entry["kind"] == "data":
        run_root = _make_run_root(work, {entry["installs_as"]: mutant_path})
        packet = _packet_from(OBSERVER_PATH, run_root)
        record = _decision_of(packet, decision_id)
        result["killed"] = bool(record["discrepancies"])
        result["detail"] = "; ".join(record["discrepancies"][:2]) or "no discrepancy recorded"
        if entry["installs_as"] == observer.EVIDENCE_PACKET:
            # Independent oracle: jsonschema over the same raw bytes. The
            # observer's stdlib walk and the library must agree.
            errors = list(validator.iter_errors(json.loads(mutant_path.read_text(encoding="utf-8"))))
            result["oracle_agrees"] = bool(errors) == result["killed"]
            result["detail"] += f" | jsonschema errors={len(errors)}"
        return result

    work.mkdir(parents=True, exist_ok=True)
    original = OBSERVER_PATH.read_text(encoding="utf-8")
    mutated = _apply_unified_diff(original, mutant_path.read_text(encoding="utf-8"))
    assert mutated != original, f"{entry['id']}: patch applied but changed nothing"
    target = work / OBSERVER_PATH.name
    target.write_text(mutated, encoding="utf-8")
    shutil.copy2(SCHEMA_PATH, work / SCHEMA_PATH.name)

    if decision_id == "D03_NO_STATIC_PRODUCT_IMPORT":
        found = _harness_static_imports(mutated)
        result["killed"] = bool(found)
        result["detail"] = f"harness_ast static findings={found}"
        return result
    if decision_id == "D04_NO_DYNAMIC_PRODUCT_IMPORT":
        found = _harness_dynamic_imports(mutated)
        result["killed"] = bool(found)
        result["detail"] = f"harness_ast dynamic findings={found}"
        return result
    if decision_id == "D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION":
        run_root = _make_run_root(work)
        packet = _packet_from(target, run_root)
        leaked = [
            error
            for error in validator.iter_errors(packet)
            if error.absolute_path and error.absolute_path[0] == "observation"
        ]
        vocabulary = _verdict_vocabulary_hits(packet.get("observation", {}))
        result["killed"] = bool(leaked) and bool(vocabulary)
        result["detail"] = (
            f"jsonschema observation-plane errors={len(leaked)} "
            f"verdict-vocabulary hits={vocabulary}"
        )
        result["oracle_agrees"] = bool(
            _decision_of(packet, decision_id)["discrepancies"]
        ) == result["killed"]
        return result

    raise AssertionError(f"{entry['id']}: no harness oracle for {decision_id}")


def _registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _bijection_errors(registry: dict[str, Any], declared: tuple[str, ...]) -> list[str]:
    """Errors in the registry <-> DECISION_IDS bijection. Empty means it holds."""
    entries = registry.get("mutants", [])
    mapped = [entry.get("decision_id") for entry in entries]
    problems: list[str] = []
    duplicates = sorted({d for d in mapped if mapped.count(d) > 1})
    if duplicates:
        problems.append(f"decision ids bound by more than one mutant: {duplicates}")
    unmatched = sorted(set(declared) - set(mapped))
    if unmatched:
        problems.append(f"declared decisions with no killing mutant: {unmatched}")
    unknown = sorted(set(mapped) - set(declared))
    if unknown:
        problems.append(f"mutants bound to undeclared decisions: {unknown}")
    if len(entries) != len(declared):
        problems.append(f"{len(entries)} mutants for {len(declared)} declared decisions")
    return problems


def _declared_location_errors(registry: dict[str, Any]) -> list[str]:
    """Registry entries whose declared ``location`` is not the one they change.

    The registry's ``one_change`` field is prose about the NATURE of the edit
    and nothing can check it mechanically. ``location`` is the WHERE, and this
    recomputes it from the raw bytes with :func:`_one_change_locations` — the
    same measurement the frozen node already uses to count changed locations,
    now compared for identity instead of only for cardinality. That gap is how
    a registry can name the wrong plane (``post``
    for ``pre``) and the wrong entry key: the count was right, so nothing
    looked at the location.

    Both mutant kinds are covered rather than one skipped. For a data mutant
    the location is a JSON pointer (or a ``lines A-B: <opcode>`` range for the
    line-oriented ``.jsonl``/``.log`` parents); for a source mutant it is the
    unified-diff hunk header with its added/removed counts, so a hunk that
    slid because the observer's bytes moved turns this red.
    """
    problems: list[str] = []
    for entry in registry.get("mutants", []):
        mutant_id = entry.get("id", "<unnamed>")
        mutant_path = FIXTURE_DIR / entry["mutant"]
        if not mutant_path.is_file():
            problems.append(f"{mutant_id}: mutant file {entry['mutant']} is missing")
            continue
        declared = entry.get("location")
        if not isinstance(declared, str) or not declared:
            problems.append(
                f"{mutant_id}: declares no `location`; an unchecked prose claim is "
                "the defect this field exists to remove"
            )
            continue
        parent_path = (
            OBSERVER_PATH if entry["kind"] == "source" else FIXTURE_DIR / entry["parent"]
        )
        measured = _one_change_locations(parent_path, mutant_path, entry["kind"])
        if len(measured) != 1:
            problems.append(
                f"{mutant_id}: changes {len(measured)} locations {measured[:4]}, "
                "but amendment:185-186 requires exactly one"
            )
            continue
        if declared != measured[0]:
            problems.append(
                f"{mutant_id}: declares location {declared!r} but changes {measured[0]!r}"
            )
    return problems


def _timeout_budget(func) -> int | None:
    """The seconds bound by a ``@pytest.mark.timeout`` on ``func``, or None."""
    for mark in getattr(func, "pytestmark", []):
        if mark.name == "timeout":
            if mark.args:
                return int(mark.args[0])
            if "seconds" in mark.kwargs:
                return int(mark.kwargs["seconds"])
    return None


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _case(manifest: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in manifest["cases"]:
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"manifest declares no {case_id}")


# ==========================================================================
# 1 — the frozen deciding node (P0-C01). Budget 20s is amendment:272's.
# ==========================================================================


@pytest.mark.timeout(FROZEN_C01_BUDGET_S)
def test_observer_has_closed_schema_no_product_import_and_kills_every_decision_mutant(tmp_path):
    """The frozen P0-C01 node. Its name is immutable (``amendment:272``).

    SCOPE — what "kills every decision mutant" means here, stated plainly
    because the frozen name over-promises relative to what the registry
    delivers:

    It MEANS every mutant registered in ``mutants.json`` — each bound 1:1 to a
    decision declared in ``observe_claude_execution.DECISION_IDS`` — turns its
    bound decision red, and the unmutated fixtures turn none red.

    It does NOT establish (a) branch or line coverage of ``reconcile()``: nine
    of twelve mutants mutate fixture DATA, and a branch declaring no decision
    id is invisible to the registry; (b) that ``DECISION_IDS`` is complete
    against real Claude Code behaviour — that is unfalsifiable at A-time and is
    what C07 (``amendment:278``) exists to test; (c) that the recorded facts
    are true of a real Claude run. All A-time evidence is synthetic, which
    ``amendment:203-205`` explicitly permits.
    """
    validator = _validator()
    registry = _registry()

    # --- POSITIVE ARM: the unmutated world turns nothing red --------------
    run_root = _make_run_root(tmp_path / "clean")
    packet = _packet_from(OBSERVER_PATH, run_root)

    schema_errors = sorted(validator.iter_errors(packet), key=str)
    assert not schema_errors, (
        "the observer emitted a packet its own closed schema rejects: "
        + "; ".join(e.message for e in schema_errors[:3])
    )
    assert packet["schema_version"] == observer.SCHEMA_VERSION
    assert packet["candidate_claim"]["read_by_reconcile"] is False

    for record in packet["comparison"]["decisions"]:
        assert record["discrepancies"] == [], (
            f"{record['decision_id']} fired on unmutated fixtures: {record['discrepancies']}"
        )
        assert record["evidence_count"] > 0, (
            f"{record['decision_id']} decided over an empty denominator"
        )
        assert record["observation_status"] == "OBSERVED", (
            f"{record['decision_id']} is {record['observation_status']} on clean fixtures"
        )
    assert packet["comparison"]["discrepancy_count"] == 0
    assert packet["comparison"]["observation_status"] == "OBSERVED"

    # The committed observer imports only the standard library, checked by the
    # harness's own scanners and corroborated by the observer's self-audit.
    source = OBSERVER_PATH.read_text(encoding="utf-8")
    assert _harness_static_imports(source) == []
    assert _harness_dynamic_imports(source) == []
    self_audit = packet["observation"]["source_audit"]
    assert self_audit["runtime_audited"] is True, (
        "the pruned-sys.path runtime audit did not run; its result is UNMEASURED, "
        "not clean"
    )
    assert self_audit["runtime_findings"] == []
    harness_says_clean = not (_harness_static_imports(source) or _harness_dynamic_imports(source))
    observer_says_clean = not (
        self_audit["static_findings"] or self_audit["dynamic_findings"] or self_audit["runtime_findings"]
    )
    assert harness_says_clean == observer_says_clean, (
        "harness and observer disagree about the import boundary — the "
        f"disagreement IS the finding. harness_clean={harness_says_clean} "
        f"observer_clean={observer_says_clean}"
    )

    # --- NEGATIVE ARM: every registered mutant turns its decision red -----
    survivors: list[str] = []
    disagreements: list[str] = []
    multi_change: list[str] = []
    killed_decisions: set[str] = set()

    for entry in registry["mutants"]:
        mutant_path = FIXTURE_DIR / entry["mutant"]
        assert mutant_path.is_file(), f"{entry['id']}: {mutant_path} missing"
        parent_path = (
            OBSERVER_PATH if entry["kind"] == "source" else FIXTURE_DIR / entry["parent"]
        )
        locations = _one_change_locations(parent_path, mutant_path, entry["kind"])
        if len(locations) != 1:
            multi_change.append(f"{entry['id']}: {len(locations)} changes {locations[:4]}")

        outcome = _kill(entry, mutant_path, tmp_path / entry["id"], validator)
        if outcome["killed"]:
            killed_decisions.add(entry["decision_id"])
        else:
            survivors.append(f"{entry['id']} ({entry['decision_id']}): {outcome['detail']}")
        if outcome.get("oracle_agrees") is False:
            disagreements.append(f"{entry['id']}: {outcome['detail']}")

    assert not multi_change, "mutants must change exactly one location: " + " | ".join(multi_change)
    assert not survivors, "surviving mutants: " + " | ".join(survivors)
    assert not disagreements, "oracle disagreement: " + " | ".join(disagreements)
    assert killed_decisions == set(observer.DECISION_IDS), (
        "decisions with no killing mutant: "
        f"{sorted(set(observer.DECISION_IDS) - killed_decisions)}"
    )


# ==========================================================================
# 2 — schema closure. 5s: one file read plus a recursive dict walk.
# ==========================================================================


@pytest.mark.timeout(5)
def test_schema_is_2020_12_and_closes_every_composed_object():
    """Draft 2020-12, closed at every object node, with no verdict vocabulary.

    Draft-07 cannot express ``unevaluatedProperties`` at all, and
    ``additionalProperties`` only inspects properties declared as direct
    siblings in the same schema object, so it cannot close a node whose
    properties arrive through ``$ref``/``allOf``. Both keywords are therefore
    required at every object node.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == DRAFT_2020_12
    jsonschema.Draft202012Validator.check_schema(schema)

    assert _unclosed_object_nodes(schema) == [], (
        "object nodes missing a closure keyword: " + ", ".join(_unclosed_object_nodes(schema))
    )

    # NEGATIVE CONTROL of a different shape: the same walk over a deliberately
    # opened copy must report offenders. A checker that never fails is a
    # decoration.
    opened = copy.deepcopy(schema)
    _strip_closure(opened)
    assert len(_unclosed_object_nodes(opened)) > 5, (
        "the closure walk reported nothing on a fully-opened schema, so it "
        "cannot distinguish a closed schema from an open one"
    )

    # NEGATIVE CONTROL 2, a DIFFERENT SHAPE AGAIN and the one this walk used to
    # be blind to: a node that admits an object through a TYPE UNION. The scan
    # matched only the bare spelling ``"type": "object"``, so a union-typed node
    # could carry no closure keyword and be reported by nothing — and this
    # schema now ships such a node, because a verbatim-forwarded subject record
    # is an object OR a scalar OR an array. Driven both ways on synthetic
    # nodes, so the arms do not depend on which node happens to be in the file.
    union_open = {"type": ["object", "string"], "properties": {"path": {}}}
    union_closed = {
        "type": ["object", "string"],
        "additionalProperties": False,
        "unevaluatedProperties": False,
        "properties": {"path": {}},
    }
    assert _unclosed_object_nodes(union_open) == ["#"], union_open
    assert _unclosed_object_nodes(union_closed) == [], union_closed
    # ...and the SHIPPED union-typed node is one the walk actually reaches, so
    # the arms above are not exercising a shape that is absent from the file.
    assert any(
        _declares_object_type(node) and isinstance(node.get("type"), list)
        for node in _schema_object_nodes(schema)
    ), "no union-typed object node in the schema; delete this control"

    # The complete status vocabulary is three members and carries no pass,
    # candidate, promotion, or release state (amendment:191).
    assert schema["$defs"]["observation_status"]["enum"] == ["OBSERVED", "UNMEASURED", "ERROR"]
    assert list(observer.DECISION_IDS) == sorted(observer.DECISION_IDS)
    hits = _verdict_vocabulary_hits(schema)
    assert hits == [], f"verdict vocabulary in the packet schema: {hits}"

    # CONTROL OF THE CONTROL: derived schema copies must disagree in the
    # predicted directions, otherwise closure is not what rejects the mutants.
    valid_doc = json.loads((VALID_DIR / "packet.json").read_text(encoding="utf-8"))
    m01 = json.loads((FIXTURE_DIR / "mutants/M01-packet-root-extra-key.json").read_text(encoding="utf-8"))
    m02 = json.loads((FIXTURE_DIR / "mutants/M02-packet-composed-extra-key.json").read_text(encoding="utf-8"))

    root_only = copy.deepcopy(schema)
    _strip_closure(root_only["$defs"])

    def rejects(candidate_schema: dict[str, Any], document: Any) -> bool:
        return bool(list(jsonschema.Draft202012Validator(candidate_schema).iter_errors(document)))

    assert not rejects(schema, valid_doc)
    assert rejects(schema, m01) and rejects(schema, m02)
    # A schema closed only at the root catches M01 and lets M02 through — so
    # M02 exercises a closure site reachable only by resolving $ref out of
    # $defs, and is not a restatement of M01.
    assert rejects(root_only, m01)
    assert not rejects(root_only, m02)
    # A fully-opened copy accepts both, so the rejections above come from
    # closure and not from `type` or `required`.
    assert not rejects(opened, m01)
    assert not rejects(opened, m02)


# ==========================================================================
# 3 — registry <-> decisions bijection. 5s: two file reads, two set compares.
# ==========================================================================


@pytest.mark.timeout(5)
def test_every_registry_mutant_maps_to_a_declared_decision_id():
    """A new decision with no killing mutant must fail the build.

    ``ladder:286`` requires only that each deciding observation has at least
    one mutation that turns it red. The strict bijection asserted here is this
    changeset's own choice: "at least one" leaves registry completeness as a
    judgment call, while a set equality is one line of Python.
    """
    registry = _registry()
    assert _bijection_errors(registry, observer.DECISION_IDS) == []
    assert len(registry["mutants"]) == len(observer.DECISION_IDS) == 12
    assert len({entry["id"] for entry in registry["mutants"]}) == 12

    # NEGATIVE CONTROL, different shape: drop one binding from a synthetic copy
    # and feed it to the SAME checker, which must refuse.
    thinned = copy.deepcopy(registry)
    dropped = thinned["mutants"].pop()
    problems = _bijection_errors(thinned, observer.DECISION_IDS)
    assert problems, "the bijection checker accepted a registry missing a decision"
    assert any(dropped["decision_id"] in problem for problem in problems)

    # SECOND NEGATIVE CONTROL, another shape: a decision id nothing declares.
    invented = copy.deepcopy(registry)
    invented["mutants"][0]["decision_id"] = "D99_NOT_DECLARED_ANYWHERE"
    assert any(
        "undeclared" in problem for problem in _bijection_errors(invented, observer.DECISION_IDS)
    )


# ==========================================================================
# 3b — the registry's declared location is the one it actually changes.
#      10s: reads 12 mutants plus their parents, all small; no subprocess.
# ==========================================================================


@pytest.mark.timeout(10)
def test_every_registry_mutant_declares_the_location_it_actually_changes():
    """Frozen prose that names the wrong place is the class this changeset closes.

    THE HOLE THIS FILLS, measured rather than supposed. The frozen node calls
    ``_one_change_locations`` and asserts ``len(...) == 1`` — the COUNT. It
    never looked at the location, so all twelve ``one_change`` strings were
    unchecked claims, and one of them was false: M02 declared
    ``observation.filesystem.post.entries["/proof/root/stream.jsonl"]`` while
    the bytes change ``observation.filesystem.pre.entries["/proof/root"]`` —
    wrong on both the plane and the entry key. The mutant was correct; only the
    prose lied. A count-oriented check is structurally blind to that, exactly
    as a rubric test containing no number is blind to an axis being added.

    THE CLASS, not the instance: every entry now declares ``location``, and it
    is recomputed from raw bytes here. Both kinds are checked — JSON pointers
    and line ranges for the nine data mutants, hunk headers for the three
    source patches — so no kind is exempted into prose.

    WHAT IS STILL PROSE, stated rather than generalised away: ``one_change``
    describes the NATURE of the edit ("add", "alter", "so it has no hook
    partner") and no mechanism checks that narrative. Recorded in the
    manifest's ``scope_limits``.
    """
    registry = _registry()

    # --- CONTROL OF THE INSTRUMENT. A measurement that returned nothing would
    # make every arm below pass for the wrong reason. Positive: a real mutant
    # measures exactly one location. Negative: a file compared with ITSELF
    # measures zero, so the differ is not simply always reporting something.
    m01 = FIXTURE_DIR / "mutants/M01-packet-root-extra-key.json"
    assert _one_change_locations(VALID_DIR / "packet.json", m01, "data") == ["/extra_root_key"]
    assert _one_change_locations(VALID_DIR / "packet.json", VALID_DIR / "packet.json", "data") == []
    assert _one_change_locations(OBSERVER_PATH, OBSERVER_PATH, "source") == []

    # --- The walk must not be vacuous: twelve entries, every one carrying the
    # field. A checker that iterated an empty list would report no problems.
    assert len(registry["mutants"]) == 12
    assert all(isinstance(entry.get("location"), str) and entry["location"]
               for entry in registry["mutants"])

    # --- PERMITTING ARM: the shipped registry agrees with the shipped bytes.
    assert _declared_location_errors(registry) == [], (
        "the registry declares a location it does not change:\n"
        + "\n".join(_declared_location_errors(registry))
    )

    # --- REFUSING ARM 1, a DATA mutant: perturb one declared JSON pointer in a
    # throwaway copy. The bytes on disk are untouched; only the claim moves.
    perturbed = copy.deepcopy(registry)
    target = next(e for e in perturbed["mutants"] if e["id"] == "M06")
    target["location"] = "/observed/0/sha256"
    problems = _declared_location_errors(perturbed)
    assert any(problem.startswith("M06: declares location") for problem in problems), (
        f"the location check PERMITTED a data mutant whose pointer was moved: {problems}"
    )

    # --- REFUSING ARM 2, a DIFFERENT SHAPE: a SOURCE mutant, whose location is
    # a hunk header rather than a pointer. Shifting the header by one line is
    # what a rebased-but-not-re-measured patch looks like; without this arm the
    # check would be proven only for the JSON kind.
    slid = copy.deepcopy(registry)
    patch_entry = next(e for e in slid["mutants"] if e["id"] == "M04")
    assert patch_entry["kind"] == "source"
    patch_entry["location"] = "@@ -1768,6 +1768,7 @@ (+1/-0)"
    problems = _declared_location_errors(slid)
    assert any(problem.startswith("M04: declares location") for problem in problems), (
        f"the location check PERMITTED a source patch whose hunk header slid: {problems}"
    )

    # --- REFUSING ARM 3, a third shape: the field deleted outright. A future
    # mutant added without one must not pass by omission.
    stripped = copy.deepcopy(registry)
    stripped["mutants"][-1].pop("location")
    assert any("declares no `location`" in problem
               for problem in _declared_location_errors(stripped)), (
        "an entry with no declared location was permitted"
    )

    # --- CONTROL OF THE CONTROL: none of the three perturbations touched the
    # shipped bytes, so re-reading the registry from disk must still be green.
    # Without this, the arms above would prove only that the checker can be
    # made to complain, not that it discriminates.
    assert _declared_location_errors(_registry()) == []


# ==========================================================================
# 4 — meta negative control on the kill harness itself. 10s: mutant runs.
# ==========================================================================


@pytest.mark.timeout(10)
def test_kill_harness_refuses_a_registry_whose_mutant_survives(tmp_path):
    """The harness must be able to report SURVIVED, or it proves nothing.

    The synthetic mutant has a DIFFERENT shape from all twelve registered
    ones: it is a real, minimal, one-line edit to a fixture family that no
    decision reads, falsely bound to a decision it cannot possibly disturb. A
    harness that reports it as killed is reporting on its own optimism.
    """
    transcript = VALID_DIR / "transcript.jsonl"
    lines = transcript.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[1] = lines[1].replace(
        "1b1f6c32-3a7e-4b8d-9ca1-6d2ef3041b22", "9999ffff-0000-4000-8000-000000000000"
    )
    decoy = tmp_path / "decoy-transcript.jsonl"
    decoy.write_text("".join(lines), encoding="utf-8")

    # Instrument control: the decoy really is exactly one line different.
    assert len(_one_change_locations(transcript, decoy, "data")) == 1

    entry = {
        "id": "SYNTHETIC-SURVIVOR",
        "kind": "data",
        "parent": "valid/transcript.jsonl",
        "installs_as": "transcript.jsonl",
        "decision_id": "D08_HOOK_TOOL_USE_ID_JOIN",
        "expected": "KILLED",
    }
    outcome = _kill(entry, decoy, tmp_path / "survivor", _validator())
    assert outcome["killed"] is False, (
        "the kill harness reported a decision as red for a mutation that "
        f"decision cannot see: {outcome['detail']}"
    )

    # POSITIVE CONTROL in the same call path: a genuine mutant bound to the
    # same decision must still come back killed, so the harness is not simply
    # unable to detect anything.
    real = {
        "id": "M08",
        "kind": "data",
        "parent": "valid/stream.jsonl",
        "installs_as": "stream.jsonl",
        "decision_id": "D08_HOOK_TOOL_USE_ID_JOIN",
        "expected": "KILLED",
    }
    genuine = _kill(
        real,
        FIXTURE_DIR / "mutants/M08-stream-orphan-tool-use-id.jsonl",
        tmp_path / "genuine",
        _validator(),
    )
    assert genuine["killed"] is True, genuine["detail"]

    # THIRD ARM, different shape again: the weak module-level-only scan kept as
    # an exhibit of #1503 must MISS the dynamic mutant that the real scan
    # catches. A guard that enumerates known members fails open on the member
    # it did not enumerate.
    mutated = _apply_unified_diff(
        OBSERVER_PATH.read_text(encoding="utf-8"),
        (FIXTURE_DIR / "mutants/M04-observer-dynamic-product-import.patch").read_text(encoding="utf-8"),
    )
    assert _module_level_only_imports(mutated) == [], (
        "the weak scan was expected to miss M04; if it now catches it, the "
        "#1503 exhibit no longer demonstrates anything"
    )
    assert _harness_dynamic_imports(mutated) == ["pipeline_state"]


# ==========================================================================
# 5 — inventory truth against os.lstat. 10s: filesystem-bound on slow CI.
# ==========================================================================


@pytest.mark.timeout(10)
def test_observer_records_mode_and_owner_matching_os_stat(tmp_path):
    """``inventory()`` must record ``stat.S_IMODE`` truth and not follow links."""
    root = tmp_path / "proof"
    nested = root / "nested"
    nested.mkdir(parents=True)
    payload = nested / "canary.log"
    payload.write_text("one canary line\n", encoding="utf-8")
    os.chmod(root, 0o700)
    os.chmod(payload, 0o600)

    outside = tmp_path / "outside-the-root.txt"
    outside.write_text("must never be inventoried\n", encoding="utf-8")
    link = root / "escape"
    link.symlink_to(outside)

    result = observer.inventory(root)
    assert result["root_exists"] is True
    assert result["observation_status"] == "OBSERVED"
    entries = result["entries"]
    assert result["entry_count"] == len(entries) > 0

    for path, entry in entries.items():
        st = os.lstat(path)
        assert entry["mode"] == stat.S_IMODE(st.st_mode), f"mode drift at {path}"
        assert entry["uid"] == (st.st_uid if hasattr(os, "geteuid") else None)
        assert entry["acl_state"] == "UNMEASURED"

    # NEGATIVE CONTROL, different shape: a raw st_mode comparison must FAIL for
    # a regular file, which is what proves S_IMODE is load-bearing rather than
    # decorative. Mutant M12 injects exactly this confusion.
    file_entry = entries[os.path.normpath(str(payload))]
    raw = os.lstat(payload).st_mode
    assert file_entry["mode"] == 0o600
    assert file_entry["mode"] != raw, (
        "st_mode and S_IMODE agree for a regular file, so this control cannot "
        "distinguish them"
    )
    assert raw > 0o7777

    # SECOND NEGATIVE CONTROL: the symlink is recorded as a symlink and its
    # target outside the root never enters the inventory.
    assert entries[os.path.normpath(str(link))]["kind"] == "symlink"
    assert os.path.normpath(str(outside)) not in entries
    assert not any(str(outside) in path for path in entries)

    # A root that does not exist is UNMEASURED, never an empty success.
    absent = observer.inventory(tmp_path / "no-such-root")
    assert absent["observation_status"] == "UNMEASURED"
    assert absent["entries"] == {} and absent["root_exists"] is False


# ==========================================================================
# 6 — manifest budget vs the declared marker. 5s: two reads, no I/O.
# ==========================================================================


@pytest.mark.timeout(5)
def test_manifest_budget_matches_the_declared_timeout_marker():
    """20s is bound in three places that must agree: manifest, marker, CI.

    ``--timeout`` is per-test, not per-file — ``.github/workflows/ci.yml`` says
    so in the repo's own words, in the comment above its ``Run smoke tests``
    step — and a ``@pytest.mark.timeout`` marker resolves over
    the command-line default. The CI step passes C01's frozen 20s as the
    default so no unmarked test can silently exceed the frozen budget.
    """
    manifest = _manifest()
    case = _case(manifest, "P0-C01")
    marker_budget = _timeout_budget(
        test_observer_has_closed_schema_no_product_import_and_kills_every_decision_mutant
    )
    assert case["timeout_s"] == marker_budget == FROZEN_C01_BUDGET_S
    assert case["node"].endswith(
        "::test_observer_has_closed_schema_no_product_import_and_kills_every_decision_mutant"
    )
    assert f"--timeout={FROZEN_C01_BUDGET_S}" in case["smoke_command"]

    # NEGATIVE CONTROL, different shape: the extractor reads a per-function
    # marker, not a constant. A supporting test with its own budget must not
    # report C01's number, and an unmarked function must report nothing.
    assert _timeout_budget(test_observer_records_mode_and_owner_matching_os_stat) == 10
    assert _timeout_budget(test_schema_is_2020_12_and_closes_every_composed_object) == 5

    def _unmarked():  # pragma: no cover - never executed, only introspected
        return None

    assert _timeout_budget(_unmarked) is None

    # Every supporting test carries an explicit budget, so none of them can
    # silently inherit C01's frozen number from the command line.
    module = sys.modules[__name__]
    budgets = {
        name: _timeout_budget(getattr(module, name))
        for name in dir(module)
        if name.startswith("test_")
    }
    assert len(budgets) >= 7, f"expected at least 7 test functions, found {len(budgets)}"
    assert all(value is not None for value in budgets.values()), (
        f"tests without an explicit timeout marker: "
        f"{[k for k, v in budgets.items() if v is None]}"
    )


# ==========================================================================
# 7 — manifest digests vs tracked bytes. 10s: ~23 small files.
# ==========================================================================


@pytest.mark.timeout(10)
def test_manifest_digests_match_current_tracked_bytes(tmp_path):
    """Any edit to a bound input invalidates the manifest (``amendment:219``)."""
    manifest = _manifest()
    case = _case(manifest, "P0-C01")
    bound = case["subject_digests"]
    assert isinstance(bound, dict) and bound, "P0-C01 binds no subject digests"

    mismatches = []
    for relative, recorded in sorted(bound.items()):
        subject = REPO_ROOT / relative
        assert subject.is_file(), f"manifest binds a missing path: {relative}"
        actual = _sha256_path(subject)
        if actual != recorded:
            mismatches.append(f"{relative}: recorded {recorded[:12]} actual {actual[:12]}")
    assert not mismatches, (
        "bound inputs changed without a replacement A commit: " + " | ".join(mismatches)
    )

    # The denominator must be complete, not cherry-picked: every tracked byte
    # under the fixture directory, plus the observer, the schema AND THIS NODE
    # FILE. The driver was the one unbound subject, and it is the file whose job
    # is to perform this check: an edit that neutered a guard here changed no
    # bound byte and nothing refused. Measured on the un-bound bytes — neuter
    # this function's body, then corrupt a frozen fixture, and the node reported
    # 77 passed. There is no self-reference: the digest lives in the MANIFEST,
    # which is a separate artifact, so this file reads its own bytes and
    # compares. Any edit here moves the manifest in the same change, which is
    # the point rather than a cost.
    expected = {
        str(OBSERVER_PATH.relative_to(REPO_ROOT)),
        str(SCHEMA_PATH.relative_to(REPO_ROOT)),
        str(NODE_FILE.relative_to(REPO_ROOT)),
    }
    for path in FIXTURE_DIR.rglob("*"):
        if path.is_file():
            expected.add(str(path.relative_to(REPO_ROOT)))
    assert set(bound) == expected, (
        f"unbound subjects: {sorted(expected - set(bound))} | "
        f"bound but absent: {sorted(set(bound) - expected)}"
    )
    assert len(expected) == 23, f"expected 23 bound subjects, found {len(expected)}"

    # NEGATIVE CONTROL, different shape: flip one byte in a copy and the same
    # digest function must disagree with the recorded value.
    tampered = tmp_path / "tampered.json"
    original = SCHEMA_PATH.read_bytes()
    tampered.write_bytes(original.replace(b"OBSERVED", b"0BSERVED", 1))
    assert tampered.read_bytes() != original, "the tamper control changed nothing"
    assert _sha256_path(tampered) != bound[str(SCHEMA_PATH.relative_to(REPO_ROOT))]

    # C02-C08 are immutable FUTURE names: their modules cannot exist at A-time
    # (amendment:263-264), so they bind no digests and are not invoked here.
    for case_id in [f"P0-C0{n}" for n in range(2, 9)]:
        future = _case(manifest, case_id)
        assert future["state"] == "FUTURE"
        assert future["subject_digests"] is None
        assert not (REPO_ROOT / future["node"].split("::")[0]).exists(), (
            f"{case_id} names a module that already exists; P0-A owns no such file"
        )


# ==========================================================================
# Harness: deterministic synthetic streams for the output-bound controls
# ==========================================================================


def _paired_stream_lines(pairs: int, prefix: str = "pad") -> list[str]:
    """``pairs`` tool_use/hook_event couples — deterministic, no orphan.

    Two records per pair, so ``pairs`` couples produce ``2 * pairs`` records.
    Generated at run time rather than committed: a 10,001-line fixture would
    add three quarters of a megabyte to a digest-bound manifest to assert one
    boolean.
    """
    lines: list[str] = []
    for index in range(pairs):
        tool_use_id = f"toolu_{prefix}_{index:06d}"
        lines.append(
            json.dumps({"type": "tool_use", "tool_use_id": tool_use_id, "outcome": "success"})
        )
        lines.append(
            json.dumps(
                {"type": "hook_event", "tool_use_id": tool_use_id, "hook_event_name": "PreToolUse"}
            )
        )
    return lines


def _bypass_line(tool_use_id: str = "toolu_BYPASS") -> str:
    """A tool_use with no hook partner anywhere — the event D08 exists to find."""
    return json.dumps({"type": "tool_use", "tool_use_id": tool_use_id, "outcome": "success"})


def _quiet_debug_log() -> str:
    """A debug log with session lines but no hook lines.

    The generated streams below do not contain the committed fixture's
    ``toolu_01AAA``/``toolu_02BBB``, so the committed debug log would inject
    two hook ids with no stream partner and manufacture orphans that have
    nothing to do with the bound under test.
    """
    return (
        "[2026-09-07T09:15:02.114Z] [DEBUG] session start "
        f"session_id={SESSION_UUID}\n"
        "[2026-09-07T09:15:04.220Z] [DEBUG] session end reason=complete\n"
    )


def _run_root_with_stream(work: Path, stream_lines: list[str]) -> Path:
    """A valid run root whose stream and debug log are replaced wholesale."""
    run_root = _make_run_root(work)
    (run_root / "stream.jsonl").write_text("\n".join(stream_lines) + "\n", encoding="utf-8")
    (run_root / "debug.log").write_text(_quiet_debug_log(), encoding="utf-8")
    return run_root


# ==========================================================================
# 8 — record-cap truncation cannot be laundered into a clean pass.
#     20s: writes ~10k JSON lines three times and runs three observer
#     subprocesses; measured at ~4s locally, 5x headroom for cold CI.
# ==========================================================================


@pytest.mark.timeout(20)
def test_record_truncated_stream_evidence_cannot_report_a_clean_observation(tmp_path):
    """A bypass past the record cap must never read as a clean D08/D09.

    The orphan set is a SYMMETRIC DIFFERENCE — ``(stream - hooks) | (hooks -
    stream)``. It can say "in one and not the other"; it structurally cannot
    say "in neither, because the reader stopped at MAX_STREAM_RECORDS". So the
    only honest answer over clipped evidence is ``UNMEASURED``
    (``amendment:208``: missing or ambiguous evidence is ``UNMEASURED``/
    ``ERROR``). Truncated-but-well-formed is *ambiguous*, not *failed*, which
    is why it degrades to ``UNMEASURED`` rather than ``ERROR``.
    """
    cap = observer.MAX_STREAM_RECORDS

    # --- POSITIVE CONTROL 1: an untruncated clean stream still says OBSERVED.
    clean_root = _run_root_with_stream(tmp_path / "clean", _paired_stream_lines(8))
    clean = _packet_from(OBSERVER_PATH, clean_root)
    clean_d08 = _decision_of(clean, "D08_HOOK_TOOL_USE_ID_JOIN")
    assert clean_d08["discrepancies"] == [], clean_d08["discrepancies"]
    assert clean_d08["observation_status"] == "OBSERVED"
    assert clean_d08["evidence_bounds"] == {"any_bound_truncated": False, "malformed": False, "notes": []}
    assert clean["observation"]["stream"]["record_truncated"] is False
    assert clean["observation"]["stream"]["record_count"] == 16

    # --- POSITIVE CONTROL 2: a bypass BEFORE the cap is still caught. This is
    # the arm that proves the detector works at all; without it, control 3
    # would be indistinguishable from a detector that reports nothing ever.
    before_root = _run_root_with_stream(
        tmp_path / "before", _paired_stream_lines(8) + [_bypass_line()]
    )
    before = _packet_from(OBSERVER_PATH, before_root)
    before_d08 = _decision_of(before, "D08_HOOK_TOOL_USE_ID_JOIN")
    assert any("toolu_BYPASS" in item for item in before_d08["discrepancies"]), (
        f"a bypass inside the cap was not detected: {before_d08}"
    )
    assert before["observation"]["stream"]["record_truncated"] is False

    # --- NEGATIVE CONTROL (the attack): exactly `cap` well-formed records,
    # then the bypass. Every record the reader is allowed to see is a complete
    # pair, so a reader that clips silently sees zero orphans and reports a
    # clean OBSERVED over evidence that hides a hook bypass.
    assert cap % 2 == 0, "the pairing below assumes an even record cap"
    after_lines = _paired_stream_lines(cap // 2) + [_bypass_line()]
    assert len(after_lines) == cap + 1
    after_root = _run_root_with_stream(tmp_path / "after", after_lines)

    # Instrument check on the raw reader before trusting the packet.
    read = observer._read_jsonl(after_root / "stream.jsonl")
    assert len(read.records) == cap, len(read.records)
    assert read.record_truncated is True, (
        "the record cap clipped the input without saying so"
    )
    assert read.byte_truncated is False, (
        "the RECORD cap fired here; if the byte flag is also set, one bound is "
        "setting the other's flag and this test is measuring the wrong thing"
    )
    assert read.unparsable == 0
    assert all(
        record.get("tool_use_id") != "toolu_BYPASS" for record in read.records
    ), "the bypass was inside the cap, so this is not the after-cap case"

    after = _packet_from(OBSERVER_PATH, after_root)
    stream_plane = after["observation"]["stream"]
    assert stream_plane["record_truncated"] is True
    assert stream_plane["byte_truncated"] is False, (
        "the BYTE bound must not be what fires here, or this test is measuring "
        "the wrong bound"
    )
    assert stream_plane["observation_status"] == "UNMEASURED"

    after_d08 = _decision_of(after, "D08_HOOK_TOOL_USE_ID_JOIN")
    assert "toolu_BYPASS" not in json.dumps(after_d08), (
        "the bypass is past the cap by construction; if it appears here the "
        "fixture is wrong, not the observer"
    )
    assert after_d08["evidence_bounds"]["any_bound_truncated"] is True
    assert after_d08["evidence_bounds"]["notes"], "a clipped decision recorded no note"
    assert after_d08["observation_status"] == "UNMEASURED", (
        "a decision over clipped stream evidence reported "
        f"{after_d08['observation_status']}"
    )

    # D09 reads the same clipped stream and must degrade with it: a hook that
    # exited non-zero past the cap is exactly what D09 exists to find.
    after_d09 = _decision_of(after, "D09_HIDDEN_HOOK_NONZERO")
    assert after_d09["evidence_bounds"]["any_bound_truncated"] is True
    assert after_d09["observation_status"] == "UNMEASURED"

    # And the packet as a whole cannot summarise clipped evidence as OBSERVED.
    assert after["comparison"]["observation_status"] != "OBSERVED"
    assert after["observation"]["hooks"]["any_bound_truncated"] is True

    # CONTROL OF THE CONTROL: every decision that declares it reads a bounded
    # plane must be capable of degrading. A decision reading no bounded plane
    # (D05) must NOT have degraded here — otherwise the degradation is global
    # noise rather than evidence-specific.
    d05 = _decision_of(after, "D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION")
    assert d05["evidence_bounds"]["any_bound_truncated"] is False
    assert d05["observation_status"] == "OBSERVED"


# ==========================================================================
# 9 — a depth-bombed JSONL line degrades instead of crashing (CWE-674).
#     10s: a 600 KB write and observer subprocesses.
# ==========================================================================


@pytest.mark.timeout(10)
def test_depth_bombed_jsonl_line_degrades_instead_of_crashing(tmp_path):
    """``RecursionError`` is a ``RuntimeError``, so ``except ValueError`` misses it.

    A single deeply nested line used to take the whole observer process down.
    It must now be counted as undecodable and reported as ``ERROR`` — the
    reader was defeated, which is a failure of the observation and not a
    partial measurement (``amendment:208``).
    """
    depth = 300_000
    bomb = "[" * depth + "]" * depth

    # INSTRUMENT CHECK: the bomb must actually defeat the stdlib parser on this
    # interpreter, or the rest of this test proves nothing at all.
    with pytest.raises(RecursionError):
        json.loads(bomb)
    assert issubclass(RecursionError, RuntimeError), (
        "the premise of this test is that `except ValueError` cannot catch it"
    )
    assert len(bomb) < observer.MAX_EVIDENCE_BYTES, (
        "the bomb must fit inside the byte bound, or the byte bound is what fires"
    )

    # --- POSITIVE CONTROL: ordinary JSONL still parses cleanly.
    clean_root = _run_root_with_stream(tmp_path / "clean", _paired_stream_lines(4))
    clean_read = observer._read_jsonl(clean_root / "stream.jsonl")
    assert len(clean_read.records) == 8
    assert clean_read.unparsable == 0
    assert clean_read.byte_truncated is False and clean_read.record_truncated is False
    clean_packet = _packet_from(OBSERVER_PATH, clean_root)
    assert _decision_of(clean_packet, "D08_HOOK_TOOL_USE_ID_JOIN")["observation_status"] == "OBSERVED"

    # --- NEGATIVE CONTROL: one bombed line among well-formed ones.
    lines = _paired_stream_lines(4)
    lines.insert(3, bomb)
    bombed_root = _run_root_with_stream(tmp_path / "bombed", lines)

    bombed_read = observer._read_jsonl(bombed_root / "stream.jsonl")
    assert bombed_read.unparsable == 1, (
        f"the undecodable line was silently dropped: {bombed_read.unparsable}"
    )
    assert len(bombed_read.records) == 8, "the well-formed lines must still be read"

    # The whole observer must survive the same input end to end.
    proc = _run_observer(OBSERVER_PATH, bombed_root)
    assert proc.returncode == 0, (
        f"the observer crashed on a depth-bombed line: rc={proc.returncode} "
        f"{proc.stderr[-800:]}"
    )
    packet = json.loads(proc.stdout)
    assert packet["observation"]["stream"]["unparsable_records"] == 1
    assert packet["observation"]["stream"]["observation_status"] == "ERROR"
    assert packet["observation"]["hooks"]["evidence_malformed"] is True

    d08 = _decision_of(packet, "D08_HOOK_TOOL_USE_ID_JOIN")
    assert d08["evidence_bounds"]["malformed"] is True
    assert d08["observation_status"] == "ERROR", d08
    assert packet["comparison"]["observation_status"] == "ERROR"

    # CONTROL OF THE CONTROL: a bombed JSON *document* (not JSONL) degrades the
    # same way through the sibling reader, so the two readers agree.
    doc = tmp_path / "bomb.json"
    doc.write_text(bomb, encoding="utf-8")
    doc_read = observer._read_json(doc)
    assert doc_read.document == {} and doc_read.malformed is True


# ==========================================================================
# 10 — forbidden carrier flags refused in every spelling.
#      5s: argv work plus observer CLI runs.
# ==========================================================================


@pytest.mark.timeout(5)
def test_forbidden_carrier_flags_are_refused_in_every_spelling(tmp_path):
    """Refusal is an allowlist first and a blacklist second.

    What was MEASURED against the real parser (claude 2.1.236 at
    ``/opt/homebrew/bin/claude``, 2026-09-07, probe ``claude <FLAG> --help``
    with stdin closed; positive control ``--settings --help`` -> rc=1
    "Settings file not found: --help", negative control
    ``--totally-bogus-flag-xyz --help`` -> rc=0 usage printed):

    * the parser is CASE-SENSITIVE (``--Settings``, ``--Session-Id`` -> rc=0);
    * it accepts NO abbreviations (``--session``, ``--settin`` -> rc=0);
    * it DOES accept the ``=``-joined form (``--settings=zzz`` -> rc=1);
    * an unknown option is NOT rejected (rc=0), so a stray token can be
      absorbed as the positional prompt rather than refused.

    What was INFERRED, not measured: that the same holds for boolean options
    such as ``--safe-mode`` itself. The discriminator above cannot see boolean
    options — control: ``--verbose --help`` prints usage exactly like an
    unknown flag — and every probe that would decide one requires letting the
    CLI proceed to session start, which is not safely decidable. Boolean
    recognition is therefore recorded UNMEASURED and hardened conservatively.

    This test does not invoke the CLI: it asserts OUR refusal, deterministically
    and without a Claude binary (``amendment:245``). The CLI measurement is the
    design input, recorded verbatim beside ``ALLOWED_CHILD_FLAGS``.
    """
    overlay = tmp_path / "settings.json"
    overlay.write_text("{}", encoding="utf-8")
    debug_file = tmp_path / "debug.log"

    def build(**overrides):
        kwargs = {
            "session_uuid": SESSION_UUID,
            "settings_overlay": overlay,
            "setting_sources": ["user", "project", "local"],
            "debug_file": debug_file,
        }
        kwargs.update(overrides)
        return observer._build_child_argv(**kwargs)

    # --- POSITIVE ARM: legitimate values still build, and the argv's option
    # tokens are exactly the frozen allowlist.
    argv = build()
    assert argv[0] == "claude"
    options = [token for token in argv if token.startswith("-")]
    assert set(options) <= set(observer.ALLOWED_CHILD_FLAGS)
    assert set(options) == set(observer.ALLOWED_CHILD_FLAGS), (
        "the allowlist declares an option this argv never emits, so the "
        f"allowlist is not the argv's shape: {sorted(set(observer.ALLOWED_CHILD_FLAGS) - set(options))}"
    )
    assert SESSION_UUID in argv and str(overlay) in argv and str(debug_file) in argv

    # A second legitimate shape: an uppercase UUID is canonicalised, not refused.
    assert observer._build_child_argv(
        session_uuid=SESSION_UUID.upper(),
        settings_overlay=overlay,
        setting_sources=["user"],
        debug_file=debug_file,
    )[-1] == SESSION_UUID

    # --- NEGATIVE ARM: each row is a DIFFERENT bypass shape, and each must
    # raise. Case variants and abbreviations are refused even though the
    # measured parser would not honour them: refusing more than the parser
    # honours is safe, refusing less is the bypass.
    bypasses = [
        ("exact flag as a setting source", {"setting_sources": ["--safe-mode"]}),
        ("'=' joined form", {"setting_sources": ["--safe-mode=1"]}),
        ("mixed case", {"debug_file": Path("--Safe-Mode")}),
        ("upper case", {"settings_overlay": Path("--SAFE-MODE")}),
        ("underscore separator", {"setting_sources": ["--SAFE_MODE"]}),
        ("abbreviation", {"setting_sources": ["--safe"]}),
        ("one-letter abbreviation", {"setting_sources": ["--s"]}),
        ("suffixed variant", {"setting_sources": ["--safe-mode-now"]}),
        ("second forbidden flag", {"setting_sources": ["--no-session-persistence"]}),
        ("second flag abbreviated", {"setting_sources": ["--no-session-persist"]}),
        ("second flag camelCase", {"setting_sources": ["--NoSessionPersistence"]}),
        ("bare value, no dashes", {"setting_sources": ["safe-mode"]}),
        ("hidden behind a legitimate source", {"setting_sources": ["user", "--safe-mode"]}),
        # Riding inside ONE element, past the comma join. Pinned in depth by
        # test_joined_setting_sources_are_validated_as_the_units_the_child_receives.
        ("smuggled behind an embedded comma", {"setting_sources": ["user,--safe-mode"]}),
        ("embedded comma, second flag", {"setting_sources": ["user,--no-session-persistence"]}),
        ("argument injection, not a forbidden flag", {"settings_overlay": Path("-rf")}),
        ("short option as a debug path", {"debug_file": Path("-p")}),
        ("forbidden flag as the session id", {"session_uuid": "--safe-mode"}),
        ("non-uuid session id", {"session_uuid": "not-a-uuid"}),
        ("empty session id", {"session_uuid": ""}),
        ("empty setting sources", {"setting_sources": []}),
        ("empty setting source member", {"setting_sources": [""]}),
    ]
    accepted = []
    for label, overrides in bypasses:
        try:
            build(**overrides)
        except ValueError:
            continue
        accepted.append(label)
    assert not accepted, "bypass shapes the argv builder accepted: " + ", ".join(accepted)

    # --- CONTROL OF THE CONTROL 1: the refusal is not refusing everything.
    # Ordinary paths and sources that merely *look* alarming must still pass.
    for benign in ("/s", "/safe/x", "/tmp/no-session/debug.log", "user"):
        assert observer._forbidden_flag_matches(benign) == [], benign
    assert build(setting_sources=["user"], debug_file=Path("/tmp/safe/debug.log"))

    # --- CONTROL OF THE CONTROL 2: the allowlist and the blacklist cannot
    # contradict. If any permitted option folded onto a forbidden key, the two
    # arms would disagree and one of them would have to be wrong.
    contradictions = [
        flag for flag in observer.ALLOWED_CHILD_FLAGS if observer._forbidden_flag_matches(flag)
    ]
    assert contradictions == [], contradictions

    # --- CONTROL OF THE CONTROL 3: the folding function itself discriminates.
    assert observer._flag_key("--Safe-Mode") == observer._flag_key("--safe_mode=1") == "safemode"
    assert observer._flag_key("--verbose") != observer._flag_key("--safe-mode")

    # capture() inherits the refusal — the guard is on the path callers use,
    # not only on the private helper.
    with pytest.raises(ValueError):
        observer.capture(
            cwd=tmp_path,
            run_root=tmp_path,
            session_uuid=SESSION_UUID,
            settings_overlay=overlay,
            setting_sources=["--safe-mode"],
            debug_file=debug_file,
        )

    # And so does the CLI, which is the copy that actually EXECUTES in CI and
    # in the future canary run. Watched both ways against the real entry point.
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"

    def cli(label: str, sources: str) -> subprocess.CompletedProcess:
        # The run root is named EXPLICITLY. `abs(hash(sources))` was a
        # different directory on every run (PYTHONHASHSEED randomises str
        # hashes per process) and `_make_run_root` uses `exist_ok=True`, so a
        # collision would silently reuse a populated root. Pinned by
        # test_no_run_root_name_is_derived_from_hash.
        run_root = _make_run_root(tmp_path / f"cli_{label}")
        return subprocess.run(
            [
                sys.executable, "-S", str(OBSERVER_PATH),
                "--cwd", str(run_root), "--run-root", str(run_root),
                "--session-uuid", SESSION_UUID,
                "--setting-sources", sources,
                "--settings-overlay", str(SETTINGS_OVERLAY),
                "--debug-file", str(run_root / "debug.log"),
            ],
            capture_output=True, text=True, timeout=OBSERVER_CLI_TIMEOUT_S,
            env=env, cwd=str(OBSERVER_PATH.parent),
        )

    refused = cli("refused", "user,--Safe-Mode")
    assert refused.returncode == 2, refused.stderr[-500:]
    assert "refused" in refused.stderr and "--Safe-Mode" in refused.stderr
    assert refused.stdout.strip() == "", "a refused run must emit no packet"
    assert "Traceback" not in refused.stderr, (
        "a named refusal must not surface as an unhandled traceback"
    )

    permitted = cli("permitted", "user,project,local")
    assert permitted.returncode == 0, permitted.stderr[-500:]
    assert json.loads(permitted.stdout)["comparison"]["decisions"], "no packet on the clean arm"


# ==========================================================================
# 10b — joined values are checked as the units the child parses. 5s: argv
# construction plus one capture() (measured 0.06s), no mutant subprocesses.
# ==========================================================================


@pytest.mark.timeout(5)
def test_joined_setting_sources_are_validated_as_the_units_the_child_receives(monkeypatch, tmp_path):
    """A forbidden flag riding inside one comma-carrying element must be refused.

    THE DEFECT THIS PINS, measured before the fix. ``_build_child_argv``
    validated each supplied ``setting_sources`` ELEMENT and then joined the
    elements with ``,``. An element may carry its own comma, so
    ``"user,--safe-mode"`` is not option-shaped *as an element*, passed the
    element-level refusal untouched, and was emitted as
    ``--setting-sources user,--safe-mode`` — which the child's parser
    decomposes back into the two sources ``user`` and ``--safe-mode``. The
    comment above that loop claimed to prevent exactly this and did not.

    THE CLASS, NOT THE MEMBER. The fix blacklists no comma and enumerates no
    bypass. It derives the checked objects from the EMITTED string via
    :func:`observe_claude_execution._emitted_units`, so the strings that are
    validated and the strings the child receives are the same bytes. Any
    arrangement of commas across any number of elements folds onto the same
    joined value and therefore onto the same units, which is why there is no
    fourth variant left to list.

    NEGATIVE CONTROLS ARE A DIFFERENT SHAPE from the positive case: the
    positive case is a legitimately joined ``"user,project"`` single element,
    and the refusals are single elements whose *interior* is hostile — not the
    multi-element ``["user", "--safe-mode"]`` shape the sibling test already
    covers.
    """
    overlay = tmp_path / "settings.json"
    overlay.write_text("{}", encoding="utf-8")
    debug_file = tmp_path / "debug.log"

    def build(sources):
        return observer._build_child_argv(
            session_uuid=SESSION_UUID,
            settings_overlay=overlay,
            setting_sources=sources,
            debug_file=debug_file,
        )

    def emitted_sources(sources):
        argv = build(sources)
        return argv[argv.index("--setting-sources") + 1]

    # --- REFUSING ARM. Every row is one element carrying its own comma.
    smuggled = [
        ("forbidden flag after a legitimate source", ["user,--safe-mode"]),
        ("second forbidden flag, same shape", ["user,--no-session-persistence"]),
        ("forbidden flag first, source second", ["--safe-mode,user"]),
        ("buried between two legitimate sources", ["user,--safe,project"]),
        ("case-folded and '='-joined inside the comma", ["user,--SAFE_MODE=1"]),
        ("no dashes at all, folded onto the flag", ["user,safe-mode"]),
        ("split across two elements at the seam", ["user,", "--safe-mode"]),
        ("empty unit from a trailing comma", ["user,"]),
    ]
    accepted = []
    for label, sources in smuggled:
        try:
            emitted = emitted_sources(sources)
        except ValueError:
            continue
        accepted.append(f"{label} -> --setting-sources {emitted!r}")
    assert not accepted, "joined-value bypasses the argv builder accepted: " + "; ".join(accepted)

    # --- PERMITTING ARM. A guard that refuses real inputs gets switched off.
    # A legitimately comma-joined element is a REAL supported form: the CLI's
    # own default is the string "user,project,local".
    assert emitted_sources(["user", "project", "local"]) == "user,project,local"
    assert emitted_sources(["user,project"]) == "user,project"
    assert emitted_sources(["user,project,local"]) == "user,project,local"
    assert emitted_sources(["user"]) == "user"
    assert emitted_sources(["user,project", "local"]) == "user,project,local"

    # --- CONTROL OF THE CONTROL 1: the new check can fail. Drop
    # ``--setting-sources`` from the decomposition registry and the very same
    # bypass is accepted again, so it is this registry entry that refuses and
    # not something else in the chain that would have caught it anyway.
    monkeypatch.setattr(observer, "COMMA_DELIMITED_CHILD_FLAGS", frozenset())
    assert emitted_sources(["user,--safe-mode"]) == "user,--safe-mode", (
        "with the decomposition registry emptied the bypass should reappear; it "
        "did not, so this test is not measuring the guard it claims to measure"
    )
    monkeypatch.undo()
    with pytest.raises(ValueError):
        build(["user,--safe-mode"])

    # --- CONTROL OF THE CONTROL 2: the decomposition itself discriminates.
    # A registered flag splits; an unregistered one does not, and that
    # difference is the whole mechanism.
    assert observer._emitted_units("--setting-sources", "user,--safe-mode") == [
        "user,--safe-mode", "user", "--safe-mode",
    ]
    assert observer._emitted_units("--settings", "user,--safe-mode") == ["user,--safe-mode"]

    # --- REGISTRY DRIFT, both directions. The tables cannot grow an entry the
    # emitted argv has never heard of, nor drop one it needs.
    argv = build(["user", "project", "local"])
    value_taking = {
        token
        for index, token in enumerate(argv)
        if token.startswith("-") and index + 1 < len(argv) and not argv[index + 1].startswith("-")
    }
    assert set(observer.CHILD_FLAG_VALUE_LABELS) == value_taking, (
        "the value-label table and the argv's value-taking options disagree: "
        f"unlabelled={sorted(value_taking - set(observer.CHILD_FLAG_VALUE_LABELS))} "
        f"phantom={sorted(set(observer.CHILD_FLAG_VALUE_LABELS) - value_taking)}"
    )
    assert observer.COMMA_DELIMITED_CHILD_FLAGS <= set(observer.ALLOWED_CHILD_FLAGS)
    assert observer.COMMA_DELIMITED_CHILD_FLAGS <= value_taking

    # --- THE SIBLING JOINED-VALUE SURFACE: ``setting_sources`` is an
    # ``Iterable[str]`` read by TWO consumers inside capture() — the argv
    # builder and the settings-provenance plane. A one-shot iterator is
    # materialised once, so both see the same sequence.
    one_shot = (source for source in ("user", "project", "local"))
    observation = observer.capture(
        cwd=tmp_path,
        run_root=tmp_path,
        session_uuid=SESSION_UUID,
        settings_overlay=overlay,
        setting_sources=one_shot,
        debug_file=debug_file,
    )
    recorded_argv = observation["run"]["argv"]
    emitted_value = recorded_argv[recorded_argv.index("--setting-sources") + 1]
    assert emitted_value == "user,project,local"
    # `expected_setting_sources` IS THE FIELD THE ARGV MUST AGREE WITH, and the
    # move off `setting_sources` is this cycle's correction rather than a
    # relaxation. `setting_sources` now carries what the SUBJECT recorded — it
    # is `None` here, because this throwaway run root holds no
    # `settings-sources.json` — and the observer's own argument reaches the
    # packet only through the canonical-contract field. Asserting the old field
    # would have been asserting that the observer still answers a question
    # about the subject on the subject's behalf.
    assert observation["settings"]["expected_setting_sources"] == ["user", "project", "local"], (
        "the packet's provenance plane and its own argv disagree about the "
        "sources of the same run"
    )

    # --- CONTROL OF THE CONTROL 3: the two-traversal pattern this replaced
    # really does lose the value, so the materialisation is load-bearing.
    exhausted = (source for source in ("user", "project", "local"))
    assert list(exhausted) == ["user", "project", "local"]
    assert list(exhausted) == [], "a generator that survives two traversals is not one-shot"


# ==========================================================================
# 11 — manifest output bounds vs the observer's own constants. 5s: two reads.
# ==========================================================================


#: manifest ``output_bounds`` key -> observer constant name. Both directions are
#: asserted, so neither side can grow a bound the other has never heard of.
_BOUND_TO_CONSTANT = {
    "max_evidence_bytes": "MAX_EVIDENCE_BYTES",
    "max_stream_records": "MAX_STREAM_RECORDS",
    "max_inventory_entries": "MAX_INVENTORY_ENTRIES",
    "max_discrepancies_per_decision": "MAX_DISCREPANCIES",
    "max_document_depth": "MAX_DOCUMENT_DEPTH",
}


def _output_bound_errors(bounds: dict[str, Any], module: Any) -> list[str]:
    """Disagreements between a manifest's declared bounds and the real constants."""
    problems: list[str] = []
    declared = {name for name in dir(module) if name.startswith("MAX_")}
    mapped = set(_BOUND_TO_CONSTANT.values())
    if declared != mapped:
        problems.append(
            f"observer MAX_* constants and the mapping disagree: "
            f"unmapped={sorted(declared - mapped)} unknown={sorted(mapped - declared)}"
        )
    for key, constant in sorted(_BOUND_TO_CONSTANT.items()):
        if key not in bounds:
            problems.append(f"manifest declares no {key}")
            continue
        actual = getattr(module, constant, None)
        if bounds[key] != actual:
            problems.append(f"{key}: manifest {bounds[key]!r} != {constant} {actual!r}")
    return problems


@pytest.mark.timeout(5)
def test_manifest_output_bounds_match_the_observer_constants():
    """Every declared bound is cross-checked, exactly as the 20s budget is.

    ``test_manifest_budget_matches_the_declared_timeout_marker`` binds the one
    number the manifest and the code must agree on for the timeout. These four
    were declared as bound facts with nothing checking them — a drift gap, and
    the same gap in the same manifest.
    """
    manifest = _manifest()
    case = _case(manifest, "P0-C01")
    bounds = case["output_bounds"]

    assert _output_bound_errors(bounds, observer) == [], _output_bound_errors(bounds, observer)
    assert bounds["max_evidence_bytes"] == 4 * 1024 * 1024
    assert bounds["max_stream_records"] == 10_000

    # NEGATIVE CONTROL, different shape: feed the SAME checker a manifest whose
    # bound drifted by one, and it must refuse.
    drifted = copy.deepcopy(bounds)
    drifted["max_stream_records"] += 1
    problems = _output_bound_errors(drifted, observer)
    assert any("max_stream_records" in problem for problem in problems), problems

    # SECOND NEGATIVE CONTROL, another shape: a manifest missing a bound.
    missing = {k: v for k, v in bounds.items() if k != "max_inventory_entries"}
    assert any("max_inventory_entries" in p for p in _output_bound_errors(missing, observer))

    # THIRD NEGATIVE CONTROL: a module that grew a bound the manifest never
    # heard of. This is the drift direction a value-by-value check misses.
    class _GrownObserver:
        MAX_EVIDENCE_BYTES = observer.MAX_EVIDENCE_BYTES
        MAX_STREAM_RECORDS = observer.MAX_STREAM_RECORDS
        MAX_INVENTORY_ENTRIES = observer.MAX_INVENTORY_ENTRIES
        MAX_DISCREPANCIES = observer.MAX_DISCREPANCIES
        MAX_BRAND_NEW_BOUND = 7

    assert any("unmapped" in p for p in _output_bound_errors(bounds, _GrownObserver))

    # Every decision declares which bounded planes it reads, so no bound can be
    # carried by a plane that no decision consults (reviewer FINDING-1).
    assert set(observer.DECISION_EVIDENCE_PLANES) == set(observer.DECISION_IDS)
    consulted = {name for names in observer.DECISION_EVIDENCE_PLANES.values() for name in names}
    assert {"stream", "debug", "transcript", "hooks", "settings", "filesystem",
            "schema_audit", "source_audit"} == consulted, sorted(consulted)


# ==========================================================================
# 12 — the byte cap is enforced in BYTES, by every reader that consults it.
#      20s: writes ~20 MB across five files and re-reads each; measured ~1s
#      locally, and cold-CI filesystems are the only reason for the headroom.
# ==========================================================================


@pytest.mark.timeout(20)
def test_byte_bounds_are_enforced_in_bytes_and_every_reader_agrees(tmp_path):
    """``MAX_EVIDENCE_BYTES`` is a byte bound, so it must be counted in bytes.

    A text-mode ``handle.read(n)`` returns *n characters* and ``len()`` counts
    *characters*. Enforcing a byte cap that way lets a UTF-8 stream of 4-byte
    code points run to FOUR TIMES the declared cap while reporting
    ``truncated=False`` — the same evidence-suppression the record cap closes,
    and a direct disagreement with :func:`_sha256_file`, which enforces the
    same constant off a binary handle.

    Measured on the un-fixed bytes, 2.0x the cap of 4-byte code points:
    ``_read_text().byte_truncated=False`` while ``_sha256_file()[2]=True``.

    Both arms are exercised, and the refusing arm has a DIFFERENT SHAPE from
    the one the character implementation already caught: ASCII-over-cap was
    always flagged, so it is the control proving the flag can fire at all;
    multibyte-over-cap is the case that was silently laundered.
    """
    cap = observer.MAX_EVIDENCE_BYTES
    assert cap % 4 == 0, "the 4-byte code point arithmetic below assumes this"

    # --- PERMITTING 1: ordinary ASCII well under the cap is read WHOLE and
    # not flagged. Without this the truncated flag could be always-on.
    small = tmp_path / "small.log"
    body = "[DEBUG] hook PreToolUse exit=0 stdout_bytes=0\n" * 64
    small.write_text(body, encoding="utf-8")
    small_read = observer._read_text(small)
    assert small_read.text == body
    assert small_read.byte_truncated is False
    assert observer._sha256_file(small)[2] is False

    # --- PERMITTING 2: multibyte well under the cap is read whole AND decoded
    # correctly. A byte-counting reader that mangled UTF-8 would be a new bug
    # traded for the old one, so the decode is asserted, not assumed.
    utf8_small = tmp_path / "utf8-small.log"
    utf8_body = "\U0001f600 hook é中文 \U0001f6e1\n" * 64
    utf8_small.write_bytes(utf8_body.encode("utf-8"))
    utf8_read = observer._read_text(utf8_small)
    assert utf8_read.text == utf8_body, "a binary read must still decode UTF-8"
    assert utf8_read.byte_truncated is False

    # --- REFUSING 1 (the shape that ALREADY worked, kept as the control that
    # the flag is reachable): ASCII past the cap.
    ascii_over = tmp_path / "ascii-over.log"
    ascii_over.write_bytes(b"a" * (cap + 4096))
    ascii_read = observer._read_text(ascii_over)
    assert ascii_read.byte_truncated is True
    assert len(ascii_read.text.encode("utf-8")) == cap

    # --- REFUSING 2 (DIFFERENT SHAPE — the defect): 2.0x the cap in bytes,
    # but only cap/2 CHARACTERS, so a character-counting reader sees nothing
    # to flag and hands back a "complete" read of half the evidence.
    multibyte = tmp_path / "multibyte-over.log"
    multibyte.write_bytes("\U0001f600".encode("utf-8") * (cap // 2))
    assert multibyte.stat().st_size == 2 * cap
    mb_read = observer._read_text(multibyte)
    assert mb_read.byte_truncated is True, (
        "a file at 2.0x the declared BYTE cap reported truncated=False: the "
        "cap is being counted in characters, so up to 4x the declared volume "
        "of evidence can be dropped while claiming a complete read"
    )
    assert len(mb_read.text) < cap, "character count must be below the byte cap here"
    assert len(mb_read.text.encode("utf-8")) == cap, "exactly cap BYTES must be kept"

    # --- CROSS-READER AGREEMENT. Two readers over the same constant and the
    # same file must never disagree about whether it was clipped; a
    # disagreement is the finding, not something to resolve silently.
    for path in (small, utf8_small, ascii_over, multibyte):
        text_flag = observer._read_text(path).byte_truncated
        byte_flag = observer._sha256_file(path)[2]
        assert text_flag is byte_flag, (
            f"{path.name}: _read_text says byte_truncated={text_flag} while "
            f"_sha256_file says {byte_flag} over the same bytes and the same cap"
        )
        # _bounded_evidence ORs those two operands into its `byte_truncated`
        # field. That OR is only legitimate while they agree — it composes the
        # SAME cap from two readers — so the agreement is asserted at the same
        # site that consumes it.
        assert observer._bounded_evidence(path, observer._count_jsonl)[
            "byte_truncated"
        ] is byte_flag, f"{path.name}: the published byte flag left the two readers behind"

    # --- DETERMINISTIC BOUNDARY DECODE. The cap cuts a 4-byte code point in
    # half. That must yield the same text every time and must not raise.
    boundary = tmp_path / "boundary.log"
    boundary.write_bytes(b"a" * (cap - 2) + "\U0001f600".encode("utf-8") * 2)
    first = observer._read_text(boundary)
    second = observer._read_text(boundary)
    assert first.byte_truncated is True and second.byte_truncated is True
    assert first.text == second.text, "boundary decode is not deterministic"
    assert first.text.endswith("�"), "a split code point must become U+FFFD"
    assert len(first.text) == cap - 1, (
        "cap-2 ASCII bytes plus one replacement character for the split pair"
    )

    # --- SIBLING READERS. Every reader layered on _read_text inherits the
    # byte cap, so the fix holds for the whole family rather than one call
    # site. The control is the small ASCII file: none of them flags it.
    assert observer._count_lines(multibyte).byte_truncated is True
    assert observer._read_jsonl(multibyte).byte_truncated is True
    assert observer._parse_debug_hooks(multibyte).byte_truncated is True
    over_json = observer._read_json(multibyte)
    assert over_json.byte_truncated is True and over_json.malformed is True

    assert observer._count_lines(small).byte_truncated is False
    assert observer._read_jsonl(small).byte_truncated is False
    assert observer._parse_debug_hooks(small).byte_truncated is False
    assert observer._read_json(small).byte_truncated is False

    # DISCRIMINATION. Every file above is over or under the BYTE cap and none
    # is anywhere near the 10,000-record cap, so no reader may set a record
    # flag here. Without this the byte assertions above would still pass on a
    # reader that set every flag it owns whenever any bound fired.
    assert observer._count_lines(multibyte).record_truncated is False
    assert observer._read_jsonl(multibyte).record_truncated is False
    assert observer._count_lines(small).record_truncated is False
    assert observer._read_jsonl(small).record_truncated is False


# ==========================================================================
# 13 — the transcript plane really participates in D08, and its byte-cap
#      truncation degrades conservatively rather than being ignored.
#      20s: writes a ~4.3 MB transcript and runs two observer subprocesses.
# ==========================================================================


def _aligned_multibyte_transcript(run_root: Path) -> int:
    """Pad ``transcript.jsonl`` past the byte cap, cutting on a line boundary.

    The pad line is exactly 1024 bytes and 1024 divides ``MAX_EVIDENCE_BYTES``,
    so the cap lands between records rather than inside one. That isolates the
    BYTE bound as the only thing degrading the plane: no line is left half
    parsed, so ``unparsable_records`` stays 0 and the status is ``UNMEASURED``
    (incomplete) rather than ``ERROR`` (undecodable).

    Returns the resulting file size in bytes.
    """
    cap = observer.MAX_EVIDENCE_BYTES
    line_len = 1024
    assert cap % line_len == 0
    prefix = '{"type": "pad", "text": "'
    suffix = '"}\n'
    fill = (line_len - len(prefix) - len(suffix)) // 4
    pad_line = (prefix + "\U0001f600" * fill + suffix).encode("utf-8")
    assert len(pad_line) == line_len, len(pad_line)
    json.loads(pad_line.decode("utf-8"))  # the pad must be a real record

    transcript = run_root / "transcript.jsonl"
    original = transcript.read_bytes()
    # Blank lines are skipped by the reader, so they are a safe aligner.
    align = (-len(original)) % line_len
    head = original + b"\n" * align
    assert len(head) % line_len == 0
    body = pad_line * ((cap // line_len) + 8)
    transcript.write_bytes(head + body)
    return transcript.stat().st_size


@pytest.mark.timeout(20)
def test_transcript_byte_truncation_degrades_d08_but_leaves_d09_clean(tmp_path):
    """D08 reads hooks+stream+debug+transcript; the transcript plane must count.

    A plane listed in ``DECISION_EVIDENCE_PLANES`` but never actually consulted
    would be a declaration rather than a mechanism. The discriminating control
    is D09, which reads hooks+stream+debug and NOT the transcript: clipping only
    the transcript must degrade D08 and leave D09 untouched. If both degraded,
    the degradation would be global noise; if neither did, the transcript would
    be decorative.
    """
    # --- POSITIVE CONTROL: untouched fixtures, both decisions clean.
    clean_root = _make_run_root(tmp_path / "clean")
    clean = _packet_from(OBSERVER_PATH, clean_root)
    clean_transcript = clean["observation"]["transcript"]
    assert clean_transcript["byte_truncated"] is False
    assert clean_transcript["record_truncated"] is False
    assert clean_transcript["unparsable_records"] == 0
    assert clean_transcript["observation_status"] == "OBSERVED"
    assert _decision_of(clean, "D08_HOOK_TOOL_USE_ID_JOIN")["observation_status"] == "OBSERVED"
    assert _decision_of(clean, "D09_HIDDEN_HOOK_NONZERO")["observation_status"] == "OBSERVED"

    # --- NEGATIVE CONTROL: only the transcript is pushed past the BYTE cap,
    # and it is pushed with multibyte content, which is the shape a
    # character-counting reader cannot see.
    over_root = _make_run_root(tmp_path / "over")
    size = _aligned_multibyte_transcript(over_root)
    cap = observer.MAX_EVIDENCE_BYTES
    assert size > cap, size

    # Instrument check on the raw reader before trusting the packet: the file
    # is over the byte cap but WELL under the record cap, so this is the byte
    # bound firing and not the record bound.
    raw = observer._read_jsonl(over_root / "transcript.jsonl")
    assert raw.byte_truncated is True
    assert raw.record_truncated is False, (
        "the record cap is untouched here by construction; if the record flag "
        "is set, the byte bound is setting it"
    )
    assert raw.unparsable == 0, "the cut must land between records, not inside one"
    assert 0 < len(raw.records) < observer.MAX_STREAM_RECORDS, len(raw.records)

    over = _packet_from(OBSERVER_PATH, over_root)
    _validator().validate(over)

    plane = over["observation"]["transcript"]
    assert plane["byte_truncated"] is True
    assert plane["record_truncated"] is False, (
        "the BYTE cap clipped this file and the 10,000-record cap was never "
        "approached, so the record flag must stay down. A True here means the "
        "packet is naming the wrong bound, and a reader cannot tell from the "
        "packet which cap actually fired."
    )
    assert plane["unparsable_records"] == 0
    assert plane["observation_status"] == "UNMEASURED", (
        "clipped-but-well-formed evidence is UNMEASURED, never OBSERVED"
    )

    # ISOLATION CONTROL: nothing else was touched, so nothing else may flag.
    for other in ("stream", "debug", "hooks"):
        other_plane = over["observation"][other]
        assert other_plane.get("byte_truncated", False) is False, other
        assert other_plane.get("record_truncated", False) is False, other
        assert other_plane.get("any_bound_truncated", False) is False, other

    d08 = _decision_of(over, "D08_HOOK_TOOL_USE_ID_JOIN")
    assert d08["evidence_bounds"]["any_bound_truncated"] is True
    assert any("transcript" in note for note in d08["evidence_bounds"]["notes"]), (
        f"D08 degraded without naming the transcript plane: {d08['evidence_bounds']}"
    )
    assert d08["observation_status"] == "UNMEASURED", (
        "D08 declares it reads the transcript; a clipped transcript must "
        f"degrade it, got {d08['observation_status']}"
    )

    # DISCRIMINATING CONTROL: D09 does not read the transcript and must stay
    # clean, or the degradation above is global rather than evidence-specific.
    d09 = _decision_of(over, "D09_HIDDEN_HOOK_NONZERO")
    assert "transcript" not in observer.DECISION_EVIDENCE_PLANES["D09_HIDDEN_HOOK_NONZERO"]
    assert d09["evidence_bounds"]["any_bound_truncated"] is False
    assert d09["observation_status"] == "OBSERVED", d09
    assert over["comparison"]["observation_status"] != "OBSERVED"


# ==========================================================================
# 14 — the byte bound and the record bound are reported INDEPENDENTLY.
#      20s: writes ~4.3 MB and runs three observer subprocesses; measured
#      ~2s locally, headroom for cold-CI filesystems.
# ==========================================================================


def _fixed_width_jsonl(path: Path, records: int, width: int) -> int:
    """Write ``records`` valid JSON lines of EXACTLY ``width`` bytes each.

    Fixed width is what makes the byte cap land on a record boundary, which is
    what isolates the byte bound: no line is left half-read, so
    ``unparsable_records`` stays 0 and the only thing degrading the plane is
    the clip itself. Generated at run time -- a 4 MiB fixture would be four
    megabytes of digest-bound bytes committed to assert one boolean.

    Returns the resulting file size.
    """
    prefix = '{"type": "pad", "n": %d, "text": "'
    suffix = '"}\n'
    sample = (prefix % (records - 1)) + suffix
    assert width > len(sample), width
    with open(path, "wb") as handle:
        for index in range(records):
            head = prefix % index
            line = head + "a" * (width - len(head) - len(suffix)) + suffix
            assert len(line.encode("utf-8")) == width, len(line)
            handle.write(line.encode("utf-8"))
    return path.stat().st_size


def _compact_jsonl(path: Path, records: int) -> int:
    """Write ``records`` short valid JSON lines, far under the byte cap."""
    with open(path, "wb") as handle:
        for index in range(records):
            handle.write(('{"type": "pad", "n": %d}\n' % index).encode("utf-8"))
    return path.stat().st_size


@pytest.mark.timeout(20)
def test_byte_and_record_bounds_are_reported_independently(tmp_path):
    """One bound firing must never raise the other bound's flag, either way.

    ``_bounded_evidence`` documents that ``truncated`` (bytes),
    ``record_truncated`` (records) and ``unparsable_records`` are separate
    "because they degrade differently, and because one flag standing for three
    bounds is how a bound gets lost". The code contradicted that docstring:
    ``_read_jsonl`` returned ``read.byte_truncated or record_truncated`` as a
    single ``truncated``, ``_count_jsonl`` forwarded that combined value into
    the RECORD slot, and a 4,195,328-byte file of 4,096 well-formed records --
    with the 10,000-record cap never approached -- published
    ``record_truncated=True``.

    A conflated flag is not a harmless naming problem. It makes the packet
    unable to answer "which cap cut this evidence short", which is the only
    question the flags exist to answer: raising the byte cap fixes one case and
    does nothing for the other, and a reader who cannot tell them apart cannot
    tell which. It also destroys the discriminating power of every downstream
    control, because a probe over a byte-clipped file and a probe over a
    record-clipped file produce identical packets.

    Three cells, and the discrimination is the point -- a control that cannot
    tell byte truncation from record truncation cannot inform:

    ======================  ============  =================  ================
    cell                    ``truncated`` ``record_...``     what it refutes
    ======================  ============  =================  ================
    byte-only, 4,096 recs   True          False              bytes -> record
    record-only, <4 MiB     False         True               record -> bytes
    neither, 3 records      False         False              always-on flags
    ======================  ============  =================  ================

    Conservative degradation is asserted in every clipped cell: separating the
    flags must not weaken the refusal, only stop it misnaming its cause.
    """
    byte_cap = observer.MAX_EVIDENCE_BYTES
    record_cap = observer.MAX_STREAM_RECORDS
    width = 1024
    assert byte_cap % width == 0, "the record-boundary arithmetic assumes this"

    # ---------------- cell A: the BYTE cap alone ----------------
    a_root = _make_run_root(tmp_path / "byte_only")
    a_size = _fixed_width_jsonl(
        a_root / "transcript.jsonl", (byte_cap // width) + 1, width
    )
    assert a_size == byte_cap + width, a_size
    assert (byte_cap // width) + 1 < record_cap, "cell A must not approach the record cap"

    a_raw = observer._read_jsonl(a_root / "transcript.jsonl")
    assert a_raw.byte_truncated is True
    assert a_raw.record_truncated is False, (
        "the byte cap fired and the record cap was never approached, yet the "
        "record flag is set: one bound is raising the other's flag"
    )
    assert len(a_raw.records) == byte_cap // width == 4096, len(a_raw.records)
    assert a_raw.unparsable == 0

    # ---------------- cell B: the RECORD cap alone ----------------
    b_root = _make_run_root(tmp_path / "record_only")
    b_size = _compact_jsonl(b_root / "transcript.jsonl", record_cap + 5)
    assert b_size < byte_cap, b_size

    b_raw = observer._read_jsonl(b_root / "transcript.jsonl")
    assert b_raw.record_truncated is True
    assert b_raw.byte_truncated is False, (
        "the record cap fired on a file well under the byte cap, yet the byte "
        "flag is set: the conflation runs in this direction too"
    )
    assert len(b_raw.records) == record_cap, len(b_raw.records)
    assert b_raw.unparsable == 0

    # ---------------- cell C: NEITHER cap ----------------
    c_root = _make_run_root(tmp_path / "neither")
    c_size = _compact_jsonl(c_root / "transcript.jsonl", 3)
    assert c_size < byte_cap
    c_raw = observer._read_jsonl(c_root / "transcript.jsonl")
    assert c_raw.byte_truncated is False and c_raw.record_truncated is False
    assert len(c_raw.records) == 3

    # ---------------- the same three cells, through the emitted packet ------
    #
    # The reader assertions above are in-process. A packet is what a third
    # party actually reads, and the conflation lived in the path BETWEEN the
    # reader and the packet (_count_jsonl -> _bounded_evidence), so the packet
    # is where it has to be refuted.
    expected = {
        "byte_only": (a_root, True, False, 4096, "UNMEASURED"),
        "record_only": (b_root, False, True, record_cap, "UNMEASURED"),
        "neither": (c_root, False, False, 3, "OBSERVED"),
    }
    packets: dict[str, dict[str, Any]] = {}
    for name, (root, want_bytes, want_records, want_count, want_status) in expected.items():
        packet = _packet_from(OBSERVER_PATH, root)
        _validator().validate(packet)
        packets[name] = packet
        plane = packet["observation"]["transcript"]
        assert plane["byte_truncated"] is want_bytes, (
            f"{name}: byte_truncated={plane['byte_truncated']}"
        )
        assert plane["record_truncated"] is want_records, (
            f"{name}: record_truncated={plane['record_truncated']}, expected "
            f"{want_records}. The two bounds are separate fields precisely so "
            "a reader can tell which cap fired."
        )
        assert plane["unparsable_records"] == 0, name
        assert plane["record_count"] == want_count, (name, plane["record_count"])
        assert plane["observation_status"] == want_status, (name, plane)

        # ISOLATION: only the transcript was touched in every cell, so no other
        # bounded plane may flag. Without this, a packet that set every flag
        # everywhere would satisfy the cells above in the clipped rows.
        for other in ("stream", "debug"):
            other_plane = packet["observation"][other]
            assert other_plane["byte_truncated"] is False, (name, other)
            assert other_plane["record_truncated"] is False, (name, other)

    # ---------------- conservative degradation survives the separation ------
    #
    # Naming the bound correctly must not soften the refusal. D08 declares it
    # reads the transcript, so EITHER cap clipping the transcript degrades it;
    # D09 does not read the transcript and must stay clean in both clipped
    # cells, or the degradation is global noise rather than evidence-specific.
    assert "transcript" in observer.DECISION_EVIDENCE_PLANES["D08_HOOK_TOOL_USE_ID_JOIN"]
    assert "transcript" not in observer.DECISION_EVIDENCE_PLANES["D09_HIDDEN_HOOK_NONZERO"]
    for name in ("byte_only", "record_only"):
        d08 = _decision_of(packets[name], "D08_HOOK_TOOL_USE_ID_JOIN")
        assert d08["evidence_bounds"]["any_bound_truncated"] is True, (name, d08)
        assert any("transcript" in note for note in d08["evidence_bounds"]["notes"]), (
            f"{name}: D08 degraded without naming the transcript plane: {d08}"
        )
        assert d08["observation_status"] == "UNMEASURED", (name, d08)
        d09 = _decision_of(packets[name], "D09_HIDDEN_HOOK_NONZERO")
        assert d09["evidence_bounds"]["any_bound_truncated"] is False, (name, d09)
        assert d09["observation_status"] == "OBSERVED", (name, d09)
        assert packets[name]["comparison"]["observation_status"] != "OBSERVED", name

    # PERMITTING ARM. The unclipped cell must reach OBSERVED on both decisions,
    # or every refusal above is indistinguishable from a decision that can
    # never be clean.
    clean = packets["neither"]
    assert _decision_of(clean, "D08_HOOK_TOOL_USE_ID_JOIN")["observation_status"] == "OBSERVED"
    assert _decision_of(clean, "D09_HIDDEN_HOOK_NONZERO")["observation_status"] == "OBSERVED"


# ==========================================================================
# 15 — the manifest's declared node count is pinned to what pytest collects.
#      20s: ONE `pytest --collect-only` subprocess.
# ==========================================================================


#: One ``-q --collect-only`` node line: an optional path, ``::``, and the node.
#: The path group is allowed to be EMPTY because pytest really does print
#: ``::test_a`` for some targets, and a pattern that could not match that form
#: would DROP those lines instead of refusing them.
_COLLECTED_NODE_RE = re.compile(r"^(?P<path>\S*)::(?P<node>\S+)\s*$")


def _collect_node_counts(targets: list[Path], attribute_to: list[Path]) -> dict[Path, int]:
    """Nodes pytest collects, per FILE, from ONE interpreter start.

    This is the same denominator CI's JUnit ``tests=`` attribute reports, so
    the manifest number is pinned to collection reality rather than to a
    source-text regex. A test renamed out of collection, or a file that fails
    to import, changes this number; a regex over ``def test_`` would not.

    ONE SUBPROCESS FOR ALL TARGETS, because the cost here is not collection.
    This node file collects 90 tests in 0.08s inside a run costing ~3.6s wall,
    so ~3.6s is fixed interpreter, conftest and plugin start-up, paid once per
    INVOCATION regardless of what is collected. The control that establishes
    that: the SAME target with every node deselected still costs ~3.6s. Two
    invocations left this frozen node at ~7.2s against a 20s budget -- 2.8x
    margin (measured directly, three back-to-back pairs: 7.21s, 7.22s, 7.26s),
    which a 2-core runner at ~3x slower turns into a permanently red gate. Merging them restores the margin without weakening anything the
    caller proves.

    A POINT ESTIMATE AND DELIBERATELY NO INTERVAL. Two earlier revisions wrote
    ranges here -- "3.75-3.82s" for the run and "3.71-3.76s" for the deselected
    control -- and BOTH were a five-run min/max reported as if it were the
    population range. Re-measured across 25 runs on one machine, the run spans
    2.98-5.23s about a median of ~3.57s, and ZERO of the 25 fell inside the
    stated 3.75-3.82s; the deselected control measured 3.57-3.65s over five
    runs, none of it inside the stated 3.71-3.76s either. Both intervals
    excluded the mode they were supposed to describe, and understated the
    spread by roughly an order of magnitude while looking more precise than the
    point estimate that replaced them.
    A wall-clock figure on a shared machine has no stable tail, so the honest
    form is one significant figure and no bound. The inference is unchanged and
    stronger for it: fixed per-invocation cost dominates, and collection is
    noise against it.

    ``targets`` AND ``attribute_to`` ARE DIFFERENT LISTS, and the reason is
    measured rather than stylistic. Pytest's printed path depends on HOW a file
    was reached: this node file, inside rootdir, prints as
    ``tests/bootstrap/test_plugin_carrier_bootstrap.py``; a file OUTSIDE rootdir
    reached through its DIRECTORY prints as its bare basename
    (``test_counter_positive_control.py``); and the same file passed DIRECTLY on
    the command line prints with NO PATH AT ALL (``::test_a``). Only the first
    two forms can be attributed, so out-of-rootdir files are reached through
    their directory while the counts are still kept PER FILE.

    ATTRIBUTION IS BY PATH SUFFIX, not by prefix: a printed path attributes to a
    file when that file's absolute path ends with it on a separator boundary,
    which reads both attributable forms and cannot match a sibling that merely
    shares a name prefix.

    Every entry of ``attribute_to`` gets a key, seeded at zero, so a file
    contributing NOTHING is answered with an absence rather than a ``KeyError``
    -- a negative control file is exactly such a file, and it must be assertable.

    Three ways this could lie, all refused rather than absorbed: a node printed
    with no path cannot be attributed at all; a printed path matching NO file
    would be an undercount nobody could see; and one matching TWO files would be
    a double count.
    """
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", *[str(target) for target in targets],
            "--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        timeout=COLLECT_TIMEOUT_S,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode in (0, 5), (
        f"collection failed ({proc.returncode}): {proc.stdout[-2000:]}{proc.stderr[-1000:]}"
    )
    resolved = {path: str(path.resolve()) for path in attribute_to}
    counts: dict[Path, int] = {path: 0 for path in attribute_to}
    for line in proc.stdout.splitlines():
        match = _COLLECTED_NODE_RE.match(line.strip())
        if match is None:
            continue
        printed = match.group("path")
        assert printed, (
            f"pytest printed the collected node {line.strip()!r} with no path, "
            "so it cannot be attributed to a file; reach that target through "
            "its directory instead of naming the file directly"
        )
        owners = [
            path
            for path, absolute in resolved.items()
            if absolute == printed or absolute.endswith(os.sep + printed)
        ]
        assert len(owners) == 1, (
            f"collected node {line.strip()!r} attributes to {len(owners)} of "
            f"the {len(attribute_to)} files; the count would be wrong either way"
        )
        counts[owners[0]] += 1
    return counts


@pytest.mark.timeout(20)
def test_manifest_declared_node_count_equals_pytest_collected_count(tmp_path):
    """One home for the count, and it cannot drift out of agreement silently.

    ``collection_completeness.expected_test_count`` in the acceptance manifest
    is the ONLY place the frozen node file's test count is written. CI reads it
    from there and compares with ``==``; this test pins it to what pytest
    actually collects. So:

    * delete or rename a frozen test  -> collected < declared -> this refuses,
      and CI's JUnit re-read refuses independently;
    * add a test without updating the manifest -> collected > declared -> this
      refuses, and CI refuses independently;
    * edit the manifest without touching the file -> this refuses.

    A floor (``tests>=N``) permitted the first case all the way down to N.
    """
    declared = int(
        _case(_manifest(), "P0-C01")["collection_completeness"]["expected_test_count"]
    )
    completeness = _case(_manifest(), "P0-C01")["collection_completeness"]
    assert completeness["rule"] == "exact"
    assert completeness["node_file"] == str(NODE_FILE.relative_to(REPO_ROOT))

    # THE SUBJECT AND BOTH INSTRUMENT CONTROLS IN ONE INTERPRETER START.
    # Collection itself costs 0.08s; interpreter, conftest and plugin start-up
    # cost ~3.6s and are paid PER INVOCATION. Two invocations left this frozen
    # 20s node at ~7.2s -- 2.8x margin, which a slower CI runner erases.
    #
    # POSITIVE CONTROL: three collectable tests must be counted.
    # NEGATIVE CONTROL, a different shape: a second file whose functions are
    # named out of collection must contribute ZERO. A counter that always
    # returned a plausible positive number, or one that counted `def` lines
    # rather than collected nodes, fails this pair. Merging the invocations
    # must not merge the ANSWERS, so the two control files are separate targets
    # and are asserted separately -- a directory target would have hidden the
    # negative control inside the positive control's number.
    controls = tmp_path / "controls"
    controls.mkdir()
    positive = controls / "test_counter_positive_control.py"
    positive.write_text(
        "def test_a():\n    assert True\n"
        "def test_b():\n    assert True\n"
        "def test_c():\n    assert True\n",
        encoding="utf-8",
    )
    negative = controls / "test_counter_negative_control.py"
    negative.write_text(
        "def helper_a():\n    assert True\n"
        "def not_a_test_b():\n    assert True\n"
        "def also_not_collected_test():\n    assert True\n",
        encoding="utf-8",
    )

    # The controls are reached through their DIRECTORY, because a file named
    # directly on the command line prints as `::test_a` with no path and could
    # not be attributed. The counts stay PER FILE regardless.
    counts = _collect_node_counts([NODE_FILE, controls], [NODE_FILE, positive, negative])

    assert counts[positive] == 3, (
        f"the positive control must contribute its three collectable tests, "
        f"not {counts[positive]}"
    )
    # An ABSENCE, read from a seeded key rather than from a missing one: a bare
    # lookup on a target that printed no line would raise KeyError, which is an
    # error and not the measurement this control exists to make.
    assert counts[negative] == 0, (
        f"the counter must count COLLECTED nodes: the negative control's three "
        f"`def` lines are named out of collection, yet it contributed "
        f"{counts[negative]}"
    )

    collected = counts[NODE_FILE]
    assert collected == declared, (
        f"the manifest declares {declared} frozen nodes but pytest collects "
        f"{collected}. Update collection_completeness.expected_test_count in "
        f"{MANIFEST_PATH.relative_to(REPO_ROOT)} — it is the single home for "
        "this number and CI reads it from there."
    )


# ==========================================================================
# 16 — the CI completeness gate itself, run as the bytes CI runs.
#      15s: short interpreter starts over the extracted command.
# ==========================================================================


def _ci_junit_guard_command() -> str:
    """The EXACT ``python -c`` guard from the P0-A step, read from ci.yml.

    Read from the copy that EXECUTES rather than restated here. A guard this
    test only paraphrased would keep passing after ci.yml changed.
    """
    lines = [
        line.strip()
        for line in CI_WORKFLOW.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("python -c ") and "p0a-results.xml" in line
    ]
    assert len(lines) == 1, f"expected exactly one P0-A JUnit guard line, found {len(lines)}"
    parts = shlex.split(lines[0])
    assert parts[:2] == ["python", "-c"] and len(parts) == 3, parts
    return parts[2]


def _junit_xml(tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite name="pytest" '
        f'errors="{errors}" failures="{failures}" skipped="{skipped}" '
        f'tests="{tests}" time="0.5"></testsuite></testsuites>'
    )


def _run_ci_guard(code: str, workdir: Path, declared: int, xml: str) -> subprocess.CompletedProcess:
    """Run the extracted guard against a synthetic manifest and JUnit report.

    The report is written to a scratch RUNNER_TEMP rather than to ``workdir``:
    the shipped step writes it outside the working tree, and a harness that
    still put it in the cwd would be driving a path the guard no longer reads.
    """
    acceptance = workdir / "tests" / "acceptance"
    acceptance.mkdir(parents=True, exist_ok=True)
    (acceptance / "plugin-carrier-p0.json").write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "P0-C00-DECOY",
                        "collection_completeness": {"expected_test_count": 999},
                    },
                    {
                        "case_id": "P0-C01",
                        "collection_completeness": {"expected_test_count": declared},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    runner_temp = workdir / "runner_temp"
    runner_temp.mkdir(parents=True, exist_ok=True)
    (runner_temp / P0A_JUNIT_ARTIFACT).write_text(xml, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_S,
        cwd=str(workdir),
        env={**os.environ, "RUNNER_TEMP": str(runner_temp)},
    )


@pytest.mark.timeout(15)
def test_ci_completeness_gate_refuses_partial_collection_and_permits_the_full_count(tmp_path):
    """The CI gate must be EXACT, and it must be watched refusing and permitting.

    The defect this closes: the guard asserted ``tests>=7`` while the frozen
    node file carried eleven tests, so four frozen tests could be deleted,
    renamed out of collection, or silently fail to collect and the step would
    still report green. A floor is not a completeness gate.

    Every arm below runs the byte-for-byte command extracted from ci.yml, in a
    scratch directory holding a synthetic manifest and a synthetic JUnit report
    — the executing copy, not a paraphrase.
    """
    code = _ci_junit_guard_command()

    # --- STATIC: the stale floor cannot come back, and the count is not
    # hardcoded in the workflow at all.
    assert ">=" not in code, f"the JUnit guard reintroduced a floor: {code}"
    assert "t==exp" in code.replace(" ", ""), code
    assert "tests/acceptance/plugin-carrier-p0.json" in code, (
        "the guard must read the expected count from the manifest, not carry "
        "its own copy of the number"
    )
    # No CONCRETE numeric floor may survive on any P0-A surface. The pattern
    # matches `t>=7` and `tests>=7` but not the prose `tests>=N` that records
    # why the floor was withdrawn, and not a version pin like `pytest>=8`
    # (no word boundary before `test` inside `pytest`).
    floor = re.compile(r"\b(?:t|tests?)\s*>=\s*\d")
    for surface in (CI_WORKFLOW, GITHUB_ACTIONS_DOC):
        hit = floor.search(surface.read_text(encoding="utf-8"))
        assert hit is None, f"{surface.name} still carries a numeric floor: {hit.group(0)!r}"
    # Control of that instrument: it must fire on the exact withdrawn strings,
    # or "no hit" above would mean nothing.
    assert floor.search("sys.exit(0 if (t>=7 and f==0) else 1)") is not None
    assert floor.search("the JUnit read additionally asserts `tests>=7`") is not None
    assert floor.search("A floor (`tests>=N`) would have permitted") is None
    assert floor.search("pip install 'pytest>=8'") is None

    # A SYNTHETIC count, deliberately different from this file's real one, so
    # the arms below prove the guard reads the manifest it is given rather than
    # happening to agree with the repository. 11 is also the count at which the
    # withdrawn `tests>=7` floor would have permitted four deletions.
    declared = 11
    assert declared != _case(_manifest(), "P0-C01")["collection_completeness"][
        "expected_test_count"
    ], "the synthetic count must differ from the real one for this to prove anything"

    # --- PERMITTING ARM: the exact declared count, nothing else wrong.
    ok = _run_ci_guard(code, tmp_path / "ok", declared, _junit_xml(declared))
    assert ok.returncode == 0, f"the gate refused a complete run: {ok.stdout}{ok.stderr}"
    assert f"tests={declared} expected={declared}" in ok.stdout, ok.stdout

    # --- REFUSING ARMS. Each is a distinct shape, and the first is the defect
    # the old floor permitted: silent deletion of frozen tests.
    refusing = {
        "one frozen test deleted": _junit_xml(declared - 1),
        "four frozen tests deleted (the old floor permitted this)": _junit_xml(7),
        "a test added without updating the manifest": _junit_xml(declared + 1),
        "zero collection": _junit_xml(0),
        "a skip laundered past the exit code": _junit_xml(declared, skipped=1),
        "a failure": _junit_xml(declared, failures=1),
        "a collection error": _junit_xml(declared, errors=1),
    }
    for label, xml in refusing.items():
        work = tmp_path / re.sub(r"\W+", "_", label)
        result = _run_ci_guard(code, work, declared, xml)
        assert result.returncode != 0, (
            f"the CI gate PERMITTED {label}: rc={result.returncode} {result.stdout}"
        )

    # --- CONTROL OF THE CONTROL: the gate reads the count from the manifest,
    # so moving the manifest number moves the verdict. A guard with the number
    # baked in would be indistinguishable from one that reads it.
    moved = _run_ci_guard(code, tmp_path / "moved", 7, _junit_xml(7))
    assert moved.returncode == 0, moved.stdout + moved.stderr
    assert "expected=7" in moved.stdout, moved.stdout


# ==========================================================================
# 17 — the CLASS guard: no truncation flag may carry a bound it does not name.
#      20s: AST parses of a ~4,550-line module plus temp copies.
# ==========================================================================
#
# A field named for one cap must never silently carry another. This reads the
# observer's AST, finds every site that BINDS a truncation-flag name, and holds
# each one to the registry the module declares about itself. It is not a
# re-check of known sites: the negative controls below add BRAND NEW functions
# that exist nowhere in the shipped module, and the guard must turn red on each.

_FLAG_TAIL_TOKENS = ("truncated", "clipped")


def _is_flag_name(name: Any) -> bool:
    """True for a truncation-flag-shaped identifier or object key.

    Deliberately shaped by the LAST underscore segment rather than by a
    substring: ``truncation_contract`` and ``_TRUNCATION_KEYS`` are prose and a
    key list, not flags, and a substring rule would drag both in and make the
    guard's output unreadable. Leading underscores are stripped so a
    deliberately discarded ``_byte_truncated`` is held to the same rule as the
    value it discards.
    """
    if not isinstance(name, str) or not name:
        return False
    bare = name.lstrip("_")
    if not bare or bare != bare.lower():
        return False
    return bare.split("_")[-1] in _FLAG_TAIL_TOKENS


def _flag_key(name: str) -> str:
    return name.lstrip("_")


class _FlagBinding:
    """One site that binds a truncation-flag name, with what flowed into it."""

    def __init__(self, name: str, lineno: int, flags: set[str], bounds: set[str],
                 literal_true: bool, guard_bounds: set[str]) -> None:
        self.name = _flag_key(name)
        self.lineno = lineno
        self.flags = flags
        self.bounds = bounds
        self.literal_true = literal_true
        self.guard_bounds = guard_bounds

    def __repr__(self) -> str:  # pragma: no cover - failure output only
        return f"<{self.name} @L{self.lineno} flags={sorted(self.flags)} bounds={sorted(self.bounds)}>"


class _Taint:
    """What a value carries: which flags and bounds it reads, and bare ``True``.

    The unit of the ALIAS MAP. Keying provenance on the operand being
    flag-shaped is enumeration of members, and a one-word rename walks straight
    past it: ``entry_truncated = entry_truncated or cut`` is the
    ``inventory()`` defect with ``file_truncated`` renamed to ``cut``, and a
    matcher that looks for flag-shaped operands permits it. Taint travels with
    the VALUE instead of the name, so the rename carries the provenance along.
    """

    __slots__ = ("flags", "bounds", "literal_true")

    def __init__(self, flags: set[str], bounds: set[str], literal_true: bool = False) -> None:
        self.flags = set(flags)
        self.bounds = set(bounds)
        self.literal_true = literal_true

    def __bool__(self) -> bool:
        return bool(self.flags or self.bounds or self.literal_true)

    def union(self, other: "_Taint") -> "_Taint":
        return _Taint(self.flags | other.flags, self.bounds | other.bounds,
                      self.literal_true or other.literal_true)

    def key(self) -> tuple[frozenset[str], frozenset[str], bool]:
        return frozenset(self.flags), frozenset(self.bounds), self.literal_true

    def __repr__(self) -> str:  # pragma: no cover - failure output only
        return f"<taint flags={sorted(self.flags)} bounds={sorted(self.bounds)}>"


_EMPTY_TAINT = _Taint(set(), set(), False)


class _ReturnInfo:
    """What a module-local function hands back, whole and per tuple slot.

    ``_sha256_file`` returns ``(sha256, byte_count, byte_truncated)``. Without
    this, unpacking it into any name at all produces a value the guard cannot
    attribute, which is exactly the hole a rename exploits.
    """

    __slots__ = ("whole", "slots")

    def __init__(self, whole: _Taint, slots: dict[int, _Taint]) -> None:
        self.whole = whole
        self.slots = slots

    def key(self) -> tuple[Any, ...]:
        return (self.whole.key(),
                tuple(sorted((index, taint.key()) for index, taint in self.slots.items())))


_EMPTY_RETURN = _ReturnInfo(_EMPTY_TAINT, {})

#: Bound on the return-provenance fixpoint. Taint only ever grows (every merge
#: is a union), so the walk is monotone and converges; the cap exists so a
#: pathological module cannot hang the guard instead of failing it.
_RETURN_TAINT_PASSES = 6


def _expression_taint(node: ast.AST, bound_names: set[str],
                      aliases: dict[str, _Taint] | None = None,
                      returns: dict[str, _ReturnInfo] | None = None) -> _Taint:
    """Everything an expression reads — flag-shaped or laundered through a local.

    Four sources, and one deliberate mask:

    * a flag-shaped ``Name``/``Attribute``/string key, as before;
    * a bound constant, as before;
    * a PLAIN local carrying taint from the enclosing function's alias map —
      this is what closes the rename vector;
    * a call to a function defined in the same module, folded in through its
      recorded return provenance.

    THE MASK, and why it is not a hole. A ``Name`` that is the object of an
    attribute or subscript access does NOT fold its alias taint:
    ``counted.byte_truncated`` names its own flag exactly, so inheriting the
    whole container's taint would make the observer's own
    ``byte_truncated = sha_truncated or counted.byte_truncated`` read
    ``record_truncated`` and turn the permitting arm red for a value it never
    reads. The access names the provenance; the container does not.
    """
    aliases = aliases or {}
    returns = returns or {}
    flags: set[str] = set()
    bounds: set[str] = set()
    literal_true = False

    masked = {
        id(child.value)
        for child in ast.walk(node)
        if isinstance(child, (ast.Attribute, ast.Subscript))
    }

    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            if _is_flag_name(child.id):
                flags.add(_flag_key(child.id))
            elif child.id in bound_names:
                bounds.add(child.id)
            elif id(child) not in masked:
                carried = aliases.get(child.id)
                if carried is not None:
                    flags |= carried.flags
                    bounds |= carried.bounds
                    literal_true = literal_true or carried.literal_true
        elif isinstance(child, ast.Attribute):
            if _is_flag_name(child.attr):
                flags.add(_flag_key(child.attr))
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            if _is_flag_name(child.value):
                flags.add(_flag_key(child.value))
            elif child.value in bound_names:
                bounds.add(child.value)
        elif isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            info = returns.get(child.func.id)
            if info is not None:
                # Deliberately NOT literal_true: a function that returns True
                # is not the "bare True with no cap named" shape.
                flags |= info.whole.flags
                bounds |= info.whole.bounds
    return _Taint(flags, bounds, literal_true)


def _walk_for_bindings(
    tree: ast.AST, bound_names: set[str], returns: dict[str, _ReturnInfo]
) -> tuple[list[_FlagBinding], dict[str, _ReturnInfo]]:
    """One source-order pass: every flag binding, and what each function returns.

    Binding shapes recognised, because the defect can wear any of them: plain
    assignment, annotated assignment (NamedTuple fields), tuple unpacking,
    augmented assignment, subscript assignment (``audit["x"] = ...``),
    object-literal keys (the emitted packet), and call keywords
    (``f(record_truncated=...)``).

    Alias scope is PER FUNCTION, the walk is in source order, and taint MERGES
    CONSERVATIVELY: a local is tainted if ANY assignment the walk has seen for
    it is tainted, so an untainted rebinding in one branch cannot cancel a
    tainted one in another. A nested function inherits the enclosing map, so a
    closure reading an enclosing tainted local carries the taint. The cost of
    conservatism is false refusals, and the control for it is the benign
    snippets in ``_BENIGN_FRESH`` plus the shipped module itself, which must
    stay green.
    """
    bindings: list[_FlagBinding] = []
    discovered: dict[str, _ReturnInfo] = {}
    guard_stack: list[set[str]] = []
    alias_stack: list[dict[str, _Taint]] = [{}]
    func_stack: list[str] = []
    return_stack: list[list[tuple[_Taint, dict[int, _Taint]]]] = []

    def guards() -> set[str]:
        return {name for frame in guard_stack for name in frame}

    def aliases() -> dict[str, _Taint]:
        return alias_stack[-1]

    def taint_of(value: ast.AST) -> _Taint:
        return _expression_taint(value, bound_names, aliases(), returns)

    def emit(name: str, lineno: int, carried: _Taint, bare_true: bool) -> None:
        if not _is_flag_name(name):
            return
        bindings.append(
            _FlagBinding(name, lineno, carried.flags, carried.bounds,
                         bare_true or carried.literal_true, guards())
        )

    def remember(name: str, carried: _Taint) -> None:
        """Taint a PLAIN local MONOTONELY. Flags and bounds keep their own rules.

        Taint is only ever ADDED, never removed. A per-function map that let a
        later untainted rebinding clear an earlier tainted one was reading
        SOURCE ORDER as if it were reachability: with
        ``if x: tt = read.byte_truncated`` / ``else: tt = False`` the else-arm
        is simply the last assignment in the file, so the taint died at a
        branch that does not dominate the read. Merging conservatively — a
        local is tainted if ANY assignment reaching it is tainted — makes the
        two arms of a branch, and a guard-clause reset, behave the same as the
        reversed spelling. This is still not a dataflow analysis: see the
        docstring of the test that consumes it.
        """
        if _is_flag_name(name) or name in bound_names:
            return
        if not carried:
            return
        existing = aliases().get(name)
        aliases()[name] = existing.union(carried) if existing is not None else carried

    def slot_taints(value: ast.AST, count: int) -> list[_Taint]:
        """Per-slot provenance for ``a, b, c = <value>``."""
        if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == count:
            return [taint_of(element) for element in value.elts]
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            info = returns.get(value.func.id)
            if info is not None and info.slots:
                return [info.slots.get(index, info.whole) for index in range(count)]
        whole = taint_of(value)
        return [whole] * count

    def bind(target: ast.AST, carried: _Taint, lineno: int, bare_true: bool) -> None:
        if isinstance(target, ast.Name):
            emit(target.id, lineno, carried, bare_true)
            remember(target.id, _Taint(carried.flags, carried.bounds,
                                       bare_true or carried.literal_true))
        elif isinstance(target, ast.Attribute):
            emit(target.attr, lineno, carried, bare_true)
        elif isinstance(target, ast.Subscript):
            key = target.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                emit(key.value, lineno, carried, bare_true)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                bind(element, carried, lineno, bare_true)

    def assign(target: ast.AST, value: ast.AST | None, lineno: int) -> None:
        if value is None:
            bind(target, _EMPTY_TAINT, lineno, False)
            return
        bare_true = isinstance(value, ast.Constant) and value.value is True
        if isinstance(target, (ast.Tuple, ast.List)):
            for element, carried in zip(target.elts, slot_taints(value, len(target.elts))):
                bind(element, carried, lineno, False)
            return
        bind(target, taint_of(value), lineno, bare_true)

    def visit(node: ast.AST) -> None:
        pushed_guard = False
        pushed_func = False
        if isinstance(node, ast.If):
            guard_stack.append(taint_of(node.test).bounds)
            pushed_guard = True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # A function nested inside ANOTHER FUNCTION inherits the enclosing
            # map rather than starting empty: a closure reading an enclosing
            # tainted local is the shape of inventory()/record(), and an empty
            # child map lets the taint die at the `def`. A function at MODULE
            # level does NOT inherit: module-level names are globals, not
            # closure cells, and inheriting them makes every function read the
            # flag-shaped string constants in `_TRUNCATION_KEYS` — measured, the
            # shipped module turns red on `for key in _TRUNCATION_KEYS`.
            alias_stack.append(dict(alias_stack[-1]) if func_stack else {})
            func_stack.append(node.name)
            return_stack.append([])
            pushed_func = True

        if isinstance(node, ast.Assign):
            for target in node.targets:
                assign(target, node.value, node.lineno)
        elif isinstance(node, ast.AnnAssign):
            assign(node.target, node.value, node.lineno)
        elif isinstance(node, ast.AugAssign):
            existing = _EMPTY_TAINT
            if isinstance(node.target, ast.Name):
                existing = aliases().get(node.target.id, _EMPTY_TAINT)
            bind(node.target, existing.union(taint_of(node.value)), node.lineno, False)
        elif isinstance(node, ast.NamedExpr):
            # A walrus target is a plain local assigned from an expression:
            # without this branch `if (w := cut):` binds `w` through no
            # assignment node the walk recognises. Receipt in _FRESH_CONFLATIONS.
            bind(node.target, taint_of(node.value), node.lineno,
                 isinstance(node.value, ast.Constant) and node.value.value is True)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            # Iterating a TAINTED iterable binds the taint to the target —
            # `for cut in [read.byte_truncated]:` is the rename vector wearing
            # a loop instead of an assignment, and an unconditional clear here
            # once permitted it. An untainted iterable adds nothing and, under
            # the monotone rule in `remember`, removes nothing either.
            carried = taint_of(node.iter)
            if carried:
                bind(node.target, carried, node.lineno, False)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    emit(key.value, getattr(key, "lineno", node.lineno), taint_of(value),
                         isinstance(value, ast.Constant) and value.value is True)
        elif isinstance(node, ast.keyword) and node.arg:
            emit(node.arg, node.value.lineno, taint_of(node.value),
                 isinstance(node.value, ast.Constant) and node.value.value is True)
        elif isinstance(node, ast.Return) and return_stack and node.value is not None:
            slots: dict[int, _Taint] = {}
            if isinstance(node.value, (ast.Tuple, ast.List)):
                slots = {index: taint_of(element)
                         for index, element in enumerate(node.value.elts)}
            return_stack[-1].append((taint_of(node.value), slots))

        for child in ast.iter_child_nodes(node):
            visit(child)

        if pushed_guard:
            guard_stack.pop()
        if pushed_func:
            records = return_stack.pop()
            name = func_stack.pop()
            alias_stack.pop()
            whole = _EMPTY_TAINT
            merged: dict[int, _Taint] = {}
            for carried, slots in records:
                whole = whole.union(carried)
                for index, slot in slots.items():
                    merged[index] = merged.get(index, _EMPTY_TAINT).union(slot)
            discovered[name] = _ReturnInfo(whole, merged)

    visit(tree)
    return bindings, discovered


def _function_return_taints(tree: ast.AST, bound_names: set[str]) -> dict[str, _ReturnInfo]:
    """Fixpoint over module-local return provenance.

    Pass 1 sees returns with no call resolution; each later pass folds the
    previous pass's answers back in, so provenance crosses one call boundary
    per pass. Monotone (every merge is a union), so it converges; the pass cap
    means a pathological module fails the guard rather than hanging it.
    """
    info: dict[str, _ReturnInfo] = {}
    for _ in range(_RETURN_TAINT_PASSES):
        _bindings, discovered = _walk_for_bindings(tree, bound_names, info)
        if {k: v.key() for k, v in discovered.items()} == {k: v.key() for k, v in info.items()}:
            return info
        info = discovered
    return info


def _collect_flag_bindings(tree: ast.AST, bound_names: set[str]) -> list[_FlagBinding]:
    """Every truncation-flag binding site in ``tree``, with laundered provenance folded in."""
    return _walk_for_bindings(tree, bound_names, _function_return_taints(tree, bound_names))[0]


def _conflation_errors(source: str, bound_flags: dict[str, str],
                       rollup_flags: dict[str, tuple[str, ...]],
                       bound_names: set[str]) -> list[str]:
    """Every truncation flag in ``source`` that is neither single-bound nor a declared rollup."""
    problems: list[str] = []
    tree = ast.parse(source)

    for name in sorted(set(bound_flags) & set(rollup_flags)):
        problems.append(f"{name}: declared as BOTH a bound flag and a rollup")
    for name in sorted(bound_flags):
        if "any" in name.split("_"):
            problems.append(f"{name}: a single-bound flag must not be named like a rollup")
        if bound_flags[name] not in bound_names:
            problems.append(f"{name}: declared bound {bound_flags[name]!r} is not a bound constant")
    for name in sorted(rollup_flags):
        if "any" not in name.split("_"):
            problems.append(
                f"{name}: a rollup's NAME must say it is a rollup (an `any` segment); "
                "a rollup wearing a bound's name is the defect this guard exists for"
            )
        for operand in rollup_flags[name]:
            if operand not in bound_flags and operand not in rollup_flags:
                problems.append(f"{name}: declares undeclared operand {operand!r}")

    for binding in _collect_flag_bindings(tree, bound_names):
        name = binding.name
        if name in bound_flags:
            own = bound_flags[name]
            for operand in sorted(binding.flags):
                if operand == name:
                    continue
                if operand in rollup_flags:
                    problems.append(
                        f"L{binding.lineno} {name} ({own}) reads the rollup {operand!r}: "
                        "a field named for one cap cannot carry an any-bound answer"
                    )
                elif bound_flags.get(operand) != own:
                    problems.append(
                        f"L{binding.lineno} {name} declares {own} but reads {operand!r} "
                        f"({bound_flags.get(operand, 'UNDECLARED')})"
                    )
            for other in sorted(binding.bounds - {own}):
                problems.append(
                    f"L{binding.lineno} {name} declares {own} but its value reads {other}"
                )
            if binding.literal_true and own not in binding.guard_bounds:
                problems.append(
                    f"L{binding.lineno} {name} is set True outside any `if` that tests {own}: "
                    "the cap that fired is not identifiable from the code"
                )
        elif name in rollup_flags:
            allowed = set(rollup_flags[name])
            for operand in sorted(binding.flags - allowed - {name}):
                problems.append(
                    f"L{binding.lineno} rollup {name} reads undeclared operand {operand!r}"
                )
            if binding.literal_true:
                problems.append(f"L{binding.lineno} rollup {name} is set to a bare True")
        else:
            problems.append(
                f"L{binding.lineno} {name!r} is a truncation flag that declares no bound "
                "and is not a declared rollup"
            )
    return problems


#: Fresh sites — none of these functions exists in the shipped observer.
#:
#: The first four wear different SITES (a plane, a reader, a counter, an
#: emitter) and different EXPRESSIONS (an OR, an invented name, a constant
#: under the wrong cap's ``if``, a keyword argument), but every offending
#: operand is flag-shaped or a bound-constant literal — a name the guard
#: already recognises — so all four exercise the SAME recognition path and a
#: one-word rename of the operand walks past all of them.
#:
#: The last two are that rename vector, one per laundering channel: a value
#: taken from a module-local call (closed by return provenance) and a bare
#: ``True`` parked in a local first (closed by taint on the literal). Neither
#: offending operand is flag-shaped, so neither is reachable by name matching.
_FRESH_CONFLATIONS = {
    "a new plane ORs the byte cap into an entry-cap field": '''

def _plane_added_next_quarter(read, counted):
    entry_truncated = False
    entry_truncated = entry_truncated or read.byte_truncated
    return {"entry_truncated": entry_truncated}
''',
    "a new reader invents an undeclared flag name": '''

def _reader_added_next_quarter(read):
    stream_truncated = read.byte_truncated or read.record_truncated
    return {"stream_truncated": stream_truncated}
''',
    "a new counter raises the record flag under the entry cap": '''

def _counter_added_next_quarter(items):
    record_truncated = False
    if len(items) >= MAX_INVENTORY_ENTRIES:
        record_truncated = True
    return record_truncated
''',
    "a new emitter puts a byte flag in the record slot by keyword": '''

def _emitter_added_next_quarter(read):
    return _EvidenceCount(count=0, byte_truncated=read.byte_truncated,
                          record_truncated=read.byte_truncated, unparsable=0)
''',
    # The rename vector. The operand is `cut` — not flag-shaped, not a bound
    # constant, nothing a name matcher can see. This is the
    # inventory() defect with one word changed, and it was GREEN before the
    # alias map. Its provenance is recovered from _sha256_file's third return
    # slot, not from its name.
    "a new walker launders the byte cap through a renamed local": '''

def _walker_added_next_quarter(paths):
    entry_truncated = False
    for path in paths:
        _digest, _size, cut = _sha256_file(path)
        entry_truncated = entry_truncated or cut
    return entry_truncated
''',
    # The second laundering channel, a different shape again: no call at all.
    # A bare True is parked in a plain local and OR-ed in, so the cap that
    # fired is unidentifiable from the code and the existing literal-True rule
    # sees only a Name. Taint on the literal is what recovers it.
    "a new plane parks a bare True in a local before OR-ing it in": '''

def _laundered_added_next_quarter(read):
    entry_truncated = False
    flagged = True
    entry_truncated = entry_truncated or flagged
    return entry_truncated
''',
    # Two BINDING FORMS: a walrus target and a loop target, both plain locals
    # assigned from an expression. No current exposure — the shipped observer
    # contains zero ast.NamedExpr nodes — which is exactly when a shape is
    # cheapest to add to the ratchet.
    "a new walker launders the byte cap through a WALRUS target": '''

def _walrus_added_next_quarter(paths):
    entry_truncated = False
    for path in paths:
        _digest, _size, cut = _sha256_file(path)
        if (w := cut):
            entry_truncated = entry_truncated or w
    return entry_truncated
''',
    "a new walker launders the byte cap through a FOR-LOOP target": '''

def _fortarget_added_next_quarter(read):
    entry_truncated = False
    for cut in [read.byte_truncated]:
        entry_truncated = entry_truncated or cut
    return entry_truncated
''',
}


#: THE CONTROL PATTERN, stated once here and referred to below: every refusing
#: arm carries a benign counterpart of the SAME syntax feeding
#: ``member_bytes_truncated``, the flag that really does carry
#: ``MAX_EVIDENCE_BYTES``. Correct code that must stay green — without it an arm
#: proves only that its syntax reddens the guard, which discriminates nothing.
#: Here that is the same walrus and the same loop target.
_BENIGN_FRESH = {
    "a benign walrus feeding the flag that owns the byte cap": '''

def _benign_walrus_added_next_quarter(paths):
    member_bytes_truncated = False
    for path in paths:
        _digest, _size, cut = _sha256_file(path)
        if (w := cut):
            member_bytes_truncated = member_bytes_truncated or w
    return member_bytes_truncated
''',
    "a benign loop target feeding the flag that owns the byte cap": '''

def _benign_fortarget_added_next_quarter(read):
    member_bytes_truncated = False
    for cut in [read.byte_truncated]:
        member_bytes_truncated = member_bytes_truncated or cut
    return member_bytes_truncated
''',
}


#: The real ``inventory()`` member-digest block, and the two one-word renames
#: applied to it. Kept as data so the refusing arm and its control are visibly
#: the SAME edit differing only in which flag receives the byte cap.
_HISTORICAL_ANCHOR = (
    "            digest, size, file_truncated = _sha256_file(Path(path_str))\n"
    "            content_truncated = file_truncated\n"
    "            member_bytes_truncated = member_bytes_truncated or file_truncated"
)
_HISTORICAL_DEFECT = (
    "            digest, size, cut = _sha256_file(Path(path_str))\n"
    "            content_truncated = cut\n"
    "            entry_truncated = entry_truncated or cut"
)
_BENIGN_RENAME = (
    "            digest, size, cut = _sha256_file(Path(path_str))\n"
    "            content_truncated = cut\n"
    "            member_bytes_truncated = member_bytes_truncated or cut"
)


@pytest.mark.timeout(20)
def test_every_truncation_flag_is_single_bound_or_a_declared_rollup():
    """No flag may carry a bound it does not name — checked over the whole module.

    THE PERMITTING ARM is the shipped observer: every truncation flag resolves
    to exactly one cap, or is a rollup whose name carries the ``any`` segment
    and whose operands are enumerated in the registry.

    THE REFUSING ARM is eight functions that do not exist in the module,
    appended to a copy of its source. Four wear different sites and
    expressions — a plane, a reader, a counter, an emitter; an OR, an invented
    name, a constant under the wrong cap's ``if``, a keyword argument — but
    every one of their offending operands is flag-shaped or a bound literal, so
    all four probe the same recognition path. The next two are the RENAME
    VECTOR, where the operand is an ordinary local no name matcher can see: one
    laundered through a module-local call's return, one through a bare
    ``True``. The last two are BINDING FORMS: a walrus target and a ``for``-loop
    target over a tainted iterable.

    EACH REFUSING ARM HAS ITS CONTROL. :data:`_BENIGN_FRESH` re-runs the same
    binding forms feeding ``member_bytes_truncated``, the flag that really does
    carry ``MAX_EVIDENCE_BYTES`` — correct code that must stay green, or the
    arms above would prove only that a walrus or a loop reddens the guard.

    WHAT THIS GUARD IS. A RATCHET over the enumerated shapes above, each with
    this test as its receipt. It is a syntactic AST scan with a per-function
    alias map, NOT a dataflow analysis and NOT a completeness guarantee, and
    ITS REACH IS NOT CHARACTERISED: any conflation may escape it. It is also
    ORDER-SENSITIVE — see
    ``test_conflation_guard_refuses_branch_merge_and_closure_capture_shapes``.
    This docstring names no residual set. Adding a shape to the refusals above
    is safe; saying the set is complete is not.

    WHERE THE WEIGHT SITS is behavioural, and does not depend on this guard's
    reach at all:
    ``test_inventory_entry_cap_and_member_byte_cap_are_reported_independently``
    and ``test_byte_and_record_bounds_are_reported_independently`` read the
    EMITTED PACKET, so they refute a real conflation however it was written.
    """
    source = OBSERVER_PATH.read_text(encoding="utf-8")
    bound_flags = dict(observer.TRUNCATION_BOUND_FLAGS)
    rollup_flags = dict(observer.TRUNCATION_ROLLUP_FLAGS)
    bound_names = set(observer.BOUND_CONSTANT_NAMES)

    # --- CONTROL OF THE INSTRUMENT. A collector that found nothing would pass
    # every arm below for the wrong reason, and a name matcher that matched
    # nothing would find nothing. Both are pinned before anything is judged.
    assert _is_flag_name("truncated") and _is_flag_name("byte_truncated")
    assert _is_flag_name("_byte_truncated") and _is_flag_name("clipped")
    assert not _is_flag_name("TRUNCATION_KEYS") and not _is_flag_name("truncation_contract")
    assert not _is_flag_name("unparsable_records") and not _is_flag_name("malformed")

    bindings = _collect_flag_bindings(ast.parse(source), bound_names)
    bound_sites = {b.name for b in bindings}
    assert len(bindings) >= 30, f"the collector found only {len(bindings)} binding sites"
    assert {"entry_truncated", "member_bytes_truncated", "content_truncated",
            "byte_truncated", "record_truncated", "any_bound_truncated"} <= bound_sites, (
        f"the collector missed a known flag: found {sorted(bound_sites)}"
    )

    # --- REGISTRY SHAPE. Every bound named by a constant, every cap covered.
    assert set(bound_flags.values()) == bound_names, (
        f"a declared bound has no flag: {sorted(bound_names - set(bound_flags.values()))}"
    )
    assert set(observer.PUBLISHED_TRUNCATION_FLAGS) <= set(bound_flags) | set(rollup_flags)
    assert observer._TRUNCATION_KEYS == observer.PUBLISHED_TRUNCATION_FLAGS, (
        "the plane-bounds reader must be DERIVED from the published set, not restated"
    )

    # --- PERMITTING ARM.
    problems = _conflation_errors(source, bound_flags, rollup_flags, bound_names)
    assert problems == [], "the shipped observer conflates bounds:\n" + "\n".join(problems)

    # --- REFUSING ARM: eight fresh sites; see _FRESH_CONFLATIONS for the shapes
    # and for which recognition path each one exercises.
    for label, snippet in _FRESH_CONFLATIONS.items():
        mutated = _conflation_errors(source + snippet, bound_flags, rollup_flags, bound_names)
        assert mutated, f"the guard PERMITTED a fresh conflation: {label}"
        assert len(mutated) >= len(problems) + 1, (label, mutated)

    # --- CONTROL ON THE TWO BINDING FORMS: the same walrus and the same loop
    # target, feeding the flag that really does carry MAX_EVIDENCE_BYTES, are
    # correct code and must stay GREEN. A guard that reddens on the SYNTAX
    # rather than on the conflation would fail here.
    for label, snippet in _BENIGN_FRESH.items():
        benign = _conflation_errors(source + snippet, bound_flags, rollup_flags, bound_names)
        assert benign == problems, (
            f"the guard REFUSED correct code — it is firing on the binding form "
            f"rather than on the conflation: {label}: {benign}"
        )

    # --- REFUSING ARM, THE SHARPEST: the real conflation put back at
    # its REAL site with the operand renamed. Appended functions could be
    # refused for reasons that have nothing to do with the shipped code; this
    # one edits inventory() itself, and this exact input was PERMITTED before
    # the alias map existed.
    assert _HISTORICAL_ANCHOR in source, (
        "the inventory() member-digest block moved; this control now proves nothing"
    )
    reintroduced = _conflation_errors(
        source.replace(_HISTORICAL_ANCHOR, _HISTORICAL_DEFECT, 1),
        bound_flags, rollup_flags, bound_names,
    )
    assert any("entry_truncated declares MAX_INVENTORY_ENTRIES" in problem
               and "byte_truncated" in problem for problem in reintroduced), (
        "the guard PERMITTED the historical inventory() defect with its operand "
        f"renamed from file_truncated to cut: {reintroduced}"
    )

    # --- The control pattern (see _BENIGN_FRESH) for the RENAME shape: the
    # same rename feeding member_bytes_truncated is correct code, and green.
    assert _conflation_errors(
        source.replace(_HISTORICAL_ANCHOR, _BENIGN_RENAME, 1),
        bound_flags, rollup_flags, bound_names,
    ) == problems, (
        "the alias map refuses a CORRECT rename: it is firing on the rename "
        "itself rather than on the conflation"
    )

    # --- REFUSING ARM, registry side: a rollup that borrows a bound's name,
    # and a bound flag declared with an `any` name, must both be refused. This
    # is the escape hatch a lazy fix would reach for.
    borrowed = dict(rollup_flags)
    borrowed["entry_truncated"] = ("byte_truncated", "entry_truncated")
    assert any("must say it is a rollup" in p or "BOTH" in p
               for p in _conflation_errors(source, bound_flags, borrowed, bound_names))
    misnamed = dict(bound_flags)
    misnamed["any_cap_truncated"] = "MAX_EVIDENCE_BYTES"
    assert any("must not be named like a rollup" in p
               for p in _conflation_errors(source, misnamed, rollup_flags, bound_names))

    # --- THE SCHEMA MUST SAY THE SAME THING. A frozen description that is
    # false about the code carries mechanical authority it has not earned, so
    # every flag-shaped property is held to its registry entry.
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    described: dict[str, list[str]] = {}
    for node in _schema_object_nodes(schema):
        for prop, body in (node.get("properties") or {}).items():
            if _is_flag_name(prop) and isinstance(body, dict):
                described.setdefault(prop, []).append(body.get("description", ""))
    assert set(described) == set(observer.PUBLISHED_TRUNCATION_FLAGS), (
        f"schema flags {sorted(described)} != published {sorted(observer.PUBLISHED_TRUNCATION_FLAGS)}"
    )
    for prop, descriptions in sorted(described.items()):
        for description in descriptions:
            if prop in bound_flags:
                assert bound_flags[prop] in description, (
                    f"schema description for {prop} never names its cap {bound_flags[prop]}"
                )
                foreign = [b for b in bound_names if b != bound_flags[prop] and b in description]
                assert all(
                    re.search(rf"(?:nor|not|neither|own field|`\w+`\s*\()[^.]*{re.escape(other)}"
                              rf"|{re.escape(other)}[^.]*(?:has its own|lives on|and nothing else)",
                              description)
                    for other in foreign
                ), f"schema description for {prop} mentions {foreign} without disowning it"
            else:
                assert "ROLLUP" in description.upper(), (
                    f"schema description for the rollup {prop} never says it is a rollup"
                )

    # --- CONTROL OF THAT CONTROL: a description stripped of its cap name must
    # be refused, or the loop above proves nothing.
    stripped = "True when a bound clipped this."
    assert bound_flags["entry_truncated"] not in stripped


# ==========================================================================
# 18 — the inventory's two caps are reported independently (three cells).
#      20s: the entry cell runs against a PATCHED entry cap (argued in the
#      docstring) so it writes probe_cap+1 tiny files rather than
#      MAX_INVENTORY_ENTRIES+1, plus one file just over the 4 MiB byte cap.
#      This node is bound by the NUMBER of files it creates and reads back,
#      not by their bytes: un-patched it measured 0.87s locally and 20.06s --
#      a TIMEOUT -- under 32-way contention on 16 cores, a 23.1x degradation
#      where the whole run degraded 5.7x. Patched it measures 0.32s locally
#      and does not reach the twelve slowest nodes under the same contention.
# ==========================================================================


@pytest.mark.timeout(20)
def test_inventory_entry_cap_and_member_byte_cap_are_reported_independently(tmp_path):
    """``MAX_INVENTORY_ENTRIES`` had no behavioural coverage at all, and was wrong.

    Measured on the un-fixed bytes: an inventory of FOUR paths, against an
    entry cap of 5,000, reported ``truncated=True`` because one member file was
    4,194,305 bytes — one byte over the byte cap. The schema said that field
    was "the MAX_INVENTORY_ENTRIES entry cap... that cap and nothing else;
    this plane applies neither the byte cap nor the record cap", which was
    measurably false about the observer shipped beside it.

    Three cells, the same discrimination built for the JSONL bounds:

    ======================  ================  ==========================
    cell                    entry_truncated   member_bytes_truncated
    ======================  ================  ==========================
    entry cap only           True              False
    byte cap only            False             True
    neither                  False             False
    ======================  ================  ==========================

    A single always-on flag satisfies no two rows, and an always-off flag
    satisfies neither clipped row, so neither degenerate answer survives.

    THE ENTRY CELL RUNS AGAINST A PATCHED CAP, and the subject of this node is
    why that costs nothing. The question here is whether the two caps are
    reported INDEPENDENTLY — one field per bound, neither standing for the
    other — not whether the entry cap is 5,000. Tripping a cap of 50 executes
    the same branch in the same reader over the same flags as tripping a cap of
    5,000; only the file count differs. The NUMBER lives in exactly one place,
    the manifest's ``output_bounds.max_inventory_entries``, bound to
    ``MAX_INVENTORY_ENTRIES`` by
    ``test_manifest_output_bounds_match_the_observer_constants``, which refuses
    a drift in either direction and in three shapes. It is cross-checked
    against the real constant below before anything is patched, so this node
    cannot be the place a wrong cap hides.

    WHY IT IS PATCHED AT ALL: un-patched this cell writes ``cap_entries + 1``
    files into a cold directory and ``inventory`` opens and digests every one
    it records — thousands of opens, none of them carrying more than a byte of
    content. That is file COUNT, not bytes, and file count is what degrades
    under load: the node measured 0.87s locally and TIMED OUT at 20.06s under
    32-way contention on 16 cores, a 23.1x degradation where the whole run
    degraded 5.7x. A frozen hard gate that reds on a loaded runner refuses the
    runner, not the defect. Patched, the same three cells measure 0.32s.

    THE PATCH HAS ITS OWN CONTROL. ``entry_count == probe_cap`` can only hold
    if ``inventory`` read the patched constant: had the patch silently not
    taken, the real cap would still be in force, this cell's handful of paths
    is nowhere near it, and the cell would report every path it wrote plus its
    root with ``entry_truncated=False``. A no-op patch therefore FAILS here
    rather than passing for the wrong reason. The constant is restored in a
    ``finally`` and the restoration is asserted.

    BOTH REINSTATEMENTS LAND ON THIS CELL, measured rather than argued: the
    entry cap raising ``member_bytes_truncated`` (the reverse conflation), and
    the entry cap clipping without raising its own flag, each turn this cell
    red at the patched cap. Neither is visible to the other two cells.
    """
    cap_entries = observer.MAX_INVENTORY_ENTRIES
    cap_bytes = observer.MAX_EVIDENCE_BYTES

    # The entry cap's ONE home, read rather than restated: this node must not
    # become a second place the number is written down.
    assert cap_entries == _case(_manifest(), "P0-C01")["output_bounds"][
        "max_inventory_entries"
    ], "the observer's entry cap and the manifest's declared bound disagree"

    # --- CELL 3 (neither). Written first so a failure here says "the probe is
    # always-on" rather than being read as a real clip.
    neither_root = tmp_path / "neither"
    neither_root.mkdir()
    for name in ("a.txt", "b.txt", "c.txt"):
        (neither_root / name).write_text(name)
    neither = observer.inventory(neither_root)
    assert neither["entry_count"] == 4, neither["entry_count"]
    assert neither["entry_truncated"] is False
    assert neither["member_bytes_truncated"] is False
    assert neither["observation_status"] == "OBSERVED"
    assert all(e["content_truncated"] is False for e in neither["entries"].values())

    # --- CELL 2 (byte cap only). Four paths against a 5,000 entry cap, one of
    # them one byte over the byte cap. This is the exact reproduction.
    byte_root = tmp_path / "byte_only"
    byte_root.mkdir()
    (byte_root / "small-a.txt").write_text("a")
    (byte_root / "small-b.txt").write_text("b")
    oversized = byte_root / "oversized.bin"
    oversized.write_bytes(b"\0" * (cap_bytes + 1))
    assert oversized.stat().st_size == cap_bytes + 1
    byte_only = observer.inventory(byte_root)
    assert byte_only["entry_count"] == 4
    assert byte_only["entry_count"] < cap_entries, "this cell must not approach the entry cap"
    assert byte_only["member_bytes_truncated"] is True
    assert byte_only["entry_truncated"] is False, (
        "an inventory of four paths reported the 5,000-entry cap as fired; the "
        "byte cap of a member file is being carried by the entry cap's field"
    )
    clipped = {p for p, e in byte_only["entries"].items() if e["content_truncated"]}
    assert clipped == {os.path.normpath(str(oversized))}, sorted(clipped)
    assert byte_only["entries"][os.path.normpath(str(oversized))]["bytes"] == cap_bytes

    # --- CELL 1 (entry cap only). Enough tiny files to trip the entry cap,
    # none of them anywhere near the byte cap. Driven against a PATCHED cap of
    # 50: the branch, the reader and the two flags are the production ones, and
    # only the file count changes. See the docstring for why the number itself
    # is not this node's subject.
    probe_cap = 50
    assert probe_cap < cap_entries, "the probe cap must be cheaper than the real one"
    entry_root = tmp_path / "entry_only"
    entry_root.mkdir()
    for index in range(probe_cap + 1):
        (entry_root / f"f{index:05d}.txt").write_text("x")
    written = sorted(p.name for p in entry_root.iterdir())
    assert len(written) == probe_cap + 1, len(written)
    observer.MAX_INVENTORY_ENTRIES = probe_cap
    try:
        # CONTROL OF THE PATCH, executed rather than declared: a patch that did
        # not take leaves the real cap of `cap_entries` in force, 51 entries is
        # nowhere near it, and both assertions below fail. Passing here is only
        # possible if `inventory` read the patched constant.
        entry_only = observer.inventory(entry_root)
    finally:
        observer.MAX_INVENTORY_ENTRIES = cap_entries
    assert observer.MAX_INVENTORY_ENTRIES == cap_entries, (
        "the patched entry cap was not restored; every later node in this "
        "session would be measuring a different observer"
    )
    assert entry_only["entry_count"] == probe_cap, entry_only["entry_count"]
    assert entry_only["entry_truncated"] is True
    assert entry_only["member_bytes_truncated"] is False, (
        "no member file is within four megabytes of the byte cap in this cell"
    )
    assert all(e["content_truncated"] is False for e in entry_only["entries"].values())

    # --- CONSERVATIVE DEGRADATION IS UNCHANGED. Splitting the fields must not
    # soften the refusal: the reader that degrades decisions consults BOTH.
    assert observer._plane_bounds(neither)[0] is False
    assert observer._plane_bounds(byte_only)[0] is True, (
        "a byte-clipped member stopped degrading the plane when the flags split"
    )
    assert observer._plane_bounds(entry_only)[0] is True

    # --- END TO END, a different shape: a recorded fs-inventory carrying only
    # the member byte flag must take every filesystem decision to UNMEASURED,
    # while a decision that reads no filesystem plane stays OBSERVED.
    document = json.loads((VALID_DIR / "fs-inventory.json").read_text(encoding="utf-8"))
    clean_root = _make_run_root(tmp_path / "fs_clean")
    clean_packet = _packet_from(OBSERVER_PATH, clean_root)
    for decision_id in ("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS",
                        "D11_NO_SILENT_CONTENT_CHANGE",
                        "D12_MODE_OWNER_RECORDED_FAITHFULLY"):
        assert _decision_of(clean_packet, decision_id)["observation_status"] == "OBSERVED"

    document["post"]["member_bytes_truncated"] = True
    clipped_file = tmp_path / "fs-inventory-clipped.json"
    clipped_file.write_text(json.dumps(document, indent=2), encoding="utf-8")
    clipped_root = _make_run_root(
        tmp_path / "fs_clipped", {"fs-inventory.json": clipped_file}
    )
    clipped_packet = _packet_from(OBSERVER_PATH, clipped_root)
    _validator().validate(clipped_packet)
    assert clipped_packet["observation"]["filesystem"]["any_bound_truncated"] is True
    assert clipped_packet["observation"]["filesystem"]["post"]["entry_truncated"] is False
    for decision_id in ("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS",
                        "D11_NO_SILENT_CONTENT_CHANGE",
                        "D12_MODE_OWNER_RECORDED_FAITHFULLY"):
        decision = _decision_of(clipped_packet, decision_id)
        assert decision["evidence_bounds"]["any_bound_truncated"] is True, decision
        assert decision["observation_status"] == "UNMEASURED", decision
    unrelated = _decision_of(clipped_packet, "D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION")
    assert unrelated["evidence_bounds"]["any_bound_truncated"] is False, unrelated
    assert unrelated["observation_status"] == "OBSERVED", unrelated


# ==========================================================================
# 19 — the prefix-digest residual is asserted, not merely declared.
#      20s: writes four files totalling ~16 MiB (measured 1.4s locally).
# ==========================================================================


@pytest.mark.timeout(20)
def test_two_files_differing_past_the_byte_cap_record_identical_digests(tmp_path):
    """The residual both the observer and the schema DECLARE, now measured.

    ``observe_claude_execution.inventory``'s docstring and the schema's
    ``content_truncated`` description both state that two files exceeding
    ``MAX_EVIDENCE_BYTES`` and differing only past it produce the same
    ``sha256`` and the same ``bytes``. That was true by construction and
    asserted nowhere — a frozen description carrying mechanical authority it
    had not earned, which is the exact defect class this changeset exists to
    remove. A residual that is only written down drifts the moment the digest
    loop changes.

    Four cells, so no degenerate implementation survives:

    ======================================  =========  ==================
    cell                                    sha256     content_truncated
    ======================================  =========  ==================
    two files differing PAST the cap        identical  True on both
    two files differing WITHIN the cap      different  False on both
    ======================================  =========  ==================

    The second row is the negative control, and it is a different shape from
    the first rather than its mirror: it holds the file SIZE below the cap and
    varies the content, where the first holds content identical below the cap
    and varies the size. A digest that always returned a constant satisfies row
    one and fails row two; a digest that ignored the cap satisfies row two and
    fails row one. Neither degenerate answer survives both.
    """
    cap = observer.MAX_EVIDENCE_BYTES

    # --- CELL 1. Identical for exactly `cap` bytes, then divergent. Both files
    # are over 4 MiB, so both are clipped and the divergence is unreachable.
    past = tmp_path / "past_the_cap"
    past.mkdir()
    shared_prefix = (b"prefix-bytes-shared-by-both-files;" * ((cap // 34) + 1))[:cap]
    assert len(shared_prefix) == cap
    (past / "alpha.bin").write_bytes(shared_prefix + b"A" * 4096)
    (past / "beta.bin").write_bytes(shared_prefix + b"B" * 4096)

    past_inventory = observer.inventory(past)
    alpha = past_inventory["entries"][os.path.normpath(str(past / "alpha.bin"))]
    beta = past_inventory["entries"][os.path.normpath(str(past / "beta.bin"))]

    assert alpha["content_truncated"] is True, alpha
    assert beta["content_truncated"] is True, beta
    assert alpha["sha256"] == beta["sha256"], (
        "two files clipped at the same cap and identical below it must record "
        f"the same prefix digest: {alpha['sha256']} != {beta['sha256']}"
    )
    assert alpha["bytes"] == beta["bytes"] == cap, (alpha["bytes"], beta["bytes"], cap)
    assert past_inventory["member_bytes_truncated"] is True
    assert past_inventory["entry_truncated"] is False, (
        "two clipped members must not be reported as the 5,000-entry cap firing"
    )

    # --- CELL 2, THE NEGATIVE CONTROL. Below the cap, the digest must still
    # discriminate; otherwise cell 1 is satisfied by a constant.
    within = tmp_path / "within_the_cap"
    within.mkdir()
    (within / "alpha.bin").write_bytes(b"a" * 1024 + b"A")
    (within / "beta.bin").write_bytes(b"a" * 1024 + b"B")

    within_inventory = observer.inventory(within)
    small_alpha = within_inventory["entries"][os.path.normpath(str(within / "alpha.bin"))]
    small_beta = within_inventory["entries"][os.path.normpath(str(within / "beta.bin"))]

    assert small_alpha["content_truncated"] is False, small_alpha
    assert small_beta["content_truncated"] is False, small_beta
    assert small_alpha["sha256"] != small_beta["sha256"], (
        "the digest does not discriminate below the cap, so the equality "
        "asserted above proves nothing about clipping"
    )
    assert small_alpha["bytes"] == small_beta["bytes"] == 1025
    assert within_inventory["member_bytes_truncated"] is False

    # --- THE DECLARATIONS THEMSELVES. Both texts must keep saying it, or the
    # cells above silently become the only record of a documented promise.
    assert "differ only past it" in (observer.inventory.__doc__ or ""), (
        "inventory() stopped declaring the prefix-digest residual"
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    descriptions = [
        body.get("description", "")
        for node in _schema_object_nodes(schema)
        for prop, body in (node.get("properties") or {}).items()
        if prop == "content_truncated" and isinstance(body, dict)
    ]
    assert descriptions, "the schema no longer describes content_truncated"
    assert all("differ only past it" in text for text in descriptions), descriptions


# ==========================================================================
# 20 — the branch-merge and closure shapes, in BOTH branch orders.
#      20s: AST parses of the ~4,550-line module plus its return-taint
#      fixpoint (measured ~1.2s locally); no subprocess, no filesystem.
# ==========================================================================

#: Probes A, B, C and D. Every one is the SAME dataflow — a plain local takes
#: ``byte_truncated`` (MAX_EVIDENCE_BYTES) and is then OR-ed into
#: ``entry_truncated`` (MAX_INVENTORY_ENTRIES) — differing only in HOW the local
#: is bound. A and C are the same dataflow with the two branches swapped, so the
#: test can assert that STATEMENT ORDER does not change the answer. D is a
#: nested-closure read of an enclosing tainted local.
_BRANCH_AND_CLOSURE_CONFLATIONS = {
    "A: tainted in the if-arm, reset in the else-arm": '''

def _probe_a_added_next_quarter(read, x):
    entry_truncated = False
    if x:
        tt = read.byte_truncated
    else:
        tt = False
    entry_truncated = entry_truncated or tt
    return entry_truncated
''',
    "B: tainted first, reset under a guard clause": '''

def _probe_b_added_next_quarter(read, x):
    entry_truncated = False
    tt = read.byte_truncated
    if not x:
        tt = False
    entry_truncated = entry_truncated or tt
    return entry_truncated
''',
    "C: the same dataflow with the two branches swapped": '''

def _probe_c_added_next_quarter(read, x):
    entry_truncated = False
    if x:
        tt = False
    else:
        tt = read.byte_truncated
    entry_truncated = entry_truncated or tt
    return entry_truncated
''',
    "D: a nested closure reads an enclosing tainted local": '''

def _probe_d_added_next_quarter(read):
    entry_truncated = False
    cut = read.byte_truncated
    def _inner():
        return cut
    entry_truncated = entry_truncated or _inner()
    return entry_truncated
''',
}

#: The control pattern (see :data:`_BENIGN_FRESH`) for each probe above, one
#: per shape: the SAME binding form feeding ``member_bytes_truncated``.
_BRANCH_AND_CLOSURE_BENIGN = {
    "A control: if/else feeding the flag that owns the byte cap": '''

def _probe_a_control_added_next_quarter(read, x):
    member_bytes_truncated = False
    if x:
        tt = read.byte_truncated
    else:
        tt = False
    member_bytes_truncated = member_bytes_truncated or tt
    return member_bytes_truncated
''',
    "B control: guard clause feeding the flag that owns the byte cap": '''

def _probe_b_control_added_next_quarter(read, x):
    member_bytes_truncated = False
    tt = read.byte_truncated
    if not x:
        tt = False
    member_bytes_truncated = member_bytes_truncated or tt
    return member_bytes_truncated
''',
    "C control: swapped branches feeding the flag that owns the byte cap": '''

def _probe_c_control_added_next_quarter(read, x):
    member_bytes_truncated = False
    if x:
        tt = False
    else:
        tt = read.byte_truncated
    member_bytes_truncated = member_bytes_truncated or tt
    return member_bytes_truncated
''',
    "D control: a closure feeding the flag that owns the byte cap": '''

def _probe_d_control_added_next_quarter(read):
    member_bytes_truncated = False
    cut = read.byte_truncated
    def _inner():
        return cut
    member_bytes_truncated = member_bytes_truncated or _inner()
    return member_bytes_truncated
''',
}


# ==========================================================================
# The PROSE ratchet: what the frozen text about the AST guard may not say
# ==========================================================================
#
# The DESCRIPTION of the AST guard is what kept getting falsified, not the
# guard. A withdrawal that reaches two of three surfaces leaves the third
# asserting the opposite about the same class, in the surface nobody guarded.
#
# So the surfaces are enumerated in :func:`_guard_prose_surfaces`, once, and all
# of them are checked. WHAT THIS RATCHET IS: a ban over an enumerated list of
# claim FORMS, plus a requirement that every surface carries the disclaimer. It
# is not a detector of claims in general, and its own reach is not characterised
# either — a reach claim worded outside the list passes. What it buys is that
# the falsified forms cannot come back in any covered surface, and that a
# surface cannot drop out of the checked set silently.
#
# DELIBERATELY OUT OF SCOPE, with the reason measured rather than asserted:
#   * this test module's own prose — it is where a falsified sentence is
#     legitimately QUOTED in order to be withdrawn, so a ban here would refuse
#     the withdrawal too;
#   * CHANGELOG.md — not digest-bound, and a historical record must restate old
#     claims to retract them. Measured before excluding it: an unrelated ratchet
#     entry there contains "refuses every" in a sentence about a pinned ceiling,
#     so covering the whole file would refuse correct prose about a different
#     subject.
# Both exclusions are gaps in this ratchet's coverage, named here rather than
# argued away.

#: Every covered surface MUST say the reach is uncharacterised, in these words.
_REACH_DISCLAIMERS: tuple[str, ...] = (
    "reach is not characterised",
    "any conflation may escape",
)

#: Claim forms that were falsified, or that assert a reach nothing here
#: measures. Every phrase was checked against all three shipped surfaces
#: before being added, and NEAR MISSES ARE DELIBERATELY ABSENT: "refuses any"
#: is not on the list because the manifest uses it truthfully about the
#: bindings a walk does see, and "exhaustive" is not, because the manifest
#: says "claiming the list is exhaustive is not [safe]". A ban that fires on
#: correct prose gets paid off by weakening the ban.
_REACH_CLAIM_PHRASES: tuple[str, ...] = (
    "the only escape",
    "the only channel",
    "remain, each measured",
    "channels remain",
    "catches a new",
    "not just the three known",
    "cannot escape",
    "no conflation escapes",
    "no conflation can",
    "always catches",
    "guaranteed to catch",
    "will catch",
    "catches every",
    "catches any",
    "refuses every",
    "every conflation",
    "all conflation",
)


def _normalise_prose(text: str) -> str:
    """Lowercase, with runs of whitespace collapsed to one space.

    Without this the check is defeated by a line break. The withdrawn claim
    shipped as ``# It catches a NEW site, not just the three known\n# ones``,
    so a raw substring scan over the source would have missed both phrases.
    """
    return re.sub(r"\s+", " ", text).strip().lower()


def _python_prose(source: str) -> str:
    """The COMMENT and DOCSTRING text of a Python module, normalised.

    Code is excluded on purpose: a banned phrase is about what a file CLAIMS,
    and an identifier is not a claim.
    """
    parts = [
        token.string.lstrip("#")
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if doc:
                parts.append(doc)
    return _normalise_prose(" ".join(parts))


def _guard_prose_surfaces(manifest: dict[str, Any], observer_source: str) -> dict[str, str]:
    """The frozen prose surfaces that DESCRIBE the AST conflation guard.

    Two manifest fields and the observer module's own source. A surface that
    cannot be found is OMITTED rather than defaulted, so the caller's size
    assertion refuses a silently dropped surface.
    """
    case = _case(manifest, "P0-C01")
    surfaces: dict[str, str] = {}
    contract = case.get("output_bounds", {}).get("bound_independence_contract")
    if isinstance(contract, str):
        surfaces["manifest:output_bounds.bound_independence_contract"] = _normalise_prose(contract)
    limits = [limit for limit in case.get("scope_limits", []) if "AST conflation guard" in limit]
    if len(limits) == 1:
        surfaces["manifest:scope_limits[AST conflation guard]"] = _normalise_prose(limits[0])
    surfaces["source:tests/bootstrap/observe_claude_execution.py"] = _python_prose(observer_source)
    return surfaces


def _reach_claim_errors(surfaces: dict[str, str]) -> list[str]:
    """Surfaces that assert a reach, or that dropped the disclaimer."""
    problems: list[str] = []
    for label in sorted(surfaces):
        text = surfaces[label]
        for disclaimer in _REACH_DISCLAIMERS:
            if disclaimer not in text:
                problems.append(f"{label}: no longer states {disclaimer!r}")
        for phrase in _REACH_CLAIM_PHRASES:
            if phrase in text:
                problems.append(f"{label}: re-acquired the claim form {phrase!r}")
    return problems


@pytest.mark.timeout(20)
def test_conflation_guard_refuses_branch_merge_and_closure_capture_shapes():
    """Four shapes the guard is PROVEN to refuse. Not a claim about its reach.

    THE TRAP THESE FOUR SHAPES NAME. A per-function alias map in which the
    LAST assignment in source order overwrites the taint discriminates
    STATEMENT ORDER rather than dataflow: ``if x: tt = read.byte_truncated`` /
    ``else: tt = False`` followed by ``entry_truncated = tt`` and the same
    dataflow with the branches swapped would then get different answers. A
    nested function starting with an EMPTY alias map loses the taint at the
    ``def``, which is the shape of ``inventory()``/``record()``. Taint therefore
    merges CONSERVATIVELY — a local is tainted if ANY assignment the walk has
    seen for it is tainted — and a nested function inherits the enclosing map.
    Neither is a dataflow analysis, neither computes reachability, and neither
    licenses a claim about what the guard reaches.

    WHAT THIS TEST DOES AND DOES NOT ESTABLISH. It establishes that these FOUR
    NAMED SHAPES are refused and that four correct counterparts are permitted,
    and that A and C — the same dataflow, branches swapped — produce the SAME
    complaint. It establishes nothing about shapes not listed here. The guard is
    documented as a RATCHET over an enumerated set of proven refusals, and its
    reach is recorded as NOT CHARACTERISED. Adding a shape is always safe;
    asserting the set is complete is not.

    THE PROTECTION THAT DOES NOT DEPEND ON THIS GUARD is behavioural:
    ``test_byte_and_record_bounds_are_reported_independently`` and
    ``test_inventory_entry_cap_and_member_byte_cap_are_reported_independently``
    read the EMITTED PACKET, so they refute a real conflation however it was
    spelled.
    """
    source = OBSERVER_PATH.read_text(encoding="utf-8")
    bound_flags = dict(observer.TRUNCATION_BOUND_FLAGS)
    rollup_flags = dict(observer.TRUNCATION_ROLLUP_FLAGS)
    bound_names = set(observer.BOUND_CONSTANT_NAMES)

    # --- CONTROL OF THE INSTRUMENT. The probes below are judged by DELTA
    # against the shipped module, so the shipped module's own answer is pinned
    # first: a guard that refused everything, or a parse that silently returned
    # nothing, would make every arm below meaningless.
    baseline = _conflation_errors(source, bound_flags, rollup_flags, bound_names)
    assert baseline == [], "the shipped observer conflates bounds:\n" + "\n".join(baseline)
    assert _collect_flag_bindings(ast.parse(source), bound_names), (
        "the binding collector found nothing; the probes below cannot inform"
    )

    # --- REFUSING ARM. All four shapes, and the refusal must NAME the two caps
    # it is separating, or a coincidental unrelated complaint would pass here.
    for label, snippet in _BRANCH_AND_CLOSURE_CONFLATIONS.items():
        problems = _conflation_errors(source + snippet, bound_flags, rollup_flags, bound_names)
        added = [p for p in problems if p not in baseline]
        assert added, f"the guard PERMITTED a branch/closure conflation: {label}"
        assert any("entry_truncated declares MAX_INVENTORY_ENTRIES" in p
                   and "byte_truncated" in p for p in added), (label, added)

    # --- PERMITTING ARM, one control per shape and of a DIFFERENT shape from
    # the probe it controls only in which flag receives the value: the same
    # branch, the same guard clause, the same closure, feeding the flag that
    # really does own MAX_EVIDENCE_BYTES. Correct code must stay green.
    for label, snippet in _BRANCH_AND_CLOSURE_BENIGN.items():
        benign = _conflation_errors(source + snippet, bound_flags, rollup_flags, bound_names)
        assert benign == baseline, (
            f"the guard REFUSED correct code — it is firing on the binding form "
            f"rather than on the conflation: {label}: {benign}"
        )

    # --- THE ORDER-SENSITIVITY THAT PROMPTED THIS TEST IS GONE, and the way it
    # is asserted is set equality between A and C rather than "both are red":
    # two different complaints would satisfy "both red" while the branch order
    # still changed the answer.
    def _messages(snippet: str) -> set[str]:
        return {
            p.split(" ", 1)[1]
            for p in _conflation_errors(source + snippet, bound_flags, rollup_flags, bound_names)
            if p not in baseline
        }

    a_messages = _messages(_BRANCH_AND_CLOSURE_CONFLATIONS[
        "A: tainted in the if-arm, reset in the else-arm"])
    c_messages = _messages(_BRANCH_AND_CLOSURE_CONFLATIONS[
        "C: the same dataflow with the two branches swapped"])
    assert a_messages and a_messages == c_messages, (
        "swapping the two branches of the same dataflow changes the guard's "
        f"answer: A={sorted(a_messages)} C={sorted(c_messages)}"
    )

    # --- A KNOWN ESCAPE, ASSERTED RATHER THAN ONLY DESCRIBED. The frozen text
    # says the reach is not characterised and that any conflation may escape.
    # A negative claim needs a witness or it is just modesty, so here is one
    # measured on the shipped bytes: a use that precedes its assignment in
    # source order but is reached through a loop back-edge is PERMITTED. This
    # is an EXAMPLE of an escape, not a list of the escapes — the list is what
    # a list of escapes cannot be. If this assertion turns red the guard got
    # stronger: move this shape into _BRANCH_AND_CLOSURE_CONFLATIONS with its
    # benign counterpart and delete this block.
    back_edge = """

def _back_edge_added_next_quarter(read):
    entry_truncated = False
    cut = False
    for _i in range(2):
        entry_truncated = entry_truncated or cut
        cut = read.byte_truncated
    return entry_truncated
"""
    assert _conflation_errors(
        source + back_edge, bound_flags, rollup_flags, bound_names
    ) == baseline, (
        "the loop back-edge shape is now REFUSED. That is an improvement, not "
        "a failure: promote it into _BRANCH_AND_CLOSURE_CONFLATIONS with a "
        "benign counterpart and remove this block."
    )

    # --- NO FROZEN SURFACE MAY RE-ACQUIRE A REACH CLAIM. A withdrawal that
    # covers only the manifest leaves the observer module's own comment
    # asserting the opposite, while the back-edge block above ships a fresh
    # site the guard PERMITS. The surface set is enumerated in
    # :func:`_guard_prose_surfaces`, covers the module source as well, and its
    # SIZE is asserted so a surface cannot leave the checked set unnoticed.
    observer_source = OBSERVER_PATH.read_text(encoding="utf-8")
    surfaces = _guard_prose_surfaces(_manifest(), observer_source)
    assert set(surfaces) == {
        "manifest:output_bounds.bound_independence_contract",
        "manifest:scope_limits[AST conflation guard]",
        "source:tests/bootstrap/observe_claude_execution.py",
    }, f"a frozen prose surface that describes the AST guard is missing: {sorted(surfaces)}"
    assert len(surfaces) == 3

    # --- CONTROL OF THE INSTRUMENT, on a synthetic module rather than on the
    # subject, so it cannot pass for the subject's reasons. Positive: a comment
    # and a docstring are both collected. Negative: an identifier is not, so
    # the ban judges what the file SAYS, not what it names. A collector that
    # returned "" would satisfy every phrase ban below for the wrong reason.
    probe = _python_prose(
        '# IT CATCHES A NEW site\ndef f():\n    """A DOC."""\n    catches_a_new_local = 1\n'
    )
    assert "it catches a new site" in probe and "a doc." in probe
    assert "catches_a_new_local" not in probe
    assert _normalise_prose("A\n   B") == "a b"

    # --- PERMITTING ARM: the shipped bytes of all three surfaces.
    assert _reach_claim_errors(surfaces) == [], (
        "a frozen surface asserts a reach that nothing here measures:\n"
        + "\n".join(_reach_claim_errors(surfaces))
    )

    # --- PERMITTING ARM 2, the false-positive control: prose that uses the
    # SAME vocabulary without claiming anything must stay green, or the ban
    # would be firing on the words rather than on the claim.
    benign = observer_source + (
        "\n# The shape list is not exhaustive, and this walk refuses any binding\n"
        "# it can see; nothing about its reach is claimed here.\n"
    )
    assert _reach_claim_errors(_guard_prose_surfaces(_manifest(), benign)) == [], (
        "the ban REFUSED legitimate prose"
    )

    # --- REFUSING ARM 1, the surface that was unguarded: put the withdrawn
    # sentence back into the OBSERVER SOURCE, wrapped across lines exactly as
    # it shipped, so the normaliser is what has to earn the catch.
    reclaimed = observer_source + (
        "\n# It catches a NEW site, not just the three known ones: a fresh\n"
        "# function writing a conflated flag fails on one of the four rules.\n"
    )
    problems = _reach_claim_errors(_guard_prose_surfaces(_manifest(), reclaimed))
    assert [p for p in problems if p.startswith("source:") and "catches a new" in p], (
        f"the observer source may re-acquire the withdrawn reach claim: {problems}"
    )

    # --- REFUSING ARM 2, a DIFFERENT SURFACE and a DIFFERENT phrase: the
    # manifest's scope_limits entry naming a residual set again.
    named_residual = copy.deepcopy(_manifest())
    limits = _case(named_residual, "P0-C01")["scope_limits"]
    index = next(i for i, limit in enumerate(limits) if "AST conflation guard" in limit)
    limits[index] += " The only escape is the loop back-edge."
    problems = _reach_claim_errors(_guard_prose_surfaces(named_residual, observer_source))
    assert [p for p in problems if p.startswith("manifest:scope_limits")
            and "the only escape" in p], problems

    # --- REFUSING ARM 3, a DIFFERENT RULE: dropping the disclaimer is as bad
    # as asserting reach, and a surface can lose it by deletion rather than by
    # gaining a banned phrase. Proven on BOTH kinds of surface.
    silent = copy.deepcopy(_manifest())
    bounds = _case(silent, "P0-C01")["output_bounds"]
    bounds["bound_independence_contract"] = bounds["bound_independence_contract"].replace(
        "ITS REACH IS NOT CHARACTERISED", "IT IS SOUND"
    )
    problems = _reach_claim_errors(_guard_prose_surfaces(silent, observer_source))
    assert [p for p in problems if p.startswith("manifest:output_bounds")
            and "reach is not characterised" in p], problems
    muted_source = observer_source.replace("ITS REACH IS NOT CHARACTERISED", "IT IS SOUND")
    assert muted_source != observer_source
    problems = _reach_claim_errors(_guard_prose_surfaces(_manifest(), muted_source))
    assert [p for p in problems if p.startswith("source:")
            and "reach is not characterised" in p], problems

    # --- REFUSING ARM 4: a surface silently leaving the checked set. Deleting
    # the scope_limits entry must shrink the surface set, which is what the
    # size assertion above refuses.
    dropped = copy.deepcopy(_manifest())
    case_dropped = _case(dropped, "P0-C01")
    case_dropped["scope_limits"] = [
        limit for limit in case_dropped["scope_limits"] if "AST conflation guard" not in limit
    ]
    assert len(_guard_prose_surfaces(dropped, observer_source)) == 2


# ==========================================================================
# 21 — the manifest's smoke_command vs the invocation ci.yml actually runs.
#      10s: two file reads and a handful of string splits.
# ==========================================================================

#: The artifact the P0-A step writes. Used to FIND the invocation in the
#: workflow without keying on the target path, so a drifted target path is
#: reported as a mismatch rather than vanishing as "not found".
P0A_JUNIT_ARTIFACT = "p0a-results.xml"

#: The FULL ``--junitxml`` value, which is OUTSIDE the working tree. Writing it
#: to the repository root added an untracked 28th file on every local run of the
#: frozen command and moved the changeset's own file pin. ``${RUNNER_TEMP:-/tmp}``
#: resolves to the runner scratch directory in Actions and to /tmp elsewhere, so
#: one spelling serves both and ``set -u`` is satisfied. This restatement is not
#: a second home: ``test_manifest_smoke_command_matches_the_ci_pytest_invocation``
#: asserts it is a token of the manifest's ``smoke_command``, which is itself
#: bound token-for-token to ci.yml.
P0A_JUNIT_PATH = "${RUNNER_TEMP:-/tmp}/" + P0A_JUNIT_ARTIFACT


def _expand_runner_temp(spec: str, runner_temp: str | None) -> str:
    """``spec`` with ``${RUNNER_TEMP:-/tmp}`` resolved the way bash resolves it.

    ``:-`` substitutes the default when the variable is UNSET **or empty**, so
    an empty ``RUNNER_TEMP`` must reach ``/tmp`` and not the current directory.
    Spelled here as a tiny reimplementation rather than via ``os.path.expandvars``,
    which does not understand ``:-`` and would leave the whole brace expression
    in place — a silent pass over the case this exists to check.
    """
    return spec.replace("${RUNNER_TEMP:-/tmp}", runner_temp or "/tmp")

#: Verbs that assert a fragment's PRESENCE or absence in a text, as opposed to
#: what BINDS it. A disclosure listing fragments and then denying they appear
#: anywhere refutes itself, because the listing is an appearance. The category
#: is banned rather than the one sentence that was written, so the next
#: author's synonym is refused too.
_APPEARANCE_VERBS: tuple[str, ...] = (
    "appear", "appears", "occur", "occurs", "are present", "is present",
    "are found", "is found", "are named", "are mentioned",
)


def _self_refuting_appearance_claims(clause: str) -> list[str]:
    """Every appearance verb this clause denies, which its own listing refutes."""
    lowered = clause.lower()
    return [
        verb for verb in _APPEARANCE_VERBS
        if f"{verb} in no " in lowered or f"{verb} nowhere" in lowered
    ]


def _joined_shell_lines(text: str) -> list[str]:
    """Every line of ``text`` with ``\\`` continuations joined and space collapsed.

    The P0-A invocation is wrapped across three lines in ``ci.yml``. A raw
    substring scan over the file would compare YAML layout; this compares the
    command.
    """
    joined: list[str] = []
    buffer = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        buffer += stripped
        joined.append(re.sub(r"\s+", " ", buffer).strip())
        buffer = ""
    if buffer:
        joined.append(re.sub(r"\s+", " ", buffer).strip())
    return joined


def _ci_p0a_pytest_invocation(workflow_text: str) -> str | None:
    """The pytest invocation the P0-A step executes, read from ci.yml.

    ``None`` when the workflow does not carry exactly one — zero and two are
    both refusals, and the caller reports which.
    """
    candidates = [
        line
        for line in _joined_shell_lines(workflow_text)
        if line.startswith("python -m pytest ") and P0A_JUNIT_ARTIFACT in line
    ]
    if len(candidates) != 1:
        return None
    # `|| ec=$?` is the step's exit-code capture, not part of the invocation.
    return candidates[0].split("||", 1)[0].strip()


def _smoke_command_binding_errors(workflow_text: str, smoke_command: Any) -> list[str]:
    """Ways the manifest's declared smoke command and ci.yml's disagree."""
    invocation = _ci_p0a_pytest_invocation(workflow_text)
    if invocation is None:
        return [f"ci.yml carries no single pytest invocation writing {P0A_JUNIT_ARTIFACT}"]
    if not isinstance(smoke_command, str) or not smoke_command.strip():
        return ["the manifest declares no smoke_command string"]
    try:
        ci_tokens = shlex.split(invocation)
        manifest_tokens = shlex.split(smoke_command)
    except ValueError as exc:  # pragma: no cover - unbalanced quoting
        return [f"unparsable command: {exc}"]

    problems: list[str] = []
    if ci_tokens != manifest_tokens:
        problems.append(
            "smoke_command and the ci.yml invocation disagree — "
            f"manifest-only={[t for t in manifest_tokens if t not in ci_tokens]} "
            f"ci-only={[t for t in ci_tokens if t not in manifest_tokens]} "
            f"manifest={manifest_tokens} ci={ci_tokens}"
        )
    target = str(NODE_FILE.relative_to(REPO_ROOT))
    for label, tokens in (("manifest", manifest_tokens), ("ci.yml", ci_tokens)):
        if target not in tokens:
            problems.append(f"{label} does not name the frozen node file {target}")
    return problems


@pytest.mark.timeout(10)
def test_manifest_smoke_command_matches_the_ci_pytest_invocation():
    """The manifest's exact smoke command, bound to the bytes CI executes.

    ``amendment:231-235`` requires the manifest to bind "the exact smoke-job
    command". The only mechanical binding it previously had was the substring
    ``--timeout=20``: the pytest TARGET PATH, the ``-o addopts=`` override, the
    timeout method and the JUnit path could all drift from ``ci.yml`` with
    nothing refusing. They are compared token-for-token here, through
    ``shlex``, so line continuations and shell quoting cannot hide a
    difference — and the comparison is ORDERED, so a reshuffle is a mismatch
    too.

    WHAT IS NOT BOUND HERE, named rather than implied: the rest of the step —
    ``set -euo pipefail``, ``pip install jsonschema -q``, the ``|| ec=$?``
    exit-code capture, the ``if:`` prerequisite gate and the JUnit re-read.
    The last two carry their own guards
    (``tests/regression/test_ci_pytest_timeout.py::test_multi_suite_steps_gate_on_their_prerequisites``
    and
    ``test_ci_completeness_gate_refuses_partial_collection_and_permits_the_full_count``
    above, which runs the extracted ``python -c`` verbatim); the first three
    carry none, and the manifest's ``scope_limits`` says so.
    """
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    smoke = _case(_manifest(), "P0-C01")["smoke_command"]
    target = str(NODE_FILE.relative_to(REPO_ROOT))

    # POSITIVE CONTROL OF THE INSTRUMENT: the extractor returns a real
    # invocation naming the frozen node file. An extractor that returned None,
    # "" or the raw YAML line would make every arm below pass for the wrong
    # reason.
    invocation = _ci_p0a_pytest_invocation(workflow)
    assert invocation is not None, "no P0-A invocation extracted from ci.yml"
    assert invocation.startswith("python -m pytest "), invocation
    assert target in invocation, invocation
    assert "||" not in invocation, f"the exit-code capture leaked in: {invocation}"
    assert "\\" not in invocation, f"a line continuation survived joining: {invocation}"

    # --- PERMITTING ARM: the shipped bytes of both surfaces agree.
    assert _smoke_command_binding_errors(workflow, smoke) == [], (
        "\n".join(_smoke_command_binding_errors(workflow, smoke))
    )

    # --- PERMITTING ARM 2, the false-positive control: the SAME command
    # rewrapped across different lines must stay green, or this would be
    # binding YAML layout rather than the command.
    rewrapped = workflow.replace(
        f"python -m pytest {target} \\",
        f"python -m pytest \\\n            {target} \\",
    )
    assert rewrapped != workflow, "the rewrap control did not change the workflow text"
    assert _smoke_command_binding_errors(rewrapped, smoke) == [], (
        "the comparison refused an identical command wrapped differently"
    )

    # --- REFUSING ARMS. Five shapes, none of them the timeout substring the
    # previous check already covered.
    drifted_target = smoke.replace(target, "tests/bootstrap/test_something_else.py")
    assert drifted_target != smoke
    problems = _smoke_command_binding_errors(workflow, drifted_target)
    assert any("does not name the frozen node file" in p for p in problems), problems

    # The JUnit target is OUTSIDE the working tree, and this restatement of it
    # is pinned to the manifest here rather than trusted. Both env states are
    # expanded: RUNNER_TEMP set (Actions) and unset or empty (local), because
    # `${VAR:-default}` substitutes on empty as well as on unset.
    assert f"--junitxml={P0A_JUNIT_PATH}" in shlex.split(smoke), (
        f"smoke_command does not carry {P0A_JUNIT_PATH!r}: {shlex.split(smoke)}"
    )
    for runner_temp in ("/runner/work/_temp", "", None):
        resolved = _expand_runner_temp(P0A_JUNIT_PATH, runner_temp)
        assert Path(resolved).is_absolute(), (runner_temp, resolved)
        assert not str(Path(resolved)).startswith(str(REPO_ROOT) + os.sep), (
            f"with RUNNER_TEMP={runner_temp!r} the JUnit report lands inside the "
            f"working tree at {resolved}, where a local run of the frozen "
            "command adds an untracked file"
        )

    dropped_flag = smoke.replace(f" --junitxml={P0A_JUNIT_PATH}", "")
    assert dropped_flag != smoke
    assert _smoke_command_binding_errors(workflow, dropped_flag) != []

    reordered_tokens = shlex.split(smoke)
    reordered_tokens[-1], reordered_tokens[-2] = reordered_tokens[-2], reordered_tokens[-1]
    assert _smoke_command_binding_errors(workflow, shlex.join(reordered_tokens)) != [], (
        "token ORDER is unbound, so a reshuffled command reads as a match"
    )

    workflow_drift = workflow.replace(
        f"python -m pytest {target} \\", "python -m pytest tests/bootstrap/ \\"
    )
    assert workflow_drift != workflow
    assert _smoke_command_binding_errors(workflow_drift, smoke) != [], (
        "drift on the WORKFLOW side is unbound"
    )

    duplicated = workflow.replace(
        f"--junitxml={P0A_JUNIT_PATH} || ec=$?",
        f"--junitxml={P0A_JUNIT_PATH} || ec=$?\n          "
        f"python -m pytest {target} --junitxml={P0A_JUNIT_PATH}",
    )
    assert duplicated != workflow
    assert _smoke_command_binding_errors(duplicated, smoke) != [], (
        "two P0-A invocations read as one"
    )

    # --- THE TWO MANIFEST FIELDS MAY NOT DRIFT APART. `smoke_command` and
    # `run_block` now carry the same invocation, which is a second home for one
    # set of bytes. It is not left to convention: the invocation read back OUT
    # of run_block, by the same extractor that reads it out of ci.yml, must be
    # smoke_command token for token. Every direction of drift is refused —
    # editing ci.yml alone fails the arm above, editing either field alone
    # fails one of these two.
    run_block = _case(_manifest(), "P0-C01")["run_block"]
    assert _smoke_command_binding_errors("\n".join(run_block), smoke) == [], (
        "\n".join(_smoke_command_binding_errors("\n".join(run_block), smoke))
    )

    # CONTROL, a different shape from the drifts driven above: the comparison
    # can fire on run_block, not only on the workflow. Drop one flag from the
    # run_block copy and the same call must report.
    thinned = [line.replace(" --timeout-method=signal", "") for line in run_block]
    assert thinned != run_block, "the run_block control changed nothing"
    assert _smoke_command_binding_errors("\n".join(thinned), smoke) != [], (
        "a run_block whose invocation lost a flag was permitted"
    )

    # --- THE UNBOUND CLAUSE, MADE A MEASUREMENT. The same scope_limits entry
    # names the step fragments it says no manifest field BINDS. Those fragments
    # are read OUT OF that sentence -- the clause is the operand -- and each is
    # checked absent from the token list this test binds. Written the other way
    # round ("appear in no manifest field") the sentence refuted itself, since
    # it is a manifest field and they appear in it; what is true and checkable
    # is that nothing BINDS them, and this is the check.
    unbound_clause = next(
        entry for entry in _case(_manifest(), "P0-C01")["scope_limits"]
        if "WHAT REMAINS UNBOUND" in entry
    ).split("WHAT REMAINS UNBOUND")[1].split(" The step's")[0]
    named = [
        match.group(1) or match.group(2)
        for match in _BACKTICK_SPAN_RE.finditer(unbound_clause)
    ]
    assert len(named) >= 3, named
    # The denominator is EVERY binding, not just this field's. `run_block` now
    # freezes the rest of the step body, so a clause calling a fragment unbound
    # must be measured against both fields or it would read true by consulting
    # the narrower one. `.split()` rather than `shlex.split()`: a run_block line
    # ends in a `\` continuation, which shlex refuses outright.
    bound_tokens = set(shlex.split(smoke))
    for line in _case(_manifest(), "P0-C01")["run_block"]:
        bound_tokens |= set(str(line).split())
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")
    for fragment in named:
        # MEASURED FACT 1: the fragment DOES appear in a manifest field -- the
        # very entry naming it. Any clause claiming non-APPEARANCE is false.
        assert fragment in manifest_text, fragment
        # MEASURED FACT 2: no field BINDS it. That is the property that holds.
        assert not (set(shlex.split(fragment)) & bound_tokens), (
            f"the entry says no manifest field binds {fragment!r}, but "
            f"smoke_command carries {sorted(set(shlex.split(fragment)) & bound_tokens)}"
        )

    # CONTROL OF FACT 2, a different shape: the empty intersection above is a
    # measurement, not an emptiness by construction. A token the smoke command
    # really carries must be caught by the same comparison.
    carried = next(token for token in shlex.split(smoke) if token.startswith("--timeout"))
    assert set(shlex.split(carried)) & bound_tokens, (
        "the intersection cannot see a token the smoke command really carries"
    )

    # Given fact 1, the clause may not assert NON-APPEARANCE in any spelling.
    # A category is removed rather than one sentence banned: any appearance
    # verb applied to fragments that demonstrably appear is a self-refuting
    # claim, whichever verb is reached for next.
    assert _self_refuting_appearance_claims(unbound_clause) == [], (
        _self_refuting_appearance_claims(unbound_clause)
    )

    # REFUSING ARM for that rule, in a spelling that is NOT the one this
    # changeset corrected: a guard pinned to the original wording would pass
    # the next author's synonym straight through.
    for spelling in ("occur in no manifest field", "are present in no manifest field"):
        assert _self_refuting_appearance_claims(f"is the rest of the step: they {spelling}."), (
            f"a non-appearance claim spelled {spelling!r} was permitted"
        )


# ==========================================================================
# 22 — which `pre`/`post` pair can differ, and which cannot.
#      20s: one observer subprocess plus one AST parse.
# ==========================================================================

#: What every frozen surface describing the git plane must say, normalised.
_GIT_DISCLOSURE_PHRASES: tuple[str, ...] = ("single-sampled at a-time", "copy of `pre`")

#: The surfaces that must say it. A surface that cannot be found is OMITTED
#: rather than defaulted, so the caller's size assertion refuses a dropped one.
_GIT_DISCLOSURE_LABELS = {
    "manifest:scope_limits[git single-sample]",
    "schema:$defs/git_plane",
    "schema:$defs/git_plane/properties/post",
    "source:tests/bootstrap/observe_claude_execution.py",
}

#: Two claims MEASURED FALSE against the shipped bytes, banned everywhere the
#: two pairs are described:
#:
#: * ``_filesystem_planes`` calls ``_read_json`` ONCE and normalises two
#:   distinct fields of that single document, so the filesystem pair is not two
#:   separate readings of the file. The AST count below measures it.
#: * Two sequential ``_git_snapshot`` calls are not literally simultaneous, so a
#:   hypothetical second sample does not observe one indivisible moment. What is
#:   true is that no controlled child action separates possible git samples.
#:
#: Spelled as fragments so this module's own prose does not trip the check it
#: defines: the banned strings appear here only inside this tuple, which is
#: CODE and therefore outside ``_python_prose``.
_REFUTED_PAIR_PHRASES: tuple[str, ...] = ("independent reads", "same instant twice")


def _refuted_pair_claims(texts: dict[str, str]) -> list[str]:
    """Surfaces that re-acquired a claim measured false against the bytes."""
    return [
        f"{label}: re-acquired the refuted claim {phrase!r}"
        for label in sorted(texts)
        for phrase in _REFUTED_PAIR_PHRASES
        if phrase in texts[label]
    ]


def _function_source(source: str, name: str) -> str:
    """The source segment of the module-level function ``name``."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment, f"no source segment for {name}"
            return segment
    raise AssertionError(f"{name} is not a module-level function")


def _pair_is_duplicate(plane: dict[str, Any]) -> bool:
    """Whether a plane's ``pre`` and ``post`` are the same value."""
    return plane["pre"] == plane["post"]


def _definition_and_call_counts(source: str, name: str) -> tuple[int, int]:
    """``(definitions, direct calls)`` of ``name`` in ``source``, by AST.

    Not by grep: a comment or docstring naming the function is text, not a
    call, and the disclosure below deliberately names ``_git_snapshot`` in
    prose — ``grep -c`` reports three for a function defined once and called
    once.
    """
    tree = ast.parse(source)
    definitions = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    calls = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    )
    return definitions, calls


def _git_disclosure_surfaces(
    manifest: dict[str, Any], schema: dict[str, Any], observer_source: str
) -> dict[str, str]:
    """The frozen prose surfaces that describe the git plane's sampling."""
    surfaces: dict[str, str] = {}
    limits = [
        limit
        for limit in _case(manifest, "P0-C01").get("scope_limits", [])
        if "single-sampled" in limit.lower() and "git" in limit.lower()
    ]
    if len(limits) == 1:
        surfaces["manifest:scope_limits[git single-sample]"] = _normalise_prose(limits[0])
    plane = schema.get("$defs", {}).get("git_plane", {})
    if isinstance(plane.get("description"), str):
        surfaces["schema:$defs/git_plane"] = _normalise_prose(plane["description"])
    post = plane.get("properties", {}).get("post", {})
    if isinstance(post.get("description"), str):
        surfaces["schema:$defs/git_plane/properties/post"] = _normalise_prose(
            post["description"]
        )
    surfaces["source:tests/bootstrap/observe_claude_execution.py"] = _python_prose(
        observer_source
    )
    return surfaces


def _git_disclosure_errors(surfaces: dict[str, str]) -> list[str]:
    """Surfaces that dropped a required phrase."""
    problems: list[str] = []
    for label in sorted(surfaces):
        for phrase in _GIT_DISCLOSURE_PHRASES:
            if phrase not in surfaces[label]:
                problems.append(f"{label}: no longer states {phrase!r}")
    return problems


@pytest.mark.timeout(20)
def test_git_plane_is_single_sampled_and_the_filesystem_pair_is_not(tmp_path):
    """Two ``pre``/``post`` pairs in one packet: one differential, one a copy.

    ``amendment:196-198`` promises "pre/post Git state" in the same sentence as
    "a recursive pre/post path/digest/mode inventory". The second pair is
    genuinely differential — two separately recorded snapshots within ONE
    inventory document, not two reads of it: ``_filesystem_planes`` calls
    ``_read_json`` once and normalises two distinct fields of that single
    document, and those two fields do differ on the shipped fixtures. The
    first pair is not differential, and could not be: ``capture()`` executes
    no child (``run.child_executed`` is ``const: false``), so no controlled
    child action separates possible git samples at P0-A. Two sequential calls
    are not literally simultaneous, but nothing this module controls happens
    between them, so a second call would not be the before/after differential
    measurement the pair's shape suggests.

    So the duplication is DISCLOSED rather than manufactured away, and this
    test is what stops the disclosure from going stale: it measures the
    duplication on the emitted packet, measures the single call site by AST,
    and refuses any of the four frozen surfaces dropping the words. If a later
    rung wires a genuine second sample, the first assertion goes red and the
    disclosure has to be revisited rather than silently becoming false.
    """
    packet = _packet_from(OBSERVER_PATH, _make_run_root(tmp_path / "clean"))
    git = packet["observation"]["git"]
    filesystem = packet["observation"]["filesystem"]

    # --- MEASURED on the emitted packet: the git pair is a duplicate, and the
    # plane's status is `pre`'s because there is no second reading to worst.
    assert _pair_is_duplicate(git), git
    assert git["observation_status"] == git["pre"]["observation_status"]

    # --- NEGATIVE CONTROL, SAME SPELLING and DIFFERENT SHAPE: the other
    # `pre`/`post` pair in the SAME packet does differ. Without this, the
    # assertion above would be indistinguishable from a predicate that reports
    # True for every pair it is shown.
    assert not _pair_is_duplicate(filesystem)
    appeared = set(filesystem["post"]["entries"]) - set(filesystem["pre"]["entries"])
    assert appeared, "the filesystem pair carries no difference to control with"

    # --- SECOND CONTROL, on the git pair itself rather than on its neighbour:
    # the predicate flips when that pair really differs.
    drifted = copy.deepcopy(git)
    drifted["post"]["head"] = "0" * 40
    assert not _pair_is_duplicate(drifted)

    # --- THE SOURCE-LEVEL REASON: one definition, one call site.
    source = OBSERVER_PATH.read_text(encoding="utf-8")
    assert _definition_and_call_counts(source, "_git_snapshot") == (1, 1), (
        "the git snapshot is no longer taken exactly once — if a second, real "
        "sample was added, update the disclosure surfaces below"
    )
    # CONTROL OF THAT COUNTER: it can report more than one call, and it can
    # report nothing. A counter stuck at (1, 1) would prove nothing above.
    reader_defs, reader_calls = _definition_and_call_counts(source, "_read_json")
    assert reader_defs == 1 and reader_calls > 1, (reader_defs, reader_calls)
    assert _definition_and_call_counts(source, "_no_such_helper_exists") == (0, 0)

    # --- DISCLOSURE, PERMITTING ARM: four frozen surfaces say so today.
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest = _manifest()
    surfaces = _git_disclosure_surfaces(manifest, schema, source)
    assert set(surfaces) == _GIT_DISCLOSURE_LABELS, (
        f"a surface describing the git plane's sampling is missing: {sorted(surfaces)}"
    )
    assert _git_disclosure_errors(surfaces) == [], "\n".join(_git_disclosure_errors(surfaces))

    # --- REFUSING ARM 1: the manifest entry deleted. The surface leaves the
    # checked set, which the size assertion above is what refuses.
    dropped = copy.deepcopy(manifest)
    case_dropped = _case(dropped, "P0-C01")
    case_dropped["scope_limits"] = [
        limit
        for limit in case_dropped["scope_limits"]
        if not ("single-sampled" in limit.lower() and "git" in limit.lower())
    ]
    assert set(_git_disclosure_surfaces(dropped, schema, source)) != _GIT_DISCLOSURE_LABELS

    # --- REFUSING ARM 2, a DIFFERENT SURFACE and a DIFFERENT RULE: the schema
    # node keeps its description but stops saying the pair is single-sampled.
    muted = copy.deepcopy(schema)
    muted["$defs"]["git_plane"]["description"] = (
        "Git state around the controlled child, recorded before and after."
    )
    problems = _git_disclosure_errors(_git_disclosure_surfaces(manifest, muted, source))
    assert [p for p in problems if p.startswith("schema:$defs/git_plane:")], problems

    # --- REFUSING ARM 3, a THIRD SURFACE: the field-level annotation removed
    # altogether, so a reader of `post` alone meets no caveat.
    stripped = copy.deepcopy(schema)
    del stripped["$defs"]["git_plane"]["properties"]["post"]["description"]
    assert set(_git_disclosure_surfaces(manifest, stripped, source)) != _GIT_DISCLOSURE_LABELS

    # --- REFUSING ARM 4, the OBSERVER'S OWN COMMENT, wrapped across lines
    # exactly as it ships, so the normaliser is what has to earn the catch.
    silent_source = source.replace("SINGLE-SAMPLED AT A-TIME", "SAMPLED BEFORE AND AFTER")
    assert silent_source != source
    problems = _git_disclosure_errors(_git_disclosure_surfaces(manifest, schema, silent_source))
    assert [p for p in problems if p.startswith("source:")], problems

    # ======================================================================
    # WHAT THE FILESYSTEM PAIR ACTUALLY IS, measured rather than described.
    # The surfaces above used to call it two separate readings of the
    # inventory file. It is not: one reader call, two recorded fields.
    # ======================================================================
    fs_source = _function_source(source, "_filesystem_planes")
    assert _definition_and_call_counts(fs_source, "_read_json") == (0, 1), (
        "the filesystem plane no longer reads its inventory exactly once — the "
        "surfaces say ONE read and TWO recorded fields, so update them"
    )
    assert _definition_and_call_counts(fs_source, "normalize") == (1, 2), (
        "the filesystem plane no longer records exactly two snapshots from "
        "that one document"
    )
    # CONTROL OF THAT COUNTER on this narrower subject: it can report nothing,
    # and it does not simply echo the whole module. `_git_snapshot` is not
    # called inside `_filesystem_planes` at all.
    assert _definition_and_call_counts(fs_source, "_no_such_helper_exists") == (0, 0)
    assert _definition_and_call_counts(fs_source, "_git_snapshot") == (0, 0)

    # --- THE REFUTED CLAIMS, PERMITTING ARM: no surface makes either of them
    # today. This module's own prose is checked too — a test that documents a
    # claim it bans elsewhere is the surface a reader would meet first.
    pair_texts = dict(surfaces)
    pair_texts["source:tests/bootstrap/test_plugin_carrier_bootstrap.py"] = _python_prose(
        Path(__file__).read_text(encoding="utf-8")
    )
    assert len(pair_texts) == len(_GIT_DISCLOSURE_LABELS) + 1, sorted(pair_texts)
    assert _refuted_pair_claims(pair_texts) == [], "\n".join(_refuted_pair_claims(pair_texts))

    # --- REFUSING ARM, every phrase against every surface, so neither claim
    # can come back on a surface nobody happened to probe.
    for phrase in _REFUTED_PAIR_PHRASES:
        for label in sorted(pair_texts):
            regressed = dict(pair_texts)
            regressed[label] = f"{pair_texts[label]} the pair is {phrase}"
            flagged = _refuted_pair_claims(regressed)
            assert [p for p in flagged if p.startswith(f"{label}:")], (label, phrase)

    # --- CONTROL OF THAT CHECKER, DIFFERENT SHAPE: the corrected wording that
    # replaced both claims must NOT be flagged, or the check is refusing the
    # subject rather than the false claim about it.
    assert _refuted_pair_claims(
        {
            "corrected": _normalise_prose(
                "two separately recorded snapshots within one inventory document, "
                "and no controlled child action separates possible git samples "
                "at P0-A"
            )
        }
    ) == []


# ==========================================================================
# 23 — a DELETED hook receipt cannot read as a quiet hook. 20s: four
#      observer subprocesses over the committed fixtures.
# ==========================================================================

#: The committed valid/debug.log, decomposed so one receipt can be removed
#: without disturbing anything else. Both ids also appear as `hook_event`
#: records in valid/stream.jsonl, which is what makes a deleted receipt
#: recoverable evidence rather than an absence nobody could have noticed.
_DEBUG_HEAD = (
    f"[2026-09-07T09:15:02.114Z] [DEBUG] session start session_id={SESSION_UUID}"
)
_DEBUG_SOURCES = (
    "[2026-09-07T09:15:02.203Z] [DEBUG] settings sources resolved order=user,project,local"
)
_RECEIPT_BENIGN = (
    "[2026-09-07T09:15:02.481Z] [DEBUG] hook PreToolUse tool_use_id=toolu_01AAA "
    "command=claude-observer-canary exit=0 stdout_bytes=0"
)
_RECEIPT_NONZERO = (
    "[2026-09-07T09:15:03.902Z] [DEBUG] hook PreToolUse tool_use_id=toolu_02BBB "
    "command=claude-observer-canary exit=2 stdout_bytes=0"
)
_DEBUG_TAIL = "[2026-09-07T09:15:04.220Z] [DEBUG] session end reason=complete"


def _packet_with_debug_lines(work: Path, lines: list[str]) -> dict[str, Any]:
    """A packet over the committed fixtures with ``lines`` as the debug log."""
    run_root = _make_run_root(work)
    (run_root / "debug.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _packet_from(OBSERVER_PATH, run_root)


def _receipt_notes(decision: dict[str, Any]) -> list[str]:
    """The discrepancies that name a missing receipt, and only those."""
    return [item for item in decision["discrepancies"] if "no debug receipt" in item]


@pytest.mark.timeout(20)
def test_a_deleted_hook_receipt_cannot_be_masked_by_a_surviving_one(tmp_path):
    """Deleting ONE non-zero receipt must not produce a genuinely-clean packet.

    The two identity sets are different observations: the stream's
    ``hook_event`` records say a hook FIRED, and the debug receipts are the
    only place a hook's EXIT CODE is observable. Unioning
    them into a single ``hook_ids`` set before comparing anything, so removing
    the single non-zero receipt from the debug log — while leaving its stream
    ``hook_event`` and the benign receipt in place — restored the id from the
    stream side, kept the symmetric-difference orphan set empty, and dropped
    the non-zero exit with no trace. The suppressed packet was
    indistinguishable at D08 and D09 from a run where both hooks really did
    exit zero.

    Four cells, and the fourth is the one that makes the other three mean
    something: a guard that refuses the intact case is worse than the defect.
    """
    # --- CELL 1, BASELINE: the non-zero receipt is present and D09 sees it.
    baseline = _packet_with_debug_lines(
        tmp_path / "baseline",
        [_DEBUG_HEAD, _DEBUG_SOURCES, _RECEIPT_BENIGN, _RECEIPT_NONZERO, _DEBUG_TAIL],
    )
    base_d09 = _decision_of(baseline, "D09_HIDDEN_HOOK_NONZERO")
    assert any("exited 2" in item for item in base_d09["discrepancies"]), base_d09
    assert _receipt_notes(base_d09) == [], "no receipt is missing in the baseline"
    assert baseline["observation"]["hooks"]["hook_events_without_receipt"] == []

    # --- CELL 2, PERMITTING ARM: both receipts present and both exit zero.
    # Nothing is deleted, so the packet must reach OBSERVED with no
    # discrepancy at all. Without this cell every refusal below would be
    # indistinguishable from a decision that can never be clean.
    intact = _packet_with_debug_lines(
        tmp_path / "intact",
        [
            _DEBUG_HEAD,
            _DEBUG_SOURCES,
            _RECEIPT_BENIGN,
            _RECEIPT_NONZERO.replace("exit=2", "exit=0"),
            _DEBUG_TAIL,
        ],
    )
    intact_d09 = _decision_of(intact, "D09_HIDDEN_HOOK_NONZERO")
    assert intact_d09["observation_status"] == "OBSERVED", intact_d09
    assert intact_d09["discrepancies"] == [], intact_d09
    assert intact["observation"]["hooks"]["hook_events_without_receipt"] == []
    assert base_d09 != intact_d09, (
        "instrument control: the baseline must differ from the clean cell, or "
        "the comparison below proves nothing"
    )

    # --- CELL 3, REFUSING ARM A: delete ONLY the non-zero receipt. Its stream
    # `hook_event` survives and so does the benign receipt, so `joins` stays
    # populated and nothing looks absent.
    suppressed = _packet_with_debug_lines(
        tmp_path / "suppressed",
        [_DEBUG_HEAD, _DEBUG_SOURCES, _RECEIPT_BENIGN, _DEBUG_TAIL],
    )
    sup_hooks = suppressed["observation"]["hooks"]
    assert sup_hooks["hook_events_without_receipt"] == ["toolu_02BBB"], sup_hooks
    assert len(sup_hooks["joins"]) == 1, (
        "the benign receipt must survive, or this is the all-receipts-gone "
        "case rather than the selective-suppression one"
    )
    assert sup_hooks["orphan_tool_use_ids"] == [], (
        "the stream hook_event restores the id for the tool_use join, which "
        "is precisely why the orphan set cannot be what catches this"
    )
    sup_d09 = _decision_of(suppressed, "D09_HIDDEN_HOOK_NONZERO")
    assert sup_d09["observation_status"] == "UNMEASURED", sup_d09
    assert any("toolu_02BBB" in item for item in _receipt_notes(sup_d09)), sup_d09
    assert sup_d09 != intact_d09, (
        "THE DEFECT: a deleted non-zero receipt read as a genuinely clean run"
    )

    # --- CELL 4, REFUSING ARM B, a DIFFERENT SHAPE: delete the BENIGN receipt
    # instead and leave the non-zero one in place. The deleted receipt is the
    # harmless one and the surviving evidence already carries an anomaly, so a
    # guard keyed on "did we lose the interesting record" would miss it. The
    # covered class is *any* stream hook_event with no debug receipt,
    # regardless of what the deleted receipt contained.
    benign_gone = _packet_with_debug_lines(
        tmp_path / "benign-gone",
        [_DEBUG_HEAD, _DEBUG_SOURCES, _RECEIPT_NONZERO, _DEBUG_TAIL],
    )
    assert benign_gone["observation"]["hooks"]["hook_events_without_receipt"] == [
        "toolu_01AAA"
    ]
    gone_d09 = _decision_of(benign_gone, "D09_HIDDEN_HOOK_NONZERO")
    assert gone_d09["observation_status"] == "UNMEASURED", gone_d09
    assert any("toolu_01AAA" in item for item in _receipt_notes(gone_d09)), gone_d09
    assert any("exited 2" in item for item in gone_d09["discrepancies"]), (
        "the surviving non-zero receipt must still be reported on its own terms"
    )

    # --- SCOPE, not global noise. D08 asks a different question — does every
    # tool_use have a lifecycle record from EITHER source — and the stream
    # `hook_event` answers it in all four cells. If D08 had degraded too, the
    # refusal above would be a plane-wide alarm rather than evidence-specific.
    for name, packet in (
        ("baseline", baseline), ("intact", intact),
        ("suppressed", suppressed), ("benign_gone", benign_gone),
    ):
        d08 = _decision_of(packet, "D08_HOOK_TOOL_USE_ID_JOIN")
        assert d08["observation_status"] == "OBSERVED", (name, d08)
        assert d08["discrepancies"] == [], (name, d08)

    # --- TRANSCRIPT SCOPING is unchanged: D09 still does not read it, so the
    # new discrepancy cannot have been smuggled in through a fourth plane.
    assert "transcript" not in observer.DECISION_EVIDENCE_PLANES["D09_HIDDEN_HOOK_NONZERO"]
    for packet in (suppressed, benign_gone):
        assert _decision_of(packet, "D09_HIDDEN_HOOK_NONZERO")["evidence_bounds"] == {
            "any_bound_truncated": False,
            "malformed": False,
            "notes": [],
        }, "the degradation must come from the missing receipt, not from a bound"


def _packet_with_stream_and_debug(
    work: Path, stream: list[dict[str, Any]], lines: list[str]
) -> dict[str, Any]:
    """A packet over the committed fixtures with both hook inputs rewritten."""
    run_root = _make_run_root(work)
    (run_root / observer.EVIDENCE_STREAM).write_text(
        "".join(json.dumps(record) + "\n" for record in stream), encoding="utf-8"
    )
    (run_root / "debug.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _packet_from(OBSERVER_PATH, run_root)


@pytest.mark.timeout(20)
def test_a_second_hook_event_on_a_receipted_id_cannot_hide_its_missing_receipt(tmp_path):
    """MULTIPLICITY, not membership: the same id on both sides, different counts.

    Claude fires ``PreToolUse`` AND ``PostToolUse`` for one tool call, both
    carrying the SAME ``tool_use_id``. The receiptless comparison was a set
    difference over BARE IDS on both sides, so a second event on an
    already-receipted id was absorbed: with a ``PostToolUse`` stream record
    added and its receipt absent, ``hook_events_without_receipt`` stayed empty
    and D09 reported zero discrepancies, while the SAME deletion on a UNIQUE id
    was named. The debug side kept multiplicity all along — ``joins`` is a list
    — and only the stream side collapsed it.

    THE ARMS ARE ABOUT COUNTS, NOT MEMBERS. Every cell below has
    ``toolu_01AAA`` present on BOTH sides, so a guard keyed on "is this id
    known to the debug log" passes all of them; what separates the cells is how
    many events that id carries against how many receipts.
    """
    pre = {
        "type": "hook_event",
        "tool_use_id": "toolu_01AAA",
        "hook_event_name": "PreToolUse",
    }
    post = dict(pre, hook_event_name="PostToolUse")
    call = {"type": "tool_use", "tool_use_id": "toolu_01AAA", "outcome": "success"}
    receipt_pre = (
        "[2026-09-07T09:15:02.481Z] [DEBUG] hook PreToolUse "
        "tool_use_id=toolu_01AAA command=claude-observer-canary exit=0 "
        "stdout_bytes=0"
    )
    receipt_post = receipt_pre.replace("hook PreToolUse", "hook PostToolUse")

    def hooks_of(label: str, stream: list[dict[str, Any]], lines: list[str]):
        packet = _packet_with_stream_and_debug(
            tmp_path / label, stream, [_DEBUG_HEAD, _DEBUG_SOURCES] + lines + [_DEBUG_TAIL]
        )
        return packet["observation"]["hooks"], _decision_of(
            packet, "D09_HIDDEN_HOOK_NONZERO"
        )

    # --- PERMITTING ARM: TWO events on one id, TWO receipts. Counts agree and
    # nothing is named. Without this the refusals below would be satisfied by a
    # comparison that reports every repeated id.
    both, both_d09 = hooks_of("both", [call, pre, post], [receipt_pre, receipt_post])
    assert both["hook_events_without_receipt"] == [], both
    assert both_d09["observation_status"] == "OBSERVED", both_d09
    assert both_d09["discrepancies"] == [], both_d09

    # --- REFUSING ARM: the SAME id, still present on both sides, with TWO
    # events and ONE receipt. This is the reproduced fail-open.
    lost, lost_d09 = hooks_of("lost-post", [call, pre, post], [receipt_pre])
    assert lost["hook_events_without_receipt"] == ["toolu_01AAA"], lost
    assert lost_d09["observation_status"] == "UNMEASURED", lost_d09
    assert any("toolu_01AAA" in item for item in _receipt_notes(lost_d09)), lost_d09
    assert lost_d09 != both_d09, (
        "THE DEFECT: a receipt deleted for a second event on a receipted id "
        "read exactly like a run where both receipts were present"
    )

    # --- CONTROL ON THE MEMBERSHIP QUESTION: the bare-id sets are IDENTICAL in
    # the permitting and refusing cells, so no comparison over ids alone could
    # tell them apart. This is what makes the arms above about multiplicity.
    assert lost["orphan_tool_use_ids"] == both["orphan_tool_use_ids"] == [], (
        lost, both,
    )

    # --- REFUSING ARM B, A DIFFERENT SHAPE: the counts MATCH and the pairing
    # still does not. One event, one receipt, but the receipt is for the OTHER
    # lifecycle event — so a fix that compared COUNTS per id rather than pairs
    # would permit it.
    crossed, crossed_d09 = hooks_of("crossed", [call, pre], [receipt_post])
    assert crossed["hook_events_without_receipt"] == ["toolu_01AAA"], crossed
    assert crossed_d09["observation_status"] == "UNMEASURED", crossed_d09
    assert len(crossed["joins"]) == 1, (
        "the receipt must survive, or this is the no-receipts case rather than "
        "the mispaired one"
    )

    # --- SCOPE: D08 asks whether every tool call has a lifecycle partner from
    # EITHER source, and a PostToolUse on a known id is a partner. It must stay
    # clean in every cell, or the refusals above are a plane-wide alarm.
    for label, stream, lines in (
        ("both", [call, pre, post], [receipt_pre, receipt_post]),
        ("lost-post", [call, pre, post], [receipt_pre]),
        ("crossed", [call, pre], [receipt_post]),
    ):
        packet = _packet_with_stream_and_debug(
            tmp_path / f"d08-{label}", stream,
            [_DEBUG_HEAD, _DEBUG_SOURCES] + lines + [_DEBUG_TAIL],
        )
        d08 = _decision_of(packet, "D08_HOOK_TOOL_USE_ID_JOIN")
        assert d08["observation_status"] == "OBSERVED", (label, d08)
        assert d08["discrepancies"] == [], (label, d08)


@pytest.mark.timeout(20)
def test_two_hook_receipts_merged_onto_one_debug_line_are_both_read(tmp_path):
    """``re.search`` returns one match per line; a receipt log is not one per line.

    Both debug readers were line-anchored and used ``re.search``, and
    ``_debug_unparsable`` ``continue``d as soon as the first receipt on a line
    parsed — so the line was never offered to the shape patterns either. Merging
    a non-zero receipt onto a line that already carried a benign one produced a
    packet with D09 at zero discrepancies, while ``grep -o 'exit=[0-9]*'`` on
    the SAME BYTES reported the ``exit=2``. The sibling JSONL reader was
    fail-closed on the identical attack all along: two records on one line raise
    "Extra data" and the plane reports ERROR.

    The fix is a RESIDUE — receipts CLAIMED minus receipts READ — and this test
    drives the WHOLE-RECEIPT arrangement of it: N complete receipts merged onto
    one line, each carrying its own ``tool_use_id``. An earlier revision of
    this docstring said the residue "closes N-per-line for every N"; that named
    a mechanism and was false of the behaviour, because the claim was counted
    by ``tool_use_id=`` lexeme and a second bare ``exit=`` pair brings no
    second id. The withdrawn half is driven by
    ``test_a_second_exit_pair_on_a_receipt_line_is_accounted_in_both_directions``.
    """
    benign = (
        "[2026-09-07T09:15:02.481Z] [DEBUG] hook PreToolUse "
        "tool_use_id=toolu_01AAA command=claude-observer-canary exit=0 "
        "stdout_bytes=0"
    )
    nonzero = (
        "hook PreToolUse tool_use_id=toolu_02BBB "
        "command=claude-observer-canary exit=2 stdout_bytes=0"
    )

    def d09_of(label: str, lines: list[str]) -> dict[str, Any]:
        return _decision_of(
            _packet_with_debug_lines(tmp_path / label, lines),
            "D09_HIDDEN_HOOK_NONZERO",
        )

    # --- PERMITTING ARM: one receipt per line, both benign. Nothing is named.
    quiet = d09_of(
        "quiet",
        [_DEBUG_HEAD, _DEBUG_SOURCES, benign,
         benign.replace("toolu_01AAA", "toolu_02BBB"), _DEBUG_TAIL],
    )
    assert quiet["observation_status"] == "OBSERVED", quiet
    assert quiet["discrepancies"] == [], quiet

    # --- POSITIVE CONTROL: the same non-zero receipt on its OWN line is named.
    # Without this the refusal below could be about the merge rather than about
    # the exit code.
    separate = d09_of(
        "separate",
        [_DEBUG_HEAD, _DEBUG_SOURCES, benign, f"[DEBUG] {nonzero}", _DEBUG_TAIL],
    )
    assert any("exited 2" in item for item in separate["discrepancies"]), separate

    # --- REFUSING ARM: MERGED onto the benign line. The reproduced fail-open.
    merged = d09_of(
        "merged", [_DEBUG_HEAD, _DEBUG_SOURCES, f"{benign} {nonzero}", _DEBUG_TAIL]
    )
    assert any("exited 2" in item for item in merged["discrepancies"]), merged
    assert merged != quiet, "THE DEFECT: a merged non-zero receipt read as clean"

    # --- THE THIRD-PARTY RECOMPUTATION, run on the same bytes with an ordinary
    # tool. The manifest claims the evidence is recomputable by a third party;
    # this is that claim, executed. Before the fix `grep` saw the exit=2 and the
    # observer did not.
    merged_text = f"{benign} {nonzero}"
    assert re.findall(r"exit=(-?\d+)", merged_text) == ["0", "2"]
    records, lost = observer._debug_line_receipts(merged_text)
    assert [r["exit_code"] for r in records] == [0, 2], (records, lost)
    assert lost == 0, "both receipts were READ; nothing should be in the residue"

    # --- REFUSING ARM B, A DIFFERENT SHAPE AND A DIFFERENT N: THREE receipts on
    # one line, the third one PERMUTED so `_DEBUG_HOOK_RE` cannot read it. The
    # residue must report exactly one lost receipt, so the plane goes ERROR
    # rather than merely reading the two it managed. A fix scoped to "read the
    # second match too" would report zero here.
    permuted = (
        "hook PreToolUse command=claude-observer-canary "
        "tool_use_id=toolu_03CCC exit=2 stdout_bytes=0"
    )
    triple = f"{benign} {nonzero} {permuted}"
    triple_records, triple_lost = observer._debug_line_receipts(triple)
    assert len(triple_records) == 2 and triple_lost == 1, (triple_records, triple_lost)
    assert observer._debug_unparsable(triple) == 1, triple
    hostile = _packet_with_debug_lines(
        tmp_path / "triple", [_DEBUG_HEAD, _DEBUG_SOURCES, triple, _DEBUG_TAIL]
    )
    assert hostile["observation"]["hooks"]["evidence_malformed"] is True, hostile
    assert hostile["observation"]["debug"]["unparsable_records"] == 1, hostile
    assert (
        _decision_of(hostile, "D09_HIDDEN_HOOK_NONZERO")["observation_status"] == "ERROR"
    ), hostile

    # --- NEGATIVE CONTROL, A DIFFERENT SHAPE FROM THE BUG: an ordinary log line
    # carrying neither lexeme claims nothing and loses nothing. A residue rule
    # that counted every line would drive every real log to ERROR.
    assert observer._debug_line_receipts(_DEBUG_HEAD) == ([], 0)
    assert observer._debug_line_receipts(_DEBUG_SOURCES) == ([], 0)
    assert observer._debug_unparsable(f"{_DEBUG_HEAD}\n{_DEBUG_SOURCES}\n") == 0


# ==========================================================================
# 24 — an ABSENT declared evidence plane degrades the decisions that declare
#      it. 20s: observer subprocesses plus one ~4.2 MB write.
# ==========================================================================

#: The three file-backed evidence planes and the run-root file each one reads.
#: Deleting the file is the only way to produce a plane that is ``UNMEASURED``
#: with NO truncation flag raised, which is precisely the state two boolean
#: bound flags cannot see.
_ABSENCE_CASES: dict[str, str] = {
    "stream": "stream.jsonl",
    "debug": "debug.log",
    "transcript": "transcript.jsonl",
}


def _declaring_decisions(plane: str) -> set[str]:
    """Decision ids whose ``DECISION_EVIDENCE_PLANES`` entry names ``plane``."""
    return {
        decision_id
        for decision_id, planes in observer.DECISION_EVIDENCE_PLANES.items()
        if plane in planes
    }


def _degraded_decisions(packet: dict[str, Any]) -> set[str]:
    """Decision ids in ``packet`` whose status is not ``OBSERVED``."""
    return {
        record["decision_id"]
        for record in packet["comparison"]["decisions"]
        if record["observation_status"] != "OBSERVED"
    }


@pytest.mark.timeout(20)
def test_an_absent_declared_plane_degrades_exactly_the_decisions_that_declare_it(tmp_path):
    """A declared plane that was never measured must not read as clean.

    THE CLASS THIS COVERS: a decision-level reader that consults only the
    truncation and malformed keys cannot see an ABSENT evidence file, which
    raises neither — so a plane correctly reporting ``present: false`` /
    ``UNMEASURED`` reaches a decision that still reports ``OBSERVED``. The
    schema's ``$defs.observation_status`` description and ``amendment:208``
    both say missing evidence is ``UNMEASURED``/``ERROR``, so that packet
    contradicts a frozen claim rather than merely under-reporting.

    WHAT IS ASSERTED, and why it is a class rather than the one instance:
    the degraded SET measured from the packet must equal the declaring SET
    read from ``DECISION_EVIDENCE_PLANES`` — for each plane, exactly the
    decisions that declare it and no others. Behaviour is compared against
    the declaration, so a plane later added to an entry is subscribed to this
    rule without anyone editing a list here.

    THE ARMS.

    * PERMITTING: a complete evidence set reaches ``OBSERVED`` on all twelve
      decisions. Without it, every refusal below would be indistinguishable
      from a decision that can never be clean.
    * REFUSING, three planes: each absence degrades its declaring decisions.
    * DISCRIMINATING, a different shape from the refusals: D09 does not name
      ``transcript``, so an absent transcript must leave D09 ``OBSERVED``
      with an empty ``evidence_bounds`` — a plane-wide alarm would fail here.
    * ROUTE SEPARATION: the absent transcript degrades D08 with
      ``any_bound_truncated`` FALSE, while a byte-clipped transcript degrades
      the same decision with it TRUE. Two distinct routes to one status, so
      the new one cannot be the old one under another name.
    * FAIL-CLOSED NORMALISATION: a plane declaring a status outside the
      three-member vocabulary resolves to ``ERROR``. ``_worst`` ranks only
      those three and returns ``OBSERVED`` for an unrecognised string, so
      without the normalisation this fold would be fail-OPEN on exactly the
      inputs it exists to catch.
    """
    # --- PERMITTING ARM.
    complete = _packet_from(OBSERVER_PATH, _make_run_root(tmp_path / "complete"))
    assert _degraded_decisions(complete) == set(), complete["comparison"]["decisions"]
    for plane in _ABSENCE_CASES:
        node = complete["observation"][plane]
        assert node["present"] is True and node["observation_status"] == "OBSERVED", node

    # --- REFUSING ARMS: one per file-backed plane.
    absent: dict[str, dict[str, Any]] = {}
    for plane, filename in _ABSENCE_CASES.items():
        run_root = _make_run_root(tmp_path / f"absent-{plane}")
        (run_root / filename).unlink()
        packet = _packet_from(OBSERVER_PATH, run_root)
        absent[plane] = packet

        # INSTRUMENT CONTROL: the deletion landed, and it raised NO bound flag.
        # If a truncation flag were up, the pre-existing bound reader would
        # already have degraded the decision and this arm would prove nothing.
        node = packet["observation"][plane]
        assert node["present"] is False, node
        assert node["observation_status"] == "UNMEASURED", node
        assert node["byte_truncated"] is False, node
        assert node["record_truncated"] is False, node
        assert node["unparsable_records"] == 0, node

        declaring = _declaring_decisions(plane)
        assert declaring, f"{plane} is named by no decision; this arm is vacuous"
        assert declaring != set(observer.DECISION_IDS), (
            f"{plane} is named by every decision, so 'only the decisions that "
            "declare it' would be unfalsifiable for this plane"
        )
        assert _degraded_decisions(packet) == declaring, (
            f"absent {plane}: degraded set does not match the declaring set; "
            f"degraded={sorted(_degraded_decisions(packet))} "
            f"declared={sorted(declaring)}"
        )
        for decision_id in sorted(declaring):
            record = _decision_of(packet, decision_id)
            assert record["observation_status"] == "UNMEASURED", record
            assert any(
                plane in note for note in record["evidence_bounds"]["notes"]
            ), f"{decision_id} degraded without naming {plane}: {record['evidence_bounds']}"

    # --- DISCRIMINATING CONTROL. D09 does not read the transcript.
    assert "transcript" not in observer.DECISION_EVIDENCE_PLANES["D09_HIDDEN_HOOK_NONZERO"]
    d09 = _decision_of(absent["transcript"], "D09_HIDDEN_HOOK_NONZERO")
    assert d09["observation_status"] == "OBSERVED", d09
    assert d09["discrepancies"] == [], d09
    assert d09["evidence_bounds"] == {
        "any_bound_truncated": False,
        "malformed": False,
        "notes": [],
    }, "an absent transcript must not reach a decision that does not declare it"

    # --- ROUTE SEPARATION: absent and clipped are two routes to one status.
    absent_d08 = _decision_of(absent["transcript"], "D08_HOOK_TOOL_USE_ID_JOIN")
    assert absent_d08["observation_status"] == "UNMEASURED", absent_d08
    assert absent_d08["evidence_bounds"]["any_bound_truncated"] is False, (
        "the absence must degrade D08 through the plane's own status, not "
        f"through a bound flag: {absent_d08['evidence_bounds']}"
    )
    assert absent_d08["evidence_bounds"]["malformed"] is False, absent_d08
    clipped_root = _make_run_root(tmp_path / "clipped-transcript")
    _aligned_multibyte_transcript(clipped_root)
    clipped_d08 = _decision_of(
        _packet_from(OBSERVER_PATH, clipped_root), "D08_HOOK_TOOL_USE_ID_JOIN"
    )
    assert clipped_d08["observation_status"] == "UNMEASURED", clipped_d08
    assert clipped_d08["evidence_bounds"]["any_bound_truncated"] is True, (
        "the clipped route must still raise the bound flag; if it did not, "
        "the two routes would be one and the assertion above would be empty"
    )

    # --- FAIL-CLOSED NORMALISATION, exercised at the composing function.
    d08_planes = observer.DECISION_EVIDENCE_PLANES["D08_HOOK_TOOL_USE_ID_JOIN"]
    for declared, expected in (
        ("OBSERVED", "OBSERVED"),
        ("UNMEASURED", "UNMEASURED"),
        ("ERROR", "ERROR"),
        ("FINE", "ERROR"),
        ("observed", "ERROR"),
        (None, "UNMEASURED"),
    ):
        plane_node = {} if declared is None else {"observation_status": declared}
        observation = {name: dict(plane_node) for name in d08_planes}
        bounds = observer._evidence_bounds(observation, "D08_HOOK_TOOL_USE_ID_JOIN")
        assert bounds.plane_status == expected, (declared, bounds)
        assert bounds.any_bound_truncated is False, (declared, bounds)
        assert bounds.malformed is False, (declared, bounds)
        record = observer._decision(
            "D08_HOOK_TOOL_USE_ID_JOIN", [], 7, "OBSERVED", bounds
        )
        assert record["observation_status"] == expected, (declared, record)

    # --- SEED CONTROL: a decision that declares NO plane must stay neutral.
    # `_worst([])` is UNMEASURED, so an unseeded accumulator would degrade D05
    # for having nothing to inherit — a refusal with no subject.
    assert observer.DECISION_EVIDENCE_PLANES["D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION"] == ()
    empty = observer._evidence_bounds({}, "D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION")
    assert empty.plane_status == "OBSERVED", empty
    assert empty.notes == [], empty
    assert (
        observer._decision(
            "D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION", [], 5, "OBSERVED", empty
        )["observation_status"]
        == "OBSERVED"
    )
    assert _decision_of(complete, "D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION")[
        "observation_status"
    ] == "OBSERVED"


# ==========================================================================
# 25 — every NESTED observation_status folds into the plane whose decisions
#      read it. 20s: observer subprocesses over throwaway worlds, each
#      ~0.15s, plus two in-process producer calls.
# ==========================================================================

_STATUS_KEY = "observation_status"


def _status_sites(packet: Any) -> list[tuple[str, str, str]]:
    """``(shape, pointer, status)`` for every object in ``packet`` with a status.

    ``shape`` normalises list indices to ``[]`` so every member of a list
    collapses to ONE registry key; ``pointer`` keeps the concrete index so a
    failure names the offending member. Ordinary walk, no knowledge of which
    keys exist — that is what lets it find a site nobody declared.
    """
    sites: list[tuple[str, str, str]] = []

    def walk(node: Any, shape: str, pointer: str) -> None:
        if isinstance(node, dict):
            if _STATUS_KEY in node:
                sites.append((shape, pointer, str(node[_STATUS_KEY])))
            for key in sorted(node):
                walk(node[key], f"{shape}/{key}", f"{pointer}/{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{shape}[]", f"{pointer}/{index}")

    walk(packet, "", "")
    return sites


def _is_plane_shape(shape: str) -> bool:
    """Whether ``shape`` is a TOP-LEVEL status bearer rather than a nested one.

    The two top-level families are ``/comparison`` (the decision rollup) and
    ``/observation/<name>`` (one evidence plane). Anything deeper is nested
    inside one of them and is what this guard governs.
    """
    parts = [part for part in shape.split("/") if part]
    if shape == "/comparison":
        return True
    return len(parts) == 2 and parts[0] == "observation" and not shape.endswith("[]")


def _enclosing_shape(shape: str, shapes: set[str]) -> str | None:
    """The longest proper prefix of ``shape`` that is itself a status bearer."""
    candidates = [other for other in shapes if other != shape and shape.startswith(other + "/")]
    return max(candidates, key=len) if candidates else None


#: EVERY nested status bearer the emitted packet carries, with the function
#: that folds it into its plane and the route by which the plane then reaches
#: a decision. This is a RATCHET, not a description: the guard below discovers
#: the sites by walking the packet and refuses any it finds that is absent
#: here, so a nested status bearer added next quarter cannot ship without an
#: entry AND a driven proof of its fold in ``_exercised`` below.
#:
#: ``deciding`` is not asserted from this table — it is RECOMPUTED from
#: ``observer.DECISION_EVIDENCE_PLANES`` in the test, so a plane later added to
#: a decision's entry turns a stale ``False`` here red instead of silently
#: excusing the site from the decision-set assertion.
_NESTED_STATUS_ROUTES: dict[str, dict[str, Any]] = {
    "/observation/environment/variables[]": {
        "plane": "environment",
        "fold": "_environment_plane: _worst over every variable's status",
        "deciding": False,
    },
    "/observation/executables/entries[]": {
        "plane": "executables",
        "fold": "_executables_plane: _worst over every entry's status",
        "deciding": False,
    },
    "/observation/git/pre": {
        "plane": "git",
        "fold": "capture: _worst over the git pair",
        "deciding": False,
    },
    "/observation/git/post": {
        "plane": "git",
        "fold": "capture: _worst over the git pair",
        "deciding": False,
    },
    "/observation/hooks/joins[]": {
        "plane": "hooks",
        "fold": "_hook_lifecycle: _worst over every join's status",
        "deciding": True,
    },
    "/observation/filesystem/pre": {
        "plane": "filesystem",
        "fold": "_filesystem_planes: _worst over the pre/post inventory pair",
        "deciding": True,
    },
    "/observation/filesystem/post": {
        "plane": "filesystem",
        "fold": "_filesystem_planes: _worst over the pre/post inventory pair",
        "deciding": True,
    },
    "/comparison/decisions[]": {
        "plane": None,
        "fold": "reconcile: _worst over every decision record's status",
        "deciding": True,
    },
}


def _fold_conformance_errors(packet: Any) -> list[str]:
    """THE GUARD. Nested statuses that are undeclared, or that reach nothing.

    Two refusals, and neither enumerates the three sites this defect was found
    at:

    * an UNDECLARED nested site — one the walk found that
      :data:`_NESTED_STATUS_ROUTES` does not name. This is what catches a
      FOURTH instance: a new nested status bearer is by construction absent
      from the registry.
    * a NON-DOMINATED nested site — one whose status is worse than the status
      of the object enclosing it. ``_worst`` ranks ERROR over UNMEASURED over
      OBSERVED, so a nested ``UNMEASURED`` under an ``OBSERVED`` plane is a
      status that was published and then discarded before any decision could
      read it. That is exactly the shipped defect, measured rather than
      described.
    """
    sites = _status_sites(packet)
    shapes = {shape for shape, _pointer, _status in sites}
    problems: list[str] = []
    for shape, pointer, status in sites:
        if _is_plane_shape(shape):
            continue
        if shape not in _NESTED_STATUS_ROUTES:
            problems.append(
                f"{pointer}: a nested {_STATUS_KEY} at undeclared shape {shape!r}; "
                "every nested status must declare the function that folds it "
                "into its plane and be exercised by a driven proof"
            )
            continue
        parent = _enclosing_shape(shape, shapes)
        if parent is None:
            problems.append(f"{pointer}: nested status with no enclosing status bearer")
            continue
        parent_pointer = pointer.rsplit("/", 1)[0]
        if shape.endswith("[]"):
            parent_pointer = pointer.rsplit("/", 2)[0]
        parent_status = _status_at(packet, parent_pointer)
        if observer._worst([parent_status, status]) != parent_status:
            problems.append(
                f"{pointer}: declares {status} while {parent_pointer} declares "
                f"{parent_status}; the nested status reaches no decision"
            )
    return problems


def _status_at(packet: Any, pointer: str) -> str:
    """The ``observation_status`` at a JSON pointer, read without a library."""
    node: Any = packet
    for part in [p for p in pointer.split("/") if p]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    return str(node[_STATUS_KEY])


def _degraded_sites(packet: Any) -> dict[str, str]:
    """``pointer -> status`` for every site in ``packet`` that is not OBSERVED."""
    return {
        pointer: status
        for _shape, pointer, status in _status_sites(packet)
        if status != "OBSERVED"
    }


@pytest.mark.timeout(20)
def test_every_nested_observation_status_folds_into_the_plane_its_decisions_read(tmp_path):
    """A status published one level down must reach the decisions above it.

    THE CLASS THIS COVERS: a plane that derives its own ``observation_status``
    from its bound flags alone, while an object nested inside it declares a
    worse one. ``inventory()`` does exactly that on an ``os.lstat`` ``OSError``
    or a failed digest — raising NEITHER ``entry_truncated`` NOR
    ``member_bytes_truncated`` — and ``hooks.joins[]`` does it for a join whose
    ``tool_use_id`` has no ``tool_use`` record in the stream. Both ``pre`` and
    ``post`` ``$ref`` the schema's ``observation_status`` def, whose description
    carries ``amendment:208``, so an unfolded status makes the packet
    contradict a frozen claim.

    WHY THIS IS A GUARD AND NOT A SPOT FIX. It does not enumerate the known
    sites. It WALKS the emitted packet, discovers every object carrying an
    ``observation_status``, and refuses (a) any nested site absent from
    :data:`_NESTED_STATUS_ROUTES` and (b) any nested site whose status is worse
    than its enclosing object's. A further instance is by construction
    undeclared, so it turns (a) red without anyone predicting its shape.

    THE ARMS.

    * PERMITTING: the shipped packet conforms, and every decision is
      ``OBSERVED``. Without it every refusal below would be indistinguishable
      from a guard that cannot pass.
    * REFUSING, FRESH SITE, a shape no fix here anticipated: a brand-new
      nested status-bearing object under a plane that has never had one. The
      guard must name it. This is the negative control that proves the guard
      is not scoped to the instances that prompted it.
    * REFUSING, NON-DOMINATED SITE: an existing registered site set worse than
      its plane.
    * DRIVEN FOLD, one per registered site, BOTH DIRECTIONS: every site is
      driven to a degraded status and to a clean one, and the enclosing plane
      must move with it. A dominance check alone would pass over a plane that
      is hard-wired to the worst status.
    * SCOPE: for a deciding plane the degraded SET must equal the set of
      decisions that declare it, recomputed from
      ``DECISION_EVIDENCE_PLANES``. For a non-deciding plane the guard asserts
      mechanically that NO decision declares it, so "reaches no decision" is a
      checked property rather than an omission.
    """
    # --- PERMITTING ARM, and the control of the control.
    shipped = _packet_from(OBSERVER_PATH, _make_run_root(tmp_path / "shipped"))
    assert _fold_conformance_errors(shipped) == [], _fold_conformance_errors(shipped)
    assert _degraded_decisions(shipped) == set(), shipped["comparison"]["decisions"]

    # INSTRUMENT CONTROL: the dominance arm is not vacuous on the shipped
    # packet. Several nested sites really are UNMEASURED there (no CLAUDE_*
    # variables, no `claude` binary observation, a run root that is not a git
    # repository), so the check has non-OBSERVED input to be wrong about.
    degraded_shipped = _degraded_sites(shipped)
    assert len(degraded_shipped) >= 6, degraded_shipped

    # --- DISCOVERY: the registry is the packet's own nested sites, not a list.
    discovered = {
        shape for shape, _p, _s in _status_sites(shipped) if not _is_plane_shape(shape)
    }
    assert discovered == set(_NESTED_STATUS_ROUTES), (
        f"undeclared nested sites: {sorted(discovered - set(_NESTED_STATUS_ROUTES))} | "
        f"declared but absent: {sorted(set(_NESTED_STATUS_ROUTES) - discovered)}"
    )
    planes = {shape.split("/")[2] for shape in discovered if shape.startswith("/observation/")}
    assert planes == {"environment", "executables", "git", "hooks", "filesystem"}, planes

    # --- REFUSING ARM A, FRESH SITE. `settings` has never carried a nested
    # status bearer, and no line of the fix above mentions it. The guard has
    # to find it by walking, which is the only way a FOURTH instance gets
    # caught.
    fresh = copy.deepcopy(shipped)
    fresh["observation"]["settings"]["overlay_probe_added_next_quarter"] = {
        "path": "somewhere",
        _STATUS_KEY: "ERROR",
    }
    fresh_errors = _fold_conformance_errors(fresh)
    assert any(
        "/observation/settings/overlay_probe_added_next_quarter" in problem
        and "undeclared shape" in problem
        for problem in fresh_errors
    ), f"the guard did not refuse a fresh nested status bearer: {fresh_errors}"

    # And a fresh site DEEPER than one level, so the refusal is not scoped to
    # direct children of a plane.
    deep = copy.deepcopy(shipped)
    deep["observation"]["hooks"]["joins"][0]["probe_added_next_quarter"] = {
        _STATUS_KEY: "UNMEASURED"
    }
    assert any(
        "probe_added_next_quarter" in problem for problem in _fold_conformance_errors(deep)
    ), "a nested status two levels below a plane escaped the walk"

    # --- REFUSING ARM B, NON-DOMINATED SITE at a REGISTERED shape: the
    # shipped defect's own shape. This is what the fold above removed.
    regressed = copy.deepcopy(shipped)
    regressed["observation"]["filesystem"]["pre"][_STATUS_KEY] = "ERROR"
    regressed_errors = _fold_conformance_errors(regressed)
    assert any(
        "/observation/filesystem/pre" in problem and "reaches no decision" in problem
        for problem in regressed_errors
    ), regressed_errors
    # ... and at a LIST member, whose pointer arithmetic differs.
    regressed_join = copy.deepcopy(shipped)
    regressed_join["observation"]["hooks"]["joins"][1][_STATUS_KEY] = "UNMEASURED"
    assert any(
        "/observation/hooks/joins/1" in problem
        for problem in _fold_conformance_errors(regressed_join)
    ), _fold_conformance_errors(regressed_join)

    exercised: set[str] = set()

    def fold_moved(shape: str, clean: dict[str, Any], clean_pointer: str,
                   dirty: dict[str, Any], dirty_pointer: str) -> None:
        """Assert a driven degradation moved its enclosing plane, both ways.

        The two arms carry their own pointers because a driven degradation can
        ADD the member it degrades — the unstreamed hook receipt is a third
        join that the clean packet does not have — so one pointer could not
        address both worlds.
        """
        exercised.add(shape)
        route = _NESTED_STATUS_ROUTES[shape]
        plane = route["plane"]
        parent_pointer = "/comparison" if plane is None else f"/observation/{plane}"
        assert _status_at(clean, clean_pointer) == "OBSERVED", (shape, "clean arm")
        assert _status_at(dirty, dirty_pointer) != "OBSERVED", (shape, "dirty arm")
        assert _status_at(clean, parent_pointer) == "OBSERVED", (shape, "clean plane")
        assert _status_at(dirty, parent_pointer) != "OBSERVED", (
            f"{shape}: {dirty_pointer} declared "
            f"{_status_at(dirty, dirty_pointer)} while {parent_pointer} declared "
            f"{_status_at(dirty, parent_pointer)}; the fold named "
            f"{route['fold']!r} did not happen"
        )
        assert _fold_conformance_errors(dirty) == [], _fold_conformance_errors(dirty)
        if plane is None:
            return
        declaring = _declaring_decisions(plane)
        assert bool(declaring) == bool(route["deciding"]), (
            f"{shape}: the registry says deciding={route['deciding']} but "
            f"DECISION_EVIDENCE_PLANES names {sorted(declaring)}"
        )
        if declaring:
            assert _degraded_decisions(dirty) == declaring, (
                f"{shape}: degraded={sorted(_degraded_decisions(dirty))} "
                f"declaring={sorted(declaring)}"
            )
        else:
            assert _degraded_decisions(dirty) == set(), (
                f"{shape}: {plane} is declared by no decision, so degrading it "
                f"must degrade none: {sorted(_degraded_decisions(dirty))}"
            )

    # --- DRIVEN SITE 1 and 2: the two inventory snapshots. Driven through the
    # evidence file, with NO truncation flag raised, so the pre-existing bound
    # reader cannot be what degrades the plane.
    for shape, side, injected in (
        ("/observation/filesystem/pre", "pre", "UNMEASURED"),
        ("/observation/filesystem/post", "post", "ERROR"),
    ):
        run_root = _make_run_root(tmp_path / f"fs-{side}")
        document = json.loads((run_root / "fs-inventory.json").read_text(encoding="utf-8"))
        document[side][_STATUS_KEY] = injected
        (run_root / "fs-inventory.json").write_text(json.dumps(document), encoding="utf-8")
        dirty = _packet_from(OBSERVER_PATH, run_root)
        assert dirty["observation"]["filesystem"]["any_bound_truncated"] is False, (
            "the driven degradation must not raise a bound flag, or the "
            "pre-existing bound reader is what degraded the plane"
        )
        assert _status_at(dirty, f"/observation/filesystem/{side}") == injected
        assert _status_at(dirty, "/observation/filesystem") == injected
        fold_moved(
            shape, shipped, f"/observation/filesystem/{side}",
            dirty, f"/observation/filesystem/{side}",
        )

    # --- DRIVEN SITE 3: a hook receipt whose tool_use_id has no `tool_use`
    # record in the stream. The join records it as UNMEASURED; before the fold
    # the hooks plane still reported OBSERVED.
    hooks_root = _make_run_root(tmp_path / "hooks-join")
    debug_lines = (hooks_root / "debug.log").read_text(encoding="utf-8").splitlines()
    orphan_receipt = (
        "[2026-09-07T09:15:02.999Z] [DEBUG] hook PreToolUse "
        "tool_use_id=toolu_UNSTREAMED command=claude-observer-canary "
        "exit=0 stdout_bytes=0"
    )
    (hooks_root / "debug.log").write_text(
        "\n".join(debug_lines[:-1] + [orphan_receipt, debug_lines[-1]]) + "\n",
        encoding="utf-8",
    )
    hooks_dirty = _packet_from(OBSERVER_PATH, hooks_root)
    unstreamed = [
        index
        for index, join in enumerate(hooks_dirty["observation"]["hooks"]["joins"])
        if join["tool_use_id"] == "toolu_UNSTREAMED"
    ]
    assert unstreamed == [2], hooks_dirty["observation"]["hooks"]["joins"]
    assert hooks_dirty["observation"]["hooks"]["any_bound_truncated"] is False
    assert hooks_dirty["observation"]["hooks"]["evidence_malformed"] is False
    fold_moved(
        "/observation/hooks/joins[]", shipped, "/observation/hooks/joins/0",
        hooks_dirty, f"/observation/hooks/joins/{unstreamed[0]}",
    )

    # --- DRIVEN SITE 4 and 5: the git pair. Its PERMITTING arm needs a real
    # repository, because every other world in this file is a throwaway run
    # root where `git rev-parse HEAD` fails — which is why the shipped packet
    # is the REFUSING observation here and the direction is inverted.
    git_root = _make_run_root(tmp_path / "git-clean")
    git_clean = _packet_from(OBSERVER_PATH, git_root, observed_cwd=REPO_ROOT)
    assert git_clean["observation"]["git"]["pre"]["head"], (
        "the permitting arm found no HEAD, so the git plane is UNMEASURED in "
        "BOTH arms and this site's fold would be unfalsifiable"
    )
    assert shipped["observation"]["git"]["pre"]["head"] is None, (
        "the refusing arm found a repository at the throwaway run root"
    )
    for shape, pointer in (
        ("/observation/git/pre", "/observation/git/pre"),
        ("/observation/git/post", "/observation/git/post"),
    ):
        fold_moved(shape, git_clean, pointer, shipped, pointer)

    # --- DRIVEN SITE 6: the environment variables. Same inverted direction:
    # the permitting arm supplies every allowlisted name to the child process,
    # which is also what proves CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA are
    # read from the PROCESS ENVIRONMENT rather than invented.
    env_root = _make_run_root(tmp_path / "env-clean")
    supplied = {name: f"p0a-{name.lower()}" for name in observer.ENVIRONMENT_ALLOWLIST}
    supplied["PATH"] = os.environ.get("PATH", "")
    supplied["HOME"] = os.environ.get("HOME", str(tmp_path))
    env_clean = _packet_from(OBSERVER_PATH, env_root, extra_env=supplied)
    names = [item["name"] for item in env_clean["observation"]["environment"]["variables"]]
    assert "CLAUDE_PLUGIN_ROOT" in names and "CLAUDE_PLUGIN_DATA" in names, names
    for item in env_clean["observation"]["environment"]["variables"]:
        assert item["present"] is True, item
        if item["name"] == "CLAUDE_PLUGIN_ROOT":
            assert item["sha256"] == hashlib.sha256(
                supplied["CLAUDE_PLUGIN_ROOT"].encode("utf-8")
            ).hexdigest(), "the digest is not of the value this process supplied"
    absent_index = names.index("CLAUDE_PLUGIN_ROOT")
    assert _status_at(shipped, f"/observation/environment/variables/{absent_index}") == (
        "UNMEASURED"
    )
    fold_moved(
        "/observation/environment/variables[]",
        env_clean, f"/observation/environment/variables/{absent_index}",
        shipped, f"/observation/environment/variables/{absent_index}",
    )

    # --- DRIVEN SITE 7: the executables entries. This one CANNOT be driven
    # through a packet in either direction: the `claude` entry is UNMEASURED
    # by construction (amendment:245 — an unavailable binary never becomes a
    # pass), which pins the plane at UNMEASURED whatever the other entries
    # say. Stated because it bounds what the packet-level arms above can show.
    # The fold is therefore driven at the producer, over a one-name allowlist.
    assert "claude" in observer.EXECUTABLE_NAMES
    for entry in shipped["observation"]["executables"]["entries"]:
        if entry["name"] == "claude":
            assert entry[_STATUS_KEY] == "UNMEASURED", entry
    exercised.add("/observation/executables/entries[]")
    real = observer.EXECUTABLE_NAMES
    try:
        observer.EXECUTABLE_NAMES = ("python3",)
        clean_plane = observer._executables_plane()
        assert clean_plane["entries"][0][_STATUS_KEY] == "OBSERVED", clean_plane
        assert clean_plane[_STATUS_KEY] == "OBSERVED", clean_plane
        observer.EXECUTABLE_NAMES = ("p0a-no-such-binary",)
        dirty_plane = observer._executables_plane()
        assert dirty_plane["entries"][0][_STATUS_KEY] == "UNMEASURED", dirty_plane
        assert dirty_plane[_STATUS_KEY] == "UNMEASURED", (
            "the entry status did not fold into the executables plane"
        )
    finally:
        observer.EXECUTABLE_NAMES = real
    assert observer.EXECUTABLE_NAMES == real
    assert _declaring_decisions("executables") == set(), (
        "executables is now read by a decision; this site needs a packet-level "
        "decision-set arm rather than a producer-level one"
    )

    # --- DRIVEN SITE 8: the decision records under `comparison`. An absent
    # transcript degrades D08 only, and the rollup must move with it.
    rollup_root = _make_run_root(tmp_path / "rollup")
    (rollup_root / "transcript.jsonl").unlink()
    rollup_dirty = _packet_from(OBSERVER_PATH, rollup_root)
    d08_index = [
        index
        for index, record in enumerate(rollup_dirty["comparison"]["decisions"])
        if record["decision_id"] == "D08_HOOK_TOOL_USE_ID_JOIN"
    ][0]
    assert _degraded_decisions(rollup_dirty) == _declaring_decisions("transcript")
    fold_moved(
        "/comparison/decisions[]", shipped, f"/comparison/decisions/{d08_index}",
        rollup_dirty, f"/comparison/decisions/{d08_index}",
    )

    # --- BIJECTION: every registered site got a driven proof. This is what
    # makes the registry ratchet bite — a new site added to
    # `_NESTED_STATUS_ROUTES` to silence the discovery arm above still fails
    # here until someone drives it.
    assert exercised == set(_NESTED_STATUS_ROUTES), (
        f"registered but never driven: {sorted(set(_NESTED_STATUS_ROUTES) - exercised)} | "
        f"driven but unregistered: {sorted(exercised - set(_NESTED_STATUS_ROUTES))}"
    )


# ==========================================================================
# 26 — every number this manifest attributes to a COMMAND, re-measured by
#      running that command. 20s: a handful of `grep -c` children and no
#      observer subprocess; measured well under a second locally.
# ==========================================================================

#: Marks a span this checker EXECUTES. Anything else in the map below carries
#: the reason it is not run, so "unrunnable" is never a silent skip.
_RUNNABLE_SPAN = "RUN"

#: Every backtick span in any case's ``scope_limits`` that carries a flag
#: token, mapped either to ``_RUNNABLE_SPAN`` or to why it cannot be executed.
#: This is a RATCHET over the spans present on these bytes — NOT a claim that
#: no other command shape exists, and not a claim that the spans it cannot run
#: are checked anywhere. Its job is narrower and mechanical: a NEWLY quoted
#: command fails here until someone either binds it to a measured count or
#: writes down why it cannot be run.
_SCOPE_LIMIT_COMMAND_SPANS: dict[str, str] = {
    "grep -c 'inventory(' tests/bootstrap/observe_claude_execution.py": _RUNNABLE_SPAN,
    "grep -c": "names a tool with no pattern and no path, so it has no output to compare",
    "-o addopts=": "a pytest flag fragment quoted from the smoke command, not a command",
    "python -c": "names an interpreter with no program text",
}

#: A backtick span, single or double delimited.
_BACKTICK_SPAN_RE = re.compile(r"``([^`]+)``|`([^`]+)`")

#: A quoted command followed by the word "reports" and the count it is
#: claimed to print. Whitespace between the two is any run, so a line break
#: cannot hide a claim.
_COMMAND_CLAIM_RE = re.compile(r"`([^`]+)`\s+reports\s+([A-Za-z0-9]+)")

#: The ONE command shape this checker will execute: ``grep -c`` with a
#: single-quoted pattern and a relative path. Run as an argv list with no
#: shell, so nothing in the manifest text can be interpreted as a shell
#: metacharacter.
_COUNTED_GREP_RE = re.compile(r"^grep -c '([^']*)' ([A-Za-z0-9_][A-Za-z0-9_./-]*)$")

_COUNT_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12,
}


def _count_from_token(token: str) -> int | None:
    """The integer a claim states, written as digits or as an English word."""
    if token.isdigit():
        return int(token)
    return _COUNT_WORDS.get(token.lower())


def _scope_limit_entries(manifest: dict[str, Any]) -> list[tuple[str, int, str]]:
    """``(case_id, index, text)`` for every scope_limits entry in the manifest."""
    return [
        (case["case_id"], index, text)
        for case in manifest["cases"]
        for index, text in enumerate(case.get("scope_limits", []) or [])
    ]


def _flag_bearing_spans(manifest: dict[str, Any]) -> dict[str, str]:
    """Backtick spans carrying a flag token, mapped to where they were found.

    A flag token is the mechanical signal that a span is a shell invocation
    rather than a field name: ``sha256`` and ``declared_writable_roots`` carry
    none, ``grep -c`` and ``set -euo pipefail`` do.
    """
    found: dict[str, str] = {}
    for case_id, index, text in _scope_limit_entries(manifest):
        for match in _BACKTICK_SPAN_RE.finditer(text):
            span = match.group(1) or match.group(2)
            if any(token.startswith("-") for token in span.split()):
                found.setdefault(span, f"{case_id}:scope_limits[{index}]")
    return found


def _command_output_claims(manifest: dict[str, Any]) -> list[tuple[str, str, str]]:
    """``(where, command, stated_count)`` for every ``reports`` claim.

    Extracted from the MANIFEST TEXT. The commands are never listed here: a
    list written in the test would be the same stale-by-construction defect
    one level up.
    """
    claims: list[tuple[str, str, str]] = []
    for case_id, index, text in _scope_limit_entries(manifest):
        for match in _COMMAND_CLAIM_RE.finditer(text):
            claims.append(
                (f"{case_id}:scope_limits[{index}]", match.group(1), match.group(2))
            )
    return claims


def _run_counted_command(command: str, root: Path) -> int:
    """Run one whitelisted ``grep -c`` under ``root`` and return its count."""
    match = _COUNTED_GREP_RE.match(command)
    assert match is not None, f"refusing to run an unwhitelisted command: {command!r}"
    proc = subprocess.run(
        ["grep", "-c", match.group(1), match.group(2)],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=SUBPROCESS_TIMEOUT_S,
    )
    # grep exits 1 for "no line matched", which is a count of zero, not a
    # failure. Anything above that is a real error and must not read as 0.
    assert proc.returncode in (0, 1), (
        f"grep exited {proc.returncode} for {command!r}: {proc.stderr.strip()}"
    )
    return int(proc.stdout.strip() or 0)


def _scope_limit_command_errors(manifest: dict[str, Any], root: Path) -> list[str]:
    """Every disagreement between a quoted command claim and its real output."""
    problems: list[str] = []
    claims = _command_output_claims(manifest)
    spans = _flag_bearing_spans(manifest)

    # VACUITY GUARD. An extraction that finds nothing must FAIL rather than
    # report a clean sweep: a checker that passes on zero inputs is exactly
    # the failure mode this test exists to remove.
    if not claims:
        problems.append(
            "extracted no command claim from scope_limits; this checker would pass vacuously"
        )
    elif not any(_COUNTED_GREP_RE.match(command) for _, command, _ in claims):
        problems.append(
            "no extracted command claim is runnable; nothing would be re-measured"
        )

    for where, command, stated in claims:
        match = _COUNTED_GREP_RE.match(command)
        if match is None:
            reason = _SCOPE_LIMIT_COMMAND_SPANS.get(command)
            if reason is None or reason == _RUNNABLE_SPAN:
                problems.append(
                    f"{where}: {command!r} states a count but is neither runnable "
                    "here nor declared unrunnable"
                )
            continue
        wanted = _count_from_token(stated)
        if wanted is None:
            problems.append(
                f"{where}: {command!r} states {stated!r}, which is not a count "
                "this checker can read"
            )
            continue
        if not (root / match.group(2)).is_file():
            problems.append(f"{where}: {command!r} names a file that does not exist")
            continue
        actual = _run_counted_command(command, root)
        if actual != wanted:
            problems.append(f"{where}: {command!r} states {wanted} but returns {actual}")

    claimed = {command for _, command, _ in claims}
    for span in sorted(span for span in spans if _COUNTED_GREP_RE.match(span)):
        if span not in claimed:
            problems.append(
                f"{spans[span]}: {span!r} is runnable but is quoted without a stated count"
            )

    for span in sorted(set(spans) - set(_SCOPE_LIMIT_COMMAND_SPANS)):
        problems.append(f"{spans[span]}: {span!r} is an undeclared command span")
    for span in sorted(set(_SCOPE_LIMIT_COMMAND_SPANS) - set(spans)):
        problems.append(f"declared command span {span!r} no longer appears in scope_limits")
    return problems


@pytest.mark.timeout(20)
def test_scope_limits_quoted_commands_are_bound_to_their_measured_output(tmp_path):
    """A count this manifest attributes to a command, re-measured by running it.

    THE CLASS THIS COVERS: a count a manifest entry attributes to a command
    that no mechanism ever re-runs. Such a number is correct when written and
    drifts silently thereafter, because prose that names a function changes the
    command's output without changing anything the tests read.

    WHAT IS BOUND HERE. Claims are extracted FROM THE MANIFEST TEXT — a
    backtick-quoted command followed by the word "reports" and a count — never
    from a list written in this file, which would be the same
    stale-by-construction defect one level up. Each extracted command matching
    the single whitelisted shape (``grep -c`` with a quoted pattern and a
    path, run as an argv list with no shell) is EXECUTED and its output
    compared. A runnable command quoted WITHOUT a count fails too, so the
    binding cannot be dodged by dropping the number.

    WHAT IS NOT BOUND, named rather than implied by the word "every": spans
    this checker will not execute. On these bytes that is the git entry's
    ``grep -c`` — a tool name with no pattern and no path, so there is no
    output to compare — plus ``-o addopts=`` and ``python -c``. Naming them is NOT
    checking them: nothing here verifies the git entry's "reports three".
    What that entry offers the number as evidence FOR — one definition, one
    call — is measured by AST in
    ``test_git_plane_is_single_sampled_and_the_filesystem_pair_is_not``.
    ``_SCOPE_LIMIT_COMMAND_SPANS`` pins the set in BOTH directions, so a newly
    quoted command and a silently dropped one each turn this red.
    """
    manifest = _manifest()
    raw = MANIFEST_PATH.read_text(encoding="utf-8")

    # --- INSTRUMENT CONTROL 1: the EXTRACTOR found real work. A zero-command
    # extraction that then passes is the failure mode here, so both branches
    # of the classifier must be populated on the shipped bytes.
    claims = _command_output_claims(manifest)
    spans = _flag_bearing_spans(manifest)
    assert claims, "the extractor found no command claim at all"
    assert spans, "the extractor found no flag-bearing command span at all"
    runnable = [claim for claim in claims if _COUNTED_GREP_RE.match(claim[1])]
    assert runnable, "no extracted claim is runnable; every arm below is vacuous"
    assert [claim for claim in claims if not _COUNTED_GREP_RE.match(claim[1])], (
        "no extracted claim is unrunnable; the classifier's second branch is unexercised"
    )
    assert any("inventory(" in claim[1] for claim in runnable), claims

    # --- INSTRUMENT CONTROL 2: the RUNNER returns real numbers in BOTH
    # directions. A count recomputed in pure Python (no grep) must equal what
    # the subprocess reports, and a pattern that occurs nowhere must come back
    # 0 rather than raising or reading as a match.
    relative = "tests/bootstrap/observe_claude_execution.py"
    independent = sum(
        1
        for line in (REPO_ROOT / relative).read_text(encoding="utf-8").splitlines()
        if "inventory(" in line
    )
    assert independent > 0, "the positive control pattern occurs nowhere"
    assert _run_counted_command(f"grep -c 'inventory(' {relative}", REPO_ROOT) == independent
    assert _run_counted_command(f"grep -c 'p0a_absent_pattern' {relative}", REPO_ROOT) == 0

    # --- INSTRUMENT CONTROL 3: a manifest carrying NO claims is a failure,
    # not a green run.
    stripped = copy.deepcopy(manifest)
    for case in stripped["cases"]:
        case.pop("scope_limits", None)
    vacuous = _scope_limit_command_errors(stripped, REPO_ROOT)
    assert any("pass vacuously" in problem for problem in vacuous), vacuous

    # --- PERMITTING ARM: every quoted command on the shipped bytes returns
    # the number the manifest attributes to it.
    problems = _scope_limit_command_errors(manifest, REPO_ROOT)
    assert problems == [], "\n".join(problems)

    where, command, stated = runnable[0]
    truth = _run_counted_command(command, REPO_ROOT)
    assert _count_from_token(stated) == truth, (where, stated, truth)

    # --- PERMITTING ARM 2, the false-positive control: the SAME claim with a
    # line break between the command and its count stays green, or this would
    # be binding manifest layout rather than the number.
    rewrapped = raw.replace(
        f"`{command}` reports {stated}", f"`{command}`\\n  reports {stated}", 1
    )
    assert rewrapped != raw, "the rewrap control changed nothing"
    assert _scope_limit_command_errors(json.loads(rewrapped), REPO_ROOT) == [], (
        "the checker refused an identical claim wrapped across lines"
    )

    # --- REFUSING ARM 1, the reproducer's shape, through a real file on disk:
    # a stale count. This is the arm that was missing when "reports two"
    # shipped against a command returning four.
    wrong_word = next(word for word, value in _COUNT_WORDS.items() if value != truth)
    stale = raw.replace(
        f"`{command}` reports {stated}", f"`{command}` reports {wrong_word}", 1
    )
    assert stale != raw, "the perturbation control changed nothing"
    stale_path = tmp_path / "stale-manifest.json"
    stale_path.write_text(stale, encoding="utf-8")
    problems = _scope_limit_command_errors(
        json.loads(stale_path.read_text(encoding="utf-8")), REPO_ROOT
    )
    assert any(
        f"states {_COUNT_WORDS[wrong_word]} but returns {truth}" in problem
        for problem in problems
    ), problems

    # --- REFUSING ARM 2, a DIFFERENT shape: a newly quoted command appears
    # and is declared nowhere. It carries no count, so arm 1 could not see it.
    grown = copy.deepcopy(manifest)
    grown["cases"][0]["scope_limits"].append(
        f"A later revision quoted `wc -l {relative}` in this entry."
    )
    problems = _scope_limit_command_errors(grown, REPO_ROOT)
    assert any("undeclared command span" in problem for problem in problems), problems

    # --- REFUSING ARM 3, a DIFFERENT shape: a RUNNABLE command quoted with no
    # count, which would otherwise be an unmeasured claim wearing a measured
    # field's authority.
    silent = copy.deepcopy(manifest)
    silent["cases"][0]["scope_limits"].append(
        f"See `grep -c 'def ' {relative}` for the detail."
    )
    problems = _scope_limit_command_errors(silent, REPO_ROOT)
    assert any("quoted without a stated count" in problem for problem in problems), problems

    # --- REFUSING ARM 4, a DIFFERENT shape: a declared span DELETED. A pin
    # that only refuses growth rots into a list of spans nobody quotes.
    shrunk = copy.deepcopy(manifest)
    shrunk["cases"][0]["scope_limits"] = [
        text
        for text in shrunk["cases"][0]["scope_limits"]
        if "-o addopts=" not in text
    ]
    assert shrunk["cases"][0]["scope_limits"] != manifest["cases"][0]["scope_limits"]
    problems = _scope_limit_command_errors(shrunk, REPO_ROOT)
    assert any(
        "no longer appears in scope_limits" in problem for problem in problems
    ), problems

    # --- REFUSING ARM 5, a DIFFERENT shape: a count written as a word this
    # checker cannot read must be a failure, never a silent skip.
    fuzzy = raw.replace(f"`{command}` reports {stated}", f"`{command}` reports several", 1)
    assert fuzzy != raw
    problems = _scope_limit_command_errors(json.loads(fuzzy), REPO_ROOT)
    assert any(
        "not a count this checker can read" in problem for problem in problems
    ), problems

    # --- REFUSING ARM 6, a DIFFERENT shape: the command names a file that is
    # not there. Without this a renamed subject reads as an honest zero.
    moved = raw.replace(
        f"`{command}` reports {stated}",
        "`grep -c 'inventory(' tests/bootstrap/no_such_observer.py` reports one",
        1,
    )
    assert moved != raw
    problems = _scope_limit_command_errors(json.loads(moved), REPO_ROOT)
    assert any("names a file that does not exist" in problem for problem in problems), problems


# ==========================================================================
# 27 — the CLASS guard: a cited test name must resolve to something.
#      10s: one def-line sweep of tests/** plus in-memory citation scans.
# ==========================================================================
#
# A receipt that names a test is a receipt only while that test exists. Frozen
# prose cannot be corrected in place (``amendment:174-175``, ``ladder:398``),
# so a citation that resolves to nothing is a false receipt for as long as the
# rung stands. This is the pointer sub-shape of the wider defect: prose
# asserting something the bytes do not do.
#
# WHAT RESOLVES. A citation passes if a ``def`` line under ``tests/`` defines
# that name, OR if a non-LIVE case of the manifest declares it — a FUTURE case
# is a SPECIFICATION for a node later rungs create, so its name legitimately
# has no definition yet. The exemption is DERIVED from each case's ``state``
# field, so a case promoted out of FUTURE stops exempting its own name on the
# same edit that promotes it.
#
# WHAT IS SCANNED. Raw lines of both frozen files, not just their comment and
# docstring tokens. A receipt in a code string counts as a receipt, and the
# superset is the conservative direction.

_TEST_CITATION_RE = re.compile(r"``(test_[a-z0-9_]+)``")
_TEST_DEF_RE = re.compile(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(")
_TEST_NAME_RE = re.compile(r"\btest_[a-z0-9_]+\b")


def _defined_test_names(root: Path) -> set[str]:
    """Every ``test_*`` name a ``def`` line under ``root/tests`` binds."""
    names: set[str] = set()
    for path in sorted((root / "tests").rglob("test_*.py")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _TEST_DEF_RE.match(line)
            if match:
                names.add(match.group(1))
    return names


def _future_declared_test_names(manifest: dict[str, Any]) -> set[str]:
    """Test names a FUTURE case specifies, read from its ``state`` field.

    Selection is on the FUTURE value, not on "anything but FROZEN": a state
    vocabulary that grows must narrow this exemption and turn the guard red,
    never widen it silently into permission.
    """
    names: set[str] = set()
    for case in manifest.get("cases", []):
        if case.get("state") == "FUTURE":
            names |= set(_TEST_NAME_RE.findall(json.dumps(case)))
    return names


def _unresolved_citation_errors(texts: dict[str, str], resolvable: set[str]) -> list[str]:
    """``file:line`` for every rst-literal test citation that names nothing."""
    problems: list[str] = []
    for label in sorted(texts):
        for number, line in enumerate(texts[label].splitlines(), 1):
            for name in _TEST_CITATION_RE.findall(line):
                if name not in resolvable:
                    problems.append(
                        f"{label}:{number}: cites ``{name}``, which no def line "
                        f"under tests/ defines and no FUTURE case declares"
                    )
    return problems


def _frozen_citation_texts() -> dict[str, str]:
    """The raw text of the two frozen files whose prose may cite a test."""
    return {
        str(path.relative_to(REPO_ROOT)): path.read_text(encoding="utf-8")
        for path in (OBSERVER_PATH, NODE_FILE)
    }


@pytest.mark.timeout(10)
def test_every_cited_test_name_resolves_to_a_defined_or_future_declared_node():
    """Every test this rung's frozen bytes name by citation, resolved.

    THE CLASS THIS COVERS: a receipt inside digest-bound prose that points at
    a test which does not exist — because it was renamed, never written, or
    written under another name. Such a pointer is correct when typed and rots
    thereafter, and the rung protocol means it can only be corrected by a
    replacement changeset, so nothing routine will ever catch it.

    Both arms below are driven through synthetic text built at runtime rather
    than written as literals, because a literal citation in this file would be
    read by the very scan it is meant to exercise.
    """
    manifest = _manifest()
    defined = _defined_test_names(REPO_ROOT)
    future = _future_declared_test_names(manifest)
    texts = _frozen_citation_texts()

    # --- INSTRUMENT CONTROL 1: the def-line sweep answers in BOTH directions.
    # A sweep that returned everything, or nothing, would make every arm below
    # vacuous, and "no findings" is the failure mode this whole test guards.
    assert len(defined) > 1000, f"the def-line sweep found only {len(defined)} names"
    assert "test_manifest_digests_match_current_tracked_bytes" in defined
    assert ("test_" + "name_no_def_line_in_this_repository_binds") not in defined

    # --- INSTRUMENT CONTROL 2: the FUTURE exemption is populated, and it is
    # NOT a restatement of what already exists. If every exempted name were
    # also defined, the permitting arm would prove nothing about the exemption.
    assert future, "no FUTURE case declares any test name; the exemption is empty"
    undefined_future = sorted(future - defined)
    assert undefined_future, (
        "every FUTURE-declared name is already defined, so the exemption is "
        "indistinguishable from the def-line sweep"
    )

    # --- INSTRUMENT CONTROL 3: the state filter DISCRIMINATES. The live case's
    # own node name must not be exempted by it, or a FROZEN case could carry a
    # citation to a node that was deleted.
    live = _case(manifest, "P0-C01")
    live_node = live["node"].rsplit("::", 1)[-1]
    assert live["state"] == "FROZEN", live["state"]
    assert live_node not in future, live_node
    assert live_node in defined, live_node

    # --- INSTRUMENT CONTROL 4: the extractor found real citations on the
    # shipped bytes, including the corrected receipt this guard was built for.
    cited = {
        name
        for text in texts.values()
        for name in _TEST_CITATION_RE.findall(text)
    }
    assert len(cited) >= 3, sorted(cited)
    assert (
        "test_joined_setting_sources_are_validated_as_the_units_the_child_receives"
        in cited
    )

    # --- PERMITTING ARM: the shipped frozen bytes cite nothing unresolved.
    problems = _unresolved_citation_errors(texts, defined | future)
    assert problems == [], "\n".join(problems)

    # --- REFUSING ARM 1, the reproducer's shape under a different name: a
    # citation naming a test nothing defines and no case declares.
    absent = "test_" + "receipt_pointing_at_a_node_that_was_never_written"
    assert absent not in defined and absent not in future
    synthetic = (
        "#: The value table is checked in both directions.\n"
        f"#: ``{absent}`` asserts it.\n"
    )
    refused = _unresolved_citation_errors({"synthetic.py": synthetic}, defined | future)
    assert len(refused) == 1, refused
    assert refused[0].startswith("synthetic.py:2: cites"), refused
    assert absent in refused[0], refused

    # --- PERMITTING ARM 2, a DIFFERENT shape from the bug: a citation that
    # ALSO matches no def line, yet must pass, because a FUTURE case declares
    # it. This is the arm that separates "unwritten by design" from "rotted",
    # and a guard that only refused would fail it.
    pending = undefined_future[0]
    spec = f"#: The later rung's node is ``{pending}``.\n"
    assert _unresolved_citation_errors({"spec.py": spec}, defined | future) == []

    # --- CONTROL OF THAT CONTROL: empty the FUTURE exemption and the SAME
    # citation must turn red. Otherwise the arm above would be green for some
    # other reason and the manifest's state field would not be load-bearing.
    without_exemption = _unresolved_citation_errors({"spec.py": spec}, defined)
    assert len(without_exemption) == 1, without_exemption
    assert pending in without_exemption[0], without_exemption

    # --- REFUSING ARM 2, a DIFFERENT shape: DRIFT. A citation that resolves
    # today stops resolving when its test is renamed or deleted. This is how
    # the class actually rots, and arm 1 (a name that never existed) cannot
    # see it.
    live_receipt = f"#: Proven by ``{live_node}``.\n"
    assert _unresolved_citation_errors({"drift.py": live_receipt}, defined | future) == []
    deleted = _unresolved_citation_errors(
        {"drift.py": live_receipt}, (defined | future) - {live_node}
    )
    assert len(deleted) == 1, deleted
    assert live_node in deleted[0], deleted

    # --- REFUSING ARM 3, a DIFFERENT shape: the SAME unresolved name cited
    # from the real frozen file, so the guard is shown to fire on the bytes it
    # is pointed at and not only on a dictionary key invented here.
    mutated = dict(texts)
    observer_key = str(OBSERVER_PATH.relative_to(REPO_ROOT))
    receipt = "``test_joined_setting_sources_are_validated_as_the_units_the_child_receives``"
    expected_line = next(
        number
        for number, line in enumerate(texts[observer_key].splitlines(), 1)
        if receipt in line
    )
    mutated[observer_key] = texts[observer_key].replace(receipt, f"``{absent}``", 1)
    assert mutated[observer_key] != texts[observer_key], "the perturbation changed nothing"
    on_bytes = _unresolved_citation_errors(mutated, defined | future)
    assert len(on_bytes) == 1, on_bytes
    assert on_bytes[0].startswith(f"{observer_key}:{expected_line}:"), on_bytes

    # --- DISCRIMINATION CONTROL: the scan is scoped to the rst-literal role.
    # A bare mention and a single-backtick span are prose, not receipts, and a
    # guard that fired on them would be paid off by being weakened.
    prose = f"#: see {absent} and `{absent}` for background.\n"
    assert _unresolved_citation_errors({"prose.py": prose}, defined | future) == []


# ==========================================================================
# 28 — an unlistable subtree cannot leave the plane reporting OBSERVED.
#      10s: one chmod-000 directory and two inventories.
# ==========================================================================


@pytest.mark.timeout(10)
def test_an_unlistable_subtree_degrades_the_inventory_and_the_plane(tmp_path):
    """``os.walk`` DISCARDS ``scandir`` errors unless ``onerror`` is supplied.

    THE CLASS THIS COVERS: a path the walk lost before ``record`` ran. Measured
    on the un-fixed bytes, a ``chmod 000`` directory holding one file produced
    ``observation_status=OBSERVED``, ``entry_truncated=False`` and no entry for
    the file: no cap fired, so no truncation flag could report it and
    ``any_bound_truncated`` could not see it either. A write inside that
    subtree is invisible to D10's ``set(post) - set(pre)`` and to D11.

    The negative control has a DIFFERENT SHAPE from the bug — an ordinary
    readable tree of the same layout, which must still read ``OBSERVED`` — so a
    fix that degraded every inventory would fail here rather than pass twice.
    """
    if os.geteuid() == 0:  # pragma: no cover - CI does not run as root
        pytest.fail("this probe cannot inform as root: mode 000 does not deny root")

    # --- PERMITTING ARM FIRST, so a failure below reads as "always degraded"
    # rather than as a real refusal.
    readable = tmp_path / "readable"
    (readable / "sub").mkdir(parents=True)
    (readable / "sub" / "hidden.txt").write_text("hello", encoding="utf-8")
    (readable / "top.txt").write_text("top", encoding="utf-8")
    clean = observer.inventory(readable)
    assert clean["observation_status"] == "OBSERVED"
    assert clean["entry_truncated"] is False
    assert any(p.endswith("hidden.txt") for p in clean["entries"]), sorted(clean["entries"])
    clean_count = clean["entry_count"]

    # --- REFUSING ARM: the same layout with the subdirectory unlistable.
    blocked = tmp_path / "blocked"
    (blocked / "sub").mkdir(parents=True)
    (blocked / "sub" / "hidden.txt").write_text("hello", encoding="utf-8")
    (blocked / "top.txt").write_text("top", encoding="utf-8")
    os.chmod(blocked / "sub", 0o000)
    try:
        walled = observer.inventory(blocked)
    finally:
        os.chmod(blocked / "sub", 0o755)

    # The evidence really is missing — otherwise this test would be asserting a
    # degradation for a subtree that was read anyway.
    assert not any(p.endswith("hidden.txt") for p in walled["entries"]), sorted(walled["entries"])
    assert walled["entry_count"] < clean_count, (walled["entry_count"], clean_count)
    # No cap fired, which is exactly why the status channel has to carry this.
    assert walled["entry_truncated"] is False
    assert walled["member_bytes_truncated"] is False
    assert observer._plane_bounds(walled)[0] is False, (
        "no bound flag can report a lost subtree; the status channel must"
    )
    assert walled["observation_status"] == "UNMEASURED", (
        "an unlistable subtree left the inventory reporting a clean OBSERVED"
    )

    # --- END TO END, a different shape: the recorded inventory reaches the
    # filesystem plane and takes every decision that reads it to UNMEASURED,
    # while a decision reading no filesystem plane is untouched.
    document = json.loads((VALID_DIR / "fs-inventory.json").read_text(encoding="utf-8"))
    document["post"] = walled
    run_root = _make_run_root(tmp_path / "walled_run")
    (run_root / "fs-inventory.json").write_text(json.dumps(document), encoding="utf-8")
    packet = _packet_from(OBSERVER_PATH, run_root)
    for decision_id in ("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS",
                        "D11_NO_SILENT_CONTENT_CHANGE",
                        "D12_MODE_OWNER_RECORDED_FAITHFULLY"):
        assert _decision_of(packet, decision_id)["observation_status"] == "UNMEASURED", decision_id
    assert _decision_of(packet, "D03_NO_STATIC_PRODUCT_IMPORT")["observation_status"] == "OBSERVED"


# ==========================================================================
# 29 — a degenerate declared root cannot decide D10, D11 or D12.
#      10s: pure string work plus two observer subprocesses.
# ==========================================================================


@pytest.mark.timeout(10)
def test_a_degenerate_declared_root_is_refused_and_degrades_the_filesystem_plane(tmp_path):
    """``declared_writable_roots`` is subject-supplied, so it cannot decide.

    THE CLASS THIS COVERS: an operand the SUBJECT supplies to the test that
    judges the subject. Measured on the un-fixed bytes,
    ``_is_within('/etc/passwd', '/')`` was ``True``, because the prefix test
    reduces to ``startswith('/')`` when the root normalizes to the filesystem
    root — the same shape as the ``_is_scratch_path`` defect fixed in this
    changeset, reached through a different door than the one ``reconcile()``
    guards.

    The refusal is a DEGRADATION, not a narrowing: silently treating a
    degenerate root as "nothing is declared" would let a candidate SUPPRESS
    D10, D11 and D12 with the same field it could otherwise use to satisfy
    them.

    Negative control of a different shape: a legitimate root must still PERMIT
    containment and must still leave the plane OBSERVED, so a fix that refused
    every root would fail here.
    """
    # --- INSTRUMENT CONTROL: the derived decision list answers in BOTH
    # directions. Empty, it would make every loop below vacuous; equal to the
    # whole decision set, it would prove nothing about the filesystem plane.
    assert _FILESYSTEM_DECISION_IDS, "no decision declares the filesystem plane"
    assert set(_FILESYSTEM_DECISION_IDS) < set(observer.DECISION_EVIDENCE_PLANES), (
        "every decision reads the filesystem plane; the derivation cannot inform"
    )

    # --- REFUSING ARM, the lexical helper. Each of these is a root a candidate
    # could write into its own fs-inventory.json.
    for degenerate in ("/", "//", "///", "", "   ", ".", "..", "relative/dir"):
        assert observer._is_declarable_root(degenerate) is False, degenerate
        assert observer._is_within("/etc/passwd", degenerate) is False, degenerate
    assert observer._is_declarable_root(None) is False

    # --- PERMITTING ARM: a legitimate root still contains what it should and
    # excludes what it should not.
    assert observer._is_declarable_root("/tmp/proof") is True
    assert observer._is_within("/tmp/proof/a.txt", "/tmp/proof") is True
    assert observer._is_within("/tmp/proof", "/tmp/proof") is True
    assert observer._is_within("/etc/passwd", "/tmp/proof") is False
    assert observer._is_within("/tmp/proofread/a", "/tmp/proof") is False, (
        "a sibling sharing a name prefix is not contained"
    )

    document = json.loads((VALID_DIR / "fs-inventory.json").read_text(encoding="utf-8"))
    declared = list(document["declared_writable_roots"])
    assert declared, "the fixture declares no root; this test could not inform"
    assert all(observer._is_declarable_root(root) for root in declared), declared

    # --- END TO END, PERMITTING: the untouched fixture stays OBSERVED.
    clean_root = _make_run_root(tmp_path / "roots_clean")
    clean = _packet_from(OBSERVER_PATH, clean_root)
    for decision_id in _FILESYSTEM_DECISION_IDS:
        assert _decision_of(clean, decision_id)["observation_status"] == "OBSERVED", decision_id

    # --- END TO END, REFUSING: the same fixture with "/" added to the roots.
    widened = copy.deepcopy(document)
    widened["declared_writable_roots"] = declared + ["/"]
    wide_root = _make_run_root(tmp_path / "roots_wide")
    (wide_root / "fs-inventory.json").write_text(json.dumps(widened), encoding="utf-8")
    wide = _packet_from(OBSERVER_PATH, wide_root)
    for decision_id in _FILESYSTEM_DECISION_IDS:
        assert _decision_of(wide, decision_id)["observation_status"] == "UNMEASURED", decision_id
    # The refused root is PUBLISHED, so a reader can recompute the refusal.
    assert "/" in wide["observation"]["filesystem"]["declared_writable_roots"]

    # --- THE DISCLOSED SET, DRIVEN RATHER THAN READ. The manifest names the
    # decisions a degenerate root degrades. Those ids are parsed OUT OF that
    # sentence and compared as a SET against the degradation the two packets
    # above actually show, because equal COUNTS are not equal sets and the
    # entry named two of the three for a full validation round.
    entry = _case(_manifest(), "P0-C01")["scope_limits"][-1]
    exception_clause = entry.split("The ONE exception:")[1].split(". ")[0]
    disclosed = sorted(set(_DECISION_PREFIX_RE.findall(exception_clause)))
    assert disclosed, "the disclosure names no decision; the sentence moved"

    def degraded(packet: dict[str, Any]) -> set[str]:
        return {
            record["decision_id"][:3]
            for record in packet["comparison"]["decisions"]
            if record["observation_status"] != "OBSERVED"
        }

    assert sorted(degraded(wide) - degraded(clean)) == disclosed, (
        f"a degenerate root degrades {sorted(degraded(wide) - degraded(clean))}; "
        f"the manifest discloses {disclosed}"
    )

    # --- CONTROL OF THAT CONTROL, a different shape: the difference must
    # DISCRIMINATE, not report every decision. A decision on another plane is
    # OBSERVED in BOTH packets, so the set above is the filesystem plane's
    # fold and not "the widened root broke everything".
    for untouched in ("D08_HOOK_TOOL_USE_ID_JOIN", "D09_HIDDEN_HOOK_NONZERO"):
        assert _decision_of(clean, untouched)["observation_status"] == "OBSERVED", untouched
        assert _decision_of(wide, untouched)["observation_status"] == "OBSERVED", untouched


# ==========================================================================
# 30 — a document too deep for the READERS, not only for the parser.
#      10s: an oversized fs-inventory and observer subprocesses.
# ==========================================================================


@pytest.mark.timeout(10)
def test_a_document_too_deep_for_the_readers_degrades_instead_of_crashing(tmp_path):
    """The CWE-674 guard was scoped to ``json.loads``, not to its consumers.

    THE CLASS THIS COVERS: a bound applied at one boundary and claimed for the
    whole path. A document just under the interpreter's recursion limit parses
    cleanly — ``malformed=False`` — and then defeats ``_verdict_leaks`` and
    ``_strip_private``, so ``reconcile()`` died with an uncaught
    ``RecursionError`` on input the module said it had decoded.

    The depth used here is derived from the live recursion limit rather than
    written as a literal, because the crashing depth is interpreter- and
    stack-dependent: the reviewer measured a crash at 600 and this machine
    survived to 1,200.

    Negative control of a different shape: a document nested to just under the
    declared limit must still be read and must still leave the plane OBSERVED.
    """
    def nest(depth: int) -> dict[str, Any]:
        node: Any = {"leaf": 1}
        for _ in range(depth):
            node = {"k": node}
        return node

    limit = observer.MAX_DOCUMENT_DEPTH
    assert limit < sys.getrecursionlimit(), (limit, sys.getrecursionlimit())

    # --- INSTRUMENT CONTROL: the depth probe answers in both directions, and
    # measuring the depth must not itself recurse.
    assert observer._exceeds_walk_depth(nest(limit + 50)) is True
    assert observer._exceeds_walk_depth(nest(2)) is False
    assert observer._exceeds_walk_depth(nest(sys.getrecursionlimit() * 3)) is True, (
        "the depth probe recursed and would crash on the input it exists to catch"
    )

    document = json.loads((VALID_DIR / "fs-inventory.json").read_text(encoding="utf-8"))

    # --- PERMITTING ARM: comfortably under the limit is ordinary evidence.
    shallow = copy.deepcopy(document)
    shallow_root = _make_run_root(tmp_path / "shallow")
    (shallow_root / "fs-inventory.json").write_text(json.dumps(shallow), encoding="utf-8")
    shallow_packet = _packet_from(OBSERVER_PATH, shallow_root)
    assert _decision_of(
        shallow_packet, "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS"
    )["observation_status"] == "OBSERVED"

    # --- REFUSING ARM: a depth that defeats the CONSUMERS, at the same place
    # the subject document really enters. Deep enough that the un-fixed bytes
    # crash on any stack.
    bombed = copy.deepcopy(document)
    bombed["post"]["entries"]["/proof/root/deep"] = nest(sys.getrecursionlimit() * 3)
    deep_root = _make_run_root(tmp_path / "deep")
    (deep_root / "fs-inventory.json").write_text(json.dumps(bombed), encoding="utf-8")
    proc = _run_observer(OBSERVER_PATH, deep_root)
    assert proc.returncode == 0, (
        f"the observer crashed on a deep document instead of degrading: "
        f"{proc.stderr[-1500:]}"
    )
    assert "RecursionError" not in proc.stderr, proc.stderr[-1500:]
    packet = json.loads(proc.stdout)
    filesystem = packet["observation"]["filesystem"]
    assert filesystem["evidence_malformed"] is True
    assert filesystem["observation_status"] == "ERROR"
    for decision_id in ("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS",
                        "D11_NO_SILENT_CONTENT_CHANGE",
                        "D12_MODE_OWNER_RECORDED_FAITHFULLY"):
        assert _decision_of(packet, decision_id)["observation_status"] == "ERROR", decision_id

    # --- THE SECOND ENTRY POINT, disclosed because the two instruments
    # DISAGREED: the file boundary degraded while a direct in-process
    # `reconcile()` on the same depth still died with an uncaught
    # RecursionError. A parse-boundary guard does not reach a caller-built
    # object, so the refusal is named at that entry point too.
    with pytest.raises(ValueError, match="MAX_DOCUMENT_DEPTH"):
        observer.reconcile({"filesystem": {"post": {"entries": nest(limit + 1)}}})
    shallow_observation = {"filesystem": {"declared_writable_roots": ["/proof/root"],
                                          "pre": {"entries": {}},
                                          "post": {"entries": {}},
                                          "observation_status": "OBSERVED"}}
    assert observer.reconcile(shallow_observation)["comparison"]["decisions"], (
        "the depth refusal fired on an ordinary observation"
    )


# ==========================================================================
# 31 — MAX_DISCREPANCIES is a bound like the others. 5s: pure in-process
#      construction of decision records.
# ==========================================================================


@pytest.mark.timeout(5)
def test_the_discrepancy_cap_is_flagged_and_its_pre_clip_extent_is_published():
    """A cap that clipped published output while reporting a clean OBSERVED.

    THE CLASS THIS COVERS: a bound with no flag. ``MAX_DISCREPANCIES`` clipped
    ``discrepancies`` and ``evidence_bounds.notes`` and published the POST-clip
    number as ``discrepancy_count``, so 60 findings were reported as 50 with
    ``any_bound_truncated=False`` — the extent removed by the thing that
    removed it.

    Negative control of a different shape: a record with fewer findings than
    the cap must stay unflagged and must keep its exact count, so a flag that
    was always on would fail here.
    """
    cap = observer.MAX_DISCREPANCIES
    assert "MAX_DISCREPANCIES" in observer.BOUND_CONSTANT_NAMES
    assert observer.TRUNCATION_BOUND_FLAGS["discrepancy_truncated"] == "MAX_DISCREPANCIES"
    assert "discrepancy_truncated" in observer.PUBLISHED_TRUNCATION_FLAGS

    # --- PERMITTING ARM: under the cap, nothing is clipped and nothing degrades.
    under = observer._decision("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS",
                               [f"finding {i:03d}" for i in range(cap - 1)], 100)
    assert under["discrepancy_truncated"] is False
    assert under["discrepancy_count"] == cap - 1 == len(under["discrepancies"])
    assert under["observation_status"] == "OBSERVED"

    # --- REFUSING ARM: over the cap, the list is clipped, the extent survives,
    # and the record cannot report a clean OBSERVED.
    over = observer._decision("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS",
                              [f"finding {i:03d}" for i in range(cap + 10)], 100)
    assert len(over["discrepancies"]) == cap
    assert over["discrepancy_count"] == cap + 10, "the clip removed its own extent"
    assert over["discrepancy_truncated"] is True
    assert over["observation_status"] == "UNMEASURED"

    # --- THE SECOND LIST THE SAME CAP CLIPS. One cap, one record, one flag.
    noisy = observer._decision(
        "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS", [], 100, "OBSERVED",
        observer._EvidenceBounds(False, False, [f"note {i:03d}" for i in range(cap + 3)]),
    )
    assert len(noisy["evidence_bounds"]["notes"]) == cap
    assert noisy["discrepancy_truncated"] is True
    assert noisy["observation_status"] == "UNMEASURED"

    # --- THE REBUILD CANNOT LOSE THE EXTENT. reconcile() rebuilds every record
    # from an ALREADY-CLIPPED list, which is where a naive recount would report
    # exactly the cap and call it whole.
    rebuilt = observer._decision(
        over["decision_id"], over["discrepancies"], over["evidence_count"],
        over["observation_status"], None, over["discrepancy_count"],
    )
    assert rebuilt["discrepancy_count"] == cap + 10
    assert rebuilt["discrepancy_truncated"] is True

    # --- THE PACKET TOTAL IS THE PRE-CLIP SUM, not the sum of the published
    # list lengths. Driven through reconcile() rather than asserted about it.
    observation = {
        "filesystem": {
            "declared_writable_roots": ["/proof/root"],
            "pre": {"entries": {}, "observation_status": "OBSERVED"},
            "post": {
                "entries": {f"/elsewhere/f{i:03d}": _path_entry(mode=0o644, uid=0)
                            for i in range(cap + 10)},
                "observation_status": "OBSERVED",
            },
            "observation_status": "OBSERVED",
        }
    }
    packet = observer.reconcile(observation)
    d10 = _decision_of(packet, "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS")
    assert len(d10["discrepancies"]) == cap
    assert d10["discrepancy_count"] == cap + 10
    assert d10["discrepancy_truncated"] is True
    assert packet["comparison"]["discrepancy_count"] >= cap + 10, (
        "the packet total counted the clipped lists, not the findings"
    )


# ==========================================================================
# 32 — the packet keeps every key the decisions cite. 5s: in-process.
# ==========================================================================


@pytest.mark.timeout(5)
def test_a_subject_supplied_key_survives_the_private_key_strip():
    """``_strip_private`` matched an ``_`` PREFIX, and inventory keys are paths.

    THE CLASS THIS COVERS: a packet that is not self-recomputable because the
    emitter deleted evidence a decision cites. A subject-supplied inventory key
    beginning with ``_`` was dropped from ``observation.filesystem.*.entries``
    while D10 still named it in ``discrepancies``.

    Reach, measured rather than assumed: real ``inventory()`` keys are absolute,
    so ``/tmp/x/__pycache__`` always survived. Only a relative key the subject
    wrote itself was reachable — the same untrusted-document boundary as the
    degenerate root — which is why this is a key-name registry and not a
    reshaping of the packet.

    Negative control of a different shape: the four bookkeeping keys this
    module adds must STILL be removed, or the closed schema would reject the
    packet and this fix would have traded one defect for another.
    """
    # --- INSTRUMENT CONTROL: the declared registry is what the module emits.
    emitted = {
        node.value
        for node in ast.walk(ast.parse(OBSERVER_PATH.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and re.fullmatch(r"_[a-z][a-z_]*", node.value)
    }
    private = set(observer.PRIVATE_BOOKKEEPING_KEYS)
    assert private, "the registry is empty; the strip would be a no-op"
    assert private <= emitted, sorted(private - emitted)

    # --- REFUSING ARM: a subject-supplied key must survive the strip.
    kept = observer._strip_private({"entries": {"_etc_hidden": {"kind": "file"},
                                                "/abs/path": {"kind": "file"}}})
    assert sorted(kept["entries"]) == ["/abs/path", "_etc_hidden"], kept

    # --- PERMITTING ARM: every declared bookkeeping key is still removed.
    stripped = observer._strip_private(
        {name: 1 for name in private} | {"kept": 2, "nested": {name: 3 for name in private}}
    )
    assert stripped == {"kept": 2, "nested": {}}, stripped

    # --- END TO END: a discrepancy names a path, and the packet contains it.
    observation = {
        "filesystem": {
            "declared_writable_roots": ["/proof/root"],
            "pre": {"entries": {}, "observation_status": "OBSERVED"},
            "post": {"entries": {"_etc_hidden": {"mode": 0o644, "uid": 0,
                                                 "acl_state": "UNMEASURED"}},
                     "observation_status": "OBSERVED"},
            "observation_status": "OBSERVED",
        },
        "schema_audit": {"_examined": 3, "observation_status": "OBSERVED"},
    }
    packet = observer.reconcile(observation)
    cited = _decision_of(packet, "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS")["discrepancies"]
    assert any("_etc_hidden" in text for text in cited), cited
    entries = packet["observation"]["filesystem"]["post"]["entries"]
    assert "_etc_hidden" in entries, "a cited path is absent from the observation it cites"
    assert "_examined" not in packet["observation"]["schema_audit"]


# ==========================================================================
# 33 — an inner timeout that can never fire is not a timeout. 10s: AST only.
# ==========================================================================


def _module_int_constants(tree: ast.Module) -> dict[str, int]:
    """Module-level ``NAME = <int>`` bindings, so a budget can be named."""
    values: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, int) and not isinstance(node.value.value, bool):
                    values[target.id] = node.value.value
    return values


def _resolve_int(node: ast.AST, constants: dict[str, int]) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _inner_timeout_violations(source: str) -> list[str]:
    """Every ``subprocess.run`` timeout that cannot fire inside a node's budget.

    Function scope is by SUBTREE, so a closure defined inside a test is charged
    to that test, and callees are followed transitively by name through the
    module's own function definitions. It is not a call-graph analysis and does
    not resolve aliases or indirection; it is a ratchet over the direct shapes
    this module actually uses.
    """
    tree = ast.parse(source)
    constants = _module_int_constants(tree)
    timeouts: dict[str, set[int]] = {}
    callees: dict[str, set[str]] = {}
    budgets: dict[str, int] = {}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        found: set[int] = set()
        called: set[str] = set()
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if isinstance(child.func, ast.Name):
                called.add(child.func.id)
            target = child.func
            is_run = (
                isinstance(target, ast.Attribute)
                and target.attr == "run"
                and isinstance(target.value, ast.Name)
                and target.value.id == "subprocess"
            )
            if not is_run:
                continue
            for keyword in child.keywords:
                if keyword.arg == "timeout":
                    resolved = _resolve_int(keyword.value, constants)
                    if resolved is not None:
                        found.add(resolved)
        timeouts[node.name] = found
        callees[node.name] = called
        for decorator in node.decorator_list:
            if not (isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "timeout"
                    and decorator.args):
                continue
            resolved = _resolve_int(decorator.args[0], constants)
            if resolved is not None:
                budgets[node.name] = resolved

    def reachable(name: str) -> set[int]:
        seen: set[str] = set()
        stack = [name]
        found: set[int] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            found |= timeouts.get(current, set())
            stack.extend(callees.get(current, set()))
        return found

    problems: list[str] = []
    for name, budget in sorted(budgets.items()):
        if not name.startswith("test_"):
            continue
        for value in sorted(reachable(name)):
            if value >= budget:
                problems.append(
                    f"{name}: reaches a subprocess timeout of {value}s inside a "
                    f"{budget}s node budget, so it can never fire"
                )
    return problems


@pytest.mark.timeout(10)
def test_every_inner_subprocess_timeout_can_fire_inside_its_node_budget():
    """A subprocess timeout above its node's budget is dead code that reads as headroom.

    THE CLASS THIS COVERS: a nested limit the enclosing limit preempts. The
    measured instance was a ``subprocess.run(..., timeout=60)`` inside a node
    marked ``@pytest.mark.timeout(20)``: a hung collection produced an opaque
    pytest-timeout instead of the subprocess diagnostic, and the ``60`` read as
    headroom that did not exist.

    WHAT THIS IS: a syntactic ratchet over the direct shapes this module uses —
    a module-level helper called by name, and a closure defined inside a test.
    It resolves no aliases and computes no reachability; its reach is not
    characterised.
    """
    source = NODE_FILE.read_text(encoding="utf-8")

    # --- INSTRUMENT CONTROL: the collector must actually find both the budgets
    # and the timeouts, or "no violations" would mean "found nothing".
    tree = ast.parse(source)
    constants = _module_int_constants(tree)
    assert constants.get("SUBPROCESS_TIMEOUT_S") == SUBPROCESS_TIMEOUT_S
    assert constants.get("FROZEN_C01_BUDGET_S") == FROZEN_C01_BUDGET_S
    assert sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "timeout"
                for d in node.decorator_list)
    ) >= 29, "the budget collector found too few decorated nodes"

    # --- PERMITTING ARM: the shipped module is clean.
    assert _inner_timeout_violations(source) == [], _inner_timeout_violations(source)

    # --- REFUSING ARM 1: the measured defect, restored at its real site.
    anchor = "        timeout=COLLECT_TIMEOUT_S,\n        cwd=str(REPO_ROOT),"
    assert anchor in source, "the collection helper moved; this control proves nothing"
    restored = _inner_timeout_violations(
        source.replace(anchor, "        timeout=60,\n        cwd=str(REPO_ROOT),", 1)
    )
    assert any("test_manifest_declared_node_count_equals_pytest_collected_count" in p
               and "60s" in p for p in restored), restored

    # --- REFUSING ARM 2, a DIFFERENT shape: a closure inside a low-budget test
    # rather than a module-level helper reached by name.
    closure = (
        "\n\n@pytest.mark.timeout(5)\n"
        "def test_probe_with_a_closure_that_outlives_its_budget():\n"
        "    def inner():\n"
        "        return subprocess.run(['true'], timeout=99)\n"
        "    return inner\n"
    )
    assert any("test_probe_with_a_closure_that_outlives_its_budget" in p and "99s" in p
               for p in _inner_timeout_violations(source + closure))

    # --- PERMITTING CONTROL of the SAME two shapes: the identical closure with
    # a timeout that CAN fire must stay green, so the guard is shown to fire on
    # the relationship and not on the syntax.
    benign = closure.replace("timeout=99", "timeout=1").replace(
        "test_probe_with_a_closure_that_outlives_its_budget",
        "test_probe_with_a_closure_inside_its_budget",
    )
    assert _inner_timeout_violations(source + benign) == []


# ==========================================================================
# 34 — a hook receipt the debug reader cannot READ must degrade the plane,
#      not disappear from it. 10s: three observer subprocesses plus in-process
#      predicate work.
# ==========================================================================


@pytest.mark.timeout(10)
def test_an_unreadable_hook_receipt_degrades_the_debug_plane_instead_of_vanishing(tmp_path):
    """``_parse_debug_hooks`` dropped every line its record regex missed.

    THE CLASS THIS COVERS: a record lost UPSTREAM of the decision that would
    have read it. No bound fires, no count changes, and the plane still reports
    OBSERVED — the same fail-open shape as an evidence line lost past a cap,
    reached through a different door. It is the debug log's missing malformed
    channel: ``_read_jsonl`` has counted ``unparsable`` for the stream since the
    beginning, and the debug reader had no such concept at all.

    Measured on the un-fixed bytes, with one line appended to the valid log::

        hook PreToolUse tool_use_id=T command=x exit=2 stdout_bytes=0  -> UNMEASURED
        hook PreToolUse command=x tool_use_id=T exit=2 stdout_bytes=0  -> OBSERVED

    The same facts with two fields transposed, and a NON-ZERO HOOK EXIT — the
    one record D09 exists to find — became invisible. The fixtures here are
    digest-frozen, so this was not exploitable at P0-A; the observer is frozen
    for C07, which runs it against real Claude debug logs whose field order is
    not ours to choose.

    NEGATIVE CONTROLS OF A DIFFERENT SHAPE, and they are the load-bearing half:
    the cheap fix — treating any line containing the word ``hook`` as a receipt
    — would drive every real debug log to a malformed status. Ordinary lines
    are driven through, each defeating a different sloppy predicate: one
    mentioning hook CONFIGURATION, one mentioning ``hooks`` as a plural, one
    carrying a ``tool_use_id`` with no hook token at all, and one carrying
    neither token.
    """
    valid_log = (VALID_DIR / "debug.log").read_text(encoding="utf-8")
    stamp = "[2026-09-07T09:15:03.950Z] [DEBUG] "
    parsable = stamp + (
        "hook PreToolUse tool_use_id=toolu_09ZZZ command=x exit=2 stdout_bytes=0"
    )
    reordered = stamp + (
        "hook PreToolUse command=x tool_use_id=toolu_09ZZZ exit=2 stdout_bytes=0"
    )
    truncated_record = stamp + "hook PreToolUse tool_use_id=toolu_09ZZZ command=x exit=2"
    unrelated = [
        stamp + "hook configuration loaded from project settings",
        stamp + "resolving hooks for PreToolUse matcher=Bash",
        stamp + "tool_use_id=toolu_03CCC result streamed bytes=412",
        stamp + "session start session_id=" + SESSION_UUID,
    ]

    # --- INSTRUMENT CONTROL: the predicate answers in BOTH directions before
    # any plane status is read from it. A predicate that claimed everything, or
    # nothing, would make every cell below vacuous.
    assert observer._debug_unparsable(valid_log) == 0, (
        "the untouched fixture must carry no unreadable receipt"
    )
    assert observer._debug_unparsable(parsable) == 0, (
        "a receipt the record regex READS is not unparsable"
    )
    assert observer._debug_unparsable(reordered) == 1
    assert observer._debug_unparsable(truncated_record) == 1, (
        "a receipt missing a field is a receipt this reader was defeated by"
    )
    for line in unrelated:
        assert observer._debug_unparsable(line) == 0, (
            f"an ordinary log line was claimed as an unreadable receipt: {line!r}"
        )
    # Counted, not merely detected: two lost receipts must not read as one.
    assert observer._debug_unparsable(reordered + "\n" + truncated_record) == 2

    # --- THE OVER-FIRE, ASSERTED AS INTENDED RATHER THAN LEFT UNCONTROLLED.
    # The predicate claims any line carrying BOTH tokens, so a benign line that
    # happens to carry them is claimed and drives the plane to ERROR. That is
    # `observe_claude_execution._DEBUG_RECEIPT_SHAPE_RES`, as
    # `_debug_receipts_claimed` applies it, read literally — cited by SYMBOL
    # because the `:NNNN` this replaced had rotted onto the EVIDENCE_* filename
    # constants and the head of an unrelated docstring, and the file-prefixed
    # form slips past the citation ratchet in section 54, which only refuses a
    # bare `:NNNN`. The symbols are asserted to exist below, so a rename turns
    # this red instead of leaving a confident pointer at the wrong lines. It is
    # the FAIL-CLOSED direction: the alternative — narrowing the predicate
    # until such a line passes — is the very drop this whole section exists to
    # stop, because a permuted receipt is indistinguishable from a mention by
    # any test the two tokens do not decide. Pinned here so that loosening it
    # turns this red instead of turning the debug plane quietly fail-open.
    for cited in ("_DEBUG_RECEIPT_SHAPE_RES", "_debug_receipts_claimed"):
        assert hasattr(observer, cited), (
            f"the comment above cites observe_claude_execution.{cited}, which no "
            "longer exists; a symbol citation that resolves to nothing is the "
            "same rot as the line number it replaced"
        )
    over_fire = stamp + "dispatching tool_use_id=toolu_01AAA to hook chain"
    assert observer._debug_unparsable(over_fire) == 1, (
        "the predicate no longer claims a line carrying both tokens; a permuted "
        "receipt can now be dropped in silence"
    )
    # CONTROL OF THAT CONTROL, a different shape: over-firing on BOTH tokens is
    # not over-firing on EITHER. The same benign sentence with one token
    # removed must pass, or the assertion above would be satisfied by a
    # predicate that simply claimed every line.
    assert observer._debug_unparsable(stamp + "dispatching to hook chain") == 0
    assert observer._debug_unparsable(stamp + "dispatching tool_use_id=toolu_01AAA") == 0

    # --- BOTH DEBUG READERS AGREE, because they share the one predicate. A
    # count published by `_count_lines` that disagreed with what
    # `_parse_debug_hooks` reports would put the two halves of the debug plane
    # into conflict about which lines were lost.
    attack_log = tmp_path / "attack.log"
    attack_log.write_text(valid_log + reordered + "\n", encoding="utf-8")
    assert observer._parse_debug_hooks(attack_log).unparsable == 1
    assert observer._count_lines(attack_log).unparsable == 1

    def packet_for(name: str, extra: str | None) -> dict[str, Any]:
        # The run root is named EXPLICITLY, never derived from hash(): PYTHONHASHSEED
        # randomises str hashes per process, so a derived name is a different
        # directory on every run and a collision would silently reuse one.
        run_root = _make_run_root(tmp_path / f"run_{name}")
        if extra is not None:
            (run_root / "debug.log").write_text(valid_log + extra + "\n", encoding="utf-8")
        return _packet_from(OBSERVER_PATH, run_root)

    # --- PERMITTING ARM: the untouched fixture stays clean end to end. Without
    # this, a change that degraded every log would satisfy the refusing arm.
    clean = packet_for("clean", None)
    assert clean["observation"]["debug"]["unparsable_records"] == 0
    assert clean["observation"]["debug"]["observation_status"] == "OBSERVED"
    assert clean["observation"]["hooks"]["evidence_malformed"] is False
    assert clean["observation"]["hooks"]["observation_status"] == "OBSERVED"
    for decision_id in ("D08_HOOK_TOOL_USE_ID_JOIN", "D09_HIDDEN_HOOK_NONZERO"):
        assert _decision_of(clean, decision_id)["observation_status"] == "OBSERVED", decision_id

    # --- PERMITTING ARM 2, a DIFFERENT shape: an ordinary log line that is
    # NOT a receipt must leave the plane exactly as clean. This is the arm that
    # fails if the predicate is widened to "mentions a hook".
    benign = packet_for("benign", unrelated[1])
    assert benign["observation"]["debug"]["unparsable_records"] == 0, (
        "an ordinary log line degraded the plane; every real debug log would"
    )
    assert benign["observation"]["debug"]["observation_status"] == "OBSERVED"
    assert _decision_of(benign, "D09_HIDDEN_HOOK_NONZERO")["observation_status"] == "OBSERVED"

    # --- REFUSING ARM: the reproducer, end to end through the observer CLI.
    attacked = packet_for("attacked", reordered)
    assert attacked["observation"]["debug"]["unparsable_records"] == 1
    assert attacked["observation"]["debug"]["observation_status"] == "ERROR", (
        "a receipt this module could not read must be ERROR, matching the "
        "stream's malformed channel: the reader was defeated, which is a "
        "failure and not a partial measurement"
    )
    assert attacked["observation"]["hooks"]["evidence_malformed"] is True
    assert attacked["observation"]["hooks"]["observation_status"] == "ERROR"
    for decision_id in ("D08_HOOK_TOOL_USE_ID_JOIN", "D09_HIDDEN_HOOK_NONZERO"):
        assert _decision_of(attacked, decision_id)["observation_status"] != "OBSERVED", (
            f"{decision_id} read clean over a hook receipt the observer could not read"
        )

    # --- ISOLATION: only the debug log was touched, so no other bounded plane
    # may flag. A change that set malformed everywhere would pass the arm above
    # while telling the reader nothing.
    for other in ("stream", "transcript"):
        assert attacked["observation"][other]["unparsable_records"] == 0, other
        assert attacked["observation"][other]["observation_status"] == "OBSERVED", other


# ==========================================================================
# 35 — the supervisor-trust disclosure, re-measured against the observer.
#      10s: observer subprocesses over edited supervisor documents.
# ==========================================================================


@pytest.mark.timeout(10)
def test_the_supervisor_trust_disclosure_matches_what_the_observer_actually_does(tmp_path):
    """The manifest's last ``scope_limits`` entry, driven rather than read.

    THE CLASS THIS COVERS: a disclosure that described the behaviour correctly
    when written and silently stopped matching it. The degenerate-root fix
    changed what a widened root list does and left the sentence saying no test
    shows a refusal — which cost a full validation round. Prose about what the
    observer does NOT detect is exactly the prose that rots into a false
    reassurance, because nothing fails when it goes stale.

    Every behavioural clause of that entry is a cell below. What it claims:

    * a widened list of DECLARABLE roots reads CLEAN — the observer does not
      resist, flag or degrade on one;
    * a DEGENERATE root is the one exception, and degrades D10, D11 and D12;
    * the observer measures digest, byte count, record count and bounds of the
      files handed to it, NEVER the truth of their records — so a deletion made
      CONSISTENTLY across ``stream.jsonl`` and ``debug.log`` reads clean, while
      an inconsistent one does not.

    The last pair is the negative control of a different shape: the clean cell
    and the flagged cells are the SAME deletion applied to different subsets of
    the documents, so this cannot pass by the observer being blind to all four.
    """
    entry = _case(_manifest(), "P0-C01")["scope_limits"][-1]
    assert "declared_writable_roots" in entry and "stream.jsonl" in entry, (
        "this test is bound to the supervisor-trust entry; it moved"
    )

    inventory = json.loads((VALID_DIR / "fs-inventory.json").read_text(encoding="utf-8"))
    declared = list(inventory["declared_writable_roots"])
    assert declared, "the fixture declares no root; this test could not inform"

    def planes_for(roots: list[str], name: str) -> str:
        run_root = _make_run_root(tmp_path / f"fs_{name}")
        document = copy.deepcopy(inventory)
        document["declared_writable_roots"] = roots
        (run_root / "fs-inventory.json").write_text(json.dumps(document), encoding="utf-8")
        return observer._filesystem_planes(run_root)["observation_status"]

    # --- CLAUSE 1, PERMITTING: ordinary widening still reads clean. Two extra
    # roots of different shapes, neither of which the fixture declares.
    assert planes_for(declared, "base") == "OBSERVED"
    for extra in ("/tmp", "/private"):
        assert planes_for(declared + [extra], extra.strip("/")) == "OBSERVED", (
            f"widening the roots with {extra} degraded the plane; the manifest "
            "discloses that ordinary widening reads CLEAN"
        )

    # --- CLAUSE 2, REFUSING: a degenerate root is the ONE exception.
    assert planes_for(declared + ["/"], "degenerate") == "UNMEASURED"

    stream = (VALID_DIR / "stream.jsonl").read_text(encoding="utf-8")
    debug = (VALID_DIR / "debug.log").read_text(encoding="utf-8")
    victim = "toolu_02BBB"
    assert victim in stream and victim in debug, (victim, "not in both documents")

    def packet_without(victim_in_stream: bool, victim_in_debug: bool, name: str) -> dict:
        run_root = _make_run_root(tmp_path / f"del_{name}")
        if victim_in_stream:
            (run_root / "stream.jsonl").write_text(
                "".join(
                    line + "\n"
                    for line in stream.splitlines()
                    if line.strip() and victim not in line
                ),
                encoding="utf-8",
            )
        if victim_in_debug:
            (run_root / "debug.log").write_text(
                "".join(
                    line + "\n" for line in debug.splitlines() if victim not in line
                ),
                encoding="utf-8",
            )
        return _packet_from(OBSERVER_PATH, run_root)

    # --- CLAUSE 3, the CLEAN cell: delete every record for the id from BOTH
    # documents. The observer measures digest, bytes, records and bounds for
    # each file and finds nothing wrong, because nothing IS inconsistent.
    coordinated = packet_without(True, True, "both")
    for decision_id in ("D08_HOOK_TOOL_USE_ID_JOIN", "D09_HIDDEN_HOOK_NONZERO"):
        record = _decision_of(coordinated, decision_id)
        assert record["observation_status"] == "OBSERVED", (decision_id, record)
        assert record["discrepancies"] == [], (
            f"{decision_id} flagged a CONSISTENT deletion; the manifest "
            "discloses that it cannot see one, and that disclosure is now false"
        )

    # --- CLAUSE 3, the FLAGGED cells: the SAME deletion, applied to one
    # document only. An inconsistent deletion IS visible, so the clean cell
    # above is a real limit of the evidence rather than global blindness.
    debug_only = packet_without(False, True, "debug")
    assert _decision_of(debug_only, "D09_HIDDEN_HOOK_NONZERO")["observation_status"] != "OBSERVED", (
        "a deleted hook receipt read clean"
    )
    stream_only = packet_without(True, False, "stream")
    assert _decision_of(stream_only, "D08_HOOK_TOOL_USE_ID_JOIN")["discrepancies"] != [], (
        "a deleted stream record left its receipt unflagged as an orphan"
    )


# ==========================================================================
# 36 — the frozen node-count gate pays for exactly ONE collection.
#      5s: AST only, no subprocess.
# ==========================================================================


@pytest.mark.timeout(5)
def test_the_node_count_gate_pays_for_exactly_one_collection_subprocess():
    """A 20s frozen budget is not headroom if the node spends it twice over.

    THE CLASS THIS COVERS: a frozen budget consumed by fixed per-invocation
    cost rather than by work. ``pytest --collect-only`` over this node file
    collects 90 tests in 0.08s inside a run costing ~3.6s: ~3.6s is interpreter,
    conftest and plugin start-up, paid per INVOCATION — the same target with
    every node deselected still costs ~3.6s. The gate ran two of them and cost
    ~7.2s against a frozen 20s budget — 2.8x margin, which a 2-core runner at
    ~3x slower turns into a permanently red gate that cannot be unfrozen.
    Splitting the collection again would reintroduce it silently, because the
    node would still PASS locally.

    ONE SIGNIFICANT FIGURE AND NO INTERVAL, for the reason recorded in full at
    ``_collect_node_counts``: the ranges this text used to carry were a five-run
    min/max presented as a population range, and a 25-run re-measurement put
    ZERO samples inside them.

    Structural, not timed: a wall-clock assertion on a shared runner is a flake
    generator, and the property that actually matters is the invocation COUNT.

    Negative control of a different shape: the guard must still refuse a
    SECOND collection introduced anywhere in the node — including one reached
    through a helper rather than written inline — and must permit a node that
    legitimately runs one.
    """
    tree = ast.parse(NODE_FILE.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    gate = "test_manifest_declared_node_count_equals_pytest_collected_count"
    assert gate in functions, f"{gate} was renamed; this guard is unbound"

    def collection_calls(node: ast.AST, seen: frozenset[str] = frozenset()) -> int:
        """Collections this node performs, following helpers it calls by name."""
        total = 0
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            name = getattr(child.func, "id", None) or getattr(child.func, "attr", None)
            if name == "run" and any(
                "pytest" in getattr(item, "value", None).__str__()
                for arg in child.args
                for item in (ast.walk(arg))
                if isinstance(item, ast.Constant)
            ):
                total += 1
            elif name in functions and name not in seen and name != getattr(node, "name", ""):
                total += collection_calls(functions[name], seen | {name})
        return total

    # --- INSTRUMENT CONTROL: the counter must see the collection that IS
    # there. A counter returning 0 for everything would pass the arm below
    # vacuously.
    assert collection_calls(functions["_collect_node_counts"]) == 1, (
        "the counter cannot see the collection subprocess it exists to count"
    )

    # --- PERMITTING ARM: the shipped gate reaches exactly one.
    assert collection_calls(functions[gate]) == 1, (
        "the node-count gate must perform exactly ONE pytest collection; "
        "each additional one costs ~3.6s of fixed start-up against a frozen "
        "20s budget"
    )

    # --- REFUSING ARM, the reproducer's shape: a second collection reached
    # through the SAME helper, as the pre-fix bytes did.
    split = ast.parse(
        "def probe():\n"
        "    a = _collect_node_counts([x], [x])\n"
        "    b = _collect_node_counts([y], [y])\n"
        "    return a, b\n"
    ).body[0]
    assert collection_calls(split) == 2, "a re-split gate would not be refused"

    # --- REFUSING ARM 2, a DIFFERENT shape: a collection written INLINE rather
    # than reached through the declared helper, which a helper-name allowlist
    # would have missed entirely.
    inline = ast.parse(
        "def probe():\n"
        "    a = _collect_node_counts([x], [x])\n"
        "    return subprocess.run([sys.executable, '-m', 'pytest', '--collect-only'])\n"
    ).body[0]
    assert collection_calls(inline) == 2, "an inline second collection would not be refused"

    # --- PERMITTING CONTROL of the same two shapes: a node that runs a
    # NON-pytest subprocess beside its one collection stays green, so the guard
    # is shown to fire on pytest collections and not on subprocesses at large.
    benign = ast.parse(
        "def probe():\n"
        "    a = _collect_node_counts([x], [x])\n"
        "    return subprocess.run(['git', 'status'])\n"
    ).body[0]
    assert collection_calls(benign) == 1


# ==========================================================================
# 37 — the CLASS guard: a NUMBER this rung's prose quotes is pinned to the
#      thing it counts. 5s: three file reads, no subprocess.
# ==========================================================================
#
# Section 26 re-measures every COMMAND the manifest quotes and section 27
# resolves every TEST NAME the frozen bytes cite. Neither pins a bare NUMBER
# written into a docstring or a section header — which is exactly where a
# stale count survives, because nothing reads it and nothing fails when it
# rots. Two claim classes here are mechanically checkable and are checked; a
# claim class that is not checkable is DELETED from the prose rather than left
# wearing a checked field's authority, which is why the per-section subprocess
# tallies these headers used to carry are gone.
#
# A RATCHET over the claim shapes present on these bytes, not a claim that no
# other numeric shape exists. Its job is narrower and mechanical: a claim of
# one of these two shapes cannot go stale without something refusing.
#
# SCOPE, stated rather than assumed: every ``-line module`` claim on these
# bytes is about the observer, so that is the module the size is measured
# against. A claim written about a DIFFERENT module would be refused here
# until someone binds it — the conservative direction, and the same ratchet
# discipline _SCOPE_LIMIT_COMMAND_SPANS applies to quoted commands.

#: ``... collects <N> tests ...`` — a count of what pytest collects from the
#: frozen node file. Thousands separators are accepted so that a claim written
#: ``1,234`` cannot slip past a digits-only pattern still reading as a claim.
_COLLECTED_COUNT_CLAIM_RE = re.compile(r"collects\s+([0-9][0-9,]*)\s+tests\b")

#: ``a ~<N>-line module`` — an approximate size for the observer module.
_MODULE_SIZE_CLAIM_RE = re.compile(r"~([0-9][0-9,]*)-line module\b")

#: What the ``~`` in a module-size claim is PERMITTED to mean, written down
#: instead of left to the reader. A claim outside this band of the real line
#: count is refused; one inside it is an approximation, which is what the
#: tilde says. 5% of the observer is roughly a hundred lines, so an ordinary
#: edit does not turn this red and a figure from a previous rung does.
_MODULE_SIZE_TOLERANCE = 0.05


def _quoted_number_errors(
    texts: dict[str, str], *, collected: int, module_lines: int
) -> list[str]:
    """``file:line`` for every quoted number that disagrees with what it counts.

    ``collected`` and ``module_lines`` are the caller's MEASURED values. This
    function holds no expectation of its own: a number written here would be
    the same stale-by-construction defect one level up.
    """
    problems: list[str] = []
    band = max(1, round(module_lines * _MODULE_SIZE_TOLERANCE))
    for label in sorted(texts):
        for number, line in enumerate(texts[label].splitlines(), 1):
            for claim in _COLLECTED_COUNT_CLAIM_RE.findall(line):
                stated = int(claim.replace(",", ""))
                if stated != collected:
                    problems.append(
                        f"{label}:{number}: states a collected count of {stated}; "
                        f"pytest collects {collected}"
                    )
            for claim in _MODULE_SIZE_CLAIM_RE.findall(line):
                stated = int(claim.replace(",", ""))
                if abs(stated - module_lines) > band:
                    problems.append(
                        f"{label}:{number}: states a module size of {stated} lines; "
                        f"the observer is {module_lines} lines, outside the "
                        f"+/-{band}-line band the tilde is permitted to mean"
                    )
    return problems


@pytest.mark.timeout(5)
def test_every_number_this_rungs_prose_quotes_is_pinned_to_what_it_counts():
    """A count written into prose is a claim, and it rots with nothing refusing.

    THE CLASS THIS COVERS: a number quoted in a docstring or a section header
    that no field, test or command reads. It is correct when typed, it goes
    stale on the next edit, and — unlike a wrong assertion — nothing turns red.
    Two independent validators found the same stale collected count in these
    frozen bytes while every other receipt in the changeset reproduced, and it
    contradicted a manifest field written in its own commit.

    THE EXPECTATIONS ARE DERIVED, NEVER WRITTEN HERE. The collected count comes
    from ``collection_completeness.expected_test_count``, which
    ``test_manifest_declared_node_count_equals_pytest_collected_count`` pins to
    a real ``pytest --collect-only`` — so this guard inherits that binding
    instead of paying for a second collection, which
    ``test_the_node_count_gate_pays_for_exactly_one_collection_subprocess``
    forbids. The module size is counted off the module. A hardcoded expectation
    would be the defect this exists to stop, moved up one level.

    Every refusing literal below is BUILT AT RUNTIME rather than written as a
    literal, because a stale-looking number spelled out in this file would be
    read by the very scan it is meant to exercise.
    """
    manifest = _manifest()
    collected = int(
        _case(manifest, "P0-C01")["collection_completeness"]["expected_test_count"]
    )
    observer_text = OBSERVER_PATH.read_text(encoding="utf-8")
    module_lines = len(observer_text.splitlines())
    # The two frozen files section 27 scans for citations are the two files
    # scanned here, read from that one helper: a file whose prose is checked
    # for a rotted pointer and not for a rotted number is the gap again.
    texts = _frozen_citation_texts()

    # --- INSTRUMENT CONTROL 1: the measured operands are real. A second,
    # independent count of the module (newline bytes, as `wc -l` counts) must
    # agree with splitlines(), or the size band is measured against a number
    # this test invented.
    assert module_lines > 100, module_lines
    assert observer_text.endswith("\n"), "no trailing newline; the two counts diverge"
    assert observer_text.count("\n") == module_lines, (
        f"splitlines() reports {module_lines}, newline bytes report "
        f"{observer_text.count(chr(10))}"
    )
    assert collected > 1, collected

    # --- INSTRUMENT CONTROL 2, the one that refutes a FALSE CLEAN. The scan
    # must FIND a claim of each class on the shipped bytes. A regex that
    # matched nothing would return no findings for any input, and "no
    # findings" is the exact answer this guard exists to make trustworthy.
    found_counts = [
        claim for text in texts.values() for claim in _COLLECTED_COUNT_CLAIM_RE.findall(text)
    ]
    found_sizes = [
        claim for text in texts.values() for claim in _MODULE_SIZE_CLAIM_RE.findall(text)
    ]
    assert len(found_counts) >= 2, found_counts
    assert len(found_sizes) >= 2, found_sizes

    # --- PERMITTING ARM: on the shipped bytes every quoted number agrees with
    # what it counts.
    assert _quoted_number_errors(
        texts, collected=collected, module_lines=module_lines
    ) == [], "\n".join(
        _quoted_number_errors(texts, collected=collected, module_lines=module_lines)
    )

    # --- CONTROL OF THAT ARM: the green above is agreement, not inertness.
    # Hand the SAME shipped bytes a different truth and every claim must be
    # reported. This is the arm that separates a working scan from one that
    # cannot fail.
    inert_check = _quoted_number_errors(
        texts, collected=collected + 1, module_lines=module_lines * 2
    )
    assert len(inert_check) == len(found_counts) + len(found_sizes), inert_check

    # --- REFUSING ARM 1, the reproducer's shape: a count that DRIFTED DOWN,
    # left behind when tests were added.
    stale_low = "Measured: this node file " + "collects " + str(collected - 4) + " tests.\n"
    refused = _quoted_number_errors(
        {"synthetic.py": stale_low}, collected=collected, module_lines=module_lines
    )
    assert len(refused) == 1, refused
    assert refused[0].startswith("synthetic.py:1: states a collected count"), refused

    # --- REFUSING ARM 2, a DIFFERENT shape: drift the OTHER WAY, and written
    # with a thousands separator. A guard fitted to "one stale small number"
    # sees neither.
    drifted_up = "#: the suite " + "collects " + f"{collected + 1000:,}" + " tests today.\n"
    assert len(
        _quoted_number_errors(
            {"synthetic.py": drifted_up}, collected=collected, module_lines=module_lines
        )
    ) == 1

    # --- REFUSING ARM 3, a DIFFERENT CLASS: the module-size claim, driven with
    # the figure these headers actually carried from a previous rung.
    historical = "#      20s: AST parses of a " + "~2," + "100-line module.\n"
    size_refused = _quoted_number_errors(
        {"synthetic.py": historical}, collected=collected, module_lines=module_lines
    )
    assert len(size_refused) == 1, size_refused
    assert "states a module size of 2100 lines" in size_refused[0], size_refused

    # --- REFUSING ARM 4, a DIFFERENT shape again: the claim written on the
    # REAL frozen bytes rather than on a dictionary key invented here, so the
    # guard is shown to fire on the file it is pointed at, at the right line.
    node_key = str(NODE_FILE.relative_to(REPO_ROOT))
    true_span = "collects " + str(collected) + " tests"
    wrong_span = "collects " + str(collected - 4) + " tests"
    expected_line = next(
        number
        for number, line in enumerate(texts[node_key].splitlines(), 1)
        if true_span in line
    )
    mutated = dict(texts)
    mutated[node_key] = texts[node_key].replace(true_span, wrong_span, 1)
    assert mutated[node_key] != texts[node_key], "the perturbation changed nothing"
    on_bytes = _quoted_number_errors(
        mutated, collected=collected, module_lines=module_lines
    )
    assert len(on_bytes) == 1, on_bytes
    assert on_bytes[0].startswith(f"{node_key}:{expected_line}:"), on_bytes

    # --- PERMITTING CONTROL 1: the band the tilde is allowed to mean is real.
    # A size at the edge PASSES and one just past it REFUSES, so the tolerance
    # is a stated width rather than a synonym for "any number".
    band = max(1, round(module_lines * _MODULE_SIZE_TOLERANCE))
    at_edge = "#: a " + "~" + str(module_lines + band) + "-line module.\n"
    past_edge = "#: a " + "~" + str(module_lines + band + 1) + "-line module.\n"
    assert _quoted_number_errors(
        {"edge.py": at_edge}, collected=collected, module_lines=module_lines
    ) == []
    assert len(
        _quoted_number_errors(
            {"edge.py": past_edge}, collected=collected, module_lines=module_lines
        )
    ) == 1

    # --- PERMITTING CONTROL 2, the DISCRIMINATION control: the scan is bound
    # to these two claim SHAPES, not to integers at large. A guard that fired
    # on every number in the prose would be paid off by being weakened, and
    # these three carry numbers that are wrong for both classes.
    benign = (
        "#: the orchard " + "collects " + str(collected - 4) + " apples.\n"
        "#: a " + "~2," + "100-line docstring is not a module.\n"
        "#: 20s covers " + str(collected - 4) + " tests plus start-up.\n"
    )
    assert _quoted_number_errors(
        {"benign.py": benign}, collected=collected, module_lines=module_lines
    ) == []


# ==========================================================================
# 38 — a duplicate the READER collapses is a mismatch the packet never saw.
#      20s: eight observer subprocesses over throwaway run roots, plus
#      in-process reconcile() calls.
# ==========================================================================


def _run_root_with(work: Path, name: str, text: str) -> Path:
    """A run root of valid fixtures with ``name`` replaced by ``text``.

    ``_make_run_root``'s ``replace`` takes PATHS, and these payloads exist only
    as strings — a repeated JSON key cannot survive a round trip through a
    ``dict``, so it can never be written by ``json.dumps`` into a fixture file.
    """
    run_root = _make_run_root(work)
    (run_root / name).write_text(text, encoding="utf-8")
    return run_root


def _append_repeated_key(raw: str, side: str, path: str, value: Any) -> str:
    """Write ``path`` a SECOND time at the END of ``side``.entries, as TEXT.

    LAST, not first: ``json.loads`` keeps the last value for a repeated key, so
    a duplicate placed first is the one discarded and the payload would mask
    nothing. This is the shape a subject writes by hand; no serialiser in this
    repository can produce it.
    """
    start = raw.index(f'"{side}"')
    open_brace = raw.index("{", raw.index('"entries"', start))
    depth = 0
    close = -1
    for index in range(open_brace, len(raw)):
        if raw[index] == "{":
            depth += 1
        elif raw[index] == "}":
            depth -= 1
            if depth == 0:
                close = index
                break
    assert close > open_brace, f"no closing brace for {side}.entries"
    payload = f",\n      {json.dumps(path)}: {json.dumps(value)}\n    "
    duplicated = raw[:close] + payload + raw[close:]
    # CONTROL OF THE PAYLOAD: the bytes really do record the key twice, and a
    # plain parse really does keep only the last one. Without this the test
    # could be exercising a well-formed document and never know.
    assert duplicated.count(json.dumps(path) + ":") == raw.count(json.dumps(path) + ":") + 1
    assert json.loads(duplicated)[side]["entries"][path] == value
    return duplicated


@pytest.mark.timeout(20)
def test_a_duplicate_in_subject_evidence_cannot_collapse_upstream_of_a_decision(tmp_path):
    """A repeat the READER folds away is a discrepancy no decision ever met.

    THE CLASS THIS COVERS: subject-written evidence losing a record BEFORE the
    deciding code compares anything — the same shape as ``os.walk``'s discarded
    ``scandir`` errors, ``startswith("/")`` on a normalised root, and the debug
    receipt dropped by a too-narrow regex. Reached here through two doors:

    * ``json.loads`` keeps the LAST value for a repeated object key. ONE extra
      ``"<path>": {...}`` pair appended inside ``post.entries`` reinstated the
      superseded record, and D11 and D12 recomputed ``[]``.
    * A dict comprehension over a LIST keeps the last element for a repeated
      ``path``. ONE appended ``{"path": <same>, "sha256": <declared>}`` made
      D06 recompute ``[]``.

    Measured on the un-fixed bytes, each mutant going 1 discrepancy -> 0 with
    ``evidence_count`` unchanged, no truncation flag raised,
    ``evidence_malformed`` still ``False`` and no plane status degraded. The
    packet read fully clean, and the mutant registry — this freeze's own
    acceptance instrument — could not see it, because the kill harness feeds
    the unmodified mutant files.

    THE TWO DOORS NEED TWO GUARDS, and that is not a duplication: a JSON LIST
    cannot carry a repeated key, so no parse-time hook can reach the array
    case, and an observation handed to ``reconcile()`` in memory never passed a
    parser at all. So the key case is refused at the parse boundary through the
    EXISTING malformed channel, and the path case in the DECIDING code, which
    is the only place both call paths meet.
    """
    settings_raw = (FIXTURE_DIR / "mutants" / "M06-settings-digest-altered.json").read_text(
        encoding="utf-8"
    )
    fs_silent_raw = (
        FIXTURE_DIR / "mutants" / "M11-fs-inventory-silent-content-change.json"
    ).read_text(encoding="utf-8")
    fs_mode_raw = (
        FIXTURE_DIR / "mutants" / "M12-fs-inventory-mode-owner-drift.json"
    ).read_text(encoding="utf-8")

    # --- CONTROL OF THE PROBE: unmasked, each mutant turns its decision red.
    # A probe whose refusing arm was already green could not report a mask.
    for label, name, raw, decision_id in (
        ("m06", observer.EVIDENCE_SETTINGS, settings_raw, "D06_SETTINGS_DIGEST_MATCH"),
        ("m11", observer.EVIDENCE_FS_INVENTORY, fs_silent_raw, "D11_NO_SILENT_CONTENT_CHANGE"),
        ("m12", observer.EVIDENCE_FS_INVENTORY, fs_mode_raw, "D12_MODE_OWNER_RECORDED_FAITHFULLY"),
    ):
        packet = _packet_from(OBSERVER_PATH, _run_root_with(tmp_path / label, name, raw))
        assert _decision_of(packet, decision_id)["discrepancy_count"] == 1, decision_id

    # --- REFUSING ARM 1: the array door. One appended element whose digest
    # agrees with the observed side must not silence D06.
    settings_doc = json.loads(settings_raw)
    observed_digests = {item["path"]: item["sha256"] for item in settings_doc["observed"]}
    masked = copy.deepcopy(settings_doc)
    for item in list(settings_doc["declared"]):
        if observed_digests.get(item["path"], item["sha256"]) != item["sha256"]:
            masked["declared"].append(
                {"path": item["path"], "sha256": observed_digests[item["path"]]}
            )
    assert len(masked["declared"]) == len(settings_doc["declared"]) + 1, (
        "the M06 payload appended nothing, so this arm proves nothing"
    )
    packet = _packet_from(
        OBSERVER_PATH,
        _run_root_with(
            tmp_path / "m06_dup", observer.EVIDENCE_SETTINGS, json.dumps(masked, indent=2)
        ),
    )
    record = _decision_of(packet, "D06_SETTINGS_DIGEST_MATCH")
    assert record["discrepancy_count"] >= 1, (
        "one appended array element masked the settings digest mismatch"
    )
    assert any("more than once" in text for text in record["discrepancies"]), record

    # --- REFUSING ARM 2: the repeated-key door, on both filesystem decisions.
    # The masked value is the one the mutant SUPERSEDED, so last-wins restores
    # a clean record over bytes that still carry the drift.
    silent_doc = json.loads(fs_silent_raw)
    drifted = next(
        path
        for path, after in silent_doc["post"]["entries"].items()
        if path in silent_doc["pre"]["entries"] and silent_doc["pre"]["entries"][path] != after
    )
    mode_doc = json.loads(fs_mode_raw)
    unfaithful = next(
        path
        for path, entry in mode_doc["post"]["entries"].items()
        if entry.get("mode") != stat.S_IMODE(entry.get("mode", 0))
    )
    faithful = dict(mode_doc["post"]["entries"][unfaithful])
    faithful["mode"] = stat.S_IMODE(faithful["mode"])

    for label, raw, side, path, value, decision_id in (
        (
            "m11_dup", fs_silent_raw, "post", drifted,
            silent_doc["pre"]["entries"][drifted], "D11_NO_SILENT_CONTENT_CHANGE",
        ),
        (
            "m12_dup", fs_mode_raw, "post", unfaithful, faithful,
            "D12_MODE_OWNER_RECORDED_FAITHFULLY",
        ),
    ):
        packet = _packet_from(
            OBSERVER_PATH,
            _run_root_with(
                tmp_path / label,
                observer.EVIDENCE_FS_INVENTORY,
                _append_repeated_key(raw, side, path, value),
            ),
        )
        assert packet["observation"]["filesystem"]["evidence_malformed"] is True, (
            f"{decision_id}: a document recording a key twice read as well formed"
        )
        assert _decision_of(packet, decision_id)["observation_status"] == "ERROR", (
            f"{decision_id} read clean over evidence a repeated key had edited"
        )

    # --- NEGATIVE CONTROL, A DIFFERENT SHAPE: an ordinary document carrying no
    # duplicate at all is untouched. Without this, a guard that flagged every
    # document would satisfy every arm above and tell a reader nothing.
    clean = _packet_from(OBSERVER_PATH, _make_run_root(tmp_path / "clean"))
    assert clean["comparison"]["discrepancy_count"] == 0
    assert clean["comparison"]["observation_status"] == "OBSERVED"
    assert clean["observation"]["settings"]["evidence_malformed"] is False
    assert clean["observation"]["filesystem"]["evidence_malformed"] is False

    # --- NEGATIVE CONTROL 2, ALSO A DIFFERENT SHAPE: a duplicate whose value
    # AGREES with the original is still reported. "Harmless" is a judgement no
    # reader here is positioned to make: a subject that recorded the same
    # source twice is a fact about the evidence either way.
    agreeing = json.loads((VALID_DIR / observer.EVIDENCE_SETTINGS).read_text(encoding="utf-8"))
    agreeing["declared"].append(copy.deepcopy(agreeing["declared"][0]))
    packet = _packet_from(
        OBSERVER_PATH,
        _run_root_with(
            tmp_path / "agree", observer.EVIDENCE_SETTINGS, json.dumps(agreeing, indent=2)
        ),
    )
    assert any(
        "more than once" in text
        for text in _decision_of(packet, "D06_SETTINGS_DIGEST_MATCH")["discrepancies"]
    ), "a duplicate that agrees with the original was treated as no evidence at all"

    # --- THE REPRODUCTION, IN PROCESS, through reconcile() directly: the entry
    # point that never passes a parser, and so is reachable by no parse-time
    # hook. The third cell is the control that proves the probe still fires.
    path = "/proof/root/project.settings.json"

    def d06(extra: dict[str, str] | None) -> dict[str, Any]:
        plane = {
            "declared": [{"path": path, "sha256": "AAAA"}],
            "observed": [{"path": path, "sha256": "BBBB"}],
            "observation_status": "OBSERVED",
        }
        if extra is not None:
            plane["declared"].append(extra)
        return _decision_of(
            observer.reconcile({"settings": plane}), "D06_SETTINGS_DIGEST_MATCH"
        )

    assert d06(None)["discrepancy_count"] == 1
    assert d06({"path": path, "sha256": "BBBB"})["discrepancy_count"] >= 1
    assert d06({"path": path, "sha256": "CCCC"})["discrepancy_count"] >= 1


# ==========================================================================
# 39 — reconcile() reads an explicit null, a pathless entry and a boolean
#      the way every other reader in the module does. 5s: in-process only.
# ==========================================================================


@pytest.mark.timeout(5)
def test_reconcile_is_uniformly_fail_closed_on_null_pathless_and_boolean_records(tmp_path):
    """Three readers that trusted a shape the rest of the module does not.

    THE CLASS THIS COVERS: a reader whose guard fires on the value it was
    written against and not on the CATEGORY. Each was reproduced:

    * ``filesystem.get("pre", {})`` — a ``.get`` default fires only on an
      ABSENT key, so ``"pre": null`` reached ``.get("entries")`` on ``None``
      and raised ``AttributeError``. Every other reader here uses ``or {}``.
    * ``item["path"]`` — a settings entry recording no path raised
      ``KeyError``, so one malformed array element crashed the whole packet.
    * ``isinstance(mode, int)`` — ``bool`` is a subclass of ``int``,
      ``stat.S_IMODE(True) == 1 == True``, and D12 accepted ``"mode": true`` as
      a faithfully recorded permission set.

    A crash is not the same failure as a fail-open, but it is the same defect:
    the decision was never made, and a caller that catches broadly cannot tell
    the two apart.
    """
    # --- CONTROL OF THE CONTROL: why the old mode check passed. Written as an
    # assertion rather than prose, so it cannot go stale about the language.
    assert isinstance(True, int) and stat.S_IMODE(True) == 1 == True  # noqa: E712

    # --- REFUSING ARM 1: an explicit null plane decides, and does not crash.
    packet = observer.reconcile({"filesystem": {"pre": None, "post": None}})
    for decision_id in ("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS", "D11_NO_SILENT_CONTENT_CHANGE"):
        assert _decision_of(packet, decision_id)["observation_status"] != "OBSERVED", decision_id

    # --- REFUSING ARM 2: an entry with no usable path is NAMED, not dropped
    # and not raised over.
    packet = observer.reconcile(
        {"settings": {"declared": [{"sha256": "A"}, "not-a-dict"], "observed": []}}
    )
    named = _decision_of(packet, "D07_SETTINGS_SOURCE_SET_EXACT")["discrepancies"]
    assert [text for text in named if "records no usable path" in text], named

    # --- REFUSING ARM 3: a boolean is not a mode, and not an owner id either.
    def d12(entry: dict[str, Any]) -> dict[str, Any]:
        return _decision_of(
            observer.reconcile(
                {
                    "filesystem": {
                        "declared_writable_roots": ["/proof/root"],
                        "pre": {"entries": {"/proof/root/f": entry}},
                        "post": {"entries": {}},
                        "observation_status": "OBSERVED",
                    }
                }
            ),
            "D12_MODE_OWNER_RECORDED_FAITHFULLY",
        )

    faithful = {"mode": 0o600, "uid": 501, "acl_state": "UNMEASURED"}
    assert d12({**faithful, "mode": True})["discrepancy_count"] == 1
    assert d12({**faithful, "uid": True})["discrepancy_count"] == 1

    # --- NEGATIVE CONTROLS, EACH A DIFFERENT SHAPE FROM THE BUG ABOVE IT.
    # 1. A faithfully recorded entry stays clean, so the widened check did not
    #    become "every mode is wrong".
    assert d12(faithful)["discrepancies"] == []
    # 2. An ABSENT key, not an explicit null — the spelling the old default DID
    #    handle. If `or {}` had been the only thing tested, a fix that broke
    #    this would have passed.
    assert observer.reconcile({"filesystem": {}})["comparison"]["decisions"]
    # 3. A well-formed settings pair reports no pathless entry, so the naming
    #    is bound to the missing field and not emitted for every document.
    quiet = observer.reconcile(
        {"settings": {"declared": [{"path": "/a", "sha256": "x"}], "observed": []}}
    )
    assert not [
        text
        for text in _decision_of(quiet, "D07_SETTINGS_SOURCE_SET_EXACT")["discrepancies"]
        if "records no usable path" in text
    ]


# ==========================================================================
# 40 — the inventory walk descends in a stated order, so two identical trees
#      digest identically. 10s: in-process walks over small temp trees.
# ==========================================================================


@pytest.mark.timeout(10)
def test_inventory_descends_in_sorted_order_so_identical_trees_record_identically(tmp_path):
    """``sorted(dirnames)`` sorted a COPY, so the descent stayed scandir order.

    THE CLASS THIS COVERS: an ordering that LOOKS pinned at the call site and
    is decided somewhere else. Recording within one directory was sorted, but
    ``os.walk`` re-reads ``dirnames`` after the loop body to choose which
    subtree to enter next — and it was never mutated, so subtrees were visited
    in ``scandir`` order. ``entries`` is an insertion-ordered dict that
    ``inventory()`` publishes and later rungs digest as ``fs-inventory.json``,
    so two identical trees produced different bytes on different filesystems.

    MEASURED WITH A STAND-IN ``os.walk``, not with a real temp tree, and that
    is the load-bearing choice: a real tree's ``scandir`` order IS the
    filesystem-dependent thing under test, so a probe built on it would be
    green or red for reasons outside this module. The stand-in reproduces the
    ONE contract that matters — ``dirnames`` is re-read after the body — and is
    itself controlled below against a recorder that does not mutate.
    """
    root = tmp_path / "tree"
    root.mkdir()
    for name in ("zulu", "alpha", "mike"):
        (root / name).mkdir()
        (root / name / f"{name}.txt").write_text(name, encoding="utf-8")
    (root / "top.txt").write_text("top", encoding="utf-8")

    descended: list[list[str]] = []

    def reverse_walk(top, onerror=None, followlinks=False):
        """Yield subdirectories REVERSED, and honour in-place pruning.

        The single behaviour of ``os.walk`` this reproduces is that the
        caller's edit to ``dirnames`` decides the descent. Everything else
        about it is irrelevant to the claim.
        """
        queue = [str(top)]
        while queue:
            here = queue.pop(0)
            names = sorted(os.listdir(here), reverse=True)
            dirs = [n for n in names if os.path.isdir(os.path.join(here, n))]
            files = [n for n in names if not os.path.isdir(os.path.join(here, n))]
            yield here, dirs, files
            descended.append(list(dirs))
            queue = [os.path.join(here, name) for name in dirs] + queue

    # --- CONTROL OF THE INSTRUMENT: the stand-in really does hand out a
    # non-sorted order, and really does honour a mutation. A walk that
    # yielded sorted names would make the assertion below unfalsifiable.
    unpruned = [list(dirs) for _here, dirs, _files in reverse_walk(root)]
    assert unpruned[0] == ["zulu", "mike", "alpha"], unpruned
    pruning = []
    for _here, dirs, _files in reverse_walk(root):
        dirs[:] = sorted(dirs)
        pruning.append(list(dirs))
    assert pruning[0] == ["alpha", "mike", "zulu"], pruning
    assert [entry for entry in pruning if entry] == [["alpha", "mike", "zulu"]]

    # --- THE MEASUREMENT. Every directory the observer hands back must be
    # sorted, which is what makes the descent deterministic.
    descended.clear()
    real_walk = os.walk
    os.walk = reverse_walk  # noqa: SIM909 - restored in the finally below
    try:
        plane = observer.inventory(root)
    finally:
        os.walk = real_walk
    assert descended, "the stand-in walk was never called"
    assert all(names == sorted(names) for names in descended), descended

    # --- THE ORACLE, owned by this test: a pre-order walk whose expectation is
    # computed independently of the observer, over the same tree.
    recorded = [os.path.basename(path) for path in plane["entries"]]
    assert recorded == [
        os.path.basename(str(root)),
        "alpha", "mike", "zulu", "top.txt",
        "alpha.txt", "mike.txt", "zulu.txt",
    ], recorded


# ==========================================================================
# 41 — D05 reads a RECORDED PATH as data and an AUTHORED KEY as a field name.
#      5s: in-process reconcile() calls.
# ==========================================================================


@pytest.mark.timeout(5)
def test_d05_reads_a_recorded_path_as_data_and_an_authored_key_as_a_field_name():
    """A filename could DENY the observation D05 exists to protect.

    THE CLASS THIS COVERS: a probe applying a rule to a category the rule was
    not written for, where the operand is the SUBJECT's to choose.
    ``_VERDICT_KEY_TOKENS`` is a FIELD-NAME rule — it splits on ``_`` — and
    ``_verdict_leaks`` walked subject-forwarded inventory content with it, so
    an ordinary recorded file named ``build_pass_marker`` produced a D05
    discrepancy. The manifest's ``positive_arm`` requires ZERO discrepancies,
    so that filename denies it. The module rules, in
    ``observer._is_declarable_root``, that a candidate able to SUPPRESS a
    decision has steered it as surely as one able to satisfy it, and this was
    the same steering, unrecognised.

    THE FIX EXEMPTS A CATEGORY, NOT A LIST: a key that is an ABSOLUTE PATH is a
    recorded location, and no observer-authored field name is one. The value
    under such a key is still walked and every authored key beneath it is still
    tested, so a key wrongly exempted here yields noise, never silence.

    WHAT IS NOT FIXED, asserted below so it cannot be removed quietly and
    disclosed in the manifest's ``scope_limits``: the VALUE side. A
    subject-written ``"sha256": "pass"`` is still a discrepancy. Narrowing
    values WOULD narrow the question — an observer-authored verdict value is
    indistinguishable from a forwarded one without a corpus argument nobody
    here has, and the conservative reading wins.
    """
    def leaks(plane: dict[str, Any]) -> list[str]:
        return _decision_of(
            observer.reconcile(plane), "D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION"
        )["discrepancies"]

    def entry(**fields: Any) -> dict[str, Any]:
        return {"filesystem": {"pre": {"entries": fields}, "post": {"entries": {}}}}

    # --- PERMITTING ARM: an ordinary recorded file is data, not a verdict.
    assert [
        text for text in leaks(entry(**{"/proof/root/build_pass_marker": {"kind": "file"}}))
        if "verdict-vocabulary key" in text
    ] == []

    # --- REFUSING ARM 1, PROVING NO NARROWING: an observer-authored key at the
    # observation root still fires. This is the shape M05 injects.
    assert [
        text for text in leaks({"candidate_verdict": "irrelevant", "filesystem": {}})
        if "verdict-vocabulary key" in text
    ], "the authored-key rule stopped firing; D05 was narrowed, not corrected"

    # --- REFUSING ARM 2, A DIFFERENT SHAPE: the exemption is bound to being an
    # ABSOLUTE path, not to "contains a separator" and not to "looks like a
    # filename". A relative key still reads as a field name.
    assert [
        text for text in leaks(entry(**{"build_pass_marker": {"kind": "file"}}))
        if "verdict-vocabulary key" in text
    ], "a relative key was exempted; the rule is wider than absoluteness"

    # --- THE DISCLOSED LIMIT, MADE AN ASSERTION: the value side still fires.
    assert [
        text
        for text in leaks(entry(**{"/proof/root/f": {"sha256": "pass"}}))
        if "verdict-vocabulary value" in text
    ], "the value arm was silently removed along with the key arm"
    disclosure = [
        limit
        for limit in _case(_manifest(), "P0-C01")["scope_limits"]
        if limit.startswith("D05 ") and "The VALUE side is NOT fixed" in limit
    ]
    assert len(disclosure) == 1, "the residual is asserted in code and nowhere disclosed"

    # --- CONTROL OF THE CONTROL: the discriminator itself separates the two
    # categories, including for operands that are not strings at all.
    assert observer._is_recorded_location("/proof/root/build_pass_marker") is True
    assert observer._is_recorded_location("candidate_pass") is False
    assert observer._is_recorded_location("proof/root/build_pass_marker") is False
    assert observer._is_recorded_location(42) is False


# ==========================================================================
# 42 — no directory name in this file is derived from hash(). 5s: one AST
#      parse of the node file plus two synthetic sources.
# ==========================================================================


def _hash_derived_names(source: str) -> list[str]:
    """``line:col`` for every call to the BUILTIN ``hash``.

    The category, not the site: ``PYTHONHASHSEED`` randomises ``str`` hashes
    per process, so ANY name derived from ``hash()`` is a different name on
    every run. Matched on the AST so that the word appearing in prose, in a
    string, or as ``hashlib.sha256`` is not confused for the builtin.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "hash":
                found.append(f"{node.lineno}:{node.col_offset}")
    return found


@pytest.mark.timeout(5)
def test_no_directory_name_in_this_file_is_derived_from_hash():
    """These bytes carried a rule and its violation at the same time.

    ``packet_for`` documents that a run root is named EXPLICITLY and never from
    ``hash()``, because ``PYTHONHASHSEED`` randomises ``str`` hashes per process
    and ``_make_run_root`` uses ``exist_ok=True``, so a collision silently
    reuses a populated root. A helper 4,900 lines earlier did exactly that.

    A rule written in a docstring binds nothing. This is the same rule with a
    reader, which is the only difference that matters.
    """
    # --- THE MEASUREMENT, against the bytes that execute.
    assert _hash_derived_names(NODE_FILE.read_text(encoding="utf-8")) == []

    # --- REFUSING ARM: the exact shape these bytes carried. Assembled at
    # runtime so the scan above does not read this test's own reproducer.
    offending = (
        "def cli(sources):\n"
        "    return _make_run_root(tmp_path / f'cli_{abs(" + "hash" + "(sources))}')\n"
    )
    assert len(_hash_derived_names(offending)) == 1, offending

    # --- PERMITTING ARM, TWO DIFFERENT SHAPES. A scan bound to the substring
    # would refuse both, and a scan that refused nothing would pass the arm
    # above only by accident.
    permitted = (
        "import hashlib\n"
        "def cli(label):\n"
        "    # never derived from hash(): PYTHONHASHSEED randomises it\n"
        "    digest = hashlib.sha256(label.encode()).hexdigest()\n"
        "    return _make_run_root(tmp_path / f'cli_{label}_{digest[:8]}')\n"
    )
    assert _hash_derived_names(permitted) == []


# ==========================================================================
# 43 — THE CLASS: a reader that DECLINES a subject-authored record must
#      account for it. Six sites did not. 5s: in-process reads over tmp files.
# ==========================================================================
#
# Every evidence document here already carries a malformed channel
# (`unparsable_records`, `evidence_malformed`) and a named-discrepancy channel.
# A record that PARSES and is then dropped by a type test, or COERCED by one,
# reaches neither — so strictly less evidence, or wrongly-typed evidence, reads
# strictly cleaner than the violation it conceals. Sections 43 to 46 drive the
# six sites; section 47 refuses a new one statically and section 48 refuses one
# behaviourally, because neither instrument alone covers the category.


@pytest.mark.timeout(5)
def test_a_line_that_yields_no_record_and_a_file_that_yields_no_bytes_both_degrade(
    tmp_path,
):
    """Two doors out of the bounded-evidence reader, both of which read clean.

    * ``_read_jsonl`` kept ``if isinstance(parsed, dict): records.append(...)``.
      A line decoding to a JSON ARRAY was dropped and counted NOWHERE: seven
      lines in, ``record_count=6``, ``unparsable_records=0``,
      ``observation_status=OBSERVED`` — byte-identical to a file that only ever
      had six lines.
    * ``_bounded_evidence`` branched on ``path.is_file()`` alone.
      ``_sha256_file`` returns ``(None, None, False)`` on ANY ``OSError`` and
      ``_read_text`` returns ``None`` with no flag, so an UNREADABLE file
      reported ``present: true``/``sha256: null``/OBSERVED while the SAME file
      merely ABSENT reported UNMEASURED. Less evidence, cleaner answer —
      against ``amendment:208``.
    """
    records = [json.dumps({"type": "tool_use", "tool_use_id": f"t{i}"}) for i in range(6)]

    def evidence(text: str, counter) -> dict[str, Any]:
        path = tmp_path / f"s{abs(len(text))}_{counter.__name__}.jsonl"
        path.write_text(text, encoding="utf-8")
        return observer._bounded_evidence(path, counter)

    # --- PERMITTING ARM: six well-formed records stay clean, so nothing below
    # is satisfied by a reader that degrades every file it touches.
    clean = evidence("\n".join(records) + "\n", observer._count_jsonl)
    assert (clean["record_count"], clean["unparsable_records"]) == (6, 0)
    assert clean["observation_status"] == "OBSERVED"

    # --- REFUSING ARM 1, the reproducer's shape: a seventh line that PARSES
    # and is not a record.
    smuggled = evidence(
        "\n".join(records) + "\n" + json.dumps(["smuggled"]) + "\n", observer._count_jsonl
    )
    assert smuggled["unparsable_records"] == 1, smuggled
    assert smuggled["observation_status"] == "ERROR", smuggled

    # --- REFUSING ARM 2, a DIFFERENT shape at the same door: a line that does
    # not decode at all. Both reach the same channel, because both leave the
    # reader holding no record.
    broken = evidence("\n".join(records) + "\n{not json\n", observer._count_jsonl)
    assert (broken["unparsable_records"], broken["observation_status"]) == (1, "ERROR")

    # --- REFUSING ARM 3, a DIFFERENT DOOR ENTIRELY and a different failure
    # mode: the file is present and no reader can open it. Driven for every
    # counter the module ships, since the defect was in the shared reader.
    for name, counter in (
        ("transcript.jsonl", observer._count_jsonl),
        ("debug.log", observer._count_lines),
        ("stream.jsonl", observer._count_jsonl),
    ):
        present = tmp_path / f"unreadable_{name}"
        present.write_text(records[0] + "\n", encoding="utf-8")
        os.chmod(present, 0o000)
        try:
            unreadable = observer._bounded_evidence(present, counter)
        finally:
            os.chmod(present, 0o600)
        absent = observer._bounded_evidence(tmp_path / f"absent_{name}", counter)
        assert unreadable["present"] is True and unreadable["sha256"] is None, name
        assert unreadable["observation_status"] == "ERROR", (name, unreadable)
        assert absent["observation_status"] == "UNMEASURED", (name, absent)
        # THE ORDERING IS THE POINT, not the two labels: unreadable must never
        # rank cleaner than absent.
        assert observer._worst([unreadable["observation_status"]]) == "ERROR", name
        assert (
            observer._worst([unreadable["observation_status"], absent["observation_status"]])
            == unreadable["observation_status"]
        ), name

    # --- NEGATIVE CONTROL, A DIFFERENT SHAPE FROM EVERY ARM ABOVE: an EMPTY
    # file is readable, digests to the digest of no bytes, and stays clean. A
    # fix that keyed on "no records" rather than "no bytes readable" would fail
    # here, and a fix that keyed on a falsy digest would too.
    empty = tmp_path / "empty.jsonl"
    empty.write_bytes(b"")
    read_empty = observer._bounded_evidence(empty, observer._count_jsonl)
    assert read_empty["sha256"] == hashlib.sha256(b"").hexdigest()
    assert read_empty["observation_status"] == "OBSERVED", read_empty


# ==========================================================================
# 44 — a hook event cannot leave the lifecycle join by RETYPING its identity.
#      5s: in-process reads over tmp files.
# ==========================================================================


@pytest.mark.timeout(5)
def test_a_hook_event_cannot_escape_d09_by_retyping_its_tool_use_id(tmp_path):
    """The ghost that changed its id's TYPE and vanished from the packet.

    ``_hook_lifecycle`` filtered on ``isinstance(tool_use_id, str)`` at two
    sites — a ``continue`` in the record loop and again in the ``hook_event``
    set comprehension. Measured on the pre-fix bytes: a stream ``hook_event``
    with ``tool_use_id`` ``"toolu_GHOST"`` produced a D09 discrepancy naming a
    hook with no receipt, and the SAME record with ``tool_use_id`` ``9999``
    produced none at all. The evidence did not become wrong; it stopped
    existing, upstream of the decision, where no bound and no flag could see it.
    """

    def d09(ghost_id: Any) -> dict[str, Any]:
        root = tmp_path / f"run_{type(ghost_id).__name__}_{str(ghost_id)[:12]}"
        root.mkdir(parents=True, exist_ok=True)
        # EVERY hook event names its event, INCLUDING THE GHOST, and that is
        # what keeps this node about the identity. The receipt join is keyed on
        # `(tool_use_id, hook_event_name)`, so a record omitting the name is
        # receiptless for a second, unrelated reason — the permitting arm below
        # would fail for a cause this test is not about, and the ghost would be
        # named whatever its id. With the name supplied on both, the only thing
        # separating `toolu_OK` from the ghost is the id, which is the
        # discrimination under test.
        lines = [
            {"type": "tool_use", "tool_use_id": "toolu_OK"},
            {
                "type": "hook_event",
                "tool_use_id": "toolu_OK",
                "hook_event_name": "PreToolUse",
            },
        ]
        if ghost_id is not ...:
            lines.append(
                {
                    "type": "hook_event",
                    "tool_use_id": ghost_id,
                    "hook_event_name": "PreToolUse",
                }
            )
        (root / observer.EVIDENCE_STREAM).write_text(
            "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
        )
        debug = root / "debug.log"
        debug.write_text(
            "[DEBUG] hook PreToolUse tool_use_id=toolu_OK command=guard "
            "exit=0 stdout_bytes=0\n",
            encoding="utf-8",
        )
        plane = observer._hook_lifecycle(root, debug)
        packet = observer.reconcile(
            {
                "hooks": plane,
                "stream": observer._bounded_evidence(
                    root / observer.EVIDENCE_STREAM, observer._count_jsonl
                ),
                "debug": observer._bounded_evidence(debug, observer._count_lines),
            }
        )
        return _decision_of(packet, "D09_HIDDEN_HOOK_NONZERO")

    # --- PERMITTING ARM: with no ghost at all, the receipt covers the single
    # hook event and D09 names nothing. Without this the arms below could be
    # satisfied by a decision that always reports a discrepancy.
    assert d09(...)["discrepancies"] == []

    # --- THE REPRODUCER, both spellings. The string id was already named; the
    # integer id is what used to disappear. Both must now be named, and the
    # discrepancy must CARRY the identity so the two are distinguishable.
    as_string = d09("toolu_GHOST")
    as_integer = d09(9999)
    assert len(as_string["discrepancies"]) == 1, as_string
    assert len(as_integer["discrepancies"]) == 1, as_integer
    assert "toolu_GHOST" in as_string["discrepancies"][0]
    assert "9999" in as_integer["discrepancies"][0], as_integer

    # --- REFUSING ARM 2, a DIFFERENT TYPE and a different shape from the
    # integer: a container. The rendering must stay INJECTIVE, or two distinct
    # ghosts would collapse into one identity the way two digests once did.
    as_list = d09(["toolu_GHOST"])
    as_dict = d09({"id": "toolu_GHOST"})
    assert len(as_list["discrepancies"]) == 1 and len(as_dict["discrepancies"]) == 1
    assert as_list["discrepancies"] != as_integer["discrepancies"]
    assert as_list["discrepancies"] != as_dict["discrepancies"]

    # --- NEGATIVE CONTROL, A DIFFERENT SHAPE FROM THE BUG: a stream record
    # that is not a lifecycle record at all carries no identity and must not be
    # named. The membership test is on the RECORD TYPE, so widening it to "any
    # record with a non-string id" would fail here.
    root = tmp_path / "run_nonlifecycle"
    root.mkdir()
    (root / observer.EVIDENCE_STREAM).write_text(
        json.dumps({"type": "system", "subtype": "init"}) + "\n"
        + json.dumps({"type": "tool_use", "tool_use_id": "toolu_OK"}) + "\n"
        + json.dumps(
            {
                "type": "hook_event",
                "tool_use_id": "toolu_OK",
                "hook_event_name": "PreToolUse",
            }
        ) + "\n",
        encoding="utf-8",
    )
    debug = root / "debug.log"
    debug.write_text(
        "[DEBUG] hook PreToolUse tool_use_id=toolu_OK command=guard "
        "exit=0 stdout_bytes=0\n",
        encoding="utf-8",
    )
    quiet = observer._hook_lifecycle(root, debug)
    assert quiet["hook_events_without_receipt"] == [], quiet
    assert quiet["orphan_tool_use_ids"] == [], quiet
    assert quiet["observation_status"] == "OBSERVED", quiet

    # --- THE FORGERY CONTROL: a rendered identity contains spaces and
    # `_DEBUG_HOOK_RE` captures `\S+`, so no debug receipt can be written that
    # pairs itself with one. Measured against the shipped regex rather than
    # asserted in prose.
    rendered = observer._recorded_as_text("tool_use_id", 9999)
    assert " " in rendered
    forged = (
        f"[DEBUG] hook PreToolUse tool_use_id={rendered} command=guard "
        "exit=0 stdout_bytes=0\n"
    )
    match = observer._DEBUG_HOOK_RE.search(forged)
    assert match is None or match.group("tool_use_id") != rendered, forged


# ==========================================================================
# 45 — the settings readers give ONE answer, through BOTH doors. 10s: one
#      observer subprocess per case.
# ==========================================================================


@pytest.mark.timeout(10)
def test_the_settings_readers_answer_identically_through_capture_and_reconcile(tmp_path):
    """The guard that named these entries could not be reached from production.

    ``_settings_provenance`` normalised the subject's provenance lists before
    ``reconcile`` ever saw them: it DROPPED every entry that was not a dict with
    a string ``path``, and COERCED a non-string ``sha256`` to ``None``. So
    ``_settings_by_path`` — added to NAME exactly those entries — was
    unreachable from ``capture()``, and section 39 was green only because it
    enters through ``reconcile()`` with an in-memory plane. The route the smoke
    command runs is the route that matters, so this drives the observer CLI
    over real bytes.

    The coercion was the worse half. Two DISTINCT non-string digests both
    became ``None``, ``None != None`` is False, and the mismatch disappeared
    from a packet that stayed schema-valid — so the external ``jsonschema``
    oracle could not see the laundering either, which is what falsified the
    manifest's ``non_self_certification.achieved[1]``.
    """

    canonical = _canonical_setting_sources()

    def both_doors(document: dict[str, Any], label: str) -> tuple[list[str], list[str]]:
        """D06+D07 discrepancies via the production route, and via reconcile()."""
        run_root = _make_run_root(tmp_path / f"settings_{label}")
        # D07'S SOURCE-SET HALF IS HELD AT ITS CANONICAL VALUE ON BOTH DOORS,
        # so every discrepancy compared below comes from the ENTRY-LIST readers
        # this test exists to drive. Left out, the source arm fires in every
        # cell and a constant masks the parity question.
        (run_root / observer.EVIDENCE_SETTINGS).write_text(
            json.dumps({"setting_sources": canonical, **document}), encoding="utf-8"
        )
        produced = _packet_from(OBSERVER_PATH, run_root)
        # The OTHER door: the same recorded lists handed straight to
        # reconcile() as an in-memory plane.
        in_memory = observer.reconcile(
            {
                "settings": {
                    "declared": document.get("declared"),
                    "observed": document.get("observed"),
                    "setting_sources": canonical,
                    "expected_setting_sources": canonical,
                    "observation_status": "OBSERVED",
                }
            }
        )

        def named(packet: dict[str, Any]) -> list[str]:
            return sorted(
                text
                for decision_id in ("D06_SETTINGS_DIGEST_MATCH", "D07_SETTINGS_SOURCE_SET_EXACT")
                for text in _decision_of(packet, decision_id)["discrepancies"]
            )

        return named(produced), named(in_memory)

    def entry(path: str, digest: Any) -> dict[str, Any]:
        return {"path": path, "sha256": digest}

    hex_a = "a" * 64
    hex_b = "b" * 64

    # --- PERMITTING ARM: agreeing string digests name nothing, through either
    # door. A guard whose refusing arms all fired would pass them vacuously.
    clean_prod, clean_mem = both_doors(
        {"declared": [entry("/s/u.json", hex_a)], "observed": [entry("/s/u.json", hex_a)]},
        "clean",
    )
    assert clean_prod == [] and clean_mem == [], (clean_prod, clean_mem)

    # --- POSITIVE CONTROL: two DIFFERENT string digests are a mismatch, and
    # were always named. This is the baseline the masked cases must now match.
    mismatch_prod, mismatch_mem = both_doors(
        {"declared": [entry("/s/u.json", hex_a)], "observed": [entry("/s/u.json", hex_b)]},
        "mismatch",
    )
    assert [t for t in mismatch_prod if "digest mismatch" in t], mismatch_prod
    assert mismatch_prod == mismatch_mem

    # --- THE REPRODUCER: two DISTINCT non-string digests. Before the fix both
    # became null, compared equal, and produced zero discrepancies.
    masked_prod, masked_mem = both_doors(
        {"declared": [entry("/s/u.json", [hex_a])], "observed": [entry("/s/u.json", [hex_b])]},
        "listdigest",
    )
    assert [t for t in masked_prod if "digest mismatch" in t], masked_prod
    assert [t for t in masked_prod if "non-string sha256" in t], masked_prod
    assert masked_prod == masked_mem, (masked_prod, masked_mem)

    # --- REFUSING ARM, A DIFFERENT TYPE: integers, which a list-shaped fix
    # would not cover.
    ints_prod, ints_mem = both_doors(
        {"declared": [entry("/s/u.json", 111)], "observed": [entry("/s/u.json", 222)]},
        "intdigest",
    )
    assert [t for t in ints_prod if "digest mismatch" in t], ints_prod
    assert ints_prod == ints_mem
    # The two masked cases must stay DISTINGUISHABLE from each other, which is
    # the property the coercion to null destroyed.
    assert ints_prod != masked_prod

    # --- REFUSING ARM, THE DROP rather than the coercion: entries the previous
    # normaliser removed entirely, so `_settings_by_path` never ran on the
    # production route.
    dropped_prod, dropped_mem = both_doors(
        {
            "declared": [entry("/s/u.json", hex_a), "BARE STRING", {"path": 7}],
            "observed": [entry("/s/u.json", hex_a)],
        },
        "dropped",
    )
    # Two unusable entries, each named on BOTH decisions that index by path —
    # `collapsed` is reported on D06 and D07 alike because both decide over
    # whatever the indexing lost.
    assert len([t for t in dropped_prod if "records no usable path" in t]) == 4, dropped_prod
    assert dropped_prod == dropped_mem

    # --- AND THE STATUS, NOT ONLY THE NAME. Every assertion above reads the
    # DISCREPANCY channel, and a loss can be named there while the decision
    # still reports OBSERVED. D06 and D07 were the only two decisions in
    # `reconcile` handing their plane's status through RAW: D01-D04, D08/D09
    # and D10-D12 all pass it through `_degraded`, which forces ERROR when a
    # read was defeated. A chokepoint with two exceptions is a convention, so
    # the exceptions are checked here rather than assumed away.
    def settings_statuses(document: dict[str, Any], label: str) -> dict[str, str]:
        run_root = _make_run_root(tmp_path / f"status_{label}")
        (run_root / observer.EVIDENCE_SETTINGS).write_text(
            json.dumps(document), encoding="utf-8"
        )
        packet = _packet_from(OBSERVER_PATH, run_root)
        return {
            decision_id: _decision_of(packet, decision_id)["observation_status"]
            for decision_id in ("D06_SETTINGS_DIGEST_MATCH", "D07_SETTINGS_SOURCE_SET_EXACT")
        }

    # PERMITTING ARM: a clean pair leaves both decisions OBSERVED, so the ERROR
    # below is caused by the defeated read and not by the fixture.
    clean_status = settings_statuses(
        {"declared": [entry("/s/u.json", hex_a)], "observed": [entry("/s/u.json", hex_a)]},
        "clean",
    )
    assert set(clean_status.values()) == {"OBSERVED"}, clean_status

    # PERMITTING CONTROL, A DIFFERENT SHAPE: an honest DIGEST MISMATCH is a
    # finding about the subject, not a defeated read. It must be NAMED and stay
    # OBSERVED — a fix that degraded on every discrepancy would pass the
    # refusing arm below and destroy the distinction the status channel exists
    # to carry.
    mismatch_status = settings_statuses(
        {"declared": [entry("/s/u.json", hex_a)], "observed": [entry("/s/u.json", hex_b)]},
        "mismatch",
    )
    assert set(mismatch_status.values()) == {"OBSERVED"}, mismatch_status

    # REFUSING ARM: an entry `_settings_by_path` could not index. Both
    # decisions read that index, so both must degrade — reporting on the one
    # whose masking was reproduced first is the same half-fix one level up.
    defeated = settings_statuses(
        {"declared": [entry("/s/u.json", hex_a), {"path": 7}], "observed": [entry("/s/u.json", hex_a)]},
        "defeated",
    )
    assert set(defeated.values()) == {"ERROR"}, defeated

    # REFUSING ARM, A DIFFERENT SHAPE AND A DIFFERENT SIDE: the loss on the
    # OBSERVED list rather than the declared one, carried by a bare string
    # rather than a dict with an unusable path.
    other_side = settings_statuses(
        {"declared": [entry("/s/u.json", hex_a)], "observed": [entry("/s/u.json", hex_a), "BARE"]},
        "otherside",
    )
    assert set(other_side.values()) == {"ERROR"}, other_side

    # --- REFUSING ARM, A DIFFERENT SHAPE AGAIN: the whole list recorded as
    # something that is not a list. Narrowing it to `[]` compares clean.
    notalist_prod, notalist_mem = both_doors(
        {"declared": {"path": "/s/u.json"}, "observed": [entry("/s/u.json", hex_a)]},
        "notalist",
    )
    assert [t for t in notalist_prod if "is not a list of entries" in t], notalist_prod
    assert notalist_prod == notalist_mem

    # --- NEGATIVE CONTROL, A DIFFERENT SHAPE FROM EVERY ARM: an ABSENT key
    # records nothing and declines nothing, so it must NOT be named. A fix that
    # treated "not a list" as covering "absent" would report a discrepancy for
    # every observation that omits the field.
    absent_prod, absent_mem = both_doors({"observed": []}, "absent")
    assert [t for t in absent_prod if "is not a list of entries" in t] == [], absent_prod
    assert absent_mem == absent_prod

    # --- THE PACKET REMAINS RECOMPUTABLE, which is the claim the coercion
    # falsified: the two masked cases produce DIFFERENT bytes, and the raw
    # value the subject wrote survives into the emitted observation.
    run_root = _make_run_root(tmp_path / "settings_recompute")
    (run_root / observer.EVIDENCE_SETTINGS).write_text(
        json.dumps(
            {"declared": [entry("/s/u.json", [hex_a])], "observed": [entry("/s/u.json", [hex_b])]}
        ),
        encoding="utf-8",
    )
    packet = _packet_from(OBSERVER_PATH, run_root)
    assert packet["observation"]["settings"]["declared"] == [entry("/s/u.json", [hex_a])]
    assert packet["observation"]["settings"]["observed"] == [entry("/s/u.json", [hex_b])]


# ==========================================================================
# 46 — an inventory entry a decision cannot READ is named, not dropped.
#      5s: in-process reconcile over in-memory planes.
# ==========================================================================


@pytest.mark.timeout(5)
def test_an_unreadable_inventory_entry_is_named_and_never_shrinks_the_denominator():
    """Two filesystem readers whose type tests removed the evidence.

    * ``_private_root_entries`` collected only ``isinstance(entry, dict)``
      members. A private-root entry recorded as a SCALAR left the list
      entirely: D12 reported ``evidence_count`` 1 instead of 2 with zero
      discrepancies, byte-identical to a run holding one clean entry.
    * D11 read ``pre_entries[path] if isinstance(..., dict) else {}`` on BOTH
      sides. Two non-dict entries both became ``{}``, ``{} == {}`` compared
      equal, and a content change outside every declared root read clean.
    """

    def plane(pre: dict[str, Any], post: dict[str, Any], roots=("/private",)) -> dict[str, Any]:
        def side(entries: dict[str, Any]) -> dict[str, Any]:
            return {
                "root": "/private",
                "root_exists": True,
                "entries": entries,
                "entry_count": len(entries),
                "entry_truncated": False,
                "member_bytes_truncated": False,
                "observation_status": "OBSERVED",
            }

        return {
            "declared_writable_roots": list(roots),
            "legacy_absolute_paths": [],
            "pre": side(pre),
            "post": side(post),
            "any_bound_truncated": False,
            "evidence_malformed": False,
            "observation_status": "OBSERVED",
        }

    def decide(decision_id: str, pre: dict[str, Any], post: dict[str, Any], **kw) -> dict[str, Any]:
        return _decision_of(observer.reconcile({"filesystem": plane(pre, post, **kw)}), decision_id)

    # A COMPLETE record: the mode/uid/acl triple is D12's subject, and the other
    # four fields are present so this probe measures D12 alone rather than also
    # tripping the forwarded-entry domain reader.
    faithful = _path_entry()

    # --- PERMITTING ARM: one faithfully recorded private-root entry, clean,
    # denominator 1. Every count below is read against this.
    clean = decide("D12_MODE_OWNER_RECORDED_FAITHFULLY", {}, {"/private/ok": dict(faithful)})
    assert (clean["discrepancy_count"], clean["evidence_count"]) == (0, 1), clean

    # --- POSITIVE CONTROL: an entry that IS a dict but records a bad mode was
    # always named, and grew the denominator to 2.
    bad_mode = decide(
        "D12_MODE_OWNER_RECORDED_FAITHFULLY",
        {},
        {"/private/ok": dict(faithful), "/private/b": {**faithful, "mode": True}},
    )
    assert (bad_mode["discrepancy_count"], bad_mode["evidence_count"]) == (1, 2), bad_mode

    # --- THE REPRODUCER: a scalar entry used to be byte-identical to `clean`.
    scalar = decide(
        "D12_MODE_OWNER_RECORDED_FAITHFULLY",
        {},
        {"/private/ok": dict(faithful), "/private/d": "rw-------"},
    )
    assert (scalar["discrepancy_count"], scalar["evidence_count"]) == (1, 2), scalar
    assert scalar != clean
    assert [t for t in scalar["discrepancies"] if "/private/d" in t], scalar

    # --- REFUSING ARM 2, a DIFFERENT SHAPE: the whole `entries` map recorded
    # as a list, which no per-entry test would reach.
    listed = _decision_of(
        observer.reconcile(
            {
                "filesystem": {
                    "declared_writable_roots": ["/private"],
                    "pre": {"entries": {}},
                    "post": {"entries": ["/private/ok"]},
                    "observation_status": "OBSERVED",
                }
            }
        ),
        "D12_MODE_OWNER_RECORDED_FAITHFULLY",
    )
    assert [t for t in listed["discrepancies"] if "not a path map" in t], listed

    # --- THE D11 ANALOGUE: a content change on a path OUTSIDE every declared
    # root, recorded on both sides as a scalar. Both coerced to `{}`; `{} == {}`.
    d11_clean = decide(
        "D11_NO_SILENT_CONTENT_CHANGE",
        {"/outside/f": _path_entry(sha256="a" * 64)},
        {"/outside/f": _path_entry(sha256="a" * 64)},
    )
    d11_changed = decide(
        "D11_NO_SILENT_CONTENT_CHANGE",
        {"/outside/f": _path_entry(sha256="a" * 64)},
        {"/outside/f": _path_entry(sha256="b" * 64)},
    )
    d11_scalar = decide("D11_NO_SILENT_CONTENT_CHANGE", {"/outside/f": "A"}, {"/outside/f": "B"})
    assert d11_clean["discrepancy_count"] == 0, d11_clean
    assert d11_changed["discrepancy_count"] == 1, d11_changed
    # THREE findings, and each is true: D11's own "no content comparison is
    # possible", plus one per side from the forwarded-entry domain reader
    # naming a scalar as not the object `$defs/path_entry` declares. The digests
    # above are LOWERCASE hex because `$defs/sha256` says so — an upper-case
    # "A"*64 is itself out of domain, so the pair would have been measuring the
    # domain reader rather than the digest comparison it is aimed at.
    assert d11_scalar["discrepancy_count"] == 3, d11_scalar
    assert [t for t in d11_scalar["discrepancies"] if "no content comparison" in t], d11_scalar

    # --- NEGATIVE CONTROL, A DIFFERENT SHAPE FROM THE BUG: a scalar entry
    # INSIDE a declared writable root is not a D11 finding, because writes
    # there are declared. A fix that named every non-dict entry everywhere
    # would fail here, and that is the over-broad direction.
    inside = decide("D11_NO_SILENT_CONTENT_CHANGE", {"/private/f": "A"}, {"/private/f": "B"})
    assert not [t for t in inside["discrepancies"] if "content changed" in t], inside
    # THE PROPERTY IS STATED ON THE MESSAGE, NOT ON THE COUNT, and that is a
    # sharpening rather than a relaxation. D11's question — did content change
    # outside every declared root — still answers "no" here, which is what this
    # control has always been about. The COUNT is no longer zero because a
    # DIFFERENT reader with a DIFFERENT question now speaks: a scalar is not the
    # object `$defs/path_entry` declares, wherever it sits, and that is packet
    # well-formedness, not D11's subject. Left as a count, this control would
    # have read "the over-broad direction returned"; on the message it says
    # exactly what it means.
    assert [t for t in inside["discrepancies"]
            if "not the object $defs/path_entry declares" in t], inside


# ==========================================================================
# 47 — THE STATIC RATCHET: a type test may not silently exclude a record.
#      5s: one AST parse of the observer.
# ==========================================================================
#
# TRACTABILITY, STATED PLAINLY. "Does this exclusion feed an accounting
# channel" is not decidable in general — the accounting can be an append, a
# counter, a status assignment, or a value returned three frames up. What IS
# decidable is the family of gating shapes in which accounting is
# STRUCTURALLY IMPOSSIBLE, and every one of the six reproduced sites was a
# member of it. That is the rule below; it is a ratchet over shapes present on
# these bytes, not a claim that no other shape exists. Section 48 is the
# behavioural instrument that does not depend on shape at all, and the two are
# shipped together because neither covers the category alone.

#: Type operands that make an ``isinstance`` call a PYTHON-TYPE test over data,
#: as opposed to a node-kind dispatch over the module's own ``ast`` trees.
#: Derived by NAME rather than by function, so the AST-walking helpers are
#: excluded because of what they test, not because they are on a list.
_DATA_TYPE_NAMES = frozenset(
    {"dict", "list", "str", "int", "bool", "float", "tuple", "set", "bytes"}
)


def _is_data_type_test(node: ast.AST) -> bool:
    """True when ``node`` contains ``isinstance(x, <builtin data type>)``."""
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)):
            continue
        if sub.func.id != "isinstance" or len(sub.args) != 2:
            continue
        operand = sub.args[1]
        candidates = operand.elts if isinstance(operand, ast.Tuple) else [operand]
        if candidates and all(
            isinstance(item, ast.Name) and item.id in _DATA_TYPE_NAMES for item in candidates
        ):
            return True
    return False


def _is_empty_value(node: ast.AST) -> bool:
    """True for the literals a silent narrowing collapses to."""
    if isinstance(node, ast.Constant):
        return node.value is None or node.value == 0 or node.value == "" or node.value is False
    if isinstance(node, ast.Dict):
        return not node.keys
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return not node.elts
    return False


def _silent_exclusions(source: str) -> list[str]:
    """``<shape> at line N`` for every gating shape that cannot account.

    Three shapes, each one in which there is nowhere to record the exclusion:

    * ``bare-continue`` — an ``if`` on a data-type test whose entire body is
      ``continue``. The record leaves the loop and no statement observed it.
    * ``comprehension-filter`` — a data-type test in a comprehension ``if``.
      A comprehension has no statement position at all.
    * ``ternary-to-empty`` — a data-type test in an ``IfExp`` whose ``orelse``
      is an empty literal. The value is replaced by nothing, inside an
      expression, with no slot to name what was replaced.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.If) and _is_data_type_test(node.test):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Continue):
                found.append(f"bare-continue at line {node.lineno}")
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for generator in node.generators:
                for condition in generator.ifs:
                    if _is_data_type_test(condition):
                        found.append(f"comprehension-filter at line {node.lineno}")
        if isinstance(node, ast.IfExp) and _is_data_type_test(node.test):
            if _is_empty_value(node.orelse):
                found.append(f"ternary-to-empty at line {node.lineno}")
    return sorted(found)


@pytest.mark.timeout(5)
def test_no_type_test_in_the_observer_excludes_a_record_where_nothing_can_record_it():
    """The ratchet: a new silent exclusion cannot be added without refusal.

    Six sites of one shape were found in one cycle, after four fixes of the
    same shape in the same rung. Patching the sixth is not a fix for a category
    — this is, for the part of the category a static rule can reach.
    """
    # --- THE MEASUREMENT, against the bytes that execute.
    assert _silent_exclusions(OBSERVER_PATH.read_text(encoding="utf-8")) == []

    # --- INSTRUMENT CONTROL: the scan is not inert. Each shipped shape is
    # reproduced here and must be found, at the right line, by name. Built at
    # runtime so this file's own bytes are not what the scan above reads.
    reproducers = {
        "bare-continue": (
            "def read(records):\n"
            "    for item in records:\n"
            "        if not " + "isinstance" + "(item, dict):\n"
            "            continue\n"
            "        yield item\n"
        ),
        "comprehension-filter": (
            "def ids(records):\n"
            "    return {r['id'] for r in records if " + "isinstance" + "(r.get('id'), str)}\n"
        ),
        "ternary-to-empty": (
            "def norm(raw):\n"
            "    return raw if " + "isinstance" + "(raw, dict) else {}\n"
        ),
    }
    for shape, text in reproducers.items():
        found = _silent_exclusions(text)
        assert len(found) == 1, (shape, found)
        assert found[0].startswith(shape), (shape, found)

    # --- PERMITTING ARM 1, THE ACCOUNTED FORM of the same exclusion: the
    # record is still declined, but a statement records it. This is what the
    # observer ships, and a scan that refused it would be paid off by being
    # deleted.
    accounted = (
        "def read(records, problems):\n"
        "    for position, item in enumerate(records):\n"
        "        if not " + "isinstance" + "(item, dict):\n"
        "            problems.append(f'entry {position} is not a record')\n"
        "            continue\n"
        "        yield item\n"
    )
    assert _silent_exclusions(accounted) == []

    # --- PERMITTING ARM 2, A DIFFERENT SHAPE ENTIRELY: node-kind dispatch over
    # an `ast` tree excludes nothing — every branch is handled and the operand
    # is not a data type. A scan bound to the word `isinstance` would refuse
    # this, and refusing the module's own AST helpers is how a guard gets
    # weakened until it is decorative.
    dispatch = (
        "import ast\n"
        "def walk(node, out):\n"
        "    for sub in ast.walk(node):\n"
        "        if " + "isinstance" + "(sub, ast.Import):\n"
        "            continue\n"
        "        out.append(sub)\n"
    )
    assert _silent_exclusions(dispatch) == []

    # --- PERMITTING ARM 3, A THIRD SHAPE: a ternary to a NON-empty default
    # substitutes a real value rather than erasing one. The rule is about
    # narrowing to nothing, and a rule that fired on every ternary would say
    # so about code that loses nothing.
    substituting = (
        "def norm(raw, fallback):\n"
        "    return raw if " + "isinstance" + "(raw, dict) else fallback\n"
    )
    assert _silent_exclusions(substituting) == []

    # --- THE SCOPE THIS DOES NOT REACH, driven so the gap is measured rather
    # than assumed: a conditional COLLECT with no else is a silent exclusion
    # too, and is not statically separable from ordinary dispatch — the branch
    # that appends and the branch that dispatches are the same AST.
    #
    # WHAT HOLDS IT INSTEAD, stated exactly rather than waved at: section 48
    # covers every instance whose effect is a packet identical to the clean
    # run, which is the sub-class that reads clean and therefore the dangerous
    # one; an exclusion that moves a published count (a dropped JSONL record
    # moves `record_count`) is visible in the packet but not as a violation,
    # and those are held by the targeted nodes in sections 43 to 46. Neither
    # instrument subsumes the other and neither is claimed to.
    #
    # This assertion fails the day the static rule is widened, which is the
    # moment to delete it.
    conditional_collect = (
        "def read(records):\n"
        "    out = []\n"
        "    for item in records:\n"
        "        if " + "isinstance" + "(item, dict):\n"
        "            out.append(item)\n"
        "    return out\n"
    )
    assert _silent_exclusions(conditional_collect) == [], (
        "the static rule now reaches the conditional-collect shape; delete this "
        "disclosure and widen the docstring"
    )



# ==========================================================================
# 48 — THE BEHAVIOURAL CLOSER: retyping any recorded value must change the
#      packet. One node per evidence document, 20s each: the sweep runs
#      `reconcile(capture(...))` once per mutation and `capture` costs ~60ms,
#      most of it the `python3 -S` import audit. Split by document so no node
#      approaches the frozen per-test budget and so a failure names the file.
# ==========================================================================
#
# THE INSTRUMENT THAT DOES NOT DEPEND ON THE SHAPE OF THE EXCLUSION. Section 47
# refuses three gating shapes statically; four were reproduced and a fifth (a
# `bool()`/`str()` coercion with no gate at all) was found by THIS sweep, not
# by the static rule and not by the six-site report that prompted the cycle.
# The question it asks is the only one that generalises: can retyping a value
# the subject RECORDED leave the packet byte-identical to the clean run? If it
# can, that value reached no channel — not the malformed one, not the
# named-discrepancy one — and less evidence read exactly as clean as more.
#
# It is deliberately NOT asserted that each mutation is DETECTED as a
# violation. Some retyped values are ordinary data with no decision attached.
# The assertion is only that the packet CHANGED, which is the necessary
# condition for any downstream reader — including a third party recomputing
# from raw bytes — to tell the two runs apart.


def _retyped_variants(document: Any, pointer: str = "") -> list[tuple[str, Any]]:
    """Every ``(pointer, document)`` pair with ONE recorded value retyped.

    DERIVED FROM THE FIXTURE, never from a list written here: a new field in a
    frozen evidence document is swept without anyone remembering to add it.
    Each variant differs from its parent at exactly one JSON pointer and
    changes that value's TYPE, which is precisely the input class every one of
    the reproduced sites excluded or coerced.
    """
    variants: list[tuple[str, Any]] = []
    if isinstance(document, dict):
        for key in sorted(document):
            for child_pointer, child in _retyped_variants(document[key], f"{pointer}/{key}"):
                variants.append((child_pointer, {**document, key: child}))
    elif isinstance(document, list):
        for index, item in enumerate(document):
            for child_pointer, child in _retyped_variants(item, f"{pointer}/{index}"):
                copied = list(document)
                copied[index] = child
                variants.append((child_pointer, copied))
            if isinstance(item, (dict, list)):
                # THE WHOLE ELEMENT retyped, not one of its leaves. A reader
                # that drops a record because the RECORD is the wrong type —
                # `if isinstance(item, dict): out.append(item)` — loses nothing
                # a leaf mutation would reach.
                wrapped = list(document)
                wrapped[index] = [item]
                variants.append((f"{pointer}/{index}", wrapped))
    elif isinstance(document, str):
        variants.append((pointer, [document]))
    elif isinstance(document, bool):
        # BEFORE the int arm: `bool` is a subclass of `int`, and the two need
        # different replacements — `str(True)` is what `bool(x)` used to
        # collapse back onto `true`.
        variants.append((pointer, str(document)))
    elif isinstance(document, int):
        variants.append((pointer, str(document)))
    return variants


#: The ``capture()`` components whose answer cannot differ between two cases of
#: one sweep, mapped to the arity of the key they are memoised on.
#:
#: BOTH ARE ARGUMENT-INVARIANT ACROSS A SWEEP, which is what makes the
#: memoisation a hoist rather than a shortcut: ``_source_audit`` is called with
#: the observer's own path in every capture, and ``_executables_plane`` takes no
#: argument at all. Neither reads the evidence document a sweep mutates, so
#: neither can distinguish case 3 from case 40.
#:
#: ``_git_snapshot`` IS here, but only because the sweep also holds ``cwd``
#: fixed. It takes ``cwd``, and the default ``_production_packet`` route passes
#: ``cwd=run_root`` — a DIFFERENT directory per case — so memoising it alone
#: would produce ZERO hits. The sweep passes one shared ``cwd`` (see
#: ``_production_packet``), which makes its question identical across variants
#: rather than merely its answer. Measured: with the sweep still spawning two
#: `git` subprocesses per case, the inventory node reached 18.16 s under 24-way
#: contention against the frozen 20 s bound — 1.10x margin — because process
#: spawns contend far worse than CPU work (10.1x degradation where the whole
#: run degraded 4.03x). Hoisting the two argument-invariant components was not
#: enough on its own.
_HOISTABLE_CAPTURE_COMPONENTS = (
    "_source_audit",
    "_executables_plane",
    "_git_snapshot",
)


@contextlib.contextmanager
def _hoisted_constant_planes():
    """Memoise the ``capture()`` components that answer identically per sweep.

    THE MEASURED PROBLEM. Each ``capture()`` spawns FIVE subprocesses and the
    inventory sweep ran 57 captures — 285 spawns. Component cost per capture:
    ``_source_audit`` 44.7 ms (65%), ``_executables_plane`` 11.6 ms (17%),
    ``_git_snapshot`` 9.0 ms (13%); ``reconcile`` is 0.3 ms. The node measured
    5.41 s against a frozen 20 s per-test budget, and doc-master REPRODUCED the
    timeout under 24-way CPU contention (whole run 125.61 s, 4.05x): the bound
    was reached at a 3.6x–4.2x slowdown, against a 2-core runner this file
    itself calls "~3x slower". That is 1.14x–1.37x of margin.

    WHAT IS NOT WEAKENED, and how it is known rather than argued. The real
    ``capture()`` -> ``reconcile()`` route still runs for every case: the
    memoised functions are the module's own, called with the module's own
    arguments, returning the module's own answers. Only the recomputation is
    skipped. ``_sweep_one_document`` PROVES this per sweep by recomputing the
    baseline with the hoist OFF and refusing a byte difference — a comparison,
    not a claim — and the reinstatement checks (a reverted R1 ``type`` fix and
    a reverted D11 JSON-identity fix) were re-run against the hoisted sweep and
    still turned it red.

    A DEEP COPY IS HANDED BACK on every hit. The cached plane is nested and
    ``capture()``'s caller owns what it receives; one case mutating a shared
    object would silently couple every later case to it, which is a worse
    defect than the one this exists to fix.
    """
    caches: dict[str, dict[Any, Any]] = {}
    originals = {
        name: getattr(observer, name) for name in _HOISTABLE_CAPTURE_COMPONENTS
    }

    def memoise(name: str, original):
        cache: dict[Any, Any] = {}
        caches[name] = cache

        def wrapper(*args):
            key = tuple(str(a) for a in args)
            if key not in cache:
                cache[key] = original(*args)
            return copy.deepcopy(cache[key])

        return wrapper

    try:
        for name, original in originals.items():
            setattr(observer, name, memoise(name, original))
        yield caches
    finally:
        for name, original in originals.items():
            setattr(observer, name, original)


def _stable_packet_text(packet: dict[str, Any], run_root: Path) -> str:
    """One packet as comparable text, with the per-case run root neutralised.

    Every packet records the run root it read — in ``run``, in each
    bounded-evidence ``path``, and in the filesystem plane's declared roots.
    That string differs per case BY CONSTRUCTION, so it is rewritten to one
    placeholder; a surviving difference is a difference in the EVIDENCE. The
    twin control in each node is what proves the rewrite is complete.
    """
    return json.dumps(packet, sort_keys=True).replace(str(run_root), "<RUN_ROOT>")


def _production_packet(run_root: Path, *, cwd: Path | None = None) -> str:
    """``reconcile(capture(...))`` — the production route, as text.

    That composition IS the production route by definition: ``_cli`` is those
    two calls plus one candidate-claim read. It is driven in-process so a sweep
    can afford tens of cases inside the frozen 20s budget; the ``sys.path``
    isolation the CLI subprocess proves is a DIFFERENT question, owned by the
    D03/D04 nodes, and ``test_the_in_process_route_and_the_cli_agree_on_the_same_bytes``
    measures
    that the two agree rather than assuming it.

    ``cwd`` DEFAULTS TO ``run_root`` — the shape ``_cli`` is driven with here —
    and is overridable for ONE caller: a sweep, which needs the git plane's
    question to be the same question in every case so it can be answered once.
    ``cwd`` is an observer INPUT, not evidence; the sweep mutates the evidence
    document and nothing else, so holding ``cwd`` fixed removes a per-case
    variation the sweep never asked about. It is recorded in ``run.cwd``, where
    a constant is exactly as comparable as a rewritten placeholder.
    """
    observation = observer.capture(
        cwd=run_root if cwd is None else cwd,
        run_root=run_root,
        session_uuid=SESSION_UUID,
        settings_overlay=SETTINGS_OVERLAY,
        setting_sources=_canonical_setting_sources(),
        debug_file=run_root / "debug.log",
    )
    return _stable_packet_text(observer.reconcile(observation), run_root)


def _decisions_by_id(packet_text: str) -> dict[str, Any]:
    """One packet's decision records, keyed by ``decision_id``.

    The unit of the laundering question. A ``comparison`` block holding twelve
    decisions changes when ANY of them changes, so comparing blocks lets a
    surviving violation on one decision hide the laundering of another —
    measured, not supposed: the block-level form passed against a deliberately
    reverted fix.
    """
    return {
        record["decision_id"]: record
        for record in json.loads(packet_text)["comparison"]["decisions"]
    }


def _write_json(path: Path, document: Any) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def _write_jsonl(path: Path, records: Any) -> None:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )


def _read_jsonl_fixture(name: str) -> list[Any]:
    return [
        json.loads(line)
        for line in (VALID_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sweep_one_document(
    tmp_path: Path,
    name: str,
    document: Any,
    writer,
    *,
    required_pointer: str,
    violate,
) -> None:
    """Drive every one-value retyping of ``name`` through the production route.

    THE CORPUS CARRIES A VIOLATION, and that is the correction this cycle. The
    sweep used to run over the CLEAN fixture and assert only that the PACKET
    changed, and both halves of that were too weak to see the class it was
    built for. An exclusion that only matters when the excluded record IS the
    violation cannot appear in a corpus that has no violation; and appending a
    ghost record moves ``stream.record_count`` from 6 to 7, so the packet
    changes — the assertion passes — while the ``comparison`` block stays
    byte-identical to a run in which nothing was wrong. R1 lived in exactly
    that gap.

    ``violate`` seeds the corpus with a violation the decisions NAME. Two
    questions are then asked of every mutation, and they are different
    questions:

    * **Did the packet change at all** (the original property): the retyped
      value reached SOME channel a reader can see.
    * **Did each VIOLATED DECISION stay away from its clean answer** (the new
      one): no single retyping makes a decision that named a violation
      recompute the record it computes when there is nothing to name.

    THE SECOND QUESTION IS ASKED PER DECISION, NOT PER COMPARISON BLOCK, and
    that is a correction measured rather than reasoned. Asked of the whole
    block it PASSED against a deliberately reverted R1 fix: this corpus seeds
    two violations, retyping the ghost's discriminator laundered D09 while D08
    still named the orphan, the block therefore still differed from the clean
    one, and the sweep reported success over the exact defect it was widened
    to find. One violation masking the laundering of another is the same
    shape as everything else in this cycle — a check whose subject is coarser
    than the thing it is about.

    Five controls, all of them here so no caller can run the sweep without
    them: a negative control (two copies of the same corpus agree) refuting a
    comparison that measures the run root; a positive control that the seeded
    violations really are NAMED, refuting a sweep run over a corpus that
    turned out to be clean; a positive control that MORE THAN ONE decision is
    violated, so the per-decision split is exercised rather than degenerate; a
    positive control that the derived mutation set is non-empty and reaches
    ``required_pointer``, refuting a zero-length sweep passing by never
    executing; and the clean comparison itself, which must differ.
    """
    violating = violate(copy.deepcopy(document))
    baseline_root = _make_run_root(tmp_path / "baseline")
    writer(baseline_root / name, violating)

    # --- THE HOIST'S OWN CONTROL, RUN BEFORE ANYTHING DEPENDS ON IT. The
    # baseline is computed TWICE over the same root, once with the constant
    # planes recomputed per capture and once with them hoisted, and the two
    # must be byte-identical. This is a comparison of the emitted packets, not
    # a claim about which functions were skipped: if hoisting changed ANY byte
    # of the production route, every assertion below would be measuring a
    # different observer from the one CI runs.
    # THE SHARED CWD the sweep captures under, so the git plane asks ONE
    # question across every case rather than N identically-answered ones.
    sweep_cwd = tmp_path
    unhoisted_baseline = _production_packet(baseline_root, cwd=sweep_cwd)

    with _hoisted_constant_planes() as caches:
        baseline = _production_packet(baseline_root, cwd=sweep_cwd)
        assert baseline == unhoisted_baseline, (
            "hoisting the constant capture components changed the emitted "
            "packet; the sweep below would not be measuring the production "
            "route"
        )
        clean_root = _make_run_root(tmp_path / "clean")
        clean_decisions = _decisions_by_id(
            _production_packet(clean_root, cwd=sweep_cwd)
        )
        _sweep_cases(
            tmp_path, name, writer, required_pointer, violating,
            baseline, clean_decisions, sweep_cwd,
        )
    # ...and the hoist really did fire. A context manager that silently failed
    # to patch would leave every number above correct and the budget unchanged.
    assert all(len(cache) == 1 for cache in caches.values()), caches
    assert set(caches) == set(_HOISTABLE_CAPTURE_COMPONENTS), sorted(caches)
    # The patch is UNDONE, so a later node cannot inherit a cached plane.
    assert observer._source_audit.__name__ == "_source_audit", observer._source_audit


def _sweep_cases(
    tmp_path: Path,
    name: str,
    writer,
    required_pointer: str,
    violating: Any,
    baseline: str,
    clean_decisions: dict[str, Any],
    sweep_cwd: Path,
) -> None:
    """The sweep body, run inside the hoist. Split out so the hoist's control
    above cannot accidentally be inside the thing it validates."""
    baseline_decisions = _decisions_by_id(baseline)

    # --- POSITIVE CONTROL OF THE CORPUS, and of the per-decision split. A
    # sweep for laundering over evidence that carries nothing to launder
    # cannot fail, whatever it asserts; and with only ONE violated decision the
    # per-decision question would collapse back into the block-level one that
    # passed against the reverted fix.
    violated = sorted(
        decision_id
        for decision_id, record in baseline_decisions.items()
        if record != clean_decisions[decision_id]
    )
    assert len(violated) >= 2, (
        f"the seeded violations in {name} move {violated}; this sweep needs at "
        "least two violated decisions or the per-decision split is untested"
    )

    twin_root = _make_run_root(tmp_path / "twin")
    writer(twin_root / name, violating)
    assert _production_packet(twin_root, cwd=sweep_cwd) == baseline, (
        "two copies of the same corpus already disagree; the comparison is "
        "measuring the run root, not the evidence"
    )

    pairs = _retyped_variants(violating)
    pointers = [pointer for pointer, _ in pairs]
    assert len(pointers) >= 10, pointers
    assert [p for p in pointers if p.endswith(required_pointer)], (name, pointers)

    # ONE RUN ROOT FOR EVERY CASE, rewriting only the document under sweep.
    #
    # THE MEASURED PROBLEM, and it is not the one the hoist fixed. With the
    # subprocess spawns already hoisted out, a cProfile of the inventory sweep
    # under 32-way contention on 16 cores put 15.29s of its 15.85s inside
    # `_io.open` across 1,377 calls. The bytes are trivial — the largest
    # fixture is 15,070 bytes — so what costs is the number of opens on
    # FRESHLY CREATED files: 27 per case, of which 12 exist only to rebuild a
    # directory identical to the last one. The two halves are not symmetric,
    # and that asymmetry is the measurement rather than an explanation of it —
    # 612 of those opens sit inside `shutil.copy2`, whose whole cumulative cost
    # is 0.15s, so essentially all of the 15.29s belongs to the other 765, the
    # ones the readers make. WHY they differ is NOT established here; a
    # mechanism nobody measured has no business in a frozen file. What IS
    # established is the remedy's effect, over the same 51 cases: a fresh root
    # per case 417ms uncontended / 14,009ms contended, one reused root 98ms /
    # 901ms — 15.5x contended.
    #
    # WHAT IS NOT WEAKENED. The case set, the mutation domain, the production
    # route and every assertion are untouched; only the directory the evidence
    # is written into is reused. Each case REWRITES `name` whole, and no other
    # file in the root is ever written, so no case can inherit another's bytes.
    # The claim that the root is not evidence is MEASURED twice here: the twin
    # control above already proves two roots at different paths produce the
    # same packet, and the equivalence control below recomputes one case
    # through a fresh root and refuses a byte difference.
    case_root = _make_run_root(tmp_path / "cases")

    unseen: list[str] = []
    laundered: list[str] = []
    for index, (pointer, mutated) in enumerate(pairs):
        run_root = case_root
        writer(run_root / name, mutated)
        text = _production_packet(run_root, cwd=sweep_cwd)
        if index == len(pairs) // 2:
            # EQUIVALENCE CONTROL, on a case chosen away from the ends so it is
            # neither the first write into a cold directory nor the last. A
            # fresh root, built the way every case used to be, must produce the
            # identical packet. If reuse leaked state between cases this is
            # where it shows.
            fresh = _make_run_root(tmp_path / f"fresh_{index}")
            writer(fresh / name, mutated)
            assert _production_packet(fresh, cwd=sweep_cwd) == text, (
                f"{name}{pointer}: the reused run root and a fresh one disagree; "
                "the sweep is measuring the directory, not the evidence"
            )
        if text == baseline:
            unseen.append(f"{name}{pointer}")
        mutated_decisions = _decisions_by_id(text)
        for decision_id in violated:
            if mutated_decisions[decision_id] == clean_decisions[decision_id]:
                laundered.append(f"{name}{pointer} -> {decision_id}")

    assert unseen == [], (
        "retyping these recorded values left the packet byte-identical to the "
        "run they were retyped from, so they reached no channel any reader can "
        "see:\n" + "\n".join(unseen)
    )
    assert laundered == [], (
        "retyping these recorded values made a decision that NAMED a violation "
        "recompute the exact record it computes over a corpus with nothing to "
        "name:\n" + "\n".join(laundered)
    )


@pytest.mark.timeout(10)
def test_the_in_process_route_and_the_cli_agree_on_the_same_bytes(tmp_path):
    """The sweep's route is the route the smoke command runs.

    ``_production_packet`` composes ``capture`` and ``reconcile`` in-process.
    That is what ``_cli`` does, but "is what it does" is a claim about source,
    and the copy that EXECUTES in CI is the subprocess. Measured here rather
    than assumed, once, so the three sweep nodes do not each pay for it.
    """
    run_root = _make_run_root(tmp_path / "agreement")
    in_process = json.loads(_production_packet(run_root))
    from_cli = json.loads(
        _stable_packet_text(_packet_from(OBSERVER_PATH, run_root), run_root)
    )
    assert in_process["comparison"] == from_cli["comparison"]
    assert in_process["observation"] == from_cli["observation"]
    # --- CONTROL OF THAT AGREEMENT: the comparison is not vacuous. A packet
    # this test perturbs must stop matching, or "they agree" would be true of
    # any two objects this assertion was handed.
    perturbed = copy.deepcopy(from_cli)
    perturbed["comparison"]["decisions"][0]["evidence_count"] += 1
    assert in_process["comparison"] != perturbed["comparison"]


def _violate_settings(document: Any) -> Any:
    """A digest mismatch (D06) and an undeclared observed source (D07)."""
    document["observed"][0]["sha256"] = "f" * 64
    document["observed"].append(
        {"path": "/proof/root/settings/undeclared.settings.json", "sha256": "a" * 64}
    )
    return document


def _violate_inventory(document: Any) -> Any:
    """A silent content change (D11) and a write outside every root (D10)."""
    shared = "/repo/plugins/autonomous-dev/lib/pipeline_state.py"
    document["post"]["entries"][shared]["sha256"] = "b" * 64
    document["post"]["entries"]["/etc/not_a_declared_root"] = {
        "kind": "file",
        "sha256": "c" * 64,
        "bytes": 12,
        "content_truncated": False,
        "mode": 420,
        "uid": 501,
        "acl_state": "UNMEASURED",
    }
    return document


def _violate_stream(records: Any) -> Any:
    """A receiptless hook event (D09) and an orphan tool call (D08).

    Both are recorded with a STRING ``type``, so the baseline names them and
    the sweep's question becomes whether retyping that discriminator — or any
    other recorded value — can make them stop being named.
    """
    records.append(
        {"type": "hook_event", "tool_use_id": "toolu_GHOST", "hook_event_name": "PreToolUse"}
    )
    records.append(
        {"type": "tool_use", "tool_use_id": "toolu_ORPHAN", "name": "Bash", "outcome": "success"}
    )
    return records


@pytest.mark.timeout(20)
def test_retyping_any_recorded_settings_value_changes_the_packet(tmp_path):
    """The document whose reader DROPPED entries and COERCED digests."""
    _sweep_one_document(
        tmp_path,
        observer.EVIDENCE_SETTINGS,
        json.loads((VALID_DIR / observer.EVIDENCE_SETTINGS).read_text(encoding="utf-8")),
        _write_json,
        required_pointer="/sha256",
        violate=_violate_settings,
    )


@pytest.mark.timeout(20)
def test_retyping_any_recorded_inventory_value_changes_the_packet(tmp_path):
    """The document whose readers dropped scalar entries and coerced flags.

    This is the node that found the coercion nobody reported: ``bool(x)`` on
    ``root_exists`` mapped ``"True"`` onto ``true``, so a subject-authored
    value reached the packet indistinguishable from a different one.
    """
    _sweep_one_document(
        tmp_path,
        observer.EVIDENCE_FS_INVENTORY,
        json.loads((VALID_DIR / observer.EVIDENCE_FS_INVENTORY).read_text(encoding="utf-8")),
        _write_json,
        required_pointer="/mode",
        violate=_violate_inventory,
    )


@pytest.mark.timeout(20)
def test_retyping_any_recorded_stream_value_changes_the_packet(tmp_path):
    """The document whose reader dropped a record by the TYPE of its identity."""
    _sweep_one_document(
        tmp_path,
        observer.EVIDENCE_STREAM,
        _read_jsonl_fixture(observer.EVIDENCE_STREAM),
        _write_jsonl,
        required_pointer="/tool_use_id",
        violate=_violate_stream,
    )


# ==========================================================================
# 49 — THE COMPARISON RULE: two recordings Python calls equal are not the same
#      recording. 20s: one `capture` plus one `reconcile` per case, in process.
# ==========================================================================
#
# THE SHAPE SECTION 48 CANNOT REACH, and the reason is structural rather than
# incidental. That sweep retypes ONE pointer at a time, so for a value that is
# only ever read by being COMPARED WITH ITS TWIN it can never produce the input
# that matters: `pre` retyped alone still differs from an untouched `post`, and
# the comparison still fires. The masking input is a COORDINATED PAIR — the
# same sub-pointer retyped on BOTH sides to two values Python calls equal and
# JSON does not. `1 == True`, `0 == False` and `1 == 1.0`; a `sha256` recorded
# `1` on one side and `true` on the other is two different documents that
# `==` cannot separate.
#
# THE PAIR POOL IS GENERATED, NOT LISTED. Enumerating `bool`/`int`/`float` at a
# call site is the #1503 shape this whole rung keeps being caught by, and it
# would miss the fourth type nobody thought of. The pairs are DERIVED from the
# property that defines the defect — `a == b` and `json(a) != json(b)` — over a
# pool of ordinary recordable scalars, so a pair nobody predicted is included
# by the same rule that includes the three above.


def _equality_masking_pairs() -> list[tuple[Any, Any]]:
    """Every ``(a, b)`` from the scalar pool where ``a == b`` but the JSON differs.

    The definition of the defect, executed. Nothing here says ``bool`` or
    ``float``: a pair qualifies by BEHAVING like the masking shape, so adding a
    value to the pool below is enough for every pair it forms to be swept.
    """
    pool: list[Any] = [0, 1, 2, 0.0, 1.0, False, True, "0", "1", "", None, [], {}, [0], [False]]
    pairs = []
    for left in pool:
        for right in pool:
            same = False
            try:
                same = bool(left == right)
            except Exception:  # pragma: no cover - no pool member does this
                same = False
            if same and json.dumps(left, sort_keys=True) != json.dumps(right, sort_keys=True):
                pairs.append((left, right))
    return pairs


def _paired_leaf_paths(document: Any) -> list[tuple[Any, ...]]:
    """Sub-paths present, as a LEAF, under BOTH ``pre`` and ``post``.

    Derived from the fixture, so a new field in a frozen evidence document is
    paired without anyone remembering to add it here.
    """

    def leaves(node: Any, path: tuple[Any, ...] = ()) -> dict[tuple[Any, ...], Any]:
        if isinstance(node, dict):
            found: dict[tuple[Any, ...], Any] = {}
            for key in sorted(node):
                found.update(leaves(node[key], path + (key,)))
            return found
        if isinstance(node, list):
            found = {}
            for index, item in enumerate(node):
                found.update(leaves(item, path + (index,)))
            return found
        return {path: node}

    pre = leaves(document.get("pre"))
    post = leaves(document.get("post"))
    return sorted(set(pre) & set(post), key=lambda path: [str(step) for step in path])


def _assign(document: Any, path: tuple[Any, ...], value: Any) -> None:
    node = document
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = value


@pytest.mark.timeout(20)
def test_python_equal_recordings_cannot_mask_a_difference_the_bytes_carry(tmp_path):
    """A coordinated pair Python calls equal must still be two recordings.

    THE MEASURED DEFECT: D11 compared ``before.get("sha256") == after.get(...)``
    with Python equality. `'000'` against `'111'` named a discrepancy and `1`
    against `2` named one, but `1`/`True`, `0`/`False` and `1`/`1.0` each named
    NOTHING — a content change outside every declared writable root, recorded
    in the subject's own bytes, recomputed as no change at all. No coercion was
    involved anywhere, which is why every guard aimed at coercions was blind to
    it, and why the settings twin — guarded by NAMING a non-string digest
    before comparing — answered correctly on the identical input.

    THE ARMS.

    * REFUSING: every generated masking pair, at every paired leaf, must leave
      the two sides distinguishable in the packet. Driven over the whole
      cross product rather than a chosen pointer, so the rule is not scoped to
      ``sha256``.
    * PERMITTING: a pair assigning the SAME recording to both sides must NOT be
      reported as a difference. A comparison that called everything different
      would satisfy the refusing arm and be worthless.
    * INSTRUMENT CONTROLS: the pool generates the three known masking pairs and
      more; the paired-leaf set is non-empty and includes ``sha256``; and the
      in-memory route agrees with the file route for one representative case,
      because this node mutates the OBSERVATION for speed and that is a
      different door from the one the smoke command walks.
    """
    inventory = json.loads(
        (VALID_DIR / observer.EVIDENCE_FS_INVENTORY).read_text(encoding="utf-8")
    )

    # --- INSTRUMENT CONTROL 1: the generated pool really contains the shape.
    pairs = _equality_masking_pairs()
    # Rendered, because a generated pair may hold a list and a list is not a
    # set element — the pool is derived from a property, not from a tuple of
    # scalars someone chose.
    rendered = {(json.dumps(left), json.dumps(right)) for left, right in pairs}
    known = {("1", "true"), ("0", "false"), ("1", "1.0"), ("0", "0.0"), ("[0]", "[false]")}
    assert known <= rendered, sorted(known - rendered)
    assert len(pairs) >= len(known) * 2, len(pairs)
    # ...and contains no pair JSON already separates by accident.
    for left, right in pairs:
        assert left == right and json.dumps(left) != json.dumps(right), (left, right)

    # --- INSTRUMENT CONTROL 2: the paired-leaf set is derived and non-empty.
    paired = _paired_leaf_paths(inventory)
    assert len(paired) >= 8, paired
    assert any(path[-1] == "sha256" for path in paired), paired

    run_root = _make_run_root(tmp_path / "pairs")
    observation = observer.capture(
        cwd=run_root,
        run_root=run_root,
        session_uuid=SESSION_UUID,
        settings_overlay=SETTINGS_OVERLAY,
        setting_sources=_canonical_setting_sources(),
        debug_file=run_root / "debug.log",
    )

    def decisions_for(path: tuple[Any, ...], left: Any, right: Any) -> dict[str, Any]:
        mutated = copy.deepcopy(observation)
        _assign(mutated["filesystem"]["pre"], path, left)
        _assign(mutated["filesystem"]["post"], path, right)
        return _decisions_by_id(json.dumps(observer.reconcile(mutated)))

    # --- WHICH LEAVES ARE COMPARED IS MEASURED, NOT LISTED. A leaf no
    # decision compares across the pair — `root_exists`, an entry's `bytes` —
    # cannot mask anything, and asserting over it would refuse 164 sites that
    # carry no comparison at all. The separation is made by DRIVING each leaf
    # with a pair that is unambiguously different and asking whether any
    # decision noticed. That is a control, and it is what makes the exclusion
    # below a measurement rather than a guess about which fields matter.
    compared: list[tuple[Any, ...]] = []
    for path in paired:
        if decisions_for(path, "PROBE_A", "PROBE_B") != decisions_for(
            path, "PROBE_A", "PROBE_A"
        ):
            compared.append(path)
    assert compared, "no paired leaf is compared by any decision; the probe is inert"
    assert any(path[-1] == "sha256" for path in compared), [
        "/" + "/".join(str(step) for step in path) for path in compared
    ]

    # --- REFUSING ARM: at every leaf a decision DOES compare, a pair recording
    # two different documents must not read like a pair recording one.
    masked: list[str] = []
    for path in compared:
        pointer = "/" + "/".join(str(step) for step in path)
        for left, right in pairs:
            if decisions_for(path, left, right) == decisions_for(path, left, left):
                masked.append(f"{pointer}: pre {left!r} / post {right!r}")
    assert masked == [], (
        "these coordinated pairs record DIFFERENT bytes on the two sides and "
        "recomputed exactly what a pair recording the SAME bytes does:\n"
        + "\n".join(masked)
    )

    # --- PERMITTING ARM: the same machinery, over pairs that ARE the same
    # recording, must report nothing. A comparison calling everything
    # different would satisfy the arm above and be worthless. Every pool
    # member is driven at every compared leaf, so this is not one lucky value.
    over_reported: list[str] = []
    for path in compared:
        pointer = "/" + "/".join(str(step) for step in path)
        for value, _ in pairs:
            if decisions_for(path, value, value) != decisions_for(path, value, value):
                over_reported.append(f"{pointer}: {value!r}")  # pragma: no cover
            if decisions_for(path, value, copy.deepcopy(value)) != decisions_for(
                path, value, value
            ):
                over_reported.append(f"{pointer}: a copy of {value!r} read as different")
    assert over_reported == [], "\n".join(over_reported)

    # --- INSTRUMENT CONTROL 3: this node mutates the OBSERVATION, and the
    # smoke command mutates a FILE. One representative case is driven through
    # both doors and the answers must agree, or every result above is about a
    # door nobody runs.
    sha_path = next(path for path in compared if path[-1] == "sha256")
    file_root = _make_run_root(tmp_path / "file_route")
    through_file = copy.deepcopy(inventory)
    _assign(through_file["pre"], sha_path, 1)
    _assign(through_file["post"], sha_path, True)
    _write_json(file_root / observer.EVIDENCE_FS_INVENTORY, through_file)
    through_file_decisions = _decisions_by_id(_production_packet(file_root))
    in_memory = decisions_for(sha_path, 1, True)
    assert (
        through_file_decisions["D11_NO_SILENT_CONTENT_CHANGE"]["discrepancy_count"]
        == in_memory["D11_NO_SILENT_CONTENT_CHANGE"]["discrepancy_count"]
        >= 1
    ), (through_file_decisions["D11_NO_SILENT_CONTENT_CHANGE"], in_memory["D11_NO_SILENT_CONTENT_CHANGE"])


# ==========================================================================
# 50 — THE MIRROR OF THE STATUS WALK, for TRUNCATION FLAGS. 20s: one `capture`
#      plus one `reconcile` per published flag location, in process.
# ==========================================================================
#
# THE ASYMMETRY THAT LET R2 SURVIVE, stated plainly. Section 44 already walks
# the emitted packet, discovers every nested `observation_status` bearer and
# refuses one nobody declared. There was NO equivalent for truncation flags —
# the registry declared which flag names may exist and the schema described
# them, and neither could say whether a reader ever REACHES the place a flag is
# published. `content_truncated` occurs in the packet at exactly one location,
# `/observation/filesystem/{pre,post}/entries/*/content_truncated`, and
# `_plane_bounds` descended into `pre` and `post` and stopped. So the one flag
# naming WHICH member digest is a prefix was published, schema'd, asserted
# about in a frozen description, and read by nobody: D11 compared prefix
# digests as if whole, `any_bound_truncated` stayed false, the decision stayed
# OBSERVED.
#
# BOTH SIDES ARE DERIVED FROM THE MODULE. The publication side is a walk of the
# emitted bytes against `observer.PUBLISHED_TRUNCATION_FLAGS`; the reader side
# is measured by FLIPPING each published flag and asking whether `reconcile`'s
# answer moves. Neither is a list written here, which is the property that
# makes this catch the NEXT flag rather than this one.


def _flag_sites(node: Any, path: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    """Every key-path at which ``node`` publishes a truncation flag.

    Key PATHS, not JSON pointer strings: inventory keys are absolute
    filesystem paths and contain ``/``, so a slash-joined pointer could not be
    walked back down.
    """
    sites: list[tuple[Any, ...]] = []
    if isinstance(node, dict):
        for key in sorted(node):
            here = path + (key,)
            if key in observer.PUBLISHED_TRUNCATION_FLAGS:
                sites.append(here)
            sites.extend(_flag_sites(node[key], here))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            sites.extend(_flag_sites(item, path + (index,)))
    return sites


def _unread_flag_sites(observation: dict[str, Any]) -> list[str]:
    """Published truncation flags whose value no reader's answer depends on.

    Measured by flipping, never by inspecting the reader's source: a walk that
    LOOKS like it reaches a key is the claim that was already false.
    """
    baseline = json.dumps(observer.reconcile(copy.deepcopy(observation))["comparison"])
    unread: list[str] = []
    for path in _flag_sites(observation):
        mutated = copy.deepcopy(observation)
        _assign(mutated, path, not bool(_read_path(observation, path)))
        if json.dumps(observer.reconcile(mutated)["comparison"]) == baseline:
            unread.append("/" + "/".join(str(step) for step in path))
    return unread


def _read_path(document: Any, path: tuple[Any, ...]) -> Any:
    node = document
    for step in path:
        node = node[step]
    return node


@pytest.mark.timeout(20)
def test_every_published_truncation_flag_is_read_where_it_is_published(tmp_path):
    """A bound the packet publishes must change some decision, wherever it sits.

    THE ARMS.

    * PERMITTING: on the shipped bytes every published flag location changes
      the comparison when flipped. Without this arm every refusal below would
      be indistinguishable from a guard that cannot pass.
    * REFUSING, THE SHIPPED DEFECT: `_plane_bounds` is restored to the
      two-key descent it shipped with, and the guard must name the
      entries-level `content_truncated` — so this instrument is measured
      against the bug it was built for rather than assumed to cover it.
    * REFUSING, A DIFFERENT SHAPE ENTIRELY: a flag published on a plane NO
      decision declares. The pre-fix defect was a flag one level too deep
      inside a plane that IS declared; this one is at the top of a plane that
      is not, so a fix scoped to depth would not satisfy it.
    * INSTRUMENT CONTROLS: the discovery is non-empty, reaches the entries
      level, and accounts for every name in the published registry — a flag
      that is declared published and appears nowhere in the packet is named,
      and a flag that appears only in the `comparison` block is separated as
      one the reader WRITES rather than reads.
    """
    run_root = _make_run_root(tmp_path / "flags")
    observation = observer.capture(
        cwd=run_root,
        run_root=run_root,
        session_uuid=SESSION_UUID,
        settings_overlay=SETTINGS_OVERLAY,
        setting_sources=_canonical_setting_sources(),
        debug_file=run_root / "debug.log",
    )
    packet = observer.reconcile(copy.deepcopy(observation))

    # --- INSTRUMENT CONTROLS on the discovery.
    observation_sites = _flag_sites(observation)
    assert len(observation_sites) >= 10, observation_sites
    assert any(
        "entries" in path and path[-1] == "content_truncated" for path in observation_sites
    ), "the walk never reached the entries level, where R2 lived"

    read_names = {path[-1] for path in observation_sites}
    written_names = {path[-1] for path in _flag_sites(packet["comparison"])}
    missing = set(observer.PUBLISHED_TRUNCATION_FLAGS) - read_names - written_names
    assert missing == set(), (
        f"these flags are declared published and appear nowhere in the packet: "
        f"{sorted(missing)}"
    )
    # THE OVERLAP IS EXACTLY THE ROLLUPS, and this assertion was written the
    # other way round first — "the two families are disjoint" — and measured
    # false: `any_bound_truncated` is published on the observation planes AND
    # written into each decision's `evidence_bounds`. The true statement is
    # the narrower one, and it matters: a BOUND flag appearing in the
    # reader's own output would let the reader's answer stand in as evidence
    # that it read the input, which is the substitution this whole node exists
    # to refuse. Derived from the registry, so a new rollup is admitted and a
    # new bound is not.
    assert read_names & written_names <= set(observer.TRUNCATION_ROLLUP_FLAGS), sorted(
        (read_names & written_names) - set(observer.TRUNCATION_ROLLUP_FLAGS)
    )

    # --- PERMITTING ARM.
    assert _unread_flag_sites(observation) == [], _unread_flag_sites(observation)

    # --- REFUSING ARM A, THE SHIPPED DEFECT, driven against the reader that
    # shipped it. `_plane_bounds` is the copy that EXECUTES, so restoring its
    # pre-fix reach is the only way to know this instrument would have caught
    # R2 rather than merely being consistent with it.
    def two_key_descent(plane: Any) -> tuple[bool, bool]:
        if not isinstance(plane, dict):
            return False, False
        clipped = any(bool(plane.get(key)) for key in observer._TRUNCATION_KEYS)
        broken = any(bool(plane.get(key)) for key in observer._MALFORMED_KEYS)
        for key in observer._MALFORMED_COUNT_KEYS:
            try:
                broken = broken or int(plane.get(key) or 0) > 0
            except (TypeError, ValueError):
                broken = True
        for side in ("pre", "post"):
            nested = plane.get(side)
            if isinstance(nested, dict):
                sub_clipped, sub_broken = two_key_descent(nested)
                clipped = clipped or sub_clipped
                broken = broken or sub_broken
        return clipped, broken

    original = observer._plane_bounds
    try:
        observer._plane_bounds = two_key_descent
        pre_fix_unread = _unread_flag_sites(observation)
    finally:
        observer._plane_bounds = original
    assert any(
        site.endswith("/content_truncated") for site in pre_fix_unread
    ), f"the guard did not refuse the reader that shipped R2: {pre_fix_unread}"
    # ...and the restored reader is not simply broken for everything, or the
    # refusal above would be about the monkeypatch rather than about reach.
    assert len(pre_fix_unread) < len(observation_sites), pre_fix_unread

    # --- REFUSING ARM B, A DIFFERENT SHAPE: a plane-level flag on a plane no
    # decision declares. Nothing about the fix above mentions `environment`.
    undeclared = copy.deepcopy(observation)
    assert "environment" not in {
        plane
        for planes in observer.DECISION_EVIDENCE_PLANES.values()
        for plane in planes
    }, "environment is now a deciding plane; pick another undeclared one"
    undeclared["environment"]["record_truncated"] = False
    assert any(
        site == "/environment/record_truncated" for site in _unread_flag_sites(undeclared)
    ), _unread_flag_sites(undeclared)


# ==========================================================================
# 50b — THE MIRROR OF SECTION 50, ASKED FROM THE OTHER END. 10s: two AST
#       parses of the shipped source plus one per arm, no subprocess.
# ==========================================================================
#
# THE QUESTION SECTION 50 STRUCTURALLY CANNOT ASK. That node walks the EMITTED
# PACKET for published flags and refuses one no reader reaches — "is every
# published flag read?". F2 is invisible to it by construction: the settings
# overlay's truncation member and the candidate claim's were discarded INTO A
# THROWAWAY at the call, upstream of publication, so no flag existed at those
# two sites for a walk of the packet to find. An overlay of
# MAX_EVIDENCE_BYTES + 50,000 published a PREFIX digest in `overlay_sha256`
# beside a `byte_truncated` naming a DIFFERENT FILE and reading false, with the
# plane at OBSERVED; the candidate claim published a prefix digest and a byte
# count with no truncation field at all.
#
# So the mirror: DOES EVERY CLIPPING SITE PUBLISH A FLAG? The site list is
# derived from the module — every function that HANDS BACK a flag-named member
# is a clipping reader, and every call to one is a site — so this refuses the
# next reader as well as these four. Nothing below is a written list of names.


def _clipping_readers(tree: ast.AST, module: Any) -> dict[str, dict[int, str]]:
    """``{function: {tuple index: flag field}}`` for every reader HANDING BACK a flag.

    DERIVED, NEVER ENUMERATED, and the derivation is about the PUBLISHED
    SURFACE rather than about the cap: a function is a clipping reader when its
    return exposes a member this file's own ``_is_flag_name`` calls a flag.
    Keying on "mentions MAX_EVIDENCE_BYTES" would have missed ``_read_json``
    and ``_read_jsonl``, which apply no cap themselves and FORWARD one, and
    forwarding is exactly how a flag reaches a caller who can drop it.

    Two return shapes, because the module has two: a ``NamedTuple``-annotated
    return contributes the flag-named entries of ``_fields``, and a bare tuple
    return contributes the positions whose returned expression is a flag-named
    ``Name``. ``_sha256_file`` is the second kind — its third member is
    positional and unnamed in the annotation ``tuple[str | None, int | None,
    bool]``, so the position has to come from the ``return`` statement.
    """
    readers: dict[str, dict[int, str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        members: dict[int, str] = {}
        if isinstance(node.returns, ast.Name):
            fields = getattr(getattr(module, node.returns.id, None), "_fields", None)
            if fields:
                members = {i: n for i, n in enumerate(fields) if _is_flag_name(n)}
        if not members:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Tuple):
                    for index, element in enumerate(sub.value.elts):
                        if isinstance(element, ast.Name) and _is_flag_name(element.id):
                            members[index] = element.id
        if members:
            readers[node.name] = members
    return readers


class _ClipSite:
    """One call to a clipping reader, and what became of one flag member."""

    def __init__(
        self, reader: str, lineno: int, function: str, argument: str, flag: str,
        kind: str, target: str,
    ) -> None:
        self.reader, self.lineno, self.function = reader, lineno, function
        self.argument, self.flag, self.kind, self.target = argument, flag, kind, target

    def __repr__(self) -> str:  # pragma: no cover - assertion output only
        return (
            f"{self.function}:{self.lineno} {self.reader}({self.argument}) "
            f"[{self.flag}] {self.kind} -> {self.target}"
        )


def _clip_sites(tree: ast.AST, readers: dict[str, dict[int, str]]) -> list[_ClipSite]:
    """Every clipping-reader call, classified KEPT / DISCARDED / FORWARDED.

    ``KEPT`` means the flag member is bound to a name that is LOADED somewhere
    in the same function, or — for a ``NamedTuple`` bound whole — that
    ``<name>.<flag>`` is read there. ``DISCARDED`` means it is bound to a name
    nothing reads, dropped by a short tuple target, or thrown away with the
    whole call as a bare expression statement. ``FORWARDED`` means the record
    flows onward as a value (an argument, a subscript, a return) and this
    reader declines to judge it.

    WHAT THIS DOES NOT REACH, stated because a guard whose reach is unstated is
    a guard nobody can size:

    * A call whose result is SUBSCRIPTED or passed as an argument is
      ``FORWARDED``. ``_sha256_file(p)[:2]`` really does drop the flag and this
      classifier does not say so — measured, not supposed.
    * An INDIRECT call is invisible: the walk keys on ``ast.Name`` function
      ids, so ``counter(path)`` in ``_bounded_evidence`` is not a site even
      though ``_count_jsonl`` and ``_count_lines`` are readers.
    * "Loaded somewhere in the same function" is not "published". A name read
      into a local nobody publishes reads as KEPT.

    Each limit is fail-OPEN, so this node is a ratchet over the shapes it is
    proven to refuse and not a completeness claim. The behavioural counterpart
    is ``test_a_prefix_digest_is_never_published_without_its_own_flag``, which
    reads the emitted packet rather than the source.
    """
    functions = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    loaded = {
        f.name: {
            n.id for n in ast.walk(f)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        }
        for f in functions
    }
    attributes = {
        f.name: {
            (n.value.id, n.attr) for n in ast.walk(f)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
        }
        for f in functions
    }

    # INNERMOST enclosing function per call. `ast.walk` from each function
    # would attribute a nested helper's calls to the parent as well, and the
    # same site would be judged twice under two names.
    home: dict[ast.Call, Any] = {}
    def descend(node: ast.AST, function: Any) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                else function
            )
            if isinstance(child, ast.Call):
                home[child] = function
            descend(child, inner)
    descend(tree, None)

    # A call BINDS only when it is the assignment's value, or a branch of an
    # `IfExp` value — `digest, size, flag = _sha256_file(p) if present else
    # (None, None, False)` is the shipped shape at two sites. Anything deeper
    # in the expression is forwarded, not bound.
    bound: dict[ast.Call, ast.expr] = {}
    thrown: set[ast.Call] = set()
    for statement in ast.walk(tree):
        if isinstance(statement, ast.Assign):
            candidates = [statement.value]
            if isinstance(statement.value, ast.IfExp):
                candidates = [statement.value.body, statement.value.orelse]
            for candidate in candidates:
                if isinstance(candidate, ast.Call):
                    bound[candidate] = statement.targets[0]
        elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            thrown.add(statement.value)

    sites: list[_ClipSite] = []
    for call, function in home.items():
        if function is None or not isinstance(call.func, ast.Name):
            continue
        if call.func.id not in readers:
            continue
        argument = ast.unparse(call.args[0]) if call.args else ""
        target = bound.get(call)
        for index, flag in readers[call.func.id].items():
            if call in thrown:
                sites.append(_ClipSite(call.func.id, call.lineno, function.name,
                                       argument, flag, "DISCARDED", "<statement>"))
            elif target is None:
                sites.append(_ClipSite(call.func.id, call.lineno, function.name,
                                       argument, flag, "FORWARDED", "<consumed whole>"))
            elif isinstance(target, ast.Tuple):
                if index >= len(target.elts):
                    sites.append(_ClipSite(call.func.id, call.lineno, function.name,
                                           argument, flag, "DISCARDED", "<absent>"))
                    continue
                element = target.elts[index]
                name = (
                    element.id if isinstance(element, ast.Name) else ast.unparse(element)
                )
                kind = "KEPT" if name in loaded[function.name] else "DISCARDED"
                sites.append(_ClipSite(call.func.id, call.lineno, function.name,
                                       argument, flag, kind, name))
            elif isinstance(target, ast.Name):
                kind = (
                    "KEPT"
                    if (target.id, flag) in attributes[function.name]
                    else "DISCARDED"
                )
                sites.append(_ClipSite(call.func.id, call.lineno, function.name,
                                       argument, flag, kind, f"{target.id}.{flag}"))
            else:
                sites.append(_ClipSite(call.func.id, call.lineno, function.name,
                                       argument, flag, "DISCARDED", ast.unparse(target)))
    return sorted(sites, key=lambda s: (s.lineno, s.flag))


def _uncovered_clip_sites(sites: list[_ClipSite]) -> list[_ClipSite]:
    """Discarded flag members with no sibling read of the SAME file and CAP.

    THE EXEMPTION, AND WHY IT IS KEYED ON THE CAP RATHER THAN ON THE FILE
    ALONE. ``_source_audit`` and ``_schema_audit`` really do discard
    ``_sha256_file``'s third member, and both are covered: each re-reads the
    SAME path through ``_read_text``/``_read_json``, which publish
    ``byte_truncated`` over the SAME ``MAX_EVIDENCE_BYTES``. Keyed on
    ``(function, argument)`` alone this exemption was MEASURED WRONG: a fresh
    site discarding ``record_truncated`` beside a kept ``byte_truncated`` on
    the same ``_read_jsonl`` result was exempted, and ``MAX_STREAM_RECORDS``
    went unreported. The cap comes from
    ``observer.TRUNCATION_BOUND_FLAGS``; a flag the registry does not declare
    keys on itself, which is the fail-CLOSED direction.

    The argument is compared AS SOURCE TEXT, so two spellings of one path do
    not exempt each other. That is noisy and fail-closed, in that order.
    """
    caps = dict(observer.TRUNCATION_BOUND_FLAGS)

    def cap_of(flag: str) -> str:
        bare = _flag_key(flag)
        return caps.get(bare, bare)

    kept = {
        (s.function, s.argument, cap_of(s.flag)) for s in sites if s.kind == "KEPT"
    }
    return [
        s for s in sites
        if s.kind == "DISCARDED"
        and (s.function, s.argument, cap_of(s.flag)) not in kept
    ]


#: Fresh clipping sites the guard MUST refuse, each a different shape from F2.
#: F2 was a three-tuple unpack of ``_sha256_file`` into a ``_``-prefixed
#: throwaway, under ``MAX_EVIDENCE_BYTES``, on a plane a decision reads.
_FRESH_UNFLAGGED_CLIPS: dict[str, str] = {
    # DIFFERENT READER, DIFFERENT BINDING FORM, DIFFERENT CAP. An attribute
    # discard off a NamedTuple bound whole, under MAX_STREAM_RECORDS, with a
    # sibling flag on the SAME result kept — the shape that first proved the
    # exemption was too loose.
    "attribute discard of record_truncated beside a kept byte_truncated": '''

def _fresh_records_plane(path: Path) -> dict[str, Any]:
    read = _read_jsonl(path)
    return {"count": len(read.records), "byte_truncated": read.byte_truncated}
''',
    # THE EXEMPTION'S NEAR TWIN: a discard whose sibling read is of a DIFFERENT
    # FILE. Syntactically identical to the two exempt shipped sites, so a
    # guard that exempted on syntax rather than on the argument would permit it.
    "discard whose covering sibling reads another file": '''

def _fresh_sibling_wrong_file(subject: Path, other: Path) -> dict[str, Any]:
    digest, _size, _byte_truncated = _sha256_file(subject)
    read = _read_text(other)
    return {"sha256": digest, "byte_truncated": read.byte_truncated}
''',
    # THE WHOLE RECORD THROWN AWAY as a bare expression statement — no target
    # at all, so a rule that inspected only assignment targets would never see
    # it.
    "clipping read issued as a bare statement": '''

def _fresh_statement_discard(path: Path) -> dict[str, Any]:
    _read_jsonl(path)
    return {"observation_status": UNMEASURED}
''',
}

#: Correct code in the SAME syntactic forms. A guard firing on the binding
#: shape rather than on the discard would redden here.
_BENIGN_FRESH_CLIPS: dict[str, str] = {
    "every flag on the result is read": '''

def _fresh_records_plane_ok(path: Path) -> dict[str, Any]:
    read = _read_jsonl(path)
    return {
        "count": len(read.records),
        "byte_truncated": read.byte_truncated,
        "record_truncated": read.record_truncated,
    }
''',
    "discard covered by a sibling read of the same file and cap": '''

def _fresh_sibling_ok(subject: Path) -> dict[str, Any]:
    digest, _size, _byte_truncated = _sha256_file(subject)
    read = _read_text(subject)
    return {"sha256": digest, "byte_truncated": read.byte_truncated}
''',
}


@pytest.mark.timeout(10)
def test_every_clipping_site_publishes_a_flag_or_is_covered_by_a_sibling_read():
    """The mirror of section 50: does every CLIP have a flag, not just vice versa.

    THE ARMS.

    * PERMITTING: on the shipped bytes no clipping site drops its flag
      uncovered. Without this arm every refusal below would be
      indistinguishable from a guard that cannot pass.
    * REFUSING, THE SHIPPED DEFECT, AT BOTH ITS REAL SITES: the third member of
      ``_sha256_file`` is rebound to a throwaway in ``_settings_provenance``
      and in ``_candidate_claim_plane`` — the two F2 sites — and each must be
      named. Driven against the source that shipped the bug rather than
      assumed to cover it.
    * REFUSING, THREE FRESH SHAPES, none of them F2's: see
      ``_FRESH_UNFLAGGED_CLIPS``. A different reader, a different binding form,
      a different cap, a near-twin of the exemption, and a call with no
      assignment target at all.
    * BENIGN CONTROLS: correct code in the same syntactic forms stays green, so
      the guard is measured to fire on the DISCARD and not on the syntax.
    * INSTRUMENT CONTROLS: the reader derivation and the site list are both
      non-empty, the derivation finds readers this test names nowhere, and the
      shipped source really does contain the two exempted discards — an
      exemption that never fires is an exemption nobody has tested.
    """
    source = OBSERVER_PATH.read_text(encoding="utf-8")
    shipped = ast.parse(source)
    # DERIVED FROM THE SHIPPED MODULE, always — the arms below append source,
    # and a snippet must not get to declare itself not-a-reader.
    readers = _clipping_readers(shipped, observer)

    # --- INSTRUMENT CONTROLS ON THE DERIVATION.
    assert len(readers) >= 4, readers
    assert {"_sha256_file", "_read_text", "_read_json", "_read_jsonl"} <= set(readers), (
        f"the derivation missed a known clipping reader: {sorted(readers)}"
    )
    assert readers["_sha256_file"] == {2: "byte_truncated"}, (
        "the positional member of _sha256_file must come from its `return`; "
        f"got {readers['_sha256_file']}"
    )
    assert readers["_read_jsonl"] == {1: "byte_truncated", 2: "record_truncated"}, (
        readers["_read_jsonl"]
    )
    # ...and the derivation reaches readers nothing in this test names, which
    # is the property that makes it catch the NEXT one.
    assert set(readers) - {
        "_sha256_file", "_read_text", "_read_json", "_read_jsonl"
    }, sorted(readers)

    sites = _clip_sites(shipped, readers)
    assert len(sites) >= 15, sites
    assert {s.kind for s in sites} >= {"KEPT", "DISCARDED"}, sorted(
        {s.kind for s in sites}
    )

    # --- CONTROL ON THE EXEMPTION: it must actually fire on the shipped bytes.
    # An exemption that never applies would let the permitting arm below pass
    # for the wrong reason.
    exempt = [
        s for s in sites
        if s.kind == "DISCARDED" and s not in _uncovered_clip_sites(sites)
    ]
    assert {s.function for s in exempt} == {"_source_audit", "_schema_audit"}, exempt

    # --- PERMITTING ARM.
    assert _uncovered_clip_sites(sites) == [], _uncovered_clip_sites(sites)

    # --- REFUSING ARM A: THE SHIPPED DEFECT, at both F2 sites, one at a time.
    f2_restorations = {
        "_settings_provenance": (
            "overlay_digest, _size, overlay_byte_truncated = "
            "_sha256_file(settings_overlay)",
            "overlay_digest, _size, _byte_truncated = _sha256_file(settings_overlay)",
        ),
        "_candidate_claim_plane": (
            "    digest, size, byte_truncated = (\n"
            "        _sha256_file(path) if present else (None, None, False)\n"
            "    )",
            "    digest, size, _byte_truncated = (\n"
            "        _sha256_file(path) if present else (None, None, False)\n"
            "    )",
        ),
    }
    for function, (fixed, broken) in f2_restorations.items():
        assert source.count(fixed) == 1, (
            f"the F2 fix at {function} moved; this arm is anchored to bytes "
            "that no longer exist and would pass vacuously"
        )
        reverted = _uncovered_clip_sites(
            _clip_sites(ast.parse(source.replace(fixed, broken)), readers)
        )
        assert [s.function for s in reverted] == [function], (function, reverted)

    # --- REFUSING ARM B: three fresh shapes, none of them F2's.
    for label, snippet in _FRESH_UNFLAGGED_CLIPS.items():
        refused = _uncovered_clip_sites(
            _clip_sites(ast.parse(source + snippet), readers)
        )
        assert refused, f"the guard PERMITTED an unflagged clip: {label}"

    # --- BENIGN CONTROLS: the same forms, written correctly.
    for label, snippet in _BENIGN_FRESH_CLIPS.items():
        permitted = _uncovered_clip_sites(
            _clip_sites(ast.parse(source + snippet), readers)
        )
        assert permitted == [], (
            f"the guard REFUSED correct code — it is firing on the binding "
            f"form rather than on the discard: {label}: {permitted}"
        )

    # --- THE DISCLOSED ESCAPE, SHIPPED BESIDE THE REFUSALS rather than
    # described. A clipping read whose result is SUBSCRIPTED drops the flag and
    # this guard does not say so, because the call is not an assignment value.
    # Pinned as a measurement so the reach cannot be over-read from the arms
    # above, and so a later widening has something to turn red.
    escape = '''

def _fresh_subscript_escape(subject: Path) -> dict[str, Any]:
    digest, size = _sha256_file(subject)[:2]
    return {"sha256": digest, "bytes": size}
'''
    escaped = _uncovered_clip_sites(_clip_sites(ast.parse(source + escape), readers))
    assert escaped == [], (
        "the subscript escape is now caught; delete this control and promote "
        "the snippet into _FRESH_UNFLAGGED_CLIPS"
    )


@pytest.mark.timeout(20)
def test_a_prefix_digest_is_never_published_without_its_own_flag(tmp_path):
    """The BEHAVIOURAL counterpart to the AST guard above: read the packet.

    Two published digests were computed by a reader that clips at
    ``MAX_EVIDENCE_BYTES`` and bound that reader's truncation member to a
    throwaway. Measured on the pre-fix bytes: an overlay of
    ``MAX_EVIDENCE_BYTES + 50,000`` yielded an ``overlay_sha256`` that is a
    PREFIX digest, published beside a ``byte_truncated`` that names
    ``settings-sources.json`` — a DIFFERENT FILE — and read ``False``, with the
    settings plane at ``OBSERVED``; and ``candidate_claim`` published
    ``sha256``/``bytes`` with no truncation field at all, the pair
    self-consistent and silently not the whole file.

    Both arms on both sites, and the SMALL cell is what makes the large one
    mean anything: a flag hard-wired to ``True`` would satisfy every refusal
    here and fail the permitting cells.
    """
    oversized = observer.MAX_EVIDENCE_BYTES + 50_000

    # --- SITE 1, THE SETTINGS OVERLAY, driven in process.
    small_overlay = tmp_path / "small.settings.json"
    small_overlay.write_bytes(SETTINGS_OVERLAY.read_bytes())
    big_overlay = tmp_path / "big.settings.json"
    big_overlay.write_bytes(b"x" * oversized)

    run_root = _make_run_root(tmp_path / "settings")
    sources = ["user", "project", "local"]

    small = observer._settings_provenance(run_root, small_overlay, sources)
    # --- PERMITTING CELL: the whole file fits, the flag is false, and the
    # published digest IS the whole-file digest a third party recomputes.
    assert small["overlay_byte_truncated"] is False, small
    assert small["overlay_sha256"] == hashlib.sha256(
        small_overlay.read_bytes()
    ).hexdigest()
    assert small["observation_status"] == "OBSERVED", small

    big = observer._settings_provenance(run_root, big_overlay, sources)
    # --- REFUSING CELL: the digest is a PREFIX, the flag says so, and the
    # plane refuses to call the read complete.
    assert big["overlay_byte_truncated"] is True, big
    assert big["overlay_sha256"] != hashlib.sha256(big_overlay.read_bytes()).hexdigest()
    assert big["overlay_sha256"] == hashlib.sha256(
        big_overlay.read_bytes()[: observer.MAX_EVIDENCE_BYTES]
    ).hexdigest(), "the flag must name the digest that was actually published"
    assert big["observation_status"] == "UNMEASURED", big
    # --- AND THE FLAG NAMES THE RIGHT FILE. The plane's other byte flag reads
    # `settings-sources.json`, which was not clipped; conflating the two is the
    # defect, so they must disagree here.
    assert big["byte_truncated"] is False, big
    assert small["byte_truncated"] is False, small

    # --- SITE 2, THE CANDIDATE CLAIM, a DIFFERENT PLANE that NO decision
    # reads. A fix scoped to "planes decisions read" would leave it uncovered.
    claim_root = _make_run_root(tmp_path / "claim")
    claim = claim_root / observer.EVIDENCE_CANDIDATE_CLAIM
    claim.write_bytes(b"y" * 128)
    small_claim = observer._candidate_claim_plane(claim_root)
    assert small_claim["byte_truncated"] is False, small_claim
    assert small_claim["sha256"] == hashlib.sha256(claim.read_bytes()).hexdigest()
    assert small_claim["bytes"] == 128, small_claim

    claim.write_bytes(b"y" * oversized)
    big_claim = observer._candidate_claim_plane(claim_root)
    assert big_claim["byte_truncated"] is True, big_claim
    assert big_claim["bytes"] == observer.MAX_EVIDENCE_BYTES, big_claim
    assert big_claim["sha256"] != hashlib.sha256(claim.read_bytes()).hexdigest()
    # ...and it stays UNREAD by reconcile, which is the whole reason it needs a
    # flag rather than a degraded status: no decision can speak for it.
    assert big_claim["read_by_reconcile"] is False, big_claim

    # --- THE FLAG REACHES THE EMITTED PACKET, through the CLI that CI runs,
    # and degrades exactly the decisions that declare the settings plane. In
    # process is not the copy that executes.
    emitted = _packet_from(
        OBSERVER_PATH, _make_run_root(tmp_path / "emitted")
    )
    assert emitted["observation"]["settings"]["overlay_byte_truncated"] is False
    assert "byte_truncated" in emitted["candidate_claim"], emitted["candidate_claim"]
    for decision_id in ("D06_SETTINGS_DIGEST_MATCH", "D07_SETTINGS_SOURCE_SET_EXACT"):
        assert _decision_of(emitted, decision_id)["observation_status"] == "OBSERVED"

    # --- REFUSING ARM ON THE EMITTED BYTES: flipping the published flag must
    # move a decision, or the flag is published and read by nobody — which is
    # exactly what section 50 refuses, asked here about the NEW field.
    observation = copy.deepcopy(emitted["observation"])
    baseline = json.dumps(observer.reconcile(copy.deepcopy(observation))["comparison"])
    observation["settings"]["overlay_byte_truncated"] = True
    assert json.dumps(observer.reconcile(observation)["comparison"]) != baseline, (
        "overlay_byte_truncated is published and no decision reads it"
    )


@pytest.mark.timeout(15)
def test_reconcile_degrades_a_non_mapping_plane_instead_of_crashing(tmp_path):
    """``reconcile()`` is PUBLIC and the module freezes; a caller who skips
    validation must get a degraded packet, not an ``AttributeError``.

    ``reconcile({"filesystem": ["a"]})`` raised ``AttributeError: 'list' object
    has no attribute 'get'``; the same for ``str`` and ``int``, while ``None``
    was already safe through the ``or {}`` idiom. Eight reads carried it — five
    top-level planes, ``filesystem.pre``/``post`` in ``reconcile`` itself, and
    the same nested pair again inside ``_private_root_entries``, reached
    through a different door.

    NOT REACHABLE FROM ANY SUPPORTED ENTRYPOINT, and that three-arm proof is
    recorded here rather than left in a review thread — it is the reason this
    is hardening and not a shipped-bug fix:

    * **Call site**: exactly one ``reconcile()`` call in the module, inside
      ``_cli``, fed only by ``capture()``. No CLI route reconciles a
      subject-authored packet.
    * **Producer**: every plane comes from a dict literal in ``capture`` or
      from a producer whose own return is a ``Dict``.
    * **Schema**: all twelve declared observation planes are ``type: object``,
      so ``jsonschema`` refuses a list plane.

    All three are DRIVEN below, not asserted, because a proof nobody re-runs
    decays into prose.
    """
    run_root = _make_run_root(tmp_path / "reconcile")
    observation = observer.capture(
        cwd=run_root,
        run_root=run_root,
        session_uuid=SESSION_UUID,
        settings_overlay=SETTINGS_OVERLAY,
        setting_sources=_canonical_setting_sources(),
        debug_file=run_root / "debug.log",
    )
    baseline = {
        d["decision_id"]: d["observation_status"]
        for d in observer.reconcile(copy.deepcopy(observation))["comparison"]["decisions"]
    }

    # --- PERMITTING ARM: untouched, every decision is OBSERVED. Without it
    # every refusal below would be indistinguishable from a reconcile that can
    # never report clean.
    assert set(baseline.values()) == {"OBSERVED"}, baseline

    def statuses(mutation) -> dict[str, str]:
        mutated = copy.deepcopy(observation)
        mutation(mutated)
        packet = observer.reconcile(mutated)
        return {
            d["decision_id"]: d["observation_status"]
            for d in packet["comparison"]["decisions"]
        }

    # --- REFUSING ARM: every crashing read, every non-mapping shape, and the
    # decisions that read the plane degrade while the others do not.
    reads = {
        "schema_audit": ("D01_SCHEMA_ROOT_CLOSED", "D02_SCHEMA_COMPOSED_CLOSED"),
        "source_audit": ("D03_NO_STATIC_PRODUCT_IMPORT", "D04_NO_DYNAMIC_PRODUCT_IMPORT"),
        "settings": ("D06_SETTINGS_DIGEST_MATCH", "D07_SETTINGS_SOURCE_SET_EXACT"),
        "hooks": ("D08_HOOK_TOOL_USE_ID_JOIN", "D09_HIDDEN_HOOK_NONZERO"),
        "filesystem": (
            "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS",
            "D11_NO_SILENT_CONTENT_CHANGE",
            "D12_MODE_OWNER_RECORDED_FAITHFULLY",
        ),
    }
    for plane, expected in reads.items():
        for shape in (["a"], "a", 7, 1.5, True):
            got = statuses(lambda doc, p=plane, s=shape: doc.__setitem__(p, s))
            degraded = tuple(sorted(k for k in got if got[k] != baseline[k]))
            assert degraded == tuple(sorted(expected)), (plane, shape, got)
            assert all(got[k] == "ERROR" for k in expected), (plane, shape, got)

    # --- REFUSING ARM, THE NESTED PAIR, A DIFFERENT SHAPE: `pre`/`post` sit
    # INSIDE a plane that is itself a perfectly good mapping declaring
    # OBSERVED, so a guard that only typed the top-level plane would permit it.
    for side in ("pre", "post"):
        for shape in (["a"], "a", 7):
            got = statuses(
                lambda doc, s=side, v=shape: doc["filesystem"].__setitem__(s, v)
            )
            assert set(
                got[k] for k in reads["filesystem"]
            ) == {"ERROR"}, (side, shape, got)

    # --- THE REFUSAL DOES NOT DEPEND ON `DECISION_EVIDENCE_PLANES`. Emptying a
    # decision's plane tuple was MEASURED to launder an unrankable status back
    # to OBSERVED through `_evidence_bounds`; the status computed at the plane
    # read is passed straight to `_decision`, so it survives that.
    original = dict(observer.DECISION_EVIDENCE_PLANES)
    try:
        observer.DECISION_EVIDENCE_PLANES["D11_NO_SILENT_CONTENT_CHANGE"] = ()
        got = statuses(lambda doc: doc.__setitem__("filesystem", ["a"]))
        assert got["D11_NO_SILENT_CONTENT_CHANGE"] == "ERROR", got
    finally:
        observer.DECISION_EVIDENCE_PLANES.clear()
        observer.DECISION_EVIDENCE_PLANES.update(original)

    # --- NEGATIVE CONTROL, A DIFFERENT SHAPE FROM THE BUG: `None` and an
    # ABSENT plane are NOT the same input as a list, and must keep their
    # existing answer — UNMEASURED, not ERROR. A fix that typed everything the
    # same way would fail here.
    for plane, expected in reads.items():
        for shape in (None, ...):
            got = statuses(
                lambda doc, p=plane, s=shape: (
                    doc.pop(p, None) if s is ... else doc.__setitem__(p, s)
                )
            )
            assert all(got[k] == "UNMEASURED" for k in expected), (plane, shape, got)

    # --- PROOF ARM 1, THE CALL SITE: one `reconcile()` call in the module, and
    # it is inside `_cli`. Measured by AST rather than by `grep`, which reports
    # the definition and the docstrings too.
    tree = ast.parse(OBSERVER_PATH.read_text(encoding="utf-8"))
    callers = [
        fn.name
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef)
        for call in ast.walk(fn)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "reconcile"
    ]
    assert callers == ["_cli"], callers

    # --- PROOF ARM 2, THE PRODUCER: every plane `capture` emits is a mapping,
    # and stays one against hostile evidence. Five shapes of `fs-inventory.json`
    # — the one document with the richest reader — all yield a dict plane.
    for label, document in (
        ("list", ["a"]), ("str", "a"), ("int", 7), ("null", None),
        ("mixed", {"pre": ["a"], "post": 7, "declared_writable_roots": "x"}),
    ):
        hostile_root = _make_run_root(tmp_path / f"hostile-{label}")
        (hostile_root / observer.EVIDENCE_FS_INVENTORY).write_text(
            json.dumps(document), encoding="utf-8"
        )
        hostile = observer.capture(
            cwd=hostile_root,
            run_root=hostile_root,
            session_uuid=SESSION_UUID,
            settings_overlay=SETTINGS_OVERLAY,
            setting_sources=_canonical_setting_sources(),
            debug_file=hostile_root / "debug.log",
        )
        assert isinstance(hostile["filesystem"], dict), (label, hostile["filesystem"])
        assert hostile["filesystem"]["observation_status"] in ("ERROR", "UNMEASURED"), (
            label, hostile["filesystem"]["observation_status"]
        )
        # ...and it survives reconcile, which is the composition CI runs.
        observer.reconcile(hostile)

    # --- PROOF ARM 3, THE SCHEMA: every declared observation plane is typed
    # `object`, so the external oracle refuses a list plane. Counted against a
    # zero-error control so "the oracle said something" cannot stand in for
    # "the oracle said this".
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    clean = json.loads((VALID_DIR / "packet.json").read_text(encoding="utf-8"))
    assert list(validator.iter_errors(clean)) == []
    planes = sorted(clean["observation"])
    assert len(planes) >= 12, planes
    for plane in planes:
        broken = copy.deepcopy(clean)
        broken["observation"][plane] = ["a"]
        assert len(list(validator.iter_errors(broken))) >= 1, plane


# ==========================================================================
# 51 — THE FOUR REPRODUCED FAIL-OPENS, each driven both ways. 15s each: a
#      handful of `capture`/`reconcile` pairs over rewritten evidence files.
# ==========================================================================


def _packet_with(tmp_path: Path, label: str, name: str, writer, document: Any) -> dict[str, Any]:
    """One production packet over a run root whose ``name`` carries ``document``."""
    run_root = _make_run_root(tmp_path / label)
    writer(run_root / name, document)
    return json.loads(_production_packet(run_root))


@pytest.mark.timeout(15)
def test_a_stream_record_cannot_leave_the_hook_join_by_retyping_its_own_type(tmp_path):
    """R1: the discriminator is rendered and counted, not silently declined.

    THE MEASUREMENT. A ghost ``hook_event`` with no debug receipt is named by
    D09 and forces UNMEASURED. Recording the SAME record's ``type`` as
    ``["hook_event"]`` or ``7`` used to drop it through a bare ``continue``
    before any membership test: D09 recomputed zero discrepancies,
    ``hook_events_without_receipt`` was empty, ``unparsable_records`` stayed 0
    and the hooks plane reported OBSERVED. The identical door dropped an orphan
    ``tool_use`` out of D08. The rendering had been applied to ``tool_use_id``
    and ``outcome`` — the two fields the reported bug used — and not to the
    discriminator beside them in the same loop.

    THE NEGATIVE CONTROL IS A DIFFERENT SHAPE, deliberately. A record whose
    ``type`` is a STRING naming another record kind is a correct decline, not a
    defeat, and a guard that refused it would be paid off by being deleted. It
    must NOT degrade the plane — and it must still MOVE A NUMBER, because a
    decline that moves nothing in the packet is invisible to a third party
    recomputing from the same bytes.
    """
    clean = _read_jsonl_fixture(observer.EVIDENCE_STREAM)
    ghost = {"type": "hook_event", "tool_use_id": "toolu_GHOST", "hook_event_name": "PreToolUse"}
    orphan = {"type": "tool_use", "tool_use_id": "toolu_ORPHAN", "name": "Bash", "outcome": "success"}

    def hooks_and(label: str, records: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        packet = _packet_with(tmp_path, label, observer.EVIDENCE_STREAM, _write_jsonl, records)
        return packet["observation"]["hooks"], _decisions_by_id(json.dumps(packet))

    # --- PERMITTING ARM: the clean corpus. Nothing unrankable, plane OBSERVED,
    # and the two non-lifecycle records the fixture really carries are counted.
    base_hooks, base_decisions = hooks_and("clean", clean)
    assert base_hooks["unrankable_record_types"] == []
    assert base_hooks["observation_status"] == "OBSERVED"
    assert base_hooks["non_lifecycle_record_count"] == 2, base_hooks
    assert base_decisions["D08_HOOK_TOOL_USE_ID_JOIN"]["discrepancy_count"] == 0
    assert base_decisions["D09_HIDDEN_HOOK_NONZERO"]["discrepancy_count"] == 0

    # --- POSITIVE CONTROL: with a STRING discriminator the violations are
    # named. Without this the refusals below would be about a corpus that
    # never carried a violation.
    named_hooks, named_decisions = hooks_and("named", clean + [ghost, orphan])
    assert named_hooks["hook_events_without_receipt"] == ["toolu_GHOST"]
    # The ghost is an orphan too: the symmetric difference is over the UNION of
    # the lifecycle sets, and a stream `hook_event` with no matching `tool_use`
    # sits on the other side of it.
    assert named_hooks["orphan_tool_use_ids"] == ["toolu_GHOST", "toolu_ORPHAN"]
    assert named_decisions["D09_HIDDEN_HOOK_NONZERO"]["discrepancy_count"] >= 1
    assert named_decisions["D08_HOOK_TOOL_USE_ID_JOIN"]["discrepancy_count"] >= 1

    # --- REFUSING ARM: every retyping of the discriminator. The record no
    # longer joins — it cannot, the vocabulary is written in strings — but it
    # is NAMED on both decisions and the plane refuses to call itself
    # OBSERVED. Driven over several Python types so the answer is not about
    # one of them.
    for retyped in (["hook_event"], 7, {"kind": "hook_event"}, None, 7.0, True):
        hooks, decisions = hooks_and(
            f"retyped_{type(retyped).__name__}_{retyped!r}"[:40].replace("/", "_"),
            clean + [dict(ghost, type=retyped), dict(orphan, type=retyped)],
        )
        assert hooks["observation_status"] == "UNMEASURED", (retyped, hooks)
        assert len(hooks["unrankable_record_types"]) == 2, (retyped, hooks)
        assert decisions["D08_HOOK_TOOL_USE_ID_JOIN"]["discrepancy_count"] >= 2, retyped
        assert decisions["D09_HIDDEN_HOOK_NONZERO"]["discrepancy_count"] >= 2, retyped
        assert decisions["D09_HIDDEN_HOOK_NONZERO"]["observation_status"] != "OBSERVED"

    # --- NEGATIVE CONTROL, A DIFFERENT SHAPE: a string type outside the
    # vocabulary is a correct decline. The plane stays OBSERVED and nothing is
    # named — and the count still moves, so the decline is visible.
    declined_hooks, declined_decisions = hooks_and(
        "declined", clean + [dict(ghost, type="Hook_Event")]
    )
    assert declined_hooks["unrankable_record_types"] == []
    assert declined_hooks["observation_status"] == "OBSERVED"
    assert declined_hooks["non_lifecycle_record_count"] == 3, declined_hooks
    assert declined_decisions["D09_HIDDEN_HOOK_NONZERO"]["discrepancy_count"] == 0
    assert (
        declined_hooks["non_lifecycle_record_count"]
        != base_hooks["non_lifecycle_record_count"]
    ), "a declined record moved nothing in the packet"


@pytest.mark.timeout(15)
def test_a_coerced_path_list_element_is_declared_instead_of_disappearing(tmp_path):
    """S2: ``[str(p) for p in raw]`` reshapes the subject and must say so.

    THE MEASUREMENT. ``legacy_absolute_paths: [5]`` and ``["5"]`` are two
    different subject documents and both emitted ``["5"]`` — with the run root
    neutralised, a byte-identical packet. So did ``[true]`` and ``["True"]``.
    No decision reads this list, so nothing was masked; what was false is the
    packet's own claim to be a recomputable record of the subject's bytes.
    ``normalize`` already declared its four scalar coercions through the
    status channel; these two list sites were skipped.

    THE NEGATIVE CONTROL IS THE SIBLING FIELD, which is a different shape: the
    same coercion at ``declared_writable_roots``, whose value DOES feed D10 and
    D11, so a fix scoped to the field that masks nothing would not satisfy it.
    """
    inventory = json.loads(
        (VALID_DIR / observer.EVIDENCE_FS_INVENTORY).read_text(encoding="utf-8")
    )

    def filesystem_for(label: str, field: str, value: Any) -> dict[str, Any]:
        document = copy.deepcopy(inventory)
        document[field] = value
        packet = _packet_with(
            tmp_path, label, observer.EVIDENCE_FS_INVENTORY, _write_json, document
        )
        return packet["observation"]["filesystem"]

    # --- PERMITTING ARM: a list of real strings is not a coercion and does not
    # degrade. A guard that degraded here would be paid off by deletion.
    clean = filesystem_for("clean", "legacy_absolute_paths", ["/tmp/one", "/tmp/two"])
    assert clean["observation_status"] == "OBSERVED", clean
    assert clean["legacy_absolute_paths"] == ["/tmp/one", "/tmp/two"]

    # --- REFUSING ARM: the two pairs that were byte-identical are now
    # separable, and separable BY THE DEGRADATION rather than by luck.
    for label, raw in (("int", [5]), ("bool", [True]), ("null", [None]), ("list", [["/x"]])):
        degraded = filesystem_for(f"legacy_{label}", "legacy_absolute_paths", raw)
        assert degraded["observation_status"] == "UNMEASURED", (raw, degraded)

    coerced_int = filesystem_for("pair_int", "legacy_absolute_paths", [5])
    string_five = filesystem_for("pair_str", "legacy_absolute_paths", ["5"])
    assert coerced_int["legacy_absolute_paths"] == string_five["legacy_absolute_paths"] == ["5"]
    assert coerced_int != string_five, (
        "[5] and ['5'] still produce the same filesystem plane; the coercion "
        "is undeclared and the packet misrepresents the subject's bytes"
    )

    # --- NEGATIVE CONTROL, THE SIBLING FIELD AND A DIFFERENT CONSUMER.
    roots_clean = filesystem_for("roots_clean", "declared_writable_roots", ["/proof/root"])
    assert roots_clean["observation_status"] == "OBSERVED", roots_clean
    roots_coerced = filesystem_for("roots_int", "declared_writable_roots", [5])
    assert roots_coerced["observation_status"] == "UNMEASURED", roots_coerced


@pytest.mark.timeout(15)
def test_an_unreadable_receipt_number_degrades_the_debug_plane_instead_of_the_run(tmp_path):
    """N3: a subject-induced reader defeat is attributed to the evidence.

    ``int(match.group("exit"))`` raises ``ValueError`` past CPython's
    4300-digit conversion limit, so a receipt recording a 5,000-digit exit code
    aborted ``capture()`` and produced ZERO packet bytes — and ``_cli`` then
    reported that on the arm reserved for ARGV refusals, attributing a defeat
    caused by the subject's evidence to the operator who ran the command. Both
    behaviours are fail-CLOSED; only one of them is attributed correctly, and
    only one of them leaves a packet to inspect.

    The negative control is a different shape: an ordinary large-but-readable
    exit code, which must be read as the non-zero it is rather than swept into
    the same malformed channel.
    """
    lines = (VALID_DIR / "debug.log").read_text(encoding="utf-8").splitlines()
    receipt = (
        "[2026-09-07T09:15:05.000Z] [DEBUG] hook PreToolUse tool_use_id=toolu_01AAA "
        "command=claude-observer-canary exit={0} stdout_bytes=0"
    )

    def packet_with_receipt(label: str, exit_text: str) -> dict[str, Any]:
        run_root = _make_run_root(tmp_path / label)
        (run_root / "debug.log").write_text(
            "\n".join(lines + [receipt.format(exit_text)]) + "\n", encoding="utf-8"
        )
        return json.loads(_production_packet(run_root))

    # --- REFUSING ARM: the packet EXISTS, the debug plane says it was
    # defeated, and D09 inherits ERROR.
    oversized = packet_with_receipt("oversized", "9" * 5000)
    debug_plane = oversized["observation"]["debug"]
    assert debug_plane["unparsable_records"] >= 1, debug_plane
    assert debug_plane["observation_status"] == "ERROR", debug_plane
    decisions = _decisions_by_id(json.dumps(oversized))
    assert decisions["D09_HIDDEN_HOOK_NONZERO"]["observation_status"] == "ERROR"

    # --- PERMITTING ARM / NEGATIVE CONTROL OF A DIFFERENT SHAPE: a large exit
    # code that IS readable is read, named as non-zero, and does NOT reach the
    # malformed channel.
    readable = packet_with_receipt("readable", "9" * 100)
    readable_debug = readable["observation"]["debug"]
    assert readable_debug["unparsable_records"] == 0, readable_debug
    readable_decisions = _decisions_by_id(json.dumps(readable))
    assert readable_decisions["D09_HIDDEN_HOOK_NONZERO"]["discrepancy_count"] >= 1
    assert readable_decisions["D09_HIDDEN_HOOK_NONZERO"]["observation_status"] != "ERROR"


# ==========================================================================
# 52 — THE STDLIB SCHEMA WALK REACHES AN ARRAY AT AN OBJECT-TYPED NODE.
#      10s: four small audits plus the same four through `jsonschema`.
# ==========================================================================


@pytest.mark.timeout(10)
def test_an_undeclared_field_wrapped_in_an_array_is_not_invisible_to_the_walk(tmp_path):
    """The two schema planes must agree, and they did not.

    ``_walk_document``'s list branch descended only through
    ``resolved.get("items")``, which is ``None`` for a node typed ``object``.
    So a candidate could hide an undeclared field by wrapping the object that
    carries it in a one-element array: ``jsonschema`` still reported the
    packet, the observer's own stdlib walk reported nothing, and D01/D02 —
    which read the walk, not the oracle — recomputed clean. The oracle is a
    self-test fixture; the walk is what ships in the packet.

    THE PERMITTING ARM IS THE SHAPE THAT MUST STAY LEGAL, and it is a
    different shape from the refusal: ``recorded_settings_entry`` admits
    ``array`` in its own type union with no ``items``, so arbitrary content
    there is legal by construction. A fix that descended into every array
    would invent findings the oracle does not share — trading one disagreement
    between the planes for another.
    """

    def audited(document: Any, label: str) -> tuple[list[str], int]:
        packet_path = tmp_path / f"{label}.json"
        packet_path.write_text(json.dumps(document), encoding="utf-8")
        audit = observer._schema_audit(SCHEMA_PATH, packet_path)
        walk = list(audit["root_unknown_fields"]) + list(audit["composed_unknown_fields"])
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        oracle = list(jsonschema.Draft202012Validator(schema).iter_errors(document))
        return walk, len(oracle)

    base = json.loads((VALID_DIR / "packet.json").read_text(encoding="utf-8"))
    entry_map = base["observation"]["filesystem"]["pre"]["entries"]
    entry_key = sorted(entry_map)[0]

    # --- NEGATIVE CONTROL: both planes are quiet on the shipped packet.
    assert audited(base, "clean") == ([], 0)

    # --- POSITIVE CONTROL of both instruments: a plain undeclared field.
    plain = copy.deepcopy(base)
    plain["observation"]["filesystem"]["pre"]["entries"][entry_key]["zzz"] = 1
    plain_walk, plain_oracle = audited(plain, "plain")
    assert plain_walk and plain_oracle >= 1, (plain_walk, plain_oracle)

    # --- REFUSING ARM: the same field, wrapped. Both planes must see it.
    wrapped = copy.deepcopy(base)
    wrapped["observation"]["filesystem"]["pre"]["entries"][entry_key] = [
        dict(entry_map[entry_key], zzz=1)
    ]
    wrapped_walk, wrapped_oracle = audited(wrapped, "wrapped")
    assert wrapped_oracle >= 1, "the oracle stopped seeing it; this control is dead"
    assert any(problem.endswith("/zzz") for problem in wrapped_walk), wrapped_walk

    # --- PERMITTING ARM, A DIFFERENT SHAPE: a node whose union admits `array`.
    legal = copy.deepcopy(base)
    legal["observation"]["settings"]["declared"] = [[{"anything_at_all": 1}]]
    legal_walk, legal_oracle = audited(legal, "legal")
    assert (legal_walk, legal_oracle) == ([], 0), (legal_walk, legal_oracle)


# ==========================================================================
# 51 — the receipt join is a MULTISET, and the residue counts DECISIONS.
#      20s: in-process sweeps plus one production-route cell per test.
# ==========================================================================


@pytest.mark.timeout(20)
def test_a_missing_receipt_is_named_for_every_multiplicity_of_one_event(tmp_path):
    """A SET DIFFERENCE cannot express "two events, one receipt". For any N.

    THE CATEGORY, not the instance. This comparison has been "fixed" three
    times and every fix moved the KEY — bare ``tool_use_id``, then
    ``(tool_use_id, hook_event_name)``, then the pair again — while the KIND of
    comparison stayed a set difference. ``{(T,Pre)} - {(T,Pre)}`` is empty
    however many times each side wrote it, so the ordinary settings shape (TWO
    hooks both registered on ``PreToolUse`` for ONE tool call) absorbed the
    deletion of one of its two receipts exactly as the bare-id set had absorbed
    a ``PostToolUse``. The reproduced packet was byte-identical, decision for
    decision, to a clean run carrying one event and one receipt.

    THE SWEEP IS OVER N, so "it works for two" cannot pass for the invariant.
    For every N in 2..5 the same id and the SAME event name appears N times in
    the stream against N-1 receipts, and each cell must name the deficit
    exactly once. A guard keyed on distinct pairs passes every one of them.
    """
    call = {"type": "tool_use", "tool_use_id": "toolu_01AAA", "outcome": "success"}
    event = {
        "type": "hook_event",
        "tool_use_id": "toolu_01AAA",
        "hook_event_name": "PreToolUse",
    }
    receipt = (
        "[2026-09-07T09:15:02.481Z] [DEBUG] hook PreToolUse "
        "tool_use_id=toolu_01AAA command=claude-observer-canary exit=0 "
        "stdout_bytes=0"
    )

    def plane(label: str, events: int, receipts: int) -> dict[str, Any]:
        """The hooks plane, in process, over N events and M receipts."""
        run_root = tmp_path / label
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / observer.EVIDENCE_STREAM).write_text(
            "".join(json.dumps(r) + "\n" for r in [call] + [dict(event)] * events),
            encoding="utf-8",
        )
        debug = run_root / "debug.log"
        debug.write_text("\n".join([receipt] * receipts) + "\n", encoding="utf-8")
        return observer._hook_lifecycle(run_root, debug)

    # --- PERMITTING ARM, swept over the SAME N: counts agree at every
    # multiplicity and nothing is named. Without this the refusals below would
    # be satisfied by a comparison that reports every repeated pair.
    for count in range(1, 6):
        balanced = plane(f"balanced-{count}", count, count)
        assert balanced["hook_events_without_receipt"] == [], (count, balanced)
        assert balanced["receipts_without_hook_event"] == [], (count, balanced)
        assert balanced["observation_status"] == "OBSERVED", (count, balanced)

    # --- REFUSING ARM: N events, N-1 receipts, for every N. The deficit is
    # named ONCE — the multiplicity survives into the published list rather
    # than collapsing to a membership answer.
    for count in range(2, 6):
        short = plane(f"short-{count}", count, count - 1)
        assert short["hook_events_without_receipt"] == ["toolu_01AAA"], (count, short)
        d09 = _decision_of(observer.reconcile({"hooks": short}), "D09_HIDDEN_HOOK_NONZERO")
        assert any("toolu_01AAA" in item for item in _receipt_notes(d09)), (count, d09)

    # --- THE DEFECT, STATED AS AN INEQUALITY: two events with one receipt must
    # not be the packet one event with one receipt produces. This is the cell
    # the three previous fixes all left equal.
    assert plane("two-one", 2, 1) != plane("one-one", 1, 1), (
        "THE DEFECT: a deleted receipt on a repeated (id, event) pair read "
        "exactly like a run that never carried the second event"
    )

    # --- REFUSING ARM B, A DIFFERENT SHAPE AND THE OPPOSITE DIRECTION: MORE
    # receipts than events. A one-directional difference calls this clean, so a
    # subject can delete stream records instead of receipts and reach the same
    # silence through the other door.
    surplus = plane("surplus", 1, 3)
    assert surplus["hook_events_without_receipt"] == [], surplus
    assert surplus["receipts_without_hook_event"] == ["toolu_01AAA"] * 2, surplus
    surplus_d09 = _decision_of(
        observer.reconcile({"hooks": surplus}), "D09_HIDDEN_HOOK_NONZERO"
    )
    assert any(
        "no stream hook_event reports" in item for item in surplus_d09["discrepancies"]
    ), surplus_d09

    # --- THE PRODUCTION ROUTE, once: the same deficit through the observer CLI
    # over real bytes, so the sweep above cannot be green for an in-process
    # reason the shipped packet does not share.
    produced = _packet_with_stream_and_debug(
        tmp_path / "produced",
        [call, dict(event), dict(event)],
        [_DEBUG_HEAD, _DEBUG_SOURCES, receipt, _DEBUG_TAIL],
    )
    assert produced["observation"]["hooks"]["hook_events_without_receipt"] == [
        "toolu_01AAA"
    ], produced["observation"]["hooks"]
    produced_d09 = _decision_of(produced, "D09_HIDDEN_HOOK_NONZERO")
    assert produced_d09["observation_status"] == "UNMEASURED", produced_d09


@pytest.mark.timeout(20)
def test_a_second_exit_pair_on_a_receipt_line_is_accounted_in_both_directions(tmp_path):
    """The residue counted IDENTITIES while D09 decides on EXITS.

    Sound arithmetic over the wrong denominator. ``_DEBUG_HOOK_RE`` is
    greedy-left and stops at the first ``exit=``/``stdout_bytes=`` pair, and
    the claim was counted with ``tool_use_id=`` — which a merged second pair
    does not bring. So ``... command=c exit=0 stdout_bytes=0 exit=2
    stdout_bytes=0`` read ONE record, claimed ONE receipt, left residue ZERO,
    and produced a packet a third party's ``grep -o 'exit=[0-9]*'`` flatly
    contradicts. ``command=`` is written by the candidate into its own
    settings, so the shape is subject-authored (``ladder:282``).

    BOTH DIRECTIONS, because the hide and the forge are different failures.
    Hiding appends a non-zero pair behind a benign one and the packet reads
    clean; forging appends a benign pair behind a non-zero one and the packet
    reports a finding it cannot say is contradicted. Each has its own control.
    """
    head = (
        "[2026-09-07T09:15:02.481Z] [DEBUG] hook PreToolUse "
        "tool_use_id=toolu_01AAA command=claude-observer-canary"
    )
    clean = f"{head} exit=0 stdout_bytes=0"
    nonzero = f"{head} exit=2 stdout_bytes=0"
    hide = f"{head} exit=0 stdout_bytes=0 exit=2 stdout_bytes=0"
    forge = f"{head} exit=2 stdout_bytes=0 exit=0 stdout_bytes=0"

    def read(line: str) -> tuple[list[int], int]:
        records, lost = observer._debug_line_receipts(line)
        return [r["exit_code"] for r in records], lost

    def grep(line: str) -> list[str]:
        """The third-party recomputation, with an ordinary tool."""
        return re.findall(r"exit=-?\d+", line)

    # --- NEGATIVE CONTROL: one decision per line reads with no residue, and
    # the reader and `grep` agree. A residue that fired here would make every
    # refusal below meaningless.
    assert (read(clean), grep(clean)) == (([0], 0), ["exit=0"])
    assert (read(nonzero), grep(nonzero)) == (([2], 0), ["exit=2"])

    # --- REFUSING ARM A, THE HIDE. Two decisions on the line, one readable:
    # the unread one lands in the residue rather than vanishing.
    assert grep(hide) == ["exit=0", "exit=2"]
    assert read(hide) == ([0], 1), read(hide)

    # --- REFUSING ARM B, THE FORGE — the mirror image, and a DIFFERENT shape:
    # here the READ decision is the non-zero one and the hidden one is benign,
    # so a guard keyed on "did we lose something alarming" passes it.
    assert grep(forge) == ["exit=2", "exit=0"]
    assert read(forge) == ([2], 1), read(forge)

    # --- REFUSING ARM C, A THIRD SHAPE the identity channel cannot see either:
    # the word-boundary gap between the reader (`hook`, unbounded) and the
    # claim gate (`\bhook\b`). `prehook` is read by one and not claimed by the
    # other, so a claim gate with an unconditional veto would zero the residue
    # for the whole line. The claim is an OR with the reader's own match.
    prehook = (
        "[2026-09-07T09:15:02.481Z] [DEBUG] prehook PreToolUse "
        "tool_use_id=toolu_01AAA command=claude-observer-canary "
        "exit=0 stdout_bytes=0 exit=2 stdout_bytes=0"
    )
    assert observer._DEBUG_HOOK_RE.search(prehook) is not None, "the reader must match"
    assert not all(
        pattern.search(prehook) for pattern in observer._DEBUG_RECEIPT_SHAPE_RES
    ), "the shape gate must NOT claim it, or this arm is about something else"
    assert read(prehook) == ([0], 1), read(prehook)

    # --- PERMITTING ARM, A DIFFERENT SHAPE AGAIN: an ordinary log line that
    # mentions neither a receipt nor an exit is claimed by nothing. Widening
    # the claim gate until every line is a receipt line would satisfy every
    # refusal above and turn every real log ERROR.
    for benign in (_DEBUG_HEAD, _DEBUG_SOURCES, _DEBUG_TAIL, "hooks registry ready"):
        assert observer._debug_receipts_claimed(benign) == 0, benign
        assert read(benign) == ([], 0), benign

    # --- AND N WHOLE RECEIPTS ON ONE LINE STILL READ, for N up to four: the
    # residue must not fire on the shape the previous cycle closed.
    for count in range(1, 5):
        merged = " ".join(clean for _ in range(count))
        assert read(merged) == ([0] * count, 0), (count, read(merged))

    # --- THE PRODUCTION ROUTE: the hide, through the observer CLI. The
    # degraded packet must differ from the clean one, which is the property the
    # residue exists to produce.
    def d09_of(label: str, line: str) -> dict[str, Any]:
        return _decision_of(
            _packet_with_debug_lines(
                tmp_path / label,
                [_DEBUG_HEAD, _DEBUG_SOURCES, line,
                 clean.replace("toolu_01AAA", "toolu_02BBB"), _DEBUG_TAIL],
            ),
            "D09_HIDDEN_HOOK_NONZERO",
        )

    clean_d09 = d09_of("clean", clean)
    hide_d09 = d09_of("hide", hide)
    assert clean_d09["observation_status"] == "OBSERVED", clean_d09
    assert hide_d09["observation_status"] == "ERROR", hide_d09
    assert hide_d09 != clean_d09, (
        "THE DEFECT: a second exit decision merged onto a benign receipt read "
        "as a genuinely clean run"
    )


@pytest.mark.timeout(10)
def test_a_join_decision_contradicting_its_own_exit_evidence_is_not_believed():
    """``decision`` is a SIBLING of ``exit_code``, and D09 believed the sibling.

    THE CATEGORY: a field a decision reads must not be trustable on its own
    when the evidence it summarises sits on the same record. ``reconcile`` is
    PUBLIC and its packet is caller-supplied, so ``join["decision"]`` is a
    candidate-authored summary standing in for the measurement
    (``ladder:282``) — the same shape as parsing a candidate's own claim file.

    BOTH DIRECTIONS, over a REALISTIC FULL PACKET rather than a bare plane:
    ``decision`` saying success over ``exit_code`` 2 hid a non-zero exit, and
    ``decision`` saying ``NONZERO`` over ``exit_code`` 0 manufactured a finding
    out of a clean exit. The derived value decides in both, and the
    disagreement itself is named.
    """
    base = json.loads((VALID_DIR / "packet.json").read_text(encoding="utf-8"))["observation"]

    def d09(mutate: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        observation = copy.deepcopy(base)
        if mutate is not None:
            mutate(observation["hooks"]["joins"][0])
        return _decision_of(observer.reconcile(observation), "D09_HIDDEN_HOOK_NONZERO")

    # --- PERMITTING ARM: the shipped packet re-derives identically. An honest
    # packet must name nothing, or every refusal below is a plane-wide alarm.
    honest = d09()
    assert honest["observation_status"] == "OBSERVED", honest
    assert honest["discrepancies"] == [], honest

    # --- POSITIVE CONTROL: an HONEST non-zero — both fields agree — is named
    # as a non-zero exit and NOT as a contradiction.
    def real_nonzero(join: dict[str, Any]) -> None:
        join["exit_code"] = 2
        join["decision"] = "NONZERO"

    truthful = d09(real_nonzero)
    assert any("exited 2" in item for item in truthful["discrepancies"]), truthful
    assert not any("records decision" in item for item in truthful["discrepancies"]), (
        truthful
    )

    # --- REFUSING ARM A, THE HIDE: exit 2 with `decision` saying SILENT. The
    # exit must still be named, AND the contradiction must be named.
    hidden = d09(lambda join: join.__setitem__("exit_code", 2))
    assert any("exited 2" in item for item in hidden["discrepancies"]), hidden
    assert any("records decision 'SILENT'" in item for item in hidden["discrepancies"]), (
        hidden
    )
    assert hidden["observation_status"] == "UNMEASURED", hidden

    # --- REFUSING ARM B, THE FORGE, a DIFFERENT shape: `decision` claims
    # NONZERO over a clean exit 0. Believing the field would manufacture a
    # finding no byte of the log supports; the packet must say the two fields
    # disagree instead.
    forged = d09(lambda join: join.__setitem__("decision", "NONZERO"))
    assert not any("exited 0" in item for item in forged["discrepancies"]), forged
    assert any("records decision 'NONZERO'" in item for item in forged["discrepancies"]), (
        forged
    )
    assert forged["observation_status"] == "UNMEASURED", forged

    # --- REFUSING ARM C: exit evidence this reader cannot rank at all. `true`
    # is the trap — `isinstance(True, int)` and `True != 0` is False — so a
    # boolean exit would otherwise rank as a clean zero.
    for shape in (True, "2", None, [2], 1.5):
        unrankable = d09(lambda join, shape=shape: join.__setitem__("exit_code", shape))
        assert unrankable["observation_status"] == "UNMEASURED", (shape, unrankable)
        assert any(
            "no exit evidence this reader can rank" in item
            for item in unrankable["discrepancies"]
        ), (shape, unrankable)


@pytest.mark.timeout(10)
def test_every_sub_plane_read_degrades_a_hostile_shape_instead_of_raising():
    """The PLANE reads were hardened; the SUB-PLANE reads beside them were not.

    ``_plane_mapping`` covered the eight ``observation[<plane>]`` reads.
    The thirteen reads on the NEXT lines — ``schema_audit["static_findings"]``,
    ``hooks["joins"]``, ``filesystem["pre"]["entries"]`` and the rest — went
    through a bare ``.get(..., [])``, and twelve of the thirteen raised
    uncaught on ``["a"]``, ``"a"``, ``7``, ``1.5`` or ``True``: ``TypeError``
    from iterating an ``int`` and from ``set(7)``, ``AttributeError`` from
    ``7.get``, ``KeyError`` from a finding with no ``evidence``. ``reconcile``
    is PUBLIC, so a malformed packet is an INPUT: it must degrade, never raise,
    and never read clean.

    THE EVIDENCE IS NAMED, not merely non-crashing. Every cell asserts the
    field label reaches a discrepancy, so "it did not crash" cannot pass for
    "the loss is visible in the packet".
    """
    base = json.loads((VALID_DIR / "packet.json").read_text(encoding="utf-8"))["observation"]
    # TWO SHAPE SETS, because the two read kinds have different legal domains.
    # A container read is defeated by every scalar; a DENOMINATOR read is
    # defeated by every non-integer, and ``7`` is a legal count rather than a
    # hostile shape. ``True`` is hostile to BOTH: ``isinstance(True, int)`` is
    # True, so a recorded ``true`` would otherwise become the denominator 1.
    container_shapes = ("a", 7, 1.5, True)
    count_shapes = ("a", 1.5, True, ["a"])

    # (path into the observation, label the packet must name, decisions that
    # read it and must therefore be defeated by it, the shapes that defeat it)
    reads: tuple[tuple[tuple[str, ...], str, tuple[str, ...], tuple[Any, ...]], ...] = (
        (("schema_audit", "root_unknown_fields"), "schema_audit.root_unknown_fields",
         ("D01_SCHEMA_ROOT_CLOSED",), container_shapes),
        (("schema_audit", "composed_unknown_fields"), "schema_audit.composed_unknown_fields",
         ("D02_SCHEMA_COMPOSED_CLOSED",), container_shapes),
        (("schema_audit", "_examined"), "schema_audit._examined",
         ("D01_SCHEMA_ROOT_CLOSED", "D02_SCHEMA_COMPOSED_CLOSED"), count_shapes),
        (("source_audit", "static_findings"), "source_audit.static_findings",
         ("D03_NO_STATIC_PRODUCT_IMPORT",), container_shapes),
        (("source_audit", "_static_examined"), "source_audit._static_examined",
         ("D03_NO_STATIC_PRODUCT_IMPORT",), count_shapes),
        (("source_audit", "dynamic_findings"), "source_audit.dynamic_findings",
         ("D04_NO_DYNAMIC_PRODUCT_IMPORT",), container_shapes),
        (("source_audit", "runtime_findings"), "source_audit.runtime_findings",
         ("D04_NO_DYNAMIC_PRODUCT_IMPORT",), container_shapes),
        (("source_audit", "_dynamic_examined"), "source_audit._dynamic_examined",
         ("D04_NO_DYNAMIC_PRODUCT_IMPORT",), count_shapes),
        (("hooks", "joins"), "hooks.joins",
         ("D08_HOOK_TOOL_USE_ID_JOIN", "D09_HIDDEN_HOOK_NONZERO"), container_shapes),
        (("hooks", "orphan_tool_use_ids"), "hooks.orphan_tool_use_ids",
         ("D08_HOOK_TOOL_USE_ID_JOIN",), container_shapes),
        (("hooks", "unrankable_record_types"), "hooks.unrankable_record_types",
         ("D08_HOOK_TOOL_USE_ID_JOIN", "D09_HIDDEN_HOOK_NONZERO"), container_shapes),
        (("hooks", "_stream_id_count"), "hooks._stream_id_count",
         ("D08_HOOK_TOOL_USE_ID_JOIN",), count_shapes),
        (("hooks", "hook_events_without_receipt"), "hooks.hook_events_without_receipt",
         ("D09_HIDDEN_HOOK_NONZERO",), container_shapes),
        (("hooks", "receipts_without_hook_event"), "hooks.receipts_without_hook_event",
         ("D09_HIDDEN_HOOK_NONZERO",), container_shapes),
        (("filesystem", "declared_writable_roots"), "filesystem.declared_writable_roots",
         ("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS", "D11_NO_SILENT_CONTENT_CHANGE",
          "D12_MODE_OWNER_RECORDED_FAITHFULLY"), container_shapes),
        (("filesystem", "pre", "entries"), "filesystem.pre.entries",
         ("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS", "D11_NO_SILENT_CONTENT_CHANGE"),
         container_shapes),
        (("filesystem", "post", "entries"), "filesystem.post.entries",
         ("D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS", "D11_NO_SILENT_CONTENT_CHANGE"),
         container_shapes),
    )

    def recomputed(path: tuple[str, ...], value: Any) -> dict[str, Any]:
        observation = copy.deepcopy(base)
        node = observation
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        return observer.reconcile(observation)

    # --- NEGATIVE CONTROL: the shipped observation, unmutated. No decision is
    # ERROR, so the ERROR asserted below is caused by the shape and not by the
    # fixture. The four schema/source decisions are UNMEASURED here because the
    # published packet strips their private denominators.
    control = observer.reconcile(copy.deepcopy(base))
    control_status = {
        d["decision_id"]: d["observation_status"] for d in control["comparison"]["decisions"]
    }
    assert "ERROR" not in set(control_status.values()), control_status
    assert control["comparison"]["discrepancy_count"] == 0, control

    for path, label, decision_ids, shapes in reads:
        for shape in shapes:
            packet = recomputed(path, shape)  # must not raise
            named = {
                d["decision_id"]: d for d in packet["comparison"]["decisions"]
            }
            for decision_id in decision_ids:
                record = named[decision_id]
                assert record["observation_status"] == "ERROR", (
                    label, shape, decision_id, record
                )
                assert any(label in item for item in record["discrepancies"]), (
                    label, shape, decision_id, record
                )

    # --- A DIFFERENT SHAPE: a well-formed LIST or MAP whose MEMBERS are
    # hostile. The container walks, so nothing degrades on the container — the
    # member must be named instead of crashing the render.
    for path, label in (
        (("source_audit", "static_findings"), "source_audit.static_findings"),
        (("hooks", "joins"), "hooks.joins"),
    ):
        for member in ("a", 7, True, [1], {"no_evidence_key": 1}):
            packet = recomputed(path, [member])  # must not raise
            texts = [
                item
                for d in packet["comparison"]["decisions"]
                for item in d["discrepancies"]
            ]
            assert any(label in item for item in texts), (label, member, texts)

    # --- AND THE PAIR ONE LEVEL DOWN, whose entries are keyed by path: a
    # non-dict entry on both sides must be named, never compared as equal.
    packet = observer.reconcile(
        {
            **copy.deepcopy(base),
            "filesystem": {
                **copy.deepcopy(base)["filesystem"],
                "pre": {"entries": {"/outside/x": 7}, "observation_status": "OBSERVED"},
                "post": {"entries": {"/outside/x": 9}, "observation_status": "OBSERVED"},
            },
        }
    )
    d11 = _decision_of(packet, "D11_NO_SILENT_CONTENT_CHANGE")
    assert any("not a digest record on both sides" in item for item in d11["discrepancies"]), d11

    # --- AND THE VALUE DOMAIN OF A LEGAL TYPE, which every shape above
    # misses. The table's two shape sets are TYPE sets: they drive the reads
    # with values of the wrong type, and both guards this test was written
    # against test types. A value of the RIGHT type and the WRONG magnitude
    # clears every type test by short-circuit and reaches a C-level
    # conversion, where it raises out of `reconcile` — the docstring's "must
    # degrade, never raise" falsified by an input the table cannot express.
    #
    # `mode` is `stat.S_IMODE`, a C call over `unsigned int`. `-1`, `2**32`
    # and `2**64` each raised `OverflowError` — an `ArithmeticError`, so
    # outside `_cli`'s `except ValueError` — giving a traceback, exit 1 and
    # ZERO packet bytes on the arm reserved for a refused argv.
    private_root = base["filesystem"]["declared_writable_roots"][0]

    def with_mode(value: Any) -> dict[str, Any]:
        observation = copy.deepcopy(base)
        entries = observation["filesystem"]["pre"]["entries"]
        entries[private_root] = {**entries[private_root], "mode": value}
        return observer.reconcile(observation)

    # POSITIVE CONTROL: the two shapes the reported bug used are still named.
    # If these went quiet, the arms below would be green for the wrong reason.
    for legal_type_wrong_value in (33188, True, "384"):
        record = _decision_of(with_mode(legal_type_wrong_value), "D12_MODE_OWNER_RECORDED_FAITHFULLY")
        assert any("is not a stat.S_IMODE value" in item for item in record["discrepancies"]), (
            legal_type_wrong_value, record
        )

    # REFUSING ARM: three magnitudes, spanning both directions and both sides
    # of the 64-bit boundary, so a fix clamping one end would still be caught.
    for out_of_domain in (-1, 2 ** 32, 2 ** 64, -(2 ** 64)):
        record = _decision_of(with_mode(out_of_domain), "D12_MODE_OWNER_RECORDED_FAITHFULLY")
        assert any("is not a stat.S_IMODE value" in item for item in record["discrepancies"]), (
            out_of_domain, record
        )

    # PERMITTING CONTROL: the ceiling is a real edge, not a synonym for "any
    # int". The largest legal mode passes and one past it is named.
    at_ceiling = _decision_of(with_mode(0o7777), "D12_MODE_OWNER_RECORDED_FAITHFULLY")
    assert not any("is not a stat.S_IMODE value" in i for i in at_ceiling["discrepancies"]), at_ceiling
    past_ceiling = _decision_of(with_mode(0o7777 + 1), "D12_MODE_OWNER_RECORDED_FAITHFULLY")
    assert any("is not a stat.S_IMODE value" in i for i in past_ceiling["discrepancies"]), past_ceiling

    # --- THE SAME CLASS THROUGH A DIFFERENT DOOR: `_plane_bounds` descends
    # every dict at every depth by design, and coerces any `unparsable_records`
    # it meets with `int()` under `except (TypeError, ValueError)`.
    # `json.loads('{"x": Infinity}')` yields `inf` by default and inventory
    # entry values are subject-authored, so `int(inf)` raised `OverflowError`
    # straight past that tuple. An enumerated catch, where every arm sets the
    # same flag anyway.
    def with_count(value: Any) -> dict[str, Any]:
        observation = copy.deepcopy(base)
        entries = observation["filesystem"]["pre"]["entries"]
        entries[private_root] = {**entries[private_root], "unparsable_records": value}
        return observer.reconcile(observation)

    # THE SIGNAL READ HERE IS `evidence_bounds.malformed`, NOT
    # `observation_status`, and the change is a sharpening rather than a
    # weakening. `unparsable_records` is not a key `$defs/path_entry` declares,
    # so injecting it into an inventory entry is ALSO an undeclared-key finding
    # for `_path_entry_domain_problems` — which is correct, and which drives the
    # status to ERROR in every arm including the quiet ones. Reading the status
    # would therefore compare a constant with itself. `evidence_bounds.malformed`
    # is the operand `_plane_bounds` actually sets, and it still discriminates:
    # measured true for 5/inf/-inf/nan and false for 0/None. The injection stays
    # at ITS ORIGINAL DEPTH — inside `entries/*` — because the depth is the
    # point: `_plane_bounds` used to descend into `("pre", "post")` only.
    def _bounds_malformed(value: Any) -> bool:
        record = _decision_of(with_count(value), "D11_NO_SILENT_CONTENT_CHANGE")
        assert record["observation_status"] == "ERROR", (value, record)
        return bool(record["evidence_bounds"]["malformed"])

    # POSITIVE CONTROL: a plain positive count degrades, which is the
    # behaviour every arm below has to be indistinguishable from.
    assert _bounds_malformed(5) is True
    # The value that was ALREADY caught by the enumerated tuple, kept so the
    # widened catch is shown not to have changed it.
    assert _bounds_malformed(float("nan")) is True
    # REFUSING ARM: the values that escaped it.
    for escaping in (float("inf"), float("-inf")):
        assert _bounds_malformed(escaping) is True, escaping
    # PERMITTING CONTROL: zero and absence are not malformed, so the widened
    # catch did not turn every entry into an error.
    for quiet in (0, None):
        assert _bounds_malformed(quiet) is False, quiet


@pytest.mark.timeout(10)
def test_child_process_output_is_decoded_by_a_named_codec_not_the_ambient_locale(tmp_path):
    """``text=True`` with no ``encoding=`` made "never raise" false.

    ``subprocess.run(text=True)`` decodes with the LOCALE codec and
    ``errors="strict"``. ``UnicodeDecodeError`` is a ``ValueError``, so it
    escaped ``except (OSError, subprocess.SubprocessError)`` entirely: a git
    ref name is bytes and need not be valid UTF-8, and one such branch aborted
    the whole observation with zero packet bytes — which ``_cli`` then reported
    on the arm reserved for a refused argv, attributing a subject-induced
    reader defeat to the operator.

    The quieter half is DETERMINISM: an ambient locale means two operators
    decode identical child bytes differently and emit different
    ``git_snapshot`` bytes from identical repositories, in a module that names
    UTF-8 and ``errors="replace"`` for every file it reads.
    """
    # --- NEGATIVE CONTROL: ASCII output decodes to itself, so a green refusal
    # below cannot be "the runner is broken".
    assert observer._run_command(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'main')"]
    ) == (0, "main")

    # --- POSITIVE CONTROL OF THE INSTRUMENT: the bytes really are undecodable
    # as strict UTF-8, so the cell below is about the reader's handling of them
    # and not about a payload that happens to be legal.
    undecodable = b"br\x80nch"
    with pytest.raises(UnicodeDecodeError):
        undecodable.decode("utf-8")

    # --- REFUSING ARM: the same bytes through `_run_command`. It must RETURN,
    # keeping the undecodable byte visible as U+FFFD rather than raising a
    # ValueError past the `except` clause that claims to catch everything.
    code, text = observer._run_command(
        [sys.executable, "-c", r"import sys; sys.stdout.buffer.write(b'br\x80nch')"]
    )
    assert code == 0, (code, text)
    assert text == "br�nch", text

    # --- A DIFFERENT SHAPE: the codec is NAMED in the source, so the result
    # cannot depend on the operator's locale. Both subprocess call sites are
    # checked, because hardening one and leaving the sibling is the shape this
    # whole cycle is about.
    source = OBSERVER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]
    assert len(runs) == 2, f"the observer's subprocess.run call sites moved: {len(runs)}"
    for call in runs:
        keywords = {kw.arg for kw in call.keywords}
        assert {"encoding", "errors"} <= keywords, (
            f"subprocess.run at line {call.lineno} inherits the ambient locale codec"
        )

    # --- PERMITTING ARM: a real, ordinary command still answers normally, so
    # the hardening did not turn every child into a degraded read.
    code, text = observer._run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                       cwd=REPO_ROOT)
    assert code == 0 and text and "�" not in text, (code, text)


# ==========================================================================
# 53 — the residue's UNIT is the FILE, because the LINE is the SUBJECT's to
#      choose. 10s: one observer CLI run per case.
# ==========================================================================
#
# THE CLASS THIS COVERS: a guard whose unit is not the decision's unit. The
# previous rung moved the debug residue's KIND from identities to decisions and
# left its UNIT — the line — untouched, so the hidden value simply moved to the
# sibling carrier: the line boundary itself. ``str.splitlines()`` honours ten
# separators; ``grep`` and ``wc -l`` honour one. ``command=`` is written by the
# candidate into its own settings overlay (``ladder:282``), so a candidate that
# spells it ``c exit=0 stdout_bytes=0<SEP>pad`` hands ``splitlines()`` a
# syntactically perfect receipt on fragment one and drops the harness-written
# real ``exit=2`` onto fragment two, which claims nothing and is read by
# nobody.
#
# The oracle here is the RAW BYTES, deliberately unaware of Python's line
# semantics, cross-checked against real ``grep``. Two instruments, and a
# disagreement between them is reported rather than resolved in favour of
# whichever is convenient.

#: ``exit=`` decisions over raw bytes. NOT the observer's own
#: ``_DEBUG_RECEIPT_EXIT_RE``: a subject cannot be the oracle for its own
#: accounting, and this pattern is deliberately written against bytes so no
#: ``splitlines()`` semantics can reach it.
_RAW_EXIT_DECISION_RE = re.compile(rb"exit=-?[0-9]+")


def _exit_decisions_in_file(path: Path) -> int:
    """How many ``exit=`` decisions ``path`` carries, measured TWICE.

    A byte-level regex and an ordinary ``grep -oE`` must agree. ``grep`` is the
    instrument the finding was originally measured with, and the byte regex is
    the one that survives a runner without it; asserting they agree is what
    keeps either from being trusted alone.
    """
    raw = path.read_bytes()
    by_bytes = len(_RAW_EXIT_DECISION_RE.findall(raw))
    proc = subprocess.run(
        ["grep", "-aoE", "exit=-?[0-9]+", str(path)],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_S,
    )
    # 1 is grep's "no match", which is an answer, not a failure.
    assert proc.returncode in (0, 1), (proc.returncode, proc.stderr[-500:])
    by_grep = len([line for line in proc.stdout.splitlines() if line])
    assert by_bytes == by_grep, (
        f"the two instruments disagree about {path}: byte regex {by_bytes}, "
        f"grep {by_grep} — the disagreement is the finding"
    )
    return by_bytes


def _debug_receipt_line(tool_use_id: str, command: str, exit_code: int) -> str:
    """One ``[DEBUG] hook ...`` receipt in the shape the log writes them."""
    return (
        "[2026-09-07T09:15:05.000Z] [DEBUG] hook PreToolUse "
        f"tool_use_id={tool_use_id} command={command} "
        f"exit={exit_code} stdout_bytes=0"
    )


@pytest.mark.timeout(10)
def test_a_separator_the_candidate_writes_into_command_cannot_hide_a_hook_exit(tmp_path):
    """Every ``exit=`` decision in the FILE is accounted for, or the plane is ERROR.

    The reproduced defeat: with a separator inside ``command=``, D09 reported
    the SAME discrepancy count as the clean control on all five of ``\\n``,
    ``\\r``, ``\\v``, ``\\x85`` and ``\\u2028``, the debug plane stayed
    ``OBSERVED``, nothing was counted unparsable, and ``grep`` on the same
    bytes saw one more decision than the reader did.

    THE FIX IS AT THE FILE UNIT, not at the separator list. Enumerating the ten
    separators ``splitlines()`` honours today would be a guard scoped to the
    members of a set the standard library is free to grow — the failure this
    cycle keeps repeating. The whole file is asked instead, over the same
    ``exit=`` channel D09 decides on.
    """
    base = (VALID_DIR / "debug.log").read_text(encoding="utf-8")

    def observed(label: str, text: str) -> tuple[dict[str, Any], dict[str, Any], int]:
        run_root = _make_run_root(tmp_path / label)
        log = run_root / "debug.log"
        log.write_text(text, encoding="utf-8")
        packet = _packet_from(OBSERVER_PATH, run_root)
        return (
            _decision_of(packet, "D09_HIDDEN_HOOK_NONZERO"),
            packet["observation"]["debug"],
            _exit_decisions_in_file(log),
        )

    # --- INSTRUMENT CONTROL: the fixture the arms are built on carries the two
    # receipts it is supposed to, so a count of "one more" below is a real
    # increment rather than an artefact of an empty baseline.
    assert base.count("exit=") == 2, base

    # --- PERMITTING ARM 1: one ordinary clean receipt appended. Accounted, and
    # the plane says so.
    clean, clean_plane, clean_exits = observed(
        "clean", base + _debug_receipt_line("toolu_03CCC", "c", 0) + "\n"
    )
    assert clean_exits == 3, clean_exits
    assert clean_plane["unparsable_records"] == 0, clean_plane
    assert clean_plane["observation_status"] == "OBSERVED", clean_plane
    assert clean["observation_status"] != "ERROR", clean

    # --- PERMITTING ARM 2, THE ONE THAT MATTERS MOST: an HONEST non-zero exit,
    # on its own ordinary line. It must be NAMED on the discrepancy channel and
    # leave the plane OBSERVED. A fix that drove every non-zero log to ERROR
    # would pass every refusing arm below and destroy the decision.
    named, named_plane, named_exits = observed(
        "named", base + _debug_receipt_line("toolu_03CCC", "c", 2) + "\n"
    )
    assert named_exits == 3, named_exits
    assert named_plane["unparsable_records"] == 0, named_plane
    assert named_plane["observation_status"] == "OBSERVED", named_plane
    assert any("exited 2" in item for item in named["discrepancies"]), named
    assert named["discrepancy_count"] == clean["discrepancy_count"] + 1, (named, clean)

    # --- REFUSING ARM 1, THE REPRODUCER'S SHAPE: an ASCII carriage return
    # inside ``command=``. `\r` carries no newline byte at all, so `wc -l`
    # reports one line where `splitlines()` reports two.
    hidden_command = "c exit=0 stdout_bytes=0\rpad"
    cr, cr_plane, cr_exits = observed(
        "cr", base + _debug_receipt_line("toolu_03CCC", hidden_command, 2) + "\n"
    )
    assert cr_exits == 4, cr_exits
    # The NAMING channel is still defeated — that is the defect, unchanged and
    # unfixable at this layer, because fragment two supports no join identity.
    assert cr["discrepancy_count"] == clean["discrepancy_count"], (cr, clean)
    assert not any("exited 2" in item for item in cr["discrepancies"]), cr
    # The ACCOUNTING channel is what refuses: one decision no record and no
    # per-line residue explains.
    assert cr_plane["unparsable_records"] == 1, cr_plane
    assert cr_plane["observation_status"] == "ERROR", cr_plane
    assert cr["observation_status"] == "ERROR", cr

    # --- REFUSING ARM 2, A DIFFERENT SHAPE ON THREE AXES: a non-ASCII
    # separator (U+2028, which no C-locale tool treats as a line break), and a
    # hidden fragment carrying TWO decisions instead of one, so the count is
    # driven rather than merely non-zero.
    two_hidden = "c exit=0 stdout_bytes=0 pad exit=3 stdout_bytes=0"
    ls, ls_plane, ls_exits = observed(
        "linesep", base + _debug_receipt_line("toolu_03CCC", two_hidden, 2) + "\n"
    )
    assert ls_exits == 5, ls_exits
    assert ls_plane["unparsable_records"] == 2, ls_plane
    assert ls_plane["observation_status"] == "ERROR", ls_plane
    assert ls["observation_status"] == "ERROR", ls

    # --- DISCRIMINATION CONTROL: the SAME two receipts, split across two
    # ordinary newline-separated lines. This is what a legitimate log looks
    # like, and it must stay clean — otherwise the arms above would be green
    # because every multi-receipt log turned ERROR.
    honest = (
        base
        + _debug_receipt_line("toolu_03CCC", "c", 0) + "\n"
        + _debug_receipt_line("toolu_04DDD", "pad", 2) + "\n"
    )
    split, split_plane, split_exits = observed("honest", honest)
    assert split_exits == 4, split_exits
    assert split_plane["unparsable_records"] == 0, split_plane
    assert split_plane["observation_status"] == "OBSERVED", split_plane
    assert any("exited 2" in item for item in split["discrepancies"]), split

    # --- DISCRIMINATION CONTROL 2: a receipt whose fields are PERMUTED. The
    # per-line residue already claims it, so the file-level arithmetic must
    # subtract that claim and add nothing — a double count here would make
    # every previously-covered shape report twice.
    permuted = (
        "[2026-09-07T09:15:05.000Z] [DEBUG] hook PreToolUse command=c "
        "tool_use_id=toolu_05EEE exit=2 stdout_bytes=0"
    )
    perm, perm_plane, perm_exits = observed("permuted", base + permuted + "\n")
    assert perm_exits == 3, perm_exits
    assert perm_plane["unparsable_records"] == 1, perm_plane
    assert perm_plane["observation_status"] == "ERROR", perm_plane


# ==========================================================================
# 54 — a citation must be ANCHORED to something that survives an edit.
#      5s: two in-memory text scans.
# ==========================================================================
#
# Section 27 resolves every cited TEST NAME and section 34 pins every quoted
# NUMBER. Neither reads a citation written as a bare LINE NUMBER — the form
# ``:NNNN``, carrying digits and no file — and the frozen bytes carried four
# of them. All four were WRONG when measured. One pointed at observer line
# 3145, a docstring bullet in ``_settings_by_path`` about ``item["path"]``
# raising ``KeyError``, while its sentence described a ``TypeError`` from
# ``set(...)`` in ``reconcile``. Two more pointed at observer lines 588-590, a
# ``_EvidenceCount`` docstring, while their sentence named a rule stated in
# ``_is_declarable_root`` — the same wrong pointer, COPIED from the observer
# into this file. The fourth continued a ``ladder:282`` citation by eliding
# its file name, which reads as anchored only while the two stay adjacent.
#
# NOTE THE SELF-REFERENCE: none of the four can be QUOTED here, because this
# comment is inside the bytes the scan below reads. That is the property the
# guard needs, not an inconvenience — a rule the rule-file itself must obey.
#
# THE RATCHET DECISION, stated rather than implied. The obvious rule — "a
# citation must land inside the function the sentence names" — was measured
# against all four instances and is NOT tractable here. It requires reading
# which definition a sentence refers to, and the two correct targets do not
# share a mechanical property with the wrong ones: one is CODE in the citing
# function, the other is PROSE in a different function, and a third is in a
# different FILE. Any rule cheap enough to write would have refused a correct
# citation or permitted a wrong one, which is a decorative guard.
#
# WHAT IS SHIPPED INSTEAD REMOVES THE FORM. A line number in a file that is
# edited has no anchor: it is correct when typed and rots with nothing
# refusing, which is the whole class. A citation carrying a SYMBOL
# (:func:`x`, ``observer._is_declarable_root``) resolves and is permitted.
# Refusing a FORM is a category rather than a list of members.
#
# THE FORM REFUSED IS THE BARE ONE, and only it: a line number carrying no
# file part at all. A citation that NAMES its file is outside this ratchet --
# the file name is an anchor this scan can see, and the permitting control
# below drives one on the real bytes. Widening the refusal to every
# ``file:line`` citation was tried in review and withdrawn: that is a
# different policy, it fired on this test's own permitting control, and no
# instance of it was measured wrong on these bytes.
#
# THE PLAN DOCUMENTS are cited by BARE NAME (``amendment``, ``ladder``), so
# they carry a file part and are permitted by the same predicate as any other
# named file. They are additionally DIGEST-FROZEN in the manifest's
# ``frozen_authority``, so their line numbers cannot move without invalidating
# the manifest; the test asserts that separately, so if it ever stops being
# true the permission stops being justified loudly rather than quietly.
#
# TWO EXTRACTORS, UNIONED, because the two instances used different carriers:
# one single-backticked inside a ``#`` comment, one double-backticked inside a
# docstring. A third carrier -- no backticks at all -- is covered by the second
# extractor. Neither extractor may see a Python SLICE (``line[:200]``), which
# is the false positive that would make this guard pay for itself by being
# deleted.
#
# WHAT THE BARE EXTRACTOR ANCHORS ON, corrected. It previously REQUIRED the
# preceding character to be whitespace or ``(``, via a lookbehind. That is a
# membership list, not a category, and it made a citation at COLUMN 0 -- or one
# preceded by the em dash this file uses constantly -- invisible to BOTH
# extractors: the escape route was reachable, since this module's own docstring
# carries column-0 prose lines today. The anchor is now stated the other way
# round, as the characters that DENY a citation, so every character nobody
# thought of permits one.
#
# THE DENYING SET, each member measured rather than assumed:
#   ``\w`` -- a word character before the colon is the tail of a file name, so
#            the citation is NAMED and outside this ratchet.
#   ``[``, ``]`` -- the two slice brackets. ``line[:200]``, ``entries[1:9]``.
#   ``)``  -- ``line[len(x):200]`` is also a slice, and the version of this
#            anchor proposed in review flagged it. A guard that reddens on a
#            Python slice is the false positive named above.
#   ``"``, ``'`` -- a citation inside a quoted string is a synthetic operand,
#            and every currently-invisible token in these bytes is one. It is a
#            CORRECT decline; without these two, ``{"x":1}`` reads as a bare
#            citation.
#   a backtick -- that is the OTHER extractor's carrier. Each extractor owns
#            one carrier, which is what keeps the union measurably
#            non-redundant rather than one pattern with a spare; the control
#            below drives exactly that, in both directions.
#   ``.``, ``/``, ``-`` -- the rest of a file name's alphabet. A citation
#            preceded by one of them names a file too, whatever that file is
#            called, so it is outside this ratchet by the same predicate as a
#            word character.
#
# THE RESIDUE, stated rather than claimed away, two members and no universal:
#
#   1. A bare citation written straight after a member of the file-name
#      alphabet -- a full stop, a hyphen, a slash or a word character with no
#      space after it -- is DECLINED, because at that position the scan cannot
#      tell a bare citation from the tail of a named one. It is paid
#      deliberately in the false-negative direction and is not claimed to be
#      covered. No example can be written here: this comment is inside the
#      bytes the scan reads, which is the self-reference the section header
#      names.
#   2. A bare citation opened by a backtick that is never closed is seen by
#      NEITHER extractor: the bare one denies the backtick, and the backticked
#      one requires the closing delimiter. Also unchanged by this correction --
#      the previous lookbehind admitted neither whitespace nor ``(`` there --
#      and left standing rather than papered over, because closing it would
#      mean permitting the backtick and collapsing the two extractors into one.

#: A citation inside rst/markdown literal markers, in either width.
_BACKTICKED_CITATION_RE = re.compile(r"`{1,2}(?P<token>[^`\s]*:\d[\d,:-]*)`{1,2}")

#: A BARE citation -- a line number with NO file part -- carrying no markup,
#: recognised by what PRECEDES it: the start of the line, or any character
#: OUTSIDE the denying set argued above. The token group starts AT the colon,
#: so the engine cannot abandon a named citation and restart inside its file
#: name to report the remainder as bare. Stated as a denial rather than an
#: allow-list so an unforeseen preceding character permits the citation to be
#: seen instead of hiding it.
_BARE_CITATION_RE = re.compile("(?:^|[^\\w\\]\\[)'\"`./-])(?P<token>:\\d[\\d,:-]*)")


def _line_citations(line: str) -> list[str]:
    """Every ``<file>:<lines>`` citation token on ``line``, from both carriers."""
    return [
        match.group("token")
        for pattern in (_BACKTICKED_CITATION_RE, _BARE_CITATION_RE)
        for match in pattern.finditer(line)
    ]


def _unanchored_citation_errors(texts: dict[str, str]) -> list[str]:
    """Every citation whose line number carries NO file part to anchor it."""
    problems: list[str] = []
    for label in sorted(texts):
        for number, line in enumerate(texts[label].splitlines(), 1):
            for token in _line_citations(line):
                if token.split(":", 1)[0] == "":
                    problems.append(
                        f"{label}:{number}: cites {token} — a line number with "
                        "no file name is anchored to nothing and rots on the "
                        "next edit; name the file or the symbol"
                    )
    return problems


@pytest.mark.timeout(5)
def test_no_frozen_citation_points_at_a_bare_line_number():
    """Every citation in the frozen bytes is anchored to a file or a symbol.

    Every literal below is BUILT AT RUNTIME. A bare citation spelled out in
    this file would be read by the very scan it exercises — the same reason
    sections 27 and 34 build theirs.
    """
    texts = _frozen_citation_texts()
    colon = ":"

    # --- INSTRUMENT CONTROL 1: the extractors FIND citations on the shipped
    # bytes. A pattern that matched nothing would return no findings for every
    # input, and "no findings" is the answer this guard exists to make
    # trustworthy.
    found = [token for text in texts.values() for line in text.splitlines()
             for token in _line_citations(line)]
    assert len(found) >= 40, len(found)
    assert any(token.startswith("amendment" + colon) for token in found), sorted(set(found))
    assert any(token.startswith("ladder" + colon) for token in found), sorted(set(found))

    # --- INSTRUMENT CONTROL 2: the two extractors are NOT redundant. Each must
    # see a carrier the other cannot, or the union is decoration. Both operands
    # are BARE, because that is the only form either extractor is asked about
    # here; the carrier is what differs.
    backticked_only = "#: see ``" + colon + "282``\n"
    bare_only = "#: see " + colon + "282 for the rule\n"
    assert [m.group("token") for m in _BACKTICKED_CITATION_RE.finditer(bare_only)] == []
    assert [m.group("token") for m in _BARE_CITATION_RE.finditer(backticked_only)] == []
    assert _line_citations(backticked_only.strip()), backticked_only
    assert _line_citations(bare_only.strip()), bare_only

    # --- PERMITTING ARM: the shipped frozen bytes carry no unanchored
    # citation.
    assert _unanchored_citation_errors(texts) == [], (
        "\n".join(_unanchored_citation_errors(texts))
    )

    # --- CONTROL OF THAT ARM, on the REAL BYTES: strip the file name off one
    # real citation and exactly that line must be reported. This is what
    # separates a working scan from one that cannot fire on this file.
    node_key = str(NODE_FILE.relative_to(REPO_ROOT))
    anchored = "``" + "amendment" + colon + "208``"
    unanchored = "``" + colon + "208``"
    expected_line = next(
        number
        for number, line in enumerate(texts[node_key].splitlines(), 1)
        if anchored in line
    )
    mutated = dict(texts)
    mutated[node_key] = texts[node_key].replace(anchored, unanchored, 1)
    assert mutated[node_key] != texts[node_key], "the perturbation changed nothing"
    on_bytes = _unanchored_citation_errors(mutated)
    assert len(on_bytes) == 1, on_bytes
    assert on_bytes[0].startswith(f"{node_key}:{expected_line}" + colon), on_bytes

    # --- REFUSING ARM 1, THE REPRODUCER'S SHAPE: a single-backticked bare line
    # number inside a `#` comment, which is the carrier the observer's
    # pointer at line 3145 used.
    comment = "    # here, at `" + colon + "3145` in the frozen bytes, before\n"
    refused = _unanchored_citation_errors({"synthetic.py": comment})
    assert len(refused) == 1, refused
    assert refused[0].startswith("synthetic.py:1" + colon), refused

    # --- REFUSING ARM 2, A DIFFERENT SHAPE ON THREE AXES: a double-backticked
    # RANGE inside a docstring, on a line that ALSO carries a legitimate
    # anchored citation. A guard paid off by the anchored neighbour would read
    # this line clean.
    ranged = (
        '    """The rule at ``' + colon + '588-590`` restates '
        "``ladder" + colon + "282``.\n"
    )
    ranged_refused = _unanchored_citation_errors({"synthetic.py": ranged})
    assert len(ranged_refused) == 1, ranged_refused
    assert colon + "588-590" in ranged_refused[0], ranged_refused

    # --- REFUSING ARM 3, A DIFFERENT CARRIER: no markup at all, which the
    # backtick extractor alone cannot see. This is the arm that makes the union
    # load-bearing rather than belt-and-braces.
    unmarked = "    # the reason is given at " + colon + "1234 above\n"
    unmarked_refused = _unanchored_citation_errors({"synthetic.py": unmarked})
    assert len(unmarked_refused) == 1, unmarked_refused
    assert colon + "1234" in unmarked_refused[0], unmarked_refused

    # --- PERMITTING CONTROL: the shapes that must NOT fire. Slices are the
    # false positive that would get this guard deleted; anchored citations of
    # all three kinds are the thing it exists to leave alone.
    benign = (
        "    version = output.splitlines()[0][" + colon + "200]\n"
        "    tail = text[10" + colon + "200]\n"
        '    payload = {"count"' + colon + '200}\n'
        "    # standup at 09" + colon + "30 UTC\n"
        "    # see ``amendment" + colon + "178-188`` and ``ladder" + colon + "282``\n"
        "    # and tests/regression/test_ci_pytest_timeout.py" + colon + "938\n"
        "    # and :func:`_is_declarable_root`\n"
    )
    assert _unanchored_citation_errors({"benign.py": benign}) == [], (
        _unanchored_citation_errors({"benign.py": benign})
    )

    # --- REFUSING ARM 4, THE ANCHOR HOLE ITSELF: a citation at COLUMN 0. The
    # previous lookbehind REQUIRED a preceding whitespace or `(` character, and
    # column 0 has no preceding character at all, so this token was invisible
    # to both extractors. It is reachable in this corpus rather than
    # hypothetical: this module's own docstring carries column-0 prose lines.
    at_column_zero = colon + "1174 is where the read is unguarded\n"
    assert at_column_zero[0] == colon, "the arm did not start at column 0"
    column_zero_refused = _unanchored_citation_errors({"synthetic.py": at_column_zero})
    assert len(column_zero_refused) == 1, column_zero_refused
    assert colon + "1174" in column_zero_refused[0], column_zero_refused

    # --- REFUSING ARM 5, A DIFFERENT SHAPE: the same hole reached from the
    # other side — a preceding character that is neither whitespace nor `(`.
    # The em dash is the one this codebase writes constantly, so the escape
    # needed no unusual typography.
    em_dash = "    # the rule—" + colon + "3883—writes the packet\n"
    assert "—" + colon in em_dash, "the arm lost its em dash"
    em_dash_refused = _unanchored_citation_errors({"synthetic.py": em_dash})
    assert len(em_dash_refused) == 1, em_dash_refused
    assert colon + "3883" in em_dash_refused[0], em_dash_refused

    # --- PERMITTING CONTROL FOR THE WIDENED ANCHOR, a DIFFERENT shape from the
    # slices above: the two constructs the review-proposed anchor was MEASURED
    # flagging. Widening the anchor must not buy the escape route back at the
    # price of reddening on Python that means nothing of the kind.
    still_benign = (
        "    tail = line[len(x)" + colon + "200]\n"
        '    d = {"x"' + colon + "1}\n"
        "    probe = \"" + colon + "208\"\n"
        # RE-ANCHORING, the shape the widening created and the denying set
        # removed: an ANCHORED backticked citation whose file part ends in a
        # slash. With only word characters denied, the engine abandoned the
        # real token start and restarted at the slash, reporting the remainder
        # as bare on a line that names its file perfectly well.
        "    # see ``x/" + colon + "208`` for it\n"
    )
    assert _unanchored_citation_errors({"benign.py": still_benign}) == [], (
        _unanchored_citation_errors({"benign.py": still_benign})
    )

    # --- CONTROL OF THAT CONTROL: the three lines above decline because of
    # WHAT PRECEDES the colon, not because the token pattern cannot fire on
    # them at all. Replace each preceding character with one outside the
    # denying set and the identical remainder must be refused.
    for preceding in (")", '"', "'"):
        probe = "    x " + preceding + colon + "200\n"
        widened = "    x  " + colon + "200\n"
        assert _unanchored_citation_errors({"p.py": probe}) == [], preceding
        assert _unanchored_citation_errors({"p.py": widened}) != [], (
            "the token pattern cannot fire on this remainder at all, so the "
            "declines above prove nothing about the anchor"
        )


# ==========================================================================
# 55 — the P0-A step's "no bypass" property is a MECHANISM, not a paragraph.
#      5s: one YAML parse and in-memory mutations of it.
# ==========================================================================
#
# ci.yml declares in prose that the P0-A step carries "no continue-on-error,
# no ``|| true``, no ratchet", and that none of its five prerequisites carries
# continue-on-error either — the second claim explicitly labelled "verified by
# parsing this file". Nothing parsed it. Adding ``continue-on-error: true`` to
# the step, or deleting the ``!cancelled()`` half of its condition, left the
# node passing and nothing refusing. By INV-1 a gate declared only in prose is
# not enforcement, and this is the gate that gates the gate.
#
# THE PREREQUISITES ARE DERIVED FROM THE CONDITION, never listed here. A guard
# holding its own copy of the five names would go quiet the moment a sixth
# prerequisite is added — the same stale-second-list defect this rung has been
# closing everywhere else.
#
# WHY THE KEY AND NOT THE VALUE. ``continue-on-error: false`` is behaviourally
# identical to absence and is one character from ``true``, so a declared
# ``false`` carries no information that absence does not while offering a
# reviewer's eye something that looks deliberate. The KEY is refused on these
# steps; elsewhere in this workflow it stays permitted, and the discrimination
# control below proves this guard is bound to the P0-A step and its named
# prerequisites rather than to the file at large.

#: How the P0-A step names itself. Matched as a substring so the issue number
#: and the "(hard, ...)" suffix can change without the guard going blind.
P0A_STEP_MARKER = "P0-A"

#: The prerequisite form ci.yml's own comment mandates. ``outcome``, not
#: ``conclusion`` — the sibling guard in tests/regression/test_ci_pytest_timeout.py
#: rejects ``conclusion`` outright, and this pattern must not accept what that
#: one refuses.
_PREREQUISITE_OUTCOME_RE = re.compile(
    r"steps\.([A-Za-z0-9_-]+)\.outcome\s*!=\s*'failure'"
)


def _smoke_job_steps(document: Any) -> list[Any]:
    """The ``smoke`` job's step list, or the empty list if it is unreadable."""
    if not isinstance(document, dict):
        return []
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return []
    smoke = jobs.get("smoke")
    if not isinstance(smoke, dict):
        return []
    steps = smoke.get("steps")
    return steps if isinstance(steps, list) else []


def _p0a_run_block_errors(step: dict[str, Any], declared: Any) -> list[str]:
    """Disagreement between the step's ``run:`` block and the manifest's frozen one.

    NORMALISATION, and only this: each line is right-stripped and blank lines
    are dropped. Trailing whitespace and an empty line are shell no-ops, so
    refusing them would be refusing layout; everything else — content, count
    and ORDER — must be equal.
    """
    if not isinstance(declared, list) or not declared:
        return [
            "the manifest declares no run_block line list for the "
            f"{P0A_STEP_MARKER} step, so its body is bound by nothing"
        ]
    actual = [line.rstrip() for line in str(step.get("run", "")).splitlines() if line.strip()]
    frozen = [str(line).rstrip() for line in declared]
    if actual == frozen:
        return []
    limit = max(len(actual), len(frozen))
    at = next(
        index
        for index in range(limit + 1)
        if (actual[index] if index < len(actual) else None)
        != (frozen[index] if index < len(frozen) else None)
    )
    return [
        f"the {P0A_STEP_MARKER} step's run block is not the one the manifest "
        f"freezes: it carries {len(actual)} commands, run_block freezes "
        f"{len(frozen)}, and they first diverge at line {at + 1} — "
        f"ci.yml={(actual[at] if at < len(actual) else None)!r} "
        f"run_block={(frozen[at] if at < len(frozen) else None)!r}"
    ]


def _p0a_bypass_errors(document: Any, declared_run: Any) -> list[str]:
    """Disagreements between the shipped P0-A step and what the manifest freezes.

    WHAT THIS BINDS, as a category rather than a list of spellings: the step's
    ``run:`` block must equal the manifest's ``run_block`` line for line and in
    order, so ANY inserted, deleted, reordered or rewritten command is refused
    — a prepended ``exit 0``, an appended ``|| :`` or ``; true``, a pipe in
    place of the exit-code capture, or a body replaced wholesale. The revision
    this replaces tested ONE TOKEN, ``|| true``, and was measured PERMITTING
    every one of those five; the enclosing test did not save it, because
    asserting that the node path and the JUnit artifact are SUBSTRINGS of the
    run block is satisfied by a block that begins ``exit 0``. Beside the body
    it refuses ``continue-on-error`` on this step or on any prerequisite the
    condition names, an ``if:`` carrying no ``!cancelled()``, and a
    prerequisite id no step in the job defines.

    WHAT IT DOES NOT BIND, named rather than claimed away, and MEASURED rather
    than reasoned about: the step's ``name:`` and ``if:`` TEXT; a byte-level
    edit that yields the SAME parsed text, since the comparison is against the
    PARSED value — re-indenting the whole block scalar is the measured example,
    and YAML strips the common indent so the text is unchanged; and trailing
    whitespace or a blank line, which are shell no-ops. RE-WRAPPING A
    CONTINUATION IS **NOT** in that set: it changes the parsed lines and is
    refused. An earlier revision of this docstring said it was permitted, which
    the predicate table refuted. Whether the step sits in the right job at all
    is established by the caller's instrument controls, not here.
    """
    steps = _smoke_job_steps(document)
    if not steps:
        return ["ci.yml declares no readable smoke job steps"]
    matches = [
        step for step in steps
        if isinstance(step, dict) and P0A_STEP_MARKER in str(step.get("name", ""))
    ]
    if len(matches) != 1:
        return [
            f"the smoke job carries {len(matches)} steps naming "
            f"{P0A_STEP_MARKER!r}, not exactly one"
        ]
    step = matches[0]
    condition = str(step.get("if", ""))
    problems: list[str] = []

    if "continue-on-error" in step:
        problems.append(
            f"the {P0A_STEP_MARKER} step declares continue-on-error: "
            f"{step['continue-on-error']!r}; a hard gate whose failure the job "
            "tolerates is a nudge"
        )
    if "!cancelled()" not in condition:
        problems.append(
            f"the {P0A_STEP_MARKER} step's if: does not carry !cancelled(), so "
            "GitHub's implicit success() returns and a red sibling step SKIPS "
            "the gate entirely"
        )
    problems.extend(_p0a_run_block_errors(step, declared_run))

    declared_ids = {
        str(other.get("id"))
        for other in steps
        if isinstance(other, dict) and other.get("id")
    }
    named = _PREREQUISITE_OUTCOME_RE.findall(condition)
    if not named:
        problems.append(
            f"the {P0A_STEP_MARKER} step's if: names no prerequisite as "
            "steps.<id>.outcome != 'failure', so !cancelled() runs it on top "
            "of broken setup"
        )
    for prerequisite in named:
        if prerequisite not in declared_ids:
            problems.append(
                f"the if: names steps.{prerequisite}.outcome, which no step in "
                "the smoke job defines: the expression resolves to the empty "
                "string, '' != 'failure' is always true, and the prerequisite "
                "is not actually gated on"
            )
            continue
        owner = next(
            other for other in steps
            if isinstance(other, dict) and str(other.get("id")) == prerequisite
        )
        if "continue-on-error" in owner:
            problems.append(
                f"prerequisite step {prerequisite!r} declares continue-on-error: "
                f"{owner['continue-on-error']!r}; `outcome` is evaluated BEFORE "
                "continue-on-error is applied, so a tolerated failure there "
                f"turns this if: false, SKIPS {P0A_STEP_MARKER}, and leaves the "
                "job green with the hard gate never having run"
            )
    return problems


@pytest.mark.timeout(5)
def test_the_p0a_ci_step_cannot_be_skipped_or_tolerated(tmp_path):
    """The step that runs this node, watched refusing AND permitting.

    Every arm mutates the PARSED workflow rather than its text, so nothing here
    depends on YAML layout; the instrument controls below establish that the
    parse read the real shipped step first.
    """
    document = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    frozen_block = _case(_manifest(), "P0-C01")["run_block"]

    # --- INSTRUMENT CONTROL 0: the manifest's frozen body is a real, non-empty
    # line list carrying the invocation. A missing or empty field would make
    # every run-block arm below refuse for the wrong reason, and the permitting
    # arm pass for the wrong reason too.
    assert isinstance(frozen_block, list) and len(frozen_block) >= 5, frozen_block
    assert any(P0A_JUNIT_ARTIFACT in line for line in frozen_block), frozen_block

    # --- INSTRUMENT CONTROL 1: the parse found the real step, with the real
    # invocation in it. A parse that returned an empty job would make every
    # permitting arm below vacuous.
    steps = _smoke_job_steps(document)
    assert len(steps) >= 5, len(steps)
    p0a = [s for s in steps if isinstance(s, dict) and P0A_STEP_MARKER in str(s.get("name", ""))]
    assert len(p0a) == 1, [s.get("name") for s in steps if isinstance(s, dict)]
    assert str(NODE_FILE.relative_to(REPO_ROOT)) in str(p0a[0].get("run", "")), p0a[0]
    assert P0A_JUNIT_ARTIFACT in str(p0a[0].get("run", "")), p0a[0]

    # --- INSTRUMENT CONTROL 2: the prerequisite extractor found real names,
    # and each resolves to a real step id. A regex matching nothing would make
    # the "unresolvable id" arm below pass for the wrong reason.
    prerequisites = _PREREQUISITE_OUTCOME_RE.findall(str(p0a[0].get("if", "")))
    assert len(prerequisites) >= 5, prerequisites
    ids = {str(s.get("id")) for s in steps if isinstance(s, dict) and s.get("id")}
    assert set(prerequisites) <= ids, (sorted(prerequisites), sorted(ids))

    # --- PERMITTING ARM: the shipped workflow. This is the arm the four
    # refusing arms below have to be distinguishable from.
    assert _p0a_bypass_errors(document, frozen_block) == [], (
        "\n".join(_p0a_bypass_errors(document, frozen_block))
    )

    def mutated(edit) -> list[str]:
        copy_of = copy.deepcopy(document)
        edit(copy_of)
        return _p0a_bypass_errors(copy_of, frozen_block)

    def p0a_step(doc: dict[str, Any]) -> dict[str, Any]:
        return next(
            s for s in _smoke_job_steps(doc)
            if isinstance(s, dict) and P0A_STEP_MARKER in str(s.get("name", ""))
        )

    # --- REFUSING ARM 1, THE MEASURED SHAPE: continue-on-error on the step.
    # Measured before this guard existed: the node still reported 69 passed and
    # nothing refused.
    tolerated = mutated(lambda doc: p0a_step(doc).__setitem__("continue-on-error", True))
    assert any("declares continue-on-error" in p for p in tolerated), tolerated

    # --- REFUSING ARM 2, THE KEY NOT THE VALUE: `false` is refused too, so the
    # guard cannot be disarmed by declaring the harmless spelling first and
    # flipping it in a later diff.
    declared_false = mutated(
        lambda doc: p0a_step(doc).__setitem__("continue-on-error", False)
    )
    assert any("declares continue-on-error" in p for p in declared_false), declared_false

    # --- REFUSING ARM 3, THE SECOND MEASURED SHAPE: delete the !cancelled()
    # half and the implicit success() returns, so a red sibling skips the gate.
    def drop_cancelled(doc: dict[str, Any]) -> None:
        step = p0a_step(doc)
        step["if"] = str(step["if"]).replace("!cancelled()", "true")

    uncancelled = mutated(drop_cancelled)
    assert any("!cancelled()" in p for p in uncancelled), uncancelled

    # --- REFUSING ARM 4, A DIFFERENT SHAPE — the SKIP-TO-GREEN direction
    # ci.yml's own comment names in prose and calls "not exploitable today,
    # verified by parsing this file". Nothing parsed it. A prerequisite that
    # gains continue-on-error and then fails reads outcome 'failure', turns the
    # condition false, and skips P0-A while the job stays green.
    def tolerate_prerequisite(doc: dict[str, Any]) -> None:
        target = _PREREQUISITE_OUTCOME_RE.findall(str(p0a_step(doc)["if"]))[-1]
        owner = next(
            s for s in _smoke_job_steps(doc)
            if isinstance(s, dict) and str(s.get("id")) == target
        )
        owner["continue-on-error"] = True

    prereq_tolerated = mutated(tolerate_prerequisite)
    assert any("prerequisite step" in p for p in prereq_tolerated), prereq_tolerated

    # --- REFUSING ARM 5, A DIFFERENT SHAPE AGAIN: an if: naming a step id that
    # does not exist. GitHub resolves it to the empty string and '' != 'failure'
    # is true, so the prerequisite silently stops gating anything — a bypass
    # that needs no continue-on-error at all.
    def typo_prerequisite(doc: dict[str, Any]) -> None:
        step = p0a_step(doc)
        target = _PREREQUISITE_OUTCOME_RE.findall(str(step["if"]))[0]
        step["if"] = str(step["if"]).replace(f"steps.{target}.", f"steps.{target}x.")

    typoed = mutated(typo_prerequisite)
    assert any("no step in the smoke job defines" in p for p in typoed), typoed

    # --- REFUSING ARM 6, THE CATEGORY THAT REPLACED A TOKEN. The predecessor
    # of this arm tested `"|| true" in run`, and calling it directly with
    # doctored steps measured it PERMITTING all five of the first shapes below.
    # `exit 0` after `set -euo pipefail` is a TOTAL bypass: pytest never runs,
    # the JUnit completeness re-read never runs, the step is unconditionally
    # green — and the node path and the JUnit artifact are both still
    # substrings of the block, so the enclosing instrument controls read clean.
    # Every shape is now refused by ONE rule, equality with the manifest's
    # frozen body, so a spelling nobody listed is refused as well.
    def rewrite(edit):
        return mutated(
            lambda doc: p0a_step(doc).__setitem__("run", edit(str(p0a_step(doc)["run"])))
        )

    def reordered(run: str) -> str:
        lines = run.splitlines()
        lines[0], lines[1] = lines[1], lines[0]
        return "\n".join(lines) + "\n"

    bypasses = (
        ("prepend exit 0", lambda r: "set -euo pipefail\nexit 0\n" + r),
        ("append || :", lambda r: r + "|| :\n"),
        ("append ; true", lambda r: r + "; true\n"),
        ("replace the body wholesale", lambda r: "true\n"),
        ("pipe instead of || ec=$?", lambda r: r.replace("|| ec=$?", "| cat")),
        ("append || true", lambda r: r + "|| true\n"),
        ("reorder two commands", reordered),
        ("delete the JUnit re-read", lambda r: "\n".join(r.splitlines()[:-1]) + "\n"),
    )
    for label, edit in bypasses:
        # Each edit must really change the body, or its refusal proves nothing.
        assert edit(str(p0a_step(document)["run"])) != str(p0a_step(document)["run"]), label
        refused_shape = rewrite(edit)
        assert any("run block is not the one the manifest freezes" in p for p in refused_shape), (
            label,
            refused_shape,
        )

    # --- DISCRIMINATION CONTROL 2, A DIFFERENT SHAPE from the continue-on-error
    # one below: an edit ELSEWHERE in ci.yml — a step body in ANOTHER job. The
    # run-block equality is scoped to the one step the manifest freezes; a
    # guard that reddened on any workflow edit would be paid off by deletion
    # rather than obeyed.
    def edit_another_job(doc: dict[str, Any]) -> None:
        for job_name, job in doc["jobs"].items():
            if job_name == "smoke":
                continue
            for step in job.get("steps", []) if isinstance(job, dict) else []:
                if isinstance(step, dict) and "run" in step:
                    step["run"] = "echo an unrelated edit\n" + str(step["run"])
                    return
        raise AssertionError("no step outside the smoke job to mutate")

    elsewhere = copy.deepcopy(document)
    edit_another_job(elsewhere)
    assert elsewhere != document, "the unrelated-edit control changed nothing"
    assert _p0a_bypass_errors(elsewhere, frozen_block) == [], (
        _p0a_bypass_errors(elsewhere, frozen_block)
    )

    # --- THE NORMALISATION, PINNED IN BOTH DIRECTIONS. Two shapes are dropped
    # before comparing, and prose saying so is not a measurement: a blank line
    # and trailing whitespace are shell no-ops and must pass. A RE-WRAPPED
    # continuation is NOT in that set — it changes the parsed lines and must
    # fail — which is the arm that keeps the normalisation from quietly
    # widening into "any layout change is fine".
    for label, edit in (
        ("a blank line", lambda r: r.replace("ec=0\n", "ec=0\n\n", 1)),
        ("trailing whitespace", lambda r: r.replace("ec=0\n", "ec=0   \n", 1)),
    ):
        assert edit(str(p0a_step(document)["run"])) != str(p0a_step(document)["run"]), label
        assert rewrite(edit) == [], (label, rewrite(edit))
    rewrapped = rewrite(lambda r: r.replace(" \\\n  -v", " \\\n   -v", 1))
    assert any("run block is not the one the manifest freezes" in p for p in rewrapped), rewrapped

    # --- REFUSING ARM 7, THE BINDING'S OWN ABSENCE: a manifest that declares no
    # run_block must refuse rather than silently stop checking the body. A
    # guard that goes quiet when its operand vanishes is the fail-open shape
    # this whole rung exists to remove.
    for empty in (None, [], "set -euo pipefail"):
        unbound = _p0a_bypass_errors(document, empty)
        assert any("bound by nothing" in p for p in unbound), (empty, unbound)

    # --- DISCRIMINATION CONTROL: continue-on-error on an UNRELATED step, in
    # another job, must NOT be reported. This repo runs deliberate ratchets
    # under continue-on-error; a guard that refused the key everywhere would be
    # paid off by being deleted rather than obeyed.
    def tolerate_elsewhere(doc: dict[str, Any]) -> None:
        for step in _smoke_job_steps(doc):
            if isinstance(step, dict) and not step.get("id") and P0A_STEP_MARKER not in str(
                step.get("name", "")
            ):
                step["continue-on-error"] = True
                return
        raise AssertionError("no unrelated, ungated smoke step to mutate")

    assert mutated(tolerate_elsewhere) == [], mutated(tolerate_elsewhere)


# ==========================================================================
# 56 — the LAST member of the value-domain class: a subject-authored value
#      converted with no guard. 10s: one in-process call per arm, no
#      subprocess (the child is replaced), no filesystem.
# ==========================================================================
#
# `_runtime_import_audit` read the probe child's stdout and did three unguarded
# things with whatever came back: `.get` on a value that need not be a dict,
# iteration over a `foreign` that need not be iterable, and `int()` over an
# `examined` that need not be a number. The `int()` is structurally identical
# to the `_plane_bounds` conversion already corrected, and the correction there
# recorded the reason a narrow `except (TypeError, ValueError)` was not enough:
# `int(float("inf"))` raises `OverflowError`, an `ArithmeticError`.
#
# NOT REACHABLE AT P0-A, and closed anyway. Two independent validators reached
# the same reading: the child program is fixed, the subject is the frozen
# observer, which prints nothing on import, so `json.loads` of any injected
# text fails first and the safe decline is taken. The category is emptied
# rather than left nearly empty — a member left standing because today's
# caller cannot reach it is a member the next caller can.


@pytest.mark.timeout(10)
def test_a_defeated_probe_payload_reports_not_audited_instead_of_crashing(monkeypatch):
    """The import probe's reading, watched declining AND succeeding.

    Every refusing arm drives a DIFFERENT defeat with a DIFFERENT exception
    base, because the shipped defect was precisely an exception-type
    enumeration that missed one. The permitting arms are what separate this
    fix from a function that returns the decline unconditionally.
    """
    subject = OBSERVER_PATH

    def child(stdout: str, code: int = 0):
        """Replace the probe child with one that prints exactly ``stdout``."""

        def fake_run(*_args: Any, **_kwargs: Any):
            return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr="")

        monkeypatch.setattr(observer.subprocess, "run", fake_run)
        return observer._runtime_import_audit(subject)

    # --- INSTRUMENT CONTROL: the monkeypatch really replaces the child. A
    # patch that missed would leave every arm below measuring the real probe
    # over the real observer, which returns a clean reading for any input.
    findings, examined, audited = child('{"examined": 41, "foreign": ["tier_registry"]}')
    assert (examined, audited) == (41, True), (findings, examined, audited)
    assert [f["module"] for f in findings] == ["tier_registry"], findings

    # --- PERMITTING ARM 2, the empty reading: a child that printed nothing is
    # still an AUDIT, of zero modules. Declining here would degrade the source
    # plane on every clean run, which is the over-correction this fix must not
    # make.
    assert child("") == ([], 0, True)

    # --- POSITIVE CONTROL FOR THE SHAPE: the conversion the fix wraps really
    # does raise, and really does raise something outside the tuple the
    # pre-existing handler names. Without this the refusing arm below could
    # pass because nothing was ever wrong.
    infinite = json.loads('{"examined": Infinity}')["examined"]
    with pytest.raises(OverflowError) as raised:
        int(infinite)
    assert not isinstance(raised.value, (ValueError, RecursionError)), (
        "the pre-existing (ValueError, RecursionError) clause would have caught "
        "this, so the arm below proves nothing"
    )

    # --- REFUSING ARMS: four defeats, four exception bases, ONE answer.
    for label, payload in (
        ("non-finite examined -> ArithmeticError", '{"examined": Infinity, "foreign": []}'),
        ("bare scalar payload -> AttributeError", "5"),
        ("non-iterable foreign -> TypeError", '{"examined": 3, "foreign": 7}'),
        ("unparsable examined -> ValueError", '{"examined": "many", "foreign": []}'),
        ("not JSON at all -> ValueError", "Traceback (most recent call last):"),
        ("repeated key -> _RepeatedJsonKey", '{"examined": 1, "examined": 2, "foreign": []}'),
    ):
        assert child(payload) == ([], 0, False), label

    # --- DISCRIMINATION CONTROL, a DIFFERENT SHAPE from all of the above: a
    # NON-ZERO child exit is not a defeated read. It is a reading — the import
    # failed — and it must still report AUDITED with its finding, or the fix
    # has swallowed a signal rather than guarded a conversion.
    failed_findings, failed_examined, failed_audited = child("", code=1)
    assert (failed_examined, failed_audited) == (0, True)
    assert len(failed_findings) == 1 and "rc=1" in failed_findings[0]["evidence"], failed_findings


# ==========================================================================
# 57 — a non-finite constant is not JSON, and the packet must stay
#      recomputable by ordinary tools. 20s: three observer subprocesses.
# ==========================================================================
#
# `json.dump` defaults to `allow_nan=True` and `json.loads` accepts
# `Infinity`, `-Infinity` and `NaN` with no `parse_constant`. A subject writing
# one into its own `fs-inventory.json` — a document this observer forwards
# verbatim BY DESIGN — got it re-emitted as a bare token. MEASURED before the
# fix: a 16,711-byte packet at `rc=0` that an ordinary strict JSON reader
# REJECTS. That falsifies the manifest's claim that the evidence is
# recomputable from raw bytes by a third party with ordinary tools.
#
# WHY IT WAS NOT A BLOCKING DEFECT, and why it is fixed anyway: the naming
# channel still fired and every observer/jq disagreement runs fail-closed, so
# no DECISION read clean over it. But the falsified claim is about
# RECOMPUTABILITY, not about decisions, and a decision-shaped argument cannot
# rescue it. The refusal is placed at the PARSE boundary so the token lands in
# the malformed channel that already exists, rather than at the emit boundary
# where the only remaining answer is to publish nothing.


@pytest.mark.timeout(20)
def test_a_non_finite_subject_constant_degrades_its_plane_and_never_reaches_the_packet(tmp_path):
    """The forwarded document's parse, watched refusing AND permitting."""

    def strict_load(text: str) -> Any:
        """An ORDINARY strict JSON reader — no `Infinity`, no `NaN`.

        Configured in this test rather than borrowed from the observer, so the
        oracle and the subject share no code. This is the reader RFC 8259
        describes and the one a third party recomputing the evidence has.
        """

        def refuse(constant: str) -> Any:
            raise ValueError(f"non-finite JSON constant {constant}")

        return json.loads(text, parse_constant=refuse)

    def world(tag: str, injected: str | None) -> Path:
        run_root = _make_run_root(tmp_path / tag)
        inventory = run_root / "fs-inventory.json"
        if injected is not None:
            original = inventory.read_text(encoding="utf-8")
            doctored = original.replace('"mode":', f'"drift_ratio": {injected}, "mode":', 1)
            assert doctored != original, "the injection changed nothing"
            inventory.write_text(doctored, encoding="utf-8")
        return run_root

    # --- INSTRUMENT CONTROL: the strict reader really refuses the token, and
    # really accepts an ordinary document. A reader that accepted everything
    # would make the permitting arms below vacuous, and one that refused
    # everything would make the refusing arm pass for the wrong reason.
    with pytest.raises(ValueError):
        strict_load('{"x": Infinity}')
    assert strict_load('{"x": 1e308}') == {"x": 1e308}

    # --- PERMITTING ARM 1: the pristine world. Every later arm has to be
    # distinguishable from this one.
    pristine = _run_observer(OBSERVER_PATH, world("pristine", None))
    assert pristine.returncode == 0, pristine.stderr[-500:]
    clean = strict_load(pristine.stdout)
    assert clean["observation"]["filesystem"]["observation_status"] == observer.OBSERVED

    # --- PERMITTING ARM 2, THE NEGATIVE CONTROL OF A DIFFERENT SHAPE: an
    # enormous but FINITE value injected at the same key. It is forwarded, the
    # packet still reparses, and the plane stays OBSERVED — so the refusal
    # below is about non-finiteness and not about the document having been
    # edited, nor about the magnitude of a number.
    finite = _run_observer(OBSERVER_PATH, world("finite", "1e308"))
    assert finite.returncode == 0, finite.stderr[-500:]
    forwarded = strict_load(finite.stdout)
    assert forwarded["observation"]["filesystem"]["observation_status"] == observer.OBSERVED
    assert forwarded["observation"]["filesystem"]["evidence_malformed"] is False

    # --- REFUSING ARM: the same injection, non-finite. The packet is still
    # emitted (an observation that names its own defeat is worth more than
    # silence), it carries no bare token, an ordinary reader parses it, and the
    # plane that read the document degrades.
    infinite = _run_observer(OBSERVER_PATH, world("infinite", "Infinity"))
    assert infinite.returncode == 0, infinite.stderr[-500:]
    assert "Infinity" not in infinite.stdout, "a bare non-finite token reached the packet"
    degraded = strict_load(infinite.stdout)
    assert degraded["observation"]["filesystem"]["observation_status"] == observer.ERROR
    assert degraded["observation"]["filesystem"]["evidence_malformed"] is True

    # --- THE SAME REFUSAL FOR THE OTHER TWO TOKENS, and on the OTHER reader.
    # `NaN` and `-Infinity` are the members `Infinity` alone would have left,
    # and `_read_jsonl` is a second parse site that would otherwise need its
    # own fix.
    for token in ("NaN", "-Infinity"):
        with pytest.raises(ValueError):
            json.loads(f'{{"x": {token}}}', parse_constant=observer._refuse_non_finite)
    assert json.loads('{"x": 1}', parse_constant=observer._refuse_non_finite) == {"x": 1}

    # --- THE SECOND ROUTE, FOUND BY ATTACKING THE FIRST FIX RATHER THAN
    # READING IT. `1e400` is a NUMBER token, so `parse_constant` never sees it
    # and `float("1e400")` is `inf` with no error. With only the constant hook
    # installed this run was MEASURED at rc=3 and ZERO packet bytes: the
    # emit-boundary `allow_nan=False` refused the whole document, so a
    # subject-authored value could DENY the observation outright. That is a
    # worse answer than the one it replaced, and it is why the number hook
    # exists — a subject may degrade the plane it authored, never the packet.
    overflowing = _run_observer(OBSERVER_PATH, world("overflow", "1e400"))
    assert overflowing.returncode == 0, (overflowing.returncode, overflowing.stderr[-300:])
    assert overflowing.stdout, "a subject-authored number produced zero packet bytes"
    overflowed = strict_load(overflowing.stdout)
    assert overflowed["observation"]["filesystem"]["observation_status"] == observer.ERROR

    # POSITIVE CONTROL FOR THAT ROUTE: the literal really does overflow through
    # the parser's NUMBER path, not its constant path, so the arm above is not
    # a second spelling of the arm before it.
    assert json.loads("1e400") == float("inf")
    assert json.loads('{"x": 1e400}', parse_constant=observer._refuse_non_finite) == {
        "x": float("inf")
    }, "parse_constant caught it, so this arm proves nothing about parse_float"
    for literal in ("1e400", "-1e400"):
        with pytest.raises(ValueError):
            observer._finite_float(literal)
    # NEGATIVE CONTROL, a different shape: ordinary finite literals, including
    # the largest representable one, must still be parsed as numbers.
    assert observer._finite_float("1e308") == 1e308
    assert observer._finite_float("-0.5") == -0.5

    # --- THE EMIT BOUNDARY, driven directly: a packet carrying a non-finite
    # float that reached it by some route other than a parse must be REFUSED,
    # not rendered as a token no third party can read.
    with pytest.raises(ValueError):
        json.dumps({"x": float("inf")}, allow_nan=False)


# ==========================================================================
# 58 — an environment value is BYTES, and a refusal must name its own cause.
#      20s: two observer subprocesses.
# ==========================================================================
#
# POSIX permits any byte but NUL in an environment value. CPython decodes such
# a value with `surrogateescape`, and `str.encode("utf-8")` of the result
# raises `UnicodeEncodeError` — a `ValueError`, which `_cli` caught on the arm
# reserved for a REFUSED ARGV. MEASURED before the fix: `HOME=/tmp/\xff` gave
# `rc=2`, ZERO packet bytes, and `refused: 'utf-8' codec can't encode
# character '\udcff'` — a message blaming the caller's arguments for something
# no argument did. This is the THIRD site of that misattribution in this
# module; `_run_command` and `_debug_receipt_numbers` were the first two.


@pytest.mark.timeout(20)
def test_a_non_utf8_environment_value_is_observed_and_does_not_read_as_a_refused_argv(tmp_path):
    """The environment plane, watched observing — and the argv arm, still refusing."""
    stray = "/tmp/\udcff"
    expected = stray.encode("utf-8", errors="surrogateescape")

    # --- INSTRUMENT CONTROL: the value really is one a plain encode refuses,
    # and `surrogateescape` really round-trips it to the ORIGINAL bytes. A
    # value that encoded cleanly would make the arms below prove nothing.
    with pytest.raises(UnicodeEncodeError) as raised:
        stray.encode("utf-8")
    assert isinstance(raised.value, ValueError), (
        "the shape only misattributes because UnicodeEncodeError IS a ValueError"
    )
    assert expected == b"/tmp/\xff" and len(expected) == 6, expected

    def home_entry(proc: subprocess.CompletedProcess) -> dict[str, Any]:
        variables = json.loads(proc.stdout)["observation"]["environment"]["variables"]
        return next(v for v in variables if v["name"] == "HOME")

    # --- PERMITTING ARM 1, the ordinary environment. Every arm below has to be
    # distinguishable from this one.
    clean = _run_observer(OBSERVER_PATH, _make_run_root(tmp_path / "clean"))
    assert clean.returncode == 0, clean.stderr[-500:]
    assert home_entry(clean)["observation_status"] == observer.OBSERVED

    # --- PERMITTING ARM 2, THE MEASURED SHAPE: the same run with one stray
    # byte in HOME. A packet is emitted, the variable is OBSERVED — it WAS
    # observed — and its digest and length are of the REAL bytes, recomputed
    # here by hashlib rather than read back from the observer.
    dirty = _run_observer(
        OBSERVER_PATH, _make_run_root(tmp_path / "dirty"), extra_env={"HOME": stray}
    )
    assert dirty.returncode == 0, (dirty.returncode, dirty.stderr[-500:])
    assert dirty.stdout, "the run produced zero packet bytes"
    entry = home_entry(dirty)
    assert entry["observation_status"] == observer.OBSERVED, entry
    assert entry["bytes"] == len(expected), entry
    assert entry["sha256"] == hashlib.sha256(expected).hexdigest(), entry

    # --- CONTROL OF THAT ARM: the two runs really did see different values. If
    # the stray byte never reached the child, both digests would agree and the
    # arm above would be measuring the ordinary environment twice.
    assert entry["sha256"] != home_entry(clean)["sha256"], "the stray byte never arrived"

    # --- THE ARM THAT WAS BEING BORROWED, still refusing. rc=2 must still mean
    # a refused argv and nothing else, or the fix has emptied the channel it
    # was misusing instead of separating the two.
    refused = subprocess.run(
        [
            sys.executable, "-S", str(OBSERVER_PATH),
            "--cwd", str(tmp_path), "--run-root", str(tmp_path / "clean" / "run"),
            "--session-uuid", SESSION_UUID,
            "--setting-sources", "user,--Safe-Mode",
            "--settings-overlay", str(SETTINGS_OVERLAY),
            "--debug-file", str(tmp_path / "clean" / "run" / "debug.log"),
        ],
        capture_output=True, text=True, timeout=OBSERVER_CLI_TIMEOUT_S,
        cwd=str(OBSERVER_PATH.parent),
    )
    assert refused.returncode == 2, (refused.returncode, refused.stderr[-500:])
    assert "--Safe-Mode" in refused.stderr and refused.stdout.strip() == ""


# ==========================================================================
# 59 — the settings-source contract is COMPARED, not merely recorded. 25s:
#      seven observer subprocesses over throwaway run roots.
# ==========================================================================
#
# THE DEFECT: three artifacts asserted that the exact settings-source set was
# checked — `amendment:190-198` ("settings sources/digests"), the manifest's
# `expected_settings.setting_sources`, and the decision's own name
# `D07_SETTINGS_SOURCE_SET_EXACT` — while D07 compared only declared-vs-observed
# settings FILE PATHS and the observer's own comment said "No decision reads
# this field." A disclosure that a field is unread is honest only when nothing
# claims it is read; with three claims outstanding it was a false contract, so
# the check is supplied rather than the claim softened.
#
# MEASURED BEFORE THE FIX, every cell permitting:
#
#     canonical user,project,local  rc=0 recorded=[u,p,l] D06=(OBSERVED,0) D07=(OBSERVED,0)
#     MISSING local                 rc=0 recorded=[u,p,l] D06=(OBSERVED,0) D07=(OBSERVED,0)
#     EXTRA enterprise              rc=0 recorded=[u,p,l] D06=(OBSERVED,0) D07=(OBSERVED,0)
#     REPLACED bogus                rc=0 recorded=[u,p,l] D06=(OBSERVED,0) D07=(OBSERVED,0)
#     REORDERED local,project,user  rc=0 recorded=[u,p,l] D06=(OBSERVED,0) D07=(OBSERVED,0)
#
# AND IT WAS WORSE THAN UNREAD — it was SELF-CERTIFYING. With
# `--setting-sources user,project,local` on the argv and a fixture recording
# `["user","bogus"]`, the emitted plane published `['user','bogus']`: the
# recorded value tracked the SUBJECT's own document and nothing compared it to
# anything (`ladder:282`).


@pytest.mark.timeout(35)
def test_the_canonical_source_contract_refuses_every_deviation_and_permits_a_reorder(tmp_path):
    """D07 compares the RECORDED source set against the CANONICAL contract.

    WHY THE COMPARISON IS A MULTISET: the DOCUMENTED PRECEDENCE, which is what
    makes argv order semantically inert and the reorder cell a control rather
    than a guess. https://code.claude.com/docs/en/cli-usage defines the flag as
    a "Comma-separated list of setting sources to load (user, project, local)"
    — it SELECTS WHICH SOURCES LOAD, and says nothing about the order of the
    list mattering. https://code.claude.com/docs/en/settings then fixes
    precedence by LEVEL, highest first: managed settings, command line
    (``claude --settings``), project-local (``.claude/settings.local.json``),
    shared project (``.claude/settings.json``), user
    (``~/.claude/settings.json``), with "A key set at a higher level overrides
    the same key set lower down." For the three SELECTABLE sources that is
    ``local > project > user``, fixed by level and INDEPENDENT of argv order.
    So a reorder must be watched PERMITTING, and a duplicate must still refuse
    — which is exactly what ``set()`` on both sides would have lost, since
    ``{user, local} == {user, local}`` for ``["user","user","local"]``.

    WHAT THE REAL BINARY ESTABLISHED, AND ONLY THAT: that MEMBERSHIP is
    validated, and case-sensitively. The probe ran ``doctor``, which reports on
    an installation, so what it observed is ACCEPTANCE AND REFUSAL of the argv
    value — never that two orders behave identically, and no claim here rests
    on it having shown that. Against claude 2.1.236::

        $ claude --setting-sources user,project,local doctor   -> accepted
        $ claude --setting-sources local,project,user doctor    -> accepted
        $ claude --setting-sources user,user,local    doctor    -> accepted
        $ claude --setting-sources project            doctor    -> accepted
        $ claude --setting-sources USER,project,local doctor
          Error processing --setting-sources: Invalid setting source: USER.
          Valid options are: user, project, local
        $ claude --setting-sources user,bogus,local   doctor
          Error processing --setting-sources: Invalid setting source: bogus.
          Valid options are: user, project, local

    UNVERIFIED, and the distinction between DOCUMENTED and MEASURED-HERE is
    kept visible on purpose: the precedence above is read out of the
    documentation, not observed by this module. P0-A executes no child
    (``run.child_executed`` is ``const: false``), so no argv was ever
    transmitted, nothing here measures a real session's settings resolution,
    and a real resolution contradicting the documented precedence would be
    invisible to every arm below.

    WHAT IS COMPARED TO WHAT: the observation plane's
    ``expected_setting_sources`` — the caller-supplied canonical contract,
    whose one home is the frozen manifest and which the observer restates
    nowhere — against ``setting_sources``, the list the SUBJECT recorded in
    ``settings-sources.json``. The two operands have DIFFERENT provenance by
    construction, which is the property the previous reader destroyed when it
    substituted the observer's own argument for the subject's record.
    """
    canonical = _canonical_setting_sources()
    assert canonical, "the manifest binds no canonical settings-source contract"

    def sources_for(contract: list[str] | None) -> list[str]:
        """The argv contract a cell drives, resolved at its ONE home.

        ``is None``, NOT ``or``. ``[]`` is falsy, so the previous
        ``contract or canonical`` substituted the canonical list for an
        EXPLICITLY EMPTY contract: ``None`` and ``[]`` produced the same argv,
        an empty contract could never reach the observer, and the cell that
        drives one could only ever have re-run the clean case. ``None`` is the
        sentinel for "the caller said nothing"; ``[]`` is the caller saying
        "no contract", which is a different claim and must survive to the
        observer. Every cell below resolves its contract through here, so a
        re-introduction of the falsy fallback has one place to hide and the
        empty-contract arm watches it.
        """
        return canonical if contract is None else contract

    def d07(recorded: Any, contract: list[str] | None = None, label: str = "") -> dict[str, Any]:
        run_root = _make_run_root(tmp_path / f"src_{label}")
        document = json.loads(
            (VALID_DIR / "settings-sources.json").read_text(encoding="utf-8")
        )
        if recorded is ...:
            document.pop("setting_sources", None)
        else:
            document["setting_sources"] = recorded
        (run_root / observer.EVIDENCE_SETTINGS).write_text(
            json.dumps(document), encoding="utf-8"
        )
        packet = _packet_from(
            OBSERVER_PATH, run_root, setting_sources=sources_for(contract)
        )
        record = _decision_of(packet, "D07_SETTINGS_SOURCE_SET_EXACT")
        record["_plane"] = packet["observation"]["settings"]
        return record

    # --- PERMITTING ARM: the canonical list, recorded exactly. Without this the
    # refusals below would be indistinguishable from a decision that can never
    # report clean.
    clean = d07(list(canonical), label="clean")
    assert clean["observation_status"] == "OBSERVED", clean
    assert clean["discrepancies"] == [], clean

    # --- THE ONE HOME IS READ FROM, not restated. The operand the packet
    # published must be the manifest's value; the observer carries no default
    # that could supply it, and this is the assertion that says so.
    assert clean["_plane"]["expected_setting_sources"] == canonical, clean["_plane"]
    assert clean["_plane"]["setting_sources"] == canonical, clean["_plane"]

    # --- NEGATIVE CONTROL, A DIFFERENT SHAPE FROM THE BUG: a REORDER changes
    # the recorded bytes and must NOT refuse, because the DOCUMENTED
    # precedence cited above is fixed by level and independent of argv order,
    # so the value carries set semantics and not sequence semantics. (The CLI
    # probe above is not what licenses this cell: it showed only that both
    # orders are ACCEPTED.) A guard that merely compared lists for
    # equality — the obvious over-fit — would fail exactly here, and a guard
    # that permitted everything would pass this cell while failing all four
    # below. This cell is the reason the comparison is a multiset.
    reordered = d07(list(reversed(canonical)), label="reordered")
    assert reordered["observation_status"] == "OBSERVED", reordered
    assert reordered["discrepancies"] == [], reordered

    # --- REFUSING ARM: the four deviations that were measured PERMITTING.
    missing = d07(canonical[:-1], label="missing")
    extra = d07(canonical + ["enterprise"], label="extra")
    replaced = d07(canonical[:-1] + ["bogus"], label="replaced")
    duplicated = d07(canonical + [canonical[0]], label="duplicated")
    # THE REFUSAL SIGNAL IS THE DISCREPANCY, not the status, and this module is
    # consistent about that: `OBSERVED` says the evidence was READABLE, and a
    # finding over readable evidence is what a discrepancy is — the manifest's
    # positive arm requires all twelve decisions OBSERVED *and* zero
    # discrepancies, so the two channels are read together. A refusing cell
    # that also degraded the status would be claiming the reader was defeated,
    # which here it was not.
    for label, record in (
        ("missing", missing), ("extra", extra),
        ("replaced", replaced), ("duplicated", duplicated),
    ):
        assert record["discrepancies"], (label, record)
        assert record["observation_status"] == "OBSERVED", (label, record)
    assert any(canonical[-1] in text for text in missing["discrepancies"]), missing
    assert any("enterprise" in text for text in extra["discrepancies"]), extra
    assert any("bogus" in text for text in replaced["discrepancies"]), replaced
    assert any(canonical[0] in text for text in duplicated["discrepancies"]), duplicated

    # --- THE SELF-CERTIFICATION ARM, driven as the reproduction ran it: the
    # subject's document is the ONLY thing that changed, the argv contract stays
    # canonical, and the recorded value must reach the packet UNCHANGED and be
    # refused. Before the fix the plane published `['user','bogus']` and D07
    # reported OBSERVED with zero discrepancies.
    forged = d07(["user", "bogus"], label="forged")
    assert forged["_plane"]["setting_sources"] == ["user", "bogus"], forged["_plane"]
    assert forged["_plane"]["expected_setting_sources"] == canonical, forged["_plane"]
    assert forged["discrepancies"], forged
    assert any("bogus" in text for text in forged["discrepancies"]), forged

    # --- THE OTHER DIRECTION, so the operand cannot be read as decorative: a
    # caller whose CONTRACT deviates from the canonical one is refused against
    # a document that records the canonical set. A comparison that fired only
    # when the document moved would still be reading one side and believing it.
    off_contract = d07(list(canonical), contract=canonical[:-1], label="offcontract")
    assert off_contract["discrepancies"], off_contract
    assert any(canonical[-1] in text for text in off_contract["discrepancies"]), off_contract

    # --- AN EXPLICITLY EMPTY CONTRACT IS THE FAIL-OPEN DIRECTION, and it must
    # be NAMED on both doors rather than answered as the clean case. An empty
    # expected list makes EVERY recorded set "exact", which is the direction
    # the whole defect ran in. Until this cycle no cell drove it, and none
    # could have: `contract or canonical` substituted the canonical list for
    # `[]`, so an empty contract was unrepresentable and this arm would have
    # re-run the permitting cell under a different name.
    #
    # DOOR 1, the production route: `[]` survives `sources_for` and the
    # observer REFUSES the run outright, before any packet exists.
    assert sources_for([]) == [], "the falsy fallback is back in sources_for"
    empty_root = _make_run_root(tmp_path / "src_emptycontract")
    (empty_root / observer.EVIDENCE_SETTINGS).write_text(
        json.dumps({"setting_sources": list(canonical)}), encoding="utf-8"
    )
    empty_run = _run_observer(OBSERVER_PATH, empty_root, setting_sources=sources_for([]))
    assert empty_run.returncode != 0, empty_run.stdout[:400]
    assert "empty setting sources" in empty_run.stderr, empty_run.stderr[-400:]
    assert empty_run.stdout.strip() == "", empty_run.stdout[:400]
    # CONTROL OF THAT CONTROL, and the cell that fails first if the falsy
    # fallback returns: the SAME run root driven with the canonical contract
    # exits 0 and emits a packet, so the refusal above is the EMPTY CONTRACT
    # and not a broken run root, an unwritable evidence file or an
    # unimportable module. Under `contract or canonical` the two invocations
    # are byte-identical and this pair cannot discriminate at all.
    empty_control = _run_observer(OBSERVER_PATH, empty_root, setting_sources=list(canonical))
    assert empty_control.returncode == 0, empty_control.stderr[-400:]
    assert json.loads(empty_control.stdout)["observation"]["settings"][
        "expected_setting_sources"
    ] == canonical

    # DOOR 2, the in-memory route, because the CLI refusal above is not the
    # only way an empty contract can reach D07 — a packet assembled by anything
    # other than this CLI reaches `reconcile()` directly. There the empty
    # expected list must be NAMED and the decision must degrade to UNMEASURED:
    # it is an ABSENCE of a contract, not a finding over one, and above all not
    # the OBSERVED/zero-discrepancy shape the manifest's positive arm accepts.
    empty_plane = observer.reconcile(
        {
            "settings": {
                "declared": [],
                "observed": [],
                "setting_sources": list(canonical),
                "expected_setting_sources": [],
                "observation_status": "OBSERVED",
            }
        }
    )
    empty_decision = _decision_of(empty_plane, "D07_SETTINGS_SOURCE_SET_EXACT")
    assert any(
        "no canonical source contract" in text
        for text in empty_decision["discrepancies"]
    ), empty_decision
    assert empty_decision["observation_status"] == "UNMEASURED", empty_decision
    # AND ITS PERMITTING CONTROL, same door, same shape, contract restored: the
    # refusal above is the EMPTY LIST and not something the in-memory route
    # refuses about every plane it is handed.
    filled_decision = _decision_of(
        observer.reconcile(
            {
                "settings": {
                    "declared": [],
                    "observed": [],
                    "setting_sources": list(canonical),
                    "expected_setting_sources": list(canonical),
                    "observation_status": "OBSERVED",
                }
            }
        ),
        "D07_SETTINGS_SOURCE_SET_EXACT",
    )
    assert filled_decision["discrepancies"] == [], filled_decision
    assert filled_decision["observation_status"] == "OBSERVED", filled_decision

    # --- ABSENCE IS NOT A CLEAN COMPARISON. A document that records no sources
    # at all names EVERY member of the contract as unrecorded — one discrepancy
    # per member, not a single vague one — so "the subject recorded nothing"
    # can never be mistaken for "the subject recorded the right thing". The
    # reader was not defeated, so the status stays OBSERVED and the refusal
    # arrives on the discrepancy channel, exactly as in the cells above.
    absent = d07(..., label="absent")
    assert len(absent["discrepancies"]) == len(canonical), absent
    for source in canonical:
        assert any(repr(source) in text for text in absent["discrepancies"]), (source, absent)

    # --- AND THE OBSERVER CARRIES NO SECOND HOME FOR THE VALUE. With
    # `--setting-sources` omitted the CLI must refuse rather than fall back to
    # a restated default, because that default is what made D07's operand come
    # from inside the subject it checks.
    no_contract = subprocess.run(
        [
            sys.executable, "-S", str(OBSERVER_PATH),
            "--cwd", str(tmp_path), "--run-root", str(tmp_path / "src_clean"),
            "--session-uuid", SESSION_UUID,
            "--settings-overlay", str(SETTINGS_OVERLAY),
            "--debug-file", str(tmp_path / "src_clean" / "debug.log"),
        ],
        capture_output=True, text=True, timeout=OBSERVER_CLI_TIMEOUT_S,
        cwd=str(OBSERVER_PATH.parent),
    )
    assert no_contract.returncode != 0, no_contract.stdout[:400]
    assert "setting-sources" in no_contract.stderr, no_contract.stderr[-400:]
    assert no_contract.stdout.strip() == "", no_contract.stdout[:400]
    # CONTROL OF THAT CONTROL: the identical argv WITH the flag exits 0 and
    # emits a packet, so the refusal above is the MISSING FLAG and not a
    # broken invocation, a bad run root or an unimportable module — the
    # instrument is verified before its zero is believed.
    with_contract = subprocess.run(
        [
            sys.executable, "-S", str(OBSERVER_PATH),
            "--cwd", str(tmp_path), "--run-root", str(tmp_path / "src_clean"),
            "--session-uuid", SESSION_UUID,
            "--settings-overlay", str(SETTINGS_OVERLAY),
            "--setting-sources", ",".join(canonical),
            "--debug-file", str(tmp_path / "src_clean" / "debug.log"),
        ],
        capture_output=True, text=True, timeout=OBSERVER_CLI_TIMEOUT_S,
        cwd=str(OBSERVER_PATH.parent),
    )
    assert with_contract.returncode == 0, with_contract.stderr[-500:]
    assert json.loads(with_contract.stdout)["comparison"]["decisions"], with_contract.stdout[:200]


# ==========================================================================
# 60 — a count has a VALUE domain, not just a type. 10s: in-process reconcile
#      over hand-built planes; no subprocess, no filesystem.
# ==========================================================================
#
# THE DEFECT: every count and byte length in this packet is declared
# `integer, minimum: 0` by the schema — `$defs/byte_count`, `evidence_count`,
# `discrepancy_count`, `unparsable_records` — and every reader carried the TYPE
# half of that domain and not the VALUE half. `bool` and `str` were named; a
# NEGATIVE integer was not.
#
# MEASURED BEFORE THE FIX, isolated so the negative did not contradict the
# recorded decision and get caught incidentally:
#
#     bytes=5   decision=RESPONDED  (control) -> D09 OBSERVED, 0 discrepancies
#     bytes=-1  decision=RESPONDED  (ATTACK)  -> D09 OBSERVED, 0 discrepancies
#     bytes=-99 decision=RESPONDED  (ATTACK)  -> D09 OBSERVED, 0 discrepancies
#     _decision_from_exit(0, -1) == "RESPONDED"
#
# AND `_recorded_count` LAUNDERED, `max(0, raw)` turning a negative denominator
# into a clean zero with nothing named:
#
#     raw=0    -> (0, [])          raw=-1  -> (0, [])   <- clamped, unnamed
#     raw=5    -> (5, [])          raw=-99 -> (0, [])   <- clamped, unnamed
#     raw=True -> (0, ['... not a count this reader can rank'])
#     raw='5'  -> (0, ['... not a count this reader can rank'])


def _d09_over(joins: list[dict[str, Any]]) -> dict[str, Any]:
    """D09 as reconciled from a hand-built hooks plane, and nothing else."""
    packet = observer.reconcile(
        {
            "hooks": {"joins": joins, "observation_status": "OBSERVED"},
            "stream": {"observation_status": "OBSERVED"},
            "debug": {"observation_status": "OBSERVED"},
        }
    )
    return _decision_of(packet, "D09_HIDDEN_HOOK_NONZERO")


@pytest.mark.timeout(15)
def test_a_negative_count_is_named_and_degrades_while_a_signal_exit_code_still_ranks():
    """The VALUE domain of every count reader, and the ONE field it must not reach.

    The correction is applied at the CATEGORY — every reader of a count or a
    byte length — rather than at the two sites the reproduction happened to
    probe, and the arms below drive each reader separately so a single fix in
    one place cannot make the others look green.

    THE NEGATIVE CONTROL IS A DIFFERENT SHAPE FROM THE BUG, and it is the whole
    reason this guard is not a blanket "reject negative integers": a negative
    ``exit_code`` is IN domain. It is the POSIX encoding of a terminating
    signal — ``-9`` is SIGKILL, ``-15`` is SIGTERM — and a hook the kernel
    killed is the loudest hidden-non-zero D09 exists to find. Generalising the
    byte-count guard onto its sibling field by analogy would have converted
    that finding into an unrankable read, so the sibling is driven here as an
    arm that must stay PERMITTING.
    """
    # --- THE PREDICATE, both arms, at the boundary values.
    for permitted in (0, 1, 5, 4096, 2**62):
        assert observer._is_recorded_count(permitted) is True, permitted
    for refused in (-1, -99, True, False, "5", 5.0, None, [5], float("inf")):
        assert observer._is_recorded_count(refused) is False, refused

    # --- READER 1, `_decision_from_exit`. PERMITTING first: a positive byte
    # count still derives RESPONDED and a zero still derives SILENT, so the
    # refusals below are not a reader that stopped answering.
    assert observer._decision_from_exit(0, 5) == "RESPONDED"
    assert observer._decision_from_exit(0, 0) == "SILENT"
    # REFUSING: a negative byte count is no longer rankable.
    assert observer._decision_from_exit(0, -1) is None
    assert observer._decision_from_exit(0, -99) is None

    # --- THE ONE THING NOT CHANGED, verified rather than assumed: a negative
    # exit code still ranks NONZERO, beside its positive twins.
    for exit_code in (-9, -15, 1, 2):
        assert observer._decision_from_exit(exit_code, 0) == "NONZERO", exit_code
    # And the TYPE guard on that same field is untouched: `true` is not a
    # clean zero exit.
    assert observer._decision_from_exit(True, 0) is None

    # --- READER 1 THROUGH D09, driven exactly as the reproduction ran it: the
    # recorded `decision` AGREES with the control, so nothing is caught
    # incidentally by a contradiction.
    def join(stdout_bytes: Any) -> list[dict[str, Any]]:
        return [{
            "tool_use_id": "T1", "hook_event_name": "PreToolUse", "exit_code": 0,
            "stdout_bytes": stdout_bytes, "decision": "RESPONDED", "stream_outcome": "ok",
        }]

    control = _d09_over(join(5))
    assert control["discrepancies"] == [], control
    assert control["observation_status"] == "OBSERVED", control
    for attack in (-1, -99):
        record = _d09_over(join(attack))
        assert record["discrepancies"], (attack, record)
        assert any(repr(attack) in text for text in record["discrepancies"]), (attack, record)

    # --- READER 2, `_recorded_count`. The clamp is gone: an out-of-domain
    # value is NAMED on the same channel and in the same words as an
    # unrankable type, and a valid count still passes through unchanged.
    assert observer._recorded_count({"x": 0}, "x", "lbl") == (0, [])
    assert observer._recorded_count({"x": 5}, "x", "lbl") == (5, [])
    assert observer._recorded_count({}, "x", "lbl") == (0, [])
    assert observer._recorded_count({"x": None}, "x", "lbl") == (0, [])
    for attack in (-1, -99, True, "5"):
        value, problems = observer._recorded_count({"x": attack}, "x", "lbl")
        assert value == 0 and problems, (attack, value, problems)
        assert repr(attack) in problems[0], (attack, problems)

    # --- READER 3, `_decision`'s own two published numbers. Both were reached
    # through `max(0, ...)`, which is the same laundering at the LAST reader
    # rather than the first; fixing only the first would have left this one
    # covering for it.
    clean = observer._decision("D01_SCHEMA_ROOT_CLOSED", [], 3)
    assert clean["evidence_count"] == 3 and clean["discrepancies"] == [], clean
    for bad in (-1, -7):
        record = observer._decision("D01_SCHEMA_ROOT_CLOSED", [], bad)
        assert record["evidence_count"] == 0, (bad, record)
        assert any("evidence_count" in text for text in record["discrepancies"]), (bad, record)
        assert record["observation_status"] == "UNMEASURED", (bad, record)
        assert record["discrepancy_count"] == len(record["discrepancies"]), (bad, record)
    negative_total = observer._decision(
        "D01_SCHEMA_ROOT_CLOSED", ["a"], 3, discrepancy_total=-4
    )
    assert negative_total["discrepancy_count"] >= 1, negative_total
    assert any(
        "discrepancy_count" in text for text in negative_total["discrepancies"]
    ), negative_total

    # --- READER 4, `_plane_bounds` over `unparsable_records`. `int(...) > 0`
    # asked only "is it positive", so a count of undecodable records that was
    # itself undecodable read NOT malformed — the one input with the strongest
    # possible claim to ERROR was the one that read clean.
    assert observer._plane_bounds({"unparsable_records": 0})[1] is False
    assert observer._plane_bounds({})[1] is False
    assert observer._plane_bounds({"unparsable_records": None})[1] is False
    assert observer._plane_bounds({"unparsable_records": 2})[1] is True
    for attack in (-1, -99, True, "1"):
        assert observer._plane_bounds({"unparsable_records": attack})[1] is True, attack


# ==========================================================================
# 61 — the judge must be bound by the thing it judges. 20s: six short
#      interpreter starts over the extracted guard plus one 23-file copy.
# ==========================================================================
#
# THE DEFECT THIS CLOSES, measured on the un-bound bytes in three clean
# sandboxes with .git restored::
#
#     baseline                                          -> 77 passed
#     POSITIVE CONTROL: corrupt a frozen fixture only   -> 1 failed
#     ATTACK: neuter the digest test's body, then       -> 77 passed
#             corrupt the same fixture
#
# CI reads tests=77 failures=0 and reports PASS. The digest guard worked;
# DISABLING the digest guard was invisible to it, because the file holding the
# guard was the one subject the manifest did not bind. Git history proves what
# the driver's bytes WERE — it refuses nothing at B-phase CI, which is the
# INV-1 shape: an enforcement claim carried by prose.
#
# TWO THINGS CLOSE IT, and they are independent on purpose.
#
#   1. The driver is now bound in `P0-C01.subject_digests` (23 subjects, up from
#      22), so an ordinary edit to this file refuses in
#      test_manifest_digests_match_current_tracked_bytes.
#   2. The digest contract also has a reader that does NOT live inside this
#      file: a `python -c` line in the P0-A CI step, frozen in the manifest's
#      `run_block`, that recomputes every bound digest before pytest starts.
#      Neutering (1) changes this file's bytes and (2) refuses; neutering (2)
#      requires editing ci.yml, which changes no test but fails the run_block
#      equality in test_the_p0a_ci_step_cannot_be_skipped_or_tolerated.
#
# RESIDUAL, stated rather than implied: an editor with write access to BOTH
# this file and ci.yml, who neuters every in-file reader AND deletes the CI
# line AND updates the manifest's run_block to match, defeats both. No guard
# that lives in the repository it guards can close that; what changes is that
# the bypass now requires three coordinated edits in three files, each visible
# in the same diff, where it previously required one edit to one function body.


def _ci_frozen_byte_guard_command() -> str:
    """The EXACT frozen-byte ``python -c`` guard from the P0-A step, read from ci.yml.

    Read from the copy that EXECUTES, for the same reason
    :func:`_ci_junit_guard_command` is: a guard this test only paraphrased would
    keep passing after ci.yml changed. Keyed on ``subject_digests`` rather than
    on the JUnit artifact, so the two ``python -c`` lines in the step are
    distinguished by what they READ rather than by their position.
    """
    lines = [
        line.strip()
        for line in CI_WORKFLOW.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("python -c ") and "subject_digests" in line
    ]
    assert len(lines) == 1, f"expected exactly one P0-A frozen-byte guard line, found {len(lines)}"
    parts = shlex.split(lines[0])
    assert parts[:2] == ["python", "-c"] and len(parts) == 3, parts
    return parts[2]


def _frozen_byte_scratch(work: Path) -> Path:
    """A scratch tree holding the manifest and every byte it binds."""
    root = work / "tree"
    (root / "tests" / "acceptance").mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST_PATH, root / "tests" / "acceptance" / MANIFEST_PATH.name)
    for relative in _case(_manifest(), "P0-C01")["subject_digests"]:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)
    return root


def _run_frozen_byte_guard(code: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_S,
        cwd=str(cwd),
    )


@pytest.mark.timeout(20)
def test_a_lone_driver_edit_refuses_through_a_guard_outside_this_file(tmp_path):
    """RED/GREEN on a DRIVER-BYTE change alone — no fixture, no manifest edit.

    Every arm runs the byte-for-byte command extracted from ci.yml. The
    permitting arm runs it against the REAL repository, so this node refuses a
    lone edit to its own bytes even if every in-file digest reader has been
    neutered — which is the property the attack above defeated.
    """
    code = _ci_frozen_byte_guard_command()
    driver = str(NODE_FILE.relative_to(REPO_ROOT))
    bound = _case(_manifest(), "P0-C01")["subject_digests"]

    # --- STATIC: the driver is a bound subject at all, and the guard reads the
    # digests from the manifest rather than carrying a copy of them.
    assert driver in bound, (
        "the file that performs the digest check is not itself digest-bound, so "
        "an edit that disables the check is invisible to the check"
    )
    assert "tests/acceptance/plugin-carrier-p0.json" in code, code
    assert "sha256" in code and "subject_digests" in code, code
    assert not any(len(token) == 64 and set(token) <= set("0123456789abcdef")
                   for token in re.findall(r"[0-9a-f]{8,}", code)), (
        "the CI guard carries a hardcoded digest instead of reading the manifest"
    )

    # --- INSTRUMENT CONTROL: the guard is frozen in `run_block` AND runs BEFORE
    # the pytest invocation, so a changed byte stops the step rather than being
    # reported after a green run. A guard the manifest did not freeze could be
    # deleted from ci.yml with nothing refusing.
    run_block = [str(line) for line in _case(_manifest(), "P0-C01")["run_block"]]
    guard_at = [i for i, line in enumerate(run_block) if "subject_digests" in line]
    pytest_at = [i for i, line in enumerate(run_block) if line.startswith("python -m pytest ")]
    assert len(guard_at) == 1 and len(pytest_at) == 1, (guard_at, pytest_at)
    assert guard_at[0] < pytest_at[0], run_block

    # --- PERMITTING ARM, AGAINST WHAT EXECUTES: the real repository, unmodified.
    live = _run_frozen_byte_guard(code, REPO_ROOT)
    assert live.returncode == 0, f"{live.stdout}{live.stderr}"
    assert f"{len(bound)} bound, 0 changed" in live.stdout, live.stdout

    # --- PERMITTING ARM 2: the scratch copy of the same tree.
    scratch = _frozen_byte_scratch(tmp_path)
    clean = _run_frozen_byte_guard(code, scratch)
    assert clean.returncode == 0, f"{clean.stdout}{clean.stderr}"
    assert f"{len(bound)} bound, 0 changed" in clean.stdout, clean.stdout

    # --- THE REFUSING ARM THIS TEST EXISTS FOR: ONE appended byte on the DRIVER
    # and nothing else. No fixture is touched, the manifest is untouched.
    lone = _frozen_byte_scratch(tmp_path / "lone")
    (lone / driver).write_bytes((lone / driver).read_bytes() + b"\n")
    refused = _run_frozen_byte_guard(code, lone)
    assert refused.returncode != 0, (
        f"a lone driver-byte change was PERMITTED: {refused.stdout}{refused.stderr}"
    )
    assert driver in refused.stdout, refused.stdout

    # --- CONTROL, A DIFFERENT SHAPE: an UNRELATED repository file changing must
    # NOT refuse. A guard that reddened on any edit anywhere would be paid off
    # by deletion rather than obeyed.
    unrelated = _frozen_byte_scratch(tmp_path / "unrelated")
    (unrelated / "CHANGELOG.md").write_text("an unrelated edit\n", encoding="utf-8")
    (unrelated / "tests" / "bootstrap" / "not_bound.py").write_text("x = 1\n", encoding="utf-8")
    permitted = _run_frozen_byte_guard(code, unrelated)
    assert permitted.returncode == 0, (
        f"an unrelated file change was refused: {permitted.stdout}{permitted.stderr}"
    )

    # --- REFUSING ARM 2, A DIFFERENT SHAPE: a bound FIXTURE changed. The two
    # shapes together show the guard reads the whole bound set, not one entry.
    fixture_relative = str((VALID_DIR / "packet.json").relative_to(REPO_ROOT))
    corrupted = _frozen_byte_scratch(tmp_path / "fixture")
    (corrupted / fixture_relative).write_bytes(
        (corrupted / fixture_relative).read_bytes() + b"\n"
    )
    fixture_refused = _run_frozen_byte_guard(code, corrupted)
    assert fixture_refused.returncode != 0, fixture_refused.stdout
    assert fixture_relative in fixture_refused.stdout, fixture_refused.stdout

    # --- REFUSING ARM 3, A THIRD SHAPE: a bound file DELETED. An `is_file()`
    # that was missing would make a deletion read as "no mismatch".
    missing = _frozen_byte_scratch(tmp_path / "missing")
    (missing / driver).unlink()
    deleted = _run_frozen_byte_guard(code, missing)
    assert deleted.returncode != 0, deleted.stdout
    assert driver in deleted.stdout, deleted.stdout


# ==========================================================================
# 62 — the ATTACK ITSELF, replayed: neutering the in-file digest reader must
#      no longer be invisible. 20s: two interpreter starts over a scratch tree.
# ==========================================================================


@pytest.mark.timeout(20)
def test_neutering_the_in_file_digest_reader_is_visible_to_the_external_guard(tmp_path):
    """The measured attack, driven end to end against the extracted CI guard.

    The attack was: replace ``test_manifest_digests_match_current_tracked_bytes``
    with ``assert True``, then corrupt a frozen fixture. Under the un-bound
    bytes the node reported 77 passed. Here the same two edits are applied to a
    scratch copy and the guard that lives OUTSIDE this file is asked.

    The neutering is written as a source edit rather than as a monkeypatch
    because that is the shape the attack used: bytes on disk, committed, read by
    CI. A monkeypatch would leave the file's digest unchanged and prove nothing.
    """
    code = _ci_frozen_byte_guard_command()
    driver = str(NODE_FILE.relative_to(REPO_ROOT))
    fixture = str((VALID_DIR / "packet.json").relative_to(REPO_ROOT))

    scratch = _frozen_byte_scratch(tmp_path)
    source = (scratch / driver).read_text(encoding="utf-8")
    marker = "def test_manifest_digests_match_current_tracked_bytes(tmp_path):"
    assert marker in source, "the digest reader was renamed; this control proves nothing"

    # --- INSTRUMENT CONTROL: before the attack, the guard permits.
    before = _run_frozen_byte_guard(code, scratch)
    assert before.returncode == 0, f"{before.stdout}{before.stderr}"

    # --- THE ATTACK: neuter the in-file reader, then corrupt a frozen fixture.
    neutered = source.replace(
        marker,
        marker + '\n    return  # NEUTERED BY THE ATTACK REPLAY',
        1,
    )
    assert neutered != source, "the neutering control changed nothing"
    (scratch / driver).write_text(neutered, encoding="utf-8")
    (scratch / fixture).write_bytes((scratch / fixture).read_bytes() + b"\n")

    after = _run_frozen_byte_guard(code, scratch)
    assert after.returncode != 0, (
        f"the attack is still invisible: {after.stdout}{after.stderr}"
    )
    # BOTH edits are named, not just the one the neutered test would have found.
    assert driver in after.stdout, after.stdout
    assert fixture in after.stdout, after.stdout


# 63 — a hostile value in a KNOWN `$defs/path_entry` field. The node is CLOSED
#      and the VALUES are open, so the packet its own schema accepts still
#      carries the subject's raw bytes, and the decision that OWNS the field
#      degrades to ERROR naming it. 20s: seven production-route captures.

#: ``(field, hostile value, the decision that owns it)``. `mode`, `uid` and
#: `acl_state` are D12's inside its scope — the general domain reader skips them
#: on a private-root entry so one bad value is named once — and the other four
#: belong to the general reader, which names them on D10.
_HOSTILE_KNOWN_FIELDS: tuple[tuple[str, Any, str], ...] = (
    ("kind", "wormhole", "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS"),
    ("sha256", 12345, "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS"),
    ("bytes", -1, "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS"),
    ("content_truncated", "yes", "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS"),
    ("mode", -7, "D12_MODE_OWNER_RECORDED_FAITHFULLY"),
    ("uid", -3, "D12_MODE_OWNER_RECORDED_FAITHFULLY"),
    ("acl_state", "MEASURED", "D12_MODE_OWNER_RECORDED_FAITHFULLY"),
)

#: An entry beneath `declared_writable_roots`, so D12 owns its three fields.
_PRIVATE_ROOT_ENTRY = "/proof/root/stream.jsonl"


@pytest.mark.timeout(20)
@pytest.mark.parametrize(
    ("field", "hostile", "owner"),
    _HOSTILE_KNOWN_FIELDS,
    ids=[name for name, _value, _owner in _HOSTILE_KNOWN_FIELDS],
)
def test_a_hostile_known_path_entry_value_is_forwarded_raw_and_degrades_its_owner(
    tmp_path: Path, field: str, hostile: Any, owner: str
) -> None:
    """Schema-valid, raw-preserved, and ERROR on the decision that reads it.

    Three facts have to hold TOGETHER, which is why one test asserts all three:
    a strict value schema here made the observer emit a packet its own schema
    REJECTED; a normaliser instead would have dropped or coerced the value and
    the finding with it; and naming a value without degrading the decision is
    how a discrepancy ships under a clean OBSERVED.
    """
    run_root = _make_run_root(tmp_path)
    inventory = run_root / "fs-inventory.json"
    document = json.loads(inventory.read_text(encoding="utf-8"))
    entry = document["post"]["entries"][_PRIVATE_ROOT_ENTRY]
    # INSTRUMENT CONTROL: the mutation must actually change the document, or
    # every assertion below would pass against an unmutated run.
    assert field in entry, (field, sorted(entry))
    assert entry[field] != hostile, (field, entry[field])
    entry[field] = hostile
    _write_json(inventory, document)

    text = _production_packet(run_root)
    packet = json.loads(text)

    assert list(_validator().iter_errors(packet)) == [], (
        f"{field}={hostile!r} made the observer emit a packet its own schema "
        f"rejects: {[e.message for e in _validator().iter_errors(packet)]}"
    )

    emitted = packet["observation"]["filesystem"]["post"]["entries"][
        _PRIVATE_ROOT_ENTRY
    ][field]
    assert emitted == hostile and type(emitted) is type(hostile), (
        f"{field} was reshaped in transit: recorded {hostile!r} "
        f"({type(hostile).__name__}), emitted {emitted!r} ({type(emitted).__name__})"
    )

    record = _decisions_by_id(text)[owner]
    assert record["observation_status"] == "ERROR", (
        f"{owner} read {record['observation_status']} over a recorded "
        f"{field}={hostile!r}: {record['discrepancies']}"
    )
    assert any(
        field in problem and repr(hostile) in problem
        for problem in record["discrepancies"]
    ), (field, hostile, record["discrepancies"])


# 64 — the closure the widening must NOT have cost: an UNKNOWN key in the same
#      $def is still refused by the real schema. 20s: two production captures.


@pytest.mark.timeout(20)
def test_an_unknown_path_entry_key_is_still_refused_while_its_value_survives(
    tmp_path: Path,
) -> None:
    """`additionalProperties: false` is what mutant M02 attacks; widening the
    seven VALUE schemas must leave it untouched.

    The permitting arm is not decoration: without it a schema that rejected
    everything would pass the refusing arm.
    """
    clean_text = _production_packet(_make_run_root(tmp_path / "clean"))
    assert list(_validator().iter_errors(json.loads(clean_text))) == []
    assert (
        _decisions_by_id(clean_text)["D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS"][
            "observation_status"
        ]
        == "OBSERVED"
    )

    run_root = _make_run_root(tmp_path / "unknown")
    inventory = run_root / "fs-inventory.json"
    document = json.loads(inventory.read_text(encoding="utf-8"))
    entry = document["post"]["entries"][_PRIVATE_ROOT_ENTRY]
    assert "wormhole" not in entry, sorted(entry)
    entry["wormhole"] = {"raw": [1, 2]}
    _write_json(inventory, document)

    text = _production_packet(run_root)
    packet = json.loads(text)

    assert list(_validator().iter_errors(packet)) != [], (
        "an unknown key inside $defs/path_entry was accepted — the closure "
        "mutant M02 attacks has been opened"
    )
    emitted = packet["observation"]["filesystem"]["post"]["entries"][
        _PRIVATE_ROOT_ENTRY
    ]["wormhole"]
    assert emitted == {"raw": [1, 2]}, emitted
    record = _decisions_by_id(text)["D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS"]
    assert record["observation_status"] == "ERROR", record


# ==========================================================================
# 65 — the source audit must not PERTURB the tree it digests. 20s: two child
#      interpreter starts over scratch copies of the subject.
# ==========================================================================


def _tree_state(root: Path) -> dict[str, str]:
    """Every path under ``root``: relative name -> content digest.

    Directories are recorded as ``"<dir>"`` so an ADDED directory is visible
    even while it is empty, and files by DIGEST so a same-name rewrite is
    visible too. Per-path rather than one hash over the whole tree: a folded
    digest can say "different" and name nothing.
    """
    state: dict[str, str] = {}
    for base, directories, files in os.walk(root):
        for name in directories:
            state[str((Path(base) / name).relative_to(root))] = "<dir>"
        for name in files:
            path = Path(base) / name
            state[str(path.relative_to(root))] = _sha256_path(path)
    return state


@pytest.mark.timeout(20)
def test_the_source_audit_leaves_no_trace_in_the_directory_it_audits(tmp_path):
    """The child that IMPORTS the subject cached bytecode into the subject's dir.

    THE CLASS THIS COVERS: a write performed by a CHILD PROCESS the observer
    spawns, into the tree the observer is measuring. ``__pycache__`` was the
    instance; the probe is a whole-tree before/after comparison, so any path a
    child adds, removes or rewrites is named whatever it happens to be called.
    Three claims rested on this and were false while it stood: the module
    docstring's "writes nothing at all outside a caller-supplied root", the
    ``capture()`` docstring's "invents no path and writes nothing", and
    ``allowed_persistent_write_roots``, which does not list this directory.

    WHY IT IS NOT AN IN-PROCESS PROBE: an import hook, an ``os`` patch or a
    ``sys.addaudithook`` in THIS process observes nothing on the far side of a
    ``subprocess.run``. The defect lived entirely in the child, so the
    mechanism has to be the filesystem itself.

    Measured cost of the fix: NONE. The audit returns the identical
    ``(findings, examined, audited)`` triple either way, so the purity buys no
    loss of fidelity — which the permitting arm below pins.
    """
    subject_dir = tmp_path / "audited"
    subject_dir.mkdir()
    shutil.copy2(OBSERVER_PATH, subject_dir / OBSERVER_PATH.name)
    shutil.copy2(SCHEMA_PATH, subject_dir / SCHEMA_PATH.name)
    before = _tree_state(subject_dir)
    assert set(before) == {OBSERVER_PATH.name, SCHEMA_PATH.name}, sorted(before)

    findings, examined, audited = observer._runtime_import_audit(
        subject_dir / OBSERVER_PATH.name
    )

    # --- PERMITTING ARM: the audit still READS. A guard that silently turned
    # the probe into a no-op would satisfy the comparison below trivially.
    assert audited is True, (findings, examined, audited)
    assert findings == [], findings
    assert examined > 0, examined

    # --- THE MEASUREMENT.
    after = _tree_state(subject_dir)
    assert after == before, (
        "the source audit perturbed the directory it audits: "
        f"added {sorted(set(after) - set(before))} "
        f"removed {sorted(set(before) - set(after))} "
        f"rewritten {sorted(k for k in set(after) & set(before) if after[k] != before[k])}"
    )

    # --- POSITIVE CONTROL, the EXACT defect shape replayed: the same child,
    # the same pruned env, with the guard removed. It must produce the write,
    # and the same comparison must name it. Without this the green above could
    # mean "children here never cache bytecode".
    replay_dir = tmp_path / "unguarded"
    replay_dir.mkdir()
    shutil.copy2(OBSERVER_PATH, replay_dir / OBSERVER_PATH.name)
    shutil.copy2(SCHEMA_PATH, replay_dir / SCHEMA_PATH.name)
    replay_before = _tree_state(replay_dir)
    unguarded = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "PYTHONHOME", "PYTHONDONTWRITEBYTECODE")
    }
    unguarded["PYTHONNOUSERSITE"] = "1"
    replay = subprocess.run(
        [sys.executable, "-S", "-c", f"import {OBSERVER_PATH.stem}"],
        cwd=str(replay_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=SUBPROCESS_TIMEOUT_S,
        env=unguarded,
    )
    assert replay.returncode == 0, f"{replay.stdout}{replay.stderr}"
    replay_after = _tree_state(replay_dir)
    added = sorted(set(replay_after) - set(replay_before))
    assert any(name.split(os.sep)[0] == "__pycache__" for name in added), (
        f"the replay wrote no bytecode cache, so this control proves nothing: {added}"
    )
    assert replay_after != replay_before

    # --- NEGATIVE CONTROL, a DIFFERENT shape from the bug: the bug ADDED
    # paths, so the control REWRITES one in place. The name set is untouched,
    # which is exactly what a filename-only comparison would miss.
    schema_copy = subject_dir / SCHEMA_PATH.name
    schema_copy.write_bytes(schema_copy.read_bytes() + b"\n")
    rewritten = _tree_state(subject_dir)
    assert set(rewritten) == set(before), sorted(set(rewritten) ^ set(before))
    assert rewritten != before
    assert rewritten[SCHEMA_PATH.name] != before[SCHEMA_PATH.name]

    # --- NEGATIVE CONTROL, a THIRD shape: a REMOVAL, which neither of the two
    # above covers.
    schema_copy.unlink()
    removed = _tree_state(subject_dir)
    assert set(before) - set(removed) == {SCHEMA_PATH.name}, sorted(removed)
    assert removed != before


# ==========================================================================
# 66 — identity and content are read by TWO syscalls, and the pair is
#      re-checked. 15s: four in-process walks over tiny scratch trees plus one
#      exec of a neutered copy of the module.
# ==========================================================================

#: The first line of the re-check branch, and the line that terminates it.
#: The neutering control below splices out everything between them, so the
#: "red before" arm is the SHIPPED code with exactly this branch removed
#: rather than a reimplementation of it written here.
_IDENTITY_RECHECK_HEAD = "            elif _identity_moved(path_str, st):\n"
_RECORD_EMIT_LINE = "        entries[os.path.normpath(path_str)] = {\n"


def _observer_without_the_identity_recheck() -> Any:
    """The shipped module with the identity re-check branch spliced out.

    A source edit rather than a monkeypatch, for the reason section 62 states:
    the defect being replayed lived in the bytes, so the replay has to be
    bytes. Executed into a private namespace, so nothing here disturbs the
    ``observer`` every other node in this file holds.
    """
    lines = OBSERVER_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    head = lines.index(_IDENTITY_RECHECK_HEAD)
    tail = lines.index(_RECORD_EMIT_LINE, head)
    neutered = "".join(lines[:head] + lines[tail:])
    assert tail > head, "the branch terminator precedes the branch; the splice is wrong"
    assert _IDENTITY_RECHECK_HEAD not in neutered, "the splice removed nothing"
    assert _RECORD_EMIT_LINE in neutered, "the splice ate the entry emission too"
    namespace: dict[str, Any] = {
        "__name__": "observe_claude_execution__unguarded",
        "__file__": str(OBSERVER_PATH),
    }
    exec(compile(neutered, str(OBSERVER_PATH), "exec"), namespace)  # noqa: S102
    return namespace


def _lstat_that_swaps_once(target: str, fired: list[str], swap: Callable[[], None]):
    """An ``os.lstat`` that performs ``swap`` immediately after the FIRST read.

    This is the race, made deterministic: the identity read returns the state
    the file was in, and by the time the caller opens the path for content it
    is a different file. It fires ONCE, so the re-check the fix adds sees the
    real post-swap state rather than a third fabricated one.
    """
    real = os.lstat

    def fake(path, *args, **kwargs):
        result = real(path, *args, **kwargs)
        if str(path) == target and not fired:
            fired.append(str(path))
            swap()
        return result

    return fake


def _swap_root(tmp_path: Path, name: str, content: bytes, mode: int) -> tuple[Path, str]:
    """A one-file scratch root plus the exact path string the walk will use."""
    root = tmp_path / name
    root.mkdir()
    subject = root / "subject.txt"
    subject.write_bytes(content)
    os.chmod(subject, mode)
    (root / "bystander.txt").write_bytes(b"untouched by any race\n")
    return root, os.path.join(str(root), "subject.txt")


@pytest.mark.timeout(15)
def test_a_file_swapped_between_the_identity_read_and_the_digest_is_not_published_as_one(
    tmp_path, monkeypatch
):
    """One entry may not mix pre-change metadata with post-change bytes.

    THE CLASS THIS COVERS: an observation assembled from TWO syscalls with
    nothing binding them together. The walk takes identity from ``os.lstat``
    and content from a separate ``open``, and between the two the subject may
    become a different file. The emitted entry then describes a state the
    filesystem was never in — and it reported ``OBSERVED``, with no flag and
    no degrade, because every channel that could have said otherwise was
    reading a bound that had not fired.

    WHY IT MATTERS THAT NOTHING CALLS THE WALK YET: it is PROVIDED and not
    USED, which is exactly why the defect must not be frozen in. The rung that
    performs the real pre/post walk inherits whatever is sitting here.

    THE POLARITY IS THE ONE ALREADY IN THIS FUNCTION, not a new one.
    ``_bounded_evidence`` ranks a defeated reader ``ERROR`` and a partial
    measurement ``UNMEASURED``; the walk answers every degradation it performs
    with ``UNMEASURED`` — an ``os.lstat`` failure and a failed digest both — and
    ``_filesystem_planes`` states that contract in a comment that folds it.
    A read that SUCCEEDED but could not be tied to the identity beside it is a
    measurement that did not complete, not a reader that was defeated, so it
    joins the two answers already there rather than inventing a third.
    """
    # --- INSTRUMENT CONTROL, on the predicate itself, in BOTH directions
    # before it is trusted anywhere below. A predicate that always answered
    # True would make every refusing arm green for the wrong reason, and one
    # that always answered False would make the permitting arm green the same
    # way.
    probe = tmp_path / "predicate-probe.txt"
    probe.write_bytes(b"first")
    before_stat = os.lstat(str(probe))
    assert observer._identity_moved(str(probe), before_stat) is False
    probe.write_bytes(b"second, and longer than the first")
    assert observer._identity_moved(str(probe), before_stat) is True
    probe.unlink()
    assert observer._identity_moved(str(probe), before_stat) is True

    # --- PERMITTING ARM: a tree nobody races reads OBSERVED, and every digest
    # matches the harness's own oracle. Without this the refusals below could
    # mean "the walk degrades everything".
    calm_root, _calm_target = _swap_root(tmp_path, "calm", b"stable bytes\n", 0o644)
    calm = observer.inventory(calm_root)
    assert calm["observation_status"] == observer.OBSERVED, calm["observation_status"]
    for name in ("subject.txt", "bystander.txt"):
        entry = calm["entries"][os.path.normpath(str(calm_root / name))]
        assert entry["sha256"] == _sha256_path(calm_root / name), (name, entry)
        assert entry["bytes"] == (calm_root / name).stat().st_size, (name, entry)
        assert entry["content_truncated"] is False

    # --- THE REPRODUCER, and first the POSITIVE CONTROL that it is a real
    # race: the SAME harness against the shipped module with the re-check
    # branch spliced out must publish the hybrid. This is the red-before arm,
    # run as bytes rather than asserted in prose.
    pre_mode, post_mode = 0o644, 0o600
    pre_bytes = b"the bytes the identity read described\n"
    post_bytes = b"different bytes, and a different length entirely, after the swap\n"
    assert len(pre_bytes) != len(post_bytes), "the swap must be visible in st_size"

    unguarded_root, unguarded_target = _swap_root(tmp_path, "unguarded", pre_bytes, pre_mode)

    def content_swap(target: str) -> Callable[[], None]:
        def swap() -> None:
            with open(target, "wb") as handle:
                handle.write(post_bytes)
            os.chmod(target, post_mode)

        return swap

    unguarded_fired: list[str] = []
    monkeypatch.setattr(
        os,
        "lstat",
        _lstat_that_swaps_once(unguarded_target, unguarded_fired, content_swap(unguarded_target)),
    )
    unguarded_entry = _observer_without_the_identity_recheck()["inventory"](unguarded_root)
    monkeypatch.undo()
    assert unguarded_fired == [unguarded_target], unguarded_fired
    hybrid = unguarded_entry["entries"][os.path.normpath(unguarded_target)]
    assert hybrid["mode"] == pre_mode, hybrid
    assert hybrid["sha256"] == hashlib.sha256(post_bytes).hexdigest(), hybrid
    assert hybrid["bytes"] == len(post_bytes), hybrid
    assert unguarded_entry["observation_status"] == observer.OBSERVED, unguarded_entry[
        "observation_status"
    ]

    # --- REFUSING ARM 1, the same harness against the SHIPPED module.
    guarded_root, guarded_target = _swap_root(tmp_path, "guarded", pre_bytes, pre_mode)
    guarded_fired: list[str] = []
    monkeypatch.setattr(
        os,
        "lstat",
        _lstat_that_swaps_once(guarded_target, guarded_fired, content_swap(guarded_target)),
    )
    guarded = observer.inventory(guarded_root)
    monkeypatch.undo()
    assert guarded_fired == [guarded_target], guarded_fired
    raced = guarded["entries"][os.path.normpath(guarded_target)]
    assert raced["kind"] == "file", raced
    assert raced["sha256"] is None, raced
    assert raced["bytes"] is None, raced
    assert raced["content_truncated"] is False, raced
    assert guarded["observation_status"] == observer.UNMEASURED, guarded["observation_status"]
    # NEITHER cap fired, so the truncation channel cannot be what carried this.
    assert guarded["entry_truncated"] is False and guarded["member_bytes_truncated"] is False
    # The path keeps its place in the walk: a degrade, not a disappearance.
    assert os.path.normpath(guarded_target) in guarded["entries"]
    # And the entry stays inside the domain the closed schema declares for it.
    assert observer._path_entry_domain_problems("subject.txt", raced) == []
    # The bystander is untouched, so the degrade is per-entry for CONTENT even
    # though the status it folds is walk-wide.
    bystander = guarded["entries"][os.path.normpath(str(guarded_root / "bystander.txt"))]
    assert bystander["sha256"] == _sha256_path(guarded_root / "bystander.txt")

    # --- REFUSING ARM 2, a DIFFERENT SHAPE: the bytes do not change at all.
    # A donor file carrying the IDENTICAL content is renamed over the subject,
    # so size and digest are unchanged and only the inode moved. A guard that
    # compared content would see nothing here.
    twin_root, twin_target = _swap_root(tmp_path, "twin", pre_bytes, pre_mode)
    donor = tmp_path / "donor-outside-the-walked-root.txt"
    donor.write_bytes(pre_bytes)
    assert os.lstat(str(donor)).st_ino != os.lstat(twin_target).st_ino
    twin_fired: list[str] = []
    monkeypatch.setattr(
        os,
        "lstat",
        _lstat_that_swaps_once(twin_target, twin_fired, lambda: os.replace(donor, twin_target)),
    )
    twin = observer.inventory(twin_root)
    monkeypatch.undo()
    assert twin_fired == [twin_target], twin_fired
    assert _sha256_path(Path(twin_target)) == hashlib.sha256(pre_bytes).hexdigest(), (
        "the donor did not carry identical bytes; this arm is not the shape it claims"
    )
    swapped = twin["entries"][os.path.normpath(twin_target)]
    assert swapped["sha256"] is None, swapped
    assert twin["observation_status"] == observer.UNMEASURED

    # --- REFUSING ARM 3, a THIRD SHAPE: the subject is TRUNCATED to nothing
    # rather than rewritten or replaced. The read still succeeds and returns a
    # perfectly valid digest — of a file that no longer matches its identity.
    cut_root, cut_target = _swap_root(tmp_path, "truncated", pre_bytes, pre_mode)
    cut_fired: list[str] = []
    monkeypatch.setattr(
        os,
        "lstat",
        _lstat_that_swaps_once(cut_target, cut_fired, lambda: os.truncate(cut_target, 0)),
    )
    cut = observer.inventory(cut_root)
    monkeypatch.undo()
    assert cut_fired == [cut_target], cut_fired
    clipped = cut["entries"][os.path.normpath(cut_target)]
    assert clipped["sha256"] is None, clipped
    assert cut["observation_status"] == observer.UNMEASURED

    # --- PERMITTING CONTROL OF THE HARNESS ITSELF, the discrimination arm: the
    # same monkeypatched lstat installed against a path that is never walked
    # fires nothing, and the walk reads OBSERVED. The three refusals above are
    # therefore about the race and not about the patch being installed.
    inert_root, _inert_target = _swap_root(tmp_path, "inert", pre_bytes, pre_mode)
    inert_fired: list[str] = []
    monkeypatch.setattr(
        os,
        "lstat",
        _lstat_that_swaps_once(
            str(tmp_path / "never-walked"), inert_fired, lambda: None
        ),
    )
    inert = observer.inventory(inert_root)
    monkeypatch.undo()
    assert inert_fired == [], inert_fired
    assert inert["observation_status"] == observer.OBSERVED, inert["observation_status"]


# ==========================================================================
# 67 — the import-audit child environment is an ALLOWLIST. 20s: two real
#      child interpreter starts for the fidelity arm, plus capture-only work.
# ==========================================================================

#: A name invented HERE and present nowhere in the observer. The point of the
#: arm that uses it: a stoplist can only refuse names someone thought of, so a
#: guard proved against LD_PRELOAD alone is scoped to LD_PRELOAD. This one
#: cannot have been enumerated, because it did not exist when the code was
#: written.
_UNENUMERATED_HOSTILE_NAME = "QZ_VARIABLE_NOBODY_WROTE_DOWN_1760"

#: The four the audit MEASURED surviving the old stoplist. Kept as the
#: reproducer's own shape, beside — never instead of — the invented name.
_MEASURED_SURVIVORS = (
    "LD_PRELOAD",
    "DYLD_INSERT_LIBRARIES",
    "PYTHONBREAKPOINT",
    "PYTHONSTARTUP",
)

#: The stoplist the audit used to build its child environment, reconstructed
#: here so the leak it permitted can be MEASURED rather than described.
def _legacy_stoplist_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


@pytest.mark.timeout(20)
def test_the_import_audit_child_environment_is_an_allowlist_not_a_stoplist(
    tmp_path, monkeypatch
):
    """What reaches the audit's child is named, not inherited-minus-a-list.

    THE CLASS THIS COVERS: a hardening step written as a SUBTRACTION. Removing
    two names from ``os.environ`` refuses exactly those two, and every variable
    nobody listed is admitted by default — including the two the ``-S`` flag
    beside it cannot touch at all, since the dynamic linker acts before the
    interpreter starts and has never heard of ``site``. Not reachable through
    any input this rung accepts; it is written because the paragraph around the
    construction calls itself hardening, and a reader is entitled to find an
    allowlist behind that word.

    THE CATEGORY, NOT THE MEMBERS. The refusing arm drives an invented name
    that appears nowhere in the observer alongside the four that were measured
    surviving, and the assertion is a SUBSET over the whole captured
    environment rather than four absences. A guard that enumerated today's
    members would pass the four and fail the invented one.

    THE FIDELITY ARM is the one that makes this free: the audit is run twice
    through its own code path, once under the shipped allowlist and once with
    the legacy environment forced back in, and the two triples must be equal.
    An allowlist that cost a reading would be a worse trade than the leak.
    """
    subject = tmp_path / "audited" / OBSERVER_PATH.name
    subject.parent.mkdir()
    shutil.copy2(OBSERVER_PATH, subject)
    shutil.copy2(SCHEMA_PATH, subject.parent / SCHEMA_PATH.name)

    # --- FIDELITY ARM, run BEFORE anything hostile is placed in the
    # environment so no child is ever started under an injected loader
    # variable. Both readings go through the shipped `_runtime_import_audit`;
    # only the environment it hands the child differs.
    guarded_result = observer._runtime_import_audit(subject)
    real_run = subprocess.run

    def run_with_legacy_env(*args, **kwargs):
        kwargs["env"] = _legacy_stoplist_env()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(observer.subprocess, "run", run_with_legacy_env)
    legacy_result = observer._runtime_import_audit(subject)
    monkeypatch.undo()

    # PERMITTING ARM: the audit still READS. A hardening step that quietly
    # turned the probe into a no-op would satisfy every absence below.
    findings, examined, audited = guarded_result
    assert audited is True, guarded_result
    assert findings == [], findings
    assert examined > 0, examined
    assert guarded_result == legacy_result, (guarded_result, legacy_result)

    # --- THE ENVIRONMENT THE SHIPPED CODE BUILDS, captured from the shipped
    # code rather than reconstructed here. The child is never started for this
    # arm: the stub answers with a well-formed payload, so the function runs to
    # completion over exactly the env it constructed.
    monkeypatch.setenv(_UNENUMERATED_HOSTILE_NAME, "/tmp/nothing-loads-this.so")
    for name in _MEASURED_SURVIVORS:
        monkeypatch.setenv(name, "/tmp/nothing-loads-this.so")

    captured: dict[str, dict[str, str]] = {}

    def capture_only(*args, **kwargs):
        captured["env"] = dict(kwargs["env"])
        return subprocess.CompletedProcess(
            args=list(args[0]) if args else [],
            returncode=0,
            stdout='{"examined": 1, "foreign": []}',
            stderr="",
        )

    monkeypatch.setattr(observer.subprocess, "run", capture_only)
    assert observer._runtime_import_audit(subject) == ([], 1, True)
    monkeypatch.setattr(observer.subprocess, "run", real_run)
    child_env = captured["env"]

    # --- POSITIVE CONTROL OF THE INSTRUMENT, and the red-before arm in one:
    # the SAME environment through the OLD construction really does carry every
    # one of these names. Without it, the absences below could mean the
    # variables were never set, or that set-membership over `child_env` cannot
    # see anything at all.
    leaked = _legacy_stoplist_env()
    for name in (_UNENUMERATED_HOSTILE_NAME, *_MEASURED_SURVIVORS):
        assert name in leaked, f"{name} did not survive the old stoplist; nothing is proven"
    assert leaked["PYTHONNOUSERSITE"] == "1", leaked["PYTHONNOUSERSITE"]

    # --- REFUSING ARM, stated as a CATEGORY: the child's environment is a
    # subset of what the source names, so nothing else can be in it whatever it
    # is called. The invented name is inside that claim by construction.
    permitted = {"PATH", "HOME", "TMPDIR", "SYSTEMROOT",
                 "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE"}
    assert set(child_env) <= permitted, sorted(set(child_env) - permitted)
    assert _UNENUMERATED_HOSTILE_NAME not in child_env
    assert not set(_MEASURED_SURVIVORS) & set(child_env)

    # THE INVENTED NAME IS GENUINELY UNENUMERATED: it appears nowhere in the
    # observer, so no member list can be what refused it.
    assert _UNENUMERATED_HOSTILE_NAME not in OBSERVER_PATH.read_text(encoding="utf-8")

    # --- PERMITTING ARM ON THE ENVIRONMENT: the two hardening settings really
    # are handed to the child, and PATH — the one location the allowlist keeps
    # that the ambient environment always supplies — survives. An "allowlist"
    # that admitted nothing would satisfy the subset above trivially.
    assert child_env["PYTHONNOUSERSITE"] == "1"
    assert child_env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert child_env.get("PATH") == os.environ["PATH"]

    # --- NEGATIVE CONTROL, a DIFFERENT SHAPE from "a hostile name is absent":
    # a name ON the allowlist that is ABSENT from the parent must not be
    # invented for the child. The construction copies values, it does not
    # fabricate them.
    monkeypatch.delenv("TMPDIR", raising=False)
    captured.clear()
    monkeypatch.setattr(observer.subprocess, "run", capture_only)
    assert observer._runtime_import_audit(subject) == ([], 1, True)
    monkeypatch.setattr(observer.subprocess, "run", real_run)
    assert "TMPDIR" not in captured["env"], sorted(captured["env"])
    assert captured["env"]["PYTHONDONTWRITEBYTECODE"] == "1"

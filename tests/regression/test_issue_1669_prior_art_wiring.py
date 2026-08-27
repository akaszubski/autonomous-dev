"""Regression tests for Issue #1669: the prior-art search must actually FIRE.

``plugins/autonomous-dev/lib/prior_art_search.py`` shipped green, registered
in the install manifest, and with ZERO production consumers — its only
callers were its own ``_main`` and its own regression suite. This file locks
the *wiring* half: STEP 4.9 of ``commands/implement.md`` must run the search
mechanically and its result must reach the planner prompt.

Design note — why these tests EXECUTE the command file instead of grepping
it: a test asserting the string ``search_prior_art`` appears in
``implement.md`` passes while the call never fires, which is precisely the
class of defect being fixed. ``_extract_block()`` pulls the block out of the
command file and RUNS it, with a witness-recording stub standing in for the
library. ``test_prose_only_block_fails_the_same_harness`` is the negative
control: a block that merely *mentions* the function writes no witness and
is refused by the same harness that accepts the real one.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
REAL_MODULE = REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "prior_art_search.py"

BEGIN_MARKER = "# BEGIN PRIOR-ART-SEARCH (Issue #1669)"
END_MARKER = "# END PRIOR-ART-SEARCH"

_MUTATION_HIT = {
    "number": 770,
    "title": "Add mutation testing (mutmut) to validate test quality on lib/",
    "state": "CLOSED",
    "closedAt": "2026-04-11T00:00:00Z",
}

# A stub that records the exact arguments the wiring passed, so the tests can
# prove the call FIRED (witness file exists) and prove WHAT it was given.
_STUB_TEMPLATE = '''\
import json
import os
from pathlib import Path

_HITS = json.loads("""__HITS_JSON__""")


def search_prior_art(keywords, repo_root=None):
    Path(os.environ["PRIOR_ART_WITNESS"]).write_text(
        json.dumps({"keywords": list(keywords), "repo_root": str(repo_root)})
    )
    return _HITS
'''


def _stub_source(hits: list) -> str:
    """Render the witness-recording stub with a fixed return value."""

    return _STUB_TEMPLATE.replace("__HITS_JSON__", json.dumps(hits))

# A block that MENTIONS the function but never invokes it. The negative
# control: the harness must refuse this while accepting the real block.
_PROSE_ONLY_BLOCK = f"""{BEGIN_MARKER}
# The coordinator should call search_prior_art before dispatching the planner.
PRIOR_ART_BLOCK="prior art: see search_prior_art"
echo "$PRIOR_ART_BLOCK"
{END_MARKER}
"""


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------
def _extract_block(content: str | None = None) -> str:
    """Return the executable body between the BEGIN/END markers."""

    text = IMPLEMENT_MD.read_text() if content is None else content
    start = text.index(BEGIN_MARKER) + len(BEGIN_MARKER)
    end = text.index(END_MARKER, start)
    return text[start:end]


def _make_repo(tmp_path: Path, *, stub_hits: list | None = None, real: bool = False) -> Path:
    """Create an isolated git repo, optionally seeded with a lib module."""

    repo = tmp_path / "repo"
    (repo / ".claude" / "lib").mkdir(parents=True)
    (repo / "README.md").write_text("seed\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=repo,
        check=True,
    )

    module = repo / ".claude" / "lib" / "prior_art_search.py"
    if real:
        shutil.copy2(REAL_MODULE, module)
    elif stub_hits is not None:
        module.write_text(_stub_source(stub_hits))
    else:
        module.unlink(missing_ok=True)
    return repo


def _run_block(
    tmp_path: Path,
    repo: Path,
    *,
    query: str | None,
    feature_description: str | None = None,
    cwd: Path | None = None,
    block: str | None = None,
    path_prefix: Path | None = None,
) -> tuple[subprocess.CompletedProcess, Path]:
    """Execute the extracted block and return (result, witness_path).

    ``query`` drives ``ISSUE_TITLE`` (the ``--issues`` path);
    ``feature_description`` drives ``FEATURE_DESCRIPTION`` (the bare
    ``/implement "<description>"`` path). Both default to absent, so every
    test states the exact environment it depends on.
    """

    tmp_path.mkdir(parents=True, exist_ok=True)
    script = tmp_path / "block.sh"
    script.write_text(_extract_block() if block is None else _extract_block(block))

    witness = tmp_path / "witness.json"
    isolated_home = tmp_path / "home"
    isolated_home.mkdir(exist_ok=True)

    env = dict(os.environ)
    # HOME isolation is load-bearing: this machine has a real
    # ~/.claude/lib/prior_art_search.py that would otherwise be imported and
    # would shell out to gh for real.
    env["HOME"] = str(isolated_home)
    if query is None:
        env.pop("ISSUE_TITLE", None)
    else:
        env["ISSUE_TITLE"] = query
    if feature_description is None:
        env.pop("FEATURE_DESCRIPTION", None)
    else:
        env["FEATURE_DESCRIPTION"] = feature_description
    env["PRIOR_ART_WITNESS"] = str(witness)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(script)],
        cwd=str(cwd or repo),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env=env,
    )
    return result, witness


def _keywords_searched(stdout: str) -> list[str]:
    """Return the keywords the emitted block reports it searched."""

    for line in stdout.splitlines():
        if line.startswith("KEYWORDS-SEARCHED:"):
            return [k.strip() for k in line.split(":", 1)[1].split(",") if k.strip()]
    raise AssertionError(f"no 'KEYWORDS-SEARCHED:' line in output:\n{stdout}")


def _status_line(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("PRIOR ART:"):
            return line
    raise AssertionError(f"no 'PRIOR ART:' status line in output:\n{stdout}")


# ---------------------------------------------------------------------------
# HITS arm — the result must reach the constructed planner block.
# ---------------------------------------------------------------------------
def test_hits_arm_surfaces_issue_770_in_the_planner_block(tmp_path: Path) -> None:
    """The #770 case: 'mutation testing' must appear in the emitted block."""

    repo = _make_repo(tmp_path, stub_hits=[_MUTATION_HIT])
    result, witness = _run_block(tmp_path, repo, query="mutation testing")

    assert result.returncode == 0, result.stderr
    assert witness.exists(), (
        "search_prior_art was never called — the block did not fire.\n"
        f"stdout:\n{result.stdout}"
    )
    # Assert on the PROMPT TEXT, not on the library return value: the defect
    # was that the return value never reached a consumer.
    assert "PRIOR ART: HITS (1)" in result.stdout, result.stdout
    assert "#770" in result.stdout, result.stdout
    assert "Add mutation testing (mutmut)" in result.stdout, result.stdout
    assert "SEARCH-EXECUTED: yes" in result.stdout, result.stdout


def test_hits_arm_passes_derived_keywords_to_the_library(tmp_path: Path) -> None:
    """Keywords must be derived from the feature description in scope."""

    repo = _make_repo(tmp_path, stub_hits=[_MUTATION_HIT])
    _, witness = _run_block(tmp_path, repo, query="mutation testing")

    recorded = json.loads(witness.read_text())
    assert recorded["keywords"][0] == "mutation testing"
    assert "mutation" in recorded["keywords"]
    assert 1 <= len(recorded["keywords"]) <= 3, recorded["keywords"]


# ---------------------------------------------------------------------------
# FEATURE_DESCRIPTION arm — the PRIMARY /implement "<description>" path.
#
# ISSUE_TITLE (--issues) is the secondary path and was the only one with a
# success-path test. The bare-description form is the one most runs take, and
# an untested primary path that looks fine is the exact defect class #1669
# exists to close.
# ---------------------------------------------------------------------------
def test_feature_description_path_fires_the_search_and_reaches_the_block(
    tmp_path: Path,
) -> None:
    """FEATURE_DESCRIPTION set, ISSUE_TITLE absent: the search must FIRE.

    Mirrors ``test_hits_arm_*`` on the other branch of
    ``${ISSUE_TITLE:-${FEATURE_DESCRIPTION:-}}``: the call fires (witness),
    the keywords are derived from the description, and the hit reaches the
    EMITTED BLOCK TEXT — not merely the library return value, which is the
    half that #1669 records as never having had a consumer.
    """

    repo = _make_repo(tmp_path, stub_hits=[_MUTATION_HIT])
    result, witness = _run_block(
        tmp_path,
        repo,
        query=None,
        feature_description="mutation testing for the lib directory",
    )

    assert result.returncode == 0, result.stderr
    assert witness.exists(), (
        "search_prior_art never fired on the FEATURE_DESCRIPTION path.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "STEP 4.9 REQUIREMENT UNMET" not in result.stderr, result.stderr

    # Keywords derived from the DESCRIPTION, in the library call...
    recorded = json.loads(witness.read_text())["keywords"]
    assert recorded[0] == "mutation testing for the lib directory", recorded
    assert "mutation" in recorded, recorded
    assert 1 <= len(recorded) <= 3, recorded

    # ...and reported identically in the emitted block.
    assert _keywords_searched(result.stdout) == recorded, result.stdout

    # The hit reaches the PROMPT TEXT, which is the consumer that was missing.
    assert "SEARCH-EXECUTED: yes" in result.stdout, result.stdout
    assert "PRIOR ART: HITS (1)" in result.stdout, result.stdout
    assert "#770" in result.stdout, result.stdout
    assert "Add mutation testing (mutmut)" in result.stdout, result.stdout


def test_issue_title_wins_when_both_are_set(tmp_path: Path) -> None:
    """Precedence control: ``${ISSUE_TITLE:-${FEATURE_DESCRIPTION:-}}``.

    Negative control for the test above, of the opposite shape: without it a
    harness that ALWAYS used FEATURE_DESCRIPTION would pass that test for the
    wrong reason. Here the two variables carry disjoint vocabularies, so the
    searched keywords name which one actually won.
    """

    repo = _make_repo(tmp_path, stub_hits=[_MUTATION_HIT])
    result, witness = _run_block(
        tmp_path,
        repo,
        query="mutation testing",
        feature_description="quantum flux capacitor calibration",
    )

    assert result.returncode == 0, result.stderr
    assert witness.exists(), result.stdout

    recorded = json.loads(witness.read_text())["keywords"]
    assert recorded[0] == "mutation testing", recorded
    assert "mutation" in recorded, recorded
    # FEATURE_DESCRIPTION must NOT have contributed a single token.
    for loser in ("quantum", "flux", "capacitor", "calibration"):
        assert loser not in " ".join(recorded).lower(), recorded
        assert loser not in _keywords_searched(result.stdout)[0].lower(), result.stdout


def test_empty_feature_description_is_treated_as_absent(tmp_path: Path) -> None:
    """``${VAR:-}`` collapses empty and unset — assert it, don't imply it.

    An exported-but-empty FEATURE_DESCRIPTION is the realistic near-miss (a
    coordinator that exports the variable before computing its value). It must
    take the loud REQUIREMENT-UNMET path, not silently search for nothing.
    """

    repo = _make_repo(tmp_path, stub_hits=[_MUTATION_HIT])
    empty, empty_witness = _run_block(
        tmp_path, repo, query=None, feature_description=""
    )

    assert empty.returncode == 0, "an empty query MUST NOT block the pipeline"
    assert "STEP 4.9 REQUIREMENT UNMET" in empty.stderr, empty.stderr
    assert "SEARCH-EXECUTED: no" in empty.stdout, empty.stdout
    assert not empty_witness.exists(), "an empty description must not search"

    # Same harness, same repo, one character of difference: non-empty fires.
    # Without this arm the assertions above would hold for a block that never
    # searches at all.
    nonempty, nonempty_witness = _run_block(
        tmp_path / "nonempty",
        repo,
        query=None,
        feature_description="mutation testing for the lib directory",
    )
    assert nonempty_witness.exists(), nonempty.stdout
    assert "SEARCH-EXECUTED: yes" in nonempty.stdout, nonempty.stdout


# ---------------------------------------------------------------------------
# PERMITTING arm — an empty result is legitimate and MUST NOT block.
# ---------------------------------------------------------------------------
def test_permitting_arm_empty_result_does_not_block_the_pipeline(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, stub_hits=[])
    result, witness = _run_block(
        tmp_path, repo, query="quantum flux capacitor calibration"
    )

    assert result.returncode == 0, result.stderr
    assert witness.exists(), "the search must still have run for a novel topic"
    assert "SEARCH-EXECUTED: yes" in result.stdout, result.stdout
    assert "PRIOR ART: UNKNOWN — 0 hits returned." in result.stdout, result.stdout
    assert "KEYWORDS-SEARCHED:" in result.stdout, result.stdout


def test_searched_and_found_nothing_is_distinguishable_from_never_ran(
    tmp_path: Path,
) -> None:
    """The all-skipped-green guard: the two empties must not look identical."""

    searched_repo = _make_repo(tmp_path / "a", stub_hits=[])
    searched, searched_witness = _run_block(
        tmp_path / "a", searched_repo, query="quantum flux capacitor"
    )

    # No module anywhere: not in the repo, and HOME is isolated.
    absent_repo = _make_repo(tmp_path / "b")
    never_ran, never_ran_witness = _run_block(
        tmp_path / "b", absent_repo, query="quantum flux capacitor"
    )

    assert searched_witness.exists()
    assert not never_ran_witness.exists()

    assert "SEARCH-EXECUTED: yes" in searched.stdout, searched.stdout
    assert "SEARCH-EXECUTED: no" in never_ran.stdout, never_ran.stdout
    assert searched.stdout != never_ran.stdout
    # Both are exit 0 — neither may block the pipeline.
    assert searched.returncode == 0 and never_ran.returncode == 0


# ---------------------------------------------------------------------------
# The contract: HITS or UNKNOWN, never ABSENT.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "stub_hits,query",
    [
        ([_MUTATION_HIT], "mutation testing"),
        ([], "quantum flux capacitor calibration"),
        (None, "quantum flux capacitor calibration"),
    ],
)
def test_status_is_only_ever_hits_or_unknown(
    tmp_path: Path, stub_hits: list | None, query: str
) -> None:
    """A false mechanical 'nothing exists' is worse than a hedged guess."""

    repo = _make_repo(tmp_path, stub_hits=stub_hits)
    result, _ = _run_block(tmp_path, repo, query=query)

    status = _status_line(result.stdout)
    assert re.match(r"^PRIOR ART: (HITS \(\d+\)|UNKNOWN)", status), status
    for forbidden in ("PRIOR ART: ABSENT", "PRIOR ART: NONE", "PRIOR ART: NO "):
        assert forbidden not in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# NEGATIVE CONTROL of a different shape — presence is not reachability.
# ---------------------------------------------------------------------------
def test_prose_only_block_fails_the_same_harness(tmp_path: Path) -> None:
    """A block that only MENTIONS search_prior_art must write no witness.

    This is the control that makes the other tests mean something: a
    grep-for-the-string test would pass on this input. The harness must
    refuse it while accepting the real block.
    """

    repo = _make_repo(tmp_path, stub_hits=[_MUTATION_HIT])
    result, witness = _run_block(
        tmp_path, repo, query="mutation testing", block=_PROSE_ONLY_BLOCK
    )

    # The string IS present in the prose block...
    assert "search_prior_art" in _PROSE_ONLY_BLOCK
    # ...and the call still never fired.
    assert not witness.exists(), "prose must not be able to satisfy this harness"
    assert "PRIOR ART: HITS" not in result.stdout

    # POSITIVE arm of the same harness, same tmp dir, same repo: the real
    # block DOES fire. Both arms observed in one test.
    real_result, real_witness = _run_block(
        tmp_path / "real", repo, query="mutation testing"
    )
    assert real_witness.exists()
    assert "PRIOR ART: HITS (1)" in real_result.stdout, real_result.stdout


# ---------------------------------------------------------------------------
# Issue #1064 class — runtime kwarg correctness, not static shape.
# ---------------------------------------------------------------------------
def test_repo_root_is_git_toplevel_not_process_cwd(tmp_path: Path) -> None:
    """The repo_root handed to the library must be the git toplevel.

    Negative control: run from a nested subdirectory, where a naive
    ``Path.cwd()`` implementation would record the subdirectory instead.
    """

    repo = _make_repo(tmp_path, stub_hits=[])
    nested = repo / "plugins" / "autonomous-dev"
    nested.mkdir(parents=True)

    _, witness = _run_block(
        tmp_path, repo, query="mutation testing", cwd=nested
    )

    recorded = os.path.realpath(json.loads(witness.read_text())["repo_root"])
    assert recorded == os.path.realpath(repo), recorded
    assert recorded != os.path.realpath(nested), (
        "repo_root followed the process cwd — the Issue #1064 failure shape"
    )


def test_git_toplevel_probe_has_a_negative_control(tmp_path: Path) -> None:
    """Outside a git repo the block still runs and still degrades cleanly.

    Positive/negative control for the ``git rev-parse`` probe itself: inside
    a repo it resolves a toplevel (asserted above); outside one it must fall
    back to cwd rather than crash.
    """

    not_a_repo = tmp_path / "loose"
    (not_a_repo / ".claude" / "lib").mkdir(parents=True)
    (not_a_repo / ".claude" / "lib" / "prior_art_search.py").write_text(
        _stub_source([])
    )

    result, witness = _run_block(
        tmp_path, not_a_repo, query="mutation testing", cwd=not_a_repo
    )

    assert result.returncode == 0, result.stderr
    assert witness.exists(), result.stdout
    recorded = os.path.realpath(json.loads(witness.read_text())["repo_root"])
    assert recorded == os.path.realpath(not_a_repo), recorded


# ---------------------------------------------------------------------------
# Network tolerance must be INHERITED by the wiring, not just claimed.
# ---------------------------------------------------------------------------
def test_unauthenticated_gh_degrades_without_hanging(tmp_path: Path) -> None:
    """Real module + a failing ``gh``: exit 0, UNKNOWN, and fast."""

    repo = _make_repo(tmp_path, real=True)
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    gh_shim = shim_dir / "gh"
    gh_shim.write_text(
        "#!/bin/sh\necho 'gh: To get started with GitHub CLI, run gh auth login.' >&2\nexit 4\n"
    )
    gh_shim.chmod(gh_shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    started = time.monotonic()
    result, _ = _run_block(
        tmp_path,
        repo,
        query="quantum flux capacitor calibration",
        path_prefix=shim_dir,
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stderr
    assert "SEARCH-EXECUTED: yes" in result.stdout, result.stdout
    assert "PRIOR ART: UNKNOWN" in result.stdout, result.stdout
    assert elapsed < 60, f"degraded path took {elapsed:.1f}s — pipeline hang risk"


# ---------------------------------------------------------------------------
# Structural: the step exists, runs before the planner, and feeds it.
# ---------------------------------------------------------------------------
def test_missing_query_warns_loudly_and_still_does_not_block(tmp_path: Path) -> None:
    """The non-issue path must fail LOUDLY, never silently do nothing.

    ISSUE_TITLE is set only on the issue path. Without a loud signal, the
    non-issue path would reproduce #1669 exactly: a shipped mechanism that
    runs nowhere and reports nothing.
    """

    repo = _make_repo(tmp_path, stub_hits=[_MUTATION_HIT])
    result, witness = _run_block(tmp_path, repo, query=None)

    assert result.returncode == 0, "a missing query MUST NOT block the pipeline"
    assert "STEP 4.9 REQUIREMENT UNMET" in result.stderr, result.stderr
    assert "SEARCH-EXECUTED: no" in result.stdout, result.stdout
    assert not witness.exists()

    # Negative control of the same probe: with a query present, the warning
    # MUST be absent — otherwise it would fire always and mean nothing.
    ok_result, ok_witness = _run_block(
        tmp_path / "withquery", repo, query="mutation testing"
    )
    assert "STEP 4.9 REQUIREMENT UNMET" not in ok_result.stderr
    assert ok_witness.exists()


def test_block_is_positioned_before_planner_dispatch() -> None:
    text = IMPLEMENT_MD.read_text()
    assert text.index(BEGIN_MARKER) < text.index("### STEP 5: Planner"), (
        "the prior-art search must run BEFORE the planner is dispatched"
    )


def test_planner_dispatch_requires_the_block_verbatim() -> None:
    text = IMPLEMENT_MD.read_text()
    step5 = text[text.index("### STEP 5: Planner") : text.index("### STEP 5.5:")]
    assert "$PRIOR_ART_BLOCK" in step5, "planner prompt does not consume the result"
    assert "verbatim" in step5.lower()
    assert "Issue #1669" in step5

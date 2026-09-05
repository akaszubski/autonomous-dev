"""State-plumbing contract for ``implement.md`` / ``implement-batch.md``.

Guards a CLASS of defect, not the instance that prompted it: the coordinator
markdown is executable instruction text, so a wrong literal in it is
production code that no linter, type-checker or import graph can see.

Four shapes are refused here:

1. **Non-atomic sentinel writes.** ``open(path, 'w')`` truncates at OPEN time.
   A kill between the open and the ``json.dump`` left a 0-byte sentinel with
   the prior content already gone; ``ensure_sentinel_heartbeat`` then failed
   ``json.loads`` and recreated it as a bare ``{session_id, recovered,
   recovered_at}``, which ``_is_pipeline_active()`` classifies NOT-active by
   design (#1384) — blocking STEP 11 issue filing during a live pipeline.
   ``sentinel.write_text(...)`` is the SAME class in a different shape and is
   refused too (#1512).
2. **A ``/tmp`` sentinel default.** ``get_legacy_sentinel_path()`` returns
   ``<repo>/.claude/local/implement_pipeline_state.json``. Measured: a
   different file. A doc-side ``/tmp`` default writes where the hook never reads.
3. **Hand-rolled ``_resolve_session_id()`` copies**, and calls to the canonical
   ``resolve_session_id()`` that omit ``sentinel_path=`` (the helper does not
   read ``PIPELINE_STATE_FILE`` itself, so omitting it silently drops env
   honouring).
4. **``gh issue create`` inside an executable ```bash fence.** That route is
   gated on ``_is_pipeline_active()``, which returns False for the remainder
   of any run whose sentinel was recovered.

EVERY extraction-based assertion carries a positive control over an inline
fixture with a KNOWN count, and pins an EXACT number. An extractor that
matches zero must FAIL here rather than report a clean doc.

Issues: #989, #1041, #1206, #1376, #1384, #1481, #1512
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
BATCH_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"


# ---------------------------------------------------------------------------
# Extractors (each has a positive control below)
# ---------------------------------------------------------------------------

_BASH_FENCE = re.compile(r"^```bash[^\n]*\n(.*?)^```", re.M | re.S)
_PSF_ANY = re.compile(r"_?os\.environ\.get\(\s*['\"]PIPELINE_STATE_FILE['\"]")
_PSF_SANCTIONED_DEFAULT = re.compile(
    r"_?os\.environ\.get\(\s*['\"]PIPELINE_STATE_FILE['\"]\s*,\s*"
    r"str\(get_legacy_sentinel_path\(\)\)\s*\)"
)
_PSF_NO_DEFAULT = re.compile(
    r"_?os\.environ\.get\(\s*['\"]PIPELINE_STATE_FILE['\"]\s*\)\s*or\s*None"
)
_HANDROLLED_RESOLVER = re.compile(r"^\s*def\s+_resolve_session_id\s*\(", re.M)
_RESOLVE_CALL = re.compile(r"resolve_session_id\(\s*(?P<args>[^)]*)")
_NON_ATOMIC_SENTINEL_WRITE = re.compile(
    r"open\(\s*_?os\.environ\.get\(\s*['\"]PIPELINE_STATE_FILE['\"][^\n]*['\"]w['\"]\s*\)"
    r"|sentinel\.write_text\(|state_path\.write_text\("
)


def bash_fences(text: str) -> list[str]:
    """Return the body of every ```bash fence."""
    return _BASH_FENCE.findall(text)


def executable_text(text: str) -> str:
    """Return ONLY the executable portion: the concatenated ```bash fences.

    Prose and comments describing the contract (``pass
    ``sentinel_path=os.environ.get('PIPELINE_STATE_FILE') or None``…``) are
    documentation, not instructions the coordinator runs. Counting them would
    make every pin drift on a wording change while the executable text was
    unchanged — the exact way a contract guard becomes noise and gets deleted.
    """
    return "\n".join(bash_fences(text))


def gh_issue_create_in_bash_fences(text: str) -> int:
    """Count ``gh issue create`` occurrences inside ```bash fences only."""
    return sum(f.count("gh issue create") for f in bash_fences(text))


def state_file_reads(text: str) -> tuple[int, int, int]:
    """Return (total PIPELINE_STATE_FILE reads, sanctioned-default, no-default).

    Scoped to executable fences.
    """
    body = executable_text(text)
    return (
        len(_PSF_ANY.findall(body)),
        len(_PSF_SANCTIONED_DEFAULT.findall(body)),
        len(_PSF_NO_DEFAULT.findall(body)),
    )


def handrolled_resolvers(text: str) -> int:
    return len(_HANDROLLED_RESOLVER.findall(executable_text(text)))


def resolve_calls_missing_sentinel_path(text: str) -> list[str]:
    """Return every executable ``resolve_session_id(...)`` call lacking
    ``sentinel_path=``. Comment lines inside fences are skipped."""
    bad = []
    for line in executable_text(text).splitlines():
        if line.lstrip().startswith("#"):
            continue
        for m in _RESOLVE_CALL.finditer(line):
            if "sentinel_path=" not in m.group("args"):
                bad.append(m.group(0))
    return bad


def non_atomic_sentinel_writes(text: str) -> int:
    return len(_NON_ATOMIC_SENTINEL_WRITE.findall(text))


def extract_python_c_block(text: str, anchor: str) -> str:
    """Return the body of the ``python3 -c "..."`` block containing ``anchor``."""
    idx = text.index(anchor)
    start = text.rindex('python3 -c "', 0, idx) + len('python3 -c "')
    end = text.index('\n"\n', start)
    return text[start:end]


# ---------------------------------------------------------------------------
# Inline fixtures for the positive controls (KNOWN counts)
# ---------------------------------------------------------------------------

FIXTURE_TWO_GH_IN_BASH = """\
Prose mentioning gh issue create must NOT be counted.

```bash
gh issue create --title "one"
```

```python
gh issue create --title "not bash, not counted"
```

```bash
echo hi
gh issue create --title "two"
```
"""

FIXTURE_TWO_STATE_DEFAULTS = """\
```bash
python3 -c "
a = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
b = _os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
c = os.environ.get('PIPELINE_STATE_FILE') or None
"
```
"""

FIXTURE_TMP_LITERAL_DEFAULT = """\
```bash
python3 -c "
p = os.environ.get('PIPELINE_STATE_FILE', '/tmp/implement_pipeline_state.json')
"
```
"""

FIXTURE_HANDROLLED_RESOLVER = """\
```bash
python3 -c "
def _resolve_session_id():
    return os.environ.get('CLAUDE_SESSION_ID', 'unknown')
sid = _resolve_session_id()
"
```
"""

FIXTURE_BARE_RESOLVE_CALL = """\
```bash
python3 -c "
sid = resolve_session_id()
"
```
"""

FIXTURE_OPEN_W_WRITE = """\
```bash
python3 -c "
with open(os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path())), 'w') as f:
    json.dump(state, f)
"
```
"""

FIXTURE_WRITE_TEXT_WRITE = """\
```bash
python3 -c "
sentinel.write_text(json.dumps(state), encoding='utf-8')
"
```
"""

FIXTURE_PYTHON_C_BLOCK = '''\
```bash
python3 -c "
import os
MARKER_ANCHOR = 1
print('done')
"
```
'''


# ---------------------------------------------------------------------------
# 1. VACUITY GUARDS — run these first
# ---------------------------------------------------------------------------


class TestExtractorPositiveControls:
    """Every extractor must return a KNOWN non-zero count on a known input."""

    def test_bash_fence_extractor_finds_exactly_two(self) -> None:
        assert len(bash_fences(FIXTURE_TWO_GH_IN_BASH)) == 2
        assert gh_issue_create_in_bash_fences(FIXTURE_TWO_GH_IN_BASH) == 2
        # And it does NOT count the prose line or the ```python fence.
        assert FIXTURE_TWO_GH_IN_BASH.count("gh issue create") == 4

    def test_state_file_extractor_finds_exactly_two_and_one(self) -> None:
        total, sanctioned, no_default = state_file_reads(FIXTURE_TWO_STATE_DEFAULTS)
        assert (total, sanctioned, no_default) == (3, 2, 1)

    def test_handrolled_resolver_extractor_finds_exactly_one(self) -> None:
        assert handrolled_resolvers(FIXTURE_HANDROLLED_RESOLVER) == 1

    def test_missing_sentinel_path_extractor_finds_exactly_one(self) -> None:
        assert len(resolve_calls_missing_sentinel_path(FIXTURE_BARE_RESOLVE_CALL)) == 1
        assert resolve_calls_missing_sentinel_path(FIXTURE_TWO_STATE_DEFAULTS) == []

    def test_non_atomic_write_extractor_finds_each_shape(self) -> None:
        assert non_atomic_sentinel_writes(FIXTURE_OPEN_W_WRITE) == 1
        assert non_atomic_sentinel_writes(FIXTURE_WRITE_TEXT_WRITE) == 1

    def test_python_c_block_extractor_returns_the_body(self) -> None:
        body = extract_python_c_block(FIXTURE_PYTHON_C_BLOCK, "MARKER_ANCHOR")
        assert body.strip().startswith("import os")
        assert "MARKER_ANCHOR = 1" in body
        assert "```" not in body


class TestPinnedOccurrenceCounts:
    """Exact counts on the LIVE docs. Never ``>= 1`` — a drifted extractor
    that matched nothing would sail through an at-least assertion."""

    def test_implement_md_state_file_reads_are_pinned(self) -> None:
        total, sanctioned, no_default = state_file_reads(IMPLEMENT_MD.read_text())
        assert (total, sanctioned, no_default) == (9, 6, 3), (
            "PIPELINE_STATE_FILE read sites changed. Every read MUST be either "
            "the sanctioned get_legacy_sentinel_path() default or the "
            "`or None` pass-through; update this pin deliberately."
        )
        # Nothing outside the two sanctioned forms exists.
        assert sanctioned + no_default == total

    def test_implement_md_bash_fence_count_is_pinned(self) -> None:
        assert len(bash_fences(IMPLEMENT_MD.read_text())) == 36

    def test_gh_issue_create_occurrences_are_pinned(self) -> None:
        text = IMPLEMENT_MD.read_text()
        assert text.count("gh issue create") == 1, (
            "The ONLY sanctioned occurrence is the deferred placeholder comment "
            "in the MEDIUM-convergence DEFER branch."
        )
        sole = [ln for ln in text.splitlines() if "gh issue create" in ln]
        assert sole == ["            # Note: Actual gh issue create command would go here"]

    def test_resolve_session_id_call_sites_are_pinned(self) -> None:
        impl = IMPLEMENT_MD.read_text()
        batch = BATCH_MD.read_text()
        assert impl.count("resolve_session_id(sentinel_path=") == 3
        assert batch.count("resolve_session_id(sentinel_path=") == 2


# ---------------------------------------------------------------------------
# 2. FIX 3 — no /tmp sentinel default; export retained
# ---------------------------------------------------------------------------


class TestSentinelPathDefault:
    @pytest.mark.parametrize("doc", [IMPLEMENT_MD, BATCH_MD], ids=["implement", "batch"])
    def test_no_tmp_literal_default_remains(self, doc: Path) -> None:
        """Both coordinators, not just the one the defect was found in.

        Scoped to IMPLEMENT_MD alone, this passed while
        ``implement-batch.md:494`` still ran
        ``rm -- "${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}"``
        on every batch merge — deleting a file that does not exist while the
        real per-repo sentinel accumulated under ``.claude/local/``. The
        sibling ``TestSessionIdResolver`` already parametrised over both docs
        for a materially identical shape; this class did not.
        """
        offenders = [
            f"{doc.name}:{lineno}: {line.strip()}"
            for lineno, line in enumerate(doc.read_text().splitlines(), 1)
            if "/tmp/implement_pipeline_state.json" in line
        ]
        assert offenders == [], (
            "machine-global /tmp sentinel literal survives; the canonical "
            "default is get_legacy_sentinel_path() "
            "(<repo>/.claude/local/implement_pipeline_state.json). Offenders:\n"
            + "\n".join(offenders)
        )

    def test_synthetic_tmp_default_is_refused(self) -> None:
        """REFUSE arm — a doc with the old literal fails the same check."""
        total, sanctioned, no_default = state_file_reads(FIXTURE_TMP_LITERAL_DEFAULT)
        assert total == 1
        assert sanctioned + no_default == 0, (
            "the /tmp literal must NOT be classified as a sanctioned form"
        )
        assert "/tmp/implement_pipeline_state.json" in FIXTURE_TMP_LITERAL_DEFAULT

    def test_export_pipeline_state_file_is_retained(self) -> None:
        """The producer of a PROTECTED variable must not be deleted."""
        text = IMPLEMENT_MD.read_text()
        assert text.count("export PIPELINE_STATE_FILE") == 1
        assert 'mkdir -p "$(dirname "$PIPELINE_STATE_FILE")"' in text, (
            "atomic_write_json requires the parent directory to exist"
        )
        sys.path.insert(0, str(HOOK_DIR))
        sys.path.insert(0, str(LIB_DIR))
        import unified_pre_tool as upt

        assert "PIPELINE_STATE_FILE" in upt.PROTECTED_ENV_VARS


# ---------------------------------------------------------------------------
# 3. FIX 1b — one canonical resolver, sentinel_path= always passed
# ---------------------------------------------------------------------------


class TestSessionIdResolver:
    @pytest.mark.parametrize("doc", [IMPLEMENT_MD, BATCH_MD], ids=["implement", "batch"])
    def test_zero_handrolled_resolvers(self, doc: Path) -> None:
        assert handrolled_resolvers(doc.read_text()) == 0

    def test_synthetic_handrolled_resolver_is_refused(self) -> None:
        """REFUSE arm, different shape from the live doc."""
        assert handrolled_resolvers(FIXTURE_HANDROLLED_RESOLVER) == 1

    @pytest.mark.parametrize("doc", [IMPLEMENT_MD, BATCH_MD], ids=["implement", "batch"])
    def test_every_call_passes_sentinel_path(self, doc: Path) -> None:
        assert resolve_calls_missing_sentinel_path(doc.read_text()) == []

    def test_synthetic_bare_call_is_refused(self) -> None:
        assert resolve_calls_missing_sentinel_path(FIXTURE_BARE_RESOLVE_CALL) == [
            "resolve_session_id("
        ]

    def test_canonical_helper_exists_with_the_documented_keyword(self) -> None:
        """The doc instructs a real API — verify the surface, do not assume it."""
        import inspect

        sys.path.insert(0, str(LIB_DIR))
        import pipeline_completion_state as pcs

        sig = inspect.signature(pcs.resolve_session_id)
        assert "sentinel_path" in sig.parameters
        assert sig.parameters["sentinel_path"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["sentinel_path"].default is None


# ---------------------------------------------------------------------------
# 4. FIX 1 — the STEP 0 sentinel write is atomic (behavioural, both arms)
# ---------------------------------------------------------------------------

STEP0_ANCHOR = "state = sign_state(state, sid)"
KNOWN_GOOD = {"session_id": "prior-owner", "run_id": "prior", "mode": "full"}


@pytest.fixture
def step0_repo(tmp_path: Path):
    """A synthetic repo whose ``.claude/lib`` is the REAL lib directory.

    A real repo cannot be given a read-only ``.claude/local/`` — hence the
    synthetic tree. Nothing about the write path is stubbed: the block imports
    the genuine ``pipeline_state`` and ``pipeline_completion_state``.
    """
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "lib").symlink_to(LIB_DIR, target_is_directory=True)
    # NOT ``.claude/local``. Measured: the block's
    # ``os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))``
    # evaluates the default EAGERLY, and get_legacy_sentinel_path() chmods
    # <repo>/.claude/local back to 0o700 as a side effect — which silently
    # undid the read-only refuse arm and made it pass for BOTH implementations.
    # A sibling directory keeps the permission control discriminating.
    local = repo / ".claude" / "ro_state"
    local.mkdir()
    sentinel = local / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps(KNOWN_GOOD))

    run_id = "t" + uuid.uuid4().hex[:12]
    session_id = "sess-" + uuid.uuid4().hex[:12]
    yield repo, local, sentinel, run_id, session_id

    # Consecutive-run isolation: record_run_start writes real /tmp state.
    digest = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    for pattern in (
        f"/tmp/pipeline_agent_completions_{run_id}*",
        f"/tmp/pipeline_agent_completions_{digest}*",
    ):
        for stale in glob.glob(pattern):
            try:
                os.unlink(stale)
            except OSError:
                pass
    try:
        local.chmod(0o700)
    except OSError:
        pass


def _run_step0(repo: Path, sentinel: Path, run_id: str, session_id: str):
    """Materialise and execute implement.md's STEP 0 sentinel block."""
    block = extract_python_c_block(IMPLEMENT_MD.read_text(), STEP0_ANCHOR)
    src = (
        block.replace("$(date +%Y-%m-%dT%H:%M:%S)", "2026-09-05T00:00:00")
        .replace("$RUN_ID", run_id)
        .replace("'MODE'", "'full'")
    )
    script = repo / "step0.py"
    script.write_text(src)
    env = dict(os.environ)
    env["PIPELINE_STATE_FILE"] = str(sentinel)
    env["CLAUDE_SESSION_ID"] = session_id
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_step0_block_is_extractable_and_uses_atomic_write() -> None:
    """Guards the extractor for the two behavioural tests below."""
    block = extract_python_c_block(IMPLEMENT_MD.read_text(), STEP0_ANCHOR)
    assert "atomic_write_json(" in block
    assert non_atomic_sentinel_writes(block) == 0
    assert "```" not in block


def test_step0_write_permit_arm(step0_repo) -> None:
    """PERMIT arm: a writable directory produces a valid signed sentinel."""
    repo, _local, sentinel, run_id, session_id = step0_repo
    proc = _run_step0(repo, sentinel, run_id, session_id)
    assert proc.returncode == 0, proc.stderr

    written = json.loads(sentinel.read_text())
    assert written["session_id"] == session_id
    assert written["run_id"] == run_id
    assert written["mode"] == "full"
    assert written["explicitly_invoked"] is True
    # #1384: a genuine STEP-0 sentinel carries run_id/mode/explicitly_invoked,
    # so _is_pipeline_active() classifies it ACTIVE.
    assert any(written.get(k) for k in ("run_id", "mode", "explicitly_invoked"))
    assert "hmac" in written or "signature" in written or "nonce" in written


def test_step0_write_leaves_no_orphan_tmp(step0_repo) -> None:
    """atomic_write_json unlinks its temp file on both paths."""
    repo, local, sentinel, run_id, session_id = step0_repo
    proc = _run_step0(repo, sentinel, run_id, session_id)
    assert proc.returncode == 0, proc.stderr
    leftovers = [p.name for p in local.iterdir() if p.name != sentinel.name]
    assert leftovers == [], f"orphaned temp files: {leftovers}"


def test_step0_write_is_atomic_dir_readonly(step0_repo) -> None:
    """REFUSE arm: a non-writable PARENT directory must leave the prior
    sentinel byte-identical, never 0 bytes.

    Measured to discriminate: ``open(path, 'w')`` succeeds and truncates
    (the FILE is still writable) while ``mkstemp(dir=d)`` raises
    ``PermissionError``.
    """
    if hasattr(os, "getuid") and os.getuid() == 0:
        pytest.skip("dir-permission control is vacuous under root: uid 0 bypasses mode bits")

    repo, local, sentinel, run_id, session_id = step0_repo
    before = sentinel.read_bytes()
    assert before, "fixture must seed known-good content"

    local.chmod(0o500)  # r-x: file stays writable, directory does not accept new entries
    try:
        proc = _run_step0(repo, sentinel, run_id, session_id)
    finally:
        local.chmod(0o700)

    assert proc.returncode != 0, (
        "a pipeline that cannot write its own sentinel MUST NOT proceed silently"
    )
    assert "PermissionError" in proc.stderr, proc.stderr
    after = sentinel.read_bytes()
    assert after == before, "prior sentinel content was destroyed"
    assert after != b"", "sentinel was truncated to 0 bytes"


def test_write_text_shape_is_also_rejected() -> None:
    """DIFFERENT-SHAPE control.

    The observed bug was ``open(..., 'w')``. This control is ``write_text``
    (#1512's mechanism) — a guard that only recognised the reproducer's shape
    would pass the live doc and this fixture alike.
    """
    assert non_atomic_sentinel_writes(FIXTURE_WRITE_TEXT_WRITE) == 1
    assert non_atomic_sentinel_writes(FIXTURE_OPEN_W_WRITE) == 1
    assert non_atomic_sentinel_writes(IMPLEMENT_MD.read_text()) == 0


def test_heartbeat_recovery_write_is_atomic() -> None:
    """The code that REPAIRS sentinels must not be able to corrupt one."""
    src = (LIB_DIR / "pipeline_completion_state.py").read_text()
    assert "sentinel.write_text(" not in src
    assert "atomic_write_json(sentinel, recovered_sentinel, indent=2)" in src


def test_unreadable_sentinel_is_distinguishable_from_absent(tmp_path) -> None:
    """A sentinel that EXISTS but does not parse names itself in the log;
    a merely-absent one stays silent."""
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_bytes(b"")  # the observed 0-byte shape
    absent = tmp_path / "absent.json"

    def _probe(path: Path) -> str:
        code = (
            f"import sys; sys.path.insert(0, {str(LIB_DIR)!r})\n"
            "from pipeline_completion_state import resolve_session_id\n"
            f"resolve_session_id(sentinel_path={str(path)!r})\n"
        )
        env = dict(os.environ)
        env.pop("CLAUDE_SESSION_ID", None)
        return subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            env=env, cwd=str(tmp_path), timeout=60,
        ).stderr

    corrupt_err = _probe(corrupt)
    absent_err = _probe(absent)
    assert "[SENTINEL-UNREADABLE]" in corrupt_err, corrupt_err
    assert str(corrupt) in corrupt_err
    assert "[SENTINEL-UNREADABLE]" not in absent_err, absent_err


# ---------------------------------------------------------------------------
# 5. FIX 4 — filing routes through the issue-creator agent
# ---------------------------------------------------------------------------


class TestGhIssueCreateDocConformance:
    """Secondary evidence. The PROOF is the runtime pair below."""

    def test_zero_gh_issue_create_in_any_bash_fence(self) -> None:
        assert gh_issue_create_in_bash_fences(IMPLEMENT_MD.read_text()) == 0

    def test_synthetic_bash_fence_occurrence_is_refused(self) -> None:
        """REFUSE arm for this very check."""
        assert gh_issue_create_in_bash_fences(FIXTURE_TWO_GH_IN_BASH) == 2

    def test_step8_pre_existing_failure_path_names_issue_creator(self) -> None:
        text = IMPLEMENT_MD.read_text()
        line = next(
            ln for ln in text.splitlines() if "pre-existing-failure" in ln
        )
        assert "issue-creator" in line, line
        assert "gh issue create" not in line

    def test_dedup_query_and_advisory_contract_survive(self) -> None:
        text = IMPLEMENT_MD.read_text()
        assert (
            "gh issue list --label security --label auto-improvement --state open --search"
            in text
        )
        assert "[ADVISORY-DEDUP-FAILED]" in text
        assert "[ADVISORY-FILE-FAILED]" in text
        assert "[ADVISORY-MALFORMED]" in text

    def test_all_three_filing_sites_dispatch_issue_creator(self) -> None:
        text = IMPLEMENT_MD.read_text()
        assert text.count('subagent_type="issue-creator"') == 3


def _gate_verdict(command: str, *, agent: str | None, tmp_path: Path) -> str:
    """Call the REAL hook gate in a fresh process with controlled inputs.

    Nothing is mocked: the sentinel and command-context paths are pointed at
    files that do not exist, so ``_is_pipeline_active()`` and
    ``_is_issue_command_active()`` return False through their own logic.
    """
    env = dict(os.environ)
    env["PIPELINE_STATE_FILE"] = str(tmp_path / "no_such_sentinel.json")
    env["GH_ISSUE_CMD_CONTEXT_PATH"] = str(tmp_path / "no_such_context.json")
    env.pop("CLAUDE_AGENT_NAME", None)
    if agent is not None:
        env["CLAUDE_AGENT_NAME"] = agent
    code = (
        f"import sys; sys.path[:0] = [{str(HOOK_DIR)!r}, {str(LIB_DIR)!r}]\n"
        "import unified_pre_tool as u\n"
        "assert u._is_pipeline_active() is False, 'precondition: pipeline must be INACTIVE'\n"
        "import json\n"
        "cmd = json.loads(sys.stdin.read())['command']\n"
        "r = u._detect_gh_issue_create(cmd)\n"
        "print('ALLOW' if r is None else 'DENY')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps({"command": command}),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


GH_CMD = 'gh issue create --title "[Security advisory] x" --body "y" --label security'
GH_SUBPROCESS_CMD = (
    "python3 -c \"import subprocess; "
    "subprocess.run(['gh','issue','create','--title','x','--body','y'])\""
)


def test_issue_creator_dispatch_is_allowed_with_pipeline_inactive(tmp_path) -> None:
    """PERMIT arm — the whole point of routing filing through the agent.

    ``_is_pipeline_active()`` is False (asserted as a precondition inside the
    subprocess), which is exactly the state a recovered sentinel produces for
    the rest of a run (#1384). The agent-identity allow-through still permits.
    """
    assert _gate_verdict(GH_CMD, agent="issue-creator", tmp_path=tmp_path) == "ALLOW"


def test_direct_coordinator_call_is_denied_with_pipeline_inactive(tmp_path) -> None:
    """REFUSE arm — same command, no agent context."""
    assert _gate_verdict(GH_CMD, agent=None, tmp_path=tmp_path) == "DENY"


def test_non_authorized_agent_is_denied(tmp_path) -> None:
    """Negative control on the identity: not just any agent gets through."""
    assert _gate_verdict(GH_CMD, agent="reviewer", tmp_path=tmp_path) == "DENY"


def test_subprocess_wrapped_form_is_also_denied(tmp_path) -> None:
    """DIFFERENT SHAPE — the bypass wrapper, not the bare command."""
    assert _gate_verdict(GH_SUBPROCESS_CMD, agent=None, tmp_path=tmp_path) == "DENY"


def test_unrelated_gh_command_is_not_gated(tmp_path) -> None:
    """Negative control on the DETECTOR: it does not flag everything."""
    assert _gate_verdict("gh issue list --state open", agent=None, tmp_path=tmp_path) == "ALLOW"


def test_issue_creator_is_the_sole_authorized_agent() -> None:
    """The doc instructs a mechanism that actually exists."""
    sys.path.insert(0, str(HOOK_DIR))
    sys.path.insert(0, str(LIB_DIR))
    import unified_pre_tool as upt

    assert upt.GH_ISSUE_AGENTS == {"issue-creator"}
    assert (REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "issue-creator.md").exists()
    manifest = json.loads(
        (REPO_ROOT / "plugins" / "autonomous-dev" / "install_manifest.json").read_text()
    )
    agent_files = manifest["components"]["agents"]["files"]
    assert any(f.endswith("/issue-creator.md") for f in agent_files), agent_files

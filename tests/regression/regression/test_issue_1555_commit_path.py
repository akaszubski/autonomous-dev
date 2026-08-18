#!/usr/bin/env python3
"""Regression tests for Issue #1555: the mandatory commit path was broken.

``create_commit_with_agent_message()`` is the commit funnel that
``/implement`` STEP 12.7 and STEP L4.7 declare mandatory. It could not
complete because of two defects:

1. ``ArtifactManager.read_artifact()`` was called with one positional
   argument (``'manifest'``) while it requires two (``workflow_id`` and
   ``artifact_type``), raising ``TypeError`` on every invocation.
2. The path dispatched ``commit-message-generator`` / ``pr-description-generator``,
   which live under ``agents/archived/``. PROJECT.md:77 forbids active code
   from referencing archived components.

The path had no end-to-end test, which is why both defects survived. These
tests exercise the real path in a temporary git repository - no stubbing of
the message generator.

Issue: #1555
"""

import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
ARCHIVED_AGENTS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "archived"
COMMIT_PATH_SOURCE = LIB_DIR / "auto_implement_git_integration.py"

sys.path.insert(0, str(LIB_DIR))

from artifacts import ArtifactManager  # noqa: E402
from auto_implement_git_integration import (  # noqa: E402
    create_commit_with_agent_message,
    generate_commit_message,
    invoke_commit_message_agent,
)


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with one seed commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "--no-verify", "-m", "chore: seed")
    _git(repo, "checkout", "-q", "-b", "feature/issue-1555")
    return repo


def _stage_change(repo: Path, relative_path: str = "lib/impl.py") -> None:
    """Write and stage a file so there is something to commit."""
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# implementation\n", encoding="utf-8")
    _git(repo, "add", relative_path)


# ---------------------------------------------------------------------------
# End-to-end: the mandatory commit path must actually produce a commit
# ---------------------------------------------------------------------------


def test_regression_issue_1555_commit_path_produces_commit_with_closes_ref(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commit path produces a real commit carrying ``Closes #N``."""
    _stage_change(git_repo)
    monkeypatch.chdir(git_repo)

    head_before = _git(git_repo, "rev-parse", "HEAD").strip()

    result = create_commit_with_agent_message(
        workflow_id="wf-1555",
        request="Fix Issue #1555 broken commit path",
        branch="feature/issue-1555",
        push=False,
        issue_number=1555,
    )

    assert result["success"] is True, f"commit path failed: {result}"
    assert result["commit_sha"], "commit path reported success with no SHA"

    head_after = _git(git_repo, "rev-parse", "HEAD").strip()
    assert head_after != head_before, "no new commit was created"

    message = _git(git_repo, "log", "-1", "--pretty=%B")
    assert "Closes #1555" in message, f"missing Closes trailer:\n{message}"
    assert message.startswith("fix("), f"not a conventional commit subject:\n{message}"


def test_regression_issue_1555_commit_path_runs_without_type_error(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The original defect raised TypeError from read_artifact - it must not."""
    _stage_change(git_repo, "docs/notes.md")
    monkeypatch.chdir(git_repo)

    result = invoke_commit_message_agent(
        workflow_id="wf-1555-no-manifest",
        request="Update README installation instructions",
    )

    assert result["success"] is True, f"generation failed: {result}"
    assert "TypeError" not in result["error"]
    assert result["output"].startswith("docs"), result["output"]


# ---------------------------------------------------------------------------
# Negative control (a): no issue number -> no Closes trailer
# ---------------------------------------------------------------------------


def test_regression_issue_1555_no_closes_trailer_when_issue_number_is_none(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without ``issue_number`` the commit must carry no ``Closes`` trailer."""
    _stage_change(git_repo)
    monkeypatch.chdir(git_repo)

    result = create_commit_with_agent_message(
        workflow_id="wf-1555-no-issue",
        request="Add structured logging to the batch runner",
        branch="feature/issue-1555",
        push=False,
        issue_number=None,
    )

    assert result["success"] is True, f"commit path failed: {result}"

    message = _git(git_repo, "log", "-1", "--pretty=%B")
    assert "Closes" not in message, f"unexpected Closes trailer:\n{message}"
    assert "#" not in message, f"unexpected issue reference:\n{message}"


# ---------------------------------------------------------------------------
# Negative control (b): empty staging area fails cleanly
# ---------------------------------------------------------------------------


def test_regression_issue_1555_empty_staging_area_fails_cleanly(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean working tree fails with a real error, never TypeError."""
    monkeypatch.chdir(git_repo)

    head_before = _git(git_repo, "rev-parse", "HEAD").strip()

    result = create_commit_with_agent_message(
        workflow_id="wf-1555-empty",
        request="Add a feature with nothing staged",
        branch="feature/issue-1555",
        push=False,
        issue_number=1555,
    )

    assert result["success"] is False, f"expected failure, got: {result}"
    assert result["commit_sha"] == ""
    assert "nothing to commit" in result["error"].lower(), result["error"]
    assert "TypeError" not in result["error"], result["error"]
    # The error must be actionable, not a bare condition.
    assert "git add" in result["error"], result["error"]
    assert result["manual_instructions"], "no manual fallback offered"

    head_after = _git(git_repo, "rev-parse", "HEAD").strip()
    assert head_after == head_before, "a commit was created from an empty tree"


def test_regression_issue_1555_empty_request_raises_value_error() -> None:
    """Invalid input raises ValueError, not an unhandled TypeError."""
    with pytest.raises(ValueError, match="request cannot be empty"):
        create_commit_with_agent_message(
            workflow_id="wf-1555",
            request="   ",
            branch="feature/issue-1555",
            push=False,
        )


# ---------------------------------------------------------------------------
# Negative control (c): no reference to any archived agent
# ---------------------------------------------------------------------------


def _archived_agent_names() -> List[str]:
    """Names of every agent under agents/archived/."""
    if not ARCHIVED_AGENTS_DIR.is_dir():
        return []
    return sorted(path.stem for path in ARCHIVED_AGENTS_DIR.glob("*.md"))


def test_regression_issue_1555_commit_path_references_no_archived_agent() -> None:
    """The commit path must not reference any agent under agents/archived/.

    PROJECT.md:77 - active code must never import or reference archived
    components.
    """
    archived = _archived_agent_names()
    assert archived, f"no archived agents discovered under {ARCHIVED_AGENTS_DIR}"

    source = COMMIT_PATH_SOURCE.read_text(encoding="utf-8")
    offenders = [name for name in archived if name in source]

    assert offenders == [], (
        f"{COMMIT_PATH_SOURCE.relative_to(REPO_ROOT)} references archived "
        f"agent(s): {offenders}. Archived code is dead code (PROJECT.md:77)."
    )


# ---------------------------------------------------------------------------
# The artifact existence probe
# ---------------------------------------------------------------------------


def test_regression_issue_1555_artifact_manager_surface_canary() -> None:
    """Sanity: the ArtifactManager methods the commit path calls really exist.

    Issue #1225 mandate - verify the real surface, do not trust mocks.
    ``read_artifact`` takes two REQUIRED positional parameters; calling it
    with one is the original Issue #1555 defect.
    """
    import inspect

    assert hasattr(ArtifactManager, "artifact_exists")
    assert hasattr(ArtifactManager, "read_artifact")

    params = inspect.signature(ArtifactManager.read_artifact).parameters
    required = [
        name
        for name, param in params.items()
        if name != "self" and param.default is inspect.Parameter.empty
    ]
    assert required == ["workflow_id", "artifact_type"], (
        f"read_artifact required parameters changed: {required}"
    )


def test_regression_issue_1555_manifest_is_optional_context(
    git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A present manifest is read and used; an absent one does not block."""
    _stage_change(git_repo)
    monkeypatch.chdir(git_repo)

    artifacts_dir = tmp_path / "artifacts"
    manager = ArtifactManager(artifacts_dir=artifacts_dir)
    manager.create_manifest_artifact(
        workflow_id="wf-1555-manifest",
        request="Repair the mandatory commit funnel",
        alignment_data={"validated": True},
        workflow_plan={"agents": ["implementer"]},
    )

    monkeypatch.setattr(
        "auto_implement_git_integration.ArtifactManager",
        lambda *a, **kw: ArtifactManager(artifacts_dir=artifacts_dir),
    )

    with_manifest = invoke_commit_message_agent(
        workflow_id="wf-1555-manifest",
        request="Add retry handling",
    )
    assert with_manifest["success"] is True, with_manifest
    assert "Repair the mandatory commit funnel" in with_manifest["output"], (
        f"manifest context was not used:\n{with_manifest['output']}"
    )

    without_manifest = invoke_commit_message_agent(
        workflow_id="wf-1555-absent",
        request="Add retry handling",
    )
    assert without_manifest["success"] is True, without_manifest
    assert "Repair the mandatory commit funnel" not in without_manifest["output"]


# ---------------------------------------------------------------------------
# Message generation is deterministic and offline
# ---------------------------------------------------------------------------


def test_regression_issue_1555_generated_message_is_conventional() -> None:
    """Generated messages follow conventional-commit shape and stay short."""
    message = generate_commit_message(
        "Fix the broken commit path so /implement can finish",
        changed_files=["plugins/autonomous-dev/lib/auto_implement_git_integration.py"],
    )

    subject = message.splitlines()[0]
    assert subject.startswith("fix(lib): "), subject
    assert len(subject) <= 72, f"subject too long ({len(subject)}): {subject}"
    assert "auto_implement_git_integration.py" in message, message


def test_regression_issue_1555_generation_is_deterministic() -> None:
    """Two calls with identical input produce identical output."""
    args = {"changed_files": ["tests/test_thing.py", "tests/test_other.py"]}
    first = generate_commit_message("Add coverage for the commit funnel", **args)
    second = generate_commit_message("Add coverage for the commit funnel", **args)
    assert first == second
    assert first.startswith("test(tests): "), first

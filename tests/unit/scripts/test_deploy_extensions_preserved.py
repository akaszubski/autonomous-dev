"""
Tests for deploy-all.sh extensions directory preservation (Issue #560).

Root cause: rsync -a --delete on hooks directory deletes target extensions/
because extensions/ doesn't exist in source. Fixed by:
  1. Adding plugins/autonomous-dev/hooks/extensions/.gitkeep to source
  2. Adding --exclude=extensions/ to rsync --delete commands in deploy-all.sh
"""
import re
from pathlib import Path

WORKTREE = Path(__file__).parent.parent.parent.parent
DEPLOY_SCRIPT = WORKTREE / "scripts" / "deploy-all.sh"
# The two remote transports do not call rsync inline any more: they route
# through prune_sync(), which deploy-all.sh inlines into its ssh heredoc via
# command substitution. The destructive rsync therefore lives in this file, and
# a scan of deploy-all.sh alone would sample 2 of the 4 sites — the same
# undercount this test was fixed to remove.
PRUNE_SYNC_LIB = WORKTREE / "scripts" / "lib" / "prune_sync.sh"
DEPLOY_ALL_TRANSPORT = (DEPLOY_SCRIPT, PRUNE_SYNC_LIB)
EXTENSIONS_DIR = WORKTREE / "plugins" / "autonomous-dev" / "hooks" / "extensions"


def test_extensions_directory_exists_in_source():
    """Regression: extensions/ must exist in source so rsync doesn't treat target as orphan."""
    assert EXTENSIONS_DIR.exists(), (
        f"extensions/ directory missing from source: {EXTENSIONS_DIR}\n"
        "This causes rsync --delete to remove target extensions/ (Issue #560)"
    )
    assert EXTENSIONS_DIR.is_dir(), f"Expected directory, got file: {EXTENSIONS_DIR}"


def test_extensions_gitkeep_exists():
    """extensions/ must have .gitkeep so git tracks the empty directory."""
    gitkeep = EXTENSIONS_DIR / ".gitkeep"
    assert gitkeep.exists(), (
        f".gitkeep missing from extensions/: {gitkeep}\n"
        "Without .gitkeep, git does not track the empty directory"
    )


def test_rsync_commands_exclude_extensions():
    """Regression: every rsync invocation on the deploy-all transport excludes extensions/.

    The filter used to be ``line.strip().startswith("rsync ") and "--delete" in
    line``. ``.strip()`` already handled indentation, so the ``and "--delete" in
    line`` clause did nothing except narrow the sample to the two sites that
    were ALREADY armed — the test could not fail for the reason it exists,
    because a site with no ``--delete`` was not sampled and a site with
    ``--delete`` had already been fixed. Dropped: every rsync invocation is now
    sampled, armed or not.

    Comments stay excluded deliberately (Issue #1610). An even earlier filter
    was ``"rsync" in line and "--delete" in line``, which matched prose: a
    comment explaining that ``rsync -a --delete`` does not clear excluded paths
    was reported as a command missing its exclusion. A guard that fires on a
    sentence is a guard people learn to route around by not writing the
    sentence.
    """
    assert DEPLOY_SCRIPT.exists(), f"deploy-all.sh not found: {DEPLOY_SCRIPT}"

    # An rsync captured into a variable is still an rsync invocation:
    # prune_sync()'s deletion preview is written `preview=$(rsync ...)`, and it
    # is the invocation that decides what gets deleted.
    invocation = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\$\()?rsync\s")

    rsync_lines: list[str] = []
    for path in DEPLOY_ALL_TRANSPORT:
        if not path.exists():
            continue
        for lineno, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if invocation.match(line):
                rsync_lines.append(f"{path.name}:{lineno}: {line}")

    assert rsync_lines, "No rsync invocations found on the deploy-all transport"

    # Both quoting forms are the same argument to rsync.
    violations = [
        line
        for line in rsync_lines
        if "--exclude=extensions/" not in line and "--exclude='extensions/'" not in line
    ]

    assert not violations, (
        "rsync invocations missing --exclude=extensions/:\n"
        + "\n".join(f"  {line}" for line in violations)
        + "\n\nFix: add --exclude=extensions/ to each rsync command"
    )


def test_deploy_repo_rsync_has_both_delete_and_exclude():
    """The deploy_repo function rsync must have both --delete and --exclude=extensions/."""
    assert DEPLOY_SCRIPT.exists(), f"deploy-all.sh not found: {DEPLOY_SCRIPT}"

    content = DEPLOY_SCRIPT.read_text()

    # Find the specific rsync in deploy_repo function
    deploy_repo_match = re.search(
        r"deploy_repo\(\).*?^}",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert deploy_repo_match, "deploy_repo() function not found in deploy-all.sh"

    func_body = deploy_repo_match.group(0)

    rsync_lines = [
        line.strip()
        for line in func_body.splitlines()
        if "rsync" in line
    ]
    assert rsync_lines, "No rsync command found inside deploy_repo()"

    for line in rsync_lines:
        assert "--delete" in line, f"rsync in deploy_repo missing --delete: {line}"
        assert "--exclude=extensions/" in line, (
            f"rsync in deploy_repo missing --exclude=extensions/: {line}\n"
            "This would delete target extensions/ on every deploy"
        )

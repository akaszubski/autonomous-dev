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
    """Regression: all rsync --delete commands in deploy-all.sh must exclude extensions/."""
    assert DEPLOY_SCRIPT.exists(), f"deploy-all.sh not found: {DEPLOY_SCRIPT}"

    content = DEPLOY_SCRIPT.read_text()

    # Find all rsync INVOCATIONS that use --delete.
    #
    # Comments are excluded deliberately (Issue #1610). The previous filter was
    # `"rsync" in line and "--delete" in line`, which matched prose: a comment
    # explaining that `rsync -a --delete` does not clear excluded paths was
    # reported as a command missing its exclusion. A guard that fires on a
    # sentence is a guard people learn to route around by not writing the
    # sentence, which is worse than the guard not existing.
    rsync_delete_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip().startswith("rsync ") and "--delete" in line
    ]

    assert rsync_delete_lines, "No rsync --delete lines found in deploy-all.sh"

    # Both quoting forms are the same argument to rsync.
    violations = [
        line
        for line in rsync_delete_lines
        if "--exclude=extensions/" not in line and "--exclude='extensions/'" not in line
    ]

    assert not violations, (
        f"rsync --delete lines missing --exclude=extensions/:\n"
        + "\n".join(f"  {line}" for line in violations)
        + "\n\nFix: add --exclude=extensions/ to each rsync --delete command"
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

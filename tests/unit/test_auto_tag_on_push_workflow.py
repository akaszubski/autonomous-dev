"""Acceptance tests for Issue #1302: Phase E sub-C auto-deploy on master push.

Static file inspection tests that verify the acceptance criteria for the
auto-tag-on-push workflow, pull-plugin-update.sh script, and RUNBOOK
documentation.

Acceptance criteria covered:
1. .github/workflows/auto-tag-on-push.yml exists and triggers on push to master
2. Workflow uses only secrets.GITHUB_TOKEN (no custom SSH credentials)
3. Workflow does NOT create a recursive trigger (no `tags:` push trigger)
4. Workflow has bounded permissions (contents: write only) and timeout
5. scripts/pull-plugin-update.sh exists, is executable, and has a shebang
6. pull-plugin-update.sh implements --dry-run, --no-deploy, and --help flags
7. RUNBOOK.md has a "Consumer-side auto-update (launchd)" H2 section
"""

import os
import re
import stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "auto-tag-on-push.yml"
PULL_SCRIPT = REPO_ROOT / "scripts" / "pull-plugin-update.sh"
RUNBOOK = REPO_ROOT / "docs" / "RUNBOOK.md"


# ---------------------------------------------------------------------------
# AC1: workflow exists and triggers on push to master
# ---------------------------------------------------------------------------


def test_auto_tag_workflow_exists() -> None:
    """AC1: .github/workflows/auto-tag-on-push.yml exists."""
    assert WORKFLOW_FILE.exists(), f"Workflow missing: {WORKFLOW_FILE}"
    assert WORKFLOW_FILE.is_file()


def test_auto_tag_workflow_triggers_on_push_to_master() -> None:
    """AC1: workflow's `on:` block triggers on push to master."""
    content = WORKFLOW_FILE.read_text()
    # Must have an `on:` block with push.branches including master
    assert re.search(r"^on:\s*$", content, re.MULTILINE), "Missing `on:` block"
    assert re.search(
        r"branches:\s*\[\s*master\s*\]", content
    ), "Workflow must trigger on push to master"


# ---------------------------------------------------------------------------
# AC2: only uses GITHUB_TOKEN, no custom SSH credentials
# ---------------------------------------------------------------------------


def test_auto_tag_only_uses_github_token() -> None:
    """AC2: workflow references only secrets.GITHUB_TOKEN (no custom secrets)."""
    content = WORKFLOW_FILE.read_text()
    secret_refs = re.findall(r"secrets\.([A-Z_][A-Z0-9_]*)", content)
    assert secret_refs, "Workflow should reference at least secrets.GITHUB_TOKEN"
    unexpected = {s for s in secret_refs if s != "GITHUB_TOKEN"}
    assert not unexpected, (
        f"Workflow must only use secrets.GITHUB_TOKEN; found unexpected: {unexpected}"
    )


def test_auto_tag_no_ssh_key_references() -> None:
    """AC2: no SSH key or deploy-key strings appear in workflow."""
    content = WORKFLOW_FILE.read_text().lower()
    forbidden = ["ssh-key", "ssh_key", "deploy_key", "deploy-key", "id_rsa", "id_ed25519"]
    for term in forbidden:
        assert term not in content, f"Workflow must not reference '{term}' (CI SSH credentials are out of scope for #1302)"


# ---------------------------------------------------------------------------
# AC3: no recursive trigger (tag push must not re-trigger the workflow)
# ---------------------------------------------------------------------------


def test_auto_tag_no_recursive_trigger() -> None:
    """AC3: workflow does NOT trigger on tag pushes (would cause infinite loop)."""
    content = WORKFLOW_FILE.read_text()
    # Extract the `on:` block (lines until next top-level key)
    on_match = re.search(r"^on:\s*\n((?:[ \t]+.*\n)+)", content, re.MULTILINE)
    assert on_match, "Could not parse `on:` block"
    on_block = on_match.group(1)
    # Within `on:`, must NOT have a `tags:` key (which would mean triggering on tag push)
    # Allow `paths-ignore`, `branches`, but not `tags`.
    assert not re.search(r"^\s+tags:", on_block, re.MULTILINE), (
        "Workflow must not trigger on tag push -- this would create infinite recursion"
    )


# ---------------------------------------------------------------------------
# AC4: bounded permissions and timeout
# ---------------------------------------------------------------------------


def test_auto_tag_has_contents_write_permission() -> None:
    """AC4: workflow declares contents: write permission (required for git tag push)."""
    content = WORKFLOW_FILE.read_text()
    assert re.search(
        r"permissions:\s*\n\s+contents:\s+write", content
    ), "Workflow must declare `permissions: contents: write`"


def test_auto_tag_has_job_timeout() -> None:
    """AC4: job has a bounded timeout-minutes (prevents runaway CI cost)."""
    content = WORKFLOW_FILE.read_text()
    m = re.search(r"timeout-minutes:\s+(\d+)", content)
    assert m, "Workflow job must declare `timeout-minutes:`"
    assert int(m.group(1)) <= 10, f"timeout-minutes should be <=10 (got {m.group(1)})"


def test_auto_tag_has_concurrency_group() -> None:
    """AC4: workflow declares a concurrency group (prevents racing tag pushes)."""
    content = WORKFLOW_FILE.read_text()
    assert re.search(r"concurrency:\s*\n\s+group:", content), (
        "Workflow must declare a concurrency group"
    )


def test_auto_tag_uses_jq_for_version_extraction() -> None:
    """Workflow extracts version with jq (matches plan spec; rejects null/invalid)."""
    content = WORKFLOW_FILE.read_text()
    assert "jq -r '.version'" in content, (
        "Workflow must use `jq -r '.version'` to read marketplace.json"
    )


def test_auto_tag_validates_version_format() -> None:
    """Workflow rejects versions that are not in N.N.N form."""
    content = WORKFLOW_FILE.read_text()
    assert re.search(r"\[0-9\]\+\\\.\[0-9\]\+\\\.\[0-9\]\+", content), (
        "Workflow must validate the version matches a N.N.N regex"
    )


def test_auto_tag_format_includes_sha7() -> None:
    """Tag includes a 7-char SHA suffix so multiple pushes per patch are distinct."""
    content = WORKFLOW_FILE.read_text()
    assert "git rev-parse --short=7 HEAD" in content, (
        "Workflow must compute 7-char SHA for tag suffix"
    )
    assert "autonomous-dev-v" in content, (
        "Tag prefix must be 'autonomous-dev-v'"
    )


# ---------------------------------------------------------------------------
# AC5: pull-plugin-update.sh exists, is executable, has shebang
# ---------------------------------------------------------------------------


def test_pull_plugin_update_exists() -> None:
    """AC5: scripts/pull-plugin-update.sh exists."""
    assert PULL_SCRIPT.exists(), f"Script missing: {PULL_SCRIPT}"
    assert PULL_SCRIPT.is_file()


def test_pull_plugin_update_has_shebang() -> None:
    """AC5: script starts with a bash shebang."""
    first_line = PULL_SCRIPT.read_text().splitlines()[0]
    assert first_line.startswith("#!"), f"Script must have a shebang, got: {first_line!r}"
    assert "bash" in first_line, f"Shebang must invoke bash, got: {first_line!r}"


def test_pull_plugin_update_is_executable() -> None:
    """AC5: script has the executable bit set (required for launchd ProgramArguments)."""
    mode = PULL_SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "Script must be executable by owner"
    assert mode & stat.S_IXGRP, "Script must be executable by group"
    assert mode & stat.S_IXOTH, "Script must be executable by others"


def test_pull_plugin_update_uses_strict_mode() -> None:
    """Script uses `set -euo pipefail` (bash strict mode)."""
    content = PULL_SCRIPT.read_text()
    assert "set -euo pipefail" in content, (
        "Script must use `set -euo pipefail` to fail fast"
    )


# ---------------------------------------------------------------------------
# AC6: --dry-run, --no-deploy, --help flags
# ---------------------------------------------------------------------------


def test_pull_plugin_update_accepts_dry_run_flag() -> None:
    """AC6: script accepts --dry-run flag."""
    content = PULL_SCRIPT.read_text()
    assert "--dry-run" in content, "Script must handle --dry-run"
    assert "DRY_RUN" in content, "Script must have a DRY_RUN variable"


def test_pull_plugin_update_accepts_no_deploy_flag() -> None:
    """AC6: script accepts --no-deploy flag."""
    content = PULL_SCRIPT.read_text()
    assert "--no-deploy" in content, "Script must handle --no-deploy"
    assert "NO_DEPLOY" in content, "Script must have a NO_DEPLOY variable"


def test_pull_plugin_update_accepts_help_flag() -> None:
    """AC6: script accepts --help and -h flags."""
    content = PULL_SCRIPT.read_text()
    assert "--help" in content, "Script must handle --help"
    assert "-h)" in content or "-h|" in content, "Script must handle -h short flag"


def test_pull_plugin_update_writes_state_file() -> None:
    """Script records the last-applied tag to .claude/local/last_pulled_tag."""
    content = PULL_SCRIPT.read_text()
    assert ".claude/local/last_pulled_tag" in content, (
        "Script must record state in .claude/local/last_pulled_tag"
    )


def test_pull_plugin_update_logs_to_claude_logs() -> None:
    """Script appends a log to .claude/logs/pull-plugin-update.log."""
    content = PULL_SCRIPT.read_text()
    assert ".claude/logs/pull-plugin-update.log" in content, (
        "Script must log to .claude/logs/pull-plugin-update.log"
    )


def test_pull_plugin_update_invokes_deploy_all_local_no_global() -> None:
    """Script invokes deploy-all.sh with --local and --no-global."""
    content = PULL_SCRIPT.read_text()
    assert "deploy-all.sh" in content, "Script must invoke scripts/deploy-all.sh"
    assert "--local" in content, "Script must pass --local to deploy-all.sh"
    assert "--no-global" in content, "Script must pass --no-global to deploy-all.sh"


def test_pull_plugin_update_uses_ff_only_pull() -> None:
    """Script uses git pull --ff-only (never merges or rebases on consumer Mac)."""
    content = PULL_SCRIPT.read_text()
    assert "git pull --ff-only" in content, (
        "Script must use `git pull --ff-only` to avoid divergence"
    )


def test_pull_plugin_update_tag_prefix_matches_workflow() -> None:
    """Script's TAG_PREFIX must match the prefix the workflow emits."""
    workflow = WORKFLOW_FILE.read_text()
    script = PULL_SCRIPT.read_text()
    # Workflow prefix: TAG="autonomous-dev-v${PATCH}+${SHA7}"
    assert "autonomous-dev-v" in workflow
    assert 'TAG_PREFIX="autonomous-dev-v"' in script, (
        "Script's TAG_PREFIX must match the workflow's tag prefix"
    )


# ---------------------------------------------------------------------------
# AC7: RUNBOOK.md has the launchd documentation section
# ---------------------------------------------------------------------------


def test_runbook_has_launchd_section() -> None:
    """AC7: RUNBOOK.md has an H2 'Consumer-side auto-update (launchd)' section."""
    content = RUNBOOK.read_text()
    assert re.search(
        r"^## Consumer-side auto-update \(launchd\)\s*$", content, re.MULTILINE
    ), "RUNBOOK.md must have H2 section: Consumer-side auto-update (launchd)"


def test_runbook_launchd_section_has_plist_template() -> None:
    """RUNBOOK's launchd section includes a plist template with StartInterval."""
    content = RUNBOOK.read_text()
    assert "com.autonomousdev.pullupdate" in content, (
        "RUNBOOK must include the launchd Label identifier"
    )
    assert "StartInterval" in content, (
        "RUNBOOK must document StartInterval for the launchd plist"
    )
    # Verify the interval is 1800 (30 minutes) per the plan
    assert "1800" in content, "RUNBOOK should document a 30-minute interval (1800 seconds)"


def test_runbook_launchd_section_documents_operations() -> None:
    """RUNBOOK launchd section documents disable/enable/inspect commands."""
    content = RUNBOOK.read_text()
    # Verify operational commands appear in the section
    assert "launchctl load" in content, "RUNBOOK must show how to load the agent"
    assert "launchctl unload" in content, "RUNBOOK must show how to unload the agent"
    assert "last_pulled_tag" in content, "RUNBOOK must show how to inspect last applied tag"


def test_runbook_explains_tag_and_pull_rationale() -> None:
    """RUNBOOK explains why tag-and-pull (vs CI push with SSH credentials)."""
    content = RUNBOOK.read_text().lower()
    # The 'why' should mention the no-SSH-credentials rationale somewhere in the section
    assert "ssh" in content, (
        "RUNBOOK must explain why we use tag-and-pull instead of CI SSH push"
    )

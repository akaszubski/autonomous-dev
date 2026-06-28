---
covers:
  - .github/workflows/
---

# GitHub Actions Integration

Automated PR review and issue implementation using Claude via `anthropics/claude-code-action`.

## Setup

### 1. Add the API Key Secret

1. Go to your GitHub repository **Settings > Secrets and variables > Actions**
2. Click **New repository secret**
3. Name: `ANTHROPIC_API_KEY`
4. Value: Your Anthropic API key
5. Click **Add secret**

### 2. Workflows Included

| Workflow | Trigger | File |
|----------|---------|------|
| Claude Code Review | PR opened/updated, `@claude` comment | `.github/workflows/claude-review.yml` |
| Claude Issue Implementation | Issue labeled `claude-implement` | `.github/workflows/claude-implement.yml` |
| Auto-tag on push | Push to `master` (non-log paths) | `.github/workflows/auto-tag-on-push.yml` |
| CI | Push/PR to `master`/`main`, manual dispatch | `.github/workflows/ci.yml` |

### CI Workflow (`ci.yml`)

Three-stage pipeline: **Smoke** (fast sanity checks, Stage 1) → **Full Test Suite** (unit + integration + regression, Stage 2, depends on smoke) → **CI Summary** (merge gate, Stage 3, always runs). A conditional **GenAI Intent Tests** job (Stage 1.5) also runs after smoke when the `OPENROUTER_API_KEY` repo variable is set.

The CI Summary gate uses positive assertions: it blocks merge unless `SMOKE_RESULT` is exactly `"success"` and `TEST_RESULT` is `"success"` or `"skipped"`. Any other conclusion — including `cancelled` and `timed_out` — is treated as blocking. This prevents silently allowing merges when jobs time out or are cancelled before completion. (Issue #1333)

**Full Test Suite — Route tests pre-step and parallelization (Issue #1332)**: The `test` job begins with a `Route tests` step (`id: route`) that calls `route_tests()` from `plugins/autonomous-dev/lib/test_routing.py`. When the routing result sets `skip_all=true` (e.g., for docs-only PRs), the install and all three pytest steps are short-circuited via `if:` guards, so documentation-only changes do not consume the full job budget. When the suite does run, all three pytest steps (unit, integration, regression) use `pytest-xdist` with `-n auto` to parallelize across available runner cores, which is the primary wall-clock fix for timeout issues. Regression tests asserting this structure live in `tests/regression/test_ci_workflow_routing.py`.

## Usage

### Automated PR Review

Every pull request automatically receives a Claude review on open, synchronize, and reopen events. Claude reads `CLAUDE.md` for project conventions and focuses on code quality, test coverage, security, and documentation.

To request additional review feedback on an existing PR, leave a comment containing `@claude` with your question or request.

### Issue Auto-Implementation

To have Claude implement a GitHub issue automatically:

1. Create a GitHub issue with a clear title and description
2. Add the label `claude-implement` to the issue
3. Claude will read the issue, implement a solution, and open a PR

The PR will reference the original issue. Review the PR as you would any human-authored code.

## Security Considerations

- **API key**: Stored as a GitHub secret, never exposed in logs or workflow files
- **Permissions**: Workflows use minimal required permissions (read contents, write PRs/issues)
- **Model**: Uses Sonnet (not Opus) to manage CI costs
- **Concurrency**: Duplicate runs are cancelled automatically via concurrency groups
- **Review required**: Auto-generated PRs still require human review and approval before merge
- **Tool access**: Review workflow has read-only tools; implementation workflow has write access limited to the PR branch

### Auto-tag on push

Every push to `master` (excluding `.claude/logs/**`) runs `.github/workflows/auto-tag-on-push.yml`, which:

1. Reads the plugin version from `plugins/autonomous-dev/.claude-plugin/marketplace.json` (validated as `N.N.N`)
2. Computes a 7-char SHA suffix via `git rev-parse --short=7 HEAD`
3. Emits an annotated tag of the form `autonomous-dev-v<version>+<sha7>`
4. Pushes the tag to origin (idempotent — skips if the tag already exists)

The tag is consumed by `scripts/pull-plugin-update.sh` running on consumer Macs via a launchd timer. See the "Consumer-side auto-update (launchd)" section of [RUNBOOK.md](../docs/RUNBOOK.md) for setup instructions.

**Credentials**: only `secrets.GITHUB_TOKEN` is used (no custom SSH keys required). **Permissions**: `contents: write` only, with a 3-minute job timeout and a `cancel-in-progress: false` concurrency group.

## Cost Management

The Claude review and issue-implementation workflows use `claude-sonnet-4-5-20250929` to keep CI costs reasonable. The concurrency groups prevent duplicate runs when PRs are updated rapidly. The auto-tag workflow uses only standard GitHub Actions (no Anthropic API calls) — it is always free.

## Troubleshooting

**Workflow not triggering**: Verify the `ANTHROPIC_API_KEY` secret is set and the workflow files are on the default branch.

**Permission errors**: Ensure the repository settings allow GitHub Actions to create pull requests (Settings > Actions > General > Workflow permissions > Read and write).

**Rate limits**: If you hit Anthropic API rate limits, consider adding delays or reducing concurrent workflow runs.

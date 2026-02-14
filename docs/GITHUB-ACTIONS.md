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

## Cost Management

Both workflows use `claude-sonnet-4-5-20250929` to keep CI costs reasonable. The concurrency groups prevent duplicate runs when PRs are updated rapidly.

## Troubleshooting

**Workflow not triggering**: Verify the `ANTHROPIC_API_KEY` secret is set and the workflow files are on the default branch.

**Permission errors**: Ensure the repository settings allow GitHub Actions to create pull requests (Settings > Actions > General > Workflow permissions > Read and write).

**Rate limits**: If you hit Anthropic API rate limits, consider adding delays or reducing concurrent workflow runs.

# GitHub Authentication Setup

This guide shows how to set up GitHub authentication for the orchestrator agent.

## Why GitHub Authentication?

The orchestrator agent can optionally integrate with GitHub to:
- Track sprint progress via Milestones
- Link work to specific Issues
- Auto-update issue status as work progresses
- Close issues when features complete

**Note**: GitHub integration is **optional** and **secondary** to PROJECT.md alignment. If not configured, the orchestrator works fine using PROJECT.md alone.

## Setup Steps

### 1. Create Personal Access Token

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name: `claude-code-autonomous-dev`
4. Select scopes:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `read:org` (Read org and team membership)
5. Click "Generate token"
6. **Copy the token** (you won't see it again!)

### 2. Create .env File

In your project root (where you installed the plugin):

```bash
# Create .env file
touch .env

# Add to .gitignore (IMPORTANT!)
echo ".env" >> .gitignore
```

Edit `.env` and add:

```bash
GITHUB_TOKEN=ghp_your_token_here
```

Replace `ghp_your_token_here` with your actual token from step 1.

### 3. Verify Setup

```bash
# Test authentication
gh auth status

# Should show:
# ✓ Logged in to github.com as YOUR_USERNAME
```

## Security Best Practices

### ✅ DO:
- ✅ Add `.env` to `.gitignore` (always!)
- ✅ Use tokens with minimal required scopes
- ✅ Rotate tokens periodically (every 90 days)
- ✅ Delete tokens you're not using
- ✅ Use different tokens for different projects

### ❌ DON'T:
- ❌ Commit `.env` to git (check .gitignore!)
- ❌ Share your token with others
- ❌ Use tokens with more permissions than needed
- ❌ Leave old tokens active indefinitely

## Token Rotation

Rotate your token every 90 days:

1. Create new token (same scopes)
2. Update `.env` with new token
3. Test: `gh auth status`
4. Delete old token from GitHub settings

## Troubleshooting

### "GITHUB_TOKEN not found"

**Problem**: `.env` file missing or not in project root

**Solution**:
```bash
# Check if .env exists
ls -la .env

# If missing, create it
cp plugins/autonomous-dev/.env.example .env
# Then edit with your token
```

### "gh: command not found"

**Problem**: GitHub CLI not installed

**Solution**:
```bash
# macOS
brew install gh

# Linux
sudo apt install gh

# Windows
choco install gh
```

### "Bad credentials"

**Problem**: Token invalid or expired

**Solution**:
1. Generate new token at https://github.com/settings/tokens
2. Update `.env` with new token
3. Restart your terminal

### "Resource not accessible by integration"

**Problem**: Token missing required scopes

**Solution**:
1. Go to https://github.com/settings/tokens
2. Edit your token
3. Ensure `repo` and `read:org` are checked
4. Save changes

## Optional: Repository Auto-Detection

The orchestrator auto-detects your repository from:

```bash
git config --get remote.origin.url
```

If this doesn't work, manually set in `.env`:

```bash
GITHUB_REPO=owner/repository
```

## Workflow with GitHub Integration

Once configured:

1. **Create GitHub Milestone** (matches sprint in PROJECT.md)
   - Example: "Sprint 4: Memory Optimization"

2. **Add Issues to Milestone**
   - Issue #47: "Add gradient checkpointing"
   - Issue #51: "Optimize memory allocation"

3. **Reference sprint in PROJECT.md**
   ```markdown
   Current Sprint: Sprint 4: Memory Optimization
   GitHub Milestone: Sprint 4: Memory Optimization
   ```

4. **Work happens automatically**
   ```bash
   You: "implement gradient checkpointing"

   Orchestrator:
   ✅ Reads PROJECT.md (Sprint 4)
   ✅ Queries GitHub Milestone "Sprint 4"
   ✅ Finds Issue #47
   ✅ Coordinates dev team
   ✅ Auto-updates issue status
   ✅ Closes issue when complete
   ```

## GitHub-Free Usage

Don't want GitHub integration? No problem!

Simply don't create `.env` file. Orchestrator works fine with just PROJECT.md:

```bash
You: "implement gradient checkpointing"

Orchestrator:
✅ Reads PROJECT.md
✅ Validates alignment
✅ Coordinates dev team
✅ Reports progress
⚠️  GitHub sync disabled (no .env)
```

Everything works except GitHub auto-updates.

---

**Questions?** See [GitHub Personal Access Tokens documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

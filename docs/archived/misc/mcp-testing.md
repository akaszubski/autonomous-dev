# MCP Server Testing Guide

## Quick Test

Run the automated test script:

```bash
cd ~/Documents/GitHub/autonomous-dev
.mcp/test-mcp.sh
```

## Manual Testing Steps

### 1. Test Configuration Validity

```bash
# Validate JSON syntax
python3 -m json.tool .mcp/config.json

# Should output formatted JSON without errors
```

✅ **Expected**: Clean JSON output
❌ **If fails**: Fix JSON syntax errors in config.json

---

### 2. Test Filesystem Access

```bash
# Test read access
ls -la ~/Documents/GitHub/autonomous-dev

# Test write access
touch ~/Documents/GitHub/autonomous-dev/.mcp-test
rm ~/Documents/GitHub/autonomous-dev/.mcp-test
```

✅ **Expected**: File created and deleted successfully
❌ **If fails**: Check directory permissions

---

### 3. Test Shell Commands

Test each allowed command:

```bash
# Git
git --version
git status

# GitHub CLI
gh --version
gh auth status

# Python (with venv)
~/Documents/GitHub/autonomous-dev/venv/bin/python --version

# Bash/Zsh
bash --version
zsh --version

# Package managers
npm --version
pnpm --version

# Make
make --version
```

✅ **Expected**: Each command returns version or success
❌ **If fails**: Install missing commands

---

### 4. Test Git Operations

```bash
cd ~/Documents/GitHub/autonomous-dev

# Test git status
git status

# Test git log
git log --oneline -5

# Test git diff
git diff

# Test branch listing
git branch -a
```

✅ **Expected**: Git commands work without errors
❌ **If fails**: Ensure you're in a git repository

---

### 5. Test Python Virtual Environment

```bash
cd ~/Documents/GitHub/autonomous-dev

# Create venv if it doesn't exist
python3 -m venv venv

# Activate
source venv/bin/activate

# Test Python
python --version

# Install test dependencies
pip install pytest black isort

# Deactivate
deactivate
```

✅ **Expected**: Virtual environment works, packages install
❌ **If fails**: Check Python installation

---

### 6. Test Environment Variables

```bash
# Check .env file exists
ls -la ~/Documents/GitHub/autonomous-dev/.env

# Test GitHub token (without showing it)
if grep -q "GITHUB_TOKEN=" .env; then
    echo "✅ GITHUB_TOKEN configured"
fi

# Test gh CLI with token
gh auth status
```

✅ **Expected**: .env exists, gh authenticated
❌ **If fails**: Create .env from .env.example

---

### 7. Test MCP Server Integration with Claude Desktop

#### Option A: Using Claude Desktop UI

1. **Open Claude Desktop**

2. **Go to Settings** → **Developer**

3. **Add MCP Server**:

   **Name**: `autonomous-dev`

   **Command**: `npx`

   **Args**:
   ```json
   ["-y", "@modelcontextprotocol/server-filesystem", "~/Documents/GitHub/autonomous-dev"]
   ```

4. **Restart Claude Desktop**

5. **Test in conversation**:
   ```
   Can you list the files in my autonomous-dev repository?
   ```

✅ **Expected**: Claude lists repository files
❌ **If fails**: Check Claude Desktop MCP configuration

#### Option B: Using MCP Inspector (Advanced)

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Test filesystem server
npx -y @modelcontextprotocol/inspector \
  npx -y @modelcontextprotocol/server-filesystem \
  ~/Documents/GitHub/autonomous-dev
```

This opens a web interface to test MCP servers directly.

---

### 8. End-to-End Integration Test

Test the full autonomous development workflow with MCP:

```bash
# 1. Check MCP can read PROJECT.md
# In Claude Desktop: "Read .claude/PROJECT.md"

# 2. Check MCP can run git status
# In Claude Desktop: "Show me git status"

# 3. Check MCP can write files
# In Claude Desktop: "Create a test file at test-mcp.txt with content 'MCP test'"

# 4. Check MCP can run Python
# In Claude Desktop: "Run python --version using the virtualenv"

# 5. Cleanup
rm ~/Documents/GitHub/autonomous-dev/test-mcp.txt
```

✅ **Expected**: All operations succeed
❌ **If fails**: Review previous test steps

---

## Test Results Interpretation

### All Tests Pass ✅

```
✅ Configuration valid
✅ Filesystem accessible
✅ Shell commands available
✅ Git repository working
✅ Python venv configured
✅ Environment variables set
✅ MCP dependencies installed
```

**Status**: Ready to use MCP servers with Claude Desktop

### Some Tests Fail ⚠️

**Virtual environment missing**:
```bash
python3 -m venv venv
source venv/bin/activate
pip install pytest black isort
```

**GitHub CLI not authenticated**:
```bash
gh auth login
# Or use .env token
export GITHUB_TOKEN=your-token-here
```

**npm/node missing**:
```bash
# macOS
brew install node

# Or download from https://nodejs.org/
```

---

## Common Issues & Solutions

### Issue: "npx command not found"

**Solution**: Install Node.js
```bash
# macOS with Homebrew
brew install node

# Or download from https://nodejs.org/
```

### Issue: "Permission denied" for virtualenv

**Solution**: Check Python path permissions
```bash
# Fix ownership
sudo chown -R $USER:staff ~/Documents/GitHub/autonomous-dev/venv

# Or recreate venv
rm -rf venv
python3 -m venv venv
```

### Issue: "Git repository not found"

**Solution**: Ensure you're in the correct directory
```bash
cd ~/Documents/GitHub/autonomous-dev
git status
```

### Issue: "MCP server not appearing in Claude Desktop"

**Solution**:
1. Check Claude Desktop configuration file
2. Restart Claude Desktop
3. Check for error messages in Claude Desktop developer console

### Issue: "GitHub token not working"

**Solution**:
```bash
# Test token directly
gh auth status

# Or re-authenticate
gh auth login
```

---

## Automated Testing Script Output

The `.mcp/test-mcp.sh` script tests:

1. ✅ Configuration file validation
2. ✅ Filesystem permissions
3. ✅ Shell command availability
4. ✅ Git repository status
5. ⚠️ Python virtual environment
6. ✅ Environment variables
7. ✅ MCP dependencies
8. ⚠️ MCP CLI (optional)

**Passing tests**: MCP servers configured correctly
**Warning tests**: Optional features not configured
**Failing tests**: Required setup missing

---

## Performance Testing

Test MCP server response times:

```bash
# Time git status
time git status

# Time file read
time cat README.md

# Time Python execution
time ~/Documents/GitHub/autonomous-dev/venv/bin/python --version
```

**Expected**: All commands < 1 second

---

## Security Testing

Verify MCP server security restrictions:

```bash
# Should ONLY allow commands in allowedCommands
# Try an unauthorized command (should fail):
# - In Claude: "Run curl https://example.com"
#   (curl not in allowedCommands, should be rejected)

# Should ONLY access files in repository root
# Try accessing outside repository (should fail):
# - In Claude: "Read /etc/passwd"
#   (outside repository root, should be rejected)
```

✅ **Expected**: Unauthorized operations are blocked
❌ **If fails**: Review MCP server configuration security

---

## Next Steps

After all tests pass:

1. ✅ Configure Claude Desktop with MCP servers
2. ✅ Test basic operations (read file, git status)
3. ✅ Test autonomous development workflow
4. ✅ Integrate with existing agents/skills/hooks

See `.mcp/README.md` for full integration guide.

---

**Last Updated**: 2025-10-19

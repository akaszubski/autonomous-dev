# File Organization - Detailed Guide

## Special Cases

### Case 1: New Directory Category

```
🤖 file-organization skill activated

Proposed: ./scripts/deploy/deploy.sh
Rule Check: scripts/deploy/ not in documented categories

New category detected: scripts/deploy/
This isn't documented in CLAUDE.md.

Options:
1. Allow (one-off script) → use scripts/deploy.sh
2. Create new category → Add to CLAUDE.md:

   ## File Organization
   - scripts/deploy/ - Deployment scripts

Create new category? [y/N]
```

If yes:
- Create directory
- Update CLAUDE.md with new category
- Proceed with file creation

If no:
- Move to `scripts/` root instead

### Case 2: Configuration Files

```
Proposed: ./tsconfig.json
Rule Check: Configuration file
Enforcement: SKIP (config files allowed in root)

✅ Config file - root location is standard
```

**Allowed in root without restriction**:
- `package.json`, `tsconfig.json`, `pyproject.toml`, `Cargo.toml`
- `.env`, `.env.example`, `.gitignore`
- `Dockerfile`, `docker-compose.yml`

### Case 3: Hidden Files/Directories

```
Proposed: ./.github/workflows/ci.yml
Rule Check: Hidden directory
Enforcement: SKIP (hidden dirs have different conventions)

✅ GitHub workflows - standard location
```

**Allowed without restrictions**:
- `.github/` - GitHub-specific files
- `.vscode/` - VS Code settings
- `.idea/` - JetBrains IDE settings

---

## Integration with Pre-Commit Hook

**Pre-commit validation** (enhanced hook):

```bash
#!/bin/bash
# .claude/hooks/pre-commit.sh

# Check for files in wrong locations
echo "🔍 Validating file organization..."

# Check for non-essential .md in root
ROOT_MD_COUNT=$(git diff --cached --name-only --diff-filter=A | \
  grep '^[^/]*\.md$' | \
  grep -v -E '(README|CHANGELOG|LICENSE|CONTRIBUTING|CODE_OF_CONDUCT|SECURITY|CLAUDE|PROJECT)\.md' | \
  wc -l)

if [ "$ROOT_MD_COUNT" -gt 0 ]; then
  echo "❌ Attempting to commit non-essential .md files in root:"
  git diff --cached --name-only --diff-filter=A | \
    grep '^[^/]*\.md$' | \
    grep -v -E '(README|CHANGELOG|LICENSE|CONTRIBUTING|CODE_OF_CONDUCT|SECURITY|CLAUDE|PROJECT)\.md'
  echo ""
  echo "Move to docs/ subdirectories per CLAUDE.md"
  exit 1
fi

# Check for shell scripts in root
ROOT_SH=$(git diff --cached --name-only --diff-filter=A | grep '^[^/]*\.sh$' | wc -l)

if [ "$ROOT_SH" -gt 0 ]; then
  echo "❌ Attempting to commit shell scripts in root:"
  git diff --cached --name-only --diff-filter=A | grep '^[^/]*\.sh$'
  echo ""
  echo "Move to scripts/ subdirectories per CLAUDE.md"
  exit 1
fi

echo "✅ File organization validated"
```

---

## Configuration

# Sync Validator - Detailed Process

Complete sync validation process with recovery strategies.

---

## Phase 1: Pre-Sync Analysis

1. **Check local state**:
   - Uncommitted changes? (warn user)
   - Stale local branches? (clean up)
   - Existing conflicts? (resolve first)

2. **Check remote state**:
   - New commits on main
   - New tags/releases
   - Breaking changes in log

3. **Assess risk**:
   - Number of new commits (< 5 = low, > 20 = high)
   - Files changed in sync area (hooks, agents, configs)
   - Any breaking change indicators

---

## Phase 2: Fetch & Analyze Changes

1. **Git fetch latest**:
   ```bash
   git fetch origin main
   ```

2. **Categorize changes**:
   - **Safe**: Agent prompts, documentation, non-critical code
   - **Requires attention**: Hook changes, config updates, dependencies
   - **Breaking**: API changes, removed features, version bumps

---

## Phase 3: Merge Strategy

| Change Type | Strategy |
|-------------|----------|
| Safe | Direct merge |
| Risky | Ask user before merging |
| Conflicts | Detect & present options |
| Breaking | Explain impact |

---

## Phase 4: Validation & Testing

1. **Syntax validation**:
   ```bash
   python -m py_compile file.py
   bash -n script.sh
   python -m json.tool config.json
   ```

2. **Plugin integrity check**:
   - All agents present
   - No missing files
   - Config valid

3. **Dependency validation**:
   - Python packages installable
   - Node packages installable
   - No version conflicts

---

## Conflict Detection Categories

### Category 1: Auto-Merge Safe
```
Changes to:
- docs/
- README.md, CHANGELOG.md
- Agent prompts (non-critical)
- Comments in code

→ Safe to merge automatically
```

### Category 2: Requires User Confirmation
```
Changes to:
- .claude/hooks/
- .claude/commands/
- .claude/agents/
- pyproject.toml (dependencies)

→ Ask user: Accept upstream? [Y/n/manual]
```

### Category 3: Potential Breaking
```
Changes to:
- API signatures
- Required environment variables
- Dependency version constraints (major bump)
- Hook behavior changes

→ Warn user + require explicit confirmation
```

---

## Conflict Resolution

```json
{
  "conflict_found": true,
  "file": ".claude/PROJECT.md",
  "options": [
    {"option": "ACCEPT UPSTREAM", "description": "Use latest version"},
    {"option": "ACCEPT LOCAL", "description": "Keep your changes"},
    {"option": "MANUAL", "description": "Resolve by hand"}
  ]
}
```

---

## Error Recovery Strategies

### If Merge Fails
```
Options:
1. ABORT & ROLLBACK → Reset to before sync
2. MANUAL FIX → Review conflict markers, guide resolution
```

### If Plugin Build Fails
```
Options:
1. REVERT AGENT → Use previous version
2. FIX INLINE → Correct error, rebuild
```

### If Dependencies Fail
```
Options:
1. AUTO-INSTALL → pip install -r requirements.txt
2. MANUAL INSTALL → User installs manually
3. USE LOCAL VERSION → Fall back to compatible version
```

---

## Rollback Strategy

```bash
# Full rollback to pre-sync state
git reset --hard ORIG_HEAD
git clean -fd

# Or selective rollback
git revert <commit>
```

---

## Validation Checklist

```
Pre-Sync:
  ✓ No uncommitted changes blocking sync
  ✓ Remote has new commits

Post-Fetch:
  ✓ New commits analyzed
  ✓ Conflicts detected

Post-Merge:
  ✓ All files merged correctly
  ✓ No conflict markers remaining
  ✓ Syntax valid

Post-Rebuild:
  ✓ Plugin builds successfully
  ✓ All agents present
  ✓ Hooks executable
  ✓ Configuration valid

Final:
  ✓ /health-check passes
```

---

## Security Considerations

- **Path Validation**: Check paths within project, reject `..` or symlinks
- **File Operations**: Backup before overwrite, atomic operations
- **Configuration Trust**: Validate `installPath` exists
- **Shared Systems**: Warn about credentials in .env

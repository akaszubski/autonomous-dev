# Semantic Validation - Detailed Guide

## When to Use This Skill

**Auto-invoke triggers** (when implemented):
- `/align-project` command (Phase 2: Semantic Validation)
- After major code changes (10+ files modified)
- Before releases

**Manual invoke**:
- Investigating documentation accuracy
- After refactoring
- When documentation feels stale

---

## What This Skill Detects

### 1. Outdated Documentation

**Problem**: Documentation claims X, code implements Y

**Example**:
```markdown
# PROJECT.md:181
### Tool Calling (CRITICAL ISSUE)
Status: Still investigating duplicate tool calls
```

```typescript
// src/convert.ts:45 (committed 3 hours ago)
// SOLVED: Streaming tool parameters via input_json_delta
case "tool-input-delta": {
  controller.enqueue({ type: "input_json_delta", ... });
}
```

**Detection**: GenAI compares documented status with implementation reality.

### 2. Version Mismatches

**Problem**: Different versions across files

**Example**:
- `CHANGELOG.md:8` says `v2.0.0`
- `package.json:3` says `v1.0.0`
- `README.md:5` says `latest stable: 1.5.0`

**Detection**: Extract version numbers from all docs, flag inconsistencies.

### 3. Architecture Drift

**Problem**: Documented architecture doesn't match current structure

**Example**:
```markdown
# PROJECT.md:95
Architecture: Simple proxy server
```

```
# Actual codebase structure:
src/
├── translation-layers/  (5 different layers)
├── format-converters/
├── stream-handlers/
└── protocol-adapters/
```

**Detection**: Analyze file organization, compare to documented architecture.

### 4. Stale Claims

**Problem**: Documentation makes claims no longer true

**Example**:
```markdown
# README.md:8
"A simplified fork of anyclaude"
```

```
# Reality:
- 2000+ lines of custom code
- Complex 5-layer architecture
- Completely different from original
```

**Detection**: Look for words like "simple", "basic", "fork" and verify against codebase size/complexity.

### 5. Broken Promises

**Problem**: Documentation promises features not implemented

**Example**:
```markdown
# README.md:45
## Features

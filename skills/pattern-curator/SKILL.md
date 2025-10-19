---
name: pattern-curator
type: automation
callable: true
version: 1.0.0
description: Learn and validate engineering patterns from codebase
trigger: After code edits, on-demand pattern analysis
auto_invoke: false
owner: Automated (runs via hook or manual)
keywords: pattern, learning, consolidation, validation, curation
---

# Pattern Curator Skill

## Purpose
Automatically detect, track, validate, and promote engineering patterns from actual codebase usage.

**Key Principle**: Patterns are LEARNED from code, not prescribed. The system observes what developers actually do, not what they say they do.

---

## Pattern Lifecycle

```
Discovery (1 use)
    ↓
Candidate (2 uses)
    ↓
Validated (≥3 uses) → Promoted to PATTERNS.md
    ↓
Archived (unused 30 days) → Moved to archive section
```

### State Definitions

1. **Discovery** (1 occurrence)
   - Pattern detected in codebase
   - Logged to `.claude/cache/patterns/candidates.json`
   - Not yet shown in PATTERNS.md

2. **Candidate** (2 occurrences)
   - Pattern used twice, shows consistency
   - Added to PATTERNS.md under "Candidate" section
   - Still being validated

3. **Validated** (≥3 occurrences)
   - Pattern used 3+ times, proven useful
   - Promoted to PATTERNS.md "Validated" section
   - Becomes official project pattern

4. **Archived** (unused 30+ days)
   - Pattern not seen in recent code
   - Moved to PATTERNS.md "Archived" section
   - Preserved for reference, not active

---

## Usage

### Automated (via hook - recommended)
```bash
# Hook triggers after every Python file write
# See .claude/settings.json PostToolUse hooks
python .claude/skills/pattern-curator/detect_patterns.py $CLAUDE_FILE_PATHS
```

### Manual (on-demand)
```bash
# Scan entire codebase
python .claude/skills/pattern-curator/detect_patterns.py --full-scan

# Scan specific directory
python .claude/skills/pattern-curator/detect_patterns.py src/[project_name]/

# Update PATTERNS.md from cached data
python .claude/skills/pattern-curator/update_patterns.py

# Show pattern statistics
python .claude/skills/pattern-curator/detect_patterns.py --stats
```

---

## Pattern Categories

Patterns are automatically classified into:

### Code Quality
- Type hints on public APIs
- Google-style docstrings
- PEP 8 formatting
- Error message templates

### Performance
- Caching strategies (@lru_cache, manual caches)
- Vectorization (numpy operations)
- Batch processing (batch_size parameters)
- Async operations (async/await patterns)

### Testing
- Quality gates (threshold checks)
- Coverage requirements (80% minimum)
- TDD patterns (test-first development)
- Assertion patterns

### [FRAMEWORK] Framework (Domain-Specific)
- GPU memory management (mx.metal.clear_cache)
- Nested layer access (model.model.layers[i])
- Lazy evaluation (mx.eval)
- Metal-specific optimizations

### Resilience
- Dual API support (Anthropic + OpenAI fallback)
- Error handling with context
- Retry mechanisms
- Graceful degradation

### User Experience
- Progress tracking (tqdm, progress bars)
- Helpful error messages (context + expected + docs link)
- Interactive CLIs (keyboard shortcuts)

---

## Detection Algorithm

### Pattern Matching

```python
# Example: Detect "Type Hints" pattern
def detect_type_hints(file_path: str) -> bool:
    with open(file_path, 'r') as f:
        content = f.read()

    tree = ast.parse(content)
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

    # Pattern exists if >50% of public functions have type hints
    if not functions:
        return False

    typed_funcs = [f for f in functions
                   if not f.name.startswith('_')
                   and f.returns is not None]

    return len(typed_funcs) / len(functions) > 0.5
```

### Validation Criteria

Pattern is validated (promoted) when:
1. ✅ Used in ≥3 different files
2. ✅ Consistent implementation across files
3. ✅ No counter-examples (anti-patterns) found
4. ✅ Still in active use (seen in last 30 days)

---

## Output Format

### candidates.json (Cache)
```json
{
  "type_hints": {
    "category": "code_quality",
    "description": "Type hints for all public APIs",
    "count": 53,
    "files": ["src/[project_name]/trainer.py", "..."],
    "first_seen": "2025-10-19T10:00:00",
    "last_seen": "2025-10-19T14:30:00",
    "state": "validated"
  }
}
```

### PATTERNS.md (Public)
Pattern added to appropriate section with:
- Pattern name
- Usage count
- Status (Validated/Candidate)
- Category
- Description
- Code example
- Rationale

---

## Integration with Agents

### Planner Agent
**Uses**: Validated patterns to design solutions
**Context**: Loads PATTERNS.md (full) to see what patterns exist
**Benefit**: Designs solutions consistent with existing codebase

### Reviewer Agent
**Uses**: Validated patterns to check code quality
**Context**: Loads PATTERNS.md (full) to verify pattern adherence
**Benefit**: Catches deviations from established patterns

### Pattern-Curator (This Skill)
**Uses**: Runs detection after code changes
**Context**: Minimal - just the changed files
**Benefit**: Learns patterns without human intervention

---

## Example Workflow

```
1. Developer writes new code:
   src/[project_name]/new_feature.py

2. PostToolUse hook triggers:
   python detect_patterns.py src/[project_name]/new_feature.py

3. Pattern detected:
   "Batch Processing" found (batch_size parameter)

4. State updated:
   candidates.json: "batch_processing": {"count": 11, "state": "validated"}

5. PATTERNS.md updated:
   Pattern moved from "Candidate" to "Validated" section

6. Next code review:
   Reviewer agent sees "Batch Processing" is validated pattern
   Checks new code follows this pattern
```

---

## Commands

### detect_patterns.py
```bash
# Scan and update counts
python detect_patterns.py [files...]

# Full codebase scan
python detect_patterns.py --full-scan

# Show statistics
python detect_patterns.py --stats

# Dry run (don't update cache)
python detect_patterns.py --dry-run [files...]
```

### update_patterns.py
```bash
# Regenerate PATTERNS.md from cache
python update_patterns.py

# Force promotion (testing only)
python update_patterns.py --promote pattern_name

# Archive old patterns
python update_patterns.py --archive-unused

# Show what would change
python update_patterns.py --dry-run
```

---

## Configuration

### Pattern Thresholds (Customizable)

```json
{
  "validation_threshold": 3,
  "archive_days": 30,
  "min_confidence": 0.7,
  "categories": {
    "code_quality": {"weight": 1.0},
    "performance": {"weight": 1.2},
    "testing": {"weight": 1.1},
    "[framework]": {"weight": 1.3},
    "resilience": {"weight": 1.0},
    "ux": {"weight": 0.9}
  }
}
```

Located in: `.claude/skills/pattern-curator/config.json`

---

## Anti-Patterns (What NOT to Promote)

Some patterns should NEVER be validated:

- ❌ Hardcoded credentials
- ❌ Commented-out code blocks
- ❌ Duplicate code (copy-paste)
- ❌ Overly complex functions (>50 lines)
- ❌ Missing error handling
- ❌ Magic numbers without constants

These are flagged in detection but NOT promoted to PATTERNS.md.

---

## Maintenance

### Monthly Audit
Review PATTERNS.md:
1. Are validated patterns still used? (check last_seen)
2. Should candidates be promoted? (check count)
3. Should archived patterns be removed? (>90 days unused)

### Quarterly Cleanup
```bash
# Archive patterns unused >30 days
python update_patterns.py --archive-unused

# Remove archived patterns >90 days
python update_patterns.py --remove-ancient

# Regenerate from scratch
python detect_patterns.py --full-scan --rebuild
```

---

## Files Created

```
.claude/skills/pattern-curator/
├── SKILL.md                    # This file
├── detect_patterns.py          # Pattern detection script
├── update_patterns.py          # PATTERNS.md updater
├── config.json                 # Configuration
├── templates/
│   └── pattern_template.md    # Template for new patterns
└── examples/
    └── example_patterns.json  # Example pattern definitions
```

---

## Dependencies

- Python 3.11+
- ast module (standard library)
- pathlib (standard library)
- json (standard library)
- No external dependencies

---

## Future Enhancements

- Machine learning to detect complex patterns
- Cross-file pattern relationships
- Pattern conflict detection
- Automatic code suggestion based on patterns
- Integration with IDE (show patterns as you type)

---

**Version**: 1.0.0
**Last Updated**: 2025-10-19
**Owner**: Automated (triggered by hooks)
**Human Review**: Monthly audit of promoted patterns

# Advisor Test Scenario 1: Command Explosion

## Test Proposal

**User Request**: "Let's add 15 new commands for fine-grained control:
- /format-python
- /format-javascript
- /test-unit-only
- /test-integration-only
- /commit-no-test
- /commit-with-format
- /security-scan-dependencies
- /security-scan-secrets
- /docs-update-readme
- /docs-update-api
- /lint-python
- /lint-javascript
- /coverage-report
- /coverage-enforce
- /validate-project-md"

## Expected Advisor Analysis

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL ANALYSIS: Add 15 Granular Commands
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Alignment with PROJECT.md

📊 Alignment Score: 1/10

✅ Serves Goals:
- (none - actively conflicts)

⚠️ Conflicts with:
- Goal: "Command minimalism - 8 commands total" (PROJECT.md:18)
- Goal: "Team, not toolkit" (PROJECT.md:14)
- Success Metric: "-80% complexity" (PROJECT.md:34)
- Philosophy: "Minimal user intervention" (PROJECT.md:30)

## Complexity Assessment

🔴 VERY HIGH CONFLICT

**Current State**: 8 commands (5 core + 3 utilities)
**Proposed State**: 23 commands (8 current + 15 new)
**Change**: +188% command count

**Impact**: Reverses v2.5.0 simplification that moved from 40 → 8 commands

## Pros & Cons

### Pros ✅
1. Fine-grained control for power users
2. Explicit about what each command does
3. Users can pick exactly what they need

### Cons ⚠️
1. **Directly violates "command minimalism" goal**
2. Returns to "toolkit" model (not "team" model)
3. User must orchestrate workflow manually
4. Cognitive load: remembering 23 commands
5. Against recent architectural decision (Issue #14 archive)
6. Reverses streamlining work done in v2.4.0/v2.5.0

## Trade-Off Analysis

**If we proceed:**
- ✅ Gain: Fine-grained control
- ❌ Lose: Simplicity (8 → 23 commands)
- ❌ Lose: Autonomous team model
- ❌ Lose: Command minimalism principle
- ⏱️ Maintenance: 23 commands to maintain

**If we don't:**
- ✅ Keep: Simplicity (8 commands)
- ✅ Keep: Autonomous team model
- ❌ Miss: Fine-grained control
- ✅ Save: Maintenance burden

## Alternative Approaches

### Option A: Flags on Existing Commands (RECOMMENDED)
**Implementation**: Add optional flags to `/auto-implement` and `/test`

```bash
/auto-implement --skip-tests  # For quick iterations
/test --unit-only             # For targeted testing
/auto-implement --format-only # For pre-commit formatting
```

**Cost**: 2 days, 200 LOC
**Pros**:
- Preserves 8-command limit
- Maintains autonomous model
- Provides granular control when needed
**Cons**:
- Flags are "escape hatches" (should be rare)
**Best for**: Power users who need occasional fine control

### Option B: Configuration Profiles
**Implementation**: `.claude/profiles/` with presets

```bash
# .claude/profiles/fast.yml
auto_implement:
  skip_tests: true
  skip_security: false
  
# Usage
/auto-implement --profile=fast "quick feature"
```

**Cost**: 1 week, 500 LOC
**Pros**:
- Reusable configurations
- No command explosion
- Team model preserved
**Cons**:
- Need to learn profile system
**Best for**: Teams with consistent workflows

### Option C: Interactive Mode
**Implementation**: Single command asks clarifying questions

```bash
/auto-implement "add auth"
  → Skip tests this time? [y/N]
  → Custom commit message? [y/N]
  → Skip security scan? [y/N]
```

**Cost**: 3 days, 300 LOC
**Pros**:
- No command memorization
- Contextual choices
- Stays autonomous
**Cons**:
- Extra prompts (slower)
**Best for**: Occasional fine control

## Risk Assessment

### Technical Risks 🔧
1. **Maintenance Burden**
   - Impact: HIGH (23 commands × documentation × testing)
   - Likelihood: VERY HIGH
   - Mitigation: None (inherent to approach)

2. **User Confusion**
   - Impact: HIGH ("Which command do I use?")
   - Likelihood: HIGH
   - Mitigation: Decision tree docs (but defeats simplicity)

### Project Risks 📋
1. **Architectural Regression**
   - Impact: VERY HIGH (reverses v2.4.0/v2.5.0 work)
   - Likelihood: VERY HIGH
   - Mitigation: None - this IS the regression

2. **Violates Project Philosophy**
   - Impact: CRITICAL (against stated principles)
   - Likelihood: 100%
   - Mitigation: Update PROJECT.md (but defeats purpose)

## Red Flags 🚩

- 🚩 **Directly violates Goal: "8 commands maximum"**
- 🚩 **Reverses recent architectural work (v2.4.0 → v2.5.0)**
- 🚩 **Returns to "toolkit" model (explicitly rejected)**
- 🚩 **+188% command count (opposite of -80% goal)**
- 🚩 **Against project philosophy on multiple dimensions**

## Recommendation

❌ **REJECT**

**Rationale**:
This proposal fundamentally conflicts with autonomous-dev's core 
philosophy of "team, not toolkit" and "command minimalism". 

You spent v2.4.0 and v2.5.0 moving from 40 → 8 commands specifically 
to avoid this exact problem. Adding 15 commands would undo that work 
and violate stated project goals.

The request for "fine-grained control" is valid, but should be 
solved via Option A (flags) or Option B (profiles), not command 
explosion.

**If user still wants this:**
1. Update PROJECT.md to remove "command minimalism" goal
2. Change philosophy from "team" to "toolkit"
3. Accept return to 40-command model
4. Justify why v2.4.0/v2.5.0 work should be undone

**Better path forward:**
1. Implement Option A (flags on existing commands)
2. Keep 8-command limit
3. Provide escape hatches for power users
4. Maintain autonomous team model

**Next Steps:**
- [ ] Review PROJECT.md goals (are they still valid?)
- [ ] If goals are valid, reject this proposal
- [ ] Implement Option A (flags) for rare fine control
- [ ] Document when to use flags vs default behavior

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Analysis completed in 3 minutes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Test Validation

**Expected outcome:**
✅ Advisor detects fundamental conflict with project goals
✅ Alignment score is very low (1/10)
✅ Identifies this reverses recent architectural work
✅ Provides concrete alternatives that preserve goals
✅ Recommendation is clear REJECT with rationale

**What makes this a good test:**
- Real conflict with documented goals
- Multiple red flags
- Historical context matters (recent refactoring)
- Alternatives exist that solve the problem differently

## Follow-Up Test

After getting REJECT recommendation, user might say:

**User**: "But users are asking for more control!"

**Advisor should respond**:
"Valid feedback, but there's a better way:

1. **Add flags to existing commands** (Option A)
   - Preserves 8-command limit
   - Provides control when needed
   - Example: `/test --unit-only`

2. **Make flags discoverable**
   - `/auto-implement --help` shows all flags
   - Document common flag combinations

3. **Track flag usage**
   - If certain flags used >50% of time, reconsider defaults
   - Data-driven decision-making

This addresses user needs WITHOUT violating project principles."

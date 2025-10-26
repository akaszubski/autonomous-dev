---
description: Generate comprehensive PROJECT.md from codebase analysis or template
---

# Create PROJECT.md

**Auto-generate PROJECT.md by analyzing your codebase, or create from template**

---

## Usage

```bash
/create-project-md [--generate|--template|--interactive]
```

**Time**: 30-90 seconds (depending on mode)
**Output**: PROJECT.md (300-500 lines)

**Modes**:
- `--generate` (default) - AI analyzes codebase and creates comprehensive PROJECT.md
- `--template` - Create template with TODO placeholders
- `--interactive` - Wizard asks questions, then generates

---

## Why PROJECT.md Matters

PROJECT.md is the **source of truth** for autonomous-dev:

- ✅ **Alignment validation**: `/align-project` validates against PROJECT.md
- ✅ **Agent context**: All agents read PROJECT.md before working
- ✅ **File organization**: Defines where files should go
- ✅ **Architecture documentation**: Describes system design
- ✅ **Known issues tracking**: Documents problems and solutions

**Without PROJECT.md**, autonomous-dev features are disabled.

---

## Mode 1: Generate from Codebase (Default)

**AI analyzes your repository and creates PROJECT.md automatically**

### What Gets Analyzed

1. **README.md** - Project description, goals, setup
2. **package.json / pyproject.toml / Cargo.toml** - Dependencies, tech stack
3. **CONTRIBUTING.md** - Development workflow
4. **src/ structure** - Architecture patterns
5. **tests/ structure** - Testing strategy
6. **docs/ organization** - Documentation map
7. **Recent commits** - Development patterns

### Architecture Pattern Detection

Automatically detects:
- **Translation Layer** - Format conversion, adapters
- **MVC/MVVM** - Models, views, controllers separation
- **Microservices** - Multiple service directories
- **Event-Driven** - Pub/sub, message queues
- **Monolithic** - Single entry point

### Example Output

```bash
/create-project-md --generate

🔍 Analyzing codebase...

✅ Found README.md (extracting project vision)
✅ Found package.json (extracting tech stack)
✅ Analyzing src/ structure (12 files)
✅ Analyzing tests/ structure (unit + integration detected)
✅ Analyzing docs/ organization (4 categories)
✅ Reviewing recent commits (last 50)

🧠 Architecture pattern detected: Translation Layer
   - Files: convert-to-anthropic.ts, convert-from-lmstudio.ts
   - Pattern: Multi-format API translation
   - Complexity: 5 translation layers

✅ Generated PROJECT.md (437 lines)

📋 Sections Created:
✅ Project Vision (from README.md)
✅ Core Principle (Active Translation pattern)
✅ Architecture Overview (with ASCII diagram)
✅ Technology Stack (TypeScript, Node.js, 8 dependencies)
✅ File Organization Standards (current structure)
✅ Development Workflow (from package.json scripts)
✅ Testing Strategy (unit + integration, 24 tests detected)
✅ Documentation Map (docs/guides, docs/debugging, etc.)
✅ Known Issues (template ready for entries)

⚠️ Review These Sections (needs verification):
1. Lines 45-89: Architecture Diagram
   → Verify data flow is accurate

2. Lines 181-210: File Organization Rules
   → Adjust paths if needed

3. Lines 310-340: Testing Strategy
   → Confirm coverage targets

📝 Sections Marked TODO (needs your input):
- Line 95: Specific deployment process
- Line 142: Performance benchmarks
- Line 267: Scalability goals

Next Steps:
1. Review PROJECT.md
2. Fill in TODO sections
3. Run /align-project to validate
4. Commit PROJECT.md

Saved to: PROJECT.md
```

**When to use**:
- ✅ New project setup
- ✅ Existing project without PROJECT.md
- ✅ Want comprehensive documentation quickly
- ✅ Trust AI to analyze structure

---

## Mode 2: Template (Minimal)

**Create basic structure with examples and TODOs**

```bash
/create-project-md --template

✅ Created PROJECT.md from template (312 lines)

Each section includes:
- TODO placeholder
- Example of what to write
- Explanation of why it matters

Next Steps:
1. Open PROJECT.md
2. Replace TODO sections with your content
3. Follow examples provided
4. Save and run /align-project

Saved to: PROJECT.md
```

**When to use**:
- ✅ Want full control over content
- ✅ Project structure is non-standard
- ✅ Prefer manual documentation
- ✅ AI analysis not appropriate

---

## Mode 3: Interactive (Wizard)

**Answer questions, then AI generates PROJECT.md**

```bash
/create-project-md --interactive
```

**Questions Asked**:

1. **Primary goal of this project?**
   - Solve a specific problem
   - Provide a tool/library
   - Learning/experimental
   - Production application

2. **How would you describe the architecture?**
   - Simple/straightforward
   - Translation layer
   - Microservices
   - Event-driven

3. **Level of detail?**
   - Minimal (basic template)
   - Standard (good starter)
   - Comprehensive (deep analysis)

Then generates PROJECT.md based on:
- Your responses
- Codebase analysis
- Best practices

**When to use**:
- ✅ First time creating PROJECT.md
- ✅ Want guidance on what to include
- ✅ Unclear about architecture pattern
- ✅ Balance of control + automation

---

## Generated PROJECT.md Structure

### Required Sections (Always Included)

```markdown
# {Project Name} Project Documentation

## Project Vision
{What is this? Why does it exist?}

## Core Principle
{What makes this unique?}

## Architecture Overview
{High-level design + ASCII diagram}

### Architecture Pattern: {Detected}
{Explanation of pattern}

### Key Components
{List major components}

### Data Flow
{How data moves through system}

## Technology Stack
{Languages, frameworks, dependencies}

## File Organization Standards
{Where files should go + examples}

### Root Directory Policy
Maximum 8 essential .md files:
- README.md, CHANGELOG.md, LICENSE
- CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
- CLAUDE.md, PROJECT.md

All others in subdirectories.

### Directory Structure
{Current structure with descriptions}

### When Creating New Files
{Decision tree for file placement}

## Development Workflow
{Setup, building, testing, deployment}

## Known Issues
{Template for tracking problems}

## Testing Strategy
{Test categories, coverage, how to run}

## Documentation Map
{Where to find docs}
```

### Optional Sections (If Detected)

- **Translation Layer Pattern** - If format conversion detected
- **Authentication Methods** - If auth code detected
- **CI/CD Pipeline** - If workflows detected
- **Deployment** - If deployment config found

---

## ASCII Architecture Diagrams

For complex architectures, generates diagrams like:

```
┌─────────────────────────────────────────────┐
│          Client (Input Format)              │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│         This Project (Translator)           │
│  ┌─────────────────────────────────────┐   │
│  │  1. Receive Input                   │   │
│  └────────────┬────────────────────────┘   │
│               │                             │
│  ┌────────────▼────────────────────────┐   │
│  │  2. Convert Format                  │   │
│  └────────────┬────────────────────────┘   │
│               │                             │
│  ┌────────────▼────────────────────────┐   │
│  │  3. Send to Provider                │   │
│  └────────────┬────────────────────────┘   │
└───────────────┼─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────┐
│        Provider (Output Format)             │
└─────────────────────────────────────────────┘
```

---

## Error Handling

### If README.md Missing

```
⚠️ No README.md found

PROJECT.md typically builds on README.md content.

Options:
1. Create minimal PROJECT.md (you'll fill in vision)
2. Create README.md first (recommended)
3. Use interactive mode to provide vision

Choice? [1/2/3]
```

### If No src/ Directory

```
⚠️ No src/ directory detected

Can't analyze architecture without source code.

Detected structure:
{List top-level directories}

Is source code in a different location?
- Enter directory name (e.g., "lib", "app")
- Or press Enter for template mode
```

### If PROJECT.md Already Exists

```
⚠️ PROJECT.md already exists (437 lines)

Options:
1. Backup and regenerate (saves to PROJECT.md.backup)
2. Create PROJECT-new.md (review and merge manually)
3. Cancel

Choice? [1/2/3]
```

### If Conflicting Information

```
⚠️ Inconsistent information detected:

README.md says: "Simple proxy server"
src/ structure suggests: Translation layer (5 components)

Which is more accurate?
1. Simple (README.md description)
2. Complex (codebase structure)
3. I'll clarify manually

Choice? [1/2/3]
```

---

## Integration with /setup

When running `/setup`, if PROJECT.md missing:

```
⚠️ No PROJECT.md found!

PROJECT.md is essential for autonomous-dev.

Options:
1. Generate from codebase (recommended) - AI analyzes repo
2. Create from template - Basic structure with TODOs
3. Interactive wizard - Answer questions, AI generates
4. Skip (you can run /create-project-md later)

Choice [1-4]:
```

---

## Success Criteria

After creation:
- ✅ PROJECT.md is 300-500 lines (substantial)
- ✅ All required sections present
- ✅ File organization standards defined
- ✅ Architecture diagram included (if complex)
- ✅ Only 10-20% needs customization
- ✅ Ready for `/align-project` validation

---

## Typical Workflow

### New Project

```bash
# 1. Install autonomous-dev
/plugin install autonomous-dev

# 2. Run setup
/setup

# 3. When prompted for PROJECT.md, choose generate
Choice [1-4]: 1

# 4. Review generated PROJECT.md
# (open in editor)

# 5. Fill in TODO sections

# 6. Validate
/align-project
```

### Existing Project

```bash
# 1. Generate PROJECT.md
/create-project-md --generate

# 2. Review output
# (read PROJECT.md)

# 3. Customize sections marked TODO

# 4. Validate alignment
/align-project

# 5. Fix any issues
Choice [1-4]: 2  # Fix interactively
```

---

## File Organization Examples in Generated PROJECT.md

The generated PROJECT.md includes clear examples:

```markdown
## When Creating New Files

### Shell Scripts (.sh)
❌ ./test-auth.sh
✅ ./scripts/test/test-auth.sh
✅ ./scripts/debug/debug-local.sh

### Documentation (.md)
❌ ./GUIDE.md (unless essential)
✅ ./docs/guides/user-guide.md
✅ ./docs/debugging/troubleshooting.md

### Source Code
❌ ./my-module.ts
✅ ./src/my-module.ts
✅ ./tests/unit/my-module.test.ts
```

---

## Template Quality Standards

Generated templates follow these standards:

- **Length**: 300-500 lines (substantial but not overwhelming)
- **Examples**: Every section has TODO + example + explanation
- **Diagrams**: ASCII diagrams for complex architectures
- **Actionable**: Clear next steps for customization
- **Complete**: All required sections present

---

## Troubleshooting

### "Analysis failed"

- Check: README.md exists and is readable
- Check: Project has standard structure (src/, package.json, etc.)
- Fallback: Use `--template` mode

### "Generated PROJECT.md too short" (&lt; 200 lines)

- Codebase may be minimal
- Add more sections manually
- Or use `--interactive` for guided creation

### "Architecture pattern not detected"

- Run `--interactive` and specify manually
- Or use `--template` and document yourself

---

## Related Commands

- `/setup` - Interactive setup wizard (calls this command)
- `/align-project` - Validate PROJECT.md alignment
- `/sync-docs` - Keep docs in sync with PROJECT.md

---

## Implementation

Invoke the **project-bootstrapper** agent to analyze the codebase and generate a comprehensive PROJECT.md file.

**Agent workflow**:

1. Analyzes codebase structure and existing documentation
2. Detects architecture patterns and tech stack
3. Generates comprehensive PROJECT.md with all required sections
4. Creates ASCII diagrams for complex architectures
5. Marks sections needing user customization

**Agent capabilities**:
- Read tool (existing docs)
- Grep/Glob (codebase analysis)
- Bash (git history, package info)

---

**Use this command to bootstrap PROJECT.md for new or existing projects. AI analysis creates 80-90% complete documentation in under 60 seconds.**

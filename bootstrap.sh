#!/bin/bash
set -e

# Claude Code 2.0 Bootstrap Script (Generic)
# Usage: ./scripts/bootstrap_project.sh /path/to/target/project
#
# This script copies GENERIC Claude Code 2.0 setup from the bootstrap template
# (NOT ReAlign-specific MLX/training stuff)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REALIGN_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
BOOTSTRAP_TEMPLATE="$SCRIPT_DIR"
TARGET_PROJECT="${1:-.}"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Claude Code 2.0 Bootstrap (Generic)                       ║"
echo "║     Multi-language autonomous development setup               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if bootstrap template exists
if [ ! -d "$BOOTSTRAP_TEMPLATE" ]; then
    echo "❌ Error: Bootstrap template not found at: $BOOTSTRAP_TEMPLATE"
    echo ""
    echo "The bootstrap template contains generic, multi-language Claude Code 2.0 setup."
    echo "It should be at: .claude/bootstrap-template/"
    exit 1
fi

# Validate target project exists
if [ ! -d "$TARGET_PROJECT" ]; then
    echo "❌ Error: Target project directory not found: $TARGET_PROJECT"
    echo ""
    echo "Usage: ./scripts/bootstrap_project.sh /path/to/target/project"
    echo "   or: ./scripts/bootstrap_project.sh    (current directory)"
    exit 1
fi

cd "$TARGET_PROJECT"
PROJECT_NAME=$(basename "$(pwd)")
echo "📂 Target project: $(pwd)"
echo "📦 Project name: $PROJECT_NAME"
echo ""

# Detect project language
echo "🔍 Detecting project language..."
LANGUAGE="unknown"
SOURCE_DIR="src"

if [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "requirements.txt" ]; then
    LANGUAGE="python"
    SOURCE_DIR="src"
    echo "   Detected: Python (source: src/)"
elif [ -f "package.json" ]; then
    if grep -q '"typescript"' package.json 2>/dev/null; then
        LANGUAGE="typescript"
        echo "   Detected: TypeScript (source: src/)"
    else
        LANGUAGE="javascript"
        echo "   Detected: JavaScript (source: src/)"
    fi
    SOURCE_DIR="src"
elif [ -f "go.mod" ]; then
    LANGUAGE="go"
    SOURCE_DIR="pkg"
    echo "   Detected: Go (source: pkg/)"
elif [ -f "Cargo.toml" ]; then
    LANGUAGE="rust"
    SOURCE_DIR="src"
    echo "   Detected: Rust (source: src/)"
else
    echo "   ⚠️  Unknown language, will use generic setup"
    LANGUAGE="generic"
    SOURCE_DIR="src"
fi
echo ""

# Ask user to confirm
echo "This will copy:"
echo "  • 8 generic agents (planner, researcher, implementer, etc.)"
echo "  • 11 automation hooks (format, test, TDD, coverage, regression, etc.)"
echo "  • 9 domain skills (testing, security, patterns, documentation, etc.)"
echo "  • 2 GitHub workflows (CI safety net, validation)"
echo "  • 3 document templates (PROJECT.md, PATTERNS.md, STATUS.md)"
echo "  • settings.json with hooks configuration"
echo ""
echo "⚠️  This will NOT copy ReAlign-specific MLX/training patterns"
echo ""
read -p "Apply generic Claude Code 2.0 setup to $PROJECT_NAME? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted."
    exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  STEP 1: Creating directory structure"
echo "════════════════════════════════════════════════════════════════"

mkdir -p .claude/agents
mkdir -p .claude/skills
mkdir -p .claude/commands
mkdir -p scripts/hooks
mkdir -p .github/workflows

echo "✓ Directories created"
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  STEP 2: Copying generic agents (8 files)"
echo "════════════════════════════════════════════════════════════════"

# Copy all agents from bootstrap template
for agent in planner researcher implementer test-master reviewer security-auditor doc-master ci-monitor; do
    if [ -f "$BOOTSTRAP_TEMPLATE/agents/$agent.md" ]; then
        cp "$BOOTSTRAP_TEMPLATE/agents/$agent.md" .claude/agents/
        echo "   ✓ $agent.md"
    else
        echo "   ⚠️  $agent.md not found in bootstrap template"
    fi
done

echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  STEP 3: Copying automation hooks (11 files)"
echo "════════════════════════════════════════════════════════════════"

# Copy ALL hooks from bootstrap template
if [ -d "$BOOTSTRAP_TEMPLATE/hooks" ]; then
    cp "$BOOTSTRAP_TEMPLATE/hooks/"*.py scripts/hooks/
    chmod +x scripts/hooks/*.py
    hook_count=$(ls -1 "$BOOTSTRAP_TEMPLATE/hooks/"*.py 2>/dev/null | wc -l | tr -d ' ')
    echo "   ✓ Copied $hook_count hooks (format, test, TDD, coverage, regression, etc.)"
else
    echo "   ⚠️  Hooks directory not found in bootstrap template"
fi

echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  STEP 4: Copying domain skills (9 skills)"
echo "════════════════════════════════════════════════════════════════"

# Copy ALL skills from bootstrap template
if [ -d "$BOOTSTRAP_TEMPLATE/skills" ]; then
    cp -r "$BOOTSTRAP_TEMPLATE/skills/"* .claude/skills/
    skill_count=$(ls -1d "$BOOTSTRAP_TEMPLATE/skills/"*/ 2>/dev/null | wc -l | tr -d ' ')
    echo "   ✓ Copied $skill_count skills (testing, security, patterns, documentation, etc.)"
else
    echo "   ⚠️  Skills directory not found in bootstrap template"
fi

echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  STEP 5: Copying GitHub workflows (2 files)"
echo "════════════════════════════════════════════════════════════════"

# Copy workflows
if [ -d "$BOOTSTRAP_TEMPLATE/.github/workflows" ]; then
    cp "$BOOTSTRAP_TEMPLATE/.github/workflows/"*.yml .github/workflows/
    echo "   ✓ Copied GitHub workflows (CI/CD + validation)"
elif [ -d "$BOOTSTRAP_TEMPLATE/github/workflows" ]; then
    cp "$BOOTSTRAP_TEMPLATE/github/workflows/"*.yml .github/workflows/
    echo "   ✓ Copied GitHub workflows (CI/CD + validation)"
else
    echo "   ⚠️  Workflows not found in bootstrap template"
fi

echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  STEP 6: Creating core documentation files"
echo "════════════════════════════════════════════════════════════════"

# Use templates if available, otherwise create basic versions
if [ -f "$BOOTSTRAP_TEMPLATE/templates/PROJECT.md.template" ]; then
    cp "$BOOTSTRAP_TEMPLATE/templates/PROJECT.md.template" .claude/PROJECT.md
    # Replace placeholders
    sed -i.bak "s/\[PROJECT_NAME\]/$PROJECT_NAME/g" .claude/PROJECT.md
    sed -i.bak "s/\[LANGUAGE\]/$LANGUAGE/g" .claude/PROJECT.md
    sed -i.bak "s/\[SOURCE_DIR\]/$SOURCE_DIR/g" .claude/PROJECT.md
    sed -i.bak "s/\[DATE\]/$(date +%Y-%m-%d)/g" .claude/PROJECT.md
    rm .claude/PROJECT.md.bak 2>/dev/null || true
    echo "   ✓ PROJECT.md (from template)"
else
    # Fallback: create basic PROJECT.md
    cat > .claude/PROJECT.md << EOF
---
project: $PROJECT_NAME
version: 0.1.0
language: $LANGUAGE
status: active
last_updated: $(date +%Y-%m-%d)
---

# $PROJECT_NAME

**Status**: 🚧 In Development
**Language**: $LANGUAGE
**Claude Code 2.0**: ✅ Enabled

---

## VISION

**Purpose**: [Describe what this project does]

**Success Criteria**:
- [ ] [Define measurable success]

---

## REQUIREMENTS

### Functional Requirements
1. [Add requirements]

### Non-Functional Requirements
1. Performance: [Specify]
2. Security: [Specify]
3. Maintainability: [Specify]

---

## ARCHITECTURE

**Source Directory**: $SOURCE_DIR/

**Key Components**:
- [Add components]

**Data Flow**:
1. [Describe flow]

---

## CURRENT FOCUS

**This Week**:
- [ ] [Add tasks]

**Blockers**: None

---

## TRACEABILITY

| Requirement | Implementation | Tests | Status |
|-------------|---------------|-------|--------|
| REQ-001 | - | - | 🚧 |

EOF
    echo "   ✓ PROJECT.md (created)"
fi

# PATTERNS.md
if [ -f "$BOOTSTRAP_TEMPLATE/templates/PATTERNS.md.template" ]; then
    cp "$BOOTSTRAP_TEMPLATE/templates/PATTERNS.md.template" .claude/PATTERNS.md
    echo "   ✓ PATTERNS.md (from template)"
else
    cat > .claude/PATTERNS.md << 'EOF'
# Coding Patterns

**Auto-learned by**: pattern-curator hook
**Project**: Learns from your codebase automatically

---

## Validation States

- ✅ **Validated** - Seen 3+ times, proven pattern
- 🔄 **Candidate** - Seen 1-2 times, under review
- ❌ **Deprecated** - Anti-pattern, avoid

---

## Patterns

<!-- Auto-populated by pattern-curator as you code -->

EOF
    echo "   ✓ PATTERNS.md (created)"
fi

# STATUS.md
if [ -f "$BOOTSTRAP_TEMPLATE/templates/STATUS.md.template" ]; then
    cp "$BOOTSTRAP_TEMPLATE/templates/STATUS.md.template" .claude/STATUS.md
    sed -i.bak "s/\[DATE\]/$(date +%Y-%m-%d)/g" .claude/STATUS.md
    rm .claude/STATUS.md.bak 2>/dev/null || true
    echo "   ✓ STATUS.md (from template)"
else
    cat > .claude/STATUS.md << EOF
# System Health Dashboard

**Last Updated**: $(date +%Y-%m-%d)
**Alignment Score**: 🎯 TBD

---

## Health Checks

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Test Coverage | ≥80% | TBD | 🚧 |
| Documentation | 100% | TBD | 🚧 |
| Security Issues | 0 | TBD | 🚧 |

---

## Recent Activity

- $(date +%Y-%m-%d): Claude Code 2.0 setup initialized

EOF
    echo "   ✓ STATUS.md (created)"
fi

# STANDARDS.md
cat > .claude/STANDARDS.md << EOF
# Engineering Standards

**Project**: $PROJECT_NAME
**Language**: $LANGUAGE

---

## Universal Principles (Claude Code 2.0)

1. **Single Source of Truth** - PROJECT.md is authoritative
2. **Progressive Disclosure** - Load only necessary context
3. **Evidence-Based** - All claims traceable to code/tests
4. **Auto-Enforcement** - Hooks enforce quality automatically
5. **Self-Improving** - System learns patterns from code

---

## Language-Specific Standards

**$LANGUAGE**:
EOF

# Add language-specific standards
case $LANGUAGE in
    python)
        cat >> .claude/STANDARDS.md << 'EOF'
- Code style: black (auto-formatted)
- Imports: isort (auto-sorted)
- Type hints: Required for public APIs
- Docstrings: Google style
- Testing: pytest, ≥80% coverage
- Security: bandit scanning

**Tools**: black, isort, mypy, pytest, bandit
EOF
        ;;
    javascript|typescript)
        cat >> .claude/STANDARDS.md << 'EOF'
- Code style: prettier (auto-formatted)
- Linting: eslint
- Testing: jest, ≥80% coverage
- Security: npm audit

**Tools**: prettier, eslint, jest
EOF
        ;;
    go)
        cat >> .claude/STANDARDS.md << 'EOF'
- Code style: gofmt (auto-formatted)
- Linting: golint
- Testing: go test, ≥80% coverage
- Security: gosec

**Tools**: gofmt, golint, go test, gosec
EOF
        ;;
    *)
        cat >> .claude/STANDARDS.md << 'EOF'
- Follow language conventions
- Testing: ≥80% coverage required
- Security: Regular scans
EOF
        ;;
esac

echo "   ✓ STANDARDS.md (created)"
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  STEP 7: Creating settings.json"
echo "════════════════════════════════════════════════════════════════"

# Determine file extension for hooks
FILE_EXT="*"
case $LANGUAGE in
    python) FILE_EXT="py" ;;
    javascript) FILE_EXT="js" ;;
    typescript) FILE_EXT="ts" ;;
    go) FILE_EXT="go" ;;
    rust) FILE_EXT="rs" ;;
esac

cat > .claude/settings.json << EOF
{
  "\$schema": "https://json.schemastore.org/claude-code-settings.json",
  "version": "2.0.0",
  "standards_version": "1.0.0",

  "permissions": {
    "defaultMode": "default",
    "allow": [
      "Bash(git status)",
      "Bash(git add)",
      "Bash(git commit)",
      "Bash(git push)",
      "Bash(git pull)",
      "Bash(git diff)",
      "Bash(git log)",
      "Bash(python scripts/hooks/auto_format.py)",
      "Bash(python scripts/hooks/auto_test.py)",
      "Bash(python scripts/hooks/security_scan.py)",
      "Bash(python scripts/hooks/validate_standards.py)",
      "Bash(pytest)",
      "Bash(black)",
      "Bash(isort)",
      "Bash(prettier)",
      "Bash(eslint)",
      "Bash(gofmt)",
      "Bash(go test)",
      "Bash(npm test)",
      "Bash(jest)",
      "WebSearch",
      "WebFetch"
    ],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(git push --force)",
      "Bash(git push -f)"
    ],
    "ask": [
      "Bash(rm)",
      "Write(.env)",
      "Write(secrets.json)"
    ]
  },

  "auto_mode": {
    "web_search": true,
    "git_operations": true,
    "run_tests": true,
    "format_code": true,
    "update_docs": true,
    "learn_patterns": true
  },

  "hooks": [
    {
      "event": "PostToolUse",
      "matcher": {
        "tool": "Write",
        "file_pattern": "$SOURCE_DIR/**/*.$FILE_EXT"
      },
      "command": "python scripts/hooks/auto_format.py \\\$CLAUDE_FILE_PATHS",
      "run_in_background": false,
      "description": "Auto-format source files"
    },
    {
      "event": "PostToolUse",
      "matcher": {
        "tool": "Write",
        "file_pattern": "$SOURCE_DIR/**/*.$FILE_EXT"
      },
      "command": "python scripts/hooks/auto_test.py \\\$CLAUDE_FILE_PATHS",
      "run_in_background": false,
      "description": "Run tests for changed files"
    },
    {
      "event": "PostToolUse",
      "matcher": {
        "tool": "Write"
      },
      "command": "python scripts/hooks/security_scan.py \\\$CLAUDE_FILE_PATHS",
      "run_in_background": false,
      "description": "Security scan for secrets and vulnerabilities"
    },
    {
      "event": "PostToolUse",
      "matcher": {
        "tool": "Write",
        "file_pattern": "*.md"
      },
      "command": "python scripts/hooks/auto_align_filesystem.py",
      "run_in_background": false,
      "description": "Auto-align filesystem (keep docs organized)"
    }
  ],

  "project": {
    "name": "$PROJECT_NAME",
    "version": "0.1.0",
    "language": "$LANGUAGE",
    "source_dir": "$SOURCE_DIR"
  },

  "agents": [
    {"name": "planner", "description": "Architecture & design", "auto_invoke": "complex features, architecture"},
    {"name": "researcher", "description": "Web research & best practices", "auto_invoke": "design questions, research"},
    {"name": "test-master", "description": "TDD + progression + regression", "auto_invoke": "test, tdd, coverage"},
    {"name": "implementer", "description": "Code implementation", "auto_invoke": "implementation"},
    {"name": "reviewer", "description": "Code quality gate", "auto_invoke": "review, quality"},
    {"name": "security-auditor", "description": "Security scanning", "auto_invoke": "security, audit"},
    {"name": "doc-master", "description": "Documentation sync", "auto_invoke": "docs, changelog"}
  ],

  "claude_code_2": {
    "enabled": true,
    "core_files": [
      ".claude/PROJECT.md",
      ".claude/PATTERNS.md",
      ".claude/STATUS.md",
      ".claude/STANDARDS.md"
    ],
    "context_budget_tokens": 5300,
    "progressive_disclosure": true,
    "auto_consolidation": true
  }
}
EOF

echo "   ✓ settings.json (configured for $LANGUAGE)"
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  STEP 8: Updating .gitignore"
echo "════════════════════════════════════════════════════════════════"

if [ -f ".gitignore" ]; then
    if ! grep -q "^.claude/" .gitignore 2>/dev/null; then
        cat >> .gitignore << 'EOF'

# Claude Code 2.0 - Track core setup, ignore generated files
.claude/
!.claude/agents/
!.claude/skills/
!.claude/commands/
!.claude/PROJECT.md
!.claude/PATTERNS.md
!.claude/STATUS.md
!.claude/STANDARDS.md
!.claude/settings.json
.claude/logs/
.claude/cache/
.claude/archive/
EOF
        echo "   ✓ Added .claude/ entries to .gitignore"
    else
        echo "   ✓ .gitignore already configured for .claude/"
    fi
else
    echo "   ⚠️  No .gitignore found - you may want to create one"
fi

echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  🎉 Bootstrap Complete! 🎉                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ Generic Claude Code 2.0 setup applied to: $PROJECT_NAME"
echo ""
echo "📦 What was installed:"
echo ""
echo "   Agents (8):"
echo "     • planner - Architecture & design"
echo "     • researcher - Web research & best practices"
echo "     • test-master - TDD, progression, regression"
echo "     • implementer - Code implementation"
echo "     • reviewer - Code quality gate"
echo "     • security-auditor - Security scanning"
echo "     • doc-master - Documentation sync"
echo "     • ci-monitor - CI/CD monitoring"
echo ""
echo "   Hooks (11):"
echo "     • auto_format - Multi-language formatting"
echo "     • auto_test - Test framework detection"
echo "     • auto_generate_tests - TDD test generation"
echo "     • auto_add_to_regression - Regression suite"
echo "     • auto_enforce_coverage - 80% coverage gate"
echo "     • auto_tdd_enforcer - TDD workflow"
echo "     • auto_update_docs - Doc sync"
echo "     • validate_standards - Code standards"
echo "     • security_scan - Secret detection"
echo "     • pattern_curator - Pattern learning"
echo "     • auto_align_filesystem - File organization"
echo ""
echo "   Skills (9):"
echo "     • testing-guide - Complete testing methodology"
echo "     • security-patterns - Security best practices"
echo "     • python-standards - Python quality (PEP 8)"
echo "     • research-patterns - Research methodology"
echo "     • documentation-guide - Doc standards"
echo "     • architecture-patterns - SOLID, DRY, design"
echo "     • engineering-standards - General best practices"
echo "     • mcp-builder - MCP server creation"
echo "     • pattern-curator - Pattern learning automation"
echo ""
echo "   Workflows (2):"
echo "     • safety-net.yml - Agent-first CI/CD"
echo "     • claude-code-validation.yml - Structure validation"
echo ""
echo "   Core Files (4):"
echo "     • PROJECT.md - Single source of truth"
echo "     • PATTERNS.md - Auto-learned patterns"
echo "     • STATUS.md - Health dashboard"
echo "     • STANDARDS.md - Engineering standards"
echo ""
echo "🚀 Next steps:"
echo ""
echo "   1. Edit .claude/PROJECT.md - Define vision & requirements"
echo "   2. Review .claude/STANDARDS.md - Customize for your project"
echo "   3. Commit the setup:"
echo "      git add .claude/ .github/ scripts/"
echo "      git commit -m 'feat: add Claude Code 2.0 autonomous setup'"
echo ""
echo "   4. Start coding! Claude will:"
echo "      • Auto-format your code"
echo "      • Run tests on every change"
echo "      • Scan for security issues"
echo "      • Learn patterns from your code"
echo "      • Keep documentation aligned"
echo ""
echo "📚 Learn more:"
echo "   • Check ReAlign project for production example"
echo "   • Read .claude/agents/ for specialized helpers"
echo "   • Run 'git log' in ReAlign to see it in action"
echo ""
echo "Happy autonomous coding! 🤖✨"

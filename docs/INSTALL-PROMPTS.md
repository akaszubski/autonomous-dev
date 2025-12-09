# Install Prompts for autonomous-dev

**Copy and paste these prompts into Claude Code to install the plugin.**

---

## Prerequisites

Before using these prompts, install Claude Code CLI:

**macOS**:
```bash
brew install --cask claude
```

**Windows**:
```bash
winget install Anthropic.Claude
```

**Linux**: Download from [claude.ai/download](https://claude.ai/download)

**Also required**:
- Python 3.9+ (`python3 --version`)
- gh CLI for GitHub integration: `brew install gh && gh auth login`

---

## New Project (Greenfield)

Use this when starting a fresh project with autonomous-dev from the beginning.

**Copy and paste into Claude Code:**

```
I want to set up autonomous-dev for a new project. Please help me:

1. Install the plugin:
   - Run: /plugin marketplace add akaszubski/autonomous-dev
   - Run: /plugin install autonomous-dev

2. After installation, tell me to restart Claude Code (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)

3. After I restart, set up hooks and scripts:
   - Find the plugin at: ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev
   - Run the setup script: python3 ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/hooks/setup.py
   - This copies hooks, scripts, and templates to my project
   - Walk me through the setup wizard options

4. Help me create PROJECT.md:
   - Create .claude/PROJECT.md with sections for GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE
   - Ask me about my project goals, what's in/out of scope, technical constraints
   - Help me fill in realistic values based on my answers

5. Set up GitHub integration:
   - Verify gh CLI is installed: gh --version
   - If not installed, show me how to install it
   - Help me create initial GitHub issues for my first features

6. Run /health-check to verify everything works

7. Show me how to run my first feature:
   - Create a GitHub issue for a simple feature
   - Run /auto-implement "issue #1"
   - Explain what each agent does as it runs

My project is: [DESCRIBE YOUR PROJECT HERE]
```

---

## Existing Project (Brownfield)

Use this when adding autonomous-dev to an existing codebase.

**Copy and paste into Claude Code:**

```
I want to add autonomous-dev to my existing project. Please help me:

1. Install the plugin:
   - Run: /plugin marketplace add akaszubski/autonomous-dev
   - Run: /plugin install autonomous-dev

2. After installation, tell me to restart Claude Code (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)

3. After I restart, set up hooks and scripts:
   - Find the plugin at: ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev
   - Run the setup script: python3 ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/hooks/setup.py
   - This copies hooks, scripts, and templates to my project
   - Walk me through the setup wizard options

4. Analyze my existing project:
   - Run /align-project-retrofit --dry-run
   - Show me what changes would be made
   - Explain the 5-phase retrofit process

5. Help me create PROJECT.md based on my existing code:
   - Analyze my current directory structure, dependencies, and patterns
   - Infer GOALS from my README or existing documentation
   - Infer SCOPE from what code already exists
   - Identify CONSTRAINTS from my tech stack
   - Document my existing ARCHITECTURE

6. Run the retrofit:
   - Run /align-project-retrofit (step-by-step mode)
   - Confirm each change with me before applying

7. Set up GitHub integration:
   - Verify gh CLI is installed
   - Help me create issues for existing TODOs or planned features

8. Run /health-check to verify everything works

9. Show me the agent pipeline by running a small feature:
   - Pick a simple enhancement from my codebase
   - Create a GitHub issue for it
   - Run /auto-implement "issue #X"
```

---

## Batch Features Setup

Use this after installation to process multiple features.

**Copy and paste into Claude Code:**

```
I have multiple features to implement. Help me set up batch processing:

1. Show me my open GitHub issues:
   - Run: gh issue list

2. Create a batch from issues:
   - Run: /batch-implement --issues [ISSUE_NUMBERS]

   OR create a features file:
   - Create sprint-backlog.txt with one feature per line
   - Run: /batch-implement sprint-backlog.txt

3. Explain the batch workflow:
   - How many features run before context reset (~4-5)
   - How to resume: /batch-implement --resume <batch-id>
   - How issues are auto-closed on completion

4. Start the batch and let me know when to /clear and resume
```

---

## Quick Health Check

Use this anytime to verify installation.

**Copy and paste into Claude Code:**

```
Please verify my autonomous-dev installation:

1. Run /health-check
2. Show me the results
3. If any issues, help me fix them
4. Run /status to show project alignment
5. List available commands with their purpose
```

---

## Update Plugin

Use this to update to the latest version.

**Copy and paste into Claude Code:**

```
Please update autonomous-dev to the latest version:

1. Run /update-plugin
2. Follow prompts for version check, backup, update
3. Tell me to restart Claude Code when done
4. After restart, run /health-check to verify
```

---

## Notes

- **Restart Required**: Claude Code caches commands at startup. After any plugin install/update, you MUST fully quit (Cmd+Q/Ctrl+Q) and reopen.

- **PROJECT.md is Key**: The plugin validates every feature against PROJECT.md. Take time to define your GOALS, SCOPE, and CONSTRAINTS accurately.

- **GitHub-First**: Issues drive development. Create issues first, then `/auto-implement "issue #X"`.

- **Context Limits**: After 4-5 features, run `/clear` then resume. This is by design, not a bug.

# Claude Code: Best Practices for Agentic Coding

> **Source**: https://www.anthropic.com/engineering/claude-code-best-practices
> **Downloaded**: 2025-12-16

## Overview

Claude Code is a command-line tool for agentic coding. This article outlines patterns proven effective across various codebases, languages, and environments.

## 1. Customize Your Setup

### Create CLAUDE.md Files

A special file that Claude automatically incorporates into context. Ideal for documenting:
- Common bash commands
- Core files and utility functions
- Code style guidelines
- Testing instructions
- Repository etiquette
- Developer environment setup
- Project-specific warnings

**Placement options:**
- Root of repo (shared via git or local-only)
- Parent directories (useful for monorepos)
- Child directories (loaded on-demand)
- Home folder (`~/.claude/CLAUDE.md`) for all sessions

**Pro tip:** Use `/init` command for automatic generation.

### Tune CLAUDE.md Files

Treat these as prompts requiring iteration. Experiment to determine what produces best instruction-following. Use the `#` key to add instructions Claude incorporates automatically. Some teams run files through prompt improvers and add emphasis markers like "IMPORTANT" or "YOU MUST."

### Curate Allowed Tools

By default, Claude requests permission for system-modifying actions. Customize via:
- Selecting "Always allow" during sessions
- Using `/permissions` command
- Manual editing of `.claude/settings.json` or `~/.claude.json`
- CLI flag `--allowedTools`

### Install gh CLI

GitHub CLI enables Claude to create issues, open PRs, read comments—without it, Claude can still use GitHub API or MCP servers.

## 2. Give Claude More Tools

### Use Bash Tools

Describe custom tools with usage examples. Direct Claude to run `--help` for documentation. Document frequently-used tools in CLAUDE.md.

### Use MCP (Model Context Protocol)

Claude functions as both MCP server and client. Connect to multiple servers via:
- Project config
- Global config
- Checked-in `.mcp.json` file (shared with team)

Use `--mcp-debug` flag for troubleshooting.

### Use Custom Slash Commands

Store prompt templates in `.claude/commands/` as Markdown files. Include `$ARGUMENTS` keyword for parameterization. Check into git for team availability. Personal commands go in `~/.claude/commands/`.

## 3. Common Workflows

### Explore, Plan, Code, Commit

1. **Explore:** Have Claude read relevant files/images/URLs without writing code
2. **Plan:** Ask Claude to think (extended thinking mode: "think" < "think hard" < "think harder" < "ultrathink"), optionally creating a document/issue
3. **Code:** Request implementation with explicit verification
4. **Commit:** Have Claude commit and create pull request

Steps 1-2 are crucial—prevents premature coding.

### Write Tests, Commit; Code, Iterate, Commit

TDD becomes more powerful with agents:

1. Write tests from input/output pairs (explicit about TDD approach)
2. Run tests and confirm failure
3. Commit tests
4. Write code to pass tests iteratively
5. Commit code

Claude performs best with clear iteration targets.

### Write Code, Screenshot Result, Iterate

1. Provide screenshot capability (Puppeteer MCP, iOS simulator, or manual)
2. Provide visual mock
3. Implement design and iterate until matching mock
4. Commit when satisfied

Multiple iterations typically yield significantly better results.

### Safe YOLO Mode

Use `claude --dangerously-skip-permissions` for uninterrupted work on safe tasks (lint fixes, boilerplate). **Critical:** only in containers without internet access. See Docker Dev Containers reference implementation.

### Codebase Q&A

Ask Claude onboarding questions like:
- How does logging work?
- How do I make a new API endpoint?
- Why are we calling foo() instead of bar()?

No special prompting needed—Claude explores code to find answers. Significantly improves ramp-up time at Anthropic.

### Interact with Git

Claude handles:
- Searching history for context
- Writing commit messages
- Complex operations (reverting, resolving conflicts, grafting patches)

Many Anthropic engineers use Claude for 90%+ of git interactions.

### Interact with GitHub

Claude manages:
- Creating pull requests
- Fixing code review comments
- Repairing failing builds/linter warnings
- Triaging issues

### Work with Jupyter Notebooks

Claude can read and write notebooks, interpreting outputs including images. Recommend opening side-by-side in VS Code. Request "aesthetically pleasing" visualizations.

## 4. Optimize Your Workflow

### Be Specific in Instructions

Success rates improve significantly with detailed directions. Example improvements:

| Poor | Good |
|------|------|
| "add tests for foo.py" | "write new test case for foo.py covering logged-out user edge case, avoid mocks" |
| "why does ExecutionFactory have weird api?" | "look through ExecutionFactory git history, summarize api evolution" |
| "add calendar widget" | "study existing widget patterns on home page, implement calendar with month selection and year pagination" |

### Give Claude Images

Provide through:
- Screenshots (macOS: cmd+ctrl+shift+4 to clipboard, ctrl+v to paste)
- Drag-and-drop
- File paths

Especially useful for design mocks and visual debugging.

### Mention Files You Want to Work On

Use tab-completion to reference repository files and folders quickly.

### Give Claude URLs

Paste specific URLs in prompts. Use `/permissions` to allowlist domains and avoid repeated prompts.

### Course Correct Early and Often

Active collaboration produces better results than full autonomy. Tools:
- **Ask for plans:** require approval before coding
- **Press Escape:** interrupt any phase while preserving context
- **Double-tap Escape:** jump back in history, edit prompts, explore alternatives
- **Ask to undo:** take different approaches

Claude occasionally solves problems perfectly on first attempt, but correction tools generally produce faster, better solutions.

### Use /clear to Keep Context Focused

During long sessions, context fills with irrelevant conversation. Use `/clear` frequently between tasks.

### Use Checklists for Complex Workflows

For large tasks (migrations, lint fixes), have Claude use Markdown file as checklist:
1. Run lint command, write all errors to checklist
2. Address each issue sequentially, checking off as completed

### Pass Data Into Claude

Methods:
- Copy/paste directly (most common)
- Pipe in (`cat foo.txt | claude`)
- Tell Claude to pull via bash/MCP/custom commands
- Have Claude read files or fetch URLs

Most sessions combine approaches.

## 5. Use Headless Mode to Automate Infrastructure

Use `-p` flag with prompt for non-interactive contexts (CI, pre-commit hooks, build scripts). Use `--output-format stream-json` for structured output. Note: doesn't persist between sessions.

### Issue Triage

Automate GitHub events (new issues) to inspect and assign labels.

### Linter

Claude provides subjective code reviews beyond traditional linting: typos, stale comments, misleading names.

## 6. Multi-Claude Workflows

### Have One Claude Write Code; Use Another to Verify

1. Claude writes code
2. Run `/clear` or start second Claude
3. Second Claude reviews first Claude's work
4. Third Claude (or cleared session) reads both code and feedback
5. Claude edits based on feedback

Separation often yields better results than single-agent approach. Can also have Claudes communicate via separate scratchpads.

### Multiple Repository Checkouts

Rather than waiting for each step:
1. Create 3-4 git checkouts in separate folders
2. Open each in separate terminal tabs
3. Start Claude in each with different tasks
4. Cycle through to check progress and approve permissions

### Use Git Worktrees

Lighter-weight alternative for independent tasks:
1. Create: `git worktree add ../project-feature-a feature-a`
2. Launch: `cd ../project-feature-a && claude`
3. Repeat for additional worktrees
4. Clean up: `git worktree remove ../project-feature-a`

Tips: consistent naming, one tab per worktree, set up iTerm2 notifications, separate IDE windows, clean up when finished.

### Headless Mode with Custom Harness

Two patterns:

**Fanning out** (large migrations/analyses):
1. Have Claude generate task list
2. Loop through tasks calling Claude for each with specific tools
3. Run script multiple times, refining prompt

**Pipelining** (integrate with existing workflows):
- `claude -p "<prompt>" --json | your_command`

Use `--verbose` flag for debugging; disable in production.

---

## Key Takeaways

- **Preparation matters:** Investing in CLAUDE.md and clear initial instructions significantly improves results
- **Iteration wins:** Claude excels with visual or test targets to iterate against
- **Separation helps:** Multiple Claude instances can outperform single agent
- **Context management:** Regular use of `/clear` maintains performance in long sessions
- **Flexibility:** No one-size-fits-all workflow—experiment to find what works for your team

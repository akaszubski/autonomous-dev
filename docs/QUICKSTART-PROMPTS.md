# autonomous-dev Quick Start Prompts

Save this file for easy access to all installation and management prompts!

---

## 🚀 First-Time Installation

**Paste this into Claude Code:**

```
Please install the autonomous-dev plugin for me:

1. Run: /plugin marketplace add akaszubski/autonomous-dev
2. Run: /plugin install autonomous-dev
3. Tell me to restart Claude Code (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)
4. After I restart, verify installation by running: /auto-implement

Once complete, tell me what commands are available and how to get started with /auto-implement.
```

---

## 🔄 Update to Latest Version

**Paste this into Claude Code:**

```
Please update the autonomous-dev plugin to the latest version:

1. Run: /update-plugin
2. Follow the prompts to check version, backup, and update
3. Tell me to restart Claude Code when update completes
4. After restart, verify the new version is working

If /update-plugin fails, use manual method:
- Remove old version: rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
- Reinstall: /plugin install autonomous-dev
- Tell me to restart Claude Code
```

---

## 🏗️ Bootstrap New Project

**Paste this into Claude Code:**

```
Please set up autonomous-dev for my project:

1. Run the bootstrap script: bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
2. This creates .claude/PROJECT.md for strategic alignment
3. Show me the PROJECT.md template so I can customize GOALS, SCOPE, and CONSTRAINTS
4. Explain how to use /auto-implement with PROJECT.md validation
```

---

## ✅ Health Check (After Installation)

**Paste this into Claude Code:**

```
Please verify my autonomous-dev installation is working:

1. Run: /health-check
2. Show me the results
3. If any issues found, help me fix them
4. Run a test command: /status
5. Confirm everything is working correctly
```

---

## 📚 Getting Started Guide

**Paste this into Claude Code:**

```
I just installed autonomous-dev. Please help me get started:

1. Explain what /auto-implement does (in 2-3 sentences)
2. Show me the PROJECT.md-first workflow
3. Give me a simple example feature to try
4. Walk me through what happens during the automation
5. Explain context limits and when to use /clear
```

---

## 🎯 Try Your First Feature

**Paste this into Claude Code:**

```
I want to try autonomous-dev with a simple feature:

1. Create a basic PROJECT.md if I don't have one (just GOALS and SCOPE)
2. Run: /auto-implement "Add input validation to the login form"
3. Show me what's happening at each step
4. After completion, explain what was created and why
5. Show me how to verify the feature works
```

---

## 🔍 Troubleshooting

**Paste this into Claude Code:**

```
I'm having issues with autonomous-dev. Please help:

1. Run: /health-check to diagnose the problem
2. Check if commands are available (try /auto-implement autocomplete)
3. Verify plugin is installed: check ~/.claude/plugins/marketplaces/
4. If needed, reinstall: remove and reinstall the plugin
5. Walk me through fixing any issues found
```

---

## 🧹 Context Management (Use After 4-5 Features)

**Paste this into Claude Code:**

```
My context is getting full after several features. Please help:

1. Explain current context usage
2. Run: /clear to reset context
3. Show me how to check if /batch-implement state exists
4. If batch state exists, show me how to resume: /batch-implement --resume <batch-id>
5. Explain when I should clear context vs when to resume
```

---

## 📦 Batch Processing Multiple Features

**Paste this into Claude Code:**

```
I want to process multiple features with /batch-implement:

1. Help me create a features file (show format)
2. Explain typical batch size (4-5 features per session)
3. Run: /batch-implement <my-file>
4. Show progress as features complete
5. If context fills, explain how to resume with --resume flag
```

---

## Why This Works

**Claude Code can execute commands and guide you through interactive steps.**

Instead of memorizing commands or following multi-step docs, just:
1. Copy a prompt from this file
2. Paste into Claude Code
3. Let Claude handle the execution and guidance

**Save this file** to your desktop or bookmark it in your browser for quick access!

---

**Project**: autonomous-dev
**Repository**: https://github.com/akaszubski/autonomous-dev
**Documentation**: https://github.com/akaszubski/autonomous-dev/blob/master/README.md

#!/usr/bin/env python3
"""
Automated setup script for autonomous-dev plugin.

Supports both interactive and non-interactive modes for:
- Hook configuration
- PROJECT.md template installation
- GitHub authentication setup
- Settings validation

Usage:
    Interactive:  python scripts/setup.py
    Automated:    python scripts/setup.py --auto --hooks=slash-commands --github
    Team install: python scripts/setup.py --preset=team
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional


class SetupWizard:
    """Interactive and automated setup for autonomous-dev plugin."""

    def __init__(self, auto: bool = False, preset: Optional[str] = None):
        self.auto = auto
        self.preset = preset
        self.project_root = Path.cwd()
        self.claude_dir = self.project_root / ".claude"
        self.plugin_dir = self.claude_dir / "plugins" / "autonomous-dev"

        # Configuration choices
        self.config = {
            "hooks_mode": None,  # "slash-commands", "automatic", "custom"
            "setup_project_md": None,  # True/False
            "setup_github": None,  # True/False
        }

    def run(self):
        """Run the setup wizard."""
        if not self.auto:
            self.print_welcome()

        # Load preset if specified
        if self.preset:
            self.load_preset(self.preset)
        else:
            # Interactive or manual choices
            self.choose_hooks_mode()
            self.choose_project_md()
            self.choose_github()

        # Execute setup based on choices
        self.setup_hooks()
        self.setup_project_md()
        self.setup_github()
        self.create_gitignore_entries()

        if not self.auto:
            self.print_completion()

    def print_welcome(self):
        """Print welcome message."""
        print("\n" + "━" * 60)
        print("🚀 Autonomous Development Plugin Setup")
        print("━" * 60)
        print("\nThis wizard will configure:")
        print("  ✓ Hooks (automatic quality checks)")
        print("  ✓ Templates (PROJECT.md)")
        print("  ✓ GitHub integration (optional)")
        print("\nThis takes about 2-3 minutes.\n")

    def load_preset(self, preset: str):
        """Load preset configuration."""
        presets = {
            "minimal": {
                "hooks_mode": "slash-commands",
                "setup_project_md": True,
                "setup_github": False,
            },
            "team": {
                "hooks_mode": "automatic",
                "setup_project_md": True,
                "setup_github": True,
            },
            "solo": {
                "hooks_mode": "slash-commands",
                "setup_project_md": True,
                "setup_github": False,
            },
            "power-user": {
                "hooks_mode": "automatic",
                "setup_project_md": True,
                "setup_github": True,
            },
        }

        if preset not in presets:
            print(f"❌ Unknown preset: {preset}")
            print(f"Available presets: {', '.join(presets.keys())}")
            sys.exit(1)

        self.config.update(presets[preset])
        if not self.auto:
            print(f"\n✅ Loaded preset: {preset}")

    def choose_hooks_mode(self):
        """Choose hooks mode (interactive or from args)."""
        if self.auto:
            return  # Already set via args

        print("\n" + "━" * 60)
        print("📋 Choose Your Workflow")
        print("━" * 60)
        print("\nHow would you like to run quality checks?\n")
        print("[1] Slash Commands (Recommended for beginners)")
        print("    - Explicit control: run /format, /test when you want")
        print("    - Great for learning the workflow")
        print("    - No surprises or automatic changes\n")
        print("[2] Automatic Hooks (Power users)")
        print("    - Auto-format on save")
        print("    - Auto-test on commit")
        print("    - Fully automated quality enforcement\n")
        print("[3] Custom (I'll configure manually later)\n")

        while True:
            choice = input("Your choice [1/2/3]: ").strip()
            if choice == "1":
                self.config["hooks_mode"] = "slash-commands"
                break
            elif choice == "2":
                self.config["hooks_mode"] = "automatic"
                break
            elif choice == "3":
                self.config["hooks_mode"] = "custom"
                break
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

    def choose_project_md(self):
        """Choose whether to setup PROJECT.md."""
        if self.auto:
            return

        print("\n" + "━" * 60)
        print("📄 PROJECT.md Template Setup")
        print("━" * 60)
        print("\nPROJECT.md defines your project's strategic direction.")
        print("All agents validate against it before working.\n")

        # Check if PROJECT.md already exists
        project_md = self.claude_dir / "PROJECT.md"
        if project_md.exists():
            print(f"⚠️  PROJECT.md already exists at: {project_md}")
            choice = input("Overwrite with template? [y/N]: ").strip().lower()
            self.config["setup_project_md"] = choice == "y"
        else:
            choice = input("Create PROJECT.md from template? [Y/n]: ").strip().lower()
            self.config["setup_project_md"] = choice != "n"

    def choose_github(self):
        """Choose whether to setup GitHub integration."""
        if self.auto:
            return

        print("\n" + "━" * 60)
        print("🔗 GitHub Integration (Optional)")
        print("━" * 60)
        print("\nGitHub integration enables:")
        print("  ✓ Sprint tracking via Milestones")
        print("  ✓ Issue management")
        print("  ✓ PR automation\n")

        choice = input("Setup GitHub integration? [y/N]: ").strip().lower()
        self.config["setup_github"] = choice == "y"

    def setup_hooks(self):
        """Configure hooks based on chosen mode."""
        if self.config["hooks_mode"] == "custom":
            if not self.auto:
                print("\n✅ Custom mode - No automatic hook configuration")
            return

        if self.config["hooks_mode"] == "slash-commands":
            if not self.auto:
                print("\n✅ Slash Commands Mode Selected")
                print("\nYou can run these commands anytime:")
                print("  /format          Format code")
                print("  /test            Run tests")
                print("  /security-scan   Security check")
                print("  /full-check      All checks")
                print("\n✅ No additional configuration needed.")
            return

        # Automatic hooks mode
        settings_file = self.claude_dir / "settings.local.json"

        hooks_config = {
            "hooks": {
                "PostToolUse": {
                    "Write": ["python .claude/hooks/auto_format.py"],
                    "Edit": ["python .claude/hooks/auto_format.py"],
                },
                "PreCommit": {
                    "*": [
                        "python .claude/hooks/auto_test.py",
                        "python .claude/hooks/security_scan.py",
                    ]
                },
            }
        }

        # Merge with existing settings if present
        if settings_file.exists():
            with open(settings_file) as f:
                existing = json.load(f)
            existing.update(hooks_config)
            hooks_config = existing

        with open(settings_file, "w") as f:
            json.dump(hooks_config, f, indent=2)

        if not self.auto:
            print("\n⚙️  Configuring Automatic Hooks...")
            print(f"\n✅ Created: {settings_file}")
            print("\nWhat will happen automatically:")
            print("  ✓ Code formatted after every write/edit")
            print("  ✓ Tests run before every commit")
            print("  ✓ Security scan before every commit")

    def setup_project_md(self):
        """Setup PROJECT.md from template."""
        if not self.config["setup_project_md"]:
            return

        template_path = self.claude_dir / "templates" / "PROJECT.md"
        target_path = self.claude_dir / "PROJECT.md"

        if not template_path.exists():
            print(f"\n⚠️  Template not found: {template_path}")
            print("    Run /plugin install autonomous-dev first")
            return

        shutil.copy(template_path, target_path)

        if not self.auto:
            print(f"\n✅ Created: {target_path}")
            print("\nNext steps:")
            print("  1. Open .claude/PROJECT.md in your editor")
            print("  2. Fill in GOALS, SCOPE, CONSTRAINTS")
            print("  3. Save and run: /align-project")

    def setup_github(self):
        """Setup GitHub integration."""
        if not self.config["setup_github"]:
            return

        env_file = self.project_root / ".env"

        # Create .env if it doesn't exist
        if not env_file.exists():
            env_content = """# GitHub Personal Access Token
# Get yours at: https://github.com/settings/tokens
# Required scopes: repo, workflow
GITHUB_TOKEN=ghp_your_token_here
"""
            env_file.write_text(env_content)

            if not self.auto:
                print(f"\n✅ Created: {env_file}")
                print("\n📝 Next Steps:")
                print("  1. Go to: https://github.com/settings/tokens")
                print("  2. Generate new token (classic)")
                print("  3. Select scopes: repo, workflow")
                print("  4. Copy token and add to .env")
                print("\nSee: .claude/docs/GITHUB_AUTH_SETUP.md for details")
        else:
            if not self.auto:
                print(f"\nℹ️  .env already exists: {env_file}")
                print("    Add GITHUB_TOKEN if not already present")

    def create_gitignore_entries(self):
        """Ensure .env and other files are gitignored."""
        gitignore = self.project_root / ".gitignore"

        entries_to_add = [
            ".env",
            ".env.local",
            ".claude/settings.local.json",
        ]

        if gitignore.exists():
            existing = gitignore.read_text()
        else:
            existing = ""

        new_entries = []
        for entry in entries_to_add:
            if entry not in existing:
                new_entries.append(entry)

        if new_entries:
            with open(gitignore, "a") as f:
                if not existing.endswith("\n"):
                    f.write("\n")
                f.write("\n# Autonomous-dev plugin (gitignored)\n")
                for entry in new_entries:
                    f.write(f"{entry}\n")

            if not self.auto:
                print(f"\n✅ Updated: {gitignore}")
                print(f"   Added: {', '.join(new_entries)}")

    def print_completion(self):
        """Print completion message."""
        print("\n" + "━" * 60)
        print("✅ Setup Complete!")
        print("━" * 60)
        print("\nYour autonomous development environment is ready!")
        print("\nQuick Start:")

        if self.config["hooks_mode"] == "slash-commands":
            print("  1. Describe feature")
            print("  2. Run: /auto-implement")
            print("  3. Before commit: /full-check")
            print("  4. Commit: /commit")
        elif self.config["hooks_mode"] == "automatic":
            print("  1. Describe feature")
            print("  2. Run: /auto-implement")
            print("  3. Commit: git commit (hooks run automatically)")

        print("\nUseful Commands:")
        print("  /align-project   Validate alignment")
        print("  /auto-implement  Autonomous development")
        print("  /full-check      Run all quality checks")
        print("  /help            Get help")

        print("\nHappy coding! 🚀\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Setup autonomous-dev plugin",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode:
    python scripts/setup.py

  Automated with slash commands:
    python scripts/setup.py --auto --hooks=slash-commands --project-md

  Automated with automatic hooks:
    python scripts/setup.py --auto --hooks=automatic --project-md --github

  Using presets:
    python scripts/setup.py --preset=minimal     # Slash commands only
    python scripts/setup.py --preset=team        # Full team setup
    python scripts/setup.py --preset=solo        # Solo developer
    python scripts/setup.py --preset=power-user  # Everything enabled

Presets:
  minimal:     Slash commands + PROJECT.md
  solo:        Same as minimal
  team:        Automatic hooks + PROJECT.md + GitHub
  power-user:  Everything enabled
        """,
    )

    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run in non-interactive mode (requires other flags)",
    )

    parser.add_argument(
        "--preset",
        choices=["minimal", "team", "solo", "power-user"],
        help="Use preset configuration",
    )

    parser.add_argument(
        "--hooks",
        choices=["slash-commands", "automatic", "custom"],
        help="Hooks mode (requires --auto)",
    )

    parser.add_argument(
        "--project-md",
        action="store_true",
        help="Setup PROJECT.md from template (requires --auto)",
    )

    parser.add_argument(
        "--github",
        action="store_true",
        help="Setup GitHub integration (requires --auto)",
    )

    args = parser.parse_args()

    # Validation
    if args.auto and not args.preset:
        if not args.hooks:
            parser.error("--auto requires --hooks or --preset")

    wizard = SetupWizard(auto=args.auto, preset=args.preset)

    # Apply command-line arguments
    if args.hooks:
        wizard.config["hooks_mode"] = args.hooks
    if args.project_md or args.auto:
        wizard.config["setup_project_md"] = args.project_md
    if args.github or args.auto:
        wizard.config["setup_github"] = args.github

    try:
        wizard.run()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

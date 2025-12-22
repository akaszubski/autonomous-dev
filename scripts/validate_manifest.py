#!/usr/bin/env python3
"""Quick validation script to check manifest completeness."""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = PROJECT_ROOT / "plugins/autonomous-dev/config/install_manifest.json"
HOOKS_DIR = PROJECT_ROOT / "plugins/autonomous-dev/hooks"
GLOBAL_SETTINGS = PROJECT_ROOT / "plugins/autonomous-dev/config/global_settings_template.json"

def main():
    # Load manifest
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    # Load global settings
    with open(GLOBAL_SETTINGS) as f:
        settings = json.load(f)

    errors = []

    # Get hooks from manifest
    manifest_hooks = {Path(p).name for p in manifest["components"]["hooks"]["files"]}

    # Check critical hooks
    critical = ["unified_pre_tool.py", "unified_prompt_validator.py", "pre_tool_use.py"]
    missing_critical = [h for h in critical if h not in manifest_hooks]
    if missing_critical:
        errors.append(f"Critical hooks missing from manifest: {missing_critical}")
    else:
        print("✅ All critical hooks in manifest")

    # Check hooks in settings exist
    for lifecycle, hooks in settings.get("hooks", {}).items():
        for entry in hooks:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                match = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*\.py)", cmd)
                if match:
                    hook_name = match.group(1)
                    if hook_name not in manifest_hooks:
                        errors.append(f"{hook_name} referenced in settings but not in manifest")
                    else:
                        print(f"✅ {hook_name} in manifest")

    # Check core commands
    core_cmds = ["sync.md", "setup.md", "health-check.md"]
    manifest_cmds = {Path(p).name for p in manifest["components"]["commands"]["files"]}
    missing_cmds = [c for c in core_cmds if c not in manifest_cmds]
    if missing_cmds:
        errors.append(f"Core commands missing: {missing_cmds}")
    else:
        print("✅ All core commands in manifest")

    # Check install.sh has global commands function
    install_sh = PROJECT_ROOT / "install.sh"
    if "install_global_commands" not in install_sh.read_text():
        errors.append("install.sh missing install_global_commands function")
    else:
        print("✅ install.sh has install_global_commands")

    if errors:
        print("\n❌ VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print("\n✅ All validations passed!")
        return 0

if __name__ == "__main__":
    exit(main())

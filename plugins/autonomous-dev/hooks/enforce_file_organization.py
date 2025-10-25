#!/usr/bin/env python3
"""
File Organization Enforcer - Keeps project structure clean

This script enforces the standard project structure defined in
templates/project-structure.json.

What it checks:
- Source code in src/
- Tests organized in tests/unit/, tests/integration/, tests/uat/
- Documentation in docs/
- Scripts in scripts/
- Root directory kept clean (no loose files)

Can run in two modes:
1. Validation mode (default): Reports violations
2. Fix mode (--fix): Automatically fixes violations

Usage:
    # Check for violations
    python hooks/enforce_file_organization.py

    # Auto-fix violations
    python hooks/enforce_file_organization.py --fix

Exit codes:
- 0: Structure correct or successfully fixed
- 1: Violations found (validation mode)
"""

import sys
import json
import shutil
from pathlib import Path
from typing import List, Tuple, Dict


def load_structure_template() -> Dict:
    """Load standard project structure template."""
    template_path = Path(__file__).parent.parent / "templates" / "project-structure.json"
    
    if not template_path.exists():
        return get_default_structure()
    
    return json.loads(template_path.read_text())


def get_default_structure() -> Dict:
    """Get default structure if template not found."""
    return {
        "structure": {
            "src/": {"required": True},
            "tests/": {"required": True},
            "docs/": {"required": True},
            "scripts/": {"required": False},
            ".claude/": {"required": True}
        }
    }


def get_project_root() -> Path:
    """Find project root directory."""
    current = Path.cwd()
    
    while current != current.parent:
        if (current / ".git").exists() or (current / "PROJECT.md").exists():
            return current
        current = current.parent
    
    return Path.cwd()


def check_required_directories(project_root: Path, structure: Dict) -> List[str]:
    """Check for missing required directories."""
    missing = []
    
    for dir_name, config in structure.get("structure", {}).items():
        if not dir_name.endswith("/"):
            continue
        
        if config.get("required", False):
            dir_path = project_root / dir_name.rstrip("/")
            if not dir_path.exists():
                missing.append(dir_name)
    
    return missing


def find_misplaced_files(project_root: Path) -> List[Tuple[Path, str]]:
    """
    Find files in root that should be in subdirectories.
    
    Returns:
        List of (file_path, suggested_location) tuples
    """
    misplaced = []
    
    # Files that should be in src/
    for pattern in ["*.py", "*.js", "*.ts", "*.go", "*.rs", "*.java"]:
        for file in project_root.glob(pattern):
            # Skip allowed files
            if file.name in ["setup.py", "conftest.py"]:
                continue
            
            # Skip if already in proper directory
            relative = file.relative_to(project_root)
            if str(relative).startswith(("src/", "tests/", "scripts/", "docs/")):
                continue
            
            misplaced.append((file, "src/"))
    
    # Files that should be in tests/
    for pattern in ["test_*.py", "*_test.py", "test*.js", "*test.ts"]:
        for file in project_root.glob(pattern):
            relative = file.relative_to(project_root)
            if not str(relative).startswith("tests/"):
                misplaced.append((file, "tests/unit/"))
    
    # Files that should be in docs/
    for pattern in ["*.md"]:
        for file in project_root.glob(pattern):
            # Skip allowed files
            if file.name in ["README.md", "LICENSE.md", "CHANGELOG.md"]:
                continue
            
            relative = file.relative_to(project_root)
            if not str(relative).startswith("docs/"):
                misplaced.append((file, "docs/"))
    
    # Temporary/scratch files that should be deleted
    temp_patterns = ["temp*.py", "scratch*.py", "test.py", "debug.py"]
    for pattern in temp_patterns:
        for file in project_root.glob(pattern):
            misplaced.append((file, "DELETE"))
    
    return misplaced


def create_directory_structure(project_root: Path, structure: Dict) -> None:
    """Create required directories if they don't exist."""
    for dir_name, config in structure.get("structure", {}).items():
        if not dir_name.endswith("/"):
            continue
        
        if config.get("required", False):
            dir_path = project_root / dir_name.rstrip("/")
            dir_path.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories if specified
            subdirs = config.get("subdirectories", {})
            for subdir_name in subdirs.keys():
                subdir_path = dir_path / subdir_name.rstrip("/")
                subdir_path.mkdir(parents=True, exist_ok=True)


def fix_file_organization(project_root: Path, misplaced: List[Tuple[Path, str]]) -> None:
    """Move misplaced files to correct locations."""
    for file_path, target_dir in misplaced:
        if target_dir == "DELETE":
            print(f"  🗑️  Deleting: {file_path.name}")
            file_path.unlink()
            continue
        
        target_path = project_root / target_dir / file_path.name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"  📁 Moving: {file_path.name} → {target_dir}")
        shutil.move(str(file_path), str(target_path))


def validate_structure(project_root: Path, fix: bool = False) -> Tuple[bool, str]:
    """
    Validate project structure against standard template.
    
    Args:
        project_root: Project root directory
        fix: If True, automatically fix violations
    
    Returns:
        (is_valid, message)
    """
    structure = load_structure_template()
    
    # Check required directories
    missing_dirs = check_required_directories(project_root, structure)
    
    # Check for misplaced files
    misplaced_files = find_misplaced_files(project_root)
    
    if not missing_dirs and not misplaced_files:
        return True, "✅ Project structure follows standard organization"
    
    # Report violations
    message = "❌ Project structure violations found:\n\n"
    
    if missing_dirs:
        message += "Missing required directories:\n"
        for dir_name in missing_dirs:
            message += f"  - {dir_name}\n"
        message += "\n"
    
    if misplaced_files:
        message += "Misplaced files:\n"
        for file_path, target in misplaced_files:
            if target == "DELETE":
                message += f"  - {file_path.name} (should be deleted - temp file)\n"
            else:
                message += f"  - {file_path.name} (should be in {target})\n"
        message += "\n"
    
    # Fix if requested
    if fix:
        message += "Fixing violations...\n\n"
        
        if missing_dirs:
            create_directory_structure(project_root, structure)
            message += "✅ Created missing directories\n"
        
        if misplaced_files:
            fix_file_organization(project_root, misplaced_files)
            message += f"✅ Moved {len(misplaced_files)} files to correct locations\n"
        
        message += "\n✅ Project structure now follows standard organization"
        return True, message
    else:
        message += "Run with --fix to automatically fix these issues:\n"
        message += "  python hooks/enforce_file_organization.py --fix"
        return False, message


def main() -> int:
    """Main entry point."""
    fix_mode = "--fix" in sys.argv
    
    print("🔍 Validating project structure...\n")
    
    project_root = get_project_root()
    is_valid, message = validate_structure(project_root, fix=fix_mode)
    
    print(message)
    print()
    
    if is_valid:
        print("✅ Structure validation PASSED")
        return 0
    else:
        print("❌ Structure validation FAILED")
        print("\nStandard structure:")
        print("  src/        - Source code")
        print("  tests/      - Tests (unit/, integration/, uat/)")
        print("  docs/       - Documentation")
        print("  scripts/    - Utility scripts")
        print("  .claude/    - Claude Code configuration")
        return 1


if __name__ == "__main__":
    sys.exit(main())

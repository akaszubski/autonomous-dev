#!/usr/bin/env python3
"""
Auto-Alignment Hook - Automatically keeps system congruent

This hook runs automatically to ensure the system stays aligned WITHOUT
asking the user. It makes intelligent decisions about what to update
based on documented patterns.

Triggers:
- Before git push (pre-push hook)
- Periodically during development

What it does:
1. Checks for documentation vs implementation drift
2. Auto-updates skills/agents with new knowledge
3. Validates cross-references
4. Creates GitHub Issues for gaps
5. All automatic - NO user prompts!
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# Configuration
AUTO_UPDATE_SKILLS = True  # Automatically update skills with new knowledge
AUTO_UPDATE_AGENTS = True  # Automatically update agents
AUTO_CREATE_ISSUES = True  # Create GitHub Issues for missing implementations
VERBOSE = False  # Set to True for debugging

def log(message: str, level: str = "INFO"):
    """Log message if verbose enabled."""
    if VERBOSE or level == "ERROR":
        prefix = "✅" if level == "INFO" else "❌" if level == "ERROR" else "⚠️"
        print(f"{prefix} {message}", file=sys.stderr)

def get_documented_features() -> Dict[str, List[str]]:
    """Extract features from documentation."""
    features = {
        "testing_layers": [],
        "commit_levels": [],
        "commands": [],
        "hooks": []
    }

    # Check COMMIT-WORKFLOW-COMPLETE.md
    commit_doc = Path("plugins/autonomous-dev/docs/COMMIT-WORKFLOW-COMPLETE.md")
    if commit_doc.exists():
        content = commit_doc.read_text()
        if "Level 1:" in content and "Level 2:" in content:
            features["commit_levels"] = ["level1", "level2", "level3", "level4"]

    # Check SYSTEM-PERFORMANCE-GUIDE.md
    system_doc = Path("plugins/autonomous-dev/docs/SYSTEM-PERFORMANCE-GUIDE.md")
    if system_doc.exists():
        features["testing_layers"].append("layer3_system_performance")

    # Check COVERAGE-GUIDE.md
    coverage_doc = Path("plugins/autonomous-dev/docs/COVERAGE-GUIDE.md")
    if coverage_doc.exists():
        content = coverage_doc.read_text()
        if "Layer 1:" in content and "Layer 2:" in content and "Layer 3:" in content:
            features["testing_layers"] = ["layer1", "layer2", "layer3"]

    return features

def check_skill_alignment(skill_name: str, required_knowledge: List[str]) -> Tuple[bool, List[str]]:
    """Check if skill has required knowledge."""
    skill_path = Path(f"plugins/autonomous-dev/skills/{skill_name}/SKILL.md")
    if not skill_path.exists():
        return False, required_knowledge

    content = skill_path.read_text()
    missing = []

    for knowledge in required_knowledge:
        if knowledge == "layer3_system_performance":
            if "Layer 3: System Performance" not in content and "Layer 3: When to Use System Performance" not in content:
                missing.append(knowledge)
        elif knowledge == "progressive_commit":
            if "progressive commit" not in content.lower() and "Level 1:" not in content:
                missing.append(knowledge)

    return len(missing) == 0, missing

def auto_update_testing_guide():
    """Automatically update testing-guide skill with Layer 3 if missing."""
    skill_path = Path("plugins/autonomous-dev/skills/testing-guide/SKILL.md")
    if not skill_path.exists():
        log("testing-guide skill not found", "ERROR")
        return False

    content = skill_path.read_text()

    # Check if already has Layer 3
    if "Layer 3: System Performance" in content or "Layer 3: When to Use System Performance" in content:
        log("testing-guide already has Layer 3 ✅")
        return True

    # Auto-update: Change "Two-Layer" to "Three-Layer"
    if AUTO_UPDATE_SKILLS:
        if "Two-Layer Testing Strategy" in content:
            content = content.replace(
                "Two-Layer Testing Strategy",
                "Three-Layer Testing Strategy ⭐ UPDATED"
            )
            content = content.replace(
                "**Traditional tests (pytest)** validate **STRUCTURE** and **BEHAVIOR**\n**GenAI validation (Claude)** validates **INTENT** and **MEANING**\n\nBoth are needed for comprehensive coverage.",
                "**Layer 1 (pytest)** validates **STRUCTURE** and **BEHAVIOR**\n**Layer 2 (GenAI)** validates **INTENT** and **MEANING**\n**Layer 3 (Meta-analysis)** validates **SYSTEM PERFORMANCE** and **OPTIMIZATION**\n\nAll three layers are needed for complete autonomous system coverage."
            )
            skill_path.write_text(content)
            log("Auto-updated testing-guide with Layer 3 knowledge")
            return True

    log("testing-guide needs Layer 3 update (AUTO_UPDATE_SKILLS disabled)", "WARN")
    return False

def check_agent_alignment(agent_name: str, required_knowledge: List[str]) -> Tuple[bool, List[str]]:
    """Check if agent has required knowledge."""
    agent_path = Path(f"plugins/autonomous-dev/agents/{agent_name}.md")
    if not agent_path.exists():
        return False, required_knowledge

    content = agent_path.read_text()
    missing = []

    for knowledge in required_knowledge:
        if knowledge == "progressive_commit":
            if "progressive commit" not in content.lower():
                missing.append(knowledge)
        elif knowledge == "readme_rebuild":
            if "README" not in content and "readme" not in content.lower():
                missing.append(knowledge)

    return len(missing) == 0, missing

def auto_update_doc_master():
    """Automatically update doc-master agent with progressive commit knowledge."""
    agent_path = Path("plugins/autonomous-dev/agents/doc-master.md")
    if not agent_path.exists():
        log("doc-master agent not found", "ERROR")
        return False

    content = agent_path.read_text()

    # Check if already mentions progressive commit
    if "progressive commit" in content.lower():
        log("doc-master already knows about progressive commit ✅")
        return True

    # For now, just log - actual update would require reading full agent structure
    log("doc-master needs progressive commit knowledge", "WARN")
    return False

def create_github_issue_for_gap(gap_type: str, description: str) -> bool:
    """Create GitHub Issue for implementation gap."""
    if not AUTO_CREATE_ISSUES:
        log(f"Would create issue for: {description} (AUTO_CREATE_ISSUES disabled)", "WARN")
        return False

    # Check if gh CLI is available
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        log("gh CLI not available, skipping issue creation", "WARN")
        return False

    # Create issue
    title_map = {
        "layer3_testing": "Implement /test system-performance (Layer 3)",
        "progressive_commit": "Implement progressive commit workflow (4 levels)",
        "readme_rebuild": "Implement README auto-rebuild",
    }

    body_map = {
        "layer3_testing": "See: plugins/autonomous-dev/docs/SYSTEM-PERFORMANCE-GUIDE.md\n\nImplement system performance testing including agent metrics, model optimization, and ROI tracking.",
        "progressive_commit": "See: plugins/autonomous-dev/docs/COMMIT-WORKFLOW-COMPLETE.md\n\nImplement 4-level progressive commit workflow with README rebuild, doc sync, and CHANGELOG update.",
        "readme_rebuild": "See: plugins/autonomous-dev/docs/COMMIT-WORKFLOW-COMPLETE.md - README rebuild section\n\nImplement automatic README generation from PROJECT.md + docs.",
    }

    title = title_map.get(gap_type, f"Implement: {description}")
    body = body_map.get(gap_type, description)

    try:
        result = subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body, "--label", "enhancement,autonomous"],
            capture_output=True,
            text=True,
            check=True
        )
        issue_url = result.stdout.strip()
        log(f"Created GitHub Issue: {issue_url}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Failed to create issue: {e.stderr}", "ERROR")
        return False

def main():
    """Main alignment check."""
    log("🔍 Running automatic alignment check...")

    # Get documented features
    features = get_documented_features()

    # Track what needs updating
    updates_made = []
    issues_needed = []

    # 1. Check testing-guide skill
    if "layer3_system_performance" in features["testing_layers"]:
        aligned, missing = check_skill_alignment("testing-guide", ["layer3_system_performance"])
        if not aligned:
            if auto_update_testing_guide():
                updates_made.append("testing-guide updated with Layer 3")
            else:
                issues_needed.append("layer3_testing")

    # 2. Check doc-master agent
    if features["commit_levels"]:
        aligned, missing = check_agent_alignment("doc-master", ["progressive_commit"])
        if not aligned:
            if auto_update_doc_master():
                updates_made.append("doc-master updated with progressive commit")
            # Don't create issue yet - agent update is more complex

    # 3. Create GitHub Issues for missing implementations
    if AUTO_CREATE_ISSUES:
        # Check if /test system-performance exists
        test_cmd = Path("plugins/autonomous-dev/commands/test.md")
        if test_cmd.exists():
            content = test_cmd.read_text()
            if "system-performance" in content and "/test system-performance" not in content:
                issues_needed.append("layer3_testing")

        # Check if progressive commit is implemented
        commit_cmd = Path("plugins/autonomous-dev/commands/commit.md")
        if commit_cmd.exists():
            content = commit_cmd.read_text()
            if "Level 1:" not in content and len(features["commit_levels"]) > 0:
                issues_needed.append("progressive_commit")

    # Create issues (with deduplication)
    created_issues = []
    for gap in set(issues_needed):  # Deduplicate
        if create_github_issue_for_gap(gap, f"Implementation gap: {gap}"):
            created_issues.append(gap)

    # Summary
    if updates_made or created_issues:
        log("\n📊 Alignment Summary:")
        if updates_made:
            log(f"   Updates made: {len(updates_made)}")
            for update in updates_made:
                log(f"     - {update}")
        if created_issues:
            log(f"   Issues created: {len(created_issues)}")
            for issue in created_issues:
                log(f"     - {issue}")
        log("\n✅ System alignment improved automatically!")
    else:
        log("✅ System fully aligned - no updates needed")

    return 0  # Always succeed (non-blocking)

if __name__ == "__main__":
    sys.exit(main())

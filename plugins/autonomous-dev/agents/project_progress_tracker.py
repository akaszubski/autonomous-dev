#!/usr/bin/env python3
"""
Python wrapper for project-progress-tracker agent.

This module provides a Python interface to the project-progress-tracker agent
for testing and programmatic access.

Issue: #46 Phase 9 (Model Downgrade)
Date: 2025-11-13
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional, List


class ProjectProgressTracker:
    """
    Wrapper class for project-progress-tracker agent.

    Provides programmatic access to agent metadata and configuration.
    """

    def __init__(self, model: Optional[str] = None, project_md: Optional[Path] = None):
        """
        Initialize project-progress-tracker agent.

        Args:
            model: Override model (defaults to value in agent.md frontmatter)
            project_md: Path to PROJECT.md file
        """
        self.agent_file = Path(__file__).parent / "project-progress-tracker.md"
        self.metadata = self._parse_frontmatter()
        self.project_md = project_md

        # Override model if provided
        if model:
            self.metadata["model"] = model

        # Load project goals if project_md provided
        self.project_content = ""
        if project_md and project_md.exists():
            self.project_content = project_md.read_text()

    def _parse_frontmatter(self) -> Dict[str, Any]:
        """
        Parse YAML frontmatter from agent.md file.

        Returns:
            Dict with frontmatter fields (name, model, tools, etc.)
        """
        if not self.agent_file.exists():
            raise FileNotFoundError(f"Agent file not found: {self.agent_file}")

        content = self.agent_file.read_text()

        # Extract frontmatter (between --- markers)
        frontmatter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            raise ValueError(f"No frontmatter found in {self.agent_file}")

        frontmatter_text = frontmatter_match.group(1)

        # Parse simple YAML (key: value format)
        metadata = {}
        for line in frontmatter_text.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Remove quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            # Parse lists
            if value.startswith('[') and value.endswith(']'):
                value = [v.strip() for v in value[1:-1].split(',')]

            metadata[key] = value

        return metadata

    @property
    def model(self) -> str:
        """Get agent model (sonnet or haiku)."""
        return self.metadata.get("model", "sonnet")

    @property
    def name(self) -> str:
        """Get agent name."""
        return self.metadata.get("name", "project-progress-tracker")

    def update(self, phase: str, completed: List[str]) -> None:
        """
        Update PROJECT.md with completed features for a phase.

        Args:
            phase: Phase name (e.g., "Phase 2: Implement authentication")
            completed: List of completed feature names

        Note: This is a mock implementation for testing.
        Real updates happen through Claude Code agent invocation and file writing.
        """
        if not self.project_md or not self.project_md.exists():
            return

        content = self.project_md.read_text()

        # Find the phase section
        lines = content.split('\n')
        updated_lines = []
        in_phase = False
        phase_features = []  # Track all features for this phase

        # First pass: identify all features in the phase
        for i, line in enumerate(lines):
            if phase in line:
                in_phase = True
                # Look ahead to collect all feature items
                for future_line in lines[i+1:]:
                    stripped = future_line.strip()
                    # Check if this is a phase line (different from feature sub-items)
                    if stripped.startswith('- [ ] Phase') or stripped.startswith('- [x] Phase'):
                        # Next phase started - stop counting
                        break
                    # Check if this is a feature sub-item (indented under phase)
                    elif stripped.startswith('- [ ]') or stripped.startswith('- [x]'):
                        # Only count if it's indented (not a top-level phase)
                        if future_line.startswith('  ') or future_line.startswith('\t'):
                            feature_name = stripped[6:]  # Remove '- [ ] ' or '- [x] '
                            phase_features.append(feature_name.strip())
                    elif stripped.startswith('##'):
                        # New section started
                        break
                break

        total_features = len(phase_features)
        completed_count = len(completed)

        # Second pass: update lines
        in_phase = False
        all_features_complete = (completed_count == total_features and total_features > 0)

        for line in lines:
            if phase in line:
                in_phase = True
                # Update the phase line with count
                if '(' in line and '/' in line and 'features)' in line:
                    # Replace existing count
                    line = line.split('(')[0] + f"({completed_count}/{total_features} features)"
                elif total_features > 0:
                    # Add count if not present
                    line = line.rstrip() + f" ({completed_count}/{total_features} features)"

                # Mark phase complete if all features done
                if all_features_complete and line.strip().startswith('- [ ]'):
                    line = line.replace('- [ ]', '- [x]', 1)

            # Update feature checkboxes
            elif in_phase and (line.strip().startswith('- [ ]') or line.strip().startswith('- [x]')):
                feature_name = line.strip()[6:]  # Remove '- [ ] ' or '- [x] '
                if any(comp.lower() in feature_name.lower() for comp in completed):
                    line = line.replace('- [ ]', '- [x]')

            # End of phase section
            elif in_phase and (line.startswith('- [ ] Phase') or line.startswith('- [x] Phase') or line.strip().startswith('##')):
                in_phase = False

            updated_lines.append(line)

        # Update overall metrics if phase complete
        if all_features_complete:
            updated_lines = self._update_overall_metrics(updated_lines)

        # Write back to file
        self.project_md.write_text('\n'.join(updated_lines))

    def _update_overall_metrics(self, lines: List[str]) -> List[str]:
        """
        Update overall completion metrics when a phase completes.

        Args:
            lines: Current PROJECT.md lines

        Returns:
            Updated lines with incremented phase count
        """
        updated_lines = []
        for line in lines:
            # Update "Completion: X/Y phases" line
            if 'completion:' in line.lower() and '/4 phases' in line.lower():
                # Extract current count
                import re
                match = re.search(r'(\d+)/4 phases', line, re.IGNORECASE)
                if match:
                    current_count = int(match.group(1))
                    new_count = current_count + 1
                    line = re.sub(r'\d+/4 phases', f'{new_count}/4 phases', line, flags=re.IGNORECASE)

            updated_lines.append(line)

        return updated_lines

    def update_goals(self, completed_feature: str, current_goals: List[str]) -> Dict[str, Any]:
        """
        Update project goals after completing a feature.

        Args:
            completed_feature: Description of completed feature
            current_goals: List of current project goals

        Returns:
            Dict with updated goals and progress

        Note: This is a mock implementation for testing.
        Real updates happen through Claude Code agent invocation.
        """
        # Mock goal update for testing
        # Real implementation would invoke the agent through Claude Code

        updated_goals = []
        for goal in current_goals:
            # Mark goals as completed if feature relates to them
            if any(keyword in completed_feature.lower() for keyword in goal.lower().split()):
                updated_goals.append({
                    "goal": goal,
                    "status": "COMPLETED",
                    "completed_by": completed_feature
                })
            else:
                updated_goals.append({
                    "goal": goal,
                    "status": "IN_PROGRESS",
                    "completed_by": None
                })

        return {
            "updated_goals": updated_goals,
            "completed_count": sum(1 for g in updated_goals if g["status"] == "COMPLETED"),
            "total_count": len(updated_goals),
            "completion_percentage": (sum(1 for g in updated_goals if g["status"] == "COMPLETED") / len(updated_goals) * 100) if updated_goals else 0
        }

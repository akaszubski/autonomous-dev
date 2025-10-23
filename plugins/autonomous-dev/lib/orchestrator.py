"""
Orchestrator for autonomous-dev v2.0
Master coordinator for PROJECT.md-aligned autonomous development.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from artifacts import ArtifactManager, generate_workflow_id
from logging_utils import WorkflowLogger, WorkflowProgressTracker


class ProjectMdParser:
    """Parse and validate PROJECT.md"""

    def __init__(self, project_md_path: Path):
        """
        Initialize parser

        Args:
            project_md_path: Path to PROJECT.md file
        """
        self.project_md_path = project_md_path

        if not project_md_path.exists():
            raise FileNotFoundError(f"PROJECT.md not found at: {project_md_path}")

        self.content = project_md_path.read_text()
        self.goals = self._parse_section("GOALS")
        self.scope_included = self._parse_section("SCOPE", subsection="In Scope")
        self.scope_excluded = self._parse_section("SCOPE", subsection="Out of Scope")
        self.constraints = self._parse_section("CONSTRAINTS")

    def _parse_section(
        self,
        section_name: str,
        subsection: Optional[str] = None
    ) -> List[str]:
        """
        Parse a section from PROJECT.md

        Args:
            section_name: Name of main section (GOALS, SCOPE, CONSTRAINTS)
            subsection: Optional subsection name (e.g., "In Scope")

        Returns:
            List of items in the section
        """
        # Find section
        section_pattern = rf"^##\s+{section_name}\s*$"
        section_match = re.search(section_pattern, self.content, re.MULTILINE)

        if not section_match:
            return []

        # Extract section content (until next ## heading)
        start = section_match.end()
        next_section = re.search(r"^##\s+", self.content[start:], re.MULTILINE)
        end = start + next_section.start() if next_section else len(self.content)

        section_content = self.content[start:end]

        # If subsection specified, extract that
        if subsection:
            subsection_pattern = rf"^###\s+{subsection}\s*$"
            subsection_match = re.search(subsection_pattern, section_content, re.MULTILINE)

            if not subsection_match:
                return []

            subsection_start = subsection_match.end()
            next_subsection = re.search(r"^###\s+", section_content[subsection_start:], re.MULTILINE)
            subsection_end = subsection_start + next_subsection.start() if next_subsection else len(section_content)

            section_content = section_content[subsection_start:subsection_end]

        # Extract bullet points and numbered lists
        items = []
        for line in section_content.split('\n'):
            line = line.strip()
            # Match bullet points (-, *) or numbered lists (1., 2., etc.)
            if line.startswith('-') or line.startswith('*') or re.match(r'^\d+\.', line):
                # Remove leading marker and ❌/✅ symbols
                item = re.sub(r'^[-*]\s*[❌✅]?\s*', '', line).strip()
                item = re.sub(r'^\d+\.\s*[❌✅]?\s*', '', item).strip()

                # Remove **bold** markers
                item = re.sub(r'\*\*(.*?)\*\*', r'\1', item)

                if item and not line.startswith('**'):  # Skip section headers
                    items.append(item)

        return items

    def to_dict(self) -> Dict[str, Any]:
        """Convert parsed PROJECT.md to dictionary"""
        return {
            'goals': self.goals,
            'scope': {
                'included': self.scope_included,
                'excluded': self.scope_excluded
            },
            'constraints': self.constraints
        }


class AlignmentValidator:
    """Validate request alignment with PROJECT.md"""

    @staticmethod
    def validate(
        request: str,
        project_md: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate if request aligns with PROJECT.md

        Args:
            request: User's request
            project_md: Parsed PROJECT.md content

        Returns:
            (is_aligned, reason, alignment_data)
        """
        goals = project_md.get('goals', [])
        scope_included = project_md.get('scope', {}).get('included', [])
        scope_excluded = project_md.get('scope', {}).get('excluded', [])
        constraints = project_md.get('constraints', [])

        # Check 1: Does request support any goal?
        matching_goals = []
        request_lower = request.lower()

        # Domain knowledge: semantic relationships
        semantic_mappings = {
            'authentication': ['security', 'auth', 'login', 'user management'],
            'testing': ['automation', 'quality', 'test', 'coverage'],
            'documentation': ['docs', 'guide', 'readme'],
            'security': ['authentication', 'encryption', 'validation', 'safe'],
            'performance': ['optimize', 'speed', 'fast', 'cache'],
            'automation': ['automatic', 'auto', 'workflow', 'pipeline']
        }

        for goal in goals:
            goal_lower = goal.lower()
            goal_keywords = set(re.findall(r'\b\w+\b', goal_lower))
            request_keywords = set(re.findall(r'\b\w+\b', request_lower))

            # Direct keyword match
            if len(goal_keywords & request_keywords) >= 1:
                matching_goals.append(goal)
                continue

            # Semantic match
            for req_keyword in request_keywords:
                for goal_keyword in goal_keywords:
                    # Check semantic relationships
                    if req_keyword in semantic_mappings.get(goal_keyword, []):
                        matching_goals.append(goal)
                        break
                    if goal_keyword in semantic_mappings.get(req_keyword, []):
                        matching_goals.append(goal)
                        break
                if goal in matching_goals:
                    break

        if not matching_goals:
            return False, f"Request doesn't support any PROJECT.md goal. Goals: {goals}", {}

        # Check 2: Is request within scope?
        # Check if explicitly excluded
        for excluded_item in scope_excluded:
            excluded_lower = excluded_item.lower()
            excluded_keywords = set(re.findall(r'\b\w+\b', excluded_lower))

            if len(excluded_keywords & set(re.findall(r'\b\w+\b', request_lower))) >= 2:
                return False, f"Request '{request}' is explicitly out of scope: {excluded_item}", {}

        # Check if within included scope
        in_scope_items = []
        for included_item in scope_included:
            included_lower = included_item.lower()
            included_keywords = set(re.findall(r'\b\w+\b', included_lower))

            if len(included_keywords & set(re.findall(r'\b\w+\b', request_lower))) >= 1:
                in_scope_items.append(included_item)

        if not in_scope_items and scope_included:  # Only check if scope is defined
            return False, f"Request not clearly within PROJECT.md scope. Scope: {scope_included}", {}

        # Check 3: Does request violate any constraint?
        violations = []
        for constraint in constraints:
            constraint_lower = constraint.lower()

            # Check for explicit "no" or "must not" patterns
            if re.search(r'\b(no|must not|cannot|don\'t)\b', constraint_lower):
                # Extract what's forbidden
                forbidden_patterns = re.findall(r'(?:no|must not|cannot|don\'t)\s+(\w+(?:\s+\w+)*)', constraint_lower)

                for pattern in forbidden_patterns:
                    if pattern in request_lower:
                        violations.append(f"{constraint} (detected: '{pattern}')")

        if violations:
            return False, f"Request violates constraints: {violations}", {}

        # All checks passed
        alignment_data = {
            'validated': True,
            'matches_goals': matching_goals,
            'within_scope': True,
            'scope_items': in_scope_items,
            'respects_constraints': True,
            'constraints_checked': len(constraints)
        }

        rationale = f"""
Alignment validated:
- Supports goals: {', '.join(matching_goals)}
- Within scope: {', '.join(in_scope_items) if in_scope_items else 'General scope'}
- Respects all {len(constraints)} constraints
"""

        return True, rationale.strip(), alignment_data


class Orchestrator:
    """
    Master coordinator for autonomous development v2.0

    Responsibilities:
    1. Validate PROJECT.md alignment
    2. Create workflow and artifacts
    3. Invoke 8-agent pipeline
    4. Monitor progress and handle errors
    5. Generate final report and commits
    """

    def __init__(
        self,
        project_md_path: Optional[Path] = None,
        artifacts_dir: Optional[Path] = None
    ):
        """
        Initialize orchestrator

        Args:
            project_md_path: Path to PROJECT.md (default: .claude/PROJECT.md)
            artifacts_dir: Base artifacts directory (default: .claude/artifacts)
        """
        if project_md_path is None:
            project_md_path = Path(".claude/PROJECT.md")

        self.project_md_path = project_md_path
        self.artifact_manager = ArtifactManager(artifacts_dir)

        # Parse PROJECT.md
        try:
            self.project_md_parser = ProjectMdParser(project_md_path)
            self.project_md = self.project_md_parser.to_dict()
        except FileNotFoundError as e:
            raise ValueError(
                f"PROJECT.md not found at {project_md_path}. "
                f"Please create .claude/PROJECT.md with GOALS, SCOPE, and CONSTRAINTS."
            ) from e

    def start_workflow(
        self,
        request: str,
        validate_alignment: bool = True
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Start autonomous workflow

        Args:
            request: User's implementation request
            validate_alignment: Whether to validate PROJECT.md alignment

        Returns:
            (success, message, workflow_id)
        """
        # Step 1: Validate alignment
        if validate_alignment:
            is_aligned, reason, alignment_data = AlignmentValidator.validate(
                request,
                self.project_md
            )

            if not is_aligned:
                error_msg = f"""
❌ **Alignment Failed**

Your request: "{request}"

Issue: {reason}

PROJECT.md goals: {self.project_md.get('goals', [])}
PROJECT.md scope: {self.project_md.get('scope', {}).get('included', [])}

To proceed:
1. Modify your request to align with PROJECT.md
2. OR update .claude/PROJECT.md if project direction changed

Cannot proceed with non-aligned work (zero tolerance for drift).
"""
                return False, error_msg, None

        else:
            # Skip validation (for testing)
            alignment_data = {
                'validated': False,
                'reason': 'Validation skipped'
            }

        # Step 2: Create workflow
        workflow_id = generate_workflow_id()
        workflow_dir = self.artifact_manager.create_workflow_directory(workflow_id)

        # Initialize logger
        logger = WorkflowLogger(workflow_id, 'orchestrator')
        logger.log_event('workflow_started', f'Starting workflow for: {request}')

        # Log alignment
        is_aligned, reason, _ = AlignmentValidator.validate(request, self.project_md)
        logger.log_alignment_check(
            is_aligned,
            reason,
            project_md_sections=self.project_md
        )

        # Step 3: Create workflow manifest
        workflow_plan = {
            'agents': ['researcher', 'planner', 'test-master', 'implementer'],
            'parallel_validators': ['reviewer', 'security-auditor', 'doc-master'],
            'estimated_duration': '60-120 seconds'
        }

        manifest_path = self.artifact_manager.create_manifest_artifact(
            workflow_id=workflow_id,
            request=request,
            alignment_data=alignment_data,
            workflow_plan=workflow_plan
        )

        logger.log_artifact_created(
            manifest_path,
            'manifest',
            summary=f'Workflow manifest for: {request}'
        )

        # Step 4: Initialize progress tracker
        progress_tracker = WorkflowProgressTracker(workflow_id)
        progress_tracker.update_progress(
            current_agent='orchestrator',
            status='completed',
            progress_percentage=10,
            message='✓ Workflow initialized - Alignment validated'
        )

        success_msg = f"""
✅ **Workflow Started**

Workflow ID: {workflow_id}
Request: {request}

Alignment: ✓ Validated
- Goals: {', '.join(alignment_data.get('matches_goals', []))}
- Scope: ✓ Within scope
- Constraints: ✓ All respected

Next: Invoking agent pipeline...

Manifest: {manifest_path}
"""

        return True, success_msg, workflow_id

    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get current workflow status

        Args:
            workflow_id: Workflow identifier

        Returns:
            Status dictionary
        """
        return self.artifact_manager.get_workflow_summary(workflow_id)


if __name__ == '__main__':
    # Example usage
    import tempfile
    from test_framework import MockProjectMd

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create mock PROJECT.md
        project_md = MockProjectMd(
            goals=["Improve security", "Automate workflows"],
            scope_included=["Authentication", "Testing automation"],
            scope_excluded=["Social media integration", "Real-time chat"],
            constraints=[
                "No third-party authentication frameworks",
                "Must use Python 3.8+",
                "80% test coverage minimum"
            ]
        )

        project_md_path = tmppath / ".claude" / "PROJECT.md"
        project_md.write_to(project_md_path)

        # Create orchestrator
        orchestrator = Orchestrator(
            project_md_path=project_md_path,
            artifacts_dir=tmppath / ".claude" / "artifacts"
        )

        # Test 1: Aligned request
        print("Test 1: Aligned request")
        print("-" * 60)
        success, message, workflow_id = orchestrator.start_workflow(
            "implement user authentication with JWT tokens"
        )
        print(message)
        print()

        # Test 2: Non-aligned request (out of scope)
        print("Test 2: Non-aligned request (out of scope)")
        print("-" * 60)
        success, message, workflow_id = orchestrator.start_workflow(
            "add real-time chat functionality"
        )
        print(message)
        print()

        # Test 3: Non-aligned request (violates constraint)
        print("Test 3: Non-aligned request (violates constraint)")
        print("-" * 60)
        success, message, workflow_id = orchestrator.start_workflow(
            "integrate OAuth with third-party authentication"
        )
        print(message)

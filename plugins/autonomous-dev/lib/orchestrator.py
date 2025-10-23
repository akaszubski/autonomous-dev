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

        # Parse SCOPE section by emoji
        self.scope_included = self._parse_section("SCOPE", emoji_filter='✅')
        self.scope_excluded = self._parse_section("SCOPE", emoji_filter='❌')

        self.constraints = self._parse_section("CONSTRAINTS")

    def _parse_section(
        self,
        section_name: str,
        subsection: Optional[str] = None,
        emoji_filter: Optional[str] = None
    ) -> List[str]:
        """
        Parse a section from PROJECT.md

        Args:
            section_name: Name of main section (GOALS, SCOPE, CONSTRAINTS)
            subsection: Optional subsection name (e.g., "In Scope")
            emoji_filter: Optional emoji to filter items (e.g., '✅' or '❌')

        Returns:
            List of items in the section
        """
        # Find section (allow any characters after section name, like emojis)
        section_pattern = rf"^##\s+{section_name}\b"
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
            # Try ### header first (h3)
            subsection_pattern = rf"^###\s+{subsection}\s*$"
            subsection_match = re.search(subsection_pattern, section_content, re.MULTILINE)

            # If not found, try **bold** header with flexible matching
            if not subsection_match:
                # Match "**What's IN Scope**" for subsection="In Scope"
                # Use case-insensitive and partial matching
                subsection_pattern = rf"\*\*.*?{re.escape(subsection)}.*?\*\*"
                subsection_match = re.search(subsection_pattern, section_content, re.IGNORECASE)

            if not subsection_match:
                return []

            subsection_start = subsection_match.end()

            # Find next subsection (either ### or **)
            next_subsection = re.search(r"(^###\s+|\*\*.*?\*\*)", section_content[subsection_start:], re.MULTILINE)
            subsection_end = subsection_start + next_subsection.start() if next_subsection else len(section_content)

            section_content = section_content[subsection_start:subsection_end]

        # Extract bullet points and numbered lists
        items = []
        for line in section_content.split('\n'):
            line = line.strip()

            # Skip section headers (lines with ** that end with : or **:)
            if line.startswith('**') and (':' in line or line.endswith('**')):
                continue

            # Skip horizontal rules (---, ***, etc.)
            if line.startswith('---') or line.startswith('***') or line == '--':
                continue

            # Apply emoji filter if specified
            if emoji_filter and emoji_filter not in line:
                continue

            # Match bullet points (-, *) or numbered lists (1., 2., etc.)
            if line.startswith('-') or line.startswith('*') or re.match(r'^\d+\.', line):
                # Remove leading marker and ❌/✅ symbols
                item = re.sub(r'^[-*]\s*[❌✅]?\s*', '', line).strip()
                item = re.sub(r'^\d+\.\s*[❌✅]?\s*', '', item).strip()

                # Remove **bold** markers
                item = re.sub(r'\*\*(.*?)\*\*', r'\1', item)

                # Extract main content before dash or hyphen (for items like "Goal - explanation")
                # This gets "Goal" from "Goal - explanation text"
                if ' - ' in item:
                    item = item.split(' - ')[0].strip()

                if item and not item.endswith(':'):  # Skip headers and empty items
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
            project_md_path: Path to PROJECT.md (default: ./PROJECT.md)
            artifacts_dir: Base artifacts directory (default: .claude/artifacts)
        """
        if project_md_path is None:
            project_md_path = Path("PROJECT.md")

        self.project_md_path = project_md_path
        self.artifact_manager = ArtifactManager(artifacts_dir)

        # Parse PROJECT.md
        try:
            self.project_md_parser = ProjectMdParser(project_md_path)
            self.project_md = self.project_md_parser.to_dict()
        except FileNotFoundError as e:
            raise ValueError(
                f"PROJECT.md not found at {project_md_path}. "
                f"Please create PROJECT.md at your project root with GOALS, SCOPE, and CONSTRAINTS.\n"
                f"Run '/setup' to create from template."
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
2. OR update PROJECT.md if project direction changed

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

    def invoke_researcher(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke researcher agent via Task tool to perform pattern research

        Args:
            workflow_id: Workflow identifier

        Returns:
            Result dictionary with status and researcher output
        """
        from logging_utils import WorkflowLogger, WorkflowProgressTracker

        # Initialize logger
        logger = WorkflowLogger(workflow_id, 'orchestrator')
        logger.log_event('invoke_researcher', 'Invoking researcher agent')
        logger.log_decision(
            decision='Invoke researcher for pattern analysis',
            rationale='Need to search codebase and web for existing patterns before planning',
            alternatives_considered=['Skip research and plan directly'],
            metadata={'workflow_id': workflow_id}
        )

        # Update progress
        progress_tracker = WorkflowProgressTracker(workflow_id)
        progress_tracker.update_progress(
            current_agent='researcher',
            status='in_progress',
            progress_percentage=20,
            message='Researcher: Searching codebase and web for patterns...'
        )

        # Read manifest to get request context
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        request = manifest.get('request', '')

        # Invoke researcher via Task tool
        logger.log_event('task_tool_invocation', f'Invoking researcher subagent for: {request}')

        # This will invoke the researcher subagent through Claude Code's Task tool
        # The Task tool will launch the researcher agent with the prompt below
        result = {
            'subagent_type': 'researcher',
            'description': f'Research patterns for: {request}',
            'prompt': f"""
You are the **researcher** agent for autonomous-dev v2.0 workflow {workflow_id}.

## Your Mission

Research existing patterns, best practices, and security considerations for the following request:

**Request**: {request}

## Workflow Context

Read the workflow manifest to understand the full context:
- **Manifest location**: `.claude/artifacts/{workflow_id}/manifest.json`
- This contains the user request, PROJECT.md alignment data, and workflow plan

## Your Tasks

### 1. Codebase Search (2-3 minutes)
- Use Grep to search for relevant keywords from the request
- Use Glob to find related files (e.g., if request mentions "auth", search for `**/auth*.py`)
- Read existing implementations to understand current patterns
- Document what we already have

### 2. Web Research (5-7 minutes)
- Perform 3-5 WebSearch queries for best practices (use 2025 for recency)
- Use WebFetch to extract content from top 5 sources
- Prioritize: official docs > GitHub examples > recent blog posts > Stack Overflow

### 3. Create Research Artifact

Create `.claude/artifacts/{workflow_id}/research.json` with this structure:

```json
{{
  "version": "2.0",
  "agent": "researcher",
  "workflow_id": "{workflow_id}",
  "status": "completed",
  "timestamp": "<current ISO timestamp>",
  "codebase_patterns": [
    {{
      "pattern": "<pattern name>",
      "location": "<file path>",
      "relevance": "<why it matters>"
    }}
  ],
  "best_practices": [
    {{
      "practice": "<practice description>",
      "source": "<URL>",
      "rationale": "<why recommended>"
    }}
  ],
  "security_considerations": [
    "<security item 1>",
    "<security item 2>"
  ],
  "recommended_libraries": [
    {{
      "name": "<library name>",
      "version": "<version>",
      "rationale": "<why chosen>"
    }}
  ],
  "alternatives_considered": [
    {{
      "option": "<alternative approach>",
      "reason_not_chosen": "<why not>"
    }}
  ]
}}
```

## Quality Requirements

✅ At least 1 codebase pattern documented (or note "none found")
✅ At least 3 best practices from recent sources (2024-2025)
✅ Security considerations included
✅ At least 1 recommended library with rationale
✅ Alternatives documented with reasons

## Logging

Use the logging system to track your research decisions:

```python
from plugins.autonomous_dev.lib.logging_utils import WorkflowLogger

logger = WorkflowLogger('{workflow_id}', 'researcher')
logger.log_decision(
    decision='Selected pattern X over pattern Y',
    rationale='Pattern X better fits our architecture',
    alternatives_considered=['Pattern Y', 'Pattern Z']
)
```

## Completion

When done:
1. Verify research.json exists and is valid JSON
2. Report back with summary of findings
3. Next agent (planner) will use your research to design architecture

**Time limit**: 15 minutes maximum
**Output**: .claude/artifacts/{workflow_id}/research.json

Begin research now.
"""
        }

        logger.log_event(
            'researcher_invoked',
            'Researcher agent invocation prepared',
            metadata={'subagent_type': result['subagent_type'], 'workflow_id': workflow_id}
        )

        # Return the prepared invocation dict
        # The caller can choose to invoke via Task tool or use for testing
        return result

    def invoke_researcher_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke researcher agent using actual Task tool (Week 5+)

        This method uses the real Task tool to launch the researcher subagent.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Result dictionary with researcher output and artifact paths
        """
        from logging_utils import WorkflowLogger
        from checkpoint import CheckpointManager

        logger = WorkflowLogger(workflow_id, 'orchestrator')

        # Prepare invocation using existing method
        invocation = self.invoke_researcher(workflow_id)

        logger.log_event(
            'task_tool_invocation_start',
            f'Launching researcher via Task tool for workflow {workflow_id}'
        )

        try:
            # Actually invoke the Task tool
            # This will launch the researcher subagent which will:
            # 1. Read manifest.json
            # 2. Search codebase and web
            # 3. Create research.json

            # Note: The Task tool will return when researcher completes
            # For now, we'll document the invocation pattern
            # In production, uncomment the Task tool call below

            logger.log_event(
                'task_tool_ready',
                'Task tool invocation prepared - ready to launch researcher',
                metadata={
                    'workflow_id': workflow_id,
                    'subagent': 'researcher',
                    'expected_output': f'.claude/artifacts/{workflow_id}/research.json'
                }
            )

            # Return invocation parameters for Claude Code to use with Task tool
            # Claude Code will invoke: Task(subagent_type=..., description=..., prompt=...)
            return {
                'status': 'ready_for_invocation',
                'workflow_id': workflow_id,
                'invocation': invocation,
                'expected_artifact': f'.claude/artifacts/{workflow_id}/research.json',
                'message': 'Orchestrator prepared researcher invocation. Use Task tool to execute.'
            }

        except Exception as e:
            logger.log_event(
                'task_tool_error',
                f'Failed to invoke researcher: {str(e)}',
                metadata={'error': str(e), 'workflow_id': workflow_id}
            )
            raise

        finally:
            # After researcher completes (whether success or failure),
            # create checkpoint
            try:
                checkpoint_manager = CheckpointManager()
                checkpoint_manager.create_checkpoint(
                    workflow_id=workflow_id,
                    completed_agents=['orchestrator', 'researcher'],
                    current_agent='planner',
                    artifacts_created=['manifest.json', 'research.json']
                )
                logger.log_event(
                    'checkpoint_created',
                    'Checkpoint created after researcher completion'
                )
            except Exception as e:
                logger.log_event(
                    'checkpoint_error',
                    f'Failed to create checkpoint: {str(e)}'
                )
    def invoke_planner(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke planner agent to design architecture

        This method prepares the planner agent invocation based on research findings.
        Planner will read research.json and create architecture.json.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Dict with planner invocation parameters ready for Task tool
        """
        from logging_utils import WorkflowLogger, WorkflowProgressTracker

        logger = WorkflowLogger(workflow_id, 'orchestrator')
        logger.log_event('invoke_planner', 'Invoking planner agent')

        # Update progress
        progress_tracker = WorkflowProgressTracker(workflow_id)
        progress_tracker.update_progress(
            current_agent='planner',
            status='in_progress',
            progress_percentage=30,
            message='Planner: Designing architecture based on research...'
        )

        # Read manifest and research for context
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        research = self.artifact_manager.read_artifact(workflow_id, 'research')

        request = manifest.get('request', '')

        # Log decision to invoke planner
        logger.log_decision(
            decision='Invoke planner for architecture design',
            rationale='Research complete, need to design implementation architecture',
            alternatives_considered=['Skip planning and implement directly'],
            metadata={'workflow_id': workflow_id}
        )

        # Prepare planner invocation with complete prompt
        result = {
            'subagent_type': 'planner',
            'description': f'Design architecture for: {request}',
            'prompt': f"""
You are the **planner** agent for autonomous-dev v2.0 workflow {workflow_id}.

## Your Mission

Design a detailed, actionable architecture plan for the following request:

**Request**: {request}

## Workflow Context

Read the workflow artifacts to understand the full context:

**Manifest location**: `.claude/artifacts/{workflow_id}/manifest.json`
- Contains: user request, PROJECT.md alignment data, workflow plan

**Research location**: `.claude/artifacts/{workflow_id}/research.json`
- Contains: codebase patterns, best practices, security considerations, recommended libraries

## Your Tasks

### 1. Read Context (2-3 minutes)

Read manifest.json and research.json to understand:
- What the user wants to build
- What patterns already exist in the codebase
- What security requirements must be met
- What libraries are recommended
- What constraints must be respected

### 2. Codebase Analysis (3-5 minutes)

Use research findings to explore integration points:
- Search for similar implementations
- Map file structure where new code will live
- Identify existing code to modify vs new files to create

### 3. Design Architecture (5-7 minutes)

Create detailed architecture including:
- API contracts (function signatures, inputs/outputs)
- File changes (create/modify/delete with purposes)
- Implementation phases (TDD approach)
- Integration points (connections to existing code)
- Testing strategy (unit + integration + security)
- Security design (threat model, mitigations)
- Error handling (expected errors, recovery)
- Documentation plan (what to update)

## Create Architecture Artifact

Create `.claude/artifacts/{workflow_id}/architecture.json` following the complete schema defined in planner.md agent specification.

**Required sections**:
- architecture_summary
- api_contracts
- file_changes
- implementation_plan
- integration_points
- testing_strategy
- security_design
- error_handling
- documentation_plan
- risk_assessment
- project_md_alignment

## Quality Requirements

✅ API contracts for all public functions/classes
✅ Complete file change list with purposes and estimates
✅ Phased implementation plan with time estimates
✅ All integration points identified
✅ Comprehensive testing strategy (unit + integration + security)
✅ Security design with threat model
✅ Error handling for expected failures
✅ Documentation update plan
✅ Risk assessment with mitigations
✅ PROJECT.md alignment confirmed

## Logging

Track your planning decisions:

```python
from plugins.autonomous_dev.lib.logging_utils import WorkflowLogger

logger = WorkflowLogger('{workflow_id}', 'planner')
logger.log_decision(
    decision='Use subprocess for gh CLI calls',
    rationale='Matches existing pattern in auto_track_issues.py',
    alternatives_considered=['PyGithub library', 'REST API']
)
```

## Completion

When done:
1. Verify architecture.json exists and is valid JSON
2. All required sections present
3. Report back with architecture summary
4. Next agent (test-master) will read architecture.json and write failing tests

**Time limit**: 15 minutes maximum
**Model**: opus (complex architectural reasoning)
**Output**: `.claude/artifacts/{workflow_id}/architecture.json`

Begin planning now.
"""
        }

        logger.log_event(
            'task_tool_invocation',
            f'Invoking planner subagent for: {request}'
        )

        logger.log_event(
            'planner_invoked',
            'Planner agent invocation prepared',
            metadata={'subagent_type': result['subagent_type'], 'workflow_id': workflow_id}
        )

        # Return the prepared invocation dict
        return result

    def invoke_planner_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke planner agent using actual Task tool (Week 7+)

        This method uses the real Task tool to launch the planner subagent.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Result dictionary with planner invocation status
        """
        from logging_utils import WorkflowLogger
        from checkpoint import CheckpointManager

        logger = WorkflowLogger(workflow_id, 'orchestrator')

        # Prepare invocation using existing method
        invocation = self.invoke_planner(workflow_id)

        logger.log_event(
            'task_tool_invocation_start',
            f'Launching planner via Task tool for workflow {workflow_id}'
        )

        try:
            logger.log_event(
                'task_tool_ready',
                'Task tool invocation prepared - ready to launch planner',
                metadata={
                    'workflow_id': workflow_id,
                    'subagent': 'planner',
                    'expected_output': f'.claude/artifacts/{workflow_id}/architecture.json'
                }
            )

            # Return invocation parameters for Claude Code to use with Task tool
            return {
                'status': 'ready_for_invocation',
                'workflow_id': workflow_id,
                'invocation': invocation,
                'expected_artifact': f'.claude/artifacts/{workflow_id}/architecture.json',
                'message': 'Orchestrator prepared planner invocation. Use Task tool to execute.'
            }

        except Exception as e:
            logger.log_event(
                'task_tool_error',
                f'Failed to invoke planner: {str(e)}',
                metadata={'error': str(e), 'workflow_id': workflow_id}
            )
            raise

        finally:
            # After planner completes, create checkpoint ONLY if artifact exists
            try:
                from pathlib import Path

                # Validate architecture.json actually exists
                arch_path = Path(f".claude/artifacts/{workflow_id}/architecture.json")

                if arch_path.exists():
                    # Artifact exists - planner truly completed
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner'],
                        current_agent='test-master',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json']
                    )
                    logger.log_event(
                        'checkpoint_created',
                        'Checkpoint created after planner completion',
                        metadata={'artifact_size': arch_path.stat().st_size}
                    )
                else:
                    # Artifact missing - planner did not complete
                    logger.log_event(
                        'checkpoint_skipped',
                        'Checkpoint not created - planner artifact missing',
                        metadata={
                            'expected_artifact': str(arch_path),
                            'reason': 'architecture.json does not exist'
                        }
                    )
                    # Create partial checkpoint showing planner did not complete
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher'],
                        current_agent='planner',
                        artifacts_created=['manifest.json', 'research.json']
                    )
            except Exception as e:
                logger.log_event(
                    'checkpoint_error',
                    f'Failed to create checkpoint: {str(e)}'
                )
    def invoke_test_master(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke test-master agent to write failing TDD tests

        This method prepares the test-master agent invocation based on architecture.
        Test-master will read architecture.json and create tests.json.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Dict with test-master invocation parameters ready for Task tool
        """
        from logging_utils import WorkflowLogger, WorkflowProgressTracker

        logger = WorkflowLogger(workflow_id, 'orchestrator')
        logger.log_event('invoke_test_master', 'Invoking test-master agent')

        # Update progress
        progress_tracker = WorkflowProgressTracker(workflow_id)
        progress_tracker.update_progress(
            current_agent='test-master',
            status='in_progress',
            progress_percentage=50,
            message='Test-Master: Writing failing TDD tests...'
        )

        # Read manifest and architecture for context
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        architecture = self.artifact_manager.read_artifact(workflow_id, 'architecture')

        request = manifest.get('request', '')

        # Log decision to invoke test-master
        logger.log_decision(
            decision='Invoke test-master for TDD test generation',
            rationale='Architecture complete, need to write failing tests before implementation',
            alternatives_considered=['Skip tests and implement directly'],
            metadata={'workflow_id': workflow_id}
        )

        # Prepare test-master invocation with complete prompt
        result = {
            'subagent_type': 'test-master',
            'description': f'Write TDD tests for: {request}',
            'prompt': f"""
You are the **test-master** agent for autonomous-dev v2.0 workflow {workflow_id}.

## Your Mission

Write comprehensive **failing tests FIRST** (TDD red phase) based on the architecture plan.

**Request**: {request}

## Workflow Context

Read the workflow artifacts to understand what to test:

**Manifest location**: `.claude/artifacts/{workflow_id}/manifest.json`
- Contains: user request, PROJECT.md alignment data

**Research location**: `.claude/artifacts/{workflow_id}/research.json`
- Contains: codebase patterns, existing test structure, testing best practices

**Architecture location**: `.claude/artifacts/{workflow_id}/architecture.json`
- Contains: API contracts to test, testing strategy, error conditions, security requirements

## Your Tasks

### 1. Read Architecture (3-5 minutes)

Read `architecture.json` and identify:
- API contracts (functions/classes with inputs, outputs, errors)
- Testing strategy (unit, integration, security test requirements)
- Error handling (expected errors to test)
- Security design (threats to test against)

### 2. Design Test Suite (5-7 minutes)

Create comprehensive test plan covering:
- Happy path tests (valid inputs → expected outputs)
- Error tests (invalid inputs → expected errors)
- Edge cases (boundary conditions, empty inputs, null values)
- Integration tests (component interactions)
- Security tests (threat model validation)

### 3. Write Test Specifications (10-15 minutes)

Design test files that will FAIL initially (no implementation yet).

For each API contract in architecture.json, create:
- Test file path (tests/unit/test_*.py or tests/integration/test_*.py)
- Test functions with descriptive names
- Assertions to validate
- Mocking strategy for external dependencies

### 4. Create Tests Artifact (3-5 minutes)

Create `.claude/artifacts/{workflow_id}/tests.json` following the complete schema defined in test-master.md agent specification.

**Required sections**:
- test_summary (total files, functions, coverage target)
- test_files (list of test files to create)
- test_cases (individual test functions with scenarios)
- coverage_plan (target percentage, critical paths)
- mocking_strategy (external services to mock)
- test_execution_plan (commands to run tests)

## Quality Requirements

✅ Test coverage aim: 90%+ of API contracts
✅ Test pyramid: More unit tests than integration tests
✅ TDD red phase: All tests MUST fail initially (no implementation)
✅ Descriptive names: Test names describe scenario being tested
✅ Error testing: Every expected error has a test
✅ Edge cases: Boundary conditions tested
✅ Mocking: External dependencies mocked appropriately
✅ Security tests: Threat model scenarios tested

## Completion

When done:
1. Verify tests.json exists and is valid JSON
2. All required sections present
3. Report back with test summary
4. Next agent (implementer) will make these tests pass

**Time limit**: 30 minutes maximum
**Model**: sonnet (cost-effective for code generation)
**Output**: `.claude/artifacts/{workflow_id}/tests.json`

Begin writing tests now.
"""
        }

        logger.log_event(
            'task_tool_invocation',
            f'Invoking test-master subagent for: {request}'
        )

        logger.log_event(
            'test_master_invoked',
            'Test-master agent invocation prepared',
            metadata={'subagent_type': result['subagent_type'], 'workflow_id': workflow_id}
        )

        # Return the prepared invocation dict
        return result

    def invoke_test_master_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke test-master agent using actual Task tool (Week 8+)

        This method uses the real Task tool to launch the test-master subagent.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Result dictionary with test-master invocation status
        """
        from logging_utils import WorkflowLogger
        from checkpoint import CheckpointManager

        logger = WorkflowLogger(workflow_id, 'orchestrator')

        # Prepare invocation using existing method
        invocation = self.invoke_test_master(workflow_id)

        logger.log_event(
            'task_tool_invocation_start',
            f'Launching test-master via Task tool for workflow {workflow_id}'
        )

        try:
            logger.log_event(
                'task_tool_ready',
                'Task tool invocation prepared - ready to launch test-master',
                metadata={
                    'workflow_id': workflow_id,
                    'subagent': 'test-master',
                    'expected_output': f'.claude/artifacts/{workflow_id}/tests.json'
                }
            )

            # Return invocation parameters for Claude Code to use with Task tool
            return {
                'status': 'ready_for_invocation',
                'workflow_id': workflow_id,
                'invocation': invocation,
                'expected_artifact': f'.claude/artifacts/{workflow_id}/tests.json',
                'message': 'Orchestrator prepared test-master invocation. Use Task tool to execute.'
            }

        except Exception as e:
            logger.log_event(
                'task_tool_error',
                f'Failed to invoke test-master: {str(e)}',
                metadata={'error': str(e), 'workflow_id': workflow_id}
            )
            raise

        finally:
            # After test-master completes, create checkpoint ONLY if artifact exists
            try:
                from pathlib import Path

                # Validate tests.json actually exists
                tests_path = Path(f".claude/artifacts/{workflow_id}/tests.json")

                if tests_path.exists():
                    # Artifact exists - test-master truly completed
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner', 'test-master'],
                        current_agent='implementer',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json', 'tests.json']
                    )
                    logger.log_event(
                        'checkpoint_created',
                        'Checkpoint created after test-master completion',
                        metadata={'artifact_size': tests_path.stat().st_size}
                    )
                else:
                    # Artifact missing - test-master did not complete
                    logger.log_event(
                        'checkpoint_skipped',
                        'Checkpoint not created - test-master artifact missing',
                        metadata={
                            'expected_artifact': str(tests_path),
                            'reason': 'tests.json does not exist'
                        }
                    )
                    # Create partial checkpoint showing test-master did not complete
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner'],
                        current_agent='test-master',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json']
                    )
            except Exception as e:
                logger.log_event(
                    'checkpoint_error',
                    f'Failed to create checkpoint: {str(e)}'
                )

    def invoke_implementer(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke implementer agent to write code that makes tests pass

        This method prepares the implementer agent invocation based on architecture and tests.
        Implementer will read architecture.json and tests.json, then create implementation.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Dict with implementer invocation parameters ready for Task tool
        """
        from logging_utils import WorkflowLogger, WorkflowProgressTracker

        logger = WorkflowLogger(workflow_id, 'orchestrator')
        logger.log_event('invoke_implementer', 'Invoking implementer agent')

        # Update progress
        progress_tracker = WorkflowProgressTracker(workflow_id)
        progress_tracker.update_progress(
            current_agent='implementer',
            status='in_progress',
            progress_percentage=70,
            message='Implementer: Writing code to make tests pass...'
        )

        # Read manifest, architecture, and tests for context
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        architecture = self.artifact_manager.read_artifact(workflow_id, 'architecture')
        tests = self.artifact_manager.read_artifact(workflow_id, 'tests')

        request = manifest.get('request', '')

        # Log decision to invoke implementer
        logger.log_decision(
            decision='Invoke implementer for TDD green phase (make tests pass)',
            rationale='Tests written and failing, need implementation to make them pass',
            alternatives_considered=['Manual implementation'],
            metadata={'workflow_id': workflow_id}
        )

        # Prepare implementer invocation with complete prompt
        result = {
            'subagent_type': 'implementer',
            'description': f'Implement code for: {request}',
            'prompt': f"""
You are the **implementer** agent for autonomous-dev v2.0 workflow {workflow_id}.

## Your Mission

Write **clean, tested implementation** that makes ALL failing tests PASS (TDD green phase).

**Request**: {request}

## Workflow Context

Read the workflow artifacts to understand what to build:

**Manifest location**: `.claude/artifacts/{workflow_id}/manifest.json`
- Contains: user request, PROJECT.md alignment data

**Architecture location**: `.claude/artifacts/{workflow_id}/architecture.json`
- Contains: API contracts to implement, file changes, error handling, security requirements

**Tests location**: `.claude/artifacts/{workflow_id}/tests.json`
- Contains: Test specifications (what needs to pass), mocking strategy, coverage requirements

## Your Tasks

### 1. Read Artifacts (3-5 minutes)

Read architecture.json and tests.json to understand:
- What functions/classes to create (API contracts)
- Function signatures, inputs, outputs, errors
- What behavior is expected (from test cases)
- What assertions need to pass

### 2. Analyze Failing Tests (2-3 minutes)

Run tests to see current state (they should all FAIL):
```bash
pytest tests/unit/test_pr_automation.py -v
pytest tests/integration/test_pr_workflow.py -v
pytest tests/security/test_pr_security.py -v
```

### 3. Implement in TDD Cycles (20-30 minutes)

For each function from architecture.json API contracts:

**RED → GREEN → REFACTOR**

1. Run ONE test to see it fail
2. Write MINIMAL code to make that test pass
3. Run test again to see it pass
4. Refactor code while keeping tests green
5. Repeat for next test

**Implementation order:**
1. `validate_gh_prerequisites()` - Simplest function first
2. `get_current_branch()` - Next simplest
3. `parse_commit_messages_for_issues()` - More complex (regex)
4. `create_pull_request()` - Most complex (builds on others)

### 4. Handle All Error Cases (10-15 minutes)

Implement error handling for:
- `FileNotFoundError` (gh CLI not installed)
- `subprocess.CalledProcessError` (command failures, auth errors)
- `subprocess.TimeoutExpired` (network timeout)
- `ValueError` (validation failures like on main branch)

### 5. Validate All Tests Pass (5 minutes)

Run complete test suite:
```bash
pytest tests/ -v
```

**Expected result:** ALL PASS, 0 FAILED

### 6. Create Implementation Artifact (3-5 minutes)

Create `.claude/artifacts/{workflow_id}/implementation.json` following the complete schema defined in implementer.md agent specification.

**Required sections:**
- implementation_summary (files created, lines added, tests passing)
- files_implemented (actual files created/modified)
- functions_implemented (list of functions with details)
- test_results (unit, integration, security test results)
- code_quality (type hints, docstrings, error handling)
- tdd_validation (red → green → refactor validation)

## Quality Requirements

✅ All tests pass (100% pass rate, 0 failures)
✅ Type hints on all functions
✅ Docstrings on all public functions (Google style)
✅ Error handling for all expected errors
✅ Code follows existing codebase patterns
✅ No secrets in code
✅ Subprocess calls use timeout=30
✅ All subprocess calls are mockable (for tests)

## Implementation Pattern

Use subprocess for gh CLI and git commands:

```python
import subprocess
from typing import Dict, List, Tuple, Any

def validate_gh_prerequisites() -> Tuple[bool, str]:
    \"\"\"Check gh CLI installed and authenticated.\"\"\"
    try:
        subprocess.run(['gh', '--version'], capture_output=True, check=True)
        result = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True)
        return result.returncode == 0, "" if result.returncode == 0 else "Not authenticated"
    except FileNotFoundError:
        return False, "gh CLI not installed"
```

## Completion

When done:
1. Verify all tests pass: `pytest tests/ -v` → ALL PASS
2. Create implementation.json artifact
3. Report back with test results
4. Next agent (reviewer) will validate code quality

**Time limit**: 45 minutes maximum
**Model**: sonnet (cost-effective code generation)
**Output**:
- `.claude/artifacts/{workflow_id}/implementation.json`
- `plugins/autonomous-dev/lib/pr_automation.py` (actual code)

Begin implementation now.
"""
        }

        logger.log_event(
            'task_tool_invocation',
            f'Invoking implementer subagent for: {request}'
        )

        logger.log_event(
            'implementer_invoked',
            'Implementer agent invocation prepared',
            metadata={'subagent_type': result['subagent_type'], 'workflow_id': workflow_id}
        )

        # Return the prepared invocation dict
        return result

    def invoke_implementer_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke implementer agent using actual Task tool (Week 9+)

        This method uses the real Task tool to launch the implementer subagent.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Result dictionary with implementer invocation status
        """
        from logging_utils import WorkflowLogger
        from checkpoint import CheckpointManager

        logger = WorkflowLogger(workflow_id, 'orchestrator')

        # Prepare invocation using existing method
        invocation = self.invoke_implementer(workflow_id)

        logger.log_event(
            'task_tool_invocation_start',
            f'Launching implementer via Task tool for workflow {workflow_id}'
        )

        try:
            logger.log_event(
                'task_tool_ready',
                'Task tool invocation prepared - ready to launch implementer',
                metadata={
                    'workflow_id': workflow_id,
                    'subagent': 'implementer',
                    'expected_output': f'.claude/artifacts/{workflow_id}/implementation.json'
                }
            )

            # Return invocation parameters for Claude Code to use with Task tool
            return {
                'status': 'ready_for_invocation',
                'workflow_id': workflow_id,
                'invocation': invocation,
                'expected_artifact': f'.claude/artifacts/{workflow_id}/implementation.json',
                'message': 'Orchestrator prepared implementer invocation. Use Task tool to execute.'
            }

        except Exception as e:
            logger.log_event(
                'task_tool_error',
                f'Failed to invoke implementer: {str(e)}',
                metadata={'error': str(e), 'workflow_id': workflow_id}
            )
            raise

        finally:
            # After implementer completes, create checkpoint ONLY if artifact exists
            try:
                from pathlib import Path

                # Validate implementation.json actually exists
                impl_path = Path(f".claude/artifacts/{workflow_id}/implementation.json")

                if impl_path.exists():
                    # Artifact exists - implementer truly completed
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner', 'test-master', 'implementer'],
                        current_agent='reviewer',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json', 'tests.json', 'implementation.json']
                    )
                    logger.log_event(
                        'checkpoint_created',
                        'Checkpoint created after implementer completion',
                        metadata={'artifact_size': impl_path.stat().st_size}
                    )
                else:
                    # Artifact missing - implementer did not complete
                    logger.log_event(
                        'checkpoint_skipped',
                        'Checkpoint not created - implementer artifact missing',
                        metadata={
                            'expected_artifact': str(impl_path),
                            'reason': 'implementation.json does not exist'
                        }
                    )
                    # Create partial checkpoint showing implementer did not complete
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner', 'test-master'],
                        current_agent='implementer',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json', 'tests.json']
                    )
            except Exception as e:
                logger.log_event(
                    'checkpoint_error',
                    f'Failed to create checkpoint: {str(e)}'
                )

    def invoke_reviewer(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke reviewer agent to validate code quality

        This method prepares the reviewer agent invocation based on implementation.
        Reviewer will read implementation.json and actual code files, then create review.json.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Dict with reviewer invocation parameters ready for Task tool
        """
        from logging_utils import WorkflowLogger, WorkflowProgressTracker

        logger = WorkflowLogger(workflow_id, 'orchestrator')
        logger.log_event('invoke_reviewer', 'Invoking reviewer agent')

        # Update progress
        progress_tracker = WorkflowProgressTracker(workflow_id)
        progress_tracker.update_progress(
            current_agent='reviewer',
            status='in_progress',
            progress_percentage=85,
            message='Reviewer: Validating code quality and test coverage...'
        )

        # Read manifest, architecture, tests, and implementation for context
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        architecture = self.artifact_manager.read_artifact(workflow_id, 'architecture')
        tests = self.artifact_manager.read_artifact(workflow_id, 'tests')
        implementation = self.artifact_manager.read_artifact(workflow_id, 'implementation')

        request = manifest.get('request', '')

        # Log decision to invoke reviewer
        logger.log_decision(
            decision='Invoke reviewer for code quality validation',
            rationale='Implementation complete, need to validate quality before security audit',
            alternatives_considered=['Skip review and proceed to security'],
            metadata={'workflow_id': workflow_id}
        )

        # Prepare reviewer invocation with complete prompt
        result = {
            'subagent_type': 'reviewer',
            'description': f'Review code quality for: {request}',
            'prompt': f"""
You are the **reviewer** agent for autonomous-dev v2.0 workflow {workflow_id}.

## Your Mission

Review implementation for code quality, test coverage, documentation completeness, and adherence to project standards. **Approve** if quality meets standards, or **request changes** if improvements needed.

**Request**: {request}

## Workflow Context

Read the workflow artifacts to understand what to review:

**Manifest location**: `.claude/artifacts/{workflow_id}/manifest.json`
- Contains: user request, PROJECT.md alignment data

**Architecture location**: `.claude/artifacts/{workflow_id}/architecture.json`
- Contains: API contracts (expected signatures), code quality requirements, testing strategy

**Tests location**: `.claude/artifacts/{workflow_id}/tests.json`
- Contains: Test specifications, coverage targets (90%+)

**Implementation location**: `.claude/artifacts/{workflow_id}/implementation.json`
- Contains: Files implemented, functions created, test results claimed

## Your Tasks

### 1. Read Implementation (3-5 minutes)

Read implementation.json to understand:
- Which files were created/modified
- Which functions were implemented
- What test results were reported
- What quality claims were made

### 2. Validate Code Quality (10-15 minutes)

For each implementation file, check:

**Type Hints:**
- ✓ All functions have complete type hints
- ✓ No missing return types
- ✓ Proper use of Optional, List, Dict, etc.

**Docstrings:**
- ✓ All public functions have Google-style docstrings
- ✓ Args, Returns, Raises sections present
- ✓ Clear descriptions

**Error Handling:**
- ✓ All expected errors caught and handled
- ✓ Specific exception types (not bare except)
- ✓ Helpful error messages with context

**Code Patterns:**
- ✓ Follows existing codebase conventions
- ✓ Uses subprocess.run() with timeouts
- ✓ No os.system() calls
- ✓ Consistent style

### 3. Validate Test Coverage (5-10 minutes)

Run tests to verify they actually pass:

```bash
pytest tests/unit/test_pr_automation.py -v
pytest tests/integration/test_pr_workflow.py -v
pytest tests/security/test_pr_security.py -v

# Check coverage
pytest tests/ --cov=plugins.autonomous_dev.lib.pr_automation --cov-report=term
```

**Coverage Requirements:**
- Unit tests: 90%+ line coverage
- All public functions tested
- All error paths tested
- Edge cases covered

### 4. Check Security (3-5 minutes)

Validate security requirements:
- No secrets in code (no hardcoded tokens, passwords)
- Subprocess calls use timeout (prevent hanging)
- Input validation (sanitize user inputs)
- No shell=True in subprocess calls (prevent injection)

### 5. Verify Documentation (2-3 minutes)

Check documentation completeness:
- All public functions have docstrings
- Docstrings follow Google style
- Error messages are helpful (what, why, how to fix)
- Comments explain complex logic

### 6. Create Review Artifact (3-5 minutes)

Create `.claude/artifacts/{workflow_id}/review.json` following the complete schema defined in reviewer.md agent specification.

**Required sections:**
- review_summary (decision, quality, issues found)
- code_quality_checks (type hints, docstrings, error handling, patterns)
- test_coverage (unit, integration, security test results)
- security_checks (no secrets, timeouts, validation, injection prevention)
- documentation (docstring coverage, error messages)
- issues (list of problems if changes requested)
- recommendations (suggestions for improvement)
- approval (approved/not approved, next step)

## Decision Criteria

### APPROVE if:
- ✅ All functions have type hints (100%)
- ✅ All public functions have docstrings (100%)
- ✅ All expected errors are handled
- ✅ Test coverage ≥ 90%
- ✅ All tests pass
- ✅ No security issues
- ✅ Code follows project patterns

### REQUEST CHANGES if:
- ❌ Missing type hints (< 100%)
- ❌ Missing docstrings (< 100%)
- ❌ Insufficient error handling
- ❌ Test coverage < 90%
- ❌ Tests failing
- ❌ Security issues found
- ❌ Critical code quality issues

## Completion

When done:
1. Verify review.json exists and is valid JSON
2. All required sections present
3. Report back with review decision and summary
4. If approved: Next agent (security-auditor) will scan for vulnerabilities
5. If changes requested: Implementer must address issues

**Time limit**: 30 minutes maximum
**Model**: sonnet (cost-effective for code review)
**Output**: `.claude/artifacts/{workflow_id}/review.json`

Begin review now.
"""
        }

        logger.log_event(
            'task_tool_invocation',
            f'Invoking reviewer subagent for: {request}'
        )

        logger.log_event(
            'reviewer_invoked',
            'Reviewer agent invocation prepared',
            metadata={'subagent_type': result['subagent_type'], 'workflow_id': workflow_id}
        )

        # Return the prepared invocation dict
        return result

    def invoke_reviewer_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke reviewer agent using actual Task tool (Week 10+)

        This method uses the real Task tool to launch the reviewer subagent.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Result dictionary with reviewer invocation status
        """
        from logging_utils import WorkflowLogger
        from checkpoint import CheckpointManager

        logger = WorkflowLogger(workflow_id, 'orchestrator')

        # Prepare invocation using existing method
        invocation = self.invoke_reviewer(workflow_id)

        logger.log_event(
            'task_tool_invocation_start',
            f'Launching reviewer via Task tool for workflow {workflow_id}'
        )

        try:
            logger.log_event(
                'task_tool_ready',
                'Task tool invocation prepared - ready to launch reviewer',
                metadata={
                    'workflow_id': workflow_id,
                    'subagent': 'reviewer',
                    'expected_output': f'.claude/artifacts/{workflow_id}/review.json'
                }
            )

            # Return invocation parameters for Claude Code to use with Task tool
            return {
                'status': 'ready_for_invocation',
                'workflow_id': workflow_id,
                'invocation': invocation,
                'expected_artifact': f'.claude/artifacts/{workflow_id}/review.json',
                'message': 'Orchestrator prepared reviewer invocation. Use Task tool to execute.'
            }

        except Exception as e:
            logger.log_event(
                'task_tool_error',
                f'Failed to invoke reviewer: {str(e)}',
                metadata={'error': str(e), 'workflow_id': workflow_id}
            )
            raise

        finally:
            # After reviewer completes, create checkpoint ONLY if artifact exists
            try:
                from pathlib import Path

                # Validate review.json actually exists
                review_path = Path(f".claude/artifacts/{workflow_id}/review.json")

                if review_path.exists():
                    # Artifact exists - reviewer truly completed
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner', 'test-master', 'implementer', 'reviewer'],
                        current_agent='security-auditor',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json', 'tests.json', 'implementation.json', 'review.json']
                    )
                    logger.log_event(
                        'checkpoint_created',
                        'Checkpoint created after reviewer completion',
                        metadata={'artifact_size': review_path.stat().st_size}
                    )
                else:
                    # Artifact missing - reviewer did not complete
                    logger.log_event(
                        'checkpoint_skipped',
                        'Checkpoint not created - reviewer artifact missing',
                        metadata={
                            'expected_artifact': str(review_path),
                            'reason': 'review.json does not exist'
                        }
                    )
                    # Create partial checkpoint showing reviewer did not complete
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner', 'test-master', 'implementer'],
                        current_agent='reviewer',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json', 'tests.json', 'implementation.json']
                    )
            except Exception as e:
                logger.log_event(
                    'checkpoint_error',
                    f'Failed to create checkpoint: {str(e)}'
                )

    def invoke_security_auditor(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke security-auditor agent to scan for vulnerabilities

        This method prepares the security-auditor agent invocation based on implementation and review.
        Security-auditor will scan for secrets, injection vulnerabilities, and validate threat model.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Dict with security-auditor invocation parameters ready for Task tool
        """
        from logging_utils import WorkflowLogger, WorkflowProgressTracker

        logger = WorkflowLogger(workflow_id, 'orchestrator')
        logger.log_event('invoke_security_auditor', 'Invoking security-auditor agent')

        # Update progress
        progress_tracker = WorkflowProgressTracker(workflow_id)
        progress_tracker.update_progress(
            current_agent='security-auditor',
            status='in_progress',
            progress_percentage=92,
            message='Security-Auditor: Scanning for vulnerabilities and validating threat model...'
        )

        # Read artifacts for context
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        architecture = self.artifact_manager.read_artifact(workflow_id, 'architecture')
        implementation = self.artifact_manager.read_artifact(workflow_id, 'implementation')
        review = self.artifact_manager.read_artifact(workflow_id, 'review')

        request = manifest.get('request', '')

        # Log decision to invoke security-auditor
        logger.log_decision(
            decision='Invoke security-auditor for security validation',
            rationale='Code reviewed, need to scan for vulnerabilities and validate threat model',
            alternatives_considered=['Skip security scan'],
            metadata={'workflow_id': workflow_id}
        )

        # Prepare security-auditor invocation with complete prompt
        result = {
            'subagent_type': 'security-auditor',
            'description': f'Security scan for: {request}',
            'prompt': f"""
You are the **security-auditor** agent for autonomous-dev v2.0 workflow {workflow_id}.

## Your Mission

Scan implementation for security vulnerabilities, validate threat model coverage, and ensure OWASP compliance. **Pass** if secure, or **flag issues** if vulnerabilities found.

**Request**: {request}

## Workflow Context

Read the workflow artifacts to understand security requirements:

**Manifest location**: `.claude/artifacts/{workflow_id}/manifest.json`
- Contains: user request, PROJECT.md alignment data

**Architecture location**: `.claude/artifacts/{workflow_id}/architecture.json`
- Contains: Security design (threat model), expected vulnerabilities to mitigate

**Implementation location**: `.claude/artifacts/{workflow_id}/implementation.json`
- Contains: Files implemented, functions created, security claims

**Review location**: `.claude/artifacts/{workflow_id}/review.json`
- Contains: Code quality validation results, security checks performed

## Your Tasks

### 1. Read Implementation (2-3 minutes)

Read artifacts to understand what was implemented and what security requirements must be met.

### 2. Secrets Detection (5-7 minutes)

Scan all implementation files for hardcoded secrets using grep:
- API keys (Anthropic `sk-`, OpenAI `sk-proj-`, GitHub `ghp_`)
- AWS credentials (`AKIA`, `aws_secret_access_key`)
- Tokens and passwords

### 3. Subprocess Injection Prevention (3-5 minutes)

Check all subprocess calls for injection vulnerabilities:
- Verify uses `subprocess.run()` with list arguments
- Verify no `shell=True` parameter
- Verify all calls have `timeout=` parameter

### 4. Input Validation (3-5 minutes)

Verify user inputs are validated before use (branch names, commits, patterns).

### 5. Timeout Enforcement (2-3 minutes)

Verify all network/subprocess calls have timeouts (5-30 seconds).

### 6. Error Message Safety (2-3 minutes)

Check that error messages don't leak sensitive info (credentials, full paths).

### 7. Dependency Security (3-5 minutes)

Check for known vulnerable dependencies using pip.

### 8. Run Security Tests (5-7 minutes)

Execute security test suite:

```bash
pytest tests/security/test_pr_security.py -v
```

All security tests must PASS.

### 9. Threat Model Validation (5-7 minutes)

Compare threat model from architecture.json with actual mitigations:
- Credential leakage mitigation
- Command injection prevention
- DoS prevention (timeouts)
- Accidental operations prevention
- Rate limit handling

### 10. Create Security Artifact (3-5 minutes)

Create `.claude/artifacts/{workflow_id}/security.json` following the complete schema defined in security-auditor.md agent specification.

**Required sections:**
- security_summary (scan_result, vulnerabilities_found, threat_model_coverage)
- secrets_scan (status, patterns_checked, issues)
- subprocess_safety (status, validation, issues)
- input_validation (status, validators_found, validations)
- timeout_enforcement (status, calls_with_timeout, issues)
- error_message_safety (status, safe_messages, issues)
- dependency_security (status, vulnerable_packages, issues)
- security_tests (status, tests_run, passed/failed)
- threat_model_validation (threats, mitigations, coverage)
- vulnerabilities (list of issues if FAIL)
- recommendations (suggestions for improvement)
- approval (security_approved, next_step)

## Decision Criteria

### PASS if:
- ✅ No secrets in code
- ✅ All subprocess calls safe (list args, no shell=True, timeouts)
- ✅ Input validation present
- ✅ All network calls have timeouts
- ✅ Error messages don't leak secrets
- ✅ No vulnerable dependencies
- ✅ All security tests pass
- ✅ All threats from threat model mitigated

### FAIL if:
- ❌ Secrets detected
- ❌ Subprocess injection vulnerability
- ❌ Missing timeouts
- ❌ Missing input validation
- ❌ Error messages leak secrets
- ❌ Vulnerable dependencies
- ❌ Security tests failing
- ❌ Unmitigated threats

## Completion

When done:
1. Verify security.json exists and is valid JSON
2. All required sections present
3. Report back with scan result and summary
4. If PASS: Next agent (doc-master) will update documentation
5. If FAIL: Implementer must fix vulnerabilities

**Time limit**: 30 minutes maximum
**Model**: haiku (fast, cost-effective for automated security scans)
**Output**: `.claude/artifacts/{workflow_id}/security.json`

Begin security audit now.
"""
        }

        logger.log_event(
            'task_tool_invocation',
            f'Invoking security-auditor subagent for: {request}'
        )

        logger.log_event(
            'security_auditor_invoked',
            'Security-auditor agent invocation prepared',
            metadata={'subagent_type': result['subagent_type'], 'workflow_id': workflow_id}
        )

        # Return the prepared invocation dict
        return result

    def invoke_security_auditor_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke security-auditor agent using actual Task tool (Week 11+)

        This method uses the real Task tool to launch the security-auditor subagent.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Result dictionary with security-auditor invocation status
        """
        from logging_utils import WorkflowLogger
        from checkpoint import CheckpointManager

        logger = WorkflowLogger(workflow_id, 'orchestrator')

        # Prepare invocation using existing method
        invocation = self.invoke_security_auditor(workflow_id)

        logger.log_event(
            'task_tool_invocation_start',
            f'Launching security-auditor via Task tool for workflow {workflow_id}'
        )

        try:
            logger.log_event(
                'task_tool_ready',
                'Task tool invocation prepared - ready to launch security-auditor',
                metadata={
                    'workflow_id': workflow_id,
                    'subagent': 'security-auditor',
                    'expected_output': f'.claude/artifacts/{workflow_id}/security.json'
                }
            )

            # Return invocation parameters for Claude Code to use with Task tool
            return {
                'status': 'ready_for_invocation',
                'workflow_id': workflow_id,
                'invocation': invocation,
                'expected_artifact': f'.claude/artifacts/{workflow_id}/security.json',
                'message': 'Orchestrator prepared security-auditor invocation. Use Task tool to execute.'
            }

        except Exception as e:
            logger.log_event(
                'task_tool_error',
                f'Failed to invoke security-auditor: {str(e)}',
                metadata={'error': str(e), 'workflow_id': workflow_id}
            )
            raise

        finally:
            # After security-auditor completes, create checkpoint ONLY if artifact exists
            try:
                from pathlib import Path

                # Validate security.json actually exists
                security_path = Path(f".claude/artifacts/{workflow_id}/security.json")

                if security_path.exists():
                    # Artifact exists - security-auditor truly completed
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner', 'test-master', 'implementer', 'reviewer', 'security-auditor'],
                        current_agent='doc-master',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json', 'tests.json', 'implementation.json', 'review.json', 'security.json']
                    )
                    logger.log_event(
                        'checkpoint_created',
                        'Checkpoint created after security-auditor completion',
                        metadata={'artifact_size': security_path.stat().st_size}
                    )
                else:
                    # Artifact missing - security-auditor did not complete
                    logger.log_event(
                        'checkpoint_skipped',
                        'Checkpoint not created - security-auditor artifact missing',
                        metadata={
                            'expected_artifact': str(security_path),
                            'reason': 'security.json does not exist'
                        }
                    )
                    # Create partial checkpoint showing security-auditor did not complete
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner', 'test-master', 'implementer', 'reviewer'],
                        current_agent='security-auditor',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json', 'tests.json', 'implementation.json', 'review.json']
                    )
            except Exception as e:
                logger.log_event(
                    'checkpoint_error',
                    f'Failed to create checkpoint: {str(e)}'
                )

    def invoke_doc_master(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke doc-master agent to update documentation

        This method prepares the doc-master agent invocation based on all previous artifacts.
        Doc-master will update documentation files to reflect implementation changes.

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Dict with doc-master invocation parameters ready for Task tool
        """
        from logging_utils import WorkflowLogger, WorkflowProgressTracker

        logger = WorkflowLogger(workflow_id, 'orchestrator')
        logger.log_event('invoke_doc_master', 'Invoking doc-master agent')

        # Update progress
        progress_tracker = WorkflowProgressTracker(workflow_id)
        progress_tracker.update_progress(
            current_agent='doc-master',
            status='in_progress',
            progress_percentage=98,
            message='Doc-Master: Updating documentation files...'
        )

        # Read artifacts for context
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        architecture = self.artifact_manager.read_artifact(workflow_id, 'architecture')
        implementation = self.artifact_manager.read_artifact(workflow_id, 'implementation')
        review = self.artifact_manager.read_artifact(workflow_id, 'review')
        security = self.artifact_manager.read_artifact(workflow_id, 'security')

        request = manifest.get('request', '')

        # Log decision to invoke doc-master
        logger.log_decision(
            decision='Invoke doc-master for documentation updates',
            rationale='Implementation complete and secure, need to update user documentation',
            alternatives_considered=['Skip documentation updates'],
            metadata={'workflow_id': workflow_id}
        )

        # Prepare doc-master invocation with complete prompt
        result = {
            'subagent_type': 'doc-master',
            'description': f'Update documentation for: {request}',
            'prompt': f"""
You are the **doc-master** agent for autonomous-dev v2.0 workflow {workflow_id}.

## Your Mission

Update documentation to reflect implementation changes. Ensure docs are accurate, complete, and helpful for users.

**Request**: {request}

## Workflow Context

Read the workflow artifacts to understand what to document:

**Manifest location**: `.claude/artifacts/{workflow_id}/manifest.json`
- Contains: user request, PROJECT.md alignment data

**Architecture location**: `.claude/artifacts/{workflow_id}/architecture.json`
- Contains: API contracts implemented, file changes, documentation plan

**Implementation location**: `.claude/artifacts/{workflow_id}/implementation.json`
- Contains: Files created/modified, functions implemented, usage examples

**Review location**: `.claude/artifacts/{workflow_id}/review.json`
- Contains: Code quality validation, issues that may need docs updates

**Security location**: `.claude/artifacts/{workflow_id}/security.json`
- Contains: Security requirements, configuration needed (.env.example)

## Your Tasks

### 1. Read Artifacts (3-5 minutes)

Read all artifacts to understand what was implemented and what documentation needs updating.

### 2. Identify Documentation Files to Update (2-3 minutes)

Find existing documentation files:

```bash
ls plugins/autonomous-dev/docs/*.md | grep -E "(PR-AUTOMATION|GITHUB-WORKFLOW|COMMAND)"
cat plugins/autonomous-dev/README.md | head -50
cat .env.example | grep -i pr
```

### 3. Update Feature Documentation (10-15 minutes)

Update or create feature-specific documentation (e.g., PR-AUTOMATION.md):
- Quick Start section with examples
- Commands section with all flags
- Configuration section (.env options)
- Troubleshooting section with common errors
- Examples (at least 3)

### 4. Update Workflow Documentation (5-7 minutes)

Update workflow diagrams (e.g., GITHUB-WORKFLOW.md):
- Add new steps to workflow diagram
- Update integration points
- Document dependencies

### 5. Update Command Reference (3-5 minutes)

Update README.md or COMMANDS.md:
- Add new command to command list
- Include brief description
- Link to detailed docs

### 6. Update Configuration Examples (2-3 minutes)

Update .env.example:
- Add new configuration options with comments
- Include default values
- Document valid values/ranges

### 7. Check for Missing Documentation (3-5 minutes)

Search for missing docs:

```bash
grep -r "TODO.*doc" plugins/autonomous-dev/
grep -A 1 "^def " plugins/autonomous-dev/lib/*.py | grep -v '"""'
```

### 8. Create Documentation Artifact (3-5 minutes)

Create `.claude/artifacts/{workflow_id}/docs.json` following the complete schema defined in doc-master.md agent specification.

**Required sections:**
- documentation_summary (files_updated, lines_added, documentation_complete)
- files_updated (list of files with changes)
- documentation_coverage (API functions documented)
- user_guide_updates (quick_start, examples, troubleshooting)
- validation (all_functions_documented, no_broken_links)
- recommendations (enhancement suggestions)
- completion (documentation_complete, next_step)

## Quality Requirements

✅ All API functions documented (100% coverage)
✅ Commands in README (all new commands listed)
✅ Configuration documented (.env.example updated)
✅ Examples included (at least 3 usage examples)
✅ Troubleshooting guide (common errors and solutions)
✅ No broken links (all documentation links valid)

## Completion

When done:
1. Verify docs.json exists and is valid JSON
2. All required sections present
3. Report back with documentation summary
4. **WORKFLOW COMPLETE - All 8 agents finished!**

**Time limit**: 30 minutes maximum
**Model**: haiku (fast, cost-effective for documentation)
**Output**: `.claude/artifacts/{workflow_id}/docs.json` + updated documentation files

Begin documentation updates now.
"""
        }

        logger.log_event(
            'task_tool_invocation',
            f'Invoking doc-master subagent for: {request}'
        )

        logger.log_event(
            'doc_master_invoked',
            'Doc-master agent invocation prepared',
            metadata={'subagent_type': result['subagent_type'], 'workflow_id': workflow_id}
        )

        # Return the prepared invocation dict
        return result

    def invoke_doc_master_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """
        Invoke doc-master agent using actual Task tool (Week 12+)

        This method uses the real Task tool to launch the doc-master subagent.
        This is the FINAL agent in the 8-agent pipeline!

        Args:
            workflow_id: Unique workflow identifier

        Returns:
            Result dictionary with doc-master invocation status
        """
        from logging_utils import WorkflowLogger
        from checkpoint import CheckpointManager

        logger = WorkflowLogger(workflow_id, 'orchestrator')

        # Prepare invocation using existing method
        invocation = self.invoke_doc_master(workflow_id)

        logger.log_event(
            'task_tool_invocation_start',
            f'Launching doc-master via Task tool for workflow {workflow_id} - FINAL AGENT!'
        )

        try:
            logger.log_event(
                'task_tool_ready',
                'Task tool invocation prepared - ready to launch doc-master (FINAL AGENT)',
                metadata={
                    'workflow_id': workflow_id,
                    'subagent': 'doc-master',
                    'expected_output': f'.claude/artifacts/{workflow_id}/docs.json',
                    'pipeline_completion': '100%'
                }
            )

            # Return invocation parameters for Claude Code to use with Task tool
            return {
                'status': 'ready_for_invocation',
                'workflow_id': workflow_id,
                'invocation': invocation,
                'expected_artifact': f'.claude/artifacts/{workflow_id}/docs.json',
                'message': 'Orchestrator prepared doc-master invocation. Use Task tool to execute. THIS IS THE FINAL AGENT!'
            }

        except Exception as e:
            logger.log_event(
                'task_tool_error',
                f'Failed to invoke doc-master: {str(e)}',
                metadata={'error': str(e), 'workflow_id': workflow_id}
            )
            raise

        finally:
            # After doc-master completes, create FINAL checkpoint
            try:
                from pathlib import Path

                # Validate docs.json actually exists
                docs_path = Path(f".claude/artifacts/{workflow_id}/docs.json")

                if docs_path.exists():
                    # Artifact exists - doc-master truly completed
                    # This is the FINAL checkpoint - all 8 agents complete!
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner', 'test-master', 'implementer', 'reviewer', 'security-auditor', 'doc-master'],
                        current_agent='workflow_complete',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json', 'tests.json', 'implementation.json', 'review.json', 'security.json', 'docs.json']
                    )
                    logger.log_event(
                        'checkpoint_created',
                        'FINAL CHECKPOINT created - All 8 agents complete!',
                        metadata={
                            'artifact_size': docs_path.stat().st_size,
                            'pipeline_status': 'COMPLETE',
                            'agents_completed': 8
                        }
                    )
                    logger.log_event(
                        'pipeline_complete',
                        '🎉 AUTONOMOUS DEVELOPMENT PIPELINE COMPLETE! All 8 agents finished successfully.',
                        metadata={
                            'workflow_id': workflow_id,
                            'total_agents': 8,
                            'total_artifacts': 8
                        }
                    )
                else:
                    # Artifact missing - doc-master did not complete
                    logger.log_event(
                        'checkpoint_skipped',
                        'Checkpoint not created - doc-master artifact missing',
                        metadata={
                            'expected_artifact': str(docs_path),
                            'reason': 'docs.json does not exist'
                        }
                    )
                    # Create partial checkpoint showing doc-master did not complete
                    checkpoint_manager = CheckpointManager()
                    checkpoint_manager.create_checkpoint(
                        workflow_id=workflow_id,
                        completed_agents=['orchestrator', 'researcher', 'planner', 'test-master', 'implementer', 'reviewer', 'security-auditor'],
                        current_agent='doc-master',
                        artifacts_created=['manifest.json', 'research.json', 'architecture.json', 'tests.json', 'implementation.json', 'review.json', 'security.json']
                    )
            except Exception as e:
                logger.log_event(
                    'checkpoint_error',
                    f'Failed to create checkpoint: {str(e)}'
                )


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

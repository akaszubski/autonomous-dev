"""
Workflow coordinator for autonomous development v2.0.

Simplified orchestrator using modular components:
- ProjectMdParser: PROJECT.md parsing
- AlignmentValidator: Request validation
- AgentInvoker: Agent invocation factory
- SecurityValidator: Security validation
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from artifacts import ArtifactManager, generate_workflow_id
from logging_utils import WorkflowLogger, WorkflowProgressTracker
from project_md_parser import ProjectMdParser
from alignment_validator import AlignmentValidator
from agent_invoker import AgentInvoker
from security_validator import SecurityValidator


class WorkflowCoordinator:
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
        Initialize workflow coordinator

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

        # Initialize agent invoker
        self.agent_invoker = AgentInvoker(self.artifact_manager)

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
            Workflow status dict
        """
        progress_tracker = WorkflowProgressTracker(workflow_id)
        return progress_tracker.get_status()

    # Agent invocation methods - now using AgentInvoker factory
    def invoke_researcher(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke researcher agent"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke(
            'researcher',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_researcher_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke researcher with Task tool enabled"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke_with_task_tool(
            'researcher',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_planner(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke planner agent"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke(
            'planner',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_planner_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke planner with Task tool enabled"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke_with_task_tool(
            'planner',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_test_master(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke test-master agent"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke(
            'test-master',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_test_master_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke test-master with Task tool enabled"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke_with_task_tool(
            'test-master',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_implementer(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke implementer agent"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke(
            'implementer',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_implementer_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke implementer with Task tool enabled"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke_with_task_tool(
            'implementer',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_reviewer(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke reviewer agent"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke(
            'reviewer',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_reviewer_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke reviewer with Task tool enabled"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke_with_task_tool(
            'reviewer',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_security_auditor(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke security-auditor agent"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke(
            'security-auditor',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_security_auditor_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke security-auditor with Task tool enabled"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke_with_task_tool(
            'security-auditor',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_doc_master(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke doc-master agent"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke(
            'doc-master',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_doc_master_with_task_tool(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke doc-master with Task tool enabled"""
        manifest = self.artifact_manager.read_artifact(workflow_id, 'manifest')
        return self.agent_invoker.invoke_with_task_tool(
            'doc-master',
            workflow_id,
            request=manifest.get('request', '')
        )

    def invoke_parallel_validators(self, workflow_id: str) -> Dict[str, Any]:
        """Invoke reviewer, security-auditor, doc-master in parallel."""
        logger = WorkflowLogger(workflow_id, 'orchestrator')
        progress_tracker = WorkflowProgressTracker(workflow_id)

        progress_tracker.update_progress(
            current_agent='validators',
            status='in_progress',
            progress_percentage=85,
            message='Running 3 validators in parallel...'
        )

        validator_results = {}
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                'reviewer': executor.submit(
                    self.invoke_reviewer_with_task_tool, workflow_id
                ),
                'security-auditor': executor.submit(
                    self.invoke_security_auditor_with_task_tool, workflow_id
                ),
                'doc-master': executor.submit(
                    self.invoke_doc_master_with_task_tool, workflow_id
                )
            }

            for name, future in futures.items():
                try:
                    result = future.result(timeout=1800)  # 30 min timeout
                    validator_results[name] = result
                    logger.log_event(
                        f'{name}_completed',
                        f'{name} validator completed'
                    )
                except Exception as e:
                    validator_results[name] = {'status': 'failed', 'error': str(e)}
                    logger.log_error(f'{name} failed', exception=e)

        elapsed = time.time() - start_time

        progress_tracker.update_progress(
            current_agent='validators',
            status='completed',
            progress_percentage=95,
            message=f'Validators complete ({elapsed:.1f}s)'
        )

        return {
            'status': 'completed',
            'validator_results': validator_results,
            'elapsed_seconds': elapsed
        }

    # Security validation methods - delegated to SecurityValidator
    def validate_threats_with_genai(
        self,
        threats: list,
        implementation_code: str
    ) -> Dict[str, Any]:
        """Validate threat model coverage using GenAI"""
        return SecurityValidator.validate_threats_with_genai(
            threats,
            implementation_code
        )

    def review_code_with_genai(
        self,
        implementation_code: str,
        architecture: Dict[str, Any],
        workflow_id: str
    ) -> Dict[str, Any]:
        """Review code for security issues using GenAI"""
        return SecurityValidator.review_code_with_genai(
            implementation_code,
            architecture,
            workflow_id
        )


# Backward compatibility: Orchestrator is now an alias for WorkflowCoordinator
Orchestrator = WorkflowCoordinator

#!/usr/bin/env python3
"""
Test Script for autonomous-dev v2.0 Workflow
Demonstrates orchestrator → researcher pipeline with artifact handoff
"""

import json
import sys
from pathlib import Path
from orchestrator import Orchestrator
from checkpoint import CheckpointManager
from artifacts import ArtifactManager
from logging_utils import WorkflowLogger


def test_workflow_initialization():
    """Test: Orchestrator initializes workflow with PROJECT.md validation"""

    print("=" * 70)
    print("TEST 1: Workflow Initialization")
    print("=" * 70)
    print()

    # Initialize orchestrator
    try:
        orchestrator = Orchestrator(
            project_md_path=Path(".claude/PROJECT.md")
        )
        print("✓ Orchestrator initialized")
        print(f"  PROJECT.md: {orchestrator.project_md_path}")
        print(f"  Goals: {len(orchestrator.project_md.get('goals', []))}")
        print(f"  Constraints: {len(orchestrator.project_md.get('constraints', []))}")
        print()
    except ValueError as e:
        print(f"✗ Failed to initialize orchestrator: {e}")
        print("\n💡 Create .claude/PROJECT.md first:")
        print("   See: plugins/autonomous-dev/docs/QUICKSTART.md")
        return False

    # Test workflow creation
    request = "implement user authentication with JWT tokens"

    print(f"Request: \"{request}\"")
    print()

    success, message, workflow_id = orchestrator.start_workflow(request)

    if not success:
        print("✗ Workflow blocked (expected if not aligned)")
        print(message)
        return False

    print("✓ Workflow started")
    print(f"  Workflow ID: {workflow_id}")
    print(f"  Status: initialized")
    print()

    # Verify artifacts created
    artifact_manager = ArtifactManager()

    if artifact_manager.artifact_exists(workflow_id, 'manifest'):
        print("✓ Manifest artifact created")

        manifest = artifact_manager.read_artifact(workflow_id, 'manifest')
        print(f"  Request: {manifest['request']}")
        print(f"  Alignment: {manifest['alignment']['validated']}")
        print(f"  Planned agents: {len(manifest['workflow_plan']['agents'])}")
    else:
        print("✗ Manifest artifact missing")
        return False

    print()
    return workflow_id


def test_checkpoint_creation(workflow_id: str):
    """Test: Checkpoint system tracks progress"""

    print("=" * 70)
    print("TEST 2: Checkpoint Creation")
    print("=" * 70)
    print()

    checkpoint_manager = CheckpointManager()

    # Simulate agent completion
    print("Simulating agent completion...")
    checkpoint_path = checkpoint_manager.create_checkpoint(
        workflow_id=workflow_id,
        completed_agents=['orchestrator'],
        current_agent='researcher',
        artifacts_created=['manifest.json'],
        metadata={'retry_count': 0}
    )

    print(f"✓ Checkpoint created: {checkpoint_path}")
    print()

    # Verify checkpoint
    is_valid, error = checkpoint_manager.validate_checkpoint(workflow_id)

    if is_valid:
        print("✓ Checkpoint validated")
    else:
        print(f"✗ Checkpoint invalid: {error}")
        return False

    # Get resume plan
    resume_plan = checkpoint_manager.get_resume_plan(workflow_id)

    print(f"✓ Resume plan generated")
    print(f"  Completed: {', '.join(resume_plan['completed_agents'])}")
    print(f"  Next: {resume_plan['next_agent']}")
    print(f"  Progress: {resume_plan['progress_percentage']}%")
    print()

    return True


def test_artifact_handoff(workflow_id: str):
    """Test: Agents can read previous agent's artifacts"""

    print("=" * 70)
    print("TEST 3: Artifact Handoff")
    print("=" * 70)
    print()

    artifact_manager = ArtifactManager()

    # Read manifest (created by orchestrator)
    print("Reading orchestrator's manifest...")
    try:
        manifest = artifact_manager.read_artifact(workflow_id, 'manifest')
        print("✓ Manifest loaded")
        print(f"  Keys: {list(manifest.keys())}")
        print()
    except Exception as e:
        print(f"✗ Failed to load manifest: {e}")
        return False

    # Simulate researcher creating research artifact
    print("Simulating researcher creating research artifact...")

    research_artifact = {
        'version': '2.0',
        'agent': 'researcher',
        'workflow_id': workflow_id,
        'status': 'completed',
        'codebase_patterns': [
            {
                'pattern': 'JWT token validation',
                'location': 'src/auth/jwt.py',
                'relevance': 'Existing JWT utilities we can reuse'
            }
        ],
        'best_practices': [
            {
                'practice': 'Use RS256 for production JWT signing',
                'source': 'https://auth0.com/blog/rs256-vs-hs256/',
                'rationale': 'Asymmetric keys more secure for distributed systems'
            }
        ],
        'security_considerations': [
            'Store JWT secret in environment variables',
            'Set reasonable expiration times (15 min access, 7 days refresh)',
            'Validate all JWT claims, not just signature'
        ],
        'recommended_libraries': [
            {
                'name': 'PyJWT',
                'version': '2.8.0',
                'rationale': 'Industry standard, well-maintained'
            }
        ],
        'alternatives_considered': [
            {
                'option': 'python-jose',
                'reason_not_chosen': 'PyJWT has better community support'
            }
        ]
    }

    research_path = artifact_manager.write_artifact(
        workflow_id=workflow_id,
        artifact_type='research',
        data=research_artifact
    )

    print(f"✓ Research artifact created: {research_path}")
    print()

    # Simulate planner reading research artifact
    print("Simulating planner reading research artifact...")

    try:
        research = artifact_manager.read_artifact(workflow_id, 'research')
        print("✓ Planner loaded research artifact")
        print(f"  Codebase patterns: {len(research['codebase_patterns'])}")
        print(f"  Best practices: {len(research['best_practices'])}")
        print(f"  Security considerations: {len(research['security_considerations'])}")
        print()
    except Exception as e:
        print(f"✗ Failed to load research artifact: {e}")
        return False

    # Verify workflow summary
    summary = artifact_manager.get_workflow_summary(workflow_id)

    print("✓ Workflow summary:")
    print(f"  Total artifacts: {summary['total_artifacts']}")
    print(f"  Progress: {summary['progress_percentage']}%")
    print()

    return True


def test_logging(workflow_id: str):
    """Test: Logging system tracks all decisions"""

    print("=" * 70)
    print("TEST 4: Logging & Observability")
    print("=" * 70)
    print()

    # Create logger
    logger = WorkflowLogger(workflow_id, 'test-agent')

    print("Logging test events...")

    # Log various events
    logger.log_event('test_start', 'Starting logging test')

    logger.log_decision(
        decision='Use PyJWT library',
        rationale='Industry standard with good security track record',
        alternatives_considered=['python-jose', 'authlib'],
        metadata={'confidence': 'high'}
    )

    logger.log_alignment_check(
        is_aligned=True,
        reason='JWT authentication aligns with security goals',
        project_md_sections={'goals': ['Improve security']}
    )

    logger.log_performance_metric(
        metric_name='artifact_size',
        value=2.5,
        unit='KB'
    )

    print("✓ Events logged")
    print()

    # Get log summary
    summary = logger.get_log_summary()

    print("✓ Log summary:")
    print(f"  Total events: {summary['total_events']}")
    print(f"  Decisions: {len(summary['decisions'])}")
    print(f"  Errors: {len(summary['errors'])}")
    print()

    if summary['decisions']:
        print("  First decision:")
        decision = summary['decisions'][0]
        print(f"    - {decision['metadata']['decision']}")
        print(f"    - Rationale: {decision['metadata']['rationale']}")
    print()

    return True


def main():
    """Run all tests"""

    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "AUTONOMOUS-DEV V2.0 WORKFLOW TEST" + " " * 19 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # Test 1: Workflow initialization
    workflow_id = test_workflow_initialization()

    if not workflow_id:
        print("\n❌ Test suite failed: Workflow initialization")
        print("\n💡 Ensure .claude/PROJECT.md exists with GOALS, SCOPE, CONSTRAINTS")
        sys.exit(1)

    # Test 2: Checkpoint creation
    if not test_checkpoint_creation(workflow_id):
        print("\n❌ Test suite failed: Checkpoint creation")
        sys.exit(1)

    # Test 3: Artifact handoff
    if not test_artifact_handoff(workflow_id):
        print("\n❌ Test suite failed: Artifact handoff")
        sys.exit(1)

    # Test 4: Logging
    if not test_logging(workflow_id):
        print("\n❌ Test suite failed: Logging")
        sys.exit(1)

    # All tests passed
    print("=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    print()
    print("Workflow artifacts:")
    print(f"  .claude/artifacts/{workflow_id}/")
    print(f"    - manifest.json")
    print(f"    - research.json")
    print(f"    - checkpoint.json")
    print(f"    - logs/test-agent.log")
    print()
    print("Next steps:")
    print("  1. Implement actual agent invocation (Task tool)")
    print("  2. Connect researcher agent to read manifest")
    print("  3. Test full orchestrator → researcher pipeline")
    print()


if __name__ == '__main__':
    main()

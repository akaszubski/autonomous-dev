#!/usr/bin/env python3
"""
Week 6: First Real Agent Execution Test

This test actually invokes the Task tool and runs the researcher agent.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "plugins/autonomous-dev/lib"))

from orchestrator import Orchestrator
from artifacts import ArtifactManager
from checkpoint import CheckpointManager


def test_first_real_execution():
    """Test real researcher agent execution"""

    print("=" * 70)
    print("WEEK 6: First Real Agent Execution Test")
    print("=" * 70)
    print()

    # Step 1: Create orchestrator
    print("Step 1: Initializing orchestrator...")
    orchestrator = Orchestrator()
    print("✓ Orchestrator initialized")
    print()

    # Step 2: Create workflow (must align with autonomous-dev's actual PROJECT.md)
    print("Step 2: Creating workflow...")
    success, message, workflow_id = orchestrator.start_workflow(
        "implement GitHub PR automation for autonomous development workflow"
    )

    if not success:
        print(f"✗ Failed to create workflow: {message}")
        return False

    print(f"✓ Workflow created: {workflow_id}")
    print()

    # Step 3: Invoke researcher (THIS WILL ACTUALLY RUN)
    print("Step 3: Invoking researcher agent...")
    print("NOTE: This will take 5-15 minutes")
    print("The researcher will:")
    print("  - Search codebase for GitHub/PR patterns")
    print("  - Perform web research (3-5 queries)")
    print("  - Fetch best practices from 5+ sources")
    print("  - Create research.json artifact")
    print()

    try:
        result = orchestrator.invoke_researcher_with_task_tool(workflow_id)

        print("✓ Researcher completed!")
        print(f"  Status: {result['status']}")
        print(f"  Artifact: {result['research_artifact']}")
        print()

        # Step 4: Validate research.json
        print("Step 4: Validating research artifact...")

        summary = result['research_summary']
        print(f"  Codebase patterns: {summary['codebase_patterns']}")
        print(f"  Best practices: {summary['best_practices']}")
        print(f"  Security considerations: {summary['security_considerations']}")
        print(f"  Recommended libraries: {summary['recommended_libraries']}")
        print()

        # Minimum quality checks
        if summary['best_practices'] < 3:
            print("⚠ Warning: Expected at least 3 best practices")

        if summary['security_considerations'] < 3:
            print("⚠ Warning: Expected at least 3 security considerations")

        # Step 5: Verify checkpoint
        print("Step 5: Verifying checkpoint...")
        checkpoint_manager = CheckpointManager()
        checkpoint = checkpoint_manager.load_checkpoint(workflow_id)

        print(f"  Completed agents: {checkpoint['completed_agents']}")
        print(f"  Current agent: {checkpoint['current_agent']}")
        print(f"  Progress: {checkpoint_manager.get_resume_plan(workflow_id)['progress_percentage']}%")
        print()

        # Step 6: Read full research artifact
        print("Step 6: Reading full research artifact...")
        artifact_manager = ArtifactManager()
        research = artifact_manager.read_artifact(workflow_id, 'research')

        print("Research Artifact Contents:")
        print(f"  Version: {research['version']}")
        print(f"  Agent: {research['agent']}")
        print(f"  Status: {research['status']}")
        print()

        if research.get('best_practices'):
            print("Best Practices Found:")
            for i, bp in enumerate(research['best_practices'][:3], 1):
                print(f"  {i}. {bp['practice']}")
                print(f"     Source: {bp['source']}")
                print(f"     Rationale: {bp['rationale']}")
                print()

        print("=" * 70)
        print("✅ WEEK 6 TEST PASSED - Real agent execution successful!")
        print("=" * 70)
        print()

        return True

    except Exception as e:
        print(f"✗ Researcher execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_first_real_execution()
    sys.exit(0 if success else 1)

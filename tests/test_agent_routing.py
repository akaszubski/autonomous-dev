#!/usr/bin/env python3
"""
Test agent routing - verifies Task tool invocation actually works
"""

import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))

from workflow_coordinator import WorkflowCoordinator
from artifacts import generate_workflow_id


def test_workflow_coordinator_initialization():
    """Test that WorkflowCoordinator initializes correctly"""
    print("Testing WorkflowCoordinator initialization...")

    try:
        # Create a test PROJECT.md
        test_project_md = Path("/tmp/test_PROJECT.md")
        test_project_md.write_text("""
# Test Project

## GOALS
- Build features quickly
- Maintain quality

## SCOPE

### In Scope
- Core features
- Tests

### Out of Scope
- Marketing website
- Social media

## CONSTRAINTS
- Python 3.8+
- PostgreSQL required
""")

        coordinator = WorkflowCoordinator(project_md_path=test_project_md)
        print("  ✓ WorkflowCoordinator initialized")
        print(f"  ✓ PROJECT.md loaded with {len(coordinator.project_md.get('goals', []))} goals")
        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def test_agent_invoker_exists():
    """Test that agent invoker is properly configured"""
    print("\nTesting AgentInvoker configuration...")

    try:
        test_project_md = Path("/tmp/test_PROJECT.md")
        coordinator = WorkflowCoordinator(project_md_path=test_project_md)

        # Check that all expected agents are configured
        expected_agents = [
            'researcher',
            'planner',
            'test-master',
            'implementer',
            'reviewer',
            'security-auditor',
            'doc-master'
        ]

        configs = coordinator.agent_invoker.AGENT_CONFIGS
        missing = [a for a in expected_agents if a not in configs]

        if missing:
            print(f"  ✗ Missing agents: {missing}")
            return False

        print(f"  ✓ All {len(expected_agents)} core agents configured")

        # Check that each agent has required config fields
        for agent in expected_agents:
            config = configs[agent]
            required_fields = ['mission', 'progress_pct', 'description_template']
            missing_fields = [f for f in required_fields if f not in config]

            if missing_fields:
                print(f"  ✗ Agent {agent} missing fields: {missing_fields}")
                return False

        print("  ✓ All agent configurations valid")
        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


def test_invoke_agent_method():
    """Test that invoke_agent method properly builds Task tool invocation"""
    print("\nTesting invoke_agent() method...")

    try:
        test_project_md = Path("/tmp/test_PROJECT.md")
        coordinator = WorkflowCoordinator(project_md_path=test_project_md)

        workflow_id = generate_workflow_id()

        # Test invoking researcher agent
        result = coordinator.invoke_agent(
            'researcher',
            workflow_id,
            request='add user authentication',
            project_md_path=str(test_project_md)
        )

        # Check result structure
        required_keys = ['agent', 'invocation', 'workflow_id', 'status']
        missing_keys = [k for k in required_keys if k not in result]

        if missing_keys:
            print(f"  ✗ Result missing keys: {missing_keys}")
            return False

        # Check invocation structure
        invocation = result['invocation']
        required_inv_keys = ['subagent_type', 'description', 'prompt']
        missing_inv_keys = [k for k in required_inv_keys if k not in invocation]

        if missing_inv_keys:
            print(f"  ✗ Invocation missing keys: {missing_inv_keys}")
            return False

        print(f"  ✓ invoke_agent() returns proper structure")
        print(f"  ✓ Agent: {result['agent']}")
        print(f"  ✓ Status: {result['status']}")
        print(f"  ✓ Invocation type: {invocation['subagent_type']}")

        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_alignment_check():
    """Test alignment validation logic"""
    print("\nTesting alignment validation...")

    try:
        test_project_md = Path("/tmp/test_PROJECT.md")
        coordinator = WorkflowCoordinator(project_md_path=test_project_md)

        # Test valid requests
        valid_requests = [
            'add user authentication',
            'implement caching layer',
            'create logging system'
        ]

        for req in valid_requests:
            result = coordinator._static_alignment_check(req)
            if not result:
                print(f"  ✗ Valid request rejected: {req}")
                return False

        print(f"  ✓ {len(valid_requests)} valid requests accepted")

        # Test invalid requests
        invalid_requests = [
            '',
            'x',
            'delete all data',
            'rm -rf /'
        ]

        for req in invalid_requests:
            result = coordinator._static_alignment_check(req)
            if result:
                print(f"  ✗ Invalid request accepted: {req}")
                return False

        print(f"  ✓ {len(invalid_requests)} invalid requests blocked")

        return True

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False


if __name__ == '__main__':
    print("=" * 70)
    print("AGENT ROUTING TEST SUITE")
    print("=" * 70)

    tests = [
        test_workflow_coordinator_initialization,
        test_agent_invoker_exists,
        test_invoke_agent_method,
        test_alignment_check,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"Test {test.__name__} crashed: {e}")
            results.append(False)

    print("\n" + "=" * 70)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 70)

    if all(results):
        print("\n✅ ALL TESTS PASSED - Agent routing infrastructure is ready!")
        print("\nNext steps:")
        print("1. Test /auto-implement command")
        print("2. Verify agents actually execute via Task tool")
        print("3. Check artifact creation")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED - Review errors above")
        sys.exit(1)

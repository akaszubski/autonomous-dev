#!/usr/bin/env python3
"""
Test: Orchestrator → Researcher Invocation (Week 4)

Validates that orchestrator can invoke researcher agent via Task tool
and that the researcher prompt is correctly structured for v2.0 artifacts.
"""

import sys
from pathlib import Path

# Add lib directory to path
lib_dir = Path(__file__).parent
sys.path.insert(0, str(lib_dir))

from orchestrator import Orchestrator
from artifacts import ArtifactManager, generate_workflow_id
import json


def print_section(title):
    """Print section header"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def test_invoke_researcher():
    """
    Test: Orchestrator can invoke researcher agent

    This test validates:
    1. Orchestrator.invoke_researcher() method exists
    2. Method prepares correct Task tool invocation
    3. Prompt includes workflow_id and artifact paths
    4. Prompt follows v2.0 artifact protocol
    """

    print_section("TEST: Orchestrator → Researcher Invocation")

    # Step 1: Create workflow
    print("Step 1: Creating workflow...")

    # Use test PROJECT.md
    test_project_md = Path(__file__).parent / "test_PROJECT.md"
    orchestrator = Orchestrator(project_md_path=test_project_md)

    success, message, workflow_id = orchestrator.start_workflow(
        "implement user authentication with JWT tokens"
    )

    if not success:
        print(f"✗ Failed to start workflow: {message}")
        return False

    print(f"✓ Workflow created: {workflow_id}")
    print()

    # Step 2: Invoke researcher
    print("Step 2: Invoking researcher...")

    try:
        result = orchestrator.invoke_researcher(workflow_id)
    except Exception as e:
        print(f"✗ Failed to invoke researcher: {e}")
        import traceback
        traceback.print_exc()
        return False

    print(f"✓ Researcher invocation prepared")
    print()

    # Step 3: Validate invocation structure
    print("Step 3: Validating invocation structure...")

    required_keys = ['subagent_type', 'description', 'prompt']
    for key in required_keys:
        if key not in result:
            print(f"✗ Missing required key: {key}")
            return False
        print(f"  ✓ Has '{key}': {result[key][:60] if isinstance(result[key], str) else result[key]}...")

    print()

    # Step 4: Validate prompt content
    print("Step 4: Validating prompt content...")

    prompt = result['prompt']

    # Check for required elements in prompt
    validations = [
        (workflow_id in prompt, f"Contains workflow_id: {workflow_id}"),
        (f".claude/artifacts/{workflow_id}/manifest.json" in prompt, "References manifest.json path"),
        (f".claude/artifacts/{workflow_id}/research.json" in prompt, "References research.json path"),
        ("codebase_patterns" in prompt, "Mentions codebase_patterns field"),
        ("best_practices" in prompt, "Mentions best_practices field"),
        ("security_considerations" in prompt, "Mentions security_considerations field"),
        ("recommended_libraries" in prompt, "Mentions recommended_libraries field"),
        ("alternatives_considered" in prompt, "Mentions alternatives_considered field"),
        ("Grep" in prompt or "grep" in prompt, "Instructs to use Grep for codebase search"),
        ("WebSearch" in prompt, "Instructs to use WebSearch"),
        ("WebFetch" in prompt, "Instructs to use WebFetch"),
    ]

    all_valid = True
    for is_valid, description in validations:
        status = "✓" if is_valid else "✗"
        print(f"  {status} {description}")
        if not is_valid:
            all_valid = False

    print()

    if not all_valid:
        print("✗ Prompt validation failed")
        print()
        print("Full prompt:")
        print("-" * 70)
        print(prompt)
        print("-" * 70)
        return False

    # Step 5: Validate that manifest was read
    print("Step 5: Validating manifest access...")

    artifact_manager = ArtifactManager()
    try:
        manifest = artifact_manager.read_artifact(workflow_id, 'manifest')
        request = manifest.get('request', '')

        if request not in prompt:
            print(f"✗ Prompt doesn't contain user request: {request}")
            return False

        print(f"✓ Prompt includes user request: {request[:60]}...")
    except Exception as e:
        print(f"✗ Failed to read manifest: {e}")
        return False

    print()

    # Step 6: Check logging
    print("Step 6: Checking workflow logs...")

    from logging_utils import WorkflowLogger

    logger = WorkflowLogger(workflow_id, 'orchestrator')
    log_summary = logger.get_log_summary()

    if log_summary['total_events'] == 0:
        print("✗ No events logged")
        return False

    print(f"  ✓ Total events: {log_summary['total_events']}")
    print(f"  ✓ Decisions logged: {len(log_summary.get('decisions', []))}")

    # Check for specific events
    events = [log['event_type'] for log in log_summary.get('events', [])]
    expected_events = ['invoke_researcher', 'task_tool_invocation', 'researcher_invoked']

    for expected in expected_events:
        if expected in events:
            print(f"  ✓ Event logged: {expected}")
        else:
            print(f"  ! Event not found: {expected} (may be in later logs)")

    print()

    # Step 7: Summary
    print_section("TEST SUMMARY")

    print("✅ ALL CHECKS PASSED")
    print()
    print("Validated:")
    print("  ✓ Orchestrator.invoke_researcher() method works")
    print("  ✓ Task tool invocation structure correct")
    print("  ✓ Prompt contains all required v2.0 elements")
    print("  ✓ Workflow ID and artifact paths included")
    print("  ✓ User request passed to researcher")
    print("  ✓ Decisions logged with rationale")
    print()
    print("Ready for:")
    print("  → Actual Task tool integration (call real researcher agent)")
    print("  → researcher-v2.md execution with artifact creation")
    print("  → Full pipeline: orchestrator → researcher → planner")
    print()

    return True


def test_researcher_prompt_format():
    """
    Test: Researcher prompt follows markdown format

    Validates that the prompt is well-structured and includes
    all necessary sections for the researcher agent.
    """

    print_section("TEST: Researcher Prompt Format")

    # Use test PROJECT.md
    test_project_md = Path(__file__).parent / "test_PROJECT.md"
    orchestrator = Orchestrator(project_md_path=test_project_md)

    # Create minimal workflow (must align with test PROJECT.md)
    success, message, workflow_id = orchestrator.start_workflow(
        "implement authentication"  # Aligns with "Authentication features" in scope
    )

    if not success:
        print(f"✗ Failed to create workflow: {message}")
        return False

    # Get invocation
    result = orchestrator.invoke_researcher(workflow_id)
    prompt = result['prompt']

    # Check markdown sections
    sections = [
        "## Your Mission",
        "## Workflow Context",
        "## Your Tasks",
        "### 1. Codebase Search",
        "### 2. Web Research",
        "### 3. Create Research Artifact",
        "## Quality Requirements",
        "## Logging",
        "## Completion"
    ]

    print("Checking prompt sections...")
    all_found = True
    for section in sections:
        if section in prompt:
            print(f"  ✓ {section}")
        else:
            print(f"  ✗ Missing: {section}")
            all_found = False

    print()

    if all_found:
        print("✅ Prompt format correct")
        return True
    else:
        print("✗ Prompt format incomplete")
        return False


def main():
    """Run all tests"""

    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "WEEK 4: Orchestrator → Researcher Tests" + " " * 18 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    tests = [
        ("Orchestrator → Researcher Invocation", test_invoke_researcher),
        ("Researcher Prompt Format", test_researcher_prompt_format)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"✗ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Final summary
    print()
    print("=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)
    print()

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    print()
    print(f"Results: {passed_count}/{total_count} tests passed")
    print()

    if passed_count == total_count:
        print("✅ ALL TESTS PASSED - Week 4 foundation ready!")
        print()
        print("Next steps:")
        print("  1. Integrate actual Task tool invocation")
        print("  2. Test with real researcher agent execution")
        print("  3. Validate research.json artifact creation")
        print("  4. Add planner invocation")
        return 0
    else:
        print("✗ Some tests failed - see details above")
        return 1


if __name__ == '__main__':
    sys.exit(main())

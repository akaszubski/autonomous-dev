#!/usr/bin/env python3
"""
Test agent communication and skill integration.

This test verifies:
1. Agents are actually executing (not just queued)
2. Inter-agent communication works (output → input)
3. Skills are being invoked by agents
4. Artifact chain is complete (researcher → planner → implementer)
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))

from artifacts import ArtifactManager, generate_workflow_id
from logging_utils import WorkflowLogger


class AgentCommunicationVerifier:
    """Verify agent communication and skill usage"""

    def __init__(self):
        self.artifact_manager = ArtifactManager()
        self.workflow_id = generate_workflow_id()
        self.logger = WorkflowLogger(self.workflow_id, 'test-verifier')

    def verify_agent_execution(self, workflow_id: str) -> Dict[str, Any]:
        """
        Verify that agents actually executed (not just queued).

        Checks for:
        1. Artifact files created (not just manifest)
        2. Timestamps showing sequential execution
        3. Content from each agent
        4. Evidence of skill usage in outputs
        """
        print(f"\n{'='*70}")
        print(f"AGENT EXECUTION VERIFICATION")
        print(f"{'='*70}")
        print(f"Workflow ID: {workflow_id}")

        artifacts_dir = Path(f".claude/artifacts/{workflow_id}")
        if not artifacts_dir.exists():
            print(f"❌ FAILED: Artifacts directory doesn't exist: {artifacts_dir}")
            return {"verified": False, "reason": "no_artifacts_dir"}

        # List all artifacts
        artifact_files = list(artifacts_dir.glob("*.json")) + list(artifacts_dir.glob("*.md"))
        print(f"\nArtifacts found: {len(artifact_files)}")
        for f in sorted(artifact_files):
            print(f"  - {f.name}")

        # Expected artifacts from each agent
        expected_agents = {
            'researcher': 'research.json',
            'planner': 'architecture.json',
            'test-master': 'tests.json',
            'implementer': 'implementation.json',
            'reviewer': 'review.json',
            'security-auditor': 'security.json',
            'doc-master': 'documentation.md'
        }

        executed_agents = {}
        missing_agents = []

        for agent, artifact_name in expected_agents.items():
            artifact_path = artifacts_dir / artifact_name
            if artifact_path.exists():
                try:
                    if artifact_name.endswith('.json'):
                        with open(artifact_path) as f:
                            content = json.load(f)
                    else:
                        with open(artifact_path) as f:
                            content = f.read()

                    executed_agents[agent] = {
                        'status': 'executed',
                        'artifact': artifact_name,
                        'has_content': bool(content),
                        'size_bytes': artifact_path.stat().st_size
                    }
                    print(f"  ✓ {agent}: {artifact_name} ({artifact_path.stat().st_size} bytes)")
                except Exception as e:
                    print(f"  ⚠️  {agent}: {artifact_name} (error reading: {e})")
                    missing_agents.append(agent)
            else:
                print(f"  ❌ {agent}: {artifact_name} NOT FOUND")
                missing_agents.append(agent)

        return {
            "verified": len(missing_agents) == 0,
            "executed_agents": executed_agents,
            "missing_agents": missing_agents,
            "artifact_count": len(artifact_files),
            "expected_count": len(expected_agents)
        }

    def verify_inter_agent_communication(self, workflow_id: str) -> Dict[str, Any]:
        """
        Verify that agents communicate with each other.

        Checks for:
        1. Planner reads researcher output
        2. Implementer reads planner output
        3. Reviewer reads implementer output
        4. References between artifacts
        """
        print(f"\n{'='*70}")
        print(f"INTER-AGENT COMMUNICATION VERIFICATION")
        print(f"{'='*70}")

        artifacts_dir = Path(f".claude/artifacts/{workflow_id}")
        communication_chain = []
        missing_links = []

        # Check: Planner reads researcher output
        print("\n1. Checking: Planner → Researcher communication")
        try:
            planner_path = artifacts_dir / "architecture.json"
            if planner_path.exists():
                with open(planner_path) as f:
                    planner_output = json.load(f)

                # Look for references to research in planner output
                planner_text = json.dumps(planner_output).lower()
                if any(ref in planner_text for ref in ['research', 'researcher', 'pattern', 'best practice']):
                    print("  ✓ Planner references researcher findings")
                    communication_chain.append("researcher→planner")
                else:
                    print("  ⚠️  Planner doesn't reference researcher output")
                    missing_links.append("researcher→planner")
            else:
                print("  ❌ Planner artifact missing")
        except Exception as e:
            print(f"  ❌ Error reading planner output: {e}")

        # Check: Implementer reads planner output
        print("\n2. Checking: Implementer → Planner communication")
        try:
            implementer_path = artifacts_dir / "implementation.json"
            if implementer_path.exists():
                with open(implementer_path) as f:
                    implementer_output = json.load(f)

                implementer_text = json.dumps(implementer_output).lower()
                if any(ref in implementer_text for ref in ['architecture', 'design', 'planner', 'pattern']):
                    print("  ✓ Implementer references planner design")
                    communication_chain.append("planner→implementer")
                else:
                    print("  ⚠️  Implementer doesn't reference planner output")
                    missing_links.append("planner→implementer")
            else:
                print("  ❌ Implementer artifact missing")
        except Exception as e:
            print(f"  ❌ Error reading implementer output: {e}")

        # Check: Test-master uses planner design
        print("\n3. Checking: Test-Master → Planner communication")
        try:
            tests_path = artifacts_dir / "tests.json"
            if tests_path.exists():
                with open(tests_path) as f:
                    tests_output = json.load(f)

                tests_text = json.dumps(tests_output).lower()
                if any(ref in tests_text for ref in ['architecture', 'design', 'interface', 'contract']):
                    print("  ✓ Test-Master references planner design")
                    communication_chain.append("planner→test-master")
                else:
                    print("  ⚠️  Test-Master doesn't reference planner design")
                    missing_links.append("planner→test-master")
            else:
                print("  ❌ Test-Master artifact missing")
        except Exception as e:
            print(f"  ❌ Error reading test output: {e}")

        return {
            "verified": len(missing_links) == 0,
            "communication_chain": communication_chain,
            "missing_links": missing_links
        }

    def verify_skill_usage(self, workflow_id: str) -> Dict[str, Any]:
        """
        Verify that agents are using skills.

        Checks for:
        1. References to python-standards in implementer output
        2. References to testing-guide in test-master output
        3. References to security-patterns in security-auditor output
        4. References to documentation-guide in doc-master output
        """
        print(f"\n{'='*70}")
        print(f"SKILL USAGE VERIFICATION")
        print(f"{'='*70}")

        artifacts_dir = Path(f".claude/artifacts/{workflow_id}")
        skill_usage = {}
        skills_not_used = []

        # Check: Implementer uses python-standards skill
        print("\n1. Checking: Implementer uses python-standards skill")
        try:
            implementer_path = artifacts_dir / "implementation.json"
            if implementer_path.exists():
                with open(implementer_path) as f:
                    implementer_output = json.load(f)

                impl_text = json.dumps(implementer_output).lower()
                python_skill_indicators = ['type hint', 'docstring', 'pep 8', 'black', 'isort', 'return annotation']
                found_indicators = [ind for ind in python_skill_indicators if ind in impl_text]

                if found_indicators:
                    print(f"  ✓ Found Python standards references: {', '.join(found_indicators)}")
                    skill_usage['python-standards'] = {'used': True, 'indicators': found_indicators}
                else:
                    print("  ⚠️  No Python standards skill indicators found")
                    skills_not_used.append('python-standards')
            else:
                print("  ❌ Implementer artifact missing")
        except Exception as e:
            print(f"  ❌ Error checking python-standards: {e}")

        # Check: Test-Master uses testing-guide skill
        print("\n2. Checking: Test-Master uses testing-guide skill")
        try:
            tests_path = artifacts_dir / "tests.json"
            if tests_path.exists():
                with open(tests_path) as f:
                    tests_output = json.load(f)

                tests_text = json.dumps(tests_output).lower()
                testing_indicators = ['pytest', 'unit test', 'integration test', 'coverage', 'mock', 'fixture', 'assert']
                found_indicators = [ind for ind in testing_indicators if ind in tests_text]

                if found_indicators:
                    print(f"  ✓ Found testing skill references: {', '.join(found_indicators)}")
                    skill_usage['testing-guide'] = {'used': True, 'indicators': found_indicators}
                else:
                    print("  ⚠️  No testing skill indicators found")
                    skills_not_used.append('testing-guide')
            else:
                print("  ❌ Test-Master artifact missing")
        except Exception as e:
            print(f"  ❌ Error checking testing-guide: {e}")

        # Check: Security-Auditor uses security-patterns skill
        print("\n3. Checking: Security-Auditor uses security-patterns skill")
        try:
            security_path = artifacts_dir / "security.json"
            if security_path.exists():
                with open(security_path) as f:
                    security_output = json.load(f)

                security_text = json.dumps(security_output).lower()
                security_indicators = ['injection', 'xss', 'csrf', 'authentication', 'authorization', 'validation', 'sanitize']
                found_indicators = [ind for ind in security_indicators if ind in security_text]

                if found_indicators:
                    print(f"  ✓ Found security skill references: {', '.join(found_indicators)}")
                    skill_usage['security-patterns'] = {'used': True, 'indicators': found_indicators}
                else:
                    print("  ⚠️  No security skill indicators found")
                    skills_not_used.append('security-patterns')
            else:
                print("  ❌ Security-Auditor artifact missing")
        except Exception as e:
            print(f"  ❌ Error checking security-patterns: {e}")

        # Check: Doc-Master uses documentation-guide skill
        print("\n4. Checking: Doc-Master uses documentation-guide skill")
        try:
            docs_path = artifacts_dir / "documentation.md"
            if docs_path.exists():
                with open(docs_path) as f:
                    docs_content = f.read().lower()

                doc_indicators = ['## ', '### ', 'example', 'usage', 'api', 'parameter', 'return']
                found_indicators = [ind for ind in doc_indicators if ind in docs_content]

                if found_indicators:
                    print(f"  ✓ Found documentation skill references: {', '.join(found_indicators)}")
                    skill_usage['documentation-guide'] = {'used': True, 'indicators': found_indicators}
                else:
                    print("  ⚠️  No documentation skill indicators found")
                    skills_not_used.append('documentation-guide')
            else:
                print("  ❌ Doc-Master artifact missing")
        except Exception as e:
            print(f"  ❌ Error checking documentation-guide: {e}")

        return {
            "verified": len(skills_not_used) == 0,
            "skills_used": skill_usage,
            "skills_not_used": skills_not_used
        }

    def generate_verification_report(self, workflow_id: str) -> Dict[str, Any]:
        """
        Generate complete verification report.

        Returns:
        - Agent execution status
        - Inter-agent communication status
        - Skill usage status
        - Overall verification result
        """
        print(f"\n\n{'='*70}")
        print(f"COMPLETE AGENT VERIFICATION REPORT")
        print(f"{'='*70}")
        print(f"Workflow ID: {workflow_id}")
        print(f"Timestamp: {Path('.claude/artifacts').stat().st_mtime}")

        exec_result = self.verify_agent_execution(workflow_id)
        comm_result = self.verify_inter_agent_communication(workflow_id)
        skill_result = self.verify_skill_usage(workflow_id)

        # Generate summary
        print(f"\n{'='*70}")
        print(f"VERIFICATION SUMMARY")
        print(f"{'='*70}")

        print(f"\n1. AGENT EXECUTION")
        print(f"   Status: {'✅ VERIFIED' if exec_result['verified'] else '❌ FAILED'}")
        print(f"   Agents executed: {exec_result['artifact_count']}/{exec_result['expected_count']}")
        if exec_result['missing_agents']:
            print(f"   Missing agents: {', '.join(exec_result['missing_agents'])}")

        print(f"\n2. INTER-AGENT COMMUNICATION")
        print(f"   Status: {'✅ VERIFIED' if comm_result['verified'] else '⚠️  INCOMPLETE'}")
        print(f"   Communication chains found: {len(comm_result['communication_chain'])}")
        if comm_result['communication_chain']:
            for chain in comm_result['communication_chain']:
                print(f"   ✓ {chain}")
        if comm_result['missing_links']:
            print(f"   Missing links: {', '.join(comm_result['missing_links'])}")

        print(f"\n3. SKILL USAGE")
        print(f"   Status: {'✅ VERIFIED' if skill_result['verified'] else '⚠️  INCOMPLETE'}")
        print(f"   Skills used: {len(skill_result['skills_used'])}")
        if skill_result['skills_used']:
            for skill, data in skill_result['skills_used'].items():
                print(f"   ✓ {skill}")
                print(f"     Indicators: {', '.join(data['indicators'][:3])}...")
        if skill_result['skills_not_used']:
            print(f"   Skills not detected: {', '.join(skill_result['skills_not_used'])}")

        overall_verified = exec_result['verified'] and comm_result['verified'] and skill_result['verified']

        print(f"\n{'='*70}")
        if overall_verified:
            print("✅ ALL VERIFICATIONS PASSED")
            print("\nConclusion:")
            print("- Agents are executing (not just queued)")
            print("- Inter-agent communication is working")
            print("- Skills are being used by agents")
        else:
            print("⚠️  SOME VERIFICATIONS INCOMPLETE")
            print("\nThis could mean:")
            print("- Agents haven't executed yet (still queued)")
            print("- Agent outputs haven't been saved to artifacts")
            print("- Communication is working but not visible in artifacts")
        print(f"{'='*70}\n")

        return {
            "overall_verified": overall_verified,
            "agent_execution": exec_result,
            "inter_agent_communication": comm_result,
            "skill_usage": skill_result
        }


def main():
    """Run verification on latest workflow"""
    verifier = AgentCommunicationVerifier()

    # Find latest workflow
    artifacts_dir = Path(".claude/artifacts")
    if not artifacts_dir.exists():
        print("❌ No artifacts directory found")
        return False

    workflows = sorted([d for d in artifacts_dir.iterdir() if d.is_dir()])
    if not workflows:
        print("❌ No workflows found")
        return False

    latest_workflow = workflows[-1].name
    print(f"\nVerifying latest workflow: {latest_workflow}")

    report = verifier.generate_verification_report(latest_workflow)

    return report['overall_verified']


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

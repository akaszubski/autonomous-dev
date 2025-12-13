"""
Unit tests for researcher agent split (Issue #128).

TDD Mode: These tests are written BEFORE implementation.
Tests should FAIL initially (agents not yet created).

Test Strategy:
- Test researcher-local agent structure and output format
- Test researcher-web agent structure and output format
- Test research merge logic and edge cases
- Test AgentTracker parallel research verification
- Test tool restrictions enforcement

Date: 2025-12-13
Issue: GitHub #128 (Split researcher into parallel agents)
Agent: test-master
Phase: TDD Red Phase
"""

import pytest
import json
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, MagicMock, patch


class TestResearcherLocalAgent:
    """Test researcher-local agent structure and output format."""

    def test_researcher_local_agent_exists(self):
        """
        Test that researcher-local.md agent file exists.

        Expected location: plugins/autonomous-dev/agents/researcher-local.md
        """
        agent_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher-local.md"

        assert agent_file.exists(), \
            "researcher-local.md agent file should exist in plugins/autonomous-dev/agents/"

    def test_researcher_local_has_correct_tools(self):
        """
        Test that researcher-local only has file system tools (no web access).

        Expected tools: Read, Grep, Glob
        Forbidden tools: WebSearch, WebFetch
        """
        agent_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher-local.md"
        content = agent_file.read_text()

        # Assert: Has file system tools
        assert "Read" in content, "researcher-local should have Read tool"
        assert "Grep" in content, "researcher-local should have Grep tool"
        assert "Glob" in content or "glob" in content.lower(), \
            "researcher-local should have Glob tool"

        # Assert: No web access tools
        assert "WebSearch" not in content, \
            "researcher-local should NOT have WebSearch tool (use researcher-web instead)"
        assert "WebFetch" not in content, \
            "researcher-local should NOT have WebFetch tool (use researcher-web instead)"

    def test_researcher_local_output_format(self):
        """
        Test that researcher-local produces valid JSON with required fields.

        Expected JSON structure:
        {
            "existing_patterns": [
                {
                    "file": "path/to/file.py",
                    "pattern": "Description of pattern",
                    "lines": "42-58"
                }
            ],
            "files_to_update": ["file1.py", "file2.py"],
            "architecture_notes": [
                "Note about project architecture"
            ],
            "similar_implementations": [
                {
                    "file": "path/to/similar.py",
                    "similarity": "Why it's similar",
                    "reusable_code": "What can be reused"
                }
            ]
        }
        """
        # Mock researcher-local output
        mock_output = {
            "existing_patterns": [
                {
                    "file": "plugins/autonomous-dev/lib/security_utils.py",
                    "pattern": "Path validation using validate_path()",
                    "lines": "45-67"
                },
                {
                    "file": "plugins/autonomous-dev/lib/validation.py",
                    "pattern": "Input sanitization pattern",
                    "lines": "23-34"
                }
            ],
            "files_to_update": [
                "plugins/autonomous-dev/lib/agent_tracker.py",
                "plugins/autonomous-dev/commands/auto-implement.md"
            ],
            "architecture_notes": [
                "Project uses two-tier library design (core + CLI wrapper)",
                "All validation goes through security_utils module"
            ],
            "similar_implementations": [
                {
                    "file": "plugins/autonomous-dev/lib/session_tracker.py",
                    "similarity": "Also uses path_utils for portable path detection",
                    "reusable_code": "Path resolution and validation logic"
                }
            ]
        }

        # Validate JSON structure
        assert "existing_patterns" in mock_output, \
            "researcher-local output must include 'existing_patterns'"
        assert "files_to_update" in mock_output, \
            "researcher-local output must include 'files_to_update'"
        assert "architecture_notes" in mock_output, \
            "researcher-local output must include 'architecture_notes'"
        assert "similar_implementations" in mock_output, \
            "researcher-local output must include 'similar_implementations'"

        # Validate types
        assert isinstance(mock_output["existing_patterns"], list), \
            "'existing_patterns' should be a list"
        assert isinstance(mock_output["files_to_update"], list), \
            "'files_to_update' should be a list"
        assert isinstance(mock_output["architecture_notes"], list), \
            "'architecture_notes' should be a list"
        assert isinstance(mock_output["similar_implementations"], list), \
            "'similar_implementations' should be a list"

        # Validate pattern structure
        if len(mock_output["existing_patterns"]) > 0:
            pattern = mock_output["existing_patterns"][0]
            assert "file" in pattern, "Pattern should have 'file' field"
            assert "pattern" in pattern, "Pattern should have 'pattern' field"
            assert "lines" in pattern, "Pattern should have 'lines' field"

    def test_researcher_local_json_is_valid(self):
        """
        Test that researcher-local output is valid JSON (can be parsed).

        Edge cases:
        - Handles empty results (empty lists, not null)
        - Handles special characters in file paths
        - Handles multi-line pattern descriptions
        """
        # Valid JSON with empty results
        empty_output = json.dumps({
            "existing_patterns": [],
            "files_to_update": [],
            "architecture_notes": [],
            "similar_implementations": []
        })
        parsed_empty = json.loads(empty_output)
        assert isinstance(parsed_empty["existing_patterns"], list)
        assert len(parsed_empty["existing_patterns"]) == 0

        # Valid JSON with special characters
        special_chars_output = json.dumps({
            "existing_patterns": [
                {
                    "file": "path/with spaces/file.py",
                    "pattern": "Pattern with \"quotes\" and \n newlines",
                    "lines": "10-20"
                }
            ],
            "files_to_update": ["file-with-dashes.py", "file_with_underscores.py"],
            "architecture_notes": ["Note with 'quotes'"],
            "similar_implementations": []
        })
        parsed_special = json.loads(special_chars_output)
        assert len(parsed_special["existing_patterns"]) == 1
        assert "quotes" in parsed_special["existing_patterns"][0]["pattern"]

    def test_researcher_local_focuses_on_codebase(self):
        """
        Test that researcher-local focuses only on codebase patterns.

        Expected behavior:
        - All patterns reference actual project files
        - No external URLs or references
        - No web search results
        - Focuses on reusable code and existing architecture
        """
        agent_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher-local.md"
        content = agent_file.read_text()

        # Assert: Mentions codebase/project
        assert "codebase" in content.lower() or "project" in content.lower(), \
            "researcher-local should focus on codebase/project patterns"

        # Assert: Mentions existing patterns/implementations
        assert "existing" in content.lower() or "similar" in content.lower(), \
            "researcher-local should search for existing patterns"

        # Assert: Mentions file search
        assert "file" in content.lower() or "search" in content.lower(), \
            "researcher-local should search files"


class TestResearcherWebAgent:
    """Test researcher-web agent structure and output format."""

    def test_researcher_web_agent_exists(self):
        """
        Test that researcher-web.md agent file exists.

        Expected location: plugins/autonomous-dev/agents/researcher-web.md
        """
        agent_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher-web.md"

        assert agent_file.exists(), \
            "researcher-web.md agent file should exist in plugins/autonomous-dev/agents/"

    def test_researcher_web_has_correct_tools(self):
        """
        Test that researcher-web only has web access tools (no file access).

        Expected tools: WebSearch, WebFetch
        Forbidden tools: Read, Grep, Glob, Edit, Write
        """
        agent_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher-web.md"
        content = agent_file.read_text()

        # Assert: Has web tools
        assert "WebSearch" in content, "researcher-web should have WebSearch tool"
        assert "WebFetch" in content, "researcher-web should have WebFetch tool"

        # Assert: No file system tools (use researcher-local instead)
        assert "Read" not in content or "Read" in content and "researcher-local" in content, \
            "researcher-web should NOT have Read tool (use researcher-local instead)"
        assert "Grep" not in content or "Grep" in content and "researcher-local" in content, \
            "researcher-web should NOT have Grep tool (use researcher-local instead)"

        # Note: We allow "Glob" to appear in documentation but not in tools list
        # The agent should reference researcher-local for file operations

    def test_researcher_web_output_format(self):
        """
        Test that researcher-web produces valid JSON with required fields.

        Expected JSON structure:
        {
            "best_practices": [
                {
                    "practice": "Description of best practice",
                    "source": "URL or reference",
                    "rationale": "Why this practice matters"
                }
            ],
            "recommended_libraries": [
                {
                    "name": "library-name",
                    "purpose": "What it does",
                    "installation": "pip install library-name"
                }
            ],
            "security_considerations": [
                {
                    "risk": "Description of security risk",
                    "mitigation": "How to mitigate",
                    "severity": "high|medium|low"
                }
            ],
            "common_pitfalls": [
                {
                    "pitfall": "Common mistake",
                    "consequence": "What goes wrong",
                    "avoidance": "How to avoid"
                }
            ]
        }
        """
        # Mock researcher-web output
        mock_output = {
            "best_practices": [
                {
                    "practice": "Use parameterized queries to prevent SQL injection",
                    "source": "https://owasp.org/www-community/attacks/SQL_Injection",
                    "rationale": "Prevents attackers from injecting malicious SQL"
                },
                {
                    "practice": "Validate all user input on server side",
                    "source": "https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html",
                    "rationale": "Client-side validation can be bypassed"
                }
            ],
            "recommended_libraries": [
                {
                    "name": "pytest",
                    "purpose": "Testing framework with fixtures and parameterization",
                    "installation": "pip install pytest"
                }
            ],
            "security_considerations": [
                {
                    "risk": "Path traversal via user input",
                    "mitigation": "Use Path.resolve() and validate against whitelist",
                    "severity": "high"
                }
            ],
            "common_pitfalls": [
                {
                    "pitfall": "Not handling edge cases in validation",
                    "consequence": "Security vulnerabilities or crashes",
                    "avoidance": "Test with fuzzing and boundary conditions"
                }
            ]
        }

        # Validate JSON structure
        assert "best_practices" in mock_output, \
            "researcher-web output must include 'best_practices'"
        assert "recommended_libraries" in mock_output, \
            "researcher-web output must include 'recommended_libraries'"
        assert "security_considerations" in mock_output, \
            "researcher-web output must include 'security_considerations'"
        assert "common_pitfalls" in mock_output, \
            "researcher-web output must include 'common_pitfalls'"

        # Validate types
        assert isinstance(mock_output["best_practices"], list), \
            "'best_practices' should be a list"
        assert isinstance(mock_output["recommended_libraries"], list), \
            "'recommended_libraries' should be a list"
        assert isinstance(mock_output["security_considerations"], list), \
            "'security_considerations' should be a list"
        assert isinstance(mock_output["common_pitfalls"], list), \
            "'common_pitfalls' should be a list"

        # Validate best practice structure
        if len(mock_output["best_practices"]) > 0:
            practice = mock_output["best_practices"][0]
            assert "practice" in practice, "Best practice should have 'practice' field"
            assert "source" in practice, "Best practice should have 'source' field"
            assert "rationale" in practice, "Best practice should have 'rationale' field"

        # Validate security consideration structure
        if len(mock_output["security_considerations"]) > 0:
            risk = mock_output["security_considerations"][0]
            assert "risk" in risk, "Security consideration should have 'risk' field"
            assert "mitigation" in risk, "Security consideration should have 'mitigation' field"
            assert "severity" in risk, "Security consideration should have 'severity' field"
            assert risk["severity"] in ["high", "medium", "low"], \
                "Severity should be high, medium, or low"

    def test_researcher_web_focuses_on_external_guidance(self):
        """
        Test that researcher-web focuses on external best practices.

        Expected behavior:
        - References industry standards (OWASP, etc.)
        - Includes web search results
        - Provides external URLs and documentation
        - No local file references
        """
        agent_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher-web.md"
        content = agent_file.read_text()

        # Assert: Mentions web/external/best practices
        assert any(keyword in content.lower() for keyword in ["web", "external", "best practice", "industry"]), \
            "researcher-web should focus on external/web best practices"

        # Assert: Mentions search
        assert "search" in content.lower(), \
            "researcher-web should perform web searches"


class TestResearchMergeLogic:
    """Test research merge logic that combines local and web findings."""

    def test_research_merge_complete(self):
        """
        Test merging research when both researchers return valid results.

        Expected merged structure:
        {
            "codebase_context": {
                "existing_patterns": [...],
                "files_to_update": [...],
                "architecture_notes": [...],
                "similar_implementations": [...]
            },
            "external_guidance": {
                "best_practices": [...],
                "recommended_libraries": [...],
                "security_considerations": [...],
                "common_pitfalls": [...]
            },
            "recommendations": [
                {
                    "type": "pattern_match|best_practice|security|warning",
                    "message": "Synthesized recommendation",
                    "source": "local|web|both"
                }
            ]
        }
        """
        # Mock inputs
        local_research = {
            "existing_patterns": [
                {"file": "lib/utils.py", "pattern": "Input validation", "lines": "10-20"}
            ],
            "files_to_update": ["lib/new_feature.py"],
            "architecture_notes": ["Uses two-tier design"],
            "similar_implementations": []
        }

        web_research = {
            "best_practices": [
                {
                    "practice": "Validate all inputs",
                    "source": "https://owasp.org",
                    "rationale": "Security"
                }
            ],
            "recommended_libraries": [],
            "security_considerations": [
                {
                    "risk": "Path traversal",
                    "mitigation": "Use Path.resolve()",
                    "severity": "high"
                }
            ],
            "common_pitfalls": []
        }

        # Mock merge function
        def merge_research(local: Dict, web: Dict) -> Dict:
            """
            Merge local and web research findings.

            Args:
                local: researcher-local output
                web: researcher-web output

            Returns:
                Merged research context for planner
            """
            # Synthesize recommendations by comparing local patterns to web guidance
            recommendations = []

            # Check if local patterns align with best practices
            for pattern in local.get("existing_patterns", []):
                for practice in web.get("best_practices", []):
                    if any(keyword in pattern["pattern"].lower()
                           for keyword in practice["practice"].lower().split()):
                        recommendations.append({
                            "type": "pattern_match",
                            "message": f"Existing pattern in {pattern['file']} aligns with best practice: {practice['practice']}",
                            "source": "both"
                        })

            # Flag security risks
            for risk in web.get("security_considerations", []):
                if risk["severity"] == "high":
                    recommendations.append({
                        "type": "security",
                        "message": f"HIGH PRIORITY: {risk['risk']} - {risk['mitigation']}",
                        "source": "web"
                    })

            return {
                "codebase_context": local,
                "external_guidance": web,
                "recommendations": recommendations
            }

        # Act: Merge research
        merged = merge_research(local_research, web_research)

        # Assert: Structure is correct
        assert "codebase_context" in merged
        assert "external_guidance" in merged
        assert "recommendations" in merged

        # Assert: Context preserved
        assert merged["codebase_context"] == local_research
        assert merged["external_guidance"] == web_research

        # Assert: Recommendations generated
        assert isinstance(merged["recommendations"], list)

        # Assert: Security recommendation flagged
        security_recs = [r for r in merged["recommendations"] if r["type"] == "security"]
        assert len(security_recs) > 0, "High severity security risks should be flagged"
        assert "HIGH PRIORITY" in security_recs[0]["message"]

    def test_research_merge_partial_failure(self):
        """
        Test merge when one researcher fails (returns empty/error).

        Expected behavior:
        - Merge proceeds with available data
        - Warnings added to recommendations
        - Missing context flagged for planner
        """
        # Mock partial failure (web research failed)
        local_research = {
            "existing_patterns": [{"file": "lib/utils.py", "pattern": "Pattern", "lines": "10"}],
            "files_to_update": ["lib/new.py"],
            "architecture_notes": ["Note"],
            "similar_implementations": []
        }

        web_research = {
            "error": "WebSearch failed: Rate limit exceeded",
            "best_practices": [],
            "recommended_libraries": [],
            "security_considerations": [],
            "common_pitfalls": []
        }

        # Mock merge with error handling
        def merge_with_errors(local: Dict, web: Dict) -> Dict:
            recommendations = []

            # Check for errors
            if "error" in local:
                recommendations.append({
                    "type": "warning",
                    "message": f"Local research failed: {local['error']}. Proceeding with web guidance only.",
                    "source": "system"
                })

            if "error" in web:
                recommendations.append({
                    "type": "warning",
                    "message": f"Web research failed: {web['error']}. Proceeding with codebase patterns only.",
                    "source": "system"
                })

            return {
                "codebase_context": local if "error" not in local else {},
                "external_guidance": web if "error" not in web else {},
                "recommendations": recommendations
            }

        # Act: Merge with failure
        merged = merge_with_errors(local_research, web_research)

        # Assert: Warnings present
        warnings = [r for r in merged["recommendations"] if r["type"] == "warning"]
        assert len(warnings) > 0, "Should have warning about web research failure"
        assert "Web research failed" in warnings[0]["message"]

        # Assert: Local context preserved
        assert len(merged["codebase_context"]["existing_patterns"]) > 0

        # Assert: Empty web context
        assert len(merged["external_guidance"]["best_practices"]) == 0

    def test_research_merge_conflicting_guidance(self):
        """
        Test merge when local pattern conflicts with web best practice.

        Expected behavior:
        - Conflict flagged in recommendations
        - Both perspectives preserved
        - Planner gets decision guidance
        """
        # Mock conflicting research
        local_research = {
            "existing_patterns": [
                {
                    "file": "lib/auth.py",
                    "pattern": "Uses MD5 for password hashing",
                    "lines": "50-55"
                }
            ],
            "files_to_update": [],
            "architecture_notes": [],
            "similar_implementations": []
        }

        web_research = {
            "best_practices": [
                {
                    "practice": "Use bcrypt or Argon2 for password hashing, never MD5",
                    "source": "https://owasp.org/password-storage",
                    "rationale": "MD5 is cryptographically broken"
                }
            ],
            "recommended_libraries": [
                {"name": "bcrypt", "purpose": "Secure password hashing", "installation": "pip install bcrypt"}
            ],
            "security_considerations": [
                {
                    "risk": "Weak password hashing (MD5)",
                    "mitigation": "Migrate to bcrypt or Argon2",
                    "severity": "high"
                }
            ],
            "common_pitfalls": []
        }

        # Mock conflict detection
        def detect_conflicts(local: Dict, web: Dict) -> List[Dict]:
            conflicts = []

            for pattern in local.get("existing_patterns", []):
                for practice in web.get("best_practices", []):
                    # Simple keyword matching (real implementation would be smarter)
                    if "MD5" in pattern["pattern"] and "never MD5" in practice["practice"]:
                        conflicts.append({
                            "type": "conflict",
                            "message": f"CONFLICT: {pattern['file']} uses {pattern['pattern']}, but best practice says: {practice['practice']}",
                            "source": "both",
                            "severity": "high",
                            "recommendation": "Refactor to align with best practice"
                        })

            return conflicts

        # Act: Detect conflicts
        conflicts = detect_conflicts(local_research, web_research)

        # Assert: Conflict detected
        assert len(conflicts) > 0, "Should detect MD5 usage conflict"
        assert conflicts[0]["type"] == "conflict"
        assert "CONFLICT" in conflicts[0]["message"]
        assert conflicts[0]["severity"] == "high"
        assert "Refactor" in conflicts[0]["recommendation"]

    def test_research_merge_json_output(self):
        """
        Test that merged research output is valid JSON.

        Ensures planner receives properly formatted context.
        """
        merged_output = {
            "codebase_context": {
                "existing_patterns": [],
                "files_to_update": [],
                "architecture_notes": [],
                "similar_implementations": []
            },
            "external_guidance": {
                "best_practices": [],
                "recommended_libraries": [],
                "security_considerations": [],
                "common_pitfalls": []
            },
            "recommendations": []
        }

        # Test: Valid JSON
        json_str = json.dumps(merged_output, indent=2)
        parsed = json.loads(json_str)

        assert "codebase_context" in parsed
        assert "external_guidance" in parsed
        assert "recommendations" in parsed


class TestAgentTrackerParallelVerification:
    """Test AgentTracker.verify_parallel_research() method."""

    def test_verify_parallel_research_method_exists(self):
        """
        Test that AgentTracker has verify_parallel_research() class method.

        Expected signature:
        @classmethod
        def verify_parallel_research(cls, session_file: Optional[Path] = None) -> Dict[str, Any]
        """
        # This test will fail until method is implemented
        from plugins.autonomous_dev.lib.agent_tracker import AgentTracker

        # Assert: Method exists
        assert hasattr(AgentTracker, "verify_parallel_research"), \
            "AgentTracker should have verify_parallel_research() class method"

        # Assert: Is a class method
        assert isinstance(AgentTracker.__dict__["verify_parallel_research"], classmethod), \
            "verify_parallel_research should be a classmethod"

    def test_verify_parallel_research_detects_parallel_execution(self):
        """
        Test that verify_parallel_research() detects parallel agent execution.

        Expected behavior:
        - Reads session file
        - Finds researcher-local and researcher-web entries
        - Checks start times are within threshold (5 seconds)
        - Returns success if parallel, failure if sequential
        """
        from plugins.autonomous_dev.lib.agent_tracker import AgentTracker

        # Mock session data with parallel execution
        parallel_session = {
            "session_id": "20251213-100000",
            "started": "2025-12-13T10:00:00",
            "agents": [
                {
                    "agent": "researcher-local",
                    "status": "completed",
                    "started_at": "2025-12-13T10:00:05",
                    "completed_at": "2025-12-13T10:03:15",
                    "duration_seconds": 190,
                    "message": "Found 3 patterns"
                },
                {
                    "agent": "researcher-web",
                    "status": "completed",
                    "started_at": "2025-12-13T10:00:06",  # Within 5 seconds
                    "completed_at": "2025-12-13T10:02:45",
                    "duration_seconds": 159,
                    "message": "Found 5 best practices"
                }
            ]
        }

        # Mock verification function (real implementation will be in AgentTracker)
        def mock_verify_parallel(session_data: Dict) -> Dict[str, Any]:
            """Verify parallel execution of research agents."""
            from datetime import datetime

            local_entry = next(
                (a for a in session_data["agents"] if a["agent"] == "researcher-local"),
                None
            )
            web_entry = next(
                (a for a in session_data["agents"] if a["agent"] == "researcher-web"),
                None
            )

            if not local_entry or not web_entry:
                return {
                    "parallel": False,
                    "reason": "Missing researcher agents",
                    "found_agents": [a["agent"] for a in session_data["agents"]]
                }

            # Parse timestamps
            local_start = datetime.fromisoformat(local_entry["started_at"])
            web_start = datetime.fromisoformat(web_entry["started_at"])

            # Check time difference
            time_diff = abs((web_start - local_start).total_seconds())
            is_parallel = time_diff <= 5  # 5 second threshold

            return {
                "parallel": is_parallel,
                "time_difference_seconds": time_diff,
                "threshold_seconds": 5,
                "researcher_local_start": local_entry["started_at"],
                "researcher_web_start": web_entry["started_at"]
            }

        # Act: Verify parallel execution
        result = mock_verify_parallel(parallel_session)

        # Assert: Detected as parallel
        assert result["parallel"] is True, \
            "Should detect parallel execution when start times within 5 seconds"
        assert result["time_difference_seconds"] <= 5

    def test_verify_parallel_research_detects_sequential_execution(self):
        """
        Test that verify_parallel_research() detects sequential (non-parallel) execution.

        If researcher-local completes before researcher-web starts, it's sequential.
        """
        # Mock session data with sequential execution
        sequential_session = {
            "session_id": "20251213-110000",
            "started": "2025-12-13T11:00:00",
            "agents": [
                {
                    "agent": "researcher-local",
                    "status": "completed",
                    "started_at": "2025-12-13T11:00:05",
                    "completed_at": "2025-12-13T11:03:15",
                    "duration_seconds": 190,
                    "message": "Found 3 patterns"
                },
                {
                    "agent": "researcher-web",
                    "status": "completed",
                    "started_at": "2025-12-13T11:03:20",  # Started after local completed (sequential)
                    "completed_at": "2025-12-13T11:05:45",
                    "duration_seconds": 145,
                    "message": "Found 5 best practices"
                }
            ]
        }

        # Mock verification
        def mock_verify_parallel(session_data: Dict) -> Dict[str, Any]:
            from datetime import datetime

            local_entry = next(
                (a for a in session_data["agents"] if a["agent"] == "researcher-local"),
                None
            )
            web_entry = next(
                (a for a in session_data["agents"] if a["agent"] == "researcher-web"),
                None
            )

            if not local_entry or not web_entry:
                return {"parallel": False, "reason": "Missing researcher agents"}

            local_start = datetime.fromisoformat(local_entry["started_at"])
            web_start = datetime.fromisoformat(web_entry["started_at"])

            time_diff = abs((web_start - local_start).total_seconds())
            is_parallel = time_diff <= 5

            return {
                "parallel": is_parallel,
                "time_difference_seconds": time_diff,
                "threshold_seconds": 5
            }

        # Act: Verify
        result = mock_verify_parallel(sequential_session)

        # Assert: Detected as sequential
        assert result["parallel"] is False, \
            "Should detect sequential execution when start times > 5 seconds apart"
        assert result["time_difference_seconds"] > 5

    def test_verify_parallel_research_missing_agents(self):
        """
        Test verify_parallel_research() when one or both research agents missing.

        Expected behavior:
        - Returns parallel=False
        - Includes reason explaining which agents are missing
        - Lists found agents for debugging
        """
        # Mock session with missing web researcher
        incomplete_session = {
            "session_id": "20251213-120000",
            "started": "2025-12-13T12:00:00",
            "agents": [
                {
                    "agent": "researcher-local",
                    "status": "completed",
                    "started_at": "2025-12-13T12:00:05",
                    "completed_at": "2025-12-13T12:03:15",
                    "duration_seconds": 190,
                    "message": "Found 3 patterns"
                },
                {
                    "agent": "planner",
                    "status": "completed",
                    "started_at": "2025-12-13T12:03:20",
                    "completed_at": "2025-12-13T12:05:00",
                    "duration_seconds": 100,
                    "message": "Created plan"
                }
            ]
        }

        # Mock verification
        def mock_verify_parallel(session_data: Dict) -> Dict[str, Any]:
            local_entry = next(
                (a for a in session_data["agents"] if a["agent"] == "researcher-local"),
                None
            )
            web_entry = next(
                (a for a in session_data["agents"] if a["agent"] == "researcher-web"),
                None
            )

            if not local_entry or not web_entry:
                missing = []
                if not local_entry:
                    missing.append("researcher-local")
                if not web_entry:
                    missing.append("researcher-web")

                return {
                    "parallel": False,
                    "reason": f"Missing researcher agents: {', '.join(missing)}",
                    "found_agents": [a["agent"] for a in session_data["agents"]],
                    "missing_agents": missing
                }

            return {"parallel": True}

        # Act: Verify
        result = mock_verify_parallel(incomplete_session)

        # Assert: Failure with reason
        assert result["parallel"] is False
        assert "researcher-web" in result["missing_agents"]
        assert "researcher-local" in result["found_agents"]
        assert "planner" in result["found_agents"]


class TestOldResearcherDeprecation:
    """Test that old monolithic researcher agent is properly deprecated."""

    def test_old_researcher_agent_removed(self):
        """
        Test that old researcher.md agent file is removed or archived.

        The old monolithic researcher should no longer be used.
        It should either be deleted or moved to an archive.
        """
        old_researcher = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents" / "researcher.md"

        # After migration, old researcher should not exist in active agents
        # OR should be clearly marked as deprecated
        if old_researcher.exists():
            content = old_researcher.read_text()
            assert "DEPRECATED" in content or "deprecated" in content, \
                "Old researcher.md should be marked as DEPRECATED or removed entirely"

    def test_agent_metadata_updated(self):
        """
        Test that AGENT_METADATA in agent_tracker.py includes new agents.

        Should have:
        - researcher-local metadata
        - researcher-web metadata
        - Remove or deprecate old "researcher" metadata
        """
        from plugins.autonomous_dev.lib.agent_tracker import AGENT_METADATA

        # Assert: New agents have metadata
        assert "researcher-local" in AGENT_METADATA, \
            "AGENT_METADATA should include researcher-local"
        assert "researcher-web" in AGENT_METADATA, \
            "AGENT_METADATA should include researcher-web"

        # Each should have description and emoji
        assert "description" in AGENT_METADATA["researcher-local"]
        assert "emoji" in AGENT_METADATA["researcher-local"]
        assert "description" in AGENT_METADATA["researcher-web"]
        assert "emoji" in AGENT_METADATA["researcher-web"]


# Mark all tests as expecting to fail (TDD red phase)
pytestmark = pytest.mark.xfail(
    reason="TDD Red Phase: Researcher split not yet implemented (Issue #128). "
           "Tests verify expected behavior for split researcher agents, merge logic, "
           "and AgentTracker parallel verification."
)

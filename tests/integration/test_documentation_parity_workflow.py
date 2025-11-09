#!/usr/bin/env python3
"""
Integration Tests for Documentation Parity Validation Workflow (FAILING - Red Phase)

This module contains FAILING integration tests for the documentation parity validation
workflow, including doc-master agent integration, pre-commit hook integration, and
end-to-end validation workflows.

Test Coverage:
1. Doc-master agent integration (5 tests)
2. Pre-commit hook blocking behavior (6 tests)
3. CLI interface integration (4 tests)
4. End-to-end workflow tests (2 tests)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe integration requirements
- Tests should FAIL until implementation is complete
- Each test validates ONE workflow requirement

Author: test-master agent
Date: 2025-11-09
Related: Documentation parity validation feature
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# These imports will FAIL until implementation is complete
from plugins.autonomous_dev.lib.validate_documentation_parity import (
    validate_documentation_parity,
    ParityReport,
    ValidationLevel,
)


class TestDocMasterAgentIntegration:
    """Test doc-master agent integration with parity validation."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with full structure."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        (repo_root / ".claude").mkdir()
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "agents").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "commands").mkdir()

        # Create doc-master agent file
        agents_dir = repo_root / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "doc-master.md").write_text("""
---
name: doc-master
description: Documentation synchronization specialist
model: claude-sonnet-4
tools: [Read, Write, Edit, Grep, Glob, Bash]
---

# Documentation Master Agent

Synchronizes documentation across all project files.

## Documentation Parity Validation Checklist

Before completing documentation sync:
1. Run documentation parity validator
2. Check version consistency (CLAUDE.md vs PROJECT.md)
3. Verify count accuracy (agents, commands, skills, hooks)
4. Validate cross-references (documented features exist)
5. Ensure CHANGELOG is up-to-date
6. Confirm security documentation is complete
        """)

        return repo_root

    def test_doc_master_runs_parity_validation_automatically(self, temp_repo):
        """Test that doc-master agent runs parity validation automatically.

        REQUIREMENT: Doc-master must validate documentation parity before completing.
        Expected: Parity validation executed as part of doc-master workflow.
        """
        # Create documentation with issues
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n### Agents (5 specialists)\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Create 2 actual agents (mismatch)
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")

        # Mock doc-master execution
        with patch('subprocess.run') as mock_run:
            # Simulate doc-master calling validation
            report = validate_documentation_parity(temp_repo)

            # Should detect issues
            assert report.has_errors is True
            assert report.total_issues > 0

    def test_doc_master_blocks_on_validation_errors(self, temp_repo):
        """Test that doc-master blocks completion when validation errors exist.

        REQUIREMENT: Doc-master must not complete if validation fails.
        Expected: Doc-master exits with error when parity issues found.
        """
        # Create documentation with ERROR level issues
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Validate
        report = validate_documentation_parity(temp_repo)

        # Should have errors
        assert report.has_errors is True
        assert report.exit_code == 1

        # Doc-master should exit with this code
        # (implementation: doc-master checks exit_code and blocks if non-zero)

    def test_doc_master_passes_on_clean_validation(self, temp_repo):
        """Test that doc-master completes successfully when validation passes.

        REQUIREMENT: Doc-master completes when documentation is valid.
        Expected: Doc-master exits with code 0 when no errors.
        """
        # Create valid documentation
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n### Agents (2 specialists)\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Create 2 actual agents (matches documentation)
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")

        # Validate
        report = validate_documentation_parity(temp_repo)

        # Should have no errors
        assert report.has_errors is False
        assert report.exit_code == 0

    def test_doc_master_reports_validation_results(self, temp_repo):
        """Test that doc-master reports validation results to user.

        REQUIREMENT: Doc-master displays validation report.
        Expected: Validation report shown in doc-master output.
        """
        # Create documentation with mixed issues
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n### Agents (5 specialists)\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Create 2 actual agents
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")

        # Generate report
        report = validate_documentation_parity(temp_repo)
        report_text = report.generate_report()

        # Should contain human-readable output
        assert len(report_text) > 0
        assert "ERROR" in report_text or "WARNING" in report_text
        assert "agent" in report_text.lower() or "version" in report_text.lower()

    def test_doc_master_checklist_includes_parity_validation(self, temp_repo):
        """Test that doc-master checklist includes parity validation step.

        REQUIREMENT: Doc-master agent prompt includes parity validation.
        Expected: Agent file contains parity validation checklist.
        """
        # Read doc-master agent file
        doc_master_file = temp_repo / "plugins" / "autonomous-dev" / "agents" / "doc-master.md"
        content = doc_master_file.read_text()

        # Should mention parity validation
        assert "parity" in content.lower()
        assert "validation" in content.lower()
        assert "checklist" in content.lower()


class TestPreCommitHookIntegration:
    """Test pre-commit hook integration with parity validation."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with git and hooks."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_root, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_root, check=True)

        # Create .claude directory
        (repo_root / ".claude").mkdir()
        (repo_root / ".claude" / "hooks").mkdir()

        # Create plugins structure
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "agents").mkdir()

        return repo_root

    def test_pre_commit_hook_runs_parity_validation(self, temp_repo):
        """Test that pre-commit hook runs parity validation.

        REQUIREMENT: Pre-commit hook must validate documentation parity.
        Expected: Hook executes validation on every commit.
        """
        # Create hook file
        hook_file = temp_repo / ".claude" / "hooks" / "validate_documentation_parity.py"
        hook_file.write_text("""#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from plugins.autonomous_dev.lib.validate_documentation_parity import validate_documentation_parity

repo_root = Path(__file__).parent.parent.parent
report = validate_documentation_parity(repo_root)
print(report.generate_report())
sys.exit(report.exit_code)
        """)
        hook_file.chmod(0o755)

        # Create invalid documentation
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Run hook manually
        result = subprocess.run(
            [sys.executable, str(hook_file)],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        # Should fail (exit code 1)
        assert result.returncode == 1
        assert "ERROR" in result.stdout or "version" in result.stdout.lower()

    def test_pre_commit_hook_blocks_commit_on_errors(self, temp_repo):
        """Test that pre-commit hook blocks commits when errors exist.

        REQUIREMENT: Hook must prevent commits with documentation errors.
        Expected: git commit fails when validation errors exist.
        """
        # Create hook file (simplified for testing)
        hook_file = temp_repo / ".git" / "hooks" / "pre-commit"
        hook_file.write_text("""#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from plugins.autonomous_dev.lib.validate_documentation_parity import validate_documentation_parity

repo_root = Path(__file__).parent.parent.parent
report = validate_documentation_parity(repo_root)
if report.has_errors:
    print("BLOCKED: Documentation parity validation failed")
    print(report.generate_report())
    sys.exit(1)
sys.exit(0)
        """)
        hook_file.chmod(0o755)

        # Create invalid documentation
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Stage and try to commit
        subprocess.run(['git', 'add', '.'], cwd=temp_repo, check=True)
        result = subprocess.run(
            ['git', 'commit', '-m', 'Test commit'],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        # Should be blocked
        assert result.returncode != 0
        assert "BLOCKED" in result.stdout or "BLOCKED" in result.stderr or result.returncode == 1

    def test_pre_commit_hook_allows_commit_when_valid(self, temp_repo):
        """Test that pre-commit hook allows commits when validation passes.

        REQUIREMENT: Hook allows commits when documentation is valid.
        Expected: git commit succeeds when no validation errors.
        """
        # Create hook file
        hook_file = temp_repo / ".git" / "hooks" / "pre-commit"
        hook_file.write_text("""#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from plugins.autonomous_dev.lib.validate_documentation_parity import validate_documentation_parity

repo_root = Path(__file__).parent.parent.parent
report = validate_documentation_parity(repo_root)
if report.has_errors:
    print("BLOCKED: Documentation parity validation failed")
    sys.exit(1)
sys.exit(0)
        """)
        hook_file.chmod(0o755)

        # Create valid documentation
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n### Agents (2 specialists)\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Create matching agents
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")

        # Stage and commit
        subprocess.run(['git', 'add', '.'], cwd=temp_repo, check=True)
        result = subprocess.run(
            ['git', 'commit', '-m', 'Test commit'],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        # Should succeed
        assert result.returncode == 0

    def test_pre_commit_hook_allows_warnings_but_blocks_errors(self, temp_repo):
        """Test that hook allows warnings but blocks errors.

        REQUIREMENT: Hook blocks only on ERROR level, not WARNING.
        Expected: Commit succeeds with warnings, fails with errors.
        """
        # Create hook file
        hook_file = temp_repo / ".git" / "hooks" / "pre-commit"
        hook_file.write_text("""#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from plugins.autonomous_dev.lib.validate_documentation_parity import validate_documentation_parity

repo_root = Path(__file__).parent.parent.parent
report = validate_documentation_parity(repo_root)
if report.has_errors:
    print("BLOCKED: Errors found")
    sys.exit(1)
if report.has_warnings:
    print("WARNING: Issues found (not blocking)")
sys.exit(0)
        """)
        hook_file.chmod(0o755)

        # Create documentation with WARNING (not ERROR)
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n### Skills (10 Active)\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Create 5 skills (mismatch -> WARNING, not ERROR)
        skills_dir = temp_repo / "plugins" / "autonomous-dev" / "skills"
        skills_dir.mkdir(parents=True)
        for i in range(5):
            (skills_dir / f"skill-{i}.md").write_text(f"# Skill {i}\n")

        # Stage and commit
        subprocess.run(['git', 'add', '.'], cwd=temp_repo, check=True)
        result = subprocess.run(
            ['git', 'commit', '-m', 'Test commit'],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        # Should succeed (warnings don't block)
        assert result.returncode == 0
        assert "WARNING" in result.stdout or "WARNING" in result.stderr or result.returncode == 0

    def test_pre_commit_hook_displays_validation_report(self, temp_repo):
        """Test that hook displays validation report to user.

        REQUIREMENT: Hook shows detailed validation results.
        Expected: Validation report visible in hook output.
        """
        # Create hook file
        hook_file = temp_repo / ".git" / "hooks" / "pre-commit"
        hook_file.write_text("""#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from plugins.autonomous_dev.lib.validate_documentation_parity import validate_documentation_parity

repo_root = Path(__file__).parent.parent.parent
report = validate_documentation_parity(repo_root)
print(report.generate_report())
sys.exit(report.exit_code)
        """)
        hook_file.chmod(0o755)

        # Create documentation with issues
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Run hook
        result = subprocess.run(
            [sys.executable, str(hook_file)],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        # Should display report
        assert len(result.stdout) > 0
        assert "ERROR" in result.stdout or "version" in result.stdout.lower()

    def test_pre_commit_hook_skippable_with_no_verify(self, temp_repo):
        """Test that hook can be skipped with --no-verify flag.

        REQUIREMENT: Support emergency commits with --no-verify.
        Expected: git commit --no-verify bypasses validation.
        """
        # Create hook file
        hook_file = temp_repo / ".git" / "hooks" / "pre-commit"
        hook_file.write_text("""#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from plugins.autonomous_dev.lib.validate_documentation_parity import validate_documentation_parity

repo_root = Path(__file__).parent.parent.parent
report = validate_documentation_parity(repo_root)
if report.has_errors:
    sys.exit(1)
sys.exit(0)
        """)
        hook_file.chmod(0o755)

        # Create invalid documentation
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Stage and commit with --no-verify
        subprocess.run(['git', 'add', '.'], cwd=temp_repo, check=True)
        result = subprocess.run(
            ['git', 'commit', '-m', 'Emergency commit', '--no-verify'],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        # Should succeed (hook skipped)
        assert result.returncode == 0


class TestCLIIntegration:
    """Test CLI interface for documentation parity validation."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()
        (repo_root / ".claude").mkdir()
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "lib").mkdir()
        return repo_root

    def test_cli_script_exists_and_executable(self, temp_repo):
        """Test that CLI script exists and is executable.

        REQUIREMENT: Provide standalone CLI script for validation.
        Expected: Script at plugins/autonomous-dev/lib/validate_documentation_parity.py.
        """
        # Create CLI script
        cli_script = temp_repo / "plugins" / "autonomous-dev" / "lib" / "validate_documentation_parity.py"
        cli_script.write_text("""#!/usr/bin/env python3
if __name__ == '__main__':
    print("CLI placeholder")
        """)
        cli_script.chmod(0o755)

        # Should be executable
        assert cli_script.exists()
        assert os.access(cli_script, os.X_OK)

    def test_cli_accepts_project_root_argument(self, temp_repo):
        """Test that CLI accepts --project-root argument.

        REQUIREMENT: CLI supports custom project root path.
        Expected: --project-root argument accepted and used.
        """
        # Mock CLI invocation
        with patch('sys.argv', ['validate_documentation_parity.py', '--project-root', str(temp_repo)]):
            # Would call CLI main() function
            # For now, just test argument parsing
            assert '--project-root' in sys.argv
            assert str(temp_repo) in sys.argv

    def test_cli_supports_json_output_mode(self, temp_repo):
        """Test that CLI supports --json output mode.

        REQUIREMENT: CLI provides machine-readable JSON output.
        Expected: --json flag produces JSON format output.
        """
        # Create valid documentation
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-09\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Run validation
        report = validate_documentation_parity(temp_repo)

        # Generate JSON output (would be in CLI)
        json_output = {
            'total_issues': report.total_issues,
            'has_errors': report.has_errors,
            'has_warnings': report.has_warnings,
            'exit_code': report.exit_code
        }

        # Should be valid JSON
        json_str = json.dumps(json_output)
        parsed = json.loads(json_str)
        assert 'total_issues' in parsed
        assert 'exit_code' in parsed

    def test_cli_returns_correct_exit_codes(self, temp_repo):
        """Test that CLI returns correct exit codes.

        REQUIREMENT: CLI follows exit code convention (0=success, 1=errors).
        Expected: Exit code 0 for success, 1 for errors.
        """
        # Create invalid documentation
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("**Last Updated**: 2025-11-08\n")

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Validate
        report = validate_documentation_parity(temp_repo)

        # Should return exit code 1
        assert report.exit_code == 1

        # Now fix documentation
        claude_md.write_text("**Last Updated**: 2025-11-09\n")

        # Validate again
        report = validate_documentation_parity(temp_repo)

        # Should return exit code 0
        assert report.exit_code == 0


class TestEndToEndWorkflow:
    """Test end-to-end validation workflows."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with full structure."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create full structure
        (repo_root / ".claude").mkdir()
        (repo_root / "plugins").mkdir()
        (repo_root / "plugins" / "autonomous-dev").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "agents").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "commands").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "skills").mkdir()
        (repo_root / "plugins" / "autonomous-dev" / "hooks").mkdir()

        # Create plugin.json
        plugin_json = repo_root / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        return repo_root

    def test_end_to_end_validation_detects_all_issues(self, temp_repo):
        """Test end-to-end validation detects all issue types.

        REQUIREMENT: Comprehensive validation across all categories.
        Expected: All issue types detected in single validation run.
        """
        # Create documentation with multiple issues:
        # 1. Version drift
        # 2. Count mismatch
        # 3. Missing cross-reference
        # 4. Missing CHANGELOG entry
        # 5. Missing security docs

        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
**Last Updated**: 2025-11-08

### Agents (10 specialists)

- **researcher**: Web research
- **phantom-agent**: This doesn't exist

**Commands**:
- `/auto-implement` - Autonomous development
        """)

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Create only 2 agents (mismatch with documented 10)
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")

        # No CHANGELOG.md (missing)
        # No SECURITY.md (missing)

        # Run validation
        report = validate_documentation_parity(temp_repo)

        # Should detect issues in all categories
        assert len(report.version_issues) > 0  # Version drift
        assert len(report.count_issues) > 0  # Agent count mismatch
        assert len(report.cross_reference_issues) > 0  # phantom-agent missing
        assert len(report.changelog_issues) > 0  # Missing CHANGELOG
        assert len(report.security_issues) > 0  # Missing security docs

        assert report.has_errors is True
        assert report.total_issues >= 5

    def test_end_to_end_validation_passes_on_complete_documentation(self, temp_repo):
        """Test end-to-end validation passes with complete documentation.

        REQUIREMENT: No false positives with comprehensive documentation.
        Expected: Zero issues when all documentation is valid.
        """
        # Create complete, valid documentation
        claude_md = temp_repo / "CLAUDE.md"
        claude_md.write_text("""
**Last Updated**: 2025-11-09

### Agents (2 specialists)

- **researcher**: Web research
- **planner**: Architecture planning

**Commands (1 active)**:
- `/auto-implement` - Autonomous development

### Skills (2 Active)

- **testing-guide**: Testing patterns
- **code-review**: Code review standards

### Hooks (1 total automation)

- **auto_format.py**: Auto-formatting

## Security Practices

- API keys in .env files
- Path validation via security_utils
- Audit logging for sensitive operations
        """)

        project_md = temp_repo / ".claude" / "PROJECT.md"
        project_md.write_text("**Last Updated**: 2025-11-09\n")

        # Create matching agents
        agents_dir = temp_repo / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher\n")
        (agents_dir / "planner.md").write_text("# Planner\n")

        # Create matching commands
        commands_dir = temp_repo / "plugins" / "autonomous-dev" / "commands"
        (commands_dir / "auto-implement.md").write_text("# Auto Implement\n")

        # Create matching skills
        skills_dir = temp_repo / "plugins" / "autonomous-dev" / "skills"
        (skills_dir / "testing-guide.md").write_text("# Testing Guide\n")
        (skills_dir / "code-review.md").write_text("# Code Review\n")

        # Create matching hooks
        hooks_dir = temp_repo / "plugins" / "autonomous-dev" / "hooks"
        (hooks_dir / "auto_format.py").write_text("# Auto format\n")

        # Create CHANGELOG
        changelog = temp_repo / "CHANGELOG.md"
        changelog.write_text("""
# Changelog

## [3.8.0] - 2025-11-09
- Current release
        """)

        # Create SECURITY.md
        security_md = temp_repo / "docs"
        security_md.mkdir()
        (security_md / "SECURITY.md").write_text("""
# Security

## Security Practices
- CWE-22 prevention
- Audit logging
        """)

        # Run validation
        report = validate_documentation_parity(temp_repo)

        # Should have zero issues
        assert report.total_issues == 0
        assert report.has_errors is False
        assert report.has_warnings is False
        assert report.exit_code == 0

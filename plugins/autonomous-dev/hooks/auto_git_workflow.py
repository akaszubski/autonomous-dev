#!/usr/bin/env python3
"""
Auto Git Workflow Hook (SubagentStop lifecycle).

Triggers automatic git operations after quality-validator agent completes.

Workflow:
1. Check if quality-validator just completed (SubagentStop)
2. Check consent via environment variables
3. Read session file for workflow metadata
4. Invoke auto_implement_git_integration.execute_step8_git_operations()
5. Handle errors gracefully (non-blocking)

Environment Variables:
- AUTO_GIT_ENABLED: Master switch (default: false)
- AUTO_GIT_PUSH: Enable git push (default: false)
- AUTO_GIT_PR: Enable pull request creation (default: false)
- SESSION_FILE: Path to session JSON file (default: latest in docs/sessions/)

Security:
- CWE-22: Path traversal prevention via security_utils.validate_path()
- CWE-59: Symlink resolution via security_utils.validate_path()
- Audit logging: All security events logged to logs/security_audit.log

Date: 2025-11-09
Feature: Automatic git operations integration
Agent: implementer
Phase: TDD Green (implementation to make tests pass)
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(Path(__file__).parent.parent / "lib"),
)

from security_utils import validate_path, audit_log

# Import github_issue_closer for issue closing functionality (Issue #91)
try:
    from github_issue_closer import (
        extract_issue_number,
        validate_issue_state,
        generate_close_summary,
        close_github_issue,
        prompt_user_consent,
        IssueAlreadyClosedError,
        IssueNotFoundError,
        GitHubAPIError,
    )
    ISSUE_CLOSE_AVAILABLE = True
except ImportError:
    # Graceful degradation - issue closing not available
    ISSUE_CLOSE_AVAILABLE = False


# Alias for test compatibility
def log_audit_event(event: Dict[str, Any]) -> None:
    """
    Log audit event (alias for security_utils.audit_log).

    Provided for test compatibility and consistent naming.

    Args:
        event: Event dictionary with action, issue_number, status, etc.
    """
    audit_log(
        event_type=event.get('action', 'github_issue_operation'),
        status=event.get('status', 'unknown'),
        context=event,
    )


def should_trigger_git_workflow(agent_name: Optional[str]) -> bool:
    """
    Check if git workflow should trigger based on agent name.

    Only triggers for quality-validator (last agent in pipeline).

    Args:
        agent_name: Name of agent that just completed

    Returns:
        True if workflow should trigger, False otherwise

    Example:
        >>> should_trigger_git_workflow('quality-validator')
        True
        >>> should_trigger_git_workflow('researcher')
        False
    """
    if not agent_name:
        return False

    # Only trigger for quality-validator (last agent in workflow)
    return agent_name == 'quality-validator'


def check_git_workflow_consent() -> Dict[str, bool]:
    """
    Check user consent for git operations via environment variables.

    Environment Variables:
        AUTO_GIT_ENABLED: Master switch (true/yes/1)
        AUTO_GIT_PUSH: Enable push (true/yes/1)
        AUTO_GIT_PR: Enable PR creation (true/yes/1)

    Returns:
        Dict with consent flags:
        {
            'git_enabled': bool,      # Master switch
            'push_enabled': bool,     # Push consent
            'pr_enabled': bool,       # PR consent
            'all_enabled': bool       # All three enabled
        }

    Example:
        >>> os.environ['AUTO_GIT_ENABLED'] = 'true'
        >>> os.environ['AUTO_GIT_PUSH'] = 'yes'
        >>> check_git_workflow_consent()
        {'git_enabled': True, 'push_enabled': True, 'pr_enabled': False, 'all_enabled': False}
    """
    def parse_bool(value: str) -> bool:
        """Parse boolean from various formats (case-insensitive)."""
        return value.lower() in ('true', 'yes', '1')

    # Read environment variables
    git_enabled_raw = os.environ.get('AUTO_GIT_ENABLED', 'false')
    push_enabled_raw = os.environ.get('AUTO_GIT_PUSH', 'false')
    pr_enabled_raw = os.environ.get('AUTO_GIT_PR', 'false')

    # Parse consent (case-insensitive, supports true/yes/1)
    git_enabled = parse_bool(git_enabled_raw)
    push_enabled = parse_bool(push_enabled_raw) if git_enabled else False
    pr_enabled = parse_bool(pr_enabled_raw) if git_enabled else False

    # All enabled if all three are true
    all_enabled = git_enabled and push_enabled and pr_enabled

    return {
        'git_enabled': git_enabled,
        'push_enabled': push_enabled,
        'pr_enabled': pr_enabled,
        'all_enabled': all_enabled,
    }


def get_session_file_path() -> Path:
    """
    Get path to session file for workflow metadata.

    Checks SESSION_FILE environment variable first, otherwise finds latest
    session file in docs/sessions/ directory.

    Returns:
        Path to session file

    Raises:
        ValueError: If path validation fails (security)
        FileNotFoundError: If no session files found

    Security:
        - Validates path against whitelist (docs/sessions/, /tmp/)
        - Resolves symlinks to prevent TOCTOU attacks (CWE-59)
        - Logs security events to audit log

    Example:
        >>> os.environ['SESSION_FILE'] = '/path/to/session.json'
        >>> get_session_file_path()
        Path('/path/to/session.json')
    """
    session_file_env = os.environ.get('SESSION_FILE')

    if session_file_env:
        # Use explicit session file (validate security)
        session_path = Path(session_file_env).resolve()

        # Validate against whitelist (docs/sessions/ or /tmp/)
        # Note: validate_path allows project root and /tmp (in test mode)
        try:
            validated_path = validate_path(
                session_path,
                purpose='session file reading',
                allow_missing=True,  # May not exist yet
            )
        except ValueError as e:
            audit_log(
                event_type='session_file_path_validation',
                status='rejected',
                context={
                    'session_file': str(session_path),
                    'reason': str(e),
                    'source': 'SESSION_FILE environment variable',
                },
            )
            raise

        return validated_path

    # Find latest session file in docs/sessions/
    sessions_dir = Path.cwd() / 'docs' / 'sessions'

    if not sessions_dir.exists():
        raise FileNotFoundError(
            f'Sessions directory not found: {sessions_dir}\n'
            f'Expected: docs/sessions/ directory with session JSON files'
        )

    # Find all session files
    session_files = sorted(sessions_dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)

    if not session_files:
        raise FileNotFoundError(
            f'No session files found in {sessions_dir}\n'
            f'Expected: At least one *.json file in docs/sessions/'
        )

    latest_session = session_files[0]

    # Validate latest session file (should always pass for docs/sessions/)
    validated_path = validate_path(
        latest_session,
        purpose='session file reading',
        allow_missing=False,
    )

    return validated_path


def read_session_data(session_file: Path) -> Dict[str, Any]:
    """
    Read and parse session JSON file.

    Args:
        session_file: Path to session JSON file

    Returns:
        Parsed JSON data as dictionary

    Raises:
        ValueError: If JSON is invalid or file is empty
        FileNotFoundError: If file doesn't exist

    Security:
        - Validates file path before reading
        - Logs security events to audit log

    Example:
        >>> data = read_session_data(Path('session.json'))
        >>> data['workflow_id']
        'auto-implement-1234'
    """
    # Validate path before reading
    validated_path = validate_path(
        session_file,
        purpose='session file reading',
        allow_missing=False,
    )

    # Read file
    try:
        content = session_file.read_text(encoding='utf-8')
    except FileNotFoundError as e:
        audit_log(
            event_type='session_file_read',
            status='failed',
            context={
                'session_file': str(session_file),
                'reason': 'File not found',
            },
        )
        # Raise with user-friendly message (matches test expectation)
        raise FileNotFoundError(f'Session file not found: {session_file}') from e

    # Check for empty file
    if not content.strip():
        audit_log(
            event_type='session_file_read',
            status='failed',
            context={
                'session_file': str(session_file),
                'reason': 'Empty file',
            },
        )
        raise ValueError(f'Session file is empty: {session_file}')

    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        audit_log(
            event_type='session_file_read',
            status='failed',
            context={
                'session_file': str(session_file),
                'reason': f'Invalid JSON: {e}',
            },
        )
        raise ValueError(f'Invalid JSON in session file: {e}')

    audit_log(
        event_type='session_file_read',
        status='success',
        context={
            'session_file': str(session_file),
            'data_keys': list(data.keys()),
        },
    )

    return data


def extract_workflow_metadata(session_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract workflow metadata from session data.

    Args:
        session_data: Parsed session JSON

    Returns:
        Dict with workflow metadata:
        {
            'workflow_id': str,    # Workflow identifier
            'request': str,        # User's original request
        }

    Raises:
        ValueError: If required fields missing or empty

    Example:
        >>> data = {'workflow_id': 'auto-implement-1234', 'feature_request': 'Add auth'}
        >>> extract_workflow_metadata(data)
        {'workflow_id': 'auto-implement-1234', 'request': 'Add auth'}
    """
    # Check for workflow_id field
    if 'workflow_id' not in session_data:
        raise ValueError('workflow_id not found in session data')

    workflow_id = session_data['workflow_id']

    # Check workflow_id not empty BEFORE checking request (order matters for tests)
    if not workflow_id or not workflow_id.strip():
        raise ValueError('workflow_id cannot be empty')  # Match test expectation

    # Try 'feature_request' first (common format), fall back to 'request'
    # Use explicit None check to distinguish between missing and empty
    request = session_data.get('feature_request')
    if request is None:
        request = session_data.get('request')

    # Check if request exists (None means not found)
    if request is None:
        raise ValueError('feature_request not found in session data')  # Match test expectation

    # Check if request is empty (empty string or whitespace only)
    if not request.strip():
        raise ValueError('feature_request cannot be empty')  # Match test expectation

    return {
        'workflow_id': workflow_id.strip(),
        'request': request.strip(),
    }


def trigger_git_operations(
    workflow_metadata: Dict[str, str],
    consent: Dict[str, bool],
) -> Dict[str, Any]:
    """
    Trigger git operations via auto_implement_git_integration.

    Args:
        workflow_metadata: Workflow ID and request
        consent: Consent flags (git_enabled, push_enabled, pr_enabled)

    Returns:
        Result dict from execute_step8_git_operations():
        {
            'success': bool,
            'error': Optional[str],
            'details': dict,
        }

    Example:
        >>> metadata = {'workflow_id': 'auto-1234', 'request': 'Add auth'}
        >>> consent = {'git_enabled': True, 'push_enabled': True, 'pr_enabled': False}
        >>> result = trigger_git_operations(metadata, consent)
        >>> result['success']
        True
    """
    # Import here to avoid circular dependencies
    from auto_implement_git_integration import execute_step8_git_operations

    # Build environment variables for consent
    env_vars = {
        'AUTO_GIT_ENABLED': 'true' if consent['git_enabled'] else 'false',
        'AUTO_GIT_PUSH': 'true' if consent['push_enabled'] else 'false',
        'AUTO_GIT_PR': 'true' if consent['pr_enabled'] else 'false',
    }

    # Temporarily set environment variables
    old_env = {}
    for key, value in env_vars.items():
        old_env[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        # Execute git operations
        result = execute_step8_git_operations(
            workflow_id=workflow_metadata['workflow_id'],
            request=workflow_metadata['request'],
            push=consent['push_enabled'],
            create_pr=consent['pr_enabled'],
        )

        audit_log(
            event_type='git_operations_triggered',
            status='success' if result.get('success') else 'failed',
            context={
                'workflow_id': workflow_metadata['workflow_id'],
                'consent': consent,
                'result': result,
            },
        )

        return result

    finally:
        # Restore original environment variables
        for key, old_value in old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def handle_issue_close(command_args: str, workflow_metadata: Dict[str, Any]) -> bool:
    """
    Handle GitHub issue auto-close after successful git workflow.

    Workflow:
    1. Extract issue number from command args
    2. If no issue number, skip (graceful)
    3. Prompt user for consent
    4. If user declines, skip (graceful)
    5. Validate issue state (exists and open)
    6. If already closed, skip (idempotent)
    7. Generate close summary from workflow metadata
    8. Close issue via gh CLI
    9. Log audit event

    Args:
        command_args: Original command args from /auto-implement
        workflow_metadata: Workflow metadata from git operations
            Expected keys:
            - pr_url (optional): Pull request URL
            - commit_hash: Git commit hash
            - files_changed: List of changed file paths
            - agents_passed (optional): List of agent names

    Returns:
        True if issue closed successfully, False if skipped or failed

    Security:
        - CWE-20: Input validation via github_issue_closer
        - CWE-78: Command injection prevention via github_issue_closer
        - Audit logging: All operations logged

    Examples:
        >>> metadata = {'commit_hash': 'abc123', 'files_changed': ['file1.py']}
        >>> handle_issue_close("implement issue #8", metadata)
        True
        >>> handle_issue_close("implement feature", metadata)
        False  # No issue number, skipped
    """
    # Check if issue closing is available
    if not ISSUE_CLOSE_AVAILABLE:
        audit_log(
            event_type='handle_issue_close',
            status='skipped',
            context={
                'reason': 'github_issue_closer library not available',
            },
        )
        return False

    # STEP 1: Extract issue number from command args
    try:
        issue_number = extract_issue_number(command_args)
    except Exception as e:
        audit_log(
            event_type='handle_issue_close',
            status='failed',
            context={
                'step': 'extract_issue_number',
                'error': str(e),
            },
        )
        return False

    # STEP 2: If no issue number, skip gracefully
    if issue_number is None:
        audit_log(
            event_type='handle_issue_close',
            status='skipped',
            context={
                'reason': 'No issue number in command args',
                'command_args': command_args,
            },
        )
        return False

    # STEP 3: Prompt user for consent
    try:
        consent = prompt_user_consent(issue_number)
    except Exception as e:
        audit_log(
            event_type='handle_issue_close',
            status='failed',
            context={
                'step': 'prompt_user_consent',
                'issue_number': issue_number,
                'error': str(e),
            },
        )
        return False

    # STEP 4: If user declines, skip gracefully
    if not consent:
        audit_log(
            event_type='handle_issue_close',
            status='skipped',
            context={
                'reason': 'User declined consent',
                'issue_number': issue_number,
            },
        )
        return False

    # STEP 5: Validate issue state (exists and open)
    try:
        validate_issue_state(issue_number)
    except IssueAlreadyClosedError as e:
        # STEP 6: Already closed - idempotent success
        audit_log(
            event_type='handle_issue_close',
            status='already_closed',
            context={
                'issue_number': issue_number,
                'reason': str(e),
            },
        )
        return True  # Idempotent - already closed is success
    except (IssueNotFoundError, GitHubAPIError) as e:
        audit_log(
            event_type='handle_issue_close',
            status='failed',
            context={
                'step': 'validate_issue_state',
                'issue_number': issue_number,
                'error': str(e),
            },
        )
        return False
    except Exception as e:
        audit_log(
            event_type='handle_issue_close',
            status='failed',
            context={
                'step': 'validate_issue_state',
                'issue_number': issue_number,
                'error': str(e),
            },
        )
        return False

    # STEP 7: Generate close summary from workflow metadata
    try:
        summary = generate_close_summary(issue_number, workflow_metadata)
    except Exception as e:
        audit_log(
            event_type='handle_issue_close',
            status='failed',
            context={
                'step': 'generate_close_summary',
                'issue_number': issue_number,
                'error': str(e),
            },
        )
        return False

    # STEP 8: Close issue via gh CLI
    try:
        result = close_github_issue(issue_number, summary)

        # STEP 9: Log audit event for successful close
        log_audit_event({
            'action': 'handle_issue_close',
            'issue_number': issue_number,
            'status': 'success',
            'closed': result,
        })

        return result
    except (IssueNotFoundError, GitHubAPIError) as e:
        audit_log(
            event_type='handle_issue_close',
            status='failed',
            context={
                'step': 'close_github_issue',
                'issue_number': issue_number,
                'error': str(e),
            },
        )
        return False
    except Exception as e:
        audit_log(
            event_type='handle_issue_close',
            status='failed',
            context={
                'step': 'close_github_issue',
                'issue_number': issue_number,
                'error': str(e),
            },
        )
        return False


def run_hook(agent_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Main hook entry point (SubagentStop lifecycle).

    Args:
        agent_name: Name of agent that just completed

    Returns:
        Result dict:
        {
            'triggered': bool,        # Whether git workflow triggered
            'success': bool,          # Whether git operations succeeded
            'reason': str,           # Reason for skip or failure
            'details': dict,         # Additional details
        }

    Example:
        >>> os.environ['AUTO_GIT_ENABLED'] = 'true'
        >>> result = run_hook('quality-validator')
        >>> result['triggered']
        True
    """
    # Check if workflow should trigger
    if not should_trigger_git_workflow(agent_name):
        return {
            'triggered': False,
            'success': False,
            'reason': f'Not quality-validator agent (got: {agent_name})',
            'details': {},
        }

    # Check consent
    consent = check_git_workflow_consent()
    if not consent['git_enabled']:
        return {
            'triggered': False,
            'success': False,
            'reason': 'Git automation disabled (AUTO_GIT_ENABLED=false)',
            'details': {'consent': consent},
        }

    # Get session file path
    try:
        session_file = get_session_file_path()
    except (ValueError, FileNotFoundError) as e:
        audit_log(
            event_type='hook_execution',
            status='failed',
            context={
                'agent_name': agent_name,
                'reason': f'Session file error: {e}',
            },
        )
        return {
            'triggered': False,
            'success': False,
            'reason': f'Session file error: {e}',
            'details': {},
        }

    # Read session data
    try:
        session_data = read_session_data(session_file)
    except (ValueError, FileNotFoundError) as e:
        audit_log(
            event_type='hook_execution',
            status='failed',
            context={
                'agent_name': agent_name,
                'session_file': str(session_file),
                'reason': f'Session read error: {e}',
            },
        )
        return {
            'triggered': False,
            'success': False,
            'reason': f'Session read error: {e}',
            'details': {},
        }

    # Extract workflow metadata
    try:
        workflow_metadata = extract_workflow_metadata(session_data)
    except ValueError as e:
        audit_log(
            event_type='hook_execution',
            status='failed',
            context={
                'agent_name': agent_name,
                'session_file': str(session_file),
                'reason': f'Metadata extraction error: {e}',
            },
        )
        return {
            'triggered': False,
            'success': False,
            'reason': f'Metadata extraction error: {e}',
            'details': {},
        }

    # Trigger git operations
    try:
        result = trigger_git_operations(workflow_metadata, consent)

        # STEP 8.1: Handle issue closing (Issue #91)
        # Only attempt if git operations succeeded and push enabled
        issue_close_result = False
        if result.get('success') and consent.get('push_enabled'):
            # Extract command args from session data for issue number
            command_args = session_data.get('feature_request') or session_data.get('request', '')

            # Build metadata for close summary
            close_metadata = {
                'pr_url': result.get('pr_url'),
                'commit_hash': result.get('commit_sha'),
                'files_changed': result.get('files_changed', []),
                'agents_passed': [
                    'researcher',
                    'planner',
                    'test-master',
                    'implementer',
                    'reviewer',
                    'security-auditor',
                    'doc-master',
                ],
            }

            # Attempt to close issue (graceful degradation)
            try:
                issue_close_result = handle_issue_close(command_args, close_metadata)
            except Exception as e:
                # Log but don't fail the workflow
                audit_log(
                    event_type='handle_issue_close',
                    status='failed',
                    context={
                        'error': str(e),
                        'reason': 'Exception during issue close',
                    },
                )

        audit_log(
            event_type='hook_execution',
            status='success' if result.get('success') else 'failed',
            context={
                'agent_name': agent_name,
                'workflow_metadata': workflow_metadata,
                'consent': consent,
                'result': result,
                'issue_closed': issue_close_result,
            },
        )

        return {
            'triggered': True,
            'success': result.get('success', False),
            'reason': result.get('error') or result.get('reason', 'Git operations completed'),
            'details': result,  # Include full result (commit_sha, pr_url, etc.)
            'issue_closed': issue_close_result,
        }

    except Exception as e:
        audit_log(
            event_type='hook_execution',
            status='failed',
            context={
                'agent_name': agent_name,
                'workflow_metadata': workflow_metadata,
                'consent': consent,
                'reason': f'Git operations error: {e}',
            },
        )
        return {
            'triggered': True,
            'success': False,
            'reason': f'Git operations error: {e}',
            'details': {},
        }


def main() -> int:
    """
    CLI entry point for testing.

    Returns:
        Exit code (0=success, 1=error, 2=skipped)

    Environment Variables:
        AGENT_NAME: Name of agent that completed
        AUTO_GIT_ENABLED: Master switch
        AUTO_GIT_PUSH: Enable push
        AUTO_GIT_PR: Enable PR
        SESSION_FILE: Path to session file

    Example:
        $ export AGENT_NAME=quality-validator
        $ export AUTO_GIT_ENABLED=true
        $ python auto_git_workflow.py
    """
    agent_name = os.environ.get('AGENT_NAME')

    if not agent_name:
        print('Error: AGENT_NAME environment variable not set', file=sys.stderr)
        return 1

    try:
        result = run_hook(agent_name)

        if result['triggered']:
            if result['success']:
                print(f"Git workflow completed: {result['reason']}")
                return 0
            else:
                print(f"Git workflow failed: {result['reason']}", file=sys.stderr)
                return 1
        else:
            print(f"Git workflow skipped: {result['reason']}")
            return 0  # Skip is success, not error

    except Exception as e:
        print(f'Hook execution error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

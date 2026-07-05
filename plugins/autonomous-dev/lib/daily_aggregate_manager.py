"""Daily-aggregate issue lifecycle helper.

Living-aggregate semantics per (repo, prefix, UTC day):
- If today's aggregate open → gh issue edit N --body-file <tmp>
- Else → close any prior open (matching prefix, UTC day < today) with
         `--comment "Superseded by #NEW"`, then gh issue create.

Public API:
    open_or_supersede_daily_aggregate(*, repo, label, title_prefix, body,
                                     today_utc, gh_runner=subprocess.run)
"""

import subprocess
import json
import tempfile
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable


def _write_gh_issue_context(command: str = 'triage-aggregate') -> None:
    """Write the gh issue command context marker."""
    from datetime import datetime, timezone
    
    context_path = Path(os.getenv(
        "GH_ISSUE_CMD_CONTEXT_PATH",
        "/tmp/autonomous_dev_cmd_context.json"
    ))
    
    context = {
        'command': command,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    try:
        with open(context_path, 'w') as f:
            json.dump(context, f)
    except Exception:
        pass


def open_or_supersede_daily_aggregate(
    *,
    repo: str,
    label: str,
    title_prefix: str,
    body: str,
    today_utc: date,
    gh_runner: Callable = subprocess.run
) -> Dict[str, Any]:
    """Create or update daily aggregate issue with superseding semantics.
    
    Args:
        repo: GitHub repository in owner/repo format
        label: Label to apply to the issue
        title_prefix: Prefix for the issue title (date will be appended)
        body: Content for the issue body
        today_utc: UTC date to use for the aggregate
        gh_runner: Subprocess runner (injectable for testing)
    
    Returns:
        Dict with action (created/edited/superseded_and_created), 
        issue_number, and superseded list
    """
    today_title = f"{title_prefix} {today_utc.isoformat()}"
    superseded = []
    
    # Write marker before any gh commands
    _write_gh_issue_context('triage-aggregate')
    
    # List open issues with this label
    try:
        result = gh_runner(
            ['gh', 'issue', 'list', '--repo', repo, '--label', label, 
             '--state', 'open', '--json', 'number,title,createdAt'],
            check=True,
            text=True,
            capture_output=True,
            cwd=None
        )
        open_issues = json.loads(result.stdout) if result.stdout else []
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        open_issues = []
    
    # Find today's aggregate and older aggregates
    today_aggregate = None
    older_aggregates = []
    
    for issue in open_issues:
        title = issue.get('title', '')
        if title.startswith(title_prefix):
            # Extract date from title
            title_date_str = title[len(title_prefix):].strip()
            try:
                # Parse ISO date
                issue_date = date.fromisoformat(title_date_str)
                if issue_date == today_utc:
                    today_aggregate = issue
                elif issue_date < today_utc:
                    older_aggregates.append(issue)
            except ValueError:
                # Can't parse date, skip
                continue
    
    # If today's aggregate exists, edit it
    if today_aggregate:
        _write_gh_issue_context('triage-aggregate')
        
        # Write body to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(body)
            body_file = f.name
        
        try:
            gh_runner(
                ['gh', 'issue', 'edit', str(today_aggregate['number']),
                 '--repo', repo, '--body-file', body_file],
                check=True,
                text=True,
                capture_output=True,
                cwd=None
            )
            return {
                'action': 'edited',
                'issue_number': today_aggregate['number'],
                'superseded': []
            }
        finally:
            try:
                os.unlink(body_file)
            except OSError:
                pass
    
    # No today's aggregate - close older ones and create new
    
    # First close older aggregates
    for old_issue in older_aggregates:
        _write_gh_issue_context('triage-aggregate')
        try:
            # We'll create the new issue first, then update this comment
            superseded.append(old_issue['number'])
        except Exception:
            pass
    
    # Create new issue
    _write_gh_issue_context('triage-aggregate')
    
    # Write body to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(body)
        body_file = f.name
    
    try:
        result = gh_runner(
            ['gh', 'issue', 'create', '--repo', repo, '--title', today_title,
             '--label', label, '--body-file', body_file],
            check=True,
            text=True,
            capture_output=True,
            cwd=None
        )
        
        # Parse issue number from output (usually format: https://github.com/owner/repo/issues/123)
        match = re.search(r'/issues/(\d+)', result.stdout)
        new_issue_number = int(match.group(1)) if match else None
        
        if not new_issue_number:
            # Try to parse alternate format
            for line in result.stdout.split('\n'):
                if line.strip().isdigit():
                    new_issue_number = int(line.strip())
                    break
    finally:
        try:
            os.unlink(body_file)
        except OSError:
            pass
    
    # Now close the older aggregates with superseded comment
    for old_num in superseded:
        _write_gh_issue_context('triage-aggregate')
        try:
            gh_runner(
                ['gh', 'issue', 'close', str(old_num), '--repo', repo,
                 '--comment', f'Superseded by #{new_issue_number}'],
                check=True,
                text=True,
                capture_output=True,
                cwd=None
            )
        except subprocess.CalledProcessError:
            pass  # Best effort
    
    action = 'superseded_and_created' if superseded else 'created'
    
    return {
        'action': action,
        'issue_number': new_issue_number,
        'superseded': superseded
    }
"""Execute the command's actual public-field correlation without signing keys."""

import json
import os
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('command,mode', [('implement.md', 'full'), ('implement-fix.md', 'fix')])
@pytest.mark.parametrize('fault', ['valid', 'no_env_owner', 'missing', 'malformed', 'mode', 'issue', 'base', 'owner', 'run', 'override'])
def test_actual_command_correlation(tmp_path, command, mode, fault):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture'], check=True)
    base = subprocess.check_output(['git', '-C', str(tmp_path), 'rev-parse', 'HEAD'], text=True).strip()
    state = {'mode': mode, 'issue_number': 1807, 'subject': 'Repair native adoption', 'base_commit': base, 'session_id': 'native-owner', 'run_id': '1234567890abcdef'}
    path = tmp_path / '.claude/local/implement_pipeline_state.json'
    path.parent.mkdir(parents=True)
    env = dict(os.environ, ISSUE_NUMBER='1807', CLAUDE_SESSION_ID='native-owner')
    # Deny signing-key reads in the actual Python subprocess, not a mocked API.
    (tmp_path / 'sitecustomize.py').write_text(
        "import sys\n"
        "def deny_key_read(event, args):\n"
        "    if event == 'open' and 'pipeline_secrets' in str(args[0]):\n"
        "        raise PermissionError('model signing-key access denied')\n"
        "sys.addaudithook(deny_key_read)\n"
    )
    env['PYTHONPATH'] = str(tmp_path)
    denied = subprocess.run(
        ['python3', '-c', "open('pipeline_secrets/key').read()"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert denied.returncode != 0
    assert 'model signing-key access denied' in denied.stderr
    if fault == 'no_env_owner':
        env.pop('CLAUDE_SESSION_ID', None)
        env.pop('CLAUDE_CODE_SESSION_ID', None)
    env.pop('PIPELINE_STATE_FILE', None)
    for key, bad in [('mode', 'batch'), ('issue_number', 1818), ('base_commit', 'stale'), ('session_id', 'other-owner'), ('run_id', 'bad')]:
        if fault == {'issue_number': 'issue', 'base_commit': 'base', 'session_id': 'owner', 'run_id': 'run'}.get(key, key):
            state[key] = bad
    if fault != 'missing':
        path.write_text('{' if fault == 'malformed' else json.dumps(state))
    if fault == 'override':
        env['PIPELINE_STATE_FILE'] = str(tmp_path / 'other.json')
    text = (ROOT / 'plugins/autonomous-dev/commands' / command).read_text()
    marker = 'STEP 0' if command == 'implement.md' else 'F1'
    block = text.split(f'# NATIVE {marker} ADOPTION START', 1)[1].split(f'# NATIVE {marker} ADOPTION END', 1)[0]
    block = block.replace("'MODE'", "'full'")
    assert not re.search(r'from pipeline_|sign_state|record_run_start|check_native_origin|classify_current_run_authority|__MODEL_BOOTSTRAP__', block)
    before = path.read_bytes() if path.exists() else None
    result = subprocess.run(['bash', '-c', block + '\nprintf "%s" "$NATIVE_ADOPTION"'], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == (0 if fault in ('valid', 'no_env_owner') else 1), result.stderr
    assert (path.read_bytes() if path.exists() else None) == before
    if fault in ('valid', 'no_env_owner'):
        assert result.stdout == state['run_id']
    else:
        assert 'BLOCKED' in result.stderr
        assert 'do not write state here' in result.stderr

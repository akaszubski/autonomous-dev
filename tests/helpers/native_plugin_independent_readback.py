"""Next version of the outside readback: actual update, no native operation."""
import copy
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys

assert len(sys.argv) == 2 and re.fullmatch('[0-9a-f]{32}', sys.argv[1])
op = Path('/var/lib/adev-d0-native-consumer') / sys.argv[1]
case = json.loads((op / 'inputs/case.PUBLIC.json').read_text())
assert case['case'] == 'D0-R0-UPDATE-1'
assert case['baseline']['operation'] == '61a33d713b794460abc1fb0db07ef508'
root = op.parent / case['baseline']['operation'] / 'run'
report = json.loads(next(line for line in (op / 'outer.stdout').read_text().splitlines()
                         if line.startswith('{')))
assert report['status'] == 'UPDATE_AND_INSTALLED_R0_EXECUTION_ONLY'
prefix = report['output_prefix']
assert re.fullmatch('update-[0-9a-f]{32}-', prefix)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def local(relative):
    value = root / relative
    assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
    assert value.resolve().is_relative_to(root.resolve())
    assert not value.is_symlink()
    return value


def fact(path, identity=False):
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)
    result = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
    if path.is_file():
        result['sha256'] = digest(path)
    if identity:
        result['identity'] = [info.st_dev, info.st_ino, info.st_nlink, info.st_size,
                              info.st_mtime_ns, info.st_ctime_ns]
    return result


def preserved(before, after):
    if not before or set(before) != set(after):
        raise ValueError('PRESERVATION_DENOMINATOR')
    for name in before:
        if before[name] != after[name]:
            raise ValueError('FOREIGN_SETTING_CHANGED:' + name)


def contains(actual, expected):
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and expected
        for key, value in expected.items():
            assert key in actual
            contains(actual[key], value)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and expected and all(item in actual for item in expected)
    else:
        assert actual == expected


assert digest(op / 'inputs/instruments/trustcheck.py') == case['pins']['trustcheck.py']
assert digest(op / 'inputs/instruments/oracle.sh') == case['pins']['oracle.sh']
assert [row['case'] for row in report['cases']] == ['permit', 'refuse', 'permit-restored']
entry = json.loads((root / 'config/plugins/installed_plugins.json').read_text())['plugins'][case['plugin_id']][0]
inside = Path(entry['installPath'])
assert entry['scope'] == 'user' and str(inside).endswith('/3.8.0-r0.2')
assert inside.is_relative_to('/work/config/plugins/cache')
installed = local(str(inside.relative_to('/work')))
assert sorted(str(p.relative_to(installed)) for p in installed.rglob('*') if p.is_file()) == [
    '.claude-plugin/plugin.json', 'scripts/control_evidence.py']
assert not any(p.is_symlink() for p in installed.rglob('*'))
leaf = installed / 'scripts/control_evidence.py'
assert digest(leaf) == case['pins']['leaf']
assert digest(installed / '.claude-plugin/plugin.json') == case['pins']['manifest']
assert json.loads((installed / '.claude-plugin/plugin.json').read_text())['version'] == '3.8.0-r0.2'
nonces = set()
results = []
for row, decision, code in zip(report['cases'], ['PASS', 'FAIL', 'PASS'], [0, 1, 0]):
    candidate = local(row['receipt'])
    oracle = local(row['oracle'])
    assert digest(candidate) == row['receipt_sha256'] and digest(oracle) == row['oracle_sha256']
    receipt = json.loads(candidate.read_text())
    obs = receipt['observation']
    nonce = obs['nonce']
    assert re.fullmatch('[0-9a-f]{32}', nonce) and nonce == row['nonce'] and nonce not in nonces
    nonces.add(nonce)
    subject = 'refuse' if row['case'] == 'refuse' else 'permit'
    target_relative = f'subjects/{prefix}/{subject}/test_subject.py'
    assert obs['target'] == row['target'] == '/work/' + target_relative
    target = local(target_relative)
    manifest = target.parent / 'cases.json'
    assert receipt['decision'] == row['decision'] == decision and obs['run_exit'] == row['raw_exit'] == code
    assert obs['selected'] == ['test_subject.py::test_value'] and obs['cleanup_complete']
    pins = {'case_manifest': digest(manifest), 'verifier': digest(leaf),
            'python': digest(Path(case['tools']['python']['path']).resolve()), 'subject': digest(target)}
    args = ['/usr/bin/python3', '-I', '-S', '-B', str(op / 'inputs/instruments/trustcheck.py'),
            'compare', '--oracle', str(oracle), '--candidate', str(candidate), '--nonce', nonce,
            '--expect-case', 'installed-r0', '--expect-tool-version', 'control-evidence-1',
            '--expect-subject-digest', digest(target), '--expect-dependency-digests', json.dumps(pins)]
    checked = subprocess.run(args, cwd=op, env={'PATH': '/usr/bin:/bin'},
                             capture_output=True, timeout=10, check=True)
    assert checked.stdout.startswith(b'OK')
    results.append({'case': row['case'], 'decision': decision,
                    'receipt': digest(candidate), 'oracle': digest(oracle)})
broken = report['broken_route']
assert broken['raw_exit'] == 2 and not local(broken['stdout']).read_bytes()
assert digest(local(broken['stdout'])) == broken['stdout_sha256']
assert digest(local(broken['stderr'])) == broken['stderr_sha256']
assert str(inside / 'scripts/control_evidence.py') in local(broken['stderr']).read_text()
assert leaf.stat().st_nlink == 1


def git(repo, *arguments):
    args = ['/usr/bin/git', '-c', 'safe.directory=' + str(repo), '-C', str(repo), *arguments]
    checked = subprocess.run(args, cwd=op, env={'PATH': '/usr/bin:/bin',
        'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_OPTIONAL_LOCKS': '0'},
        capture_output=True, timeout=5, check=True)
    assert not checked.stderr and len(checked.stdout) <= 65536
    return checked.stdout


catalogue_inside = Path(report['update']['catalogue_root'])
assert catalogue_inside.is_relative_to('/work/config/plugins/marketplaces')
catalogue = local(str(catalogue_inside.relative_to('/work')))
commit = git(local('seed'), 'rev-parse', 'HEAD').decode().strip()
assert re.fullmatch('[0-9a-f]{40}', commit)
assert commit == report['update']['new_commit'] == report['update']['catalogue_commit']
assert git(catalogue, 'rev-parse', 'HEAD').decode().strip() == commit
assert git(local('origin.git'), 'rev-parse', 'HEAD').decode().strip() == commit
assert git(catalogue, 'ls-tree', '-r', '--name-only', 'HEAD:plugins/autonomous-dev').decode().splitlines() == [
    '.claude-plugin/plugin.json', 'scripts/control_evidence.py']
for name in ('.claude-plugin/plugin.json', 'scripts/control_evidence.py'):
    blob = git(catalogue, 'cat-file', 'blob', 'HEAD:plugins/autonomous-dev/' + name)
    assert hashlib.sha256(blob).hexdigest() == digest(installed / name)
registry_sha = entry.get('gitCommitSha')
registry_identity = ('MATCH' if registry_sha == commit else
                     'CONFLICTED' if registry_sha else 'UNMEASURED')
assert report['update']['registry_commit_identity'] == registry_identity
calls = report['update']['native_calls']
expected_calls = [
    [case['tools']['cli']['path'], 'plugin', 'marketplace', 'update', 'adev-d0-native-consumer'],
    [case['tools']['cli']['path'], 'plugin', 'update', case['plugin_id'], '--scope', 'user'],
]
assert len(calls) == len(expected_calls)
for call, expected in zip(calls, expected_calls):
    assert call['argv'] == expected and call['cwd'] == '/work/' + prefix + 'consumer'
    assert call['raw_exit'] == 0
    assert local(call['stdout']).is_file() and local(call['stderr']).is_file()
assert report['update']['preservation_file'] == prefix + 'preservation.json'
snapshot = json.loads(local('private/' + report['update']['preservation_file']).read_text())
assert snapshot['new_commit'] == commit
consumer = prefix + 'consumer'
expected_paths = {'config/settings.json', f'{consumer}/.claude/settings.json',
                  f'{consumer}/.claude/settings.local.json', f'{consumer}/unrelated.txt'}
before = snapshot['foreign_before']
assert set(before) == expected_paths
foreign = case['foreign']
assert all(isinstance(foreign[k], dict) and foreign[k] for k in ('user', 'repo', 'local'))
assert isinstance(foreign['unrelated'], str) and foreign['unrelated']
assert any(v.get('permissions', {}).get('allow') for v in [foreign[k] for k in ('user', 'repo', 'local')])
assert any(v.get('permissions', {}).get('deny') for v in [foreign[k] for k in ('user', 'repo', 'local')])
assert any(v.get('hooks') for v in [foreign[k] for k in ('user', 'repo', 'local')])
assert any(v.get('env') for v in [foreign[k] for k in ('user', 'repo', 'local')])
for key, path in [('user', 'config/settings.json'), ('repo', f'{consumer}/.claude/settings.json'),
                  ('local', f'{consumer}/.claude/settings.local.json')]:
    contains(json.loads(local(path).read_text()), foreign[key])
assert local(f'{consumer}/unrelated.txt').read_text() == foreign['unrelated']
assert local(f'{consumer}/.git').is_dir()
after = {name: fact(local(name)) for name in before}
preserved(before, after)
mutant = copy.deepcopy(after)
mutant['config/settings.json']['sha256'] = '0' * 64
try:
    preserved(before, mutant)
except ValueError as error:
    assert str(error) == 'FOREIGN_SETTING_CHANGED:config/settings.json'
else:
    raise AssertionError('Bad settings observation was permitted')
for category in ('old_cache_before', 'retained_before'):
    assert snapshot[category]
    assert snapshot[category] == {name: fact(local(name), identity=True) for name in snapshot[category]}
unit = 'adev-d0-acquire-' + op.name + '.service'
assert not (Path('/sys/fs/cgroup/system.slice') / unit).exists()
assert not (Path('/run/systemd/system') / (unit + '.d')).exists()
actors = subprocess.run(['/bin/ps', '-eo', 'uid=,pid='], capture_output=True, text=True, check=True).stdout
assert not [line for line in actors.splitlines() if line.split()[0] == '999']
result = {'status': 'INDEPENDENT_NATIVE_UPDATE_READBACK_PASS', 'operation': op.name,
          'baseline_operation': case['baseline']['operation'], 'installed_root': str(inside),
          'cases': results, 'foreign_settings_preserved': True, 'old_cache_preserved': True,
          'bad_settings_observation_refused': True, 'cleanup': True,
          'catalogue_commit': commit, 'registry_commit_identity': registry_identity,
          'native_hooks_loaded': 'UNMEASURED'}
(op / 'INDEPENDENT-UPDATE-READBACK.PUBLIC.json').write_text(json.dumps(result, sort_keys=True) + '\n')
print(json.dumps(result, sort_keys=True))

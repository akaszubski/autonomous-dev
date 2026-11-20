"""Next version of the outside readback: actual update, no native operation."""
import copy
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile

assert len(sys.argv) == 2 and re.fullmatch('[0-9a-f]{32}', sys.argv[1])
op = Path('/var/lib/adev-d0-native-consumer') / sys.argv[1]
case = json.loads((op / 'inputs/case.PUBLIC.json').read_text())
UNINSTALL = case['case'] == 'D0-R0-UNINSTALL-1'
FRESH = case['case'] == 'D0-R0-ACQUIRE-1'
assert FRESH or case['case'] in ('D0-R0-UPDATE-1', 'D0-R0-UNINSTALL-1')
if UNINSTALL or FRESH:
    root = op / 'run'
else:
    assert case['baseline']['operation'] == '61a33d713b794460abc1fb0db07ef508'
    root = op.parent / case['baseline']['operation'] / 'run'
lines = (op / 'outer.stdout').read_text().splitlines()
report = json.loads(next(line for line in lines if line.startswith('{')))
meta = dict(line.split('=', 1) for line in lines if '=' in line and not line.startswith('{'))
unit = 'adev-d0-acquire-' + op.name + '.service'
assert meta['Id'] == unit and re.fullmatch('[0-9a-f]{32}', meta['InvocationID'])
assert meta['ControlGroup'] == '/system.slice/' + unit
assert meta['Result'] == 'success' and meta['ExecMainStatus'] == '0'
assert meta['TypedCredentialsEmpty'] == 'yes'
for key in ('NoNewPrivileges', 'ProtectHome', 'PrivateTmp', 'PrivateDevices',
            'PrivateNetwork', 'ProtectControlGroups', 'ProtectKernelTunables', 'ProtectKernelModules'):
    assert meta[key] == 'yes'
assert meta['ProtectSystem'] == 'strict'

assert report['status'] == ('NATIVE_UNINSTALL_SELECTION_ONLY' if UNINSTALL else 'ACQUISITION_AND_INSTALLED_R0_EXECUTION_ONLY' if FRESH else 'UPDATE_AND_INSTALLED_R0_EXECUTION_ONLY')
prefix = report['output_prefix']
assert prefix == '' if FRESH else re.fullmatch(('uninstall-' if UNINSTALL else 'update-') + '[0-9a-f]{32}-', prefix)


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
    if identity and path.is_file():
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


def cleanup():
    current = subprocess.run(['/usr/bin/systemctl', 'show', '--all', unit,
        '--property=Id,ActiveState,MainPID,LoadState'], capture_output=True, text=True)
    state = dict(line.split('=', 1) for line in current.stdout.splitlines() if '=' in line)
    assert state['Id'] == unit and state['ActiveState'] == 'inactive' and state['MainPID'] == '0'
    assert current.returncode == 0 or (current.returncode == 1 and state['LoadState'] == 'not-found')
    assert not (Path('/sys/fs/cgroup/system.slice') / unit).exists()
    assert not (Path('/run/systemd/system') / (unit + '.d')).exists()
    actors = subprocess.run(['/bin/ps', '-eo', 'uid=,pid='], capture_output=True, text=True, check=True).stdout
    assert not [line for line in actors.splitlines() if line.split()[0] == '999']


def select(rows):
    assert type(rows) is list
    found = [row for row in rows if row['id'] == case['plugin_id'] and row['scope'] == 'user']
    assert len(found) <= 1
    return found[0] if found else None

nonces = set()
results = []
def compare_case(row, decision, code):
    candidate = local(row['receipt'])
    oracle = local(row['oracle'])
    assert digest(candidate) == row['receipt_sha256'] and digest(oracle) == row['oracle_sha256']
    receipt = json.loads(candidate.read_text())
    obs = receipt['observation']
    nonce = obs['nonce']
    assert re.fullmatch('[0-9a-f]{32}', nonce) and nonce == row['nonce'] and nonce not in nonces
    nonces.add(nonce)
    subject = 'refuse' if row['case'] == 'refuse' else 'permit'
    target_relative = str(Path('subjects') / prefix / subject / 'test_subject.py')
    assert obs['target'] == row['target'] == '/work/' + target_relative
    target = local(target_relative)
    manifest = target.parent / 'cases.json'
    assert receipt['decision'] == row['decision'] == decision and obs['run_exit'] == row['raw_exit'] == code
    assert obs['selected'] == ['test_subject.py::test_value'] and obs['cleanup_complete']
    pins = {'case_manifest': digest(manifest), 'verifier': case['pins']['leaf'],
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



if UNINSTALL:
    assert digest(op / 'inputs/case.PUBLIC.json') == 'd336ffef59a3b1a39f6d2af4e788772c608ac7c9ac7564522ad6aa395a912cc3'
    assert digest(op / 'inputs/operator.py') == case['operator_sha256']
    assert digest(op / 'inputs/instruments/trustcheck.py') == case['pins']['trustcheck.py']
    assert digest(op / 'inputs/instruments/oracle.sh') == case['pins']['oracle.sh']
    assert digest(op / 'inputs/payload.tar') == case['pins']['archive']
    foreign_path = op / 'inputs/foreign-case.json'
    assert digest(foreign_path) == case['foreign_fixture_sha256']
    foreign = json.loads(foreign_path.read_text())['foreign']
    calls = report['native_calls'][-3:]
    expected = [['plugin', 'list', '--json'], ['plugin', 'uninstall', case['plugin_id'], '--scope', 'user'], ['plugin', 'list', '--json']]
    assert len(calls) == 3
    for call, tail in zip(calls, expected):
        assert call['argv'] == [case['tools']['cli']['path'], *tail]
        assert call['cwd'] == '/work/' + prefix + 'consumer' and call['raw_exit'] == 0
    before = select(json.loads(local(report['before_inventory']).read_text()))
    assert before and before['version'] == '3.8.0-r0.2' and before['enabled'] is True
    assert select(json.loads(local(report['after_inventory']).read_text())) is None
    assert before['installPath'] == report['installed_root']
    selected = Path(before['installPath'])
    assert selected.is_relative_to('/work/config/plugins/cache')
    saved = json.loads(local('private/' + report['preservation_file']).read_text())
    assert saved['selected_before'] == before
    assert len(report['cases']) == 1
    row = report['cases'][0]
    assert row['case'] == 'permit'
    assert saved['installed_before'][str((selected / 'scripts/control_evidence.py').relative_to('/work'))]['sha256'] == case['pins']['leaf']
    assert saved['installed_before'][str((selected / '.claude-plugin/plugin.json').relative_to('/work'))]['sha256'] == case['pins']['manifest']
    compare_case(row, 'PASS', 0)
    consumer = prefix + 'consumer'
    assert set(saved['foreign_before']) == {'config/settings.json', f'{consumer}/.claude/settings.json', f'{consumer}/.claude/settings.local.json', f'{consumer}/unrelated.txt'}
    user_before = json.loads(saved['user_before_text'])
    user_after = json.loads(local('config/settings.json').read_text())
    contains(user_before, foreign['user'])
    contains(user_after, foreign['user'])
    assert user_before['enabledPlugins'].pop(case['plugin_id']) is True
    assert case['plugin_id'] not in user_after.get('enabledPlugins', {})
    for value in (user_before, user_after):
        if not value.get('enabledPlugins'):
            value.pop('enabledPlugins', None)
    assert user_before == user_after
    for name, expected_fact in saved['foreign_before'].items():
        actual = fact(local(name))
        if name == 'config/settings.json':
            expected_fact = expected_fact.copy()
            expected_fact.pop('sha256')
            actual.pop('sha256')
        preserved({name: expected_fact}, {name: actual})
    assert json.loads(local(f'{consumer}/.claude/settings.json').read_text()) == foreign['repo']
    assert json.loads(local(f'{consumer}/.claude/settings.local.json').read_text()) == foreign['local']
    assert local(f'{consumer}/unrelated.txt').read_text() == foreign['unrelated']
    cleanup()
    result = {'status': 'NATIVE_UNINSTALL_SELECTION_ASSESSMENT_PASS', 'operation': op.name,
        'before_selected': True, 'after_selected': False, 'permit_before': 'PASS', 'foreign_settings_preserved': True,
        'owned_data': 'UNMEASURED_NO_PRODUCT_STORE', 'historical_cache_eradication': 'NOT_CLAIMED', 'native_hooks_loaded': 'UNMEASURED'}
    (op / 'INDEPENDENT-UNINSTALL.PUBLIC.json').write_text(json.dumps(result, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))
    sys.exit(0)


assert digest(op / 'inputs/operator.py') == ('f77020adf56d3966622a71b7ec630c0b5691cddbc879f028eefd7ef58b0d95f9' if FRESH else '808a29678d820fe0bfcce073f71045a579d6d74eee74e76dcfbae89344ac0ab3')
assert digest(op / 'inputs/case.PUBLIC.json') == ('5ffba955514e94cc808302b1ca650423665369b58a784a71ec08e225e83a8072' if FRESH else '65fb0df3db245d54dfd45aed0e38573d35bc3bcd89ae5e9e2043cd355c366388')
assert digest(op / 'inputs/payload.tar') == case['pins']['archive']
assert digest(op / 'inputs/instruments/trustcheck.py') == case['pins']['trustcheck.py']
assert digest(op / 'inputs/instruments/oracle.sh') == case['pins']['oracle.sh']
assert [row['case'] for row in report['cases']] == ['permit', 'refuse', 'permit-restored']
entries = json.loads((root / 'config/plugins/installed_plugins.json').read_text())['plugins'][case['plugin_id']]
assert len(entries) == 1
entry = entries[0]
inside = Path(entry['installPath'])
version = '3.8.0-r0.1' if FRESH else '3.8.0-r0.2'
assert entry['scope'] == 'user' and entry['version'] == version and inside.name == version
assert inside.is_relative_to('/work/config/plugins/cache')
installed = local(str(inside.relative_to('/work')))
assert installed.resolve().is_relative_to(local('config/plugins/cache').resolve())
assert sorted(str(p.relative_to(installed)) for p in installed.rglob('*') if p.is_file()) == [
    '.claude-plugin/plugin.json', 'scripts/control_evidence.py']
assert not any(p.is_symlink() for p in installed.rglob('*'))
leaf = installed / 'scripts/control_evidence.py'
assert digest(leaf) == case['pins']['leaf']
assert digest(installed / '.claude-plugin/plugin.json') == case['pins']['manifest']
for row, decision, code in zip(report['cases'], ['PASS', 'FAIL', 'PASS'], [0, 1, 0]):
    compare_case(row, decision, code)
broken = report['broken_route']
assert broken['raw_exit'] == 2 and not local(broken['stdout']).read_bytes()
assert digest(local(broken['stdout'])) == broken['stdout_sha256']
assert digest(local(broken['stderr'])) == broken['stderr_sha256']
assert str(inside / 'scripts/control_evidence.py') in local(broken['stderr']).read_text()
assert leaf.stat().st_nlink == 1 and leaf.stat().st_ino == report['restored_leaf_inode']


def git(repo, *arguments):
    args = ['/usr/bin/git', '-c', 'safe.directory=' + str(repo), '-C', str(repo), *arguments]
    checked = subprocess.run(args, cwd=op, env={'PATH': '/usr/bin:/bin',
        'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_OPTIONAL_LOCKS': '0'},
        capture_output=True, timeout=5, check=True)
    assert not checked.stderr and len(checked.stdout) <= 65536
    return checked.stdout


if FRESH:
    expected_calls = [['marketplace', 'add', case['url']], ['install', case['plugin_id'], '--scope', 'user']]
    assert len(report['native_calls']) == len(expected_calls)
    for index, (call, tail) in enumerate(zip(report['native_calls'], expected_calls)):
        assert call['argv'] == [case['tools']['cli']['path'], 'plugin', *tail]
        assert call['cwd'] == '/work/foreign'
        assert call['raw_exit'] == 0
    catalogue = local('config/plugins/marketplaces/adev-d0-native-consumer')
    head = git(local('seed'), 'rev-parse', 'HEAD').decode().strip()
    assert git(local('origin.git'), 'rev-parse', 'HEAD').decode().strip() == head
    assert git(catalogue, 'rev-parse', 'HEAD').decode().strip() == head
    baseline = head
    with tarfile.open(op / 'inputs/payload.tar') as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        assert len(members) == 3
        for member in members:
            assert git(catalogue, 'cat-file', 'blob', baseline + ':' + member.name) == archive.extractfile(member).read()
            assert git(catalogue, 'ls-tree', baseline, '--', member.name).decode().split()[0] == ('100755' if member.mode & 0o111 else '100644')
            if member.name.startswith('plugins/autonomous-dev/'):
                observed = fact(installed / member.name.removeprefix('plugins/autonomous-dev/'))
                assert (observed['mode'], observed['uid'], observed['gid']) == (member.mode & 0o700, 999, 990)
    cleanup()
    print(json.dumps({'status': 'ACQUIRE_REPLACEMENT_OBSERVED', 'operation': op.name,
        'installed_root': str(inside), 'version': version, 'leaf_sha256': digest(leaf),
        'manifest_sha256': digest(installed / '.claude-plugin/plugin.json'), 'cases': results,
        'restored_leaf_inode': leaf.stat().st_ino, 'broken_route_refused': True,
        'invocation_id': meta['InvocationID'], 'cleanup_verified': True, 'native_hooks_loaded': 'UNMEASURED'}))
    sys.exit(0)


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
with tarfile.open(op / 'inputs/payload.tar') as archive:
    for member in archive.getmembers():
        if member.isfile():
            assert git(catalogue, 'cat-file', 'blob', 'HEAD:' + member.name) == archive.extractfile(member).read()
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
held_path = op / 'OLD-CONSUMER.BEFORE.PUBLIC.json'
info = held_path.lstat()
assert stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
assert not info.st_mode & 0o022
held = json.loads(held_path.read_text())
assert hashlib.sha256(held['registry_text'].encode()).hexdigest() == held['registry_sha256']
old_entries = json.loads(held['registry_text'])['plugins'][case['plugin_id']]
assert len(old_entries) == 1 and old_entries[0]['scope'] == 'user'
assert old_entries[0]['installPath'] == case['baseline']['cache']
assert old_entries[0]['version'] == '3.8.0-r0.1'
old_root = str(Path(case['baseline']['cache']).relative_to('/work'))
old_members = {old_root, old_root + '/.claude-plugin', old_root + '/scripts',
               old_root + '/.claude-plugin/plugin.json', old_root + '/scripts/control_evidence.py'}
assert old_members <= set(held['old_cache_before'])
assert {name for name, value in held['old_cache_before'].items() if 'sha256' in value} == {
    old_root + '/.claude-plugin/plugin.json', old_root + '/scripts/control_evidence.py'}
actual_old_members = {old_root, *(str(p.relative_to(root)) for p in local(old_root).rglob('*'))}
assert set(held['old_cache_before']) <= actual_old_members
additions = {}
for name in sorted(actual_old_members - set(held['old_cache_before'])):
    path = local(name)
    if path.is_file():
        assert path.stat().st_nlink == 1 and path.stat().st_size <= 131072
    additions[name] = fact(path)
    additions[name]['type'] = 'file' if path.is_file() else 'directory'
    additions[name]['size'] = path.stat().st_size

for category in ('old_cache_before', 'retained_before'):
    preserved(held[category], snapshot[category])
    preserved(held[category], {name: fact(local(name), identity=True) for name in held[category]})
omitted = copy.deepcopy(snapshot['old_cache_before'])
del omitted[old_root + '/scripts/control_evidence.py']
try:
    preserved(held['old_cache_before'], omitted)
except ValueError as error:
    assert str(error) == 'PRESERVATION_DENOMINATOR'
else:
    raise AssertionError('Omitted old-cache entry was permitted')
old_inputs = json.loads((op / 'OLD-INPUTS.BEFORE.PUBLIC.json').read_text())
assert old_inputs
for relative, expected in old_inputs.items():
    path = root.parent / relative
    assert path.resolve().is_relative_to(root.parent / 'inputs') and not path.is_symlink()
    assert [digest(path), path.stat().st_mode] == expected
cleanup()
result = {'status': 'AMENDED_IDLE_UPDATE_PRESERVATION_ASSESSMENT_PASS', 'operation': op.name,
          'unit_invocation': meta['InvocationID'], 'native_service_result': 'success',
          'original_root_assessment': 'FAILED_OLD_EXACT_TREE_CONTRACT_RETAINED',
          'inactive_old_cache_additions': additions, 'addition_writer_provenance': 'UNKNOWN',
          'old_generation_reuse_rollback_active_safety': 'UNQUALIFIED',
          'baseline_operation': case['baseline']['operation'], 'installed_root': str(inside),
          'cases': results, 'foreign_settings_preserved': True, 'old_cache_preserved': True,
          'bad_settings_observation_refused': True, 'omitted_old_cache_entry_refused': True,
          'old_registry_admitted': True, 'cleanup': True,
          'catalogue_commit': commit, 'registry_commit_identity': registry_identity,
          'native_hooks_loaded': 'UNMEASURED'}
(op / 'INDEPENDENT-UPDATE-REASSESSMENT.PUBLIC.json').write_text(json.dumps(result, sort_keys=True) + '\n')
print(json.dumps(result, sort_keys=True))

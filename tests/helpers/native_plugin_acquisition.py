"""One disposable D0 R0-family acquisition case; no native model session."""
import hashlib
import json
import os
import resource
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

assert len(sys.argv) == 2, 'one outside-owned case record is required'
case_fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
try:
    case_stat = os.fstat(case_fd)
    assert stat.S_ISREG(case_stat.st_mode) and case_stat.st_uid == 0
    assert case_stat.st_gid == 0 and stat.S_IMODE(case_stat.st_mode) == 0o444
    assert case_stat.st_nlink == 1 and case_stat.st_size <= 8192
    case_raw = os.read(case_fd, 8193)
finally:
    os.close(case_fd)
CASE = json.loads(case_raw)
IDEMPOTENT = CASE['case'] == 'D0-R0-IDLE-IDEMPOTENCE-1'
RECOVERY = CASE['case'] == 'D0-R0-RECOVERY-1'
if RECOVERY or IDEMPOTENT:
    assert set(CASE) == {'case', 'fixture_sha256', 'operator_sha256', 'baseline'}
    fixture = (Path('/work') / 'foreign-case.json').read_bytes()
    assert len(fixture) <= 8192 and hashlib.sha256(fixture).hexdigest() == CASE.pop('fixture_sha256')
    CASE = dict(json.loads(fixture), **CASE)
UPDATE = CASE['case'] == 'D0-R0-UPDATE-1' or RECOVERY or IDEMPOTENT
UNINSTALL = CASE['case'] == 'D0-R0-UNINSTALL-1'
assert CASE['case'] in ('D0-R0-ACQUIRE-1', 'D0-R0-UPDATE-1', 'D0-R0-UNINSTALL-1', 'D0-R0-RECOVERY-1', 'D0-R0-IDLE-IDEMPOTENCE-1')
assert set(CASE) == {'case', 'root', 'tools', 'versions', 'pins', 'plugin_id', 'url'} | ({'baseline', 'foreign', 'operator_sha256'} if RECOVERY or IDEMPOTENT else {'baseline', 'foreign'} if UPDATE else {'foreign_fixture_sha256', 'operator_sha256'} if UNINSTALL else set())
assert set(CASE['tools']) == {'cli', 'python', 'git'}
assert all(set(tool) == {'path', 'sha256'} for tool in CASE['tools'].values())
assert set(CASE['versions']) == {'python', 'pytest'}
assert set(CASE['pins']) == {'archive', 'leaf', 'manifest', 'oracle.sh', 'trustcheck.py'}
ROOT = Path(CASE['root'])
CLI = Path(CASE['tools']['cli']['path'])
PYTHON = Path(CASE['tools']['python']['path'])
GIT = Path(CASE['tools']['git']['path'])
PLUGIN_ID = CASE['plugin_id']
URL = CASE['url']
EXPECTED = CASE['pins']
assert ROOT.is_absolute() and ROOT == ROOT.resolve()
assert all(path.is_absolute() for path in (CLI, PYTHON, GIT))
assert PLUGIN_ID == 'autonomous-dev@adev-d0-native-consumer'
assert URL == 'https://pave-d0.invalid/marketplace.git'
# A real inherited per-file OS limit, not a claim about all command resources.
resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    return path


def run(argv, expected=0, cwd=None):
    global sequence
    assert expected is not None or ((RECOVERY or IDEMPOTENT) and str(argv[0]) == str(CLI))
    sequence += 1
    out = ROOT / 'private' / f'{OUTPUT_PREFIX}{sequence}.stdout'
    err = ROOT / 'private' / f'{OUTPUT_PREFIX}{sequence}.stderr'
    assert cwd in (None, POPULATED)
    assert not list(FOREIGN.iterdir())
    with out.open('xb') as stdout, err.open('xb') as stderr:
        try:
            proc = subprocess.run(list(map(str, argv)), cwd=cwd or FOREIGN, env=ENV,
                                  stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, timeout=40)
            status = proc.returncode
        except subprocess.TimeoutExpired:
            if expected is not None:
                raise
            status = -1
    assert out.stat().st_size <= 131072 and err.stat().st_size <= 131072
    assert not list(FOREIGN.iterdir())
    if str(argv[0]) == str(CLI):
        native_calls.append({'argv': list(map(str, argv)), 'cwd': str(cwd or FOREIGN),
                             'raw_exit': status, 'stdout': str(out.relative_to(ROOT)),
                             'stderr': str(err.relative_to(ROOT))})
    assert expected is None or status == expected, (sequence, status)
    return out


def compare_receipt(candidate, oracle, nonce, pins):
    comparison = run([PYTHON, '-I', '-S', '-B', ROOT / 'instruments/trustcheck.py', 'compare',
        '--oracle', oracle, '--candidate', candidate, '--nonce', nonce,
        '--expect-case', 'installed-r0', '--expect-tool-version', 'control-evidence-1',
        '--expect-subject-digest', pins['subject'], '--expect-dependency-digests', json.dumps(pins)])
    assert comparison.read_text().startswith('OK')


def select_native(rows):
    assert type(rows) is list
    matches = [row for row in rows if row['id'] == PLUGIN_ID and row['scope'] == 'user']
    assert len(matches) <= 1
    return matches[0] if matches else None


sequence = 0
native_calls = []
OUTPUT_PREFIX = ('update-' if UPDATE else 'uninstall-') + os.urandom(16).hex() + '-' if UPDATE or UNINSTALL else ''
POPULATED = ROOT / ('consumer' if RECOVERY or IDEMPOTENT else OUTPUT_PREFIX + 'consumer')
assert os.getuid() == 999 and os.getgid() == 990
assert set(os.getgroups()) <= {990}
assert not ROOT.is_symlink() and ROOT.is_dir()
assert digest(ROOT / 'payload.tar') == EXPECTED['archive']
for tool in CASE['tools'].values():
    assert digest(Path(tool['path']).resolve()) == tool['sha256']
for instrument in ('oracle.sh', 'trustcheck.py'):
    assert digest(ROOT / 'instruments' / instrument) == EXPECTED[instrument]
status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert all(int(status[key].strip(), 16) == 0 for key in ('CapEff', 'CapPrm', 'CapAmb', 'CapBnd'))
assert status['NoNewPrivs'].strip() == '1'
assert {line.split(':', 1)[0].strip()
        for line in Path('/proc/self/net/dev').read_text().splitlines()[2:]} == {'lo'}
for name in ('home', 'config', 'private', 'seed', 'empty-template', 'subjects', 'foreign'):
    if UPDATE:
        assert (ROOT / name).is_dir() and not (ROOT / name).is_symlink()
    else:
        (ROOT / name).mkdir(mode=0o700)
FOREIGN = ROOT / 'foreign'
ENV = {'PATH': '/usr/bin:/bin', 'HOME': str(ROOT / 'home'),
       'CLAUDE_CONFIG_DIR': str(ROOT / 'config'), 'XDG_CONFIG_HOME': str(ROOT / 'home'),
       'GIT_CONFIG_GLOBAL': str(ROOT / 'home/.gitconfig'), 'GIT_CONFIG_NOSYSTEM': '1',
       'GIT_TERMINAL_PROMPT': '0', 'GIT_TEMPLATE_DIR': str(ROOT / 'empty-template'),
       'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'DISABLE_AUTOUPDATER': '1',
       'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'}
def snapshot(paths, strict=False):
    values = {}
    for path in paths:
        assert not path.is_symlink() and path.resolve().is_relative_to(ROOT)
        info = path.stat()
        value = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
        if path.is_file():
            value['sha256'] = digest(path)
        else:
            assert path.is_dir()
        if strict and stat.S_ISREG(info.st_mode):
            value['identity'] = [info.st_dev, info.st_ino, info.st_nlink, info.st_size,
                                 info.st_mtime_ns, info.st_ctime_ns]
        values[str(path.relative_to(ROOT))] = value
    return values


FOREIGN_SETTINGS = CASE.get('foreign')
if UNINSTALL:
    fixture = ROOT / 'foreign-case.json'
    assert digest(fixture) == CASE['foreign_fixture_sha256'] and fixture.stat().st_size <= 8192
    FOREIGN_SETTINGS = json.loads(fixture.read_text())['foreign']


def populate_consumer():
    POPULATED.mkdir(mode=0o700)
    run([GIT, 'init', '--initial-branch=main', POPULATED])
    (POPULATED / '.claude').mkdir(mode=0o700)
    user = ROOT / 'config/settings.json'
    assert not user.is_symlink() and user.parent == user.parent.resolve()
    user_mode = stat.S_IMODE(user.stat().st_mode) if user.exists() else 0o600
    settings = json.loads(user.read_text()) if user.exists() else {}
    assert set(FOREIGN_SETTINGS) == {'user', 'repo', 'local', 'unrelated'}
    for key, value in FOREIGN_SETTINGS['user']['env'].items():
        assert key not in settings.get('env', {})
        settings.setdefault('env', {})[key] = value
    for section in ('permissions', 'hooks'):
        for key, values in FOREIGN_SETTINGS['user'][section].items():
            existing = settings.setdefault(section, {}).setdefault(key, [])
            assert not any(value in existing for value in values)
            existing.extend(values)
    write_json(user, settings).chmod(user_mode)
    project = POPULATED / '.claude/settings.json'
    local = POPULATED / '.claude/settings.local.json'
    write_json(project, FOREIGN_SETTINGS['repo']).chmod(0o640)
    write_json(local, FOREIGN_SETTINGS['local']).chmod(0o600)
    unrelated = POPULATED / 'unrelated.txt'
    unrelated.write_text(FOREIGN_SETTINGS['unrelated'])
    unrelated.chmod(0o644)
    return [user, project, local, unrelated]


with tarfile.open(ROOT / 'payload.tar') as archive:
    files = [member for member in archive.getmembers() if not member.isdir()]
    assert len(files) == 3 and {member.name for member in files} == {
        '.claude-plugin/marketplace.json',
        'plugins/autonomous-dev/.claude-plugin/plugin.json',
        'plugins/autonomous-dev/scripts/control_evidence.py'}
    payload = {}
    for member in files:
        assert member.isfile() and not member.issym() and not member.islnk()
        payload[member.name] = (archive.extractfile(member).read(), member.mode)
if UPDATE:
    baseline = CASE['baseline']
    old_cache = ROOT / Path(baseline['cache']).relative_to('/work')
    assert old_cache.is_dir() and old_cache == old_cache.resolve()
    old_leaf = old_cache / 'scripts/control_evidence.py'
    assert old_leaf.stat().st_ino == baseline['leaf_inode'] and digest(old_leaf) == EXPECTED['leaf']
    assert digest(old_cache / '.claude-plugin/plugin.json') == baseline['manifest_sha256']
    old_paths = ([old_cache, old_cache / '.claude-plugin', old_cache / '.claude-plugin/plugin.json',
                  old_cache / 'scripts', old_cache / 'scripts/control_evidence.py']
                 if IDEMPOTENT else [old_cache, *old_cache.rglob('*')])
    old_cache_before = snapshot(old_paths, strict=True)
    retained_paths = [path for folder in ('private', 'subjects')
                      for path in (ROOT / folder).rglob('*') if path.is_file()]
    retained_paths.append(ROOT / 'home/.gitconfig')
    retained_before = snapshot(retained_paths, strict=True)
    if RECOVERY or IDEMPOTENT:
        foreign_paths = [ROOT / 'config/settings.json', POPULATED / '.claude/settings.json',
                         POPULATED / '.claude/settings.local.json', POPULATED / 'unrelated.txt']
        foreign_before = snapshot(foreign_paths)
        before_inventory = run([CLI, 'plugin', 'list', '--json'], cwd=POPULATED)
        selected = select_native(json.loads(before_inventory.read_text()))
        assert selected and selected['enabled'] and selected['version'] == ('3.8.0-r0.2' if IDEMPOTENT else '57f1c12d3b81')
        assert Path(selected['installPath']) == old_cache and old_cache == old_cache.resolve()
        assert old_leaf == old_leaf.resolve() and old_leaf.stat().st_uid == 999 and old_leaf.stat().st_nlink == 1
        assert (not selected.get('errors') if IDEMPOTENT else any('repository: Invalid input: expected string, received object' in item for item in selected.get('errors', [])))
    seed_manifest = ROOT / 'seed/plugins/autonomous-dev/.claude-plugin/plugin.json'
    assert digest(seed_manifest) == baseline['manifest_sha256']
    for name, (body, mode) in payload.items():
        target = ROOT / 'seed' / name
        assert target.is_file() and not target.is_symlink()
        if target != seed_manifest:
            assert target.read_bytes() == body
    assert hashlib.sha256(payload['plugins/autonomous-dev/.claude-plugin/plugin.json'][0]).hexdigest() == EXPECTED['manifest']
    assert run([GIT, '-C', ROOT / 'seed', 'status', '--porcelain']).read_bytes() == b''
    if RECOVERY:
        assert run([GIT, '-C', ROOT / 'seed', 'rev-parse', 'HEAD']).read_text().strip() == '57f1c12d3b8162c411745168bd67351249d11eb1'
        assert run([GIT, '-C', ROOT / 'origin.git', 'rev-parse', 'refs/heads/main']).read_text().strip() == '57f1c12d3b8162c411745168bd67351249d11eb1'
    if not IDEMPOTENT:
        seed_manifest.write_bytes(payload['plugins/autonomous-dev/.claude-plugin/plugin.json'][0])
        run([GIT, '-C', ROOT / 'seed', 'add', '--', 'plugins/autonomous-dev/.claude-plugin/plugin.json'])
        assert run([GIT, '-C', ROOT / 'seed', 'diff', '--cached', '--name-only']).read_text().splitlines() == [
            'plugins/autonomous-dev/.claude-plugin/plugin.json']
        run([GIT, '-C', ROOT / 'seed', '-c', 'user.name=D0 fixture', '-c', 'user.email=d0@invalid',
             '-c', 'commit.gpgsign=false', 'commit', '-m', 'frozen R0 family update'])
    seed_head = run([GIT, '-C', ROOT / 'seed', 'rev-parse', 'HEAD'])
    new_commit = seed_head.read_text().strip()
    git_rows = run([GIT, '-C', ROOT / 'seed', 'ls-tree', '-r', '--full-tree', new_commit]).read_text().splitlines()
    assert len(git_rows) == len(payload)
    for row in git_rows:
        header, name = row.split('\t', 1)
        mode, kind, blob = header.split()
        assert name in payload and kind == 'blob'
        assert mode == ('100755' if payload[name][1] & 0o111 else '100644')
        assert run([GIT, '-C', ROOT / 'seed', 'cat-file', 'blob', blob]).read_bytes() == payload[name][0]
    if IDEMPOTENT:
        assert new_commit == '43a53efffd3eba6c26a2129a067fd7070d7771fd'
        before_heads = [seed_head, run([GIT, '-C', ROOT / 'origin.git', 'rev-parse', 'refs/heads/main']),
                        run([GIT, '-C', ROOT / 'config/plugins/marketplaces/adev-d0-native-consumer', 'rev-parse', 'HEAD'])]
        assert all(path.read_text().strip() == new_commit for path in before_heads)
    else:
        run([GIT, '-C', ROOT / 'seed', 'push', ROOT / 'origin.git', 'HEAD:refs/heads/main'])
    if not RECOVERY and not IDEMPOTENT:
        foreign_paths = populate_consumer()
        foreign_before = snapshot(foreign_paths)
    write_json(ROOT / 'private' / (OUTPUT_PREFIX + 'preservation.json'), {
        'foreign_before': foreign_before, 'old_cache_before': old_cache_before,
        'retained_before': retained_before, 'new_commit': new_commit})
    cycle_records = []
    for cycle in range(2 if IDEMPOTENT else 1):
        if IDEMPOTENT and cycle:
            selected = None
            try:
                before_inventory = run([CLI, 'plugin', 'list', '--json'], None, cwd=POPULATED)
                if native_calls[-1]['raw_exit'] == 0:
                    selected = select_native(json.loads(before_inventory.read_text()))
            except (AssertionError, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
                pass
            if not selected or not selected.get('enabled') or selected.get('errors') or selected.get('version') != '3.8.0-r0.2' or Path(selected.get('installPath', '')) != old_cache:
                print(json.dumps({'status': 'IDLE_IDEMPOTENCE_NONPASS_OBSERVED', 'completed_cycles': cycle_records,
                                  'native_calls': native_calls, 'stage': 'SECOND_BEFORE_SELECTION'}, sort_keys=True))
                sys.exit(0)
        try:
            run([CLI, 'plugin', 'marketplace', 'update', 'adev-d0-native-consumer'], None if RECOVERY or IDEMPOTENT else 0, cwd=POPULATED)
            marketplace_exit = native_calls[-1]['raw_exit']
        except (AssertionError, OSError, subprocess.SubprocessError):
            if not RECOVERY and not IDEMPOTENT:
                raise
            marketplace_exit = -1
        update_exit = None
        if not (RECOVERY or IDEMPOTENT) or marketplace_exit == 0:
            try:
                run([CLI, 'plugin', 'update', PLUGIN_ID, '--scope', 'user'], None if RECOVERY or IDEMPOTENT else 0, cwd=POPULATED)
                update_exit = native_calls[-1]['raw_exit']
            except (AssertionError, OSError, subprocess.SubprocessError):
                if not RECOVERY and not IDEMPOTENT:
                    raise
                update_exit = -1
        if RECOVERY or IDEMPOTENT:
            after_inventory, after_exit, after_selected = None, -1, None
            try:
                after_inventory = run([CLI, 'plugin', 'list', '--json'], None, cwd=POPULATED)
                after_exit = native_calls[-1]['raw_exit']
                if after_exit == 0:
                    after_selected = select_native(json.loads(after_inventory.read_text()))
            except (AssertionError, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
                pass
            after_maps = {}
            for name, paths, strict in (('foreign', foreign_paths, False), ('old_cache', old_paths, True),
                                        ('retained', retained_paths, True)):
                try:
                    after_maps[name] = {'value': snapshot(paths, strict=strict), 'error': None}
                except (AssertionError, OSError, ValueError):
                    after_maps[name] = {'value': None, 'error': 'UNAVAILABLE'}
            selected_after = {'value': None, 'error': 'UNAVAILABLE'}
            try:
                selected_path = Path(after_selected['installPath'])
                assert selected_path.is_absolute() and selected_path == selected_path.resolve()
                assert selected_path.is_relative_to(ROOT / 'config/plugins/cache')
                selected_files = [selected_path / '.claude-plugin/plugin.json', selected_path / 'scripts/control_evidence.py']
                for path in selected_files:
                    assert path == path.resolve() and not path.is_symlink()
                    info = path.stat()
                    assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 131072
                selected_after = {'value': snapshot(selected_files, strict=True), 'error': None}
            except (AssertionError, KeyError, TypeError, ValueError, OSError):
                pass
            if IDEMPOTENT:
                try:
                    vendor = [path for path in old_cache.rglob('*') if path not in old_paths]
                    assert len(vendor) <= 64 and all(path.is_dir() or path.stat().st_size <= 131072 for path in vendor)
                    after_maps['vendor'] = {'value': snapshot(vendor, strict=True), 'error': None}
                except (AssertionError, OSError, ValueError):
                    after_maps['vendor'] = {'value': None, 'error': 'UNAVAILABLE'}
            after_files = after_maps['foreign']['value']
            if (marketplace_exit != 0 or update_exit != 0 or after_exit != 0 or not after_selected or
                    not after_selected.get('enabled') or after_selected.get('version') != '3.8.0-r0.2' or
                    after_selected.get('errors') or selected_after['error'] or after_files != foreign_before or
                    (IDEMPOTENT and after_selected.get('installPath') != str(old_cache)) or
                    (IDEMPOTENT and after_maps['vendor']['error']) or
                    after_maps['old_cache']['value'] != old_cache_before or
                    after_maps['retained']['value'] != retained_before):
                print(json.dumps({'status': 'IDLE_IDEMPOTENCE_NONPASS_OBSERVED' if IDEMPOTENT else 'RECOVERY_NONPASS_OBSERVED', 'output_prefix': OUTPUT_PREFIX,
                    'before_inventory': str(before_inventory.relative_to(ROOT)),
                    'after_inventory': str(after_inventory.relative_to(ROOT)) if after_inventory else None,
                    'foreign_before': foreign_before, 'foreign_after': after_files, 'native_calls': native_calls,
                    'old_cache_after': after_maps['old_cache'], 'retained_after': after_maps['retained'],
                    'foreign_after_status': after_maps['foreign']['error'],
                    'selected_after': selected_after,
                    **({'vendor_after': after_maps['vendor']} if IDEMPOTENT else {}),
                **({'completed_cycles': cycle_records} if IDEMPOTENT else {}),
                    'marketplace_exit': marketplace_exit, 'update_exit': update_exit,
                    'native_hooks_loaded': 'UNMEASURED'}, sort_keys=True))
                sys.exit(0)
        if IDEMPOTENT:
            heads = [run([GIT, '-C', ROOT / name, 'rev-parse', ref]) for name, ref in (
                ('seed', 'HEAD'), ('origin.git', 'refs/heads/main'),
                ('config/plugins/marketplaces/adev-d0-native-consumer', 'HEAD'))]
            assert all(path.read_text().strip() == new_commit for path in heads)
            cycle_records.append({'before_inventory': str(before_inventory.relative_to(ROOT)),
                                  'after_inventory': str(after_inventory.relative_to(ROOT)),
                                  'foreign_after': after_files, 'cache_after': after_maps['old_cache'],
                                  'retained_after': after_maps['retained'], 'selected_after': selected_after,
                                  'head_records': [str(path.relative_to(ROOT)) for path in heads],
                                  'vendor_after': after_maps['vendor']})
    catalogue = ROOT / 'config/plugins/marketplaces/adev-d0-native-consumer'
    assert catalogue == catalogue.resolve() and catalogue.is_dir() and not catalogue.is_symlink()
    catalogue_commit = run([GIT, '-C', catalogue, 'rev-parse', 'HEAD']).read_text().strip()
    assert catalogue_commit == new_commit
    assert snapshot(foreign_paths) == foreign_before
    assert snapshot(old_paths, strict=True) == old_cache_before
    assert snapshot(retained_paths, strict=True) == retained_before
else:
    for name, (body, mode) in payload.items():
        target = ROOT / 'seed' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        target.chmod(mode)
    run([GIT, 'init', '--initial-branch=main', ROOT / 'seed'])
    run([GIT, '-C', ROOT / 'seed', 'add', '.'])
    run([GIT, '-C', ROOT / 'seed', '-c', 'user.name=D0 fixture',
         '-c', 'user.email=d0@invalid', '-c', 'commit.gpgsign=false', 'commit', '-m', 'frozen R0 family'])
    run([GIT, 'clone', '--bare', ROOT / 'seed', ROOT / 'origin.git'])
    run([GIT, 'config', '--global', f'url.file://{ROOT}/origin.git.insteadOf', URL])
    run([CLI, 'plugin', 'marketplace', 'add', URL])
    run([CLI, 'plugin', 'install', PLUGIN_ID, '--scope', 'user'])
metadata = ROOT / 'config/plugins/installed_plugins.json'
assert metadata.is_file() and not metadata.is_symlink() and metadata.stat().st_size <= 131072
entries = json.loads(metadata.read_text())['plugins'][PLUGIN_ID]
assert len(entries) == 1 and entries[0]['scope'] == 'user'
if UPDATE:
    assert entries[0]['version'] == '3.8.0-r0.2'
installed = Path(entries[0]['installPath'])
cache = ROOT / 'config/plugins/cache'
def verify_installed_cache():
    for directory in (cache, installed):
        assert directory.is_dir() and not directory.is_symlink()
        assert directory.is_absolute() and directory == directory.resolve()
    assert installed.is_relative_to(cache)
    for path in cache.rglob('*'):
        assert not path.is_symlink() and path.resolve().is_relative_to(cache)
        assert path.is_dir() or path.is_file()
    actual_files = {str(p.relative_to(installed)) for p in installed.rglob('*') if p.is_file()}
    payload_files = {'.claude-plugin/plugin.json', 'scripts/control_evidence.py'}
    assert payload_files <= actual_files if IDEMPOTENT else payload_files == actual_files


verify_installed_cache()
leaf = installed / 'scripts/control_evidence.py'
assert digest(leaf) == EXPECTED['leaf']
assert digest(installed / '.claude-plugin/plugin.json') == EXPECTED['manifest']
assert leaf.stat().st_ino != (ROOT / 'seed/plugins/autonomous-dev/scripts/control_evidence.py').stat().st_ino
if UPDATE:
    assert (installed == old_cache if IDEMPOTENT else installed != old_cache) and installed.name == '3.8.0-r0.2'
    for path in installed.rglob('*'):
        if path.is_file() and (not IDEMPOTENT or str(path.relative_to(installed)) in {'.claude-plugin/plugin.json', 'scripts/control_evidence.py'}):
            name = 'plugins/autonomous-dev/' + str(path.relative_to(installed))
            assert path.read_bytes() == payload[name][0]
            assert bool(path.stat().st_mode & 0o111) == bool(payload[name][1] & 0o111)
            assert not (path.stat().st_mode & 0o022)
if UNINSTALL:
    foreign_paths = populate_consumer()
    foreign_before = snapshot(foreign_paths)
    user_before = (ROOT / 'config/settings.json').read_text()
    before_inventory = run([CLI, 'plugin', 'list', '--json'], cwd=POPULATED)

    selected = select_native(json.loads(before_inventory.read_text()))
    assert selected and selected['enabled'] is True and selected['version'] == '3.8.0-r0.2'
    assert selected['installPath'] == str(installed)
    leaf = Path(selected['installPath']) / 'scripts/control_evidence.py'
    write_json(ROOT / 'private' / (OUTPUT_PREFIX + 'preservation.json'), {
        'foreign_before': foreign_before, 'user_before_text': user_before,
        'installed_before': snapshot([leaf, installed / '.claude-plugin/plugin.json'], strict=True),
        'selected_before': selected})
results = []
subject_parent = ROOT / 'subjects' / OUTPUT_PREFIX if UPDATE or UNINSTALL else ROOT / 'subjects'
if UPDATE or UNINSTALL:
    subject_parent.mkdir()
cases = [('permit', 'True', 'PASS', 0)] if UNINSTALL else [('permit', 'True', 'PASS', 0), ('refuse', 'False', 'FAIL', 1)]
for name, truth, decision, exit_code in cases:
    work = subject_parent / name
    work.mkdir()
    target = work / 'test_subject.py'
    target.write_text(f'def test_value():\n    assert {truth}\n')
    nonce = os.urandom(16).hex()
    versions = json.loads(run([PYTHON, '-I', '-B', '-c',
        'import json,platform,pytest;print(json.dumps([platform.python_version(),pytest.__version__]))']).read_text())
    assert versions == [CASE['versions']['python'], CASE['versions']['pytest']]
    manifest = write_json(work / 'cases.json', {'cases': [{'id': 'installed-r0',
        'runner': {'cwd': str(work), 'python_version': versions[0], 'pytest_version': versions[1]},
        'expected': {'selected_ids': ['test_subject.py::test_value'], 'selected_count': 1,
                     'collect_exit': 0, 'run_exit': 0}}]})
    common = ['--target', target, '--workroot', work, '--nonce', nonce,
              '--python', PYTHON, '--pycache-prefix', work / 'unused-cache']
    oracle = run(['/bin/sh', ROOT / 'instruments/oracle.sh', *common])
    candidate_argv = [PYTHON, '-I', '-S', '-B', leaf, *common,
                      '--child-timeout', '20', '--case', 'installed-r0', '--case-manifest', manifest]
    candidate = run(candidate_argv, exit_code)
    receipt = json.loads(candidate.read_text())
    obs = receipt['observation']
    assert receipt['decision'] == decision and obs['run_exit'] == exit_code
    assert obs['cleanup_complete'] and obs['selected'] == ['test_subject.py::test_value']
    pins = {'case_manifest': digest(manifest), 'verifier': digest(leaf),
            'python': digest(PYTHON.resolve()), 'subject': digest(target)}
    compare_receipt(candidate, oracle, nonce, pins)
    if name == 'permit':
        permit_argv, permit_common, permit_pins = candidate_argv.copy(), common.copy(), pins.copy()
    results.append({'case': name, 'raw_exit': exit_code, 'decision': decision,
                    'receipt_sha256': digest(candidate), 'oracle_sha256': digest(oracle),
                    'receipt': str(candidate.relative_to(ROOT)), 'oracle': str(oracle.relative_to(ROOT)),
                    'target': str(target), 'nonce': nonce})
if UNINSTALL:
    run([CLI, 'plugin', 'uninstall', PLUGIN_ID, '--scope', 'user'], cwd=POPULATED)
    after_inventory = run([CLI, 'plugin', 'list', '--json'], cwd=POPULATED)
    assert select_native(json.loads(after_inventory.read_text())) is None
    print(json.dumps({'status': 'NATIVE_UNINSTALL_SELECTION_ONLY', 'output_prefix': OUTPUT_PREFIX,
        'cases': results, 'native_calls': native_calls, 'installed_root': str(installed),
        'before_inventory': str(before_inventory.relative_to(ROOT)),
        'after_inventory': str(after_inventory.relative_to(ROOT)),
        'preservation_file': OUTPUT_PREFIX + 'preservation.json',
        'owned_data': 'UNMEASURED_NO_PRODUCT_STORE', 'native_hooks_loaded': 'UNMEASURED'}, sort_keys=True))
    sys.exit(0)
if not IDEMPOTENT:
    before = leaf.stat()
    held = leaf.with_name(leaf.name + '.held')
    os.link(leaf, held, follow_symlinks=False)
    leaf.unlink()
    try:
        broken_argv = permit_argv.copy()
        broken_argv[broken_argv.index('--nonce') + 1] = os.urandom(16).hex()
        broken_output = run(broken_argv, 2)
        assert not broken_output.read_bytes()
        assert not leaf.exists() and digest(held) == EXPECTED['leaf']
    finally:
        current = held.stat()
        assert (current.st_dev, current.st_ino, current.st_mode, current.st_uid, current.st_gid,
                current.st_size, current.st_mtime_ns) == (
                    before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_gid,
                    before.st_size, before.st_mtime_ns)
        os.link(held, leaf, follow_symlinks=False)
        held.unlink()
    after = leaf.stat()
    assert after.st_ino == before.st_ino and after.st_dev == before.st_dev and after.st_nlink == 1
    assert digest(leaf) == EXPECTED['leaf']
    assert digest(installed / '.claude-plugin/plugin.json') == EXPECTED['manifest']
    verify_installed_cache()
else:
    after = leaf.stat()
    assert after.st_ino == baseline['leaf_inode'] and after.st_nlink == 1
nonce = os.urandom(16).hex()
permit_argv[permit_argv.index('--nonce') + 1] = nonce
permit_common[permit_common.index('--nonce') + 1] = nonce
oracle = run(['/bin/sh', ROOT / 'instruments/oracle.sh', *permit_common])
candidate = run(permit_argv)
restored = json.loads(candidate.read_text())
assert restored['decision'] == 'PASS' and restored['observation']['cleanup_complete']
compare_receipt(candidate, oracle, nonce, permit_pins)
results.append({'case': 'permit-repeat' if IDEMPOTENT else 'permit-restored', 'raw_exit': 0, 'decision': 'PASS',
                'receipt_sha256': digest(candidate), 'oracle_sha256': digest(oracle),
                'receipt': str(candidate.relative_to(ROOT)), 'oracle': str(oracle.relative_to(ROOT)),
                'target': str(permit_argv[permit_argv.index('--target') + 1]), 'nonce': nonce})
if UPDATE:
    assert snapshot(foreign_paths) == foreign_before
    assert snapshot(old_paths, strict=True) == old_cache_before
    assert snapshot(retained_paths, strict=True) == retained_before
broken_error = broken_output.with_suffix('.stderr') if not IDEMPOTENT else None
print(json.dumps({'status': 'UPDATE_AND_INSTALLED_R0_EXECUTION_ONLY' if UPDATE else
                  'ACQUISITION_AND_INSTALLED_R0_EXECUTION_ONLY', 'cases': results,
                  'installed_root': str(installed), 'metadata_sha256': digest(metadata),
                  'installed_leaf_sha256': EXPECTED['leaf'], 'restored_leaf_inode': after.st_ino,
                  'broken_route_refused_and_restored': True if not IDEMPOTENT else 'NOT_RUN_REUSED_PRIOR',
                  'broken_route': None if IDEMPOTENT else {'stdout': str(broken_output.relative_to(ROOT)),
                                   'stderr': str(broken_error.relative_to(ROOT)), 'raw_exit': 2,
                                   'stdout_sha256': digest(broken_output), 'stderr_sha256': digest(broken_error)},
                  'native_hooks_loaded': 'UNMEASURED', 'output_prefix': OUTPUT_PREFIX,
                  'native_calls': native_calls,
                  **({'recovery': {'before_inventory': str(before_inventory.relative_to(ROOT)),
                                   'after_inventory': str(after_inventory.relative_to(ROOT)),
                                   'foreign_before': foreign_before, 'foreign_after': after_files}}
                     if RECOVERY else {}),
                  **({'idempotence': {'cycles': cycle_records, 'broken_control': 'NOT_RUN_REUSED_PRIOR',
                                      'before_heads': [str(path.relative_to(ROOT)) for path in before_heads]}} if IDEMPOTENT else {}),
                  'update': {'new_commit': new_commit, 'catalogue_root': str(catalogue),
                             'catalogue_commit': catalogue_commit, 'native_calls': native_calls,
                             'preservation_file': OUTPUT_PREFIX + 'preservation.json',
                             'registry_commit_identity': 'MATCH' if entries[0].get('gitCommitSha') == new_commit else
                             'CONFLICTED' if entries[0].get('gitCommitSha') else 'UNMEASURED'}
                             if UPDATE else None}, sort_keys=True))

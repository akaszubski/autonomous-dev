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
assert set(CASE) == {'case', 'root', 'tools', 'versions', 'pins', 'plugin_id', 'url'}
assert CASE['case'] == 'D0-R0-ACQUIRE-1'
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


def run(argv, expected=0):
    global sequence
    sequence += 1
    out = ROOT / 'private' / f'{sequence}.stdout'
    err = ROOT / 'private' / f'{sequence}.stderr'
    assert not list(FOREIGN.iterdir())
    with out.open('xb') as stdout, err.open('xb') as stderr:
        proc = subprocess.run(list(map(str, argv)), cwd=FOREIGN, env=ENV,
                              stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, timeout=40)
    assert out.stat().st_size <= 131072 and err.stat().st_size <= 131072
    assert not list(FOREIGN.iterdir())
    assert proc.returncode == expected, (sequence, proc.returncode)
    return out


sequence = 0
assert os.getuid() == 999 and os.getgid() == 990
assert not ROOT.is_symlink() and ROOT.is_dir()
assert digest(ROOT / 'payload.tar') == EXPECTED['archive']
for tool in CASE['tools'].values():
    assert digest(Path(tool['path']).resolve()) == tool['sha256']
for instrument in ('oracle.sh', 'trustcheck.py'):
    assert digest(ROOT / 'instruments' / instrument) == EXPECTED[instrument]
status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert all(int(status[key].strip(), 16) == 0 for key in ('CapEff', 'CapPrm', 'CapAmb', 'CapBnd'))
assert {line.split(':', 1)[0].strip()
        for line in Path('/proc/self/net/dev').read_text().splitlines()[2:]} == {'lo'}
for name in ('home', 'config', 'private', 'seed', 'empty-template', 'subjects', 'foreign'):
    (ROOT / name).mkdir(mode=0o700)
FOREIGN = ROOT / 'foreign'
ENV = {'PATH': '/usr/bin:/bin', 'HOME': str(ROOT / 'home'),
       'CLAUDE_CONFIG_DIR': str(ROOT / 'config'), 'XDG_CONFIG_HOME': str(ROOT / 'home'),
       'GIT_CONFIG_GLOBAL': str(ROOT / 'home/.gitconfig'), 'GIT_CONFIG_NOSYSTEM': '1',
       'GIT_TERMINAL_PROMPT': '0', 'GIT_TEMPLATE_DIR': str(ROOT / 'empty-template'),
       'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'DISABLE_AUTOUPDATER': '1',
       'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'}
with tarfile.open(ROOT / 'payload.tar') as archive:
    files = [member for member in archive.getmembers() if not member.isdir()]
    assert {member.name for member in files} == {
        '.claude-plugin/marketplace.json',
        'plugins/autonomous-dev/.claude-plugin/plugin.json',
        'plugins/autonomous-dev/scripts/control_evidence.py'}
    for member in files:
        assert member.isfile() and not member.issym() and not member.islnk()
        target = ROOT / 'seed' / member.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.extractfile(member).read())
        target.chmod(member.mode)
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
    assert sorted(str(p.relative_to(installed)) for p in installed.rglob('*') if p.is_file()) == [
        '.claude-plugin/plugin.json', 'scripts/control_evidence.py']


verify_installed_cache()
leaf = installed / 'scripts/control_evidence.py'
assert digest(leaf) == EXPECTED['leaf']
assert digest(installed / '.claude-plugin/plugin.json') == EXPECTED['manifest']
assert leaf.stat().st_ino != (ROOT / 'seed/plugins/autonomous-dev/scripts/control_evidence.py').stat().st_ino
verify_installed_cache()
results = []
for name, truth, decision, exit_code in [('permit', 'True', 'PASS', 0), ('refuse', 'False', 'FAIL', 1)]:
    work = ROOT / 'subjects' / name
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
    comparison = run([PYTHON, '-I', '-S', '-B', ROOT / 'instruments/trustcheck.py', 'compare',
        '--oracle', oracle, '--candidate', candidate, '--nonce', nonce,
        '--expect-case', 'installed-r0', '--expect-tool-version', 'control-evidence-1',
        '--expect-subject-digest', digest(target), '--expect-dependency-digests', json.dumps(pins)])
    assert comparison.read_text().startswith('OK')
    if name == 'permit':
        permit_argv, permit_common, permit_pins = candidate_argv.copy(), common.copy(), pins.copy()
    results.append({'case': name, 'raw_exit': exit_code, 'decision': decision,
                    'receipt_sha256': digest(candidate), 'oracle_sha256': digest(oracle)})
before = leaf.stat()
held = leaf.with_name(leaf.name + '.held')
os.link(leaf, held, follow_symlinks=False)
leaf.unlink()
try:
    broken_argv = permit_argv.copy()
    broken_argv[broken_argv.index('--nonce') + 1] = os.urandom(16).hex()
    run(broken_argv, 2)
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
nonce = os.urandom(16).hex()
permit_argv[permit_argv.index('--nonce') + 1] = nonce
permit_common[permit_common.index('--nonce') + 1] = nonce
oracle = run(['/bin/sh', ROOT / 'instruments/oracle.sh', *permit_common])
candidate = run(permit_argv)
restored = json.loads(candidate.read_text())
assert restored['decision'] == 'PASS' and restored['observation']['run_exit'] == 0
assert restored['observation']['cleanup_complete']
assert restored['observation']['selected'] == ['test_subject.py::test_value']
comparison = run([PYTHON, '-I', '-S', '-B', ROOT / 'instruments/trustcheck.py', 'compare',
    '--oracle', oracle, '--candidate', candidate, '--nonce', nonce,
    '--expect-case', 'installed-r0', '--expect-tool-version', 'control-evidence-1',
    '--expect-subject-digest', permit_pins['subject'],
    '--expect-dependency-digests', json.dumps(permit_pins)])
assert comparison.read_text().startswith('OK')
results.append({'case': 'permit-restored', 'raw_exit': 0, 'decision': 'PASS',
                'receipt_sha256': digest(candidate), 'oracle_sha256': digest(oracle)})
print(json.dumps({'status': 'ACQUISITION_AND_INSTALLED_R0_EXECUTION_ONLY', 'cases': results,
                  'installed_root': str(installed), 'metadata_sha256': digest(metadata),
                  'installed_leaf_sha256': digest(leaf), 'restored_leaf_inode': after.st_ino,
                  'broken_route_refused_and_restored': True,
                  'native_hooks_loaded': 'UNMEASURED'}, sort_keys=True))

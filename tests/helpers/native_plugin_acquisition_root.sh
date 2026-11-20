#!/bin/bash
# Qualification fixture only: maintained file tools and systemd own the lifecycle.
set -euo pipefail
pave_upload=$1
pave_id=$2
pave_sums_sha=$3
[[ "$pave_upload" == /home/f0/adev-d0-inputs.* ]]
[[ "$pave_id" =~ ^[0-9a-f]{32}$ && "$pave_sums_sha" =~ ^[0-9a-f]{64}$ ]]
test "$(id -u)" = 0
# Bound the outer pipe writer too; Bash uses 1024-byte file-size blocks.
ulimit -f 128
test -d "$pave_upload" && test ! -L "$pave_upload"
test "$(stat -c %u "$pave_upload")" = 501
pave_parent=/var/lib/adev-d0-native-consumer
if test ! -e "$pave_parent"; then install -d -o 0 -g 0 -m 0700 "$pave_parent"; fi
test ! -L "$pave_parent" && test "$(stat -c %u:%g:%a "$pave_parent")" = 0:0:700
pave_op="$pave_parent/$pave_id"
mkdir -m 0700 "$pave_op"
install -d -o 0 -g 0 -m 0700 "$pave_op/inputs"
install -d -o 0 -g 0 -m 0555 "$pave_op/inputs/instruments"
for pave_file in operator.py case.PUBLIC.json payload.tar SHA256SUMS; do
  test -f "$pave_upload/$pave_file" && test ! -L "$pave_upload/$pave_file"
  test "$(stat -c %u:%h "$pave_upload/$pave_file")" = 0:1
  install -o 0 -g 0 -m 0444 "$pave_upload/$pave_file" "$pave_op/inputs/$pave_file"
done
for pave_file in oracle.sh trustcheck.py; do
  test -f "$pave_upload/$pave_file" && test ! -L "$pave_upload/$pave_file"
  test "$(stat -c %u:%h "$pave_upload/$pave_file")" = 0:1
  install -o 0 -g 0 -m 0444 "$pave_upload/$pave_file" "$pave_op/inputs/instruments/$pave_file"
done
pave_foreign_bind=
for pave_file in foreign-case.json; do
  if test -e "$pave_upload/$pave_file"; then
    test -f "$pave_upload/$pave_file" && test ! -L "$pave_upload/$pave_file"
    test "$(stat -c %u:%h "$pave_upload/$pave_file")" = 0:1
    install -o 0 -g 0 -m 0444 "$pave_upload/$pave_file" "$pave_op/inputs/$pave_file"
    pave_foreign_bind+="${pave_foreign_bind:+ }$pave_op/inputs/$pave_file:/work/$pave_file"
  fi
done
pave_sum=$(sha256sum "$pave_op/inputs/SHA256SUMS")
test "${pave_sum%% *}" = "$pave_sums_sha"
(cd "$pave_op/inputs" && sha256sum --check --strict --status SHA256SUMS)
pave_actors=$(ps -eo uid=,pid=,comm= | awk '$1 == 999 {print}')
test -z "$pave_actors"
for pave_policy in /etc/claude-code/managed-settings.json /etc/claude-code/managed-mcp.json; do
  test ! -e "$pave_policy"
done
pave_run=$(/usr/bin/python3 -I -S -B - "$pave_op" <<'BASELINE'
import hashlib,json,os,pathlib,re,stat,subprocess,sys
op = pathlib.Path(sys.argv[1])
case = json.loads((op / 'inputs/case.PUBLIC.json').read_text())
recovery = case['case'] == 'D0-R0-RECOVERY-1'
if recovery:
    assert set(case) == {'case', 'fixture_sha256', 'operator_sha256', 'baseline'}
    fixture = (op / 'inputs/foreign-case.json').read_bytes()
    assert len(fixture) <= 8192 and hashlib.sha256(fixture).hexdigest() == case.pop('fixture_sha256')
    assert hashlib.sha256((op / 'inputs/operator.py').read_bytes()).hexdigest() == case['operator_sha256']
    case = dict(json.loads(fixture), **case)
if case['case'] == 'D0-R0-UPDATE-1' or recovery:
    baseline = case['baseline']
    assert baseline['accepted_freeze_sha256'] == ('3baf71dc69dc3a5fbeafecf7f2e014f5a04e695b18b607fe73c8fd1dd460e4b3' if recovery else '6ee2f213871c69d5f687fcef6f161cf1fca05c8e21999414b5ad5f5300f3f81b')
    assert set(baseline) == {'operation', 'invocation_id', 'cache', 'leaf_inode',
                             'manifest_sha256', 'accepted_freeze_sha256'}
    assert re.fullmatch('[0-9a-f]{32}', baseline['operation']) and baseline['operation'] != op.name
    old = op.parent / baseline['operation']
    assert old == old.resolve() and not old.is_symlink()
    info = old.stat()
    assert (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (0, 0, 0o700)
    record = old / 'OUTSIDE-RESULT.PUBLIC.json'
    assert not record.is_symlink() and record.stat().st_uid == 0
    assert record.stat().st_nlink == 1 and not (record.stat().st_mode & 0o022)
    receipt = json.loads(record.read_text())
    assert receipt['status'] == ('RAW_UNIT_AND_CLEANUP_OBSERVED' if recovery else 'D0_FAMILY_CASES_AND_CLEANUP_OBSERVED')
    assert receipt['operation'] == baseline['operation'] and receipt['invocation_id'] == baseline['invocation_id']
    assert receipt['raw_unit_exit'] == 0 and receipt['cgroup_empty']
    assert recovery or receipt['broken_route_restored']
    if recovery:
        assert baseline['operation'] == 'bd960e7a8de14af09c1d919c6f57b319'
    old_unit = 'adev-d0-acquire-' + baseline['operation'] + '.service'
    assert receipt['unit'] == old_unit
    query = subprocess.run(['/usr/bin/systemctl', 'show', '--all', old_unit,
                            '--property=Id,ActiveState,LoadState,MainPID'], capture_output=True,
                           env={'PATH': '/usr/bin:/bin'}, text=True, timeout=5)
    current = dict(line.split('=', 1) for line in query.stdout.splitlines() if '=' in line)
    assert current.get('Id') == old_unit and current.get('ActiveState') == 'inactive'
    assert current.get('MainPID') == '0'
    assert query.returncode == 0 or (query.returncode == 1 and current.get('LoadState') == 'not-found')
    old_group = pathlib.Path('/sys/fs/cgroup/system.slice') / old_unit
    assert not old_group.exists() or not (old_group / 'cgroup.procs').read_text().strip()
    old_policy = pathlib.Path('/run/systemd/system') / (old_unit + '.d')
    assert not old_policy.exists() and not old_policy.is_symlink()
    root = old / 'run'
    assert root == root.resolve() and not root.is_symlink()
    info = root.stat()
    assert (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (999, 990, 0o700)
    registry = root / 'config/plugins/installed_plugins.json'
    assert registry == registry.resolve() and not registry.is_symlink()
    with os.fdopen(os.open(registry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC), 'rb') as stream:
        info = os.fstat(stream.fileno())
        assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 65536
        registry_raw = stream.read(65537)
    assert len(registry_raw) <= 65536
    registry_text = registry_raw.decode('utf-8')
    rows = json.loads(registry_text)['plugins'][case['plugin_id']]
    assert type(rows) is list and len(rows) == 1 and rows[0]['scope'] == 'user'
    assert rows[0]['version'] == ('57f1c12d3b81' if recovery else '3.8.0-r0.1') and rows[0]['installPath'] == baseline['cache']
    if recovery:
        assert hashlib.sha256(registry_raw).hexdigest() == '5400080596072c5216e2ae7d79729be40d0dd746e255d2a446829e09832272df'
    cache = root / pathlib.Path(baseline['cache']).relative_to('/work')
    assert cache == cache.resolve() and cache.is_relative_to(root / 'config/plugins/cache')
    expected_cache = {'.claude-plugin', 'scripts', '.claude-plugin/plugin.json', 'scripts/control_evidence.py'}
    assert expected_cache <= {str(path.relative_to(cache)) for path in cache.rglob('*')}
    assert {str(path.relative_to(cache)) for path in cache.rglob('*') if path.is_file()} == {
        '.claude-plugin/plugin.json', 'scripts/control_evidence.py'}

    def fact(path):
        assert path == path.resolve() and not path.is_symlink()
        info = path.stat()
        value = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
        if stat.S_ISREG(info.st_mode):
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC), 'rb') as stream:
                data = stream.read(131073)
            assert len(data) <= 131072
            value['sha256'] = hashlib.sha256(data).hexdigest()
        else:
            assert stat.S_ISDIR(info.st_mode)
        if stat.S_ISREG(info.st_mode):
            value['identity'] = [info.st_dev, info.st_ino, info.st_nlink, info.st_size,
                                 info.st_mtime_ns, info.st_ctime_ns]
        return value

    old_cache_before = {str(path.relative_to(root)): fact(path) for path in [cache, *cache.rglob('*')]}
    retained_before = {}
    for folder in ('private', 'subjects'):
        directory = root / folder
        assert directory.is_dir() and directory == directory.resolve() and not directory.is_symlink()
        for path in directory.rglob('*'):
            assert not path.is_symlink()
            if not path.is_dir():
                retained_before[str(path.relative_to(root))] = fact(path)
    retained_before['home/.gitconfig'] = fact(root / 'home/.gitconfig')
    held = {'registry_text': registry_text, 'registry_sha256': hashlib.sha256(registry_raw).hexdigest(),
            'old_cache_before': old_cache_before, 'retained_before': retained_before}
    if recovery:
        names = ('config/settings.json', 'consumer/.claude/settings.json',
                 'consumer/.claude/settings.local.json', 'consumer/unrelated.txt')
        held['foreign_before'] = {name: fact(root / name) for name in names}
        assert [held['foreign_before'][name]['sha256'] for name in names] == [
            'cdb576a3e399423dd4d535f802b0981e5d256fcf2ec19eb3978135c91ec2e28b',
            '3d5e4c0d461c1893959b290e415483987bda74a67e807f62e547aed7c1e985ee',
            'f10d0d00aa75b9a4e40245fbb2897b9a9d5ead29a9cf5b4b7f48dd1d50678085',
            'e951dbb7bfc4942f7ced0928f8224cd8f56bc73dbd8ce6a2cc664bffee59a6da']
    encoded = json.dumps(held, sort_keys=True) + '\n'
    assert len(encoded.encode('utf-8')) <= 131072
    held_path = op / 'OLD-CONSUMER.BEFORE.PUBLIC.json'
    with held_path.open('x') as stream:
        stream.write(encoded)
    held_path.chmod(0o444)
    leaf = cache / 'scripts/control_evidence.py'
    assert leaf.stat().st_ino == baseline['leaf_inode'] and leaf.stat().st_nlink == 1
    assert hashlib.sha256(leaf.read_bytes()).hexdigest() == case['pins']['leaf']
    assert hashlib.sha256((cache / '.claude-plugin/plugin.json').read_bytes()).hexdigest() == baseline['manifest_sha256']
    before = {}
    for path in (old / 'inputs').rglob('*'):
        assert not path.is_symlink()
        if path.is_file():
            info = path.stat()
            assert info.st_uid == 0 and info.st_nlink == 1
            before[str(path.relative_to(old))] = [hashlib.sha256(path.read_bytes()).hexdigest(), info.st_mode]
    (op / 'OLD-INPUTS.BEFORE.PUBLIC.json').write_text(json.dumps(before, sort_keys=True) + '\n')
else:
    assert case['case'] in ('D0-R0-ACQUIRE-1', 'D0-R0-UNINSTALL-1')
    root = op / 'run'
    root.mkdir(mode=0o700)
    os.chown(root, 999, 990)
print(root)
BASELINE
)
pave_unit="adev-d0-acquire-$pave_id.service"
pave_load_status=0
pave_load=$(systemctl show --value --property=LoadState "$pave_unit" 2>"$pave_op/unit-before.stderr") || pave_load_status=$?
test "$pave_load" = not-found
pave_dropdir="/run/systemd/system/$pave_unit.d"
pave_dropfile="$pave_dropdir/zzzz-pave-d0.conf"
test ! -e "$pave_dropdir" && test ! -L "$pave_dropdir"
cat >"$pave_op/zzzz-pave-d0.conf" <<'POLICY'
[Service]
User=999
Group=990
SupplementaryGroups=
CapabilityBoundingSet=
AmbientCapabilities=
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
PrivateNetwork=yes
ProtectControlGroups=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
EnvironmentFile=
ImportCredential=
LoadCredential=
LoadCredentialEncrypted=
SetCredential=
SetCredentialEncrypted=
POLICY
chmod 0444 "$pave_op/zzzz-pave-d0.conf"
pave_policy_sum=$(sha256sum "$pave_op/zzzz-pave-d0.conf")
pave_policy_sha=${pave_policy_sum%% *}
mkdir -m 0755 "$pave_dropdir"
install -o 0 -g 0 -m 0444 "$pave_op/zzzz-pave-d0.conf" "$pave_dropfile"
systemctl daemon-reload
pave_pre_gate=$(/usr/bin/python3 -I -S -B - "$pave_unit" <<'GATE_ARGV'
import json,sys
program = """
import json,re,resource,subprocess,sys,tempfile
resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))
flags = {
    "NoNewPrivileges": "yes", "ProtectSystem": "strict", "ProtectHome": "yes",
    "PrivateTmp": "yes", "PrivateDevices": "yes", "PrivateNetwork": "yes",
    "ProtectControlGroups": "yes", "ProtectKernelTunables": "yes",
    "ProtectKernelModules": "yes",
}
properties = ["Id", "InvocationID", "ControlGroup", "Result", "ExecMainCode", "ExecMainStatus", *flags]
with tempfile.TemporaryFile(dir="/tmp") as output:
    subprocess.run(["/usr/bin/systemctl", "show", "--all", sys.argv[1],
                    "--property=" + ",".join(properties)], stdout=output, stderr=subprocess.DEVNULL,
                   env={"PATH": "/usr/bin:/bin"}, timeout=5, check=True)
    output.seek(0)
    raw = output.read(8193)
assert len(raw) <= 8192
meta = dict(line.split("=", 1) for line in raw.decode().splitlines() if "=" in line)
assert meta.get("Id") == sys.argv[1]
assert all(meta.get(key) == value for key, value in flags.items())

def pairs(items):
    result = {}
    for key, value in items:
        assert key not in result
        result[key] = value
    return result

def query(arguments, maximum):
    with tempfile.TemporaryFile(dir="/tmp") as output, tempfile.TemporaryFile(dir="/tmp") as errors:
        subprocess.run(["/usr/bin/busctl", "--system", "--json=short", *arguments],
                       stdin=subprocess.DEVNULL, stdout=output, stderr=errors, timeout=2,
                       env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, check=True)
        output.seek(0)
        errors.seek(0)
        raw = output.read(maximum + 1)
        assert not errors.read(1) and len(raw) <= maximum
    return json.loads(raw, object_pairs_hook=pairs)

obj = query(["call", "org.freedesktop.systemd1", "/org/freedesktop/systemd1",
             "org.freedesktop.systemd1.Manager", "GetUnit", "s", sys.argv[1]], 4096)
assert type(obj) is dict and set(obj) == {"type", "data"} and obj["type"] == "o"
assert type(obj["data"]) is list and len(obj["data"]) == 1 and type(obj["data"][0]) is str
assert re.fullmatch(r"/org/freedesktop/systemd1/unit/[A-Za-z0-9_]+", obj["data"][0])
for key, signature in (("EnvironmentFiles", "a(sb)"), ("LoadCredential", "a(ss)"),
                       ("LoadCredentialEncrypted", "a(ss)"), ("SetCredential", "a(say)"),
                       ("SetCredentialEncrypted", "a(say)"), ("ImportCredential", "as")):
    value = query(["get-property", "org.freedesktop.systemd1", obj["data"][0],
                   "org.freedesktop.systemd1.Service", key], 16384)
    assert value == {"type": signature, "data": []}
assert sys.argv[2] in ("pre", "post")
if sys.argv[2] == "post":
    for key in properties:
        print(key + "=" + meta[key])
    print("TypedCredentialsEmpty=yes")
"""
# JSON double quoting is C-escaped systemd argv syntax, not shell execution.
print("/usr/bin/python3 -I -S -B -c " + json.dumps(program) + " " + sys.argv[1])
GATE_ARGV
)
pave_status=0
systemd-run --unit="$pave_unit" --wait --pipe --collect \
  -p Type=exec -p Slice=system.slice -p User=999 -p Group=990 -p SupplementaryGroups= \
  -p CapabilityBoundingSet= -p AmbientCapabilities= \
  -p NoNewPrivileges=yes -p ProtectSystem=strict -p ProtectHome=yes \
  -p PrivateTmp=yes -p PrivateDevices=yes -p PrivateNetwork=yes \
  -p ProtectControlGroups=yes -p ProtectKernelTunables=yes -p ProtectKernelModules=yes \
  -p RestrictNamespaces=yes -p RestrictSUIDSGID=yes -p LockPersonality=yes \
  -p RestrictAddressFamilies='AF_UNIX AF_INET AF_INET6' \
  -p InaccessiblePaths='-/Users -/mnt -/media -/Volumes -/var/lib/adev-f0-stored-login-proposed' \
  -p BindPaths="$pave_run:/work" \
  -p BindReadOnlyPaths="$pave_op/inputs/operator.py:/work/operator.py $pave_op/inputs/case.PUBLIC.json:/work/case.PUBLIC.json $pave_op/inputs/payload.tar:/work/payload.tar $pave_op/inputs/instruments:/work/instruments${pave_foreign_bind:+ }$pave_foreign_bind" \
  -p WorkingDirectory=/work -p UMask=0077 -p RuntimeMaxSec=240s -p TimeoutStopSec=3s \
  -p KillMode=control-group -p TasksMax=128 -p MemoryMax=1G -p LimitFSIZE=131072 \
  -p "ExecStartPre=$pave_pre_gate pre" \
  -p "ExecStopPost=$pave_pre_gate post" \
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B \
  /work/operator.py /work/case.PUBLIC.json \
  >"$pave_op/outer.stdout" 2>"$pave_op/outer.stderr" || pave_status=$?
/usr/bin/python3 -I -S -B - "$pave_op" "$pave_unit" "$pave_status" "$pave_policy_sha" "$pave_run" <<'AUDIT'
import hashlib,json,pathlib,re,stat,subprocess,sys,tarfile
op=pathlib.Path(sys.argv[1]);unit=sys.argv[2];raw_exit=int(sys.argv[3])
cgroup=pathlib.Path('/sys/fs/cgroup/system.slice')/unit
empty=not cgroup.exists() or not (cgroup/'cgroup.procs').read_text().strip()
assert empty, 'owned service cgroup is not empty; preserve and recover through manager'
stdout=(op/'outer.stdout').read_text();lines=stdout.splitlines()
flags = {
    'NoNewPrivileges': 'yes', 'ProtectSystem': 'strict', 'ProtectHome': 'yes',
    'PrivateTmp': 'yes', 'PrivateDevices': 'yes', 'PrivateNetwork': 'yes',
    'ProtectControlGroups': 'yes', 'ProtectKernelTunables': 'yes',
    'ProtectKernelModules': 'yes',
}
keys = {'Id', 'InvocationID', 'ControlGroup', 'Result', 'ExecMainCode', 'ExecMainStatus',
        'TypedCredentialsEmpty', *flags}
meta = dict(line.split('=', 1) for line in lines if line.partition('=')[0] in keys)
query = subprocess.run(['/usr/bin/systemctl', 'show', '--all', unit,
                        '--property=Id,ActiveState,LoadState'], capture_output=True, text=True)
current = dict(line.split('=', 1) for line in query.stdout.splitlines() if '=' in line)
assert current.get('Id') == unit and current.get('ActiveState') == 'inactive'
assert query.returncode == 0 or (query.returncode == 1 and current.get('LoadState') == 'not-found')
dropdir = pathlib.Path('/run/systemd/system') / (unit + '.d')
policy = dropdir / 'zzzz-pave-d0.conf'
assert not dropdir.is_symlink() and dropdir.is_dir()
assert list(dropdir.iterdir()) == [policy]
for owned in (op / 'zzzz-pave-d0.conf', policy):
    info = owned.lstat()
    assert stat.S_ISREG(info.st_mode) and (info.st_uid, info.st_gid, info.st_nlink) == (0, 0, 1)
    assert stat.S_IMODE(info.st_mode) == 0o444
    assert hashlib.sha256(owned.read_bytes()).hexdigest() == sys.argv[4]
policy.unlink()
dropdir.rmdir()
subprocess.run(['/usr/bin/systemctl', 'daemon-reload'], check=True)
assert meta.get('Id') == unit and re.fullmatch('[0-9a-f]{32}',meta.get('InvocationID',''))
assert meta.get('ControlGroup') == '/system.slice/'+unit
assert all(meta.get(key) == value for key, value in flags.items())
assert meta.get('TypedCredentialsEmpty') == 'yes'
assert raw_exit == 0 and meta.get('Result') == 'success' and meta.get('ExecMainStatus') == '0'
report=json.loads(next(line for line in lines if line.startswith('{')))
result = {'status': 'RAW_UNIT_AND_CLEANUP_OBSERVED', 'operation': op.name, 'unit': unit,
          'invocation_id': meta['InvocationID'], 'cgroup_empty': empty, 'raw_unit_exit': raw_exit,
          'effective_hardening': {key: meta[key] for key in flags}, 'typed_credentials_empty': True,
          'owned_policy_removed': True, 'policy_sha256': sys.argv[4],
          'producer_report_sha256': hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest(),
          'semantic_acceptance': 'REQUIRES_INDEPENDENT_READER'}
(op/'OUTSIDE-RESULT.PUBLIC.json').write_text(json.dumps(result,sort_keys=True)+'\n')
print(json.dumps(result,sort_keys=True))
AUDIT

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
pave_sum=$(sha256sum "$pave_op/inputs/SHA256SUMS")
test "${pave_sum%% *}" = "$pave_sums_sha"
(cd "$pave_op/inputs" && sha256sum --check --strict --status SHA256SUMS)
pave_actors=$(ps -eo uid=,pid=,comm= | awk '$1 == 999 {print}')
test -z "$pave_actors"
for pave_policy in /etc/claude-code/managed-settings.json /etc/claude-code/managed-mcp.json; do
  test ! -e "$pave_policy"
done
install -d -o 999 -g 990 -m 0700 "$pave_op/run"
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
  -p BindPaths="$pave_op/run:/work" \
  -p BindReadOnlyPaths="$pave_op/inputs/operator.py:/work/operator.py $pave_op/inputs/case.PUBLIC.json:/work/case.PUBLIC.json $pave_op/inputs/payload.tar:/work/payload.tar $pave_op/inputs/instruments:/work/instruments" \
  -p WorkingDirectory=/work -p UMask=0077 -p RuntimeMaxSec=240s -p TimeoutStopSec=3s \
  -p KillMode=control-group -p TasksMax=128 -p MemoryMax=1G -p LimitFSIZE=131072 \
  -p "ExecStartPre=$pave_pre_gate pre" \
  -p "ExecStopPost=$pave_pre_gate post" \
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B \
  /work/operator.py /work/case.PUBLIC.json \
  >"$pave_op/outer.stdout" 2>"$pave_op/outer.stderr" || pave_status=$?
/usr/bin/python3 -I -S -B - "$pave_op" "$pave_unit" "$pave_status" "$pave_policy_sha" <<'AUDIT'
import hashlib,json,pathlib,re,stat,subprocess,sys
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
assert meta.get('Id') == unit and re.fullmatch('[0-9a-f]{32}',meta.get('InvocationID',''))
assert meta.get('ControlGroup') == '/system.slice/'+unit
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
assert all(meta.get(key) == value for key, value in flags.items())
assert meta.get('TypedCredentialsEmpty') == 'yes'
assert raw_exit == 0 and meta.get('Result') == 'success' and meta.get('ExecMainStatus') == '0'
report=json.loads(next(line for line in lines if line.startswith('{')))
assert report['status'] == 'ACQUISITION_AND_INSTALLED_R0_EXECUTION_ONLY'
root=op/'run';metadata=root/'config/plugins/installed_plugins.json'
entry=json.loads(metadata.read_text())['plugins']['autonomous-dev@adev-d0-native-consumer'][0]
inside=pathlib.Path(entry['installPath']);assert inside.is_relative_to('/work/config/plugins/cache')
installed=root/inside.relative_to('/work');assert installed.resolve().is_relative_to((root/'config/plugins/cache').resolve())
case=json.loads((op/'inputs/case.PUBLIC.json').read_text());leaf=installed/'scripts/control_evidence.py'
assert not any(p.is_symlink() for p in installed.rglob('*'))
assert sorted(str(p.relative_to(installed)) for p in installed.rglob('*') if p.is_file()) == ['.claude-plugin/plugin.json','scripts/control_evidence.py']
assert hashlib.sha256(leaf.read_bytes()).hexdigest() == case['pins']['leaf']
assert hashlib.sha256((installed/'.claude-plugin/plugin.json').read_bytes()).hexdigest() == case['pins']['manifest']
assert leaf.stat().st_ino == report['restored_leaf_inode'] and leaf.stat().st_nlink == 1
result={'status':'D0_FAMILY_CASES_AND_CLEANUP_OBSERVED','operation':op.name,'unit':unit,'invocation_id':meta['InvocationID'],'cgroup_empty':empty,'raw_unit_exit':raw_exit,'cases':report['cases'],'broken_route_restored':report['broken_route_refused_and_restored'],'installed_leaf_sha256':case['pins']['leaf'],'native_hooks_loaded':'UNMEASURED','effective_hardening':{key:meta[key] for key in flags},'credentials_absent':True,'owned_policy_removed':True,'policy_sha256':sys.argv[4]}
(op/'OUTSIDE-RESULT.PUBLIC.json').write_text(json.dumps(result,sort_keys=True)+'\n')
print(json.dumps(result,sort_keys=True))
AUDIT

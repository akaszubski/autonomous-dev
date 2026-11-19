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
  test "$(stat -c %u:%h "$pave_upload/$pave_file")" = 501:1
  install -o 0 -g 0 -m 0444 "$pave_upload/$pave_file" "$pave_op/inputs/$pave_file"
done
for pave_file in oracle.sh trustcheck.py; do
  test -f "$pave_upload/$pave_file" && test ! -L "$pave_upload/$pave_file"
  test "$(stat -c %u:%h "$pave_upload/$pave_file")" = 501:1
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
pave_status=0
systemd-run --unit="$pave_unit" --wait --pipe --collect \
  -p Type=exec -p Slice=system.slice -p User=root -p Group=root \
  -p CapabilityBoundingSet='CAP_SETUID CAP_SETGID CAP_SETPCAP' -p AmbientCapabilities= \
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
  -p 'ExecStopPost=/usr/bin/systemctl show %n --property=Id,InvocationID,ControlGroup,Result,ExecMainCode,ExecMainStatus' \
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/setpriv --reuid=999 --regid=990 \
  --clear-groups --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs \
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B \
  /work/operator.py /work/case.PUBLIC.json \
  >"$pave_op/outer.stdout" 2>"$pave_op/outer.stderr" || pave_status=$?
/usr/bin/python3 -I -S -B - "$pave_op" "$pave_unit" "$pave_status" <<'AUDIT'
import hashlib,json,pathlib,re,sys
op=pathlib.Path(sys.argv[1]);unit=sys.argv[2];raw_exit=int(sys.argv[3])
cgroup=pathlib.Path('/sys/fs/cgroup/system.slice')/unit
empty=not cgroup.exists() or not (cgroup/'cgroup.procs').read_text().strip()
assert empty, 'owned service cgroup is not empty; preserve and recover through manager'
stdout=(op/'outer.stdout').read_text();lines=stdout.splitlines()
meta=dict(line.split('=',1) for line in lines if line.startswith(('Id=','InvocationID=','ControlGroup=','Result=','ExecMainCode=','ExecMainStatus=')))
assert meta.get('Id') == unit and re.fullmatch('[0-9a-f]{32}',meta.get('InvocationID',''))
assert meta.get('ControlGroup') == '/system.slice/'+unit
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
result={'status':'D0_FAMILY_CASES_AND_CLEANUP_OBSERVED','operation':op.name,'unit':unit,'invocation_id':meta['InvocationID'],'cgroup_empty':empty,'raw_unit_exit':raw_exit,'cases':report['cases'],'broken_route_restored':report['broken_route_refused_and_restored'],'installed_leaf_sha256':case['pins']['leaf'],'native_hooks_loaded':'UNMEASURED'}
(op/'OUTSIDE-RESULT.PUBLIC.json').write_text(json.dumps(result,sort_keys=True)+'\n')
print(json.dumps(result,sort_keys=True))
AUDIT

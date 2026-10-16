#!/usr/bin/env python3
"""Run a frozen source tree five times; retain raw evidence, not boot claims."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gtk-runtime', type=Path, help='Optional private dependency prefix; omit on a prepared Arch VM')
parser.add_argument('--disable-leak-check', action='store_true', help='Only for restricted environments where LeakSanitizer cannot inspect tasks')
parser.add_argument('--output', type=Path, help='New evidence directory; never overwrite an earlier run')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = args.output or root / '.build' / ('verification-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
try:
    if out.is_symlink(): raise FileExistsError(str(out))
    out.mkdir(parents=True, exist_ok=False)
except FileExistsError:
    parser.error('Evidence output already exists; choose a new directory: ' + str(out))
runtime = args.gtk_runtime.resolve() if args.gtk_runtime else None
base_env = dict(os.environ, PYTHONPATH=str(root / 'src'))
gtk_env = dict(base_env)
if runtime:
    gtk_env = dict(base_env,
    LD_LIBRARY_PATH=str(runtime / 'usr/lib/x86_64-linux-gnu'),
    GI_TYPELIB_PATH=str(runtime / 'usr/lib/x86_64-linux-gnu/girepository-1.0'),
    PYTHONPATH=str(runtime / 'usr/lib/python3/dist-packages') + ':' + str(root / 'src'))

def snapshot():
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=root).split(b'\0')
    files = {}
    for raw in sorted(set(paths)):
        if not raw: continue
        name = raw.decode()
        if name.startswith('docs/') or name in ('README.md', 'CHANGELOG.md'): continue
        p = root / name
        if p.is_file(): files[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {'sha256': digest, 'files': files}

worker = '''import json, sys, unittest
from pathlib import Path
suite = unittest.defaultTestLoader.discover('tests')
result = unittest.TextTestRunner(verbosity=2).run(suite)
summary = {'discovered':result.testsRun, 'executed':result.testsRun-len(result.skipped),
 'passed':result.testsRun-len(result.skipped)-len(result.failures)-len(result.errors)-len(result.expectedFailures),
 'failed':len(result.failures)+len(result.errors), 'skipped':len(result.skipped),
 'expected_failures':len(result.expectedFailures),
 'skip_details':[{'test':str(test), 'reason':reason} for test,reason in result.skipped],
 'failure_details':[{'test':str(test), 'traceback':trace} for test,trace in result.failures+result.errors]}
Path(sys.argv[1]).write_text(json.dumps(summary,indent=2)+'\\n')
sys.exit(0 if result.wasSuccessful() else 1)
'''
before = snapshot()
(out / 'source-snapshot.json').write_text(json.dumps(before, indent=2) + '\n')
checks = [
 ('unit', [sys.executable, '-c', worker], base_env, False),
 ('syntax', [sys.executable, 'scripts/check-source.py'], base_env, False),
 ('native', ['make', '-B', 'native'] + (['WAYLAND_SCANNER=' + str(runtime / 'usr/bin/wayland-scanner'),
   'WAYLAND_CFLAGS=-I' + str(runtime / 'usr/include'), 'WAYLAND_LIBS=-l:libwayland-client.so.0'] if runtime else []), base_env, False),
 ('c-sanitizers', ['make', 'test-c'], dict(base_env, **({'ASAN_OPTIONS':'detect_leaks=0'} if args.disable_leak_check else {})), False),
 ('gtk-import', ['/usr/bin/python3', '-c',
  'from ownos.ui import common, control, file_manager, launcher, panel, shell, notification_service; '
  'assert common.Gio.DBusNodeInfo.new_for_xml(shell.CONTROL_XML).interfaces[0].name == "org.ownos.Desktop"; '
  'print("Actual GTK imports and status D-Bus XML: PASS (no window/display test)")'], gtk_env, False),
 ('gtk-css', ['/usr/bin/python3', 'scripts/test-style.py'], gtk_env, False),
 ('packages-preflight', ['bash', 'scripts/build-packages.sh', '--check'], base_env, True),
 ('iso-preflight', ['bash', 'scripts/build-iso.sh', '--check'], base_env, True),
 ('qemu-preflight', [sys.executable, 'scripts/test-vm.py', '--check'], base_env, True),
]
rounds = []
for index in range(1, 6):
    directory = out / f'round-{index}'
    directory.mkdir(exist_ok=True)
    record = {'round':index, 'started_utc':datetime.now(timezone.utc).isoformat(), 'checks':[]}
    for name, argv, env, preflight in checks:
        command = argv + [str(directory / 'unit.json')] if name == 'unit' else argv
        try:
            completed = subprocess.run(command, cwd=root, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            status = ('ready' if completed.returncode == 0 else 'blocked') if preflight else ('passed' if completed.returncode == 0 else 'failed')
            item = {'name':name,'command':command,'returncode':completed.returncode,'status':status,'log':f'round-{index}/{name}.txt'}
            (directory / f'{name}.txt').write_text(completed.stdout)
            if name == 'syntax':
                match = re.search(r'(\d+) source/configuration syntax checks passed',completed.stdout)
                item['checked_files'] = int(match.group(1)) if match else None
        except subprocess.TimeoutExpired as error:
            item = {'name':name,'command':command,'status':'timeout','log':f'round-{index}/{name}.txt'}
            (directory / f'{name}.txt').write_text(str(error))
        record['checks'].append(item)
    unit = directory / 'unit.json'
    record['unit'] = json.loads(unit.read_text()) if unit.exists() else None
    record['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (directory / 'record.json').write_text(json.dumps(record,indent=2)+'\n')
    rounds.append(record)
    (out / 'results.json').write_text(json.dumps({'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(), 'source_sha256':before['sha256'],'source_unchanged_during_rounds':before == snapshot(), 'rounds':rounds},indent=2)+'\n')
    print(json.dumps({'round':index,'unit':{k:record['unit'][k] for k in ('discovered','executed','passed','failed','skipped')} if record['unit'] else None,
        'checks':[{k:item[k] for k in ('name','status')} for item in record['checks']]}),flush=True)
after = snapshot()
result = {'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
    'source_sha256':before['sha256'], 'source_unchanged_during_rounds':before == after,
    'scope':'Source/model/fixture checks; enabled GTK tests use the supplied display. No ISO boot or hardware acceptance is implied.',
    'environment':{'os_release':Path('/etc/os-release').read_text(), 'gtk_gui_tests_enabled':os.environ.get('OWNOS_UI_TESTS') == '1'},
    'leak_sanitizer_enabled':not args.disable_leak_check,'rounds':rounds}
(out / 'results.json').write_text(json.dumps(result,indent=2)+'\n')
print('Source unchanged:', before == after, flush=True)
sys.exit(1 if not result['source_unchanged_during_rounds'] or any(
    c['status'] in ('failed','timeout') for r in rounds for c in r['checks']) else 0)

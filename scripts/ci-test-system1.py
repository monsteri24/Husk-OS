#!/usr/bin/env python3
"""Boot the already published ISO via OVMF; collect real guest/VM evidence."""
import argparse
import hashlib
import http.server
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ownos.live import validate_live_status

OUT = ROOT / 'out/boot-system1'
HARDWARE_USB = None


def hardware_collector():
    spec=importlib.util.spec_from_file_location('husk_hardware_report',ROOT/'scripts/collect-system-report.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def collector_digest():
    return hashlib.sha256((ROOT/'scripts/collect-system-report.py').read_bytes()).hexdigest()


def create_usb_sentinels(directory):
    """No disk/path input: only exclusive, newly allocated disposable files."""
    disks={}
    for name in ('nvme-test','sata-test'):
        path=directory/(name+'.raw')
        with path.open('xb') as stream:
            for _ in range(32): stream.write(bytes(range(256))*4096)
        disks[name]=path
    return disks


def usb_drive_options(iso, disks):
    return ['-drive','if=none,id=live,format=raw,readonly=on,file='+str(iso),
        '-device','qemu-xhci,id=xhci', '-device','usb-storage,bus=xhci.0,drive=live,bootindex=1',
        '-drive','if=none,id=nvme-test,format=raw,file='+str(disks['nvme-test']),
        '-device','nvme,drive=nvme-test,serial=HUSK-NVME',
        '-drive','if=none,id=sata-test,format=raw,file='+str(disks['sata-test']),
        '-device','ide-hd,drive=sata-test,bus=ide.0,serial=HUSK-SATA']


def validate_usb_blockstats(stats):
    problems=[]
    for name in ('nvme-test','sata-test'):
        matches=[item.get('stats',{}) for item in stats if item.get('device')==name]
        if len(matches)!=1:
            problems.append('Missing/duplicate sentinel statistics: '+name); continue
        values=matches[0]
        keys=('wr_bytes','wr_operations','unmap_bytes','unmap_operations','failed_wr_operations',
              'invalid_wr_operations','failed_unmap_operations','invalid_unmap_operations')
        if any(type(values.get(key)) is not int or values[key]!=0 for key in keys):
            problems.append('Sentinel data write/unmap or missing observation: '+name)
        if type(values.get('flush_operations')) is not int or values['flush_operations']<0:
            problems.append('Missing sentinel flush observation: '+name)
    return problems


def observe_usb_shutdown(monitor, timeout=45):
    # Hardware mode alone uses -no-shutdown, so the guest can power off while
    # QMP retains final counters. A merely paused/running guest is insufficient.
    deadline=time.monotonic()+timeout
    while True:
        status=monitor.command('query-status')
        if status.get('status')=='shutdown' and status.get('running') is False:
            return dict(guest_status=status,blockstats=monitor.command('query-blockstats'))
        if time.monotonic()>=deadline: raise RuntimeError('Guest shutdown was not observed')
        time.sleep(0.5)


def validate_hardware_usb(state, mode):
    if not isinstance(state,dict): return ['Missing actual USB guest observations']
    devices=state.get('pci_storage',[])
    if mode=='protected':
        problems=hardware_collector().validate_live_usb(state)
        if {item.get('class_code') for item in devices}!={'0x010802','0x010601'}:
            problems.append('Both attached internal controllers must remain observable in PCI')
        return problems
    if mode!='control': return ['Unknown USB test mode']
    # This is an expected unsafe negative control on disposable VM files only.
    # It must expose both disks/drivers and be rejected by the physical safety gate.
    try:
        disks=json.loads(state['probes']['storage']['stdout'])['blockdevices']
        kinds={item.get('tran') for item in disks if item.get('type')=='disk'}
        drivers={(item.get('class_code'),item.get('driver')) for item in devices}
        if (kinds!={'usb','nvme','sata'} or drivers!={('0x010802','nvme'),('0x010601','ahci')} or
            any(token.startswith('module_blacklist=') for token in state.get('kernel_cmdline','').split()) or
            not hardware_collector().validate_live_usb(state)):
            return ['Negative control did not expose both NVMe/AHCI disks and fail the safety gate']
    except (KeyError,TypeError,ValueError): return ['Missing negative-control disk observations']
    return []


def edit_usb_boot(monitor, mode):
    # systemd-boot documents holding/repeatedly pressing Space to show its menu.
    for _ in range(80): monitor.key('spc'); time.sleep(0.1)
    monitor.capture('uefi-usb-menu')
    monitor.key('e'); time.sleep(0.5); monitor.key('end')
    options=hardware_collector().USB_BOOT_OPTIONS
    if mode=='control': options=tuple(option for option in options if not option.startswith('module_blacklist='))
    monitor.type_console(' '+' '.join(options),submit=False)
    monitor.capture('uefi-usb-edited-options')
    monitor.key('ret')


def validate_live_write_space(guest):
    """Observe the normal ISO's effective mount, independently of kernel overrides."""
    problems = []
    commandline = guest.get('kernel_cmdline')
    if not isinstance(commandline, str) or 'cow_spacesize=50%' not in commandline.split():
        problems.append('Normal ISO boot did not use the requested Live write-space limit')
    space = guest.get('live_write_space')
    memory = guest.get('memory_total_bytes')
    total = space.get('total_bytes') if isinstance(space, dict) else None
    if (not isinstance(space, dict) or space.get('filesystem') != 'tmpfs' or
            type(memory) is not int or memory <= 0 or type(total) is not int or
            total <= 1024**3 or not 0.48 <= total/memory <= 0.52):
        problems.append('Normal ISO boot did not provide an effective half-RAM Live tmpfs')
    return problems


def verified_recovered_boot(build, boot, source, sha256, size, version='v3-phase2'):
    """Reuse only successful Live proof for the identical inspected image.

    A missing prior boot is a request to run it, never evidence of success.
    Release size eligibility is a separate gate from diagnostic VM testing.
    """
    if (not isinstance(build,dict) or build.get('source_commit') != source or build.get('iso_bytes') != size or
            any(not isinstance(build.get(name),dict) or build[name].get('status') != 'PASS'
                for name in ('rootfs','v3_rootfs'))):
        raise ValueError('Recovered image build/payload evidence does not match the expected source and size')
    if boot is None: return None
    if (not isinstance(boot,dict) or boot.get('iso_sha256') != sha256 or boot.get('iso_bytes') != size or
            any(boot.get(name) != 'PASSED' for name in ('boot','terminal','shutdown')) or boot.get('problems')):
        raise ValueError('Prior Live boot evidence does not prove this exact image booted successfully')
    status=boot.get('desktop_status')
    if validate_live_status(status) or status.get('version') != version:
        raise ValueError('Prior Live boot evidence does not prove the expected Live Wayland desktop/version')
    return dict(boot)


PROBE = r'''import json, os, pathlib, subprocess, urllib.request
info = {'uid': os.getuid(), 'live': pathlib.Path('/run/archiso').is_dir(), 'terminals': []}
try:
    info['kernel_cmdline'] = pathlib.Path('/proc/cmdline').read_text().strip()
    info['memory_total_bytes'] = int(next(line.split()[1] for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))) * 1024
    space = os.statvfs('/run/archiso/cowspace')
    filesystem = subprocess.run(['/usr/bin/findmnt','-n','-o','FSTYPE','/run/archiso/cowspace'], capture_output=True, text=True, check=True, timeout=5).stdout.strip()
    info['live_write_space'] = dict(total_bytes=space.f_blocks*space.f_frsize, available_bytes=space.f_bavail*space.f_frsize, filesystem=filesystem)
except (OSError, ValueError, StopIteration, subprocess.SubprocessError) as exc:
    info['live_write_space_error'] = str(exc)
env = os.environ.copy()
for directory in pathlib.Path('/proc').iterdir():
    if not directory.name.isdigit(): continue
    try:
        executable = (directory / 'exe').readlink()
        if executable.name == 'foot': info['terminals'].append(int(directory.name))
    except OSError: pass
for directory in pathlib.Path('/proc').iterdir():
    if not directory.name.isdigit(): continue
    try:
        args = (directory / 'cmdline').read_bytes()
        if b'/usr/bin/husk-desktop' not in args: continue
        values = dict(item.split(b'=', 1) for item in (directory / 'environ').read_bytes().split(b'\0') if b'=' in item)
        for key in ('DBUS_SESSION_BUS_ADDRESS','XDG_RUNTIME_DIR','WAYLAND_DISPLAY','GDK_BACKEND','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'):
            if key.encode() in values: env[key] = values[key.encode()].decode()
        info['desktop_pid'] = int(directory.name)
        break
    except (OSError, ValueError): pass
for name in ('husk-status','husk-live-smoke','husk-toggle-start'):
    try:
        result = subprocess.run([name], env=env, capture_output=True, text=True, timeout=15)
        info[name] = {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    except Exception as exc: info[name] = {'error': str(exc)}
try: info['status'] = json.loads(info['husk-status']['stdout'])
except (KeyError, ValueError): info['status'] = {}
try: info['session_log'] = pathlib.Path.home().joinpath('.local/state/ownos/session.log').read_text(errors='replace')[-131072:]
except OSError as exc: info['session_log_error'] = str(exc)
try:
    result = subprocess.run(['journalctl','-b','--no-pager','-n','200'], capture_output=True, text=True, timeout=10)
    info['journal'] = result.stdout
except Exception as exc: info['journal_error'] = str(exc)
data = json.dumps(info).encode()
urllib.request.urlopen(urllib.request.Request('http://10.0.2.2:8765/result', data=data, method='POST'), timeout=10).read()
print(json.dumps(info['status']))
'''


def hardware_probe():
    extra="""source=urllib.request.urlopen('http://10.0.2.2:8765/collector',timeout=10).read()
import hashlib
if hashlib.sha256(source).hexdigest() != %r: raise RuntimeError('Collector digest mismatch')
collector={'__name__':'husk_usb_diagnostics'}
exec(compile(source,'<verified hardware collector>','exec'),collector)
info['hardware']=collector['hardware_state']()
info['usb_safety_problems']=collector['validate_live_usb'](info['hardware'])
""" % collector_digest()
    return PROBE.replace('data = json.dumps(info).encode()',extra+'data = json.dumps(info).encode()')


class EvidenceServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/collector' and HARDWARE_USB:
            data=(ROOT/'scripts/collect-system-report.py').read_bytes()
        elif self.path == '/probe':
            data=(hardware_probe() if HARDWARE_USB else PROBE).encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        size = int(self.headers.get('Content-Length', '0'))
        if self.path != '/result' or not 0 < size <= 1024 * 1024:
            self.send_error(400)
            return
        data = self.rfile.read(size)
        json.loads(data)
        (OUT / 'guest.json').write_bytes(data)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_):
        pass


class Monitor:
    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(10)
        self.socket.connect(str(path))
        self.stream = self.socket.makefile('rwb', buffering=0)
        self.stream.readline()
        self.command('qmp_capabilities')

    def command(self, name, arguments=None):
        self.stream.write((json.dumps({'execute': name, 'arguments': arguments or {}}) + '\n').encode())
        while True:
            response = json.loads(self.stream.readline())
            if 'error' in response:
                raise RuntimeError(response['error'])
            if 'return' in response:
                return response['return']

    def key(self, keys):
        response = self.command('human-monitor-command', {'command-line': 'sendkey ' + keys})
        if response.strip():
            raise RuntimeError('QEMU keyboard input failed: ' + response)
        time.sleep(0.05)

    def type_console(self, text, submit=True):
        # The rescue Linux console uses upstream US keymap; Labwc uses Finnish.
        punctuation = {' ': 'spc', '-': 'minus', '/': 'slash', '.': 'dot', ':': 'shift-semicolon',
                       ';': 'semicolon', '=':'equal', ',':'comma', '_':'shift-minus'}
        for char in text:
            self.key(punctuation.get(char, ('shift-' + char.lower()) if char.isupper() else char))
        if submit: self.key('ret')

    def capture(self, name):
        from PIL import Image
        ppm = OUT / (name + '.ppm')
        self.command('screendump', {'filename': str(ppm)})
        with Image.open(ppm) as frame:
            frame.save(OUT / (name + '.png'))
        ppm.unlink()


def request_guest_evidence(monitor):
    # A DRM compositor needs its own VT active even while starting. The first
    # run left tty2 active and made Labwc time out waiting for its seat.
    try:
        monitor.key('ctrl-alt-f2')
        time.sleep(0.7)
        monitor.type_console('curl -fsS -o /tmp/probe.py http://10.0.2.2:8765/probe; python3 /tmp/probe.py')
    finally:
        monitor.key('ctrl-alt-f1')


def main(iso=None, artifacts=None, expected_version=None, require_live_write_space=False, hardware_usb=None):
    global OUT, HARDWARE_USB
    HARDWARE_USB=hardware_usb
    if artifacts is not None:
        OUT = Path(artifacts).resolve()
    OUT.mkdir(parents=True, exist_ok=False)
    iso = Path(iso).resolve() if iso is not None else ROOT / 'out/HuskOS-system-1.iso'
    code = Path('/usr/share/OVMF/OVMF_CODE_4M.fd')
    template = Path('/usr/share/OVMF/OVMF_VARS_4M.fd')
    if not iso.is_file() or not code.is_file() or not template.is_file():
        raise RuntimeError('Published ISO or OVMF firmware is missing')
    variables = OUT / 'OVMF_VARS.fd'
    shutil.copyfile(template, variables)
    kvm = os.access('/dev/kvm', os.R_OK | os.W_OK)
    disks=create_usb_sentinels(OUT) if hardware_usb else {}
    hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in disks.items()}
    media=(usb_drive_options(iso,disks) if hardware_usb else
           ['-cdrom',str(iso),'-boot','d','-device','qemu-xhci'])
    command = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'kvm' if kvm else 'tcg',
               '-cpu', 'host' if kvm else 'max', '-m', '4096', '-smp', '2',
               '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(code),
               '-drive', 'if=pflash,format=raw,file=' + str(variables),
               *media, *(['-no-shutdown'] if hardware_usb else []),
               '-device', 'virtio-vga', '-device', 'usb-tablet',
               '-nic', 'user,model=virtio-net-pci', '-display', 'none',
               '-serial', 'file:' + str(OUT / 'serial.log'),
               '-qmp', 'unix:' + str(OUT / 'monitor.sock') + ',server=on,wait=off']
    (OUT / 'qemu-command.json').write_text(json.dumps(command, indent=2))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), EvidenceServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result = {'iso': iso.name, 'accelerator': 'kvm' if kvm else 'tcg',
              'boot': 'FAILED', 'shutdown': 'NOT TESTED', 'problems': []}
    if hardware_usb: result['hardware_usb']=dict(mode=hardware_usb,status='FAILED',collector_sha256=collector_digest())
    with iso.open('rb') as stream:
        result['iso_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    result['iso_bytes'] = iso.stat().st_size
    with (OUT / 'qemu.log').open('wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 30
            while not (OUT / 'monitor.sock').exists() and time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError('QEMU exited before monitor startup')
                time.sleep(0.2)
            monitor = Monitor(OUT / 'monitor.sock')
            if hardware_usb: edit_usb_boot(monitor,hardware_usb)
            started = time.monotonic()
            attempt = 0
            next_probe = 45 if kvm else 300
            while time.monotonic() - started < 600:
                elapsed = int(time.monotonic() - started)
                if process.poll() is not None: raise RuntimeError('Guest/QEMU exited before desktop acceptance')
                monitor.capture('frame-' + str(elapsed).zfill(3))
                guest = OUT / 'guest.json'
                if guest.is_file():
                    data = json.loads(guest.read_text())
                    problems = validate_live_status(data.get('status'))
                    if expected_version and data.get('status', {}).get('version') != expected_version:
                        problems.append('Guest version differs from expected source: ' + expected_version)
                    if require_live_write_space:
                        space_problems = validate_live_write_space(data)
                        if space_problems:
                            raise RuntimeError('; '.join(space_problems))
                    if data.get('uid') == 1000 and data.get('live') is True and not problems and data.get('husk-live-smoke', {}).get('exit') == 0:
                        if hardware_usb:
                            hardware_problems=validate_hardware_usb(data.get('hardware'),hardware_usb)
                            result['hardware_usb'].update(guest=data.get('hardware'),
                                safety_problems=data.get('usb_safety_problems'),problems=hardware_problems)
                            if hardware_problems: raise RuntimeError('; '.join(hardware_problems))
                            result['hardware_usb']['status']='PASSED'
                        result.update(boot='PASSED', desktop_status=data['status'], problems=[])
                        if require_live_write_space:
                            result.update(live_write_space=data['live_write_space'], memory_total_bytes=data['memory_total_bytes'],
                                          kernel_cmdline=data['kernel_cmdline'])
                        break
                    result['problems'] = problems
                if elapsed >= next_probe:
                    attempt += 1
                    request_guest_evidence(monitor)
                    print('Guest evidence request', attempt, 'at', elapsed, 'seconds', flush=True)
                    next_probe = elapsed + 60
                time.sleep(10)
            if result['boot'] != 'PASSED' and not result['problems']:
                result['problems'].append('600-second deadline expired without accepted guest evidence.')
            if result['boot'] == 'PASSED':
                monitor.key('ctrl-alt-f1')
                time.sleep(5)
                monitor.capture('desktop-start')
                monitor.key('meta_l-ret')
                time.sleep(5)
                if expected_version:
                    previous_count = result['desktop_status'].get('window_count', 0)
                    guest.unlink(missing_ok=True)
                    request_guest_evidence(monitor)
                    deadline = time.monotonic() + 40
                    result['terminal'] = 'FAILED'
                    while time.monotonic() < deadline:
                        if guest.is_file():
                            after = json.loads(guest.read_text())
                            if after.get('terminals') and after.get('status', {}).get('window_count', 0) > previous_count:
                                result['terminal'] = 'PASSED'
                                result['terminal_pids'] = after['terminals']
                                break
                        time.sleep(1)
                    if result['terminal'] != 'PASSED':
                        result['problems'].append('Terminal shortcut did not produce an observed Foot window/process.')
                monitor.capture('desktop-terminal')
                result['terminal_shortcut_sent'] = True
                if hardware_usb:
                    stats=monitor.command('query-blockstats')
                    result['hardware_usb']['pre_shutdown_blockstats']=stats
                    result['problems']+=validate_usb_blockstats(stats)
                monitor.command('system_powerdown')
                if hardware_usb:
                    final=observe_usb_shutdown(monitor)
                    result['hardware_usb']['after_guest_shutdown']=final
                    result['problems']+=validate_usb_blockstats(final['blockstats'])
                    monitor.command('quit')
                try:
                    result['shutdown'] = 'PASSED' if process.wait(timeout=45) == 0 else 'FAILED'
                except subprocess.TimeoutExpired:
                    result['shutdown'] = 'FAILED'
        except Exception as exc:
            result['problems'].append(str(exc))
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
            server.shutdown()
            if hardware_usb:
                after={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in disks.items()}
                result['hardware_usb'].update(sentinel_sha256_before=hashes,sentinel_sha256_after_shutdown=after)
                if hashes!=after: result['problems'].append('A disposable sentinel changed during boot/session/shutdown')
                if result['problems'] or result['shutdown']!='PASSED': result['hardware_usb']['status']='FAILED'
            (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
    return 0 if (result['boot'] == 'PASSED' and result['shutdown'] == 'PASSED'
                 and (not expected_version or result.get('terminal') == 'PASSED')
                 and (not hardware_usb or result['hardware_usb']['status']=='PASSED')) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', type=Path)
    parser.add_argument('--artifacts', type=Path)
    parser.add_argument('--expected-version')
    parser.add_argument('--require-live-write-space', action='store_true')
    parser.add_argument('--hardware-usb',choices=('control','protected'))
    args = parser.parse_args()
    raise SystemExit(main(args.iso, args.artifacts, args.expected_version, args.require_live_write_space,args.hardware_usb))

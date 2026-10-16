#!/usr/bin/env python3
"""Boot the already published ISO via OVMF; collect real guest/VM evidence."""
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ownos.live import validate_live_status

OUT = ROOT / 'out/boot-system1'
PROBE = r'''import json, os, pathlib, subprocess, urllib.request
info = {'uid': os.getuid(), 'live': pathlib.Path('/run/archiso').is_dir()}
env = os.environ.copy()
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


class EvidenceServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/probe':
            self.send_error(404)
            return
        data = PROBE.encode()
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

    def type_console(self, text):
        # The rescue Linux console uses upstream US keymap; Labwc uses Finnish.
        punctuation = {' ': 'spc', '-': 'minus', '/': 'slash', '.': 'dot', ':': 'shift-semicolon', ';': 'semicolon'}
        for char in text:
            self.key(punctuation.get(char, ('shift-' + char.lower()) if char.isupper() else char))
        self.key('ret')

    def capture(self, name):
        ppm = OUT / (name + '.ppm')
        self.command('screendump', {'filename': str(ppm)})
        with Image.open(ppm) as frame:
            frame.save(OUT / (name + '.png'))
        ppm.unlink()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    iso = ROOT / 'out/HuskOS-system-1.iso'
    code = Path('/usr/share/OVMF/OVMF_CODE_4M.fd')
    template = Path('/usr/share/OVMF/OVMF_VARS_4M.fd')
    if not iso.is_file() or not code.is_file() or not template.is_file():
        raise RuntimeError('Published ISO or OVMF firmware is missing')
    variables = OUT / 'OVMF_VARS.fd'
    shutil.copyfile(template, variables)
    kvm = os.access('/dev/kvm', os.R_OK | os.W_OK)
    command = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'kvm' if kvm else 'tcg',
               '-cpu', 'host' if kvm else 'max', '-m', '4096', '-smp', '2',
               '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(code),
               '-drive', 'if=pflash,format=raw,file=' + str(variables),
               '-cdrom', str(iso), '-boot', 'd', '-device', 'virtio-vga',
               '-device', 'qemu-xhci', '-device', 'usb-tablet',
               '-nic', 'user,model=virtio-net-pci', '-display', 'none',
               '-serial', 'file:' + str(OUT / 'serial.log'),
               '-qmp', 'unix:' + str(OUT / 'monitor.sock') + ',server=on,wait=off']
    (OUT / 'qemu-command.json').write_text(json.dumps(command, indent=2))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), EvidenceServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result = {'iso': iso.name, 'accelerator': 'kvm' if kvm else 'tcg',
              'boot': 'FAILED', 'shutdown': 'NOT TESTED', 'problems': []}
    with (OUT / 'qemu.log').open('wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 30
            while not (OUT / 'monitor.sock').exists() and time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError('QEMU exited before monitor startup')
                time.sleep(0.2)
            monitor = Monitor(OUT / 'monitor.sock')
            started = time.monotonic()
            attempt = 0
            while time.monotonic() - started < 600:
                elapsed = int(time.monotonic() - started)
                if process.poll() is not None: raise RuntimeError('Guest/QEMU exited before desktop acceptance')
                monitor.capture('frame-' + str(elapsed).zfill(3))
                guest = OUT / 'guest.json'
                if guest.is_file():
                    data = json.loads(guest.read_text())
                    problems = validate_live_status(data.get('status'))
                    if data.get('uid') == 1000 and data.get('live') is True and not problems and data.get('husk-live-smoke', {}).get('exit') == 0:
                        result.update(boot='PASSED', desktop_status=data['status'])
                        break
                    result['problems'] = problems
                if elapsed >= 90:
                    attempt += 1
                    monitor.key('ctrl-alt-f2')
                    time.sleep(3)
                    monitor.type_console('curl -fsS -o /tmp/probe.py http://10.0.2.2:8765/probe; python3 /tmp/probe.py')
                    print('Guest evidence request', attempt, 'at', elapsed, 'seconds', flush=True)
                time.sleep(10)
            if result['boot'] == 'PASSED':
                monitor.key('ctrl-alt-f1')
                time.sleep(5)
                monitor.capture('desktop-start')
                monitor.key('meta_l-ret')
                time.sleep(5)
                monitor.capture('desktop-terminal')
                result['terminal_shortcut_sent'] = True
                monitor.command('system_powerdown')
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
            (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
    return 0 if result['boot'] == 'PASSED' and result['shutdown'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())

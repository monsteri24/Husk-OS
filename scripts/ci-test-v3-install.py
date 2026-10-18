#!/usr/bin/env python3
"""Install the real V3 ISO onto a newly created disposable UEFI VM disk.

The live phase uses a test-only debug VT to deliver a Qt mouse/keyboard fixture.
It executes the unmodified privileged wrapper, disk guard and Calamares jobs.
This tests installation, not the graphical polkit authorization dialog. The
second VM boots the resulting disk through OVMF with no ISO or kernel override,
logs in through SDDM and collects evidence as the newly created normal user.
Never pass a host disk: this script has no disk-path option and creates its own.
"""
import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import stat
import subprocess
import threading
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
DISK_SIZE = 32 * 1024 ** 3
REQUIRED_DRIVER_EVENTS = (
    'driver-started', 'page-welcome', 'page-keyboard', 'page-locale', 'timezone-selected',
    'drive-no-selection', 'drive-selected', 'erase-selected', 'users-entered',
    'summary-reviewed', 'confirmation-shown', 'confirmation-click',
    'page-execution', 'installation-success', 'countdown-observed',
    'restart-later-click', 'application-quit',
)
REQUIRED_TARGET_CHECKS = (
    'efi_partition', 'root_partition', 'fstab', 'user', 'kernel', 'initramfs',
    'grub', 'efi_fallback', 'version', 'live_cleanup', 'guard_job', 'copy_job',
    'users_job', 'initramfs_job', 'bootloader_job', 'timezone', 'keyboard', 'english_locale',
)


def redact_artifact_text(text, password):
    """Never preserve the generated credential or upstream usermod hash logs."""
    if password: text = text.replace(password, '[redacted-test-password]')
    return re.sub(r'\$(?:y|gy|6|5|2[aby]?)\$[A-Za-z0-9./$=+_-]+',
                  '[redacted-password-hash]', text)


def create_disposable_disk(directory):
    directory = Path(directory).resolve(strict=True)
    disk = directory / 'install-target.qcow2'
    if disk.exists() or disk.is_symlink():
        raise ValueError('Refusing to overwrite or reuse an existing installation disk')
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', str(disk), str(DISK_SIZE)],
                   check=True, capture_output=True, text=True)
    info = json.loads(subprocess.check_output(['qemu-img', 'info', '--output=json', str(disk)], text=True))
    if (disk.is_symlink() or not stat.S_ISREG(disk.stat().st_mode) or
            info.get('format') != 'qcow2' or info.get('virtual-size') != DISK_SIZE or
            info.get('backing-filename') or info.get('full-backing-filename')):
        raise ValueError('The newly created disposable image did not pass its format/isolation check')
    return disk


def make_qemu_command(stage, *, artifacts, disk, iso, firmware_code, firmware_vars,
                      kernel, initrd, iso_label, kvm):
    if stage not in ('live', 'installed'):
        raise ValueError('Unknown VM phase')
    artifacts = Path(artifacts).resolve(strict=True)
    disk = Path(disk)
    if (disk.is_symlink() or disk.resolve() != artifacts/'install-target.qcow2' or
            not disk.is_file() or not stat.S_ISREG(disk.stat().st_mode)):
        raise ValueError('QEMU may attach only the new regular disk image inside this run directory')
    paths = [disk, firmware_code, firmware_vars, artifacts]
    if stage == 'live': paths += [iso, kernel, initrd]
    if any(any(character in str(path) for character in (',', '\n', '\0')) for path in paths):
        raise ValueError('QEMU paths contain unsupported option delimiters')
    monitor = artifacts / (stage + '.sock')
    if len(os.fsencode(monitor)) > 100:
        raise ValueError('The QMP socket path is too long')
    command = ['qemu-system-x86_64', '-nodefaults', '-machine', 'q35',
        '-accel', 'kvm' if kvm else 'tcg', '-cpu', 'host' if kvm else 'max',
        '-m', '4096', '-smp', '2', '-no-reboot',
        '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(firmware_code),
        '-drive', 'if=pflash,format=raw,file=' + str(firmware_vars),
        '-drive', 'if=none,id=target,format=qcow2,file=' + str(disk),
        '-device', 'virtio-blk-pci,drive=target,serial=HUSK-DISPOSABLE',
        '-device', 'virtio-vga', '-device', 'qemu-xhci', '-device', 'usb-tablet',
        '-nic', 'user,model=virtio-net-pci', '-display', 'none',
        '-serial', 'file:' + str(artifacts/(stage + '-serial.log')),
        '-qmp', 'unix:' + str(monitor) + ',server=on,wait=off']
    if stage == 'live':
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', iso_label):
            raise ValueError('The ISO label is not suitable for an unquoted archisolabel argument')
        command += ['-cdrom', str(iso), '-boot', 'order=d', '-kernel', str(kernel),
            '-initrd', str(initrd), '-append', 'archisobasedir=arch archisolabel=' + iso_label +
            ' systemd.debug_shell=1 console=tty0 console=ttyS0,115200n8']
    else:
        command += ['-boot', 'order=c']
    return command


def validate_install_report(report):
    problems = []
    if not isinstance(report, dict): return ['No installation report was received']
    for key in ('success', 'restart_postponed', 'offline', 'guard_target_accepted', 'live_medium_rejected', 'cancellation'):
        if report.get(key) is not True: problems.append('Installation evidence is missing: ' + key)
    if report.get('process_exit') != 0: problems.append('The real Calamares process did not exit successfully')
    events = {value.get('event') for value in report.get('events', []) if isinstance(value, dict)}
    for event in REQUIRED_DRIVER_EVENTS:
        if event not in events: problems.append('A required real GUI checkpoint is missing: ' + event)
    if 'driver-failed' in events: problems.append('The Qt input driver reported an acceptance failure')
    for name in ('cancel-click','cancel-confirmed'):
        if name not in events: problems.append('Real summary-page cancellation evidence is missing: '+name)
    for name in REQUIRED_TARGET_CHECKS:
        if report.get('target_checks', {}).get(name) is not True:
            problems.append('Installed target evidence is missing: ' + name)
    return problems


def validate_installed_report(report, version, username):
    problems = []
    if not isinstance(report, dict): return ['No installed-user report was received']
    if type(report.get('uid')) is not int or report['uid'] < 1000 or report.get('user') != username:
        problems.append('The evidence did not run as the newly created normal user')
    for key, expected in (('live', False), ('uefi', True), ('debug_shell', False)):
        if report.get(key) is not expected: problems.append('Installed boot check failed: ' + key)
    if not re.fullmatch(r'/dev/vda[1-9][0-9]*', report.get('root_device', '')) or report.get('root_fstype') != 'ext4':
        problems.append('The installed root is not the disposable virtio disk ext4 partition')
    if report.get('optical_media') != []: problems.append('Live/optical media remained attached')
    session = report.get('session', {})
    if session.get('Type') != 'wayland' or session.get('Name') != username or session.get('Remote') != 'no':
        problems.append('The real local SDDM Wayland session was not observed')
    status = report.get('status', {})
    if (status.get('version') != version or status.get('backend') != 'wayland' or status.get('live') is not False or
            status.get('bridge_connected') is not True or status.get('panel_mapped') is not True or
            status.get('desktop_surfaces', 0) < 1):
        problems.append('Installed Husk Desktop/version acceptance failed')
    packages = set(report.get('packages', []))
    if {'ownos-core','ownos-ui','ownos-desktop','linux','grub','sddm'} - packages:
        problems.append('Essential installed packages are missing')
    if packages.intersection({'calamares','ownos-live'}): problems.append('Live installer packages survived installation')
    return problems


# These fixtures run only inside the new VM. They are served from memory, never
# copied into the ISO/target, and the generated test password is never logged.
GUEST_SETUP = r'''
import hashlib, json, os, pathlib, re, subprocess, time, urllib.request
P = pathlib.Path
output = P('/tmp/husk-v3-calamares-output.log')
events_path = P('/tmp/husk-v3-driver.jsonl')
state = dict(phase='installation', success=False, events=[], target_checks={})
def command(argv, check=True, timeout=60):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode: raise RuntimeError(str(argv) + ': ' + result.stderr[-2000:])
    return result
def tail(path, maximum=1024*1024):
    try: return P(path).read_text(errors='replace')[-maximum:]
    except OSError: return ''
def events():
    values=[]
    for line in tail(events_path, 256*1024).splitlines():
        try: values.append(json.loads(line))
        except ValueError: pass
    return values
def post():
    state['events'] = events()
    state['calamares_output'] = tail(output)
    state['calamares_log'] = tail('/root/.cache/calamares/session.log')
    state['uptime'] = P('/proc/uptime').read_text().split()[0]
    state['boot_id'] = P('/proc/sys/kernel/random/boot_id').read_text().strip()
    try:
        text=json.dumps(state).replace(CONFIG['password'],'[redacted-test-password]')
        text=re.sub(r'\$(?:y|gy|6|5|2[aby]?)\$[A-Za-z0-9./$=+_-]+','[redacted-password-hash]',text)
        data=text.encode()
        urllib.request.urlopen(urllib.request.Request(CONFIG['base']+'/report',data=data,method='POST'),timeout=15).read()
    except Exception: pass
def routes():
    return command(['ip','-4','route','show','default']).stdout.strip() + command(['ip','-6','route','show','default']).stdout.strip()
def serial():
    return P('/sys/class/block/vda/serial').read_text().strip()
def disk_write_evidence():
    if serial()!='HUSK-DISPOSABLE': raise RuntimeError('Cancellation probe disk is not disposable')
    with open('/dev/vda','rb',buffering=0) as stream:
        first=stream.read(2*1024**2); stream.seek(32*1024**3-2*1024**2); last=stream.read(2*1024**2)
    return dict(sectors_written=int(P('/sys/class/block/vda/stat').read_text().split()[6]),
                partition_edges_sha256=hashlib.sha256(first+last).hexdigest())
def inspect_target():
    devices = json.loads(command(['lsblk','--json','-b','-o','PATH,TYPE,FSTYPE,UUID,PARTTYPE,SIZE,SERIAL']).stdout)
    disk = next(device for device in devices['blockdevices'] if device['path']=='/dev/vda')
    parts=disk.get('children',[])
    root=next(part for part in parts if part.get('fstype')=='ext4')
    esp=next(part for part in parts if part.get('fstype')=='vfat')
    if len(parts)!=2 or not all(re.fullmatch(r'/dev/vda[1-9][0-9]*',p['path']) for p in parts):
        raise RuntimeError('The disposable disk has an unexpected partition layout')
    mount=P('/mnt/husk-v3-check'); mount.mkdir(exist_ok=True)
    command(['e2fsck','-fn',root['path']],timeout=120)
    command(['mount','-o','ro,noload',root['path'],str(mount)])
    try:
        efi=mount/'boot/efi'
        command(['mount','-o','ro',esp['path'],str(efi)])
        try:
            passwd=(mount/'etc/passwd').read_text()
            users={line.split(':')[0]:line.split(':') for line in passwd.splitlines()}
            shadow={line.split(':')[0]:line.split(':')[1] for line in (mount/'etc/shadow').read_text().splitlines()}
            fstab=(mount/'etc/fstab').read_text()
            release=dict(line.split('=',1) for line in (mount/'etc/os-release').read_text().splitlines() if '=' in line)
            grub=(mount/'boot/grub/grub.cfg').read_text()
            logs=state.get('calamares_output','')+'\n'+state.get('calamares_log','')
            joblines='\n'.join(line for line in logs.splitlines() if 'Starting job' in line)
            checks=dict(efi_partition=esp.get('parttype','').lower()=='c12a7328-f81f-11d2-ba4b-00a0c93ec93b',
                root_partition=root.get('fstype')=='ext4',
                fstab=root['uuid'] in fstab and esp['uuid'] in fstab and '/boot/efi' in fstab,
                user=CONFIG['user'] in users and int(users[CONFIG['user']][2])>=1000 and
                    bool(shadow.get(CONFIG['user'])) and not shadow[CONFIG['user']].startswith(('!','*')),
                kernel=(mount/'boot/vmlinuz-linux').stat().st_size>1024*1024,
                initramfs=(mount/'boot/initramfs-linux.img').stat().st_size>1024*1024,
                grub='linux' in grub and 'initrd' in grub and root['uuid'] in grub and 'archisolabel' not in grub,
                efi_fallback=(efi/'EFI/BOOT/BOOTX64.EFI').stat().st_size>32768,
                version=release.get('ID','').strip('"')=='huskos' and release.get('VERSION_ID','').strip('"')==CONFIG['version'],
                live_cleanup='live' not in users and not (mount/'etc/sddm.conf.d/ownos-live.conf').exists() and
                    not (mount/'etc/systemd/system/ownos-live-setup.service').exists() and
                    not (mount/'tmp/husk-v3-driver.so').exists(),
                guard_job='Verify installation drive and protect Live USB' in joblines,
                copy_job='Filling up filesystems' in joblines,
                users_job=('Create user '+CONFIG['user']) in joblines,
                initramfs_job='mkinitcpio' in joblines,
                bootloader_job='Install bootloader' in joblines,
                timezone=(mount/'etc/localtime').is_symlink() and
                    str((mount/'etc/localtime').readlink()).endswith('/zoneinfo/Europe/Helsinki'),
                keyboard=json.loads((mount/'etc/ownos/keyboard.json').read_text())==dict(layout='us',variant=''),
                english_locale='LANG=en_US.UTF-8' in (mount/'etc/locale.conf').read_text())
            state['target_checks']=checks
            state['target_partitions']=devices
            state['target_fstab']=fstab
            state['target_jobs']=joblines
            state['target_grub_excerpt']=grub[-32768:]
            state['target_files']={}
            for relative in ('boot/vmlinuz-linux','boot/initramfs-linux.img','boot/efi/EFI/BOOT/BOOTX64.EFI'):
                path=mount/relative
                with path.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
                state['target_files'][relative]=dict(bytes=path.stat().st_size,sha256=digest)
        finally: command(['umount',str(efi)])
    finally: command(['umount',str(mount)])
try:
    if os.getuid()!=0 or not P('/run/archiso').is_dir() or not P('/sys/firmware/efi').is_dir() or serial()!='HUSK-DISPOSABLE':
        raise RuntimeError('The setup fixture is not in its marked disposable UEFI Live guest')
    before=json.loads(command(['lsblk','--json','-b','-o','PATH,TYPE,SIZE,SERIAL,RO,MOUNTPOINTS']).stdout)
    disks=[device for device in before['blockdevices'] if device['type']=='disk']
    if len(disks)!=1 or disks[0]['path']!='/dev/vda' or disks[0]['size']!=32*1024**3:
        raise RuntimeError('Guest disk isolation failed before launching the installer')
    state['devices_before']=before
    guard=command(['/usr/lib/ownos/husk-install-guard','snapshot','/dev/vda'])
    state['guard_target_accepted']=bool(re.fullmatch('[0-9a-f]{64}',guard.stdout.strip()))
    protected=command(['/usr/lib/ownos/husk-install-guard','snapshot','/dev/sr0'],check=False)
    state['live_medium_rejected']=protected.returncode!=0
    if not state['guard_target_accepted'] or not state['live_medium_rejected']:
        raise RuntimeError('The unmodified installation disk guard did not accept/reject the expected devices')
    command(['ip','-4','route','flush','default']); command(['ip','-6','route','flush','default'])
    state['offline']=not routes()
    if not state['offline']: raise RuntimeError('External default routes could not be removed for the offline install')
    P('/run/husk-v3-disposable-test').write_text('HUSK-DISPOSABLE\n')
    driver=P('/tmp/husk-v3-driver.so')
    urllib.request.urlretrieve(CONFIG['base']+'/driver.so',driver)
    if hashlib.sha256(driver.read_bytes()).hexdigest()!=CONFIG['driver_sha256']:
        raise RuntimeError('The test-only Qt input fixture digest differs from the host build')
    env=os.environ.copy(); desktop=None; deadline=time.monotonic()+420
    while time.monotonic()<deadline and desktop is None:
        for path in P('/proc').iterdir():
            if not path.name.isdigit(): continue
            try:
                if b'/usr/bin/husk-desktop' not in (path/'cmdline').read_bytes(): continue
                values=dict(item.split(b'=',1) for item in (path/'environ').read_bytes().split(b'\0') if b'=' in item)
                if b'DISPLAY' not in values: continue
                for key in ('DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS'):
                    if key.encode() in values: env[key]=values[key.encode()].decode()
                desktop=int(path.name); break
            except (OSError,ValueError): pass
        if desktop is None: post(); time.sleep(2)
    if desktop is None: raise RuntimeError('No actual Live desktop XWayland environment became available')
    if 'XAUTHORITY' not in env:
        for candidate in (P('/home/live/.Xauthority'),P('/run/user/1000/Xauthority')):
            if candidate.is_file(): env['XAUTHORITY']=str(candidate); break
    env.update(LD_PRELOAD=str(driver), HUSK_INSTALL_ACCEPTANCE='1',
        HUSK_INSTALL_DRIVER_LOG=str(events_path), HUSK_INSTALL_TEST_USER=CONFIG['user'],
        HUSK_INSTALL_TEST_PASSWORD=CONFIG['password'], QT_QUICK_BACKEND='software')
    state['live_desktop_pid']=desktop
    def run_installer(mode):
        env['HUSK_INSTALL_TEST_MODE']=mode
        with output.open('ab') as stream:
            process=subprocess.Popen(['/usr/lib/ownos/husk-installer-root'],env=env,stdout=stream,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+CONFIG['timeout']
            while process.poll() is None and time.monotonic()<deadline:
                post(); time.sleep(2)
            if process.poll() is None:
                process.terminate(); process.wait(timeout=30); raise RuntimeError('The real installer exceeded the VM deadline')
        return process
    state['cancellation_disk_before']=disk_write_evidence()
    cancelled=run_installer('cancel')
    state['cancellation_disk_after']=disk_write_evidence()
    cancel_events={event.get('event') for event in events()}
    state['cancellation']=(cancelled.returncode==0 and {'cancel-click','cancel-confirmed','application-quit'}<=cancel_events
        and 'page-execution' not in cancel_events and 'driver-failed' not in cancel_events
        and state['cancellation_disk_before']==state['cancellation_disk_after'])
    post()
    if not state['cancellation']: raise RuntimeError('Real cancellation did not leave the disposable disk untouched')
    process=run_installer('install')
    state['process_exit']=process.returncode; post()
    if process.returncode!=0: raise RuntimeError('Calamares or the input driver failed; inspect its real event/log evidence')
    names={event.get('event') for event in events()}
    if not {'installation-success','countdown-observed','restart-later-click','application-quit'} <= names:
        raise RuntimeError('Calamares exited without the required successful completion and Restart Later interaction')
    boot=P('/proc/sys/kernel/random/boot_id').read_text().strip()
    postponed=time.monotonic()
    while time.monotonic()-postponed<35:
        state['restart_wait_seconds']=round(time.monotonic()-postponed,1); post(); time.sleep(2)
    state['restart_postponed']=P('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
    state['offline']=state['offline'] and not routes()
    inspect_target()
    state['success']=state['restart_postponed'] and state['offline'] and all(state['target_checks'].values())
except Exception as exc:
    state['error']=str(exc)
finally:
    state['finished']=True; post()
'''

INSTALLED_PROBE = r'''
import json, os, pathlib, pwd, subprocess, urllib.request
P=pathlib.Path
def run(argv):
    return subprocess.run(argv,capture_output=True,text=True,timeout=20)
report=dict(phase='installed',uid=os.getuid(),user=pwd.getpwuid(os.getuid()).pw_name,
    live=P('/run/archiso').exists(),uefi=P('/sys/firmware/efi').exists(),
    debug_shell='systemd.debug_shell' in P('/proc/cmdline').read_text(),session={},status={})
report['cmdline']=P('/proc/cmdline').read_text().strip()
report['root_device']=run(['findmnt','-n','-o','SOURCE','/']).stdout.strip()
report['root_fstype']=run(['findmnt','-n','-o','FSTYPE','/']).stdout.strip()
devices=json.loads(run(['lsblk','--json','-o','PATH,TYPE']).stdout)
report['optical_media']=[device['path'] for device in devices['blockdevices'] if device['type']=='rom']
report['packages']=run(['pacman','-Qq']).stdout.splitlines()
report['os_release']=P('/etc/os-release').read_text()
for path in P('/proc').iterdir():
    if not path.name.isdigit(): continue
    try:
        if b'/usr/bin/husk-desktop' not in (path/'cmdline').read_bytes() or path.stat().st_uid!=os.getuid(): continue
        values=dict(item.split(b'=',1) for item in (path/'environ').read_bytes().split(b'\0') if b'=' in item)
        env=os.environ.copy()
        for key in ('DBUS_SESSION_BUS_ADDRESS','XDG_RUNTIME_DIR','WAYLAND_DISPLAY','GDK_BACKEND','XDG_SESSION_ID'):
            if key.encode() in values: env[key]=values[key.encode()].decode()
        status=subprocess.run(['husk-status'],env=env,capture_output=True,text=True,timeout=25)
        report['status_command']=dict(exit=status.returncode,stdout=status.stdout,stderr=status.stderr)
        try: report['status']=json.loads(status.stdout)
        except ValueError: pass
        report['desktop_pid']=int(path.name)
        identifier=env.get('XDG_SESSION_ID')
        if identifier:
            result=run(['loginctl','show-session',identifier,'-p','Type','-p','Name','-p','Remote','-p','State'])
            report['session']=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
        break
    except (OSError,ValueError): pass
try: report['session_log']=P.home().joinpath('.local/state/ownos/session.log').read_text(errors='replace')[-131072:]
except OSError: pass
data=json.dumps(report).encode()
urllib.request.urlopen(urllib.request.Request(CONFIG['base']+'/report',data=data,method='POST'),timeout=20).read()
'''


class Monitor:
    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(15); self.socket.connect(str(path))
        self.stream = self.socket.makefile('rwb', buffering=0)
        self.stream.readline(); self.command('qmp_capabilities')

    def command(self, name, arguments=None):
        self.stream.write((json.dumps(dict(execute=name, arguments=arguments or {}))+'\n').encode())
        while True:
            line = self.stream.readline()
            if not line: raise RuntimeError('QEMU closed its monitor')
            response = json.loads(line)
            if 'error' in response: raise RuntimeError(response['error'])
            if 'return' in response: return response['return']

    def key(self, keys):
        response = self.command('human-monitor-command', {'command-line':'sendkey '+keys+' 20'})
        if response.strip(): raise RuntimeError('QEMU keyboard input failed: '+response)
        time.sleep(0.04)

    def type_text(self, text):
        punctuation = {' ':'spc','-':'minus','/':'slash','.':'dot',':':'shift-semicolon',';':'semicolon'}
        for char in text:
            if char not in punctuation and not char.isascii() or not (char.isalnum() or char in punctuation):
                raise ValueError('Unsupported console character')
            self.key(punctuation.get(char, ('shift-'+char.lower()) if char.isupper() else char))

    def console(self, text):
        self.type_text(text); self.key('ret')

    def capture(self, path):
        from PIL import Image
        ppm = Path(path).with_suffix('.ppm')
        self.command('screendump', {'filename':str(ppm)})
        with Image.open(ppm) as image: image.save(path)
        ppm.unlink()

    def close(self):
        self.stream.close(); self.socket.close()


class Acceptance:
    def __init__(self, args):
        self.args = args
        self.artifacts = args.artifacts.resolve()
        self.artifacts.mkdir(parents=True, exist_ok=False)
        self.reports = {}; self.lock = threading.Lock()
        self.token = secrets.token_hex(16)
        self.password = 'V3Orbit7' + secrets.token_hex(12)
        self.kvm = os.access('/dev/kvm', os.R_OK | os.W_OK)
        self.process = None; self.monitor = None; self.qemu_log = None
        self.auth_started = False
        self.result = dict(installation='FAILED', installed_boot='NOT TESTED',
            live_shutdown='NOT TESTED', installed_shutdown='NOT TESTED', problems=[],
            polkit='NOT TESTED: test-only root debug shell delivered the input fixture',
            accelerator='kvm' if self.kvm else 'tcg', user=args.username)

    def handler(self):
        acceptance = self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                name = self.path.removeprefix('/'+acceptance.token+'/')
                if self.path != '/'+acceptance.token+'/'+name or name not in acceptance.resources:
                    self.send_error(404); return
                data = acceptance.resources[name]
                self.send_response(200); self.send_header('Content-Length',str(len(data)))
                self.end_headers(); self.wfile.write(data)
            def do_POST(self):
                try: size = int(self.headers.get('Content-Length','0'))
                except ValueError: size = 0
                if self.path != '/'+acceptance.token+'/report' or not 0 < size <= 5*1024*1024:
                    self.send_error(400); return
                try:
                    text = self.rfile.read(size).decode('utf-8')
                    data = redact_artifact_text(text, acceptance.password).encode()
                    value = json.loads(data)
                    phase = value.get('phase')
                    if phase not in ('installation','installed'): raise ValueError('Unknown phase')
                    with acceptance.lock:
                        acceptance.reports[phase] = value
                        temporary = acceptance.artifacts/(phase+'-latest.tmp')
                        temporary.write_bytes(data)
                        temporary.replace(acceptance.artifacts/(phase+'-guest.json'))
                except (ValueError,AttributeError): self.send_error(400); return
                self.send_response(204); self.end_headers()
            def log_message(self,*_): pass
        return Handler

    def latest(self, phase):
        with self.lock: return self.reports.get(phase)

    def start_vm(self, stage, disk, variables, label):
        command = make_qemu_command(stage, artifacts=self.artifacts, disk=disk, iso=self.args.iso,
            firmware_code=self.args.firmware_code, firmware_vars=variables, kernel=self.args.kernel,
            initrd=self.args.initrd, iso_label=label, kvm=self.kvm)
        (self.artifacts/(stage+'-qemu-command.json')).write_text(json.dumps(command,indent=2)+'\n')
        self.qemu_log = (self.artifacts/(stage+'-qemu.log')).open('wb')
        self.process = subprocess.Popen(command,stdout=self.qemu_log,stderr=subprocess.STDOUT)
        deadline = time.monotonic()+40
        while not (self.artifacts/(stage+'.sock')).exists():
            self.alive()
            if time.monotonic()>deadline: raise RuntimeError('QEMU monitor startup timed out')
            time.sleep(0.2)
        self.monitor = Monitor(self.artifacts/(stage+'.sock'))

    def alive(self):
        if self.process.poll() is not None:
            raise RuntimeError('QEMU exited before acceptance (an unexpected reboot also fails because -no-reboot is set)')

    def shutdown(self, stage):
        self.monitor.command('system_powerdown')
        try: code = self.process.wait(timeout=150)
        except subprocess.TimeoutExpired: raise RuntimeError(stage+' did not shut down after ACPI powerdown')
        self.result[stage+'_shutdown'] = 'PASSED' if code == 0 else 'FAILED'
        self.monitor.close(); self.monitor = None
        self.qemu_log.close(); self.qemu_log = None
        if code: raise RuntimeError(stage+' QEMU shutdown exited with '+str(code))

    def live_install(self):
        started=time.monotonic(); bootstrapped=False; last_event=None
        while time.monotonic()-started < self.args.timeout:
            self.alive()
            elapsed=time.monotonic()-started
            if not bootstrapped and elapsed >= (35 if self.kvm else 150):
                self.monitor.capture(self.artifacts/'live-before-installer.png')
                self.monitor.key('ctrl-alt-f9'); time.sleep(1)
                self.monitor.console('loadkeys us')
                self.monitor.console('curl -fsS --retry 20 --retry-delay 3 --retry-all-errors -o /tmp/husk-v3-setup.py '+
                    self.base+'/setup.py; python3 /tmp/husk-v3-setup.py')
                self.monitor.key('ctrl-alt-f1'); bootstrapped=True
            report=self.latest('installation')
            if report:
                events=report.get('events',[])
                event=events[-1].get('event') if events else 'setup'
                if event!=last_event:
                    print('Real installer checkpoint:',event,flush=True)
                    self.monitor.capture(self.artifacts/('install-'+re.sub('[^a-z0-9-]','-',event)+'.png'))
                    last_event=event
                if report.get('finished'):
                    problems=validate_install_report(report)
                    if problems: raise RuntimeError('; '.join(problems)+': '+report.get('error',''))
                    self.result['installation']='PASSED'
                    self.monitor.capture(self.artifacts/'installation-complete-restart-postponed.png')
                    return
            time.sleep(2)
        raise RuntimeError('The bounded real installation deadline expired without accepted evidence')

    def sddm_login(self):
        self.auth_started = True
        self.monitor.key('ctrl-alt-f1'); time.sleep(1)
        self.monitor.key('shift-tab'); self.monitor.key('ctrl-a')
        self.monitor.type_text(self.args.username); self.monitor.key('tab')
        self.monitor.type_text(self.password); self.monitor.key('ret')

    def installed_boot(self):
        started=time.monotonic(); login=False; console_login=False
        next_probe=65 if self.kvm else 210
        while time.monotonic()-started < self.args.boot_timeout:
            self.alive(); elapsed=time.monotonic()-started
            if not login and elapsed >= (40 if self.kvm else 180):
                self.monitor.capture(self.artifacts/'installed-sddm-greeter.png')
                self.sddm_login(); login=True
            if login and elapsed >= next_probe:
                self.monitor.key('ctrl-alt-f2'); time.sleep(1)
                if not console_login:
                    self.monitor.console(self.args.username); time.sleep(1)
                    self.monitor.console(self.password); time.sleep(2)
                    console_login=True
                self.monitor.console('curl -fsS -o /tmp/husk-v3-probe.py '+self.base+
                    '/installed.py; python3 /tmp/husk-v3-probe.py')
                self.monitor.key('ctrl-alt-f1'); next_probe=elapsed+45
            report=self.latest('installed')
            if report:
                problems=validate_installed_report(report,self.args.expected_version,self.args.username)
                self.result['installed_problems']=problems
                if not problems:
                    self.result['installed_boot']='PASSED'; self.result['installed_status']=report['status']
                    self.monitor.capture(self.artifacts/'installed-husk-desktop.png'); return
            time.sleep(2)
        raise RuntimeError('Installed UEFI/user/session acceptance expired: '+str(self.result.get('installed_problems',[])))

    def run(self):
        server = None
        try:
            for path in (self.args.iso,self.args.driver,self.args.kernel,self.args.initrd,
                         self.args.firmware_code,self.args.firmware_vars):
                if not path.is_file() or path.stat().st_size == 0: raise ValueError('Missing required test input: '+str(path))
            if not re.fullmatch('[a-z][a-z0-9]{2,16}',self.args.username) or self.args.username in ('live','root'):
                raise ValueError('The disposable test account name is invalid')
            iso=self.args.iso
            with iso.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
            self.result.update(iso=str(iso),iso_sha256=digest,iso_bytes=iso.stat().st_size,
                               expected_version=self.args.expected_version)
            label=subprocess.check_output(['blkid','-p','-s','LABEL','-o','value',str(iso)],text=True).strip()
            disk=create_disposable_disk(self.artifacts)
            variables=self.artifacts/'OVMF_VARS.fd'; shutil.copyfile(self.args.firmware_vars,variables)
            driver=self.args.driver.read_bytes()
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),self.handler())
            self.base='http://10.0.2.2:'+str(server.server_address[1])+'/'+self.token
            config=dict(base=self.base,user=self.args.username,password=self.password,
                        version=self.args.expected_version,timeout=self.args.timeout,
                        driver_sha256=hashlib.sha256(driver).hexdigest())
            self.resources={'setup.py':('CONFIG='+repr(config)+'\n'+GUEST_SETUP).encode(),
                            'installed.py':('CONFIG='+repr(dict(base=self.base))+'\n'+INSTALLED_PROBE).encode(),
                            'driver.so':driver}
            threading.Thread(target=server.serve_forever,daemon=True).start()
            self.start_vm('live',disk,variables,label); self.live_install(); self.shutdown('live')
            self.start_vm('installed',disk,variables,label); self.installed_boot(); self.shutdown('installed')
            info=subprocess.check_output(['qemu-img','info','--output=json',str(disk)],text=True)
            (self.artifacts/'installed-image-info.json').write_text(info)
        except Exception:
            self.result['problems'].append(traceback.format_exc())
            if self.monitor and self.process and self.process.poll() is None and not self.auth_started:
                try: self.monitor.capture(self.artifacts/'failure.png')
                except Exception: pass
        finally:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=15)
                except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
            if self.monitor: self.monitor.close()
            if self.qemu_log: self.qemu_log.close()
            if server: server.shutdown(); server.server_close()
            for path in [*self.artifacts.glob('*.log'),*self.artifacts.glob('*.json')]:
                text=path.read_text(errors='replace')
                path.write_text(redact_artifact_text(text,self.password))
            safe=redact_artifact_text(json.dumps(self.result,indent=2),self.password)
            (self.artifacts/'result.json').write_text(safe+'\n')
            print(safe,flush=True)
        return 0 if all(self.result[key]=='PASSED' for key in
            ('installation','installed_boot','live_shutdown','installed_shutdown')) else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso',type=Path,default=ROOT/'out/HuskOS-v3-phase2.iso')
    parser.add_argument('--driver',type=Path,default=ROOT/'out/v3-installer-driver.so')
    parser.add_argument('--kernel',type=Path,default=ROOT/'.build/v3-iso-boot/vmlinuz-linux')
    parser.add_argument('--initrd',type=Path,default=ROOT/'.build/v3-iso-boot/initramfs-linux.img')
    parser.add_argument('--artifacts',type=Path,default=ROOT/'out/install-v3')
    parser.add_argument('--firmware-code',type=Path,default=Path('/usr/share/OVMF/OVMF_CODE_4M.fd'))
    parser.add_argument('--firmware-vars',type=Path,default=Path('/usr/share/OVMF/OVMF_VARS_4M.fd'))
    parser.add_argument('--expected-version',default='v3-phase2')
    parser.add_argument('--username',default='huskcheck')
    parser.add_argument('--timeout',type=int,default=2700)
    parser.add_argument('--boot-timeout',type=int,default=600)
    args=parser.parse_args()
    if args.timeout<120 or args.boot_timeout<120: parser.error('VM deadlines must allow at least 120 seconds')
    for name in ('iso','driver','kernel','initrd','firmware_code','firmware_vars'):
        setattr(args,name,getattr(args,name).resolve())
    return Acceptance(args).run()


if __name__=='__main__':
    raise SystemExit(main())

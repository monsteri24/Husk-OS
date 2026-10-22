#!/usr/bin/env python3
"""Actual Live Steam GUI, cancellation, PAM/polkit and signed package transaction.

Only the existing guarded disposable-VM transport is shared with the installer
authorization test. The root console observes; it never installs a package,
changes a policy, supplies a PAM result or launches the privileged helper.
"""
import argparse
import importlib.util
import inspect
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('husk_live_auth', ROOT/'scripts/ci-test-v3-live-auth.py')
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)
vm = auth.vm
CLIENT_NAME = 'huskappcheck.py'
REQUIRED_CHECKS = ('initial_package_absent', 'initial_password_empty', 'live_session_active',
    'unprivileged_launcher', 'confirmation_cancel_unchanged', 'password_cancel_unchanged',
    'authorization_cancel_unchanged', 'retry_existing_password', 'root_helper', 'pkexec_caller',
    'no_test_injection', 'polkit_authenticated', 'full_upgrade', 'signatures_required',
    'package_installed', 'official_icon', 'gtk_verified', 'no_extra_terminal',
    'live_write_space', 'matching_graphics')


def authorized_application_audit(records, helper_pid):
    for record in records:
        if not isinstance(record, dict) or record.get('SYSLOG_IDENTIFIER') != 'pkexec':
            continue
        if str(record.get('_PID')) != str(helper_pid):
            continue
        message = record.get('MESSAGE')
        if not isinstance(message, str) or not message.startswith('live: Executing command '):
            continue
        if '[USER=root]' not in message:
            continue
        target = '/usr/lib/ownos/own-admin install-confirmed steam'
        if '[COMMAND='+target+']' in message or "[COMMAND='"+target+"']" in message:
            return True
    return False


def validate_application_report(report):
    problems = []
    if not isinstance(report, dict):
        return ['No actual application report']
    if report.get('finished') is not True or report.get('success') is not True:
        problems.append('The actual application observer did not finish successfully')
    checks = report.get('checks')
    for name in REQUIRED_CHECKS:
        if not isinstance(checks, dict) or checks.get(name) is not True:
            problems.append('Missing actual application check: '+name)
    if not isinstance(report.get('package'), str) or not report['package'].startswith('steam '):
        problems.append('Missing actual Steam package record')
    return problems


def steam_window(entry):
    return (isinstance(entry, dict) and
            entry.get('app_id', '').lower() in ('steam', 'steam.exe', 'steamwebhelper') and
            entry.get('title', '').strip().lower() != 'install steam')


def validate_steam_launch(report):
    if not isinstance(report, dict):
        return ['No Steam client observation']
    problems = []
    if not any(steam_window(entry) for entry in report.get('windows', [])):
        problems.append('No actual Steam client window was observed')
    if not any(isinstance(process, dict) and type(process.get('pid')) is int and process['pid'] > 0 and
               process.get('uid') == 1000 and process.get('elf') is True and
               process.get('executable', '').startswith('/home/live/.local/share/Steam/') and
               Path(process['executable']).name in ('steam', 'steamwebhelper')
               for process in report.get('processes', [])):
        problems.append('No unprivileged native Steam client process was observed')
    return problems


GTK_CLIENT = inspect.getsource(steam_window) + r'''
import json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,'/usr/lib/ownos')
from ownos.ui.app_install import AppInstallWindow, LivePasswordDialog
from ownos.ui.common import Gtk, GLib, ConfirmationDialog, launch_app
from ownos.bridge import PipeLineReader
directory=Path('/run/husk-v3-auth')
CONFIG=json.loads((directory/'client-config.json').read_text())
log=(directory/'client-output.log').open('a',buffering=1)
os.dup2(log.fileno(),1); os.dup2(log.fileno(),2)
window=AppInstallWindow('steam')
state=dict(pid=os.getpid(),uid=os.getuid(),phase='starting',password_dialogs=0,
           password_submitted=False,confirmations=[],windows=[])
started=time.monotonic(); last_control=None; seen_dialog=None; bridge=None; launch_at=None
def write():
    state.update(ui_state=window.state,status=window.status.get_text(),
        detail=window.explanation.get_text(),result_code=window.result_code)
    if window.state in ('failed','complete'):
        buffer=window.output.get_buffer()
        state['transaction_output']=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)[-80000:]
    temporary=directory/'client.tmp'; temporary.write_text(json.dumps(state)); temporary.replace(directory/'client.json')
def begin():
    state['begun']=True
    window.install_button.clicked()
    return False
def observe():
    global last_control,seen_dialog,bridge,launch_at
    try:
        control=(directory/'control').read_text().strip() if (directory/'control').exists() else ''
        if control and control!=last_control:
            last_control=control
            if control in ('confirm-cancel','password-cancel','authorization-cancel','install'):
                state['phase']=control; state['dialog']=None; state['begun']=False
                GLib.idle_add(begin)
            elif control=='launch':
                bridge_process=subprocess.Popen(['/usr/bin/own-toplevel'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
                bridge=PipeLineReader(bridge_process.stdout.fileno())
                process=launch_app('steam',window)
                state.update(phase='launching',launch_pid=process.pid if process else None)
                launch_at=time.monotonic()
        dialogs=[item for item in Gtk.Window.list_toplevels() if item is not window and item.get_mapped()]
        dialog=next((item for item in dialogs if isinstance(item,(ConfirmationDialog,LivePasswordDialog))),None)
        if dialog is not None:
            if isinstance(dialog,ConfirmationDialog):
                if seen_dialog is not dialog:
                    seen_dialog=dialog; state['confirmations'].append(state['phase'])
                    if state['phase']!='confirm-cancel': dialog.confirm_button.grab_focus()
                button=dialog.cancel_button if state['phase']=='confirm-cancel' else dialog.confirm_button
                state['dialog']='confirmation' if dialog.get_focus() is button else 'mapping'
            else:
                if seen_dialog is not dialog:
                    seen_dialog=dialog; state['password_dialogs']+=1
                    if state['phase']=='install': raise RuntimeError('Retry requested the Live password again')
                state['dialog']='password'
                if state['phase']=='authorization-cancel' and not state['password_submitted']:
                    if dialog.set_button.get_sensitive(): raise RuntimeError('Empty password accepted')
                    dialog.password.set_text(CONFIG['password']); dialog.repeat.set_text(CONFIG['password'])
                    if not dialog.set_button.get_sensitive(): raise RuntimeError('Valid matching password refused')
                    state['password_submitted']=True; dialog.set_button.clicked()
        else:
            state['dialog']=None
            if state.get('begun') and state['phase']=='confirm-cancel' and state['confirmations'] and window.state=='ready':
                state['phase']='confirmation-cancelled'
            elif state.get('begun') and state['phase']=='password-cancel' and window.state=='failed':
                state['phase']='password-cancelled'
            elif state.get('begun') and state['phase']=='authorization-cancel' and window.state=='failed':
                state['phase']='authorization-cancelled'
            elif state.get('begun') and state['phase']=='install' and window.state=='complete':
                state['phase']='installed'
            elif state.get('begun') and state['phase']=='install' and window.state=='failed':
                raise RuntimeError(window.status.get_text()+': '+window.explanation.get_text())
        if bridge:
            lines,eof=bridge.read_ready()
            for line in lines:
                value=json.loads(line)
                if value.get('event')=='upsert' and steam_window(value):
                    state['windows']=(state['windows']+[value])[-50:]
            state['launch_seconds']=round(time.monotonic()-launch_at)
        if time.monotonic()-started>CONFIG['timeout']: raise RuntimeError('Actual GTK application deadline expired')
        write()
    except Exception as exc:
        state['error']=type(exc).__name__+': '+str(exc); write()
    return True
window.connect('destroy',lambda *_:Gtk.main_quit())
GLib.timeout_add(100,observe)
Gtk.main()
'''

# Share only the strict audit parser with the delivered read-only observer.
ROOT_OBSERVER = inspect.getsource(authorized_application_audit) + r'''
import hashlib, json, os, shlex, subprocess, time, urllib.request
from pathlib import Path as P
state=dict(phase='installation',stage='starting',finished=False,success=False,checks={})
def command(argv,check=True):
    return subprocess.run(argv,check=check,capture_output=True,text=True,timeout=20).stdout
def post():
    data=json.dumps(state).encode()
    request=urllib.request.Request(CONFIG['base']+'/report',data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=10) as response: response.read()
def environment(pid):
    return dict(item.split('=',1) for item in (P('/proc')/str(pid)/'environ').read_bytes().decode().split('\0') if '=' in item)
def processes(needle,uid=None):
    for path in P('/proc').iterdir():
        if not path.name.isdecimal(): continue
        try:
            if uid is not None and path.stat().st_uid!=uid: continue
            if needle in (path/'cmdline').read_bytes().split(b'\0'): yield int(path.name)
        except OSError: pass
def password_state():
    fields=command(['/usr/bin/passwd','-S','live']).split()
    return fields[1] if len(fields)==7 and fields[0]=='live' else ''
def journal():
    raw=command(['/usr/bin/journalctl','-b','--no-pager','-o','json','-t','polkitd','-t','pkexec','-t','polkit-agent-helper-1'])
    return [{key:entry.get(key) for key in ('SYSLOG_IDENTIFIER','_PID','MESSAGE')}
        for entry in (json.loads(line) for line in raw.splitlines() if line.strip())][-100:]
def package_snapshot():
    # Full hashes of local/sync package DB files and pacman log, not just -Q steam.
    digest=hashlib.sha256()
    for directory in (P('/var/lib/pacman/local'),P('/var/lib/pacman/sync')):
        for path in sorted(directory.rglob('*')):
            if path.is_file(): digest.update(str(path).encode()); digest.update(path.read_bytes())
    log=P('/var/log/pacman.log')
    if log.exists(): digest.update(log.read_bytes())
    return digest.hexdigest()
def acknowledge(value):
    temporary=directory/'control.tmp'; temporary.write_text(value)
    os.chown(temporary,uid,uid); temporary.chmod(0o600)
    temporary.replace(directory/'control')
def native_steam_processes():
    result=[]
    for process in P('/proc').iterdir():
        if not process.name.isdecimal(): continue
        try:
            if process.stat().st_uid!=uid: continue
            executable=(process/'exe').resolve(strict=True)
            if P('/home/live/.local/share/Steam') not in executable.parents or executable.name not in ('steam','steamwebhelper'): continue
            with executable.open('rb') as stream: elf=stream.read(4)==b'\x7fELF'
            if elf: result.append(dict(pid=int(process.name),uid=uid,executable=str(executable),elf=True))
        except OSError: pass
    return result
try:
    if os.getuid()!=0 or not P('/run/archiso').is_dir() or not P('/sys/firmware/efi').is_dir():
        raise RuntimeError('A disposable UEFI Live VM is required')
    if P('/sys/class/block/vda/serial').read_text().strip()!='HUSK-DISPOSABLE':
        raise RuntimeError('Attached disk is not the new disposable image')
    checks=state['checks']; initial=package_snapshot()
    cow=os.statvfs('/run/archiso/cowspace')
    state['live_write_space']=dict(total_bytes=cow.f_blocks*cow.f_frsize,available_bytes=cow.f_bavail*cow.f_frsize,
        mount=command(['/usr/bin/findmnt','-n','-o','FSTYPE,SIZE,AVAIL','/run/archiso/cowspace']).strip())
    checks['live_write_space']=('cow_spacesize=50%' in P('/proc/cmdline').read_text().split() and
        state['live_write_space']['total_bytes']>1024**3)
    before_packages=set(command(['/usr/bin/pacman','-Qq']).splitlines())
    if not {'vulkan-radeon','vulkan-intel'}<=before_packages or {'nvidia-utils','lib32-nvidia-utils'}&before_packages:
        raise RuntimeError('The clean Live graphics inventory is not the expected Mesa stack')
    checks['initial_package_absent']=subprocess.run(['/usr/bin/pacman','-Q','steam'],capture_output=True).returncode!=0
    checks['initial_password_empty']=password_state()=='NP'
    if not checks['initial_package_absent'] or not checks['initial_password_empty']:
        raise RuntimeError('The disposable Live session must start with no Steam and no password')
    deadline=time.monotonic()+CONFIG['timeout']; desktop=None
    while time.monotonic()<deadline:
        desktop=next(processes(b'/usr/bin/husk-desktop'),None)
        if desktop is not None: break
        post(); time.sleep(1)
    if desktop is None: raise RuntimeError('Actual Live desktop did not start')
    uid=(P('/proc')/str(desktop)).stat().st_uid; env=environment(desktop)
    details=command(['/usr/bin/loginctl','show-session',env.get('XDG_SESSION_ID',''),'-p','Name','-p','Active','-p','Remote'])
    state['live_session']=details.splitlines()
    checks['live_session_active']={'Name=live','Active=yes','Remote=no'}<=set(details.splitlines())
    directory=P('/run/husk-v3-auth'); directory.mkdir(mode=0o700); os.chown(directory,uid,uid)
    client=directory/'client.py'; urllib.request.urlretrieve(CONFIG['base']+'/client.py',client)
    if hashlib.sha256(client.read_bytes()).hexdigest()!=CONFIG['client_sha256']: raise RuntimeError('Wrong GTK fixture digest')
    client.chmod(0o644)
    home=P('/home/live')/CONFIG['client_name']
    if home.exists() or home.is_symlink(): raise RuntimeError('Refusing to replace a Live home file')
    home.symlink_to(client)
    config=directory/'client-config.json'; config.write_text(json.dumps(dict(password=CONFIG['password'],timeout=CONFIG['timeout'])))
    os.chown(config,uid,uid); config.chmod(0o600)
    state['stage']='terminal-needed'; post()
    while time.monotonic()<deadline and not (list(processes(b'foot',uid))+list(processes(b'/usr/bin/foot',uid))): time.sleep(1)
    state['stage']='terminal-ready'; post()
    probe=directory/'client.json'; control_sent=False; baseline_terminals=None; installed_since=None
    while time.monotonic()<deadline:
        if not probe.exists(): post(); time.sleep(1); continue
        info=json.loads(probe.read_text()); state['gtk']=info
        if info.get('error'): raise RuntimeError('Actual GTK application: '+info['error'])
        pid=info.get('pid')
        checks['unprivileged_launcher']=type(pid) is int and uid!=0 and (P('/proc')/str(pid)).stat().st_uid==uid
        terminals=sorted(set(processes(b'foot',uid))|set(processes(b'/usr/bin/foot',uid)))
        if baseline_terminals is None: baseline_terminals=terminals
        checks['no_extra_terminal']=terminals==baseline_terminals and len(terminals)==1
        if not control_sent: acknowledge('confirm-cancel'); control_sent=True
        phase=info.get('phase'); state['stage']=phase
        if info.get('dialog')=='confirmation': state['stage']=phase+'-confirmation'
        elif info.get('dialog')=='password': state['stage']=phase+'-password'
        if phase=='confirmation-cancelled' and not checks.get('confirmation_cancel_unchanged'):
            checks['confirmation_cancel_unchanged']=password_state()=='NP' and package_snapshot()==initial
            if not checks['confirmation_cancel_unchanged']: raise RuntimeError('Confirmation Cancel changed packages/password')
            acknowledge('password-cancel')
        elif phase=='password-cancelled' and not checks.get('password_cancel_unchanged'):
            checks['password_cancel_unchanged']=password_state()=='NP' and package_snapshot()==initial
            if not checks['password_cancel_unchanged']: raise RuntimeError('Password Cancel changed packages/password')
            acknowledge('authorization-cancel')
        elif phase=='authorization-cancelled' and not checks.get('authorization_cancel_unchanged'):
            checks['authorization_cancel_unchanged']=(password_state()=='P' and package_snapshot()==initial and
                info.get('ui_state')=='failed' and 'Authorization was cancelled' in info.get('status',''))
            if not checks['authorization_cancel_unchanged']: raise RuntimeError('Authorization Cancel changed packages or showed wrong status')
            acknowledge('install')
        if info.get('ui_state')=='installing' and phase in ('authorization-cancel','install'):
            state['stage']=phase+'-authorization'
        for helper in processes(b'/usr/lib/ownos/own-admin',0):
            try:
                args=(P('/proc')/str(helper)/'cmdline').read_bytes().split(b'\0')
                if b'install-confirmed' not in args or b'steam' not in args: continue
                privileged=environment(helper)
            except OSError: continue
            if privileged.get('PKEXEC_UID')!=str(uid): continue
            state['helper_pid']=helper
            checks['root_helper']=True
            checks['pkexec_caller']=privileged.get('PKEXEC_UID')==str(uid)
            checks['no_test_injection']=not any(key in privileged for key in ('LD_PRELOAD','HUSK_INSTALL_ACCEPTANCE'))
        if phase in ('install','installed','launching'):
            state['polkit_journal']=journal()
            checks['polkit_authenticated']=authorized_application_audit(state['polkit_journal'],state.get('helper_pid'))
        if phase=='installed' and installed_since is None:
            checks['retry_existing_password']=info.get('password_dialogs')==2 and info.get('password_submitted') is True
            result=subprocess.run(['/usr/bin/pacman','-Q','steam'],capture_output=True,text=True)
            state['package']=result.stdout.strip(); checks['package_installed']=result.returncode==0
            output=info.get('transaction_output','')
            prefix='Husk OS: verified full-system transaction: '
            commands=[shlex.split(line[len(prefix):]) for line in output.splitlines() if line.startswith(prefix)]
            checks['full_upgrade']=(commands==[['/usr/bin/pacman','-Syu','--needed','steam',
                'lib32-vulkan-radeon','lib32-vulkan-intel','--noconfirm']] and
                'OWNOS-STAGE:preflight' in output and ':: Starting full system upgrade' in output)
            final_packages=set(command(['/usr/bin/pacman','-Qq']).splitlines())
            checks['matching_graphics']=({'lib32-vulkan-radeon','lib32-vulkan-intel'}<=final_packages and
                not {'nvidia-utils','lib32-nvidia-utils'}&final_packages and 'providers available for lib32-vulkan-driver' not in output)
            state['graphics_packages']=sorted(name for name in final_packages if name.startswith(('vulkan-','lib32-vulkan-','nvidia','lib32-nvidia')))
            state['siglevel']=command(['/usr/bin/pacman-conf','SigLevel']).splitlines()
            checks['signatures_required']={'PackageRequired','PackageTrustedOnly'}<=set(state['siglevel'])
            icon=P('/usr/share/applications/steam.desktop')
            checks['official_icon']=icon.is_file() and 'Icon=steam' in icon.read_text() and subprocess.run(
                ['/usr/bin/pacman','-Qqo',str(icon)],capture_output=True,text=True).stdout.strip()=='steam'
            checks['gtk_verified']=info.get('ui_state')=='complete' and info.get('result_code')==0 and 'installed (verified)' in info.get('status','')
            if not all(checks.get(name) is True for name in CONFIG['required']):
                raise RuntimeError('The actual graphical installation did not satisfy all acceptance checks')
            state['stage']='installed-verified'; post(); installed_since=time.monotonic()
        if installed_since is not None:
            if phase=='installed': state['stage']='installed-verified'
            try:
                acknowledged=urllib.request.urlopen(CONFIG['base']+'/launch',timeout=3).read()==b'LAUNCH\n'
            except Exception: acknowledged=False
            if acknowledged and phase=='installed': acknowledge('launch')
            if phase=='launching':
                state['steam_launch']=dict(windows=info.get('windows',[]),wrapper_pid=info.get('launch_pid'),
                    processes=native_steam_processes(),
                    scope='Client startup only; no login-readiness, Steam account, downloaded game or GPU acceleration claim')
            if phase=='launching' and (info.get('launch_seconds',0)>=240 or
                    info.get('launch_seconds',0)>=60 and state['steam_launch']['windows'] and state['steam_launch']['processes']):
                log=directory/'client-output.log'
                if log.exists(): state['client_output']=log.read_text(errors='replace')[-64000:]
                state.update(stage='launch-observed',finished=True,success=True); post(); break
        post(); time.sleep(1)
    if not state['success']: raise RuntimeError('Bounded application acceptance deadline expired')
    while time.monotonic()<deadline:
        try:
            if urllib.request.urlopen(CONFIG['base']+'/cleanup',timeout=3).read()==b'CLEANUP\n':
                state['cleanup_completed']=True; break
        except Exception: pass
        time.sleep(1)
except Exception as exc:
    state.update(error=type(exc).__name__+': '+str(exc),success=False)
finally:
    try:
        state['polkit_journal']=journal()
        state['pacman_log_tail']=P('/var/log/pacman.log').read_text(errors='replace')[-40000:]
    except Exception: pass
    state['finished']=True; post()
'''


class ApplicationAcceptance(auth.AuthorizationAcceptance):
    client_source = GTK_CLIENT
    observer_source = ROOT_OBSERVER
    required_checks = REQUIRED_CHECKS
    client_name = CLIENT_NAME
    proof_scope = 'Actual Live graphical Steam cancellation, PAM/polkit and signed full-system transaction'

    def run(self):
        result = super().run()
        return result or (0 if self.result.get('client_startup') == 'PASSED' else 1)

    def live_authorization(self):
        started=time.monotonic(); next_ready=15; delivered=False; terminal=False; launched=False
        handled=set(); pending_since={}; last_stage=None; captured=False
        while time.monotonic()-started<self.args.timeout:
            self.alive(); elapsed=time.monotonic()-started; output=self.serial.read()
            if not delivered:
                if self.ready_marker in output:
                    self.serial.sendline('umask 077; curl -fsS --max-time 30 -o /tmp/husk-app-observer.py '+
                        self.base+'/setup.py && python3 /tmp/husk-app-observer.py')
                    delivered=True
                elif elapsed>=next_ready:
                    self.serial.interrupt()
                    self.serial.sendline('[ "$(id -u)" = 0 ] && curl -fsS --max-time 10 '+self.base+'/ready')
                    next_ready=elapsed+20
            report=self.latest('installation')
            if report:
                stage=report.get('stage')
                if stage!=last_stage:
                    print('Live application checkpoint:',stage,flush=True); last_stage=stage
                if stage=='terminal-needed' and not terminal:
                    self.monitor.key('meta_l-ret'); terminal=True
                if stage=='terminal-ready' and not launched:
                    self.monitor.console('python3 '+CLIENT_NAME); launched=True
                if stage and stage not in handled and (stage.endswith('-confirmation') or
                        stage=='password-cancel-password' or stage in ('authorization-cancel-authorization','install-authorization')):
                    pending_since.setdefault(stage,time.monotonic())
                    if time.monotonic()-pending_since[stage]>=3:
                        if stage in ('confirm-cancel-confirmation','password-cancel-password','authorization-cancel-authorization'):
                            self.monitor.key('esc')
                        elif stage=='install-authorization':
                            self.monitor.capture(self.artifacts/'package-authorization-before-password.png')
                            self.auth_started=True
                            self.monitor.type_text(self.password); self.monitor.key('ret')
                        else:
                            # The next real GTK password dialog may fill its
                            # private fields before the next host observation.
                            if stage=='authorization-cancel-confirmation': self.auth_started=True
                            self.monitor.key('ret')
                        handled.add(stage)
                if stage=='installed-verified' and 'launch' not in self.resources:
                    self.monitor.capture(self.artifacts/'steam-installation-verified.png')
                    self.resources['launch']=b'LAUNCH\n'
                if report.get('finished'):
                    problems=validate_application_report(report)
                    if problems: raise RuntimeError('; '.join(problems)+': '+report.get('error',''))
                    if not captured:
                        self.monitor.capture(self.artifacts/'steam-client-startup.png')
                        self.result['target_blockstats']=vm.cancellation_blockstats(self.monitor.command('query-blockstats'))
                        self.result['steam_launch']=report.get('steam_launch',{})
                        launch_problems=validate_steam_launch(self.result['steam_launch'])
                        self.result['client_startup']='FAILED' if launch_problems else 'PASSED'
                        self.result['problems'].extend(launch_problems)
                        self.resources['cleanup']=b'CLEANUP\n'; captured=True
                    if report.get('cleanup_completed') is True:
                        self.result['authorization']='PASSED'
                        self.result['package_installation']='PASSED'; return
            time.sleep(1)
        raise RuntimeError('Bounded Live application deadline expired at '+str(last_stage))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name,default in [('iso','out/HuskOS-v3-phase2.iso'),('kernel','.build/v3-iso-boot/vmlinuz-linux'),
                         ('initrd','.build/v3-iso-boot/initramfs-linux.img'),('artifacts','out/live-app-v3'),
                         ('firmware-code','/usr/share/OVMF/OVMF_CODE_4M.fd'),('firmware-vars','/usr/share/OVMF/OVMF_VARS_4M.fd')]:
        parser.add_argument('--'+name,type=Path,default=Path(default))
    parser.add_argument('--timeout',type=int,default=1500)
    args=parser.parse_args(); args.username='live'; args.expected_version='v3-phase2'
    if not 300<=args.timeout<=2400: parser.error('Bounded Live application timeout must be 300–2400 seconds')
    for name in ('iso','kernel','initrd','firmware_code','firmware_vars'): setattr(args,name,getattr(args,name).resolve())
    return ApplicationAcceptance(args).run()


if __name__=='__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Test actual Live GTK/password/polkit startup without modifying its helpers.

A root debug console delivers test files and observes processes/journald only.
The real active Live session launches the GTK client through its terminal.
GTK widget input sets the temporary password; QMP keyboard input authenticates
the actual system dialog. No root helper, PAM rule or executable is replaced.
This smoke test never authorizes disk changes or performs an installation.
"""
import argparse
import hashlib
import http.server
import importlib.util
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
CLIENT_NAME = 'huskauthcheck.py'
spec = importlib.util.spec_from_file_location('husk_install_vm', ROOT/'scripts/ci-test-v3-install.py')
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)
REQUIRED_CHECKS = ('initial_password_empty', 'live_session_active', 'unprivileged_launcher',
                   'password_was_set', 'polkit_authenticated', 'pkexec_caller', 'root_calamares',
                   'no_test_injection', 'private_xauthority', 'qt_english')


def validate_authorization_report(report):
    problems = []
    if report.get('finished') is not True or report.get('success') is not True:
        problems.append('The authorization observer did not finish successfully')
    checks = report.get('checks')
    for name in REQUIRED_CHECKS:
        if not isinstance(checks, dict) or checks.get(name) is not True:
            problems.append('Missing or failed actual authorization check: ' + name)
    return problems


GTK_CLIENT = r'''
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, '/usr/lib/ownos')
from ownos.ui.installer import InstallerLauncher
from ownos.ui.app_install import LivePasswordDialog
from ownos.ui.common import Gtk, GLib
CONFIG=json.loads(Path('/run/husk-v3-auth/client-config.json').read_text())
probe=Path('/run/husk-v3-auth/client.json')
window=InstallerLauncher()
state=dict(pid=os.getpid(),uid=os.getuid(),attempted=False,password_submitted=False)
started=time.monotonic()
def write():
    state.update(status=window.status.get_text(),busy=window.busy,
                 helper_pid=window.process.pid if window.process else None)
    temporary=probe.with_suffix('.tmp'); temporary.write_text(json.dumps(state)); temporary.replace(probe)
def begin():
    state['attempted']=True
    window.open.clicked()  # Actual GTK signal and unchanged production handler.
    return False
def observe():
    try:
        for dialog in Gtk.Window.list_toplevels():
            if isinstance(dialog,LivePasswordDialog) and not state['password_submitted']:
                if dialog.set_button.get_sensitive(): raise RuntimeError('Empty password was accepted')
                dialog.password.set_text(CONFIG['password'])
                dialog.repeat.set_text(CONFIG['password'])
                if not dialog.set_button.get_sensitive(): raise RuntimeError('Matching valid password was refused')
                state['password_submitted']=True
                dialog.set_button.clicked()
                # Let Dialog.run return before checking the launcher's busy state.
                write(); return True
        if state['attempted'] and not window.busy and state['password_submitted']:
            state['error']=window.status.get_text() or 'Launcher returned before authorization'
        if time.monotonic()-started>CONFIG['timeout']: state['error']='GTK launcher deadline expired'
        write()
    except Exception as exc:
        state['error']=type(exc).__name__+': '+str(exc); write()
    return True
window.connect('destroy',lambda *_:Gtk.main_quit())
GLib.timeout_add(100,observe)
GLib.idle_add(begin)
Gtk.main()
'''

ROOT_OBSERVER = r'''
import hashlib, json, os, signal, stat, subprocess, time, urllib.request
from pathlib import Path as P
state=dict(phase='installation',stage='starting',finished=False,success=False,checks={})
def command(argv):
    return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=15).stdout
def authorization_journal():
    # pkexec/agent audit messages belong to the caller's session, not necessarily
    # polkit.service. Collect their identifiers and keep the trusted journal PID.
    raw=command(['/usr/bin/journalctl','-b','--no-pager','-o','json',
        '-t','polkitd','-t','pkexec','-t','polkit-agent-helper-1'])
    records=[]
    for line in raw.splitlines():
        if not line.strip(): continue
        entry=json.loads(line)
        records.append({key:entry.get(key) for key in ('SYSLOG_IDENTIFIER','_PID','MESSAGE')})
    return records[-100:]
def authorized_exec_audit(records,helper_pid):
    for record in records:
        if not isinstance(record,dict) or record.get('SYSLOG_IDENTIFIER')!='pkexec': continue
        if str(record.get('_PID'))!=str(helper_pid): continue
        message=record.get('MESSAGE')
        if not isinstance(message,str) or not message.startswith('live: Executing command '): continue
        if '[USER=root]' not in message: continue
        if any(target in message for target in (
                '[COMMAND=/usr/lib/ownos/husk-installer-root]',
                "[COMMAND='/usr/lib/ownos/husk-installer-root']")):
            return True
    return False
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
try:
    if os.getuid()!=0 or not P('/run/archiso').is_dir() or not P('/sys/firmware/efi').is_dir():
        raise RuntimeError('The observer requires a disposable UEFI Live VM')
    if P('/sys/class/block/vda/serial').read_text().strip()!='HUSK-DISPOSABLE':
        raise RuntimeError('The attached disk is not the new disposable target')
    checks=state['checks']; state['initial_password_state']=password_state()
    checks['initial_password_empty']=state['initial_password_state']=='NP'
    deadline=time.monotonic()+CONFIG['timeout']; desktop=None
    while time.monotonic()<deadline:
        desktop=next(processes(b'/usr/bin/husk-desktop'),None)
        if desktop is not None: break
        post(); time.sleep(1)
    if desktop is None: raise RuntimeError('The real Live desktop did not start')
    uid=(P('/proc')/str(desktop)).stat().st_uid; env=environment(desktop)
    session=env.get('XDG_SESSION_ID','')
    details=command(['/usr/bin/loginctl','show-session',session,'-p','Name','-p','Active','-p','Remote'])
    state['live_session']=details.splitlines()
    checks['live_session_active']={'Name=live','Active=yes','Remote=no'}<=set(details.splitlines())
    directory=P('/run/husk-v3-auth'); directory.mkdir(mode=0o700); os.chown(directory,uid,uid)
    client=directory/'client.py'; urllib.request.urlretrieve(CONFIG['base']+'/client.py',client)
    if hashlib.sha256(client.read_bytes()).hexdigest()!=CONFIG['client_sha256']:
        raise RuntimeError('The GTK fixture digest did not match')
    client.chmod(0o644)
    # The shipped Live layout is Finnish. A plain home filename avoids typing
    # slash/minus keys with a US physical-key map; do not change the user's layout.
    home_client=P('/home/live')/CONFIG['client_name']
    if home_client.exists() or home_client.is_symlink():
        raise RuntimeError('Refusing to replace an existing Live home test file')
    home_client.symlink_to(client)
    config=directory/'client-config.json'; config.write_text(json.dumps(dict(password=CONFIG['password'],timeout=CONFIG['timeout'])))
    os.chown(config,uid,uid); config.chmod(0o600)
    state['stage']='terminal-needed'; post()
    while time.monotonic()<deadline and not list(processes(b'foot',uid)) and not list(processes(b'/usr/bin/foot',uid)):
        time.sleep(1)
    if time.monotonic()>=deadline: raise RuntimeError('The active session terminal did not start')
    state['stage']='terminal-ready'; post()
    probe=directory/'client.json'; calamares_since=None; target_pid=None; journal_at=0
    client_deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        if not probe.is_file() and time.monotonic()>client_deadline:
            raise RuntimeError('The GTK client did not report after terminal launch; inspect the terminal screenshot')
        if probe.is_file():
            info=json.loads(probe.read_text()); state['gtk']=info
            if info.get('error'): raise RuntimeError('Actual GTK launcher: '+info['error'])
            pid=info.get('pid'); helper=info.get('helper_pid')
            if type(pid) is int:
                checks['unprivileged_launcher']=(P('/proc')/str(pid)).stat().st_uid==uid and uid!=0
            state['final_password_state']=password_state()
            checks['password_was_set']=info.get('password_submitted') is True and state['final_password_state']=='P'
            if type(helper) is int:
                process=P('/proc')/str(helper)
                argv=(process/'cmdline').read_bytes().split(b'\0')
                if b'/usr/bin/calamares' in argv and process.stat().st_uid==0:
                    target_pid=helper; qt=environment(helper)
                    state['qt_environment']={key:qt.get(key) for key in ('LANG','LC_ALL','QT_QPA_PLATFORM',
                        'QT_STYLE_OVERRIDE','QT_QUICK_CONTROLS_STYLE')}
                    checks['root_calamares']=True
                    state['pkexec_uid']=qt.get('PKEXEC_UID')
                    checks['pkexec_caller']=qt.get('PKEXEC_UID')==str(uid)
                    checks['no_test_injection']=not any(key in qt for key in ('LD_PRELOAD','HUSK_INSTALL_ACCEPTANCE'))
                    authority=P(qt.get('XAUTHORITY','/missing'))
                    checks['private_xauthority']=(authority.is_file() and not authority.is_symlink() and
                        authority.stat().st_uid==uid and stat.S_IMODE(authority.stat().st_mode)==0o600 and
                        authority.parent.stat().st_uid==uid and stat.S_IMODE(authority.parent.stat().st_mode)==0o700)
                    checks['qt_english']=all(qt.get(key)==value for key,value in {
                        'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','QT_QPA_PLATFORM':'xcb',
                        'QT_STYLE_OVERRIDE':'Fusion','QT_QUICK_CONTROLS_STYLE':'Basic'}.items())
                    journal=authorization_journal()
                    state['polkit_journal']=journal
                    checks['polkit_authenticated']=authorized_exec_audit(journal,helper)
                    if calamares_since is None: calamares_since=time.monotonic()
                    state['stage']='calamares-starting'
                    if time.monotonic()-calamares_since>=8:
                        if not all(checks.get(name) is True for name in CONFIG['required']):
                            raise RuntimeError('The actual root Calamares process did not satisfy all authorization checks')
                        state.update(stage='calamares-ready',finished=True,success=True); post(); break
                else:
                    state['stage']='authorization-pending'
                    if time.monotonic()-journal_at>=10:
                        state['polkit_journal']=authorization_journal()
                        journal_at=time.monotonic()
        post(); time.sleep(1)
    if not state['success']: raise RuntimeError('Normal Live authorization deadline expired')
    # The host first captures the verified GUI and independently checks zero writes.
    while time.monotonic()<deadline:
        try:
            if urllib.request.urlopen(CONFIG['base']+'/cleanup',timeout=5).read()==b'CLEANUP\n': break
        except Exception: pass
        time.sleep(1)
    else: raise RuntimeError('The host did not acknowledge the authorization evidence')
    process=P('/proc')/str(target_pid)
    if process.stat().st_uid!=0 or b'/usr/bin/calamares' not in (process/'cmdline').read_bytes().split(b'\0'):
        raise RuntimeError('Refusing to terminate a different process during test cleanup')
    os.kill(target_pid,signal.SIGTERM)
    state['cleanup_completed']=True
except Exception as exc:
    state.update(error=type(exc).__name__+': '+str(exc),success=False)
finally:
    # Keep the actual startup/authentication diagnostics even if Qt exits before
    # a process observation. No password or Xauthority contents are collected.
    try:
        state['polkit_journal']=authorization_journal()
        log=P('/root/.cache/calamares/session.log')
        if log.is_file(): state['calamares_log']=log.read_text(errors='replace')[-64000:]
    except (OSError,subprocess.SubprocessError): pass
    state['finished']=True; post()
'''


class AuthorizationAcceptance(vm.Acceptance):
    def live_authorization(self):
        started=time.monotonic(); next_ready=15; delivered=False
        terminal=False; launched=False; prompt_since=None; authenticated=False; captured=False; last_stage=None
        while time.monotonic()-started<self.args.timeout:
            self.alive(); elapsed=time.monotonic()-started
            output=self.serial.read()
            if not delivered:
                if self.ready_marker in output:
                    self.serial.sendline('umask 077; curl -fsS --max-time 30 -o /tmp/husk-auth-observer.py '+
                        self.base+'/setup.py && python3 /tmp/husk-auth-observer.py')
                    delivered=True
                elif elapsed>=next_ready:
                    self.serial.interrupt()
                    self.serial.sendline('[ "$(id -u)" = 0 ] && curl -fsS --max-time 10 '+self.base+'/ready')
                    next_ready=elapsed+20
            report=self.latest('installation')
            if report:
                stage=report.get('stage')
                if stage!=last_stage:
                    print('Live authorization checkpoint:',stage,flush=True); last_stage=stage
                if stage=='terminal-needed' and not terminal:
                    self.monitor.key('meta_l-ret'); terminal=True
                if stage=='terminal-ready' and not launched:
                    self.monitor.console('python3 '+CLIENT_NAME); launched=True
                if stage=='authorization-pending' and not authenticated:
                    if prompt_since is None: prompt_since=time.monotonic()
                    if time.monotonic()-prompt_since>=4:
                        self.monitor.capture(self.artifacts/'system-authorization-before-password.png')
                        self.auth_started=True
                        self.monitor.type_text(self.password); self.monitor.key('ret'); authenticated=True
                if report.get('finished'):
                    problems=validate_authorization_report(report)
                    if problems: raise RuntimeError('; '.join(problems)+': '+report.get('error',''))
                    if not captured:
                        self.monitor.capture(self.artifacts/'authorized-calamares-welcome.png')
                        self.result['target_blockstats']=vm.cancellation_blockstats(self.monitor.command('query-blockstats'))
                        self.resources['cleanup']=b'CLEANUP\n'; captured=True
                    if report.get('cleanup_completed') is True:
                        self.result['authorization']='PASSED'; return
            time.sleep(1)
        last=self.latest('installation') or {}
        raise RuntimeError('The bounded Live authorization deadline expired at stage '+str(last.get('stage'))+
                           '; checks='+json.dumps(last.get('checks',{}),sort_keys=True))

    def run(self):
        self.result=dict(authorization='FAILED',live_shutdown='NOT TESTED',problems=[],
            accelerator='kvm' if self.kvm else 'tcg',proof_scope='Real Live GTK/password/polkit launch; no installation')
        server=None
        try:
            for path in (self.args.iso,self.args.kernel,self.args.initrd,self.args.firmware_code,self.args.firmware_vars):
                if not path.is_file() or path.stat().st_size==0: raise ValueError('Missing test input: '+str(path))
            with self.args.iso.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
            self.result.update(iso_sha256=digest,iso_bytes=self.args.iso.stat().st_size)
            disk=vm.create_disposable_disk(self.artifacts)
            variables=self.artifacts/'OVMF_VARS.fd'; shutil.copyfile(self.args.firmware_vars,variables)
            label=subprocess.check_output(['blkid','-p','-s','LABEL','-o','value',str(self.args.iso)],text=True).strip()
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),self.handler())
            self.base='http://10.0.2.2:'+str(server.server_address[1])+'/'+self.token
            self.ready_marker=('HUSK-AUTH-READY-'+secrets.token_hex(16)).encode()
            client=GTK_CLIENT.encode()
            # Let the observer report its failure/logs before the host deadline.
            config=dict(base=self.base,password=self.password,timeout=self.args.timeout-60,
                        client_sha256=hashlib.sha256(client).hexdigest(),client_name=CLIENT_NAME,required=REQUIRED_CHECKS)
            self.resources={'ready':self.ready_marker+b'\n','client.py':client,
                            'setup.py':('CONFIG='+repr(config)+'\n'+ROOT_OBSERVER).encode()}
            threading.Thread(target=server.serve_forever,daemon=True).start()
            self.start_vm('live',disk,variables,label)
            self.live_authorization(); self.shutdown('live')
        except Exception:
            self.result['problems'].append(traceback.format_exc())
            if self.monitor and self.process and self.process.poll() is None and not self.auth_started:
                self.monitor.capture(self.artifacts/'failure-before-authentication.png')
        finally:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=15)
                except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
            if self.monitor: self.monitor.close()
            if self.serial: self.serial.close()
            if self.qemu_log: self.qemu_log.close()
            if server: server.shutdown(); server.server_close()
            for path in [*self.artifacts.glob('*.json'),*self.artifacts.glob('*.log')]:
                path.write_text(vm.redact_artifact_text(path.read_text(errors='replace'),self.password))
            safe=vm.redact_artifact_text(json.dumps(self.result,indent=2),self.password)
            (self.artifacts/'result.json').write_text(safe+'\n'); print(safe,flush=True)
        return 0 if self.result['authorization']=='PASSED' and self.result['live_shutdown']=='PASSED' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name,default in [('iso','out/HuskOS-v3-phase2.iso'),('kernel','.build/v3-iso-boot/vmlinuz-linux'),
                         ('initrd','.build/v3-iso-boot/initramfs-linux.img'),('artifacts','out/live-auth-v3'),
                         ('firmware-code','/usr/share/OVMF/OVMF_CODE_4M.fd'),('firmware-vars','/usr/share/OVMF/OVMF_VARS_4M.fd')]:
        parser.add_argument('--'+name,type=Path,default=Path(default))
    parser.add_argument('--timeout',type=int,default=600)
    args=parser.parse_args(); args.username='live'; args.expected_version='v3-phase2'
    if args.timeout<120: parser.error('The real Live startup needs a bounded deadline of at least 120 seconds')
    for name in ('iso','kernel','initrd','firmware_code','firmware_vars'): setattr(args,name,getattr(args,name).resolve())
    return AuthorizationAcceptance(args).run()


if __name__=='__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Actual Live user Flatpak installation and native Heroic startup, without login.

The existing GTK installer/client and disposable-VM transport are reused. Root
only delivers/observes the test: installation uses the actual unprivileged GUI,
trusted Flathub and its signed deployment. No account or game is used.
"""
import argparse
import ast
import importlib.util
import inspect
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('husk_steam_acceptance', ROOT/'scripts/ci-test-v3-live-app.py')
steam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(steam)
auth, vm = steam.auth, steam.vm
APP_ID = 'com.heroicgameslauncher.hgl'
CLIENT_NAME = 'huskheroiccheck.py'
GTK_CLIENT = steam.GTK_CLIENT
REQUIRED_CHECKS = ('initial_app_absent', 'initial_system_app_absent', 'live_session_active',
    'unprivileged_launcher', 'confirmation_cancel_unchanged', 'password_unchanged',
    'user_install_record', 'trusted_origin', 'system_packages_unchanged', 'no_system_install',
    'official_icon', 'gtk_verified', 'no_extra_terminal')


def validate_heroic_installation(report):
    if not isinstance(report, dict):
        return ['No actual Heroic observation']
    problems = []
    checks = report.get('checks', {})
    for name in REQUIRED_CHECKS:
        if not isinstance(checks, dict) or checks.get(name) is not True:
            problems.append('Missing actual user Flatpak check: '+name)
    if (report.get('app_id') != APP_ID or report.get('origin') != 'flathub' or
            re.fullmatch('[0-9a-f]{64}', str(report.get('deployment_commit', ''))) is None):
        problems.append('No verified curated user Flatpak deployment')
    return problems


def validate_heroic_report(report):
    problems = validate_heroic_installation(report)
    if not isinstance(report, dict):
        return problems
    if report.get('finished') is not True or report.get('success') is not True:
        problems.append('The actual Heroic observer did not finish successfully')
    launch = report.get('client_launch', {})
    if not isinstance(launch, dict):
        launch = {}
    duration, available = launch.get('healthy_seconds'), launch.get('available_bytes')
    if type(duration) not in (int, float) or not 30 <= duration <= 180:
        problems.append('No 30-second continuous current native Heroic UI')
    if type(available) is not int or available <= 0:
        problems.append('No verified free Live write space')
    if not any(isinstance(entry, dict) and entry.get('app_id', '').lower() in ('heroic', APP_ID) and
               entry.get('minimized') is False and not entry.get('title', '').lower().startswith('install heroic')
               for entry in launch.get('windows', [])):
        problems.append('No current Heroic client window')
    if not any(isinstance(process, dict) and type(process.get('pid')) is int and process['pid'] > 0 and
               process.get('uid') == 1000 and process.get('elf') is True and
               process.get('flatpak_id') == APP_ID and process.get('executable', '').startswith('/app/')
               for process in launch.get('processes', [])):
        problems.append('No unprivileged native process in the Heroic Flatpak namespace')
    return problems


def native_heroic_processes(proc_root, uid):
    import configparser
    rows = []
    for process in proc_root.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            executable = str((process/'exe').readlink())
            if not executable.startswith('/app/'):
                continue
            with (process/'exe').open('rb') as stream:
                if stream.read(4) != b'\x7fELF':
                    continue
            info = configparser.ConfigParser(interpolation=None)
            info.read(process/'root/.flatpak-info')
            if info.get('Application', 'name', fallback='') != 'com.heroicgameslauncher.hgl':
                continue
            rows.append(dict(pid=int(process.name), uid=uid, elf=True,
                flatpak_id='com.heroicgameslauncher.hgl', executable=executable[:1000]))
        except (OSError, configparser.Error):
            continue
        if len(rows) >= 64:
            break
    return rows


# Reuse the existing delivered observer's transport/query helpers verbatim.
_helpers = {'command', 'post', 'environment', 'processes', 'package_snapshot', 'acknowledge', 'password_state'}
_tree = ast.parse(steam.ROOT_OBSERVER)
_nodes = [node for node in _tree.body if isinstance(node, ast.FunctionDef) and node.name in _helpers]
if {node.name for node in _nodes} != _helpers:
    raise RuntimeError('The existing read-only Live observer helpers are incomplete')
ROOT_OBSERVER = ast.unparse(ast.Module(body=_nodes, type_ignores=[])) + '\n' + inspect.getsource(native_heroic_processes) + r'''
import configparser, hashlib, json, os, subprocess, time, urllib.request
from pathlib import Path as P
APP_ID='com.heroicgameslauncher.hgl'
state=dict(phase='installation',stage='starting',finished=False,success=False,checks={},app_id=APP_ID)
def user_query(*args):
    return subprocess.run(['/usr/bin/runuser','-u','live','--','/usr/bin/flatpak',*args],
        capture_output=True,text=True,timeout=20)
def system_absent():
    return subprocess.run(['/usr/bin/flatpak','info','--system',APP_ID],capture_output=True).returncode!=0
def repository_snapshot():
    path=P('/home/live/.local/share/flatpak/repo/config')
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
try:
    if os.getuid()!=0 or not P('/run/archiso').is_dir() or not P('/sys/firmware/efi').is_dir():
        raise RuntimeError('A disposable UEFI Live VM is required')
    if P('/sys/class/block/vda/serial').read_text().strip()!='HUSK-DISPOSABLE':
        raise RuntimeError('Attached disk is not the new disposable image')
    checks=state['checks']; initial_packages=package_snapshot(); initial_repo=repository_snapshot()
    initial_password=password_state()
    checks['initial_app_absent']=user_query('info','--user',APP_ID).returncode!=0
    checks['initial_system_app_absent']=system_absent()
    if not checks['initial_app_absent'] or not checks['initial_system_app_absent'] or initial_password!='NP':
        raise RuntimeError('The fresh Live image must have no Heroic and no account password')
    deadline=time.monotonic()+CONFIG['timeout']; desktop=None
    while time.monotonic()<deadline:
        desktop=next(processes(b'/usr/bin/husk-desktop'),None)
        if desktop is not None: break
        post(); time.sleep(1)
    if desktop is None: raise RuntimeError('The real Husk Live desktop did not start')
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
    config=directory/'client-config.json'
    config.write_text(json.dumps(dict(application='heroic',timeout=CONFIG['timeout'])))
    os.chown(config,uid,uid); config.chmod(0o600)
    state['stage']='terminal-needed'; post()
    while time.monotonic()<deadline and not (list(processes(b'foot',uid))+list(processes(b'/usr/bin/foot',uid))): time.sleep(1)
    state['stage']='terminal-ready'; post()
    probe=directory/'client.json'; control_sent=False; baseline_terminals=None; verified=False
    launch_since=None; healthy_since=None
    while time.monotonic()<deadline:
        if not probe.exists(): post(); time.sleep(1); continue
        info=json.loads(probe.read_text()); state['gtk']=info
        if info.get('error'): raise RuntimeError('Actual GTK application: '+info['error'])
        pid=info.get('pid')
        checks['unprivileged_launcher']=type(pid) is int and uid==1000 and (P('/proc')/str(pid)).stat().st_uid==uid
        terminals=sorted(set(processes(b'foot',uid))|set(processes(b'/usr/bin/foot',uid)))
        if baseline_terminals is None: baseline_terminals=terminals
        checks['no_extra_terminal']=terminals==baseline_terminals and len(terminals)==1
        if not control_sent: acknowledge('confirm-cancel'); control_sent=True
        phase=info.get('phase'); state['stage']=phase
        if info.get('dialog')=='confirmation': state['stage']=phase+'-confirmation'
        if phase=='confirmation-cancelled' and not checks.get('confirmation_cancel_unchanged'):
            checks['confirmation_cancel_unchanged']=(package_snapshot()==initial_packages and
                repository_snapshot()==initial_repo and user_query('info','--user',APP_ID).returncode!=0)
            if not checks['confirmation_cancel_unchanged']: raise RuntimeError('Cancel changed package/repository state')
            acknowledge('install')
        if info.get('ui_state')=='failed':
            raise RuntimeError(info.get('status','')+': '+info.get('detail',''))
        if phase=='installed' and not verified:
            checks['password_unchanged']=password_state()==initial_password=='NP' and info.get('password_dialogs')==0
            installed=user_query('info','--user',APP_ID)
            commit=user_query('info','--user','--show-commit',APP_ID)
            origin=user_query('info','--user','--show-origin',APP_ID)
            state['deployment_commit']=commit.stdout.strip(); state['origin']=origin.stdout.strip()
            state['flatpak_info']=installed.stdout[-12000:]
            checks['user_install_record']=installed.returncode==commit.returncode==origin.returncode==0
            repo=configparser.ConfigParser(interpolation=None)
            repo.read('/home/live/.local/share/flatpak/repo/config')
            state['remote_url']=repo.get('remote "flathub"','url',fallback='')
            checks['trusted_origin']=(state['origin']=='flathub' and
                state['remote_url'] in ('https://dl.flathub.org/repo/','https://dl.flathub.org/repo') and
                repo.getboolean('remote "flathub"','gpg-verify',fallback=False))
            checks['system_packages_unchanged']=package_snapshot()==initial_packages
            checks['no_system_install']=system_absent()
            icon=P('/home/live/.local/share/flatpak/exports/share/applications')/(APP_ID+'.desktop')
            checks['official_icon']=icon.is_file() and ('Icon='+APP_ID) in icon.read_text()
            checks['gtk_verified']=info.get('ui_state')=='complete' and info.get('result_code')==0 and 'installed (verified)' in info.get('status','')
            if not all(checks.get(name) is True for name in CONFIG['required']):
                raise RuntimeError('The actual user Flatpak installation did not satisfy all checks')
            verified=True
        if verified:
            if phase=='installed':
                state['stage']='installed-verified'
                try: acknowledged=urllib.request.urlopen(CONFIG['base']+'/launch',timeout=3).read()==b'LAUNCH\n'
                except Exception: acknowledged=False
                if acknowledged: acknowledge('launch')
            if phase=='launching':
                if launch_since is None: launch_since=time.monotonic()
                space=os.statvfs('/run/archiso/cowspace')
                state['client_launch']=dict(windows=info.get('windows',[]),
                    processes=native_heroic_processes(P('/proc'),uid),available_bytes=space.f_bavail*space.f_frsize)
                healthy=(state['client_launch']['windows'] and state['client_launch']['processes'] and
                         state['client_launch']['available_bytes']>0)
                if not healthy: healthy_since=None
                elif healthy_since is None: healthy_since=time.monotonic()
                duration=time.monotonic()-healthy_since if healthy_since is not None else 0
                if duration>=30 or time.monotonic()-launch_since>=180:
                    state['client_launch']['healthy_seconds']=duration
                    state.update(stage='launch-observed',finished=True,success=True); post(); break
        post(); time.sleep(1)
    if not state['success']: raise RuntimeError('The bounded Heroic acceptance deadline expired')
    while time.monotonic()<deadline:
        try:
            if urllib.request.urlopen(CONFIG['base']+'/cleanup',timeout=3).read()==b'CLEANUP\n':
                state['cleanup_completed']=True; break
        except Exception: pass
        time.sleep(1)
except Exception as error:
    state.update(error=type(error).__name__+': '+str(error),success=False)
finally:
    try:
        output=directory/'client-output.log'
        if output.exists(): state['client_output']=output.read_text(errors='replace')[-80000:]
    except Exception: pass
    state['finished']=True; post()
'''


class HeroicAcceptance(auth.AuthorizationAcceptance):
    success_key = 'package_installation'
    client_source, observer_source = GTK_CLIENT, ROOT_OBSERVER
    required_checks, client_name = REQUIRED_CHECKS, CLIENT_NAME
    proof_scope = 'Actual Live user Flatpak install and native Heroic startup; no administrator authorization, account or game'

    def run(self):
        result = super().run()
        return result or (0 if self.result.get('client_startup') == 'PASSED' else 1)

    def live_authorization(self):
        self.result['client_startup']='NOT TESTED'
        started=time.monotonic(); next_ready=15; delivered=terminal=launched=captured=False
        handled=set(); pending={}; previous=None
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
                if stage!=previous: print('Live Heroic checkpoint:',stage,flush=True); previous=stage
                if stage=='terminal-needed' and not terminal:
                    self.monitor.key('meta_l-ret'); terminal=True
                if stage=='terminal-ready' and not launched:
                    self.monitor.console('python3 '+CLIENT_NAME); launched=True
                if stage in ('confirm-cancel-confirmation','install-confirmation') and stage not in handled:
                    pending.setdefault(stage,time.monotonic())
                    if time.monotonic()-pending[stage]>=3:
                        self.monitor.key('esc' if stage.startswith('confirm-cancel') else 'ret'); handled.add(stage)
                if stage=='installed-verified' and 'launch' not in self.resources:
                    problems=validate_heroic_installation(report)
                    if problems: raise RuntimeError('; '.join(problems))
                    self.result['package_installation']='PASSED'
                    self.monitor.capture(self.artifacts/'heroic-installation-verified.png')
                    self.resources['launch']=b'LAUNCH\n'
                if report.get('finished'):
                    if not validate_heroic_installation(report):
                        self.result['package_installation']='PASSED'
                    problems=validate_heroic_report(report)
                    if problems:
                        if self.result['package_installation']=='PASSED':
                            self.result['client_startup']='FAILED'
                        raise RuntimeError('; '.join(problems)+': '+report.get('error',''))
                    if not captured:
                        self.monitor.capture(self.artifacts/'heroic-client-startup.png')
                        self.result['target_blockstats']=vm.cancellation_blockstats(self.monitor.command('query-blockstats'))
                        self.result.update(client_startup='PASSED',client_launch=report['client_launch'],
                            app_id=APP_ID,origin=report['origin'],deployment_commit=report['deployment_commit'])
                        self.resources['cleanup']=b'CLEANUP\n'; captured=True
                    if report.get('cleanup_completed') is True:
                        self.result['package_installation']='PASSED'; return
            time.sleep(1)
        raise RuntimeError('The bounded Heroic acceptance deadline expired at '+str(previous))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name,default in [('iso','out/HuskOS-v3-phase2.iso'),('kernel','.build/v3-iso-boot/vmlinuz-linux'),
                         ('initrd','.build/v3-iso-boot/initramfs-linux.img'),('artifacts','out/live-app-v3'),
                         ('firmware-code','/usr/share/OVMF/OVMF_CODE_4M.fd'),('firmware-vars','/usr/share/OVMF/OVMF_VARS_4M.fd')]:
        parser.add_argument('--'+name,type=Path,default=Path(default))
    parser.add_argument('--timeout',type=int,default=1500)
    parser.add_argument('--memory-mib',type=int,choices=(4096,8192,12288),default=4096)
    args=parser.parse_args(); args.username='live'; args.expected_version='v3-phase2'
    if not 300<=args.timeout<=2400: parser.error('Bounded Live application timeout must be 300–2400 seconds')
    for name in ('iso','kernel','initrd','firmware_code','firmware_vars'): setattr(args,name,getattr(args,name).resolve())
    return HeroicAcceptance(args).run()


if __name__=='__main__':
    raise SystemExit(main())

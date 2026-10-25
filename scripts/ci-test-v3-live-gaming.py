#!/usr/bin/env python3
"""Actual accountless SuperTuxKart input, virtual audio and 3D race acceptance."""
import argparse
import array
import ast
import hashlib
import importlib.util
import inspect
import json
import math
from pathlib import Path
import re
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('husk_heroic_acceptance', ROOT/'scripts/ci-test-v3-live-heroic.py')
heroic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(heroic)
auth, vm = heroic.auth, heroic.vm
APP_ID = 'net.supertuxkart.SuperTuxKart'
CLIENT_NAME = 'huskgamecheck.py'
REQUIRED_CHECKS = ('live_session_active', 'unprivileged_launcher', 'initial_app_absent',
    'user_install_record', 'trusted_origin', 'system_packages_unchanged',
    'password_unchanged', 'no_system_install', 'no_extra_terminal')


def parse_input_history(text):
    if not isinstance(text, str) or len(text) > 512000:
        raise ValueError('No bounded original game input history')
    def field(name):
        match = re.search(r'^'+re.escape(name)+r':\s*(\S+)', text, re.M)
        if not match: raise ValueError('Missing game input field: '+name)
        return match.group(1)
    if field('STK-version') != '1.5' or field('History-version') != '1':
        raise ValueError('Unreviewed game input format/version')
    if field('numplayers') != '1' or field('numkarts') != '1' or field('track') != 'lighthouse':
        raise ValueError('Input was not recorded in the single-player test race')
    count = int(field('count'))
    rows = [tuple(map(int, line.split())) for line in text.splitlines()
            if re.fullmatch(r'\d+ \d+ \d+ \d+', line)]
    if not 4 <= count <= 100000 or len(rows) != count or not text.rstrip().endswith('History file end.'):
        raise ValueError('Incomplete game input history')
    if any(kart != 0 or action > 15 or value > 32768 for _, kart, action, value in rows):
        raise ValueError('Invalid native game input event')
    if [row[0] for row in rows] != sorted(row[0] for row in rows):
        raise ValueError('Game input ticks are not ordered')
    def pressed_released(action):
        pressed = next((i for i, row in enumerate(rows) if row[2] == action and row[3] > 0), None)
        return pressed is not None and any(row[2] == action and row[3] == 0 for row in rows[pressed+1:])
    accelerated = pressed_released(2)  # Upstream 1.5 input.hpp: PA_ACCEL=2.
    steered = pressed_released(0) or pressed_released(1)
    if not accelerated or not steered:
        raise ValueError('No human acceleration/steering press and release in the game engine')
    return dict(events=count, accelerated=accelerated, steered=steered,
                first_tick=rows[0][0], last_tick=rows[-1][0])


def parse_profile_log(text):
    if not isinstance(text, str): raise ValueError('No native game profile log')
    match = re.search(r'Number of frames:\s*(\d+)\s+time\s+([^,\s]+),\s*Average FPS:\s*(\S+)', text, re.I)
    gl = re.search(r'OpenGL(?: version)?[:\s]+([0-9]+\.[0-9]+)', text, re.I)
    renderer = re.search(r'(?:OpenGL renderer|Renderer):\s*([^\r\n]+)', text, re.I)
    if not renderer: renderer = re.search(r'((?:llvmpipe|softpipe)[^\r\n]+)', text, re.I)
    geometry = re.search(r'Average # drawn nodes\s+([^\s]+)', text, re.I)
    if not all((match, gl, renderer, geometry)):
        raise ValueError('No complete rendered OpenGL race statistics/renderer')
    frames, runtime, reported_fps = int(match[1]), float(match[2]), float(match[3])
    triangles = float(geometry[1])
    if (frames <= 0 or not math.isfinite(runtime) or not 60 <= runtime <= 600 or
            not math.isfinite(reported_fps) or reported_fps <= 0 or
            not math.isfinite(triangles) or triangles <= 0):
        raise ValueError('Invalid or short native game profile')
    return dict(frames=frames, runtime_seconds=runtime,
        upstream_reported_fps=reported_fps, average_drawn_nodes_k=triangles,
        opengl_version=gl[1], renderer=renderer[1].strip())


def summarize_audio(path, start_byte, end_byte, clip_path=None):
    if type(start_byte) is not int or type(end_byte) is not int or not 0 <= start_byte < end_byte:
        raise ValueError('No measured game audio interval')
    with Path(path).open('rb') as raw, wave.open(raw, 'rb') as source:
        channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
        data_start = raw.tell()
        if width != 2 or channels not in (1, 2) or not 8000 <= rate <= 192000:
            raise ValueError('Unsupported virtual PCM audio format')
        block = channels*width
        first = max(0, start_byte-data_start)//block
        last = min(source.getnframes(), max(0, end_byte-data_start)//block, first+rate*15)
        if first >= last: raise ValueError('No complete frames in the measured audio interval')
        source.setpos(first); pcm = source.readframes(last-first)
        samples = array.array('h', pcm)
        if sys.byteorder != 'little': samples.byteswap()
        result = dict(seconds=len(pcm)/block/rate, sample_rate=rate, channels=channels,
            peak=max(abs(value) for value in samples),
            rms=math.sqrt(sum(value*value for value in samples)/len(samples)),
            minimum=min(samples), maximum=max(samples), bytes=len(pcm),
            temporal_peak_to_peak=max(max(samples[channel::channels])-min(samples[channel::channels])
                for channel in range(channels)))
        if clip_path is not None:
            with wave.open(str(clip_path), 'wb') as clip:
                clip.setparams((channels,width,rate,0,'NONE','not compressed')); clip.writeframes(pcm)
        return result


def validate_audio(summary):
    if not isinstance(summary, dict): return ['No measured virtual game audio']
    numbers = [summary.get(key) for key in ('seconds','peak','rms','minimum','maximum','temporal_peak_to_peak')]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in numbers):
        return ['Invalid virtual game audio measurements']
    if not 2 <= summary['seconds'] <= 15 or summary['peak'] <= 32 or summary['rms'] <= 5 or summary['temporal_peak_to_peak'] <= 64:
        return ['Measured game interval was too short or had no varying non-silent PCM']
    return []


def validate_audio_capture(capture):
    if not isinstance(capture,dict): return ['No game-attributed audio capture bracket']
    start,end=capture.get('start'),capture.get('end')
    if any(type(value) not in (int,float) or not math.isfinite(value) for value in (start,end)) or not 8 <= end-start <= 60:
        return ['Invalid game audio capture times']
    observations=capture.get('observations',[])
    if not isinstance(observations,list) or not 4 <= len(observations) <= 512:
        return ['No continuous game audio observations']
    times=[row.get('at') if isinstance(row,dict) else None for row in observations]
    if any(type(value) not in (int,float) or not math.isfinite(value) for value in times) or times!=sorted(times):
        return ['Invalid game audio observation clock']
    before=[i for i,value in enumerate(times) if value<=start]
    after=[i for i,value in enumerate(times) if value>=end]
    if not before or not after: return ['Game audio observations do not bracket the capture']
    segment=observations[before[-1]:after[0]+1]
    if len(segment)<4 or any(b['at']-a['at']>2.5 for a,b in zip(segment,segment[1:])):
        return ['Game audio attribution was stale during capture']
    pids=set()
    for row in capture.get('native_processes',[]):
        if (isinstance(row,dict) and row.get('uid')==1000 and row.get('elf') is True and
                row.get('flatpak_id')==APP_ID and type(row.get('pid')) is int and row['pid']>0):
            pids.add(str(row['pid']))
            pids.update(str(value) for value in row.get('namespace_pids',[]) if type(value) is int and value>0)
    for observation in segment:
        streams=observation.get('streams',[])
        if observation.get('error') or observation.get('other_streams'):
            return ['Audio query failed or another active stream could contaminate game capture']
        if not isinstance(streams,list) or not any(isinstance(row,dict) and
                row.get('mute') is False and row.get('corked') is False and
                'supertuxkart' in str(row.get('properties',{}).get('application.name','')).lower() and
                str(row.get('properties',{}).get('application.process.id','')) in pids for row in streams):
            return ['The native game audio stream disappeared or could not be attributed during capture']
    return []


def validate_gameplay_report(report):
    if not isinstance(report, dict): return ['No actual game observation']
    problems=[]
    if report.get('finished') is not True or report.get('success') is not True:
        problems.append('Actual gaming observer did not complete successfully')
    checks=report.get('checks',{})
    for name in REQUIRED_CHECKS:
        if not isinstance(checks,dict) or checks.get(name) is not True:
            problems.append('Missing actual gaming check: '+name)
    if (report.get('app_id')!=APP_ID or report.get('origin')!='flathub' or
            re.fullmatch('[0-9a-f]{64}',str(report.get('deployment_commit',''))) is None):
        problems.append('No verified signed user game deployment')
    try: parse_input_history(report.get('input_history'))
    except (ValueError,TypeError): problems.append('No actual human controls consumed by the game engine')
    client=report.get('client',{})
    if not isinstance(client,dict): client={}
    try: parse_profile_log(client.get('profile_log'))
    except (ValueError,TypeError): problems.append('No completed rendered OpenGL game profile')
    if type(client.get('profile_exit_code')) is not int or client['profile_exit_code']!=0:
        problems.append('The actual profile race did not exit naturally with code zero')
    streams=client.get('audio_streams',[])
    if not isinstance(streams,list) or not any(isinstance(row,dict) and row.get('mute') is False and
            'supertuxkart' in str(row.get('properties',{}).get('application.name','')).lower() for row in streams):
        problems.append('No unmuted guest audio stream attributed to SuperTuxKart')
    problems.extend(validate_audio_capture(report.get('audio_capture')))
    stable=report.get('stability',{})
    if not isinstance(stable,dict): stable={}
    duration, samples=stable.get('healthy_seconds'),stable.get('samples')
    if type(duration) not in (int,float) or not math.isfinite(duration) or not 60 <= duration <= 600 or type(samples) is not int or samples<3:
        problems.append('No 60-second continuous native game/window observation')
    if not any(isinstance(row,dict) and row.get('minimized') is False and
            row.get('app_id','').lower() in ('supertuxkart',APP_ID.lower()) for row in stable.get('windows',[])):
        problems.append('No current native game window during stability measurement')
    if not any(isinstance(row,dict) and type(row.get('pid')) is int and row['pid']>0 and
            row.get('uid')==1000 and row.get('elf') is True and row.get('flatpak_id')==APP_ID and
            row.get('executable','').startswith('/app/') for row in stable.get('processes',[])):
        problems.append('No unprivileged native game ELF in its exact Flatpak namespace')
    if type(report.get('available_bytes')) is not int or report['available_bytes']<=0:
        problems.append('No free Live game write space')
    return problems


GAME_CLIENT = r'''
import json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,'/usr/lib/ownos')
from ownos.bridge import PipeLineReader
from ownos.toplevel import ToplevelStore
from ownos.config import ConfigStore
from ownos.gaming import game_command
from ownos.app_install import trusted_flathub
from ownos.catalog import FLATHUB_REPOFILE
APP_ID='net.supertuxkart.SuperTuxKart'
directory=Path('/run/husk-v3-auth')
CONFIG=json.loads((directory/'client-config.json').read_text())
output=(directory/'client-output.log').open('a',buffering=1)
os.dup2(output.fileno(),1); os.dup2(output.fileno(),2)
state=dict(pid=os.getpid(),uid=os.getuid(),phase='installing',finished=False,windows=[],audio_streams=[],audio_observations=[])
bridge=None; process=None; store=ToplevelStore()
def tail(path):
    if not path.is_file(): return ''
    with path.open('rb') as stream:
        head=stream.read(16000); stream.seek(max(16000,path.stat().st_size-80000))
        return (head+stream.read(80000)).decode(errors='replace')
def write():
    temporary=directory/'client.tmp';temporary.write_text(json.dumps(state));temporary.replace(directory/'client.json')
def pump():
    if bridge is not None:
        lines,ended=reader.read_ready()
        for line in lines:
            try: store.apply(json.loads(line))
            except (ValueError,TypeError): pass
        state['windows']=[] if ended else [row for row in store.entries.values()
            if row['app_id'].lower() in ('supertuxkart',APP_ID.lower()) and not row['minimized']]
        if ended: state['bridge_error']='The native toplevel observer closed'
    write()
try:
    if os.getuid()!=1000: raise RuntimeError('The game must run in the actual normal-user session')
    write();trusted_flathub()
    with (directory/'game-install.log').open('w') as log:
        for argv in (['/usr/bin/flatpak','remote-add','--user','--if-not-exists','flathub',FLATHUB_REPOFILE],
                     ['/usr/bin/flatpak','install','--user','--noninteractive','--assumeyes','flathub',APP_ID]):
            installed=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,timeout=1100)
            if installed.returncode: raise RuntimeError('Signed user game installation exited '+str(installed.returncode))
    trusted_flathub()
    state['install_log']=tail(directory/'game-install.log')
    state['game_version']=subprocess.run(['/usr/bin/flatpak','run',APP_ID,'--version'],
        capture_output=True,text=True,timeout=30).stdout.strip()
    settings=ConfigStore().load()
    state['game_policy']={key:settings[key] for key in ('gaming_mode','overlay')}
    common=['--no-start-screen','--track=lighthouse','--kart=tux','--difficulty=0',
        '--fullscreen','--screensize=800x600','--render-driver=gl','--disable-dynamic-lights',
        '--disable-ssao','--shadows=0','--log=0']
    bridge=subprocess.Popen(['/usr/bin/own-toplevel'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    reader=PipeLineReader(bridge.stdout.fileno())
    def launch(options,log):
        argv=['/usr/bin/flatpak','run',APP_ID,*common,*options]
        # Record the existing policy decision, then execute the real installed
        # Husk entry point which reloads that unchanged configuration itself.
        state['policy_command']=game_command(argv,settings)
        return subprocess.Popen(['/usr/bin/husk-game','--',*argv],stdout=log,stderr=subprocess.STDOUT)
    with (directory/'game-normal.log').open('w') as log:
        state['phase']='normal-loading';process=launch(['--numkarts=1','--laps=99','--use-keyboard=0'],log)
        launched=time.monotonic()
        while time.monotonic()-launched<180:
            if process.poll() is not None: raise RuntimeError('The normal race exited before input acceptance')
            state['normal_log']=tail(directory/'game-normal.log');pump()
            if time.monotonic()-launched>=15 and state['windows']:
                state['phase']='normal-ready'
                state['audio_streams']=[]
                query=subprocess.run(['/usr/bin/pactl','-f','json','list','sink-inputs'],capture_output=True,text=True,timeout=10)
                observation=dict(at=time.monotonic(),streams=[],other_streams=[],error=None)
                if query.returncode==0:
                    streams=json.loads(query.stdout)
                    matched=[row for row in streams if 'supertuxkart' in
                        str(row.get('properties',{}).get('application.name','')).lower()]
                    state['audio_streams']=matched;observation['streams']=matched
                    observation['other_streams']=[row for row in streams if row not in matched and
                        row.get('mute') is False and row.get('corked') is False]
                else:
                    observation['error']=query.stderr[-4000:] or 'pactl failed'
                    state['audio_query_error']=observation['error']
                state['audio_observations']=(state['audio_observations']+[observation])[-512:]
                pump()
            control=directory/'control'
            if control.is_file() and control.read_text().strip()=='profile': break
            time.sleep(.25)
        else: raise RuntimeError('The normal race never received verified host input acknowledgement')
        subprocess.run(['/usr/bin/flatpak','kill',APP_ID],capture_output=True,timeout=15)
        process.wait(timeout=20);state['normal_controlled_stop']=True
    with (directory/'game-profile.log').open('w') as log:
        state['phase']='profile-running';process=launch(['--numkarts=3','--profile-time=120'],log)
        launched=time.monotonic();pump()
        while process.poll() is None:
            state['profile_log']=tail(directory/'game-profile.log');pump()
            if time.monotonic()-launched>540: raise RuntimeError('The bounded 3D profile did not finish')
            time.sleep(.25)
        state['profile_exit_code']=process.returncode
        state['profile_log']=tail(directory/'game-profile.log')
    state.update(phase='completed',finished=True);pump()
    until=time.monotonic()+60
    while time.monotonic()<until:
        if (directory/'control').read_text().strip()=='stop': break
        time.sleep(.5)
except Exception as error:
    state.update(error=type(error).__name__+': '+str(error),finished=True)
    for name in ('install','normal','profile'):
        state[name+'_log']=tail(directory/('game-'+name+'.log'))
    write()
finally:
    if process is not None and process.poll() is None:
        subprocess.run(['/usr/bin/flatpak','kill',APP_ID],capture_output=True,timeout=15)
    if bridge is not None: bridge.terminate()
'''


ROOT_OBSERVER = (ast.unparse(ast.Module(body=heroic._nodes,type_ignores=[]))+'\n'+
    inspect.getsource(heroic.native_heroic_processes)+inspect.getsource(validate_audio_capture)) + r'''
import configparser, hashlib, json, math, os, subprocess, time, urllib.request
from pathlib import Path as P
APP_ID='net.supertuxkart.SuperTuxKart'
state=dict(phase='installation',stage='starting',finished=False,success=False,checks={},app_id=APP_ID)
def user_query(*args):
    return subprocess.run(['/usr/bin/runuser','-u','live','--','/usr/bin/flatpak',*args],
        capture_output=True,text=True,timeout=20)
def read_history(native):
    candidates=[]
    for row in native:
        candidates.append(P('/proc')/str(row['pid'])/'cwd/history.dat')
    config=P('/home/live/.var/app')/APP_ID/'config'
    if config.is_dir(): candidates+=list(config.glob('supertuxkart/*/history.dat'))[:16]
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size<=512000:
                value=path.read_text()
                if value.startswith('STK-version:'): return value
        except OSError: pass
    return None
try:
    if os.getuid()!=0 or not P('/run/archiso').is_dir() or not P('/sys/firmware/efi').is_dir():
        raise RuntimeError('A disposable UEFI Live VM is required')
    if P('/sys/class/block/vda/serial').read_text().strip()!='HUSK-DISPOSABLE':
        raise RuntimeError('Attached disk is not the new disposable image')
    checks=state['checks'];initial_packages=package_snapshot();initial_password=password_state()
    checks['initial_app_absent']=user_query('info','--user',APP_ID).returncode!=0
    if not checks['initial_app_absent'] or initial_password!='NP': raise RuntimeError('The fresh image must have no game or account password')
    deadline=time.monotonic()+CONFIG['timeout'];desktop=None
    while time.monotonic()<deadline:
        desktop=next(processes(b'/usr/bin/husk-desktop'),None)
        if desktop is not None: break
        post();time.sleep(1)
    if desktop is None: raise RuntimeError('The actual Live desktop did not start')
    uid=(P('/proc')/str(desktop)).stat().st_uid;env=environment(desktop)
    details=command(['/usr/bin/loginctl','show-session',env.get('XDG_SESSION_ID',''),'-p','Name','-p','Active','-p','Remote'])
    state['live_session']=details.splitlines()
    checks['live_session_active']={'Name=live','Active=yes','Remote=no'}<=set(details.splitlines())
    directory=P('/run/husk-v3-auth');directory.mkdir(mode=0o700);os.chown(directory,uid,uid)
    client=directory/'client.py';urllib.request.urlretrieve(CONFIG['base']+'/client.py',client)
    if hashlib.sha256(client.read_bytes()).hexdigest()!=CONFIG['client_sha256']: raise RuntimeError('Wrong game client digest')
    client.chmod(0o644)
    home=P('/home/live')/CONFIG['client_name']
    if home.exists() or home.is_symlink(): raise RuntimeError('Refusing to replace a Live home file')
    home.symlink_to(client)
    config=directory/'client-config.json';config.write_text(json.dumps(dict(timeout=CONFIG['timeout'])))
    os.chown(config,uid,uid);config.chmod(0o600)
    state['stage']='terminal-needed';post()
    while time.monotonic()<deadline and not (list(processes(b'foot',uid))+list(processes(b'/usr/bin/foot',uid))): time.sleep(1)
    state['stage']='terminal-ready';post()
    probe=directory/'client.json';baseline_terminals=None;verified=False;healthy_since=None;samples=0;history_since=None;capture_end=None
    while time.monotonic()<deadline:
        if not probe.exists(): post();time.sleep(1);continue
        info=json.loads(probe.read_text());state['client']=info;state['stage']=info.get('phase')
        if info.get('error'): raise RuntimeError('Actual game client: '+info['error'])
        pid=info.get('pid')
        checks['unprivileged_launcher']=type(pid) is int and uid==1000 and (P('/proc')/str(pid)).stat().st_uid==uid
        terminals=sorted(set(processes(b'foot',uid))|set(processes(b'/usr/bin/foot',uid)))
        if baseline_terminals is None: baseline_terminals=terminals
        checks['no_extra_terminal']=terminals==baseline_terminals and len(terminals)==1
        if str(info.get('phase','')).startswith(('normal','profile')) and not verified:
            installed=user_query('info','--user',APP_ID);commit=user_query('info','--user','--show-commit',APP_ID)
            origin=user_query('info','--user','--show-origin',APP_ID)
            state['deployment_commit']=commit.stdout.strip();state['origin']=origin.stdout.strip()
            state['flatpak_info']=installed.stdout[-12000:]
            checks['user_install_record']=installed.returncode==commit.returncode==origin.returncode==0
            repo=configparser.ConfigParser(interpolation=None);repo.read('/home/live/.local/share/flatpak/repo/config')
            state['remote_url']=repo.get('remote "flathub"','url',fallback='')
            checks['trusted_origin']=(state['origin']=='flathub' and state['remote_url'] in
                ('https://dl.flathub.org/repo/','https://dl.flathub.org/repo') and
                repo.getboolean('remote "flathub"','gpg-verify',fallback=False))
            verified=True
        native=native_heroic_processes(P('/proc'),uid,APP_ID)
        for row in native:
            try:
                status=(P('/proc')/str(row['pid'])/'status').read_text()
                row['namespace_pids']=[int(value) for line in status.splitlines() if line.startswith('NSpid:') for value in line.split()[1:]]
            except OSError: row['namespace_pids']=[]
        state['native_current']=native
        space=os.statvfs('/run/archiso/cowspace');state['available_bytes']=space.f_bavail*space.f_frsize
        if info.get('phase')=='normal-ready':
            observations=info.get('audio_observations',[])
            state['audio_observation_age']=time.monotonic()-observations[-1]['at'] if observations else None
            try: driven=urllib.request.urlopen(CONFIG['base']+'/drive',timeout=2).read()==b'DRIVEN\n'
            except Exception: driven=False
            if driven:
                if history_since is None: history_since=time.monotonic()
                history=read_history(native)
                if history:
                    state['input_history']=history
                    if capture_end is None: capture_end=time.monotonic()
                    if observations and observations[-1]['at']>=capture_end:
                        begin=json.loads(urllib.request.urlopen(CONFIG['base']+'/audio-begin',timeout=3).read())
                        state['audio_capture']=dict(start=begin['at'],end=capture_end,
                            observations=observations,native_processes=native)
                        problems=validate_audio_capture(state['audio_capture'])
                        if problems: raise RuntimeError('; '.join(problems))
                        acknowledge('profile')
                elif time.monotonic()-history_since>20:
                    raise RuntimeError('The game did not save its actual controller history after Ctrl-F11')
        if info.get('phase')=='profile-running':
            windows=info.get('windows',[])
            if native and windows and state['available_bytes']>0:
                if healthy_since is None: healthy_since=time.monotonic();samples=0
                samples+=1;duration=time.monotonic()-healthy_since
                if duration>=state.get('stability',{}).get('healthy_seconds',0):
                    state['stability']=dict(healthy_seconds=duration,samples=samples,windows=windows,processes=native)
            else: healthy_since=None;samples=0
        if info.get('finished'):
            checks['system_packages_unchanged']=package_snapshot()==initial_packages
            checks['password_unchanged']=password_state()==initial_password=='NP'
            checks['no_system_install']=subprocess.run(['/usr/bin/flatpak','info','--system',APP_ID],capture_output=True).returncode!=0
            if not all(checks.get(name) is True for name in CONFIG['required']):
                raise RuntimeError('The actual game installation did not satisfy all session/deployment guards')
            state.update(stage='gameplay-observed',finished=True,success=True);post();break
        post();time.sleep(1)
    if not state['success']: raise RuntimeError('The bounded actual game deadline expired')
    while time.monotonic()<deadline:
        try:
            if urllib.request.urlopen(CONFIG['base']+'/cleanup',timeout=3).read()==b'CLEANUP\n':
                acknowledge('stop');state['cleanup_completed']=True;break
        except Exception: pass
        time.sleep(1)
except Exception as error:
    state.update(error=type(error).__name__+': '+str(error),success=False)
finally:
    try:
        output=directory/'client-output.log'
        if output.exists(): state['client_output']=output.read_text(errors='replace')[-80000:]
    except Exception: pass
    state['finished']=True;post()
'''


class GamingAcceptance(auth.AuthorizationAcceptance):
    success_key='gameplay'
    client_source,observer_source=GAME_CLIENT,ROOT_OBSERVER
    required_checks,client_name=REQUIRED_CHECKS,CLIENT_NAME
    proof_scope='Actual accountless STK user install, QMP/game-engine input, rendered OpenGL race and virtual HDA output; no physical hardware claim'
    audio_interval=None

    def run(self):
        status=super().run()
        try:
            if self.audio_interval is None: raise ValueError('No game-attributed audio capture interval was measured')
            summary=summarize_audio(self.artifacts/'game-audio.wav',*self.audio_interval,
                clip_path=self.artifacts/'game-audio-clip.wav')
            problems=validate_audio(summary);self.result['audio_measurements']=summary
            self.result['virtual_audio']='FAILED' if problems else 'PASSED'
            self.result['problems'].extend(problems)
        except (OSError,ValueError,wave.Error) as error:
            self.result['virtual_audio']='FAILED';self.result['problems'].append('Virtual audio: '+str(error))
        safe=vm.redact_artifact_text(json.dumps(self.result,indent=2),self.password)
        (self.artifacts/'result.json').write_text(safe+'\n');print(safe,flush=True)
        return 0 if status==0 and self.result['virtual_audio']=='PASSED' else 1

    def drive(self,report):
        self.monitor.capture(self.artifacts/'game-before-input.png')
        def key(name,down):
            self.monitor.command('input-send-event',{'events':[{'type':'key','data':
                {'down':down,'key':{'type':'qcode','data':name}}}]})
        start=(self.artifacts/'game-audio.wav').stat().st_size
        observation=report['client']['audio_observations'][-1]
        self.resources['audio-begin']=json.dumps(dict(at=observation['at'])).encode()
        try:
            key('up',True);time.sleep(4)
            key('right',True);time.sleep(1);key('right',False)
            key('left',True);time.sleep(1);key('left',False)
            time.sleep(3)
        finally:
            for name in ('up','right','left'): key(name,False)
        self.monitor.key('ctrl-f11');time.sleep(1)
        end=(self.artifacts/'game-audio.wav').stat().st_size
        self.audio_interval=(start,end)
        self.result['audio_capture_interval_bytes']=[start,end]
        self.monitor.capture(self.artifacts/'game-after-input.png')
        self.resources['drive']=b'DRIVEN\n'

    def live_authorization(self):
        self.result.update(package_installation='NOT TESTED',virtual_audio='NOT TESTED')
        started=time.monotonic();next_ready=15;delivered=terminal=launched=driven=captured=False
        previous=None;frames=[];next_frame=0
        while time.monotonic()-started<self.args.timeout:
            self.alive();elapsed=time.monotonic()-started;output=self.serial.read()
            if not delivered:
                if self.ready_marker in output:
                    self.serial.sendline('umask 077; curl -fsS --max-time 30 -o /tmp/husk-app-observer.py '+
                        self.base+'/setup.py && python3 /tmp/husk-app-observer.py');delivered=True
                elif elapsed>=next_ready:
                    self.serial.interrupt();self.serial.sendline('[ "$(id -u)" = 0 ] && curl -fsS --max-time 10 '+self.base+'/ready')
                    next_ready=elapsed+20
            report=self.latest('installation')
            if report:
                stage=report.get('stage');client=report.get('client',{})
                if stage!=previous: print('Actual gaming checkpoint:',stage,flush=True);previous=stage
                if stage=='terminal-needed' and not terminal: self.monitor.key('meta_l-ret');terminal=True
                if stage=='terminal-ready' and not launched: self.monitor.console('python3 '+CLIENT_NAME);launched=True
                if report.get('checks',{}).get('user_install_record') is True and report.get('checks',{}).get('trusted_origin') is True:
                    self.result['package_installation']='PASSED'
                if stage=='normal-ready' and not driven and report.get('native_current') and client.get('audio_streams'):
                    age=report.get('audio_observation_age')
                    if type(age) in (int,float) and 0<=age<=2 and any(row.get('active') is True for row in client.get('windows',[])):
                        self.drive(report);driven=True
                stable=report.get('stability',{})
                if stage=='profile-running' and stable.get('healthy_seconds',-1)>=next_frame and len(frames)<4:
                    path=self.artifacts/('game-profile-'+str(len(frames))+'.png');self.monitor.capture(path)
                    frames.append(dict(file=path.name,healthy_seconds=stable['healthy_seconds'],sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                    next_frame+=20
                if report.get('finished'):
                    problems=validate_gameplay_report(report)
                    if problems: raise RuntimeError('; '.join(problems)+': '+report.get('error',''))
                    if len(frames)<4 or len({row['sha256'] for row in frames})<3:
                        raise RuntimeError('No sequence of changing rendered race frames across stability measurement')
                    if not captured:
                        self.result['target_blockstats']=vm.cancellation_blockstats(self.monitor.command('query-blockstats'))
                        self.result.update(input=parse_input_history(report['input_history']),
                            profile=parse_profile_log(client['profile_log']),stability=stable,
                            rendered_frames=frames,game_policy=client.get('game_policy'),
                            deployment_commit=report['deployment_commit'],origin=report['origin'])
                        (self.artifacts/'game-input-history.log').write_text(report['input_history'])
                        self.resources['cleanup']=b'CLEANUP\n';captured=True
                    if report.get('cleanup_completed') is True:
                        self.result['gameplay']='PASSED';return
            time.sleep(1)
        raise RuntimeError('The bounded game acceptance deadline expired at '+str(previous))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name,default in [('iso','out/HuskOS-v3-phase2.iso'),('kernel','.build/v3-iso-boot/vmlinuz-linux'),
                         ('initrd','.build/v3-iso-boot/initramfs-linux.img'),('artifacts','out/live-app-v3'),
                         ('firmware-code','/usr/share/OVMF/OVMF_CODE_4M.fd'),('firmware-vars','/usr/share/OVMF/OVMF_VARS_4M.fd')]:
        parser.add_argument('--'+name,type=Path,default=Path(default))
    parser.add_argument('--timeout',type=int,default=1500)
    parser.add_argument('--memory-mib',type=int,choices=(4096,8192,12288),default=4096)
    args=parser.parse_args();args.username='live';args.expected_version='v3-phase2'
    if not 600<=args.timeout<=2400: parser.error('Actual game acceptance needs a bounded 600..2400 second deadline')
    for name in ('iso','kernel','initrd','firmware_code','firmware_vars'): setattr(args,name,getattr(args,name).resolve())
    args.audio_path=args.artifacts.resolve()/'game-audio.wav'
    return GamingAcceptance(args).run()


if __name__=='__main__':
    raise SystemExit(main())

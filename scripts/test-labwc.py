#!/usr/bin/env python3
"""Real Labwc/Wayland integration test, without building or booting an ISO.

On a disposable Ubuntu runner, install the dependencies and source packages as
shown in .github/workflows/system2-desktop.yml, then run this script. Xvfb is
only Labwc's parent X server: Husk Desktop, GTK apps and Foot are Wayland
clients, with real layer-shell, foreign-toplevel and screencopy protocols.
Decoration actions use XTest pointer events forwarded through Labwc's X11
backend. Telemetry observes application state; it never substitutes actions.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def output_candidates(tree):
    """Find nested outputs even when a bare X server has no WM name atoms."""
    candidates = []
    for line in tree.splitlines():
        match = re.match(r'^\s*(0x[0-9a-fA-F]+)\s+.*?\s(\d+)x(\d+)[+-]\d+[+-]\d+', line)
        if match:
            identifier, width, height = match.groups()
            if int(width) >= 320 and int(height) >= 200:
                candidates.append((int(width) * int(height), identifier))
    return [identifier for _, identifier in sorted(candidates, reverse=True)]


class DesktopTest:
    def __init__(self, artifacts):
        self.artifacts = artifacts
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='husk-labwc-')
        self.runtime = Path(self.temporary.name)
        self.telemetry = self.runtime / 'telemetry'
        self.telemetry.mkdir()
        self.processes = []
        self.logs = []
        self.results = []
        self.environment = dict(os.environ)
        for key in ('WAYLAND_DISPLAY', 'WAYLAND_SOCKET'):
            self.environment.pop(key, None)
        self.environment.update(
            HOME=str(self.runtime / 'home'), XDG_CONFIG_HOME=str(self.runtime / 'config'),
            XDG_DATA_HOME=str(self.runtime / 'data'), XDG_STATE_HOME=str(self.runtime / 'state'),
            XDG_RUNTIME_DIR=str(self.runtime / 'run'), GDK_BACKEND='wayland',
            XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='Husk:OwnOS',
            XDG_SESSION_DESKTOP='husk', WLR_BACKENDS='x11', WLR_RENDERER='pixman',
            WLR_X11_OUTPUTS='1', WLR_LIBINPUT_NO_DEVICES='1', WLR_NO_HARDWARE_CURSORS='1',
            XKB_DEFAULT_LAYOUT='us', LANG='C.UTF-8', LC_ALL='C.UTF-8', LANGUAGE='en',
            HUSK_LABWC_TELEMETRY=str(self.telemetry),
            PYTHONPATH=str(ROOT / 'scripts/labwc-test-observer') + ':' + str(ROOT / 'src'),
            PATH=str(ROOT / '.build/native') + ':/usr/bin:/bin:' + os.environ['PATH'])
        for variable in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_RUNTIME_DIR'):
            Path(self.environment[variable]).mkdir(parents=True, mode=0o700)
        self.config = Path(self.environment['XDG_CONFIG_HOME']) / 'ownos/labwc'
        self.config.mkdir(parents=True)
        # Frozen behavior of the original config: explicit mouse contexts with
        # no decoration actions and no <default/>. Preserve all other settings.
        tree = ET.parse(ROOT / 'config/labwc/rc.xml')
        mouse = tree.getroot().find('mouse')
        if mouse is None:
            raise AssertionError('Source Labwc mouse configuration is missing')
        for child in list(mouse):
            if child.tag == 'default' or child.get('name') in ('Close', 'Iconify', 'Maximize'):
                mouse.remove(child)
        tree.write(self.config / 'rc.xml', encoding='utf-8', xml_declaration=True)
        shutil.copyfile(self.config / 'rc.xml', self.artifacts / 'legacy-rc.xml')
        (self.config / 'autostart').write_text('#!/bin/sh\n# Test starts the real desktop separately.\n')
        (self.config / 'autostart').chmod(0o755)
        (self.config / 'environment').write_text('XKB_DEFAULT_LAYOUT=us\n')
        applications = Path(self.environment['XDG_DATA_HOME']) / 'applications'
        applications.mkdir(parents=True)
        (applications / 'husk-integration-terminal.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=Husk Integration Terminal\n'
            'Exec=foot --title=Husk-Integration-Terminal --app-id=husk-integration-terminal\n'
            'Icon=utilities-terminal\nTerminal=false\n')

    def command(self, argv, check=True, timeout=15):
        result = subprocess.run(argv, env=self.environment, text=True, capture_output=True, timeout=timeout)
        if check and result.returncode:
            raise AssertionError(f'{argv!r} failed ({result.returncode}): {result.stderr} {result.stdout}')
        return result.stdout

    def launch(self, argv, name):
        log = (self.artifacts / (name + '.log')).open('w')
        self.logs.append(log)
        process = subprocess.Popen(argv, env=self.environment, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        self.processes.append(process)
        return process

    def wait(self, description, predicate, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            if hasattr(self, 'compositor') and self.compositor.poll() is not None:
                raise AssertionError('Labwc exited; inspect labwc.log')
            time.sleep(0.1)
        raise AssertionError('Timed out: ' + description)

    def state(self, kind='desktop'):
        try:
            return json.loads((self.telemetry / (kind + '.json')).read_text())
        except (OSError, ValueError):
            return {}

    def record(self, name, **evidence):
        self.results.append(dict(test=name, passed=True, **evidence))
        print('PASS ' + name, flush=True)

    def screenshot(self, name):
        from PIL import Image
        path = self.artifacts / (name + '.png')
        self.command(['grim', str(path)])
        return Image.open(path).convert('RGB')

    def click(self, rect):
        if rect is None:
            raise AssertionError('The target has no mapped GTK allocation')
        x, y, width, height = rect
        with (self.artifacts / 'input-events.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(event='pointer-click', button=1,
                                         x=x + width // 2, y=y + height // 2,
                                         time=time.monotonic())) + '\n')
        self.command(['xdotool', 'mousemove', '--sync', '--window', self.output,
                      str(x + width // 2), str(y + height // 2), 'click', '1'])
        time.sleep(0.25)

    def key(self, key):
        with (self.artifacts / 'input-events.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(event='keyboard', key=key, time=time.monotonic())) + '\n')
        self.command(['xdotool', 'windowfocus', '--sync', self.output, 'key', '--clearmodifiers', key])

    def titlebar(self, name):
        # Exact project theme colors identify actual rendered decorations. Glyph
        # centers identify buttons without depending on version-specific sizes.
        self.command(['xdotool', 'mousemove', '--sync', '--window', self.output, '1200', '500'])
        image = self.screenshot(name)
        pixels = image.load()
        rows = []
        for y in range(image.height):
            xs = [x for x in range(image.width) if pixels[x, y] == (28, 48, 76)]
            if len(xs) >= 250:
                rows.append((y, min(xs), max(xs)))
        if not rows:
            raise AssertionError('No rendered OwnOS server titlebar found in ' + name)
        y0, y1 = rows[0][0], rows[-1][0]
        x0, x1 = min(row[1] for row in rows), max(row[2] for row in rows)
        columns = []
        for x in range(max(x0, x1 - 120), x1 + 1):
            if any(pixels[x, y] == (234, 241, 255) for y in range(y0, y1 + 1)):
                columns.append(x)
        groups = []
        for x in columns:
            if not groups or x > groups[-1][-1] + 1:
                groups.append([x])
            else:
                groups[-1].append(x)
        groups = [group for group in groups if len(group) >= 3]
        if len(groups) < 3:
            raise AssertionError('Could not identify three rendered titlebar glyphs in ' + name)
        buttons = {action: [(group[0] + group[-1]) // 2, (y0 + y1) // 2, 1, 1]
                   for action, group in zip(('minimize', 'maximize', 'close'), groups[-3:])}
        return dict(bounds=[x0, y0, x1 - x0 + 1, y1 - y0 + 1], buttons=buttons)

    def entries(self):
        return self.state().get('toplevels', [])

    def entry(self, identifier):
        return next((entry for entry in self.entries() if entry['id'] == identifier), None)

    def healthy(self):
        state = self.state()
        status = state.get('status', {})
        assert self.desktop.poll() is None, 'Desktop died after application action'
        assert status.get('backend') == 'wayland', state
        assert 'Wayland' in state.get('display', ''), state
        assert status.get('desktop_surfaces', 0) >= 1, status
        assert status.get('panel_mapped') and status.get('bridge_connected'), status
        output = self.command(['gdbus', 'call', '--session', '--dest', 'org.ownos.Desktop',
                               '--object-path', '/org/ownos/Desktop', '--method', 'org.ownos.Desktop.GetStatus'])
        assert 'wayland' in output, output
        return status

    def wallpaper(self, name):
        from PIL import Image, ImageChops, ImageOps, ImageStat
        image = self.screenshot(name)
        source = ROOT / 'data/wallpapers/husk-desert.jpg'
        expected = ImageOps.fit(Image.open(source).convert('RGB'), image.size, Image.Resampling.BILINEAR)
        # Exclude actual desktop icons and the taskbar; compare the painted image.
        region = (image.width // 3, 60, image.width - 30, image.height - 110)
        error = sum(ImageStat.Stat(ImageChops.difference(image.crop(region), expected.crop(region))).mean) / 3
        assert error < 12, f'Wallpaper differs from centered, aspect-preserving cover: MAE={error:.2f}'
        actual = self.state().get('wallpapers', [])
        assert actual and actual[0]['source'].endswith('husk-desert.jpg'), actual
        self.record(name, output=list(image.size), pixel_mean_absolute_error=round(error, 3),
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), telemetry=actual)

    def exercise(self, identifier, name, kind=None):
        before = self.titlebar(name + '-normal')
        self.click(before['buttons']['maximize'])
        if kind:
            self.wait(name + ' native GTK maximized state',
                      lambda: any(w.get('maximized') for w in self.state(kind).get('windows', [])))
        time.sleep(0.3)
        maximum = self.titlebar(name + '-maximized')
        assert maximum['bounds'][2] >= 1260, maximum
        assert maximum['bounds'][2] > before['bounds'][2] + 100, (before, maximum)
        self.click(maximum['buttons']['maximize'])
        self.wait(name + ' unmaximized', lambda: not kind or not any(
            w.get('maximized') for w in self.state(kind).get('windows', [])))
        time.sleep(0.3)
        restored = self.titlebar(name + '-restored')
        assert abs(restored['bounds'][2] - before['bounds'][2]) <= 4, restored
        self.click(restored['buttons']['minimize'])
        self.wait(name + ' minimized via pointer', lambda: self.entry(identifier)
                  and self.entry(identifier)['minimized'])
        self.screenshot(name + '-minimized')
        title = self.entry(identifier)['title']
        task = self.wait(name + ' taskbar button', lambda: next((button for button in
            self.state().get('panel_buttons', []) if button.get('tooltip') == title), None))
        self.click(task['rect'])
        self.wait(name + ' restored by taskbar click', lambda: self.entry(identifier)
                  and not self.entry(identifier)['minimized'] and self.entry(identifier)['active'])
        decoration = self.titlebar(name + '-taskbar-restored')
        self.click(decoration['buttons']['close'])
        self.wait(name + ' closed by X pointer click', lambda: self.entry(identifier) is None)
        if kind:
            self.wait(name + ' source application exited', lambda: self.state(kind).get('exited'))
        self.record(name + '-close-minimize-maximize', application=title,
                    before=before['bounds'], maximized=maximum['bounds'], desktop=self.healthy())

    def run(self):
        self.compositor = self.launch(['labwc', '-C', str(self.config), '--debug'], 'labwc')
        def wayland_socket():
            for path in Path(self.environment['XDG_RUNTIME_DIR']).glob('wayland-*'):
                if not path.name.endswith('.lock') and path.is_socket():
                    return path.name
        self.environment['WAYLAND_DISPLAY'] = self.wait('real Labwc Wayland socket', wayland_socket)
        def output_window():
            # The dedicated parent X server may lack both WM_CLASS and title
            # atoms. Read its actual client geometry rather than those hints.
            tree = self.command(['xwininfo', '-root', '-tree'])
            (self.artifacts / 'parent-window-tree.txt').write_text(tree)
            for identifier in output_candidates(tree):
                geometry = self.command(['xdotool', 'getwindowgeometry', '--shell', identifier], check=False)
                values = dict(line.split('=', 1) for line in geometry.splitlines() if '=' in line)
                if int(values.get('WIDTH', 0)) >= 320 and int(values.get('HEIGHT', 0)) >= 200:
                    title = self.command(['xdotool', 'getwindowname', identifier], check=False).strip()
                    (self.artifacts / 'parent-output-window.json').write_text(
                        json.dumps(dict(id=identifier, title=title, geometry=values), indent=2))
                    return identifier
            return None
        self.output = self.wait('nested Labwc X11 output', output_window)
        self.command(['xdotool', 'windowsize', '--sync', self.output, '1280', '800'])
        time.sleep(0.5)
        self.desktop = self.launch(['/usr/bin/husk-desktop'], 'desktop')
        self.wait('real desktop layer surfaces and native bridge', lambda:
                  self.state().get('status', {}).get('bridge_connected') and
                  self.state().get('status', {}).get('panel_mapped'))
        self.record('wayland-desktop-started', status=self.healthy())
        self.wallpaper('01-desktop-wallpaper')
        button = next(button for button in self.state()['panel_buttons']
                      if (button.get('tooltip') or '').startswith('Start'))
        self.click(button['rect'])
        self.wait('Start popup mapped after taskbar click', lambda: self.state().get('start_mapped'))
        self.screenshot('02-start-popup')
        self.click(self.state()['search'])
        self.command(['xdotool', 'type', '--clearmodifiers', '--delay', '30', 'Husk Integration Terminal'])
        row = self.wait('real launcher search result', lambda: next((row for row in
            self.state().get('rows', []) if row['name'] == 'Husk Integration Terminal'), None))
        self.click(row['rect'])
        terminal = self.wait('Foot launched from Start', lambda: next((entry for entry in self.entries()
            if entry['app_id'] == 'husk-integration-terminal'), None))
        self.wait('Start dismissed by launcher activation', lambda: not self.state().get('start_mapped'))
        self.record('start-pointer-search-launch', application=terminal)
        legacy = self.titlebar('03-legacy-before-X')
        self.click(legacy['buttons']['close'])
        time.sleep(0.8)
        assert self.entry(terminal['id']) is not None, 'Legacy config unexpectedly closed the application'
        self.screenshot('04-legacy-X-does-nothing')
        self.record('legacy-regression-reproduced', pointer=legacy['buttons']['close'],
                    application_survived=True, config='legacy-rc.xml')
        # Use the real source migration, with an actual saved legacy rc.xml.
        sys.path.insert(0, str(ROOT / 'src'))
        from ownos.session import prepare_session
        from ownos.config import ConfigStore
        store = ConfigStore(Path(self.environment['XDG_CONFIG_HOME']) / 'ownos/settings.json')
        settings = store.load(); settings['keymap'] = 'us'; store.save(settings)
        prepare_session(self.config, ROOT / 'config/labwc', store)
        shutil.copyfile(self.config / 'rc.xml', self.artifacts / 'migrated-rc.xml')
        os.kill(self.compositor.pid, signal.SIGHUP)
        time.sleep(0.8)
        fixed = self.titlebar('05-fixed-before-X')
        self.click(fixed['buttons']['close'])
        self.wait('same Foot closes after saved-config migration', lambda: self.entry(terminal['id']) is None)
        self.record('saved-config-migration-X-fixed', desktop=self.healthy())
        before = {entry['id'] for entry in self.entries()}
        self.key('super+Return')
        terminal = self.wait('Foot from real Super+Return', lambda: next((entry for entry in self.entries()
            if entry['id'] not in before and 'foot' in entry['app_id'].lower()), None))
        self.exercise(terminal['id'], '06-foot')
        for kind, shortcut in (('files', 'super+e'), ('control', 'super+i')):
            before = {entry['id'] for entry in self.entries()}
            self.key(shortcut)
            self.wait(kind + ' native Wayland GTK window', lambda: self.state(kind).get('windows'))
            assert 'Wayland' in self.state(kind).get('display', ''), self.state(kind)
            entry = self.wait(kind + ' in real taskbar bridge', lambda: next((entry for entry in self.entries()
                if entry['id'] not in before), None))
            self.exercise(entry['id'], '07-' + kind, kind)
        self.command(['xdotool', 'windowsize', '--sync', self.output, '1280', '960'])
        self.wait('wallpaper redraw after real output resize', lambda:
                  self.state().get('wallpapers', [{}])[0].get('size') == [1280, 960])
        time.sleep(0.3)
        self.wallpaper('08-wallpaper-after-output-resize')
        self.record('desktop-survives-all-app-controls', status=self.healthy())

    def close(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        for log in self.logs:
            log.close()
        shutil.copytree(self.telemetry, self.artifacts / 'telemetry', dirs_exist_ok=True)
        self.temporary.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, default=ROOT / '.build/system2-desktop')
    parser.add_argument('--inside-session', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.artifacts = args.artifacts.resolve()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    if not args.inside_session:
        for executable in ('dbus-run-session', 'xvfb-run', 'labwc', 'xdotool', 'xwininfo', 'grim', 'foot', 'gdbus', 'own-toplevel'):
            if not shutil.which(executable):
                # own-toplevel can be in the source build directory.
                if executable == 'own-toplevel' and (ROOT / '.build/native/own-toplevel').exists():
                    continue
                raise SystemExit('Missing dependency: ' + executable + '; see system2-desktop.yml')
        return subprocess.call(['dbus-run-session', '--', 'xvfb-run', '-a', '-s',
                                '-screen 0 1600x1000x24 -nolisten tcp', sys.executable,
                                str(Path(__file__).resolve()), '--inside-session',
                                '--artifacts', str(args.artifacts)])
    versions = subprocess.run(['dpkg-query', '-W', '-f=${Package} ${Version}\n',
                               'labwc', 'libwlroots*', 'foot', 'python3-gi', 'gir1.2-gtklayershell-0.1'],
                              capture_output=True, text=True)
    (args.artifacts / 'versions.txt').write_text(versions.stdout + versions.stderr)
    test = None
    failure = None
    try:
        test = DesktopTest(args.artifacts)
        test.run()
    except Exception:
        failure = traceback.format_exc()
        print(failure, file=sys.stderr, flush=True)
        if test and 'WAYLAND_DISPLAY' in test.environment:
            try:
                test.screenshot('FAILURE')
            except Exception:
                pass
    finally:
        summary = dict(passed=failure is None, tests=test.results if test else [], failure=failure,
                       environment='Ubuntu source install; real Labwc on wlroots X11 backend with Xvfb parent',
                       limitations='No ISO boot, GPU/KMS, physical monitor, audio, networking or installed Arch session acceptance is implied.')
        (args.artifacts / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        if test:
            test.close()
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())

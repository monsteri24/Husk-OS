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
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def active_decoration_bounds(image):
    """Locate the rendered active server decoration in the shipped theme."""
    pixels = image.load()
    rows = []
    for y in range(image.height):
        xs = [x for x in range(image.width) if pixels[x, y] == (28, 48, 76)]
        if len(xs) >= 150:
            rows.append((y, min(xs), max(xs)))
    if not rows:
        raise AssertionError('No rendered OwnOS active server decoration found')
    return [min(row[1] for row in rows), rows[0][0],
            max(row[2] for row in rows) - min(row[1] for row in rows) + 1,
            rows[-1][0] - rows[0][0] + 1]


def client_widget_rectangle(decoration, client_size, relative):
    """Place passive GTK allocations below the real one-pixel-bordered titlebar.

    Wayland clients cannot report their global placement. The actual Labwc
    decoration supplies it; GTK supplies only allocations within that client.
    Reject a mismatched window or an allocation outside its visible client.
    """
    if relative is None:
        raise AssertionError('The target has no mapped GTK allocation')
    left, top, width, height = decoration
    client_width, client_height = client_size
    x, y, widget_width, widget_height = relative
    if abs(width - client_width) > 8 or min(client_width, client_height) <= 0:
        raise AssertionError(f'Rendered decoration does not match GTK client: {decoration}, {client_size}')
    if (min(x, y) < 0 or min(widget_width, widget_height) <= 0
            or x + widget_width > client_width or y + widget_height > client_height):
        raise AssertionError(f'Target is outside the visible GTK client: {relative}, {client_size}')
    return [left + (width - client_width) // 2 + x,
            top + height + 1 + y, widget_width, widget_height]


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
        self.navigation_root = Path(self.environment['HOME']) / ('Husk navigation ' + secrets.token_hex(4))
        (self.navigation_root / 'Nested folder' / 'Keyboard target').mkdir(parents=True)
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

    def click(self, rect, button=1, count=1):
        if rect is None:
            raise AssertionError('The target has no mapped GTK allocation')
        assert button in (1, 3) and count in (1, 2), (button, count)
        x, y, width, height = rect
        with (self.artifacts / 'input-events.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(event='pointer-click', button=button, count=count,
                                         x=x + width // 2, y=y + height // 2,
                                         time=time.monotonic())) + '\n')
        # XTest preserves move/click order. --sync can wait forever when two
        # successive targets have the same center (for example nested rows).
        clicks = ['click', str(button)] if count == 1 else ['click', '--repeat', '2', '--delay', '90', str(button)]
        self.command(['xdotool', 'mousemove', '--window', self.output,
                      str(x + width // 2), str(y + height // 2), *clicks])
        time.sleep(0.25)

    def key(self, key):
        with (self.artifacts / 'input-events.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(event='keyboard', key=key, time=time.monotonic())) + '\n')
        self.command(['xdotool', 'windowfocus', '--sync', self.output, 'key', '--clearmodifiers', key])

    def key_event(self, action, key):
        assert action in ('keydown', 'keyup'), action
        with (self.artifacts / 'input-events.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(event=action, key=key, time=time.monotonic())) + '\n')
        self.command(['xdotool', 'windowfocus', '--sync', self.output, action, key])

    def type_text(self, text):
        with (self.artifacts / 'input-events.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(event='type', text=text, time=time.monotonic())) + '\n')
        self.command(['xdotool', 'type', '--clearmodifiers', '--delay', '15', '--', text])

    def pointer_event(self, action, rect=None):
        assert action in ('mousedown', 'mouseup', 'move'), action
        argv = ['xdotool']
        evidence = dict(event=action, button=1, time=time.monotonic())
        if rect is not None:
            x, y, width, height = rect
            evidence.update(x=x + width // 2, y=y + height // 2)
            argv += ['mousemove', '--window', self.output,
                     str(evidence['x']), str(evidence['y'])]
        if action != 'move':
            argv += [action, '1']
        with (self.artifacts / 'input-events.jsonl').open('a') as stream:
            stream.write(json.dumps(evidence) + '\n')
        self.command(argv)
        time.sleep(0.15)

    def window_rectangle(self, window, relative, name):
        image = self.screenshot(name)
        decoration = active_decoration_bounds(image)
        rectangle = client_widget_rectangle(decoration, window['size'], relative)
        (self.artifacts / (name + '-geometry.json')).write_text(json.dumps(dict(
            decoration=decoration, client=window, relative=relative, target=rectangle), indent=2) + '\n')
        return rectangle

    def native_window(self, kind, predicate=lambda window: True):
        return next((window for window in self.state(kind).get('windows', [])
                     if window.get('mapped') and predicate(window)), None)

    def wait_stable_window(self, kind, predicate, description):
        sequence, previous, samples = -1, None, 0
        def stable():
            nonlocal sequence, previous, samples
            state = self.state(kind)
            if state.get('sequence', 0) <= sequence:
                return None
            sequence = state['sequence']
            window = next((w for w in state.get('windows', []) if w.get('mapped') and predicate(w)),None)
            signature = json.dumps((window.get('id'),window.get('size'),window.get('buttons')),
                                   sort_keys=True) if window else None
            samples = samples+1 if signature is not None and signature == previous else 1
            previous = signature
            return window if window and samples >= 3 else None
        return self.wait(description,stable)

    def titlebar(self, name):
        # Exact project theme colors identify actual rendered decorations. Glyph
        # centers identify buttons without depending on version-specific sizes.
        self.command(['xdotool', 'mousemove', '--window', self.output, '1200', '500'])
        image = self.screenshot(name)
        pixels = image.load()
        x0, y0, width, height = active_decoration_bounds(image)
        x1, y1 = x0 + width - 1, y0 + height - 1
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

    def terminal_roundtrip(self, terminal):
        token = 'husk-foot-' + secrets.token_hex(16)
        destination = self.runtime / ('typed-command-' + secrets.token_hex(8) + '.txt')
        assert not destination.exists(), destination
        self.wait('Foot keyboard focus before command', lambda:
                  self.entry(terminal['id']) and self.entry(terminal['id'])['active'])
        command = "printf '%s\\n' " + shlex.quote(token) + ' > ' + shlex.quote(str(destination))
        self.type_text(command)
        self.key('Return')
        def written():
            try:
                return destination.read_text() == token + '\n'
            except OSError:
                return False
        self.wait('typed Foot shell command writes its exact unique content', written)
        shutil.copyfile(destination, self.artifacts / 'foot-command-roundtrip.txt')
        self.screenshot('06-foot-keyboard-roundtrip')
        self.record('foot-keyboard-command-roundtrip', application=terminal,
                    command=command, content=token + '\n', artifact='foot-command-roundtrip.txt')

    def desktop_context_menu(self):
        before = self.screenshot('desktop-before-context-menu')
        target = [before.width * 3 // 4, before.height // 3, 1, 1]
        expected = ['New Folder', 'New File', 'Paste', 'Refresh', 'Display Settings', 'Change Wallpaper', 'Personalize']
        def mapped():
            return next((menu for menu in self.state().get('desktop_menus', []) if menu.get('mapped')), None)
        def dismissed():
            menus = self.state().get('desktop_menus', [])
            return menus and all(not any(menu.get(key) for key in ('active', 'mapped', 'host_present', 'host_mapped'))
                                 for menu in menus)
        def open_menu():
            self.click(target, button=3)
            menu = self.wait('actual native desktop context menu and keyboard layer host map', mapped)
            assert menu['type'] == 'Menu' and menu['host_mapped'], menu
            assert menu['labels'] == expected, menu
            assert menu['background_keyboard_mode'] == 0 and menu['host_keyboard_mode'] == 1, menu
            return menu
        menu = open_menu()
        image = self.screenshot('desktop-native-context-menu')
        surface = (21, 30, 46)
        before_count = list(before.getdata()).count(surface)
        after_count = list(image.getdata()).count(surface)
        assert after_count > before_count + 1000, 'Mapped desktop menu has no visible dark native surface'
        self.key('Home')
        self.wait('desktop menu receives real keyboard Home', lambda: mapped() and mapped().get('selected') == 'New Folder')
        self.key('Down')
        self.wait('desktop menu navigates to New File with real Down', lambda: mapped() and mapped().get('selected') == 'New File')
        self.screenshot('desktop-context-menu-keyboard-selection')
        self.key('Escape')
        self.wait('Escape closes the native menu and releases its layer keyboard host', dismissed)
        # The server processes the popup/layer destruction asynchronously.
        # A fresh real motion and wl_pointer enter must precede another press;
        # a second XTest click at the unchanged location can otherwise vanish
        # into the old compositor grab even though GTK has destroyed it.
        self.pointer_event('move',[before.width//2,before.height-95,1,1])
        self.wait('compositor returns pointer focus to the actual desktop after Escape',lambda:
                  self.state().get('pointer_window_title') == 'Husk Desktop')
        self.screenshot('desktop-context-menu-escape-dismissed')
        open_menu()
        self.click([before.width // 2, before.height - 95, 1, 1])
        self.wait('outside pointer click closes the native menu and layer host', dismissed)
        self.screenshot('desktop-context-menu-dismissed')
        self.record('desktop-native-context-menu-keyboard-and-outside-click', labels=menu['labels'],
                    keyboard=['Home', 'Down', 'Escape'], outside_click=True,
                    visible_dark_pixels=after_count - before_count, status=self.healthy())

    def files_navigation(self):
        def current(path):
            return self.native_window('files', lambda window:
                window.get('files', {}).get('current') == str(path)
                and window['files'].get('location') == str(path)
                and all(row.get('rect') and row['rect'][2] >= 100 and row['rect'][3] >= 24
                        for row in window['files'].get('rows', [])))
        home = Path(self.environment['HOME'])
        window = self.wait('Files starts at the isolated home directory', lambda: current(home))
        steps = []
        for destination in (self.navigation_root, self.navigation_root / 'Nested folder'):
            row = next(row for row in window['files']['rows'] if row['path'] == str(destination))
            self.click(self.window_rectangle(window, row['rect'], 'files-row-' + str(len(steps))), count=2)
            window = self.wait('Files directory opens by real row pointer activation', lambda: current(destination))
            steps.append(dict(input='folder-row-pointer', current=window['files']['current']))
        up = next(button for button in window['buttons'] if button['label'] == 'Up')
        self.click(self.window_rectangle(window, up['rect'], 'files-up-button'))
        window = self.wait('Files Up returns to the real parent directory', lambda: current(self.navigation_root))
        steps.append(dict(input='Up-pointer', current=window['files']['current']))
        destination = self.navigation_root / 'Nested folder' / 'Keyboard target'
        self.click(self.window_rectangle(window, window['files']['location_rect'], 'files-location-entry'))
        self.key('ctrl+a')
        self.type_text(str(destination))
        self.key('Return')
        window = self.wait('Files location accepts a real typed path and Return', lambda: current(destination))
        steps.append(dict(input='location-keyboard-Return', current=window['files']['current']))
        button = next(button for button in window['buttons'] if button['label'] == 'Home')
        self.click(self.window_rectangle(window, button['rect'], 'files-home-button'))
        window = self.wait('Files Home returns to the isolated home directory', lambda: current(home))
        steps.append(dict(input='Home-pointer', current=window['files']['current']))
        self.screenshot('files-navigation-complete')
        self.record('files-real-folder-location-Home-Up-navigation', steps=steps,
                    title=window['title'], backend=self.state('files')['display'])

    def search_start(self, name):
        button = next(button for button in self.state()['panel_buttons']
                      if (button.get('tooltip') or '').startswith('Start'))
        self.click(button['rect'])
        self.wait('Start mapped for ' + name, lambda:
                  self.state().get('start_mapped') and self.state().get('start', [0, 0, 0, 0])[2] >= 400)
        self.click(self.state()['search'])
        if self.state().get('search_text') != name:
            self.key('ctrl+a')
            self.type_text(name)
        # Rewriting an unchanged query destroys/recreates rows immediately and
        # again in SearchEntry's delayed search-changed signal. Old telemetry
        # can already match that query while its input/layout is still pending.
        # Require three fresh matching snapshots of one actual row before use.
        sequence = self.state().get('sequence', 0)
        previous = None
        samples = 0
        def stable_result():
            nonlocal sequence, previous, samples
            state = self.state()
            if state.get('sequence', 0) <= sequence:
                return None
            sequence = state['sequence']
            row = next((row for row in state.get('rows', [])
                        if row['name'] == name and row.get('rect') and row['rect'][2] >= 200 and row['rect'][3] >= 24
                        and state.get('start_mapped') and state.get('search_text') == name), None)
            signature = (row.get('identity'), tuple(row['rect'])) if row else None
            samples = samples + 1 if signature is not None and signature == previous else 1
            previous = signature
            return row if row and samples >= 3 else None
        return self.wait('fresh stable Start search result for ' + name, stable_result)

    def confirmation(self, kind='desktop'):
        return self.native_window(kind, lambda window: bool(window.get('confirmation')))

    def firefox_confirmation(self):
        row = self.search_start('Firefox')
        self.click(row['rect'])
        window = self.wait('real missing-Firefox confirmation from Start', self.confirmation)
        assert window['confirmation']['primary_text'] == 'Install Firefox?', window
        assert window['confirmation']['cancel_focused'] and window['confirmation']['cancel_default'], window
        self.wait('Start hides before confirmation interaction', lambda: not self.state().get('start_mapped'))
        return window

    def installer_terminals(self):
        """Inspect real Foot processes; no installer or terminal is substituted."""
        terminals = []
        for process in Path('/proc').iterdir():
            if not process.name.isdigit():
                continue
            try:
                argv = process.joinpath('cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
                executable = str(process.joinpath('exe').resolve(strict=True))
            except (OSError, UnicodeError):
                continue
            if (argv and Path(argv[0]).name == 'foot' and '--hold' in argv
                    and argv[-3:] == ['-e', '/usr/bin/husk-install-app', 'firefox']):
                terminals.append(dict(pid=int(process.name), executable=executable, argv=argv))
        return terminals

    def assert_no_installer(self, before, description, delay=0.35):
        time.sleep(delay)
        unexpected = [entry for entry in self.entries()
                      if entry['id'] not in before and 'foot' in entry['app_id'].lower()]
        assert not unexpected, description + ': unexpected Foot window ' + repr(unexpected)
        assert not self.installer_terminals(), description + ': installer terminal started'
        assert not any(window.get('app_install') for window in self.state().get('windows', [])), (
            description + ': graphical installer started')

    def held_pointer_confirmation(self, release_over='confirm'):
        """A separate real GTK client maps the production dialog during a hold."""
        assert release_over in ('cancel', 'confirm'), release_over
        label = 'Cancel' if release_over == 'cancel' else 'OK'
        script = self.runtime / 'husk-labwc-confirm-client.py'
        result = self.runtime / ('held-pointer-' + label + '-result.json')
        script.write_text('''import json
from pathlib import Path
import sys
from ownos.ui.common import ConfirmationDialog, Gtk, GLib, require_display
require_display()
parent = Gtk.Window(title='Husk held-pointer confirmation client')
parent.set_default_size(620, 240)
parent.connect('destroy', lambda *_: Gtk.main_quit())
button = Gtk.Button(label='Hold pointer to open confirmation')
parent.add(button)
opened = False
def open_dialog():
    dialog = ConfirmationDialog(parent, 'Held pointer input regression',
                                'Only fresh deliberate button input may answer this test dialog.')
    dialog.show_all()
    response = dialog.run()
    Path(sys.argv[1]).write_text(json.dumps(dict(response=int(response),
        accepted=response == Gtk.ResponseType.OK)))
    dialog.destroy()
    parent.destroy()
    return False
def pressed(_button, event):
    global opened
    if event.button == 1 and not opened:
        opened = True
        GLib.timeout_add(100, open_dialog)
    return False
button.connect('button-press-event', pressed)
parent.show_all()
Gtk.main()
''')
        process = self.launch(['/usr/bin/python3', str(script), str(result)], 'held-pointer-' + label + '-client')
        def client_window():
            state = self.state('confirmation')
            if state.get('pid') != process.pid or state.get('exited'):
                return None
            return self.native_window('confirmation', lambda candidate: any(
                button['label'] == 'Hold pointer to open confirmation' for button in candidate['buttons']))
        window = self.wait('separate real held-pointer GTK client for ' + label, client_window)
        button = next(button for button in window['buttons']
                      if button['label'] == 'Hold pointer to open confirmation')
        rectangle = self.window_rectangle(window, button['rect'], 'held-pointer-' + label + '-open-button')
        self.pointer_event('mousedown', rectangle)
        try:
            dialog = self.wait('production confirmation maps while pointer remains held', lambda:
                               self.confirmation('confirmation'))
            target = self.window_rectangle(dialog, dialog['confirmation'][release_over], 'held-pointer-over-' + label)
            self.pointer_event('move', target)
        finally:
            self.pointer_event('mouseup')
        time.sleep(0.35)
        assert not result.exists(), 'A release inherited from another widget accepted or dismissed the dialog'
        dialog = self.confirmation('confirmation')
        assert dialog, 'Held-pointer dialog disappeared without a fresh press'
        self.screenshot('held-pointer-over-' + label + '-release-rejected')
        self.click(self.window_rectangle(dialog, dialog['confirmation']['cancel'],
                                         'held-pointer-over-' + label + '-fresh-Cancel'))
        self.wait('fresh Cancel closes held-pointer dialog', lambda: result.exists() and process.poll() is not None)
        response = json.loads(result.read_text())
        assert response == dict(response=-6, accepted=False), response
        self.record('confirmation-inherited-pointer-release-over-' + label + '-rejected', result=response,
                    client='separate real GTK client using unchanged production ConfirmationDialog')

    def deliberate_installer_confirmation(self, keyboard=False):
        dialog = self.firefox_confirmation()
        before = {entry['id'] for entry in self.entries()}
        if keyboard:
            self.key('Tab')
            self.wait('fresh keyboard focus moves from Cancel to OK', lambda:
                      self.confirmation() and self.confirmation()['confirmation']['confirm_focused'])
            self.key_event('keydown', 'space')
            try:
                self.assert_no_installer(before, 'OK key press without release', delay=0.2)
            finally:
                self.key_event('keyup', 'space')
            name = 'missing-app-deliberate-keyboard-OK-opens-native-installer'
        else:
            target = self.window_rectangle(dialog, dialog['confirmation']['confirm'], 'firefox-fresh-OK')
            self.pointer_event('mousedown', target)
            try:
                self.assert_no_installer(before, 'OK pointer press without release', delay=0.2)
            finally:
                self.pointer_event('mouseup')
            name = 'missing-app-deliberate-pointer-OK-opens-native-installer'
        def installer():
            return self.native_window('desktop',lambda window:
                window.get('app_install',{}).get('appid') == 'firefox')
        window = self.wait('deliberate OK creates the real native application installer',installer)
        self.wait('confirmation closes after deliberate OK', lambda: self.confirmation() is None)
        # This Ubuntu source runner has no Arch package manager. Real preflight
        # must report that failure graphically before requesting authorization.
        window = self.wait_stable_window('desktop',lambda candidate:
            candidate.get('app_install',{}).get('appid') == 'firefox' and
            candidate['app_install']['state'] == 'failed',
            'native preflight reports missing tools and its Close button finishes allocation')
        assert 'repository' in window['app_install']['status'].lower(), window
        assert not self.installer_terminals(), 'The graphical installer started a Foot password sequence'
        assert not any(entry['id'] not in before and 'foot' in entry['app_id'].lower()
                       for entry in self.entries()), 'A terminal opened after graphical confirmation'
        self.screenshot(name)
        self.record(name, application=window['app_install'], terminal_started=False,
                    installation='Not assessed: actual graphical preflight fails closed without Arch tools on Ubuntu.')
        close = next(button for button in window['buttons'] if button['label'] == 'Close')
        self.click(self.window_rectangle(window,close['rect'],name+'-close'))
        self.wait('native installer closes through its real Close button',lambda: installer() is None)

    def missing_app_confirmation(self):
        from ownos.app_install import app_installed
        from ownos.catalog import app_by_id
        assert not app_installed(app_by_id('firefox')), (
            'Missing-app acceptance requires no authoritative installed Firefox package record')
        dialog = self.firefox_confirmation()
        before = {entry['id'] for entry in self.entries()}
        self.key('Return')
        self.wait('default Return selects Cancel', lambda: self.confirmation() is None)
        self.assert_no_installer(before, 'default Return cancellation')
        self.record('missing-app-default-keyboard-Cancel', default='Cancel', installer_started=False)
        dialog = self.firefox_confirmation()
        before = {entry['id'] for entry in self.entries()}
        cancel = self.window_rectangle(dialog, dialog['confirmation']['cancel'], 'firefox-drag-Cancel')
        confirm = self.window_rectangle(dialog, dialog['confirmation']['confirm'], 'firefox-drag-OK')
        self.pointer_event('mousedown', cancel)
        try:
            self.pointer_event('move', confirm)
        finally:
            self.pointer_event('mouseup')
        self.assert_no_installer(before, 'Cancel press dragged to OK release')
        dialog = self.confirmation()
        assert dialog, 'Cross-button drag dismissed the confirmation'
        self.screenshot('firefox-cross-button-release-rejected')
        self.click(self.window_rectangle(dialog, dialog['confirmation']['cancel'], 'firefox-fresh-Cancel'))
        self.wait('fresh Cancel closes missing-app confirmation', lambda: self.confirmation() is None)
        self.assert_no_installer(before, 'fresh Cancel')
        self.record('missing-app-cross-button-drag-and-fresh-Cancel', installer_started=False,
                    sequence=['Cancel press', 'move to OK', 'OK release', 'fresh Cancel click'])
        self.held_pointer_confirmation('confirm')
        self.held_pointer_confirmation('cancel')
        self.deliberate_installer_confirmation()
        self.deliberate_installer_confirmation(keyboard=True)

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
            self.state().get('task_buttons', []) if button.get('tooltip') == title), None))
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

    def panel_window_states(self):
        destination = self.runtime / 'panel-client.json'
        client = self.launch([sys.executable, str(ROOT / 'scripts/labwc-panel-client.py'),
                              str(destination)], 'panel-client')
        def state():
            try:
                return json.loads(destination.read_text())
            except (OSError, ValueError):
                return {}
        entry = self.wait('real panel state client in the compositor bridge', lambda:
            next((entry for entry in self.entries() if entry['title'] == 'Husk Panel State Test'), None))
        identifier = entry['id']
        self.wait('panel client output identity from actual wl_output membership', lambda:
                  self.entry(identifier).get('outputs'))
        outputs = self.entry(identifier)['outputs']
        assert outputs[0]['name'] or outputs[0]['width'] > 0, outputs
        self.key('F10')
        self.wait('native maximize removes the reserved panel strip', lambda:
                  state().get('maximized') and self.entry(identifier).get('maximized') and
                  self.state().get('status', {}).get('panel_mode') == 'maximized' and
                  state().get('height', 0) >= outputs[0]['height'] - 40)
        image = self.screenshot('panel-maximized-transparent')
        panel = self.state()['panel']
        for point in [(20, image.height - 2), (20, panel[1] + 4)]:
            assert image.getpixel(point) == (36, 80, 74), (point, image.getpixel(point))
        clicks = len(state().get('clicks', []))
        self.click([20, image.height - 16, 1, 1])
        self.wait('a click through the transparent panel gap reaches the real maximized client', lambda:
                  len(state().get('clicks', [])) > clicks)
        start = next(button for button in self.state()['panel_buttons']
                     if (button.get('tooltip') or '').startswith('Start'))
        self.click(start['rect'])
        self.wait('centered Start remains clickable above the maximized client', lambda:
                  self.state().get('start_mapped'))
        self.click(start['rect'])
        self.wait('Start dismissed above the maximized client', lambda: not self.state().get('start_mapped'))
        self.record('panel-maximized-transparent-click-through-and-launcher', outputs=outputs,
                    panel=panel, native=state())
        self.click([20, image.height - 16, 1, 1])
        self.key('F11')
        self.wait('true fullscreen unmaps every panel icon', lambda:
                  state().get('fullscreen') and self.entry(identifier).get('fullscreen') and
                  not self.state().get('status', {}).get('panel_mapped') and
                  self.state().get('status', {}).get('panel_mode') == 'fullscreen' and
                  (state().get('width'), state().get('height')) == (image.width, image.height))
        image = self.screenshot('panel-fullscreen-no-icons')
        assert image.getcolors(maxcolors=2) == [(image.width * image.height, (36, 80, 74))], (
            'Fullscreen must contain only the native client canvas; panel/wallpaper pixels remain')
        self.key('F11')
        self.wait('exiting fullscreen restores the compact panel', lambda:
                  not state().get('fullscreen') and self.state().get('status', {}).get('panel_mapped') and
                  self.state().get('status', {}).get('panel_mode') == 'maximized')
        self.key('F10')
        self.wait('restoring the window restores the desktop panel reservation', lambda:
                  not state().get('maximized') and
                  self.state().get('status', {}).get('panel_mode') == 'desktop')
        self.screenshot('panel-restored-desktop')
        self.key('alt+F4')
        self.wait('panel test client closed by actual keyboard input', lambda:
                  client.poll() is not None and self.entry(identifier) is None)
        self.record('panel-true-fullscreen-hide-and-restore', native=state(), desktop=self.healthy())

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
        image = self.screenshot('desktop-normal-panel-background')
        probes = [(10,image.height-4),(300,image.height-4)]
        assert all(image.getpixel(point)[2]>image.getpixel(point)[0] and
                   image.getpixel(point)[2]>image.getpixel(point)[1] for point in probes), (
            'The normal desktop panel must paint its configured CSS background',
            [(point,image.getpixel(point)) for point in probes])
        self.record('desktop-normal-panel-background',pixels=[image.getpixel(point) for point in probes])
        self.desktop_context_menu()
        row = self.search_start('Husk Integration Terminal')
        self.screenshot('02-start-popup')
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
        self.terminal_roundtrip(terminal)
        self.exercise(terminal['id'], '06-foot')
        self.panel_window_states()
        for kind, shortcut in (('files', 'super+e'), ('control', 'super+i')):
            before = {entry['id'] for entry in self.entries()}
            self.key(shortcut)
            self.wait(kind + ' native Wayland GTK window', lambda: self.state(kind).get('windows'))
            assert 'Wayland' in self.state(kind).get('display', ''), self.state(kind)
            entry = self.wait(kind + ' in real taskbar bridge', lambda: next((entry for entry in self.entries()
                if entry['id'] not in before), None))
            if kind == 'files':
                self.files_navigation()
            self.exercise(entry['id'], '07-' + kind, kind)
        self.missing_app_confirmation()
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

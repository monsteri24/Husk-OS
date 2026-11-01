import contextlib
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from ownos.config import ConfigStore, defaults


ROOT = Path(__file__).resolve().parents[1]


class SessionTests(unittest.TestCase):
    def test_saved_input_applies_without_replacing_custom_session_files(self):
        from ownos.session import prepare_session
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / 'labwc'; directory.mkdir()
            custom = '#!/bin/sh\ncustom-panel &\n'
            (directory / 'autostart').write_text(custom)
            (directory / 'environment').write_text('CUSTOM=keep\nXKB_DEFAULT_LAYOUT=us\n')
            (directory / 'rc.xml').write_text(
                '<labwc_config><keyboard><keybind key="W-f">'
                '<action name="Execute" command="custom-files"/>'
                '</keybind></keyboard></labwc_config>')
            store = ConfigStore(root / 'settings.json')
            settings = defaults(); settings.update(keymap='de', pointer_speed=-0.65)
            store.save(settings)
            self.assertEqual(prepare_session(directory, ROOT / 'config/labwc', store), directory)
            config = ET.parse(directory / 'rc.xml')
            self.assertEqual(config.find('keyboard/keybind/action').get('command'), 'custom-files')
            self.assertEqual(config.find("libinput/device[@category='mouse']/pointerSpeed").text, '-0.65')
            self.assertEqual((directory / 'environment').read_text(), 'CUSTOM=keep\nXKB_DEFAULT_LAYOUT=de\nXKB_DEFAULT_VARIANT=\n')
            self.assertEqual((directory / 'autostart').read_text(), custom)

    def test_only_exact_stock_lock_binding_is_migrated(self):
        from ownos.session import migrate_lock_binding
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rc.xml'
            path.write_text('''<labwc_config><keyboard>
                <keybind key="W-l"><action name="Execute" command="swaylock -f -c 0b1321"/></keybind>
                <keybind key="W-l"><action name="Execute" command="swaylock -f -c 0b1321 --indicator"/></keybind>
                <keybind key="W-l" onRelease="yes"><action name="Execute" command="swaylock -f -c 0b1321"/></keybind>
                <keybind key="W-l"><action name="Execute" command="swaylock -f -c 0b1321"/><action name="Focus"/></keybind>
                <keybind key="W-k"><action name="Execute" command="swaylock -f -c 0b1321"/></keybind>
                </keyboard></labwc_config>''')
            self.assertTrue(migrate_lock_binding(path))
            actions = ET.parse(path).findall('keyboard/keybind/action')
            self.assertEqual([a.get('command') for a in actions], [
                'husk-lock', 'swaylock -f -c 0b1321 --indicator',
                'swaylock -f -c 0b1321', 'swaylock -f -c 0b1321', None,
                'swaylock -f -c 0b1321'])
            before = path.read_bytes()
            self.assertFalse(migrate_lock_binding(path))
            self.assertEqual(path.read_bytes(), before)

    def test_stock_autostart_updates_and_missing_files_are_installed(self):
        from ownos.session import LEGACY_AUTOSTART, prepare_session
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'labwc'; directory.mkdir()
            (directory / 'autostart').write_text(LEGACY_AUTOSTART)
            prepare_session(directory, ROOT / 'config/labwc')
            self.assertEqual((directory / 'autostart').read_bytes(), (ROOT / 'config/labwc/autostart').read_bytes())
            self.assertTrue(os.access(directory / 'autostart', os.X_OK))
            self.assertEqual(ET.parse(directory / 'rc.xml').find("keyboard/keybind[@key='W-l']/action").get('command'), 'husk-lock')

    def test_log_is_private_and_only_rotates_over_one_mebibyte(self):
        from ownos.session import LOG_LIMIT, open_session_log
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'ownos'
            with open_session_log(directory) as log:
                log.write('first\n')
            path = directory / 'session.log'
            path.chmod(0o666)
            with open_session_log(directory, rotate=False) as log:
                log.write('second\n')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            self.assertEqual(path.read_text(), 'first\nsecond\n')
            path.write_bytes(b'x' * LOG_LIMIT)
            with open_session_log(directory): pass
            self.assertFalse((directory / 'session.log.1').exists())
            path.write_bytes(b'x' * (LOG_LIMIT + 1))
            with open_session_log(directory, rotate=False): pass
            self.assertFalse((directory / 'session.log.1').exists())
            with open_session_log(directory) as log:
                log.write('new login\n')
            self.assertEqual((directory / 'session.log.1').stat().st_size, LOG_LIMIT + 1)
            self.assertEqual(path.read_text(), 'new login\n')
            self.assertEqual(stat.S_IMODE((directory / 'session.log.1').stat().st_mode), 0o600)

    def test_log_rejects_symlinks_without_touching_the_target(self):
        from ownos.session import open_session_log
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = root / 'ownos'; directory.mkdir()
            target = root / 'private'; target.write_text('keep'); target.chmod(0o640)
            (directory / 'session.log').symlink_to(target)
            with self.assertRaises((OSError, ValueError)):
                open_session_log(directory)
            self.assertEqual(target.read_text(), 'keep')
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)

    def test_start_prepares_before_exec_and_exports_wayland_environment(self):
        from ownos.session import start_session
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); config = root / 'labwc'
            settings = ConfigStore(root / 'config/ownos/settings.json')
            settings.save(dict(defaults(), keymap='gb', pointer_speed=0.4))
            environment = {'HOME': str(root), 'XDG_CONFIG_HOME': str(root / 'config'), 'WLR_RENDERER': 'gles2'}
            for address in ['', 'unix:path=/example/bus']:
                if address: environment['DBUS_SESSION_BUS_ADDRESS'] = address
                else: environment.pop('DBUS_SESSION_BUS_ADDRESS', None)
                with self.subTest(dbus=address), patch.dict(os.environ, environment, clear=True), \
                     patch('ownos.session.os.dup2') as duplicate, \
                     patch('ownos.session.os.execvpe') as execute:
                    def assert_prepared(program, command, child_environment):
                        self.assertEqual(ET.parse(config / 'rc.xml').find("libinput/device[@category='mouse']/pointerSpeed").text, '0.4')
                        self.assertIn('XKB_DEFAULT_LAYOUT=gb', (config / 'environment').read_text())
                    execute.side_effect = assert_prepared
                    self.assertEqual(start_session(config, ROOT / 'config/labwc', root / 'state'), 0)
                    program, command, exported = execute.call_args.args
                    self.assertEqual(command[-3:], ['/usr/bin/labwc', '-C', str(config)])
                    self.assertEqual(program, '/usr/bin/labwc' if address else '/usr/bin/dbus-run-session')
                    self.assertEqual(exported['GDK_BACKEND'], 'wayland')
                    self.assertEqual(exported['XDG_CURRENT_DESKTOP'], 'Husk:OwnOS')
                    self.assertEqual(exported['XDG_SESSION_DESKTOP'], 'husk')
                    self.assertEqual(exported['XDG_SESSION_TYPE'], 'wayland')
                    self.assertEqual(exported['WLR_RENDERER'], 'gles2')
                    self.assertEqual([call.args[1] for call in duplicate.call_args_list], [1, 2])

    def test_compositor_children_inherit_the_private_session_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = '''import subprocess, sys
from pathlib import Path
from ownos import session
session.prepare_session = lambda *_: Path(sys.argv[1])
session.session_renderer = lambda: 'pixman'
def compositor(program, command, environment):
    subprocess.run([sys.executable, '-c',
        "import sys; print('compositor child stdout'); print('compositor child stderr', file=sys.stderr)"],
        env=environment, check=True)
    raise SystemExit(0)
session.os.execvpe = compositor
session.start_session(state_dir=sys.argv[1])
'''
            environment = os.environ.copy(); environment['PYTHONPATH'] = str(ROOT / 'src')
            result = subprocess.run([sys.executable, '-c', script, tmp], env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, '')
            content = (Path(tmp) / 'session.log').read_text()
            self.assertIn('compositor child stdout', content)
            self.assertIn('compositor child stderr', content)

    def test_desktop_failure_opens_one_logged_recovery_terminal(self):
        from ownos.session import start_desktop
        with tempfile.TemporaryDirectory() as tmp:
            for failed in [23, OSError('desktop missing')]:
                with self.subTest(failed=failed), patch('ownos.session.subprocess.call', side_effect=[failed, 0]) as run:
                    self.assertEqual(start_desktop(Path(tmp)), failed if isinstance(failed, int) else 1)
                    self.assertEqual(run.call_count, 2)
                    self.assertEqual(run.call_args_list[0].args[0], ['/usr/bin/husk-desktop'])
                    self.assertEqual(run.call_args_list[1].args[0][0], '/usr/bin/foot')
                    self.assertEqual(run.call_args_list[0].kwargs['env']['GDK_BACKEND'], 'wayland')
                    self.assertEqual(run.call_args_list[0].kwargs['stdout'].name, run.call_args_list[1].kwargs['stdout'].name)
            self.assertIn('recovery terminal', (Path(tmp) / 'session.log').read_text())

    def test_normal_desktop_exit_does_not_open_a_terminal(self):
        from ownos.session import start_desktop
        with tempfile.TemporaryDirectory() as tmp, patch('ownos.session.subprocess.call', return_value=0) as run:
            self.assertEqual(start_desktop(Path(tmp)), 0)
            run.assert_called_once()

    def test_all_live_lock_requests_are_refused_before_swaylock(self):
        from ownos.session import lock_session
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / 'archiso'; live.mkdir()
            with patch('ownos.session.subprocess.call') as run, contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(lock_session(live), 1)
                run.assert_not_called()
                self.assertEqual(errors.getvalue(),
                                 'The live session cannot be locked because the live user has no password.\n')
            with patch('ownos.session.subprocess.call', return_value=0) as run:
                self.assertEqual(lock_session(Path(tmp) / 'installed'), 0)
                run.assert_called_once_with(['/usr/bin/swaylock', '-f', '-c', '0b1321'])

    def test_helper_aliases_dispatch_to_packaged_functions(self):
        from ownos import cli
        for suffix, function in [('session-start', 'start_session'), ('desktop-start', 'start_desktop'), ('lock', 'lock_session')]:
            for prefix in ['husk', 'own']:
                with self.subTest(command=prefix + '-' + suffix), patch('sys.argv', [prefix + '-' + suffix]), \
                     patch('ownos.session.' + function, return_value=17) as helper:
                    self.assertEqual(cli.main(), 17)
                    helper.assert_called_once_with()


if __name__ == '__main__': unittest.main()

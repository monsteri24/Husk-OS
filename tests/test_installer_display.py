"""Private display credentials for the authenticated graphical installer."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class InstallerDisplayTests(unittest.TestCase):
    def setUp(self):
        from ownos import installer_display
        self.module = installer_display
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.runtime = Path(self.temporary.name)
        self.runtime.chmod(0o700)
        self.environment = dict(DISPLAY=':2', XDG_RUNTIME_DIR=str(self.runtime),
                                XAUTHORITY='/session/existing-authority', LANG='C')

    def generate(self, argv, **kwargs):
        self.assertEqual(argv[0], '/usr/bin/xauth')
        self.assertEqual(argv[3:], ['generate', ':2', '.', 'trusted', 'timeout', '120'])
        self.assertEqual(kwargs['env']['XAUTHORITY'], '/session/existing-authority')
        self.assertEqual(kwargs['env']['LANG'], 'C.UTF-8')
        self.assertEqual(kwargs['env']['LC_ALL'], 'C.UTF-8')
        self.assertTrue(kwargs['check'])
        self.assertTrue(kwargs['capture_output'])
        self.assertLessEqual(kwargs['timeout'], 20)
        path = Path(argv[2])
        self.assertEqual(path.parent.parent, self.runtime)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        path.write_bytes(b'private-display-fixture')
        path.chmod(0o600)
        return subprocess.CompletedProcess(argv, 0, '', '')

    def test_private_credentials_are_passed_only_by_filename_and_cleaned_after_exit(self):
        original = self.environment.copy()
        with patch.object(self.module.subprocess, 'run', side_effect=self.generate) as generate:
            with self.module.installer_display_environment(self.environment) as environment:
                authority = Path(environment['XAUTHORITY'])
                self.assertTrue(authority.is_file())
                self.assertEqual(stat.S_IMODE(authority.stat().st_mode), 0o600)
                self.assertNotIn('private-display-fixture', repr(generate.call_args))
            self.assertFalse(authority.parent.exists())
        self.assertEqual(self.environment, original)

    def test_credentials_are_cleaned_when_authorization_or_the_installer_raises(self):
        with patch.object(self.module.subprocess, 'run', side_effect=self.generate):
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                with self.module.installer_display_environment(self.environment) as environment:
                    authority = Path(environment['XAUTHORITY'])
                    raise RuntimeError('cancelled')
        self.assertFalse(authority.parent.exists())

    def test_remote_displays_and_nonprivate_or_linked_runtime_directories_are_refused(self):
        linked = self.runtime / 'linked'; linked.symlink_to(self.runtime, target_is_directory=True)
        cases = [dict(self.environment, DISPLAY='remote.example:0'),
                 dict(self.environment, DISPLAY=''),
                 dict(self.environment, XDG_RUNTIME_DIR=str(linked))]
        with patch.object(self.module.subprocess, 'run') as generate:
            for environment in cases:
                with self.subTest(environment=environment), self.assertRaises(self.module.DisplayAuthorizationError):
                    with self.module.installer_display_environment(environment): pass
            self.runtime.chmod(0o755)
            with self.assertRaises(self.module.DisplayAuthorizationError):
                with self.module.installer_display_environment(self.environment): pass
            self.assertFalse(generate.called)

    def test_generation_failure_is_secret_free_and_removes_temporary_files(self):
        def fail(argv, **kwargs):
            self.generate(argv, **kwargs)
            raise subprocess.CalledProcessError(1, argv, stderr='private-display-fixture')
        with patch.object(self.module.subprocess, 'run', side_effect=fail):
            with self.assertRaises(self.module.DisplayAuthorizationError) as failure:
                with self.module.installer_display_environment(self.environment): pass
        self.assertNotIn('private-display-fixture', str(failure.exception))
        self.assertEqual(list(self.runtime.iterdir()), [])

    def test_nonprivate_and_linked_credential_files_are_refused_and_removed(self):
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / 'preserved'; target.write_bytes(b'preserve-existing-file'); target.chmod(0o600)
            for kind in ('nonprivate', 'symlink', 'hardlink'):
                def corrupt(argv, **kwargs):
                    result = self.generate(argv, **kwargs)
                    path = Path(argv[2])
                    if kind == 'nonprivate': path.chmod(0o644)
                    else:
                        path.unlink()
                        if kind == 'symlink': path.symlink_to(target)
                        else: os.link(target, path)
                    return result
                with self.subTest(kind=kind), patch.object(self.module.subprocess, 'run', side_effect=corrupt):
                    with self.assertRaises(self.module.DisplayAuthorizationError):
                        with self.module.installer_display_environment(self.environment): pass
                self.assertEqual(list(self.runtime.iterdir()), [])
                self.assertEqual(target.read_bytes(), b'preserve-existing-file')

    @unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1', 'Needs the real GTK/X11 test session')
    def test_real_xsecurity_credential_opens_an_actual_gtk_window(self):
        import sys
        environment = dict(os.environ, XDG_RUNTIME_DIR=str(self.runtime), GDK_BACKEND='x11')
        code = '''import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
window=Gtk.Window(title='Husk installer display authorization test')
window.show_all()
while Gtk.events_pending(): Gtk.main_iteration_do(False)
assert window.get_mapped(), 'The real GTK window did not map'
window.destroy()
'''
        with self.module.installer_display_environment(environment) as authorized:
            subprocess.run([sys.executable, '-c', code], env=authorized,
                           capture_output=True, text=True, check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()

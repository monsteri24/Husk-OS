"""Exercise the packaged first-login default with real systemd-tmpfiles."""
import configparser
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SddmDefaultsTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which('systemd-tmpfiles'):
            self.skipTest('systemd-tmpfiles unavailable')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        directory = Path(self.temporary.name)
        (directory / 'ownos').symlink_to(ROOT, target_is_directory=True)
        self.root = directory / 'dest'
        staged = subprocess.run(['bash', '--noprofile', '--norc', '-ec',
            'source "$1"; pkgname=ownos-branding; package_ownos-branding',
            'package-test', str(ROOT / 'packaging/ownos/PKGBUILD')],
            cwd=directory, env=dict(os.environ, pkgdir=str(self.root)),
            capture_output=True, text=True, timeout=15)
        self.assertEqual(staged.returncode, 0, staged.stderr)
        rule = self.root / 'usr/lib/tmpfiles.d/ownos-sddm.conf'
        self.assertTrue(rule.is_file(), 'Branding package must ship the first-login default')
        etc = self.root / 'etc'
        # Keep the fake SDDM identity inside the test user's UID/GID mapping.
        self.identity = (os.geteuid(), os.getegid())
        uid, gid = self.identity
        (etc / 'passwd').write_text(f'root:x:0:0:root:/root:/bin/sh\nsddm:x:{uid}:{gid}:SDDM:/var/lib/sddm:/usr/bin/nologin\n')
        (etc / 'group').write_text(f'root:x:0:\nsddm:x:{gid}:\n')
        self.state = self.root / 'var/lib/sddm/state.conf'

    def create(self):
        result = subprocess.run(['systemd-tmpfiles', '--root=' + str(self.root),
            '--create', '--prefix=/var/lib/sddm'], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_first_login_selects_husk_without_enabling_autologin(self):
        self.create()
        state = configparser.ConfigParser()
        state.read(self.state)
        # Session::setTo canonicalizes the directory; SessionModel compares its
        # absolute fileName() with stateConfig.Last.Session, not its basename.
        self.assertEqual(state['Last']['Session'], '/usr/share/wayland-sessions/ownos-wayland.desktop')
        self.assertNotIn('User', state['Last'])
        self.assertNotIn('Autologin', state)
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o600)
        self.assertEqual((self.state.stat().st_uid, self.state.stat().st_gid), self.identity)

    def test_subsequent_boots_preserve_the_users_remembered_session(self):
        self.state.parent.mkdir(parents=True)
        previous = b'[Last]\nUser=remembered\nSession=/usr/share/wayland-sessions/labwc.desktop\n'
        self.state.write_bytes(previous)
        self.create()
        self.create()
        self.assertEqual(self.state.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()

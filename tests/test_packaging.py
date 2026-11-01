import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_live_package_keeps_calamare_optional(self):
        result=subprocess.run(['bash','--noprofile','--norc','-c',
            'source "$1"; install() { :; }; cp() { :; }; package_ownos-live; printf "%s\\n" "${depends[@]}"',
            'dependency-test',str(ROOT/'packaging/ownos/PKGBUILD')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('calamares',result.stdout.splitlines())
        self.assertIn('ownos-desktop',result.stdout.splitlines())

    def test_husk_core_aliases_are_installed_with_legacy_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); (path / 'ownos').symlink_to(ROOT, target_is_directory=True)
            dest = path / 'dest'; env = os.environ.copy(); env['pkgdir'] = str(dest)
            result = subprocess.run(['bash','--noprofile','--norc','-c',
                'source "$1"; pkgname=ownos-core; package_ownos-core', 'package-test',
                str(ROOT / 'packaging/ownos/PKGBUILD')], cwd=path, env=env, capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            for name in ['own-game','own-install-app','husk-game','husk-install-app','husk-status','husk-live-smoke',
                         'own-session-renderer','husk-session-renderer','own-session-start','husk-session-start',
                         'own-desktop-start','husk-desktop-start','own-lock','husk-lock']:
                with self.subTest(command=name): self.assertTrue((dest / 'usr/bin' / name).is_file())
            command = ('import sys; sys.path.insert(0, sys.argv[1]); '
                       'from ownos import cli, session; '
                       'setattr(session, sys.argv[3], lambda: 17); '
                       'sys.argv = [sys.argv[2]]; raise SystemExit(cli.main())')
            for alias, function in [('husk-session-start','start_session'),
                                    ('husk-desktop-start','start_desktop'), ('husk-lock','lock_session')]:
                with self.subTest(dispatch=alias):
                    result = subprocess.run(['python3', '-I', '-c', command, str(dest / 'usr/lib/ownos'), alias, function],
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 17, result.stderr)

    def test_system2_core_does_not_ship_postponed_finnish_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); (path / 'ownos').symlink_to(ROOT, target_is_directory=True)
            dest = path / 'dest'; env = dict(os.environ, pkgdir=str(dest))
            result = subprocess.run(['bash', '--noprofile', '--norc', '-ec',
                'source "$1"; pkgname=ownos-core; package_ownos-core', 'package-test',
                str(ROOT / 'packaging/ownos/PKGBUILD')], cwd=path, env=env,
                capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((dest / 'usr/lib/ownos/ownos/i18n.py').is_file())
            self.assertEqual(list(dest.rglob('huskos.mo')), [])
            self.assertTrue((ROOT / 'locale/fi/LC_MESSAGES/huskos.po').is_file())

    def test_packaged_session_uses_installed_helpers_and_explicit_tryexec(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); source = path / 'ownos'; source.mkdir()
            for name in ('bin', 'src', 'data', 'config', 'LICENSE'):
                (source / name).symlink_to(ROOT / name)
            native = source / '.build/native'; native.mkdir(parents=True)
            (native / 'own-toplevel').write_text('#!/bin/sh\nexit 0\n')
            dest = path / 'dest'; env = os.environ.copy(); env['pkgdir'] = str(dest)
            result = subprocess.run(['bash', '--noprofile', '--norc', '-ec',
                'source "$1"; pkgname=ownos-core; package_ownos-core; pkgname=ownos-desktop; package_ownos-desktop',
                'package-test', str(ROOT / 'packaging/ownos/PKGBUILD')], cwd=path, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((dest / 'usr/bin/husk-session').readlink(), Path('own-session'))
            self.assertIn('exec /usr/bin/husk-session-start', (dest / 'usr/bin/husk-session').read_text())
            desktop = (dest / 'usr/share/wayland-sessions/ownos-wayland.desktop').read_text()
            self.assertIn('Exec=/usr/bin/husk-session\n', desktop)
            self.assertIn('TryExec=/usr/bin/husk-session\n', desktop)
            self.assertIn('/usr/bin/husk-desktop-start &', (dest / 'etc/ownos/labwc/autostart').read_text())
            self.assertIn("'/usr/bin/husk-lock'", (dest / 'etc/ownos/labwc/autostart').read_text())
            self.assertTrue(os.access(dest / 'etc/ownos/labwc/autostart', os.X_OK))

    def test_staged_core_is_importable_in_python_isolated_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); (path / 'ownos').symlink_to(ROOT, target_is_directory=True)
            dest = path / 'dest'
            env = os.environ.copy(); env['pkgdir'] = str(dest)
            result = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                'source "$1"; pkgname=ownos-core; package_ownos-core', 'package-test',
                str(ROOT / 'packaging/ownos/PKGBUILD')], cwd=path, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            empty=path/'without-game-tools';empty.mkdir()
            command = ('import sys; sys.path.insert(0, sys.argv[1]); from ownos.config import defaults; '
                       'from ownos.gaming import game_command; assert defaults()["gaming_mode"] is False; '
                       'assert game_command(["/usr/bin/test-game"],defaults()) == ["/usr/bin/test-game"]')
            result = subprocess.run([sys.executable, '-I', '-c', command, str(dest / 'usr/lib/ownos')],
                                    env=dict(os.environ,PATH=str(empty)),capture_output=True,text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((dest / 'usr/bin/own-game').is_file())


if __name__ == '__main__': unittest.main()

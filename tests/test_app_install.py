import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from ownos import cli
from ownos.catalog import FLATHUB_REPOFILE


class OptionalAppInstallTests(unittest.TestCase):
    def test_existing_flathub_with_disabled_signatures_is_rejected_before_any_change(self):
        for options in ('no-gpg-verify', 'user,no-gpg-verify', 'user, no-gpg-verify,subset=verified'):
            with self.subTest(options=options), \
                    patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(
                        stdout='flathub\thttps://dl.flathub.org/repo/\t' + options + '\n')) as query, \
                    patch('ownos.cli.subprocess.call') as execute:
                with self.assertRaisesRegex(ValueError, 'GPG verification disabled'):
                    cli.install_app('heroic')
                execute.assert_not_called()
                query.assert_called_once_with(
                    ['/usr/bin/flatpak', 'remotes', '--user', '--show-disabled', '--columns=name,url,options'],
                    capture_output=True, text=True, check=True)

    def test_unexpected_or_missing_flathub_url_is_rejected_before_any_change(self):
        for remote in ('flathub\thttps://example.invalid/repo/\tuser\n', 'flathub\n'):
            with self.subTest(remote=remote), \
                    patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(stdout=remote)), \
                    patch('ownos.cli.subprocess.call') as execute:
                with self.assertRaisesRegex(ValueError, 'unexpected URL'):
                    cli.install_app('heroic')
                execute.assert_not_called()

    def test_trusted_flathub_keeps_user_confirmation_and_signed_repo_defaults(self):
        for remote in ('flathub\thttps://dl.flathub.org/repo/\tuser\n',
                       'flathub\thttps://dl.flathub.org/repo\t\n',
                       'flathub\thttps://dl.flathub.org/repo/\tsubset=no-gpg-verify-label\n',
                       'other\thttps://example.invalid/repo/\tno-gpg-verify\n'):
            with self.subTest(remote=remote), \
                    patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(stdout=remote)), \
                    patch('ownos.cli.subprocess.call', return_value=0) as execute:
                self.assertEqual(cli.install_app('heroic'), 0)
                self.assertEqual(execute.call_args_list, [
                    call(['/usr/bin/flatpak', 'remote-add', '--user', '--if-not-exists',
                          'flathub', FLATHUB_REPOFILE]),
                    call(['/usr/bin/flatpak', 'install', '--user', 'flathub', 'com.heroicgameslauncher.hgl']),
                ])
                self.assertTrue(FLATHUB_REPOFILE.startswith('https://flathub.org/'))

    def test_failed_remote_inspection_cannot_start_installation(self):
        with patch('ownos.cli.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'flatpak')), \
                patch('ownos.cli.subprocess.call') as execute:
            with self.assertRaises(subprocess.CalledProcessError):
                cli.install_app('heroic')
            execute.assert_not_called()

    def test_fresh_install_stops_if_adding_the_official_remote_fails(self):
        with patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(stdout='')), \
                patch('ownos.cli.subprocess.call', return_value=7) as execute:
            self.assertEqual(cli.install_app('heroic'), 7)
            execute.assert_called_once_with(
                ['/usr/bin/flatpak', 'remote-add', '--user', '--if-not-exists', 'flathub', FLATHUB_REPOFILE])


if __name__ == '__main__':
    unittest.main()

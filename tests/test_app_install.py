import contextlib
import io
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from ownos import cli
from ownos.catalog import FLATHUB_REPOFILE


class OptionalAppInstallTests(unittest.TestCase):
    def test_zero_native_transaction_exit_does_not_report_an_absent_package_as_installed(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch('ownos.cli.subprocess.call', return_value=0) as execute, \
                patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(returncode=1)) as query, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertNotEqual(cli.install_app('firefox'), 0)
        execute.assert_called_once_with(
            ['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'install', 'firefox'])
        query.assert_called_once_with(['/usr/bin/pacman', '-Q', '--', 'firefox'],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      timeout=8, check=False)
        self.assertIn('not verified', errors.getvalue())
        self.assertNotIn('is installed (verified)', output.getvalue())

    def test_native_authorization_denial_and_transaction_errors_keep_their_status(self):
        for status in (126, 127, 23):
            with self.subTest(status=status), \
                    patch('ownos.cli.subprocess.call', return_value=status) as execute, \
                    patch('ownos.cli.subprocess.run') as query, \
                    contextlib.redirect_stdout(io.StringIO()) as output, \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(cli.install_app('firefox'), status)
                self.assertIn(str(status), errors.getvalue())
                self.assertNotIn('is installed (verified)', output.getvalue())
                query.assert_not_called()
                execute.assert_called_once()

    def test_native_success_requires_the_curated_package_record_and_does_not_launch(self):
        with patch('ownos.cli.subprocess.call', return_value=0) as execute, \
                patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(returncode=0)), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.install_app('firefox'), 0)
        execute.assert_called_once_with(
            ['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'install', 'firefox'])
        self.assertIn('Firefox is installed (verified)', output.getvalue())
        self.assertIn('Select it again', output.getvalue())

    def test_failed_or_timed_out_installed_state_query_cannot_report_success(self):
        for failure in (FileNotFoundError('pacman'), subprocess.TimeoutExpired('pacman', 8)):
            with self.subTest(failure=failure), \
                    patch('ownos.cli.subprocess.call', return_value=0), \
                    patch('ownos.cli.subprocess.run', side_effect=failure), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertNotEqual(cli.install_app('firefox'), 0)
                self.assertIn('not verified', errors.getvalue())

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
                    capture_output=True, text=True, check=True, timeout=8)

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
                    patch('ownos.cli.subprocess.run', side_effect=[SimpleNamespace(stdout=remote),
                                                                  SimpleNamespace(returncode=0)]) as query, \
                    patch('ownos.cli.subprocess.call', return_value=0) as execute:
                self.assertEqual(cli.install_app('heroic'), 0)
                self.assertEqual(execute.call_args_list, [
                    call(['/usr/bin/flatpak', 'remote-add', '--user', '--if-not-exists',
                          'flathub', FLATHUB_REPOFILE]),
                    call(['/usr/bin/flatpak', 'install', '--user', 'flathub', 'com.heroicgameslauncher.hgl']),
                ])
                self.assertTrue(FLATHUB_REPOFILE.startswith('https://flathub.org/'))
                self.assertEqual(query.call_args_list[-1], call(
                    ['/usr/bin/flatpak', 'info', '--user', 'com.heroicgameslauncher.hgl'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=8, check=False))

    def test_zero_flatpak_transaction_exit_does_not_report_an_absent_user_app_as_installed(self):
        with patch('ownos.cli.subprocess.run', side_effect=[SimpleNamespace(stdout=''),
                                                          SimpleNamespace(returncode=1)]), \
                patch('ownos.cli.subprocess.call', return_value=0), \
                contextlib.redirect_stdout(io.StringIO()) as output, \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertNotEqual(cli.install_app('heroic'), 0)
        self.assertIn('not verified', errors.getvalue())
        self.assertNotIn('is installed (verified)', output.getvalue())

    def test_flatpak_install_failure_is_reported_without_running_a_state_query(self):
        with patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(stdout='')) as query, \
                patch('ownos.cli.subprocess.call', side_effect=[0, 19]), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(cli.install_app('heroic'), 19)
        self.assertEqual(query.call_count, 1)
        self.assertIn('19', errors.getvalue())

    def test_failed_remote_inspection_cannot_start_installation(self):
        failure = subprocess.CalledProcessError(9, 'flatpak', stderr='Remote inspection failed: test diagnostic')
        with patch('ownos.cli.subprocess.run', side_effect=failure), \
                patch('ownos.cli.subprocess.call') as execute, \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(cli.install_app('heroic'), 9)
            execute.assert_not_called()
        self.assertIn('Remote inspection failed: test diagnostic', errors.getvalue())
        self.assertIn('exit status 9', errors.getvalue())

    def test_remote_inspection_timeout_is_a_visible_failure_before_any_change(self):
        with patch('ownos.cli.subprocess.run', side_effect=subprocess.TimeoutExpired('flatpak', 8)), \
                patch('ownos.cli.subprocess.call') as execute, \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            try:
                self.assertEqual(cli.install_app('heroic'), 1)
            except subprocess.TimeoutExpired:
                self.fail('Remote inspection timeout must become a visible transaction failure')
        execute.assert_not_called()
        self.assertIn('timed out', errors.getvalue())
        self.assertIn('exit status 1', errors.getvalue())

    def test_missing_transaction_program_has_a_visible_failure_result(self):
        with patch('ownos.cli.subprocess.call', side_effect=FileNotFoundError('pkexec is missing')), \
                patch('ownos.cli.subprocess.run') as query, \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(cli.install_app('firefox'), 1)
        self.assertIn('pkexec is missing', errors.getvalue())
        self.assertIn('exit status 1', errors.getvalue())
        query.assert_not_called()

    def test_live_native_install_sets_a_password_interactively_before_pkexec(self):
        user = SimpleNamespace(pw_name='live')
        results = [SimpleNamespace(returncode=0, stdout='live NP 2026-10-16 0 99999 7 -1\n'),
                   SimpleNamespace(returncode=0, stdout='live P 2026-10-16 0 99999 7 -1\n'),
                   SimpleNamespace(returncode=0)]
        with patch('pathlib.Path.is_dir', return_value=True), \
                patch('pwd.getpwuid', return_value=user), \
                patch('os.getuid', return_value=1000), \
                patch('ownos.cli.subprocess.run', side_effect=results) as query, \
                patch('ownos.cli.subprocess.call', return_value=0) as execute, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.install_app('firefox'), 0)
        self.assertEqual(execute.call_args_list, [call(['/usr/bin/passwd']),
            call(['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'install', 'firefox'])])
        self.assertEqual(query.call_args_list[:2], [call(
            ['/usr/bin/passwd', '-S', 'live'], capture_output=True, text=True, check=True, timeout=8)] * 2)
        self.assertIn('temporary Live administrator password', output.getvalue())

    def test_cancelled_live_password_change_stops_before_pkexec(self):
        with patch('pathlib.Path.is_dir', return_value=True), \
                patch('pwd.getpwuid', return_value=SimpleNamespace(pw_name='live')), \
                patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(
                    returncode=0, stdout='live NP 2026-10-16 0 99999 7 -1\n')) as query, \
                patch('ownos.cli.subprocess.call', return_value=10) as execute, \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(cli.install_app('firefox'), 10)
        execute.assert_called_once_with(['/usr/bin/passwd'])
        self.assertEqual(query.call_count, 1)
        self.assertIn('exit status 10', errors.getvalue())

    def test_live_password_setup_never_treats_unchanged_empty_or_locked_state_as_usable(self):
        for record in ('live NP 2026-10-16 0 99999 7 -1\n', 'live L 2026-10-16 0 99999 7 -1\n',
                       'other P 2026-10-16 0 99999 7 -1\n', ''):
            with self.subTest(record=record), \
                    patch('pathlib.Path.is_dir', return_value=True), \
                    patch('pwd.getpwuid', return_value=SimpleNamespace(pw_name='live')), \
                    patch('ownos.cli.subprocess.run', side_effect=[SimpleNamespace(
                        returncode=0, stdout='live NP 2026-10-16 0 99999 7 -1\n'),
                        SimpleNamespace(returncode=0, stdout=record)]), \
                    patch('ownos.cli.subprocess.call', return_value=0) as execute, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(cli.install_app('firefox'), 1)
                execute.assert_called_once_with(['/usr/bin/passwd'])
                self.assertIn('does not have a usable administrator password', errors.getvalue())

    def test_live_account_with_a_password_does_not_change_it(self):
        with patch('pathlib.Path.is_dir', return_value=True), \
                patch('pwd.getpwuid', return_value=SimpleNamespace(pw_name='live')), \
                patch('ownos.cli.subprocess.run', side_effect=[SimpleNamespace(
                    returncode=0, stdout='live P 2026-10-16 0 99999 7 -1\n'),
                    SimpleNamespace(returncode=0)]), \
                patch('ownos.cli.subprocess.call', return_value=0) as execute, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.install_app('firefox'), 0)
        execute.assert_called_once_with(
            ['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'install', 'firefox'])

    def test_locked_or_malformed_live_status_cannot_change_a_password_or_start_pkexec(self):
        for record in ('live L 2026-10-16 0 99999 7 -1\n', 'live NP\n',
                       'other P 2026-10-16 0 99999 7 -1\n', ''):
            with self.subTest(record=record), \
                    patch('pathlib.Path.is_dir', return_value=True), \
                    patch('pwd.getpwuid', return_value=SimpleNamespace(pw_name='live')), \
                    patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(stdout=record)), \
                    patch('ownos.cli.subprocess.call') as execute, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(cli.install_app('firefox'), 1)
                execute.assert_not_called()
                self.assertIn('does not have a usable administrator password', errors.getvalue())

    def test_live_password_query_failure_stops_before_any_change(self):
        for failure in (subprocess.CalledProcessError(5, 'passwd', stderr='status denied'),
                        FileNotFoundError('passwd is missing'), subprocess.TimeoutExpired('passwd', 8)):
            with self.subTest(failure=failure), \
                    patch('pathlib.Path.is_dir', return_value=True), \
                    patch('pwd.getpwuid', return_value=SimpleNamespace(pw_name='live')), \
                    patch('ownos.cli.subprocess.run', side_effect=failure), \
                    patch('ownos.cli.subprocess.call') as execute, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertNotEqual(cli.install_app('firefox'), 0)
                execute.assert_not_called()
                self.assertIn('Could not check the Live administrator password status', errors.getvalue())

    def test_installed_system_or_other_uid_never_sets_a_live_password(self):
        for archiso, user in ((False, 'live'), (True, 'alice')):
            with self.subTest(archiso=archiso, user=user), \
                    patch('pathlib.Path.is_dir', return_value=archiso), \
                    patch('pwd.getpwuid', return_value=SimpleNamespace(pw_name=user)), \
                    patch.dict('os.environ', {'USER': 'live', 'LOGNAME': 'live', 'HOME': '/home/live'}), \
                    patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(returncode=0)) as query, \
                    patch('ownos.cli.subprocess.call', return_value=0) as execute, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.install_app('firefox'), 0)
                execute.assert_called_once_with(
                    ['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'install', 'firefox'])
                self.assertEqual(query.call_count, 1)

    def test_live_flatpak_install_does_not_inspect_or_change_the_account_password(self):
        with patch('pathlib.Path.is_dir', return_value=True), \
                patch('pwd.getpwuid', return_value=SimpleNamespace(pw_name='live')), \
                patch('ownos.cli.subprocess.run', side_effect=[SimpleNamespace(stdout=''),
                                                              SimpleNamespace(returncode=0)]) as query, \
                patch('ownos.cli.subprocess.call', return_value=0) as execute, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.install_app('heroic'), 0)
        self.assertFalse(any('passwd' in part for command in execute.call_args_list for part in command.args[0]))
        self.assertFalse(any('passwd' in part for command in query.call_args_list for part in command.args[0]))

    def test_fresh_install_stops_if_adding_the_official_remote_fails(self):
        with patch('ownos.cli.subprocess.run', return_value=SimpleNamespace(stdout='')), \
                patch('ownos.cli.subprocess.call', return_value=7) as execute:
            self.assertEqual(cli.install_app('heroic'), 7)
            execute.assert_called_once_with(
                ['/usr/bin/flatpak', 'remote-add', '--user', '--if-not-exists', 'flathub', FLATHUB_REPOFILE])


if __name__ == '__main__':
    unittest.main()

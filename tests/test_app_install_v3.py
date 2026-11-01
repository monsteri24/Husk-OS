"""Read-only connectivity, explicit transactions and credential isolation."""
import importlib.util
import io
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import termios
import unittest
from types import SimpleNamespace
from unittest.mock import call, patch
from urllib.error import HTTPError, URLError

from ownos import app_install as install
from ownos.catalog import app_by_id
from ownos import live_password

ROOT = Path(__file__).resolve().parents[1]


class ConnectivityTests(unittest.TestCase):
    def test_pacman_conf_resolves_every_configured_repository(self):
        replies = ['core\nextra\nmultilib\n', 'https://mirror.invalid/core/os/x86_64\n',
                   'https://mirror.invalid/extra/os/x86_64\n', 'https://mirror.invalid/multilib/os/x86_64\n']
        with patch('ownos.app_install.subprocess.run', side_effect=[SimpleNamespace(stdout=x) for x in replies]) as query:
            targets = install.repository_targets(app_by_id('steam'))
        self.assertEqual([name for name, _ in targets], ['core', 'extra', 'multilib'])
        self.assertEqual(targets[-1][1], ['https://mirror.invalid/multilib/os/x86_64/multilib.db'])
        self.assertEqual(query.call_args_list[0].args[0], ['/usr/bin/pacman-conf', '--repo-list'])
        self.assertTrue(all('-Sy' not in str(c) for c in query.call_args_list))

    def test_dns_failure_stops_before_any_authentication_or_package_transaction(self):
        with patch('ownos.app_install.repository_targets', return_value=[('core', ['https://mirror.invalid/core.db'])]), \
                patch('ownos.app_install._probe_repository', side_effect=URLError(socket.gaierror(-2, 'lookup failed'))), \
                patch('ownos.app_install.subprocess.Popen') as transaction, \
                patch('ownos.app_install._live_password_status') as password:
            with self.assertRaises(install.InstallProblem) as caught:
                install.preflight_install(app_by_id('steam'))
        self.assertEqual(caught.exception.kind, 'dns')
        self.assertIn('DNS', caught.exception.detail)
        transaction.assert_not_called(); password.assert_not_called()

    def test_valid_fallback_mirror_is_used_without_rewriting_configuration(self):
        candidates = ['https://one.invalid/core.db', 'https://two.invalid/core.db']
        with patch('ownos.app_install.repository_targets', return_value=[('core', candidates)]), \
                patch('ownos.app_install._probe_repository', side_effect=[OSError('offline mirror'), None]) as probe:
            install.preflight_install(app_by_id('firefox'))
        self.assertEqual(probe.call_args_list, [call(x) for x in candidates])

    def test_failed_mirror_retry_count_is_bounded_to_three_hosts_per_repository(self):
        candidates = ['https://%d.invalid/core.db' % n for n in range(20)]
        with patch('ownos.app_install.repository_targets', return_value=[('core', candidates)]), \
                patch('ownos.app_install._probe_repository', side_effect=URLError(socket.gaierror())) as probe:
            with self.assertRaises(install.InstallProblem):
                install.preflight_install(app_by_id('steam'))
        self.assertEqual(probe.call_count, 3)

    def test_every_repository_must_be_reachable(self):
        targets = [('core', ['https://one.invalid/core.db']), ('multilib', ['https://one.invalid/multilib.db'])]
        with patch('ownos.app_install.repository_targets', return_value=targets), \
                patch('ownos.app_install._probe_repository', side_effect=[None, URLError(socket.gaierror())]):
            with self.assertRaises(install.InstallProblem) as caught:
                install.preflight_install(app_by_id('steam'))
        self.assertIn('multilib', caught.exception.detail)

    def test_cancelled_preflight_does_not_read_configuration_or_start_process(self):
        with patch('ownos.app_install.repository_targets') as query:
            with self.assertRaises(install.InstallProblem) as caught:
                install.preflight_install(app_by_id('steam'), cancelled=lambda: True)
        self.assertEqual(caught.exception.kind, 'cancelled'); query.assert_not_called()

    def test_mirror_and_certificate_errors_are_distinguished(self):
        self.assertEqual(install._connection_problem(HTTPError('https://mirror.invalid', 503, '', {}, None)).kind, 'mirror')
        self.assertEqual(install._connection_problem(URLError(ssl.SSLCertVerificationError())).kind, 'tls')
        self.assertEqual(install._connection_problem(URLError(TimeoutError())).kind, 'network')

    def test_probe_uses_read_only_headers_and_never_downloads_a_database(self):
        reply = SimpleNamespace(__enter__=lambda self: self, __exit__=lambda *args: None)
        from unittest.mock import MagicMock
        reply = MagicMock()
        with patch('ownos.app_install.urlopen', return_value=reply) as fetch:
            install._probe_repository('https://mirror.invalid/core.db')
        self.assertEqual(fetch.call_args.args[0].method, 'HEAD')
        reply.__enter__.return_value.read.assert_not_called()

    def test_trusted_flathub_rejects_bad_url_disabled_and_unsigned_remote(self):
        for remote, kind in [('flathub\thttps://evil.invalid/\tuser\n', 'repository'),
                             ('flathub\thttps://dl.flathub.org/repo/\tuser,no-gpg-verify\n', 'signature'),
                             ('flathub\thttps://dl.flathub.org/repo/\tuser,disabled\n', 'repository')]:
            with self.subTest(remote=remote), patch('ownos.app_install.subprocess.run', return_value=SimpleNamespace(stdout=remote)):
                with self.assertRaises(install.InstallProblem) as caught:
                    install.trusted_flathub()
                self.assertEqual(caught.exception.kind, kind)


class TransactionTests(unittest.TestCase):
    def test_gui_native_command_is_curated_and_still_uses_polkit(self):
        commands = install.graphical_commands(app_by_id('steam'))
        self.assertEqual(commands, [(['/usr/bin/pkexec', '--disable-internal-agent',
                                     '/usr/lib/ownos/own-admin', 'install-confirmed', 'steam'], 'authorization')])

    def test_gui_flatpak_commands_are_user_scoped_and_keep_gpg_defaults(self):
        commands = [argv for argv, _ in install.graphical_commands(app_by_id('heroic'))]
        self.assertTrue(all('--user' in argv for argv in commands))
        self.assertFalse(any('--no-gpg-verify' in argv for argv in commands))
        self.assertIn('--noninteractive', commands[-1])
        self.assertEqual(commands[-1][-1], 'com.heroicgameslauncher.hgl')

    def test_errors_preserve_authorization_dns_signature_and_transaction_distinctions(self):
        for status, text, kind in [(126, '', 'authorization'), (127, '', 'authorization'),
                                   (1, 'Could not resolve host: mirror.invalid', 'dns'),
                                   (1, 'error: Partition / too full: 152870 blocks needed, 62830 blocks free\nerror: failed to commit transaction (not enough free disk space)', 'space'),
                                   (1, 'invalid or corrupted package (PGP signature)', 'signature'),
                                   (1, 'unable to lock database', 'locked'), (23, 'failed', 'transaction')]:
            with self.subTest(kind=kind):
                self.assertEqual(install.transaction_problem(status, text).kind, kind)
        self.assertEqual(install.transaction_problem(127, '', native=False).kind, 'transaction')

    def test_space_failure_explains_temporary_live_memory_and_has_a_real_remedy(self):
        problem = install.transaction_problem(1, 'Checking package signatures...\nerror: failed to commit transaction (not enough free disk space)')
        self.assertEqual(problem.kind, 'space')
        self.assertIn('RAM', problem.detail)
        self.assertIn('installed system', problem.detail)

    def test_progress_stages_come_only_from_actual_output(self):
        self.assertIsNone(install.transaction_stage('random diagnostic 54%'))
        self.assertIn('Downloading', install.transaction_stage(':: Retrieving packages...'))
        self.assertIn('signatures', install.transaction_stage('checking package integrity...'))

    def test_root_helper_revalidates_curated_targets_before_noninteractive_full_upgrade(self):
        # Load the real script without invoking its main/doing privileged work.
        from importlib.machinery import SourceFileLoader
        loader = SourceFileLoader('husk_test_admin', str(ROOT / 'bin/own-admin'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        admin = importlib.util.module_from_spec(spec); loader.exec_module(admin)
        from unittest.mock import MagicMock
        fake_file = MagicMock()
        with patch.object(admin.os, 'geteuid', return_value=0), \
                patch.object(admin.sys, 'argv', ['own-admin', 'install-confirmed', 'steam']), \
                patch.object(admin.Path, 'exists', return_value=False), \
                patch.object(admin.Path, 'mkdir'), patch.object(admin.Path, 'open', return_value=fake_file), \
                patch.object(admin.fcntl, 'flock'), patch.object(admin, 'preflight_install') as checks, \
                patch.object(admin.subprocess, 'run', return_value=SimpleNamespace(stdout='mesa\nvulkan-radeon\nvulkan-intel\n')), \
                patch.object(admin.subprocess, 'call', return_value=0) as execute:
            self.assertEqual(admin.main(), 0)
        checks.assert_called_once()
        self.assertEqual(execute.call_args.args[0], ['/usr/bin/pacman', '-Syu', '--needed', 'steam',
                                                   'lib32-vulkan-radeon', 'lib32-vulkan-intel', '--noconfirm'])
        self.assertNotIn('nosignature', str(execute.call_args))
        with patch.object(admin.os, 'geteuid', return_value=0), \
                patch.object(admin.sys, 'argv', ['own-admin', 'install-confirmed', '--noconfirm']), \
                patch.object(admin.subprocess, 'call') as execute:
            with self.assertRaises(ValueError):
                admin.main()
            execute.assert_not_called()


class SteamGraphicsTests(unittest.TestCase):
    def test_32_bit_drivers_match_existing_64_bit_graphics_without_an_alphabetic_default(self):
        select = getattr(install, 'steam_graphics_targets', None)
        self.assertTrue(callable(select), 'Steam needs an explicit matching 32-bit Vulkan provider')
        cases = [({'vulkan-radeon', 'vulkan-intel', 'mesa'}, ('lib32-vulkan-radeon', 'lib32-vulkan-intel')),
                 ({'nvidia-utils'}, ('lib32-nvidia-utils',)),
                 ({'vulkan-nouveau'}, ('lib32-vulkan-nouveau',)),
                 ({'vulkan-virtio'}, ('lib32-vulkan-virtio',)),
                 ({'vulkan-swrast'}, ('lib32-vulkan-swrast',)),
                 ({'vulkan-intel', '--config=/tmp/untrusted'}, ('lib32-vulkan-intel',))]
        for packages, expected in cases:
            with self.subTest(packages=packages):
                self.assertEqual(select(packages), expected)

    def test_unknown_graphics_stops_the_noninteractive_transaction_instead_of_picking_nvidia(self):
        select = getattr(install, 'steam_graphics_targets', None)
        self.assertTrue(callable(select), 'Steam provider selection is missing')
        for packages in (set(), {'mesa'}, {'unreviewed-vulkan-driver'}):
            with self.subTest(packages=packages), self.assertRaises(install.InstallProblem) as caught:
                select(packages)
            self.assertEqual(caught.exception.kind, 'graphics')


class LivePasswordTests(unittest.TestCase):
    def test_live_status_is_fail_closed_and_does_not_reset_existing_password(self):
        for value, outcome in [('NP', 'setup'), ('P', 'ready')]:
            with patch('ownos.app_install.Path.is_dir', return_value=True), \
                    patch('ownos.app_install.pwd.getpwuid', return_value=SimpleNamespace(pw_name='live')), \
                    patch('ownos.app_install._live_password_status', return_value=value):
                self.assertEqual(install.live_authentication_state(), outcome)
        with patch('ownos.app_install.Path.is_dir', return_value=True), \
                patch('ownos.app_install.pwd.getpwuid', return_value=SimpleNamespace(pw_name='live')), \
                patch('ownos.app_install._live_password_status', return_value='L'):
            with self.assertRaises(RuntimeError):
                install.live_authentication_state()

    def test_only_the_unprivileged_live_account_with_an_empty_password_is_eligible(self):
        for uid, name, state, expected in [(1000, 'live', 'NP', True), (0, 'live', 'NP', False),
                                           (1000, 'other', 'NP', False), (1000, 'live', 'P', False),
                                           (1000, 'live', 'L', False)]:
            with self.subTest(uid=uid, name=name, state=state), \
                    patch.object(live_password.os, 'getuid', return_value=uid), \
                    patch.object(live_password.Path, 'is_dir', return_value=True), \
                    patch.object(live_password.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name=name)), \
                    patch.object(live_password.subprocess, 'run', return_value=SimpleNamespace(stdout=f'{name} {state} 2026-10-17 0 99999 7 -1')):
                self.assertEqual(live_password._eligible(), expected)

    def test_password_validation_prevents_terminal_control_delimiters(self):
        self.assertTrue(live_password.valid_password('A literal $() password'))
        for value in ('', 'short', 'x' * 129, 'newline\npassword', 'carriage\rreturn', 'null\x00password',
                      'terminal\x04EOF', 'terminal\x15clear', 'terminal\x03interrupt'):
            self.assertFalse(live_password.valid_password(value))

    @unittest.skipUnless(hasattr(os, 'fork'), 'Controlling PTY test requires POSIX')
    def test_passwd_bridge_uses_a_controlling_tty_and_keeps_secret_out_of_output(self):
        # Only the synthetic child runs here; the system passwd is never run.
        secret = 'Test-only $() credential'
        def synthetic_passwd(_file, argv, env):
            if argv != ['/usr/bin/passwd'] or env['LC_ALL'] != 'C':
                os._exit(9)
            tty = os.open('/dev/tty', os.O_RDWR)
            attrs = termios.tcgetattr(tty); attrs[3] &= ~termios.ECHO
            termios.tcsetattr(tty, termios.TCSANOW, attrs)
            os.write(tty, b'New password: '); first = os.read(tty, 512).decode().rstrip('\n')
            os.write(tty, b'Retype new password: '); second = os.read(tty, 512).decode().rstrip('\n')
            os.close(tty)
            os._exit(0 if first == second == secret else 8)
        with patch.object(live_password.os, 'execve', side_effect=synthetic_passwd):
            self.assertEqual(live_password._exchange(secret, timeout=3), 0)

    @unittest.skipUnless(hasattr(os, 'fork'), 'Controlling PTY test requires POSIX')
    def test_passwd_bridge_refuses_to_send_a_secret_when_terminal_echo_is_enabled(self):
        def echoing_child(_file, _argv, _env):
            os.write(1, b'New password: ')
            os.read(0, 128)
            os._exit(9)
        write = os.write
        with patch.object(live_password.os, 'execve', side_effect=echoing_child), \
                patch.object(live_password.os, 'write', wraps=write) as sent:
            self.assertEqual(live_password._exchange('Test-only secret', timeout=3), 1)
        sent.assert_not_called()


if __name__ == '__main__':
    unittest.main()

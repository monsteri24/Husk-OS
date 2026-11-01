"""Real GTK widget/state checks; transactions are always synthetic in this suite."""
import io
import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class AppInstallCallbackTests(unittest.TestCase):
    """Exercise GTK callbacks without constructing widgets or opening a display."""
    def setUp(self):
        try:
            from ownos.ui import app_install
        except ModuleNotFoundError as exc:
            if exc.name != 'gi':
                raise
            self.skipTest('GTK imports require the prepared runtime: ' + str(exc))
        self.ui = app_install

    def test_install_callback_can_translate_its_title_and_cancel_with_signal_arguments(self):
        window = SimpleNamespace(state='ready', app=self.ui.app_by_id('steam'), begin=MagicMock())
        with patch.object(self.ui, 'confirm', return_value=False) as confirmation:
            self.ui.AppInstallWindow._install(window, object())
        confirmation.assert_called_once_with(window, 'Install Steam?', self.ui.installation_detail(window.app))
        window.begin.assert_not_called()

    def test_password_validation_can_translate_a_mismatch_with_signal_arguments(self):
        dialog = SimpleNamespace(password=SimpleNamespace(get_text=lambda: 'Test password'),
                                 repeat=SimpleNamespace(get_text=lambda: 'Different password'),
                                 set_button=MagicMock(), message=MagicMock())
        self.ui.LivePasswordDialog._validate(dialog, object())
        dialog.set_button.set_sensitive.assert_called_once_with(False)
        dialog.message.set_text.assert_called_once_with('Passwords do not match.')


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1',
                     'Run with OWNOS_UI_TESTS=1 inside a test display')
class GraphicalAppInstallTests(unittest.TestCase):
    def setUp(self):
        from ownos.ui import app_install as ui
        from ownos.ui import common
        self.ui, self.common = ui, common
        common.require_display()
        self.window = ui.AppInstallWindow('steam')
        self.addCleanup(self.window.destroy)

    def drain(self):
        for _ in range(200):
            if not self.common.Gtk.events_pending():
                break
            self.common.Gtk.main_iteration_do(False)

    def fake_process(self, status, output=''):
        process = MagicMock()
        process.__enter__.return_value = process
        process.stdout = io.StringIO(output)
        process.wait.return_value = status
        return process

    def test_cancel_in_confirmation_has_no_authentication_or_package_side_effect(self):
        with patch.object(self.ui, 'confirm', return_value=False), \
                patch.object(self.ui, 'preflight_install') as checks, \
                patch.object(self.ui, 'set_live_password') as password, \
                patch.object(self.ui.subprocess, 'Popen') as transaction:
            self.window._install()
        checks.assert_not_called(); password.assert_not_called(); transaction.assert_not_called()
        self.assertEqual(self.window.state, 'ready')

    def test_dns_failure_has_retry_network_settings_and_never_reaches_authentication(self):
        from ownos.app_install import InstallProblem
        with patch.object(self.ui, 'preflight_install', side_effect=InstallProblem('dns', 'DNS lookup failed.', 'Check DNS.')), \
                patch.object(self.ui, 'live_authentication_state') as authentication, \
                patch.object(self.ui.subprocess, 'Popen') as transaction:
            self.window._preflight(); self.drain()
        self.assertEqual(self.window.state, 'failed')
        self.assertEqual(self.window.install_button.get_label(), 'Retry')
        self.assertIn('DNS', self.window.status.get_text())
        self.assertTrue(self.window.network_button.get_sensitive())
        authentication.assert_not_called(); transaction.assert_not_called()

    def test_cancelling_temporary_password_dialog_does_not_set_password_or_start_transaction(self):
        dialog = MagicMock()
        dialog.run.return_value = self.common.Gtk.ResponseType.CANCEL
        with patch.object(self.ui, 'LivePasswordDialog', return_value=dialog), \
                patch.object(self.ui, 'set_live_password') as password, \
                patch.object(self.window, '_start_transaction') as transaction:
            self.window._authentication('setup')
        password.assert_not_called(); transaction.assert_not_called()
        dialog.take_password.assert_not_called()
        self.assertEqual(self.window.state, 'failed')
        self.assertIn('No password', self.window.explanation.get_text())

    def test_authorization_denial_is_visible_and_does_not_claim_success(self):
        with patch.object(self.ui.subprocess, 'Popen', return_value=self.fake_process(126)), \
                patch.object(self.ui, 'app_installed') as verified:
            self.window._transaction(); self.drain()
        verified.assert_not_called()
        self.assertEqual(self.window.state, 'failed')
        self.assertIn('Authorization', self.window.status.get_text())

    def test_zero_transaction_status_requires_verified_package_record(self):
        with patch.object(self.ui.subprocess, 'Popen', return_value=self.fake_process(0)), \
                patch.object(self.ui, 'app_installed', return_value=False):
            self.window._transaction(); self.drain()
        self.assertEqual(self.window.state, 'failed')
        self.assertIn('could not be verified', self.window.status.get_text())

    def test_success_is_verified_and_does_not_launch_the_new_application(self):
        with patch.object(self.ui.subprocess, 'Popen', return_value=self.fake_process(0, ':: Retrieving packages...\n')) as execute, \
                patch.object(self.ui, 'app_installed', return_value=True):
            self.window._transaction(); self.drain()
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(self.window.state, 'complete')
        self.assertIn('installed (verified)', self.window.status.get_text())
        self.assertFalse(self.window.install_button.get_visible())
        self.assertFalse(self.window.progress.get_show_text())

    def test_active_transaction_cannot_be_closed_mid_upgrade(self):
        self.window.state = 'installing'
        self.assertTrue(self.window._delete())
        self.window._close()
        self.assertFalse(self.window.closed)

    def test_standalone_installer_exits_when_its_window_is_closed(self):
        expired = []
        def timeout():
            expired.append(True)
            self.common.Gtk.main_quit()
            return False
        fallback = self.common.GLib.timeout_add(500, timeout)
        self.common.GLib.idle_add(lambda: (self.window.destroy(), False)[1])
        with patch.object(self.ui, 'AppInstallWindow', return_value=self.window):
            result = self.ui.main('steam')
        if not expired:
            self.common.GLib.source_remove(fallback)
        self.assertEqual(expired, [], 'Closing the installer must quit its own GTK loop')
        self.assertNotEqual(result, 0, 'Closing without installing cannot report installation success')

    def test_password_is_only_on_stdin_of_an_isolated_unprivileged_helper(self):
        secret = 'Test-only $() password'
        with patch.object(self.ui.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as execute, \
                patch.object(self.ui, 'live_authentication_state', return_value='ready'):
            self.ui.set_live_password(secret)
        argv = execute.call_args.args[0]
        self.assertEqual(argv[:2], ['/usr/bin/python3', '-I'])
        self.assertTrue(argv[-1].endswith('/ownos/live_password.py'))
        self.assertNotIn(secret, ' '.join(argv))
        self.assertIn(secret.encode(), execute.call_args.kwargs['input'])
        self.assertEqual(execute.call_args.kwargs['stdout'], subprocess.DEVNULL)
        self.assertEqual(execute.call_args.kwargs['stderr'], subprocess.DEVNULL)

    def test_gui_launch_hands_off_to_native_window_without_starting_terminal(self):
        fake_window = MagicMock()
        with patch.object(self.common, 'installed', return_value=False), \
                patch.object(self.common, 'confirm', return_value=True), \
                patch.object(self.ui, 'AppInstallWindow', return_value=fake_window), \
                patch.object(self.common, 'terminal') as terminal:
            self.assertIs(self.common.launch_app('steam'), fake_window)
        fake_window.begin.assert_called_once_with()
        terminal.assert_not_called()

    def test_new_native_windows_use_saved_accent_and_dark_gtk_preference(self):
        from ownos.config import defaults
        settings = defaults(); settings['accent'] = '#26a269'
        with patch.object(self.common.ConfigStore, 'load', return_value=settings):
            provider = self.common.load_style()
        try:
            self.drain()
            self.assertTrue(self.common.Gtk.Settings.get_default().get_property('gtk-application-prefer-dark-theme'))
            found, actual = self.window.get_style_context().lookup_color('accent')
            self.assertTrue(found)
            expected = self.common.Gdk.RGBA(); expected.parse('#26a269')
            self.assertEqual(actual, expected)
        finally:
            self.common.remove_style(provider)


if __name__ == '__main__':
    unittest.main()

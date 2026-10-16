"""Real GTK smoke tests, enabled only in a prepared display environment."""
import os
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1', 'Run with OWNOS_UI_TESTS=1 inside a test display')
class UISmokeTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos.ui import shell, control, file_manager
            from ownos.config import ConfigStore
            from ownos.ui.common import Gtk
            self.shell, self.control, self.file_manager, self.Gtk = shell, control, file_manager, Gtk
        except ImportError as exc:
            self.fail('GUI implementation missing: ' + str(exc))
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = ConfigStore(self.root / 'settings.json')

    def drain(self):
        for _ in range(200):
            if not self.Gtk.events_pending(): break
            self.Gtk.main_iteration_do(False)

    def test_start_opens_and_search_finds_heroic(self):
        shell = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(shell.shutdown)
        shell.toggle_start(); self.drain()
        self.assertTrue(shell.start_window.get_visible())
        shell.search.set_text('Heroic'); self.drain()
        self.assertTrue(any('Heroic' in row.app_name for row in shell.app_list.get_children()))

    def test_control_center_persists_gaming_toggle(self):
        control = self.control.ControlWindow(store=self.store)
        self.addCleanup(control.destroy)
        control.gaming_switch.set_active(False); self.drain()
        self.assertFalse(self.store.load()['gaming_mode'])

    def test_file_manager_changes_directory(self):
        (self.root / 'folder').mkdir()
        window = self.file_manager.FileWindow(self.root)
        self.addCleanup(window.destroy)
        window.navigate(self.root / 'folder'); self.drain()
        self.assertEqual(window.current, self.root / 'folder')

    def test_notification_center_shows_plain_text(self):
        shell = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(shell.shutdown)
        shell.notifications.notify('Test', 'Title <tag>', 'Body')
        shell.refresh_notifications(); self.drain()
        self.assertEqual(len(shell.notification_list.get_children()), 1)

    def test_husk_panel_and_launcher_are_separate_components(self):
        from ownos.ui.panel import Panel
        from ownos.ui.launcher import Launcher
        shell = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(shell.shutdown)
        self.assertIsInstance(shell.taskbar, Panel)
        self.assertIsInstance(shell.launcher, Launcher)
        self.assertIn('Husk', shell.panel.get_title())

    def test_panel_position_change_preserves_launcher_and_notifications(self):
        shell = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(shell.shutdown)
        shell.notifications.notify('Test', 'Keep', 'Body')
        old_panel = shell.panel
        settings = self.store.load(); settings['taskbar_position'] = 'top'; self.store.save(settings)
        shell.reload_settings(); self.drain()
        self.assertIsNot(shell.panel, old_panel)
        self.assertEqual(shell.taskbar.position, 'top')
        self.assertEqual(len(shell.notifications.history), 1)
        shell.toggle_start(); self.drain()
        self.assertTrue(shell.start_window.get_visible())

    def test_invalid_user_css_keeps_base_style(self):
        (self.store.path.parent / 'desktop.css').write_text('* { bad-property: ; }')
        shell = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(shell.shutdown)
        self.assertTrue(shell.provider.husk_style_warning)
        self.assertTrue(shell.panel.get_visible())

    def test_preview_status_cannot_claim_live_wayland_boot(self):
        shell = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(shell.shutdown); self.drain()
        self.assertEqual(shell.status()['backend'],'preview')
        self.assertFalse(shell.status()['bridge_connected'])


if __name__ == '__main__': unittest.main()

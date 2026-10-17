"""Real GTK checks for System 2's English-only release policy."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1', 'Run with OWNOS_UI_TESTS=1 inside a test display')
class LocalizationUITests(unittest.TestCase):
    def setUp(self):
        from ownos import i18n
        from ownos.config import ConfigStore
        from ownos.ui import control, file_manager, shell
        from ownos.ui.common import Gtk, Gio
        self.i18n, self.Gtk, self.Gio = i18n, Gtk, Gio
        self.control, self.files, self.shell = control, file_manager, shell
        self.addCleanup(i18n.configure)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'files'; self.folder.mkdir()
        locale_patch = patch.object(i18n, 'LOCALEDIR', self.root / 'missing-locale')
        locale_patch.start(); self.addCleanup(locale_patch.stop)
        environment = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config')})
        environment.start(); self.addCleanup(environment.stop)
        self.store = ConfigStore()
        i18n.configure()

    def drain(self):
        for _ in range(200):
            if not self.Gtk.events_pending(): break
            self.Gtk.main_iteration_do(False)

    def write_old_language(self, language):
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.store.path.write_text(json.dumps({'language': language, 'overlay': True}))

    def test_settings_offers_only_english(self):
        window = self.control.ControlWindow(store=self.store)
        self.addCleanup(window.destroy)
        self.assertEqual(window.language.get_active_id(), 'en')
        self.assertEqual(window.language.get_active_text(), 'English')
        self.assertEqual(len(window.language.get_model()), 1)
        self.assertFalse(window.language.get_sensitive())
        self.assertFalse(window.language.set_active_id('fi'))
        self.assertEqual(window.language.get_active_id(), 'en')

    def test_saved_finnish_opens_settings_and_files_in_english(self):
        self.write_old_language('fi')
        settings = self.control.ControlWindow(store=self.store)
        files = self.files.FileWindow(self.folder, store=self.store)
        self.addCleanup(settings.destroy); self.addCleanup(files.destroy)
        self.assertEqual(settings.language.get_active_id(), 'en')
        self.assertIn('Husk Settings', settings.get_title())
        self.assertEqual(files.get_title(), 'Husk Files')
        self.assertEqual(files.status.get_text(), '0 items')
        self.assertTrue(settings.settings['overlay'])
        (self.folder / 'one').write_text('one')
        files.navigate(self.folder)
        self.assertEqual(files.status.get_text(), '1 item')

    def test_saved_finnish_locale_does_not_localize_desktop(self):
        self.write_old_language('fi_FI')
        desktop = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(desktop.shutdown)
        self.assertEqual(desktop.panel.get_title(), 'Husk Taskbar')
        self.assertEqual(desktop.search.get_placeholder_text(), 'Search applications…')
        self.assertEqual(desktop.notification_window.get_title(), 'Husk Notifications')

    def test_settings_watcher_ignores_finnish_and_retains_notifications(self):
        desktop = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(desktop.shutdown)
        old_panel = desktop.panel
        desktop.notifications.notify('Test', 'Keep', 'Body')
        desktop.refresh_notifications()
        self.write_old_language('fi')
        desktop.settings_changed(None, self.Gio.File.new_for_path(str(self.store.path)), None,
                                 self.Gio.FileMonitorEvent.CHANGED)
        self.drain()
        self.assertIs(desktop.panel, old_panel)
        self.assertEqual(desktop.panel.get_title(), 'Husk Taskbar')
        self.assertEqual(desktop.search.get_placeholder_text(), 'Search applications…')
        self.assertEqual([item.summary for item in desktop.notifications.history], ['Keep'])
        self.assertEqual(len(desktop.notification_list.get_children()), 1)
        desktop.toggle_start(); self.drain()
        self.assertTrue(desktop.start_window.get_visible())

    def test_finnish_host_locale_does_not_select_finnish(self):
        with patch.dict(os.environ, {'LANGUAGE': 'fi:en', 'LANG': 'fi_FI.UTF-8'}):
            files = self.files.FileWindow(self.folder)
            settings = self.control.ControlWindow(store=self.store)
        self.addCleanup(files.destroy); self.addCleanup(settings.destroy)
        self.assertEqual(files.get_title(), 'Husk Files')
        self.assertIn('Husk Settings', settings.get_title())
        self.assertEqual(settings.language.get_active_id(), 'en')

    def test_bad_saved_language_falls_back_in_settings_and_files(self):
        self.write_old_language(['fi'])
        settings = self.control.ControlWindow(store=self.store)
        files = self.files.FileWindow(self.folder, store=self.store)
        self.addCleanup(settings.destroy); self.addCleanup(files.destroy)
        self.assertEqual(settings.language.get_active_id(), 'en')
        self.assertTrue(settings.settings['overlay'])
        self.assertIn('Husk Settings', settings.get_title())
        self.assertEqual(files.get_title(), 'Husk Files')


if __name__ == '__main__':
    unittest.main()

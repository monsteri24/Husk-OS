"""Real GTK localization checks, run in the prepared graphical test job."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


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
        directory = self.root / 'locale'
        target = directory / 'fi/LC_MESSAGES/huskos.mo'
        target.parent.mkdir(parents=True)
        subprocess.run(['msgfmt', '--check', '--check-format', str(ROOT / 'locale/fi/LC_MESSAGES/huskos.po'),
                        '-o', str(target)], check=True, capture_output=True, timeout=10)
        locale_patch = patch.object(i18n, 'LOCALEDIR', directory)
        locale_patch.start(); self.addCleanup(locale_patch.stop)
        environment = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config')})
        environment.start(); self.addCleanup(environment.stop)
        self.store = ConfigStore()
        i18n.configure()

    def drain(self):
        for _ in range(200):
            if not self.Gtk.events_pending(): break
            self.Gtk.main_iteration_do(False)

    def save_language(self, language):
        settings = self.store.load(); settings['language'] = language; self.store.save(settings)

    def test_selector_persists_finnish_and_reopened_apps_apply_it(self):
        window = self.control.ControlWindow(store=self.store)
        self.addCleanup(window.destroy)
        self.assertEqual(window.language.get_active_id(), 'en')
        window.language.set_active_id('fi'); self.drain()
        self.assertEqual(self.store.load()['language'], 'fi')
        self.assertEqual(window.status.get_text(), 'Language saved. Reopen Husk applications to apply it.')
        window.destroy()
        reopened = self.control.ControlWindow(store=self.store)
        files = self.files.FileWindow(self.folder, store=self.store)
        self.addCleanup(reopened.destroy); self.addCleanup(files.destroy)
        self.assertEqual(reopened.language.get_active_id(), 'fi')
        self.assertIn('Husk-asetukset', reopened.get_title())
        self.assertEqual(files.get_title(), 'Husk-tiedostot')
        self.assertEqual(files.status.get_text(), '0 kohdetta')
        (self.folder / 'one').write_text('one')
        files.navigate(self.folder)
        self.assertEqual(files.status.get_text(), '1 kohde')
        (self.folder / 'two').write_text('two')
        files.navigate(self.folder)
        self.assertEqual(files.status.get_text(), '2 kohdetta')

    def test_selector_can_restore_english(self):
        self.save_language('fi')
        window = self.control.ControlWindow(store=self.store)
        self.addCleanup(window.destroy)
        self.assertEqual(window.language.get_active_id(), 'fi')
        self.assertIn('Husk-asetukset', window.get_title())
        window.language.set_active_id('en'); self.drain()
        self.assertEqual(self.store.load()['language'], 'en')
        files = self.files.FileWindow(self.folder, store=self.store)
        self.addCleanup(files.destroy)
        self.assertEqual(files.get_title(), 'Husk Files')
        self.assertEqual(files.status.get_text(), '0 items')

    def test_failed_language_write_restores_the_saved_selection(self):
        window = self.control.ControlWindow(store=self.store)
        self.addCleanup(window.destroy)
        # A directory at the destination forces a real atomic-save failure.
        self.store.path.mkdir(parents=True)
        with patch.object(self.control, 'error') as report:
            window.language.set_active_id('fi'); self.drain()
        self.assertEqual(window.language.get_active_id(), 'en')
        self.assertEqual(self.store.load()['language'], 'en')
        report.assert_called_once()

    def test_saved_finnish_loads_on_desktop_startup(self):
        self.save_language('fi')
        desktop = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(desktop.shutdown)
        self.assertEqual(desktop.panel.get_title(), 'Husk-tehtäväpalkki')
        self.assertEqual(desktop.search.get_placeholder_text(), 'Etsi sovelluksia…')
        self.assertEqual(desktop.notification_window.get_title(), 'Husk-ilmoitukset')

    def test_settings_watcher_reloads_desktop_language_and_retains_notifications(self):
        desktop = self.shell.OwnShell(preview=True, store=self.store)
        self.addCleanup(desktop.shutdown)
        old_panel = desktop.panel
        desktop.notifications.notify('Test', 'Keep', 'Body')
        self.save_language('fi')
        desktop.settings_changed(None, self.Gio.File.new_for_path(str(self.store.path)), None,
                                 self.Gio.FileMonitorEvent.CHANGED)
        self.drain()
        self.assertIsNot(desktop.panel, old_panel)
        self.assertEqual(desktop.panel.get_title(), 'Husk-tehtäväpalkki')
        self.assertEqual(desktop.search.get_placeholder_text(), 'Etsi sovelluksia…')
        self.assertEqual(desktop.notification_window.get_title(), 'Husk-ilmoitukset')
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
        self.store.path.parent.mkdir(parents=True)
        self.store.path.write_text(json.dumps({'language': ['fi'], 'overlay': True}))
        settings = self.control.ControlWindow(store=self.store)
        files = self.files.FileWindow(self.folder, store=self.store)
        self.addCleanup(settings.destroy); self.addCleanup(files.destroy)
        self.assertEqual(settings.language.get_active_id(), 'en')
        self.assertTrue(settings.settings['overlay'])
        self.assertIn('Husk Settings', settings.get_title())
        self.assertEqual(files.get_title(), 'Husk Files')


if __name__ == '__main__':
    unittest.main()

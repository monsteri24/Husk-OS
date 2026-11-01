"""Native GTK desktop menus, activation and file/Trash surfaces."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1', 'Run inside a GTK test display with OWNOS_UI_TESTS=1')
class DesktopFileUITests(unittest.TestCase):
    def setUp(self):
        from ownos.ui.common import Gtk
        from ownos.config import ConfigStore
        from ownos.ui.shell import HuskDesktop
        self.Gtk = Gtk
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.desktop = self.root / 'Desktop'; self.desktop.mkdir()
        self.data_patch = patch.dict(os.environ, {'XDG_DATA_HOME': str(self.root / 'data')})
        self.data_patch.start(); self.addCleanup(self.data_patch.stop)
        self.path_patch = patch('ownos.ui.desktop.desktop_directory', return_value=self.desktop)
        self.path_patch.start(); self.addCleanup(self.path_patch.stop)
        self.shell = HuskDesktop(preview=True, store=ConfigStore(self.root / 'settings.json'))
        self.addCleanup(self.shell.shutdown)
        self.surface = self.shell.desktop_surfaces[0]

    def drain_until(self, condition=lambda: True):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            while self.Gtk.events_pending(): self.Gtk.main_iteration_do(False)
            if condition(): return
            time.sleep(0.01)
        self.assertTrue(condition(), 'GTK did not reach the expected state')

    def labels(self, menu):
        return [child.get_label() for child in menu.get_children() if isinstance(child, self.Gtk.MenuItem) and not isinstance(child, self.Gtk.SeparatorMenuItem)]

    def test_empty_space_menu_is_native_and_has_expected_actions(self):
        from ownos.ui.common import Gdk
        self.Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text('ordinary text', -1)
        menu = self.surface.build_menu(); self.addCleanup(menu.destroy)
        self.drain_until()
        self.assertIsInstance(menu, self.Gtk.Menu)
        self.assertEqual(self.labels(menu), ['New Folder', 'New File', 'Paste', 'Refresh',
                                           'Display Settings', 'Change Wallpaper', 'Personalize'])
        paste = next(child for child in menu.get_children() if child.get_label() == 'Paste')
        self.assertFalse(paste.get_sensitive())

    def test_regular_and_protected_icon_menus_preserve_virtual_actions(self):
        from ownos.desktop_files import DesktopEntry
        path = self.desktop / 'notes.txt'; path.touch()
        regular = self.surface.build_menu(DesktopEntry('file', path.name, 'text-x-generic', path))
        self.addCleanup(regular.destroy)
        self.assertEqual(self.labels(regular), ['Open', 'Rename', 'Move to Trash', 'Properties'])
        for kind in ('home', 'trash', 'installer'):
            menu = self.surface.build_menu(DesktopEntry(kind, kind, 'folder'))
            self.addCleanup(menu.destroy)
            self.assertIn('Open', self.labels(menu))
            self.assertNotIn('Rename', self.labels(menu)); self.assertNotIn('Move to Trash', self.labels(menu))

    def test_file_monitor_updates_icons_and_trash_setting_only_hides_the_icon(self):
        (self.desktop / 'fresh.txt').touch()
        self.drain_until(lambda: any(entry.label == 'fresh.txt' for entry in self.surface.entries))
        self.assertIn('trash', [entry.kind for entry in self.surface.entries])
        settings = self.shell.store.load(); settings['show_trash'] = False; self.shell.store.save(settings)
        self.shell.reload_settings(); self.surface = self.shell.desktop_surfaces[0]
        self.assertNotIn('trash', [entry.kind for entry in self.surface.entries])
        self.assertTrue((self.desktop / 'fresh.txt').is_file())

    def test_native_icon_activation_spawns_installer_directly(self):
        from ownos.desktop_files import DesktopEntry
        with patch('ownos.ui.desktop.spawn') as launch:
            self.surface.open_entry(DesktopEntry('installer', 'Install Husk OS', 'husk-install'))
        launch.assert_called_once_with(['/usr/bin/husk-install'], self.shell.panel)
        self.assertFalse(self.surface.flow.get_activate_on_single_click())

    def test_escape_dismisses_the_native_menu(self):
        from ownos.ui.common import Gdk
        self.surface.popup()
        menu = self.surface.active_menu
        self.drain_until(menu.get_mapped)
        event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        event.window = menu.get_window(); event.keyval = Gdk.KEY_Escape
        event.time = Gdk.CURRENT_TIME
        event.set_device(Gdk.Display.get_default().get_default_seat().get_keyboard())
        self.Gtk.main_do_event(event)
        self.drain_until(lambda: self.surface.active_menu is None)
        self.assertFalse(menu.get_mapped())
        self.assertIsNone(self.surface.menu_host)

    def test_trash_file_window_uses_trash_location_and_confirmed_empty_action(self):
        from ownos.ui.file_manager import FileWindow
        window = FileWindow('trash:///'); self.addCleanup(window.destroy)
        self.assertTrue(window.in_trash)
        self.assertEqual(window.location.get_text(), 'trash:///')
        with patch('ownos.ui.file_manager.confirm', return_value=False) as ask, \
             patch.object(window.trash_store, 'empty') as empty:
            window.empty_trash(None)
        ask.assert_called_once(); empty.assert_not_called()


if __name__ == '__main__': unittest.main()

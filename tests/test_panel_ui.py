"""Real GTK checks for compact, transparent and hidden panel transitions."""
import os
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1',
                     'Run with OWNOS_UI_TESTS=1 inside a test display')
class PanelPresentationTests(unittest.TestCase):
    def setUp(self):
        from ownos.config import ConfigStore
        from ownos.ui.common import Gtk
        from ownos.ui.shell import HuskDesktop
        self.Gtk = Gtk
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.shell = HuskDesktop(preview=True, store=ConfigStore(Path(temporary.name) / 'settings.json'))
        self.addCleanup(self.shell.shutdown)
        self.drain()

    def drain(self):
        for _ in range(300):
            if not self.Gtk.events_pending():
                break
            self.Gtk.main_iteration_do(False)

    def state(self, **changes):
        value = dict(event='upsert', id=1, title='A real task title', app_id='game',
                     active=True, minimized=False, maximized=False, fullscreen=False)
        value.update(changes)
        self.assertTrue(self.shell.window_store.apply(value))
        self.shell.refresh_tasks()
        self.drain()

    def test_maximize_removes_panel_background_and_keeps_task_icons(self):
        self.state(maximized=True)
        self.assertEqual(getattr(self.shell.taskbar, 'mode', None), 'maximized')
        self.assertTrue(self.shell.panel.get_visible())
        background = self.shell.panel.get_style_context().get_background_color(self.Gtk.StateFlags.NORMAL)
        self.assertEqual(background.alpha, 0)
        button = self.shell.tasks.get_children()[0]
        self.assertIsInstance(button.get_child(), self.Gtk.Image)
        self.assertEqual(button.get_tooltip_text(), 'A real task title')

    def test_fullscreen_unmaps_panel_and_closes_open_panel_popups(self):
        self.shell.toggle_start()
        self.state(fullscreen=True)
        self.assertEqual(getattr(self.shell.taskbar, 'mode', None), 'fullscreen')
        self.assertFalse(self.shell.panel.get_visible())
        self.assertFalse(self.shell.panel.get_mapped())
        self.assertFalse(self.shell.start_window.get_visible())
        self.state(maximized=True)
        self.assertTrue(self.shell.panel.get_visible())
        self.assertEqual(getattr(self.shell.taskbar, 'mode', None), 'maximized')
        self.state()
        self.assertEqual(getattr(self.shell.taskbar, 'mode', None), 'desktop')
        background = self.shell.panel.get_style_context().get_background_color(self.Gtk.StateFlags.NORMAL)
        self.assertGreater(background.alpha, 0.9)

    def test_tray_order_is_network_volume_bluetooth_clock(self):
        panel = self.shell.taskbar
        status = getattr(panel, 'status', None)
        self.assertIsNotNone(status, 'Panel status controls must be inspectable')
        self.assertEqual([button.get_tooltip_text() for button in status.get_children()],
                         ['Network connection settings', 'Volume', 'Bluetooth settings',
                          'Clock · Notification Center'])


if __name__ == '__main__':
    unittest.main()

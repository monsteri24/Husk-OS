"""Appearance choices persist and apply to real native GTK surfaces."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from ownos import config


class AppearanceConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = config.ConfigStore(Path(temporary.name) / 'settings.json')

    def test_first_run_uses_husk_yellow_and_shows_trash(self):
        self.assertEqual(self.store.load()['accent'], '#f5cf3b')
        self.assertEqual(config.HUSK_YELLOW, '#f5cf3b')
        self.assertIs(self.store.load().get('show_trash'), True)

    def test_accent_and_desktop_icon_choice_survive_reopening(self):
        settings = self.store.load()
        settings.update(accent='#26a269', show_trash=False)
        self.store.save(settings)
        reopened = config.ConfigStore(self.store.path).load()
        self.assertEqual(reopened['accent'], '#26a269')
        self.assertIs(reopened.get('show_trash'), False)

    def test_existing_settings_gain_trash_without_losing_appearance(self):
        self.store.path.write_text(json.dumps({
            'accent': '#abcdef', 'wallpaper': '/home/test/desert.png',
            'animations': False, 'overlay': True,
        }))
        settings = self.store.load()
        self.assertIs(settings.get('show_trash'), True)
        self.assertEqual(settings['accent'], '#abcdef')
        self.assertEqual(settings['wallpaper'], '/home/test/desert.png')
        self.assertFalse(settings['animations'])
        self.assertTrue(settings['overlay'])

    def test_trash_visibility_requires_a_real_boolean(self):
        for value in (0, 1, 'true', 'false', None, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.save({'show_trash': value})

    def test_bad_saved_trash_choice_falls_back_without_losing_accent(self):
        self.store.path.write_text('{"show_trash": "false", "accent": "#123abc"}')
        settings = self.store.load()
        self.assertIs(settings.get('show_trash'), True)
        self.assertEqual(settings['accent'], '#123abc')


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1',
                     'Run with OWNOS_UI_TESTS=1 inside a test display')
class AppearanceUITests(unittest.TestCase):
    def setUp(self):
        from ownos.ui.common import Gtk, Gdk
        from ownos.ui.control import ControlWindow
        self.Gtk, self.Gdk = Gtk, Gdk
        self.ControlWindow = ControlWindow
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = config.ConfigStore(Path(temporary.name) / 'settings.json')
        self.window = ControlWindow(store=self.store)
        self.addCleanup(self.window.destroy)
        self.window.show_all()
        self.drain()

    def drain(self):
        for _ in range(200):
            if not self.Gtk.events_pending():
                break
            self.Gtk.main_iteration_do(False)

    def assert_accent(self, widget, expected):
        found, actual = widget.get_style_context().lookup_color('accent')
        wanted = self.Gdk.RGBA()
        wanted.parse(expected)
        self.assertTrue(found)
        for channel in ('red', 'green', 'blue'):
            self.assertAlmostEqual(getattr(actual, channel), getattr(wanted, channel), places=5)

    def choose_accent(self, value):
        self.assertTrue(hasattr(self.window, 'accent_color'), 'Settings must expose the accent picker')
        color = self.Gdk.RGBA()
        color.parse(value)
        self.window.accent_color.set_rgba(color)
        self.window.accent_color.emit('color-set')
        self.drain()

    def test_color_choice_saves_and_immediately_styles_settings(self):
        self.choose_accent('#26a269')
        self.assertEqual(self.store.load()['accent'], '#26a269')
        self.assert_accent(self.window, '#26a269')

    def test_desktop_appearance_shortcut_opens_appearance_page(self):
        window = self.ControlWindow(store=self.store, page='appearance')
        self.addCleanup(window.destroy)
        window.show_all()
        self.drain()
        def descendants(widget):
            if isinstance(widget, self.Gtk.Notebook):
                yield widget
            if isinstance(widget, self.Gtk.Container):
                for child in widget.get_children():
                    yield from descendants(child)
        notebook = next(descendants(window))
        current = notebook.get_nth_page(notebook.get_current_page())
        self.assertEqual(notebook.get_tab_label_text(current), 'Appearance')

    def test_reset_to_default_restores_yellow_without_changing_wallpaper(self):
        self.window.save('wallpaper', '/home/test/custom.png')
        self.choose_accent('#26a269')
        self.window.reset_accent_button.clicked()
        self.drain()
        self.assertEqual(self.store.load()['accent'], config.HUSK_YELLOW)
        self.assertEqual(self.store.load()['wallpaper'], '/home/test/custom.png')
        self.assert_accent(self.window, config.HUSK_YELLOW)
        expected = self.Gdk.RGBA()
        expected.parse(config.HUSK_YELLOW)
        self.assertEqual(self.window.accent_color.get_rgba(), expected)

    def test_trash_switch_persists_both_choices(self):
        self.assertTrue(hasattr(self.window, 'trash_switch'), 'Settings must expose Show Trash')
        self.assertTrue(self.window.trash_switch.get_active())
        self.window.trash_switch.set_active(False)
        self.drain()
        self.assertFalse(self.store.load()['show_trash'])
        self.window.trash_switch.set_active(True)
        self.drain()
        self.assertTrue(self.store.load()['show_trash'])

    def test_native_color_chooser_uses_dark_surfaces_and_current_accent(self):
        chooser = self.Gtk.ColorChooserDialog(title='Accent color', transient_for=self.window)
        self.addCleanup(chooser.destroy)
        chooser.show_all()
        self.drain()
        self.assertTrue(self.Gtk.Settings.get_default().get_property('gtk-application-prefer-dark-theme'))
        background = chooser.get_style_context().get_background_color(self.Gtk.StateFlags.NORMAL)
        self.assertLess(max(background.red, background.green, background.blue), 0.25)
        self.assert_accent(chooser, config.HUSK_YELLOW)

    def test_native_menu_uses_dark_rounded_surface_and_yellow_selection(self):
        menu = self.Gtk.Menu()
        menu.attach_to_widget(self.window, None)
        self.addCleanup(menu.destroy)
        item = self.Gtk.MenuItem(label='Choose')
        menu.append(item)
        menu.show_all()
        self.drain()
        background = menu.get_style_context().get_background_color(self.Gtk.StateFlags.NORMAL)
        self.assertLess(max(background.red, background.green, background.blue), 0.25)
        self.assertGreater(menu.get_style_context().get_property('border-radius', self.Gtk.StateFlags.NORMAL), 0)
        selected = item.get_style_context().get_background_color(self.Gtk.StateFlags.PRELIGHT)
        expected = self.Gdk.RGBA()
        expected.parse(config.HUSK_YELLOW)
        for channel in ('red', 'green', 'blue'):
            self.assertAlmostEqual(getattr(selected, channel), getattr(expected, channel), places=5)


if __name__ == '__main__':
    unittest.main()

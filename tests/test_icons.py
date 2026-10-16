"""Packaged icon contracts and opt-in real GTK icon lookup checks."""
import configparser
import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON_NAMES = {'husk-start', 'husk-settings', 'husk-files', 'husk-games', 'husk-app'}


class PackagedIconTests(unittest.TestCase):
    def test_bundled_icons_are_small_original_scalable_assets(self):
        paths = list((ROOT / 'data/icons').glob('*.svg'))
        self.assertEqual({path.stem for path in paths}, ICON_NAMES)
        for path in paths:
            with self.subTest(icon=path.name):
                svg = ET.parse(path).getroot()
                self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
                self.assertEqual(svg.attrib['viewBox'], '0 0 24 24')
                self.assertLess(path.stat().st_size, 4096)
                text = path.read_text()
                self.assertIn('SPDX-License-Identifier: MIT', text)
                self.assertNotIn('<script', text)
                self.assertNotIn('href=', text)
        self.assertIn('original', (ROOT / 'data/icons/README.md').read_text().lower())

    def test_ui_package_installs_every_own_desktop_icon_in_hicolor(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            (staging / 'ownos').symlink_to(ROOT, target_is_directory=True)
            dest = staging / 'dest'
            env = dict(os.environ, pkgdir=str(dest))
            result = subprocess.run(
                ['bash', '--noprofile', '--norc', '-ec',
                 'source "$1"; pkgname=ownos-ui; package_ownos-ui',
                 'icon-package-test', str(ROOT / 'packaging/ownos/PKGBUILD')],
                cwd=staging, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            icons = dest / 'usr/share/icons/hicolor/scalable/apps'
            self.assertEqual({path.stem for path in icons.glob('*.svg')}, ICON_NAMES)
            for name in ICON_NAMES:
                self.assertEqual((icons / f'{name}.svg').read_bytes(),
                                 (ROOT / 'data/icons' / f'{name}.svg').read_bytes())
            for path in (dest / 'usr/share/applications').glob('org.ownos.*.desktop'):
                entry = configparser.ConfigParser(interpolation=None)
                entry.read(path)
                name = entry['Desktop Entry']['Icon']
                with self.subTest(desktop=path.name):
                    self.assertIn(name, ICON_NAMES)
                    self.assertTrue((icons / f'{name}.svg').is_file())
            self.assertEqual((dest / 'usr/share/licenses/ownos-ui/LICENSE.icons').read_bytes(),
                             (ROOT / 'LICENSE').read_bytes())


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1',
                     'Run with OWNOS_UI_TESTS=1 inside a test display')
class GTKIconTests(unittest.TestCase):
    def setUp(self):
        from ownos.ui import common
        self.common = common
        common.require_display()

    def assert_named_image(self, image, name, size):
        self.assertEqual(image.get_icon_name()[0], name)
        self.assertEqual(image.get_pixel_size(), size)
        self.assertEqual(image.get_size_request(), (size, size))
        theme = self.common.Gtk.IconTheme.get_default()
        pixbuf = theme.load_icon(name, size, self.common.Gtk.IconLookupFlags.FORCE_SIZE)
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (size, size))

    def test_source_preview_discovers_and_loads_every_bundled_icon(self):
        for name in ICON_NAMES:
            for size in (16, 24, 32, 48):
                with self.subTest(icon=name, size=size):
                    self.assert_named_image(self.common.icon(name, size), name, size)

    def test_unknown_names_and_gicons_get_visible_bundled_fallback(self):
        Gio = self.common.Gio
        missing = 'husk-test-application-that-is-not-installed'
        for source in (missing, Gio.ThemedIcon.new(missing),
                       Gio.FileIcon.new(Gio.File.new_for_path('/missing/husk-test-icon.svg')), None):
            with self.subTest(icon=str(source)):
                self.assert_named_image(self.common.icon(source), 'husk-app', 24)
        self.assert_named_image(self.common.icon(missing, fallback='husk-games'), 'husk-games', 24)

    def test_valid_installed_names_and_gicons_are_preserved(self):
        theme = self.common.Gtk.IconTheme.get_default()
        self.assertIsNotNone(theme.lookup_icon('folder', 24, 0), 'Adwaita essential icon dependency is missing')
        self.assert_named_image(self.common.icon('folder'), 'folder', 24)
        source = self.common.Gio.ThemedIcon.new('folder')
        image = self.common.icon(source)
        self.assertTrue(image.get_gicon()[0].equal(source))
        source = self.common.Gio.FileIcon.new(self.common.Gio.File.new_for_path(str(ROOT / 'data/icons/husk-files.svg')))
        image = self.common.icon(source)
        self.assertTrue(image.get_gicon()[0].equal(source))

    def test_icon_button_has_visible_icon_and_accessible_name(self):
        clicks = []
        button = self.common.icon_button('husk-start', 'Start', lambda: clicks.append(True))
        self.assert_named_image(button.get_child(), 'husk-start', 24)
        self.assertEqual(button.get_accessible().get_name(), 'Start')
        button.clicked()
        self.assertEqual(clicks, [True])


if __name__ == '__main__':
    unittest.main()

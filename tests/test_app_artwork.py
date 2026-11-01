"""Upstream brand assets stay present even when optional apps are absent."""
import hashlib
import os
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ARTWORK = ROOT / 'data/app-icons'


class UpstreamArtworkTests(unittest.TestCase):
    def test_assets_are_pinned_unmodified_upstream_bytes(self):
        for name, checksum in {
            'steam.png': 'b7087da76b8315024887b9a9313be5b9e6ba87d25eb624eac2d6542a823bb87d',
            'com.heroicgameslauncher.hgl.svg': '717865139e87a37bdbedf6afed1e6f7eba2eb93806c536f444afac0f24607ca5',
        }.items():
            with self.subTest(asset=name):
                self.assertEqual(hashlib.sha256((ARTWORK / name).read_bytes()).hexdigest(), checksum)

    def test_steam_is_real_256px_png_and_heroic_is_self_contained_vector(self):
        png = (ARTWORK / 'steam.png').read_bytes()
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', png[16:24]), (256, 256))
        svg = ET.parse(ARTWORK / 'com.heroicgameslauncher.hgl.svg').getroot()
        self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
        self.assertEqual(svg.attrib['viewBox'], '0 0 256 256')
        for element in svg.iter():
            self.assertNotIn(element.tag.rsplit('}', 1)[-1], ('script', 'image', 'foreignObject'))
            for attr, value in element.attrib.items():
                if attr.rsplit('}', 1)[-1] == 'href':
                    self.assertTrue(value.startswith('#'))

    def test_asset_licenses_and_primary_source_provenance_are_retained(self):
        readme = (ARTWORK / 'README.md').read_text()
        self.assertIn('repo.steampowered.com', readme)
        self.assertIn('Heroic-Games-Launcher/HeroicGamesLauncher', readme)
        self.assertIn('not covered by Husk', readme)
        self.assertIn('Valve Corporation', (ARTWORK / 'COPYRIGHT.Steam').read_text())
        self.assertIn('GNU GENERAL PUBLIC LICENSE', (ARTWORK / 'COPYING.Heroic').read_text())
        self.assertTrue((ARTWORK / 'LICENSE.Steam').is_file())


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1',
                     'Run with OWNOS_UI_TESTS=1 inside a test display')
class GTKUpstreamArtworkTests(unittest.TestCase):
    def test_optional_app_icons_load_offline_without_the_apps_installed(self):
        from ownos.ui import common
        common.require_display()
        for name in ('steam', 'com.heroicgameslauncher.hgl'):
            with self.subTest(name=name):
                image = common.icon(name, 48)
                self.assertEqual(image.get_icon_name()[0], name)
                pixbuf = common._icon_theme().load_icon(name, 48, common.Gtk.IconLookupFlags.FORCE_SIZE)
                self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (48, 48))


if __name__ == '__main__':
    unittest.main()

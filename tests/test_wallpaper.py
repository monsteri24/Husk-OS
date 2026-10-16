import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WallpaperTests(unittest.TestCase):
    def test_cover_keeps_aspect_ratio_at_common_output_sizes(self):
        from ownos.wallpaper import image_placement
        for width, height in ((1920, 1080), (2560, 1440), (3440, 1440), (1280, 1024), (1080, 1920)):
            with self.subTest(output=(width, height)):
                scale, x, y = image_placement(1536, 864, width, height)
                self.assertGreaterEqual(1536 * scale + 0.001, width)
                self.assertGreaterEqual(864 * scale + 0.001, height)
                self.assertAlmostEqual(x, (width - 1536 * scale) / 2)
                self.assertAlmostEqual(y, (height - 864 * scale) / 2)

    def test_contain_keeps_the_whole_image_and_rejects_invalid_sizes(self):
        from ownos.wallpaper import image_placement
        scale, x, y = image_placement(1536, 864, 1280, 1024, 'contain')
        self.assertAlmostEqual(scale, 1280 / 1536)
        self.assertGreater(y, 0)
        self.assertEqual(x, 0)
        for args in ((0, 864, 1920, 1080), (1536, 864, 0, 1080)):
            with self.assertRaises(ValueError): image_placement(*args)
        with self.assertRaises(ValueError): image_placement(1, 1, 1, 1, 'stretch')

    def test_defaults_select_the_supplied_wallpaper_without_a_background_process(self):
        from ownos.config import defaults
        from ownos.wallpaper import wallpaper_candidates
        self.assertEqual(defaults()['wallpaper'], '')
        candidates = wallpaper_candidates(defaults()['wallpaper'])
        original = ROOT / 'data/wallpapers/husk-desert.jpg'
        self.assertIn(original, candidates)
        self.assertTrue(original.is_file())
        self.assertEqual(original.read_bytes()[:2], b'\xff\xd8')

    def test_user_wallpaper_precedes_the_official_fallback(self):
        from ownos.wallpaper import wallpaper_candidates
        custom = Path('/tmp/my-wallpaper.png')
        choices = wallpaper_candidates(str(custom))
        self.assertEqual(choices[0], custom)
        self.assertEqual(choices[-1].name, 'husk-desert.jpg')

    def test_ui_package_contains_the_exact_wallpaper_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'ownos').symlink_to(ROOT, target_is_directory=True)
            dest = root / 'dest'; env = dict(os.environ, pkgdir=str(dest))
            result = subprocess.run(['bash', '--noprofile', '--norc', '-ec',
                'source "$1"; pkgname=ownos-ui; package_ownos-ui', 'wallpaper-package-test',
                str(ROOT / 'packaging/ownos/PKGBUILD')], cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = dest / 'usr/share/ownos/wallpapers/husk-desert.jpg'
            self.assertTrue(installed.is_file())
            self.assertEqual(hashlib.sha256(installed.read_bytes()).digest(),
                             hashlib.sha256((ROOT / 'data/wallpapers/husk-desert.jpg').read_bytes()).digest())


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1', 'Requires a prepared GTK display')
class WallpaperGTKTests(unittest.TestCase):
    def test_zero_monitor_transition_keeps_desktop_alive(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from ownos.ui.shell import HuskDesktop
        display = Mock()
        display.get_primary_monitor.return_value = None
        display.get_monitor.return_value = None
        desktop = SimpleNamespace(stopped=False, display=display, build_desktop=Mock(), layer=Mock())
        HuskDesktop.monitors_changed(desktop)
        desktop.build_desktop.assert_not_called()
        desktop.layer.set_monitor.assert_not_called()

    def test_invalid_user_image_falls_back_and_allocation_does_not_force_image_size(self):
        from ownos.ui.wallpaper import Wallpaper
        from ownos.ui.common import Gtk
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'broken.png'; path.write_text('not an image')
            image = Wallpaper(str(path))
            self.addCleanup(image.destroy)
            self.assertEqual(image.source_path.name, 'husk-desert.jpg')
            self.assertEqual((image.pixbuf.get_width(), image.pixbuf.get_height()), (1536, 864))
            self.assertIsInstance(image, Gtk.DrawingArea)
            self.assertEqual(image.get_preferred_width().minimum_width, 0)

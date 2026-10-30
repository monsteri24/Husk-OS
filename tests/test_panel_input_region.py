"""Panel input masks use real Cairo regions at the GDK boundary."""
from types import SimpleNamespace
import unittest

try:
    import cairo
    from ownos.ui.panel import Panel
    HAVE_GTK = True
except ImportError:
    HAVE_GTK = False


@unittest.skipUnless(HAVE_GTK, 'Requires PyGObject and Cairo')
class PanelInputRegionTests(unittest.TestCase):
    def test_desktop_mode_restores_the_whole_allocated_panel_with_a_real_region(self):
        regions = []
        native = SimpleNamespace(input_shape_combine_region=lambda region, x, y: regions.append((region, x, y)))
        panel = Panel.__new__(Panel)
        panel.mode = 'desktop'
        panel.window = SimpleNamespace(get_window=lambda: native, get_allocated_width=lambda: 1280,
                                       get_allocated_height=lambda: 54)
        self.assertFalse(panel.update_input_region())
        region, x, y = regions[-1]
        self.assertIsInstance(region, cairo.Region, 'PyGI rejects a None input region')
        self.assertEqual((x, y), (0, 0))
        self.assertEqual(region.get_extents(), cairo.RectangleInt(0, 0, 1280, 54))
        self.assertTrue(region.contains_point(0, 0))
        self.assertTrue(region.contains_point(1279, 53))
        self.assertFalse(region.contains_point(1280, 54))


if __name__ == '__main__': unittest.main()

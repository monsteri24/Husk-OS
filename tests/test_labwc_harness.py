import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class LabwcHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'scripts/test-labwc.py'
        spec = importlib.util.spec_from_file_location('husk_labwc_harness', path)
        harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(harness)
        cls.harness = harness

    def test_output_discovery_accepts_a_visible_window_without_name_or_class(self):
        tree = '''xwininfo: Window id: 0x50d (the root window) (has no name)
  Root window id: 0x50d (the root window) (has no name)
  2 children:
  0x400001 (has no name): ()  1024x768+0+0  +0+0
  0x400002 "tiny helper": ()  1x1+0+0  +0+0
'''
        self.assertEqual(self.harness.output_candidates(tree), ['0x400001'])

    def test_rendered_active_decoration_excludes_inactive_and_scattered_pixels(self):
        class Raster:
            width, height = 600, 90

            def load(self):
                return self

            def __getitem__(self, point):
                x, y = point
                if 80 <= x < 380 and 12 <= y < 38:
                    return (28, 48, 76)
                if 400 <= x < 590 and 50 <= y < 75:
                    return (22, 32, 51)  # The shipped inactive decoration.
                if x == 30 and y == 80:
                    return (28, 48, 76)
                return (0, 0, 0)

        self.assertEqual(self.harness.active_decoration_bounds(Raster()), [80, 12, 300, 26])

    def test_a_missing_rendered_decoration_cannot_guess_an_input_target(self):
        class Raster:
            width, height = 300, 100

            def load(self):
                return self

            def __getitem__(self, point):
                return (0, 0, 0)

        with self.assertRaisesRegex(AssertionError, 'No rendered'):
            self.harness.active_decoration_bounds(Raster())

    def test_widget_target_uses_the_rendered_decoration_and_relative_allocation(self):
        self.assertEqual(self.harness.client_widget_rectangle(
            [100, 50, 852, 30], [850, 560], [10, 20, 112, 36]), [111, 101, 112, 36])

    def test_a_different_window_width_is_rejected_before_sending_input(self):
        with self.assertRaisesRegex(AssertionError, 'does not match'):
            self.harness.client_widget_rectangle([10, 10, 900, 30], [460, 300], [20, 20, 112, 36])

    def test_missing_or_clipped_widget_allocations_cannot_receive_input(self):
        for allocation in (None, [-1, 10, 112, 36], [400, 10, 112, 36],
                           [10, 290, 112, 36], [10, 10, 0, 36]):
            with self.subTest(allocation=allocation), self.assertRaises(AssertionError):
                self.harness.client_widget_rectangle([10, 10, 460, 30], [460, 300], allocation)

    def test_same_position_row_clicks_and_pointer_moves_do_not_wait_for_motion(self):
        test = self.harness.DesktopTest.__new__(self.harness.DesktopTest)
        test.output = '0x200004'
        commands = []
        test.command = lambda argv: commands.append(argv)
        with tempfile.TemporaryDirectory() as directory, patch.object(self.harness.time, 'sleep'):
            test.artifacts = Path(directory)
            row = [240, 188, 800, 40]
            test.click(row)
            test.click(row)
            test.pointer_event('move', row)
            test.pointer_event('move', row)
        self.assertEqual(len(commands), 4)
        for command in commands:
            self.assertEqual(command[:2], ['xdotool', 'mousemove'])
            self.assertNotIn('--sync', command)
            self.assertEqual(command[command.index('--window') + 1:][:3], ['0x200004', '640', '208'])
        self.assertEqual(commands[0][-2:], ['click', '1'])
        self.assertEqual(commands[1][-2:], ['click', '1'])

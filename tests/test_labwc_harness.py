import importlib.util
from pathlib import Path
import unittest


class LabwcHarnessTests(unittest.TestCase):
    def test_output_discovery_accepts_a_visible_window_without_name_or_class(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/test-labwc.py'
        spec = importlib.util.spec_from_file_location('husk_labwc_harness', path)
        harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(harness)
        self.assertTrue(hasattr(harness, 'output_candidates'))
        tree = '''xwininfo: Window id: 0x50d (the root window) (has no name)
  Root window id: 0x50d (the root window) (has no name)
  2 children:
  0x400001 (has no name): ()  1024x768+0+0  +0+0
  0x400002 "tiny helper": ()  1x1+0+0  +0+0
'''
        self.assertEqual(harness.output_candidates(tree), ['0x400001'])


"""A diagnostic TTY must never take the live compositor's seat permanently."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


class BootHarnessTests(unittest.TestCase):
    def load_harness(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/ci-test-system1.py'
        spec = importlib.util.spec_from_file_location('husk_boot_harness', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_diagnostic_query_returns_to_the_compositor_vt(self):
        module = self.load_harness()
        self.assertTrue(hasattr(module, 'request_guest_evidence'))
        class Monitor:
            active = 1
            queried = False
            def key(self, keys): self.active = {'ctrl-alt-f1': 1, 'ctrl-alt-f2': 2}[keys]
            def type_console(self, text):
                self.queried = self.active == 2 and 'probe.py' in text
        monitor = Monitor()
        with patch.object(module.time, 'sleep'):
            module.request_guest_evidence(monitor)
        self.assertTrue(monitor.queried)
        self.assertEqual(monitor.active, 1)

    def test_failed_diagnostic_typing_still_restores_the_compositor_vt(self):
        module = self.load_harness()
        self.assertTrue(hasattr(module, 'request_guest_evidence'))
        class Monitor:
            active = 1
            def key(self, keys): self.active = {'ctrl-alt-f1': 1, 'ctrl-alt-f2': 2}[keys]
            def type_console(self, text): raise RuntimeError('keyboard disconnected')
        monitor = Monitor()
        with patch.object(module.time, 'sleep'), self.assertRaisesRegex(RuntimeError, 'keyboard disconnected'):
            module.request_guest_evidence(monitor)
        self.assertEqual(monitor.active, 1)

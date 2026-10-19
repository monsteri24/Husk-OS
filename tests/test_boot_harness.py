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

    def prior_evidence(self):
        build=dict(source_commit='candidate-source',iso_bytes=2147778560,
                   rootfs=dict(status='PASS'),v3_rootfs=dict(status='PASS'),release_file_eligible=False)
        boot=dict(iso_sha256='a'*64,iso_bytes=2147778560,boot='PASSED',terminal='PASSED',shutdown='PASSED',
                  problems=[],desktop_status=dict(os='Husk OS',desktop='Husk Desktop',backend='wayland',
                      version='v3-phase2',live=True,panel_visible=True,panel_mapped=True,
                      bridge_connected=True,desktop_surfaces=1))
        return build,boot

    def test_missing_prior_live_boot_requires_a_real_new_boot_even_when_payload_checks_pass(self):
        module=self.load_harness(); build,_=self.prior_evidence()
        self.assertIsNone(module.verified_recovered_boot(build,None,'candidate-source','a'*64,2147778560))

    def test_only_matching_successful_live_boot_evidence_can_be_reused(self):
        module=self.load_harness(); build,boot=self.prior_evidence()
        self.assertEqual(module.verified_recovered_boot(build,boot,'candidate-source','a'*64,2147778560),boot)
        for change in (dict(iso_sha256='b'*64),dict(iso_bytes=2147778561),dict(boot='FAILED'),
                       dict(terminal='NOT TESTED'),dict(shutdown='FAILED'),dict(problems=['failed']),
                       dict(desktop_status=dict(boot['desktop_status'],live=False)),
                       dict(desktop_status=dict(boot['desktop_status'],version='system-2'))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.verified_recovered_boot(build,dict(boot,**change),'candidate-source','a'*64,2147778560)

    def test_a_wrong_build_or_failed_payload_never_authorizes_evidence_reuse(self):
        module=self.load_harness(); build,boot=self.prior_evidence()
        for change in (dict(source_commit='other-source'),dict(iso_bytes=1),dict(rootfs=dict(status='FAIL')),
                       dict(v3_rootfs=dict(status='FAIL'))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.verified_recovered_boot(dict(build,**change),boot,'candidate-source','a'*64,2147778560)

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

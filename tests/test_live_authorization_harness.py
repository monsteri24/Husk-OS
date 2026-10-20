"""Acceptance must distinguish real Live authorization from root test injection."""
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LiveAuthorizationHarnessTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'scripts/ci-test-v3-live-auth.py'
        self.assertTrue(path.is_file(), 'Normal Live authorization acceptance is missing')
        spec = importlib.util.spec_from_file_location('live_auth_acceptance', path)
        self.harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.harness)

    def test_success_requires_every_real_authorization_check(self):
        valid = dict(finished=True, success=True,
                     checks={name: True for name in self.harness.REQUIRED_CHECKS})
        self.assertEqual(self.harness.validate_authorization_report(valid), [])
        for name in self.harness.REQUIRED_CHECKS:
            with self.subTest(missing=name):
                checks = dict(valid['checks']); checks.pop(name)
                self.assertTrue(self.harness.validate_authorization_report(dict(valid, checks=checks)))
            with self.subTest(failed=name):
                checks = dict(valid['checks']); checks[name] = False
                self.assertTrue(self.harness.validate_authorization_report(dict(valid, checks=checks)))
        self.assertTrue(self.harness.validate_authorization_report(dict(valid, finished=False)))
        self.assertTrue(self.harness.validate_authorization_report(dict(valid, success=False)))

    def test_delivered_observer_and_actual_gtk_client_compile(self):
        for name in ('ROOT_OBSERVER', 'GTK_CLIENT'):
            with self.subTest(source=name):
                ast.parse('CONFIG={}\n' + getattr(self.harness, name), filename=name)


if __name__ == '__main__':
    unittest.main()

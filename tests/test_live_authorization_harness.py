"""Acceptance must distinguish real Live authorization from root test injection."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

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

    def test_terminal_input_uses_the_shipped_labwc_shortcut(self):
        config = ET.parse(ROOT / 'config/labwc/rc.xml')
        action = config.find('.//keybind[@key="W-Return"]/action')
        self.assertIsNotNone(action)
        self.assertEqual(action.attrib, dict(name='Execute', command='foot'))
        monitor = Mock()
        window = SimpleNamespace(args=SimpleNamespace(timeout=120), alive=lambda: None,
            serial=SimpleNamespace(read=lambda: b''), ready_marker=b'not-ready', monitor=monitor,
            latest=lambda _: dict(stage='terminal-needed'))
        with patch.object(self.harness.time, 'monotonic', side_effect=[0, 1, 1, 121]), \
             patch.object(self.harness.time, 'sleep'), self.assertRaisesRegex(RuntimeError, 'deadline'):
            self.harness.AuthorizationAcceptance.live_authorization(window)
        monitor.key.assert_called_once_with('meta_l-ret')

    def test_terminal_bootstrap_does_not_assume_us_punctuation(self):
        monitor = Mock()
        window = SimpleNamespace(args=SimpleNamespace(timeout=120), alive=lambda: None,
            serial=SimpleNamespace(read=lambda: b''), ready_marker=b'not-ready', monitor=monitor,
            latest=lambda _: dict(stage='terminal-ready'))
        with patch.object(self.harness.time, 'monotonic', side_effect=[0, 1, 1, 121]), \
             patch.object(self.harness.time, 'sleep'), self.assertRaisesRegex(RuntimeError, 'deadline'):
            self.harness.AuthorizationAcceptance.live_authorization(window)
        monitor.console.assert_called_once_with('python3 huskauthcheck.py')

    def audit_matcher(self):
        source=ast.parse(self.harness.ROOT_OBSERVER)
        functions=[node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='authorized_exec_audit']
        self.assertEqual(len(functions),1,'Missing PID-bound pkexec audit verification')
        namespace={}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'audit-parser','exec'),namespace)
        return namespace['authorized_exec_audit']

    def test_pkexec_audit_identifies_the_actual_privileged_helper(self):
        match=self.audit_matcher()
        record=dict(SYSLOG_IDENTIFIER='pkexec',_PID='1240',
            MESSAGE='live: Executing command [USER=root] [TTY=unknown] [CWD=/home/live] [COMMAND=/usr/lib/ownos/husk-installer-root]')
        self.assertTrue(match([record],1240))

    def test_pkexec_audit_rejects_wrong_process_identity_target_and_denial(self):
        match=self.audit_matcher()
        record=dict(SYSLOG_IDENTIFIER='pkexec',_PID='1240',
            MESSAGE='live: Executing command [USER=root] [TTY=unknown] [CWD=/home/live] [COMMAND=/usr/lib/ownos/husk-installer-root]')
        for changes in (dict(_PID='1239'),dict(SYSLOG_IDENTIFIER='logger'),
                        dict(MESSAGE=record['MESSAGE'].replace('Executing command','Error executing command')),
                        dict(MESSAGE=record['MESSAGE'].replace('USER=root','USER=live')),
                        dict(MESSAGE=record['MESSAGE'].replace('husk-installer-root','different-helper')),
                        dict(MESSAGE=record['MESSAGE'].replace('live:','other:'))):
            with self.subTest(changes=changes):
                self.assertFalse(match([dict(record,**changes)],1240))
        self.assertFalse(match([],1240))


if __name__ == '__main__':
    unittest.main()

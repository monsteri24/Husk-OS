"""Reject package/authentication claims unsupported by the actual Live run."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from ownos.toplevel import ToplevelStore

ROOT = Path(__file__).resolve().parents[1]


class LiveApplicationAcceptanceTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'scripts/ci-test-v3-live-app.py'
        self.assertTrue(path.is_file(), 'Actual graphical package acceptance is missing')
        spec = importlib.util.spec_from_file_location('live_app_acceptance', path)
        self.harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.harness)

    def report(self):
        # Literal evidence contract: removing any check must reject the run.
        return dict(finished=True, success=True, package='steam 1.0.0.87-3',
            checks=dict(initial_package_absent=True, initial_password_empty=True,
                live_session_active=True, unprivileged_launcher=True,
                confirmation_cancel_unchanged=True, password_cancel_unchanged=True,
                authorization_cancel_unchanged=True, retry_existing_password=True,
                root_helper=True, pkexec_caller=True, no_test_injection=True,
                polkit_authenticated=True, full_upgrade=True,
                signatures_required=True, package_installed=True,
                official_icon=True, gtk_verified=True, no_extra_terminal=True,
                live_write_space=True, matching_graphics=True))

    def test_root_only_or_partial_transactions_cannot_pass(self):
        report = self.report()
        self.assertEqual(self.harness.validate_application_report(report), [])
        for name in report['checks']:
            with self.subTest(missing=name):
                checks = dict(report['checks']); checks.pop(name)
                self.assertTrue(self.harness.validate_application_report(dict(report, checks=checks)))
            with self.subTest(false=name):
                checks = dict(report['checks']); checks[name] = False
                self.assertTrue(self.harness.validate_application_report(dict(report, checks=checks)))
        for changes in (dict(finished=False), dict(success=False), dict(package=''),
                        dict(package='firefox 158.0-1')):
            self.assertTrue(self.harness.validate_application_report(dict(report, **changes)))

    def test_audit_requires_the_exact_pid_user_and_allowlisted_operation(self):
        match = self.harness.authorized_application_audit
        record = dict(SYSLOG_IDENTIFIER='pkexec', _PID='1240',
            MESSAGE='live: Executing command [USER=root] [TTY=unknown] [CWD=/home/live] [COMMAND=/usr/lib/ownos/own-admin install-confirmed steam]')
        self.assertTrue(match([record], 1240))
        for changes in (dict(_PID='1241'), dict(SYSLOG_IDENTIFIER='logger'),
                        dict(MESSAGE=record['MESSAGE'].replace('live:', 'other:')),
                        dict(MESSAGE=record['MESSAGE'].replace('USER=root', 'USER=live')),
                        dict(MESSAGE=record['MESSAGE'].replace('Executing command', 'Error executing command')),
                        dict(MESSAGE=record['MESSAGE'].replace(' steam]', ' firefox]')),
                        dict(MESSAGE=record['MESSAGE'].replace('install-confirmed', 'install'))):
            with self.subTest(changes=changes):
                self.assertFalse(match([dict(record, **changes)], 1240))
        self.assertFalse(match([], 1240))

    def test_embedded_real_gtk_and_read_only_observer_compile(self):
        for name in ('GTK_CLIENT', 'ROOT_OBSERVER'):
            with self.subTest(source=name):
                ast.parse('CONFIG={}\n' + getattr(self.harness, name), filename=name)

    @unittest.skipUnless(os.geteuid() == 0, 'Cross-UID file permissions require root; exercised in the real VM')
    def test_root_acknowledgement_has_private_live_user_ownership(self):
        source = ast.parse(self.harness.ROOT_OBSERVER)
        functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'acknowledge']
        with tempfile.TemporaryDirectory() as temporary:
            mappings = [list(map(int, line.split())) for line in Path('/proc/self/uid_map').read_text().splitlines()]
            if not any(start <= 1000 < start+count for start, _outside, count in mappings):
                self.skipTest('The local user namespace maps only root; actual cross-UID control is verified in the Live VM')
            directory = Path(temporary)
            directory.chmod(0o711)
            namespace = dict(os=os, directory=directory, uid=1000)
            exec(compile(ast.Module(body=functions, type_ignores=[]), 'observer-acknowledgement', 'exec'), namespace)
            previous = os.umask(0o077)
            try:
                namespace['acknowledge']('confirm-cancel')
            finally:
                os.umask(previous)
            control = directory/'control'
            self.assertEqual(control.read_text(), 'confirm-cancel')
            self.assertEqual(control.stat().st_uid, 1000)
            self.assertEqual(control.stat().st_mode & 0o777, 0o600)

    def test_client_startup_requires_a_real_native_process_and_noninstaller_window(self):
        self.assertTrue(callable(getattr(self.harness, 'validate_steam_launch', None)),
                        'A Steam client launch needs independent native-process/window validation')
        valid = dict(windows=[dict(app_id='steam', title='Steam')],
            processes=[dict(pid=1500, uid=1000, elf=True,
                executable='/home/live/.local/share/Steam/ubuntu12_32/steam')])
        self.assertEqual(self.harness.validate_steam_launch(valid), [])
        for changes in (dict(windows=[]), dict(processes=[]),
                        dict(windows=[dict(app_id='python3', title='Install Steam')]),
                        dict(windows=[dict(app_id='steam', title='Install Steam')]),
                        dict(processes=[dict(pid=1500, uid=0, elf=True,
                            executable='/home/live/.local/share/Steam/ubuntu12_32/steam')]),
                        dict(processes=[dict(pid=1500, uid=1000, elf=False,
                            executable='/usr/bin/steam')])):
            self.assertTrue(self.harness.validate_steam_launch(dict(valid, **changes)))

    def test_screenshots_are_suppressed_before_the_real_password_dialog_can_fill(self):
        keys = []
        window = SimpleNamespace(args=SimpleNamespace(timeout=120), alive=lambda: None,
            serial=SimpleNamespace(read=lambda: b''), ready_marker=b'not-ready', auth_started=False,
            latest=lambda _: dict(stage='authorization-cancel-confirmation'))
        window.monitor = SimpleNamespace(key=lambda key: keys.append((key, window.auth_started)))
        with patch.object(self.harness.time, 'monotonic', side_effect=[0,1,1,1,1,5,5,5,5,121]), \
             patch.object(self.harness.time, 'sleep'), self.assertRaisesRegex(RuntimeError, 'deadline'):
            self.harness.ApplicationAcceptance.live_authorization(window)
        self.assertEqual(keys, [('ret', True)])

    def test_a_visible_native_client_cannot_hide_a_full_live_filesystem_or_failed_update(self):
        validate = getattr(self.harness, 'validate_steam_startup', None)
        self.assertTrue(callable(validate), 'The real 8 GiB observation needs a bootstrap-health gate')
        native = dict(healthy_seconds=30, windows=[dict(app_id='steam', title='Sign in to Steam')],
            processes=[dict(pid=3937, uid=1000, elf=True,
                executable='/home/live/.local/share/Steam/ubuntu12_32/steam')])
        complete = '[15:27:05] Update complete, launching...\n'
        failed = ('[15:27:14] Extracting package...\n'
                  '[15:27:24] Error: Failed to unzip item 26 (package/tmp/ubuntu12_32/steamui.so_)\n')
        def observation(available, log):
            return dict(steam_launch=native, bootstrap_diagnostics=dict(
                live_write_space=dict(total_bytes=4155494400, available_bytes=available),
                logs={'logs/bootstrap_log.txt': log}))
        self.assertEqual(validate(observation(512000000, complete)), [])
        self.assertTrue(validate(observation(0, complete+failed)))
        self.assertTrue(validate(observation(512000000, complete+failed)))
        self.assertTrue(validate(observation(512000000, complete+'Extracting package...\n')))
        self.assertTrue(validate(observation(512000000, 'Downloading update (1 of 2 KB)...\n')))
        self.assertTrue(validate(dict(steam_launch=native)))
        for invalid in (None, -1, True, '512000000'):
            with self.subTest(available=invalid):
                self.assertTrue(validate(observation(invalid, complete)))
        # A later successful vendor retry supersedes its historical error.
        self.assertEqual(validate(observation(512000000, complete+failed+complete)), [])
        missing_native = observation(512000000, complete)
        missing_native['steam_launch'] = dict(windows=[], processes=[])
        self.assertTrue(validate(missing_native))

    def test_the_startup_deadline_cannot_replace_thirty_seconds_of_healthy_ui(self):
        report = dict(steam_launch=dict(healthy_seconds=1,
            windows=[dict(app_id='steam', title='Sign in to Steam')],
            processes=[dict(pid=3937, uid=1000, elf=True,
                executable='/home/live/.local/share/Steam/ubuntu12_32/steam')]),
            bootstrap_diagnostics=dict(live_write_space=dict(available_bytes=512000000),
                logs={'logs/bootstrap_log.txt':'Update complete, launching...\n'}))
        for seconds in (None, 0, 1, 29, True, '30', 241, float('nan'), float('inf')):
            with self.subTest(healthy_seconds=seconds):
                report['steam_launch']['healthy_seconds'] = seconds
                self.assertTrue(self.harness.validate_steam_startup(report),
                                'A final healthy snapshot cannot prove 30 continuous healthy seconds')
        report['steam_launch']['healthy_seconds'] = 30
        self.assertEqual(self.harness.validate_steam_startup(report), [])

    def test_a_closed_or_minimized_steam_window_is_not_a_current_startup_observation(self):
        observe = getattr(self.harness, 'observe_steam_windows', None)
        self.assertTrue(callable(observe), 'Startup stability must follow current native toplevel events')
        store = ToplevelStore()
        opened = dict(event='upsert', id=9, app_id='steam', title='Sign in to Steam',
                      active=True, minimized=False)
        self.assertEqual(len(observe(store, opened)), 1)
        self.assertEqual(observe(store, dict(event='closed', id=9)), [])
        self.assertEqual(len(observe(store, opened)), 1)
        self.assertEqual(observe(store, dict(opened, minimized=True)), [])
        self.assertEqual(len(observe(store, opened)), 1)
        self.assertEqual(observe(store, dict(opened, app_id='python3', title='Install Steam')), [])

    def test_bootstrap_process_diagnostics_omit_arguments_environment_and_unrelated_status(self):
        snapshot = getattr(self.harness, 'process_snapshot', None)
        self.assertTrue(callable(snapshot), 'The bounded bootstrap probe needs safe process observations')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); process = root/'1500'; process.mkdir()
            (process/'fd').mkdir()
            (process/'comm').write_text('tar\n')
            (process/'status').write_text('Name:\ttar\nState:\tS (sleeping)\nPPid:\t1499\nVmRSS:\t1024 kB\nPrivateField:\tstatus-secret\n')
            (process/'environ').write_text('PASSWORD=environment-secret')
            (process/'cmdline').write_text('argument-secret')
            (process/'wchan').write_text('pipe_read\n')
            (process/'exe').symlink_to('/usr/bin/tar')
            (process/'fd/0').symlink_to('/dev/pts/1')
            result = snapshot(root, os.getuid())
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['pid'], 1500)
            self.assertEqual(result[0]['comm'], 'tar')
            self.assertEqual(result[0]['wait_channel'], 'pipe_read')
            self.assertEqual(result[0]['stdin'], '/dev/pts/1')
            text = json.dumps(result)
            for secret in ('status-secret', 'environment-secret', 'argument-secret'):
                self.assertNotIn(secret, text)

    def test_optional_bootstrap_log_rotation_preserves_other_diagnostics(self):
        source = ast.parse(self.harness.ROOT_OBSERVER)
        functions = [node for node in source.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'bootstrap_diagnostics']
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steam = root/'home/live/.local/share/Steam'
            (steam/'logs').mkdir(parents=True)
            (steam/'logs/bootstrap_log.txt').write_text('first-start bootstrap')
            (steam/'logs/console-linux.txt').write_text('remaining observation')
            (root/'proc').mkdir()

            class RotatingPath(type(Path())):
                def read_text(path, *args, **kwargs):
                    if path.name == 'bootstrap_log.txt':
                        path.unlink()
                    return super().read_text(*args, **kwargs)

            namespace = dict(P=lambda filename: RotatingPath(root/str(filename).lstrip('/')),
                uid=os.getuid(), process_snapshot=self.harness.process_snapshot,
                command=lambda args: '', json=json, hashlib=hashlib, subprocess=subprocess,
                os=SimpleNamespace(statvfs=lambda path: os.statvfs(root)))
            exec(compile(ast.Module(body=functions, type_ignores=[]), 'bootstrap-diagnostics', 'exec'), namespace)
            try:
                result = namespace['bootstrap_diagnostics']()
            except OSError as error:
                self.fail('An optional log rotation aborted diagnostics: '+type(error).__name__)
            self.assertEqual(result['processes'], [])
            self.assertGreater(result['live_write_space']['total_bytes'], 0)
            self.assertEqual(result['logs']['logs/console-linux.txt'], 'remaining observation')
            self.assertNotIn('logs/bootstrap_log.txt', result['logs'])


if __name__ == '__main__':
    unittest.main()

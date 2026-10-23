"""Require real user Flatpak installation and current native Heroic startup."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import yaml

ROOT = Path(__file__).resolve().parents[1]


class LiveHeroicAcceptanceTests(unittest.TestCase):
    def setUp(self):
        path = ROOT/'scripts/ci-test-v3-live-heroic.py'
        self.assertTrue(path.is_file(), 'The next unverified user Flatpak path needs actual Live acceptance')
        spec = importlib.util.spec_from_file_location('heroic_acceptance', path)
        self.harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.harness)

    def report(self):
        return dict(finished=True, success=True, app_id='com.heroicgameslauncher.hgl',
            origin='flathub', deployment_commit='a'*64,
            checks=dict(initial_app_absent=True, initial_system_app_absent=True,
                live_session_active=True, unprivileged_launcher=True,
                confirmation_cancel_unchanged=True, password_unchanged=True,
                user_install_record=True, trusted_origin=True, system_packages_unchanged=True,
                no_system_install=True, official_icon=True, gtk_verified=True,
                no_extra_terminal=True),
            client_launch=dict(healthy_seconds=30, available_bytes=500000000,
                windows=[dict(app_id='heroic', title='Heroic Games Launcher', minimized=False)],
                processes=[dict(pid=1800, uid=1000, elf=True,
                    flatpak_id='com.heroicgameslauncher.hgl', executable='/app/bin/heroic/heroic')]))

    def test_partial_root_or_wrapper_observations_cannot_pass(self):
        report = self.report()
        self.assertEqual(self.harness.validate_heroic_report(report), [])
        for name in report['checks']:
            invalid = copy.deepcopy(report); invalid['checks'].pop(name)
            with self.subTest(missing=name):
                self.assertTrue(self.harness.validate_heroic_report(invalid))
        for changes in (dict(finished=False), dict(success=False), dict(origin='unreviewed'),
                        dict(deployment_commit=''), dict(app_id='other.application')):
            self.assertTrue(self.harness.validate_heroic_report(dict(report, **changes)))
        for changes in (dict(healthy_seconds=29), dict(healthy_seconds=True),
                        dict(available_bytes=0), dict(windows=[]), dict(processes=[]),
                        dict(windows=[dict(app_id='python3', title='Install Heroic', minimized=False)]),
                        dict(windows=[dict(app_id='heroic', title='Heroic', minimized=True)]),
                        dict(processes=[dict(pid=1800, uid=0, elf=True,
                            flatpak_id='com.heroicgameslauncher.hgl', executable='/app/bin/heroic/heroic')]),
                        dict(processes=[dict(pid=1800, uid=1000, elf=False,
                            flatpak_id='com.heroicgameslauncher.hgl', executable='/usr/bin/flatpak')])):
            invalid = copy.deepcopy(report); invalid['client_launch'].update(changes)
            with self.subTest(changes=changes):
                self.assertTrue(self.harness.validate_heroic_report(invalid))

    def test_shared_gtk_routes_default_steam_and_explicit_heroic_to_the_actual_app(self):
        tree = ast.parse(self.harness.GTK_CLIENT)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                 isinstance(node.func, ast.Name) and node.func.id in ('AppInstallWindow', 'launch_app')]
        self.assertEqual(len(calls), 2)
        for config, expected in (({}, 'steam'), ({'application':'heroic'}, 'heroic')):
            namespace = dict(CONFIG=config, window=object(), AppInstallWindow=lambda app: app,
                             launch_app=lambda app, _window: app)
            for call in calls:
                self.assertEqual(eval(compile(ast.Expression(call), 'actual-gtk-app-route', 'eval'), namespace), expected)

    def test_successful_installation_remains_passed_when_native_startup_fails(self):
        installed = self.report()
        installed.update(stage='installed-verified', finished=False, success=False)
        installed.pop('client_launch')
        failed = self.report()
        failed.update(stage='launch-observed')
        failed['client_launch'].update(healthy_seconds=0, windows=[], processes=[])
        with tempfile.TemporaryDirectory() as temporary:
            acceptance = SimpleNamespace(args=SimpleNamespace(timeout=120), alive=Mock(),
                serial=Mock(read=Mock(return_value=b'')), ready_marker=b'not-ready',
                latest=Mock(side_effect=[installed, failed]), artifacts=Path(temporary),
                monitor=Mock(), resources={}, result=dict(package_installation='FAILED'))
            with patch.object(self.harness.time, 'monotonic', side_effect=[0, 1, 1, 2, 2]), \
                    patch.object(self.harness.time, 'sleep'), self.assertRaises(RuntimeError):
                self.harness.HeroicAcceptance.live_authorization(acceptance)
            self.assertEqual(acceptance.result['package_installation'], 'PASSED')
            self.assertEqual(acceptance.result['client_startup'], 'FAILED')
            gate = object.__new__(self.harness.HeroicAcceptance)
            gate.result = acceptance.result
            with patch.object(self.harness.auth.AuthorizationAcceptance, 'run', return_value=0):
                self.assertEqual(gate.run(), 1)

    def test_cancel_baseline_includes_initialization_by_the_observers_own_query(self):
        self.assertTrue(hasattr(self.harness, 'user_flatpak_snapshot'),
                        'Snapshot after the backend query that may initialize an empty user repository')
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary)/'config'
            def query(*args):
                self.assertEqual(args, ('info', '--user', 'com.heroicgameslauncher.hgl'))
                if not config.exists(): config.write_text('[core]\nrepo_version=1\n')
                return SimpleNamespace(returncode=1)
            def repository():
                return hashlib.sha256(config.read_bytes()).hexdigest() if config.exists() else None
            self.assertIsNone(repository())
            snapshot = self.harness.user_flatpak_snapshot
            initial = snapshot(query, lambda: 'unchanged-system-packages', repository)
            self.assertTrue(initial['app_absent'])
            self.assertIsNotNone(initial['repository'])
            self.assertIsNone(initial['repository_before_query'])
            repeated = snapshot(query, lambda: 'unchanged-system-packages', repository)
            self.assertEqual(repeated['repository_before_query'], initial['repository'])
            self.assertEqual({key: repeated[key] for key in ('app_absent', 'packages', 'repository')},
                             {key: initial[key] for key in ('app_absent', 'packages', 'repository')})
            config.write_text('[remote "unexpected"]\nurl=https://example.invalid\n')
            self.assertNotEqual(snapshot(query, lambda: 'unchanged-system-packages', repository), initial)
            self.assertNotEqual(snapshot(query, lambda: 'changed-system-packages', repository), initial)
            installed = snapshot(lambda *args: SimpleNamespace(returncode=0),
                                 lambda: 'unchanged-system-packages', repository)
            self.assertFalse(installed['app_absent'])

    def test_cancel_cannot_hide_deleted_repository_behind_the_final_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary)/'config'
            def query(*args):
                if not config.exists(): config.write_text('[core]\nrepo_version=1\n')
                return SimpleNamespace(returncode=1)
            def repository():
                return hashlib.sha256(config.read_bytes()).hexdigest() if config.exists() else None
            packages = lambda: 'unchanged-system-packages'
            initial = self.harness.user_flatpak_snapshot(query, packages, repository)
            config.unlink()
            tree = ast.parse(self.harness.ROOT_OBSERVER)
            block = next(node for node in ast.walk(tree) if isinstance(node, ast.If) and
                         any(isinstance(value, ast.Constant) and value.value == 'confirmation-cancelled'
                             for value in ast.walk(node.test)))
            namespace = dict(user_flatpak_snapshot=self.harness.user_flatpak_snapshot,
                user_query=query, package_snapshot=packages, repository_snapshot=repository,
                initial_packages=initial['packages'], initial_repo=initial['repository'],
                state={}, checks={}, acknowledge=Mock())
            with self.assertRaisesRegex(RuntimeError, 'Cancel changed'):
                exec(compile(ast.Module(body=block.body, type_ignores=[]), 'actual-cancel-observer', 'exec'), namespace)
            self.assertFalse(namespace['checks']['confirmation_cancel_unchanged'])
            namespace['acknowledge'].assert_not_called()

    def test_current_heroic_windows_follow_the_existing_native_store(self):
        from ownos.toplevel import ToplevelStore
        observe = self.harness.steam.observe_client_windows
        store = ToplevelStore()
        event = dict(event='upsert', id=9, app_id='com.heroicgameslauncher.hgl',
                     title='Heroic Games Launcher', active=True, minimized=False)
        self.assertEqual(observe(store, event), [])
        self.assertEqual(len(observe(store, event, 'heroic')), 1)
        self.assertEqual(observe(store, dict(event='closed', id=9), 'heroic'), [])
        self.assertEqual(observe(store, event, 'unreviewed'), [])

    def test_embedded_actual_client_and_read_only_observer_compile(self):
        for name in ('GTK_CLIENT', 'ROOT_OBSERVER'):
            ast.parse('CONFIG={}\n'+getattr(self.harness, name), filename=name)

    def test_workflow_selects_only_the_reviewed_application_harness(self):
        workflow = yaml.safe_load((ROOT/'.github/workflows/v3-live-app.yml').read_text())
        step = next(step for step in workflow['jobs']['live-application']['steps']
                    if step.get('name') == 'Validate the immutable image request')
        script = step['run'].split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        for selection, expected in (('missing', 'steam'), ('heroic', 'heroic'),
                                    ('steam', 'steam'), ('unreviewed', None),
                                    ('heroic\nINJECTED=1', None)):
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); (directory/'.github').mkdir()
                request = dict(source='285fb33c7395ba622092079beeac1a9b09f084d3',
                    run=39720818758, sha256='3202758c52c029d98be852a6cc1217f863afffd8735e692368d0d51eb5ceea05',
                    bytes=2079227904, memory_mib=12288)
                if selection != 'missing': request['application'] = selection
                (directory/'.github/v3-live-app-request.json').write_text(json.dumps(request))
                output = directory/'environment'
                result = subprocess.run(['/usr/bin/python3','-c',script], cwd=directory,
                    env=dict(os.environ, GITHUB_ENV=str(output)), capture_output=True, text=True)
                if expected is None:
                    self.assertNotEqual(result.returncode, 0)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('HUSK_TEST_APPLICATION='+expected+'\n', output.read_text())

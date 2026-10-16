import importlib
import json
import tempfile
import unittest
from pathlib import Path


class CoreTests(unittest.TestCase):
    def setUp(self):
        try:
            for name in ('config', 'gaming', 'updates', 'installer', 'notifications', 'library', 'metrics', 'catalog'):
                setattr(self, name, importlib.import_module('ownos.' + name))
        except ImportError as exc:
            self.fail('Core behavior has not been implemented: ' + str(exc))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_corrupt_config_uses_defaults(self):
        p = self.root / 'settings.json'; p.write_text('{broken')
        self.assertTrue(self.config.ConfigStore(p).load()['gaming_mode'])

    def test_settings_persist_and_have_private_permissions(self):
        store = self.config.ConfigStore(self.root / 'config/settings.json')
        settings = store.load(); settings['overlay'] = True
        store.save(settings)
        self.assertTrue(store.load()['overlay'])
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(store.path.parent.glob('*.tmp')), [])

    def test_config_rejects_wrong_types_and_invalid_color(self):
        s = self.config.ConfigStore(self.root / 's.json')
        for key, val in [('gaming_mode', 'yes'), ('accent', 'url(evil)'), ('pointer_speed', 5), ('overlay', 1)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                cfg = s.load(); cfg[key] = val; s.save(cfg)

    def test_config_filters_unknown_keys(self):
        p = self.root / 's.json'; p.write_text(json.dumps({'shell': 'run anything', 'overlay': True}))
        settings = self.config.ConfigStore(p).load()
        self.assertNotIn('shell', settings)
        self.assertTrue(settings['overlay'])

    def test_game_wrapper_preserves_literal_arguments(self):
        settings = self.config.defaults(); settings['overlay'] = True
        command = self.gaming.game_command(['game', '$(touch /tmp/no)', 'a b'], settings,
                                         available=lambda name: '/usr/bin/' + name)
        self.assertEqual(command, ['/usr/bin/gamemoderun', '/usr/bin/mangohud', 'game', '$(touch /tmp/no)', 'a b'])

    def test_game_wrapper_disabled_does_not_change_command(self):
        cfg = self.config.defaults(); cfg['gaming_mode'] = False
        self.assertEqual(self.gaming.game_command(['game'], cfg), ['game'])

    def test_enabled_but_missing_game_tool_reports_error(self):
        with self.assertRaises(FileNotFoundError):
            self.gaming.game_command(['game'], self.config.defaults(), available=lambda _: None)

    def test_empty_game_command_is_rejected(self):
        with self.assertRaises(ValueError):
            self.gaming.game_command([], self.config.defaults())

    def test_update_is_a_full_transaction(self):
        self.assertEqual(self.updates.admin_command('update'), ['/usr/bin/pacman', '-Syu'])

    def test_app_install_includes_full_upgrade(self):
        cmd = self.updates.admin_command('install', 'steam')
        self.assertEqual(cmd, ['/usr/bin/pacman', '-Syu', '--needed', 'steam'])

    def test_privileged_install_rejects_arbitrary_packages(self):
        for name in ['steam; reboot', '--noconfirm', 'foo', '../../bin/bash']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.updates.admin_command('install', name)

    def test_privileged_action_rejects_arbitrary_commands(self):
        with self.assertRaises(ValueError):
            self.updates.admin_command('bash', 'steam')

    def test_kde_install_is_available_after_initial_install(self):
        cmd = self.updates.admin_command('desktop', 'kde')
        self.assertIn('plasma-desktop', cmd)
        self.assertIn('-Syu', cmd)

    def test_notification_replaces_only_active_identifier(self):
        store = self.notifications.NotificationStore()
        a = store.notify('app', 'first', 'body')
        b = store.notify('app', 'updated', '', replaces_id=a.id)
        self.assertEqual(a.id, b.id)
        self.assertEqual(len(store.history), 1)
        self.assertEqual(store.history[0].summary, 'updated')
        store.close(a.id)
        c = store.notify('app', 'new', '', replaces_id=a.id)
        self.assertNotEqual(c.id, a.id)

    def test_notifications_are_bounded(self):
        store = self.notifications.NotificationStore(limit=3)
        for i in range(8): store.notify('app', str(i), 'b')
        self.assertEqual(len(store.history), 3)
        self.assertEqual(store.history[-1].summary, '7')
        self.assertFalse(store.close(999))

    def test_own_desktop_plan_is_explicit(self):
        plan = self.installer.installation_plan('own', 'mesa')
        self.assertIn('ownos-desktop', plan.packages)
        self.assertEqual(plan.display_manager, 'sddm')
        self.assertNotIn('ownos-desktop', plan.remove)

    def test_other_desktop_choices_have_correct_login_manager(self):
        for desktop, pkg, dm in [('kde', 'plasma-desktop', 'sddm'), ('gnome', 'gnome-shell', 'gdm')]:
            with self.subTest(desktop=desktop):
                plan = self.installer.installation_plan(desktop, 'mesa')
                self.assertIn(pkg, plan.packages)
                self.assertIn('ownos-desktop', plan.remove)
                self.assertEqual(plan.display_manager, dm)

    def test_minimal_plan_has_no_desktop_or_display_manager(self):
        plan = self.installer.installation_plan('minimal', 'mesa')
        self.assertIsNone(plan.display_manager)
        self.assertNotIn('ownos-ui', plan.packages)
        self.assertIn('ownos-ui', plan.remove)
        self.assertIn('steam', plan.remove)

    def test_nvidia_driver_requires_explicit_selection(self):
        self.assertNotIn('nvidia-open-dkms', self.installer.installation_plan('own', 'mesa').packages)
        self.assertIn('nvidia-open-dkms', self.installer.installation_plan('own', 'nvidia-open').packages)

    def test_installer_rejects_missing_or_hostile_choices(self):
        for desktop, gpu in [('', 'mesa'), ('own;kde', 'mesa'), ('own', 'bad'), ('own', '--nodeps')]:
            with self.subTest(desktop=desktop, gpu=gpu), self.assertRaises(ValueError):
                self.installer.installation_plan(desktop, gpu)

    def test_root_installer_target_is_rejected(self):
        with self.assertRaises(ValueError): self.installer.validate_target('/')

    def test_symlink_installer_target_is_rejected(self):
        link = self.root / 'link'; link.symlink_to('/')
        with self.assertRaises(ValueError): self.installer.validate_target(str(link))

    def test_regular_directory_is_not_a_mounted_installer_target(self):
        with self.assertRaises(ValueError): self.installer.validate_target(str(self.root))

    def test_installer_target_requires_exact_os_identity(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='calamares-root-') as directory:
            target = Path(directory); (target / 'etc').mkdir()
            (target / 'etc/os-release').write_text('ID=ownos-evil\n')
            with patch.object(Path, 'is_mount', return_value=True), self.assertRaises(ValueError):
                self.installer.validate_target(directory)

    def test_steam_game_names_and_ids_are_read_from_manifests(self):
        apps = self.root / 'steamapps'; apps.mkdir()
        (apps / 'appmanifest_42.acf').write_text('"AppState" { "appid" "42" "name" "Test Game" "installdir" "Test" }')
        games = self.library.discover_steam_games([self.root])
        self.assertEqual([(g.appid, g.name) for g in games], [('42', 'Test Game')])

    def test_external_steam_library_and_duplicate_games(self):
        ext = self.root / 'Other Library'; (ext / 'steamapps').mkdir(parents=True)
        (ext / 'steamapps/appmanifest_55.acf').write_text('"AppState" { "appid" "55" "name" "Game" }')
        apps = self.root / 'steamapps'; apps.mkdir()
        (apps / 'libraryfolders.vdf').write_text('"libraryfolders" { "0" { "path" "' + str(ext) + '" } }')
        self.assertEqual(len(self.library.discover_steam_games([self.root, ext])), 1)

    def test_bad_manifest_never_crashes_game_discovery(self):
        apps = self.root / 'steamapps'; apps.mkdir()
        for name, contents in [('8', 'broken'), ('9', '"AppState" {'),
                               ('10', '"AppState" { "appid" "1;reboot" "name" "Bad" }')]:
            (apps / ('appmanifest_' + name + '.acf')).write_text(contents)
        self.assertEqual(self.library.discover_steam_games([self.root]), [])

    def test_vdf_handles_escaped_quotes_and_comments(self):
        text = '// note\n"a" { "name" "A \\"quoted\\" game" }'
        self.assertEqual(self.library.parse_vdf(text)['a']['name'], 'A "quoted" game')

    def test_memory_and_cpu_samples_are_real_and_valid(self):
        sampler = self.metrics.SystemSampler()
        sampler.sample(); sample = sampler.sample()
        self.assertGreater(sample['ram_total_bytes'], 0)
        self.assertLessEqual(sample['ram_used_bytes'], sample['ram_total_bytes'])
        self.assertGreaterEqual(sample['cpu_percent'], 0)
        self.assertLessEqual(sample['cpu_percent'], 100)

    def test_heroic_install_does_not_need_system_permissions(self):
        commands = self.catalog.install_commands('heroic')
        self.assertEqual(commands[-1], ['/usr/bin/flatpak', 'install', '--user', 'flathub', 'com.heroicgameslauncher.hgl'])
        self.assertFalse(any('pkexec' in cmd for cmd in commands))


if __name__ == '__main__':
    unittest.main()

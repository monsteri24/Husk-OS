"""Installed keyboard choices survive the first Husk session and user overrides."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ownos import config


ROOT = Path(__file__).resolve().parents[1]


class KeyboardFixture:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.keyboard = self.root / 'keyboard.json'
        self.system_path = patch.object(config, 'SYSTEM_KEYBOARD_PATH', self.keyboard, create=True)
        self.system_path.start(); self.addCleanup(self.system_path.stop)
        self.real_fstat = os.fstat
        def root_owned_file(descriptor):
            metadata = list(self.real_fstat(descriptor))
            metadata[4] = 0
            return os.stat_result(metadata)
        self.metadata = patch.object(config.os, 'fstat', side_effect=root_owned_file)
        self.metadata.start(); self.addCleanup(self.metadata.stop)
        self.store = config.ConfigStore(self.root / 'user/settings.json')

    def install_keyboard(self, layout='ee', variant='nodeadkeys'):
        self.keyboard.write_text(json.dumps({'layout': layout, 'variant': variant}))
        self.keyboard.chmod(0o644)

    def read_keyboard(self):
        self.assertTrue(hasattr(config, 'read_system_keyboard'), 'Installed keyboard record reader is missing')
        return config.read_system_keyboard(self.keyboard)


class InstalledKeyboardTests(KeyboardFixture, unittest.TestCase):
    def test_source_and_live_defaults_stay_finnish_without_an_installed_record(self):
        settings = self.store.load()
        self.assertEqual(settings['keymap'], 'fi')
        self.assertEqual(settings.get('keymap_variant'), '')

    def test_installed_record_sets_layout_and_variant_on_the_first_session(self):
        from ownos.session import prepare_session
        self.install_keyboard()
        settings = self.store.load()
        self.assertEqual(settings['keymap'], 'ee')
        self.assertEqual(settings.get('keymap_variant'), 'nodeadkeys')
        directory = prepare_session(self.root / 'labwc', ROOT / 'config/labwc', self.store)
        environment = (directory / 'environment').read_text().splitlines()
        self.assertIn('XKB_DEFAULT_LAYOUT=ee', environment)
        self.assertIn('XKB_DEFAULT_VARIANT=nodeadkeys', environment)

    def test_reader_accepts_only_a_root_owned_regular_nonwritable_record(self):
        self.install_keyboard()
        self.assertEqual(self.read_keyboard(), {'layout': 'ee', 'variant': 'nodeadkeys'})
        self.keyboard.chmod(0o666)
        self.assertIsNone(self.read_keyboard())
        self.keyboard.chmod(0o644)
        def untrusted_owner(descriptor):
            metadata = list(self.real_fstat(descriptor))
            metadata[4] = 12345
            return os.stat_result(metadata)
        with patch.object(config.os, 'fstat', side_effect=untrusted_owner):
            self.assertIsNone(self.read_keyboard())
        self.keyboard.rename(self.root / 'real.json')
        self.keyboard.symlink_to(self.root / 'real.json')
        self.assertIsNone(self.read_keyboard())

    def test_corrupt_or_oversized_record_falls_back_to_finnish(self):
        for data in ('{broken', '[]', '{"layout": "../us", "variant": ""}',
                     '{"layout": "us", "variant": "intl\\nEVIL=yes"}', ' ' * 4097):
            with self.subTest(data=data[:80]):
                self.keyboard.write_text(data); self.keyboard.chmod(0o644)
                self.assertEqual(self.store.load()['keymap'], 'fi')
                self.assertEqual(self.store.load().get('keymap_variant'), '')

    def test_record_validation_allows_single_xkb_identifiers_and_refuses_injection(self):
        self.assertTrue(hasattr(config, 'validate_keyboard_record'), 'Keyboard record validation is missing')
        self.assertEqual(config.validate_keyboard_record({'layout': 'latam', 'variant': 'nodeadkeys'}),
                         {'layout': 'latam', 'variant': 'nodeadkeys'})
        self.assertEqual(config.validate_keyboard_record({'layout': 'us', 'variant': 'colemak_dh'}),
                         {'layout': 'us', 'variant': 'colemak_dh'})
        for field in ('layout', 'variant'):
            for value in (True, None, [], '../us', 'us,fi', 'us(intl)', 'us\nEVIL=yes',
                          'us;touch bad', '$(touch bad)', 'a' * 65):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    config.validate_keyboard_record({'layout': 'us', 'variant': ''} | {field: value})

    def test_settings_preserve_explicit_user_layout_and_variant(self):
        self.install_keyboard()
        self.store.save(dict(self.store.load(), keymap='us', keymap_variant='dvorak'))
        settings = self.store.load()
        self.assertEqual((settings['keymap'], settings.get('keymap_variant')), ('us', 'dvorak'))

    def test_legacy_user_layout_override_clears_the_installed_variant(self):
        self.install_keyboard()
        self.store.path.parent.mkdir()
        self.store.path.write_text('{"keymap":"us", "overlay":true}')
        settings = self.store.load()
        self.assertEqual((settings['keymap'], settings.get('keymap_variant')), ('us', ''))
        self.assertTrue(settings['overlay'])

    def test_legacy_matching_layout_keeps_the_installed_variant(self):
        self.install_keyboard()
        self.store.path.parent.mkdir()
        self.store.path.write_text('{"keymap":"ee"}')
        settings = self.store.load()
        self.assertEqual((settings['keymap'], settings.get('keymap_variant')), ('ee', 'nodeadkeys'))

    def test_invalid_saved_variant_does_not_discard_valid_layout_or_appearance(self):
        self.install_keyboard()
        self.store.path.parent.mkdir()
        self.store.path.write_text(json.dumps({'keymap': 'us', 'keymap_variant': 'intl\nEVIL=yes',
                                               'accent': '#123abc'}))
        settings = self.store.load()
        self.assertEqual((settings['keymap'], settings.get('keymap_variant')), ('us', ''))
        self.assertEqual(settings['accent'], '#123abc')

    def test_layout_choices_keep_existing_options_and_include_the_installed_layout(self):
        self.install_keyboard()
        self.assertTrue(hasattr(config, 'keymap_options'), 'Installed layouts must remain selectable in Settings')
        self.assertEqual(config.keymap_options(), (*config.KEYMAPS, 'ee'))
        self.install_keyboard('de', '')
        self.assertEqual(config.keymap_options(), config.KEYMAPS)
        with self.assertRaises(ValueError):
            self.store.save(dict(self.store.load(), keymap='unrecorded'))

    def test_input_environment_replaces_stale_values_and_explicitly_clears_variant(self):
        from ownos.input_config import write_input_config
        self.install_keyboard()
        directory = self.root / 'labwc'; directory.mkdir()
        (directory / 'environment').write_text('CUSTOM=keep\nXKB_DEFAULT_LAYOUT=fi\n'
                                               'XKB_DEFAULT_VARIANT=old\nXKB_DEFAULT_VARIANT=duplicate\n')
        settings = dict(self.store.load(), keymap='us', keymap_variant='')
        write_input_config(directory, ROOT / 'config/labwc/rc.xml', settings)
        self.assertEqual((directory / 'environment').read_text(),
                         'CUSTOM=keep\nXKB_DEFAULT_LAYOUT=us\nXKB_DEFAULT_VARIANT=\n')
        with self.assertRaises(ValueError):
            write_input_config(directory, ROOT / 'config/labwc/rc.xml', dict(settings, keymap_variant='a\nBAD=yes'))
        self.assertNotIn('BAD=', (directory / 'environment').read_text())


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1', 'Requires a prepared GTK display')
class InstalledKeyboardUITests(KeyboardFixture, unittest.TestCase):
    def test_settings_adds_installed_layout_and_clears_variant_only_after_layout_change(self):
        from ownos.ui.control import ControlWindow
        self.install_keyboard()
        window = ControlWindow(store=self.store, page='input')
        self.addCleanup(window.destroy)
        self.assertEqual(window.keymap.get_active_id(), 'ee')
        with patch('ownos.ui.control.shutil.which', return_value=None):
            window.apply_input(None)
        self.assertEqual(self.store.load()['keymap_variant'], 'nodeadkeys')
        self.assertTrue(window.keymap.set_active_id('us'))
        with patch('ownos.ui.control.shutil.which', return_value=None):
            window.apply_input(None)
        self.assertEqual(self.store.load()['keymap'], 'us')
        self.assertEqual(self.store.load()['keymap_variant'], '')
        self.assertIn('XKB_DEFAULT_VARIANT=\n', (self.store.path.parent / 'labwc/environment').read_text())


if __name__ == '__main__':
    unittest.main()

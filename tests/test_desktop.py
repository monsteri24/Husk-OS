import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


class DesktopPolicyTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos import toplevel, input_config
        except ImportError as exc:
            self.fail('Desktop message/input validation is missing: ' + str(exc))

    def test_invalid_bridge_messages_leave_window_list_unchanged(self):
        from ownos.toplevel import ToplevelStore
        store = ToplevelStore()
        valid = dict(event='upsert', id=3, title='Game', app_id='game', active=True, minimized=False)
        self.assertTrue(store.apply(valid))
        for message in [[], None, {'event': 'upsert', 'id': '3;close'},
                        dict(valid, title=[]), dict(valid, id=True), dict(valid, active='yes')]:
            with self.subTest(message=message):
                self.assertFalse(store.apply(message))
                self.assertEqual(store.entries[3]['title'], 'Game')
        self.assertTrue(store.apply({'event': 'closed', 'id': 3}))
        self.assertEqual(store.entries, {})

    def test_bridge_window_list_is_bounded(self):
        from ownos.toplevel import ToplevelStore
        store = ToplevelStore(limit=2)
        for id in range(1, 8):
            store.apply(dict(event='upsert', id=id, title='Game', app_id='game', active=False, minimized=False))
        self.assertEqual(list(store.entries), [6, 7])

    def test_input_settings_preserve_keybindings_and_environment(self):
        from ownos.input_config import write_input_config
        from ownos.config import defaults
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / 'template.xml'
            template.write_text('<labwc_config><keyboard><keybind key="W-e"/></keyboard></labwc_config>')
            config = root / 'labwc'; config.mkdir()
            (config / 'environment').write_text('CUSTOM=keep\nXKB_DEFAULT_LAYOUT=us\n')
            settings = defaults(); settings.update(keymap='fi', pointer_speed=-0.35)
            write_input_config(config, template, settings)
            xml = ET.parse(config / 'rc.xml')
            self.assertEqual(xml.find('keyboard/keybind').get('key'), 'W-e')
            self.assertEqual(xml.find("libinput/device[@category='mouse']/pointerSpeed").text, '-0.35')
            self.assertEqual(xml.find("libinput/device[@category='mouse']/accelProfile").text, 'flat')
            self.assertEqual((config / 'environment').read_text(), 'CUSTOM=keep\nXKB_DEFAULT_LAYOUT=fi\nXKB_DEFAULT_VARIANT=\n')
            self.assertEqual(list(config.glob('*.tmp')), [])

    def test_invalid_input_settings_do_not_create_configuration(self):
        from ownos.input_config import write_input_config
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'labwc'
            with self.assertRaises(ValueError):
                write_input_config(config, Path('missing.xml'), {'keymap': 'fi\nEVIL=1'})
            self.assertFalse(config.exists())


if __name__ == '__main__':
    unittest.main()

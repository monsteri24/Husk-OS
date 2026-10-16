import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from ownos.config import ConfigStore
from ownos.session import prepare_session


ROOT = Path(__file__).resolve().parents[1]
WINDOW_CONTROLS = {'Close': 'Close', 'Iconify': 'Iconify', 'Maximize': 'ToggleMaximize'}
SYSTEM1_MOUSE = '''<mouse>
  <context name="Titlebar">
    <mousebind button="Left" action="Drag"><action name="Move"/></mousebind>
    <mousebind button="Left" action="DoubleClick"><action name="ToggleMaximize"/></mousebind>
  </context>
  <context name="Frame">
    <mousebind button="A-Left" action="Drag"><action name="Move"/></mousebind>
    <mousebind button="A-Right" action="Drag"><action name="Resize"/></mousebind>
  </context>
  <context name="Client">
    <mousebind button="Left" action="Press"><action name="Focus"/><action name="Raise"/></mousebind>
  </context>
</mouse>'''


class WindowBindingTests(unittest.TestCase):
    def assert_control(self, root, context, action):
        binding = root.find(f"mouse/context[@name='{context}']/mousebind[@button='Left'][@action='Click']")
        self.assertIsNotNone(binding, context + ' needs a left-click binding')
        self.assertEqual([child.get('name') for child in binding.findall('action')], [action])

    def prepare_saved(self, root, mouse):
        directory = root / 'labwc'
        directory.mkdir()
        (directory / 'rc.xml').write_text(
            '<labwc_config><keyboard><keybind key="W-f">'
            '<action name="Execute" command="custom-files"/>'
            '</keybind></keyboard>' + mouse + '</labwc_config>')
        store = ConfigStore(root / 'settings.json')
        prepare_session(directory, ROOT / 'config/labwc', store)
        return directory, store

    def test_stock_window_controls_have_left_click_actions(self):
        root = ET.parse(ROOT / 'config/labwc/rc.xml').getroot()
        for context, action in WINDOW_CONTROLS.items():
            with self.subTest(context=context):
                self.assert_control(root, context, action)

    def test_saved_system1_controls_are_repaired_at_session_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy = ET.fromstring(SYSTEM1_MOUSE)
            original_contexts = [ET.tostring(context) for context in legacy]
            directory, store = self.prepare_saved(Path(tmp), SYSTEM1_MOUSE)
            root = ET.parse(directory / 'rc.xml').getroot()
            for context, action in WINDOW_CONTROLS.items():
                self.assert_control(root, context, action)
            self.assertEqual([ET.tostring(context) for context in root.find('mouse')][:3], original_contexts)
            self.assertEqual(root.find('keyboard/keybind/action').get('command'), 'custom-files')
            before = (directory / 'rc.xml').read_bytes()
            prepare_session(directory, ROOT / 'config/labwc', store)
            self.assertEqual((directory / 'rc.xml').read_bytes(), before)

    def test_existing_control_contexts_keep_custom_actions_and_no_ops(self):
        customizations = [
            ('Close', '<context name="cLoSe"><mousebind button="Left" action="Click">'
             '<action name="Execute" command="custom-close"/></mousebind></context>'),
            ('Iconify', '<context name="Iconify"><mousebind button="Left" action="Click"/></context>'),
            ('Maximize', '<context><name>Maximize</name><mousebind button="Right" action="Click">'
             '<action name="Execute" command="custom-maximize"/></mousebind></context>'),
            ('Close', '<context name="Close"/>'),
        ]
        for customized_control, customization in customizations:
            with self.subTest(context=customized_control, customization=customization), tempfile.TemporaryDirectory() as tmp:
                mouse = ET.fromstring(SYSTEM1_MOUSE)
                mouse.append(ET.fromstring(customization))
                before = ET.tostring(mouse[-1])
                directory, _ = self.prepare_saved(Path(tmp), ET.tostring(mouse, encoding='unicode'))
                root = ET.parse(directory / 'rc.xml').getroot()
                contexts = root.findall('mouse/context')
                self.assertEqual(ET.tostring(contexts[3]), before)
                self.assertEqual(len(contexts), 6)
                for context, action in WINDOW_CONTROLS.items():
                    if context != customized_control:
                        self.assert_control(root, context, action)

    def test_explicit_default_mouse_bindings_are_not_replaced(self):
        mouse = '''<mouse><default/>
          <context name="Close"><mousebind button="Left" action="Click"/></context>
          <context name="Frame"><mousebind button="W-Right" action="Drag">
            <action name="Execute" command="custom-resize"/>
          </mousebind></context>
        </mouse>'''
        with tempfile.TemporaryDirectory() as tmp:
            directory, _ = self.prepare_saved(Path(tmp), mouse)
            self.assertEqual(ET.tostring(ET.parse(directory / 'rc.xml').find('mouse')),
                             ET.tostring(ET.fromstring(mouse)))

    def test_configs_without_mouse_bindings_keep_implicit_defaults(self):
        for mouse in ['', '<mouse/>', '<mouse><doubleClickTime>400</doubleClickTime></mouse>',
                      '<mouse><context name="Close"/></mouse>']:
            with self.subTest(mouse=mouse), tempfile.TemporaryDirectory() as tmp:
                directory, _ = self.prepare_saved(Path(tmp), mouse)
                after = ET.parse(directory / 'rc.xml').find('mouse')
                self.assertEqual(ET.tostring(after) if after is not None else '',
                                 ET.tostring(ET.fromstring(mouse)) if mouse else '')


if __name__ == '__main__': unittest.main()

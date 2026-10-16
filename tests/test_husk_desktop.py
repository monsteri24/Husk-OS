import tempfile
import unittest
from pathlib import Path


class HuskDesktopPolicyTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos import identity, desktop_layout, themes
            self.identity, self.layout, self.themes = identity, desktop_layout, themes
        except ImportError as exc: self.fail('Husk identity/modular layout is missing: ' + str(exc))

    def test_public_identity_is_husk_and_arch_base_is_explicit(self):
        self.assertEqual(self.identity.OS_NAME, 'Husk OS')
        self.assertEqual(self.identity.DESKTOP_NAME, 'Husk Desktop')
        self.assertEqual(self.identity.TECHNICAL_BASE, 'Arch Linux')

    def test_public_cli_aliases_preserve_legacy_behavior(self):
        from ownos.cli import normalize_command
        for public, legacy in [('husk-desktop','own-shell'),('husk-files','own-files'),
                               ('husk-control','own-control'),('husk-game','own-game'),
                               ('husk-install-app','own-install-app'),('husk-status','own-status')]:
            with self.subTest(public=public):
                self.assertEqual(normalize_command(public), legacy)
                self.assertEqual(normalize_command(legacy), legacy)

    def test_panel_and_popup_edges_move_together(self):
        from ownos.config import defaults
        settings = defaults()
        for position, edge in [('bottom','BOTTOM'),('top','TOP')]:
            settings['taskbar_position'] = position
            layout = self.layout.layout(settings)
            self.assertEqual(layout['panel_anchors'], (edge,'LEFT','RIGHT'))
            self.assertEqual(layout['popup_edge'], edge)

    def test_old_settings_get_default_layout_without_losing_gaming_choices(self):
        from ownos.config import ConfigStore
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'settings.json'
            path.write_text('{"gaming_mode":false,"overlay":true,"accent":"#abcdef"}')
            settings = ConfigStore(path).load()
            self.assertEqual(settings['taskbar_position'], 'bottom')
            self.assertFalse(settings['gaming_mode']); self.assertTrue(settings['overlay'])
            self.assertEqual(settings['accent'], '#abcdef')

    def test_bad_layout_setting_is_rejected(self):
        from ownos.config import validate
        for value in ['left','bottom;reboot',True,None]:
            with self.subTest(value=value), self.assertRaises(ValueError): validate({'taskbar_position': value})

    def test_user_css_is_utf8_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'desktop.css'
            self.assertEqual(self.themes.read_user_css(path), b'')
            path.write_text('.panel { padding: 10px; }')
            self.assertEqual(self.themes.read_user_css(path), b'.panel { padding: 10px; }')
            path.write_bytes(b'x' * 65537)
            with self.assertRaises(ValueError): self.themes.read_user_css(path)
            path.write_bytes(b'\xff')
            with self.assertRaises(ValueError): self.themes.read_user_css(path)


if __name__ == '__main__': unittest.main()

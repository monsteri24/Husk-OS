import unittest
from unittest.mock import patch
import io
import contextlib
import json


class HuskLivePolicyTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos import live
            self.live = live
        except ImportError as exc:self.fail('Live readiness policy is missing: ' + str(exc))

    def status(self):
        return dict(os='Husk OS', desktop='Husk Desktop', version='0.1.1-dev', live=True,
                    backend='wayland', desktop_surfaces=1, panel_visible=True,
                    panel_mapped=True, bridge_connected=True)

    def test_real_live_status_can_pass_acceptance(self):
        self.assertEqual(self.live.validate_live_status(self.status()), [])

    def test_preview_or_unmapped_desktop_is_not_a_live_boot_success(self):
        for field,value in [('backend','preview'),('live',False),('panel_mapped',False),
                            ('desktop_surfaces',0),('bridge_connected',False),('os','Other OS')]:
            with self.subTest(field=field):
                status=self.status();status[field]=value
                self.assertTrue(self.live.validate_live_status(status))
        self.assertTrue(self.live.validate_live_status([]))

    def test_virtual_graphics_fallback_preserves_explicit_renderer(self):
        self.assertEqual(self.live.choose_renderer('qemu',''), 'pixman')
        self.assertEqual(self.live.choose_renderer('oracle',''), 'pixman')
        self.assertEqual(self.live.choose_renderer('none',''), '')
        self.assertEqual(self.live.choose_renderer('docker',''), '')
        self.assertEqual(self.live.choose_renderer('qemu','gles2'), 'gles2')

    def test_status_rejects_non_object_or_oversized_dbus_reply(self):
        for payload in ['[]', 'broken', ' ' * 65537]:
            with self.subTest(payload=payload[:10]), self.assertRaises(ValueError):
                self.live.desktop_status(fetch=lambda:payload)
        self.assertEqual(self.live.desktop_status(fetch=lambda:json.dumps(self.status())),self.status())

    def test_live_smoke_cli_returns_failure_for_preview_and_success_for_live_status(self):
        from ownos import cli
        for mapped, expected in [(False,1),(True,0)]:
            status=self.status(); status['panel_mapped']=mapped
            with patch('sys.argv',['husk-live-smoke']), patch('ownos.live.desktop_status',return_value=status), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(),expected)

    def test_renderer_probe_is_read_only_and_preserves_user_choice(self):
        self.assertEqual(self.live.session_renderer(current='gles2',detect=lambda:'qemu'),'gles2')
        self.assertEqual(self.live.session_renderer(current='',detect=lambda:'qemu'),'pixman')
        self.assertEqual(self.live.session_renderer(current='',detect=lambda:'none'),'')


if __name__ == '__main__':unittest.main()

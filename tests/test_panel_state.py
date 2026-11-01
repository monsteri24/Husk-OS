"""Compositor state, including output identity, controls panel reservations."""
import unittest

from ownos.toplevel import ToplevelStore


def window(**changes):
    message = dict(event='upsert', id=1, title='Game', app_id='game', active=True,
                   minimized=False, maximized=False, fullscreen=False,
                   outputs=[dict(name='DP-1', x=0, y=0, width=1920, height=1080)])
    message.update(changes)
    return message


class WindowStateBoundaryTests(unittest.TestCase):
    def test_compositor_maximized_fullscreen_and_outputs_are_preserved(self):
        store = ToplevelStore()
        message = window(maximized=True, fullscreen=True)
        self.assertTrue(store.apply(message))
        self.assertTrue(store.entries[1].get('maximized'))
        self.assertTrue(store.entries[1].get('fullscreen'))
        self.assertEqual(store.entries[1].get('outputs'), message['outputs'])
        message['outputs'][0]['name'] = 'mutated'
        self.assertEqual(store.entries[1]['outputs'][0]['name'], 'DP-1')

    def test_legacy_bridge_messages_keep_working_without_new_state(self):
        store = ToplevelStore()
        message = window()
        for key in ('maximized', 'fullscreen', 'outputs'):
            message.pop(key)
        self.assertTrue(store.apply(message))
        self.assertFalse(store.entries[1].get('maximized', False))
        self.assertFalse(store.entries[1].get('fullscreen', False))

    def test_invalid_extended_state_cannot_replace_a_valid_window(self):
        store = ToplevelStore()
        valid = window()
        self.assertTrue(store.apply(valid))
        malformed = [dict(maximized=1), dict(fullscreen='true'), dict(outputs=None), dict(outputs='DP-1'),
                     dict(outputs=[None]), dict(outputs=[dict(name='DP-1')]),
                     dict(outputs=[dict(name='DP-1', x=True, y=0, width=1920, height=1080)]),
                     dict(outputs=[dict(name='DP-1', x=0, y=0, width=-1, height=1080)]),
                     dict(outputs=valid['outputs'] * 33)]
        for changes in malformed:
            with self.subTest(changes=changes):
                self.assertFalse(store.apply(window(title='bad', **changes)))
                self.assertEqual(store.entries[1]['title'], 'Game')


class PanelOutputPolicyTests(unittest.TestCase):
    def mode(self, entries, **changes):
        try:
            from ownos.panel_state import panel_mode
        except ImportError:
            self.fail('The output-aware panel policy is missing')
        options = dict(output_name='DP-1', geometry=(0, 0, 1920, 1080), monitor_count=2)
        options.update(changes)
        return panel_mode(entries, **options)

    def test_normal_maximized_fullscreen_and_restore(self):
        store = ToplevelStore()
        self.assertEqual(self.mode(store.entries.values()), 'desktop')
        for flags, expected in [(dict(maximized=True), 'maximized'),
                                (dict(maximized=True, fullscreen=True), 'fullscreen'),
                                (dict(maximized=True), 'maximized'), ({}, 'desktop')]:
            self.assertTrue(store.apply(window(**flags)))
            self.assertEqual(self.mode(store.entries.values()), expected)

    def test_fullscreen_on_a_different_monitor_keeps_the_primary_panel(self):
        other = [dict(name='HDMI-A-1', x=1920, y=0, width=1920, height=1080)]
        self.assertEqual(self.mode([window(fullscreen=True, outputs=other)]), 'desktop')
        self.assertEqual(self.mode([window(maximized=True, outputs=other)]), 'desktop')

    def test_minimized_and_closed_windows_restore_the_panel(self):
        store = ToplevelStore()
        store.apply(window(fullscreen=True, minimized=True))
        self.assertEqual(self.mode(store.entries.values()), 'desktop')
        store.apply(window(fullscreen=True))
        store.apply(dict(event='closed', id=1))
        self.assertEqual(self.mode(store.entries.values()), 'desktop')

    def test_known_output_name_is_authoritative_even_for_cloned_geometry(self):
        other = [dict(name='HDMI-A-1', x=0, y=0, width=1920, height=1080)]
        self.assertEqual(self.mode([window(fullscreen=True, outputs=other)]), 'desktop')

    def test_geometry_matches_compositors_without_output_names(self):
        unnamed = [dict(name='', x=0, y=0, width=1920, height=1080)]
        self.assertEqual(self.mode([window(fullscreen=True, outputs=unnamed)]), 'fullscreen')
        other = [dict(name='', x=1920, y=0, width=1920, height=1080)]
        self.assertEqual(self.mode([window(fullscreen=True, outputs=other)]), 'desktop')

    def test_missing_output_identity_is_only_safe_on_a_single_monitor(self):
        legacy = window(fullscreen=True)
        legacy.pop('outputs')
        self.assertEqual(self.mode([legacy]), 'desktop')
        self.assertEqual(self.mode([legacy], monitor_count=1), 'fullscreen')

    def test_an_explicit_empty_membership_does_not_hide_the_remaining_monitor(self):
        self.assertEqual(self.mode([window(fullscreen=True, outputs=[])], monitor_count=1), 'desktop')


if __name__ == '__main__':
    unittest.main()

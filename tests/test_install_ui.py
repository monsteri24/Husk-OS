"""Confirmation input policy, plus GTK wiring in a prepared test display."""
import os
import unittest
from unittest.mock import patch

try:
    from ownos.dialog_input import FreshActivation
except ModuleNotFoundError as exc:
    if exc.name != 'ownos.dialog_input':
        raise
    FreshActivation = None


class ConfirmationInputTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(FreshActivation, 'A fresh activation policy is required')
        self.activation = FreshActivation()

    def test_an_inherited_release_without_an_ok_press_cannot_confirm(self):
        self.assertFalse(self.activation.pointer_release(1, inside=True))

    def test_a_press_outside_ok_and_release_inside_ok_cannot_confirm(self):
        self.activation.pointer_press(1, inside=False)
        self.assertFalse(self.activation.pointer_release(1, inside=True))

    def test_dragging_off_ok_cancels_the_entire_pointer_activation(self):
        self.activation.pointer_press(1, inside=True)
        self.assertFalse(self.activation.pointer_release(1, inside=False))
        self.assertFalse(self.activation.pointer_release(1, inside=True))

    def test_a_fresh_primary_pointer_pair_confirms_once(self):
        self.activation.pointer_press(1, inside=True)
        self.assertTrue(self.activation.pointer_release(1, inside=True))
        self.assertFalse(self.activation.pointer_release(1, inside=True))

    def test_another_button_cannot_complete_the_primary_pointer_press(self):
        self.activation.pointer_press(1, inside=True)
        self.assertFalse(self.activation.pointer_release(3, inside=True))
        self.activation.pointer_press(3, inside=True)
        self.assertFalse(self.activation.pointer_release(3, inside=True))

    def test_losing_focus_or_leaving_the_button_cancels_an_armed_activation(self):
        self.activation.pointer_press(1, inside=True)
        self.activation.cancel()
        self.assertFalse(self.activation.pointer_release(1, inside=True))
        self.activation.key_press(32)
        self.activation.cancel()
        self.assertFalse(self.activation.key_release(32))

    def test_fresh_space_and_enter_pairs_confirm_only_on_release(self):
        for key in (32, 65293, 65421):
            with self.subTest(key=key):
                self.assertFalse(self.activation.key_release(key))
                self.activation.key_press(key)
                self.assertTrue(self.activation.key_release(key))
                self.assertFalse(self.activation.key_release(key))

    def test_the_held_opening_key_must_be_released_before_a_fresh_activation(self):
        for key in (32, 65293, 65421):
            with self.subTest(key=key):
                activation = FreshActivation(opening_key=key)
                activation.key_press(key)  # Autorepeat from the opening key.
                activation.key_press(key)
                self.assertFalse(activation.key_release(key))
                activation.key_press(key)
                self.assertTrue(activation.key_release(key))

    def test_dialog_can_identify_the_held_opening_key_until_its_release(self):
        activation = FreshActivation(opening_key=65293)
        pending = getattr(activation, 'is_opening_key', None)
        self.assertIsNotNone(pending, 'Dialogs need to guard the held opening key before default activation')
        self.assertTrue(pending(65293))
        self.assertFalse(pending(32))
        activation.key_press(65293)  # Repeat does not clear the opening hold.
        self.assertTrue(pending(65293))
        self.assertFalse(activation.key_release(65293))
        self.assertFalse(pending(65293))

    def test_modifiers_or_mismatched_keys_do_not_confirm(self):
        self.activation.key_press(32, modified=True)
        self.assertFalse(self.activation.key_release(32))
        self.activation.key_press(32)
        self.assertFalse(self.activation.key_release(32, modified=True))
        self.activation.key_press(32)
        self.assertFalse(self.activation.key_release(65293))


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1',
                     'Run with OWNOS_UI_TESTS=1 inside a test display')
class InstallationGTKTests(unittest.TestCase):
    def setUp(self):
        from ownos.ui import common
        self.common = common
        self.Gtk, self.Gdk = common.Gtk, common.Gdk
        self.assertIsNotNone(getattr(common, 'ConfirmationDialog', None),
                             'GTK confirmation must enforce fresh activation')
        self.dialog = common.ConfirmationDialog(None, 'Install Firefox?', 'Signed packages; review the transaction.')
        self.addCleanup(self.dialog.destroy)
        self.responses = []
        self.dialog.connect('response', lambda _, response: self.responses.append(response))
        self.dialog.show_all()
        self.drain()

    def drain(self):
        for _ in range(200):
            if not self.Gtk.events_pending():
                break
            self.Gtk.main_iteration_do(False)

    def settle_activation(self):
        # GtkButton's default keyboard activation may finish on an animation
        # timer. Process the actual GLib loop long enough to observe it; a
        # drain-only assertion can miss an inherited Return activation.
        loop = self.common.GLib.MainLoop()
        self.common.GLib.timeout_add(500, lambda: (loop.quit(), False)[1])
        loop.run()
        self.drain()

    def pointer(self, widget, event_type, inside=True):
        event = self.Gdk.Event.new(event_type)
        event.window = widget.get_event_window()
        event.button = 1
        event.x, event.y = ((widget.get_allocated_width() / 2,
                             widget.get_allocated_height() / 2) if inside else (-10, -10))
        event.send_event = True
        event.set_device(self.Gdk.Display.get_default().get_default_seat().get_pointer())
        widget.event(event)
        self.drain()

    def key(self, widget, event_type, key):
        event = self.Gdk.Event.new(event_type)
        window = widget.get_toplevel()
        event.window = window.get_window()
        event.keyval = key
        # GTK's built-in key bindings translate the physical keycode, unlike
        # our OK handler which can read keyval directly. A zero keycode tests
        # only that custom handler and silently misses default Cancel.
        keymap = self.Gdk.Keymap.get_for_display(window.get_display())
        found, entries = keymap.get_entries_for_keyval(key)
        self.assertTrue(found, 'The test display must map the requested key')
        entry = min((entry for entry in entries if entry.level == 0),
                    key=lambda entry: entry.group, default=None)
        self.assertIsNotNone(entry, 'The test key must be available without modifiers')
        event.hardware_keycode = entry.keycode
        event.group = entry.group
        event.state = self.Gdk.ModifierType(0)
        event.time = self.Gdk.CURRENT_TIME
        translated = keymap.translate_keyboard_state(event.hardware_keycode, event.state, event.group)
        self.assertTrue(translated[0], 'The synthetic hardware keycode must translate')
        self.assertEqual(translated[1], key)
        event.send_event = True
        event.set_device(self.Gdk.Display.get_default().get_default_seat().get_keyboard())
        # Route through GtkWindow's normal focus propagation, rather than
        # sending directly to the button and hiding dialog-level handlers.
        window.event(event)
        self.drain()

    def test_default_return_cancels_without_starting_confirmation(self):
        self.key(self.dialog.cancel_button, self.Gdk.EventType.KEY_PRESS, self.Gdk.KEY_Return)
        self.key(self.dialog.cancel_button, self.Gdk.EventType.KEY_RELEASE, self.Gdk.KEY_Return)
        self.settle_activation()
        self.assertNotIn(self.Gtk.ResponseType.OK, self.responses)
        self.assertIn(self.Gtk.ResponseType.CANCEL, self.responses)

    def test_held_opening_return_autorepeat_cannot_activate_default_cancel(self):
        opening = self.Gdk.Event.new(self.Gdk.EventType.KEY_PRESS)
        opening.keyval = self.Gdk.KEY_Return
        with patch.object(self.Gtk, 'get_current_event', return_value=opening):
            dialog = self.common.ConfirmationDialog(None, 'Install Firefox?', 'Review first.')
        self.addCleanup(dialog.destroy)
        responses = []
        dialog.connect('response', lambda _, response: responses.append(response))
        dialog.show_all()
        self.drain()
        self.assertEqual(dialog.get_focus(), dialog.cancel_button)
        # Real keyboard autorepeat emits another KEY_PRESS before the held
        # opening Return is released. Neither response is a fresh activation.
        self.key(dialog.cancel_button, self.Gdk.EventType.KEY_PRESS, self.Gdk.KEY_Return)
        self.settle_activation()
        self.assertEqual(responses, [], 'The opening Return repeat dismissed the dialog before release')
        self.key(dialog.cancel_button, self.Gdk.EventType.KEY_RELEASE, self.Gdk.KEY_Return)
        self.settle_activation()
        self.assertEqual(responses, [], 'The inherited opening Return release dismissed the dialog')
        self.key(dialog.cancel_button, self.Gdk.EventType.KEY_PRESS, self.Gdk.KEY_Return)
        self.key(dialog.cancel_button, self.Gdk.EventType.KEY_RELEASE, self.Gdk.KEY_Return)
        self.settle_activation()
        self.assertEqual(responses, [self.Gtk.ResponseType.CANCEL])

    def test_unpaired_inherited_keyboard_release_over_cancel_does_not_dismiss(self):
        for key in (self.Gdk.KEY_Return, self.Gdk.KEY_space):
            with self.subTest(key=key):
                self.key(self.dialog.cancel_button, self.Gdk.EventType.KEY_RELEASE, key)
                self.settle_activation()
                self.assertEqual(self.responses, [])

    def test_unpaired_inherited_pointer_release_over_cancel_does_not_dismiss(self):
        self.pointer(self.dialog.cancel_button, self.Gdk.EventType.BUTTON_RELEASE)
        self.settle_activation()
        self.assertEqual(self.responses, [])

    def test_cancel_is_focused_default_and_buttons_have_separate_rectangles(self):
        cancel, ok = self.dialog.cancel_button, self.dialog.confirm_button
        self.assertEqual(self.dialog.get_default_widget(), cancel)
        self.assertEqual(self.dialog.get_focus(), cancel)
        positions = [(button.translate_coordinates(self.dialog, 0, 0),
                      button.get_allocated_width(), button.get_allocated_height()) for button in (cancel, ok)]
        for _, width, height in positions:
            self.assertGreaterEqual(width, 112)
            self.assertGreater(height, 0)
        (cx, cy), cw, ch = positions[0]
        (ox, oy), ow, oh = positions[1]
        self.assertTrue(cx + cw + 12 <= ox or ox + ow + 12 <= cx or
                        cy + ch + 12 <= oy or oy + oh + 12 <= cy)

    def test_inherited_clicked_signal_and_unpaired_release_cannot_confirm(self):
        self.dialog.confirm_button.clicked()
        self.pointer(self.dialog.confirm_button, self.Gdk.EventType.BUTTON_RELEASE)
        self.assertEqual(self.responses, [])

    def test_synthetic_second_press_of_an_opening_double_click_does_not_confirm(self):
        self.pointer(self.dialog.confirm_button, self.Gdk.EventType.DOUBLE_BUTTON_PRESS)
        self.pointer(self.dialog.confirm_button, self.Gdk.EventType.BUTTON_RELEASE)
        self.assertEqual(self.responses, [])

    def test_press_cancel_release_ok_cannot_confirm_and_cancel_is_safe(self):
        self.pointer(self.dialog.cancel_button, self.Gdk.EventType.BUTTON_PRESS)
        self.pointer(self.dialog.confirm_button, self.Gdk.EventType.BUTTON_RELEASE)
        self.assertNotIn(self.Gtk.ResponseType.OK, self.responses)
        self.dialog.cancel_button.clicked()
        self.assertEqual(self.responses[-1], self.Gtk.ResponseType.CANCEL)

    def test_press_ok_release_outside_does_not_confirm(self):
        self.pointer(self.dialog.confirm_button, self.Gdk.EventType.BUTTON_PRESS)
        self.pointer(self.dialog.confirm_button, self.Gdk.EventType.BUTTON_RELEASE, inside=False)
        self.assertEqual(self.responses, [])

    def test_fresh_pointer_pair_confirms_once(self):
        self.pointer(self.dialog.confirm_button, self.Gdk.EventType.BUTTON_PRESS)
        self.assertEqual(self.responses, [])
        self.pointer(self.dialog.confirm_button, self.Gdk.EventType.BUTTON_RELEASE)
        self.pointer(self.dialog.confirm_button, self.Gdk.EventType.BUTTON_RELEASE)
        self.assertEqual(self.responses, [self.Gtk.ResponseType.OK])

    def test_fresh_keyboard_pair_after_focusing_ok_confirms_on_release(self):
        self.dialog.confirm_button.grab_focus()
        self.drain()
        self.key(self.dialog.confirm_button, self.Gdk.EventType.KEY_PRESS, self.Gdk.KEY_Return)
        self.assertEqual(self.responses, [])
        self.key(self.dialog.confirm_button, self.Gdk.EventType.KEY_RELEASE, self.Gdk.KEY_Return)
        self.assertEqual(self.responses, [self.Gtk.ResponseType.OK])

    def test_inherited_opening_key_and_autorepeat_cannot_confirm(self):
        opening = self.Gdk.Event.new(self.Gdk.EventType.KEY_PRESS)
        opening.keyval = self.Gdk.KEY_space
        with patch.object(self.Gtk, 'get_current_event', return_value=opening):
            dialog = self.common.ConfirmationDialog(None, 'Install Firefox?', 'Review first.')
        self.addCleanup(dialog.destroy)
        responses = []
        dialog.connect('response', lambda _, response: responses.append(response))
        dialog.show_all()
        dialog.confirm_button.grab_focus()
        self.drain()
        self.key(dialog.confirm_button, self.Gdk.EventType.KEY_PRESS, self.Gdk.KEY_space)
        self.key(dialog.confirm_button, self.Gdk.EventType.KEY_RELEASE, self.Gdk.KEY_space)
        self.assertEqual(responses, [])
        self.key(dialog.confirm_button, self.Gdk.EventType.KEY_PRESS, self.Gdk.KEY_space)
        self.key(dialog.confirm_button, self.Gdk.EventType.KEY_RELEASE, self.Gdk.KEY_space)
        self.assertEqual(responses, [self.Gtk.ResponseType.OK])

    def test_gui_install_opens_native_progress_window_without_a_terminal(self):
        with patch.object(self.common, 'installed', return_value=False), \
                patch.object(self.common, 'confirm', return_value=True), \
                patch('ownos.ui.app_install.AppInstallWindow') as window, \
                patch.object(self.common, 'terminal') as terminal:
            result = self.common.launch_app('firefox')
        window.assert_called_once_with('firefox', None)
        window.return_value.begin.assert_called_once_with()
        self.assertIs(result, window.return_value)
        terminal.assert_not_called()

    def test_cancel_does_not_start_a_terminal_or_an_installer(self):
        with patch.object(self.common, 'installed', return_value=False), \
                patch.object(self.common, 'confirm', return_value=False), \
                patch.object(self.common, 'terminal') as terminal:
            self.common.launch_app('firefox')
        terminal.assert_not_called()


if __name__ == '__main__':
    unittest.main()

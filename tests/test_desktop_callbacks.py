"""GTK callback contracts that do not require a display or host clipboard."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class DesktopCallbackTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos.ui import desktop
        except ImportError as exc:
            self.skipTest('GTK introspection unavailable: '+str(exc))
        self.ui=desktop

    def test_clipboard_targets_accepts_the_real_four_argument_gtk_callback(self):
        target=SimpleNamespace(name=lambda:'text/uri-list')
        selection=SimpleNamespace(get_data=lambda:b'file:///tmp/clipboard-file.txt\r\n',get_target=lambda:target)
        clipboard=SimpleNamespace(
            request_targets=lambda callback,data:callback(None,[target],1,data),
            request_contents=lambda atom,callback,data:callback(None,selection,data))
        surface=SimpleNamespace(closed=False,clipboard_files=None,clipboard_serial=0)
        paste=Mock()
        with patch.object(self.ui.Gtk.Clipboard,'get',return_value=clipboard):
            self.ui.DesktopSurface.read_clipboard(surface,None,paste)
        paste.set_sensitive.assert_called_once_with(True)
        self.assertIsNotNone(surface.clipboard_files)

    def test_native_popup_grab_outside_press_dismisses_but_inside_press_stays_open(self):
        surface=SimpleNamespace(dismiss_menu=Mock())
        menu=SimpleNamespace(get_allocated_width=lambda:219,get_allocated_height=lambda:284)
        inside=SimpleNamespace(type=self.ui.Gdk.EventType.BUTTON_PRESS,x=20,y=40)
        outside=SimpleNamespace(type=self.ui.Gdk.EventType.BUTTON_PRESS,x=-320,y=439)
        self.assertFalse(self.ui.DesktopSurface.menu_pointer_pressed(surface,menu,inside))
        surface.dismiss_menu.assert_not_called()
        self.assertTrue(self.ui.DesktopSurface.menu_pointer_pressed(surface,menu,outside))
        surface.dismiss_menu.assert_called_once_with()


if __name__=='__main__':unittest.main()

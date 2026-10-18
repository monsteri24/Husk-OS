#!/usr/bin/env python3
"""Real GTK test canvas; only actual input requests window-state changes."""
import json
from pathlib import Path
import sys

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib


def main():
    GLib.set_prgname('husk-panel-test')
    destination = Path(sys.argv[1])
    window = Gtk.Window(title='Husk Panel State Test')
    window.set_default_size(660, 440)
    canvas = Gtk.DrawingArea()
    canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
    window.add(canvas)
    clicks = []
    keys = []

    def draw(_, context):
        context.set_source_rgb(36 / 255, 80 / 255, 74 / 255)
        context.paint()
        return False

    def clicked(_, event):
        clicks.append(dict(x=event.x, y=event.y, button=event.button))
        return False

    def key(_, event):
        native = window.get_window()
        state = native.get_state() if native else Gdk.WindowState(0)
        keys.append(Gdk.keyval_name(event.keyval))
        if event.keyval == Gdk.KEY_F10:
            window.unmaximize() if state & Gdk.WindowState.MAXIMIZED else window.maximize()
            return True
        if event.keyval == Gdk.KEY_F11:
            window.unfullscreen() if state & Gdk.WindowState.FULLSCREEN else window.fullscreen()
            return True
        return False

    def report():
        native = window.get_window()
        state = native.get_state() if native else Gdk.WindowState(0)
        value = dict(maximized=bool(state & Gdk.WindowState.MAXIMIZED),
                     fullscreen=bool(state & Gdk.WindowState.FULLSCREEN),
                     mapped=window.get_mapped(), width=canvas.get_allocated_width(),
                     height=canvas.get_allocated_height(), clicks=clicks, keys=keys)
        temporary = destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(value))
        temporary.replace(destination)
        return True

    canvas.connect('draw', draw)
    canvas.connect('button-press-event', clicked)
    window.connect('key-press-event', key)
    window.connect('destroy', lambda *_: Gtk.main_quit())
    window.show_all()
    GLib.timeout_add(100, report)
    Gtk.main()


if __name__ == '__main__':
    main()

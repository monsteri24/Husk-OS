"""Passive telemetry for the real source applications in the Labwc CI test.

Loaded only when test-labwc.py injects this directory into PYTHONPATH. No input,
window-management requests, widget replacements, or preview windows live here.
"""
import atexit
import json
import os
from pathlib import Path
import sys

name = Path(sys.argv[0]).name
kind = {'husk-desktop': 'desktop', 'husk-files': 'files',
        'husk-control': 'control'}.get(name)
directory = os.environ.get('HUSK_LABWC_TELEMETRY')

if kind and directory:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gtk, Gdk, GLib

    destination = Path(directory) / (kind + '.json')
    shell = None
    latest = {'pid': os.getpid(), 'kind': kind, 'exited': False}

    def save(value):
        temporary = destination.with_suffix('.' + str(os.getpid()) + '.tmp')
        temporary.write_text(json.dumps(value), encoding='utf-8')
        temporary.replace(destination)

    if kind == 'desktop':
        def capture(frame, event, result):
            global shell
            if (event == 'return' and frame.f_code.co_name == '__init__'
                    and frame.f_globals.get('__name__') == 'ownos.ui.shell'):
                shell = frame.f_locals['self']
                sys.setprofile(None)
        sys.setprofile(capture)

    def descendants(widget):
        yield widget
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                yield from descendants(child)

    def rectangle(widget, window, origin):
        point = widget.translate_coordinates(window, 0, 0)
        if point is None:
            return None
        return [origin[0] + point[0], origin[1] + point[1],
                widget.get_allocated_width(), widget.get_allocated_height()]

    def surface(window):
        monitor = shell.layer.get_monitor(window) or shell.primary
        geometry = monitor.get_geometry()
        width, height = window.get_allocated_width(), window.get_allocated_height()
        edge = shell.layer.Edge
        left = shell.layer.get_anchor(window, edge.LEFT)
        right = shell.layer.get_anchor(window, edge.RIGHT)
        top = shell.layer.get_anchor(window, edge.TOP)
        bottom = shell.layer.get_anchor(window, edge.BOTTOM)
        x = (geometry.x + shell.layer.get_margin(window, edge.LEFT) if left else
             geometry.x + geometry.width - width - shell.layer.get_margin(window, edge.RIGHT)
             if right else geometry.x + (geometry.width - width) // 2)
        y = (geometry.y + shell.layer.get_margin(window, edge.TOP) if top else
             geometry.y + geometry.height - height - shell.layer.get_margin(window, edge.BOTTOM)
             if bottom else geometry.y + (geometry.height - height) // 2)
        return [x, y, width, height]

    def poll():
        global latest
        try:
            windows = []
            for window in Gtk.Window.list_toplevels():
                native = window.get_window()
                state = native.get_state() if native else Gdk.WindowState(0)
                windows.append(dict(title=window.get_title(), mapped=window.get_mapped(),
                                    visible=window.get_visible(),
                                    maximized=bool(state & Gdk.WindowState.MAXIMIZED),
                                    size=[window.get_allocated_width(), window.get_allocated_height()]))
            latest = dict(pid=os.getpid(), kind=kind, exited=False, windows=windows,
                          display=type(Gdk.Display.get_default()).__name__)
            if shell is not None and not shell.stopped:
                panel = surface(shell.panel)
                start = surface(shell.start_window)
                latest.update(status=shell.status(), panel=panel, start=start,
                              start_mapped=shell.start_window.get_mapped(),
                              toplevels=list(shell.toplevels.values()))
                latest['panel_buttons'] = [dict(label=w.get_label(), tooltip=w.get_tooltip_text(),
                                                rect=rectangle(w, shell.panel, panel))
                                           for w in descendants(shell.panel) if isinstance(w, Gtk.Button)]
                latest['task_buttons'] = [dict(label=w.get_label(), tooltip=w.get_tooltip_text(),
                                               rect=rectangle(w, shell.panel, panel))
                                          for w in shell.tasks.get_children() if isinstance(w, Gtk.Button)]
                latest['search'] = rectangle(shell.search, shell.start_window, start)
                latest['search_text'] = shell.search.get_text()
                latest['rows'] = [dict(name=row.app_name,
                                       rect=rectangle(row, shell.start_window, start))
                                  for row in shell.app_list.get_children()]
                latest['wallpapers'] = []
                for background in shell.backgrounds:
                    wallpaper = background.get_child().get_child()
                    latest['wallpapers'].append(dict(
                        source=str(getattr(wallpaper, 'source_path', '')),
                        size=[wallpaper.get_allocated_width(), wallpaper.get_allocated_height()]))
            save(latest)
        except Exception as exc:
            save(dict(latest, observer_error=repr(exc)))
        return True

    def exited():
        save(dict(latest, exited=True))

    GLib.timeout_add(100, poll)
    atexit.register(exited)

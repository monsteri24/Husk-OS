"""Passive telemetry for the real source applications in the Labwc CI test.

Loaded only when test-labwc.py injects this directory into PYTHONPATH. No input,
window-management requests, widget replacements, or preview windows live here.
"""
import atexit
import json
import os
from pathlib import Path
import sys
import time
import weakref

name = Path(sys.argv[0]).name
kind = {'husk-desktop': 'desktop', 'husk-files': 'files',
        'husk-control': 'control',
        'husk-labwc-confirm-client.py': 'confirmation'}.get(name)
directory = os.environ.get('HUSK_LABWC_TELEMETRY')

if kind and directory:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gtk, Gdk, GLib

    destination = Path(directory) / (kind + '.json')
    shell = None
    latest = {'pid': os.getpid(), 'kind': kind, 'exited': False}
    observed = weakref.WeakSet()
    sequence = 0

    def observe_input(widget, event, window_id):
        """Record delivered GTK events without consuming or synthesizing them."""
        value = dict(window=window_id, widget=type(widget).__name__,
                     event=event.type.value_nick, time=time.monotonic())
        if isinstance(widget, Gtk.Button):
            value['label'] = widget.get_label()
        if event.type in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE):
            value['button'] = event.get_button()[1]
        elif event.type in (Gdk.EventType.KEY_PRESS, Gdk.EventType.KEY_RELEASE):
            value['key'] = Gdk.keyval_name(event.keyval)
        else:
            return False
        with (Path(directory) / (kind + '-input.jsonl')).open('a') as stream:
            stream.write(json.dumps(value) + '\n')
        return False

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
        global latest, sequence
        sequence += 1
        try:
            windows = []
            for window in Gtk.Window.list_toplevels():
                native = window.get_window()
                state = native.get_state() if native else Gdk.WindowState(0)
                identifier = str(id(window))
                widgets = list(descendants(window))
                for widget in widgets:
                    if widget not in observed and isinstance(widget, (
                            Gtk.Window, Gtk.Button, Gtk.Entry, Gtk.ListBoxRow, Gtk.ComboBox, Gtk.Menu, Gtk.MenuItem)):
                        widget.connect('event', observe_input, identifier)
                        observed.add(widget)
                value = dict(id=identifier, type=type(window).__name__, title=window.get_title(),
                             mapped=window.get_mapped(), visible=window.get_visible(),
                             maximized=bool(state & Gdk.WindowState.MAXIMIZED),
                             size=[window.get_allocated_width(), window.get_allocated_height()])
                value['buttons'] = [dict(label=w.get_label(), focused=w.has_focus(),
                                         default=w.has_default(), sensitive=w.get_sensitive(),
                                         rect=rectangle(w, window, (0, 0)))
                                    for w in widgets if isinstance(w, Gtk.Button) and w.get_mapped()]
                if hasattr(window, 'cancel_button') and hasattr(window, 'confirm_button'):
                    value['confirmation'] = dict(
                        primary_text=window.get_property('text'),
                        cancel=rectangle(window.cancel_button, window, (0, 0)),
                        confirm=rectangle(window.confirm_button, window, (0, 0)),
                        cancel_focused=window.cancel_button.has_focus(),
                        cancel_default=window.cancel_button.has_default(),
                        confirm_focused=window.confirm_button.has_focus())
                if hasattr(window, 'current') and hasattr(window, 'location') and hasattr(window, 'list'):
                    value['files'] = dict(
                        current=str(window.current), location=window.location.get_text(),
                        location_rect=rectangle(window.location, window, (0, 0)),
                        status=window.status.get_text(),
                        rows=[dict(name=row.path.name, path=str(row.path),
                                   rect=rectangle(row, window, (0, 0)))
                              for row in window.list.get_children()])
                if type(window).__name__ == 'AppInstallWindow':
                    value['app_install'] = dict(appid=window.app.id, state=window.state,
                                                status=window.status.get_text())
                if hasattr(window, 'language'):
                    value['language'] = dict(active_id=window.language.get_active_id(),
                                             rect=rectangle(window.language, window, (0, 0)))
                    value['tabs'] = [dict(label=notebook.get_tab_label_text(notebook.get_nth_page(i)),
                                          rect=rectangle(notebook.get_tab_label(notebook.get_nth_page(i)),
                                                         window, (0, 0)))
                                     for notebook in widgets if isinstance(notebook, Gtk.Notebook)
                                     for i in range(notebook.get_n_pages())]
                windows.append(value)
            latest = dict(pid=os.getpid(), kind=kind, exited=False, windows=windows, sequence=sequence,
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
                                       identity=str(hash(row)),
                                       focused=any(w.has_focus() for w in descendants(row)),
                                       rect=rectangle(row, shell.start_window, start))
                                  for row in shell.app_list.get_children()]
                latest['wallpapers'] = []
                for background in shell.backgrounds:
                    wallpaper = background.get_child().get_child()
                    latest['wallpapers'].append(dict(
                        source=str(getattr(wallpaper, 'source_path', '')),
                        size=[wallpaper.get_allocated_width(), wallpaper.get_allocated_height()]))
                latest['desktop_menus'] = []
                for desktop in shell.desktop_surfaces:
                    menu, host = desktop.active_menu, desktop.menu_host
                    selected = menu.get_selected_item() if menu is not None else None
                    if menu is not None:
                        for widget in descendants(menu):
                            if widget not in observed and isinstance(widget, (Gtk.Menu, Gtk.MenuItem)):
                                widget.connect('event', observe_input, 'desktop-menu-' + str(id(menu)))
                                observed.add(widget)
                    latest['desktop_menus'].append(dict(
                        active=menu is not None, type=type(menu).__name__ if menu is not None else None,
                        mapped=bool(menu is not None and menu.get_mapped()),
                        host_present=host is not None, host_mapped=bool(host is not None and host.get_mapped()),
                        background_keyboard_mode=int(shell.layer.get_keyboard_mode(desktop.window)),
                        host_keyboard_mode=int(shell.layer.get_keyboard_mode(host)) if host is not None else None,
                        selected=selected.get_label() if selected is not None else None,
                        labels=[item.get_label() for item in menu.get_children()
                                if isinstance(item, Gtk.MenuItem) and not isinstance(item, Gtk.SeparatorMenuItem)]
                               if menu is not None else []))
            save(latest)
        except Exception as exc:
            save(dict(latest, observer_error=repr(exc)))
        return True

    def exited():
        save(dict(latest, exited=True))

    GLib.timeout_add(100, poll)
    atexit.register(exited)

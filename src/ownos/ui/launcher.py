"""Husk application launcher, replaceable independently of taskbar/compositor."""
from ownos.catalog import APPS
from pathlib import Path
from ownos.ui.common import Gtk, Gio, GLib, icon, launch_app, spawn, error


class Launcher:
    def __init__(self, shell):
        self.shell = shell
        self.window, box = shell.popup('Husk Start', 510, 540)
        title = Gtk.Label(label='Start · Husk OS', xalign=0); title.get_style_context().add_class('title')
        box.pack_start(title, False, False, 0)
        self.search = Gtk.SearchEntry(); self.search.set_placeholder_text('Hae sovelluksia…')
        self.search.connect('search-changed', lambda _: self.refresh())
        self.search.connect('changed', lambda _: self.refresh())
        box.pack_start(self.search, False, False, 0)
        self.app_list = Gtk.ListBox(); self.app_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.app_list.connect('row-activated', self.activate)
        scroll = Gtk.ScrolledWindow(); scroll.add(self.app_list); box.pack_start(scroll, True, True, 0)
        self.system_apps = [app for app in Gio.AppInfo.get_all() if app.should_show()]
        self.refresh()
        footer = Gtk.Box(spacing=8)
        for label, argv in [('Asetukset',['/usr/bin/husk-control']), ('Lukitse',['/usr/bin/husk-lock']),
                            ('Kirjaudu ulos',['/usr/bin/labwc','--exit'])]:
            button = Gtk.Button(label=label)
            if label == 'Lukitse' and Path('/run/archiso').is_dir():
                button.set_sensitive(False)
                button.set_tooltip_text('Live-istunnolla ei ole salasanaa. Lukitse vasta asennettu käyttäjäistunto.')
            button.connect('clicked', lambda _, cmd=argv: (self.window.hide(), spawn(cmd, shell.panel)))
            footer.pack_start(button, True, True, 0)
        box.pack_end(footer, False, False, 0)

    def refresh(self):
        query = self.search.get_text().casefold()
        for row in self.app_list.get_children(): self.app_list.remove(row)
        entries = [(app.name, app.icon, lambda id=app.id: launch_app(id, self.shell.panel)) for app in APPS]
        for app in sorted(self.system_apps, key=lambda a:a.get_display_name().casefold()):
            name = app.get_display_name()
            if name.casefold() in {'steam','lutris','discord','firefox'}: continue
            entries.append((name, app.get_icon(), lambda info=app:self.launch_desktop(info)))
        count = 0
        for name, app_icon, callback in entries:
            if query not in name.casefold(): continue
            row = Gtk.ListBoxRow(); row.app_name = name; row.activate_callback = callback
            content = Gtk.Box(spacing=14); content.set_border_width(10)
            image = Gtk.Image.new_from_gicon(app_icon, Gtk.IconSize.BUTTON) if isinstance(app_icon,Gio.Icon) else icon(app_icon)
            content.pack_start(image, False, False, 0); content.pack_start(Gtk.Label(label=name,xalign=0), True, True, 0)
            row.add(content); self.app_list.add(row); count += 1
            if count == 80: break
        self.app_list.show_all()

    def launch_desktop(self, info):
        try: info.launch([],None)
        except GLib.Error as exc:error(self.shell.panel,exc)

    def activate(self, _, row):
        self.window.hide(); row.activate_callback()

    def toggle(self):
        if self.window.get_visible():self.window.hide()
        else:
            self.shell.notification_window.hide(); self.window.show_all(); self.search.grab_focus()

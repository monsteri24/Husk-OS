"""Desktop files and native context menus on Husk's wallpaper surfaces."""
import threading
from pathlib import Path
import gi
gi.require_version('Pango', '1.0')
from gi.repository import Pango
from ownos.desktop_files import desktop_entries
from ownos.files import create_file, create_folder, rename_entry, paste_entries, parse_file_clipboard
from ownos.trash import TrashStore
from ownos.ui.common import Gtk, Gdk, Gio, GLib, icon, spawn, error, confirm


def desktop_directory():
    return Path(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP) or Path.home() / 'Desktop')


MENU_CSS = b'''
.husk-context-menu { background-color: @surface; color: @text;
 border: 1px solid #3b4b62; border-radius: 9px; padding: 6px; }
.husk-context-menu menuitem { color: @text; padding: 8px 18px; border-radius: 5px; }
.husk-context-menu menuitem:hover, .husk-context-menu menuitem:selected { background-color: @accent; color: @accent_text; }
.husk-context-menu menuitem:hover label, .husk-context-menu menuitem:selected label { color: @accent_text; }
.husk-context-menu menuitem:disabled { color: #8290a4; }
.husk-context-menu separator { background-color: #3b4b62; margin: 5px 8px; }
flowboxchild.desktop-icon { border: 1px solid transparent; border-radius: 9px; padding: 6px; }
flowboxchild.desktop-icon:selected { background-color: alpha(@accent, 0.22); border-color: @accent; }
flowboxchild.desktop-icon label { color: #f3f5f9; text-shadow: 0 1px 3px #000; }
'''


class DesktopSurface:
    def __init__(self, shell, window, overlay, monitor, show_icons=True):
        self.shell, self.window, self.monitor = shell, window, monitor
        self.closed = False; self.refresh_source = None; self.active_menu = None; self.menu_host = None
        self.clipboard_files = None; self.clipboard_serial = 0
        self.entries = []; self.flow = None; self.file_monitor = None
        self.desktop = desktop_directory(); self.trash_store = TrashStore()
        self.provider = Gtk.CssProvider(); self.provider.load_from_data(MENU_CSS)
        Gtk.StyleContext.add_provider_for_screen(window.get_screen(), self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        window.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        self.pointer_handler = window.connect('button-press-event', self.background_pressed)
        self.popup_handler = window.connect('popup-menu', lambda *_: self.popup())
        if show_icons:
            from ownos.desktop_layout import layout
            top = layout(shell.settings)['desktop_margin_top']
            self.flow = Gtk.FlowBox(orientation=Gtk.Orientation.VERTICAL)
            self.flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self.flow.set_activate_on_single_click(False)
            self.flow.set_min_children_per_line(1)
            height = 600 if shell.preview else monitor.get_geometry().height
            self.flow.set_max_children_per_line(max(1, (height - top - 88) // 104))
            self.flow.set_row_spacing(4); self.flow.set_column_spacing(4)
            self.flow.set_margin_top(top); self.flow.set_margin_start(18)
            self.flow.set_halign(Gtk.Align.START); self.flow.set_valign(Gtk.Align.START)
            self.flow.connect('child-activated', lambda _, child: self.open_entry(child.entry))
            overlay.add_overlay(self.flow)
            try:
                self.desktop.mkdir(parents=True, exist_ok=True)
                self.file_monitor = Gio.File.new_for_path(str(self.desktop)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
                self.file_monitor.connect('changed', lambda *_: self.schedule_refresh())
                self.trash_store.watch(self.schedule_refresh)
            except (OSError, GLib.Error):
                pass
            self.refresh()

    def schedule_refresh(self):
        if not self.closed and self.refresh_source is None:
            self.refresh_source = GLib.timeout_add(120, self.refresh)

    def refresh(self):
        self.refresh_source = None
        if self.closed or self.flow is None: return False
        selected = next((child.entry for child in self.flow.get_selected_children()), None)
        self.entries = desktop_entries(self.desktop, show_trash=self.shell.settings.get('show_trash', True))
        for child in self.flow.get_children(): self.flow.remove(child)
        trash_full = False
        if any(entry.kind == 'trash' for entry in self.entries):
            try: trash_full = bool(self.trash_store.entries())
            except (OSError, GLib.Error): pass
        for entry in self.entries:
            child = Gtk.FlowBoxChild(); child.entry = entry
            child.get_style_context().add_class('desktop-icon'); child.set_size_request(108, 96)
            child.set_tooltip_text(str(entry.path) if entry.path else entry.label)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
            name = 'user-trash-full' if entry.kind == 'trash' and trash_full else entry.icon
            box.pack_start(icon(name, 36, fallback='husk-install' if entry.kind == 'installer' else 'husk-app'), False, False, 3)
            label = Gtk.Label(label=entry.label); label.set_max_width_chars(16); label.set_ellipsize(Pango.EllipsizeMode.END)
            box.pack_start(label, False, False, 0); child.add(box)
            child.connect('button-press-event', self.icon_pressed)
            child.connect('popup-menu', lambda widget: self.popup(entry=widget.entry))
            self.flow.add(child)
            if entry == selected: self.flow.select_child(child)
        self.flow.show_all()
        return False

    def background_pressed(self, _, event):
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            return self.popup(event)
        return False

    def icon_pressed(self, child, event):
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            self.flow.select_child(child)
            return self.popup(event, child.entry)
        return False

    def open_entry(self, entry):
        parent = getattr(self.shell, 'panel', self.window)
        if entry.kind == 'installer': spawn(['/usr/bin/husk-install'], parent)
        elif entry.kind == 'trash': spawn(['/usr/bin/husk-files', 'trash:///'], parent)
        elif entry.path is not None: self.shell.open_desktop_entry(entry.path)

    @staticmethod
    def _defer(action):
        def run():
            action()
            return False
        GLib.idle_add(run)

    def build_menu(self, entry=None):
        menu = Gtk.Menu(); menu.get_style_context().add_class('husk-context-menu')
        def add(label, action, enabled=True):
            item = Gtk.MenuItem(label=label); item.set_sensitive(enabled)
            item.connect('activate', lambda _: self._defer(action)); menu.append(item)
            return item
        def separator(): menu.append(Gtk.SeparatorMenuItem())
        if entry is None:
            add('New Folder', lambda: self.new_item(folder=True))
            add('New File', lambda: self.new_item(folder=False))
            paste = add('Paste', self.paste, False)
            self.read_clipboard(menu, paste)
            separator(); add('Refresh', self.refresh)
            separator(); add('Display Settings', lambda: spawn(['/usr/bin/wdisplays'], self.window))
            add('Change Wallpaper', lambda: spawn(['/usr/bin/husk-control', '--page', 'appearance'], self.window))
            add('Personalize', lambda: spawn(['/usr/bin/husk-control', '--page', 'appearance'], self.window))
        else:
            add('Open', lambda: self.open_entry(entry))
            if not entry.protected:
                add('Rename', lambda: self.rename(entry))
                add('Move to Trash', lambda: self.run_operation(lambda: self.trash_store.move(entry.path)))
            elif entry.kind == 'trash':
                add('Empty Trash', self.empty_trash)
            separator(); add('Properties', lambda: self.properties(entry))
        menu.show_all()
        return menu

    def read_clipboard(self, menu, paste_item):
        self.clipboard_files = None; self.clipboard_serial += 1
        serial = self.clipboard_serial
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        def received(_, selection, _data):
            if self.closed or serial != self.clipboard_serial: return
            raw = selection.get_data()
            try: text = bytes(raw).decode('utf-8') if raw is not None else ''
            except (UnicodeError, TypeError): text = ''
            self.clipboard_files = parse_file_clipboard(text, gnome=selection.get_target().name() == 'x-special/gnome-copied-files')
            paste_item.set_sensitive(self.clipboard_files is not None)
        def targets(_, atoms, *_callback_data):
            if self.closed or serial != self.clipboard_serial: return
            available = {atom.name(): atom for atom in (atoms or [])}
            for target in ('x-special/gnome-copied-files', 'text/uri-list'):
                if target in available:
                    clipboard.request_contents(available[target], received, None)
                    break
        clipboard.request_targets(targets, None)

    def popup(self, event=None, entry=None):
        if self.closed: return True
        self.dismiss_menu()
        event = event if event is not None else Gtk.get_current_event()
        pointer_event = event is not None and event.type in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE,
                                                            Gdk.EventType._2BUTTON_PRESS, Gdk.EventType._3BUTTON_PRESS)
        menu = self.build_menu(entry); self.active_menu = menu
        menu.connect('deactivate', self.menu_deactivated)
        menu.connect('unmap', self.menu_deactivated)
        menu.connect('key-press-event', self.menu_key_pressed)
        menu.connect('button-press-event', self.menu_pointer_pressed)
        if self.shell.layer:
            # A BACKGROUND layer intentionally has no keyboard focus. Give the
            # native popup a short-lived OVERLAY parent instead of making the
            # wallpaper grab the keyboard or raising it over application windows.
            layer = self.shell.layer
            host = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
            host.set_decorated(False); host.set_app_paintable(True)
            visual = host.get_screen().get_rgba_visual()
            if visual: host.set_visual(visual)
            host.set_opacity(0.0)
            layer.init_for_window(host); layer.set_namespace(host, 'husk-desktop-menu')
            layer.set_layer(host, layer.Layer.OVERLAY); layer.set_monitor(host, self.monitor)
            for edge in (layer.Edge.TOP, layer.Edge.BOTTOM, layer.Edge.LEFT, layer.Edge.RIGHT):
                layer.set_anchor(host, edge, True)
            layer.set_exclusive_zone(host, -1); layer.set_keyboard_mode(host, layer.KeyboardMode.EXCLUSIVE)
            self.menu_host = host
            rect = Gdk.Rectangle(); rect.width = 1; rect.height = 1
            rect.x, rect.y = 24, 24
            if pointer_event:
                rect.x, rect.y = int(event.x), int(event.y)
                owner = event.window.get_user_data() if event.window else None
                if isinstance(owner, Gtk.Widget):
                    point = owner.translate_coordinates(self.window, int(event.x), int(event.y))
                    if point is not None: rect.x, rect.y = point
            trigger = event.copy() if event is not None else None
            def mapped(*_):
                if self.active_menu is not menu: return False
                # Wait for the parent layer surface to have its compositor
                # allocation before creating the native xdg_popup below it.
                menu.attach_to_widget(host, None)
                menu.popup_at_rect(host.get_window(), rect, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, trigger)
                if not pointer_event: menu.select_first(True)
                return False
            host.connect('map-event', mapped)
            host.connect('key-press-event', lambda _host, key: (self.dismiss_menu(), True)[1] if key.keyval == Gdk.KEY_Escape else False)
            host.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            host.connect('button-press-event', lambda *_: (self.dismiss_menu(), True)[1])
            host.show_all()
        else:
            menu.attach_to_widget(self.window, None)
            if pointer_event: menu.popup_at_pointer(event)
            else: menu.popup_at_widget(self.window, Gdk.Gravity.CENTER, Gdk.Gravity.CENTER, None)
            if not pointer_event: menu.select_first(True)
        return True

    def menu_key_pressed(self, _, event):
        # Handle dismissal at the receiving menu as well as its layer host.
        # GtkMenu's key bindings otherwise depend on the backend translating
        # the event's hardware keycode, even when its keyval is already Escape.
        if event.keyval == Gdk.KEY_Escape:
            self.dismiss_menu()
            return True
        return False

    def menu_pointer_pressed(self, menu, event):
        # A Wayland popup grab can deliver the outside press to Gtk.Menu
        # itself. Explicitly dismiss it even inside GTK's opening-click grace
        # period; the layer parent does not receive that grabbed event.
        if event.type == Gdk.EventType.BUTTON_PRESS and (
                event.x < 0 or event.y < 0 or event.x >= menu.get_allocated_width()
                or event.y >= menu.get_allocated_height()):
            self.dismiss_menu()
            return True
        return False

    def menu_deactivated(self, menu):
        if self.active_menu is menu:
            self.active_menu = None
            if self.menu_host is not None:
                self.menu_host.destroy(); self.menu_host = None
        GLib.idle_add(lambda: (menu.destroy(), False)[1])

    def dismiss_menu(self):
        self.clipboard_serial += 1
        if self.active_menu is not None:
            menu, self.active_menu = self.active_menu, None
            menu.popdown(); menu.destroy()
        if self.menu_host is not None:
            self.menu_host.destroy(); self.menu_host = None

    def prompt_name(self, title, initial=''):
        dialog = Gtk.Dialog(title=title, transient_for=self.window, modal=True)
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'Save', Gtk.ResponseType.OK)
        entry = Gtk.Entry(text=initial); entry.set_activates_default(True)
        entry.set_margin_start(16); entry.set_margin_end(16); entry.set_margin_top(16); entry.set_margin_bottom(16)
        dialog.get_content_area().add(entry); dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all(); entry.grab_focus(); entry.select_region(0, -1)
        try: return entry.get_text() if dialog.run() == Gtk.ResponseType.OK else None
        finally: dialog.destroy()

    def new_item(self, folder):
        name = self.prompt_name('New Folder' if folder else 'New File', 'New Folder' if folder else 'New File.txt')
        if name is None: return
        try:
            self.desktop.mkdir(parents=True, exist_ok=True)
            (create_folder if folder else create_file)(self.desktop, name)
            self.refresh()
        except (OSError, ValueError) as exc: error(self.window, exc)

    def rename(self, entry):
        if entry.protected or entry.path is None: return
        name = self.prompt_name('Rename', entry.path.name)
        if name is None: return
        try: rename_entry(entry.path, name); self.refresh()
        except (OSError, ValueError) as exc: error(self.window, exc)

    def run_operation(self, operation):
        def worker():
            problem = None
            try: operation()
            except (OSError, ValueError, GLib.Error) as exc: problem = exc
            def done():
                if not self.closed:
                    self.refresh()
                    if problem is not None: error(self.window, problem)
                return False
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    def paste(self):
        if self.clipboard_files is None: return
        cut, paths = self.clipboard_files
        self.run_operation(lambda: paste_entries(self.desktop, paths, cut=cut))

    def empty_trash(self):
        if confirm(self.window, 'Empty Trash?', 'All items in Trash will be permanently deleted. This cannot be undone.'):
            self.run_operation(self.trash_store.empty)

    def properties(self, entry):
        details = entry.label
        if entry.path is not None:
            try:
                stat = entry.path.lstat()
                details = f'{entry.path}\n\nType: {"Folder" if entry.path.is_dir() else "File"}\nSize: {stat.st_size:,} bytes'
            except OSError as exc: error(self.window, exc); return
        elif entry.kind == 'trash': details = 'Trash\n\nDeleted files can be restored to their original locations.'
        elif entry.kind == 'installer': details = 'Install Husk OS\n\nStarts the Husk OS installer in the live session.'
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.INFO,
                                   buttons=Gtk.ButtonsType.CLOSE, text='Properties')
        dialog.format_secondary_text(details)
        try: dialog.run()
        finally: dialog.destroy()

    def close(self):
        self.closed = True; self.dismiss_menu()
        if self.refresh_source is not None: GLib.source_remove(self.refresh_source); self.refresh_source = None
        if self.file_monitor is not None: self.file_monitor.cancel()
        self.trash_store.close()
        Gtk.StyleContext.remove_provider_for_screen(self.window.get_screen(), self.provider)

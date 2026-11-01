from pathlib import Path
from ownos.files import list_folder, create_folder
from ownos.trash import TrashStore
from ownos.config import ConfigStore
from ownos.i18n import _, ngettext, configure_saved
from ownos.ui.common import Gtk, Gio, GLib, icon, load_style, remove_style, open_path, error, confirm, require_display


class FileWindow(Gtk.Window):
    def __init__(self, path=None, store=None):
        store = store if store is not None else ConfigStore()
        configure_saved(store)
        require_display()
        super().__init__(title=_('Husk Files'))
        self.set_default_size(850, 560)
        self.provider = load_style(store.load(), store.path.parent / 'desktop.css'); self.connect('destroy', self.cleanup)
        self.current = Path.home(); self.in_trash = False; self.closed = False
        self.file_monitor = None; self.refresh_source = None; self.trash_store = TrashStore()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); outer.set_border_width(16)
        self.add(outer)
        toolbar = Gtk.Box(spacing=8); outer.pack_start(toolbar, False, False, 0)
        self.up_button = Gtk.Button(label=_('Up')); self.up_button.connect('clicked', lambda _: self.navigate(self.current.parent))
        toolbar.pack_start(self.up_button, False, False, 0)
        home = Gtk.Button(label=_('Home')); home.connect('clicked', lambda _: self.navigate(Path.home()))
        toolbar.pack_start(home, False, False, 0)
        trash = Gtk.Button(label=_('Trash')); trash.connect('clicked', lambda _: self.navigate('trash:///'))
        toolbar.pack_start(trash, False, False, 0)
        self.location = Gtk.Entry(); self.location.connect('activate', lambda e: self.navigate(e.get_text()))
        toolbar.pack_start(self.location, True, True, 0)
        self.create_button = Gtk.Button(label=_('New folder')); self.create_button.connect('clicked', self.new_folder)
        toolbar.pack_start(self.create_button, False, False, 0)
        self.trash_toolbar = Gtk.Box(spacing=8); outer.pack_start(self.trash_toolbar, False, False, 0)
        self.trash_toolbar.set_no_show_all(True)
        self.restore_button = Gtk.Button(label=_('Restore')); self.restore_button.connect('clicked', self.restore_selected)
        self.trash_toolbar.pack_start(self.restore_button, False, False, 0)
        self.empty_button = Gtk.Button(label=_('Empty Trash')); self.empty_button.connect('clicked', self.empty_trash)
        self.trash_toolbar.pack_end(self.empty_button, False, False, 0)
        self.list = Gtk.ListBox(); self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list.set_activate_on_single_click(False)
        self.list.connect('row-activated', self.activated)
        self.list.connect('row-selected', self.selection_changed)
        scroll = Gtk.ScrolledWindow(); scroll.add(self.list); outer.pack_start(scroll, True, True, 0)
        self.status = Gtk.Label(xalign=0); outer.pack_start(self.status, False, False, 0)
        self.navigate(path or self.current)

    def cleanup(self, *_):
        self.closed = True
        if self.refresh_source is not None: GLib.source_remove(self.refresh_source); self.refresh_source = None
        if self.file_monitor is not None: self.file_monitor.cancel()
        self.trash_store.close(); remove_style(self.provider)

    def schedule_refresh(self, *_):
        if not self.closed and self.refresh_source is None:
            def refresh():
                self.refresh_source = None
                if not self.closed: self.navigate('trash:///' if self.in_trash else self.current)
                return False
            self.refresh_source = GLib.timeout_add(120, refresh)

    def navigate(self, path):
        if str(path) in ('trash:', 'trash://', 'trash:///'):
            self.show_trash(); return
        try:
            path = Path(path).expanduser().absolute(); entries = list_folder(path)
        except OSError as exc:
            error(self, exc); return
        self.trash_store.close(); self.in_trash = False
        self.trash_toolbar.hide(); self.up_button.set_sensitive(True); self.create_button.set_sensitive(True)
        self.current = path; self.location.set_text(str(path))
        if self.file_monitor is not None: self.file_monitor.cancel()
        try:
            self.file_monitor = Gio.File.new_for_path(str(path)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self.file_monitor.connect('changed', self.schedule_refresh)
        except GLib.Error: self.file_monitor = None
        for child in self.list.get_children(): self.list.remove(child)
        for entry in entries[:2000]:
            row = Gtk.ListBoxRow(); row.path = entry
            box = Gtk.Box(spacing=12); box.set_border_width(10)
            box.pack_start(icon('folder' if entry.is_dir() else 'text-x-generic'), False, False, 0)
            box.pack_start(Gtk.Label(label=entry.name, xalign=0), True, True, 0)
            row.add(box); self.list.add(row)
        count = len(entries)
        if count > 2000:
            status = ngettext('{count} item · Showing the first {limit}',
                              '{count} items · Showing the first {limit}', count).format(count=count, limit=2000)
        else:
            status = ngettext('{count} item', '{count} items', count).format(count=count)
        self.status.set_text(status)
        self.list.show_all()

    def show_trash(self):
        try: entries = self.trash_store.entries()
        except (OSError, GLib.Error) as exc: error(self, exc); return
        if self.file_monitor is not None: self.file_monitor.cancel(); self.file_monitor = None
        self.in_trash = True; self.location.set_text('trash:///')
        self.up_button.set_sensitive(False); self.create_button.set_sensitive(False)
        for child in self.list.get_children(): self.list.remove(child)
        for item in entries:
            row = Gtk.ListBoxRow(); row.trash_item = item
            box = Gtk.Box(spacing=12); box.set_border_width(10)
            box.pack_start(icon(item.icon), False, False, 0)
            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            labels.pack_start(Gtk.Label(label=item.name, xalign=0), False, False, 0)
            detail = str(item.original) if item.original else _('Original location unavailable')
            if item.deleted: detail += ' · ' + item.deleted.replace('T', ' ')
            description = Gtk.Label(label=detail, xalign=0); description.set_line_wrap(True)
            description.get_style_context().add_class('muted'); labels.pack_start(description, False, False, 0)
            box.pack_start(labels, True, True, 0); row.add(box); self.list.add(row)
        self.status.set_text(ngettext('{count} item in Trash', '{count} items in Trash', len(entries)).format(count=len(entries)))
        self.empty_button.set_sensitive(bool(entries)); self.restore_button.set_sensitive(False)
        self.list.show_all(); self.restore_button.show(); self.empty_button.show(); self.trash_toolbar.show()
        try: self.trash_store.watch(self.schedule_refresh)
        except (OSError, GLib.Error): pass

    def selection_changed(self, _, row):
        item = getattr(row, 'trash_item', None)
        self.restore_button.set_sensitive(self.in_trash and item is not None and item.original is not None)

    def restore_selected(self, _button):
        row = self.list.get_selected_row()
        if not self.in_trash or row is None: return
        try: self.trash_store.restore(row.trash_item); self.show_trash()
        except (OSError, ValueError, GLib.Error) as exc: error(self, exc)

    def empty_trash(self, _button):
        if not self.in_trash: return
        if not confirm(self, _('Empty Trash?'), _('All items in Trash will be permanently deleted. This cannot be undone.')):
            return
        try: self.trash_store.empty(); self.show_trash()
        except (OSError, ValueError, GLib.Error) as exc: error(self, exc)

    def activated(self, _, row):
        if self.in_trash:
            self.list.select_row(row); self.restore_selected(None); return
        if row.path.is_dir(): self.navigate(row.path)
        else: open_path(row.path, self)

    def new_folder(self, _button):
        if self.in_trash: return
        dialog = Gtk.Dialog(title=_('New folder'), transient_for=self, modal=True)
        dialog.add_buttons(_('Cancel'), Gtk.ResponseType.CANCEL, _('Create'), Gtk.ResponseType.OK)
        entry = Gtk.Entry(); entry.set_activates_default(True)
        dialog.get_content_area().pack_start(entry, True, True, 12)
        dialog.set_default_response(Gtk.ResponseType.OK); dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK:
            try: create_folder(self.current, entry.get_text()); self.navigate(self.current)
            except (OSError, ValueError) as exc: error(self, exc)
        dialog.destroy()


def main(path=None):
    window = FileWindow(path); window.connect('destroy', lambda _: Gtk.main_quit())
    window.show_all(); Gtk.main()

from pathlib import Path
from ownos.files import list_folder, create_folder
from ownos.ui.common import Gtk, Gio, GLib, icon, load_style, remove_style, open_path, error, require_display


class FileWindow(Gtk.Window):
    def __init__(self, path=None):
        require_display()
        super().__init__(title='Husk Files')
        self.set_default_size(850, 560)
        self.provider = load_style(); self.connect('destroy', self.cleanup)
        self.current = Path(path or Path.home()).absolute()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); outer.set_border_width(16)
        self.add(outer)
        toolbar = Gtk.Box(spacing=8); outer.pack_start(toolbar, False, False, 0)
        up = Gtk.Button(label='Ylös'); up.connect('clicked', lambda _: self.navigate(self.current.parent))
        toolbar.pack_start(up, False, False, 0)
        home = Gtk.Button(label='Koti'); home.connect('clicked', lambda _: self.navigate(Path.home()))
        toolbar.pack_start(home, False, False, 0)
        self.location = Gtk.Entry(); self.location.connect('activate', lambda e: self.navigate(Path(e.get_text()).expanduser()))
        toolbar.pack_start(self.location, True, True, 0)
        create = Gtk.Button(label='Uusi kansio'); create.connect('clicked', self.new_folder)
        toolbar.pack_start(create, False, False, 0)
        self.list = Gtk.ListBox(); self.list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list.connect('row-activated', self.activated)
        scroll = Gtk.ScrolledWindow(); scroll.add(self.list); outer.pack_start(scroll, True, True, 0)
        self.status = Gtk.Label(xalign=0); outer.pack_start(self.status, False, False, 0)
        self.navigate(self.current)

    def cleanup(self, *_): remove_style(self.provider)

    def navigate(self, path):
        try:
            path = Path(path).absolute(); entries = list_folder(path)
        except OSError as exc:
            error(self, exc); return
        self.current = path; self.location.set_text(str(path))
        for child in self.list.get_children(): self.list.remove(child)
        for entry in entries[:2000]:
            row = Gtk.ListBoxRow(); row.path = entry
            box = Gtk.Box(spacing=12); box.set_border_width(10)
            box.pack_start(icon('folder' if entry.is_dir() else 'text-x-generic'), False, False, 0)
            box.pack_start(Gtk.Label(label=entry.name, xalign=0), True, True, 0)
            row.add(box); self.list.add(row)
        self.status.set_text(str(len(entries)) + ' kohdetta' + (' · Näytetään ensimmäiset 2000' if len(entries) > 2000 else ''))
        self.list.show_all()

    def activated(self, _, row):
        if row.path.is_dir(): self.navigate(row.path)
        else: open_path(row.path, self)

    def new_folder(self, _):
        dialog = Gtk.Dialog(title='Uusi kansio', transient_for=self, modal=True)
        dialog.add_buttons('Peruuta', Gtk.ResponseType.CANCEL, 'Luo', Gtk.ResponseType.OK)
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

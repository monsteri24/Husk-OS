import shutil
import subprocess
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from ownos.identity import OS_NAME, VERSION
from ownos.i18n import _, configure_saved
from ownos.config import ConfigStore, HUSK_YELLOW, keymap_options
from ownos.metrics import SystemSampler
from ownos.library import discover_steam_games
from ownos.input_config import write_input_config
from ownos.ui.common import Gtk, Gdk, GLib, load_style, remove_style, row_box, spawn, terminal, error, confirm, require_display


class ControlWindow(Gtk.Window):
    def __init__(self, store=None, page=None):
        store = store if store is not None else ConfigStore()
        configure_saved(store)
        require_display()
        super().__init__(title=_('Husk Settings · Gaming Control Center · Experimental'))
        self.set_default_size(900, 650)
        self.store = store; self.settings = self.store.load()
        self.provider = load_style(self.settings, self.store.path.parent / "desktop.css"); self.sampler = SystemSampler()
        self.closed = False; self.monitor_busy = False
        self.connect('destroy', self.cleanup)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15); outer.set_border_width(22)
        self.add(outer)
        title = Gtk.Label(label=_('Husk Settings'), xalign=0); title.get_style_context().add_class('title')
        outer.pack_start(title, False, False, 0)
        outer.pack_start(Gtk.Label(label=_('{os} · {version} · Gaming Control Center · Experimental').format(os=OS_NAME, version=VERSION), xalign=0), False, False, 0)
        notebook = Gtk.Notebook(); outer.pack_start(notebook, True, True, 0)
        selected_page = None
        for name, title, create in [('gaming', _('Gaming'), self.gaming_page), ('system', _('System'), self.system_page),
                                    ('input', _('Input'), self.input_page), ('appearance', _('Appearance'), self.appearance_page),
                                    ('updates', _('Updates'), self.updates_page)]:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16); box.set_border_width(20)
            create(box); scroll = Gtk.ScrolledWindow(); scroll.add(box)
            index = notebook.append_page(scroll, Gtk.Label(label=title))
            if name == page: selected_page = index
        if selected_page is not None:
            notebook.show_all()
            notebook.set_current_page(selected_page)
        self.status = Gtk.Label(xalign=0); outer.pack_start(self.status, False, False, 0)
        self.timer = GLib.timeout_add_seconds(2, self.sample)
        self.sample()

    def cleanup(self, *_):
        self.closed = True
        if self.timer: GLib.source_remove(self.timer); self.timer = None
        remove_style(self.provider)

    def save(self, key, value):
        settings = dict(self.settings); settings[key] = value
        if key == 'keymap' and value != self.settings['keymap']:
            settings['keymap_variant'] = ''
        try: self.store.save(settings)
        except (OSError, ValueError) as exc: error(self, exc); return False
        self.settings = settings
        if key in ('accent', 'animations'):
            provider = load_style(self.settings, self.store.path.parent / 'desktop.css')
            remove_style(self.provider)
            self.provider = provider
        self.status.set_text(_('Setting saved.'))
        return True

    def switch_row(self, box, title, detail, key):
        row = Gtk.Box(spacing=16); row.pack_start(row_box(title, detail), True, True, 0)
        switch = Gtk.Switch(); switch.set_valign(Gtk.Align.CENTER); switch.set_active(self.settings[key])
        switch.connect('notify::active', lambda obj, _: self.save(key, obj.get_active()))
        row.pack_end(switch, False, False, 0); box.pack_start(row, False, False, 0)
        return switch

    def gaming_page(self, box):
        self.gaming_switch = self.switch_row(box, _('GameMode launcher'),
            _('Applies to games launched with husk-game. In Steam, use the launch option husk-game -- %command%. Changes apply the next time a game starts.'), 'gaming_mode')
        self.switch_row(box, _('FPS / frame time overlay'), _('husk-game enables MangoHud. Some games and graphics APIs do not support the overlay.'), 'overlay')
        box.pack_start(row_box(_('Steam games'), _('Games are read from local Steam libraries. Manage Heroic and Lutris games in their own applications.')), False, False, 0)
        self.games = Gtk.ListBox(); self.games.set_selection_mode(Gtk.SelectionMode.NONE)
        box.pack_start(self.games, True, True, 0)
        self.refresh_games()
        button = Gtk.Button(label=_('Refresh game list')); button.connect('clicked', lambda _: self.refresh_games())
        box.pack_start(button, False, False, 0)

    def refresh_games(self):
        for child in self.games.get_children(): self.games.remove(child)
        games = discover_steam_games()
        if not games: self.games.add(Gtk.Label(label=_('No local Steam games found.')))
        for game in games:
            row = Gtk.Box(spacing=12); row.set_border_width(8)
            row.pack_start(Gtk.Label(label=game.name, xalign=0), True, True, 0)
            button = Gtk.Button(label=_('Launch'))
            button.connect('clicked', lambda _, appid=game.appid: spawn(['/usr/bin/steam', '-applaunch', appid], self))
            row.pack_end(button, False, False, 0); self.games.add(row)
        self.games.show_all()

    def system_page(self, box):
        self.cpu = Gtk.ProgressBar(); self.cpu.set_show_text(True)
        self.ram = Gtk.ProgressBar(); self.ram.set_show_text(True)
        self.gpu = Gtk.Label(label=_('GPU usage: not measured yet'), xalign=0)
        for label, widget in [('CPU', self.cpu), ('RAM', self.ram), ('GPU', self.gpu)]:
            box.pack_start(row_box(label), False, False, 0); box.pack_start(widget, False, False, 0)
        self.driver = Gtk.Label(label=_('Reading driver information…'), xalign=0); self.driver.set_line_wrap(True)
        box.pack_start(self.driver, False, False, 0)
        threading.Thread(target=self.read_drivers, daemon=True).start()
        button = Gtk.Button(label=_('Displays and refresh rate · wdisplays'))
        button.connect('clicked', lambda _: spawn(['/usr/bin/wdisplays'], self))
        box.pack_start(button, False, False, 0)

    def read_drivers(self):
        try:
            text = subprocess.run(['/usr/bin/lspci', '-k'], capture_output=True, text=True, timeout=5).stdout
            lines = text.splitlines(); keep = []
            for i, line in enumerate(lines):
                if 'VGA compatible' in line or '3D controller' in line or 'Display controller' in line:
                    keep += lines[i:i + 4]
            result = '\n'.join(keep) or _('No graphics card information found.')
        except (OSError, subprocess.TimeoutExpired): result = _('lspci is not available.')
        def update():
            if not self.closed: self.driver.set_text(result)
            return False
        GLib.idle_add(update)

    def sample(self):
        if self.closed: return False
        if self.monitor_busy: return True
        self.monitor_busy = True
        def read():
            try: result = self.sampler.sample()
            except (OSError, ValueError, KeyError): result = None
            def update():
                self.monitor_busy = False
                if self.closed: return False
                if result:
                    self.cpu.set_fraction(result['cpu_percent'] / 100)
                    self.cpu.set_text(_('{percent:.1f} %').format(percent=result['cpu_percent']))
                    total = result['ram_total_bytes']; used = result['ram_used_bytes']
                    self.ram.set_fraction(used / total if total else 0)
                    self.ram.set_text(_('{used:.2f} / {total:.2f} GiB').format(used=used / 2**30, total=total / 2**30))
                    gpu = result['gpu_percent']
                    self.gpu.set_text(_('GPU usage: {percent} %').format(percent=gpu) if gpu is not None
                                      else _('GPU usage: the driver does not provide a sysfs metric.'))
                return False
            GLib.idle_add(update)
        threading.Thread(target=read, daemon=True).start()
        return True

    def input_page(self, box):
        box.pack_start(row_box(_('Husk Desktop input settings'), _('These settings apply to the Husk labwc session. KDE and GNOME use their own input settings.')), False, False, 0)
        self.keymap = Gtk.ComboBoxText()
        for code in keymap_options(): self.keymap.append(code, code.upper())
        self.keymap.set_active_id(self.settings['keymap']); box.pack_start(self.keymap, False, False, 0)
        self.speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1, 1, 0.05)
        self.speed.set_value(self.settings['pointer_speed'])
        box.pack_start(row_box(_('Pointer speed'), _('Libinput speed from −1 to 1. Husk Desktop uses the flat pointer acceleration profile.')), False, False, 0)
        box.pack_start(self.speed, False, False, 0)
        apply = Gtk.Button(label=_('Save and apply Husk Desktop settings'))
        apply.connect('clicked', self.apply_input); box.pack_start(apply, False, False, 0)

    def apply_input(self, _button):
        if not self.save('keymap', self.keymap.get_active_id()): return
        if not self.save('pointer_speed', self.speed.get_value()): return
        directory = self.store.path.parent / 'labwc'
        template = Path('/etc/ownos/labwc/rc.xml')
        if not template.exists(): template = Path(__file__).resolve().parents[3] / 'config/labwc/rc.xml'
        try:
            write_input_config(directory, template, self.settings)
            labwc = shutil.which('labwc')
            if labwc:
                result = subprocess.run([labwc, '--reconfigure'], capture_output=True, timeout=4)
                if result.returncode == 0:
                    self.status.set_text(_('Husk Desktop settings applied.')); return
            self.status.set_text(_('Saved for the next Husk Desktop session.'))
        except (OSError, ET.ParseError, subprocess.TimeoutExpired) as exc: error(self, exc)

    def appearance_page(self, box):
        box.pack_start(row_box(_('Interface language')), False, False, 0)
        self.language = Gtk.ComboBoxText()
        self.language.append('en', 'English')
        self.language.set_sensitive(False)
        self.language.set_active_id(self.settings['language'])
        self.language_handler = self.language.connect('changed', self.change_language)
        box.pack_start(self.language, False, False, 0)
        box.pack_start(row_box(_('Husk Desktop taskbar'), _('This experimental desktop is under development. The taskbar and launcher are separate components.')), False, False, 0)
        position = Gtk.ComboBoxText()
        position.append('bottom', _('Bottom')); position.append('top', _('Top'))
        position.set_active_id(self.settings['taskbar_position'])
        position.connect('changed', lambda widget: self.save('taskbar_position', widget.get_active_id()))
        box.pack_start(position, False, False, 0)
        box.pack_start(row_box(_('Desktop Icons')), False, False, 0)
        self.trash_switch = self.switch_row(box, _('Show Trash'),
            _('Show the Trash icon on the desktop.'), 'show_trash')
        box.pack_start(row_box(_('Custom CSS'), _('{path} · Changes load into Husk Desktop without rebuilding the operating system.').format(path=self.store.path.parent / 'desktop.css')), False, False, 0)
        self.switch_row(box, _('Animations'), _('Short interface transitions.'), 'animations')
        box.pack_start(row_box(_('Accent color')), False, False, 0)
        self.accent_color = Gtk.ColorButton()
        self.accent_color.set_title(_('Accent color'))
        self.accent_color.set_use_alpha(False)
        rgba = Gdk.RGBA(); rgba.parse(self.settings['accent']); self.accent_color.set_rgba(rgba)
        self.accent_color.connect('color-set', self.change_accent)
        box.pack_start(self.accent_color, False, False, 0)
        self.reset_accent_button = Gtk.Button(label=_('Reset to Default'))
        self.reset_accent_button.connect('clicked', self.reset_accent)
        box.pack_start(self.reset_accent_button, False, False, 0)
        self.wallpaper = Gtk.Label(label=self.settings['wallpaper'] or _('Husk OS Desert (default)'), xalign=0)
        self.wallpaper.set_line_wrap(True); box.pack_start(self.wallpaper, False, False, 0)
        button = Gtk.Button(label=_('Choose wallpaper')); button.connect('clicked', self.choose_wallpaper)
        box.pack_start(button, False, False, 0)
        reset = Gtk.Button(label=_('Restore default wallpaper'))
        reset.connect('clicked', lambda _button: (self.save('wallpaper', ''), self.wallpaper.set_text(_('Husk OS Desert (default)'))))
        box.pack_start(reset, False, False, 0)

    def change_accent(self, button):
        color = button.get_rgba()
        value = '#%02x%02x%02x' % tuple(round(channel * 255) for channel in (color.red, color.green, color.blue))
        if not self.save('accent', value):
            saved = Gdk.RGBA(); saved.parse(self.settings['accent']); button.set_rgba(saved)

    def reset_accent(self, _button):
        if self.save('accent', HUSK_YELLOW):
            rgba = Gdk.RGBA(); rgba.parse(HUSK_YELLOW); self.accent_color.set_rgba(rgba)

    def change_language(self, widget):
        if self.save('language', widget.get_active_id()):
            self.status.set_text(_('Language saved. Reopen Husk applications to apply it.'))
        else:
            # A failed write must not leave the selector claiming a saved choice.
            widget.handler_block(self.language_handler)
            try: widget.set_active_id(self.settings['language'])
            finally: widget.handler_unblock(self.language_handler)

    def choose_wallpaper(self, _button):
        dialog = Gtk.FileChooserDialog(title=_('Choose wallpaper'), transient_for=self, action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(_('Cancel'), Gtk.ResponseType.CANCEL, _('Select'), Gtk.ResponseType.OK)
        filt = Gtk.FileFilter(); filt.set_name(_('Images')); filt.add_pixbuf_formats(); dialog.add_filter(filt)
        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename(); self.save('wallpaper', path); self.wallpaper.set_text(path)
        dialog.destroy()

    def updates_page(self, box):
        box.pack_start(row_box(_('System updates'), _('Run a full pacman -Syu upgrade. Pacman will show package changes in the terminal and ask for confirmation. Automatic rollback is not available in this experimental release.')), False, False, 0)
        button = Gtk.Button(label=_('Open system update'))
        button.connect('clicked', lambda _: terminal(['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'update'], self))
        box.pack_start(button, False, False, 0)
        for id, label in [('own', _('Husk Desktop')), ('kde', 'KDE Plasma'), ('gnome', 'GNOME')]:
            button = Gtk.Button(label=_('Install {desktop}').format(desktop=label))
            button.connect('clicked', lambda _, choice=id: terminal(['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'desktop', choice], self))
            box.pack_start(button, False, False, 0)
        driver = Gtk.Button(label=_('Install the NVIDIA Turing+ / RTX driver'))
        def install_driver(_button):
            if confirm(self, _('Is your GPU Turing or newer?'), _('Supports cards such as the RTX 20/30/40/50 series and GTX 1650. Pascal and older cards are not supported. Read the driver documentation before continuing.')):
                terminal(['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'driver', 'nvidia-open'], self)
        driver.connect('clicked', install_driver); box.pack_start(driver, False, False, 0)


def main(page=None):
    window = ControlWindow(page=page); window.connect('destroy', lambda _: Gtk.main_quit())
    window.show_all(); Gtk.main()

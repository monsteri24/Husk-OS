import shutil
import subprocess
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from ownos.identity import OS_NAME, VERSION
from ownos.config import ConfigStore, KEYMAPS
from ownos.metrics import SystemSampler
from ownos.library import discover_steam_games
from ownos.input_config import write_input_config
from ownos.ui.common import Gtk, GLib, load_style, remove_style, row_box, spawn, terminal, error, confirm, require_display


class ControlWindow(Gtk.Window):
    def __init__(self, store=None):
        require_display()
        super().__init__(title='Husk Gaming Control Center · Experimental')
        self.set_default_size(900, 650)
        self.store = store or ConfigStore(); self.settings = self.store.load()
        self.provider = load_style(self.settings, self.store.path.parent / "desktop.css"); self.sampler = SystemSampler()
        self.closed = False; self.monitor_busy = False
        self.connect('destroy', self.cleanup)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15); outer.set_border_width(22)
        self.add(outer)
        title = Gtk.Label(label='Husk Gaming Control Center', xalign=0); title.get_style_context().add_class('title')
        outer.pack_start(title, False, False, 0)
        outer.pack_start(Gtk.Label(label=f'{OS_NAME} · {VERSION} · Experimental', xalign=0), False, False, 0)
        notebook = Gtk.Notebook(); outer.pack_start(notebook, True, True, 0)
        for title, create in [('Gaming', self.gaming_page), ('Järjestelmä', self.system_page),
                              ('Syöttölaitteet', self.input_page), ('Ulkoasu', self.appearance_page), ('Päivitykset', self.updates_page)]:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16); box.set_border_width(20)
            create(box); scroll = Gtk.ScrolledWindow(); scroll.add(box)
            notebook.append_page(scroll, Gtk.Label(label=title))
        self.status = Gtk.Label(xalign=0); outer.pack_start(self.status, False, False, 0)
        self.timer = GLib.timeout_add_seconds(2, self.sample)
        self.sample()

    def cleanup(self, *_):
        self.closed = True
        if self.timer: GLib.source_remove(self.timer); self.timer = None
        remove_style(self.provider)

    def save(self, key, value):
        settings = dict(self.settings); settings[key] = value
        try: self.store.save(settings)
        except (OSError, ValueError) as exc: error(self, exc); return False
        self.settings = settings; self.status.set_text('Asetus tallennettu.')
        return True

    def switch_row(self, box, title, detail, key):
        row = Gtk.Box(spacing=16); row.pack_start(row_box(title, detail), True, True, 0)
        switch = Gtk.Switch(); switch.set_valign(Gtk.Align.CENTER); switch.set_active(self.settings[key])
        switch.connect('notify::active', lambda obj, _: self.save(key, obj.get_active()))
        row.pack_end(switch, False, False, 0); box.pack_start(row, False, False, 0)
        return switch

    def gaming_page(self, box):
        self.gaming_switch = self.switch_row(box, 'GameMode käynnistyskääre',
            'Koskee husk-game-kääreellä käynnistettyjä pelejä. Steamissa käytä käynnistysasetusta husk-game -- %command%. Muutokset koskevat seuraavaa käynnistystä.', 'gaming_mode')
        self.switch_row(box, 'FPS / frametime-overlay', 'MangoHud aktivoidaan husk-game-kääreessä. Kaikki pelit tai grafiikkarajapinnat eivät tue overlayta.', 'overlay')
        box.pack_start(row_box('Steam-pelit', 'Pelit luetaan paikallisista Steam-kirjastoista. Heroicin ja Lutrisin pelit hallitaan niiden omissa sovelluksissa.'), False, False, 0)
        self.games = Gtk.ListBox(); self.games.set_selection_mode(Gtk.SelectionMode.NONE)
        box.pack_start(self.games, True, True, 0)
        self.refresh_games()
        button = Gtk.Button(label='Päivitä pelilista'); button.connect('clicked', lambda _: self.refresh_games())
        box.pack_start(button, False, False, 0)

    def refresh_games(self):
        for child in self.games.get_children(): self.games.remove(child)
        games = discover_steam_games()
        if not games: self.games.add(Gtk.Label(label='Paikallisia Steam-pelejä ei löytynyt.'))
        for game in games:
            row = Gtk.Box(spacing=12); row.set_border_width(8)
            row.pack_start(Gtk.Label(label=game.name, xalign=0), True, True, 0)
            button = Gtk.Button(label='Käynnistä')
            button.connect('clicked', lambda _, appid=game.appid: spawn(['/usr/bin/steam', '-applaunch', appid], self))
            row.pack_end(button, False, False, 0); self.games.add(row)
        self.games.show_all()

    def system_page(self, box):
        self.cpu = Gtk.ProgressBar(); self.cpu.set_show_text(True)
        self.ram = Gtk.ProgressBar(); self.ram.set_show_text(True)
        self.gpu = Gtk.Label(label='GPU-kuormitus: ei vielä mitattu', xalign=0)
        for label, widget in [('CPU', self.cpu), ('RAM', self.ram), ('GPU', self.gpu)]:
            box.pack_start(row_box(label), False, False, 0); box.pack_start(widget, False, False, 0)
        self.driver = Gtk.Label(label='Ajuritiedot: luetaan…', xalign=0); self.driver.set_line_wrap(True)
        box.pack_start(self.driver, False, False, 0)
        threading.Thread(target=self.read_drivers, daemon=True).start()
        button = Gtk.Button(label='Näytöt ja virkistystaajuus · wdisplays')
        button.connect('clicked', lambda _: spawn(['/usr/bin/wdisplays'], self))
        box.pack_start(button, False, False, 0)

    def read_drivers(self):
        try:
            text = subprocess.run(['/usr/bin/lspci', '-k'], capture_output=True, text=True, timeout=5).stdout
            lines = text.splitlines(); keep = []
            for i, line in enumerate(lines):
                if 'VGA compatible' in line or '3D controller' in line or 'Display controller' in line:
                    keep += lines[i:i + 4]
            result = '\n'.join(keep) or 'Näytönohjaimen tietoja ei löytynyt.'
        except (OSError, subprocess.TimeoutExpired): result = 'lspci ei ole saatavilla.'
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
                    self.cpu.set_text(f"{result['cpu_percent']:.1f} %")
                    total = result['ram_total_bytes']; used = result['ram_used_bytes']
                    self.ram.set_fraction(used / total if total else 0)
                    self.ram.set_text(f'{used / 2**30:.2f} / {total / 2**30:.2f} GiB')
                    gpu = result['gpu_percent']
                    self.gpu.set_text('GPU-kuormitus: ' + (str(gpu) + ' %' if gpu is not None else 'Ajuri ei tarjoa sysfs-mittaria.'))
                return False
            GLib.idle_add(update)
        threading.Thread(target=read, daemon=True).start()
        return True

    def input_page(self, box):
        box.pack_start(row_box('Husk Desktopin syöttöasetukset', 'Asetukset koskevat omaa labwc-istuntoa. KDE/GNOME käyttävät omia syöttöasetuksiaan.'), False, False, 0)
        self.keymap = Gtk.ComboBoxText()
        for code in KEYMAPS: self.keymap.append(code, code.upper())
        self.keymap.set_active_id(self.settings['keymap']); box.pack_start(self.keymap, False, False, 0)
        self.speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1, 1, 0.05)
        self.speed.set_value(self.settings['pointer_speed'])
        box.pack_start(row_box('Hiiren nopeus', 'Libinputin nopeus −1…1. Oma istunto käyttää tasaista (flat) hiiriprofiilia.'), False, False, 0)
        box.pack_start(self.speed, False, False, 0)
        apply = Gtk.Button(label='Tallenna ja lataa Husk Desktopin asetukset')
        apply.connect('clicked', self.apply_input); box.pack_start(apply, False, False, 0)

    def apply_input(self, _):
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
                    self.status.set_text('Husk Desktopin asetukset ladattu.'); return
            self.status.set_text('Tallennettu seuraavaan Husk Desktop-istuntoon.')
        except (OSError, ET.ParseError, subprocess.TimeoutExpired) as exc: error(self, exc)

    def appearance_page(self, box):
        box.pack_start(row_box('Husk Desktopin paneeli', 'Windows-henkinen MVP on välivaihe. Paneeli ja käynnistin ovat erillisiä komponentteja.'), False, False, 0)
        position = Gtk.ComboBoxText()
        position.append('bottom', 'Alareuna'); position.append('top', 'Yläreuna')
        position.set_active_id(self.settings['taskbar_position'])
        position.connect('changed', lambda widget: self.save('taskbar_position', widget.get_active_id()))
        box.pack_start(position, False, False, 0)
        box.pack_start(row_box('Oma CSS', str(self.store.path.parent / 'desktop.css') + ' · muutokset latautuvat Husk Desktopiin ilman käyttöjärjestelmän uudelleenrakentamista.'), False, False, 0)
        self.switch_row(box, 'Kevyet animaatiot', 'Käyttöliittymän lyhyet siirtymät.', 'animations')
        box.pack_start(row_box('Korostusväri'), False, False, 0)
        color = Gtk.ColorButton(); from ownos.ui.common import Gdk
        rgba = Gdk.RGBA(); rgba.parse(self.settings['accent']); color.set_rgba(rgba)
        def changed(button):
            c = button.get_rgba(); self.save('accent', '#%02x%02x%02x' % (int(c.red * 255), int(c.green * 255), int(c.blue * 255)))
        color.connect('color-set', changed); box.pack_start(color, False, False, 0)
        self.wallpaper = Gtk.Label(label=self.settings['wallpaper'] or 'Oma sininen oletustausta', xalign=0)
        self.wallpaper.set_line_wrap(True); box.pack_start(self.wallpaper, False, False, 0)
        button = Gtk.Button(label='Valitse taustakuva'); button.connect('clicked', self.choose_wallpaper)
        box.pack_start(button, False, False, 0)
        reset = Gtk.Button(label='Palauta oletustausta')
        reset.connect('clicked', lambda _: (self.save('wallpaper', ''), self.wallpaper.set_text('Oma sininen oletustausta')))
        box.pack_start(reset, False, False, 0)

    def choose_wallpaper(self, _):
        dialog = Gtk.FileChooserDialog(title='Valitse taustakuva', transient_for=self, action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Peruuta', Gtk.ResponseType.CANCEL, 'Valitse', Gtk.ResponseType.OK)
        filt = Gtk.FileFilter(); filt.set_name('Kuvat'); filt.add_pixbuf_formats(); dialog.add_filter(filt)
        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename(); self.save('wallpaper', path); self.wallpaper.set_text(path)
        dialog.destroy()

    def updates_page(self, box):
        box.pack_start(row_box('Järjestelmäpäivitykset', 'Täydellinen pacman -Syu. Pacman näyttää pakettimuutokset terminaalissa ja pyytää vahvistuksen. Automaattista palautusta ei ole tässä MVP:ssä.'), False, False, 0)
        button = Gtk.Button(label='Avaa järjestelmäpäivitys')
        button.connect('clicked', lambda _: terminal(['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'update'], self))
        box.pack_start(button, False, False, 0)
        for id, label in [('own', 'Husk Desktop'), ('kde', 'KDE Plasma'), ('gnome', 'GNOME')]:
            button = Gtk.Button(label='Asenna ' + label)
            button.connect('clicked', lambda _, choice=id: terminal(['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'desktop', choice], self))
            box.pack_start(button, False, False, 0)
        driver = Gtk.Button(label='Asenna NVIDIA Turing+ / RTX -ajuri')
        def install_driver(_):
            if confirm(self, 'Onko GPU Turing tai uudempi?', 'Sopii esimerkiksi RTX 20/30/40/50 -sarjoille ja GTX 1650:lle. Ei Pascalille tai vanhemmille. Lue ajuridokumentaatio ennen muutosta.'):
                terminal(['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'driver', 'nvidia-open'], self)
        driver.connect('clicked', install_driver); box.pack_start(driver, False, False, 0)


def main():
    window = ControlWindow(); window.connect('destroy', lambda _: Gtk.main_quit())
    window.show_all(); Gtk.main()

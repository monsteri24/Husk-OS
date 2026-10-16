import shutil
import subprocess
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, Gio, GLib, GdkPixbuf
from ownos.catalog import app_by_id
from ownos.config import ConfigStore
from ownos.themes import read_user_css


def require_display():
    if not Gtk.init_check()[0] or Gdk.Display.get_default() is None:
        raise RuntimeError('GTK-näyttöyhteys puuttuu. Avaa ohjelma graafisessa istunnossa; headless-testissä käytä Xvfb:tä tai labwc:tä.')


def create_style_provider(settings=None, override_path=None):
    source = Path(__file__).resolve().parents[3] / 'data/style.css'
    if not source.exists(): source = Path('/usr/share/ownos/style.css')
    css = source.read_text(encoding='utf-8')
    if settings:
        css += '\n@define-color accent ' + settings['accent'] + ';\n'
        if not settings['animations']: css += '\n* { transition-duration: 0s; }\n'
    provider = Gtk.CssProvider()
    provider.husk_style_warning = ''
    try:
        override = read_user_css(override_path or ConfigStore().path.parent / 'desktop.css')
        provider.load_from_data(css.encode() + b'\n' + override)
    except (OSError, ValueError, GLib.Error) as exc:
        provider.husk_style_warning = str(exc)
        provider.load_from_data(css.encode())
    return provider


def load_style(settings=None, override_path=None):
    provider = create_style_provider(settings, override_path)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    return provider


def remove_style(provider):
    if provider: Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(), provider)


def error(parent, message):
    dialog = Gtk.MessageDialog(transient_for=parent, modal=True,
                               message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE,
                               text='Toiminto ei onnistunut')
    dialog.format_secondary_text(str(message)[:2000]); dialog.run(); dialog.destroy()


def confirm(parent, title, detail):
    dialog = Gtk.MessageDialog(transient_for=parent, modal=True,
                               message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL,
                               text=title)
    dialog.format_secondary_text(detail)
    result = dialog.run() == Gtk.ResponseType.OK; dialog.destroy()
    return result


def spawn(argv, parent=None):
    try:
        return subprocess.Popen(list(argv), shell=False, start_new_session=True)
    except OSError as exc:
        error(parent, exc)
        return None


def terminal(argv, parent=None):
    exe = shutil.which('foot')
    if not exe:
        error(parent, 'Foot-terminaali puuttuu. Asenna foot ennen tämän toiminnon käyttöä.')
        return None
    return spawn([exe, '-e', *argv], parent)


def icon(name, size=24):
    image = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.BUTTON)
    image.set_pixel_size(size)
    return image


def icon_button(name, tip, callback):
    button = Gtk.Button(); button.add(icon(name)); button.set_tooltip_text(tip)
    button.connect('clicked', lambda _: callback())
    return button


def installed(app):
    if app.flatpak_id:
        flatpak = shutil.which('flatpak')
        if not flatpak: return False
        try:
            return subprocess.run([flatpak, 'info', app.flatpak_id], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=4).returncode == 0
        except (OSError, subprocess.TimeoutExpired): return False
    return shutil.which(Path(app.command[0]).name) is not None


def launch_app(appid, parent=None):
    app = app_by_id(appid)
    if installed(app): return spawn(app.command, parent)
    detail = ('Asennus käyttäjäkohtaiseen Flatpakiin Flathubista. Asentaja näyttää riippuvuudet ja pyytää vahvistuksen.'
              if app.flatpak_id else 'Asennus Archin allekirjoitetuista paketeista täydellä järjestelmäpäivityksellä. Pacman näyttää muutokset ja pyytää vahvistuksen.')
    if confirm(parent, 'Asennetaanko ' + app.name + '?', detail):
        return terminal(['/usr/bin/husk-install-app', appid], parent)


def open_path(path, parent=None):
    path = Path(path)
    if path.suffix == '.desktop':
        if not confirm(parent, 'Suoritetaanko pikakuvake?', str(path) + '\nVarmista, että luotat tämän tiedoston alkuperään.'): return
        app = Gio.DesktopAppInfo.new_from_filename(str(path))
        if not app: error(parent, 'Virheellinen .desktop-tiedosto'); return
        try: app.launch([], None)
        except GLib.Error as exc: error(parent, exc)
    else:
        try: Gio.AppInfo.launch_default_for_uri(path.absolute().as_uri(), None)
        except (GLib.Error, OSError) as exc: error(parent, exc)


def row_box(title, description=''):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    label = Gtk.Label(label=title, xalign=0); label.get_style_context().add_class('heading')
    box.pack_start(label, False, False, 0)
    if description:
        label = Gtk.Label(label=description, xalign=0); label.set_line_wrap(True)
        label.get_style_context().add_class('muted'); box.pack_start(label, False, False, 0)
    return box

import shutil
import subprocess
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, Gio, GLib, GdkPixbuf
from ownos.catalog import app_by_id
from ownos.app_install import app_installed
from ownos.config import ConfigStore
from ownos.dialog_input import FreshActivation
from ownos.i18n import _
from ownos.themes import read_user_css


def require_display():
    if not Gtk.init_check()[0] or Gdk.Display.get_default() is None:
        raise RuntimeError(_('No GTK display connection. Open this application in a graphical session; use Xvfb or labwc for headless testing.'))


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
    if settings is None:
        settings = ConfigStore().load()
    gtk_settings = Gtk.Settings.get_default()
    if gtk_settings:
        gtk_settings.set_property('gtk-application-prefer-dark-theme', True)
    provider = create_style_provider(settings, override_path)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    return provider


def remove_style(provider):
    if provider: Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(), provider)


def error(parent, message):
    dialog = Gtk.MessageDialog(transient_for=parent, modal=True,
                               message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.NONE,
                               text=_('The operation could not be completed'))
    dialog.add_button(_('Close'), Gtk.ResponseType.CLOSE)
    dialog.format_secondary_text(str(message)[:2000]); dialog.run(); dialog.destroy()


class ConfirmationDialog(Gtk.MessageDialog):
    """Cancel is safe by default; OK requires its own fresh input pair.

    The OK button deliberately has no automatic Gtk.Dialog response mapping.
    An inherited release/click from the launcher or another button therefore
    cannot confirm the transaction. A focused keyboard press must also receive
    its matching release, including releasing a held opening key first.
    """
    def __init__(self, parent, title, detail):
        super().__init__(transient_for=parent, modal=True,
                         message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE,
                         text=title)
        opening = Gtk.get_current_event()
        opening_key = (opening.keyval if opening is not None and
                       opening.type == Gdk.EventType.KEY_PRESS else None)
        self.activation = FreshActivation(opening_key)
        self.format_secondary_text(detail)
        self.set_default_size(460, -1)
        self.cancel_button = self.add_button(_('Cancel'), Gtk.ResponseType.CANCEL)
        self.confirm_button = Gtk.Button(label=_('OK'))
        area = self.get_action_area()
        area.set_spacing(12)
        area.set_border_width(12)
        area.pack_end(self.confirm_button, False, False, 0)
        self.confirm_button.show()
        for button in (self.cancel_button, self.confirm_button):
            button.set_size_request(112, -1)
        self.set_default_response(Gtk.ResponseType.CANCEL)
        self.cancel_button.grab_focus()
        self.confirm_button.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                                       Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.KEY_RELEASE_MASK |
                                       Gdk.EventMask.LEAVE_NOTIFY_MASK | Gdk.EventMask.FOCUS_CHANGE_MASK)
        self.confirm_button.connect('button-press-event', self._pointer_press)
        self.confirm_button.connect('button-release-event', self._pointer_release)
        self.confirm_button.connect('key-press-event', self._key_press)
        self.confirm_button.connect('key-release-event', self._key_release)
        for signal in ('leave-notify-event', 'focus-out-event', 'grab-broken-event'):
            self.confirm_button.connect(signal, self._cancel_activation)
        self.connect('key-press-event', self._opening_key_press)
        self.connect('key-release-event', self._opening_key_release)
        self.connect('unmap', lambda _: self.activation.cancel())

    @staticmethod
    def _inside(button, event):
        # GtkButton's input window gives widget-local coordinates even when
        # the containing dialog is moved or running under Wayland.
        return 0 <= event.x < button.get_allocated_width() and 0 <= event.y < button.get_allocated_height()

    def _pointer_press(self, button, event):
        if event.type != Gdk.EventType.BUTTON_PRESS:
            self.activation.cancel()
            return True
        self.activation.pointer_press(event.button, self._inside(button, event))
        if event.button == 1:
            button.grab_focus()
            button.set_state_flags(Gtk.StateFlags.ACTIVE, False)
        return True

    def _pointer_release(self, button, event):
        button.unset_state_flags(Gtk.StateFlags.ACTIVE)
        if self.activation.pointer_release(event.button, self._inside(button, event)):
            self.response(Gtk.ResponseType.OK)
        return True

    def _key_press(self, button, event):
        if event.keyval not in FreshActivation.KEYS:
            return False
        modified = bool(event.state & Gtk.accelerator_get_default_mod_mask())
        self.activation.key_press(event.keyval, modified)
        if not modified:
            button.set_state_flags(Gtk.StateFlags.ACTIVE, False)
        return True

    def _key_release(self, button, event):
        if event.keyval not in FreshActivation.KEYS:
            return False
        button.unset_state_flags(Gtk.StateFlags.ACTIVE)
        modified = bool(event.state & Gtk.accelerator_get_default_mod_mask())
        if self.activation.key_release(event.keyval, modified):
            self.response(Gtk.ResponseType.OK)
        return True

    def _opening_key_press(self, _, event):
        # A repeated Return must not reach GtkWindow's default Cancel action.
        return self.activation.is_opening_key(event.keyval)

    def _opening_key_release(self, _, event):
        if self.activation.is_opening_key(event.keyval):
            self.activation.key_release(event.keyval)
            return True
        # GtkWindow emits this before its default handler forwards the event
        # to the focused button. Do not consume that button's armed key pair.
        if self.get_focus() != self.confirm_button:
            self.activation.key_release(event.keyval)
        return False

    def _cancel_activation(self, button, _):
        self.activation.cancel()
        button.unset_state_flags(Gtk.StateFlags.ACTIVE)
        return False


def confirm(parent, title, detail):
    dialog = ConfirmationDialog(parent, title, detail)
    try:
        return dialog.run() == Gtk.ResponseType.OK
    finally:
        dialog.destroy()


def spawn(argv, parent=None):
    try:
        return subprocess.Popen(list(argv), shell=False, start_new_session=True)
    except OSError as exc:
        error(parent, exc)
        return None


def terminal(argv, parent=None, hold=False):
    exe = shutil.which('foot')
    if not exe:
        error(parent, _('The foot terminal is not installed. Install foot to use this action.'))
        return None
    return spawn([exe, *(['--hold'] if hold else []), '-e', *argv], parent)


def _icon_directory():
    source = Path(__file__).resolve().parents[3] / 'data/icons'
    return source if source.is_dir() else Path('/usr/share/icons/hicolor/scalable/apps')


def _icon_theme():
    theme = Gtk.IconTheme.get_default()
    # The source preview has no installed hicolor theme. An unthemed search
    # directory also keeps our fallback available in third-party icon themes.
    directory = str(_icon_directory())
    if directory not in theme.get_search_path():
        theme.append_search_path(directory)
    # Optional-app artwork is shipped independently of the optional app. Keep
    # upstream brand art separate from Husk's original interface icon set.
    source = Path(__file__).resolve().parents[3] / 'data/app-icons'
    artwork = str(source if source.is_dir() else Path('/usr/share/ownos/app-icons'))
    if artwork not in theme.get_search_path():
        theme.append_search_path(artwork)
    installer = Path(__file__).resolve().parents[3] / 'installer'
    if installer.is_dir() and str(installer) not in theme.get_search_path():
        theme.append_search_path(str(installer))
    return theme


def _loadable_icon(theme, name, size):
    if isinstance(name, Gio.Icon):
        info = theme.lookup_by_gicon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
    elif isinstance(name, str) and name:
        info = theme.lookup_icon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
    else:
        return False
    if info is None:
        return False
    try:
        # A name may exist in the theme cache but reference an unreadable file.
        return info.load_icon() is not None
    except GLib.Error:
        return False


def icon(name, size=24, fallback='husk-app'):
    """Use installed application art when loadable, with a bundled fallback.

    Validate both names and desktop-file GIcons before handing them to GTK:
    Gtk.Image otherwise silently displays its missing-image placeholder.
    Keep the result themed so GTK handles symbolic colors and display scale.
    """
    theme = _icon_theme()
    for candidate in (name, fallback, 'husk-app'):
        if not _loadable_icon(theme, candidate, size):
            continue
        image = (Gtk.Image.new_from_gicon(candidate, Gtk.IconSize.BUTTON)
                 if isinstance(candidate, Gio.Icon)
                 else Gtk.Image.new_from_icon_name(candidate, Gtk.IconSize.BUTTON))
        break
    else:
        # Bypass a damaged third-party theme's override of our fallback name.
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(_icon_directory() / 'husk-app.svg'), size, size, True)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
    image.set_pixel_size(size)
    image.set_size_request(size, size)
    image.set_halign(Gtk.Align.CENTER); image.set_valign(Gtk.Align.CENTER)
    return image


def icon_button(name, tip, callback, fallback='husk-app'):
    button = Gtk.Button(); button.add(icon(name, fallback=fallback)); button.set_tooltip_text(tip)
    button.get_accessible().set_name(tip)
    button.connect('clicked', lambda _: callback())
    return button


def installed(app):
    return app_installed(app)


def launch_app(appid, parent=None):
    app = app_by_id(appid)
    if installed(app): return spawn(app.command, parent)
    from ownos.ui.app_install import AppInstallWindow, installation_detail
    if confirm(parent, _('Install {application}?').format(application=app.name), installation_detail(app)):
        window = AppInstallWindow(appid, parent)
        window.begin()
        return window


def open_path(path, parent=None):
    path = Path(path)
    if path.suffix == '.desktop':
        if not confirm(parent, _('Run this shortcut?'), _('{path}\nMake sure you trust the source of this file.').format(path=path)): return
        app = Gio.DesktopAppInfo.new_from_filename(str(path))
        if not app: error(parent, _('Invalid .desktop file')); return
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

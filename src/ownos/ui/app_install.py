"""Native curated-app installation with real backend output and stage names."""
import json
from pathlib import Path
import subprocess
import threading

from ownos.app_install import (InstallProblem, app_installed, graphical_commands,
                              live_authentication_state, preflight_install,
                              transaction_problem, transaction_stage)
from ownos.catalog import app_by_id
from ownos.i18n import _
from ownos.live_password import valid_password
from ownos.ui.common import Gtk, GLib, confirm, icon, load_style, require_display, spawn


def installation_detail(app):
    if app.flatpak_id:
        return _('Install the official Heroic Flatpak from Flathub for your user, including its required runtimes. The download may be large. No administrator password is needed. Nothing is installed until you choose Install.')
    return _('Install signed Arch packages and their dependencies. This also refreshes package databases and upgrades ALL out-of-date system packages (pacman -Syu). The download may be large. After authorization the transaction runs without another package prompt. In Live mode, changes and a temporary password last only for this session.')


def set_live_password(password):
    """Pass the secret through stdin, never a command argument or log line."""
    helper = Path(__file__).resolve().parents[1] / 'live_password.py'
    result = subprocess.run(['/usr/bin/python3', '-I', str(helper)],
                            input=json.dumps(password, ensure_ascii=False).encode('utf-8') + b'\n',
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=45, check=False)
    if result.returncode or live_authentication_state() != 'ready':
        raise InstallProblem('password', _('The temporary password could not be set.'),
                             _('Try a stronger password. If the problem continues, check the Live account configuration. No package transaction has started.'))


class LivePasswordDialog(Gtk.Dialog):
    """Collect only the temporary Live password; polkit handles authorization."""
    def __init__(self, parent):
        super().__init__(title=_('Set a temporary Live password'), transient_for=parent,
                         modal=True, destroy_with_parent=True)
        self.set_default_size(460, -1)
        self.add_button(_('Cancel'), Gtk.ResponseType.CANCEL)
        self.set_button = self.add_button(_('Set password'), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.CANCEL)
        area = self.get_content_area()
        area.set_border_width(20); area.set_spacing(12)
        detail = Gtk.Label(label=_('Choose a password for the live account. It lasts for this Live session. After it is set, enter it once in the system authorization dialog to approve installation.'), xalign=0)
        detail.set_line_wrap(True); detail.set_max_width_chars(56)
        area.pack_start(detail, False, False, 0)
        self.password = Gtk.Entry(visibility=False, input_purpose=Gtk.InputPurpose.PASSWORD)
        self.password.set_placeholder_text(_('Temporary password (8–128 characters)'))
        self.repeat = Gtk.Entry(visibility=False, input_purpose=Gtk.InputPurpose.PASSWORD)
        self.repeat.set_placeholder_text(_('Repeat password'))
        for entry in (self.password, self.repeat):
            entry.set_max_length(128)
            entry.set_activates_default(False)
            entry.connect('changed', self._validate)
            area.pack_start(entry, False, False, 0)
        self.message = Gtk.Label(xalign=0); self.message.set_line_wrap(True)
        area.pack_start(self.message, False, False, 0)
        self._validate()
        self.show_all()

    def _validate(self, *_):
        password, repeated = self.password.get_text(), self.repeat.get_text()
        self.set_button.set_sensitive(valid_password(password) and password == repeated)
        self.message.set_text(_('Passwords do not match.') if repeated and password != repeated else '')

    def take_password(self):
        value = self.password.get_text()
        self.password.set_text(''); self.repeat.set_text('')
        return value


class AppInstallWindow(Gtk.Window):
    """Network checks precede account setup, polkit and the package transaction.

    Closing during read-only checks cancels them. Once a transaction starts,
    the window stays open until the backend finishes; killing pacman midway
    through system updates is deliberately not offered as a Cancel action.
    """
    def __init__(self, appid, parent=None):
        require_display()
        super().__init__(title=_('Install {application}').format(application=app_by_id(appid).name))
        if parent:
            self.set_transient_for(parent)
        self.app = app_by_id(appid)
        self.provider = load_style()
        self.set_default_size(640, 470)
        self.set_border_width(24)
        self.state, self.closed = 'ready', False
        self.result_code = 1
        self.cancelled = threading.Event()
        self.connect('delete-event', self._delete)
        self.connect('destroy', self._destroy)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16); self.add(box)
        heading = Gtk.Box(spacing=14)
        heading.pack_start(icon(self.app.icon, 48), False, False, 0)
        title = Gtk.Label(label=self.app.name, xalign=0)
        title.get_style_context().add_class('heading')
        heading.pack_start(title, True, True, 0); box.pack_start(heading, False, False, 0)
        self.detail = Gtk.Label(label=installation_detail(self.app), xalign=0)
        self.detail.set_line_wrap(True); self.detail.set_max_width_chars(74)
        box.pack_start(self.detail, False, False, 0)
        self.status = Gtk.Label(label=_('Ready to install.'), xalign=0)
        self.status.set_line_wrap(True); self.status.set_selectable(True)
        box.pack_start(self.status, False, False, 0)
        self.progress = Gtk.ProgressBar(show_text=False)
        box.pack_start(self.progress, False, False, 0)
        self.explanation = Gtk.Label(xalign=0); self.explanation.set_line_wrap(True)
        self.explanation.set_selectable(True)
        box.pack_start(self.explanation, False, False, 0)
        expander = Gtk.Expander(label=_('Transaction details'))
        scroll = Gtk.ScrolledWindow(); scroll.set_min_content_height(140)
        self.output = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                   wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroll.add(self.output); expander.add(scroll)
        box.pack_start(expander, True, True, 0)
        actions = Gtk.Box(spacing=10)
        self.network_button = Gtk.Button(label=_('Network settings'))
        self.network_button.connect('clicked', lambda _: spawn(['/usr/bin/husk-control', '--page', 'system'], self))
        actions.pack_start(self.network_button, False, False, 0)
        self.cancel_button = Gtk.Button(label=_('Cancel'))
        self.cancel_button.connect('clicked', self._close)
        self.install_button = Gtk.Button(label=_('Install') if self.app.flatpak_id else _('Install and update system'))
        self.install_button.connect('clicked', self._install)
        actions.pack_end(self.install_button, False, False, 0)
        actions.pack_end(self.cancel_button, False, False, 0)
        box.pack_end(actions, False, False, 0)
        self.pulse_source = GLib.timeout_add(120, self._pulse)
        self.show_all()
        self.progress.hide()
        self.cancel_button.grab_focus()

    def _post(self, callback, *args):
        def invoke():
            if not self.closed:
                callback(*args)
            return False
        GLib.idle_add(invoke)

    def _pulse(self):
        if self.closed:
            return False
        if self.state in ('checking', 'password', 'installing'):
            self.progress.pulse()
        return True

    def _append(self, text):
        buffer = self.output.get_buffer()
        buffer.insert(buffer.get_end_iter(), text)
        # Keep details bounded without writing a transaction/credential log.
        if buffer.get_char_count() > 100000:
            buffer.delete(buffer.get_start_iter(), buffer.get_iter_at_offset(20000))

    def _delete(self, *_):
        if self.state in ('password', 'installing'):
            return True
        return False

    def _destroy(self, *_):
        self.closed = True
        self.cancelled.set()
        if self.pulse_source:
            GLib.source_remove(self.pulse_source)
            self.pulse_source = None
        from ownos.ui.common import remove_style
        remove_style(self.provider)

    def _close(self, *_):
        if self.state not in ('password', 'installing'):
            self.destroy()

    def _install(self, *_):
        # Each retry is a new informed decision, with new network/auth checks.
        if self.state not in ('ready', 'failed'):
            return
        if not confirm(self, _('Install {application}?').format(application=self.app.name), installation_detail(self.app)):
            return
        self.begin()

    def begin(self):
        if self.state not in ('ready', 'failed'):
            return
        self.state = 'checking'
        self.install_button.set_sensitive(False)
        self.cancel_button.set_label(_('Cancel'))
        self.explanation.set_text(_('Checking the connection before asking for a password. No packages have been changed.'))
        self.progress.show()
        self.output.get_buffer().set_text('')
        threading.Thread(target=self._preflight, daemon=True).start()

    def _preflight(self):
        try:
            preflight_install(self.app, report=lambda message: self._post(self.status.set_text, message),
                              cancelled=self.cancelled.is_set)
            auth = 'ready' if self.app.flatpak_id else live_authentication_state()
            if not self.cancelled.is_set():
                self._post(self._authentication, auth)
        except InstallProblem as exc:
            self._post(self._failed, exc)
        except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            self._post(self._failed, InstallProblem('configuration', _('The installation checks could not be completed.'), str(exc)))

    def _authentication(self, auth):
        if auth == 'setup':
            dialog = LivePasswordDialog(self)
            try:
                if dialog.run() != Gtk.ResponseType.OK:
                    self._failed(InstallProblem('cancelled', _('Installation cancelled.'), _('No password was set and no package transaction started.')))
                    return
                password = dialog.take_password()
            finally:
                dialog.destroy()
            self.state = 'password'
            self.cancel_button.set_sensitive(False)
            self.status.set_text(_('Setting the temporary Live password…'))
            self.explanation.set_text(_('The system authorization dialog follows. Use the temporary password you chose.'))
            threading.Thread(target=self._password, args=(password,), daemon=True).start()
        else:
            self._start_transaction()

    def _password(self, password):
        try:
            set_live_password(password)
            self._post(self._start_transaction)
        except (InstallProblem, OSError, subprocess.SubprocessError) as exc:
            problem = exc if isinstance(exc, InstallProblem) else InstallProblem('password', _('The temporary password could not be set.'), _('No package transaction has started.'))
            self._post(self._failed, problem)

    def _start_transaction(self):
        self.state = 'installing'
        self.cancel_button.set_sensitive(False)
        self.network_button.set_sensitive(False)
        self.status.set_text(_('Installing for your user…') if self.app.flatpak_id else _('Waiting for administrator authorization…'))
        self.explanation.set_text(_('Keep this window open until the package transaction finishes. Details below show the actual package-manager output.'))
        threading.Thread(target=self._transaction, daemon=True).start()

    def _transaction(self):
        transcript = ''
        try:
            for command, stage in graphical_commands(self.app):
                if stage == 'repository':
                    self._post(self.status.set_text, _('Preparing the trusted user Flathub repository…'))
                elif stage == 'install':
                    self._post(self.status.set_text, _('Downloading and installing the Flatpak and required runtimes…'))
                with subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, bufsize=1) as process:
                    for line in process.stdout:
                        transcript = (transcript + line)[-100000:]
                        self._post(self._append, line)
                        actual_stage = transaction_stage(line)
                        if actual_stage:
                            self._post(self.status.set_text, actual_stage)
                    status = process.wait()
                if status:
                    self._post(self._failed, transaction_problem(status, transcript, native=not bool(self.app.flatpak_id)))
                    return
            self._post(self.status.set_text, _('Verifying the installed application…'))
            if not app_installed(self.app):
                self._post(self._failed, InstallProblem('verification', _('Installation could not be verified.'),
                                                       _('The application is not recorded as installed. Review the transaction details before retrying.')))
                return
            self._post(self._success)
        except (OSError, subprocess.SubprocessError) as exc:
            self._post(self._failed, InstallProblem('transaction', _('The installer could not run the package transaction.'), str(exc)))

    def _failed(self, problem):
        self.state = 'failed'
        self.status.set_text(problem.message)
        self.explanation.set_text(problem.detail)
        self.progress.hide()
        self.cancel_button.set_sensitive(True); self.cancel_button.set_label(_('Close'))
        self.network_button.set_sensitive(True)
        self.install_button.set_sensitive(True); self.install_button.set_label(_('Retry'))
        self.install_button.get_accessible().set_description(_('Check connectivity and request authorization again.'))

    def _success(self):
        self.state = 'complete'
        self.result_code = 0
        self.progress.hide()
        self.status.set_text(_('{application} is installed (verified).').format(application=self.app.name))
        self.explanation.set_text(_('Select the application again in Husk Desktop to launch it.'))
        self.cancel_button.set_sensitive(True); self.cancel_button.set_label(_('Close'))
        self.install_button.hide()
        self.network_button.set_sensitive(True)


def main(appid):
    window = AppInstallWindow(appid)
    window.connect('destroy', lambda *_: Gtk.main_quit())
    Gtk.main()
    return window.result_code

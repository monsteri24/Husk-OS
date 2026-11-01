"""Unprivileged graphical entry point for the pinned Calamares installer."""
from pathlib import Path
import subprocess
import threading
from ownos.app_install import InstallProblem, live_authentication_state
from ownos.installer_display import DisplayAuthorizationError, installer_display_environment
from ownos.ui.app_install import LivePasswordDialog, set_live_password
from ownos.ui.common import Gtk, GLib, error, load_style, remove_style, require_display


def prerequisites():
    if not Path('/run/archiso/bootmnt/arch/x86_64/airootfs.sfs').is_file():
        raise ValueError('Start the installer from the Husk OS Live USB session.')
    if not Path('/sys/firmware/efi').is_dir():
        raise ValueError('Restart the Live USB in UEFI mode to install Husk OS. Legacy BIOS installation is not supported in this release.')
    if not Path('/usr/bin/calamares').is_file():
        raise ValueError('This Live image does not contain the graphical installer. Use the V3 installer image.')


class InstallerLauncher(Gtk.Window):
    def __init__(self):
        require_display()
        super().__init__(title='Install Husk OS')
        self.provider = load_style()
        self.set_default_size(650,400); self.set_border_width(28)
        self.closed = False; self.busy = False; self.process = None
        self.connect('destroy',self.cleanup)
        self.connect('delete-event',lambda *_: self.busy)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20); self.add(box)
        title = Gtk.Label(label='Welcome to Husk OS',xalign=0)
        title.get_style_context().add_class('title'); box.pack_start(title,False,False,0)
        detail = Gtk.Label(label='Install Husk OS on an internal SSD or hard drive.\n\n'
            'This version supports erasing one selected drive in UEFI mode. Existing files and operating systems on that drive will be removed. '
            'You will choose the drive, review its partitions and confirm the changes separately. The Live USB is protected.\n\n'
            'Back up files you want to keep before continuing. You can cancel before installation starts.',xalign=0)
        detail.set_line_wrap(True); detail.set_max_width_chars(70); box.pack_start(detail,True,True,0)
        self.status = Gtk.Label(xalign=0); self.status.set_line_wrap(True); box.pack_start(self.status,False,False,0)
        row = Gtk.Box(spacing=12); box.pack_end(row,False,False,0)
        self.cancel = Gtk.Button(label='Cancel'); self.cancel.connect('clicked',lambda *_: self.destroy())
        self.open = Gtk.Button(label='Open Installer'); self.open.connect('clicked',self.start)
        row.pack_start(self.cancel,False,False,0); row.pack_end(self.open,False,False,0)
        try: prerequisites()
        except (OSError,ValueError) as exc:
            self.status.set_text(str(exc)); self.open.set_sensitive(False)
        self.show_all(); self.cancel.grab_focus()

    def cleanup(self,*_):
        self.closed = True; remove_style(self.provider)

    def start(self,*_):
        if self.busy: return
        try:
            prerequisites()
            state = live_authentication_state()
            if state == 'setup':
                dialog = LivePasswordDialog(self)
                try:
                    if dialog.run() != Gtk.ResponseType.OK: return
                    secret = dialog.take_password()
                finally: dialog.destroy()
                self.busy=True; self.open.set_sensitive(False); self.cancel.set_sensitive(False)
                self.status.set_text('Setting the temporary Live password…')
                def password():
                    try:
                        set_live_password(secret); GLib.idle_add(self.authorize)
                    except (InstallProblem,OSError,subprocess.SubprocessError):
                        GLib.idle_add(self.failed,'The temporary Live password could not be set. No disk changes were started.')
                threading.Thread(target=password,daemon=True).start()
            elif state == 'ready': self.authorize()
            else: self.failed('The Live administrator account is unavailable. No disk changes were started.')
        except (ValueError,OSError,RuntimeError,InstallProblem,subprocess.SubprocessError) as exc:
            self.failed(str(exc))

    def authorize(self):
        if self.closed: return False
        self.busy=True; self.open.set_sensitive(False); self.cancel.set_sensitive(False)
        self.status.set_text('Authorize the installer in the system dialog. Disk selection and final confirmation follow.')
        def wait():
            try:
                with installer_display_environment() as environment:
                    self.process = subprocess.Popen(['/usr/bin/pkexec','/usr/lib/ownos/husk-installer-root'],
                                                    env=environment)
                    code = self.process.wait()
            except DisplayAuthorizationError as exc:
                GLib.idle_add(self.failed,str(exc)); return
            except (OSError,subprocess.SubprocessError):
                GLib.idle_add(self.failed,'The system authorization service could not start.'); return
            GLib.idle_add(self.finished,code)
        threading.Thread(target=wait,daemon=True).start()
        return False

    def finished(self,code):
        if self.closed: return False
        if code in (126,127): return self.failed('Authorization was cancelled or unavailable. No installation was started.')
        if code != 0:
            return self.failed('The installer stopped unexpectedly (status %s). Installation was not verified. An administrator can inspect /root/.cache/calamares/session.log before trying again.' % code)
        # A zero process exit also means the user may have cancelled Calamares.
        # Only Calamares's successful job queue displays installation success.
        self.destroy(); return False

    def failed(self,message):
        if self.closed: return False
        self.busy=False; self.open.set_sensitive(True); self.cancel.set_sensitive(True)
        self.status.set_text(message); return False


def main():
    window=InstallerLauncher(); window.connect('destroy',lambda *_:Gtk.main_quit())
    Gtk.main()

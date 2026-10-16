"""Installed-state verification and deliberate Live authentication setup."""
import os
import pwd
import subprocess
import sys
from pathlib import Path
from ownos.i18n import _


def app_installed(app):
    """Verify the package record, never a command found in an untrusted PATH."""
    command = (['/usr/bin/flatpak', 'info', '--user', app.flatpak_id]
               if app.flatpak_id else ['/usr/bin/pacman', '-Q', '--', app.package])
    try:
        return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=8, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _live_password_status(user):
    # Shadow's passwd(1) documents seven fields, with NP/P/L in field two.
    result = subprocess.run(['/usr/bin/passwd', '-S', user], capture_output=True,
                            text=True, check=True, timeout=8)
    fields = result.stdout.split()
    return fields[1] if len(fields) == 7 and fields[0] == user else ''


def prepare_live_authentication():
    """Set only the invoking Live user's password, using passwd's own TTY UI.

    Installed systems, other users and per-user Flatpak transactions do not
    enter this path. No password or generated input passes through Python.
    Authentication remains pkexec/polkit's responsibility after this returns.
    """
    if not Path('/run/archiso').is_dir():
        return 0
    try:
        user = pwd.getpwuid(os.getuid()).pw_name
    except (OSError, KeyError) as exc:
        print(_('Could not check the Live administrator password status: {error}').format(
            error=exc), file=sys.stderr, flush=True)
        return 1
    if user != 'live':
        return 0
    for check in range(2):
        try:
            state = _live_password_status(user)
        except (OSError, subprocess.SubprocessError) as exc:
            diagnostic = getattr(exc, 'stderr', None) or str(exc)
            print(_('Could not check the Live administrator password status: {error}').format(
                error=diagnostic), file=sys.stderr, flush=True)
            return getattr(exc, 'returncode', 1) or 1
        if state == 'P':
            return 0
        if state != 'NP' or check:
            break
        print(_('A temporary Live administrator password is required to install system applications. Set a password now, then enter it again in the authorization dialog. It lasts only for this Live session.'), flush=True)
        try:
            result = subprocess.call(['/usr/bin/passwd'])
        except OSError as exc:
            print(str(exc), file=sys.stderr, flush=True)
            return 1
        if result:
            return result
    print(_('The Live account does not have a usable administrator password. Installation was stopped.'),
          file=sys.stderr, flush=True)
    return 1

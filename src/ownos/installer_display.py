"""Give the authenticated installer private, temporary access to XWayland."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile


class DisplayAuthorizationError(RuntimeError):
    pass


@contextmanager
def installer_display_environment(environment=None):
    """Keep a generated cookie private and alive until the installer exits.

    Run as the existing desktop user. pkexec still performs administrator
    authorization and retains only DISPLAY/XAUTHORITY through its fixed policy.
    No X server access-control list is changed, and no cookie enters argv/logs.
    """
    environment = dict(os.environ if environment is None else environment)
    display = environment.get('DISPLAY', '')
    if not re.fullmatch(r':[0-9]+(?:\.[0-9]+)?', display):
        raise DisplayAuthorizationError('The installer needs a local Live desktop display.')
    runtime = Path(environment.get('XDG_RUNTIME_DIR', ''))
    try:
        metadata = runtime.lstat()
        if (not runtime.is_absolute() or runtime.resolve(strict=True) != runtime or
                not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or
                stat.S_IMODE(metadata.st_mode) != 0o700):
            raise DisplayAuthorizationError('The Live desktop session could not be verified. Restart the Live USB and try again.')
    except OSError:
        raise DisplayAuthorizationError('The Live desktop runtime directory is unavailable.') from None

    try:
        temporary = tempfile.TemporaryDirectory(prefix='husk-installer-', dir=runtime)
    except OSError:
        raise DisplayAuthorizationError('The installer could not prepare its private display connection.') from None
    with temporary as directory:
        authority = Path(directory) / 'Xauthority'
        try:
            # Authenticate as the desktop user while asking the server for a
            # separate credential. Its unused timeout does not interrupt an
            # active installer connection. The original authority is untouched.
            subprocess.run(['/usr/bin/xauth', '-f', str(authority), 'generate',
                            display, '.', 'trusted', 'timeout', '120'],
                           env=dict(environment, LANG='C.UTF-8', LC_ALL='C.UTF-8'),
                           capture_output=True, text=True, check=True, timeout=20)
            metadata = authority.lstat()
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or
                    metadata.st_nlink != 1 or metadata.st_size <= 0 or
                    stat.S_IMODE(metadata.st_mode) != 0o600):
                raise DisplayAuthorizationError('Secure access to the Live desktop could not be verified.')
        except (OSError, subprocess.SubprocessError):
            raise DisplayAuthorizationError('Secure access to the Live display could not be prepared. '
                                            'Close this window and try again from the Live desktop.') from None
        yield dict(environment, XAUTHORITY=str(authority))

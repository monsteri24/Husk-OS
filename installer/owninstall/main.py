"""Small Calamares adapter; the tested policy lives in ownos.provisioning."""
import subprocess
import sys
sys.path.insert(0, '/usr/lib/ownos')
import libcalamares
from ownos.provisioning import configure_cloned_target
from ownos.i18n import _


def pretty_name():
    return 'Configure the installed Husk OS system'


def run():
    try:
        configure_cloned_target(libcalamares.globalstorage.value('rootMountPoint'))
        return None
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        detail = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            detail += '\n' + (exc.stderr or exc.stdout or '')[-4000:]
        return _('Husk OS installation stopped'), detail

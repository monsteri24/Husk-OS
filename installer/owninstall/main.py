"""Small Calamares adapter; the tested policy lives in ownos.provisioning."""
import subprocess
import sys
sys.path.insert(0, '/usr/lib/ownos')
import libcalamares
from ownos.provisioning import configure_target


def pretty_name():
    return 'Husk OS: valitun työpöydän ja ajurien asennus'


def run():
    try:
        configure_target(libcalamares.globalstorage.value('rootMountPoint'),
                         libcalamares.globalstorage.value('packagechooser_desktop'),
                         libcalamares.globalstorage.value('packagechooser_graphics'))
        return None
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        detail = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            detail += '\n' + (exc.stderr or exc.stdout or '')[-4000:]
        return 'Husk OS-asennus keskeytyi', detail

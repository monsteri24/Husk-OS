import sys
import subprocess
sys.path.insert(0,'/usr/lib/ownos')
import libcalamares
from ownos.provisioning import flush_target


def pretty_name():
    return 'Flush installed filesystems and check writeback errors'


def run():
    try:
        flush_target(libcalamares.globalstorage.value('rootMountPoint'))
        return None
    except (OSError,ValueError,subprocess.SubprocessError):
        return 'Disk synchronization failed', 'The installed filesystems could not be synchronized. Completion and automatic restart were stopped.'

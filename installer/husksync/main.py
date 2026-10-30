"""Only mark completion after target unmount and checked disk synchronization."""
import subprocess


def pretty_name():
    return 'Synchronize installed system disks'


def run():
    try:
        subprocess.run(['/usr/bin/sync'], check=True, timeout=120)
        return None
    except (OSError, subprocess.SubprocessError):
        return 'Disk synchronization failed', 'Installation completion and automatic restart were stopped.'

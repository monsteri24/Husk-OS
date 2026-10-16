"""Allowlisted, complete pacman transactions for the polkit helper."""
from ownos.catalog import app_by_id
from ownos.installer import DESKTOP_PACKAGES, NVIDIA_PACKAGES


def admin_command(action, choice=None):
    if action == 'update' and choice is None:
        return ['/usr/bin/pacman', '-Syu']
    if action == 'install':
        app = app_by_id(choice)
        if app.package:
            return ['/usr/bin/pacman', '-Syu', '--needed', app.package]
    if action == 'desktop' and choice in ('own', 'kde', 'gnome'):
        return ['/usr/bin/pacman', '-Syu', '--needed', *DESKTOP_PACKAGES[choice]]
    if action == 'driver' and choice == 'nvidia-open':
        return ['/usr/bin/pacman', '-Syu', '--needed', *NVIDIA_PACKAGES]
    raise ValueError('Operation is not permitted')

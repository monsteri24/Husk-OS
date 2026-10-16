"""Pure installer policy, shared by the Calamares job and unit tests."""
from dataclasses import dataclass
from pathlib import Path
from ownos.identity import OS_ID, LEGACY_OS_IDS

DESKTOP_PACKAGES = {
    'own': ('ownos-desktop', 'ownos-ui', 'ownos-branding', 'sddm'),
    'kde': ('plasma-desktop', 'plasma-workspace', 'systemsettings', 'dolphin', 'konsole', 'kscreen', 'ownos-ui', 'ownos-branding', 'sddm'),
    'gnome': ('gnome-shell', 'gnome-session', 'gnome-control-center', 'nautilus', 'gnome-console', 'gdm', 'ownos-ui', 'ownos-branding'),
    'minimal': (),
}
GAME_PACKAGES = ('steam', 'wine', 'winetricks', 'lutris', 'mangohud', 'lib32-mangohud',
                 'gamemode', 'lib32-gamemode', 'discord', 'firefox', 'flatpak', 'steam-devices')
MESA_PACKAGES = ('mesa', 'lib32-mesa', 'vulkan-radeon', 'lib32-vulkan-radeon',
                 'vulkan-intel', 'lib32-vulkan-intel', 'vulkan-icd-loader', 'lib32-vulkan-icd-loader')
NVIDIA_PACKAGES = ('linux-headers', 'nvidia-open-dkms', 'nvidia-utils', 'lib32-nvidia-utils')
LIVE_PACKAGES = ('ownos-live', 'calamares', 'archinstall')


@dataclass(frozen=True)
class InstallationPlan:
    desktop: str
    packages: tuple
    remove: tuple
    display_manager: str | None


def installation_plan(desktop, graphics):
    if desktop not in DESKTOP_PACKAGES or graphics not in ('mesa', 'nvidia-open'):
        raise ValueError('A supported desktop and graphics option must be selected')
    packages = ('ownos-core', 'ownos-keyring', 'linux', 'linux-firmware', 'networkmanager',
                'sudo', 'polkit', 'btrfs-progs', 'pipewire', 'pipewire-pulse', 'wireplumber')
    packages += MESA_PACKAGES + DESKTOP_PACKAGES[desktop]
    remove = list(LIVE_PACKAGES)
    if desktop == 'minimal':
        remove += ['ownos-desktop', 'ownos-ui', 'ownos-branding', 'sddm'] + list(GAME_PACKAGES)
    else:
        packages += GAME_PACKAGES
        if desktop != 'own':
            remove += ['ownos-desktop']
        if desktop == 'gnome':
            remove += ['sddm']
    if graphics == 'nvidia-open':
        packages += NVIDIA_PACKAGES
    manager = None if desktop == 'minimal' else ('gdm' if desktop == 'gnome' else 'sddm')
    return InstallationPlan(desktop, tuple(dict.fromkeys(packages)), tuple(remove), manager)


def validate_target(root):
    path = Path(root)
    if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
        raise ValueError('Installer root must be an absolute non-symlink path')
    if path.parent not in (Path('/tmp'), Path('/run')) or not path.name.startswith('calamares-root-'):
        raise ValueError('Refusing an unexpected installer mount point')
    if not path.is_mount():
        raise ValueError('Installer target is not a mounted filesystem')
    release = path / 'etc/os-release'
    if not release.resolve().is_relative_to(path) or not release.is_file():
        raise ValueError('Target release metadata escapes the installer root')
    values = dict(line.split('=', 1) for line in release.read_text(encoding='utf-8').splitlines()
                  if '=' in line and not line.lstrip().startswith('#'))
    if values.get('ID', '').strip('"') not in (OS_ID, *LEGACY_OS_IDS):
        raise ValueError('Target does not contain a Husk OS image')
    return path

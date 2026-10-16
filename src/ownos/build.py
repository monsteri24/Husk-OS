"""Archiso staging and read-only environment checks. Never partitions a disk."""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from ownos.installer import GAME_PACKAGES, MESA_PACKAGES
from ownos.identity import OS_ID, VERSION

TOOLS = ('mkarchiso', 'pacman', 'pacman-key', 'gpgv', 'mksquashfs', 'xorriso')
LIVE = ('base', 'linux', 'archlinux-keyring', 'labwc', 'wayland', 'gtk3', 'gtk-layer-shell',
        'python-gobject', 'xorg-xwayland', 'network-manager-applet', 'foot', 'libnotify',
        'vulkan-tools', 'mesa-utils', 'wayland-utils',
        'ownos-core', 'ownos-ui', 'ownos-desktop', 'ownos-branding', 'ownos-keyring',
        'ownos-live', 'sddm', 'xorg-server', 'xorg-xauth', 'grub',
        'efibootmgr', 'networkmanager', 'sudo', 'linux-firmware', 'btrfs-progs',
        'dosfstools', 'pipewire', 'pipewire-pulse', 'wireplumber', 'pciutils',
        'noto-fonts', 'adwaita-icon-theme', 'python-yaml', 'wpa_supplicant',
        'intel-ucode', 'amd-ucode', 'bluez', 'bluez-utils', 'blueman', 'upower',
        'power-profiles-daemon', 'pipewire-alsa', 'pavucontrol', 'alsa-utils', 'udisks2', 'gvfs')


def preflight(available=shutil.which, os_id=None):
    if os_id is None:
        os_id = next((line.partition('=')[2].strip('"') for line in
                      Path('/etc/os-release').read_text().splitlines() if line.startswith('ID=')), '')
    problems = []
    if os_id not in ('arch', 'ownos', OS_ID):
        problems.append('ISO construction needs an isolated Arch Linux x86_64 build VM (current ID: ' + os_id + ').')
    for tool in TOOLS:
        if not available(tool): problems.append('Missing build tool: ' + tool)
    return problems


def pacman_config(server):
    return '''[options]
Architecture = auto
CheckSpace
SigLevel = Required DatabaseOptional
LocalFileSigLevel = Required
ParallelDownloads = 5

[core]
Include = /etc/pacman.d/mirrorlist
[extra]
Include = /etc/pacman.d/mirrorlist
[multilib]
Include = /etc/pacman.d/mirrorlist
[ownos]
SigLevel = Required DatabaseRequired
Server = ''' + server + '\n'


def safe_path(base, relative):
    target = base / relative
    if not target.resolve().is_relative_to(base.resolve()):
        raise ValueError('Refusing a path that escapes the target: ' + str(relative))
    return target


def write(base, relative, contents):
    target = Path(base) / relative
    safe_path(Path(base), target.parent.relative_to(base))
    target.parent.mkdir(parents=True, exist_ok=True)
    # Replace inherited symlink files without writing through them.
    if target.is_symlink(): target.unlink()
    target.write_text(contents, encoding='utf-8')


def live_packages(first_boot=False):
    """The small boot edition retains the desktop and native graphics drivers."""
    if first_boot:
        return LIVE + tuple(package for package in MESA_PACKAGES if not package.startswith('lib32-'))
    return LIVE + GAME_PACKAGES + MESA_PACKAGES


def remove_overlay_file(root, relative):
    """Unlink an inherited file itself, never an absolute symlink's host target."""
    target = Path(root) / relative
    safe_path(Path(root), target.parent.relative_to(root))
    if target.is_symlink() or target.is_file(): target.unlink()


def overlay_link(root, relative, destination):
    target = Path(root) / relative
    safe_path(Path(root), target.parent.relative_to(root))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.is_file(): target.unlink()
    target.symlink_to(destination)


def repository_files(repo):
    if not (repo / 'ownos.db.tar.gz').is_file() or not (repo / 'ownos.db.tar.gz.sig').is_file():
        raise ValueError('Missing signed ownos repository database. Run build-packages.sh first.')
    packages = sorted(repo.glob('*.pkg.tar.zst'))
    if not packages or any(not Path(str(p) + '.sig').is_file() for p in packages):
        raise ValueError('Every repository package requires a detached signature.')
    for p in [repo / 'ownos.db.tar.gz', repo / 'ownos.db.tar.gz.sig', *packages,
              *[Path(str(p) + '.sig') for p in packages]]:
        if p.is_symlink() or not p.resolve().is_relative_to(repo):
            raise ValueError('Unexpected repository file path')
    return packages


def generate_profile(releng, repo, public_key, output, project, with_installer=False, first_boot=False):
    output = Path(output).absolute()
    if output.is_symlink() or output.exists() or output.resolve() != output:
        raise ValueError('Profile output must be a new non-symlink directory; existing work is never deleted.')
    if output == Path('/') or any(output.is_relative_to(Path(p)) for p in ('/etc', '/usr', '/dev', '/proc', '/sys', '/boot')):
        raise ValueError('Unsafe build output directory')
    releng, repo, public_key, project = [Path(p).resolve() for p in (releng, repo, public_key, project)]
    if not (releng / 'profiledef.sh').is_file() or not (releng / 'packages.x86_64').is_file():
        raise ValueError('The installed Archiso releng profile is required.')
    if output.is_relative_to(releng) or output.is_relative_to(repo):
        raise ValueError('Output may not be nested in build inputs')
    repository_files(repo)
    if not public_key.is_file(): raise ValueError('Public signing key is missing')
    shutil.copytree(releng, output, symlinks=True)
    profile = safe_path(output, 'profiledef.sh')
    with profile.open('a') as stream:
        stream.write('''
# Husk OS additions; upstream bootmodes and install_dir are retained.
iso_name="huskos"
iso_publisher="Husk OS experimental project"
iso_application="Husk OS live with Husk Desktop (Experimental)"
iso_label="HUSK_$(date +%Y%m%d)"
file_permissions+=( ["/etc/shadow"]="0:0:400" )
''')
        if first_boot:
            stream.write('''
# Fast, bounded compression for the first boot verification edition.
airootfs_image_type="squashfs"
airootfs_image_tool_options=(-comp zstd -Xcompression-level 3 -b 1M -processors 2)
''')
    write(output, 'husk-profile.json', json.dumps({'edition': 'first-boot' if first_boot else 'gaming',
                                                  'version': VERSION}, indent=2) + '\n')
    packages = safe_path(output, 'packages.x86_64').read_text().splitlines()
    packages += list(live_packages(first_boot))
    if with_installer: packages.append('calamares')
    else: packages = [p for p in packages if p.strip() not in ('calamares','archinstall')]
    write(output, 'packages.x86_64', '\n'.join(dict.fromkeys(p for p in packages if p.strip())) + '\n')
    root = safe_path(output, 'airootfs')
    safe_path(root, 'opt/ownos/repo')
    shutil.copytree(repo, root / 'opt/ownos/repo', symlinks=False)
    (root / 'opt/ownos').mkdir(exist_ok=True)
    remove_overlay_file(root, 'opt/ownos/repo-key.gpg')
    shutil.copyfile(public_key, root / 'opt/ownos/repo-key.gpg')
    write(output, 'pacman.conf', pacman_config(repo.as_uri()))
    write(root, 'etc/pacman.conf', pacman_config('file:///opt/ownos/repo'))
    write(root, 'etc/os-release', (project / 'branding/os-release').read_text())
    # Change only user-facing boot labels; retain kernel/initrd/options paths.
    for directory in ('efiboot', 'syslinux', 'grub'):
        for path in (output / directory).rglob('*'):
            if path.suffix not in ('.cfg','.conf') or not path.is_file(): continue
            safe_path(output, str(path.relative_to(output)))
            text = path.read_text()
            text = text.replace('Arch Linux install medium', 'Husk OS live')
            text = text.replace('Arch Linux installation medium', 'Husk OS live')
            text = text.replace('Arch Linux archiso', 'Husk OS live')
            path.write_text(text)
    # The live ISO logs in as an unprivileged disposable live user.
    for name in ('getty@tty1.service.d/autologin.conf', 'sshd.service',
                 'multi-user.target.wants/sshd.service', 'multi-user.target.wants/iwd.service',
                 'multi-user.target.wants/systemd-networkd.service',
                 'multi-user.target.wants/systemd-networkd.socket',
                 'sockets.target.wants/systemd-networkd.socket',
                 'sysinit.target.wants/systemd-time-wait-sync.service',
                 'multi-user.target.wants/systemd-time-wait-sync.service',
                 'time-sync.target.wants/systemd-time-wait-sync.service',
                 'multi-user.target.wants/pacman-init.service'):
        remove_overlay_file(root, 'etc/systemd/system/' + name)
    write(root, 'etc/sddm.conf.d/ownos-live.conf', '''[General]
DisplayServer=x11

[Wayland]
SessionDir=/usr/share/wayland-sessions
SessionLogFile=.local/share/sddm/wayland-session.log

[Autologin]
User=live
Session=ownos-wayland.desktop
Relogin=false
''')
    write(root, 'etc/systemd/system/ownos-live-setup.service', (project / 'iso/ownos-live-setup.service').read_text())
    write(root, 'etc/systemd/system/ownos-live-keyring.service', (project / 'iso/ownos-live-keyring.service').read_text())
    write(root, 'etc/systemd/system/etc-pacman.d-gnupg.mount', (project / 'iso/etc-pacman.d-gnupg.mount').read_text())
    write(root, 'etc/systemd/system/getty@tty2.service.d/husk-live.conf', (project / 'iso/getty-live.conf').read_text())
    write(root, 'etc/systemd/system/sddm.service.d/husk-live.conf',
          '[Unit]\nRequires=ownos-live-setup.service\nAfter=ownos-live-setup.service\n')
    write(root, 'etc/NetworkManager/conf.d/husk-wifi.conf', '[device]\nwifi.backend=wpa_supplicant\n')
    for name, destination in [('display-manager.service', '/usr/lib/systemd/system/sddm.service'),
                              ('default.target', '/usr/lib/systemd/system/graphical.target')]:
        overlay_link(root, 'etc/systemd/system/' + name, destination)
    for name in ('NetworkManager.service', 'ownos-live-setup.service', 'ownos-live-keyring.service', 'bluetooth.service', 'power-profiles-daemon.service'):
        overlay_link(root, 'etc/systemd/system/multi-user.target.wants/' + name,
                     '/etc/systemd/system/' + name if name.startswith('ownos') else '/usr/lib/systemd/system/' + name)
    overlay_link(root, 'etc/systemd/system/getty.target.wants/getty@tty2.service', '/usr/lib/systemd/system/getty@.service')
    return output


def validate_profile(profile):
    """Check staged sources/configuration; this is not an ISO boot test."""
    profile = Path(profile).resolve()
    problems = []
    packages_path = profile / 'packages.x86_64'
    if not packages_path.is_file(): return ['Missing profile package list.']
    packages = {line.split('#',1)[0].strip() for line in packages_path.read_text().splitlines()}
    first_boot = False
    try:
        metadata = json.loads(safe_path(profile, 'husk-profile.json').read_text())
        first_boot = metadata.get('edition') == 'first-boot'
        if metadata.get('edition') not in ('first-boot', 'gaming') or metadata.get('version') != VERSION:
            problems.append('Invalid Husk OS edition/version metadata.')
    except (OSError, ValueError, AttributeError):
        problems.append('Missing or invalid Husk OS edition/version metadata.')
    for package in live_packages(first_boot):
        if package not in packages: problems.append('Missing live package: ' + package)
    if first_boot:
        for package in sorted(packages.intersection(GAME_PACKAGES) | {p for p in packages if p.startswith('lib32-')}):
            problems.append('Unexpected first-boot gaming/multilib addition: ' + package)
    required = {
        'airootfs/etc/os-release':['NAME="Husk OS"','ID=huskos'],
        'airootfs/etc/sddm.conf.d/ownos-live.conf':['DisplayServer=x11','SessionDir=/usr/share/wayland-sessions',
                                               'SessionLogFile=.local/share/sddm/wayland-session.log',
                                               'User=live','Session=ownos-wayland.desktop','Relogin=false'],
        'airootfs/etc/systemd/system/ownos-live-setup.service':['ConditionPathExists=/run/archiso','ExecStart=/usr/lib/ownos/live-setup'],
        'airootfs/etc/systemd/system/ownos-live-keyring.service':['Requires=etc-pacman.d-gnupg.mount','After=etc-pacman.d-gnupg.mount'],
        'airootfs/etc/systemd/system/etc-pacman.d-gnupg.mount':['ConditionPathExists=/run/archiso','Where=/etc/pacman.d/gnupg','Type=tmpfs','mode=0755','noswap'],
        'airootfs/etc/systemd/system/getty@tty2.service.d/husk-live.conf':['Requires=ownos-live-setup.service','After=ownos-live-setup.service','--autologin live'],
        'airootfs/etc/systemd/system/sddm.service.d/husk-live.conf':['Requires=ownos-live-setup.service','After=ownos-live-setup.service'],
        'airootfs/etc/pacman.conf':['SigLevel = Required DatabaseRequired','[multilib]'],
    }
    for relative, values in required.items():
        path = safe_path(profile, relative)
        if not path.is_file(): problems.append('Missing live configuration/setup: ' + relative); continue
        text = path.read_text()
        for value in values:
            if value not in text: problems.append('Missing ' + value + ' in ' + relative)
    manager = profile / 'airootfs/etc/systemd/system/display-manager.service'
    if not manager.is_symlink() or manager.readlink() != Path('/usr/lib/systemd/system/sddm.service'):
        problems.append('Live display manager must be SDDM.')
    for name in ('NetworkManager.service','ownos-live-setup.service','ownos-live-keyring.service',
                 'bluetooth.service','power-profiles-daemon.service'):
        link = profile / 'airootfs/etc/systemd/system/multi-user.target.wants' / name
        expected = Path(('/etc/systemd/system/' if name.startswith('ownos') else '/usr/lib/systemd/system/') + name)
        if not link.is_symlink() or link.readlink() != expected:
            problems.append('Missing or incorrect live service: ' + name)
    definition = profile / 'profiledef.sh'
    if not definition.is_file() or 'iso_name="huskos"' not in definition.read_text():
        problems.append('Missing Husk OS profile metadata.')
    root_login = profile / 'airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf'
    if root_login.exists() or root_login.is_symlink(): problems.append('Unexpected root console autologin.')
    tty = profile / 'airootfs/etc/systemd/system/getty.target.wants/getty@tty2.service'
    if not tty.is_symlink() or tty.readlink() != Path('/usr/lib/systemd/system/getty@.service'):
        problems.append('Missing live console on tty2.')
    for relative in ('sysinit.target.wants/systemd-time-wait-sync.service',
                     'multi-user.target.wants/systemd-time-wait-sync.service',
                     'time-sync.target.wants/systemd-time-wait-sync.service',
                     'multi-user.target.wants/pacman-init.service'):
        path = profile / 'airootfs/etc/systemd/system' / relative
        if path.is_symlink() or path.exists(): problems.append('Unexpected live boot initializer/wait: ' + relative)
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--with-installer', action='store_true')
    parser.add_argument('--first-boot', action='store_true', help='Keep desktop and 64-bit Mesa; omit gaming and lib32 additions.')
    parser.add_argument('--releng', default='/usr/share/archiso/configs/releng')
    parser.add_argument('--repo', type=Path, default=Path('.build/repo'))
    parser.add_argument('--key', type=Path, default=Path('.build/keys/ownos.gpg'))
    parser.add_argument('--output', type=Path, default=Path('.build/profile'))
    args = parser.parse_args()
    if args.check:
        problems = preflight()
        if not Path(args.releng).is_dir(): problems.append('Missing installed releng profile: ' + args.releng)
        if not args.repo.is_dir(): problems.append('Missing signed package repository: ' + str(args.repo))
        if not args.key.is_file(): problems.append('Missing public repository key: ' + str(args.key))
        print('\n'.join(problems) if problems else 'Build prerequisites found. This does not prove ISO bootability.')
        return 1 if problems else 0
    print(generate_profile(args.releng, args.repo, args.key, args.output, Path(__file__).resolve().parents[2],
                           with_installer=args.with_installer, first_boot=args.first_boot))
    return 0


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print('Husk OS build:', exc, file=sys.stderr); raise SystemExit(1)

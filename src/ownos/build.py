"""Archiso staging and read-only environment checks. Never partitions a disk."""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from ownos.installer import GAME_PACKAGES, MESA_PACKAGES, OPTIONAL_APPLICATION_PACKAGES
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
        'power-profiles-daemon', 'pipewire-alsa', 'pavucontrol', 'alsa-utils', 'udisks2', 'gvfs',
        # Required by the inherited releng boot modes/initramfs and offline
        # repair workflows, independently of the optional installer choice.
        'arch-install-scripts', 'mkinitcpio', 'mkinitcpio-archiso', 'mkinitcpio-nfs-utils',
        'squashfs-tools', 'erofs-utils', 'syslinux', 'efitools', 'edk2-shell',
        'memtest86+', 'memtest86+-efi', 'cryptsetup', 'e2fsprogs', 'lvm2', 'mdadm',
        'parted', 'gptfdisk', 'mtools', 'less', 'nano', 'man-db', 'man-pages', 'rsync',
        'smartmontools', 'nvme-cli', 'usbutils', 'ethtool', 'sof-firmware', 'wireless-regdb')

# Reviewed Archiso releng hardware, accessibility, networking and recovery
# tools. Preserve them when present in the installed upstream profile. This
# list follows Arch's official read-only mirror, reviewed 2026-10-16:
# https://github.com/archlinux/archiso/blob/master/configs/releng/packages.x86_64
# Unknown additions require review instead of silently shipping an app or
# silently discarding a new boot dependency. Older package names stay accepted
# so the installed releng version remains the source of those utility choices.
RELENG_RECOVERY_PACKAGES = frozenset('''
alsa-utils amd-ucode arch-install-scripts b43-fwcutter base bcachefs-tools bind bolt
brltty broadcom-wl btrfs-progs clonezilla cloud-init cryptsetup darkhttpd ddrescue
dhcpcd diffutils dmidecode dmraid dnsmasq dosfstools e2fsprogs edk2-shell efibootmgr
efitools erofs-utils espeakup ethtool exfatprogs f2fs-tools fatresize foot-terminfo
fsarchiver ghostty-terminfo gnu-netcat gpart gpm gptfdisk grml-zsh-config grub hdparm
hyperv intel-ucode iw iwd jfsutils kitty-terminfo kmscon-terminfo ldns less lftp
libfido2 libusb-compat linux linux-atm linux-firmware linux-firmware-marvell
livecd-sounds lsscsi lvm2 man-db man-pages mc mdadm memtest86+ memtest86+-efi
mkinitcpio mkinitcpio-archiso mkinitcpio-nfs-utils mmc-utils modemmanager mtools mtr
nano nbd ndisc6 nfs-utils nilfs-utils nmap ntfs-3g ntfsprogs nvme-cli open-iscsi
open-vm-tools openconnect openpgp-card-tools openssh openvpn partclone parted
partimage pcsclite ppp pptpclient pv qemu-guest-agent refind reflector reiserfsprogs
rp-pppoe rsync rxvt-unicode-terminfo screen sdparm sequoia-sq sg3_utils
smartmontools sof-firmware squashfs-tools sudo syslinux systemd-resolvconf tcpdump
terminus-font testdisk tmux tpm2-tools tpm2-tss udftools usb_modeswitch usbmuxd
usbutils vim virtiofsd virtualbox-guest-utils-nox vpnc wireless-regdb wireless_tools
wpa_supplicant wvdial xdg-utils xfsprogs xl2tpd zsh
'''.split())


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
    """Both editions keep the desktop and drivers without optional user apps."""
    if first_boot:
        return LIVE + tuple(package for package in MESA_PACKAGES if not package.startswith('lib32-'))
    return LIVE + MESA_PACKAGES


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
    packages = []
    approved = RELENG_RECOVERY_PACKAGES | set(live_packages(first_boot)) | {'calamares', 'archinstall'}
    for line in (releng / 'packages.x86_64').read_text().splitlines():
        package = line.partition('#')[0].strip()
        if not package or package in OPTIONAL_APPLICATION_PACKAGES or package in GAME_PACKAGES:
            continue
        if package not in approved:
            raise ValueError('Unreviewed upstream package: ' + package + '. Review its system role before including it.')
        packages.append(package)
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
            compression_level = 19 if with_installer else 3
            stream.write(f'''
# Keep installer images distributable without removing drivers or desktop tools.
# The smaller first-boot-only verification image retains its fast compression.
airootfs_image_type="squashfs"
airootfs_image_tool_options=(-comp zstd -Xcompression-level {compression_level} -b 1M -processors 2)
''')
    write(output, 'husk-profile.json', json.dumps({'edition': 'first-boot' if first_boot else 'desktop',
                                                  'version': VERSION,
                                                  'live_login': 'tty1' if first_boot else 'sddm'}, indent=2) + '\n')
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
            if with_installer:
                # Archiso's 256 MiB default cannot hold ordinary application
                # transactions. A tmpfs limit scales with RAM without allocating
                # it up front; retain half for the running Live desktop.
                lines = []
                for line in text.splitlines(keepends=True):
                    if (re.match(r'\s*(options|linux|linuxefi|append)\s+', line, re.IGNORECASE)
                            and re.search(r'\barchisobasedir=\S+', line)):
                        ending = '\n' if line.endswith('\n') else ''
                        line = re.sub(r'(?<!\S)cow_spacesize=\S+\s*', '', line).rstrip() + ' cow_spacesize=50%' + ending
                    lines.append(line)
                text = ''.join(lines)
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
    # NetworkManager owns DHCP and resolver state. The inherited releng
    # resolved symlink cannot survive when networkd/resolved are disabled.
    write(root, 'etc/NetworkManager/conf.d/husk-network.conf',
          '[main]\ndns=default\nrc-manager=symlink\ndhcp=internal\n')
    overlay_link(root, 'etc/resolv.conf', '/run/NetworkManager/resolv.conf')
    for name, destination in [('display-manager.service', '/usr/lib/systemd/system/sddm.service'),
                              ('default.target', '/usr/lib/systemd/system/graphical.target')]:
        overlay_link(root, 'etc/systemd/system/' + name, destination)
    if first_boot:
        # Use the normal login/PAM path, retaining logind and XDG_RUNTIME_DIR.
        remove_overlay_file(root, 'etc/systemd/system/display-manager.service')
        overlay_link(root, 'etc/systemd/system/default.target', '/usr/lib/systemd/system/multi-user.target')
        write(root, 'etc/systemd/system/getty@tty1.service.d/husk-live.conf',
              (project / 'iso/getty-live.conf').read_text())
        overlay_link(root, 'etc/systemd/system/getty.target.wants/getty@tty1.service',
                     '/usr/lib/systemd/system/getty@.service')
        write(root, 'etc/profile.d/husk-live-session.sh', (project / 'iso/husk-live-session.sh').read_text())
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
        if metadata.get('edition') not in ('first-boot', 'desktop') or metadata.get('version') != VERSION:
            problems.append('Invalid Husk OS edition/version metadata.')
    except (OSError, ValueError, AttributeError):
        problems.append('Missing or invalid Husk OS edition/version metadata.')
    for package in live_packages(first_boot):
        if package not in packages: problems.append('Missing live package: ' + package)
    approved = RELENG_RECOVERY_PACKAGES | set(live_packages(first_boot)) | {'', 'calamares', 'archinstall'}
    for package in sorted(packages - approved):
        problems.append('Unexpected optional or unreviewed live package: ' + package)
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
    if first_boot:
        if manager.is_symlink() or manager.exists():
            problems.append('First-boot login must not start SDDM.')
        hook = profile / 'airootfs/etc/profile.d/husk-live-session.sh'
        if not hook.is_file() or 'exec /usr/bin/husk-session' not in hook.read_text():
            problems.append('Missing first-boot husk-live-session hook.')
        tty1 = profile / 'airootfs/etc/systemd/system/getty@tty1.service.d/husk-live.conf'
        if not tty1.is_file() or '--autologin live' not in tty1.read_text():
            problems.append('Missing first-boot tty1 live login.')
        target = profile / 'airootfs/etc/systemd/system/default.target'
        if not target.is_symlink() or target.readlink() != Path('/usr/lib/systemd/system/multi-user.target'):
            problems.append('First-boot default target must start console login.')
    elif not manager.is_symlink() or manager.readlink() != Path('/usr/lib/systemd/system/sddm.service'):
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

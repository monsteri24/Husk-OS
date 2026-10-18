"""Read-only V3 ISO payload checks, additional to the generic rootfs check.

These checks inspect files and configuration in an extracted image. They do
not execute guest code or establish installation, boot, or hardware support.
"""
import configparser
import hashlib
from pathlib import Path, PurePosixPath
import re
import shlex
import xml.etree.ElementTree as ET
import yaml
from ownos.rootfs import guest_path


INSTALLER_ICON_SHA256 = '91eea8060bb48286290a7762dc4ec492d849b10118d9d1a7e053c170fb9e9801'
V3_VERSION = 'v3-phase2'
SHOW_MODULES = ('welcome', 'keyboard', 'locale', 'partition', 'users', 'summary')
EXEC_MODULES = ('partition', 'mount', 'unpackfs', 'machineid', 'fstab', 'locale',
                'keyboard', 'localecfg', 'users', 'owninstall', 'initcpio',
                'bootloader', 'huskflush', 'umount', 'husksync')


def _pacman_fields(text):
    fields = {}
    active = None
    for line in text.splitlines():
        if re.fullmatch(r'%[A-Z0-9_]+%', line):
            if line in fields:
                raise ValueError('Duplicate package database field: ' + line)
            active = line
            fields[active] = []
        elif not line:
            active = None
        elif active is not None:
            fields[active].append(line)
    return fields


class _Payload:
    def __init__(self, root, problems):
        self.root, self.problems = root, problems

    def required(self, relative, executable=False):
        try:
            path = guest_path(self.root, relative)
            if not path.is_file() or not path.stat().st_size:
                self.problems.append('Missing or empty V3 rootfs payload: ' + relative)
                return None
            if executable and not path.stat().st_mode & 0o111:
                self.problems.append('V3 rootfs payload is not executable: ' + relative)
                return None
            return path
        except (OSError, ValueError) as exc:
            self.problems.append('Invalid V3 rootfs payload ' + relative + ': ' + str(exc))
            return None

    def text(self, relative):
        path = self.required(relative)
        if path is None:
            return ''
        try:
            return path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as exc:
            self.problems.append('Cannot read V3 configuration ' + relative + ': ' + str(exc))
            return ''

    def mapping(self, relative):
        text = self.text(relative)
        if not text:
            return {}
        try:
            value = yaml.safe_load(text)
            if not isinstance(value, dict):
                raise ValueError('Expected a YAML mapping')
            return value
        except (ValueError, yaml.YAMLError) as exc:
            self.problems.append('Invalid V3 configuration ' + relative + ': ' + str(exc))
            return {}


def _check_installer(reader):
    problems = reader.problems
    settings = reader.mapping('etc/calamares/settings.conf')
    expected = [{'show': list(SHOW_MODULES)}, {'exec': list(EXEC_MODULES)}, {'show': ['finishedq']}]
    if settings.get('sequence') != expected:
        problems.append('Invalid V3 installer job sequence: require the reviewed offline copy, bootloader, flush, unmount and synchronization order before finishedq.')
    for key, expected_value in (('prompt-install', True), ('dont-chroot', False),
                                ('disable-cancel-during-exec', True),
                                ('hide-back-and-next-during-exec', True)):
        if settings.get(key) is not expected_value:
            problems.append('Invalid V3 installer setting: ' + key)
    if settings.get('modules-search') != ['local'] or settings.get('branding') != 'ownos':
        problems.append('Invalid V3 installer module search path or branding selection.')

    for name in sorted(set(SHOW_MODULES + EXEC_MODULES + ('finishedq',))):
        base = 'usr/lib/calamares/modules/' + name + '/'
        metadata = reader.mapping(base + 'module.desc')
        expected_type = 'viewmodule' if name in SHOW_MODULES + ('finishedq',) else 'job'
        if metadata.get('name') != name or metadata.get('type') != expected_type:
            problems.append('Invalid V3 installer module identity/type: ' + base + 'module.desc')
        interface = metadata.get('interface')
        field = 'load' if interface == 'qtplugin' else 'script' if interface == 'python' else None
        filename = metadata.get(field) if field else None
        if not isinstance(filename, str) or PurePosixPath(filename).name != filename or filename in ('', '.', '..'):
            problems.append('Invalid V3 installer module entry point: ' + base + 'module.desc')
        else:
            reader.required(base + filename)
        if interface == 'python' and expected_type != 'job':
            problems.append('V3 installer view requires its Qt plugin: ' + name)
        # Every configured module has a reviewed local config, including empty
        # maps for jobs that need no options. Do not accept a fallback default.
        reader.mapping('etc/calamares/modules/' + name + '.conf')

    partition = reader.mapping('etc/calamares/modules/partition.conf')
    if (partition.get('initialPartitioningChoice') != 'none'
            or partition.get('allowManualPartitioning') is not False
            or partition.get('enableLuksAutomatedPartitioning') is not False
            or partition.get('lvm', {}).get('enable') is not False):
        problems.append('Invalid V3 erase-only installation drive configuration.')
    unpack = reader.mapping('etc/calamares/modules/unpackfs.conf').get('unpack')
    if (not isinstance(unpack, list) or len(unpack) != 1 or not isinstance(unpack[0], dict)
            or unpack[0].get('source') != '/run/archiso/bootmnt/arch/x86_64/airootfs.sfs'
            or unpack[0].get('sourcefs') != 'squashfs' or unpack[0].get('destination') != ''):
        problems.append('Invalid V3 offline Live filesystem copy source.')
    bootloader = reader.mapping('etc/calamares/modules/bootloader.conf')
    if bootloader.get('efiBootLoader') != 'grub' or bootloader.get('installEFIFallback') is not True:
        problems.append('Invalid V3 UEFI GRUB bootloader configuration.')
    initcpio = reader.mapping('etc/calamares/modules/initcpio.conf')
    if initcpio.get('kernel') != 'all' or initcpio.get('be_unsafe') is not False:
        problems.append('Invalid V3 initramfs configuration.')
    finish = reader.mapping('etc/calamares/modules/finishedq.conf')
    if (finish.get('restartNowMode') != 'user-unchecked'
            or finish.get('restartNowCommand') != '/usr/bin/sync && /usr/bin/systemctl reboot'):
        problems.append('Invalid V3 installer restart configuration.')
    welcome = reader.mapping('etc/calamares/modules/welcome.conf')
    requirements = welcome.get('requirements', {})
    if not isinstance(requirements, dict) or 'internet' in requirements.get('required', []):
        problems.append('V3 installation must remain available offline; Internet cannot be a required welcome check.')
    locale = reader.mapping('etc/calamares/modules/locale.conf')
    if locale.get('adjustLiveTimezone') is not False or locale.get('geoip', {}).get('style') != 'none':
        problems.append('Invalid V3 explicit timezone/disabled GeoIP configuration.')
    branding = reader.mapping('etc/calamares/branding/ownos/branding.desc')
    if branding.get('componentName') != 'ownos' or branding.get('strings', {}).get('productName') != 'Husk OS' or branding.get('strings', {}).get('version') != 'V3 Phase 2':
        problems.append('Invalid V3 installer product/version branding.')


def _check_policy_and_launcher(reader):
    problems = reader.problems
    try:
        policy = ET.fromstring(reader.text('usr/share/polkit-1/actions/org.ownos.install.policy'))
        actions = policy.findall("action[@id='org.ownos.install']")
        if len(actions) != 1:
            raise ValueError('Expected one installer authorization action')
        action = actions[0]
        annotations = {item.get('key'): item.text for item in action.findall('annotate')}
        if (action.findtext('defaults/allow_any') != 'no'
                or action.findtext('defaults/allow_inactive') != 'no'
                or action.findtext('defaults/allow_active') != 'auth_admin'
                or annotations.get('org.freedesktop.policykit.exec.path') != '/usr/lib/ownos/husk-installer-root'
                or annotations.get('org.freedesktop.policykit.exec.allow_gui') != 'true'):
            raise ValueError('Installer must authorize the restricted wrapper with an administrator password')
    except (ValueError, ET.ParseError) as exc:
        problems.append('Invalid V3 installer polkit authorization: ' + str(exc))
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(reader.text('usr/share/applications/org.ownos.Install.desktop'))
        entry = parser['Desktop Entry']
        expected = {'Type': 'Application', 'Name': 'Install Husk OS', 'Exec': '/usr/bin/husk-install',
                    'TryExec': '/usr/bin/husk-install', 'Icon': 'husk-install', 'Terminal': 'false'}
        if any(entry.get(key) != value for key, value in expected.items()):
            raise ValueError('Expected the native graphical Husk installer launcher and supplied icon')
    except (ValueError, KeyError, configparser.Error) as exc:
        problems.append('Invalid V3 installer desktop launcher: ' + str(exc))
    relative = 'usr/share/icons/hicolor/128x128/apps/husk-install.png'
    path = reader.required(relative)
    if path is not None and hashlib.sha256(path.read_bytes()).hexdigest() != INSTALLER_ICON_SHA256:
        problems.append('Supplied installer icon checksum mismatch: ' + relative)


def _check_packages(reader):
    installed, owners = {}, {}
    try:
        database = guest_path(reader.root, 'var/lib/pacman/local')
        for entry in database.iterdir():
            relative = 'var/lib/pacman/local/' + entry.name
            if not guest_path(reader.root, relative).is_dir():
                continue
            fields = _pacman_fields(reader.text(relative + '/desc'))
            names, versions = fields.get('%NAME%', []), fields.get('%VERSION%', [])
            if len(names) != 1 or len(versions) != 1 or not re.fullmatch(r'[A-Za-z0-9@._+-]+', names[0]):
                raise ValueError('Invalid package identity/version in ' + relative)
            name = names[0]
            if name in installed:
                raise ValueError('Duplicate installed package identity: ' + name)
            installed[name] = versions[0]
            files = guest_path(reader.root, relative + '/files')
            if files.is_file():
                for filename in _pacman_fields(files.read_text(encoding='utf-8')).get('%FILES%', []):
                    owners.setdefault(filename.lstrip('/'), set()).add(name)
    except (OSError, ValueError, UnicodeError) as exc:
        reader.problems.append('Invalid V3 installed package inventory: ' + str(exc))
    required = {'ownos-core', 'ownos-ui', 'ownos-desktop', 'ownos-live', 'calamares',
                'networkmanager', 'wpa_supplicant', 'bluez', 'bluez-utils', 'blueman', 'linux-firmware'}
    for name in sorted(required - installed.keys()):
        reader.problems.append('Missing V3 installed package: ' + name)
    if 'calamares' in installed and not installed['calamares'].startswith('3.3.14-'):
        reader.problems.append('Unexpected Calamares package version; V3 requires the reviewed 3.3.14 backend.')
    launcher = 'usr/share/applications/org.ownos.Install.desktop'
    if owners.get(launcher) != {'ownos-live'}:
        reader.problems.append('Live-only launcher must be owned exclusively by ownos-live: ' + launcher)


def _check_network(reader):
    problems = reader.problems
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        directory = guest_path(reader.root, 'etc/NetworkManager/conf.d')
        for entry in sorted(directory.iterdir()):
            if entry.name.endswith('.conf'):
                parser.read_string(reader.text('etc/NetworkManager/conf.d/' + entry.name))
        expected = (('main', 'dns', 'default'), ('main', 'rc-manager', 'symlink'),
                    ('main', 'dhcp', 'internal'), ('device', 'wifi.backend', 'wpa_supplicant'))
        if any(parser.get(section, key, fallback=None) != value for section, key, value in expected):
            problems.append('Invalid V3 NetworkManager DHCP, resolver or Wi-Fi backend configuration.')
    except (OSError, ValueError, configparser.Error) as exc:
        problems.append('Invalid V3 NetworkManager configuration: ' + str(exc))
    try:
        resolver = guest_path(reader.root, 'etc') / 'resolv.conf'
        if not resolver.is_symlink() or guest_path(reader.root, 'etc/resolv.conf') != reader.root / 'run/NetworkManager/resolv.conf':
            raise ValueError('Expected the NetworkManager runtime resolver symlink')
    except (OSError, ValueError) as exc:
        problems.append('Invalid V3 etc/resolv.conf: ' + str(exc))
    for name in ('NetworkManager.service', 'bluetooth.service'):
        enabled = 'etc/systemd/system/multi-user.target.wants/' + name
        unit = 'usr/lib/systemd/system/' + name
        reader.required(unit)
        try:
            link = guest_path(reader.root, str(PurePosixPath(enabled).parent)) / name
            if not link.is_symlink() or guest_path(reader.root, enabled) != guest_path(reader.root, unit):
                raise ValueError('Expected an enabled service link to the installed unit')
        except (OSError, ValueError) as exc:
            problems.append('Invalid V3 enabled service ' + enabled + ': ' + str(exc))


def _assignments(text):
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator:
            raise ValueError('Expected a KEY=VALUE assignment')
        words = shlex.split(value, comments=True)
        if len(words) != 1:
            raise ValueError('Expected one quoted or unquoted assignment value')
        values[key.strip()] = words[0]
    return values


def validate_v3_rootfs(root, boot=None):
    """Return V3 payload/configuration problems; call after validate_rootfs()."""
    root = Path(root).resolve()
    if root == Path('/') or not root.is_dir():
        return ['Expected an extracted V3 ISO rootfs directory.']
    problems = []
    reader = _Payload(root, problems)
    for name in ('calamares', 'husk-install', 'pkexec', 'lsblk', 'findmnt', 'arch-chroot',
                 'mkinitcpio', 'grub-install', 'grub-mkconfig', 'efibootmgr', 'rsync',
                 'sync', 'pacman', 'pacman-key', 'passwd', 'systemctl', 'wpa_supplicant',
                 'nm-connection-editor', 'blueman-manager', 'bluetoothctl'):
        reader.required('usr/bin/' + name, executable=True)
    for relative in ('usr/lib/ownos/husk-installer-root', 'usr/lib/ownos/husk-install-guard',
                     'usr/lib/bluetooth/bluetoothd'):
        reader.required(relative, executable=True)
    for name in ('installer_safety', 'provisioning', 'live_password', 'network', 'bluetooth'):
        reader.required('usr/lib/ownos/ownos/' + name + '.py')
    for name in ('installer', 'network', 'bluetooth'):
        reader.required('usr/lib/ownos/ownos/ui/' + name + '.py')
    for relative in ('usr/lib/libcalamares.so', 'usr/lib/libcalamaresui.so', 'usr/lib/libnm.so.0',
                     'usr/lib/qt6/plugins/platforms/libqxcb.so',
                     'usr/lib/girepository-1.0/NM-1.0.typelib', 'etc/calamares/husk.qss',
                     'etc/polkit-1/rules.d/49-ownos-live.rules'):
        reader.required(relative)
    try:
        release = _assignments(reader.text('etc/os-release'))
        if release.get('NAME') != 'Husk OS' or release.get('ID') != 'huskos' or release.get('VERSION_ID') != V3_VERSION or release.get('BUILD_ID') != V3_VERSION:
            problems.append('Invalid Husk OS V3 product/version metadata in etc/os-release.')
        locale = _assignments(reader.text('etc/locale.conf'))
        if locale.get('LANG') != 'en_US.UTF-8' or any(value not in ('en_US.UTF-8', 'en_US:en', 'en') for key, value in locale.items() if key == 'LANGUAGE' or key.startswith('LC_')):
            problems.append('V3 Live locale must use the English en_US.UTF-8 interface.')
    except ValueError as exc:
        problems.append('Invalid V3 product/version or English locale metadata: ' + str(exc))
    _check_installer(reader)
    _check_policy_and_launcher(reader)
    _check_packages(reader)
    _check_network(reader)
    boot_root = Path(boot).resolve() if boot is not None else root / 'boot'
    if boot_root == Path('/') or not boot_root.is_dir():
        problems.append('Expected an extracted V3 boot directory; pass --boot after mkarchiso relocates /boot.')
    else:
        boot_reader = _Payload(boot_root, problems)
        for filename in ('vmlinuz-linux', 'initramfs-linux.img'):
            boot_reader.required(filename)
    return problems

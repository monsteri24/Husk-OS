"""Read-only checks of mkarchiso's installed live filesystem before delivery."""
from collections import deque
import hashlib
from pathlib import Path, PurePosixPath
from ownos.installer import OPTIONAL_APPLICATION_PACKAGES


def guest_path(root, relative):
    """Resolve links as the guest would, including absolute /usr/... links.

    Path.resolve() cannot be used on paths in a mounted guest: absolute links
    would resolve against the build host. Resolve every component beneath root.
    """
    root = Path(root).resolve()
    pending = deque(PurePosixPath(str(relative)).parts)
    parts = []
    links = 0
    while pending:
        part = pending.popleft()
        if part in ('', '.', '/'):
            continue
        if part == '..':
            if not parts:
                raise ValueError('Symlink escapes the guest root: ' + str(relative))
            parts.pop()
            continue
        candidate = root.joinpath(*parts, part)
        if candidate.is_symlink():
            links += 1
            if links > 40:
                raise ValueError('Symlink loop in guest path: ' + str(relative))
            destination = candidate.readlink()
            if destination.is_absolute():
                parts = []
            pending.extendleft(reversed(destination.parts))
        else:
            parts.append(part)
    return root.joinpath(*parts)


def _payload_files(root, relative):
    """Walk payloads without following directory links into the build host."""
    pending = [relative]
    visited = set()
    while pending:
        relative = pending.pop()
        try:
            path = guest_path(root, relative)
            if path.is_file():
                if path.stat().st_size:
                    yield path
            elif path.is_dir() and path not in visited:
                visited.add(path)
                pending.extend(str(child.relative_to(root)) for child in path.iterdir())
        except (OSError, ValueError):
            continue


def validate_rootfs(root, boot=None):
    """Return missing/broken payloads; package staging alone is not a boot test."""
    root = Path(root).resolve()
    if root == Path('/') or not root.is_dir():
        return ['Expected a populated mkarchiso airootfs directory.']
    problems = []

    def required(relative, executable=False):
        try:
            path = guest_path(root, relative)
            if not path.is_file() or not path.stat().st_size:
                problems.append('Missing or empty rootfs payload: ' + relative)
                return False
            if executable and not path.stat().st_mode & 0o111:
                problems.append('Rootfs payload is not executable: ' + relative)
                return False
            return True
        except (OSError, ValueError) as exc:
            problems.append('Invalid rootfs payload ' + relative + ': ' + str(exc))
            return False

    for relative in ('usr/bin/husk-session', 'usr/bin/husk-desktop', 'usr/bin/labwc',
                     'usr/bin/foot', 'usr/bin/own-toplevel', 'usr/lib/ownos/own.py',
                     'usr/lib/ownos/live-setup', 'usr/lib/ownos/live-keyring',
                     'etc/ownos/labwc/autostart'):
        required(relative, executable=True)
    for relative in ('usr/share/wayland-sessions/ownos-wayland.desktop',
                     'etc/ownos/labwc/rc.xml', 'etc/ownos/labwc/environment',
                     'usr/lib/ownos/ownos/ui/shell.py', 'usr/lib/ownos/ownos/ui/common.py',
                     'usr/lib/ownos/ownos/i18n.py', 'usr/lib/ownos/ownos/wallpaper.py',
                     'usr/lib/ownos/ownos/ui/wallpaper.py',
                     'usr/share/ownos/wallpapers/husk-desert.jpg', 'usr/lib/libgtk-3.so.0',
                     'usr/lib/libgtk-layer-shell.so.0',
                     'usr/lib/girepository-1.0/Gtk-3.0.typelib',
                     'usr/lib/girepository-1.0/GtkLayerShell-0.1.typelib'):
        required(relative)
    for name in ('husk-start', 'husk-settings', 'husk-files', 'husk-games', 'husk-app'):
        required('usr/share/icons/hicolor/scalable/apps/' + name + '.svg')

    # Test the installed bytes, not just the presence of a promising filename.
    wallpaper = 'usr/share/ownos/wallpapers/husk-desert.jpg'
    if required(wallpaper):
        digest = hashlib.sha256(guest_path(root, wallpaper).read_bytes()).hexdigest()
        if digest != 'e0f2ee190ff6c11a2102251d4fb13f3cad2690a8f3b9ef3bc5e963079aaeeaac':
            problems.append('Official wallpaper checksum mismatch: ' + wallpaper)

    # Inspect the installed package database, including transitive dependencies,
    # without executing any guest program. Directory names are not authoritative
    # package identities; pacman's desc records carry the %NAME% field.
    installed = set()
    try:
        database = guest_path(root, 'var/lib/pacman/local')
        for entry in database.iterdir():
            relative = str(entry.relative_to(root))
            if not guest_path(root, relative).is_dir():
                continue
            descriptor = guest_path(root, relative + '/desc')
            lines = descriptor.read_text(encoding='utf-8').splitlines()
            if lines.count('%NAME%') != 1:
                raise ValueError('Missing or duplicate %NAME% field in ' + relative + '/desc')
            index = lines.index('%NAME%') + 1
            name = lines[index].strip() if index < len(lines) else ''
            if not name or name.startswith('%') or any(character.isspace() for character in name):
                raise ValueError('Invalid %NAME% field in ' + relative + '/desc')
            installed.add(name)
        if not installed:
            raise ValueError('No installed package records found')
    except (OSError, ValueError, UnicodeError) as exc:
        problems.append('Missing or invalid installed package inventory: ' + str(exc))
    for package in sorted(installed.intersection(OPTIONAL_APPLICATION_PACKAGES)):
        problems.append('Unexpected optional application in installed rootfs: ' + package)

    try:
        libraries = guest_path(root, 'usr/lib')
        gi = any(guest_path(root, str(directory.relative_to(root) / 'site-packages/gi/__init__.py')).is_file()
                 for directory in libraries.iterdir() if directory.name.startswith('python3.'))
    except (OSError, ValueError):
        gi = False
    if not gi:
        problems.append('Missing Python GObject (gi) bindings in the rootfs.')

    try:
        modules = guest_path(root, 'usr/lib/modules')
        versions = [entry for entry in modules.iterdir()
                    if guest_path(root, str(entry.relative_to(root))).is_dir()]
    except (OSError, ValueError):
        versions = []
    kernel_paths = ['boot/vmlinuz-linux'] + [str(version.relative_to(root) / 'vmlinuz') for version in versions]
    kernel = any(next(_payload_files(root, relative), None) for relative in kernel_paths)
    if boot is not None:
        # mkarchiso deliberately empties airootfs/boot after copying these
        # artifacts to work/<arch>/boot and the ISO filesystem.
        boot = Path(boot).resolve()
        kernel = kernel or bool(next(_payload_files(boot, 'vmlinuz-linux'), None))
        if not next(_payload_files(boot, 'initramfs-linux.img'), None):
            problems.append('Missing boot initramfs image: ' + str(boot / 'initramfs-linux.img'))
    if not kernel:
        problems.append('Missing Linux kernel image in /boot or /usr/lib/modules.')
    if not any(next((path for path in _payload_files(root, str(version.relative_to(root) / 'kernel'))
                     if path.name.endswith(('.ko', '.ko.zst', '.ko.xz', '.ko.gz'))), None)
               for version in versions):
        problems.append('Missing installed Linux kernel modules.')
    if not versions or not any(guest_path(root, str(version.relative_to(root) / 'modules.dep')).is_file()
                               for version in versions):
        problems.append('Missing kernel module dependency index (modules.dep).')
    if not next((path for path in _payload_files(root, 'usr/lib/firmware')
                 if not path.name.startswith(('LICENSE', 'LICENCE', 'WHENCE'))), None):
        problems.append('Missing firmware payload under /usr/lib/firmware.')
    return problems

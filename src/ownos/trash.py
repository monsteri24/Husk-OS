"""Gio Trash operations, with the standard local Trash as an offline fallback."""
import configparser
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote_to_bytes


def _gio():
    from gi.repository import Gio, GLib
    return Gio, GLib


def mounted_roots(mountinfo=Path('/proc/self/mountinfo')):
    """Local mount points, including the escaping used by Linux mountinfo."""
    try: lines = Path(mountinfo).read_text(encoding='utf-8', errors='surrogateescape').splitlines()
    except OSError: return []
    roots = set()
    for line in lines:
        fields = line.split()
        if len(fields) < 7: continue
        decoded = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), fields[4])
        if decoded.startswith('/'): roots.add(Path(decoded))
    return sorted(roots, key=str)


def _real_directory(path, owned=True):
    try: info = path.lstat()
    except OSError: return False
    return (stat.S_ISDIR(info.st_mode) and
            (not owned or (info.st_uid == os.getuid() and not info.st_mode & 0o022)))


@dataclass(frozen=True)
class TrashItem:
    uri: str
    name: str
    original: Path | None
    deleted: str = ''
    icon: object = 'text-x-generic'
    info_path: Path | None = None


class TrashStore:
    def __init__(self):
        self.root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'Trash'
        self.monitors = []
        self.local_monitors = {}; self.virtual_monitor = None; self.callback = None

    def move(self, path):
        Gio, _ = _gio()
        Gio.File.new_for_path(str(path)).trash(None)

    def entries(self):
        Gio, GLib = _gio()
        if self.callback is not None: self._sync_monitors()
        root = Gio.File.new_for_uri('trash:///')
        try:
            iterator = root.enumerate_children('standard::name,standard::display-name,standard::icon,trash::orig-path,trash::deletion-date',
                                               Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None)
        except GLib.Error as exc:
            if not (exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_SUPPORTED) or
                    exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND)):
                raise
            return self._local_entries()
        items = []
        try:
            while True:
                info = iterator.next_file(None)
                if info is None: break
                original = info.get_attribute_byte_string('trash::orig-path')
                items.append(TrashItem(root.get_child(info.get_name()).get_uri(), info.get_display_name(),
                                       Path(original) if original else None,
                                       info.get_attribute_string('trash::deletion-date') or '', info.get_icon()))
        finally:
            iterator.close(None)
        return sorted(items, key=lambda item: item.name.casefold())

    def _locations(self):
        locations = {}
        def add(root, mount):
            if all(_real_directory(path) for path in (root, root / 'files', root / 'info')):
                locations[root] = mount
        add(self.root, None)
        uid = os.getuid()
        for mount in mounted_roots():
            add(mount / f'.Trash-{uid}', mount)
            shared = mount / '.Trash'
            if _real_directory(shared, owned=False) and shared.lstat().st_mode & stat.S_ISVTX:
                add(shared / str(uid), mount)
        return locations.items()

    def _local_entries(self):
        """Read home and per-volume stores using the freedesktop Trash format."""
        items = []
        for location, mount in self._locations():
            items.extend(self._location_entries(location, mount))
        return sorted(items, key=lambda item: item.name.casefold())

    @staticmethod
    def _location_entries(location, mount):
        files, info_dir = location / 'files', location / 'info'
        items = []
        for file in files.iterdir():
            info_path = info_dir / (file.name + '.trashinfo')
            parser = configparser.ConfigParser(interpolation=None)
            original = None; deleted = ''
            try:
                parser.read(info_path, encoding='utf-8')
                value = os.fsdecode(unquote_to_bytes(parser.get('Trash Info', 'Path')))
                parsed = Path(value)
                if '\0' not in value and '..' not in parsed.parts:
                    if parsed.is_absolute() and (mount is None or parsed.is_relative_to(mount)):
                        original = parsed
                    elif mount is not None and not parsed.is_absolute(): original = mount / parsed
                deleted = parser.get('Trash Info', 'DeletionDate', fallback='')
            except (OSError, ValueError, configparser.Error):
                pass
            items.append(TrashItem(file.as_uri(), original.name if original else file.name, original,
                                   deleted, 'folder' if file.is_dir() else 'text-x-generic', info_path))
        return sorted(items, key=lambda item: item.name.casefold())

    def restore(self, item):
        if item.original is None:
            raise ValueError('The original location of this item is unavailable')
        Gio, _ = _gio()
        # NONE refuses replacement, including a competing create after a UI
        # refresh. Gio reports collisions without deleting the trashed copy.
        item.original.parent.mkdir(parents=True, exist_ok=True)
        Gio.File.new_for_uri(item.uri).move(Gio.File.new_for_path(str(item.original)),
                                           Gio.FileCopyFlags.NONE, None, None, None)
        if item.info_path is not None:
            item.info_path.unlink(missing_ok=True)
        return item.original

    @staticmethod
    def _delete(file):
        Gio, _ = _gio()
        info = file.query_info('standard::type', Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None)
        if info.get_file_type() == Gio.FileType.DIRECTORY:
            iterator = file.enumerate_children('standard::name', Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None)
            try:
                while True:
                    child = iterator.next_file(None)
                    if child is None: break
                    TrashStore._delete(file.get_child(child.get_name()))
            finally:
                iterator.close(None)
        file.delete(None)

    def empty(self):
        """Permanently delete Trash contents; the caller must confirm in the UI."""
        Gio, _ = _gio()
        for item in self.entries():
            self._delete(Gio.File.new_for_uri(item.uri))
            if item.info_path is not None: item.info_path.unlink(missing_ok=True)

    def watch(self, callback):
        Gio, GLib = _gio()
        self.close()
        for directory in (self.root, self.root / 'files', self.root / 'info'):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not _real_directory(directory): raise OSError('Trash must use directories owned by the current user')
        self.callback = callback
        self._sync_monitors()
        try:
            self.virtual_monitor = Gio.File.new_for_uri('trash:///').monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self.virtual_monitor.connect('changed', self._changed)
            self.monitors.append(self.virtual_monitor)
        except GLib.Error:
            pass

    def _changed(self, *_):
        if self.callback is not None: self.callback()

    def _sync_monitors(self):
        Gio, GLib = _gio()
        paths = {location / child for location, _ in self._locations() for child in ('files', 'info')}
        for path in self.local_monitors.keys() - paths:
            self.local_monitors.pop(path).cancel()
        for path in paths - self.local_monitors.keys():
            try:
                monitor = Gio.File.new_for_path(str(path)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
                monitor.connect('changed', self._changed); self.local_monitors[path] = monitor
            except GLib.Error: pass
        self.monitors = list(self.local_monitors.values()) + ([self.virtual_monitor] if self.virtual_monitor is not None else [])

    def close(self):
        for monitor in self.monitors: monitor.cancel()
        self.monitors.clear()
        self.local_monitors.clear(); self.virtual_monitor = None; self.callback = None

"""File navigation and explicit, non-overwriting desktop operations."""
import ctypes
import errno
import os
import shutil
from pathlib import Path
from urllib.parse import unquote, urlsplit
from ownos.i18n import _


def list_folder(path, hidden=False):
    entries = [p for p in Path(path).iterdir() if hidden or not p.name.startswith('.')]
    return sorted(entries, key=lambda p: (not p.is_dir(), p.name.casefold()))


def validate_name(name):
    if not isinstance(name, str) or name in ('', '.', '..') or '/' in name or '\0' in name or len(name.encode()) > 255:
        raise ValueError(_('Give the item a single valid name'))
    return name


def create_folder(parent, name):
    validate_name(name)
    path = Path(parent) / name
    path.mkdir()
    return path


def create_file(parent, name):
    path = Path(parent) / validate_name(name)
    with path.open('xb'):
        pass
    return path


def rename_entry(path, name):
    """Linux rename without replacing a file created during the operation."""
    source = Path(path)
    target = source.with_name(validate_name(name))
    if target == source:
        return source
    _move_entry(source, target)
    return target


def _move_entry(source, target):
    libc = ctypes.CDLL(None, use_errno=True)
    # Husk OS runs on Linux. RENAME_NOREPLACE is atomic, unlike an exists()
    # check followed by Path.rename(), which can silently replace user data.
    rename = libc.renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def _copy_file(source, target):
    source, target = Path(source), Path(target)
    if source.is_symlink():
        target.symlink_to(os.readlink(source))
    else:
        with source.open('rb') as incoming, target.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        shutil.copystat(source, target)
    return str(target)


def paste_entries(parent, sources, cut=False):
    """Copy entries, or atomically move cuts within the same filesystem."""
    parent = Path(parent)
    pairs = [(Path(source), parent / Path(source).name) for source in sources]
    destinations = set()
    for source, target in pairs:
        if target in destinations or target.exists() or target.is_symlink():
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(target))
        destinations.add(target)
        if source.is_dir() and not source.is_symlink() and source.resolve() in (parent.resolve(), *parent.resolve().parents):
            raise ValueError(_('A folder cannot be pasted into itself'))
        if not source.is_symlink() and not source.is_file() and not source.is_dir():
            raise ValueError(_('Only regular files and folders can be pasted'))
        if cut and source.lstat().st_dev != parent.stat().st_dev:
            raise OSError(errno.EXDEV, _('Moving between filesystems is unavailable. Copy the item instead.'), str(source))
    result = []
    for source, target in pairs:
        if cut:
            _move_entry(source, target)
        elif source.is_dir() and not source.is_symlink():
            shutil.copytree(source, target, symlinks=True, copy_function=_copy_file)
        else:
            _copy_file(source, target)
        result.append(target)
    return result


def parse_file_clipboard(data, gnome=False):
    """Return (cut, local paths) for file clipboard targets, else None."""
    if not isinstance(data, str) or '\0' in data:
        return None
    lines = [line.strip() for line in data.splitlines() if line.strip() and not line.startswith('#')]
    cut = False
    if gnome:
        if not lines or lines[0] not in ('copy', 'cut'):
            return None
        cut = lines.pop(0) == 'cut'
    paths = []
    for line in lines:
        try: uri = urlsplit(line)
        except ValueError: return None
        if uri.scheme != 'file' or uri.netloc not in ('', 'localhost') or uri.query or uri.fragment:
            return None
        decoded = unquote(uri.path)
        if not decoded.startswith('/') or '\0' in decoded:
            return None
        paths.append(Path(decoded))
    return (cut, paths) if paths else None

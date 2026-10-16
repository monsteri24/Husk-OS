"""Non-destructive file navigation primitives."""
from pathlib import Path


def list_folder(path, hidden=False):
    entries = [p for p in Path(path).iterdir() if hidden or not p.name.startswith('.')]
    return sorted(entries, key=lambda p: (not p.is_dir(), p.name.casefold()))


def create_folder(parent, name):
    if not isinstance(name, str) or name in ('', '.', '..') or '/' in name or '\0' in name or len(name.encode()) > 255:
        raise ValueError('Give the folder a single valid name')
    path = Path(parent) / name
    path.mkdir()
    return path

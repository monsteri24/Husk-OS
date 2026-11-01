"""Desktop entries distinguish user files from protected shell actions."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesktopEntry:
    kind: str
    label: str
    icon: str
    path: Path | None = None

    @property
    def protected(self):
        return self.kind != 'file'


def live_installer_available(live_root=Path('/run/archiso'), executable=Path('/usr/bin/husk-install')):
    return Path(live_root).is_dir() and Path(executable).is_file() and os.access(executable, os.X_OK)


def desktop_entries(desktop, *, home=None, show_trash=True, live=None):
    home = Path.home() if home is None else Path(home)
    entries = [DesktopEntry('home', 'Home', 'user-home', home)]
    if show_trash:
        entries.append(DesktopEntry('trash', 'Trash', 'user-trash'))
    if (live_installer_available() if live is None else live):
        entries.append(DesktopEntry('installer', 'Install Husk OS', 'husk-install'))
    try:
        paths = sorted((p for p in Path(desktop).iterdir() if not p.name.startswith('.')),
                       key=lambda p: (not p.is_dir(), p.name.casefold()))
    except OSError:
        paths = []
    entries.extend(DesktopEntry('file', p.name, 'folder' if p.is_dir() else 'text-x-generic', p) for p in paths)
    return entries

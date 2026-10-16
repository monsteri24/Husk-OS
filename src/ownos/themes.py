"""Bounded per-user appearance inputs; no system rebuild is involved."""
from pathlib import Path
from ownos.i18n import _


def read_user_css(path):
    path = Path(path)
    if not path.exists(): return b''
    if path.stat().st_size > 65536:
        raise ValueError(_('Custom CSS must be no larger than 64 KiB.'))
    data = path.read_bytes()
    data.decode('utf-8')
    return data

"""Per-process gaming policy; never runs arbitrary strings through a shell."""
import shutil
from ownos.config import validate
from ownos.i18n import _


def game_command(argv, settings, available=shutil.which):
    if not argv or not all(isinstance(a, str) and '\0' not in a for a in argv):
        raise ValueError(_('A non-empty game command is required'))
    cfg = validate(settings)
    result = []
    for enabled, tool in ((cfg['gaming_mode'], 'gamemoderun'), (cfg['overlay'], 'mangohud')):
        if enabled:
            path = available(tool)
            if not path:
                raise FileNotFoundError(_('{tool} is not installed; install it or disable this setting').format(tool=tool))
            result.append(path)
    return result + list(argv)

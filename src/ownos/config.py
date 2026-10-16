"""Small, validated, atomic per-user configuration."""
import json
import os
import re
import tempfile
from pathlib import Path
from ownos.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

KEYMAPS = ('fi', 'us', 'gb', 'se', 'de', 'fr')


def defaults():
    return dict(gaming_mode=True, overlay=False, animations=True,
                accent='#4d94ff', wallpaper='', keymap='fi', pointer_speed=0.0,
                taskbar_position='bottom', language=DEFAULT_LANGUAGE)


def validate(settings):
    values = defaults()
    for key in values:
        if key in settings:
            values[key] = settings[key]
    for key in ('gaming_mode', 'overlay', 'animations'):
        if type(values[key]) is not bool:
            raise ValueError(key + ' must be a boolean')
    if not isinstance(values['accent'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', values['accent']):
        raise ValueError('Invalid accent color')
    if not isinstance(values['wallpaper'], str) or len(values['wallpaper']) > 4096:
        raise ValueError('Invalid wallpaper path')
    if values['keymap'] not in KEYMAPS:
        raise ValueError('Unsupported keyboard layout')
    if values['taskbar_position'] not in ('bottom', 'top'):
        raise ValueError('Taskbar position must be bottom or top')
    if values['language'] not in SUPPORTED_LANGUAGES:
        raise ValueError('Unsupported interface language')
    speed = values['pointer_speed']
    if type(speed) not in (int, float) or not -1 <= speed <= 1:
        raise ValueError('Pointer speed must be between -1 and 1')
    return values


class ConfigStore:
    def __init__(self, path=None):
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        self.path = Path(path) if path is not None else base / 'ownos/settings.json'

    def load(self):
        try:
            if self.path.stat().st_size > 65536:
                return defaults()
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                return defaults()
            result = defaults()
            for key, value in data.items():
                if key not in result:
                    continue
                try:
                    result[key] = validate({key: value})[key]
                except (ValueError, TypeError):
                    pass
            return result
        except (OSError, ValueError, UnicodeError):
            return defaults()

    def save(self, settings):
        data = validate(settings)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp = tempfile.mkstemp(prefix='.settings-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                json.dump(data, out, ensure_ascii=False, indent=2)
                out.write('\n'); out.flush(); os.fsync(out.fileno())
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

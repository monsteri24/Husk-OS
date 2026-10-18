"""Small, validated, atomic per-user configuration."""
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from ownos.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

KEYMAPS = ('fi', 'us', 'gb', 'se', 'de', 'fr')
HUSK_YELLOW = '#f5cf3b'
SYSTEM_KEYBOARD_PATH = Path('/etc/ownos/keyboard.json')


def validate_keyboard_record(record):
    """A single XKB layout/variant, safe in labwc's environment file."""
    if not isinstance(record, dict):
        raise ValueError('Invalid keyboard record')
    layout, variant = record.get('layout'), record.get('variant', '')
    identifier = r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}'
    if not isinstance(layout, str) or not re.fullmatch(identifier, layout):
        raise ValueError('Invalid keyboard layout')
    if not isinstance(variant, str) or (variant and not re.fullmatch(identifier, variant)):
        raise ValueError('Invalid keyboard variant')
    return {'layout': layout, 'variant': variant}


def read_system_keyboard(path=None):
    """Read the installer record only when it is a trusted root-owned file."""
    path = SYSTEM_KEYBOARD_PATH if path is None else path
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, encoding='utf-8') as stream:
            metadata = os.fstat(stream.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or
                    metadata.st_mode & 0o022 or metadata.st_size > 4096):
                return None
            data = stream.read(4097)
            if len(data) > 4096:
                return None
        return validate_keyboard_record(json.loads(data))
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None


def keymap_options():
    keyboard = read_system_keyboard()
    return _keymap_options(keyboard)


def _keymap_options(keyboard):
    if keyboard and keyboard['layout'] not in KEYMAPS:
        return (*KEYMAPS, keyboard['layout'])
    return KEYMAPS


def defaults():
    return _defaults(read_system_keyboard())


def _defaults(keyboard):
    keyboard = keyboard or {'layout': 'fi', 'variant': ''}
    return dict(gaming_mode=True, overlay=False, animations=True,
                accent=HUSK_YELLOW, wallpaper='', keymap=keyboard['layout'],
                keymap_variant=keyboard['variant'], pointer_speed=0.0,
                taskbar_position='bottom', language=DEFAULT_LANGUAGE, show_trash=True)


def validate(settings):
    keyboard = read_system_keyboard()
    values = _defaults(keyboard)
    if 'keymap' in settings and settings['keymap'] != values['keymap'] and 'keymap_variant' not in settings:
        values['keymap_variant'] = ''
    for key in values:
        if key in settings:
            values[key] = settings[key]
    for key in ('gaming_mode', 'overlay', 'animations', 'show_trash'):
        if type(values[key]) is not bool:
            raise ValueError(key + ' must be a boolean')
    if not isinstance(values['accent'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', values['accent']):
        raise ValueError('Invalid accent color')
    if not isinstance(values['wallpaper'], str) or len(values['wallpaper']) > 4096:
        raise ValueError('Invalid wallpaper path')
    if values['keymap'] not in _keymap_options(keyboard):
        raise ValueError('Unsupported keyboard layout')
    validate_keyboard_record({'layout': values['keymap'], 'variant': values['keymap_variant']})
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
                if key not in result or key in ('keymap', 'keymap_variant'):
                    continue
                try:
                    result[key] = validate({key: value})[key]
                except (ValueError, TypeError):
                    pass
            keyboard = {key: data[key] for key in ('keymap', 'keymap_variant') if key in data}
            try:
                selected = validate(keyboard)
            except (ValueError, TypeError):
                try: selected = validate({'keymap': data['keymap']}) if 'keymap' in data else defaults()
                except (ValueError, TypeError): selected = defaults()
            for key in ('keymap', 'keymap_variant'):
                result[key] = selected[key]
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

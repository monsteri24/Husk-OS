"""English source messages and an explicit gettext language allowlist.

Add a reviewed language to SUPPORTED_LANGUAGES when its catalog is shipped.
Host locale variables never select an unsupported translation implicitly.
"""
import gettext as _gettext
import struct
from pathlib import Path

DOMAIN = 'huskos'
DEFAULT_LANGUAGE = 'en'
SUPPORTED_LANGUAGES = ('en', 'fi')
LOCALEDIR = Path('/usr/share/locale')

_translation = _gettext.NullTranslations()


def configure(language=DEFAULT_LANGUAGE, localedir=None):
    """Load a supported catalog, falling back to the English source messages."""
    global _translation
    language = language if isinstance(language, str) else DEFAULT_LANGUAGE
    language = language.split('.', 1)[0].replace('-', '_')
    if language not in SUPPORTED_LANGUAGES:
        language = language.split('_', 1)[0]
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    try:
        _translation = _gettext.translation(
            DOMAIN, localedir=str(LOCALEDIR if localedir is None else localedir),
            languages=[language], fallback=True)
    except (OSError, EOFError, ValueError, LookupError, struct.error):
        # Broken or unreadable catalogs must not prevent a graphical login.
        _translation = _gettext.NullTranslations()
        language = DEFAULT_LANGUAGE
    return DEFAULT_LANGUAGE if type(_translation) is _gettext.NullTranslations else language


def configure_saved(store=None, localedir=None):
    """Load the explicit per-user choice before building a Husk interface.

    ConfigStore supplies English for missing, unsupported or corrupt settings;
    localedir is injectable for catalog development and isolated tests.
    """
    from ownos.config import ConfigStore
    settings = (store if store is not None else ConfigStore()).load()
    return configure(settings.get('language', DEFAULT_LANGUAGE), localedir=localedir)


def gettext(message):
    return _translation.gettext(message)


def ngettext(singular, plural, count):
    return _translation.ngettext(singular, plural, count)


gettext_ = gettext
_ = gettext

configure()

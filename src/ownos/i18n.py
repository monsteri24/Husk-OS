"""English source messages and an explicit gettext language allowlist.

Add a reviewed language to SUPPORTED_LANGUAGES when its catalog is shipped.
Host locale variables never select an unsupported translation implicitly.
"""
import gettext as _gettext
from pathlib import Path

DOMAIN = 'huskos'
DEFAULT_LANGUAGE = 'en'
SUPPORTED_LANGUAGES = ('en',)
LOCALEDIR = Path('/usr/share/locale')

_translation = _gettext.NullTranslations()


def configure(language=DEFAULT_LANGUAGE, localedir=None):
    """Load a supported catalog, falling back to the English source messages."""
    global _translation
    language = str(language or DEFAULT_LANGUAGE).split('.', 1)[0].replace('-', '_')
    if language not in SUPPORTED_LANGUAGES:
        language = language.split('_', 1)[0]
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    _translation = _gettext.translation(
        DOMAIN, localedir=str(LOCALEDIR if localedir is None else localedir),
        languages=[language], fallback=True)
    return language


def gettext(message):
    return _translation.gettext(message)


def ngettext(singular, plural, count):
    return _translation.ngettext(singular, plural, count)


gettext_ = gettext
_ = gettext

configure()

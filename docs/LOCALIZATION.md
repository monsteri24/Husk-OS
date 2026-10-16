# Husk OS localization

Husk Desktop and Husk Settings use English source messages. English is the
only supported Husk interface language in system-2-dev. Finnish host locale
variables such as `LANGUAGE=fi` do not select a Finnish Husk interface, and
there is no Husk language selector or Finnish catalog. Keyboard layouts,
including the Finnish layout, are independent of the interface language.

Python UI and user-facing helper messages use the standard-library gettext
domain `huskos` through `ownos.i18n`. Import `_` for singular messages and
`ngettext` for counts. Translate the complete message before formatting named
placeholders:

```python
from ownos.i18n import _, ngettext

title = _('Install {application}?').format(application=app.name)
status = ngettext('{count} item', '{count} items', count).format(count=count)
```

`gettext`, `gettext_`, and `_` are equivalent entry points. Their functions
follow later calls to `configure(language='en', localedir=...)`, so imported
entry points do not retain an old catalog. Unsupported languages fall back
to English. Missing catalogs fall back to the English source text.

Run `bash scripts/update-translations.sh` with GNU gettext installed to
regenerate `locale/huskos.pot` from Python and desktop entry source messages.
The POT is a template, not an enabled translation. A future language needs a
reviewed PO catalog, an entry in `SUPPORTED_LANGUAGES`, appropriate plural
forms, and tests before it becomes selectable. Compile reviewed catalogs to
`/usr/share/locale/<language>/LC_MESSAGES/huskos.mo` with `msgfmt --check`.

SDDM and the Calamares slideshow use English Qt `qsTr` source strings. Their
future translations need the Qt translation tools and a separate reviewed
catalog. Calamares, GTK file chooser internals, KDE, GNOME, and other external
applications manage their own translations and locale choices. Husk does
not remove upstream language choices. Husk-owned dialog buttons use explicit
English gettext messages even when the toolkit's host locale is Finnish.

Validate the English fallback with
`PYTHONPATH=src python3 -m unittest discover -s tests -p test_i18n.py -v`.
GTK smoke tests require GI and a prepared display; use `scripts/test-gtk.sh`
in that environment.

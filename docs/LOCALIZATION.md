# Husk OS localization

Husk applications default to English, regardless of host `LANG`, `LC_ALL` or
`LANGUAGE`. Finnish is explicitly selectable in **Husk Settings → Appearance →
Interface language** as **Suomi (fi-FI)**. The choice is saved per user in
`~/.config/ownos/settings.json` (or `$XDG_CONFIG_HOME/ownos/settings.json`) as
`"language": "fi"`; English uses `"en"`. Existing settings without that key
continue to use English. Keyboard layout is a separate setting under **Input**.

The running Husk Desktop watches settings and reloads its taskbar, launcher,
desktop labels and notification controls when the language changes. Notification
history is retained. Reopen other Husk applications, including Settings and Files,
to apply the new language throughout their interfaces. The choice is loaded again
when a new application or desktop session starts. Live-session settings last for
that session unless persistence is provided by the boot environment.

Python UI and user-facing helper messages use the standard-library gettext
domain `huskos` through `ownos.i18n`. Import `_` for singular messages and
`ngettext` for counts. Translate the complete message before formatting named
placeholders:

```python
from ownos.i18n import _, ngettext

title = _('Install {application}?').format(application=app.name)
status = ngettext('{count} item', '{count} items', count).format(count=count)
```

`gettext`, `gettext_`, and `_` are equivalent dynamic entry points: imported
functions follow later catalog configuration. `configure_saved(store=None)` loads
the validated user choice at process startup. GUI constructors also load it before
creating translated widgets, using their passed configuration store. For catalog
development, `configure(language='fi-FI', localedir=...)` and
`configure_saved(store, localedir=...)` accept an explicit catalog directory.
Locale aliases such as `fi-FI` and `fi_FI.UTF-8` resolve to the `fi` gettext catalog;
settings store the allowlisted short code. Unsupported or invalid saved language
values fall back to English while preserving other valid settings. Corrupt settings,
missing catalogs and unreadable or malformed gettext files also fall back safely.
No host-language autodetection is used.

The Finnish catalog is `locale/fi/LC_MESSAGES/huskos.po`. It includes Husk-owned
Settings, Files, Start/search, taskbar, window-action, notification and helper
messages. Finnish uses two plural forms, with singular only for one. Product names,
commands and named formatting fields are preserved. GNU gettext checks formatting;
the tests also check UI message coverage and field names. The Arch package compiles
the catalog to `/usr/share/locale/fi/LC_MESSAGES/huskos.mo` during packaging.

Run `bash scripts/update-translations.sh` with GNU gettext installed to regenerate
`locale/huskos.pot` from Python and desktop-entry source messages. Review additions
in every supported PO catalog and compile with:

```sh
msgfmt --check --check-format locale/fi/LC_MESSAGES/huskos.po -o /tmp/huskos-fi.mo
```

SDDM and the Calamares slideshow use English Qt `qsTr` source strings. Their
translations need Qt translation tools and separate reviewed catalogs. Calamares,
GTK file chooser internals, KDE, GNOME, desktop-entry labels supplied by other
packages, and other external applications manage their own language choices. The
Husk language setting does not change the system locale or those upstream choices.
Husk-owned dialog buttons use explicit gettext messages.

Run `PYTHONPATH=src python3 -m unittest discover -s tests -p test_i18n.py -v` for
catalog compilation, Finnish plurals, English fallbacks and saved-choice loading
in a fresh process. Real GTK localization checks live in
`tests/test_localization_ui.py`; run `scripts/test-gtk.sh` with GI, gettext and a
prepared display. Skipped GUI tests are not evidence of graphical acceptance.

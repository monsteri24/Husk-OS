# Husk OS language policy

**System 2 supports English only.** Finnish is postponed. Husk Settings shows
English as the sole, fixed interface-language choice. The preserved
`locale/fi/LC_MESSAGES/huskos.po` is source material for later work; the System 2
binary package does not install a Finnish `huskos.mo`, and rootfs validation does
not require one.

Husk's interface stays English regardless of host `LANG`, `LC_ALL` or `LANGUAGE`.
Earlier settings containing `"language": "fi"`, `fi_FI`, `fi-FI` or
`fi_FI.UTF-8` load as English while retaining other valid settings. Unsupported
or malformed values and corrupt settings also use English. New settings accept
only `"language": "en"`; there is no host-language autodetection. Keyboard layout
is independent under **Input**, where the Finnish layout remains available.

The existing standard-library gettext architecture remains in place. Python UI
and helper messages use domain `huskos` through `ownos.i18n`. Import `_` for
singular messages and `ngettext` for counts; format complete translated messages
with named placeholders:

```python
from ownos.i18n import _, ngettext

title = _('Install {application}?').format(application=app.name)
status = ngettext('{count} item', '{count} items', count).format(count=count)
```

`gettext`, `gettext_`, and `_` remain equivalent dynamic entry points.
`configure_saved(store=None)` loads validated settings before application/session
startup and before GUI widgets are built. `configure(language=..., localedir=...)`
retains its existing API, but System 2's allowlist contains only `en`. An existing
Finnish catalog cannot enable Finnish, even when explicitly requested. Missing,
unreadable or malformed supported catalogs safely fall back to English source
messages.

`locale/huskos.pot` remains the gettext source template. The Finnish PO is retained
unchanged in Git for future work; compiling it for a source check does not enable
or package that language in System 2.

SDDM and the Calamares slideshow use English Qt `qsTr` source strings. Calamares,
GTK toolkit internals, KDE, GNOME and external applications manage their own
upstream language choices. Husk's English-only policy does not change the system
locale or external applications. Husk-owned dialog buttons use explicit gettext
messages.

Run `PYTHONPATH=src python3 -m unittest discover -s tests -p test_i18n.py -v` for
English-only runtime/configuration checks, including Finnish host settings and
saved Finnish choices in a fresh process. The package test verifies that postponed
catalogs are absent from the staged core package. Real GTK checks in
`tests/test_localization_ui.py` verify the sole English Settings choice and English
application/desktop labels; run `scripts/test-gtk.sh` with GI and a prepared
display. Skips do not establish graphical acceptance.

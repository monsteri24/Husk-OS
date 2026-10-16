# Husk Desktop icons

These five scalable icons are original geometric artwork by the Husk OS / OwnOS
contributors, released under the repository's MIT license. Each SVG carries an
SPDX license identifier; the UI package includes the full license as
`/usr/share/licenses/ownos-ui/LICENSE.icons`.

The icons share a 24 by 24 coordinate system and a two-unit safe margin. They
serve Start, Settings, Files and the generic game/application fallbacks. They
contain no third-party logos. Installed applications retain their own icon when
GTK can load it; an optional application does not need to be preinstalled for
its launcher to have a visible fallback.

The UI adds this directory to GTK's source-preview search path. Packaging
installs the SVGs in the standard hicolor `scalable/apps` directory without
replacing the system hicolor theme or requiring a network download.

# Optional application artwork

These unmodified upstream assets identify optional applications before they are
installed. They are separate from Husk's original MIT-licensed interface icons.
An installed icon theme may provide its own application icon. The bundled
artwork is available offline and does not install or run either application.

## Steam

- File: `steam.png`, exactly the 256 × 256 app icon from Valve's versioned
  `steam-launcher_1.0.0.87_amd64.deb`, path
  `usr/share/icons/hicolor/256x256/apps/steam.png`.
- Upstream: <https://repo.steampowered.com/steam/archive/stable/steam-launcher_1.0.0.87_amd64.deb>
- Icon SHA-256: `b7087da76b8315024887b9a9313be5b9e6ba87d25eb624eac2d6542a823bb87d`.
- Package SHA-256: `765aba9a0ed339a50226ceb614fcc9879a991ba184098bc8de920efb12c714a4`.
- Rights: proprietary Valve artwork, not covered by Husk's MIT license.
  The package's copyright notice and supplied agreement are retained in
  `COPYRIGHT.Steam` and `LICENSE.Steam`. Use of the logo is subject to Valve's
  [Steam Branding Guidelines](https://partner.steamgames.com/doc/marketing/branding).
  It is used only to identify Steam in the launcher and optional installer.
- ©2026 Valve Corporation. Steam and the Steam logo are trademarks and/or
  registered trademarks of Valve Corporation in the U.S. and/or other countries.
  Husk OS is not affiliated with or endorsed by Valve.

Valve's Linux launcher supplies this icon as PNG. The original bytes are
preserved rather than retracing or inventing vector artwork. GTK scales the
256px source for the desktop's smaller icon sizes.

## Heroic Games Launcher

- File: `com.heroicgameslauncher.hgl.svg`, exactly
  `src/frontend/assets/heroic-icon.svg` from Heroic upstream commit
  `509a34feea8541b73c928e289f2cf262d432db4a`.
- Upstream: <https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/blob/509a34feea8541b73c928e289f2cf262d432db4a/src/frontend/assets/heroic-icon.svg>
- SHA-256: `717865139e87a37bdbedf6afed1e6f7eba2eb93806c536f444afac0f24607ca5`.
- License: GPL-3.0-only, as declared by the upstream `package.json` at the same
  commit. The complete upstream GPL text is retained as `COPYING.Heroic`.
- Corresponding upstream source:
  <https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/tree/509a34feea8541b73c928e289f2cf262d432db4a>.
  The original SVG is its preferred editable source and is distributed here
  without modification. The Heroic name and logo identify that project;
  Husk OS is not affiliated with or endorsed by Heroic's developers.

Retrieved 2026-10-17. SHA-256 values are checked by the artwork regression tests.

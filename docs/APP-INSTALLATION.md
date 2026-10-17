# A clean base and optional applications

System 2 development profiles retain Husk Desktop, Husk Settings, Husk Files,
Labwc, Foot, the kernel, firmware, graphics libraries and essential network,
audio, storage and recovery tools. Steam, Proton, Wine/Winetricks, Lutris, Heroic,
Discord, Firefox, OBS and other optional user applications are excluded from the
default package policy. A catalog entry or taskbar icon does not mean an app is
installed. The desktop never installs optional apps at startup.

Flatpak remains installation infrastructure. The first-boot release candidate
uses 64-bit Mesa; the standard development profile also includes 32-bit graphics
libraries. Generating a profile or testing an inventory fixture does not establish
what a finished ISO contains. The completed System 2 image has now been extracted
and its actual package records and required payloads have passed validation.
The separate optional-app transaction does not add Firefox to that image.

## Curated choices and trusted sources

| Start entry / helper ID | Source | Scope |
|---|---|---|
| Steam / `steam` | Signed Arch package | Native system transaction |
| Heroic / `heroic` | Official Flathub `com.heroicgameslauncher.hgl` | Per-user Flatpak |
| Lutris / `lutris` | Signed Arch package | Native system transaction |
| Discord / `discord` | Signed Arch package | Native system transaction |
| Firefox / `firefox` | Signed Arch package | Native system transaction |

The native helper is allowlisted and performs a full `pacman -Syu --needed`
transaction. It retains package signature checks and avoids partial upgrades.
Heroic uses the official HTTPS Flathub repository description and user-level
installation. An existing Flathub remote with an unexpected URL or disabled GPG
verification is refused before changes. No AUR recipes, arbitrary download-and-run
scripts or disabled signature checks are part of these paths.

## Installation sequence

1. Search Start and activate the application's row, or use its curated taskbar
   shortcut. An installed application launches; an absent one opens an
   installation dialog.
2. Read the source and transaction description. **Cancel** stops the request.
   A deliberate new press and release on **OK** opens the installer terminal;
   the dialog does not reuse the click that opened it.
3. For native installation as the fresh Live `live` user, follow the terminal's
   interactive `passwd` prompts to create a temporary account password. Then
   enter it in the separate administrator authorization dialog.
4. Review and confirm pacman's complete proposed update/install transaction, or
   Flatpak's per-user installation proposal for Heroic. Cancelling authentication
   or declining installation does not install the application.
5. Read the final message in the terminal. Foot is started with `--hold`, so
   success and failure output stay visible after the installer exits. Success
   requires a package record from `pacman -Q` or an app record from
   `flatpak info --user`; an exit status alone is insufficient.
6. After verified success, select the application again in Husk Desktop to launch
   it. Installation does not automatically launch it. Close the held terminal
   after reading the result.

Native authorization remains `auth_admin`. The Live-specific polkit rule chooses
the active local `live` user's identity only for the allowlisted
`org.ownos.admin` action; it does not grant passwordless permission. The separate
experimental installer policy also retains administrator authentication. The
Live root account remains locked. The temporary password lasts only for the
Live session unless a separate persistence system is provided. Installed systems
use their normal administrator credentials. User-level Flatpak installation does
not use this native Live-password setup.

The equivalent explicit terminal helpers accept these IDs:

```sh
husk-install-app steam
husk-install-app heroic
husk-install-app lutris
husk-install-app discord
husk-install-app firefox
```

The standalone command returns its result to your terminal. The desktop's
installation path adds the held Foot window described above.

## Current verification limits

Current verification commit `5fd07e6` passed **235 actual GTK tests without
skips**, 121 source/configuration checks and **18 real nested Labwc scenarios**.
These include default/fresh Cancel, inherited pointer releases over both buttons,
cross-button dragging, and deliberate pointer/keyboard OK opening the real held
Foot installer terminal. See [the verification run](https://github.com/monsteri24/Husk-OS/actions/runs/39004672433)
and [the System 2 report](../HuskOS-system-2-REPORT.md).

The immutable System 2 ISO was created and its actual extracted root filesystem,
original wallpaper, English-only Husk configuration, authentication helpers and
package inventory were checked. The same signed Husk core package embedded in
that image was verified and installed in a separate disposable Arch container.
There, the real `own-admin` helper installed signed Firefox packages through a
full pacman transaction; the package record, nonroot version command and normal
headless Firefox launch/screenshot all passed. Explicit font/JACK providers were
selected during CI setup before the actual transaction confirmation.

**A complete Live GUI/password/polkit/network installation and subsequent GUI
application launch has not been accepted end to end.** The independent package
transaction and real dialog-input checks do not establish that path or physical
networking. The Ubuntu source-test terminal safely displayed its missing-pkexec
error; that screenshot is evidence of visible failure handling, not a successful
Arch installation. Heroic/Steam/Lutris downloads, launcher account login and games
have no new runtime acceptance result.

## Updates and gaming tools

Settings exposes a full Arch system update; user Flatpaks can be updated with
`flatpak --user update`. Both require the relevant network access and normal
confirmation. Automatic rollback is not available.

Before using Settings' system-update, desktop-install or driver actions in a
fresh Live session, open Terminal and run `passwd` to set the temporary `live`
password first. Those existing actions go directly to the authentication prompt;
the native application installer described above performs this preparation
automatically. No passwordless administrative permission is supplied.

GameMode and MangoHud are optional and are not installed by their Settings
switches. `husk-game` uses `gamemoderun` when GameMode is enabled and `mangohud`
when the overlay is enabled; it reports a missing tool instead of silently
pretending it ran. Install the required tools through trusted package sources,
or disable the corresponding option before using the wrapper. Steam launch
options can use `husk-game -- %command%` once those prerequisites are satisfied.
Let Steam manage its supported Proton versions after you install Steam; no
Proton or Proton GE binary is bundled. Some games also need appropriate optional
32-bit libraries.

These controls apply to games launched through the wrapper. They do not provide
universal game detection, CPU governor/EPP policy controls, automatic
NVIDIA/Optimus GPU switching, accepted VRR behavior or an FPS guarantee. Actual
launcher downloads, account login, graphics drivers, anti-cheat compatibility and
games require their own runtime tests.

Husk Store and the native **`.hpk`** package format remain planned. `.hpk` is the
chosen extension; no functioning parser, signer, native installer, repository or
graphical store is claimed. A maintained signed Husk repository and durable
signing-key lifecycle are also required before an installable release can promise
ongoing Husk component updates. Calamares source remains experimental and has no
accepted System 2 permanent-installation result.

# A clean base and optional applications

System 2 development profiles contain Husk Desktop, Husk Settings, Labwc,
terminal/file utilities, the kernel, firmware, graphics libraries and essential
network/audio/storage/recovery tools. Neither live edition nor any installer
desktop choice automatically adds the historical gaming application bundle.
Flatpak is retained as installation infrastructure, not as an installed game
launcher. Native and, in the standard edition, 32-bit graphics libraries remain.

Steam, Proton, Wine, Lutris, Discord, Firefox, OBS and other optional user
applications are not default packages. Curated Start/taskbar entries are
installation entry points: if an application is absent, Husk asks the user
before opening its installer. The desktop does not install applications at
startup and does not require an Internet connection to show the desktop,
open local files or use its terminal/settings.

The following existing helper is an explicit user action:

```bash
husk-install-app steam
husk-install-app heroic
husk-install-app lutris
husk-install-app discord
husk-install-app firefox
```

The Arch path uses the allowlisted privileged helper with a full
`pacman -Syu --needed` transaction. It retains package signature checks and
avoids partial system upgrades. Heroic uses the official HTTPS Flathub
repository description and user-level Flatpak installation with confirmation.
An existing Flathub remote with an unexpected URL or disabled GPG verification
is refused before any change. No AUR recipes, arbitrary download-and-run
scripts, or disabled signature checks are added.

Settings exposes the existing Arch system update action. User Flatpaks can
be updated with `flatpak --user update`. Let Steam install/manage its own
supported Proton versions after Steam is installed; no Proton/Proton GE binary
is bundled into the base. Actual application downloads, signature transactions,
Steam/Proton and games need separate network/runtime testing. The current tests
verify installation command contracts, not a completed game installation.

The build profile reviews inherited Archiso recovery packages explicitly and
stops on unreviewed upstream additions. The installed rootfs checker also
reads pacman's actual package records, including dependencies, and rejects
known optional applications. This check must run against the next real build;
generated-profile and fixture tests alone cannot establish ISO contents.

Husk Store and the native `.hpk` package format remain planned. `.hpk` is the
chosen extension; no working `.hpk` parser, signer, installer, repository or
graphical store is claimed. Those need their own specification and validation.
The Calamares source remains experimental and has no System 2 install acceptance
test. A maintained signed Husk package repository/key lifecycle is also required
before an installable release can promise ongoing Husk component updates.

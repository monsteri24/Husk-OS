# Husk OS System 2 completion brief

User-authorized recovery and completion of the existing project, starting at
`e6595eae660afa6eafdbc4511a95fd6ae86dc1cb`. Preserve all history, Husk Desktop,
Labwc, black-and-gold branding, the exact official wallpaper and System 1 release.

## Acceptance

- English is the default; Finnish (`fi-FI`) is explicitly selectable using gettext.
- Start/search, launchers, Files, Settings, taskbar, window controls and shortcuts
  have bounded real GTK/Wayland interaction checks with preserved failure logs.
- Confirm/Cancel buttons cannot overlap or consume one another's pointer release.
  An optional application transaction uses existing trusted sources and reports
  actual failure or verified installation; cancelled authorization is failure.
- No Steam, Proton, Wine, Lutris, Heroic, Firefox or optional everyday apps are
  preinstalled. Essential desktop, terminal, Files, Settings, networking, drivers
  and authenticated package infrastructure remain usable offline.
- Build a real Archiso ISO, verify its rootfs, boot it with QEMU/OVMF, and publish
  `HuskOS-system-2.iso` plus SHA-256, notes and evidence in a separate experimental
  `system-2` pre-release. Never modify or delete System 1 assets.
- English documentation distinguishes live boot from permanent installation.
  Calamares source alone does not establish a working permanent installer.
- Save completed milestones to GitHub frequently and verify the remote ref.
  No false completion, boot, hardware, installation or download claims.

## Implementation approach

Keep current modular Python/GTK desktop and existing signed Arch packaging.
Repair existing flows without introducing another desktop, store or package format.
Use independent localization and installation work streams; coordinate packaging
and shared files. Extend the existing bounded compositor and UEFI test harnesses.
Use an ephemeral privileged Arch container only on a disposable Actions runner.
Release only after source, desktop and resulting ISO acceptance gates pass.

## Evidence boundaries

Automated source/GTK/Wayland tests, full ISO VM boot and physical hardware are
separate categories. The user-reported System 1 ASUS ROG boot proves no System 2
hardware acceptance. Real optional application downloads require their own test.

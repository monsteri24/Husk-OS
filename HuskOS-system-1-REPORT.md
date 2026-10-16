# Husk OS System 1 — build and release verification, 2026-10-16

## Delivered ISO

- Download: https://github.com/monsteri24/Husk-OS/releases/download/system-1/HuskOS-system-1.iso
- Release: https://github.com/monsteri24/Husk-OS/releases/tag/system-1
- Source commit: `8b0ac0b32dc60fc00bbef261acddc3414ce02a52`.
- Exact size: **2,103,050,240 bytes**.
- SHA-256: `8f14dc313556db9e56fb37a0ce3ef33f2d46cf35200238fb61a3b6240c856363`.
- GitHub ISO asset ID: `646339649`; state `uploaded`.
- Build/publication run: https://github.com/monsteri24/Husk-OS/actions/runs/38859335619

## Independently recorded outcomes

| Check | Result | Evidence |
|---|---|---|
| Source saved before build | PASSED | Remote source content and main ref verified before build request |
| Signed Husk packages/repository | PASSED | makepkg, repo-add and gpgv; signatures remained required |
| Real Archiso ISO creation | PASSED | mkarchiso success; ISO9660, HUSK_20261016, El Torito UEFI |
| Kernel/initramfs/live SquashFS | PASSED | Actual ISO file listing, not just profile configuration |
| Installed Husk/GTK/kernel/firmware payload | PASSED | check-rootfs.py against the populated mkarchiso filesystem |
| GitHub Release upload | PASSED | Release asset uploaded; size and server SHA-256 matched |
| Download verification | PASSED | A fresh complete download matched SHA-256; VM job also rechecked it |
| UEFI -> Linux -> rootfs -> live user | PASSED | First actual QEMU/OVMF CD-ROM boot, guest UID 1000 and live evidence |
| TTY2 keyboard and virtual Ethernet/NAT | PASSED | Real injected console command downloaded a probe and posted guest logs |
| Automatic Labwc/Husk Desktop acceptance | PASSED | Second VM run, actual Wayland GetStatus and husk-live-smoke exit 0 |
| Start menu and taskbar | PASSED (limited) | D-Bus toggle exit 0 and actual screenshots; mouse clicking not tested |
| Desktop terminal | PASSED | Super+Return opened Foot; actual screenshot inspected |
| Orderly shutdown | PASSED | ACPI power request; guest/QEMU exited normally with code 0 |
| Physical GPU/input/audio/Wi-Fi/controllers | NOT TESTED | No physical machine tests |
| Games/FPS, installer and installed-system reboot | NOT TESTED | This is the lightweight Live edition without Calamares |

## Source fixes and failure record

The existing checkpoint/desktop was retained. Seven command symlinks damaged
by the earlier Git API restoration were restored to their original `own.py`
target, preserving Git symlink modes. The first-boot edition uses standard
tty1 login/PAM to start Husk/Labwc; gaming profiles retain SDDM. TTY2 remains
an independent unprivileged live rescue console. Installer cleanup removes
the new live-only login hook. No physical disks were attached or modified.

Build attempt 1 stopped before ISO construction: Arch container GTK preview
aborted in the glycin/bwrap SVG image loader. Its underlying sandbox failure
was not bypassed. GTK preview regression runs on the supported Ubuntu/Xvfb
host; actual Arch/Wayland acceptance is a separate VM test.

Build attempt 2 built and verified Husk packages but stopped when pacman-key
could not locally sign the repository key: the official container had no
local pacman secret key. Normal `pacman-key --init` in the disposable build
container fixed this. Attempt 3 built and published the ISO successfully.

First boot acceptance run:
https://github.com/monsteri24/Husk-OS/actions/runs/38860056918
used QEMU TCG, OVMF, and the actual ISO as CD-ROM. Linux mounted `/dev/sr0`
and the SquashFS on `/dev/loop0`. Live/PAM login and the rescue console
worked. The harness switched to tty2 too early and left it active, while
Labwc on tty1 logged `Timeout waiting session to become active` and
`Failed to start a DRM session`. Desktop acceptance **FAILED** and shutdown
was **NOT TESTED**. This failed run has not been relabelled as a pass.

The harness now restores tty1 in `finally`, even after a diagnostic input
failure, and gives TCG boot time before probing. Both new regression tests
were seen failing before the fix and passing afterwards. The ISO was not
rebuilt or replaced for this test correction.

Second boot acceptance run:
https://github.com/monsteri24/Husk-OS/actions/runs/38861414136
**PASSED** on QEMU TCG/OVMF using the same downloaded release ISO, without
manually launching Husk Desktop. `husk-live-smoke` exited 0; status reported
`backend=wayland`, `panel_visible=true`, `panel_mapped=true`,
`bridge_connected=true`, `desktop_surfaces=1`, and `keyring_ready=true`.
The actual screens show the UEFI menu, Husk Desktop/Start/taskbar, and Foot
opened via its keyboard shortcut. ACPI-requested shutdown completed normally.
This is one virtual hardware configuration, not physical hardware certification.

Preserved results: [boot-result.json](docs/evidence/system1/boot-result.json),
[actual desktop/Start screenshot](docs/evidence/system1/desktop-start.png),
[actual terminal screenshot](docs/evidence/system1/desktop-terminal.png),
and [actual UEFI menu](docs/evidence/system1/uefi-menu.png).
These are QEMU screen captures; no generated/mock desktop image was used.
Original successful evidence artifact SHA-256:
`5f264de6ffe00fa543369664df66a45980db6bef96e267f661d4af0a329a4c5d`.

## Automated regression scope

The ISO source had 122 tests: 114 passed / 8 GUI skipped in headless mode;
Ubuntu GTK/Xvfb ran all 122 successfully. Adding harness regressions raised
the source suite to 124: local headless run 116 passed / 8 GUI skipped, and
101 source/configuration syntax checks passed. GitHub's corresponding
GTK/Xvfb workflow completed successfully. Xvfb is not Wayland acceptance.

## Remaining release limits

Boot acceptance passing does not mean the log is clean. Switching VTs
temporarily removes the monitor; `shell.py:124` logged
`TypeError: Argument 1 does not allow None as a value` in `monitors_changed`.
The desktop recovered and passed the live check, but this remains a real bug.
Labwc also reported transient DRM permission/CRTC errors during the VT switch.
The older `<snapping><range>` setting is deprecated. The intended CSS background
renders black, and some launcher/taskbar icons show missing-image placeholders.
Start includes a Steam entry although Steam is not installed in the light ISO.
The live journal also records a failed `systemd-loop@...sr0.service`/pktsetup
attempt; the actual SquashFS mount and desktop still succeeded.

Mouse clicking, window dragging, settings UI interaction, audio, public guest
Internet access, reboot, suspend, persistence and installation were not tested.
The tests verified virtual console keyboard input, a desktop terminal shortcut,
and guest-to-host networking; they do not establish all input or network support.

This is an experimental Live image with Husk Desktop, Labwc, Foot, Husk
Files, NetworkManager, PipeWire and the preserved settings/control center.
Large gaming additions and Calamares are omitted; their source and future
installation paths remain in Git. No game compatibility or performance is
claimed. The build uses an ephemeral development package key (one-day
validity); durable distribution signing/update keys need a separate release
process before this becomes an installable, maintained system.

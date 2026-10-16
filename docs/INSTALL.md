# Download, USB boot and installation status

**System 2 is development source, with no published ISO or release as of
2026-10-16.** Its new graphical tests, ISO build and QEMU/OVMF acceptance are
pending. The [Releases page](https://github.com/monsteri24/Husk-OS/releases) and
[System 2 report](../HuskOS-system-2-REPORT.md) are the places to check for a
later verified image. Do not treat a source archive or a successful unit test
as a bootable release.

The existing [System 1 release](https://github.com/monsteri24/Husk-OS/releases/tag/system-1)
is a preserved experimental Live image. Its [original report](../HuskOS-system-1-REPORT.md)
records an actual QEMU/OVMF desktop boot and the known limits. Instructions below
explain Live use; they do not describe a completed permanent installer.

## Target and reference environment

Husk OS targets **x86_64 PCs with UEFI**. The recorded automated boot reference
uses **4 GiB RAM and 2 virtual CPUs** with QEMU/OVMF. This is a test configuration,
not a measured minimum for a physical PC. Device-specific graphics, Wi-Fi,
audio, controllers, suspend and multi-monitor behavior require separate testing.
Secure Boot is not an accepted feature of this experimental image; the VM
reference uses ordinary OVMF firmware without Secure Boot.

Start with a disposable VM. A Live boot does not require an internal installation
disk. Keep important files backed up before experimenting with removable media
or operating-system installation tools.

## Download and verify an existing release

1. Open the [Releases page](https://github.com/monsteri24/Husk-OS/releases) and
   choose a release that actually has an ISO, matching checksum file and report.
   Currently that is the historical System 1 image, not System 2.
2. Download the ISO and checksum from the same release. For System 1 these are
   [HuskOS-system-1.iso](https://github.com/monsteri24/Husk-OS/releases/download/system-1/HuskOS-system-1.iso)
   and [HuskOS-system-1-SHA256.txt](https://github.com/monsteri24/Husk-OS/releases/download/system-1/HuskOS-system-1-SHA256.txt).
3. Verify the complete download before writing or booting it. In a Linux terminal,
   with both files in the current directory:

   ```sh
   sha256sum -c HuskOS-system-1-SHA256.txt
   ```

   In PowerShell, compute the digest and compare all 64 hexadecimal characters
   with the matching release checksum:

   ```powershell
   Get-FileHash .\HuskOS-system-1.iso -Algorithm SHA256
   ```

4. For the preserved System 1 image, the size is **2,103,050,240 bytes** and SHA-256
   is `8f14dc313556db9e56fb37a0ce3ef33f2d46cf35200238fb61a3b6240c856363`.
   Stop if either differs. A future System 2 image must have its own published
   checksum; never use the System 1 digest to verify a different image.

## Write a USB image

**Image writing erases the selected USB device, including its existing partitions
and files. Check its model and capacity carefully.**

1. Use an empty or backed-up USB device large enough for the selected ISO.
2. Open a disk-image writing utility, select the verified ISO as the source,
   and select that USB device as the destination.
3. Write the ISO as a complete disk image. Copying the ISO file onto an ordinary
   USB filesystem does not perform this operation.
4. Wait for writing and any verification to finish, then safely eject the device.
5. Use the computer's boot menu to select the USB's UEFI entry, then choose the
   Live boot entry. Firmware menu names vary by machine.

A successful USB write does not prove the machine's hardware is supported. The
System 1 automated evidence is a VM boot; System 2 USB/hardware acceptance is
still pending.

## Use the Live session

The first-boot profile logs in as the unprivileged **`live`** user through
TTY1/PAM and starts Labwc/Husk Desktop. TTY2 is a separate rescue console.
The Live root account is locked. Use the running user's actual home directory,
`$HOME`, for files and settings; do not assume a differently named home path.

The desktop, terminal, Settings and local file browsing are intended to remain
usable offline. Use the taskbar's Network action to configure a connection when
needed. Optional application downloads and full system updates require Internet
access. Physical network and audio devices have no System 2 acceptance result yet.

Live changes, installed applications and any temporary password normally disappear
at shutdown. No persistent-USB setup is provided by this guide. Save files you
need to separate persistent storage before leaving the session.

English is the default Husk interface language. Select **Settings → Appearance →
Interface language → Suomi (fi-FI)** for Finnish. The desktop reloads its controls;
reopen Settings, Files and other Husk applications for the full change. Keyboard
layout is separate under **Input**. See [localization](LOCALIZATION.md).

| Shortcut | Action |
|---|---|
| Super+Space | Open or close Start |
| Super+E | Open Husk Files |
| Super+I | Open Husk Settings |
| Super+Return | Open Foot terminal |
| Super+Left / Super+Right | Snap the active window |
| Super+Up / Super+Down | Maximize / minimize |
| Alt+Tab | Switch windows |
| Alt+F4 | Close the active window |

The lock action is disabled in Live. Setting a temporary administrator password
for an application transaction does not enable Live-session locking.

## Install an optional application on demand

These steps describe the current System 2 source behavior. **A real Live GUI
administrator-authentication and network-install transaction has not yet been
accepted.** The separate build-container application test does not prove that path.

1. Open Start and search for a curated application such as Firefox, Steam,
   Heroic, Lutris or Discord. Activate the matching row. An already installed
   application launches directly.
2. For an absent application, read the installation dialog. Choose **Cancel** to
   stop, or deliberately press and release **OK** to start. The dialog requires
   fresh input so that the launcher's earlier release cannot confirm it.
3. Read the Foot terminal that opens and remains open after the command finishes.
   For a native application in a fresh Live session, it asks you to set a
   temporary password for the `live` account using `passwd`'s interactive prompts.
4. Complete the separate administrator authorization dialog with that password.
   Native installation still requires administrator authentication; setting the
   password does not itself approve the package transaction. Installed systems
   use their normal administrator credentials. Heroic's per-user Flatpak path
   does not use this native Live-password setup.
5. Review the package-manager proposal and confirm it deliberately. Native
   installation performs a full `pacman -Syu --needed` transaction, which may
   include dependencies and system updates. Heroic uses user-level Flathub
   installation with Flatpak's own confirmation.
6. Read the terminal's final result. Success requires an installed package/app
   record, not merely a zero exit status. Cancelled authorization, declined or
   failed installation, and an unverified result must not be treated as success.
7. After verified success, select the application in Start again to launch it.
   Close the held terminal when you have finished reading it.

See [application installation](APP-INSTALLATION.md) for trusted sources, available
helpers and gaming-tool limitations.

## Permanent installation and updates

**There is no completed graphical operating-system installer in the current
release candidate.** Calamares and the Husk Desktop/KDE/GNOME/Minimal choices
remain experimental source. The default first-boot Live build omits Calamares.
A custom `--with-installer` build is not evidence of successful partitioning,
installation or an installed-system reboot. Do not use this guide to replace an
existing operating system; installation acceptance belongs on disposable virtual
disks first. See the [build guide](BUILD.md) and [VM checklist](VM-TESTING.md).

Settings exposes a full Arch system-update action with normal authentication and
package confirmation. Automatic rollback and Btrfs snapshots are not implemented.
A maintained signed Husk update repository and durable signing-key lifecycle
remain planned, so this experimental Live work is not a promise of ongoing
installed-system updates.

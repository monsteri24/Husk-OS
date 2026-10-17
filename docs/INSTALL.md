# Download, USB boot and installation status

Husk OS is an experimental Arch-based gaming operating system with its own GTK
Husk Desktop on Labwc/Wayland. **System 2 was published on 2026-10-17 as an
experimental Live USB/VM release.** It has no completed permanent graphical
operating-system installer.

The [System 2 release](https://github.com/monsteri24/Husk-OS/releases/tag/system-2)
contains the actual ISO, checksum and automated evidence. The exact image passed
filesystem validation and a QEMU/OVMF UEFI boot to the English desktop, real Foot
terminal launch and clean shutdown. See the [verification report](../HuskOS-system-2-REPORT.md).
Physical System 2 hardware acceptance remains outstanding.

The historical [System 1 release](https://github.com/monsteri24/Husk-OS/releases/tag/system-1)
and its [report](../HuskOS-system-1-REPORT.md) are preserved as a separate recovery
baseline. Its checksum is different; always use the matching release files.

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

## Download and verify System 2

1. Open the [official System 2 release](https://github.com/monsteri24/Husk-OS/releases/tag/system-2).
2. Download [HuskOS-system-2.iso](https://github.com/monsteri24/Husk-OS/releases/download/system-2/HuskOS-system-2.iso)
   and [HuskOS-system-2-SHA256.txt](https://github.com/monsteri24/Husk-OS/releases/download/system-2/HuskOS-system-2-SHA256.txt)
   from that release. A source archive is not a bootable ISO.
3. Verify the complete download before writing or booting it. With both files
   in the current directory on Linux:

   ```sh
   sha256sum -c HuskOS-system-2-SHA256.txt
   ```

   In PowerShell, compute the digest and compare all 64 hexadecimal characters
   with the matching release checksum:

   ```powershell
   Get-FileHash .\HuskOS-system-2.iso -Algorithm SHA256
   ```

4. The exact ISO size is **2,101,264,384 bytes**. Its SHA-256 is
   `d36214faecce244cf5c92e0730849857821499cae4f20c3bd71f2448952e8f99`.
   Stop if the size or checksum differs.

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
System 2 automated evidence is a VM boot; physical USB/hardware acceptance is
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

System 2 supports **English only**. Finnish is postponed and is not selectable;
earlier saved Finnish choices and Finnish host locales fall back to English.
Keyboard layout remains a separate setting under **Input**, including the Finnish
layout. See [localization](LOCALIZATION.md).

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

The release contains this application workflow; its dialogs passed actual GTK
and Labwc input tests, and a separate signed Firefox installation/headless launch
passed in Arch CI. **A real Live GUI
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
System 2 Live release.** Calamares and the Husk Desktop/KDE/GNOME/Minimal choices
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

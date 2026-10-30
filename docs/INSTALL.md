# Download, USB boot and installation status

<a name="v3-first-lenovo-hardware-test--live-only-2026-10-27"></a>

## V3 first ASUS ROG hardware test — Live only (2026-10-30)

This section applies to the **unpublished V3 candidate**, not the historical
System 2 download below. The user corrected the target on 2026-10-30: it is an
**ASUS ROG with an RTX 3070 Laptop GPU**, not a Lenovo. The exact model/CPU,
Wi-Fi chip, display routing/MUX and storage
controller are still unknown. Physical compatibility is **NOT TESTED**. See
[current hardware assessment](HARDWARE-COMPATIBILITY.md) and [V3 status](V3-PHASE2-STATUS.md).
Do not run the installer during this first test. The guarded UEFI USB
boot path passed [VM acceptance](https://github.com/monsteri24/Husk-OS/actions/runs/40524446117)
with disposable NVMe/AHCI disks, zero final write/unmap/failure counters and
unchanged complete disk hashes through normal shutdown. This remains VM proof.

**Current decision: preflight only; physical boot is not yet approved.** The
ASUS model, UEFI/Secure Boot state and internal storage controllers still need
verification. No new runtime defect has been demonstrated and no ISO rebuild
is justified by the manufacturer correction. Obtain the user's explicit
confirmation before physical testing or writing/booting the test USB. These
instructions alone are not that confirmation.

### Before writing or booting

1. Back up important Windows files. Confirm that you can access your own
   BitLocker/device-encryption recovery information privately if encryption is
   enabled, before changing
   boot media. Never post a recovery key in an issue or diagnostic report.
   [Microsoft documents boot-order changes as a recovery trigger](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/faq).
2. Record the exact ASUS ROG model code, BIOS version, **BIOS Mode = UEFI** and
   current Secure Boot state from Windows System Information (`msinfo32`).
   **If BIOS Mode is not UEFI or Secure Boot is enabled or unknown,
   STOP.** This candidate has no accepted Secure Boot signing/trust chain.
   This procedure does not disable Secure Boot, suspend/decrypt BitLocker,
   clear the TPM, enroll keys, or change firmware settings.
3. Read-only PowerShell inventory can help identify the hardware:

   ```powershell
   Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model
   Get-CimInstance Win32_VideoController | Select-Object Name,PNPDeviceID
   Get-Disk | Select-Object Number,FriendlyName,BusType,Size,IsBoot,IsSystem
   Get-CimInstance Win32_PnPSignedDriver |
     Where-Object { $_.DeviceClass -in @('SCSIAdapter','HDC') } |
     Select-Object DeviceName,InfName,DriverProviderName
   ```

   The controller/driver output is needed as well as disk bus labels. This is
   read-only inventory, not permission to change drivers. If the command fails
   or the disk-to-controller mapping is unclear, STOP and review the exact
   model/output. Check device-encryption/BitLocker status separately in Windows;
   `manage-bde -status C:` is a read-only alternative when permitted. Do not use
   `-off`, `-disable`, unlock or repair commands. Never send a recovery key.

   Continue only after confirming that **all internal disks use standard NVMe
   or SATA/AHCI**. RAID/VMD, eMMC, internal USB, unknown controllers or ambiguous
   inventory require separate assessment first. A SATA bus label alone does
   not prove AHCI mode. Do not change RAID/AHCI/MUX settings to pass this check.
4. After the preflight has been reviewed and the user has confirmed the physical
   test, disconnect other removable storage. Choose one spare USB stick and positively
   identify its model/capacity. Writing the image erases **that USB only**;
   never choose an internal disk. **Complete the size/hash checks below before
   writing.** Then use the image writer's complete-disk/raw-image
   mode and verification, not file copying. Do not accept Windows prompts to
   initialize, format or repair the resulting Linux USB.

Download `HuskOS-v3-phase2.iso` from the existing
[candidate artifact](https://github.com/monsteri24/Husk-OS/actions/runs/40172519876/artifacts/12590858411)
(GitHub sign-in may be needed; expires **2026-11-01 09:43 Europe/Helsinki**,
07:43 UTC). Extract the ZIP.
This is a temporary development artifact, not a V3 release. Verify **both**:

- ISO bytes: **2,080,997,376**
- ISO SHA-256: `496bd1508307d3ac6d7affff0e813b64ad8517d680ec0edd4dd2a447b512e715`

```powershell
(Get-Item .\HuskOS-v3-phase2.iso).Length
Get-FileHash .\HuskOS-v3-phase2.iso -Algorithm SHA256
```

Stop on an expired/missing artifact or any mismatch. Do not substitute a source
ZIP, older image or an unverified rebuild. Existing VM tests reused this exact
runtime (`96a0a02`) after integrity checks.

### One-time guarded UEFI USB boot

After confirmation, keep AC power connected and fully shut down the ASUS.
**Hold Esc, press the power button, and release Esc when the one-time boot
menu appears**, as described in [ASUS's official boot-menu instructions](https://www.asus.com/global/support/faq/1013017/).
Select the USB's UEFI entry. If the menu or USB entry does not appear, STOP and
check the exact ROG model's manual; do not apply firmware workarounds.
Only the one-time hotkey/menu portion of that ASUS article applies here, not
its optional format, Fast Boot or Secure Boot changes. Do not reformat the
raw-written hybrid ISO or alter the permanent boot order.

The candidate uses **systemd-boot**. Repeatedly press **Space** during USB
startup to display its menu. Select `Husk OS live (x86_64, UEFI)`, press **e**,
then **End**. Preserve the existing line and append one space followed by:

```text
module_blacklist=nvme,ahci,vmd initcall_blacklist=ahci_pci_driver_init noresume systemd.gpt_auto=0 rd.systemd.gpt_auto=0 systemd.mask=udisks2.service systemd.mask=swap.target rd.systemd.mask=swap.target
```

Check every character **before Enter**. The long line scrolls horizontally;
use Home and the arrow keys to review the entire line, not only its visible tail.
The editor uses a US keyboard layout;
Finnish physical keys for `=`, `_` and punctuation differ. If the edited line
cannot be verified, cancel the boot. **Enter** boots that edited entry once;
do not save a new default. [Official menu/editor keys](https://www.freedesktop.org/software/systemd/man/latest/systemd-boot.html).

This ISO has a built-in AHCI driver: module-only blocking failed the actual VM
test and must not be used. The extra initcall guard is essential. These options
block the known internal storage drivers for this boot, disable
resume/GPT auto-discovery and runtime-mask swap/UDisks. They deliberately make
internal NVMe/SATA drives unavailable. They are **not universal write protection
for every controller**. Never use the unprotected VM control configuration on
the laptop. Do not add `nomodeset` or force a different GPU/MUX for this test.

### First checks and diagnostics

The expected desktop runs as unprivileged `live` on Labwc/Wayland. Open Foot
with **Super+Return**. Before browsing disks or further testing, inspect:

```sh
cat /proc/cmdline
lsblk --tree -o PATH,TYPE,TRAN,MOUNTPOINTS
findmnt -n -o SOURCE,FSTYPE,OPTIONS /run/archiso/bootmnt
swapon --show
systemctl show udisks2.service --property=LoadState --value
```

Require the exact appended flags, only the boot USB disk and its partitions
(Live loop devices are expected), its `iso9660` read-only boot mount, no swap
rows, and `masked` for UDisks. **Any internal/extra/unknown disk, missing guard,
active swap or writable boot mount means STOP and power off.** Do not mount,
unlock, repair, format, benchmark or browse Windows/internal partitions.

The improved collector is a **standalone sidecar, not installed in this ISO**.
If Wi-Fi/Ethernet works, fetch the reviewed script into session RAM, verify its
digest, and run without sudo. Use a fresh output filename if one already exists:

```sh
cd "$XDG_RUNTIME_DIR" &&
curl -fL https://raw.githubusercontent.com/monsteri24/Husk-OS/96f3efeeed35bbafb40fc9f9ca273b27d2513b0d/scripts/collect-system-report.py -o husk-hardware-report.py &&
printf '%s  %s\n' d2f93e5f804032c65a1f2308e66353056694fa4ef211deb88047c94196804b84 husk-hardware-report.py | sha256sum -c - &&
python3 ./husk-hardware-report.py --live-usb --output "$XDG_RUNTIME_DIR/husk-live-hardware.json"
```

Run the last command **only if checksum verification succeeds**. It returns
nonzero and records `STOP` if required observations fail or are unavailable.
Reports are private mode 0600 and never replace an existing file. Optional
missing tools (for example `nvidia-smi`) are recorded, not treated as hardware
success. If the network/script is unavailable, retain the read-only observations
(a photo is enough), stop the automated test and power off; do not mount Windows
or add another storage device to retrieve the script. Review device identifiers
and personal names before sharing any diagnostics. RAM reports disappear at
shutdown; copy only chosen text through an already working network if desired.

After the safety checks, record each result separately: internal panel image
and native mode, keyboard letters/Fn keys, touchpad, USB mouse buttons/wheel,
Wi-Fi connection and DNS, and quiet speaker/headphone playback at low volume.
Do not infer audible sound from a detected sink. `lspci -nnk`, `wpctl status`,
`aplay -l` and `glxinfo -B` are detection aids; a software renderer is not NVIDIA
acceleration. Note renderer and PCI IDs, rather than guessing from a logo.
External displays, microphone, Bluetooth, Vulkan/Proton/games, suspend and long
soak testing are later tests. Do not install drivers, upgrade packages or set an
administrator password during this first run.

If the display stays black, Ctrl+Alt+F2 may reach the unprivileged rescue TTY;
record the observation without changing drivers. If neither desktop nor TTY is
usable, stop instead of improvising firmware/storage changes. For a responsive
session use `systemctl poweroff` and wait for complete power-off before removing
the USB. Then start Windows normally from its existing internal boot entry.
If Windows requests recovery, use your private recovery procedure; never select
format/reset/reinstall as part of this test. Record model/BIOS, ISO hash, boot
flags and each PASS/FAIL/NOT TESTED result. No hardware acceptance is claimed
until those physical observations exist.

## Preserved System 2 download and installation status

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

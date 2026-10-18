# Husk OS V3 Phase 2 — acceptance status

The development branch continues verified System 2 at `8a57d6c` without
replacing Labwc/GTK or modifying the System 1 and System 2 releases. Main is
unchanged. [Draft PR #1](https://github.com/monsteri24/Husk-OS/pull/1) is the
reviewable candidate. No V3 release has been published.

The source implements an authenticated graphical application-install flow,
separate network/DNS/repository diagnostics, official Steam/Heroic artwork,
libnm Wi-Fi controls, adapter-aware BlueZ/Blueman controls, the requested tray
order, persistent yellow accent/reset, desktop Trash with visibility control,
protected special icons, real file/context-menu actions and distinct
foreign-toplevel-driven maximized/fullscreen panel behavior. The wallpaper,
Husk-native application artwork and existing architecture are preserved.
English is the only active UI language.

The installer extends pinned Calamares 3.3.14/KPMCore. Its supported initial
mode is UEFI whole-drive erase only: no preselected drive, protected Live
media, kernel disk lifetime and topology checks, repeated verification, an
actual disk-change summary and separate destructive confirmation. It clones
the Live filesystem offline and requires real user, initramfs, GRUB, checked
filesystem flush and non-lazy unmount jobs before completion. Clock selection
resolves to IANA zones with DST; the installed keyboard layout/variant is
retained. The completion view provides the requested decreasing 30-second
countdown and Restart Later/Restart Now order.

## Completed evidence

| Check | Observed result |
| --- | --- |
| Source/models/real GTK | [39124770527](https://github.com/monsteri24/Husk-OS/actions/runs/39124770527) passed 423 tests with zero failures or skips in the actual GTK run at `6dd54d1`; 174 source/configuration checks also passed. |
| Local checks | 419 tests, zero failures, 69 explicit environment skips before the latest four harness regressions; 174 current source/configuration checks pass. Real Gio Trash, libnm profiles, compiled Qt clock/DST/completion behavior and strict native compilation were exercised. |
| Actual Labwc | [39122977898](https://github.com/monsteri24/Husk-OS/actions/runs/39122977898) passed at `1e2b159`, including normal panel pixels, maximized transparency/click-through, genuine fullscreen hide/restore, GTK window controls, menus, file navigation and app confirmation/Cancel. The same production code also passed the desktop job in [39124770527](https://github.com/monsteri24/Husk-OS/actions/runs/39124770527), using the latest compositor focus evidence. |
| Real application packages | [39123974007](https://github.com/monsteri24/Husk-OS/actions/runs/39123974007) passed: the shipped root helper, real DNS/repository preflight and signed full-system transactions installed Firefox `158.0-1` and Steam `1.0.0.87-3` in a fresh disposable Arch container. Pacman confirmed both packages; Firefox executed its version command and Steam executable/official desktop artwork were checked. |
| Full V3 build | [39123206803](https://github.com/monsteri24/Husk-OS/actions/runs/39123206803) compiled the patched Calamares/backend, built signed packages and produced the actual ISO. Generic and V3 extracted-rootfs checks passed. |
| Live UEFI boot | The same exact ISO passed real OVMF Live startup, desktop evidence, terminal shortcut and safe ACPI shutdown. |
| Disk guard in Live | The real guard accepted the new `HUSK-DISPOSABLE` virtual disk and rejected the mounted Live optical medium. |

The latest ISO is preserved as an explicitly **unverified** Actions artifact:

- Source: `0ac564dbd141f00bcfd68503fbe75f9065041e51`
- Size: **2,214,559,744 bytes**
- SHA-256: `7597f76451ed19829e4e8b4fe6879d7ce11f95cee43901aa38ceae6fbedd6088`
- [ISO and checksum artifact](https://github.com/monsteri24/Husk-OS/actions/runs/39123206803/artifacts/12135396899)
- [Build/rootfs/Live-boot evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39123206803/artifacts/12135591545)

The completed image includes the normal panel painting, GTK clipboard callback
and popup outside-click fixes, explicit os-prober dependency and nonexpiring
public build certificate. Private signing material was confined to the
disposable runner. The older `c5ad77f` image remains preserved but is not the
current release candidate.

## Active acceptance and blockers

The first install attempt on this exact image stopped **before launching
Calamares**: the test fixture tried to flush an absent IPv6 default route and
iproute2 returned an error. The fixture now inspects each address family,
flushes only existing default routes and still fails if inspection fails or
external routes remain. Four regression tests cover this and stronger disk
operation evidence. The current recovery workflow verifies the exact ISO
hash/size and requires unchanged production sources before reusing it.

[39124770527](https://github.com/monsteri24/Husk-OS/actions/runs/39124770527)
continues the same image through the corrected real VM test. It may attach
only a newly created 32 GiB qcow2 without a backing file and read-only Live
media. Actual Qt pointer/keyboard input must select the target, IANA zone and
account, review and cancel before writes, then separately confirm a fresh
installation. Cancellation compares write, discard and flush counters plus
GPT-edge hashes. Success requires real backend completion, a decreasing
countdown, Restart Later surviving beyond 30 seconds, target filesystem/job
checks, safe shutdown and a second UEFI boot with **no ISO or kernel override**
into the newly created user's SDDM/Wayland desktop. These installation and
installed-boot gates have **not yet passed**.

A later parallel Labwc run exposed test input arriving before the compositor
returned pointer focus after Escape destroyed a popup. The harness now moves
the actual pointer and waits for observed GDK focus on Husk Desktop before
reopening; production menu behavior and assertions are unchanged. The latest
real Labwc run at `6dd54d1` passed with this focus check.

## Coverage limits

The VM input fixture uses a test-only root debug VT; it does not verify the
normal graphical polkit/PAM authorization or Live password dialog. The signed
package test also runs as an explicitly consented disposable root container;
it does not launch Steam or games. Restart Now and automatic-zero behavior
have real Qt logic tests, but their actual VM restart remains unverified.
Wi-Fi scanning/association, Bluetooth pairing, physical GPU/firmware behavior
and USB removal still need compatible hardware tests. Cross-filesystem Cut is
deliberately refused; Copy remains available and existing files are not
silently overwritten.

The local sandbox prevents Unix sockets, so actual Xvfb/Labwc and VM acceptance
runs in GitHub Actions. Local sanitizer checks disable leak detection because
the required process metadata is unavailable. Offscreen Qt and source checks
alone never imply ISO or installation success. Do not publish this candidate
as a working installer unless essential installation and installed UEFI boot
gates pass; report failures and hardware-dependent gaps explicitly.

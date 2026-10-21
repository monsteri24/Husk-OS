# Husk OS V3 Phase 2 — acceptance status

The development branch continues verified System 2 at `8a57d6c` without
replacing Labwc/GTK or modifying the System 1 and System 2 releases. Main is
unchanged. [Draft PR #1](https://github.com/monsteri24/Husk-OS/pull/1) is the
reviewable candidate. No V3 release has been published.
The current user instruction explicitly forbids publication, merging the PR,
changing main or deleting old releases. Passing acceptance does not authorize
a release.

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

## Verified acceptance

The existing corrected ISO passed the complete disposable-VM acceptance chain.
The final test source is 1e567c0; every installed runtime input still matches
image source c677d21. No ISO rebuild was needed during this continuation.

| Check | Actual result |
| --- | --- |
| Normal graphical launch | [39609995495](https://github.com/monsteri24/Husk-OS/actions/runs/39609995495): actual unprivileged GTK password setup, system PAM/polkit authorization, PID-bound root helper audit, private Xauthority and visible English UTF-8 Calamares Welcome; all ten checks and safe shutdown passed. No test-driver/policy injection. |
| Offline installation and first default login | [39449998340](https://github.com/monsteri24/Husk-OS/actions/runs/39449998340): all 30 jobs and all 19 target checks passed. SDDM already selected Husk Desktop; the controller did not choose a session. |
| Disk protection and Cancel | Every installation scenario protected the Live medium. Actual summary cancellation left zero QMP target data writes/unmaps and unchanged partition-edge hashes before installation was authorized. |
| Restart Later | The same corrected-image build observed 30 to 26, actual pointer input, process exit 0 and unchanged Live boot beyond the countdown interval. |
| Restart Now | [39613704162](https://github.com/monsteri24/Husk-OS/actions/runs/39613704162/artifacts/12352660922): actual click/request/stopped timer at 26, clean QMP guest-reset, then independent normal-user UEFI/Husk Wayland boot passed. |
| Automatic zero | [39620742691](https://github.com/monsteri24/Husk-OS/actions/runs/39620742691): every actual value 30,29,...,0 was recorded before the unchanged production reboot command. Clean QMP guest-reset and independent installed UEFI/Husk Wayland boot passed. |
| Installed isolation | Both actual restart scenarios booted their own installed disk without ISO, kernel override or debug console. UID 1000 used /dev/vda2 ext4 and a real local Wayland session, with connected native bridge and mapped desktop/panel. Original wallpaper/Home/Trash remain; Install Husk OS is absent. Safe installed shutdown passed. |
| Source/GTK | Final source passed 487 real GTK tests with zero skips, 181 syntax checks and native sanitizers in 39620742691. Local checks passed 487 with 71 explicit environment skips; local leak detection was disabled. The complete C++ test driver also compiled with warnings treated as errors. |
| Real Labwc | [39620752139](https://github.com/monsteri24/Husk-OS/actions/runs/39620752139): maximized transparency/click-through/launcher, genuine fullscreen hide/restore, controls, menus, navigation and confirmation/Cancel passed. |

The final desktop and completion screenshots were inspected. The independent
normal-user report confirms UEFI, no Live medium, no debug shell, Husk Wayland,
UID 1000 and the expected installed root. Installation tests used only new 32 GiB qcow2 disks;
no physical user disk was attached or modified.

## Exact existing ISO

- Runtime source: c677d2193a6cb542db9e3a60e8a1b91981b6fb17
- Size: **2,079,227,904 bytes**
- SHA-256: 14a42898997dd30dc5838d4f254da218c322e9bae132917fdafd0e3819a15aec
- [ISO and checksum artifact](https://github.com/monsteri24/Husk-OS/actions/runs/39449998340/artifacts/12279651558), retained until 2026-10-27
- [Build/Live/first default-login evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39449998340/artifacts/12280125234)
- [Final automatic/installed-boot evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39620742691/artifacts/12355561324)

The artifact retains its original UNVERIFIED filename. These are VM acceptance
results, not hardware certification or permission to publish a release.
System 1/System 2 releases and main remain unchanged; PR 1 stays a draft.

## Corrections and permanent evidence

The installed default now uses SDDM's absolute session filename, seeded only
when state is absent; remembered user choices and authenticated login remain.
The normal Live GTK/password/PAM/polkit path was verified separately from the
root-input installation fixture. Earlier Calamares display/locale/style and
scrollable-summary corrections were preserved and validated on the same ISO.

The completion test observer was corrected to distinguish expected XWayland
shutdown from an installation failure, require genuine guest-reset provenance,
and observe actual Qt property changes synchronously through zero. Restart Now
must take effect at positive seconds; an automatic fallback cannot pass as Now.
Production timer values and reboot commands were not changed for these tests.
The real compositor's confirmation test now waits for actual Cancel focus after
mapping. Failed scenarios are preserved and superseded by the passing evidence.

- [Consolidated machine-readable acceptance](evidence/v3-phase2/2026-10-21-final-acceptance.json)
- [Automatic countdown/reset/installed-boot trace](evidence/v3-phase2/2026-10-21-automatic-restart-acceptance.json)
- [Now trace](evidence/v3-phase2/2026-10-21-restart-now-acceptance.json)
- [Normal Live authorization](evidence/v3-phase2/2026-10-21-live-authorization.json)
- [First default installed session](evidence/v3-phase2/2026-10-20-default-session-acceptance.json)
- [Earlier evidence and failure diagnostics](V3-PHASE2-HISTORY.md)

## Remaining coverage

Physical Wi-Fi/Bluetooth adapters, GPU/firmware, actual USB removal and nonempty
real-hardware targets need independent testing. The VM renderer is pixman.
Normal graphical package authorization and Steam/Heroic/game launch remain
unverified. Earlier signed Firefox/Steam package transactions on an older ISO
are a narrower proof. The installer supports UEFI whole-drive erase only;
alongside installation is not implemented or advertised.

No V3 release has been published and no PR has been merged. The user's current
instruction continues to forbid publication, merging, changing main or deleting
previous releases, even though these acceptance checks passed.

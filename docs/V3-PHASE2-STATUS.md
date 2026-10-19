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
| Source/models/real GTK | [39249438444](https://github.com/monsteri24/Husk-OS/actions/runs/39249438444) passed its separate source/GTK job: 433 tests with zero failures or skips in the actual GTK run; 174 source/configuration checks also passed. The VM job in that run failed separately, as described below. |
| Local checks | Current source: 444 tests, zero failures, 70 explicit graphical/environment skips; 176 source/configuration checks and the native sanitizer check pass. Local leak detection is disabled as described below. New display tests cover private files, normal/error cleanup, symlink/hardlink rejection, secret-free failures and fixed-helper invocation; their actual GTK/X SECURITY test is deferred to Actions. |
| Actual Labwc | [39249438444](https://github.com/monsteri24/Husk-OS/actions/runs/39249438444) passed its separate desktop job, including normal panel pixels, maximized transparency/click-through, genuine fullscreen hide/restore, GTK window controls, menus, file navigation and app confirmation/Cancel. |
| Real application packages | [39246817254](https://github.com/monsteri24/Husk-OS/actions/runs/39246817254) passed using the current `0ac564d` ISO, on the day after its build. The shipped root helper, real DNS/repository preflight and signed full-system transactions installed Firefox `158.0-1` and Steam `1.0.0.87-3` in a fresh disposable Arch container. Pacman confirmed both packages; Firefox executed its version command and Steam executable/official desktop artwork were checked. [Result/log artifact](https://github.com/monsteri24/Husk-OS/actions/runs/39246817254/artifacts/12183189690) records the exact image digest and the authentication/game-testing limits. |
| Full V3 build | [39123206803](https://github.com/monsteri24/Husk-OS/actions/runs/39123206803) compiled the patched Calamares/backend, built signed packages and produced the actual ISO. Generic and V3 extracted-rootfs checks passed. |
| Live UEFI boot | The same exact ISO passed real OVMF Live startup, desktop evidence, terminal shortcut and safe ACPI shutdown. |
| Disk guard in Live | The real guard accepted the new `HUSK-DISPOSABLE` virtual disk and rejected the mounted Live optical medium. |

The latest completed ISO is preserved as an explicitly **unverified** Actions artifact.
It predates the installer startup fixes below and must not be published as a
working installer:

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

The current 2,214,559,744-byte image also exceeds GitHub's strictly-under-2-GiB
release-file limit ([GitHub documentation](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)).
The next installer build uses zstd level 15 with the same bounded two compression
workers and unchanged package selection, rather than the level-3 fast first-boot
profile. The build report records actual size eligibility and fails publication
eligibility when oversized, while preserving the candidate and diagnostics.
All 32 profile/integration tests pass, including package-payload preservation.
The smaller image has not yet been built. Build request attempt 4 includes the
startup fixes below and the same package selection. The earlier immutable
image remains useful as diagnostic evidence but cannot prove the new source.

Installation attempts on this exact image have stopped **before reaching
Calamares navigation**. [39248059460](https://github.com/monsteri24/Husk-OS/actions/runs/39248059460)
successfully reached the acknowledged root setup over the separate UART under
KVM and verified offline mode with no IPv4/IPv6 default routes. This resolves
the prior test-only `ip -6 route flush default` error. The fixture inspects
exact default routes as structured JSON and temporarily
sets NetworkManager's active device configuration to never provide IPv4/IPv6
defaults. It does not alter saved connection profiles or remove the connected
route to the evidence server. It independently requires no remaining external
unicast defaults, records before/after routes and propagates inspection or
NetworkManager errors. Regression tests cover absent IPv6 defaults, dual-stack
device deduplication, unreachable/link routes, malformed data and real failures.

The next blocker was Qt's X11 display authorization: the isolated root fixture
could not connect to the Live user's XWayland display. The disk still had zero
writes/discards/flushes and identical GPT-edge hashes, but reviewed GUI
cancellation did not occur. [39249438444](https://github.com/monsteri24/Husk-OS/actions/runs/39249438444)
then successfully supplied a private, user-owned Xauthority generated through
X SECURITY with a 120-second unused timeout, without changing the X server ACL
or the ISO. Calamares progressed past display initialization and exposed the
production startup-path error: `-c /etc/calamares` overrides the application
data root, so it fatally searched for `/etc/calamares/qml`. The pinned upstream
source normally reads `/etc/calamares/settings.conf` while loading QML from
`/usr/share/calamares/qml`. The wrapper also requested an unavailable
`en_US.UTF-8` Live locale and Qt fell back to `C.UTF-8`.

The new source removes the test-only `-c` override and explicitly uses the
built-in English `C.UTF-8` locale. The normal unprivileged GTK launcher now
prepares a private temporary Xauthority before calling the same restricted
pkexec helper, keeps it until that process exits and cleans it on success,
cancel or error. Administrator authorization remains required. This work runs
in a worker thread. Packaging and payload checks now require Xauth, the display
helper and installed Calamares QML, and reject the known incorrect startup
override. These source fixes require the new ISO build and real VM verification;
normal polkit/PAM authorization is still unverified.

The earlier recovery workflow verifies the exact ISO
hash/size and requires unchanged runtime sources before reusing it. The only
excluded source file is the build-only profile generator `ownos/build.py`;
its new compression is recorded separately and is not claimed to be present
in the reused image. Its strict runtime-source comparison correctly prevents
reusing that image as acceptance for the new installer startup source.

The older TCG run [39122974054](https://github.com/monsteri24/Husk-OS/actions/runs/39122974054)
expired without any guest setup report. Its captured screen showed boot still
in progress when the fixed-delay VT keyboard command was delivered. The new
test uses systemd's debug shell on a test-only serial socket, waits for a
random root/network acknowledgement and sends the setup exactly once. Missing
acknowledgement or execution now has a separate bounded failure. No test debug
options are passed to the second installed-system boot. The QEMU serial
transport has a real socket-pair regression; the Qt driver also records and
times out unexpected dialogs without inspecting password controls.

The first acknowledged-serial attempt at `808da74` then isolated another test
transport fault: boot/Plymouth traffic and the debug shell shared ttyS0, and
the captured log contains truncated shell input and a continuation prompt.
The test now leaves boot output on ttyS0 and uses a separate ttyS1 UART/socket
for setup, paces UART writes and can reset only the harmless readiness probe.
All 19 focused harness tests pass, including real socket I/O, port isolation,
input pacing, target isolation and installed-boot argument checks. Compatible
hosted runners also grant their own test account access to an existing KVM
device with mode 0600; runners without it retain TCG. These changes affect
only the disposable test environment, not the ISO or installed system.

The recovery workflow reuses the already-passed Live UEFI evidence for the
verified identical ISO instead of repeating that separate boot. The new
installation VM still has to reach real Calamares and the installed desktop.
The replaced fixed-delay run was superseded by this acknowledged test. It may attach
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
reopening; production menu behavior and assertions are unchanged. Subsequent
real Labwc runs, including `9b488ff`, passed with this focus check.

## Coverage limits

The VM input fixture uses a test-only root debug console; it does not verify the
normal graphical polkit/PAM authorization or Live password dialog. The signed
package test also runs as an explicitly consented disposable root container;
it does not launch Steam or games. Restart Now and automatic-zero behavior
have real Qt logic tests, but their actual VM restart remains unverified.
Wi-Fi scanning/association, Bluetooth pairing, physical GPU/firmware behavior
and USB removal still need compatible hardware tests. Cross-filesystem Cut is
deliberately refused; Copy remains available and existing files are not
silently overwritten.

The local sandbox prevents binding Unix listener sockets, so actual Xvfb/Labwc and VM acceptance
runs in GitHub Actions. Local sanitizer checks disable leak detection because
the required process metadata is unavailable. Offscreen Qt and source checks
alone never imply ISO or installation success. Do not publish this candidate
as a working installer unless essential installation and installed UEFI boot
gates pass; report failures and hardware-dependent gaps explicitly.

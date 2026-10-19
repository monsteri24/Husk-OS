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
| Source/models/real GTK | [39252514418](https://github.com/monsteri24/Husk-OS/actions/runs/39252514418) passed at `9b9f424`: 447 tests with zero failures or skips in the actual GTK run, including a real X SECURITY credential opening a GTK window and native-widget observer ownership; 176 source/configuration checks also passed. ISO/VM acceptance is separate. |
| Local checks | The last full local run passed 444 tests with 70 explicit graphical/environment skips, plus native sanitizer checks with local leak detection disabled. Current focused boot-proof/profile tests pass all 37 cases; Labwc harness tests pass with one explicit real-GTK skip. All 176 source/configuration checks pass. |
| Actual Labwc | [39252514315](https://github.com/monsteri24/Husk-OS/actions/runs/39252514315) passed after the observer correction, including taskbar restore, normal panel pixels, maximized transparency/click-through, genuine fullscreen hide/restore, GTK window controls, menus, file navigation and app confirmation/Cancel. The earlier parallel taskbar timeout is documented below. |
| Real application packages | [39246817254](https://github.com/monsteri24/Husk-OS/actions/runs/39246817254) passed using the current `0ac564d` ISO, on the day after its build. The shipped root helper, real DNS/repository preflight and signed full-system transactions installed Firefox `158.0-1` and Steam `1.0.0.87-3` in a fresh disposable Arch container. Pacman confirmed both packages; Firefox executed its version command and Steam executable/official desktop artwork were checked. [Result/log artifact](https://github.com/monsteri24/Husk-OS/actions/runs/39246817254/artifacts/12183189690) records the exact image digest and the authentication/game-testing limits. |
| Full V3 build | [39250972954](https://github.com/monsteri24/Husk-OS/actions/runs/39250972954) compiled the patched Calamares/backend, built signed packages and produced the startup-fixed ISO. Generic and stricter V3 extracted-rootfs checks passed. The job then correctly failed its release-size gate and preserved the image/evidence. |
| Live UEFI boot | The older `0ac564d` image passed real OVMF Live startup, desktop evidence, terminal shortcut and safe ACPI shutdown. The new `65b2085` image still requires its own boot test; old-image proof cannot substitute for it. |
| Disk guard in Live | Earlier real tests accepted only the new `HUSK-DISPOSABLE` virtual disk and rejected the mounted Live optical medium; this must also pass on the rebuilt image. |

The latest completed ISO is preserved as an explicitly **unverified** Actions artifact.
It contains the startup fixes below, but still needs real boot/installation
acceptance and is too large for a release file:

- Source: `65b20855fa919a447989cd932134f63493d2f18f`
- Size: **2,147,778,560 bytes**
- SHA-256: `1228919a759373a40aec227b24517264219450842bf290914a4c4727cb0af604`
- [ISO and checksum artifact](https://github.com/monsteri24/Husk-OS/actions/runs/39250972954/artifacts/12185574285)
- [Build/rootfs evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39250972954/artifacts/12185589502)

The completed image includes the normal panel painting, GTK clipboard callback
and popup outside-click fixes, installer display/startup corrections, explicit os-prober dependency and nonexpiring
public build certificate. Private signing material was confined to the
disposable runner. The older `c5ad77f` image remains preserved but is not the
current release candidate. The previous `0ac564d` image and its
[successful Live-boot evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39123206803/artifacts/12135591545)
remain preserved for diagnostic history.

## Active acceptance and blockers

The current 2,147,778,560-byte image exceeds GitHub's strictly-under-2-GiB
release-file limit ([GitHub documentation](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)).
Zstd level 15 reduced the previous image by 66,781,184 bytes, but this is still
288 KiB above the cap. The next build is configured for level 19 with the same
two compression workers and unchanged package selection; all 32 profile tests
pass, including payload preservation. Level 19 has not yet been built. The
build report correctly blocked publication and preserved the completed image.
The recovery workflow now pins this new exact image and runs its first Live
UEFI and disposable installation tests before another lengthy build. Missing
prior boot evidence requires a fresh real boot; mismatched/failed evidence is
rejected. Three new regressions cover that proof-reuse decision.

Earlier installation attempts on the `0ac564d` image stopped **before reaching
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
override. These source fixes are included in the new `65b2085` ISO but still
require real VM verification;
normal polkit/PAM authorization is still unverified.

The recovery workflow verifies the exact ISO
hash/size and requires unchanged runtime sources before reusing it. The only
excluded source file is the build-only profile generator `ownos/build.py`;
its new compression is recorded separately and is not claimed to be present
in the reused image. Its strict runtime-source comparison requires identical
installer/desktop sources; only the build-only level-19 profile change is
excluded and separately recorded when testing the level-15 image.

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

At `65b2085`, the standalone Labwc run passed while the build workflow's
parallel desktop job timed out on one taskbar restore. Its captured GTK log
showed 257 copies of one release callback: weak Python-wrapper tracking had
reconnected observers while GTK still owned the native widget. The observer
now tracks the native GObject identity until destroy without retaining dead
wrappers, and records real button activation separately. The taskbar test
waits for a fresh compositor pointer enter and actual GTK button hover before
its single click, retaining the original restore/active assertions. Focused
harness checks pass; the real GTK ownership regression and subsequent real Labwc
run passed with this correction. No production desktop code or current ISO
payload changed for this test-harness correction.

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

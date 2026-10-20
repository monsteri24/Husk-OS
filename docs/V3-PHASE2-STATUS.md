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

## Completed evidence

| Check | Observed result |
| --- | --- |
| Source/models/real GTK | [39256344428](https://github.com/monsteri24/Husk-OS/actions/runs/39256344428) passed at `8bf2df4`: 454 tests with zero failures or skips in the actual GTK run; 176 source/configuration checks and native sanitizer checks also passed. ISO/VM acceptance is separate. |
| Local checks | The last full local run passed 454 tests with 71 explicit graphical/environment skips, plus native sanitizer checks with local leak detection disabled. The current focused installer-input/orchestration suite passes all 25 tests, including a real styled Qt combo popup regression. All 176 source/configuration checks pass. |
| Actual Labwc | The same `8bf2df4` run passed taskbar restore, normal panel pixels, maximized transparency/click-through, genuine fullscreen hide/restore, GTK window controls, menus, file navigation and app confirmation/Cancel. |
| Real application packages | [39246817254](https://github.com/monsteri24/Husk-OS/actions/runs/39246817254) passed using the older `0ac564d` ISO, on the day after its build. Signed root-container transactions installed Firefox `158.0-1` and Steam `1.0.0.87-3`. This does not prove graphical authentication or Steam/game launch. |
| Full V3 build | [39256344428](https://github.com/monsteri24/Husk-OS/actions/runs/39256344428) compiled patched Calamares, built signed packages and produced the branding-fixed ISO. Generic/V3 extracted-rootfs checks and the file-size gate passed. The later installation test failed as described below. |
| Live UEFI boot | That exact `8bf2df4` ISO passed real OVMF Live startup, Wayland desktop evidence, terminal shortcut and safe ACPI shutdown. |
| Calamares UI | Actual Qt navigation reached Welcome, English (US) keyboard selection and the clock-based location page. The real screenshot shows the Husk installer window. The input driver then failed to select the regional combo row; no installer job queue ran. |
| Disk guard in Live | The new run accepted the disposable target and rejected the Live optical medium. Written/discarded sectors remained zero and GPT-edge hashes matched. A zero-sector flush incremented raw write/flush operation counters; those are recorded rather than described as all-zero. |

The latest completed ISO is preserved as an explicitly **unverified** Actions artifact.
It includes the required branding maps and existing artwork, passed payload
validation and Live UEFI boot, and fits the file-size limit. Installation and
independent installed boot remain unaccepted:

- Source: `8bf2df4eaa297747b30de5aa34c41d682e512843`
- Size: **2,079,227,904 bytes**
- SHA-256: `8d06e8f62e55d8157c703cdd9b103e9e0d12b12bccc892a9ed05ce5088068ed2`
- [ISO and checksum artifact](https://github.com/monsteri24/Husk-OS/actions/runs/39256344428/artifacts/12189701056)
- [Build/Live/installer evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39256344428/artifacts/12189785495)

The completed image includes the normal panel painting, GTK clipboard callback
and popup outside-click fixes, installer display/startup corrections, explicit os-prober dependency and nonexpiring
public build certificate. Private signing material was confined to the
disposable runner. The older `c5ad77f` image remains preserved but is not the
current release candidate. The previous `0ac564d` image and its
[successful Live-boot evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39123206803/artifacts/12135591545)
remain preserved for diagnostic history.

## Active acceptance and blockers

The `8bf2df4` build now passes the size gate. Zstd19 reduced the previous
2,147,778,560-byte image by 68,550,656 bytes with the same package selection
and preserved wallpaper digest. The previous `65b2085` ISO and its successful
[Live evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39253873845)
remain preserved; only the required production branding correction justified
this rebuild. Publication remains forbidden by the user's current instruction.

The actual remaining failure in `39256344428` was the test driver's immediate
pointer selection of a row in a large styled region popup. The same failure
was reproduced locally with the actual Qt popup and Husk stylesheet: pointer
input left the placeholder selected, while native Home/Down/Enter events
selected Europe/Helsinki. The driver now uses those real keyboard events,
checks the resulting selection and refuses unavailable/invalid rows. A compiled
Qt regression covers an initially off-screen item and disabled controls.

The recovery run reuses this immutable ISO and its matching, already-passed
Live proof. It also collects the correctly capitalized Calamares log path
(`/root/.cache/Calamares/session.log`), confirmed by the pinned upstream
application name. The old lowercase path missed the real diagnostic log.

Cancellation retains actual GUI confirmation, zero guest written/discarded
sectors, monotonic raw counters and identical GPT-edge hashes. Before the
second installer process can start, the guest now waits for an explicit test
host acknowledgement. The host independently queries the exact `target`
backend through [QMP block statistics](https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html)
and requires zero write/unmap bytes, operations and failed/invalid requests
since the fresh disk was attached. Flush counts are recorded separately.
Missing, ambiguous or nonzero evidence stops the VM before installation.
Focused regressions pass; a real QMP-over-stdio check on a fresh local qcow2
confirmed the response schema without booting an OS or opening listener sockets.
The strengthened cancellation/installation gates still require the recovery VM.

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
override. These source fixes are included in the `65b2085` ISO. Its actual VM
run passed XWayland display authorization, UTF-8 startup and standard QML-path
initialization without the previous errors. Normal polkit/PAM authorization
is still unverified.

The next actual startup error in [39253873845](https://github.com/monsteri24/Husk-OS/actions/runs/39253873845)
was `invalid node; first invalid key: "images"` in `branding.desc`. Inspection
of the pinned upstream `Branding.cpp` confirmed that `strings`, `images` and
`style` are required mappings, even when optional image entries are absent.
The corrected configuration supplies the existing installer artwork and Husk
wallpaper as absolute installed asset paths. Read-only payload validation now
rejects missing/malformed branding maps, absent guest image/slideshow files,
host paths and theme-dependent image names. Regression tests first reproduced
the missing-map failure and then passed with the correction. The rebuilt `8bf2df4` image reached its actual Qt event loop and the first
three pages; disk review and the installation job queue remain unverified.

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
installation. Cancellation retains guest data counters/GPT-edge hashes and now requires
independent QEMU zero-write/unmap acknowledgement before the next process. Success requires real backend completion, a decreasing
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

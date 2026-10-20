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
| Source/models/real GTK | [39384138078](https://github.com/monsteri24/Husk-OS/actions/runs/39384138078) passed at `22ed589`: 469 tests with zero failures or skips in the actual GTK run; 177 source/configuration checks and native sanitizer checks also passed. |
| Local checks | The current full local run passed 469 tests with 71 explicit graphical/environment skips, plus native sanitizer checks with local leak detection disabled. Real offscreen Qt checks cover actual launcher styles, completion actions, popup selection, navigation bounds, the patched partition renderer and input against the actual SDDM theme in Basic/Fusion styles. All 177 source/configuration checks pass. |
| Actual Labwc | The same `22ed589` run passed taskbar restore, normal panel pixels, maximized transparency/click-through, genuine fullscreen hide/restore, GTK window controls, menus, file navigation and app confirmation/Cancel. |
| Real application packages | [39246817254](https://github.com/monsteri24/Husk-OS/actions/runs/39246817254) passed using the older `0ac564d` ISO, on the day after its build. Signed root-container transactions installed Firefox `158.0-1` and Steam `1.0.0.87-3`. This does not prove graphical authentication or Steam/game launch. |
| Full V3 build | [39377861570](https://github.com/monsteri24/Husk-OS/actions/runs/39377861570) compiled patched Calamares, built signed packages and produced the UI-corrected ISO. Generic/V3 extracted-rootfs checks and the file-size gate passed. Final target inspection failed in the test fixture as described below. |
| Live UEFI boot | That exact `812d74c` ISO passed real OVMF Live startup, Wayland desktop evidence, terminal shortcut and safe ACPI shutdown. |
| Calamares UI/jobs | Actual selection, readable scrollable disk review, separate irreversible confirmation, all 30 offline jobs, Installation Complete, real countdown 30 to 26 and pointer activation of Restart Later passed. The process exited 0 and the Live boot ID remained unchanged beyond 35 seconds. Target-file and independent installed-boot validation also passed. |
| Disk guard/cancellation | The current VM accepted only the disposable target and rejected the Live medium. Actual summary cancellation exited 0, guest written/discard sectors and GPT-edge hashes were unchanged, and independent QMP counters showed zero target writes/unmaps before installation was authorized. |
| Installed target | Recovery `39384138078` passed all 19 target checks: GPT/ESP/ext4, fstab, user/password presence, kernel/initramfs, GRUB/fallback, version, Live cleanup, actual job starts, IANA timezone, keyboard, English locale and hostname. Installation and Live ACPI shutdown were PASSED. |
| Independent UEFI boot | The same run booted the installed disk with no ISO/kernel override and authenticated through SDDM into Husk Desktop. The actual normal-user report confirms UID 1000, `/dev/vda2` ext4, UEFI, no Live medium/debug shell, Wayland session on VT1, connected native bridge and mapped desktop/panel. Installed ACPI shutdown passed. |

The latest completed ISO is preserved as an explicitly **unverified** Actions artifact.
It includes the corrected summary/completion UI and existing artwork, passed
payload validation, Live UEFI boot, real offline installation and target
inspection, and fits the file-size limit. Independent installed UEFI boot,
normal-user/Wayland login and safe shutdown also passed. The artifact retains
its original UNVERIFIED filename; these results do not imply hardware or
normal Live authorization acceptance and do not authorize publication:

- Source: `812d74c248ca4696fd6cda27f87ffaef0f9a14ec`
- Size: **2,079,227,904 bytes**
- SHA-256: `860c264492199262fe413876d3477006729119dbe198e2cf640155f2bfacbc21`
- [ISO and checksum artifact](https://github.com/monsteri24/Husk-OS/actions/runs/39377861570/artifacts/12244682086) (retained until 2026-10-27)
- [Build/Live/installer evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39377861570/artifacts/12245252087)
- [Passing installation/installed-boot evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39384138078/artifacts/12246674833)
- [Permanent machine-readable acceptance summary](evidence/v3-phase2/2026-10-20-acceptance.json)

The completed image includes the normal panel painting, GTK clipboard callback
and popup outside-click fixes, installer display/startup corrections, explicit os-prober dependency and nonexpiring
public build certificate. Private signing material was confined to the
disposable runner. The older `c5ad77f` image remains preserved but is not the
current release candidate. The previous `0ac564d` image and its
[successful Live-boot evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39123206803/artifacts/12135591545)
remain preserved for diagnostic history.

## Current acceptance and diagnostic history

All three jobs in [39384138078](https://github.com/monsteri24/Husk-OS/actions/runs/39384138078)
passed at `22ed589`. It reused the exact `812d74c` ISO and matching prior Live
UEFI proof without rebuilding. The real installer cancelled without writes,
installed offline, passed all 19 target checks, postponed restart and shut
down safely. A new VM booted only the installed disk, selected Husk in SDDM,
authenticated as newly created user `huskcheck` (UID 1000), and reported a real
Wayland Husk Desktop with no Live media or debug kernel arguments. Its final
screenshot shows the preserved wallpaper, Home/Trash and normal panel, with
no Install Husk OS icon. Installed-system ACPI shutdown passed. Results and
proof scope are preserved in the linked JSON; remaining coverage limits are
listed below. No publication, merge or main change is authorized.

Recovery [39381173228](https://github.com/monsteri24/Husk-OS/actions/runs/39381173228)
passed the corrected target inspection and all 19 checks, then cleanly shut
down the Live VM. Its new VM had no ISO or kernel override; OVMF loaded the
installed GRUB from the virtual disk and the screenshot shows the Husk SDDM
greeter with Password focused. The selected session was stock `labwc`, not
Husk. The input fixture then unnecessarily switched to VT1 and later assumed
VT2 was a text console. No installed-user report arrived, so the full gate
failed rather than claiming success from a greeter screenshot.

The fixture now keeps the auto-activated greeter, explicitly selects the Husk
session through actual keyboard input, and uses separate text VT6 for normal
password authentication. It reads VTNr from the actual Wayland session and
returns only to that validated graphical VT. An attempted boot is now marked
FAILED until accepted, rather than being left NOT TESTED. No debug shell,
autologin, authorization bypass or installed-system modification is added.
Actual Qt Quick tests load the repository's real SDDM theme: the old sequence
left stock labwc selected; the corrected sequence selects Husk and fills the
proper username/password fields under both Basic and Fusion. The tests mock
the authentication backend; the subsequent recovery VM proved real login.
The current full local suite passes 469 tests with 71 explicit environment
skips, all 177 source checks and native sanitizer checks. Recovery
`39384138078` used the identical ISO and passed the full user/session gate.

The current `812d74c` build passed both payload checks, its size gate and real
Live UEFI boot. Actual screenshots verify the readable partition legend,
scrollable summary and navigation inside the 1280x746 work area. Completion
loaded correctly with the Husk palette and working ViewManager actions. The
offline VM ran all 30 jobs, including users, locale generation, mkinitcpio,
UEFI GRUB/fallback, checked filesystem flush, normal unmount and final sync.
The countdown changed 30 to 26 in four seconds, Restart Later exited 0 and
the boot ID remained unchanged beyond the automatic-restart interval.

Final inspection then raised an empty StopIteration: its lsblk request used
PATH without NAME or `--tree`, so the output was flat and had no `children`.
The read-only fixture now explicitly requests `--tree` after udev settle,
preserves the raw result before validation, checks the disposable disk identity
and expected ext4/FAT32 layout, and reports exception types on failure
([lsblk format documentation](https://man.archlinux.org/man/lsblk.8.html)). A
regression reproduces the old StopIteration and reaches the read-only fsck
checkpoint with the corrected request. Wrong disk identity, absent partitions
and paths outside the disposable disk are rejected. No target validation is bypassed.

The real log also shows Python start events use stable module IDs (`unpackfs`,
`bootloader`) before their lazy pretty_name is loaded. The fixture now checks
those exact start events, rejects mere planned queue entries, and additionally
checks the installed hostname. All 31 focused input/orchestration tests pass.
The following recovery reused this image without rebuilding and passed target
inspection as recorded above; `39384138078` then passed normal-user/Wayland acceptance.

The preceding `8bf2df4` build passed the size gate. Zstd19 reduced the previous
2,147,778,560-byte image by 68,550,656 bytes with the same package selection
and preserved wallpaper digest. The previous `65b2085` ISO and its successful
[Live evidence](https://github.com/monsteri24/Husk-OS/actions/runs/39253873845)
remain preserved; only the required production branding correction justified
this rebuild. Publication remains forbidden by the user's current instruction.

Recovery [39374652341](https://github.com/monsteri24/Husk-OS/actions/runs/39374652341)
verified the existing ISO digest/payload and matching prior Live boot proof.
Its real GTK run passed 458 tests without skips, and real Labwc passed. The
VM setup then stopped safely before Calamares: a default route was still
visible immediately after NetworkManager reported successful reapplication.
The prior code inspected routes just once, so it could not distinguish delayed
kernel/RA convergence from a persistent failure. The test now applies each
device change once, polls for up to 30 seconds and requires a stable empty
result for one second. It records every route observation and the apply
result, and preserves the exact remaining routes on timeout. Command/JSON
errors still stop immediately. Two regressions reproduce delayed removal and
a persistent route; all 24 focused orchestration tests pass. This is a VM
fixture change and does not require rebuilding or modifying the ISO.

The bounded retry [39375337125](https://github.com/monsteri24/Husk-OS/actions/runs/39375337125)
showed a persistent IPv6 default through `fe80::2` after 30 seconds; IPv4 had
been removed. The fixture now explicitly uses QEMU user networking with
`ipv6=off`, avoiding an independent IPv6 router in this IPv4 evidence transport
([QEMU invocation documentation](https://www.qemu.org/docs/master/system/invocation.html)).
The ISO and installed-system network configuration are unchanged. The guest
still checks both IPv4 and IPv6 for unexpected defaults and requires stable
absence before starting Calamares. This offline/IPv4 VM fixture does not prove
real-hardware IPv6 networking. All 24 focused orchestration tests pass,
including the explicit VM network configuration and unchanged boot isolation.

Recovery [39375781268](https://github.com/monsteri24/Husk-OS/actions/runs/39375781268)
passed offline setup with no external IPv4/IPv6 defaults, then reached actual
Helsinki selection, an initially unselected protected drive, explicit erase,
validated account input and the disk-change summary. The driver's expectation
that the summary contain a username was incorrect: pinned UsersViewStep has
no prettyStatus/summary widget. The driver now verifies the actual account and
hostname before leaving the enabled Users page; the summary must identify
`/dev/vda`, erase, GPT, FAT32 and ext4 and must not mention the Live medium.
It retains the separate destructive confirmation and cancellation checks.

Recovery [39376727601](https://github.com/monsteri24/Husk-OS/actions/runs/39376727601)
again verified offline mode and reached validated account fields and the real
summary. Its next driver failure was rich-text handling: the actual summary
says `<strong>Erase</strong> disk`, so a raw substring search for `Erase disk`
incorrectly rejected it. The helper now converts through Qt's rich-text parser
before checking the unchanged disk/method/filesystem requirements. A real Qt
regression uses the captured markup. No installation jobs ran; guest written
and discard sectors remained zero and the GPT-edge digest matched.

The newly collected real session log also exposed a production QML failure:
`module "fusion" is not installed`. The launcher's `-style fusion` option
overrode `QT_QUICK_CONTROLS_STYLE=Basic`; Qt Quick treated the lowercase widget
style as a case-sensitive import. The wrapper now sets Fusion for QWidget and
Basic for Qt Quick independently, without the conflicting command-line option
([Qt style precedence](https://doc.qt.io/qt-6.12/qtquickcontrols-styles.html)).
The actual completion QML test now uses the wrapper's real style environment
and arguments; it reproduced this exact load failure and passes after the fix.
Read-only rootfs validation rejects the conflicting style option.

Pinned `registerQmlModels()` exports ViewManager from `io.calamares.ui`, while
the custom completion page previously imported only core. The test double had
incorrectly exposed ViewManager from core. Both now match the real UI module;
the corrected fixture first failed with the old import and then passed actual
Restart Later, Restart Now and countdown logic with the fix. The page also
sets the existing Husk dark/yellow palette explicitly for Qt Quick controls.
The `812d74c` ISO includes these runtime corrections. Its actual completion
page and Restart Later behavior passed as recorded above; the older ISO
cannot prove them.

The Qt startup event reported the actual log at `//.cache/calamares/session.log`:
the debug service had HOME=/ and the runtime application cache name was
lowercase. The fixture now supplies the normal root HOME/cache environment
and reads the actual Qt-reported path, restricted to Calamares session logs in
root cache directories. Unrelated/relative/traversal paths are rejected. The
previous inferred capitalization did not collect real logs. All 28 focused
input/orchestration tests pass, including summary and log-path regressions.

The same real screenshot exposed two product UI issues that remain in this
immutable ISO: automatic summary expansion places navigation beneath the
panel, and partition-legend text is hardcoded black on the dark background.
Pinned Calamares already supports `windowExpanding: noexpand`, which keeps the
existing summary scroll area instead of requesting automatic growth. The
legend renderer now uses its widget's foreground palette in the pinned UI
patch, and branding disables automatic expansion. A real offscreen Qt test
compiles the actual patched upstream text renderer and verifies that both text
lines are light on a dark background. It failed before the patch and passes
after it. The next VM driver additionally requires visible, unclipped Install
and Cancel buttons and an installer frame inside the available screen before
disk confirmation. Real Qt cases cover parent clipping and off-screen windows.
The launcher's failure message now identifies the observed lowercase root
cache log. These source corrections are included in the `812d74c` ISO; its
actual screenshots and navigation-bound events verify their behavior. Earlier
backend diagnostics on `8bf2df4` remain historical evidence, not final
graphical acceptance of that older image.

The actual remaining failure in `39256344428` was the test driver's immediate
pointer selection of a row in a large styled region popup. The same failure
was reproduced locally with the actual Qt popup and Husk stylesheet: pointer
input left the placeholder selected, while native Home/Down/Enter events
selected Europe/Helsinki. The driver now uses those real keyboard events,
checks the resulting selection and refuses unavailable/invalid rows. A compiled
Qt regression covers an initially off-screen item and disabled controls.

The recovery run reuses this immutable ISO and its matching, already-passed
Live proof. Log collection now uses the actual Qt-reported cache path as
described above, rather than assuming HOME or application-name capitalization.

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
verified identical ISO instead of repeating that separate boot. Each new
installation VM must independently reach real Calamares and the installed desktop;
this passed in `39384138078`.
The replaced fixed-delay run was superseded by this acknowledged test. It may attach
only a newly created 32 GiB qcow2 without a backing file and read-only Live
media. Actual Qt pointer/keyboard input must select the target, IANA zone and
account, review and cancel before writes, then separately confirm a fresh
installation. Cancellation retains guest data counters/GPT-edge hashes and now requires
independent QEMU zero-write/unmap acknowledgement before the next process. Success requires real backend completion, a decreasing
countdown, Restart Later surviving beyond 30 seconds, target filesystem/job
checks, safe shutdown and a second UEFI boot with **no ISO or kernel override**
into the newly created user's SDDM/Wayland desktop. These installation and
installed-boot gates **passed in 39384138078**.

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

For this candidate's first installed login, select **Husk Desktop (Experimental)**
in SDDM. The stock labwc entry remains present and was initially selected in
the real greeter; default-session refinement remains incomplete. The VM input
test explicitly chose Husk and proved the real user session. Automatic default
selection of Husk remains future refinement.

The VM input fixture uses a test-only root debug console; it does not verify the
normal Live graphical polkit/PAM authorization or Live password dialog. The
installed user's SDDM and text-console password authentication did pass. The signed
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
alone never imply ISO or installation success. The passing VM gates do not
authorize publication: the user's explicit no-release instruction remains in
force. Report the remaining hardware-dependent and authorization gaps explicitly.

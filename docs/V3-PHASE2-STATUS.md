# Husk OS V3 Phase 2 — candidate status

This branch continues System 2 at `8a57d6c` and preserves both older releases.
It is a development candidate, not a released or certified installer image.

Implemented source includes the graphical curated-app install flow, explicit
network/DNS/repository diagnostics, offline official Steam/Heroic artwork,
libnm Wi-Fi controls, adapter-aware BlueZ/Blueman controls, correct tray
ordering, yellow persistent accent/reset, desktop Trash and protected special
icons, real file/context-menu actions, and foreign-toplevel-driven panel modes.

The installer extends pinned Calamares 3.3.14/KPMCore. Its first mode is UEFI
whole-drive erase only, with no preselected drive, Live-device exclusion,
kernel disk lifetime checks, repeated target verification, real change summary
and a separate final confirmation. Installation clones the verified Live
filesystem offline; initramfs and GRUB remain real required backend jobs.
Checked filesystem flushing and non-lazy unmount must precede completion.
Clock choices resolve to geographic IANA zones; real Qt tests cover DST and
fractional offsets. Completion countdown and Later/Now logic also have Qt tests.

Fresh local verification on 2026-10-18: 419 tests completed with zero failures
and 69 explicit environment/graphical skips; 173 source/configuration checks
passed. Native Wayland code compiles with warnings treated as errors.
Address/undefined sanitizer checks pass with leak detection disabled because
this local environment cannot read the required process metadata. Real Gio
Trash, real libnm profiles, compiled Qt clock/completion behavior and a
test-only Qt input driver's host-refusal checks were exercised.

The first graphical Actions run at e551cee failed. It exposed a nullable GTK
input-region call, gettext shadowing in two application-install callbacks,
menu Escape delivery and an unallocated launcher-row race in the acceptance
harness. These have regression fixes. The complete real Labwc acceptance run
[39121908391](https://github.com/monsteri24/Husk-OS/actions/runs/39121908391)
passed at `3f2a1b4`: native menu pointer/keyboard dismissal, maximized panel
transparency and click-through, genuine fullscreen hide/restore, window
controls, file navigation, missing-app Cancel/confirm and the new graphical
installer's fail-closed preflight/Close behavior. The source/GTK workflow also
passed without graphical skips at the previous checkpoint. The installer now
retains the selected keyboard layout and
variant in the installed user's Labwc defaults. Completion uses the requested
exact title and decreasing countdown text.

Additional visual QA found that app-paintable panel windows suppressed the
normal CSS background. GTK now paints it in desktop mode, with the existing
transparent compact CSS and unmapping for fullscreen. A later parallel run
also exposed GTK's four-argument clipboard target callback and its early
outside-click popup grab. Both now have direct regressions. The updated full
[Labwc run 39122977898](https://github.com/monsteri24/Husk-OS/actions/runs/39122977898)
passed at `1e2b159`, including real normal-background pixels, compact
click-through, fullscreen hide/restore and native menu keyboard/outside input.
The accompanying source and actual GTK jobs passed as well.

The local execution sandbox blocks Unix sockets, so Xvfb/Labwc interactions
must run in GitHub Actions. Qt offscreen logic checks do not replace visible
Calamares, ISO boot, real authorization or installed-system acceptance.

The V3 candidate workflow builds signed packages and the full ISO in a
disposable Arch container. It preserves the exact ISO/checksum as an explicitly
unverified Actions artifact before VM tests. Its new installation harness can
attach only a newly created 32 GiB qcow2 file and read-only Live media. Actual
Qt input must review the target and separate confirmation, observe completion
and choose Restart Later; it then waits beyond 30 seconds and boots the same
disk through OVMF with no ISO or kernel override. It now first cancels from the
reviewed summary and requires unchanged guest disk write counters and GPT-edge
hashes before attempting installation. This harness has not yet run
against a V3 ISO. Test-only root debug delivery does not verify graphical
polkit authorization. Full installer cancellation also remains unverified in
the VM. Guest passwords and password hashes are excluded from saved evidence.

The first package build failed because makepkg links local source assets into
its source directory while the UI patch deliberately requires regular files.
The recipe now uses the checksum-verified regular originals; a real prepare()
regression reproduces makepkg's symlinks and exercises both patches. The second
build produced a real ISO, with the full patched Calamares backend:

- Source: `c5ad77f045babfadacfef93ca0dc37d765a1263d`
- Size: 2,214,559,744 bytes
- SHA-256: `d612e177df905d590f192fc4e2615eab925131f8dc46e29366559beee41b22a4`
- [Preserved unverified image artifact](https://github.com/monsteri24/Husk-OS/actions/runs/39121558357/artifacts/12133754719)

The initial read-only V3 check incorrectly rejected the English C.UTF-8 locale.
Recovery confirmed its actual value, preserved category checks, and required
root access to inspect the correctly protected polkit rules directory. Both
rootfs checks then passed in the recovery workflow; Live boot and installation
results are still pending. This older image predates the latest desktop fixes
and the explicit os-prober dependency. It is an acceptance input, not the final
V3 release image. The next build also keeps the immutable repository's
public signing certificate valid after the build day; private signing material
remains confined to the disposable runner and is never shipped.

Remaining release gates: build the full pinned backend and V3 ISO; boot Live;
install onto a newly created disposable
virtual disk; remove the Live image and boot the installed UEFI system. Until
those pass, do not publish this candidate as working. Wi-Fi scanning and real
association, Bluetooth pairing, and physical GPU/firmware behavior still need
compatible real hardware. Cross-filesystem Cut is deliberately refused;
Copy remains available and existing files are never overwritten silently.

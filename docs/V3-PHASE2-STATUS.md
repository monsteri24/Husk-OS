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

Fresh local verification on 2026-10-18: 413 tests completed with zero failures
and 69 explicit environment/graphical skips; 171 source/configuration checks
passed. Native Wayland code compiles with warnings treated as errors.
Address/undefined sanitizer checks pass with leak detection disabled because
this local environment cannot read the required process metadata. Real Gio
Trash, real libnm profiles, compiled Qt clock/completion behavior and a
test-only Qt input driver's host-refusal checks were exercised.

The first graphical Actions run at e551cee failed. It exposed a nullable GTK
input-region call, gettext shadowing in two application-install callbacks,
menu Escape delivery and an unallocated launcher-row race in the acceptance
harness. These have regression fixes; the replacement graphical CI result
is still required. The installer now retains the selected keyboard layout and
variant in the installed user's Labwc defaults. Completion uses the requested
exact title and decreasing countdown text.

The local execution sandbox blocks Unix sockets, so Xvfb/Labwc interactions
must run in GitHub Actions. Qt offscreen logic checks do not replace visible
Calamares, ISO boot, real authorization or installed-system acceptance.

The V3 candidate workflow builds signed packages and the full ISO in a
disposable Arch container. It preserves the exact ISO/checksum as an explicitly
unverified Actions artifact before VM tests. Its new installation harness can
attach only a newly created 32 GiB qcow2 file and read-only Live media. Actual
Qt input must review the target and separate confirmation, observe completion
and choose Restart Later; it then waits beyond 30 seconds and boots the same
disk through OVMF with no ISO or kernel override. This harness has not yet run
against a V3 ISO. Test-only root debug delivery does not verify graphical
polkit authorization. Full installer cancellation also remains unverified in
the VM. Guest passwords and password hashes are excluded from saved evidence.

Remaining release gates: build the full pinned backend and V3 ISO; run actual
GTK and Labwc interactions; boot Live; install onto a newly created disposable
virtual disk; remove the Live image and boot the installed UEFI system. Until
those pass, do not publish this candidate as working. Wi-Fi scanning and real
association, Bluetooth pairing, and physical GPU/firmware behavior still need
compatible real hardware. Cross-filesystem Cut is deliberately refused;
Copy remains available and existing files are never overwritten silently.

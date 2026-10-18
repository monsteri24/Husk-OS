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

Verification so far: the integrated local suite reached 375 tests with zero
failures and 68 explicit environment/graphical skips before the final review
fixes; focused regression tests cover those subsequent fixes. Native Wayland
code compiles with warnings treated as errors. Address/undefined sanitizer
checks pass with leak detection disabled because this local environment cannot
read the required process metadata. Real Gio Trash and real libnm profile
objects were exercised. Source/configuration syntax checks passed.

The local execution sandbox blocks Unix sockets, so Xvfb/Labwc interactions
must run in GitHub Actions. Qt offscreen logic checks do not replace visible
Calamares, ISO boot, real authorization or installed-system acceptance.

Remaining release gates: build the full pinned backend and V3 ISO; run actual
GTK and Labwc interactions; boot Live; install onto a newly created disposable
virtual disk; remove the Live image and boot the installed UEFI system. Until
those pass, do not publish this candidate as working. Wi-Fi scanning and real
association, Bluetooth pairing, and physical GPU/firmware behavior still need
compatible real hardware. Cross-filesystem Cut is deliberately refused;
Copy remains available and existing files are never overwritten silently.

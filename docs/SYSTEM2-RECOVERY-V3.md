# System 2 recovery V3

Recovery date: 2026-10-16. This is a continuation of the existing project.
Recovered GitHub main: `6b254a27898386b40bf070d2af10c881194c346f`.
Latest executable source with successful source/GTK and real Labwc evidence:
`993d80bf8a9d94a7f4f43e0a74b65fdafbde62cd`. The two later commits contain only
documentation and preserved evidence. No source rollback was necessary.

## Repository and evidence reviewed before implementation

Reviewed the complete tracked-file inventory, all 26 historical commits,
System 2 commits and their changes, source and test definitions, Arch package
recipes, Archiso generation/rootfs validation, existing plans/reports, all four
workflows, all 38 Actions run results, current source and successful desktop
job logs, published release metadata and committed failure evidence.

Current main source CI: [38916413623](https://github.com/monsteri24/Husk-OS/actions/runs/38916413623).
Real Labwc CI at the unchanged executable source:
[38896881547](https://github.com/monsteri24/Husk-OS/actions/runs/38896881547).
That job exercised ten scenarios including actual pointer clicks, taskbar
restoration of the same window, keyboard search and wallpaper pixels.
Artifact `12044078330` remains available (11,145,530 bytes); selected evidence
is already committed. It was not needlessly downloaded again.

Fresh recovery baseline: `timeout 90 make test` discovered 164 tests;
148 passed, zero failed, 16 display-dependent tests skipped. The current
workspace lacks GTK GI, Xvfb and Labwc; those skips are not GUI acceptance.
Previous complete GTK CI executed all 164 without skips.

## Requirement inventory before new changes

| Area | Classification | Evidence / remaining requirement |
|---|---|---|
| Original GTK/Labwc desktop, taskbar, Start/search, popups | COMPLETE for existing tested scenarios | Ten actual Wayland scenarios passed on identical executable source; prolonged stability remains unverified |
| Close, minimize, maximize, restore, taskbar focus | COMPLETE for Foot, Files and Settings | Actual Labwc decoration input and same-window taskbar targeting; preserve existing fixes |
| Official wallpaper | COMPLETE for tested sizes and packaging | Exact original desktop JPEG, SHA-256 `e0f2ee190ff6c11a2102251d4fb13f3cad2690a8f3b9ef3bc5e963079aaeeaac`; package exact-byte test; full-output pixel checks |
| English default | COMPLETE | gettext and real GTK labels tested independently of Finnish host locale |
| Selectable persistent Finnish | MISSING | Existing allowlist supports only English; no selector or Finnish catalog |
| Husk Settings | PARTIAL | Real window, persisted gaming/input/appearance settings, GPU information and wdisplays launch exist; VRR, CPU policy and Optimus controls are not implemented |
| Husk Files | IMPLEMENTED BUT UNVERIFIED for full navigation acceptance | Basic directory tests and real window controls pass; extend actual navigation/Home/Up checks |
| Terminal | IMPLEMENTED BUT UNVERIFIED for shell round trip | Start/shortcut launch and real controls pass; verify typed shell command output |
| Optional application installation | PARTIAL | Trusted Arch/Flatpak command contracts pass; outcome/presence not verified and terminal result disappears; press/release dialog issue needs actual input regression |
| Gaming compatibility | IMPLEMENTED BUT UNVERIFIED on hardware | Mesa/Vulkan and optional Steam/Proton/Wine architecture exists; no game/FPS/hardware certification |
| Native `.hpk` ecosystem | MISSING, intentionally planned | Preserve documented future format; no new package ecosystem in this task |
| System 2 ISO / UEFI boot / release | MISSING | No System 2 build or release exists at recovery |
| Permanent graphical installation | PARTIAL experimental source | Calamares exists as optional source, excluded from default Live ISO; no accepted target installation |

The supplied rounded-corner image is a different branding variant. The already
documented original 1536×864 desktop wallpaper is retained unchanged; no artwork
is generated or substituted.

## System 1 preservation

Preserved release `system-1`, ID `414611526`, source
`8b0ac0b32dc60fc00bbef261acddc3414ce02a52` and all existing assets.
ISO: `HuskOS-system-1.iso`, 2,103,050,240 bytes, SHA-256
`8f14dc313556db9e56fb37a0ce3ef33f2d46cf35200238fb61a3b6240c856363`.
Existing QEMU/OVMF evidence passed. The user's ASUS ROG USB boot is historical
physical evidence for System 1 only. Neither establishes System 2 hardware support.

## Completion priorities and bounded execution

1. Add Finnish to the existing gettext/configuration path.
2. Require fresh deliberate confirmation, preserve installation progress/errors,
   and verify installed state before success.
3. Extend real compositor input/navigation tests and rerun source/GTK/native CI.
4. Reuse signed Arch packaging and the proven TTY1 Live path for a separate
   System 2 ISO. Validate actual ISO/rootfs/assets, UEFI boot and shutdown.
5. Publish an experimental Live release with checksum and honest known limits.

Use finite test/build deadlines, retain failure evidence, and do not repeat a
failed run without a changed hypothesis. Save verified milestones to GitHub
before lengthy operations. System 1 workflows/releases remain unchanged.

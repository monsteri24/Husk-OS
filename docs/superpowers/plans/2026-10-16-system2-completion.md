# Husk OS System 2 completion plan

**Goal:** Finish and publish the recovered System 2 as a verified experimental Live ISO.

**Architecture:** Retain existing GTK/Labwc modules and Archiso packaging. Repair
localization and installation independently, then validate the combined source
and the actual built image before creating a separate pre-release.

**Tech stack:** Python, GTK3, gettext, Labwc/Wayland, Archiso, pacman, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-16-system2-completion.md`

## Global constraints

Preserve `main` ancestry and System 1 release. No optional default user apps.
Use the exact official wallpaper, signed package sources and English default.
No destructive host disk operations; bounded tests; preserve failure evidence.

## Review focus

- Authorization denial and transaction failure never become success.
- Pointer press and release across adjacent dialog buttons never confirm accidentally.
- A saved Finnish choice works after restart; unsupported/corrupt choices fall back.
- Release assets must match the boot-tested ISO and exact source commit.
- No optional user application enters through transitive rootfs dependencies.

## Task 1: Recover and checkpoint

- [x] Compare local source and remote main, recent workflows and release inventory.
- [x] Run existing source baseline: 164 tests, 16 display-dependent skips, no failures.
- [x] Commit and remotely verify this recovery brief before lengthy work.

## Task 2: Localization and application installation

- [x] Add failing behavioral tests for Finnish selection/default/fallback and packaging.
- [x] Add catalog, selection and startup loading without changing desktop architecture.
- [x] Reproduce dialog geometry/input and install failure feedback; add regression tests.
- [ ] Fix confirmation/input/transaction reporting and run complete source/GTK checks.
- [ ] Save and remotely verify the source milestone.

## Task 3: Real desktop and ISO acceptance

- [ ] Extend reproducible compositor checks for file navigation, shortcuts and dialog input.
- [x] Add separate System 2 build workflow and integrity gates; preserve System 1 workflows.
- [ ] Run full source, native and GTK/Wayland Actions on the exact candidate commit.
- [ ] Build signed packages and real Archiso image; check installed rootfs/package inventory.
- [ ] Boot exact image through OVMF; verify desktop, terminal and clean shutdown.
- [ ] Exercise a real optional application installation in the disposable test environment.

## Task 4: Release and documentation

- [ ] Write accurate English download/checksum/USB/Live/desktop/app-install guide.
- [ ] Publish separate System 2 pre-release only after gates; verify remote digest and download.
- [ ] Preserve verification evidence and detailed report with starting/final commits.
- [ ] Run independent final review and fix material findings with regression coverage.

## Recovery ledger

2026-10-16: GitHub main verified at e6595ea; System 1 release 414611526 unchanged.
Latest recovered executable source CI 993d80b passed source and 10 real Wayland
scenarios. Those are prior evidence, not newly boot-tested System 2 acceptance.

V3 recovery continued at 6b254a2, checkpointed as 03a5948. First implementation
milestone 2778f2e is saved and remotely tree-verified. Its complete GTK run executed
235 tests with one early-animation assertion failure; all seven Finnish GUI
cases passed. Real Labwc accepted startup/wallpaper/search/window migration and
Foot typed-command roundtrip/controls, then exposed xdotool's same-position
mousemove --sync wait in new Files navigation. No unchanged retry was requested.
Targeted fixes and a held-opening-key Cancel guard are prepared; fresh local
baseline is 240 tests, 203 passed, 37 GUI skips, 119 source checks. New real
GTK/Wayland acceptance, ISO build, boot and release remain pending. Review also
fixed host/container output ownership and the browser-smoke screenshot path.
System 1 remains unchanged. See docs/evidence/system2-v3/candidate-2778f2e.json.

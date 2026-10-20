# Installed Husk session default implementation plan

> **For agentic workers:** Use superpowers:executing-plans in the existing V3 branch. The user has authorized continuation and saving tested progress; no merge or release.

**Goal:** First installed login opens Husk Desktop without manually selecting its session, while retaining later remembered choices.

**Architecture:** SDDM's existing theme already uses `sessionModel.lastIndex`. Seed its standard `[Last] Session` only when `/var/lib/sddm/state.conf` is missing, using systemd-tmpfiles `f`; retain the theme and SDDM's normal persistence.

**Tech Stack:** Arch packages, systemd-tmpfiles, SDDM, Qt Quick, QEMU/OVMF.

**Spec:** `docs/superpowers/specs/2026-10-17-v3-phase2.md`, continued by the user's explicit first installed desktop/UEFI testing instructions.

## Global constraints

- Work only on `codex/v3-phase2`; preserve `main`, the draft PR, and System 1/2 releases.
- Keep English UI, existing branding, authenticated login and offline operation.
- Test installation only on a fresh disposable VM disk. Do not publish a release.

## Review focus

- Missing state must select `ownos-wayland.desktop`, without adding an autologin user.
- Existing remembered `labwc.desktop` state must survive repeated tmpfiles runs.
- Packaged rule must create the file with SDDM ownership and mode 0600.
- First login must use the default, without a test controller silently changing sessions.
- Final image must pass real offline installation and normal-user UEFI/Wayland boot.

## Task 1: Package the missing default

**Files:** `branding/ownos-sddm.conf`, `packaging/ownos/PKGBUILD`, `tests/test_sddm_defaults.py`.

- [x] Reproduce: upstream SDDM initializes `lastIndex=0` without saved state; actual VM selected stock Labwc.
- [x] Add real package staging/tmpfiles tests and observe failure because no default is packaged.
- [x] Install a non-truncating `f` rule, and run both tests successfully.
- [x] Run the repository check/native suite and save tested source remotely (`0d7dda6`, 471 tests / 71 explicit local skips, 178 syntax checks).

## Task 2: Verify the default in the installed VM

**Files:** `scripts/ci-test-v3-install.py`, `tests/test_sddm_login_input.py`, `tests/test_v3_install_harness.py`, `.github/v3-build-request`, `docs/V3-PHASE2-STATUS.md`.

- [x] Make the actual-theme keyboard regression exercise login without session-selection keys and observe the old controller fail that requirement.
- [x] Remove session manipulation from the VM login controller; retain actual active greeter and observed graphical VT handling.
- [ ] Save the verified change, then request one new ISO because the installed runtime payload changes.
- [ ] Verify Live UEFI, cancellation disk counters, offline installation, and independent normal-user UEFI/Wayland login to the default Husk session.
- [ ] Save exact digest, artifact links, results and remaining hardware/authentication limits in the status report; do not merge or release.

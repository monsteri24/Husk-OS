# Installed Husk session default implementation plan

> **For agentic workers:** Use superpowers:executing-plans in the existing V3 branch. The user has authorized continuation and saving tested progress; no merge or release.

**Goal:** First installed login opens Husk Desktop without manually selecting its session, while retaining later remembered choices.

**Architecture:** SDDM's existing theme already uses `sessionModel.lastIndex`. Seed its standard `[Last] Session` with `/usr/share/wayland-sessions/ownos-wayland.desktop` only when `/var/lib/sddm/state.conf` is missing, using systemd-tmpfiles `f`; retain the theme and SDDM's normal persistence.

**Tech Stack:** Arch packages, systemd-tmpfiles, SDDM, Qt Quick, QEMU/OVMF.

**Spec:** `docs/superpowers/specs/2026-10-17-v3-phase2.md`, continued by the user's explicit first installed desktop/UEFI testing instructions.

## Global constraints

- Work only on `codex/v3-phase2`; preserve `main`, the draft PR, and System 1/2 releases.
- Keep English UI, existing branding, authenticated login and offline operation.
- Test installation only on a fresh disposable VM disk. Do not publish a release.

## Review focus

- Missing state must select `/usr/share/wayland-sessions/ownos-wayland.desktop`, without adding an autologin user.
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
- [x] Save the verified change, then request one new ISO because the installed runtime payload changes.
- [x] Verify Live UEFI, cancellation disk counters, offline installation, and independent normal-user UEFI/Wayland login to the default Husk session (`39449998340`, all passed).
- [x] Save exact digest, artifact links, results and remaining hardware/authentication limits in the status report; do not merge or release.

## Task 3: Close the normal Live authorization coverage gap

**Files:** `scripts/ci-test-v3-live-auth.py`, `tests/test_live_authorization_harness.py`, `.github/workflows/v3-live-authorization.yml`, `.github/v3-live-auth-request.json`.

- [x] Add a fail-closed authorization-report validator and observe missing-harness failures before implementation.
- [x] Implement an observer-only root fixture, actual unprivileged GTK launcher/password input, and QMP input to the real polkit dialog. Keep helpers, PAM/polkit rules and Calamares executable unmodified; forbid preload/test-driver injection.
- [x] Require the active Live session, NP-to-P password state, successful polkit journal action, UID-0 real Calamares, private cookie, English Qt environment, zero QMP disk writes and safe shutdown. Local suite: 473 tests / 71 explicit skips; 180 syntax checks.
- [ ] Save/review test code, then pin the completed new ISO's exact source/digest/size without rebuilding.
- [x] Run the real VM check and inspect its actual polkit/Calamares screenshots before claiming graphical startup acceptance (`39449998358`, all ten checks and shutdown passed).

Review: the SDDM diff had no findings. Independent review of the new authorization
fixture found an incorrect terminal shortcut before VM execution. The shipped
Labwc binding is Super+Return, so the controller now sends `meta_l-ret` as the
existing Live boot harness does. The regression exercised the actual controller
against the shipped XML and failed with Ctrl+Alt+T before the correction. No
runtime desktop binding was changed. Other review assumptions (real dialog
focus/journal wording/GUI visibility) remain for the VM and screenshot check.
After the shortcut regression, the full local suite passed 474 tests with 71
explicit environment skips, native sanitizer checks and 180 syntax checks.
The observer also retains actual polkit/Calamares startup logs on failure,
NP/P password-status letters, active-session fields and the nonsecret Qt locale/
platform/style environment. It never collects password hashes or cookie bytes.
The final local suite remains 474 / 71 explicit skips / 180 syntax checks.

Correction found while the new VM was running: the first seed used a basename.
Tracing upstream `Session::setTo` in `src/common/Session.cpp` shows that
`fileName()` is absolute, and `SessionModel::populate` compares that exact value
with the saved setting. Initial source review and the injected-index Qt fixture
missed this integration requirement. The packaged-state regression now requires
the absolute path; it failed against the basename before the rule was corrected.
Remembered-session preservation still passes. The running `7a190ec` image must
not be accepted as fixing the default; a corrected image is required.
The `7a190ec` VM then confirmed the boundary: Live/terminal/ACPI, offline install,
all 19 target checks and Restart Later passed; the installed disk booted UEFI and
accepted normal-user console login, but its greeter still selected stock Labwc
and no Husk session was observed. The corrected full local suite passed 474
tests / 71 explicit skips / 180 syntax checks (second log with explicit exit 0).

The Live-only authorization test may reuse this image: all runtime inputs must
match except the exact basename-to-absolute SDDM seed correction, whose diff is
saved. It never starts SDDM or claims default-session/installation acceptance.
This narrowly checked difference avoids withholding a tested fix from the branch
while testing the unchanged GTK/PAM/polkit pipeline. The corrected final image
still requires its own complete offline-install/default-login acceptance.

Normal authorization attempt `39445082106` ended at `terminal-ready`, before
the GTK class or polkit was reached. Its real terminal screenshot shows that
typing a slash/hyphen path with US physical key codes produced the wrong text
under the shipped Finnish Live layout (`config/labwc/environment` and defaults).
The test now creates a collision-checked plain filename in the fresh Live home
and types only layout-neutral characters. The controller regression failed on
the old slash path first. The bootstrap has a 60-second acknowledgement deadline;
root diagnostics finish before the host deadline and stage changes are logged.
No keyboard setting or production launcher/authentication policy was changed.

The layout-neutral fix passed the full local suite: 475 tests / 71 explicit
environment skips / 180 syntax checks and native sanitizers (explicit exit 0).
Both failed-scenario summaries are preserved under `docs/evidence/v3-phase2`.

Authorization attempt `39448260566` reached the actual dialog, set the Live
password NP-to-P and observed the real root Calamares process with private cookie,
English Qt and no injection. Its only failing check was the expected log message:
the fixture filtered `polkit.service`, while pkexec's audit belongs to its caller's
session. Upstream pkexec logs `Executing command` through its own identifier before
exec. The observer now requires that exact helper/root-target audit from the
trusted matching journal PID plus actual `PKEXEC_UID`, instead of an unrelated
daemon-unit phrase. Positive and wrong-PID/identity/target/denial tests first failed
before the parser was added. Production policies/helpers remain unchanged.

The PID-bound audit parser passed its positive/negative regressions and the full
local suite: 477 tests / 71 explicit environment skips / 180 syntax checks,
native sanitizers, explicit exit 0. The corrected SDDM ISO build is now requested
alongside the third smoke test; the actual root launcher needs no runtime change
from the eight positive observations in the second smoke test.

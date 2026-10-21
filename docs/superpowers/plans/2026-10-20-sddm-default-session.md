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
- [x] Save/review test code, then pin the completed new ISO's exact source/digest/size without rebuilding.
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

## Task 4: Verify the remaining real completion actions

The continuation recovered remote `c677d21` and inspected its successful full
image acceptance `39449998340`, plus real authorization `39449998358`. Their
permanent summaries are committed. The scratch checkout had reverted to the
previous synced milestone; the unsent completion-test patch mentioned by the
previous execution is absent locally and its tree is not available remotely.
Keep all remotely saved work and continue from that verified head.

- [x] Extend only the existing guarded disposable-disk fixture with Now and
  automatic modes; leave production QML, timer and reboot commands unchanged.
- [x] Test validation first: target checks before restart, genuine QMP
  guest-reset provenance, real countdown/input records, refusal of poweroff,
  host reset, missing evidence and failed QEMU exit; preserve asynchronous QMP events.
- [ ] Reuse the exact corrected ISO with a strict runtime-source/digest/size
  check, separate fresh disks for each action, then independent installed UEFI boot.
- [ ] Observe actual Now click before zero and automatic countdown through zero;
  do not inject reboot commands or treat a plain application exit as restart.
- [ ] Run the complete local suite and C++ driver compilation, save the milestone
  remotely, review the fixture and run the real acceptance jobs.
- [ ] Inspect evidence and record precise results/remaining limits. No release,
  main update, merge or hardware disk operation is authorized.

Ruling: use QEMU `-no-reboot` and require SHUTDOWN `guest=true`,
`reason=guest-reset`, then boot the same installed disk without the ISO. This
separates a real guest reboot from host ACPI poweroff or process termination
and keeps USB removal deterministic. Cost if wrong: the test fails closed
and requires further diagnostics; it never accepts a host reset as success.

The corrected image also passed normal Live authorization in `39609995495`:
all ten checks, actual English Calamares screenshot, zero QMP writes/unmaps and
safe shutdown. Permanent evidence: `2026-10-21-live-authorization.json`.

The fresh Labwc run `39610003707` passed panel maximized transparency and true
fullscreen hide/restore, but its confirmation assertion consumed the first
mapped snapshot before Cancel had focus (neither button was focused). The
fixture now waits bounded for the same real Cancel focus/default requirement.
Its regression first failed with the observed unfocused snapshot, then passed.
Product confirmation behavior is unchanged; real follow-up remains pending.

Final review: two Important findings, no Critical or Minor findings. The
Now validator could accept a missed click followed by automatic zero; the
observer could race expected shutdown against alive()/serial reads. Both were
reproduced before correction. Now requires the actual QML restartRequested
and stopped timer at positive seconds after the real click, plus genuine QMP
guest reset. Approved shutdown waits no longer use live serial/liveness calls.
The focused 35-test harness suite passed after these corrections.

The first complete local run hit its explicit 180-second limit while compiling
native-state checks; it was not accepted as passing. The focused native-state
tests passed (2 tests, 19.854 seconds). A longer bounded full run follows the
review fixes; no ISO rebuild or VM rerun was started by that timeout.

Final: fixed false-positive Now fallback — positive QML request/stopped-timer
evidence and fallback/zero/running-timer regressions RED→GREEN. Final: fixed
shutdown observer race — exit-between-polls/serial-EOF regression RED→GREEN.
The final full suite passed 484 tests with 71 explicit local environment skips
in 270.668 seconds, native ASAN/UBSAN with local leak detection disabled and
180 syntax checks; explicit exit 0. Complete C++ test driver compiled with
Qt6 Widgets/Test/Quick and -Wall -Wextra -Werror; explicit exit 0.
No minor findings were deferred. The image request now pins the already
accepted c677d21 ISO for both actual restart modes; no runtime payload changed.

## Task 5: Distinguish Qt display loss during actual automatic shutdown

`39613704162` passed the real Now scenario: click at26, actual QML request and
stopped timer at26, quit at26, clean QMP guest-reset and independent installed
normal-user UEFI/Husk Wayland boot. All19 target checks and cancellation counters
passed. Permanent Now evidence and the passing 484/zero-skip GTK plus real Labwc
evidence are saved. The corrected focus wait passed the real compositor run.

The automatic scenario ran all30 jobs and all19 checks, observed each real tick
30..0 and invoked the unchanged production sync/systemctl reboot. XWayland closed
during shutdown and Qt exited1. The observer treated that late display loss as
an installation error; the host terminated QEMU before final reset proof.
This failed run is preserved, not counted as automatic-restart acceptance.

- [x] Reproduce the captured late Qt exit and automatic-only request selection
  in failing regressions before changing either fixture.
- [x] Preserve early/driver failures, retain late exit as diagnostics only after
  verified completion and require the same independent QMP/countdown proof.
- [x] Add validated request modes so the already passing Now VM is not repeated.
- [ ] Run the complete suite, save progress, retry only automatic on a new disk
  using the same accepted ISO, and inspect final UEFI/Wayland evidence.

The captured late Qt exit and validated request selection regressions passed,
followed by the complete local suite: 486 tests in 394.224 seconds, 71 explicit
environment skips, native ASAN/UBSAN with local leak detection disabled, all181
source/configuration checks, explicit exit0. No production runtime or C++ driver
change was needed. The source and all completed/failed evidence are saved before
the automatic-only retry; Now is not rerun.

## Task 6: Observe zero before the QML reboot call

`39617183344` reached a clean QMP SHUTDOWN guest=true/reason=guest-reset.
The Qt late-exit correction worked. The strict zero gate still failed: the
500 ms sampler recorded30..1, then the process shut down before another poll.
Independent installed boot was correctly withheld. The failed trace is kept
in `2026-10-21-automatic-zero-diagnostic.json`.

Ruling: replace only test countdown polling with a read-only native
QQmlExpression valueChanged subscription. Its direct callback observes the
actual secondsRemaining change before the QML handler calls reboot; no timer,
value or product command is changed. Cost if wrong: strict zero/reset/target
gates still reject the run. A real Qt test sets zero and immediately emits
QML shutdown without pumping the event loop; the observer must already hold0.
It failed before implementation and passed afterward (16.013 seconds).

- [x] Implement direct property observation with guarded object lifetime;
  stop fixture polling after zero, preserving the actual production timer.
- [ ] Run the full suite and full driver compilation, save progress and retry
  only automatic with a fresh disk and the identical ISO.
- [ ] Inspect zero, actual guest reset and independent installed UEFI/Wayland
  evidence, then save the final status without a release or merge.

The final notifier change passed the full local suite: 487 tests in387.359
seconds, 71 explicit environment skips, native ASAN/UBSAN with local leak
detection disabled and181 source checks. Full shared-driver compilation with
Qt6 Widgets/Test/Quick and -Wall -Wextra -Werror also passed; explicit exit0.
The third automatic-only request retains the exact c677d21 image/digest/size.

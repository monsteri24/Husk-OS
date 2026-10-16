# Husk OS

Husk OS is an experimental gaming operating system built on **Arch Linux**, with
its own GTK **Husk Desktop** on Labwc/Wayland. The desktop, Settings, Files,
launcher and taskbar are developed here. Existing `ownos` package, configuration
and D-Bus names remain for compatibility.

**System 2 is current development source. As of 2026-10-16, no System 2 ISO or
release is available.** New GTK/Labwc acceptance checks and the signed ISO build
are pending. Check the [Releases page](https://github.com/monsteri24/Husk-OS/releases)
and the dated [System 2 report](HuskOS-system-2-REPORT.md) for publication and
verification status. Results for an older source commit do not validate the
current candidate.

## Current System 2 source

- English is the default interface language. **Settings → Appearance → Interface
  language → Suomi (fi-FI)** saves Finnish for subsequent application starts;
  the desktop reloads its translated controls. See [localization](docs/LOCALIZATION.md).
- The original black-and-gold desert wallpaper, Start/search, taskbar,
  notifications, window controls, Husk Settings, Husk Files and Foot terminal
  are retained.
- The base includes essential desktop, firmware, graphics, networking, audio,
  storage and recovery components. Optional applications such as Steam, Proton,
  Wine, Lutris, Heroic, Discord and Firefox are installed only on request.
  Local desktop, terminal, Settings and file use do not require an Internet connection.
- Missing curated applications open a deliberate Cancel/OK installation dialog.
  The application helper keeps its terminal open and verifies installed state
  before reporting success. Native application installation in Live requires a temporary password,
  administrator authentication and normal package-manager confirmation.
  [Application installation](docs/APP-INSTALLATION.md) explains the sequence and
  its current acceptance limits.

The latest recorded headless source baseline has **240 discovered tests: 203
passed and 37 display-dependent tests skipped**. New graphical acceptance and
System 2 ISO/QEMU checks are pending. Source tests, a nested Wayland desktop,
a booted ISO and physical hardware are separate evidence categories.

## Try or build Husk OS

Read the [download, checksum, USB and Live guide](docs/INSTALL.md) first.
There is **no completed graphical operating-system installer**; the Calamares
integration remains experimental source. Use a disposable VM for development.
The [build guide](docs/BUILD.md) describes the new System 2 gates and preserves
historical System 1 instructions. [VM testing](docs/VM-TESTING.md) documents
isolated virtual-disk checks.

The release candidate uses the first-boot Live profile, with 64-bit Mesa and
TTY1/PAM session startup. The standard development profile also retains 32-bit
graphics libraries. GameMode and MangoHud are optional tools: their Settings
switches configure `husk-game` and do not install them. Install the tools or
disable the corresponding switch before using that wrapper. CPU policy controls,
automatic NVIDIA/Optimus switching and accepted VRR behavior are not provided.
No FPS improvement or universal game/anti-cheat compatibility is claimed.

Husk Store, the native **`.hpk`** format and a maintained signed Husk update
repository/key lifecycle remain planned. The current Arch/Flatpak installation
paths do not implement that future store or native package ecosystem.

## Historical System 1 release

System 1 remains preserved as **Husk OS System 1 — Experimental Live**:

- [Download HuskOS-system-1.iso](https://github.com/monsteri24/Husk-OS/releases/download/system-1/HuskOS-system-1.iso)
  — **2,103,050,240 bytes**.
- [SHA-256 file](https://github.com/monsteri24/Husk-OS/releases/download/system-1/HuskOS-system-1-SHA256.txt)
  — `8f14dc313556db9e56fb37a0ce3ef33f2d46cf35200238fb61a3b6240c856363`.
- Source: `8b0ac0b32dc60fc00bbef261acddc3414ce02a52`.
- [Release](https://github.com/monsteri24/Husk-OS/releases/tag/system-1) and
  [original build/boot report](HuskOS-system-1-REPORT.md).

The recorded System 1 QEMU/OVMF run reached the real Labwc/Wayland desktop,
opened Start and Foot, and shut down normally. Its report retains the earlier
failed run and known limitations. This lightweight Live release omits Calamares;
its VM result does not establish permanent installation, game performance,
physical hardware support or System 2 acceptance. System 1 assets and history
must not be overwritten by System 2.

## Development

| Path | Purpose |
|---|---|
| `src/ownos/` | Configuration, installation policy, gaming wrapper, metrics and session code |
| `src/ownos/ui/` | GTK desktop, launcher, taskbar, Settings, Files and notifications |
| `native/` | Wayland toplevel helper and window actions |
| `config/labwc/` | Window controls, shortcuts and session/input configuration |
| `locale/` | Gettext template and Finnish catalog |
| `packaging/` | Signed Arch package recipes and optional Calamares integration |
| `installer/` | Experimental installation policy and configuration |
| `iso/` | Live profile inputs and session setup |
| `scripts/` | Source, desktop, package, ISO and VM verification |
| `tests/` | Source contracts, regressions, native helpers and prepared-display tests |

Run `make test` for Python tests, `make test-c` for the native JSON helper,
and `python3 scripts/check-source.py` for source/configuration syntax checks.
Python checks require PyYAML; catalog checks require GNU gettext. Run
`./scripts/test-gtk.sh` in the prepared GTK/Xvfb environment, and
`python3 scripts/test-labwc.py` in the prepared nested Wayland environment.
Neither substitutes for booting the exact ISO.

License: [MIT](LICENSE). Linux, Arch Linux, Labwc, GTK and other upstream
components retain their own licenses and are documented openly.

# Husk OS

**An experimental Arch Linux-based operating system designed for gaming.**

Husk OS combines an Arch Linux foundation with its own GTK desktop environment, **Husk Desktop**, running on Labwc and Wayland.

The project focuses on building a distinctive gaming-oriented Linux experience while retaining a transparent, testable development process.

> **Project status:** Experimental. System 2 is the latest public Live release. Version 3 is under active development and has not been released.

## Project overview

| Component | Technology |
|---|---|
| Base distribution | Arch Linux |
| Architecture | x86_64 |
| Display protocol | Wayland |
| Window compositor | Labwc |
| Desktop interface | Husk Desktop (GTK) |
| Package management | Pacman / Flatpak |
| ISO construction | Archiso |
| Graphical installer (V3) | Calamares 3.3.14 / KPMCore |
| Firmware target | UEFI |
| License | MIT (project code) |

Existing internal `ownos` package names, paths and D-Bus identifiers are retained for compatibility.

## Features

### Husk Desktop

- Custom launcher, taskbar and window management integration
- Husk Settings and Husk Files
- Native desktop menus and file operations
- Network and Bluetooth controls
- Custom black-and-gold branding and wallpaper
- Desktop notification and application-launching support

### Gaming-oriented design

- Optional Steam, Heroic, Lutris and other application installation paths
- Gaming-related configuration and utility integration
- Support for standard Linux graphics and package ecosystems

Gaming performance and game compatibility depend on hardware, drivers and upstream software. Husk OS does not claim universal anti-cheat compatibility or guaranteed FPS improvements.

### Version 3 development

The V3 development branch includes:

- Graphical Calamares installation
- Explicit target-disk selection and destructive-operation confirmation
- Offline installation from the Live environment
- Installed-system UEFI boot and Husk Desktop login
- Installation-completion countdown and restart controls
- Desktop interaction, networking and application-installation improvements

The initial installer supports **UEFI whole-drive erase only**. Dual-boot, alongside installation and manual partitioning are not supported installation modes.

## Releases

### System 2 — Experimental Live

The latest public release is **Husk OS System 2**, published on October 17, 2026.

[Download System 2](https://github.com/monsteri24/Husk-OS/releases/tag/system-2)

System 2 is a Live USB/VM release. It does not contain a completed permanent graphical installer.

### Version 3 — In development

Version 3 is being developed separately from the published releases.

- [Development pull request](https://github.com/monsteri24/Husk-OS/pull/1)
- [V3 acceptance status](docs/V3-PHASE2-STATUS.md)
- [Development history](docs/V3-PHASE2-HISTORY.md)

The development branch has passed automated tests covering graphical authorization, disposable-disk installation, installed UEFI boot, Husk Desktop login and installation-completion restarts.

The current candidate passed normal Live UEFI boot, offline installation, independent installed UEFI login and actual graphical Steam package installation. Steam's completed self-updates and native sign-in window passed the strengthened 30-second startup gate on the same ISO in a 12 GiB Live VM. Heroic/game startup remains under verification. Physical hardware testing remains outstanding. See the scoped [V3 acceptance status](docs/V3-PHASE2-STATUS.md).

**No V3 release has been published.**

Historical System 1 and System 2 releases remain available.

## Repository structure

```text
Husk-OS/
├── src/ownos/          # Core services and application logic
│   └── ui/             # GTK desktop applications and shell
├── native/             # Native Wayland integration
├── config/labwc/       # Compositor and keyboard configuration
├── installer/          # Installer integration and policies
├── packaging/          # Arch package definitions
├── iso/                # Archiso profile inputs
├── locale/             # Localization sources
├── scripts/            # Build, test and verification tools
├── tests/              # Automated regression tests
├── docs/               # Technical documentation
└── .github/workflows/  # Continuous integration
```

## Development setup

Development and ISO construction should take place in a disposable Arch Linux virtual machine rather than on a machine containing important personal data.

Consult [BUILD.md](docs/BUILD.md) for dependencies, package signing and complete build instructions.

### Clone the repository

```bash
git clone https://github.com/monsteri24/Husk-OS.git
cd Husk-OS
```

### Run source tests

```bash
make test
make test-c
python3 scripts/check-source.py
```

### Build and verify native components

```bash
make native
make check
```

### Graphical tests

In a correctly prepared graphical test environment:

```bash
./scripts/test-gtk.sh
python3 scripts/test-labwc.py
```

These checks require their respective GTK/Xvfb and nested Wayland environments.

Passing source tests does not establish that a newly built ISO boots or installs successfully.

## Building an ISO

The project uses signed Arch packages and an Archiso-based build process.

Relevant commands include:

```bash
./scripts/build-packages.sh --check
./scripts/build-packages.sh
./scripts/build-iso.sh --check
sudo ./scripts/build-iso.sh
```

These commands require a prepared Arch Linux build environment, appropriate dependencies and configured package-signing credentials.

The V3 installer build has additional requirements. Follow the version-specific workflow and documentation instead of assuming that the default historical build produces the current installer candidate.

See:

- [Build documentation](docs/BUILD.md)
- [VM testing](docs/VM-TESTING.md)
- [Installation guidance](docs/INSTALL.md)

## Testing and verification

Husk OS uses multiple levels of verification:

1. Python and native regression tests
2. Source and configuration validation
3. GTK interaction tests
4. Real nested Labwc/Wayland tests
5. Signed-package and ISO-content checks
6. QEMU/OVMF UEFI boot testing
7. Disposable virtual-disk installation
8. Independent installed-system boot and login
9. Application authorization and installation tests
10. Physical hardware testing

Results are recorded in GitHub Actions and the repository's technical evidence files.

Automated virtual-machine acceptance is not equivalent to hardware certification.

## Current limitations

- Experimental software; not recommended as a replacement for a working primary operating system
- English-only active desktop interface
- Physical GPU, Wi-Fi, Bluetooth and USB boot compatibility not fully verified
- No accepted universal game or anti-cheat compatibility guarantee
- No completed native `.hpk` package ecosystem
- V3 installer limited to UEFI whole-drive erase
- V3 not yet published as a stable or pre-release download

Always back up important data before testing operating-system installation tools.

## Roadmap

Development priorities include:

- Complete V3 application-installation acceptance
- Validate a new installer ISO against the complete test suite
- Expand physical hardware compatibility testing
- Improve desktop usability and gaming integration
- Develop the planned native `.hpk` application package ecosystem

Roadmap items are plans, not commitments or implemented features.

## Contributing

Contributions, bug reports and technical feedback are welcome through GitHub Issues and Pull Requests.

For reproducible reports, include the Husk OS version or commit, hardware or virtual-machine configuration, reproduction steps, expected behavior and relevant logs.

## License

Husk OS project code is licensed under the [MIT License](LICENSE).

Arch Linux, Linux, GTK, Labwc, Calamares and other upstream projects retain their respective licenses.

---

**Husk OS — Built for gaming. Developed in the open.**

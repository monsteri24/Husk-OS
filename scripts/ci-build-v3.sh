#!/usr/bin/env bash
# Runs only in the disposable privileged Arch container on an Actions runner.
set -euo pipefail
cd /src
[[ $(. /etc/os-release; printf '%s' "$ID") == arch && $EUID == 0 ]]
[[ ${HUSK_HOST_UID:?} =~ ^[0-9]+$ && $HUSK_HOST_UID -ne 0 ]]
[[ ${HUSK_HOST_GID:?} =~ ^[0-9]+$ ]]
trap 'if [[ -d /src/out && ! -L /src/out ]]; then chown -R "$HUSK_HOST_UID:$HUSK_HOST_GID" /src/out; fi' EXIT
pacman -Sy --noconfirm archlinux-keyring
pacman -Syu --noconfirm --needed base-devel archiso git gnupg python python-yaml \
  wayland pkgconf gtk3 python-gobject python-cairo librsvg gettext gtk-layer-shell \
  networkmanager xorg-server-xvfb xorg-xauth dbus cmake ninja extra-cmake-modules \
  qt6-base qt6-declarative qt6-svg qt6-wayland qt6-tools kpmcore yaml-cpp icu \
  libpwquality polkit polkit-qt6 kconfig kcoreaddons ki18n kservice kiconthemes solid kjobwidgets pybind11
useradd --create-home --user-group --uid "$HUSK_HOST_UID" builder
install -d -m700 -o builder -g builder /husk-gnupg
runuser -u builder -- env GNUPGHOME=/husk-gnupg bash -eu -o pipefail -c '
  cd /src
  gpg --batch --pinentry-mode loopback --passphrase "" \
    --quick-generate-key "Husk OS V3 ephemeral build key" ed25519 sign 1d
  OWNOS_SIGNING_KEY=$(gpg --batch --with-colons --list-secret-keys | awk -F: '\''$1 == "fpr" {print $10; exit}'\'')
  export OWNOS_SIGNING_KEY
  make check native
  bash scripts/build-packages.sh --with-installer
  mkdir -p out
  c++ -std=c++17 -Wall -Wextra -Werror -shared -fPIC \
    scripts/v3-installer-driver.cpp -o out/v3-installer-driver.so \
    $(pkg-config --cflags --libs Qt6Widgets Qt6Test Qt6Quick)
'
pacman-key --init
bash scripts/build-iso.sh --first-boot --with-installer
images=(out/huskos-*.iso)
[[ ${#images[@]} == 1 && -s ${images[0]} ]]
mv "${images[0]}" out/HuskOS-v3-phase2.iso
# Preserve the completed image and its exact digest before optional VM checks.
sha256sum out/HuskOS-v3-phase2.iso | sed 's@out/@@' > out/HuskOS-v3-phase2-SHA256.txt
stat -c '%s' out/HuskOS-v3-phase2.iso > out/HuskOS-v3-phase2-SIZE.txt
file out/HuskOS-v3-phase2.iso | tee out/iso-file.txt
grep -q 'ISO 9660' out/iso-file.txt
xorriso -indev out/HuskOS-v3-phase2.iso -report_el_torito plain > out/el-torito.txt 2>&1
grep -q UEFI out/el-torito.txt
xorriso -osirrox on -indev out/HuskOS-v3-phase2.iso \
  -extract /arch/x86_64/airootfs.sfs "$PWD/.build/v3-rootfs.sfs" \
  -extract /arch/boot/x86_64 "$PWD/.build/v3-iso-boot" > out/iso-extraction.log 2>&1
unsquashfs -processors 2 -d .build/v3-iso-root .build/v3-rootfs.sfs > out/squashfs-extraction.log 2>&1
python scripts/check-rootfs.py .build/v3-iso-root --boot .build/v3-iso-boot > out/iso-rootfs-check.json
python scripts/check-v3-rootfs.py .build/v3-iso-root --boot .build/v3-iso-boot > out/v3-rootfs-check.json
python - <<'PY'
import hashlib, json, os
from pathlib import Path
root = Path('.build/v3-iso-root')
report = dict(source_commit=os.environ['HUSK_SOURCE_SHA'],
    wallpaper_sha256=hashlib.sha256((root/'usr/share/ownos/wallpapers/husk-desert.jpg').read_bytes()).hexdigest(),
    iso_bytes=Path('out/HuskOS-v3-phase2.iso').stat().st_size,
    rootfs=json.loads(Path('out/iso-rootfs-check.json').read_text()),
    v3_rootfs=json.loads(Path('out/v3-rootfs-check.json').read_text()))
Path('out/v3-build.json').write_text(json.dumps(report,indent=2)+'\n')
PY

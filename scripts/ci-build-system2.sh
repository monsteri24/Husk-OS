#!/usr/bin/env bash
# Only the disposable privileged Arch container on the Actions runner.
set -euo pipefail
cd /src
[[ $(. /etc/os-release; printf '%s' "$ID") == arch && $EUID == 0 ]]
[[ ${HUSK_HOST_UID:?} =~ ^[0-9]+$ && $HUSK_HOST_UID -ne 0 ]]
[[ ${HUSK_HOST_GID:?} =~ ^[0-9]+$ ]]
# The host boot harness and release step must be able to create files in out/.
trap 'if [[ -d /src/out && ! -L /src/out ]]; then chown "$HUSK_HOST_UID:$HUSK_HOST_GID" /src/out; fi' EXIT
pacman -Sy --noconfirm archlinux-keyring
pacman -Syu --noconfirm --needed base-devel archiso git gnupg python python-yaml \
  wayland pkgconf gtk3 python-gobject python-cairo librsvg gettext gtk-layer-shell \
  xorg-server-xvfb xorg-xauth dbus
useradd --create-home --user-group --uid "$HUSK_HOST_UID" builder
install -d -m700 -o builder -g builder /husk-gnupg
runuser -u builder -- env GNUPGHOME=/husk-gnupg bash -eu -o pipefail -c '
  cd /src
  gpg --batch --pinentry-mode loopback --passphrase "" \
    --quick-generate-key "Husk OS System 2 ephemeral build key" ed25519 sign 1d
  OWNOS_SIGNING_KEY=$(gpg --batch --with-colons --list-secret-keys | awk -F: '\''$1 == "fpr" {print $10; exit}'\'')
  export OWNOS_SIGNING_KEY
  make check native
  bash scripts/build-packages.sh
'
pacman-key --init
# Retain System 1's proven TTY1/PAM/Wayland Live startup, without Calamares.
bash scripts/build-iso.sh --first-boot
images=(out/huskos-*.iso)
[[ ${#images[@]} == 1 && -s ${images[0]} ]]
file "${images[0]}" | tee out/iso-file.txt
grep -q 'ISO 9660' out/iso-file.txt
xorriso -indev "${images[0]}" -report_el_torito plain > out/el-torito.txt 2>&1
grep -q UEFI out/el-torito.txt
xorriso -indev "${images[0]}" -find / -type f -exec lsdl -- > out/iso-files.txt 2>&1
for payload in /arch/boot/x86_64/vmlinuz-linux /arch/boot/x86_64/initramfs-linux.img /arch/x86_64/airootfs.sfs; do
  grep -q "$payload" out/iso-files.txt
done
mv "${images[0]}" out/HuskOS-system-2.iso
sha256sum out/HuskOS-system-2.iso | sed 's@out/@@' > out/HuskOS-system-2-SHA256.txt
stat -c '%s' out/HuskOS-system-2.iso > out/HuskOS-system-2-SIZE.txt

# Independently check the filesystem actually stored inside the completed ISO.
xorriso -osirrox on -indev out/HuskOS-system-2.iso \
  -extract /arch/x86_64/airootfs.sfs "$PWD/.build/system2-rootfs.sfs" \
  -extract /arch/boot/x86_64 "$PWD/.build/system2-iso-boot" > out/iso-extraction.log 2>&1
unsquashfs -processors 2 -d .build/system2-iso-root .build/system2-rootfs.sfs > out/squashfs-extraction.log 2>&1
python3 scripts/check-rootfs.py .build/system2-iso-root --boot .build/system2-iso-boot > out/iso-rootfs-check.json
python3 - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('.build/system2-iso-root')
report = dict(source_commit=__import__('os').environ['HUSK_SOURCE_SHA'],
              wallpaper_sha256=hashlib.sha256((root / 'usr/share/ownos/wallpapers/husk-desert.jpg').read_bytes()).hexdigest(),
              iso_bytes=Path('out/HuskOS-system-2.iso').stat().st_size,
              rootfs=json.loads(Path('out/iso-rootfs-check.json').read_text()))
Path('out/system2-build.json').write_text(json.dumps(report, indent=2) + '\n')
PY

# A real signed optional-app transaction in the disposable BUILD container.
# This does not modify the ISO and does not stand in for GUI/polkit acceptance.
pacman -U --noconfirm .build/repo/ownos-core-*.pkg.tar.zst
printf 'y\n' | /usr/lib/ownos/own-admin install firefox 2>&1 | tee out/firefox-install.log
pacman -Q firefox | tee out/firefox-package.txt
runuser -u builder -- /usr/bin/firefox --version 2>&1 | tee out/firefox-version.txt
install -d -m755 -o builder -g builder /firefox-smoke
runuser -u builder -- timeout 60 /usr/bin/firefox --headless \
  --screenshot /firefox-smoke/firefox-headless.png about:blank > out/firefox-headless.log 2>&1
install -m644 /firefox-smoke/firefox-headless.png out/firefox-headless.png
test -s out/firefox-headless.png

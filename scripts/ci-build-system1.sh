#!/usr/bin/env bash
# Run only inside the disposable privileged Arch container on a CI runner.
set -euo pipefail
cd /src
[[ $(. /etc/os-release; printf '%s' "$ID") == arch ]]
[[ $EUID == 0 ]]
pacman -Sy --noconfirm archlinux-keyring
pacman -Syu --noconfirm --needed base-devel archiso git gnupg python python-yaml \
  wayland pkgconf gtk3 python-gobject gtk-layer-shell xorg-server-xvfb xorg-xauth dbus
useradd --create-home builder
install -d -m700 -o builder -g builder /husk-gnupg
chown -R builder:builder /src
runuser -u builder -- env GNUPGHOME=/husk-gnupg bash -eu -o pipefail -c '
  cd /src
  gpg --batch --pinentry-mode loopback --passphrase "" \
    --quick-generate-key "Husk OS System 1 ephemeral build key" ed25519 sign 1d
  OWNOS_SIGNING_KEY=$(gpg --batch --with-colons --list-secret-keys | awk -F: '\''$1 == "fpr" {print $10; exit}'\'')
  export OWNOS_SIGNING_KEY
  make check native
  # GTK preview regression runs in tests.yml on the supported Ubuntu host.
  # Arch container glycin/bwrap image sandbox cannot run on this runner;
  # do not disable its sandbox to turn a blocked GUI check into a pass.
  bash scripts/build-packages.sh
'
bash scripts/build-iso.sh --first-boot

# Only a completed mkarchiso image is eligible for publication.
images=(out/huskos-*.iso)
[[ ${#images[@]} == 1 && -s ${images[0]} ]]
file "${images[0]}" | tee out/iso-file.txt
file "${images[0]}" | grep -q 'ISO 9660'
xorriso -indev "${images[0]}" -report_el_torito plain > out/el-torito.txt 2>&1
grep -q UEFI out/el-torito.txt
xorriso -indev "${images[0]}" -find / -type f -exec lsdl -- > out/iso-files.txt 2>&1
grep -q '/arch/boot/x86_64/vmlinuz-linux' out/iso-files.txt
grep -q '/arch/boot/x86_64/initramfs-linux.img' out/iso-files.txt
grep -q '/arch/x86_64/airootfs.sfs' out/iso-files.txt
mv "${images[0]}" out/HuskOS-system-1.iso
cd out
sha256sum HuskOS-system-1.iso > HuskOS-system-1-SHA256.txt
stat -c '%s' HuskOS-system-1.iso > HuskOS-system-1-SIZE.txt

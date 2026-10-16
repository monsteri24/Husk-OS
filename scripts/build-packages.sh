#!/usr/bin/env bash
set -euo pipefail
ownos_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ownos_root"
ownos_with_installer=0
ownos_check_only=0
for ownos_arg in "$@"; do
  case "$ownos_arg" in
    --with-installer) ownos_with_installer=1 ;;
    --check) ownos_check_only=1 ;;
    *) echo 'Usage: build-packages.sh [--check] [--with-installer]' >&2; exit 2 ;;
  esac
done
if (( ownos_check_only )); then
  for ownos_tool in makepkg repo-add gpg cc make wayland-scanner; do command -v "$ownos_tool" >/dev/null || { echo "Missing: $ownos_tool" >&2; exit 1; }; done
  echo 'Package tools found. Dependencies and signatures are checked during the build.'
  exit 0
fi
[[ $EUID -ne 0 ]] || { echo 'Run makepkg as a regular user in a disposable Arch build VM.' >&2; exit 1; }
[[ "${OWNOS_SIGNING_KEY:-}" =~ ^[0-9A-Fa-f]{40}$ ]] || { echo 'Set OWNOS_SIGNING_KEY to the full fingerprint of your build signing key.' >&2; exit 1; }
gpg --list-secret-keys "$OWNOS_SIGNING_KEY" >/dev/null
[[ ! -e .build/repo ]] || { echo '.build/repo exists. Keep it or move it aside before rebuilding.' >&2; exit 1; }
mkdir -p .build/repo .build/keys .build/packages/ownos .build/packages/calamares
gpg --export "$OWNOS_SIGNING_KEY" > .build/keys/ownos.gpg
printf '%s:6:\n' "$OWNOS_SIGNING_KEY" > .build/keys/ownos-trusted
: > .build/keys/ownos-revoked
python3 scripts/source-tar.py
ownos_checksum="$(sha256sum .build/packages/ownos/ownos-source.tar.gz | cut -d ' ' -f 1)"
sed "s/__SOURCE_SHA256__/$ownos_checksum/" packaging/ownos/PKGBUILD > .build/packages/ownos/PKGBUILD
cp packaging/calamares/PKGBUILD .build/packages/calamares/PKGBUILD
ownos_packages=(ownos)
if (( ownos_with_installer )); then ownos_packages=(calamares ownos); fi
for ownos_package in "${ownos_packages[@]}"; do
  (cd ".build/packages/$ownos_package"; makepkg --sign --key "$OWNOS_SIGNING_KEY")
  cp .build/packages/"$ownos_package"/*.pkg.tar.zst .build/packages/"$ownos_package"/*.pkg.tar.zst.sig .build/repo/
done
repo-add --sign --key "$OWNOS_SIGNING_KEY" .build/repo/ownos.db.tar.gz .build/repo/*.pkg.tar.zst
python3 scripts/verify-repo.py .build/repo .build/keys/ownos.gpg
echo 'Signed package repository ready at .build/repo. No packages were installed by this script.'

#!/usr/bin/env bash
set -euo pipefail
ownos_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ownos_root"
export PYTHONPATH="$ownos_root/src"
ownos_profile_args=()
ownos_check_only=0
for ownos_arg in "$@"; do
  case "$ownos_arg" in
    --with-installer) ownos_profile_args+=(--with-installer) ;;
    --first-boot) ownos_profile_args+=(--first-boot) ;;
    --check) ownos_check_only=1 ;;
    *) echo 'Usage: build-iso.sh [--check] [--with-installer] [--first-boot]' >&2; exit 2 ;;
  esac
done
if (( ownos_check_only )); then exec python3 -m ownos.build --check "${ownos_profile_args[@]}"; fi
python3 -m ownos.build --check "${ownos_profile_args[@]}"
[[ $EUID == 0 ]] || { echo 'Run the ISO step with sudo inside the Arch build VM.' >&2; exit 1; }
[[ ! -e .build/profile && ! -e .build/archiso-work ]] || { echo 'Profile/work exists; move the previous build aside before rebuilding.' >&2; exit 1; }
python3 scripts/verify-repo.py .build/repo .build/keys/ownos.gpg
ownos_fingerprint="$(cat .build/keys/ownos-trusted)"
ownos_fingerprint="${ownos_fingerprint%%:*}"
[[ "$ownos_fingerprint" =~ ^[0-9A-Fa-f]{40}$ ]] || { echo 'Invalid signing-key fingerprint.' >&2; exit 1; }
# These keyring changes affect only the build VM where this script is run.
pacman-key --add .build/keys/ownos.gpg
pacman-key --lsign-key "$ownos_fingerprint"
python3 -m ownos.build --output .build/profile "${ownos_profile_args[@]}"
python3 scripts/check-profile.py .build/profile
mkdir -p out
mkarchiso -v -w "$ownos_root/.build/archiso-work" -o "$ownos_root/out" "$ownos_root/.build/profile"
python3 scripts/check-rootfs.py "$ownos_root/.build/archiso-work/x86_64/airootfs" \
  --boot "$ownos_root/.build/archiso-work/x86_64/boot" > out/rootfs-check.json
sha256sum out/*.iso > out/SHA256SUMS
echo 'ISO created. Boot and installation acceptance still requires the VM checklist.'

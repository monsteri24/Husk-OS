#!/usr/bin/env bash
# Actual signed transactions in a fresh disposable Arch container only.
# No package or keyring changes are made inside the recovered Live ISO.
set -euo pipefail
cd /src
[[ -e /.dockerenv && $EUID == 0 && ${HUSK_CI_APP_TEST:-} == 1 ]]
[[ $(. /etc/os-release; printf '%s' "$ID") == arch ]]
[[ ${HUSK_HOST_UID:?} =~ ^[0-9]+$ && $HUSK_HOST_UID -ne 0 ]]
[[ ${HUSK_HOST_GID:?} =~ ^[0-9]+$ ]]
husk_app_root=/src/.build/v3-app-root
[[ -s "$husk_app_root/etc/pacman.conf" && -d "$husk_app_root/opt/ownos/repo" ]]
mkdir -p out
trap 'chown "$HUSK_HOST_UID:$HUSK_HOST_GID" out/v3-app-* 2>/dev/null || true' EXIT
pacman-key --init
pacman -Sy --noconfirm archlinux-keyring
pacman -Syu --noconfirm --needed python polkit gnupg noto-fonts pipewire-jack mesa
useradd --create-home --user-group --uid "$HUSK_HOST_UID" builder
install -d -m755 /opt/ownos/repo
cp -a "$husk_app_root/opt/ownos/repo/." /opt/ownos/repo/
husk_app_fingerprint=$(cut -d: -f1 "$husk_app_root/usr/share/pacman/keyrings/ownos-trusted")
[[ "$husk_app_fingerprint" =~ ^[0-9A-Fa-f]{40}$ ]]
pacman-key --add "$husk_app_root/usr/share/pacman/keyrings/ownos.gpg"
pacman-key --lsign-key "$husk_app_fingerprint"
cp "$husk_app_root/etc/pacman.conf" /etc/pacman.conf
husk_app_core=(/opt/ownos/repo/ownos-core-*.pkg.tar.zst)
[[ ${#husk_app_core[@]} == 1 && -s ${husk_app_core[0]} ]]
pacman -U --noconfirm "${husk_app_core[0]}"
# Provider setup is explicit CI infrastructure. Both full upgrade/install
# transactions below still execute the shipped allowlisted graphical helper.
pacman -Syu --noconfirm --needed lib32-mesa lib32-vulkan-radeon lib32-vulkan-intel
for husk_app_id in firefox steam; do
  if pacman -Q "$husk_app_id" >/dev/null 2>&1; then
    echo "The disposable test must start without $husk_app_id" >&2; exit 1
  fi
  timeout 900 /usr/lib/ownos/own-admin install-confirmed "$husk_app_id" \
    2>&1 | tee "out/v3-app-$husk_app_id.log"
  grep -q 'OWNOS-STAGE:preflight' "out/v3-app-$husk_app_id.log"
  pacman -Q "$husk_app_id" | tee "out/v3-app-$husk_app_id-package.txt"
done
runuser -u builder -- /usr/bin/firefox --version 2>&1 | tee out/v3-app-firefox-version.txt
test -x /usr/bin/steam
test -s /usr/share/applications/steam.desktop
grep -q '^Icon=steam' /usr/share/applications/steam.desktop
python - <<'PY'
import json, os
from pathlib import Path
report=dict(status='PASSED', image_source=os.environ['HUSK_IMAGE_SOURCE'],
    image_sha256=Path('out/HuskOS-v3-phase2-SHA256.txt').read_text().split()[0],
    scope='Actual shipped root helper, repository/DNS preflight and signed full-system transactions',
    authentication='NOT TESTED: explicitly consented disposable root container',
    steam_client_and_games='NOT TESTED', packages={})
for name in ('firefox','steam'):
    report['packages'][name]=Path('out/v3-app-'+name+'-package.txt').read_text().strip()
Path('out/v3-app-result.json').write_text(json.dumps(report,indent=2)+'\n')
PY

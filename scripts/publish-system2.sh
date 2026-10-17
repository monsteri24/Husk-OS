#!/usr/bin/env bash
# Publish an already verified image; no build, guest mutation or permission expansion.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ ${GITHUB_ACTIONS:-} == true ]]
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_SHA:?}" "${HUSK_IMAGE_SOURCE:?}"
(cd out && sha256sum -c HuskOS-system-2-SHA256.txt)
python3 - <<'CHECK'
import json, os
from pathlib import Path
out = Path('out')
boot = json.loads((out / 'boot-system2/result.json').read_text())
image = json.loads((out / 'system2-build.json').read_text())
rootfs = json.loads((out / 'iso-rootfs-check.json').read_text())
digest = (out / 'HuskOS-system-2-SHA256.txt').read_text().split()[0]
size = (out / 'HuskOS-system-2.iso').stat().st_size
assert image['source_commit'] == os.environ['HUSK_IMAGE_SOURCE']
assert rootfs['status'] == 'PASS' and rootfs['problems'] == []
assert all(boot.get(key) == 'PASSED' for key in ('boot', 'terminal', 'shutdown')), boot
assert boot['iso_sha256'] == digest and boot['iso_bytes'] == size
assert boot['problems'] == [] and boot['desktop_status']['version'] == 'system-2'
assert (out / 'firefox-package.txt').read_text().startswith('firefox ')
assert (out / 'firefox-version.txt').read_text().startswith('Mozilla Firefox ')
assert (out / 'firefox-headless.png').stat().st_size > 0
CHECK
set -euo pipefail
iso_sha=$(cut -d ' ' -f1 out/HuskOS-system-2-SHA256.txt)
iso_size=$(cat out/HuskOS-system-2-SIZE.txt)
cat > out/RELEASE-NOTES.md <<EOF
Husk OS System 2 is an experimental Arch-based gaming operating system with its own GTK Husk Desktop and Labwc/Wayland.

This release is a Live USB/VM environment. It has no completed graphical operating-system installer. The historical System 1 release is preserved unchanged.

Includes the original black-and-gold desert wallpaper, English UI, Start/search/taskbar, window controls, Husk Settings, Husk Files, Foot terminal and user-confirmed optional application installation. System 2 supports English only; Finnish translations are preserved in source for a future release. Steam, Firefox, Heroic and other optional user apps are not preinstalled.

Source/GTK/native and real nested Labwc interaction checks passed before building. The resulting ISO filesystem, exact wallpaper and installed package inventory were checked, then the exact ISO booted through QEMU/OVMF to the live Wayland desktop and shut down. A real signed Firefox installation and headless launch were tested separately in the disposable Arch build container; this is not a physical hardware or GUI authentication test.

Known limits: no System 2 physical hardware acceptance; no game/FPS, NVIDIA/Optimus, VRR, suspend, multi-monitor or long-duration certification. CPU policy and Optimus controls are planned. GameMode/MangoHud and 32-bit gaming libraries are optional and must be installed when needed; first-boot edition ships 64-bit Mesa. Unsupported anti-cheat games are not promised. Native .hpk packaging and a maintained Husk update repository remain planned. GUI/polkit authentication for a real network application installation on Live hardware still needs acceptance testing.

Image source commit: $HUSK_IMAGE_SOURCE
Accepted verification commit: ${HUSK_VERIFICATION_SHA:-$GITHUB_SHA}
Publication/tag commit: $GITHUB_SHA (the OS payload is unchanged from the image source)
Filename: HuskOS-system-2.iso
Size: $iso_size bytes
SHA-256: $iso_sha

Download/checksum/USB guide: https://github.com/$GITHUB_REPOSITORY/blob/main/docs/INSTALL.md
Automated evidence is attached. Physical USB testing is separate.
EOF
extra_evidence=()
if [[ -s out/system2-recovery.json ]]; then extra_evidence+=(out/system2-recovery.json); fi
gh release create system-2 --repo "$GITHUB_REPOSITORY" --target "$GITHUB_SHA" \
  --title 'Husk OS System 2 — Experimental Live' --prerelease --notes-file out/RELEASE-NOTES.md \
  out/HuskOS-system-2.iso out/HuskOS-system-2-SHA256.txt out/system2-build.json \
  out/iso-rootfs-check.json out/boot-system2/result.json out/boot-system2/guest.json \
  out/boot-system2/desktop-start.png out/boot-system2/desktop-terminal.png \
  out/firefox-package.txt out/firefox-version.txt out/firefox-headless.png "${extra_evidence[@]}"
asset=$(gh api "repos/$GITHUB_REPOSITORY/releases/tags/system-2" \
  --jq '.assets[] | select(.name=="HuskOS-system-2.iso")')
test "$(jq -r .state <<< "$asset")" = uploaded
test "$(jq -r .size <<< "$asset")" = "$iso_size"
test "$(jq -r .digest <<< "$asset")" = "sha256:$iso_sha"
download_url=$(jq -r .browser_download_url <<< "$asset")
curl --fail --location --retry 2 --max-time 600 "$download_url" -o "$RUNNER_TEMP/HuskOS-system-2.iso"
test "$(sha256sum "$RUNNER_TEMP/HuskOS-system-2.iso" | cut -d ' ' -f1)" = "$iso_sha"
printf 'ISO: %s\nSize: %s bytes\nSHA-256: %s\nSource: %s\nQEMU/OVMF: PASSED\nPhysical hardware: NOT TESTED\n' \
  "$download_url" "$iso_size" "$iso_sha" "$HUSK_IMAGE_SOURCE" | tee -a "$GITHUB_STEP_SUMMARY"

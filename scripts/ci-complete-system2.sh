#!/usr/bin/env bash
# Resume verification of the immutable ISO preserved by the earlier Actions run.
set -euo pipefail
cd /src
[[ $(. /etc/os-release; printf '%s' "$ID") == arch && $EUID == 0 ]]
[[ ${HUSK_HOST_UID:?} =~ ^[0-9]+$ && $HUSK_HOST_UID -ne 0 ]]
[[ ${HUSK_HOST_GID:?} =~ ^[0-9]+$ ]]
[[ ${HUSK_SOURCE_SHA:?} == b1c27dd8bc73d7dc4e9f9856083dd69c67f30d58 ]]
trap 'if [[ -d /src/out && ! -L /src/out ]]; then chown "$HUSK_HOST_UID:$HUSK_HOST_GID" /src/out; fi' EXIT
test "$(stat -c '%s' out/HuskOS-system-2.iso)" = 2101264384
test "$(sha256sum out/HuskOS-system-2.iso | cut -d ' ' -f1)" = d36214faecce244cf5c92e0730849857821499cae4f20c3bd71f2448952e8f99
pacman -Sy --noconfirm archlinux-keyring
pacman -Syu --noconfirm --needed python python-yaml gnupg libisoburn squashfs-tools
useradd --create-home --user-group --uid "$HUSK_HOST_UID" builder
mkdir -p .build

file out/HuskOS-system-2.iso | tee out/iso-file.txt
grep -q 'ISO 9660' out/iso-file.txt
xorriso -indev out/HuskOS-system-2.iso -report_el_torito plain > out/el-torito.txt 2>&1
grep -q UEFI out/el-torito.txt
xorriso -osirrox on -indev out/HuskOS-system-2.iso \
  -extract /arch/x86_64/airootfs.sfs "$PWD/.build/system2-rootfs.sfs" \
  -extract /arch/boot/x86_64 "$PWD/.build/system2-iso-boot" > out/iso-extraction.log 2>&1
unsquashfs -processors 2 -d .build/system2-iso-root .build/system2-rootfs.sfs > out/squashfs-extraction.log 2>&1
python3 scripts/check-rootfs.py .build/system2-iso-root --boot .build/system2-iso-boot > out/iso-rootfs-check.json

# Install the signed Husk helper actually embedded in this exact image.
# Both the explicit detached-signature check and pacman's normal checks remain.
repo="$PWD/.build/system2-iso-root/opt/ownos/repo"
key="$PWD/.build/system2-iso-root/opt/ownos/repo-key.gpg"
packages=("$repo"/ownos-core-*.pkg.tar.zst)
[[ ${#packages[@]} == 1 && -s ${packages[0]}.sig ]]
gpgv --keyring "$key" "${packages[0]}.sig" "${packages[0]}"
fingerprint=$(gpg --batch --with-colons --show-keys "$key" | awk -F: '$1 == "fpr" {print $10; exit}')
[[ $fingerprint =~ ^[0-9A-Fa-f]{40}$ ]]
pacman-key --init
pacman-key --add "$key"
pacman-key --lsign-key "$fingerprint"
pacman -U --noconfirm "${packages[0]}"
bash scripts/ci-test-application.sh

python3 - <<'PY'
import ast, hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0, 'src')
from ownos.rootfs import guest_path
root = Path('.build/system2-iso-root')
language = {}
for node in ast.parse((root / 'usr/lib/ownos/ownos/i18n.py').read_text()).body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in ('DEFAULT_LANGUAGE', 'SUPPORTED_LANGUAGES'):
                language[target.id] = ast.literal_eval(node.value)
assert language == dict(DEFAULT_LANGUAGE='en', SUPPORTED_LANGUAGES=('en',)), language
assert not list(root.glob('usr/share/locale/*/LC_MESSAGES/huskos.mo')), 'Postponed catalogs must not ship'
for payload in ('usr/bin/pkexec', 'usr/bin/husk-install-app', 'usr/lib/ownos/own-admin',
                'usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1'):
    path = guest_path(root, payload)
    assert path.is_file() and path.stat().st_mode & 0o111, payload
with Path('out/HuskOS-system-2.iso').open('rb') as stream:
    iso_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
result = dict(image_source_commit=os.environ['HUSK_SOURCE_SHA'], reused_iso=True,
              iso_bytes=Path('out/HuskOS-system-2.iso').stat().st_size,
              iso_sha256=iso_digest, husk_language=language, authentication_payloads_present=True,
              wallpaper_sha256=hashlib.sha256((root / 'usr/share/ownos/wallpapers/husk-desert.jpg').read_bytes()).hexdigest(),
              rootfs=json.loads(Path('out/iso-rootfs-check.json').read_text()),
              application='Signed Firefox package transaction, installed-state query and normal sandboxed headless launch passed in the separate build container')
Path('out/system2-recovery.json').write_text(json.dumps(result, indent=2) + '\n')
PY

#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
command -v xgettext >/dev/null || { echo 'Install GNU gettext to update translation messages.' >&2; exit 1; }
mkdir -p locale
python_sources="$(mktemp)"
desktop_sources="$(mktemp)"
trap 'rm -f -- "$python_sources" "$desktop_sources"' EXIT
find src/ownos installer/owninstall -type f -name '*.py' -print | LC_ALL=C sort > "$python_sources"
find data installer -type f -name '*.desktop' -print | LC_ALL=C sort > "$desktop_sources"

xgettext --from-code=UTF-8 --language=Python \
    --keyword=_ --keyword=gettext --keyword=gettext_ --keyword=ngettext:1,2 \
    --package-name='Husk OS' --package-version='system-2-dev' \
    --copyright-holder='Husk OS contributors' \
    --msgid-bugs-address='https://github.com/monsteri24/Husk-OS/issues' \
    --sort-by-file --files-from="$python_sources" bin/own-admin \
    --output=locale/huskos.pot
xgettext --from-code=UTF-8 --language=Desktop --join-existing \
    --keyword=Name --keyword=GenericName --keyword=Comment --keyword=Keywords \
    --package-name='Husk OS' --package-version='system-2-dev' \
    --copyright-holder='Husk OS contributors' \
    --msgid-bugs-address='https://github.com/monsteri24/Husk-OS/issues' \
    --sort-by-file --files-from="$desktop_sources" --output=locale/huskos.pot

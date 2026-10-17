#!/usr/bin/env bash
# Real optional-app smoke test in the disposable Arch CI container only.
# The caller installs the verified ownos-core package and creates builder/out.
set -euo pipefail
cd /src
[[ $(. /etc/os-release; printf '%s' "$ID") == arch && $EUID == 0 ]]
[[ -d out && ! -L out && $(id -u builder) -ne 0 ]]
if pacman -Q firefox > /dev/null 2>&1; then
  echo 'Firefox must be absent before the optional-app installation smoke test.' >&2
  exit 1
fi

# These explicit trusted runtime providers are CI setup, after ISO creation.
# Otherwise pacman asks numbered jack/font provider questions before Proceed,
# consuming the one affirmative response intended for the actual transaction.
pacman -Syu --noconfirm --needed noto-fonts pipewire-jack 2>&1 | tee out/firefox-provider-setup.log
printf 'y\n' | timeout 600 /usr/lib/ownos/own-admin install firefox 2>&1 | tee out/firefox-install.log
pacman -Q firefox | tee out/firefox-package.txt
runuser -u builder -- /usr/bin/firefox --version 2>&1 | tee out/firefox-version.txt
install -d -m755 -o builder -g builder /firefox-smoke
runuser -u builder -- timeout 60 /usr/bin/firefox --headless \
  --screenshot /firefox-smoke/firefox-headless.png about:blank > out/firefox-headless.log 2>&1
install -m644 /firefox-smoke/firefox-headless.png out/firefox-headless.png
test -s out/firefox-headless.png

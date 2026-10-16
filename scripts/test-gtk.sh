#!/usr/bin/env bash
set -euo pipefail
ownos_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ownos_root"
export PYTHONPATH="$ownos_root/src${PYTHONPATH:+:$PYTHONPATH}"
export OWNOS_UI_TESTS=1
exec dbus-run-session -- xvfb-run -a python3 -m unittest discover -s tests -v

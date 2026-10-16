#!/usr/bin/env python3
"""Check installed ISO payloads without executing programs from the guest."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ownos.rootfs import validate_rootfs

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('rootfs', type=Path)
parser.add_argument('--boot', type=Path, help='mkarchiso work/<arch>/boot containing relocated boot artifacts')
args = parser.parse_args()
try:
    problems = validate_rootfs(args.rootfs, boot=args.boot)
except (OSError, ValueError) as exc:
    problems = [str(exc)]
print(json.dumps({'status': 'FAIL' if problems else 'PASS', 'rootfs': str(args.rootfs),
                  'boot': str(args.boot) if args.boot else None, 'problems': problems}, indent=2))
raise SystemExit(1 if problems else 0)

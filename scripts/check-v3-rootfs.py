#!/usr/bin/env python3
"""Check V3 ISO artifact payloads; this does not run an installer or boot test."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ownos.v3_rootfs import validate_v3_rootfs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rootfs', type=Path)
    parser.add_argument('--boot', type=Path, help='Extracted ISO arch/boot/x86_64 directory')
    args = parser.parse_args(argv)
    try:
        problems = validate_v3_rootfs(args.rootfs, boot=args.boot)
    except (OSError, ValueError) as exc:
        problems = [str(exc)]
    print(json.dumps({'status': 'FAIL' if problems else 'PASS',
                      'proof_scope': 'artifact-payloads-only',
                      'rootfs': str(args.rootfs), 'boot': str(args.boot) if args.boot else None,
                      'problems': problems}, indent=2))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate a generated Archiso profile without installing or booting it."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ownos.build import validate_profile

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('profile',type=Path)
args=parser.parse_args()
try: problems=validate_profile(args.profile)
except (OSError,ValueError) as exc: problems=[str(exc)]
print('\n'.join(problems) if problems else 'Husk OS live profile checks: PASS. Boot acceptance is still required.')
raise SystemExit(1 if problems else 0)

#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ownos.vm import main
try: raise SystemExit(main())
except (OSError, ValueError) as exc:
    print('OwnOS VM:', exc, file=sys.stderr); raise SystemExit(1)

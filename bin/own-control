#!/usr/bin/env python3
import sys
from pathlib import Path
source = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(source) if source.is_dir() else '/usr/lib/ownos')
try:
    from ownos.identity import OS_NAME
    from ownos.cli import main
    raise SystemExit(main())
except (OSError, ValueError, RuntimeError, ImportError) as exc:
    print('Husk OS:', str(exc), file=sys.stderr)
    raise SystemExit(1)

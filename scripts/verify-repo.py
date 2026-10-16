#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ownos.build import repository_files

repo = Path(sys.argv[1]).resolve(); key = Path(sys.argv[2]).resolve()
for artifact in [repo / 'ownos.db.tar.gz', *repository_files(repo)]:
    subprocess.run(['/usr/bin/gpgv', '--keyring', str(key), str(artifact) + '.sig', str(artifact)], check=True)
print('Repository database and all package signatures verified.')

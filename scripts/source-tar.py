#!/usr/bin/env python3
"""Create the local makepkg input, including only public repository keys."""
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / '.build/packages/ownos/ownos-source.tar.gz'
with tarfile.open(target, 'w:gz') as archive:
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(p in ('.git', '.build', '.superpowers', 'out', '__pycache__', '.test-runtime') for p in relative.parts):
            continue
        if path.is_file() and path.suffix not in ('.pyc', '.iso'):
            archive.add(path, 'ownos/' + str(relative), recursive=False)
    for name in ('ownos.gpg', 'ownos-trusted', 'ownos-revoked'):
        archive.add(root / '.build/keys' / name, 'ownos/keys/' + name)

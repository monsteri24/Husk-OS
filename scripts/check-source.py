#!/usr/bin/env python3
"""Syntax/configuration verification, with no package or disk mutations."""
import ast
import configparser
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parents[1]
checked = 0
for directory in ('src', 'scripts', 'installer/owninstall', 'tests'):
    for path in (root / directory).rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path)); checked += 1
for pattern in ('packaging/*/PKGBUILD', 'scripts/*.sh', 'iso/*.sh'):
    for path in root.glob(pattern):
        subprocess.run(['bash', '-n', str(path)], check=True); checked += 1
for path in [root / 'bin/own-session', root / 'iso/live-setup', root / 'iso/live-keyring', root / 'config/labwc/autostart']:
    subprocess.run(['sh', '-n', str(path)], check=True); checked += 1
for path in [root / 'config/labwc/rc.xml', *root.glob('data/*.policy'), *root.glob('installer/*.policy'), *root.glob('native/protocols/*.xml')]:
    ET.parse(path); checked += 1
for path in [*root.glob('data/*.desktop'), *root.glob('installer/*.desktop'), root / 'branding/sddm/metadata.desktop']:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read(path); assert parser.sections(), str(path); checked += 1
try:
    import yaml
except ImportError:
    raise SystemExit('Install PyYAML in the test environment to validate Calamares YAML.')
for path in list((root / 'installer').rglob('*.conf')) + list((root / 'installer').rglob('*.desc')):
    assert isinstance(yaml.safe_load(path.read_text()), dict), str(path); checked += 1
print(f'{checked} source/configuration syntax checks passed. No graphical or boot test is implied.')

#!/usr/bin/env python3
"""Exercise actual GTK CSS fallback without creating windows or a display."""
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ownos.ui import common

with tempfile.TemporaryDirectory() as tmp:
    css = Path(tmp) / 'desktop.css'
    css.write_text('* { bad-property: ; }')
    assert hasattr(common, 'create_style_provider'), 'Display-independent style parser is missing'
    provider = common.create_style_provider(override_path=css)
    assert provider.husk_style_warning, 'Malformed user CSS was not reported'
    assert '.panel' in provider.to_string(), 'Default style was lost'
    css.write_text('.panel { padding: 19px; }')
    provider = common.create_style_provider(override_path=css)
    assert not provider.husk_style_warning, provider.husk_style_warning
    assert '19px' in provider.to_string(), 'Valid user style was not applied'
print('Actual GTK CSS fallback and custom appearance: PASS (no window/display test)')

"""Write validated labwc input settings without losing existing keybindings."""
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from ownos.config import validate


def _replace(path, content):
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_input_config(directory, template, settings):
    settings = validate(settings)
    directory = Path(directory)
    target = directory / 'rc.xml'
    tree = ET.parse(target if target.exists() else template)
    root = tree.getroot()
    libinput = root.find('libinput')
    if libinput is None:
        libinput = ET.SubElement(root, 'libinput')
    device = next((d for d in libinput.findall('device') if d.get('category') == 'mouse'), None)
    if device is None:
        device = ET.SubElement(libinput, 'device', category='mouse')
    for key, value in [('pointerSpeed', str(settings['pointer_speed'])), ('accelProfile', 'flat')]:
        el = device.find(key)
        if el is None:
            el = ET.SubElement(device, key)
        el.text = value
    environment = directory / 'environment'
    lines = environment.read_text().splitlines() if environment.exists() else []
    lines = [line for line in lines if not line.startswith(('XKB_DEFAULT_LAYOUT=', 'XKB_DEFAULT_VARIANT='))]
    lines.append('XKB_DEFAULT_LAYOUT=' + settings['keymap'])
    lines.append('XKB_DEFAULT_VARIANT=' + settings['keymap_variant'])
    directory.mkdir(parents=True, exist_ok=True)
    _replace(target, ET.tostring(root, encoding='utf-8', xml_declaration=True))
    _replace(environment, ('\n'.join(lines) + '\n').encode())
    return directory
